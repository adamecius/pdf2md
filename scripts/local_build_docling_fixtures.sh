#!/usr/bin/env bash
set -euo pipefail

BATCH="batch_001"; DOCS="all"; OUTPUT_ROOT=".current/docling_groundtruth"; CONSENSUS_CONFIG="pdf2md.consensus.example.toml"
BACKENDS="mineru,paddleocr,deepseek"; SKIP_LATEX=0; SKIP_BACKENDS=0; SKIP_DOCLING=0; VERBOSE=0; ALLOW_MISSING_BACKENDS=0; ALLOW_STAGE_FAILURES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --batch) BATCH="$2"; shift 2;; --documents) DOCS="$2"; shift 2;; --output-root) OUTPUT_ROOT="$2"; shift 2;; --consensus-config) CONSENSUS_CONFIG="$2"; shift 2;; --backends) BACKENDS="$2"; shift 2;;
    --skip-latex) SKIP_LATEX=1; shift;; --skip-backends) SKIP_BACKENDS=1; shift;; --skip-docling) SKIP_DOCLING=1; shift;; --verbose) VERBOSE=1; shift;; --allow-stage-failures) ALLOW_STAGE_FAILURES=1; shift;; --allow-missing-backends) ALLOW_MISSING_BACKENDS=1; shift;;
    *) echo "Unknown arg: $1"; exit 2;;
  esac
done

LATEX_ENGINE=""; command -v latexmk >/dev/null && LATEX_ENGINE="latexmk" || true; [[ -z "$LATEX_ENGINE" ]] && command -v pdflatex >/dev/null && LATEX_ENGINE="pdflatex" || true; [[ -z "$LATEX_ENGINE" ]] && command -v tectonic >/dev/null && LATEX_ENGINE="tectonic" || true
[[ "$DOCS" == "all" ]] && DOC_IDS=(linked_sections_figures lists_footnotes_tables) || IFS=',' read -r -a DOC_IDS <<< "$DOCS"
IFS=',' read -r -a BACKEND_LIST <<< "$BACKENDS"

backend_default_cmd(){ case "$1" in paddleocr) [[ -f backend/paddleocr/pdf2ir_paddleocr.py ]] && echo "python backend/paddleocr/pdf2ir_paddleocr.py";; deepseek) [[ -f backend/deepseek/pdf2ir_deeepseek.py ]] && echo "python backend/deepseek/pdf2ir_deeepseek.py";; mineru) echo "";; esac; }
normalize_backend_output(){
  local backend_root="$1" pdf_stem="$2"
  local expected="$backend_root/.current/extraction_ir/$pdf_stem"
  mkdir -p "$expected"
  if [[ -f "$expected/manifest.json" ]]; then return 0; fi
  if [[ -f "$backend_root/manifest.json" ]]; then
    cp -r "$backend_root"/* "$expected/" 2>/dev/null || true
  fi
  if [[ ! -f "$expected/manifest.json" ]]; then
    local candidate
    candidate="$(find "$backend_root" -type f -name manifest.json | head -n 1 || true)"
    if [[ -n "$candidate" ]]; then
      cp -r "$(dirname "$candidate")"/* "$expected/" 2>/dev/null || true
    fi
  fi
}

any_failure=0
for doc_id in "${DOC_IDS[@]}"; do
  DOC_ROOT="$OUTPUT_ROOT/$BATCH/$doc_id"; INPUT_DIR="$DOC_ROOT/input"; IR_DIR="$DOC_ROOT/backend_ir"; CONS_DIR="$DOC_ROOT/consensus"; DOCL_DIR="$DOC_ROOT/docling"; REP_DIR="$DOC_ROOT/reports"; mkdir -p "$INPUT_DIR" "$IR_DIR" "$CONS_DIR" "$DOCL_DIR" "$REP_DIR"
  TEX="tests/docling_groundtruth/latex_sources/$BATCH/$doc_id.tex"; cp "$TEX" "$INPUT_DIR/$doc_id.tex"; PDF_STEM="$doc_id"
  declare -A STAGE_RC; declare -A STAGE_LOG; declare -A BACKEND_CMD

  if [[ "$SKIP_LATEX" -eq 0 ]]; then
    [[ -n "$LATEX_ENGINE" ]] || { echo "No LaTeX engine found"; exit 1; }
    log="$REP_DIR/latex.log"; STAGE_LOG[latex]="$log"
    python - <<PY >"$log" 2>&1
from pathlib import Path
from tests.docling_groundtruth.tools.generate_latex_fixtures import generate_pdf
ok = generate_pdf(Path("$TEX"), Path("$INPUT_DIR/$doc_id.pdf"))
raise SystemExit(0 if ok else 1)
PY
    STAGE_RC[latex]=$?
  else STAGE_RC[latex]=0; fi

  for backend in "${BACKEND_LIST[@]}"; do
    backend_root="$IR_DIR/$backend"; mkdir -p "$backend_root/.current/extraction_ir/$PDF_STEM"
    [[ "$SKIP_BACKENDS" -eq 1 ]] && { STAGE_RC[backend_$backend]=0; continue; }
    env_var="PDF2MD_${backend^^}_PDF2IR_CMD"; cmd="${!env_var:-}"; [[ -z "$cmd" ]] && cmd="$(backend_default_cmd "$backend")" || true
    log="$REP_DIR/backend_${backend}.log"; STAGE_LOG[backend_$backend]="$log"; BACKEND_CMD[$backend]="$cmd"
    if [[ -z "$cmd" ]]; then
      echo "backend=$backend missing command; set $env_var" >"$log"; STAGE_RC[backend_$backend]=127
      [[ "$ALLOW_MISSING_BACKENDS" -eq 1 ]] || { echo "Missing backend command for $backend"; exit 1; }
      continue
    fi
    bash -lc "$cmd '$INPUT_DIR/$doc_id.pdf' --output-root '$backend_root/.current/extraction_ir/$PDF_STEM'" >"$log" 2>&1 || true
    STAGE_RC[backend_$backend]=$?
    normalize_backend_output "$backend_root" "$PDF_STEM"
  done

  for backend in "${BACKEND_LIST[@]}"; do
    rc="${STAGE_RC[backend_$backend]:-0}"
    if [[ "$SKIP_BACKENDS" -eq 0 && "$rc" -ne 0 && "$ALLOW_STAGE_FAILURES" -eq 0 ]]; then
      echo "Stopping before consensus due to backend failure: $backend rc=$rc"
      exit 1
    fi
  done

  DOC_CFG="$REP_DIR/consensus_config.$doc_id.toml"
  cat > "$DOC_CFG" <<CFG
[consensus]
output_root = "$CONS_DIR"
coordinate_space = "page_normalised_1000"
text_similarity_threshold = 0.90
weak_text_similarity_threshold = 0.75
bbox_iou_threshold = 0.50
weak_bbox_iou_threshold = 0.25
include_evidence_only_blocks = false

[backends.mineru]
enabled = true
root = "$IR_DIR/mineru"
label = "mineru"

[backends.paddleocr]
enabled = true
root = "$IR_DIR/paddleocr"
label = "paddleocr"

[backends.deepseek]
enabled = true
root = "$IR_DIR/deepseek"
label = "deepseek"

[pymupdf]
enabled = true
extract_text = true
extract_images = false
CFG

  if [[ "$SKIP_BACKENDS" -eq 0 ]]; then
    python -m pdf2md.utils.consensus_report "$INPUT_DIR/$doc_id.pdf" --config "$DOC_CFG" --output "$CONS_DIR/consensus_report.json" ${VERBOSE:+--verbose} >"$REP_DIR/consensus.log" 2>&1; STAGE_RC[consensus]=$?; STAGE_LOG[consensus]="$REP_DIR/consensus.log"
    python -m pdf2md.utils.semantic_linker "$CONS_DIR/consensus_report.json" --output "$CONS_DIR/semantic_links.json" ${VERBOSE:+--verbose} >"$REP_DIR/semantic_linker.log" 2>&1; STAGE_RC[semantic_linker]=$?; STAGE_LOG[semantic_linker]="$REP_DIR/semantic_linker.log"
    python -m pdf2md.utils.media_materializer "$CONS_DIR/consensus_report.json" --semantic-links "$CONS_DIR/semantic_links.json" --output-root "$CONS_DIR" ${VERBOSE:+--verbose} >"$REP_DIR/media_materializer.log" 2>&1; STAGE_RC[media_materializer]=$?; STAGE_LOG[media_materializer]="$REP_DIR/media_materializer.log"
    python -m pdf2md.utils.semantic_document_builder "$CONS_DIR/consensus_report.json" --semantic-links "$CONS_DIR/semantic_links.json" --media-manifest "$CONS_DIR/media_manifest.json" --output "$CONS_DIR/semantic_document.json" ${VERBOSE:+--verbose} >"$REP_DIR/semantic_document_builder.log" 2>&1; STAGE_RC[semantic_document_builder]=$?; STAGE_LOG[semantic_document_builder]="$REP_DIR/semantic_document_builder.log"
  fi

  if [[ "$SKIP_DOCLING" -eq 0 && -f src/pdf2md/utils/docling_adapter.py ]]; then
    python -m pdf2md.utils.docling_adapter "$CONS_DIR/semantic_document.json" --output-root "$DOCL_DIR" --mode inspection --export-markdown ${VERBOSE:+--verbose} >"$REP_DIR/docling_adapter.log" 2>&1; STAGE_RC[docling_adapter]=$?; STAGE_LOG[docling_adapter]="$REP_DIR/docling_adapter.log"
  fi

  stage_args=(); for k in "${!STAGE_RC[@]}"; do stage_args+=(--stage "$k:${STAGE_RC[$k]}:${STAGE_LOG[$k]:-}"); done
  backend_args=(); for k in "${!BACKEND_CMD[@]}"; do backend_args+=(--backend-command "$k=${BACKEND_CMD[$k]}"); done
  python tests/docling_groundtruth/tools/build_local_run_manifest.py --output "$REP_DIR/local_run_manifest.json" --document-id "$doc_id" --batch "$BATCH" --input-pdf "$INPUT_DIR/$doc_id.pdf" --source-tex "$TEX" --consensus-config "$DOC_CFG" --latex-engine "$LATEX_ENGINE" "${backend_args[@]}" "${stage_args[@]}" --artifact consensus_report="$CONS_DIR/consensus_report.json" --artifact semantic_links="$CONS_DIR/semantic_links.json" --artifact semantic_document="$CONS_DIR/semantic_document.json" --artifact docling_report="$DOCL_DIR/docling_adapter_report.json" --artifact docling_preview="$DOCL_DIR/docling_preview.md"

  python tests/docling_groundtruth/tools/validate_generated_contracts.py --generated-root "$OUTPUT_ROOT" --report-out "$REP_DIR/validation_report.json" --backends "$BACKENDS" || true

  for k in "${!STAGE_RC[@]}"; do
    if [[ ${STAGE_RC[$k]} -ne 0 ]]; then
      any_failure=1
      [[ "$ALLOW_STAGE_FAILURES" -eq 1 ]] || { echo "Stage failed: $doc_id:$k rc=${STAGE_RC[$k]}"; exit 1; }
    fi
  done
done

if [[ "$any_failure" -eq 1 ]]; then
  echo "Completed with failures (allowed)."; exit 1
fi

echo "Local-only fixture build completed successfully: $OUTPUT_ROOT"
