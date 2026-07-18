# Onboarding to Kavi (kavi-prototype)

> A guide for new team members. It decodes the acronyms, the three foundational
> decisions (ADR-001 / 002 / 003), and how the repository is laid out — so you
> can read the rest of the docs without a translator. Pair this with
> `README.md` (the quickstart) and `CONTRIBUTING.md` (how we work).

## Start here — reading order (from zero to productive)

You probably arrived at the **public parent repo** (`aivoice-2026`). That repo
only holds the *story and public docs*; the **real code and internal docs live
in the private submodule** (`kavi-prototype`, under `prototype/`). Read in this
order — each step builds the mental model you need for the next.

```
aivoice-2026/                 (PUBLIC parent — what we tell the world)
├─ README.md                  ①  landing page
└─ docs/
   ├─ contest-info.md         ②  the contest + how we're graded
   └─ specifications.md       ③  our concrete targets + glossary
kavi-prototype/               (PRIVATE submodule — the real repo)
├─ README.md                  ④  pipeline + layout + how to run
├─ CONTRIBUTING.md            ⑤  cloning + tooling
└─ docs/
   ├─ onboarding.md           ⑥  this file — architecture, decoded
   ├─ benchmarking-plan.md    ⑪  datasets + candidate landscape + harness
   ├─ benchmarking-todo.md    ⑫  execution checklist
   └─ decisions/
      ├─ ADR-001 …            ⑦  100% offline, forever
      ├─ ADR-002 …            ⑧  one phone: Snapdragon 8 Gen 2
      ├─ ADR-003 …            ⑨  CPU now, NPU later
      ├─ ADR-004 …            ⑩  tech stack NOT decided yet
      └─ license-situation …  ⑬  license gate
```

**What to conclude from each:**

1. **Parent `README.md`** → the public landing page; the code is in the private
   `prototype/` submodule; public docs are just the contest brief + our spec.
2. **`docs/contest-info.md`** → Kavi is an entry to the **OneVoice AI Challenge**
   (Saigon AI Hub × Qualcomm, May–Nov 2026); an offline VI↔EN speech-to-speech
   translator; here are the contest rules + the six grading metrics.
3. **`docs/specifications.md`** → our translated targets — offline, RTF < 1.0,
   turnaround < 2.0 s, BLEU/COMET both ways, TTS MOS, stability — plus a newcomer
   acronym glossary. This is the scoreboard "good" is measured against.
4. **Submodule `README.md`** → the pipeline is **ASR → MT → TTS**, fully offline,
   VI↔EN; repo layout + how to run.
5. **Submodule `CONTRIBUTING.md`** (Cloning) → clone with `--recurse-submodules`;
   a plain parent clone skips the private submodule. Tooling: ruff + commitlint +
   pre-commit.
6. **`docs/onboarding.md`** (this file) → plain-language walkthrough of the three
   architecture decisions, so the ADRs below make sense without prior context.
7. **`ADR-001` (offline-first)** → **zero cloud, ever.** A network call during
   testing is an instant disqualification.
8. **`ADR-002` (target platform)** → we optimize for **one device** — Snapdragon
   8 Gen 2, Android 16, Hexagon HTP v73. Phone-only.
9. **`ADR-003` (Hexagon runtime)** → start on **CPU (ORT-XNNPACK int8)** —
   license-clean, ships today; add **NPU / QAIRT later** after on-device
   benchmarks. NNAPI rejected.
10. **`ADR-004` (architecture, draft)** → the **actual ASR / MT / TTS model
    choices are NOT made yet** — they wait for benchmark numbers. The doc the
    whole benchmarking effort feeds.
11. **`docs/decisions/license-situation.md`** → most candidates are license-clean;
    this gate is *why* we can pick safely. Two open items: the **Qualcomm QAIRT
    EULA** and the **Piper GPL split**.
12. **`docs/benchmarking-plan.md`** → we **benchmark before choosing** — datasets,
    the ASR/MT/TTS candidate landscape, the pluggable harness design, the lean v0.
13. **`docs/benchmarking-todo.md`** → the **execution checklist** (phases 0–7,
    checkboxes) to produce those numbers — what you'd actually pick up and work on.

> **Skip for now:** `archive/` (historical, superseded) and `docs/README.md`
> (just an index).

## What Kavi is, in one breath

Kavi is an entry to the **OneVoice AI Challenge** (Saigon AI Hub × Qualcomm,
May–Nov 2026): a **real-time speech-to-speech translator** for **Vietnamese ↔
English** (later Chinese, Korean) that runs **entirely on a phone**, with **no
internet**. It is built for workers in **factories, construction sites, and
logistics hubs** — noisy, hands-busy, low-connectivity places where cloud
translation fails.

The pipeline is a single local chain:

```
[mic] → VAD → denoise → ASR → MT → TTS → [speaker]
```

- **VAD** — Voice Activity Detection (find the speech, skip silence)
- **denoise** — strip industrial noise while keeping Vietnamese tone
- **ASR** — Automatic Speech Recognition (speech → text)
- **MT** — Machine Translation (text → text, VI↔EN)
- **TTS** — Text-to-Speech (text → spoken output)

Everything between the microphone and the speaker happens on-device.

## The three decisions you must know

These are the **Architecture Decision Records (ADRs)** in `docs/decisions/`.
Read them as "here is what we locked in, and why." They are the backbone of
everything else.

### ADR-001 — Offline-first, on-device (Accepted)

**Plain version:** Kavi runs 100% on the phone. No cloud, no network calls,
ever, while it is translating.

**Why:** the contest **disqualifies** any entry that touches the network during
testing. Separately, the actual users (factory floors) often have no reliable
connection — so offline is the product, not a fallback.

**What it forces:** every model must be small enough to run on the phone
**within ~2 seconds** end-to-end (turnaround < 2.0 s) and keep pace with live
speech (RTF < 1.0). It also means **no runtime telemetry** — analytics, if any,
are queued locally.

### ADR-002 — Target platform: Snapdragon 8 Gen 2, Android 16, Hexagon NPU (Accepted)

**Plain version:** we build and test for **one specific phone configuration**:
a **Snapdragon 8 Gen 2** running **Android 16**, using its **Hexagon NPU** (the
AI chip) as the primary compute, with **GPU → CPU** as fallback.

**Why:** Qualcomm co-hosts the contest and offers **Qualcomm AI Hub** — models
pre-optimized for Snapdragon. A phone is the required portable form factor.
Wearables / headsets are out of scope.

**What it forces:** models are compiled for that NPU generation (**HTP v73**);
benchmarks run on **real hardware** (emulators don't exercise the NPU); newer
Snapdragon 8 parts *may* work but aren't guaranteed.

### ADR-003 — Hexagon runtime strategy (Proposed — not final yet)

**Plain version:** the plan for *how* we reach that NPU is to use Qualcomm's
**QAIRT / QNN** runtime (via ONNX Runtime), with models **quantized**
(compressed to low-precision numbers) and **fixed input sizes**, falling back
to CPU if the NPU path isn't ready.

**Why provisional:** we haven't benchmarked on the real phone yet, so this ADR
will be amended once numbers exist.

**The catch that matters most:** our *current v0 harness* runs ASR via
**faster-whisper** (CTranslate2-backed) and MT via **CTranslate2** — and **neither
can be converted to QNN**. QNN only ingests PyTorch / TFLite / ONNX. So getting NPU speed likely
means **re-sourcing models in a convertible format** (e.g. Opus-MT → ONNX →
QAIRT). **NNAPI is explicitly avoided** (deprecated in Android 15; we target
16). The safe path is **CPU-first**, then layer NPU.

## Glossary — decode the cryptic

| Term | Plain meaning | Why it matters here |
| --- | --- | --- |
| **S2ST / S2S** | Speech-to-speech translation | What Kavi *is*. |
| **VI↔EN** | Vietnamese ↔ English | Our language pair (later ZH, KO). |
| **ADR** | Architecture Decision Record | A written, durable "we chose X because Y". In `docs/decisions/`. |
| **SoC** | System-on-Chip | The whole phone computer on one chip (CPU + GPU + NPU). |
| **NPU** | Neural Processing Unit | The chip's AI accelerator; far faster / power-efficient than CPU for models. |
| **Hexagon** | Qualcomm's NPU brand | Our NPU. |
| **HTP v73** | Hexagon Tensor Processor, version 73 | The 8 Gen 2's NPU generation. Compiled models are version-locked to it (8 Gen 3 = v75, 8 Elite = v79 / v81). |
| **QNN / QAIRT** | Qualcomm Neural Network / Qualcomm AI Runtime SDK (QNN rebranded at v2.32) | The runtime / compiler that runs models on Hexagon. Our planned primary path. |
| **ONNX** | Open Neural Network Exchange | A common, tool-agnostic model format. The lingua franca for conversion. |
| **ORT** | ONNX Runtime | The inference engine; talks to NPU / CPU / GPU via "Execution Providers". |
| **EP (Execution Provider)** | ORT's backend plugin | e.g. QNN EP (NPU), OpenCL EP (GPU), XNNPACK (CPU int8). |
| **DLC** | Deep Learning Container | Qualcomm's compiled model file. Preferred over raw context binaries (forward-compatible). |
| **AI Hub** | Qualcomm's model catalog + device farm | Free, build-time only; gives pre-optimized models and remote test devices. |
| **AIMET** | AI Model Efficiency Toolkit | Qualcomm tool for quantization, run on a PC (x86_64). |
| **int8 / w8a16** | 8-bit integer weights / 8-bit weights + 16-bit activations | The low-precision formats the NPU needs; w8a16 protects accuracy. |
| **NNAPI** | Android Neural Networks API | Avoided — deprecated in Android 15; we target 16. |
| **RTF** | Real-Time Factor | processing time ÷ audio time. **< 1.0** = faster than real-time (required). |
| **WER / CER** | Word / Character Error Rate | ASR accuracy (lower is better). |
| **BLEU / COMET** | MT quality metrics | Translation accuracy (higher is better). |
| **MOS** | Mean Opinion Score | Human-rated TTS naturalness (1–5). |
| **TTFT** | Time To First Token | Latency to first output from a streaming model. |
| **EOS→SA** | End Of Speech → Start of Audio | The < 2.0 s turnaround we must hit. |
| **VAD** | Voice Activity Detection | Finds speech, drops silence. |
| **CT2 / CTranslate2** | CPU MT runtime we currently use | Fast on CPU, but **not QNN-convertible**. |
| **faster-whisper / whisper.cpp** | Current v0 ASR runtime (faster-whisper, CTranslate2-backed) / alternative (whisper.cpp) | Same problem — **neither is QNN-convertible**; NPU needs re-sourcing. |
| **DQ** | Disqualification | What a network call during testing causes. |

## Repository layout — what lives where

This repo is a **fresh scaffold**; the previous implementation is preserved
under `archive/` for reference.

| Path | What it is |
| --- | --- |
| `archive/` | The old implementation (old `pipeline.py`, `architecture.md`, `design.md`, legacy ADRs, experiments). **Reference only — do not edit.** |
| `models/` | Checked-in model weights. Today: **Opus-MT vi-en** (CTranslate2 + SentencePiece) — our current MT. |
| `voices/` | TTS voice model(s) (Piper). Usually gitignored / downloaded at runtime. |
| `docs/` | Internal docs (this file's siblings). |
| `docs/decisions/` | The ADRs (001–004) + `license-situation.md`. Source of truth for architecture + licensing. |
| `docs/benchmarking-plan.md` | The plan to *measure* models before picking them (gates ADR-004). **Read this next.** |
| `AGENTS.md`, `CONTRIBUTING.md`, `README.md` | Project / agent guidance, how we work, quickstart. |
| `Makefile`, `pyproject.toml`, `LICENSE` | Build / run, deps (uv), MIT license. |
| `.github/` | CI (lint + changelog) and PR / issue templates. |

## The model-licensing rule (contest-critical)

The contest can lead to **commercialization**, so every model must permit
commercial use. This single rule eliminates several otherwise-attractive models.
Full detail is in `docs/benchmarking-plan.md` §4.4–§4.5.

- **Commercial-clean (use these):** Opus-MT (Apache-2.0), MeloTTS (MIT),
  MADLAD-400 (Apache-2.0), M2M-100 (MIT), Kokoro (Apache-2.0),
  vietTTS / VITS (MIT / Apache, verify InfoRe terms), SpeechT5 (MIT).
- **Live license decision — Piper:** **split / time-sensitive.** The old
  `rhasspy/piper` is **MIT** (frozen, no fixes); the active `OHF-Voice/piper1-gpl`
  is **GPL-3.0** (copyleft — problematic for a commercial product), and its
  `espeak-ng` phonemizer is also GPL. Our prototype pins an MIT-era build today,
  but we must decide pinned-version + distribution model (subprocess vs bundled)
  before shipping. See `docs/benchmarking-plan.md` §4.5.
- **Avoid (license blocks):** **NLLB** (CC-BY-NC), **MMS-TTS-vie** (CC-BY-NC),
  **Coqui XTTS** (CPML — restrictive; Coqui Inc. shut down Jan 2024).
- **Caution (verify):** **Hy-MT** (HY Community License — commercial-permitted
  *per old ADR-001*, but a regional carve-out is flagged by our current stance).

## Where the architecture is going (ADR-004)

The **tech stack** — exact ASR / MT / TTS models and runtimes — is **not yet
decided**. That is **ADR-004**, and it is intentionally deferred until the
**v0 benchmark harness** (spec'd in `docs/benchmarking-plan.md`) produces real
on-device numbers. The candidate landscape in that plan (§4) is the working
shortlist; the harness is what turns it into a decision.

## How to get running & next steps

1. **Clone** (see `CONTRIBUTING.md` → Cloning — it's a private submodule):

   ```bash
   git clone --recurse-submodules git@github.com:TanKhoiTV/aivoice-2026.git
   cd aivoice-2026/prototype && git checkout main
   ```

2. **Install & check:**

   ```bash
   uv sync
   make check
   ```

3. **Read in order** — see **Start here** (top of this guide): parent
   `README.md` → `contest-info.md` → `specifications.md`, then the submodule docs
   (`README.md` → this guide → `benchmarking-plan.md` → `docs/decisions/*`).
4. **The v0 harness is built** (`bench/`) — build the eval set and run it:

   ```bash
   make bench-data   # -> eval_manifest_v1.json (offline fallback until FLEURS downloads)
   make bench        # run the harness (offline smoke: Opus-MT vi->en + Piper EN TTS)
   make test         # run the pytest suite
   ```

   Feed the numbers into ADR-004.

> **If you remember nothing else:** Kavi is a fully-offline phone translator
> (VI↔EN); we target **one chip** (Snapdragon 8 Gen 2 / Hexagon HTP v73); the
> runtime path is **QAIRT / QNN via ONNX Runtime, CPU-first**; models must be
> **commercial-licensed** and **small enough for < 2 s**; and the **exact model
> choices are still TBD** behind ADR-004 + the benchmark harness.
