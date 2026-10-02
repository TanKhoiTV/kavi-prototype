# ADR-006: Native on-device runner (no ADB bridge)

## Status

Accepted

## Date

2026-07-22

## Deciders

Kavi team, @winterSolstice25 (reviewer)

## Context

The initial Android runner design had the host **micromanage inference over ADB**,
pushing data per inference step. A PR #73 review identified this as an
architectural problem:

- **ADB bridge I/O overhead** — host-driven per-token round-trips inflate measured
  latency, corrupting the very numbers the runner exists to produce.

Runner results must be trustworthy enough to close the tech-stack
parameters tracked in the [open-parameters register](README.md#open-parameters), and must demonstrate the offline invariant
([ADR-001](ADR-001-offline-first-on-device-architecture.md)) rather than assume it.

> **Split note (2026-09-25):** this record previously held four decisions. It has
> been split into one decision per record: the runner (this file),
> [ADR-025](ADR-025-app-layer-dynamic-padding.md) (app-layer padding/trimming) and
> [ADR-026](ADR-026-real-data-calibration.md) (calibration data). The Piper epsilon
> guard it also recorded is a consequence of
> [ADR-024](ADR-024-piper-tts-on-cpu.md).

## Decision

Replace host-driven inference with a **standalone Android instrumented test that
runs the batch internally**.

**Instead of:** host pushes data per inference step via ADB
**Use:** standalone Android instrumented test that runs the batch internally

### Architecture

```text
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
│  │     - TTS (CPU)                              │  │
│  │     - Measure latency_ns, peak_rss_bytes     │  │
│  │ - Write results to /sdcard/Android/data/...  │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Key principles

1. **Single push, single pull** — the host pushes all inputs once and pulls all
   outputs once.
2. **Internal timing** — latency is measured inside the app, not via ADB
   round-trips.
3. **Zero network assertion** — a `NetworkMonitor` verifies flight mode before the
   test.
4. **Batch processing** — the manifest reader processes all items in one run.

## Consequences

### Positive

- **Accurate latency measurement** — no ADB overhead in the measured path.
- **Clean separation** of host and device responsibilities.
- **Reproducible results** via internal timing.
- **Proper offline verification** — the zero-network assertion is mechanical.

### Negative / risk

- More complex Android test code.
- Two build targets to maintain (host scorer + Android instrumentation test).
- Requires dynamic-shape handling in the app layer, decided separately in
  [ADR-025](ADR-025-app-layer-dynamic-padding.md).

## Follow-up actions

| # | Task | Owner | Effort | Status |
| --- | ------ | ------- | -------- | -------- |
| 1 | Update QNN adapter stubs with correct architecture comments | Worker | 1 hr | Pending |
| 2 | Build Android instrumented test runner | Worker | 6 hrs | Pending |
| 3 | On-device verification | Manual | 4 hrs | Pending |

## References

- PR #73 review comment from @winterSolstice25
- [ADR-025](ADR-025-app-layer-dynamic-padding.md) — App-layer dynamic padding/trimming
- [ADR-026](ADR-026-real-data-calibration.md) — Calibration with real data only
- [ADR-005](ADR-005-qnn-isnan-workaround.md) — QNN conversion workarounds
