---
name: paper_references
track: core
kind: live_api
provider: arXiv PDF (pypdf), OpenAlex API
requires_env: []
inputs: [paper, start, end, source]
outputs: [items, total_references, citation_style, references_heading]
side_effect: local_file_write
---
# paper_references

Lists the references (bibliography) of a paper, from reference `[start]` to `[end]`,
and — when parsed from the PDF — where each one sits: `page_start:line_start` →
`page_end:line_end` (1-based line numbers within each page's pypdf-extracted text).

## Parameters

| Param | Values | Default |
|---|---|---|
| `paper` | arXiv ID/URL (`1706.03762`), DOI, OpenAlex ID (`W2626778328`) or title | required |
| `start` | first reference number, ≥ 1 | `1` |
| `end` | last reference number; span capped at 50 | `20` |
| `source` | `arxiv_pdf` \| `openalex` | `arxiv_pdf` |

## Sources

- **`arxiv_pdf`** — downloads the arXiv PDF into `arxiv_papers/` (reuses a cached copy;
  same download code as `paper_text`), finds the last `References` / `Bibliography` heading and
  splits the entries:
  - `bracket` style `[1] ...` and `numbered` style `1. ...` — numbers must be consecutive, so the
    original numbering is kept exactly.
  - `author_year` style (ACL/NeurIPS-like `Name, Name. 2018. Title...`) — a new entry starts when the
    previous line ends with `.` and the line starts like an author list (`Name,`, `Z. Chen,`,
    `Name and`, `Name. 2018`). Heuristic; numbered in list order.
  - Stops at an `Appendix`/`A Additional ...` heading, at a new page after a finished numbered
    list, or when an entry grows past 8 (numbered) / 12 (author-year) lines.
- **`openalex`** — resolves the paper (DOI → arXiv DOI `10.48550/arXiv.<id>` → OpenAlex ID →
  title search), then fetches details of `referenced_works[start-1:end]`. Works for any paper
  OpenAlex knows, but the order is **not** the paper's `[1],[2]` order, there are no page/line
  positions, and references OpenAlex could not match are missing.

## Input handling

- `start` < 1 or non-numeric → 1; `end` non-numeric → `start + 19`; `end < start` → `end = start`;
  span > 50 → trimmed to 50.
- `source` outside the enum → `arxiv_pdf`.
- Empty `paper`, no arXiv ID with `source=arxiv_pdf`, no References section, HTTP error →
  error dict `{"tool", "error", "message"}`; never raises.

Verified on 1706.03762 (bracket, 40 refs) and 1810.04805 (author-year, 56 refs = OpenAlex count).
