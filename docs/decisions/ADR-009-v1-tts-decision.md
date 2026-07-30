# ADR-009: v1 Android TTS Decision

**Status:** Proposed
**Date:** 2026-07-30
**Deciders:** Kavi team
**Relates to:** ADR-007 (parent architecture — TTS slot reserved in pipeline), ADR-008 (Dual Zipformer ASR — TTS remains TBD in both ADRs), ADR-004 (tech-stack deferred decisions)

---

## Context

ADR-007 and ADR-008 reserve a TTS slot in the inference pipeline but leave the model selection open. This ADR evaluates TTS candidates for Kavi v1, covering both Vietnamese and English output.

### Requirements

| Requirement | Detail |
| ----------- | ------ |
| **Languages** | Vietnamese (primary) + English (translated output). Must cover both directions. |
| **Runtime** | On-device, CPU via ONNX Runtime (NPU not required — TTS decoder graphs are autoregressive and map poorly to HTP fixed-graph paradigm, similar to the ASR/MT decoder pattern in ADR-005/008) |
| **Latency** | RTF < 1.0 (real-time); RTF < 0.5 preferred for snappy UX |
| **License** | Must permit commercial use (MIT, Apache-2.0, or CC BY 4.0 with attribution) |
| **Android** | Must integrate via sherpa-onnx JNI with the existing Kotlin `OfflineTts` API |
| **Memory** | Must fit within the 4 GB peak budget established in ADR-007 Decision 5, shared with ASR (~20 MB), MT (~100 MB), denoiser (~50 MB), and runtime overhead |
| **Multi-speaker** | At minimum one male and one female voice for each language (optional but strongly preferred) |
| **Prosody control** | Nice-to-have, not a requirement |

### Research scope

The full sherpa-onnx TTS model catalog was surveyed. Models were screened for:

1. Vietnamese + English language coverage
2. Permissive license for commercial use
3. On-device inference feasibility (model size, RTF)
4. Android integration maturity (pre-built APK availability, Kotlin API support)

---

## Candidate evaluation

### Candidate 1: Single SupertonicTTS 3 (Recommended)

**Single model covers both Vietnamese and English** — a unified TTS pipeline with no model swapping, no dual configuration, and shared audio output routing.

| Attribute | Detail |
| --------- | ------ |
| **License** | **MIT** (model weights + code, Supertone Inc.) |
| **Languages** | **31 languages** — `vi` + `en` + 29 others in a single model |
| **Parameters** | 99M (open-weight ONNX) |
| **Compressed** | **122.8 MB** (tar.bz2) |
| **On-disk extracted** | ~280–320 MB (4 ONNX sub-models + vocoder + voice.bin + config) |
| **Sample rate** | **44.1 kHz** 16-bit WAV — studio-grade, no upsampling needed |
| **Voices** | **10 built-in voice styles**: M1–M5 (male), F1–F5 (female), per language |
| **RTF (M4 Pro CPU)** | **0.012–0.023** — significantly faster than real-time |
| **RTF (RTX 4090)** | 0.001–0.005 (GPU optional, not required) |
| **Quality control** | `total_steps` parameter (2–12, default 8) — low steps = fast, high steps = higher fidelity |
| **Speed control** | `speed` parameter (0.7–2.0) — global, no inline prosody |
| **Expression tags** | 10 undocumented inline tags (`<laugh>`, `<breath>`, `<sigh>`, etc.) in the native Python SDK — **not confirmed available via sherpa-onnx** |
| **Language selection** | `--lang vi` or `--lang en` via `GenerationConfig.extra={"lang": "vi"}` — clean, single-config |
| **Android APK** | ✅ **Pre-built APKs exist** for both Vietnamese and English TTS Engine |
| **Android API** | `OfflineTts` Kotlin class via sherpa-onnx JNI — same integration pattern as ADR-008's Zipformer ASR |
| **Repository status** | ⚠️ **Repository will be archived.** Supertone Inc. announced no further development or official support for open-source models after August 2026. Voice Builder will be inaccessible after August 31, 2026. |

**Pros:**

- Single model for all languages — no hot-swapping, no dual-loading
- Excellent RTF (0.012) — fast enough for real-time conversation without GPU
- 44.1 kHz output — production-ready audio quality
- 10 built-in voices across gender spectrum
- Pre-built Android APK for immediate device testing
- MIT license — no attribution boilerplate, no revenue cap
- Voice cloning via Voice Builder JSON export (available until August 31, 2026)

**Cons / risks:**

- **~280–320 MB on-disk** — significant storage budget. The 4 ONNX sub-models (duration_predictor, text_encoder, vector_estimator, vocoder) are loaded together.
- **Repository archival** — no upstream bug fixes, security patches, or new voices after 2026-08. The model itself remains MIT-licensed and downloadable, but the ecosystem freezes.
- **Voice Builder shutdown** — after August 31, 2026, no new custom voice profiles can be created. Existing profiles remain usable as JSON exports.
- **100% CPU inference for 44.1 kHz vocoder** — the vocoder ONNX model is the heaviest component; on less capable devices (e.g., older Snapdragon), RTF may degrade.
- **Expression tags unconfirmed in sherpa-onnx** — the tag support lives in the native supertonic-py SDK, and may not pass through sherpa-onnx's ONNX runtime wrapper.
- **No SSML or fine-grained prosody** — no per-word emphasis, volume contours, or whisper modes. The `speed` parameter is a global multiplier only.
- **Vietnamese CER 4.49%** on MLS benchmark — below VoxCPM2 (1.48%) and OmniVoice (0.79%) among open models, though still competitive.

---

### Candidate 2: Dual Piper VITS (Alternative)

**Two separate Piper VITS models** — one Vietnamese voice, one English voice — loaded as independent TTS sessions. Language direction selects which model to invoke.

| Attribute | Detail |
| --------- | ------ |
| **License** | **CC BY 4.0** (Vietnamese VAIS1000 voice) + **MIT** (Piper framework + English voices) |
| **Vietnamese voices** | `vits-piper-vi_VN-vais1000-medium-int8` — ~20.6 MB, CC BY 4.0. Alternative: `25hours_single-low-int8` (~20 MB), `vivos-x_low-int8` (~14 MB) |
| **English voices** | `vits-piper-en_US-amy-low-int8` (~20 MB, MIT, female), `en_US-lessac-medium-int8` (~20 MB, MIT, male), plus ~20+ others |
| **Total model size** | **~40–50 MB** (two int8 models) — significantly smaller than Supertonic |
| **Sample rate** | 22.05 kHz (vs Supertonic's 44.1 kHz) |
| **RTF (RPi4, 4 threads)** | 0.35–0.81 — fast enough for real-time on modest hardware |
| **Dependency** | `espeak-ng-data` (~4 MB) shared between voices |
| **Android APK** | ✅ Pre-built APK exists for `vits-piper-vi_VN-vais1000-medium` |
| **Android API** | `OfflineTts` Kotlin class — two `OfflineTtsConfig` instances, one per language |
| **Prosody** | ❌ No SSML, no expression tags, no prosody control |

**Pros:**

- **Much smaller footprint** — ~50 MB total vs ~300 MB for Supertonic; fits more comfortably in the 4 GB budget alongside ASR + MT + denoiser
- **Proven on-device** — Piper VITS models have been deployed on Raspberry Pi 4 with RTF < 1.0 at 4 threads
- **Both voices per language** — choose from 20+ English voices and 3+ Vietnamese voices, mix male/female
- **CC BY 4.0 is commercial-friendly** — requires attribution but has no usage cap, no revenue limit
- **espeak-ng-data is shared** — single ~4 MB dependency reused across all Piper voices, not duplicated
- **Repository active** — Piper is actively maintained, no archival risk
- **Shipped as Android TTS Engine** — Google's own ASR uses Piper; mature integration pattern

**Cons / risks:**

- **Dual model management** — two separate `OfflineTtsConfig` instances, two model directories, two ONNX sessions. Language direction determines which TTS engine is invoked, adding a small branching overhead.
- **22.05 kHz vs 44.1 kHz** — perceptibly lower quality. May require upsampling in the audio output path if the rest of the pipeline (or Bluetooth headset) expects higher sample rates.
- **No voice cloning** — Piper VITS uses fixed trained voices; custom voice cloning is not available through the sherpa-onnx integration.
- **eSpeak-ng phonemisation** — Piper relies on eSpeak-ng for text-to-phoneme conversion. Edge-case pronunciation errors (proper nouns, loanwords) are harder to correct than in Supertonic's learned grapheme-to-phoneme approach.
- **No prosody or expression** — Piper produces flat, neutral prosody from punctuation alone. No expression tags, no emphasis, no speed variation within an utterance.
- **CC BY 4.0 attribution requirement** — must credit the voice dataset source in the app's about/licenses screen.

---

### Ruled-out candidates

| Model | Why ruled out |
| ----- | ------------- |
| **Kokoro** (v1.0, v1.1) | No Vietnamese support — only English, Chinese, Japanese, Korean. Int8 at 126–140 MB but does not cover the primary requirement. |
| **MeloTTS** | RTF 6.7 on RPi4 single-thread — too slow for real-time without heavy multi-threading. zh_en bilingual only, no Vietnamese. |
| **KittenTTS** | English-only models (nano/mini). No Vietnamese. Would require pairing with a separate VI TTS. |
| **ZipVoice** | Zero-shot voice cloning model requiring both reference audio and exact reference text transcript. CN/EN bilingual only. |
| **PocketTTS** | Zero-shot voice cloning requiring reference audio only, but CN/EN only. No Vietnamese. |
| **Matcha-TTS** | English and Chinese only. Faster than VITS (RTF 0.39–0.94) but no Vietnamese support. |
| **MMS-TTS** | 1,100+ languages including Vietnamese, but character-level output with lower naturalness than neural models tested here. Not available as pre-built sherpa-onnx asset. |

---

## Recommended Decision: SupertonicTTS 3 for v1 Android

Kavi v1 TTS should use **SupertonicTTS 3** as a single-model, single-config TTS engine via sherpa-onnx, covering both Vietnamese and English output with a unified ONNX session.

### Rationale

1. **Single-model simplicity** — `--lang vi` / `--lang en` switching on the same ONNX session avoids dual-configuration overhead, dual memory reservation, and branch logic in the pipeline. This aligns with ADR-008's architectural preference for merged simplicity.

2. **Latency headroom** — RTF 0.012 on M4 Pro CPU is dramatically faster than real-time. Even accounting for less capable mobile SoCs (SD8G2), the headroom is substantial. The 44.1 kHz vocoder is the heaviest component but benefits from ONNX Runtime CPU optimisations (ALL_OPT, arena allocator) already established in ADR-007 Decision 10.

3. **Output quality** — 44.1 kHz native output matches (or exceeds) typical Bluetooth A2DP sink rates. No upsampling pipeline needed. The built-in numerical text handling (currency, dates, phone numbers) is best-in-class among open TTS models.

4. **10 built-in voices** — five male + five female per language, covering the multi-speaker requirement without any voice cloning or additional model downloads.

5. **Android readiness** — pre-built APKs exist. The `OfflineTts` Kotlin API mirrors the `OfflineRecognizer` integration from ADR-008, so the team builds expertise with one sherpa-onnx API surface.

6. **MIT license** — no attribution boilerplate, no revenue cap, no concerns about the $1M threshold that affected Moonshine Tiny in ADR-008's evaluation.

### Key mitigations for the archival risk

| Risk | Mitigation |
| ---- | ---------- |
| Repository archived after 2026-08 | The model is MIT-licensed and frozen, not removed. Pi releases from sherpa-onnx will continue to bundle the ONNX assets. No online dependency. |
| No upstream bug fixes | The model is a static ONNX graph — no runtime patches needed. Sherpa-onnx itself maintains the inference engine (libsherpa-onnx-jni.so), which is separate and actively developed. |
| Voice Builder shutdown after 2026-08-31 | Extract and save any desired custom voice JSON profiles before the shutdown date. Pre-built voices (M1–M5, F1–F5) remain available indefinitely. |

### Integration architecture

```
TranslationService pipeline (from ADR-007 Decision 1)
    ↓ (translated text from Opus-MT decoder)
┌────────────────────────────────────────────────────────────┐
│ TTS: SupertonicTTS 3 (single ONNX session via sherpa-onnx) │
│                                                             │
│  OfflineTtsConfig:                                          │
│    model = "sherpa-onnx-supertonic-3-tts-int8"              │
│    voice = "M1" / "F1" / ... (10 built-in)                  │
│    lang  = "vi" or "en"  (switched per utterance)           │
│    numThreads = 4                                            │
│    provider = "cpu"                                          │
│                                                              │
│  OfflineTts.createStream() → OfflineTtsStream                │
│  stream.addText(text, sid, speed)                            │
│  tts.synthesize(stream) → float[] audio_samples              │
└────────────────────────────────────────────────────────────┘
    ↓ (44.1 kHz PCM float)
AudioTrack → playback / Bluetooth A2DP
```

Example Kotlin integration:

```kotlin
// Single config, both languages (Sherpa-onnx Java API)
val ttsConfig = OfflineTtsConfig(
    model = "$modelDir/sherpa-onnx-supertonic-3-tts-int8",
    voice = "M1",          // or F1–F5, M2–M5
    numThreads = 4,
    provider = "cpu"
)
val tts = OfflineTts(ttsConfig)

// For each utterance, select language based on ASR language detection (ADR-008):
fun synthesize(text: String, direction: TranslationDirection): FloatArray {
    val lang = when (direction) {
        VI_TO_EN -> "vi"
        EN_TO_VI -> "en"
    }
    val stream = tts.createStream()
    stream.addText(text, sid = 0, speed = 1.0)
    return tts.synthesize(stream)
}
```

---

## Open items

| Item | Description | Owner | Phase |
| ---- | ----------- | ----- | ----- |
| **Android RTF benchmark** | Measure SupertonicTTS 3 RTF on SD8G2 reference device with 4 CPU threads. The M4 Pro benchmarks (0.012) are not representative of mobile Snapdragon performance. | Benchmarking | Phase 4 |
| **On-disk size measurement** | Measure exact extracted model size with the sherpa-onnx distribution (the native model is ~400 MB; the sherpa-onnx ONNX int8 bundle may differ). Confirm storage budget. | Integration | Phase 4 |
| **Voice selection test** | Listen to all 10 built-in voices (M1–M5, F1–F5) in both Vietnamese and English. Select a default pair (e.g., F3 for VI, M2 for EN) or a single voice that works well for both. | UX / PM | Phase 4 |
| **Language switching latency** | Measure overhead of switching `lang` between utterances on the same session — does it reset any internal state, or is it purely a generation-time parameter? | Integration | Phase 4 |
| **Pre-built APK evaluation** | Download and test the pre-built Android TTS Engine APK for Supertonic 3 VI and EN on the SD8G2 device. Validate audio quality and latency before custom build. | Integration | Phase 3 (ongoing) |
| **Expression tag investigation** | Investigate whether sherpa-onnx's Supertonic wrapper supports the 10 inline expression tags (`<laugh>`, `<breath>`, etc.). If yes, document and evaluate for Kavi's UX. | Research | Phase 4 |
| **Piper fallback verification** | Benchmark Piper VITS dual-model path (VAIS1000 + Amy/Lessac) as a fallback option if Supertonic is too slow on SD8G2 or the archival risk is deemed unacceptable. | Benchmarking | Phase 4 |

---

## Consequences

### Positive

- **Single model, single config, zero branching** — the TTS pipeline is a straight line. Load one ONNX session, switch `lang` per utterance. No dual-manifest management, no model-swap logic, no concurrency concerns with two TTS engines.
- **44.1 kHz native output** — matches Bluetooth A2DP high-quality profile. No resampling or quality loss in the audio output path.
- **10 voices built-in** — male and female options for both VI and EN without additional downloads. Users can toggle or the system can auto-select based on ASR-detected speaker gender.
- **MIT license** — cleanest possible commercial terms. No attribution screen needed, no usage tracking.
- **Pre-built APK available now** — the team can evaluate TTS quality on device today, without building custom JNI libs.
- **Repository archival is not a service shutdown** — the model binaries remain downloadable and MIT-licensed indefinitely. The open-source ONNX assets are frozen, not removed. Sherpa-onnx (the integration layer) continues active development independently.

### Negative / risk

- **~280–320 MB on-disk** is non-trivial. Combined with Zipformer ASR (~20 MB), Opus-MT (~100 MB), GTCRN denoiser (~50 MB), and runtime overhead, the total model storage may push past 500 MB. Mitigation: Android APK expansion file (OBB) or on-device download on first run.
- **Repository archival (August 2026)** means the Supertonic open-source project stops evolving. No new languages, voices, or optimisations. Mitigation: the model is static ONNX — it does not need upstream updates to function.
- **44.1 kHz vocoder on mobile CPU** may be more expensive than the M4 Pro benchmarks suggest. The ONNX vocoder graph includes a mel-spectrogram decoder and neural vocoder (HiFi-GAN or similar). If RTF exceeds 0.5 on SD8G2, fall back to int8 Piper VITS (22.05 kHz, ~5× less compute per sample).
- **No fine-grained prosody control** — Kavi v1 cannot whisper, shout, or add emphasis inline. If the UX requires tonal variation (e.g., "ERROR: connection lost" read with urgency), a post-processing volume envelope or a separate "alert" voice would be needed.
- **Voice Builder shutdown (2026-08-31)** — the window for creating custom cloned voices closes. If the team wants a unique Kavi-brand voice, they must act before this date. After shutdown, only pre-built voices remain.
- **CC BY 4.0 dual-Piper path is available but lower quality** — if Supertonic proves unsuitable on target hardware, the fallback is two separate Piper models at 22.05 kHz, which is a significant quality regression. Consider evaluating Piper in parallel during Phase 4.

---

## References

- **Supertonic 3 Python SDK docs:** <https://supertone-inc.github.io/supertonic-py/>
- **Supertonic 3 GitHub (to be archived):** <https://github.com/supertone-inc/supertonic>
- **Supertonic 3 ONNX models (HuggingFace):** <https://huggingface.co/Supertone/supertonic-3>
- **sherpa-onnx TTS models index:** <https://k2-fsa.github.io/sherpa/onnx/tts/index.html>
- **sherpa-onnx Supertonic TTS page:** <https://k2-fsa.github.io/sherpa/onnx/tts/supertonic.html>
- **sherpa-onnx pre-built APK catalog:** <https://github.com/k2-fsa/sherpa-onnx/releases/tag/android-models>
- **sherpa-onnx Kotlin TTS API examples:** <https://github.com/k2-fsa/sherpa-onnx/tree/master/kotlin-api-examples>
- **Piper VITS voices (sherpa-onnx):** <https://k2-fsa.github.io/sherpa/onnx/tts/piper.html>
- **Piper GitHub (active):** <https://github.com/rhasspy/piper>
- **VAIS1000 dataset license (CC BY 4.0):** <https://zenodo.org/records/14034235>
- **ADR-007:** Production Inference Architecture & Service Layer (TTS slot reserved)
- **ADR-008:** v1 Android ASR Decision — Dual Zipformer (TTS remains TBD in pipeline)
- **ADR-004:** Speech-to-Speech Architecture / Tech-Stack (deferred decisions)
