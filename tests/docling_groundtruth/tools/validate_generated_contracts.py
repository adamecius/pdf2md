from __future__ import annotations

import argparse
import json
from pathlib import Path


def _check(path: Path) -> dict:
    return {"path": str(path), "exists": path.exists()}


def validate_doc(generated_root: Path, contract_path: Path, enabled_backends: list[str]) -> dict:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    doc_id = contract["document_id"]
    doc_root = generated_root / "batch_001" / doc_id

    checks = {
        "document_root": _check(doc_root),
        "input_pdf": _check(doc_root / "input" / f"{doc_id}.pdf"),
        "consensus_report": _check(doc_root / "consensus" / "consensus_report.json"),
        "semantic_links": _check(doc_root / "consensus" / "semantic_links.json"),
        "semantic_document": _check(doc_root / "consensus" / "semantic_document.json"),
    }
    checks["docling_preview"] = _check(doc_root / "docling" / "docling_preview.md")

    backend_checks = {}
    for backend in enabled_backends:
        backend_checks[backend] = _check(doc_root / "backend_ir" / backend)
    checks["backend_ir"] = backend_checks

    ok = all(v["exists"] for k, v in checks.items() if isinstance(v, dict) and "exists" in v)
    ok = ok and all(v["exists"] for v in backend_checks.values())

    return {"document_id": doc_id, "contract": str(contract_path), "checks": checks, "pass": ok}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--generated-root", default=".current/docling_groundtruth")
    p.add_argument("--contracts-root", default="tests/docling_groundtruth/contracts/batch_001")
    p.add_argument("--backends", default="mineru,paddleocr,deepseek")
    p.add_argument("--report-out", default=None)
    args = p.parse_args()

    enabled_backends = [x.strip() for x in args.backends.split(",") if x.strip()]
    contracts_root = Path(args.contracts_root)
    reports = []
    for contract_path in sorted(contracts_root.glob("*/expected_semantic_contract.json")):
        reports.append(validate_doc(Path(args.generated_root), contract_path, enabled_backends))

    summary = {"documents": reports, "pass": all(r["pass"] for r in reports)}
    if args.report_out:
        out = Path(args.report_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
