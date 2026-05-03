#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # type: ignore
except Exception:
    fitz = None

DOC_IDS=["simple_title_paragraph","section_subsection_references","figure_caption_reference","two_figures_cross_references","table_caption_reference","table_with_multiline_cells","equation_label_reference","multiple_equations_references","inline_and_display_math","itemize_enumerate_nested","footnotes_basic","footnote_inside_list","repeated_footnote_like_markers","mixed_captions_near_text","unnumbered_sections","multipage_sections","multipage_references","complex_multi_reference_network","bibliography_like_references","all_features_small"]
FILLER="Deterministic filler sentence for page flow and stable layout. "

def build_tex(doc_id:str,title:str)->str:
    body={
      "simple_title_paragraph":"\\section{Intro}\\label{sec:intro} Plain paragraph for intro.",
      "section_subsection_references":"\\section{Alpha}\\label{sec:alpha}\\subsection{Beta}\\label{sub:beta} See Section~\\ref{sec:alpha} and Subsection~\\ref{sub:beta}.",
      "figure_caption_reference":"\\section{Visual}\\begin{figure}[h]\\centering\\fbox{A}\\caption{Boxed figure}\\label{fig:box}\\end{figure} See Figure~\\ref{fig:box}.",
      "two_figures_cross_references":"\\section{Visuals}\\begin{figure}[h]\\centering\\fbox{A}\\caption{First}\\label{fig:one}\\end{figure}\\begin{figure}[h]\\centering\\fbox{B}\\caption{Second}\\label{fig:two}\\end{figure} refs \\ref{fig:one}, \\ref{fig:two}.",
      "table_caption_reference":"\\section{Data}\\begin{table}[h]\\centering\\caption{Sample table}\\label{tab:s}\\begin{tabular}{|l|l|}\\hline A&B\\\\\\hline\\end{tabular}\\end{table} See \\ref{tab:s}.",
      "table_with_multiline_cells":"\\section{Data}\\begin{table}[h]\\centering\\caption{Long cells}\\label{tab:ml}\\begin{tabular}{|p{5cm}|p{5cm}|}\\hline long text line one and two & another deterministic long cell\\\\\\hline\\end{tabular}\\end{table}",
      "equation_label_reference":"\\section{Math}\\begin{equation}E=mc^2\\label{eq:one}\\end{equation} Eq.~\\ref{eq:one}.",
      "multiple_equations_references":"\\section{Math}\\begin{equation}a=b\\label{eq:a}\\end{equation}\\begin{equation}c=d\\label{eq:c}\\end{equation} refs \\ref{eq:a} \\ref{eq:c} \\ref{eq:a}.",
      "inline_and_display_math":"\\section{Math} Inline $x+y$ and $$x^2+y^2=z^2$$ display.",
      "itemize_enumerate_nested":"\\section{Lists}\\begin{itemize}\\item one\\item two\\begin{enumerate}\\item sub\\end{enumerate}\\end{itemize}",
      "footnotes_basic":"\\section{Notes} Footnote here\\footnote{First note.} and more\\footnote{Second note}.",
      "footnote_inside_list":"\\section{Notes}\\begin{itemize}\\item one\\footnote{List note}\\end{itemize}",
      "repeated_footnote_like_markers":"\\section{Notes} markers [*] [*] and one real\\footnote{Only real note}.",
      "mixed_captions_near_text":"\\section{Mixed}\\begin{figure}[h]\\centering\\fbox{A}\\caption{Visual}\\label{fig:mixed}\\end{figure} text \\begin{table}[h]\\centering\\caption{Tab cap}\\label{tab:mixed}\\begin{tabular}{|l|l|}\\hline X&Y\\\\\\hline\\end{tabular}\\end{table}",
      "unnumbered_sections":"\\section*{Starred} text \\subsection*{Starred sub} text \\section{Numbered}\\label{sec:num} ref \\ref{sec:num}.",
      "multipage_sections":"\\section{Long} "+(FILLER*250),
      "multipage_references":"\\section{P1}\\label{sec:p1}"+(FILLER*120)+"\\newpage\\section{P2} ref \\ref{sec:p1} "+(FILLER*100),
      "complex_multi_reference_network":"\\section{Complex}\\label{sec:complex}\\subsection{Mesh}\\label{sub:mesh}\\begin{figure}[h]\\centering\\fbox{A}\\caption{Boxed figure}\\label{fig:box}\\end{figure}\\begin{table}[h]\\centering\\caption{Sample table}\\label{tab:s}\\begin{tabular}{|l|l|}\\hline A&B\\\\\\hline\\end{tabular}\\end{table}\\begin{equation}E=mc^2\\label{eq:one}\\end{equation} refs \\ref{sec:complex} \\ref{sub:mesh} \\ref{fig:box} \\ref{tab:s} \\ref{eq:one}.",
      "bibliography_like_references":"\\section{Body} cite [1], [2].\\section{References}\\label{sec:refs} [1] Alpha. [2] Beta.",
      "all_features_small":"\\section{All}\\label{sec:all}\\subsection{AllSub}\\label{sub:all}\\begin{figure}[h]\\centering\\fbox{A}\\caption{Boxed figure}\\label{fig:all}\\end{figure}\\begin{table}[h]\\centering\\caption{Sample table}\\label{tab:all}\\begin{tabular}{|l|l|}\\hline A&B\\\\\\hline\\end{tabular}\\end{table}\\begin{equation}E=mc^2\\label{eq:all}\\end{equation}\\begin{itemize}\\item one\\begin{enumerate}\\item sub\\end{enumerate}\\end{itemize}\\footnote{All note} ref \\ref{sec:all} \\ref{sub:all} \\ref{fig:all} \\ref{tab:all} \\ref{eq:all}.\\section{References} [1] Item."
    }[doc_id]
    return f"""\\documentclass{{article}}
\\usepackage{{amsmath}}
\\begin{{document}}
\\title{{{title}}}\\maketitle
{body}
\\end{{document}}
"""

def detect_engine():
    for e in ("latexmk","pdflatex","tectonic"):
        if shutil.which(e): return e
    return None

def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()

def parse_nodes(doc_id, title, tex):
    nodes=[]; labels={}; refs=[]; i=0
    def add(t,txt,label=None,kind="text"):
        nonlocal i
        nid=f"gt:block:{doc_id}:{i}"; i+=1
        nodes.append({"id":nid,"type":t,"text":txt,"label":label,"expected_docling_kind":kind});
        if label: labels[label]=nid
        return nid
    add("title",title,kind="title")
    for s in re.findall(r"\\section\*?\{([^}]+)\}",tex): add("section",s,kind="section_header")
    for s in re.findall(r"\\subsection\*?\{([^}]+)\}",tex): add("subsection",s,kind="section_header")
    for c in re.findall(r"\\caption\{([^}]+)\}",tex): add("caption",c,kind="caption")
    for _ in re.findall(r"\\begin\{figure\}",tex): add("figure","figure",kind="picture")
    for _ in re.findall(r"\\begin\{table\}",tex): add("table","table",kind="table")
    for e in re.findall(r"\\begin\{equation\}(.*?)\\end\{equation\}",tex,re.S): add("equation",e.strip(),kind="formula")
    for f in re.findall(r"\\footnote\{([^}]+)\}",tex): add("footnote",f,kind="footnote")
    for _ in re.findall(r"\\begin\{itemize\}",tex): add("list","itemize",kind="list")
    for _ in re.findall(r"\\begin\{enumerate\}",tex): add("list","enumerate",kind="list")
    for it in re.findall(r"\\item\s+([^\\]+)",tex): add("list_item",it.strip(),kind="list_item")
    for lbl in re.findall(r"\\label\{([^}]+)\}",tex):
        target=next((n["id"] for n in nodes[::-1] if n["type"]!="reference"),None)
        if target: labels[lbl]=target
    for j,lbl in enumerate(re.findall(r"\\ref\{([^}]+)\}",tex)):
        sid=add("reference",f"ref:{lbl}")
        refs.append({"id":f"gt:ref:{doc_id}:{j}","source_node_id":sid,"target_label":lbl,"target_node_id":labels.get(lbl),"expected_resolved":labels.get(lbl) is not None})
    if "\\section{References}" in tex: add("bibliography_like","References",kind="text")
    return nodes,labels,refs

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--batch",default="batch_001"); ap.add_argument("--output-root",default=".current/latex_docling_groundtruth"); ap.add_argument("--count",type=int,default=20); ap.add_argument("--compile",action="store_true"); a=ap.parse_args()
    root=Path(a.output_root)/a.batch; root.mkdir(parents=True,exist_ok=True); eng=detect_engine()
    for did in DOC_IDS[:max(a.count,20)]:
      title=did.replace('_',' ').title(); tex_src=build_tex(did,title)
      doc=root/did; inp=doc/'input'; gt=doc/'groundtruth'; inp.mkdir(parents=True,exist_ok=True); gt.mkdir(parents=True,exist_ok=True)
      tex=inp/f"{did}.tex"; pdf=inp/f"{did}.pdf"; tex.write_text(tex_src)
      rc=None; cmd=None
      if a.compile and eng:
        run=[eng,"-pdf","-interaction=nonstopmode",f"-outdir={inp}",str(tex)] if eng=="latexmk" else [eng,"-interaction=nonstopmode",f"-output-directory={inp}",str(tex)]
        p=subprocess.run(run,capture_output=True,text=True); rc=p.returncode; cmd=" ".join(run)
      nodes,labels,refs=parse_nodes(did,title,tex_src)
      feats={k:sum(1 for n in nodes if n["type"]==k[:-1] if k.endswith('s')) for k in ["sections","subsections","figures","tables","equations","footnotes"]}
      feats.update({"references":len(refs),"captions":sum(1 for n in nodes if n['type']=='caption'),"lists":sum(1 for n in nodes if n['type']=='list')})
      multipage='multipage' in did; pages_min=2 if multipage else 1
      sem={"document_id":did,"expected_title":title,"expected_sections":[n['text'] for n in nodes if n['type']=='section'],"expected_subsections":[n['text'] for n in nodes if n['type']=='subsection'],"expected_labels":sorted(labels),"expected_markdown_snippets":[title],"required_node_types":sorted(set(n['type'] for n in nodes if n['type']!='reference'))}
      docling={"document_id":did,"required_docling_kinds":sorted(set(n['expected_docling_kind'] for n in nodes)),"required_reference_sidecar_entries":[r['target_label'] for r in refs]}
      sgt={"schema_name":"pdf2md.source_groundtruth_ir","document_id":did,"title":title,"pages_expected_min":pages_min,"nodes":nodes,"labels":labels,"references":refs,"features":feats}
      page_count=None
      if pdf.exists() and fitz is not None:
        try: page_count=fitz.open(pdf).page_count
        except Exception: pass
      prov={"document_id":did,"page_count":page_count,"pages_expected_min":pages_min,"page_count_valid":(page_count is None) or (page_count>=pages_min),"latex_engine":eng,"latex_command":cmd,"compilation_return_code":rc}
      (gt/'source_groundtruth_ir.json').write_text(json.dumps(sgt,indent=2)); (gt/'expected_semantic_contract.json').write_text(json.dumps(sem,indent=2)); (gt/'expected_docling_contract.json').write_text(json.dumps(docling,indent=2)); (gt/'provenance_manifest.json').write_text(json.dumps(prov,indent=2))

if __name__=='__main__': main()
