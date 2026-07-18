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

### Documentation

- Refresh stale layout/index docs to match current repo

### Features

- Scaffold host-side v0 benchmark harness (Phases 0-3)
- Build lean eval set + SNR recipe in data_prep (Phase 1)

### Miscellaneous

- Update CHANGELOG
- Update CHANGELOG
- Update CHANGELOG
- Update CHANGELOG
- Update CHANGELOG
- Update CHANGELOG
- Update CHANGELOG

### Refactoring

- **bench:** Make manifest candidate-agnostic + cheap FLEURS reads
- **bench:** Cache candidate instances per cid in run_manifest

### Ci

- Guard changelog footer for repos without tags([#20](https://github.com/TanKhoiTV/kavi-prototype/pull/20))
- Declare latest Node.js LTS in workflows([#21](https://github.com/TanKhoiTV/kavi-prototype/pull/21))
- Bump actions to Node 24 runtime (checkout/setup-node @v7)([#22](https://github.com/TanKhoiTV/kavi-prototype/pull/22))
- Use commit.remote instead of deprecated commit.github([#23](https://github.com/TanKhoiTV/kavi-prototype/pull/23))
- Bump astral-sh/setup-uv to v8 (Node 24 runtime)([#24](https://github.com/TanKhoiTV/kavi-prototype/pull/24))
- Pin astral-sh/setup-uv to v8.3.2 (resolvable tag)([#25](https://github.com/TanKhoiTV/kavi-prototype/pull/25))
- Pin GitHub Action tags to full commit SHAs([#27](https://github.com/TanKhoiTV/kavi-prototype/pull/27))
[unreleased]: https://github.com/TanKhoiTV/kavi-prototype/compare/v0.1.0...HEAD

