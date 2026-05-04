from __future__ import annotations
import json
from pathlib import Path


def write_report(output_dir: Path, report: dict, emit_markdown: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "conventions_report.json").write_text(json.dumps(report, indent=2))
    if emit_markdown:
        lines = ["# OCR Convention Examples", ""]
        for backend, payload in report.get("backends", {}).items():
            lines.append(f"## {backend}")
            for ex in payload.get("examples", []):
                lines.append(f"- `{ex.get('block_id','')}`: {ex.get('before','')} -> {ex.get('after','')}")
            lines.append("")
        (output_dir / "examples.md").write_text("\n".join(lines))
