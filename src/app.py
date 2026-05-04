import sys
import tempfile
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_assistant.citations import build_export_markdown, check_citations, source_badge
from research_assistant.config import settings
from research_assistant.exporting import markdown_to_pdf, pandoc_available
from research_assistant.manual_ingest import ingest_file, ingest_url
from research_assistant.rag_pipeline import answer_message
from research_assistant.vector_store import delete_source_document, source_documents, update_document_metadata
from research_assistant.writing import build_glossary, generate_article, generate_chapter
from research_assistant.workbases import (
    add_report,
    create_workbase,
    delete_report,
    delete_workbase,
    get_workbase,
    list_workbases,
    update_report,
)


st.set_page_config(page_title="SourceStack AI", page_icon="SS", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --ss-bg: #f7f8fa;
        --ss-panel: #ffffff;
        --ss-line: #dfe3e8;
        --ss-line-soft: #edf0f3;
        --ss-text: #1f2933;
        --ss-muted: #697586;
        --ss-soft: #f2f5f8;
        --ss-accent: #2454a6;
        --ss-accent-soft: #eaf1ff;
        --ss-good: #20744a;
        --ss-warn: #9a5b00;
    }
    .stApp { background: var(--ss-bg); color: var(--ss-text); }
    header[data-testid="stHeader"], .stDeployButton, #MainMenu, footer { display: none; visibility: hidden; }
    .block-container { max-width: 100%; padding: 0.75rem 1.1rem 1.3rem; }
    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid var(--ss-line);
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        letter-spacing: 0;
    }
    .ss-topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        min-height: 52px;
        padding: 0.7rem 1rem;
        margin-bottom: 0.85rem;
        background: #ffffff;
        border: 1px solid var(--ss-line);
        border-radius: 8px;
    }
    .ss-brand {
        font-size: 1.02rem;
        font-weight: 740;
        color: var(--ss-text);
    }
    .ss-context {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        align-items: center;
        justify-content: flex-end;
        color: var(--ss-muted);
        font-size: 0.84rem;
    }
    .ss-chip {
        display: inline-flex;
        align-items: center;
        min-height: 27px;
        padding: 0.18rem 0.55rem;
        border: 1px solid var(--ss-line);
        border-radius: 999px;
        background: var(--ss-soft);
        color: #3b4754;
        font-size: 0.78rem;
        font-weight: 620;
        white-space: nowrap;
    }
    .ss-chip-blue {
        border-color: #cddbf5;
        background: var(--ss-accent-soft);
        color: var(--ss-accent);
    }
    .ss-card {
        background: #ffffff;
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        padding: 1rem;
    }
    .ss-chat-shell {
        min-height: calc(100vh - 130px);
        background: #ffffff;
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        padding: 1.1rem 1.1rem 0.75rem;
    }
    .ss-empty {
        max-width: 760px;
        margin: 8vh auto 2rem;
        text-align: center;
    }
    .ss-empty h1 {
        font-size: clamp(2rem, 4vw, 3.2rem);
        letter-spacing: 0;
        line-height: 1.05;
        margin: 0 0 0.8rem;
    }
    .ss-empty p {
        color: var(--ss-muted);
        font-size: 1.03rem;
        line-height: 1.6;
        margin-bottom: 1.2rem;
    }
    .ss-prompts {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.55rem;
        max-width: 640px;
        margin: 0 auto;
    }
    .ss-prompt {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        background: #fbfcfd;
        padding: 0.8rem 0.9rem;
        text-align: left;
        color: #334155;
        font-weight: 620;
        min-height: 54px;
    }
    .ss-message-meta, .ss-muted {
        color: var(--ss-muted);
        font-size: 0.82rem;
    }
    .ss-message {
        border: 1px solid var(--ss-line-soft);
        border-radius: 8px;
        padding: 0.85rem 0.95rem;
        margin: 0.65rem 0;
        background: #ffffff;
    }
    .ss-message-user {
        background: #f8fafc;
    }
    .ss-message-role {
        color: var(--ss-muted);
        font-size: 0.78rem;
        font-weight: 760;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }
    .ss-source-card {
        border: 1px solid var(--ss-line-soft);
        border-radius: 8px;
        padding: 0.75rem 0.85rem;
        margin: 0.45rem 0;
        background: #ffffff;
    }
    .ss-source-card a { color: var(--ss-accent); font-weight: 650; text-decoration: none; }
    .ss-source-card small { color: var(--ss-muted); }
    .ss-right-panel {
        background: #ffffff;
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        padding: 0.8rem;
        min-height: calc(100vh - 130px);
    }
    .ss-section-title {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 760;
        color: #4b5563;
        margin: 0.7rem 0 0.35rem;
    }
    .ss-kpi-row {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.55rem;
        margin: 0.8rem 0;
    }
    .ss-kpi {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        padding: 0.75rem;
        background: #fff;
    }
    .ss-kpi strong {
        display: block;
        font-size: 1.2rem;
        margin-bottom: 0.1rem;
    }
    .ss-table-note {
        color: var(--ss-muted);
        font-size: 0.86rem;
        margin: 0.4rem 0 0.7rem;
    }
    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button {
        border-radius: 7px;
        font-weight: 650;
    }
    input[type="radio"], input[type="checkbox"] { accent-color: var(--ss-accent); }
    div[data-testid="stToggle"] button { background-color: var(--ss-accent) !important; }
    div[data-testid="stChatInput"] {
        border-radius: 8px;
    }
    @media (max-width: 980px) {
        .ss-prompts { grid-template-columns: 1fr; }
        .ss-topbar { align-items: flex-start; flex-direction: column; }
        .ss-context { justify-content: flex-start; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


ANSWER_STYLES = ["Simple", "Technical", "Study Notes", "Article Draft", "Book Chapter Draft"]
RETRIEVAL_MODES = ["all", "curated_trusted", "curated_only"]
RETRIEVAL_LABELS = {
    "all": "All Sources",
    "curated_trusted": "Curated + Trusted Web",
    "curated_only": "Curated Only",
}
LENGTH_OPTIONS = ["Short", "Medium", "Long"]
TONE_OPTIONS = ["Clear", "Academic", "Friendly", "Professional"]
CITATION_STYLES = ["Numbered [1]", "Author-Year", "Markdown footnotes"]
MODEL_PRESETS = ["Cheapest", "Balanced", "Best Quality", "Custom"]


def model_options() -> list[str]:
    options = settings.generation_model_options
    return options or [settings.generation_model]


def init_state() -> None:
    defaults = {
        "current_workbase": None,
        "busy": False,
        "page": "Chat",
        "selected_model": model_options()[0],
        "planning_model": settings.model_planner,
        "answer_model": settings.model_final,
        "embedding_model_label": settings.embedding_model,
        "technical_mode": True,
        "budget_mode": True,
        "advanced_mode": False,
        "controls_open": True,
        "retrieval_mode": "curated_trusted",
        "answer_style": "Simple",
        "answer_length": "Medium",
        "answer_tone": "Clear",
        "include_examples": True,
        "include_takeaways": True,
        "include_definitions": True,
        "include_steps": False,
        "answer_sources_bottom": True,
        "citations_on": True,
        "citation_style": "Numbered [1]",
        "references_bottom": True,
        "include_urls": True,
        "include_accessed_date": True,
        "show_trust_badge": True,
        "citation_strictness": "Normal",
        "model_preset": "Balanced",
        "reranker_mode": "Local",
        "active_document_id": None,
        "active_source_title": "",
        "selected_tags": [],
        "latest_generated": None,
        "last_export_markdown": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def parse_tags(raw: str) -> list[str]:
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def latest_assistant_message(workbase: dict[str, Any]) -> dict[str, Any] | None:
    for message in reversed(workbase.get("messages", [])):
        if message.get("role") == "assistant":
            return message
    return None


def badge_class(source: dict[str, Any]) -> str:
    trust = source.get("trust_level", "general_web")
    if trust == "curated":
        return "ss-chip ss-chip-blue"
    if trust == "trusted_domain":
        return "ss-chip"
    return "ss-chip"


def render_topbar(workbase: dict[str, Any] | None) -> None:
    name = workbase.get("name", "No Workbase") if workbase else "No Workbase"
    mode = "Advanced Mode" if st.session_state.advanced_mode else "Beginner Mode"
    retrieval = RETRIEVAL_LABELS.get(st.session_state.retrieval_mode, "Curated + Trusted Web")
    st.markdown(
        f"""
        <div class="ss-topbar">
            <div class="ss-brand">SourceStack AI</div>
            <div class="ss-context">
                <span>Workbase: <strong>{name}</strong></span>
                <span class="ss-chip">{mode}</span>
                <span class="ss-chip ss-chip-blue">{retrieval}</span>
                <span class="ss-chip">{st.session_state.answer_style}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_source_cards(sources: list[dict[str, Any]], expanded: bool = False) -> None:
    if not sources:
        return
    with st.expander(f"Sources ({len(sources)})", expanded=expanded):
        for index, source in enumerate(sources, start=1):
            score = source.get("score_final", source.get("score", 0.0))
            dataset = source.get("dataset_id") or "manual"
            badge = source_badge(source)
            url = source.get("url") or "#"
            st.markdown(
                f"""
                <div class="ss-source-card">
                    <a href="{url}" target="_blank">[{index}] {source.get('title') or 'Untitled source'}</a><br/>
                    <small>[{badge}] {dataset} | Score: {float(score or 0):.3f}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_message(role: str, content: str, sources: list[dict[str, Any]] | None = None) -> None:
    label = "You" if role == "user" else "SourceStack AI"
    with st.container(border=True):
        st.markdown(f'<div class="ss-message-role">{label}</div>', unsafe_allow_html=True)
        st.markdown(content)
        render_source_cards(sources or [])


def ingest_source_form(workbase_id: str, form_key: str = "source_ingest") -> None:
    with st.form(form_key):
        upload = st.file_uploader("Upload PDF, Markdown, or text", type=["pdf", "md", "markdown", "txt"])
        manual_url = st.text_input("Or paste URL", placeholder="https://...")
        title = st.text_input("Title")
        tags = st.text_input("Tags", placeholder="RAG, Embeddings, Chapter 1")
        notes = st.text_area("Notes", height=80)
        submitted = st.form_submit_button("Add Source", use_container_width=True)
    if not submitted:
        return

    try:
        if upload is not None:
            suffix = Path(upload.name).suffix or ".txt"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
                temp.write(upload.getbuffer())
                temp_path = temp.name
            result = ingest_file(
                workbase_id,
                temp_path,
                title=title,
                notes=notes,
                source_name=upload.name,
                tags=parse_tags(tags),
            )
            Path(temp_path).unlink(missing_ok=True)
        elif manual_url.strip():
            result = ingest_url(workbase_id, manual_url.strip(), title=title, notes=notes, tags=parse_tags(tags))
        else:
            st.warning("Choose a file or paste a URL.")
            return
        st.success(
            f"Source added successfully. Chunks created: {result['chunks_added']}. "
            f"Duplicates skipped: {result['duplicates_skipped']}. Source type: Curated."
        )
        st.rerun()
    except Exception as exc:
        st.error(f"Source could not be added: {exc}")


def render_left_sidebar(workbases: list[dict[str, Any]]) -> None:
    with st.sidebar:
        st.title("SourceStack AI")
        st.caption("Research chat with sources")

        if st.button("+ New Chat", use_container_width=True):
            st.session_state.page = "Chat"
            st.session_state.active_document_id = None
            st.session_state.active_source_title = ""
            st.rerun()

        with st.expander("+ New Workbase", expanded=not bool(workbases)):
            name = st.text_input("Name", placeholder="LLM Book", key="new_workbase_name")
            description = st.text_area("Description", placeholder="Trusted sources and drafts", key="new_workbase_desc")
            if st.button("Create Workbase", use_container_width=True):
                result = create_workbase(name, description)
                if result.ok:
                    st.session_state.current_workbase = result.workbase["id"]
                    st.session_state.page = "Chat"
                    st.rerun()
                st.error(result.error)

        st.markdown("### Workbases")
        if workbases:
            labels = {workbase["id"]: workbase["name"] for workbase in workbases}
            ids = list(labels.keys())
            current = st.session_state.current_workbase if st.session_state.current_workbase in ids else ids[0]
            selected = st.radio(
                "Workbases",
                ids,
                index=ids.index(current),
                format_func=lambda workbase_id: labels.get(workbase_id, workbase_id),
                label_visibility="collapsed",
            )
            st.session_state.current_workbase = selected
        else:
            st.info("Create a Workbase to start.")

        st.markdown("### Recent Chats")
        current = get_workbase(st.session_state.current_workbase) if st.session_state.current_workbase else None
        recent = [
            message.get("content", "")
            for message in (current or {}).get("messages", [])
            if message.get("role") == "user"
        ][-5:]
        if recent:
            for index, text in enumerate(reversed(recent), start=1):
                st.caption(f"{index}. {text[:54]}")
        else:
            st.caption("No chats yet")

        st.markdown("### Library")
        st.radio(
            "Navigation",
            ["Chat", "Sources", "Reports", "Settings"],
            key="page",
            label_visibility="collapsed",
        )


def render_control_panel(workbase_id: str, workbase: dict[str, Any]) -> None:
    st.markdown("#### Controls")
    panel_tabs = st.tabs(["Sources", "Answer", "Citations", "Models", "Export"])
    sources = source_documents(workbase_id)

    with panel_tabs[0]:
        st.markdown('<div class="ss-section-title">Source Mode</div>', unsafe_allow_html=True)
        st.radio(
            "Source Mode",
            RETRIEVAL_MODES,
            format_func=lambda value: RETRIEVAL_LABELS[value],
            key="retrieval_mode",
            label_visibility="collapsed",
        )
        st.toggle("Technical Mode", key="technical_mode")
        st.markdown('<div class="ss-section-title">Ask Scope</div>', unsafe_allow_html=True)
        scope = st.radio(
            "Ask Scope",
            ["Entire Workbase", "One Source Only", "Tags"],
            label_visibility="collapsed",
        )
        if scope == "One Source Only":
            if sources:
                options = {source["document_id"]: source.get("title") or source["document_id"] for source in sources}
                selected = st.selectbox("One Source", list(options.keys()), format_func=lambda value: options[value])
                st.session_state.active_document_id = selected
                st.session_state.active_source_title = options[selected]
            else:
                st.info("No sources yet.")
        elif scope == "Tags":
            all_tags = sorted({tag for source in sources for tag in source.get("tags", [])})
            st.session_state.selected_tags = st.multiselect("Selected Tags", all_tags, default=st.session_state.selected_tags)
            st.session_state.active_document_id = None
            st.session_state.active_source_title = ""
        else:
            st.session_state.active_document_id = None
            st.session_state.active_source_title = ""
        st.markdown(
            '<span class="ss-chip ss-chip-blue">Curated</span> '
            '<span class="ss-chip">Trusted Web</span> '
            '<span class="ss-chip">Web</span>',
            unsafe_allow_html=True,
        )

    with panel_tabs[1]:
        st.markdown('<div class="ss-section-title">Answer Style</div>', unsafe_allow_html=True)
        st.radio("Answer Style", ANSWER_STYLES, key="answer_style", label_visibility="collapsed")
        st.radio("Length", LENGTH_OPTIONS, key="answer_length", horizontal=True)
        st.radio("Tone", TONE_OPTIONS, key="answer_tone", horizontal=True)
        st.markdown('<div class="ss-section-title">Include</div>', unsafe_allow_html=True)
        st.checkbox("Examples", key="include_examples")
        st.checkbox("Key takeaways", key="include_takeaways")
        st.checkbox("Definitions", key="include_definitions")
        st.checkbox("Step-by-step explanation", key="include_steps")
        st.checkbox("Sources at bottom", key="answer_sources_bottom")

    with panel_tabs[2]:
        st.toggle("Citations", key="citations_on")
        st.radio("Citation Style", CITATION_STYLES, key="citation_style")
        st.markdown('<div class="ss-section-title">Reference List</div>', unsafe_allow_html=True)
        st.checkbox("Show references at bottom", key="references_bottom")
        st.checkbox("Include URLs", key="include_urls")
        st.checkbox("Include accessed date", key="include_accessed_date")
        st.checkbox("Show trust badge", key="show_trust_badge")
        st.radio("Citation Strictness", ["Normal", "Strict"], key="citation_strictness")
        latest = st.session_state.latest_generated or latest_assistant_message(workbase)
        if st.button("Check Citations", use_container_width=True):
            if latest:
                for issue in check_citations(latest.get("content", ""), latest.get("sources", []), st.session_state.retrieval_mode):
                    st.write(f"- {issue}")
            else:
                st.info("Ask or generate something first.")

    with panel_tabs[3]:
        st.toggle("Budget Mode", key="budget_mode")
        st.radio("Model Preset", MODEL_PRESETS, key="model_preset")
        st.caption("Cheapest lowers cost. Balanced is recommended. Best Quality improves long writing.")
        if st.session_state.advanced_mode or st.session_state.model_preset == "Custom":
            st.selectbox("Planning Model", model_options(), key="planning_model")
            st.selectbox("Answer Model", model_options(), key="selected_model")
            st.text_input("Embedding Model", key="embedding_model_label")
            st.radio("Reranker", ["Local", "API", "Off"], key="reranker_mode", horizontal=True)
        else:
            st.info("Open Advanced Mode in Settings to edit model IDs.")

    with panel_tabs[4]:
        latest = st.session_state.latest_generated or latest_assistant_message(workbase)
        st.radio("Export as", ["Research Summary", "Technical Article", "Book Chapter"], key="export_template")
        include_title = st.checkbox("Title", value=True)
        st.checkbox("Table of contents", value=False)
        st.checkbox("Inline citations", value=True)
        st.checkbox("References", value=True)
        st.checkbox("Source list", value=True)
        st.checkbox("Workbase metadata", value=True)
        if latest:
            export_title = latest.get("title") or workbase.get("name", "SourceStack Export")
            if not include_title:
                export_title = "SourceStack Export"
            markdown = build_export_markdown(export_title, latest.get("content", ""), latest.get("sources", []), workbase["name"])
            st.session_state.last_export_markdown = markdown
            st.download_button("Export Markdown", markdown, file_name=f"{export_title}.md", mime="text/markdown", use_container_width=True)
            if pandoc_available():
                pdf_bytes, pdf_error = markdown_to_pdf(markdown, export_title)
                if pdf_bytes:
                    st.download_button("Export PDF", pdf_bytes, file_name=f"{export_title}.pdf", mime="application/pdf", use_container_width=True)
                else:
                    st.warning(pdf_error)
            else:
                st.warning("PDF export requires Pandoc. Markdown export is available.")
        else:
            st.info("Ask or generate something first.")


def render_chat_page(workbase_id: str, workbase: dict[str, Any]) -> None:
    main_col, right_col = st.columns([0.69, 0.31], gap="large")
    with main_col:
        messages = workbase.get("messages", [])
        if not messages:
            st.markdown(
                """
                <div class="ss-empty">
                    <h1>SourceStack AI</h1>
                    <p>Ask questions, write articles, or generate cited chapters from your trusted sources.</p>
                    <div class="ss-prompts">
                        <div class="ss-prompt">Ask a question</div>
                        <div class="ss-prompt">Write an article</div>
                        <div class="ss-prompt">Draft a book chapter</div>
                        <div class="ss-prompt">Summarize my sources</div>
                        <div class="ss-prompt">Build a glossary</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            for message in messages:
                render_message(message["role"], message["content"], message.get("sources", []))

        chip_text = (
            f"<span class='ss-chip ss-chip-blue'>{st.session_state.answer_style}</span> "
            f"<span class='ss-chip'>{RETRIEVAL_LABELS[st.session_state.retrieval_mode]}</span> "
            f"<span class='ss-chip'>Numbered Citations</span> "
            f"<span class='ss-chip'>{'Budget Mode' if st.session_state.budget_mode else 'Standard Cost'}</span>"
        )
        if st.session_state.active_source_title:
            chip_text += f" <span class='ss-chip ss-chip-blue'>Only: {st.session_state.active_source_title}</span>"
        st.markdown(chip_text, unsafe_allow_html=True)

        prompt = st.chat_input("Ask SourceStack AI...", disabled=st.session_state.busy)
        if prompt:
            st.session_state.busy = True
            status = st.empty()
            output = st.empty()
            full_answer = ""
            final_sources: list[dict[str, Any]] = []
            try:
                for event in answer_message(
                    workbase_id,
                    prompt,
                    model=st.session_state.selected_model,
                    technical_mode=st.session_state.technical_mode,
                    retrieval_mode=st.session_state.retrieval_mode,
                    answer_style=st.session_state.answer_style,
                    document_id=st.session_state.active_document_id,
                    tags=st.session_state.selected_tags,
                ):
                    if event["type"] == "status" and st.session_state.advanced_mode:
                        status.markdown(f"<span class='ss-muted'>{event['content']}</span>", unsafe_allow_html=True)
                    elif event["type"] == "token":
                        full_answer += event["content"]
                        output.markdown(full_answer + "|")
                    elif event["type"] == "sources":
                        final_sources = event["content"]
                output.markdown(full_answer)
                status.empty()
                render_source_cards(final_sources)
            except Exception as exc:
                st.error(f"SourceStack could not answer: {exc}")
            st.session_state.busy = False
            st.rerun()

    with right_col:
        render_control_panel(workbase_id, workbase)


def source_rows(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Badge": source_badge(source),
            "Title": source.get("title", "Untitled"),
            "Type": (source.get("file_type") or "web").upper(),
            "Tags": ", ".join(source.get("tags", [])),
            "Date Added": (source.get("date_added") or "")[:10],
            "Chunks": source.get("chunk_count", 0),
        }
        for source in sources
    ]


def render_sources_page(workbase_id: str) -> None:
    st.markdown("## Sources")
    top_left, top_mid, top_right = st.columns([0.2, 0.22, 0.58])
    show_add = top_left.toggle("+ Add Source", value=False)
    trust_filter = top_mid.selectbox("Filter", ["All", "Curated", "Trusted Web", "Web"], label_visibility="collapsed")
    search_text = top_right.text_input("Search Sources", placeholder="Search sources", label_visibility="collapsed")

    if show_add:
        ingest_source_form(workbase_id, "sources_page_ingest")

    sources = source_documents(workbase_id)
    if trust_filter != "All":
        trust_lookup = {"Curated": "curated", "Trusted Web": "trusted_domain", "Web": "general_web"}
        sources = [source for source in sources if source.get("trust_level") == trust_lookup[trust_filter]]
    if search_text.strip():
        needle = search_text.lower()
        sources = [
            source
            for source in sources
            if needle in (source.get("title") or "").lower()
            or needle in (source.get("url") or "").lower()
            or any(needle in tag.lower() for tag in source.get("tags", []))
        ]

    st.dataframe(source_rows(sources), use_container_width=True, hide_index=True)
    st.markdown('<div class="ss-table-note">Use Ask to focus the next chat turn on one source.</div>', unsafe_allow_html=True)
    for index, source in enumerate(sources):
        title = source.get("title") or "Untitled source"
        with st.expander(f"{source_badge(source)} | {title}", expanded=False):
            st.write(
                {
                    "URL": source.get("url"),
                    "Type": source.get("file_type"),
                    "Datasets": source.get("dataset_ids"),
                    "Chunks": source.get("chunk_count"),
                    "Document": source.get("document_id"),
                }
            )
            c1, c2, c3 = st.columns(3)
            if c1.button("Ask", key=f"source_ask_{index}", use_container_width=True):
                st.session_state.active_document_id = source["document_id"]
                st.session_state.active_source_title = title
                st.session_state.page = "Chat"
                st.rerun()
            if c2.button("Delete", key=f"source_delete_{index}", use_container_width=True):
                removed = delete_source_document(workbase_id, source["document_id"])
                st.success(f"Deleted {removed} source chunks.")
                st.rerun()
            if c3.button("Re-ingest", key=f"source_reingest_{index}", use_container_width=True):
                try:
                    if source.get("stored_file_path") and Path(source["stored_file_path"]).exists():
                        result = ingest_file(
                            workbase_id,
                            source["stored_file_path"],
                            title=title,
                            source_name=source.get("file_name") or Path(source["stored_file_path"]).name,
                            tags=source.get("tags", []),
                        )
                    elif source.get("url"):
                        result = ingest_url(workbase_id, source["url"], title=title, tags=source.get("tags", []))
                    else:
                        st.warning("No stored file or URL is available.")
                        result = None
                    if result:
                        st.success(f"Re-ingested. Chunks created: {result['chunks_added']}; duplicates skipped: {result['duplicates_skipped']}.")
                        st.rerun()
                except Exception as exc:
                    st.error(f"Re-ingest failed: {exc}")

            with st.form(f"source_edit_{index}"):
                edited_title = st.text_input("Title", value=title, key=f"source_title_{index}")
                edited_tags = st.text_input("Tags", value=", ".join(source.get("tags", [])), key=f"source_tags_{index}")
                edited_author = st.text_input("Author", value=source.get("author", ""), key=f"source_author_{index}")
                edited_year = st.text_input("Year", value=source.get("year", ""), key=f"source_year_{index}")
                edited_url = st.text_input("URL", value=source.get("url", ""), key=f"source_url_{index}")
                if st.form_submit_button("Save Metadata"):
                    update_document_metadata(
                        workbase_id,
                        source["document_id"],
                        {
                            "title": edited_title,
                            "tags": parse_tags(edited_tags),
                            "author": edited_author,
                            "year": edited_year,
                            "url": edited_url,
                            "canonical_url": edited_url,
                        },
                    )
                    st.success("Source metadata updated.")
                    st.rerun()


def render_reports_page(workbase_id: str, workbase: dict[str, Any]) -> None:
    st.markdown("## Reports")
    with st.expander("+ New Report", expanded=False):
        tool = st.selectbox("Type", ["Article", "Book Chapter", "Glossary"])
        topic = st.text_input("Title or topic")
        goal = st.text_area("Goal", height=80)
        if st.button("Generate Report", use_container_width=True):
            if tool == "Article":
                result = generate_article(workbase_id, topic, "Students", "Clear and professional", "Medium", goal, st.session_state.retrieval_mode)
            elif tool == "Book Chapter":
                result = generate_chapter(workbase_id, topic, goal, "Beginner", "Medium", retrieval_mode=st.session_state.retrieval_mode)
            else:
                result = build_glossary(workbase_id, topic, st.session_state.retrieval_mode)
            report = add_report(workbase_id, topic or tool, tool, result["content"], result.get("sources", []))
            st.session_state.latest_generated = {"title": report["title"], **result} if report else result
            st.success("Report created.")
            st.rerun()

    reports = workbase.get("reports", [])
    if not reports:
        st.info("Generated articles, chapters, and summaries will appear here.")
        return
    rows = [
        {
            "Title": report.get("title"),
            "Type": report.get("type"),
            "Workbase": workbase.get("name"),
            "Date": (report.get("created_at") or "")[:10],
        }
        for report in reports
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    for index, report in enumerate(reports):
        with st.expander(f"{report.get('type')} | {report.get('title')}", expanded=False):
            edited = st.text_area("Content", value=report.get("content", ""), height=340, key=f"report_content_{index}")
            c1, c2, c3 = st.columns(3)
            if c1.button("Save", key=f"report_save_{index}", use_container_width=True):
                update_report(workbase_id, report["id"], {"content": edited})
                st.success("Report saved.")
                st.rerun()
            markdown = build_export_markdown(report.get("title", "Report"), edited, report.get("sources", []), workbase["name"])
            c2.download_button("Export Markdown", markdown, file_name=f"{report.get('title', 'report')}.md", mime="text/markdown", use_container_width=True)
            if c3.button("Delete", key=f"report_delete_{index}", use_container_width=True):
                delete_report(workbase_id, report["id"])
                st.success("Report deleted.")
                st.rerun()
            render_source_cards(report.get("sources", []), expanded=False)


def render_settings_page(workbase_id: str, workbase: dict[str, Any]) -> None:
    st.markdown("## Settings")
    general, sources, models, export, advanced = st.tabs(["General", "Sources", "Models and Cost", "Export", "Advanced"])
    with general:
        st.selectbox("Default Workbase", [workbase_id], format_func=lambda _: workbase.get("name", workbase_id))
        st.selectbox("Default Answer Style", ANSWER_STYLES, key="answer_style")
        st.selectbox("Default Citation Style", CITATION_STYLES, key="citation_style")
        st.toggle("Advanced Mode", key="advanced_mode")
    with sources:
        st.radio("Default Retrieval Mode", RETRIEVAL_MODES, format_func=lambda value: RETRIEVAL_LABELS[value], key="retrieval_mode")
        st.toggle("Technical Mode", key="technical_mode")
        st.text_area("Trusted Domain List", value="\n".join(settings.technical_domain_whitelist), height=180)
        st.info("Duplicate handling is automatic: repeated uploads and URLs skip existing chunks.")
    with models:
        st.radio("Model Preset", MODEL_PRESETS, key="model_preset")
        st.toggle("Budget Mode", key="budget_mode")
        st.selectbox("Planning Model", model_options(), key="planning_model")
        st.selectbox("Answer Model", model_options(), key="selected_model")
        st.text_input("Embedding Model", key="embedding_model_label")
        st.radio("Reranker", ["Local", "API", "Off"], key="reranker_mode", horizontal=True)
    with export:
        st.radio("Default Export Format", ["Markdown", "PDF"], horizontal=True)
        st.write("PDF Export Method: Markdown to Pandoc to PDF")
        st.checkbox("Include References", value=True)
        st.checkbox("Include Source List", value=True)
    with advanced:
        st.number_input("Chunk Size", min_value=200, value=settings.chunk_size)
        st.number_input("Retrieval Candidate Count", min_value=1, value=settings.reranker_candidate_limit)
        st.number_input("Final Context Count", min_value=1, value=settings.reranker_top_k)
        st.toggle("Debug Logs", value=settings.debug_costs)
        if st.button("Delete selected Workbase", type="secondary"):
            delete_workbase(workbase_id)
            st.session_state.current_workbase = None
            st.rerun()


init_state()
workbases = list_workbases()
render_left_sidebar(workbases)

workbase_id = st.session_state.current_workbase
workbase = get_workbase(workbase_id) if workbase_id else None

render_topbar(workbase)

if not workbase_id or not workbase:
    st.markdown(
        """
        <div class="ss-card">
            <h2>Welcome to SourceStack AI</h2>
            <p class="ss-muted">Create a Workbase from the left sidebar to add sources, ask questions, and write with citations.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

sources_count = len(source_documents(workbase_id))
st.markdown(
    f"""
    <div class="ss-kpi-row">
        <div class="ss-kpi"><strong>{sources_count}</strong><span class="ss-muted">Sources</span></div>
        <div class="ss-kpi"><strong>{workbase.get('chunk_count', 0)}</strong><span class="ss-muted">Source passages</span></div>
        <div class="ss-kpi"><strong>{len(workbase.get('reports', []))}</strong><span class="ss-muted">Reports</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.session_state.page == "Chat":
    render_chat_page(workbase_id, workbase)
elif st.session_state.page == "Sources":
    render_sources_page(workbase_id)
elif st.session_state.page == "Reports":
    render_reports_page(workbase_id, workbase)
else:
    render_settings_page(workbase_id, workbase)
