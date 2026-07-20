# PLAN.md — Kavi Benchmark Harness: Phases 4–7

> **Last updated:** 2026-07-20
> **Cross-references:** `docs/benchmarking-todo.md` (§7 phased TODO),
> `docs/phase-4-qnn-plan.md` (executable QNN spec), `docs/benchmarking-plan.md`
> (datasets + candidates), `.pi/HANDOFF.md` (session continuity),
> `bench/` source tree.

---

## 0. Current state (verified 2026-07-20)

| Phase | Status | Evidence |
|-------|--------|----------|
| 0–3 (host harness) | ✅ **Complete** | `bench/` package running; CPU baseline numbers (MT BLEU ~76, TTS RTF 0.06–0.22) |
| 4 (QNN on-device) | 🟡 **Partial** — scripts written, Android scaffold exists, no conversion or runner | See §1 below |
| 5 (RTranslator) | 🟡 **Partial** — APK downloaded, scoring scripts exist, no on-device run | See §2 below |
| 6 (Denoising gate) | ✅ **Complete** | ADOPT Wiener (49.82% vs 51.23% raw WER) — `docs/denoising-gate-results.md` |
| 7 (COMET + MOS) | ❌ **Not started** | See §3 below |

### Key facts

- **eval_manifest_v1.json**: 594 items (540 ASR, 42 MT, 12 TTS)
- **Android scaffold**: 39 `libQnn*.so` bundled in `jniLibs/arm64-v8a/`, empty `assets/`
- **APK**: `eval_data/rtranslator/RTranslator_2.1.5.apk` (SHA-256 verified)
- **FLEURS parquets**: Available in `eval_data/raw/` (vi_vn + en_us test splits)
- **Registry**: 4 candidates registered (WhisperASR, OpusMT, Piper, RTranslator)
- **Deps gap**: `optimum`, `datasets`, `onnx-graphsurgeon` NOT in `pyproject.toml`

---

## 1. Phase 4 — QNN On-Device Runner

### 1.1 What exists

| Component | Path | Status |
|-----------|------|--------|
| QNN conversion plan | `docs/phase-4-qnn-plan.md` (283 lines) | ✅ Complete executable spec |
| Opus-MT ONNX export | `bench/qnn/export_opusmt_onnx.py` (360 lines) | ✅ Written, needs `optimum` dep |
| QAIRT conversion wrapper | `bench/qnn/convert_to_qnn.sh` (313 lines) | ✅ Written, needs QAIRT SDK |
| Setup docs | `models/qnn/README.md` | ✅ Complete |
| Android app scaffold | `android/app/` (build.gradle.kts, MainActivity.kt) | ✅ Buildable skeleton |
| QNN runtime .so | `android/app/src/main/jniLibs/arm64-v8a/` (39 files) | ✅ Bundled |
| Model assets | `android/app/src/main/assets/` | ❌ Empty |
| `qairt-env.sh` | `scripts/qairt-env.sh` | ❌ Not created |
| Whisper ONNX export | — | ❌ Not started |
| Piper ONNX surgery | — | ❌ Not started |
| Calibration input lists | — | ❌ Not started |
| Android instrumented test | `android/app/src/androidTest/` | ❌ Not started |
| QNN candidate adapters | `bench/candidates/qnn_*.py` | ❌ Not started |
| QNN registry entries | `bench/registry.py` | ❌ Not started |

### 1.2 What blocks Phase 4

| Blocker | Severity | Mitigation |
|---------|----------|------------|
| **QAIRT SDK 2.31.0.250130 not installed** | **Hard** — blocks all conversion | Download from Qualcomm (requires account); SDK version MUST match device `qnn-2.31` / HTP v73 |
| **`optimum` not in pyproject.toml** | Soft — blocks ONNX export scripts | `uv pip install transformers optimum[onnx] datasets` |
| **`onnx-graphsurgeon` not in pyproject.toml** | Soft — blocks Piper surgery | `uv pip install onnx-graphsurgeon` |
| **Whisper ONNX export not written** | Medium — no Whisper→QNN path | Write `bench/qnn/export_whisper_onnx.py` (analogous to Opus-MT script) |
| **Piper `RandomNormalLike` surgery not implemented** | Medium — no TTS→QNN path | Write `bench/qnn/patch_piper_onnx.py` per plan §3.3/§10 |
| **Windows build host for context binaries** | Hard — `qnn-context-binary-generator` needs Windows or WSL | Plan §1 documents hybrid WSL/Linux + Windows workflow |
| **No instrumented test code** | Hard — no on-device runner | Write `android/app/src/androidTest/` per plan §5 |

### 1.3 Task breakdown (ordered by dependency)

#### 1.3.1 Environment setup (prerequisite for everything)

| Task | Owner | Effort | Files |
|------|-------|--------|-------|
| Install QAIRT SDK 2.31.0.250130 on Ubuntu 22.04 host | Manual | 30 min | External |
| Create `scripts/qairt-env.sh` per `models/qnn/README.md` spec | Worker | 15 min | `scripts/qairt-env.sh` |
| Add `optimum[onnx]`, `datasets`, `onnx-graphsurgeon` to pyproject.toml | Worker | 10 min | `pyproject.toml` |
| Verify `qnn-onnx-converter --help` runs in converter venv | Manual | 5 min | — |

#### 1.3.2 Model export scripts (lowest risk first)

| Task | Owner | Effort | Files | Blocked by |
|------|-------|--------|-------|------------|
| Write Whisper Small ONNX export script | Worker | 2 hrs | `bench/qnn/export_whisper_onnx.py` | `optimum` dep |
| Export Opus-MT vi→en ONNX | Worker | 1 hr | `models/qnn/opus-mt-vi-en/` | `optimum` dep, QAIRT SDK |
| Export Whisper Small ONNX | Worker | 1 hr | `models/qnn/whisper-small/` | Whisper export script |
| Generate calibration input lists from FLEURS | Worker | 2 hrs | `models/qnn/*_input_list.txt` | FLEURS parquets (available) |
| Write Piper ONNX surgery script | Worker | 3 hrs | `bench/qnn/patch_piper_onnx.py` | `onnx-graphsurgeon`, Netron inspection |

#### 1.3.3 QNN conversion (requires QAIRT SDK)

| Task | Owner | Effort | Files | Blocked by |
|------|-------|--------|-------|------------|
| Convert Whisper encoder → `.cpp` | Manual | 1 hr | `models/qnn/whisper-small_encoder.cpp` | QAIRT SDK, ONNX export |
| Convert Opus-MT → `.cpp` | Manual | 1 hr | `models/qnn/opus-mt-vi-en.cpp` | QAIRT SDK, ONNX export |
| Convert Piper → `.cpp` | Manual | 2 hrs | `models/qnn/piper-en.cpp` | QAIRT SDK, ONNX surgery |
| Build model `.so` + HTP v73 context binaries | Manual | 2 hrs | `models/qnn/*_v73.bin` | Windows build host |

#### 1.3.4 Android instrumented runner

| Task | Owner | Effort | Files | Blocked by |
|------|-------|--------|-------|------------|
| Write QNN model loader (Kotlin) | Worker | 4 hrs | `android/app/src/main/java/com/kavi/app/qnn/QnnModelLoader.kt` | QNN context binaries |
| Write manifest reader | Worker | 2 hrs | `android/app/src/main/java/com/kavi/app/runner/ManifestReader.kt` | — |
| Write instrumented test runner | Worker | 6 hrs | `android/app/src/androidTest/java/com/kavi/app/` | QNN loader, manifest reader |
| Write network monitor (zero-call assertion) | Worker | 2 hrs | `android/app/src/main/java/com/kavi/app/runner/NetworkMonitor.kt` | — |
| Wire latency/RTF/RSS logging | Worker | 3 hrs | Runner files | QNN loader |

#### 1.3.5 Host-side QNN scoring

| Task | Owner | Effort | Files | Blocked by |
|------|-------|--------|-------|------------|
| Write QNN ASR candidate adapter | Worker | 2 hrs | `bench/candidates/qnn_whisper_asr.py` | QNN context binaries |
| Write QNN MT candidate adapter | Worker | 2 hrs | `bench/candidates/qnn_opusmt_mt.py` | QNN context binaries |
| Write QNN TTS candidate adapter | Worker | 2 hrs | `bench/candidates/qnn_piper_tts.py` | QNN context binaries |
| Register QNN candidates in registry | Worker | 30 min | `bench/registry.py` | QNN adapters |

### 1.4 Decision gates

| Gate | Threshold | Source |
|------|-----------|--------|
| RTF (per stage + E2E) | **< 1.0** | `benchmarking-todo.md` §2 |
| Turnaround (EOS→SA) | **< 2.0 s** | `benchmarking-todo.md` §2 |
| Zero network calls | **0 calls** | `benchmarking-todo.md` §2 |
| Accuracy regression | WER/BLEU within tolerance vs CPU | ADR-003 §6 |

**Decision rule:** Adopt QNN for a stage **iff** it meets hard gates AND beats CPU baseline on RTF/turnaround WITHOUT accuracy regression. Else CPU fallback.

---

## 2. Phase 5 — RTranslator Baseline Row

### 2.1 What exists

| Component | Path | Status |
|-----------|------|--------|
| Test protocol | `docs/rtranslator-test-protocol.md` (278 lines) | ✅ Complete |
| Scoring adapter | `bench/candidates/rtranslator.py` (168 lines) | ✅ Written |
| CLI scorer | `bench/score_rtranslator.py` (253 lines) | ✅ Written |
| APK | `eval_data/rtranslator/RTranslator_2.1.5.apk` | ✅ Downloaded, SHA-256 verified |
| Output directory | `eval_data/rtranslator/outputs/` | ❌ Empty (no on-device run) |
| Device state metadata | `eval_data/rtranslator/device-state.json` | ❌ Not created |
| On-device test execution | — | ❌ Not started |
| Latency measurement | — | ❌ Not started |

### 2.2 What blocks Phase 5

| Blocker | Severity | Mitigation |
|---------|----------|------------|
| **Physical Meizu 21 Note required** | **Hard** — all protocol steps need `adb` access | No remote workaround; must be done on-device |
| **Semi-manual process** | Medium — ~600 utterances take hours | Start with 10-utterance subset for v0 |
| **ML Kit offline behavior unverified** | Medium — may download model on first WalkieTalkie use | Pre-warm with network ON, then go offline |
| **System TTS voice packs** | Medium — fresh device may lazy-download | Pre-warm EN + VI voice packs before testing |
| **RTranslator 3.0 imminent** | Low — version snapshot needed | Lock to v2.1.5, document commit + date |

### 2.3 Task breakdown

| Task | Owner | Effort | Files | Blocked by |
|------|-------|--------|-------|------------|
| Create `eval_data/rtranslator/outputs/` directory structure | Worker | 10 min | `eval_data/rtranslator/outputs/{vi-en,en-vi}/` | — |
| Create sample `device-state.json` template | Worker | 15 min | `eval_data/rtranslator/device-state-template.json` | — |
| Run RTranslator on device (10-utterance subset) | Manual | 1 hr | `eval_data/rtranslator/outputs/` | Physical device |
| Run full lean eval set on device | Manual | 4–6 hrs | `eval_data/rtranslator/outputs/` | Physical device, subset run |
| Score RTranslator outputs | Worker | 30 min | `bench-results/rtranslator/` | On-device run complete |
| Document latency/RAM as author-reported | Worker | 30 min | `docs/rtranslator-results.md` | On-device run complete |
| Compare RTranslator vs Kavi CPU baseline | Worker | 1 hr | `docs/rtranslator-comparison.md` | Both scored |

### 2.4 Decision gates

Same as Phase 4 — RTranslator is the **anchor** Kavi must not be worse than:

| Target | Value | Source |
|--------|-------|--------|
| Whisper-Small latency | **0.9 GB / 1.6 s** per 11 s audio | Author-reported (§5) |
| NLLB-600M latency | **1.3 GB / 2 s** per 75 tok | Author-reported (§5) |
| Kavi must publish | **First defensible mic→speaker turnaround** | Opportunity |

---

## 3. Phase 7 — COMET + MOS (v1 Quality Depth)

### 3.1 What exists

| Component | Path | Status |
|-----------|------|--------|
| Scorer | `bench/scorer.py` | ✅ WER/BLEU/RTF implemented; COMET deferred |
| Eval manifest | `eval_data/eval_manifest_v1.json` | ✅ 594 items |

### 3.2 Task breakdown

| Task | Owner | Effort | Files | Blocked by |
|------|-------|--------|-------|------------|
| Add COMET scoring (both directions) | Worker | 4 hrs | `bench/scorer.py` | `comet` dep install |
| Add DNSMOS proxy scoring | Worker | 3 hrs | `bench/scorer.py` | DNSMOS model download |
| Run COMET on clean + cascaded ASR output | Worker | 2 hrs | `bench-results/comet/` | COMET implemented |
| Design human MOS panel protocol | Worker | 2 hrs | `docs/mos-protocol.md` | — |
| Execute human MOS panel (5–10 raters) | Manual | 1–2 weeks | `bench-results/mos/` | Panel recruitment |
| Run ≥3 averaged configs | Worker | 1 hr | `bench-results/final/` | All candidates scored |
| Run stability test (N=10 consecutive) | Worker | 2 hrs | `bench-results/stability/` | Final config chosen |

### 3.3 Dependencies

- `comet` package (`Unbabel/wmt22-comet-da`) — NOT in `pyproject.toml`
- DNSMOS model — needs download
- Human panel — needs 5–10 raters, 20–30 clips

---

## 4. Cross-cutting concerns

### 4.1 Dependency gaps (pyproject.toml)

| Dependency | Required By | In pyproject.toml? |
|------------|-------------|-------------------|
| `faster-whisper` | Phase 2 (CPU ASR) | ✅ Yes |
| `ctranslate2` | Phase 2 (CPU MT) | ✅ Yes |
| `transformers` | Phase 4 (ONNX export) | ✅ Yes |
| `optimum[onnx]` | Phase 4 (ONNX export) | ❌ **Missing** |
| `datasets` | Phase 4 (FLEURS calibration) | ❌ **Missing** |
| `onnx-graphsurgeon` | Phase 4 (Piper surgery) | ❌ **Missing** |
| `sentencepiece` | Phase 4 (Opus-MT tokenizers) | ✅ Yes (`>=0.2.1`) |
| `comet` | Phase 7 (COMET scoring) | ❌ **Missing** |
| `noisereduce` | Phase 6 (denoising) | ✅ Yes (`>=3.0`) |
| `jiwer` | Phase 2 (WER/CER) | ✅ Yes (`>=4.0.0`) |
| `sacrebleu` | Phase 2 (BLEU) | ✅ Yes (`>=2.6.0`) |

### 4.2 Open gates / blockers

| Blocker | Status | Unblocks |
|---------|--------|----------|
| Qualcomm QAIRT runtime EULA | **RESOLVED — ADOPT (clean)** | Phase 4 |
| Piper engine GPL split | Deferred — MIT-era + subprocess default | TTS finalization |
| InfoRe donation terms | **RESOLVED — AVOID** | VI voice dropped |
| VI→EN ST corpus | **RESOLVED** — FLEURS + gold set | EN→VI eval |
| RTranslator 3.0 imminent | Snapshot version when tested | Fair comparison |

### 4.3 Sequencing dependencies

```
Phase 0–3 (host harness) ──────┬────→ Phase 4 (QNN conversion + on-device runner)
                                │
                                └────→ Phase 5 (RTranslator baseline) ────┐
                                                                          ▼
                                          ADR-004 finalization ← Phase 7 (COMET/MOS)
```

- **Phase 4 and 5 can run in parallel** (different workstreams)
- **Phase 7 depends on** Phase 4 (QNN numbers) + Phase 5 (RTranslator row)
- **ADR-004 cannot close** until Phase 4 + 5 + 7 are complete

---

## 5. File map (key paths)

```
prototype/
├── bench/
│   ├── adapters.py              # Candidate ABC + StageResult
│   ├── registry.py              # REGISTRY + build_candidate()
│   ├── schema.py                # EvalItem, StageResult, RunManifest
│   ├── data_prep.py             # build_lean_manifest, FLEURS download, noise mix
│   ├── run.py                   # Host runner: manifest → fan-out → score → table
│   ├── scorer.py                # jiwer WER/CER, sacrebleu BLEU, RTF
│   ├── eval_denoising.py        # Phase 6 denoising gate eval
│   ├── score_rtranslator.py     # Phase 5 RTranslator scorer
│   ├── candidates/
│   │   ├── whisper_asr.py       # faster-whisper Small int8 (CPU)
│   │   ├── opusmt_mt.py         # CTranslate2 Opus-MT vi→en int8 (CPU)
│   │   ├── piper_tts.py         # Piper EN lessac-medium (CPU)
│   │   └── rtranslator.py       # RTranslator scoring adapter
│   └── qnn/
│       ├── __init__.py
│       ├── export_opusmt_onnx.py  # Opus-MT ONNX export
│       └── convert_to_qnn.sh      # QAIRT conversion wrapper
├── android/
│   ├── app/
│   │   ├── build.gradle.kts     # compileSdk=36, NDK r26c, testInstrumentationRunner
│   │   └── src/main/
│   │       ├── AndroidManifest.xml  # Offline-only, no network permissions
│   │       ├── java/com/kavi/app/MainActivity.kt  # Scaffold placeholder
│   │       ├── jniLibs/arm64-v8a/   # 39 libQnn*.so (HTP v73 runtime)
│   │       └── assets/              # Empty (QNN model artifacts go here)
│   ├── CONTRIBUTING.md
│   └── README.md
├── docs/
│   ├── benchmarking-todo.md     # §7 phased TODO (source of truth)
│   ├── benchmarking-plan.md     # Datasets, candidates, harness design
│   ├── phase-4-qnn-plan.md      # Executable QNN spec (283 lines)
│   ├── rtranslator-test-protocol.md  # Phase 5 test protocol
│   ├── denoising-gate-results.md     # Phase 6 results
│   ├── onboarding.md
│   └── decisions/
│       ├── ADR-003-hexagon-runtime.md
│       └── ADR-004-architecture.md
├── models/
│   ├── opus-mt-vi-en-ct2/       # CT2 int8 weights (vi→en)
│   ├── opus-mt-vi-en-src/       # SentencePiece tokenizers
│   └── qnn/                     # README + (future) ONNX/converted artifacts
├── eval_data/
│   ├── eval_manifest_v1.json    # 594 items
│   ├── raw/                     # FLEURS parquets
│   ├── mixed/                   # Audio files (clean + SNR-swept)
│   └── rtranslator/
│       ├── RTranslator_2.1.5.apk
│       └── outputs/             # (empty — awaiting on-device run)
└── voices/
    ├── en_US-lessac-medium.onnx
    └── en_US-lessac-medium.onnx.json
```

---

## 6. Validation commands

```bash
# Lint
make check                     # ruff check + format

# Tests
make test                      # pytest tests/test_bench.py

# CPU baseline
uv run python -m bench.run --smoke --out bench-results

# Denoising gate
uv run python -m bench.eval_denoising --manifest eval_data/eval_manifest_v1.json --out bench-results/denoising

# RTranslator scoring (after on-device run)
uv run python -m bench.score_rtranslator --manifest eval_data/eval_manifest_v1.json --outputs eval_data/rtranslator/outputs/2026-07-20 --out bench-results/rtranslator

# ONNX export (requires optimum)
uv run python -m bench.qnn.export_opusmt_onnx --model Helsinki-NLP/opus-mt-vi-en --output models/qnn/opus-mt-vi-en/
```

---

## 7. Next actions (immediate)

1. **Add missing deps**: `uv pip install optimum[onnx] datasets onnx-graphsurgeon` + update pyproject.toml
2. **Create `scripts/qairt-env.sh`** per README spec
3. **Write Whisper ONNX export script** (`bench/qnn/export_whisper_onnx.py`)
4. **Create sample RTranslator output directory** for scorer unit testing
5. **Run RTranslator on device** (10-utterance subset first, then full)

---

## 8. Acceptance criteria for ADR-004 closure

ADR-004 (architecture / tech-stack) can close when:

- [ ] Phase 4 on-device numbers exist (RTF, turnaround, WER/BLEU for QNN vs CPU)
- [ ] Phase 5 RTranslator row exists (quality + latency/RAM, author-reported flagged)
- [ ] Phase 7 COMET scores exist (both directions, clean + cascaded)
- [ ] Per-stage decision made: QNN or CPU for ASR/MT/TTS
- [ ] All hard gates met (RTF < 1.0, turnaround < 2.0 s, zero network calls)
- [ ] Kavi is not worse than RTranslator on quality metrics
