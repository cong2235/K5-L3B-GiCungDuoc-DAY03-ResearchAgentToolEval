from __future__ import annotations

import os
from typing import Any

import requests

from tools._shared import TIMEOUT, err


MAX_TELEGRAM_CHARS = 4096


def send_telegram(text: str = "", confirmed: bool = False) -> dict[str, Any]:
    # Strict: only the JSON boolean true counts. A truthy string such as "false" or "yes"
    # must NOT bypass the confirmation guardrail.
    if confirmed is not True:
        return {
            "tool": "send_telegram",
            "status": "needs_confirmation",
            "message": "Only send after the user explicitly confirms.",
        }
    try:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must not be empty")
        if len(text) > MAX_TELEGRAM_CHARS:
            raise ValueError(f"text is {len(text)} characters; Telegram allows at most {MAX_TELEGRAM_CHARS}")
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID env var")
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return {"tool": "send_telegram", "status": "sent"}
    except Exception as exc:
        return err("send_telegram", exc)

