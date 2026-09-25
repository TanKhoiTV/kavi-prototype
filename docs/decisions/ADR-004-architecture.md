# ADR-004: Speech-to-Speech Architecture / Tech-Stack *(withdrawn)*

## Status

Withdrawn — superseded by [ADR-008](ADR-008-dual-zipformer-asr.md) (ASR),
[ADR-009](ADR-009-supertonic-tts-v1.md) (TTS) and
[ADR-030](ADR-030-qairt-runtime-redistribution.md) (QAIRT runtime licence).
The **MT model choice remains unrecorded** — see
[Open parameters #1](README.md#open-parameters).

## Date

2026-07-15

## Deciders

Project lead

## Context

This record was created as the umbrella **tech-stack** ADR while individual model
and runtime choices were still blocked on licensing and benchmarking. It never
made a decision — deliberately. Its own text stated:

> **No architecture / tech-stack decision is recorded yet.**

Instead it tracked four "settled parameters" (license-gated options) and four
"open parameters" to be closed by the v0 benchmark harness. As those parameters
closed, their decisions were recorded in the records that actually made them —
which left this file holding no decision at all, and a parameter table that was
better served by an index.

## Decision

**Withdrawn.** There is no decision to record here.

The parameter register it maintained has been superseded:

- **Settled parameters** — the license-gated candidate set — are now the verdict
  tables in [ADR-029](ADR-029-license-gate.md).
- **Open parameters** — the four items this record tracked — are now
  [Open parameters](README.md#open-parameters) in the index, where each is owned
  by the record that can close it.
- **The choices that closed** were recorded elsewhere:
  - ASR → [ADR-008](ADR-008-dual-zipformer-asr.md) (dual Zipformer) and
    [ADR-027](ADR-027-asr-cpu-only.md) (CPU-only)
  - TTS → [ADR-009](ADR-009-supertonic-tts-v1.md) / [ADR-028](ADR-028-vieneu-tts-migration.md)
  - Runtime licence gate → [ADR-030](ADR-030-qairt-runtime-redistribution.md)
  - Piper licence fork → [ADR-031](ADR-031-piper-engine-gpl-split.md) (still open)

### What this record never closed

The **MT model**. Opus-MT is the current prototype and is pinned in `.kavi.yaml`,
but no ADR records the choice, and the Harve/MT candidate comparison in
`docs/reference/benchmarking-plan.md` §4.4 was never resolved into a decision.
That gap is tracked as
[Open parameters #1](README.md#open-parameters) and is expected to be closed by a
dedicated MT decision record.

## Consequences

### Positive

- The register that supersedes this file is generated from the actual records, so
  it cannot drift out of date the way a hand-maintained parameter table does.
- The status no longer implies a decision exists where none does.

### Negative / risk

- Historical references to "ADR-004" (there were eight tracked files) now point at
  a withdrawn record; they must be repointed to the specific decision they meant
  (this was done in the same change).

## References

- [ADR-008](ADR-008-dual-zipformer-asr.md) — v1 Android ASR (closed the ASR parameter)
- [ADR-009](ADR-009-supertonic-tts-v1.md) — v1 Android TTS (closed the TTS parameter)
- [ADR-029](ADR-029-license-gate.md) — Shipping license gate (holds the candidate verdicts)
- [ADR-030](ADR-030-qairt-runtime-redistribution.md) — QAIRT runtime redistribution (closed the runtime-licence parameter)
- [ADR-031](ADR-031-piper-engine-gpl-split.md) — Piper engine GPL split (the remaining licence fork)
- [Open parameters](README.md#open-parameters) — where the tracked items now live
