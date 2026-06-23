# scripts/03_add_noise_and_denoise.py
"""
Buoc 3: Mix audio voi noise SNR 5dB,
sau do chay RNNoise va DeepFilterNet.
"""

import os
import json
import numpy as np
import soundfile as sf
import scipy.signal as sps
import noisereduce as nr
import torch
from df.enhance import enhance, init_df

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

MANIFEST_PATH = "data/manifest.json"
NOISE_FILE    = "noise_samples/factory_noise.wav"
TARGET_SNR_DB = 5
SR            = 16000
DFN_SR        = 48000

os.makedirs("data/noisy/noisy_65db",        exist_ok=True)
os.makedirs("data/noisy/denoised_rnnoise",  exist_ok=True)
os.makedirs("data/noisy/denoised_dfn",      exist_ok=True)

with open(MANIFEST_PATH, encoding="utf-8") as f:
    manifest = json.load(f)

# Load noise
print(f"Loading noise: {NOISE_FILE}")
noise_full, _ = sf.read(NOISE_FILE)
noise_full    = noise_full.astype(np.float32)
print(f"Noise: {len(noise_full)/SR:.1f}s")

# Load DeepFilterNet
print("Loading DeepFilterNet...")
dfn_model, df_state, _ = init_df()
print(f"DeepFilterNet loaded. SR: {df_state.sr()}Hz")

print(f"Processing {len(manifest)} files @ SNR {TARGET_SNR_DB}dB...")

for i, item in enumerate(manifest):
    audio, _ = sf.read(item["clean"])
    audio    = audio.astype(np.float32)
    n        = len(audio)

    # Tile noise neu can
    if len(noise_full) < n:
        noise_full = np.tile(
            noise_full, int(np.ceil(n / len(noise_full)))
        )
    start = np.random.randint(0, len(noise_full) - n)
    noise = noise_full[start : start + n].astype(np.float32)

    # Scale theo SNR
    p_signal = np.mean(audio ** 2) + 1e-9
    p_noise  = np.mean(noise ** 2) + 1e-9
    target_p = p_signal / (10 ** (TARGET_SNR_DB / 10))
    scale    = np.sqrt(target_p / p_noise)
    noisy    = audio + scale * noise
    noisy    = noisy / (np.max(np.abs(noisy)) + 1e-9)

    # Save noisy
    noisy_path   = os.path.join(
        "data/noisy/noisy_65db",
        os.path.basename(item["clean"])
    )
    sf.write(noisy_path, noisy, SR)
    item["noisy"] = noisy_path

    # RNNoise baseline
    denoised_rn = nr.reduce_noise(
        y=noisy, sr=SR,
        stationary=True,
        prop_decrease=1.0,
    )
    rn_path = os.path.join(
        "data/noisy/denoised_rnnoise",
        os.path.basename(item["clean"])
    )
    sf.write(rn_path, denoised_rn, SR)
    item["denoised_rnnoise"] = rn_path

    # DeepFilterNet
    n_48k     = int(len(noisy) * DFN_SR / SR)
    audio_48k = sps.resample(noisy, n_48k).astype(np.float32)
    tensor    = torch.from_numpy(audio_48k).float().unsqueeze(0)
    enhanced  = enhance(dfn_model, df_state, tensor)
    enh_np    = enhanced.squeeze(0).numpy()
    n_16k     = int(len(enh_np) * SR / DFN_SR)
    out_audio = sps.resample(enh_np, n_16k).astype(np.float32)
    dfn_path  = os.path.join(
        "data/noisy/denoised_dfn",
        os.path.basename(item["clean"])
    )
    sf.write(dfn_path, out_audio, SR)
    item["denoised_dfn"] = dfn_path

    if (i + 1) % 100 == 0:
        print(f"  {i+1}/{len(manifest)}")

# Update manifest
with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print(f"Done!")
print(f"Noisy   : {len(os.listdir('data/noisy/noisy_65db'))} files")
print(f"RNNoise : {len(os.listdir('data/noisy/denoised_rnnoise'))} files")
print(f"DFN     : {len(os.listdir('data/noisy/denoised_dfn'))} files")
