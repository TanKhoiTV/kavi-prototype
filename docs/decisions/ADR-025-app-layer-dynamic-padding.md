# ADR-025: App-layer dynamic padding and trimming for fixed shapes

## Status

Accepted

## Date

2026-07-22

## Deciders

Kavi team

## Context

The HTP requires **fixed shapes** — no dynamic shapes are permitted (see
[ADR-003](ADR-003-hexagon-runtime.md)). The QNN context binaries are compiled for a
fixed duration `T_FIXED`, whereas real utterances vary in length. Something must
reconcile the two, and it cannot be the NPU.

Without handling, fixed-shape truncation degrades TTS output — the PR #73 review
flagged this as an **MOS degradation** risk.

> **Canonical home note:** this decision was recorded **twice** — as
> `ADR-005 Decision 5` ("Android runner must handle dynamic padding") and as a
> separate `## Decision` section in
> [ADR-006](ADR-006-native-on-device-runner.md) ("App-layer dynamic padding").
> Both describe the same rule. It now lives here, in the runner record's family,
> as a single decision; the duplicate text has been folded in and the
> [ADR-005](ADR-005-qnn-isnan-workaround.md) tombstone points here.

## Decision

The **app layer** pads inputs to `T_FIXED` before inference and trims outputs
afterwards. The QNN graph itself never sees a dynamic shape.

1. **Before the NPU:** pad mel spectrograms / input tensors to `T_FIXED`.
2. **After the NPU:** trim the output to the actual duration, based on phoneme
   count.
3. **Silence handling:** add or trim silence padding so playback timing stays
   natural (MOS preservation).

## Alternatives considered

- **Dynamic-shape graphs** — not available on the HTP: the runtime silently rejects
  unquantized or dynamic-shaped graphs ([ADR-003](ADR-003-hexagon-runtime.md)).
- **Compile a graph per utterance length** — several context binaries, larger APK,
  slower switching, and no benefit once padding is done correctly.
- **Truncate in the model** — rejected: silent truncation is exactly the MOS
  degradation this decision exists to prevent.

## Consequences

### Positive

- Fixed-shape graphs are usable with variable-length utterances, at negligible
  cost.
- Output timing stays natural (no clipped or oddly-timed speech).

### Negative / risk

- Padding/trimming logic lives in app code and must be correct per stage — TTS
  timing depends on the trim being right, not just the pad.
- Compute is spent on padded frames that carry silence.

## References

- [ADR-003](ADR-003-hexagon-runtime.md) — Hexagon runtime (no dynamic shapes)
- [ADR-006](ADR-006-native-on-device-runner.md) — Native on-device runner
- [ADR-005](ADR-005-qnn-isnan-workaround.md) — QNN conversion workarounds (original `Decision 5` location)
- PR #73 comment from @winterSolstice25 — documented the padding/trimming requirement
