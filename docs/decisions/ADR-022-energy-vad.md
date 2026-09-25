# ADR-022: Energy-based VAD with speech timeout

## Status

Accepted — threshold parameters **OPEN** (to be tuned in noise benchmarking)

## Date

2026-07-26

## Deciders

Kavi team

## Context

The pipeline needs utterance boundaries: when to start capturing and when to
declare the end of speech. Options range from an energy threshold on the already
captured PCM buffer (near-zero overhead) to a model-based VAD such as Silero
(~5–10 ms per frame).

The choice interacts with the denoising stage
([ADR-018](ADR-018-denoising-slot.md)): if background noise has as much energy as
speech, a purely amplitude-based detector will fail.

> **Split note:** extracted from the former `ADR-007 Decision 11`.

## Decision

Use an **energy-based VAD built into the `Recorder` class** for v1, with a model
slot reserved for later.

- **Energy-based VAD:** amplitude threshold on the PCM float stream.
- **Speech timeout:** configurable silence period (default ~500 ms) triggers
  utterance-finalisation.
- **Rationale:** the energy-based approach adds ~0 ms overhead (it operates on the
  already-captured buffer). A model-based VAD (e.g. Silero) adds ~5–10 ms per
  frame.
- **Model slot reserved:** if benchmark results show energy-based VAD is inadequate
  for the target noise environments, a lightweight model can be slotted in **without
  changing the pipeline architecture**.
- **Open:** energy threshold parameters and noise robustness are determined in the
  noise-benchmarking phase.

## Consequences

### Positive

- **Energy-based VAD** keeps the capture path simple and zero-overhead for v1; a
  model-based VAD can be slotted in later without pipeline changes.

### Negative / risk

- **Energy VAD may miss speech onsets in high-noise environments** — if contest
  evaluation uses noisy samples near 0 dB SNR, a model-based VAD may be required.
  Mitigation: the VAD model slot is in the pipeline; the energy threshold can be
  tuned or replaced without changing `Recorder`'s interface.

## References

- [ADR-007](ADR-007-translation-service.md) — TranslationService (parent record)
- [ADR-018](ADR-018-denoising-slot.md) — Denoising slot (the next stage)
- [ADR-012](ADR-012-asr-thread-tuning.md) — ASR thread tuning (capture-thread priority interaction)
