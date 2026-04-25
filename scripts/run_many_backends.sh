#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <input.pdf> <backend_id> [<backend_id> ...]" >&2
  exit 1
fi

INPUT_PDF="$1"
shift

for BACKEND_ID in "$@"; do
  echo "=== Running backend: $BACKEND_ID ==="
  scripts/run_backend.sh "$BACKEND_ID" "$INPUT_PDF"
done
