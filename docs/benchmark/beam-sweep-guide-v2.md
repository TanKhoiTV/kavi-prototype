Chi tiết đầy đủ — Giai đoạn 1 (sweep beam width trên host/laptop, áp dụng cho Opus-MT / M2M-100 / Hy-MT)

> Bản gộp thay thế `beam-sweep-guide.md` (chỉ Opus-MT). Các bước 0, 2–8 dùng chung cho cả 3 candidate.
> Chỉ Bước 1 khác nhau về kiến trúc — xem đúng mục con theo model bạn đang thêm.

---

Bước 0 — Kiểm tra trước khi bắt đầu

```bash
ls eval_data/eval_manifest_v1.json    # phải tồn tại (từ make bench-data)
uv run python -c "import ctranslate2; print(ctranslate2.__version__)"
uv run python -c "import transformers; print(transformers.__version__)"   # cần cho Hy-MT (tokenizer HF)
```

Xác nhận CTranslate2 version hỗ trợ `Generator.generate_batch(..., include_prompt_in_result=False)` — cần cho Hy-MT (xem Bước 1c). Nếu version cũ không có tham số này, phải tự cắt prompt khỏi output bằng tay trong `_infer()`.

Xác nhận manifest có item MT với reference_text không rỗng (BLEU sẽ không tính được nếu thiếu):

```bash
uv run python -c "
from bench.schema import RunManifest
m = RunManifest.from_json('eval_data/eval_manifest_v1.json')
mt = [i for i in m.items if i.stage == 'MT']
print(f'{len(mt)} MT items, {sum(1 for i in mt if i.reference_text)} có reference_text')
"
```

---

Bước 1 — Implement candidate cho từng model

Nguyên tắc chung bắt buộc cho cả 3 (đây chính là điều kiện để --config-override hoạt động đúng): `beam_size` phải đọc từ `config` ở cấp **instance** (`__init__`), không hard-code cấp class. Các tham số khác (repetition_penalty, no_repeat_ngram_size, max length) giữ cố định để sweep chỉ đổi đúng 1 biến số.

### 1a. Opus-MT — `bench/candidates/opusmt_mt.py`

Encoder-decoder, `ctranslate2.Translator`, SentencePiece riêng cho source/target.

```python
class OpusMTMTCandidate(Candidate):
    stage = "MT"
    id = "opus-mt-vi-en-ct2-cpu"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        import ctranslate2
        import sentencepiece as spm

        cfg = config or {}
        self._decode_kwargs = dict(
            beam_size=cfg.get("beam_size", 4),
            repetition_penalty=1.1,
            no_repeat_ngram_size=3,
            max_decoding_length=256,
        )

        model_dir = Path(model_path) if model_path else MT_MODEL_DIR
        if not model_dir.exists():
            raise FileNotFoundError(f"MT model not found at {model_dir}")
        self.translator = ctranslate2.Translator(
            str(model_dir), device="cpu", compute_type="int8"
        )
        self.sp_src = spm.SentencePieceProcessor()
        self.sp_src.load(str(MT_SRC_DIR / "source.spm"))  # pyright: ignore[reportAttributeAccessIssue]
        self.sp_tgt = spm.SentencePieceProcessor()
        self.sp_tgt.load(str(MT_SRC_DIR / "target.spm"))  # pyright: ignore[reportAttributeAccessIssue]

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        text = item.resolve_input()
        tokens = self.sp_src.encode(text, out_type=str)  # pyright: ignore[reportAttributeAccessIssue]
        results = self.translator.translate_batch([tokens], **self._decode_kwargs)
        translation = self.sp_tgt.decode(results[0].hypotheses[0])  # pyright: ignore[reportAttributeAccessIssue]
        return translation, None
```

### 1b. M2M-100 — `bench/candidates/m2m_mt.py`

Cũng encoder-decoder, cũng `ctranslate2.Translator`, nhưng **multilingual** — bắt buộc phải ép ngôn ngữ đích bằng `target_prefix`, khác Opus-MT (vốn chỉ dịch 1 cặp ngôn ngữ cố định nên không cần token ngôn ngữ đích).

```python
class M2M100MTCandidate(Candidate):
    stage = "MT"
    id = "m2m100-vi-en-ct2-cpu"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        import ctranslate2
        from transformers import AutoTokenizer

        cfg = config or {}
        self._decode_kwargs = dict(
            beam_size=cfg.get("beam_size", 4),
            repetition_penalty=1.1,
            no_repeat_ngram_size=3,
            max_decoding_length=256,
        )

        model_dir = Path(model_path) if model_path else M2M_MODEL_DIR
        if not model_dir.exists():
            raise FileNotFoundError(f"M2M-100 model not found at {model_dir}")
        self.translator = ctranslate2.Translator(
            str(model_dir), device="cpu", compute_type="int8"
        )
        # M2M-100 dùng tokenizer HF gốc (không phải 2 file .spm riêng như Opus-MT)
        self.tokenizer = AutoTokenizer.from_pretrained(
            "facebook/m2m100_418M", src_lang="vi"
        )

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        text = item.resolve_input()
        tokens = self.tokenizer.convert_ids_to_tokens(self.tokenizer.encode(text))
        # QUAN TRỌNG: target_prefix ép ngôn ngữ đích — thiếu dòng này M2M-100
        # có thể dịch sang ngôn ngữ khác tiếng Anh, không liên quan gì đến beam_size.
        target_prefix = [[self.tokenizer.lang_code_to_token["en"]]]
        results = self.translator.translate_batch(
            [tokens], target_prefix=target_prefix, **self._decode_kwargs
        )
        translation = self.tokenizer.decode(
            self.tokenizer.convert_tokens_to_ids(results[0].hypotheses[0][1:])  # bỏ token lang ở đầu output
        )
        return translation, None
```

### 1c. Hy-MT (`tencent/HY-MT1.5-1.8B`) — `bench/candidates/hymt_mt.py`

**Khác kiến trúc hoàn toàn**: decoder-only causal LM, dịch bằng prompt instruction chứ không phải encoder-decoder. Dùng `ctranslate2.Generator` (không phải `Translator`), tokenizer HF, và phải cắt prompt khỏi output.

Convert model 1 lần trước khi dùng:

```bash
uv run ct2-transformers-converter \
  --model tencent/HY-MT1.5-1.8B \
  --output_dir models/hy-mt1.5-1.8b-ct2-int8 \
  --quantization int8 \
  --copy_files tokenizer.json tokenizer_config.json special_tokens_map.json
```

```python
class HyMTCandidate(Candidate):
    stage = "MT"
    id = "hy-mt1.5-1.8b-ct2-cpu"

    PROMPT_TEMPLATE = (
        "Translate the following segment into {target_language}, "
        "without additional explanation: {source_text}"
    )

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        import ctranslate2
        from transformers import AutoTokenizer

        cfg = config or {}
        self._decode_kwargs = dict(
            beam_size=cfg.get("beam_size", 4),
            repetition_penalty=1.1,
            no_repeat_ngram_size=3,
            max_length=256,
            include_prompt_in_result=False,  # cắt prompt khỏi output — bắt buộc, xem cảnh báo dưới
        )

        model_dir = Path(model_path) if model_path else HYMT_MODEL_DIR
        if not model_dir.exists():
            raise FileNotFoundError(f"Hy-MT model not found at {model_dir}")
        self.generator = ctranslate2.Generator(
            str(model_dir), device="cpu", compute_type="int8"
        )
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir))

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        text = item.resolve_input()
        prompt = self.PROMPT_TEMPLATE.format(target_language="English", source_text=text)
        tokens = self.tokenizer.convert_ids_to_tokens(self.tokenizer.encode(prompt))
        results = self.generator.generate_batch([tokens], **self._decode_kwargs)
        translation = self.tokenizer.decode(
            self.tokenizer.convert_tokens_to_ids(results[0].sequences[0])
        )
        return translation, None
```

⚠️ Cảnh báo riêng cho Hy-MT (không áp dụng cho 2 model kia):
- Nếu quên `include_prompt_in_result=False` (hoặc bản CTranslate2 không hỗ trợ), output dính nguyên cả prompt → BLEU tụt thê thảm, trông giống "model kém" nhưng thực ra là lỗi đo, không liên quan beam_size.
- Template prompt phải khớp đúng format gốc trong repo Hy-MT — sai template làm giảm chất lượng dịch thật, dễ nhầm lẫn với ảnh hưởng của beam width.
- Model 1.8B nặng hơn hẳn Opus-MT/M2M-100 (418M) → cần theo dõi thêm RAM tuyệt đối, không chỉ Δ (xem Bước 6).

---

Bước 2 — Thêm --config-override vào bench/run.py

Không đổi so với `beam-sweep-guide.md` gốc — logic này model-agnostic vì `build_candidate()` trong `registry.py` đọc `item.config` cho mọi candidate như nhau.

```python
def run_manifest(
    manifest: RunManifest,
    out_dir: Path,
    candidate_filter: str | None,
    config_override: dict | None = None,
) -> list[dict]:
    records: list[dict] = []
    candidates: dict[str, Candidate] = {}
    for item in manifest.items:
        if config_override:
            item.config = {**item.config, **config_override}

        cid = item.candidate_id
        if cid is None:
            cid = default_candidate_id_for_stage(item.stage)
        cid_label = cid
        if cid_label is None:
            cid_label = "unknown"
        elif cid != candidate_filter:
            continue
        try:
            cached = None
            if cid is not None:
                cached = candidates.get(cid)
            if cached is not None:
                candidate = cached
            else:
                candidate = build_candidate(item)
                if hasattr(candidate, "out_dir"):
                    candidate.out_dir = str(out_dir / "outputs")
                if cid is not None:
                    candidates[cid] = candidate
            result = candidate.run(item)
        except Exception as exc:  # noqa: BLE001
            result = StageResult(
                candidate_id=cid_label,
                item_id=item.id,
                stage=item.stage,
                error=f"{type(exc).__name__}: {exc}",
            )

        duration = None
        if item.stage == "ASR":
            duration = audio_duration(item.audio_ref)
        elif item.stage == "TTS":
            duration = audio_duration(result.output_audio_path)

        metrics = score_item(item, result, duration)
        records.append(
            {
                "item": asdict(item),
                "result": asdict(result),
                "metrics": asdict(metrics),
            }
        )
    return records
```

`main()` giữ nguyên như bản gốc (đọc `--config-override` bằng `json.loads`).

---

Bước 3 — Lọc bộ MT nhỏ để sweep nhanh (bench/filter_manifest.py)

Không đổi — dùng chung cho cả 3 model, vì filter theo `stage` không phụ thuộc engine.

```bash
uv run python -m bench.filter_manifest \
  --stage MT --limit 30 \
  --out eval_data/mt_subset_beam.json
```

---

Bước 4 — Smoke test trước khi chạy full

Chung cho cả 3: 3 câu, 2 beam width.

```bash
uv run python -m bench.filter_manifest --stage MT --limit 3 --out /tmp/mt_smoke.json

for cand in opus-mt-vi-en-ct2-cpu m2m100-vi-en-ct2-cpu hy-mt1.5-1.8b-ct2-cpu; do
  for beam in 1 2; do
    uv run python -m bench.run \
      --manifest /tmp/mt_smoke.json \
      --candidate "$cand" \
      --out "/tmp/beam-smoke-$cand-$beam" \
      --config-override "{\"beam_size\": $beam}"
  done
done
```

Kiểm tra thêm riêng theo model (bổ sung so với bản gốc, vì đây là 2 lỗi hay gặp không liên quan gì đến beam_size nhưng dễ lẫn với "model kém"):

- **M2M-100**: in raw output của smoke test, xác nhận output là tiếng Anh (không lẫn ngôn ngữ khác) — nếu sai, kiểm tra lại `target_prefix`.
- **Hy-MT**: in raw output, xác nhận **không còn dính câu prompt** trong kết quả — nếu còn, kiểm tra `include_prompt_in_result` hoặc version CTranslate2.

```bash
uv run python -c "
from bench.candidates.hymt_mt import HyMTCandidate
c = HyMTCandidate(config={'beam_size': 1})
out, _ = c._infer(item)  # item mẫu 1 câu
print(repr(out))
"
```

Kiểm tra `print_table()` in ra đúng cột BLEU, không có dòng error cho cả 3 candidate — nếu ổn mới chạy full ở Bước 5.

---

Bước 5 — Chạy sweep thật, mỗi (model, beam width) là 1 process riêng biệt

Lặp thêm 1 chiều so với bản chỉ-Opus-MT: model × beam. Kết quả tách thư mục theo candidate để không đè lẫn nhau.

```bash
mkdir -p bench-results
for cand in opus-mt-vi-en-ct2-cpu m2m100-vi-en-ct2-cpu hy-mt1.5-1.8b-ct2-cpu; do
  for beam in 1 2 4 5 8; do
    echo "=== candidate=$cand beam_size=$beam ==="
    uv run python -m bench.run \
      --manifest eval_data/mt_subset_beam.json \
      --candidate "$cand" \
      --out "bench-results/$cand/beam-$beam" \
      --config-override "{\"beam_size\": $beam}"
  done
done
```

Vì sao bắt buộc tách process (không đổi so với bản gốc, áp dụng cho cả 3 model như nhau):

- **Cô lập RAM** — `peak_ram_mb()` là high-water mark của toàn process, không tự reset.
- **Tránh cache candidate cũ** — `candidates` dict trong `run_manifest()` cache theo `cid`, không phân biệt theo config. Gọi lại trong cùng process với config khác sẽ âm thầm tái sử dụng candidate cũ (beam cũ), không báo lỗi. Đây chính là Root Cause 1 trong `beam-sweep-retrospective.md` — rủi ro như nhau cho cả 3 model, không riêng gì Opus-MT.

---

Bước 6 — Tổng hợp kết quả (bench/aggregate_beam_sweep.py)

Khác so với bản gốc: script giờ cần tham số `--candidate` (thay vì hard-code `beam-{beam}` ở root), và nên in báo cáo cho từng model **cộng thêm** 1 bảng so sánh chéo giữa 3 model tại cùng beam width.

```python
"""Aggregate beam-width sweep result directories into the issue #88 table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_records(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(records: list[dict]) -> dict:
    bleu_vals = [
        r["metrics"]["bleu"] for r in records if r["metrics"].get("bleu") is not None
    ]
    lat_vals = [r["result"]["latency_s"] for r in records if not r["result"].get("error")]
    ram_vals = [r["result"]["peak_ram_mb"] for r in records if r["result"].get("peak_ram_mb")]
    n_err = sum(1 for r in records if r["result"].get("error"))
    return {
        "n": len(records),
        "n_err": n_err,
        "bleu": sum(bleu_vals) / len(bleu_vals) if bleu_vals else None,
        "latency_s": sum(lat_vals) / len(lat_vals) if lat_vals else None,
        "peak_ram_mb": max(ram_vals) if ram_vals else None,  # tuyệt đối — quan trọng cho Hy-MT (1.8B)
    }


def load_candidate_rows(root: Path, candidate: str, beams: list[int]) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for beam in beams:
        p = root / candidate / f"beam-{beam}" / "run_results.json"
        if not p.exists():
            print(f"  MISSING: {p} — chạy sweep cho {candidate} beam={beam} trước")
            continue
        rows[beam] = summarize(load_records(p))
    return rows


def print_candidate_table(candidate: str, rows: dict[int, dict], beams: list[int]) -> None:
    if 1 not in rows or rows[1]["latency_s"] is None:
        print(f"ERROR ({candidate}): thiếu baseline beam=1 (hoặc toàn lỗi) — bỏ qua model này")
        return

    baseline_latency = rows[1]["latency_s"]
    baseline_ram = rows[1]["peak_ram_mb"]

    print(f"\n== {candidate} ==")
    print(f"{'Beam':<8} {'BLEU':>7} {'Rel.latency':>12} {'ΔRAM(MB)':>10} {'RAM abs(MB)':>12} {'Errors':>7}")
    print("-" * 62)
    for beam in beams:
        if beam not in rows:
            continue
        r = rows[beam]
        rel_lat = f"{r['latency_s'] / baseline_latency:.2f}x" if r["latency_s"] else "-"
        delta_ram = (
            f"{r['peak_ram_mb'] - baseline_ram:+.0f}"
            if r["peak_ram_mb"] is not None and baseline_ram is not None
            else "-"
        )
        ram_abs = f"{r['peak_ram_mb']:.0f}" if r["peak_ram_mb"] is not None else "-"
        bleu_str = f"{r['bleu']:.1f}" if r["bleu"] is not None else "-"
        print(f"{beam:<8} {bleu_str:>7} {rel_lat:>12} {delta_ram:>10} {ram_abs:>12} {r['n_err']:>7}")


def print_cross_model_table(all_rows: dict[str, dict[int, dict]], beams: list[int]) -> None:
    print("\n== So sánh chéo BLEU giữa các model (theo beam width) ==")
    header = f"{'Beam':<8}" + "".join(f"{cand:>28}" for cand in all_rows)
    print(header)
    for beam in beams:
        line = f"{beam:<8}"
        for cand in all_rows:
            r = all_rows[cand].get(beam)
            bleu_str = f"{r['bleu']:.1f}" if r and r.get("bleu") is not None else "-"
            line += f"{bleu_str:>28}"
        print(line)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-root", default="bench-results")
    ap.add_argument(
        "--candidates",
        nargs="+",
        default=["opus-mt-vi-en-ct2-cpu", "m2m100-vi-en-ct2-cpu", "hy-mt1.5-1.8b-ct2-cpu"],
    )
    ap.add_argument("--beams", type=int, nargs="+", default=[1, 2, 4, 5, 8])
    args = ap.parse_args()

    root = Path(args.results_root)
    all_rows: dict[str, dict[int, dict]] = {}
    for cand in args.candidates:
        rows = load_candidate_rows(root, cand, args.beams)
        all_rows[cand] = rows
        print_candidate_table(cand, rows, args.beams)

    print_cross_model_table(all_rows, args.beams)


if __name__ == "__main__":
    main()
```

Chạy:

```bash
uv run python -m bench.aggregate_beam_sweep
```

Vì sao thêm cột RAM tuyệt đối (không chỉ Δ như bản gốc): với Opus-MT/M2M-100, phần RAM cố định để load model gần như nhau nên Δ đủ để so sánh. Nhưng Hy-MT (1.8B) có RAM nền cao hơn hẳn — nếu chỉ nhìn Δ, model có thể "trông rẻ" trong khi tổng RAM tuyệt đối đã vượt ngân sách thiết bị target ngay ở beam=1. Cần cả 2 con số để quyết định loại sớm.

---

Bước 7 — Điền vào bảng issue #88 và viết Verdict

Copy output Bước 6 vào issue — mỗi model 1 bảng riêng, cộng thêm bảng so sánh chéo BLEU. Ví dụ khung bảng cho từng model:

Beam width	Quality metric (BLEU)	Relative decode latency	Peak KV-cache memory (Δ)	Peak RAM tuyệt đối (MB)	Verdict
1 (greedy)	(điền)	1.0× (baseline)	—	(điền)	
2	(điền)	(điền)	(điền)	(điền)	
4	(điền)	(điền)	(điền)	(điền)	
5	(điền)	(điền)	(điền)	(điền)	
8	(điền)	(điền)	(điền)	(điền)	

Gợi ý viết Verdict (không đổi nguyên tắc so với bản gốc, áp dụng cho cả 3 model):

- Beam nào tăng BLEU rõ rệt (>1 điểm) mà relative latency vẫn <1.5× → "chấp nhận được".
- Beam nào BLEU gần như không đổi so với beam nhỏ hơn liền trước → "không đáng".
- Beam nào relative latency vượt ngân sách turnaround <2.0s tổng (MT chỉ 1 phần trong 3 stage) → "loại".
- **Riêng cho model nặng (Hy-MT)**: nếu RAM tuyệt đối ở beam=1 đã sát/vượt ngân sách thiết bị target → "loại toàn bộ model, không cần sweep beam cao hơn" (loại sớm, không đợi đến beam=8 mới kết luận).

Verdict cuối issue nên chọn 1 cặp (model, beam) tốt nhất tổng thể, không chỉ tốt nhất trong từng model riêng lẻ.

---

Bước 8 — Ghi chú caveat trước khi đóng Giai đoạn 1

Thêm 1 dòng comment vào issue, áp dụng cho cả 3 model nhưng nhấn mạnh riêng phần khác biệt:

> Số liệu trên đo trên host (laptop), chưa phải điện thoại thật. Cần re-verify sau khi ADR-006 Android runner build xong, vì theo ADR-005 Decision 2, decoder (bao gồm beam search) luôn chạy CPU on-device — beam width tối ưu trên laptop có thể không còn tối ưu khi đổi sang CPU chậm hơn của điện thoại. **Riêng Hy-MT (1.8B)**: chênh lệch kích thước với Opus-MT/M2M-100 (418M) có thể khiến rel. latency on-device lệch xa hơn nhiều so với đo trên laptop — ưu tiên re-verify model này trước khi đưa vào ADR-007 nếu ngân sách thiết bị target eo hẹp.

---

## Tóm tắt khác biệt so với `beam-sweep-guide.md` gốc

| Phần | Opus-MT (gốc) | M2M-100 | Hy-MT |
|---|---|---|---|
| Runtime CT2 | `Translator` | `Translator` | `Generator` |
| Tokenizer | 2× SentencePiece riêng | HF tokenizer + `target_prefix` | HF tokenizer + prompt template |
| Rủi ro riêng | — | quên `target_prefix` → sai ngôn ngữ đích | quên cắt prompt → BLEU sai; RAM nền cao hơn hẳn |
| Bước 0/2/3/5/6/7/8 | dùng chung | dùng chung | dùng chung |
