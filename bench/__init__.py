"""Kavi host-side benchmark harness (v0).

Model-agnostic, pluggable harness for the ASR->MT->TTS pipeline. Candidates
implement a thin adapter interface; the off-device scorer computes the contest
metrics from a fixed, versioned eval manifest so every candidate is scored on
byte-identical inputs.

See docs/benchmarking-plan.md (S6 harness design) and docs/benchmarking-todo.md
(Phases 0-3). This package is the host-side, CPU-default scaffold (Phase 0-3);
the on-device QNN runner is Phase 4 (blocked on the Qualcomm QAIRT EULA).
"""
