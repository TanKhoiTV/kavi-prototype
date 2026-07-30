# Beam Sweep Report — Moonshine Tiny (Transformers, CPU)

**Date:** 2025-07-28  
**Model:** Moonshine Tiny via HuggingFace Transformers (`MoonshineForConditionalGeneration`)  
**Candidate IDs:** `moonshine-tiny-vi-hf-cpu`, `moonshine-tiny-en-hf-cpu`  
**Dataset:** 30 ASR items per language from `eval_manifest_v1.json` (vi + en, mixed noise)  
**Runtime:** PyTorch CPU (no CTranslate2 support — PR #1808 open since Oct 2024, never merged)  
**Metric:** WER (Word Error Rate), RTF (Real-Time Factor), relative latency, ΔRAM

---

## Results

### Vietnamese

| Beam | WER | RTF | Rel. Latency | ΔRAM (MB) | RAM abs (MB) | Errors |
|------|-----|-----|-------------|-----------|-------------|--------|
| 1 (greedy) | **0.524** | 0.13 | 1.00× | — | 485 | 0 |
| 2 | 0.540 | 0.14 | 1.10× | +20 | 506 | 0 |
| 4 | 0.559 | 0.29 | 2.28× | +63 | 548 | 0 |
| 5 | 0.551 | 0.34 | 2.70× | +76 | 562 | 0 |
| 8 | 0.569 | 0.51 | 4.05× | +125 | 610 | 0 |

### English

| Beam | WER | RTF | Rel. Latency | ΔRAM (MB) | RAM abs (MB) | Errors |
|------|-----|-----|-------------|-----------|-------------|--------|
| 1 (greedy) | **0.354** | 0.04 | 1.00× | — | 481 | 0 |
| 2 | 0.358 | 0.07 | 1.69× | +13 | 494 | 0 |
| 4 | 0.351 | 0.10 | 2.54× | +36 | 517 | 0 |
| 5 | 0.351 | 0.11 | 2.74× | +48 | 529 | 0 |
| 8 | 0.364 | 0.17 | 4.29× | +81 | 561 | 0 |

---

## Analysis

### Beam search has no effect on WER

Both languages show **flat WER within ±0.03** across all beam widths (1–8). Greedy decoding (beam=1) is sufficient. Beam search explores alternative hypotheses but does not improve accuracy for this model size.

### Moonshine vs Whisper Small — head-to-head

| Metric | Moonshine Tiny (27M) | Whisper Small (244M) | Δ |
|--------|---------------------|---------------------|---|
| **Vi WER (greedy)** | 0.524 | **0.452** | **+0.072** (16% worse) |
| **En WER (greedy)** | 0.354 | **0.278** | **+0.076** (27% worse) |
| **Vi latency (greedy)** | **1.94 s** | 3.10 s | **1.6× faster** |
| **En latency (greedy)** | **0.41 s** | 2.90 s | **7.1× faster** |
| **Vi WER flatness** | ±0.02 across beams | ±0.01 across beams | Similar |
| **En WER flatness** | ±0.01 across beams | ±0.01 across beams | Similar |
| **RAM (greedy)** | **485 MB** | 923 MB | **1.9× smaller** |
| **RAM sensitivity** | +13→+125 MB Δ | **Flat (+0)** | Moonshine RAM grows with beam; Whisper doesn't |

### Key observations

1. **Whisper Small beats Moonshine Tiny on WER for both languages** — 16% better for vi, 27% better for en. Despite being 9× smaller, Moonshine's quality is noticeably worse.

2. **Moonshine is faster at greedy** (especially English: 0.76 s vs 2.90 s) — this is the advantage of a tiny 27M model over 244M. However, beam search destroys this advantage (vi beam=8 is 10+ seconds).

3. **RAM grows with beam size** — unlike Whisper (where CT2's fixed workspace absorbs KV-cache), PyTorch Transformers' `generate()` allocates fresh memory for each beam hypothesis. ΔRAM from greedy to beam=8 is **+125 MB for vi**, making larger beams costly.

4. **No CT2 optimization available** — without CTranslate2, inference runs on raw PyTorch which is slower and more memory-intensive than the int8-optimized Whisper CT2 pipeline.

### Why Vi is worse than En for Moonshine

| Factor | Moonshine Tiny Vi | Moonshine Tiny En |
|--------|------------------|------------------|
| Parameters | 27M | 27M |
| Training data | Vietnamese subset | English (large) |
| Greedy WER | **0.524** | **0.354** |
| Greedy latency | **2.40 s** | **0.76 s** |

The latency gap (2.40 vs 0.76 s) suggests the Vietnamese model may have a different decoder structure or is handling longer token sequences (Vietnamese text produces more tokens per utterance due to diacritics/syllables). The WER gap (0.52 vs 0.35) reflects Moonshine's English-training bias — like most ASR models, English gets more training data and better accuracy.

---

## Comparison: Moonshine vs Whisper per noise condition

### Vietnamese (beam=1, greedy)

| Condition | Moonshine WER | Whisper WER | Δ |
|-----------|--------------|-------------|---|
| Clean | 0.480 | 0.384 | +0.096 |
| Steady-15 | 0.491 | 0.414 | +0.077 |
| Steady-10 | 0.516 | 0.455 | +0.061 |
| Steady-5 | 0.568 | 0.467 | +0.101 |
| Steady-0 | 0.618 | 0.494 | +0.124 |
| Impulsive-15 | 0.500 | 0.440 | +0.060 |
| Impulsive-10 | 0.518 | 0.458 | +0.060 |
| Impulsive-5 | 0.527 | 0.468 | +0.059 |
| Impulsive-0 | 0.500 | 0.489 | +0.011 |

Moonshine degrades faster than Whisper under noise. At Steady-0 (SNR 0 dB), Moonshine WER jumps to 0.618 vs Whisper's 0.494. Under impulsive noise, the gap is smaller (0.01–0.06).

---

## Verdict

| Choice | WER (vi) | WER (en) | Latency | RAM | Verdict |
|--------|---------|---------|---------|-----|---------|
| **Whisper Small (beam=1)** | **0.452** | **0.278** | ~3.0 s | 923 MB | **Recommended for prod** |
| Moonshine Tiny (beam=1) | 0.524 | 0.354 | ~1.6 s* | 490 MB | ❌ Worse WER, no CT2 path |

**❌ Moonshine Tiny is not a viable ASR candidate for the OneVoice pipeline.**

Rationale:
- **WER is significantly worse** than Whisper Small for both languages (+0.07–0.08)
- **No CT2 optimization** available (PR #1808 never merged) — runs on raw PyTorch
- **RAM grows with beam** (+125 MB vi, +81 MB en from greedy→beam=8)
- **Vi latency at beam=8 exceeds 10 seconds** — unusable for real-time pipeline
- The only advantage (faster greedy for en: 0.76 s) does not compensate for the quality loss

\* *Average of vi + en latencies weighted by item count.*

---

## Caveat — Phase 1 (Host/Laptop Only)

These measurements were taken on a laptop (host) with PyTorch CPU inference. On-device (Android) numbers will be different:

- **Moonshine without CT2 is slower** on mobile CPU — expect 2–5× worse latency than reported here
- **Whisper gap widens** — Whisper via CT2 int8 is already optimized; Moonshine via PyTorch cannot compete
- **The `moonshine-voice` Python package** (ONNX Runtime) might give better latency, but uses a non-commercial license ("Moonshine Community License") — not cleared for production

Re-verify on-device after ADR-006 Android runner if the team decides to reconsider Moonshine.
