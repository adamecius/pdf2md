"""Ground-truth generation for the semantic layer.

Runs the system ``latexml`` binary on a ``.tex`` source, parses the
emitted LaTeXML XML, and returns a :class:`CrossReferenceGraph` with
``backend="ground_truth"`` and unit confidence on every entry.

LaTeXML emits its native XML in the ``http://dlmf.nist.gov/LaTeXML``
namespace (not TEI). This parser handles that namespace directly. The
``<ref labelref="LABEL:xxx"/>`` cross-references are matched against
``labels="LABEL:xxx"`` anchors on ``<figure>`` / ``<table>`` /
``<equation>`` / ``<section>`` / ``<bibitem>`` elements to recover the
resolved cross-reference graph.

LaTeXML is a read-only external tool — the agent does not install it.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

from pdf2md.models.cross_ref import (
    CROSS_REF_SCHEMA_VERSION,
    CrossReferenceGraph,
    RefEdge,
    RefMarker,
    RefType,
    SemanticEntity,
)

BACKEND_NAME = "ground_truth"
BACKEND_VERSION = "0.1.0"
LATEXML_NS = "http://dlmf.nist.gov/LaTeXML"
_NS = {"l": LATEXML_NS}


class LatexMLUnavailableError(RuntimeError):
    """Raised when the ``latexml`` binary is not on ``$PATH``.

    Callers (the benchmark CLI) catch this and exit 3 with a clean
    ``env_not_ready`` message, matching the Plan 005/006 convention.
    """


# Map LaTeXML element tags to canonical RefType slugs.
# Used both to classify anchors (figure → FIGURE) and to type the markers
# pointing at them.
_TAG_TO_REF_TYPE: dict[str, RefType] = {
    "figure": RefType.FIGURE,
    "table": RefType.TABLE,
    "equation": RefType.EQUATION,
    "section": RefType.SECTION,
    "subsection": RefType.SECTION,
    "subsubsection": RefType.SECTION,
    "chapter": RefType.CHAPTER,
    "theorem": RefType.THEOREM,
    "definition": RefType.DEFINITION,
    "proof": RefType.PROOF,
    "corollary": RefType.COROLLARY,
    "example": RefType.EXAMPLE,
    "bibitem": RefType.BIBLIOGRAPHY,
    "note": RefType.FOOTNOTE,
}


def _xml_id(elem: ET.Element) -> str | None:
    return elem.attrib.get("{http://www.w3.org/XML/1998/namespace}id")


def _doc_hash_from_tex(tex_path: Path) -> str:
    sha = hashlib.sha256()
    with tex_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(chunk)
    return "sha256:" + sha.hexdigest()


def _ensure_latexml(latexml_bin: str) -> str:
    """Return the absolute path to ``latexml`` or raise."""
    resolved = shutil.which(latexml_bin)
    if resolved is None:
        raise LatexMLUnavailableError(
            f"latexml binary not found on PATH (looked for {latexml_bin!r})"
        )
    return resolved


def _run_latexml(
    tex_path: Path,
    output_dir: Path,
    latexml_bin: str,
    timeout_s: int,
) -> Path:
    """Run ``latexml`` and write XML to ``output_dir/<stem>.latexml.xml``."""
    bin_path = _ensure_latexml(latexml_bin)
    output_dir.mkdir(parents=True, exist_ok=True)
    xml_path = output_dir / f"{tex_path.stem}.latexml.xml"
    try:
        result = subprocess.run(
            [bin_path, f"--dest={xml_path}", str(tex_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"latexml timed out after {timeout_s}s on {tex_path}") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"latexml failed on {tex_path} (exit {result.returncode}): "
            f"{result.stderr.strip()[:500]}"
        )
    if not xml_path.is_file():
        raise RuntimeError(
            f"latexml exited 0 but did not produce {xml_path}"
        )
    return xml_path


def _strip_ns(tag: str) -> str:
    """Strip the namespace from ``{ns}tag``."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _tag_to_ref_type(local_tag: str) -> RefType | None:
    return _TAG_TO_REF_TYPE.get(local_tag.lower())


def _collect_anchors(root: ET.Element) -> dict[str, tuple[RefType, str, str]]:
    """Walk the LaTeXML tree and collect labelled anchors.

    Returns:
        Map ``LABEL:foo → (RefType, xml_id, surface_label)``. The
        ``surface_label`` is the visible tag (e.g. ``"Figure 1"``,
        ``"Section 1.1"``) extracted from the ``<tag>`` siblings when
        available; falls back to the bare element id.
    """
    anchors: dict[str, tuple[RefType, str, str]] = {}
    for elem in root.iter():
        labels = elem.attrib.get("labels")
        if not labels:
            continue
        local = _strip_ns(elem.tag)
        ref_type = _tag_to_ref_type(local)
        if ref_type is None:
            continue
        anchor_id = _xml_id(elem) or labels.replace(":", "_")
        # LaTeXML emits one or more <tag role="..."> elements; the role
        # "autoref" carries the human-readable surface form.
        surface_label = anchor_id
        tags_parent = elem.find(f"{{{LATEXML_NS}}}tags")
        if tags_parent is not None:
            autoref = None
            for tag in tags_parent.findall(f"{{{LATEXML_NS}}}tag"):
                role = tag.attrib.get("role")
                if role == "autoref" and tag.text:
                    autoref = tag.text.strip()
                    break
            if autoref:
                surface_label = autoref

        for label_value in labels.split():
            anchors[label_value] = (ref_type, anchor_id, surface_label)
    return anchors


def _collect_markers(
    root: ET.Element,
    anchors: dict[str, tuple[RefType, str, str]],
) -> tuple[list[tuple[RefType, str, str | None]], list[tuple[RefType, str]]]:
    """Walk the tree and collect (marker_type, marker_text, target).

    Targets reference the labelref attribute on ``<ref>`` elements when
    that label is present in ``anchors``. Unknown labels yield markers
    with ``target=None`` (resolved=False).
    """
    markers: list[tuple[RefType, str, str | None]] = []

    for ref in root.iter(f"{{{LATEXML_NS}}}ref"):
        labelref = ref.attrib.get("labelref")
        target_id: str | None = None
        marker_type: RefType | None = None
        anchor_surface: str | None = None
        if labelref:
            hit = anchors.get(labelref)
            if hit is not None:
                marker_type, target_id, anchor_surface = hit
        # Prefer the rendered ref text (when LaTeXML emits one), then the
        # resolved anchor's surface form (e.g. "Figure 1"), then the bare
        # labelref minus its LABEL: prefix.
        text = (ref.text or "").strip()
        if not text and anchor_surface:
            text = anchor_surface
        if not text:
            text = labelref.replace("LABEL:", "") if labelref else "ref"
        if marker_type is None:
            ref_type_attr = ref.attrib.get("type", "")
            marker_type = _tag_to_ref_type(ref_type_attr) or RefType.SECTION
        markers.append((marker_type, text, target_id))

    # <cite> elements → bibliography markers. LaTeXML emits one <cite>
    # per \cite{} call, with <bibref bibrefs="key">.
    for cite in root.iter(f"{{{LATEXML_NS}}}cite"):
        text = (cite.text or "").strip() or _inner_text(cite)
        if not text:
            text = "cite"
        # bibrefs may point to bibitems; capture the first key as target.
        target_id = None
        bibref = cite.find(f"{{{LATEXML_NS}}}bibref")
        if bibref is not None:
            keys = bibref.attrib.get("bibrefs", "").split(",")
            if keys:
                target_id = keys[0].strip() or None
        markers.append((RefType.BIBLIOGRAPHY, text, target_id))

    # <note role="footnote"> → footnote markers (already labelled with
    # numeric autoref tags).
    biblio_entries: list[tuple[RefType, str]] = []
    for note in root.iter(f"{{{LATEXML_NS}}}note"):
        if note.attrib.get("role") != "footnote":
            continue
        note_id = _xml_id(note) or "footnote"
        # Surface form: the numeric refnum tag if present, else the id.
        surface = note_id
        tags_parent = note.find(f"{{{LATEXML_NS}}}tags")
        if tags_parent is not None:
            for tag in tags_parent.findall(f"{{{LATEXML_NS}}}tag"):
                if tag.attrib.get("role") == "autoref" and tag.text:
                    surface = tag.text.strip()
                    break
        markers.append((RefType.FOOTNOTE, surface, note_id))

    # <bibitem> elements collect into entities.
    for bibitem in root.iter(f"{{{LATEXML_NS}}}bibitem"):
        biblio_entries.append((RefType.BIBLIOGRAPHY, _xml_id(bibitem) or ""))

    return markers, biblio_entries


def _inner_text(elem: ET.Element) -> str:
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(_inner_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(p.strip() for p in parts if p and p.strip())


def _build_markers_and_edges(
    raw_markers: list[tuple[RefType, str, str | None]],
    source_ref: str,
) -> tuple[list[RefMarker], list[RefEdge]]:
    body_text = " ".join(text for _, text, _ in raw_markers)

    markers: list[RefMarker] = []
    edges: list[RefEdge] = []
    cursor = 0
    for marker_type, text, target_id in raw_markers:
        start = body_text.find(text, cursor)
        if start < 0:
            start = 0
        end = start + len(text)
        cursor = end
        marker = RefMarker(
            source_ref=source_ref,
            marker_text=text,
            marker_type=marker_type,
            char_offset=(start, end),
            confidence=1.0,
            backend=BACKEND_NAME,
        )
        markers.append(marker)
        if target_id:
            edges.append(
                RefEdge(
                    marker=marker,
                    target_ref=f"#{target_id}",
                    resolved=True,
                    resolution_method="grobid_tei",
                )
            )
        else:
            edges.append(
                RefEdge(
                    marker=marker,
                    target_ref=None,
                    resolved=False,
                    resolution_method="unresolved",
                )
            )
    return markers, edges


def generate_ground_truth(
    tex_path: Path,
    output_dir: Path,
    *,
    latexml_bin: str = "latexml",
    timeout_s: int = 300,
    source_ref: str = "#/document",
) -> CrossReferenceGraph:
    """Generate a :class:`CrossReferenceGraph` from a ``.tex`` source.

    Args:
        tex_path: Path to a LaTeX source file. Must exist.
        output_dir: Working directory; ``latexml`` writes XML here.
        latexml_bin: Override the binary name (e.g. for tests with a
            mocked PATH).
        timeout_s: Subprocess timeout for the ``latexml`` invocation.
        source_ref: JSON pointer stamped on every emitted marker.

    Returns:
        A :class:`CrossReferenceGraph` with ``backend="ground_truth"``.

    Raises:
        FileNotFoundError: If ``tex_path`` does not exist.
        LatexMLUnavailableError: If ``latexml`` is not on PATH.
        RuntimeError: If ``latexml`` exits non-zero or produces no output.
        ValueError: If the produced XML is not valid.
    """
    if not tex_path.is_file():
        raise FileNotFoundError(f"tex_path not found: {tex_path}")

    xml_path = _run_latexml(tex_path, output_dir, latexml_bin, timeout_s)
    xml_body = xml_path.read_text(encoding="utf-8")
    try:
        root = ET.fromstring(xml_body)
    except ET.ParseError as exc:
        raise ValueError(f"invalid LaTeXML XML: {exc}") from exc

    anchors = _collect_anchors(root)
    raw_markers, biblio_entries = _collect_markers(root, anchors)
    markers, edges = _build_markers_and_edges(raw_markers, source_ref)

    entities: list[SemanticEntity] = []
    for ref_type, ref_id in biblio_entries:
        item_ref = f"#/bibliography/{ref_id}" if ref_id else f"#/bibliography/anon-{len(entities)}"
        entities.append(
            SemanticEntity(
                item_ref=item_ref,
                entity_type=ref_type,
                label=ref_id or None,
                confidence=1.0,
                backend=BACKEND_NAME,
            )
        )

    return CrossReferenceGraph(
        schema_version=CROSS_REF_SCHEMA_VERSION,
        doc_hash=_doc_hash_from_tex(tex_path),
        markers=markers,
        edges=edges,
        entities=entities,
        backend_versions={BACKEND_NAME: BACKEND_VERSION},
    )


__all__ = [
    "BACKEND_NAME",
    "BACKEND_VERSION",
    "LatexMLUnavailableError",
    "generate_ground_truth",
]
