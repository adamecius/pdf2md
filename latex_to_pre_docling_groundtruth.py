#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, hashlib
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone

CMD_RE = re.compile(r"\\(title|section|subsection|label|caption|ref|footnote)\*?\{")
ITEM_RE = re.compile(r"\\item\s+")
BEGIN_RE = re.compile(r"\\begin\{(figure|table|tabular|equation|itemize|enumerate)\}")
END_RE = re.compile(r"\\end\{(figure|table|tabular|equation|itemize|enumerate)\}")
NEWPAGE_RE = re.compile(r"\\newpage")

@dataclass
class Ctx:
    env:str
    block_id:str|None=None

class Builder:
    def __init__(self,did:str,tex:str):
        self.did=did; self.tex=tex; self.i=0; self.n=0
        self.blocks=[]; self.labels={}; self.references=[]; self.relations=[]; self.warnings=[]
        self.stack=[]; self.pending_label=None; self.pending_footnote_anchor=None
        self.root_title=None
    def bid(self,p='b'): self.n+=1; return f"gt:{self.did}:{p}{self.n:04d}"
    def add(self,tp,text,parent_id=None,source_hint=None,labels=None,extra=None):
        b={"id":self.bid(),"type":tp,"text":text.strip(),"parent_id":parent_id,"children":[],"labels":labels or [],"references":[],"relations":[],"source_latex_hint":source_hint or ""}
        if extra: b.update(extra)
        self.blocks.append(b)
        if parent_id:
            p=next((x for x in self.blocks if x['id']==parent_id),None)
            if p: p['children'].append(b['id'])
        return b
    def parse_group(self,start):
        j=start; depth=1; out=[]
        while j < len(self.tex) and depth>0:
            c=self.tex[j]
            if c=='{': depth+=1
            elif c=='}':
                depth-=1
                if depth==0: break
            out.append(c); j+=1
        return ''.join(out), j+1
    def parse(self):
        while self.i < len(self.tex):
            m=min([x for x in [BEGIN_RE.search(self.tex,self.i),END_RE.search(self.tex,self.i),CMD_RE.search(self.tex,self.i),ITEM_RE.search(self.tex,self.i),NEWPAGE_RE.search(self.tex,self.i)] if x], key=lambda z:z.start(), default=None)
            if not m:
                self.parse_text(self.tex[self.i:]); break
            if m.start()>self.i: self.parse_text(self.tex[self.i:m.start()])
            s=m.group(0)
            if s.startswith('\\begin'):
                env=m.group(1); self.i=m.end(); self.on_begin(env); continue
            if s.startswith('\\end'):
                env=m.group(1); self.i=m.end(); self.on_end(env); continue
            if s.startswith('\\item'):
                self.i=m.end()
                end=min([x.start() for x in [BEGIN_RE.search(self.tex,self.i),END_RE.search(self.tex,self.i),CMD_RE.search(self.tex,self.i),ITEM_RE.search(self.tex,self.i),NEWPAGE_RE.search(self.tex,self.i)] if x] or [len(self.tex)])
                self.on_cmd('item', self.tex[self.i:end].strip(), False)
                self.i=end
                continue
            if s.startswith('\\newpage'):
                self.i=m.end(); self.add('page_break','newpage',source_hint='\\newpage'); continue
            cmd=re.match(r"\\(\w+)\*?\{",s).group(1)
            grp,ni=self.parse_group(m.end())
            self.i=ni
            self.on_cmd(cmd,grp,m.group(0).startswith('\\'+cmd+'*'))
        self.resolve_refs()
    def parse_text(self,txt):
        clean=re.sub(r"\s+"," ",txt).strip()
        if not clean: return
        parent=None
        for c in reversed(self.stack):
            if c.env in ('item','list','figure','table','equation'): parent=c.block_id; break
        b=self.add('paragraph',clean,parent_id=parent,source_hint='text')
        self.pending_footnote_anchor=b['id']
    def on_begin(self,env):
        if env in ('itemize','enumerate'):
            parent=next((c.block_id for c in reversed(self.stack) if c.env in ('item','list')),None)
            l=self.add('list',env,parent_id=parent,source_hint=f'begin:{env}',extra={'list_kind':env})
            self.stack.append(Ctx('list',l['id']))
        elif env in ('figure','table','equation'):
            b=self.add(env,env,source_hint=f'begin:{env}',labels=([self.pending_label] if self.pending_label else []))
            if self.pending_label: self.labels[self.pending_label]=b['id']; self.pending_label=None
            self.stack.append(Ctx(env,b['id']))
        elif env=='tabular':
            self.stack.append(Ctx('tabular'))
        else: self.stack.append(Ctx(env))
    def on_end(self,env):
        if self.stack: self.stack.pop()
    def on_cmd(self,cmd,val,is_star):
        if cmd=='title': self.root_title=val.strip(); self.add('title',val,source_hint='\\title')
        elif cmd=='section':
            b=self.add('section',val,source_hint='\\section*' if is_star else '\\section')
            if self.pending_label: b['labels'].append(self.pending_label); self.labels[self.pending_label]=b['id']; self.pending_label=None
        elif cmd=='subsection':
            b=self.add('subsection',val,source_hint='\\subsection*' if is_star else '\\subsection')
            if self.pending_label: b['labels'].append(self.pending_label); self.labels[self.pending_label]=b['id']; self.pending_label=None
        elif cmd=='label':
            target=next((c for c in reversed(self.stack) if c.block_id),None)
            if target:
                tb=next(x for x in self.blocks if x['id']==target.block_id); tb['labels'].append(val); self.labels[val]=tb['id']
            else: self.pending_label=val
        elif cmd=='caption':
            parent=next((c.block_id for c in reversed(self.stack) if c.env in ('figure','table')),None)
            cap=self.add('caption',val,parent_id=parent,source_hint='\\caption')
            if parent: self.relations.append({'type':'caption_of','source_id':cap['id'],'target_id':parent})
        elif cmd=='ref':
            src=self.add('reference',f"ref:{val}",parent_id=self.pending_footnote_anchor,source_hint='\\ref')
            self.references.append({'source_block_id':src['id'],'target_label':val,'relation_type':'reference_to'})
        elif cmd=='footnote':
            ft=self.add('footnote',val,parent_id=None,source_hint='\\footnote')
            if self.pending_footnote_anchor: self.relations.append({'type':'footnote_of','source_id':ft['id'],'target_id':self.pending_footnote_anchor})
        elif cmd=='item':
            while self.stack and self.stack[-1].env=='item':
                self.stack.pop()
            pl=next((c.block_id for c in reversed(self.stack) if c.env=='list'),None)
            it=self.add('list_item',val,parent_id=pl,source_hint='\\item')
            self.stack.append(Ctx('item',it['id']))
        # table rows/cells from tabular raw text are captured as paragraphs; augment later
    def resolve_refs(self):
        for r in self.references:
            tid=self.labels.get(r['target_label'])
            r['target_block_id']=tid; r['resolved']=tid is not None
            if tid: self.relations.append({'type':'reference_to','source_id':r['source_block_id'],'target_id':tid,'target_label':r['target_label'],'resolved':True})


def extract_table_structures(doc):
    tex=doc['provenance']['tex_content']
    tables=[]
    for tm in re.finditer(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}",tex,re.S):
        body=tm.group(1).replace('\\hline','')
        rows=[]
        for ri,row in enumerate([r.strip() for r in body.split('\\\\') if r.strip()]):
            cells=[]
            for ci,c in enumerate(row.split('&')):
                cells.append({'row':ri,'col':ci,'text':re.sub(r'\s+',' ',c).strip()})
            rows.append({'row':ri,'cells':cells})
        tables.append(rows)
    return tables

def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None

def process_doc(doc_dir:Path, verbose=False):
    did=doc_dir.name; tex=doc_dir/'input'/f'{did}.tex'; pdf=doc_dir/'input'/f'{did}.pdf'; gt=doc_dir/'groundtruth'; gt.mkdir(exist_ok=True)
    t=tex.read_text()
    b=Builder(did,t); b.parse()
    sem={"schema_name":"pdf2md.semantic_document_groundtruth","schema_version":"1.0.0","document_id":did,"title":b.root_title or did,"pages":[],"body":b.blocks,"labels":b.labels,"references":b.references,"relations":b.relations,"warnings":b.warnings,"provenance":{"source_tex":str(tex),"source_pdf":str(pdf) if pdf.exists() else None,"tex_content":t}}
    tbls=extract_table_structures(sem)
    for i,rows in enumerate(tbls):
        tbs=[x for x in sem['body'] if x['type']=='table']
        if i < len(tbs): tbs[i]['table_rows']=rows
    src={"schema_name":"pdf2md.source_groundtruth_ir","schema_version":"1.0.0","document_id":did,"nodes":b.blocks,"labels":b.labels,"references":b.references,"relations":b.relations}
    contract={"expected_title":sem['title'],"expected_sections":[x['text'] for x in b.blocks if x['type']=='section'],"expected_subsections":[x['text'] for x in b.blocks if x['type']=='subsection'],"expected_ordered_block_constraints":[x['type'] for x in b.blocks],"expected_labels":b.labels,"expected_references":b.references,"expected_captions":[r for r in b.relations if r['type']=='caption_of'],"expected_tables":[x.get('table_rows',[]) for x in sem['body'] if x['type']=='table'],"expected_nested_lists":True,"expected_markdown_snippets":[sem['title']],"allowed_warnings":[],"tolerance_policy":{"text_normalization":"whitespace"}}
    docling={"required_docling_object_kinds":["title","section_header","text","picture","table","formula","caption","list","footnote"],"body_order_constraints":contract['expected_ordered_block_constraints'],"required_caption_relations":contract['expected_captions'],"required_reference_sidecar_entries":[r['target_label'] for r in b.references],"expected_markdown_snippets":[sem['title']],"allowed_degradation_warnings":[],"tolerance_policy":contract['tolerance_policy']}
    report={"document_id":did,"counts":{k:sum(1 for bl in b.blocks if bl['type']==k) for k in ['section','subsection','figure','table','equation','list','list_item','footnote','reference']}}
    prov={"document_id":did,"generated_at":datetime.now(timezone.utc).isoformat(),"source_tex":{"path":str(tex),"sha256":sha(tex)},"source_pdf":{"path":str(pdf),"sha256":sha(pdf)} if pdf.exists() else None}
    sem['provenance'].pop('tex_content')
    (gt/'semantic_document_groundtruth.json').write_text(json.dumps(sem,indent=2))
    (gt/'source_groundtruth_ir.json').write_text(json.dumps(src,indent=2))
    (gt/'expected_semantic_contract.json').write_text(json.dumps(contract,indent=2))
    (gt/'expected_docling_contract.json').write_text(json.dumps(docling,indent=2))
    (gt/'latex_groundtruth_report.json').write_text(json.dumps(report,indent=2))
    (gt/'provenance_manifest.json').write_text(json.dumps(prov,indent=2))
    if verbose: print('processed',did)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default='.current/latex_docling_groundtruth'); ap.add_argument('--batch',default='batch_001'); ap.add_argument('--verbose',action='store_true'); a=ap.parse_args()
    root=Path(a.root)/a.batch
    for d in sorted([x for x in root.iterdir() if x.is_dir()]): process_doc(d,a.verbose)

if __name__=='__main__': main()
