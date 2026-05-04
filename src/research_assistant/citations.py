import re
from datetime import datetime, timezone
from typing import Any


SOURCE_BADGES = {
    "curated": "Curated",
    "trusted_domain": "Trusted Web",
    "general_web": "Web",
}


def source_badge(source: dict[str, Any]) -> str:
    return SOURCE_BADGES.get(source.get("trust_level", "general_web"), "Web")


def reference_line(index: int, source: dict[str, Any]) -> str:
    title = source.get("title") or "Untitled source"
    author = source.get("author") or ""
    year = source.get("year") or ""
    url = source.get("url") or source.get("canonical_url") or ""
    accessed = source.get("accessed_date") or ""
    details = ", ".join(part for part in [author, year] if part)
    suffix = f", {url}" if url else ""
    accessed_text = f" (accessed {accessed})" if accessed and url else ""
    return f"[{index}] {title}{', ' + details if details else ''}{suffix}{accessed_text}"


def cited_indexes(markdown: str) -> list[int]:
    found = {int(match) for match in re.findall(r"\[(\d+)\]", markdown or "")}
    return sorted(found)


def format_references(sources: list[dict[str, Any]], used_only: list[int] | None = None) -> str:
    if not sources:
        return ""
    indexes = used_only or list(range(1, len(sources) + 1))
    lines = []
    for index in indexes:
        if 1 <= index <= len(sources):
            lines.append(reference_line(index, sources[index - 1]))
    return "## References\n\n" + "\n".join(lines) if lines else ""


def ensure_references(markdown: str, sources: list[dict[str, Any]]) -> str:
    if not sources or re.search(r"^#{1,3}\s+References\b", markdown or "", flags=re.MULTILINE | re.IGNORECASE):
        return markdown
    used = cited_indexes(markdown)
    references = format_references(sources, used_only=used or None)
    return f"{markdown.rstrip()}\n\n{references}" if references else markdown


def build_export_markdown(
    title: str,
    content: str,
    sources: list[dict[str, Any]],
    workbase_name: str,
) -> str:
    export_date = datetime.now(timezone.utc).date().isoformat()
    body = ensure_references(content, sources)
    source_lines = [
        f"- [{source_badge(source)}] {source.get('title') or 'Untitled source'}"
        f"{' - ' + (source.get('url') or '') if source.get('url') else ''}"
        for source in sources
    ]
    source_list = "\n".join(source_lines) if source_lines else "- No sources attached"
    return (
        f"# {title.strip() or 'SourceStack AI Export'}\n\n"
        f"Workbase: {workbase_name}\n\n"
        f"Export date: {export_date}\n\n"
        f"{body.strip()}\n\n"
        f"## Source List\n\n{source_list}\n"
    )


def check_citations(markdown: str, sources: list[dict[str, Any]], retrieval_mode: str = "all") -> list[str]:
    issues: list[str] = []
    indexes = cited_indexes(markdown)
    for index in indexes:
        if index < 1 or index > len(sources):
            issues.append(f"Citation [{index}] does not point to an available source.")

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", markdown or "")
        if paragraph.strip() and not paragraph.lstrip().startswith("#") and "References" not in paragraph[:30]
    ]
    uncited = [paragraph for paragraph in paragraphs if not re.search(r"\[\d+\]", paragraph)]
    if uncited:
        issues.append(f"{len(uncited)} paragraph(s) have no inline citation.")

    missing_titles = [index + 1 for index, source in enumerate(sources) if not source.get("title")]
    if missing_titles:
        issues.append(f"Source(s) missing titles: {', '.join(f'[{item}]' for item in missing_titles)}.")

    if retrieval_mode == "curated_only":
        low_trust = [
            index + 1
            for index, source in enumerate(sources)
            if source.get("source_origin") != "manual_curation" and source.get("trust_level") != "curated"
        ]
        if low_trust:
            issues.append(f"Curated Only output includes non-curated source(s): {', '.join(f'[{item}]' for item in low_trust)}.")

    return issues or ["No basic citation hygiene issues found."]
