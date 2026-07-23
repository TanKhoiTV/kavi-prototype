# ADR-006: Android Runner Architecture

**Date:** 2026-07-22
**Status:** Accepted
**Deciders:** Kavi team, @winterSolstice25 (reviewer)
**Relates to:** ADR-005 (QNN conversion), Phase 4 Android runner

## Context

PR #73 review identified critical architectural issues with the proposed Android runner design:

1. **ADB bridge I/O overhead** — Host micromanaging inference via ADB per-token would inflate latency
2. **Division by zero risk** — Piper surgery scale factor needs epsilon
3. **MOS degradation** — Fixed T_FIXED requires app-layer dynamic padding/trimming
4. **Calibration fallback** — Random synthetic tokens degrade quantization

## Decision: Native on-device runner (no ADB bridge)

**Instead of:** Host pushes data per inference step via ADB
**Use:** Standalone Android instrumented test that runs batch internally

### Architecture

```
┌─────────────────────────────────────────────────────┐
│ Host (Ubuntu 22.04)                                 │
│                                                     │
│  1. adb push eval_manifest_v1.json                  │
│  2. adb push model assets                           │
│  3. adb shell am instrument -w com.kavi.app.test/   │
│  4. adb pull results/run_results_android.json       │
│  5. uv run python -m bench.score --from-android     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Android Device (Snapdragon 8 Gen 2)                 │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ InstrumentedTest (Kotlin)                    │  │
│  │ - ManifestReader.parse("eval_manifest_v1.json") │  │
│  │ - For each item:                             │  │
│  │     - QnnModelLoader.run Encoder (NPU)       │  │
│  │     - CPU fallback Decoder                    │  │
│  │     - Piper TTS (CPU)                        │  │
│  │     - Measure latency_ns, peak_rss_bytes     │  │
│  │ - Write results to /sdcard/Android/data/...  │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Key principles

1. **Single push, single pull** — Host pushes all inputs once, pulls all outputs once
2. **Internal timing** — Latency measured inside the app (not via ADB round-trips)
3. **Zero network assertion** — NetworkMonitor verifies flight mode before test
4. **Batch processing** — Manifest reader processes all items in one run

## Decision: Epsilon for Piper surgery

```python
scale = T_FIXED / (ReduceSum(raw_durations) + 1e-5)
```

Prevents division by zero for empty/silent inputs.

## Decision: App-layer dynamic padding

The QNN graph uses fixed shapes, but the app must:

1. **Before NPU:** Pad mel spectrograms to `T_FIXED`
2. **After NPU:** Trim output to actual duration (based on phoneme count)
3. **Silence handling:** Add/trim silence padding for natural timing

This is documented in the patched Piper surgery script comments.

## Decision: Calibration with real data only

- Use FLEURS parquets for calibration (available locally)
- Fall back to GOLD_SET offline data if FLEURS missing
- **Never** use random synthetic tokens for calibration
- Raise `ValueError` if no real calibration data available

## Consequences

### Positive

- Accurate latency measurement (no ADB overhead)
- Clean separation of host/device responsibilities
- Reproducible results (internal timing)
- Proper offline verification (zero network)

### Negative

- More complex Android test code
- Need to handle dynamic shapes in app layer
- Two build targets (host scorer + Android test)

## Follow-up actions

| # | Task | Owner | Effort | Status |
| --- | ------ | ------- | -------- | -------- |
| 1 | Update QNN adapter stubs with correct architecture comments | Worker | 1 hr | Pending |
| 2 | Add epsilon to `patch_piper_onnx.py` | Worker | 30 min | Pending |
| 3 | Fix calibration fallback to raise ValueError | Worker | 30 min | Pending |
| 4 | Build Android instrumented test runner | Worker | 6 hrs | Pending |
| 5 | On-device verification | Manual | 4 hrs | Pending |

## References

- PR #73 review comment from @winterSolstice25
- `docs/adr/005-qnn-conversion-workarounds.md`
- `android/app/src/main/java/com/kavi/app/` (Kotlin loader/runner)
