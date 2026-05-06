#!/usr/bin/env python3
"""Build DoclingDocument ground truth JSON from LaTeX corpus fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docling_core.types.doc import (
    DocItemLabel,
    DoclingDocument,
    GroupLabel,
    TableCell,
    TableData,
)

_COMMAND_WITH_ARG_RE = re.compile(r"\\(?:textbf|emph|textit|mathrm|mathbf|cite|url)\{([^{}]*)\}")
_REF_RE = re.compile(r"\\ref\{([^{}]+)\}")
_BEGIN_RE = re.compile(r"\\begin\{([^{}]+)\}")
_ENV_NAMES = {
    "document",
    "equation",
    "figure",
    "table",
    "tabular",
    "itemize",
    "enumerate",
    "thebibliography",
}
_KNOWN_COMMANDS = {
    "begin",
    "centering",
    "caption",
    "cite",
    "clearpage",
    "documentclass",
    "emph",
    "end",
    "fbox",
    "footnote",
    "frac",
    "hline",
    "int",
    "item",
    "label",
    "maketitle",
    "mathbf",
    "mathrm",
    "newpage",
    "ref",
    "rule",
    "section",
    "subsection",
    "textbf",
    "textit",
    "title",
    "url",
}


@dataclass
class GroundtruthMeta:
    document_id: str
    source_tex: str
    source_sha256: str
    labels: dict[str, str] = field(default_factory=dict)
    references: list[dict[str, str]] = field(default_factory=list)
    footnote_anchors: list[dict[str, str]] = field(default_factory=list)
    caption_relations: list[dict[str, str]] = field(default_factory=list)
    bibliography_entries: list[str] = field(default_factory=list)
    ordered_list_groups: list[str] = field(default_factory=list)
    latexml_checks: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_name": "pdf2md.docling_groundtruth_meta",
            "schema_version": "1.0.0",
            "document_id": self.document_id,
            "source_tex": self.source_tex,
            "source_sha256": self.source_sha256,
            "labels": self.labels,
            "references": self.references,
            "footnote_anchors": self.footnote_anchors,
            "caption_relations": self.caption_relations,
            "bibliography_entries": self.bibliography_entries,
            "ordered_list_groups": self.ordered_list_groups,
            "latexml_checks": self.latexml_checks,
            "warnings": sorted(set(self.warnings)),
        }


@dataclass
class ParseState:
    doc_id: str
    tex_path: Path
    doc: DoclingDocument
    meta: GroundtruthMeta
    current_section: Any = None
    current_subsection: Any = None
    last_item: Any = None
    pending_labels: list[str] = field(default_factory=list)
    section_titles: list[str] = field(default_factory=list)
    paragraph_texts: list[str] = field(default_factory=list)

    def parent(self) -> Any:
        return self.current_subsection or self.current_section

    def add_label(self, label: str) -> None:
        if self.last_item is not None:
            self.meta.labels[label] = self.last_item.self_ref
        else:
            self.pending_labels.append(label)

    def bind_pending_labels(self, item: Any) -> None:
        for label in self.pending_labels:
            self.meta.labels[label] = item.self_ref
        self.pending_labels.clear()

    def add_text(self, label: DocItemLabel, text: str, parent: Any = None, **kwargs: Any) -> Any:
        cleaned = normalize_text(text)
        if not cleaned:
            return None
        item = self.doc.add_text(label=label, text=cleaned, parent=parent if parent is not None else self.parent(), **kwargs)
        if label == DocItemLabel.TEXT:
            self.paragraph_texts.append(cleaned)
        self.last_item = item
        self.bind_pending_labels(item)
        record_refs(self.meta, item.self_ref, text)
        return item


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strip_comments(tex: str) -> str:
    out: list[str] = []
    for line in tex.splitlines():
        escaped = False
        keep: list[str] = []
        for ch in line:
            if ch == "%" and not escaped:
                break
            keep.append(ch)
            escaped = ch == "\\" and not escaped
            if ch != "\\":
                escaped = False
        out.append("".join(keep))
    return "\n".join(out)


def normalize_text(text: str) -> str:
    text = text.replace("~", " ")
    text = re.sub(r"\\(?:maketitle|newpage|clearpage|hline)\b", " ", text)
    text = re.sub(r"\\label\{[^{}]+\}", " ", text)
    text = re.sub(r"\\caption\{[^{}]*\}", " ", text, flags=re.S)
    text = re.sub(r"\\ref\{([^{}]+)\}", r"\\ref{\1}", text)
    previous = None
    while previous != text:
        previous = text
        text = _COMMAND_WITH_ARG_RE.sub(r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = text.replace("\\&", "&")
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_braced(text: str, command: str, start: int = 0) -> tuple[str, int, int] | None:
    marker = f"\\{command}"
    idx = text.find(marker, start)
    if idx < 0:
        return None
    brace = text.find("{", idx + len(marker))
    if brace < 0:
        return None
    depth = 0
    for pos in range(brace, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1 : pos], idx, pos + 1
    return None


def iter_braced(text: str, command: str) -> list[tuple[str, int, int]]:
    items: list[tuple[str, int, int]] = []
    start = 0
    while True:
        found = extract_braced(text, command, start)
        if not found:
            return items
        items.append(found)
        start = found[2]


def extract_environment(text: str, env: str, start: int = 0) -> tuple[str, int, int] | None:
    begin = f"\\begin{{{env}}}"
    end = f"\\end{{{env}}}"
    idx = text.find(begin, start)
    if idx < 0:
        return None
    pos = idx + len(begin)
    depth = 1
    while depth:
        next_begin = text.find(begin, pos)
        next_end = text.find(end, pos)
        if next_end < 0:
            return None
        if next_begin >= 0 and next_begin < next_end:
            depth += 1
            pos = next_begin + len(begin)
        else:
            depth -= 1
            if depth == 0:
                return text[idx + len(begin) : next_end], idx, next_end + len(end)
            pos = next_end + len(end)
    return None


def record_refs(meta: GroundtruthMeta, source_ref: str, text: str) -> None:
    for target in _REF_RE.findall(text):
        meta.references.append({"source_ref": source_ref, "target_label": target, "resolved_ref": ""})


def resolve_references(meta: GroundtruthMeta) -> None:
    for ref in meta.references:
        ref["resolved_ref"] = meta.labels.get(ref["target_label"], "")
        if not ref["resolved_ref"]:
            meta.warnings.append(f"unresolved_ref:{ref['target_label']}")


def parse_tabular(body: str, meta: GroundtruthMeta) -> TableData:
    body = re.sub(r"^\s*\{[^{}]*\}", "", body, count=1)
    body = re.sub(r"\\hline\b", "", body)
    rows: list[list[str]] = []
    for raw_row in re.split(r"\\\\", body):
        raw_row = raw_row.strip()
        if not raw_row:
            continue
        cells = [normalize_text(cell) for cell in raw_row.split("&")]
        if cells:
            rows.append(cells)
    if not rows:
        meta.warnings.append(f"table_parse_incomplete:{meta.document_id}")
        rows = [[""]]
    num_rows = len(rows)
    num_cols = max(len(row) for row in rows)
    table_cells: list[TableCell] = []
    for row_idx, row in enumerate(rows):
        for col_idx in range(num_cols):
            table_cells.append(
                TableCell(
                    text=row[col_idx] if col_idx < len(row) else "",
                    start_row_offset_idx=row_idx,
                    end_row_offset_idx=row_idx + 1,
                    start_col_offset_idx=col_idx,
                    end_col_offset_idx=col_idx + 1,
                )
            )
    return TableData(table_cells=table_cells, num_rows=num_rows, num_cols=num_cols)


def split_top_level_items(body: str) -> list[str]:
    matches = list(re.finditer(r"\\(?:item\b|begin\{(?:itemize|enumerate)\}|end\{(?:itemize|enumerate)\})", body))
    starts: list[int] = []
    depth = 0
    for match in matches:
        token = match.group(0)
        if token == r"\item" and depth == 0:
            starts.append(match.start())
        elif token.startswith(r"\begin"):
            depth += 1
        elif token.startswith(r"\end") and depth > 0:
            depth -= 1
    if not starts:
        return []
    starts.append(len(body))
    chunks: list[str] = []
    for idx in range(len(starts) - 1):
        chunk = re.sub(r"^\\item\b\s*", "", body[starts[idx] : starts[idx + 1]].strip())
        if chunk:
            chunks.append(chunk)
    return chunks


def parse_inline_math_and_text(state: ParseState, text: str, parent: Any = None) -> None:
    text = re.sub(r"\\label\{([^{}]+)\}", lambda m: _capture_label(state, m.group(1)), text)
    parts = re.split(r"(\$\$.*?\$\$|(?<!\\)\$.*?(?<!\\)\$)", text, flags=re.S)
    for part in parts:
        if not part or not part.strip():
            continue
        if part.startswith("$$") and part.endswith("$$"):
            state.add_text(DocItemLabel.FORMULA, part[2:-2], parent=parent)
        elif part.startswith("$") and part.endswith("$"):
            state.add_text(DocItemLabel.FORMULA, part[1:-1], parent=parent)
        else:
            clean = normalize_text(part)
            if clean:
                state.add_text(DocItemLabel.TEXT, part, parent=parent)


def _capture_label(state: ParseState, label: str) -> str:
    state.add_label(label)
    return " "


def parse_list(state: ParseState, env: str, body: str, parent: Any = None) -> Any:
    group = state.doc.add_group(
        label=GroupLabel.ORDERED_LIST if env == "enumerate" else GroupLabel.LIST,
        parent=parent if parent is not None else state.parent(),
    )
    state.last_item = group
    if env == "enumerate":
        state.meta.ordered_list_groups.append(group.self_ref)
    state.bind_pending_labels(group)
    for chunk in split_top_level_items(body):
        nested_match = re.search(r"\\begin\{(itemize|enumerate)\}", chunk)
        item_text = chunk[: nested_match.start()] if nested_match else chunk
        item = state.add_text(
            DocItemLabel.LIST_ITEM,
            item_text,
            parent=group,
            enumerated=env == "enumerate",
            marker="",
        )
        if nested_match:
            parse_blocks(state, chunk[nested_match.start() :], parent=item or group)
    return group


def parse_figure(state: ParseState, body: str) -> None:
    caption_item = None
    caption = extract_braced(body, "caption")
    if caption:
        caption_item = state.doc.add_text(label=DocItemLabel.CAPTION, text=normalize_text(caption[0]), parent=state.parent())
        state.last_item = caption_item
        state.bind_pending_labels(caption_item)
        record_refs(state.meta, caption_item.self_ref, caption_item.text)
    picture = state.doc.add_picture(caption=caption_item, parent=state.parent())
    state.last_item = picture
    state.bind_pending_labels(picture)
    for label, _, _ in iter_braced(body, "label"):
        state.meta.labels[label] = picture.self_ref
    if caption_item is not None:
        state.meta.caption_relations.append({"caption_ref": caption_item.self_ref, "target_ref": picture.self_ref})


def parse_table(state: ParseState, body: str) -> None:
    caption_item = None
    caption = extract_braced(body, "caption")
    if caption:
        caption_item = state.doc.add_text(label=DocItemLabel.CAPTION, text=normalize_text(caption[0]), parent=state.parent())
        state.last_item = caption_item
        state.bind_pending_labels(caption_item)
        record_refs(state.meta, caption_item.self_ref, caption_item.text)
    tabular = extract_environment(body, "tabular")
    data = parse_tabular(tabular[0] if tabular else "", state.meta)
    table = state.doc.add_table(data=data, caption=caption_item, parent=state.parent())
    state.last_item = table
    state.bind_pending_labels(table)
    for label, _, _ in iter_braced(body, "label"):
        state.meta.labels[label] = table.self_ref
    if caption_item is not None:
        state.meta.caption_relations.append({"caption_ref": caption_item.self_ref, "target_ref": table.self_ref})


def parse_footnotes(state: ParseState, text: str, parent: Any = None) -> str:
    pieces: list[str] = []
    last = 0
    for footnote, start, end in iter_braced(text, "footnote"):
        pieces.append(text[last:start])
        anchor = state.last_item.self_ref if state.last_item is not None else ""
        item = state.add_text(DocItemLabel.FOOTNOTE, footnote, parent=parent)
        if item is not None:
            state.meta.footnote_anchors.append({"footnote_ref": item.self_ref, "anchor_ref": anchor})
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def parse_blocks(state: ParseState, text: str, parent: Any = None) -> None:
    pos = 0
    paragraph: list[str] = []

    def flush() -> None:
        raw = "\n".join(paragraph).strip()
        paragraph.clear()
        if raw:
            raw_no_footnotes = parse_footnotes(state, raw, parent=parent)
            parse_inline_math_and_text(state, raw_no_footnotes, parent=parent)

    while pos < len(text):
        commands: list[tuple[int, str, Any]] = []
        for cmd in ("title", "section", "subsection", "label"):
            found = extract_braced(text, cmd, pos)
            if found:
                commands.append((found[1], cmd, found))
        for env in ("equation", "figure", "table", "itemize", "enumerate"):
            found = extract_environment(text, env, pos)
            if found:
                commands.append((found[1], env, found))
        if not commands:
            paragraph.append(text[pos:])
            break
        start, kind, found = min(commands, key=lambda item: item[0])
        paragraph.append(text[pos:start])
        flush()
        if kind == "title":
            item = state.add_text(DocItemLabel.TITLE, found[2] and found[0] or "", parent=parent)
        elif kind == "section":
            item = state.doc.add_text(label=DocItemLabel.SECTION_HEADER, text=normalize_text(found[0]), parent=parent, level=1)
            state.section_titles.append(item.text)
            state.current_section = item
            state.current_subsection = None
            state.last_item = item
            state.bind_pending_labels(item)
            record_refs(state.meta, item.self_ref, item.text)
        elif kind == "subsection":
            item = state.doc.add_text(label=DocItemLabel.SECTION_HEADER, text=normalize_text(found[0]), parent=state.current_section or parent, level=2)
            state.section_titles.append(item.text)
            state.current_subsection = item
            state.last_item = item
            state.bind_pending_labels(item)
            record_refs(state.meta, item.self_ref, item.text)
        elif kind == "label":
            state.add_label(found[0])
        elif kind == "equation":
            body = normalize_text(found[0])
            if not body:
                state.meta.warnings.append(f"empty_equation:{state.doc_id}")
            else:
                state.add_text(DocItemLabel.FORMULA, body, parent=parent)
            for label, _, _ in iter_braced(found[0], "label"):
                state.meta.labels[label] = state.last_item.self_ref if state.last_item is not None else ""
        elif kind == "figure":
            parse_figure(state, found[0])
        elif kind == "table":
            parse_table(state, found[0])
        elif kind in {"itemize", "enumerate"}:
            parse_list(state, kind, found[0], parent=parent)
        pos = found[2]
    flush()

    for match in _BEGIN_RE.finditer(text):
        env = match.group(1)
        if env not in _ENV_NAMES:
            state.meta.warnings.append(f"unknown_environment:{env}")
    for match in re.finditer(r"\\([a-zA-Z]+)\*?", text):
        command = match.group(1)
        if command not in _KNOWN_COMMANDS:
            state.meta.warnings.append(f"unknown_command:{command}")


def strip_preamble(tex: str) -> str:
    document = extract_environment(tex, "document")
    if document:
        preamble = tex[: document[1]]
        title = extract_braced(preamble, "title")
        prefix = f"\\title{{{title[0]}}}\n" if title else ""
        return prefix + document[0]
    return tex


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def xml_node_text(node: ET.Element) -> str:
    return normalize_text(" ".join(node.itertext()))


def xml_child_text(node: ET.Element, names: set[str]) -> str:
    for child in node:
        if xml_local_name(child.tag) in names:
            return xml_node_text(child)
    return ""


def ref_label_from_xml(node: ET.Element) -> str:
    for key in ("labelref", "label", "target", "href", "refid", "idref"):
        value = node.attrib.get(key)
        if not value:
            continue
        value = value.lstrip("#")
        if value.startswith("LABEL:"):
            value = value.removeprefix("LABEL:")
        return value
    return ""


def enrich_from_latexml(state: ParseState) -> None:
    xml_path = state.tex_path.with_suffix(".latexml.xml")
    if not xml_path.exists():
        state.meta.warnings.append(f"missing_latexml_xml:{state.doc_id}")
        return
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError as exc:
        state.meta.warnings.append(f"latexml_parse_error:{state.doc_id}:{exc.__class__.__name__}")
        return

    xml_sections: list[str] = []
    xml_paragraphs: list[str] = []
    xml_refs: list[str] = []

    for node in root.iter():
        name = xml_local_name(node.tag)
        if name in {"section", "subsection"}:
            section_text = xml_child_text(node, {"title"}) or xml_node_text(node)
            if section_text:
                xml_sections.append(section_text)
        elif name in {"p", "para", "paragraph"}:
            paragraph_text = xml_node_text(node)
            if paragraph_text:
                xml_paragraphs.append(paragraph_text)
        elif name == "bibitem":
            text = xml_node_text(node)
            if text:
                state.meta.bibliography_entries.append(text)
        elif name in {"ref", "xref"}:
            label = ref_label_from_xml(node)
            if label:
                xml_refs.append(label)

    for bibliography in root.iter():
        if xml_local_name(bibliography.tag) == "bibliography":
            for item in bibliography:
                if xml_local_name(item.tag) in {"item", "bibitem"}:
                    text = xml_node_text(item)
                    if text and text not in state.meta.bibliography_entries:
                        state.meta.bibliography_entries.append(text)

    state.meta.latexml_checks = {
        "sections_checked": len(xml_sections),
        "paragraphs_checked": len(xml_paragraphs),
        "references_checked": len(xml_refs),
        "bibliography_entries": len(state.meta.bibliography_entries),
    }

    parsed_sections = set(state.section_titles)
    parsed_paragraphs = set(state.paragraph_texts)
    parsed_ref_labels = {ref["target_label"] for ref in state.meta.references}

    for section in xml_sections:
        if section not in parsed_sections:
            state.meta.warnings.append(f"latexml_section_mismatch:{section}")
    for paragraph in xml_paragraphs:
        if not any(paragraph == parsed or paragraph in parsed or parsed in paragraph for parsed in parsed_paragraphs):
            state.meta.warnings.append(f"latexml_paragraph_mismatch:{paragraph}")
    for label in xml_refs:
        if label not in state.meta.labels:
            state.meta.warnings.append(f"latexml_unresolved_ref:{label}")
        elif label not in parsed_ref_labels:
            state.meta.warnings.append(f"latexml_ref_not_in_tex:{label}")


def build_docling_from_tex(tex_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    tex = strip_comments(tex_path.read_text(encoding="utf-8"))
    doc_id = tex_path.parent.name
    meta = GroundtruthMeta(
        document_id=doc_id,
        source_tex=tex_path.as_posix(),
        source_sha256=sha256_text(tex),
    )
    state = ParseState(doc_id=doc_id, tex_path=tex_path, doc=DoclingDocument(name=doc_id), meta=meta)
    parse_blocks(state, strip_preamble(tex))
    resolve_references(meta)
    enrich_from_latexml(state)
    doc_dict = state.doc.export_to_dict()
    ordered_refs = set(meta.ordered_list_groups)
    for group in doc_dict.get("groups", []):
        if group.get("self_ref") in ordered_refs:
            group["label"] = "ordered_list"
    return doc_dict, meta.to_dict()


def discover_fixtures(corpus_root: Path, doc_id: str | None = None) -> list[Path]:
    if doc_id:
        candidate = corpus_root / doc_id / f"{doc_id}.tex"
        return [candidate] if candidate.exists() else []
    return sorted(path for path in corpus_root.glob("*/*.tex") if path.stem == path.parent.name)


def should_skip(tex_path: Path, json_path: Path, meta_path: Path, force: bool) -> bool:
    if force or not json_path.exists() or not meta_path.exists():
        return False
    try:
        old_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    tex_hash = sha256_text(strip_comments(tex_path.read_text(encoding="utf-8")))
    return old_meta.get("source_sha256") == tex_hash


def run(corpus_root: Path, doc_id: str | None = None, force: bool = False, verbose: bool = False) -> int:
    fixtures = discover_fixtures(corpus_root, doc_id)
    if doc_id and not fixtures:
        print(f"No fixture found for --doc {doc_id}", file=sys.stderr)
        return 2
    for tex_path in fixtures:
        out_json = tex_path.with_suffix(".docling.json")
        out_meta = tex_path.with_suffix(".docling_groundtruth_meta.json")
        if should_skip(tex_path, out_json, out_meta, force):
            if verbose:
                print(f"skip unchanged {tex_path.parent.name}")
            continue
        doc_dict, meta_dict = build_docling_from_tex(tex_path)
        out_json.write_text(json.dumps(doc_dict, indent=2) + "\n", encoding="utf-8")
        out_meta.write_text(json.dumps(meta_dict, indent=2) + "\n", encoding="utf-8")
        if verbose:
            warnings = ", ".join(meta_dict["warnings"]) or "none"
            print(f"wrote {tex_path.parent.name} warnings={warnings}")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert LaTeX corpus fixtures to DoclingDocument JSON ground truth.")
    parser.add_argument("--corpus-root", type=Path, default=Path("groundtruth/corpus/latex"))
    parser.add_argument("--doc", dest="doc_id", help="Only process a single fixture document id.")
    parser.add_argument("--force", action="store_true", help="Regenerate outputs even when the source hash is unchanged.")
    parser.add_argument("--verbose", action="store_true", help="Print per-document actions and warnings.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    return run(args.corpus_root, doc_id=args.doc_id, force=args.force, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
