Chi tiết đầy đủ — Giai đoạn 1 (sweep beam width trên host/laptop)

Bước 0 — Kiểm tra trước khi bắt đầu

```bash
ls eval_data/eval_manifest_v1.json    # phải tồn tại (từ make bench-data)
uv run python -c "import ctranslate2; print(ctranslate2.__version__)"
```

Xác nhận manifest có item MT với reference_text không rỗng (BLEU sẽ không tính được nếu thiếu):

```bash
uv run python -c "
from bench.schema import RunManifest
m = RunManifest.from_json('eval_data/eval_manifest_v1.json')
mt = [i for i in m.items if i.stage == 'MT']
print(f'{len(mt)} MT items, {sum(1 for i in mt if i.reference_text)} có reference_text')
"
```

Bước 1 — Sửa bench/candidates/opusmt_mt.py để beam_size đọc được từ config

File: `bench/candidates/opusmt_mt.py`

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
        # Chỉ đổi beam_size — giữ nguyên repetition_penalty và
        # no_repeat_ngram_size cố định, để sweep chỉ thay đổi ĐÚNG 1 biến số.
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

Đổi gì: xoá _DECODE_KWARGS cấp class (hard-code), chuyển thành self._decode_kwargs cấp instance, đọc beam_size từ cfg.get("beam_size", 4) — giữ default 4 để không phá vỡ hành vi hiện tại nếu ai gọi mà không truyền config.

Bước 2 — Thêm --config-override vào bench/run.py

File: `bench/run.py`

Sửa run_manifest:

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
        # Merge override vào config của item TRƯỚC khi build candidate,
        # để beam_size mới có hiệu lực ngay từ lần khởi tạo Translator.
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

Sửa main():

```python
def main() -> None:
    ap = argparse.ArgumentParser(description="Kavi benchmark harness (host-side v0)")
    ap.add_argument("--manifest", help="path to eval_manifest_v1.json")
    ap.add_argument(
        "--smoke", action="store_true", help="generate + run a tiny offline sample"
    )
    ap.add_argument("--out", default="bench-results", help="output directory")
    ap.add_argument("--candidate", help="only run this candidate_id")
    ap.add_argument(
        "--config-override",
        help='JSON dict merged into every item.config, e.g. \'{"beam_size": 4}\'',
    )
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.smoke:
        manifest = build_smoke_manifest(workdir=out_dir / "smoke-inputs")
    elif args.manifest:
        manifest = RunManifest.from_json(args.manifest)
    else:
        ap.error("either --manifest PATH or --smoke required")

    config_override = json.loads(args.config_override) if args.config_override else None
    records = run_manifest(manifest, out_dir, args.candidate, config_override)
    (out_dir / "run_results.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print_table(records)
    print(f"\nWrote {out_dir / 'run_results.json'}")
```

Vì sao merge vào item.config thay vì truyền tham số riêng qua build_candidate: build_candidate() trong registry.py đã có sẵn logic đọc item.config — không cần sửa registry.py, chỉ cần đảm bảo item.config chứa đúng override trước khi hàm đó chạy.

Bước 3 — Tạo file lọc riêng bộ MT nhỏ để sweep nhanh (bench/filter_manifest.py)

```python
"""Filter eval_manifest_v1.json down to a stage subset for quick experiments."""

from __future__ import annotations

import argparse

from .schema import RunManifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Filter manifest by stage + limit")
    ap.add_argument("--manifest", default="eval_data/eval_manifest_v1.json")
    ap.add_argument("--stage", required=True, choices=["ASR", "MT", "TTS"])
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    manifest = RunManifest.from_json(args.manifest)
    filtered = [
        it
        for it in manifest.items
        if it.stage == args.stage and (it.reference_text or it.transcript_ref)
    ][: args.limit]
    RunManifest(version=manifest.version, items=filtered).to_json(args.out)
    print(f"Wrote {len(filtered)} {args.stage} items (with reference) to {args.out}")


if __name__ == "__main__":
    main()
```

Chạy:

```bash
uv run python -m bench.filter_manifest \
  --stage MT --limit 30 \
  --out eval_data/mt_subset_beam.json
```

Lọc thêm điều kiện reference_text or transcript_ref để tránh lấy nhầm item thiếu ground-truth, vì thiếu ground-truth thì BLEU sẽ ra None, làm loãng số liệu.

Bước 4 — Smoke test trước với 3 câu, 2 beam width (đừng chạy full ngay)

```bash
uv run python -m bench.filter_manifest --stage MT --limit 3 --out /tmp/mt_smoke.json

for beam in 1 2; do
  uv run python -m bench.run \
    --manifest /tmp/mt_smoke.json \
    --candidate opus-mt-vi-en-ct2-cpu \
    --out /tmp/beam-smoke-$beam \
    --config-override "{\"beam_size\": $beam}"
done
```

Kiểm tra print_table() in ra đúng cột BLEU, không có dòng error — nếu ổn mới chạy full ở Bước 5.

Bước 5 — Chạy sweep thật, mỗi beam width là 1 process riêng biệt

```bash
mkdir -p bench-results
for beam in 1 2 4 5 8; do
  echo "=== beam_size=$beam ==="
  uv run python -m bench.run \
    --manifest eval_data/mt_subset_beam.json \
    --candidate opus-mt-vi-en-ct2-cpu \
    --out bench-results/beam-$beam \
    --config-override "{\"beam_size\": $beam}"
done
```

Vì sao bắt buộc chạy tách process (không viết vòng lặp Python gọi trong cùng 1 chương trình):

Cô lập RAM — peak_ram_mb() là high-water mark của toàn process, không tự reset. Nếu chạy cả 5 beam trong 1 process, số RAM của beam=8 sẽ cộng dồn RAM còn sót từ các lần chạy trước.
Tránh cache candidate cũ — nhìn kỹ run_manifest(): candidates dict cache theo cid ("opus-mt-vi-en-ct2-cpu"), không phân biệt theo config. Nếu gọi run_manifest() 2 lần liên tiếp trong cùng process với 2 config_override khác nhau, lần gọi thứ 2 sẽ tái sử dụng candidate đã build sẵn beam cũ, bỏ qua override mới — im lặng, không báo lỗi. Chạy tách process loại bỏ hoàn toàn rủi ro này vì mỗi process luôn khởi tạo candidate mới từ đầu.
Bước 6 — Viết script tổng hợp kết quả thành đúng bảng của issue #88 (bench/aggregate_beam_sweep.py)

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
        "peak_ram_mb": max(ram_vals) if ram_vals else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-root", default="bench-results")
    ap.add_argument("--beams", type=int, nargs="+", default=[1, 2, 4, 5, 8])
    args = ap.parse_args()

    root = Path(args.results_root)
    rows: dict[int, dict] = {}
    for beam in args.beams:
        p = root / f"beam-{beam}" / "run_results.json"
        if not p.exists():
            print(f"  MISSING: {p} — chạy sweep cho beam={beam} trước")
            continue
        rows[beam] = summarize(load_records(p))

    if 1 not in rows or rows[1]["latency_s"] is None:
        print("ERROR: thiếu baseline beam=1 (hoặc toàn lỗi) — không tính được relative latency")
        return

    baseline_latency = rows[1]["latency_s"]
    baseline_ram = rows[1]["peak_ram_mb"]

    print(f"{'Beam':<8} {'BLEU':>7} {'Rel.latency':>12} {'ΔRAM(MB)':>10} {'Errors':>7}")
    print("-" * 50)
    for beam in args.beams:
        if beam not in rows:
            continue
        r = rows[beam]
        rel_lat = f"{r['latency_s'] / baseline_latency:.2f}x" if r["latency_s"] else "-"
        delta_ram = (
            f"{r['peak_ram_mb'] - baseline_ram:+.0f}"
            if r["peak_ram_mb"] is not None and baseline_ram is not None
            else "-"
        )
        bleu_str = f"{r['bleu']:.1f}" if r["bleu"] is not None else "-"
        print(f"{beam:<8} {bleu_str:>7} {rel_lat:>12} {delta_ram:>10} {r['n_err']:>7}")


if __name__ == "__main__":
    main()
```

Chạy:

```bash
uv run python -m bench.aggregate_beam_sweep
```

Vì sao báo Δ RAM (chênh lệch so với beam=1) thay vì số RAM tuyệt đối: peak_ram_mb() đo cả process, bao gồm cả phần RAM cố định để load trọng số model CTranslate2 (không đổi theo beam) — số tuyệt đối sẽ làm loãng phần thực sự do KV-cache lớn hơn gây ra. Lấy Δ so với baseline mới phản ánh đúng "chi phí tăng thêm do tăng beam".

Bước 7 — Điền vào bảng issue #88 và viết Verdict

Copy output của Bước 6 vào bảng markdown trong issue, ví dụ:

Beam width	Quality metric (BLEU)	Relative decode latency	Peak KV-cache memory (Δ)	Verdict
1 (greedy)	(điền)	1.0× (baseline)	—	
2	(điền)	(điền)	(điền)	
4	(điền)	(điền)	(điền)	
5	(điền)	(điền)	(điền)	
8	(điền)	(điền)	(điền)	

Gợi ý viết Verdict cho từng dòng (dựa theo số thật sẽ ra, nguyên tắc chung):

Beam nào tăng BLEU rõ rệt (>1 điểm) mà relative latency vẫn <1.5× → "chấp nhận được, đổi ít tốc độ lấy nhiều chất lượng".
Beam nào BLEU gần như không đổi so với beam nhỏ hơn liền trước → "không đáng, lợi ích cận biên gần 0".
Beam nào relative latency vượt hẳn ngưỡng chấp nhận được cho ngân sách turnaround <2.0s (MT chỉ là 1 phần trong 3 stage) → "loại, vượt ngân sách".
Bước 8 — Ghi chú caveat vào issue #88 trước khi đóng Giai đoạn 1

Thêm 1 dòng comment vào issue, đúng như đã thống nhất ở lượt trước:

Số liệu trên đo trên host (laptop), chưa phải điện thoại thật. Cần re-verify sau khi ADR-006 Android runner build xong, vì theo ADR-005 Decision 2, decoder (bao gồm beam search) luôn chạy CPU on-device — beam width tối ưu trên laptop có thể không còn tối ưu khi đổi sang CPU chậm hơn của điện thoại.
