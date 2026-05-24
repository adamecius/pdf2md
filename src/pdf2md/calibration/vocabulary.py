"""Docling-label to canonical BlockKind vocabulary alignment (Plan 12).

The repository calibration matcher (``pdf2md.calibration.matching.match_blocks``)
expects ``CalibrationTruthDocument.blocks[].block_kind`` to be a canonical
``BlockKind`` value. Real ground-truth corpora produced by Docling often use
raw Docling labels such as ``text``, ``section_header``, ``title`` and
``picture``. This module owns the canonical mapping and provides the
vocabulary-alignment gate that calibration must pass before priors can be
trusted.

The mandatory top-four labels are a hard gate. Without them, the matcher
inflates false positives/negatives on the most common corpus categories.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pdf2md.models.ir import BlockKind

VOCABULARY_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
TOOL_NAME: Literal["vocabulary_alignment_check"] = "vocabulary_alignment_check"

# Canonical Docling label -> BlockKind mapping. Lookup is case-insensitive on
# the docling label key. Add only labels that the repository BlockKind enum
# already supports; do not invent BlockKind values.
DOCLING_LABEL_TO_BLOCK_KIND: dict[str, BlockKind] = {
    # Mandatory top-four (Plan 12 hard gate)
    "text": BlockKind.PARAGRAPH,
    "section_header": BlockKind.HEADING,
    "title": BlockKind.HEADING,
    "picture": BlockKind.FIGURE,
    # Extras observed in Docling outputs and supported by the schema
    "paragraph": BlockKind.PARAGRAPH,
    "heading": BlockKind.HEADING,
    "caption": BlockKind.CAPTION,
    "table": BlockKind.TABLE,
    "formula": BlockKind.FORMULA,
    "equation": BlockKind.FORMULA,
    "footnote": BlockKind.FOOTNOTE,
    "list": BlockKind.LIST,
    "list_item": BlockKind.LIST_ITEM,
    "page_number": BlockKind.PAGE_NUMBER,
    "page-header": BlockKind.HEADER,
    "page-footer": BlockKind.FOOTER,
    "page_header": BlockKind.HEADER,
    "page_footer": BlockKind.FOOTER,
    "reference": BlockKind.REFERENCE,
    "bibitem": BlockKind.BIBITEM,
    "code": BlockKind.CODE,
    "figure": BlockKind.FIGURE,
    "unknown": BlockKind.UNKNOWN,
}

MANDATORY_DOCLING_LABELS: tuple[str, ...] = ("text", "section_header", "title", "picture")

# Set of all canonical BlockKind string values for fast membership checks.
CANONICAL_BLOCK_KIND_VALUES: frozenset[str] = frozenset(b.value for b in BlockKind)


class _VocabBaseModel(BaseModel):
    """Private base for vocabulary-alignment Pydantic models (extra=forbid)."""

    model_config = ConfigDict(extra="forbid")


class BlockKindVocabularyAlignmentReport(_VocabBaseModel):
    """Plan 12 vocabulary alignment report."""

    schema_name: Literal["pdf2md.BlockKindVocabularyAlignmentReport"] = (
        "pdf2md.BlockKindVocabularyAlignmentReport"
    )
    schema_version: Literal["1.0.0"] = VOCABULARY_SCHEMA_VERSION
    generated_at: str
    tool_name: Literal["vocabulary_alignment_check"] = TOOL_NAME
    truth_root: str
    mapping_source: str = "pdf2md.calibration.vocabulary.DOCLING_LABEL_TO_BLOCK_KIND"
    mandatory_mapping_passed: bool = False
    all_observed_labels_mapped: bool = False
    top_label_coverage: dict[str, dict[str, Any]] = Field(default_factory=dict)
    mapping_used: dict[str, str] = Field(default_factory=dict)
    observed_truth_labels: dict[str, int] = Field(default_factory=dict)
    mapped_labels: dict[str, str] = Field(default_factory=dict)
    unmapped_labels: list[str] = Field(default_factory=list)
    mandatory_labels: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_docling_label(label: str | None) -> str | None:
    """Return a canonical BlockKind value for a Docling label, or None if unknown.

    Already-canonical BlockKind values pass through unchanged. Lookup is
    case-insensitive on the docling label key.
    """

    if label is None:
        return None
    key = str(label).strip()
    if not key:
        return None
    if key in CANONICAL_BLOCK_KIND_VALUES:
        return key
    lower = key.lower()
    if lower in CANONICAL_BLOCK_KIND_VALUES:
        return lower
    mapped = DOCLING_LABEL_TO_BLOCK_KIND.get(lower)
    if mapped is None:
        return None
    return mapped.value


def normalise_truth_payload(payload: Any) -> Any:
    """Walk a parsed ``truth.json`` payload and rewrite raw Docling block_kind labels.

    Returns a deep copy with ``blocks[i].block_kind`` mapped through
    ``normalize_docling_label``. Labels that have no canonical mapping are
    preserved verbatim; downstream Pydantic validation will fail on them, which
    is the desired behaviour (vocabulary gate enforces the fix).
    """

    if not isinstance(payload, dict):
        return payload
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        return payload
    new_blocks: list[Any] = []
    for block in blocks:
        if not isinstance(block, dict):
            new_blocks.append(block)
            continue
        kind = block.get("block_kind")
        mapped = normalize_docling_label(kind) if isinstance(kind, str) else None
        if mapped is not None and mapped != kind:
            block = dict(block)
            block["block_kind"] = mapped
        new_blocks.append(block)
    out = dict(payload)
    out["blocks"] = new_blocks
    return out


def scan_truth_root_labels(truth_root: Path) -> tuple[dict[str, int], list[str]]:
    """Collect raw ``block_kind`` label counts and per-file errors from a truth root."""

    truth_root = Path(truth_root)
    counts: dict[str, int] = {}
    errors: list[str] = []
    if not truth_root.exists():
        errors.append(f"truth_root_missing:{truth_root}")
        return counts, errors

    candidate_paths: list[Path] = []
    if truth_root.is_file():
        candidate_paths = [truth_root]
    else:
        if (truth_root / "truth.json").is_file():
            candidate_paths.append(truth_root / "truth.json")
        for child in sorted(truth_root.iterdir()):
            if child.is_dir() and (child / "truth.json").is_file():
                candidate_paths.append(child / "truth.json")

    if not candidate_paths:
        errors.append(f"no_truth_json_under:{truth_root}")
        return counts, errors

    for path in candidate_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"unreadable_truth_json:{path}:{exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"truth_not_object:{path}")
            continue
        blocks = data.get("blocks")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            kind = block.get("block_kind")
            if not isinstance(kind, str) or not kind:
                continue
            counts[kind] = counts.get(kind, 0) + 1
    return counts, errors


def build_vocabulary_alignment_report(
    *,
    truth_root: Path,
    observed_labels: Mapping[str, int] | None = None,
    mapping: Mapping[str, BlockKind] | None = None,
    generated_at: str | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> BlockKindVocabularyAlignmentReport:
    """Compose the vocabulary alignment report for a truth root."""

    truth_root = Path(truth_root)
    errors: list[str] = []
    if observed_labels is None:
        observed_labels, scan_errors = scan_truth_root_labels(truth_root)
        errors.extend(scan_errors)
    mapping = dict(mapping if mapping is not None else DOCLING_LABEL_TO_BLOCK_KIND)
    mapping_used = {label: kind.value for label, kind in mapping.items()}

    mapped_labels: dict[str, str] = {}
    unmapped_labels: list[str] = []
    for label, _count in sorted(observed_labels.items()):
        canonical = normalize_docling_label(label)
        if canonical is None:
            unmapped_labels.append(label)
        else:
            mapped_labels[label] = canonical

    top_coverage: dict[str, dict[str, Any]] = {}
    for label in MANDATORY_DOCLING_LABELS:
        canonical = normalize_docling_label(label)
        top_coverage[label] = {
            "canonical": canonical,
            "observed_count": int(observed_labels.get(label, 0)),
            "mapped": canonical is not None,
        }

    mandatory_mapping_passed = all(entry["mapped"] for entry in top_coverage.values())
    all_observed_labels_mapped = len(unmapped_labels) == 0

    warnings: list[str] = []
    if unmapped_labels:
        warnings.append(
            "unmapped_truth_labels_present: "
            + ", ".join(unmapped_labels[:10])
            + (f" (+{len(unmapped_labels) - 10} more)" if len(unmapped_labels) > 10 else "")
        )
    if not mandatory_mapping_passed:
        missing = [
            label for label, entry in top_coverage.items() if not entry["mapped"]
        ]
        errors.append("mandatory_mapping_missing: " + ", ".join(missing))

    metadata: dict[str, Any] = {
        "label_count_total": sum(observed_labels.values()),
        "distinct_label_count": len(observed_labels),
        "mandatory_label_count": len(MANDATORY_DOCLING_LABELS),
    }
    if extra_metadata:
        metadata.update(dict(extra_metadata))

    return BlockKindVocabularyAlignmentReport(
        generated_at=generated_at or _utc_now(),
        truth_root=str(truth_root),
        mandatory_mapping_passed=mandatory_mapping_passed,
        all_observed_labels_mapped=all_observed_labels_mapped,
        top_label_coverage=top_coverage,
        mapping_used=mapping_used,
        observed_truth_labels=dict(observed_labels),
        mapped_labels=mapped_labels,
        unmapped_labels=unmapped_labels,
        mandatory_labels=list(MANDATORY_DOCLING_LABELS),
        warnings=warnings,
        errors=errors,
        metadata=metadata,
    )


def build_vocabulary_alignment_summary(report: BlockKindVocabularyAlignmentReport) -> str:
    """Render the human-readable summary for the alignment report."""

    gate = "PASSED" if report.mandatory_mapping_passed else "FAILED"
    all_ok = "yes" if report.all_observed_labels_mapped else "no"
    lines = [
        "pdf2md BlockKind vocabulary alignment (Plan 12)",
        f"schema: {report.schema_name} {report.schema_version}",
        f"tool: {report.tool_name}",
        f"generated_at: {report.generated_at}",
        f"truth_root: {report.truth_root}",
        f"mandatory_mapping_passed: {gate}",
        f"all_observed_labels_mapped: {all_ok}",
        "",
        "mandatory label coverage:",
    ]
    for label, entry in report.top_label_coverage.items():
        canon = entry.get("canonical")
        obs = entry.get("observed_count")
        lines.append(
            f"- {label} -> {canon if canon else '(unmapped)'} (observed_count={obs})"
        )

    lines.extend(["", "observed truth labels:"])
    if not report.observed_truth_labels:
        lines.append("- (none)")
    for label, count in sorted(report.observed_truth_labels.items()):
        canon = report.mapped_labels.get(label, "(unmapped)")
        lines.append(f"- {label} (n={count}) -> {canon}")

    if report.unmapped_labels:
        lines.extend(["", "unmapped labels:"])
        lines.extend(f"- {label}" for label in report.unmapped_labels)

    if report.warnings:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {w}" for w in report.warnings)
    if report.errors:
        lines.extend(["", "errors:"])
        lines.extend(f"- {e}" for e in report.errors)
    return "\n".join(lines) + "\n"


def write_vocabulary_alignment_report(
    *,
    report: BlockKindVocabularyAlignmentReport,
    out_dir: Path,
) -> Path:
    """Write JSON + summary files for the vocabulary alignment report."""

    out_dir = Path(out_dir)
    reports_dir = out_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "blockkind_vocabulary_alignment_report.json"
    summary_path = reports_dir / "blockkind_vocabulary_alignment_summary.txt"
    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(build_vocabulary_alignment_summary(report), encoding="utf-8")
    return report_path


__all__ = [
    "CANONICAL_BLOCK_KIND_VALUES",
    "DOCLING_LABEL_TO_BLOCK_KIND",
    "MANDATORY_DOCLING_LABELS",
    "TOOL_NAME",
    "VOCABULARY_SCHEMA_VERSION",
    "BlockKindVocabularyAlignmentReport",
    "build_vocabulary_alignment_report",
    "build_vocabulary_alignment_summary",
    "normalise_truth_payload",
    "normalize_docling_label",
    "scan_truth_root_labels",
    "write_vocabulary_alignment_report",
]
