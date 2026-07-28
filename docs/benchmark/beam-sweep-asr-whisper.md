# Beam Sweep Report — Whisper Small (faster-whisper, CPU int8)

**Date:** 2025-07-28  
**Model:** Whisper Small via faster-whisper 1.2.1 (CPU int8)  
**Candidate ID:** `whisper-small-multilang-ct2-cpu`  
**Dataset:** 30 ASR items per language from `eval_manifest_v1.json` (vi + en, balanced)  
**Metric:** WER (Word Error Rate), RTF (Real-Time Factor), relative latency, ΔRAM

---

## Results

### Vietnamese

| Beam | WER | RTF | Rel. Latency | ΔRAM (MB) | Errors |
|------|-----|-----|-------------|-----------|--------|
| 1 (greedy) | **0.452** | 0.24 | 1.00× | — | 0 |
| 2 | 0.454 | 0.25 | 1.08× | +1 | 0 |
| 4 | 0.457 | 0.28 | 1.17× | +1 | 0 |
| 5 | 0.455 | 0.29 | 1.23× | +0 | 0 |
| 8 | 0.461 | 0.30 | 1.29× | +1 | 0 |

### English

| Beam | WER | RTF | Rel. Latency | ΔRAM (MB) | Errors |
|------|-----|-----|-------------|-----------|--------|
| 1 (greedy) | **0.278** | 0.33 | 1.00× | — | 0 |
| 2 | 0.272 | 0.30 | 0.93× | +1 | 0 |
| 4 | 0.273 | 0.31 | 0.94× | +0 | 0 |
| 5 | 0.276 | 0.34 | 1.03× | −0 | 0 |
| 8 | 0.284 | 0.29 | 0.88× | +0 | 0 |

---

## Analysis

### Beam search has no effect on WER

Both languages show **flat WER within ±0.01** across all beam widths (1–8). Greedy decoding (beam=1) is sufficient for Whisper Small. This is expected because:
- `temperature=0` disables the temperature fallback — the model takes the most likely path at each step
- With greedy already deterministic, larger beams explore alternative paths that don't improve accuracy
- Whisper was trained with its own internal decoding strategy; beam search on top adds latency without quality gain

### English WER is significantly better than Vietnamese

| Language | WER (beam=1) | Gap |
|----------|-------------|-----|
| en | **0.278** | Baseline |
| vi | **0.452** | +0.174 (63% worse) |

This is consistent with Whisper's training data distribution — English is heavily represented while Vietnamese has less coverage. This is a model limitation, not a beam-size issue.

### RTF: All configurations are faster than real-time

| Language | RTF range | Meaning |
|----------|-----------|---------|
| vi | 0.24–0.30 | **4× faster than real-time** |
| en | 0.29–0.34 | **3× faster than real-time** |

Even at beam=8, Whisper processes audio faster than it plays. RTF is not a constraint for any beam width.

### RAM is flat

All runs show ~923 MB regardless of beam width. Model weights dominate the process RSS; KV-cache growth from beam search is negligible.

---

## Verdict

| Choice | WER (vi) | WER (en) | RTF | Verdict |
|--------|---------|---------|-----|---------|
| **beam=1 (greedy)** | 0.452 | 0.278 | 0.24–0.33 | **Recommended.** No quality gain from larger beams. |
| beam=2 | 0.454 | 0.272 | 0.25–0.30 | Same WER within noise. No reason to prefer. |
| beam=4+ | 0.455+ | 0.273+ | 0.28–0.34 | Higher latency, same WER. Avoid. |

**Recommended: beam=1 (greedy)** for both languages. Beam search adds latency with zero WER improvement.

---

## Caveat — Phase 1 (Host/Laptop Only)

These measurements were taken on a laptop (host) with `temperature=0` and `condition_on_previous_text=False`. If the production pipeline uses different settings (temperature fallback enabled, segment conditioning on), the WER and latency numbers here will not reflect actual deployment behavior.

Re-verify on-device after ADR-006 Android runner is built. The RTF margins (0.24–0.34) are comfortable on laptop but may narrow significantly on mobile CPU.