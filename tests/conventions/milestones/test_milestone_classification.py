from pdf2md.conventions.milestones import evaluate_framework_stage


def test_milestone_status_uses_allowed_values_only():
    report = {
        "evaluation": {"status": "pass", "partial": 1, "missed": 0, "ambiguous": 0},
        "backends": {"paddleocr": {"evaluation": {}, "proposed_rules": [{"id": "x"}]}}
    }
    stage = evaluate_framework_stage(report)
    statuses = {m["status"] for m in stage["milestones"]}
    assert statuses <= {"pass", "fail", "partial", "not_implemented"}


def test_partial_classification_is_not_hidden():
    report = {
        "evaluation": {"status": "warn", "partial": 2, "missed": 0, "ambiguous": 0},
        "backends": {"mineru": {"evaluation": {}, "proposed_rules": []}},
    }
    stage = evaluate_framework_stage(report)
    ms = {m["id"]: m["status"] for m in stage["milestones"]}
    assert ms["partial_classification"] == "pass"
