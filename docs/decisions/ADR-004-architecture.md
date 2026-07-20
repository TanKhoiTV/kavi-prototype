# ADR-004: Speech-to-Speech Architecture / Tech-Stack

**Status:** Draft — **tech stack NOT yet decided.** This record captures the
license-gated parameters that are already settled and lists the open parameters
the v0 benchmark harness must close. It deliberately makes **no final pick**
of ASR / MT / TTS models or runtime.
**Date:** 2026-07-15
**Author:** Project lead
**Supersedes / relates to:** ADR-001 (offline-first), ADR-002 (target platform),
ADR-003 (Hexagon runtime strategy), `docs/decisions/license-situation.md`.

---

## Context

Kavi is a **commercial, fully-offline on-device** Vietnamese ↔ English
speech-to-speech translator for a **Snapdragon 8 Gen 2** (Hexagon HTP v73),
Android. ADR-001/002/003 fixed the *shape* of the system (offline-first, phone
form factor, CPU baseline with NPU deferred to on-device results). The actual
**model + runtime choices** were deferred to benchmarking, gated by licensing.

`docs/decisions/license-situation.md` has now cleared the candidate set:
most components are license-clean, and the remaining unknowns are few. This ADR
records what is **settled** and what stays **open** until the v0 harness
(`docs/benchmarking-plan.md` §8) produces on-device numbers.

> **No tech-stack decision is made here.** The final ASR/MT/TTS/runtime pick
> follows the harness results. Anything below marked *option* / *open* is a
> parameter, not a decision.

## Parameters settled (license-gated)

### MT — Hy-MT1.5 is ADOPT-able

- HY Community License excludes only EU / UK / South Korea; **Vietnam (contest
  location) is in territory**, and no launch is planned for the excluded regions.
- **100M MAU** threshold noted as a **sky-high ceiling** (not a current concern);
  a separate Tencent license is required only if we approach it.
- `Opus-MT` (Apache-2.0) remains the current prototype + a clean alternative.
- Both are license-clean MT *candidates*.

### TTS — MIT-era Piper is a clean *option*; GPL build deferred

- `rhasspy/piper` (MIT, archived Oct 2025) is a **licensed-clean option**, run
  via **subprocess isolation** so the GPL `espeak-ng`/engine never links into
  our binary.
- The GPL build `OHF-Voice/piper1-gpl` (GPL-3.0) is **deferred** — not decided.
- `vais1000` is a clean **CC BY 4.0** Vietnamese voice (attribution required).
- `MeloTTS` (MIT) / `Kokoro` (Apache-2.0) are alternatives (no off-the-shelf
  VI voice). **No final TTS pick yet.**

### ASR — leading candidates are license-clean

- `Whisper Small` (MIT, confirmed EN+VI) and `PhoWhisper Small` (BSD-3,
  VI-accuracy winner) are the leading candidates; `Zipformer-30M` / `Moonshine`
  are VI-only. All permissive. **No final ASR pick yet.**

### Runtime — CPU baseline is license-clean; NPU pending Qualcomm

- Per ADR-003, **CPU / XNNPACK int8 is the license-clean baseline** and can ship
  today.
- The **NPU / QAIRT path is now unblocked** — the Qualcomm runtime gate is
  resolved (ADOPT, clean; see `license-situation.md`).

## Open parameters (closed by the v0 harness + remaining lookups)

| # | Open parameter | Closes when |
| --- | --- | --- |
| 1 | **Final ASR / MT / TTS models** | v0 harness WER / BLEU / RTF / peak-RAM on the CPU-default stack. **Initial slate already chosen in `bench/`:** faster-whisper Small int8 (ASR), CTranslate2 Opus-MT vi→en int8 (MT), Piper EN (TTS). Closes when on-device QNN numbers exist (Phase 4, QAIRT gate resolved). |
| 2 | **Piper engine GPL split** | resolved as MIT-era subprocess (default option) or alternative; GPL build stays deferred |
| 3 | **QAIRT runtime EULA** (Qualcomm) | **RESOLVED — ADOPT (clean)** (see `license-situation.md`) |
| 4 | **Pre-ASR denoising gate** | v0 harness Wiener/RNNoise toggle result (benchmarking-plan §8) |

## Decision (deferred)

**No architecture / tech-stack decision is recorded yet.** Once parameters

# 1–#4 close, ADR-004 will be promoted from *Draft* to *Accepted* with the

concrete model + runtime matrix. Until then, development proceeds on the
**license-clean CPU-default stack** (faster-whisper / Opus-MT / MIT-era Piper or
MeloTTS) so the harness can run. The v0 host-side harness is implemented in
`bench/` (PR #28/#36) and has already chosen this initial candidate slate.

## Consequences

### Positive

- Licensing no longer blocks standing up the v0 harness — a clean default stack
  exists for every stage.
- The candidate set is narrowed to license-clean options, removing legal risk
  from the benchmark.

### Negative / risk

- The final model pick may still shift after harness numbers (e.g., if a
  license-clean model misses the RTranslator quality bar).
- **Qualcomm QAIRT EULA (#3) is resolved** (ADOPT, clean). The NPU path is
  unblocked; CPU fallback (ADR-003) remains available.

## References

- ADR-001 / 002 / 003.
- `docs/decisions/license-situation.md` (license gate).
- `docs/benchmarking-plan.md` §4 (candidate landscape), §8 (v0 harness).
- `docs/onboarding.md` (architecture decoded for newcomers).
