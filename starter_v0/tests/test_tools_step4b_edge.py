"""Step 4b (Challenge+) - edge-case inputs that models really send, and the bugs they exposed.

Every test here either failed against the original starter tools or pins a behaviour decision
(noted in the docstring). Each test checks ONE behaviour and asserts both the request that is
sent (or that no request is sent) and the value the tool returns.

Bugs found (details in the group report, B5):
 1. send(confirmed="false") sent the message: a truthy string bypassed the confirmation guardrail.
 2. send(text="") / whitespace / >4096 chars hit Telegram instead of failing fast.
 3. fetch("") / "not a url" / "javascript:..." spent a Firecrawl credit.
 4. lookup / timeline / social_search / papers sent empty queries to paid or rate-limited APIs.
 5. lookup(max_results=-2) and out-of-enum topic / search_type were forwarded to the API.
 6. timeline("@sama") sent the '@' although the handle convention is "no @".
 7. timeline(limit="abc") raised ValueError after the HTTP request had already been made.
 8. format(items="oops") raised AttributeError instead of returning an error dict.
"""
from __future__ import annotations

import pytest

from conftest import FakeResponse
from tools import TOOL_FUNCTIONS

send = TOOL_FUNCTIONS["send"]
fetch = TOOL_FUNCTIONS["fetch"]
lookup = TOOL_FUNCTIONS["lookup"]
timeline = TOOL_FUNCTIONS["timeline"]
social_search = TOOL_FUNCTIONS["social_search"]
format_tool = TOOL_FUNCTIONS["format"]
papers = TOOL_FUNCTIONS["papers"]
policy = TOOL_FUNCTIONS["policy"]


def _tweets(n: int = 8) -> dict:
    return {"timeline": [{"tweet_id": str(i), "text": f"t{i}", "screen_name": "sama"} for i in range(n)]}


@pytest.fixture
def telegram_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-10042")


# ---------------------------------------------------------------- send (guardrail)

@pytest.mark.parametrize("flag", ["false", "False", "no", "yes", "true", "1", 1, "0", None, [], {}])
def test_send_only_the_boolean_true_counts_as_confirmation(flag, telegram_env, fake_http) -> None:
    """Bug 1: `if not confirmed` treated the string "false" as confirmed and posted the message."""
    calls = fake_http(FakeResponse({"ok": True}))
    result = send(text="Bản tin", confirmed=flag)
    assert result["status"] == "needs_confirmation"
    assert calls == []


@pytest.mark.parametrize("text", ["", "   ", "\n\t", None, 123])
def test_send_blank_or_non_string_text_returns_error_and_no_request(text, telegram_env, fake_http) -> None:
    calls = fake_http(FakeResponse({"ok": True}))
    result = send(text=text, confirmed=True)
    assert result["error"] == "ValueError"
    assert "empty" in result["message"]
    assert calls == []


def test_send_text_over_telegram_limit_returns_error_and_no_request(telegram_env, fake_http) -> None:
    calls = fake_http(FakeResponse({"ok": True}))
    result = send(text="x" * 4097, confirmed=True)
    assert result["error"] == "ValueError"
    assert "4096" in result["message"]
    assert calls == []


def test_send_text_of_exactly_telegram_limit_is_sent(telegram_env, fake_http) -> None:
    calls = fake_http(FakeResponse({"ok": True}))
    result = send(text="x" * 4096, confirmed=True)
    assert result["status"] == "sent"
    assert len(calls) == 1 and len(calls[0]["json"]["text"]) == 4096


def test_send_http_error_does_not_report_sent(telegram_env, fake_http) -> None:
    fake_http(FakeResponse(status_code=400))
    result = send(text="hello", confirmed=True)
    assert result["error"] == "HTTPError"
    assert result.get("status") != "sent"


# ---------------------------------------------------------------- fetch

@pytest.mark.parametrize("url", ["", "   ", "not a url", "javascript:alert(1)", "ftp://example.com/f", "//example.com", None])
def test_fetch_rejects_non_http_urls_without_spending_a_request(url, monkeypatch, fake_http) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc")
    calls = fake_http(FakeResponse({"data": {}}))
    result = fetch(url=url)
    assert result["error"] == "ValueError"
    assert calls == []


def test_fetch_strips_whitespace_around_the_url(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc")
    calls = fake_http(FakeResponse({"data": {"markdown": "body", "metadata": {}}}))
    fetch(url="  https://example.com/a  ")
    assert calls[0]["json"]["url"] == "https://example.com/a"


# ---------------------------------------------------------------- lookup

@pytest.mark.parametrize("query", ["", "   ", None])
def test_lookup_empty_query_returns_error_and_no_request(query, monkeypatch, fake_http) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    calls = fake_http(FakeResponse({"results": []}))
    assert lookup(query=query)["error"] == "ValueError"
    assert calls == []


@pytest.mark.parametrize("given, sent", [(0, 1), (-2, 1), (3, 3), ("3", 3), (999, 20), ("abc", 5), (None, 5)])
def test_lookup_max_results_is_coerced_into_1_to_20(given, sent, monkeypatch, fake_http) -> None:
    """Decision: 0 / negative -> 1 (the smallest valid page), garbage -> default 5, huge -> 20."""
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    calls = fake_http(FakeResponse({"results": []}))
    lookup(query="ai", max_results=given)
    assert calls[0]["json"]["max_results"] == sent


def test_lookup_out_of_enum_topic_and_timeframe_fall_back_to_defaults(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    calls = fake_http(FakeResponse({"results": []}))
    result = lookup(query="ai", topic="sports", timeframe="decade")
    assert calls[0]["json"]["topic"] == "general"
    assert calls[0]["json"]["time_range"] == "week"
    assert (result["topic"], result["timeframe"]) == ("general", "week")


def test_lookup_enum_values_are_case_insensitive(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    calls = fake_http(FakeResponse({"results": []}))
    lookup(query="ai", topic="NEWS", timeframe="Day")
    assert (calls[0]["json"]["topic"], calls[0]["json"]["time_range"]) == ("news", "day")


# ---------------------------------------------------------------- timeline

@pytest.mark.parametrize("handle", ["", "   ", "@", None])
def test_timeline_empty_handle_returns_error_and_no_request(handle, monkeypatch, fake_http) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    calls = fake_http(FakeResponse(_tweets()))
    assert timeline(screenname=handle)["error"] == "ValueError"
    assert calls == []


@pytest.mark.parametrize("given", ["@sama", " @sama ", "sama"])
def test_timeline_strips_at_sign_so_the_api_receives_a_bare_handle(given, monkeypatch, fake_http) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    calls = fake_http(FakeResponse(_tweets()))
    result = timeline(screenname=given)
    assert calls[0]["params"] == {"screenname": "sama"}
    assert result["screenname"] == "sama"


@pytest.mark.parametrize("given, expected_items", [(0, 1), (-1, 1), ("2", 2), ("abc", 5), (None, 5), (999, 8)])
def test_timeline_limit_is_coerced_and_never_raises(given, expected_items, monkeypatch, fake_http) -> None:
    """Bug 7: limit="abc" raised after the request. Decision: 0/negative -> 1, garbage -> 5."""
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    calls = fake_http(FakeResponse(_tweets(8)))
    result = timeline(screenname="sama", limit=given)
    assert "error" not in result
    assert len(result["items"]) == expected_items
    assert len(calls) == 1


# ---------------------------------------------------------------- social_search

@pytest.mark.parametrize("query", ["", "  ", None])
def test_social_search_empty_query_returns_error_and_no_request(query, monkeypatch, fake_http) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    calls = fake_http(FakeResponse(_tweets()))
    assert social_search(query=query)["error"] == "ValueError"
    assert calls == []


@pytest.mark.parametrize("given, sent", [("Hot", "Latest"), ("top", "Top"), ("LATEST", "Latest"), (None, "Latest")])
def test_social_search_search_type_is_normalised_to_the_enum(given, sent, monkeypatch, fake_http) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    calls = fake_http(FakeResponse(_tweets()))
    result = social_search(query="ai", search_type=given)
    assert calls[0]["params"]["search_type"] == sent
    assert result["search_type"] == sent


def test_social_search_limit_zero_returns_one_item_not_the_default(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    fake_http(FakeResponse(_tweets(8)))
    assert len(social_search(query="ai", limit=0)["items"]) == 1


# ---------------------------------------------------------------- format

@pytest.mark.parametrize("bad", ["oops", 42, {"title": "x"}])
def test_format_non_list_items_returns_error_dict_instead_of_raising(bad) -> None:
    """Bug 8: format(items="oops") raised AttributeError."""
    result = format_tool(items=bad, template="bullets")
    assert result["error"] == "TypeError"


def test_format_skips_entries_that_are_not_objects() -> None:
    result = format_tool(items=[None, 5, "x", {"title": "ok", "url": "https://a.com/1"}], template="bullets")
    assert result["item_count"] == 1
    assert "ok" in result["markdown"] and "a.com" in result["markdown"]


def test_format_unknown_template_falls_back_to_sections() -> None:
    result = format_tool(items=[{"title": "t", "section": "S"}], template="weird")
    assert "## S" in result["markdown"]


# ---------------------------------------------------------------- papers / policy

@pytest.mark.parametrize("query", ["", "   ", None])
def test_papers_empty_query_returns_error_and_no_request(query, fake_http) -> None:
    calls = fake_http(FakeResponse(text=""))
    assert papers(query=query)["error"] == "ValueError"
    assert calls == []


def test_policy_none_query_returns_no_results_instead_of_an_attribute_error() -> None:
    result = policy(query=None)
    assert "error" not in result
    assert result["results"] == []


@pytest.mark.parametrize("given, expected", [(2, 2), ("2", 2), (-1, 1), (0, 3)])
def test_policy_top_k_boundaries(given, expected) -> None:
    """Pins existing behaviour: top_k=0 means 'unset' -> default 3; negative -> at least 1."""
    assert len(policy(query="privacy data", top_k=given)["results"]) == expected
