# ADR-015: NPU→CPU zero-copy handoff via ION shared memory

## Status

Accepted

## Date

2026-07-26

## Deciders

Kavi team

## Context

The pipeline splits work between the NPU (encoders, via QNN context binaries —
see [ADR-003](ADR-003-hexagon-runtime.md)) and the CPU (decoders — see
[ADR-023](ADR-023-decoder-on-cpu.md)). Every encoder→decoder handoff is therefore
a cross-compute-unit transfer of `encoder_hidden_states`, and every such transfer
lands directly inside the 2.0 s turnaround budget.

On Snapdragon 8 Gen 2 the Hexagon NPU (HTP v73) and the CPU share DDR memory.

> **Split note:** extracted from the former `ADR-007 Decision 4`.

## Decision

Hand encoder outputs from the NPU to the CPU **without copying**, by having the
NPU write `encoder_hidden_states` into an **ION buffer** that the CPU then reads
through a pointer, synchronised by a cache-coherency barrier only (~1–3 ms for
~5 MB on Snapdragon).

### Pipeline handoff

```
NPU (QNN context binary)            CPU (ONNX Runtime)
┌──────────────────────┐           ┌──────────────────────┐
│ Whisper encoder      │   ION     │ Whisper decoder       │
│ → encoder_output     │ ────────→ │ (reads ION buffer     │
│   in ION buffer      │  barrier  │  via pointer, no copy)│
├──────────────────────┤           ├──────────────────────┤
│ Opus-MT encoder      │   ION     │ Opus-MT decoder       │
│ → encoder_output     │ ────────→ │ (same pattern)        │
│   in ION buffer      │  barrier  │                       │
└──────────────────────┘           └──────────────────────┘
```

### Why this matters

- NPU→GPU or CPU→GPU handoffs require explicit DMA copies (slower).
- NPU→CPU zero-copy is unique to the Snapdragon ION architecture.
- Every millisecond saved here goes directly into the 2.0 s turnaround budget.

### Implementation notes

1. QNN context binary output is written into an ION-backed buffer allocated by
   `QnnBackend_create()`.
2. The JNI bridge (`qnn_loader_jni.cpp`) returns a **direct ByteBuffer**
   referencing the ION memory — not a heap copy.
3. ONNX Runtime creates a tensor from the same buffer via
   `OrtValue::CreateTensor()` with the data pointer, no data migration.

## Consequences

### Positive

- **Zero-copy NPU→CPU handoff** saves ~5–10 ms per utterance vs. a heap-copy
  approach, directly contributing to the 2.0 s turnaround budget.

### Negative / risk

- **ION zero-copy is Snapdragon-specific** — the NPU→CPU handoff optimisation
  does not port to other SoCs (MediaTek, Apple). Mitigation: the pipeline works
  correctly with heap copies on non-Qualcomm hardware; zero-copy is a performance
  optimisation, not a correctness requirement.

## References

- [ADR-007](ADR-007-translation-service.md) — TranslationService (parent record)
- [ADR-003](ADR-003-hexagon-runtime.md) — Hexagon runtime / compiler strategy
- [ADR-023](ADR-023-decoder-on-cpu.md) — Decoder on CPU (the other half of the split)
- [ADR-016](ADR-016-memory-budget.md) — Peak memory budget
