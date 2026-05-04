from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Rule:
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
