#!/usr/bin/env python3
"""Build a paddleocr calibration corpus from the synthetic LaTeX ground truth.

For every doc in ``groundtruth/corpus/latex/<doc>/`` that has both a
compiled ``<doc>.pdf`` and a ``<doc>.docling.json`` reference, this
script:

  1. converts the docling JSON into a ``truth.json`` in the calibration
     schema (CalibrationTruthDocument) under
     ``<out-root>/<doc>/truth.json``;
  2. runs ``pdf2md convert`` on the compiled PDF to get a canonical
     paddleocr connector output (``pages/`` + ``entities.json``);
  3. drops that connector output next to the truth file as
     ``<out-root>/<doc>/paddleocr/`` so that
     ``calibrate_priors.py --root <out-root>`` will discover it.

Convert failures are isolated per-document: the script keeps going,
records the failure, and reports a summary at the end.

Usage:
    conda run -n pdf2md python tools/build_paddle_calibration_set.py \
        --corpus-root groundtruth/corpus/latex \
        --out-root .tmp/calibration_corpus \
        [--limit N] [--force]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus-root", type=Path, default=Path("groundtruth/corpus/latex"))
    p.add_argument("--out-root", type=Path, default=Path(".tmp/calibration_corpus"))
    p.add_argument("--backend-config", type=Path, default=Path("pdf2md.backends.toml"))
    p.add_argument("--limit", type=int, default=None, help="Process at most N docs (for smoke tests).")
    p.add_argument("--force", action="store_true", help="Re-run paddleocr even if connector output exists.")
    p.add_argument("--timeout", type=int, default=600, help="Per-doc backend timeout (seconds).")
    return p.parse_args()


# ---------------------------------------------------------------------------
# docling.json -> truth.json conversion
# ---------------------------------------------------------------------------

def _page_no_from_prov(prov: list[dict]) -> int:
    """Return the first ``page_no`` in a docling prov[] list, defaulting to 1."""

    if not prov:
        return 1
    for entry in prov:
        page = entry.get("page_no") or entry.get("page")
        if isinstance(page, int) and page >= 1:
            return page
    return 1


# Docling-label -> EntityType (from pdf2md.models.entities.EntityType).
# Used in addition to blocks so the entity_type calibration target has real
# truth records, not "every prediction is a false positive".
_DOCLING_LABEL_TO_ENTITY_TYPE: dict[str, str] = {
    "title": "section",
    "section_header": "section",
    "heading": "section",
    "caption": "caption",
    "footnote": "footnote",
    "formula": "equation",
    "equation": "equation",
    "table": "table",
    "picture": "figure",
    "figure": "figure",
    "page_number": "page_number",
    "page_header": "header",
    "page_footer": "footer",
    "page-header": "header",
    "page-footer": "footer",
}


def _convert_docling_to_truth(docling_path: Path, document_id: str) -> dict:
    """Build a CalibrationTruthDocument payload from a DoclingDocument JSON.

    Populates both ``blocks`` (drives BlockKind priors) and ``entities``
    (drives EntityType / calibration_key priors). Without entities the
    paddleocr entity prior would degenerate to 0 (every prediction is an
    FP), which would unfairly suppress the entity_prior_weight signal in
    the consensus scorer.
    """

    payload = json.loads(docling_path.read_text(encoding="utf-8"))
    blocks: list[dict] = []
    entities: list[dict] = []

    def _append_entity(idx: int, kind: str, label: str, page_no: int, text: str | None) -> None:
        et = _DOCLING_LABEL_TO_ENTITY_TYPE.get(label)
        if et is None:
            return
        entities.append(
            {
                "id": f"truth:{document_id}:{kind}_entity:{idx}",
                "entity_type": et,
                "canonical_text": text,
                "page_no": page_no,
                "metadata": {},
            }
        )

    # texts[] is the bulk of the body
    for idx, text in enumerate(payload.get("texts") or []):
        label = text.get("label") or "text"
        page_no = _page_no_from_prov(text.get("prov") or [])
        text_value = text.get("text") or text.get("orig")
        blocks.append(
            {
                "id": f"truth:{document_id}:text:{idx}",
                "block_kind": label,  # normalised by truth loader
                "page_no": page_no,
                "text": text_value,
                "metadata": {},
            }
        )
        _append_entity(idx, "text", label, page_no, text_value)

    for idx, picture in enumerate(payload.get("pictures") or []):
        page_no = _page_no_from_prov(picture.get("prov") or [])
        text_value = picture.get("text") or None
        blocks.append(
            {
                "id": f"truth:{document_id}:picture:{idx}",
                "block_kind": "picture",
                "page_no": page_no,
                "text": text_value,
                "metadata": {},
            }
        )
        _append_entity(idx, "picture", "picture", page_no, text_value)

    for idx, table in enumerate(payload.get("tables") or []):
        page_no = _page_no_from_prov(table.get("prov") or [])
        text_value = table.get("text") or None
        blocks.append(
            {
                "id": f"truth:{document_id}:table:{idx}",
                "block_kind": "table",
                "page_no": page_no,
                "text": text_value,
                "metadata": {},
            }
        )
        _append_entity(idx, "table", "table", page_no, text_value)

    return {
        "schema_name": "pdf2md.CalibrationTruthDocument",
        "schema_version": "1.0.0",
        "document_id": document_id,
        "blocks": blocks,
        "entities": entities,
        "relations": [],
        "metadata": {
            "source": "synthetic_latex_corpus",
            "source_docling_json": str(docling_path.relative_to(ROOT))
            if str(docling_path).startswith(str(ROOT))
            else str(docling_path),
        },
    }


# ---------------------------------------------------------------------------
# Paddleocr run via `pdf2md convert`
# ---------------------------------------------------------------------------

def _run_convert(pdf_path: Path, out_dir: Path, backend_config: Path, timeout: int) -> tuple[bool, str]:
    """Drive ``pdf2md convert`` on a single PDF. Returns (ok, log_tail)."""

    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "conda",
        "run",
        "-n",
        "pdf2md",
        "python",
        "-m",
        "pdf2md.cli.main",
        "convert",
        str(pdf_path),
        "--config",
        str(backend_config),
        "--out-dir",
        str(out_dir),
        "--force",
        "--timeout",
        str(timeout),
    ]
    try:
        cp = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        return False, "subprocess timeout"
    output = (cp.stdout + cp.stderr).strip()
    # The pipeline exits 0 on success, 2 on partial, 1 on hard failure.
    ok = cp.returncode in (0, 2)
    return ok, output[-2000:]


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> int:
    args = _parse_args()
    corpus_root = (ROOT / args.corpus_root).resolve()
    out_root = (ROOT / args.out_root).resolve()
    if not corpus_root.is_dir():
        print(f"corpus root not found: {corpus_root}", file=sys.stderr)
        return 1
    out_root.mkdir(parents=True, exist_ok=True)

    doc_dirs = []
    for child in sorted(corpus_root.iterdir()):
        if not child.is_dir():
            continue
        doc_id = child.name
        pdf = child / f"{doc_id}.pdf"
        docling = child / f"{doc_id}.docling.json"
        if pdf.exists() and docling.exists():
            doc_dirs.append((doc_id, pdf, docling))

    if args.limit:
        doc_dirs = doc_dirs[: args.limit]

    print(f"discovered {len(doc_dirs)} candidate docs under {corpus_root}")

    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []
    skipped: list[str] = []
    started = time.time()

    for i, (doc_id, pdf, docling) in enumerate(doc_dirs, start=1):
        elapsed = time.time() - started
        rate = elapsed / max(i - 1, 1) if i > 1 else 0
        eta = (len(doc_dirs) - i + 1) * rate
        print(
            f"[{i}/{len(doc_dirs)}] {doc_id}  "
            f"(elapsed {elapsed:6.1f}s, eta {eta:6.1f}s)"
        )

        doc_out = out_root / doc_id
        doc_out.mkdir(parents=True, exist_ok=True)

        # 1. truth.json
        truth_path = doc_out / "truth.json"
        try:
            truth_payload = _convert_docling_to_truth(docling, doc_id)
            truth_path.write_text(json.dumps(truth_payload, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            failed.append((doc_id, f"truth conversion failed: {exc}"))
            continue

        # 2. paddleocr/ (skip if exists unless --force)
        paddle_dir = doc_out / "paddleocr"
        if paddle_dir.is_dir() and (paddle_dir / "entities.json").exists() and not args.force:
            skipped.append(doc_id)
            succeeded.append(doc_id)
            continue

        # 3. run convert into a scratch dir, then move its connector output
        scratch = out_root / "_scratch" / doc_id
        if scratch.exists():
            shutil.rmtree(scratch)
        scratch.mkdir(parents=True)
        ok, log_tail = _run_convert(pdf, scratch, args.backend_config, args.timeout)
        connector_src = scratch / "connector" / "paddleocr"
        if not ok or not (connector_src / "entities.json").exists():
            failed.append((doc_id, f"convert failed; last log: {log_tail[-400:]}"))
            shutil.rmtree(scratch, ignore_errors=True)
            continue

        if paddle_dir.exists():
            shutil.rmtree(paddle_dir)
        shutil.copytree(connector_src, paddle_dir)
        # remove scratch raw output to save disk
        shutil.rmtree(scratch, ignore_errors=True)
        succeeded.append(doc_id)

    total = time.time() - started
    print()
    print("=" * 70)
    print(f"build_paddle_calibration_set: {len(succeeded)} succeeded, {len(failed)} failed, {len(skipped)} reused")
    print(f"total wall time: {total:.1f}s")
    if failed:
        print("failed:")
        for doc_id, msg in failed:
            print(f"  - {doc_id}: {msg}")
    print(f"output root: {out_root}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
