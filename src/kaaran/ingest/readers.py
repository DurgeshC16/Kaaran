"""Low-level readers: physical rows of xlsx/csv files and text lines of PDFs, with row numbers kept."""

from __future__ import annotations

import csv
import io
from collections import Counter
from functools import lru_cache
from pathlib import Path

import openpyxl
import pypdfium2 as pdfium

FORMATS = {".xlsx": "xlsx", ".csv": "csv", ".pdf": "pdf"}
HEADER_SCAN_ROWS = 15
CSV_TITLE_PREFIX = "#"


@lru_cache(maxsize=32)
def _xlsx_rows(path: str, mtime: int) -> dict[str, list[tuple]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return {ws.title: list(ws.iter_rows(values_only=True)) for ws in wb.worksheets}
    finally:
        wb.close()


def xlsx_rows(path: Path) -> dict[str, list[tuple]]:
    """sheet -> rows; list index + 1 is the physical (1-based) row number."""
    return _xlsx_rows(str(path), path.stat().st_mtime_ns)


@lru_cache(maxsize=32)
def _csv_rows(path: str, mtime: int) -> tuple[str, bool, tuple[tuple[str, ...], ...]]:
    data = Path(path).read_bytes()
    bom = data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig")
    rows = []
    for line in text.splitlines():
        if line.startswith(CSV_TITLE_PREFIX):
            rows.append((line,))
        else:
            rows.append(tuple(next(csv.reader(io.StringIO(line))) if line else ()))
    return ("utf-8-sig" if bom else "utf-8", bom, tuple(rows))


def csv_rows(path: Path) -> tuple[str, bool, tuple[tuple[str, ...], ...]]:
    """(encoding, has_bom, rows); index + 1 is the physical line number (title lines included)."""
    return _csv_rows(str(path), path.stat().st_mtime_ns)


def header_candidates(path: Path) -> dict[str | None, list[tuple[int, tuple]]]:
    """First rows of every sheet (or of the CSV) as (physical_row, cells), for header detection."""
    fmt = FORMATS[path.suffix.lower()]
    if fmt == "xlsx":
        return {s: [(i + 1, r) for i, r in enumerate(rows[:HEADER_SCAN_ROWS])] for s, rows in xlsx_rows(path).items()}
    _, _, rows = csv_rows(path)
    return {None: [(i + 1, r) for i, r in enumerate(rows[:HEADER_SCAN_ROWS]) if not (r and str(r[0]).startswith(CSV_TITLE_PREFIX))]}


@lru_cache(maxsize=8)
def _pdf_lines(path: str, mtime: int) -> tuple[tuple[int, int, str], ...]:
    pdf = pdfium.PdfDocument(path)
    try:
        out = []
        for p in range(len(pdf)):
            text = pdf[p].get_textpage().get_text_range()
            for i, line in enumerate(text.splitlines(), start=1):
                line = line.strip()
                if line:
                    out.append((p + 1, i, line))
        return tuple(out)
    finally:
        pdf.close()


def pdf_lines(path: Path) -> tuple[tuple[int, int, str], ...]:
    """(page, line_no, text) for every non-empty text line."""
    return _pdf_lines(str(path), path.stat().st_mtime_ns)


def pdf_page_count(path: Path) -> int:
    return max((p for p, _, _ in pdf_lines(path)), default=0)


def pdf_header_line(path: Path) -> str:
    """The table header: the line repeated on the most pages that contains no digits."""
    pages_per_line = Counter()
    seen = set()
    for page, _, text in pdf_lines(path):
        if any(ch.isdigit() for ch in text) or (page, text) in seen:
            continue
        seen.add((page, text))
        pages_per_line[text] += 1
    candidates = [(n, t) for t, n in pages_per_line.items() if "SYNTHETIC" not in t]
    return max(candidates)[1] if candidates else ""
