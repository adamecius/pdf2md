#!/usr/bin/env python3
"""Run mineru-OCR on the synthetic LaTeX corpus and drop outputs into the
same ``.tmp/calibration_corpus/`` layout used by the paddle and deepseek
loops. Pinned to GPU0 via ``pdf2md.backends.mineru-only.toml``.

Usage:
    conda run -n pdf2md python tools/build_mineru_calibration_set.py \
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
sys.path.insert(0, str(ROOT / "tools"))
from build_paddle_calibration_set import _convert_docling_to_truth  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus-root", type=Path, default=Path("groundtruth/corpus/latex"))
    p.add_argument("--out-root", type=Path, default=Path(".tmp/calibration_corpus"))
    p.add_argument("--backend-config", type=Path, default=Path("pdf2md.backends.mineru-only.toml"))
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--timeout", type=int, default=900)
    return p.parse_args()


def _run_convert(pdf_path: Path, out_dir: Path, backend_config: Path, timeout: int) -> tuple[bool, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "conda", "run", "-n", "pdf2md",
        "python", "-m", "pdf2md.cli.main",
        "convert", str(pdf_path),
        "--config", str(backend_config),
        "--out-dir", str(out_dir),
        "--force",
        "--timeout", str(timeout),
    ]
    try:
        cp = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout + 60)
    except subprocess.TimeoutExpired:
        return False, "subprocess timeout"
    output = (cp.stdout + cp.stderr).strip()
    return cp.returncode in (0, 2), output[-2000:]


def main() -> int:
    args = _parse_args()
    corpus_root = (ROOT / args.corpus_root).resolve()
    out_root = (ROOT / args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    if not corpus_root.is_dir():
        print(f"corpus root not found: {corpus_root}", file=sys.stderr)
        return 1

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
        print(f"[{i}/{len(doc_dirs)}] {doc_id}  (elapsed {elapsed:6.1f}s, eta {eta:6.1f}s)")

        doc_out = out_root / doc_id
        doc_out.mkdir(parents=True, exist_ok=True)

        truth_path = doc_out / "truth.json"
        if not truth_path.exists():
            try:
                truth = _convert_docling_to_truth(docling, doc_id)
                truth_path.write_text(json.dumps(truth, indent=2), encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                failed.append((doc_id, f"truth conversion failed: {exc}"))
                continue

        mineru_dir = doc_out / "mineru"
        if mineru_dir.is_dir() and (mineru_dir / "entities.json").exists() and not args.force:
            skipped.append(doc_id)
            succeeded.append(doc_id)
            continue

        scratch = out_root / "_scratch_mineru" / doc_id
        if scratch.exists():
            shutil.rmtree(scratch)
        scratch.mkdir(parents=True)
        ok, log_tail = _run_convert(pdf, scratch, args.backend_config, args.timeout)
        connector_src = scratch / "connector" / "mineru"
        if not ok or not (connector_src / "entities.json").exists():
            failed.append((doc_id, f"convert failed; last log: {log_tail[-400:]}"))
            shutil.rmtree(scratch, ignore_errors=True)
            continue
        if mineru_dir.exists():
            shutil.rmtree(mineru_dir)
        shutil.copytree(connector_src, mineru_dir)
        shutil.rmtree(scratch, ignore_errors=True)
        succeeded.append(doc_id)

    total = time.time() - started
    print()
    print("=" * 70)
    print(f"build_mineru_calibration_set: {len(succeeded)} succeeded, {len(failed)} failed, {len(skipped)} reused")
    print(f"total wall time: {total:.1f}s")
    if failed:
        print("failed:")
        for doc_id, msg in failed:
            print(f"  - {doc_id}: {msg}")
    print(f"output root: {out_root}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
