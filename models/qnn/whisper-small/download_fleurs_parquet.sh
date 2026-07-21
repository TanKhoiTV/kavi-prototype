#!/usr/bin/env bash
# Chunked download of the FLEURS vi_vn train parquet (2.07 GB) over a proxy that
# drops sustained connections (~120 s cap). Each 30 MiB Range chunk completes well
# under the cap; -L re-resolves a fresh signed XET URL per chunk (no expiry risk).
set -u
PARQ_API="https://huggingface.co/api/datasets/google/fleurs/parquet/vi_vn/train/0.parquet"
OUTDIR="/home/dmin/qairt-work/whisper-encoder/fleurs_vi_parquet"
mkdir -p "$OUTDIR"
LOG="/tmp/fleurs_dl.log"
ts() { date '+%H:%M:%S'; }
echo "[$(ts)] starting FLEURS vi_vn train parquet chunked download" >> "$LOG"

SIZE=$(curl -sIL --max-time 60 -L "$PARQ_API" | grep -i "content-length" | tail -1 | tr -d '\r' | awk '{print $2}')
echo "[$(ts)] total size: $SIZE bytes (~$(( SIZE / 1048576 )) MiB)" >> "$LOG"

CHUNK=31457280   # 30 MiB per chunk (<120s proxy connection cap)
i=0
START=0
while [ "$START" -lt "$SIZE" ]; do
  END=$(( START + CHUNK - 1 ))
  if [ "$END" -ge "$SIZE" ]; then END=$(( SIZE - 1 )); fi
  OUT="$OUTDIR/chunk_$(printf %03d "$i")"
  EXPECTED=$(( END - START + 1 ))
  GOT=0
  for attempt in 1 2 3 4 5 6; do
    curl -sSL --retry 3 --retry-delay 3 -r ${START}-${END} "$PARQ_API" -o "$OUT"
    GOT=$(wc -c < "$OUT" 2>/dev/null || echo 0)
    if [ "$GOT" -eq "$EXPECTED" ]; then break; fi
    echo "[$(ts)] chunk $i attempt $attempt got $GOT expected $EXPECTED, retrying" >> "$LOG"
    sleep 3
  done
  if [ "$GOT" -ne "$EXPECTED" ]; then
    echo "[$(ts)] ERROR: chunk $i failed after retries (got $GOT / $EXPECTED)" >> "$LOG"
    exit 1
  fi
  echo "[$(ts)] chunk $i done: $GOT/$EXPECTED" >> "$LOG"
  START=$(( END + 1 ))
  i=$(( i + 1 ))
done

cat "$OUTDIR"/chunk_* > "$OUTDIR/0000.parquet"
FINAL=$(wc -c < "$OUTDIR/0000.parquet")
echo "[$(ts)] concatenated -> $OUTDIR/0000.parquet final size $FINAL (expected $SIZE)" >> "$LOG"
if [ "$FINAL" -ne "$SIZE" ]; then
  echo "[$(ts)] ERROR: concatenated size mismatch" >> "$LOG"
  exit 1
fi
echo "[$(ts)] DOWNLOAD COMPLETE" >> "$LOG"
