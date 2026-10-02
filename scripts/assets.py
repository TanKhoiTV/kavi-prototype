"""Shared helpers for pinned third-party assets.

The digests live in ``assets.lock.toml`` at the repo root. The acquisition
scripts (``scripts.fetch_models``, ``scripts.fetch_data``) and
``scripts.verify_assets`` all read that file, so there is a single source of
truth for *what* should be on disk and *how* to tell it is intact.

Nothing here needs the network; it is pure local verification.
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = REPO_ROOT / "assets.lock.toml"

_CHUNK = 1024 * 1024


def load_lock(path: Path | None = None) -> dict[str, Any]:
    """Return the parsed ``assets.lock.toml``."""
    lock_path = path or LOCK_PATH
    try:
        with open(lock_path, "rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"asset lock not found: {lock_path} (expected at the repo root)"
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"asset lock is not valid TOML: {lock_path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    """Streamed SHA-256 of a file (safe for multi-GB inputs)."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(_CHUNK), b""):
                digest.update(chunk)
    except OSError as exc:
        raise OSError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def verify(path: Path, *, sha256: str, size: int | None = None) -> tuple[bool, str]:
    """Check ``path`` against an expected size and digest.

    Returns ``(ok, message)``; the message is human-readable either way so
    callers can print it verbatim.
    """
    if not path.exists():
        return False, f"missing: {path}"
    if size is not None:
        actual_size = path.stat().st_size
        if actual_size != size:
            return False, f"size mismatch: {path} ({actual_size} != {size})"
    actual = sha256_file(path)
    if actual != sha256:
        return False, f"sha256 mismatch: {path} ({actual[:12]}... != {sha256[:12]}...)"
    return True, f"ok: {path}"
