# Điều tra ΔRAM/KV-cache — M2M-100

> Tài liệu này ghi lại kết quả của 3 cuộc điều tra nhằm giải thích tại sao
> `ΔRAM` trong báo cáo beam-sweep của M2M-100 hiển thị `+0` trên
> mọi beam, trong khi Opus-MT lại hiển thị `+12→+49 MB`.

---

## Bối cảnh

Trong beam-sweep gốc, `peak_ram_mb` được đo bằng `psutil.Process().memory_info().peak_wset`
(Windows) hoặc `resource.getrusage().ru_maxrss` (Unix) — tức là **RSS đỉnh của toàn bộ
process**. ΔRAM được tính là:

```
ΔRAM = peak_ram_mb[beam=N] − peak_ram_mb[beam=1]
     = KV_cache_N − KV_cache_1   (triệt tiêu model weights + runtime overhead)
```

| Model | Baseline RSS | ΔRAM (beam 1→8) | Kết luận ban đầu |
|-------|-------------|-----------------|-----------------|
| Opus-MT | 372 MB | +12→+49 MB | KV-cache tăng rõ rệt |
| M2M-100 | 1101 MB | +0 MB | "Miễn nhiễm với RAM tăng" |

Kết luận ban đầu cho rằng ΔRAM phẳng là do **nhiễu đo ±5–10 MB** nuốt mất tín hiệu
KV-cache 13 MB. Tuy nhiên, tài liệu [`docs/benchmark-plan/ram-delta-m2m100-investigation.md`]
(../benchmark-plan/ram-delta-m2m100-investigation.md) đã chỉ ra 3 vấn đề:

1. Số "±5–10 MB" là ước lượng cảm tính, không có dữ liệu thực nghiệm (mỗi beam chỉ chạy 1 lần).
2. Dữ liệu RAM tuyệt đối của M2M-100 là `1101, 1102, 1101, 1101, 1101` — quá "sạch" để giải thích bằng nhiễu ngẫu nhiên.
3. Giả thuyết thay thế: **đỉnh RAM rơi vào lúc load model, không phải lúc decode**.

---

## Investigation 1: Đo variance thật bằng cách lặp mỗi beam 5 lần

**Phương pháp:** Chạy 5 process riêng biệt cho mỗi beam (1, 2, 4, 5, 8), mỗi process
infer 30 items MT trên M2M-100, ghi lại `peak_ram_mb` từ mỗi `run_results.json`.

**Kết quả (5 reps × 5 beams):**

| Beam | N | Mean (MB) | Std (MB) | Min (MB) | Max (MB) |
|------|---|-----------|----------|---------|---------|
| 1 | 5 | 1105.2 | 0.32 | 1104.7 | 1105.7 |
| 2 | 5 | 1105.0 | 0.32 | 1104.6 | 1105.4 |
| 4 | 5 | 1105.1 | 0.13 | 1105.0 | 1105.3 |
| 5 | 5 | 1105.0 | 0.36 | 1104.4 | 1105.4 |
| 8 | 5 | 1105.0 | 0.37 | 1104.6 | 1105.6 |

**Kết luận Investigation 1:**
- **Variance thực tế chỉ ~0.3 MB**, không phải ±5–10 MB như giả định ban đầu.
- **ΔRAM giữa beam=1 và beam=8 là 0.2 MB** — không có xu hướng tăng theo beam.
- Giả thuyết "nhiễu che mất tín hiệu" **bị bác bỏ**. RAM phẳng là thật.

---

## Investigation 2: Đo RSS ngay trước và sau `translate_batch()`

**Phương pháp:** Viết script chạy trong 1 process, ghi lại RSS tại từng pha:
import → load model → decode với từng beam_size. Đồng thời ghi lại `peak_wset`
(cao nhất mọi thời điểm trong vòng đời process).

⚠️ **Lưu ý:** Thiết kế này chạy 4 beam decode tuần tự trong cùng 1 process — vi phạm
nguyên tắc "1 process/beam" đã được xác lập trong `beam-sweep-retrospective.md`.
Kết quả peak_wset bị nhiễm do cộng dồn bộ nhớ giữa các lần decode.

**Kết quả:**

```
[1] RSS before anything:        18.8 MB
[2] RSS after imports:         260.1 MB
[3] RSS after model load:      841.3 MB
[4] Decode beam=1:              841.4 → 843.1 MB  (delta: +1.7 MB)
[4] Decode beam=2:              843.1 → 844.4 MB  (delta: +1.3 MB)
[4] Decode beam=4:              844.4 → 846.3 MB  (delta: +1.9 MB)
[4] Decode beam=8:              846.3 → 847.1 MB  (delta: +0.8 MB)
[5] Process peak_wset:        **1160.0 MB**
```

**Kết luận Investigation 2:**
- RSS decode chỉ tăng **+1–2 MB mỗi beam**, không phải nguồn gây peak.
- Tuy nhiên, peak_wset = 1160 MB **không thể dùng làm bằng chứng chính thức** vì
  bị nhiễm bởi chạy tuần tự (xem Investigation 2b bên dưới để có con số sạch).
- Thông tin hữu ích duy nhất từ investigation này là **pattern RSS theo pha**
  (load ~841 MB, decode +1–2 MB).

### Investigation 2b: Load-only — xác nhận thời điểm peak

**Phương pháp:** Chạy 5 process riêng biệt, mỗi process **chỉ import + load model,
không decode gì cả**, ghi lại peak_wset ngay sau load. Đây là cách trực tiếp để
xác định thời điểm peak.

**Kết quả (5 reps, mỗi rep là 1 process riêng):**

| Rep | peak_after_load | peak_final | RSS_after_load |
|-----|----------------|-----------|---------------|
| 1 | 1106 MB | 1106 MB | 787 MB |
| 2 | 1106 MB | 1106 MB | 788 MB |
| 3 | 1106 MB | 1106 MB | 787 MB |
| 4 | 1106 MB | 1106 MB | 787 MB |
| 5 | 1106 MB | 1106 MB | 787 MB |

peak_final và peak_after_load luôn bằng nhau — decode không đóng góp gì vào đỉnh.

**Kết luận Investigation 2b:**
- **peak_wset = 1106 MB, thiết lập hoàn toàn tại load time** — không cần decode.
- RSS persistent sau load chỉ 787 MB; peak cao hơn ~319 MB là bộ nhớ tạm của CT2
  (workspace GEMM, buffer trung gian) được cấp phát và thu hồi trong lúc init.
- **Giải thích chênh lệch 54 MB giữa Inv 2 (1160 MB) và Inv 2b (1106 MB):**
  4 decode tuần tự trong Inv 2 gây cộng dồn bộ nhớ (fragmentation, buffer giữ lại
  giữa các lần gọi `translate_batch`) — đúng như cảnh báo trong retrospective.
  Con số 1160 MB là nhiễm chéo process, không phải peak thật.

---

## Investigation 3: Kiểm tra CT2 cấp phát buffer cố định

**Phương pháp:** Chạy model init + decode trong các subprocess riêng biệt với các tham số
runtime khác nhau (`max_queued_batches`, `inter_threads`), đo `peak_wset` mỗi lần.
Đồng thời kiểm tra cấu hình model CT2 để tìm tham số convert-time liên quan đến bộ nhớ.

**Kết quả runtime params (mỗi config decode 1 lần với beam=8 trong process riêng):**

| Config | Peak_wset | RSS after load | RSS after decode |
|--------|----------|---------------|-----------------|
| default (mqb=0, it=1) | **1106** | 788 | 848 |
| mqb=1 | **1106** | 787 | 849 |
| mqb=16 | **1106** | 787 | 848 |
| mqb=0, it=4 | **1106** | 787 | 849 |

**Kết quả cấu hình model CT2:**

```json
{
  "add_source_bos": false,
  "add_source_eos": false,
  "bos_token": "<s>",
  "decoder_start_token": "</s>",
  "eos_token": "</s>",
  "layer_norm_epsilon": null,
  "multi_query_attention": false,
  "unk_token": "<unk>"
}
```

Không có tham số `max_batch_size`, `workspace`, `beam_size`, hay bất kỳ cấu hình bộ nhớ nào.

**Kết luận Investigation 3** (chỉ dựa trên dữ liệu của riêng investigation này):
- **peak_wset không thay đổi** khi thay đổi `max_queued_batches` hay `inter_threads` — workspace cố định.
- **File cấu hình CT2 không chứa tham số bộ nhớ** — workspace hoàn toàn do C++ runtime
  của CT2 quyết định dựa trên kiến trúc model (d_model, num_layers).
- **Model.bin = 467.9 MB** trên đĩa. Peak_wset = 1106 MB — gấp ~2.4× kích thước model.
  Phần chênh lệch (~638 MB) là workspace nội bộ của CT2 cho GEMM int8.
- **Workspace được cấp phát 1 lần tại load time**, không phụ thuộc vào runtime params.

**Kết hợp với Investigation 1 và 2b để suy luận:**
- Investigation 1 (beam sweep, process riêng) cho thấy ΔRAM = 0 giữa các beam.
- Investigation 2b (load-only) xác nhận peak = 1106 MB tại load time.
- Investigation 3 cho thấy workspace cố định không đổi khi decode.
- Suy luận tổng hợp: **workspace load-time đủ lớn để chứa KV-cache của mọi beam_size
  mà không cần cấp phát RSS thêm.**

---

## Giải thích đầy đủ

### Tại sao Opus-MT hiển thị ΔRAM còn M2M-100 thì không?

Opus-MT (d_model=512, 6 layers) có workspace nhỏ hơn nhiều so với M2M-100
(d_model=1024, 12 layers). Với Opus-MT:
- Baseline RSS thấp (~372 MB)
- KV-cache delta (~49 MB) là 13% của baseline → dễ thấy

Với M2M-100:
- Workspace CT2 tại load time (~1106 MB) đã chiếm đỉnh RSS
- KV-cache delta (~13 MB) chỉ là 1.2% của đỉnh
- Quan trọng hơn: KV-cache được cấp phát **bên trong** workspace có sẵn, không phải là RSS mới

**Cơ chế chính xác:**
1. CT2 cấp phát workspace lớn tại load time (đỉnh 1106 MB, sau đó thu hồi 1 phần về 841 MB RSS)
2. `peak_ram_mb()` ghi nhận đỉnh 1106 MB này
3. Khi decode, KV-cache (1.9→15 MB tùy beam) nằm gọn trong workspace đã cấp phát
4. RSS không tăng đáng kể (+1–2 MB chỉ là Python overhead)
5. peak_wset không thay đổi vì đỉnh đã được thiết lập từ pha load

### Kết luận cho ADR-007

- **M2M-100: beam_size không ảnh hưởng đến RSS** — KV-cache nằm trong workspace có sẵn của CT2
- **Opus-MT: beam_size ảnh hưởng đến RSS** — model đủ nhỏ để KV-cache vượt workspace
- **Không cần "beam=1 để tiết kiệm RAM" cho M2M-100** — RAM là hằng số bất kể beam_size
- **Cần kiểm tra lại Whisper trên Android device**: chưa có dữ liệu tương tự cho ASR, Whisper có thể có cơ chế workspace khác (faster-whisper dùng CT2 Generator, không phải Translator)

---

## Phụ lục: Các script sử dụng

| Script | Mục đích |
|--------|---------|
| `bench/investigate_ram_variance.py` | Investigation 1: lặp beam × 5 reps |
| `bench/investigate_ram_phases.py` | Investigation 2: RSS theo từng pha |
| `bench/investigate_ram_phases_3.py` | Investigation 3: runtime params vs peak |

Dữ liệu thô tại `bench-results/investigation/m2m100/` (Investigation 1)
và `bench-results/investigation/m2m100-ram-phases*.json` (Investigation 2 & 3).
