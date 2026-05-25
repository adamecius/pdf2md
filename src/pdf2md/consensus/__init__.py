"""Consensus factory v2 components."""

from pdf2md.consensus.entity_merge import CONSENSUS_BACKEND, merge_entity_documents
from pdf2md.consensus.factory import ConsensusFactorySettings, ConsensusRunResult, build_consensus_ir

__all__ = [
    "CONSENSUS_BACKEND",
    "ConsensusFactorySettings",
    "ConsensusRunResult",
    "build_consensus_ir",
    "merge_entity_documents",
]
