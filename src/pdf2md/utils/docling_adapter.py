from __future__ import annotations
import argparse, datetime as dt, json
from pathlib import Path
from typing import Any

class AdapterError(RuntimeError): ...

class DoclingBackend:
    def __init__(self, doc: Any): self.doc = doc
    @staticmethod
    def load() -> "DoclingBackend":
        try:
            from docling_core.types.doc import DoclingDocument  # type: ignore
        except Exception as e:
            raise AdapterError("Docling adapter requires docling/docling-core. Install the optional Docling dependency before using this command.") from e
        try: doc = DoclingDocument(name="inspection")
        except Exception: doc = DoclingDocument()
        return DoclingBackend(doc)
    def add_text(self, text:str, semantic_type:str|None=None):
        if not hasattr(self.doc, "add_text"): raise AdapterError("DoclingDocument add_text API unavailable")
        label = _docling_label_for_semantic_type(semantic_type)
        attempts = [
            ("add_text(label=..., text=...)", lambda: self.doc.add_text(label=label, text=text)),
            ("add_text(label, text)", lambda: self.doc.add_text(label, text)),
            ("add_text(text=..., label=...)", lambda: self.doc.add_text(text=text, label=label)),
            ("add_text(text)", lambda: self.doc.add_text(text)),
        ]
        errors: list[str] = []
        for name, fn in attempts:
            try:
                fn()
                return
            except Exception as e:
                errors.append(f"{name}: {e.__class__.__name__}: {e}")
        raise AdapterError("DoclingDocument add_text API unsupported; attempted variants: " + " | ".join(errors))
    def add_picture(self, path:str, caption:str|None=None):
        if not hasattr(self.doc, "add_picture"): raise AdapterError("DoclingDocument add_picture API unavailable")
        self.doc.add_picture(path, caption=caption)
    def export_json(self)->dict[str,Any]:
        if hasattr(self.doc, "export_to_dict"): return self.doc.export_to_dict()
        if hasattr(self.doc, "model_dump"): return self.doc.model_dump(mode="json")
        raise AdapterError("DoclingDocument JSON export API unavailable")
    def export_markdown(self)->str:
        if not hasattr(self.doc, "export_to_markdown"): raise AdapterError("Docling markdown export API unavailable")
        return self.doc.export_to_markdown()

def _dedup_push(container:list[str], msg:str):
    if msg not in container: container.append(msg)

def _single_source_geometry(block:dict[str,Any])->bool:
    ag=(block.get("agreement") or {}).get("geometry")
    md=block.get("metadata") or {}
    warns=[str(x) for x in (block.get("warnings") or [])]
    return ag=="single_source" or md.get("media_status")=="single_source_geometry" or any("single_source_geometry" in w for w in warns)

def _docling_label_for_semantic_type(semantic_type: str | None) -> Any:
    fallback = semantic_type or "paragraph"
    try:
        from docling_core.types.doc import DocItemLabel  # type: ignore
    except Exception:
        return fallback
    mapping = {
        "paragraph": "TEXT",
        "caption": "CAPTION",
        "footnote": "FOOTNOTE",
        "heading": "SECTION_HEADER",
        "title": "TITLE",
        "list_item": "LIST_ITEM",
        "table": "TABLE",
        "formula": "FORMULA",
    }
    label_name = mapping.get((semantic_type or "").lower())
    if label_name and hasattr(DocItemLabel, label_name):
        return getattr(DocItemLabel, label_name)
    return fallback

def _backend_add_text(backend: Any, text: str, semantic_type: str | None) -> None:
    try:
        backend.add_text(text, semantic_type=semantic_type)
    except TypeError:
        backend.add_text(text)

def adapt_semantic_document(semantic:dict[str,Any], *, source_semantic_document:str="", include_orphan_media:bool=False, mode:str="inspection", output_root:Path|None=None, backend:DoclingBackend|None=None)->tuple[dict[str,Any],dict[str,Any],dict[str,Any],str|None]:
    backend = backend or DoclingBackend.load()
    created = dt.datetime.now(dt.timezone.utc).isoformat()
    rel={"schema_name":"pdf2md.docling_relations","schema_version":"0.1.0","source_semantic_document":source_semantic_document,"source_docling_document":"docling_document.json","created_at":created,"id_map":{},"nodes":[],"anchors":semantic.get("anchors",[]),"references":semantic.get("references",[]),"relations":semantic.get("relations",[]),"conflicts":semantic.get("conflicts",[]),"warnings":[]}
    rep={"schema_name":"pdf2md.docling_adapter_report","schema_version":"0.1.0","mode":mode,"created_at":created,"source_semantic_document":source_semantic_document,"outputs":{"docling_document":"docling_document.json","docling_relations":"docling_relations.json","markdown_preview":"docling_preview.md"},"stats":{"blocks_total":len(semantic.get("blocks",[])),"mapped":0,"degraded":0,"suppressed":0,"relations_preserved":len(semantic.get("relations",[])),"references_preserved":len(semantic.get("references",[])),"anchors_preserved":len(semantic.get("anchors",[])),"conflicts_preserved":len(semantic.get("conflicts",[]))},"warnings":[],"errors":[]}
    text_i=0; pic_i=0
    for w in semantic.get("warnings", []) or []:
        _dedup_push(rel["warnings"], str(w)); _dedup_push(rep["warnings"], str(w))
    blocks={b.get("id"):b for b in semantic.get("blocks",[])}
    caption_sources={}
    for r in semantic.get("relations",[]):
        if r.get("relation_type")=="caption_of": caption_sources.setdefault(r.get("target_id"),[]).append(r.get("source_id"))
    by_anchor={}
    for b in semantic.get("blocks",[]):
        if b.get("type")=="formula" and b.get("anchor_id"): by_anchor.setdefault(b["anchor_id"],[]).append(b["id"])
    for aid, ids in by_anchor.items():
        if len(ids)>1:
            m=f"duplicate_formula_candidates:{aid}:{','.join(ids)}"; _dedup_push(rel["warnings"],m); _dedup_push(rep["warnings"],m)

    for b in semantic.get("blocks",[]):
        bid=b.get("id"); btype=b.get("type")
        node={k:b.get(k) for k in ["id","type","text","label","page_index","page_number","bbox","source_group_id","source_group_members","sources","status","selection_mode","selected_text_source","selected_geometry_source","media_id","media_path","anchor_id","agreement","conflicts","warnings","metadata"]}
        rel["nodes"].append(node)
        if not b.get("bbox"): _dedup_push(rel["warnings"],f"missing_bbox:{bid}"); _dedup_push(rep["warnings"],f"missing_bbox:{bid}")
        if b.get("selection_mode")=="fallback_default_backend": _dedup_push(rel["warnings"],f"fallback_default_backend:{bid}"); _dedup_push(rep["warnings"],f"fallback_default_backend:{bid}")
        if _single_source_geometry(b): _dedup_push(rel["warnings"],f"single_source_geometry:{bid}"); _dedup_push(rep["warnings"],f"single_source_geometry:{bid}")
        if btype=="formula":
            if b.get("selected_text_source") and b.get("selected_geometry_source") and b.get("selected_text_source")!=b.get("selected_geometry_source"):
                _dedup_push(rel["warnings"],f"formula_text_geometry_not_fused:{bid}"); _dedup_push(rep["warnings"],f"formula_text_geometry_not_fused:{bid}")
            if not b.get("bbox") or b.get("conflicts") or (b.get("agreement") or {}).get("text")=="conflict" or (b.get("agreement") or {}).get("geometry")=="conflict":
                _dedup_push(rel["warnings"],f"formula_text_geometry_not_fused:{bid}"); _dedup_push(rep["warnings"],f"formula_text_geometry_not_fused:{bid}")

        mapped_ref=None; mapped_type=None
        try:
            if btype=="figure":
                mp=b.get("media_path")
                if not mp:
                    if b.get("anchor_id"):
                        m = f"figure_without_media_degraded:{bid}"
                        _dedup_push(rel["warnings"], m); _dedup_push(rep["warnings"], m)
                        if mode == "strict":
                            rep["errors"].append(m)
                        _backend_add_text(backend, (b.get("text") or "").strip(), btype)
                        mapped_type="text"; mapped_ref=f"#/texts/{text_i}"; text_i+=1
                    else:
                        m = f"figure_without_media_suppressed:{bid}"
                        _dedup_push(rel["warnings"], m); _dedup_push(rep["warnings"], m)
                        if mode == "strict":
                            rep["errors"].append(m)
                        rel["id_map"][bid]={"docling_ref":None,"docling_type":None,"semantic_type":btype,"suppressed":True,"reason":"figure_without_media_suppressed"}; rep["stats"]["suppressed"]+=1
                    if mapped_ref is not None:
                        rel["id_map"][bid]={"docling_ref":mapped_ref,"docling_type":mapped_type,"semantic_type":btype}; node["docling_ref"]=mapped_ref; node["docling_type"]=mapped_type; rep["stats"]["mapped"]+=1
                    continue
                if mp:
                    p=Path(mp)
                    if not p.is_absolute() and source_semantic_document: p=Path(source_semantic_document).parent/p
                    if output_root and not p.exists() and (output_root/mp).exists(): p=output_root/mp
                    if not p.exists():
                        mm=f"missing_media_file:{bid}:{mp}"; _dedup_push(rel["warnings"],mm); _dedup_push(rep["warnings"],mm)
                        if mode=="strict" and b.get("anchor_id"): rep["errors"].append(mm)
                if mp and not b.get("anchor_id") and not include_orphan_media:
                    m=f"orphan_media_suppressed:{bid}"; _dedup_push(rel["warnings"],m); _dedup_push(rep["warnings"],m);
                    if mode=="strict": rep["errors"].append(m)
                    rel["id_map"][bid]={"docling_ref":None,"docling_type":None,"semantic_type":btype,"suppressed":True,"reason":"orphan_media_suppressed"}; rep["stats"]["suppressed"]+=1; continue
                if mp and not b.get("anchor_id") and include_orphan_media:
                    _dedup_push(rel["warnings"],f"orphan_media_included_debug:{bid}"); _dedup_push(rep["warnings"],f"orphan_media_included_debug:{bid}")
                caps=caption_sources.get(bid,[])
                cap=" ".join((blocks.get(cid,{}) or {}).get("text") or "" for cid in caps).strip() or None
                if len(caps)>1:
                    _dedup_push(rel["warnings"],f"fragmented_caption:{b.get('anchor_id') or bid}:{','.join(caps)}"); _dedup_push(rep["warnings"],f"fragmented_caption:{b.get('anchor_id') or bid}:{','.join(caps)}")
                    _dedup_push(rel["warnings"],f"caption_joined_from_fragments:{bid}"); _dedup_push(rep["warnings"],f"caption_joined_from_fragments:{bid}")
                backend.add_picture(mp or "", caption=cap)
                mapped_type="picture"; mapped_ref=f"#/pictures/{pic_i}"; pic_i+=1
            else:
                if btype=="table": _dedup_push(rel["warnings"],f"table_structure_degraded:{bid}"); _dedup_push(rep["warnings"],f"table_structure_degraded:{bid}"); rep["stats"]["degraded"]+=1
                if btype=="formula": _dedup_push(rel["warnings"],f"degraded_block:{bid}:formula->text"); _dedup_push(rep["warnings"],f"degraded_block:{bid}:formula->text"); rep["stats"]["degraded"]+=1
                if btype=="footnote": _dedup_push(rel["warnings"],f"footnote_degraded:{bid}"); _dedup_push(rep["warnings"],f"footnote_degraded:{bid}"); rep["stats"]["degraded"]+=1
                _backend_add_text(backend, (b.get("text") or "").strip(), btype)
                mapped_type="text"; mapped_ref=f"#/texts/{text_i}"; text_i+=1
        except Exception as e:
            msg=f"degraded_block:{bid}:{btype}->text:{e.__class__.__name__}:{e}"
            _dedup_push(rel["warnings"],msg); _dedup_push(rep["warnings"],msg)
            if mode=="strict" and btype=="figure" and b.get("anchor_id"): rep["errors"].append(msg)
            _backend_add_text(backend, (b.get("text") or "").strip(), btype); mapped_type="text"; mapped_ref=f"#/texts/{text_i}"; text_i+=1
        rel["id_map"][bid]={"docling_ref":mapped_ref,"docling_type":mapped_type,"semantic_type":btype}; node["docling_ref"]=mapped_ref; node["docling_type"]=mapped_type; rep["stats"]["mapped"]+=1

    unresolved=set(semantic.get("validation",{}).get("unresolved_references",[]) or [])
    unresolved.update(r.get("reference_id") for r in semantic.get("references",[]) if not r.get("resolved") and r.get("reference_id"))
    for rid in sorted(unresolved):
        m=f"unresolved_reference:{rid}"; _dedup_push(rel["warnings"],m); _dedup_push(rep["warnings"],m);
        if mode=="strict": rep["errors"].append(m)
    for r in semantic.get("references",[]):
        if r.get("reference_type")=="footnote" and not r.get("resolved"):
            m=f"footnote_marker_unresolved:{r.get('reference_id')}"; _dedup_push(rel["warnings"],m); _dedup_push(rep["warnings"],m)

    return backend.export_json(), rel, rep, None

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("semantic_document_json"); ap.add_argument("--output-root",required=True); ap.add_argument("--mode",choices=["inspection","strict"],default="inspection"); ap.add_argument("--include-orphan-media",action="store_true"); ap.add_argument("--export-markdown",action="store_true"); ap.add_argument("--json-only",action="store_true"); ap.add_argument("--verbose",action="store_true"); args=ap.parse_args()
    inp=Path(args.semantic_document_json); out=Path(args.output_root); out.mkdir(parents=True,exist_ok=True)
    try:
        semantic=json.loads(inp.read_text(encoding="utf-8")); backend=DoclingBackend.load()
    except Exception as e:
        print(str(e)); return 2
    doc, rel, rep, _=adapt_semantic_document(semantic, source_semantic_document=str(inp), include_orphan_media=args.include_orphan_media, mode=args.mode, output_root=out, backend=backend)
    (out/"docling_document.json").write_text(json.dumps(doc,indent=2),encoding="utf-8")
    (out/"docling_relations.json").write_text(json.dumps(rel,indent=2),encoding="utf-8")
    if args.export_markdown:
        try: (out/"docling_preview.md").write_text(backend.export_markdown(),encoding="utf-8")
        except Exception as e:
            m=f"markdown_export_unavailable:{e}"; _dedup_push(rel["warnings"],m); _dedup_push(rep["warnings"],m); rep["errors"].append("failed_docling_markdown_export")
            (out/"docling_relations.json").write_text(json.dumps(rel,indent=2),encoding="utf-8")
    (out/"docling_adapter_report.json").write_text(json.dumps(rep,indent=2),encoding="utf-8")
    if args.verbose: print(json.dumps(rep,indent=2))
    return 2 if args.mode=="strict" and (rep["warnings"] or rep["errors"]) else 0

if __name__=="__main__": raise SystemExit(main())
