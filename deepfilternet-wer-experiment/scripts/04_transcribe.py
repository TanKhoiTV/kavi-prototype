# scripts/04_transcribe.py
"""
Buoc 4: Chay Whisper Medium tren 4 conditions.
"""

import os
import json

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from faster_whisper import WhisperModel

MANIFEST_PATH = "data/manifest.json"
RESULTS_DIR   = "results"
MODEL_SIZE    = "medium"
DEVICE        = "cpu"
COMPUTE       = "int8"

os.makedirs(RESULTS_DIR, exist_ok=True)

CONDITIONS = {
    "clean":            "clean",
    "noisy":            "noisy",
    "denoised_rnnoise": "denoised_rnnoise",
    "denoised_dfn":     "denoised_dfn",
}

print(f"Loading Whisper {MODEL_SIZE}...")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE)
print("Loaded.")

with open(MANIFEST_PATH, encoding="utf-8") as f:
    manifest = json.load(f)

for condition_name, manifest_key in CONDITIONS.items():
    out_path = os.path.join(RESULTS_DIR, f"transcripts_{condition_name}.json")

    if os.path.exists(out_path):
        print(f"[{condition_name}] Already done, skipping.")
        continue

    print(f"\n=== Transcribing: {condition_name} ===")
    results = []

    for i, item in enumerate(manifest):
        audio_path = item.get(manifest_key)
        if not audio_path or not os.path.exists(audio_path):
            results.append({"id": item["id"], "hypothesis": ""})
            continue

        segments, _ = model.transcribe(
            audio_path,
            language="vi",
            beam_size=5,
            vad_filter=False,
        )
        hypothesis = " ".join(seg.text.strip() for seg in segments)
        results.append({"id": item["id"], "hypothesis": hypothesis})

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(manifest)}")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {out_path}")

print("\nAll conditions transcribed!")
