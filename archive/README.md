# Kavi

> Offline, on-device speech-to-speech translation for Vietnamese ↔ English (and beyond).

Kavi is an entry to the **OneVoice AI Challenge** (Saigon AI Hub × Qualcomm, 2026).
It is a fully offline pipeline that runs entirely on a Snapdragon 8 Gen 2 Android
phone: capture speech → transcribe → translate → speak the result, with **no cloud
dependency**. The target is sub-2-second end-to-end latency for industrial,
low-connectivity environments.

## Pipeline

```
VAD (Silero) → ASR (Whisper) → MT (Hy-MT1.5) → TTS (MeloTTS / Piper)
```

See [docs/design.md](docs/design.md) for the full architecture and
[docs/architecture.md](docs/architecture.md) for the contest strategy.

## Repository layout

| Path | What it is |
| ------ | ------------ |
| `audio.py` | Silero VAD — voice activity detection |
| `pipeline.py` | ASR → MT → TTS orchestrator |
| `server.py` | Persistent model server (Unix socket) |
| `eval.py` | Evaluation harness — WER (jiwer) + chrF (sacrebleu) |
| `main.py` | CLI entry point |
| `experiments/denoising-validation/` | DeepFilterNet WER experiment |
| `models/` | Machine-translation checkpoints (CTranslate2) |
| `docs/` | All project documentation — see [docs/README.md](docs/README.md) |
| `refs/`, `logs/`, `voices/` | Reference transcripts, run logs, TTS voices |

## Quickstart

```bash
uv sync                                  # install dependencies
uv run python main.py --help             # CLI
uv run python eval.py greeting_vi.wav --json   # smoke test
make test                                # full CI smoke test
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Commits follow Conventional Commits.
