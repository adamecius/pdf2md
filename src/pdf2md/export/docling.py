"""Project LinkedStructure into a Docling-compatible JSON dictionary.

Plan 17 wiring guarantees (post-MVP refinement):

- ``origin.filename`` and ``origin.binary_hash`` are always populated when
  a source PDF path is supplied; otherwise placeholders are written that
  still pass ``docling_core.types.doc.DoclingDocument.model_validate``.
- Every emitted ``label`` is a member of
  ``docling_core.types.doc.DocItemLabel`` (or ``None`` for group items
  whose docling representation does not require a label). Unknown
  ``LinkedNodeType`` values fall back to ``"text"`` with a
  ``block_kind_unmapped`` warning.
- ``schema_version`` is resolved at module load from the installed
  ``docling_core`` package's default, falling back to ``"1.10.0"`` if
  unavailable.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib import import_module, util
from pathlib import Path
from typing import Any

from pdf2md.models.ir import ConsensusIR
from pdf2md.models.linked import LinkedNode, LinkedNodeType, LinkedRelationType, LinkedStructure, LinkStatus


def _resolve_docling_schema_version() -> str:
    """Return the docling_core default schema version, fallback to 1.10.0."""

    try:
        if util.find_spec("docling_core") is not None:
            mod = import_module("docling_core.types.doc")
            doc_cls = getattr(mod, "DoclingDocument", None)
            if doc_cls is not None:
                field = doc_cls.model_fields.get("version")
                if field is not None and field.default is not None:
                    return str(field.default)
    except Exception:
        pass
    return "1.10.0"


_DOCLING_SCHEMA_VERSION_DEFAULT: str = _resolve_docling_schema_version()


@dataclass(frozen=True)
class DoclingExportSettings:
    """Settings controlling the Docling export projection.

    Attributes:
        schema_name: Value written to the top-level ``schema_name`` field.
        schema_version: Docling schema version recorded on the document.
        include_unresolved: Emit nodes whose status is ``unresolved`` when
            true; drop them silently when false.
        coord_origin: Coordinate origin convention recorded with bboxes.
    """

    schema_name: str = "DoclingDocument"
    schema_version: str = _DOCLING_SCHEMA_VERSION_DEFAULT
    include_unresolved: bool = True
    coord_origin: str = "BOTTOMLEFT"


@dataclass(frozen=True)
class DoclingExportResult:
    """Result of a Docling export build.

    Attributes:
        document: The Docling document as a JSON-serialisable dictionary.
        warnings: Warnings raised while projecting the LinkedStructure.
    """

    document: dict[str, Any]
    warnings: list[str]


_GROUP_TYPES = {LinkedNodeType.DOCUMENT, LinkedNodeType.SECTION, LinkedNodeType.LIST, LinkedNodeType.REFERENCE_SECTION}
_TABLE_TYPES = {LinkedNodeType.TABLE}
_PICTURE_TYPES = {LinkedNodeType.FIGURE}

# LinkedNodeType -> docling_core.types.doc.DocItemLabel string value.
# Every entry is a real DocItemLabel; previous draft used "toc_entry",
# "reference_marker", and "unknown" which are NOT in the enum. Body
# paragraphs map to "text" rather than "paragraph" to match the corpus
# groundtruth convention (both are valid DocItemLabel values; "text" is
# the one Docling itself emits for narrative body content).
_TEXT_LABELS = {
    LinkedNodeType.TITLE: "title",
    LinkedNodeType.PARAGRAPH: "text",
    LinkedNodeType.LIST_ITEM: "list_item",
    LinkedNodeType.CAPTION: "caption",
    LinkedNodeType.EQUATION: "formula",
    LinkedNodeType.FOOTNOTE: "footnote",
    LinkedNodeType.PAGE_NUMBER: "page_footer",
    LinkedNodeType.HEADER: "page_header",
    LinkedNodeType.FOOTER: "page_footer",
    LinkedNodeType.TOC_ENTRY: "text",  # was "toc_entry" (not a DocItemLabel)
    LinkedNodeType.REFERENCE_ITEM: "reference",
    LinkedNodeType.BIBLIOGRAPHY_MARKER: "reference",  # was "reference_marker"
    LinkedNodeType.CODE: "code",
    LinkedNodeType.UNKNOWN: "text",  # was "unknown" (not a DocItemLabel)
}

# Group items in docling-core do NOT carry a `label`; previously we emitted
# strings like "section" / "list" / "references" / "document" which fail
# strict validation. Plan 17 leaves the label off on groups (the schema
# accepts `label = None`).
_GROUP_LABELS: dict[LinkedNodeType, str | None] = {
    LinkedNodeType.SECTION: None,
    LinkedNodeType.LIST: None,
    LinkedNodeType.REFERENCE_SECTION: None,
    LinkedNodeType.DOCUMENT: None,
}


def _compute_origin(source_pdf: Path | str | None) -> tuple[dict[str, Any], list[str]]:
    """Build the docling `origin` block from a source PDF path.

    Returns (origin_dict, warnings). The dict is always a valid
    ``DocumentOrigin`` payload: ``filename``, ``binary_hash`` and
    ``mimetype`` are always populated. If ``source_pdf`` is None or the
    path does not exist, sentinel values are written and an
    ``origin_pdf_path_unknown`` warning is recorded.

    ``binary_hash`` is the lower 63 bits of the sha256 digest converted
    to an unsigned int. docling-core's schema models the field as a
    positive int; 63 bits comfortably fits in a Python int and gives
    deterministic, collision-resistant identity for an input PDF.
    """

    warnings: list[str] = []
    if source_pdf is None:
        return (
            {"mimetype": "application/pdf", "binary_hash": 0, "filename": "unknown.pdf"},
            ["origin_pdf_path_unknown"],
        )
    path = Path(source_pdf)
    filename = path.name or "unknown.pdf"
    if not path.is_file():
        warnings.append("origin_pdf_path_unknown")
        return ({"mimetype": "application/pdf", "binary_hash": 0, "filename": filename}, warnings)
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    binary_hash = int.from_bytes(h.digest()[:8], "big") & ((1 << 63) - 1)
    return ({"mimetype": "application/pdf", "binary_hash": binary_hash, "filename": filename}, warnings)


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
    source_pdf: Path | str | None = None,
) -> DoclingExportResult:
    """Project a LinkedStructure into a Docling-compatible document dict.

    Walks ``linked.nodes`` in reading order, maps each node to the
    appropriate Docling container (``texts``, ``tables``, ``pictures`` or
    ``groups``), attaches provenance and metadata, and resolves relations
    into Docling parent/child references. Unknown block kinds are routed
    to ``texts`` with a ``block_kind_unmapped`` warning.

    Args:
        linked: Linked structure to project.
        consensus: Optional consensus IR used to backfill bbox/page
            provenance when nodes carry only consensus block references.
        settings: Schema-name and inclusion settings.
        source_pdf: Original PDF path; used to populate ``origin``.

    Returns:
        A DoclingExportResult containing the document dict and the
        warning list (schema, provenance and validation warnings).
    """

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

    origin, origin_warnings = _compute_origin(source_pdf)
    warnings.extend(origin_warnings)

    document: dict[str, Any] = {
        "schema_name": settings.schema_name,
        "version": settings.schema_version,
        "name": linked.document_id,
        "origin": origin,
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
            # docling-core groups do not require (and reject) the legacy
            # pdf2md group labels like "section"/"list"/"references".
            # Drop the label key entirely when the mapping says None.
            group_label = _GROUP_LABELS.get(ntype)
            item.update({"name": _text(node), "children": []})
            if group_label is not None:
                item["label"] = group_label
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
                warnings.append(f"block_kind_unmapped:{node.id}:{_node_type(node)}")
            ref = f"#/texts/{len(document['texts'])}"
            item = _base_item(node, ref, consensus)
            # Fall back to "text" (a valid DocItemLabel) for unmapped kinds;
            # this is recorded as a warning above so the human reviewer sees
            # it on the export report.
            item.update({"label": _TEXT_LABELS.get(ntype, "text"), "text": _text(node)})
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
            parent, child = src, tgt
            parent_item = by_ref.get(parent)
            if parent_item is not None and "children" in parent_item and child not in parent_item["children"]:
                parent_item["children"].append(child)
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
            src_item = by_ref.get(src)
            if src_item is not None:
                src_item.setdefault("metadata", {}).setdefault("links", []).append(payload)

    for node in emitted_nodes:
        node_ref_value = node_ref.get(node.id)
        if not node_ref_value or node_ref_value == "#/body" or node_ref_value in parent_by_child:
            continue
        document["body"]["children"].append(node_ref_value)

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
    """Run lightweight structural checks on a Docling-like document.

    Verifies that required top-level keys are present, ``self_ref`` values
    are unique, child references resolve, page references are known and
    pdf2md metadata is attached.

    Args:
        document: The Docling document dictionary to validate.

    Returns:
        A list of warning strings (empty when the document is valid).
    """

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
    """Attempt validation through ``docling_core.types.doc.DoclingDocument``.

    Args:
        document: The Docling document dictionary to validate.

    Returns:
        A tuple ``(ok, reason)`` where ``ok`` is ``True`` only when
        docling_core is installed and accepts the document; ``reason``
        carries a short marker string explaining the outcome.
    """

    if util.find_spec("docling_core") is None:
        return False, "docling_core_unavailable"
    module = import_module("docling_core.types.doc.document")
    docling_document = module.DoclingDocument
    try:
        docling_document.model_validate(document)
    except Exception as exc:
        return False, f"docling_core_validation_failed:{exc.__class__.__name__}"
    return True, None
