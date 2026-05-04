#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # type: ignore
except Exception:
    fitz = None

DOC_IDS=["simple_title_paragraph","section_subsection_references","figure_caption_reference","two_figures_cross_references","table_caption_reference","table_with_multiline_cells","equation_label_reference","multiple_equations_references","inline_and_display_math","itemize_enumerate_nested","footnotes_basic","footnote_inside_list","repeated_footnote_like_markers","mixed_captions_near_text","unnumbered_sections","multipage_sections","multipage_references","complex_multi_reference_network","bibliography_like_references","all_features_small","multipage_all_features_references_footnotes"]
FILLER="Deterministic filler sentence for page flow and stable layout. "

def build_tex(doc_id:str,title:str)->str:
    # unchanged fixture intent; source-driven IR is derived from these definitions.
    body_map={
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
      ,"multipage_all_features_references_footnotes":"Opening paragraph before refs with marker [*].\\footnote{Paragraph note one.}\\section{Deep Section}\\label{sec:deep} normal paragraph before cross references.\\subsection{Deep Subsection}\\label{sub:deep} Inline math $a+b$ and display $$a^2+b^2=c^2$$. caption-like text: Figure caption: not a real caption.\\begin{figure}[h]\\centering\\fbox{A}\\caption{Deep figure caption}\\label{fig:deep}\\end{figure} Reference section \\ref{sec:deep}, subsection \\ref{sub:deep}, figure \\ref{fig:deep}. "+(FILLER*120)+"\\newpage Continue paragraph after page break.\\begin{table}[h]\\centering\\caption{Deep table caption}\\label{tab:deep}\\begin{tabular}{|l|l|}\\hline X&Y\\\\\\hline\\end{tabular}\\end{table} Equation text \\begin{equation}x=y\\label{eq:deep}\\end{equation} repeated refs \\ref{eq:deep} and again \\ref{eq:deep}.\\begin{itemize}\\item outer one\\footnote{List note two.}\\item outer two\\begin{enumerate}\\item inner enum\\end{enumerate}\\end{itemize} repeated markers [*] [*] near real notes. refs to table \\ref{tab:deep} and section \\ref{sec:deep}. Closing paragraph after cross-references.\\section{References} [1] Alpha source. [2] Beta source."
    }
    body=body_map[doc_id]
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

def sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()

def parse_nodes(doc_id:str,title:str,tex:str):
    nodes=[]; labels={}; refs=[]; idx=0
    def add(tp,text,kind="text",parent_id=None,source_hint="",ref_target=None,label=None):
        nonlocal idx
        nid=f"gt:block:{doc_id}:{idx}"; idx+=1
        nodes.append({"id":nid,"type":tp,"text":text,"label":label,"ref_target":ref_target,"order":idx-1,"parent_id":parent_id,"children":[],"expected_docling_kind":kind,"source_latex_hint":source_hint})
        if parent_id:
            for n in nodes:
                if n["id"]==parent_id: n["children"].append(nid)
        if label: labels[label]=nid
        return nid

    add("title",title,kind="title",source_hint="\\title")
    # headings with immediate labels
    for m in re.finditer(r"\\section(\*?)\{([^}]+)\}(?:\\label\{([^}]+)\})?",tex):
        add("section",m.group(2),kind="section_header",source_hint="\\section",label=m.group(3))
    for m in re.finditer(r"\\subsection(\*?)\{([^}]+)\}(?:\\label\{([^}]+)\})?",tex):
        add("subsection",m.group(2),kind="section_header",source_hint="\\subsection",label=m.group(3))

    for fm in re.finditer(r"\\begin\{figure\}(.*?)\\end\{figure\}",tex,re.S):
        block=fm.group(1); fig=add("figure","figure",kind="picture",source_hint="figure")
        cm=re.search(r"\\caption\{([^}]+)\}",block)
        if cm: add("caption",cm.group(1),kind="caption",parent_id=fig,source_hint="\\caption")
        lm=re.search(r"\\label\{([^}]+)\}",block)
        if lm: labels[lm.group(1)]=fig
    for tm in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}",tex,re.S):
        block=tm.group(1); tab=add("table","table",kind="table",source_hint="table")
        cm=re.search(r"\\caption\{([^}]+)\}",block)
        if cm: add("caption",cm.group(1),kind="caption",parent_id=tab,source_hint="\\caption")
        lm=re.search(r"\\label\{([^}]+)\}",block)
        if lm: labels[lm.group(1)]=tab
    for em in re.finditer(r"\\begin\{equation\}(.*?)\\end\{equation\}",tex,re.S):
        body=em.group(1); eq=add("equation",re.sub(r"\\label\{[^}]+\}","",body).strip(),kind="formula",source_hint="equation")
        lm=re.search(r"\\label\{([^}]+)\}",body)
        if lm: labels[lm.group(1)]=eq

    for m in re.finditer(r"\\footnote\{([^}]+)\}",tex): add("footnote",m.group(1),kind="footnote",source_hint="\\footnote")
    for m in re.finditer(r"\\begin\{(itemize|enumerate)\}(.*?)\\end\{\1\}",tex,re.S):
        lid=add("list",m.group(1),kind="list",source_hint=f"\\begin{{{m.group(1)}}}")
        for it in re.findall(r"\\item\s+([^\\]+)",m.group(2)): add("list_item",it.strip(),kind="list_item",parent_id=lid,source_hint="\\item")

    for p in re.findall(r"\.\s+([A-Z][^.]{10,}?)\.",tex): add("paragraph",p.strip()+".",kind="text",source_hint="text")
    if "\\section{References}" in tex: add("bibliography_like","References",kind="text",source_hint="References")

    for i,lbl in enumerate(re.findall(r"\\ref\{([^}]+)\}",tex)):
        rid=add("reference",f"ref:{lbl}",kind="text",ref_target=lbl,source_hint="\\ref")
        refs.append({"id":f"gt:ref:{doc_id}:{i}","source_node_id":rid,"target_label":lbl,"target_node_id":labels.get(lbl),"reference_text":f"\\ref{{{lbl}}}","expected_resolved":labels.get(lbl) is not None})
    return nodes,labels,refs

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--corpus-root',default='groundtruth/corpus/latex'); ap.add_argument("--batch",default="batch_001"); ap.add_argument("--output-root",default=".current/latex_docling_groundtruth"); ap.add_argument("--count",type=int,default=20); ap.add_argument("--compile",action="store_true"); ap.add_argument("--skip-pre-docling",action="store_true"); ap.add_argument("--verbose",action="store_true"); a=ap.parse_args()
    root=Path(a.output_root)/a.batch; root.mkdir(parents=True,exist_ok=True); eng=detect_engine()
    for did in DOC_IDS[:max(21,a.count)]:
        title=did.replace('_',' ').title(); tex_src=build_tex(did,title)
        doc=root/did; inp=doc/"input"; gt=doc/"groundtruth"; inp.mkdir(parents=True,exist_ok=True); gt.mkdir(parents=True,exist_ok=True)
        tex=inp/f"{did}.tex"; pdf=inp/f"{did}.pdf"; tex.write_text(tex_src,encoding="utf-8")
        rc=None; cmd=None
        if a.compile and eng:
            if eng=="latexmk": runs=[[eng,"-pdf","-interaction=nonstopmode",f"-outdir={inp}",str(tex.resolve())]]
            elif eng=="pdflatex": runs=[[eng,"-interaction=nonstopmode",f"-output-directory={inp}",str(tex.resolve())]]*2
            else: runs=[[eng,"-o",str(pdf),str(tex.resolve())]]
            for r in runs:
                p=subprocess.run(r,capture_output=True,text=True); rc=p.returncode; cmd=" ".join(r)
                if p.returncode!=0: break
        nodes,labels,refs=parse_nodes(did,title,tex_src)
        feature_counts={k:sum(1 for n in nodes if n['type']==k) for k in ["section","subsection","figure","table","equation","footnote","caption","list","list_item","reference","bibliography_like","paragraph"]}
        multipage='multipage' in did; pages_min=2 if multipage else 1
        sgt={"schema_name":"pdf2md.source_groundtruth_ir","schema_version":"0.1.0","document_id":did,"source_type":"latex","source_tex":str(tex),"expected_pdf":str(pdf),"title":title,"pages_expected_min":pages_min,"nodes":nodes,"labels":labels,"references":refs,"features":feature_counts}
        sem={"document_id":did,"source_tex":str(tex),"expected_title":title,"expected_sections":[n['text'] for n in nodes if n['type']=='section'],"expected_subsections":[n['text'] for n in nodes if n['type']=='subsection'],"expected_labels":sorted(labels),"expected_markdown_snippets":[title],"required_node_types":sorted(set(n['type'] for n in nodes if n['type']!='reference'))}
        docling={"document_id":did,"required_docling_kinds":sorted(set(n['expected_docling_kind'] for n in nodes)),"required_reference_sidecar_entries":[r['target_label'] for r in refs]}
        page_count=None
        if pdf.exists() and fitz is not None:
            try: page_count=fitz.open(pdf).page_count
            except Exception: page_count=None
        prov={"schema_name":"pdf2md.latex_docling_groundtruth_manifest","schema_version":"0.1.0","document_id":did,"batch":a.batch,"generated_at":datetime.now(timezone.utc).isoformat(),"source_tex":{"path":str(tex),"sha256":sha(tex)},"pdf":({"path":str(pdf),"sha256":sha(pdf)} if pdf.exists() else None),"latex_engine":eng,"latex_command":cmd,"compilation_return_code":rc,"page_count":page_count,"pages_expected_min":pages_min,"generated_files":[str(tex),str(gt/'source_groundtruth_ir.json'),str(gt/'expected_semantic_contract.json'),str(gt/'expected_docling_contract.json'),str(gt/'provenance_manifest.json')],"feature_counts":feature_counts}
        (gt/'source_groundtruth_ir.json').write_text(json.dumps(sgt,indent=2),encoding='utf-8')
        (gt/'expected_semantic_contract.json').write_text(json.dumps(sem,indent=2),encoding='utf-8')
        (gt/'expected_docling_contract.json').write_text(json.dumps(docling,indent=2),encoding='utf-8')
        (gt/'provenance_manifest.json').write_text(json.dumps(prov,indent=2),encoding='utf-8')
        if a.verbose: print(f"generated {did}")
    if not a.skip_pre_docling:
        subprocess.run(["python","latex_to_pre_docling_groundtruth.py","--root",a.output_root,"--batch",a.batch] + (["--verbose"] if a.verbose else []), check=True)

if __name__=='__main__': main()
