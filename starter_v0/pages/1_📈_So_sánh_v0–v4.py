"""Streamlit page: how v0 -> v4 differ (what changed, why, and what it fixed).

Everything here is read from evidence files, nothing is typed by hand:
  - artifacts/version_log.csv            hypothesis / reason / metric per version
  - runs/<version>_B_base_*.json         summary metrics + per-case PASS/FAIL
  - artifacts/history/*                  snapshots of system_prompt.md / tools.yaml per version
"""
from __future__ import annotations

import csv
import difflib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
HISTORY = ARTIFACTS / "history"
VERSIONS = ["v0", "v1", "v2", "v3", "v4"]
ARTIFACT_LABEL = {"system_prompt": "system_prompt.md", "tools": "tools.yaml"}

CASE_MEANING = {
    "R01_user_tweets_routing": "Tweet của một người → timeline, map tên → handle",
    "R02_search_tweets_routing": "Mọi người bàn gì trên Twitter → social_search",
    "R03_web_news_routing": "Tin AI hôm nay → lookup",
    "R04_read_url_routing": "Có URL thì đọc luôn, không hỏi lại",
    "R05_limit_arg": "Giữ đúng số lượng tweet (limit)",
    "R06_timeframe_arg": "Tin trong tuần → timeframe",
    "R07_search_type_arg": "Tweet phổ biến → search_type=Top",
    "R08_out_of_scope": "Bài toán tích phân → từ chối, không gọi tool",
    "R09_no_tool_capability": "Hỏi agent làm được gì → trả lời, không gọi tool",
    "R10_missing_handle": "Không nói tài khoản → hỏi lại, không đoán",
    "R11_missing_url": "Không có link → hỏi lại, không bịa URL",
    "R12_confirm_before_send": "Đăng Telegram → xác nhận yes/no trước",
    "R13_parallel_web_and_tweets": "Web + tweet song song, topic=news",
    "R14_out_of_scope_coding": "Viết code → từ chối, không gọi tool",
    "M01_clarify_then_fill": "Hỏi lại rồi điền tài khoản ở lượt sau",
    "M02_carryover_timeframe": "Giữ timeframe qua các lượt",
    "M03_correction_handle": "Sửa lại tài khoản ('à nhầm')",
    "M04_clarify_then_url": "Hỏi link rồi nhận link ở lượt sau",
    "M05_correction_limit": "Đổi số lượng ở lượt sau",
    "M06_switch_tool": "Bỏ Twitter, chuyển sang web",
}

st.markdown(
    """
    <style>
      .block-container {max-width: 1100px; padding-top: 2rem;}
      .vcard {border: 1px solid rgba(120,120,120,.28); border-radius: 14px; padding: 14px 18px; margin-bottom: 10px;}
      .vcard.best {border-color: rgba(16,185,129,.6); background: rgba(16,185,129,.07);}
      .vtitle {display:flex; align-items:baseline; gap:12px; flex-wrap:wrap;}
      .vtag {font-family: ui-monospace, monospace; font-weight: 800; font-size: 1.35rem;}
      .file {font-family: ui-monospace, monospace; font-size: .85rem; padding: 2px 8px; border-radius: 6px;
             background: rgba(99,102,241,.14);}
      .acc {margin-left:auto; font-family: ui-monospace, monospace; font-weight: 800; font-size: 1.35rem;}
      .acc.down {color: #ea580c;}
      .hash {font-family: ui-monospace, monospace; font-size: .78rem; opacity: .7;}
      .chip {display:inline-block; font-family: ui-monospace, monospace; font-size: .8rem; font-weight: 600;
             border-radius: 6px; padding: 2px 8px; margin: 6px 6px 0 0;}
      .chip.ok {background: rgba(16,185,129,.16); color: #047857;}
      .chip.bad {background: rgba(234,88,12,.16); color: #c2410c;}
      .lbl {font-size: .78rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; opacity: .6; margin-top: 8px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------- data ----------------
@st.cache_data(show_spinner=False)
def load_evidence() -> tuple[dict, dict, dict]:
    log = {row["version"]: row for row in csv.DictReader((ARTIFACTS / "version_log.csv").open(encoding="utf-8"))}
    runs, cases = {}, {}
    for version in VERSIONS:
        run_file = (log.get(version) or {}).get("run_file", "")
        path = ROOT / run_file if run_file else None
        if not path or not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        runs[version] = {**data["summary"], "model": data.get("model"),
                         "prompt_hash": data.get("prompt_hash", "")[:12], "tools_hash": data.get("tools_hash", "")[:12],
                         "run_file": run_file}
        for result in data["results"]:
            case_id = result.get("id") or result.get("case_id")
            cases.setdefault(case_id, {})[version] = bool(result["result"].get("passed"))
    manifest = json.loads((HISTORY / "manifest.json").read_text(encoding="utf-8"))
    return log, runs, {"cases": cases, "manifest": manifest}


log, runs, extra = load_evidence()
cases: dict[str, dict[str, bool]] = extra["cases"]
manifest: dict = extra["manifest"]
available = [v for v in VERSIONS if v in runs]


def fixed_and_broken(version: str) -> tuple[list[str], list[str]]:
    index = available.index(version)
    if index == 0:
        return [], [c.split("_")[0] for c, r in cases.items() if not r.get(version, True)]
    previous = available[index - 1]
    fixed = [c.split("_")[0] for c, r in cases.items() if not r.get(previous) and r.get(version)]
    broken = [c.split("_")[0] for c, r in cases.items() if r.get(previous) and not r.get(version)]
    return fixed, broken


# ---------------- header ----------------
st.title("📈 v0 → v4: mỗi version thay đổi gì")
st.caption(
    "Mỗi version chỉ sửa **một** file (`system_prompt.md` hoặc `tools.yaml`) để kiểm chứng **một** giả thuyết, "
    "rồi chạy lại 20 case base bằng API thật. Số liệu đọc trực tiếp từ `version_log.csv` và `runs/*.json`."
)
if not available:
    st.error("Không tìm thấy run JSON của v0–v4 (kiểm tra cột run_file trong artifacts/version_log.csv).")
    st.stop()

first, last = runs[available[0]], runs[available[-1]]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Case accuracy", f"{last['case_accuracy']:.0%}", f"{(last['case_accuracy'] - first['case_accuracy']) * 100:+.0f} điểm từ {available[0]}")
c2.metric("Tool routing", f"{last['tool_routing_accuracy']:.0%}", f"{(last['tool_routing_accuracy'] - first['tool_routing_accuracy']) * 100:+.0f} điểm")
c3.metric("Arguments", f"{last['argument_accuracy']:.0%}", f"{(last['argument_accuracy'] - first['argument_accuracy']) * 100:+.0f} điểm")
c4.metric("Case PASS", f"{last['passed_cases']}/{last['total_cases']}", f"{last['passed_cases'] - first['passed_cases']:+d} case")

chart = pd.DataFrame(
    {
        "Case accuracy": [runs[v]["case_accuracy"] for v in available],
        "Tool routing": [runs[v]["tool_routing_accuracy"] for v in available],
        "Arguments": [runs[v]["argument_accuracy"] for v in available],
    },
    index=available,
)
st.line_chart(chart, y_label="accuracy", x_label="version", height=260)

tab_story, tab_cases, tab_diff = st.tabs(["🧭 Từng version sửa gì", "🧪 Case nào thay đổi", "🔍 So sánh nội dung file"])

# ---------------- tab 1: story ----------------
with tab_story:
    for version in available:
        row, run = log.get(version, {}), runs[version]
        fixed, broken = fixed_and_broken(version)
        previous_acc = runs[available[available.index(version) - 1]]["case_accuracy"] if available.index(version) else None
        down = previous_acc is not None and run["case_accuracy"] < previous_acc
        best = version == available[-1] and run["case_accuracy"] == 1.0
        if available.index(version) == 0:
            chips = f'<span class="chip bad">{len(broken)} FAIL: {" ".join(broken)}</span>' if broken else ""
        else:
            chips = (f'<span class="chip ok">✓ sửa được: {" ".join(fixed)}</span>' if fixed else "") + \
                    (f'<span class="chip bad">✗ hỏng thêm: {" ".join(broken)}</span>' if broken else "") + \
                    ("" if fixed or broken else '<span class="chip bad">không case nào đổi</span>')
        changed = row.get("changed_artifact", "") or "—"
        st.markdown(
            f"""<div class="vcard{' best' if best else ''}">
              <div class="vtitle"><span class="vtag">{version}</span><span class="file">{changed}</span>
                <span class="hash">prompt {run['prompt_hash']} · tools {run['tools_hash']}</span>
                <span class="acc{' down' if down else ''}">{run['case_accuracy']:.0%}</span></div>
              <div>{chips}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        with st.expander(f"Chi tiết {version}: giả thuyết, thay đổi, bằng chứng"):
            st.markdown(f"**Giả thuyết:** {row.get('hypothesis') or '—'}")
            st.markdown(f"**Đã sửa / quan sát:** {row.get('reason') or '—'}")
            st.markdown(
                f"**Metric:** {row.get('metric_before') or '—'} → {row.get('metric_after') or '—'} · "
                f"routing {run['tool_routing_accuracy']:.0%} · args {run['argument_accuracy']:.0%} · "
                f"multi-turn {run['multiturn_accuracy']:.0%} · provider error {run['provider_error_cases']}"
            )
            st.caption(f"Run: `{run['run_file']}` · model `{run['model']}`")

    st.info(
        "**Bài học:** prompt sửa *hành vi* (phạm vi, hỏi lại, xác nhận). Ràng buộc trong schema (`required`) "
        "hiệu quả hơn mô tả dài (v2 tụt, v3 tăng). Khi hai luật xung đột thì phải ghi rõ thứ tự ưu tiên (v4 sửa R12)."
    )

# ---------------- tab 2: case matrix ----------------
with tab_cases:
    only_changed = st.toggle("Chỉ hiện case từng FAIL", value=True)
    rows = []
    for case_id, by_version in cases.items():
        if only_changed and all(by_version.get(v, True) for v in available):
            continue
        rows.append({"Case": case_id.split("_")[0], "Kiểm tra gì": CASE_MEANING.get(case_id, case_id),
                     **{v: "✓" if by_version.get(v) else "✗" for v in available}})
    table = pd.DataFrame(rows)
    if table.empty:
        st.success("Không có case nào FAIL ở bất kỳ version nào.")
    else:
        def color(value: str) -> str:
            if value == "✓":
                return "background-color: rgba(16,185,129,.18); color: #047857; font-weight: 700; text-align: center"
            if value == "✗":
                return "background-color: rgba(234,88,12,.18); color: #c2410c; font-weight: 700; text-align: center"
            return ""
        st.dataframe(table.style.map(color, subset=available), hide_index=True, width="stretch")
    totals = " → ".join(f"{v}: **{runs[v]['passed_cases']}**" for v in available)
    st.markdown(f"Tổng PASS / {first['total_cases']}: {totals}")

# ---------------- tab 3: artifact diff ----------------
with tab_diff:
    st.caption(manifest.get("note", ""))
    col_a, col_b, col_f = st.columns([1, 1, 1.4])
    version_a = col_a.selectbox("Từ version", VERSIONS, index=0)
    version_b = col_b.selectbox("Đến version", VERSIONS, index=len(VERSIONS) - 1)
    artifact = col_f.radio("File", list(ARTIFACT_LABEL), format_func=ARTIFACT_LABEL.get, horizontal=True)

    def snapshot(version: str) -> tuple[str | None, dict | None]:
        entry = (manifest["versions"].get(version) or {}).get(artifact)
        if not entry:
            return None, None
        return (HISTORY / entry["file"]).read_text(encoding="utf-8"), entry

    text_a, meta_a = snapshot(version_a)
    text_b, meta_b = snapshot(version_b)
    for version, meta in ((version_a, meta_a), (version_b, meta_b)):
        if meta is None:
            st.warning(f"{version}: `{ARTIFACT_LABEL[artifact]}` của version này chưa từng được commit, không có bản để so sánh.")
        elif not meta["exact"]:
            st.caption(f"⚠️ {version}: dùng commit gần nhất `{meta['commit']}` (hash khác một chút so với run).")
        else:
            st.caption(f"✅ {version}: commit `{meta['commit']}` khớp chính xác hash trong run.")

    if text_a is not None and text_b is not None:
        diff = list(difflib.unified_diff(
            text_a.replace("\r\n", "\n").splitlines(), text_b.replace("\r\n", "\n").splitlines(),
            fromfile=f"{version_a}/{ARTIFACT_LABEL[artifact]}", tofile=f"{version_b}/{ARTIFACT_LABEL[artifact]}",
            lineterm="", n=2,
        ))
        if not diff:
            st.success("Hai version dùng cùng một nội dung file này (không thay đổi).")
        else:
            added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
            removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
            st.markdown(f"**+{added}** dòng thêm · **−{removed}** dòng bỏ")
            st.code("\n".join(diff), language="diff")
        with st.expander("Xem toàn văn hai bản"):
            left, right = st.columns(2)
            left.code(text_a, language="markdown" if artifact == "system_prompt" else "yaml")
            right.code(text_b, language="markdown" if artifact == "system_prompt" else "yaml")
