"""Tests for marker adjudication label-file schemas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pdf2md.diagnostics.adjudication import AdjudicationDocument, merge_documents

FIXTURE = Path("tests/data/semantic_fixtures/sample_adjudications.json")


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_sample_adjudications_validate_all_decisions() -> None:
    doc = AdjudicationDocument.model_validate(_payload())
    assert doc.schema_name == "pdf2md.MarkerAdjudication"
    assert doc.schema_version == "1.0.0"
    assert doc.document_id == "fixture-doc"
    assert {item.decision for item in doc.adjudications} == {
        "resolve",
        "reclassify",
        "noise",
        "rule_hint",
    }


@pytest.mark.parametrize(
    ("decision", "updates"),
    [
        ("resolve", {"target_entity_id": None}),
        ("noise", {"target_entity_id": "ent:bad"}),
        ("rule_hint", {"rule_hint": "", "corrected_type": "figure"}),
    ],
)
def test_exactly_one_payload_field_matches_decision(decision: str, updates: dict) -> None:
    payload = _payload()
    item = payload["adjudications"][0]
    item.update({"decision": decision, "target_entity_id": None, "corrected_type": None, "rule_hint": None})
    item.update(updates)
    with pytest.raises(ValidationError, match="payload field|noise"):
        AdjudicationDocument.model_validate(payload)


def test_ref_type_values_are_constrained() -> None:
    payload = _payload()
    payload["adjudications"][0]["marker_type"] = "appendixish"
    with pytest.raises(ValidationError):
        AdjudicationDocument.model_validate(payload)

    payload = _payload()
    payload["adjudications"][1]["corrected_type"] = "appendixish"
    with pytest.raises(ValidationError):
        AdjudicationDocument.model_validate(payload)


def test_merge_documents_without_conflicts_adds_markers() -> None:
    left = AdjudicationDocument.model_validate(_payload())
    right_payload = _payload()
    right_payload["adjudications"] = [right_payload["adjudications"][0] | {"marker_id": "marker:new"}]
    right = AdjudicationDocument.model_validate(right_payload)

    merged = merge_documents(left, right, merged_from="right.json")
    assert len(merged.adjudications) == 5
    assert merged.metadata.import_history[-1].added == 1
    assert merged.metadata.import_history[-1].overwritten == 0


def test_merge_documents_conflict_latest_decision_wins() -> None:
    left = AdjudicationDocument.model_validate(_payload())
    right_payload = _payload()
    right_payload["adjudications"] = [
        right_payload["adjudications"][0]
        | {
            "decision": "noise",
            "target_entity_id": None,
            "corrected_type": None,
            "rule_hint": None,
            "decided_at": "2026-05-31T01:00:00Z",
        }
    ]
    right = AdjudicationDocument.model_validate(right_payload)

    merged = merge_documents(left, right, merged_from="right.json")
    winner = next(item for item in merged.adjudications if item.marker_id == right.adjudications[0].marker_id)
    assert winner.decision == "noise"
    assert merged.metadata.import_history[-1].added == 0
    assert merged.metadata.import_history[-1].overwritten == 1


def test_merge_documents_rejects_mismatched_document_id() -> None:
    left = AdjudicationDocument.model_validate(_payload())
    right_payload = _payload() | {"document_id": "other-doc"}
    right = AdjudicationDocument.model_validate(right_payload)
    with pytest.raises(ValueError, match="document_id mismatch"):
        merge_documents(left, right)
