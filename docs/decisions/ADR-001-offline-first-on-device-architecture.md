# ADR-001: Offline-first, on-device architecture

## Status

Accepted

## Date

2026-07-14

## Deciders

Kavi team

## Context

Kavi is our entry to the OneVoice AI Challenge: a real-time speech-to-speech
translator for Vietnamese ↔ English (later Chinese and Korean), built to run on
a portable device (target: Snapdragon 8 Gen 2 Android phone) for workers in
factories, construction sites, and logistics hubs.

The contest imposes hard constraints that drive the architecture:

- **No internet at runtime → disqualification.** Any network dependency during
  testing eliminates the entry.
- **Turnaround latency** (end of speech → start of audio synthesis) must be
  **< 2.0 s**; exceeding it incurs significant point deductions.
- **Real-Time Factor (RTF) < 1.0** — the pipeline must keep pace with live speech.
- The target environments are **noisy, hands-busy, and low-connectivity**, so a
  solution that assumes a network is not merely non-compliant, it is unusable.

We must decide where the translation pipeline (capture → denoise → ASR → MT →
TTS → playback) executes.

## Decision

Kavi runs **100% on-device, offline-first**. Every stage of the pipeline —
audio capture, denoising, automatic speech recognition (ASR), machine
translation (MT), and text-to-speech (TTS) — executes locally on the device's
own compute (Snapdragon CPU/NPU). There are **no runtime network calls, no
cloud model inference, and no external API dependencies**.

The system is structured as a single local pipeline with a hard
**0 network egress** invariant.

## Alternatives Considered

### Cloud-based (full pipeline in the cloud)

- **Pros:** access to the largest models; trivial model updates; no on-device
  compute budget.
- **Cons:** violates the contest's no-internet rule (→ disqualification);
  round-trip latency degrades responsiveness; fails exactly in the
  low-connectivity environments we target; audio leaves the device.
- **Rejected:** disqualifies from the contest and contradicts the problem
  statement.

### Hybrid (on-device with cloud fallback / cloud assist)

- **Pros:** can use larger models when connected; graceful degradation.
- **Cons:** any code path that *can* reach the network is unsafe under the
  contest's binary connectivity rule (any dependency → DQ); adds fallback
  complexity and ambiguous offline behavior.
- **Rejected:** the connectivity rule is binary, so a hybrid that can call the
  cloud is a disqualification risk; offline operation is also the actual
  product goal, not a fallback.

### Edge server / local gateway (processing on a nearby box)

- **Pros:** more compute than a phone; still "local" in the networking sense.
- **Cons:** not a standalone portable device; the contest requires a device
  workers carry; adds infrastructure the target settings do not have.
- **Rejected:** fails the "standalone AI translation device" requirement.

## Consequences

- **Model selection is now constrained** to models small enough to run on-device
  within the latency budget (RTF < 1.0, turnaround < 2.0 s). Specific choices
  (ASR / MT / TTS) are captured in a separate ADR.
- **No runtime telemetry or updates over the network.** Analytics, if any, must
  be queued locally; model and code updates require redeployment, not server
  pushes.
- **Testing must assert zero network egress** as a release gate.
- **Privacy benefit:** raw audio never leaves the device.
- **The 2.0 s budget shapes the whole pipeline** — it defines how the latency
  budget splits across capture, denoise, ASR, MT, and TTS (a performance-budget
  spec will track this).
- This decision is **stable and foundational**; later ADRs build on it rather
  than revisiting it.
