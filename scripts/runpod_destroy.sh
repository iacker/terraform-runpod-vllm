#!/usr/bin/env bash
# Delete a RunPod pod to stop billing. Called by Terraform's destroy-time
# provisioner. The API key comes from the RUNPOD_API_KEY env var (never on the
# command line, so it does not leak into process listings or TF logs).
set -euo pipefail
POD_ID="${1:?usage: runpod_destroy.sh <pod_id>}"
: "${RUNPOD_API_KEY:?RUNPOD_API_KEY env var required}"

code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  "https://rest.runpod.io/v1/pods/${POD_ID}")

if [ "$code" = "200" ] || [ "$code" = "204" ]; then
  echo "pod ${POD_ID} deleted (HTTP ${code})"
else
  echo "warning: delete of pod ${POD_ID} returned HTTP ${code}" >&2
fi
