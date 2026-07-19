# Phase 4 — On-device QNN Conversion & Comparison Plan

> **Status:** Planning (precedes and parallels the Phase-4 implementation, job (1))
> **Companion docs:** `benchmarking-todo.md` §Phase 4, `ADR-003` (Hexagon runtime, *Proposed*), `ADR-004` (architecture, *Draft*).
> **Tracking:** issue #51.

## 0. Purpose

This is the **executable spec** for Phase 4 (on-device QNN). It turns ADR-003's
provisional determination method into concrete, pinned steps:

- how each v0 candidate is converted to a QAIRT / QNN artifact,
- how those artifacts are bundled into the Android app,
- how the on-device comparison runner works, and
- the pass/fail gates that decide whether **QNN becomes the NPU path**.

It is written **before (and in parallel with)** the actual conversion work (job
(1)) so the implementation has a fixed target. The CPU-only baseline already runs
(Phase 2–3), so QNN here is an *optimization pass* layered on top, not a
greenfield build.

---

## 1. Environment contract (host, build-time only)

All conversion happens **off-device** on a Linux x86_64 host. The artifacts
(`.dlc`, HTP v73 context binary, `libQnn*.so`) are **host-independent** — byte
identical regardless of the developer's OS — and are committed so every commit
builds.

| Item | Value | Notes |
| --- | --- | --- |
| **QAIRT SDK** | `2.31.0.250130` (Linux x86_64) at `QAIRT_SDK_ROOT` | **Must match** the device `qnn-2.31` / **HTP v73** runtime. Do **not** upgrade — ABI drift breaks on-device loading. Outside the repo. |
| **ANDROID_NDK_ROOT** | NDK r26c (`26.1.10909125`) | Matches `archive/`/`sdk.yaml` pin. |
| **Env helper** | `qairt-env.sh` | `source`s `bin/envsetup.sh` (sets `QNN_SDK_ROOT`, `SNPE_ROOT`) and exports `LD_LIBRARY_PATH` (venv `libpython3.10` + `$QAIRT_SDK_ROOT/lib/x86_64-linux-clang`). |
| **Converter venv** | Python 3.10 (`qairt-converters`) | `onnx 1.16.1`, `onnxruntime 1.17.1`, `numpy<2`, `onnx-simplifier`, `scipy`, `lxml`, `absl-py`, `pandas`. |
| **Converters** | `qnn-onnx-converter`, `qnn-context-binary-generator` | Under `$QAIRT_SDK_ROOT/bin/x86_64-linux-clang`. |
| **Device** | Meizu 21 Note — SD 8 Gen 2 (`kalama`), **Android 16 (API 36)**, **HTP v73**, `qnn-2.31` | Runtime **preinstalled**; app **bundles** `libQnn*.so`. |

**Offline guarantee:** the SDK is build-time only; the on-device runtime is
preinstalled firmware + the bundled `.so`. No network at app runtime.

---

## 2. Conversion pipeline (per model)

```
sourceable model (PyTorch / TFLite / ONNX)
        │
        ▼
  qnn-onnx-converter        →  <model>.dlc        (w8a16 quant: int8 wts / int16 acts)
        │
        ▼
  qnn-context-binary-generator --htp_arch v73   →  HTP v73 context binary
```

- **Quantization required:** HTP only executes quantized graphs; **w8a16**
  (int8 weights / int16 activations) recommended to protect transformer accuracy.
  HTP silently rejects unquantized graphs.
- **No dynamic shapes:** batch / sequence length must be **fixed** (padding +
  masking). This is the main engineering cost for the autoregressive ASR / MT
  decoders.
- **Artifact choice:** prefer **DLC** over a context binary for forward-compat
  across QAIRT SDK versions; generate the v73 context binary for the NPU path.

---

## 3. Model-by-model export plan

The current v0 CPU-default candidates are **not QNN-convertible as-is**
(`faster-whisper`/ggml for ASR, `CTranslate2` for MT). QNN converters ingest
**PyTorch / TFLite / ONNX only**, so NPU acceleration requires *re-sourcing* in a
convertible format. Per ADR-003 the stance is **evaluate** (not retire) — the
benchmark below is what decides.

### 3.1 ASR — Whisper Small (244M, MIT) — *evaluate re-source*

- **v0 (CPU):** `faster-whisper` Small int8 — ggml, **not** QNN-convertible.
- **For QNN:** export Whisper Small to **ONNX** (e.g. `optimum` Whisper ONNX
  export), **or** use Qualcomm-optimized **Whisper-Small-Quantized** (w8a16) from
  AI Hub Models.
- **Hard part:** the autoregressive decoder needs **fixed-sequence handling** —
  KV-cache / padded decoding, because **no dynamic shapes** are allowed. This is
  the riskiest conversion; budget time for it.
- **Output:** `.dlc` + v73 context binary.

### 3.2 MT — Opus-MT vi↔en (Helsinki-NLP, PyTorch, Apache-2.0)

- **v0 (CPU):** `CTranslate2`-int8 Opus-MT, **vi→en only** (en→vi weights not in
  repo). CTranslate2 is **not** QNN-convertible.
- **For QNN:** re-export from the **original Helsinki-NLP PyTorch** model → ONNX
  → `qnn-onnx-converter` → `.dlc` (w8a16). No AI Hub prebuilt exists for Opus-MT;
  the en-es recipe is a template.
- **Scope:** export **vi→en** (v0 need) and **en→vi** if the bidirectional eval
  set requires it.
- **Output:** `.dlc` + v73 context binary.

### 3.3 TTS — Piper (MIT-era `rhasspy/piper`, ONNX)

- **v0 (CPU):** Piper-CPU, **EN leg only** (`vais1000` VI voice not in repo).
- **For QNN:** Piper is **already ONNX** → short hop through `qnn-onnx-converter`
  → `.dlc`. Check **Vietnamese** voice coverage (e.g. `vais1000`, CC-BY-4.0) in
  the QAIRT/AI Hub Piper path.
- **Output:** `.dlc` + v73 context binary.

---

## 4. Artifact layout & bundling

- **Host-independent outputs** (`.dlc`, v73 context binary, `libQnn*.so`) are
  **committed** so every commit builds — no developer needs the SDK to build.
- **Location in `kavi-android`:**
  - `app/src/main/jniLibs/arm64-v8a/` — `libQnn*.so` (39 `.so` already bundled)
    plus the compiled model `.so`/`.dlc` loaders.
  - `app/src/main/assets/` — model `.dlc` + HTP v73 context binaries (read at
    runtime, kept out of `jniLibs` binary load path if preferred).
- **License:** AI Stack License §1(iv) permits distributing the runtime in object
  code within the app; `public.libraries.txt` does **not** list `libQnn*.so`, so
  the app **bundles** them (ADR-002 / QAIRT gate *ADOPT clean*).

---

## 5. On-device instrumented runner

- **Form:** Android **instrumented test** / thin **service** that reads the
  **same versioned `eval_manifest_v1.json`** the host scorer uses — so QNN and CPU
  candidates are scored on **byte-identical inputs**.
- **Per-utterance logging:** latency, **RTF**, **turnaround (EOS→SA)**,
  **peak RSS**, plus dumped audio/text outputs.
- **Network monitor:** assert **zero network calls** during a run (hard DQ gate).
- **Scoring off-device:** dumps are pulled to the host and scored by
  `bench/scorer.py` (jiwer WER/CER, sacrebleu BLEU; COMET/MOS deferred to Phase
  7) — identical pipeline to the CPU baseline.

---

## 6. Comparison & success gates

For each stage × candidate runtime `{QNN, CPU-default}`, measure RTF,
turnaround, WER/BLEU, peak RAM.

**Hard gates (from `benchmarking-todo.md` §2):**

| Gate | Threshold | Type |
| --- | --- | --- |
| **RTF** | **< 1.0** | Hard |
| **Turnaround** (EOS→SA) | **< 2.0 s** | Hard |
| **No internet** | **0 calls** | Hard (DQ) |

**Per-stage decision rule (ADR-003):** adopt QNN for a stage **iff** it meets the
hard gates **and** beats the CPU baseline on RTF / turnaround **without**
accuracy regression (WER/BLEU within tolerance). Otherwise fall back to CPU for
that stage.

This comparison **closes ADR-003** (→ *Accepted*) and feeds the per-stage picks
that finalize **ADR-004** (tech stack).

---

## 7. Sequencing & risks

- **CPU-first already done** (Phase 2–3): the baseline exists, so a QNN toolchain
  snag cannot block the submission.
- **Risks:**
  - ASR decoder **fixed-shape reformulation** (KV-cache / padded decode) — the
    heaviest lift.
  - **QAIRT version must match** the device (`2.31.0.250130` = `qnn-2.31` / HTP
    v73); do not upgrade the SDK.
  - Toolchain env verified (`libc++1` installed; `qairt-converters` venv runs
    `qnn-onnx-converter`/`qnn-context-binary-generator`).
- **Deferred:** COMET + human MOS depth (Phase 7); pre-ASR denoising gate (Phase
  6).

---

## 8. Status / tracking

- **Precedes** job (1) (the actual conversion). Implementation tracks this spec.
- **Related:** `benchmarking-todo.md` §Phase 4 (terse checklist), `ADR-003`
  (determination method → this plan), `ADR-004` open params #1–4.
- **Issues:** #51 (this doc), #52 (ADR-003 tightening).
