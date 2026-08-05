# Android Implementation Plan (ADR-007 → ADR-010)

> **Status:** Proposed — not yet executed
> **Date:** 2026-08-03
> **Sources:** ADR-007 (production inference architecture), ADR-008 (Dual Zipformer ASR),
> ADR-009 (phased TTS: Supertonic → VieNeu-TTS), ADR-010 (`ALL_OPT` analysis),
> ADR-006 (Android runner architecture), `.pi/PLAN.md` (Phases 4–7)
> **Scope:** Everything needed to take `android/` from a buildable skeleton to the
> production two-mode speech-to-speech app.

---

## 1. Goal

Turn the current `android/` submodule (bare `MainActivity` + stubbed QNN JNI bridge +
39 bundled `libQnn*.so`) into the ADR-007 `TranslationService` app: a fully offline,
on-device, two-mode (OneDevice walkie-talkie / PeerToPeer BLE) Vietnamese↔English
speech-to-speech translator meeting the 2.0 s turnaround budget on a Snapdragon 8 Gen 2.

## 2. Current state vs. target

| ADR decision | Required | Current `android/` | Gap |
| --- | --- | --- | --- |
| D1: Two-mode `TranslationService` foreground service | Full pipeline service | None (bare `MainActivity`) | **Build from scratch** |
| D2: Persistent model residency | Load all models in `onCreate`, never release | — | **Build** |
| D3 (modified): MT KV-cache pre-allocation (256 tok) | Opus-MT decoder | — | **Build** |
| D4: NPU→CPU zero-copy via ION | Real QNN graph execution | `qnn_loader_jni.cpp` is a **stub** (`nativeExecute` copies input→output; no graph enumeration, hardcoded provider offsets) | **Complete JNI** |
| D5 (revised): Memory budget ~1.16 GB | Model set sized | — | Verify on-device |
| D7: Tiered denoising (ADSP → GTCRN) | Denoiser stage | Phase-6 gate adopted **Wiener**, not GTCRN — needs resolution (see Risk R1) | **Decision + port** |
| D8: jniLibs roster + version lock | Minimal QNN roster | 39 `.so` incl. V68/V69/V75/V79, GPU/DSP/HTA/LPAI/GenAi extras | **Trim roster** |
| D9: Structured concurrency (coroutines) | Suspend-stage pipeline | — | **Build** |
| D10 / ADR-010: `ALL_OPT` + arena + mem-pattern | All ORT sessions | — | Verify sherpa-onnx; benchmark per-session |
| D11: Energy VAD + speech timeout | `Recorder` | — | **Build** |
| ADR-008: Dual Zipformer ASR | sherpa-onnx, 2× `OfflineRecognizer`, confidence-based lang-ID | No sherpa-onnx libs; `assets/` empty | **Vendor libs + models** |
| ADR-009: Supertonic Phase-1 TTS | `OfflineTts` + `GenerationConfig` lang switch | — | **Vendor models + integrate** |
| ADR-006: Instrumented benchmark runner | `androidTest/` batch runner | `ManifestReader`/`NetworkMonitor` exist; no test code | **Build** |

### Already available on disk

- **Opus-MT**: ONNX export + QNN encoder artifacts at
  `models/qnn/opus-mt-vi-en/` (`encoder/opus_mt_vi_en_encoder.bin` ~74 MB,
  `_net.json`). **Verify QAIRT 2.31 / HTP v73 provenance before vendor.**
- **Correction (2026-08-05):** `opus_mt_vi_en_encoder.bin` is a **tar of raw
  `.raw` weights** (converter intermediate), **not** the on-device HTP v73
  context binary — that binary does **not** exist yet and is the M3
  deliverable (`qnn-context-binary-generator`, Windows host, `phase-4-qnn-plan`
  §8). All `models/qnn/*` artifacts are **gitignored & uncommitted**
  (`.gitignore` `models/qnn/*`) — provenance is unverifiable locally.
- **Denoiser**: Phase-6 gate adopted Wiener (`noisereduce`, `prop_decrease=0.5`) —
  `docs/reference/denoising-gate-results.md`.
- **Superseded, do NOT vendor**: Whisper QNN artifacts (`models/qnn/whisper-small/`,
  774 MB decoder) — replaced by Dual Zipformer CPU (ADR-008); Piper QNN artifacts
  (`models/qnn/piper-en/`) — replaced by Supertonic Phase 1 (ADR-009).

---

## 3. Milestones

### Milestone 0 — Foundation & asset strategy

1. **Asset delivery (~450–500 MB models)**
   - Zipformer VI int8 (~32 MB) + EN Small int8 (~28 MB) — ADR-008
   - Opus-MT decoder ONNX (~322 MB fp32 → **int8 quantise**, Risk R3)
   - SupertonicTTS 3 sherpa-onnx bundle (~280–320 MB) — ADR-009
   - Total exceeds APK practical limits → **Android App Bundle + Play Asset
     Delivery (install-time)**, plus an `adb push` → `filesDir` path for contest /
     benchmark use (offline invariant preserved: **no runtime network**).
2. **Vendor sherpa-onnx 1.13.4** (pin version)
   - Download `sherpa-onnx-v1.13.4-android.tar.bz2` from the releases page.
   - Copy `libsherpa-onnx-jni.so` + `libonnxruntime.so` (arm64-v8a) into
     `jniLibs/arm64-v8a/`.
   - Copy the Kotlin API (`kotlin-api/`) into
     `app/src/main/java/com/k2fsa/...`.
   - No official Maven Central artifact exists — the AAR/jniLibs path is canonical
     (verified 2026-08-03).
3. **Trim QNN roster to ADR-007 D8**
   - Keep: `libQnnHtp.so`, `libQnnHtpV73Stub.so`, `libQnnHtpV73CalculatorStub.so`,
     `libQnnHtpPrepare.so`, `libQnnSystem.so`, `libQnnCpu.so`, `libqnn_loader_jni.so`.
   - ADR-007 D8 also lists `libQnnGpu.so` (future-proofing; v1 fallback chain is NPU→CPU only) — keep it to stay ADR-faithful.
   - Delete ~25 extras: V68/V69/V75/V79 stubs, GPU, DSP, HTA, LPAI, GenAi,
     TFLite delegate, profiling readers. Keeps HTP v73 firmware matched to the
     QAIRT 2.31 pin; shrinks APK.
4. **Model procurement script** (`android/scripts/fetch-models.sh`)
   - Download → SHA-256 verify → strip test artifacts (per ADR-008 deployment
     section) → place under `app/src/main/assets/` (or OBB manifest).
5. **Provenance & commit rule (ADR-011)**
   - All on-device artifacts (HTP v73 context binary, model `.so`, Opus-MT
     decoder ONNX, Zipformer/Supertonic assets) are committed **inside
     `kavi-android` `app/src/main/assets/`** with a SHA-256 manifest.
     `prototype/models/qnn/*` is gitignored — host outputs are regenerable
     only and must never be treated as deliverables.

### Milestone 1 — sherpa-onnx engines (ASR + TTS)

1. **Dual Zipformer** (`asr/DualZipformerRecognizer.kt`)
   - VI: `sherpa-onnx-zipformer-vi-30M-int8-2026-02-09`
   - EN: `csukuangfj/sherpa-onnx-zipformer-small-en-2023-06-26`
   - Two `OfflineRecognizer` instances, `numThreads = 4`, provider `"cpu"`.
   - `suspend fun transcribe(pcm: FloatArray): (text, confidence)`; confidence
     from native `ys_log_probs`.
2. **Language selection** (`asr/LanguageSelector.kt`)
   - `argmax(mean_confidence_vi, mean_confidence_en)`.
   - `max confidence < 0.6` → undetermined → push-to-talk manual direction
     (ADR-008 fallback).
3. **Supertonic TTS** (`tts/SupertonicTts.kt`)
   - Single `OfflineTts` with supertonic model config (duration_predictor,
     text_encoder, vector_estimator, vocoder, `tts.json`, `unicode_indexer.bin`,
     `voice.bin`).
   - Per-utterance `GenerationConfig(sid, speed = 1.0f, numSteps = 8,
     extra = {"lang": "vi" | "en"})` — lang from ASR lang-ID (ADR-009).
4. **`ALL_OPT` verification (ADR-010)**
   - sherpa-onnx manages ORT sessions internally — confirm its `SessionOptions`
     use `ORT_ENABLE_ALL` (default for CPU) + arena + mem-pattern.
   - Record per-session optimised-vs-`NO_OPT` latency as a Phase-4 validation item.

### Milestone 2 — TranslationService + pipeline

1. **`service/TranslationService.kt`** (D1, D2)
   - `startForegroundService`, type `microphone`, `PowerManager.WakeLock`.
   - Load **everything** in `onCreate`: 2 recognizers, Opus-MT encoder (QNN),
     Opus-MT decoder (ORT), TTS, denoiser; pre-allocate MT KV cache (D3);
     never release.
2. **`audio/Recorder.kt`** (D11)
   - `AudioRecord` 16 kHz mono PCM float, circular buffer, energy VAD +
     ~500 ms speech timeout.
3. **`audio/AudioPlayer.kt`**
   - `AudioTrack` write (44.1 kHz from Supertonic; resample if A2DP requires).
4. **Pipeline** (`service/SpeechPipeline.kt`, D9 + ADR-008 concurrency model)

   ```kotlin
   val cleaned = denoiser.apply(audio)                       // toggleable (D7)
   val (vi, en) = coroutineScope {
       async { viTranscribe(cleaned) } to async { enTranscribe(cleaned) }
   }
   val (text, lang) = selectLanguage(vi, en)
   val mtEncoded = mtEncoder.run(text, lang)                 // QNN w/ CPU fallback
   val translated = mtDecoder.decode(mtEncoded)              // ORT greedy, ALL_OPT
   val audio = tts.synthesize(translated, lang)
   ```

   - Per-encoder fallback (D9): QNN failure → ONNX CPU encoder; degrade, don't crash.
5. **Denoiser stage**
   - Decide GTCRN (sherpa-onnx `OfflineDenoise` — fits the JNI pipeline) vs.
     porting the Phase-6 Wiener (Risk R1).
   - Toggleable per-utterance (D7); pre-allocated buffers.

### Milestone 3 — Real QNN NPU path (Opus-MT encoder)

1. **Complete `qnn_loader_jni.cpp`**
   - Replace the stub: `QnnGraph_retrieve` by name from the context binary;
     `QnnTensor_createGraphTensor` with correct rank/dims/types (from
     `_net.json`); bind ION-backed input/output buffers (tensor `memHandle`);
     call `QnnGraph_execute`; read output via `QnnTensor_getData`.
   - Retire the hardcoded provider-offset hack (parse the provider struct).
2. **ION zero-copy (D4)**
   - `QnnModelLoader` returns a direct `ByteBuffer` over ION memory; ORT
     `OrtValue` created from the same pointer for the decoder input — no memcpy.
3. **Wire CPU fallback**
   - Opus-MT encoder ONNX (186 MB) via ORT on CPU when QNN init/execute throws
     (D9 pattern).
4. **Version-lock check (D8)**
   - Verify the **HTP v73 context binary** (not the weight-tar) was produced
     with QAIRT 2.31.0.250130 for HTP v73 — mismatch = silent inference
     failure. Re-convert via `bench/qnn/convert_to_qnn.sh` if needed.

### Milestone 4 — UI + modes (D1)

1. **Mode A — OneDevice (WalkieTalkie)**
   - PTT button or auto-VAD segmentation; single record/play; conversation UI
     (transcript + translation).
2. **Mode B — PeerToPeer**
   - BLE 5.2+ peripheral/central pairing (`BluetoothGatt` / `BluetoothLeAdvertiser`);
     send **translated text** to peer; peer synthesises locally.
3. **Cold-start UX**
   - Splash / progress bar for the 2–3 s load (D2 trade-off mitigation).

### Milestone 5 — Instrumented benchmark runner (ADR-006)

1. **`androidTest/.../BenchmarkRunner.kt`**
   - Single push / single pull: read `eval_manifest_v1.json` (existing
     `ManifestReader`), assert zero network (`NetworkMonitor`), run each item
     through the real pipeline, write `run_results_android.json` with internal
     `latency_ns` / `peak_rss_bytes`, per-stage RTF and turnaround.
2. **Host scripts**
   - `adb push` assets+manifest → `am instrument -w` → `adb pull` →
     `uv run python -m bench.score --from-android`.
3. **Hard gates**
   - Dual Zipformer RTF on Meizu 21 Note (SD8G2) **≤ 0.05** (ADR-008 go/no-go for
     CPU-only ASR).
   - Supertonic RTF **≤ 0.5** (else Piper VITS fallback, ADR-009).
   - Per-session `ALL_OPT` vs `NO_OPT` measurement (ADR-010).

### Milestone 6 — Packaging & release

- `AndroidManifest.xml`: `RECORD_AUDIO`, `FOREGROUND_SERVICE`,
  `FOREGROUND_SERVICE_MICROPHONE`, `POST_NOTIFICATIONS`, `WAKE_LOCK`,
  `BLUETOOTH_CONNECT` / `ADVERTISE` / `SCAN` (BLE), optional
  `USE_FULL_SCREEN_INTENT`.
- Proguard: keep JNI entry points (`QnnModelLoader`, `sherpa-onnx-jni`).
- OBB / Play Asset Delivery config + reproducible `fetch-models.sh`.
- README update: build (incl. sherpa-onnx vendoring), model fetch, bench protocol.

---

## 4. Risks / decision points

| # | Risk | Detail | Mitigation / recommendation |
| --- | --- | --- | --- |
| R1 | **Denoiser conflict** | ADR-007 says GTCRN (sherpa-onnx `OfflineDenoise`); Phase-6 gate adopted Python Wiener (`prop_decrease=0.5`) | Quick on-device GTCRN-vs-Wiener WER check, then pick; keep the D7 toggle |
| R2 | **Model size** | ~800 MB total ⇒ PAD/OBB required | Install-time PAD plus `adb push` → `filesDir` sideload path for contest |
| R3 | **Opus-MT decoder is 322 MB fp32** | CPU decoder too large | int8-quantise for the CPU decoder before shipping (fits `ALL_OPT` + arena; ~4× smaller) |
| R4 | **Native lib clash** | sherpa-onnx + our loader both in-process | Ensure no `libQnnHtp` symbol clash; keep QNN `dlopen` local (RTLD_LOCAL) |
| R5 | **Confidence-based lang-ID unvalidated** | ADR-008 open item on real code-switched audio | Held-out code-switched set before trusting PTT fallback |

---

## 5. Execution order

```
M0 (roster trim + sherpa-onnx vendor + assets) ──┬──→ M1 (ASR + TTS engines, standalone-testable)
                                                 └──→ M3 (QNN NPU path)         [parallel after M0]
M1 ──→ M2 (TranslationService + pipeline) ──→ M4 (UI + modes)
M5 (bench runner + hard gates) ──→ M6 (packaging + release)
```

M1 and M3 can proceed in parallel after M0. M5's hard gates must pass before
ADR-004 closure (per `.pi/PLAN.md` §8 acceptance criteria).

---

## 6. Related documents

- ADR-007 — Production Inference Architecture & Service Layer (parent; D6 superseded)
- ADR-008 — v1 Android ASR Decision: Dual Zipformer (revises D3/D5/D6)
- ADR-009 — v1 Android TTS Decision (Supertonic Phase 1 → VieNeu-TTS Phase 2)
- ADR-010 — `ALL_OPT` Decoder Optimisation (confirms D10)
- ADR-006 — Android Runner Architecture (benchmark runner design)
- `.pi/PLAN.md` — Phases 4–7 task breakdown (QNN conversion, RTranslator, COMET/MOS)
- `docs/reference/phase-4-qnn-plan.md` — executable QNN conversion spec
- `docs/reference/denoising-gate-results.md` — Phase-6 Wiener adoption
