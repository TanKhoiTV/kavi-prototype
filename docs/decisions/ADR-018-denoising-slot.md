# ADR-018: Tiered, toggleable denoising slot in the pipeline

## Status

Accepted — model pick **OPEN** (gated on benchmark results)

## Date

2026-07-26

## Deciders

Kavi team

## Context

The target environments are noisy (factories, construction sites, logistics hubs),
and the energy-based VAD ([ADR-022](ADR-022-energy-vad.md)) is deliberately simple,
so speech-to-noise ratio at the ASR encoder will vary widely. A denoising stage is
therefore required — but *where* it sits, *how* it loads, and *whether* it can be
switched off for latency-vs-quality measurement are pipeline questions that must be
settled before the denoiser model itself is chosen.

> **Split note:** extracted from the former `ADR-007 Decision 7`. A later, separate
> finding — the Phase-6 host-side gate that adopted Wiener — has been moved out to
> `docs/reference/denoising-gate-results.md`; it is a result about a *different*
> (host-side) denoiser choice, not part of this architectural slot.

## Decision

Add a **three-tier denoising stage**, applied in order of availability, with the
model tier toggleable per utterance.

```text
AudioRecord (mic, 16 kHz PCM float)
    ↓
[Tier 1: ADSP AI-ECNS]    — if available on the device's DSP, free hardware-accelerated echo/noise suppression
    ↓
[Tier 2: GTCRN]           — 523 KB ONNX model via sherpa-onnx, our controlled denoiser
    ↓
[Tier 3: ASR]             — denoised audio enters the ASR encoder
```

### Decision

- **GTCRN** is the working default for v1 pending benchmark confirmation
  (permissive license, small footprint).
- **ADSP AI-ECNS** is a free bonus layer on supported devices; if unavailable, skip
  transparently.
- The pipeline must allow **toggling denoising on/off per utterance** for latency
  vs. quality benchmarking.
- The denoising model stays loaded permanently (appended to the persistent
  residency list in [ADR-013](ADR-013-persistent-model-residency.md)), with
  pre-allocated STFT/ISTFT buffers to avoid per-utterance setup overhead.

### What remains open

The final denoising model (GTCRN vs. an alternative, and whether the on-device pick
differs from the host-side benchmarking reference) is gated on benchmark results.
**This record fixes the architectural slot** — where denoising sits, how it loads,
how it toggles — **not the model binary.** Only the model file changes once the
pick is made.

## Consequences

### Positive

- Denoising has a defined home in the pipeline without committing to a model,
  so benchmark comparison can proceed against a fixed interface.
- Per-utterance toggling makes the latency/quality trade-off measurable rather than
  assumed.

### Negative / risk

- **An open parameter remains** — the denoiser model is not yet selected; the
  integration point (ONNX session slot, persistent memory reservation,
  pre-allocated buffers) is fixed, only the binary changes.
- The tiered design assumes ADSP AI-ECNS availability cannot be relied upon; where
  it is absent, all suppression work lands on the software tier.

## References

- [ADR-007](ADR-007-translation-service.md) — TranslationService (parent record)
- [ADR-022](ADR-022-energy-vad.md) — Energy-based VAD (the stage immediately before)
- [ADR-013](ADR-013-persistent-model-residency.md) — Persistent model residency
- `docs/reference/denoising-gate-results.md` — Phase-6 host-side gate result (Wiener adopted as benchmarking reference)
- `docs/android-implementation-plan.md` — Risk R1 (on-device denoiser pick still open)
