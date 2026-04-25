#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 <backend_id> <input.pdf> [run_root]" >&2
  exit 1
fi

BACKEND_ID="$1"
INPUT_PDF="$2"
RUN_ROOT="${3:-runs}"
CATALOG_PATH="backend_catalog.yaml"

if [[ ! -f "$CATALOG_PATH" ]]; then
  echo "Missing $CATALOG_PATH at repository root." >&2
  exit 1
fi

if [[ ! -f "$INPUT_PDF" ]]; then
  echo "Input PDF not found: $INPUT_PDF" >&2
  exit 1
fi

DOC_ID="$(basename "$INPUT_PDF")"
DOC_ID="${DOC_ID%.pdf}"
RUN_DIR="$RUN_ROOT/$DOC_ID/$BACKEND_ID"
mkdir -p "$RUN_DIR"

REGISTRY_NAME="$(python - <<'PY' "$CATALOG_PATH" "$BACKEND_ID"
import sys
import yaml

catalog_path, backend_id = sys.argv[1], sys.argv[2]
with open(catalog_path, 'r', encoding='utf-8') as f:
    catalog = yaml.safe_load(f) or {}

backends = catalog.get('backends', {})
if backend_id not in backends:
    available = ', '.join(sorted(backends)) or 'none'
    raise SystemExit(f"Unknown backend_id '{backend_id}'. Available: {available}")

print(backends[backend_id]['registry_name'])
PY
)"

if [[ "$REGISTRY_NAME" == "deterministic" ]]; then
  python -m doc2md "$INPUT_PDF" -o "$RUN_DIR" --emit-docir
  GENERATED_DOCIR="$RUN_DIR/$DOC_ID.docir.json"
  if [[ -f "$GENERATED_DOCIR" ]]; then
    cp "$GENERATED_DOCIR" "$RUN_DIR/document.docir.json"
  fi
  echo "Run output: $RUN_DIR"
  exit 0
fi

python - <<'PY' "$REGISTRY_NAME" "$INPUT_PDF" "$RUN_DIR"
import json
import sys
from pathlib import Path

from doc2md.backends.base import OptionalBackendUnavailable
from doc2md.backends.registry import create_backend
from doc2md.ir import to_dict

registry_name, input_pdf, run_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])

try:
    backend = create_backend(registry_name)
    doc = backend.extract(input_pdf, output_dir=run_dir)
except OptionalBackendUnavailable as exc:
    raise SystemExit(f"Optional backend unavailable: {exc}") from exc
except RuntimeError as exc:
    raise SystemExit(f"Backend runtime error: {exc}") from exc

payload = to_dict(doc)
out_path = run_dir / "document.docir.json"
out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Run output: {run_dir}")
PY
