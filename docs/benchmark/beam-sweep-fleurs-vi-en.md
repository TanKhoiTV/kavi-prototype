# FLEURS Beam Sweep — Whisper vs Moonshine vs Zipformer (vi + en)

**Date:** 2025-07-28 → 2025-07-29  
**Dataset:** FLEURS vi + en test subsets — 30 ASR items per language per model, mixed noise conditions (clean, steady-15/10/5/0, impulsive-15/10/5/0)  
**Manifest:** `eval_manifest_v1.json` (FLEURS items)  
**Candidates:** `whisper-small-multilang-ct2-cpu`, `moonshine-tiny-{vi,en}-hf-cpu`, `zipformer-{vi-30m,en}-sherpa-onnx-cpu`  
**Metric:** WER (case-normalized for Zipformer), RTF, relative latency, ΔRAM  
**Related:** [beam-sweep-vss-vi.md](beam-sweep-vss-vi.md) (VSS conversational benchmark — invalid for Zipformer)

> **Why FLEURS is the authoritative benchmark:** FLEURS is a standardized read-speech test set with **no source overlap with any model's training data**. Unlike VSS (where Zipformer shows 64–65% byte-exact agreement = reference-style bias / training overlap), FLEURS numbers measure honest generalization. **All Zipformer production decisions should cite these numbers, never VSS.**

---

## Summary Table (best beam per model per language)

| Model | Lang | Best beam | WER | Latency (s) | RTF | RAM (MB) |
|-------|------|-----------|-----|-------------|-----|----------|
| **Zipformer 30M** | vi | 1 (greedy) | **0.137** | **0.60** | **0.04** | 522 |
| **Zipformer EN** | en | 1 (greedy) | **0.240** | **0.41** | **0.04** | 538 |
| Whisper Small | vi | 1 (greedy) | 0.452 | 3.10 | 0.24 | 923 |
| Whisper Small | en | 1 (greedy) | 0.278 | 2.90 | 0.33 | 923 |
| Moonshine Tiny | vi | 1 (greedy) | 0.524 | 1.94 | 0.13 | 485 |
| Moonshine Tiny | en | 1 (greedy) | 0.354 | 0.41 | 0.04 | 481 |

---

## Results by Model

### Zipformer 30M / EN (sherpa-onnx, CPU int8)

#### Vietnamese (Zipformer 30M)

| Beam | WER | RTF | Rel. Latency | ΔRAM (MB) | RAM abs (MB) | Errors |
|------|-----|-----|-------------|-----------|-------------|--------|
| 1 (greedy) | **0.146** | 0.04 | 1.00× | — | 522 | 0 |
| 2 | 0.148 | 0.05 | 1.19× | −1 | 521 | 0 |
| 4 | **0.139** | 0.04 | 1.11× | −1 | 521 | 0 |
| 5 | **0.137** | 0.04 | 1.13× | −2 | 520 | 0 |
| 8 | 0.139 | 0.06 | 1.52× | −1 | 521 | 0 |

#### English (Zipformer EN, 2023 checkpoint)

| Beam | WER | RTF | Rel. Latency | ΔRAM (MB) | RAM abs (MB) | Errors |
|------|-----|-----|-------------|-----------|-------------|--------|
| 1 (greedy) | 0.263 | 0.04 | 1.00× | — | 538 | 0 |
| 2 | 0.259 | 0.06 | 1.56× | +0 | 538 | 0 |
| 4 | **0.240** | 0.05 | 1.21× | +0 | 538 | 0 |
| 5 | **0.240** | 0.05 | 1.28× | +1 | 539 | 0 |
| 8 | **0.240** | 0.06 | 1.44× | +0 | 538 | 0 |

**Beam search provides marginal improvement:** vi −0.009 (−6%), en −0.023 (−9%), plateauing at beam=4–5. **Greedy (beam=1) is sufficient for production.**

**RAM is completely flat** (±2 MB) — sherpa-onnx manages its own workspace like CT2. **Latency is extremely fast** — all RTF < 0.1 (10–25× real-time), 5–7× faster than Whisper.

**Caveats:** EN checkpoint is 2023 vintage and shows higher WER than vi (0.24 vs 0.14) possibly due to training data mismatch. ADR-008 references a different EN model (`zipformer-small-en-2023-06-26`) which was NOT the one benchmarked here (`zipformer-en-2023-03-30`) — see [ADR-008 review](#).

### Whisper Small (faster-whisper, CT2 CPU int8)

#### Vietnamese

| Beam | WER | RTF | Rel. Latency | ΔRAM (MB) | Errors |
|------|-----|-----|-------------|-----------|--------|
| 1 (greedy) | **0.452** | 0.24 | 1.00× | — | 0 |
| 2 | 0.454 | 0.25 | 1.08× | +1 | 0 |
| 4 | 0.457 | 0.28 | 1.17× | +1 | 0 |
| 5 | 0.455 | 0.29 | 1.23× | +0 | 0 |
| 8 | 0.461 | 0.30 | 1.29× | +1 | 0 |

#### English

| Beam | WER | RTF | Rel. Latency | ΔRAM (MB) | Errors |
|------|-----|-----|-------------|-----------|--------|
| 1 (greedy) | **0.278** | 0.33 | 1.00× | — | 0 |
| 2 | 0.272 | 0.30 | 0.93× | +1 | 0 |
| 4 | 0.273 | 0.31 | 0.94× | +0 | 0 |
| 5 | 0.276 | 0.34 | 1.03× | −0 | 0 |
| 8 | 0.284 | 0.29 | 0.88× | +0 | 0 |

**Beam search has NO effect on WER** (flat within ±0.01). Greedy is sufficient. With `temperature=0` and `condition_on_previous_text=False`, greedy is deterministic and beams add latency without quality gain.

**English WER is 63% better than Vietnamese** (0.278 vs 0.452) — Whisper's training data favors English. **All RTF values are faster than real-time** (0.24–0.34). **RAM is flat at ~923 MB** regardless of beam.

### Moonshine Tiny (Transformers HF, PyTorch CPU)

#### Vietnamese

| Beam | WER | RTF | Rel. Latency | ΔRAM (MB) | RAM abs (MB) | Errors |
|------|-----|-----|-------------|-----------|-------------|--------|
| 1 (greedy) | **0.524** | 0.13 | 1.00× | — | 485 | 0 |
| 2 | 0.540 | 0.14 | 1.10× | +20 | 506 | 0 |
| 4 | 0.559 | 0.29 | 2.28× | +63 | 548 | 0 |
| 5 | 0.551 | 0.34 | 2.70× | +76 | 562 | 0 |
| 8 | 0.569 | 0.51 | 4.05× | +125 | 610 | 0 |

#### English

| Beam | WER | RTF | Rel. Latency | ΔRAM (MB) | RAM abs (MB) | Errors |
|------|-----|-----|-------------|-----------|-------------|--------|
| 1 (greedy) | **0.354** | 0.04 | 1.00× | — | 481 | 0 |
| 2 | 0.358 | 0.07 | 1.69× | +13 | 494 | 0 |
| 4 | 0.351 | 0.10 | 2.54× | +36 | 517 | 0 |
| 5 | 0.351 | 0.11 | 2.74× | +48 | 529 | 0 |
| 8 | 0.364 | 0.17 | 4.29× | +81 | 561 | 0 |

**Beam search has no effect on WER** (flat within ±0.03). Greedy is sufficient.

**RAM grows with beam size** (+125 MB vi, +81 MB en from greedy→beam=8) — unlike CT2/sherpa-onnx models, PyTorch `generate()` allocates fresh memory per beam hypothesis. **No CT2 path** (PR #1808 open since Oct 2024, never merged).

---

## Head-to-head Comparison

### Vietnamese

| Metric | Zipformer 30M | Whisper Small | Moonshine Tiny |
|--------|--------------|---------------|----------------|
| **WER (greedy)** | **0.146** | 0.452 | 0.524 |
| **WER (best beam)** | **0.137** | 0.452 | 0.524 |
| **Latency (greedy)** | **0.60 s** | 3.10 s | 1.94 s |
| **RTF (greedy)** | **0.04** | 0.24 | 0.13 |
| **RAM (greedy)** | **522 MB** | 923 MB | 485 MB |
| **RAM sensitivity** | Flat (±2 MB) | Flat (+1 MB) | Grows (+125 MB) |
| **Runtime** | sherpa-onnx | CTranslate2 | PyTorch HF |

**Zipformer is 3.3× better than Whisper on vi WER** (0.137 vs 0.452) — the biggest gap across all models.

### English

| Metric | Zipformer EN | Whisper Small | Moonshine Tiny |
|--------|-------------|---------------|----------------|
| **WER (greedy)** | **0.263** | 0.278 | 0.354 |
| **WER (best beam)** | **0.240** | 0.278 | 0.354 |
| **Latency (greedy)** | **0.41 s** | 2.90 s | 0.41 s |
| **RTF (greedy)** | **0.04** | 0.33 | 0.04 |
| **RAM (greedy)** | **538 MB** | 923 MB | 481 MB |
| **RAM sensitivity** | Flat (+1 MB) | Flat (+0 MB) | Grows (+81 MB) |

Zipformer EN wins on quality (−16% WER) and latency; Moonshine matches Zipformer's latency (0.41 s) but with worse WER.

---

## Noise-condition Comparison (beam=1, greedy)

### Vietnamese

| Condition | Zipformer WER | Whisper WER | Moonshine WER |
|-----------|--------------|-------------|--------------|
| Clean | **0.082** | 0.384 | 0.480 |
| Steady-15 | **0.104** | 0.414 | 0.491 |
| Steady-10 | **0.130** | 0.455 | 0.516 |
| Steady-5 | **0.167** | 0.467 | 0.568 |
| Steady-0 | **0.286** | 0.494 | 0.618 |
| Impulsive-15 | **0.105** | 0.440 | 0.500 |
| Impulsive-10 | **0.117** | 0.458 | 0.518 |
| Impulsive-5 | **0.130** | 0.468 | 0.527 |
| Impulsive-0 | **0.193** | 0.489 | 0.500 |

Zipformer dominates all conditions. Gap widest on clean (0.082 vs 0.384), narrows on severe noise (0.286 vs 0.494 at Steady-0) but remains the clear winner.

### English

| Condition | Zipformer WER | Whisper WER | Moonshine WER |
|-----------|--------------|-------------|--------------|
| Clean | **0.193** | 0.222 | 0.342 |
| Steady-15 | **0.216** | 0.228 | 0.375 |
| Steady-10 | **0.239** | 0.244 | 0.347 |
| Steady-5 | **0.282** | 0.271 | 0.387 |
| Steady-0 | 0.360 | **0.322** | 0.427 |
| Impulsive-15 | **0.222** | 0.262 | 0.333 |
| Impulsive-10 | **0.242** | 0.278 | 0.310 |
| Impulsive-5 | **0.240** | 0.288 | 0.300 |
| Impulsive-0 | **0.275** | 0.313 | 0.321 |

Zipformer wins on cleaner conditions; Whisper slightly better at Steady-0 (0.360 vs 0.322). Operating range (SNR ≥ 5 dB) all favor Zipformer.

---

## Conclusions

### Beam decisions per model

| Model | Beam decision | Rationale |
|-------|--------------|-----------|
| **Zipformer (vi + en)** | **beam=1 (greedy)** | Marginal gain from beams (−6% vi, −9% en); greedy sufficient; RAM flat |
| **Whisper Small (vi + en)** | **beam=1 (greedy)** | Completely flat WER (±0.01); beams add latency, zero quality gain |
| **Moonshine Tiny (vi + en)** | **beam=1 (greedy)** | Flat WER (±0.03); beams add RAM (+125 MB) and latency (vi beam=8 > 10 s) |

### Model ranking (FLEURS, honest generalization)

| Rank | Model | Vi WER | En WER | Verdict |
|------|-------|--------|--------|---------|
| 🥇 | **Zipformer 30M** | **0.137** | **0.240** | **Recommended** — best quality, speed, RAM |
| 🥈 | Whisper Small | 0.452 | 0.278 | Fallback if multilingual single-model needed |
| 🥉 | Moonshine Tiny | 0.524 | 0.354 | ❌ Not viable — no CT2, RAM grows, restrictive license |

### Key takeaways

1. **Zipformer is the clear ASR winner** — 3.3× better vi WER than Whisper, 5–7× faster, half the RAM, flat memory.
2. **All three models converge on beam=1 (greedy)** on FLEURS — beam search never improves WER meaningfully on read speech.
3. **Runtime family determines RAM sensitivity** — CT2/sherpa-onnx models are flat; PyTorch Transformers grows with beam.
4. **VSS vs FLEURS difference:** on VSS conversational/code-switched speech, Whisper's beam search DOES help (1.13 → 0.75) — see [beam-sweep-vss-vi.md](beam-sweep-vss-vi.md). Beam decisions should consider the expected production input type.

---

## Caveats — Phase 1 (Host/Laptop Only)

- All measurements on a laptop (host), CPU inference, int8 where applicable.
- **Whisper:** `temperature=0`, `condition_on_previous_text=False`. Different production settings → different numbers.
- **Moonshine:** raw PyTorch (no CT2). On mobile expect 2–5× worse latency; the ONNX `moonshine-voice` package is faster but licensed non-commercial.
- **Zipformer:** EN checkpoint is 2023 vintage; ADR-008's chosen EN model (`small-en-2023-06-26`) was not the one benchmarked here. NPU not tested (CPU-only).
- Re-verify on-device after ADR-006 Android runner is built.
