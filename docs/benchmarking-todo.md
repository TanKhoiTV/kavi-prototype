# Benchmark Harness — TODO & Execution Plan

> **Pitch doc for team members.** This is the *execution checklist* for the
> benchmarking work that gates **ADR-004 (architecture / tech-stack)**. It is
> derived from `docs/benchmarking-plan.md` (what we measure + datasets) and
> `docs/specifications.md` §3 (the six contest metrics). **No tech-stack decision
> is made here** — the harness is pluggable; we swap candidates in and score them
> against identical data.
>
> **Why this exists:** we run experiments *before* picking ASR / MT / TTS. The
> numbers this harness produces are what ADR-004 records as the architecture.

---

## 0. Goal

Stand up a **model-agnostic, pluggable benchmark harness** that, on a real
**Snapdragon 8 Gen 2**, produces the on-device numbers needed to choose the
speech-to-speech stack — and proves Kavi is **not worse than RTranslator** while
being **100% offline**.

---

## 1. Platform & method

- **Device:** Snapdragon 8 Gen 2 (Hexagon HTP v73), Android 16. GPU/CPU fallback.
- **Split architecture (two halves):**
  - **On-device runner** — Android instrumented test / thin service reads a run
    manifest, executes candidates, logs latency / RTF / peak RSS, dumps outputs.
  - **Off-device scorer** — host Python script ingests dumps + references and
    computes WER/CER, BLEU, COMET, MOS, RTF, turnaround, peak RAM. Scoring stays
    off the phone.
- **Pluggable by construction:** one thin adapter interface per stage —
  `ASRCandidate.transcribe`, `MTCandidate.translate`, `TTSCandidate.synthesize`,
  each returning `(text|audio, latency, peak_ram)`. Candidates are classes
  registered in a manifest; swapping needs **zero harness changes**.
- **Fairness:** a single **versioned `eval_manifest_v1.json`** (clean + noisy
  variants) is generated once, so every candidate is scored on **byte-identical
  inputs**.
- **Sequencing (de-risks Qualcomm dependency):** build the **host-side CPU-default
  harness first** (runs today, no Qualcomm access). Add the **on-device QNN path**
  only after the QAIRT runtime EULA is confirmed (see §8).

---

## 2. Metrics to capture

| Metric | Definition | Threshold | Hard/Target | Measured |
| --- | --- | --- | --- | --- |
| **RTF** (per stage + E2E) | compute time / audio duration | **< 1.0** | **Hard** | runner |
| **Turnaround** (EOS→SA) | VAD end-of-speech → first synthesized-audio sample | **< 2.0 s** | **Hard** | runner (instrumented) |
| **No internet at runtime** | zero network calls during a run | **none allowed** | **Hard (DQ)** | runner monitor |
| **ASR WER / CER** | per language, clean + per-SNR | minimize | Target | scorer |
| **MT BLEU** | both directions, clean ref + cascaded ASR output | maximize | Target | scorer (`evaluate`) |
| **MT COMET** | both directions, clean + cascaded | maximize | Target | scorer (`Unbabel/wmt22-comet-da`) |
| **TTS MOS** | output naturalness | maximize | Target | DNSMOS proxy (v0/v1) + human panel (v1) |
| **Peak RAM** | per stage + combined | beat RTranslator bar | Target | runner (RSS) |
| **Stability** | crash / silent-failure rate over N runs | minimize | Named contest metric | runner |

---

## 3. Models to benchmark (candidates)

> License-clean set only (see `docs/decisions/license-situation.md`). "v0?" =
> in the first lean harness.

### ASR

| Candidate | License | Runtime (v0) | EN+VI? | v0? |
| --- | --- | --- | --- | --- |
| Whisper Small (244M) | MIT | CPU + QNN | **Yes** | **Yes** (baseline pair) |
| PhoWhisper Small (244M) | BSD-3 | CPU + DIY QNN | Inherited (unbench) | Follow-up |
| Zipformer-30M-VI | Apache-2.0 | CPU / DIY | **VI only** | No (VI→EN only) |
| Moonshine Tiny VI (27M) | Apache-2.0 | CPU / DIY | **VI only** | No (VI→EN only) |

### MT

| Candidate | License | Runtime (v0) | Bidirectional? | v0? |
| --- | --- | --- | --- | --- |
| Opus-MT (vi-en + en-vi) | Apache-2.0 | CTranslate2-int8 / ORT+QNN | **Yes (2 models)** | **Yes** (baseline pair) |
| M2M-100 (418M) | MIT | CPU / ONNX-QNN | Yes (one model) | Follow-up |
| Hy-MT1.5-1.8B | HY Community (ADOPT) | CPU-only STQ | Yes (one model) | Follow-up |
| NLLB-200-distilled-600M | CC-BY-NC-4.0 | — | Yes | **Reference only** (NC) |
| SeamlessM4T v2 | CC-BY-NC-4.0 | — | Yes | Avoid (NC) |

### TTS

| Candidate | License | Runtime (v0) | VI + EN voice? | v0? |
| --- | --- | --- | --- | --- |
| Piper (MIT-era `rhasspy/piper`) | MIT | CPU (+ QNN later) | EN yes; VI `vais1000` (CC-BY-4.0) | **Yes** (EN leg) |
| MeloTTS | MIT | CPU / ONNX-QNN | EN/ZH/ES on Hub; VI needs self-export | Follow-up |
| Kokoro | Apache-2.0 | CPU | **EN only** | EN-leg only |
| vietTTS / VITS-VI | VITS MIT (verify) + InfoRe terms | CPU / DIY | VI yes | If InfoRe clears |
| MMS-TTS-vie | CC-BY-NC-4.0 | — | VI yes | Avoid (NC) |

### Baseline (product comparator)

| Candidate | How | Notes |
| --- | --- | --- |
| **RTranslator** (APK v2.1.5) | Semi-manual: install on 8 Gen 2, run lean set via UI, capture outputs | Latency/RAM from **published table (author-reported)**; quality we measure. **Snapshot exact version/commit + date** — 3.0 is imminent and swaps NLLB for HY-MT. |

---

## 4. Datasets & eval set

**Lean eval set (~40–60 utts/direction):** VIVOS test slice (VI anchor),
Common Voice-en / LibriSpeech (EN), + a **bespoke 150–300-sentence VI↔EN gold
set** skewed to factory/logistics vocabulary (equipment, safety, numbers,
imperatives). Scale to full VSS/PhoST/FLEURS only after narrowing to 1–2
finalists per stage.

**Noise bank (factory / construction / logistics):** MUSAN (PD), RIRS_NOISES
(CC-BY-4.0, RIR convolution), DEMAND (CC-BY-SA-3.0, attribution+share-alike),
NOISEX-92 (eval-only), Freesound (per-clip CC, construction/logistics packs).

**SNR sweep (applied at eval time, not baked in):**

| Condition | SNR | Purpose |
| --- | --- | --- |
| Clean | ∞ | ceiling |
| Mild | +15 dB | light background |
| Moderate | +10 dB | workable |
| Hard | +5 dB | loud warehouse / near-forklift |
| Severe | 0 dB | stress |
| (stretch) Worst | −5 dB | stability only |

Run each SNR against **≥2 noise types** (steady/mechanical vs babble/impulsive) —
a single averaged "noisy" number hides the failure mode.

**License hygiene:** VIVOS / viVoice / NOISEX-92 = eval-only, never bundle.
PhoST = eval-only (research/no-redistribution). VSS = MIT (commercial-safe, but
pseudo-labeled refs). Common Voice / LibriSpeech / FLEURS / LibriTTS / MUSAN /
RIRS_NOISES = public-safe.

---

## 5. Target numbers to beat

| Target | Value | Source | Type |
| --- | --- | --- | --- |
| **RTranslator latency** | Whisper-Small RT-optimized **0.9 GB / 1.6 s** per 11 s audio | §5 published table (author-reported) | Anchor — Kavi must not be worse |
| **RTranslator latency (MT)** | NLLB-600M optimized **1.3 GB / 2 s** per 75 tok | §5 | Anchor |
| **RTF** | **< 1.0** | §7 hard gate | Pass/fail |
| **Turnaround** | **< 2.0 s** (EOS→SA) | §7 hard gate | Pass/fail |
| **No internet** | **0 calls** | §7 hard gate | DQ if violated |
| VI ASR WER (reference) | PhoWhisper **6.33** (VIVOS) / **11.08** (CMV-Vi); Whisper Small **~20–25%** (VIVOS) | §4.1 | Ranking, not pass/fail |
| MT BLEU (reference) | Opus-MT vi→en **42.8** / en→vi **37.2** (Tatoeba) | §4.4 | Ranking |
| MT COMET (vi↔en) | **none published** → we measure | §4.4 caveat | We produce |
| TTS MOS (VI) | **none published** → human panel | §4.5 caveat | We produce |
| Denoising gate | raw-noisy WER ceiling **20.23%** @ SNR5 (Whisper Medium) | §8 | Beat raw-noisy to keep denoiser |

> **Re-measure on our unit:** all RTranslator figures are author-reported on an
> unknown device — treat as order-of-magnitude, confirm on our 8 Gen 2.

---

## 6. Number of runs

- **v0 (exploration):** single device, **single run per config**. Enough to see
  trend breaks between CPU vs QNN and across candidates.
- **Final confirmation:** **≥ 3 runs per config**, averaged, once we narrow to
  1–2 finalists per stage.
- **Stability metric:** **N consecutive runs** (propose N = 10) per final config,
  record crash / silent-failure rate.
- **Scale-up trigger:** only expand the lean set to full corpora after finalists
  are chosen — keep iteration cheap early.

---

## 7. Phased TODO

### Phase 0 — Setup

- [ ] Branch + deps: add `datasets`, `torchaudio`, `evaluate`, `comet` to the
      dev environment (uv-managed).
- [ ] Agree `eval_manifest_v1.json` schema (stage, candidate_id, model_path,
      config, audio_ref, transcript_ref, snr, noise_type).

### Phase 1 — Data prep (host)

- [ ] Download lean eval set: VIVOS test slice, Common Voice-en/LibriSpeech,
      bespoke VI↔EN gold set (factory/logistics vocab).
- [ ] Download noise bank: MUSAN, RIRS_NOISES, DEMAND; stage NOISEX-92 eval-only.
- [ ] Generate noisy variants via `torchaudio.add_noise` + `fftconvolve` +
      `resample` across the §4 SNR sweep × ≥2 noise types.
- [ ] Emit versioned `eval_manifest_v1.json` (clean + noisy, byte-identical).

### Phase 2 — Host harness (CPU-default, runs today)

- [ ] Implement adapter interfaces (`ASRCandidate` / `MTCandidate` /
      `TTSCandidate`).
- [ ] Implement CPU candidates: whisper.cpp-int8 (ASR), CTranslate2-int8-OpusMT
      (MT), Piper-CPU (TTS, EN leg + `vais1000` VI voice).
- [ ] Implement off-device scorer: WER/CER (`evaluate`), BLEU (`evaluate`),
      COMET (`Unbabel/wmt22-comet-da`), RTF/turnaround/RAM from runner logs.
- [ ] Run manifest fan-out; emit comparison table.

### Phase 3 — First CPU numbers

- [ ] Run v0 slice (30–50 utts: clean / +5 dB / 0 dB, both langs + directions).
- [ ] Report WER / BLEU / RTF / turnaround / peak RAM for CPU candidates.
- [ ] Wire RTranslator pseudo-row (manual APK run; published latency/RAM flagged
      author-reported).

### Phase 4 — On-device runner (QNN)  ⚠️ blocked on Qualcomm QAIRT EULA

- [ ] Compile Whisper-Small-Quantized-QNN `.dlc`, ORT+QNN-OpusMT, Piper-QNN.
- [ ] Android instrumented runner: read manifest, run candidates, log latency/
      RTF/peak RSS, dump outputs.
- [ ] Re-run v0 slice on-device; answer: **does QNN meaningfully beat CPU?**

### Phase 5 — RTranslator row (full)

Pre-conditions: airplane mode on, Play Services network blocked if possible; compare
against **WalkieTalkie** mode (not Conversation — see plan §5.1). Record per the §5.5
checklist.

- [ ] Document exact APK **version + commit hash** + date tested (2.1.5 = commit
      `49e7f20`, tagged 2026-02-22 — grab the hash, not just the tag).
- [ ] Record device / chipset / RAM / Android version / thermal state, and which
      **mode** was tested (Conversation / WalkieTalkie / Text).
- [ ] Record **system-TTS engine + version** (TTS is not bundled — see plan §5.3) and
      the **RAM-mode switch** state (0.9 GB vs 0.5 GB Whisper variant).
- [ ] Confirm **network state** during the run (airplane mode on; verify no calls,
      given the system-TTS / ML Kit first-use download caveats).
- [ ] Score RTranslator outputs on the same references (WER/BLEU/MOS) via the lean set.
- [ ] Flag all RTranslator latency/RAM as **author-reported**; re-measure on our unit.
- [ ] If a **3.0 beta** is tested, label every number with its backend generation
      (NLLB vs HY-MT/Bergamot/Madlad) — they are not the same product.

### Phase 6 — Pre-ASR denoising gate

- [ ] Add denoising toggle (raw vs Wiener `prop_decrease=0.5` vs RNNoise
      `stationary=False`) as a fixed factor in v0 slice (mixing per §4, not the
      archived custom RMS mix).
- [ ] Trigger binary gate: denoiser beats raw-noisy WER → tune `prop_decrease`;
      else VAD-only pipeline.

### Phase 7 — v1 (quality depth)

- [ ] Add COMET both directions (clean + cascaded ASR output).
- [ ] Add MOS: DNSMOS proxy + small human panel (5–10 raters, 20–30 clips).
- [ ] Averaging (≥3 runs) + stability (N=10) for final configs.

---

## 8. Open gates / blockers

| Blocker | Status | Unblocks |
| --- | --- | --- |
| **Qualcomm QAIRT runtime EULA** | escalate (detailed instructions pending) | Phase 4 (on-device QNN) |
| **Piper engine GPL split** | deferred — MIT-era `rhasspy/piper` + subprocess is default option | TTS candidate finalization |
| **InfoRe donation terms** | verify before relying | vietTTS VI voice |
| **VI→EN ST corpus** | FLEURS ID-alignment vs bespoke gold (or both) | EN→VI eval coverage |
| **RTranslator 3.0 imminent** | snapshot version/date when tested | fair comparison |

---

## 9. References

- `docs/benchmarking-plan.md` — datasets, candidate landscape, harness design, v0.
- `docs/specifications.md` §3 — the six contest metrics + thresholds.
- `docs/decisions/ADR-004-architecture.md` — tech-stack deferred; open params #1–4.
- `docs/decisions/license-situation.md` — license-clean candidate set.
- ADR-001 / 002 / 003 — offline-first, target platform, Hexagon runtime.
- `docs/onboarding.md` — architecture decoded for newcomers.
