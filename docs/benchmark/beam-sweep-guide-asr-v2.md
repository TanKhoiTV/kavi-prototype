Chi tiết đầy đủ — Giai đoạn 1 (sweep beam width trên host/laptop) — Whisper Small (faster-whisper)

> Bước khởi đầu cho ASR, theo đúng cách tiếp cận đã dùng cho MT: làm 1 model (Whisper) cho chuẩn methodology
> trước, rồi mới mở rộng sang Moonshine/Zipformer. Cấu trúc bám sát `beam-sweep-guide.md`/`-v2.md`,
> nhưng có 4 khác biệt cần đặc biệt chú ý: (1) faster-whisper là API cấp cao chứ không phải
> `ctranslate2.Translator` thô, (2) metric là WER (thấp hơn = tốt hơn, ngược chiều BLEU), (3) độ dài audio
> không đồng đều như câu văn bản MT nên cần chuẩn hoá latency theo real-time factor (RTF), (4) **cần cả 2
> chiều vi-en và en-vi** — tức Whisper phải nhận diện đúng cả audio tiếng Việt lẫn audio tiếng Anh (vì
> pipeline vi→en dùng ASR-vi và pipeline en→vi dùng ASR-en), không chỉ tiếng Việt như bản đầu.
>
> **Sửa quan trọng so với bản trước:** `language` trước đây bị hard-code `"vi"` ở cấp instance — điều này
> giờ SAI vì sẽ khiến audio tiếng Anh bị ép nhận diện như tiếng Việt. `language` phải đọc theo từng item
> (giống input data, không phải biến sweep), tách hẳn khỏi `beam_size` vốn cố định cho cả 1 lần chạy.

---

Bước 0 — Kiểm tra trước khi bắt đầu

```bash
ls eval_data/eval_manifest_v1.json
uv run python -c "import faster_whisper; print(faster_whisper.__version__)"
```

Xác nhận manifest có item ASR với `transcript_ref` không rỗng (WER không tính được nếu thiếu):

```bash
uv run python -c "
from bench.schema import RunManifest
m = RunManifest.from_json('eval_data/eval_manifest_v1.json')
asr = [i for i in m.items if i.stage == 'ASR']
print(f'{len(asr)} ASR items, {sum(1 for i in asr if i.transcript_ref)} có transcript_ref')
"
```

Xác nhận `score_item()` trong bench đã có sẵn phép tính WER cho stage ASR (tương tự BLEU cho MT) — nếu chưa, cần bổ sung trước khi sweep, vì nếu không có bước này thì mọi kết quả beam sau đó sẽ không đánh giá được chất lượng, chỉ có latency/RAM.

**Bổ sung cho 2 chiều:** xác nhận `EvalItem` có trường lưu ngôn ngữ nguồn của audio (ví dụ `item.language` hoặc `item.audio_lang` — tên trường thực tế cần đối chiếu với `bench/schema.py`, guide này giả định là `item.language` với giá trị `"vi"`/`"en"`; đổi lại cho khớp schema thật nếu khác) và đếm số item mỗi chiều:

```bash
uv run python -c "
from bench.schema import RunManifest
from collections import Counter
m = RunManifest.from_json('eval_data/eval_manifest_v1.json')
asr = [i for i in m.items if i.stage == 'ASR']
print(Counter(getattr(i, 'language', None) for i in asr))
"
```

Nếu 1 trong 2 chiều có quá ít item so với chiều còn lại, cần cân nhắc bổ sung dữ liệu trước khi sweep — sweep trên bộ mất cân bằng sẽ cho WER trung bình không đáng tin cho chiều thiểu số.

---

Bước 1 — Candidate: `bench/candidates/whisper_asr.py`

Nguyên tắc chung giữ nguyên như Opus-MT: `beam_size` đọc từ `config` ở cấp instance, các tham số khác cố định để sweep chỉ đổi đúng 1 biến số. Khác biệt: dùng `faster_whisper.WhisperModel`, không phải `ctranslate2.Translator` trực tiếp.

```python
class WhisperASRCandidate(Candidate):
    stage = "ASR"
    id = "whisper-small-multilang-ct2-cpu"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        from faster_whisper import WhisperModel

        cfg = config or {}
        # Chỉ beam_size là biến sweep, cố định cho suốt 1 lần chạy (1 process = 1 beam).
        # KHÔNG đặt "language" ở đây — ngôn ngữ là thuộc tính của TỪNG item audio
        # (vi hoặc en), không phải biến cấu hình cố định cho cả candidate. Nếu hard-code
        # "vi" ở cấp instance như bản trước, mọi audio tiếng Anh sẽ bị ép nhận diện
        # sai ngôn ngữ — không liên quan gì đến beam_size nhưng làm hỏng toàn bộ WER
        # phía en-vi.
        self._decode_kwargs = dict(
            beam_size=cfg.get("beam_size", 5),
            temperature=0,          # tắt temperature fallback — xem cảnh báo ở đầu file
            condition_on_previous_text=False,  # tránh lỗi domino giữa segment
            without_timestamps=True,
        )

        model_dir = Path(model_path) if model_path else WHISPER_MODEL_DIR
        self.model = WhisperModel(
            str(model_dir) if model_dir else "small",
            device="cpu",
            compute_type="int8",
        )

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        audio_path = item.resolve_input()
        # Đọc ngôn ngữ theo từng item — ép, không auto-detect (auto-detect có thể
        # nhầm lẫn ở audio ngắn/nhiễu, lỗi không liên quan gì đến beam_size nhưng
        # làm WER tăng đột biến đúng những item đó, giống lỗi "quên target_prefix"
        # đã gặp với M2M-100).
        lang = getattr(item, "language", None)
        if lang not in ("vi", "en"):
            return None, f"missing/invalid language tag on item {item.id}: {lang!r}"
        segments, info = self.model.transcribe(
            audio_path, language=lang, **self._decode_kwargs
        )
        transcript = "".join(seg.text for seg in segments).strip()
        return transcript, None
```

Vì sao `condition_on_previous_text=False`: mặc định faster-whisper dùng text của segment trước làm ngữ cảnh cho segment sau (giúp mạch lạc trong transcribe dài), nhưng điều này khiến lỗi ở 1 segment lan sang các segment kế tiếp — một dạng nhiễu khác không liên quan đến beam_size. Tắt đi để mỗi segment độc lập, kết quả ổn định hơn giữa các lần chạy.

Vì sao trả lỗi tường minh khi thiếu `language`: thà fail rõ ràng ở 1 item còn hơn để `transcribe()` tự auto-detect âm thầm — auto-detect âm thầm là đúng loại lỗi (nhiễu không liên quan biến sweep) mà toàn bộ guide này cố tránh từ đầu.

Candidate ID đổi từ `whisper-small-vi-ct2-cpu` thành `whisper-small-multilang-ct2-cpu`: đây vẫn là **1 model, 1 candidate class** dùng chung 1 bộ trọng số cho cả 2 ngôn ngữ (Whisper multilingual vốn hỗ trợ cả vi và en sẵn) — chỉ tham số runtime `language` đổi theo item, không cần load 2 model riêng như trường hợp M2M-100 cần `target_prefix` khác nhau cho từng cặp ngôn ngữ dịch.

---

Bước 2 — `--config-override` trong `bench/run.py`

Không đổi — đã tổng quát hoá từ khi làm MT, đọc `item.config` cho mọi stage/candidate như nhau. Không cần sửa gì thêm.

---

Bước 3 — Lọc bộ ASR nhỏ để sweep nhanh, tách riêng theo ngôn ngữ

`bench/filter_manifest.py` đã hỗ trợ `--stage ASR` sẵn và điều kiện lọc `it.transcript_ref` vẫn đúng. Nhưng cần thêm 1 tham số `--lang` để tách 2 file riêng — **không gộp chung 1 file rồi lấy N item đầu tiên**, vì thứ tự item trong manifest gốc không đảm bảo cân bằng vi/en, dễ vô tình lấy gần hết 1 chiều.

Thêm vào `bench/filter_manifest.py`:

```python
ap.add_argument("--lang", choices=["vi", "en"], help="lọc thêm theo ngôn ngữ audio (ASR)")
```

```python
filtered = [
    it
    for it in manifest.items
    if it.stage == args.stage
    and (it.reference_text or it.transcript_ref)
    and (args.lang is None or getattr(it, "language", None) == args.lang)
][: args.limit]
```

Chạy 2 lần, 1 lần mỗi chiều:

```bash
uv run python -m bench.filter_manifest \
  --stage ASR --lang vi --limit 30 \
  --out eval_data/asr_subset_beam_vi.json

uv run python -m bench.filter_manifest \
  --stage ASR --lang en --limit 30 \
  --out eval_data/asr_subset_beam_en.json
```

Vì sao tách file thay vì gộp rồi lọc lúc tổng hợp: giữ mỗi lần chạy `bench.run` chỉ chứa 1 ngôn ngữ giúp Bước 6 (aggregate) đơn giản — không cần sửa logic đọc `run_results.json` để tự group theo ngôn ngữ, chỉ cần trỏ `--results-root` đúng thư mục.

---

Bước 4 — Smoke test trước khi chạy full

```bash
uv run python -m bench.filter_manifest --stage ASR --lang vi --limit 3 --out /tmp/asr_smoke_vi.json
uv run python -m bench.filter_manifest --stage ASR --lang en --limit 3 --out /tmp/asr_smoke_en.json

for lang in vi en; do
  for beam in 1 2; do
    uv run python -m bench.run \
      --manifest /tmp/asr_smoke_$lang.json \
      --candidate whisper-small-multilang-ct2-cpu \
      --out /tmp/asr-beam-smoke-$lang-$beam \
      --config-override "{\"beam_size\": $beam}"
  done
done
```

Kiểm tra thêm (riêng cho Whisper, không có ở MT):

- In raw transcript của cả 2 bộ smoke, xác nhận **đúng ngôn ngữ tương ứng từng file** (bộ vi ra tiếng Việt, bộ en ra tiếng Anh, không lẫn) — nếu sai, kiểm tra `item.language` đọc đúng chưa và có bị auto-detect ghi đè không.
- Xác nhận `print_table()` không có dòng error, cột WER có giá trị hợp lệ cho cả 2 bộ (không phải `None` hàng loạt — báo hiệu `score_item()` chưa hỗ trợ ASR).
- Nếu candidate trả lỗi `"missing/invalid language tag"` ở bất kỳ item nào → dừng lại, kiểm tra schema/manifest trước khi chạy full, đừng bỏ qua các item lỗi này.

---

Bước 5 — Chạy sweep thật, mỗi beam width 1 process riêng biệt

```bash
mkdir -p bench-results
for lang in vi en; do
  for beam in 1 2 4 5 8; do
    echo "=== lang=$lang beam_size=$beam ==="
    uv run python -m bench.run \
      --manifest eval_data/asr_subset_beam_$lang.json \
      --candidate whisper-small-multilang-ct2-cpu \
      --out bench-results/whisper-small-multilang-ct2-cpu/$lang/beam-$beam \
      --config-override "{\"beam_size\": $beam}"
  done
done
```

Lý do tách process không đổi so với MT (cô lập RAM high-water mark, tránh cache candidate cũ giữ beam cũ) — 2 rủi ro này áp dụng y hệt cho mọi candidate/stage, không riêng gì Whisper. Lang giờ thêm 1 chiều lặp nữa, nhưng **không phải vì language cần cô lập process như beam_size** (language đọc theo item, không cache theo candidate) — tách thư mục kết quả theo `lang` chỉ để Bước 6 tổng hợp WER riêng từng chiều được gọn, không phải để né bug cache.

---

Bước 6 — Tổng hợp kết quả

Khác biệt quan trọng so với `aggregate_beam_sweep.py` gốc (viết cho BLEU): metric giờ là **WER — thấp hơn là tốt hơn**, ngược chiều với BLEU. Nếu dùng nguyên script cũ mà chỉ đổi tên field `bleu`→`wer`, phần Verdict sẽ suy luận sai chiều (tưởng WER tăng là cải thiện). Tổng quát hoá script để nhận `--metric` và tự đảo chiều so sánh, tránh phải giữ 2 bản trôi nhau như bài học từ old/new report trước đây.

```python
"""Aggregate beam-width sweep result directories, hỗ trợ cả bleu (higher-better)
và wer (lower-better)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

METRIC_DIRECTION = {"bleu": "higher", "wer": "lower"}


def load_records(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(records: list[dict], metric: str) -> dict:
    metric_vals = [
        r["metrics"][metric] for r in records if r["metrics"].get(metric) is not None
    ]
    lat_vals = [r["result"]["latency_s"] for r in records if not r["result"].get("error")]
    dur_vals = [r["metrics"].get("duration_s") for r in records if r["metrics"].get("duration_s")]
    ram_vals = [r["result"]["peak_ram_mb"] for r in records if r["result"].get("peak_ram_mb")]
    n_err = sum(1 for r in records if r["result"].get("error"))
    rtf = None
    if lat_vals and dur_vals and sum(dur_vals) > 0:
        rtf = sum(lat_vals) / sum(dur_vals)  # real-time factor: <1.0 = nhanh hơn thời lượng audio
    return {
        "n": len(records),
        "n_err": n_err,
        "metric": sum(metric_vals) / len(metric_vals) if metric_vals else None,
        "latency_s": sum(lat_vals) / len(lat_vals) if lat_vals else None,
        "rtf": rtf,
        "peak_ram_mb": max(ram_vals) if ram_vals else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-root", default="bench-results")
    ap.add_argument("--candidate", default="whisper-small-multilang-ct2-cpu")
    ap.add_argument("--lang", choices=["vi", "en"], help="chiều audio (ASR có 2 chiều)")
    ap.add_argument("--metric", choices=["bleu", "wer"], default="wer")
    ap.add_argument("--beams", type=int, nargs="+", default=[1, 2, 4, 5, 8])
    args = ap.parse_args()

    root = Path(args.results_root) / args.candidate
    if args.lang:
        root = root / args.lang
    rows: dict[int, dict] = {}
    for beam in args.beams:
        p = root / f"beam-{beam}" / "run_results.json"
        if not p.exists():
            print(f"  MISSING: {p} — chạy sweep cho beam={beam} trước")
            continue
        rows[beam] = summarize(load_records(p), args.metric)

    if 1 not in rows or rows[1]["latency_s"] is None:
        print("ERROR: thiếu baseline beam=1 (hoặc toàn lỗi) — không tính được relative latency")
        return

    baseline_latency = rows[1]["latency_s"]
    baseline_ram = rows[1]["peak_ram_mb"]
    direction = METRIC_DIRECTION[args.metric]

    print(f"{'Beam':<8} {args.metric.upper():>7} {'RTF':>7} {'Rel.latency':>12} {'ΔRAM(MB)':>10} {'Errors':>7}")
    print("-" * 58)
    for beam in args.beams:
        if beam not in rows:
            continue
        r = rows[beam]
        rel_lat = f"{r['latency_s'] / baseline_latency:.2f}x" if r["latency_s"] else "-"
        rtf_str = f"{r['rtf']:.2f}" if r["rtf"] is not None else "-"
        delta_ram = (
            f"{r['peak_ram_mb'] - baseline_ram:+.0f}"
            if r["peak_ram_mb"] is not None and baseline_ram is not None
            else "-"
        )
        metric_str = f"{r['metric']:.1f}" if r["metric"] is not None else "-"
        print(f"{beam:<8} {metric_str:>7} {rtf_str:>7} {rel_lat:>12} {delta_ram:>10} {r['n_err']:>7}")

    print(f"\n(direction: {args.metric} — {'cao hơn tốt hơn' if direction == 'higher' else 'thấp hơn tốt hơn'})")


if __name__ == "__main__":
    main()
```

Vì sao thêm cột **RTF (real-time factor)** — khác biệt so với MT: độ dài audio giữa các item ASR chênh lệch nhau nhiều hơn độ dài câu văn bản MT, nên "Rel. latency" trung bình đơn thuần có thể bị lệch bởi 1-2 item audio dài bất thường. RTF (latency giải mã / thời lượng audio, gộp theo tổng chứ không theo trung bình từng item) phản ánh đúng hơn "beam này có kịp thời gian thực không" — quan trọng vì đây là input trực tiếp cho ngân sách turnaround <2.0s tổng của pipeline.

Chạy riêng từng chiều — **không gộp chung 1 con số trung bình vi+en**, vì tiếng Anh và tiếng Việt thường có baseline WER khác nhau (đặc điểm ngữ âm, dữ liệu huấn luyện Whisper không cân bằng giữa 2 ngôn ngữ), gộp lại sẽ che mất khả năng beam tối ưu khác nhau giữa 2 chiều:

```bash
uv run python -m bench.aggregate_beam_sweep --lang vi --metric wer
uv run python -m bench.aggregate_beam_sweep --lang en --metric wer
```

---

Bước 7 — Điền bảng issue và viết Verdict cho từng chiều

Copy output Bước 6 vào issue — **2 bảng riêng biệt** (vi và en), vì đây là 2 tập dữ liệu khác nhau với baseline WER khác nhau:

Beam width	WER (vi)	RTF (vi)	Rel. latency (vi)	Verdict (vi)
1 (greedy)	(điền)	(điền)	1.0× (baseline)	
2	(điền)	(điền)	(điền)	
4	(điền)	(điền)	(điền)	
5	(điền)	(điền)	(điền)	
8	(điền)	(điền)	(điền)	

Beam width	WER (en)	RTF (en)	Rel. latency (en)	Verdict (en)
1 (greedy)	(điền)	(điền)	1.0× (baseline)	
2	(điền)	(điền)	(điền)	
4	(điền)	(điền)	(điền)	
5	(điền)	(điền)	(điền)	
8	(điền)	(điền)	(điền)	

Gợi ý viết Verdict cho từng bảng — **lưu ý chiều ngược với BLEU**:

- Beam nào giảm WER rõ rệt (>1 điểm phần trăm) mà relative latency vẫn <1.5× → "chấp nhận được".
- Beam nào WER gần như không đổi so với beam nhỏ hơn liền trước → "không đáng, lợi ích cận biên gần 0".
- Beam nào relative latency (hoặc RTF) vượt ngân sách turnaround <2.0s tổng (ASR chỉ 1 phần trong 3 stage) → "loại".

**Quan trọng — không giả định 2 chiều có cùng beam tối ưu.** Rất có thể vi cần beam cao hơn en (hoặc ngược lại) để đạt cùng mức cải thiện WER, do độ khó nhận diện khác nhau giữa 2 ngôn ngữ. Sau khi có cả 2 bảng, cần 1 quyết định sản phẩm rõ ràng:

- Nếu pipeline cho phép **cấu hình beam riêng theo chiều dịch** (vi audio dùng beam A, en audio dùng beam B) → chọn tối ưu độc lập cho từng bảng.
- Nếu hệ thống chỉ cho **1 giá trị beam_size chung** cho cả 2 chiều (đơn giản hoá vận hành) → phải chọn 1 beam thoả cả 2 ngân sách latency đồng thời, có thể phải hy sinh 1 phần WER của chiều "dễ" hơn để chiều "khó" hơn không vượt ngân sách. Ghi rõ trade-off này trong issue thay vì chỉ chọn theo bảng có WER đẹp hơn.

---

Bước 8 — Ghi chú caveat trước khi đóng phần Whisper

> Số liệu trên đo trên host (laptop), chưa phải điện thoại thật. Cần re-verify sau khi ADR-006 Android runner build xong, vì theo ADR-005 Decision 2, decoder (bao gồm beam search) luôn chạy CPU on-device — beam width tối ưu trên laptop có thể không còn tối ưu khi đổi sang CPU chậm hơn của điện thoại.
>
> Riêng Whisper: đã cố định `temperature=0` để tắt temperature fallback trong suốt sweep này. Nếu pipeline production của nhóm để mặc định (fallback bật), số liệu WER đo được ở đây **không phản ánh đúng hành vi thật khi deploy** — cần ghi rõ trong issue #88 rằng kết quả sweep giả định fallback tắt, và nhắc lại quyết định này trước khi đưa vào ADR-007 nếu production dùng cấu hình mặc định.
>
> **2 chiều vi/en:** nếu Bước 7 kết luận 2 chiều cần beam khác nhau nhưng hệ thống chỉ hỗ trợ 1 config chung, caveat này cần nêu rõ chiều nào bị đánh đổi WER để nhường ngân sách latency cho chiều kia — tránh việc quyết định trade-off âm thầm nằm trong code mà không ai trong nhóm biết để review lại khi đổi model/threshold sau này.

---

## Phần 2 — Moonshine Tiny (en + vi)

> **Khác biệt cấu trúc quan trọng so với Whisper:** Moonshine (dòng "Flavors of Moonshine",
> 2025) là **các model đơn ngữ riêng biệt**, không phải 1 model đa ngôn ngữ với tham số
> `language=` runtime. `moonshine-tiny` (gốc, tiếng Anh) và `moonshine-tiny-vi` (tiếng Việt) là
> **2 bộ trọng số khác nhau hoàn toàn**. Do đó không tái dùng được pattern "1 candidate ID, đổi
> `language` theo item" như Whisper — cần **2 candidate ID riêng**, mỗi cái load đúng 1 bộ trọng số.
>
> **Chưa xác nhận CT2 hoạt động** — theo yêu cầu, guide này viết giả định CT2 dùng được, nhưng
> **bắt buộc chạy Bước M0 (gate) trước khi đầu tư viết candidate đầy đủ**, học từ bài học Hy-MT
> (`hymt-ct2-blockers.md`): đã từng giả định `ct2-transformers-converter` chạy được cho mọi model
> HF rồi mới phát hiện block giữa chừng do kiến trúc không tương thích. Với Moonshine, PR hỗ trợ CT2
> (OpenNMT/CTranslate2#1808) chỉ xác nhận cho `moonshine-tiny`/`moonshine-base` gốc (tiếng Anh) —
> **chưa có bằng chứng** rằng bản `moonshine-tiny-vi` (kiến trúc/dòng release mới hơn) đã được convert
> hay tương thích với cùng 1 spec CT2 đó. Repo chính thức hiện tại (`moonshine-ai/moonshine`) còn dùng
> ONNX Runtime (.ort) làm định dạng chính, không phải CT2 — dấu hiệu cho thấy CT2 có thể chỉ là 1
> nhánh phụ, không được maintain song song với bản chính.

### Bước M0 — Gate: xác nhận CT2 khả thi cho cả 2 bộ trọng số (làm trước tiên)

```bash
uv run python -c "import ctranslate2; print(ctranslate2.__version__)"
# Kiểm tra CHANGELOG/release notes CT2 xem PR #1808 đã vào bản pip release nào chưa —
# nếu chưa, có thể phải build CTranslate2 từ source mới có Moonshine support.
```

Thử convert/tải model CT2 cho tiếng Anh trước (đã có sẵn theo PR, rủi ro thấp hơn):

```bash
# Model CT2 đã convert sẵn, theo PR #1808:
# https://huggingface.co/UsefulSensors/moonshine/tree/main/ctranslate2
uv run python -c "
import ctranslate2
print([x for x in dir(ctranslate2.models) if 'oonshine' in x.lower() or 'Whisper' in x])
"
```

Nếu class Python cho Moonshine tồn tại (tên chính xác cần xác nhận thực nghiệm — có thể là
`ctranslate2.models.Whisper`-compatible hoặc 1 class riêng), thử load + infer 1 câu tiếng Anh. **Chỉ
sau khi bước này pass mới thử tiếp với `moonshine-tiny-vi`:**

```bash
uv run ct2-transformers-converter \
  --model UsefulSensors/moonshine-tiny-vi \
  --output_dir models/moonshine-tiny-vi-ct2-int8 \
  --quantization int8
```

Nếu bước convert cho `-vi` báo lỗi kiến trúc không nhận diện được (giống `ValueError: No conversion
is registered...` đã gặp với Hy-MT) → dừng lại, viết 1 file blocker tương tự
`hymt-ct2-blockers.md`, và cân nhắc phương án B: chuyển sang ONNX Runtime trực tiếp theo repo chính
thức (`moonshine-ai/moonshine`, định dạng `.ort`) — khi đó Bước M1 bên dưới cần viết lại hoàn toàn
theo `onnxruntime` API, không phải `ctranslate2`. Đừng viết tiếp Bước M2 trở đi cho đến khi gate này
pass, để tránh lặp lại việc đầu tư công sức vào 1 hướng có thể bị chặn giữa chừng.

### Bước M1 — Candidate: `bench/candidates/moonshine_asr.py` (giả định CT2 pass gate)

```python
class MoonshineTinyENCandidate(Candidate):
    stage = "ASR"
    id = "moonshine-tiny-en-ct2-cpu"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        import ctranslate2

        cfg = config or {}
        self._decode_kwargs = dict(
            beam_size=cfg.get("beam_size", 5),
            # Tên tham số khác cần đối chiếu lại API thật của class CT2 Moonshine
            # (chưa xác nhận — xem Bước M0). Whisper-style CT2 dùng "beam_size" trong
            # generate(); nếu class Moonshine khác, đổi lại cho khớp.
        )
        model_dir = Path(model_path) if model_path else MOONSHINE_EN_MODEL_DIR
        self.model = ...  # class CT2 thật, xác nhận ở Bước M0

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        if getattr(item, "language", None) != "en":
            return None, f"MoonshineTinyENCandidate nhận nhầm item không phải en: {item.id}"
        audio_path = item.resolve_input()
        # ... gọi decode theo API thật, trả transcript
        return transcript, None


class MoonshineTinyVICandidate(Candidate):
    stage = "ASR"
    id = "moonshine-tiny-vi-ct2-cpu"
    # Cấu trúc y hệt bản EN, chỉ khác model_dir và guard language == "vi".
    # KHÔNG gộp chung 1 class rồi if/else chọn model theo item.language — vì mỗi
    # candidate instance chỉ nên load 1 bộ trọng số (đúng tinh thần "1 candidate =
    # 1 model cố định" đã áp dụng xuyên suốt guide, tránh nhầm lẫn khi cache theo cid).
```

Vì sao **2 class riêng thay vì 1 class + if/else theo `item.language`**: nếu gộp chung, 1 candidate
instance sẽ phải giữ **2 model trong RAM cùng lúc** (vì `run_manifest()` cache theo `cid`, dùng lại
cho mọi item có cùng `cid` bất kể ngôn ngữ) — làm sai lệch số đo RAM so với thực tế deploy (production
chỉ load 1 model tương ứng 1 chiều tại 1 thời điểm, không load cả 2 cùng lúc). Tách 2 candidate ID
đảm bảo mỗi lần sweep chỉ có đúng 1 bộ trọng số trong RAM, khớp với kịch bản thật.

### Bước M2–M8 — Áp dụng lại pattern Whisper, với 2 điều chỉnh

- **Filter manifest**: dùng lại `--lang vi`/`--lang en` như Bước 3 (đã có sẵn), không cần sửa thêm.
- **Sweep loop**: khác Whisper — giờ lặp theo **cặp (lang, candidate_id) cố định**, không phải 1
  candidate + lang thay đổi per-item:

```bash
mkdir -p bench-results
for pair in "vi:moonshine-tiny-vi-ct2-cpu" "en:moonshine-tiny-en-ct2-cpu"; do
  lang="${pair%%:*}"; cand="${pair##*:}"
  for beam in 1 2 4 5 8; do
    uv run python -m bench.run \
      --manifest "eval_data/asr_subset_beam_$lang.json" \
      --candidate "$cand" \
      --out "bench-results/$cand/beam-$beam" \
      --config-override "{\"beam_size\": $beam}"
  done
done
```

- Bước 6 (aggregate) chạy với `--candidate moonshine-tiny-vi-ct2-cpu` và `--candidate
  moonshine-tiny-en-ct2-cpu` riêng biệt (bỏ `--lang`, vì giờ ngôn ngữ đã nằm trong `--candidate`).
- Caveat Bước 8 giữ nguyên toàn bộ + thêm: **RAM giữa 2 chiều không so sánh trực tiếp được** như
  Whisper (1 model, 1 baseline RAM cho cả 2 chiều) — Moonshine-EN và Moonshine-VI có thể có kích
  thước/kiến trúc hơi khác nhau (huấn luyện riêng), nên baseline RAM lệch giữa 2 chiều là bình
  thường, không phải bug đo — khác hẳn tình huống ΔRAM đáng ngờ đã điều tra với M2M-100.

---

## Phần 3 — Zipformer (transducer, sherpa-onnx)

> Checkpoint xác nhận qua sherpa-onnx model zoo: **vi** — `hynt/Zipformer-30M-RNNT-6000h`
> (`sherpa-onnx-zipformer-vi-30M-int8-2026-02-09`, 30M tham số, 6000h dữ liệu tiếng Việt); **en** —
> `csukuangfj/sherpa-onnx-zipformer-en-2023-06-26` (offline transducer, có bản `small`/`large`).
> **Đây cũng là 2 checkpoint đơn ngữ riêng biệt**, không có bản song ngữ vi-en trong model zoo (chỉ
> vài cặp khác như zh-en tồn tại) — cùng tình huống với Moonshine, khác Whisper.
>
> **Lưu ý chọn checkpoint EN**: bản vi là 30M tham số — nếu chọn bản `large-en` (kích thước lớn hơn
> nhiều so với 30M) sẽ khiến so sánh RAM/latency giữa 2 chiều không công bằng (giống kiểu chênh lệch
> M2M-100 vs Opus-MT, nhưng lần này là giữa 2 chiều của **cùng 1 model** thay vì giữa 2 model). Nên ưu
> tiên bản `small-en` hoặc bản có tham số gần 30M nhất để giữ so sánh 2 chiều công bằng — nếu không có
> bản khớp size, ghi rõ caveat chênh lệch kích thước khi báo cáo, đừng so RAM/latency 2 chiều trực tiếp.

### Bước Z0 — Runtime hoàn toàn khác: sherpa-onnx, không phải CTranslate2

```bash
pip install sherpa-onnx --break-system-packages
uv run python -c "import sherpa_onnx; print(sherpa_onnx.__version__)"

wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09.tar.bz2
tar xvf sherpa-onnx-zipformer-vi-30M-int8-2026-02-09.tar.bz2

# tải bản EN tương ứng (chọn size theo lưu ý ở trên), ví dụ:
wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-zipformer-small-en-2023-06-26.tar.bz2
tar xvf sherpa-onnx-zipformer-small-en-2023-06-26.tar.bz2
```

### Bước Z1 — Candidate: `bench/candidates/zipformer_asr.py`

Khái niệm "beam" khác hẳn CT2: `modified_beam_search` dùng `max_active_paths`, không phải
`beam_size`. Để tái dùng nguyên xi cơ chế `--config-override '{"beam_size": N}'` đã xây cho MT/Whisper
(không phải sửa `run.py`/`aggregate_beam_sweep.py` thêm lần nữa), candidate tự **map** `beam_size` từ
config sang `max_active_paths` nội bộ — giữ tên khoá `beam_size` ở tầng config-override để nhất quán
xuyên suốt toàn bộ hệ thống sweep, chỉ đổi tên khi gọi vào sherpa-onnx.

```python
class ZipformerCandidateBase(Candidate):
    stage = "ASR"
    _model_dir_attr: str  # override ở subclass
    _expected_lang: str   # "vi" hoặc "en"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        import sherpa_onnx

        cfg = config or {}
        beam = cfg.get("beam_size", 4)
        # beam=1 dùng greedy_search thật (không phải modified_beam_search với
        # max_active_paths=1) — 2 thuật toán khác nhau, "beam=1" của transducer
        # đúng nghĩa nhất là chạy greedy, không phải beam search với độ rộng 1.
        # Ghi rõ trong bảng kết quả đây là quy ước, không phải tương đương toán học
        # với beam=1 của Whisper/MT.
        decoding_method = "greedy_search" if beam == 1 else "modified_beam_search"

        model_dir = Path(model_path) if model_path else Path(self._model_dir_attr)
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(model_dir / "encoder.int8.onnx"),
            decoder=str(model_dir / "decoder.onnx"),
            joiner=str(model_dir / "joiner.int8.onnx"),
            tokens=str(model_dir / "tokens.txt"),
            decoding_method=decoding_method,
            max_active_paths=beam,  # bị bỏ qua nếu decoding_method="greedy_search"
            provider="cpu",
        )

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        if getattr(item, "language", None) != self._expected_lang:
            return None, f"{type(self).__name__} nhận nhầm item khác ngôn ngữ: {item.id}"
        audio_path = item.resolve_input()
        stream = self.recognizer.create_stream()
        samples, sample_rate = load_wav(audio_path)  # đọc mono float32, đúng sample_rate model yêu cầu
        stream.accept_waveform(sample_rate, samples)
        self.recognizer.decode_stream(stream)
        return stream.result.text, None


class ZipformerVICandidate(ZipformerCandidateBase):
    id = "zipformer-vi-30m-sherpa-onnx-cpu"
    _model_dir_attr = "models/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09"
    _expected_lang = "vi"


class ZipformerENCandidate(ZipformerCandidateBase):
    id = "zipformer-small-en-sherpa-onnx-cpu"
    _model_dir_attr = "models/sherpa-onnx-zipformer-small-en-2023-06-26"
    _expected_lang = "en"
```

Vì sao guard `_expected_lang` giống Moonshine: cùng lý do — mỗi candidate chỉ nên gánh đúng 1 bộ
trọng số/1 ngôn ngữ, tránh nạp nhầm audio sai chiều vào model không được huấn luyện cho ngôn ngữ đó
(lỗi này sẽ cho WER cực cao, dễ nhầm là do beam thấp).

### Bước Z2–Z8 — Áp dụng lại pattern, thêm 2 lưu ý runtime riêng

- Sweep loop giống hệt cấu trúc Moonshine (Bước M2, lặp theo cặp lang:candidate_id cố định), đổi tên
  candidate ID.
- **Cột "Beam" trong bảng kết quả (Bước 7) nên đổi nhãn thành "Beam (max_active_paths)"** và ghi chú
  dòng beam=1 là "greedy_search — không tương đương toán học với modified_beam_search
  max_active_paths=1", để người đọc sau này (kể cả tự mình đọc lại vài tháng sau) không hiểu nhầm 2
  cơ chế là cùng 1 thuật toán chỉ khác độ rộng.
- **Runtime hoàn toàn tách biệt CTranslate2** — nghĩa là RAM/latency của Zipformer **không so sánh
  trực tiếp công bằng** với Whisper/Moonshine/MT (khác cơ chế cấp phát bộ nhớ hoàn toàn, bài học từ
  cuộc điều tra ΔRAM/workspace CT2 không áp dụng được cho sherpa-onnx — cần điều tra riêng nếu nghi
  ngờ tương tự xảy ra ở đây). Ghi rõ trong Bước 8 rằng so sánh chéo giữa Zipformer và 3 candidate CT2
  kia chỉ nên dừng ở WER, không nên so RAM/latency ngang hàng nếu chưa kiểm chứng cơ chế đo tương
  đương.
- Về việc chưa xác định checkpoint từ đầu: nếu sau này đổi sang checkpoint EN khác (vd. đổi từ
  `small` sang `large` để tăng chất lượng), phải chạy lại **toàn bộ** sweep 2 chiều từ đầu — không
  tái dùng được số liệu cũ, vì thay checkpoint là thay đổi biến số khác hẳn beam_size.
