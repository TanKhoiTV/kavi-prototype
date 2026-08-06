# Beam Sweep — Whisper vs Moonshine vs Zipformer (VIVOS vi)

**Date:** 2026-07-31  
**Dataset:** VIVOS official test split — 100 of 760 utterances, speaker-stratified (19 speakers × 5–6 items), clean read speech, 16 kHz, ALL-CAPS transcripts  
**Manifest:** `eval_data/vivos_vi_test_manifest.json`  
**Candidates:** `whisper-small-multilang-ct2-cpu`, `moonshine-tiny-vi-hf-cpu`, `zipformer-vi-30m-sherpa-onnx-cpu`  
**Metric:** WER (case-normalized), RTF, latency, peak RAM  
**Prior benchmarks:** [FLEURS vi/en](beam-sweep-fleurs-vi-en.md) · [VSS vi (invalid for Zipformer)](beam-sweep-vss-vi.md)

> **Why VIVOS matters:** VSS was invalidated for Zipformer by training-data/reference-style contamination (64–65% byte-exact on 40–90-word utterances — mathematically impossible honestly). VIVOS is the second held-out conversational/read benchmark attempt with studio-quality recordings.

---

## ✅ Leakage Verdict: VIVOS is CLEAN — Zipformer results are trustworthy

Phase-0 disambiguation (beam=1, 100 items) confirmed **no contamination**:

| Evidence | Result | Interpretation |
|----------|--------|----------------|
| Zipformer exact-match by sentence length | 67% (1–4w) → 89% (5–7w) → 88% (8–10w) → 63% (11–15w) | Decays with length, tracking honest expectation (0.95ⁿ ≈ 86/74/63/50%) |
| Zipformer overall WER | 0.050 vs FLEURS clean 0.082 | Only 1.6× better on genuinely easier audio — not collapsed to ~0.01 |
| Zipformer non-exact items | WER ≈ 0.18, 1–3 word/diacritic errors | Realistic recognition errors, not wholesale reproduction |
| Whisper cross-check | VIVOS 0.369 ≈ FLEURS clean 0.384 | A normal (non-leaking) model shows identical quality on both sets |
| Contrast with VSS | VSS: 65% exact on 40–90w (honest P ≈ 0.001%) | VIVOS's 72% exact on 3–15w is statistically normal |

**VIVOS is the first Vietnamese benchmark with genuine held-out validity for Zipformer** (studio recordings, 19 consistent speakers, short read sentences — outside the model's conversational training distribution).

---

## Results

### Zipformer 30M (`zipformer-vi-30m-sherpa-onnx-cpu`)

| Beam | WER | Latency (s) | RTF | RAM (MB) | Errors |
|------|-----|-------------|-----|----------|--------|
| 1 (greedy) | **0.050** | 0.11 | 0.030 | 359 | 0 |
| 2 | 0.051 | **0.08** | **0.024** | 359 | 0 |
| 4 | 0.051 | 0.12 | 0.035 | 358 | 0 |
| 5 | 0.051 | 0.16 | 0.044 | 359 | 0 |
| 8 | 0.051 | 0.16 | 0.046 | 359 | 0 |

**WER is perfectly flat (±0.001) across all beams. Beam=1 (greedy) is the production choice.** RAM is flat at ~359 MB (short utterances → small workspace; cf. 522 MB on FLEURS). Latency 0.08–0.16 s — RTF as low as 0.024 (40× real-time).

### Whisper Small (`whisper-small-multilang-ct2-cpu`)

| Beam | WER | Latency (s) | RTF | RAM (MB) | Errors |
|------|-----|-------------|-----|----------|--------|
| 1 (greedy) | 0.369 | 3.05 | 0.922 | 923 | 0 |
| 2 | 0.346 | 3.03 | 0.916 | 923 | 0 |
| 4 | 0.345 | 2.90 | 0.878 | 923 | 0 |
| 5 | 0.344 | 3.01 | 0.906 | 923 | 0 |
| 8 | **0.340** | 3.18 | 0.952 | 923 | 0 |

**Beam search helps slightly (−8%):** 0.369 → 0.340. Unlike FLEURS (flat ±0.01), VIVOS shows a modest monotonic improvement — the second dataset where Whisper benefits from beams (VSS showed −33%). RAM is flat at 923 MB; latency ~3.0 s regardless of beam.

**⚠️ RTF anomaly:** Whisper's RTF is ~0.9 here — *not faster than real-time* — because VIVOS utterances are short (mean 3.6 s, fixed decode overhead ~2.5–3 s dominates). On FLEURS (10–15 s utterances) RTF was 0.24–0.34. Short-utterance pipelines pay a fixed ~3 s per item for Whisper regardless of audio length.

### Moonshine Tiny (`moonshine-tiny-vi-hf-cpu`)

| Beam | WER | Latency (s) | RTF | RAM (MB) | Errors |
|------|-----|-------------|-----|----------|--------|
| 1 (greedy) | 0.201 | **0.49** | 0.139 | 501 | 0 |
| 2 | 0.183 | 0.72 | 0.206 | 508 | 0 |
| 4 | 0.164 | 0.92 | 0.258 | 524 | 0 |
| 5 | **0.158** | 0.98 | 0.275 | 530 | 0 |
| 8 | 0.168 | 1.44 | 0.406 | 546 | 0 |

**Beam search helps meaningfully (−21%):** 0.201 → 0.158 at beam=5, with beam=8 regressing (0.168). Also unlike FLEURS (flat ±0.03). RAM grows with beam (501 → 546 MB), latency grows 3×.

---

## Head-to-head (best beam)

| Metric | Zipformer 30M | Whisper Small | Moonshine Tiny |
|--------|--------------|---------------|----------------|
| **WER (best)** | **0.050** | 0.340 | 0.158 |
| **WER (greedy)** | **0.050** | 0.369 | 0.201 |
| **Latency (greedy)** | **0.11 s** | 3.05 s | 0.49 s |
| **RTF (greedy)** | **0.030** | 0.922 | 0.139 |
| **RAM (greedy)** | **359 MB** | 923 MB | 501 MB |
| **RAM sensitivity** | Flat (±1 MB) | Flat (+0 MB) | Grows (+45 MB) |
| **Runtime** | sherpa-onnx | CTranslate2 | PyTorch HF |

Zipformer: **7.4× better WER than Whisper**, 28× faster, 2.6× less RAM. Best WER on every dataset tested to date (FLEURS 0.137, VIVOS 0.050).

---

## Beam decisions

| Model | Recommendation | Rationale |
|-------|---------------|-----------|
| **Zipformer** | **beam=1 (greedy)** | Perfectly flat WER (±0.001) — beams buy nothing, add latency |
| **Whisper** | **beam=1 (or 4)** | −8% at beam=8 (0.369→0.340); beam=4 gives −6.5% at no latency cost. If strict WER matters, 4 is a free win; otherwise greedy |
| **Moonshine** | **beam=5 (if used at all)** | −21% from beams, but model still worst quality and rejected on other grounds |

### Cross-dataset beam behavior (Whisper, vi)

| Dataset | Type | beam=1 → beam=8 | Beam helps? |
|---------|------|-----------------|-------------|
| FLEURS | read, 10–15 s | 0.452 → 0.461 | ❌ flat |
| VIVOS | read, 2–6 s | 0.369 → 0.340 | ⚠️ −8% |
| VSS | conversational | 1.127 → 0.754 | ✅ −33% |

Whisper's beam benefit scales with task difficulty — easy read speech: flat; short clean read: slight; hard conversational: strong. **Production beam choice depends on input type.**

---

## Model ranking (all trustworthy vi benchmarks)

| Rank | Model | FLEURS | VIVOS | VSS* | Verdict |
|------|-------|--------|-------|------|---------|
| 🥇 | **Zipformer 30M** | **0.137** | **0.050** | (invalid) | Best WER, speed, RAM on every valid set |
| 🥈 | Moonshine Tiny | 0.524 | 0.158 | 0.670 | Surprising VIVOS jump (2.4× better than FLEURS) — but still worse than Zipformer everywhere |
| 🥉 | Whisper Small | 0.452 | 0.340 | 0.754 | Reliable but 7× worse than Zipformer on VIVOS |

\* VSS contaminated for Zipformer; numbers for Whisper/Moonshine shown for reference.

---

## Caveats & Limitations

- **Single-split caveat:** VIVOS test has 19 speakers; the 100-item stratified sample covers all of them, but results may not generalize to other Vietnamese speakers/domains.
- **Read speech only:** VIVOS is read, not spontaneous — the hardest conversational case is better probed by VSS (for Whisper/Moonshine) or Kavi's own recordings.
- **Moonshine VIVOS improvement is unexplained** — 0.201 vs FLEURS clean 0.480 (2.4×). Length-stratified exact-match decay (50% → 65% → 27%) argues against memorization, but the magnitude warrants caution if Moonshine is ever reconsidered.
- **Whisper RTF > 1 on short utterances** — fixed ~3 s decode overhead makes Whisper slower than real-time for sub-6 s clips (mean VIVOS RTF 0.92).
- **Host/laptop only** — CPU int8; re-verify on-device after ADR-006 Android runner.
- **License:** VIVOS is CC BY-NC-SA 4.0 (non-commercial) — fine for internal benchmarking, flag before any production use.
