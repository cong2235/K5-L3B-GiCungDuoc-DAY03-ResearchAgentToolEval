## 1. Thông tin thành viên

- Họ tên: Nguyễn Công Tú
- MSSV: 2A202604008
- Email: nguyencongtu5050@gmail.com

## 2. Phần việc phụ trách

- Thực hiện phần CP4 : Eval nhóm 10 case


## 3. Đóng góp cụ thể
- Xây dựng và bổ sung 10 test case theo yêu cầu của nhóm.
- Bao phủ các tool cốt lõi và 4 tool mới: hackernews, wikipedia, openalex, top_papers.
- Thiết kế các tình huống kiểm thử nhiều dạng lỗi như wrong_tool, wrong_arg_value, wrong_boundary, unnecessary_tool, missing_info và out_of_scope.
- Chạy đánh giá bằng run_eval.py với cấu hình OpenRouter, phân tích kết quả và xác định các trường hợp cần điều chỉnh.
- Ghi nhận kết quả ban đầu: 8/10 case đạt, tool routing accuracy 100%, argument accuracy 80%; đề xuất cải thiện test case để tránh đánh giá sai các tham số mặc định hoặc truy vấn tương đương về ngữ nghĩa.
...

## 4. Bằng chứng

- File/commit/PR: file eval_group.md, commit :478ee623a50474d796a29015e62db83b1e099adb, 90648a4b390684dfbb400d66e37aefcc1d764b54,85eba0c1162420daf62bc6099d2c421bbfb078f8
- AI/công cụ đã dùng và cách tự kiểm tra kết quả: ChatGPT hỗ trợ phân tích yêu cầu, xây dựng thêm bổ sung và rà soát các test case; Tự kiểm tra: Kiểm tra cấu trúc và số lượng 10 case trong data/eval_group.json, đảm bảo đúng tỷ lệ 5 single-turn và 5 multi-turn, Phân tích các case chưa đạt để xác định nguyên nhân và điều chỉnh lại test case khi cần.

## 5. Tự đánh giá
- Hoàn thành phần việc được giao, xây dựng đủ 10 test case theo đúng yêu cầu về số lượng và cấu trúc single-turn, multi-turn.
- Các test case có độ bao phủ tương đối đa dạng, kiểm tra được khả năng lựa chọn tool, truyền tham số và xử lý ngữ cảnh qua nhiều lượt hội thoại.
- Đã chạy thử nghiệm và phân tích kết quả: 8/10 case đạt, qua đó nhận diện một số điểm chưa hợp lý trong tiêu chí so khớp tham số và thiết kế test case.