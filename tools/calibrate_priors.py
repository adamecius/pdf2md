#!/usr/bin/env python
"""Build calibrated backend prior files from synthetic or corpus fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.calibration.io import (  # noqa: E402
    discover_calibration_inputs,
    load_calibration_document,
    read_backend_version,
    write_prior_outputs,
)
from pdf2md.calibration.matching import match_blocks, match_entities, match_relations  # noqa: E402
from pdf2md.calibration.metrics import CalibrationSettings, build_prior_document  # noqa: E402


def _parse_backends(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--backends")
    parser.add_argument("--min-samples", type=int, default=5)
    parser.add_argument("--smoothing-alpha", type=float, default=1.0)
    parser.add_argument("--smoothing-beta", type=float, default=1.0)
    parser.add_argument("--default-confidence", type=float, default=0.5)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        settings = CalibrationSettings(
            min_samples=args.min_samples,
            smoothing_alpha=args.smoothing_alpha,
            smoothing_beta=args.smoothing_beta,
            default_confidence=args.default_confidence,
        )
        requested_backends = _parse_backends(args.backends)
        inputs = discover_calibration_inputs(root=args.root, backends=requested_backends)
        records_by_backend = defaultdict(list)
        generated_from_by_backend = defaultdict(list)
        warnings_by_backend = defaultdict(list)
        versions = {}
        all_warnings: list[str] = []
        seen_backends = set(requested_backends or [])
        for item in inputs:
            result = load_calibration_document(item=item, strict=args.strict)
            all_warnings.extend(result.warnings)
            seen_backends.update(item.prediction_roots)
            if result.truth is None:
                all_warnings.append(f"truth_missing:{item.document_id}")
                continue
            for backend, root in item.prediction_roots.items():
                versions.setdefault(backend, read_backend_version(root))
                generated_from_by_backend[backend].append(str(item.truth_path))
                if backend in result.pages_by_backend:
                    records_by_backend[backend].extend(match_blocks(backend=backend, pages=result.pages_by_backend[backend], truth=result.truth))
                else:
                    warnings_by_backend[backend].append(f"pages_missing:{backend}")
                if backend in result.entities_by_backend:
                    entities = result.entities_by_backend[backend]
                    records_by_backend[backend].extend(match_entities(backend=backend, predictions=entities, truth=result.truth))
                    records_by_backend[backend].extend(match_relations(backend=backend, predictions=entities, truth=result.truth))
                else:
                    warnings_by_backend[backend].append(f"entities_missing:{backend}")
        priors = []
        for backend in sorted(seen_backends):
            backend_warnings = list(warnings_by_backend.get(backend, []))
            backend_warnings.extend(w for w in all_warnings if w.endswith(f":{backend}"))
            prior = build_prior_document(
                backend=backend,
                backend_version=versions.get(backend),
                generated_from=sorted(set(generated_from_by_backend.get(backend, []))),
                records=records_by_backend.get(backend, []),
                settings=settings,
                warnings=backend_warnings,
                metadata={"document_count": len(inputs)},
            )
            priors.append(prior)
        report = {
            "schema_name": "pdf2md.CalibrationReport",
            "schema_version": "1.0.0",
            "document_count": len(inputs),
            "backends": [prior.backend for prior in priors],
            "prior_files": {prior.backend: f"priors/{prior.backend}.json" for prior in priors},
            "warnings": all_warnings,
            "settings": {
                "min_samples": settings.min_samples,
                "smoothing_alpha": settings.smoothing_alpha,
                "smoothing_beta": settings.smoothing_beta,
                "default_confidence": settings.default_confidence,
            },
        }
        write_prior_outputs(priors=priors, report=report, out_dir=args.out_dir)
        if args.verbose:
            print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"calibrate_priors failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
