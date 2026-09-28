# Issue #116 — Opus-MT Encoder Quantization A/B: w8a16 vs w8a8

> **Issue:** [#116 — adr: close ADR-003 — Opus-MT quantization: w8a16 vs w8a8](https://github.com/TanKhoiTV/kavi-prototype/issues/116)
> **Scope:** Measure the accuracy/latency trade-off of QNN quantization bit-width on the
> Opus-MT vi→en **encoder**, then record a decision and close open parameter **#7**.
> **Pre-requisite reading:** `docs/ndk-conversion-runbook.md` (the conversion pipeline),
> `docs/decisions/ADR-003-hexagon-runtime.md`, ADR-026 (real-data calibration),
> ADR-027 (ASR CPU-only), `docs/decisions/README.md` (open-parameters register).
> **Related issue:** #74 (calibration data sufficiency) — see [§6 Coupling](#6-coupling-with-issue-74).

---

## 1. Why this issue exists

`.kavi.yaml` currently pins the Opus-MT QNN encoder to `quantization: "w8a16"`
(int8 weights / int16 activations) with the rationale *"the HTP only executes
quantized graphs; w8a16 is recommended to protect transformer accuracy"*. That
rationale was **never measured** — it is the unresolved open question in ADR-003,
which is still `Proposed` for this reason alone.

`w8a8` (int8 activations) is cheaper on HTP but carries a larger accuracy risk.
This plan produces the numbers, and ADR-003 turns *Proposed* → *Accepted* (or
records why it stays `Proposed`).

**Scope boundary:** the **encoder only**. The MT decoder runs on CPU
(ADR-023/ADR-027), and per ADR-027 the Opus-MT encoder is the **only** remaining
QNN artifact on the v1 path — this is the last opportunity for quantization
tuning before v1 freeze.

### Definition of Done (from the issue)

1. Accuracy regression measured for `w8a16` vs `w8a8` on the Opus-MT encoder.
2. A decision recorded; `.kavi.yaml` updated if it changes.
3. Open parameter #7 closed in the register.

### Out of scope

- Decoder quantization (CPU/ORT path, not HTP).
- `w4a8` / `w8a4` and other bit-widths — only the A/B the issue asks for.
- Re-tuning Whisper/Piper QNN paths (obsolete per ADR-008/009/024).
- Beam search (deferred to Phase 5 per ADR-007 §MT); both arms use greedy.

---

## 2. Current state — what already exists vs what does not

Verified against the working tree, 2026-09-25.

| Asset | State | Path / note |
| --- | --- | --- |
| Eval set vi→en | ✅ **Ready** | `eval_data/mt_vi_en_eval_manifest.json` — 347 items, 347/347 with `reference_text` |
| BLEU scorer | ✅ **Ready** | `bench/scorer.py` (sacrebleu) |
| RTF capture | ✅ **Ready** | via the runner latency logs |
| COMET scorer | ❌ Missing | `bench/scorer.py`: *"COMET deferred to v1"* — see [§7 Open decisions](#7-open-decisions-need-a-call) D1 |
| CPU baseline | ✅ **Ready** | `models/opus-mt-vi-en-ct2`; prior run in `bench-results/mt-vi-en-v1` (BLEU ≈ 76) |
| Calibration list generator | ✅ **Done** | `bench/qnn/generate_calibration_lists.py` — both graph inputs, int64, `--require-disjoint` (P2) |
| Calibration list file | ✅ **Generated** | `models/qnn/opusmt_input_list.txt` — 64 samples / 128 entries, sha256 `d98546fd2787…` |
| Quantization flag | ✅ **Done** | `bench/qnn/convert_to_qnn.sh` — `--quantization` / bit-width / `--require-input-list` (P0) |
| Encoder ONNX | ✅ **Exported** | `models/qnn/opus-mt-vi-en/opus-mt-vi-en/encoder_model.onnx` (178.2 MiB), verified vs the PyTorch reference (max\|Δ\| 2.9e-06) |
| Model `.so` + context binary | ❌ Missing | `.kavi.yaml` marks the context binary *"NOT YET PRODUCED — M3 deliverable"* |
| On-device runner | ❌ Stub | `bench/candidates/qnn_opusmt_mt.py` raises `NotImplementedError`; `android/app/src/main/java/com/kavi/app/runner/` does not exist |
| QNN candidate registration | ⚠️ Single arm | `bench/registry.py` has only `qnn-opus-mt-vi-en-htp-v73`; no way to hold two arms |
| QAIRT SDK / NDK | ❌ Not set | `QAIRT_SDK_ROOT` and `ANDROID_NDK_ROOT` unset on this host; conversion is **Linux-x86_64 only** |

**Bottom line:** the *measurement* itself is small (change one flag, run twice).
Roughly 80 % of the effort is in the pre-requisites. This issue is effectively
gated on the **M3 deliverable** (`docs/android-implementation-plan.md` §Milestone 3),
not independently deliverable.

---

## 3. Phases

Phases 0–2 are **unblocking** and run on the dev host with no device and no
Qualcomm access. Phases 3–4 need the Linux build host. Phases 5–6 need the device.

| Phase | Name | Needs | Produces |
| --- | --- | --- | --- |
| **P0** | Make quantization configurable | dev host | `convert_to_qnn.sh` flag |
| **P1** | Export encoder ONNX | dev host | `encoder_model.onnx` |
| **P2** | Build calibration list (real data) | dev host + FLEURS/GOLD_SET | `opusmt_input_list.txt` |
| **P3** | Build both context binaries | Linux + QAIRT 2.31.0.250130 + NDK r26c | `..._w8a16.bin`, `..._w8a8.bin` |
| **P4** | Register two candidates | dev host | `qnn-opus-mt-...-w8a8` id in `registry.py` |
| **P5** | On-device run — two arms | Meizu 21 Note | `run_results` per arm |
| **P6** | Score + compare | dev host | comparison table |
| **P7** | Record decision & close #7 | dev host | ADR-003, `.kavi.yaml`, register row |

### P0 — Make quantization configurable — ✅ **DONE**

**Objective:** the conversion script can emit either arm from one code path, so the
two artifacts differ **only** in bit-width.

- [x] Add `--weights-bitwidth` (default `8`) and `--act-bitwidth` (default `16`) to
      `bench/qnn/convert_to_qnn.sh`; replace the hardcoded block at the
      `--param_quantizer/--act_quantizer` step.
- [x] Add the artifact-suffix convention so the two arms cannot overwrite each
      other: `--name opus_mt_vi_en_encoder_w8a16` / `..._w8a8`.
- [x] Add the numeric argument validation already implied by the usage block
      (act-bitwidth must be 8 or 16), and echo the final quantizer settings into the
      run log so the build is self-documenting.
- [x] Keep the "no `--input-list` → fallback ranges" warning, but make it **fatal
      under P2** (or add a `--require-input-list` flag) so a calibration-less build
      can never silently become the w8a8 arm.

**Delivered:**

| Addition | Purpose |
| --- | --- |
| `--quantization w8a16\|w8a8` | Preset matching the `quantization:` key in `.kavi.yaml`; sets both bit-widths |
| `--weights-bitwidth` / `--act-bitwidth` | Explicit per-flag control (8/16 validated) |
| `--param-quantizer` / `--act-quantizer` | `tf` (default), `percentile`, `minmax`, `entropy` |
| `--require-input-list` | Turns the missing-calibration warning into a hard error (ADR-026) |
| `--force-rebuild` | Explicit override of the build-stamp guard |
| `<name>_qconv_meta.txt` | Build stamp; refuses to rebuild a `--name` with different bit-widths, quantizers or calibration hash — the two A/B arms cannot silently clobber each other |
| `--input-list` existence check | A mistyped calibration path now fails early instead of reaching the converter |
| Log lines | `Quant: w8a8 (param=tf act=tf)` header + `Arm:` summary |

Verification: `bash bench/qnn/test_convert_to_qnn.sh` — 38 assertions, no Qualcomm
SDK required (the `qnn-*` tools are replaced by stubs). Covers flag plumbing,
validation rejection, back-compat of the w8a16 default, the build-stamp guard, and
that the two arms produce **different** context binaries.

**What that does and does not prove.** The stubs verify *flag plumbing* — that
the wrapper hands the intended bit-widths to the converter binary. They cannot
verify that QAIRT *applies* them. Byte-differing binaries are a provenance and
difference check; confirming the effective widths needs the real converter — see
the P3 checklist.

**Exit criteria:** ✅ met — `bash -n` clean; `--help` documents all flags; dry run
shows the intended quantizer tuple per arm.

**Risk:** the QNN converter's accepted quantizer/bit-width combinations differ per
QAIRT release. Confirm `tf` activation quantizer supports 8-bit before assuming the
flag is sufficient; the fallback is a percentile/minmax activation quantizer, which
must then be held **identical across both arms**. The script prints a NOTE when
`--act-bitwidth 8 --act-quantizer tf` is combined.

### P1 — Export the encoder ONNX — ✅ **DONE**

**Objective:** produce the single source graph both arms are built from.

- [x] Fetch the missing `pytorch_model.bin` (289 MB, SHA-256 verified against
      `assets.lock.toml`). It was absent, so the export could not start.
- [x] Run `bench/qnn/export_opusmt_onnx.py` to emit `encoder_model.onnx` into
      `models/qnn/opus-mt-vi-en/opus-mt-vi-en/` (178.2 MiB = 186.9 MB, matching
      the size `.kavi.yaml` already documented).
- [x] Record input names and fixed input dims (HTP forbids dynamic shapes —
      ADR-003). The exported graph declares *symbolic* dims, so the QAIRT step must
      pin them explicitly:

  | Tensor | Name | Shape | Dtype |
  | --- | --- | --- | --- |
  | in | `input_ids` | `[1, 128]` | int64 |
  | in | `attention_mask` | `[1, 128]` | int64 |
  | out | `last_hidden_state` | `[1, 128, 512]` | float32 |

- [x] Confirm the decoder is **not** part of this A/B — it runs on CPU (ADR-023).
      `decoder_model.onnx` (307 MB) and `decoder_with_past_model.onnx` were exported
      only because the exporter emits them; they are not quantized here.
- [x] Sanity-check the fp32 graph before any quantization: `bench/qnn/verify_onnx_encoder.py`
      compares it against the PyTorch reference on real eval sentences at the fixed
      shape. Result: **max|Δ| = 2.9e-06, cos = 1.000000, all finite → PASS.**

**Fixed along the way** (all were blocking the export):

| Problem | Fix |
| --- | --- |
| `export_opusmt_onnx.py` loaded `google/fleurs` config `all`, then `list(ds)` — the whole train split of every language, with audio, into RAM. Unpinned, and on any failure it fell through `except Exception: pass` to **synthetic** sequences (ADR-026) | Removed calibration generation from the exporter; `bench.qnn.generate_calibration_lists.py` is now the single owner (P2). The synthetic path is deleted, not just unreached |
| `optimum` 2.1 rejects `task=` for `ORTModelForSeq2SeqLM` (pyproject pins `>=1.20.0`, so a 2.x resolves) | Dropped the `task=` argument |
| Passing the Hub ID made transformers load `tf_model.h5` and fail on missing TensorFlow | Export from the pinned local snapshot (`models/opus-mt-vi-en-src`), which `fetch_models.py` deliberately keeps TF-free |
| `--help` crashed on Windows (`UnicodeEncodeError`, cp1252 vs `↔`/`→`) | ASCII-only argparse text |

**Exit criteria:** ✅ met — ONNX loads, runs on CPU, and matches the checkpoint.

**Findings carried forward from P1, with their current state:**

1. **Dtype mismatch — resolved in P2.** The graph declares `input_ids` /
   `attention_mask` as int64 while the generator wrote int32.
   `--opusmt-dtype` now defaults to int64, matching the graph.
2. **Sequence length — resolved in P2.** `--opusmt-seq-len` defaults to 128,
   which is the value P3 must pass as `--input-dims "1,128"`.
3. **Fresh-checkout note (still true).** `docs/ndk-conversion-runbook.md` §3
   claims the step-1 outputs and the calibration list already exist.
   `models/qnn/*` is gitignored, so a fresh checkout has neither: regenerate the
   calibration list rather than assume it. This does not block the completed P2
   state.

**Trap (now closed):** if the fp32 graph is wrong, both arms inherit the same bug and
the comparison looks clean. The verification script makes that failure loud.


### P2 — Build the calibration input list (real data only) — ✅ **DONE**

**Objective:** one calibration list, real data, used by **both** arms. This is the
single most likely source of an invalid conclusion.

- [x] Generate the list from real text via `bench.qnn.generate_calibration_lists`:
      **64 samples**, shape `[1, 128]`, **int64**, both graph inputs.
- [x] **Fixed the `attention_mask` gap.** The list previously carried only
      `input_ids`, while the encoder takes two inputs — `attention_mask` would have
      stayed on fallback ranges, silently skewing exactly the activation ranges
      this issue measures. One file per input is now written per sample.
- [x] **Fixed the dtype.** The generator wrote int32; the exported graph declares
      int64. `--opusmt-dtype` defaults to int64, int32 stays available.
- [x] Sanity-checked: 64 samples run through the real ONNX encoder →
      `(64, 128, 512)`, all finite, **64/64 distinct outputs** (no collapsed
      or duplicated samples). Token lengths min 15 / median 34 / max 81 of 128.
- [x] Frozen and checksummed: `opusmt_input_list.txt.sha256`
      (`d98546fd2787…`). The P0 build stamp records the same digest, so a
      calibration swap between the two arms is refused.

**Activation range observed:** max|activation| ≈ 6.6 per sample — a plausible
transformer range, and the bound the converter must cover.

**Calibration provenance — overlap, and why it is acceptable here:** the local FLEURS
`vi_vn` **test** split holds 857 rows but only **347 unique sentences, all of which
the MT eval set scores on**. There is no disjoint text available locally, and
GOLD_SET is 12 sentences (too few). The generator therefore measures the overlap and
warns rather than claiming disjointness it cannot deliver.

- Both arms use identical calibration, so the **w8a16-vs-w8a8 comparison is valid**.
- The **absolute** BLEU is optimistic against the CT2 CPU baseline, which was not
  calibrated on these sentences. Read the third row of the P6 table accordingly.
- `--require-disjoint` turns this into a hard error, and `--calib-source fleurs`
  becomes usable as soon as a FLEURS dev/train split is pinned in
  `assets.lock.toml`. Tracked as **D6** in §7.

**Fixed along the way:**

| Problem | Fix |
| --- | --- |
| Manifest read without `encoding=` → `UnicodeDecodeError` on the first Vietnamese sentence (cp1252) | Explicit UTF-8 on every manifest/list read |
| Disjointness was checked against one manifest only: `eval_manifest_v1.json` has 42 MT items while `mt_vi_en_eval_manifest.json` has the 347 actually scored, so 347 eval sentences were reported as "unused" | `_collect_eval_texts` scans every `*manifest*.json` in the eval dir and prints which files it consulted |
| Sample count was computed as `len(list_lines) // 2` although each element already held both inputs | Explicit `samples` counter |
| The provenance line interpolated the whole item list, dumping 40 manifest records into the log | Reports counts only |

**Exit criteria:** ✅ met — real data, both inputs, correct dtype, verified against
the graph, checksummed.

**Carry into P3:** the sequence length **must** stay 128 (`--input-dims "1,128"`),
and both arms must be built from this exact list. `convert_to_qnn.sh
--require-input-list` enforces the second at build time.


### P3 — Build both context binaries

**Objective:** two artifacts, identical except for activation width.

**Environment:** Linux x86_64 host; `QAIRT_SDK_ROOT` = QAIRT **2.31.0.250130**
(must match device `qnn-2.31` / HTP v73 — ABI drift = silent load failure,
ADR-019); `ANDROID_NDK_ROOT` = NDK **r26c (26.1.10909125)**;
`source scripts/qairt-env.sh`; converter venv Python 3.10. Procedure:
`docs/ndk-conversion-runbook.md`.

- [ ] Build **arm A** — w8a16: `--weights-bitwidth 8 --act-bitwidth 16`.
- [ ] Build **arm B** — w8a8: `--weights-bitwidth 8 --act-bitwidth 8`.
- [ ] Both with the **same** `--input-list` from P2, same `--input-dims`, same
      `--htp_arch v73`, same QAIRT version.
- [ ] Verify each output is a **context binary** (`.bin`), not the weight-tar
      (`.cpp_net.json` / step-1 output). M3 explicitly calls out this confusion.
- [ ] Record `SHA256SUMS` for both (ADR-011 provenance) and confirm the two differ
      — this proves the artifacts are distinct, not that the requested widths
      were applied.
- [ ] Read back the **effective** quantization widths per arm from the converter
      output (`<name>_net.json` quantization params, or the converter log). This
      is the only check that shows what QAIRT actually applied; the stub test and
      the hashes above cannot.

**Exit criteria:** two distinct, version-locked HTP v73 context binaries, each
with its effective widths confirmed, verified by hash and by a device-side load
smoke test (P5).

**Blocker note:** this host is Windows/MINGW64 with both env vars unset; conversion
must happen on the Linux build host.

### P4 — Register two benchmark arms

**Objective:** the harness can score the arms side by side without one clobbering
the other.

- [ ] Add a second candidate id (e.g. `qnn-opus-mt-vi-en-htp-v73-w8a8`) in
      `bench/registry.py`, or parameterize the existing candidate by a
      `context_binary` config key.
- [ ] Point each arm at its own model directory / context binary.
- [ ] Verify `bench/run.py` writes to **distinct output paths** per candidate id
      (`bench-results/<experiment>/<candidate-id>/`).
- [ ] Pin the arm configs: greedy decoding, `kv_cache_tokens: 256`, identical
      `max_length`, identical source/target SentencePiece models. Any difference
      here contaminates the comparison.

**Exit criteria:** `registry.py` exposes both arms; a smoke run writes two separate
output trees.

### P5 — On-device run (two arms, one manifest)

**Objective:** the numbers, on real silicon.

**Device:** Meizu 21 Note — Snapdragon 8 Gen 2 (`kalama`), HTP **v73**,
Android 16 (API 36), QNN runtime preinstalled; app bundles `libQnn*.so` (ADR-019).
Emulators do not exercise the NPU (ADR-002).

- [ ] **Prerequisite — the runner must exist.** `bench/candidates/qnn_opusmt_mt.py`
      is a stub raising `NotImplementedError`, and
      `android/.../com/kavi/app/runner/` is absent. Completing
      `qnn_loader_jni.cpp` (M3 step 1) is the hard blocker for this phase; until
      then, P5 cannot start.
- [ ] Read the **same** `eval_manifest_v1.json` subset (`mt_vi_en_eval_manifest.json`)
      for both arms — byte-identical inputs are what makes the comparison fair.
- [ ] Log per-utterance **latency / RTF** and peak RSS per arm; keep the
      zero-network assertion.
- [ ] Repeat the latency measurement (≥ 3 runs) — single-shot NPU timing on a
      shared phone is noisy enough to invert a small RTF delta.

**Exit criteria:** two output dumps, same item IDs, with RTF populated for both.

### P6 — Score and compare

**Objective:** one table that answers the issue.

- [ ] Score both arms off-device with `bench/scorer.py` (BLEU vs the 347 references;
      RTF from the runner logs).
- [ ] Include the **CPU baseline** (`models/opus-mt-vi-en-ct2`,
      `bench-results/mt-vi-en-v1`, BLEU ≈ 76) as a third row — w8a16 should be
      sanity-checked against it, since a large gap means the QNN path is broken
      rather than "w8a16 is accurate".
- [ ] Report **ΔBLEU (w8a8 − w8a16)** and **ΔRTF**, plus absolute values.
- [ ] Spot-check ~20 items by eye in both arms — BLEU alone can hide a qualitative
      degradation (e.g. truncation, repetition) on a subset.

**Exit criteria:** a comparison table with BLEU, RTF, and CPU baseline row.

### P7 — Record the decision and close parameter #7

**Objective:** the issue's actual deliverable — a recorded decision, not a number.

- [ ] **ADR-003** — fold the result into the open-questions section; the
      determination-method text already promises *"This comparison closes this ADR
      (→ Accepted)"*. If w8a16 is retained, say so explicitly and move the status
      from `Proposed` with a dated decision note.
- [ ] **`.kavi.yaml`** — update `mt.qnn_encoder.quantization` **iff** the decision
      changes; add the chosen `context_binary` / `model_lib` names, and remove the
      stale *"NOT YET PRODUCED"* comment once P3 lands.
- [ ] **`docs/decisions/README.md`** — close open parameter **#7**
      (`| 7 | w8a16 vs w8a8 for Opus-MT | ADR-003 | Accuracy regression measurement |`)
      with the outcome, the numbers, and a link to the results.
- [ ] Cross-reference **#74** if the calibration work overlapped.

**Exit criteria:** ADR status updated, `.kavi.yaml` consistent, register row closed.
Closes #116.

---

## 4. Decision rule

Pre-registered so the conclusion is not chosen after seeing the numbers:

- **Adopt `w8a8`** if — and only if — the BLEU/COMET regression stays within an
  agreed tolerance **and** the RTF improvement is material. "Material" should be
  fixed before P5 (suggested: ≥ 10 % RTF improvement on the encoder stage).
- **Keep `w8a16`** if the regression exceeds tolerance, or the RTF gain is
  negligible — a defensible and fully valid outcome. The issue asks for a
  *recorded decision*, not for w8a8.
- **Inconclusive → keep `w8a16`** (status quo) and record why, rather than shipping
  an unmeasured change.

**Suggested BLEU tolerance:** 1.0 corpus BLEU point vs the w8a16 arm. The issue does
not name a threshold; it must be agreed **before** P6, not after.

---

## 5. Phase dependency graph

```
P0 (quant flag) ─┐
P1 (export ONNX) ─┼─→ P3 (build ×2 ctx) ─→ P4 (register 2 arms) ─┐
P2 (calib list) ─┘                                                    ├─→ P6 (score) ─→ P7 (decide)
                       M3 on-device runner ─────────────────────────┘ (P5)
```

- P0, P1, P2 are **independent** and parallelizable; all runnable on the dev host
  with no device and no Qualcomm access — **start here**.
- P3 requires the Linux build host (QAIRT 2.31.0.250130 + NDK r26c).
- P5 is gated on the **M3 on-device runner**, which does not exist. This is the
  critical path.
- P7 must not start before P6.

---

## 6. Coupling with issue #74

#74 (*"Track: Validate calibration data sufficiency for QNN quantization"*) is not
independent of this work:

- **P2 is shared work.** Calibration sufficiency is a prerequisite for a trustworthy
  w8a8 verdict — a poorly calibrated int8 activation range is the main accuracy risk.
- **If #74 changes the corpus, P3 re-runs for both arms** and P6 repeats. Batching
  the two avoids paying that cost twice.
- Recommended sequencing: land the calibration sufficiency check as part of P2 so
  #74 is de-risked here rather than run as a separate experiment afterwards.

---

## 7. Open decisions (need a call)

| # | Question | Impact if left open |
| --- | --- | --- |
| **D1** | **COMET** — add it to the harness (model download, scoring cost) or accept BLEU + manual spot-check? `scorer.py` explicitly defers it to v1. | P6 scope grows; the issue's "BLEU/COMET" wording is unimplementable as-is |
| **D2** | **BLEU tolerance** for accepting w8a8 (§4) | Decision rule has to be invented after seeing results — bias risk |
| **D3** | **Latency measurement** — is a Meizu 21 Note available, or do we use the Qualcomm AI Hub device farm? | P5 cannot start; also affects whether the result is a real-device claim |
| **D4** | **RTF materiality threshold** (§4) | Same bias risk as D2 |
| **D5** | Run the **full 347-item set** or a fixed subset (e.g. 100) for both arms? | Full set = better confidence, longer device time |
| **D6** | Calibration currently **overlaps the eval split** (P2): the local FLEURS test split is fully consumed by the 347 MT eval sentences and GOLD_SET is too small. Accept the overlap and note the optimistic absolute BLEU, or pin a FLEURS dev/train split in `assets.lock.toml` and regenerate? | The w8a16-vs-w8a8 decision is valid either way; the number reported against the CPU baseline is not |

---

## 8. Risks

| Risk | Mitigation |
| --- | --- |
| **Contaminated comparison** — a differing flag (padding, kv_cache, decoder, max_length) is blamed on quantization | P4 pins both arms' configs; diff them before running |
| **Calibration collapse** — single-sample or synthetic calibration (ADR-026) makes the w8a8 arm look arbitrarily bad | P2 forbids the fallback; ≥ tens of real samples; shared and checksummed |
| **Flag silently ignored** — the converter accepts `--act_bitwidth 8` but the build still emits a w8a16 graph | P3 reads the effective widths back from the converter output; differing hashes are only a difference check, and a device smoke test confirms the loading path |
| **fp32 graph defect** — both arms inherit the same bug and the A/B looks clean | P1 sanity-checks the fp32 ONNX on CPU before any quantization |
| **NPU timing noise** inverts a small RTF delta | ≥ 3 repeated runs in P5; report variance, not a single number |
| **Wrong artifact type** — the weight-tar is mistaken for the context binary | P3 verifies `.bin` output; M3 calls this out explicitly |
| **QAIRT version drift** — SDK upgraded from 2.31.0.250130 breaks on-device loading (silent failure, ADR-019) | Pin the SDK version; record it in the result table |
| **Scope creep into the decoder** (CPU path, ADR-023) | Encoder-only is stated in §1; reject decoder changes in review |
