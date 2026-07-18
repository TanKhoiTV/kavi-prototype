# License Situation & Gate

**Status:** Proposed — clean/avoid resolved; **Piper engine GPL split (fork #1)
deferred** (MIT-era Piper is the clean option; GPL build not decided); **QAIRT
runtime redistribution EULA (escalate to Qualcomm) still open**; **Hy-MT
ADOPT** (Vietnam contest, no blocked-region launch; 100M MAU = sky-high
ceiling). All dataset/voice licenses closed via Claude lookup (see #3 / #4 / #7).
This record **gates ADR-004 (architecture / tech-stack)**.
**Date:** 2026-07-15
**Author:** Project lead

---

## Context

Kavi is a **commercial product** (OneVoice contest → product). We **ship a
binary that bundles three independent license layers**, so all three must permit
closed-source commercial distribution:

1. **Model weights** (ASR / MT / TTS) — each has its own license.
2. **Engine / runtime code** (whisper.cpp, CTranslate2, Piper, ORT/QNN) —
   each its own license.
3. **SDK / toolchain** (QAIRT Community Edition, Qualcomm AI Hub) — separate
   from the models.

One **copyleft (GPL)** or **non-commercial (CC-BY-NC / CPML)** item anywhere
in the shipped stack is **disqualifying** unless isolated (subprocess, not linked)
or dropped.

Two nuances:

+ **Eval-time vs ship-time.** NC datasets (VIVOS, viVoice, NOISEX-92) are fine
  to *evaluate* internally; they are forbidden to *bundle* in the shipped app.
+ **Public parent must stay clean.** `aivoice-2026` (public) can host only
  CC0 / CC-BY / permissive content — never NC weights or data.

## Decision

### Resolved now — no further action

**Adopt (commercial-safe):**

| Layer | Component | License | Basis |
| --- | --- | --- | --- |
| ASR | Whisper Small | MIT | OpenAI Whisper — confirmed MIT; the plan's 'Apache-2.0' note was wrong |
| ASR | PhoWhisper Small | BSD-3 | same arch as Whisper Small |
| ASR | Zipformer-30M-VI | Apache-2.0 | |
| ASR | Moonshine Tiny VI | Apache-2.0 | |
| ASR | Silero VAD | MIT | `silero-vad` dep |
| MT | Opus-MT (vi-en + en-vi) | Apache-2.0 | current prototype |
| MT | M2M-100 | MIT | realistic finalist vs Opus-MT |
| MT | MADLAD-400 | Apache-2.0 | size-blocked, not license |
| TTS | MeloTTS | MIT | AI-Hub-backed EN/ZH/ES; VI needs self-export |
| TTS | Kokoro | Apache-2.0 | EN-leg only (no VI confirmed) |
| TTS | SpeechT5 | MIT | EN only (needs VI fine-tune) |
| TTS voice | Piper `vais1000` (VI) | CC BY 4.0 | attribution required (VAIS/IEEE DataPort); clean VI voice |
| TTS engine | Piper (MIT-era `rhasspy/piper`) | MIT | **option**; run via subprocess isolation; GPL build (`OHF-Voice/piper1-gpl`) deferred |
| SDK | QAIRT Community Edition | free for contest | via free Qualcomm ID; AI Hub build-time only |
| Data (eval-only) | VIVOS, viVoice, NOISEX-92 | NC / ambiguous | internal eval, never bundle |
| Data (public-safe) | Common Voice (CC0), LibriSpeech/FLEURS/LibriTTS (CC-BY-4.0), MUSAN (PD), RIRS_NOISES (CC-BY-4.0), DEMAND (CC-BY-SA-3.0), VietSuperSpeech (MIT; labels Zipformer pseudo-labeled, not gold) | various | credit / share-alike as noted; VSS usable but verify labels |

**Avoid (blocked):**

| Layer | Component | License | Why |
| --- | --- | --- | --- |
| MT | NLLB-200-distilled-600M | CC-BY-NC-4.0 | non-commercial |
| MT | SeamlessM4T v2 | CC-BY-NC-4.0 | non-commercial |
| TTS | MMS-TTS-vie | CC-BY-NC-4.0 | non-commercial |
| TTS | Coqui XTTS v2 | CPML + Coqui shut down | non-commercial + no licensor |
| Voice | Piper `vivos` (VI) | inherits VIVOS CC-BY-NC-SA | do not ship |
| Data | PhoST | research/educational ONLY, no redistribution (VinAI terms) | was VI→EN corpus candidate in plan; now avoid for commercial |
| Voice | Piper `25hours_single` (VI) | **License: Unknown** — voice MODEL_CARD (verified 2026-07-18); trained on "InfoRe Technology 1" (InfoRe-derived) | AVOID — no license grant; do not ship |
| Data | InfoRe (vietTTS corpus) | no formal license; canonical `VINAI/InfoRe` is **gated** (HF HTTP 401, no published terms — verified 2026-07-18) | AVOID — no commercial grant; taints any voice trained on it |

### Open — policy forks (fork #1 requires a decision; fork #2 resolved)

1. **Piper engine — GPL split deferred.** MIT-era `rhasspy/piper` (frozen,
   archived Oct 2025) is a **licensed-clean option** (MIT) and can run via
   **subprocess isolation** so the GPL `espeak-ng`/engine never links into our
   binary. The GPL build `OHF-Voice/piper1-gpl` (GPL-3.0) is **deferred** — not
   decided now. **No tech-stack decision yet:** Piper (MIT-era) is one TTS
   *option* alongside MeloTTS (MIT) / Kokoro (Apache-2.0); the final pick waits
   for the benchmark harness. Shapes *all* TTS.
2. **Hy-MT1.5 regional carve-out — RESOLVED: ADOPT.** Contest is in
   **Vietnam**; no launch planned for the excluded regions (EU / UK / South
   Korea). The HY Community License therefore **permits commercial use** of
   Hy-MT1.5. The **100M MAU** threshold is noted as a **sky-high ceiling** (not
   a current concern) — if we ever approach it, a separate Tencent license is
   required. Outputs must not train non-Hunyuan models. Hy-MT is a usable MT
   candidate alongside Opus-MT / M2M-100.

### Open — verification lookups (facts pending, no judgment)

| # | Item | Status |
| --- | --- | --- |
| 3 | Piper VI voice licenses: `vais1000`, `25hours_single`, `vivos` | RESOLVED — `vais1000` = **CC BY 4.0** (ADOPT, attribution to VAIS/IEEE DataPort); `vivos` = CC BY-NC-SA (**AVOID**, confirmed); `25hours_single` = **License: Unknown** (voice MODEL_CARD, verified 2026-07-18; trained on InfoRe-derived data) → **AVOID** (no grant). |
| 4 | InfoRe donation / usage terms (vietTTS VI reference) | RESOLVED — **AVOID**. Informal donation with **no formal license, no commercial grant, no indemnification**; canonical `VINAI/InfoRe` is **gated** (HF HTTP 401, no published terms — verified 2026-07-18), only derivative community sets are public. Taints any voice trained on it (incl. `25hours_single`, `vivos`, reference vietTTS). Treat research-only. |
| 5 | VietSuperSpeech dataset license | RESOLVED — **MIT** (commercial-safe). Quality caveat: labels are Zipformer pseudo-labeled, not gold. |
| 6 | PhoST dataset license | RESOLVED — **research/educational ONLY, no redistribution** (VinAI terms). → AVOID for commercial; was a VI→EN corpus candidate in the plan. |
| 7 | QAIRT / Qualcomm AI Hub commercial terms | PARTIAL — `qai_hub_models` pip package = **BSD-3** (ADOPT). AI Hub compile service is **free today but revocable at Qualcomm's sole discretion** (QUIC can quote/charge). QAIRT **runtime redistribution (PKLA)** is **login-gated / not publicly verified** → **escalate to Qualcomm** before shipping. Conditional adopt. |
| 8 | Whisper exact license | RESOLVED — **MIT** (plan's 'Apache-2.0' note was wrong). |

## Consequences

### Positive

+ De-risks ADR-004 **before** the benchmark harness runs — most candidates
  are already license-decided.
+ The adopt/avoid lists let us wire candidates into the harness with no legal
  ambiguity.

### Negative / risk

+ The two policy forks can force a **late TTS/MT swap** if resolved against the
  current picks.
+ Eval-only NC datasets are easy to **accidentally bundle** — enforce in the
  harness data-prep step.

## Open items → ADR-004

ADR-004 (architecture / tech-stack) records the licensed-clean candidate set
but **defers the final tech-stack pick** until the v0 benchmark harness runs.
Remaining gates: **Piper engine GPL split** (deferred — MIT-era is the clean
option), the **QAIRT runtime redistribution EULA** (escalate to Qualcomm), and
harness confirmation that the CPU-default stack is license-clean. Lookups #3–#8
are closed or advanced. Candidate shortlist in `docs/benchmarking-plan.md` §4
stands, with the avoid-list already dropped.

## References

+ `docs/benchmarking-plan.md` §3.6 (license watch-outs), §4.4 (MT), §4.5 (TTS).
+ `docs/onboarding.md` (commercial-clean vs avoid rule).
+ ADR-001 / 002 / 003.
+ **Corrections to `docs/benchmarking-plan.md`** (this record supersedes): §3.3 / §3.6 — VietSuperSpeech is **MIT** (not "verify"); PhoST is **research-only, no redistribution** (not "verify") → move to avoid; §4.1 — Whisper is **MIT** (plan's "Apache-2.0" is wrong).
