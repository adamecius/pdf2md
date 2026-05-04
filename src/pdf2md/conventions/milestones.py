from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

VALID_STATUSES = {"pass", "fail", "partial", "not_implemented"}


@dataclass(frozen=True)
class Milestone:
    id: str
    category: str
    description: str


MILESTONES: tuple[Milestone, ...] = (
    Milestone("alignment_reporting", "tooling", "Report contains top-level evaluation summary and backend rollups."),
    Milestone("proposed_config_output", "tooling", "Writes evidence-derived proposed conventions config."),
    Milestone("partial_classification", "classification", "Partial alignments are surfaced distinctly from hard failures."),
    Milestone("strict_mode_gating", "gating", "Strict mode exits non-zero when required milestones are not achieved."),
)


def milestone_statuses_from_report(report: dict) -> dict[str, str]:
    statuses: dict[str, str] = {}

    evaluation = report.get("evaluation") or {}
    backends = report.get("backends") or {}

    if evaluation and "status" in evaluation and backends:
        statuses["alignment_reporting"] = "pass"
    elif evaluation or backends:
        statuses["alignment_reporting"] = "partial"
    else:
        statuses["alignment_reporting"] = "fail"

    has_rules = any(section.get("proposed_rules") for section in backends.values())
    statuses["proposed_config_output"] = "pass" if has_rules else "not_implemented"

    partial_count = int(evaluation.get("partial", 0) or 0)
    fail_count = int(evaluation.get("missed", 0) or 0) + int(evaluation.get("ambiguous", 0) or 0)
    if partial_count > 0:
        statuses["partial_classification"] = "pass"
    elif fail_count > 0:
        statuses["partial_classification"] = "fail"
    else:
        statuses["partial_classification"] = "not_implemented"

    strict_supported = any("evaluation" in section for section in backends.values())
    statuses["strict_mode_gating"] = "pass" if strict_supported else "not_implemented"

    return statuses


def evaluate_framework_stage(report: dict) -> dict:
    statuses = milestone_statuses_from_report(report)
    stage = {
        "milestones": [
            {
                "id": ms.id,
                "category": ms.category,
                "description": ms.description,
                "status": statuses.get(ms.id, "not_implemented"),
            }
            for ms in MILESTONES
        ]
    }
    stage["summary"] = {
        "pass": sum(1 for m in stage["milestones"] if m["status"] == "pass"),
        "fail": sum(1 for m in stage["milestones"] if m["status"] == "fail"),
        "partial": sum(1 for m in stage["milestones"] if m["status"] == "partial"),
        "not_implemented": sum(1 for m in stage["milestones"] if m["status"] == "not_implemented"),
    }
    return stage


def _strict_exit_code(stage: dict, allow_partial: bool) -> int:
    statuses = [m["status"] for m in stage["milestones"]]
    if "fail" in statuses or "not_implemented" in statuses:
        return 1
    if not allow_partial and "partial" in statuses:
        return 1
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--report", required=True, help="Path to conventions_report.json")
    p.add_argument("--output", required=True, help="Path for milestone_stage.json")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--allow-partial", action="store_true")
    a = p.parse_args()

    report = json.loads(Path(a.report).read_text())
    stage = evaluate_framework_stage(report)
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(stage, indent=2))

    if a.strict:
        raise SystemExit(_strict_exit_code(stage, a.allow_partial))


if __name__ == "__main__":
    main()
