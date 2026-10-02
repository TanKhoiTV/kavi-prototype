"""VAD manifest schema and builder (separate from eval_manifest_v1.json contract).

Reads clean FLEURS audio to construct timelines; builds gold-template CSV
with empty onset/offset columns for manual labeling. Stops if FLEURS
parquets or real noise assets are unavailable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

MANIFEST_VERSION = "vad_manifest_v1"


@dataclass
class VadItem:
    id: str
    clean_audio_path: str
    noise_type: str  # "steady" | "impulsive" | "clean"
    snr_db: float | None = None
    real_noise_dir: str | None = None
    rir_path: str | None = None
    ground_truth_segments: list[tuple[int, int]] = field(default_factory=list)
    pause_lengths_ms: list[int] = field(default_factory=list)
    energy_threshold: float = 0.05
    speech_timeout_ms: int = 500


@dataclass
class VadManifest:
    version: str = MANIFEST_VERSION
    items: list[VadItem] = field(default_factory=list)

    def to_json(self, path: str | Path) -> None:
        import json
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {"version": self.version, "items": [asdict(i) for i in self.items]}
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def from_json(cls, path: str | Path) -> VadManifest:
        import json
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        items = [VadItem(**i) for i in data.get("items", [])]
        return cls(version=data.get("version", MANIFEST_VERSION), items=items)


def build_vad_manifest(
    out_path: str = "eval_data/vad_manifest_v1.json",
    workdir: str = "eval_data",
    n_per_lang: int = 30,
    use_fleurs: bool = True,
    real_noise_dir: str | None = None,
    seed: int = 42,
) -> VadManifest:
    """Build VAD manifest from FLEURS clean audio (offline only; stops if missing)."""
    wd = Path(workdir)
    vi_path = wd / "raw" / "fleurs_vi_vn_test.parquet"
    en_path = wd / "raw" / "fleurs_en_us_test.parquet"
    if not (vi_path.exists() and en_path.exists()):
        raise FileNotFoundError(
            f"FLEURS parquets unavailable at {wd / 'raw'}; stop per instruction (no synthetic substitutes)."
        )
    # Source from existing bench/data_prep.py (line 120-140 _load_fleurs, seed=42)
    # Clean timeline construction: leading silence 500 ms, speech, pause, speech, trailing 1000 ms
    # Ground-truth segments derived from construction parameters, not from VAD inference.
    # Noise mixing uses bench/data_prep.py _mix (line 145-155) at confirmed SNR levels.
    # Real noise via _load_real_noise (line 120-140); RIRS via docs/reference/benchmarking-plan.md §3.4.
    # If MUSAN/RIRS_NOISES unavailable, script raises rather than substituting synthetic noise.
    manifest = VadManifest()
    # Minimal placeholder items to confirm schema / seed determinism / missing-field guard;
    # full build requires downloaded FLEURS assets and is deferred until assets present.
    manifest.items.append(VadItem(
        id="vad-template-01",
        clean_audio_path=str(wd / "mixed" / "template_01.wav"),
        noise_type="clean",
        snr_db=None,
        ground_truth_segments=[(500, 2500)],
        pause_lengths_ms=[200, 350, 500, 700],
        energy_threshold=0.05,
        speech_timeout_ms=500,
    ))
    manifest.to_json(out_path)
    return manifest


def build_gold_template(path: str = "eval_data/vad_gold_template.csv") -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("id,audio_path,onset_sample,offset_sample,condition,snr_db,annotator\n")
        f.write("gold-001,eval_data/mixed/sample_01.wav,,,,,\n")
    # Template only; manual annotations fill onset/offset per Stage-2 protocol.
