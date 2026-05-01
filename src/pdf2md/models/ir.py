"""Planning scaffold for page-level IR and consensus IR.

This module is intentionally documentation-first for the current step.
It declares where IR models and serialization/deserialization interfaces
will live without implementing backend-specific logic yet.
"""

# TODO: Add ExtractionDocument / ExtractionPage / ExtractionBlock models.
# TODO: Add PageConsensusIR models (CandidateGroup, AgreedBlock, Conflict, etc.).
# TODO: Define model-level `to_dict` / `from_dict` and JSON serialization helpers.
# NOTE: Keep this additive to the existing Document -> Page -> Block schema.


class IRModelScaffold:
    """Placeholder base type for future IR models.

    Intended responsibility:
    - provide shared serialization and deserialization interface contracts.
    - centralize common metadata/provenance fields used across IR entities.
    """

    pass
