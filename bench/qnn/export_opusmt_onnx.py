#!/usr/bin/env python3
"""Export Helsinki-NLP Opus-MT vi↔en models to ONNX via HuggingFace Optimum.

Produces separate encoder + decoder ONNX graphs for each translation direction,
ready for the QAIRT conversion pipeline (qnn-onnx-converter → model lib → HTP
v73 context binary).

Usage:
    uv run python -m bench.qnn.export_opusmt_onnx \
        --model Helsinki-NLP/opus-mt-vi-en \
        --output models/qnn/opus-mt-vi-en/

    uv run python -m bench.qnn.export_opusmt_onnx \
        --model Helsinki-NLP/opus-mt-en-vi \
        --output models/qnn/opus-mt-en-vi/

    # Both directions at once:
    uv run python -m bench.qnn.export_opusmt_onnx --both --output models/qnn/

Dependencies (install via uv):
    uv pip install transformers optimum[onnx] datasets sentencepiece
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from datasets import load_dataset  # pyright: ignore[reportMissingImports]
    from optimum.onnxruntime import (  # pyright: ignore[reportMissingImports]
        ORTModelForSeq2SeqLM,
    )
    from transformers import AutoConfig, AutoTokenizer, PreTrainedTokenizer
except ImportError as exc:
    print(
        f"Missing dependency: {exc}\n"
        "Install with: uv pip install transformers optimum[onnx] datasets sentencepiece",
        file=sys.stderr,
    )
    sys.exit(1)

# ── calibration helpers ──────────────────────────────────────────────────────


def _build_calibration_sequences(
    tokenizer_src: PreTrainedTokenizer,
    tokenizer_tgt: PreTrainedTokenizer | None = None,
    num_samples: int = 64,
    max_length: int = 128,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate calibration token sequences from FLEURS VI/EN text.

    Draws real sentences from the FLEURS train split (vi_vn for vi→en,
    en_us for en→vi) and tokenizes them.  Falls back to synthetic sequences
    if FLEURS is not available.
    """
    import numpy as np

    rng = np.random.default_rng(seed)

    # Try to load real FLEURS text first
    try:
        ds = load_dataset("google/fleurs", "all", split="train", trust_remote_code=True)
        # Convert to list for indexed access (IterableDataset does not support [])
        lang_field = "vi_vn"  # default; caller can override
        fleurs_list = list(ds)
        texts: list[str] = []
        for item in fleurs_list:
            val = item.get(lang_field, "")
            if isinstance(val, str) and val.strip():
                texts.append(val.strip())
        if len(texts) >= num_samples and tokenizer_tgt is not None:
            # Use paired data for calibration
            return _tokenize_pairs(
                texts[:num_samples], tokenizer_src, tokenizer_tgt, max_length
            )
        elif len(texts) >= num_samples:
            # Source-only
            return _tokenize_source(texts[:num_samples], tokenizer_src, max_length)
    except Exception:
        pass

    # Fallback: synthetic token sequences matching the model's vocab distribution
    print(
        "Warning: FLEURS not available; using synthetic calibration data.",
        file=sys.stderr,
    )
    vocab_size = tokenizer_src.vocab_size
    _pad = tokenizer_src.pad_token_id
    pad_id: int = _pad if isinstance(_pad, int) else 0
    _eos = tokenizer_src.eos_token_id
    eos_id: int = _eos if isinstance(_eos, int) else 1

    if tokenizer_tgt is not None:
        return [
            {
                "input_ids": _rand_seq(rng, vocab_size, max_length, pad_id, eos_id),
                "attention_mask": [1] * (max_length // 2) + [0] * (max_length // 2),
                "labels": _rand_seq(rng, vocab_size, max_length, pad_id, eos_id),
                "decoder_input_ids": _rand_seq(
                    rng, vocab_size, max_length, pad_id, eos_id
                ),
            }
            for _ in range(num_samples)
        ]
    return [
        {
            "input_ids": _rand_seq(rng, vocab_size, max_length, pad_id, eos_id),
            "attention_mask": [1] * (max_length // 2) + [0] * (max_length // 2),
        }
        for _ in range(num_samples)
    ]


def _rand_seq(
    rng: Any, vocab_size: int, length: int, pad_id: int, eos_id: int
) -> list[int]:
    """Generate a random token sequence with plausible length distribution."""
    seq_len = rng.integers(8, length - 1)
    tokens = rng.integers(3, vocab_size - 10, size=seq_len).tolist()
    tokens[-1] = eos_id
    tokens += [pad_id] * (length - seq_len)
    return tokens[:length]


def _tokenize_source(
    texts: list[str], tokenizer: PreTrainedTokenizer, max_length: int
) -> list[dict[str, Any]]:
    """Tokenize source-only calibration texts."""
    enc = tokenizer(
        texts,
        padding="max_length",
        truncation=True,
        max_length=max_length,
        return_tensors=None,
    )
    return [
        {
            "input_ids": enc["input_ids"][i],
            "attention_mask": enc["attention_mask"][i],
        }
        for i in range(len(texts))
    ]


def _tokenize_pairs(
    src_texts: list[str],
    tokenizer_src: PreTrainedTokenizer,
    tokenizer_tgt: PreTrainedTokenizer,
    max_length: int,
) -> list[dict[str, Any]]:
    """Tokenize source + target calibration pairs."""
    src = tokenizer_src(
        src_texts,
        padding="max_length",
        truncation=True,
        max_length=max_length,
        return_tensors=None,
    )
    tgt = tokenizer_tgt(
        src_texts,
        padding="max_length",
        truncation=True,
        max_length=max_length,
        return_tensors=None,
    )
    return [
        {
            "input_ids": src["input_ids"][i],
            "attention_mask": src["attention_mask"][i],
            "labels": tgt["input_ids"][i],
            "decoder_input_ids": tgt["input_ids"][i][:-1] + [0],
        }
        for i in range(len(src_texts))
    ]


# ── export logic ─────────────────────────────────────────────────────────────


def export_model(
    model_id: str,
    output_dir: str | Path,
    calibration_samples: int = 64,
    max_length: int = 128,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Export an Opus-MT model to ONNX using Optimum.

    Returns a dict with paths to the exported artifacts.
    """
    output_dir = Path(output_dir)
    if output_dir.exists() and not overwrite:
        raise FileExistsError(
            f"{output_dir} already exists; use --overwrite or remove it first"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading tokenizer and config for {model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    config = AutoConfig.from_pretrained(model_id)

    # Determine the model direction for calibration
    is_vi_en = "vi-en" in model_id or "opus-mt-vi-en" in model_id

    print(f"Exporting {model_id} to ONNX (task=text2text-generation-with-past)...")
    model = ORTModelForSeq2SeqLM.from_pretrained(
        model_id,
        export=True,
        task="text2text-generation-with-past",
    )

    # Save ONNX files in the standard format:
    #   encoder_model.onnx
    #   decoder_model.onnx
    #   decoder_with_past_model.onnx  (optional, for autoregressive)
    model.save_pretrained(str(output_dir))

    # Also save the tokenizer and config alongside the ONNX artifacts
    tokenizer.save_pretrained(str(output_dir))
    config.save_pretrained(str(output_dir))

    # Build calibration data for quantization
    print("Generating calibration data...")
    tgt_tokenizer = tokenizer  # same tokenizer for both sides in Opus-MT
    calib_data = _build_calibration_sequences(
        tokenizer_src=tokenizer,
        tokenizer_tgt=tgt_tokenizer,
        num_samples=calibration_samples,
        max_length=max_length,
    )

    calib_path = output_dir / "calibration_data.jsonl"
    with open(calib_path, "w", encoding="utf-8") as f:
        for sample in calib_data:
            f.write(json.dumps(sample) + "\n")
    print(f"Wrote {len(calib_data)} calibration samples to {calib_path}")

    # List exported artifacts
    artifacts = {
        "model_id": model_id,
        "output_dir": str(output_dir),
        "encoder": str(output_dir / "encoder_model.onnx"),
        "decoder": str(output_dir / "decoder_model.onnx"),
        "decoder_with_past": str(output_dir / "decoder_with_past_model.onnx"),
        "config": str(output_dir / "config.json"),
        "tokenizer_files": sorted(
            p.name for p in output_dir.iterdir() if p.suffix in (".json", ".model")
        ),
        "calibration_data": str(calib_path),
        "direction": "vi->en" if is_vi_en else "en->vi",
    }

    # Validate that files exist
    for key in ("encoder", "decoder", "config"):
        path = Path(artifacts[key])
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            artifacts[f"{key}_size_mb"] = round(size_mb, 2)
            print(f"  {key}: {path.name} ({size_mb:.2f} MB)")
        else:
            print(f"  WARNING: {key} not found at {path}")

    return artifacts


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Opus-MT vi↔en models to ONNX for QNN conversion",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="HuggingFace model ID (e.g. Helsinki-NLP/opus-mt-vi-en)",
    )
    parser.add_argument(
        "--output",
        default="models/qnn/opus-mt",
        help="Output directory for ONNX artifacts",
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help="Export both vi→en and en→vi directions",
    )
    parser.add_argument(
        "--calibration-samples",
        type=int,
        default=64,
        help="Number of calibration samples to generate (default: 64)",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=128,
        help="Max sequence length for export/calibration (default: 128)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output directories",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if args.both:
        models = [
            ("Helsinki-NLP/opus-mt-vi-en", "opus-mt-vi-en"),
            ("Helsinki-NLP/opus-mt-en-vi", "opus-mt-en-vi"),
        ]
        results = {}
        for model_id, subdir in models:
            out = Path(args.output) / subdir
            try:
                results[model_id] = export_model(
                    model_id,
                    out,
                    calibration_samples=args.calibration_samples,
                    max_length=args.max_length,
                    overwrite=args.overwrite,
                )
            except FileExistsError:
                print(f"Skipping {model_id}: {out} exists (use --overwrite to replace)")
            except Exception as exc:
                print(f"Error exporting {model_id}: {exc}", file=sys.stderr)
                results[model_id] = {"error": str(exc)}

        print("\n=== Summary ===")
        for model_id, info in results.items():
            if "error" in info:
                print(f"  {model_id}: FAILED - {info['error']}")
            else:
                print(f"  {model_id}: OK -> {info['output_dir']}")
    elif args.model:
        export_model(
            args.model,
            args.output,
            calibration_samples=args.calibration_samples,
            max_length=args.max_length,
            overwrite=args.overwrite,
        )
    else:
        print(
            "Provide --model or --both.\n"
            "  uv run python -m bench.qnn.export_opusmt_onnx --both --output models/qnn/",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
