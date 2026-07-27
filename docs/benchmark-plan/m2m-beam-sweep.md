# M2M-100 Beam Sweep — Execution Plan

> Benchmark `facebook/m2m100_418M` (vi→en) via CTranslate2 int8 on host/laptop.
> Follows `docs/benchmark/beam-sweep-guide-v2.md` Section 1b.

---

## Phase 0 — Download & Convert Model

### Step 0.1 — Download and convert M2M-100 to CTranslate2 int8

```bash
uv run ct2-transformers-converter \
  --model facebook/m2m100_418M \
  --output_dir models/m2m100-418m-ct2-int8 \
  --quantization int8 \
  --copy_files tokenizer.json tokenizer_config.json special_tokens_map.json
```

This downloads ~1.6 GB of HF weights, converts to CT2 format (~600 MB int8), and stores the tokenizer files alongside.

### Step 0.2 — Verify conversion

```bash
uv run python -c "
import ctranslate2
t = ctranslate2.Translator('models/m2m100-418m-ct2-int8', device='cpu', compute_type='int8')
print('M2M-100 CT2 model loaded OK')
print('Encoder vocab:', t.num_encoder_tokens)
print('Decoder vocab:', t.num_decoder_tokens)
"
```

---

## Phase 1 — Code Changes

### Step 1.1 — Create `bench/candidates/m2m_mt.py`

New file implementing `M2M100MTCandidate`.

**Key design decisions** (from guide v2 Section 1b):

| Aspect | Implementation |
|--------|---------------|
| Runtime | `ctranslate2.Translator` (same as Opus-MT) |
| Tokenizer | `AutoTokenizer.from_pretrained("facebook/m2m100_418M", src_lang="vi")` |
| Language control | **Must** pass `target_prefix=[[tokenizer.lang_code_to_token["en"]]]` to `translate_batch()` |
| Output stripping | Slice `[1:]` on hypothesis tokens to remove leading language token before `decode()` |
| Config | `beam_size` from `cfg.get("beam_size", 4)` |
| Other decode params | `repetition_penalty=1.1`, `no_repeat_ngram_size=3`, `max_decoding_length=256` (fixed) |

Model path constant:
```python
M2M_MODEL_DIR = _ROOT / "models" / "m2m100-418m-ct2-int8"
```

**Critical warning**: Omitting `target_prefix` causes M2M-100 to output in a random language (not English). This will produce BLEU ≈ 0 regardless of beam width — easily mistaken for "model is bad" when it's actually a missing parameter.

### Step 1.2 — Register in `bench/registry.py`

Add import at top:
```python
from .candidates.m2m_mt import M2M100MTCandidate
```

Add entry to `REGISTRY` dict:
```python
M2M100MTCandidate.id: (M2M100MTCandidate, None, {}),
```

### Step 1.3 — Update `bench/aggregate_beam_sweep.py` to v2

Current version (v1) is Opus-MT-only:
- Hard-codes `beam-{beam}` at results root
- No `--candidates` argument
- No absolute RAM column
- No cross-model comparison table

Changes needed (per guide v2 Section 6):

1. Add `--candidates` argument (list of candidate IDs, default includes all 3 models)
2. Look up results at `root / candidate / f"beam-{beam}" / "run_results.json"`
3. Print per-candidate table with extra **absolute RAM** column
4. Add cross-model BLEU comparison table at the end
5. Rename `D_RAM(MB)` header to `ΔRAM(MB)`

Why absolute RAM matters: M2M-100 (418M params) has a different RAM baseline than Opus-MT (~300 MB effective). When we add Hy-MT (1.8B) later, the difference becomes critical for device budget decisions.

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
    --candidate m2m100-vi-en-ct2-cpu \
    --out /tmp/beam-m2m-$beam \
    --config-override "{\"beam_size\": $beam}"
done
```

### Step 2.3 — Validate output is English

```bash
uv run python -c "
from bench.schema import RunManifest
from bench.candidates.m2m_mt import M2M100MTCandidate
m = RunManifest.from_json('/tmp/mt_smoke.json')
c = M2M100MTCandidate(config={'beam_size': 1})
for item in m.items[:2]:
    out, err = c._infer(item)
    print(f'{item.id}: {repr(out)}')
"
```

Check:
- Output is recognizably English (not Vietnamese, not gibberish)
- No language token prefix visible in decoded text
- Latency and BLEU columns in `print_table()` are populated, no error rows

If output is wrong → fix `target_prefix` before proceeding.

---

## Phase 3 — Full Sweep

### Step 3.1 — Run 5 beam widths as separate processes

```bash
mkdir -p bench-results
for beam in 1 2 4 5 8; do
  echo "=== beam_size=$beam ==="
  uv run python -m bench.run \
    --manifest eval_data/mt_subset_beam.json \
    --candidate m2m100-vi-en-ct2-cpu \
    --out bench-results/m2m100-vi-en-ct2-cpu/beam-$beam \
    --config-override "{\"beam_size\": $beam}"
done
```

Each beam runs in a separate `uv run` process to avoid:
- Candidate cache contamination (reusing stale instance with old beam_size)
- RAM high-water mark bleed (peak_ram_mb accumulates within a process)

---

## Phase 4 — Aggregate & Report

### Step 4.1 — Run aggregation

```bash
uv run python -m bench.aggregate_beam_sweep \
  --candidates m2m100-vi-en-ct2-cpu
```

Expected output columns: Beam, BLEU, Rel.latency, ΔRAM(MB), RAM abs(MB), Errors.

### Step 4.2 — Write report

Write to `bench-results/report-new/beam-sweep-mt-m2m100.md` including:

- Results table
- Opus-MT comparison (how does M2M-100 BLEU/latency/RAM compare at same beam widths?)
- Verdict with recommended beam width
- Caveat (host-only, need on-device re-verification)

---

## Timeline

| Step | Estimated duration | Notes |
|------|-------------------|-------|
| 0.1 Download + convert | 10–20 min | Depends on internet speed; ~1.6 GB download |
| 0.2 Verify conversion | 1 min | Quick smoke load |
| 1.1 Create m2m_mt.py | 10 min | Straightforward; ~50 lines |
| 1.2 Registry update | 1 min | 2 lines |
| 1.3 Update aggregation script | 15 min | V1 → V2 changes |
| 2.1–2.3 Smoke test | 3 min | 3 items × 2 beams |
| 3.1 Full sweep | 15–30 min | 30 items × 5 beams; M2M-100 is 418M, expect ~1–2 s/item |
| 4.1–4.2 Aggregate + report | 10 min | Analysis + markdown |

**Total: ~1–1.5 hours** (mostly waiting for downloads and inference).