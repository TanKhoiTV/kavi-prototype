# Benchmarking & Test-Suite Plan

> **Status:** Draft (planning). This document captures *what we will measure and on
> what data* — it deliberately does **not** pick the ASR / MT / TTS tech stack.
> Those choices are deferred to **ADR-004 (architecture)**, which this plan gates.
>
> **Sources:** synthesized from an external analysis pass (Claude) on datasets,
> the RTranslator baseline, and harness design, cross-checked with Context7 for the
> `datasets` / `torchaudio` / `evaluate` library APIs. Corrections to earlier
> assumptions are flagged inline.

---

## 1. Purpose & scope

We run experiments **before** settling the tech stack (per the agreed sequencing).
This plan is the first deliverable: a **model-agnostic testing & benchmarking
suite** plus a **dataset decision**. The numbers it produces are what ADR-004 will
record as the architecture choice.

The suite must be **pluggable**: we swap ASR / MT / TTS candidates in and out and
score them against identical data and the contest metrics. No candidate is wired
into harness code.

### Relationship to existing decisions

| Doc | What it locks | What this plan adds |
| --- | --- | --- |
| **ADR-001** Offline-first, on-device | Zero cloud dependency | No-internet DQ is a scored gate in §7 |
| **ADR-002** Target platform | Snapdragon 8 Gen 2 / Android 16, Hexagon HTP v73, GPU→CPU fallback | Datasets + noise must reflect the *noisy* deployment, not clean-room only |
| **ADR-003** Hexagon runtime (Proposed) | QAIRT/QNN primary, ORT-XNNPACK CPU fallback, w8a16, fixed shapes | Determination method = **CPU baseline first, then on-device benchmark** (§6, §8) |
| `docs/specifications.md` | The six objective metrics + hard thresholds | §7 restates them as harness outputs |

> **Out of scope here:** which models/frameworks we ship. That is ADR-004, fed by
> the v0 results in §8.

---

## 2. Evaluation axes

The pipeline is **ASR → MT → TTS** (VI↔EN). We need data + a noise bank covering
four axes:

1. **VI ASR** — Vietnamese speech recognition.
2. **EN ASR** — English speech recognition (for the EN→VI direction).
3. **VI↔EN speech translation** — the real end-to-end test.
4. **TTS reference audio** — targets / MOS references.

Plus a **noise bank** for the contest's factory / construction / logistics settings.

---

## 3. Datasets (shortlist)

### 3.1 Vietnamese ASR

| Dataset | Size | Style | Transcripts | License | Obtain |
| --- | --- | --- | --- | --- | --- |
| **VIVOS** | 15 h, 11,660 train / 760 test | Read speech, 65 speakers, quiet studio | Human-annotated (gold) | **CC BY-NC-SA 4.0** ("academic purposes only") | `AILAB-VNUHCM/vivos` |
| **VietSuperSpeech (VSS)** | 267.4 h, 52,023 utterances (240.7 h train / 26.7 h dev-test) | Casual conversational — YouTube vlogs, informal, diaspora dialogue | **Pseudo-labeled** via Zipformer-30M-RNNT (not human-verified) | Not clearly stated — **verify HF page before relying** | `thanhnew2001/VietSuperSpeech` |
| **FOSD / FPTVIET** | clean studio | clean anchor | — | verify | — |

**Use them as complements, not substitutes:**

- **VIVOS** = clean-room, gold-labeled read speech → a controlled WER baseline, but
  near-zero acoustic/register match to a noisy factory floor.
- **VietSuperSpeech** = far closer to deployment register (spontaneous, informal)
  and gives real acoustic diversity, but its labels are **model-generated** — use it
  for robustness/stress testing, and hand-verify a small subset (50–100 utts) if you
  want a trustworthy WER figure from it. Do **not** treat its labels as ground truth
  for a final WER number.

### 3.2 English ASR / TTS reference

- **Common Voice (Mozilla)** — **CC0** (safest license in this list). EN + VI splits
  from the same crowdsourced pipeline; accent-diverse. Good for EN ASR eval and as a
  second VI source beyond VIVOS's 65 speakers.
- **LibriSpeech** — CC BY 4.0, the standard EN ASR benchmark (clean/other splits give
  a free "quiet room" vs "harder acoustic" split).
- **LibriTTS** — CC BY 4.0, 585 h, 2,456 speakers, 24 kHz — best bet for **EN TTS
  reference audio** (multi-speaker, studio, designed for TTS).
- **InfoRe** (VI TTS ref) — single female speaker, ~14,935 clips, reused in open VI
  TTS projects (e.g. `vietTTS`); closest VI analog to LJSpeech. **Verify donation
  terms** before bundling raw clips in a public repo.
- **viVoice** (VI TTS ref) — 1,017 h, multi-speaker, YouTube-sourced; **CC BY-NC-SA
  4.0, research-only, institutional-email gate** → internal-eval-only, do not
  redistribute.

### 3.3 VI↔EN speech translation — correction

> **Correction (important):** earlier we assumed **CoVoST-2** / **MuST-C** covered
> Vietnamese. They do **not**:
>
> - **CoVoST-2** translates 21 langs → EN and EN → 15 of those. **Vietnamese is in
>   neither list.**
> - **MuST-C** is EN-source only → 8 European langs. No Vietnamese, no non-EN audio
>   input either way.
>
> Do **not** build around them for VI.

What actually exists / is usable:

- **PhoST** (VinAI, Interspeech 2022) — 508 audio h, 331K triplets of (EN audio, EN
  transcript, VI subtitle text). `github.com/VinAIResearch/PhoST`. A real,
  purpose-built **EN audio → VI text** corpus → tests the **EN→VI** direction.
  **Verify license on the repo directly** (not confirmed here).
- **VI→EN direction has no equivalent large purpose-built corpus.** Two workarounds:
  1. **FLEURS-vi** is built from FLoRes-101, so each VI recording's transcript is a
     translation of the *same underlying sentence* that exists in **FLEURS-en** (and
     100+ langs). That gives a legitimate, if indirect, **VI-audio → EN-text** pairing
     by matching sentence IDs across the two language splits — **CC BY 4.0**, directly
     downloadable (`google/fleurs`). Validate the exact ID-alignment mechanics before
     leaning on it heavily.
  2. **Bespoke gold set** — take 150–300 sentences from a verified VI subset
     (VIVOS / Common Voice-vi / VSS), get careful human translations into EN. For a
     *lean* eval set this is a half-day task; write factory/logistics-flavored
     sentences (equipment names, safety instructions, numbers, short imperatives) to
     match the contest domain.

### 3.4 Noise bank

| Corpus | Content | License | Fit |
| --- | --- | --- | --- |
| **MUSAN** | ~109 h music/speech/technical & non-technical noise | CC / US public domain, built legally clean | General additive noise + babble (speech subset) |
| **DEMAND** | 18 multichannel real-world recordings, 6 env categories | CC BY-SA 3.0 | Reverberant real-room character; noisier cats = logistics proxy |
| **NOISEX-92** | factory1/factory2, babble, machine-gun, military | Murky redistribution terms | **Internal eval only** — closest to literal "factory floor" |
| **OpenSLR RIRS_NOISES** | Simulated + real room impulse responses | CC BY 4.0 | Convolutional reverb (warehouse/factory-scale rooms) |
| **Freesound** (curated industrial/machinery/forklift packs) | Real recordings, per-clip licensing | Per-clip CC — check each | Best for construction/logistics sounds not elsewhere represented |

### 3.5 Noise-mixing recipe (eval time, not baked in)

Applied at **eval time** so every candidate is scored on **byte-identical inputs**:

1. **Reverb** — convolve clean utterance with a large/medium-room RIR from
   RIRS_NOISES (warehouse/factory reflections).
2. **Additive noise** — select a noise clip (rotate: mechanical/steady vs
   babble/impulsive), trim/loop to utterance length, scale to target SNR via
   RMS-based scaling, mix, peak-normalize. (`torchaudio.functional.add_noise` +
   `fftconvolve` + `resample` cover this directly.)
3. **SNR sweep** — five conditions is enough for a real curve:

| Condition | SNR | Purpose |
| --- | --- | --- |
| Clean | ∞ | Reference / ceiling |
| Mild | +15 dB | Light background |
| Moderate | +10 dB | Noisy but workable |
| Hard | +5 dB | Loud warehouse / near-forklift |
| Severe | 0 dB | Stress test, near WER breakdown |
| (Stretch) Worst-case | −5 dB | Stability check only, not a pass/fail bar |

Run each SNR against **≥2 noise types** (steady vs impulsive) — ASR degrades very
differently under the two, and a single averaged "noisy" number hides which failure
mode you have.

### 3.6 License watch-outs (for a possibly-public contest repo)

- **Safe to bundle/reference publicly:** Common Voice (CC0), LibriSpeech / FLEURS /
  LibriTTS (CC BY 4.0, credit), MUSAN (public domain), RIRS_NOISES (CC BY 4.0).
- **Attribution + share-alike:** DEMAND (CC BY-SA 3.0).
- **Research/eval-only, don't ship:** VIVOS (CC BY-NC-SA), viVoice (CC BY-NC-SA),
  NOISEx-92 (ambiguous redistribution).
- **Verify before relying on:** VietSuperSpeech license, PhoST license, InfoRe
  donation terms — none pinned down precisely here.
- **NLLB** (RTranslator ships it; we already avoid it): CC BY-NC 4.0 — confirmed
  non-commercial. Do not let RTranslator's NLLB weights leak into anything we
  distribute, even for comparison.

---

## 4. Model candidate landscape (ASR, MT, TTS)

> **Input to ADR-004, not a decision here.** Candidate-model comparisons for the ASR,
> MT, and TTS stages. ASR (§4.1–4.3) is sourced from an external analysis pass; MT and
> TTS (§4.4–4.5) are synthesized from the repo's archived docs (architecture.md,
> ADR-001) plus Context7 library docs (CTranslate2, Piper, Transformers). It refines
> the v0 candidate set (§8) and the per-stage list (§9); the final picks stay with
> ADR-004.

Four VI/EN ASR candidates were compared on accuracy, latency (Snapdragon 8 Gen 2
estimates), memory, licensing, and Qualcomm AI Hub availability.

### 4.1 Accuracy — Vietnamese WER (lower is better)

| Model | CMV-Vi | VIVOS | VLSP T2 | EN support | License | AI Hub (SD8G2) |
| --- | --- | --- | --- | --- | --- | --- |
| **Whisper Small** (244M) | ~26–30% | ~20–25% | ~55–65% | Full multilingual | Apache-2.0 | Yes (w8a16) |
| **PhoWhisper Small** (244M) | **11.08** | **6.33** | **32.96** | Inherited (unbench) | BSD-3 | No (DIY export) |
| **Zipformer 30M VI** (~30M) | no public # | — | — | **None — VI only** | Apache-2.0 | No (untested) |
| **Moonshine Tiny VI** (27M) | 18.8 (CV17) | — | — | **None — VI only** | Apache-2.0 | No (DIY) |

- **PhoWhisper Small** is the VI-accuracy winner (~2.4× better than Whisper Small on
  CMV-Vi) and is the same architecture as Whisper Small, so the AI Hub `SHA+conv` →
  w8a16 trick applies — a QNN/HTP path is feasible, just not prebuilt.
- **Whisper Small** is the only candidate with **confirmed EN + VI** support and the
  only one with **published SD8G2 latency** (via Qualcomm AI Hub).
- **Zipformer / Moonshine are VI-only** — they cannot serve the EN→VI direction's ASR
  leg and can only compete for the VI→EN direction.

### 4.2 Latency & memory (SD8G2 estimates)

| Model | Encoder TTFT | Decoder/token | Params | INT8 size | Window |
| --- | --- | --- | --- | --- | --- |
| Whisper Small | ~400–800 ms | ~15–30 ms | 244M | ~244 MB | **30 s fixed** (overhead on short utts) |
| PhoWhisper Small | ~400–800 ms | ~15–30 ms | 244M | ~244 MB | 30 s fixed |
| Zipformer 30M VI | ~50–150 ms | ~5–15 ms | ~30M | ~32 MB | scales w/ duration (streaming) |
| Moonshine Tiny VI | ~50 ms | ~10–20 ms | 27M | ~27–34 MB | scales w/ duration (streaming) |

- Whisper/PhoWhisper's **fixed 30 s window** is pure overhead on short utterances and
  directly pressures the **2.0 s turnaround budget** (§7).
- Zipformer/Moonshine **stream and scale with actual duration** (~50 ms TTFT) — a
  better structural fit for that budget, *if* we accept VI-only + a CPU/DIY-NPU path.

### 4.3 Implications for the candidate matrix

- **Kavi is bidirectional VI↔EN**, so the ASR candidate set is constrained *per
  direction*: EN→VI needs an EN-capable ASR (Whisper Small, or PhoWhisper by
  inheritance), while VI→EN may also evaluate PhoWhisper / Zipformer / Moonshine.
- **Licensing is clean** across all four (Apache-2.0 / BSD-3, commercial OK) — no
  NLLB-style blocker on the ASR side.
- Only Whisper Small has published on-device numbers; the rest need the manual
  profiling our v0 harness exists to produce — so this comparison *broadens* the
  candidate set without answering the on-device question.

> **Caveats:** FLEURS is read/quiet speech; real-world VI WER is 2–5× higher.
> PhoWhisper/Zipformer numbers are on more conversational data (VLSP, VIVOS) and are
> more representative. No public head-to-head of Moonshine Tiny VI vs PhoWhisper Small
> exists (different evaluation sets). Latencies are paper/architecture estimates, not
> measured on our unit.

### 4.4 MT candidate landscape (VI↔EN)

> Sources: archived `architecture.md` + `docs/adr/001-prioritize-hy-mt-over-nllb.md`
> (ADR-001, accepted 2026-06-14) + Context7 (CTranslate2, Transformers). The prototype
> (`archive/pipeline.py`, `models/opus-mt-vi-en-ct2`) actually runs **Opus-MT vi-en via
> CTranslate2 int8**; the archived ADR-001 instead selected **Hy-MT1.5** (NLLB only as
> benchmark reference). MT is **bidirectional** — VI→EN and EN→VI.

| Model | VI↔EN quality | Latency (SD8G2 est) | Size | License (commercial?) | AI Hub / SD8G2 | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| **Opus-MT** (Helsinki-NLP/opus-mt-vi-en) | Moderate (small MarianMT, ~60M params) | Low (CPU int8, fast) | int8 CT2 ~70 MB (verify) | Apache-2.0 (OK) | No (DIY ONNX→QAIRT) | **Current prototype.** VN→EN only; EN→VN needs a separate opus-mt-en-vi. CTranslate2 is NOT QNN-convertible — NPU needs PyTorch→ONNX→QAIRT re-source (Transformers export confirmed). |
| **NLLB-600M-Distilled** (Meta) | High | ~2 s / 75 tok (RTranslator optimized, CPU) | ~600 MB int8 | CC-BY-NC-4.0 (avoid) | No (DIY ONNX→QNN) | **Avoid for production** (non-commercial). NPU-acceleratable; benchmark reference only. Needs `forced_bos_token_id` per lang. |
| **Hy-MT1.5-1.8B** (Tencent) | High (surpasses 72B-class on FLORES-200, per ADR-001) | ~400–800 ms CPU (SD888 tested; SD8G2 faster est.) | 440 MB (1.25-bit STQ) | HY Community — commercial OK *per ADR-001*, but regional carve-out flagged by current stance → avoid/verify | No (CPU-only STQ kernel, no NPU path) | Old ADR-001 sole pick; covers all pairs in one model. CPU-only, no NPU acceleration. |
| **MADLAD-400** (Google) | Moderate–high | High (3B/7B, CPU-heavy) | 3B / 7B | Apache-2.0 (OK) | No | 450+ langs incl VI/EN; too large for 8G2 latency budget. |
| **M2M-100** (Meta) | Moderate | Moderate (418M) | 418M–1.2B | MIT (OK) | No | 100 langs; 418M edge-plausible; older. |
| **SeamlessM4T v2** (Meta) | High (unified S2ST) | Too slow (2.3B) | 2.3B | Custom (verify; likely research-only) | No | Unified speech-to-speech (bypasses ASR/MT/TTS split); server-scale, not 8G2-deployable. |

- **Bidirectional coverage:** Opus-MT needs two models (vi-en + en-vi). NLLB / Hy-MT /
  MADLAD / M2M / Seamless are multilingual (both directions in one).
- **NPU path (ADR-003):** CTranslate2 (our current MT runtime) is **not** QNN-convertible.
  Opus-MT and NLLB are standard PyTorch Seq2Seq → exportable to ONNX → QAIRT via
  Transformers/optimum (confirmed by Context7). Hy-MT's STQ kernel is CPU-only with no
  NPU path.
- **Licensing gate:** commercial-clean = Opus-MT, MADLAD-400, M2M-100. **Avoid** =
  NLLB (NC), and **Hy-MT** pending regional-carve-out verification. SeamlessM4T license
  verify.

### 4.5 TTS candidate landscape (VI + EN voices)

> Sources: archived `architecture.md` (MeloTTS-VI primary, MMS-TTS-vie fallback) +
> Context7 (Piper). The prototype (`archive/pipeline.py`, `voices/`) uses **Piper**
> (`en_US-lessac-medium`). TTS must supply **both** a Vietnamese voice (EN→VI output)
> and an English voice (VI→EN output).

| Model | VI + EN voices | Quality (MOS) | Latency (SD8G2 est) | Size | License | AI Hub / SD8G2 | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Piper** (rhasspy) | EN yes (official); VI community voice (verify) | Good (non-AR VITS-like) | Very fast (< RTF 1, real-time+) | ~tens MB/voice | MIT (OK) | No (ONNX→QAIRT feasible; Piper is already ONNX) | **Current prototype.** Offline, CPU via onnxruntime. Phonemization needs espeak-ng. |
| **MeloTTS** (myshell-ai) | EN/ZH/ES on AI Hub yes; VI absent (needs fine-tune from VIVOS/CommonVoice-VI) | Good (VITS, BERT-conditioned) | ~150–250 ms (target) | ~tens–100 MB | MIT (OK) | EN/ZH/ES on Hub (w8a16, SD8G2); VI needs self-export | Archived primary TTS. VITS-based, non-AR. VI is the known gap. |
| **vietTTS / VITS-VI** | VI yes (VI-only) | Moderate–good (depends on data) | Low (CPU) | ~tens MB | MIT/Apache (verify) | No (DIY ONNX) | VI-native alternative to MeloTTS-VI fine-tune. |
| **MMS-TTS-vie** (Meta) | VI yes | Lower (intelligibility tier) | Very low (~15 ms) | small | CC-BY-NC-4.0 (avoid) | No | **Avoid for production** (non-commercial). Was archived thermal-tier fallback. |
| **Coqui XTTS-v2** | EN + 16 langs (not VI) | High | Higher (AR, larger) | ~1 GB+ | CPML (restrictive, avoid) | No | **Avoid for commercial.** High quality but license gating + no VI. |
| **Kokoro** (hexgrad) | EN yes + growing multilingual (VI? verify) | Good (lightweight) | Very fast (~80M) | ~80 MB | Apache-2.0 (OK) | No | Lightweight EN TTS option; check VI coverage. |
| **SpeechT5** (Microsoft) | Multilingual yes | Moderate | Higher (larger) | ~100s MB | MIT (OK) | No | General multilingual TTS; slower/heavier. |

- **VI voice is the hard gap.** Our prototype's Piper has EN but VI needs a community
  voice; MeloTTS-VI must be fine-tuned (archived plan's "contribution"); vietTTS is
  VI-native. EN voice is easy (Piper EN, MeloTTS-EN on Hub).
- **Offline guarantee:** Piper and MeloTTS both run fully offline (unlike RTranslator's
  system-TTS dependency — see §5). This is a verifiable Kavi advantage.
- **NPU path (ADR-003):** Piper/MeloTTS are ONNX → ORT QNN EP / QAIRT feasible (Piper
  already ONNX). vietTTS/VITS also ONNX-exportable.
- **Licensing gate:** commercial-clean = Piper, MeloTTS, vietTTS, Kokoro, SpeechT5.
  **Avoid** = MMS-TTS-vie (NC), Coqui XTTS (CPML).

> **Caveats (MT/TTS):** quality/latency figures for MT/TTS are mostly archived-plan
> estimates or training-knowledge, not measured on our 8 Gen 2 — our v0 harness must
> produce the real numbers. License fields marked (verify) need a model-card check
> before any public release. Opus-MT / Piper sizes are approximate.

## 5. RTranslator as product baseline

Kavi must not accept worse benchmark numbers than RTranslator (the closest reference
product), while it narrows to VI↔EN on a fixed platform.

> **Correction:** RTranslator does **not** bundle Piper or any embedded TTS — it uses
> the **Android system TTS** the user has installed (defaults to Google TTS). That
> *strengthens* our "bundled Piper = verifiable 100% offline" advantage: RTranslator's
> offline guarantee for the output leg depends on the user's phone having an offline
> voice pack, which the app doesn't control or verify.

**Latency / RAM table (author-reported, published in the README — cite as-is):**

| Model | Variant | RAM | Latency |
| --- | --- | --- | --- |
| NLLB-Distilled-600M | Full int8, no KV-cache | 2.5 GB | 8 s / 75 tokens |
| NLLB-Distilled-600M | RTranslator optimized (partial int8, KV-cache) | 1.3 GB | 2 s / 75 tokens |
| Whisper-Small-244M | Olive-optimized (full int8, KV-cache) | 1.4 GB | 1.9 s / 11 s audio |
| Whisper-Small-244M | RTranslator optimized | 0.9 GB | 1.6 s / 11 s audio |
| Whisper-Small-244M | Low-RAM mode (<8 GB phones) | 0.5 GB | 2.1 s / 11 s audio |

Use this as the **latency/RAM anchor** — order-of-magnitude reference; re-measure on
our actual 8 Gen 2 unit (author's device unknown).

**Quality (BLEU/COMET/MOS):** no published number. Budget an explicit early task to
**install the APK** (latest v2.1.5 on 8 Gen 2) and run our lean eval set through it
manually, capturing transcribed/translated/synthesized output for scoring against the
same references. Semi-manual (feed audio via UI, capture output), not scriptable.

**Caveats to record:**

- **VI is in RTranslator's full-quality tier**, not the low-quality fallback — a fair,
  non-degraded VI↔EN comparison.
- **RTranslator 3.0 is imminent** (NGI Mobifree-funded; first beta Jun–Aug 2026):
  drops NLLB for Bergamot / Madlad-400-3B / **HY-MT-1.5-1.8B** (the HY-MT we avoid
  for its regional license carve-out). **Snapshot the exact version/commit + date** you
  test; if later citations use "3.0 numbers," check which backend variant was used.
- App code is **Apache-2.0** — its ONNX conversion/optimization scripts are fair game
  to study/adapt (not the NLLB weights). **ML Kit** (closed) is only for language
  auto-detect in WalkieTalkie mode, irrelevant to quality benchmarking.

---

## 6. Harness design (pluggable by construction)

One thin adapter interface per stage so candidates are swappable without harness
changes:

```python
ASRCandidate.transcribe(audio)   -> (text, latency, peak_ram)
MTCandidate.translate(text)       -> (text, latency, peak_ram)
TTSCandidate.synthesize(text)     -> (audio, latency, peak_ram)
```

Each real candidate (whisper.cpp-ggml-int8, Whisper-Small-Quantized-QNN-DLC,
CTranslate2-int8-OpusMT, ORT+QNN-OpusMT, Piper-CPU, Piper-QNN once compiled) is just
a class implementing that interface — register in a manifest, fan out across every
registered candidate per stage with zero harness changes.

- **On-device runner:** an Android instrumented-test / thin service app reads a run
  manifest (`{stage, candidate_id, model_path, config}`), executes the eval set
  through each candidate, logs per-utterance latency, RTF, peak RSS, and dumps raw
  outputs to disk.
- **Off-device scorer:** a host-side Python script ingests those dumps + reference
  labels and computes WER/CER, BLEU/COMET, and objective TTS-quality proxies — keep
  scoring off the phone. (`datasets` + `evaluate` cover loading/corpus + WER/BLEU/COMET;
  MOS needs a separate path — DNSMOS model or a subjective panel.)
- **Fixed, versioned eval manifest** (`eval_manifest_v1.json`): clean + noisy variants
  per SNR level, generated once via §3.5, so every candidate is scored on
  byte-identical inputs — what makes a whisper.cpp-vs-QNN-Whisper A/B actually fair.

---

## 7. Metrics (from `specifications.md` §3)

| Metric | Requirement | Hard? |
| --- | --- | --- |
| RTF (per stage + E2E) | **< 1.0** | **Yes** |
| Turnaround (EOS→SA) | **< 2.0 s** (instrumented from VAD EOS to first SA, not raw compute) | **Yes** |
| No internet at runtime | **Zero network calls (else DQ)** | **Yes** |
| MT BLEU + COMET | Maximize; both directions; on clean ref **and** actual ASR output (cascaded error) | Target |
| TTS MOS | Maximize via high-quality offline TTS + clean input | Target |
| Stability | Crash / silent-failure rate over N consecutive runs (named contest metric) | Named |

---

## 8. Lean eval set & v0 minimal

**Lean eval set:** ~40–60 utterances per direction (VI ASR, EN ASR, VI→EN, EN→VI)
from VIVOS (clean anchor) + a hand-verified VSS/Common Voice-vi slice (conversational)

- Common Voice-en/LibriSpeech (EN) + the bespoke 150–300-sentence gold VI↔EN set
skewed to factory/logistics vocabulary. Each run through the §3.5 SNR sweep
(clean + 4 noisy × 2 noise types) ≈ 400–500 scored clips — small enough to re-run on
every candidate swap, large enough to catch real trend breaks. Scale to full
VSS/PhoST/FLEURS only after narrowing to 1–2 finalists per stage.

**v0 (smallest harness that gates the decision):**

1. ~30–50 utterance slice — clean + one moderate (+5 dB) + one hard (0 dB) condition,
   both languages, both directions.
2. **Two candidates per stage** to start: whisper.cpp-int8 vs Whisper-Small-Quantized-QNN (the only confirmed EN+VI
   pair; see §4 for the broader ASR landscape); CTranslate2-int8-OpusMT vs ORT+QNN-OpusMT (once a vi↔en compile works);
   Piper-CPU vs Piper-QNN if/when compiled.
3. **Automated metrics only:** RTF, turnaround, WER, BLEU, RAM. Defer COMET + human
   MOS to v1 (slower to stand up; not needed to answer "does QNN beat CPU here").
4. **Single device, single run per config** during exploration; add averaging only
   when confirming final numbers.

**Job of v0 (narrowly):** answer *does QNN meaningfully beat CPU on this chip, for
these specific models, before we sink more days into harder QNN engineering*
(dynamic-shape rework, AIMET quantization, DLC packaging)? If the gap on this rough
slice is marginal, that's a cheap, legitimate signal to reconsider effort allocation
— exactly what the experiments were meant to gate.

---

## 9. Open questions / deferred decisions (→ ADR-004)

- **Final dataset set** — confirm licenses for VSS / PhoST / InfoRe before relying.
- **VI→EN ST corpus** — adopt FLEURS ID-alignment, the bespoke gold set, or both?
- **RTranslator snapshot** — which version/commit tested + dated in writeup; APK-eval
  task owner & timeline.
- **MOS proxy** — DNSMOS vs small human panel (5–10 raters, 20–30 clips) for v1.
- **Per-stage candidate list** — which two (and later finalist) models per stage,
  contingent on ADR-003 runtime availability (QAIRT Community Edition access).
- **Architecture (ASR/MT/TTS frameworks)** — **not decided here**; selected by ADR-004
  once v0/v1 numbers exist.
