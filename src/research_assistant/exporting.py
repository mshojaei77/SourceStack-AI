import shutil
import subprocess
import tempfile
from pathlib import Path


def pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


def markdown_to_pdf(markdown: str, title: str = "sourcestack-export") -> tuple[bytes | None, str]:
    if not pandoc_available():
        return None, "PDF export requires Pandoc to be installed. Markdown export is still available."

    safe_title = "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-") or "sourcestack-export"
    with tempfile.TemporaryDirectory() as temp_dir:
        md_path = Path(temp_dir) / f"{safe_title}.md"
        pdf_path = Path(temp_dir) / f"{safe_title}.pdf"
        md_path.write_text(markdown, encoding="utf-8")
        result = subprocess.run(
            ["pandoc", str(md_path), "-o", str(pdf_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None, result.stderr.strip() or "Pandoc could not create the PDF."
        return pdf_path.read_bytes(), ""
