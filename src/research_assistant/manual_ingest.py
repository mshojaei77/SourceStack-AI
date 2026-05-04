import hashlib
import mimetypes
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from .config import settings
from .llm import embedding_model
from .search import USER_AGENT, canonicalize_url
from .text import chunk_text
from .vector_store import count, delete_document_points, document_payloads, update_document_metadata, upsert_chunks
from .workbases import next_dataset_id, now_iso, record_dataset, workbase_dir


TRACKED_HEADER_LEVELS = ("section_h1", "section_h2", "section_h3")


@dataclass
class ParsedSource:
    title: str
    text: str
    parser_name: str
    parser_version: str
    file_type: str
    canonical_url: str = ""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def document_id_for(workbase_id: str, stable_source_key: str) -> str:
    return sha256_text(f"{workbase_id}\n{stable_source_key}")


def point_id_for(document_id: str, chunk_index: int, content_hash: str) -> str:
    return sha256_text(f"{document_id}\n{chunk_index}\n{content_hash}")


def _package_version(package_name: str) -> str:
    try:
        from importlib.metadata import version

        return version(package_name)
    except Exception:
        return ""


def _read_text_file(path: Path) -> ParsedSource:
    text = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    parser = "markdown" if suffix in {".md", ".markdown"} else "text"
    return ParsedSource(
        title=path.stem,
        text=text,
        parser_name=parser,
        parser_version="stdlib",
        file_type=suffix.lstrip(".") or "txt",
    )


def _read_pdf(path: Path) -> ParsedSource:
    try:
        from marker.converters.pdf import PdfConverter

        converter = PdfConverter()
        rendered = converter(str(path))
        text = getattr(rendered, "markdown", None) or str(rendered)
        return ParsedSource(
            title=path.stem,
            text=text,
            parser_name="marker",
            parser_version=_package_version("marker-pdf"),
            file_type="pdf",
        )
    except Exception:
        pass

    import fitz

    parts = []
    with fitz.open(path) as document:
        for page_index, page in enumerate(document, start=1):
            parts.append(f"\n\n## Page {page_index}\n\n{page.get_text('text')}")
    return ParsedSource(
        title=path.stem,
        text="\n".join(parts).strip(),
        parser_name="pymupdf",
        parser_version=_package_version("PyMuPDF"),
        file_type="pdf",
    )


def parse_file(path: str | Path) -> tuple[ParsedSource, bytes]:
    source_path = Path(path)
    raw = source_path.read_bytes()
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(source_path), raw
    if suffix in {".md", ".markdown", ".txt", ".text"}:
        return _read_text_file(source_path), raw
    guessed_type = mimetypes.guess_type(source_path.name)[0] or ""
    if guessed_type.startswith("text/"):
        return _read_text_file(source_path), raw
    raise ValueError(f"Unsupported file type: {source_path.suffix or source_path.name}")


def _html_to_markdown(html: str, url: str) -> tuple[str, str, str]:
    try:
        import trafilatura

        extracted = trafilatura.extract(
            html,
            url=url,
            output_format="markdown",
            include_links=True,
            include_tables=True,
            include_comments=False,
        )
        if extracted:
            return extracted, "trafilatura", _package_version("trafilatura")
    except Exception:
        pass

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"]):
        tag.decompose()
    for code in soup.find_all("code"):
        if code.parent and code.parent.name == "pre":
            continue
        code.string = f"`{code.get_text()}`"
    for pre in soup.find_all("pre"):
        pre.string = f"\n```\n{pre.get_text()}\n```\n"
    node = soup.find("main") or soup.find("article") or soup.body or soup
    return node.get_text("\n", strip=True), "beautifulsoup", _package_version("beautifulsoup4")


def parse_url(url: str, title: str = "") -> ParsedSource:
    canonical = canonicalize_url(url)
    response = requests.get(canonical, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    text, parser_name, parser_version = _html_to_markdown(response.text, canonical)
    inferred_title = title.strip()
    if not inferred_title:
        soup = BeautifulSoup(response.text, "html.parser")
        inferred_title = soup.title.get_text(strip=True) if soup.title else canonical
    return ParsedSource(
        title=inferred_title,
        text=text,
        parser_name=parser_name,
        parser_version=parser_version,
        file_type="url",
        canonical_url=canonical,
    )


def _split_markdown_with_headers(text: str, chunk_size: int, overlap: int) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    headers = {"section_h1": "", "section_h2": "", "section_h3": ""}
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        prefix_lines = [value for key, value in headers.items() if value]
        prefix = "\n".join(prefix_lines)
        body = "\n".join(buffer).strip()
        source = f"{prefix}\n\n{body}".strip() if prefix and not body.startswith(prefix_lines[-1]) else body
        for text_chunk in chunk_text(source, chunk_size=chunk_size, overlap=overlap, preserve_structure=True):
            chunk = {"text": text_chunk}
            chunk.update(headers)
            chunks.append(chunk)
        buffer.clear()

    in_code = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
        if not in_code and stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            heading_text = stripped[level:].strip()
            if 1 <= level <= 3:
                flush()
                headers[f"section_h{level}"] = heading_text
                if level == 1:
                    headers["section_h2"] = ""
                    headers["section_h3"] = ""
                elif level == 2:
                    headers["section_h3"] = ""
        buffer.append(line)
        if sum(len(item) + 1 for item in buffer) >= chunk_size:
            flush()
    flush()
    return chunks


def _build_chunks(
    workbase_id: str,
    dataset_id: str,
    parsed: ParsedSource,
    document_id: str,
    source_fingerprint: str,
    source_key: str,
    ingestion_method: str,
    file_name: str = "",
    stored_file_path: str = "",
    notes: str = "",
    tags: list[str] | None = None,
    citation: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    created_at = now_iso()
    text_chunks = _split_markdown_with_headers(parsed.text, settings.chunk_size, settings.chunk_overlap)
    chunks = []
    citation = citation or {}
    for index, chunk in enumerate(text_chunks):
        chunk_hash = sha256_text(chunk["text"])
        chunks.append(
            {
                "id": point_id_for(document_id, index, chunk_hash),
                "text": chunk["text"],
                "dataset_id": dataset_id,
                "source_id": sha256_text(source_key)[:16],
                "title": parsed.title,
                "url": parsed.canonical_url,
                "canonical_url": parsed.canonical_url,
                "source_position": 0,
                "chunk_index": index,
                "created_at": created_at,
                "ingested_at": created_at,
                "source_origin": "manual_curation",
                "trust_level": "curated",
                "is_verified": True,
                "ingestion_method": ingestion_method,
                "parser_name": parsed.parser_name,
                "parser_version": parsed.parser_version,
                "document_id": document_id,
                "source_fingerprint": source_fingerprint,
                "content_hash": chunk_hash,
                "file_name": file_name,
                "stored_file_path": stored_file_path,
                "file_type": parsed.file_type,
                "embedding_model": embedding_model(),
                "section_h1": chunk.get("section_h1", ""),
                "section_h2": chunk.get("section_h2", ""),
                "section_h3": chunk.get("section_h3", ""),
                "notes": notes,
                "tags": tags or [],
                "author": citation.get("author", ""),
                "year": citation.get("year", ""),
                "accessed_date": citation.get("accessed_date", created_at[:10]),
                "citation_key": citation.get("citation_key", ""),
            }
        )
    return chunks


def _ingest_parsed(
    workbase_id: str,
    parsed: ParsedSource,
    source_fingerprint: str,
    stable_source_key: str,
    ingestion_method: str,
    file_name: str = "",
    stored_file_path: str = "",
    notes: str = "",
    tags: list[str] | None = None,
    citation: dict[str, str] | None = None,
) -> dict[str, Any]:
    dataset_id = next_dataset_id(workbase_id)
    document_id = document_id_for(workbase_id, stable_source_key)
    existing = document_payloads(workbase_id, document_id)
    existing_fingerprints = {payload.get("source_fingerprint") for payload in existing}
    if existing and existing_fingerprints == {source_fingerprint}:
        duplicates = len(existing)
        stats = {"chunks_added": 0, "chunks_updated": 0, "duplicates_skipped": duplicates}
        update_document_metadata(
            workbase_id,
            document_id,
            {
                "title": parsed.title,
                "url": parsed.canonical_url,
                "canonical_url": parsed.canonical_url,
                "source_origin": "manual_curation",
                "trust_level": "curated",
                "is_verified": True,
                "ingestion_method": ingestion_method,
                "parser_name": parsed.parser_name,
                "parser_version": parsed.parser_version,
                "file_name": file_name,
                "file_type": parsed.file_type,
                "stored_file_path": stored_file_path,
                "notes": notes,
                "tags": tags or [],
                "author": (citation or {}).get("author", ""),
                "year": (citation or {}).get("year", ""),
                "accessed_date": (citation or {}).get("accessed_date", now_iso()[:10]),
                "citation_key": (citation or {}).get("citation_key", ""),
            },
        )
    else:
        if existing:
            delete_document_points(workbase_id, document_id)
        chunks = _build_chunks(
            workbase_id,
            dataset_id,
            parsed,
            document_id,
            source_fingerprint,
            stable_source_key,
            ingestion_method,
            file_name=file_name,
            stored_file_path=stored_file_path,
            notes=notes,
            tags=tags,
            citation=citation,
        )
        stats = upsert_chunks(workbase_id, chunks)
        if existing and stats["chunks_added"]:
            stats["chunks_updated"] = stats["chunks_added"]
            stats["chunks_added"] = 0

    total = count(workbase_id)
    source_record = {
        "source_id": sha256_text(stable_source_key)[:16],
        "document_id": document_id,
        "title": parsed.title,
        "url": parsed.canonical_url,
        "canonical_url": parsed.canonical_url,
        "source_origin": "manual_curation",
        "trust_level": "curated",
        "is_verified": True,
        "scrape_status": "success",
        "scrape_error": "",
        "parser_name": parsed.parser_name,
        "content_source": ingestion_method,
        "file_type": parsed.file_type,
        "file_name": file_name,
        "stored_file_path": stored_file_path,
        "tags": tags or [],
        "author": (citation or {}).get("author", ""),
        "year": (citation or {}).get("year", ""),
        "accessed_date": (citation or {}).get("accessed_date", now_iso()[:10]),
        "citation_key": (citation or {}).get("citation_key", ""),
    }
    record_dataset(
        workbase_id,
        dataset_id,
        query=None,
        results=[source_record],
        chunks_added=stats["chunks_added"],
        chunks_updated=stats["chunks_updated"],
        duplicates_skipped=stats["duplicates_skipped"],
        total_chunks=total,
        dataset_type="manual_ingestion",
    )
    return {
        "dataset_id": dataset_id,
        "document_id": document_id,
        "title": parsed.title,
        "parser_name": parsed.parser_name,
        "chunks_added": stats["chunks_added"],
        "chunks_updated": stats["chunks_updated"],
        "duplicates_skipped": stats["duplicates_skipped"],
        "total_chunks": total,
    }


def ingest_file(
    workbase_id: str,
    path: str | Path,
    title: str = "",
    notes: str = "",
    source_name: str | None = None,
    tags: list[str] | None = None,
    citation: dict[str, str] | None = None,
) -> dict[str, Any]:
    source_path = Path(path)
    file_name = source_name or source_path.name
    parsed, raw = parse_file(source_path)
    if title.strip():
        parsed.title = title.strip()
    fingerprint = sha256_bytes(raw)
    stable_key = f"file:{fingerprint}"
    stored_path = workbase_dir(workbase_id) / "sources" / f"{fingerprint[:16]}-{Path(file_name).name}"
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    if not stored_path.exists():
        shutil.copyfile(source_path, stored_path)
    return _ingest_parsed(
        workbase_id,
        parsed,
        source_fingerprint=fingerprint,
        stable_source_key=stable_key,
        ingestion_method="file_upload",
        file_name=file_name,
        stored_file_path=str(stored_path),
        notes=notes,
        tags=tags,
        citation=citation,
    )


def ingest_url(
    workbase_id: str,
    url: str,
    title: str = "",
    notes: str = "",
    tags: list[str] | None = None,
    citation: dict[str, str] | None = None,
) -> dict[str, Any]:
    parsed = parse_url(url, title=title)
    fingerprint = sha256_text(f"{parsed.canonical_url}\n{parsed.text}")
    stable_key = parsed.canonical_url
    return _ingest_parsed(
        workbase_id,
        parsed,
        source_fingerprint=fingerprint,
        stable_source_key=stable_key,
        ingestion_method="direct_url",
        notes=notes,
        tags=tags,
        citation=citation,
    )
