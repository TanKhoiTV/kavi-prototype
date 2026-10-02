# Additional Reading — Onboarding Syllabus

**Audience:** Undergraduate-level new members with basic university CS/CE coursework (data structures, algorithms, introductory ML, maybe one mobile or systems elective). **No Android, no speech recognition, no edge-AI deployment experience expected.**

**How to use this:** Each section is ~1–2 weeks of self-study at a comfortable pace. You don't need to master everything before contributing — read the first two sections (Android fundamentals + ONNX Runtime), skim the rest for vocabulary, and come back to the relevant section when a task touches that area.

**Prerequisites you already have:** Java or Kotlin syntax (enough to read code), basic linear algebra (matrix multiply, vectors), introductory machine-learning vocabulary (training vs inference, model, weight, loss). Everything else is built on top.

---

## 1. Android Service Model & Lifecycle

**Why this matters:** Kavi's `TranslationService` is an Android foreground service — it runs persistently, binds to the UI via Binder, and must survive configuration changes and low-memory kills. You cannot write or debug the pipeline without understanding how Android manages long-lived background work.

**Key concepts**

- Android `Service` vs `Foreground Service` vs `Bound Service`. Why the notification is mandatory (Android 8+).
- `onCreate()` → `onStartCommand()` → `onBind()` → `onDestroy()` — where models load, where inference runs, where cleanup happens.
- Process lifecycle and the "importance hierarchy" — why a foreground service (vs a plain `Service` or a `Worker`) guarantees your inference isn't killed mid-utterance.
- `Binder` and one-shot vs `Messenger` for service-to-activity IPC. (Kavi's IPC layer is not fully specified in ADR-007 — it will likely use a coroutine bridge via `Flow` / `LiveData` over Binder, but this should be confirmed during Phase-4 implementation.)

**Resources**

- [Android Developer Guide: Services](https://developer.android.com/guide/components/services) — start here, especially the Foreground Service section.
- [Android Processes and Threads Overview](https://developer.android.com/guide/components/processes-and-threads) — the process-lifecycle table is worth memorising.
- **In our codebase:** `app/src/main/java/com/kavi/app/service/TranslationService.kt` — trace `onCreate()` → model loading → `onBind()` → `startCommand()`.

**You're done when:** You can explain why a foreground service is preferred over a WorkManager task for real-time audio processing, and you can find where in `TranslationService` the pipeline stages are wired together.

---

## 2. ONNX Runtime on Android

**Why this matters:** Every CPU-side model in Kavi (Whisper decoder, Opus-MT decoder, TTS, GTCRN denoiser) runs through ONNX Runtime. You need to understand sessions, tensors, and the I/O pattern to add a new model or debug a crash.

**Key concepts**

- `OrtEnvironment` (singleton) vs `OrtSession` (per-model). Sessions hold the compiled graph and weights.
- `OnnxTensor` — the currency of inference. How to wrap a Java `FloatBuffer` into a tensor, run the session, and read outputs. The zero-copy ION handoff (ADR-015) is an optimisation on top of this same I/O pattern.
- Session options: optimisation level (`ORT_ENABLE_ALL`), CPU arena (`CpuArenaAllocator`), memory pattern (`MemoryPatternOptimization`). Each is a latency-vs-RAM trade-off you may need to tune per-model (as RTranslator did per-device).
- Running multiple sessions concurrently vs sequentially — the pipeline design in ADR-007 chains them sequentially, but the KV cache pre-allocation (ADR-014) means the same tensors are reused across decode iterations within one utterance.

**Resources**

- [ONNX Runtime Android Java API Reference](https://onnxruntime.ai/docs/api/java/) — read the `OrtSession.run()` and `OnnxTensor` pages, skip the training API.
- [ORT Android sample app](https://github.com/microsoft/onnxruntime-inference-examples/tree/main/java/android) — the simplest end-to-end example. The sample runs a single model; Kavi's innovation is chaining multiple sessions with KV cache reuse.
- **In our codebase:** `app/src/main/java/com/kavi/app/inference/` — the `Orchestrator` class that creates sessions and dispatches inference.

**You're done when:** You can load any ONNX model, feed it a tensor, and read the output from Kotlin without looking at a reference.

---

## 3. Speech Recognition (Whisper)

**Why this matters:** Whisper Small is the ASR engine — the longest-latency pipeline stage and the one where most quality issues surface. You need to understand mel spectrograms as the encoder input, the encoder/decoder split (which maps to Kavi's NPU/CPU boundary), and how the decoder's autoregressive loop produces text token by token.

**Key concepts**

- **Mel spectrogram:** The encoder doesn't process raw audio. It takes a 2D time-frequency image (80 mel bands × 3000 time frames for a 30-second window). Understand the pipeline: raw PCM → windowed FFT → mel-filterbank → log-magnitude → normalise. Kavi's `Recorder` captures raw PCM; the mel conversion happens inside the Whisper encoder (now on NPU, so opaque to the CPU side).
- **Encoder/decoder split:** The encoder runs once per utterance and produces a cross-attention representation. The decoder then iterates token-by-token, attending to those encoder outputs plus its own previously generated tokens (via KV cache). In Kavi, the encoder is on NPU; the decoder stays on CPU because its autoregressive loop doesn't map well to QNN (ADR-005).
- **Autoregressive decoding and KV cache:** At each step the decoder predicts the next token. The KV cache stores the key-value pairs from previous steps so they don't need to be recomputed. ADR-014 pre-allocates the maximum KV cache size at startup so the decode loop allocates zero additional memory.
- **Byte-level BPE tokenizer:** Whisper doesn't use SentencePiece. It uses byte-level BPE (like GPT-2) with **51,865 tokens** in the multilingual vocabulary (50,257 base BPE + ~1,608 special/language/task/timestamp tokens). This is relevant if you ever need to implement or debug the detokenizer on the CPU side.

**Resources**

- [OpenAI Whisper blog post](https://cdn.openai.com/papers/whisper.pdf) — the paper. Read the architecture section (Figure 1, §2.2) and the tokenizer section (§2.4). Skip the training data and multilingual benchmarks.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — CTranslate2-based CPU optimisation of the same architecture. By contrast, Kavi's decoder runs through ONNX Runtime's Java API — a design choice that avoids hand-rolling per-step native code (the argument for ADR-007's Path B over Paths A/C).
- **In our codebase:** `bench/candidates/whisper_asr.py` for the Python reference; `app/src/main/java/com/kavi/app/inference/decoder/WhisperDecoder.kt` for the Android side.

**You're done when:** You can explain why the encoder runs once and the decoder runs N times (where N = utterance length in tokens), and what "KV cache" means in terms of tensors flowing through the decoder loop.

---

## 4. Neural Machine Translation (Opus-MT)

**Why this matters:** Opus-MT vi↔en is the MT engine — smaller and simpler than Whisper, but architecturally very similar (encoder-decoder transformer). Understanding it reinforces the same encoder/decoder/KV-cache patterns, and the licence difference (Apache-2.0 vs Whisper's MIT) matters for deployment.

**Key concepts**

- **Encoder-decoder transformer:** Same architecture as Whisper's decoder but no cross-modal encoder (Opus-MT is text-to-text). The encoder processes the source sentence, the decoder generates the target sentence autoregressively.
- **SentencePiece tokenizer:** Unlike Whisper's byte-level BPE, Opus-MT uses SentencePiece with separate source and target `.spm` models. The vocab is ~32,000 tokens per side. See `models/opus-mt-vi-en-src/source.spm` and `target.spm`.
- **Smaller model, same pattern:** Opus-MT is ~70M parameters (vs Whisper's 244M). The decoder fits in ~60–80 MB FP16 (see the comparison doc §3.7 fn. 4 for why the ADR's 350 MB estimate is conservative). This is the model to start with if you want to trace the encoder/decoder/KV-cache pattern end-to-end in a debugger — the tensors are small enough to inspect easily.

**Resources**

- [Helsinki-NLP Opus-MT](https://huggingface.co/Helsinki-NLP) — the model family page. The vi-en model is `Helsinki-NLP/opus-mt-vi-en`.
- [SentencePiece GitHub](https://github.com/google/sentencepiece) — read the README to understand the unigram language-model tokeniser. You don't need to build it; just understand that it works on raw text without a pre-tokeniser (unlike BPE which runs on whitespace-split words).
- **In our codebase:** `bench/candidates/opusmt_mt.py` for the Python CTranslate2 reference; `models/opus-mt-vi-en-ct2/model.bin` for the on-disk int8 weights.

**You're done when:** You can explain the structural difference between Whisper's byte-level BPE and Opus-MT's SentencePiece tokenizer, and why that difference matters for the detokenizer on the CPU side.

---

## 5. Qualcomm AI Runtime / QNN

**Why this matters:** The NPU encoder split (confirmed in ADR-005, reinforced by ADR-007 Decisions 3–4) is Kavi's main architectural innovation. You don't need to master QAIRT — Qualcomm's toolchain does the heavy lifting — but you need to understand what a "context binary" is, how it gets loaded, and where the I/O boundary between NPU and CPU lives.

**Key concepts**

- **QNN vs ONNX Runtime:** QNN is Qualcomm's inference SDK for Hexagon NPU. It takes an ONNX file and compiles it to a **context binary** (`.bin`) that runs on the HTP (Hexagon Tensor Processor). The CPU side never sees the model graph — only the compiled binary.
- **Context binary:** A self-contained bundle of compiled compute graphs for the NPU. Kavi ships two of these in `assets/` (not in `jniLibs/` — see ADR-019's file roster): `whisper_encoder_v73.bin` (~80 MB) and `opusmt_encoder_v73.bin` (~80 MB). They are loaded via `QnnModelLoader`, not via ONNX Runtime. The `.so` runtime libraries (libQnnHtp.so, etc.) live in `jniLibs/arm64-v8a/`.
- **ION shared memory:** The zero-copy handoff (ADR-015). The NPU writes encoder output directly to an ION buffer (a Linux DMA-buf). The CPU reads from the same physical memory — no memcpy. A cache-coherency fence (~1–3 ms for a ~5 MB transfer) synchronises the two sides.
- **QAIRT SDK version lock:** Kavi pins `qnn-2.31.0.250130` (ADR-019). The context binaries are compiled with a specific QAIRT version and will not load with a different runtime library. This is why the `jniLibs` roster is precise and versioned.

**Resources**

- [Qualcomm AI Hub Documentation](https://aihub.qualcomm.com/docs/) — start with the "Deploy on Device" section to understand the workflow. You don't need to run it; just understand the QNN→ONNX→context-binary pipeline.
- [Snapdragon Neural Processing Engine SDK Overview](https://developer.qualcomm.com/sites/default/files/docs/snpe/overview.html) — the predecessor to QAIRT. The concepts (DLC files instead of context binaries, ION buffers, HTP loading) are the same.
- **In our codebase:** `docs/decisions/ADR-005-qnn-isnan-workaround.md` for the concrete conversion-failure story; `models/qnn/` for the actual context binaries.

**You're done when:** You can draw the data flow from PCM audio → NPU encoder context binary → ION buffer → CPU decoder session, and explain why the QAIRT version matters for the `jniLibs` roster.

---

## 6. Voice Activity Detection & Audio Fundamentals

**Why this matters:** The pipeline starts and ends with audio. VAD determines utterance boundaries — get it wrong and the system either cuts off speech or never stops listening. The energy-based VAD in ADR-022 is deliberately simple for v1, so expect to work on this.

**Key concepts**

- **PCM audio on Android:** `AudioRecord` captures raw PCM float samples at 16 kHz mono. Understand sample rate (16,000 Hz = 16,000 floats per second), bit depth (32-bit float), and how a circular buffer stores the last ~30 seconds of audio (ADR-016, memory budget table: ~5 MB buffer).
- **Energy-based VAD:** Compute RMS of a short window (e.g. 30 ms). If RMS > threshold, "speech." If RMS < threshold for N consecutive windows, "silence." RTranslator uses N=15 with a configurable threshold of 2000 in PCM16 units (≈ 0.061 in PCM float — see the comparison doc §3.8 fn. 5 for the unit-conversion trap). Kavi's v1 is the same pattern, simpler (single threshold, no margin).
- **Pipeline ordering (important):** The pipeline is VAD → denoising → ASR. The VAD first detects speech onset (using the raw audio's energy), then the denoiser (GTCRN) cleans the captured audio, then ASR runs on the denoised signal. VAD does **not** run on denoised audio — the energy threshold operates on raw mic input, and denoising is a separate stage that prepares audio for the ASR model.
- **Amplitude vs SNR:** Energy VAD fails when background noise has as much energy as speech. This is why Kavi adds a denoising stage after VAD and reserves a model-based VAD slot (Silero, ADR-022) for a later phase — a neural VAD can distinguish speech from noise by acoustic features rather than raw energy.
- **Pre-voice buffer:** VAD can't detect speech until the speaker has started. A circular buffer with a pre-roll (RTranslator uses 1300 ms default) captures the utterance onset. Kavi's `Recorder` already implements this.

**Resources**

- [Silero VAD](https://github.com/snakers4/silero-vad) — the industry-standard lightweight model-based VAD. The README has a good explanation of why energy VAD fails in noisy conditions. Kavi reserves a slot for a model like this in Phase-2.
- [AudioRecord API reference](https://developer.android.com/reference/android/media/AudioRecord) — read `read(float[], int, int)` and the `ENCODING_PCM_FLOAT` note. Understand the difference between `MODE_STATIC` and `MODE_STREAM`.
- **In our codebase:** `app/src/main/java/com/kavi/app/audio/Recorder.kt` — the circular buffer and VAD gate; `app/src/main/java/com/kavi/app/audio/Denoiser.kt` — the GTCRN wrapper.

**You're done when:** You can explain why a 15-threshold margin and a 1300 ms pre-roll exist, and why the threshold constant needs rescaling between PCM16 and PCM float.

---

## 7. BLE Peer-to-Peer Communication

**Why this matters:** PeerToPeer mode (ADR-007) enables two phones to exchange translations over BLE. This is the second most complex subsystem after the inference pipeline.

**Key concepts**

- **BLE GATT architecture:** Central vs Peripheral. One device acts as the GATT server (advertises a service with characteristics), the other as the GATT client (discovers and reads/writes). For a symmetric conversation, each device is both a server for its own translation service and a client for the other.
- **Payload size and MTU:** BLE L2CAP MTU is typically 23 bytes (Android default) or up to 512 bytes after MTU negotiation. A Vietnamese sentence can easily be 100+ bytes. You need to chunk translations into MTU-sized packets and reassemble on the receiving side.
- **Reconnection strategy:** RTranslator uses `STRATEGY_P2P_WITH_RECONNECTION` — if the link drops, it auto-reconnects. This is essential for real-world use (walking out of range, pocket interference). Kavi's BLE layer is not detailed in ADR-007; expect to design this during implementation.
- **BLE vs Classic Bluetooth:** Kavi specifies BLE 5.2+. BLE has lower power and more modern API (`BluetoothLeScanner` instead of `BluetoothDevice.createRfcommSocketToServiceRecord`), but lower throughput. For text-only translations (< 1 KB per utterance), throughput is not the bottleneck — reliability and reconnection are.

**Resources**

- [Android BLE Overview](https://developer.android.com/develop/connectivity/bluetooth/ble/ble-overview) — start with the GATT architecture page. Understand services, characteristics, descriptors, and the difference between `onCharacteristicWrite` and `onCharacteristicChanged` (notification).
- [Android BLE Scanning](https://developer.android.com/develop/connectivity/bluetooth/ble/scan) — for the PeerToPeer discovery flow.
- **In our codebase:** `app/src/main/java/com/kavi/app/ble/` — the BLE communicator layer (to be designed; currently placeholder). RTranslator is the closest reference: `RTranslator/app/src/main/java/nie/translator/rtranslator/bluetooth/BluetoothCommunicator.java`.

**You're done when:** You can describe the GATT server/client setup for a symmetric two-device conversation and explain why MTU negotiation matters.

---

## 8. Putting It Together: The Pipeline End-to-End

Once you've covered the sections above (even just skimming the last few), read the following in order:

1. **ADR-007** (`docs/decisions/ADR-007-translation-service.md`) — all 11 decisions. You now have the vocabulary for every term in the document.
2. **ADR-007 vs RTranslator comparison** (`docs/reference/rtranslator-comparison.md`) — the dimension-by-dimension comparison reinforces each concept and shows where Kavi's design differs from a real shipping product.
3. **ADR-005** (`docs/decisions/ADR-005-qnn-isnan-workaround.md`) — the concrete story of why the decoder stayed on CPU and how that shapes the NPU/CPU boundary.
4. **The code itself:** Start with `TranslationService.kt`, trace one utterance end-to-end, then drill into the component you're assigned to.

**You're ready to contribute when:** You can look at any table row or code comment in the Kavi codebase and identify which ADR decision it implements, which model it touches, and whether the compute goes through ONNX Runtime or QNN.
