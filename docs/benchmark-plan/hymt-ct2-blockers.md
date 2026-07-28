# Hy-MT (1.8B) — CT2 Conversion Blockers

> Why `tencent/HY-MT1.5-1.8B` cannot be converted to CTranslate2 int8
> with the current toolchain, and what alternatives were explored.

---

## Attempted Approach

Following `docs/benchmark/beam-sweep-guide-v2.md` Section 1c, we attempted:

```bash
uv run ct2-transformers-converter \
  --model tencent/HY-MT1.5-1.8B \
  --output_dir models/hy-mt1.5-1.8b-ct2-int8 \
  --quantization int8 \
  --copy_files tokenizer.json tokenizer_config.json special_tokens_map.json
```

---

## Blocker 1: Unrecognized Architecture

**Error:**
```
ValueError: No conversion is registered for the model configuration
HunYuanDenseV1Config (supported configurations are: BartConfig, ...,
LlamaConfig, ...)
```

Hy-MT uses a custom Tencent architecture (`HunYuanDenseV1ForCausalLM`) that is not in CTranslate2's converter registry.

**Attempted fix:** Patched `config.json` to change `model_type` from `"hunyuan_v1_dense"` to `"llama"` and `architectures` from `["HunYuanDenseV1ForCausalLM"]` to `["LlamaForCausalLM"]`. This got past the config check but revealed two deeper incompatibilities.

---

## Blocker 2: Dynamic RoPE Scaling (fatal)

**Error:**
```
NotImplementedError: RoPE scaling type 'dynamic' is not yet implemented.
The following RoPE scaling types are currently supported: linear, su,
llama3, longrope
```

Hy-MT's config uses `"rope_scaling": {"type": "dynamic"}` with custom parameters:
- `alpha`: 1000.0
- `beta_fast`: 32
- `beta_slow`: 1
- `mscale`: 1.0
- `mscale_all_dim`: 1.0

CTranslate2's LLaMA converter only supports `linear`, `su`, `llama3`, and `longrope`. The `dynamic` type used by Hy-MT is a Tencent-specific extension not implemented upstream.

---

## Blocker 3: QK LayerNorm (non-fatal but weights dropped)

**Warning during conversion:**
```
Some weights were not used: model.layers.0.self_attn.key_layernorm.weight,
model.layers.0.self_attn.query_layernorm.weight, ...
```

Hy-MT enables `"use_qk_norm": true` — applying RMSNorm to Q and K projections before attention. Standard LLaMA does not have these parameters. Even if the RoPE issue were fixed, these weights would be silently dropped, degrading translation quality.

---

## Comparison: Model Architecture vs LLaMA

| Parameter | Hy-MT 1.8B | Standard LLaMA | Compatible? |
|-----------|-----------|---------------|------------|
| Hidden size | 2048 | Varies | ✅ |
| Layers | 32 | Varies | ✅ |
| Attention heads | 16 | Varies | ✅ |
| KV heads (GQA) | 4 | 4+ | ✅ |
| Activation | SiLU (Swish) | SiLU | ✅ |
| Normalization | RMSNorm | RMSNorm | ✅ |
| RoPE | ✅ | ✅ | ✅ |
| **RoPE scaling type** | **dynamic** | linear/llama3 | **❌** |
| **QK-Norm** | **Yes** | **No** | **❌** (weights dropped) |
| Custom architecture | `HunYuanDenseV1` | `Llama` | **❌** |

Under the hood Hy-MT is **LLaMA-like**, but the `dynamic` RoPE scaling and QK-Norm are proprietary Tencent additions that CTranslate2's converter cannot handle.

---

## Alternative: HF Transformers Directly

| Aspect | HF Transformers (bfloat16, CPU) |
|--------|-------------------------------|
| Model load time | 1.6 s |
| Per-inference time | ~19 s (18 input → 50 output tokens) |
| Estimated full sweep (30 items × 5 beams) | ~48 min (excluding process spawn overhead) |
| Prompt format | Unknown — tested template produced incorrect results |
| RAM | ~3.5–4 GB (bfloat16) |

**Problems with this approach:**
1. **19× slower** than anticipated CT2 inference → sweep takes ~1 hr instead of ~10 min
2. **Latency numbers not comparable** to Opus-MT/M2M-100 (both use CT2) — benchmark would mix optimized vs unoptimized runtimes
3. **Prompt format mismatch** — the guide's template produced generic text, not translations
4. **Separate processes** for each beam width means reloading the model 5× → ~8 s overhead per beam

---

## Options Going Forward

| Option | Effort | Quality data | Runtime comparability |
|--------|--------|-------------|---------------------|
| **A.** HF Transformers, find correct prompt, accept slow sweep | 1–2 hr | ✅ Real Hy-MT scores | ❌ Not comparable to CT2 models |
| **B.** Skip Hy-MT; decide between Opus-MT and M2M-100 only | 0 hr | ✅ M2M-100 (16.9 BLEU) is strong | ✅ All CT2, same pipeline |
| **C.** Upstream CT2 `dynamic` RoPE support + QK-Norm | Weeks/months | — | — |
| **D.** Try ONNX export via `optimum-cli` | 2–3 hr | Unknown | Unknown speed |

---

## Recommendation

**Option B** unless Hy-MT quality is expected to significantly exceed M2M-100's BLEU 16.9. The 19× latency penalty and incomparable runtime data make Option A unattractive for a decision-driving benchmark. Revisit Hy-MT if:
- CTranslate2 adds `dynamic` RoPE scaling support in a future release
- OR on-device runner (ADR-006) supports direct HF inference with acceleration (GPU/NPU)