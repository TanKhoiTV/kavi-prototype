# Beam Sweep Retrospective — Old vs New Approach

> Why the old beam-sweep results for Opus-MT were inaccurate and what we fixed.

## Background

Two beam-sweep reports were generated for Opus-MT (vi→en, CTranslate2 int8, CPU):

| Report | Path | Date |
|--------|------|------|
| Old | `bench-results/report-old/beam-sweep-mt-opusmt.md` | 2026-07-27 |
| New | `bench-results/report-new/beam-sweep-mt-opusmt.md` | 2025-07-26 |

The old report was produced before the formal beam-sweep guide (`docs/beam-sweep-guide.md`) existed. The new report follows the guide's methodology exactly.

---

## Side-by-Side Results

| Beam | Old BLEU | New BLEU | Old Rel. Latency | New Rel. Latency | Old RAM (MB) | New ΔRAM (MB) |
|------|----------|----------|-----------------|-----------------|-------------|---------------|
| 1    | 7.58     | 6.2      | 1.00×           | 1.00×           | 12          | — (baseline)  |
| 2    | 9.95     | 7.8      | 1.28×           | 1.63×           | 8           | +12           |
| 4    | 10.35    | 8.8      | 2.06×           | 2.50×           | 12          | +21           |
| 5    | 10.78    | 9.0      | 2.62×           | 3.02×           | 11          | +28           |
| 8    | 10.79    | 9.0      | 3.74×           | 4.46×           | 14          | +49           |

Key discrepancies: BLEU inflated by ~1.4–2.2 points, latencies compressed (esp. beam=2 at 1.28×), RAM flat and non-monotonic.

---

## Root Cause 1: Candidate Cache Contamination

### The Bug

`run_manifest()` caches candidate instances by `cid` (candidate ID string) in a dictionary:

```python
candidates: dict[str, Candidate] = {}
```

When the sweep runs multiple beam widths **in a single Python process** (e.g. a `for` loop calling `run_manifest()` repeatedly), the second call finds the candidate already cached under `"opus-mt-vi-en-ct2-cpu"` and **reuses the existing instance** — which was initialized with the *previous* beam's `config` dict.

The `__init__` method reads `beam_size` from config and stores it in `self._decode_kwargs`. Once set, it never changes:

```python
self._decode_kwargs = dict(
    beam_size=cfg.get("beam_size", 4),  # read once in __init__, never re-read
    ...
)
```

### What Actually Happened

If the old sweep ran beams in order `[1, 2, 4, 5, 8]`:

1. `beam=1` → candidate built with `beam_size=1` ✅
2. `beam=2` → candidate **reused from step 1** → still `beam_size=1` ❌
3. `beam=4` → candidate reused → still `beam_size=1` ❌
4. ...and so on

But the old report shows *different* BLEU per beam, so the contamination was more subtle. A likely scenario:

- The old script rebuilt the candidate for *some* runs but not others
- Or the item manifest was mutated across calls (side-effect contamination)
- The resulting BLEU values are a mix of runs with correct and stale configs — uninterpretable

### Why Separate Processes Fixes It

```bash
for beam in 1 2 4 5 8; do
    uv run python -m bench.run ... --config-override '{"beam_size": '$beam'}'
done
```

Each `uv run` spawns a fresh Python process. No shared state, no cache. The candidate is built exactly once per process with the intended `beam_size`.

---

## Root Cause 2: RAM High-Water Mark Contamination

### The Bug

`peak_ram_mb` (implemented via `tracemalloc` or `resource.getrusage()`) reports the **maximum** memory the process has ever used since startup. It does not reset between sweep iterations.

If beams are run sequentially in one process:
- `beam=1` runs → peak RAM = ~372 MB
- `beam=2` runs → peak RAM = max(372, new peak) → stays ~372 MB if barely higher
- `beam=8` runs → peak RAM may reach ~421 MB → **all previous beams now report 421 MB**

### Evidence in Old Report

The old report's "KV-cache (MB)" column shows 8, 12, 12, 11, 14 — flat and non-monotonic. This looks like someone tried to subtract a fixed model-load constant from a contaminated `peak_ram_mb`, but the subtraction couldn't recover clean data because the numerator was already wrong.

### Why Separate Processes Fixes It

Each `uv run` starts from zero. `peak_ram_mb` measures only that single beam's run. The report correctly shows monotonic RAM growth: +0, +12, +21, +28, +49 MB.

---

## Root Cause 3: Unfiltered Manifest

The old report used all 42 MT items from `eval_manifest_v1.json`. The new report filters to 30 items that have `reference_text` (via `bench/filter_manifest.py`). Items without reference text produce `BLEU = None`, which can skew averages if the aggregation script handles `None` incorrectly.

---

## Root Cause 4: No Smoke Test

The old approach went straight to the full 42-item run. The new approach runs a **smoke test** first (3 items, 2 beam widths) to catch bugs early. The smoke test immediately reveals:

- Whether `--config-override` actually changes the beam (compare BLEU/latency across beams)
- Whether any items error out
- Whether the output table looks sane

---

## Summary: What to Trust

| Aspect | Old Report | New Report |
|--------|-----------|-----------|
| **Methodology** | Single-process loop | Separate processes per beam |
| **Candidate isolation** | ❌ Shared cache | ✅ Fresh candidate each run |
| **RAM measurement** | ❌ High-water mark contaminated | ✅ Clean per-process peak |
| **Manifest quality** | ❌ Mixed with/without references | ✅ Filtered to valid items only |
| **Smoke test** | ❌ Skipped | ✅ 3-item smoke pass before full run |
| **BLEU scores** | Unreliable (inflated) | Trustworthy |
| **Latency ratios** | Unreliable (compressed) | Trustworthy |
| **RAM deltas** | Unreliable (flat) | Trustworthy |
| **Verdict** | beam=2 (based on bad data) | beam=4 (based on clean data) |

**Decision:** Use the new report (`bench-results/report-new/beam-sweep-mt-opusmt.md`) for all future planning and ADR-007.

---

## Prevention

1. Always run beam sweeps in **separate processes** (`uv run` per beam, not a Python `for` loop).
2. Always **smoke test** with 3 items × 2 beam widths before the full run.
3. Filter the manifest to items with `reference_text` before sweeping MT (or `transcript_ref` for ASR).
4. Document the sweep methodology in `docs/beam-sweep-guide.md` (done).