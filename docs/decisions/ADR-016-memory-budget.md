# ADR-016: Peak memory budget

## Status

Accepted — revised 2026-07-27 by [ADR-008](ADR-008-dual-zipformer-asr.md)

## Date

2026-07-26

## Deciders

Kavi team

## Context

The contest imposes a **4 GB peak-RAM ceiling**. Several decisions allocate
against that ceiling: persistent model residency
([ADR-013](ADR-013-persistent-model-residency.md)), max-size KV cache
pre-allocation ([ADR-014](ADR-014-max-size-kv-cache-preallocation.md)),
encoder context binaries on the NPU, CPU decoder sessions, and the zero-copy ION
buffers ([ADR-015](ADR-015-npu-cpu-zero-copy-ion.md)). Without an explicit
accounting, no single one of those can be shown to be affordable.

> **Split note:** extracted from the former `ADR-007 Decision 5`.

## Decision

Hold the pipeline to a **4 GB peak-RAM budget**, accounted per component, with all
persistent allocations bounded and predictable.

### Estimated peak memory budget

| Component | Memory | Compute unit | Notes |
| --- | --- | --- | --- |
| Whisper encoder context binary | ~80 MB | NPU (ION/DDR) | QNN context bin, loaded once |
| Opus-MT encoder context binary | ~80 MB | NPU (ION/DDR) | QNN context bin, loaded once |
| Whisper decoder ONNX session | ~350 MB | CPU (DDR) | FP16 weights + decode graph |
| Opus-MT decoder ONNX session | ~350 MB | CPU (DDR) | FP16 weights + decode graph |
| TTS model ONNX session | ~150 MB | CPU (DDR) | Model TBD; conservative estimate |
| Denoiser model (GTCRN) | ~50 MB | CPU (DDR) | Weights + STFT/ISTFT buffers |
| ASR KV cache (max 448 tokens, batch=2) | ~240 MB | CPU (DDR) | Pre-allocated, reused; 2× for dual-language ASR batch |
| MT KV cache (max 256 tokens) | ~70 MB | CPU (DDR) | Pre-allocated, reused |
| I/O tensors + scratch buffers | ~100 MB | Shared (ION/DDR) | Fixed-size encoder outputs, decoder inputs |
| QNN runtime .so files | ~20 MB | Code (DDR) | libQnnHtp, stubs, system, CPU/GPU backends |
| ONNX Runtime library | ~15 MB | Code (DDR) | libonnxruntime.so |
| Audio circular buffer | ~5 MB | CPU (DDR) | 16 kHz PCM float, ~30 s capacity |
| Android app + service overhead | ~200 MB | CPU (DDR) | Heap, framework, UI |

**Total accounted (statically allocated, max-size):** ~1.71 GB
**Remaining headroom within 4 GB ceiling:** ~2.3 GB

*The 1.71 GB figure is the known-allocated baseline (all models + max-size KV
caches, including the batch=2 ASR cache for dual-language detection). The
remaining ~2.3 GB covers OS RSS overhead, system-wide framework services (shared
via Zygote), transient allocations, and a safety margin — none of which affect the
architecture's guarantee that peak is bounded and predictable.*

### Notes

- NPU encoder context binaries execute from shared DDR (ION), not VTCM. The HTP
  v73's local VTCM (~8–16 MB) is insufficient for the full encoder graphs, so the
  zero-copy handoff ([ADR-015](ADR-015-npu-cpu-zero-copy-ion.md)) reads directly
  from DDR.
- All figures are estimates based on ONNX Runtime session sizes for equivalent
  FP16 transformer models. Exact numbers are measured in Phase-4 on-device
  benchmarking ([ADR-006](ADR-006-native-on-device-runner.md)).
- The 4 GB ceiling is a contest constraint, not a device limit — the reference
  device (Snapdragon 8 Gen 2, 16 GB RAM) has substantial headroom. The budget
  accounts for worst-case concurrent load.
- **The ~350 MB Opus-MT decoder figure is likely 4–5× too high.** The same number
  is used for both the Whisper decoder and the Opus-MT decoder, but the
  underlying models differ by roughly 3× in parameter count (~70M total for
  Opus-MT vs 244M for Whisper Small). The measured CTranslate2 int8 checkpoint is
  71 MB for the full encoder+decoder, so a decoder-only session is expected around
  60–80 MB. To be revised when on-device numbers exist.

### Revision — 2026-07-27 ([ADR-008](ADR-008-dual-zipformer-asr.md))

Replacing Whisper Small with dual Zipformer removes most of the ASR footprint:

| Component | ADR-007 (Whisper) | ADR-008 (Dual Zipformer) | Delta |
| --- | --- | --- | --- |
| ASR encoder (NPU) | ~80 MB | **Eliminated** (CPU-only for v1) | −80 MB |
| ASR decoder (CPU) | ~350 MB | **~60 MB** (32 MB VI + 28 MB EN int8) | −290 MB |
| ASR KV cache (batch=2) | ~240 MB | **~0** (transducer, no KV cache) | −240 MB |
| **Total ASR** | **~670 MB** | **~60 MB** | **−610 MB** |

**New total accounted (statically allocated, max-size):** ~1.16 GB (down from
~1.71 GB)
**Remaining headroom within 4 GB ceiling:** ~2.84 GB (up from ~2.3 GB)

This ~610 MB saving provides substantial headroom for the TTS model
([ADR-009](ADR-009-supertonic-tts-v1.md)), larger denoising models, or additional
safety margin.

## Consequences

### Positive

- Peak memory is **bounded and predictable** — no heap growth as utterance length
  varies, because every large allocation is made once at startup.
- Headroom is explicitly quantified, so a new model can be assessed against a
  number rather than guessed at.

### Negative / risk

- The budget is estimate-driven until Phase-4 on-device measurement; the Opus-MT
  decoder line is known to overstate reality by 4–5×.

## References

- [ADR-007](ADR-007-translation-service.md) — TranslationService (parent record)
- [ADR-013](ADR-013-persistent-model-residency.md) — Persistent model residency
- [ADR-014](ADR-014-max-size-kv-cache-preallocation.md) — Max-size KV cache pre-allocation
- [ADR-015](ADR-015-npu-cpu-zero-copy-ion.md) — NPU→CPU zero-copy via ION
- [ADR-008](ADR-008-dual-zipformer-asr.md) — Dual Zipformer ASR (revised the ASR rows)
