# ADR-019: QNN runtime bundling — jniLibs roster and version lock

## Status

Accepted — ASR entries superseded 2026-07-27 by [ADR-027](ADR-027-asr-cpu-only.md)

## Date

2026-07-26

## Deciders

Kavi team

## Context

The QNN runtime is **preinstalled** on the target device but is **not** listed in
`/vendor/etc/public.libraries.txt` or `/system/etc/public.libraries.txt`, so a
third-party app cannot `dlopen` it directly (linker-namespace/SELinux). The runtime
must therefore be **bundled in the APK** — which the Qualcomm AI Stack License
§1(iv) permits (see [ADR-030](ADR-030-qairt-runtime-redistribution.md)).

Bundling requires an exact roster: which shared objects, which compiled context
binaries, and which version they must match. A mismatch causes *silent* inference
failure rather than a clean error.

> **Split note:** extracted from the former `ADR-007 Decision 8`. The context
> binary and CPU-model rosters below were subsequently changed by
> [ADR-027](ADR-027-asr-cpu-only.md) — see the revision note.

## Decision

Bundle the QNN runtime shared objects and compiled context binaries in
`android/app/src/main/jniLibs/arm64-v8a/`, pinned to one QAIRT SDK version.

### Required .so files

| File | Purpose |
| --- | --- |
| `libQnnHtp.so` | CPU-side QNN API (2.0 MB) |
| `libQnnHtpV73Stub.so` | Hexagon NPU firmware for HTP v73 (444 KB) |
| `libQnnHtpV73CalculatorStub.so` | NPU calculator firmware (6.4 KB) |
| `libQnnHtpPrepare.so` | HTP preparation/initialisation |
| `libQnnSystem.so` | System context manager |
| `libQnnCpu.so` | CPU fallback backend |
| `libQnnGpu.so` | GPU fallback backend (included for future-proofing; the v1 fallback chain is NPU→CPU only — see [ADR-020](ADR-020-pipeline-concurrency.md)) |
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

QAIRT SDK version must match the device runtime: **2.31.0.250130** ↔ **qnn-2.31**
↔ **HTP v73**. Mismatch causes silent inference failure.

### Revision — 2026-07-27 ([ADR-027](ADR-027-asr-cpu-only.md))

The **ASR entries are withdrawn from the NPU/asset rosters**: Zipformer transducer
(RNN-T) has no QNN path, and ASR runs CPU-only for v1. In practice this means:

- `whisper_encoder_v73.bin` is **not shipped**; the dual Zipformer models load via
  sherpa-onnx on CPU ([ADR-008](ADR-008-dual-zipformer-asr.md)).
- `whisper_decoder.onnx` is replaced by the two sherpa-onnx Zipformer model sets.
- **`opusmt_encoder_v73.bin` + `opusmt_decoder.onnx` remain**, and are now the sole
  reason the QNN/NPU path exists in v1.

The `.so` roster and the version lock are unchanged.

## Consequences

### Positive

- **jniLibs roster and version locks are documented**, reducing integration risk for
  new team members.
- Bundling is licence-clean and makes the APK self-contained and offline
  ([ADR-030](ADR-030-qairt-runtime-redistribution.md)).

### Negative / risk

- **Version lock on QAIRT SDK** — `qnn-2.31` / HTP v73. An OS update that ships a
  different Hexagon firmware version breaks inference until the SDK version is
  matched.
- Carrying the GPU backend for future-proofing costs APK size for a fallback tier
  v1 never uses.

## References

- [ADR-007](ADR-007-translation-service.md) — TranslationService (parent record)
- [ADR-003](ADR-003-hexagon-runtime.md) — Hexagon runtime / compiler strategy
- [ADR-027](ADR-027-asr-cpu-only.md) — ASR stays CPU-only (revised the ASR roster)
- [ADR-030](ADR-030-qairt-runtime-redistribution.md) — QAIRT runtime redistribution (licence basis)
- [ADR-011](ADR-011-android-asset-provenance-delivery.md) — Asset provenance & delivery
- `docs/reference/phase-4-qnn-plan.md` — verified converter commands
