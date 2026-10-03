"""Representative Stage 3A validation script (7 representative items)."""
from __future__ import annotations
import soundfile as sf
import numpy as np
from pathlib import Path
from bench.vad_manifest import VadManifest
from bench.vad_noise import load_mono, apply_rir

SR = 16000
LEADING = 16000
TRAILING = 16000
MANIFEST_PATH = "eval_data/vad_manifest_v2.json"

def main():
    m = VadManifest.from_json(MANIFEST_PATH)
    picks = [
        ("vi-quiet-clean-200-000", "quiet/clean"),
        ("vi-quiet-15-200-000", "quiet/+15"),
        ("vi-street-10-350-003", "street/+10"),
        ("vi-indoors-10-500-001", "indoors/+10"),
        ("vi-near-field-5-700-002", "near-field/+5"),
        ("vi-far-field-0-200-000", "far-field/0"),
        ("vi-far-field-m5-700-009", "far-field/-5"),
    ]
    results = []
    for item_id, label in picks:
        item = next(i for i in m.items if i.id == item_id)
        speech_a = load_mono(item.clean_audio_path)
        if item.speech_b_path is None:
            raise ValueError(f"speech_b_path missing for {item_id}")
        speech_b = load_mono(item.speech_b_path)

        lead = np.zeros(LEADING, dtype=np.float32)
        trail = np.zeros(TRAILING, dtype=np.float32)

        if item.rir_path is not None:
            if not Path(item.rir_path).exists():
                raise FileNotFoundError(f"RIR missing for {item_id}: {item.rir_path}")
            rir = load_mono(item.rir_path)
            speech_a_rev = apply_rir(speech_a, rir)
        else:
            speech_a_rev = speech_a

        if item.noise_type == "clean":
            mixed_a = speech_a_rev
            measured_snr = None
        else:
            if item.noise_path is None or not Path(item.noise_path).exists():
                raise FileNotFoundError(f"Real noise missing for {item_id}: {item.noise_path}")
            noise = load_mono(item.noise_path)
            target_snr = item.snr_db
            target_len = len(speech_a_rev)
            if len(noise) < target_len:
                repeats = (target_len + len(noise) - 1) // len(noise)
                noise = np.tile(noise, repeats)
            noise_aligned = noise[:target_len]
            s_rms = np.sqrt(np.mean(speech_a_rev**2))
            n_rms = np.sqrt(np.mean(noise_aligned**2))
            if s_rms == 0 or n_rms == 0:
                raise ValueError("Zero RMS for SNR calculation")
            target_noise_rms = s_rms / (10**(target_snr / 20.0))
            scaled_noise = noise_aligned * (target_noise_rms / (n_rms + 1e-12))
            mixed_a = speech_a_rev + scaled_noise[:len(speech_a_rev)]
            peak = np.max(np.abs(mixed_a))
            clipping = peak > 0.99
            if clipping:
                mixed_a = mixed_a * (0.99 / peak)
            measured_snr = float(20 * np.log10(s_rms / (np.sqrt(np.mean(scaled_noise**2)) + 1e-12)))

        pause_samples = int(item.pause_ms * 16)
        mixed = np.concatenate([lead, mixed_a, np.zeros(pause_samples, dtype=np.float32), speech_b, trail])
        out_path = f"/tmp/kavi_rep_{item_id}.wav"
        sf.write(out_path, mixed, SR)

        info = sf.info(out_path)
        assert info.samplerate == SR, f"Sample rate mismatch: {info.samplerate}"
        assert info.frames > 0, f"Empty output for {item_id}"

        s1, e1 = item.ground_truth_segments[0]
        s2, e2 = item.ground_truth_segments[1]
        expected_gap = int(item.pause_ms * 16)
        actual_gap = s2 - e1
        assert actual_gap == expected_gap, f"GT gap mismatch {item_id}: {actual_gap} != {expected_gap}"
        assert s2 > e1

        assert item.speech_b_path is not None
        assert Path(item.speech_b_path).exists(), f"speech_b_path missing for {item_id}"

        if item.noise_type != "clean":
            assert item.noise_path is not None
            assert Path(item.noise_path).exists(), f"Real noise missing for {item_id}"
        if item.condition in ("indoors", "near-field", "far-field"):
            assert item.rir_path is not None
            assert Path(item.rir_path).exists(), f"Real RIR missing for {item_id}"

        results.append({
            "item_id": item_id,
            "label": label,
            "condition": item.condition,
            "snr_target": item.snr_db,
            "measured_snr": measured_snr,
            "out_path": out_path,
            "duration_s": info.duration,
            "frames": info.frames,
            "clipping": clipping if item.noise_type != "clean" else False,
        })
        print(f"PASS {label} | {item_id} | target={item.snr_db} | meas={measured_snr} | out={out_path} | dur={info.duration:.2f}s")

    print("\n=== All 7 representative materializations PASS ===")
    for r in results:
        print(f"  {r['label']:12} | target={r['snr_target']} | meas={r['measured_snr']} | clip={r['clipping']} | file={r['out_path']}")

if __name__ == "__main__":
    main()
