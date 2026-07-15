# License Situation & Gate

**Status:** Proposed — clean/avoid resolved; 2 policy forks + 5 verification
lookups open. This record **gates ADR-004 (architecture / tech-stack)**.
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
| ASR | Whisper Small | MIT / permissive | OpenAI Whisper (verify exact vs plan's Apache-2.0 note) |
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
| Data (public-safe) | Common Voice (CC0), LibriSpeech/FLEURS/LibriTTS (CC-BY-4.0), MUSAN (PD), RIRS_NOISES (CC-BY-4.0), DEMAND (CC-BY-SA-3.0) | various | credit / share-alike as noted |

**Avoid (blocked):**

| Layer | Component | License | Why |
| --- | --- | --- | --- |
| MT | NLLB-200-distilled-600M | CC-BY-NC-4.0 | non-commercial |
| MT | SeamlessM4T v2 | CC-BY-NC-4.0 | non-commercial |
| TTS | MMS-TTS-vie | CC-BY-NC-4.0 | non-commercial |
| TTS | Coqui XTTS v2 | CPML + Coqui shut down | non-commercial + no licensor |
| Voice | Piper `vivos` (VI) | inherits VIVOS CC-BY-NC-SA | do not ship |

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
| 3 | Piper VI voice licenses: `vais1000`, `25hours_single` | PENDING |
| 4 | InfoRe donation / usage terms (vietTTS VI reference) | PENDING |
| 5 | VietSuperSpeech dataset license | PENDING |
| 6 | PhoST dataset license | PENDING |
| 7 | QAIRT Community Edition → commercial post-contest terms | PENDING |
| 8 | Whisper exact license (plan says Apache-2.0; likely MIT) | PENDING |

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

ADR-004 (architecture / tech-stack) is recorded **only after** lookups #3–#7
close and forks #1–#2 are decided. Until then the candidate shortlist in
`docs/benchmarking-plan.md` §4 stands, with the avoid-list already dropped.

## References

- `docs/benchmarking-plan.md` §3.6 (license watch-outs), §4.4 (MT), §4.5 (TTS).
- `docs/onboarding.md` (commercial-clean vs avoid rule).
- ADR-001 / 002 / 003.
