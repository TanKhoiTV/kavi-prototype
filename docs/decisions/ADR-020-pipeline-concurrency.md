# ADR-020: Pipeline concurrency and per-encoder CPU fallback

## Status

Accepted

## Date

2026-07-26

## Deciders

Kavi team

## Context

The pipeline chains five stages across two compute units (NPU encoders, CPU
decoders — [ADR-015](ADR-015-npu-cpu-zero-copy-ion.md),
[ADR-023](ADR-023-decoder-on-cpu.md)). Three things must be true for this to hold
up under live conversation:

1. **Cancellation must propagate** — when the user stops speaking or switches modes
   mid-utterance, no stage may keep running.
2. **A single NPU failure must not kill the pipeline** — an unavailable HTP, an
   unloaded model, or an unsupported op should degrade, not crash.
3. **The decode strategy must fit the latency budget** — the 2.0 s turnaround gate
   constrains how much decoder compute can be spent per utterance.

> **Split note:** extracted from the former `ADR-007 Decision 9`.

## Decision

Run the per-utterance pipeline on `Dispatchers.Default` within a
lifecycle-scoped coroutine scope, with **per-encoder** CPU fallback and **greedy
(beam=1) MT decoding** for v1.

### Pipeline invocation

```kotlin
scope.launch(Dispatchers.Default) {
    val cleaned = denoiser.apply(audio)             // 16 kHz PCM float
    val encoded = asrEncoder.run(cleaned)            // NPU
    val text = asrDecoder.decode(encoded)            // CPU, batch=2
    val mtEncoded = mtEncoder.run(text)              // NPU
    val translated = mtDecoder.decode(mtEncoded)     // CPU
    val audio = ttsModel.synthesize(translated)      // CPU
    withContext(Dispatchers.Main) {
        audioTrack.write(audio)
        updateUI()
    }
}
```

### CPU fallback pattern

If QNN inference fails (model not loaded, HTP unavailable, unsupported op):

```kotlin
try {
    val encoded = qnnLoader.runInference(input)
} catch (e: QnnException) {
    logger.warn("QNN failed (${e.code}), falling back to CPU")
    val encoded = cpuEncoder.run(input)  // ONNX Runtime on CPU
}
```

### Rationale

- Structured concurrency ensures cancellation propagates correctly when the user
  stops speaking or switches modes.
- CPU fallback is **per-encoder, not global** — one encoder may use the NPU while
  another falls back to CPU.
- The fallback is a **degradation, not a crash** — the conversation continues with
  higher latency.
- **MT decoding strategy is greedy (beam=1) for v1.** This is a latency-budget
  decision, not an implementation-friction one: ONNX Runtime handles beam reorder
  natively, but 4× decoder compute with no NPU offload would risk the 2.0 s
  turnaround gate at beam=4. Greedy keeps the CPU decoder fast enough to meet the
  budget. A beam=4 upgrade path exists — it requires widening the decoder's KV
  cache across beam candidates but does not affect the encoder, the ION handoff, or
  any other pipeline stage. **Deferred to Phase-5** for latency-vs-BLEU
  measurement.

### Revision — 2026-07-27 ([ADR-008](ADR-008-dual-zipformer-asr.md))

The `asrDecoder.decode(encoded) // CPU, batch=2` step above is superseded: dual
Zipformer runs **two concurrent CPU recognizers compared by confidence**
([ADR-008](ADR-008-dual-zipformer-asr.md)), not one batch=2 Whisper decoder. The
concurrency model and the per-encoder fallback rule are unchanged.

## Consequences

### Positive

- **Per-encoder fallback** prevents a single NPU failure from taking down the full
  pipeline — the ASR encoder may use the NPU while the MT encoder falls back to
  CPU, or vice versa.
- Cancellation is structured, so no stage outlives the utterance that started it.

### Negative / risk

- Two compute paths per encoder means two code paths to test, and the fallback
  widens latency variance between NPU and CPU operation.
- Greedy decoding trades translation quality (BLEU) for latency until the Phase-5
  beam measurement justifies otherwise.

## References

- [ADR-007](ADR-007-translation-service.md) — TranslationService (parent record)
- [ADR-015](ADR-015-npu-cpu-zero-copy-ion.md) — NPU→CPU zero-copy via ION
- [ADR-023](ADR-023-decoder-on-cpu.md) — Decoder on CPU
- [ADR-008](ADR-008-dual-zipformer-asr.md) — Dual Zipformer ASR (revised the ASR step)
- [ADR-010](ADR-010-all-opt-decoder-optimisation.md) — ORT optimisation level for these CPU sessions
