# ADR-011: Android Model Asset Provenance & Delivery

**Status:** Accepted
**Date:** 2026-08-05
**Deciders:** Kavi team
> **Note (2026-08-14):** The decision below stands unchanged. One contextual
> detail is now stale: `kavi-android` is **no longer a submodule** of
> `kavi-prototype` — it was unregistered so the public prototype repo does not
> carry a gitlink to a private repository. `kavi-android` remains the sole owner
> of on-device artifacts, exactly as decided here.
**Relates to:** ADR-002 (target platform), ADR-006 (Android runner), ADR-007
Decision 8 (QNN bundling), ADR-008 (ASR assets), ADR-009 (TTS assets),
`prototype/.gitignore` (`models/qnn/*`)

## Context

The on-device app (`android/` = `kavi-android` submodule) needs a fixed set of
inference artifacts: sherpa-onnx Zipformer models (ADR-008), Supertonic TTS
bundle (ADR-009), the Opus-MT ONNX decoder (CPU), and — once built — the
Opus-MT encoder HTP v73 context binary (ADR-007 D4/D8).

Host-side conversion outputs under `prototype/models/qnn/*` are **gitignored and
regenerable** (`.gitignore` line 20, commit 3502156) and can only be reproduced
with the QAIRT SDK (2.31.0.250130, not installed on every host). Treating them
as deliverables breaks fresh clones. The on-device HTP v73 context binary does
**not exist yet** — it is a Windows-host `qnn-context-binary-generator` output
(`reference/phase-4-qnn-plan.md` §8). The contest grading requires a buildable,
fully offline APK with no runtime network.

## Decision

1. **Commit every on-device inference artifact inside `kavi-android`**
   (`app/src/main/assets/` for models/context binaries; `jniLibs/` for `.so`),
   alongside a `SHA256SUMS` manifest committed in the same repo.
2. **Never vendor from `prototype/models/qnn/*`** — host outputs are
   regenerable intermediates, not deliverables.
3. **Record provenance per artifact**: QAIRT version (must be 2.31.0.250130 /
   HTP v73), converter invocation, source ONNX hash — in `kavi-android`'s model
   README (mirroring `models/qnn/README.md`).
4. **`android/scripts/fetch-models.sh`** downloads external models (Zipformer,
   Supertonic, sherpa-onnx libs), verifies SHA-256, and places them under
   assets with the manifest entry — preserving the offline invariant (no
   runtime network).
5. Re-conversion (SDK/model change) updates the manifest + provenance record,
   never patches binaries in place.

## Consequences

- **Positive:** always-buildable APKs on any host; reproducible contest
  submission; QAIRT version lock enforced mechanically; offline invariant
  preserved.
- **Negative:** `kavi-android` grows large (models committed); re-conversion
  workflow required on SDK/model change; manifest drift possible if artifacts
  are hand-placed — the fetch script is the only supported path.

## References

- ADR-007 Decision 8 (QNN jniLibs roster + version lock)
- ADR-008 (Dual Zipformer assets), ADR-009 (Supertonic bundle)
- `reference/phase-4-qnn-plan.md` §8 (verified converter commands)
- `prototype/.gitignore` (`models/qnn/*`, commit 3502156)
