from typing import Any

from .citations import ensure_references
from .config import settings
from .llm import chat
from .rag_pipeline import context_for_question


STYLE_INSTRUCTIONS = {
    "Simple": "Use short, beginner-friendly language and define jargon.",
    "Technical": "Be precise and useful for developers or technical readers.",
    "Study Notes": "Use bullet-point notes with definitions and examples.",
    "Article Draft": "Write as a structured article with an introduction, sections, and conclusion.",
    "Book Chapter Draft": "Write as a longer book-chapter draft with headings, explanations, examples, and citations.",
}


def answer_style_instruction(answer_style: str) -> str:
    return STYLE_INSTRUCTIONS.get(answer_style, STYLE_INSTRUCTIONS["Simple"])


def _generate(
    workbase_id: str,
    prompt: str,
    retrieval_query: str,
    task: str,
    retrieval_mode: str = "all",
    document_id: str | None = None,
    tags: list[str] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    context, sources = context_for_question(
        workbase_id,
        retrieval_query,
        retrieval_mode=retrieval_mode,
        document_id=document_id,
        tags=tags,
    )
    if not context:
        return {
            "content": "There is not enough source material in this Workbase to generate this with citations.",
            "sources": [],
            "usage": {},
            "model": "",
        }

    messages = [
        {
            "role": "system",
            "content": (
                "You are SourceStack AI, a beginner-friendly research and writing assistant. "
                "Write only from the provided source context. Use inline numbered citations like [1]. "
                "Do not invent citations. If the source material is not enough, say what is missing."
            ),
        },
        {
            "role": "user",
            "content": f"{prompt}\n\nSource context:\n{context}",
        },
    ]
    response = chat(messages, model=model, task=task)
    content = ensure_references(response.get("content", ""), sources)
    return {
        "content": content,
        "sources": sources,
        "usage": response.get("usage", {}),
        "model": response.get("model", ""),
    }


def generate_article(
    workbase_id: str,
    topic: str,
    target_audience: str,
    tone: str,
    approximate_length: str,
    required_sources: str = "",
    retrieval_mode: str = "all",
    model: str | None = None,
) -> dict[str, Any]:
    prompt = (
        "Generate a cited article.\n"
        f"Topic: {topic}\n"
        f"Target audience: {target_audience}\n"
        f"Tone: {tone}\n"
        f"Approximate length: {approximate_length}\n"
        f"Required sources or constraints: {required_sources or 'None'}\n\n"
        "Output: title, introduction, main sections, conclusion, and references."
    )
    return _generate(workbase_id, prompt, topic, "deep_reasoning", retrieval_mode=retrieval_mode, model=model)


def generate_chapter(
    workbase_id: str,
    chapter_title: str,
    chapter_goal: str,
    target_reader_level: str,
    approximate_length: str,
    style_notes: str = "",
    required_sources: str = "",
    retrieval_mode: str = "curated_only",
    model: str | None = None,
) -> dict[str, Any]:
    prompt = (
        "Generate a cited book chapter.\n"
        f"Chapter title: {chapter_title}\n"
        f"Chapter goal: {chapter_goal}\n"
        f"Target reader level: {target_reader_level}\n"
        f"Approximate length: {approximate_length}\n"
        f"Writing style notes: {style_notes or 'None'}\n"
        f"Required sources or constraints: {required_sources or 'None'}\n\n"
        "Output: chapter title, chapter introduction, main sections, examples, key takeaways, and references. "
        "Every major section must include inline citations."
    )
    return _generate(
        workbase_id,
        prompt,
        f"{chapter_title} {chapter_goal}",
        "deep_reasoning",
        retrieval_mode=retrieval_mode,
        model=model,
    )


def build_outline(
    workbase_id: str,
    topic: str,
    work_type: str,
    retrieval_mode: str = "all",
    model: str | None = None,
) -> dict[str, Any]:
    prompt = (
        f"Create a practical outline for a {work_type} from this Workbase.\n"
        f"Topic: {topic}\n\n"
        "Output: title, section 1, section 2, section 3 or more if useful, and suggested sources for each section."
    )
    return _generate(workbase_id, prompt, topic, "final", retrieval_mode=retrieval_mode, model=model)


def build_glossary(
    workbase_id: str,
    topic: str,
    retrieval_mode: str = "all",
    model: str | None = None,
) -> dict[str, Any]:
    prompt = (
        f"Create a glossary for: {topic}\n\n"
        "Output a Markdown table with columns: Term, Simple definition, Technical definition, Source citation."
    )
    return _generate(workbase_id, prompt, topic, "final", retrieval_mode=retrieval_mode, model=model or settings.model_default)
