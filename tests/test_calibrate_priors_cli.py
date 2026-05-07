import json
import subprocess
import sys
from pathlib import Path

import pytest

from pdf2md.calibration.io import CalibrationDocumentInput, discover_calibration_inputs, load_calibration_document
from pdf2md.models.priors import CalibrationPriorDocument, CalibrationStatus, lookup_confidence


class TestCalibrationIO:
    def test_discover_calibration_inputs_finds_fixture_document(self):
        root = Path("tests/data/calibration_fixtures/mixed_predictions")
        inputs = discover_calibration_inputs(root=root, backends=["mineru", "paddleocr"])
        assert len(inputs) == 1
        assert set(inputs[0].prediction_roots) == {"mineru", "paddleocr"}

    def test_load_calibration_document_reads_truth_entities_and_pages(self):
        root = Path("tests/data/calibration_fixtures/mixed_predictions")
        result = load_calibration_document(item=discover_calibration_inputs(root=root, backends=["mineru"])[0])
        assert result.truth is not None
        assert len(result.truth.entities) >= 7
        assert result.pages_by_backend["mineru"]
        assert result.entities_by_backend["mineru"].entities

    def test_load_calibration_document_lenient_missing_backend_adds_warning(self):
        item = CalibrationDocumentInput("missing", Path("tests/data/calibration_fixtures/mixed_predictions/truth.json"), {"missing": Path("tests/data/calibration_fixtures/mixed_predictions/missing")})
        result = load_calibration_document(item=item)
        assert "prediction_missing:missing" in result.warnings

    def test_load_calibration_document_strict_invalid_truth_raises(self, tmp_path):
        bad_truth = tmp_path / "truth.json"
        bad_truth.write_text("{bad json")
        with pytest.raises(Exception):
            load_calibration_document(item=CalibrationDocumentInput("bad", bad_truth, {}), strict=True)


class TestCalibratePriorsCLI:
    def test_cli_help_exits_zero(self):
        completed = subprocess.run([sys.executable, "tools/calibrate_priors.py", "--help"], check=False, text=True, capture_output=True)
        assert completed.returncode == 0
        assert "--root" in completed.stdout

    def test_cli_writes_prior_and_report_for_minimal_fixture(self, tmp_path):
        completed = subprocess.run([sys.executable, "tools/calibrate_priors.py", "--root", "tests/data/calibration_fixtures/minimal_predictions", "--out-dir", str(tmp_path), "--backends", "mineru", "--min-samples", "1"], check=False, text=True, capture_output=True)
        assert completed.returncode == 0, completed.stderr
        prior = CalibrationPriorDocument.model_validate_json((tmp_path / "priors/mineru.json").read_text())
        assert prior.backend == "mineru"
        assert prior.block_kind_priors[0].key == "heading"
        assert json.loads((tmp_path / "reports/calibration_report.json").read_text())["document_count"] == 1

    def test_cli_writes_one_prior_per_backend_for_mixed_fixture(self, tmp_path):
        completed = subprocess.run([sys.executable, "tools/calibrate_priors.py", "--root", "tests/data/calibration_fixtures/mixed_predictions", "--out-dir", str(tmp_path), "--backends", "mineru,paddleocr", "--min-samples", "2"], check=False, text=True, capture_output=True)
        assert completed.returncode == 0, completed.stderr
        assert (tmp_path / "priors/mineru.json").exists()
        assert (tmp_path / "priors/paddleocr.json").exists()

    def test_cli_empty_predictions_writes_no_samples_prior(self, tmp_path):
        completed = subprocess.run([sys.executable, "tools/calibrate_priors.py", "--root", "tests/data/calibration_fixtures/empty_predictions", "--out-dir", str(tmp_path), "--backends", "deepseek", "--min-samples", "2"], check=False, text=True, capture_output=True)
        assert completed.returncode == 0, completed.stderr
        prior = CalibrationPriorDocument.model_validate_json((tmp_path / "priors/deepseek.json").read_text())
        assert prior.calibration_key_priors == []
        assert lookup_confidence(prior, "calibration_key", "deepseek:missing") == prior.default_confidence

    def test_cli_strict_mode_fails_on_invalid_input(self, tmp_path):
        bad = tmp_path / "bad"
        (bad / "mineru").mkdir(parents=True)
        (bad / "truth.json").write_text("{bad json")
        (bad / "mineru/entities.json").write_text("{bad json")
        completed = subprocess.run([sys.executable, "tools/calibrate_priors.py", "--root", str(bad), "--out-dir", str(tmp_path / "out"), "--backends", "mineru", "--strict"], check=False, text=True, capture_output=True)
        assert completed.returncode == 1

    def test_written_prior_validates_as_calibration_prior_document(self, tmp_path):
        subprocess.run([sys.executable, "tools/calibrate_priors.py", "--root", "tests/data/calibration_fixtures/mixed_predictions", "--out-dir", str(tmp_path), "--backends", "mineru"], check=True)
        prior = CalibrationPriorDocument.model_validate_json((tmp_path / "priors/mineru.json").read_text())
        assert all(metric.status in set(CalibrationStatus) for metric in prior.entity_type_priors)

    def test_written_report_contains_prior_file_paths(self, tmp_path):
        subprocess.run([sys.executable, "tools/calibrate_priors.py", "--root", "tests/data/calibration_fixtures/mixed_predictions", "--out-dir", str(tmp_path), "--backends", "mineru,paddleocr"], check=True)
        report = json.loads((tmp_path / "reports/calibration_report.json").read_text())
        assert report["prior_files"] == {"mineru": "priors/mineru.json", "paddleocr": "priors/paddleocr.json"}
