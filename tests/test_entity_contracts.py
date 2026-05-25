import pytest
from pydantic import ValidationError

from pdf2md.models.entities import *
from pdf2md.models.ir import BBox, CoordOrigin

BLOCK_ID = "mineru:doc_001:p1:b0"
ENT1 = "ent:mineru:doc_001:section:1"
ENT2 = "ent:mineru:doc_001:caption:2"
REL1 = "rel:mineru:doc_001:1"


def evidence(**kwargs):
    data = dict(kind=EvidenceKind.BLOCK_TEXT, page_no=1, source_block_id=BLOCK_ID, raw_ref=None, text="x", bbox=None, weight=1.0, reason="test", metadata={})
    data.update(kwargs)
    return EntityEvidence(**data)


def entity(**kwargs):
    data = dict(id=ENT1, entity_type=EntityType.SECTION, subtype=None, canonical_text="Intro", page_no=1, block_ids=[BLOCK_ID], confidence=0.5, confidence_source=ConfidenceSource.HEURISTIC, evidence=[evidence()], calibration_key=None, metadata={})
    data.update(kwargs)
    return EntityProposal(**data)


def relation(**kwargs):
    data = dict(id=REL1, relation_type=RelationType.NEAR, source_entity_id=ENT1, target_entity_id=ENT2, confidence=0.5, confidence_source=ConfidenceSource.HEURISTIC, evidence=[evidence()], metadata={})
    data.update(kwargs)
    return RelationProposal(**data)


class TestEntityEnums:
    def test_entity_type_values_match_specification(self):
        assert {e.value for e in EntityType} == {"document_title","chapter","section","toc_entry","page_number","header","footer","footnote","equation","figure","table","caption","reference_section","reference_item","bibliography_marker","index_section","index_entry","glossary_section","glossary_entry","unknown"}
    def test_relation_type_values_match_specification(self):
        assert {e.value for e in RelationType} == {"caption_of","footnote_anchor_for","toc_points_to","reference_mention_of","glossary_defines","same_entity_as","near","sequence_next","candidate_for"}
    def test_evidence_kind_values_match_specification(self):
        assert "markdown_syntax" in {e.value for e in EvidenceKind}
    def test_confidence_source_values_match_specification(self):
        assert {e.value for e in ConfidenceSource} == {"heuristic","calibrated","manual","unknown"}


class TestEntityEvidence:
    def test_minimal_evidence_constructs(self): assert evidence().weight == 1.0
    def test_evidence_accepts_ir_bbox(self): assert evidence(bbox=BBox(l=0,t=1,r=1,b=0,coord_origin=CoordOrigin.BOTTOMLEFT)).bbox is not None
    def test_evidence_rejects_weight_outside_unit_interval(self):
        with pytest.raises(ValidationError): evidence(weight=1.1)
    def test_evidence_rejects_malformed_source_block_id(self):
        with pytest.raises(ValidationError): evidence(source_block_id="bad")
    def test_evidence_forbids_extra_fields(self):
        with pytest.raises(ValidationError): EntityEvidence(kind=EvidenceKind.BLOCK_TEXT, page_no=1, source_block_id=None, raw_ref=None, text=None, bbox=None, weight=1, reason="x", metadata={}, extra=1)


class TestEntityProposal:
    def test_entity_id_pattern_accepted(self): assert entity().id == ENT1
    def test_entity_id_pattern_rejected(self):
        with pytest.raises(ValidationError): entity(id="bad")
    def test_entity_requires_at_least_one_evidence(self):
        with pytest.raises(ValidationError): entity(evidence=[])
    def test_entity_block_ids_must_match_extraction_id_pattern(self):
        with pytest.raises(ValidationError): entity(block_ids=["bad"])
    def test_entity_confidence_in_unit_interval(self):
        with pytest.raises(ValidationError): entity(confidence=-0.1)
    def test_entity_forbids_extra_fields(self):
        with pytest.raises(ValidationError): EntityProposal(**{**entity().model_dump(), "extra": 1})


class TestRelationProposal:
    def test_relation_id_pattern_accepted(self): assert relation().id == REL1
    def test_relation_id_pattern_rejected(self):
        with pytest.raises(ValidationError): relation(id="bad")
    def test_relation_requires_distinct_source_and_target(self):
        with pytest.raises(ValidationError): relation(target_entity_id=ENT1)
    def test_relation_confidence_in_unit_interval(self):
        with pytest.raises(ValidationError): relation(confidence=2)
    def test_relation_requires_evidence(self):
        with pytest.raises(ValidationError): relation(evidence=[])
    def test_relation_endpoint_ids_must_match_entity_pattern(self):
        with pytest.raises(ValidationError): relation(source_entity_id="bad")


class TestEntityProposalDocument:
    def test_minimal_document_round_trip(self):
        e1 = entity(id=ENT1); e2 = entity(id=ENT2, entity_type=EntityType.CAPTION)
        doc = EntityProposalDocument(document_id="doc_001", backend="mineru", backend_version=None, page_count=1, entities=[e1,e2], relations=[relation()], warnings=[], metadata={})
        assert EntityProposalDocument.model_validate_json(doc.model_dump_json()).document_id == "doc_001"
    def test_document_rejects_duplicate_entity_ids(self):
        with pytest.raises(ValidationError): EntityProposalDocument(document_id="d", backend="b", page_count=1, entities=[entity(), entity()], relations=[], warnings=[], metadata={})
    def test_document_rejects_duplicate_relation_ids(self):
        e1=entity(id=ENT1); e2=entity(id=ENT2, entity_type=EntityType.CAPTION); r=relation()
        with pytest.raises(ValidationError): EntityProposalDocument(document_id="d", backend="b", page_count=1, entities=[e1,e2], relations=[r,r], warnings=[], metadata={})
    def test_document_rejects_relation_with_unknown_source(self):
        e2=entity(id=ENT2, entity_type=EntityType.CAPTION)
        with pytest.raises(ValidationError): EntityProposalDocument(document_id="d", backend="b", page_count=1, entities=[e2], relations=[relation()], warnings=[], metadata={})
    def test_document_rejects_relation_with_unknown_target(self):
        with pytest.raises(ValidationError): EntityProposalDocument(document_id="d", backend="b", page_count=1, entities=[entity()], relations=[relation()], warnings=[], metadata={})
    def test_json_schema_export_basic_shape(self): assert EntityProposalDocument.model_json_schema()["title"] == "EntityProposalDocument"


class TestEntityIdFactories:
    def test_entity_id_format(self): assert entity_id("mineru", "doc_001", EntityType.SECTION, 1) == ENT1
    def test_relation_id_format(self): assert relation_id("mineru", "doc_001", 1) == REL1
    def test_factories_round_trip_through_validators(self): assert relation(id=relation_id("mineru", "doc_001", 1), source_entity_id=entity_id("mineru","doc_001",EntityType.SECTION,1), target_entity_id=entity_id("mineru","doc_001",EntityType.CAPTION,2))
