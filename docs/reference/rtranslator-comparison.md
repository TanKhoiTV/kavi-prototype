# ADR-007 vs RTranslator 2.1.5 — Architectural Comparison

**Date:** 2026-07-26
**RTranslator version:** 2.1.5 (commit `49e7f20`, tag `2.1.5`)
**Kavi ADR-007 status:** Proposed

> **Purpose:** Cross-reference the two architectures for the Kavi team. RTranslator
> is the closest production analogue to Kavi's design (offline speech-to-speech
> translation on Android) and served as the original inspiration for the
> OneDevice/PeerToPeer mode split. This document maps shared patterns, highlights
> divergences, and flags learnings from RTranslator's shipping experience.
>
> **Note on the contest scope:** RTranslator targets a general audience (29
> languages, 6+ GB RAM, CPU-only). Kavi targets a VI-EN contest (2 languages,
> 4 GB ceiling, NPU+CPU). Many architectural differences follow from this narrower
> scope rather than design merit — the comparison notes where this is the case.
>
> **Source documents:** `RTranslator/` (clone of niedev/RTranslator v2.00),
> `docs/decisions/ADR-007-translation-service.md`,
> `docs/rtranslator-test-protocol.md`.

---

## 1. High-Level Architecture Map

| Layer | RTranslator 2.1.5 | Kavi (ADR-007) |
| --- | --- | --- |
| **Service** | `VoiceTranslationService` (abstract Java) → `WalkieTalkieService` / `ConversationService` | `TranslationService` (Kotlin) with `OneDevice` / `PeerToPeer` modes |
| **Inference engine** | ONNX Runtime CPU 1.19.0 | QNN (NPU encoder) + ONNX Runtime CPU (decoders) |
| **ASR** | Whisper Small (6 ONNX files, CPU) | Whisper Small encoder on NPU (QNN context binary), decoder on CPU (ORT) |
| **MT** | NLLB-Distilled-600M (4 ONNX files, CPU) | Opus-MT vi↔en encoder on NPU (QNN), decoder on CPU (ORT) |
| **TTS** | Android system TTS (Google TTS / per-device) | Bundled ONNX model (MeloTTS / Piper / Kokoro — TBD) |
| **Denoising** | None | Tiered: ADSP AI-ECNS (DSP) + GTCRN (ONNX CPU, working default) |
| **Language detection** | ML Kit (Google Play Services, closed-source) | Dual ASR batch=2 confidence comparison (no external dependency) |
| **VAD** | Energy-based, 15-threshold margin, configurable | Energy-based (simpler v1), configurable |
| **Concurrency** | Java Threads + Handlers + `synchronized` | Kotlin coroutines + `Dispatchers.Default` |
| **NPU** | None | Hexagon HTP v73 via QNN context binaries |
| **BLE** | `BluetoothCommunicator` library (P2P + reconnection strategy) | BLE 5.2+ |
| **Memory ceiling** | 6 GB minimum recommended | 4 GB peak budget |
| **Model delivery** | Downloaded on first launch (~1.2 GB from GitHub) | Bundled in APK assets |

---

## 2. Model Pipeline Comparison

### RTranslator pipeline (WalkieTalkie)

```text
AudioRecord (PCM float, 16 kHz mono)
    ↓
Recorder (circular buffer, energy VAD, 15-threshold margin)
    ↓
Recognizer.recognize(data, beamSize, lang1, lang2)  ← ML Kit identifies direction
    ├── Whisper initializer (CPU)
    ├── Whisper encoder (CPU)
    ├── Whisper cache_initializer (CPU) — batch=2 for dual language
    ├── Whisper decoder (CPU, autoregressive, KV cache)
    └── Whisper detokenizer (CPU)
    ↓
Translator.detectLanguage() — ML Kit LanguageIdentifier (closed-source)
    ↓ two ASR results, one selected by confidence comparison
Translator.translate(text, inputLang, outputLang, beamSize)
    ├── SentencePiece tokenizer
    ├── NLLB encoder (CPU)
    ├── NLLB cache_initializer (CPU)
    └── NLLB decoder (CPU, autoregressive, KV cache)
    ↓
Android system TTS (TextToSpeech API)
    ↓
AudioTrack playback
```

### Kavi pipeline (ADR-007, OneDevice mode)

```text
AudioRecord (PCM float, 16 kHz mono)
    ↓
Recorder (circular buffer, energy VAD)
    ↓
Tier 1: ADSP AI-ECNS (DSP, if available)
    ↓
Tier 2: GTCRN denoiser (ONNX CPU)
    ↓
ASR encoder (NPU via QNN context binary)  ← single shared encoder
    ↓  ION zero-copy barrier (~1–3 ms cache-coherency fence)
ASR decoder (CPU, batch=2, greedy)  ← dual ASR selects direction via confidence
    ↓
MT encoder (NPU via QNN context binary)
    ↓  ION zero-copy barrier
MT decoder (CPU, greedy for v1)
    ↓
TTS synthesis (ONNX CPU — model TBD)
    ↓
AudioTrack playback
```

---

## 3. Detailed Dimension-by-Dimension Comparison

### 3.1 Inference Acceleration

| | RTranslator | Kavi |
| --- | --- | --- |
| **NPU** | Not used. All inference on CPU via ORT 1.19.0 | Hexagon HTP v73 for ASR + MT encoders (QNN context binaries compiled via QAIRT) |
| **GPU** | Not used. No GPU fallback mentioned | Not used in v1. `libQnnGpu.so` bundled for future-proofing only; v1 fallback chain is NPU→CPU (ADR-020) |
| **CPU optimisations** | `NO_OPT` on nearly all sessions. `CPUArenaAllocator(false)` and `MemoryPatternOptimization(false)` on < 7 GB RAM devices | `ALL_OPT` + `CPUArenaAllocator(true)` + `MemoryPatternOptimization(true)` on all CPU decoder sessions (ADR-021) |
| **Quantisation** | Partial int8 (some weights skipped to preserve quality) | Encoders: compiled QNN binary (quantised during QAIRT). Decoders: int8/XNNPACK per ADR-003 baseline |

**Key insight:** RTranslator runs everything on CPU as a practical necessity — it targets any Android phone with 6+ GB RAM. Kavi's NPU+CPU split is made possible by targeting a specific Snapdragon SKU (8 Gen 2). This is the single biggest architectural departure.

---

### 3.2 ASR (Whisper)

| | RTranslator | Kavi |
| --- | --- | --- |
| **Model** | Whisper Small (244M) | Whisper Small (244M) — same base model |
| **File split** | 6 ONNX files[^1] | 1 QNN context binary (encoder) + 1 ONNX (decoder) |
| **Encoder runtime** | ONNX Runtime CPU | QNN on Hexagon NPU |
| **Decoder runtime** | ONNX Runtime CPU | ONNX Runtime CPU (`IsNaN` blocked QNN conversion — ADR-005) |
| **Language support** | 29 high-quality (WER ≤ 37%) + ~60 low-quality | VI + EN only (contest scope) |
| **Batch configuration** | Two modes: single-language (batch=1) and dual-language (dedicated `cache_init_batch` session, batch=2); separate ONNX file per mode | Single `cache_init` session always runs at batch=2 (dual ASR for language detection) |
| **Beam search** | WalkieTalkie: `SPEECH_BEAM_SIZE=1`. Conversation: `SPEECH_BEAM_SIZE=4` | Greedy (beam=1) for v1; beam=4 deferred to Phase-5 as a latency-budget decision (ADR-020, note) |
| **Decoding** | Autoregressive with run-time KV cache allocation | Autoregressive with pre-allocated max-size KV cache (448 tokens, batch=2) |

[^1]: `Whisper_initializer.onnx`, `Whisper_encoder.onnx`, `Whisper_decoder.onnx`, `Whisper_cache_initializer.onnx`, `Whisper_cache_initializer_batch.onnx`, `Whisper_detokenizer.onnx`.

**Notable:** RTranslator already decomposes Whisper into the same encoder/decoder/cache_init split Kavi uses. Kavi's innovation is moving only the encoder to NPU — the computationally heavier stage (mel spectrogram + 3× transformer encoder blocks). The decoder stays on CPU in both designs.

---

### 3.3 Machine Translation

| | RTranslator | Kavi |
| --- | --- | --- |
| **Model** | NLLB-Distilled-600M (CC-BY-NC-4.0, non-commercial) | Opus-MT vi↔en (Apache-2.0, permissive) |
| **Parameters** | 600M | ~70M (Helsinki-NLP transformer-base)[^2] |
| **File split** | 4 ONNX files: encoder, decoder, cache_init, embed_and_lm_head | 1 QNN context binary (encoder) + 1 ONNX (decoder) |
| **Encoder runtime** | ONNX Runtime CPU | QNN on Hexagon NPU |
| **Decoder runtime** | ONNX Runtime CPU | ONNX Runtime CPU |
| **Tokenizer** | SentencePiece (shared `sentencepiece_bpe.model`) | SentencePiece (separate source/target `.spm` files) |
| **Beam search** | `TRANSLATOR_BEAM_SIZE=1`. Beam-search code present but doc-commented *"not updated, so it won't work with the final models"* | Greedy (beam=1) for v1; beam=4 path documented as latency-budget decision (ADR-020, note) |
| **Language support** | 29+ languages via NLLB's multilingual model | vi↔en only (contest scope) |
| **License** | CC-BY-NC-4.0 (non-commercial only). RTranslator 3.0 switching to MADLAD/HY-MT | Apache-2.0 |

[^2]: Confirmed from the on-disk model: the CTranslate2 int8 checkpoint at `models/opus-mt-vi-en-ct2/model.bin` is 71 MB for the full encoder+decoder. At ~70M total parameters in FP16 the decoder-only session is expected at ~60–80 MB, **not the 350 MB shown in ADR-016's conservative estimate**. The ADR's table uses the same 350 MB figure for both Whisper decoder and Opus-MT decoder, but the underlying models differ by ~3× in parameter count. This comparison uses the ADR's stated numbers for consistency (see §3.7 footnotes), but the Opus-MT decoder figure likely overstates reality by a factor of 4–5× and should be revised when ADR-007 moves from Proposed to Accepted.

**Key insight:** RTranslator's NLLB is licensed for non-commercial use only — this is why RTranslator 3.0 is switching models (to Bergamot/MADLAD/HY-MT). Kavi's Opus-MT choice was explicitly driven by this license constraint (see the [open-parameters register](../decisions/README.md#open-parameters)). The trade-off is model quality: NLLB-600M is a larger, higher-quality multilingual model, while Opus-MT at ~70M parameters is smaller and VI-EN-specific.

---

### 3.4 TTS

| | RTranslator | Kavi |
| --- | --- | --- |
| **Engine** | Android system TTS (`android.speech.tts.TextToSpeech`) | Bundled ONNX model (MeloTTS / Piper / Kokoro — open parameter) |
| **Voice quality** | Depends on device's TTS engine and installed voice packs | Deterministic (same model, same voice on every device) |
| **Model** | Google TTS recommended; user can install any engine | TBD — slot reserved in persistent-residency load sequence (ADR-013) |
| **Language packs** | Must be downloaded per-language via device TTS settings | Bundled in APK. Single model supports both VI and EN |
| **Offline at runtime** | Yes, if voice packs pre-downloaded | Yes, always |
| **Latency** | Uncontrolled (depends on TTS engine, voice pack size, device CPU) | Deterministic — integrated into pipeline latency budget |
| **Determinism** | None — different devices produce different TTS output | Full — same model, same graph, same output |

**Notable:** RTranslator offloads TTS to the Android system, which is simpler (no model to bundle or maintain) but gives up control over latency, determinism, and quality. The test protocol (§4.4, §5) documents this as a measurement pain point — system TTS voice packs must be pre-verified and recorded per-run. Kavi's bundled ONNX model eliminates this uncertainty at the cost of ~150 MB in the memory budget and ongoing voice-quality tuning.

---

### 3.5 Language Detection

| | RTranslator | Kavi |
| --- | --- | --- |
| **Method** | ML Kit LanguageIdentifier (Google Play Services) | Dual ASR batch=2, confidence comparison on decoder log-probabilities |
| **Library** | `com.google.mlkit:language-id:17.0.5` | None |
| **License** | Closed-source (Google proprietary) | N/A (Whisper weights: MIT) |
| **Offline** | Yes — ML Kit runs on-device. **But requires Play Services to be present and unblocked** (test protocol §2.1) | Always offline. Zero external dependencies |
| **Latency** | ~200 ms separate API call | 0 ms — absorbed into ASR decoder pass |
| **Accuracy** | Good for single-language text; degrades on code-switching or short utterances | TBD — depends on Whisper confidence calibration for VI vs EN. The decoder's log-probability-per-token is a reasonable signal but untested for this specific use case |
| **Direction selection logic** | In WalkieTalkie mode: ASR runs `recognize(data, beamSize, lang1, lang2)` → ML Kit identifies each result's language → confidence comparison selects direction | In OneDevice mode: ASR encoder runs once (language-agnostic) → decoder batch=2 (one slot per language) → confidence comparison selects direction |

**Key insight:** This is Kavi's cleanest architectural win over RTranslator. ML Kit is not just a licensing issue — it's a practical testing friction (the test protocol dedicates §2.1 to blocking Play Services network) and a runtime risk on devices where Play Services is missing, restricted, or version-mismatched. Kavi's batch=2 dual-ASR approach eliminates the separate LD model entirely.

---

### 3.6 Denoising

| | RTranslator | Kavi |
| --- | --- | --- |
| **Denoising** | None | Tier 1: ADSP AI-ECNS (DSP, hardware-dependent, free when available) |
| | | Tier 2: GTCRN (523 KB ONNX model via sherpa-onnx, permissive license) |
| **License** | N/A | GTCRN: permissive |
| **Status** | No denoising in pipeline | GTCRN is the working default for v1, pending benchmark confirmation (ADR-018 notes this as an open parameter) |
| **SNR strategy** | Physical: recommends Bluetooth headset / bone-conduction for noise rejection | Physical + software: BT headset optional; software denoising handles moderate noise without external hardware |

**Notable:** RTranslator's README recommends Bluetooth headsets (especially bone-conduction) as a noise-rejection strategy for the Conversation mode. Kavi adds a software denoising layer, which is important for the target use case (factories, construction sites, logistics centres) where external headsets may not always be worn.

---

### 3.7 Memory Management

| | RTranslator | Kavi (ADR-016) |
| --- | --- | --- |
| **Whisper encoder** | Part of 0.9 GB (~460 MB encoder portion)[^3] | ~80 MB (QNN context binary, NPU ION/DDR) |
| **Whisper decoder** | Included in 0.9 GB (~460 MB decoder portion)[^3] | ~350 MB (ONNX CPU, FP16 weights + decode graph)[^4] |
| **Total Whisper** | ~900 MB (or ~500 MB in low-RAM mode) | ~430 MB |
| **MT encoder** | Part of 1.3 GB NLLB total | ~80 MB (QNN context binary, NPU ION/DDR) |
| **MT decoder** | Included in 1.3 GB NLLB total | ~350 MB (ONNX CPU, FP16 weights + decode graph)[^4] |
| **Total MT** | ~1,300 MB (NLLB-600M) | ~430 MB (Opus-MT, conservative estimate) |
| **TTS** | System TTS (varies, not measured) | ~150 MB (bundled ONNX model, conservative estimate) |
| **Denoiser (GTCRN)** | N/A | ~50 MB |
| **ASR KV cache (batch=2)** | Run-time allocation (size varies) | ~240 MB (pre-allocated, max 448 tokens × 2) |
| **MT KV cache** | Run-time allocation (size varies) | ~70 MB (pre-allocated, max 256 tokens) |
| **ONNX Runtime / QNN .so** | ~15 MB (ORT only) | ~35 MB (ORT + QNN runtimes) |
| **Android app + service overhead** | Not itemised | ~200 MB (heap, framework, UI) |
| **Total accounted** | ~2,200 MB (Whisper + NLLB only; TTS/overhead unmeasured) | ~1,710 MB (all components, max-size allocations; see fn. 4) |
| **Device RAM required** | 6 GB minimum recommended; 8 GB for best experience | 4 GB ceiling (contest constraint); reference device has 16 GB |
| **Model loading** | Lazy — `Global.initializeTranslator()` and `Global.initializeSpeechRecognizer()` on first use | Eager — all models load in `TranslationService.onCreate()`, never released |
| **KV cache allocation** | Run-time, token-by-token via ORT tensor creation in decode loop | Pre-allocated max-size at startup, zero allocation in decode loop |

[^3]: RTranslator does not publish per-component breakdowns. The Whisper total of 0.9 GB (or 0.5 GB in low-RAM mode) covers initializer + encoder + decoder + cache_init + cache_init_batch + detokenizer. The encoder/decoder split within that is estimated.

[^4]: **Discrepancy with actual model sizes.** The ADR-007 table assigns the Opus-MT decoder the same 350 MB figure as the Whisper decoder, but these models differ significantly in size:

    - Whisper Small: ~244M total parameters → decoder ~120M params → FP16 ONNX ~240 MB → 350 MB is conservative (~1.5× overhead for ORT session internals).
    - Opus-MT (Helsinki-NLP vi↔en): ~70M total parameters → decoder ~35M params → FP16 ONNX ~70 MB → 350 MB is approximately **5× over**.
    - On-disk evidence: the full Opus-MT model in CTranslate2 int8 is **71 MB** (encoder + decoder combined). The QNN encoder context binary is also **71 MB** — so the 80 MB encoder estimate is accurate. The decoder is expected at ~60–80 MB in FP16, not 350 MB.

    **Recommendation for ADR-007:** Revise the Opus-MT decoder entry from ~350 MB to ~80 MB (or measure the actual ONNX FP16 export and update). This would reduce the total accounted budget from ~1.71 GB to ~1.44 GB and increase headroom within the 4 GB ceiling by ~270 MB. The 350 MB figure was likely copied from the Whisper decoder row as a conservative placeholder.

**Key insight:** RTranslator's lazy loading conserves cold-start time but means model init happens during the first utterance — adding latency to the first conversation turn. Kavi's eager loading pays a 2–3 s cold start for predictable per-utterance latency thereafter. Both trade-offs are valid for their respective product profiles (consumer app vs industrial tool).

---

### 3.8 VAD (Voice Activity Detection)

| | RTranslator | Kavi |
| --- | --- | --- |
| **Method** | Energy-based amplitude threshold | Energy-based amplitude threshold (ADR-022) |
| **Threshold** | `DEFAULT_AMPLITUDE_THRESHOLD = 2000` (in PCM16-scaled units, i.e. samples × 32767)[^5] | Configurable (exact value TBD in noise-benchmarking phase) |
| **Margin** | 15-threshold margin: requires 15+ consecutive under-threshold samples before declaring silence | Not specified (v1 design is single-threshold) |
| **Pre-voice duration** | Configurable: 100–1800 ms (default 1300 ms) — captures audio before threshold is crossed | Not specified (TBD in noise-benchmarking phase) |
| **Speech timeout** | Configurable: 100–5000 ms (default 1300 ms) | Configurable, default ~500 ms |
| **Max speech length** | 29 seconds (hard limit) | Not specified |
| **Model-based VAD** | Not used (no slot reserved) | Not used for v1 but a lightweight model slot is reserved (Silero VAD or similar — ADR-022 notes this) |
| **Manual/Push-to-talk** | Yes — dedicated manual mode with per-language recognition buttons alongside automatic VAD | Push-to-talk via UI toggle (not detailed in ADR-007) |

[^5]: **Unit conversion warning for implementers.** RTranslator's `amplitudeThreshold = 2000` operates on PCM16 (`ENCODING_PCM_16BIT`) samples in the range [-32768, 32767]. Kavi's `Recorder` uses `ENCODING_PCM_FLOAT` (range [-1.0, 1.0]). The raw constant 2000 does not transfer directly — the equivalent float threshold is approximately 2000 / 32768 ≈ **0.061**. Using 2000 unmodified in PCM_FLOAT mode would effectively disable VAD (threshold above the signal's maximum range). This note applies wherever RTranslator's VAD constants are referenced as design inspiration.

**Notable:** RTranslator's VAD is more battle-tested: the 15-threshold margin prevents noise spikes from falsely extending utterances; the configurable pre-voice duration (default 1300 ms) ensures no speech is lost at the start of an utterance. Kavi's simpler threshold-only approach is a valid v1 starting point, but the RTranslator parameters represent a useful baseline for the noise-benchmarking phase.

---

### 3.9 Concurrency Model

| | RTranslator | Kavi |
| --- | --- | --- |
| **Model** | Java `Thread` per operation (`new Thread("recognizer")`, `new Thread("textTranslation")`) | Kotlin coroutines on `Dispatchers.Default` within a lifecycle-scoped scope (ADR-020) |
| **Queue management** | `ArrayDeque<DataContainer>` with `synchronized(lock)` + `recognizing` / `translating` flags | Structured cancellation via `viewModelScope.launch` — no manual queue management |
| **ASR threading** | Each `recognize()` call spawns a thread; serialised via `recognizing` boolean + `dataToRecognize` deque | Sequential `suspend` functions in a single coroutine |
| **MT threading** | Each `translate()`/`translateMessage()` call spawns a thread; message translation uses its own deque + `translatingMessages` flag | Same coroutine scope as ASR — pipeline is a chain of suspend calls |
| **IPC** | `Messenger` + `Handler` (Binder-based) between service and Activity/Fragment | Not specified in ADR-007 (likely `Binder` + `Flow` / `LiveData`) |
| **Memory pressure in decode loop** | Explicit `result.close()` in every decode iteration to release ORT tensors; documented as *"serves to release the memory occupied by the result (otherwise it accumulates and increases a lot)"* | Pre-allocated buffers + structured scope handles cleanup; no per-token `close()` needed |
| **Error handling** | Error codes as int constants + `notifyError(int[] reasons, long value)` callback pattern | Structured `try/catch` in coroutine with per-encoder CPU fallback |

**Notable:** RTranslator's threading model works (it's a shipping app) but the manual `synchronized` + thread-creation-per-call + explicit `result.close()` pattern is fragile. The comment about memory accumulation in the decode loop is a concrete pain point. Kavi's coroutine approach is more idiomatic modern Android and makes cancellation and error propagation cleaner.

---

### 3.10 Model Delivery & Packaging

| | RTranslator | Kavi |
| --- | --- | --- |
| **Delivery** | Downloaded on first launch (~1.2 GB from GitHub) | Bundled in APK assets (`jniLibs/arm64-v8a/` + `assets/`) |
| **APK size** | ~10 MB (models downloaded separately) | **Estimated** ~1.5–2 GB based on the accounted memory footprint[^6] |
| **Versioning** | Model bundle version tracked in app UI | Models version-locked with QAIRT SDK (2.31.0.250130 ↔ qnn-2.31 — ADR-019) |
| **Sideloading** | Supported — manual model placement per `Sideloading.md` | Not applicable (models inside APK) |
| **First-launch UX** | Download progress screen (shown in `DownloadFragment`) with notification channel | Install-time APK size; no download needed |
| **Play Store** | Not on Play Store (sideload via GitHub Releases) | Not specified; APK distribution via MDM or sideloading for contest deployment |

[^6]: **Unsourced estimate.** This figure is not from ADR-007 — it is a rough projection from the ~1.71 GB runtime memory budget. On-disk model size (compressed ONNX / QNN context binaries) does not track runtime tensor layout 1:1. The actual APK size depends on compression ratios, ONNX protobuf overhead, and whether QNN context binaries are stored compressed. This estimate should be replaced with a measured value once the Phase-4 APK is built.

**Key insight:** RTranslator's model-download approach is more practical for broad distribution (Play Store's 100 MB APK limit) but introduces a network dependency at first launch and requires a download-manager UI (`DownloadReceiver`, `DownloadFragment`). Kavi's bundled approach eliminates the download but makes the APK very large — feasible for a targeted contest deployment via MDM or `adb install`, but a barrier if Play Store distribution is considered later.

---

### 3.11 ONNX Runtime Usage

| | RTranslator | Kavi |
| --- | --- | --- |
| **ORT version** | 1.19.0 (stable) | Later (no version specified in ADR-007) |
| **ORT extensions** | `OrtxPackage.getLibraryPath()` registered on **every** session (initializer, encoder, decoder, cache_init, detokenizer) | Not specified in ADR-007 |
| **CPU arena allocator** | Conditional on device RAM: `false` on < 7 GB, `true` on ≥ 7 GB | `true` (always enabled — ADR-021) |
| **Memory pattern optimisation** | Conditional on device RAM: `false` on < 7 GB, `true` on ≥ 7 GB | `true` (always enabled — ADR-021) |
| **Optimisation level** | `NO_OPT` on all encoder/decoder/cache_init sessions; only detokenizer uses ORT's default optimisation level | `ALL_OPT` on all CPU decoder sessions (ADR-021) |
| **Custom ops** | Required — RTranslator's Whisper detokenizer uses a fused custom op via `OrtxPackage`. The detokenizer session is the only one where optimisations are enabled, and it's the only one that registers `OrtxPackage` for a custom op | Not specified. If Kavi's CPU decoder graph fuses detokenization the same way (e.g. a Whisper `detokenizer.onnx` session with a custom `LogitsToText` op), `OrtxPackage` may still be needed on the CPU side **regardless of where the encoder runs**. Moving the encoder to QNN does not affect whether the CPU decoder graph has custom ops[^7] |

[^7]: **Correction to an earlier draft.** The earlier version of this comparison reasoned that Kavi *"likely"* doesn't need `OrtxPackage` *"if QNN handles encoders."* This logic is incorrect: `OrtxPackage` registers custom ops in the ONNX Runtime graph, which in both designs is the **CPU decoder** graph (not the encoder). RTranslator needed it for its Whisper detokenizer custom op. If Kavi's decoder pipeline similarly fuses detokenization into an ONNX session (rather than doing it in Java/Kotlin code), it will need `OrtxPackage` regardless of whether the encoder runs on NPU, CPU, or GPU. The ADR-007 text simply doesn't address this — it should be resolved during Phase-4 implementation.

**Notable:** RTranslator's aggressive use of `NO_OPT` is itself notable — it likely indicates that `ALL_OPT` caused graph-transformation errors during their conversion (a common issue with ORT's full optimisation pass on custom ops or unusual model splits). Kavi should validate `ALL_OPT` on each CPU decoder session independently during benchmarking, and be prepared to fall back to per-session optimisation levels if needed.

---

### 3.12 Bluetooth / Peer-to-Peer

| | RTranslator | Kavi |
| --- | --- | --- |
| **Library** | Custom `BluetoothCommunicator` library (`nie.translator.rtranslator.bluetooth`) with `STRATEGY_P2P_WITH_RECONNECTION` | BLE 5.2+ (no specific library named in ADR-007) |
| **Communication** | BLE (via `BluetoothCommunicator`); custom message types (`Message`, `BluetoothMessage`) with E2E encryption (`EncryptionKey.java`) | BLE 5.2+; protocol details not specified in ADR-007 |
| **Peer discovery** | `Peer` / `BluetoothConnectionServer` / `BluetoothConnectionClient` pattern | Not specified |
| **Reconnection** | Built-in reconnection strategy (`STRATEGY_P2P_WITH_RECONNECTION`) | Not specified |
| **Multi-peer** | Supports >2 devices in a conversation (single sender broadcast) | Two devices only (one speaker each) |
| **Data sent** | Translated text + language code appended as suffix (`text + langCode + langCode.length`) | Translated text (peer device handles local TTS synthesis) |

---

## 4. What Kavi Can Learn from RTranslator

### 4.1 Proven patterns worth adopting

1. **Whisper model decomposition (encoder/decoder/cache_init split):** RTranslator already proves this works — they split Whisper into separate init, encoder, decoder, cache_init, and detokenizer ONNX sessions. Kavi's NPU-encoder + CPU-decoder split is architecturally consistent with this proven approach.

2. **15-threshold VAD margin:** RTranslator requires 15 consecutive under-threshold samples before declaring silence, preventing momentary noise dips from falsely splitting utterances. Kavi's energy VAD should consider adopting a similar margin parameter during the noise-benchmarking phase.

3. **Pre-voice duration** (configurable `prevVoiceDuration`, default 1300 ms): RTranslator captures audio *before* the voice-trigger threshold is crossed, ensuring no speech is lost at the utterance start. Kavi's circular buffer design (already present in `Recorder`) should implement the same pre-roll.

4. **Manual mode fallback:** RTranslator supports push-to-talk with per-language manual recognition buttons alongside automatic VAD. This is a UX win for noisy environments where VAD struggles, and maps naturally to Kavi's OneDevice mode.

5. **KV cache lifecycle:** RTranslator's decoder loop demonstrates the pattern Kavi should follow: `cache_initializer` runs once per utterance, then the decoder iterates token-by-token feeding `present.key`/`present.value` back as `past_key_values`. Kavi's pre-allocated KV cache is an optimisation on top of the same pattern.

### 4.2 RTranslator pain points Kavi should avoid

1. **ML Kit dependency:** The test protocol (§2.1) shows how painful this is — requires blocking Play Services network, per-run pre-warm sequence, and risks runtime failure if Play Services is missing, restricted, or version-mismatched. Kavi's batch=2 dual-ASR approach is the right fix.

2. **Lazy model loading:** RTranslator initialises models on first use, adding cold-start latency to the first utterance and forcing every service to check `if(translator == null) { initializeTranslator(callback) }`. Kavi's eager loading in `TranslationService.onCreate()` is cleaner, though it moves the latency to app launch.

3. **Broken beam search for MT:** RTranslator's beam-search code for NLLB is documented as *"not updated, so it won't work with the final models"* and crashes at runtime. This is a cautionary tale — beam search is not free, and Kavi's decision to defer it to Phase-5 with clear latency-budget reasoning (ADR-020 note) is prudent.

4. **Thread-per-call concurrency:** RTranslator spawns `new Thread("recognizer")` and `new Thread("textTranslation")` for each operation, managing work queues manually with `synchronized`. The explicit `result.close()` calls in the decode loop (with the comment *"otherwise it accumulates and increases a lot"*) highlight the memory-pressure risk. Kavi's coroutine approach is safer and more maintainable.

5. **`NO_OPT` on all sessions:** This is a red flag — it likely indicates that ORT's graph optimisation pass caused errors during RTranslator's conversion (common with custom ops like `OrtxPackage`). Kavi should validate `ALL_OPT` per-session and be prepared to tune optimisation levels individually.

### 4.3 Data points from RTranslator's test protocol

The `docs/rtranslator-test-protocol.md` reveals several practical insights applicable to Kavi's benchmarking:

- **Thermal management is critical** (§2 items 7–8): The protocol requires recording thermal state before and after each run, and waiting 10+ seconds between utterances. Kavi's NPU should be more thermally efficient than CPU-only, but this needs validation.
- **Pre-warm sequence** (§5): RTranslator needs 2–3 pre-warm utterances to stabilise ML Kit and TTS. Kavi's persistent model residency should eliminate this, but the first utterance after cold start still includes the 2–3 s model-loading delay.
- **System TTS variability** (§2 items 11–12): The protocol records "System TTS engine + version" and "voice pack" per run because these are uncontrolled variables. Kavi's bundled TTS eliminates this variance.
- **Low-RAM mode exists** (§2 item 13): RTranslator's Whisper model has a documented low-RAM mode (0.5 GB vs 0.9 GB) for devices with < 8 GB RAM. Kavi's 4 GB ceiling is tighter, so a similar memory/accuracy trade-off may be worth planning for.
- **Per-utterance latency capture** (§7): RTranslator's baseline template captures ASR transcript, MT translation, TTS audio, and end-to-end latency per utterance. Kavi's ADR-006 runner should capture the same dimensions for direct comparison.

---

## 5. Summary: What Changes from RTranslator's Design

| Dimension | RTranslator 2.1.5 | Kavi (ADR-007) | Nature of change |
| --- | --- | --- | --- |
| **Compute** | CPU-only (ORT 1.19.0) | NPU (QNN) for encoders + CPU (ORT) for decoders | New compute unit |
| **Language detection** | ML Kit (Google Play Services) | Dual ASR batch=2 confidence comparison | Removed external dependency |
| **TTS** | System TTS (uncontrolled variability) | Bundled ONNX model (deterministic) | Added determinism |
| **Denoising** | None | GTCRN + ADSP tiered pipeline | New pipeline stage |
| **MT model** | NLLB-600M (non-commercial license) | Opus-MT vi↔en (Apache-2.0) | License-driven model change |
| **Model loading** | Lazy (on first use) | Eager (at service start) | Latency predictability trade-off |
| **Concurrency** | Java Threads + Handlers | Kotlin coroutines | Concurrency model modernisation |
| **Model delivery** | First-launch download (~1.2 GB) | Bundled in APK | Distribution strategy |
| **Memory target** | 6 GB RAM (implicit minimum) | 4 GB peak budget (explicit) | Tighter resource constraint |
| **Language scope** | 29+ languages | 2 languages (VI-EN) | Scope reduction (contest-driven) |
| **KV cache** | Run-time allocation (token-by-token) | Max-size pre-allocation at startup | Memory predictability |
| **ORT optimisations** | `NO_OPT` (conservative) | `ALL_OPT` (aggressive) | Performance optimisation |
| **CPU arena allocator** | Conditional on device RAM | Always enabled | Performance optimisation |

The most consequential architectural departure is the **NPU+CPU split** — everything else (model decomposition into encoder/decoder/cache_init, circular-buffer audio capture, energy-based VAD, KV-cache autoregressive decode loop) follows patterns RTranslator already proved viable. Kavi's main improvements are:

1. **Eliminating the ML Kit dependency** (dual-ASR batch=2) — the single most impactful change for offline-first reliability
2. **Adding software denoising** (GTCRN) — critical for the target noise environment
3. **Tighter memory budget with explicit accounting** — enables predictable performance on the 4 GB contest target
4. **Switching to a permissively-licensed MT model** (Opus-MT) — necessary for commercial deployment

The price Kavi pays is a larger APK (bundled models), longer cold start (eager loading), and narrower language support (VI-EN only) — all acceptable trade-offs given the contest scope.

---

## References

- `RTranslator/` — Clone of niedev/RTranslator v2.00 (commit `e1cd028`)
- `docs/decisions/ADR-007-translation-service.md` — Kavi's production inference architecture
- `docs/decisions/ADR-005-qnn-isnan-workaround.md` — Encoder/NPU, decoder/CPU split rationale
- `docs/rtranslator-test-protocol.md` — RTranslator baseline test procedure
- `bench/candidates/opusmt_mt.py` — CTranslate2 Opus-MT candidate adapter
- `bench/qnn/export_opusmt_onnx.py` — Opus-MT ONNX export script
- `models/opus-mt-vi-en-ct2/` — CTranslate2 Opus-MT checkpoint (71 MB int8)
- `models/qnn/opus-mt-vi-en/` — QNN Opus-MT encoder context binary (71 MB)
