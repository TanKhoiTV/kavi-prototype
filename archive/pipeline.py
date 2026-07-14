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
import json
import os
import socket
import subprocess
import sys
import time
import wave
from pathlib import Path

import soundfile as sf

from audio import get_speech_metadata, rms_normalize


def _default_socket_path() -> str:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return str(Path(runtime_dir) / "aivoice.sock")
    return f"/tmp/aivoice-{os.getuid()}.sock"


class PipelineClient:
    def __init__(self, socket_path: str | None = None, timeout: float = 30.0):
        self.socket_path = socket_path or _default_socket_path()
        self.timeout = timeout
        self._request_id = 0

    def call(self, method: str, params: dict) -> dict:
        self._request_id += 1
        payload = {"id": self._request_id, "method": method, "params": params}
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect(self.socket_path)
            sock.sendall((json.dumps(payload) + "\n").encode())
            with sock.makefile("rwb") as f:
                line = f.readline()
            if not line:
                raise ConnectionError("Server closed connection")
            response = json.loads(line.decode())
            if response.get("id") != self._request_id:
                raise RuntimeError(
                    f"Request ID mismatch: sent {self._request_id}, "
                    f"got {response.get('id')}"
                )
            return response
        finally:
            sock.close()


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


def load_tts(voice_name: str = "en_US-lessac-medium", voice_dir: str | Path = "voices"):
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

    for _tool, args in [
        (
            "ffmpeg",
            ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path],
        ),
        ("sox", ["sox", input_path, "-r", "16000", "-c", "1", output_path]),
    ]:
        try:
            subprocess.run(args, check=True, capture_output=True)
            return output_path
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue

    data, sr = sf.read(input_path)
    if sr != 16000:
        import torch
        import torchaudio.functional as AF

        data_t = torch.from_numpy(data).float()
        # torchaudio AF.resample expects (channels, samples) — transpose if 2D
        if data_t.dim() == 2:
            data_t = data_t.T  # (samples, channels) → (channels, samples)
        resampled = AF.resample(data_t, sr, 16000)
        if resampled.dim() == 2:
            resampled = resampled.T  # (channels, samples) → (samples, channels)
        sf.write(output_path, resampled.numpy().astype(data.dtype), 16000)
    else:
        sf.write(output_path, data, sr)
    return output_path


# ── Main pipeline ────────────────────────────────────────


def run_pipeline(
    audio_path: str,
    asr_model_size: str = "small",
    output_dir: str = ".",
    quiet: bool = False,
    vad: bool = True,
    vad_threshold: float = 0.4,
    normalize: bool = True,
    use_server: bool = True,
) -> dict:
    audio_path = str(audio_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()

    # Try persistent server first
    if use_server:
        try:
            client = PipelineClient(timeout=60.0)
            params = {
                "audio_path": str(Path(audio_path).resolve()),
                "asr_model_size": asr_model_size,
                "output_dir": str(Path(output_dir).resolve()),
                "quiet": quiet,
                "vad": vad,
                "vad_threshold": vad_threshold,
                "normalize": normalize,
            }
            response = client.call("run_pipeline", params)
            if "error" in response:
                return {"error": response["error"]}
            return response["result"]
        except (
            TimeoutError,
            FileNotFoundError,
            ConnectionRefusedError,
            OSError,
            ConnectionError,
        ) as e:
            if not quiet:
                print(
                    f"      Server unavailable ({e}), falling back to direct loading…"
                )
    # Fall through to direct-loading code

    total_steps = 6 if vad else 5
    step = 0

    if not quiet:
        print("─" * 52)
        print("  Pipeline: ASR → MT → TTS")
        print("─" * 52)

    # ── Resample ──
    step += 1
    if not quiet:
        print(f"\n[{step}/{total_steps}] Resampling audio to 16 kHz …")
    resampled = resample_to_16k(audio_path, str(out_dir / "resampled.wav"))
    info = sf.SoundFile(resampled)
    if not quiet:
        print(
            f"      {Path(audio_path).name} → {info.samplerate} Hz, {info.channels}ch"
        )

    # ── Normalize ──
    step += 1
    if not quiet:
        print(f"\n[{step}/{total_steps}] RMS-normalizing audio …")
    if normalize:
        data, sr = sf.read(resampled)
        data = rms_normalize(data)
        sf.write(resampled, data, sr)
        if not quiet:
            print(f"      Normalized to -20 dBFS")
    else:
        if not quiet:
            print("      Skipped")

    # ── VAD ──
    vad_result = None
    if vad:
        step += 1
        if not quiet:
            print(f"\n[{step}/{total_steps}] Running VAD …")
        vad_result = get_speech_metadata(resampled, threshold=vad_threshold)
        if not quiet:
            if vad_result.get("available", True):
                print(
                    f"      speech: {vad_result['speech_ratio'] * 100:.1f}%  "
                    f"({vad_result['elapsed_s']}s)"
                )
            else:
                print("      VAD unavailable (silero-vad not installed), skipping")

    # ── ASR ──
    step += 1
    if not quiet:
        print(
            f"\n[{step}/{total_steps}] Loading ASR (faster-whisper {asr_model_size}) …"
        )
    asr_model = load_asr(asr_model_size)
    if not quiet:
        print("      Transcribing …")
    asr_result = transcribe(asr_model, resampled)
    if not quiet:
        print(f"      → {asr_result['text']!r}")
        print(f"      ({asr_result['elapsed_s']}s)")

    if not asr_result["text"]:
        if not quiet:
            print("      ⚠ No speech detected — stopping.")
        return {"error": "no speech detected"}

    # ── MT ──
    step += 1
    if not quiet:
        print(f"\n[{step}/{total_steps}] Loading MT (CTranslate2 int8 Opus-MT) …")
    translator, sp_src, sp_tgt = load_mt()
    if not quiet:
        print("      Translating …")
    mt_result = translate(translator, sp_src, sp_tgt, asr_result["text"])
    if not quiet:
        print(f"      → {mt_result['translation']!r}")
        print(f"      ({mt_result['elapsed_s']}s)")

    # ── TTS ──
    step += 1
    if not quiet:
        print(f"\n[{step}/{total_steps}] Loading TTS (Piper: en_US-lessac-medium) …")
    tts_model = load_tts(voice_dir=str(out_dir / "voices"))
    output_wav = str(out_dir / "output.wav")
    if not quiet:
        print("      Synthesising …")
    tts_result = synthesize(tts_model, mt_result["translation"], output_wav)
    if not quiet:
        print(f"      → {tts_result['output']}")
        print(
            f"      ({tts_result['elapsed_s']}s, {tts_result['audio_duration_s']}s audio)"
        )

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
        "vad": vad_result,
        "asr": asr_result,
        "mt": mt_result,
        "tts": tts_result,
        "total_s": total,
        "output_wav": output_wav,
    }


# ── CLI ──────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="OneVoice AI Challenge — ASR→MT→TTS pipeline"
    )
    parser.add_argument("audio", nargs="?", help="Input WAV file (Vietnamese speech)")
    parser.add_argument(
        "--serve", action="store_true", help="Start persistent model server"
    )
    parser.add_argument(
        "--socket", help="Unix socket path for --serve mode (default: auto)"
    )
    parser.add_argument(
        "--asr-model", default="small", help="Whisper model size [small]"
    )
    parser.add_argument("--output-dir", default=".", help="Output directory [.]")
    parser.add_argument(
        "--normalize",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="RMS-normalize audio to -20 dBFS [default: enabled]",
    )
    parser.add_argument(
        "--vad",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable Silero VAD [default: enabled]",
    )
    parser.add_argument(
        "--vad-threshold",
        type=float,
        default=0.4,
        help="VAD confidence threshold [default: 0.4]",
    )

    args = parser.parse_args()

    if args.serve:
        from server import run_server

        run_server(socket_path=args.socket, asr_model_size=args.asr_model)
        return

    if not args.audio:
        parser.print_help()
        sys.exit(1)
    if not Path(args.audio).exists():
        print(f"❌ File not found: {args.audio}")
        sys.exit(1)
    result = run_pipeline(
        audio_path=args.audio,
        asr_model_size=args.asr_model,
        output_dir=args.output_dir,
        normalize=args.normalize,
        vad=args.vad,
        vad_threshold=args.vad_threshold,
    )
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
