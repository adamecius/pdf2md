"""Filesystem I/O for consensus factory inputs and outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pdf2md.consensus.factory import ConsensusRunResult
from pdf2md.consensus.reporting import build_consensus_summary
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import ConsensusIR, PageExtractionIR
from pdf2md.models.priors import (
    CalibrationPriorDocument,
    build_uninformative_prior,
    load_factory_prior,
)


@dataclass(frozen=True)
class ConsensusInput:
    document_id: str
    connector_root: Path
    priors_root: Path | None
    backends: tuple[str, ...]


@dataclass(frozen=True)
class ConsensusLoadResult:
    pages_by_backend: dict[str, list[PageExtractionIR]]
    entities_by_backend: dict[str, EntityProposalDocument]
    priors_by_backend: dict[str, CalibrationPriorDocument]
    warnings: list[str]


def _load_json(path: Path):
    return json.loads(path.read_text())


def _warn_or_raise(strict: bool, warnings: list[str], warning: str, exc: Exception | None = None) -> None:
    if strict and exc is not None:
        raise exc
    warnings.append(warning)


def _discover_backends(connector_root: Path, backends: list[str] | None) -> list[str]:
    if backends:
        return backends
    return sorted(path.name for path in connector_root.iterdir() if path.is_dir() and path.name != "priors")


def _resolve_prior_with_fallback(
    *,
    backend: str,
    priors_root: Path | None,
    priors_by_backend: dict[str, CalibrationPriorDocument],
    warnings: list[str],
    strict: bool,
) -> None:
    """Plan 19 fallback chain: user prior on disk → factory prior → uninformative.

    Always populates ``priors_by_backend[backend]`` (never empty for a
    backend with page data) and appends a level-specific warning so the
    caller can tell which level was used:

      - user prior on disk: no warning (expected, silent)
      - factory: ``prior_factory:<backend>``
      - uninformative: ``prior_uninformative:<backend>``
    """

    if priors_root is not None:
        prior_path = priors_root / f"{backend}.json"
        if prior_path.exists():
            try:
                priors_by_backend[backend] = CalibrationPriorDocument.model_validate(_load_json(prior_path))
                return
            except Exception as exc:  # noqa: BLE001
                _warn_or_raise(strict, warnings, f"invalid_prior:{backend}", exc)
                # fall through to factory / uninformative
    factory = load_factory_prior(backend)
    if factory is not None:
        priors_by_backend[backend] = factory
        warnings.append(f"prior_factory:{backend}")
        return
    priors_by_backend[backend] = build_uninformative_prior(backend)
    warnings.append(f"prior_uninformative:{backend}")


def load_consensus_inputs(
    *,
    connector_root: Path,
    document_id: str,
    backends: list[str] | None = None,
    priors_root: Path | None = None,
    strict: bool = False,
) -> ConsensusLoadResult:
    warnings: list[str] = []
    pages_by_backend: dict[str, list[PageExtractionIR]] = {}
    entities_by_backend: dict[str, EntityProposalDocument] = {}
    priors_by_backend: dict[str, CalibrationPriorDocument] = {}
    for backend in _discover_backends(connector_root, backends):
        backend_dir = connector_root / backend
        if not backend_dir.exists():
            warnings.append(f"backend_missing:{backend}")
            continue
        pages_dir = backend_dir / "pages"
        if not pages_dir.exists():
            warnings.append(f"pages_missing:{backend}")
            continue
        pages: list[PageExtractionIR] = []
        for page_path in sorted(pages_dir.glob("*.json")):
            try:
                pages.append(PageExtractionIR.model_validate(_load_json(page_path)))
            except Exception as exc:  # noqa: BLE001 - strict mode re-raises exact input failure
                _warn_or_raise(strict, warnings, f"invalid_page:{backend}:{page_path.name}", exc)
        if pages:
            pages_by_backend[backend] = pages
        else:
            warnings.append(f"empty_pages:{backend}")
        entities_path = backend_dir / "entities.json"
        if entities_path.exists():
            try:
                entities_by_backend[backend] = EntityProposalDocument.model_validate(_load_json(entities_path))
            except Exception as exc:  # noqa: BLE001
                _warn_or_raise(strict, warnings, f"invalid_entities:{backend}", exc)
        else:
            warnings.append(f"entities_missing:{backend}")
        # Plan 19 — three-level prior fallback. Only backends that
        # produced page data need a prior at all (consensus has nothing
        # to score otherwise).
        if backend in pages_by_backend:
            _resolve_prior_with_fallback(
                backend=backend,
                priors_root=priors_root,
                priors_by_backend=priors_by_backend,
                warnings=warnings,
                strict=strict,
            )
    return ConsensusLoadResult(
        pages_by_backend=pages_by_backend,
        entities_by_backend=entities_by_backend,
        priors_by_backend=priors_by_backend,
        warnings=warnings,
    )


def write_consensus_outputs(*, result: ConsensusRunResult, out_dir: Path) -> None:
    reports_dir = out_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "consensus_ir.json").write_text(result.consensus.model_dump_json(indent=2))
    (reports_dir / "consensus_report.json").write_text(json.dumps(result.report, indent=2, sort_keys=True))
    (out_dir / "consensus_summary.txt").write_text(build_consensus_summary(result.report))
    ConsensusIR.model_validate_json((out_dir / "consensus_ir.json").read_text())
