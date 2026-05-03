#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fitz  # type: ignore
except Exception:
    fitz = None

@dataclass
class Node:
    type:str; text:str; expected_docling_kind:str="text"; label:str|None=None; ref_target:str|None=None; parent_id:str|None=None; source_latex_hint:str=""

@dataclass
class DocSpec:
    document_id:str; title:str; body:str; nodes:list[Node]=field(default_factory=list); refs:list[tuple[int,str,str]]=field(default_factory=list); features:dict[str,Any]=field(default_factory=dict); snippets:list[str]=field(default_factory=list)

FILLER="Deterministic filler sentence for page flow and stable layout. "

def mk_specs()->list[DocSpec]:
    ids=["simple_title_paragraph","section_subsection_references","figure_caption_reference","two_figures_cross_references","table_caption_reference","table_with_multiline_cells","equation_label_reference","multiple_equations_references","inline_and_display_math","itemize_enumerate_nested","footnotes_basic","footnote_inside_list","repeated_footnote_like_markers","mixed_captions_near_text","unnumbered_sections","multipage_sections","multipage_references","complex_multi_reference_network","bibliography_like_references","all_features_small"]
    specs=[]
    for i,did in enumerate(ids,1):
        title=did.replace('_',' ').title()
        body="\\section{Overview}\\label{sec:overview}\nParagraph A. Paragraph B."
        if did=="section_subsection_references": body="\\section{Alpha}\\label{sec:alpha}\\subsection{Beta}\\label{sub:beta} See Section~\\ref{sec:alpha} and Subsection~\\ref{sub:beta}."
        if "figure" in did or did in {"complex_multi_reference_network","all_features_small"}: body+="\n\\begin{figure}[h]\\centering\\fbox{\\rule{0pt}{2cm}\\rule{3cm}{0pt}}\\caption{Boxed figure}\\label{fig:box}\\end{figure} See Figure~\\ref{fig:box}."
        if "two_figures" in did: body+="\\begin{figure}[h]\\centering\\fbox{B}\\caption{Second}\\label{fig:two}\\end{figure} refs \\ref{fig:box},\\ref{fig:two}."
        if "table" in did or did in {"complex_multi_reference_network","all_features_small"}: body+="\\begin{table}[h]\\centering\\caption{Sample table}\\label{tab:s}\\begin{tabular}{|l|l|}\\hline A&B\\\\\\hline\\end{tabular}\\end{table}"
        if did=="table_with_multiline_cells": body+="\\begin{table}[h]\\centering\\caption{Long cells}\\label{tab:ml}\\begin{tabular}{|p{5cm}|p{5cm}|}\\hline long text line one and two & another deterministic long cell\\\\\\hline\\end{tabular}\\end{table}"
        if "equation" in did or did in {"complex_multi_reference_network","all_features_small"}: body+="\\begin{equation}E=mc^2\\label{eq:one}\\end{equation} Eq.~\\ref{eq:one}."
        if did=="multiple_equations_references": body+="\\begin{equation}a=b\\label{eq:a}\\end{equation}\\begin{equation}c=d\\label{eq:c}\\end{equation} refs \\ref{eq:a} \\ref{eq:c} \\ref{eq:a}."
        if did=="inline_and_display_math": body+="Inline $x+y$ and $$x^2+y^2=z^2$$ display."
        if "list" in did or did in {"all_features_small"}: body+="\\begin{itemize}\\item one\\item two\\begin{enumerate}\\item sub\\end{enumerate}\\end{itemize}"
        if "footnote" in did or did in {"all_features_small"}: body+="Footnote here\\footnote{First note.} and more\\footnote{Second note}."
        if did=="unnumbered_sections": body="\\section*{Starred} text \\subsection*{Starred sub} text \\section{Numbered}\\label{sec:num} ref \\ref{sec:num}."
        if did=="multipage_sections": body="\\section{Long} "+(FILLER*250)
        if did=="multipage_references": body="\\section{P1}\\label{sec:p1}"+(FILLER*120)+"\\newpage\\section{P2} ref \\ref{sec:p1} "+(FILLER*100)
        if did=="bibliography_like_references": body="Text cites [1], [2].\\section{References} [1] Alpha. [2] Beta."
        tex=f"""\\documentclass{{article}}
\\usepackage{{amsmath}}
\\begin{{document}}
\\title{{{title}}}\\maketitle
{body}
\\end{{document}}
"""
        specs.append(DocSpec(did,title,tex,snippets=[title,"Overview"]))
    return specs

def detect_engine():
    for e in ("latexmk","pdflatex","tectonic"):
        if shutil.which(e): return e
    return None

def sha(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--batch",default="batch_001"); ap.add_argument("--output-root",default=".current/latex_docling_groundtruth"); ap.add_argument("--count",type=int,default=20); ap.add_argument("--compile",action="store_true"); ap.add_argument("--verbose",action="store_true"); a=ap.parse_args()
    specs=mk_specs()[:max(20,a.count)]
    root=Path(a.output_root)/a.batch; root.mkdir(parents=True,exist_ok=True)
    eng=detect_engine();
    for spec in specs:
        doc=root/spec.document_id; inp=doc/"input"; gt=doc/"groundtruth"; inp.mkdir(parents=True,exist_ok=True); gt.mkdir(parents=True,exist_ok=True)
        tex=inp/f"{spec.document_id}.tex"; pdf=inp/f"{spec.document_id}.pdf"; tex.write_text(spec.body,encoding="utf-8")
        rc=None;cmd=None
        if a.compile and eng:
            if eng=="latexmk": runs=[[eng,"-pdf","-interaction=nonstopmode",f"-outdir={inp}",str(tex.resolve())]]
            elif eng=="pdflatex": runs=[[eng,"-interaction=nonstopmode",f"-output-directory={inp}",str(tex.resolve())]]*2
            else: runs=[[eng,"-o",str(inp),str(tex.resolve())]]
            for r in runs:
                p=subprocess.run(r,capture_output=True,text=True); rc=p.returncode; cmd=" ".join(r)
                if p.returncode!=0: break
        labels={}; nodes=[]; refs=[]
        # coarse node extraction from patterns
        order=0
        for t,kind,hint in [(spec.title,"title","\\title"),("Overview","section_header","\\section")]:
            nid=f"gt:block:{spec.document_id}:{order}"; nodes.append({"id":nid,"type":"title" if order==0 else "section","text":t,"label":None,"ref_target":None,"order":order,"parent_id":None,"children":[],"expected_docling_kind":kind,"source_latex_hint":hint}); order+=1
        for m in ["fig:box","fig:two","tab:s","tab:ml","eq:one","eq:a","eq:c","sec:alpha","sub:beta","sec:num","sec:p1"]:
            if m in spec.body:
                nid=f"gt:block:{spec.document_id}:{order}"; nodes.append({"id":nid,"type":"reference","text":m,"label":m,"ref_target":None,"order":order,"parent_id":None,"children":[],"expected_docling_kind":"text","source_latex_hint":"\\label"});labels[m]=nid;order+=1
        for lbl in labels:
            refs.append({"id":f"gt:ref:{spec.document_id}:{lbl}","source_node_id":nodes[1]["id"],"target_label":lbl,"target_node_id":labels[lbl],"reference_text":f"\\ref{{{lbl}}}","expected_resolved":True})
        features={k:0 for k in ["sections","subsections","figures","tables","equations","footnotes","itemize_lists","enumerate_lists","nested_lists","references","captions"]}; features["multipage"]="multipage" in spec.document_id
        for k,s in [("sections","\\section{"),("subsections","\\subsection{"),("figures","\\begin{figure}"),("tables","\\begin{table}"),("equations","\\begin{equation}"),("footnotes","\\footnote"),("itemize_lists","\\begin{itemize}"),("enumerate_lists","\\begin{enumerate}"),("captions","\\caption")]: features[k]=spec.body.count(s)
        features["nested_lists"]=1 if "\\begin{itemize}" in spec.body and "\\begin{enumerate}" in spec.body else 0; features["references"]=len(refs)
        sgt={"schema_name":"pdf2md.source_groundtruth_ir","schema_version":"0.1.0","document_id":spec.document_id,"source_type":"latex","source_tex":str(tex),"expected_pdf":str(pdf),"title":spec.title,"pages_expected_min":1,"nodes":nodes,"labels":labels,"references":refs,"features":features}
        sem={"document_id":spec.document_id,"source_tex":str(tex),"expected_title":spec.title,"expected_sections":["Overview"],"expected_labels":sorted(labels),"expected_references":[r["target_label"] for r in refs],"expected_figures":{"count_min":features["figures"]},"expected_tables":{"count_min":features["tables"]},"expected_equations":{"count_min":features["equations"]},"expected_footnotes":{"count_min":features["footnotes"]},"expected_list_types":{"require_itemize":features["itemize_lists"]>0,"require_enumerate":features["enumerate_lists"]>0},"expected_captions":{"count_min":features["captions"]},"expected_markdown_snippets":[spec.title],"allowed_warnings":["unresolved_reference"],"tolerance_policy":{"allow_missing_pdf_when_no_latex":True}}
        docling={"document_id":spec.document_id,"required_docling_kinds":["text","section_header"],"body_order_constraints":["title_before_body"],"required_presence":{"picture":features["figures"]>0,"table":features["tables"]>0,"formula":features["equations"]>0,"caption":features["captions"]>0,"list":features["itemize_lists"]>0 or features["enumerate_lists"]>0,"footnote":features["footnotes"]>0},"required_reference_sidecar_entries":[r["target_label"] for r in refs],"expected_markdown_snippets":[spec.title],"allowed_degradation_warnings":["missing_caption_link"],"tolerance_policy":{"non_exact_json":True}}
        page_count=None
        if pdf.exists() and fitz is not None:
            try: page_count=fitz.open(pdf).page_count
            except Exception: page_count=None
        prov={"schema_name":"pdf2md.latex_docling_groundtruth_manifest","schema_version":"0.1.0","document_id":spec.document_id,"batch":a.batch,"generated_at":datetime.now(timezone.utc).isoformat(),"source_tex":{"path":str(tex),"sha256":sha(tex)},"pdf":{"path":str(pdf),"sha256":sha(pdf)} if pdf.exists() else None,"latex_engine":eng,"latex_command":cmd,"compilation_return_code":rc,"page_count":page_count,"generated_files":[str(tex),str(gt/'source_groundtruth_ir.json'),str(gt/'expected_semantic_contract.json'),str(gt/'expected_docling_contract.json')],"feature_counts":features}
        (gt/"source_groundtruth_ir.json").write_text(json.dumps(sgt,indent=2),encoding="utf-8")
        (gt/"expected_semantic_contract.json").write_text(json.dumps(sem,indent=2),encoding="utf-8")
        (gt/"expected_docling_contract.json").write_text(json.dumps(docling,indent=2),encoding="utf-8")
        (gt/"provenance_manifest.json").write_text(json.dumps(prov,indent=2),encoding="utf-8")
        if a.verbose: print(f"generated {spec.document_id}")
if __name__=='__main__': main()
