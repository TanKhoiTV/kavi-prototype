# Registration Checklist — OneVoice AI Challenge

> **Deadline:** June 24, 2026 (Luma)  
> **Buffer target:** June 22  
> **Last updated:** 2026-06-20

---

## 🔴 Must-Have

| # | Item | Est. time | Owner | Status |
| --- | ------ | ----------- | ------- | :------: |
| 1 | Decide: Individual or Team? | ✅ Done | → | ✅ Team of 2 |
| 2 | Pick a project name | 30 min | Team | ☐ |
| 3 | Fill Google Sheets template | 1 hr | Lead | ☐ |
| 4 | Draft Luma form long answers | 3 hrs | Lead | ☐ |
| 5 | Create a pitch deck (PDF) | 4–6 hrs | → | ◐ Draft done, needs final review |
| 6 | Set up GitHub repo with scaffold | 2 hrs | → | ◐ Local repo + submodule, no remote |
| 7 | Fill Luma form + submit | 1 hr | Lead | ☐ |

### Details

**1. Applicant type** ✅

- Team of 2 — user (lead) + 1 teammate
- Google Sheets template: Part 3+4 (Team info + Member table)

**2. Project name** ❌

- Still undecided, needs team discussion

**3. Google Sheets template**

- Link: <https://docs.google.com/spreadsheets/d/1L4lc7vOiovBdRgDQ3Xmw3hADomxThHa1zE_Lfi8TlvQ>
- Fill in: Applicant Type → Personal/Team Info → Team Member Table
- Set sharing to "Anyone with the link can view"

**4. Luma form long-answer fields**

| Field | Source | Status |
| ------- | -------- | -------- |
| Project name | Needs decision | ☐ Pending |
| Describe your solution | Architecture §4.1 + §3.2 | ☐ Draft needed |
| What makes it innovative? | §6 Innovation Anchors | ☐ Draft needed |
| Technical approach | §4 Architecture + §5 Components | ☐ Draft needed |
| Language pair | VI↔EN | ✅ Known |
| Current phase | — | ✅ **Working prototype** |
| Use case / industry | §3.2 + §1 | ☐ Draft needed |
| Expected impact | §1 (5%/87%) | ☐ Draft needed |
| Product evolution | §3.4 Business Viability | ☐ Draft needed |

**5. Pitch deck** ◐

- `docs/pitch-deck/registration-pitch.pptx` exists (49KB, python-pptx)
- Slide 4 MT model abstracted per ADR-001
- Needs: final review, style decision (technical vs investor), PDF export

**6. GitHub repo** ◐

- Local repo initialized (commit 78ae923, 11 files)
- Prototype submodule via sibling bare repo
- No remote — user chose to proceed without one

---

## 🟡 Should-Have

| # | Item | Est. time | Status |
| --- | ------ | ----------- | :------: |
| 8 | Run DeepFilterNet WER experiment | ~2 days | ☐ |
| 9 | Pipeline scaffolding | 3–4 hrs | ✅ Done |
| 10 | ASR→MT→TTS chain on laptop | 1–2 days | ✅ Done |
| 11 | Persistent model server | 1 day | ✅ Done (8× speedup) |
| 12 | Evaluation harness (WER/chrF) | 1 day | ✅ Done |
| 13 | Local CI pipeline | 1 day | ✅ Done |
| 14 | Design document | 1 day | ✅ Done |
| 15 | Git submodule setup | 1 day | ✅ Done |

### Baseline Metrics (greeting_vi.wav, ASR small, CPU)

| Metric | Value |
| -------- | ------- |
| ASR WER | 22.2% (7 hits, 2 substitutions) |
| MT chrF | 31.83 |
| Total (cold) | 25.03s |
| Total (server) | 3.22s (8× speedup) |
| VAD speech ratio | 0.5134 |

---

## 🔵 Nice-to-Have

| # | Item | Status |
| --- | ------ | :------: |
| 16 | Record a 60-second prototype demo | ☐ |
| 17 | MOS pre-test for MeloTTS-VI | ☐ |
| 18 | Team page / LinkedIn profiles | ☐ |

---

## 📋 Admin Decisions

| # | Decision | Status |
| --- | ---------- | :------: |
| A | Solo or team? | ✅ Team of 2 |
| B | Project name | ❌ Undecided |
| C | Who submits? | ✅ User (lead) |
| D | Testing device | ✅ SD8G2 phone |
| E | Pitch deck style | ❌ Undecided |
| F | Language pair | ✅ VI↔EN |

---

## ✅ Completed Since Last Check

| When | What | Details |
| ------ | ------ | --------- |
| Jun 20 | ADR-001: Hy-MT1.5 over NLLB | docs/adr/001-prioritize-hy-mt-over-nllb.md |
| Jun 20 | Pitch deck slide 4 fixed | MT description abstracted |
| Jun 20 | Pipeline prototype | ASR (faster-whisper small) → MT (CTranslate2 Opus-MT) → TTS (Piper) |
| Jun 20 | MT layer | CTranslate2 int8, 72MB, 0.22-0.27s CPU |
| Jun 20 | Silero VAD | audio.py with --vad-threshold, ImportError fallback |
| Jun 20 | Eval harness | eval.py — WER (jiwer) + chrF (sacrebleu), JSON output |
| Jun 20 | Design doc | prototype/docs/design.md — full architecture, ADTs, metrics |
| Jun 20 | Git submodule | Parent + submodule via sibling bare repo |
| Jun 20 | Repo docs | CONTRIBUTING.md, AGENTS.md — semver + conventional commits |
| Jun 20 | Model server | server.py — Unix socket, 3.22s vs 25.03s cold |
| Jun 20 | CI pipeline | Makefile — 8 targets (check, lint, typecheck, test, format, clean, sync, help) |
| Jun 20 | Lint fixes | ruff auto-fix on 4 files (unused imports, naming, type hints) |
| Jun 20 | Doc restructure | Design doc moved into submodule, pointer doc at parent |

---

## ADRs

| ADR | Title | File |
|-----|-------|------|
| 001 | Prioritize Hy-MT1.5 over NLLB-600M | docs/adr/001-prioritize-hy-mt-over-nllb.md |

---

## Project Structure

```
aivoice-2026/
├── docs/
│   ├── adr/001-prioritize-hy-mt-over-nllb.md
│   ├── architecture.md
│   ├── contest-info.md
│   ├── pitch-deck/
│   │   ├── registration-deck.py
│   │   └── registration-pitch.pptx
│   ├── prototype.md          (pointer → submodule)
│   └── registration-checklist.md
├── CONTRIBUTING.md
├── Makefile                   (local CI)
└── prototype/                 (submodule — code)
    ├── pipeline.py            (ASR→MT→TTS orchestrator)
    ├── server.py              (persistent model server)
    ├── audio.py               (Silero VAD)
    ├── eval.py                (evaluation harness)
    ├── docs/design.md         (design document)
    ├── refs/greeting_vi.txt   (ground truth reference)
    └── greeting_vi.wav        (test input)
```

---

## Changelog

| Date | Change |
| ------ | -------- |
| 2026-06-20 | Full rewrite with all progress since Jun 14: pipeline prototype, model server (8×), eval harness, CI pipeline, ADR-001, submodule setup, design doc, lint fixes, doc restructure. Added changelog section. |
| 2026-06-14 | Added admin decisions, risk assessment, sprint plan |
| 2026-06-13 | Initial checklist from Luma form analysis |
