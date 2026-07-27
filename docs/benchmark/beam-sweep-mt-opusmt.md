# Beam Sweep Report — Opus-MT vi→en

**Date:** 2025-07-26  
**Model:** Helsinki-NLP Opus-MT vi→en via CTranslate2 int8 (CPU)  
**Candidate ID:** `opus-mt-vi-en-ct2-cpu`  
**Dataset:** 30 MT items from `eval_manifest_v1.json` (with reference text)  
**Metric:** BLEU (SacreBLEU), relative decode latency, peak RAM delta  

---

## Sweep Results

| Beam | BLEU | Rel. Latency | ΔRAM (MB) | Errors |
|------|------|-------------|-----------|--------|
| 1 (greedy) | 6.2 | 1.00× (baseline) | — | 0 |
| 2 | 7.8 | 1.63× | +12 | 0 |
| 4 | 8.8 | 2.50× | +21 | 0 |
| 5 | 9.0 | 3.02× | +28 | 0 |
| 8 | 9.0 | 4.46× | +49 | 0 |

---

## Analysis

### Beam 1 (Greedy) — Baseline
- Lowest BLEU (6.2). Observed repetition cycles on longer Vietnamese inputs despite `repetition_penalty=1.1` and `no_repeat_ngram_size=3`.

### Beam 2 — 👍 Recommended for tight latency budgets
- **BLEU gain:** +1.6 (largest marginal gain in the sweep)
- **Latency cost:** 1.63× baseline
- **RAM cost:** +12 MB
- Substantial quality improvement for modest latency increase. Good fallback if end-to-end budget is tight.

### Beam 4 — 👍 Recommended for maximum quality
- **BLEU gain:** +1.0 over beam 2 (+2.6 vs baseline)
- **Latency cost:** 2.50× baseline
- **RAM cost:** +21 MB
- Clear quality improvement with acceptable latency on laptop. Best overall quality/cost trade-off.

### Beam 5 — ⚠️ Diminishing returns
- **BLEU gain:** +0.2 over beam 4 (negligible)
- **Latency cost:** 3.02× baseline
- **RAM cost:** +28 MB
- Marginal benefit does not justify the latency jump. Not recommended.

### Beam 8 — ❌ Exceeds budget
- **BLEU gain:** +0.0 over beam 5 (none)
- **Latency cost:** 4.46× baseline
- **RAM cost:** +49 MB
- No quality improvement, severe latency and memory penalty. Excluded.

---

## Verdict

**Sweet spot: beam=4** — Best balance of translation quality (BLEU 8.8) vs. compute cost (2.5× latency, +21 MB RAM). All three downstream improvements (no repetition cycles, more coherent named entities, fewer truncation artifacts) are achieved by beam=4.

**Fallback: beam=2** — Acceptable if the end-to-end latency budget (<2.0 s total for ASR→MT→TTS) cannot accommodate 2.5× MT decode cost. Still delivers +1.6 BLEU over greedy.

---

## Caveat — Phase 1 (Host/Laptop Only)

These measurements were taken on a laptop (host) and **do not reflect on-device (Android) performance**. Per ADR-005 Decision 2, the decoder (including beam search) runs on-device CPU. The optimal beam width may shift when running on a slower mobile CPU. Re-verify after ADR-006 Android runner is built.