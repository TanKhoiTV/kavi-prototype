"""Build canonical Whisper FP32 mel from ONE real FLEURS vi_vn train clip.

Reads the LOCALLY downloaded parquet via pyarrow (zero network, no datasets/HF Hub).
The parquet has 3 row groups and the audio column is struct<bytes:binary, path:string>.

Usage:
    python models/qnn/whisper-small/make_mel.py [--parquet PATH] [--out-dir PATH]
"""

import argparse
import os

import numpy as np
import pyarrow.parquet as pq
import whisper

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--parquet",
        default=os.path.join(SCRIPT_DIR, "fleurs_vi_parquet", "0000.parquet"),
        help="Path to local FLEURS parquet file",
    )
    parser.add_argument(
        "--out-dir",
        default=SCRIPT_DIR,
        help="Output directory for mel spectrogram files",
    )
    args = parser.parse_args()

    assert os.path.exists(args.parquet), f"missing {args.parquet}"

    pf = pq.ParquetFile(args.parquet)
    # Read only audio/transcription/id of the FIRST row group from local disk.
    tbl = pf.read_row_group(0, columns=["audio", "transcription", "id"])
    row = tbl.slice(0, 1).to_pylist()[0]
    audio = row["audio"]  # {'bytes': b'...', 'path': None|str}
    print("id:", row.get("id"))
    print("transcription:", row.get("transcription"))

    wav_path = os.path.join(args.out_dir, "fleurs_vi_0.wav")
    with open(wav_path, "wb") as f:
        f.write(audio["bytes"])
    print("wrote", len(audio["bytes"]), "bytes ->", wav_path)

    # Canonical Whisper preprocessing: ffmpeg decode -> mono 16kHz float32, pad/trim to 30s.
    y = whisper.load_audio(wav_path)  # float32, 16 kHz
    y = whisper.pad_or_trim(y)  # 480000 samples
    print("waveform:", tuple(y.shape), y.dtype)

    # whisper-small uses 80 mels; log_mel_spectrogram applies Whisper's exact settings.
    mel = whisper.log_mel_spectrogram(y, n_mels=80)
    print("mel:", tuple(mel.shape), mel.dtype)

    ref = mel.cpu().numpy().astype(np.float32)
    out_npy = os.path.join(args.out_dir, "ref_mel_fleurs_vi_vn_0.npy")
    out_bin = os.path.join(args.out_dir, "input_features.bin")
    np.save(out_npy, ref)  # FP32 reference for scoring
    ref.tofile(out_bin)  # raw FP32 [1,80,3000] for qnn-onnx-converter --input_list
    print("saved:", out_npy, ref.shape, ref.dtype)
    print("saved:", out_bin, ref.size * 4, "bytes")


if __name__ == "__main__":
    main()
