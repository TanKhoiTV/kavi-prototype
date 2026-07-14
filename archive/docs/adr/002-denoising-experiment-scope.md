# ADR-002: Denoising Experiment Scope and Methodology

**Status:** Accepted  
**Date:** 2026-06-23  
**Author:** Project lead  

---

## Context

The prototype pipeline (ASR→MT→TTS) currently has no noise handling — no VAD or
denoising stage. Contest evaluation data is expected to include noisy or
far-field samples, making this a production requirement.

Cuong (niuqohn2510) ran a WER experiment on PR #1 (`feat/wer-experiment`) using
the full VIVOS Vietnamese test set (760 utterances) at SNR 5 dB with ESC-50
industrial noise. The results were counterintuitive:

| Condition | WER | Delta vs noisy |
|-----------|:---:|:--------------:|
| Clean | 15.53% | — |
| Noisy (SNR 5 dB) | 20.23% | baseline |
| RNNoise (stationary=True) | 33.10% | +12.87 pp |
| DeepFilterNet | 27.05% | +6.82 pp |

Both denoisers *degraded* WER relative to raw noisy audio. Two confounding
factors were identified in the PR #1 review:

1. **RNNoise used `stationary=True`** — incorrect for non-stationary ESC-50
   industrial noise. Filed as Issue #2.
2. **The experiment used Whisper Medium** — not our pipeline's Whisper Small
   int8 on CPU.

An advisor consultation (2026-06-23) further challenged the experimental design:

- The contest specification says "noisy, hands-busy, or low-connectivity
  environments" — no SNR floor or noise type mandated.
- RTranslator (niedev/RTranslator), a working reference implementation, uses
  Whisper Small with zero denoising on real Android phones.
- The contest operating range is approximately SNR 0–10 dB — SNR 5 dB with
  industrial noise is a valid stress test but does not answer the pipeline
  decision.

### DeepFilterNet PyPI bug

DeepFilterNet was dropped from the experiment due to an unresolved PyPI import
bug: `torchaudio.backend.common.AudioMetaData` is not found in torchaudio 2.x.
The fix exists in the DeepFilterNet GitHub main branch but no release has been
shipped with it. Any local workaround would be fragile and would not reflect the
production-ready state of the dependency.

### Advisor analysis and denoiser selection

The advisor evaluated denoising approaches against the ASR-first criterion: ASR
penalizes speech distortion more heavily than residual noise. Key findings:

| Approach | Speech distortion | Residual noise | Control granularity |
|----------|:-:|:-:|:-:|
| RNNoise (spectral subtraction) | High | Low | None |
| DeepFilterNet (deep F0-preserving) | Medium | Medium | None |
| **Wiener filtering** (noisereduce) | **Low** | **Medium** | **`prop_decrease`** |

Wiener filtering via `noisereduce.reduce_noise()` with `method='wiener'` was
selected as the primary candidate because:

- ASR-introduced errors (substitutions from distorted phonemes) dominate WER
  degradation more than residual noise does.
- Wiener's `prop_decrease` parameter (0.0 = no filtering, 1.0 = full filtering)
  gives granular control to find the optimal trade-off.
- RNNoise remains as a secondary candidate for comparison — using
  `stationary=False` (corrected from PR #1).

### RNNoise stationary=True deferred

RNNoise with `stationary=True` requires a stationary noise profile (e.g. AC
hum, fan noise). Our current noise set (ESC-50 industrial mix — engine,
chainsaw, hand_saw, washing_machine) is entirely non-stationary. Deferred until
we source or synthesize a stationary noise sample appropriate for the contest
use case.

---

## Decision

### Scope

1. **Drop DeepFilterNet.** The PyPI bug is unresolved and upstream has not
   shipped a fix. DeepFilterNet is not production-ready in our toolchain.

2. **Narrow to 10 VIVOS utterances** (sampled from the test set, diverse
   speakers) with 4 conditions:
   - Clean (no noise)
   - Raw noisy (ESC-50 industrial mix at SNR 5 dB)
   - RNNoise via `noisereduce.reduce_noise(stationary=False)`
   - Wiener via `noisereduce.reduce_noise(method='wiener', prop_decrease=0.5)`

3. **Single noise type:** ESC-50 industrial mix (engine + chainsaw + hand_saw +
   washing_machine) at SNR 5 dB.

4. **Whisper Small int8 on CPU** — matches the production pipeline ASR model.

### Primary candidate

Wiener filtering with `prop_decrease=0.5` is the primary candidate. If it beats
raw noisy WER, we proceed to tuning `prop_decrease` on a larger sample. If it
does not, we skip denoising entirely and use a VAD-only pipeline (Task P1 from
design.md §7).

### Binary go/no-go gate

| Outcome | Action |
|---------|--------|
| Denoisers beat raw noisy WER | Tune `prop_decrease` on 50–100 files |
| Denoisers do not beat raw noisy WER | Drop denoising; VAD-only pipeline |

---

## Consequences

### Positive

- Simpler experiment: 4 conditions × 10 files × 1 noise type. Fast turnaround.
- No fragile DeepFilterNet workarounds to maintain.
- Wiener filtering exposes a tunable parameter (`prop_decrease`) that RNNoise
  and DeepFilterNet lack — regardless of outcome, we learn the WER sensitivity
  to denoising strength.
- The 10-file subset result can be obtained in a single Colab session or local
  run without GPU.

### Negative

- 10 files may have high variance. If WER spread exceeds 15 pp (some files
  improve while others degrade), we will need 30–50 files before drawing
  conclusions.
- Single noise type and single SNR level limit generalizability. This is
  acceptable for Phase 1 — the gate determines whether Phase 2 (SNR sweep ×
  noise types) is worth running.
- RNNoise `stationary=True` path remains untested. If the contest noise
  environment includes stationary noise (AC, fan), we may need to revisit.

### Risk mitigation

- Results are archived in `experiments/denoising-validation/results/` (JSON +
  CSV) for reproducibility.
- Data archiving via Zenodo (or institutional repository) to be evaluated after
  Phase 1. Not a blocker.
- The binary gate prevents scope creep: no Phase 2 unless denoising shows value
  in Phase 1.

---

## References

- **PR #1:** feat/wer-experiment — Cuong's original 760-utterance DFN run
- **Issue #2:** RNNoise stationary=True bug — must use stationary=False
- **Issue #3:** Phase 1 validation — 10-file VIVOS subset scaffold
- **design.md §7:** VAD as P1 task, current no-noise-handling state
- **RTranslator:** niedev/RTranslator — working Whisper Small implementation
  with zero denoising
