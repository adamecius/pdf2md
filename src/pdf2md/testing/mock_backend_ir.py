from __future__ import annotations
import hashlib, json, re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import fitz
TYPE_MAP={"title":"title","section":"heading","subsection":"heading","paragraph":"paragraph","caption":"caption","list_item":"list_item","footnote":"footnote","equation":"formula","table":"table","figure":"picture","reference":"paragraph"}
@dataclass
class GTNode:
    text:str; kind:str; used:bool=False

def _norm_text(text:str)->str:return re.sub(r"\s+"," ",(text or "").strip().lower())
def _sha(v:str)->str:return "sha256:"+hashlib.sha256((v or "").encode()).hexdigest()
def _bbox_norm(rect:list[float],w:float,h:float)->list[float]:
    x0,y0,x1,y1=rect;return [max(0.0,min(1000.0,round(v,3))) for v in [x0/w*1000,y0/h*1000,x1/w*1000,y1/h*1000]]
def _match_kind(text:str,nodes:list[GTNode])->str:
    nt=_norm_text(text)
    if not nt:return "paragraph"
    toks=set(nt.split());bi=None;bs=0.0
    for i,n in enumerate(nodes):
        if n.used:continue
        nn=_norm_text(n.text)
        if not nn:continue
        if nn in nt or nt in nn:score=min(len(nn),len(nt))/max(len(nn),len(nt))
        else:
            ntoks=set(nn.split());score=len(toks & ntoks)/(len(toks|ntoks) or 1)
        if score>bs:bi,bs=i,score
    if bi is not None and bs>=0.25:
        nodes[bi].used=True;return TYPE_MAP.get(nodes[bi].kind,"paragraph")
    return "paragraph"

def _build_block(doc_id:str,page_index:int,order:int,text:str,bbox:list[float],kind:str,heading_level:int|None=None)->dict[str,Any]:
    n=_norm_text(text)
    return {"block_id":f"groundtruth_{doc_id}_p{page_index:04d}_b{order:04d}","page_index":page_index,"page_number":page_index+1,"order":order,"type":kind,"subtype":None,"semantic_role":kind,"docling_label_hint":kind,"docling":{"label_hint":kind,"excluded_from_docling":False},"geometry":{"bbox":bbox,"coordinate_space":"page_normalised_1000","origin":"top_left"},"content":{"text":text,"normalised_text":n,"markdown":text},"structure":{"heading_level":heading_level},"confidence":{"overall":0.99,"layout":0.99,"text":0.99},"comparison":{"compare_as":kind,"text_hash":_sha(n),"geometry_hash":_sha(",".join(str(x) for x in bbox))},"compile_role":"candidate","source_refs":[],"flags":[]}

def generate_mock_backend_ir(fixture_dir:Path,out_dir:Path,backend_name:str="groundtruth"):
    fixture_dir=Path(fixture_dir);out_dir=Path(out_dir)
    gt=json.loads((fixture_dir/"groundtruth"/"source_groundtruth_ir.json").read_text())
    pdf_path=fixture_dir/"input"/f"{fixture_dir.name}.pdf"
    nodes=[GTNode(text=n.get("text",""),kind=n.get("type","paragraph")) for n in gt.get("nodes",[])]
    pages_dir=out_dir/"pages";pages_dir.mkdir(parents=True,exist_ok=True)
    doc=fitz.open(pdf_path);page_refs=[]
    for pidx,page in enumerate(doc):
        pw,ph=page.rect.width,page.rect.height;blocks=[];order=0
        for b in page.get_text("dict").get("blocks",[]):
            if b.get("type")!=0:continue
            raw="\n".join("".join(span.get("text","") for span in line.get("spans",[])) for line in b.get("lines",[])).strip()
            if not raw:continue
            kind=_match_kind(raw,nodes);hl=1 if kind=="heading" and raw.lstrip().startswith("1") else None
            blocks.append(_build_block(fixture_dir.name,pidx,order,raw,_bbox_norm(b["bbox"],pw,ph),kind,hl));order+=1
        for d in page.get_drawings() or []:
            rect=d.get("rect")
            if not rect:continue
            blocks.append(_build_block(fixture_dir.name,pidx,order,"",_bbox_norm([rect.x0,rect.y0,rect.x1,rect.y1],pw,ph),"picture"));order+=1
        pf=pages_dir/f"page_{pidx:04d}.json";pf.write_text(json.dumps({"schema_name":"pdf2md.extraction_ir_page","page_index":pidx,"page_number":pidx+1,"blocks":blocks},indent=2))
        page_refs.append(str(pf))
    mf=out_dir/"manifest.json";mf.write_text(json.dumps({"schema_name":"pdf2md.extraction_ir_manifest","backend":{"id":backend_name,"name":backend_name},"document_id":fixture_dir.name,"pdf_path":str(pdf_path),"page_refs":page_refs},indent=2))
    return pages_dir,mf
