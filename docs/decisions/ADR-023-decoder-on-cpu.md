# ADR-023: Encoder on NPU, decoder on CPU

## Status

Accepted

## Date

2026-07-22

## Deciders

Kavi team

## Context

QNN conversion of the full encoder+decoder graphs failed: the Whisper decoder uses
an unsupported op (see [ADR-005](ADR-005-qnn-isnan-workaround.md)), and
autoregressive decoder loops map poorly onto the HTP's fixed-graph execution model.
A choice was needed between forcing the whole graph through the NPU and splitting
the model across compute units.

> **Split note:** extracted from the former `ADR-005 Decision 2`.

## Decision

Run **encoders on the NPU and decoders on the CPU**.

- **Architecture:** encoder on NPU, decoder on CPU.

### Rationale

- Encoder is **compute-bound** (matrix multiplications) → benefits from NPU.
- Decoder is **memory-bound** (embedding lookups, small matmuls) → less NPU
  benefit.
- The decoder contains unsupported ops (`IsNaN`, potentially others).
- Autoregressive loops are hard to optimise on fixed-function hardware.
- This is a common pattern in hybrid NPU deployments (e.g. Qualcomm AI Hub models).

**Action taken:** QNN adapter stubs updated for encoder-only architecture; Opus-MT
encoder exported and converted to QNN (71 MB `.bin`); see PR #75.

### Revised architecture

```text
┌─────────────────────────────────────────────────────┐
│ Android Device (Snapdragon 8 Gen 2)                 │
│                                                     │
│  ┌─────────────┐     ┌──────────────────────────┐  │
│  │ ASR          │     │ Opus-MT                  │  │
│  │ Encoder      │     │ Encoder (QNN/NPU)        │  │
│  │ (QNN/NPU)   │     │ Decoder (CPU/CT2)        │  │
│  └─────────────┘     └──────────────────────────┘  │
│                                                     │
│  ┌─────────────┐                                    │
│  │ TTS         │                                    │
│  │ (CPU only)  │                                    │
│  └─────────────┘                                    │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ Instrumented Test Runner (Kotlin)            │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

*(The ASR encoder box is now CPU-only — see the 2026-07-27 revision.)*

### Revision — 2026-07-27 ([ADR-027](ADR-027-asr-cpu-only.md))

The ASR half of this split no longer applies: Zipformer transducer (RNN-T) has no
QNN path, so **ASR runs CPU-only for v1**. The encoder-on-NPU/decoder-on-CPU
pattern survives **only for Opus-MT**, which is now the sole reason the NPU path
exists.

## Alternatives considered

- **QNN-only (whole graph on NPU)** — blocked by unsupported ops and by the
  autoregressive decoder loop; see [ADR-005](ADR-005-qnn-isnan-workaround.md).
- **CPU-only everywhere** — simpler, but gives up the NPU acceleration the platform
  target was chosen for ([ADR-002](ADR-002-target-platform.md)).

## Consequences

### Positive

- Simpler conversion pipeline: only encoders need QNN.
- Clear separation of concerns between compute units, with a defined handoff
  ([ADR-015](ADR-015-npu-cpu-zero-copy-ion.md)).

### Negative / risk

- **Decoder won't benefit from NPU acceleration.**
- Need to implement a CPU decoder in the Android app.
- **Two inference backends to manage** (QNN/NPU and ORT/CPU).
- **Risks:** encoder-only NPU may not meet the RTF < 1.0 gate, and the CPU decoder
  adds latency to turnaround — both to be measured.

## References

- [ADR-005](ADR-005-qnn-isnan-workaround.md) — `IsNaN` conversion workaround
- [ADR-015](ADR-015-npu-cpu-zero-copy-ion.md) — NPU→CPU zero-copy handoff
- [ADR-003](ADR-003-hexagon-runtime.md) — Hexagon runtime / compiler strategy
- [ADR-027](ADR-027-asr-cpu-only.md) — ASR stays CPU-only (revised the ASR half)
- [ADR-020](ADR-020-pipeline-concurrency.md) — Pipeline concurrency and per-encoder fallback
