#!/usr/bin/env python3
"""Persistent model server — preloads ASR/MT/TTS models and serves via Unix socket."""

from __future__ import annotations

import contextlib
import json
import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path

import soundfile as sf

from audio import get_speech_metadata, rms_normalize
from pipeline import (
    _default_socket_path,
    load_asr,
    load_mt,
    load_tts,
    resample_to_16k,
    synthesize,
    transcribe,
    translate,
)


class PipelineModelServer:
    """Preloads all models and serves pipeline requests over a Unix socket."""

    def __init__(self, socket_path: str | None = None, asr_model_size: str = "small"):
        self.socket_path = socket_path or _default_socket_path()
        self.asr_model_size = asr_model_size
        self.lock = threading.Lock()
        self._server_socket = None
        self._running = False

        print(f"      Loading ASR ({asr_model_size}) …", file=sys.stderr)
        self.asr_model = load_asr(asr_model_size)

        print("      Loading MT (CTranslate2 int8) …", file=sys.stderr)
        self.translator, self.sp_src, self.sp_tgt = load_mt()

        print("      Loading TTS (Piper) …", file=sys.stderr)
        self.tts_model = load_tts()

        print("      Loading VAD …", file=sys.stderr)
        from audio import load_vad

        load_vad()

        print("      All models loaded.", file=sys.stderr)

    def run(self):
        """Start the server, blocking until shutdown."""
        socket_path = Path(self.socket_path)
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(FileNotFoundError):
            os.unlink(str(socket_path))

        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.bind(str(socket_path))
        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)
        self._running = True

        def _handle_sig(signum, frame):
            self.shutdown()

        signal.signal(signal.SIGINT, _handle_sig)
        signal.signal(signal.SIGTERM, _handle_sig)

        print(f"Pipeline model server ready on {socket_path}", file=sys.stderr)

        while self._running:
            try:
                conn, _ = self._server_socket.accept()
                t = threading.Thread(
                    target=self._handle_client, args=(conn,), daemon=True
                )
                t.start()
            except TimeoutError:
                continue
            except OSError:
                break

        self.shutdown()

    def _handle_client(self, conn):
        try:
            with conn.makefile("rwb") as f:
                line = f.readline()
                if not line:
                    return
                request = json.loads(line.decode())
                req_id = request.get("id", 0)
                method = request.get("method", "")
                params = request.get("params", {})

                if method != "run_pipeline":
                    response = {"id": req_id, "error": f"Unknown method: {method}"}
                else:
                    with self.lock:
                        try:
                            result = self._process(**params)
                            if "error" in result:
                                response = {"id": req_id, "error": result["error"]}
                            else:
                                response = {"id": req_id, "result": result}
                        except Exception as e:
                            response = {"id": req_id, "error": str(e)}

                f.write((json.dumps(response) + "\n").encode())
                f.flush()
        except Exception as exc:
            print(f"      [server] error: {exc}", file=sys.stderr)
        finally:
            with contextlib.suppress(Exception):
                conn.close()

    def _process(
        self,
        audio_path,
        asr_model_size="small",
        output_dir=".",
        quiet=True,  # quiet: accepted for RPC API compatibility; server always runs silently
        vad=True,
        vad_threshold=0.4,
        normalize=True,
    ) -> dict:
        audio_path = str(audio_path)
        output_dir = str(Path(output_dir).resolve())
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        if asr_model_size != self.asr_model_size:
            return {
                "error": f"asr_model_size mismatch: server has "
                f"'{self.asr_model_size}', client requested "
                f"'{asr_model_size}'"
            }

        t0 = time.perf_counter()
        resampled = resample_to_16k(audio_path, str(Path(output_dir) / "resampled.wav"))

        # ── Normalize ──
        if normalize:
            data, sr = sf.read(resampled)
            data = rms_normalize(data)
            sf.write(resampled, data, sr)

        vad_result = None
        if vad:
            vad_result = get_speech_metadata(resampled, threshold=vad_threshold)

        asr_result = transcribe(self.asr_model, resampled)
        if not asr_result["text"]:
            return {"error": "no speech detected"}

        mt_result = translate(
            self.translator, self.sp_src, self.sp_tgt, asr_result["text"]
        )

        output_wav = str(Path(output_dir) / "output.wav")
        tts_result = synthesize(self.tts_model, mt_result["translation"], output_wav)

        total = round(time.perf_counter() - t0, 2)

        return {
            "audio_input": audio_path,
            "vad": vad_result,
            "asr": asr_result,
            "mt": mt_result,
            "tts": tts_result,
            "total_s": total,
            "output_wav": output_wav,
        }

    def shutdown(self):
        self._running = False
        if self._server_socket:
            with contextlib.suppress(OSError):
                self._server_socket.close()
        with contextlib.suppress(FileNotFoundError):
            os.unlink(self.socket_path)
        print("Pipeline model server shutting down.", file=sys.stderr)


def run_server(socket_path=None, asr_model_size="small"):
    server = PipelineModelServer(socket_path=socket_path, asr_model_size=asr_model_size)
    server.run()
