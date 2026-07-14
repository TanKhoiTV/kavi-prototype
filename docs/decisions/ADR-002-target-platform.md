# ADR-002: Target platform — Snapdragon 8 Gen 2, Android 16, Hexagon NPU

## Status

Accepted

## Date

2026-07-14

## Context

ADR-001 establishes that Kavi runs 100% on-device, offline-first. This ADR
fixes the **target hardware and OS platform** the system is built and optimized
for.

The OneVoice AI Challenge is co-hosted by Qualcomm and targets standalone,
portable Edge-AI translation devices. Key drivers for the platform choice:

- Inference must run with **RTF < 1.0** and **turnaround < 2.0 s** on-device —
  this demands an NPU-class accelerator, not CPU-only.
- The device must be **portable and battery-powered** for factory,
  construction, and logistics use.
- Qualcomm, as co-host, provides the **Qualcomm AI Hub** with models
  pre-optimized (quantized + compiled) for Snapdragon — a strong reason to
  target that silicon.
- The contest allows any portable form factor, but we scope Kavi to a
  **phone-only** reference for easy installation; wearables, headsets, and other
  form factors are explicitly out of scope.

We must choose the SoC, OS, and primary compute path.

## Decision

Kavi targets the **Snapdragon 8 Gen 2** mobile platform running **Android 16**,
with inference **optimized for the Hexagon NPU** and a documented
**GPU → CPU fallback** chain.

- **SoC:** Snapdragon 8 Gen 2 (Kryo CPU + Adreno GPU + Hexagon NPU — **HTP
  v73**) — the **exact target**; newer Snapdragon 8-series parts (8 Gen 3, 8
  Elite) may work as supersets but are **not guaranteed**.
- **OS:** Android 16 (API level 36).
- **Primary compute:** Hexagon NPU (the specific runtime / compiler is deferred
  to ADR-003).
- **Fallback:** if a model/op is not NPU-accelerated, fall back to **Adreno
  GPU**, then **Kryo CPU**, without changing the pipeline.

## Alternatives Considered

### Other Snapdragon tiers

- **Snapdragon 8 Elite / 8 Gen 3** — newer, stronger NPU; may work as supersets
  but not guaranteed — 8 Gen 2 is the exact target we optimize and test against.
- **Snapdragon 7-series / 6-series** — cheaper, but weaker NPU; risks missing
  the latency budget. Rejected as target (may be validated later).
- **Chosen: 8 Gen 2 as the exact target** — balances NPU capability,
  availability, and contest relevance.

### Other mobile silicon

- **MediaTek Dimensity** — capable NPU, but no first-class Qualcomm AI Hub
  optimization and weaker tooling fit for this challenge. Rejected.
- **Apple A-series** — excellent NPU, but not Android; incompatible with the
  Android / Qualcomm contest ecosystem. Rejected.

### Dedicated edge-AI boards

- **Raspberry Pi + Google Coral / Qualcomm RB5** — strong NPU options, but not a
  portable consumer device form factor the contest targets; adds power/size
  constraints. Rejected as the primary target (may inform a fixed-install
  variant later).

### Cloud / connected accelerator

- Rejected by ADR-001 (offline-first; network → DQ).

## Consequences

- **Models must be compiled for Hexagon** (e.g. Qualcomm AI Hub exports compiled
  for Hexagon) to hit the NPU path; a CPU/GPU fallback keeps the pipeline running
  if compilation isn't available for an op.
- **Android 16 (API 36) is the minimum**; we rely on current NNAPI / AIE
  capabilities.
- **Testing must run on real 8 Gen 2 hardware** — emulators do not exercise the
  NPU. A reference device is required for the performance-budget spec.
- **Forward compatibility:** newer Snapdragon 8-series parts may run as
  supersets but are not guaranteed; if they become the test devices we
  re-validate.
- **Hexagon HTP version:** the 8 Gen 2's NPU is **HTP v73** (reference: 8 Gen 3 =
  v75, 8 Elite = v79 / v81); compiled NPU artifacts are version-locked to v73.
- **Tooling / runtime:** the specific runtime / compiler is deferred to
  ADR-003; whatever is chosen must target the Hexagon NPU with the GPU → CPU
  fallback above.
- **Power / battery:** NPU-primary execution is the main lever for staying
  within the device's thermal / power budget during live translation.
