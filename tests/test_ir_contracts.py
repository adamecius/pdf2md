"""Contract tests for PageExtractionIR and ConsensusIR models."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import pdf2md.models.ir as ir

FIXTURE_DIR = Path(__file__).parent / "data" / "ir_fixtures"


def fixture(name: str) -> Path:
    return FIXTURE_DIR / name


def round_trip(model_type, fixture_name: str):
    model = model_type.model_validate_json(fixture(fixture_name).read_text())
    payload = model.model_dump(mode="json")
    validated = model_type.model_validate(payload)
    assert validated.model_dump(mode="json") == payload
    return model


def page_size() -> ir.PageSize:
    return ir.PageSize(width=612.0, height=792.0)


def candidate_id(index: int = 0) -> str:
    return ir.extraction_id("mineru", "doc-1", 1, index)


def consensus_block(**overrides):
    payload = {
        "id": ir.consensus_id("doc-1", 1, 0),
        "kind": ir.BlockKind.PARAGRAPH,
        "bbox": None,
        "order": 0,
        "text": "Hello",
        "selection_mode": ir.SelectionMode.SINGLE_SOURCE,
        "selected_source": "mineru",
        "agreement_score": 1.0,
        "candidate_ids": [candidate_id()],
        "conflict_ids": [],
        "metadata": {},
    }
    payload.update(overrides)
    return ir.ConsensusBlock(**payload)


class TestEnums:
    def test_block_kind_values_match_specification(self):
        """BlockKind exposes exactly the plan-specified string values."""
        assert [kind.value for kind in ir.BlockKind] == [
            "paragraph", "heading", "formula", "figure", "table", "caption", "list",
            "list_item", "footnote", "page_number", "header", "footer", "reference",
            "bibitem", "code", "unknown",
        ]

    def test_selection_mode_values_match_specification(self):
        """SelectionMode exposes exactly the plan-specified string values."""
        assert [mode.value for mode in ir.SelectionMode] == ["agreed", "single_source", "fallback", "unresolved"]

    def test_conflict_kind_values_match_specification(self):
        """ConflictKind exposes exactly the plan-specified string values."""
        assert [kind.value for kind in ir.ConflictKind] == [
            "text_conflict", "kind_conflict", "bbox_conflict", "presence_conflict", "order_conflict"
        ]

    def test_coord_origin_values_match_specification(self):
        """CoordOrigin exposes exactly the plan-specified string values."""
        assert [origin.value for origin in ir.CoordOrigin] == ["bottomleft", "topleft"]


class TestBBox:
    def test_valid_bbox_bottomleft_constructs(self):
        """Bottom-left coordinates accept t greater than b."""
        assert ir.BBox(l=0, t=10, r=10, b=0, coord_origin="bottomleft").coord_origin == "bottomleft"

    def test_valid_bbox_topleft_constructs(self):
        """Top-left coordinates accept b greater than t."""
        assert ir.BBox(l=0, t=0, r=10, b=10, coord_origin="topleft").coord_origin == "topleft"

    def test_bbox_rejects_l_ge_r(self):
        """Bounding boxes reject non-positive horizontal extent."""
        with pytest.raises(ValidationError):
            ir.BBox(l=10, t=10, r=10, b=0, coord_origin="bottomleft")

    def test_bbox_rejects_inverted_t_b_for_bottomleft(self):
        """Bottom-left boxes reject t less than or equal to b."""
        with pytest.raises(ValidationError):
            ir.BBox(l=0, t=0, r=10, b=10, coord_origin="bottomleft")

    def test_bbox_rejects_inverted_b_t_for_topleft(self):
        """Top-left boxes reject b less than or equal to t."""
        with pytest.raises(ValidationError):
            ir.BBox(l=0, t=10, r=10, b=0, coord_origin="topleft")

    def test_bbox_extra_field_forbidden(self):
        """Bounding boxes forbid fields outside the contract."""
        with pytest.raises(ValidationError):
            ir.BBox(l=0, t=10, r=10, b=0, coord_origin="bottomleft", unit="pt")


class TestPageSize:
    def test_valid_page_size(self):
        """PageSize accepts positive width and height."""
        assert page_size().width == 612.0

    def test_page_size_rejects_zero_or_negative(self):
        """PageSize rejects zero or negative dimensions."""
        with pytest.raises(ValidationError):
            ir.PageSize(width=0, height=-1)


class TestExtractionBlock:
    def test_minimal_construction(self):
        """ExtractionBlock supports the minimal required evidence fields."""
        block = ir.ExtractionBlock(id=candidate_id(), backend="mineru", page_no=1, kind="paragraph", order=0, text="Hello")
        assert block.metadata == {}

    def test_id_pattern_accepted(self):
        """ExtractionBlock accepts the canonical extraction id pattern."""
        assert ir.ExtractionBlock(id="backend_1:Doc.1:p12:b3", backend="backend_1", page_no=12, kind="unknown", order=0, text="").id

    def test_id_pattern_rejected_when_malformed(self):
        """ExtractionBlock rejects ids outside the canonical extraction pattern."""
        with pytest.raises(ValidationError):
            ir.ExtractionBlock(id="bad", backend="mineru", page_no=1, kind="paragraph", order=0, text="")

    def test_confidence_in_unit_interval(self):
        """ExtractionBlock confidence is nullable or within the unit interval."""
        assert ir.ExtractionBlock(id=candidate_id(), backend="mineru", page_no=1, kind="paragraph", order=0, text="", confidence=0.5)
        with pytest.raises(ValidationError):
            ir.ExtractionBlock(id=candidate_id(), backend="mineru", page_no=1, kind="paragraph", order=0, text="", confidence=1.1)

    def test_extra_field_forbidden(self):
        """ExtractionBlock forbids fields outside the contract."""
        with pytest.raises(ValidationError):
            ir.ExtractionBlock(id=candidate_id(), backend="mineru", page_no=1, kind="paragraph", order=0, text="", extra=True)


class TestPageExtractionIR:
    def test_minimal_round_trip(self):
        """Minimal PageExtractionIR fixture round-trips through Pydantic validation."""
        round_trip(ir.PageExtractionIR, "page_extraction_ir.min.json")

    def test_full_round_trip(self):
        """Full PageExtractionIR fixture round-trips through Pydantic validation."""
        round_trip(ir.PageExtractionIR, "page_extraction_ir.full.json")

    def test_blocks_must_share_page_no(self):
        """PageExtractionIR rejects blocks from another page."""
        payload = json.loads(fixture("page_extraction_ir.min.json").read_text())
        payload["blocks"][0]["page_no"] = 2
        with pytest.raises(ValidationError):
            ir.PageExtractionIR.model_validate(payload)

    def test_blocks_must_share_backend_name(self):
        """PageExtractionIR rejects blocks from another backend."""
        payload = json.loads(fixture("page_extraction_ir.min.json").read_text())
        payload["blocks"][0]["backend"] = "deepseek"
        with pytest.raises(ValidationError):
            ir.PageExtractionIR.model_validate(payload)

    def test_block_ids_must_be_unique(self):
        """PageExtractionIR rejects duplicate block ids within a page."""
        payload = json.loads(fixture("page_extraction_ir.min.json").read_text())
        payload["blocks"].append(dict(payload["blocks"][0]))
        with pytest.raises(ValidationError):
            ir.PageExtractionIR.model_validate(payload)

    def test_schema_name_and_version_pinned(self):
        """PageExtractionIR pins the schema name and schema version literals."""
        model = round_trip(ir.PageExtractionIR, "page_extraction_ir.min.json")
        assert model.schema_name == "pdf2md.PageExtractionIR"
        assert model.schema_version == ir.SCHEMA_VERSION

    def test_json_schema_export_basic_shape(self):
        """PageExtractionIR exports a serializable JSON Schema with pinned literals."""
        schema = ir.PageExtractionIR.model_json_schema()
        assert schema["title"] == "PageExtractionIR"
        assert schema["properties"]["schema_name"]["const"] == "pdf2md.PageExtractionIR"
        assert schema["properties"]["schema_version"]["const"] == "1.0.0"
        assert schema["additionalProperties"] is False
        json.dumps(schema)


class TestConsensusBlock:
    def test_unresolved_requires_no_selected_source_and_has_conflicts(self):
        """Unresolved consensus blocks require no selected source and at least one conflict."""
        consensus_block(selection_mode="unresolved", selected_source=None, conflict_ids=[ir.conflict_id("doc-1", 0)])
        with pytest.raises(ValidationError):
            consensus_block(selection_mode="unresolved", selected_source="mineru", conflict_ids=[ir.conflict_id("doc-1", 0)])
        with pytest.raises(ValidationError):
            consensus_block(selection_mode="unresolved", selected_source=None, conflict_ids=[])

    def test_resolved_requires_selected_source(self):
        """Resolved consensus blocks require a selected source backend name."""
        with pytest.raises(ValidationError):
            consensus_block(selection_mode="agreed", selected_source=None)

    def test_agreement_score_in_unit_interval(self):
        """ConsensusBlock agreement scores are constrained to the unit interval."""
        consensus_block(agreement_score=0.0)
        with pytest.raises(ValidationError):
            consensus_block(agreement_score=-0.1)

    def test_candidate_ids_must_match_extraction_id_pattern(self):
        """ConsensusBlock candidate ids must be canonical extraction ids."""
        with pytest.raises(ValidationError):
            consensus_block(candidate_ids=["not-an-extraction-id"])


class TestConflict:
    def test_unresolved_allows_no_selected_candidate(self):
        """Unresolved conflicts may omit selected_candidate_id."""
        conflict = ir.Conflict(id=ir.conflict_id("doc-1", 0), kind="text_conflict", page_no=1, candidate_ids=[candidate_id(0), candidate_id(1)], description="diff", resolution="unresolved")
        assert conflict.selected_candidate_id is None

    def test_resolved_requires_selected_candidate_in_candidate_ids(self):
        """Resolved conflicts require selected_candidate_id to be one of the candidates."""
        ir.Conflict(id=ir.conflict_id("doc-1", 0), kind="text_conflict", page_no=1, candidate_ids=[candidate_id(0), candidate_id(1)], description="diff", resolution="resolved_by_consensus", selected_candidate_id=candidate_id(0))
        with pytest.raises(ValidationError):
            ir.Conflict(id=ir.conflict_id("doc-1", 0), kind="text_conflict", page_no=1, candidate_ids=[candidate_id(0), candidate_id(1)], description="diff", resolution="resolved_by_consensus", selected_candidate_id="deepseek:doc-1:p1:b0")

    def test_minimum_two_candidates(self):
        """Conflict candidate sets require at least two extraction candidates."""
        with pytest.raises(ValidationError):
            ir.Conflict(id=ir.conflict_id("doc-1", 0), kind="text_conflict", page_no=1, candidate_ids=[candidate_id(0)], description="diff", resolution="unresolved")


class TestConsensusIR:
    def test_minimal_round_trip(self):
        """Minimal ConsensusIR fixture round-trips through Pydantic validation."""
        round_trip(ir.ConsensusIR, "consensus_ir.min.json")

    def test_full_round_trip(self):
        """Full ConsensusIR fixture round-trips through Pydantic validation."""
        round_trip(ir.ConsensusIR, "consensus_ir.full.json")

    def test_with_conflicts_round_trip(self):
        """ConsensusIR fixture with unresolved conflicts round-trips through validation."""
        round_trip(ir.ConsensusIR, "consensus_ir.with_conflicts.json")

    def test_page_count_must_match_pages_length(self):
        """ConsensusIR page_count must equal the number of pages."""
        payload = json.loads(fixture("consensus_ir.min.json").read_text())
        payload["page_count"] = 2
        with pytest.raises(ValidationError):
            ir.ConsensusIR.model_validate(payload)

    def test_pages_must_be_contiguous_from_one(self):
        """ConsensusIR pages must be contiguous from page one."""
        payload = json.loads(fixture("consensus_ir.full.json").read_text())
        payload["pages"][1]["page_no"] = 3
        with pytest.raises(ValidationError):
            ir.ConsensusIR.model_validate(payload)

    def test_block_conflict_ids_must_exist_in_top_level_conflicts(self):
        """ConsensusIR block conflict ids must refer to top-level conflicts."""
        payload = json.loads(fixture("consensus_ir.with_conflicts.json").read_text())
        payload["conflicts"] = []
        with pytest.raises(ValidationError):
            ir.ConsensusIR.model_validate(payload)

    def test_schema_name_and_version_pinned(self):
        """ConsensusIR pins the schema name and schema version literals."""
        model = round_trip(ir.ConsensusIR, "consensus_ir.min.json")
        assert model.schema_name == "pdf2md.ConsensusIR"
        assert model.schema_version == ir.SCHEMA_VERSION

    def test_json_schema_export_basic_shape(self):
        """ConsensusIR exports a serializable JSON Schema with pinned literals."""
        schema = ir.ConsensusIR.model_json_schema()
        assert schema["title"] == "ConsensusIR"
        assert schema["properties"]["schema_name"]["const"] == "pdf2md.ConsensusIR"
        assert schema["properties"]["schema_version"]["const"] == "1.0.0"
        assert schema["additionalProperties"] is False
        json.dumps(schema)


class TestIdFactories:
    def test_extraction_id_format(self):
        """extraction_id builds ids matching the extraction regex."""
        assert ir.EXTRACTION_ID_PATTERN.fullmatch(ir.extraction_id("backend_1", "Doc.1", 12, 3))

    def test_consensus_id_format(self):
        """consensus_id builds ids matching the consensus regex."""
        assert ir.CONSENSUS_ID_PATTERN.fullmatch(ir.consensus_id("Doc.1", 12, 3))

    def test_conflict_id_format(self):
        """conflict_id builds ids matching the conflict regex."""
        assert ir.CONFLICT_ID_PATTERN.fullmatch(ir.conflict_id("Doc.1", 3))

    def test_factories_round_trip_through_validators(self):
        """Factory ids are accepted by the validators that consume them."""
        extraction = ir.extraction_id("mineru", "doc-1", 1, 0)
        ir.ExtractionBlock(id=extraction, backend="mineru", page_no=1, kind="paragraph", order=0, text="")
        consensus_block(id=ir.consensus_id("doc-1", 1, 0), candidate_ids=[extraction])
        ir.Conflict(id=ir.conflict_id("doc-1", 0), kind="text_conflict", page_no=1, candidate_ids=[extraction, ir.extraction_id("deepseek", "doc-1", 1, 0)], description="diff", resolution="unresolved")
