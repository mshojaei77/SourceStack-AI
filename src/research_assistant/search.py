import hashlib
import logging
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .config import settings
from .text import clean_text

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

SEARCH_WEB_TOOL = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web using the self-hosted SearxNG instance before answering.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A focused web search query for the user's latest question.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of search results to fetch, from 1 to 10.",
                    "default": settings.searxng_results,
                },
            },
            "required": ["query"],
        },
    },
}


def content_hash(*parts: str) -> str:
    payload = "\n".join(part or "" for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}
    ]
    normalized = parsed._replace(
        scheme=parsed.scheme.lower() or "https",
        netloc=parsed.netloc.lower(),
        query=urlencode(filtered_query),
        fragment="",
    )
    return urlunparse(normalized)


def domain_for_url(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def is_whitelisted_domain(url: str) -> bool:
    domain = domain_for_url(url)
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in settings.technical_domain_whitelist)


def technical_query(query: str) -> str:
    domains = settings.technical_domain_whitelist[:8]
    restrictors = " OR ".join(f"site:{domain}" for domain in domains)
    return f"({restrictors}) {query}" if restrictors else query


def search_web(query: str, num_results: int | None = None, technical_mode: bool | None = None) -> list[dict[str, Any]]:
    use_technical_mode = settings.technical_mode if technical_mode is None else technical_mode
    limit = max(1, min(num_results or settings.max_search_results, 10))
    transformed_query = technical_query(query) if use_technical_mode else query
    response = requests.get(
        f"{settings.searxng_url.rstrip('/')}/search",
        params={
            "q": transformed_query,
            "format": "json",
            "language": "auto",
            "pageno": 1,
            "engines": settings.searxng_engines,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    results = []
    dropped = []
    for index, item in enumerate(data.get("results", [])[:limit], start=1):
        url = canonicalize_url(item.get("url") or "")
        if use_technical_mode and not is_whitelisted_domain(url):
            dropped.append({"title": item.get("title") or "Untitled", "url": url, "reason": "domain_not_whitelisted"})
            continue
        trust_level = "trusted_domain" if is_whitelisted_domain(url) else "general_web"
        results.append(
            {
                "position": index,
                "title": item.get("title") or "Untitled",
                "url": url,
                "canonical_url": url,
                "snippet": item.get("content") or item.get("snippet") or "",
                "engine": item.get("engine") or "",
                "source_origin": "agent_web",
                "trust_level": trust_level,
                "is_verified": trust_level == "trusted_domain",
                "dropped_results": dropped,
            }
        )
    return results


def _extract_with_trafilatura(html: str, url: str) -> str:
    try:
        import trafilatura
    except ImportError:
        return ""

    extracted = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    return clean_text(extracted or "")


def _extract_with_beautifulsoup(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"]):
        tag.decompose()

    node = soup.find("main") or soup.find("article") or soup.body or soup
    return clean_text(node.get_text(" ", strip=True))


def _fetch_with_playwright(url: str) -> str:
    if not settings.scrape_playwright:
        return ""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        html = page.content()
        browser.close()
        return html


def scrape_url(url: str) -> tuple[str, str]:
    if not url:
        return "", "missing_url"

    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=25)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and "xml" not in content_type:
        return "", "unsupported_content_type"

    html = response.text
    text = _extract_with_trafilatura(html, url)
    if text:
        return text[: settings.scrape_max_chars], "trafilatura"

    text = _extract_with_beautifulsoup(html)
    if text:
        return text[: settings.scrape_max_chars], "beautifulsoup"

    rendered = _fetch_with_playwright(url)
    if rendered:
        text = _extract_with_trafilatura(rendered, url) or _extract_with_beautifulsoup(rendered)
        if text:
            return text[: settings.scrape_max_chars], "playwright"

    return "", "empty_extraction"


def search_and_scrape(query: str, num_results: int | None = None, technical_mode: bool | None = None) -> list[dict[str, Any]]:
    results = search_web(query, num_results, technical_mode=technical_mode)
    for result in results[: settings.max_scrape_pages]:
        result["source_id"] = content_hash(query, result.get("url", ""), str(result.get("position", "")))[:16]
        try:
            scraped, content_source = scrape_url(result["url"])
            result["scrape_status"] = "success" if scraped else "failed"
            result["scrape_error"] = "" if scraped else content_source
            result["content_source"] = content_source if scraped else "snippet"
        except Exception as exc:
            logger.warning("Could not scrape %s: %s", result["url"], exc)
            scraped = ""
            result["scrape_status"] = "failed"
            result["scrape_error"] = str(exc)
            result["content_source"] = "snippet"
        result["content"] = scraped or result["snippet"]
        time.sleep(0.2)
    for result in results[settings.max_scrape_pages :]:
        result["source_id"] = content_hash(query, result.get("url", ""), str(result.get("position", "")))[:16]
        result["scrape_status"] = "skipped"
        result["scrape_error"] = "max_scrape_pages"
        result["content_source"] = "snippet"
        result["content"] = result["snippet"]
    return results
