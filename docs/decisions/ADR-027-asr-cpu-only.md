# ADR-027: ASR stays CPU-only for v1

## Status

Accepted

## Date

2026-07-27

## Deciders

Kavi team

## Context

[ADR-008](ADR-008-dual-zipformer-asr.md) selected dual Zipformer (RNN-T) transducers
for ASR, replacing Whisper Small — whose prebuilt Qualcomm AI Hub QNN path was one
of the original reasons for the NPU-primary platform choice
([ADR-002](ADR-002-target-platform.md)). That left an open question: should the new
ASR models be compiled for the Hexagon NPU as well?

Investigation of the sherpa-onnx QNN model catalog (Feb 2026) settled it.

> **Split note:** extracted from the former `ADR-008` section *"ADR-007 Decision 5
> (revised): Memory budget"*, where this conclusion was buried alongside the memory
> accounting. It is a distinct, independently-reversible decision about compute
> placement and now lives on its own.

## Decision

**ASR stays CPU-only for v1.** No QNN context binary is built or shipped for the
ASR stage.

The sherpa-onnx QNN catalog has **no prebuilt QNN context binaries for Zipformer
transducer (RNN-T)** — only Zipformer CTC (Chinese), Paraformer, and SenseVoice are
available, all for SM8850 (Snapdragon 8 Elite) and newer chips. Even if DIY QNN
compilation via QAIRT were pursued, three fundamental incompatibilities block it:

1. **Static input shapes** — QNN requires fixed-duration models (5s/10s/30s) with
   silent truncation beyond the limit. This is incompatible with streaming
   transducer processing, where audio arrives in chunks.
2. **RNN-T decoder loop** — the iterative frame-by-frame decoder does not map
   cleanly to the HTP's fixed-graph execution model.
3. **Context binary size bloat** — existing QNN models are 241–351 MB (`model.bin`)
   vs ~10 MB ONNX int8, defeating the memory savings Zipformer exists to provide.

### Why CPU is sufficient

Zipformer RTF **0.011** on desktop (0.041 s elapsed on a 3.74 s clip, 1 thread;
[verified from the sherpa-onnx benchmark](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/zipformer-transducer-models.html))
is fast enough that NPU offload provides **no meaningful benefit** within the 2.0 s
turnaround budget.

## Consequences

### Positive

- ASR avoids the entire QNN/QAIRT toolchain and its version-lock risk
  ([ADR-019](ADR-019-qnn-runtime-bundling.md) no longer needs ASR entries).
- ASR memory drops to ~60 MB on-disk and ~150 MB peak, since no NPU context binaries
  are involved ([ADR-016](ADR-016-memory-budget.md)).
- Removes a whole class of risk: no ASR graph to re-convert on SDK or model change.

### Negative / risk

- The NPU path now exists **solely for the Opus-MT encoder**
  ([ADR-023](ADR-023-decoder-on-cpu.md)) — if MT later moves to CPU, the QNN runtime
  bundling ([ADR-019](ADR-019-qnn-runtime-bundling.md)) and much of the
  platform-specific machinery become dead weight.
- The ION zero-copy handoff ([ADR-015](ADR-015-npu-cpu-zero-copy-ion.md)) now has a
  single consumer (Opus-MT encoder → decoder) instead of two.

## References

- [ADR-008](ADR-008-dual-zipformer-asr.md) — Dual Zipformer ASR (parent decision)
- [ADR-023](ADR-023-decoder-on-cpu.md) — Encoder on NPU, decoder on CPU
- [ADR-019](ADR-019-qnn-runtime-bundling.md) — QNN runtime bundling (ASR entries withdrawn)
- [ADR-016](ADR-016-memory-budget.md) — Peak memory budget
- [ADR-003](ADR-003-hexagon-runtime.md) — Hexagon runtime / compiler strategy
