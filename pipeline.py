#!/usr/bin/env python3
"""
OneVoice AI Challenge — ASR → MT → TTS pipeline prototype.
Single-file, file-based I/O for fast iteration.

Usage:
    python pipeline.py greeting_vi.wav

Pipeline:
    audio.wav → Whisper (ASR) → Opus-MT (CTranslate2 int8) → Piper-TTS → output.wav
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import wave
from pathlib import Path

import soundfile as sf


# ── ASR: Whisper via faster-whisper ──────────────────────

def load_asr(model_size: str = "small"):
    from faster_whisper import WhisperModel
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe(model, audio_path: str, language: str = "vi") -> dict:
    start = time.perf_counter()
    segments, info = model.transcribe(audio_path, language=language)
    segments = list(segments)
    elapsed = time.perf_counter() - start
    text = " ".join(s.text for s in segments).strip()
    return {
        "text": text,
        "language": info.language if info else language,
        "duration": info.duration if info else None,
        "elapsed_s": round(elapsed, 2),
    }


# ── MT: Opus-MT via CTranslate2 int8 ─────────────────────

MT_MODEL_DIR = Path(__file__).parent / "models" / "opus-mt-vi-en-ct2"
MT_SRC_DIR = Path(__file__).parent / "models" / "opus-mt-vi-en-src"


def load_mt():
    """Load CTranslate2 translation model (int8 quantized) + SPM tokenizers."""
    import ctranslate2
    import sentencepiece as spm

    if not MT_MODEL_DIR.exists():
        raise FileNotFoundError(
            f"MT model not found at {MT_MODEL_DIR}.\n"
            "Run: uv run ct2-transformers-converter "
            "--model Helsinki-NLP/opus-mt-vi-en "
            f"--output_dir {MT_MODEL_DIR} --quantization int8"
        )

    translator = ctranslate2.Translator(
        str(MT_MODEL_DIR), device="cpu", compute_type="int8"
    )
    sp_src = spm.SentencePieceProcessor()
    sp_src.load(str(MT_SRC_DIR / "source.spm"))
    sp_tgt = spm.SentencePieceProcessor()
    sp_tgt.load(str(MT_SRC_DIR / "target.spm"))
    return translator, sp_src, sp_tgt


def translate(translator, sp_src, sp_tgt, text: str) -> dict:
    start = time.perf_counter()
    tokens = sp_src.encode(text, out_type=str)
    results = translator.translate_batch([tokens])
    translation = sp_tgt.decode(results[0].hypotheses[0])
    elapsed = time.perf_counter() - start
    return {
        "source": text,
        "translation": translation,
        "elapsed_s": round(elapsed, 2),
    }


# ── TTS: Piper-TTS (offline, fast) ────────────────────────

def load_tts(voice_name: str = "en_US-lessac-medium",
             voice_dir: str = "voices"):
    from piper import PiperVoice
    from piper.download_voices import download_voice

    voice_dir = Path(voice_dir)
    voice_dir.mkdir(parents=True, exist_ok=True)

    model_path = voice_dir / f"{voice_name}.onnx"
    config_path = voice_dir / f"{voice_name}.onnx.json"

    if not model_path.exists() or not config_path.exists():
        download_voice(voice_name, voice_dir)

    return PiperVoice.load(model_path, config_path)


def synthesize(voice, text: str, output_path: str = "output.wav") -> dict:
    start = time.perf_counter()
    with wave.open(output_path, "w") as wav_file:
        voice.synthesize_wav(text, wav_file)
    elapsed = time.perf_counter() - start

    with wave.open(output_path, "r") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        duration = frames / rate if rate else 0

    return {
        "output": output_path,
        "elapsed_s": round(elapsed, 2),
        "audio_duration_s": round(duration, 2),
    }


# ── Audio helpers ─────────────────────────────────────────

def resample_to_16k(input_path: str, output_path: str) -> str:
    if Path(output_path).exists():
        return output_path

    for tool, args in [
        ("ffmpeg", ["ffmpeg", "-y", "-i", input_path,
                     "-ar", "16000", "-ac", "1", output_path]),
        ("sox", ["sox", input_path, "-r", "16000", "-c", "1", output_path]),
    ]:
        try:
            subprocess.run(args, check=True, capture_output=True)
            return output_path
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue

    data, sr = sf.read(input_path)
    if sr != 16000:
        import numpy as np
        from scipy import signal
        target_len = int(len(data) * 16000 / sr)
        data_resampled = signal.resample(data, target_len)
        sf.write(output_path, data_resampled.astype(data.dtype), 16000)
    else:
        sf.write(output_path, data, sr)
    return output_path


# ── Main pipeline ────────────────────────────────────────

def run_pipeline(audio_path: str, asr_model_size: str = "small",
                 output_dir: str = ".", quiet: bool = False) -> dict:
    audio_path = str(audio_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()

    if not quiet:
        print("─" * 52)
        print("  Pipeline: ASR → MT → TTS")
        print("─" * 52)

    # ── Resample ──
    if not quiet:
        print(f"\n[1/4] Resampling audio to 16 kHz …")
    resampled = resample_to_16k(audio_path, str(output_dir / "resampled.wav"))
    info = sf.SoundFile(resampled)
    if not quiet:
        print(f"      {Path(audio_path).name} → {info.samplerate} Hz, {info.channels}ch")

    # ── ASR ──
    if not quiet:
        print(f"\n[2/4] Loading ASR (faster-whisper {asr_model_size}) …")
    asr_model = load_asr(asr_model_size)
    if not quiet:
        print(f"      Transcribing …")
    asr_result = transcribe(asr_model, resampled)
    if not quiet:
        print(f"      → {asr_result['text']!r}")
        print(f"      ({asr_result['elapsed_s']}s)")

    if not asr_result["text"]:
        if not quiet:
            print("      ⚠ No speech detected — stopping.")
        return {"error": "no speech detected"}

    # ── MT ──
    if not quiet:
        print(f"\n[3/4] Loading MT (CTranslate2 int8 Opus-MT) …")
    translator, sp_src, sp_tgt = load_mt()
    if not quiet:
        print(f"      Translating …")
    mt_result = translate(translator, sp_src, sp_tgt, asr_result["text"])
    if not quiet:
        print(f"      → {mt_result['translation']!r}")
        print(f"      ({mt_result['elapsed_s']}s)")

    # ── TTS ──
    if not quiet:
        print(f"\n[4/4] Loading TTS (Piper: en_US-lessac-medium) …")
    tts_model = load_tts(voice_dir=str(output_dir / "voices"))
    output_wav = str(output_dir / "output.wav")
    if not quiet:
        print(f"      Synthesising …")
    tts_result = synthesize(tts_model, mt_result["translation"], output_wav)
    if not quiet:
        print(f"      → {tts_result['output']}")
        print(f"      ({tts_result['elapsed_s']}s, {tts_result['audio_duration_s']}s audio)")

    total = round(time.perf_counter() - t0, 2)

    if not quiet:
        print(f"\n{'─' * 52}")
        print(f"  ✅ Pipeline complete — {total}s total (CPU, no GPU)")
        print(f"     Input:  {Path(audio_path).name}")
        print(f"     ASR:    {asr_result['text']!r}")
        print(f"     MT:     {mt_result['translation']!r}")
        print(f"     Output: {output_wav}")
        print(f"{'─' * 52}")

    return {
        "audio_input": audio_path,
        "asr": asr_result,
        "mt": mt_result,
        "tts": tts_result,
        "total_s": total,
        "output_wav": output_wav,
    }


# ── CLI ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="OneVoice AI Challenge — ASR→MT→TTS pipeline")
    parser.add_argument("audio", help="Input WAV file (Vietnamese speech)")
    parser.add_argument("--asr-model", default="small",
                        help="Whisper model size [small]")
    parser.add_argument("--output-dir", default=".",
                        help="Output directory [.]")
    args = parser.parse_args()

    if not Path(args.audio).exists():
        print(f"❌ File not found: {args.audio}")
        sys.exit(1)

    result = run_pipeline(
        audio_path=args.audio,
        asr_model_size=args.asr_model,
        output_dir=args.output_dir,
    )
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
