# ADR-026: Calibration must use real data only

## Status

Accepted

## Date

2026-07-22

## Deciders

Kavi team

## Context

QNN quantization needs a calibration set to derive activation ranges. A convenient
shortcut is to synthesise random tokens when no real corpus is on hand — but random
inputs produce **unrepresentative activation distributions**, degrading quantization
accuracy in ways that only show up later as unexplained quality loss in a converted
model.

The PR #73 review flagged this as a correctness hazard for the conversion pipeline.

> **Split note:** extracted from the former `ADR-006 Decision: Calibration with real
> data only`.

## Decision

Calibrate **only with real data**, and fail loudly rather than silently degrading.

- Use **FLEURS parquets** for calibration (available locally).
- Fall back to **GOLD_SET** offline data if FLEURS is missing.
- **Never** use random synthetic tokens for calibration.
- **Raise `ValueError`** if no real calibration data is available.

**Action:** the calibration fallback raises `ValueError` instead of substituting
synthetic tokens.

## Alternatives considered

- **Synthetic random tokens as a fallback** — rejected: they degrade quantization
  quality invisibly and violate the "fail loudly" principle for a build-time step.
- **Skip calibration when no corpus is present** — rejected: silently produces a
  worse model rather than a clear error.

## Consequences

### Positive

- Quantized models reflect real activation distributions.
- A missing corpus fails fast at build time instead of surfacing as a quality
  regression on device.

### Negative / risk

- Calibration requires the FLEURS corpus (or GOLD_SET) to be present, so the
  conversion step is no longer self-contained on a bare checkout.

## References

- [ADR-006](ADR-006-native-on-device-runner.md) — Native on-device runner
- [ADR-003](ADR-003-hexagon-runtime.md) — Hexagon runtime (quantization requirement)
- `docs/reference/phase-4-qnn-plan.md` — Phase-4 conversion plan
