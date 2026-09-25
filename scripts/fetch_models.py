"""Fetch the pinned third-party Opus-MT vi->en artifacts into ``models/``.

Writes two directories under ``--out`` (default ``models``):

* ``opus-mt-vi-en-src/`` - the upstream HuggingFace repository
  (``Helsinki-NLP/opus-mt-vi-en``), including the SentencePiece tokenizers read
  at runtime by ``bench/candidates/opusmt_mt.py``. ``tf_model.h5`` is skipped:
  it is a redundant TensorFlow copy that CTranslate2 never reads (~289 MB).
* ``opus-mt-vi-en-ct2/`` - the CTranslate2 int8 conversion used by the harness.

Repository, revision and digests come from ``assets.lock.toml``; the resulting
files are verified against it (``--no-verify`` to skip). Neither directory is
tracked by git - see ``NOTICE``.

Needs network access. Run via ``make models``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .assets import load_lock, verify

SRC_DIRNAME = "opus-mt-vi-en-src"
CT2_DIRNAME = "opus-mt-vi-en-ct2"

# Redundant TensorFlow copy; never read by CTranslate2.
_SKIP_PATTERNS = ["tf_model.h5"]


def fetch_source(out_dir: Path, repo: str, revision: str) -> Path:
    """Snapshot the upstream HF repo (weights + tokenizers) into ``out_dir``."""
    from huggingface_hub import snapshot_download

    src_dir = out_dir / SRC_DIRNAME
    print(f"[fetch_models] downloading {repo}@{revision[:12]} -> {src_dir}")
    snapshot_download(
        repo_id=repo,
        revision=revision,
        local_dir=src_dir,
        ignore_patterns=_SKIP_PATTERNS,
    )
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
    lock = load_lock()["models"]["opus_mt_vi_en"]

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("models"),
        help="Directory to place the fetched artifacts in (default: models).",
    )
    parser.add_argument(
        "--repo",
        default=lock["repo"],
        help="Upstream HuggingFace repository (default: %(default)s).",
    )
    parser.add_argument(
        "--revision",
        default=lock["revision"],
        help="Upstream HuggingFace revision to pin (default: the locked one).",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Reuse the existing source directory; only run the CT2 conversion.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip SHA-256 verification against assets.lock.toml.",
    )
    args = parser.parse_args()

    out_dir: Path = args.out
    src_dir = out_dir / SRC_DIRNAME
    if args.skip_download:
        if not src_dir.exists():
            parser.error(f"--skip-download given but {src_dir} does not exist")
    else:
        src_dir = fetch_source(out_dir, args.repo, args.revision)

    ct2_dir = convert_to_ct2(src_dir, out_dir)

    if args.no_verify:
        print("[fetch_models] skipping digest verification (--no-verify)")
    else:
        checks = [
            (out_dir / lock["source_path"], lock["source_sha256"], lock["source_size"]),
            (out_dir / lock["ct2_path"], lock["ct2_sha256"], lock["ct2_size"]),
        ]
        ok = True
        for path, sha, size in checks:
            good, msg = verify(path, sha256=sha, size=size)
            print(f"[fetch_models] {'PASS' if good else 'FAIL'} {msg}")
            ok = ok and good
        if not ok:
            print(
                "[fetch_models] verification failed - on-disk artifacts do not "
                "match assets.lock.toml",
                file=sys.stderr,
            )
            return 1

    print(f"[fetch_models] done:\n  {src_dir}\n  {ct2_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
