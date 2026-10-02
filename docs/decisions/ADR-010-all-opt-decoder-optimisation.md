# ADR-010: `ALL_OPT` is safe — no custom ONNX operators in the pipeline

## Status

Proposed

## Date

2026-07-30

## Deciders

Kavi team

## Relates to

[ADR-021](ADR-021-ort-cpu-decoder-session-options.md) (the baseline ORT session
config this record expands), [ADR-008](ADR-008-dual-zipformer-asr.md) (Dual
Zipformer ASR — no custom ops in the pipeline),
[ADR-009](ADR-009-supertonic-tts-v1.md) (TTS Phase 1 — Supertonic via sherpa-onnx)

---

## Context

ADR-021 specifies that all CPU-side ONNX Runtime decoder sessions should use `GraphOptimizationLevel.ORT_ENABLE_ALL` (hereafter `ALL_OPT`), alongside `CPUArenaAllocator(true)` and `MemoryPatternOptimization(true)`. The `ALL_OPT` setting was chosen to maximise decoder throughput — an uncontroversial choice given that Kavi's pipeline uses only standard ONNX operators.

However, the RTranslator reference architecture (§3.11 and §4.2.5 of the ADR-007 vs RTranslator comparison doc) is forced to use `NO_OPT` on every ORT session despite being an otherwise similar offline speech-translation pipeline. Understanding *why* RTranslator cannot use `ALL_OPT` — and why Kavi can — is important for:

1. **Confidence that the setting is correct** — no silent correctness or stability regression.
2. **Knowing the boundary conditions** — under what future circumstances would `ALL_OPT` become unsafe?
3. **Design review documentation** — so new team members understand the trade-off without rediscovering it.

This ADR records that analysis. It formalises the `ALL_OPT` decision by establishing the architectural invariant that makes it safe, enumerates the three scenarios that would break it and why none are on the roadmap, and quantifies the expected benefit.

---

## Decision: Use `ORT_ENABLE_ALL` on all CPU ONNX decoder sessions

All CPU-side ONNX Runtime decoder sessions in the Kavi pipeline use:

```kotlin
sessionOptions.setCPUArenaAllocator(true)
sessionOptions.setMemoryPatternOptimization(true)
sessionOptions.setOptimizationLevel(ORT_ENABLE_ALL)
```

### Affected sessions

| Pipeline stage | Session | Managed by | Graph content |
| --- | --- | --- | --- |
| **ASR decoder** | Zipformer decoder + joiner | sherpa-onnx (internal) | Standard ONNX ops: `Conv`, `Relu`, `Gemm`, `Tanh`, `Sigmoid`, `Add`, `Mul`, `Reshape`, `Transpose` |
| **MT decoder** | Opus-MT autoregressive decoder | Kavi / sherpa-onnx | Standard ONNX ops: `Embedding`, `MultiHeadAttention`, `LayerNorm`, `Gelu`, `Gemm`, `Softmax` |
| **TTS (Phase 1)** | SupertonicTTS 4 sub-models (duration_predictor, text_encoder, vector_estimator, vocoder) | sherpa-onnx (internal) | Standard ONNX ops: `Conv1d`, `ConvTranspose1d`, `Gemm`, `Relu`, `Tanh`, `Add`, `Mul` |
| **Denoiser** | GTCRN | sherpa-onnx (internal) | Standard ONNX ops: `STFT`, `Conv2d`, `Relu`, `GRU`, `ISTFT` |

Every affected session uses **only operators from the standard `ai.onnx` domain** — no custom operators, no non-standard domains, no `OrtxPackage` dependency.

---

## Why RTranslator cannot use `ALL_OPT`

RTranslator's Whisper/NLLB pipeline requires `OrtxPackage` — Microsoft's ONNX Runtime Extensions for Android — because its Whisper detokenizer is fused into the ONNX graph as a custom operator (`LogitsToText` or `BpeDecoder`) rather than executed externally in Java. The same `OrtxPackage` dependency applies to NLLB's SentencePiece tokenization.

This creates a fundamental conflict with `ALL_OPT` through three failure mechanics:

### Mechanism 1: Schema registry isolation

ONNX Runtime's graph optimisation passes rely on formal operator schemas (`OpSchema`) to infer output shapes, data types, and layout rules. Custom operators registered via `registerCustomOpLibrary()` belong to non-standard domains (e.g., `ai.onnx.contrib` or `com.microsoft.extensions`). The optimiser's shape- and type-inference engines cannot inspect these ops because no static C++ schema registration exists for them. When `ALL_OPT` encounters a node whose schema it cannot resolve, the optimisation pass aborts or produces invalid intermediate graphs.

### Mechanism 2: Illegal graph transformations across custom-op boundaries

At `ALL_OPT`, optimisation passes traverse adjacent nodes across the entire graph — fusing, constant-folding, and reordering operations for better cache locality and kernel efficiency. When a pass attempts to push a `Transpose` node across a custom-op boundary, or fold constants through an unknown operator, it cannot verify that the transformation preserves correctness. The result is one of:

- Schema resolution errors (`Status(ONNXRUNTIME, INVALID_ARGUMENT)`)
- Graph corruption (wrong tensor shapes propagated past the custom op)
- Native segmentation faults during `InferenceSession::Initialize()`

### Mechanism 3: Phase-order execution hazard

Graph optimisation runs inside `OrtSession` creation *before* the execution plan is finalised. If an optimisation rule attempts to evaluate a node whose custom-kernel ABI hasn't been linked to the execution plan yet, the pass crashes or aborts. This is a phase-ordering issue: the optimiser assumes all operators are resolvable at optimisation time, but custom-domain kernels are registered later in the session lifecycle.

### The `NO_OPT` workaround

RTranslator works around all three by setting `NO_OPT` on every session while still registering `OrtxPackage.getLibraryPath()` for the custom ops:

```java
sessionOptions.setOptimizationLevel(OptLevel.NO_OPT);
sessionOptions.registerCustomOpLibrary(OrtxPackage.getLibraryPath());
```

This is not a Kavi mistake to avoid — it is the **correct design choice for RTranslator's constraints**:

- **29+ languages** — fusing the detokenizer into ONNX via a custom op avoids maintaining 29 separate tokenizer code paths in Java. The single-custom-op approach simplifies deployment at the cost of losing `ALL_OPT`.
- **Pre-optimised offline** — RTranslator's models are pre-quantised and graph-optimised during desktop export. Runtime optimisation gains on already-optimised int8 graphs are negligible, so `NO_OPT` loses little.
- **Memory spikes** — Whisper + NLLB together total ~1 GB in memory. `ALL_OPT`'s graph compilation pass allocates significant temporary memory, which on 6 GB Android devices triggers the Low Memory Killer.

---

## Why Kavi can use `ALL_OPT`

Kavi avoids all three failure mechanisms because **no pipeline stage uses custom ONNX operators**. The architectural invariants that make `ALL_OPT` safe:

| Invariant | RTranslator | Kavi | Why Kavi differs |
| --- | --- | --- | --- |
| **Detokenization in ONNX graph?** | Yes — fused `LogitsToText` custom op via `OrtxPackage` | No — sherpa-onnx handles decoding internally in C++ | Kavi uses sherpa-onnx, which keeps detokenization outside ORT. Zipformer transducers output native `ys_log_probs` — no custom op needed. |
| **Tokenization in ONNX graph?** | Yes — SentencePiece custom op for NLLB decode | No — SentencePiece runs externally (C++/JNI), separate from ORT sessions | Only VI and EN directions; external tokenization is trivial to maintain. |
| **Raw ORT sessions with custom ops?** | Yes — custom Whisper detokenizer, custom NLLB tokenizer | No — every session is managed by sherpa-onnx or uses standard ONNX ops directly | Kavi's pipeline composes existing inference frameworks (sherpa-onnx, VieNeu-TTS.cpp) rather than wiring raw ORT sessions. |
| **Model scope** | 29+ languages → fused abstraction necessary | 2 languages (VI-EN) → direct approach feasible | Contest scope eliminates the abstraction pressure that led to the ORTX dependency. |

### Per-stage validation

| Stage | Custom ops? | `ALL_OPT` safe? | Evidence |
| --- | --- | --- | --- |
| Zipformer encoder + decoder + joiner | None — standard `Conv`, `Gemm`, `Relu`, `Tanh`, etc. | ✅ Yes | sherpa-onnx internal; all ops in `ai.onnx` domain |
| Opus-MT decoder | None — standard transformer decoder ops | ✅ Yes | Verified against op list; no custom domains |
| GTCRN denoiser | None — standard STFT/Conv2d/GRU | ✅ Yes | Permissive small model; all ops standard |
| SupertonicTTS 3 sub-models | None — standard Conv/Relu/Tanh | ✅ Yes | sherpa-onnx manages sessions internally |
| VieNeu-TTS (Phase 2) | None — GGUF backbone is llama.cpp (not ORT), codec decoder uses standard ONNX | ✅ Yes | GGUF path avoids ORT entirely; codec decoder is standard Conv1d ops |

---

## Expected benefit

The ADR-007 vs RTranslator comparison doc (§3.11) estimates `ALL_OPT` provides **~15–30% faster decoder execution** over `NO_OPT`. This is consistent with ONNX Runtime's published benchmarks for graph optimisation on transformer decoder graphs.

### Estimated per-utterance impact

| Decoder session | Estimated latency (`NO_OPT`) | Estimated latency (`ALL_OPT`) | Saving |
| --- | --- | --- | --- |
| Zipformer decoder (ASR) | ~40 ms | ~28–34 ms | ~6–12 ms |
| Opus-MT decoder | ~80 ms | ~56–68 ms | ~12–24 ms |
| Supertonic vocoder | ~150 ms | ~105–128 ms | ~22–45 ms |
| **Total per utterance** | **~270 ms** | **~189–230 ms** | **~40–80 ms saved** |

The ~40–80 ms saving per utterance directly contributes to the 2.0 s end-to-end turnaround budget (ADR-020). Note that these are **desktop-class estimates** — actual savings on SD8G2 will be measured during Phase 4 benchmarking, but the *direction* of the benefit is well-established.

### Cost

The cost is effectively **zero** beyond the one-time graph compilation overhead during model load:

| Cost | Detail | Impact |
| --- | --- | --- |
| **Session init time** | `ALL_OPT` graph compilation adds ~100–500 ms per session during `InferenceSession::Initialize()` | Absorbed into the already-budgeted 2–3 s cold-start window (ADR-013); happens once, before any utterance |
| **Additional peak RAM at init** | Graph transformation allocates temporary memory during compilation | Released after session creation; does not affect steady-state peak budget |
| **APK size** | No change — `ALL_OPT` is a runtime option, not a model format | None |

---

## The three off-roadmap scenarios

During the research that informed this ADR, three scenarios were identified where `ALL_OPT` would become unsafe. None are on Kavi's roadmap for any phase.

### Scenario 1: Reverting to Whisper with fused detokenizer custom op

**Hypothetical situation:** Kavi switches from Dual Zipformer back to a Whisper-based ASR, and the Whisper decoder session uses a fused `LogitsToText` custom op (e.g., via an `onnxruntime-extensions` export pipeline from Hugging Face `optimum`).

**Roadmap status:** ❌ Not on roadmap. ADR-008 confirmed Zipformer-30M-VI as the only Vietnamese ASR on sherpa-onnx and committed to Dual Zipformer. Whisper was superseded because Zipformer is smaller (~20 MB vs ~430 MB), streaming-native, and has equal or better WER on Vietnamese. No roadmap item proposes returning to Whisper.

**Theoretical `ALL_OPT` impact:** Would regress to `NO_OPT` on the ASR decoder session — losing ~6–12 ms per utterance. Session would need `OrtxPackage` registered, adding 15–30 MB APK bloat.

### Scenario 2: Fusing MT tokenization into the ONNX graph

**Hypothetical situation:** The Opus-MT pipeline merges SentencePiece tokenization (source-side or target-side) into the ONNX graph as a custom op for an "end-to-end" MT ONNX session.

**Roadmap status:** ❌ Not on roadmap. External tokenization is the correct pattern for Kavi — it keeps the ONNX graph standard, debuggable, and independent of any ORTX dependency. SentencePiece via JNI is simple (two `.spm` files, one C++ wrapper), adds no custom-op risk, and incurs negligible per-utterance overhead (~1–2 ms).

**Theoretical `ALL_OPT` impact:** Would regress to `NO_OPT` on the MT decoder session — losing ~12–24 ms per utterance. Session would need `OrtxPackage` and its version-lock constraint.

### Scenario 3: Bypassing sherpa-onnx and wiring raw ORT sessions with custom ops

**Hypothetical situation:** A future pipeline stage uses raw ONNX Runtime sessions directly (not through sherpa-onnx) and those sessions include custom operators (e.g., a fused post-processing step).

**Roadmap status:** ❌ Not on roadmap. Every current and planned pipeline stage builds on an existing inference framework:

- **ASR** → sherpa-onnx (Zipformer)
- **TTS Phase 1** → sherpa-onnx (Supertonic 3)
- **TTS Phase 2** → VieNeu-TTS.cpp (GGUF + ONNX standard ops)
- **Denoiser** → sherpa-onnx (GTCRN)
- **MT** → Opus-MT via C++ with external SentencePiece

None involve writing raw ORT sessions from scratch.

**Theoretical `ALL_OPT` impact:** Would depend on the custom op type — the three failure mechanisms would need re-evaluation on a case-by-case basis.

### Summary

| Scenario | On roadmap? | `ALL_OPT` risk | Practical consequence |
| --- | --- | --- | --- |
| Whisper + `LogitsToText` | ❌ No | Loss of ~6–12 ms/utt on ASR decoder, 15–30 MB APK bloat | Would require reverting ADR-008 first — not going to happen |
| Fused MT tokenization | ❌ No | Loss of ~12–24 ms/utt on MT decoder, ORTX version lock | External SentencePiece is simpler and better |
| Raw ORT + custom ops | ❌ No | Undefined — depends on op type | No current or planned stage does this |

---

## Cross-reference to ADR-021

This ADR supersedes the brief motivation in ADR-021 with a full analysis. The three ORT session options from ADR-021 remain unchanged:

| Option | Purpose | Status |
| --- | --- | --- |
| `CPUArenaAllocator(true)` | Pool and reuse memory — zero allocation during inference | Confirmed |
| `MemoryPatternOptimization(true)` | Pre-compute optimal tensor layout — faster inference at higher upfront cost | Confirmed |
| `OptimizationLevel(ORT_ENABLE_ALL)` | Full graph fusion, constant folding, layout opt — ~15–30% faster decode | Confirmed by this ADR |

The additional insight from this ADR is the **architectural invariant** that makes `ALL_OPT` safe: Kavi uses only standard ONNX operators on every CPU decoder session, mediated by existing inference frameworks (sherpa-onnx, VieNeu-TTS.cpp). No custom op domains, no `OrtxPackage`, no `NO_OPT` regression.

---

## Consequences

### Positive

- **~15–30% faster CPU decoder execution** on every session — directly contributes to the 2.0 s turnaround budget.
- **No APK bloat** — no `onnxruntime-extensions-android` (saves 15–30 MB vs. the ORTX path).
- **No version-lock risk** — no ORTX AAR version dependency beyond the core `onnxruntime-android` package.
- **No memory spike at session init** — `ALL_OPT` graph compilation on standard ops is well-behaved and bounded; the aggressive ORTX + `ALL_OPT` memory spike RTranslator avoids is not a risk here.
- **Design clarity** — the architectural invariant is now documented: "Kavi uses `ALL_OPT` on all CPU decoder sessions because no pipeline stage uses custom ONNX operators."

### Negative / risk

- **`ALL_OPT` must be validated per-session during Phase 4 benchmarking** — the fact that all ops are standard does not guarantee that every graph transforms optimally. Each session (Zipformer decoder, Opus-MT decoder, GTCRN, Supertonic) should have its optimised-vs-unoptimised latency measured independently.
- **If a future phase adds a custom op** (e.g., a fused post-processing node), this ADR's invariant is violated and per-session optimisation-level tuning is required. The three off-roadmap scenarios serve as a design-review checklist.
- **`ALL_OPT`'s graph transformations are a black box** — ORT does not expose a human-readable diff of what was fused or reordered. If a regression occurs (correctness issue after an ORT version upgrade), diagnosing it requires rebuilding with `NO_OPT` and bisecting the optimisation passes.

---

## References

- **ADR-021:** ONNX Runtime CPU decoder optimisations (`ALL_OPT`, arena allocator, memory pattern optimisation)
- **ADR-007 vs RTranslator comparison, §3.11:** ONNX Runtime usage — RTranslator's `NO_OPT` vs Kavi's `ALL_OPT`
- **ADR-007 vs RTranslator comparison, §4.2.5:** Pain point: `NO_OPT` on all sessions is a red flag — validate `ALL_OPT` per-session
- **ADR-007 vs RTranslator comparison, fn [7]:** Custom-op persistence regardless of encoder runtime
- **ADR-008:** Dual Zipformer ASR — confirms no custom ops in ASR path
- **ADR-009:** Phased TTS strategy — Supertonic via sherpa-onnx, VieNeu-TTS via GGUF/standard ONNX
- **microsoft/onnxruntime-extensions:** <https://github.com/microsoft/onnxruntime-extensions>
- **ONNX Runtime optimisation levels (official docs):** <https://onnxruntime.ai/docs/performance/graph-optimizations.html>
- **RTranslator source (niedev/RTranslator):** `app/src/main/java/nie/translator/rtranslator/` — session config with `NO_OPT` + `OrtxPackage`
