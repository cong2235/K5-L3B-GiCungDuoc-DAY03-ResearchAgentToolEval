"""Offline tests for the Telegram bot UI (bot.py): no Telegram, no model, no network."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import bot as bot_module
from providers.base import ModelResponse, ToolCall

ROOT = Path(__file__).resolve().parents[1]


class ScriptedProvider:
    """Returns the scripted responses in order, one per `complete` call."""

    def __init__(self, responses: list[ModelResponse | Exception]) -> None:
        self.responses = list(responses)
        self.seen_messages: list[list[dict]] = []

    def complete(self, messages, tools=None, *, model=None, temperature=0.0, tool_choice=None) -> ModelResponse:
        self.seen_messages.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_bot(monkeypatch, tmp_path, responses, allowed: str = ""):
    provider = ScriptedProvider(responses)
    monkeypatch.setattr(bot_module, "make_provider", lambda name: provider)
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", allowed)
    replies: list[tuple[int, str]] = []
    args = argparse.Namespace(
        provider="openrouter", model="fake-model", version="vtest",
        system_prompt=ROOT / "artifacts" / "system_prompt.md", tools=ROOT / "artifacts" / "tools.yaml",
        transcripts_dir=tmp_path, history_window=5, max_tool_rounds=4,
    )
    bot = bot_module.ResearchBot(args, reply=lambda chat_id, text: replies.append((chat_id, text)), typing=lambda chat_id: None)
    return bot, provider, replies


def message(text: str, chat_id: int = 42) -> dict:
    return {"chat": {"id": chat_id}, "from": {"first_name": "Tester", "username": "secret_handle"}, "text": text}


def test_bot_clarify_then_answer_keeps_history_and_writes_transcript(monkeypatch, tmp_path) -> None:
    bot, provider, replies = make_bot(monkeypatch, tmp_path, [
        ModelResponse(text=None, tool_calls=[ToolCall("clarify", {"question": "Bạn muốn xem tài khoản nào?"})]),
        ModelResponse(text="Đây là tweet mới nhất của Karpathy.", tool_calls=[]),
    ])

    bot.handle_message(message("Tweet mới nhất là gì?"))
    bot.handle_message(message("Của Andrej Karpathy"))

    assert replies == [(42, "Bạn muốn xem tài khoản nào?"), (42, "Đây là tweet mới nhất của Karpathy.")]
    second_call = provider.seen_messages[1]
    assert {"role": "assistant", "content": "Bạn muốn xem tài khoản nào?"} in second_call  # history carried
    transcript = json.loads(next(tmp_path.glob("telegram_vtest_42_*.transcript.json")).read_text(encoding="utf-8"))
    assert transcript["ui"] == "telegram" and len(transcript["turns"]) == 2
    assert transcript["turns"][0]["status"] == "waiting_for_user"
    assert "secret_handle" not in json.dumps(transcript)  # no Telegram username in the log


def test_bot_provider_error_is_shown_not_hidden(monkeypatch, tmp_path) -> None:
    bot, _, replies = make_bot(monkeypatch, tmp_path, [RuntimeError("429 rate limit")])

    bot.handle_message(message("Tin AI hôm nay?"))

    assert "Lỗi khi gọi model" in replies[0][1] and "429 rate limit" in replies[0][1]
    transcript = json.loads(next(tmp_path.glob("*.transcript.json")).read_text(encoding="utf-8"))
    assert transcript["turns"][0]["status"] == "provider_error"


def test_bot_reset_and_help_commands_do_not_call_model(monkeypatch, tmp_path) -> None:
    bot, provider, replies = make_bot(monkeypatch, tmp_path, [])

    bot.handle_message(message("/start"))
    bot.handle_message(message("/reset@MyBot"))

    assert "Research Agent" in replies[0][1]
    assert "xoá lịch sử" in replies[1][1]
    assert provider.seen_messages == []


def test_bot_allowlist_blocks_other_chats(monkeypatch, tmp_path) -> None:
    bot, provider, replies = make_bot(monkeypatch, tmp_path, [], allowed="111, -100222")

    bot.handle_message(message("Tin AI hôm nay?", chat_id=42))

    assert "chỉ dành cho nhóm" in replies[0][1]
    assert provider.seen_messages == []
    assert bot.allowed == {111, -100222}


@pytest.mark.parametrize("length", [10, 4000, 9001])
def test_telegram_send_text_splits_long_messages(monkeypatch, length) -> None:
    sent: list[str] = []
    api = bot_module.TelegramAPI("token")
    monkeypatch.setattr(api, "call", lambda method, **payload: sent.append(payload["text"]))

    api.send_text(1, "x" * length)

    assert "".join(sent) == "x" * length
    assert all(len(chunk) <= 4000 for chunk in sent)
