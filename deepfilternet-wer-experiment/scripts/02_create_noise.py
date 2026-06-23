# scripts/02_create_noise.py
"""
Buoc 2: Tao factory noise tu ESC-50 dataset.
Download ESC-50 truoc:
  kaggle datasets download mmoreaux/environmental-sound-classification-50 \
    -p noise_samples/esc50/ --unzip
"""

import os
import json
import numpy as np
import pandas as pd
import soundfile as sf
import scipy.signal as sps

ESC50_CSV   = "noise_samples/esc50/esc50.csv"
ESC50_AUDIO = "noise_samples/esc50/audio/audio/"
OUTPUT_PATH = "noise_samples/factory_noise.wav"
SR          = 16000

# Category giong factory noise nhat
FACTORY_CATS = ["engine", "chainsaw", "hand_saw", "washing_machine"]

os.makedirs("noise_samples", exist_ok=True)

print(f"Loading ESC-50 metadata: {ESC50_CSV}")
df = pd.read_csv(ESC50_CSV)

factory_files = df[df["category"].isin(FACTORY_CATS)]["filename"].tolist()
print(f"Found {len(factory_files)} files: {FACTORY_CATS}")

noise_chunks = []
for fname in factory_files:
    fpath = os.path.join(ESC50_AUDIO, fname)
    if not os.path.exists(fpath):
        continue
    audio, sr = sf.read(fpath)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32)
    if sr != SR:
        n     = int(len(audio) * SR / sr)
        audio = sps.resample(audio, n).astype(np.float32)
    noise_chunks.append(audio)

noise_full = np.concatenate(noise_chunks)
noise_full = noise_full / (np.max(np.abs(noise_full)) + 1e-9)
sf.write(OUTPUT_PATH, noise_full, SR)

print(f"Created: {OUTPUT_PATH} ({len(noise_full)/SR:.1f}s)")
print(f"Files used: {len(noise_chunks)}")
