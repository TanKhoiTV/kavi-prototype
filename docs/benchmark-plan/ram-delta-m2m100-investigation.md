# Nghi vấn ΔRAM/KV-cache — Opus-MT vs M2M-100

> Đánh giá lại tuyên bố "M2M-100 miễn nhiễm với RAM tăng theo beam" trước khi đưa vào ADR-007.

---

## Lập luận gốc (cần xem lại)

Công thức đại số đưa ra là đúng về mặt hình thức — nếu mỗi beam chạy trong 1 process riêng (đúng thiết kế sweep hiện tại):

```
ΔRAM = peak_ram_mb[beam=N] − peak_ram_mb[beam=1]
     = (model_weights + runtime + KV_cache_N) − (model_weights + runtime + KV_cache_1)
     = KV_cache_N − KV_cache_1
```

Kết luận được đưa ra: với Opus-MT (baseline ~372 MB), KV-cache delta (+12→+49 MB) đủ lớn để "nhìn thấy" trên nền baseline nhỏ; với M2M-100 (baseline ~1101 MB), delta KV-cache lý thuyết chỉ ~13 MB, bị "nhiễu đo ±5–10 MB" nuốt mất nên ΔRAM đọc ra là +0.

**Vấn đề:** đây là một giả thuyết chưa kiểm chứng, không phải kết luận đã xác nhận. Con số "±5–10 MB variance" không có bằng chứng thực nghiệm đi kèm.

---

## Vì sao giả thuyết "nhiễu che mất" đáng ngờ

- Sweep hiện tại chỉ chạy **1 lần/beam** (n=1) — không đủ dữ liệu để tính variance thật. Số ±5–10 MB là ước lượng cảm tính, không phải số đo được.
- Dữ liệu RAM tuyệt đối của M2M-100 là `1101, 1102, 1101, 1101, 1101` — gần như **trùng khít tuyệt đối** ở 4/5 điểm. Nếu thật sự có nhiễu ngẫu nhiên ±5–10 MB giữa các process độc lập, xác suất 4/5 lần ra đúng cùng 1 số nguyên là rất thấp. Dữ liệu quá "sạch" để giải thích bằng nhiễu ngẫu nhiên.

---

## Giả thuyết thay thế, cụ thể hơn và kiểm chứng được

Nhiều khả năng **đỉnh RAM (`peak_ram_mb`) của toàn process không rơi vào lúc decode**, mà rơi vào **lúc load model** — nơi CTranslate2 có thể cấp phát sẵn scratch buffer nội bộ (workspace cho GEMM int8, buffer trung gian) với kích thước **không phụ thuộc `beam_size` runtime**, mà phụ thuộc cấu hình lúc convert hoặc giá trị mặc định cố định — lớn hơn nhiều so với phần KV-cache tăng thêm do beam (lý thuyết chỉ 1.9→15 MB).

Nếu đúng vậy: đây không phải "tín hiệu bị nhiễu nuốt mất" mà là **điểm mù cấu trúc của cách đo** (peak-over-toàn-process không nhạy với beam_size), không phải nhiễu ngẫu nhiên. Với Opus-MT (baseline nhỏ hơn hẳn), phần overhead load-time có thể thấp hơn đủ để đỉnh thực sự rơi vào lúc decode, nên vẫn "nhìn thấy" được KV-cache tăng — nhưng đây có thể là trùng hợp về kích thước model, không phải bằng chứng cho thấy Opus-MT được đo đúng còn M2M-100 đo sai theo kiểu nhiễu.

---

## 3 khả năng đang bị lẫn với nhau

1. Nhiễu đo thật (giả thuyết gốc, chưa có bằng chứng)
2. Đỉnh RAM nằm ở pha load, không phải pha decode (giả thuyết thay thế, khớp với dữ liệu quá "sạch" hơn)
3. KV-cache thực sự phẳng gần tuyệt đối (khó tin, vì công thức lý thuyết đã tính tăng dần rõ ràng 1.9→15 MB)

Chưa đủ dữ liệu để chọn giữa 3 khả năng này.

---

## Cần đo thêm trước khi kết luận

1. **Lặp lại mỗi beam 3–5 lần** (vẫn tách process riêng như thiết kế cũ) để đo variance thật, thay vì giả định ±5–10 MB.
2. **Đo RSS ngay trước và ngay sau `translate_batch()`**, tách riêng peak lúc load và peak lúc decode — cách trực tiếp nhất để xác nhận/bác bỏ giả thuyết "đỉnh nằm ở lúc load".
3. Kiểm tra CTranslate2 cấp phát buffer cố định theo tham số convert-time (vd. `max_batch_size` lúc convert) hay theo đúng `beam_size` runtime — nếu là cố định, "Est. KV-cache" theo công thức lý thuyết (d_model, layers) trong report M2M-100 chỉ là con số lý thuyết, chưa chắc phản ánh bộ nhớ CTranslate2 thực sự cấp phát.

---

## Kết luận

Không nên công bố "M2M-100 miễn nhiễm với RAM tăng theo beam" như một phát hiện đã xác nhận. Cần thực hiện 3 phép đo bổ sung ở trên để tách bạch nguyên nhân trước khi đưa kết luận này vào ADR-007.
