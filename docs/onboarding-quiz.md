# Onboarding Quiz — Kavi current state

> A checkpoint to confirm a new member understands Kavi's **current** architecture,
> licensing, and benchmarking state — not trivia, but which decisions are *locked*
> vs *deferred*, and the hard constraints that disqualify options.
> Answer key + rubric in **Appendix A**. Pair with `onboarding.md` (Start here)
> and the ADRs in `docs/decisions/`.
>
> ~30–45 min. Mix of short-answer, scenario, and classification.

## Questions

**Q1 — Scenario (licensing + offline).** *Source: ADR-001, ADR-029.*
OneVoice grades on a hidden benchmark with **no internet allowed at runtime**, and
the contest can lead to **commercialization**. A teammate proposes swapping our MT
to **NLLB-200-distilled-600M** because it scores highest on FLORES-200. What is
wrong with this proposal, and what would you suggest instead?

**Q2 — Classification (decided vs deferred vs open).** *Source: ADR-001/002/003, ADR-029, `decisions/README.md`.*
Classify each as **DECIDED**, **DEFERRED**, or **OPEN**:
(a) Kavi runs fully offline · (b) target device is Snapdragon 8 Gen 2 · (c) the
NPU runtime is QAIRT/QNN · (d) the exact ASR model · (e) Hy-MT is commercially
usable · (f) Piper's distribution model (subprocess vs bundled) · (g) the Qualcomm
runtime EULA for shipping QNN model artifacts (model `.so` + context binary).

**Q3 — Short answer (benchmark method).** *Source: `decisions/README.md` (open parameters), reference/benchmarking-plan §8.*
Why do we stand up a benchmark harness **before** finalizing the ASR/MT/TTS stack?
What is the **single question the v0 harness must answer**, and name **one thing v0
deliberately leaves out**?

**Q4 — Short answer (target platform).** *Source: ADR-002.*
Name the exact target SoC, Android version, and NPU generation Kavi is built for.
What form factor is explicitly **out of scope**, and why must benchmarks run on
real hardware rather than an emulator?

**Q5 — Scenario (runtime choice).** *Source: ADR-003.*
A member suggests using **NNAPI** for the NPU path because it is Android-native and
needs no Qualcomm SDK. What is wrong with this, and what is our actual planned path?

**Q6 — Short answer (model portability).** *Source: ADR-003.*
Our current prototype runs ASR via **whisper.cpp** and MT via **CTranslate2**. Why
can't these simply run on the Hexagon NPU today, and what does reaching NPU speed
likely require?

**Q7 — Short answer (baseline).** *Source: reference/benchmarking-plan §5.*
RTranslator is our product baseline. What latency/RAM figure must Kavi **not be
worse than**? What is our **verifiable offline advantage** over RTranslator, and
what must you **record** when testing it?

**Q8 — Practical (repo layout).** *Source: onboarding Start here, CONTRIBUTING.*
A new member runs `git clone git@github.com:TanKhoiTV/aivoice-2026.git` and finds
`prototype/` empty. Why, and what is the correct clone command?

**Q9 — Classification (metrics).** *Source: specifications §3, reference/benchmarking-plan §7.*
Label each as **Hard gate**, **Target**, or **Named contest metric**: RTF ·
EOS→SA turnaround · no-internet-at-runtime · MT BLEU + COMET · TTS MOS · stability
(crash / silent-failure rate).

**Q10 — Short answer (denoising gate).** *Source: `reference/denoising-gate-results.md`.*
The Phase-6 denoising gate ran a smoke test (2 utterances × 5 conditions) on
faster-whisper Small int8. What was **ADOPTED** and at what weighted-average WER,
and what caveat does the results file flag before the on-device denoiser pick closes?

**Q11 — Scenario (TTS voice licensing).** *Source: ADR-029, ADR-009.*
A member picks the Piper **`vivos`** Vietnamese voice because it is a real VI
voice and easy to find. What is wrong, and what is the **v1 TTS plan** that
supersedes the Piper voice question?

**Q12 — Short answer (VI↔EN speech-translation corpus).** *Source: reference/benchmarking-plan §3.3.*
Why can't we build the VI↔EN test set from **CoVoST-2** or **MuST-C**? What purpose-
built corpus covers the **EN→VI** direction, and what are the two **VI→EN**
workarounds?

---

## Appendix A — Answer key & rubric

**Q1.** Offline is necessary but *not* the blocker (NLLB runs offline). The blocker
is **licensing**: NLLB is **CC-BY-NC-4.0 → non-commercial → disqualifying** for a
commercial product; it is **reference-only**. Suggest **Opus-MT (Apache-2.0)**,
**M2M-100 (MIT)**, or **Hy-MT1.5 (ADOPT)**. *Rubric: identifies the NC license as
the killer + names ≥1 clean alternative.*

**Q2.** (a) DECIDED (ADR-001) · (b) DECIDED (ADR-002) · (c) DEFERRED / provisional
(ADR-003 = CPU-first, NPU later) · (d) DECIDED (ADR-008 Dual Zipformer ASR, ADR-009 Supertonic TTS; the MT choice remains open) ·
(e) DECIDED (ADR-029: Hy-MT ADOPT for Vietnam; 100M MAU noted as a
sky-high ceiling) · (f) OPEN / deferred (ADR-031 Piper GPL split) · (g) DECIDED (ADR-030: QAIRT runtime
ADOPT, clean — no escalation required). *Rubric: all 7 correct = pass; (c)/(f) are
the common mistakes.*

**Q3.** We benchmark **before** picking so the decision is evidence-based, not
assumed (the tech-stack register is gated by numbers). v0 must answer: **"does QNN meaningfully
beat CPU on this chip for these models, before we sink days into harder QNN
engineering?"** v0 deliberately **defers COMET + human MOS** (and runs a single
device / single run). *Rubric: names the QNN-vs-CPU question + at least one
omission.*

**Q4.** **Snapdragon 8 Gen 2**, **Android 16**, **Hexagon HTP v73** (NPU). **Phone-
only** — wearables / headsets out of scope. Emulators don't exercise the NPU, so
benchmarks must run on **real hardware** (newer 8-series may work as supersets but
aren't guaranteed). *Rubric: SoC + Android + HTP v73 + phone-only + real-hardware.*

**Q5.** **NNAPI is deprecated in Android 15**; we target **16**, so it is rejected
as a fallback. Planned path: **QAIRT / QNN via ONNX Runtime** (QNN EP), with CPU
(ORT-XNNPACK int8) as the license-clean baseline / fallback. *Rubric: names NNAPI
deprecation + QNN/ORT + CPU fallback.*

**Q6.** **QNN only ingests PyTorch / TFLite / ONNX**; whisper.cpp (ggml) and
CTranslate2 are **not QNN-convertible**. Reaching NPU speed likely means **re-
sourcing models in a convertible format** (e.g. Opus-MT → ONNX → QAIRT). *Rubric:
format-ingestion limit + re-source implication.*

**Q7.** Not worse than RTranslator's **Whisper-Small RT-optimized: 0.9 GB / 1.6 s
per 11 s audio** (and NLLB-600M optimized 1.3 GB / 2 s per 75 tok) — author-
reported, so re-measure on our unit. Our advantage: **bundled Piper = verifiable
100% offline** (RTranslator relies on the user's system TTS). Record: **exact APK
version / commit + date** (RTranslator 3.0 is imminent and swaps backends).
*Rubric: cites the anchor + offline advantage + version snapshot.*

**Q8.** `prototype/` is a **submodule** skipped by a plain parent clone (it is
public, like the parent). Fix: `git clone --recurse-submodules …` then
`cd prototype && git checkout main`.
*Rubric: identifies the submodule + gives the recurse command.*

**Q9.** Hard gate: **RTF < 1.0**, **turnaround < 2.0 s**, **no-internet (DQ)**.
Target: **BLEU + COMET**, **MOS**. Named contest metric: **stability**. *Rubric: the
three hard gates are the common miss.*

**Q10.** The Phase-6 gate **ADOPTED Wiener** (`noisereduce`, `prop_decrease=0.5`):
weighted-average WER **49.82%** on noisy conditions vs raw **51.23%**; RNNoise
**REJECTED** (64.36%). Caveat: smoke test only (2 utterances × 5 conditions) — a
full lean-slice eval is still pending before the on-device denoiser pick closes, and the
on-device GTCRN-vs-Wiener pick (ADR-018) remains open.
*Rubric: names Wiener + 49.82% vs 51.23% + the smoke-test caveat.*

**Q11.** `vivos` inherits **VIVOS CC-BY-NC-SA-4.0 (research-only)** → must not ship.
The **v1 TTS plan (ADR-009)** supersedes the Piper voice question: **Supertonic
Phase 1** via sherpa-onnx `OfflineTts` (VI + EN voices, lang-switch per ASR
lang-ID), **VieNeu-TTS Phase 2** later; Piper VITS is demoted to **fallback only**
— pin the MIT-era `rhasspy/piper` snapshot then. *Rubric: names the NC taint +
ADR-009 Supertonic Phase 1.*

**Q12.** **CoVoST-2** translates 21 langs→EN + EN→15 (Vietnamese in neither);
**MuST-C** is EN-source only — so neither covers Vietnamese speech translation.
EN→VI is covered by **PhoST** (EN audio→VI text; research-only / no-redistribution).
VI→EN workarounds: **FLEURS-vi ID-alignment** with FLEURS-en (CC-BY-4.0), or a
**bespoke 150–300-sentence gold set** with human EN translations. *Rubric: explains
the CoVoST/MuST gap + PhoST direction + two VI→EN workarounds.*
