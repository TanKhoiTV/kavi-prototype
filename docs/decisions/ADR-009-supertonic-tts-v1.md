# ADR-009: v1 Android TTS — SupertonicTTS 3 (Phase 1)

## Status

Proposed

## Date

2026-07-30

## Deciders

Kavi team

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
| **Memory** | Must fit within the 4 GB peak budget established in ADR-007 Decision 5, shared with ASR (~60 MB dual Zipformer int8, per ADR-008 deployment section), MT (~500 MB encoder+decoder+KV cache, per ADR-007 Decision 5), denoiser (~50 MB), and runtime overhead |
| **Multi-speaker** | At minimum one male and one female voice for each language (optional but strongly preferred) |
| **Prosody control** | Nice-to-have, not a requirement |

### Research scope

The full sherpa-onnx TTS model catalog was surveyed. Models were screened for:

1. Vietnamese + English language coverage
2. Permissive license for commercial use
3. On-device inference feasibility (model size, RTF)
4. Android integration maturity (pre-built APK availability, Kotlin API support)

---

> **Split note (2026-09-25):** this record was titled *"v1 Android TTS Decision"*
> and recorded the whole **phased** TTS strategy in one file. Phase 2 (migration to
> VieNeu-TTS v3 Turbo) is now **[ADR-028](ADR-028-vieneu-tts-migration.md)**. This
> record holds the Phase-1 pick; the candidate evaluation below is retained here in
> full because it is the alternatives analysis for that pick.

## Alternatives considered

### Candidate 1: Single SupertonicTTS 3 (Recommended)

**Single model covers both Vietnamese and English** — a unified TTS pipeline with no model swapping, no dual configuration, and shared audio output routing.

| Attribute | Detail |
| --------- | ------ |
| **License** | **BigScience OpenRAIL-M** (model weights) + **MIT** (code). OpenRAIL-M permits commercial use but includes use-based restrictions — see [LICENSE](https://huggingface.co/Supertone/supertonic-3/blob/main/LICENSE). |
| **Languages** | **31 languages** — `vi` + `en` + 29 others in a single model |
| **Parameters** | 99M (open-weight ONNX) |
| **Compressed download** | **122.8 MB** (tar.bz2 from sherpa-onnx releases) |
| **On-disk extracted (sherpa-onnx int8 bundle)** | ~280–320 MB (4 ONNX int8 sub-models + vocoder + voice.bin + config) |
| **Native model (upstream Python SDK)** | ~400 MB (fp32 weights, not used in sherpa-onnx deployment) |
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
- OpenRAIL-M license (model) + MIT (code) — permits commercial use with use-based restrictions; no revenue cap
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

### Candidate 3: VieNeu-TTS v3 Turbo (Strong Alternative — Outside sherpa-onnx)

**Bilingual Vietnamese-English TTS trained from scratch on 10,000+ hours of speech.** Uses a two-stage architecture: an autoregressive transformer backbone (Qwen3-based, ~0.1B params) paired with the MOSS-Audio-Tokenizer-Nano neural codec for 48 kHz waveform output. Runs outside sherpa-onnx via the standalone [VieNeu-TTS.cpp](https://github.com/dduongtrandai/VieNeu-TTS.cpp) C++ inference engine.

| Attribute | Detail |
| --------- | ------ |
| **License** | **Apache 2.0** (model weights + code) |
| **Languages** | **Bilingual VI+EN** — trained for Vietnamese-first output with native English code-switching via `sea-g2p` phonemizer |
| **Architecture** | Autoregressive transformer backbone (Qwen3-based, ~0.1B params) + MOSS neural audio codec decoder |
| **Compressed (int8/Q4)** | **~160–200 MB** — backbone ~130–160 MB, codec decoder ~25–35 MB, phonemizer lexicon ~3–5 MB |
| **Sample rate** | **48 kHz** 16-bit WAV — highest output quality of any candidate |
| **Voices** | **8 built-in default voices**: Ngọc Lan, Ngọc Linh, Trúc Ly, Mỹ Duyên (female); Xuân Vĩnh, Thái Sơn, Gia Bảo, Đức Trí (male) |
| **RTF (SD8G2 CPU, int8/Q4)** | **0.15–0.25** — 4–6× real-time on Snapdragon 8 Gen 2 |
| **TTFT (first audio)** | ~120–180 ms for short sentences |
| **Emotion tags** | ✅ **Native support** — `[cười]` (laugh), `[thở dài]` (sigh), `[hắng giọng]` (clear throat), `[ngập ngừng]` (hesitation), `[kể chuyện]` (storytelling), `[suy nghĩ]` (pause/ponder) |
| **Reading styles** | natural, news, storytelling — selected via voice prompt |
| **Voice cloning** | ✅ **Zero-shot** — from 3–5 s reference audio, no reference text needed. Temperature 0.7–0.8 for consistent identity |
| **English quality** | Clear and intelligible, slight Vietnamese accent. Intrasentential code-switching (e.g., "Hệ thống sử dụng alternating current") executes smoothly |
| **Android integration** | Requires **custom NDK build** of `VieNeu-TTS.cpp` + JNI bridge (~1.5–2 days). No pre-built AAR exists |
| **Inference backends** | Two paths: (1) **GGUF/llama.cpp** — 20–30% faster on ARM NEON for autoregressive backbone; (2) **ONNX Runtime** — for codec decoder |
| **Peak RAM** | ~250–350 MB during active synthesis |
| **Repository status** | ✅ **Active development** — v3 Turbo early access now, full v3 targeted mid-to-late 2026. Maintained by Phạm Nguyễn Ngọc Bảo (model) and dduongtrandai (C++ engine) |

**Pros:**

- **Best Vietnamese quality of all candidates** — trained from scratch on 10,000+ hours of bilingual VI+EN speech, not a fine-tune or adaptation. 48 kHz output is the highest sample rate available.
- **Native expression tags** — `[cười]`, `[thở dài]`, `[hắng giọng]` work inline, answering the prosody question that Supertonic leaves uncertain on mobile. Additional experimental tags (`[ngập ngừng]`, `[kể chuyện]`, `[suy nghĩ]`) for finer control.
- **Apache 2.0 license** — clean commercial terms, no attribution required, no revenue cap. Active maintenance with no archival risk.
- **Zero-shot voice cloning** — 3–5 s reference audio, no reference text needed. Available indefinitely (no Voice Builder shutdown deadline).
- **GGUF/llama.cpp path is faster than ONNX for autoregressive decoding** — 20–30% speedup on ARM NEON vs ONNX Runtime for the backbone.
- **Active community** — rapid iteration through v1 → v2 → v2 Turbo → v3 Turbo in under a year. Full v3 release with expanded features incoming.

**Cons / risks:**

- **Android integration effort** — no pre-built APK or AAR. Requires NDK cross-compilation of `VieNeu-TTS.cpp` and a ~1.5–2 day JNI bridge. This is the primary adoption barrier for v1.
- **No sherpa-onnx compatibility** — uses a separate C++ runtime. Cannot reuse the `OfflineTts` Kotlin API from ADR-008's ASR integration pattern.
- **Larger peak RAM** — ~250–350 MB vs Supertonic's ~200 MB. Still fits within the 4 GB budget but consumes more headroom.
- **English voice quality is accented** — English output carries a Vietnamese speaker accent. For EN→VI direction (Vietnamese user hearing translated English), this may be acceptable; for VI→EN direction (English speaker hearing the translation), it may sound less natural.
- **Emotion tags are experimental** — marked experimental in v3 Turbo early access. Standard tags (`[cười]`, `[thở dài]`) work consistently at natural punctuation pauses, but can occasionally cause pitch instability during aggressive voice cloning or high-speed streaming.
- **Model format fragmentation / toolchain sprawl** — the optimal hybrid path (GGUF backbone + ONNX codec) means two different inference engines in the same pipeline, increasing build complexity. This adds a fourth runtime family (GGUF/llama.cpp) on top of QNN/QAIRT, ONNX Runtime, and sherpa-onnx JNI — cross-referencing ADR-003's toolchain sprawl risk.

---

### Ruled-out candidates

| Model | Why ruled out |
| ----- | ------------- |
| **Kokoro** (v1.0, v1.1) | No Vietnamese support — only English, Chinese, Japanese, Korean. Int8 at 126–140 MB but does not cover the primary requirement. |
| **MeloTTS** (original) | RTF 6.7 on RPi4 single-thread — too slow for real-time without heavy multi-threading. zh_en bilingual only, no Vietnamese. A community Vietnamese fork exists (`nmcuong/MeloTTS-Vietnamese`, MIT) but the author warns of suboptimal voice quality and imprecise transcriptions from a 25 h dataset. Would need fine-tuning on quality data for production use — not a v1 path. |
| **KittenTTS** | English-only models (nano/mini). No Vietnamese. Would require pairing with a separate VI TTS. |
| **ZipVoice** | Zero-shot voice cloning model requiring both reference audio and exact reference text transcript. CN/EN bilingual only. |
| **PocketTTS** | Zero-shot voice cloning requiring reference audio only, but CN/EN only. No Vietnamese. |
| **Matcha-TTS** | English and Chinese only. Faster than VITS (RTF 0.39–0.94) but no Vietnamese support. |
| **MMS-TTS** | 1,100+ languages including Vietnamese, but character-level output with lower naturalness than neural models tested here. Not available as pre-built sherpa-onnx asset. |

---

## Decision


Kavi v1 TTS should adopt a **two-phase approach**: start with **SupertonicTTS 3 via sherpa-onnx** for rapid integration, then transition to **VieNeu-TTS v3 Turbo** as the primary Vietnamese TTS engine once the NDK/JNI bridge is built. Piper VITS serves as a lightweight fallback if neither primary option meets latency or size constraints.

### Phase 1 (v1 launch): SupertonicTTS 3 via sherpa-onnx

For the initial v1 release, use **SupertonicTTS 3** as the single-model TTS engine. This gets Kavi to market with minimal integration risk while the VieNeu-TTS bridge is developed in parallel.

**Rationale for Phase 1:**

1. **Zero integration lead time** — pre-built APKs exist. The `OfflineTts` Kotlin API mirrors the `OfflineRecognizer` from ADR-008. The team builds expertise with one sherpa-onnx API surface for both ASR and TTS.

2. **Single-model simplicity** — `--lang vi` / `--lang en` switching on the same ONNX session avoids dual-configuration overhead and branch logic in the pipeline. This aligns with ADR-008's architectural preference for merged simplicity.

3. **Latency headroom** — RTF 0.012 on M4 Pro CPU is dramatically faster than real-time. Even on SD8G2, the expected RTF (~0.10–0.15) leaves headroom in the 2.0 s pipeline budget.

4. **OpenRAIL-M + MIT license** — permits commercial use; no revenue cap. See [Supertonic 3 LICENSE](https://huggingface.co/Supertone/supertonic-3/blob/main/LICENSE) for use-based restrictions.

### Key mitigations for the archival risk (Supertonic Phase 1)

| Risk | Mitigation |
| ---- | ---------- |
| Repository archived after 2026-08 | The model is OpenRAIL-M-licensed and frozen, not removed. sherpa-onnx releases will continue to bundle the ONNX assets. Phase 2 migration to VieNeu-TTS removes dependency entirely. |
| No upstream bug fixes | The model is a static ONNX graph — no runtime patches needed. Sherpa-onnx itself maintains the inference engine separately. |
| Voice Builder shutdown after 2026-08-31 | If the team wants a custom Kavi voice, create and export the JSON profile before the shutdown date. Pre-built voices (M1–M5, F1–F5) remain available indefinitely. |

### Integration architecture (Phase 1 — Supertonic)

```text
TranslationService pipeline (from ADR-007 Decision 1)
    ↓ (translated text from Opus-MT decoder)
┌────────────────────────────────────────────────────────────┐
│ TTS: SupertonicTTS 3 (single ONNX session via sherpa-onnx) │
│                                                             │
│  OfflineTtsConfig:                                          │
│    model.supertonic = {                                     │
│      durationPredictor, textEncoder, vectorEstimator,       │
│      vocoder, ttsJson, unicodeIndexer, voiceStyle           │
│    }                                                        │
│    numThreads = 4                                            │
│    provider = "cpu"                                          │
│                                                              │
│  GenerationConfig:                                          │
│    sid = 0–9 (selects voice: M1–M5, F1–F5)                  │
│    lang = "vi" or "en" (switched per utterance)              │
│    speed = 1.0                                               │
│                                                              │
│  tts.generateWithConfigAndCallback(text, genConfig)          │
│  → float[] audio_samples                                     │
└────────────────────────────────────────────────────────────┘
    ↓ (44.1 kHz PCM float)
AudioTrack → playback / Bluetooth A2DP
```

Example Kotlin integration (Phase 1):

```kotlin
// Single config, both languages (Sherpa-onnx Kotlin API)
// Source: https://github.com/k2-fsa/sherpa-onnx/blob/master/kotlin-api-examples/test_supertonic_tts.kt
val ttsConfig = OfflineTtsConfig(
    model = OfflineTtsModelConfig(
        supertonic = OfflineTtsSupertonicModelConfig(
            durationPredictor = "$modelDir/duration_predictor.int8.onnx",
            textEncoder = "$modelDir/text_encoder.int8.onnx",
            vectorEstimator = "$modelDir/vector_estimator.int8.onnx",
            vocoder = "$modelDir/vocoder.int8.onnx",
            ttsJson = "$modelDir/tts.json",
            unicodeIndexer = "$modelDir/unicode_indexer.bin",
            voiceStyle = "$modelDir/voice.bin",
        ),
        numThreads = 4,
    ),
)
val tts = OfflineTts(config = ttsConfig)

// For each utterance, select language based on ASR language detection (ADR-008):
// VI_TO_EN: user spoke VI → translated text is English → TTS lang="en"
// EN_TO_VI: user spoke EN → translated text is Vietnamese → TTS lang="vi"
fun synthesize(text: String, direction: TranslationDirection): FloatArray {
    val lang = when (direction) {
        VI_TO_EN -> "en"   // translated text is English
        EN_TO_VI -> "vi"   // translated text is Vietnamese
    }
    val genConfig = GenerationConfig(
        sid = 0,           // speaker ID: 0–9 maps to M1–M5, F1–F5
        speed = 1.0f,
        numSteps = 8,
        extra = mapOf("lang" to lang),
    )
    return tts.generateWithConfigAndCallback(text, genConfig) { samples -> 1 }
}
```

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
| **VieNeu-TTS NDK build** | Cross-compile `VieNeu-TTS.cpp` for `arm64-v8a` using Android NDK r25c+. Validate the CMake toolchain with `-DENABLE_NEON=ON -DCMAKE_CXX_FLAGS="-O3 -flto"`. Measure build output size. | Integration | Phase 3 (parallel) |
| **VieNeu-TTS JNI bridge** | Write JNI wrapper around `vieneu_tts.h` C ABI (vieneu_init, vieneu_synthesize, vieneu_free). Target ~1.5–2 days effort. Expose as `VieNeuTTSWrapper` Kotlin class with `suspend fun synthesize()`. | Integration | Phase 3 (parallel) |
| **VieNeu-TTS Android RTF benchmark** | Measure RTF on SD8G2 for both inference paths (GGUF backbone + ONNX codec vs. pure ONNX). Compare to Supertonic 3 baseline. | Benchmarking | Phase 4 |
| **VieNeu-TTS emotion tag reliability** | Test all documented tags (`[cười]`, `[thở dài]`, `[hắng giọng]`, `[ngập ngừng]`, `[kể chuyện]`, `[suy nghĩ]`) on device. Classify each as stable vs. experimental. Document sanitisation path for critical translations. | Research | Phase 4 |
| **VieNeu-TTS English quality assessment** | Conduct listening test comparing VieNeu-TTS English output (accented) vs. Supertonic English output (native) for the VI→EN direction. Decide whether accent is acceptable for the target user. | UX / PM | Phase 4 |
| **Phased migration plan** | Define cutover criteria from Phase 1 (Supertonic) to Phase 2 (VieNeu-TTS): RTF threshold, quality score, JNI bridge completion, emotion tag readiness. | Architecture | Phase 3 |

---

## Consequences

### Positive


- **Single model, single config, zero branching** — the TTS pipeline is a straight line. Load one ONNX session, switch `lang` per utterance. No dual-manifest management, no model-swap logic.
- **44.1 kHz native output** — matches Bluetooth A2DP high-quality profile. No resampling needed.
- **10 voices built-in** — male and female options for both VI and EN without additional downloads.
- **OpenRAIL-M + MIT license** — permits commercial use; no revenue cap. Use-based restrictions apply to model weights (see LICENSE).
- **Pre-built APK available now** — immediate device testing without custom JNI builds.
- **Repository archival is not a service shutdown** — the model binaries remain downloadable under OpenRAIL-M indefinitely.


- **~280–320 MB on-disk (Phase 1)** — Supertonic is non-trivial. Combined with ASR (~60 MB dual Zipformer int8), MT (~500 MB encoder+decoder+KV cache), denoiser (~50 MB), total may exceed 800 MB. Mitigation: Android APK expansion file (OBB) or on-device download on first run.
- **Repository archival (Phase 1)** — Supertonic stops evolving after August 2026. Mitigation: Phase 2 migration to VieNeu-TTS removes this dependency entirely.
- **44.1 kHz vocoder on mobile CPU (Phase 1)** — Supertonic's RTF may degrade on SD8G2 vs. M4 Pro benchmarks. If RTF exceeds 0.5, fall back to Piper VITS.
- **Android integration effort (Phase 2)** — VieNeu-TTS requires a ~1.5–2 day NDK/JNI bridge. No pre-built AAR exists. Mitigation: start building in parallel with Phase 1.
- **English voice is accented (Phase 2)** — VieNeu-TTS English carries a Vietnamese accent. Acceptable for VI→EN direction (Vietnamese user hears translated EN), but less natural for EN→VI. Mitigation: use Supertonic for EN→VI in a hybrid configuration if needed.
- **Emotion tags are experimental (Phase 2)** — occasional pitch instability during aggressive voice cloning or high-speed streaming. Mitigation: sanitizable/optional for critical translation outputs.
- **Model format fragmentation (Phase 2)** — hybrid GGUF + ONNX path means two inference engines in the same pipeline, increasing build complexity.
- **Voice Builder shutdown (Phase 1)** — after 2026-08-31, no new custom Supertonic voices. Mitigation: create any desired Kavi voice profile before shutdown.
- **No fine-grained prosody control (both phases)** — neither engine supports full SSML or per-word emphasis. Post-processing volume envelopes would be needed for alert/urgency scenarios.

---


See [ADR-028](ADR-028-vieneu-tts-migration.md) for the Phase-2-specific
consequences and risks.

## References

- **VieNeu-TTS official docs:** <https://docs.vieneu.io/>
- **VieNeu-TTS GitHub (active):** <https://github.com/pnnbao97/VieNeu-TTS>
- **VieNeu-TTS v3 Turbo HuggingFace:** <https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo>
- **VieNeu-TTS.cpp (C++ engine):** <https://github.com/dduongtrandai/VieNeu-TTS.cpp>
- **MOSS-Audio-Tokenizer-Nano ONNX:** <https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX> (Apache 2.0 — [LICENSE](https://raw.githubusercontent.com/OpenMOSS/MOSS-Audio-Tokenizer/main/LICENSE))
- **sea-g2p phonemizer:** <https://github.com/pnnbao97/sea-g2p> (Apache 2.0 — [LICENSE](https://raw.githubusercontent.com/pnnbao97/sea-g2p/main/LICENSE))
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
- **ADR-003:** Hexagon runtime / compiler strategy (toolchain sprawl risk — relevant to Phase 2 GGUF/llama.cpp addition)
- **ADR-007:** Production Inference Architecture & Service Layer (TTS slot reserved, Decision 5 memory budget)
- **ADR-008:** v1 Android ASR Decision — Dual Zipformer (TTS remains TBD in pipeline, corrected ASR memory ~60 MB)
- **ADR-004:** Speech-to-Speech Architecture / Tech-Stack (deferred decisions)
