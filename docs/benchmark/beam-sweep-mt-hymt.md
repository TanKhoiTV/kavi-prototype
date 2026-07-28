# Beam Sweep Report — Hy-MT vi→en

**Status:** ❌ Skipped — CTranslate2 conversion not feasible.

**Model:** Tencent HY-MT1.5-1.8B  
**Candidate ID:** N/A (no CT2 candidate created)  
**Reason:** Custom `HunYuanDenseV1` architecture uses `dynamic` RoPE scaling and QK-Norm, neither supported by CTranslate2's converter. See [`docs/benchmark/hymt-ct2-blockers.md`](hymt-ct2-blockers.md) for full technical details.

---

## Attempted Approach

Following `docs/benchmark/beam-sweep-guide-v2.md` Section 1c, conversion was attempted via:

```bash
uv run ct2-transformers-converter \
  --model tencent/HY-MT1.5-1.8B \
  --output_dir models/hy-mt1.5-1.8b-ct2-int8 \
  --quantization int8
```

Three blockers were encountered (see blockers doc for full analysis):

| # | Blocker | Severity |
|---|---------|----------|
| 1 | `HunYuanDenseV1Config` not in CT2 converter registry | Fatal |
| 2 | `dynamic` RoPE scaling type not implemented in CT2 | Fatal |
| 3 | QK-Norm weights silently dropped under LLaMA config | Degradation |

---

## Fallback Evaluated

HF Transformers (bfloat16, CPU) works but at ~19 s/inference — 19× slower than CT2-optimized models. Sweep data would not be comparable with Opus-MT and M2M-100 (both CT2). Not pursued.

---

## Revisit Criteria

- CTranslate2 adds `dynamic` RoPE scaling support in a future release
- OR on-device runner (ADR-006) supports direct HF inference with hardware acceleration (GPU/NPU)
- OR the quality gap vs M2M-100 is deemed large enough to justify the runtime penalty