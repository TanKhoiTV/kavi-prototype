"""Tests for bench.qnn.generate_calibration_lists and bench.qnn.patch_whisper_decoder.

Covers:
  - Bug #1: _mel_spectrogram must not call .numpy() on a numpy array
  - Bug #2: strip_isnan_nodes must handle dynamic ONNX shapes (None / str dims)
  - Regression guards for the qairt lightweight-env constraint (no torch)
"""

from __future__ import annotations

import numpy as np
import pytest


# ── _mel_spectrogram ────────────────────────────────────────────────


class TestMelSpectrogram:
    """Bug #1 regression: scipy rewrite left a stale .numpy() call."""

    def test_output_shape(self) -> None:
        """Must return (1, 80, 3000) float32."""
        from bench.qnn.generate_calibration_lists import _mel_spectrogram

        audio = np.random.randn(480_000).astype(np.float32)
        result = _mel_spectrogram(audio)
        assert result.shape == (1, 80, 3000)
        assert result.dtype == np.float32

    def test_no_nan(self) -> None:
        """Mel spectrogram should not contain NaN."""
        from bench.qnn.generate_calibration_lists import _mel_spectrogram

        audio = np.zeros(480_000, dtype=np.float32)
        result = _mel_spectrogram(audio)
        assert not np.isnan(result).any()

    def test_silence_vs_signal_differ(self) -> None:
        """Silence and signal should produce different mel features."""
        from bench.qnn.generate_calibration_lists import _mel_spectrogram

        silence = np.zeros(480_000, dtype=np.float32)
        signal = np.random.randn(480_000).astype(np.float32) * 0.1
        m_silence = _mel_spectrogram(silence)
        m_signal = _mel_spectrogram(signal)
        assert not np.allclose(m_silence, m_signal)

    def test_torch_not_imported(self) -> None:
        """_mel_spectrogram must work without torch (qairt env constraint)."""
        import sys

        torch_was = sys.modules.pop("torch", None)
        try:
            from bench.qnn.generate_calibration_lists import _mel_spectrogram

            audio = np.random.randn(480_000).astype(np.float32)
            _mel_spectrogram(audio)  # must not raise
        finally:
            if torch_was is not None:
                sys.modules["torch"] = torch_was


# ── strip_isnan_nodes ───────────────────────────────────────────────


class TestStripIsnanNodes:
    """Bug #2 regression: np.zeros crashes on None / str shape dims."""

    @staticmethod
    def _make_isnan_graph(shape: tuple) -> "gs.Graph":  # noqa: F821
        """Build a minimal graph with one IsNaN node of given output shape."""
        import onnx_graphsurgeon as gs

        X = gs.Variable("X", dtype=np.float32, shape=(1, 4))
        Y = gs.Variable("Y", dtype=np.bool_, shape=shape)
        isnan_node = gs.Node("IsNaN", inputs=[X], outputs=[Y], name="isnan_0")
        graph = gs.Graph(
            nodes=[isnan_node],
            inputs=[X],
            outputs=[Y],
            name="test_graph",
        )
        return graph

    def test_static_shape(self) -> None:
        """IsNaN with static shape (3, 4) should be replaced."""
        from bench.qnn.patch_whisper_decoder import strip_isnan_nodes

        graph = self._make_isnan_graph(shape=(3, 4))
        count = strip_isnan_nodes(graph)
        graph.cleanup().toposort()  # remove dead nodes (matches main())
        assert count == 1
        assert all(n.op != "IsNaN" for n in graph.nodes)

    def test_dynamic_shape_none(self) -> None:
        """IsNaN with (None, 128) must not crash — Bug #2 regression."""
        from bench.qnn.patch_whisper_decoder import strip_isnan_nodes

        graph = self._make_isnan_graph(shape=(None, 128))
        count = strip_isnan_nodes(graph)
        graph.cleanup().toposort()  # remove dead nodes (matches main())
        assert count == 1
        assert all(n.op != "IsNaN" for n in graph.nodes)

    def test_fully_dynamic_shape(self) -> None:
        """IsNaN with (None, None, 128) must not crash."""
        from bench.qnn.patch_whisper_decoder import strip_isnan_nodes

        graph = self._make_isnan_graph(shape=(None, None, 128))
        count = strip_isnan_nodes(graph)
        graph.cleanup().toposort()
        assert count == 1

    def test_string_dynamic_shape(self) -> None:
        """IsNaN with named dims ('batch', 'seq', 128) must not crash."""
        from bench.qnn.patch_whisper_decoder import strip_isnan_nodes

        graph = self._make_isnan_graph(shape=("batch", "seq", 128))
        count = strip_isnan_nodes(graph)
        graph.cleanup().toposort()
        assert count == 1

    def test_empty_shape(self) -> None:
        """IsNaN with scalar output () should work."""
        from bench.qnn.patch_whisper_decoder import strip_isnan_nodes

        graph = self._make_isnan_graph(shape=())
        count = strip_isnan_nodes(graph)
        graph.cleanup().toposort()
        assert count == 1

    def test_no_isnan_pass_through(self) -> None:
        """Graph with no IsNaN nodes should return 0 and remain unchanged."""
        import onnx_graphsurgeon as gs

        from bench.qnn.patch_whisper_decoder import strip_isnan_nodes

        X = gs.Variable("X", dtype=np.float32, shape=(1, 4))
        Y = gs.Variable("Y", dtype=np.float32, shape=(1, 4))
        relu_node = gs.Node("Relu", inputs=[X], outputs=[Y], name="relu_0")
        graph = gs.Graph(nodes=[relu_node], inputs=[X], outputs=[Y], name="no_isnan")
        count = strip_isnan_nodes(graph)
        assert count == 0
        assert len(graph.nodes) == 1
