from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _find_labels_in_json(data: dict) -> set[str]:
    blob = json.dumps(data)
    return {lbl for lbl in [":"] if False} or set()


def validate_doc(generated_root: Path, contracts_root: Path, doc_id: str, enabled_backends: list[str]) -> dict:
    sem_contract = json.loads((contracts_root / doc_id / "expected_semantic_contract.json").read_text())
    doc_contract = json.loads((contracts_root / doc_id / "expected_docling_contract.json").read_text())

    doc_root = generated_root / "batch_001" / doc_id
    consensus = doc_root / "consensus"
    docling = doc_root / "docling"
    checks: list[dict] = []

    def req(path: Path, name: str):
        checks.append({"check": name, "path": str(path), "pass": path.exists()})

    req(doc_root, "document_root")
    req(doc_root / "input" / f"{doc_id}.pdf", "input_pdf")
    for backend in enabled_backends:
        req(doc_root / "backend_ir" / backend, f"backend_ir_{backend}")

    cr = consensus / "consensus_report.json"
    sl = consensus / "semantic_links.json"
    sd = consensus / "semantic_document.json"
    req(cr, "consensus_report")
    req(sl, "semantic_links")
    req(sd, "semantic_document")

    preview = docling / "docling_preview.md"
    report = docling / "docling_adapter_report.json"
    if preview.exists():
        req(report, "docling_adapter_report")
        report_json = _load_json(report) or {}
        allowed = set(doc_contract.get("allowed_warnings", []))
        errs = report_json.get("errors", [])
        checks.append({"check": "docling_report_errors", "pass": len(errs) == 0 or "allow_report_errors" in allowed, "errors": errs})
        md = _text(preview)
        for snippet in doc_contract.get("expected_markdown_snippets", []):
            checks.append({"check": f"markdown_snippet:{snippet}", "pass": snippet in md})

    labels_needed = set(sem_contract.get("expected_labels", []))
    refs_needed = set(sem_contract.get("expected_references", []))
    sl_json = _load_json(sl) or {}
    sd_json = _load_json(sd) or {}
    blob = json.dumps({"semantic_links": sl_json, "semantic_document": sd_json})
    for label in labels_needed:
        checks.append({"check": f"label_present:{label}", "pass": label in blob})
    for ref in refs_needed:
        checks.append({"check": f"reference_present:{ref}", "pass": ref in blob})

    passed = all(c["pass"] for c in checks)
    return {"document_id": doc_id, "checks": checks, "pass": passed}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--generated-root", default=".current/docling_groundtruth")
    p.add_argument("--contracts-root", default="tests/docling_groundtruth/contracts/batch_001")
    p.add_argument("--backends", default="mineru,paddleocr,deepseek")
    p.add_argument("--report-out", default=None)
    args = p.parse_args()

    enabled_backends = [x.strip() for x in args.backends.split(",") if x.strip()]
    contracts_root = Path(args.contracts_root)
    doc_ids = sorted(p.parent.name for p in contracts_root.glob("*/expected_semantic_contract.json"))
    docs = [validate_doc(Path(args.generated_root), contracts_root, d, enabled_backends) for d in doc_ids]

    summary = {"documents": docs, "pass": all(d["pass"] for d in docs)}
    if args.report_out:
        out = Path(args.report_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
