# Vấn đề ở Investigation 2: tái phạm đúng lỗi đã cảnh báo trước đó

Investigation 2 mô tả: "chạy trong 1 process, ghi lại RSS tại từng pha... decode với từng beam_size" — tức 4 lần decode (beam 1, 2, 4, 8) chạy tuần tự trong cùng 1 process. Đây chính là dạng vi phạm nguyên tắc "1 process/beam" đã được xác lập từ đầu chuỗi công việc này (Root Cause 1 và 2 trong beam-sweep-retrospective.md) — chỉ khác là lần này áp dụng cho việc đo RAM theo pha thay vì đo BLEU.

Bằng chứng cụ thể cho thấy điều này có ảnh hưởng thật, không chỉ là rủi ro lý thuyết: peak_wset của Investigation 2 là 1160 MB, cao hơn ~54–55 MB so với Investigation 1 (mean ~1105 MB, đo từng beam trong process riêng) và Investigation 3 (1106 MB, cũng đo process riêng). Nếu đúng như giả thuyết "workspace cố định, cấp 1 lần lúc load, không phụ thuộc gì vào decode sau đó", thì con số peak của Investigation 2 phải trùng khớp với 2 investigation kia (vì cùng model, cùng workload cơ bản) — chứ không nên cao hơn hẳn. Chênh lệch 54 MB này là dấu hiệu cho thấy 4 lần decode tuần tự trong Investigation 2 có cộng dồn thêm bộ nhớ (fragmentation, buffer giữ lại giữa các lần gọi), tức là ngược lại với kết luận "decode không ảnh hưởng gì đến peak" mà chính investigation này đưa ra.

Kéo theo đó, khẳng định "đỉnh RAM xảy ra trong lúc CT2 khởi tạo, không phải lúc decode" thực ra chưa được đo trực tiếp — file chỉ có 2 điểm dữ liệu (RSS sau load = 841.3 MB, và peak_wset cuối cùng = 1160 MB sau khi đã chạy hết 4 beam), rồi suy luận khoảng cách đó là do pha load. Cách chứng minh trực tiếp và rẻ hơn: chạy 1 process chỉ load model, không gọi decode gì cả, đo peak_wset ngay lập tức. Nếu con số đó đã ~1105–1106 MB dù chưa decode 1 câu nào, giả thuyết mới thực sự được xác nhận sạch. Hiện tại kết luận này đang được diễn giải hơi vội.

# Vấn đề nhỏ hơn: Investigation 3 kết luận vượt quá những gì tự nó đã kiểm tra

Investigation 3 chỉ thay đổi max_queued_batches và inter_threads — không thay đổi beam_size trong chính investigation này (bảng không có cột beam). Nhưng dòng kết luận lại viết "đủ lớn để chứa toàn bộ KV-cache của mọi beam" — đây là kết hợp với phát hiện của Investigation 1 (đã test qua các beam), không phải điều Investigation 3 tự đo được. Không sai về tổng thể (2 investigation cộng lại thì hợp lý), nhưng nên ghi rõ dòng này là suy luận kết hợp, không phải phát hiện riêng của Investigation 3, để tránh đọc nhầm là mỗi investigation độc lập chứng minh đủ.

# Điểm đúng và đáng tin

- Investigation 1: thiết kế đúng (n=5, process riêng, có std) — đây là cách làm nên áp dụng ngay từ đầu thay vì chỉ chạy 1 lần/beam như sweep gốc. Kết luận "biến thiên thật chỉ ~0.3 MB, không phải ±5–10 MB giả định" là vững, bác bỏ đúng giả thuyết "nhiễu" trong file trước.
- Số học đều đúng: 1106/467.9 ≈ 2.36×, và cách diễn giải "Opus-MT baseline nhỏ nên % KV-cache đủ lớn để thấy, M2M-100 baseline lớn nên bị workspace che" — logic tỷ lệ này hợp lý và nhất quán với phát hiện trước đó.

# Đề xuất trước khi chốt vào ADR-007

- Chạy thêm 1 process "chỉ load, không decode" để xác nhận trực tiếp thời điểm peak, thay vì suy luận từ Investigation 2.
- Giải thích chênh lệch 54 MB giữa Investigation 2 và Investigation 1/3 trước khi dùng Investigation 2 làm bằng chứng — nếu do chạy tuần tự cùng process, nên loại bỏ số peak_wset=1160 khỏi kết luận chính thức, chỉ giữ lại pattern RSS-theo-pha (vẫn hữu ích) chứ không dùng con số peak đó.