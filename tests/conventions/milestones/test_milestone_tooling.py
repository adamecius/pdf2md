import json
from pathlib import Path

from pdf2md.conventions.milestones import main


def test_machine_readable_stage_report_written(tmp_path, monkeypatch):
    report_path = tmp_path / "conventions_report.json"
    output_path = tmp_path / "stage.json"
    report_path.write_text(json.dumps({"evaluation": {}, "backends": {}}))

    monkeypatch.setattr(
        "sys.argv",
        ["x", "--report", str(report_path), "--output", str(output_path)],
    )
    main()

    payload = json.loads(output_path.read_text())
    assert "milestones" in payload
    assert "summary" in payload
