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
| Calibration list generator | ⚠️ Script only | `bench/qnn/generate_calibration_lists.py`; has a **single-sample fallback** that violates ADR-026 |
| Quantization flag | ❌ Missing | `bench/qnn/convert_to_qnn.sh` **hardcodes** `--weights_bitwidth 8 --act_bitwidth 16` |
| Encoder ONNX | ❌ Missing | `models/qnn/` contains only `README.md`; no `encoder_model.onnx` (186 MB) |
| Calibration list file | ❌ Missing | no `opusmt_input_list.txt` |
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

Verification: `bash bench/qnn/test_convert_to_qnn.sh` — 31 assertions, no Qualcomm
SDK required (the `qnn-*` tools are replaced by stubs). Covers flag plumbing,
validation rejection, back-compat of the w8a16 default, the build-stamp guard, and
that the two arms produce **different** context binaries (the check that catches a
silently ignored bit-width flag).

**Exit criteria:** ✅ met — `bash -n` clean; `--help` documents all flags; dry run
shows the intended quantizer tuple per arm.

**Risk:** the QNN converter's accepted quantizer/bit-width combinations differ per
QAIRT release. Confirm `tf` activation quantizer supports 8-bit before assuming the
flag is sufficient; the fallback is a percentile/minmax activation quantizer, which
must then be held **identical across both arms**. The script prints a NOTE when
`--act-bitwidth 8 --act-quantizer tf` is combined.

### P1 — Export the encoder ONNX

**Objective:** produce the single source graph both arms are built from.

- [ ] Run `bench/qnn/export_opusmt_onnx.py` against the pinned Opus-MT weights
      (`make models` if absent) to emit `encoder_model.onnx` (186 MB fp32) into
      `models/qnn/opus-mt-vi-en/opus-mt-vi-en/`.
- [ ] Record input names and fixed input dims (HTP forbids dynamic shapes —
      ADR-003; expect `[1, 128]` token ids) for the P3 invocation.
- [ ] Confirm the decoder ONNX export is still needed — the decoder runs on CPU
      (ADR-023), so it is **not** part of this A/B. Export it only if M3 needs it
      for the CPU fallback path.

**Exit criteria:** ONNX loads; a CPU ORT run produces a sane translation, proving
the graph is good **before** quantizing it.

**Trap:** if the fp32 graph is wrong, both arms will be wrong in the same way and the
comparison will look fine. Always sanity-check fp32 output first.

### P2 — Build the calibration input list (real data only)

**Objective:** one calibration list, real data, used by **both** arms. This is the
single most likely source of an invalid conclusion.

- [ ] Run `python -m bench.qnn.generate_calibration_lists` against a **real** corpus
      (FLEURS or GOLD_SET) to produce `opusmt_input_list.txt`.
- [ ] **Disable / refuse the single-sample fallback.** ADR-026 forbids synthetic
      data; the script's fallback to a previously converted single sample is exactly
      the failure mode #74 exists to catch.
- [ ] Sanity-check sample count and distribution (≥ tens of samples; cover the
      sentence-length range present in the eval set).
- [ ] Freeze the list and checksum it — both arms must byte-match this input.

**Exit criteria:** list exists, is non-trivial in size, and is committed/checksummed.

> **Coupled to #74:** if #74 changes the calibration corpus, **P3 must re-run for both
> arms**. See [§6](#6-coupling-with-issue-74).

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
      (a byte-identical pair means a flag did not take effect).

**Exit criteria:** two distinct, version-locked HTP v73 context binaries, verified
by hash and by a device-side load smoke test (P5).

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

---

## 8. Risks

| Risk | Mitigation |
| --- | --- |
| **Contaminated comparison** — a differing flag (padding, kv_cache, decoder, max_length) is blamed on quantization | P4 pins both arms' configs; diff them before running |
| **Calibration collapse** — single-sample or synthetic calibration (ADR-026) makes the w8a8 arm look arbitrarily bad | P2 forbids the fallback; ≥ tens of real samples; shared and checksummed |
| **Flag silently ignored** — the converter accepts `--act_bitwidth 8` but the build still emits a w8a16 graph | P3 verifies the two binaries differ by hash, and a device smoke test confirms the loading path |
| **fp32 graph defect** — both arms inherit the same bug and the A/B looks clean | P1 sanity-checks the fp32 ONNX on CPU before any quantization |
| **NPU timing noise** inverts a small RTF delta | ≥ 3 repeated runs in P5; report variance, not a single number |
| **Wrong artifact type** — the weight-tar is mistaken for the context binary | P3 verifies `.bin` output; M3 calls this out explicitly |
| **QAIRT version drift** — SDK upgraded from 2.31.0.250130 breaks on-device loading (silent failure, ADR-019) | Pin the SDK version; record it in the result table |
| **Scope creep into the decoder** (CPU path, ADR-023) | Encoder-only is stated in §1; reject decoder changes in review |
