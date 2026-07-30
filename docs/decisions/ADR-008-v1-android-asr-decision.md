# ADR-008: v1 Android ASR Decision — Dual Zipformer

**Status:** Accepted
**Date:** 2026-07-27
**Deciders:** Kavi team
**Supersedes:** ADR-007 Decision 6 (Dual ASR inference — Whisper Small batch=2), Decision 5 (Memory budget — Whisper decoder allocation)
**Relates to:** ADR-007 (parent architecture — all other decisions stand), ADR-004 (benchmark-gated candidate set), ADR-006 (Android runner), ADR-002 (target platform)

---

## Context

ADR-007 proposed a production inference architecture with **Whisper Small** (244M params) using dual batch=2 decoding for language-autonomous direction detection. Since ADR-007 was written, detailed technical research has clarified the landscape for lightweight, streaming-capable ASR models on the Snapdragon 8 Gen 2 target.

Three key findings drove this decision:

1. **Zipformer-30M-RNNT achieves 7.97% WER on Vietnamese** (VLSP2025) — dramatically better than Whisper Small's ~20–25% on VIVOS, and better than any other license-clean candidate. Trained on 6,000 hours of Vietnamese speech including call-centre and conversational data — a strong domain match for Kavi's factory/logistics use case.

2. **Zipformer is streaming-native** — transducer architecture processes audio in chunks, unlike Whisper/Moonshine which operate on fixed-length windows. This fundamentally changes the pipeline design and latency profile.

3. **A dual-instance approach** (one Zipformer per language) achieves bidirectional coverage without sacrificing the streaming advantage, while fitting in ~20 MB total model weights (int8) — 20× smaller than Whisper Small's ~430 MB ASR footprint.

### What stays from ADR-007

All other ADR-007 decisions remain in effect for the v1 Android app:

| Decision | Content | Status |
| ---------- | --------- | -------- |
| Decision 1 | TranslationService — Two-mode foreground service (OneDevice + PeerToPeer) | **Kept** |
| Decision 2 | Persistent model residency — load everything at startup | **Kept** |
| Decision 3 | Max-size KV cache pre-allocation (Opus-MT decoder only; Zipformer transducers have no KV cache) | **Modified (see below)** |
| Decision 4 | NPU→CPU zero-copy via ION shared memory | **Kept** |
| Decision 5 | Memory budget | **Revised (see below)** |
| Decision 6 | Dual ASR inference for language-autonomous direction detection | **Superseded by this ADR** |
| Decision 7 | Denoising pipeline — tiered, toggleable (GTCRN) | **Kept** |
| Decision 8 | QNN runtime bundling — precise jniLibs/arm64-v8a roster | **Kept** |
| Decision 9 | Structured concurrency via Kotlin coroutines | **Kept** |
| Decision 10 | ONNX Runtime CPU decoder optimisations | **Kept** (applies to Opus-MT decoder) |
| Decision 11 | VAD — amplitude threshold + speech timeout | **Kept** |

---

## Decision: Dual Zipformer ASR for v1 Android

Kavi v1 implements ASR as **two parallel Zipformer-30M transducer instances** — one for Vietnamese, one for English — running concurrently on separate CPU threads. Language direction is determined by comparing confidence scores (logits extracted from ONNX outputs) between the two streams.

### Model selection

| Direction | Model | Params | Size (int8) | WER | Runtime |
| ----------- | ------- | -------- | ------------ | ----- | --------- |
| VI→EN | `sherpa-onnx-zipformer-vi-30M-int8-2026-02-09` | ~30M | ~10 MB | 7.97% (VLSP2025) | CPU via sherpa-onnx |
| EN→VI | `csukuangfj/sherpa-onnx-zipformer-small-en-2023-06-26` | ~20M | ~8 MB | N/A | CPU via sherpa-onnx |

**Confirmed in sherpa-onnx model catalog (Feb 2026):** Multiple English Zipformer transducer variants exist — Small (~20M), Medium, Large, and GigaSpeech-trained. The Small variant is the best parity match for the ~30M VI model. All English models are 2023 vintage, but English ASR is a mature domain; Vietnamese-accented English benchmarking during Phase 4 will confirm adequacy.

### Language detection

- Both recognizers run **in parallel** on the same audio chunk
- Each Zipformer transducer natively outputs per-token confidence scores in its JSON result (`ys_log_probs` for offline models, `ys_probs` for streaming models) — no manual logit extraction or softmax shim needed
- Direction selected by argmax(mean_confidence_vi, mean_confidence_en)
- Fallback threshold: if max confidence < 0.6, treat as undetermined and prompt user (push-to-talk manual direction)

### Why Zipformer over Moonshine

| Factor | Zipformer-30M | Moonshine Tiny VI | Winner |
| -------- | --------------- | ------------------- | -------- |
| **WER (Vietnamese)** | **7.97%** | ~15–18% (est.) | **Zipformer** |
| **License** | **Apache 2.0** (unrestricted) | Community ($1M revenue cap) | **Zipformer** |
| **Streaming** | ✅ **Native** (transducer) | ❌ Offline only | **Zipformer** |
| **Model size (int8)** | **~10 MB** | ~50 MB | **Zipformer** |
| **RTF** | **0.025** (40× real-time) | 0.05–0.08 | **Zipformer** |
| **Confidence scores** | **Built-in `ys_log_probs`** (native per-token output) | Built-in token_log_probs | **Tie** |

Zipformer decisively wins on accuracy, license, streaming, size, and speed. The confidence score gap from earlier research is eliminated — Zipformer natively outputs `ys_log_probs` per token, making language detection via confidence comparison a simple extraction from the existing JSON result.

### Why Dual (two models) over single multilingual (Whisper batch=2)

| Aspect | Whisper Small batch=2 (ADR-007) | Dual Zipformer (this ADR) |
| -------- | ------------------------------- | -------------------------- |
| **Encoder TTFT** | ~400–800 ms | **~40 ms** (10–20× faster) |
| **Total ASR memory** | ~430 MB | **~20 MB** |
| **Streaming** | Fixed 30s window | **Native chunk processing** |
| **Language detection** | Batch=2 in one decoder | **Parallel confidence from two streams** |
| **Vietnamese WER** | ~20–25% | **7.97%** |
| **QNN path** | Prebuilt on AI Hub | ❌ **No QNN artifacts exist** for Zipformer transducer (RNN-T). Only Zipformer CTC, Paraformer, and SenseVoice have QNN builds. Even if compiled, QNN's static input shapes are fundamentally incompatible with streaming transducer architecture. CPU-only is the correct path. |

The streaming architecture alone justifies this change — Whisper's fixed 30s window adds latency overhead on every utterance that directly pressures the 2.0 s turnaround budget. Zipformer's streaming avoids this entirely.

---

## Revised Decisions from ADR-007

### ADR-007 Decision 3 (modified): KV cache pre-allocation

The Zipformer transducer architecture has **no autoregressive KV cache** in the ASR stage — the decoder is a small RNN-T decoder that processes a frame at a time without caching past key-value pairs. The ~240 MB ASR KV cache allocation from ADR-007 Decision 5 is **eliminated**.

The Opus-MT decoder still uses autoregressive decoding with a KV cache. The MT KV cache allocation (~70 MB, max 256 tokens) from ADR-007 Decision 3 **remains unchanged**.

### ADR-007 Decision 5 (revised): Memory budget

The removal of Whisper Small's decoder (~350 MB) and its KV cache (~240 MB) dramatically reduces the ASR portion of the budget:

| Component | ADR-007 (Whisper) | ADR-008 (Dual Zipformer) | Delta |
| ----------- | ------------------- | -------------------------- | ------- |
| ASR encoder (NPU) | ~80 MB | **Eliminated** (CPU-only for v1) | −80 MB |
| ASR decoder (CPU) | ~350 MB | **~10 MB** (Dual Zipformer int8) | −340 MB |
| ASR KV cache (batch=2) | ~240 MB | **~0** (transducer, no KV cache) | −240 MB |
| **Total ASR** | **~670 MB** | **~10 MB** | **−660 MB** |

**New total accounted (statically allocated, max-size):** ~1.05 GB (down from ~1.71 GB)
**Remaining headroom within 4 GB ceiling:** ~2.95 GB (up from ~2.3 GB)

This ~660 MB saving provides substantial headroom for the TTS model (when selected), larger denoising models, or additional safety margin.

**NPU path ruled out for ASR v1 (confirmed):** Investigation of the sherpa-onnx QNN model catalog (Feb 2026) reveals that **Zipformer transducer (RNN-T) has no prebuilt QNN context binaries** — only Zipformer CTC (Chinese), Paraformer, and SenseVoice are available, all for SM8850 (Snapdragon 8 Elite) and newer chips. Even if DIY QNN compilation via QAIRT were pursued, three fundamental incompatibilities block it:

1. **Static input shapes** — QNN requires fixed-duration models (5s/10s/30s) with silent truncation beyond the limit. This is incompatible with streaming transducer processing where audio arrives in chunks.
2. **RNN-T decoder loop** — the iterative frame-by-frame decoder does not map cleanly to the HTP's fixed-graph execution model.
3. **Context binary size bloat** — existing QNN models are 241–351 MB (model.bin) vs ~10 MB ONNX int8, defeating the memory savings of Zipformer.

**Decision:** ASR stays **CPU-only** for v1. Zipformer RTF 0.011 on desktop (0.011 for a 3.7s clip at 1 thread) is fast enough that NPU offload provides no meaningful benefit within the 2.0 s turnaround budget. The ADR-007 NPU→CPU ION zero-copy pipeline still applies to **Opus-MT encoder** (which has real transformer decoder complexity and verified Qualcomm AI Hub support).

---

## Pipeline (v1 Android, revised)

```
AudioRecord (mic, 16 kHz PCM float, circular buffer)
    ↓
[VAD: energy threshold] — speech onset detected → capture until silence timeout
    ↓
[Tier 1: ADSP AI-ECNS] — hardware denoising (if available)
    ↓
[Tier 2: GTCRN] — software denoising (toggleable)
    ↓
┌────────────────────────────────────────────────────────────┐
│ ASR (Dual Zipformer — two parallel streams)                │
│  Stream 1: Zipformer-30M-VI (CPU via sherpa-onnx)         │
│    → VI transcript + per-token confidence                 │
│  Stream 2: Zipformer-Small-EN (CPU via sherpa-onnx)       │
│    → EN transcript + per-token confidence                 │
│  Language selection → argmax(mean_confidence_vi,           │
│                               mean_confidence_en)          │
│  Selected transcript → MT pipeline                         │
└────────────────────────────────────────────────────────────┘
    ↓ (transcript in detected language)
┌────────────────────────────────────────────────────────────┐
│ MT (Opus-MT vi↔en)                                        │
│  Encoder (NPU via QNN context binary)                      │
│    → encoder_hidden_states in ION buffer (zero-copy)       │
│  Decoder (CPU via ONNX Runtime, greedy)                    │
│    → translated text                                       │
└────────────────────────────────────────────────────────────┘
    ↓ (translated text)
┌────────────────────────────────────────────────────────────┐
│ TTS (model TBD, CPU via ONNX Runtime)                     │
│  → synthesised audio                                       │
└────────────────────────────────────────────────────────────┘
    ↓
AudioTrack (playback)
    ↓ (PeerToPeer mode only)
BLE 5.2+ → translated text sent to peer device → peer local TTS
```

### Concurrency model (revised for dual streams)

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

---

## Alternatives Considered

### Whisper Small (ADR-007 baseline)

- **Pros:** Multilingual, prebuilt QNN path on AI Hub, batch=2 language detection
- **Cons:** 20–25% VI WER vs 7.97% for Zipformer; fixed 30s window; ~670 MB ASR footprint; no streaming
- **Rejected:** Accuracy gap alone disqualifies it for the contest quality target

### Dual Moonshine Tiny (EN + VI)

- **Pros:** Built-in confidence scores via token_log_probs API; merged encoder-decoder format simplifies loading
- **Cons:** ~15–18% estimated VI WER; offline-only (no streaming); Moonshine Community License has $1M revenue cap; ~100 MB total model weights
- **Rejected:** Worse accuracy, no streaming, restrictive license

### PhoWhisper Small

- **Pros:** Best VI WER (6.33% VIVOS) among Whisper-family models; inherits Whisper's multilingual support
- **Cons:** Still 244M params; fixed 30s window; no streaming; same ~670 MB footprint as Whisper Small; DIY QNN export (no prebuilt AI Hub artifact)
- **Rejected:** Retains Whisper's non-streaming architecture and large memory footprint

### Single Zipformer + separate language classifier

- **Pros:** Only one ASR model needed; simpler pipeline
- **Cons:** Requires an external language ID model (ML Kit or Silero) — reintroducing the dependency ADR-007 explicitly eliminated
- **Rejected:** ADR-007's key win was eliminating external language detection; dual Zipformer keeps that win

---

## Consequences

### Positive

- **Best-in-class Vietnamese ASR accuracy** — 7.97% WER vs Whisper Small's ~20–25%, directly improving translation quality
- **Streaming-native architecture** — no fixed 30s window overhead; per-chunk processing eliminates ~400 ms of unnecessary encoder compute on short utterances
- **~660 MB memory savings** — ASR footprint drops from ~670 MB to ~10 MB, freeing substantial headroom for TTS and future enhancements
- **Apache 2.0 license** — no revenue caps or enterprise licensing gates, unlike Moonshine
- **NPU path confirmed infeasible** for Zipformer transducer — QNN's static input shapes are incompatible with streaming RNN-T architectures. ASR stays CPU-only, matching Zipformer's native RTF of 0.011–0.025 on desktop. NPU remains allocated to Opus-MT encoder via prebuilt Qualcomm AI Hub artifacts.
- **Dual confidence comparison** preserves ADR-007's key win of eliminating external language detection
- **All other ADR-007 decisions stand** — the architecture change is scoped to ASR only

### Negative / risk

- **Confidence scores are native** — Zipformer outputs `ys_log_probs` (offline) / `ys_probs` (streaming) per token in the JSON result. No manual logit extraction or softmax shim required. Mitigation: validate mean-confidence comparison works across both model variants during Phase 4.
- **Dual models double the loading time** — two Zipformer instances at cold start vs one Whisper. Mitigation: both are tiny (~10 MB each vs Whisper's ~430 MB), so total load time is still dramatically faster.
- **No QNN path for Zipformer transducer** — prebuilt QNN artifacts exist only for Zipformer CTC, Paraformer, and SenseVoice (all Chinese-focused, SoC-locked). QNN's fixed input shapes fundamentally conflict with streaming transducer processing. The RNN-T iterative decoder loop does not map to HTP's graph-execution model. Mitigation: CPU-only ASR is the correct architectural choice; NPU investment stays focused on Opus-MT.
- **EN Zipformer model quality unverified** — the EN-side Zipformer Small (2023 vintage) may underperform on Vietnamese-accented English. Mitigation: benchmark against FLEURS-en during Phase 4; fall back to Whisper Small EN-only or sherpa-onnx's other EN models if needed.
- **Two maintained ASR models** — instead of one multilingual model, v1 carries two separate Zipformer checkpoints with different update cycles. Mitigation: both use the same sherpa-onnx transducer interface, so maintenance is uniform.

### Open items for Phase 4 benchmarking

- [ ] Verify Zipformer-30M-VI WER on Kavi's bespoke factory/logistics eval set (not just VLSP2025)
- [ ] Benchmark Dual Zipformer RTF and peak RAM on the Meizu 21 Note (SD8G2)
- [ ] Implement and validate confidence-based language detection against a held-out code-switched set
- [ ] Evaluate EN Zipformer Small on Vietnamese-accented English (FLEURS-en subset)
- [ ] Compare turnaround latency: Dual Zipformer streaming vs Whisper Small fixed-window
- [x] NPU offload for Zipformer — ruled out. QNN's static input shapes and RNN-T decoder incompatibility make it infeasible for streaming transducer ASR. See QNN docs for context.

---

## References

- ADR-007: Production Inference Architecture & Service Layer (parent architecture, superseded for Decision 5–6)
- ADR-006: Android Runner Architecture (batch evaluation framework)
- ADR-004: Speech-to-Speech Architecture / Tech-Stack (Draft — benchmark-gated candidate set)
- ADR-002: Target Platform — Snapdragon 8 Gen 2, Android 16, Hexagon NPU
- `docs/benchmarking-plan.md` §4.1–4.3 — ASR candidate landscape (Zipformer, Whisper, Moonshine comparison)
- `docs/benchmarking-plan.md` §4.2 — Latency & memory estimates for Zipformer on SD8G2
- `docs/decisions/license-situation.md` — License clearance for all candidate models (Zipformer Apache-2.0 confirmed)
- [sherpa-onnx-zipformer-vi-30M-int8-2026-02-09](https://github.com/k2-fsa/sherpa-onnx/releases) — Vietnamese Zipformer model
- [Moonshine confidence API (PR #2897)](https://github.com/k2-fsa/sherpa-onnx) — sherpa-onnx token_log_probs support
- [sherpa-onnx QNN docs](https://k2-fsa.github.io/sherpa/onnx/qnn/) — QNN model catalog (Zipformer CTC/Paraformer/SenseVoice only; no Zipformer transducer)
- [sherpa-onnx Zipformer transducer models](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/zipformer-transducer-models.html) — confirmed `csukuangfj/sherpa-onnx-zipformer-small-en-2023-06-26` and other EN variants
- [sherpa-onnx Zipformer streaming models](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/online-transducer/zipformer-transducer-models.html) — confirmed `ys_probs` native output for streaming variants
