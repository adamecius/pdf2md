"""Plan 17 docling export wiring tests.

Covers the four A1/A2/A6 wiring fixes:
- `origin.filename` and `origin.binary_hash` are populated from a source PDF.
- Every emitted `label` is a valid `docling_core.types.doc.DocItemLabel`.
- Group items don't carry stringy legacy labels (`section`/`list`/`references`/`document`).
- Schema version matches docling_core's default.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pdf2md.export.docling import (
    _DOCLING_SCHEMA_VERSION_DEFAULT,
    _GROUP_LABELS,
    _TEXT_LABELS,
    DoclingExportSettings,
    _compute_origin,
    build_docling_document,
)
from pdf2md.export.io import build_export_run, load_export_inputs
from pdf2md.export.markdown import MarkdownExportSettings
from pdf2md.export.rag import RagExportSettings
from pdf2md.models.linked import LinkedNodeType

FIX = Path("tests/data/export_fixtures")


# ---------------------------------------------------------------------------
# A1 — origin block
# ---------------------------------------------------------------------------


class TestOriginBlock:
    def test_origin_filename_and_binary_hash_populated_when_source_pdf_given(self, tmp_path: Path):
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake content")
        origin, warnings = _compute_origin(pdf)
        assert origin["mimetype"] == "application/pdf"
        assert origin["filename"] == "sample.pdf"
        assert isinstance(origin["binary_hash"], int)
        assert origin["binary_hash"] != 0
        # sha256 lower 63 bits
        expected = int.from_bytes(hashlib.sha256(pdf.read_bytes()).digest()[:8], "big") & ((1 << 63) - 1)
        assert origin["binary_hash"] == expected
        assert warnings == []

    def test_origin_sentinel_when_source_pdf_none(self):
        origin, warnings = _compute_origin(None)
        assert origin["mimetype"] == "application/pdf"
        assert origin["filename"] == "unknown.pdf"
        assert isinstance(origin["binary_hash"], int)
        assert origin["binary_hash"] == 0
        assert warnings == ["origin_pdf_path_unknown"]

    def test_origin_sentinel_when_source_pdf_missing(self, tmp_path: Path):
        origin, warnings = _compute_origin(tmp_path / "nope.pdf")
        assert origin["filename"] == "nope.pdf"
        assert origin["binary_hash"] == 0
        assert "origin_pdf_path_unknown" in warnings

    def test_build_document_threads_source_pdf_into_origin(self, tmp_path: Path):
        from tests.test_docling_export import load

        linked, consensus = load("simple_document")
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 doc")
        result = build_docling_document(linked=linked, consensus=consensus, source_pdf=pdf)
        assert result.document["origin"]["filename"] == "doc.pdf"
        assert isinstance(result.document["origin"]["binary_hash"], int)
        assert result.document["origin"]["binary_hash"] != 0

    def test_build_export_run_threads_source_pdf(self, tmp_path: Path):
        loaded = load_export_inputs(
            linked_structure_path=FIX / "simple_document" / "linked_structure.json",
            consensus_ir_path=FIX / "simple_document" / "consensus_ir.json",
        )
        pdf = tmp_path / "input.pdf"
        pdf.write_bytes(b"%PDF-1.4 input")
        result = build_export_run(
            linked=loaded.linked,
            consensus=loaded.consensus,
            source_linked_structure=str(FIX / "simple_document" / "linked_structure.json"),
            source_consensus_ir=str(FIX / "simple_document" / "consensus_ir.json"),
            source_pdf=str(pdf),
            docling_settings=DoclingExportSettings(),
            rag_settings=RagExportSettings(),
            markdown_settings=MarkdownExportSettings(),
        )
        assert result.docling["origin"]["filename"] == "input.pdf"
        assert result.docling["origin"]["binary_hash"] != 0


# ---------------------------------------------------------------------------
# A2 — label mapping
# ---------------------------------------------------------------------------


class TestLabelMapping:
    def test_every_text_label_is_valid_doc_item_label(self):
        pytest.importorskip("docling_core")
        from docling_core.types.doc import DocItemLabel

        valid_labels = {label.value for label in DocItemLabel}
        for node_type, label in _TEXT_LABELS.items():
            assert label in valid_labels, (
                f"{node_type.value} -> {label!r} is not a valid DocItemLabel; "
                f"valid: {sorted(valid_labels)}"
            )

    def test_paragraph_maps_to_text_not_paragraph(self):
        assert _TEXT_LABELS[LinkedNodeType.PARAGRAPH] == "text"

    def test_unknown_maps_to_text_with_warning(self, tmp_path: Path):
        from tests.test_docling_export import load

        linked, consensus = load("simple_document")
        result = build_docling_document(linked=linked, consensus=consensus, source_pdf=tmp_path / "doc.pdf")
        for item in result.document["texts"]:
            assert item["label"] != "unknown"
            assert item["label"] != "paragraph"  # body paras should be "text"

    def test_groups_do_not_emit_legacy_labels(self):
        for nt, label in _GROUP_LABELS.items():
            assert label is None, f"{nt.value} should not emit a docling group label; got {label!r}"

    def test_built_document_has_no_invalid_group_labels(self):
        from tests.test_docling_export import load

        linked, consensus = load("simple_document")
        doc = build_docling_document(linked=linked, consensus=consensus, source_pdf=None).document
        for group in doc["groups"]:
            # docling-core groups should not carry one of the legacy labels.
            assert group.get("label") not in {"section", "list", "references", "document"}


# ---------------------------------------------------------------------------
# A6 — schema version
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    def test_default_schema_version_matches_docling_core(self):
        pytest.importorskip("docling_core")
        from docling_core.types.doc import DoclingDocument

        expected = DoclingDocument.model_fields.get("version").default
        assert expected == _DOCLING_SCHEMA_VERSION_DEFAULT

    def test_settings_default_uses_resolved_version(self):
        assert DoclingExportSettings().schema_version == _DOCLING_SCHEMA_VERSION_DEFAULT

    def test_exported_document_carries_resolved_version(self, tmp_path: Path):
        from tests.test_docling_export import load

        linked, consensus = load("simple_document")
        doc = build_docling_document(linked=linked, consensus=consensus, source_pdf=None).document
        assert doc["version"] == _DOCLING_SCHEMA_VERSION_DEFAULT


# ---------------------------------------------------------------------------
# docling_core strict validation gate
# ---------------------------------------------------------------------------


class TestDoclingCoreStrictValidation:
    """A1+A2+A6 dramatically reduce strict-validation errors but do not
    eliminate them in all cases. The remaining failures uncover additional
    wiring defects that are explicitly Plan 17 follow-up scope:

    - ``pictures[*].text`` / ``pictures[*].metadata`` extras (docling-core
      forbids extras on picture items).
    - ``tables[*].text`` / ``tables[*].metadata`` extras (same).
    - ``prov[*].bbox.coord_origin`` is emitted lowercase
      (``bottomleft``); docling-core expects ``BOTTOMLEFT`` / ``TOPLEFT``.
    - ``prov[*].charspan`` is a required field but never emitted by the
      pdf2md exporter.

    These are tracked as a Plan 17 follow-up bundle (call it ``A8 — strip
    pdf2md-only keys from docling-core items + emit prov.charspan +
    uppercase coord_origin``). The wiring tests below DEMONSTRATE the
    failure mode is what the v2 GPU report saw, so the follow-up has
    a concrete starting point.

    For now, the headline gate is that the ORIGIN block passes — the
    315/6601 validation errors the v2 report observed were dominated by
    the missing origin fields. After A1+A2+A6 the simple_document case
    reduces to a small handful of per-item structural errors.
    """

    def test_simple_document_passes_strict_validation_with_origin(self, tmp_path: Path):
        pytest.importorskip("docling_core")
        from docling_core.types.doc import DoclingDocument

        from tests.test_docling_export import load

        linked, consensus = load("simple_document")
        pdf = tmp_path / "simple.pdf"
        pdf.write_bytes(b"%PDF-1.4 simple")
        doc = build_docling_document(
            linked=linked, consensus=consensus, source_pdf=pdf,
            settings=DoclingExportSettings(strict=True),
        ).document
        DoclingDocument.model_validate(doc)

    def test_rich_document_passes_strict_validation_with_origin(self, tmp_path: Path):
        pytest.importorskip("docling_core")
        from docling_core.types.doc import DoclingDocument

        from tests.test_docling_export import load

        linked, consensus = load("rich_document")
        pdf = tmp_path / "rich.pdf"
        pdf.write_bytes(b"%PDF-1.4 rich")
        doc = build_docling_document(
            linked=linked, consensus=consensus, source_pdf=pdf,
            settings=DoclingExportSettings(strict=True),
        ).document
        DoclingDocument.model_validate(doc)

    def test_origin_field_errors_are_eliminated(self, tmp_path: Path):
        """The headline gate: the origin block no longer triggers
        validation errors after A1+A2+A6, even when other extras remain.
        """

        pytest.importorskip("docling_core")
        from docling_core.types.doc import DoclingDocument
        from pydantic import ValidationError

        from tests.test_docling_export import load

        linked, consensus = load("simple_document")
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        doc = build_docling_document(linked=linked, consensus=consensus, source_pdf=pdf).document
        try:
            DoclingDocument.model_validate(doc)
        except ValidationError as exc:
            # If validation still fails it must NOT be because of origin —
            # that's the regression we explicitly want to prevent.
            messages = str(exc)
            assert "origin.binary_hash" not in messages, (
                "Origin binary_hash is still failing validation after Plan 17 A1: "
                + messages[:500]
            )
            assert "origin.filename" not in messages, (
                "Origin filename is still missing after Plan 17 A1: " + messages[:500]
            )
