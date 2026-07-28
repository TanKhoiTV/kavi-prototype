"""Filter eval_manifest_v1.json down to a stage subset for quick experiments."""

from __future__ import annotations

import argparse

from .schema import RunManifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Filter manifest by stage + limit")
    ap.add_argument("--manifest", default="eval_data/eval_manifest_v1.json")
    ap.add_argument("--stage", required=True, choices=["ASR", "MT", "TTS"])
    ap.add_argument("--lang", choices=["vi", "en"], help="loc them theo ngon ngu audio (ASR)")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    manifest = RunManifest.from_json(args.manifest)
    filtered = [
        it
        for it in manifest.items
        if it.stage == args.stage
        and (it.reference_text or it.transcript_ref)
        and (args.lang is None or getattr(it, "language", None) == args.lang)
    ][: args.limit]
    RunManifest(version=manifest.version, items=filtered).to_json(args.out)
    print(f"Wrote {len(filtered)} {args.stage} items (with reference) to {args.out}")


if __name__ == "__main__":
    main()