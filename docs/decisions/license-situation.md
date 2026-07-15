# License Situation & Gate

**Status:** Proposed — clean/avoid resolved; 2 policy forks open; 3 of 6
lookups closed (Whisper=MIT, VietSuperSpeech=MIT, PhoST=research-only→avoid),
3 partial (Piper VI voice licenses, InfoRe, QAIRT commercial EULA); Piper
engine GPL split confirmed. This record **gates ADR-004 (architecture /
tech-stack)**.
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

- **Eval-time vs ship-time.** NC datasets (VIVOS, viVoice, NOISEX-92) are fine
  to *evaluate* internally; they are forbidden to *bundle* in the shipped app.
- **Public parent must stay clean.** `aivoice-2026` (public) can host only
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

### Open — policy forks (require a human/business call)

1. **Piper engine GPL split.** Pin MIT-era `rhasspy/piper` (frozen) + run via
   **subprocess isolation** (espeak-ng / GPL engine stays a separate non-linked
   process), **or** accept GPL-3.0 (`OHF-Voice/piper1-gpl`) source-disclosure,
   **or** switch TTS engine (MeloTTS / Kokoro). Shapes *all* TTS.
2. **Hy-MT1.5 regional carve-out.** Verify whether our deployment market is
   excluded by the HY Community License; if excluded → drop to Opus-MT / M2M-100.

### Open — verification lookups (facts pending, no judgment)

| # | Item | Status |
| --- | --- | --- |
| 3 | Piper VI voice licenses: `vais1000`, `25hours_single` | PARTIAL — engine split CONFIRMED: `rhasspy/piper` (MIT) **archived/read-only Oct 2025**; active fork `OHF-Voice/piper1-gpl` is **GPL-3.0**. Per-voice VI licenses not in VOICES.md (links only); HF voice cards not fetched this pass — PENDING. `vivos` = NC confirmed. |
| 4 | InfoRe donation / usage terms (vietTTS VI reference) | PENDING — vietTTS/InfoRe repo not locatable (GitHub search 0 results; guessed URLs 404). Defer; only matters if we pick vietTTS. |
| 5 | VietSuperSpeech dataset license | RESOLVED — **MIT** (commercial-safe). Quality caveat: labels are Zipformer pseudo-labeled, not gold. |
| 6 | PhoST dataset license | RESOLVED — **research/educational ONLY, no redistribution** (VinAI terms). → AVOID for commercial; was a VI→EN corpus candidate in the plan. |
| 7 | QAIRT Community Edition → commercial post-contest terms | PARTIAL — free for contest via free Qualcomm ID CONFIRMED; QAIRT is a supported on-device runtime (AI Hub). Explicit commercial-redistribution EULA not in public pages (ToS URL 404) — PENDING that EULA. |
| 8 | Whisper exact license | RESOLVED — **MIT** (plan's 'Apache-2.0' note was wrong). |

## Consequences

### Positive

- De-risks ADR-004 **before** the benchmark harness runs — most candidates
  are already license-decided.
- The adopt/avoid lists let us wire candidates into the harness with no legal
  ambiguity.

### Negative / risk

- The two policy forks can force a **late TTS/MT swap** if resolved against the
  current picks.
- Eval-only NC datasets are easy to **accidentally bundle** — enforce in the
  harness data-prep step.

## Open items → ADR-004

ADR-004 (architecture / tech-stack) is recorded **only after** lookups #3–#8
close and forks #1–#2 are decided. Until then the candidate shortlist in
`docs/benchmarking-plan.md` §4 stands, with the avoid-list already dropped.

## References

- `docs/benchmarking-plan.md` §3.6 (license watch-outs), §4.4 (MT), §4.5 (TTS).
- `docs/onboarding.md` (commercial-clean vs avoid rule).
- ADR-001 / 002 / 003.
- **Corrections to `docs/benchmarking-plan.md`** (this record supersedes): §3.3 / §3.6 — VietSuperSpeech is **MIT** (not "verify"); PhoST is **research-only, no redistribution** (not "verify") → move to avoid; §4.1 — Whisper is **MIT** (plan's "Apache-2.0" is wrong).
