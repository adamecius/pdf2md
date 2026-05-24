"""Filesystem I/O for semantic linker inputs and outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from pdf2md.linking.builder import LinkerRunResult
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import ConsensusIR
from pdf2md.models.priors import CalibrationPriorDocument

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class LinkerLoadResult:
    """Inputs gathered from disk for a single semantic linker run.

    Attributes:
        consensus: Parsed consensus IR for the document.
        consensus_report: Parsed consensus report payload, or None when
            absent or invalid in non-strict mode.
        entities_by_backend: Entity proposal documents keyed by backend name.
        priors_by_backend: Calibration prior documents keyed by backend name.
        source_entity_documents: Source file paths of the loaded entity
            documents, for traceability.
        source_prior_documents: Source file paths of the loaded prior
            documents, for traceability.
        warnings: Stable warning codes from the load pass.
    """

    consensus: ConsensusIR
    consensus_report: dict[str, Any] | None
    entities_by_backend: dict[str, EntityProposalDocument]
    priors_by_backend: dict[str, CalibrationPriorDocument]
    source_entity_documents: list[str]
    source_prior_documents: list[str]
    warnings: list[str]


def _read_model(path: Path, model: type[T]) -> T:
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def _entity_files(root: Path) -> list[Path]:
    files = [p for p in root.glob("*.json") if p.is_file()]
    files.extend(p / "entities.json" for p in root.iterdir() if p.is_dir() and (p / "entities.json").exists())
    return sorted(files)


def load_linker_inputs(
    *,
    consensus_ir_path: Path,
    consensus_report_path: Path | None = None,
    entities_root: Path | None = None,
    priors_root: Path | None = None,
    strict: bool = False,
) -> LinkerLoadResult:
    """Load the consensus IR plus per-backend entities and priors from disk.

    Entity files are discovered as ``<root>/*.json`` or
    ``<root>/<backend>/entities.json``. Prior files are loaded from
    ``<priors_root>/*.json``. Missing optional roots, missing per-backend
    files, and validation failures are recorded as stable warning codes;
    strict mode promotes the first such issue to an exception.

    Args:
        consensus_ir_path: Path to the consensus IR JSON.
        consensus_report_path: Optional path to the consensus report JSON.
        entities_root: Optional directory containing per-backend entity JSONs.
        priors_root: Optional directory containing per-backend prior JSONs.
        strict: When True, raise on input problems instead of recording them.

    Returns:
        A ``LinkerLoadResult`` containing the parsed inputs, source paths,
        and any accumulated warnings.

    Raises:
        ValueError: If the consensus IR is invalid, or in strict mode for any
            other input problem.
    """
    warnings: list[str] = []
    try:
        consensus = _read_model(consensus_ir_path, ConsensusIR)
    except Exception as exc:
        raise ValueError("invalid_consensus_ir") from exc

    consensus_report = None
    if consensus_report_path is None or not consensus_report_path.exists():
        warnings.append("consensus_report_missing")
        if strict and consensus_report_path is not None:
            raise ValueError("consensus_report_missing")
    else:
        try:
            consensus_report = _read_json(consensus_report_path)
        except Exception as exc:
            warnings.append("invalid_consensus_report")
            if strict:
                raise ValueError("invalid_consensus_report") from exc

    entities_by_backend: dict[str, EntityProposalDocument] = {}
    source_entity_documents: list[str] = []
    if entities_root is None or not entities_root.exists():
        warnings.append("entities_root_missing")
        if strict and entities_root is not None:
            raise ValueError("entities_root_missing")
    else:
        for path in _entity_files(entities_root):
            backend = path.stem if path.name != "entities.json" else path.parent.name
            try:
                document = _read_model(path, EntityProposalDocument)
                entities_by_backend[document.backend] = document
                source_entity_documents.append(str(path))
            except Exception as exc:
                warnings.append(f"invalid_entities:{backend}")
                if strict:
                    raise ValueError(f"invalid_entities:{backend}") from exc

    priors_by_backend: dict[str, CalibrationPriorDocument] = {}
    source_prior_documents: list[str] = []
    if priors_root is None or not priors_root.exists():
        warnings.append("priors_root_missing")
        if strict and priors_root is not None:
            raise ValueError("priors_root_missing")
    else:
        for path in sorted(p for p in priors_root.glob("*.json") if p.is_file()):
            backend = path.stem
            try:
                prior = _read_model(path, CalibrationPriorDocument)
                priors_by_backend[prior.backend] = prior
                source_prior_documents.append(str(path))
            except Exception as exc:
                warnings.append(f"invalid_prior:{backend}")
                if strict:
                    raise ValueError(f"invalid_prior:{backend}") from exc

    for manifest in consensus.backends:
        if entities_root is not None and entities_root.exists() and manifest.backend not in entities_by_backend:
            warnings.append(f"entities_missing:{manifest.backend}")
        if priors_root is not None and priors_root.exists() and manifest.backend not in priors_by_backend:
            warnings.append(f"prior_missing:{manifest.backend}")

    return LinkerLoadResult(consensus, consensus_report, entities_by_backend, priors_by_backend, source_entity_documents, source_prior_documents, warnings)


def write_linker_outputs(*, result: LinkerRunResult, out_dir: Path) -> None:
    """Write the linked structure JSON and linking report to ``out_dir``.

    Creates ``out_dir/linked_structure.json`` and
    ``out_dir/reports/linking_report.json``. Directories are created if they
    do not exist.

    Args:
        result: Linker run output to serialise.
        out_dir: Output root that will contain the linked structure file and
            a ``reports/`` subdirectory.
    """
    reports_dir = out_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "linked_structure.json").write_text(result.linked.model_dump_json(indent=2), encoding="utf-8")
    (reports_dir / "linking_report.json").write_text(json.dumps(result.report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
