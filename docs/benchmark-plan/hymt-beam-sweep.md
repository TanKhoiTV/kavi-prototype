# Hy-MT Beam Sweep — Execution Plan

> Benchmark `tencent/HY-MT1.5-1.8B` (vi→en) via CTranslate2 int8 on host/laptop.
> Follows `docs/benchmark/beam-sweep-guide-v2.md` Section 1c.

---

## Key Differences from M2M-100

| Aspect | M2M-100 | Hy-MT |
|--------|---------|-------|
| Architecture | Encoder-decoder | **Decoder-only causal LM** |
| CT2 runtime | `Translator` | **`Generator`** |
| Params | 418M | **1.8B** |
| Language control | `target_prefix` | **Prompt instruction** |
| Output handling | Strip leading lang token `[1:]` | **Strip prompt via `include_prompt_in_result=False`** |
| RAM baseline | ~1101 MB | **~2× higher (estimated)** |

---

## Phase 0 — Download & Convert Model

### Step 0.1 — Verify CT2 version supports `include_prompt_in_result`

Before downloading anything, confirm that `ctranslate2.Generator.generate_batch()` accepts the `include_prompt_in_result` parameter. If not, we'll need a manual workaround in `_infer()`.

```bash
uv run python -c "
import ctranslate2
# Attempt to call with the parameter to check
help(ctranslate2.Generator.generate_batch)
" 2>&1 | grep -A2 include_prompt_in_result
```

If unsupported → add manual prompt slicing in `_infer()` (strip prompt tokens from output before decoding).

### Step 0.2 — Download and convert Hy-MT to CTranslate2 int8

```bash
uv run ct2-transformers-converter \
  --model tencent/HY-MT1.5-1.8B \
  --output_dir models/hy-mt1.5-1.8b-ct2-int8 \
  --quantization int8 \
  --copy_files tokenizer.json tokenizer_config.json special_tokens_map.json
```

**Expected size**: ~1.8 GB int8 (model.bin). Download ~7 GB of HF weights.

**Tokenizers**: Hy-MT likely has `tokenizer.json` (unlike M2M-100 which uses SentencePiece). The `--copy_files` list differs — verify against actual repo contents.

### Step 0.3 — Verify conversion

```bash
uv run python -c "
import ctranslate2
g = ctranslate2.Generator('models/hy-mt1.5-1.8b-ct2-int8', device='cpu', compute_type='int8')
print('Hy-MT CT2 model loaded OK')
"
```

---

## Phase 1 — Code Changes

### Step 1.1 — Create `bench/candidates/hymt_mt.py`

New file implementing `HyMTCandidate`.

**Architecture** (from guide v2 Section 1c):

| Aspect | Implementation |
|--------|---------------|
| Runtime | `ctranslate2.Generator` (not `Translator`) |
| Tokenizer | HF `AutoTokenizer.from_pretrained(str(model_dir))` — loads from local CT2 dir |
| Language control | **Prompt template**: `"Translate the following segment into {target_language}, without additional explanation: {source_text}"` |
| Output handling | **Critical**: `include_prompt_in_result=False` in `generate_batch()` — otherwise output includes the full prompt text, destroying BLEU |
| Fallback (if CT2 too old) | Manually strip prompt tokens from output before `decode()` |
| Config | `beam_size` from `cfg.get("beam_size", 4)` |
| Other decode params | `repetition_penalty=1.1`, `no_repeat_ngram_size=3`, `max_length=256` (fixed) |

**Critical warnings** from guide:
1. Forgetting `include_prompt_in_result=False` → output contains the prompt → BLEU ~0 → looks like "model is bad" but it's a measurement bug
2. Wrong prompt template → genuinely lower quality translations, confusable with beam width effects
3. RAM baseline is much higher than M2M-100 (1.8B vs 418M) — need absolute RAM column in report

Model path constant:
```python
HYMT_MODEL_DIR = _ROOT / "models" / "hy-mt1.5-1.8b-ct2-int8"
```

Prompt template:
```python
PROMPT_TEMPLATE = (
    "Translate the following segment into {target_language}, "
    "without additional explanation: {source_text}"
)
```

### Step 1.2 — Register in `bench/registry.py`

Add import:
```python
from .candidates.hymt_mt import HyMTCandidate
```

Add entry to `REGISTRY`:
```python
HyMTCandidate.id: (HyMTCandidate, None, {}),
```

### Step 1.3 — No aggregator changes needed

`bench/aggregate_beam_sweep.py` already lists `hy-mt1.5-1.8b-ct2-cpu` in the default `--candidates`. The v2 multi-model support (absolute RAM column, cross-model comparison) is already in place from the M2M-100 sweep.

---

## Phase 2 — Smoke Test

### Step 2.1 — Filter 3 MT items

```bash
uv run python -m bench.filter_manifest --stage MT --limit 3 --out /tmp/mt_smoke.json
```

### Step 2.2 — Run smoke with beam=1 and beam=2

```bash
for beam in 1 2; do
  uv run python -m bench.run \
    --manifest /tmp/mt_smoke.json \
    --candidate hy-mt1.5-1.8b-ct2-cpu \
    --out /tmp/beam-hymt-$beam \
    --config-override "{\"beam_size\": $beam}"
done
```

### Step 2.3 — Validate prompt stripping (Hy-MT specific check)

```bash
uv run python -c "
from bench.schema import RunManifest
from bench.candidates.hymt_mt import HyMTCandidate
import tempfile
m = RunManifest.from_json(tempfile.gettempdir() + '/mt_smoke.json')
c = HyMTCandidate(config={'beam_size': 1})
for item in m.items[:2]:
    out, err = c._infer(item)
    print(f'{item.id}: {repr(out)}')
"
```

Check:
- Output is **only the translation**, not the prompt text repeated
- If prompt text appears in output → `include_prompt_in_result` is not working → implement manual prompt stripping
- Output is recognizably English
- BLEU and latency columns in `print_table()` are populated, no error rows

---

## Phase 3 — Full Sweep

### Step 3.1 — Run 5 beam widths as separate processes

```bash
mkdir -p bench-results
for beam in 1 2 4 5 8; do
  echo "=== beam_size=$beam ==="
  uv run python -m bench.run \
    --manifest eval_data/mt_subset_beam.json \
    --candidate hy-mt1.5-1.8b-ct2-cpu \
    --out bench-results/hy-mt1.5-1.8b-ct2-cpu/beam-$beam \
    --config-override "{\"beam_size\": $beam}"
done
```

Each beam runs in a separate `uv run` process (same isolation requirement as Opus-MT and M2M-100).

**Expected duration**: ~17–18 min for the full sweep (30 items × 5 beams at ~3–10 s/item).

---

## Phase 4 — Aggregate & Report

### Step 4.1 — Run aggregation

```bash
uv run python -m bench.aggregate_beam_sweep \
  --candidates hy-mt1.5-1.8b-ct2-cpu
```

Key columns to watch:
- **Absolute RAM**: If baseline exceeds device budget (~2 GB), consider eliminating Hy-MT entirely
- **BLEU vs latency**: Compare with Opus-MT and M2M-100 baselines from earlier sweeps
- **Cross-model table**: Already supported by v2 aggregator

### Step 4.2 — Write report

Write to `bench-results/report-new/beam-sweep-mt-hymt.md` including:
- Results table
- Comparison with Opus-MT and M2M-100 (3-model cross-model table)
- Verdict: recommended beam width for Hy-MT specifically
- Overall verdict: which (model, beam) pair is best for the contest
- Caveat (host-only, on-device RAM concerns are amplified for 1.8B)

---

## Risk Register

| Risk | Impact | Mitigation | Step |
|------|--------|-----------|------|
| `include_prompt_in_result` unsupported in CT2 4.8.0 | BLEU ~0 from prompt leakage | Add manual prompt token stripping in `_infer()` | 0.1, 1.1 |
| Wrong prompt template | Depressed BLEU, confusable with beam effects | Match template exactly from Hy-MT repo; validate in smoke test | 1.1 |
| RAM exceeds 2 GB at beam=1 | Model unusable on device | Flag early; eliminate model without running full sweep | 4.1 |
| Download fails / timeout | Blocked | Retry with `--resume`; check internet | 0.2 |
| Model too slow (>5 s/item) | Sweep takes >30 min | Accept and run overnight | 3.1 |

---

## Timeline

| Step | Best case | Worst case |
|------|-----------|-----------|
| 0.1 Verify CT2 parameter | 1 min | 5 min (if debugging needed) |
| 0.2 Download + convert | 30 min | 60 min |
| 0.3 Verify conversion | 1 min | 1 min |
| 1.1 Create hymt_mt.py | 15 min | 25 min |
| 1.2 Registry update | 1 min | 1 min |
| 2.1–2.3 Smoke test | 5 min | 10 min |
| 3.1 Full sweep | 17 min | 25 min |
| 4.1–4.2 Aggregate + report | 11 min | 15 min |
| **Total** | **~80 min** | **~140 min** |

The download + conversion (30–60 min) is the critical path. Everything else is ~50–80 min of active work.