"""Candidate adapter base class + per-stage interfaces.

Each concrete candidate implements `_infer(item)` and declares its `stage` and
`id`. `run()` wraps timing + peak-RAM measurement and guarantees a `StageResult`
(even on failure) so one bad candidate never aborts the whole fan-out.
"""

from __future__ import annotations

import resource
import time
from abc import ABC, abstractmethod

from .schema import EvalItem, StageResult


def peak_ram_mb() -> float:
    # ru_maxrss is the high-water mark of resident memory (KB on Linux).
    # NOTE: this is the process-wide peak, not a per-candidate delta; a rough
    # proxy for v0 that we refine (per-process runner) in the on-device Phase 4.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


class Candidate(ABC):
    stage: str = ""
    id: str = ""

    def run(self, item: EvalItem) -> StageResult:
        start = time.perf_counter()
        try:
            out_text, out_audio = self._infer(item)
            return StageResult(
                candidate_id=self.id,
                item_id=item.id,
                stage=self.stage,
                output_text=out_text,
                output_audio_path=out_audio,
                latency_s=round(time.perf_counter() - start, 4),
                peak_ram_mb=peak_ram_mb(),
            )
        except Exception as exc:  # noqa: BLE001 - one bad candidate must not kill the run
            return StageResult(
                candidate_id=self.id,
                item_id=item.id,
                stage=self.stage,
                latency_s=round(time.perf_counter() - start, 4),
                error=f"{type(exc).__name__}: {exc}",
            )

    @abstractmethod
    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]: ...
