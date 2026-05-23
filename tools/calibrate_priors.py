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
from pdf2md.calibration.vocabulary import (  # noqa: E402
    build_vocabulary_alignment_report,
    scan_truth_root_labels,
    write_vocabulary_alignment_report,
)
from pdf2md.models.priors import CalibrationStatus  # noqa: E402


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
    parser.add_argument(
        "--skip-vocabulary-gate",
        action="store_true",
        help=(
            "Skip the BlockKind vocabulary alignment gate. Use only when calibration "
            "is being run against truth files known to already carry canonical labels."
        ),
    )
    return parser


def _prior_safe_for_consensus(prior) -> bool:
    """A backend prior is safe for consensus if any block-kind metric is calibrated."""

    return any(
        (metric.status if isinstance(metric.status, str) else metric.status.value)
        == CalibrationStatus.CALIBRATED.value
        for metric in prior.block_kind_priors
    )


def _summarise_metrics(metrics) -> dict[str, int]:
    """Tally CalibrationStatus values across a metric list."""

    counts = {"calibrated": 0, "underpowered": 0, "no_samples": 0}
    for metric in metrics:
        value = metric.status if isinstance(metric.status, str) else metric.status.value
        counts[value] = counts.get(value, 0) + 1
    return counts


def _backend_calibration_status(prior, has_inputs: bool) -> str:
    """Per-backend Plan 12 status taxonomy."""

    if not has_inputs:
        return "insufficient_backend_output"
    block_counts = _summarise_metrics(prior.block_kind_priors)
    if block_counts["calibrated"] > 0:
        return "calibrated"
    if block_counts["underpowered"] > 0:
        return "underpowered"
    return "no_samples"


def _plan13_readiness(priors, backend_inputs_seen: dict) -> dict:
    """Summarise which priors are safe for Plan 13 weighted ConsensusIR."""

    safe: list[str] = []
    underpowered: list[str] = []
    no_samples: list[str] = []
    blocked: list[str] = []
    per_backend: dict[str, dict] = {}
    for prior in priors:
        has_inputs = backend_inputs_seen.get(prior.backend, False)
        status = _backend_calibration_status(prior, has_inputs)
        block_counts = _summarise_metrics(prior.block_kind_priors)
        entity_counts = _summarise_metrics(prior.entity_type_priors)
        relation_counts = _summarise_metrics(prior.relation_type_priors)
        per_backend[prior.backend] = {
            "status": status,
            "block_kind_priors": block_counts,
            "entity_type_priors": entity_counts,
            "relation_type_priors": relation_counts,
            "warnings": list(prior.warnings),
        }
        if status == "calibrated" and _prior_safe_for_consensus(prior):
            safe.append(prior.backend)
        elif status == "underpowered":
            underpowered.append(prior.backend)
        elif status == "no_samples":
            no_samples.append(prior.backend)
        else:
            blocked.append(prior.backend)
    return {
        "safe_for_consensus": safe,
        "underpowered": underpowered,
        "no_samples": no_samples,
        "blocked": blocked,
        "per_backend": per_backend,
    }


def _summary_text(report: dict, vocab_passed: bool | None) -> str:
    lines = [
        "pdf2md calibration prior summary (Plan 12)",
        f"schema: {report['schema_name']} {report['schema_version']}",
        f"document_count: {report['document_count']}",
        f"backends: {report['backends']}",
        f"prior_files: {report['prior_files']}",
        (
            "vocabulary_alignment_passed: "
            + ("(skipped)" if vocab_passed is None else str(vocab_passed).lower())
        ),
        "",
        "Plan 13 readiness:",
    ]
    p13 = report.get("plan13_readiness", {})
    lines.append(f"- safe_for_consensus: {p13.get('safe_for_consensus', [])}")
    lines.append(f"- underpowered: {p13.get('underpowered', [])}")
    lines.append(f"- no_samples: {p13.get('no_samples', [])}")
    lines.append(f"- blocked: {p13.get('blocked', [])}")
    per_backend = p13.get("per_backend", {})
    if per_backend:
        lines.extend(["", "per-backend detail:"])
        for backend, detail in per_backend.items():
            lines.append(
                f"- {backend} [{detail['status']}] block_kind_priors={detail['block_kind_priors']}"
            )
    if report.get("warnings"):
        lines.extend(["", "warnings:"])
        lines.extend(f"- {w}" for w in report["warnings"])
    lines.extend(
        [
            "",
            "Weighted ConsensusIR (Plan 13) is the consumer of these priors. "
            "Plan 12 itself does not build consensus.",
        ]
    )
    return "\n".join(lines) + "\n"


def _run_vocabulary_gate(
    *,
    root: Path,
    out_dir: Path,
) -> tuple[bool, str | None, dict]:
    """Run the vocabulary alignment gate. Returns (passed, report_path, observed_labels)."""

    observed, _errors = scan_truth_root_labels(root)
    vocab_report = build_vocabulary_alignment_report(
        truth_root=root,
        observed_labels=observed,
    )
    write_vocabulary_alignment_report(report=vocab_report, out_dir=out_dir)
    report_path = str(out_dir / "reports" / "blockkind_vocabulary_alignment_report.json")
    return vocab_report.mandatory_mapping_passed, report_path, dict(observed)


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        vocabulary_alignment_report_path: str | None = None
        vocabulary_alignment_passed: bool | None = None
        if not args.skip_vocabulary_gate:
            vocabulary_alignment_passed, vocabulary_alignment_report_path, _observed = (
                _run_vocabulary_gate(root=args.root, out_dir=args.out_dir)
            )
            if not vocabulary_alignment_passed:
                print(
                    "calibrate_priors: vocabulary alignment gate failed; see "
                    f"{vocabulary_alignment_report_path}",
                    file=sys.stderr,
                )
                if args.strict:
                    return 1

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
        backend_inputs_seen: dict[str, bool] = {}
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
                has_inputs = False
                if backend in result.pages_by_backend:
                    records_by_backend[backend].extend(match_blocks(backend=backend, pages=result.pages_by_backend[backend], truth=result.truth))
                    has_inputs = has_inputs or bool(result.pages_by_backend[backend])
                else:
                    warnings_by_backend[backend].append(f"pages_missing:{backend}")
                if backend in result.entities_by_backend:
                    entities = result.entities_by_backend[backend]
                    records_by_backend[backend].extend(match_entities(backend=backend, predictions=entities, truth=result.truth))
                    records_by_backend[backend].extend(match_relations(backend=backend, predictions=entities, truth=result.truth))
                    has_inputs = True
                else:
                    warnings_by_backend[backend].append(f"entities_missing:{backend}")
                backend_inputs_seen[backend] = backend_inputs_seen.get(backend, False) or has_inputs
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
        plan13_readiness = _plan13_readiness(priors, backend_inputs_seen)
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
            "vocabulary_alignment_report": vocabulary_alignment_report_path,
            "plan13_readiness": plan13_readiness,
        }
        write_prior_outputs(priors=priors, report=report, out_dir=args.out_dir)
        summary_path = Path(args.out_dir) / "reports" / "calibration_summary.txt"
        summary_path.write_text(_summary_text(report, vocabulary_alignment_passed), encoding="utf-8")
        if args.verbose:
            print(json.dumps(report, indent=2, sort_keys=True))
        if args.strict and vocabulary_alignment_passed is False:
            return 1
        return 0
    except Exception as exc:
        print(f"calibrate_priors failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
