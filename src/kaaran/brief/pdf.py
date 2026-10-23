"""HTML -> PDF with a headless Chromium browser (Edge or Chrome), which shapes Devanagari correctly.

The browser is found from KAARAN_BROWSER, then the standard Windows install paths, then the PATH.
If none is available, PdfUnavailable is raised and callers fall back to the HTML/Markdown brief.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..llm.client import setting

WINDOWS_PATHS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)
PATH_NAMES = ("msedge", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")


class PdfUnavailable(RuntimeError):
    pass


def find_browser() -> str | None:
    configured = setting("KAARAN_BROWSER")
    if configured and Path(configured).exists():
        return configured
    for p in WINDOWS_PATHS:
        if Path(p).exists():
            return p
    for name in PATH_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def html_to_pdf(document: str, out_path: str | Path, timeout: int = 90) -> Path:
    browser = find_browser()
    if browser is None:
        raise PdfUnavailable("no Edge/Chrome/Chromium browser found (set KAARAN_BROWSER)")
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "brief.html"
        src.write_text(document, encoding="utf-8")
        cmd = [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               "--disable-extensions", f"--user-data-dir={Path(d) / 'profile'}", "--no-pdf-header-footer",
               "--print-to-pdf-no-header", f"--print-to-pdf={out_path}", src.as_uri()]
        if out_path.exists():
            out_path.unlink()
        try:
            subprocess.run(cmd, check=False, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise PdfUnavailable(f"browser timed out after {timeout}s") from e
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise PdfUnavailable("browser did not produce a PDF")
    return out_path
