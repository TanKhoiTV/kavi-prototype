# Documentation

Internal documentation for the Kavi prototype. **Public** contest docs
(contest-info, registration checklist, Luma answers, pitch deck) live in the
parent repo `aivoice-2026/docs/`.

## Index

- `onboarding.md` — new-member guide: decodes the jargon, the ADRs, and
the repo layout. **Start here.**
- `onboarding-quiz.md` — comprehension checkpoint: 12 questions to verify a
new member understands the current state.
- `benchmarking-plan.md` — datasets, candidate models (ASR / MT / TTS), harness
design, metrics, and the v0 minimal. Gates ADR-004.
- `benchmarking-todo.md` — execution checklist / pitch for the v0 benchmark
harness (what to build, in what order).
- `phase-4-qnn-plan.md` — executable spec for the on-device QNN conversion &
  comparison (Phase 4): env contract, per-model ONNX export, artifact
  bundling, instrumented runner, and the RTF<1.0 / turnaround<2.0s gates.
  Precedes the Phase-4 implementation (ADR-003 determination method).
- `decisions/` — Architecture Decision Records (ADR-001 offline-first,
  ADR-002 target platform, ADR-003 Hexagon runtime, ADR-004 ASR/MT/TTS
  architecture, ADR-005 QNN conversion workarounds, ADR-006 Android runner
  architecture, plus `license-situation.md`). Source of truth for
  architecture choices.

## Planned / deferred

- `architecture.md` — system architecture (deferred; we figure this out later).
- `design.md` — design decisions.
- Legacy ADRs (`001`, `002`) are in `../archive/docs/adr/`.
- `pitch-deck/` — registration pitch materials (legacy in `../archive/docs/pitch-deck/`).

## Reference

The full previous documentation set is preserved under `../archive/docs/`.
