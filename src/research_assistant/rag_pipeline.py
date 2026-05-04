import json
from typing import Any, Generator, TypedDict

from langgraph.graph import END, StateGraph

from .config import settings
from .citations import ensure_references
from .llm import chat, route_report, stream_chat
from .manual_ingest import document_id_for, point_id_for, sha256_text
from .reranker import rerank
from .search import SEARCH_WEB_TOOL, content_hash, search_and_scrape
from .text import chunk_text
from .vector_store import count, search, upsert_chunks
from .workbases import add_message, conversation_history, next_dataset_id, now_iso, record_dataset

TOOL_SYSTEM_PROMPT = """You are Research Assistant, a ChatGPT-like assistant with a growing web knowledge base.

For every user question, you must call search_web first. Create a focused search query that will help answer the latest user message.
Do not answer directly in this step."""

ANSWER_SYSTEM_PROMPT = """You are Research Assistant, a helpful research chatbot powered by RAG.

Answer only from the retrieved workbase knowledge.
Use citations like [1], [2], [3] for the evidence you used.
If the retrieved knowledge is not enough, say what is missing and cite the closest available sources.
Be clear, direct, and useful."""


class PipelineState(TypedDict, total=False):
    workbase_id: str
    user_message: str
    model: str | None
    history: list[dict[str, str]]
    query: str
    num_results: int
    results: list[dict]
    failed_scrapes: list[dict]
    dataset_id: str
    chunks_added: int
    total_chunks: int
    context: str
    sources: list[dict]
    technical_mode: bool
    retrieval_mode: str
    answer_style: str
    document_id: str
    tags: list[str]
    planner_model: str
    planner_usage: dict[str, int]


def _search_query_from_tool(history: list[dict[str, str]], user_message: str, model: str | None) -> tuple[str, int, dict]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": TOOL_SYSTEM_PROMPT}]
    messages.extend(history[-8:])
    messages.append({"role": "user", "content": user_message})

    response = chat(messages, model=model, tools=[SEARCH_WEB_TOOL], task="planner")
    if not response["tool_calls"]:
        return user_message, settings.searxng_results, response

    tool_call = response["tool_calls"][0]
    try:
        args = json.loads(tool_call.get("arguments") or "{}")
    except json.JSONDecodeError:
        args = {}

    query = (args.get("query") or user_message).strip()
    num_results = int(args.get("num_results") or settings.max_search_results)
    return query, max(1, min(num_results, 10)), response


def _chunks_from_results(workbase_id: str, results: list[dict], query: str, dataset_id: str) -> list[dict]:
    chunks: list[dict] = []
    created_at = now_iso()
    for result in results:
        text = result.get("content") or result.get("snippet") or ""
        canonical_url = result.get("canonical_url", result.get("url", ""))
        document_id = document_id_for(workbase_id, canonical_url)
        for index, chunk in enumerate(
            chunk_text(text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
        ):
            chunk_hash = content_hash(chunk)
            chunks.append(
                {
                    "id": point_id_for(document_id, index, chunk_hash),
                    "text": chunk,
                    "dataset_id": dataset_id,
                    "source_id": result.get("source_id", ""),
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "canonical_url": canonical_url,
                    "search_query": query,
                    "source_position": result.get("position", 0),
                    "chunk_index": index,
                    "created_at": created_at,
                    "ingested_at": created_at,
                    "source_origin": result.get("source_origin", "agent_web"),
                    "trust_level": result.get("trust_level", "general_web"),
                    "is_verified": result.get("is_verified", False),
                    "ingestion_method": "search_web",
                    "parser_name": result.get("content_source", ""),
                    "document_id": document_id,
                    "source_fingerprint": content_hash(canonical_url, text),
                    "content_hash": chunk_hash,
                    "file_type": "web",
                    "accessed_date": created_at[:10],
                    "citation_key": sha256_text(canonical_url)[:12],
                }
            )
    return chunks


def _context(rows: list[dict]) -> tuple[str, list[dict]]:
    parts: list[str] = []
    sources: list[dict] = []
    for index, row in enumerate(rows, start=1):
        meta = row.get("metadata", {})
        score = row.get("rerank_score", row.get("score", 0.0))
        parts.append(
            f"[{index}] Title: {meta.get('title', 'Untitled')}\n"
            f"URL: {meta.get('url', '')}\n"
            f"Dataset: {meta.get('dataset_id', '')}\n"
            f"Trust: {meta.get('trust_level', 'general_web')}\n"
            f"Search query: {meta.get('search_query', '')}\n"
            f"Content: {row['text']}"
        )
        sources.append(
            {
                "title": meta.get("title", "Untitled"),
                "url": meta.get("url", ""),
                "dataset_id": meta.get("dataset_id", ""),
                "document_id": meta.get("document_id", ""),
                "source_id": meta.get("source_id", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "trust_level": meta.get("trust_level", "general_web"),
                "source_origin": meta.get("source_origin", "agent_web"),
                "search_query": meta.get("search_query", ""),
                "author": meta.get("author", ""),
                "year": meta.get("year", ""),
                "accessed_date": meta.get("accessed_date", ""),
                "citation_key": meta.get("citation_key", ""),
                "score": float(score or 0.0),
                "score_reranker": float(row.get("score_reranker", row.get("rerank_score", row.get("score", 0.0))) or 0.0),
                "authority_boost": float(row.get("authority_boost", 1.0) or 1.0),
                "score_final": float(row.get("score_final", score) or 0.0),
            }
        )
    return "\n\n".join(parts), sources


def _plan_search_node(state: PipelineState) -> PipelineState:
    query, num_results, response = _search_query_from_tool(
        state.get("history", []),
        state["user_message"],
        None,
    )
    return {
        "query": query,
        "num_results": num_results,
        "planner_model": response.get("model", ""),
        "planner_usage": response.get("usage", {}),
    }


def _search_node(state: PipelineState) -> PipelineState:
    results = search_and_scrape(
        state["query"],
        num_results=state["num_results"],
        technical_mode=state.get("technical_mode", settings.technical_mode),
    )
    failed_scrapes = [item for item in results if item.get("scrape_status") == "failed"]
    return {"results": results, "failed_scrapes": failed_scrapes}


def _ingest_node(state: PipelineState) -> PipelineState:
    if not state.get("results"):
        return {"dataset_id": "", "chunks_added": 0, "total_chunks": count(state["workbase_id"])}

    dataset_id = next_dataset_id(state["workbase_id"])
    chunks = _chunks_from_results(state["workbase_id"], state["results"], state["query"], dataset_id)
    stats = upsert_chunks(state["workbase_id"], chunks)
    chunks_added = stats["chunks_added"] + stats["chunks_updated"]
    total_chunks = count(state["workbase_id"])
    record_dataset(
        state["workbase_id"],
        dataset_id,
        state["query"],
        state["results"],
        chunks_added=chunks_added,
        chunks_updated=stats["chunks_updated"],
        duplicates_skipped=stats["duplicates_skipped"],
        total_chunks=total_chunks,
    )
    return {"dataset_id": dataset_id, "chunks_added": chunks_added, "total_chunks": total_chunks}


def _retrieve_node(state: PipelineState) -> PipelineState:
    candidates = search(
        state["workbase_id"],
        state["user_message"],
        limit=settings.reranker_candidate_limit,
        retrieval_mode=state.get("retrieval_mode", "all"),
        document_id=state.get("document_id") or None,
        tags=state.get("tags") or None,
    )
    ranked = rerank(state["user_message"], candidates, top_k=settings.reranker_top_k)
    context, sources = _context(ranked)
    return {"context": context, "sources": sources}


def _build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("plan_search", _plan_search_node)
    graph.add_node("search_web", _search_node)
    graph.add_node("ingest_dataset", _ingest_node)
    graph.add_node("retrieve_workbase", _retrieve_node)
    graph.set_entry_point("plan_search")
    graph.add_edge("plan_search", "search_web")
    graph.add_edge("search_web", "ingest_dataset")
    graph.add_edge("ingest_dataset", "retrieve_workbase")
    graph.add_edge("retrieve_workbase", END)
    return graph.compile()


INGESTION_GRAPH = _build_graph()


def context_for_question(
    workbase_id: str,
    question: str,
    retrieval_mode: str = "all",
    document_id: str | None = None,
    tags: list[str] | None = None,
) -> tuple[str, list[dict]]:
    candidates = search(
        workbase_id,
        question,
        limit=settings.reranker_candidate_limit,
        retrieval_mode=retrieval_mode,
        document_id=document_id,
        tags=tags,
    )
    ranked = rerank(question, candidates, top_k=settings.reranker_top_k)
    return _context(ranked)


ANSWER_STYLE_PROMPTS = {
    "Simple": "Use short, clear language for beginners. Define jargon.",
    "Technical": "Give a more detailed, precise answer suitable for developers or technical readers.",
    "Study Notes": "Format as bullet-point study notes with definitions and examples.",
    "Article Draft": "Write a structured article-style answer with an introduction, sections, and conclusion.",
    "Book Chapter Draft": "Write a longer structured book-chapter draft with headings, explanations, examples, and citations.",
}


def answer_message(
    workbase_id: str,
    user_message: str,
    model: str | None = None,
    technical_mode: bool | None = None,
    retrieval_mode: str = "all",
    answer_style: str = "Simple",
    document_id: str | None = None,
    tags: list[str] | None = None,
) -> Generator[dict, None, None]:
    history = conversation_history(workbase_id)

    use_existing_sources_only = retrieval_mode == "curated_only" or bool(document_id)
    yield {
        "type": "status",
        "content": "Retrieving from existing sources..." if use_existing_sources_only else "Running LangGraph ingestion and retrieval workflow...",
    }
    routes = route_report(model)
    yield {
        "type": "status",
        "content": (
            f"Models: planner={routes['planner_model']} | final={routes['final_model']} | "
            f"embedding={routes['embedding_model']} | reranker={routes['reranker_model']}"
        ),
    }
    if use_existing_sources_only:
        context, sources = context_for_question(
            workbase_id,
            user_message,
            retrieval_mode=retrieval_mode,
            document_id=document_id,
            tags=tags,
        )
        state = {"context": context, "sources": sources, "results": [{"scrape_status": "skipped"}], "dataset_id": "existing-sources"}
    else:
        state = INGESTION_GRAPH.invoke(
            {
                "workbase_id": workbase_id,
                "user_message": user_message,
                "model": model,
                "history": history,
                "technical_mode": settings.technical_mode if technical_mode is None else technical_mode,
                "retrieval_mode": retrieval_mode,
                "document_id": document_id or "",
                "tags": tags or [],
            }
        )

    results = state.get("results", [])
    if not results:
        answer = "I could not get results from SearxNG. Check that your self-hosted SearxNG instance is running."
        add_message(workbase_id, "user", user_message)
        add_message(workbase_id, "assistant", answer, [])
        yield {"type": "token", "content": answer}
        yield {"type": "sources", "content": []}
        return

    query = state.get("query", "")
    dataset_id = state["dataset_id"]
    failed_scrapes = state.get("failed_scrapes", [])
    if failed_scrapes:
        yield {
            "type": "status",
            "content": f"{len(failed_scrapes)} pages could not be fully scraped; using available snippets for them.",
        }

    if not use_existing_sources_only:
        yield {
            "type": "status",
            "content": f"Stored {state.get('chunks_added', 0)} chunks in {dataset_id}; retrieving from selected sources.",
        }
    context = state.get("context", "")
    sources = state.get("sources", [])
    if not context:
        answer = "There is not enough source material in this Workbase to answer with citations."
        add_message(workbase_id, "user", user_message)
        add_message(workbase_id, "assistant", answer, [])
        yield {"type": "token", "content": answer}
        yield {"type": "sources", "content": []}
        return

    final_messages: list[dict[str, str]] = [{"role": "system", "content": ANSWER_SYSTEM_PROMPT}]
    final_messages.extend(history[-8:])
    final_messages.append(
        {
            "role": "user",
            "content": (
                "Use the retrieved workbase knowledge below to answer the question.\n\n"
                f"Answer style: {answer_style}. {ANSWER_STYLE_PROMPTS.get(answer_style, ANSWER_STYLE_PROMPTS['Simple'])}\n"
                "Use inline citations like [1]. Do not cite sources that are not listed in the retrieved knowledge.\n"
                f"Retrieved knowledge:\n{context}\n\n"
                f"Latest ingestion: {dataset_id}; failed full scrapes: {len(failed_scrapes)}.\n"
                f"Question: {user_message}"
            ),
        }
    )

    yield {"type": "status", "content": "Writing answer from reranked knowledge..."}
    full_answer = ""
    for token in stream_chat(final_messages, model=model, task="final"):
        full_answer += token
        yield {"type": "token", "content": token}
    answer_with_references = ensure_references(full_answer, sources)
    if answer_with_references != full_answer:
        extra = answer_with_references[len(full_answer) :]
        full_answer = answer_with_references
        yield {"type": "token", "content": extra}
    if settings.debug_costs:
        rough_input_tokens = max(1, len(context) // 4)
        rough_output_tokens = max(1, len(full_answer) // 4)
        yield {
            "type": "status",
            "content": (
                f"Cost log: planner={routes['planner_model']} | final={routes['final_model']} | "
                f"embedding={routes['embedding_model']} | input_tokens~{rough_input_tokens} | "
                f"output_tokens~{rough_output_tokens} | estimated_cost=configure price table"
            ),
        }

    add_message(workbase_id, "user", user_message)
    add_message(workbase_id, "assistant", full_answer, sources)
    yield {"type": "sources", "content": sources}
