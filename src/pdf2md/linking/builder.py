"""Build document-level LinkedStructure payloads from consensus IR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

from pdf2md.linking.extract import extract_link_candidates
from pdf2md.linking.graph_utils import linked_structure_to_graph
from pdf2md.linking.reporting import build_linking_report
from pdf2md.linking.resolvers import run_all_resolvers
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import ConsensusIR
from pdf2md.models.linked import (
    LinkedConflict,
    LinkedNode,
    LinkedNodeType,
    LinkedRelation,
    LinkedRelationType,
    LinkedStructure,
    LinkEvidence,
    LinkEvidenceKind,
    LinkStatus,
    linked_conflict_id,
    linked_node_id,
    linked_relation_id,
)
from pdf2md.models.priors import CalibrationPriorDocument


@dataclass(frozen=True)
class LinkerSettings:
    """Configuration for the semantic linker build pass.

    Attributes:
        strict: If True, fail fast on input problems instead of recording
            warnings.
        default_confidence: Confidence assigned to derived evidence that has
            no calibrated source (e.g. preserved consensus conflicts).
        low_confidence_threshold: Confidence below which a node or relation
            is marked ``RESOLVED_LOW_CONFIDENCE`` instead of ``RESOLVED``.
    """

    strict: bool = False
    default_confidence: float = 0.50
    low_confidence_threshold: float = 0.60


@dataclass(frozen=True)
class LinkerRunResult:
    """Output of a single semantic linker run.

    Attributes:
        linked: The fully built ``LinkedStructure`` (nodes, relations,
            conflicts).
        report: Aggregate linking report ready to be serialised as JSON.
        warnings: Non-fatal warnings produced during linking, with stable
            string codes.
    """

    linked: LinkedStructure
    report: dict[str, Any]
    warnings: list[str]

    @property
    def graph(self) -> nx.MultiDiGraph:
        """networkx view derived from ``linked``.

        One node per ``LinkedNode``, one edge per ``LinkedRelation``. This is
        additive and computed on access: ``linked`` (its node/relation lists)
        remains the source of truth and serialisation format, so any consumer
        that constructs a ``LinkerRunResult`` directly still gets a graph
        consistent with its structure. See :mod:`pdf2md.linking.graph_utils`.
        """

        return linked_structure_to_graph(self.linked)


def _status(confidence: float, settings: LinkerSettings) -> LinkStatus:
    return LinkStatus.RESOLVED if confidence >= settings.low_confidence_threshold else LinkStatus.RESOLVED_LOW_CONFIDENCE


def _candidate_node_id(document_id: str, index_by_candidate: dict[str, int], candidate_id: str) -> str:
    return linked_node_id(document_id, index_by_candidate[candidate_id])


def build_linked_structure(
    *,
    consensus: ConsensusIR,
    entities_by_backend: dict[str, EntityProposalDocument],
    priors_by_backend: dict[str, CalibrationPriorDocument],
    consensus_report: dict[str, Any] | None = None,
    source_consensus_ir: str | None = None,
    source_consensus_report: str | None = None,
    source_entity_documents: list[str] | None = None,
    source_prior_documents: list[str] | None = None,
    settings: LinkerSettings = LinkerSettings(),
) -> LinkerRunResult:
    """Promote consensus blocks to linked nodes and run all resolvers.

    Each consensus block becomes a ``LinkedNode`` whose type is refined by
    supporting entity evidence and whose confidence blends agreement score,
    entity confidences, and calibration priors. Every node receives a
    ``DERIVED_FROM_CONSENSUS`` relation from the document root. The full
    chain of semantic resolvers (reading order, section hierarchy, ToC,
    page-number sequence, headers/footers, captions, footnotes, equation
    sequence, figure/table sequence, references) is then run to produce the
    inter-node relations. Source consensus conflicts and unresolved resolver
    warnings are preserved as ``LinkedConflict`` records.

    Args:
        consensus: Consensus IR for the document to link.
        entities_by_backend: Entity proposal documents keyed by backend name.
        priors_by_backend: Calibration prior documents keyed by backend name.
        consensus_report: Optional consensus report payload (recorded in
            output metadata only).
        source_consensus_ir: Source path of the consensus IR (recorded in the
            ``LinkedStructure`` for traceability).
        source_consensus_report: Source path of the consensus report.
        source_entity_documents: Source paths of the per-backend entity
            documents.
        source_prior_documents: Source paths of the per-backend prior
            documents.
        settings: Linker configuration knobs.

    Returns:
        A ``LinkerRunResult`` containing the linked structure, the linking
        report, and accumulated warnings.
    """
    candidates = extract_link_candidates(consensus=consensus, entities_by_backend=entities_by_backend, priors_by_backend=priors_by_backend)
    nodes: list[LinkedNode] = [
        LinkedNode(
            id=linked_node_id(consensus.document_id, 0),
            node_type=LinkedNodeType.DOCUMENT,
            text=None,
            page_no=None,
            order=0,
            consensus_block_id=None,
            source_backend=None,
            source_entity_ids=[],
            confidence=1.0,
            status=LinkStatus.RESOLVED,
            evidence=[LinkEvidence(kind=LinkEvidenceKind.CONSENSUS_BLOCK, source_id=source_consensus_ir, page_no=None, confidence=1.0, reason="document root", metadata={})],
            metadata={"page_count": consensus.page_count},
        )
    ]
    index_by_candidate: dict[str, int] = {}
    for idx, candidate in enumerate(candidates, start=1):
        index_by_candidate[candidate.consensus_block_id] = idx
        nodes.append(
            LinkedNode(
                id=linked_node_id(consensus.document_id, idx),
                node_type=candidate.node_type,
                text=candidate.text,
                page_no=candidate.page_no,
                order=candidate.order,
                consensus_block_id=candidate.consensus_block_id,
                source_backend=candidate.source_backend,
                source_entity_ids=list(candidate.source_entity_ids),
                confidence=candidate.confidence,
                status=_status(candidate.confidence, settings),
                evidence=[
                    LinkEvidence(
                        kind=LinkEvidenceKind.CONSENSUS_BLOCK,
                        source_id=candidate.consensus_block_id,
                        page_no=candidate.page_no,
                        confidence=candidate.confidence,
                        reason="consensus block promoted to linked node",
                        metadata={"source_backend": candidate.source_backend},
                    )
                ],
                metadata=dict(candidate.metadata),
            )
        )

    relations: list[LinkedRelation] = []
    rel_index = 0
    document_node_id = linked_node_id(consensus.document_id, 0)
    for candidate in candidates:
        rel_index += 1
        relations.append(
            LinkedRelation(
                id=linked_relation_id(consensus.document_id, rel_index),
                relation_type=LinkedRelationType.DERIVED_FROM_CONSENSUS,
                source_node_id=document_node_id,
                target_node_id=_candidate_node_id(consensus.document_id, index_by_candidate, candidate.consensus_block_id),
                confidence=1.0,
                status=LinkStatus.RESOLVED,
                evidence=[LinkEvidence(kind=LinkEvidenceKind.CONSENSUS_BLOCK, source_id=candidate.consensus_block_id, page_no=candidate.page_no, confidence=1.0, reason="document contains consensus-derived node", metadata={})],
                metadata={},
            )
        )

    resolver_result = run_all_resolvers(candidates)
    for link in resolver_result.links:
        if link.source_candidate_id not in index_by_candidate or link.target_candidate_id not in index_by_candidate:
            continue
        rel_index += 1
        relations.append(
            LinkedRelation(
                id=linked_relation_id(consensus.document_id, rel_index),
                relation_type=link.relation_type,
                source_node_id=_candidate_node_id(consensus.document_id, index_by_candidate, link.source_candidate_id),
                target_node_id=_candidate_node_id(consensus.document_id, index_by_candidate, link.target_candidate_id),
                confidence=link.confidence,
                status=link.status,
                evidence=list(link.evidence),
                metadata=dict(link.metadata),
            )
        )

    def _linked_warning(warning: str) -> str:
        if ":" not in warning:
            return warning
        prefix, candidate_id = warning.split(":", 1)
        if candidate_id not in index_by_candidate:
            return warning
        return f"{prefix}:{_candidate_node_id(consensus.document_id, index_by_candidate, candidate_id)}"

    warnings = [_linked_warning(warning) for warning in resolver_result.warnings]
    conflicts: list[LinkedConflict] = []
    conflict_index = 0
    candidate_by_id = {candidate.consensus_block_id: candidate for candidate in candidates}
    for source_conflict in consensus.conflicts:
        conflict_candidate_ids = set(source_conflict.candidate_ids)
        related = [
            linked_node_id(consensus.document_id, idx)
            for cid, idx in index_by_candidate.items()
            if conflict_candidate_ids.intersection(candidate_by_id[cid].metadata.get("candidate_ids", []))
        ]
        conflict_index += 1
        conflicts.append(
            LinkedConflict(
                id=linked_conflict_id(consensus.document_id, conflict_index),
                conflict_type=str(source_conflict.kind),
                source_conflict_id=source_conflict.id,
                node_ids=related,
                relation_ids=[],
                description=source_conflict.description,
                status=LinkStatus.UNRESOLVED if source_conflict.resolution == "unresolved" else LinkStatus.RESOLVED,
                evidence=[LinkEvidence(kind=LinkEvidenceKind.CONSENSUS_BLOCK, source_id=source_conflict.id, page_no=source_conflict.page_no, confidence=settings.default_confidence, reason="preserved source consensus conflict", metadata={})],
                metadata=dict(source_conflict.metadata),
            )
        )
        if source_conflict.resolution == "unresolved":
            warnings.append("unresolved_semantic_ambiguity")

    for warning in resolver_result.warnings:
        if ":" in warning:
            _, candidate_id = warning.split(":", 1)
            node_ids = []
            if candidate_id in index_by_candidate:
                node_ids.append(_candidate_node_id(consensus.document_id, index_by_candidate, candidate_id))
            conflict_index += 1
            conflicts.append(
                LinkedConflict(
                    id=linked_conflict_id(consensus.document_id, conflict_index),
                    conflict_type=warning.split(":", 1)[0],
                    source_conflict_id=None,
                    node_ids=node_ids,
                    relation_ids=[],
                    description=warning,
                    status=LinkStatus.UNRESOLVED,
                    evidence=[LinkEvidence(kind=LinkEvidenceKind.TEXT_PATTERN, source_id=candidate_id, page_no=None, confidence=settings.default_confidence, reason="unresolved resolver warning", metadata={})],
                    metadata={},
                )
            )

    linked = LinkedStructure(
        document_id=consensus.document_id,
        source_consensus_ir=source_consensus_ir,
        source_consensus_report=source_consensus_report,
        source_entity_documents=source_entity_documents or [],
        source_prior_documents=source_prior_documents or [],
        nodes=nodes,
        relations=relations,
        conflicts=conflicts,
        warnings=warnings,
        metadata={"consensus_report_present": consensus_report is not None},
    )
    report = build_linking_report(linked)
    return LinkerRunResult(linked=linked, report=report, warnings=warnings)
