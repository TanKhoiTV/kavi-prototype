# ADR-028: Migrate v1 TTS to VieNeu-TTS v3 Turbo (Phase 2)

## Status

Proposed

## Date

2026-07-30

## Deciders

Kavi team

## Context

[ADR-009](ADR-009-supertonic-tts-v1.md) selects **SupertonicTTS 3** as the Phase-1
v1 TTS engine, chosen for zero integration lead time (pre-built APKs, the same
sherpa-onnx `OfflineTts` API surface as ASR). It is a pragmatic first pick, not the
quality ceiling.

Two properties of Supertonic make a migration path necessary rather than optional:

- **Repository archival** — the upstream Supertonic repo stops evolving after
  August 2026 (the model stays downloadable under OpenRAIL-M, but receives no
  upstream fixes and no new voices).
- **Vietnamese quality** — Supertonic is a multilingual generalist, so its
  Vietnamese is good but not best-in-class for a product whose primary direction
  is Vietnamese.

This record decides the Phase-2 migration and its preconditions. It was extracted
from the former combined *"v1 Android TTS Decision"*, whose candidate evaluation
(including VieNeu-TTS v3 Turbo as Candidate 3) is retained in
[ADR-009](ADR-009-supertonic-tts-v1.md).

## Decision

Build the `VieNeu-TTS.cpp` NDK/JNI bridge and switch to **VieNeu-TTS v3 Turbo** as
the primary Vietnamese TTS engine. Keep Supertonic as a fallback or for
English-only paths.

### Phase 2 (v1.x or v2): Migrate to VieNeu-TTS v3 Turbo

Build the `VieNeu-TTS.cpp` NDK/JNI bridge and switch to VieNeu-TTS v3 Turbo as the primary Vietnamese TTS engine. Keep Supertonic as a fallback or for English-only paths.

**Rationale for Phase 2:**

1. **Superior Vietnamese quality** — 48 kHz output and 10,000+ hours of bilingual training produce more natural Vietnamese speech than Supertonic's multilingual generalist approach.

2. **Native emotion tags** — `[cười]`, `[thở dài]`, `[hắng giọng]` enable inline expression control that Supertonic cannot guarantee on mobile. This directly addresses the prosody question.

3. **Zero-shot voice cloning** — available indefinitely (no Voice Builder shutdown). With temperature 0.7–0.8, cloned voices remain consistent across utterances.

4. **No archival risk** — Apache 2.0, active community, rapid iteration.


### Integration architecture (Phase 2 — VieNeu-TTS)

```text
TranslationService pipeline (from ADR-007 Decision 1)
    ↓ (translated text from Opus-MT decoder)
┌───────────────────────────────────────────────────────────────┐
│ TTS: VieNeu-TTS v3 Turbo (via VieNeu-TTS.cpp + JNI bridge)   │
│                                                               │
│  // Hybrid inference: GGUF backbone + ONNX codec decoder      │
│  // C ABI via vieneu_tts.h → JNI → Kotlin                     │
│                                                               │
│  VieNeuTTS.init(modelDir, profile="vieneu-v3-onnx")          │
│    ↓                                                            │
│  audio = VieNeuTTS.synthesize(text, voice, lang)              │
│    // emotion tags work inline: "Nghe hay quá [cười]"         │
└───────────────────────────────────────────────────────────────┘
    ↓ (48 kHz PCM float)
AudioTrack → playback / Bluetooth A2DP
```

Example Kotlin integration (Phase 2):

```kotlin
// Custom JNI wrapper for VieNeu-TTS.cpp (estimated 1.5–2 days to build)
class VieNeuTTSWrapper(modelPath: String) {
    private var handle: Long = 0

    suspend fun synthesize(
        text: String,
        voice: String = "Ngọc Lan",
        lang: String = "vi"
    ): FloatArray = withContext(Dispatchers.Default) {
        nativeSynthesize(handle, text, voice, lang)
    }

    private external fun nativeSynthesize(
        handle: Long,
        text: String,
        voice: String,
        lang: String
    ): FloatArray
}
```

---

## Cutover criteria

The migration is gated on all of the following, none of which are met yet:

1. **NDK/JNI bridge complete** — `VieNeu-TTS.cpp` cross-compiled for `arm64-v8a`
   and wrapped as a Kotlin `suspend fun`.
2. **RTF threshold met on SD8G2** — measured on the reference device, and better
   than the Supertonic baseline it replaces.
3. **Emotion-tag reliability classified** — each documented tag tested on device
   and marked stable or experimental, with a sanitisation path for critical
   translations.
4. **English-quality decision made** — a listening test comparing VieNeu-TTS English
   (accented) against Supertonic English (native) for the VI→EN direction.

The open measurement items behind these criteria are tracked in the open-items
table in [ADR-009](ADR-009-supertonic-tts-v1.md).

## Consequences

### Positive


- **Best Vietnamese quality of any candidate** — 48 kHz, trained from scratch on 10,000+ hours of bilingual speech.
- **Native expression tags** — `[cười]`, `[thở dài]`, `[hắng giọng]` enable inline prosody control that Supertonic cannot guarantee.
- **Apache 2.0 license** — no archival risk, active maintenance, rapid iteration.
- **Zero-shot voice cloning indefinitely** — no Voice Builder shutdown deadline.
- **GGUF backbone path is faster than ONNX for autoregressive decoding** — 20–30% speedup on ARM NEON.


Shared risks (on-disk size, archival, prosody control) are recorded in
[ADR-009](ADR-009-supertonic-tts-v1.md). Phase-2-specific risks:

- **Android integration effort** — VieNeu-TTS requires a ~1.5–2 day NDK/JNI
  bridge. No pre-built AAR exists. Mitigation: build in parallel with Phase 1.
- **English voice is accented** — VieNeu-TTS English carries a Vietnamese accent.
  Acceptable for VI→EN (a Vietnamese user hears the translated English), less
  natural for EN→VI. Mitigation: use Supertonic for EN→VI in a hybrid
  configuration if needed.
- **Emotion tags are experimental** — occasional pitch instability during
  aggressive voice cloning or high-speed streaming. Mitigation: sanitizable and
  optional for critical translation output.
- **Model format fragmentation** — the hybrid GGUF + ONNX path means two inference
  engines in the same pipeline, increasing build complexity.

## References

- [ADR-009](ADR-009-supertonic-tts-v1.md) — Phase-1 TTS: SupertonicTTS 3 (and the full candidate evaluation)
- [ADR-003](ADR-003-hexagon-runtime.md) — Hexagon runtime (toolchain sprawl risk; relevant to the GGUF/llama.cpp addition)
- [ADR-016](ADR-016-memory-budget.md) — Peak memory budget
- **VieNeu-TTS official docs:** <https://docs.vieneu.io/>
- **VieNeu-TTS GitHub (active):** <https://github.com/pnnbao97/VieNeu-TTS>
- **VieNeu-TTS v3 Turbo HuggingFace:** <https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo>
- **VieNeu-TTS.cpp (C++ engine):** <https://github.com/dduongtrandai/VieNeu-TTS.cpp>
