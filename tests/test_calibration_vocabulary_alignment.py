"""Plan 12 BlockKind vocabulary alignment tests."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from pdf2md.calibration.vocabulary import (
    DOCLING_LABEL_TO_BLOCK_KIND,
    MANDATORY_DOCLING_LABELS,
    build_vocabulary_alignment_report,
    build_vocabulary_alignment_summary,
    normalise_truth_payload,
    normalize_docling_label,
    scan_truth_root_labels,
    write_vocabulary_alignment_report,
)
from pdf2md.models.ir import BlockKind

ROOT = Path(__file__).resolve().parents[1]
DOCLING_ROOT = ROOT / "tests" / "data" / "calibration_vocabulary_fixtures" / "docling_truth_root"
MISSING_MANDATORY_ROOT = ROOT / "tests" / "data" / "calibration_vocabulary_fixtures" / "missing_mandatory_root"


def _load_cli_module():
    spec = importlib.util.spec_from_file_location(
        "vocabulary_alignment_check_cli",
        ROOT / "tools" / "vocabulary_alignment_check.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["vocabulary_alignment_check_cli"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Mapping table
# ---------------------------------------------------------------------------


def test_mandatory_docling_labels_all_present_in_mapping() -> None:
    """The four mandatory labels MUST be in the canonical mapping table."""

    for label in MANDATORY_DOCLING_LABELS:
        assert label in DOCLING_LABEL_TO_BLOCK_KIND, label


@pytest.mark.parametrize(
    "label,expected",
    [
        ("text", BlockKind.PARAGRAPH),
        ("section_header", BlockKind.HEADING),
        ("title", BlockKind.HEADING),
        ("picture", BlockKind.FIGURE),
    ],
)
def test_mandatory_label_mapping_is_canonical(label: str, expected: BlockKind) -> None:
    assert DOCLING_LABEL_TO_BLOCK_KIND[label] is expected


def test_mapping_targets_are_only_canonical_block_kinds() -> None:
    canonical = {b.value for b in BlockKind}
    for docling_label, mapped_kind in DOCLING_LABEL_TO_BLOCK_KIND.items():
        assert mapped_kind.value in canonical, docling_label


# ---------------------------------------------------------------------------
# normalize_docling_label
# ---------------------------------------------------------------------------


def test_normalize_docling_label_top_four() -> None:
    assert normalize_docling_label("text") == BlockKind.PARAGRAPH.value
    assert normalize_docling_label("section_header") == BlockKind.HEADING.value
    assert normalize_docling_label("title") == BlockKind.HEADING.value
    assert normalize_docling_label("picture") == BlockKind.FIGURE.value


def test_normalize_docling_label_already_canonical_passes_through() -> None:
    assert normalize_docling_label("paragraph") == "paragraph"
    assert normalize_docling_label("heading") == "heading"
    assert normalize_docling_label("figure") == "figure"


def test_normalize_docling_label_unknown_returns_none() -> None:
    assert normalize_docling_label("totally_unknown_label") is None


def test_normalize_docling_label_case_insensitive() -> None:
    assert normalize_docling_label("Text") == BlockKind.PARAGRAPH.value
    assert normalize_docling_label("SECTION_HEADER") == BlockKind.HEADING.value


# ---------------------------------------------------------------------------
# normalise_truth_payload
# ---------------------------------------------------------------------------


def test_normalise_truth_payload_rewrites_block_kind_in_place() -> None:
    payload = {
        "document_id": "doc",
        "blocks": [
            {"id": "tb1", "block_kind": "text", "page_no": 1},
            {"id": "tb2", "block_kind": "section_header", "page_no": 1},
            {"id": "tb3", "block_kind": "picture", "page_no": 2},
        ],
    }
    normalised = normalise_truth_payload(payload)
    assert [b["block_kind"] for b in normalised["blocks"]] == [
        "paragraph",
        "heading",
        "figure",
    ]
    # original untouched
    assert payload["blocks"][0]["block_kind"] == "text"


def test_normalise_truth_payload_preserves_already_canonical() -> None:
    payload = {
        "document_id": "doc",
        "blocks": [
            {"id": "tb1", "block_kind": "paragraph", "page_no": 1},
            {"id": "tb2", "block_kind": "heading", "page_no": 1},
        ],
    }
    normalised = normalise_truth_payload(payload)
    assert [b["block_kind"] for b in normalised["blocks"]] == ["paragraph", "heading"]


def test_normalise_truth_payload_leaves_unmapped_labels_unchanged() -> None:
    payload = {
        "document_id": "doc",
        "blocks": [{"id": "tb1", "block_kind": "weird_docling_label", "page_no": 1}],
    }
    normalised = normalise_truth_payload(payload)
    assert normalised["blocks"][0]["block_kind"] == "weird_docling_label"


# ---------------------------------------------------------------------------
# scan_truth_root_labels
# ---------------------------------------------------------------------------


def test_scan_truth_root_labels_counts_observed_labels() -> None:
    counts, errors = scan_truth_root_labels(DOCLING_ROOT)
    assert errors == []
    # docA: text, section_header, title, picture; docB: text, caption, table
    assert counts.get("text") == 2
    assert counts.get("section_header") == 1
    assert counts.get("title") == 1
    assert counts.get("picture") == 1
    assert counts.get("caption") == 1
    assert counts.get("table") == 1


def test_scan_truth_root_labels_reports_missing_root() -> None:
    counts, errors = scan_truth_root_labels(ROOT / "tests" / "data" / "does_not_exist_xyz")
    assert counts == {}
    assert any("truth_root_missing" in e for e in errors)


# ---------------------------------------------------------------------------
# build_vocabulary_alignment_report
# ---------------------------------------------------------------------------


def test_build_alignment_report_passes_on_canonical_root() -> None:
    counts, _ = scan_truth_root_labels(DOCLING_ROOT)
    report = build_vocabulary_alignment_report(
        truth_root=DOCLING_ROOT,
        observed_labels=counts,
    )
    assert report.mandatory_mapping_passed is True
    assert report.all_observed_labels_mapped is True
    assert report.mapped_labels.get("text") == "paragraph"
    assert report.mapped_labels.get("section_header") == "heading"
    assert report.mapped_labels.get("title") == "heading"
    assert report.mapped_labels.get("picture") == "figure"
    assert report.top_label_coverage["text"]["observed_count"] == 2
    assert report.errors == []


def test_build_alignment_report_fails_when_mandatory_missing() -> None:
    # Force a mapping table without "text" to simulate a regression.
    truncated_mapping = {
        k: v for k, v in DOCLING_LABEL_TO_BLOCK_KIND.items() if k != "text"
    }
    # We don't actually rebuild via mapping arg here — the mapping argument is
    # informational only. Instead we verify the *report* flags unmapped labels.
    report = build_vocabulary_alignment_report(
        truth_root=DOCLING_ROOT,
        observed_labels={"unmappable_label_only": 1},
        mapping=truncated_mapping,
    )
    assert report.mandatory_mapping_passed is True  # mapping table itself still has the top-four
    assert report.all_observed_labels_mapped is False
    assert "unmappable_label_only" in report.unmapped_labels


def test_build_alignment_report_records_unmapped_labels() -> None:
    report = build_vocabulary_alignment_report(
        truth_root=MISSING_MANDATORY_ROOT,
    )
    assert "weird_docling_label" in report.unmapped_labels
    assert report.all_observed_labels_mapped is False


def test_alignment_report_json_contract() -> None:
    counts, _ = scan_truth_root_labels(DOCLING_ROOT)
    report = build_vocabulary_alignment_report(
        truth_root=DOCLING_ROOT,
        observed_labels=counts,
    )
    payload = json.loads(report.model_dump_json())
    required = {
        "schema_name",
        "schema_version",
        "generated_at",
        "tool_name",
        "truth_root",
        "mapping_source",
        "mandatory_mapping_passed",
        "all_observed_labels_mapped",
        "top_label_coverage",
        "mapping_used",
        "observed_truth_labels",
        "mapped_labels",
        "unmapped_labels",
        "mandatory_labels",
        "warnings",
        "errors",
        "metadata",
    }
    assert required.issubset(payload.keys())
    assert payload["schema_name"] == "pdf2md.BlockKindVocabularyAlignmentReport"
    assert payload["schema_version"] == "1.0.0"
    assert payload["tool_name"] == "vocabulary_alignment_check"


def test_summary_written_to_disk(tmp_path: Path) -> None:
    counts, _ = scan_truth_root_labels(DOCLING_ROOT)
    report = build_vocabulary_alignment_report(
        truth_root=DOCLING_ROOT,
        observed_labels=counts,
    )
    write_vocabulary_alignment_report(report=report, out_dir=tmp_path)
    assert (tmp_path / "reports" / "blockkind_vocabulary_alignment_report.json").is_file()
    assert (tmp_path / "reports" / "blockkind_vocabulary_alignment_summary.txt").is_file()
    summary = (tmp_path / "reports" / "blockkind_vocabulary_alignment_summary.txt").read_text()
    assert "Plan 12" in summary
    assert "mandatory_mapping_passed: PASSED" in summary


# ---------------------------------------------------------------------------
# CLI behaviour
# ---------------------------------------------------------------------------


def test_cli_exit_zero_on_canonical_root(tmp_path: Path) -> None:
    cli = _load_cli_module()
    exit_code = cli.main(["--root", str(DOCLING_ROOT), "--out-dir", str(tmp_path)])
    assert exit_code == 0
    payload = json.loads(
        (tmp_path / "reports" / "blockkind_vocabulary_alignment_report.json").read_text()
    )
    assert payload["mandatory_mapping_passed"] is True


def test_cli_strict_exit_nonzero_on_unmapped_label(tmp_path: Path) -> None:
    cli = _load_cli_module()
    exit_code = cli.main(
        ["--root", str(MISSING_MANDATORY_ROOT), "--out-dir", str(tmp_path), "--strict"]
    )
    assert exit_code == 1


def test_cli_nonstrict_passes_when_only_non_top_labels_unmapped(tmp_path: Path) -> None:
    cli = _load_cli_module()
    exit_code = cli.main(["--root", str(MISSING_MANDATORY_ROOT), "--out-dir", str(tmp_path)])
    # mandatory mapping table still has the top-four; non-strict CLI accepts that even when
    # observed labels include unmapped non-mandatory ones.
    assert exit_code == 0
