# Documentation

Internal documentation for the Kavi prototype. **Public** contest docs
(contest-info, registration checklist, Luma answers, pitch deck) live in the
parent repo `aivoice-2026/docs/` (the prototype copy is deprecated — see
`reference/contest-info.md`).

## Current — read these first

- `onboarding.md` — new-member guide: decodes the jargon, the ADRs, and the
  repo layout. **Start here.**
- `onboarding-quiz.md` — comprehension checkpoint (12 questions).
- `android-implementation-plan.md` — the active implementation plan
  (ADR-007 → ADR-010): Milestones 0–6, risks R1–R5, execution order.
- `rtranslator-test-protocol.md` — Phase-5 APK test procedure (live).
- `specifications.md` — the six objective metrics + hard thresholds; cited by
  every plan as the gate contract.

## Hot reference — source of truth

- `decisions/` — Architecture Decision Records, one decision per record
  (`ADR-001` … `ADR-031`). Start at `decisions/README.md` — the index with the
  supersession graph and the open parameters. Immutable by convention; status
  changes are recorded in the ADR header.

## Cold reference — superseded / deprecated

- `reference/` — everything no longer current, kept for history and for the
  content still consulted:
  - `benchmarking-plan.md` — pre-decision dataset/candidate landscape; the
    **corpus catalog (§3) and licensing notes** are still consulted for eval work.
  - `benchmarking-todo.md` — v0 harness execution checklist (implemented).
  - `phase-4-qnn-plan.md` — QNN conversion spec; **only the Opus-MT encoder
    path (§2, §8, §9) is live**; Whisper/Piper sections are reference-only.
  - `denoising-gate-results.md` — Phase-6 gate result (Wiener ADOPTED).
  - `contest-info.md` — stale copy; canonical version is in the parent repo.
  - `additional-reading.md` — reading list.

## Planned / deferred

- `architecture.md` — system architecture (deferred; see ADR-007 instead).
- Legacy ADRs (`001`, `002`) are in `../archive/docs/adr/`.

## Reference

The full previous documentation set is preserved under `../archive/docs/`.
