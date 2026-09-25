# ADR-007: TranslationService — two-mode foreground service

## Status

Accepted

## Date

2026-07-26

## Deciders

Kavi team

## Context

ADR-001 through ADR-006 fix the shape of the system (offline-first, phone form
factor, CPU baseline with NPU deferred) and the runtime/runner strategy. They do
**not** say how the pipeline stages (denoise → ASR → MT → TTS) are composed,
orchestrated, and exposed to the Android app for production use — as opposed to
the batch evaluation runner in ADR-006.

Two operational scenarios must be supported:

- **OneDevice (WalkieTalkie)** — a single device with two speakers passing the
  phone back and forth.
- **PeerToPeer (Conversation)** — two devices, one speaker each.

Both must share infrastructure so the pipeline is implemented once.

> **Split note (2026-09-25):** this record originally held eleven decisions
> (`Decision 1` … `Decision 11`). It has been split into one decision per record
> — see [ADR-013](ADR-013-persistent-model-residency.md) through
> [ADR-022](ADR-022-energy-vad.md) — and now holds only the service-layer
> decision. Its file-level status previously read *"Superseded by ADR-008"*,
> which was wrong: ADR-008 supersedes only the former `Decision 6`
> ([ADR-017](ADR-017-dual-asr-language-detection.md)) and modifies
> [ADR-014](ADR-014-max-size-kv-cache-preallocation.md) /
> [ADR-016](ADR-016-memory-budget.md). The remaining decisions were, and are,
> **Accepted**.

## Decision

Kavi exposes a single Android `Service` that hosts the full inference pipeline in
two operational modes, sharing all componentry.

### Mode A: OneDevice (WalkieTalkie)

- Single device, two speakers pass the phone back and forth.
- One `AudioRecord` capture, one `AudioTrack` playback.
- Push-to-talk or VAD-triggered utterance segmentation.
- No external hardware; entirely self-contained.

### Mode B: PeerToPeer (Conversation)

- Two devices paired over BLE 5.2+, each handling one speaker.
- Each device captures its own speaker's audio, processes denoise → ASR → MT →
  TTS locally, and sends the translated text to the peer device (which
  synthesises it locally).
- Optional bone-conduction headset or earbuds for improved SNR on the capture
  side.

### Shared infrastructure (both modes)

| Component | Role |
| --- | --- |
| `TranslationService` | Android `Service` with `FOREGROUND_SERVICE` + `microphone` foreground service type; holds all model references, manages `PowerManager.WakeLock` |
| `Recorder` | `AudioRecord` PCM float, 16 kHz mono, circular buffer; VAD (amplitude threshold + speech timeout) built in or composed with a lightweight model |
| `AudioTrack` | Playback of synthesised audio |
| Model instances | Loaded once in `TranslationService.onCreate()`, never released during the session |

The **model-lifecycle invariant** that follows from this — one service instance
per process holding all model state, with no lazy loading and no on-demand model
swapping — is decided in
[ADR-013](ADR-013-persistent-model-residency.md).

## Consequences

### Positive

- **Two-mode service** covers both contest scenarios (one-device walkie-talkie
  and two-device conversation) with shared infrastructure.

### Negative / risk

- The service is process-wide state: an OS-initiated kill takes the whole
  pipeline down and forces a cold start (see
  [ADR-013](ADR-013-persistent-model-residency.md)). Mitigation: foreground
  notification keeps the service alive during active use.

## References

- [ADR-001](ADR-001-offline-first-on-device-architecture.md) — Offline-first, on-device architecture
- [ADR-002](ADR-002-target-platform.md) — Target platform (Snapdragon 8 Gen 2 / Android 16 / Hexagon NPU)
- [ADR-003](ADR-003-hexagon-runtime.md) — Hexagon runtime / compiler strategy
- [ADR-005](ADR-005-qnn-isnan-workaround.md) — QNN conversion workarounds (encoder-on-NPU, decoder-on-CPU split)
- [ADR-006](ADR-006-native-on-device-runner.md) — Android runner architecture (batch evaluation framework)
