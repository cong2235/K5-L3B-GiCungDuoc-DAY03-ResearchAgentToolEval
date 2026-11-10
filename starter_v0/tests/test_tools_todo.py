"""Tool Unit Test Challenge — filled in.

Patterns come from test_tools_examples.py. Fixtures are in conftest.py.

Rules:
- Offline only: mock HTTP with `fake_http`, set fake keys with `monkeypatch.setenv`.
- One behaviour per test. Name the test after the behaviour, not the function.
- Done = `pytest tests/ -v` shows 0 skipped, 0 failed.
"""
from __future__ import annotations

from datetime import date

import pytest
import requests

from conftest import FakeResponse
from tools import TOOL_FUNCTIONS

clarify = TOOL_FUNCTIONS["clarify"]
format_tool = TOOL_FUNCTIONS["format"]
send = TOOL_FUNCTIONS["send"]
lookup = TOOL_FUNCTIONS["lookup"]
fetch = TOOL_FUNCTIONS["fetch"]
timeline = TOOL_FUNCTIONS["timeline"]
social_search = TOOL_FUNCTIONS["social_search"]
policy = TOOL_FUNCTIONS["policy"]
hackernews = TOOL_FUNCTIONS["hackernews"]
wikipedia = TOOL_FUNCTIONS["wikipedia"]
openalex = TOOL_FUNCTIONS["openalex"]


# ---------------- clarify ----------------

def test_clarify_choice_returns_options_and_awaits_user() -> None:
    result = clarify(question="Chọn nguồn?", response_type="choice", options=["web", "twitter"])
    assert result["options"] == ["web", "twitter"]
    assert result["response_type"] == "choice"
    assert result["awaiting_user"] is True


# ---------------- format ----------------

def test_format_sections_groups_items_by_section() -> None:
    items = [
        {"title": "a1", "url": "https://a.com/1", "section": "A"},
        {"title": "b1", "url": "https://b.com/1", "section": "B"},
        {"title": "a2", "url": "https://a.com/2", "section": "A"},
    ]
    markdown = format_tool(items=items, template="sections")["markdown"]
    assert markdown.count("## A") == 1
    assert markdown.count("## B") == 1
    assert markdown.index("a2") < markdown.index("## B")  # a2 grouped under A


def test_format_thread_numbers_items() -> None:
    items = [{"title": f"t{i}", "url": f"https://x.com/{i}"} for i in range(3)]
    lines = format_tool(items=items, template="thread")["markdown"].split("\n\n")
    assert [line.split(" ", 1)[0] for line in lines] == ["1/", "2/", "3/"]


def test_format_empty_items_does_not_crash() -> None:
    assert format_tool(items=None, template="sections")["item_count"] == 0
    assert format_tool(items=[], template="brief")["item_count"] == 0


def test_format_item_without_url_has_no_empty_link() -> None:
    """Regression check for the B5 hint: items missing `url` must not render `[](...)` links."""
    markdown = format_tool(items=[{"title": "No link", "source": "memo"}], template="bullets")["markdown"]
    assert "](" not in markdown
    assert markdown.endswith("memo")


# ---------------- send (guardrail) ----------------

def test_send_confirmed_posts_to_telegram(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-10042")
    calls = fake_http(FakeResponse({"ok": True}))

    result = send(text="Bản tin AI", confirmed=True)

    assert len(calls) == 1
    assert calls[0]["method"] == "POST"
    assert "bot123:abc/sendMessage" in calls[0]["url"]
    assert calls[0]["json"]["chat_id"] == "-10042"
    assert calls[0]["json"]["text"] == "Bản tin AI"
    assert result["status"] == "sent"


def test_send_confirmed_without_env_returns_error_and_no_request(fake_http) -> None:
    calls = fake_http(FakeResponse({"ok": True}))
    result = send(text="x", confirmed=True)
    assert result["error"] == "RuntimeError"
    assert "TELEGRAM_BOT_TOKEN" in result["message"]
    assert calls == []


# ---------------- lookup ----------------

def test_lookup_without_timeframe_omits_time_range(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    calls = fake_http(FakeResponse({"results": []}))
    result = lookup(query="AI", timeframe=None)
    assert "time_range" not in calls[0]["json"]
    assert result["items"] == []


def test_lookup_string_max_results_is_sent_as_int(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    calls = fake_http(FakeResponse({"results": []}))
    lookup(query="AI", max_results="3")
    assert calls[0]["json"]["max_results"] == 3


# ---------------- fetch ----------------

def test_fetch_maps_firecrawl_response(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc")
    calls = fake_http(FakeResponse({"data": {
        "markdown": "# Hello\nbody",
        "metadata": {"title": "T", "sourceURL": "https://www.example.com/post"},
    }}))

    result = fetch(url="https://www.example.com/post")

    assert calls[0]["url"] == "https://api.firecrawl.dev/v1/scrape"
    assert calls[0]["json"]["url"] == "https://www.example.com/post"
    assert calls[0]["headers"]["Authorization"] == "Bearer fc"
    assert result["items"][0] == {
        "title": "T", "url": "https://www.example.com/post",
        "source": "example.com", "summary": "# Hello\nbody",
    }


def test_fetch_truncates_markdown_to_4000_chars(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc")
    fake_http(FakeResponse({"data": {"markdown": "y" * 9000, "metadata": {}}}))
    item = fetch(url="https://example.com")["items"][0]
    assert len(item["summary"]) == 4000
    assert item["title"] == "https://example.com"  # falls back to url when no title


# ---------------- timeline / social_search ----------------

def test_timeline_respects_limit_and_skips_items_without_id(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    raw = [{"text": "no id", "screen_name": "sama"}] + [
        {"tweet_id": str(i), "text": f"tweet {i}", "screen_name": "sama"} for i in range(6)
    ]
    calls = fake_http(FakeResponse({"timeline": raw}))

    result = timeline(screenname="sama", limit=3)

    assert calls[0]["params"] == {"screenname": "sama"}
    assert calls[0]["headers"]["x-rapidapi-key"] == "rk"
    assert len(result["items"]) == 3
    assert [item["url"] for item in result["items"]] == [f"https://x.com/sama/status/{i}" for i in range(3)]


def test_social_search_passes_search_type(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    calls = fake_http(FakeResponse({"timeline": []}))
    result = social_search(query="OpenAI", search_type="Top")
    assert calls[0]["url"].endswith("/search.php")
    assert calls[0]["params"] == {"query": "OpenAI", "search_type": "Top"}
    assert result["search_type"] == "Top"


def test_timeline_without_key_returns_error_dict(fake_http) -> None:
    calls = fake_http(FakeResponse({}))
    result = timeline(screenname="sama")
    assert result["error"] == "RuntimeError"
    assert calls == []


# ---------------- policy (local knowledge + trust boundary) ----------------

def test_policy_empty_query_returns_no_results() -> None:
    assert policy(query="")["results"] == []
    assert policy(query="   ")["results"] == []


def test_policy_area_filter_only_returns_that_area() -> None:
    results = policy(query="dữ liệu cá nhân privacy", policy_area="data_privacy", top_k=5)["results"]
    assert results
    assert all(item["policy_area"] == "data_privacy" for item in results)


def test_policy_instruction_like_lines_go_to_untrusted_text() -> None:
    results = policy(query="citation tweet verified", policy_area="source_citation", top_k=10)["results"]
    flagged = [line for item in results for line in item["untrusted_text"] if "viral tweet" in line]
    assert flagged, "instruction-like quoted line should be isolated in untrusted_text"
    assert all("viral tweet as verified" not in item["facts"] for item in results)


# ================ TEAM TOOLS ================

# ---------------- hackernews ----------------

def test_hackernews_sends_query_and_maps_hits(fake_http) -> None:
    calls = fake_http(FakeResponse({"hits": [
        {"objectID": "42", "title": "Agents", "url": "https://www.blog.dev/a", "points": 120, "num_comments": 33,
         "created_at": "2026-11-01T00:00:00Z"},
        {"objectID": "43", "title": "Ask HN", "url": None, "points": 5, "num_comments": 1},
    ]}))

    result = hackernews(query="LLM agents", limit=2)

    assert calls[0]["url"] == "https://hn.algolia.com/api/v1/search"
    assert calls[0]["params"] == {"query": "LLM agents", "tags": "story", "hitsPerPage": 2}
    assert result["items"][0]["url"] == "https://www.blog.dev/a"
    assert result["items"][0]["source"] == "blog.dev"
    assert result["items"][0]["summary"] == "120 points, 33 comments"
    # Ask HN post without external url falls back to the discussion page
    assert result["items"][1]["url"] == "https://news.ycombinator.com/item?id=43"


def test_hackernews_sort_date_uses_search_by_date_endpoint(fake_http) -> None:
    calls = fake_http(FakeResponse({"hits": []}))
    hackernews(query="rust", sort="date")
    assert calls[0]["url"].endswith("/search_by_date")


def test_hackernews_bad_model_input_is_coerced(fake_http) -> None:
    calls = fake_http(FakeResponse({"hits": []}))
    result = hackernews(query="ai", sort="popular", limit="0")
    assert result["sort"] == "relevance"          # out-of-enum -> default
    assert calls[0]["params"]["hitsPerPage"] == 1  # "0" -> clamped to 1


def test_hackernews_empty_query_returns_error_without_request(fake_http) -> None:
    calls = fake_http(FakeResponse({"hits": []}))
    result = hackernews(query="  ")
    assert result["error"] == "ValueError"
    assert calls == []


def test_hackernews_http_error_returns_error_dict(fake_http) -> None:
    fake_http(FakeResponse(status_code=503))
    assert hackernews(query="ai")["error"] == "HTTPError"


# ---------------- wikipedia ----------------

def test_wikipedia_returns_intro_of_best_match(fake_http) -> None:
    calls = fake_http(FakeResponse({"query": {"pages": [
        {"title": "Transformer (deep learning)", "fullurl": "https://en.wikipedia.org/wiki/Transformer",
         "extract": "A transformer is a deep learning architecture."},
    ]}}))

    result = wikipedia(query="transformer model")

    assert calls[0]["url"] == "https://en.wikipedia.org/w/api.php"
    assert calls[0]["params"]["gsrsearch"] == "transformer model"
    assert "User-Agent" in calls[0]["headers"]
    assert result["items"] == [{
        "title": "Transformer (deep learning)", "url": "https://en.wikipedia.org/wiki/Transformer",
        "source": "en.wikipedia.org", "summary": "A transformer is a deep learning architecture.",
    }]


def test_wikipedia_unknown_lang_falls_back_to_en_and_long_extract_truncated(fake_http) -> None:
    calls = fake_http(FakeResponse({"query": {"pages": [{"title": "X", "fullurl": "u", "extract": "z" * 3000}]}}))
    result = wikipedia(query="x", lang="klingon")
    assert calls[0]["url"].startswith("https://en.wikipedia.org")
    assert len(result["items"][0]["summary"]) == 1503


def test_wikipedia_no_match_returns_empty_items(fake_http) -> None:
    fake_http(FakeResponse({"batchcomplete": True}))
    assert wikipedia(query="qwertyuiopasdf")["items"] == []


def test_wikipedia_network_error_returns_error_dict(fake_http) -> None:
    fake_http(requests.Timeout("timed out"))
    result = wikipedia(query="AI")
    assert result["error"] == "Timeout"
    assert result["tool"] == "wikipedia_summary"


# ---------------- openalex ----------------

def _openalex_router(monkeypatch, authors=None, works=None):
    """Route requests.get by URL: /authors -> authors payload, /works -> works payload."""
    calls: list[dict] = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        payload = authors if url.endswith("/authors") else works
        if isinstance(payload, FakeResponse):
            return payload
        return FakeResponse(payload if payload is not None else {})

    monkeypatch.setattr(requests, "get", fake_get)
    return calls


WORK = {
    "id": "https://openalex.org/W1", "display_name": "Deep learning", "publication_year": 2015,
    "cited_by_count": 60000, "doi": "https://doi.org/10.1038/nature14539",
    "authorships": [{"author": {"display_name": n}} for n in ("Y. LeCun", "Y. Bengio", "G. Hinton", "Extra")],
    "primary_location": {"source": {"display_name": "Nature"}},
}


def test_openalex_by_author_resolves_id_then_filters_works(monkeypatch) -> None:
    calls = _openalex_router(
        monkeypatch,
        authors={"results": [{"id": "https://openalex.org/A5000", "display_name": "Geoffrey E. Hinton"}]},
        works={"results": [WORK]},
    )

    result = openalex(author="Geoffrey Hinton", limit=3)

    assert calls[0]["url"].endswith("/authors")
    assert calls[0]["params"]["search"] == "Geoffrey Hinton"
    assert calls[1]["url"].endswith("/works")
    assert calls[1]["params"]["filter"] == "author.id:A5000"
    assert calls[1]["params"]["sort"] == "cited_by_count:desc"
    assert calls[1]["params"]["per-page"] == 3
    assert "search" not in calls[1]["params"]
    assert result["author"] == "Geoffrey E. Hinton"
    assert result["items"][0] == {
        "title": "Deep learning", "url": "https://doi.org/10.1038/nature14539", "source": "Nature",
        "summary": "2015, 60000 citations, authors: Y. LeCun, Y. Bengio, G. Hinton",
        "year": 2015, "cited_by": 60000,
    }


def test_openalex_by_topic_skips_author_lookup_and_sorts_recent(monkeypatch) -> None:
    calls = _openalex_router(monkeypatch, works={"results": []})
    result = openalex(query="retrieval-augmented generation", sort="recent")
    assert len(calls) == 1 and calls[0]["url"].endswith("/works")
    assert calls[0]["params"]["search"] == "retrieval-augmented generation"
    assert calls[0]["params"]["sort"] == "publication_date:desc"
    # future-dated records must be excluded from "newest first"
    assert calls[0]["params"]["filter"] == f"to_publication_date:{date.today().isoformat()}"
    assert result["items"] == []


def test_openalex_unknown_author_returns_empty_items_without_works_request(monkeypatch) -> None:
    calls = _openalex_router(monkeypatch, authors={"results": []})
    result = openalex(author="Zzzxq Nobody")
    assert result["items"] == [] and result["note"] == "author not found"
    assert len(calls) == 1


def test_openalex_needs_query_or_author_and_makes_no_request(fake_http) -> None:
    calls = fake_http(FakeResponse({}))
    assert openalex(query="  ", author=None)["error"] == "ValueError"
    assert calls == []


def test_openalex_bad_model_input_is_coerced(monkeypatch) -> None:
    calls = _openalex_router(monkeypatch, works={"results": []})
    result = openalex(query="llm", sort="best", limit="999")
    assert result["sort"] == "cited"
    assert calls[0]["params"]["per-page"] == 20


def test_openalex_http_error_returns_error_dict(fake_http) -> None:
    fake_http(FakeResponse(status_code=429))
    assert openalex(query="llm")["error"] == "HTTPError"


@pytest.mark.parametrize("name", ["hackernews", "wikipedia", "openalex"])
def test_team_tools_never_raise_on_wrong_arg_types(name: str, fake_http) -> None:
    fake_http(FakeResponse({}))
    result = TOOL_FUNCTIONS[name](query=None)
    assert "error" in result


# ---------------- Regression: bug found in starter tools (REPORT B5) ----------------

@pytest.mark.parametrize("tool_name", ["timeline", "social_search"])
def test_negative_limit_does_not_slice_from_the_end(tool_name: str, monkeypatch, fake_http) -> None:
    """Bug: `items[: int(limit)]` with limit=-1 returned all-but-last (5 of 6) instead of 1 item."""
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    raw = [{"tweet_id": str(i), "text": f"t{i}", "screen_name": "sama"} for i in range(6)]
    fake_http(FakeResponse({"timeline": raw}))
    arg = {"screenname": "sama"} if tool_name == "timeline" else {"query": "AI"}
    result = TOOL_FUNCTIONS[tool_name](**arg, limit=-1)
    assert len(result["items"]) == 1


from datetime import date  # noqa: E402

import requests  # noqa: E402

from tools.top_papers.tool import _months_ago  # noqa: E402

OPENALEX_WORK = {
    "id": "https://openalex.org/W1",
    "doi": "https://doi.org/10.1000/xyz",
    "title": "A Survey of Agents",
    "publication_date": "2026-05-09",
    "cited_by_count": 812,
    "primary_location": {
        "landing_page_url": "https://example.org/paper",
        "source": {"display_name": "Nature", "type": "journal"},
    },
    "authorships": [{"author": {"display_name": f"Author {i}"}} for i in range(7)],
}


def test_top_papers_sends_date_venue_sort_filters_and_maps_results(fake_http) -> None:
    calls = fake_http(FakeResponse({"meta": {"count": 1234}, "results": [OPENALEX_WORK]}))

    result = TOOL_FUNCTIONS["top_papers"](query="AI agents", months=9, venue_type="all", limit=10)

    params = calls[0]["params"]
    from_date = _months_ago(date.today(), 9).isoformat()
    assert calls[0]["url"] == "https://api.openalex.org/works"
    assert params["search"] == "AI agents"
    assert params["sort"] == "cited_by_count:desc"
    assert params["per_page"] == 10
    assert f"from_publication_date:{from_date}" in params["filter"]
    assert f"to_publication_date:{date.today().isoformat()}" in params["filter"]
    assert "primary_location.source.type:journal|conference" in params["filter"]
    assert result["from_date"] == from_date
    assert result["total_matches"] == 1234
    item = result["items"][0]
    assert item["title"] == "A Survey of Agents"
    assert item["venue"] == "Nature" and item["venue_type"] == "journal"
    assert item["cited_by_count"] == 812
    assert item["url"] == "https://doi.org/10.1000/xyz"
    assert item["authors"] == [f"Author {i}" for i in range(5)]  # capped at 5


def test_top_papers_bad_input_from_model_is_normalised(fake_http) -> None:
    calls = fake_http(FakeResponse({"results": []}))

    result = TOOL_FUNCTIONS["top_papers"](
        query="   ", months="nine", venue_type="Workshop", limit=500, sort_by="hot", source="google",
    )

    params = calls[0]["params"]
    assert calls[0]["url"] == "https://api.openalex.org/works"  # unknown source -> openalex
    assert "search" not in params  # blank query -> no keyword filter
    assert params["per_page"] == 25  # limit clamped
    assert params["sort"] == "cited_by_count:desc"  # unknown sort -> citations
    assert result["months"] == 9  # non-numeric -> default
    assert result["venue_type"] == "all"  # out-of-enum -> all
    assert result["sort_by"] == "citations" and result["source"] == "openalex"
    assert "primary_location.source.type:journal|conference" in params["filter"]
    assert result["items"] == []


def test_top_papers_conference_only_filter_and_string_months(fake_http) -> None:
    calls = fake_http(FakeResponse({"results": []}))
    TOOL_FUNCTIONS["top_papers"](query="LLM", venue_type="conference", months="3")
    assert "primary_location.source.type:conference" in calls[0]["params"]["filter"]
    assert f"from_publication_date:{_months_ago(date.today(), 3).isoformat()}" in calls[0]["params"]["filter"]


def test_top_papers_http_error_returns_error_dict(fake_http) -> None:
    fake_http(FakeResponse(status_code=429))
    result = TOOL_FUNCTIONS["top_papers"](query="LLM")
    assert result["tool"] == "top_papers"
    assert result["error"] == "HTTPError"
    assert "429" in result["message"]


def test_top_papers_timeout_returns_error_dict(fake_http) -> None:
    fake_http(requests.Timeout("timed out"))
    result = TOOL_FUNCTIONS["top_papers"](query="LLM")
    assert result["error"] == "Timeout"


def test_top_papers_openalex_sort_options_map_to_api_sort(fake_http) -> None:
    calls = fake_http(FakeResponse({"results": []}))
    TOOL_FUNCTIONS["top_papers"](query="LLM", sort_by="relevance")
    TOOL_FUNCTIONS["top_papers"](query="LLM", sort_by="newest", limit="5", months=12)
    assert calls[0]["params"]["sort"] == "relevance_score:desc"
    assert calls[1]["params"]["sort"] == "publication_date:desc"
    assert calls[1]["params"]["per_page"] == 5
    assert f"from_publication_date:{_months_ago(date.today(), 12).isoformat()}" in calls[1]["params"]["filter"]


def test_top_papers_relevance_without_query_falls_back_to_citations(fake_http) -> None:
    calls = fake_http(FakeResponse({"results": []}))
    result = TOOL_FUNCTIONS["top_papers"](query="", sort_by="relevance")
    assert calls[0]["params"]["sort"] == "cited_by_count:desc"
    assert result["sort_by"] == "citations"
    assert "fell back" in result["note"]


S2_PAPER = {
    "paperId": "abc",
    "title": "Agents at Scale",
    "venue": "NeurIPS",
    "publicationDate": "2026-06-01",
    "citationCount": 321,
    "authors": [{"name": "Ann"}, {"name": "Bob"}],
    "externalIds": {"DOI": "10.5555/agents"},
    "url": "https://www.semanticscholar.org/paper/abc",
    "publicationTypes": ["Conference"],
}


def test_top_papers_semantic_scholar_citations_uses_bulk_sort_and_maps_results(fake_http) -> None:
    calls = fake_http(FakeResponse({"total": 77, "data": [S2_PAPER, S2_PAPER, S2_PAPER]}))

    result = TOOL_FUNCTIONS["top_papers"](query="AI agents", source="semantic_scholar", venue_type="conference", limit=2)

    params = calls[0]["params"]
    from_date = _months_ago(date.today(), 9).isoformat()
    assert calls[0]["url"] == "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    assert params["query"] == "AI agents"
    assert params["sort"] == "citationCount:desc"
    assert params["publicationTypes"] == "Conference"
    assert params["publicationDateOrYear"] == f"{from_date}:{date.today().isoformat()}"
    assert calls[0]["headers"] == {}  # no key -> no x-api-key header
    assert len(result["items"]) == 2  # bulk returns many rows, trimmed to limit
    assert result["total_matches"] == 77
    item = result["items"][0]
    assert item["venue"] == "NeurIPS" and item["venue_type"] == "conference"
    assert item["cited_by_count"] == 321
    assert item["url"] == "https://doi.org/10.5555/agents"
    assert item["source"] == "semanticscholar.org"


def test_top_papers_semantic_scholar_relevance_uses_search_endpoint_with_key(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "s2-key")
    calls = fake_http(FakeResponse({"total": 1, "data": [S2_PAPER]}))

    TOOL_FUNCTIONS["top_papers"](query="LLM", source="semantic_scholar", sort_by="relevance", limit=7)

    assert calls[0]["url"] == "https://api.semanticscholar.org/graph/v1/paper/search"
    assert calls[0]["params"]["limit"] == 7
    assert "sort" not in calls[0]["params"]
    assert calls[0]["params"]["publicationTypes"] == "JournalArticle,Conference"
    assert calls[0]["headers"] == {"x-api-key": "s2-key"}


def test_top_papers_semantic_scholar_rate_limit_returns_error_dict(fake_http) -> None:
    fake_http(FakeResponse(status_code=429))
    result = TOOL_FUNCTIONS["top_papers"](query="LLM", source="semantic_scholar")
    assert result["tool"] == "top_papers"
    assert result["error"] == "HTTPError"


def test_months_ago_clamps_to_end_of_month() -> None:
    assert _months_ago(date(2026, 11, 30), 9) == date(2026, 2, 28)
    assert _months_ago(date(2026, 3, 15), 9) == date(2025, 6, 15)


# ---------------- paper_references (team tool #2) ----------------

from tools.paper_references import tool as refs_tool  # noqa: E402

BRACKET_PAGES = [
    "Intro text\nConclusion.",
    "Acknowledgements.\nReferences\n[1] A. Author and B. Author. First paper. In NeurIPS,\n2017.\n"
    "[2] C. Author. Second paper. arXiv\npreprint arXiv:1234.56789, 2016.\n10",
    "[3] D. Author. Third paper con-\ntinued here. 2015.\n[4] E. Author. Fourth. 2014.",
    "Attention Visualizations\nFigure 3: some caption text that is not a reference.",
]

AUTHOR_YEAR_PAGES = [
    "References\nAlan Akbik, Duncan Blythe, and Roland Vollgraf.\n2018. Contextual string embeddings. In COLING.\n"
    "Z. Chen, H. Zhang, and L. Zhao. 2018. Quora question pairs.\n"
    "Wilson L Taylor. 1953. Cloze procedure. Journalism Bulletin.\n"
    "A Additional Details for BERT\nAppendix text.",
]


def test_paper_references_parse_bracket_keeps_numbers_and_page_line_positions() -> None:
    parsed = refs_tool.parse_references(BRACKET_PAGES)

    assert parsed["style"] == "bracket"
    assert (parsed["heading_page"], parsed["heading_line"]) == (2, 2)
    assert [e["number"] for e in parsed["entries"]] == [1, 2, 3, 4]  # stops before the figure page
    first, third = parsed["entries"][0], parsed["entries"][2]
    assert first["text"] == "A. Author and B. Author. First paper. In NeurIPS, 2017."
    assert (first["page_start"], first["line_start"], first["page_end"], first["line_end"]) == (2, 3, 2, 4)
    assert third["text"] == "D. Author. Third paper continued here. 2015."  # hyphenation re-joined
    assert (third["page_start"], third["line_start"]) == (3, 1)


def test_paper_references_parse_author_year_splits_initials_and_single_author() -> None:
    parsed = refs_tool.parse_references(AUTHOR_YEAR_PAGES)

    assert parsed["style"] == "author_year"
    texts = [e["text"] for e in parsed["entries"]]
    assert len(texts) == 3  # stops at "A Additional Details" appendix heading
    assert texts[0].startswith("Alan Akbik") and texts[0].endswith("In COLING.")
    assert texts[1].startswith("Z. Chen")
    assert texts[2].startswith("Wilson L Taylor. 1953.")


def test_paper_references_parse_without_heading_returns_no_entries() -> None:
    parsed = refs_tool.parse_references(["Just a page.", "No bibliography here."])
    assert parsed["entries"] == [] and parsed["style"] is None


def test_paper_references_arxiv_pdf_returns_requested_range(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(refs_tool, "_arxiv_pdf_path", lambda arxiv_id: (tmp_path / "x.pdf", f"https://arxiv.org/pdf/{arxiv_id}.pdf"))
    monkeypatch.setattr(refs_tool, "_pdf_pages", lambda path: BRACKET_PAGES)

    result = TOOL_FUNCTIONS["paper_references"](paper="https://arxiv.org/abs/1706.03762v7", start=2, end=3)

    assert result["paper_id"] == "1706.03762v7"
    assert result["total_references"] == 4
    assert [item["number"] for item in result["items"]] == [2, 3]
    assert result["items"][0]["line_start"] == 5


def test_paper_references_bad_input_from_model_is_normalised(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(refs_tool, "_arxiv_pdf_path", lambda arxiv_id: (tmp_path / "x.pdf", ""))
    monkeypatch.setattr(refs_tool, "_pdf_pages", lambda path: BRACKET_PAGES)

    result = TOOL_FUNCTIONS["paper_references"](paper="1706.03762", start="zero", end=-5, source="scholar")
    assert (result["start"], result["end"], result["source"]) == (1, 1, "arxiv_pdf")
    assert [item["number"] for item in result["items"]] == [1]

    wide = TOOL_FUNCTIONS["paper_references"](paper="1706.03762", start=3, end=999)
    assert wide["end"] == 52  # span capped at 50


def test_paper_references_empty_or_non_arxiv_paper_returns_error_without_network(fake_http) -> None:
    calls = fake_http(FakeResponse({}))

    empty = TOOL_FUNCTIONS["paper_references"](paper="  ")
    not_arxiv = TOOL_FUNCTIONS["paper_references"](paper="Attention is all you need", source="arxiv_pdf")

    assert empty["error"] == "ValueError" and "paper is required" in empty["message"]
    assert not_arxiv["error"] == "ValueError" and "openalex" in not_arxiv["message"]
    assert calls == []


def test_paper_references_openalex_resolves_arxiv_doi_and_keeps_slice_order(monkeypatch) -> None:
    calls: list[dict] = []
    work = {"id": "https://openalex.org/W1", "title": "Attention Is All You Need", "publication_year": 2017,
            "referenced_works": [f"https://openalex.org/W{n}" for n in range(100, 105)]}
    details = {"results": [  # API returns them in arbitrary order
        {"id": "https://openalex.org/W102", "title": "Ref C", "doi": "https://doi.org/10.1/c", "publication_year": 2015,
         "authorships": [{"author": {"display_name": "Cara"}}], "primary_location": {"source": {"display_name": "ICML"}}},
        {"id": "https://openalex.org/W101", "title": "Ref B", "doi": None, "publication_year": 2014,
         "authorships": [], "primary_location": None},
    ]}

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse(work if len(calls) == 1 else details)

    monkeypatch.setattr(requests, "get", fake_get)
    result = TOOL_FUNCTIONS["paper_references"](paper="arXiv:1706.03762", source="openalex", start=2, end=3)

    assert calls[0]["url"] == "https://api.openalex.org/works/doi:10.48550/arXiv.1706.03762"
    assert calls[1]["params"]["filter"] == "openalex_id:W101|W102"
    assert result["total_references"] == 5
    assert [(i["number"], i["text"]) for i in result["items"]] == [(2, "Ref B"), (3, "Ref C")]
    assert result["items"][1]["venue"] == "ICML" and result["items"][1]["line_start"] is None


def test_paper_references_openalex_http_error_returns_error_dict(fake_http) -> None:
    fake_http(FakeResponse(status_code=404))
    result = TOOL_FUNCTIONS["paper_references"](paper="10.1000/missing", source="openalex")
    assert result["tool"] == "paper_references"
    assert result["error"] == "HTTPError" and "404" in result["message"]
