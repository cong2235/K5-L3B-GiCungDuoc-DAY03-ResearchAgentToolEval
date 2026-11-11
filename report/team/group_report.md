# Báo cáo nhóm — Day 03 Research Agent Tool Eval

> Báo cáo gồm 2 phần:
> - **Phần A (mục 2)** — giới thiệu agent, ngắn gọn 1 trang, dùng khi Team showdown.
> - **Phần B (mục 3–7)** — chi tiết và bằng chứng, dựa trên log thật.
>
> Mọi đường dẫn tương đối với `starter_v0/`. Chỉ dùng run hợp lệ (`provider_error_cases == 0` và `measured_cases == total_cases`). Cách chấm xem [RUBRIC.md](../../RUBRIC.md).

## 1. Thông tin nhóm

- Tên nhóm: GiCungDuoc
- Thành viên và phân công: xem [TEAM.md](../../TEAM.md)
- Provider/model dùng cho v0–v5: **OpenRouter, `openai/gpt-4o-mini`**, temperature 0 (`run_eval.py` đặt cố định).

## 2. Mục tiêu và cách tiếp cận — PHẦN A: Giới thiệu agent

### A1. Agent này làm được gì

Research agent về AI/tech: tìm tin trên web, đọc bài đăng X/Twitter theo tài khoản hoặc từ khóa, đọc URL, tra Hacker News, Wikipedia, bài báo khoa học (theo tác giả, theo chủ đề, danh sách tài liệu tham khảo), rồi trình bày thành digest. Agent **hỏi lại khi thiếu thông tin**, **xin xác nhận trước khi đăng Telegram** và từ chối yêu cầu ngoài phạm vi (viết code, làm bài tập).

**Cách chạy UI:**

```bash
cd starter_v0
pip install -r requirements.txt      # đã có streamlit
# điền starter_v0/.env (OPENROUTER_API_KEY, TAVILY_API_KEY, FIRECRAWL_API_KEY, RAPIDAPI_KEY, ...)
streamlit run app.py                  # http://localhost:8501
tailscale funnel --bg 8501            # link công khai cố định (Tailscale Funnel)
# cách tạm thay thế: cloudflared tunnel --url http://localhost:8501  (link trycloudflare đổi mỗi lần chạy)
```

**Link dùng thử (deploy):**

> URL: **https://phuong-ideapad-slim-5-16imh9.tail65ddfe.ts.net/**
>
> - Trang chat: `/` · Trang so sánh v0 → v4 (metric, case thay đổi, diff prompt/tools): `/So_sánh_v0–v4` (menu bên trái).
> - Deploy bằng Tailscale Funnel trỏ tới Streamlit trên máy thành viên: link cố định, nhưng chỉ hoạt động khi máy đó bật và `streamlit run app.py` đang chạy.

### A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| clarify | hỏi lại khi thiếu thông tin (`text`) hoặc xin xác nhận trước khi gửi (`yes_no`) | không |
| timeline | bài đăng mới nhất của **một** tài khoản X (handle, không có `@`) | không |
| social_search | tìm bài đăng X theo từ khóa (`Latest` / `Top`) | không |
| lookup | tìm web / tin tức (`topic`, `timeframe`) | không |
| fetch | đọc nội dung một URL do người dùng đưa | không |
| format | trình bày item đã có thành digest markdown | không |
| send | đăng lên Telegram, chỉ khi `confirmed=true` | không (bonus có sẵn) |
| policy | tra chính sách nội bộ công ty | không (bonus có sẵn) |
| papers | tìm preprint trên arXiv theo từ khóa | không (bonus có sẵn) |
| paper_text | tải PDF arXiv và trích text | không (bonus có sẵn) |
| **hackernews** | tìm story Hacker News (điểm, bình luận, link thảo luận) | **có** |
| **wikipedia** | phần giới thiệu Wikipedia của một khái niệm / người (`en`, `vi`) | **có** |
| **openalex** | bài báo khoa học theo **tên tác giả** và/hoặc chủ đề, xếp theo trích dẫn hoặc mới nhất | **có** |
| **top_papers** | top bài báo đã xuất bản trên tạp chí / hội nghị trong N tháng gần đây (OpenAlex, Semantic Scholar) | **có** |
| **paper_references** | liệt kê tài liệu tham khảo của một bài báo (tham chiếu `[start]`–`[end]`, vị trí trang:dòng) | **có** |

5 tool mới đều dùng API công khai, **không cần API key** (Semantic Scholar có thể giới hạn tốc độ khi không có key).

### A3. Câu hỏi mẫu để thử

1. Tin tức AI hôm nay có gì nổi bật?
2. Dân tech trên Hacker News đang bàn gì về LangGraph? (lấy 10 thảo luận liên quan nhất)
3. Tìm 5 nghiên cứu gần đây của Yoshua Bengio về deep learning.
4. Top 5 bài báo được trích dẫn nhiều nhất về AI agents trong 6 tháng qua.
5. Tóm tắt 5 tweet mới nhất giúp mình → (agent hỏi tài khoản nào) → Elon Musk.
6. Đăng bản tin này lên Telegram giúp mình → (agent xin xác nhận trước, không gửi ngay).

## 3. Giải pháp

**`artifacts/system_prompt.md`** (v1, v4, v5):
- v1: bỏ 3 chỉ dẫn xấu của starter (đoán thay vì hỏi, gửi không cần xác nhận, ép một bước). Thay bằng: phạm vi rõ ràng (ngoài phạm vi như toán, code thì từ chối, **không** gọi tool); thiếu handle hoặc URL thì `clarify(text)`, không đoán, không bịa URL; yêu cầu gửi/đăng thì `clarify(yes_no)` trước, chỉ `send` sau khi người dùng đồng ý ở lượt sau; quy tắc multi-turn (giữ tham số cũ, lấy giá trị sửa mới nhất).
- v4: thêm ngoại lệ "yêu cầu gửi/đăng không dùng `response_type=text` kể cả khi chưa có nội dung"; hành động **đầu tiên** với mọi yêu cầu gửi/đăng luôn là `clarify(yes_no)`, gộp việc xin nội dung vào cùng một câu hỏi.
- v5: thêm mục "Extra sources" định tuyến tới các tool mới.

**`artifacts/tools.yaml`** (v2, v3, v5): mỗi description nói rõ *làm gì / DÙNG khi / KHÔNG dùng khi (dùng tool X)*. Quy ước tham số: handle không có `@` và đổi tên người nổi tiếng thành handle (Sam Altman → `sama`); `query` chỉ là từ khóa; thời gian đi vào `timeframe`, tin tức đi vào `topic=news`; `search_type=Top` cho "nổi bật". v3 khai báo `response_type` của `clarify` là **tham số bắt buộc** và ghi "KHÔNG dùng khi người dùng đã đưa URL". v5 khai báo 5 tool mới.

**Tool mới** (mỗi tool có `TOOL.md`, đăng ký trong `tools/__init__.py` và `tools.yaml`): xem bảng A2. Agent gọi `hackernews` khi người dùng nhắc Hacker News, `wikipedia` khi hỏi định nghĩa hoặc nhắc Wikipedia, `openalex` khi người dùng nêu **tên tác giả**, `top_papers` khi hỏi top bài báo đã xuất bản trong một khoảng thời gian, `paper_references` khi cần danh sách tài liệu tham khảo của một bài.

## 4. Kết quả — PHẦN B: Chi tiết và bằng chứng

### B1. Version Evidence

Từ `artifacts/version_log.csv` và `runs/*.json`. Base eval 20 case, `openai/gpt-4o-mini`. Chỉ liệt kê run hợp lệ.

| Version | Changed Artifact | Hypothesis | Metric Before | Metric After | Run File |
|---|---|---|---:|---:|---|
| v0 | baseline | Đo hành vi chưa tối ưu | — | 0.70 | `runs/v0_B_base_openrouter_20261110T171647554591.json` |
| v1 | `system_prompt.md` | Bỏ chỉ dẫn xấu và thêm rule scope / clarify / confirm sẽ sửa nhóm `out_of_scope`, `missing_info`, `wrong_boundary` | 0.70 | 0.85 | `runs/v1_B_base_openrouter_20261110T174124264176.json` |
| v2 | `tools.yaml` | Mô tả rõ khi nào dùng / không dùng cho từng tool sẽ sửa lỗi hỏi thừa và thiếu tham số | 0.85 | 0.80 (giảm) | `runs/v2_B_base_openrouter_20261110T174700121287.json` |
| v3 | `tools.yaml` | Khai báo `response_type` là tham số bắt buộc và ghi rõ khi nào KHÔNG dùng `clarify` sẽ sửa R04, R10, R11 | 0.80 | 0.95 | `runs/v3_B_base_openrouter_20261110T175516491312.json` |
| v4 | `system_prompt.md` | Rule "thiếu thông tin → hỏi nội dung" đang thắng rule "gửi → xin xác nhận"; ghi rõ ngoại lệ và ưu tiên `yes_no` sẽ sửa R12 | 0.95 | **1.00** | `runs/v4_B_base_openrouter_20261110T180213947961.json` |
| v5 | `system_prompt.md` + `tools.yaml` | Thêm 5 tool mới kèm description rõ và dòng routing sẽ không làm giảm base | 1.00 | 1.00 | `runs/v5_B_base_openrouter_20261110T191450124678.json` |

Chi tiết các chỉ số:

| Version | case_accuracy | tool_routing | argument | multiturn | provider_error |
|---|---:|---:|---:|---:|---:|
| v0 | 0.70 (14/20) | 0.75 | 0.70 | 1.00 | 0 |
| v1 | 0.85 (17/20) | 0.95 | 0.85 | 1.00 | 0 |
| v2 | 0.80 (16/20) | 0.95 | 0.80 | 1.00 | 0 |
| v3 | 0.95 (19/20) | 1.00 | 0.95 | 1.00 | 0 |
| v4 | 1.00 (20/20) | 1.00 | 1.00 | 1.00 | 0 |
| v5 | 1.00 (20/20) | 1.00 | 1.00 | 1.00 | 0 |

**v2 làm kết quả giảm** (0.85 → 0.80): R11 từ PASS thành FAIL (`clarify` được gọi mà thiếu `response_type`), R04/R10/R12 vẫn FAIL. Phân tích ở B2. Giả thuyết "mô tả rõ hơn là đủ" bị bác bỏ một phần: model vẫn bỏ qua tham số tùy chọn, đến v3 mới sửa được nhờ đổi `response_type` thành bắt buộc.

**Độ dao động giữa các lần chạy:** artifact v0 (cùng prompt và tools) được chạy hai lần cho 0.70 và 0.75 dù temperature 0 (`runs/v0_B_base_openrouter_20261110T171647554591.json`, `runs/v0_B_base_openrouter_20261110T174342622585.json`). Chênh lệch ±0.05 (1 case) nằm trong nhiễu, nên các bước tăng nhỏ nên được đọc thận trọng.

### B2. Failure Analysis

Lấy từ `results[*].result.failures` trong run JSON.

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| R08, R14 (v0) | `out_of_scope` | `send(text=<lời giải / code>)` | Starter bảo "luôn gọi một tool": agent viết lời giải rồi **đăng lên Telegram** thay vì từ chối | v1: mục Scope, ngoài phạm vi thì từ chối và không gọi tool |
| R10 (v0) | `missing_info` | `timeline(screenname="sama")` | Prompt starter bảo "đoán một tài khoản nổi tiếng" | v1: thiếu handle thì `clarify(text)` |
| R11 (v0) | `missing_info` | `fetch(url="https://example.com/article")` | Bịa URL khi người dùng nói "bài viết này" mà không đưa link | v1: không bao giờ bịa URL, thiếu thì `clarify` |
| R12 (v0) | `wrong_boundary` | `send(text="Bản tin này")` | Gửi ngay không xin xác nhận | v1: yêu cầu gửi thì `clarify(yes_no)` trước |
| R13 (v0) | `wrong_arg_value` | `lookup(query="AI news", timeframe="day")` | Nhồi chữ "news" vào query và bỏ `topic=news` | Hết FAIL từ v1 |
| R04 (v1, v2) | `wrong_tool` | `clarify(yes_no)` hỏi "Bạn có chắc muốn tóm tắt bài từ link này?" | Người dùng đã đưa URL đầy đủ nhưng agent vẫn hỏi lại | v3: description `clarify` ghi "KHÔNG dùng khi người dùng đã đưa URL" |
| R10 (v1, v2) | `missing_info` | `clarify(question=...)` không có `response_type` | Hỏi đúng nhưng thiếu tham số mà eval chấm | v3: `response_type` bắt buộc (`required: [question, response_type]`) |
| R11 (v2) | `missing_info` | `clarify(question=...)` không có `response_type` | **Lỗi mới do v2** (v1 đang PASS) | v3: như trên |
| R12 (v1, v2, v3) | `wrong_boundary` | `clarify(response_type="text")` hỏi nội dung bản tin | Người dùng chưa nêu nội dung nên rule "thiếu thông tin" thắng rule "xác nhận trước khi gửi" | v4: ngoại lệ trong prompt, hành động đầu tiên luôn là `clarify(yes_no)` |

### B3. Team Eval Cases

`data/eval_group.json`: đúng 10 case (5 single turn + 5 multi turn), 4/10 case route tới tool mới. Run: `runs/v5_B_group_openrouter_20261110T191517936193.json` (artifact `v5+pef90408b98e0+t6c8acaab4a58`) → **8/10 PASS**, routing 1.00, argument 0.80, multiturn 1.00.

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| G01_social_search_top | Phân biệt "nổi bật" với "mới nhất", truyền đúng `search_type` | `social_search(query="AI Agents", search_type="Top", ...)` | PASS |
| G02_lookup_news | Dùng `lookup` cho tin web, không nhầm với X | `lookup(query="AI models", topic="news", timeframe="week", max_results=5)` | **FAIL**: agent gọi đúng tool và tham số, nhưng viết `query="mô hình AI"` (tiếng Việt) thay vì "AI models" |
| G03_hackernews_discussion | Nhận ra nguồn Hacker News | `hackernews(query="LangGraph", sort="relevance", limit=10)` ★ | **FAIL**: agent gọi đúng tool, bỏ `sort` vì mặc định đã là `relevance` |
| G04_wikipedia_definition | Chỉ dùng Wikipedia khi được yêu cầu, đúng ngôn ngữ | `wikipedia(query="Transformer", lang="vi")` ★ | PASS |
| G05_openalex_author | Truyền đúng tác giả, chủ đề, thứ tự, số lượng | `openalex(author="Yoshua Bengio", query="deep learning", ...)` ★ | PASS |
| G06_clarify_missing_url | Thiếu URL thì hỏi lại, bổ sung ở lượt sau (multi-turn) | `clarify(response_type="text")` | PASS |
| G07_timeline_account_mapping | Đổi tên Sam Altman thành `sama`, cập nhật `limit` theo lượt sau | `timeline(screenname="sama", limit=3)` | PASS |
| G08_fetch_url_boundary | Chỉ `fetch` khi đã có URL | `fetch(url="https://example.com/ai-agents")` | PASS |
| G09_format_existing_content | Chỉ định dạng dữ liệu đã có, không gọi thêm tool tìm kiếm | `format(template="sections")` | PASS |
| G10_top_papers_published | Phân biệt bài đã xuất bản với preprint arXiv | `top_papers(query="Multimodal AI", months=12, ...)` ★ | PASS |

★ = case route tới tool mới của nhóm.

**Nhận xét hai case FAIL:** cả hai đều là lỗi **giá trị tham số do cách chấm khá cứng**, không phải chọn sai tool (routing 1.00). G02 yêu cầu `query` đúng chữ "AI models" trong khi người dùng viết tiếng Việt; G03 coi việc bỏ tham số có giá trị mặc định là sai. Đây là các điểm cần review thủ công (xem mục 7). Nhóm giữ nguyên case thay vì chỉnh `expect` để khớp kết quả.

Run group trước đó (`runs/v3_B_group_openrouter_20261110T185506710798.json`, artifact `v3+p3e71a3386c32+t11847243314d`) dùng **đúng bộ 10 case này** và cho cùng kết quả 8/10, fail cùng hai case G02 và G03. Việc thêm tool mới ở v5 do đó không làm thay đổi kết quả group: hai lỗi đến từ cách chấm, không đến từ phiên bản artifact.

### B4. Live Chat Evidence

Từ `transcripts/*.transcript.json` (`chat.py`, model `openai/gpt-4o-mini`). Hash trong transcript là `v3+p45c2f48ecf76+t4b34e765b228` (ba transcript đầu) và `v3+p3e71a3386c32+t11847243314d` (các transcript sau); nhãn "v3" do người chạy đặt, hash của transcript đầu trùng prompt và tools của v4 (xem `version_log.csv`).

| Turn | User Request | Tool Calls | Version Evidence | Outcome |
|---|---|---|---|---|
| 1 | Tweet mới nhất của Sam Altman là gì? (yêu cầu thường) | `timeline(screenname="sama", limit=1)` | `…184027196287.transcript.json` | ✅ đổi tên thành handle đúng, trả dữ liệu thật |
| 2 | Tin tức AI hôm nay có gì nổi bật? (yêu cầu thường) | `lookup(query="AI", topic="news", timeframe="day")` | `…184614232991.transcript.json` | ✅ query chỉ là từ khóa, thời gian nằm trong `timeframe` |
| 3 | Tóm tắt 5 tweet mới nhất giúp mình (thiếu thông tin) | không gọi tool; hỏi tài khoản nào bằng văn bản | `…184614232991.transcript.json` | ✅ không đoán, hỏi lại |
| 4 | Elon Musk (bổ sung) | `timeline(screenname="elonmusk", limit=5)` | `…184614232991.transcript.json` | ✅ giữ `limit=5` từ lượt 3 |
| 5 | Đăng bản tin này lên Telegram giúp mình (đăng/gửi) | `clarify(response_type="yes_no")` | `…184614232991.transcript.json` | ✅ xin xác nhận, không gửi ngay |
| 6 | Không | không gọi tool | `…184614232991.transcript.json` | ✅ người dùng từ chối nên không gửi |
| 7 | 3 bài viết mới trên hackerank | `hackernews(query="hackerank", sort="date", limit=3)` | `…185540920306.transcript.json` | ✅ dùng tool mới; ⚠ người dùng gõ "hackerank" nên agent tìm đúng từ này |
| 8 | Top 5 bài báo được trích dẫn nhiều nhất về AI agents trong 6 tháng qua | `top_papers(query="AI agents", months=6, limit=5, ...)` | `…185825658715.transcript.json` | ✅ |
| 9 | Tóm tắt 5 tweet mới nhất → elon musk | `timeline(...)` → `format(...)` | `…185957360047.transcript.json` | ✅ hỏi lại rồi tạo digest |

Lượt 5–6 chứng minh **boundary xác nhận trước khi gửi**. Luồng gửi thật lên Telegram (hỏi yes/no → xác nhận → `status: sent`) nằm ở `transcripts/v4_openrouter_20261111T062351019749.transcript.json` (xem B5).

### B5a. Required Evidence — Tool mới, unit test, UI

| Item | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Tool mới (`tools/<tên>/`) | `tools/hackernews/`, `wikipedia/`, `openalex/`, `top_papers/`, `paper_references/` (mỗi folder có `tool.py` + `TOOL.md`), đăng ký trong `tools/__init__.py` và `artifacts/tools.yaml` | contract test xanh; 4/10 case nhóm route tới tool mới; tool chạy thật trong live chat (turn 7, 8) | API công khai có giới hạn tốc độ (Semantic Scholar khi không có key) → trả error dict, không raise |
| Unit test tool mới (≥ 3 test/tool) | `tests/test_tools_todo.py`, `tests/test_tools_step4b_edge.py`; `pytest` → **216 passed, 0 failed, 0 skipped** | số test mang tên tool (`pytest --collect-only`): hackernews 5, wikipedia 4, openalex 9, top_papers 9, paper_references 6 | toàn bộ offline, HTTP mock bằng `fake_http` |
| UI (lệnh chạy + link dùng thử) | `app.py`, mục A1 | Streamlit chat, hiện từng tool call và kết quả | link công khai chỉ tạo khi demo (Cloudflare Tunnel) |

Tool unit tests: ví dụ lỗi mà unit test bắt được còn eval thì **không**: eval chỉ chấm *model gọi tool nào với tham số gì*, nên một lời gọi `send(text=..., confirmed="false")` vẫn là một lời gọi hợp lệ và được chấm PASS. Unit test kiểm tra *tool làm gì với tham số đó* và phát hiện `confirmed="false"` (chuỗi) bị coi là đã xác nhận nên **tin nhắn vẫn được gửi** (xem Test challenge bên dưới).

### B5. Bonus Evidence

| Bonus | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Small Local Model | B7; `runs/v4-*`, `runs/v5-local-*`, `runs/v6-local-*` (ollama), `artifacts/tools_local.yaml`, `artifacts/system_prompt_local.md` | 3 model ≤ 8B (qwen2.5:3b, llama3.2:3b, gemma4:e2b) chạy base eval, 2 vòng tối ưu, kiểm tra ngược trên cloud. Tốt nhất: gemma4:e2b 45% → 100%, qwen2.5:3b 45% → 85% | Bản local chỉ có 7 tool core (mất 9 tool nghiên cứu); prompt local làm cloud tụt 100% → 90% |
| Hơn 3 tool mới (≥ 4) | 5 folder tool ở B5a; case G03, G04, G05, G10 trong `data/eval_group.json` | 5 tool mới, đủ `TOOL.md`, đăng ký, ≥ 3 test; 4 tool có eval case route tới | — |
| `send` gửi thật lên Telegram sau xác nhận | `transcripts/v4_openrouter_20261111T062351019749.transcript.json` | Lượt 1: agent gọi `clarify(response_type="yes_no")` "Bạn muốn mình đăng bản tin này lên Telegram, đúng không?". Lượt 2: user "Có, đăng đi" → `send(confirmed=true)` → **`status: sent`** lên private channel của nhóm. Model `gpt-4o-mini`, artifact v4 | `send` trả `needs_confirmation` khi chưa xác nhận (có test). Rủi ro thấy được: ở một lượt bị ngắt (không dùng làm bằng chứng), agent gọi `send` với nội dung giữ chỗ `[Tin 1]` cùng lượt với `lookup` — guardrail chặn vì chưa có `confirmed=true` |
| Telegram bot (UI phụ, ngoài rubric) | `starter_v0/bot.py`, `tests/test_bot.py` (7 test), `transcripts/telegram_v4-telegram_*.transcript.json` | Chat với agent ngay trong Telegram (@congatest2005bot): lịch sử riêng mỗi chat, `/start` `/reset`, transcript JSON cho mỗi chat, lỗi model/tool hiển thị thẳng | Bot công khai tốn quota; có allowlist tuỳ chọn `TELEGRAM_ALLOWED_CHAT_IDS`; chỉ một tiến trình được poll mỗi token |
| Test challenge (0 skipped / regression test) | `pytest` output (216 passed, 0 skipped); `tests/test_tools_step4b_edge.py` | **0 skipped** và 73 test biên có regression cho bug thật | — |

**Test challenge — bug tìm được trong tool có sẵn.** Khi gọi từng tool với input biên mà model hay gửi, nhóm phát hiện và sửa các bug sau; mỗi bug có test hồi quy trong `tests/test_tools_step4b_edge.py`. Chạy file test này trên bản tool gốc cho **55 fail / 18 pass**; trên bản đã sửa tất cả pass.

| # | Bug | Sửa |
|---|---|---|
| 1 | `send(confirmed="false")` vẫn **gửi tin**: `if not confirmed` coi chuỗi là đúng | chỉ boolean `true` mới tính là xác nhận |
| 2 | `send` gửi text rỗng hoặc dài hơn 4096 ký tự lên Telegram | trả error dict trước khi gọi mạng |
| 3 | `fetch("")`, `"not a url"`, `"javascript:..."` vẫn tốn một lượt Firecrawl | chỉ nhận URL `http(s)` tuyệt đối |
| 4 | `lookup`, `timeline`, `social_search`, `papers` gửi truy vấn rỗng tới API tính phí | trả error dict, không gọi mạng |
| 5 | `lookup(max_results=-2)`, `topic="sports"`, `search_type="Hot"` bị đẩy nguyên lên API | ép về khoảng hợp lệ / giá trị mặc định |
| 6 | `timeline("@sama")` gửi cả `@` dù quy ước là handle không có `@` | tự bỏ `@` |
| 7 | `timeline(limit=-1)` trả gần hết tweet vì `items[:-1]`; `limit="abc"` báo lỗi sau khi đã gọi API | ép `limit` về 1–20 trước khi gọi |
| 8 | `format(items="oops")` văng `AttributeError` | trả error dict, bỏ qua phần tử không phải object |

Quyết định hành vi (ghi trong docstring của file test): `limit` ≤ 0 → 1, giá trị không đọc được → mặc định 5, lớn → 20.

### B7. Small Local Model Challenge (bonus)

**Setup.** Ollama trên máy `minhphuong` (RTX 5060 Ti 16 GB) trong tailnet của nhóm; script eval chạy trên laptop, gọi `OLLAMA_BASE_URL=http://100.116.167.90:11434/v1`. 3 model hỗ trợ tool calling, đều ≤ 8B: `qwen2.5:3b`, `llama3.2:3b`, `gemma4:e2b` (4.6B). Bản prompt/tools riêng cho local nằm ở file riêng để không phá v4 của cloud: `artifacts/tools_local.yaml`, `artifacts/system_prompt_local.md`. Mọi run có `provider_error_cases == 0`, `measured_cases == 20`, ghi trong `version_log.csv`.

**Bảng cloud vs local (case accuracy trên 20 case base):**

| Version | Thay đổi (một giả thuyết) | gpt-4o-mini (cloud) | gemma4:e2b | qwen2.5:3b | llama3.2:3b |
|---|---|---:|---:|---:|---:|
| v4 | prompt + tools v4 của cloud, không sửa | 100% | 45% | 45% | 20% |
| v5-local | `tools_local.yaml`: chỉ 7 tool core, description giữ nguyên | 100% | **100%** | 45% | 25% |
| v6-local | + `system_prompt_local.md`: bảng quyết định, quy ước args, 8 ví dụ few-shot | 90% | 95% | **85%** | **50%** |

Run: `runs/v4-{gemma4e2b,qwen3b,llama3b}_B_base_ollama_*.json`, `runs/v5-local-*_B_base_*.json`, `runs/v6-local-*_B_base_*.json`. Cột cloud của v5/v6 là kiểm tra ngược (`v5-local-on-cloud`, `v6-local-on-cloud`).

**Lỗi đặc thù của model nhỏ (baseline v4):**

| Loại lỗi | Ví dụ thật | Model |
|---|---|---|
| Phản hồi rỗng (không tool, không text) | 10/11 case FAIL | gemma4:e2b |
| Hỏi lại bằng text thay vì gọi `clarify` | R11, R12 | qwen2.5:3b |
| Đoán thay vì hỏi | R10 gọi `timeline(screenname="twitter_account")` | qwen2.5:3b |
| Số truyền dạng chuỗi | `limit="10"`, `max_results="10"` | llama3.2:3b |
| Tự thêm từ vào `query` | `"AI news today"` thay vì `"AI"` | llama3.2:3b |
| Gọi tool cho yêu cầu ngoài phạm vi | R08 gọi `lookup("tích phân")`, R14 gọi `format` | llama3.2:3b |
| Có URL nhưng không gọi `fetch` | R04 gọi `lookup(query="GPT-5")` thay vì đọc URL | qwen2.5:3b |

**Vòng 1 — v5-local (tools).** Giả thuyết: prompt v4 + 16 tool ≈ 4.9k token vượt context mặc định của Ollama, model nhỏ bị cắt đầu vào nên trả rỗng. Bỏ 9 tool không cần cho base suite (≈ 2.5k token). Kết quả: gemma4:e2b **45% → 100%**, xác nhận giả thuyết; qwen không đổi, llama +1 case — hai model này không trả rỗng, lỗi của chúng nằm ở hành vi và args.

**Vòng 2 — v6-local (prompt).** Giả thuyết: model 3B không theo được prompt dài nhiều đoạn quy tắc (~420 từ); bảng quyết định 5 bước + quy ước args + 8 ví dụ few-shot (dùng tên và chủ đề **khác** bộ eval) sẽ sửa lỗi clarify và args. Kết quả: qwen **45% → 85%**, llama **25% → 50%**, gemma 100% → 95% (R01 đoán handle `samaltman` thay vì `sama`; cả prompt v4 lẫn prompt local đều không có ví dụ map tên → handle, ở v5 gemma đoán đúng).

**Kiểm tra ngược.** `tools_local.yaml` trên cloud vẫn 100%. `system_prompt_local.md` trên cloud tụt còn 90%: R03 và M02 gọi thừa `social_search` vì rule "web news AND tweets → gọi cả hai" bị model lớn áp dụng quá rộng. Không có một bản prompt tốt nhất cho cả hai: bản dùng chung tốt nhất trên base suite là **prompt v4 + `tools_local.yaml`** (cloud 100%, gemma 100%), còn qwen/llama cần prompt ngắn có few-shot.

**Kết luận có bằng chứng:**
1. Với model nhỏ, **độ dài tool declaration là lỗi trước tiên cần loại**: gemma4:e2b từ 45% lên 100% chỉ nhờ bớt tool, không sửa chữ nào trong prompt.
2. **Few-shot ngắn giúp model 3B gọi đúng `clarify` và đúng kiểu args** (qwen +40 điểm, llama gấp đôi), nhưng
3. **prompt tối ưu cho model nhỏ có thể làm model lớn hỏng theo kiểu khác** (cloud gọi thừa tool), nên nên tách prompt theo model như nhóm đã làm.

Giới hạn: mỗi version chạy 1 lần; bản local chỉ giữ 7 tool nên không phục vụ được các câu hỏi về paper / Hacker News / Wikipedia.

## 5. Khó khăn và cách xử lý

- **Run không hợp lệ do lỗi provider.** Một số lần chạy đầu cho `provider_error` trên 20/20 case vì thiếu gói `openai` trong môi trường (`RuntimeError: Install live provider dependency first`), và hai lần khác vì OpenRouter trả `429` (17/20 và 1/1 case). Nhóm không dùng các run này làm bằng chứng: phần lớn nằm ở `runs/invalid/`, riêng hai file `runs/v0_B_base_openrouter_20261110T183336655028.json` và `runs/v4_B_base_openrouter_20261110T183348932339.json` (0/20, thiếu gói `openai`) vẫn nằm ở thư mục `runs/` và cần chuyển vào `runs/invalid/`. Bằng chứng chính thức của từng version là các file trong bảng B1.
- **Conflict `data/eval_group.json`.** Hai thành viên cùng thêm case vào một mảng JSON nên một commit trên `main` chứa nguyên dấu conflict (`<<<<<<<`), làm hỏng JSON và `test_eval_cases_only_expect_declared_tools`. Đã sửa ở commit `85eba0c`. Bài học: một người chốt file này vì rubric đòi đúng 10 case.
- **Hash prompt không khớp file đã commit** cho các run v1–v3: người chạy sửa nhẹ prompt/tools rồi mới commit, và kiểu xuống dòng CRLF/LF làm hash khác nhau giữa các máy. Vì vậy mỗi dòng `version_log.csv` ghi `artifact_version` lấy trực tiếp từ run JSON; run v5 (`v5+pef90408b98e0+t6c8acaab4a58`) được chạy từ đúng bản đang có trong repo.
- **Key RapidAPI chưa đăng ký gói** trên một máy: `timeline` trả `403 You are not subscribed to this API`, `social_search` trả `429`. Đây là vấn đề tài khoản, không phải lỗi logic; các transcript ở B4 chạy bằng key đã đăng ký nên `timeline` trả dữ liệu thật.
- **Môi trường Python hỏng** (`pydantic_core`, `jiter`) khiến `openai` không import được; xử lý bằng cách cài lại gói.

- **Mạng chập chờn khi làm bonus.** `ollama pull` lỗi DNS (`server misbehaving`) và một lượt gửi Telegram lỗi `APIConnectionError`; lượt Telegram bị ngắt giữa chừng nên không dùng làm bằng chứng. Xử lý: chạy model trên máy `minhphuong` qua Tailscale, chạy lại khi mạng ổn.
- **Run local đầu tiên 20/20 `provider_error`** (`model 'qwen2.5:3b' not found`) vì `OLLAMA_BASE_URL` trỏ sang máy khác chưa có model; run này ở `runs/invalid/`. Run `qwen2.5:3b` chạy bằng CPU laptop (50%) ở `runs/extra/`, không dùng trong bảng B7 để mọi model local chạy cùng một máy.

## 6. Tổng hợp đóng góp

Chi tiết đóng góp của từng thành viên nằm trong [TEAM.md](../../TEAM.md) và các báo cáo cá nhân `report/team/MSSV_HoTen.md`. Theo lịch sử commit trên `main`:

| Thành viên (tên git) | Phần chính |
|---|---|
| congvt | tool `hackernews`, `wikipedia`, `openalex`; ghi `version_log.csv`; merge và xử lý conflict |
| thbao4545 | cập nhật `system_prompt.md`, `tools.yaml`; chạy run v0–v4 |
| minhphuong150505 | tool `top_papers`, `paper_references` kèm test |
| nguyencongtu4800 | 10 case trong `data/eval_group.json` |

## 7. Hạn chế và hướng cải thiện — B6. Reflection

- **Fix nào thuộc `system_prompt.md`?** Hành vi và ranh giới giữa các quy tắc: phạm vi (từ chối ngoài phạm vi), hỏi lại thay vì đoán, xác nhận trước khi gửi (v1), và thứ tự ưu tiên khi hai quy tắc đụng nhau: xác nhận gửi thắng thiếu thông tin (v4, sửa R12).
- **Fix nào thuộc `tools.yaml`?** Hợp đồng của từng tool: khi nào dùng / không dùng, quy ước tham số, và đặc biệt **tham số bắt buộc** (`response_type`, v3). v2 chỉ viết lại mô tả mà vẫn thiếu tham số, bài học là model hay bỏ qua tham số tùy chọn, nên cần khai báo `required`.
- **Failure nào cần review thủ công thay vì chấm tự động?** (1) G02 và G03: agent gọi đúng tool với tham số hợp lý nhưng bị chấm FAIL do khác chữ ("mô hình AI" so với "AI models") hoặc bỏ tham số mặc định. (2) R12: `clarify(text)` hỏi nội dung cũng an toàn (chưa gửi gì) nhưng eval đòi `yes_no`. (3) Eval chỉ chấm lời gọi tool nên không phát hiện agent nói "đã gửi" mà không gọi `send`; cần đọc câu trả lời. (4) Độ dao động ±0.05 giữa hai lần chạy cùng artifact (B1).
- **Nếu có thêm một vòng, nhóm sẽ thử giả thuyết nào?** (a) Làm cho eval bớt cứng: chỉ kiểm tra tham số thực sự quan trọng (bỏ `sort=relevance` ở G03, nới `query` ở G02) hoặc ghi chú trong description để agent luôn truyền tham số đó; (b) chạy mỗi version 3 lần và báo cáo trung bình; (c) thêm kiểm tra trên câu trả lời cho các case `send`; (d) với model local: thêm lại ví dụ map tên → handle vào prompt local (sửa R01 của gemma) và thu hẹp rule "gọi cả hai tool" để không làm hỏng cloud.

## 8. Tài liệu tham khảo

- OpenRouter API: https://openrouter.ai/docs
- Hacker News Search API (Algolia): https://hn.algolia.com/api
- MediaWiki Action API: https://www.mediawiki.org/wiki/API:Main_page
- OpenAlex API: https://docs.openalex.org
- Semantic Scholar API: https://api.semanticscholar.org
- Đề bài và rubric của khoá: [README.md](../../README.md), [RUBRIC.md](../../RUBRIC.md)
