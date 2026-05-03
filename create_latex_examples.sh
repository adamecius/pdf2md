#!/usr/bin/env bash
set -euo pipefail

BATCH="batch_001"
OUT_ROOT=".current/docling_groundtruth"
DOCS=(linked_sections_figures lists_footnotes_tables)

if [[ "${1:-}" == "--help" ]]; then
  cat <<USAGE
Usage: ./create_latex_examples.sh [output_root]

Generates fixture PDFs from LaTeX sources and raster renders (PNG).
- output_root defaults to .current/docling_groundtruth
USAGE
  exit 0
fi

if [[ $# -ge 1 ]]; then
  OUT_ROOT="$1"
fi

python - <<'PY'
from tests.docling_groundtruth.tools.check_latex_support import detect_latex_support
s = detect_latex_support()
if not s.available:
    raise SystemExit(f"No LaTeX engine available: {s.reason}")
print(f"LaTeX engine: {s.engine}")
PY

for doc in "${DOCS[@]}"; do
  src="tests/docling_groundtruth/latex_sources/${BATCH}/${doc}.tex"
  out_dir="${OUT_ROOT}/${BATCH}/${doc}/input"
  mkdir -p "$out_dir"
  cp "$src" "$out_dir/${doc}.tex"

  python - <<PY
from pathlib import Path
from tests.docling_groundtruth.tools.generate_latex_fixtures import generate_pdf
tex = Path("$src")
out_pdf = Path("$out_dir/$doc.pdf")
ok = generate_pdf(tex, out_pdf)
if not ok:
    raise SystemExit("PDF generation failed for $doc")
print(f"Generated: {out_pdf}")
PY

  render_dir="${OUT_ROOT}/${BATCH}/${doc}/renders"
  mkdir -p "$render_dir"

  if command -v pdftoppm >/dev/null 2>&1; then
    pdftoppm -png "$out_dir/$doc.pdf" "$render_dir/$doc" >/dev/null
  elif command -v magick >/dev/null 2>&1; then
    magick -density 180 "$out_dir/$doc.pdf" "$render_dir/$doc-%03d.png"
  else
    echo "warning: no renderer found (pdftoppm or magick). PDF was generated but no PNG renders." >&2
  fi

done

echo "Done. Outputs written under: $OUT_ROOT"
