import pytest
from pydantic import ValidationError

from pdf2md.models.ir import consensus_id, conflict_id
from pdf2md.models.linked import *


def evidence():
    return LinkEvidence(kind=LinkEvidenceKind.TEXT_PATTERN, source_id="src", page_no=1, confidence=0.9, reason="reason", metadata={})


def node(i=1, **kw):
    data = dict(id=linked_node_id("doc", i), node_type=LinkedNodeType.PARAGRAPH, text="x", page_no=1, order=i, consensus_block_id=consensus_id("doc",1,i), source_backend="mineru", source_entity_ids=[], confidence=0.8, status=LinkStatus.RESOLVED, evidence=[evidence()], metadata={})
    data.update(kw)
    return LinkedNode(**data)


def rel(i=1, src=None, tgt=None, **kw):
    data = dict(id=linked_relation_id("doc", i), relation_type=LinkedRelationType.FOLLOWS, source_node_id=src or linked_node_id("doc",1), target_node_id=tgt or linked_node_id("doc",2), confidence=0.8, status=LinkStatus.RESOLVED, evidence=[evidence()], metadata={})
    data.update(kw)
    return LinkedRelation(**data)


def conflict(i=1, **kw):
    data=dict(id=linked_conflict_id("doc",i), conflict_type="missing", source_conflict_id=conflict_id("doc",0), node_ids=[linked_node_id("doc",1)], relation_ids=[], description="desc", status=LinkStatus.UNRESOLVED, evidence=[evidence()], metadata={})
    data.update(kw)
    return LinkedConflict(**data)


def test_enum_values():
    assert LinkedNodeType.TOC_ENTRY == "toc_entry"
    assert LinkedRelationType.CAPTION_OF == "caption_of"
    assert LinkStatus.UNRESOLVED == "unresolved"
    assert LinkEvidenceKind.FOOTNOTE_PATTERN == "footnote_pattern"


def test_evidence_validation_accepts_valid():
    assert evidence().confidence == 0.9

@pytest.mark.parametrize("kwargs", [dict(page_no=0), dict(confidence=1.1), dict(reason="")])
def test_evidence_rejects_invalid(kwargs):
    data = dict(kind=LinkEvidenceKind.TEXT_PATTERN, source_id=None, page_no=1, confidence=0.5, reason="x", metadata={})
    data.update(kwargs)
    with pytest.raises(ValidationError):
        LinkEvidence(**data)


def test_node_accepts_valid_and_factory_ids():
    assert node().id == "node:doc:1"

@pytest.mark.parametrize("kwargs", [dict(id="bad"), dict(page_no=0), dict(order=-1), dict(confidence=-.1), dict(evidence=[]), dict(consensus_block_id="bad")])
def test_node_rejects_invalid(kwargs):
    with pytest.raises(ValidationError):
        node(**kwargs)


def test_relation_accepts_valid():
    assert rel().source_node_id == "node:doc:1"

@pytest.mark.parametrize("kwargs", [dict(id="bad"), dict(source_node_id="bad"), dict(target_node_id="node:doc:1"), dict(confidence=2), dict(evidence=[])])
def test_relation_rejects_invalid(kwargs):
    with pytest.raises(ValidationError):
        rel(**kwargs)


def test_conflict_accepts_valid():
    assert conflict().source_conflict_id == "conf:doc:0"

@pytest.mark.parametrize("kwargs", [dict(id="bad"), dict(source_conflict_id="bad"), dict(node_ids=["bad"]), dict(relation_ids=["bad"]), dict(description=""), dict(evidence=[])])
def test_conflict_rejects_invalid(kwargs):
    with pytest.raises(ValidationError):
        conflict(**kwargs)


def structure(**kw):
    n1=node(1); n2=node(2)
    r=rel(1)
    data=dict(document_id="doc", nodes=[n1,n2], relations=[r], conflicts=[conflict(relation_ids=[r.id])], warnings=[], metadata={})
    data.update(kw)
    return LinkedStructure(**data)


def test_structure_round_trip_and_schema():
    s=structure()
    assert LinkedStructure.model_validate_json(s.model_dump_json()).document_id == "doc"
    assert LinkedStructure.model_json_schema()["title"] == "LinkedStructure"

@pytest.mark.parametrize("kwargs", [dict(nodes=[node(1),node(1)]), dict(relations=[rel(1),rel(1)]), dict(conflicts=[conflict(1),conflict(1)]), dict(relations=[rel(src="node:doc:1", tgt="node:doc:9")]), dict(conflicts=[conflict(node_ids=["node:doc:9"])]), dict(conflicts=[conflict(relation_ids=["lrel:doc:9"])])])
def test_structure_rejects_invalid_graph(kwargs):
    with pytest.raises(ValidationError):
        structure(**kwargs)


def test_schema_defaults_are_set():
    s = structure()
    assert s.schema_name == "pdf2md.LinkedStructure"
    assert s.schema_version == LINKED_SCHEMA_VERSION


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        LinkedNode(**{**node().model_dump(), "unexpected": True})
