#!/usr/bin/env python
"""Export LinkedStructure to Docling-compatible JSON, RAG chunks, and markdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf2md.export.docling import DoclingExportSettings
from pdf2md.export.io import build_export_run, load_export_inputs, write_export_outputs
from pdf2md.export.markdown import MarkdownExportSettings
from pdf2md.export.rag import RagExportSettings
from pdf2md.export.reporting import INSPECTION_STATUSES, build_export_report


class _ExitCodeOneParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _parser() -> argparse.ArgumentParser:
    parser = _ExitCodeOneParser(description="Export pdf2md LinkedStructure to Docling JSON and derived artefacts")
    parser.add_argument("--linked-structure", required=True, type=Path)
    parser.add_argument("--consensus-ir", type=Path)
    parser.add_argument("--source-pdf")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-rag", action="store_true")
    parser.add_argument("--no-markdown", action="store_true")
    parser.add_argument("--include-unresolved", action="store_true")
    parser.add_argument("--max-chars", type=int, default=1800)
    parser.add_argument(
        "--inspection-status",
        default="diagnostic_only",
        choices=list(INSPECTION_STATUSES),
        help=(
            "Human-supplied Plan 16 readiness verdict comparing exported "
            "Docling JSON against ConsensusIR and ground truth. Defaults to "
            "diagnostic_only."
        ),
    )
    parser.add_argument(
        "--ground-truth",
        default=None,
        type=Path,
        help=(
            "Optional ground-truth .docling.json reference recorded in the "
            "report. No automated structural comparison is performed in Plan 15."
        ),
    )
    parser.add_argument(
        "--inspection-note",
        action="append",
        default=[],
        help="Optional inspection note (repeatable).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        loaded = load_export_inputs(linked_structure_path=args.linked_structure, consensus_ir_path=args.consensus_ir, strict=args.strict)
        result = build_export_run(
            linked=loaded.linked,
            consensus=loaded.consensus,
            source_linked_structure=str(args.linked_structure),
            source_consensus_ir=str(args.consensus_ir) if args.consensus_ir else None,
            source_pdf=args.source_pdf,
            docling_settings=DoclingExportSettings(include_unresolved=args.include_unresolved or True),
            rag_settings=RagExportSettings(max_chars=args.max_chars),
            markdown_settings=MarkdownExportSettings(),
            strict=args.strict,
            include_rag=not args.no_rag,
            include_markdown=not args.no_markdown,
        )
        all_warnings = result.warnings + loaded.warnings
        manifest = (
            result.manifest.model_copy(update={"warnings": result.manifest.warnings + loaded.warnings})
            if loaded.warnings
            else result.manifest
        )
        rebuilt_report = build_export_report(
            document_id=loaded.linked.document_id,
            docling=result.docling,
            rag_chunks=result.rag_chunks,
            markdown=result.markdown,
            warnings=all_warnings,
            inspection_status=args.inspection_status,
            inspection_notes=args.inspection_note,
            source_consensus_ir=str(args.consensus_ir) if args.consensus_ir else None,
            source_pdf=args.source_pdf,
            ground_truth_ref=str(args.ground_truth) if args.ground_truth else None,
        )
        result = type(result)(
            docling=result.docling,
            rag_chunks=result.rag_chunks,
            markdown=result.markdown,
            manifest=manifest,
            report=rebuilt_report,
            warnings=all_warnings,
            write_rag=result.write_rag,
            write_markdown=result.write_markdown,
        )
        write_export_outputs(result=result, out_dir=args.out_dir)
        if args.verbose:
            for warning in result.warnings:
                print(f"warning:{warning}", file=sys.stderr)
            plan16 = rebuilt_report["plan16_readiness"]
            print(f"docling_text_count: {plan16['docling_text_count']}")
            print(f"rag_chunk_count: {plan16['rag_chunk_count']}")
            print(f"markdown_char_count: {plan16['markdown_char_count']}")
            print(f"inspection_status: {rebuilt_report['inspection_status']}")
            print(f"end_to_end_orchestration_handed_off_by: {plan16['end_to_end_orchestration_handed_off_by']}")
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
