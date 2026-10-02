#!/usr/bin/env python3
"""Verify an exported Opus-MT encoder ONNX against the PyTorch reference.

Issue #116 (P1) exit check. Quantizing a broken graph produces two arms that
are *both* wrong in the same way, and the A/B then looks clean while measuring
nothing. So the fp32 graph is compared against the checkpoint it came from
before any bit-width is chosen.

The comparison runs at the fixed shape the QAIRT converter is given
(``--seq-len``), because the HTP rejects dynamic shapes (ADR-003) and padding
positions are not meaningful to compare.

Usage:
    uv run python -m bench.qnn.verify_onnx_encoder \
        --onnx-dir models/qnn/opus-mt-vi-en/opus-mt-vi-en \
        --source   models/opus-mt-vi-en-src

Exits non-zero when the graph diverges, so it can gate a build.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort

# 128 is the sequence length pinned in .kavi.yaml / the NDK runbook.
DEFAULT_SEQ_LEN = 128
DEFAULT_MAX_ABS_DIFF = 1e-3
DEFAULT_MIN_COSINE = 0.9999


def _load_manifest_texts(manifest: Path, num_samples: int) -> list[str]:
    """Read ``num_samples`` real source sentences from an eval manifest."""
    # A non-positive count would slice to nothing (crash in max() below) or,
    # when negative, drop only the last item and silently compare the rest.
    if num_samples <= 0:
        raise SystemExit("--num-samples must be a positive integer")
    items = json.loads(manifest.read_text(encoding="utf-8"))["items"]
    texts = [it["input_text"] for it in items if it.get("input_text")]
    if not texts:
        raise SystemExit(f"no input_text in {manifest}")
    return texts[:num_samples]


def compare(
    source_dir: str | Path,
    onnx_dir: str | Path,
    texts: list[str],
    seq_len: int = DEFAULT_SEQ_LEN,
    max_abs_diff: float = DEFAULT_MAX_ABS_DIFF,
    min_cosine: float = DEFAULT_MIN_COSINE,
) -> tuple[bool, list[dict[str, float]]]:
    """Return ``(passed, rows)`` comparing ONNX vs torch encoder outputs."""
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    source_dir = Path(source_dir)
    onnx_path = Path(onnx_dir) / "encoder_model.onnx"
    if not onnx_path.exists():
        raise SystemExit(f"encoder ONNX not found: {onnx_path}")

    tokenizer = AutoTokenizer.from_pretrained(str(source_dir))
    model = AutoModelForSeq2SeqLM.from_pretrained(str(source_dir)).eval()
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    rows: list[dict[str, float]] = []
    for text in texts:
        batch = tokenizer(
            text,
            padding="max_length",
            truncation=True,
            max_length=seq_len,
            return_tensors="pt",
        )
        input_ids = batch["input_ids"].to(torch.int64)
        attention_mask = batch["attention_mask"].to(torch.int64)
        with torch.no_grad():
            reference = model.get_encoder()(
                input_ids=input_ids, attention_mask=attention_mask
            ).last_hidden_state.numpy()
        produced = session.run(
            None,
            {
                "input_ids": input_ids.numpy(),
                "attention_mask": attention_mask.numpy(),
            },
        )[0]

        live = int(attention_mask.sum())  # padding rows are not comparable
        ref_live = reference[0, :live].ravel()
        got_live = produced[0, :live].ravel()
        rows.append(
            {
                "tokens": float(live),
                "max_abs_diff": float(np.abs(ref_live - got_live).max()),
                "cosine": float(
                    ref_live
                    @ got_live
                    / (np.linalg.norm(ref_live) * np.linalg.norm(got_live))
                ),
                "finite": float(np.isfinite(produced).all()),
            }
        )

    passed = all(
        row["finite"] == 1.0
        and row["max_abs_diff"] < max_abs_diff
        and row["cosine"] > min_cosine
        for row in rows
    )
    return passed, rows


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="models/opus-mt-vi-en-src",
        help="Pinned checkpoint snapshot the ONNX was exported from",
    )
    parser.add_argument(
        "--onnx-dir",
        default="models/qnn/opus-mt-vi-en/opus-mt-vi-en",
        help="Directory holding encoder_model.onnx",
    )
    parser.add_argument(
        "--manifest",
        default="eval_data/mt_vi_en_eval_manifest.json",
        help="Eval manifest supplying real source sentences",
    )
    parser.add_argument(
        "--num-samples", type=int, default=5, help="Sentences to compare"
    )
    parser.add_argument(
        "--seq-len",
        type=int,
        default=DEFAULT_SEQ_LEN,
        help="Fixed sequence length; must match the QAIRT --input-dims",
    )
    parser.add_argument(
        "--max-abs-diff",
        type=float,
        default=DEFAULT_MAX_ABS_DIFF,
        help="Per-element tolerance vs the PyTorch reference",
    )
    parser.add_argument(
        "--min-cosine",
        type=float,
        default=DEFAULT_MIN_COSINE,
        help="Minimum cosine similarity vs the PyTorch reference",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    texts = _load_manifest_texts(Path(args.manifest), args.num_samples)
    passed, rows = compare(
        args.source,
        args.onnx_dir,
        texts,
        seq_len=args.seq_len,
        max_abs_diff=args.max_abs_diff,
        min_cosine=args.min_cosine,
    )

    print(
        f"Comparing {args.onnx_dir}/encoder_model.onnx vs {args.source} @ seq_len={args.seq_len}"
    )
    for row in rows:
        print(
            f"  tokens={int(row['tokens']):3d}  max|d|={row['max_abs_diff']:.2e}  "
            f"cos={row['cosine']:.8f}  finite={bool(row['finite'])}"
        )
    worst_diff = max(row["max_abs_diff"] for row in rows)
    worst_cos = min(row["cosine"] for row in rows)
    print(f"\nworst max|d| = {worst_diff:.3e}   worst cos = {worst_cos:.8f}")
    if passed:
        print("VERDICT: PASS — the ONNX encoder matches the PyTorch reference")
        return 0
    print("VERDICT: FAIL — the graph diverges from the checkpoint; do not quantize")
    return 1


if __name__ == "__main__":
    sys.exit(main())
