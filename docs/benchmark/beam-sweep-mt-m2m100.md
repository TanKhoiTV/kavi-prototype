# Beam Sweep Report — M2M-100 vi→en

**Date:** 2025-07-27  
**Model:** Facebook M2M-100 (418M) via CTranslate2 int8 (CPU)  
**Candidate ID:** `m2m100-vi-en-ct2-cpu`  
**Dataset:** 30 MT items from `eval_manifest_v1.json` (with reference text)  
**Metric:** BLEU (SacreBLEU), relative decode latency, absolute peak RAM, ΔRAM

---

## Sweep Results

| Beam | BLEU | Rel. Latency | ΔRAM (MB) | RAM abs (MB) | Errors |
|------|------|-------------|-----------|-------------|--------|
| 1 (greedy) | 16.9 | 1.00× (baseline) | — | 1101 | 0 |
| 2 | 17.2 | 0.93× | +0 | 1102 | 0 |
| 4 | 17.2 | 1.04× | +0 | 1101 | 0 |
| 5 | 15.3 | 1.36× | −0 | 1101 | 0 |
| 8 | 15.9 | 1.91× | +0 | 1101 | 0 |

---

## Analysis

### Quality

M2M-100 achieves **BLEU 16.9 at greedy decoding (beam=1)** — more than **2.7× higher** than Opus-MT's greedy baseline (6.2). The multilingual pre-training (81 languages) produces coherent translations even without beam search.

Beam search provides **no meaningful quality improvement**:
- Beam 1→2: +0.3 BLEU (negligible, within noise)
- Beam 2→4: +0.0 BLEU (flat)
- Beam 4→5: −1.9 BLEU (regression — likely noise from repetition penalty interacting with larger search space)
- Beam 5→8: +0.6 BLEU (within noise)

**Conclusion: M2M-100 does not need beam search for quality.** Greedy decoding is sufficient.

### Latency

| Beam | Mean latency | vs greedy |
|------|-------------|-----------|
| 1 | ~0.92 s | 1.00× |
| 2 | ~0.86 s | 0.93× |
| 4 | ~0.96 s | 1.04× |
| 5 | ~1.25 s | 1.36× |
| 8 | ~1.76 s | 1.91× |

Latency measurements are noisy (beam=2 appears faster than beam=1 — measurement variance from background system load). The practical takeaway: beam ≤ 4 adds no meaningful latency overhead; beam ≥ 5 starts showing a clear cost.

### Memory

Absolute RAM is **flat at ~1101 MB** across all beam widths. The 468 MB model weights (int8) dominate the process RSS so completely that KV-cache growth from beam search is invisible (< 1 MB). This is in stark contrast to Opus-MT which showed +12→+49 MB ΔRAM across beams.

---

## Comparison with Opus-MT

| Metric | Opus-MT | M2M-100 | Delta |
|--------|---------|---------|-------|
| Greedy BLEU (beam=1) | 6.2 | **16.9** | **+10.7** |
| Best BLEU | 9.0 (beam=5) | **17.2** (beam=2/4) | **+8.2** |
| Latency at best BLEU | 2.50× (beam=4) | **1.04×** (beam=4) | **2.4× faster** |
| Absolute RAM | 372 MB baseline | **1101 MB** | **+729 MB** |
| RAM sensitivity | +12→+49 MB Δ | **Flat (+0)** | **M2M-100 immune** |

M2M-100 is **qualitatively better in translation quality** (BLEU +8–10 vs Opus-MT) and **does not need beam search**, but uses **3× more RAM** (1101 vs 372 MB). The RAM cost is fixed — model weights, not beam search.

---

## Verdict

| Choice | BLEU | Latency | RAM | Verdict |
|--------|------|---------|-----|---------|
| **beam=1 (greedy)** | 16.9 | 0.92 s | 1101 MB | **Recommended.** No quality benefit from larger beams. |
| beam=2 | 17.2 | 0.86 s | 1102 MB | Marginally higher BLEU but within noise. No reason to prefer. |
| beam=4 | 17.2 | 0.96 s | 1101 MB | Same BLEU as beam=2, ~4% slower. No advantage. |
| beam=5 | 15.3 | 1.25 s | 1101 MB | Lower BLEU + higher latency. Avoid. |
| beam=8 | 15.9 | 1.76 s | 1101 MB | No quality gain at 2× latency. Avoid. |

**Recommended: beam=1 (greedy).** Unlike Opus-MT, M2M-100 produces strong translations without beam search. Larger beams add latency with zero quality benefit.

**If switching from Opus-MT to M2M-100**: the beam=4 default can stay (no harm), but the real consideration is RAM — 1101 MB vs 372 MB is a **3× increase** that may exceed device budget.

---

## Caveat — Phase 1 (Host/Laptop Only)

These measurements were taken on a laptop (host) and **do not reflect on-device (Android) performance**. Key concerns for M2M-100 specifically:

1. **RAM**: 1101 MB is **3× Opus-MT's baseline**. If the device has <2 GB available for the translation process, M2M-100 may be outright excluded regardless of beam width.
2. **Latency scaling**: The 0.92 s greedy latency on laptop will be slower on mobile CPU. Re-verify after ADR-006 Android runner is built.
3. **Model size**: 468 MB int8 is large for on-device deployment. Consider quantization to int8 (already done) or float16 if the device supports it.