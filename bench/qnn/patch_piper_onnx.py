#!/usr/bin/env python3
"""Patch Piper TTS ONNX for QNN conversion by replacing stochastic ops.

Removes two obstacles to ``qnn-onnx-converter`` (2.31.0.250130) support:

  1. **RandomNormalLike nodes** → ConstantOfShape with zero value.
  2. **Data-dependent output length** → fixed T_FIXED via duration-sum rescale.

The surgery works entirely on the ONNX graph using onnx-graphsurgeon. No
re-export or re-training is required.

Usage::

    uv run python -m bench.qnn.patch_piper_onnx \\
        --input voices/en_US-lessac-medium.onnx \\
        --output models/qnn/piper-en/piper_patched.onnx \\
        --verify

    # Custom fixed output length (latent frames):
    uv run python -m bench.qnn.patch_piper_onnx \\
        --input voices/en_US-lessac-medium.onnx \\
        --output models/qnn/piper-en/piper_patched.onnx \\
        --t-fixed 512
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np

try:
    import onnx
    import onnx_graphsurgeon as gs  # type: ignore[import-untyped]
except ImportError as exc:
    print(f"Missing dependency: {exc}", file=sys.stderr)
    print("Install: uv pip install onnx onnx-graphsurgeon", file=sys.stderr)
    sys.exit(1)


# ── surgery 1: deterministic noise ──────────────────────────────────────


def replace_random_normal_like(graph: gs.Graph) -> int:
    """Replace every ``RandomNormalLike`` node with a zero ``Mul``.

    ``RandomNormalLike(reference_tensor)`` → ``Mul(reference_tensor, 0)``

    ``RandomNormalLike`` takes a reference tensor whose *shape* determines
    the output shape.  ``Mul(ref, 0)`` produces a zero tensor of the *same*
    shape, preserving the downstream graph topology.

    Returns the number of nodes modified.
    """
    count = 0
    for node in list(graph.nodes):
        if node.op != "RandomNormalLike":
            continue

        ref_tensor = node.inputs[0]
        orig_out = node.outputs[0]

        zero_const = gs.Constant(
            name=f"{node.name}_zero_const",
            values=np.array(0.0, dtype=np.float32),
        )
        node.op = "Mul"
        node.inputs = [ref_tensor, zero_const]  # type: ignore[assignment]
        node.outputs = [orig_out]  # type: ignore[assignment]
        node.attrs.clear()
        count += 1

    return count


# ── surgery 2: fixed output length ──────────────────────────────────────


def pin_duration_to_fixed(graph: gs.Graph, t_fixed: int) -> bool:
    """Rescale predicted durations so total sum ≈ *t_fixed* latent frames.

    The Piper duration predictor outputs per-phoneme durations in latent
    frames (shape ``[batch, 1, num_phonemes]``).  These are Ceil'd, summed
    via ``ReduceSum`` (axes ``[1, 2]``) to get total length, then used in a
    ``CumSum`` mask and the decoder.

    This function inserts a **separate** ReduceSum on the raw (pre-Ceil)
    durations to compute the scale factor, avoiding a feedback cycle::

        scale      = T_FIXED / ReduceSum(raw_durations)   # [batch]
        scaled     = raw_durations * Unsqueeze(scale)      # [batch, 1, phonemes]

    Then re-wires ``Ceil``'s input from raw durations to scaled durations.
    The existing ``ReduceSum`` (on Ceil'd values) continues to feed the
    downstream mask/decoder with the actual Ceil'd total (≈ T_FIXED).

    Returns ``True`` if the patch was applied.
    """
    ceil_node = _node_by_name(graph, "/Ceil")
    rs_node = _node_by_name(graph, "/ReduceSum")
    if ceil_node is None or rs_node is None:
        print(
            "  WARNING: duration-pathing landmarks not found — skipping pinning",
            file=sys.stderr,
        )
        return False

    raw_durations = ceil_node.inputs[0]  # /Mul_1_output_0  [batch, 1, num_phonemes]

    # ---- Create a separate ReduceSum on RAW (pre-Ceil) durations ----
    # Using the same axes [1, 2] as the existing ReduceSum node
    axes_const_raw = gs.Constant(
        name="duration_reduce_axes",
        values=np.array([1, 2], dtype=np.int64),
    )
    raw_sum_var = gs.Variable(
        name="raw_duration_sum",
        dtype=np.float32,
        shape=raw_durations.shape[:1],  # [batch]
    )
    new_rs_node = gs.Node(
        op="ReduceSum",
        name="/duration/ReduceSum_raw",
        inputs=[raw_durations, axes_const_raw],
        outputs=[raw_sum_var],
    )
    new_rs_node.attrs["keepdims"] = 0  # match original Behavior

    # 1. T_FIXED constant (float32)
    t_fixed_const = gs.Constant(
        name="duration_T_FIXED",
        values=np.array(float(t_fixed), dtype=np.float32),
    )

    # 2. Div: scale = T_FIXED / ReduceSum(raw_durations)  (shape [batch])
    scale_var = gs.Variable(
        name="duration_scale",
        dtype=np.float32,
        shape=raw_durations.shape[:1],  # [batch]
    )
    div_node = gs.Node(
        op="Div",
        name="/duration/Div",
        inputs=[t_fixed_const, raw_sum_var],
        outputs=[scale_var],
    )

    # 3. Unsqueeze(scale, axes=[1, 2])  →  [batch, 1, 1]
    scale_unsq = gs.Variable(
        name="duration_scale_unsq",
        dtype=np.float32,
        shape=[raw_durations.shape[0], 1, 1],
    )
    axes_const = gs.Constant(
        name="duration_axes_12",
        values=np.array([1, 2], dtype=np.int64),
    )
    unsq_node = gs.Node(
        op="Unsqueeze",
        name="/duration/Unsqueeze",
        inputs=[scale_var, axes_const],
        outputs=[scale_unsq],
    )

    # 4. Mul(raw_durations, scale_unsq) → scaled_durations
    scaled_dur = gs.Variable(
        name="scaled_durations",
        dtype=np.float32,
        shape=raw_durations.shape,
    )
    mul_node = gs.Node(
        op="Mul",
        name="/duration/Mul_scaled",
        inputs=[raw_durations, scale_unsq],
        outputs=[scaled_dur],
    )

    # 5. Wire new nodes into graph
    graph.nodes.extend(  # type: ignore[attr-defined]
        [new_rs_node, div_node, unsq_node, mul_node]
    )

    # 6. Re-wire Ceil's input from raw → scaled
    ceil_node.inputs[0] = scaled_dur
    return True


# ── helpers ──────────────────────────────────────────────────────────────


def _node_by_name(graph: gs.Graph, name: str) -> gs.Node | None:
    for n in graph.nodes:
        if n.name == name:
            return n
    return None


# ── summary ──────────────────────────────────────────────────────────────


def print_summary(graph: gs.Graph, model: onnx.ModelProto) -> None:
    """Print input/output shapes, node counts, and remaining unsupported ops."""
    print("\n=== Patched model summary ===")
    print(f"  Nodes: {len(graph.nodes)}")
    print(f"  Inputs: {len(graph.inputs)}")
    for inp in graph.inputs:
        print(f"    {inp.name}: shape={inp.shape}, dtype={inp.dtype}")  # type: ignore[union-attr]
    for out in graph.outputs:
        print(f"    output: {out.name}: shape={out.shape}, dtype={out.dtype}")  # type: ignore[union-attr]

    op_counts: Counter[str] = Counter(n.op for n in graph.nodes)
    print(f"  Unique ops: {len(op_counts)}")
    for op, cnt in sorted(op_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    {op}: {cnt}")
    if len(op_counts) > 10:
        print(f"    … ({len(op_counts) - 10} more types)")

    unsupported = [
        op
        for op in op_counts
        if op in ("RandomNormalLike", "RandomNormal", "RandomUniformLike")
    ]
    if unsupported:
        print(f"  ⚠️  Unsupported op(s) remain: {unsupported}")
    else:
        print("  ✅ All RandomNormalLike ops replaced")


# ── verification ─────────────────────────────────────────────────────────


def _build_dummy_feed(session) -> dict[str, np.ndarray]:  # onnxruntime.InferenceSession
    """Build a plausible dummy feed dict from session input metadata."""
    feed: dict[str, np.ndarray] = {}
    for inp in session.get_inputs():
        shape = list(inp.shape)
        if len(shape) == 0:
            shape = [1]
        if shape[0] in (0, "batch_size", None):
            shape[0] = 1
        for i, s in enumerate(shape):
            if not isinstance(s, int) or s <= 0:
                shape[i] = 30  # fallback dim

        # ONNX tensor type string → numpy dtype
        type_str = str(inp.type)
        if "int64" in type_str:
            dt = np.int64
        elif "int32" in type_str:
            dt = np.int32
        elif "float" in type_str:
            dt = np.float32
        else:
            dt = np.float32

        if "length" in inp.name:
            feed[inp.name] = np.random.randint(1, 30, size=tuple(shape), dtype=np.int64)
        elif "scales" in inp.name:
            feed[inp.name] = np.array([1.0, 0.667, 0.8], dtype=np.float32)
        elif dt == np.int64:
            # Phoneme IDs — small positive integers
            feed[inp.name] = np.random.randint(0, 50, size=tuple(shape), dtype=np.int64)
        else:
            feed[inp.name] = np.random.randn(*shape).astype(dt)
    return feed


def verify_with_ort(input_path: Path, output_path: Path) -> bool:
    """Run inference on original and patched models, compare output shapes."""
    try:
        import onnxruntime as ort  # type: ignore[import-untyped]
    except ImportError:
        print("  SKIP: onnxruntime not available for verification", file=sys.stderr)
        return False

    print("\n=== Verification ===")

    for tag, path in [("Original", input_path), ("Patched", output_path)]:
        try:
            session = ort.InferenceSession(
                str(path), providers=["CPUExecutionProvider"]
            )
        except Exception as exc:
            print(f"  ERROR loading {tag}: {exc}", file=sys.stderr)
            return False

        feed = _build_dummy_feed(session)

        try:
            out = session.run(None, feed)
        except Exception as exc:
            print(f"  ERROR running {tag}: {exc}", file=sys.stderr)
            return False

        print(f"  {tag}: {len(out)} output(s)")
        for i, o in enumerate(out):
            print(
                f"    [{i}] shape={o.shape}  dtype={o.dtype}  "
                f"range=[{o.min():.4f}, {o.max():.4f}]"
            )

    # Cross-check shape compatibility with identical feed
    print("\n  --- Cross-check output shapes ---")
    try:
        s1 = ort.InferenceSession(str(input_path), providers=["CPUExecutionProvider"])
        s2 = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
        feed = _build_dummy_feed(s1)
        o1 = s1.run(None, feed)
        o2 = s2.run(None, feed)
    except Exception as exc:
        print(f"  ERROR during cross-check: {exc}", file=sys.stderr)
        return False

    all_ok = True
    for i, (a, b) in enumerate(zip(o1, o2, strict=True)):
        if a.shape != b.shape:
            print(f"  ⚠️  Output [{i}] shape mismatch: {a.shape} vs {b.shape}")
            all_ok = False
        else:
            print(f"  ✅ Output [{i}] shape OK: {a.shape}")

    print(f"\n  {'✅ All output shapes match' if all_ok else '⚠️  Shape mismatch(es)'}")
    return all_ok


# ── main ─────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Patch Piper TTS ONNX for QNN conversion "
        "(deterministic noise + fixed length)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to original Piper ONNX model",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for patched ONNX output",
    )
    parser.add_argument(
        "--t-fixed",
        type=int,
        default=400,
        help="Fixed output length in latent frames "
        "(default: 400 ≈ 4.6 s @ 22050 Hz / hop 256)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run ONNX Runtime inference on both models and compare output shapes",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading: {args.input}")
    model = onnx.load(str(args.input))
    graph = gs.import_onnx(model)

    # ── Step 1: RandomNormalLike → zero ──
    print("\n--- Step 1: Replace RandomNormalLike with zero ConstantOfShape ---")
    n_replaced = replace_random_normal_like(graph)
    print(f"  Replaced {n_replaced} node(s)")

    # ── Step 2: Pin duration ──
    print(f"\n--- Step 2: Pin output length to T_FIXED = {args.t_fixed} frames ---")
    ok = pin_duration_to_fixed(graph, args.t_fixed)
    print(f"  {'✅ Applied' if ok else '⏭️  Skipped (landmarks not found)'}")

    # ── Clean, reorder, export, save ──
    print("\n--- Cleaning and sorting graph ---")
    try:
        graph.cleanup()
        graph.toposort()
        print("  ✅ Cleanup + toposort succeeded")
    except Exception as exc:
        # Even if toposort fails, we can still export the graph
        print(f"  ⚠️  Graph sorting warning: {exc}", file=sys.stderr)
        print("  (Proceeding with export anyway)")

    new_model = gs.export_onnx(graph)

    new_model.ir_version = model.ir_version
    new_model.producer_name = "patch_piper_onnx.py"
    new_model.producer_version = "1.0"
    if model.doc_string:
        new_model.doc_string = model.doc_string
    if not new_model.opset_import and model.opset_import:
        new_model.opset_import.extend(model.opset_import)

    print(f"\nSaving: {args.output}")
    onnx.save(new_model, str(args.output))
    size_mb = args.output.stat().st_size / 1e6
    print(f"  Size: {size_mb:.1f} MB")

    print_summary(graph, new_model)

    if args.verify:
        verify_with_ort(args.input, args.output)

    print("\nDone.")


if __name__ == "__main__":
    main()
