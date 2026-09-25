# ADR-014: Max-size KV cache pre-allocation at startup

## Status

Accepted — modified 2026-07-27 by [ADR-008](ADR-008-dual-zipformer-asr.md)

## Date

2026-07-26

## Deciders

Kavi team

## Context

The autoregressive decoders allocate KV cache tensors token-by-token during
decoding. Left to grow dynamically, that produces per-utterance allocation and
free traffic inside the decode loop — exactly the kind of unpredictable latency
the 2.0 s turnaround budget cannot absorb.

The decoder runs on CPU (see [ADR-023](ADR-023-decoder-on-cpu.md)), so the KV
cache lives in CPU-accessible memory, not NPU VTCM, and can be sized freely
within the RAM budget.

> **Split note:** extracted from the former `ADR-007 Decision 3`.

## Decision

Pre-allocate the **maximum possible** KV cache size at startup and reuse it
across every decode invocation, rather than growing it per utterance.

### Constants

| Parameter | Value | Basis |
| --- | --- | --- |
| `MAX_ASR_TOKENS` | 448 | ~15 s of speech × 30 tok/s |
| `MAX_MT_TOKENS` | 256 | Max translation output length |

### Allocation

```
float[] kvCache = new float[MAX_TOKENS × layers × heads × dim];
// Allocated once, zero allocations during decode loop
```

### Effect

- **Zero allocation/free overhead** in the per-token decode loop — the loop
  becomes pure matmul + attention.
- **Predictable peak RAM** — no heap growth as utterance length varies.
- **Waste on short utterances** — a 2-second utterance uses only ~14% of the ASR
  KV cache; the rest is unused but resident.
- **Cache reuse** — after each utterance, the KV cache pointer resets to position
  0; no re-allocation needed.

### Revision — 2026-07-27 ([ADR-008](ADR-008-dual-zipformer-asr.md))

The Zipformer transducer architecture has **no autoregressive KV cache** in the
ASR stage — the decoder is a small RNN-T decoder that processes a frame at a time
without caching past key-value pairs. The **~240 MB ASR KV cache allocation is
eliminated**.

The Opus-MT decoder still uses autoregressive decoding with a KV cache. The
**MT KV cache allocation (~70 MB, max 256 tokens) remains unchanged.**

## Consequences

### Positive

- **Predictable per-utterance latency** — pre-allocated KV caches eliminate
  allocation and JIT overhead from the critical path, together with persistent
  model residency ([ADR-013](ADR-013-persistent-model-residency.md)).

### Negative / risk

- **RAM waste on short utterances** — a 2-second utterance uses ~14% of the
  pre-allocated 448-token ASR KV cache. Mitigation: considered acceptable within
  the peak budget ([ADR-016](ADR-016-memory-budget.md)).
- The ASR-side waste no longer applies as of the 2026-07-27 revision, which
  removed the ASR KV cache entirely.

## References

- [ADR-007](ADR-007-translation-service.md) — TranslationService (parent record)
- [ADR-023](ADR-023-decoder-on-cpu.md) — Decoder on CPU (why the cache is in CPU memory)
- [ADR-016](ADR-016-memory-budget.md) — Peak memory budget it feeds into
- [ADR-008](ADR-008-dual-zipformer-asr.md) — Dual Zipformer ASR (revised this decision)
