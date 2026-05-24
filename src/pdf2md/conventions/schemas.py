"""Dataclasses describing convention rules and their match qualifiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Rule:
    """A convention normalisation rule.

    Attributes:
        id: Unique rule identifier (e.g. ``caption.figure_or_table_prefix``).
        backend: Backend filter, or ``*`` for any backend.
        object_type: Object-type filter, or ``*`` for any type.
        text_regex: Pattern the block text must match for the rule to fire.
        normalised_type: New block type to assign when the rule matches.
        normalised_text_rewrite: Optional ``re.sub`` replacement applied to
            the matched text.
        extract_equation_label: If True, capture the numeric label from
            the text for equation linking.
        requires_near_caption_regex: Optional regex; if set, the rule
            only fires when a neighbouring block matches this pattern.
        y_norm_min: Optional minimum normalised y-coordinate gate
            (0-1000).
        merge_with_nearby_formula: Hint for the consensus stage to merge
            this block with an adjacent formula block.
        merge_when_text_exact: Hint to merge blocks with identical text.
        geometry_required: When False, accept geometry-less blocks
            (relevant for the deepseek backend).
        reason: Human-readable provenance string.
    """

    id: str
    backend: str
    object_type: str
    text_regex: str
    normalised_type: str | None = None
    normalised_text_rewrite: str | None = None
    extract_equation_label: bool = False
    requires_near_caption_regex: str | None = None
    y_norm_min: float | None = None
    merge_with_nearby_formula: bool = False
    merge_when_text_exact: bool = False
    geometry_required: bool | None = None
    reason: str = ""


@dataclass
class RuleEvidence:
    """Aggregated evidence supporting a proposed convention rule.

    Attributes:
        rule_id: Rule identifier this evidence supports.
        backend: Backend the evidence applies to.
        object_type: Object type the evidence applies to.
        support_count: Number of distinct blocks supporting the rule.
        supporting_doc_ids: Documents in which the rule was observed.
        supporting_backend_block_ids: Block IDs that triggered the rule.
        groundtruth_source: Provenance string for the ground-truth basis.
        example_before: Representative text before normalisation.
        example_after: Representative text after normalisation.
        reason: Human-readable rationale string.
    """

    rule_id: str
    backend: str
    object_type: str
    support_count: int = 0
    supporting_doc_ids: list[str] = field(default_factory=list)
    supporting_backend_block_ids: list[str] = field(default_factory=list)
    groundtruth_source: str = ""
    example_before: str = ""
    example_after: str = ""
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict view with deduplicated id lists."""
        return {
            "rule_id": self.rule_id,
            "backend": self.backend,
            "object_type": self.object_type,
            "support_count": self.support_count,
            "supporting_doc_ids": sorted(set(self.supporting_doc_ids)),
            "supporting_backend_block_ids": sorted(set(self.supporting_backend_block_ids)),
            "groundtruth_source": self.groundtruth_source,
            "example_before": self.example_before,
            "example_after": self.example_after,
            "reason": self.reason,
        }
