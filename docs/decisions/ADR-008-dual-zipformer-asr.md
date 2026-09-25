# ADR-008: v1 Android ASR — dual Zipformer

## Status

Accepted

## Date

2026-07-27

## Deciders

Kavi team

## Supersedes

- [ADR-017](ADR-017-dual-asr-language-detection.md) — dual ASR language detection (Whisper Small batch=2)

## Context

[ADR-007](ADR-007-translation-service.md) proposed **Whisper Small** (244M params)
with dual batch=2 decoding for language-autonomous direction detection. Since then,
research clarified the landscape for lightweight, streaming-capable ASR on the
Snapdragon 8 Gen 2 target. Three findings drove this decision:

1. **Zipformer-30M-RNNT achieves 7.97% WER on Vietnamese** (VLSP2025) —
   dramatically better than Whisper Small's ~20–25% on VIVOS, and better than any
   other license-clean candidate. Trained on 6,000 hours of Vietnamese speech
   including call-centre and conversational data — a strong domain match for
   Kavi's factory/logistics use case.
2. **Zipformer is streaming-native** — transducer architecture processes audio in
   chunks, unlike Whisper/Moonshine which operate on fixed-length windows. This
   fundamentally changes the pipeline design and latency profile.
3. **A dual-instance approach** (one Zipformer per language) achieves
   bidirectional coverage without sacrificing the streaming advantage, fitting in
   ~60 MB total model weights (int8: ~32 MB VI + ~28 MB EN) — 7× smaller than
   Whisper Small's ~430 MB ASR footprint.

This record also revised two [ADR-007](ADR-007-translation-service.md) decisions —
the KV cache pre-allocation ([ADR-014](ADR-014-max-size-kv-cache-preallocation.md))
and the memory budget ([ADR-016](ADR-016-memory-budget.md)) — which now carry the
revision notes; it no longer records those amendments itself.

> **Split note (2026-09-25):** this record previously also carried the two ADR-007
> amendments above **and** the "ASR stays CPU-only" conclusion. The amendments now
> live as revision notes in the amended records, and the CPU-only conclusion is
> [ADR-027](ADR-027-asr-cpu-only.md).

## Decision

Kavi v1 implements ASR as **two parallel Zipformer-30M transducer instances** — one
for Vietnamese, one for English — running concurrently on separate CPU threads.
Language direction is determined by comparing confidence scores (logits extracted
from ONNX outputs) between the two streams.

### Model selection

| Direction | Model | Params | Size (int8, on-disk) | WER | Runtime |
| ----------- | ------- | -------- | ------------ | ----- | --------- |
| VI→EN | `sherpa-onnx-zipformer-vi-30M-int8-2026-02-09` | ~30M | **~32 MB** (encoder 26 MB + decoder 4.9 MB fp32 + joiner 1.0 MB + tokens 23 KB) | 7.97% (VLSP2025) | CPU via sherpa-onnx |
| EN→VI | `csukuangfj/sherpa-onnx-zipformer-small-en-2023-06-26` | ~20M | **~28 MB** (encoder 26 MB + decoder 1.3 MB + joiner 259 KB + tokens 5 KB) | N/A | CPU via sherpa-onnx |

*Note: the decoder stays fp32 in the VI int8 variant; the EN variant has an int8
decoder at 1.31 MB. On-disk sizes verified from the
[sherpa-onnx model catalog](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/zipformer-transducer-models.html)
and [HuggingFace file listings](https://huggingface.co/csukuangfj/sherpa-onnx-zipformer-small-en-2023-06-26/tree/main).*

**Confirmed in sherpa-onnx model catalog (Feb 2026):** multiple English Zipformer
transducer variants exist — Small (~20M), Medium, Large, and GigaSpeech-trained.
The Small variant is the best parity match for the ~30M VI model. All English
models are 2023 vintage, but English ASR is a mature domain;
Vietnamese-accented English benchmarking during Phase 4 will confirm adequacy.

### Language detection

- Both recognizers run **in parallel** on the same audio chunk.
- Each Zipformer transducer natively outputs per-token confidence scores in its
  JSON result (`ys_log_probs` for offline models, `ys_probs` for streaming
  models) — no manual logit extraction or softmax shim needed.
- Direction selected by `argmax(mean_confidence_vi, mean_confidence_en)`.
- Fallback threshold: if max confidence < 0.6, treat as undetermined and prompt
  the user (push-to-talk manual direction).

### Why Zipformer over Moonshine

| Factor | Zipformer-30M | Moonshine Tiny VI | Winner |
| -------- | --------------- | ------------------- | -------- |
| **WER (Vietnamese)** | **7.97%** | ~15–18% (est.) | **Zipformer** |
| **License** | **Apache 2.0** (unrestricted) | Community ($1M revenue cap) | **Zipformer** |
| **Streaming** | ✅ **Native** (transducer) | ❌ Offline only | **Zipformer** |
| **Model size (int8, on-disk)** | **~32 MB** | ~50 MB | **Zipformer** |
| **RTF** | **0.011** (91× real-time, desktop 1 thread) | 0.05–0.08 | **Zipformer** |
| **Confidence scores** | **Built-in `ys_log_probs`** (native per-token output) | Built-in token_log_probs | **Tie** |

Zipformer decisively wins on accuracy, license, streaming, size, and speed. The
confidence-score gap from earlier research is eliminated — Zipformer natively
outputs `ys_log_probs` per token, making language detection via confidence
comparison a simple extraction from the existing JSON result.

### Why dual (two models) over a single multilingual model (Whisper batch=2)

| Aspect | Whisper Small batch=2 (ADR-007) | Dual Zipformer (this ADR) |
| -------- | ------------------------------- | -------------------------- |
| **Encoder TTFT** | ~400–800 ms | **~40 ms** (10–20× faster) |
| **Total ASR memory** | ~430 MB | **~60 MB** (32 MB VI + 28 MB EN on-disk) |
| **Streaming** | Fixed 30s window | **Native chunk processing** |
| **Language detection** | Batch=2 in one decoder | **Parallel confidence from two streams** |
| **Vietnamese WER** | ~20–25% | **7.97%** |
| **QNN path** | Prebuilt on AI Hub | ❌ **No QNN artifacts exist** for Zipformer transducer (RNN-T) — see [ADR-027](ADR-027-asr-cpu-only.md) |

The streaming architecture alone justifies this change — Whisper's fixed 30s window
adds latency overhead on every utterance that directly pressures the 2.0 s
turnaround budget. Zipformer's streaming avoids this entirely.

## Alternatives considered

### Whisper Small (ADR-007 baseline)

- **Pros:** Multilingual, prebuilt QNN path on AI Hub, batch=2 language detection
- **Cons:** 20–25% VI WER vs 7.97% for Zipformer; fixed 30s window; ~670 MB ASR
  footprint; no streaming
- **Rejected:** the accuracy gap alone disqualifies it for the contest quality target

### Dual Moonshine Tiny (EN + VI)

- **Pros:** Built-in confidence scores via the `token_log_probs` API; merged
  encoder-decoder format simplifies loading
- **Cons:** ~15–18% estimated VI WER; offline-only (no streaming); Moonshine
  Community License has a $1M revenue cap; ~100 MB total model weights
- **Rejected:** worse accuracy, no streaming, restrictive license

### PhoWhisper Small

- **Pros:** Best VI WER (6.33% VIVOS) among Whisper-family models; inherits
  Whisper's multilingual support
- **Cons:** still 244M params; fixed 30s window; no streaming; same ~670 MB
  footprint as Whisper Small; DIY QNN export (no prebuilt AI Hub artifact)
- **Rejected:** retains Whisper's non-streaming architecture and large memory
  footprint

### Single Zipformer + separate language classifier

- **Pros:** Only one ASR model needed; simpler pipeline
- **Cons:** Requires an external language-ID model (ML Kit or Silero) —
  reintroducing the dependency [ADR-017](ADR-017-dual-asr-language-detection.md)
  explicitly eliminated
- **Rejected:** dual Zipformer preserves the "no external language detection" win

## Consequences

### Positive

- **Best-in-class Vietnamese ASR accuracy** — 7.97% WER vs Whisper Small's
  ~20–25%, directly improving translation quality.
- **Streaming-native architecture** — no fixed 30s window overhead; per-chunk
  processing eliminates ~400 ms of unnecessary encoder compute on short utterances.
- **~610 MB memory savings** — ASR footprint drops from ~670 MB to ~60 MB
  (on-disk model weights), freeing headroom for TTS and future enhancements
  ([ADR-016](ADR-016-memory-budget.md)).
- **Apache 2.0 license** — no revenue caps or enterprise licensing gates, unlike
  Moonshine.
- **Dual confidence comparison** preserves the "no external language detection"
  win.

### Negative / risk

- **Confidence scores are native** — Zipformer outputs `ys_log_probs` (offline) /
  `ys_probs` (streaming) per token in the JSON result. Mitigation: validate
  mean-confidence comparison across both model variants during Phase 4.
- **Dual models double the loading time** at cold start vs one Whisper; mitigated
  by both being small (~60 MB combined vs Whisper's ~430 MB).
- **No QNN path for Zipformer transducer** — see
  [ADR-027](ADR-027-asr-cpu-only.md).
- **EN Zipformer model quality unverified** — the EN-side Zipformer Small (2023
  vintage) may underperform on Vietnamese-accented English. Mitigation: benchmark
  against FLEURS-en during Phase 4; fall back to Whisper Small EN-only or another
  sherpa-onnx EN model if needed.
- **Two maintained ASR models** — v1 carries two separate Zipformer checkpoints
  with different update cycles. Mitigation: both use the same sherpa-onnx
  transducer interface, so maintenance is uniform.

## Pipeline (v1 Android)

```text
AudioRecord (mic, 16 kHz PCM float, circular buffer)
    ↓
[VAD: energy threshold] — see ADR-022
    ↓
[Tier 1: ADSP AI-ECNS] — hardware denoising (if available)
    ↓
[Tier 2: GTCRN] — software denoising (toggleable) — see ADR-018
    ↓
┌────────────────────────────────────────────────────────────┐
│ ASR (Dual Zipformer — two parallel streams)                │
│  Stream 1: Zipformer-30M-VI (CPU via sherpa-onnx)         │
│  Stream 2: Zipformer-Small-EN (CPU via sherpa-onnx)       │
│  Language selection → argmax(mean_confidence_vi, en)       │
└────────────────────────────────────────────────────────────┘
    ↓ (transcript in detected language)
┌────────────────────────────────────────────────────────────┐
│ MT (Opus-MT vi↔en) — encoder NPU, decoder CPU              │
└────────────────────────────────────────────────────────────┘
    ↓ (translated text)
┌────────────────────────────────────────────────────────────┐
│ TTS (see ADR-009)                                          │
└────────────────────────────────────────────────────────────┘
    ↓
AudioTrack (playback)
    ↓ (PeerToPeer mode only)
BLE 5.2+ → translated text sent to peer device → peer local TTS
```

### Concurrency model

```kotlin
scope.launch(Dispatchers.Default) {
    val cleaned = denoiser.apply(audio)                         // 16 kHz PCM float

    // Dual Zipformer streams — run concurrently
    val (viResult, enResult) = coroutineScope {
        val viDeferred = async { zipformerVi.transcribe(cleaned) }
        val enDeferred = async { zipformerEn.transcribe(cleaned) }
        awaitAll(viDeferred, enDeferred)
    }

    // Select language by confidence
    val (text, lang) = selectLanguage(viResult, enResult)

    val mtEncoded = mtEncoder.run(text, lang)                    // NPU
    val translated = mtDecoder.decode(mtEncoded)                 // CPU
    val audio = ttsModel.synthesize(translated)                  // CPU
    withContext(Dispatchers.Main) {
        audioTrack.write(audio)
        updateUI()
    }
}
```

### Memory savings in practice

Dual Zipformer running concurrently on 8 cores:

- Peak ASR memory: ~150 MB (dual models + streaming state)
- CPU core usage: 3–4 cores out of 8
- Leaves ~3+ cores for audio pipeline, UI, and OS
- **Reduces total pipeline RAM by ~660 MB vs Whisper Small**

## Android integration — sherpa-onnx

The sherpa-onnx project provides a complete Android integration path via JNI with
Kotlin API wrappers. A pre-built APK already exists for the Vi Zipformer 30M int8
model.

### Native library build

```bash
git clone https://github.com/k2-fsa/sherpa-onnx
cd sherpa-onnx

export ANDROID_NDK=/path/to/ndk

./build-android-arm64-v8a.sh

# Produces two .so files:
#   build-android-arm64-v8a/install/lib/libsherpa-onnx-jni.so  ~3.7 MB
#   build-android-arm64-v8a/install/lib/libonnxruntime.so     ~5.8 MB (mobile build)
# Total runtime overhead: ~10 MB
```

Alternatively, download pre-built shared libraries from the
[releases page](https://github.com/k2-fsa/sherpa-onnx/releases/latest) — pre-built
libs are available for all four Android ABIs.

### Model deployment

Model files are placed in `app/src/main/assets/`; asset provenance and delivery
rules are in [ADR-011](ADR-011-android-asset-provenance-delivery.md).

## References

- [ADR-007](ADR-007-translation-service.md) — Production inference architecture (parent)
- [ADR-014](ADR-014-max-size-kv-cache-preallocation.md) — KV cache (revised by this record)
- [ADR-016](ADR-016-memory-budget.md) — Memory budget (revised by this record)
- [ADR-017](ADR-017-dual-asr-language-detection.md) — **Superseded by this record**
- [ADR-027](ADR-027-asr-cpu-only.md) — ASR stays CPU-only (extracted from this record)
- [ADR-011](ADR-011-android-asset-provenance-delivery.md) — Asset provenance & delivery
- [sherpa-onnx Zipformer transducer models](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/zipformer-transducer-models.html) — WER/RTF benchmark source
