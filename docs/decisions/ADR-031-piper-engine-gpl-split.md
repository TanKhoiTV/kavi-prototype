# ADR-031: Piper engine GPL split (open)

## Status

Proposed — **deferred**, not decided

## Date

2026-07-15

## Deciders

Project lead

## Context

Piper is a candidate TTS engine. Its licensing is split across two upstreams with
different terms and different maintenance states:

- **`rhasspy/piper`** — MIT, but **frozen and archived** (Oct 2025).
- **`OHF-Voice/piper1-gpl`** — GPL-3.0, actively maintained.

A GPL engine linked into the app would impose copyleft obligations on the whole
binary, which is disqualifying for a commercial closed-source product. So the
choice is not simply "which Piper?", but *whether* the GPL build can be used at
all, and under what isolation.

This fork **shapes all of TTS**, so leaving it undecided is the main route to a
late TTS swap. Note that Piper is no longer the v1 default — see
[ADR-009](ADR-009-supertonic-tts-v1.md) and
[ADR-024](ADR-024-piper-tts-on-cpu.md) — which lowers the stakes but does not
remove the fork, since Piper remains the documented fallback.

> **Split note (2026-09-25):** extracted from `license-situation.md` (now
> [ADR-029](ADR-029-license-gate.md)), where it was "fork #1". Unlike the other
> determinations in that record it is **genuinely undecided**, so it is a pending
> decision rather than a resolved verdict.

## Decision

**Deferred — no decision recorded.** The position at the time of writing:

- MIT-era `rhasspy/piper` (frozen, archived Oct 2025) is a **licence-clean
  option** (MIT) and can run via **subprocess isolation**, so the GPL
  `espeak-ng`/engine never links into our binary.
- The GPL build `OHF-Voice/piper1-gpl` (GPL-3.0) is **deferred** — not decided.
- **No tech-stack decision follows from this yet:** Piper (MIT-era) is one TTS
  *option* alongside MeloTTS (MIT) and Kokoro (Apache-2.0); the final pick waits
  for the benchmark harness.

### What would close it

A decision on whether the subprocess-isolation pattern is adopted as the
supported Piper path, or whether Piper is dropped from the shipped stack
entirely in favour of the v1 default.

## Consequences

### Positive

- Deferring costs nothing today: Piper is not the v1 default
  ([ADR-009](ADR-009-supertonic-tts-v1.md)).

### Negative / risk

- **An open policy fork can force a late TTS swap** if resolved against the
  current picks ([ADR-029](ADR-029-license-gate.md)).
- The MIT-era upstream is archived, so the clean option is frozen: it will not
  receive fixes.
- Subprocess isolation is an architectural commitment (IPC boundary, lifecycle),
  so adopting it is not a one-line change.

## References

- [ADR-029](ADR-029-license-gate.md) — Shipping license gate (parent record)
- [ADR-009](ADR-009-supertonic-tts-v1.md) — v1 TTS: SupertonicTTS 3 (current default)
- [ADR-024](ADR-024-piper-tts-on-cpu.md) — Piper TTS stays on CPU (conversion position)
- `docs/reference/phase-4-qnn-plan.md` §3.3 — Piper conversion, deferred
