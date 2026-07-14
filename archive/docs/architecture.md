# OneVoice AI Challenge — Project Documentation

> **Status:** Pre-Phase 2 (as of May 26, 2026)  
> **Maintainer:** TK  
> **Last updated:** 2026-05-26

---

## Table of Contents

1. [Contest Overview](#1-contest-overview)
2. [Market Research](#2-market-research)
3. [Strategic Positioning](#3-strategic-positioning)
4. [System Architecture](#4-system-architecture)
5. [Component Analysis](#5-component-analysis)
6. [Innovation Anchors](#6-innovation-anchors)
7. [Competitive Landscape](#7-competitive-landscape)
8. [Evaluation & Benchmarking Plan](#8-evaluation--benchmarking-plan)
9. [Timeline & Phase Plan](#9-timeline--phase-plan)
10. [Backlog](#10-backlog)
11. [Open Questions](#11-open-questions)

---

## 1. Contest Overview

### Basic Facts

| Field | Detail |
| --- | --- |
| Name | OneVoice AI Challenge |
| Hosts | Saigon AI Hub (SAIH) × Qualcomm |
| Partners | VNG Group, Vietnam National University HCMC (VNU-HCM) |
| Period | May – November 2026 |
| Finale venue | VNG Campus, Ho Chi Minh City |
| Registration | May 22 – June 22, 2026 |
| Prize pool | $50,000 total |

### Prize Breakdown

| Rank | Prize | Additional |
| --- | --- | --- |
| 1st | $20,000 | Partnership for product development |
| 2nd | $15,000 | Incubation support |
| 3rd | $10,000 | Incubation support |
| Special Innovation Awards | $5,000 total | Breakthrough innovations |

### Judging Criteria

| Dimension | Weight | Description |
| --- | --- | --- |
| Innovation & Novelty | 25% | Originality of approach, supplementary features |
| Technical Excellence | 50% | Accuracy, latency, speed, stability on-device |
| Business Impact & Real-World Potential | 25% | Feasibility, scalability, commercial viability |

### Target Language Pairs

- Vietnamese ↔ English
- Vietnamese ↔ Mandarin Chinese
- Vietnamese ↔ Korean

### Core Requirements

- Fully offline, on-device inference (no cloud dependency)
- Handheld Edge AI device form factor
- Teams may use a self-developed device or a Qualcomm device
- Qualcomm AI Hub compatibility testing explicitly supported
- Specific benchmark values to be published before Phase 3

### Problem Statement (from contest page)

> Only 5% of Vietnamese workers are proficient in English (ManpowerGroup, 2022), lower than many non-English ASEAN countries. 87% of FDI companies require English or foreign language proficiency. In manufacturing, construction, and logistics, communication barriers directly impact productivity, safety, and skills transfer — particularly in environments without stable internet.

---

## 2. Market Research

### 2.1 Novelty Confirmation

Research confirmed the following three-way intersection has **never appeared in any prior contest, product, or published pipeline**:

1. Vietnamese as the **primary** source/target language
2. Full **speech-to-speech** (not speech-to-text) translation pipeline
3. **Qualcomm AI Hub** as co-host / target deployment platform

Each pair of two exists in various forms. All three together: confirmed absent.

Additional gaps confirmed:

- Vietnamese has **never appeared in an IWSLT speech translation track** (the de facto S2ST benchmark)
- VLSP has run Vietnamese ASR, TTS, and text MT as separate tasks but **never as a chained end-to-end S2ST pipeline**
- Qualcomm's Vietnam touchpoint (QVIC) is a startup accelerator, not a speech benchmark

### 2.2 Enterprise Landscape

| Product | Offline Support | Vietnamese | Industrial Focus | Open Stack | Snapdragon-optimized |
| --- | --- | --- | --- | --- | --- |
| Timekettle W4 Pro | Partial (13 pairs) | Online only | No | No | No |
| iFLYTEK Smart Translator 4.0 | Partial | Weak | No | No | No |
| ANFIER W12 | Yes (10 languages) | **No** | No | No | No |
| Pocketalk | Cloud-dependent | Limited | No | No | No |

**Key gap:** No enterprise product is designed for noisy factory environments, targets Vietnamese as a primary language offline, or exposes its model stack.

### 2.3 Open-Source / Hobbyist Landscape

| Project | Pipeline | Vietnamese | TTS | NPU-optimized | Mobile |
| --- | --- | --- | --- | --- | --- |
| RTranslator (niedev) | Whisper + NLLB int8 | Yes (NLLB) | **No** | No | Android |
| HuggingFace speech-to-speech | VAD + Whisper + LLM + MeloTTS | **No** | Yes | No | Desktop |
| arXiv 2507.02530 (Jul 2025) | Whisper + Llama3×2 + MeloTTS | **No** | Yes | No | Server |
| CSUF iOS paper (arXiv 2505.07583) | TinyLlama GGUF + CoreML | VI↔EN text only | No | Apple NE | iOS |

**Closest architectural cousin:** RTranslator — same ASR+MT backbone, but stops before TTS and has no NPU optimization.

**Key published precedent (arXiv 2507.02530):** Confirms Whisper + LLM-corrector + MeloTTS as a viable pattern. Server-grade only, no Vietnamese.

### 2.4 Research Landscape

| Work | Relevance | Gap |
| --- | --- | --- |
| Meta SeamlessM4T v2 / SeamlessStreaming | Gold standard S2ST, ~2s latency, 100 languages incl. Vietnamese | Server-scale, not Snapdragon-deployable |
| IWSLT 2025 simultaneous track (CUNI) | Uses Silero VAD + Whisper-Streaming — exact ASR front-end | English→German only, no industrial context |
| WhisperKitAndroid (Argmax) | Validates Whisper on Snapdragon NPU via AI Hub `.tflite` | Deprecated, ASR only, no translation |
| quic/qidk Whisper demo | Whisper encoder on Snapdragon DSP, quantized a16w8 | ASR only, no translation or TTS |

---

## 3. Strategic Positioning

### 3.1 Device

**Platform:** Snapdragon 8 Gen 2 Android phone, 16 GB RAM (developer's own device)

**Rationale:**

- Confirmed supported by all Qualcomm AI Hub MeloTTS variants (EN, ZH, ES)
- Avoids custom hardware risk (no PCB design, no supply chain)
- Maximizes Business Viability score: deployable to hundreds of millions of existing devices
- Co-host (Qualcomm) has direct institutional interest in Snapdragon validation

### 3.2 Use Case Framing

**"Discussion Companion"** — not a simultaneous interpreter.

Targets non-emergency industrial contexts: safety briefings, skills transfer sessions, training, shift handovers. Sacrifices minimal raw latency in exchange for accuracy. This is the correct tradeoff for the stated problem (factory floor communication, not emergency response).

### 3.3 Core Claim

> **"We are the first team to build a complete, field-tested, Snapdragon-NPU-validated speech-to-speech translation pipeline with Vietnamese as a primary language, using exclusively open models that extend the Qualcomm AI Hub catalog."**

Each word is load-bearing:

- *Complete* — VAD through TTS, no missing stages
- *Field-tested* — benchmarks under industrial noise, not lab conditions
- *Snapdragon-NPU-validated* — profiled through AI Hub Workbench, not just "runs on Android"
- *Vietnamese as primary* — not an afterthought language pack
- *Open models* — reproducible, auditable, no cloud dependency
- *Extends the Hub catalog* — MeloTTS-VI as a genuine contribution, not just consumption

### 3.4 Scoring Strategy

| Criterion | Strategy |
| --- | --- |
| Technical Excellence (50%) | Lead with latency budget, per-stage profiling, WER/BLEU benchmarks framed against IWSLT standards |
| Innovation (25%) | MeloTTS-VI as Hub extension, DeepFilterNet tonal hypothesis, thermal degradation tier |
| Business Viability (25%) | Snapdragon-first, Android-portable second. Existing device = zero hardware cost to deploy |

### 3.5 Key Framing Decisions

- **"Accuracy per watt via intelligent pipeline design"** — not "large models = better accuracy"
- Aggressive upfront denoising (DeepFilterNet ~35ms) enables a smaller fine-tuned Whisper Medium to outperform a thermally-throttled Whisper Large in a live demo
- The IWSLT/VLSP benchmark gap is cited as *proof of novelty*, not just context
- Snapdragon-optimized **leads**; Android-portable follows as business story

---

## 4. System Architecture

### 4.1 Primary Pipeline

```
[Microphone Input]
        │
        ▼
┌─────────────────────┐
│   Silero VAD        │  ~15ms     — Voice activity detection, filters silence
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│   DeepFilterNet     │  ~30–50ms  — Perceptual noise suppression
└─────────────────────┘            — Preserves Vietnamese tonal F0 contour
        │
        ▼
┌─────────────────────┐
│  Whisper Medium     │  ~400–600ms — ASR, fine-tuned on Vietnamese
│  (VI fine-tuned)    │             — Snapdragon 8 Gen 2 NPU via AI Hub
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  Hy-MT1.5-1.8B      │  ~TBD — Neural MT, all 3 pairs in one 440MB model
│  (1.25-bit)         │  — CPU-only (custom STQ kernel)
│                     │  — NLLB-600M used as benchmark reference only
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  MeloTTS-VI         │  ~150–250ms — Fine-tuned VI checkpoint
│  (primary)          │             — Extends Qualcomm AI Hub model family
└─────────────────────┘
        │
        ▼
[Audio Output]
```

**Total nominal latency:** ~800ms – 1.3s

### 4.2 Language Pair Routing

| Source → Target | ASR | MT | TTS |
| --- | --- | --- | --- |
| Source → Target | ASR | MT | TTS |
| --- | --- | --- | --- |
| VI → EN | Whisper Medium VI | **Hy-MT1.5** | MeloTTS-EN (Hub) |
| VI → ZH | Whisper Medium VI | **Hy-MT1.5** | MeloTTS-ZH (Hub) |
| VI → KO | Whisper Medium VI | **Hy-MT1.5** | MeloTTS-KO (self-exported) |
| EN → VI | Whisper Medium EN | **Hy-MT1.5** | MeloTTS-VI (fine-tuned) |
| ZH → VI | Whisper Medium ZH | **Hy-MT1.5** | MeloTTS-VI (fine-tuned) |
| KO → VI | Whisper Medium KO | **Hy-MT1.5** | MeloTTS-VI (fine-tuned) |

### 4.3 Thermal Degradation Tiers

Triggered by device skin temperature thresholds (Snapdragon 8 Gen 2 throttles ~45°C).

| Tier | Condition | TTS Model | Est. Latency | Quality |
| --- | --- | --- | --- | --- |
| 1 — Nominal | < 40°C | MeloTTS-VI | ~200ms | MOS ~4.1 (target) |
| 2 — Warm | 40–45°C | MMS-TTS-vie | ~120ms | MOS ~3.6 (target) |
| 3 — Throttled | > 45°C | espeak-ng | ~15ms | MOS ~2.8 (target) |

> **Note:** MOS values are targets pending empirical measurement. Must be validated on-device before Phase 2 submission.

---

## 5. Component Analysis

### 5.1 Silero VAD

- **Role:** Voice activity detection, silence filtering
- **Latency:** ~15ms
- **Rationale:** Lightweight, widely validated, used in IWSLT 2025 CUNI submission with identical parameters (min chunk 0.04s, min non-voice 500ms, 100ms padding)
- **Hub status:** Not on Hub; runs on CPU, negligible cost

### 5.2 DeepFilterNet

- **Role:** Perceptual noise suppression pre-ASR
- **Latency:** ~30–50ms
- **Key hypothesis:** Vietnamese has 6 tones distinguished by F0 contour and phonation type. Standard noise suppressors (RNNoise, WebRTC NS) tuned for European speech may corrupt tonal features. DeepFilterNet's perceptual loss design is more conservative about harmonic preservation.
- **Validation needed:** WER comparison on Vietnamese speech under industrial noise (65dB) with RNNoise vs DeepFilterNet vs no denoising. **This is the fastest experiment to run.**
- **Prior art:** MeloTTS.cpp (Intel OpenVINO) includes DeepFilterNet in its C++ pipeline as a post-processing denoiser for int8 quantization artifacts — confirms pipeline compatibility

### 5.3 Whisper Medium (Vietnamese fine-tune)

- **Role:** ASR
- **Latency:** ~400–600ms (target, NPU-accelerated)
- **Hub status:** Whisper-Small is on the Hub. Medium is larger — export via Workbench required.
- **Fine-tuning data:** VIVOS (~15h, single speaker), CommonVoice-VI, VLSP ASR data
- **Rationale over Whisper Large:** Thermal throttling on sustained load makes Large unreliable in a live demo. Fine-tuned Medium outperforms throttled Large — this is the "accuracy per watt" claim.
- **Known issue:** Whisper trained primarily on clean speech; industrial noise degrades VI performance significantly without DeepFilterNet preprocessing

### 5.4 Machine Translation — Hy-MT1.5 (primary)

> **Decision:** Hy-MT1.5 is the sole production MT model. NLLB-600M excluded from production — benchmark reference only. See [ADR-001](../adr/001-prioritize-hy-mt-over-nllb.md).

- **Primary model:** Hy-MT1.5-1.8B-1.25bit (Tencent, April 2026)
- **Size:** 440MB — single model covering all 33 languages and all contest pairs
- **Quality:** Surpasses Tower-Plus-72B and Qwen3-32B on Flores-200 benchmarks
- **On-device precedent:** Tested on Snapdragon 888, 8x speedup over FP16, real Android APK exists
- **Execution:** CPU-only (custom STQ quantization kernel). NPU acceleration path not yet demonstrated.
- **License:** Tencent HY Community License (commercial use permitted)
- **Latency:** ~TBD on SD8G2 — deferred to Phase 2 profiling

#### Fallback: NLLB-600M int8

- **Role:** NPU-accelerated alternative if Hy-MT breaks latency budget
- **Latency:** ~200–350ms via ONNX + QNN
- **Precedent:** RTranslator uses NLLB-Distilled-600M with KV cache on Android
- **License:** CC-BY-NC-4.0 (non-commercial). Flagged as unresolved — only viable if commercial terms are not triggered by contest participation.
- **Decision gate:** Phase 2 latency profiling will determine whether NPU acceleration from NLLB is necessary to meet the 2s budget.

### 5.5 MeloTTS-VI (fine-tuned)

- **Role:** Vietnamese TTS output
- **Latency:** ~150–250ms (target)
- **Hub status:** MeloTTS-EN, ZH, ES are live on Hub (Snapdragon 8 Gen 2 supported, MIT). **Vietnamese is absent** — confirmed gap.
- **Architecture:** VITS-based, BERT-conditioned, non-autoregressive. MIT license.
- **Fine-tuning precedent:** MeloTTS-MS (Malay, by mesolitica) proves the community fork pattern. MeloTTS.cpp (Intel) adds Japanese branch.
- **Training data candidates:** VIVOS (15h, single speaker), CommonVoice-VI, VLSP TTS data
- **Known Hub issue:** MeloTTS HTP summation bug fixed — pre-generated assets may be stale, use export script path. This is the same workflow required for a custom checkpoint, so no extra overhead.
- **Contest framing:** "We extended the Qualcomm AI Hub MeloTTS family to Vietnamese" — directly aligned with co-host's institutional interest.

### 5.6 MeloTTS-KO

- **Role:** Korean TTS output
- **Hub status:** Not present. MeloTTS upstream supports Korean. Self-export via Workbench required.
- **Training data:** KSS dataset, NIKL corpus (well-resourced language)
- **Fallback:** MMS-TTS-kor (Meta)
- **Priority:** Lower than MeloTTS-VI but required for full contest coverage

### 5.7 MMS-TTS-vie (Meta)

- **Role:** Thermal Tier 2 TTS fallback for Vietnamese
- **Hub status:** Not on Hub. ONNX export via Workbench required.
- **Quality:** Lower than MeloTTS-VI; sufficient for degraded-mode intelligibility
- **License:** CC-BY-NC-4.0

---

## 6. Innovation Anchors

Ranked by strength and evidence status:

### Anchor 1: MeloTTS-VI as Qualcomm AI Hub Extension ⭐ Primary

**Claim:** First Vietnamese TTS model in the MeloTTS family, exported through Qualcomm AI Hub Workbench, extending the Hub's official model catalog.

**Strength:** Strategic + institutional. Qualcomm co-hosts the contest and has direct interest in Hub catalog growth. No prior Vietnamese entry exists.

**Evidence needed:** Working checkpoint with MOS score, successful Workbench export, latency profile on SD8G2.

**Type:** Strategic differentiator (not novel research, but novel *context and execution*)

---

### Anchor 2: DeepFilterNet for Vietnamese Tonal Preservation ⭐ Most Technically Arguable

**Claim:** Standard noise suppression corrupts Vietnamese F0 tonal contours that Whisper relies on for disambiguation. DeepFilterNet's perceptual loss design is measurably more conservative, yielding lower WER on Vietnamese under industrial noise.

**Strength:** Genuine technical hypothesis with no prior published evidence. Ownable if validated.

**Evidence needed:** WER table — Vietnamese speech + 65dB industrial noise, comparing: (a) no denoising, (b) RNNoise/WebRTC NS, (c) DeepFilterNet.

**Type:** Technical contribution (hypothesis → finding if experiment confirms it)

**Priority:** Run this experiment first. Highest evidence-to-effort ratio.

---

### Anchor 3: Thermal Graceful Degradation ⭐ Demo-Safety + Business Viability

**Claim:** Production-grade pipeline includes three named fallback tiers triggered by device temperature, with measured latency and quality at each level.

**Strength:** Weak on paper, strong in live demo. A staged throttle scenario at Phase 5 is memorable and directly signals production-readiness.

**Evidence needed:** Real MOS/latency table per tier, measured on SD8G2. Thermal threshold calibration (at what skin temperature does SD8G2 throttle?).

**Type:** Engineering depth signal

---

### Anchor 4: Gemma 4 E2B Domain Correction Layer (Backlog) ⭐ Architectural Novelty

**Claim:** Lightweight LLM used not as translator but as domain-aware pre-processor — corrects ASR errors and injects industrial glossary context before NLLB translation.

**Framing:** "We use a lightweight LLM not as a translator but as an intelligent pre-processor — injecting domain context and correcting ASR noise before a specialized MT model handles cross-lingual transfer."

**Evidence needed:** Side-by-side example: ASR output with industrial error → E2B correction → NLLB translation (correct) vs no correction → NLLB translation (incorrect).

**Concerns:** E2B multilingual ceiling — community reports suggest E2B is "mostly English-capable" for multilingual tasks. E4B is significantly better for VI/ZH/KO. May be viable for VI↔EN only. Latency at 60+ tok/s may push total pipeline to 1.5–1.8s.

**Status:** First-seat backlog priority. Do not include in Phase 2 spec without preliminary results.

---

## 7. Competitive Landscape

### 7.1 Convergence Risk

The pipeline premise is **not unique**. Silero VAD + Whisper + NLLB/Hy-MT + MeloTTS is the natural assembly of well-known components. Multiple teams will converge on similar architectures. The RTranslator project (Android, open-source) already implements Whisper + NLLB int8 without TTS. Our choice of Hy-MT1.5 (CPU-only, no NPU fallback) over NLLB diverges from the most common pattern (see [ADR-001](../adr/001-prioritize-hy-mt-over-nllb.md)), but the structural similarity remains.

### 7.2 Differentiation Matrix

| Capability | Generic competitor | This proposal |
| --- | --- | --- |
| Full S2S pipeline (VAD→TTS) | Unlikely | ✓ |
| Vietnamese primary language | Possibly | ✓ |
| Snapdragon NPU profiled | Unlikely | ✓ |
| AI Hub model used | Possibly | ✓ (MeloTTS-EN/ZH/ES) |
| AI Hub model *contributed* | No | ✓ (MeloTTS-VI target) |
| Industrial noise benchmarks | Unlikely | ✓ (target) |
| Thermal degradation tiers | No | ✓ |
| Preliminary results in Phase 2 | Unlikely | ✓ (target) |

### 7.3 Phase 2 Filtering Strategy

Technical verbosity alone does not win. **Specificity that can only come from having touched the problem** does. The goal is not more words — it is fewer words that a team still on paper cannot write.

Examples of phase-2-winning specificity:

- "Baseline Whisper Medium achieves X% WER on VIVOS. With DeepFilterNet preprocessing, WER drops to Y% under 65dB noise."
- "MeloTTS HTP summation bug in pre-generated assets required export script path — we validated this on SD8G2 with QNN runtime v2.X."
- "Thermal throttle begins at 44°C skin temperature on our test device. Tier 2 fallback adds <5ms switching overhead."

---

## 8. Evaluation & Benchmarking Plan

### 8.1 ASR Benchmark

| Metric | Tool | Dataset | Condition |
| --- | --- | --- | --- |
| WER (Vietnamese) | faster-whisper eval | VIVOS test set | Clean |
| WER (Vietnamese) | faster-whisper eval | VIVOS + synthetic noise | 65dB industrial noise |
| WER delta (DeepFilterNet) | Δ WER above | Above | Above |

### 8.2 Translation Benchmark

| Metric | Tool | Dataset | Language pair |
| --- | --- | --- | --- |
| BLEU | sacrebleu | FLORES-200 | VI↔EN, VI↔ZH, VI↔KO |
| chrF | sacrebleu | FLORES-200 | All pairs |

Reference framing: IWSLT simultaneous track standard (≤2s Average Lagging for "real-time"). Vietnamese has never appeared in IWSLT speech track — cite this gap explicitly in Phase 2.

### 8.3 TTS Benchmark

| Metric | Method | Target |
| --- | --- | --- |
| MOS (naturalness) | Human evaluation (5-point scale) | ≥ 3.8 for MeloTTS-VI |
| Intelligibility | WER on TTS output via ASR | < 10% |
| Latency | On-device profiling via AI Hub Workbench | < 250ms |

### 8.4 End-to-End Benchmark

| Metric | Definition | Target |
| --- | --- | --- |
| Total pipeline latency | VAD trigger → audio output start | < 2000ms (IWSLT ceiling) |
| Thermal stability | Latency variance over 30min sustained use | < 20% degradation |
| Noise robustness | End-to-end BLEU at 65dB SNR vs clean | < 15% BLEU drop |

---

## 9. Timeline & Phase Plan

### Contest Phases

| Phase | Period | Deliverable |
| --- | --- | --- |
| Phase 1 — Registration | May–June 2026 | Team registration by June 22 |
| Phase 2 — Technical Spec | July 2026 | System architecture + design doc |
| Phase 3 — Prototype | Aug–Sep 2026 | Functional device prototype |
| Phase 4 — Field Testing | October 2026 | Real-world evaluation |
| Phase 5 — Finale | November 2026 | Live demo at VNG Campus, HCMC |

### Pre-Phase 2 Experiment Priority

Ordered by evidence-to-effort ratio:

1. **DeepFilterNet WER experiment** — runnable on CPU in a weekend. Vietnamese VIVOS + synthetic noise, WER comparison table. Highest priority.
2. **MeloTTS-VI prototype checkpoint** — VIVOS fine-tune. Even a rough voice by Phase 2 changes proposal quality dramatically.
3. **Thermal tier latency table** — needs SD8G2 device (available). Measure Tier 1/2/3 latency and trigger temperature.
4. **Whisper Medium export via AI Hub Workbench** — validate NPU profiling, confirm SD8G2 latency numbers.

---

## 10. Backlog

### First-Seat Priority

**Gemma 4 E2B Domain Correction Layer**

- Replace or augment NLLB with Gemma 4 E2B as a domain-aware pre-processor
- System prompt injection with industrial glossary (e.g. "dừng khẩn cấp" → "emergency stop")
- Architecture: ASR → E2B correction → NLLB MT → TTS
- For VI↔EN: explore E2B as full translator (strongest multilingual performance at E2B tier)
- For VI↔ZH, VI↔KO: E2B correction only, NLLB handles translation
- **Concern:** E2B multilingual ceiling; community reports suggest mostly English-capable. E4B better for non-English tasks but higher latency/RAM.
- **Latency impact:** E2B at 60+ tok/s → ~500ms for 30-token output. Total pipeline 1.5–1.8s — within 2s ceiling but tight.
- **Blocker:** Do not include in Phase 2 spec without at least one demonstrated example.

### Second-Seat Priority

- MeloTTS-KO self-export via Workbench
- NLLB license review (CC-BY-NC-4.0 vs contest commercial terms)
- Industrial domain glossary construction (VI/EN/ZH/KO manufacturing terminology)

---

## 11. Open Questions

| Question | Priority | Notes |
| --- | --- | --- |
| NLLB-600M license (CC-BY-NC-4.0) compatible with contest IP terms? | High | Contest rules state "original development for competition" — check if NC restriction conflicts |
| MeloTTS-KO training data availability? | Medium | KSS + NIKL should suffice; confirm licensing |
| VIVOS sufficient for MeloTTS-VI naturalness? | High | ~15h single speaker may be insufficient; investigate VLSP TTS corpus access |
| Whisper Medium latency on SD8G2 NPU via Workbench? | High | Must measure before Phase 2 numbers are committed |
| Thermal throttle temperature calibration on test device? | Medium | Required for Tier 2/3 trigger thresholds |
| Benchmark values from contest organizers (Phase 3 pre-release)? | Low now, High later | Organizers will publish before Phase 3; frame Phase 2 spec around IWSLT standards as proxy |
| E2B Vietnamese correction quality? | Low (backlog) | Evaluate only after core pipeline is stable |

---

## References

### Contest

- Contest page: <https://saigonaihub.com/OneVoiceAIChallenge>
- Vietnamese press coverage: <https://doanhnghiepvn.vn/tin-tuc/giao-duc/tim-kiem-giai-phap-ai-dich-song-ngu-thoi-gian-thuc-khong-can-internet/20260525102944273>

### Qualcomm AI Hub Models

- MeloTTS-EN: <https://aihub.qualcomm.com/models/melotts_en>
- MeloTTS-ZH: <https://aihub.qualcomm.com/models/melotts_zh>
- MeloTTS-ES: <https://aihub.qualcomm.com/models/melotts_es>
- Hub releases (MeloTTS HTP bug fix): <https://github.com/qualcomm/ai-hub-models/releases>
- Whisper on Snapdragon DSP: <https://github.com/quic/qidk/blob/master/Solutions/NLPSolution3-AutomaticSpeechRecognition-Whisper/README.md>
- WhisperKitAndroid (Argmax): <https://github.com/argmaxinc/WhisperKitAndroid>

### Open-Source Comparable Projects

- RTranslator (Whisper + NLLB Android): <https://github.com/niedev/RTranslator>
- HuggingFace speech-to-speech: <https://github.com/huggingface/speech-to-speech>
- MeloTTS (upstream): <https://github.com/myshell-ai/MeloTTS>
- MeloTTS-MS (Malay fork): <https://github.com/mesolitica/MeloTTS-MS>
- MeloTTS.cpp (OpenVINO C++): <https://github.com/apinge/MeloTTS.cpp>

### Research

- SeamlessM4T / SeamlessStreaming: <https://ai.meta.com/research/seamless-communication/>
- Seamless paper: <https://arxiv.org/pdf/2312.05187>
- IWSLT 2025 CUNI submission (Silero VAD + Whisper-Streaming): <https://arxiv.org/pdf/2506.17077>
- KIT IWSLT 2025 offline ST: <https://arxiv.org/pdf/2505.13036>
- Whisper + Llama3 + MeloTTS pipeline (Jul 2025): <https://arxiv.org/html/2507.02530v1>
- Vietnamese-English Edge AI on iOS (May 2025): <https://arxiv.org/pdf/2505.07583>

### Gemma 4 E2B

- Google announcement: <https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/>
- Google developer docs: <https://ai.google.dev/gemma/docs/core>
- E2B vs E4B comparison: <https://gemma4-ai.com/blog/gemma4-e2b-vs-e4b>
- Community 24h findings: <https://dev.to/dentity007/-gemma-4-after-24-hours-what-the-community-found-vs-what-google-promised-3a2f>

---

## 2026.06.13 Update

New benchmark and timeline details surfaced from re-visiting the Luma registration page (June 12–13, 2026), which contains more authoritative information than the earlier contest page scrape.

### Date Corrections

| Field | Previously | Corrected |
| --- | --- | --- |
| Registration period | May 22 – June 22, 2026 | **May 24 – June 24, 2026** |
| Phase 2 — Technical Spec | July 2026 | **June – July 2026** (opens earlier) |
| Phase 3 — Prototype | Aug – Sep 2026 | **September 2026** (single month) |

### New Contest Requirements (from Luma scoring criteria)

| Rule | Impact |
| ------ | -------- |
| **RTF < 1.0** explicitly required | Our pipeline budget (800ms–1.3s) is tight; the RTF constraint adds a processing-throughput dimension our current plan doesn't explicitly track |
| **>2.0s latency → significant point deductions** (our doc already targets < 2000ms but framed it as IWSLT reference — contest rule is stronger) | This confirms our target is correct but the penalty framing matters for judging narrative |
| **Internet dependency during testing = disqualification** | Our doc already states "no cloud dependency" — reinforce this in testing methodology |

### Metrics We Were Missing

| Metric | Where to add |
| -------- | ------------- |
| **COMET** alongside BLEU for translation accuracy | Section 8.2 — Translation Benchmark currently only lists BLEU + chrF |
| **MOS by native speaker panel** (not just generic human eval) | Section 8.3 — TTS Benchmark |
| Judges use a **proprietary benchmark dataset** (not just FLORES-200) | Section 8 — adds uncertainty; FLORES-200 is our proxy, not the actual eval set |

### Registration Info

Registration is **two-step**: Luma RSVP with wallet token verification + Google Sheets template:
<https://docs.google.com/spreadsheets/d/1L4lc7vOiovBdRgDQ3Xmw3hADomxThHa1zE_Lfi8TlvQ>

Fields: Applicant Type (Individual/Team), Full Name, Email, Phone, Location, Organization, Role, Expertise, Experience, Portfolio. Teams also provide Team Name, member count, and per-member rows.

### Phase 2 Implications

1. **Benchmark sections 8.1–8.4** should add COMET alongside BLEU, and note the proprietary dataset uncertainty
2. **Latency constraint** (2s ceiling with deductions) strengthens our architecture doc's existing framing — cite the contest rule directly, not IWSLT convention
3. **Internet dependency → disqualification** — no change needed, our doc already states this
4. **Registration window closes June 24** — 11 days from this writing
5. **Registration window closes June 24** — 11 days from this writing
6. **Phase 2 may start June, not July** — pre-Phase-2 experiment window is shorter than assumed
