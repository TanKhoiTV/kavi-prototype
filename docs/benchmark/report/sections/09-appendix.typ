#pagebreak()

#let d = json("../data.json")

// 09-appendix.typ

// Helper: SNR table (same as in 05-results-asr.typ)
#let blue-header(cells) = table.header(..cells.map(c => table.cell(fill: rgb("#D6E8F7"), c)))

#let snr-table(grid, cands, noise) = table(
  columns: 6,
  align: center,
  blue-header(([Model], [Clean], [15 dB], [10 dB], [5 dB], [0 dB])),
  ..cands.map(((label, key)) => (
    [#label], [#grid.at(key).at("clean")],
    [#grid.at(key).at(noise + "_15")],
    [#grid.at(key).at(noise + "_10")],
    [#grid.at(key).at(noise + "_5")],
    [#grid.at(key).at(noise + "_0")],
  )).flatten(),
)

= Phụ lục

== Reproducibility <sec:appendix-repro>

Lệnh chạy benchmark:

```bash
uv run python -m bench/run.py --manifest eval_data/mt_vi_en_eval_manifest.json --candidate hy-mt1.5-1.8b-hf-cpu --out bench-results/fleurs-mt/gold-set/hy-mt1.5-1.8b-hf-cpu
```

- Manifest:
  - `eval_data/eval_manifest_v1.json` (FLEURS)
  - `eval_data/vivos_vi_eval_manifest.json` (VIVOS)
  - `eval_data/mt_vi_en_eval_manifest.json` (MT).
- Model paths: `models/` (CT2 weights, sherpa-onnx); HF cache (transformers).
- Beam config: xem `bench/registry.py` `REGISTRY` dict.
- Aggregation:
  - `bench/scripts/aggregate_results.py` → `docs/benchmark/benchmark-results-fleurs-vivos.md`
  - `benchmark-results-raw.md` (từ `docs/benchmark/raw-results/*.csv`).

== Limitations <sec:appendix-limits>

- *FLEURS references là informal spoken transcripts* → BLEU penalty cho output fluent/literary (ảnh hưởng HY-MT nhiều hơn m2m/opus).
- *VSS/Zipformer contamination:* Zipformer-vi train trên VSS; VIVOS cùng miền giọng đọc chuẩn → kết quả Zipformer-vi trên VIVOS có thể bị lạc quan. So sánh công bằng nhất nằm ở FLEURS.
- *Single test environment* — CPU-only Core i7-1165G7 (Tiger Lake, 4 cores / 8 threads), không GPU/NPU.
- *Chưa có on-device (QNN/HTP)* numbers — cần Qualcomm HTP hardware.
- *HY-MT chỉ gold-set* — full-pool chưa chạy; latency không comparable với CT2.
- *Text normalization hạn chế* — chỉ lowercase, không strip punctuation/số → WER/CER cao hơn các báo cáo dùng aggressive normalization.
- *RTF không so sánh chéo dataset* — Whisper có fixed overhead bất kể độ dài audio.

#pagebreak()

== Chi tiết SNR grid (FLEURS ASR)

#figure(
  kind: "table",
  supplement: [Bảng],
  snr-table(d.at("fa-grid"), (
    ("Moonshine-en", "moonshine-en"),
    ("Moonshine-vi", "moonshine-vi"),
    ("Whisper-en", "whisper-en"),
    ("Whisper-vi", "whisper-vi"),
    ("Zipformer-en", "zipformer-en"),
    ("Zipformer-vi", "zipformer-vi"),
  ), "steady"),
  caption: [FLEURS — WER theo SNR dưới steady noise.],
)

#figure(
  kind: "table",
  supplement: [Bảng],
  snr-table(d.at("fa-grid"), (
    ("Moonshine-en", "moonshine-en"),
    ("Moonshine-vi", "moonshine-vi"),
    ("Whisper-en", "whisper-en"),
    ("Whisper-vi", "whisper-vi"),
    ("Zipformer-en", "zipformer-en"),
    ("Zipformer-vi", "zipformer-vi"),
  ), "impulsive"),
  caption: [FLEURS — WER theo SNR dưới impulsive noise.],
)

== Chi tiết SNR grid (VIVOS ASR)

#figure(
  kind: "table",
  supplement: [Bảng],
  snr-table(d.at("va-grid"), (
    ("Moonshine-vi", "moonshine-vi"),
    ("Whisper-vi", "whisper-vi"),
    ("Zipformer-vi", "zipformer-vi"),
  ), "steady"),
  caption: [VIVOS — WER theo SNR dưới steady noise.],
)

#figure(
  kind: "table",
  supplement: [Bảng],
  snr-table(d.at("va-grid"), (
    ("Moonshine-vi", "moonshine-vi"),
    ("Whisper-vi", "whisper-vi"),
    ("Zipformer-vi", "zipformer-vi"),
  ), "impulsive"),
  caption: [VIVOS — WER theo SNR dưới impulsive noise.],
)
