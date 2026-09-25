## [Unreleased]

### Bug Fixes

- Resolve pi-lens false positives via pyrightconfig.json([#26](https://github.com/TanKhoiTV/kavi-prototype/pull/26))
- Resume large FLEURS parquet downloads in download_fleurs
- Build real-speech FLEURS set (decode audio bytes, pair VI->EN)
- Emit EN ASR items and honor per-item language in Whisper
- **bench:** Set ASR reference via reference_text, not transcript_ref
- **bench:** Emit clean ASR condition once instead of per-noise-type
- **bench:** Stop Opus-MT decode loops; scope WER/CER to ASR only
- **bench:** Bound FLEURS audio read to sampled rows (resolve #34)
- **bench:** Select FLEURS audio by id, not position([#28](https://github.com/TanKhoiTV/kavi-prototype/pull/28))
- **bench:** Drop no-op candidate_filter pass in run.py
- Lint cleanup for eval_denoising.py
- **android:** Remove stale .dlc reference in MainActivity.kt
- **android:** Remove stale .dlc reference in MainActivity.kt([#79](https://github.com/TanKhoiTV/kavi-prototype/pull/79))
- **bench:** Guard peak_ram_mb against missing resource module on Windows (#80)([#80](https://github.com/TanKhoiTV/kavi-prototype/pull/80))
- **qnn:** Use repo-root-relative paths in calibration input lists (#85)([#85](https://github.com/TanKhoiTV/kavi-prototype/pull/85))

### Documentation

- Refresh stale layout/index docs to match current repo
- Verify InfoRe + 25hours_single licenses (stay avoid)([#35](https://github.com/TanKhoiTV/kavi-prototype/pull/35))
- Sync harness docs with the implemented v0 benchmark harness
- **benchmarking-todo:** Add progress & to-do snapshot at top([#43](https://github.com/TanKhoiTV/kavi-prototype/pull/43))
- **license:** Resolve QAIRT runtime gate — ADOPT (clean)([#45](https://github.com/TanKhoiTV/kavi-prototype/pull/45))
- **license:** Record PKLA (signed 2026-07-19) findings([#47](https://github.com/TanKhoiTV/kavi-prototype/pull/47))
- Fix PKLA expansion and clarify PhoST benchmarking vs redistribution([#50](https://github.com/TanKhoiTV/kavi-prototype/pull/50))
- Add Phase-4 QNN conversion & comparison plan (#51)([#53](https://github.com/TanKhoiTV/kavi-prototype/pull/53))
- **adr-003:** Turn determination method into executable plan (#52)([#54](https://github.com/TanKhoiTV/kavi-prototype/pull/54))
- Expand CONTRIBUTING with OS-agnostic dev setup + OS notes (#55)
- **phase-4:** Fold verified QNN command reference + pitfalls (#57)([#58](https://github.com/TanKhoiTV/kavi-prototype/pull/58))
- **phase-4:** Correct .dlc claims and elaborate conversion plan([#61](https://github.com/TanKhoiTV/kavi-prototype/pull/61))
- Point eval_manifest_v1.json references at eval_data/([#65](https://github.com/TanKhoiTV/kavi-prototype/pull/65))
- Pin Python 3.12 and document sync prereqs([#67](https://github.com/TanKhoiTV/kavi-prototype/pull/67))
- Point AGENTS.md reference at .pi/AGENTS.md
- Update agent guidance in .pi/AGENTS.md
- Mirror parent contest-info.md and specifications.md
- Add handoff notes to .pi/HANDOFF.md([#70](https://github.com/TanKhoiTV/kavi-prototype/pull/70))
- Update stale blocker references (QAIRT EULA resolved, FLEURS available)([#72](https://github.com/TanKhoiTV/kavi-prototype/pull/72))
- Add PLAN.md for Phases 4–7 with cross-checked task breakdown
- Update PLAN.md — mark Batch 1 done, add Batch 2 task breakdown
- Fix stale SDK paths, venv names, and .dlc references
- **adr:** Accept ADR-005, update follow-up status table (#82)([#82](https://github.com/TanKhoiTV/kavi-prototype/pull/82))
- Consolidate ADR directory, move ADR-005/006 to docs/decisions/ (#83)([#83](https://github.com/TanKhoiTV/kavi-prototype/pull/83))
- Defer Piper QNN per ADR-005 Decision 3([#84](https://github.com/TanKhoiTV/kavi-prototype/pull/84))
- **adr:** ADR-007 production inference architecture and service layer (#89)([#89](https://github.com/TanKhoiTV/kavi-prototype/pull/89))
- ADR-008 — v1 Android Dual Zipformer ASR decision ([#92](https://github.com/TanKhoiTV/kavi-prototype/pull/92))
- ADR-009 — v1 Android TTS decision (Supertonic Phase 1 → VieNeu-TTS Phase 2) (#93)([#93](https://github.com/TanKhoiTV/kavi-prototype/pull/93))
- Add ADR-010 — ALL_OPT decoder optimisation analysis (#94)([#94](https://github.com/TanKhoiTV/kavi-prototype/pull/94))
- Index NDK conversion runbook in docs/README
- Reconcile plans with ADR-007-010; archive superseded docs to reference/ ([#95](https://github.com/TanKhoiTV/kavi-prototype/pull/95))
- Add ADR-012 — ASR thread tuning strategy (Proposed) (#100)([#100](https://github.com/TanKhoiTV/kavi-prototype/pull/100))
- Plan Kotlin + C++ implementation for the android app (#97)([#97](https://github.com/TanKhoiTV/kavi-prototype/pull/97))
- **repo:** Document that the android app is not vendored here
- Correct kavi-android repo structure after untracking

### Features

- Scaffold host-side v0 benchmark harness (Phases 0-3)
- Build lean eval set + SNR recipe in data_prep (Phase 1)
- **bench:** Support a real noise bank in data_prep([#36](https://github.com/TanKhoiTV/kavi-prototype/pull/36))
- **qnn:** Add Phase 4 QNN conversion pipeline setup
- Add Phase 4 QNN setup, Phase 5 RTranslator prep, Phase 6 denoising gate
- **qnn:** Add Whisper Small ONNX export script with fixed-shape encoder
- **qnn:** Add Piper surgery script, calibration lists, and QNN adapter stubs
- **qnn:** Whisper decoder patch + Opus-MT encoder conversion (#75)([#75](https://github.com/TanKhoiTV/kavi-prototype/pull/75))
- Add .kavi.yaml — single source of truth for pinned config values (#98)([#98](https://github.com/TanKhoiTV/kavi-prototype/pull/98))

### Miscellaneous

- Add kavi-android submodule (prototype/android)
- Pin kavi-android to runtime-bundled commit
- Pin kavi-android to README consistency fix
- Bump kavi-android submodule to CONTRIBUTING (#1)([#56](https://github.com/TanKhoiTV/kavi-prototype/pull/56))
- Skip git-cliff changelog-bot commits([#62](https://github.com/TanKhoiTV/kavi-prototype/pull/62))
- Clarify Makefile targets and drop unused PY var([#63](https://github.com/TanKhoiTV/kavi-prototype/pull/63))
- Move eval_manifest_v1.json into eval_data/([#64](https://github.com/TanKhoiTV/kavi-prototype/pull/64))
- Ignore *cache/ directories
- Exclude caches and dot-dirs from pyright([#66](https://github.com/TanKhoiTV/kavi-prototype/pull/66))
- Declare pyarrow, ctranslate2, and numpy as direct deps
- Normalize dev dependency array to uv canonical single-line form([#68](https://github.com/TanKhoiTV/kavi-prototype/pull/68))
- Move AGENTS.md into .pi/
- Add handoff prompt to .pi/prompts([#69](https://github.com/TanKhoiTV/kavi-prototype/pull/69))
- Untrack .pi agent config directory([#71](https://github.com/TanKhoiTV/kavi-prototype/pull/71))
- Add Phase 4 deps + qairt-env.sh
- Consolidate stray paths, fix SDK path, update .gitignore
- Migrate qairt-converters venv into repo as dependency group
- Update android submodule (stale .dlc refs removed)
- Update android submodule (doc fixes)
- **gitignore:** Ignore generated QNN artifacts, keep README (#81)([#81](https://github.com/TanKhoiTV/kavi-prototype/pull/81))
- **repo:** Ignore the unvendored android path
- **ci:** Drop the submodule opt-out from checkout

### Refactoring

- **bench:** Make manifest candidate-agnostic + cheap FLEURS reads
- **bench:** Cache candidate instances per cid in run_manifest
- **repo:** Untrack the private android submodule

### Testing

- Add bench harness tests + pytest config

### Build

- Bump kavi-android to AGP 8.10.0 / Gradle 8.11.1 (API 36)
- **deps:** Bump actions/checkout from 7.0.0 to 7.0.1 (#87)([#87](https://github.com/TanKhoiTV/kavi-prototype/pull/87))
- **deps:** Bump astral-sh/setup-uv from 8.3.2 to 9.0.0 (#86)([#86](https://github.com/TanKhoiTV/kavi-prototype/pull/86))

### Ci

- Guard changelog footer for repos without tags([#20](https://github.com/TanKhoiTV/kavi-prototype/pull/20))
- Declare latest Node.js LTS in workflows([#21](https://github.com/TanKhoiTV/kavi-prototype/pull/21))
- Bump actions to Node 24 runtime (checkout/setup-node @v7)([#22](https://github.com/TanKhoiTV/kavi-prototype/pull/22))
- Use commit.remote instead of deprecated commit.github([#23](https://github.com/TanKhoiTV/kavi-prototype/pull/23))
- Bump astral-sh/setup-uv to v8 (Node 24 runtime)([#24](https://github.com/TanKhoiTV/kavi-prototype/pull/24))
- Pin astral-sh/setup-uv to v8.3.2 (resolvable tag)([#25](https://github.com/TanKhoiTV/kavi-prototype/pull/25))
- Pin GitHub Action tags to full commit SHAs([#27](https://github.com/TanKhoiTV/kavi-prototype/pull/27))
- Stop recursing into the private kavi-android submodule
[unreleased]: https://github.com/TanKhoiTV/kavi-prototype/compare/v0.1.0...HEAD

