# ADR-005: Strip the unsupported `IsNaN` op when converting to QNN

## Status

Accepted

## Date

2026-07-22

## Deciders

Kavi team

## Context

Converting ONNX models to QNN context binaries for Snapdragon 8 Gen 2 (HTP v73)
with QAIRT SDK 2.31.0.250130, the Whisper decoder failed outright:

```text
KeyError: 'No translation registered for op type onnx_isnan.'
```

The Whisper decoder ONNX graph uses `IsNaN` for beam-search NaN detection, and
**the HTP does not implement it**. `IsNaN`/`IsInf` are the only unsupported ops
encountered; the rest of the ops used by the pipeline are confirmed supported:

**Supported on HTP v73 (QAIRT 2.31):** `ElementWiseSelect` (Where) · `TopK` ·
`NonZero` · `Gather`/`GatherND` · `Scatter`/`ScatterND` · `MatMul`/`Gemm` ·
`LayerNorm` · `Reshape`/`Transpose`/`Concat` · `ReduceSum`/`ReduceMean` ·
`Softmax`/`LogSoftmax`

**Not supported:** `IsNaN` · `IsInf`

> **Split note (2026-09-25):** this record previously held five decisions
> (`Decision 1` … `Decision 5`). It has been split into one decision per record:
> [ADR-023](ADR-023-decoder-on-cpu.md) (decoder on CPU),
> [ADR-024](ADR-024-piper-tts-on-cpu.md) (Piper on CPU, absorbing the Piper
> epsilon guard), and [ADR-025](ADR-025-app-layer-dynamic-padding.md) (app-layer
> padding, whose canonical home is the runner record). It now holds only the
> `IsNaN` conversion workaround.

## Decision

Replace the `IsNaN`-based NaN guard with an equivalent expressed in supported ops,
or remove it where inputs are provably valid.

**Instead of:** `IsNaN(x) → bool`

**Use:** `Where(x != x, zero, x)` — equivalently `ElementWiseEqual` +
`ElementWiseSelect` — or simply remove the NaN guards if inputs are guaranteed
valid.

For beam search the NaN check is a **safety guard**, so two options are viable:

1. Remove the `IsNaN` nodes entirely (fastest).
2. Replace them with `x != x` using `ElementWiseEqual` + `ElementWiseSelect`.

**Action taken:** `bench/qnn/patch_whisper_decoder.py` strips the `IsNaN` nodes
from the ONNX graph (done, PR #75).

## Alternatives considered

- **Keep `IsNaN` and run the decoder on CPU** — subsumed by
  [ADR-023](ADR-023-decoder-on-cpu.md), which removes the decoder from the NPU
  path altogether and makes this patch a portability insurance policy rather than
  a load-bearing requirement.
- **`IsInf` guards** — likewise unsupported; the same treatment applies if ever
  encountered.

## Consequences

### Positive

- Unblocks NPU conversion of graphs that contain `IsNaN`, using only confirmed
  ops.
- Fewer unsupported ops to work around in the rest of the pipeline.

### Negative / risk

- Removing a NaN guard relies on inputs being valid in practice; the
  `Where`-based replacement is the safe variant where that assumption is not
  acceptable.

## References

- [ADR-003](ADR-003-hexagon-runtime.md) — Hexagon runtime / compiler strategy
- [ADR-023](ADR-023-decoder-on-cpu.md) — Decoder on CPU (the larger workaround)
- [ADR-024](ADR-024-piper-tts-on-cpu.md) — Piper TTS on CPU (the other conversion failure)
- `docs/reference/phase-4-qnn-plan.md` — Phase-4 conversion plan
