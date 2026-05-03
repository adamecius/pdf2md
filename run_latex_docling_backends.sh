#!/usr/bin/env bash
set -u
BATCH=batch_001; ROOT=.current/latex_docling_groundtruth; CONFIG=pdf2md.consensus.example.toml; VERBOSE=0; ALLOW_MISSING_BACKENDS=0; ALLOW_MISSING_ENVS=0; ALLOW_STAGE_FAILURES=0
while [[ $# -gt 0 ]]; do case "$1" in
  --batch) BATCH="$2"; shift 2;; --root) ROOT="$2"; shift 2;; --config) CONFIG="$2"; shift 2;; --verbose) VERBOSE=1; shift;;
  --allow-missing-backends) ALLOW_MISSING_BACKENDS=1; shift;; --allow-missing-envs) ALLOW_MISSING_ENVS=1; shift;; --allow-stage-failures) ALLOW_STAGE_FAILURES=1; shift;; *) echo "unknown arg $1"; exit 2;; esac; done
set -e
batch_root="$ROOT/$BATCH"; [[ -d "$batch_root" ]] || { echo "missing $batch_root"; exit 1; }
backends=$(python - <<PY
import tomllib; c=tomllib.load(open('$CONFIG','rb')); print('\n'.join([k for k,v in c.get('backends',{}).items() if v.get('enabled',False)]))
PY
)
[[ -n "$backends" ]] || { echo "No enabled backends"; exit 1; }
status=0
for docdir in "$batch_root"/*; do
  [[ -d "$docdir/input" ]] || continue
  docid=$(basename "$docdir"); pdf="$docdir/input/$docid.pdf"; reports="$docdir/reports"; mkdir -p "$reports"
  run_manifest="$docdir/local_run_manifest.json"; echo '{"document_id":"'$docid'","backends":[]}' > "$run_manifest"
  for b in $backends; do
    blog="$reports/backend_${b}.log"; mkdir -p "$docdir/backend_ir/$b/.current/extraction_ir/$docid"
    override_var="PDF2MD_$(echo "$b" | tr '[:lower:]-' '[:upper:]_')_PDF2IR_CMD"; cmd="${!override_var-}"
    if [[ -z "$cmd" ]]; then
      cand1="backend/$b/pdf2ir_${b}.py"; cand=$(find "backend/$b" -maxdepth 1 -name 'pdf2ir*.py' | head -n1 || true)
      [[ -f "$cand1" ]] && cmd="python $cand1" || cmd="python ${cand:-}"
    fi
    if [[ -z "$cmd" || "$cmd" == "python " ]]; then [[ $ALLOW_MISSING_BACKENDS -eq 1 ]] && continue || { echo "missing adapter for $b"; exit 1; }; fi
    if ! command -v conda >/dev/null 2>&1; then [[ $ALLOW_MISSING_ENVS -eq 1 ]] && continue || { echo "conda missing"; exit 1; }; fi
    help=$($cmd --help 2>/dev/null || true)
    outbase="$docdir/backend_ir/$b/.current"; expected="$outbase/extraction_ir/$docid"; mkdir -p "$expected"
    arg_in="$pdf"; [[ "$help" == *"--input"* ]] && arg_in="--input $pdf" || ([[ "$help" == *"-i"* ]] && arg_in="-i $pdf")
    arg_out=""; [[ "$help" == *"--ir-dir"* ]] && arg_out="--ir-dir $expected" || ([[ "$help" == *"--out-dir"* ]] && arg_out="--out-dir $outbase" || ([[ "$help" == *"--output-root"* ]] && arg_out="--output-root $outbase"))
    set +e
    bash -lc "source \"\$(conda info --base)/etc/profile.d/conda.sh\" && conda activate pdf2md-$b && $cmd $arg_in $arg_out" >"$blog" 2>&1
    rc=$?
    set -e
    if [[ $rc -ne 0 ]]; then status=1; [[ $ALLOW_STAGE_FAILURES -eq 1 ]] || exit 1; fi
    [[ -f "$expected/manifest.json" && -d "$expected/pages" ]] || {
      mapfile -t cands < <(find "$docdir/backend_ir/$b" -name manifest.json)
      if [[ ${#cands[@]} -eq 1 ]]; then cp -r "$(dirname "${cands[0]}")"/* "$expected"/; else status=1; [[ $ALLOW_STAGE_FAILURES -eq 1 ]] || exit 1; fi
    }
  done
  conf="$docdir/consensus/local_consensus.toml"; mkdir -p "$docdir/consensus"
  {
    echo "[consensus]"; echo "output_root = \"$docdir/consensus\""; echo "coordinate_space = \"page_normalised_1000\""; echo "text_similarity_threshold = 0.90"; echo "weak_text_similarity_threshold = 0.75"; echo "bbox_iou_threshold = 0.50"; echo "weak_bbox_iou_threshold = 0.25"; echo "include_evidence_only_blocks = false"
    for b in $backends; do echo "[backends.$b]"; echo "enabled = true"; echo "root = \"$docdir/backend_ir/$b\""; echo "label = \"$b\""; done
    echo "[pymupdf]"; echo "enabled = true"; echo "extract_text = true"; echo "extract_images = false"
  } > "$conf"
  set +e
  PYTHONPATH=src python -m pdf2md.utils.consensus_report "$pdf" --config "$conf" --output "$docdir/consensus/consensus_report.json" --verbose >"$reports/consensus.log" 2>&1 || status=1
  PYTHONPATH=src python -m pdf2md.utils.semantic_linker "$docdir/consensus/consensus_report.json" --output "$docdir/consensus/semantic_links.json" --verbose >"$reports/semantic_linker.log" 2>&1 || status=1
  PYTHONPATH=src python -m pdf2md.utils.media_materializer "$docdir/consensus/consensus_report.json" --semantic-links "$docdir/consensus/semantic_links.json" --output-root "$docdir/consensus" --verbose >"$reports/media_materializer.log" 2>&1 || status=1
  PYTHONPATH=src python -m pdf2md.utils.semantic_document_builder "$docdir/consensus/consensus_report.json" --semantic-links "$docdir/consensus/semantic_links.json" --media-manifest "$docdir/consensus/media_manifest.json" --output "$docdir/consensus/semantic_document.json" --verbose >"$reports/semantic_document_builder.log" 2>&1 || status=1
  if [[ -f src/pdf2md/utils/docling_layer.py ]]; then mod=pdf2md.utils.docling_layer; else mod=pdf2md.utils.docling_adapter; fi
  PYTHONPATH=src python -m "$mod" "$docdir/consensus/semantic_document.json" --output-root "$docdir/docling" --mode inspection --export-markdown --verbose >"$reports/docling.log" 2>&1 || status=1
  set -e
  [[ $status -eq 0 || $ALLOW_STAGE_FAILURES -eq 1 ]] || exit 1
done
[[ $status -eq 0 ]] || exit 1
echo "Completed with status=$status"
