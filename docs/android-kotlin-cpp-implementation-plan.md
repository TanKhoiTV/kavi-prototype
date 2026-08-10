# Android Kotlin + C++ Implementation Plan

> **Status:** Draft — planning only (no code changes yet)
> **Date:** 2026-08-05
> **Branch:** `docs/android-kotlin-cpp-implementation` (off `main`)
> **Target repo:** `android/` = **kavi-android** submodule (`github.com:TanKhoiTV/kavi-android.git`)
> **Supersedes/relates to:** `docs/android-implementation-plan.md` (Milestones 0–6, **PR #95**) — this doc is the *technical blueprint* underneath those milestones; ADR-007 (service/architecture), ADR-008 (Dual Zipformer ASR), ADR-009 (Supertonic TTS), ADR-010 (`ALL_OPT`), ADR-011 (asset provenance, **PR #95**)
> **Scope guard:** planning only — no `android/` or `app/` code changes on this branch.

---

## 1. Purpose

Turn ADR-007 → ADR-011 and the existing android-implementation-plan milestones into a
concrete, file-level implementation blueprint for the **Kotlin app layer** and the
**C++/NDK core**. It specifies: the layered architecture, every Kotlin and C++ file to
create/modify, the JNI contract, build wiring, the data/threading flow, the memory
budget mapping, fallbacks, testing, and a build-by-build sequencing with effort.

## 2. Current state audit (verified 2026-08-05)

| Area | State | Gap |
| --- | --- | --- |
| Build | AGP 8.10.0, Gradle 8.11.1, Kotlin 2.0.21, NDK 26.1.10909125, CMake 3.22.1, compile/target 36, min 24, arm64-v8a only | No sherpa-onnx, no ORT, no jniLibs source sets beyond bundled QAIRT |
| Native | `qnn_loader_jni.cpp`: dlopen `libQnnHtp.so` + dlsym C API ✓; backend create ✓; context-from-binary ✓ | **`nativeExecute` is a stub** (zero 64 KB out); provider struct offsets hardcoded; no graph enumeration, no `Qnn_Tensor_t` creation, no ION, no version-lock check |
| Kotlin | `QnnModelLoader.kt` (init/load/execute/shutdown, VmPeak timing), `ManifestReader.kt`, `NetworkMonitor.kt` (runner pkg) | No service, no audio, no pipeline, no TTS/ASR engines, no BLE |
| UI | `MainActivity` scaffold ("Kavi — on-device speech-to-speech (scaffold)") | Full walkie-talkie UI |
| Manifest | No permissions, single launcher activity | No `FOREGROUND_SERVICE`/`RECORD_AUDIO`/`POST_NOTIFICATIONS`/`BLUETOOTH_*`, no service |
| Assets | `app/src/main/assets/` empty (`.gitkeep`) | No models (ADR-011: fetch script + SHA-256 manifest; QAIRT 2.31 context binary still to be **generated** — hard blocker for real QNN exec) |
| ManifestReader | Parses `eval_manifest_v1.json` into `EvalItem` (matches `bench/schema.py`) | Test-wiring only — usable by BenchmarkRunner |

## 3. Target architecture

Five layers, dependency direction strictly downward (Kotlin layers → JNI boundary → C++).

```
┌─ L0 UI (Kotlin)            MainActivity / WalkieController, PeerToPeer BLE surface
├─ L1 Service (Kotlin)       TranslationService (foreground, OneDevice + PeerToPeer)
│                            ├─ WakeLock, NotificationChannel, coroutine SuperScope
├─ L2 Engine (Kotlin)        SpeechPipeline (utterance-batched coroutine chain)
│                            ├─ Recorder+Vad · DualZipformerRecognizer ×2 · LanguageSelector
│                            ├─ Denoiser (GTCRN, toggleable) · SupertonicTts · AudioSink
│                            ├─ MtEncoder (QNN, CPU fallback) · MtDecoder (ORT) · KvCache
│                            └─ ModelRegistry (ADR-011 manifest + SHA-256 + extraction)
├─ L3 JNI boundary           ~stable C ABI per native lib (see §5 for exact extern "C")
│                            · error/status codes → Kotlin sealed results
└─ L4 C++ core (NDK)         qnn_graph (real exec, ION) · ort_decoder (greedy + SPM)
                             · ion_buffer (zero-copy) · spm (source tokenisation)
```

**Pipeline shape (utterance-batched, per ADR-008 offline recognizers):**
`AudioRecord 16k mono → VAD (energy + ~500 ms timeout) → [collect utterance] →
denoiser (optional) → DualZipformer offline ASR (VI+EN in parallel) → LanguageSelector
(confidence argmax; < 0.6 ⇒ push-to-talk manual) → MT encoder (QNN; per-encoder CPU
fallback) → MT decoder (ORT greedy, ALL_OPT, KV-cache pre-alloc) → Supertonic offline
TTS (44.1 kHz) → AudioTrack.` PeerToPeer mode: after TTS input text is produced, ship
the translated *text* over BLE; the peer synthesises locally (ADR-007 Decision 2).

## 4. Kotlin file plan (`app/src/main/java/com/kavi/app/`)

Existing: `MainActivity.kt`, `qnn/QnnModelLoader.kt`, `runner/ManifestReader.kt`,
`runner/NetworkMonitor.kt`.

New/modified files (all under `com.kavi.app`):

| File | Responsibility | Key API |
| --- | --- | --- |
| `AppContainer.kt` | Manual DI: builds engines once, holds model paths (ADR-011 registry), owns the app-lifetime scope | `val container: AppContainer` via `Application` subclass |
| `KaviApplication.kt` | `Application` subclass wiring `AppContainer` (created **before** `TranslationService.onCreate`) | — |
| `service/TranslationService.kt` | Two-mode foreground service (ADR-007 D1/D6): owns `WakeLock`, notification, `CoroutineScope(SupervisorJob + Dispatchers.Default)`; loads all models in `onCreate` (persistent residency, D2); exposes `OneDevice` / `PeerToPeer` control | `onStartCommand` intents; state `@Stateflow` |
| `audio/Recorder.kt` | `AudioRecord` 16 kHz mono float, ring of read buffers; VAD-gated; ~500 ms speech timeout (end-of-utterance) (ADR-007 D5) | `fun collectUtterance(): Result<float[]>` |
| `audio/Vad.kt` | Energy-threshold VAD state machine (start/stop/holdoff/turnaround timing) — pure Kotlin, unit-testable | `fun feed(frameRms: Float): VadState` |
| `audio/AudioSink.kt` | `AudioTrack` 44.1 kHz stereo->mono correct, blocking write; underrun stats | `fun play(pcm: ShortArray)` |
| `engine/SpeechPipeline.kt` | Coroutine chain: listen→denoise→dual ASR→select→MT encoder→MT decoder→TTS→play; keeps per-utterance telemetry (stage latencies) in a `PipelineStepTimings` data class | `fun processOneUtterance(audio: FloatArray): PipelineResult` |
| `engine/DualZipformerRecognizer.kt` | Two sherpa-onnx `OfflineRecognizer` (VI 30M int8 2026-02-09 + EN small 2023-06-26), `numThreads=4`, provider `cpu`; returns per-recognizer text + mean log-prob | `fun transcribe(audio: FloatArray): Pair<Hyp, Hyp>` |
| `engine/LanguageSelector.kt` | Confidence argmax over `(ys_log_probs/ys_probs)`; confidence < 0.6 ⇒ UNAMBIGUOUS=false (→ PTT manual direction) | `fun select(vi: Hyp, en: Hyp): LanguageDecision` |
| `engine/Denoiser.kt` | GTCRN via sherpa-onnx (523 KB); toggle per utterance (ADR-007 D7; Phase-6 gate: Wiener adopted on host, GTCRN-vs-Wiener still open → Risk R1) | `fun denoise(audio: FloatArray): FloatArray` |
| `engine/MtEncoder.kt` | Opus-MT encoder: QNN path via `QnnModelLoader` (NPU); per-encoder **CPU fallback** via ORT session (ONNX 186 MB fp32 → int8 later); implements `Encoder` interface | `fun encode(tokens: IntArray): FloatArray` |
| `engine/MtDecoder.kt` | Opus-MT decoder via `ort_decoder_jni` (greedy, `ALL_OPT`, SentencePiece target), KV-cache pre-allocated (per ADR-007 D3/D10, ADR-010) | `fun decode(context: IntArray): String` |
| `engine/KvCache.kt` | Pre-allocated max-size KV cache (decoder ~70 MB / 256 tokens); ownership passed to native decoder | — |
| `engine/SupertonicTts.kt` | sherpa-onnx `OfflineTts`, `GenerationConfig(sid, speed=1.0f, numSteps=8, lang)` (ADR-009); Piper-VITS fallback hook | `fun speak(text: String): Result<ShortArray>` |
| `qnn/QnnModelLoader.kt` | **Extend** (not replace): real tensor enumeration, ION-backed zero-copy output exposure (return direct `ByteBuffer` over ION + `OrtValue` same pointer), QAIRT version-lock assert (2.31/HTP v73), latency+RSS retained | add `loadGraphFromJson(netJsonAsset)`; `runInference(...): QnnInferenceResult` (ByteBuffer) |
| `qnn/QnnTensorFactory.kt` | Parse `*_net.json` → tensor descriptors (name/rank/dims/dtype) for graph I/O | — |
| `ble/PeerLink.kt` | BLE 5.2: `BluetoothLeAdvertiser`/`BluetoothGattServer` advert; sends translated *text*; onReceive → local TTS (ADR-007 D2) | `fun sendText(t: String)`; `callback { incomingText }` |
| `ui/WalkieController.kt` | UI state holder: PTT button state, auto-VAD toggle, language indicator, stage-spinner, error surface | — |
| `util/ModelRegistry.kt` | **ADR-011**: read `SHA256SUMS` from assets, verify + extract models to `filesDir` (adb-push sideload path), load `fetch-models.sh`-provided assets; never trust `models/qnn/*` host outputs | `fun ensure(model: ModelSpec): File` |
| `runner/BenchmarkRunner.kt` (androidTest) | ADR-006 runner: single push/pull, `am instrument -w`, writes `run_results_android.json` (`latency_ns`/`peak_rss_bytes`), `NetworkMonitor` flight-mode assert | instrumentation `onStart` |
| `runner/ManifestReader.kt` / `NetworkMonitor.kt` | keep as-is (EvalItem parsing; flight-mode assertion) | — |

UI detail (L0): keep Views (appcompat + Material) for v1 — no Compose dependency to
minimize new surface; `activity_main.xml` gets PTT button, VAD-toggle, mode switch,
language badge, status text, latency readout.

## 5. C++ / JNI plan (`app/src/main/cpp/`)

### 5.1 Libraries (CMake targets → .so names)

| Target | File(s) | Purpose |
| --- | --- | --- |
| `qnn_loader_jni` (rewrite) | `qnn_loader_jni.cpp`, `qnn_graph.cpp`, `qnn_graph.h`, `ion_buffer.cpp`, `ion_buffer.h` | Real graph execution: parse provider struct properly (no hardcoded offsets), enumerate graphs/tensors by name from `_net.json`, create `Qnn_Tensor_t` (rank/dims/type), ION-backed memHandles, `QnnGraph_execute`, `QnnTensor_getData` |
| `ort_decoder_jni` (new) | `ort_decoder_jni.cpp`, `ort_decoder.cpp/.h` | ONNX Runtime decoder session: load decoder ONNX from filesDir, greedy decode loop with `ALL_OPT` + `CPUArenaAllocator` + memory-pattern (ADR-007 D10/ADR-010), SentencePiece target decode |
| `spm_jni` (new, optional) | `spm_jni.cpp` | SentencePiece encode of source text → IntArray for the MT encoder (if not folded into ort_decoder_jni) |
| `qnn_dummy` (keep for now) | — | placeholder matching current API shape, replaced by `qnn_loader_jni` rewrite |

### 5.2 JNI contract (stable ABI; error convention `jint status = 0 ok, <0 QNN/ORT error code`, plus `getLastError()` returning the message)

Existing (keep signatures, change semantics):

- `nativeInit(): jlong` — now also *parses* the provider struct via `QnnInterface_getProviders` → find backend API vtable by version (`QnnSBackend_Api_t.version`), no offset hardcoding; asserts HTP v73 (`qnn-2.31`) and aborts init with descriptive error otherwise
- `nativeLoadContext(handle, binaryPath): jboolean` — unchanged externally
- `nativeExecute(handle, input, inputName, outputName): ByteArray` — **replaced internally**: real tensor enumeration, memHandle registration, `QnnGraph_execute`
- `nativeShutdown(handle)` — plus ION buffer teardown

New:

- `nativeLoadGraph(handle, netJsonPath): jlong graphHandle` — parse `_net.json`, create input/output tensor names + shapes
- `nativeGetOutputDirectBuffer(handle, graphHandle, outputName): jobject` — returns a **direct ByteBuffer over the ION buffer** (zero-copy into ORT: `OrtSession` created with an external buffer backed by the same pointer → no memcpy, ADR-007 D4)
- *(no separate version function — version-lock lives in `nativeInit` via `QnnBackend_getApiVersion`, asserting HTP v73 / QAIRT 2.31)*
- `ortDecoderCreate(modelPath, spmPath, kvCacheBytes, maxTokens): jlong`
- `ortDecoderDecode(handle, srcTokens: IntArray): String`  (greedy, KV cache reused)
- `spmEncode(spmPath, text): IntArray` / `spmDecode(...)`
- `ionAlloc(bytes): jlong fd` / `ionMap(fd, size): jobject ByteBuffer` / `ionFree(fd)` — heap-managed dma-buf (QNN `QnnMem_register` path on Android)

### 5.3 CMakeLists.txt changes

- Multi-target: `qnn_loader_jni`, `ort_decoder_jni` (+ `spm_jni`); keep C++17; add `-O2 -ffast-math` is **not** used (fp determinism) — use `-O2` only; `ANDROID_STL=c++_shared` must **match** the sherpa-onnx prebuilt (`libsherpa-onnx-jni.so` links `libc++_shared.so`) — otherwise duplicate STL symbols at load.
- ORT: reuse sherpa's bundled `libonnxruntime.so` (one ORT copy) — **verify its version supports ALL_OPT for the decoder graph** (ADR-010 constraint; do NOT bundle a second ORT).
- Link `log`, `dl`, and (for the decoder) `${CMAKE_SOURCE_DIR}/../jniLibs/arm64-v8a/libonnxruntime.so`-adjacent includes only if headers are vendored; otherwise declare the ORT C API via function pointers like the QNN bridge (dlsym) — keeps the build header-free, consistent with the QNN approach.

### 5.4 QNN real-execution design (the M3 core)

Replaces the stub `nativeExecute` with, per inference:

1. `QnnContext_createFromBinary` (done) → `QnnContext_getAllGraphs` **by name** (parse `_net.json` for graph name) — no placeholder `graphHandle = contextHandle`.
2. `QnnTensor_createGraphTensor` for I/O with rank/dims/type from `_net.json`.
3. Input: register an ION buffer (`QnnMem_register`, alignment to 128/256 bytes, ion fd via dma-buf heap) → `QnnTensor_setMemHandle`.
4. Output: same ION path; after `QnnGraph_execute` wrap the output pointer as a Java direct `ByteBuffer` (no copy).
5. Zero-copy contract with MtDecoder: `QnnModelLoader` returns direct buffer over ION; `MtDecoder` builds the ORT `OrtValue` off the same pointer on the CPU fallback... (see §6 note — QNN and ORT cannot share one buffer trivially; the real zero-copy applies QNN-output → ORT-input *when both are on-device ION*, i.e. the encoder output feeding decoder input path — keep as design goal, fallback to a single copy until measured).

## 6. Data flow, threads, buffers

- **Threads:** one dedicated audio thread (AudioRecord callback/loop) → utterance handoff into a `Channels.UNLIMITED`-backed coroutine chain on `Dispatchers.Default`; TTS/audio playback on a dedicated `AudioTrack` thread; QNN/ORT native calls run on `Dispatchers.Default` workers (machine code, no Android binder).
- **Formats:** mic 16 kHz mono `FloatArray`; ASR consumes 16k floats; TTS emits 44.1 kHz PCM → downmix/resample in `AudioSink` (sherpa TTS models output 44.1k; AudioTrack 44.1k).
- **KV cache:** allocated once at service `onCreate` (~70 MB / 256 tokens, ADR-007 D3), passed by pointer to `ortDecoderDecode`; never freed until service teardown (D2 residency).
- **Timing budget:** E2E turnaround (EOS→SA) < 2.0 s hard gate (Phase 4); per-stage latencies recorded by `SpeechPipeline` into `run_results_android.json` (`latency_ns`), WER/BLEU scored off-device per ADR-004.

## 7. Memory budget mapping (ADR-007/008 ≈ 1.16 GB)

| Asset | Loader | Size (est.) |
| --- | --- | --- |
| Zipformer VI 30M int8 + EN small | `OfflineRecognizer` ×2 (sherpa) | ~2 × 30 MB (int8) |
| GTCRN denoiser ONNX | sherpa `OfflineRecognizer`-adjacent | ~0.5 MB |
| Opus-MT encoder | QNN ctx binary (M3) **or** ORT CPU fallback | 186 MB fp32 → int8 (~4× smaller, planned) |
| Opus-MT decoder | ORT (ort_decoder_jni) | 322 MB fp32 → int8 (~80 MB) |
| KV cache (decoder) | pre-allocated | ~70 MB |
| Supertonic TTS | sherpa OfflineTts | ~1 model (size TBD at vendoring) |
| QAIRT jniLibs (trimmed set of 7) + sherpa libs + `c++_shared` | system | ~100–150 MB RSS |
| **Total** | | ≤ 1.16 GB target; verify with `readPeakRssKb` VmPeak per stage |

ADR-011 rule: every on-device asset ships with a `SHA256SUMS` entry in `kavi-android`; models downloaded via `android/scripts/fetch-models.sh` are **verified** by `ModelRegistry` at first run; host `prototype/models/qnn/*` outputs are never vendored.

## 8. Fallbacks & error handling

- **Encoder:** QNN unavailable/fails → ORT CPU session per encoder (automatic, logged, counted for Phase-4 per-stage decision rule).
- **TTS:** Supertonic fails → Piper VITS fallback (MIT-era pinned snapshot, per ADR-009).
- **Denoiser:** toggle off per utterance (D7); if GTCRN load fails, pass-through clean audio.
- **Language:** confidence < 0.6 → PTT manual direction (UNAMBIGUOUS=false).
- **Service:** all model loads in `onCreate`; any failure → `PendingIntent`-styled notification "model load failed", service stays alive for retry; no crash (top-level try/catch + `Result`-typed engines).
- **Native errors:** all JNI funcs return status codes; Kotlin maps to `sealed class` (`QnnError`/`OrtError`/`SpError`) carrying `getLastError()` message for `Logcat` + benchmark capture.

## 9. Testing strategy

| Type | Scope | Notes |
| --- | --- | --- |
| JVM unit (`test/`) | `LanguageSelector` (argmax/confidence/<0.6 rule), `Vad` state machine, `KvCache` size math, `ModelRegistry` manifest parsing (Robolectric for `Context`) | pure-Kotlin; add `kotlinx-coroutines-test` |
| Instrumented (`androidTest/`) | Per-engine smoke (load + 1 utterance each: ASR, TTS, encoder[CTX], decoder), **`BenchmarkRunner`** (ADR-006: single push/pull, flight-mode assert, `run_results_android.json`) | needs physical Meizu 21 Note (Phase 5 shared blocker); emulator only for non-QNN engines |
| Native | `ctest` on the two wrapper targets optional (log-format assertions); main validation is instrumented | — |
| CI | `make check` (ruff) does not cover Kotlin — add ktlint or GitHub Action `android/composite` lint in a **separate follow-up** (not this branch) | — |

## 10. Sequencing (build-by-build, each ends green + committed)

| Build | Outcome | Depends on / effort |
| --- | --- | --- |
| **A. Build plumbing** | Vendor sherpa-onnx 1.13.4 jniLibs + kotlin-api AAR; trim QAIRT jniLibs 39→7 (ADR-007 D8 set incl. `libQnnGpu.so`); multi-target CMake; `ModelRegistry` + `fetch-models.sh` + `SHA256SUMS` (ADR-011); Kotlin 17 stays | ~4–6 h |
| **B. ASR + language** | `DualZipformerRecognizer`, `LanguageSelector`, unit tests; instrumented smoke (2 Zipformers on device) | A; ~6 h (+device time) |
| **C. Service + audio + pipeline (CPU-first)** | `TranslationService`, `Recorder`/`Vad`, `AudioSink`, `SupertonicTts`, `MtDecoder` (ORT greedy), `SpeechPipeline` walkie-talkie loop — **encoder CPU fallback** first, QNN later; `MainActivity` UI | B; ~10–12 h |
| **D. QNN encoder real exec** | `qnn_loader_jni` rewrite (graphs/tensors/ION), `QnnTensorFactory`, direct-Buffer zero-copy path, version-lock assert | C; **blocked until QAIRT 2.31 SDK + HTP v73 ctx binary exist**; C++ can be written + unit-tested ahead w/ mock backend ~8 h |
| **E. TTS polish + BLE** | Supertonic gen config tuning, Piper fallback wire, `PeerLink` BLE 5.2 + mode switch | C; ~6 h |
| **F. Benchmark + gates** | `BenchmarkRunner` (ADR-006), hard gates (Dual Zipformer RTF ≤ 0.05, Supertonic RTF ≤ 0.5, ALL_OPT vs NO_OPT per session), WER/BLEU off-device scoring | A–E; ~6 h runner + ~4 h on-device verify |

Totals ≈ 44–50 h of implementation + device time. Maps to android-implementation-plan
M0 (A), M1 (B), M2 (C), M3 (D), M4 (E), M5–M6 (F).

## 11. Risks & open questions

1. **QAIRT SDK absent** (2.31.0.250130 not installed; HTP v73 ctx binary doesn't exist) — **hard blocker for real QNN exec (D)**; the C++ layer can still be written against the dlsym ABI and validated with a mock; context-binary generation needs a Windows/WSL host.
2. **ORT version match** — sherpa's bundled `libonnxruntime.so` version must satisfy the decoder graph's opset + `ALL_OPT`; if not, vendor a second ORT (size/roster impact) — decide in Build A.
3. **STL policy** — `c++_shared` must match sherpa prebuilds; verify no `libc++` clash at runtime (`dlopen RTLD_LOCAL` for QNN already decided).
4. **ION zero-copy** — needs QNN `QnnMem_register` + dma-buf heaps on SD8G2; feasibility to confirm on the physical device in Build D; fallback = one copy.
5. **Sherpa-onnx version pin** — 1.13.4 prebuilt tarball (no official Maven artifact); third-party com.bihe0832 AAR exists but not canonical.
6. **Model availability for Build B/D smoke** — Zipformer assets downloadable via fetch script; encoder ctx binary is the only gating artifact.
7. **Foreground-service policy (API 34+/36)** — needs `FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_MICROPHONE` permissions and a mic-type service declaration; cold-start splash hides 2–3 s load per M4.
8. **BLE peers** — two-phone split-brain: peer list/manual pairing first, auto-discovery later.

## 12. Definition of done for this planning branch

- [x] Branch `docs/android-kotlin-cpp-implementation` off `main`
- [x] This plan committed (Conventional Commits `docs:`), no code changes
- [ ] Review against ADR-007…011 + PR #95 (owner: next planning turn or reviewer)
- [ ] Gate: do **not** start Build A until plan approved here
