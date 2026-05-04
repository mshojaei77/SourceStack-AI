import sys
import tempfile
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_assistant.config import settings
from research_assistant.manual_ingest import ingest_file, ingest_url
from research_assistant.rag_pipeline import answer_message
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


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"Sources ({len(sources)})", expanded=False):
        for index, source in enumerate(sources, start=1):
            score = source.get("score", 0.0)
            dataset = source.get("dataset_id") or "unknown dataset"
            trust = source.get("trust_level", "general_web")
            badge = {"curated": "Curated", "trusted_domain": "Trusted Domain"}.get(trust, "Web")
            st.markdown(
                f"""
                <div class="source-card">
                    <a href="{source.get('url', '#')}" target="_blank">[{index}] {source.get('title') or 'Untitled source'}</a><br/>
                    <small>[{badge}] {dataset} | Search: {source.get('search_query') or 'manual'} | Score: {score:.3f}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )


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
                    )
                    Path(temp_path).unlink(missing_ok=True)
                elif manual_url.strip():
                    result = ingest_url(
                        st.session_state.current_workbase,
                        manual_url.strip(),
                        title=source_title,
                        notes=source_notes,
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
