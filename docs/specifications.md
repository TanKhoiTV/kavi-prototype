# Kavi — Technical Specifications & Grading

> **Audience:** new Kavi team members with no speech / ML background.
> **Companion doc:** [Contest Information](contest-info.md) §4 (Evaluation & Benchmarks).
> **Purpose:** translate the contest's grading rules into the concrete targets Kavi must hit, and define every acronym in plain language.

---

## 1. Goal

Kavi is a **fully offline, on-device speech-to-speech translator** for Vietnamese ↔ English (later Chinese and Korean). The OneVoice AI Challenge grades every solution on three dimensions:

| Dimension | Weight |
| --- | --- |
| Innovation & Novelty | 25% |
| **Technical Excellence** | **50%** |
| Business Impact & Real-World Potential | 25% |

This document focuses on the **50% Technical Excellence** column, because that is where the contest's *objective, scoreable metrics* live. Our goal is unambiguous: **maximize those objective scores while staying 100% offline and inside the latency budget.**

The remaining 50% (Innovation, Business Impact) is judged subjectively by the panel — important, but not something a spec can pin down to a number.

---

## 2. Grading Overview (what "Technical Excellence" covers)

Within the 50% Technical Excellence weight, judges look at four things (from the contest brief):

- **Translation accuracy** — how correct the translated text is.
- **Processing speed and responsiveness** — how fast the system keeps up with real conversation.
- **Low-latency communication** — the wall-clock delay a user feels.
- **Stability and operational performance** — does it run reliably end-to-end.

The first three map directly onto the six objective metrics in §3. "Stability" is a judge judgement, not a published number — we cover it by building a robust pipeline (see the architecture work, deferred for now).

---

## 3. Technical Excellence — The Metrics (the excerpt)

These are the **six objective metrics** taken from the Luma scoring criteria. Each is explained in plain language for readers new to the field. Targets we must hit are called out in **bold**.

### 3.1 Accuracy — BLEU + COMET

**What it measures:** how close Kavi's translated text is to a professional human reference translation of the same speech.

- **BLEU** (Bilingual Evaluation Understudy) — counts how many word chunks (1-, 2-, 3-, 4-grams) in our output also appear in the reference. Higher = fewer word/phrase errors. Plain version: *"did we use the right words?"* Scores run 0–100 but realistically land around 20–50 for hard language pairs.
- **COMET** — a neural model that scores *meaning* similarity, not just word overlap. Plain version: *"did we say the same thing?"* It catches cases where BLEU looks fine but the meaning drifted.

**Why both?** BLEU can be inflated by short, safe outputs; COMET keeps us honest about meaning. Judges score the pair together, so we track both.

> **Target:** maximize. We will record our BLEU/COMET against a public proxy (e.g. a public MT baseline) and watch it as we tune.

### 3.2 Naturalness — MOS (Mean Opinion Score)

**What it measures:** how natural and human the *spoken* translation sounds.

- A **panel of native speakers** listens to Kavi's synthesized voice and rates it **1–5** (1 = bad, 5 = excellent). That average is the **MOS** (Mean Opinion Score).
- They judge two things:
  - **Prosody** — the rhythm, stress, and intonation of speech (what makes a voice sound human instead of robotic).
  - **Clarity** — how easy it is to understand.

We don't run the panel (the contest does), but MOS is driven by our choices: the **TTS voice** and **denoising** upstream so the input speech is clean before synthesis.

> **Target:** maximize MOS via a high-quality offline TTS + clean input audio.

### 3.3 Speed — RTF & Turnaround Latency

**What it measures:** whether Kavi keeps pace with a live conversation.

- **RTF — Real-Time Factor** = (processing time) ÷ (audio duration).
  - **RTF < 1.0 required.** Plain version: *if a 10-second clip is processed in under 10 seconds, you're ahead of real time.* RTF > 1.0 means the system is falling behind.
- **Turnaround Latency** = time from **End of Speech (EOS)** → **Start of Audio synthesis (SA)**.
  - **Total < 2.0 s required.** Going over incurs *significant point deductions*.
  - Plain version: *the moment you stop talking, you should hear the translated voice start within 2 seconds.*

This 2.0 s budget has to cover the whole pipeline — **ASR** (speech→text) + **MT** (text→text) + **TTS** (text→voice), plus any denoising. That budget is what shapes our pipeline design (a performance budget will live in a later spec).

> **Target:** RTF < 1.0 **and** total turnaround < 2.0 s.

### 3.4 Connectivity — No Internet

**What it measures:** whether the solution is truly on-device.

- **Any internet dependency during testing → disqualification.**
- Plain version: *no API calls, no cloud model, nothing leaves the device.* This single rule is what defines Kavi — offline-first is not a nice-to-have, it is the contest.

> **Target:** zero network calls at runtime. All models (ASR, MT, TTS) run locally.

### 3.5 Dataset — Proprietary Benchmark

**What it measures:** final scoring is done against a **hidden, proprietary benchmark dataset** the contest does not publish.

- Plain version: *we never get to see the exact test sentences, so we cannot tune directly to them.*
- Implication: we build general, robust quality and measure ourselves on public proxies (e.g. **VIVOS** for Vietnamese ASR) while tracking BLEU / COMET / MOS / RTF on that proxy so we have a stable signal.

> **Target:** strong, consistent scores on our own proxy; do not overfit to any one dataset.

### 3.6 (judge view) Stability & Operational Performance

Not a published metric, but part of the Technical Excellence score: does the device run the full pipeline reliably, end-to-end, without crashing or drifting? We earn this by a robust, well-tested pipeline.

---

## 4. Definitions & Acronyms (newcomer glossary)

| Term | Plain definition |
| --- | --- |
| **ASR** | Automatic Speech Recognition — turns spoken audio into text. |
| **MT** | Machine Translation — turns text in one language into text in another. |
| **TTS** | Text-to-Speech — turns text into a spoken voice. |
| **Pipeline** | The chain ASR → MT → TTS that produces a translated voice. |
| **BLEU** | Word-overlap score for translation quality (higher = fewer word errors). |
| **COMET** | Neural score for translation *meaning* quality (higher = closer in meaning). |
| **MOS** | Mean Opinion Score — average 1–5 human rating of how natural audio sounds. |
| **Prosody** | Rhythm, stress, and intonation that make speech sound human. |
| **RTF** | Real-Time Factor — processing time ÷ audio length; must be < 1.0. |
| **EOS** | End of Speech — the moment the user stops talking. |
| **SA** | Start of Audio synthesis — the moment the translated voice begins. |
| **Edge AI / on-device** | Models run locally on the device; no cloud. |
| **NPU** | Neural Processing Unit — the Snapdragon (Hexagon) chip that runs models fast and efficiently. |
| **Offline-first** | Designed so it works with no internet at all. |

---

## 5. Target Thresholds (our spec, at a glance)

| Metric | Requirement | Must hit? |
| --- | --- | --- |
| Accuracy (BLEU + COMET) | Maximize | Target |
| Naturalness (MOS) | Maximize | Target |
| Real-Time Factor (RTF) | **< 1.0** | **Hard requirement** |
| Turnaround Latency (EOS→SA) | **< 2.0 s** | **Hard requirement** |
| Connectivity | **No internet at all** | **Hard requirement (else DQ)** |
| Dataset | Hidden proprietary benchmark | Build robust general quality |

---

## 6. Open Questions

- What BLEU / COMET numbers count as "competitive" for VN↔EN? (Decide a baseline from the Opus-MT reference.)
- Do we score per language pair, or report VN↔EN first and add ZH/KO later?
- How do we proxy the MOS panel internally before the contest runs it?
- Where does the 2.0 s turnaround budget split across ASR / MT / TTS? (Needs a performance-budget spec once `src/` exists.)
