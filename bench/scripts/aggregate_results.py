"""Aggregate docs/benchmark/raw-results/*.csv into the two benchmark .md docs.

Reads the cleaned per-item CSVs (error/skip rows already removed) and
regenerates:
  - docs/benchmark/benchmark-results-fleurs-vivos.md (detailed, with notes)
  - docs/benchmark/benchmark-results-raw.md         (tables only)
"""
from __future__ import annotations

import csv
import datetime
import statistics as st
from collections import defaultdict
from pathlib import Path

DOCS = Path("docs/benchmark")
RAW = DOCS / "raw-results"

SNRS = [None, 15.0, 10.0, 5.0, 0.0]
NOISES = ["clean", "steady", "impulsive"]


def mean(xs):
    return st.mean(xs) if xs else float("nan")


def md(x, nd=4):
    return f"{x:.{nd}f}" if x == x else "-"


def fnum(x, nd=2):
    return f"{x:.{nd}f}" if x == x else "-"


def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


ASR = load_csv(RAW / "fleurs-asr.csv")
MT = load_csv(RAW / "fleurs-mt.csv")
VV = load_csv(RAW / "vivos.csv")


def asr_grid(rows, lang):
    grid = defaultdict(list)
    for r in rows:
        if r["language"] != lang:
            continue
        snr = float(r["snr"]) if r["snr"] not in ("", None) else None
        grid[(r["noise_type"], snr)].append(float(r["wer"]))
    return grid


def asr_summary(rows, lang):
    rows = [r for r in rows if r["language"] == lang]
    wers = [float(r["wer"]) for r in rows if r["wer"] not in ("", None)]
    lats = [float(r["latency_s"]) for r in rows if r["latency_s"] not in ("", None)]
    rtfs = [float(r["rtf"]) for r in rows if r["rtf"] not in ("", None)]
    ram = [float(r["peak_ram_mb"]) for r in rows if r["peak_ram_mb"] not in ("", None)]
    return (
        md(mean(wers)),
        fnum(mean(lats)) if lats else "-",
        fnum(mean(rtfs)) if rtfs else "-",
        f"{mean(ram):.0f}" if ram else "-",
    )


def grid_table(grid):
    out = ["| condition | clean | 15 dB | 10 dB | 5 dB | 0 dB |", "|---|---|---|---|---|---|"]
    for noise in NOISES:
        cells = [md(mean(grid[(noise, s)])) if grid[(noise, s)] else "-" for s in SNRS]
        out.append(f"| {noise} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def fleurs_asr_sections():
    out = []
    for cid in sorted({r["run"].split("/")[-1] for r in ASR}):
        rows = [r for r in ASR if r["run"].endswith(cid)]
        for lang in sorted({r["language"] for r in rows}):
            w, la, rt, rm = asr_summary(rows, lang)
            out.append(f"### `{cid}` · {lang.upper()}\n")
            out.append(f"mean WER {w} | mean latency {la} s | RTF {rt} | peak RAM {rm} MB\n")
            out.append(grid_table(asr_grid(rows, lang)))
            out.append("")
    return out


def mt_table():
    out = [
        "| run | n | mean BLEU | median | min | max | mean latency s | peak RAM MB |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for run in sorted({r["run"] for r in MT}):
        rows = [r for r in MT if r["run"] == run]
        bs = [float(r["bleu"]) for r in rows if r["bleu"] not in ("", None)]
        lats = [float(r["latency_s"]) for r in rows if r["latency_s"] not in ("", None)]
        ram = [float(r["peak_ram_mb"]) for r in rows if r["peak_ram_mb"] not in ("", None)]
        out.append(
            f"| {run} | {len(bs)} | {fnum(mean(bs))} | {fnum(st.median(bs))} | "
            f"{fnum(min(bs))} | {fnum(max(bs))} | {fnum(mean(lats))} | "
            f"{f'{mean(ram):.0f}' if ram else '-'} |"
        )
    return "\n".join(out)


def vivos_sections():
    out = []
    for cid in sorted({r["run"].split("/")[-1] for r in VV}):
        rows = [r for r in VV if r["run"].endswith(cid)]
        w, la, rt, rm = asr_summary(rows, "vi")
        out.append(f"### `{cid}`\n")
        out.append(f"mean WER {w} | mean latency {la} s | RTF {rt} | peak RAM {rm} MB\n")
        out.append(grid_table(asr_grid(rows, "vi")))
        out.append("")
    return out


INVENTORY = [
    "| Dataset | Manifest | Items | Candidates (beam) |",
    "|---|---|---|---|",
    "| FLEURS ASR | `eval_data/eval_manifest_v1.json` | 540 (30 vi + 30 en base × 9 conditions) | whisper-small (2), moonshine-vi (1), moonshine-en (4), zipformer-vi (5), zipformer-en (4) |",
    "| FLEURS MT | `eval_data/mt_vi_en_eval_manifest.json` | 347 vi→en pairs | opus-mt (5), m2m100 (4) |",
    "| VIVOS ASR | `eval_data/vivos_vi_eval_manifest.json` | 900 (100 vi × 9 conditions) | whisper-small (2), moonshine-vi (1), zipformer-vi (5) |",
]


def gen_detailed():
    out = []
    append = out.append
    append("# Benchmark Results — FLEURS + VIVOS\n")
    append(
        f"_Generated {datetime.date.today().isoformat()} from `docs/benchmark/raw-results/*.csv` "
        "(error/skip rows removed). WER case-normalized; BLEU = sacrebleu corpus-bleu. "
        "RTF = latency / audio duration._\n"
    )
    append("## Run inventory\n")
    append("\n".join(INVENTORY))
    append("")
    append("All ASR runs cover the full SNR grid: **clean + steady/impulsive @ 15/10/5/0 dB** (60 items/condition FLEURS, 100 VIVOS).\n")
    append("## 1. FLEURS ASR — mean WER by condition\n")
    out.extend(fleurs_asr_sections())
    append("## 2. FLEURS MT (vi→en) — BLEU\n")
    append(mt_table())
    gold = [r for r in MT if r["item_id"].startswith("gold")]
    append("")
    append(f"Gold items across runs: {len(gold)} rows (`gold-mt-00..11` × candidates).\n")
    append("## 3. VIVOS ASR (vi) — mean WER by condition\n")
    out.extend(vivos_sections())
    append("## 4. Notes & caveats\n")
    append("- Aggregated from `docs/benchmark/raw-results/` CSVs; ASR skip/error rows and non-MT rows in MT runs are excluded (see the CSVs for full per-item detail).")
    append("- Steady noise is the dominant degradation; impulsive noise degrades WER only mildly even at 0 dB.")
    append("- VIVOS whisper RTF (~0.9) is not comparable to FLEURS (~0.3): whisper costs ~3.3 s per item regardless of clip length; use absolute latency across datasets.")
    append("- 3 FLEURS whisper items exceed WER 1.0 (`vi-asr-1899-steady-0`, `vi-asr-1730-steady-10`, one en steady-0) — low-SNR repetition loops (real model behavior).")
    append("- Archive parity: per-item WER/BLEU on items shared with `bench-results/archive/` reproduce exactly (zipformer-vi 0.1375, zipformer-en 0.2404, m2m 17.19).")
    append("- On-device candidates (qnn-*, rtranslator) are not included — they require Qualcomm HTP hardware.")
    return "\n".join(out)


def gen_raw_tables():
    out = []
    append = out.append
    append("# Benchmark Results — aggregated tables\n")
    append(f"_Generated {datetime.date.today().isoformat()} from `docs/benchmark/raw-results/*.csv`_\n")
    append("## Run inventory\n")
    append("\n".join(INVENTORY))
    append("")
    append("## 1. FLEURS ASR — mean WER by condition\n")
    out.extend(fleurs_asr_sections())
    append("## 2. FLEURS MT (vi→en) — BLEU\n")
    append(mt_table())
    append("")
    append("## 3. VIVOS ASR (vi) — mean WER by condition\n")
    out.extend(vivos_sections())
    return "\n".join(out)


def main() -> None:
    (DOCS / "benchmark-results-fleurs-vivos.md").write_text(
        gen_detailed(), encoding="utf-8"
    )
    (DOCS / "benchmark-results-raw.md").write_text(gen_raw_tables(), encoding="utf-8")
    print("regenerated both .md files from the CSVs")


if __name__ == "__main__":
    main()
