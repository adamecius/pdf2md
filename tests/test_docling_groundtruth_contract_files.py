import json
import re
from pathlib import Path

CONTRACTS = [
    Path("tests/docling_groundtruth/contracts/batch_001/linked_sections_figures/expected_semantic_contract.json"),
    Path("tests/docling_groundtruth/contracts/batch_001/linked_sections_figures/expected_docling_contract.json"),
    Path("tests/docling_groundtruth/contracts/batch_001/lists_footnotes_tables/expected_semantic_contract.json"),
    Path("tests/docling_groundtruth/contracts/batch_001/lists_footnotes_tables/expected_docling_contract.json"),
]


def _labels_from_tex(tex_path: Path) -> set[str]:
    text = tex_path.read_text(encoding="utf-8")
    return set(re.findall(r"\\label\{([^}]+)\}", text))


def test_contract_files_exist_and_valid_json() -> None:
    for contract in CONTRACTS:
        assert contract.exists(), f"missing contract: {contract}"
        data = json.loads(contract.read_text(encoding="utf-8"))
        for key in [
            "document_id", "source_tex", "expected_title", "expected_sections", "expected_labels",
            "expected_references", "expected_figures", "expected_tables", "expected_equations",
            "expected_footnotes", "expected_list_types", "expected_captions", "expected_markdown_snippets",
            "allowed_warnings", "tolerance_policy",
        ]:
            assert key in data, f"missing key '{key}' in {contract}"


def test_contract_labels_exist_in_tex_sources() -> None:
    for contract in CONTRACTS:
        data = json.loads(contract.read_text(encoding="utf-8"))
        tex_path = Path(data["source_tex"])
        labels = _labels_from_tex(tex_path)
        for expected_label in data["expected_labels"]:
            assert expected_label in labels, f"{expected_label} not found in {tex_path}"


def test_contract_feature_count_minima() -> None:
    for contract in CONTRACTS:
        data = json.loads(contract.read_text(encoding="utf-8"))
        assert data["expected_figures"]["count_min"] >= 0
        assert data["expected_tables"]["count_min"] >= 0
        assert data["expected_equations"]["count_min"] >= 0
        assert data["expected_footnotes"]["count_min"] >= 0
