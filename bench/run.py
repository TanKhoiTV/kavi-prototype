"""Host-side v0 runner: load manifest -> fan out candidates -> score -> table."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .registry import build_candidate, default_candidate_id_for_stage
from .schema import RunManifest, StageResult
from .scorer import score_item
from .smoke_sample import build_smoke_manifest


def audio_duration(path: str | None) -> float | None:
    if not path or not Path(path).exists():
        return None
    try:
        import soundfile as sf

        with sf.SoundFile(path) as f:
            return f.frames / f.samplerate
    except Exception:  # noqa: BLE001
        return None


def run_manifest(
    manifest: RunManifest, out_dir: Path, candidate_filter: str | None
) -> list[dict]:
    records: list[dict] = []
    for item in manifest.items:
        cid = item.candidate_id or default_candidate_id_for_stage(item.stage)
        if candidate_filter and cid != candidate_filter:
            continue
        try:
            candidate = build_candidate(item)
            if hasattr(candidate, "out_dir"):
                candidate.out_dir = str(out_dir / "outputs")
            result = candidate.run(item)
        except (RuntimeError, ValueError, OSError, KeyError, ImportError) as exc:
            result = StageResult(
                candidate_id=cid or "unknown",
                item_id=item.id,
                stage=item.stage,
                error=f"{type(exc).__name__}: {exc}",
            )

        duration = None
        if item.stage == "ASR":
            duration = audio_duration(item.audio_ref)
        elif item.stage == "TTS":
            duration = audio_duration(result.output_audio_path)

        metrics = score_item(item, result, duration)
        records.append(
            {
                "item": asdict(item),
                "result": asdict(result),
                "metrics": asdict(metrics),
            }
        )
    return records


def print_table(records: list[dict]) -> None:
    headers = [
        "item",
        "stage",
        "cand",
        "lat_s",
        "ram_mb",
        "WER",
        "BLEU",
        "RTF",
        "out/err",
    ]
    rows = []
    for rec in records:
        it, res, met = rec["item"], rec["result"], rec["metrics"]
        rows.append(
            [
                it["id"],
                it["stage"],
                res["candidate_id"].split("-")[0],
                f"{res['latency_s']:.2f}",
                f"{res['peak_ram_mb']:.0f}" if res.get("peak_ram_mb") else "-",
                f"{met['wer']:.3f}" if met.get("wer") is not None else "-",
                f"{met['bleu']:.1f}" if met.get("bleu") is not None else "-",
                f"{met['rtf']:.2f}" if met.get("rtf") is not None else "-",
                (
                    res.get("output_audio_path")
                    or res.get("error")
                    or res.get("output_text")
                    or ""
                )[:36],
            ]
        )
    if not rows:
        print("(no items matched)")
        return
    widths = [
        max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))
    ]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths, strict=True))
    print(line)
    print("-" * len(line))
    for row in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(row, widths, strict=True)))


def main() -> None:
    ap = argparse.ArgumentParser(description="Kavi benchmark harness (host-side v0)")
    ap.add_argument("--manifest", help="path to eval_manifest_v1.json")
    ap.add_argument(
        "--smoke", action="store_true", help="generate + run a tiny offline sample"
    )
    ap.add_argument("--out", default="bench-results", help="output directory")
    ap.add_argument("--candidate", help="only run this candidate_id")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.smoke:
        manifest = build_smoke_manifest(workdir=out_dir / "smoke-inputs")
    elif args.manifest:
        manifest = RunManifest.from_json(args.manifest)
    else:
        ap.error("either --manifest PATH or --smoke required")

    records = run_manifest(manifest, out_dir, args.candidate)
    (out_dir / "run_results.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print_table(records)
    print(f"\nWrote {out_dir / 'run_results.json'}")


if __name__ == "__main__":
    main()
