# ADR-005: QNN Conversion Workarounds

**Date:** 2026-07-22
**Status:** Proposed
**Deciders:** Kavi team
**Relates to:** ADR-003 (Hexagon runtime), Phase 4 QNN conversion

## Context

We're converting ONNX models to QNN context binaries for Snapdragon 8 Gen 2 (HTP v73) using QAIRT SDK 2.31.0.250130. Two models failed conversion:

### Failure 1: Whisper decoder — unsupported `IsNaN` op

```
KeyError: 'No translation registered for op type onnx_isnan.'
```

The Whisper decoder ONNX graph uses `IsNaN` for beam search NaN detection.

### Failure 2: Piper TTS — cyclic graph + dynamic scales

```
KeyError: 'ERROR_WEIGHTS_MISSING_KEY: Expected a static initializer for value scales'
```

The Piper ONNX has a cyclic graph with dynamic scales that can't be statically initialized.

## Supported ops on HTP v73 (QAIRT 2.31)

Key ops confirmed supported:

- `ElementWiseSelect` (Where) ✅
- `TopK` ✅
- `NonZero` ✅
- `Gather` / `GatherND` ✅
- `Scatter` / `ScatterND` ✅
- `MatMul` / `Gemm` ✅
- `LayerNorm` ✅
- `Reshape` / `Transpose` / `Concat` ✅
- `ReduceSum` / `ReduceMean` ✅
- `Softmax` / `LogSoftmax` ✅

**NOT supported:**

- `IsNaN` ❌
- `IsInf` ❌

## Decision 1: Replace IsNaN with Where-based NaN detection

**Instead of:** `IsNaN(x) → bool`
**Use:** `Where(x != x, zero, x)` or simply remove NaN guards if inputs are guaranteed valid.

For beam search, the NaN check is a safety guard. If we guarantee valid inputs (no NaN in practice), we can:

1. Remove the IsNaN nodes entirely (fastest)
2. Replace with `x != x` using `ElementWiseEqual` + `ElementWiseSelect`

**Action:** Write `bench/qnn/patch_whisper_decoder.py` to strip IsNaN nodes from the ONNX graph.

## Decision 2: Run decoder on CPU (recommended)

**Architecture:** Encoder on NPU, decoder on CPU.

Rationale:

- Encoder is compute-bound (matrix multiplications) → benefits from NPU
- Decoder is memory-bound (embedding lookups, small matmuls) → less NPU benefit
- Decoder has unsupported ops (IsNaN, potentially others)
- Autoregressive loops are hard to optimize on fixed-function hardware
- This is a common pattern in hybrid NPU deployments (e.g., Qualcomm AI Hub models)

**Action:** Update QNN adapter stubs to reflect encoder-on-NPU, decoder-on-CPU architecture.

## Decision 3: Piper TTS — run on CPU

**Rationale:**

- Piper ONNX has cyclic graph that QAIRT can't handle
- The surgery script (`patch_piper_onnx.py`) didn't fully fix the topology
- Piper is already fast on CPU (RTF 0.06–0.22 from baseline)
- TTS is not the bottleneck in the pipeline

**Action:** Keep Piper on CPU. Skip QNN conversion for TTS.

## Decision 4: Fix division-by-zero in Piper surgery

If we ever need to re-run the surgery, add epsilon to the denominator:

```python
scale = T_FIXED / (ReduceSum(raw_durations) + 1e-5)
```

## Decision 5: Android runner must handle dynamic padding

The QNN graph uses fixed shapes (`T_FIXED`), but the Android app must:

1. Pad input to `T_FIXED` before pushing to NPU
2. Trim output after pulling from NPU
3. Handle silence padding/trimming for natural timing

This is documented in PR #73 comment from @winterSolstice25.

## Revised architecture

```
┌─────────────────────────────────────────────────────┐
│ Android Device (Snapdragon 8 Gen 2)                 │
│                                                     │
│  ┌─────────────┐     ┌──────────────────────────┐  │
│  │ Whisper      │     │ Opus-MT                  │  │
│  │ Encoder      │     │ Encoder (QNN/NPU)        │  │
│  │ (QNN/NPU)   │     │ Decoder (CPU/CT2)        │  │
│  └─────────────┘     └──────────────────────────┘  │
│                                                     │
│  ┌─────────────┐                                    │
│  │ Piper TTS   │                                    │
│  │ (CPU only)  │                                    │
│  └─────────────┘                                    │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ Instrumented Test Runner (Kotlin)            │  │
│  │ - Load manifest                              │  │
│  │ - Run pipeline                               │  │
│  │ - Measure latency/RTF/RAM                    │  │
│  │ - Write results JSON                         │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Consequences

### Positive

- Simpler conversion pipeline (only encoders need QNN)
- Fewer unsupported ops to deal with
- Piper stays fast on CPU anyway
- Clear separation of concerns

### Negative

- Decoder won't benefit from NPU acceleration
- Need to implement CPU decoder in Android app
- Two inference backends to manage

### Risks

- Encoder-only NPU may not meet RTF < 1.0 gate (need to measure)
- CPU decoder adds latency to turnaround time

## Follow-up actions

| # | Task | Owner | Effort |
| --- | ------ | ------- | -------- |
| 1 | Write `patch_whisper_decoder.py` to strip IsNaN | Worker | 2 hrs |
| 2 | Update QNN adapter stubs for encoder-only architecture | Worker | 1 hr |
| 3 | Export Opus-MT encoder only (skip decoder) | Worker | 1 hr |
| 4 | Convert Opus-MT encoder → QNN | Manual | 1 hr |
| 5 | Build Android runner with CPU decoder fallback | Worker | 4 hrs |
| 6 | On-device verification | Manual | 4 hrs |
