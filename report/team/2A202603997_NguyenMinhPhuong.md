# Báo cáo cá nhân — Nguyễn Minh Phương - 2A202603997

## 1. Thông tin thành viên

- Họ tên: Nguyễn Minh Phương
- MSSV: 2A202603997
- Email: phuongnm150505@gmail.com
- GitHub: minhphuong150505

## 2. Phần việc phụ trách

- **Tool mới (CP3):** viết 2 tool nghiên cứu cho agent: `top_papers` và `paper_references`, kèm unit test, khai báo trong `tools.yaml` và eval case.
- **UI và kênh dùng thử (CP5):** bot Telegram cho agent, trang Streamlit so sánh v0 → v4, nâng cấp giao diện chat Streamlit (chọn model, gồm model local Gemma 4 qua Ollama), deploy link dùng thử cố định bằng Tailscale Funnel (trước đó dùng Cloudflare Tunnel).
- **Bonus:** gửi Telegram thật sau khi xác nhận, và Small Local Model Challenge (3 model ≤ 8B, 2 vòng tối ưu).
- **Tích hợp code:** merge nhánh tool của mình vào `main` và xử lý conflict với tool của các bạn khác (hackernews, wikipedia, openalex).

## 3. Đóng góp cụ thể

### 3.1. Tool `top_papers`

- **Làm gì:** trả về các bài báo được trích dẫn nhiều nhất đã **đăng trên tạp chí/hội nghị** (không phải preprint) trong N tháng gần đây, theo chủ đề.
- **Nguồn dữ liệu:** OpenAlex, dự phòng bằng Semantic Scholar. Không bắt buộc API key.
- **Tham số:** `query`, `months`, `venue_type` (journal/conference), `limit`, `sort_by`, `source`. Đề bài ban đầu là "top 10 bài trong 9 tháng". Tôi tách số tháng và số bài thành tham số để model tự điền theo câu hỏi.
- **Phân biệt với tool có sẵn:** `papers` chỉ tìm arXiv, `top_papers` lọc bài đã xuất bản và xếp theo citation. Description trong `tools.yaml` ghi rõ khi nào dùng tool nào để model route đúng.
- **Kiểm thử:** 10 unit test trong `tests/test_tools_todo.py`. Eval case `G10_top_papers_published` **pass** ở run nhóm v5 (`runs/v5_B_group_openrouter_20261110T191517936193.json`).

### 3.2. Tool `paper_references`

- **Làm gì:** liệt kê tài liệu tham khảo của một paper, từ mục `[start]` đến `[end]`. Khi đọc từ PDF, tool trả thêm vị trí của từng mục trong bài (`trang:dòng` bắt đầu → kết thúc).
- **Nguồn dữ liệu:** tải PDF arXiv và parse bằng `pypdf`, dự phòng bằng OpenAlex.
- **Tham số:** `paper`, `start`, `end`, `source`.
- **Kiểm thử:** 8 unit test. Tôi có viết eval case `G02_paper_references_range` ("tài liệu tham khảo từ số 5 tới 10 của arXiv 1706.03762"). Nhưng bộ 10 case nhóm chốt sau (`85eba0c fix 10 eval case`) không còn case này, nên `paper_references` **chưa có kết quả eval** trong run v5.
- **Khác:** thêm biến tùy chọn `SEMANTIC_SCHOLAR_API_KEY` và `OPENALEX_API_KEY` vào `.env.example`.

### 3.3. Bot Telegram (nhánh `feat/telegram-bot`)

- `bot.py` chạy cùng vòng lặp model → tool với `chat.py`.
- Mỗi chat Telegram có lịch sử multi-turn và file transcript riêng (`transcripts/telegram_<version>_<chat>_<timestamp>.transcript.json`).
- Có thể giới hạn người dùng bằng `TELEGRAM_ALLOWED_CHAT_IDS`.
- 5 hàm test trong `tests/test_bot.py` (7 test case khi chạy, một hàm có 3 bộ tham số).
- **Bonus gửi Telegram thật:** `transcripts/v4_openrouter_20261111T062351019749.transcript.json`: agent gọi `clarify(response_type="yes_no")` → tôi xác nhận "Có, đăng đi" → `send(confirmed=true)` → `status: sent` lên channel của nhóm.

### 3.4. Streamlit (nhánh `feat/version-showcase`)

- **Trang so sánh** `pages/1_📈_So_sánh_v0–v4.py`: hiển thị khác biệt giữa các version. Snapshot artifact của từng version lưu trong `artifacts/history/` (`manifest.json`, `v0/v1/v4_system_prompt.md`, `v0/v3_tools.yaml`).
- **Giao diện chat** `app.py`:
  - Chọn model bằng dropdown: GPT-4o mini qua OpenRouter, **Gemma 4 E2B chạy local qua Ollama**, hoặc tự nhập provider/model.
  - Đèn trạng thái 🟢/🔴 kiểm tra Ollama có chạy và đã có model chưa.
  - Kết quả tool hiện dạng thẻ, có nút Đồng ý/Không trước khi gửi.
  - Theme riêng trong `.streamlit/config.toml`.

### 3.5. Model local qua Tailscale (Small Local Model Challenge)

- Laptop không có GPU và RAM trống ít, nên tôi chạy Ollama trên máy `minhphuong` (RTX 5060 Ti 16 GB). Máy này cùng mạng Tailscale với laptop.
- Ollama chỉ lắng nghe trên IP Tailscale (`100.116.167.90:11434`). Model: `gemma4:e2b` (4.6B), `qwen2.5:3b`, `llama3.2:3b`.
- Trong `.env` (không commit): `OLLAMA_BASE_URL=http://100.116.167.90:11434/v1`. Không phải sửa code provider; script eval chạy trên laptop, model chạy trên GPU máy kia.
- **Kết quả base eval (20 case, mọi run hợp lệ, ghi trong `version_log.csv`):**

| Version | Thay đổi | Cloud | gemma4:e2b | qwen2.5:3b | llama3.2:3b |
|---|---|---:|---:|---:|---:|
| v4 | giữ nguyên prompt/tools cloud | 100% | 45% | 45% | 20% |
| v5-local | `tools_local.yaml`: 7 tool core | 100% | 100% | 45% | 25% |
| v6-local | `system_prompt_local.md`: bảng quyết định + 8 ví dụ few-shot | 90% | 95% | 85% | 50% |

- **Rút ra:** gemma trả rỗng vì prompt + 16 tool (~4.9k token) vượt context mặc định của Ollama, bớt tool là lên 100%. qwen và llama cần prompt ngắn có ví dụ. Prompt local làm cloud gọi thừa tool (100% → 90%), nên tách prompt riêng cho local. Chi tiết ở mục B7 của group report.
- **Hạn chế:** mỗi version chạy 1 lần; bản local chỉ còn 7 tool; Ollama trên máy `minhphuong` chạy bằng `nohup`, khởi động lại máy phải bật lại.

### 3.6. Deploy và tích hợp

- **Deploy:** ban đầu dùng Cloudflare quick tunnel (`cloudflared tunnel --url http://localhost:8501`), nhưng link là tạm thời: link đầu tiên bị Cloudflare thu hồi ("Tunnel not found"). Tôi thử Streamlit Community Cloud nhưng không có quyền admin repo nhóm. Link cuối cùng dùng để nộp là **Tailscale Funnel** (`tailscale funnel --bg 8501`): **https://phuong-ideapad-slim-5-16imh9.tail65ddfe.ts.net/**, link cố định, hoạt động khi máy bật và Streamlit đang chạy. Đã kiểm tra trang chat và trang so sánh trả HTTP 200.
- **Merge vào `main`** (`2f3be8e`, `660d7b5`, `e31b6cf`):
  - Gộp `tools/__init__.py`, giữ đủ tool của cả hai bên.
  - Phát hiện một lần merge trước đó (`6e7d38b`) làm `eval_group.json` chỉ còn 2/11 case. Tôi đã khôi phục lại, sau đó cả 143 test pass.

## 4. Bằng chứng

- **Commit:**
  - `05535c2`: tool `top_papers`
  - `ff105b3`, `fc77b47`: tool `paper_references`
  - `b0aa6fb`: bot Telegram
  - `3f11180`: trang so sánh v0–v4
  - `c586a62`: UI chat
  - `1962358`, `2f3be8e`, `660d7b5`, `e31b6cf`: dọn dẹp và merge
  - `a5506d5`: group report A1 dùng link Tailscale Funnel
  - `951ae28`: dọn `.gitignore`, thêm transcript
  - `1090346`: bonus gửi Telegram thật và Small Local Model Challenge (làm sau deadline 23:59 ngày 10/11, commit riêng)
- **File:** `tools/top_papers/`, `tools/paper_references/`, `bot.py`, `tests/test_bot.py`, `app.py`, `pages/1_📈_So_sánh_v0–v4.py`, `artifacts/history/`, `artifacts/tools_local.yaml`, `artifacts/system_prompt_local.md`
- **Run:**
  - `runs/v5_B_group_openrouter_20261110T191517936193.json` (G10 top_papers pass, nhóm 8/10)
  - `runs/extra/v0_B_group_openrouter_20261110T181122675966.json` (top_papers routing 1/1 với `nvidia/nemotron-3-ultra-550b-a55b:free`)
  - `runs/extra/v0_B_base_openrouter_20261110T181408561770.json` (base 16/20 với cùng model free)
  - `runs/v4-*`, `runs/v5-local-*`, `runs/v6-local-*`: 11 run Small Local Model Challenge (bảng ở mục 3.5)
- **Transcript gửi Telegram thật:** `transcripts/v4_openrouter_20261111T062351019749.transcript.json`
- **AI/công cụ đã dùng và cách tự kiểm tra kết quả:**
  - **Dùng:** Claude Code để đọc repo và hiểu đề, viết code tool, test, bot, UI, merge, cấu hình Tailscale/Ollama và Cloudflare Tunnel. Thêm Tavily skill cho tra cứu web.
  - **Kiểm tra:**
    - Chạy `pytest` sau mỗi thay đổi (143 test pass sau lần merge tool; hiện tại 223 test pass trên `main`).
    - Chạy `run_eval.py` cho base và group suite, đọc `summary` và từng case trong run JSON.
    - Chạy `preflight_provider.py` cho provider mới.
    - Tự mở link Cloudflare, sau đó link Tailscale Funnel để thử.
    - Quét run và transcript tìm key/token trước mỗi lần commit.
  - **Những chỗ AI hoặc kết quả sai mà tôi phát hiện:**
    - Run với `google/gemma-4-31b-it:free` bị lỗi provider gần hết (17/20 và 1/1 case). Tôi chuyển các run này vào `runs/invalid/`, không dùng làm số liệu.
    - Commit `1962358` lỡ thêm 2 run (`runs/v0_B_base_openrouter_20261110T183336655028.json`, `runs/v4_B_base_openrouter_20261110T183348932339.json`) bị lỗi provider 20/20, case_accuracy = 0. Hai run này không hợp lệ và không được dùng trong bảng kết quả; đã chuyển vào `runs/invalid/`.
    - AI in nguyên API key trong output lúc kiểm tra `.env`. Tôi đã đổi các key bị lộ.
    - AI ghi sai số liệu trong slide trình bày ("8 case từng FAIL", đúng là 7). Phát hiện khi đếm lại bảng case và đã sửa trước khi dùng.
    - Khi viết mục B7 của group report, AI lấy nhầm lỗi R04/R10 của qwen từ run chạy bằng CPU laptop thay vì run GPU dùng trong bảng. Đã đối chiếu lại với run JSON và sửa.
    - Lần chạy eval local đầu tiên trỏ nhầm sang máy khác (`OLLAMA_BASE_URL` trong `.env`), nên 20/20 case lỗi `model not found`. Run này nằm ở `runs/invalid/`, không dùng làm số liệu.

## 5. Tự đánh giá

> Phần này tôi tự viết. Theo RULES, AI không được viết phần tự đánh giá.

- **Làm tốt:** Tôi nghĩ phần tôi làm tốt nhất là phần tool và phần local model. Vì tôi là một software engineer nên tôi có thể dễ dàng đọc hiểu các tool và viết được tool mới; còn phần local model thì tôi đã từng host rồi nên tôi có kinh nghiệm ở phần này.
- **Hạn chế:** Một số chỗ về syntax và một số phương thức tôi không nhớ được và phải nhờ AI hướng dẫn, nhưng tôi có kiểm tra lại kết quả đầu ra trước khi commit.
- **Bài học:** Các agent gọi tool sai đa số là do chỉ dẫn trong prompt sai, chứ không phải do AI đó không thông minh. Agent có làm đúng hướng hay không phần lớn phụ thuộc vào prompt của chúng ta.
