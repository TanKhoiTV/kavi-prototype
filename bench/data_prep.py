"""Phase 1 data prep: build the lean eval set + noise/SNR variants -> manifest.

The eval set is built from locally-available FLEURS parquets when present
(download them with `download_fleurs()` / `make bench-data --download-fleurs`
once Hugging Face large-file downloads work in your environment). When they are
not present, a runnable **offline fallback** set is emitted instead: an authored
VI<->EN factory/logistics gold set scored as MT (vi->en) + TTS items, using
synthetic noise for the SNR recipe.

Speech corpora (FLEURS `vi_vn`/`en_us`, CC BY 4.0) give:
  - VI ASR + EN ASR items (real speech, transcript references)
  - VI<->EN speech-translation items via FLEURS' shared sentence IDs (plan S3.3)
The authored gold set adds domain-flavored MT/TTS references that need no
download. ASR items are only emitted when FLEURS parquets are available; the
offline fallback covers MT + TTS, which the v0 CPU candidates score fully
offline (Opus-MT vi->en + Piper EN).

Noise is applied at eval time (plan S3.5): synthetic steady/impulsive noise mixed
to a target SNR via torchaudio.add_noise. Swap in MUSAN/RIRS_NOISES later by
replacing `_synth_noise` with real clips (the manifest schema is unchanged).
"""

from __future__ import annotations

import random
from pathlib import Path

import soundfile as sf

from .schema import EvalItem, RunManifest

SNR_LEVELS = [None, 15.0, 10.0, 5.0, 0.0]  # clean + mild/moderate/hard/severe
NOISE_TYPES = ["steady", "impulsive"]

# Authored VI<->EN factory/logistics gold set (text only, no download needed).
# Domain-skewed per the benchmarking plan (S8): equipment, safety, numbers,
# short imperatives. Use as MT (vi->en) + TTS reference texts.
GOLD_SET: list[tuple[str, str]] = [
    (
        "Xin hãy đeo kính bảo hộ trước khi vào khu vực làm việc.",
        "Please wear safety goggles before entering the work area.",
    ),
    (
        "Cần kiểm tra áp suất lốp xe nâng mỗi ca làm việc.",
        "Check the forklift tire pressure at the start of every shift.",
    ),
    (
        "Máy nén khí đang quá nhiệt, hãy tắt ngay lập tức.",
        "The air compressor is overheating, switch it off immediately.",
    ),
    (
        "Kho hàng số tám đã nhận đủ năm mươi thùng hàng.",
        "Warehouse number eight has received the full fifty cartons.",
    ),
    (
        "Cảnh báo: khu vực này có nguy cơ rơi vật thể từ trên cao.",
        "Warning: this area has a risk of falling objects from above.",
    ),
    (
        "Vui lòng giữ khoảng cách hai mét với băng chuyền.",
        "Please keep a two meter distance from the conveyor belt.",
    ),
    (
        "Đèn báo hiệu đang nhấp nháy, không được đi qua.",
        "The signal light is flashing, do not walk through.",
    ),
    (
        "Hôm nay chúng ta xuất kho tổng cộng một trăm hai mươi đơn.",
        "Today we shipped a total of one hundred and twenty orders.",
    ),
    (
        "Mặt hàng dễ vỡ, xếp nhẹ tay và dán nhãn cẩn thận.",
        "Fragile goods, handle with care and label them properly.",
    ),
    (
        "Cần bổ sung ba kiện hàng vào chuyến giao buổi chiều.",
        "We need to add three packages to the afternoon delivery.",
    ),
    (
        "Van an toàn đã mở, xả áp suất dư thừa ra ngoài.",
        "The relief valve opened and vented the excess pressure outside.",
    ),
    (
        "Cấm sử dụng điện thoại di động gần trạm biến áp.",
        "Mobile phones are prohibited near the transformer station.",
    ),
]


def _synth_noise(kind: str, length: int, sample_rate: int, seed: int):
    import torch
    import torchaudio

    g = torch.Generator().manual_seed(seed)
    if kind == "steady":
        noise = torch.randn(1, length, generator=g)
        noise = torchaudio.functional.lowpass_biquad(noise, sample_rate, 1200)
    else:  # impulsive: periodic bursts -> forklift/clatter impulses
        noise = torch.zeros(1, length)
        burst = round(0.02 * sample_rate)
        spacing = round(0.25 * sample_rate)
        rng = random.Random(seed)
        pos = rng.randint(0, max(1, burst))
        while pos < length:
            end = min(pos + burst, length)
            noise[0, pos:end] = torch.randn(end - pos, generator=g) * 4.0
            pos += spacing
    return noise


def _mix(clean, noise, snr_db: float):
    import torch
    import torchaudio

    if noise.shape[-1] < clean.shape[-1]:
        reps = (clean.shape[-1] + noise.shape[-1] - 1) // noise.shape[-1]
        noise = noise.repeat(1, reps)
    noise = noise[:, : clean.shape[-1]]
    try:
        return torchaudio.functional.add_noise(clean, noise, torch.tensor([snr_db]))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"noise mix failed (snr={snr_db}): {exc}") from exc


def mix_noise(clean_wav: str, noise_wav: str, snr_db: float, out_path: str) -> None:
    """Mix `noise_wav` into `clean_wav` at `snr_db` dB and write to `out_path`."""
    import torch
    import torchaudio

    clean, sr = sf.read(clean_wav, dtype="float32", always_2d=True)
    clean = torch.from_numpy(clean).transpose(0, 1)
    noise, nsr = sf.read(noise_wav, dtype="float32", always_2d=True)
    noise = torch.from_numpy(noise).transpose(0, 1)
    if nsr != sr:
        noise = torchaudio.functional.resample(noise, nsr, sr)
    mixed = _mix(clean, noise, snr_db)
    sf.write(out_path, mixed.transpose(0, 1).numpy(), sr)


def download_fleurs(
    workdir: str,
    max_retries: int = 20,
    langs: tuple[str, ...] = ("vi_vn", "en_us"),
) -> None:
    """Fetch FLEURS parquets via curl (needs working HF access).

    Uses `-C -` (resume) + `--retry-all-errors` so a dropped connection
    continues from the downloaded offset instead of restarting -- required
    because the proxy here drops large (~690 MB) parquet downloads.
    """
    import subprocess

    wd = Path(workdir)
    (wd / "raw").mkdir(parents=True, exist_ok=True)
    base = "https://huggingface.co/datasets/google/fleurs/resolve/main/parquet-data"
    for lang in langs:
        url = f"{base}/{lang}/test-00000-of-00001.parquet"
        out = wd / "raw" / f"fleurs_{lang}_test.parquet"
        for attempt in range(1, max_retries + 1):
            print(f"downloading {lang} (attempt {attempt}/{max_retries})...")
            rc = subprocess.run(
                [
                    "curl",
                    "-sSL",
                    "--retry",
                    "20",
                    "--retry-delay",
                    "2",
                    "--retry-all-errors",
                    "--max-time",
                    "600",
                    "-C",
                    "-",
                    "-o",
                    str(out),
                    url,
                ],
                check=False,
            ).returncode
            if rc == 0 and out.exists() and out.stat().st_size > 1_000_000:
                print(f"  ok: {out} ({out.stat().st_size} bytes)")
                break
            print(f"  incomplete (rc={rc}); resuming")


def _load_fleurs(path: str, n: int, sample_rate: int, seed: int = 42):
    """Return list of (id, transcript, audio_tensor) from a FLEURS parquet.

    FLEURS stores the `audio` column as encoded bytes (WAV); decode via
    soundfile and resample/downmix to `sample_rate`. Reads only the needed
    columns, and random-samples `n` utterances with a fixed seed so the lean
    set is reproducible and not biased by file order.
    """
    import io
    import random

    import pyarrow.parquet as pq
    import torch
    import torchaudio

    try:
        pf = pq.ParquetFile(path)
        # Cheap pass: ids + transcripts only (no audio bytes) for sampling.
        meta = pf.read_row_groups([0], columns=["id", "transcription"]).to_pylist()
        idxs = (
            list(range(len(meta)))
            if len(meta) <= n
            else random.Random(seed).sample(range(len(meta)), n)
        )
        # Audio pass: read only the audio column for the needed row group, then
        # keep just the sampled rows. (Parquet is read at row-group granularity,
        # so for a single-row-group file the audio column is still materialized
        # once -- true peak-memory reduction would need smaller row groups.)
        audio_rows = pf.read_row_groups([0], columns=["id", "audio"]).to_pylist()
        audio_by_id = {str(r["id"]): (r.get("audio") or {}) for r in audio_rows}
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"cannot read FLEURS parquet {path}: {exc}") from exc
    out = []
    for i in idxs:
        r = meta[i]
        uid = str(r.get("id"))
        a = r.get("audio") or audio_by_id.get(uid) or {}
        arr = a.get("array")
        if arr is None:
            blob = a.get("bytes")
            if blob is None:
                continue
            data, sr = sf.read(io.BytesIO(blob), dtype="float32", always_2d=True)
            audio = torch.from_numpy(data).transpose(0, 1)
        else:
            audio = torch.tensor(arr).float().unsqueeze(0)
            sr = a.get("sampling_rate") or sample_rate
        if audio.shape[0] > 1:  # downmix to mono
            audio = audio.mean(0, keepdim=True)
        if sr != sample_rate:
            audio = torchaudio.functional.resample(audio, sr, sample_rate)
        out.append((uid, (r.get("transcription") or "").strip(), audio))
    return out


def _load_fleurs_ids_texts(path: str) -> dict[str, str]:
    """Full id->transcription map (no audio decode) for VI->EN MT pairing."""
    import pyarrow.parquet as pq

    table = pq.read_table(path, columns=["id", "transcription"])
    return {
        str(r["id"]): (r.get("transcription") or "").strip() for r in table.to_pylist()
    }


def _emit_asr_items(items, mixed_dir, lang, idx, uid, transcript, audio, sample_rate):
    """Emit the SNR-sweep ASR items for one utterance (clean + noisy)."""
    for snr in SNR_LEVELS:
        for kind in NOISE_TYPES:
            if snr is None:
                wav = mixed_dir / f"{lang}_{uid}_{kind}_clean.wav"
                sf.write(str(wav), audio.transpose(0, 1).numpy(), sample_rate)
                items.append(
                    EvalItem(
                        id=f"{lang}-asr-{uid}-{kind}-clean",
                        stage="ASR",
                        language=lang,
                        direction="",
                        audio_ref=str(wav),
                        transcript_ref=transcript,
                        snr=None,
                        noise_type=kind,
                    )
                )
                continue
            noise = _synth_noise(kind, audio.shape[-1], sample_rate, seed=idx + 1)
            mixed = _mix(audio, noise, snr)
            wav = mixed_dir / f"{lang}_{uid}_{kind}_{snr:g}.wav"
            sf.write(str(wav), mixed.transpose(0, 1).numpy(), sample_rate)
            items.append(
                EvalItem(
                    id=f"{lang}-asr-{uid}-{kind}-{snr:g}",
                    stage="ASR",
                    language=lang,
                    direction="",
                    audio_ref=str(wav),
                    transcript_ref=transcript,
                    snr=snr,
                    noise_type=kind,
                )
            )


def build_lean_manifest(
    out_path: str,
    workdir: str = "eval_data",
    n_per_lang: int = 30,
    sample_rate: int = 16000,
    use_fleurs: bool = True,
) -> None:

    wd = Path(workdir)
    mixed_dir = wd / "mixed"
    mixed_dir.mkdir(parents=True, exist_ok=True)
    items: list[EvalItem] = []

    vi_path = wd / "raw" / "fleurs_vi_vn_test.parquet"
    en_path = wd / "raw" / "fleurs_en_us_test.parquet"
    if use_fleurs and vi_path.exists() and en_path.exists():
        vi = _load_fleurs(str(vi_path), n_per_lang, sample_rate)
        en_audio = _load_fleurs(str(en_path), n_per_lang, sample_rate)
        en_text_by_id = _load_fleurs_ids_texts(str(en_path))
        for idx, (uid, transcript, audio) in enumerate(vi):
            _emit_asr_items(
                items, mixed_dir, "vi", idx, uid, transcript, audio, sample_rate
            )
            en_tr = en_text_by_id.get(uid)
            if en_tr:
                items.append(
                    EvalItem(
                        id=f"vi-en-mt-{uid}",
                        stage="MT",
                        language="vi",
                        direction="vi->en",
                        input_text=transcript,
                        reference_text=en_tr,
                    )
                )
        for idx, (uid, transcript, audio) in enumerate(en_audio):
            _emit_asr_items(
                items, mixed_dir, "en", idx, uid, transcript, audio, sample_rate
            )
        print(
            f"FLEURS: added {len(vi)} VI + {len(en_audio)} EN ASR speakers "
            f"+ VI->EN MT items"
        )
    elif use_fleurs:
        print(
            f"FLEURS parquets not found in {wd / 'raw'} "
            f"-- emitting offline fallback (MT + TTS only)."
        )

    for i, (vi_text, en_text) in enumerate(GOLD_SET):
        items.append(
            EvalItem(
                id=f"gold-mt-{i:02d}",
                stage="MT",
                language="vi",
                direction="vi->en",
                input_text=vi_text,
                reference_text=en_text,
            )
        )
        items.append(
            EvalItem(
                id=f"gold-tts-{i:02d}",
                stage="TTS",
                language="en",
                direction="",
                input_text=en_text,
            )
        )

    RunManifest(items=items).to_json(out_path)
    print(
        f"Wrote {out_path} with {len(items)} items "
        f"({sum(1 for it in items if it.stage == 'ASR')} ASR, "
        f"{sum(1 for it in items if it.stage == 'MT')} MT, "
        f"{sum(1 for it in items if it.stage == 'TTS')} TTS)"
    )


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Kavi bench data prep (Phase 1)")
    ap.add_argument("--out", default="eval_manifest_v1.json")
    ap.add_argument("--workdir", default="eval_data")
    ap.add_argument("--n-per-lang", type=int, default=30)
    ap.add_argument(
        "--download-fleurs",
        action="store_true",
        help="curl FLEURS parquets first (needs working HF access)",
    )
    ap.add_argument(
        "--lang",
        action="append",
        help="limit FLEURS download to these langs (repeatable)",
    )
    ap.add_argument(
        "--no-fleurs",
        action="store_true",
        help="skip FLEURS even if present (offline fallback only)",
    )
    args = ap.parse_args()
    if args.download_fleurs:
        langs = tuple(args.lang) if args.lang else ("vi_vn", "en_us")
        download_fleurs(args.workdir, langs=langs)
    build_lean_manifest(
        args.out,
        workdir=args.workdir,
        n_per_lang=args.n_per_lang,
        use_fleurs=not args.no_fleurs,
    )


if __name__ == "__main__":
    main()
