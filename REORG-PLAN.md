# Reorganization Plan — docs/ hot/cold split + ADR reconciliation

> **Purpose:** Execute the documentation reorganization agreed in session
> 2026-08-05: classify all docs into **current** (live), **hot reference**
> (`docs/decisions/`, the ADRs), and **cold reference** (`docs/reference/`,
> superseded/deprecated). Reconcile stale content against the latest decisions
> (ADR-007 → ADR-010).
> **Branch:** `chore/docs-reorg` (create from `main`)
> **Commit:** one commit, Conventional Commits message
> `docs: reconcile plans with ADR-007-010; archive superseded docs to reference/`
> **Scope guard:** docs-only. **Do NOT touch** `android/` (modified submodule),
> `.pi/PLAN.md`, `bench/`, `models/`, `scripts/`, or any ADR other than
> ADR-007 (one appended status note) and the new ADR-011.

---

## 1. Background — what is stale (verified 2026-08-05)

| Doc | Problem |
| --- | --- |
| `docs/benchmarking-plan.md` | Pre-ADR landscape; ASR table says Zipformer is "VI-only" (ADR-008 chose Dual Zipformer VI+EN); denoising gate described as "never executed" (it was — Wiener ADOPTED); Piper-GPL framed as "decision needed now" (ADR-009 resolved TTS); "Architecture not decided" (ADR-007/008/009/010 decide it) |
| `docs/phase-4-qnn-plan.md` | Whisper (ADR-008: ASR CPU-only) and Piper (ADR-005 D3 + ADR-009) QNN paths obsolete; only the **Opus-MT encoder** path is live |
| `docs/denoising-gate-results.md` | Historical result, not a live doc |
| `docs/contest-info.md` | Byte-identical duplicate of canonical `aivoice-2026/docs/contest-info.md` (parent repo) |
| `docs/benchmarking-todo.md` | v0 harness implemented (PR #28/#36); checklist superseded |
| `docs/additional-reading.md` | Static reading list |
| `docs/onboarding.md`, `docs/onboarding-quiz.md` | Stale links + stale answers (Q10 denoising "open", Q11 Piper "decide now", "architecture not decided" prose) |
| `docs/android-implementation-plan.md` | NEW (2026-08-03) — already ADR-aligned; needs 3 corrections (see D3.x) |
| `.gitignore` `models/qnn/*` | Host QNN artifacts are gitignored/regenerable — on-device artifacts must live in `kavi-android` assets (ADR-011) |

## 2. Target structure

```
docs/
├── README.md                        # rewritten index (Step 5)
├── specifications.md                # [current] metrics + gates
├── android-implementation-plan.md   # [current] active plan
├── rtranslator-test-protocol.md     # [current] Phase-5 procedure
├── onboarding.md                    # [current] refreshed
├── onboarding-quiz.md               # [current] refreshed
├── decisions/                       # [hot reference] UNCHANGED except ADR-007 D7 note + new ADR-011
└── reference/                       # [cold] superseded / deprecated
    ├── README.md
    ├── benchmarking-plan.md
    ├── benchmarking-todo.md
    ├── phase-4-qnn-plan.md
    ├── denoising-gate-results.md
    ├── contest-info.md
    └── additional-reading.md
```

---

## 3. Steps (apply in order)

### Step 0 — preflight

1. `git checkout main && git checkout -b chore/docs-reorg`
2. `git status --short` — expect pre-existing `M android` (submodule pointer) and
   untracked `docs/android-implementation-plan.md`, `REORG-PLAN.md`. Leave them.
3. Confirm no other uncommitted work.

### Step 1 — ADR-007 Decision 7 status note (append only)

File: `docs/decisions/ADR-007-production-inference-architecture.md`.
Append after the last line of **Decision 7** section (ends with "...not the final
model pick."), a new paragraph:

```markdown
> **Status note (2026-08-05):** the Phase-6 denoising gate
> (`docs/reference/denoising-gate-results.md`) ran the archived binary gate and
> **ADOPTED Wiener** (`noisereduce`, `prop_decrease=0.5`): weighted-average WER
> 49.82% vs raw 51.23%; RNNoise rejected (64.36%). The GTCRN-vs-Wiener on-device
> choice remains open — see `docs/android-implementation-plan.md` Risk R1.
```

Do not modify any other part of any ADR.

### Step 2 — moves + `docs/reference/README.md`

```bash
mkdir -p docs/reference
git mv docs/benchmarking-plan.md      docs/reference/benchmarking-plan.md
git mv docs/benchmarking-todo.md      docs/reference/benchmarking-todo.md
git mv docs/phase-4-qnn-plan.md       docs/reference/phase-4-qnn-plan.md
git mv docs/denoising-gate-results.md docs/reference/denoising-gate-results.md
git mv docs/contest-info.md           docs/reference/contest-info.md
git mv docs/additional-reading.md     docs/reference/additional-reading.md
```

Create `docs/reference/README.md` with exactly:

```markdown
# Cold reference — superseded / deprecated docs

These docs are **no longer current** but are kept for history and for the
content they still contribute. Do **not** treat them as source of truth for
architecture — the ADRs in `../decisions/` are.

| File | Why it is here | Still consulted for |
| --- | --- | --- |
| `benchmarking-plan.md` | Pre-decision landscape; architecture decided in ADR-007/008/009 | Dataset corpus catalog + licenses (§3), noise-mixing recipe (§3.5), RTranslator baseline notes (§5) |
| `benchmarking-todo.md` | v0 harness implemented (PR #28/#36); superseded by `.pi/PLAN.md` | Historical checklist |
| `phase-4-qnn-plan.md` | Superseded scope — Whisper/Piper QNN paths obsolete (ADR-008, ADR-005 D3 + ADR-009) | **Opus-MT encoder conversion path only** (§2 pipeline, §8 verified QAIRT commands, §9 calibration) |
| `denoising-gate-results.md` | One-off Phase-6 gate result | Wiener-adoption evidence for ADR-007 D7 / android plan Risk R1 |
| `contest-info.md` | Byte-identical copy of the canonical parent-repo doc (`aivoice-2026/docs/contest-info.md`) | n/a |
| `additional-reading.md` | Static reading list | n/a |
```

### Step 3 — content edits (apply exactly)

#### D1 — `docs/reference/phase-4-qnn-plan.md`

(a) In the title blockquote, after the `**Status:**` line, insert:

```markdown
> **Superseded scope (2026-08-05):** the ASR (Whisper) and TTS (Piper) QNN paths
> are **obsolete** — ADR-008 keeps ASR CPU-only (Dual Zipformer via sherpa-onnx);
> ADR-009 replaces Piper with Supertonic Phase 1 (ADR-005 D3 already deferred
> Piper QNN). **Live scope = Opus-MT encoder only** (§2, §8, §9). Whisper/Piper
> sections are retained for reference only.
```

(b) In **§3.1**, under the heading `### 3.1 ASR — Whisper Small (244M, MIT) — *evaluate re-source*`, insert:

```markdown
> **Superseded (ADR-008):** ASR is CPU-only Dual Zipformer. The Whisper ONNX/QNN
> path below is retained for reference only.
```

(c) In **§3.3**, after the existing ADR-005 blockquote, append:

```markdown
> **ADR-009 supersedes further (2026-07-30):** v1 TTS is Supertonic Phase 1
> (sherpa-onnx `OfflineTts`) → VieNeu-TTS Phase 2, with Piper VITS as fallback.
> Piper QNN conversion is permanently out of scope.
```

(d) In **§4**, after the `app/src/main/assets/` bullet, append:

```markdown
- **Provenance & commit (ADR-011):** on-device artifacts (HTP v73 context
  binary, model `.so`, ONNX decoder) are committed **inside `kavi-android`
  assets**. Host-side `prototype/models/qnn/*` outputs are gitignored
  (`.gitignore` `models/qnn/*`, commit 3502156) and regenerable — never treat
  them as deliverables.
```

(e) In **§11**, after the first bullet, append:

```markdown
  → **2026-08-05:** superseded scope — see banner. Only the Opus-MT encoder path
  (§2, §8, §9) is live; Whisper/Piper are reference-only.
```

#### D2 — `docs/reference/benchmarking-plan.md`

(a) **§4.1 table:** after the Zipformer-30M-VI row insert:

```markdown
| **Zipformer small EN** (csukuangfj, ~27M) | — | — | — | **EN only** | Apache-2.0 | No (untested) |
```

(b) **§4.1 bullet** — replace the bullet
`- **Zipformer / Moonshine are VI-only** — they cannot serve the EN→VI direction's ASR\n  leg and can only compete for the VI→EN direction.`
with:

```markdown
- **Zipformer / Moonshine are single-language** — neither serves both directions alone.
> **Superseded (ADR-008, 2026-07-30):** the v1 ASR decision pairs the VI
> Zipformer-30M with the **EN Zipformer small** as a **Dual-Zipformer CPU
> configuration** via sherpa-onnx, serving both directions. Whisper/PhoWhisper
> QNN re-sourcing is out of scope; this table is the pre-decision landscape.
```

(c) **§4.4** — after the "Realistic finalist set" bullet append:

```markdown
> **Resolved (ADR-007):** Opus-MT vi↔en is the v1 MT choice; M2M-100 remains a
> contingency candidate.
```

(d) **§4.5** — replace the "Piper license is the single most consequential open item" bullet with:

```markdown
- **Piper license — resolved for v1 (ADR-009):** TTS is Supertonic Phase 1 →
  VieNeu-TTS Phase 2; Piper VITS is fallback only. The MIT/GPL fork question
  matters only if the fallback is exercised — pin the MIT-era `rhasspy/piper`
  snapshot then.
```

(e) **§8 denoising subsection** — replace the bullet beginning
`- **That Phase-1 re-run was never executed** —` (through `is **still open**.`) with:

```markdown
- **RESOLVED (2026-07-20, Phase-6 gate):** executed — see
  `docs/reference/denoising-gate-results.md`. **Wiener ADOPTED**
  (`noisereduce`, `prop_decrease=0.5`): weighted avg WER **49.82%** vs raw
  **51.23%**; RNNoise REJECTED (64.36%). Smoke test only (2 utts × 5
  conditions); adaptive threshold on clean/high-SNR input is an open tune.
  Feeds ADR-007 D7's GTCRN-vs-Wiener choice (android plan Risk R1).
```

(f) **§9 open questions** — replace the two bullets beginning
`- **Pre-ASR denoising gate** —` and `- **Architecture (ASR/MT/TTS frameworks)** —` with:

```markdown
- **Pre-ASR denoising gate — gate decision made (Wiener ADOPTED); full lean-slice
  eval still pending** — see `denoising-gate-results.md`; the on-device
  GTCRN-vs-Wiener pick (ADR-007 D7) remains → android plan R1.
- **Architecture — decided in ADR-007/008/009/010** (Dual Zipformer ASR, Opus-MT
  MT, Supertonic Phase-1 TTS, sherpa-onnx + ORT, coroutines pipeline). **ADR-004
  remains Draft** pending the Phase-4/5/7 gates.
```

#### D3 — `docs/android-implementation-plan.md`

(a) **§2 "Already available on disk"** — after the Opus-MT bullet, append:

```markdown
- **Correction (2026-08-05):** `opus_mt_vi_en_encoder.bin` is a **tar of raw
  `.raw` weights** (converter intermediate), **not** the on-device HTP v73
  context binary — that binary does **not** exist yet and is the M3
  deliverable (`qnn-context-binary-generator`, Windows host, `phase-4-qnn-plan`
  §8). All `models/qnn/*` artifacts are **gitignored & uncommitted**
  (`.gitignore` `models/qnn/*`) — provenance is unverifiable locally.
```

(b) **M0 step 3** — after the "Keep:" line of the roster-trim list, append:

```markdown
      - ADR-007 D8 also lists `libQnnGpu.so` (future-proofing; v1 fallback chain
        is NPU→CPU only) — keep it to stay ADR-faithful.
```

(c) **M0 step 4** — after the "Model procurement script" sub-bullets, append a new numbered step:

```markdown
   5. **Provenance & commit rule (ADR-011)**
      - All on-device artifacts (HTP v73 context binary, model `.so`, Opus-MT
        decoder ONNX, Zipformer/Supertonic assets) are committed **inside
        `kavi-android` `app/src/main/assets/`** with a SHA-256 manifest.
        `prototype/models/qnn/*` is gitignored — host outputs are regenerable
        only and must never be treated as deliverables.
```

(d) **M3 step 4** — replace the version-lock bullet (the one beginning `- Verify`opus_mt_vi_en_encoder.bin``) with:

```markdown
      - Verify the **HTP v73 context binary** (not the weight-tar) was produced
        with QAIRT 2.31.0.250130 for HTP v73 — mismatch = silent inference
        failure. Re-convert via `bench/qnn/convert_to_qnn.sh` if needed.
```

(e) **§6 Related documents** — update paths:

- `docs/phase-4-qnn-plan.md` → `docs/reference/phase-4-qnn-plan.md`
- `docs/denoising-gate-results.md` → `docs/reference/denoising-gate-results.md`

#### D4 — superseded QNN adapters (bench/ — comments/docstrings only, no logic change)

- `bench/candidates/qnn_whisper_asr.py`: first docstring line becomes
  `"""QNN Whisper ASR adapter — stub for on-device inference. **SUPERSEDED**\n(ADR-008): ASR is CPU-only Dual Zipformer via sherpa-onnx; the Whisper QNN path\nis retained for the record only.`
- `bench/candidates/qnn_piper_tts.py`: first docstring line becomes
  `"""Piper TTS adapter — CPU-only stub for on-device inference. **SUPERSEDED**\n(ADR-009): v1 TTS is Supertonic Phase 1 via sherpa-onnx`OfflineTts`; Piper VITS\nis demoted to fallback. Retained for the record.`
- `bench/registry.py`: add a comment above the two imports:
  `# qnn_whisper_asr / qnn_piper_tts: superseded by ADR-008/009 — kept registered\n# as no-op stubs for the record; only QnnOpusMTMTCandidate is on the v1 path.`

### Step 4 — link sweep (mandatory)

Run `git grep -n "benchmarking-plan\|benchmarking-todo\|phase-4-qnn-plan\|denoising-gate-results\|contest-info\|additional-reading" -- '*.md'` and fix every hit that points at a moved file, so it points at `docs/reference/...`. Known hits (verified 2026-08-05):

| File | Line(s) | Fix |
| --- | --- | --- |
| `docs/onboarding.md` | 19, 42 | `contest-info.md` → `reference/contest-info.md` (or drop from tree; parent repo is canonical) |
| `docs/onboarding.md` | 26, 27, 67, 69, 198, 207, 217, 227, 248, 249 | `benchmarking-plan.md` / `benchmarking-todo.md` → `reference/...` |
| `docs/onboarding-quiz.md` | 26, 45, 54, 59, 64, 69 | `benchmarking-plan` → `reference/benchmarking-plan`; Q10/Q11 refreshed in Step 6 |
| `docs/specifications.md` | 4 | `contest-info.md` → `reference/contest-info.md` (parent repo canonical) |
| `docs/rtranslator-test-protocol.md` | 9, 235, 236 | → `reference/...` |
| `docs/decisions/license-situation.md` | 192 | `benchmarking-plan.md` → `reference/benchmarking-plan.md` |
| `docs/android-implementation-plan.md` | 44, 226, 227 | already covered by D3(e) |

### Step 5 — rewrite `docs/README.md`

Replace the entire file with:

```markdown
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

- `decisions/` — Architecture Decision Records (ADR-001 … ADR-010) +
  `license-situation.md`. Immutable by convention; status changes are recorded
  in the ADR header.

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
```

### Step 6 — refresh `docs/onboarding.md` + `docs/onboarding-quiz.md`

(a) **onboarding.md tree block (lines ~17–30):** replace the `docs/` listing of
kavi-prototype so it reads:

```markdown
   ├─ onboarding.md           ⑥  this file — architecture, decoded
   ├─ android-implementation-plan.md  ⑪  the active plan (ADR-007 → ADR-010)
   ├─ reference/              ⑫  superseded / deprecated docs (benchmarking-plan, phase-4-qnn-plan, …)
   └─ decisions/
      ├─ ADR-001 …            ⑦  100% offline, forever
      ├─ ADR-002 …            ⑧  one phone: Snapdragon 8 Gen 2
```

(b) **onboarding.md repo-layout table (line ~198):** replace the
`docs/benchmarking-plan.md` row with:

```markdown
| `docs/android-implementation-plan.md` | The active implementation plan (ADR-007 → ADR-010). **Read this next.** |
| `docs/reference/` | Superseded / deprecated docs (benchmarking-plan, phase-4-qnn-plan, …). |
```

(c) **onboarding.md licensing section:** replace the "Live license decision — Piper" bullet with:

```markdown
- **TTS — resolved for v1 (ADR-009):** Supertonic Phase 1 → VieNeu-TTS Phase 2,
  via sherpa-onnx; Piper VITS is fallback only. The old MIT/GPL fork question
  matters only if the fallback is exercised (pin the MIT-era `rhasspy/piper`
  snapshot then). See `docs/reference/benchmarking-plan.md` §4.5 for the landscape.
```

(d) **onboarding.md "Where the architecture is going (ADR-004)" section:** replace its
prose with:

```markdown
## Where the architecture is going (ADR-004)

The **tech stack is decided**: ADR-007 (production architecture), ADR-008 (Dual
Zipformer ASR, CPU-only), ADR-009 (Supertonic Phase-1 TTS), ADR-010 (`ALL_OPT`).
**ADR-004 remains Draft** — it closes only after the Phase-4/5/7 on-device
numbers and hard gates pass (see `.pi/PLAN.md` §8).
```

(e) **onboarding-quiz.md Q10** — replace with:

```markdown
**Q10 — Short answer (denoising gate).** *Source: `reference/denoising-gate-results.md`.*
The Phase-6 denoising gate ran a smoke test (2 utterances × 5 conditions) on
faster-whisper Small int8. What was **ADOPTED** and at what weighted-average WER,
and what caveat does the results file flag before ADR-004 finalization?
```

(f) **onboarding-quiz.md Q11** — replace with:

```markdown
**Q11 — Scenario (TTS voice licensing).** *Source: `license-situation.md`, ADR-009.*
A member picks the Piper **`vivos`** Vietnamese voice because it is a real VI
voice and easy to find. What is wrong, and what is the **v1 TTS plan** that
supersedes the Piper voice question?
```

### Step 7 — new ADR-011

Create `docs/decisions/ADR-011-android-asset-provenance-delivery.md` with exactly:

```markdown
# ADR-011: Android Model Asset Provenance & Delivery

**Status:** Accepted
**Date:** 2026-08-05
**Deciders:** Kavi team
**Relates to:** ADR-002 (target platform), ADR-006 (Android runner), ADR-007
Decision 8 (QNN bundling), ADR-008 (ASR assets), ADR-009 (TTS assets),
`prototype/.gitignore` (`models/qnn/*`)

## Context

The on-device app (`android/` = `kavi-android` submodule) needs a fixed set of
inference artifacts: sherpa-onnx Zipformer models (ADR-008), Supertonic TTS
bundle (ADR-009), the Opus-MT ONNX decoder (CPU), and — once built — the
Opus-MT encoder HTP v73 context binary (ADR-007 D4/D8).

Host-side conversion outputs under `prototype/models/qnn/*` are **gitignored and
regenerable** (`.gitignore` line 20, commit 3502156) and can only be reproduced
with the QAIRT SDK (2.31.0.250130, not installed on every host). Treating them
as deliverables breaks fresh clones. The on-device HTP v73 context binary does
**not exist yet** — it is a Windows-host `qnn-context-binary-generator` output
(`reference/phase-4-qnn-plan.md` §8). The contest grading requires a buildable,
fully offline APK with no runtime network.

## Decision

1. **Commit every on-device inference artifact inside `kavi-android`**
   (`app/src/main/assets/` for models/context binaries; `jniLibs/` for `.so`),
   alongside a `SHA256SUMS` manifest committed in the same repo.
2. **Never vendor from `prototype/models/qnn/*`** — host outputs are
   regenerable intermediates, not deliverables.
3. **Record provenance per artifact**: QAIRT version (must be 2.31.0.250130 /
   HTP v73), converter invocation, source ONNX hash — in `kavi-android`'s model
   README (mirroring `models/qnn/README.md`).
4. **`android/scripts/fetch-models.sh`** downloads external models (Zipformer,
   Supertonic, sherpa-onnx libs), verifies SHA-256, and places them under
   assets with the manifest entry — preserving the offline invariant (no
   runtime network).
5. Re-conversion (SDK/model change) updates the manifest + provenance record,
   never patches binaries in place.

## Consequences

- **Positive:** always-buildable APKs on any host; reproducible contest
  submission; QAIRT version lock enforced mechanically; offline invariant
  preserved.
- **Negative:** `kavi-android` grows large (models committed); re-conversion
  workflow required on SDK/model change; manifest drift possible if artifacts
  are hand-placed — the fetch script is the only supported path.

## References

- ADR-007 Decision 8 (QNN jniLibs roster + version lock)
- ADR-008 (Dual Zipformer assets), ADR-009 (Supertonic bundle)
- `reference/phase-4-qnn-plan.md` §8 (verified converter commands)
- `prototype/.gitignore` (`models/qnn/*`, commit 3502156)
```

### Step 8 — CHANGELOG + commit

1. Append to `CHANGELOG.md` under **Unreleased**:

```markdown
- docs: reconcile plans with ADR-007–010; archive superseded docs to `docs/reference/`
```

1. Stage **only** the intended files (never `git add -A` / `git add .`, never
   `git add android`): the moved docs, edits, new files (`docs/reference/README.md`,
   `ADR-011-...md`, `REORG-PLAN.md`), and the CHANGELOG.
2. Commit: `docs: reconcile plans with ADR-007-010; archive superseded docs to reference/`
3. Do **not** push. Do **not** open a PR.

---

## 4. Verification / Definition of Done

1. `git status --short` — clean except `M android` (submodule, untouched).
2. `git grep -n "docs/benchmarking-plan\|docs/benchmarking-todo\|docs/phase-4-qnn-plan\|docs/denoising-gate-results\|docs/contest-info\|docs/additional-reading" -- '*.md'` — zero hits (all point to `docs/reference/`).
3. All ADR files under `docs/decisions/` byte-identical to `main` except
   `ADR-007-...md` (one appended status note) and the new `ADR-011-...md`.
4. `git diff main --stat` shows only docs/ + the two bench adapter docstrings + registry comment.
5. No `android/` content change staged or committed.
6. One commit on `chore/docs-reorg` with the exact message above.

## 5. Escalation rules

- If any Step's source text cannot be matched exactly, **stop that step and
  report** the mismatch — do not improvise replacements.
- If a link-sweep hit is ambiguous (unclear whether the reference is intentional),
  **report it and keep the current path** unless the target file demonstrably moved.
- If any ADR other than ADR-007/ADR-011 must change, **stop and report**.
- Do not touch `bench/` logic, `models/`, `scripts/`, `.pi/`, or `android/`.

## 6. Report format

Return a structured report with exactly these sections:

- `steps-completed`: list of Step numbers (0–8) with OK/FAIL
- `changed-files`: list of created/modified/moved paths
- `commands-run`: the key commands (moves, grep sweeps, git status/diff)
- `commit-hash`: the final commit SHA (or "none" if blocked)
- `residual-risks`: anything left open (e.g., link-sweep hits left as-is with rationale)
- `blockers`: exact mismatch/ambiguity messages, if any
