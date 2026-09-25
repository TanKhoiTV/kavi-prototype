# ADR-024: Piper TTS stays on CPU

## Status

Accepted

## Date

2026-07-22

## Deciders

Kavi team

## Context

Alongside the Whisper decoder (see [ADR-005](ADR-005-qnn-isnan-workaround.md)),
the Piper TTS graph failed QNN conversion:

```text
KeyError: 'ERROR_WEIGHTS_MISSING_KEY: Expected a static initializer for value scales'
```

The Piper ONNX has a **cyclic graph with dynamic scales** that cannot be statically
initialised — a topology problem, not a missing-op problem.

> **Split note:** extracted from the former `ADR-005 Decision 3`. It also absorbs
> the Piper epsilon guard formerly recorded as `ADR-005 Decision 4` and as a
> separate `## Decision` section in
> [ADR-006](ADR-006-native-on-device-runner.md) — a one-line numeric guard, not an
> independent architectural decision.

## Decision

**Keep Piper on CPU. Skip QNN conversion for TTS.**

### Rationale

- The Piper ONNX has a cyclic graph that QAIRT cannot handle.
- The surgery script (`patch_piper_onnx.py`) **did not fully fix** the topology.
- Piper is already fast on CPU (RTF 0.06–0.22 from baseline).
- TTS is **not the bottleneck** in the pipeline.

**Action taken:** TTS excluded from the QNN conversion path.

### Consequence: Piper surgery epsilon

Should the surgery ever need to be re-run, **add an epsilon to the denominator**:

```python
scale = T_FIXED / (ReduceSum(raw_durations) + 1e-5)
```

This prevents division by zero for empty or silent inputs. It is a guard on a code
path that this decision renders dormant — not a separate decision.

## Alternatives considered

- **Rewrite the Piper graph to remove the cycle** — attempted via
  `patch_piper_onnx.py`; the routine did not fully fix the topology, and the
  remaining benefit did not justify further surgery given Piper's CPU RTF.
- **Run TTS on the NPU with a different synthesiser** — out of scope for v1; the
  TTS model selection is recorded in [ADR-009](ADR-009-supertonic-tts-v1.md).

## Consequences

### Positive

- Piper stays fast on CPU anyway; no engineering effort spent on a non-bottleneck.
- Simpler conversion pipeline (only encoders need QNN).

### Negative / risk

- TTS cannot benefit from NPU acceleration on this path; if a future TTS model is
  much heavier, this decision is the one to revisit.

## References

- [ADR-005](ADR-005-qnn-isnan-workaround.md) — `IsNaN` conversion workaround
- [ADR-023](ADR-023-decoder-on-cpu.md) — Encoder on NPU, decoder on CPU
- [ADR-009](ADR-009-supertonic-tts-v1.md) — v1 TTS decision (supersedes the Piper default)
- `docs/reference/phase-4-qnn-plan.md` §3.3 — Piper conversion section, deferred by this record
