"""Build canonical ConsensusIR objects from connector outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pdf2md.consensus.grouping import CandidateGroup, group_document_candidates
from pdf2md.consensus.reporting import build_consensus_report
from pdf2md.consensus.scoring import ConsensusScoringSettings, GroupScore, score_candidate_group
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import (
    BackendManifest,
    Conflict,
    ConsensusBlock,
    ConsensusIR,
    ConsensusPage,
    PageExtractionIR,
    PageSize,
    SelectionMode,
    conflict_id,
    consensus_id,
)
from pdf2md.models.priors import CalibrationPriorDocument


@dataclass(frozen=True)
class ConsensusRunResult:
    """Result of a single consensus build.

    Attributes:
        consensus: Canonical ConsensusIR for the document.
        report: Structured consensus report (selection counts,
            per-backend summary, etc.).
        warnings: Warnings accumulated during consensus assembly.
    """

    consensus: ConsensusIR
    report: dict[str, Any]
    warnings: list[str]


@dataclass(frozen=True)
class ConsensusFactorySettings:
    """Tunables for the consensus factory pipeline.

    Attributes:
        scoring: Candidate scoring settings forwarded to
            :func:`pdf2md.consensus.scoring.score_candidate_group`.
        strict: If True, downstream loaders raise on missing/invalid
            inputs instead of warning.
    """

    scoring: ConsensusScoringSettings = field(default_factory=ConsensusScoringSettings)
    strict: bool = False


def _value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _page_sizes(pages_by_backend: dict[str, list[PageExtractionIR]]) -> dict[int, PageSize]:
    sizes: dict[int, PageSize] = {}
    for pages in pages_by_backend.values():
        for page in pages:
            sizes.setdefault(page.page_no, page.page_size)
    return sizes


def _group_sort_key(group_score: GroupScore) -> tuple[int, int, str]:
    candidate = group_score.selected.candidate if group_score.selected else group_score.candidate_scores[0].candidate
    return (group_score.group.page_no, candidate.block.order, group_score.group.id)


def _make_conflict(document_id: str, index: int, score: GroupScore) -> Conflict:
    candidate_ids = [candidate.block.id for candidate in score.group.candidates]
    return Conflict(
        id=conflict_id(document_id, index),
        kind=score.conflict_kind or "presence_conflict",
        page_no=score.group.page_no,
        candidate_ids=candidate_ids,
        description=f"Unresolved consensus group {score.group.id}",
        resolution="unresolved",
        selected_candidate_id=None,
        metadata={
            "group_id": score.group.id,
            "candidate_scores": [
                {
                    "candidate_id": candidate_score.candidate.block.id,
                    "backend": candidate_score.candidate.backend,
                    "score": candidate_score.score,
                    "metadata": candidate_score.metadata,
                }
                for candidate_score in score.candidate_scores
            ],
            "conflict_reason": _value(score.conflict_kind or "presence_conflict"),
        },
    )


def _make_block(document_id: str, page_no: int, index: int, score: GroupScore, conflict_ids: list[str]) -> ConsensusBlock:
    source_score = score.selected or score.candidate_scores[0]
    source = source_score.candidate.block
    kind = source_score.metadata.get("inferred_kind", source.kind)
    return ConsensusBlock(
        id=consensus_id(document_id, page_no, index),
        kind=kind,
        bbox=source.bbox,
        order=index,
        text=source.text,
        selection_mode=score.selection_mode,
        selected_source=source_score.candidate.backend if score.selection_mode != SelectionMode.UNRESOLVED else None,
        agreement_score=score.agreement_score,
        candidate_ids=[candidate.block.id for candidate in score.group.candidates],
        conflict_ids=conflict_ids,
        metadata={
            "group_id": score.group.id,
            "group_reason": score.group.reason,
            "selected_candidate_id": source.id if score.selected else None,
            **source_score.metadata,
        },
    )


def _backend_summary(
    pages_by_backend: dict[str, list[PageExtractionIR]],
    priors_by_backend: dict[str, CalibrationPriorDocument],
) -> dict[str, dict[str, Any]]:
    return {
        backend: {
            "page_count": len(pages),
            "block_count": sum(len(page.blocks) for page in pages),
            "prior_loaded": backend in priors_by_backend,
        }
        for backend, pages in sorted(pages_by_backend.items())
    }


def build_consensus_ir(
    *,
    document_id: str,
    pages_by_backend: dict[str, list[PageExtractionIR]],
    entities_by_backend: dict[str, EntityProposalDocument],
    priors_by_backend: dict[str, CalibrationPriorDocument],
    settings: ConsensusFactorySettings = ConsensusFactorySettings(),
) -> ConsensusRunResult:
    """Build a canonical ConsensusIR from per-backend connector outputs.

    Groups candidate blocks page-by-page via
    :func:`pdf2md.consensus.grouping.group_document_candidates`, scores
    each group via
    :func:`pdf2md.consensus.scoring.score_candidate_group`, and emits a
    ConsensusIR with per-page consensus blocks, conflicts for
    unresolved groups, and a summary report.

    Args:
        document_id: Stable document identifier embedded in consensus
            IDs.
        pages_by_backend: Per-backend page IR keyed by backend name.
        entities_by_backend: Per-backend entity proposal documents keyed
            by backend name.
        priors_by_backend: Per-backend calibration priors keyed by
            backend name. Backends missing a prior receive a warning.
        settings: Factory settings (scoring weights, strict mode).

    Returns:
        A ConsensusRunResult bundling the ConsensusIR, structured
        report, and warnings.
    """
    warnings: list[str] = []
    for backend in sorted(pages_by_backend):
        if backend not in entities_by_backend:
            warnings.append(f"entities_missing:{backend}")
        if backend not in priors_by_backend:
            warnings.append(f"prior_missing:{backend}")

    groups = group_document_candidates(pages_by_backend=pages_by_backend, entities_by_backend=entities_by_backend)
    group_scores = [
        score_candidate_group(
            group=group,
            priors_by_backend=priors_by_backend,
            entities_by_backend=entities_by_backend,
            settings=settings.scoring,
        )
        for group in groups
    ]
    group_scores.sort(key=_group_sort_key)
    conflicts: list[Conflict] = []
    conflict_ids_by_group: dict[str, list[str]] = {}
    for score in group_scores:
        if score.selection_mode == SelectionMode.UNRESOLVED:
            conflict = _make_conflict(document_id, len(conflicts), score)
            conflicts.append(conflict)
            conflict_ids_by_group[score.group.id] = [conflict.id]

    sizes = _page_sizes(pages_by_backend)
    page_count = max(sizes.keys(), default=0)
    blocks_by_page: dict[int, list[ConsensusBlock]] = {page_no: [] for page_no in range(1, page_count + 1)}
    for score in group_scores:
        page_no = score.group.page_no
        block_index = len(blocks_by_page.setdefault(page_no, []))
        blocks_by_page[page_no].append(
            _make_block(document_id, page_no, block_index, score, conflict_ids_by_group.get(score.group.id, []))
        )

    pages = [
        ConsensusPage(page_no=page_no, page_size=sizes.get(page_no) or PageSize(width=1, height=1), blocks=blocks_by_page.get(page_no, []))
        for page_no in range(1, page_count + 1)
    ]
    selection_counts: dict[str, int] = {mode.value: 0 for mode in SelectionMode}
    for page in pages:
        for block in page.blocks:
            selection_counts[_value(block.selection_mode)] += 1
    consensus = ConsensusIR(
        document_id=document_id,
        page_count=page_count,
        pages=pages,
        conflicts=conflicts,
        backends=[BackendManifest(backend=backend) for backend in sorted(pages_by_backend)],
        agreement_summary={"selection_counts": selection_counts, "group_count": len(groups)},
        metadata={"factory": "consensus_v2"},
    )
    consensus = ConsensusIR.model_validate(consensus.model_dump(mode="json"))
    report = build_consensus_report(
        consensus=consensus,
        warnings=warnings,
        backend_summary=_backend_summary(pages_by_backend, priors_by_backend),
    )
    return ConsensusRunResult(consensus=consensus, report=report, warnings=warnings)
