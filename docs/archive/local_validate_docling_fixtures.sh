#!/usr/bin/env bash
set -euo pipefail
GENERATED_ROOT="${1:-.current/docling_groundtruth}"
BACKENDS="${PDF2MD_VALIDATION_BACKENDS:-mineru,paddleocr,deepseek}"
python tests/docling_groundtruth/tools/validate_generated_contracts.py \
  --generated-root "$GENERATED_ROOT" \
  --backends "$BACKENDS" \
  --report-out "$GENERATED_ROOT/validation_report.json"
