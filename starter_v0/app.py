"""Streamlit UI for the Research Agent. Put this file next to chat.py.

Run:          streamlit run app.py
Public link:  cloudflared tunnel --url http://localhost:8501
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime

import streamlit as st

from chat import (
    ARTIFACTS_DIR,
    ROOT,
    now_iso,
    run_model_tool_loop,
    safe_slug,
    trim_history,
    write_transcript,
)
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version

TRANSCRIPTS_DIR = ROOT / "transcripts"

# label -> (provider, model, short description). "Tùy chỉnh" lets you type anything.
MODEL_PRESETS = {
    "GPT-4o mini · OpenRouter": ("openrouter", "openai/gpt-4o-mini", "Cloud · nhanh, gọi tool ổn định"),
    "Gemma 4 E2B · Ollama local": ("ollama", "gemma4:e2b", "Model local qua Ollama (OLLAMA_BASE_URL)"),
}
CUSTOM_LABEL = "Tùy chỉnh…"
PROVIDERS = ["openrouter", "openai", "anthropic", "gemini", "ollama"]

EXAMPLES = {
    "🐦 Mạng xã hội": [
        "Tweet mới nhất của Sam Altman là gì?",
        "Lấy 5 tweet mới nhất của Andrej Karpathy",
        "Cho mình các tweet phổ biến nhất về OpenAI",
    ],
    "🌐 Web & cộng đồng": [
        "Tin tức AI hôm nay có gì nổi bật?",
        "Dân tech bàn gì về LLM agents trên Hacker News?",
        "Transformer là gì?",
    ],
    "🎓 Nghiên cứu": [
        "Top 5 bài báo được trích dẫn nhiều nhất về AI agents trong 6 tháng qua",
        "Liệt kê tài liệu tham khảo từ số 5 tới 10 của paper arXiv 1706.03762",
        "Tìm preprint arXiv mới nhất về diffusion models",
    ],
    "✅ Hành vi đúng": [
        "Tóm tắt 5 tweet mới nhất giúp mình",
        "Tóm tắt bài viết này hộ mình",
        "Đăng bản tin này lên Telegram giúp mình",
    ],
}

TOOL_ICONS = {
    "timeline": "🐦", "social_search": "🔍", "lookup": "🌐", "fetch": "📄",
    "hackernews": "🟧", "wikipedia": "📚", "openalex": "🎓", "top_papers": "🏆",
    "papers": "📑", "paper_text": "📖", "paper_references": "🔗", "send": "📤",
    "clarify": "❓", "format": "🧾", "policy": "🛡️",
}

RESET_KEYS = ("messages", "history", "transcript", "transcript_path", "pending", "queued")

st.set_page_config(page_title="Research Agent", page_icon="🔎", layout="centered")
st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; max-width: 900px;}
      .hero {padding: 1.4rem 1.6rem; border-radius: 18px; margin-bottom: 1.2rem;
             background: linear-gradient(135deg, rgba(79,70,229,.16), rgba(14,165,233,.12));
             border: 1px solid rgba(99,102,241,.25);}
      .hero h1 {font-size: 1.9rem; margin: 0 0 .25rem 0; padding: 0;}
      .hero p {margin: 0; opacity: .8;}
      .chip {display:inline-block; padding:3px 11px; border-radius:999px; font-size:.78rem;
             margin:.5rem .35rem 0 0; background: rgba(99,102,241,.14);
             border: 1px solid rgba(99,102,241,.25);}
      .group-title {font-weight: 600; font-size: .95rem; margin: .2rem 0 .4rem 0;}
      .tool-badge {display:inline-block; padding:2px 10px; border-radius:12px;
                   background: rgba(120,120,120,.15); font-size:.85rem; margin-right:6px;}
      .item-title {font-weight:600;}
      .muted {opacity:.65; font-size:.85rem;}
      .status {font-size:.82rem; padding:.45rem .7rem; border-radius:10px; margin-top:.3rem;}
      .status.ok {background: rgba(34,197,94,.13); border:1px solid rgba(34,197,94,.3);}
      .status.bad {background: rgba(239,68,68,.12); border:1px solid rgba(239,68,68,.3);}
      div[data-testid="stButton"] button {text-align: left; border-radius: 12px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------- callbacks (run BEFORE the script reruns, so no st.rerun needed) ----------------
def queue(text: str) -> None:
    st.session_state.queued = text


def reset_chat() -> None:
    for k in RESET_KEYS:
        st.session_state.pop(k, None)


@st.cache_data(ttl=15, show_spinner=False)
def ollama_status(model_name: str) -> tuple[bool, str]:
    """Ping the Ollama server behind OLLAMA_BASE_URL and check the model is pulled."""
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    root = base[:-3] if base.endswith("/v1") else base
    try:
        with urllib.request.urlopen(f"{root}/api/tags", timeout=3) as r:
            names = [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return False, f"Không kết nối được Ollama tại {root}"
    if model_name in names or f"{model_name}:latest" in names:
        return True, f"Ollama sẵn sàng · {model_name}"
    return False, f"Ollama chạy tại {root} nhưng chưa có model {model_name} (ollama pull {model_name})"


# ---------------- sidebar: settings ----------------
with st.sidebar:
    st.markdown("### 🔎 Research Agent")
    st.button("➕ Cuộc trò chuyện mới", on_click=reset_chat, use_container_width=True, type="primary")

    choice = st.selectbox("🧠 Model", [*MODEL_PRESETS, CUSTOM_LABEL], on_change=reset_chat)
    if choice == CUSTOM_LABEL:
        provider_name = st.selectbox("Provider", PROVIDERS, on_change=reset_chat)
        model = st.text_input("Model (để trống = mặc định)", value="", on_change=reset_chat) or None
    else:
        provider_name, model, desc = MODEL_PRESETS[choice]
        st.caption(desc)

    if provider_name == "ollama":
        ok, msg = ollama_status(model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))
        st.markdown(f'<div class="status {"ok" if ok else "bad"}">{"🟢" if ok else "🔴"} {msg}</div>',
                    unsafe_allow_html=True)

    with st.expander("⚙️ Nâng cao", expanded=False):
        version = st.text_input("Version label", value="v3")
        window = st.number_input("History window", 1, 10, 5)
        st.caption("Đổi model sẽ tự mở cuộc trò chuyện mới.")


@st.cache_resource
def get_provider(name: str):
    return make_provider(name)


def init_session() -> None:
    ss = st.session_state
    if "messages" in ss:
        return
    sp_path = ARTIFACTS_DIR / "system_prompt.md"
    tools_path = ARTIFACTS_DIR / "tools.yaml"
    av = build_artifact_version(version, sp_path, tools_path)
    tid = "_".join(
        [safe_slug(version), safe_slug(provider_name), datetime.now().strftime("%Y%m%dT%H%M%S%f")]
    )
    ss.messages = []  # {"role","content","events","elapsed"}
    ss.history = []  # plain user/assistant text, same as chat.py
    ss.pending = None
    ss.transcript_path = TRANSCRIPTS_DIR / f"{tid}.transcript.json"
    ss.transcript = {
        "transcript_id": tid,
        **artifact_version_dict(av),
        "provider": provider_name,
        "model": model,
        "system_prompt": str(sp_path),
        "tools": str(tools_path),
        "history_window": int(window),
        "max_tool_rounds": 4,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }


def handle_user_input(user_text: str) -> None:
    init_session()
    ss = st.session_state
    system_prompt = (ARTIFACTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
    tools = to_openai_tools(load_tool_declarations(ARTIFACTS_DIR / "tools.yaml"))
    messages = [
        {"role": "system", "content": system_prompt},
        *trim_history(ss.history, int(window)),
        {"role": "user", "content": user_text},
    ]
    turn = {
        "turn_index": len(ss.transcript["turns"]) + 1,
        "started_at": now_iso(),
        "user": user_text,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }
    ss.messages.append({"role": "user", "content": user_text, "events": [], "elapsed": None})
    ss.pending = None
    t0 = time.time()
    try:
        result = run_model_tool_loop(
            provider=get_provider(provider_name),
            messages=messages,
            tools=tools,
            model=model,
            max_tool_rounds=4,
        )
        turn.update(result)
        reply = result["assistant_text"]
        ss.history += [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": reply},
        ]
        for ev in result["tool_events"]:
            res = ev.get("result", {})
            if isinstance(res, dict) and res.get("awaiting_user"):
                if (ev.get("args") or {}).get("response_type") == "yes_no":
                    ss.pending = reply
        ss.messages.append(
            {"role": "assistant", "content": reply, "events": result["tool_events"],
             "elapsed": time.time() - t0}
        )
    except Exception as exc:
        turn.update({"status": "provider_error", "error": f"{type(exc).__name__}: {exc}"})
        ss.messages.append(
            {"role": "assistant", "content": f"⚠️ Lỗi: {turn['error']}", "events": [],
             "elapsed": time.time() - t0}
        )
    turn["ended_at"] = now_iso()
    ss.transcript["turns"].append(turn)
    write_transcript(ss.transcript_path, ss.transcript)


# ---------------- rendering helpers ----------------
def short(v, n=60) -> str:
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def clean(text: str, n: int) -> str:
    text = (text or "").replace("\n", " ").replace("[", "(").replace("]", ")")
    return text if len(text) <= n else text[: n - 1] + "…"


def render_event(ev: dict) -> None:
    name = ev.get("tool", "?")
    args = ev.get("args") or {}
    res = ev.get("result")
    icon = TOOL_ICONS.get(name, "🔧")

    if name == "clarify":
        st.markdown(
            f'<span class="tool-badge">{icon} hỏi lại · {args.get("response_type", "?")}</span>',
            unsafe_allow_html=True,
        )
        return

    arg_text = ", ".join(f"{k}={short(v)}" for k, v in args.items())
    with st.expander(f"{icon} {name}({arg_text})"):
        if isinstance(res, dict) and res.get("error"):
            st.error(f"{res.get('error')}: {res.get('message', '')}")
        elif isinstance(res, dict) and res.get("status") == "needs_confirmation":
            st.warning("Chưa gửi — chờ người dùng xác nhận.")
        elif isinstance(res, dict) and res.get("items"):
            for it in res["items"][:5]:
                title = clean(it.get("title") or it.get("url") or "(không tiêu đề)", 100)
                url = it.get("url")
                head = f"[{title}]({url})" if url else title
                src = it.get("source") or ""
                st.markdown(
                    f'<span class="item-title">{head}</span> <span class="muted">{src}</span>',
                    unsafe_allow_html=True,
                )
                if it.get("summary"):
                    st.caption(clean(it["summary"], 200))
            if len(res["items"]) > 5:
                st.caption(f"… và {len(res['items']) - 5} kết quả khác")
        st.json({"args": args, "result": res}, expanded=False)


# ---------------- main flow ----------------
init_session()
prompt = st.chat_input("Hỏi về tweet, tin tức, Hacker News, Wikipedia hay bài báo khoa học…")
queued = st.session_state.pop("queued", None) or prompt
if queued:
    with st.spinner("Agent đang xử lý…"):
        handle_user_input(queued)

ss = st.session_state

# ---------------- sidebar: examples + session info ----------------
with st.sidebar:
    st.divider()
    st.markdown("**💡 Câu hỏi mẫu**")
    for gi, (group, qs) in enumerate(EXAMPLES.items()):
        with st.expander(group):
            for qi, q in enumerate(qs):
                st.button(q, key=f"side_{gi}_{qi}", on_click=queue, args=(q,),
                          use_container_width=True)
    st.divider()
    n_calls = sum(len(m["events"]) for m in ss.messages)
    c1, c2 = st.columns(2)
    c1.metric("Lượt", len(ss.transcript["turns"]))
    c2.metric("Tool calls", n_calls)
    st.caption(f"{provider_name} · {model or 'model mặc định'} · {version}")
    st.download_button(
        "⬇️ Tải transcript",
        data=json.dumps(ss.transcript, ensure_ascii=False, indent=2, default=str),
        file_name=ss.transcript_path.name,
        mime="application/json",
        use_container_width=True,
    )

# ---------------- chat area ----------------
if not ss.messages:
    chips = "".join(
        f'<span class="chip">{t}</span>'
        for t in ["🐦 X/Twitter", "🟧 Hacker News", "📚 Wikipedia", "🎓 OpenAlex",
                  "📑 arXiv", "🔗 Tài liệu tham khảo", "📤 Telegram"]
    )
    st.markdown(
        f"""<div class="hero"><h1>🔎 Research Agent</h1>
        <p>Trợ lý nghiên cứu AI/tech — tự chọn tool phù hợp và trích nguồn rõ ràng.</p>
        {chips}<p class="muted" style="margin-top:.7rem">Đang dùng: <b>{provider_name}</b> ·
        <code>{model or 'model mặc định'}</code></p></div>""",
        unsafe_allow_html=True,
    )
    st.markdown("##### Bắt đầu nhanh")
    groups = list(EXAMPLES.items())
    for row in (groups[:2], groups[2:]):
        cols = st.columns(2)
        for col, (group, qs) in zip(cols, row):
            gi = list(EXAMPLES).index(group)
            with col.container(border=True):
                st.markdown(f'<div class="group-title">{group}</div>', unsafe_allow_html=True)
                for qi, q in enumerate(qs[:2]):
                    st.button(q, key=f"empty_{gi}_{qi}", on_click=queue, args=(q,),
                              use_container_width=True)
else:
    for m in ss.messages:
        is_user = m["role"] == "user"
        with st.chat_message("user" if is_user else "assistant", avatar="🧑" if is_user else "🔎"):
            st.write(m["content"])
            for ev in m["events"]:
                render_event(ev)
            if m["elapsed"] is not None:
                n = len(m["events"])
                st.caption(f"⏱ {m['elapsed']:.1f}s" + (f" · {n} tool call" if n else ""))

    if ss.pending:
        with st.container(border=True):
            st.markdown("**Cần xác nhận trước khi gửi**")
            c1, c2 = st.columns(2)
            c1.button("✅ Đồng ý", on_click=queue, args=("Đồng ý",), use_container_width=True)
            c2.button("❌ Không", on_click=queue, args=("Không",), use_container_width=True)
