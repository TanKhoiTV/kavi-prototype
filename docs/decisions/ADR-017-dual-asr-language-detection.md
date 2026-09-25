# ADR-017: Dual ASR inference for language-autonomous direction detection

## Status

Superseded by [ADR-008](ADR-008-dual-zipformer-asr.md)

## Date

2026-07-26

## Deciders

Kavi team

## Context

The system must detect whether the user spoke Vietnamese or English to select the
correct MT direction (VI→EN or EN→VI). RTranslator solves this with ML Kit
language identification — a separate closed-source dependency, and one that
requires Google Play Services, which conflicts with the offline-first invariant
([ADR-001](ADR-001-offline-first-on-device-architecture.md)).

> **Split note:** extracted from the former `ADR-007 Decision 6`. The decision
> below was **superseded on 2026-07-27** by
> [ADR-008](ADR-008-dual-zipformer-asr.md), which replaced Whisper Small with two
> parallel Zipformer transducers. It is retained unedited as the historical
> record; the *goal* it established — no external language-detection dependency —
> still holds in ADR-008.

## Decision

Run two ASR decoder batches in parallel for every utterance — one with English
prompts, one with Vietnamese prompts — and use confidence scores to select the
language.

### Batch configuration

- ASR encoder runs once (language-agnostic, shared encoder).
- ASR decoder runs at **batch_size=2** (one slot for VI, one for EN).
- Language selected by comparing decoder confidence scores (log-probability per
  token averaged over the decoded sequence).
- No separate language-identification model or API call.

### Performance impact

| Aspect | Single ASR | Dual ASR (proposed) |
| --- | --- | --- |
| Encoder runs | 1 | 1 (unchanged — encoder is language-agnostic) |
| Decoder runs | 1 | 1 (batch_size=2, same total compute) |
| Language ID latency | ~200 ms (ML Kit) | 0 ms (eliminated) |
| External dependency | Google Play Services | None |

### Caveat

This requires the ASR model to support both VI and EN in a single decoder pass —
confirmed for Whisper Small (96 languages) and PhoWhisper (Vietnamese-optimised
Whisper fine-tune, also supports EN). Moonshine Tiny is English-only and cannot
use this strategy.

## Consequences

### Positive

- **No external language detection dependency** — dual ASR batch eliminates ML Kit
  (or any Play Services dependency), keeping the offline-first invariant clean.

### Negative / risk

- **Dual ASR requires a multilingual ASR model** — Moonshine Tiny (EN-only) cannot
  use this strategy. (This constraint is what later motivated the replacement
  architecture in ADR-008, which achieves the same goal with two monolingual
  models compared by confidence.)

## References

- [ADR-007](ADR-007-translation-service.md) — TranslationService (parent record)
- [ADR-008](ADR-008-dual-zipformer-asr.md) — **Supersedes this record**
- [ADR-001](ADR-001-offline-first-on-device-architecture.md) — Offline-first, on-device architecture
