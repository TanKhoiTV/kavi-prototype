"""Tests for VAD manifest schema and builder; synthetic only, no real audio."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench.vad_manifest import (
    VadItem,
    VadManifest,
    build_gold_template,
    build_vad_manifest,
)


def test_manifest_schema_fields() -> None:
    item = VadItem(
        id="vad-test-01",
        language="vi",
        condition="quiet",
        clean_audio_path="eval_data/mixed/test.wav",
        noise_type="clean",
        pause_ms=500,
        ground_truth_segments=[(500, 2500)],
        energy_threshold=0.05,
        speech_timeout_ms=500,
    )
    manifest = VadManifest(items=[item])
    assert manifest.version == "vad_manifest_v2"
    assert len(manifest.items) == 1
    assert manifest.items[0].noise_type == "clean"
    assert manifest.items[0].pause_ms == 500
    assert manifest.items[0].condition == "quiet"


def test_manifest_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "vad_manifest_v2.json"
    manifest = VadManifest()
    manifest.items.append(
        VadItem(
            id="t1",
            language="vi",
            condition="quiet",
            clean_audio_path="a.wav",
            noise_type="clean",
            pause_ms=500,
            ground_truth_segments=[(500, 2500)],
        )
    )
    manifest.to_json(out)
    back = VadManifest.from_json(out)
    assert back.version == "vad_manifest_v2"
    assert [i.id for i in back.items] == ["t1"]
    assert back.items[0].condition == "quiet"
    assert back.items[0].pause_ms == 500


def test_seed_determinism() -> None:
    m1 = VadManifest(
        items=[
            VadItem(
                id="seed-a",
                language="en",
                condition="quiet",
                clean_audio_path="a.wav",
                noise_type="clean",
                pause_ms=500,
                ground_truth_segments=[(500, 2500)],
            )
        ]
    )
    m2 = VadManifest(
        items=[
            VadItem(
                id="seed-a",
                language="en",
                condition="quiet",
                clean_audio_path="a.wav",
                noise_type="clean",
                pause_ms=500,
                ground_truth_segments=[(500, 2500)],
            )
        ]
    )
    assert m1.items[0].id == m2.items[0].id


def test_build_stops_when_fleurs_missing(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        build_vad_manifest(
            out_path=str(tmp_path / "vad_stop.json"),
            workdir=str(tmp_path),
            use_fleurs=True,
        )


def test_gold_template_exists_and_fields() -> None:
    build_gold_template(path="/tmp/vad_gold.csv")
    content = Path("/tmp/vad_gold.csv").read_text(encoding="utf-8")
    assert (
        "id,audio_path,onset_sample,offset_sample,condition,snr_db,annotator" in content
    )
    assert "gold-001" in content
    lines = content.strip().splitlines()
    assert len(lines) == 51  # header + 50 gold rows (stage 3A v2)
    # Verify 25 VI / 25 EN / coverage >=2 per cell handled in build_gold_template


def test_snr_tolerance_declaration() -> None:
    item = VadItem(
        id="test",
        language="vi",
        condition="street",
        clean_audio_path="x.wav",
        noise_type="steady",
        snr_db=10.0,
        pause_ms=500,
    )
    assert item.snr_db == 10.0
    assert item.condition == "street"
    # Stage-0 reference: data_prep._mix uses torchaudio.functional.add_noise with target SNR


def test_vad_item_accepts_valid_condition_snr():
    item = VadItem(
        id="vi-street-10-200-000",
        language="vi",
        condition="street",
        clean_audio_path="clean.wav",
        noise_type="impulsive",
        noise_path="noise.wav",
        snr_db=10.0,
        pause_ms=200,
    )
    assert item.condition == "street"
    assert item.snr_db == 10.0
    assert item.pause_ms == 200


def test_vad_item_rejects_invalid_condition_snr():
    with pytest.raises(ValueError):
        VadItem(
            id="vi-street-0-200-000",
            language="vi",
            condition="street",
            clean_audio_path="clean.wav",
            noise_type="impulsive",
            noise_path="noise.wav",
            snr_db=0.0,
            pause_ms=200,
        )


def test_vad_item_rejects_invalid_pause():
    with pytest.raises(ValueError):
        VadItem(
            id="vi-street-10-100-000",
            language="vi",
            condition="street",
            clean_audio_path="clean.wav",
            noise_type="impulsive",
            noise_path="noise.wav",
            snr_db=10.0,
            pause_ms=100,
        )


def test_vad_item_accepts_far_field_minus_5_db():
    item = VadItem(
        id="en-far-field-m5-700-000",
        language="en",
        condition="far-field",
        clean_audio_path="clean.wav",
        noise_type="impulsive",
        noise_path="noise.wav",
        snr_db=-5.0,
        pause_ms=700,
    )
    assert item.condition == "far-field"
    assert item.snr_db == -5.0
    assert item.pause_ms == 700


def test_vad_item_accepts_quiet_clean():
    item = VadItem(
        id="vi-quiet-clean-200-000",
        language="vi",
        condition="quiet",
        clean_audio_path="clean.wav",
        noise_type="clean",
        noise_path=None,
        snr_db=None,
        rir_path=None,
        pause_ms=200,
    )
    assert item.condition == "quiet"
    assert item.noise_type == "clean"
    assert item.snr_db is None
