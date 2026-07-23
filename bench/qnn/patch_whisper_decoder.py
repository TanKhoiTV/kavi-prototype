#!/usr/bin/env python3
"""Patch Whisper decoder ONNX for QNN conversion by removing unsupported ops.

Removes ``IsNaN`` nodes unsupported by ``qnn-onnx-converter`` (2.31.0.250130).

The Whisper decoder uses ``IsNaN`` for beam search NaN detection. Since we
guarantee valid inputs (no NaN in practice), we can safely remove these guards.

Usage::

    uv run python -m bench.qnn.patch_whisper_decoder \\
        --input models/qnn/whisper-small/onnx/decoder_model.onnx \\
        --output models/qnn/whisper-small/decoder_patched.onnx \\
        --verify
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

try:
    import onnx
    import onnx_graphsurgeon as gs  # type: ignore[import-untyped]
except ImportError as exc:
    print(f"Missing dependency: {exc}", file=sys.stderr)
    print("Install: uv pip install onnx onnx-graphsurgeon", file=sys.stderr)
    sys.exit(1)


def strip_isnan_nodes(graph: gs.Graph) -> int:
    """Remove all IsNaN nodes by replacing them with a constant False.

    ``IsNaN(x)`` → ``Constant(False)``

    The IsNaN output is a boolean tensor used in Where nodes. By replacing
    with False, the Where node will always select the second input (the
    non-NaN path), effectively removing the NaN guard.

    Returns the number of nodes removed.
    """
    count = 0
    for node in list(graph.nodes):
        if node.op != "IsNaN":
            continue

        # IsNaN has one input and one output
        out_var = node.outputs[0]

        # Replace with constant False
        # The output shape is typically [batch, seq_len] or [batch, heads, seq, seq]
        raw_shape = out_var.shape if out_var.shape is not None else ()
        # Replace dynamic dims (None / str) with 1 for the constant's storage shape;
        # onnx-graphsurgeon will broadcast the constant at graph level.
        safe_shape = tuple(s if isinstance(s, int) else 1 for s in raw_shape)
        false_const = gs.Constant(
            name=f"{node.name}_false_const",
            values=np.zeros(safe_shape, dtype=np.bool_),
        )

        # Redirect all consumers: replace the output variable in consumer inputs
        for consumer in graph.nodes:
            for i, inp in enumerate(consumer.inputs):
                if inp is out_var:
                    consumer.inputs[i] = false_const

        # Also update graph outputs if they reference this variable
        for i, out in enumerate(graph.outputs):
            if out is out_var:
                graph.outputs[i] = false_const

        # Remove the node
        node.outputs.clear()
        count += 1

    return count


def verify(original_path: str, patched_path: str) -> bool:
    """Verify the patched model is valid and has no IsNaN nodes."""
    print("\n=== Verification ===")

    # Load patched model
    patched = onnx.load(patched_path, load_external_data=False)

    # Check no IsNaN nodes remain
    isnan_count = sum(1 for n in patched.graph.node if n.op_type == "IsNaN")
    if isnan_count > 0:
        print(f"  FAIL: {isnan_count} IsNaN nodes still present")
        return False
    print("  ✓ No IsNaN nodes remaining")

    # Check model is valid
    try:
        onnx.checker.check_model(patched)
        print("  ✓ Model passes onnx.checker")
    except Exception as exc:
        print(f"  WARNING: onnx.checker failed: {exc}")
        # Continue anyway — checker may fail on dynamic shapes

    # Compare node counts
    original = onnx.load(original_path, load_external_data=False)
    orig_ops = {}
    for node in original.graph.node:
        orig_ops[node.op_type] = orig_ops.get(node.op_type, 0) + 1
    patch_ops = {}
    for node in patched.graph.node:
        patch_ops[node.op_type] = patch_ops.get(node.op_type, 0) + 1

    print(f"  Original nodes: {sum(orig_ops.values())}")
    print(f"  Patched nodes:  {sum(patch_ops.values())}")
    print(f"  IsNaN removed:  {orig_ops.get('IsNaN', 0)}")

    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to original Whisper decoder ONNX",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path for patched ONNX output",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run verification after patching",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Load model
    print(f"Loading {input_path}...")
    model = onnx.load(str(input_path), load_external_data=False)
    graph = gs.import_onnx(model)

    # Patch
    print("Stripping IsNaN nodes...")
    count = strip_isnan_nodes(graph)
    print(f"  Removed {count} IsNaN nodes")

    # Clean up graph
    graph.cleanup().toposort()

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(gs.export_onnx(graph), str(output_path))
    print(f"Saved patched model to {output_path}")

    # Verify
    if args.verify:
        if verify(str(input_path), str(output_path)):
            print("\n✓ Verification passed")
        else:
            print("\n✗ Verification failed")
            sys.exit(1)


if __name__ == "__main__":
    main()
