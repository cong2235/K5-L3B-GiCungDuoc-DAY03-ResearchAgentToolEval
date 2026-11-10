"""Telegram bot UI for the Research Agent.

Each Telegram chat gets its own multi-turn history and its own transcript file
(`transcripts/telegram_<version>_<chat>_<timestamp>.transcript.json`), using the exact same
model -> tool loop as `chat.py`.

Run (from starter_v0/):
    python bot.py --provider openrouter --version v4
    python bot.py --provider openrouter --model nvidia/nemotron-3-ultra-550b-a55b:free --version v4

Env (.env):
    TELEGRAM_BOT_TOKEN          required (same bot as the `send` tool is fine)
    TELEGRAM_ALLOWED_CHAT_IDS   optional, comma-separated chat ids; empty = anyone may use the bot
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests

from chat import (
    ARTIFACTS_DIR, ROOT, now_iso, run_model_tool_loop, safe_slug, trim_history, write_transcript,
)
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


TELEGRAM_MAX_CHARS = 4000  # Telegram hard limit is 4096
POLL_TIMEOUT_SECONDS = 30

HELP_TEXT = (
    "Xin chào! Mình là Research Agent.\n\n"
    "Mình có thể: xem tweet của một tài khoản, tìm bài đăng theo chủ đề, tìm tin trên web, "
    "đọc và tóm tắt một URL, tìm paper arXiv, top bài báo được trích dẫn nhiều nhất trên tạp chí/hội nghị, "
    "liệt kê tài liệu tham khảo của một paper, tra policy công ty, và làm bản tin.\n\n"
    "Thử hỏi:\n"
    "• Tin AI hôm nay có gì nổi bật?\n"
    "• Top 5 bài báo về AI agents được trích dẫn nhiều nhất trong 9 tháng qua\n"
    "• Tài liệu tham khảo từ số 1 tới 5 của paper arXiv 1706.03762\n"
    "• Tóm tắt bài này: https://openai.com/research/\n\n"
    "Lệnh: /reset xoá lịch sử hội thoại, /help xem hướng dẫn."
)


class TelegramAPI:
    def __init__(self, token: str) -> None:
        self.base = f"https://api.telegram.org/bot{token}"

    def call(self, method: str, *, timeout: float = 30, **payload: Any) -> Any:
        response = requests.post(f"{self.base}/{method}", json=payload, timeout=timeout)
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {data.get('error_code')} {data.get('description')}")
        return data["result"]

    def send_text(self, chat_id: int, text: str) -> None:
        text = text or "(không có nội dung)"
        for start in range(0, len(text), TELEGRAM_MAX_CHARS):
            # Plain text on purpose: model output is not guaranteed to be valid Telegram Markdown.
            self.call("sendMessage", chat_id=chat_id, text=text[start:start + TELEGRAM_MAX_CHARS],
                      disable_web_page_preview=True)

    def typing(self, chat_id: int) -> None:
        try:
            self.call("sendChatAction", chat_id=chat_id, action="typing")
        except Exception:
            pass


class ResearchBot:
    def __init__(self, args: argparse.Namespace, reply: Callable[[int, str], None], typing: Callable[[int], None]) -> None:
        self.args = args
        self.reply = reply
        self.typing = typing
        self.system_prompt = args.system_prompt.read_text(encoding="utf-8")
        self.tools = to_openai_tools(load_tool_declarations(args.tools))
        self.provider = make_provider(args.provider)
        self.model = args.model or getattr(self.provider, "default_model", None)
        self.artifact_version = build_artifact_version(args.version, args.system_prompt, args.tools)
        allowed = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
        self.allowed = {int(x) for x in allowed.replace(" ", "").split(",") if x.lstrip("-").isdigit()}
        self.sessions: dict[int, dict[str, Any]] = {}

    def _new_session(self, chat_id: int, user: dict[str, Any]) -> dict[str, Any]:
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        transcript_id = "_".join(["telegram", safe_slug(self.args.version), str(chat_id).lstrip("-"), timestamp])
        return {
            "history": [],
            "path": self.args.transcripts_dir / f"{transcript_id}.transcript.json",
            "transcript": {
                "transcript_id": transcript_id,
                **artifact_version_dict(self.artifact_version),
                "ui": "telegram",
                "telegram_chat_id": chat_id,
                # Only the first name is kept; no username / phone / last name in the log.
                "telegram_user_first_name": user.get("first_name"),
                "provider": self.args.provider,
                "model": self.model,
                "system_prompt": str(self.args.system_prompt),
                "tools": str(self.args.tools),
                "history_window": self.args.history_window,
                "max_tool_rounds": self.args.max_tool_rounds,
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "turns": [],
            },
        }

    def handle_message(self, message: dict[str, Any]) -> None:
        chat_id = message["chat"]["id"]
        text = (message.get("text") or "").strip()
        if not text:
            return
        if self.allowed and chat_id not in self.allowed:
            self.reply(chat_id, "Bot này chỉ dành cho nhóm. Liên hệ nhóm để được thêm quyền truy cập.")
            return
        if text.split("@")[0] in {"/start", "/help"}:
            self.reply(chat_id, HELP_TEXT)
            return
        if text.split("@")[0] == "/reset":
            self.sessions.pop(chat_id, None)
            self.reply(chat_id, "Đã xoá lịch sử hội thoại. Bắt đầu lại nhé!")
            return

        session = self.sessions.get(chat_id) or self._new_session(chat_id, message.get("from") or {})
        self.sessions[chat_id] = session
        transcript = session["transcript"]
        turn: dict[str, Any] = {
            "turn_index": len(transcript["turns"]) + 1,
            "started_at": now_iso(),
            "user": text,
            "status": "started",
            "assistant_text": None,
            "rounds": [],
            "tool_events": [],
        }
        self.typing(chat_id)
        messages = [
            {"role": "system", "content": self.system_prompt},
            *trim_history(session["history"], self.args.history_window),
            {"role": "user", "content": text},
        ]
        try:
            result = run_model_tool_loop(
                provider=self.provider, messages=messages, tools=self.tools,
                model=self.args.model, max_tool_rounds=self.args.max_tool_rounds,
            )
            turn.update(result)
            answer = result["assistant_text"] or "(agent không trả lời)"
            session["history"] += [{"role": "user", "content": text}, {"role": "assistant", "content": answer}]
        except Exception as exc:
            turn.update({"status": "provider_error", "error": f"{type(exc).__name__}: {exc}"})
            # Show the real error instead of hiding it (rubric: UI must not mask tool/provider errors).
            answer = f"⚠️ Lỗi khi gọi model: {turn['error']}"
        turn["ended_at"] = now_iso()
        transcript["turns"].append(turn)
        write_transcript(session["path"], transcript)
        self.reply(chat_id, answer)
        print(f"[chat {chat_id}] turn {turn['turn_index']} {turn['status']} -> {session['path'].name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram bot UI for the Research Agent.")
    parser.add_argument("--provider", choices=["openrouter", "openai", "anthropic", "gemini", "ollama"], required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--version", required=True, help="Artifact version label, e.g. v4.")
    parser.add_argument("--system-prompt", type=Path, default=ARTIFACTS_DIR / "system_prompt.md")
    parser.add_argument("--tools", type=Path, default=ARTIFACTS_DIR / "tools.yaml")
    parser.add_argument("--transcripts-dir", type=Path, default=ROOT / "transcripts")
    parser.add_argument("--history-window", type=int, default=5)
    parser.add_argument("--max-tool-rounds", type=int, default=4)
    args = parser.parse_args()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("Missing TELEGRAM_BOT_TOKEN in .env")
    api = TelegramAPI(token)
    me = api.call("getMe")
    api.call("deleteWebhook")  # long polling cannot run while a webhook is set
    bot = ResearchBot(args, reply=api.send_text, typing=api.typing)
    print(f"Bot @{me.get('username')} running. artifact_version={bot.artifact_version.artifact_version} model={bot.model}")
    print("Allowed chats:", sorted(bot.allowed) or "anyone", "| Ctrl+C to stop.")

    offset = None
    while True:
        try:
            # Long polling: Telegram holds the request up to POLL_TIMEOUT_SECONDS until a message arrives.
            updates = requests.post(
                f"{api.base}/getUpdates",
                json={"offset": offset, "timeout": POLL_TIMEOUT_SECONDS, "allowed_updates": ["message"]},
                timeout=POLL_TIMEOUT_SECONDS + 10,
            ).json()
            if not updates.get("ok"):
                # 409 = another bot.py instance is already polling with this token.
                print(f"getUpdates error: {updates.get('error_code')} {updates.get('description')}")
                time.sleep(5)
                continue
            for update in updates["result"]:
                offset = update["update_id"] + 1
                message = update.get("message")
                if message:
                    try:
                        bot.handle_message(message)
                    except Exception as exc:  # never let one bad message kill the bot
                        print(f"handler error: {type(exc).__name__}: {exc}")
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except requests.RequestException as exc:
            print(f"network error: {exc}; retrying in 5s")
            time.sleep(5)


if __name__ == "__main__":
    main()
