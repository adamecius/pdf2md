from __future__ import annotations
import argparse, json
from pathlib import Path

ALLOWED_STATUSES = {"pass", "partial", "fail", "not_implemented", "manual_required"}
ALLOWED_STAGES = ["scaffold", "diagnostic", "groundtruth_aligned", "rule_learning", "normalisation_validated", "ci_gate_ready"]


def _milestones_from_report(conventions_report: dict) -> list[dict]:
    eval_status = (conventions_report.get("evaluation") or {}).get("status")
    milestones = [
        {"id": "M1_groundtruth_extraction", "status": "pass" if conventions_report.get("fixture_provenance") else "not_implemented"},
        {"id": "M2_alignment_obligations", "status": "pass" if conventions_report.get("backends") else "not_implemented"},
        {"id": "M4_evaluation_report", "status": "pass" if eval_status in {"pass", "warn", "fail"} else "fail"},
        {"id": "M5_strict_mode", "status": "manual_required"},
        {"id": "M6_rule_learning", "status": "partial" if any(b.get("proposed_rules") for b in conventions_report.get("backends", {}).values()) else "not_implemented"},
        {"id": "M8_normalisation_before_after_evaluation", "status": "not_implemented"},
    ]
    return milestones


def _stage(milestones: list[dict]) -> str:
    states = {m["id"]: m["status"] for m in milestones}
    if states.get("M8_normalisation_before_after_evaluation") == "pass" and states.get("M5_strict_mode") == "pass":
        return "ci_gate_ready"
    if states.get("M6_rule_learning") in {"pass", "partial"}:
        return "rule_learning"
    if states.get("M2_alignment_obligations") == "pass":
        return "groundtruth_aligned"
    return "diagnostic"


def evaluate(root: Path, batch: str, output: Path, emit_markdown: bool = False) -> dict:
    report_path = root / batch / "diagnostics" / "conventions" / "conventions_report.json"
    conventions_report = json.loads(report_path.read_text()) if report_path.exists() else {}
    milestones = _milestones_from_report(conventions_report)
    summary = {k: sum(1 for m in milestones if m["status"] == k) for k in ALLOWED_STATUSES}
    payload = {"batch": batch, "stage": _stage(milestones), "allowed_stages": ALLOWED_STAGES, "milestones": milestones, "summary": summary}
    output.mkdir(parents=True, exist_ok=True)
    (output / "milestone_report.json").write_text(json.dumps(payload, indent=2))
    if emit_markdown:
        lines = [f"# Milestone Report ({batch})", "", f"Stage: `{payload['stage']}`", ""]
        lines += [f"- {m['id']}: `{m['status']}`" for m in milestones]
        (output / "milestone_report.md").write_text("\n".join(lines))
    return payload


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--batch", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--emit-markdown", action="store_true")
    p.add_argument("--strict", action="store_true")
    a = p.parse_args()
    payload = evaluate(Path(a.root), a.batch, Path(a.output), emit_markdown=a.emit_markdown)
    if a.strict and payload["stage"] != "ci_gate_ready":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
