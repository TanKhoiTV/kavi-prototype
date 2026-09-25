# ADR-021: ONNX Runtime CPU decoder session options

## Status

Accepted

## Date

2026-07-26

## Deciders

Kavi team

## Context

The CPU-side decoder sessions (Opus-MT decoder, TTS, denoiser) sit in the critical
path of the 2.0 s turnaround budget. ORT exposes several session-level options that
trade startup time and baseline RAM for steady-state inference speed. Which of them
Kavi can safely enable depends on whether the graphs contain custom operators —
a question analysed in full in [ADR-010](ADR-010-all-opt-decoder-optimisation.md),
which concluded that no Kavi pipeline stage uses a custom ONNX operator.

> **Split note:** extracted from the former `ADR-007 Decision 10`. The motivation
> for `ALL_OPT` was later expanded into its own record,
> [ADR-010](ADR-010-all-opt-decoder-optimisation.md); the option set below is
> unchanged.

## Decision

CPU-side decoder sessions use these ORT settings:

```kotlin
sessionOptions.setCPUArenaAllocator(true)           // Pool & reuse memory
sessionOptions.setMemoryPatternOptimization(true)   // Pre-compute optimal tensor layout
sessionOptions.setOptimizationLevel(ALL_OPT)        // Graph fusion, constant folding
```

- **CPU arena allocator:** zero allocations during inference (slightly higher
  baseline RSS).
- **Memory pattern optimisation:** more upfront RAM, faster inference.
- **Full ORT optimisation:** ~15–30% faster decoder execution via fused graphs.

The safety argument for `ALL_OPT` — and the boundary conditions under which it
would become unsafe — is recorded in
[ADR-010](ADR-010-all-opt-decoder-optimisation.md).

## Consequences

### Positive

- **~15–30% faster CPU decoder execution**, contributing directly to the 2.0 s
  turnaround budget.
- Zero per-inference allocation, keeping steady-state RAM predictable alongside
  [ADR-016](ADR-016-memory-budget.md).

### Negative / risk

- Each option raises baseline/startup RAM, absorbed into the cold-start window of
  [ADR-013](ADR-013-persistent-model-residency.md).
- `ALL_OPT` must be validated per-session on device — see the per-session
  validation requirement in [ADR-010](ADR-010-all-opt-decoder-optimisation.md).

## References

- [ADR-007](ADR-007-translation-service.md) — TranslationService (parent record)
- [ADR-010](ADR-010-all-opt-decoder-optimisation.md) — `ALL_OPT` safety analysis (expands this decision)
- [ADR-020](ADR-020-pipeline-concurrency.md) — Pipeline concurrency and fallback
- [ADR-013](ADR-013-persistent-model-residency.md) — Persistent model residency (absorbs startup cost)
