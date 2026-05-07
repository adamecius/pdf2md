"""Project LinkedStructure into a Docling-compatible JSON dictionary."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module, util
from typing import Any

from pdf2md.models.ir import ConsensusIR
from pdf2md.models.linked import LinkedNode, LinkedNodeType, LinkedRelationType, LinkedStructure, LinkStatus


@dataclass(frozen=True)
class DoclingExportSettings:
    schema_name: str = "DoclingDocument"
    schema_version: str = "1.7.0"
    include_unresolved: bool = True
    coord_origin: str = "BOTTOMLEFT"


@dataclass(frozen=True)
class DoclingExportResult:
    document: dict[str, Any]
    warnings: list[str]


_GROUP_TYPES = {LinkedNodeType.DOCUMENT, LinkedNodeType.SECTION, LinkedNodeType.LIST, LinkedNodeType.REFERENCE_SECTION}
_TABLE_TYPES = {LinkedNodeType.TABLE}
_PICTURE_TYPES = {LinkedNodeType.FIGURE}
_TEXT_LABELS = {
    LinkedNodeType.TITLE: "title",
    LinkedNodeType.PARAGRAPH: "paragraph",
    LinkedNodeType.LIST_ITEM: "list_item",
    LinkedNodeType.CAPTION: "caption",
    LinkedNodeType.EQUATION: "formula",
    LinkedNodeType.FOOTNOTE: "footnote",
    LinkedNodeType.PAGE_NUMBER: "page_footer",
    LinkedNodeType.HEADER: "page_header",
    LinkedNodeType.FOOTER: "page_footer",
    LinkedNodeType.TOC_ENTRY: "toc_entry",
    LinkedNodeType.REFERENCE_ITEM: "reference",
    LinkedNodeType.BIBLIOGRAPHY_MARKER: "reference_marker",
    LinkedNodeType.CODE: "code",
    LinkedNodeType.UNKNOWN: "unknown",
}
_GROUP_LABELS = {
    LinkedNodeType.SECTION: "section",
    LinkedNodeType.LIST: "list",
    LinkedNodeType.REFERENCE_SECTION: "references",
    LinkedNodeType.DOCUMENT: "document",
}


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _node_type(node: LinkedNode) -> str:
    return str(_value(node.node_type))


def _text(node: LinkedNode) -> str:
    return node.text or str(node.metadata.get("title") or node.metadata.get("label") or "")


def _prov_for(node: LinkedNode, consensus: ConsensusIR | None) -> list[dict[str, Any]]:
    page_no = node.page_no
    bbox = node.metadata.get("bbox")
    if (bbox is None or page_no is None) and consensus is not None and node.consensus_block_id:
        for page in consensus.pages:
            for block in page.blocks:
                if block.id == node.consensus_block_id:
                    page_no = page_no or page.page_no
                    if bbox is None and block.bbox is not None:
                        bbox = block.bbox.model_dump(mode="json")
    if page_no is None:
        return []
    prov: dict[str, Any] = {"page_no": page_no}
    if bbox is not None:
        prov["bbox"] = bbox
    if node.consensus_block_id:
        prov["consensus_block_id"] = node.consensus_block_id
    return [prov]


def _base_item(node: LinkedNode, self_ref: str, consensus: ConsensusIR | None) -> dict[str, Any]:
    metadata = {
        "pdf2md_node_id": node.id,
        "type": _node_type(node),
        "status": _value(node.status),
        "confidence": node.confidence,
        "source_entity_ids": list(node.source_entity_ids),
        **node.metadata,
    }
    if node.status == LinkStatus.UNRESOLVED or _value(node.status) == "unresolved":
        metadata["status"] = "unresolved"
    item = {"self_ref": self_ref, "prov": _prov_for(node, consensus), "metadata": metadata}
    if node.text is not None:
        item["text"] = node.text
    return item


def build_docling_document(
    *,
    linked: LinkedStructure,
    consensus: ConsensusIR | None = None,
    settings: DoclingExportSettings = DoclingExportSettings(),
) -> DoclingExportResult:
    warnings: list[str] = []
    nodes = sorted(linked.nodes, key=lambda n: (n.order, n.id))
    emitted_nodes = [n for n in nodes if settings.include_unresolved or _value(n.status) != "unresolved"]
    pages: dict[str, dict[str, Any]] = {}
    if consensus is not None:
        for page in consensus.pages:
            pages[str(page.page_no)] = {"page_no": page.page_no, "size": page.page_size.model_dump(mode="json")}
    for node in emitted_nodes:
        if node.page_no is not None:
            pages.setdefault(str(node.page_no), {"page_no": node.page_no})
        elif node.node_type != LinkedNodeType.DOCUMENT:
            warnings.append(f"missing_page_for_node:{node.id}")
        if _value(node.status) == "unresolved":
            warnings.append(f"unresolved_node_emitted:{node.id}")

    document: dict[str, Any] = {
        "schema_name": settings.schema_name,
        "version": settings.schema_version,
        "name": linked.document_id,
        "origin": {"mimetype": "application/pdf", "binary_hash": None},
        "body": {"self_ref": "#/body", "children": []},
        "groups": [],
        "texts": [],
        "tables": [],
        "pictures": [],
        "pages": pages,
        "key_value_items": [],
        "form_items": [],
        "metadata": {
            "pdf2md": {
                "schema_name": linked.schema_name,
                "schema_version": linked.schema_version,
                "document_id": linked.document_id,
            },
            "pdf2md_conflicts": [c.model_dump(mode="json") for c in linked.conflicts],
            "warnings": warnings,
        },
    }

    node_ref: dict[str, str] = {}
    for node in emitted_nodes:
        ntype = node.node_type
        if ntype == LinkedNodeType.DOCUMENT:
            node_ref[node.id] = "#/body"
            continue
        if ntype in _GROUP_TYPES:
            ref = f"#/groups/{len(document['groups'])}"
            item = _base_item(node, ref, consensus)
            item.update({"name": _text(node), "label": _GROUP_LABELS.get(ntype, _node_type(node)), "children": []})
            document["groups"].append(item)
        elif ntype in _TABLE_TYPES:
            ref = f"#/tables/{len(document['tables'])}"
            item = _base_item(node, ref, consensus)
            item.update({"label": "table", "data": node.metadata.get("data") or {"table_cells": []}})
            document["tables"].append(item)
        elif ntype in _PICTURE_TYPES:
            ref = f"#/pictures/{len(document['pictures'])}"
            item = _base_item(node, ref, consensus)
            item.update({"label": "picture"})
            document["pictures"].append(item)
        else:
            if ntype not in _TEXT_LABELS:
                warnings.append(f"unsupported_node_type:{node.id}")
            ref = f"#/texts/{len(document['texts'])}"
            item = _base_item(node, ref, consensus)
            item.update({"label": _TEXT_LABELS.get(ntype, "unknown"), "text": _text(node)})
            document["texts"].append(item)
        node_ref[node.id] = ref

    by_ref = _items_by_ref(document)
    parent_by_child: dict[str, str] = {}
    for relation in linked.relations:
        rtype = relation.relation_type
        src = node_ref.get(relation.source_node_id)
        tgt = node_ref.get(relation.target_node_id)
        payload = relation.model_dump(mode="json")
        if rtype in {LinkedRelationType.CONTAINS, LinkedRelationType.PARENT_OF} and src and tgt:
            parent, child = (src, tgt) if rtype == LinkedRelationType.CONTAINS else (src, tgt)
            item = by_ref.get(parent)
            if item is not None and "children" in item and child not in item["children"]:
                item["children"].append(child)
                parent_by_child[child] = parent
        elif rtype == LinkedRelationType.CAPTION_OF and src and tgt:
            target = by_ref.get(tgt)
            if target is not None:
                target.setdefault("metadata", {}).setdefault("captions", []).append(src)
                target["metadata"].setdefault("relations", []).append(payload)
        elif rtype == LinkedRelationType.FOOTNOTE_ANCHOR_FOR and src and tgt:
            footnote = by_ref.get(src)
            anchor_target = by_ref.get(tgt)
            if footnote is not None:
                metadata = footnote.setdefault("metadata", {})
                metadata.setdefault("links", []).append(payload)
                metadata.setdefault("footnote_anchor_targets", []).append(tgt)
            if anchor_target is not None:
                metadata = anchor_target.setdefault("metadata", {})
                metadata.setdefault("links", []).append(payload)
                metadata.setdefault("footnote_anchors", []).append(src)
        elif src:
            item = by_ref.get(src)
            if item is not None:
                item.setdefault("metadata", {}).setdefault("links", []).append(payload)

    for node in emitted_nodes:
        ref = node_ref.get(node.id)
        if not ref or ref == "#/body" or ref in parent_by_child:
            continue
        document["body"]["children"].append(ref)

    warnings.extend(validate_docling_like_document(document))
    document["metadata"]["warnings"] = warnings
    return DoclingExportResult(document=document, warnings=warnings)


def _items_by_ref(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = {"#/body": document["body"]}
    for key in ("groups", "texts", "tables", "pictures"):
        for item in document.get(key, []):
            items[item.get("self_ref", "")] = item
    return items


def validate_docling_like_document(document: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    required = ["schema_name", "version", "name", "origin", "body", "groups", "texts", "tables", "pictures", "pages", "key_value_items", "form_items", "metadata"]
    for key in required:
        if key not in document:
            warnings.append(f"missing_top_level_key:{key}")
    body = document.get("body") or {}
    if body.get("self_ref") != "#/body":
        warnings.append("missing_body_self_ref")
    refs: list[str] = []
    for item in [body, *document.get("groups", []), *document.get("texts", []), *document.get("tables", []), *document.get("pictures", [])]:
        ref = item.get("self_ref")
        if ref:
            refs.append(ref)
    if len(refs) != len(set(refs)):
        warnings.append("duplicate_self_ref")
    known = set(refs)
    for item in [body, *document.get("groups", [])]:
        for child in item.get("children", []):
            if child not in known:
                warnings.append(f"broken_child_ref:{child}")
    page_keys = set(document.get("pages", {}).keys())
    for item in [*document.get("texts", []), *document.get("tables", []), *document.get("pictures", [])]:
        if not item.get("label") and not item.get("metadata", {}).get("type"):
            warnings.append(f"missing_label:{item.get('self_ref')}")
        for prov in item.get("prov", []):
            page_no = prov.get("page_no")
            if page_no is not None and str(page_no) not in page_keys:
                warnings.append(f"missing_page_ref:{item.get('self_ref')}:{page_no}")
    if "pdf2md" not in document.get("metadata", {}):
        warnings.append("missing_pdf2md_metadata")
    return warnings


def try_validate_with_docling_core(document: dict[str, Any]) -> tuple[bool, str | None]:
    if util.find_spec("docling_core") is None:
        return False, "docling_core_unavailable"
    module = import_module("docling_core.types.doc.document")
    docling_document = getattr(module, "DoclingDocument")
    try:
        docling_document.model_validate(document)
    except Exception as exc:
        return False, f"docling_core_validation_failed:{exc.__class__.__name__}"
    return True, None
