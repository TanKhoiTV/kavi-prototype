# Prototype — ASR→MT→TTS Pipeline

> **Status:** Working baseline (CPU-only, cold models)
> **Last updated:** 2026-06-20

---

## 1. Architecture Overview

Single-file pipeline (`prototype/pipeline.py`) with file-based I/O and a
separate evaluation harness (`prototype/eval.py`). Each stage is a function
with a well-defined return contract (ADT). No shared state between stages —
the pipeline is a pure ordered composition.

> **CWD:** All commands run from `prototype/` unless otherwise noted.

```
audio.wav
   │
   ▼
[1] Resample ───── 16 kHz mono (ffmpeg / scipy)
   │
   ▼
[2] ASR ─────────── faster-whisper (CTranslate2, CPU int8)
   │                default: "small" (244 MB, ~1.5s inference)
   │                outputs: Vietnamese text
   ▼
[3] MT ──────────── Opus-MT vi→en (CTranslate2 int8, 72 MB)
   │                Helsinki-NLP/opus-mt-vi-en
   │                outputs: English text
   ▼
[4] TTS ─────────── Piper-TTS (en_US-lessac-medium)
                    outputs: English speech WAV
   │
   ▼
output.wav
```

**Key constraints:**

- CPU-only (no NVIDIA GPU)
- Offline inference (no internet dependency at runtime)
- Target: Snapdragon 8 Gen 2 Android phone (16 GB RAM)

---

## 2. Pipeline ADTs (Contracts)

### `run_pipeline()` → `PipelineResult`

```python
PipelineResult = {
    "audio_input": str,           # Input WAV path
    "asr": AsrResult,             # absent if no speech detected → {"error": "no speech detected"}
    "mt":  MtResult,              # absent if ASR returned no speech
    "tts": TtsResult,             # absent if ASR returned no speech
    "total_s": float,             # Wall-clock total (cold models)
    "output_wav": str,            # Output WAV path
}
```

**Error path:** If ASR returns empty text, `run_pipeline()` returns
`{"error": "no speech detected"}`. Pipeline consumers must check for
this before accessing per-stage fields.

### `AsrResult`

```python
AsrResult = {
    "text": str,                  # Transcribed Vietnamese text
    "language": str,              # Detected language code
    "duration": float | None,     # Audio duration (seconds)
    "elapsed_s": float,           # Wall-clock inference time
}
```

### `MtResult`

```python
MtResult = {
    "source": str,                # Input Vietnamese text (from ASR)
    "translation": str,           # Translated English text
    "elapsed_s": float,           # Wall-clock inference time
}
```

### `TtsResult`

```python
TtsResult = {
    "output": str,                # Output WAV path
    "elapsed_s": float,           # Wall-clock synthesis time
    "audio_duration_s": float,    # Audio duration (seconds)
}
```

### `run_pipeline()` signature

```python
def run_pipeline(
    audio_path: str,
    asr_model_size: str = "small",   # tiny / base / small / medium / large-v3
    output_dir: str = ".",
    quiet: bool = False,             # Suppress stdout progress
) -> dict:                           # PipelineResult or {"error": str}
```

---

## 3. Stage Details

### 3.1 Resample

Convert arbitrary input audio to 16 kHz mono for Whisper.

- **Tools tried (in order):** ffmpeg → sox → scipy.signal.resample
- **Fallback:** Pure-Python resampling via scipy (no external deps)
- **Output:** Temporary WAV in `output_dir/`

### 3.2 ASR — faster-whisper

| Aspect | Detail |
|--------|--------|
| Engine | `faster-whisper` (CTranslate2 backend) |
| Compute | CPU, int8 quantization |
| Model sizes | `tiny` (39 MB), `base` (74 MB), `small` (244 MB → **default**), `medium` (769 MB), `large-v3` (~3 GB) |
| Language | `vi` (forced, no auto-detect) |

**Model comparison (on `greeting_vi.wav`, inference-only time):**

| Model | WER | Inference | Total (cold) |
|-------|-----|-----------|-------------|
| tiny | 77.8% | 1.18s | 38.6s |
| base | ~78% | 2.86s | 12.1s |
| **small** | **22.2%** | **1.56s** | **24.4s** |
| medium | ~11% | 6.04s | ~214s (cold, incl. download) |

### 3.3 MT — Opus-MT vi→en

| Aspect | Detail |
|--------|--------|
| Model | `Helsinki-NLP/opus-mt-vi-en` |
| Engine | `CTranslate2` (int8 quantized, 578 MB → 72 MB) |
| Tokenizer | SentencePiece (`source.spm` / `target.spm`) |
| Ref model | `Helsinki-NLP/opus-mt-vi-en` (PyTorch, via HuggingFace) |

**Conversion:**

```bash
ct2-transformers-converter \
  --model Helsinki-NLP/opus-mt-vi-en \
  --output_dir models/opus-mt-vi-en-ct2 \
  --quantization int8
```

Tokenizers loaded from separate directory (`models/opus-mt-vi-en-src/`) — CT2's
`shared_vocabulary.json` is not used directly.

### 3.4 TTS — Piper

| Aspect | Detail |
|--------|--------|
| Engine | `piper-tts` v1.4.2 |
| Voice | `en_US-lessac-medium` (auto-download on first use) |
| Output | 16-bit PCM WAV |

Voice model is cached per `output_dir` — each `--output-dir` value creates its
own `voices/` subdirectory with the model files (~500 MB total).

**MeloTTS blocked:** `MeloTTS` PyPI v0.1.1 has a packaging bug (missing
`src/requirements.txt`). git clone from `myshell-ai/MeloTTS` timed out.
Piper is the working fallback. MeloTTS-VI remains the target for production.

---

## 4. Evaluation Harness

**File:** `prototype/eval.py`

### Reference format

```
# refs/<audio_stem>.txt
<Vietnamese ground-truth transcript>
<English ground-truth translation>
```

Example (`refs/greeting_vi.txt`):

```
Xin chào, tôi có thể giúp gì cho bạn?
Hello, how can I help you?
```

### `evaluate_file()` → `EvalResult`

```python
EvalResult = {
    "audio": str,
    "reference": Ref | None,          # Ref = {"vi": str, "en": str}
    "asr_result": AsrResult,
    "mt_result": MtResult,
    "tts_result": TtsResult,
    "total_s": float,
    "metrics": {
        "asr": {
            "wer": float,             # 0.0 – 1.0
            "hits": int,
            "substitutions": int,
            "deletions": int,
            "insertions": int,
        },
        "mt": {
            "chrf": float,            # 0 – 100
            "hypothesis": str,
            "reference": str,
        }
    }
}
```

### Metrics

- **WER** via `jiwer.process_words()` — word-level error rate.
  Formula: `(S + D + I) / N` where N = reference word count.
- **chrF** via `sacrebleu.sentence_chrf()` — character n-gram F-score.

### CLI

```bash
# Single file (CWD = prototype/)
uv run python eval.py greeting_vi.wav

# Batch mode — evaluates all refs/*.txt with matching audio
uv run python eval.py --batch

# Specify a custom reference directory
uv run python eval.py --batch --ref-dir refs/

# Show pipeline progress during evaluation
uv run python eval.py greeting_vi.wav --verbose

# JSON output (for scripting / CI)
uv run python eval.py greeting_vi.wav --json

# Specify ASR model
uv run python eval.py greeting_vi.wav --asr-model small
```

---

## 5. Current Baseline

**Model:** `small` (default)
**Test file:** `greeting_vi.wav` (4s, 48 kHz PCM, clean speech, soft voice)
**Ground truth:** `"Xin chào, tôi có thể giúp gì cho bạn?"`

| Metric | Value | Notes |
|--------|-------|-------|
| ASR WER | **22.2%** | H=7 S=2 D=0 I=0 (2 substitutions: "lý" for "gì", missing "?") |
| MT chrF | **31.83** | Low due to ASR error propagation ("lý" → "reason") |
| ASR inference | **1.56s** | |
| MT inference | **0.10s** | |
| TTS inference | **0.66s** | |
| **Total** | **24.40s** | Cold start, ~21s (86%) = model loading |

### Bottlenecks

1. **Model loading dominates** (~86% of total). Each `run_pipeline()` call
   loads ASR + MT + TTS models from disk. Solution: persistent server (Task 4).
2. **ASR accuracy for soft/low voice** — 22% WER on clean speech is too high
   for contest evaluation. Fine-tuning or VAD preprocessing needed.
3. **No noise handling** — no VAD or denoising stage. Critical for contest
   evaluation data (likely includes noisy / far-field samples).

---

## 6. Setup

### First-time setup

```bash
cd prototype
uv sync                                # Install Python deps
# Set HF_TOKEN for faster HuggingFace downloads:
export HF_TOKEN="hf_..."               # Your HuggingFace read token
```

### MT model conversion (one-time)

```bash
cd prototype
uv run ct2-transformers-converter \
  --model Helsinki-NLP/opus-mt-vi-en \
  --output_dir models/opus-mt-vi-en-ct2 \
  --quantization int8

# Copy tokenizer files from original model
python -c "
from pathlib import Path; import shutil
src = Path.home() / '.cache' / 'huggingface' / 'hub' / \\
      'models--Helsinki-NLP--opus-mt-vi-en' / 'snapshots'
d = list(src.iterdir())[0]
dst = Path('models/opus-mt-vi-en-src')
dst.mkdir(parents=True, exist_ok=True)
for f in ['source.spm', 'target.spm']:
    shutil.copy2(str(d / f), str(dst / f))
"
```

---

## 7. Technical Debt & Next Tasks

| Priority | Task | Description |
|----------|------|-------------|
| P1 | Silero VAD (`audio.py`) | Pre-filter non-speech regions, reduce ASR hallucination |
| P1 | Persistent server (`server.py`) | Keep all models loaded in memory, eliminate 21s overhead |
| P2 | More test utterances | Record 3-5 samples covering different phrasing patterns |
| P2 | Module refactoring | Split `pipeline.py` into `asr.py`, `mt.py`, `tts.py` |
| P3 | MeloTTS-VI integration | Once packaging is fixed / source build works |
| P3 | DeepFilterNet evaluation | Compare WER with/without denoising on noisy data |

---

## 8. Git Sub-repo Strategy (Target State)

> **Status:** Planned — not yet implemented. The following describes the
> target state once `prototype/` is extracted as a submodule.

`prototype/` will be tracked as a **`git submodule`** — its own repo
(`aivoice-2026-prototype`) embedded inside `aivoice-2026`. The parent repo
pins a specific commit; the submodule evolves independently.

Rationale: cleaner separation, independent CI, easier to share just the
prototype without the full contest repo.

### Setup (one-time)

```bash
cd aivoice-2026
git submodule add <repo-url> prototype
cd prototype
# ... work in prototype normally ...
cd ..
git commit -m "feat: add prototype submodule"
```

### Cloning with submodules

```bash
git clone --recurse-submodules <parent-repo-url>
# or, if already cloned:
git submodule update --init
```

### Updating the submodule

```bash
cd prototype
git pull origin main
cd ..
git commit -m "chore(prototype): bump submodule"
```
