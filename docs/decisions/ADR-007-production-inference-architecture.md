# ADR-007: Production Inference Architecture & Service Layer

**Status:** Superseded by ADR-008
**Date:** 2026-07-26 (Superseded: 2026-07-27)
**Deciders:** Kavi team
**Supersedes / relates to:** ADR-004 (tech-stack deferred decisions), ADR-005 (QNN workarounds — encoder/NPU, decoder/CPU split confirmed), ADR-006 (Android runner — feeds into service design)
**Superseded by:** [ADR-008](ADR-008-v1-android-asr-decision.md) — v1 Android implementation decision (Dual Zipformer ASR, confirming Opus-MT MT and TBD TTS)

---

## Context

ADR-001 through ADR-006 establish the foundations:

- **ADR-001:** 100% offline, on-device execution (no cloud dependency).
- **ADR-002:** Snapdragon 8 Gen 2 / Android 16 / Hexagon HTP v73 target.
- **ADR-003:** QAIRT/QNN as the NPU runtime; CPU fallback via XNNPACK int8.
- **ADR-004:** License-gated candidate set; final model picks deferred to benchmarks (remains Draft).
- **ADR-005:** Encoder-on-NPU, decoder-on-CPU split — the conversion-failure analysis (Whisper decoder `IsNaN`, Piper cyclic graph) that replaced the initial "custom ops" hypothesis with measured blockers.
- **ADR-006:** Android instrumented-test runner for batch evaluation (single push, single pull).

**What these ADRs do not cover:**

1. **Service-layer architecture** — how the pipeline stages (denoise → ASR → MT → TTS) are composed, orchestrated, and exposed as Android services for production use (not just batch eval).
2. **Model lifecycle** — when models load, whether they stay resident, how tensors and KV caches are allocated.
3. **Memory management across compute units** — how encoder outputs hand off from NPU (ION buffers) to CPU decoders without copies, and what that implies for buffer lifetimes.
4. **Language detection** — how the system detects whether the user spoke Vietnamese or English without an external classifier.
5. **Concurrency model** — how structured concurrency (coroutines) connects the pipeline stages while respecting the 2.0 s turnaround budget.
6. **Denoising integration** — whether and where noise suppression sits in the pipeline.
7. **Packaging** — the precise set of QNN shared objects and context binaries that ship in the APK.

This ADR fills those gaps. It describes the production inference architecture intended for the Phase-4 Android application, building on the runtime and runner decisions captured in ADR-003/005/006.

---

## Decision 1: TranslationService — Two-mode foreground service

Kavi exposes a single Android `Service` that hosts the full inference pipeline in two operational modes.

### Mode A: OneDevice (WalkieTalkie)

- Single device, two speakers pass the phone back and forth.
- One `AudioRecord` capture, one `AudioTrack` playback.
- Push-to-talk or VAD-triggered utterance segmentation.
- No external hardware; entirely self-contained.

### Mode B: PeerToPeer (Conversation)

- Two devices paired over BLE 5.2+, each handling one speaker.
- Each device captures its own speaker's audio, processes denoise → ASR → MT → TTS locally, and sends the translated text to the peer device (which synthesises it locally).
- Optional bone-conduction headset or earbuds for improved SNR on the capture side.

### Shared infrastructure (both modes)

| Component | Role |
| --- | --- |
| `TranslationService` | Android `Service` with `FOREGROUND_SERVICE` + `microphone` foreground service type; holds all model references, manages `PowerManager.WakeLock` |
| `Recorder` | `AudioRecord` PCM float, 16 kHz mono, circular buffer; VAD (amplitude threshold + speech timeout) built in or composed with a lightweight model |
| `AudioTrack` | Playback of synthesised audio |
| Model instances | Loaded once in `TranslationService.onCreate()`, never released during the session |

**Key invariant:** one `TranslationService` instance per process, holding all model state. No lazy loading, no on-demand model swapping.

---

## Decision 2: Persistent model residency — load everything at startup

All models load in `TranslationService.onCreate()` and remain resident for the lifetime of the service. No lazy loading, no on-demand swapping between modes.

### Load sequence (cold start, ~2–3 s)

```
TranslationService.onCreate()
├── Load Whisper tokenizer (byte-level BPE/GPT-2)  → permanent
├── Load Opus-MT tokenizer (SentencePiece)          → permanent
├── Load Whisper encoder QNN context binary          → NPU, permanent
├── Load Whisper decoder ONNX session                → CPU, permanent
├── Load Opus-MT encoder QNN context binary           → NPU, permanent
├── Load Opus-MT decoder ONNX session                 → CPU, permanent
├── Load TTS model ONNX session                       → CPU, permanent (model TBD)
├── Allocate KV caches (max-size)                     → CPU memory, permanent
└── Allocate I/O tensors                              → permanent
```

### Rationale

- **Zero model-loading overhead per utterance** — after cold start, every pipeline invocation skips I/O and initialization.
- **Predictable latency** — no garbage-collection or JIT loading spikes mid-conversation.
- **RAM headroom** — the 4 GB peak budget comfortably accommodates all models concurrently (see Decision 5: Memory budget).
- **Trade-off:** ~2–3 s cold start when the service first launches (or is killed and restarted by the OS).

### Open parameter: TTS model

The TTS model slot is reserved but the specific model (MeloTTS / Piper / Kokoro / other) is not yet selected. ADR-004 lists this as an open parameter closed by benchmark results.

---

## Decision 3: Max-size KV cache pre-allocation at startup

The autoregressive decoders (Whisper, Opus-MT) allocate KV cache tensors token-by-token during decoding. With RAM headroom in the 4 GB budget, Kavi pre-allocates the maximum possible KV cache size at startup and reuses it across every decode invocation.

### Constants

| Parameter | Value | Basis |
| --- | --- | --- |
| `MAX_ASR_TOKENS` | 448 | ~15 s of speech × 30 tok/s |
| `MAX_MT_TOKENS` | 256 | Max translation output length |

### Allocation

```
float[] kvCache = new float[MAX_TOKENS × layers × heads × dim];
// Allocated once, zero allocations during decode loop
```

### Effect

- **Zero allocation/free overhead** in the per-token decode loop — the loop becomes pure matmul + attention.
- **Predictable peak RAM** — no heap growth as utterance length varies.
- **Waste on short utterances** — a 2-second utterance uses only ~14% of the ASR KV cache; the rest is unused but resident.
- **Cache reuse** — after each utterance, the KV cache pointer resets to position 0; no re-allocation needed.

### Cross-reference

ADR-005 established that the **decoder runs on CPU** — so KV cache lives in CPU-accessible memory (not NPU VTCM), which naturally handles the dynamic-length access pattern. The NPU encoder never touches the KV cache; it writes only `encoder_hidden_states` to a fixed-size ION buffer.

---

## Decision 4: NPU→CPU zero-copy via ION shared memory

On Snapdragon 8 Gen 2, the Hexagon NPU (HTP v73) shares DDR memory with the CPU via ION buffers. When the NPU finishes writing `encoder_hidden_states`, the CPU can read the same physical memory directly — no memcpy needed, just a cache-coherency barrier (~1–3 ms for ~5 MB on Snapdragon).

### Pipeline handoff

```
NPU (QNN context binary)            CPU (ONNX Runtime)
┌──────────────────────┐           ┌──────────────────────┐
│ Whisper encoder      │   ION     │ Whisper decoder       │
│ → encoder_output     │ ────────→ │ (reads ION buffer     │
│   in ION buffer      │  barrier  │  via pointer, no copy)│
├──────────────────────┤           ├──────────────────────┤
│ Opus-MT encoder      │   ION     │ Opus-MT decoder       │
│ → encoder_output     │ ────────→ │ (same pattern)        │
│   in ION buffer      │  barrier  │                       │
└──────────────────────┘           └──────────────────────┘
```

### Why this matters

- NPU→GPU or CPU→GPU handoffs require explicit DMA copies (slower).
- NPU→CPU zero-copy is unique to the Snapdragon ION architecture.
- Every millisecond saved here goes directly into the 2.0 s turnaround budget.

### Implementation notes

1. QNN context binary output is written into an ION-backed buffer allocated by `QnnBackend_create()`.
2. The JNI bridge (`qnn_loader_jni.cpp`) returns a **direct ByteBuffer** referencing the ION memory — not a heap copy.
3. ONNX Runtime creates a tensor from the same buffer via `OrtValue::CreateTensor()` with the data pointer, no data migration.

---

## Decision 5: Memory budget

This section accounts for the 4 GB peak-RAM ceiling asserted in Decisions 2 and 3.
The table below sums estimated per-component usage for the full set of persistently
loaded models, runtimes, and buffers.

### Estimated peak memory budget

| Component | Memory | Compute unit | Notes |
| --- | --- | --- | --- |
| Whisper encoder context binary | ~80 MB | NPU (ION/DDR) | QNN context bin, loaded once |
| Opus-MT encoder context binary | ~80 MB | NPU (ION/DDR) | QNN context bin, loaded once |
| Whisper decoder ONNX session | ~350 MB | CPU (DDR) | FP16 weights + decode graph |
| Opus-MT decoder ONNX session | ~350 MB | CPU (DDR) | FP16 weights + decode graph |
| TTS model ONNX session | ~150 MB | CPU (DDR) | Model TBD; conservative estimate |
| Denoiser model (GTCRN) | ~50 MB | CPU (DDR) | Weights + STFT/ISTFT buffers |
| ASR KV cache (max 448 tokens, batch=2) | ~240 MB | CPU (DDR) | Pre-allocated, reused; 2× for dual-language ASR batch (Decision 6) |
| MT KV cache (max 256 tokens) | ~70 MB | CPU (DDR) | Pre-allocated, reused |
| I/O tensors + scratch buffers | ~100 MB | Shared (ION/DDR) | Fixed-size encoder outputs, decoder inputs |
| QNN runtime .so files | ~20 MB | Code (DDR) | libQnnHtp, stubs, system, CPU/GPU backends |
| ONNX Runtime library | ~15 MB | Code (DDR) | libonnxruntime.so |
| Audio circular buffer | ~5 MB | CPU (DDR) | 16 kHz PCM float, ~30 s capacity |
| Android app + service overhead | ~200 MB | CPU (DDR) | Heap, framework, UI |

**Total accounted (statically allocated, max-size):** ~1.71 GB
**Remaining headroom within 4 GB ceiling:** ~2.3 GB

*The 1.71 GB figure is the known-allocated baseline (all models + max-size KV caches, including the batch=2 ASR cache for dual-language detection). The remaining ~2.3 GB covers OS RSS overhead, system-wide framework services (shared via Zygote), transient allocations, and a safety margin — none of which affect the architecture's guarantee that peak is bounded and predictable.*

### Notes

- NPU encoder context binaries execute from shared DDR (ION), not VTCM. The HTP v73's
  local VTCM (~8–16 MB) is insufficient for the full encoder graphs, so the zero-copy
  handoff (Decision 4) reads directly from DDR.
- All figures are estimates based on ONNX Runtime session sizes for equivalent FP16
  transformer models. Exact numbers will be measured during Phase-4 on-device
  benchmarking (ADR-006 runner).
- The 4 GB ceiling is a contest constraint, not a device limit — the reference device
  (Snapdragon 8 Gen 2, 16 GB RAM) has substantial headroom. The budget accounts for
  worst-case concurrent load.

---

## Decision 6: Dual ASR inference for language-autonomous direction detection

### Problem

The system must detect whether the user spoke Vietnamese or English to select the correct MT direction (VI→EN or EN→VI). RTranslator uses ML Kit language identification as a separate closed-source dependency. Kavi eliminates this external dependency.

### Decision

Run two ASR decoder batches in parallel for every utterance — one with English prompts, one with Vietnamese prompts — and use confidence scores to select the language.

### Batch configuration

- ASR encoder runs once (language-agnostic, shared encoder).
- ASR decoder runs at **batch_size=2** (one slot for VI, one for EN).
- Language selected by comparing decoder confidence scores (log-probability per token averaged over the decoded sequence).
- No separate language-identification model or API call.

### Performance impact

| Aspect | Single ASR | Dual ASR (proposed) |
| --- | --- | --- |
| Encoder runs | 1 | 1 (unchanged — encoder is language-agnostic) |
| Decoder runs | 1 | 1 (batch_size=2, same total compute) |
| Language ID latency | ~200 ms (ML Kit) | 0 ms (eliminated) |
| External dependency | Google Play Services | None |

### Caveat

This requires the ASR model to support both VI and EN in a single decoder pass — confirmed for Whisper Small (96 languages) and PhoWhisper (Vietnamese-optimised Whisper fine-tune, also supports EN). Moonshine Tiny is English-only and cannot use this strategy.

---

## Decision 7: Denoising pipeline — tiered, toggleable

The denoising stage has three tiers, applied in order of availability:

```
AudioRecord (mic, 16 kHz PCM float)
    ↓
[Tier 1: ADSP AI-ECNS]    — if available on the device's DSP, free hardware-accelerated echo/noise suppression
    ↓
[Tier 2: GTCRN]           — 523 KB ONNX model via sherpa-onnx, our controlled denoiser
    ↓
[Tier 3: ASR]             — denoised audio enters the ASR encoder
```

### Decision

- **GTCRN** is the working default for v1 pending benchmark confirmation (permissive license, small footprint).
- **ADSP AI-ECNS** is a free bonus layer on supported devices; if unavailable, skip transparently.
- The pipeline must allow toggling denoising on/off per utterance for latency vs. quality benchmarking.
- Denoising model stays loaded permanently (appended to the persistent residency list), with pre-allocated STFT/ISTFT buffers to avoid per-utterance setup overhead.

### Status: OPEN

The final denoising choice (GTCRN vs. alternative) is gated on benchmark results, per ADR-004 parameter #4. This ADR records the *architectural slot* — where denoising sits, how it loads, how it toggles — not the final model pick.

---

## Decision 8: QNN runtime bundling — precise jniLibs/arm64-v8a roster

The APK bundles the QNN runtime shared objects and compiled context binaries in `android/app/src/main/jniLibs/arm64-v8a/`.

### Required .so files

| File | Purpose |
| --- | --- |
| `libQnnHtp.so` | CPU-side QNN API (2.0 MB) |
| `libQnnHtpV73Stub.so` | Hexagon NPU firmware for HTP v73 (444 KB) |
| `libQnnHtpV73CalculatorStub.so` | NPU calculator firmware (6.4 KB) |
| `libQnnHtpPrepare.so` | HTP preparation/initialisation |
| `libQnnSystem.so` | System context manager |
| `libQnnCpu.so` | CPU fallback backend |
| `libQnnGpu.so` | GPU fallback backend (included for future-proofing; the v1 fallback chain is NPU→CPU only — see Decision 9) |
| `libqnn_loader_jni.so` | Our JNI bridge (built from `qnn_loader_jni.cpp`) |

### Context binaries (in assets/)

| File | Model content |
| --- | --- |
| `whisper_encoder_v73.bin` | Whisper Small encoder compiled for HTP v73 |
| `opusmt_encoder_v73.bin` | Opus-MT vi↔en encoder compiled for HTP v73 |

### CPU-side ONNX Runtime models (in assets/)

| File | Runtime |
| --- | --- |
| `whisper_decoder.onnx` | ONNX Runtime CPU (FP16 or int8) |
| `opusmt_decoder.onnx` | ONNX Runtime CPU (FP16 or int8) |
| `tts_model.onnx` | ONNX Runtime CPU (model TBD) |

### Version lock

QAIRT SDK version must match the device runtime: **2.31.0.250130** ↔ **qnn-2.31** ↔ **HTP v73**. Mismatch causes silent inference failure.

---

## Decision 9: Structured concurrency via Kotlin coroutines

The per-utterance pipeline runs on `Dispatchers.Default` within a lifecycle-scoped coroutine scope. Each stage is a `suspend` function.

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

- Structured concurrency ensures cancellation propagates correctly when the user stops speaking or switches modes.
- CPU fallback is **per-encoder, not global** — one encoder may use the NPU while another falls back to CPU.
- The fallback is a **degradation, not a crash** — the conversation continues with higher latency.
- **MT decoding strategy is greedy (beam=1) for v1.** This is a latency-budget decision, not an implementation-friction one: ONNX Runtime handles beam reorder natively, but 4× decoder compute with no NPU offload would risk the 2.0 s turnaround gate at beam=4. Greedy keeps the CPU decoder fast enough to meet the budget. A beam=4 upgrade path exists: it requires widening the decoder's KV cache across beam candidates but does not affect the encoder, ION handoff, or any other pipeline stage. Deferred to Phase-5 for latency-vs-BLEU measurement.

---

## Decision 10: ONNX Runtime CPU decoder optimisations

CPU-side decoder sessions use these ORT settings:

```kotlin
sessionOptions.setCPUArenaAllocator(true)           // Pool & reuse memory
sessionOptions.setMemoryPatternOptimization(true)   // Pre-compute optimal tensor layout
sessionOptions.setOptimizationLevel(ALL_OPT)        // Graph fusion, constant folding
```

- **CPU arena allocator:** zero allocations during inference (slightly higher baseline RSS).
- **Memory pattern optimisation:** more upfront RAM, faster inference.
- **Full ORT optimisation:** ~15–30% faster decoder execution via fused graphs.

---

## Decision 11: VAD — amplitude threshold + speech timeout (no separate VAD model)

Kavi uses an energy-based VAD built into the `Recorder` class for v1.

- **Energy-based VAD:** amplitude threshold on the PCM float stream.
- **Speech timeout:** configurable silence period (default ~500 ms) triggers utterance-finalisation.
- **Rationale:** the energy-based approach adds ~0 ms overhead (operates on the already-captured buffer). A model-based VAD (e.g., Silero) adds ~5–10 ms per frame.
- **Model slot reserved:** if benchmark results show energy-based VAD is inadequate for the target noise environments, a lightweight model can be slotted in without changing the pipeline architecture.
- **Status:** OPEN — energy threshold parameters and noise robustness to be determined in noise-benchmarking phase.

---

## End-to-end data flow

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
│ ASR (Whisper Small)                                        │
│  Encoder (NPU via QNN context binary)                      │
│    → encoder_hidden_states in ION buffer (zero-copy)       │
│  Decoder (CPU via ONNX Runtime, batch_size=2)              │
│    → VI transcript + EN transcript + confidence scores     │
│  Language selection → argmax(confidence_vi, confidence_en) │
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

---

## Consequences

### Positive

- **Predictable per-utterance latency** — persistent model residency + pre-allocated KV caches eliminate I/O, allocation, and JIT overhead from the critical path.
- **No external language detection dependency** — dual ASR batch eliminates ML Kit (or any Play Services dependency), keeping the offline-first invariant clean.
- **Zero-copy NPU→CPU handoff** saves ~5–10 ms per utterance vs. a heap-copy approach, directly contributing to the 2.0 s turnaround budget.
- **Per-encoder fallback** prevents a single NPU failure from taking down the full pipeline — ASR encoder may use NPU while MT encoder falls back to CPU, or vice versa.
- **Two-mode service** covers both contest scenarios (one-device walkie-talkie and two-device conversation) with shared infrastructure.
- **Energy-based VAD** keeps the capture path simple and zero-overhead for v1; model-based VAD can be slotted in later without pipeline changes.
- **jniLibs roster and version locks are documented**, reducing integration risk for new team members.

### Negative / risk

- **Cold start latency (~2–3 s)** — the first utterance after app launch is delayed while all models load. Mitigation: splash screen with progress indication; keep service alive via foreground notification during active use.
- **RAM waste on short utterances** — a 2-second utterance uses ~14% of the pre-allocated 448-token ASR KV cache. Mitigation: considered acceptable within the 4 GB peak budget.
- **Dual ASR requires a multilingual ASR model** — Moonshine Tiny (EN-only) cannot use this strategy. If the final ASR pick is monolingual, language detection reverts to a separate classifier.
- **ION zero-copy is Snapdragon-specific** — the NPU→CPU handoff optimisation does not port to other SoCs (MediaTek, Apple). Mitigation: the pipeline works correctly with heap copies on non-Qualcomm hardware; zero-copy is a performance optimisation, not a correctness requirement.
- **Energy VAD may miss speech onsets in high-noise environments** — if contest evaluation uses noisy samples near 0 dB SNR, a model-based VAD may be required. Mitigation: VAD model slot is in the pipeline; the energy threshold can be tuned or replaced without changing `Recorder`'s interface.
- **Two open parameters remain** — TTS model and denoising model are not yet selected. Their integration points (ONNX session slot, persistent memory reservation, pre-allocated buffers) are fixed by this ADR; only the model binary changes.
- **Version lock on QAIRT SDK** — `qnn-2.31` / HTP v73. An OS update that ships a different Hexagon firmware version would break inference until the SDK version is matched.

---

## References

- ADR-001: Offline-first, on-device architecture
- ADR-002: Target platform — Snapdragon 8 Gen 2, Android 16, Hexagon NPU
- ADR-003: Hexagon runtime / compiler strategy (Proposed)
- ADR-004: Speech-to-Speech Architecture / Tech-Stack (Draft — tech stack NOT yet decided)
- ADR-005: QNN Conversion Workarounds (encoder-on-NPU, decoder-on-CPU split)
- ADR-006: Android Runner Architecture (batch evaluation framework)
- `docs/decisions/license-situation.md` — License clearance for all candidate models
- Kavi App Architecture Proposal — Original architecture proposal (source material for this ADR)
