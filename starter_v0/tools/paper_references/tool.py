from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import requests

from tools._shared import TIMEOUT, err
from tools.paper_text.tool import ARXIV_DIR, _download_arxiv_pdf


OPENALEX_WORKS_URL = "https://api.openalex.org/works"
SOURCES = {"arxiv_pdf", "openalex"}
MAX_SPAN = 50
DEFAULT_SPAN = 20

ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
DOI_RE = re.compile(r"(10\.\d{4,9}/\S+)")
OPENALEX_ID_RE = re.compile(r"\b(W\d{4,})\b")

HEADING_RE = re.compile(r"^(?:\d+\.?\s*)?(references|bibliography|literature cited)\s*$", re.IGNORECASE)
STOP_RE = re.compile(
    r"^(appendix|appendices|supplementary)\b|^[A-Z](?:\.\d+)?\s+(appendix|additional|supplementary|details|experimental|proofs?)\b",
    re.IGNORECASE,
)
BRACKET_RE = re.compile(r"^\[(\d{1,3})\]\s*")
NUMBERED_RE = re.compile(r"^(\d{1,3})\.\s+(?=[A-Z])")
# Author-year entry start: "First Last, ..." / "Z. Chen, ..." / "First Last and ..." / "Wilson L Taylor. 1953."
AUTHOR_START_RE = re.compile(
    r"^(?!(?:In|Proceedings|Advances|Association|Curran|Springer|MIT|ACM|IEEE|Inc)\b)"
    r"[A-Z][\w'’\-]*\.?(?:\s+(?:[A-Z][\w.'’\-]*|de|van|von|der|di|da|la|le))*\s*(?:,|\band\b|\.\s+(?:19|20)\d{2})"
)
PAGE_NUMBER_RE = re.compile(r"^\d{1,3}$")
# An entry longer than this means we ran past the end of the list (e.g. into an unlabeled appendix).
MAX_ENTRY_LINES = {"bracket": 8, "numbered": 8, "author_year": 12}


# ---------------- range handling ----------------

def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalise_range(start: Any, end: Any) -> tuple[int, int]:
    start = max(1, _to_int(start, 1))
    end = _to_int(end, start + DEFAULT_SPAN - 1)
    if end < start:
        end = start
    return start, min(end, start + MAX_SPAN - 1)


# ---------------- PDF parsing (pure, unit-testable) ----------------

def _join_lines(lines: list[str]) -> str:
    text = ""
    for line in lines:
        line = line.strip()
        if text.endswith("-") and line[:1].islower():
            text = text[:-1] + line  # re-join hyphenated word: "lan-" + "guage"
        else:
            text = f"{text} {line}" if text else line
    return " ".join(text.split())


def parse_references(pages: list[str]) -> dict[str, Any]:
    """Split the References section of extracted PDF pages into entries with page/line positions.

    Returns {"style", "heading_page", "heading_line", "entries": [{number, text, page_start,
    line_start, page_end, line_end}]}. Line numbers are 1-based within each page's extracted text.
    """
    lines: list[tuple[int, int, str]] = []  # (page, line_in_page, text)
    for page_index, page_text in enumerate(pages, start=1):
        for line_index, line in enumerate((page_text or "").splitlines(), start=1):
            lines.append((page_index, line_index, line.strip()))

    heading_at = None
    for index, (_, _, text) in enumerate(lines):
        if HEADING_RE.match(text):
            heading_at = index  # keep the LAST heading (a TOC may mention "References" earlier)
    if heading_at is None:
        return {"style": None, "heading_page": None, "heading_line": None, "entries": []}

    body = [item for item in lines[heading_at + 1:] if item[2] and not PAGE_NUMBER_RE.match(item[2])]
    first = body[0][2] if body else ""
    if BRACKET_RE.match(first):
        style = "bracket"
    elif NUMBERED_RE.match(first):
        style = "numbered"
    else:
        style = "author_year"

    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def close() -> None:
        if current:
            current["text"] = _join_lines(current.pop("_lines"))
            entries.append(current)

    for page, line_no, text in body:
        if STOP_RE.match(text):
            break
        number = None
        expected = current["number"] + 1 if current else None  # numbers must be consecutive
        if style in ("bracket", "numbered"):
            match = (BRACKET_RE if style == "bracket" else NUMBERED_RE).match(text)
            if match and (expected is None or int(match.group(1)) == expected):
                number = int(match.group(1))
        else:
            previous = current["_lines"][-1] if current else ""
            if current is None:
                number = 1
            elif previous.endswith((".", "?", "!")) and AUTHOR_START_RE.match(text):
                number = expected

        if number is not None:
            close()
            if style == "bracket":
                text = BRACKET_RE.sub("", text, count=1)
            elif style == "numbered":
                text = NUMBERED_RE.sub("", text, count=1)
            current = {"number": number, "_lines": [text], "page_start": page, "line_start": line_no,
                       "page_end": page, "line_end": line_no}
        elif current is not None:
            new_page_after_full_stop = page != current["page_end"] and current["_lines"][-1].endswith(".")
            if style != "author_year" and new_page_after_full_stop:
                break  # numbered list ended on the previous page; this page is something else
            if len(current["_lines"]) >= MAX_ENTRY_LINES[style]:
                break
            current["_lines"].append(text)
            current["page_end"], current["line_end"] = page, line_no
    close()
    return {"style": style, "heading_page": lines[heading_at][0], "heading_line": lines[heading_at][1], "entries": entries}


def _pdf_pages(pdf_path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf first: pip install pypdf") from exc
    return [page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages]


def _arxiv_pdf_path(arxiv_id: str) -> tuple[Path, str]:
    cached = ARXIV_DIR / f"{arxiv_id}.pdf"
    if cached.exists() and cached.stat().st_size > 0:
        return cached, f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    _, path, pdf_url = _download_arxiv_pdf(arxiv_id)
    return path, pdf_url


def _from_arxiv_pdf(paper: str, start: int, end: int) -> dict[str, Any]:
    match = ARXIV_ID_RE.search(paper)
    if not match:
        raise ValueError("source=arxiv_pdf needs an arXiv ID or URL (e.g. 1706.03762); use source=openalex for a DOI or title")
    arxiv_id = match.group(0)
    path, pdf_url = _arxiv_pdf_path(arxiv_id)
    parsed = parse_references(_pdf_pages(path))
    entries = parsed["entries"]
    if not entries:
        raise ValueError("Could not find a References section in the PDF text")
    selected = [entry for entry in entries if start <= entry["number"] <= end]
    note = "Positions are page + line numbers in pypdf-extracted text (1-based per page)."
    if parsed["style"] == "author_year":
        note += " Author-year style: entries are split heuristically and numbered in list order."
    return {
        "paper_id": arxiv_id,
        "pdf_url": pdf_url,
        "citation_style": parsed["style"],
        "references_heading": {"page": parsed["heading_page"], "line": parsed["heading_line"]},
        "total_references": len(entries),
        "items": [{**entry, "source": "arxiv.org"} for entry in selected],
        "note": note,
    }


# ---------------- OpenAlex ----------------

def _openalex_lookup_url(paper: str) -> tuple[str, dict[str, Any]]:
    select = "id,title,doi,publication_year,referenced_works"
    arxiv = ARXIV_ID_RE.search(paper)
    doi = DOI_RE.search(paper)
    work_id = OPENALEX_ID_RE.search(paper)
    if doi:
        return f"{OPENALEX_WORKS_URL}/doi:{doi.group(1)}", {"select": select}
    if arxiv:
        return f"{OPENALEX_WORKS_URL}/doi:10.48550/arXiv.{arxiv.group(1)}", {"select": select}
    if work_id:
        return f"{OPENALEX_WORKS_URL}/{work_id.group(1)}", {"select": select}
    return OPENALEX_WORKS_URL, {"search": paper, "per_page": 1, "select": select}


def _from_openalex(paper: str, start: int, end: int) -> dict[str, Any]:
    url, params = _openalex_lookup_url(paper)
    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    work = (data.get("results") or [None])[0] if "results" in data else data
    if not work:
        raise ValueError(f"No OpenAlex work found for: {paper}")
    referenced = work.get("referenced_works") or []
    wanted = referenced[start - 1:end]
    details: dict[str, dict[str, Any]] = {}
    if wanted:
        ids = "|".join(item.rsplit("/", 1)[-1] for item in wanted)
        detail_response = requests.get(
            OPENALEX_WORKS_URL,
            params={"filter": f"openalex_id:{ids}", "per_page": len(wanted),
                    "select": "id,title,doi,publication_year,authorships,primary_location"},
            timeout=TIMEOUT,
        )
        detail_response.raise_for_status()
        details = {item.get("id"): item for item in (detail_response.json().get("results") or [])}
    items = []
    for offset, ref_id in enumerate(wanted):
        ref = details.get(ref_id, {})
        source = ((ref.get("primary_location") or {}).get("source") or {})
        authors = [(a.get("author") or {}).get("display_name") for a in (ref.get("authorships") or [])]
        items.append({
            "number": start + offset,
            "text": ref.get("title") or ref_id,
            "authors": [name for name in authors if name][:5],
            "year": ref.get("publication_year"),
            "venue": source.get("display_name"),
            "doi": ref.get("doi"),
            "url": ref.get("doi") or ref_id,
            "page_start": None, "line_start": None, "page_end": None, "line_end": None,
            "source": "openalex.org",
        })
    return {
        "paper_id": work.get("id"),
        "matched_title": work.get("title"),
        "matched_year": work.get("publication_year"),
        "citation_style": None,
        "references_heading": None,
        "total_references": len(referenced),
        "items": items,
        "note": "OpenAlex order is NOT the paper's [1],[2] order and has no page/line positions; "
                "references OpenAlex could not match are missing. Use source=arxiv_pdf for exact numbering.",
    }


# ---------------- Tool entry point ----------------

def get_paper_references(paper: str = "", start: int = 1, end: int = DEFAULT_SPAN, source: str = "arxiv_pdf") -> dict[str, Any]:
    """List a paper's references [start]..[end], with page/line positions when parsed from the PDF."""
    try:
        paper = " ".join(str(paper or "").split())
        if not paper:
            raise ValueError("paper is required: arXiv ID/URL, DOI, OpenAlex ID or title")
        start, end = _normalise_range(start, end)
        source = str(source or "arxiv_pdf").strip().lower()
        if source not in SOURCES:
            source = "arxiv_pdf"
        fetch = _from_openalex if source == "openalex" else _from_arxiv_pdf
        result = fetch(paper, start, end)
        return {"tool": "paper_references", "paper": paper, "source": source, "start": start, "end": end, **result}
    except Exception as exc:
        return err("paper_references", exc)
