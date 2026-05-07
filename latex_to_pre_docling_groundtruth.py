#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # type: ignore
except Exception:
    fitz = None

TOK = re.compile(r"\\begin\{(figure|table|tabular|equation|itemize|enumerate)\}|\\end\{(figure|table|tabular|equation|itemize|enumerate)\}|\\(title|section|subsection|label|caption|ref|footnote)\*?\{|\\item\s+|\$\$|\$|\\newpage", re.S)

@dataclass
class Ctx: env:str; block_id:str|None=None

class Parser:
    def __init__(self,did,tex):
        self.did=did; self.tex=tex; self.i=0; self.n=0
        self.blocks=[]; self.labels={}; self.refs=[]; self.relations=[]; self.warnings=[]
        self.stack=[]; self.pending_label=None; self.anchor=None; self.title=did
    def bid(self): self.n+=1; return f"gt:{self.did}:b{self.n:04d}"
    def add(self,tp,text,parent=None,extra=None):
        b={"id":self.bid(),"type":tp,"text":text.strip(),"parent_id":parent,"children":[],"labels":[],"source_latex_hint":tp}
        if extra: b.update(extra)
        self.blocks.append(b)
        if parent:
            p=next((x for x in self.blocks if x['id']==parent),None)
            if p: p['children'].append(b['id'])
        if tp in ('paragraph','list_item','section','subsection'): self.anchor=b['id']
        return b
    def parse_group(self,start):
        d=1; j=start; out=[]
        while j < len(self.tex) and d>0:
            c=self.tex[j]
            if c=='{': d+=1
            elif c=='}':
                d-=1
                if d==0: break
            out.append(c); j+=1
        return ''.join(out), j+1
    def flush_text(self,txt):
        t=' '.join(txt.split())
        if not t:
            return
        if any(c.env=='equation' for c in self.stack):
            return
        self.add('paragraph',t,parent=self.current_parent())
    def current_parent(self):
        return next((c.block_id for c in reversed(self.stack) if c.env in ('item','list','figure','table')),None)
    def bind_label(self,lbl):
        t=next((c.block_id for c in reversed(self.stack) if c.block_id),None)
        if not t:
            for b in reversed(self.blocks):
                if b['type'] in ('section','subsection','figure','table','equation','caption'): t=b['id']; break
        if t:
            b=next(x for x in self.blocks if x['id']==t)
            if lbl not in b['labels']: b['labels'].append(lbl)
            self.labels[lbl]=t
        else:
            self.pending_label=lbl
    def parse(self):
        while self.i < len(self.tex):
            m=TOK.search(self.tex,self.i)
            if not m: self.flush_text(self.tex[self.i:]); break
            self.flush_text(self.tex[self.i:m.start()]); self.i=m.end(); s=m.group(0)
            if s.startswith('\\begin'):
                env=m.group(1)
                if env in ('itemize','enumerate'):
                    l=self.add('list',env,parent=self.current_parent(),extra={'list_kind':env}); self.stack.append(Ctx('list',l['id']))
                elif env in ('figure','table','equation'):
                    b=self.add(env,'',parent=None)
                    self.stack.append(Ctx(env,b['id']))
                else: self.stack.append(Ctx(env))
                continue
            if s.startswith('\\end'):
                env=m.group(2)
                if env=='equation':
                    # capture equation body from last equation start to this end
                    eq=next((x for x in reversed(self.blocks) if x['type']=='equation' and not x['text']),None)
                    if eq:
                        pass
                if self.stack: self.stack.pop();
                continue
            if s in ('$$','$'):
                term=s; j=self.tex.find(term,self.i)
                if j!=-1:
                    math=self.tex[self.i:j].strip(); self.i=j+len(term)
                    self.add('display_math' if term=='$$' else 'inline_math',math,parent=self.current_parent())
                continue
            if s.startswith('\\item'):
                while self.stack and self.stack[-1].env=='item': self.stack.pop()
                end=TOK.search(self.tex,self.i); j=end.start() if end else len(self.tex)
                it=self.add('list_item',' '.join(self.tex[self.i:j].split()),parent=next((c.block_id for c in reversed(self.stack) if c.env=='list'),None))
                self.stack.append(Ctx('item',it['id'])); self.i=j; continue
            if s.startswith('\\newpage'):
                self.add('page_break','newpage'); continue
            cmd=re.match(r"\\(\w+)\*?\{",s).group(1)
            grp,self.i=self.parse_group(self.i)
            if cmd=='title': self.title=grp.strip(); self.add('title',grp)
            elif cmd=='section':
                b=self.add('section',grp)
                if grp.strip().lower()=='references': self.add('bibliography_like','References',parent=b['id'])
                if self.pending_label: self.bind_label(self.pending_label); self.pending_label=None
            elif cmd=='subsection': self.add('subsection',grp)
            elif cmd=='label': self.bind_label(grp)
            elif cmd=='caption':
                p=next((c.block_id for c in reversed(self.stack) if c.env in ('figure','table')),None)
                c=self.add('caption',grp,parent=p)
                if p: self.relations.append({'type':'caption_of','caption_text':grp.strip(),'source_block_id':c['id'],'target_label':next((l for l,v in self.labels.items() if v==p),None)})
            elif cmd=='ref':
                r=self.add('reference',f"ref:{grp}",parent=self.anchor)
                self.refs.append({'id':f'gt:ref:{self.did}:{len(self.refs)}','source_node_id':r['id'],'source_block_id':r['id'],'target_label':grp,'relation_type':'reference_to','reference_text':f'\\ref{{{grp}}}'})
            elif cmd=='footnote':
                f=self.add('footnote',grp)
                if self.anchor: self.relations.append({'type':'footnote_of','source_block_id':f['id'],'target_block_id':self.anchor,'footnote_text':grp.strip()})
        # equation text extraction
        for m in re.finditer(r"\\begin\{equation\}(.*?)\\end\{equation\}",self.tex,re.S):
            t=re.sub(r"\\label\{[^}]+\}",'',m.group(1)).strip()
            b=next((x for x in self.blocks if x['type']=='equation' and not x['text']),None)
            if b: b['text']=t
        for r in self.refs:
            r['target_block_id']=self.labels.get(r['target_label']); r['target_node_id']=r['target_block_id']; r['resolved']=r['target_block_id'] is not None; r['expected_resolved']=r['resolved']
            self.relations.append({'type':'reference_to','source_block_id':r['source_block_id'],'target_label':r['target_label'],'resolved':r['resolved']})

def extract_tables(tex):
    out=[]
    for m in re.finditer(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}",tex,re.S):
        rows=[]; body=m.group(1).replace('\\hline','')
        for ri,row in enumerate([r.strip() for r in body.split('\\\\') if r.strip()]):
            cells=[]
            for ci,c in enumerate(row.split('&')): cells.append({'row':ri,'col':ci,'text':' '.join(c.split())})
            rows.append({'row':ri,'cells':cells})
        out.append(rows)
    return out

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None

def process(doc_dir):
    did=doc_dir.name; tex=doc_dir/'input'/f'{did}.tex'; pdf=doc_dir/'input'/f'{did}.pdf'; gt=doc_dir/'groundtruth'; gt.mkdir(exist_ok=True)
    src=tex.read_text(); p=Parser(did,src); p.parse(); counts=Counter(b['type'] for b in p.blocks)
    tables=extract_tables(src)
    tblocks=[b for b in p.blocks if b['type']=='table']
    for i,t in enumerate(tables):
        if i<len(tblocks): tblocks[i]['table_rows']=t
    pages=[]
    if pdf.exists() and fitz is not None:
        try: pages=[{'page_count':fitz.open(pdf).page_count}]
        except Exception: pages=[]
    sem={"schema_name":"pdf2md.semantic_document_groundtruth","schema_version":"1.0.0","document_id":did,"title":p.title,"pages":pages,"body":p.blocks,"labels":p.labels,"references":p.refs,"relations":p.relations,"warnings":p.warnings,"provenance":{"source_tex":str(tex),"source_pdf":str(pdf) if pdf.exists() else None}}
    sgt={"schema_name":"pdf2md.source_groundtruth_ir","schema_version":"1.0.0","document_id":did,"source_type":"latex","source_tex":str(tex),"expected_pdf":str(pdf),"title":p.title,"nodes":p.blocks,"labels":p.labels,"references":p.refs,"relations":p.relations,"features":dict(counts),"pages_expected_min":(2 if 'multipage' in did else 1)}
    econ={"document_id":did,"expected_title":p.title,"expected_sections":[b['text'] for b in p.blocks if b['type']=='section'],"expected_subsections":[b['text'] for b in p.blocks if b['type']=='subsection'],"expected_ordered_block_constraints":[b['type'] for b in p.blocks],"expected_labels":list(p.labels.keys()),"expected_references":p.refs,"expected_captions":[r for r in p.relations if r['type']=='caption_of'],"expected_nested_list_structure":True,"expected_table_cells":[tb.get('table_rows',[]) for tb in tblocks],"expected_markdown_snippets":[p.title],"allowed_warnings":[],"tolerance_policy":{"whitespace":True}}
    dcon={"document_id":did,"required_docling_kinds":["title","section_header","text","picture","table","formula","caption","list","footnote"],"body_order_constraints":econ['expected_ordered_block_constraints'],"required_caption_relations":econ['expected_captions'],"required_reference_sidecar_entries":[r['target_label'] for r in p.refs],"expected_markdown_snippets":[p.title],"allowed_degradation_warnings":[],"tolerance_policy":econ['tolerance_policy']}
    (gt/'semantic_document_groundtruth.json').write_text(json.dumps(sem,indent=2))
    (gt/'source_groundtruth_ir.json').write_text(json.dumps(sgt,indent=2))
    (gt/'expected_semantic_contract.json').write_text(json.dumps(econ,indent=2))
    (gt/'expected_docling_contract.json').write_text(json.dumps(dcon,indent=2))
    (gt/'latex_groundtruth_report.json').write_text(json.dumps({'document_id':did,'counts':dict(counts)},indent=2))
    (gt/'provenance_manifest.json').write_text(json.dumps({'schema_name':'pdf2md.latex_docling_groundtruth_manifest','schema_version':'1.0.0','document_id':did,'batch':doc_dir.parent.name,'generated_at':datetime.now(timezone.utc).isoformat(),'source_tex':{'path':str(tex),'sha256':sha(tex)},'source_pdf':({'path':str(pdf),'sha256':sha(pdf)} if pdf.exists() else None),'generated_files':[str(gt/'source_groundtruth_ir.json'),str(gt/'semantic_document_groundtruth.json'),str(gt/'expected_semantic_contract.json'),str(gt/'expected_docling_contract.json'),str(gt/'latex_groundtruth_report.json'),str(gt/'provenance_manifest.json')],'feature_counts':dict(counts)},indent=2))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default='.current/latex_docling_groundtruth'); ap.add_argument('--batch',default='batch_001'); ap.add_argument('--verbose',action='store_true'); a=ap.parse_args()
    for d in sorted((Path(a.root)/a.batch).iterdir()):
        if d.is_dir():
            process(d)
            if a.verbose: print('processed',d.name)

if __name__=='__main__': main()
