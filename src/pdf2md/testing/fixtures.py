from __future__ import annotations
import json
from pathlib import Path

BATCH_002_FIXTURES = {
    "det_title_paragraph": r"""\documentclass[letterpaper]{article}
\begin{document}
\title{Detectable Title Paragraph}\author{}\date{}\maketitle
\section{Intro}
A short paragraph.
\end{document}
""",
    "det_figure_reference": r"""\documentclass[letterpaper]{article}
\begin{document}
\title{Detectable Figure}\author{}\date{}\maketitle
\section{Visual}
\begin{figure}[h]
\centering\fbox{FIG}
\caption{Boxed figure}\label{fig:one}
\end{figure}
See Figure~\ref{fig:one}.
\end{document}
""",
    "det_table_reference": r"""\documentclass[letterpaper]{article}
\begin{document}
\title{Detectable Table}\author{}\date{}\maketitle
\section{Data}
\begin{table}[h]
\centering
\caption{Sample table}\label{tab:one}
\begin{tabular}{cc}A & B\\1 & 2\end{tabular}
\end{table}
See Table~\ref{tab:one}.
\end{document}
""",
    "det_equation_reference": r"""\documentclass[letterpaper]{article}
\begin{document}
\title{Detectable Equation}\author{}\date{}\maketitle
\section{Math}
\begin{equation}\label{eq:one}
E = mc^2
\end{equation}
Eq.~(\ref{eq:one}) is famous.
\end{document}
""",
    "det_footnote": r"""\documentclass[letterpaper]{article}
\begin{document}
\title{Detectable Footnote}\author{}\date{}\maketitle
\section{Notes}
Footnote here\footnote{First note.}
\end{document}
""",
    "det_section_reference": r"""\documentclass[letterpaper]{article}
\begin{document}
\title{Detectable Section Ref}\author{}\date{}\maketitle
\section{Alpha}\label{sec:alpha}
See Section~\ref{sec:alpha}.
\end{document}
""",
    "det_bibliography": r"""\documentclass[letterpaper]{article}
\begin{document}
\title{Detectable Bibliography}\author{}\date{}\maketitle
\section{Refs}
As shown in [1].
\end{document}
""",
    "det_all_features": r"""\documentclass[letterpaper]{article}
\begin{document}
\title{Detectable All Features}\author{}\date{}\maketitle
\section{All}\label{sec:all}
\begin{figure}[h]\centering\fbox{FIG}\caption{Boxed figure}\label{fig:one}\end{figure}
\begin{table}[h]\centering\caption{Sample table}\label{tab:one}\begin{tabular}{cc}A & B\\1 & 2\end{tabular}\end{table}
\begin{equation}\label{eq:one}E = mc^2\end{equation}
See Figure~\ref{fig:one}, Table~\ref{tab:one}, Eq.~(\ref{eq:one}), and Section~\ref{sec:all}.\footnote{First note.}
As shown in [1].
\end{document}
""",
}


def _contracts(doc_id: str):
    base = {"document_id": doc_id, "expected_title": doc_id.replace('det_', '').replace('_', ' ').title(), "expected_sections": [], "expected_subsections": [], "expected_ordered_block_constraints": [], "expected_labels": [], "expected_references": [], "expected_captions": [], "expected_nested_list_structure": True, "expected_table_cells": [], "expected_markdown_snippets": [], "allowed_warnings": [], "tolerance_policy": {"whitespace": True}}
    det = {"document_id": doc_id, "expected_title": base['expected_title'], "expected_sections": [], "expected_anchors": [], "expected_resolved_references": [], "expected_block_types": ["title", "heading", "paragraph"], "expected_footnote_count": 0, "expected_bibliography_refs": []}
    if doc_id == 'det_figure_reference':
        det.update({"expected_sections":["Visual"],"expected_anchors":[{"anchor_type":"figure","numeric_label":"1"}],"expected_resolved_references":[{"reference_type":"figure","label":"1","should_resolve":True}],"expected_block_types":["title","heading","caption","figure","paragraph"]})
    if doc_id == 'det_table_reference':
        det.update({"expected_sections":["Data"],"expected_anchors":[{"anchor_type":"table","numeric_label":"1"}],"expected_resolved_references":[{"reference_type":"table","label":"1","should_resolve":True}],"expected_block_types":["title","heading","caption","table","paragraph"]})
    if doc_id == 'det_equation_reference':
        det.update({"expected_sections":["Math"],"expected_anchors":[{"anchor_type":"equation","numeric_label":"1"}],"expected_resolved_references":[{"reference_type":"equation","label":"1","should_resolve":True}],"expected_block_types":["title","heading","formula","paragraph"]})
    if doc_id == 'det_footnote':
        det.update({"expected_sections":["Notes"],"expected_footnote_count":1})
    if doc_id == 'det_section_reference':
        det.update({"expected_sections":["Alpha"],"expected_resolved_references":[{"reference_type":"section","label":"1","should_resolve":False}]})
    if doc_id == 'det_bibliography':
        det.update({"expected_sections":["Refs"],"expected_bibliography_refs":["1"]})
    if doc_id == 'det_all_features':
        det.update({"expected_sections":["All"],"expected_anchors":[{"anchor_type":"figure","numeric_label":"1"},{"anchor_type":"table","numeric_label":"1"},{"anchor_type":"equation","numeric_label":"1"}],"expected_resolved_references":[{"reference_type":"figure","label":"1","should_resolve":True},{"reference_type":"table","label":"1","should_resolve":True},{"reference_type":"equation","label":"1","should_resolve":True},{"reference_type":"section","label":"1","should_resolve":False}],"expected_footnote_count":1,"expected_bibliography_refs":["1"],"expected_block_types":["title","heading","caption","figure","table","formula","paragraph"]})
    return base, det


def generate_batch_002(output_root: Path) -> None:
    root = Path(output_root) / 'batch_002'
    for doc_id, tex in BATCH_002_FIXTURES.items():
        d = root / doc_id
        (d / 'input').mkdir(parents=True, exist_ok=True)
        (d / 'groundtruth').mkdir(parents=True, exist_ok=True)
        (d / 'input' / f'{doc_id}.tex').write_text(tex, encoding='utf-8')
        sg = {"schema_name":"pdf2md.source_groundtruth_ir","schema_version":"0.1.0","document_id":doc_id,"source_type":"latex","source_tex":str(d/'input'/f'{doc_id}.tex'),"expected_pdf":str(d/'input'/f'{doc_id}.pdf'),"title":doc_id.replace('det_','').replace('_',' ').title(),"nodes":[],"labels":{},"references":[],"relations":[],"features":[],"pages_expected_min":1}
        sem, det = _contracts(doc_id)
        (d / 'groundtruth' / 'source_groundtruth_ir.json').write_text(json.dumps(sg, indent=2), encoding='utf-8')
        (d / 'groundtruth' / 'expected_semantic_contract.json').write_text(json.dumps(sem, indent=2), encoding='utf-8')
        (d / 'groundtruth' / 'expected_detectable_contract.json').write_text(json.dumps(det, indent=2), encoding='utf-8')
