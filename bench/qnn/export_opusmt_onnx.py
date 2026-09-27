#!/usr/bin/env python3
"""Export Helsinki-NLP Opus-MT vi↔en models to ONNX via HuggingFace Optimum.

Produces separate encoder + decoder ONNX graphs for each translation direction,
ready for the QAIRT conversion pipeline (qnn-onnx-converter → model lib → HTP
v73 context binary).

Usage:
    uv run python -m bench.qnn.export_opusmt_onnx \
        --model Helsinki-NLP/opus-mt-vi-en \
        --output models/qnn/opus-mt-vi-en

    uv run python -m bench.qnn.export_opusmt_onnx \
        --model Helsinki-NLP/opus-mt-en-vi \
        --output models/qnn/opus-mt-en-vi

    # Both directions at once:
    uv run python -m bench.qnn.export_opusmt_onnx --both --output models/qnn/

Calibration data is NOT produced here. Input lists for the QNN converter come
from ``bench.qnn.generate_calibration_lists``, which draws from the pinned
FLEURS data — an earlier version of this script tried to build its own and
silently fell back to synthetic sequences, which ADR-026 forbids.

Dependencies (install via uv):
    uv pip install transformers optimum[onnx] sentencepiece
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    from optimum.onnxruntime import (  # pyright: ignore[reportMissingImports]
        ORTModelForSeq2SeqLM,
    )
    from transformers import AutoConfig, AutoTokenizer
except ImportError as exc:
    print(
        f"Missing dependency: {exc}\n"
        "Install with: uv pip install transformers optimum[onnx] sentencepiece",
        file=sys.stderr,
    )
    sys.exit(1)


# ── graph inspection ────────────────────────────────────────────────────────


def _describe(value_info: Any, model: Any) -> str:
    """Format one graph input/output as ``name [dims] dtype``."""
    import onnx

    tensor_type = value_info.type.tensor_type
    dims = [d.dim_param or d.dim_value for d in tensor_type.shape.dim]
    dtype = onnx.TensorProto.DataType.Name(tensor_type.elem_type)
    if any(not isinstance(d, int) for d in dims):
        # HTP rejects dynamic shapes (ADR-003): the converter needs a static
        # --input_dim for every axis.
        return f"{value_info.name} {dims} {dtype}  <-- DYNAMIC, HTP rejects"
    return f"{value_info.name} {dims} {dtype}"


def report_onnx_io(path: Path) -> None:
    """Print the encoder/decoder input contract that the QAIRT step must pin.

    The names and dims printed here are exactly what ``--input-name`` and
    ``--input-dims`` need in ``convert_to_qnn.sh`` (issue #116, P1 → P3).
    """
    import onnx

    model = onnx.load(str(path), load_external_data=False)
    initializers = {i.name for i in model.graph.initializer}
    print(f"  graph I/O for {path.name}:")
    for value_info in model.graph.input:
        if value_info.name in initializers:
            continue  # initializers are weights, not runtime inputs
        print(f"    in  {_describe(value_info, model)}")
    for value_info in model.graph.output:
        print(f"    out {_describe(value_info, model)}")


# ── export logic ─────────────────────────────────────────────────────────────


def export_model(
    model_id: str,
    output_dir: str | Path,
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

    print(f"Exporting {model_id} to ONNX (text2text-generation-with-past)...")
    # No task= argument: since optimum 2.x the task is inferred from the class
    # and passing it raises ValueError.
    #
    # Resolve to a local snapshot when one is given. Pointing at the pinned
    # directory (make models) rather than the Hub ID keeps the export on the
    # verified revision and avoids picking up the repo's tf_model.h5, which
    # transformers tries to load and fails on without TensorFlow installed.
    model = ORTModelForSeq2SeqLM.from_pretrained(model_id, export=True)

    # Save ONNX files in the standard format:
    #   encoder_model.onnx
    #   decoder_model.onnx
    #   decoder_with_past_model.onnx  (optional, for autoregressive)
    model.save_pretrained(str(output_dir))

    # Also save the tokenizer and config alongside the ONNX artifacts
    tokenizer.save_pretrained(str(output_dir))
    config.save_pretrained(str(output_dir))

    # Calibration input lists are a separate concern: they must come from real
    # data (ADR-026), so they are built by bench.qnn.generate_calibration_lists
    # rather than here. A synthetic fallback in this script once hid that.
    print(
        "Calibration input lists are not generated here. Build them with:\n"
        "  uv run python -m bench.qnn.generate_calibration_lists \\\n"
        "      --manifest eval_data/eval_manifest_v1.json --out-dir models/qnn/"
    )

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
        "direction": "vi->en" if is_vi_en else "en->vi",
    }

    # Validate that files exist
    for key in ("encoder", "decoder", "config"):
        path = Path(artifacts[key])
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            artifacts[f"{key}_size_mb"] = round(size_mb, 2)
            print(f"  {key}: {path.name} ({size_mb:.2f} MB)")
            if key in ("encoder", "decoder") and path.suffix == ".onnx":
                try:
                    report_onnx_io(path)
                except Exception as exc:  # inspection is diagnostic only
                    print(f"  WARNING: could not read graph I/O: {exc}")
        else:
            print(f"  WARNING: {key} not found at {path}")

    return artifacts


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        # ASCII only: the Windows console defaults to cp1252 and cannot encode
        # the arrow, which made --help crash with UnicodeEncodeError.
        description="Export Opus-MT vi-en models to ONNX for QNN conversion",
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
        help="Export both vi->en and en->vi directions",
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
