"""Fetch the pinned third-party Opus-MT vi->en artifacts into ``models/``.

Writes two directories under ``--out`` (default ``models``):

* ``opus-mt-vi-en-src/`` — the upstream HuggingFace repository
  (``Helsinki-NLP/opus-mt-vi-en``), including the SentencePiece tokenizers
  read at runtime by ``bench/candidates/opusmt_mt.py``.
* ``opus-mt-vi-en-ct2/`` — the CTranslate2 int8 conversion used by the
  benchmark harness.

Neither directory is tracked by git: the weights are third-party artifacts
(see ``NOTICE``) and are fetched on demand.

Needs network access. Run via ``make models``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

MODEL_ID = "Helsinki-NLP/opus-mt-vi-en"

# Pinned upstream revision (HF `main` as of 2023-08-16) so repeated runs and
# conversions stay reproducible. Bump deliberately, then update NOTICE.
MODEL_REVISION = "c8d2853e77f5fae31124d993e0b35176b1c8914e"

SRC_DIRNAME = "opus-mt-vi-en-src"
CT2_DIRNAME = "opus-mt-vi-en-ct2"


def fetch_source(out_dir: Path, revision: str) -> Path:
    """Snapshot the upstream HF repo (weights + tokenizers) into ``out_dir``."""
    from huggingface_hub import snapshot_download

    src_dir = out_dir / SRC_DIRNAME
    print(f"[fetch_models] downloading {MODEL_ID}@{revision[:12]} -> {src_dir}")
    snapshot_download(repo_id=MODEL_ID, revision=revision, local_dir=src_dir)
    return src_dir


def convert_to_ct2(src_dir: Path, out_dir: Path) -> Path:
    """Convert the Marian checkpoint to CTranslate2 int8."""
    from ctranslate2.converters import TransformersConverter

    ct2_dir = out_dir / CT2_DIRNAME
    print(f"[fetch_models] converting {src_dir} -> {ct2_dir} (int8)")
    TransformersConverter(str(src_dir), low_cpu_mem_usage=True).convert(
        str(ct2_dir), quantization="int8", force=True
    )
    return ct2_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("models"),
        help="Directory to place the fetched artifacts in (default: models).",
    )
    parser.add_argument(
        "--revision",
        default=MODEL_REVISION,
        help="Upstream HuggingFace revision to pin (default: %(default)s).",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Reuse the existing source directory; only run the CT2 conversion.",
    )
    args = parser.parse_args()

    out_dir: Path = args.out
    src_dir = out_dir / SRC_DIRNAME
    if args.skip_download:
        if not src_dir.exists():
            parser.error(f"--skip-download given but {src_dir} does not exist")
    else:
        src_dir = fetch_source(out_dir, args.revision)

    ct2_dir = convert_to_ct2(src_dir, out_dir)
    print(f"[fetch_models] done:\n  {src_dir}\n  {ct2_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
