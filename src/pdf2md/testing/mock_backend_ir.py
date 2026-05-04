from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any
import fitz

FIG_RE = re.compile(r'\b(?:Figure|Fig\.)\s+(\d+(?:\.\d+)*)', re.I)
TAB_RE = re.compile(r'\bTable\s+(\d+(?:\.\d+)*)', re.I)
EQ_RE = re.compile(r'\b(?:Eq\.?|Equation)\s*\(?\s*(\d+(?:\.\d+)*)\s*\)?', re.I)
SEC_RE = re.compile(r'^\s*(\d+)\s+[A-Z]')
SUB_RE = re.compile(r'^\s*(\d+\.\d+)\s+[A-Z]')
FOOTNOTE_BODY_RE = re.compile(r'^\s*(\d+)\s+')


def _norm_text(t: str) -> str: return re.sub(r'\s+', ' ', (t or '').strip().lower())
def _sha(v: str) -> str: return 'sha256:' + hashlib.sha256((v or '').encode()).hexdigest()
def _bbox_norm(bb: list[float], w: float, h: float) -> list[float]:
    x0,y0,x1,y1=bb
    return [round(max(0,min(1000,x0/w*1000)),3),round(max(0,min(1000,y0/h*1000)),3),round(max(0,min(1000,x1/w*1000)),3),round(max(0,min(1000,y1/h*1000)),3)]
def _set_block_type(block: dict[str, Any], typ: str) -> None:
    block["type"] = typ
    block["semantic_role"] = typ
    block["docling_label_hint"] = typ
    block["docling"]["label_hint"] = typ
    block["comparison"]["compare_as"] = typ

def _token_set(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t}

def assign_block_type(text: str, y_normalised: float, page_drawings: int) -> tuple[str, int|None]:
    t=text.strip()
    if re.match(r'^\d+\.\d+\s+[A-Z]', t) and len(t)<100: return 'heading',2
    if re.match(r'^\d+\s+[A-Z]', t) and len(t)<100: return 'heading',1
    if re.match(r'^(?:Figure|Fig\.)\s+\d', t, re.I): return 'caption',None
    if re.match(r'^Table\s+\d', t, re.I): return 'caption',None
    if re.match(r'^\d+$', t) and y_normalised>800: return 'page_number',None
    if re.search(r'[=∑∫∏]', t) and len(t)<200: return 'formula',None
    if not t and page_drawings>0: return 'picture',None
    return 'paragraph',None

def _build_block(doc_id:str,pidx:int,order:int,text:str,bbox:list[float],typ:str,hl:int|None)->dict[str,Any]:
    nt=_norm_text(text)
    return {"block_id":f"groundtruth_{doc_id}_p{pidx:04d}_b{order:04d}","page_index":pidx,"page_number":pidx+1,"order":order,"type":typ,"subtype":None,"semantic_role":typ,"docling_label_hint":typ,"docling":{"label_hint":typ,"excluded_from_docling":False},"geometry":{"bbox":bbox,"coordinate_space":"page_normalised_1000","origin":"top_left"},"content":{"text":text,"normalised_text":nt,"markdown":text},"structure":{"heading_level":hl},"confidence":{"overall":0.99,"layout":0.99,"text":0.99},"comparison":{"compare_as":typ,"text_hash":_sha(nt),"geometry_hash":_sha(','.join(map(str,bbox)))} ,"compile_role":"candidate","source_refs":[],"flags":[]}



def iter_latex_labels(gt: dict) -> list[str]:
    labels = gt.get('labels', {})
    if isinstance(labels, dict):
        return list(labels.keys())
    if isinstance(labels, list):
        out=[]
        for item in labels:
            if isinstance(item,str): out.append(item)
            elif isinstance(item,dict): out.append(item.get('label') or item.get('id') or '')
        return [x for x in out if x]
    return []

def build_label_map(fixture_dir: Path) -> dict[str, dict]:
    fixture_dir=Path(fixture_dir)
    gt=json.loads((fixture_dir/'groundtruth'/'source_groundtruth_ir.json').read_text())
    all_text=[]
    with fitz.open(fixture_dir/'input'/f'{fixture_dir.name}.pdf') as d:
        for p in d: all_text.append(p.get_text())
    txt='\n'.join(all_text)
    nums={'figure':[m.group(1) for m in FIG_RE.finditer(txt)],'table':[m.group(1) for m in TAB_RE.finditer(txt)],'equation':[m.group(1) for m in re.finditer(r'\((\d+(?:\.\d+)*)\)',txt)],'section':[m.group(1) for m in SEC_RE.finditer(txt)],'subsection':[m.group(1) for m in SUB_RE.finditer(txt)]}
    out={}
    kmap={'fig:':'figure','tab:':'table','eq:':'equation','sec:':'section','sub:':'subsection'}
    iidx={k:0 for k in nums}
    for lbl in iter_latex_labels(gt):
        lid=lbl
        kind=next((v for k,v in kmap.items() if lid.startswith(k)), 'section')
        arr=nums.get(kind,[])
        n=arr[iidx[kind]] if iidx[kind] < len(arr) else None
        iidx[kind]+=1
        detectable=kind in {'figure','table','equation'}
        if kind=='section': detectable=True
        if kind=='subsection': detectable=False
        out[lid]={"kind":kind,"numeric_label":n,"detectable":bool(n and detectable)}
    return out

def get_detectable_references(fixture_dir: Path) -> list[dict]:
    lm=build_label_map(fixture_dir)
    txt=''
    with fitz.open(Path(fixture_dir)/'input'/f'{Path(fixture_dir).name}.pdf') as d:
        for p in d: txt += '\n'+p.get_text()
    refs=[]
    pats=[('figure',FIG_RE),('table',TAB_RE),('equation',EQ_RE),('section',re.compile(r'\b(?:Section|Chap\.?|Chapter)\s+(\d+(?:\.\d+)*)',re.I)),('bibliography',re.compile(r'\[(\d+(?:\s*[-,]\s*\d+)*)\]'))]
    for kind,pat in pats:
        for m in pat.finditer(txt): refs.append({'kind':kind,'label':m.group(1),'text':m.group(0)})
    nums={(v['kind'],v['numeric_label']) for v in lm.values() if v['detectable']}
    return [r for r in refs if (r['kind'],r['label']) in nums]

def generate_mock_backend_ir(fixture_dir: Path, out_dir: Path, backend_name: str='mineru'):
    fixture_dir,out_dir=Path(fixture_dir),Path(out_dir)
    gt=json.loads((fixture_dir/'groundtruth'/'source_groundtruth_ir.json').read_text())
    nodes=gt.get('nodes',[])
    has_figure=any(n.get('type')=='figure' for n in nodes)
    pages=out_dir/'pages'; pages.mkdir(parents=True,exist_ok=True)
    pdf=fixture_dir/'input'/f'{fixture_dir.name}.pdf'
    refs=[]
    with fitz.open(pdf) as d:
      for pidx,page in enumerate(d):
        w,h=page.rect.width,page.rect.height
        drawings=[dr for dr in (page.get_drawings() or []) if dr.get('rect')]
        blocks=[]; order=0; title_done=False
        text_blocks=[]
        for b in page.get_text('dict').get('blocks',[]):
          if b.get('type')!=0: continue
          t='\n'.join(''.join(sp.get('text','') for sp in ln.get('spans',[])) for ln in b.get('lines',[])).strip()
          if not t: continue
          bb=_bbox_norm(b['bbox'],w,h); y=bb[1]
          if pidx==0 and not title_done and t and not re.match(r'^\w+\s+\d{1,2},\s+\d{4}$',t) and not re.match(r'^\d+(?:\.\d+)?\s+[A-Z]',t):
            typ,hl='title',None; title_done=True
          else:
            typ,hl=assign_block_type(t,y,len(drawings))
          if has_figure and len(t)<=2 and any(abs(bb[1]-_bbox_norm([dr['rect'].x0,dr['rect'].y0,dr['rect'].x1,dr['rect'].y1],w,h)[1])<80 for dr in drawings):
            continue
          text_blocks.append(_build_block(fixture_dir.name,pidx,order,t,bb,typ,hl)); order+=1
        blocks.extend(text_blocks)
        gt_nodes=[n for n in nodes if n.get("type") in {"figure","table"} and n.get("page")==pidx+1]
        for n in gt_nodes:
          target_type='picture' if n.get("type")=='figure' else 'table'
          ntext=n.get("text") or ""
          ntoks=_token_set(ntext)
          best_idx=None
          best_score=-1.0
          for i,bk in enumerate(text_blocks):
            if bk["type"]!="paragraph":
              continue
            btoks=_token_set(bk["content"]["text"])
            if ntoks and btoks:
              overlap=len(ntoks & btoks)
              score=(2*overlap)/(len(ntoks)+len(btoks)) if (len(ntoks)+len(btoks)) else 0.0
            else:
              score=0.0
            if score>best_score:
              best_score=score; best_idx=i
          if best_idx is None:
            continue
          if best_score<=0:
            ny=(n.get("bbox") or [0,0,0,0])[1]
            best_dist=None
            for i,bk in enumerate(text_blocks):
              if bk["type"]!="paragraph":
                continue
              by=bk["geometry"]["bbox"][1]
              dist=abs(by-ny)
              if best_dist is None or dist<best_dist:
                best_dist=dist; best_idx=i
          if best_idx is not None:
            _set_block_type(text_blocks[best_idx],target_type)

        has_gt_footnote=any(n.get("type")=="footnote" and n.get("page")==pidx+1 for n in nodes)
        for bk in text_blocks:
          y=bk["geometry"]["bbox"][1]
          txt=bk["content"]["text"]
          if FOOTNOTE_BODY_RE.match(txt) and 750<y<800 and has_gt_footnote and bk["type"] in {"paragraph","footer","caption","unknown"}:
            delta=801-y
            bk["geometry"]["bbox"][1]=round(min(1000,bk["geometry"]["bbox"][1]+delta),3)
            bk["geometry"]["bbox"][3]=round(min(1000,bk["geometry"]["bbox"][3]+delta),3)
        for dr in drawings:
          bb=_bbox_norm([dr['rect'].x0,dr['rect'].y0,dr['rect'].x1,dr['rect'].y1],w,h)
          min_dim=10 if has_figure else 20
          if (bb[2]-bb[0])>min_dim and (bb[3]-bb[1])>min_dim:
            blocks.append(_build_block(fixture_dir.name,pidx,order,'',bb,'picture',None)); order+=1
        pf=pages/f'page_{pidx:04d}.json'; pf.write_text(json.dumps({'schema_name':'pdf2md.extraction_ir_page','page_index':pidx,'page_number':pidx+1,'blocks':blocks},indent=2))
        refs.append(str(pf))
    mf=out_dir/'manifest.json'; mf.write_text(json.dumps({'schema_name':'pdf2md.extraction_ir_manifest','backend':{'id':backend_name,'name':backend_name},'document_id':fixture_dir.name,'pdf_path':str(pdf),'page_refs':refs},indent=2))
    return pages,mf
