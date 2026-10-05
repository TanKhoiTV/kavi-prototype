"""Summarise a beam-sweep archive into a citable aggregate table.

The raw per-item sweep output lives under ``bench-results/``, which is
gitignored, so it is not reproducible from the repository. This script reduces
a finished sweep to the small table that *is* committed (see
``docs/reference/beam-sweep-host-aggregate.md``), so the figures quoted in
[ADR-020](../docs/decisions/ADR-020-pipeline-concurrency.md) have a source a
future reader can re-derive.

It also reports the two things that make the sweep's own latency column
uncitable, so the caveat travels with the numbers:

- latency ratios on both the **mean** and the **median**, which disagree; and
- how many items break the monotonicity a beam ladder must satisfy
  (``b1 <= b2 <= b4 <= b5 <= b8``).

Usage::

    uv run python -m scripts.summarise_beam_sweep <sweep-dir> [--beams 1 2 4 5 8]

where ``<sweep-dir>`` is a directory containing one ``beam-N/`` subdirectory per
beam width, each holding a ``run_results.json``.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def load_beam(root: Path, beam: int) -> dict[str, dict]:
    """Return ``{item_id: record}`` for one beam width."""
    path = root / f"beam-{beam}" / "run_results.json"
    records: dict[str, dict] = {}
    for entry in json.loads(path.read_text(encoding="utf-8")):
        if entry["result"].get("error"):
            continue
        records[entry["item"]["id"]] = entry
    return records


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile; avoids an interpolation dependency."""
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round(q * len(ordered))) - 1))
    return ordered[idx]


def corpus_bleu(per_beam: dict[int, dict[str, dict]]) -> dict[int, float]:
    """SacreBLEU over the whole item set, not a mean of per-sentence scores.

    Averaging per-sentence BLEU weights a 3-word item the same as a 40-word one,
    which is why the sweep's own figure and this one differ. Reported separately
    rather than substituted, so the published column stays traceable.
    """
    import sacrebleu

    out: dict[int, float] = {}
    for beam, records in per_beam.items():
        hyps, refs = [], []
        for entry in records.values():
            hyp = entry["result"].get("output_text")
            ref = entry["item"].get("reference_text")
            # `None` and `0.0` are different states in the scorer: an absent
            # reference is unscoreable (bleu is None), while an empty hypothesis
            # against a real reference is a *failed* translation scoring 0.0.
            # Filtering on truthiness drops the second kind, which is exactly the
            # sample that must count against the aggregate.
            if ref:
                hyps.append(hyp or "")
                refs.append(ref)
        out[beam] = round(sacrebleu.corpus_bleu(hyps, [refs]).score, 2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "sweep_dir", type=Path, help="dir containing beam-N/run_results.json"
    )
    ap.add_argument("--beams", type=int, nargs="+", default=[1, 2, 4, 5, 8])
    args = ap.parse_args()

    per_beam = {b: load_beam(args.sweep_dir, b) for b in args.beams}
    corpus = corpus_bleu(per_beam)
    base = args.beams[0]

    print(f"source: {args.sweep_dir}")
    print(
        f"{'beam':>5} {'n':>4} {'sentBLEU':>9} {'corpusBLEU':>11} "
        f"{'mean_s':>8} {'ratio':>7} {'med_s':>7} {'ratio':>7} {'p95_s':>7}"
    )
    for beam in args.beams:
        recs = per_beam[beam]
        lat = [e["result"]["latency_s"] for e in recs.values()]
        sent = [
            e["metrics"]["bleu"]
            for e in recs.values()
            if e["metrics"]["bleu"] is not None
        ]
        mean_s, med_s = statistics.mean(lat), statistics.median(lat)
        base_lat = [e["result"]["latency_s"] for e in per_beam[base].values()]
        print(
            f"{beam:>5} {len(lat):>4} {statistics.mean(sent):>9.2f} {corpus[beam]:>11.2f} "
            f"{mean_s:>8.3f} {mean_s / statistics.mean(base_lat):>6.2f}x "
            f"{med_s:>7.3f} {med_s / statistics.median(base_lat):>6.2f}x "
            f"{percentile(lat, 0.95):>7.3f}"
        )

    ids = set(per_beam[base])
    for beam in args.beams:
        ids &= set(per_beam[beam])
    ladder = args.beams
    broken = [
        i
        for i in sorted(ids)
        if not all(
            per_beam[a][i]["result"]["latency_s"]
            <= per_beam[b][i]["result"]["latency_s"]
            for a, b in zip(ladder, ladder[1:], strict=False)
        )
    ]
    regressions = [
        (i, a, b)
        for i in sorted(ids)
        for a, b in zip(ladder, ladder[1:], strict=False)
        if per_beam[b][i]["result"]["latency_s"] < per_beam[a][i]["result"]["latency_s"]
    ]

    print()
    print(f"items compared: {len(ids)}")
    print(f"ladder: {' <= '.join(f'b{b}' for b in ladder)}")
    print(
        f"items breaking monotonicity: {len(broken)} ({100 * len(broken) / len(ids):.0f}%)"
    )
    print(f"adjacent pairs where the wider beam is FASTER: {len(regressions)}")
    for item, a, b in regressions[:5]:
        ratio = (
            per_beam[b][item]["result"]["latency_s"]
            / per_beam[a][item]["result"]["latency_s"]
        )
        print(f"  {item}: b{b} is {ratio:.2f}x the time of b{a}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
