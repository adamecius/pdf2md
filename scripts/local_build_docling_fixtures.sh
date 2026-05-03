#!/usr/bin/env bash
set -euo pipefail

BATCH="batch_001"
DOCS="all"
OUTPUT_ROOT=".current/docling_groundtruth"
CONSENSUS_CONFIG="pdf2md.consensus.example.toml"
BACKENDS="mineru,paddleocr,deepseek"
SKIP_LATEX=0
SKIP_BACKENDS=0
SKIP_DOCLING=0
VERBOSE=0
ALLOW_MISSING_BACKENDS=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --batch) BATCH="$2"; shift 2 ;;
    --documents) DOCS="$2"; shift 2 ;;
    --output-root) OUTPUT_ROOT="$2"; shift 2 ;;
    --consensus-config) CONSENSUS_CONFIG="$2"; shift 2 ;;
    --backends) BACKENDS="$2"; shift 2 ;;
    --skip-latex) SKIP_LATEX=1; shift ;;
    --skip-backends) SKIP_BACKENDS=1; shift ;;
    --skip-docling) SKIP_DOCLING=1; shift ;;
    --verbose) VERBOSE=1; shift ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

LATEX_ENGINE=""
if command -v latexmk >/dev/null 2>&1; then LATEX_ENGINE="latexmk"; fi
if [[ -z "$LATEX_ENGINE" ]] && command -v pdflatex >/dev/null 2>&1; then LATEX_ENGINE="pdflatex"; fi
if [[ -z "$LATEX_ENGINE" ]] && command -v tectonic >/dev/null 2>&1; then LATEX_ENGINE="tectonic"; fi

command -v python >/dev/null 2>&1 || { echo "python is required"; exit 1; }

if [[ "$DOCS" == "all" ]]; then
  DOC_IDS=(linked_sections_figures lists_footnotes_tables)
else
  IFS=',' read -r -a DOC_IDS <<< "$DOCS"
fi

backend_default_cmd() {
  case "$1" in
    paddleocr) [[ -f backend/paddleocr/pdf2ir_paddleocr.py ]] && echo "python backend/paddleocr/pdf2ir_paddleocr.py" ;;
    deepseek) [[ -f backend/deepseek/pdf2ir_deeepseek.py ]] && echo "python backend/deepseek/pdf2ir_deeepseek.py" ;;
    mineru) [[ -f backend/mineru/pdf2md_mineru.py ]] && echo "" ;;
  esac
}

IFS=',' read -r -a BACKEND_LIST <<< "$BACKENDS"

for doc_id in "${DOC_IDS[@]}"; do
  DOC_ROOT="$OUTPUT_ROOT/$BATCH/$doc_id"
  INPUT_DIR="$DOC_ROOT/input"; IR_DIR="$DOC_ROOT/backend_ir"; CONS_DIR="$DOC_ROOT/consensus"; DOCL_DIR="$DOC_ROOT/docling"; REP_DIR="$DOC_ROOT/reports"
  mkdir -p "$INPUT_DIR" "$IR_DIR" "$CONS_DIR" "$DOCL_DIR" "$REP_DIR"
  TEX="tests/docling_groundtruth/latex_sources/$BATCH/$doc_id.tex"
  cp "$TEX" "$INPUT_DIR/$doc_id.tex"

  if [[ "$SKIP_LATEX" -eq 0 ]]; then
    if [[ -z "$LATEX_ENGINE" ]]; then echo "No LaTeX engine found"; exit 1; fi
    case "$LATEX_ENGINE" in
      latexmk) (cd "$INPUT_DIR" && latexmk -pdf -interaction=nonstopmode "$doc_id.tex" >/dev/null) ;;
      pdflatex) (cd "$INPUT_DIR" && pdflatex -interaction=nonstopmode "$doc_id.tex" >/dev/null) ;;
      tectonic) (cd "$INPUT_DIR" && tectonic -o "$INPUT_DIR" "$doc_id.tex" >/dev/null) ;;
    esac
  fi

  for backend in "${BACKEND_LIST[@]}"; do
    mkdir -p "$IR_DIR/$backend"
    [[ "$SKIP_BACKENDS" -eq 1 ]] && continue
    env_var="PDF2MD_${backend^^}_PDF2IR_CMD"
    cmd="${!env_var:-}"
    if [[ -z "$cmd" ]]; then cmd="$(backend_default_cmd "$backend")"; fi
    log="$REP_DIR/backend_${backend}.log"
    if [[ -z "$cmd" ]]; then
      echo "backend=$backend missing command; set $env_var" | tee "$log"
      [[ "$ALLOW_MISSING_BACKENDS" -eq 1 ]] || exit 1
      continue
    fi
    bash -lc "$cmd '$INPUT_DIR/$doc_id.pdf' --output-root '$IR_DIR/$backend'" >"$log" 2>&1 || true
  done

  if [[ "$SKIP_BACKENDS" -eq 0 ]]; then
    python -m pdf2md.utils.consensus_report "$INPUT_DIR/$doc_id.pdf" --config "$CONSENSUS_CONFIG" --output "$CONS_DIR/consensus_report.json" ${VERBOSE:+--verbose} || true
    python -m pdf2md.utils.semantic_linker "$CONS_DIR/consensus_report.json" --output "$CONS_DIR/semantic_links.json" ${VERBOSE:+--verbose} || true
    python -m pdf2md.utils.media_materializer "$CONS_DIR/consensus_report.json" --semantic-links "$CONS_DIR/semantic_links.json" --output-root "$CONS_DIR" ${VERBOSE:+--verbose} || true
    python -m pdf2md.utils.semantic_document_builder "$CONS_DIR/consensus_report.json" --semantic-links "$CONS_DIR/semantic_links.json" --media-manifest "$CONS_DIR/media_manifest.json" --output "$CONS_DIR/semantic_document.json" ${VERBOSE:+--verbose} || true
  fi

  if [[ "$SKIP_DOCLING" -eq 0 && -f src/pdf2md/utils/docling_adapter.py ]]; then
    python -m pdf2md.utils.docling_adapter "$CONS_DIR/semantic_document.json" --output-root "$DOCL_DIR" --mode inspection --export-markdown ${VERBOSE:+--verbose} || true
  fi

  python tests/docling_groundtruth/tools/build_local_run_manifest.py >/dev/null 2>&1 || true
  python tests/docling_groundtruth/tools/validate_generated_contracts.py --generated-root "$OUTPUT_ROOT" --report-out "$REP_DIR/validation_report.json" --backends "$BACKENDS" || true
done

echo "Local-only fixture build completed: $OUTPUT_ROOT"
