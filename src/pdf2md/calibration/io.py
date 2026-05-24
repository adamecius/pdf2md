"""Filesystem I/O for calibration inputs and outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2md.calibration.vocabulary import normalise_truth_payload
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import PageExtractionIR
from pdf2md.models.priors import CalibrationPriorDocument, CalibrationTruthDocument


@dataclass(frozen=True)
class CalibrationDocumentInput:
    """Filesystem locations of a single calibration document's truth and predictions.

    Attributes:
        document_id: Stable identifier for the document (typically the
            directory name).
        truth_path: Path to the ``truth.json`` file with ground-truth blocks,
            entities, and relations.
        prediction_roots: Mapping from backend name to the prediction directory
            that contains ``entities.json`` and a ``pages/`` subdirectory.
    """

    document_id: str
    truth_path: Path
    prediction_roots: dict[str, Path]


@dataclass(frozen=True)
class CalibrationLoadResult:
    """Loaded truth and per-backend predictions for one calibration document.

    Attributes:
        truth: Parsed truth document, or None if it was missing or invalid in
            non-strict mode.
        pages_by_backend: Per-backend list of page-level extraction IRs.
        entities_by_backend: Per-backend entity proposal documents.
        warnings: Non-fatal load problems (missing files, invalid JSON,
            validation failures) reported with stable string codes.
    """

    truth: CalibrationTruthDocument | None
    pages_by_backend: dict[str, list[PageExtractionIR]]
    entities_by_backend: dict[str, EntityProposalDocument]
    warnings: list[str]


def _candidate_backend_dirs(root: Path) -> dict[str, Path]:
    if (root / "backend_ir").is_dir():
        return {p.name: p for p in (root / "backend_ir").iterdir() if p.is_dir()}
    return {p.name: p for p in root.iterdir() if p.is_dir() and (p / "entities.json").exists()}


def discover_calibration_inputs(*, root: Path, backends: list[str] | None = None) -> list[CalibrationDocumentInput]:
    """Discover calibration documents under a root directory.

    Supports three layouts:

    - ``root`` directly contains ``truth.json`` (single-document layout).
    - ``root`` is a ``*_predictions`` directory paired with a sibling
      ``*_truth`` directory.
    - ``root`` contains one subdirectory per document, each with a
      ``truth.json``.

    Args:
        root: Directory to scan for calibration documents.
        backends: Optional whitelist of backend names; when set, prediction
            directories whose names are not listed are filtered out.

    Returns:
        One ``CalibrationDocumentInput`` per discovered document. The list is
        empty if no truth files are found.
    """
    root = Path(root)
    allowed = set(backends or [])
    if (root / "truth.json").exists():
        dirs = _candidate_backend_dirs(root)
        if allowed:
            dirs = {name: path for name, path in dirs.items() if name in allowed}
        return [CalibrationDocumentInput(document_id=root.name, truth_path=root / "truth.json", prediction_roots=dirs)]
    if root.name.endswith("_predictions"):
        truth_root = root.with_name(root.name.removesuffix("_predictions") + "_truth")
        truth_path = truth_root / "truth.json"
        if truth_path.exists():
            dirs = _candidate_backend_dirs(root)
            if allowed:
                dirs = {name: path for name, path in dirs.items() if name in allowed}
            return [CalibrationDocumentInput(document_id=root.name.removesuffix("_predictions"), truth_path=truth_path, prediction_roots=dirs)]
    items: list[CalibrationDocumentInput] = []
    for child in sorted(root.iterdir() if root.exists() else [], key=lambda p: p.name):
        if not child.is_dir():
            continue
        truth_path = child / "truth.json"
        if not truth_path.exists():
            continue
        dirs = _candidate_backend_dirs(child)
        if allowed:
            dirs = {name: path for name, path in dirs.items() if name in allowed}
        items.append(CalibrationDocumentInput(document_id=child.name, truth_path=truth_path, prediction_roots=dirs))
    return items


def _load_model(path: Path, model: type[Any], warning: str, warnings: list[str], strict: bool) -> Any | None:
    try:
        return model.model_validate_json(path.read_text())
    except Exception as exc:
        if strict:
            raise
        warnings.append(warning)
        warnings.append(f"{warning}_detail:{exc.__class__.__name__}")
        return None


def load_calibration_truth_document(
    path: Path,
    *,
    strict: bool = False,
    warnings: list[str] | None = None,
) -> CalibrationTruthDocument | None:
    """Load a ``truth.json`` file with the Docling-to-BlockKind mapping applied.

    The mandatory top-four Docling labels (``text``, ``section_header``,
    ``title``, ``picture``) and the rest of the canonical mapping declared in
    ``pdf2md.calibration.vocabulary.DOCLING_LABEL_TO_BLOCK_KIND`` are rewritten
    before Pydantic validation, so ``CalibrationTruthDocument.blocks[].block_kind``
    always receives canonical ``BlockKind`` values. Already-canonical truth
    files pass through unchanged.
    """

    warnings = warnings if warnings is not None else []
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        if strict:
            raise
        warnings.append(f"truth_missing:{path}")
        return None
    except json.JSONDecodeError as exc:
        if strict:
            raise
        warnings.append(f"invalid_truth:{path}")
        warnings.append(f"invalid_truth:{path}_detail:JSONDecodeError:{exc.msg}")
        return None

    payload = normalise_truth_payload(raw)
    try:
        return CalibrationTruthDocument.model_validate(payload)
    except Exception as exc:
        if strict:
            raise
        warnings.append(f"invalid_truth:{path}")
        warnings.append(f"invalid_truth:{path}_detail:{exc.__class__.__name__}")
        return None


def load_calibration_document(*, item: CalibrationDocumentInput, strict: bool = False) -> CalibrationLoadResult:
    """Load the truth and all per-backend predictions for one calibration document.

    Reads the truth JSON (with vocabulary normalisation) and, for each backend
    listed in ``item.prediction_roots``, the entity proposal document and every
    ``pages/*.json`` extraction IR.

    Args:
        item: The discovered document input describing where to read from.
        strict: If True, propagate the first I/O or validation error. If
            False, record stable warning codes and continue loading the rest.

    Returns:
        A ``CalibrationLoadResult`` with the truth, per-backend pages and
        entities, and a list of non-fatal warnings.

    Raises:
        FileNotFoundError: In strict mode, if the truth file or any expected
            prediction file/directory is missing.
    """
    warnings: list[str] = []
    truth: CalibrationTruthDocument | None = None
    if not item.truth_path.exists():
        warnings.append("truth_missing")
        if strict:
            raise FileNotFoundError(item.truth_path)
    else:
        truth = load_calibration_truth_document(item.truth_path, strict=strict, warnings=warnings)
    pages_by_backend: dict[str, list[PageExtractionIR]] = {}
    entities_by_backend: dict[str, EntityProposalDocument] = {}
    for backend, root in sorted(item.prediction_roots.items()):
        if not root.exists():
            warnings.append(f"prediction_missing:{backend}")
            if strict:
                raise FileNotFoundError(root)
            continue
        entities_path = root / "entities.json"
        if not entities_path.exists():
            warnings.append(f"entities_missing:{backend}")
            if strict:
                raise FileNotFoundError(entities_path)
        else:
            entities = _load_model(entities_path, EntityProposalDocument, f"invalid_entities:{backend}", warnings, strict)
            if entities is not None:
                entities_by_backend[backend] = entities
        pages_dir = root / "pages"
        if not pages_dir.exists():
            warnings.append(f"pages_missing:{backend}")
            if strict:
                raise FileNotFoundError(pages_dir)
            continue
        pages: list[PageExtractionIR] = []
        for page_path in sorted(pages_dir.glob("*.json")):
            page = _load_model(page_path, PageExtractionIR, f"invalid_page:{backend}:{page_path.name}", warnings, strict)
            if page is not None:
                pages.append(page)
        if not pages:
            warnings.append(f"pages_missing:{backend}")
        pages_by_backend[backend] = pages
    return CalibrationLoadResult(truth=truth, pages_by_backend=pages_by_backend, entities_by_backend=entities_by_backend, warnings=warnings)


def read_backend_version(prediction_root: Path) -> str | None:
    """Return the backend version recorded in a prediction root's manifest.

    Reads ``manifest.json`` and returns the ``backend_version`` field, falling
    back to ``version``.

    Args:
        prediction_root: Directory expected to contain ``manifest.json``.

    Returns:
        The version string, or None if the manifest is missing, unparsable, or
        does not carry a version field.
    """
    manifest_path = prediction_root / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return None
    value = payload.get("backend_version") or payload.get("version")
    return None if value is None else str(value)


def write_prior_outputs(*, priors: list[CalibrationPriorDocument], report: dict[str, Any], out_dir: Path) -> None:
    """Write calibration prior documents and the aggregate report to disk.

    Creates ``priors/<backend>.json`` for each prior and
    ``reports/calibration_report.json`` for the aggregate report. Directories
    are created if they do not exist.

    Args:
        priors: One calibration prior document per backend.
        report: Aggregate calibration report payload to serialise as JSON.
        out_dir: Output root that will contain ``priors/`` and ``reports/``
            subdirectories.
    """
    priors_dir = Path(out_dir) / "priors"
    reports_dir = Path(out_dir) / "reports"
    priors_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    for prior in priors:
        (priors_dir / f"{prior.backend}.json").write_text(prior.model_dump_json(indent=2) + "\n")
    (reports_dir / "calibration_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
