import json
import os
import tempfile
from pathlib import Path
from typing import Any

import requests


API_BASE = os.getenv("SOURCESTACK_API_BASE", "http://127.0.0.1:8000/api").rstrip("/")
TIMEOUT = 120


def log(message: str) -> None:
    print(f"[integration] {message}")


def request_json(method: str, path: str, **kwargs: Any) -> Any:
    response = requests.request(method, f"{API_BASE}{path}", timeout=TIMEOUT, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed ({response.status_code}): {response.text}")
    if response.text:
        return response.json()
    return None


def stream_answer(workbase_id: str, question: str) -> tuple[str, list[dict[str, Any]]]:
    payload = {
        "content": question,
        "retrieval_mode": "curated_only",
        "answer_style": "Simple",
        "technical_mode": False,
        "advanced_mode": True,
    }
    response = requests.post(
        f"{API_BASE}/chats/{workbase_id}:default/messages/stream",
        json=payload,
        headers={"Accept": "text/event-stream"},
        timeout=TIMEOUT,
        stream=True,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"stream endpoint failed ({response.status_code}): {response.text}")

    content = ""
    citations: list[dict[str, Any]] = []
    current_event = ""
    saw_done = False
    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
            continue
        if not line.startswith("data:"):
            continue
        data = json.loads(line.split(":", 1)[1].strip())
        if current_event == "token":
            content += data.get("text", "")
        elif current_event == "citations":
            citations = data.get("citations", [])
        elif current_event == "done":
            saw_done = True
            break
        elif current_event == "error":
            raise RuntimeError(data.get("message", "stream error"))
    if not saw_done:
        raise RuntimeError("stream did not return a done event")
    return content, citations


def main() -> int:
    workbase_id = ""
    try:
        log("Creating Workbase")
        created = request_json("POST", "/workbases", json={"name": "Integration Check", "description": "Automated check"})
        workbase_id = created["id"]
        log(f"Workbase created: {workbase_id}")

        log("Uploading source file")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write(
                "Retrieval-augmented generation (RAG) combines retrieval and generation.\n"
                "A retriever finds relevant evidence and a generator answers with citations.\n"
            )
            temp_path = Path(handle.name)
        with temp_path.open("rb") as file_obj:
            files = {"file": (temp_path.name, file_obj, "text/plain")}
            data = {"title": "Integration Source", "notes": "Smoke test source", "tags": "integration,rag"}
            upload = requests.post(
                f"{API_BASE}/workbases/{workbase_id}/sources/upload",
                files=files,
                data=data,
                timeout=TIMEOUT,
            )
        temp_path.unlink(missing_ok=True)
        if upload.status_code >= 400:
            raise RuntimeError(f"source upload failed ({upload.status_code}): {upload.text}")
        log("Source uploaded")

        log("Asking a question with streaming")
        answer, citations = stream_answer(workbase_id, "What is RAG according to the uploaded source?")
        if not answer.strip():
            raise RuntimeError("streaming answer was empty")
        if not citations:
            raise RuntimeError("streaming response returned no citations")
        log(f"Streamed answer length: {len(answer)}")
        log(f"Citations returned: {len(citations)}")

        log("Saving answer as report")
        report = request_json(
            "POST",
            f"/workbases/{workbase_id}/reports",
            json={
                "title": "Integration Report",
                "type": "Research Summary",
                "content": answer,
                "sources": citations,
                "generate": "none",
            },
        )
        report_id = report["id"]
        log(f"Report saved: {report_id}")

        log("Exporting Markdown")
        markdown_resp = requests.post(
            f"{API_BASE}/exports/markdown",
            json={
                "title": "Integration Report",
                "content": answer,
                "sources": citations,
                "workbase_name": "Integration Check",
            },
            timeout=TIMEOUT,
        )
        if markdown_resp.status_code >= 400:
            raise RuntimeError(f"markdown export failed ({markdown_resp.status_code}): {markdown_resp.text}")
        markdown_text = markdown_resp.text
        if "References" not in markdown_text:
            raise RuntimeError("markdown export missing references section")
        log("Markdown export includes references")

        log("Exporting PDF")
        pdf_resp = requests.post(
            f"{API_BASE}/exports/pdf",
            json={
                "title": "Integration Report",
                "content": answer,
                "sources": citations,
                "workbase_name": "Integration Check",
            },
            timeout=TIMEOUT,
        )
        if pdf_resp.status_code == 503:
            log("PDF export skipped: Pandoc not available")
        elif pdf_resp.status_code >= 400:
            raise RuntimeError(f"pdf export failed ({pdf_resp.status_code}): {pdf_resp.text}")
        else:
            if pdf_resp.headers.get("content-type", "").lower().find("application/pdf") == -1:
                raise RuntimeError("pdf export response was not application/pdf")
            log("PDF export successful")

        log("Integration checks completed")
        return 0
    except Exception as exc:
        log(f"FAILED: {exc}")
        return 1
    finally:
        if workbase_id:
            try:
                requests.delete(f"{API_BASE}/workbases/{workbase_id}", timeout=TIMEOUT)
                log("Cleanup complete")
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
