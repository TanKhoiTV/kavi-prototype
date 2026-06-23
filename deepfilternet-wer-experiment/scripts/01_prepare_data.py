# scripts/01_prepare_data.py
"""
Buoc 1: Doc VIVOS test set, resample 16kHz mono,
build manifest.json mapping audio_path -> transcript.
Download VIVOS: kaggle datasets download kynthesis/vivos-vietnamese-speech-corpus-for-asr -p data/ --unzip
"""

import os
import json
import soundfile as sf
import numpy as np
import scipy.signal as sps

VIVOS_TEST_WAVES   = "data/vivos/test/waves"
VIVOS_TEST_PROMPTS = "data/vivos/test/prompts.txt"
OUTPUT_DIR         = "data/noisy/clean"
MANIFEST_PATH      = "data/manifest.json"
TARGET_SR          = 16000

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Reading transcripts...")
transcripts = {}
with open(VIVOS_TEST_PROMPTS, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        transcripts[parts[0]] = parts[1] if len(parts) > 1 else ""

print(f"Found {len(transcripts)} transcripts")

manifest = []
missing  = 0

for file_id, text in transcripts.items():
    speaker  = file_id[:10]
    src_path = os.path.join(VIVOS_TEST_WAVES, speaker, file_id + ".wav")
    dst_path = os.path.join(OUTPUT_DIR, file_id + ".wav")

    if not os.path.exists(src_path):
        missing += 1
        continue

    audio, sr = sf.read(src_path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32)

    if sr != TARGET_SR:
        n     = int(len(audio) * TARGET_SR / sr)
        audio = sps.resample(audio, n).astype(np.float32)

    sf.write(dst_path, audio, TARGET_SR)
    manifest.append({
        "id":        file_id,
        "clean":     dst_path,
        "reference": text,
    })

with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print(f"Done   : {len(manifest)} files -> {OUTPUT_DIR}")
print(f"Missing: {missing}")
print(f"Manifest: {MANIFEST_PATH}")
