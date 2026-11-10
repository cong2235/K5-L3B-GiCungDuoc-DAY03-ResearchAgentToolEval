# Báo cáo cá nhân — Võ Trần Công (2A202604026)

## 1. Thông tin thành viên

- Họ tên: Võ Trần Công
- MSSV: 2A202604026
- Email: congvotran2003@gmail.com
- GitHub: cong2235 (tên git: congvt)

## 2. Phần việc phụ trách

- Làm nhóm trưởng, phân công công việc.
- Quản lý version trên git và `artifacts/version_log.csv`.
- Viết 3 tool mới cho agent: `hackernews`, `wikipedia`, `openalex` (tìm bài báo theo tên tác giả / chủ đề).
- Unit test cho tool (Step 4b) và sửa các bug tìm được trong tool có sẵn.
- Gộp (merge) công việc của các thành viên và xử lý conflict.

## 3. Đóng góp cụ thể

- **Quản lý version:** ghi `version_log.csv` cho v0–v5, lấy hash, metric và đường dẫn run trực tiếp từ file run JSON (không gõ tay); chỉ ghi các run hợp lệ (`provider_error_cases == 0`).
- **3 tool mới** (mỗi tool có `tool.py`, `TOOL.md`, đăng ký trong `tools/__init__.py` và `tools.yaml`):
  - `hackernews`: tìm story Hacker News qua Algolia API.
  - `wikipedia`: lấy phần giới thiệu của một bài Wikipedia (`en`, `vi`).
  - `openalex`: tìm bài báo theo tên tác giả (tra id tác giả trước rồi lọc bài), theo chủ đề, hoặc kết hợp; sắp xếp theo trích dẫn hoặc mới nhất. Khi gọi API thật phát hiện `sort=recent` trả cả bản ghi đề ngày tương lai, đã thêm bộ lọc ngày.
- **Unit test:** điền các stub trong `tests/test_tools_todo.py`; viết `tests/test_tools_step4b_edge.py` (73 test) cho các input biên model hay gửi. Phát hiện và sửa 8 nhóm bug trong tool có sẵn (nghiêm trọng nhất: `send(confirmed="false")` vẫn gửi tin vì chuỗi được coi là đã xác nhận). Chạy file test trên bản tool gốc cho 55 fail / 18 pass, trên bản đã sửa tất cả pass. Chi tiết ở mục B5 của group report.
- **Kiểm thử bằng API thật:** gọi từng tool với dữ liệu thật và đối chiếu lại với API gốc (ví dụ tra lại bài theo DOI trên OpenAlex, tra lại story theo id trên Hacker News) để kiểm tra tool trả đúng nguồn.
- **Merge và conflict:** gộp `top_papers` của bạn Phương với 3 tool của mình (conflict ở `tools/__init__.py`, `tools.yaml`, `eval_group.json`, `test_tools_todo.py`), giữ cả hai phía, chạy lại `pytest` trước khi push.
- **Chạy eval cho bản cuối:** chạy base và group cho artifact hiện tại (v5): base 20/20, group 8/10; phân tích 2 case fail (G02, G03) là lỗi giá trị tham số do cách chấm cứng, không phải chọn sai tool.
- **Báo cáo:** soạn `report/team/group_report.md` từ số liệu run và transcript thật.

## 4. Bằng chứng

- File/commit/PR:
  - `4764bde` feat: add hackernews, wikipedia and openalex tools
  - `805d275` Merge origin/main: combine top_papers with hackernews, wikipedia, openalex
  - `5f94adb` docs: record v0-v4 in version_log from valid OpenRouter runs
  - `6e7d38b` fix conflict eval_group.json
  - `9eeb796` docs: team info
  - `starter_v0/tools/hackernews/`, `wikipedia/`, `openalex/`
  - `starter_v0/tests/test_tools_step4b_edge.py` và các bản sửa tool tương ứng
  - Run: `runs/v5_B_base_openrouter_20261110T191450124678.json`, `runs/v5_B_group_openrouter_20261110T191517936193.json`
- AI/công cụ đã dùng và cách tự kiểm tra kết quả:
  - **Công cụ AI đã dùng:** Claude (Claude Code, Anthropic) để viết và chạy code, test, phân tích log và soạn báo cáo trên máy của tôi. Tôi đưa ra các quyết định hướng đi.
  - **Cách tự kiểm tra kết quả:**
    - Chạy `pytest` (216 passed, 0 skipped) sau mỗi thay đổi tool.
    - Chạy test mới lên bản tool gốc để chắc test thật sự bắt được bug, chứ không chỉ pass trên code đã sửa.
    - Gọi API thật và đối chiếu độc lập với nguồn gốc (DOI, id Hacker News, REST API Wikipedia).
    - Chỉ dùng run có `provider_error_cases == 0` và `measured_cases == total_cases`, kiểm tra bằng script; số trong `version_log.csv` lấy từ JSON.
    - Đọc từng kết quả FAIL của eval để phân biệt lỗi chọn tool với lỗi do cách chấm.
    - Quét `.env` và token trước khi commit để không đẩy key lên repo.

## 5. Tự đánh giá

- **Làm được:** có đầy đủ v0–v5 với run hợp lệ, base eval từ 0.70 lên 1.00; 3 tool mới chạy đúng nguồn khi kiểm chứng bằng API thật; bộ test sạch (0 skipped) và bắt được bug thật trong tool có sẵn.
- **Chưa tốt / còn hạn chế:**
  - v2 làm kết quả giảm (0.85 → 0.80); nhóm chỉ sửa được khi chuyển `response_type` thành tham số bắt buộc (v3).
  - Hai case group (G02, G03) vẫn FAIL do cách chấm quá cứng; nhóm chưa chỉnh `expect` để khớp, và cần review thủ công.
  - Chưa làm bonus Telegram gửi thật và Small Local Model.
  - Một số hash prompt của run v1–v3 không khớp file đã commit, nên run đó khó tái lập chính xác.
- **Bài học:** unit test và eval đo hai việc khác nhau, như ví dụ `send(confirmed="false")` vẫn được eval chấm PASS nhưng unit test mới phát hiện ra việc tin nhắn bị gửi đi.
