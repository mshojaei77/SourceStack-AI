import sys
import tempfile
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_assistant.config import settings
from research_assistant.citations import build_export_markdown, check_citations, source_badge
from research_assistant.exporting import markdown_to_pdf, pandoc_available
from research_assistant.manual_ingest import ingest_file, ingest_url
from research_assistant.rag_pipeline import answer_message
from research_assistant.vector_store import delete_source_document, source_documents, update_document_metadata
from research_assistant.writing import build_glossary, build_outline, generate_article, generate_chapter
from research_assistant.workbases import (
    create_workbase,
    delete_workbase,
    get_workbase,
    list_workbases,
)


st.set_page_config(
    page_title="Research Assistant",
    page_icon="RA",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container { max-width: 980px; padding-top: 1.5rem; }
    .source-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 0.7rem 0.85rem;
        margin: 0.35rem 0;
        background: #ffffff;
    }
    .source-card a { color: #2563eb; font-weight: 650; text-decoration: none; }
    .source-card small { color: #6b7280; }
    .status-text { color: #6b7280; font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def model_options() -> list[str]:
    options = settings.generation_model_options
    return options or [settings.generation_model]


def init_state() -> None:
    st.session_state.setdefault("current_workbase", None)
    st.session_state.setdefault("busy", False)
    st.session_state.setdefault("selected_model", model_options()[0])
    st.session_state.setdefault("technical_mode", settings.technical_mode)
    st.session_state.setdefault("retrieval_mode", "all")
    st.session_state.setdefault("answer_style", "Simple")
    st.session_state.setdefault("active_document_id", None)
    st.session_state.setdefault("active_source_title", "")
    st.session_state.setdefault("latest_generated", None)


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"Sources ({len(sources)})", expanded=False):
        for index, source in enumerate(sources, start=1):
            score = source.get("score", 0.0)
            dataset = source.get("dataset_id") or "unknown dataset"
            badge = source_badge(source)
            st.markdown(
                f"""
                <div class="source-card">
                    <a href="{source.get('url', '#')}" target="_blank">[{index}] {source.get('title') or 'Untitled source'}</a><br/>
                    <small>[{badge}] {dataset} | Search: {source.get('search_query') or 'manual'} | Score: {score:.3f}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )


def parse_tags(raw: str) -> list[str]:
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def latest_assistant_message(workbase: dict) -> dict | None:
    for message in reversed(workbase.get("messages", [])):
        if message.get("role") == "assistant":
            return message
    return None


init_state()

with st.sidebar:
    st.title("Research Assistant")
    st.caption("A growing RAG workspace for web research")

    st.selectbox("Model", model_options(), key="selected_model")
    st.toggle("Technical Mode", key="technical_mode")
    st.selectbox(
        "Retrieval Mode",
        ["all", "curated_trusted", "curated_only"],
        format_func=lambda value: {
            "all": "All Sources",
            "curated_trusted": "Curated + Trusted Domains",
            "curated_only": "Curated Only",
        }[value],
        key="retrieval_mode",
    )
    st.selectbox(
        "Answer Style",
        ["Simple", "Technical", "Study Notes", "Article Draft", "Book Chapter Draft"],
        key="answer_style",
    )
    if st.session_state.active_document_id:
        st.info(f"Asking only: {st.session_state.active_source_title or st.session_state.active_document_id}")
        if st.button("Clear source filter", use_container_width=True):
            st.session_state.active_document_id = None
            st.session_state.active_source_title = ""
            st.rerun()
    st.divider()

    with st.expander("Create workbase", expanded=False):
        name = st.text_input("Name", placeholder="Machine Learning Article")
        description = st.text_area("Description", placeholder="Research notes and sources for my article")
        if st.button("Create", use_container_width=True):
            result = create_workbase(name, description)
            if result.ok:
                st.session_state.current_workbase = result.workbase["id"]
                st.rerun()
            st.error(result.error)

    workbases = list_workbases()
    if workbases:
        labels = {wb["id"]: wb["name"] for wb in workbases}
        ids = list(labels.keys())
        current = st.session_state.current_workbase if st.session_state.current_workbase in ids else ids[0]
        selected = st.selectbox(
            "Workbase",
            ids,
            index=ids.index(current),
            format_func=lambda wb_id: labels.get(wb_id, wb_id),
        )
        st.session_state.current_workbase = selected

        meta = get_workbase(selected)
        if meta:
            st.caption(f"{meta.get('chunk_count', 0)} chunks")
            st.caption(f"{len(meta.get('datasets', []))} datasets")
            if meta.get("description"):
                st.caption(meta["description"])

        if st.button("Delete selected workbase", use_container_width=True):
            delete_workbase(selected)
            st.session_state.current_workbase = None
            st.rerun()
    else:
        st.info("Create a workbase to start.")

    st.divider()
    st.caption(f"SearxNG: {settings.searxng_url}")

    if st.session_state.current_workbase:
        st.divider()
        st.subheader("Manual Ingest")
        source_title = st.text_input("Source title", key="manual_source_title")
        source_notes = st.text_area("Notes", key="manual_source_notes", height=80)
        source_tags = st.text_input("Tags", key="manual_source_tags", placeholder="RAG, Chapter 1, Official Docs")
        with st.expander("Citation metadata", expanded=False):
            citation_author = st.text_input("Author", key="manual_citation_author")
            citation_year = st.text_input("Year", key="manual_citation_year")
            citation_key = st.text_input("Citation key", key="manual_citation_key")
        upload = st.file_uploader("PDF, Markdown, or text", type=["pdf", "md", "markdown", "txt"])
        manual_url = st.text_input("Direct URL", key="manual_url")

        if st.button("Ingest Source", use_container_width=True):
            try:
                if upload is not None:
                    suffix = Path(upload.name).suffix or ".txt"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
                        temp.write(upload.getbuffer())
                        temp_path = temp.name
                    result = ingest_file(
                        st.session_state.current_workbase,
                        temp_path,
                        title=source_title,
                        notes=source_notes,
                        source_name=upload.name,
                        tags=parse_tags(source_tags),
                        citation={
                            "author": citation_author,
                            "year": citation_year,
                            "citation_key": citation_key,
                        },
                    )
                    Path(temp_path).unlink(missing_ok=True)
                elif manual_url.strip():
                    result = ingest_url(
                        st.session_state.current_workbase,
                        manual_url.strip(),
                        title=source_title,
                        notes=source_notes,
                        tags=parse_tags(source_tags),
                        citation={
                            "author": citation_author,
                            "year": citation_year,
                            "citation_key": citation_key,
                        },
                    )
                else:
                    st.warning("Choose a file or enter a URL.")
                    result = None

                if result:
                    st.success(
                        f"Source added: {result['dataset_id']} | "
                        f"added {result['chunks_added']} | updated {result['chunks_updated']} | "
                        f"skipped {result['duplicates_skipped']} | parser {result['parser_name']}"
                    )
                    st.rerun()
            except Exception as exc:
                st.error(f"Ingestion failed: {exc}")


workbase_id = st.session_state.current_workbase

if not workbase_id:
    st.title("Research Assistant")
    st.write(
        "Create a workbase, ask a question, and every answer will search the web, store new evidence, "
        "then retrieve and rerank the whole accumulated knowledge base for that workbase."
    )
    st.stop()

workbase = get_workbase(workbase_id)
st.title(workbase["name"])

chat_tab, library_tab, writing_tab, export_tab = st.tabs(["Ask", "Source Library", "Writing Tools", "Export & Review"])

with chat_tab:
    if st.session_state.active_document_id:
        st.caption(f"Source filter active: {st.session_state.active_source_title}")

    for message in workbase.get("messages", []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                render_sources(message.get("sources", []))

    prompt = st.chat_input("Ask anything about this workbase...", disabled=st.session_state.busy)
    if prompt:
        st.session_state.busy = True
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            status = st.empty()
            output = st.empty()
            full_answer = ""
            final_sources: list[dict] = []

            try:
                for event in answer_message(
                    workbase_id,
                    prompt,
                    model=st.session_state.selected_model,
                    technical_mode=st.session_state.technical_mode,
                    retrieval_mode=st.session_state.retrieval_mode,
                    answer_style=st.session_state.answer_style,
                    document_id=st.session_state.active_document_id,
                ):
                    if event["type"] == "status":
                        status.markdown(f"<span class='status-text'>{event['content']}</span>", unsafe_allow_html=True)
                    elif event["type"] == "token":
                        full_answer += event["content"]
                        output.markdown(full_answer + "|")
                    elif event["type"] == "sources":
                        final_sources = event["content"]

                output.markdown(full_answer)
                status.empty()
                render_sources(final_sources)
            except Exception as exc:
                st.error(f"Error: {exc}")

        st.session_state.busy = False
        st.rerun()

with library_tab:
    sources = source_documents(workbase_id)
    if not sources:
        st.info("No sources yet. Add a PDF, Markdown, text file, URL, or ask a web-backed question.")
    else:
        rows = [
            {
                "Title": source.get("title", "Untitled"),
                "Source Type": (source.get("file_type") or "web").upper(),
                "Trust Level": source_badge(source),
                "Date Added": (source.get("date_added") or "")[:10],
                "Chunk Count": source.get("chunk_count", 0),
                "Dataset ID": ", ".join(source.get("dataset_ids", [])),
                "Tags": ", ".join(source.get("tags", [])),
            }
            for source in sources
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

        for index, source in enumerate(sources):
            title = source.get("title") or "Untitled source"
            with st.expander(f"{source_badge(source)} - {title}", expanded=False):
                st.write(
                    {
                        "document_id": source.get("document_id"),
                        "url": source.get("url"),
                        "file_name": source.get("file_name"),
                        "parser": source.get("parser_name"),
                        "chunk_count": source.get("chunk_count"),
                    }
                )
                col1, col2, col3 = st.columns(3)
                if col1.button("Ask only this source", key=f"ask_source_{index}", use_container_width=True):
                    st.session_state.active_document_id = source["document_id"]
                    st.session_state.active_source_title = title
                    st.rerun()
                if col2.button("Delete source", key=f"delete_source_{index}", use_container_width=True):
                    removed = delete_source_document(workbase_id, source["document_id"])
                    st.success(f"Deleted {removed} chunks.")
                    st.rerun()
                if col3.button("Re-ingest source", key=f"reingest_source_{index}", use_container_width=True):
                    try:
                        if source.get("stored_file_path") and Path(source["stored_file_path"]).exists():
                            result = ingest_file(
                                workbase_id,
                                source["stored_file_path"],
                                title=title,
                                source_name=source.get("file_name") or Path(source["stored_file_path"]).name,
                                tags=source.get("tags", []),
                                citation={
                                    "author": source.get("author", ""),
                                    "year": source.get("year", ""),
                                    "accessed_date": source.get("accessed_date", ""),
                                    "citation_key": source.get("citation_key", ""),
                                },
                            )
                            st.success(f"Re-ingested {result['dataset_id']}.")
                            st.rerun()
                        elif source.get("url"):
                            result = ingest_url(
                                workbase_id,
                                source["url"],
                                title=title,
                                tags=source.get("tags", []),
                                citation={
                                    "author": source.get("author", ""),
                                    "year": source.get("year", ""),
                                    "accessed_date": source.get("accessed_date", ""),
                                    "citation_key": source.get("citation_key", ""),
                                },
                            )
                            st.success(f"Re-ingested {result['dataset_id']}.")
                            st.rerun()
                        else:
                            st.warning("This source cannot be re-ingested because the original file or URL is unavailable.")
                    except Exception as exc:
                        st.error(f"Re-ingest failed: {exc}")

                with st.form(f"metadata_form_{index}"):
                    edited_title = st.text_input("Title", value=title, key=f"meta_title_{index}")
                    edited_author = st.text_input("Author", value=source.get("author", ""), key=f"meta_author_{index}")
                    edited_year = st.text_input("Year", value=source.get("year", ""), key=f"meta_year_{index}")
                    edited_url = st.text_input("URL", value=source.get("url", ""), key=f"meta_url_{index}")
                    edited_accessed = st.text_input(
                        "Accessed date",
                        value=source.get("accessed_date", ""),
                        key=f"meta_accessed_{index}",
                    )
                    edited_key = st.text_input("Citation key", value=source.get("citation_key", ""), key=f"meta_key_{index}")
                    edited_tags = st.text_input("Tags", value=", ".join(source.get("tags", [])), key=f"meta_tags_{index}")
                    if st.form_submit_button("Save metadata"):
                        update_document_metadata(
                            workbase_id,
                            source["document_id"],
                            {
                                "title": edited_title,
                                "author": edited_author,
                                "year": edited_year,
                                "url": edited_url,
                                "canonical_url": edited_url,
                                "accessed_date": edited_accessed,
                                "citation_key": edited_key,
                                "tags": parse_tags(edited_tags),
                            },
                        )
                        st.success("Metadata updated.")
                        st.rerun()

with writing_tab:
    tool = st.selectbox("Writing tool", ["Article Writer", "Book Chapter Writer", "Outline Builder", "Glossary Builder"])
    writing_retrieval_mode = st.selectbox(
        "Source scope",
        ["all", "curated_trusted", "curated_only"],
        format_func=lambda value: {
            "all": "All Sources",
            "curated_trusted": "Curated + Trusted Web",
            "curated_only": "Curated Only",
        }[value],
        key="writing_retrieval_mode",
    )

    if tool == "Article Writer":
        with st.form("article_writer"):
            topic = st.text_input("Topic")
            audience = st.text_input("Target audience", value="Beginners")
            tone = st.text_input("Tone", value="Clear and practical")
            length = st.text_input("Approximate length", value="800-1200 words")
            required = st.text_area("Required sources (optional)")
            submitted = st.form_submit_button("Generate article")
        if submitted:
            result = generate_article(workbase_id, topic, audience, tone, length, required, writing_retrieval_mode)
            st.session_state.latest_generated = {"title": topic or "Article Draft", **result}
            if settings.debug_costs:
                st.caption(f"Model: {result.get('model', '')} | Usage: {result.get('usage', {})}")
            st.markdown(result["content"])
            render_sources(result["sources"])

    elif tool == "Book Chapter Writer":
        with st.form("chapter_writer"):
            chapter_title = st.text_input("Chapter title")
            goal = st.text_area("Chapter goal")
            reader = st.text_input("Target reader level", value="Beginner")
            length = st.text_input("Approximate length", value="1500-2500 words")
            required = st.text_area("Required sources (optional)")
            notes = st.text_area("Writing style notes (optional)")
            submitted = st.form_submit_button("Generate chapter")
        if submitted:
            result = generate_chapter(workbase_id, chapter_title, goal, reader, length, notes, required, writing_retrieval_mode)
            st.session_state.latest_generated = {"title": chapter_title or "Book Chapter Draft", **result}
            if settings.debug_costs:
                st.caption(f"Model: {result.get('model', '')} | Usage: {result.get('usage', {})}")
            st.markdown(result["content"])
            render_sources(result["sources"])

    elif tool == "Outline Builder":
        with st.form("outline_builder"):
            topic = st.text_input("Topic")
            work_type = st.selectbox("Type", ["article", "book chapter"])
            submitted = st.form_submit_button("Build outline")
        if submitted:
            result = build_outline(workbase_id, topic, work_type, writing_retrieval_mode)
            st.session_state.latest_generated = {"title": topic or "Outline", **result}
            if settings.debug_costs:
                st.caption(f"Model: {result.get('model', '')} | Usage: {result.get('usage', {})}")
            st.markdown(result["content"])
            render_sources(result["sources"])

    else:
        with st.form("glossary_builder"):
            topic = st.text_input("Glossary topic")
            submitted = st.form_submit_button("Build glossary")
        if submitted:
            result = build_glossary(workbase_id, topic, writing_retrieval_mode)
            st.session_state.latest_generated = {"title": topic or "Glossary", **result}
            if settings.debug_costs:
                st.caption(f"Model: {result.get('model', '')} | Usage: {result.get('usage', {})}")
            st.markdown(result["content"])
            render_sources(result["sources"])

with export_tab:
    latest = st.session_state.latest_generated or latest_assistant_message(workbase)
    if not latest:
        st.info("Generate or ask something first, then export it here.")
    else:
        export_title = st.text_input("Export title", value=latest.get("title") or workbase["name"])
        export_content = latest.get("content", "")
        export_sources = latest.get("sources", [])
        export_markdown = build_export_markdown(export_title, export_content, export_sources, workbase["name"])
        st.download_button(
            "Download Markdown",
            data=export_markdown,
            file_name=f"{export_title or 'sourcestack-export'}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        if pandoc_available():
            pdf_bytes, pdf_error = markdown_to_pdf(export_markdown, export_title)
            if pdf_bytes:
                st.download_button(
                    "Download PDF",
                    data=pdf_bytes,
                    file_name=f"{export_title or 'sourcestack-export'}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.warning(pdf_error)
        else:
            st.warning("PDF export requires Pandoc to be installed. Markdown export is still available.")

        if st.button("Check Citations", use_container_width=True):
            for issue in check_citations(export_content, export_sources, st.session_state.retrieval_mode):
                st.write(f"- {issue}")

        with st.expander("Preview Markdown", expanded=False):
            st.markdown(export_markdown)
