# ADR-013: Persistent model residency — load everything at startup

## Status

Accepted

## Date

2026-07-26

## Deciders

Kavi team

## Context

The [`TranslationService`](ADR-007-translation-service.md) hosts the whole
pipeline in one process, in two modes that must not swap model sets. Two
questions follow: *when* do models load, and *how long* do they stay resident?

The competing risks are a long cold start (loading at launch) versus per-utterance
loading overhead in the middle of a live conversation, where the 2.0 s turnaround
budget leaves no room for I/O or initialisation spikes.

> **Split note:** extracted from the former `ADR-007 Decision 2`. It also now
> owns the residency invariant previously stated in `ADR-007 Decision 1`.

## Decision

All models load in `TranslationService.onCreate()` and remain resident for the
lifetime of the service. **No lazy loading, no on-demand swapping between modes.**

**Key invariant:** one `TranslationService` instance per process, holding all
model state.

### Load sequence (cold start, ~2–3 s)

```
TranslationService.onCreate()
├── Load Whisper tokenizer (byte-level BPE/GPT-2)  → permanent
├── Load Opus-MT tokenizer (SentencePiece)          → permanent
├── Load Whisper encoder QNN context binary          → NPU, permanent
├── Load Whisper decoder ONNX session                → CPU, permanent
├── Load Opus-MT encoder QNN context binary           → NPU, permanent
├── Load Opus-MT decoder ONNX session                 → CPU, permanent
├── Load TTS model ONNX session                       → CPU, permanent (model TBD)
├── Allocate KV caches (max-size)                     → CPU memory, permanent
└── Allocate I/O tensors                              → permanent
```

*(The Whisper ASR entries in this sequence were replaced by dual Zipformer in
[ADR-008](ADR-008-dual-zipformer-asr.md) / [ADR-027](ADR-027-asr-cpu-only.md); the
TTS slot was filled by [ADR-009](ADR-009-supertonic-tts-v1.md). The eager-loading
decision itself is unchanged.)*

### Rationale

- **Zero model-loading overhead per utterance** — after cold start, every
  pipeline invocation skips I/O and initialization.
- **Predictable latency** — no garbage-collection or JIT loading spikes
  mid-conversation.
- **RAM headroom** — the peak budget (see
  [ADR-016](ADR-016-memory-budget.md)) accommodates all models concurrently.
- **Trade-off:** ~2–3 s cold start when the service first launches (or is killed
  and restarted by the OS).

### Open parameter: TTS model

The TTS model slot is reserved but the specific model is not yet selected here;
the selection is recorded in [ADR-009](ADR-009-supertonic-tts-v1.md).

## Consequences

### Positive

- **Predictable per-utterance latency** — persistent residency eliminates I/O and
  initialisation from the critical path, together with the pre-allocated KV
  caches in [ADR-014](ADR-014-max-size-kv-cache-preallocation.md).

### Negative / risk

- **Cold start latency (~2–3 s)** — the first utterance after app launch is
  delayed while all models load. Mitigation: splash screen with progress
  indication; keep the service alive via a foreground notification during active
  use.

## References

- [ADR-007](ADR-007-translation-service.md) — TranslationService two-mode foreground service
- [ADR-014](ADR-014-max-size-kv-cache-preallocation.md) — Max-size KV cache pre-allocation
- [ADR-016](ADR-016-memory-budget.md) — Peak memory budget
- [ADR-008](ADR-008-dual-zipformer-asr.md) — Dual Zipformer ASR (replaced the Whisper load entries)
