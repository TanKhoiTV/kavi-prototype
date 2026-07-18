"""Model-free tests for the v0 bench harness (no Whisper/Opus/Piper weights).

Covers the eval-manifest schema round-trip, the off-device scorer on known
inputs, and the FLEURS id-merging logic (audio<->transcript must pair by id
even when the parquet's physical row order is shuffled).
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from bench.schema import EvalItem, RunManifest, StageResult
from bench.scorer import score_item


def test_manifest_roundtrip(tmp_path: Path) -> None:
    items = [
        EvalItem(
            id="a",
            stage="MT",
            language="vi",
            direction="vi->en",
            input_text="Xin chào",
            reference_text="Hello",
        ),
        EvalItem(
            id="b",
            stage="ASR",
            language="en",
            audio_ref="/tmp/x.wav",
            reference_text="hi",
            snr=5.0,
            noise_type="steady",
        ),
    ]
    m = RunManifest(version="eval_manifest_v1", items=items)
    out = tmp_path / "eval_manifest_v1.json"
    m.to_json(out)
    back = RunManifest.from_json(out)
    assert back.version == m.version
    assert [asdict(i) for i in back.items] == [asdict(i) for i in m.items]


def test_scorer_wer_cer_exact_and_off_by_one() -> None:
    item = EvalItem(id="a", stage="ASR", language="en", reference_text="the cat sat")
    exact = score_item(
        item, StageResult("c", "a", "ASR", output_text="the cat sat"), None
    )
    assert exact.wer == 0.0
    assert exact.cer == 0.0
    off = score_item(
        item, StageResult("c", "a", "ASR", output_text="the dog sat"), None
    )
    assert off.wer == pytest.approx(1 / 3)
    assert off.cer is not None and off.cer > 0.0


def test_scorer_bleu_positive() -> None:
    # Reference needs >=4 tokens so 4-gram precision is defined (else BLEU=0).
    item = EvalItem(
        id="m",
        stage="MT",
        language="vi",
        direction="vi->en",
        input_text="Xin chào",
        reference_text="the cat sat on the mat",
    )
    met = score_item(
        item, StageResult("c", "m", "MT", output_text="the cat sat on the mat"), None
    )
    assert met.bleu is not None and met.bleu > 0.0


def test_scorer_skips_without_reference() -> None:
    item = EvalItem(id="a", stage="ASR", language="en")  # no reference_text
    met = score_item(item, StageResult("c", "a", "ASR", output_text="anything"), None)
    assert met.wer is None
    assert any("skipped" in n for n in met.notes)


def test_scorer_error_short_circuits() -> None:
    item = EvalItem(id="a", stage="ASR", language="en", reference_text="x")
    met = score_item(item, StageResult("c", "a", "ASR", error="Boom"), None)
    assert met.wer is None
    assert met.notes and met.notes[0].startswith("error")


def _write_synthetic_fleurs(
    path: Path, n: int = 100, shuffle_seed: int = 7
) -> dict[str, int]:
    import random

    expected: dict[str, int] = {}
    rows = []
    for i in range(n):
        rid = f"utt_{i:04d}"
        rows.append(
            {
                "id": rid,
                "transcription": f"text_{i}",
                "audio": {
                    "array": [float(i), float(i)],
                    "bytes": None,
                    "sampling_rate": 16000,
                },
            }
        )
        expected[rid] = i
    random.Random(shuffle_seed).shuffle(rows)  # physical order != id order
    audio_struct = pa.array(
        [
            {"array": r["audio"]["array"], "bytes": None, "sampling_rate": 16000}
            for r in rows
        ],
        type=pa.struct(
            [
                ("array", pa.list_(pa.float64())),
                ("bytes", pa.binary()),
                ("sampling_rate", pa.int64()),
            ]
        ),
    )
    tbl = pa.table(
        {
            "id": pa.array([r["id"] for r in rows]),
            "transcription": pa.array([r["transcription"] for r in rows]),
            "audio": audio_struct,
        }
    )
    pq.write_table(tbl, str(path), row_group_size=50)  # 2 row groups
    return expected


def test_fleurs_load_pairs_audio_to_transcript_by_id(tmp_path: Path) -> None:
    from bench.data_prep import _load_fleurs

    pq_path = tmp_path / "synthetic_fleurs.parquet"
    expected = _write_synthetic_fleurs(pq_path)
    out = _load_fleurs(str(pq_path), n=30, sample_rate=16000, seed=42)
    assert len(out) == 30
    for uid, tx, audio in out:
        i = expected[uid]
        assert abs(audio[0, 0].item() - i) < 1e-6
        assert tx == f"text_{i}"
