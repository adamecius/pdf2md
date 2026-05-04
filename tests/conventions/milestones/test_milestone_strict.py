import json
import pytest

from pdf2md.conventions.milestones import main


def test_strict_mode_fails_for_not_implemented(tmp_path, monkeypatch):
    report = tmp_path / "conventions_report.json"
    report.write_text(json.dumps({"evaluation": {}, "backends": {}}))
    out = tmp_path / "stage.json"

    monkeypatch.setattr("sys.argv", ["x", "--report", str(report), "--output", str(out), "--strict"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
