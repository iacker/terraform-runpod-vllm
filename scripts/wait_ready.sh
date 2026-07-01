#!/usr/bin/env bash
# Poll a vLLM endpoint until the model is actually serving.
# RUNNING pod status only means the container started — vLLM still downloads
# the model (tens of GB) and loads it to VRAM, which takes 5-15 min.
# HTTP 200 on /v1/models = truly ready. 502 = still loading. 403 = crashed.
set -euo pipefail
ENDPOINT="${1:?usage: wait_ready.sh <endpoint-url> [max_minutes]}"
MAX_MIN="${2:-20}"
deadline=$(( $(date +%s) + MAX_MIN * 60 ))

echo "waiting for ${ENDPOINT}/v1/models (up to ${MAX_MIN} min)..."
while [ "$(date +%s)" -lt "$deadline" ]; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${ENDPOINT}/v1/models" || echo 000)
  case "$code" in
    200) echo "READY — model is serving (HTTP 200)"; exit 0 ;;
    502|504) echo "  still loading (HTTP ${code})..." ;;
    403) echo "vLLM CRASHED at startup (HTTP 403, port never opened). Check model arch / image." >&2; exit 1 ;;
    *)   echo "  HTTP ${code}, retrying..." ;;
  esac
  sleep 20
done
echo "timeout after ${MAX_MIN} min — not ready" >&2
exit 1
