import os

import numpy as np
import pyarrow.parquet as pq
import whisper

# Phase-4 Step 2 (part 2): build the canonical Whisper FP32 mel from ONE real
# FLEURS vi_vn train clip. Reads the LOCALLY downloaded parquet via pyarrow
# (zero network, no datasets/HF Hub). The parquet has 3 row groups and the
# audio column is struct<bytes:binary, path:string>.

LOCAL = "/home/dmin/qairt-work/whisper-encoder/fleurs_vi_parquet/0000.parquet"
assert os.path.exists(LOCAL), f"missing {LOCAL}"

pf = pq.ParquetFile(LOCAL)
# Read only audio/transcription/id of the FIRST row group from local disk.
tbl = pf.read_row_group(0, columns=["audio", "transcription", "id"])
row = tbl.slice(0, 1).to_pylist()[0]
audio = row["audio"]  # {'bytes': b'...', 'path': None|str}
print("id:", row.get("id"))
print("transcription:", row.get("transcription"))

wav_path = "/home/dmin/qairt-work/whisper-encoder/fleurs_vi_0.wav"
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
out_npy = "/home/dmin/qairt-work/whisper-encoder/ref_mel_fleurs_vi_vn_0.npy"
out_bin = "/home/dmin/qairt-work/whisper-encoder/input_features.bin"
np.save(out_npy, ref)  # FP32 reference for scoring
ref.tofile(out_bin)  # raw FP32 [1,80,3000] for qnn-onnx-converter --input_list
print("saved:", out_npy, ref.shape, ref.dtype)
print("saved:", out_bin, ref.size * 4, "bytes")
