"""Shared connector implementation for backend raw-output adapters."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

from pdf2md.models.entities import (
    ConfidenceSource,
    EntityEvidence,
    EntityProposal,
    EntityProposalDocument,
    EntityType,
    EvidenceKind,
    RelationProposal,
    RelationType,
    entity_id,
    relation_id,
)
from pdf2md.models.ir import BlockKind, ExtractionBlock, PageExtractionIR, PageSize, extraction_id


@dataclass(frozen=True)
class ConnectorResult:
    """Output of a single backend connector run.

    Attributes:
        pages: Per-page extraction IR derived from the backend's
            markdown.
        entities: Entity proposals recognised across all pages.
        warnings: Connector warnings (missing manifest, missing raw
            text, etc.).
    """

    pages: list[PageExtractionIR]
    entities: EntityProposalDocument
    warnings: list[str]


# Avoid a top-level import cycle: the semantic-layer schema lives under
# `pdf2md.models.cross_ref` and is only used by `SemanticConnectorResult`
# below — we re-export the name via a TYPE_CHECKING-guarded forward
# reference so existing `from pdf2md.connectors.common import ...`
# call-sites keep working.
from pdf2md.models.cross_ref import CrossReferenceGraph as _CrossReferenceGraph
from pdf2md.semantic.document_class import (
    classify_document as _classify_document,
)


@dataclass(frozen=True)
class SemanticConnectorResult:
    """Output of a single semantic-backend connector run.

    Parallels :class:`ConnectorResult` for the semantic layer. The
    return-type shape is intentionally different from the OCR
    `ConnectorResult` because the two layers cover different domains
    (extraction IR vs. cross-reference graph), but the ``warnings``
    field is identical so downstream code can handle both uniformly.

    Attributes:
        graph: The cross-reference graph the backend produced.
        warnings: Connector warnings (env_not_ready notes, model fell
            back to CPU, parse-error fallback to empty graph, etc.).
    """

    graph: _CrossReferenceGraph
    warnings: list[str]


@dataclass(frozen=True)
class BackendConnectorConfig:
    """Connector configuration for a single backend.

    Attributes:
        backend: Backend identifier (e.g. ``paddleocr``, ``deepseek``).
        default_backend_version: Version recorded when the raw manifest
            does not supply one.
        markdown_file_candidates: Filenames to probe for the backend's
            markdown output, in priority order.
        manifest_file_candidates: Filenames to probe for the backend's
            JSON manifest, in priority order.
    """

    backend: str
    default_backend_version: str | None
    markdown_file_candidates: tuple[str, ...] = ("output.md", "output.mmd", "result.md", "result.mmd")
    manifest_file_candidates: tuple[str, ...] = ("manifest.json", "status.json", "command.json")


def connect_raw_dir(
    *, raw_dir: Path, document_id: str, config: BackendConnectorConfig, out_dir: Path | None = None
) -> ConnectorResult:
    """Read a backend's raw output directory and produce connector IR.

    Discovers the markdown and manifest artefacts in ``raw_dir``, parses
    them into per-page extraction IR, recognises entities, and (if
    ``out_dir`` is given) writes the connector outputs to disk.

    Args:
        raw_dir: Directory containing the backend's raw markdown and
            manifest files.
        document_id: Stable identifier embedded in IR/entity IDs.
        config: Backend-specific connector configuration.
        out_dir: Optional output root; when provided, per-page IR and
            entities are written under ``<out_dir>/<backend>/``.

    Returns:
        A ConnectorResult holding pages, entities, and warnings.

    Raises:
        ValueError: If ``raw_dir`` does not exist or is not a directory.
    """
    raw_dir = Path(raw_dir)
    if not raw_dir.exists() or not raw_dir.is_dir():
        raise ValueError(f"raw_dir does not exist: {raw_dir}")
    warnings: list[str] = []
    manifest_path = _find_manifest(raw_dir, config)
    manifest = _read_manifest(manifest_path, warnings) if manifest_path else {}
    if manifest_path is None:
        warnings.append("manifest_missing")
    backend_version = manifest.get("backend_version") or config.default_backend_version
    markdown_path = _find_markdown(raw_dir, config)
    if markdown_path is None:
        warnings.append("raw_text_missing")
        pages: list[PageExtractionIR] = []
    else:
        text = markdown_path.read_text(encoding="utf-8")
        pages = markdown_to_pages(
            text,
            backend=config.backend,
            backend_version=backend_version,
            document_id=document_id,
            raw_ref=_relative(markdown_path, raw_dir),
            warnings=warnings,
        )
    entities = recognize_entities(
        pages, backend=config.backend, backend_version=backend_version, document_id=document_id, warnings=warnings
    )
    result = ConnectorResult(pages=pages, entities=entities, warnings=warnings)
    if out_dir is not None:
        write_connector_result(
            result=result, backend=config.backend, document_id=document_id, raw_dir=raw_dir, out_dir=Path(out_dir)
        )
    return result


def write_connector_result(
    *, result: ConnectorResult, backend: str, document_id: str, raw_dir: Path, out_dir: Path
) -> Path:
    """Persist a ConnectorResult under ``<out_dir>/<backend>/``.

    Writes one JSON file per page under ``pages/``, an ``entities.json``,
    and a top-level ``manifest.json`` referencing both.

    Args:
        result: ConnectorResult to serialise.
        backend: Backend identifier used as a subdirectory name.
        document_id: Document identifier recorded in the manifest.
        raw_dir: Raw input directory recorded in the manifest for
            traceability.
        out_dir: Output root that will contain ``<backend>/``.

    Returns:
        Path to the written ``manifest.json``.

    Raises:
        ValueError: If ``out_dir`` exists but is not a directory.
    """
    if out_dir.exists() and not out_dir.is_dir():
        raise ValueError(f"out_dir is not a directory: {out_dir}")
    target = out_dir / backend
    pages_dir = target / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    page_files: list[str] = []
    for page in result.pages:
        rel = Path("pages") / f"page_{page.page_no:04d}.json"
        (target / rel).write_text(page.model_dump_json(indent=2), encoding="utf-8")
        page_files.append(rel.as_posix())
    entity_file = "entities.json"
    (target / entity_file).write_text(result.entities.model_dump_json(indent=2), encoding="utf-8")
    manifest = {
        "schema_name": "pdf2md.ConnectorManifest",
        "schema_version": "1.0.0",
        "document_id": document_id,
        "backend": backend,
        "backend_version": result.entities.backend_version,
        "raw_dir": str(raw_dir),
        "page_count": len(result.pages),
        "page_ir_files": page_files,
        "entity_file": entity_file,
        "warnings": result.warnings,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    manifest_path = target / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


# Pre-compiled deepseek-OCR tag patterns. DeepSeek-OCR-2 prefixes every
# block with `<|ref|>tag<|/ref|><|det|>[[bbox]]<|/det|>\n<content>` where
# `tag` is one of title / sub_title / text / figure_title / image /
# equation / table / footnote / page-header / page-footer / list /
# list_item. We use these tags as the primary block-kind signal and
# strip the prefix from the block text so downstream text comparison is
# clean.
_DEEPSEEK_REF_RE = re.compile(r"<\|ref\|>([^<]+)<\|/ref\|>")
_DEEPSEEK_DET_RE = re.compile(r"<\|det\|>[^<]*<\|/det\|>")
_DEEPSEEK_TAG_TO_BLOCK_KIND: dict[str, BlockKind] = {
    "title": BlockKind.HEADING,
    "sub_title": BlockKind.HEADING,
    "section_header": BlockKind.HEADING,
    "text": BlockKind.PARAGRAPH,
    "paragraph": BlockKind.PARAGRAPH,
    "figure_title": BlockKind.CAPTION,
    "caption": BlockKind.CAPTION,
    "image": BlockKind.FIGURE,
    "figure": BlockKind.FIGURE,
    "equation": BlockKind.FORMULA,
    "formula": BlockKind.FORMULA,
    "table": BlockKind.TABLE,
    "list": BlockKind.LIST,
    "list_item": BlockKind.LIST_ITEM,
    "footnote": BlockKind.FOOTNOTE,
    "page-header": BlockKind.HEADER,
    "page_header": BlockKind.HEADER,
    "page-footer": BlockKind.FOOTER,
    "page_footer": BlockKind.FOOTER,
    "page_number": BlockKind.PAGE_NUMBER,
    "header": BlockKind.HEADER,
    "footer": BlockKind.FOOTER,
}


def _strip_deepseek_tags(chunk: str) -> tuple[str, str | None]:
    """Strip leading deepseek-OCR `<|ref|>` / `<|det|>` tags from a chunk.

    Returns (clean_text, ref_tag) — ``ref_tag`` is the value inside
    `<|ref|>...<|/ref|>`, lowercased, or None if no tag was found. The
    rest of any embedded `<|det|>` markers are also dropped so the block
    text doesn't carry bbox noise into text-overlap matching.
    """

    m = _DEEPSEEK_REF_RE.match(chunk.strip())
    if not m:
        return chunk, None
    tag = m.group(1).strip().lower()
    # Drop the leading ref tag and any det tag that follows on the same line.
    cleaned = _DEEPSEEK_REF_RE.sub("", chunk, count=1)
    cleaned = _DEEPSEEK_DET_RE.sub("", cleaned, count=1)
    return cleaned.strip(), tag


_BIB_LINE_RE = re.compile(r"^\[\d+\]\s+\S")


# Heading words that open a back-matter Index section. Lowercased.
_INDEX_HEADING_WORDS: frozenset[str] = frozenset({
    "index",
    "subject index",
    "name index",
    "author index",
})

# Heading words that open a back-matter Glossary section. Lowercased.
_GLOSSARY_HEADING_WORDS: frozenset[str] = frozenset({
    "glossary",
    "terms",
    "vocabulary",
    "glossary of terms",
})

# An index entry: ``Term, 5, 17–19, 42`` — term text followed by a
# comma-separated list of page numbers / page ranges. Page ranges accept
# ASCII ``-``, en-dash ``–``, em-dash ``—``. The term is everything
# before the first numeric page reference; we anchor on the comma that
# separates term from page list.
_INDEX_ENTRY_RE = re.compile(
    r"""^
    (?P<term>[^,\n]+?(?:\s*,\s*[^,\d\n]+)*)   # term (allows sub-clauses)
    \s*[,:]\s*                                # separator
    (?P<pages>\d+(?:\s*[-–—]\s*\d+)?
              (?:\s*,\s*\d+(?:\s*[-–—]\s*\d+)?)*)  # page list
    \s*$""",
    re.VERBOSE,
)

# A glossary entry — same shape as an index entry when the entry carries
# explicit page references, e.g. ``Conductivity, 3, 7``. Definition-only
# glossary entries (``Conductivity — property of a material...``) are
# captured by a looser pattern and emitted without page links.
_GLOSSARY_DEF_RE = re.compile(
    r"""^
    (?:\*\*(?P<term_bold>[^*\n]+)\*\*|(?P<term>[A-Za-z][A-Za-z0-9 _'\-]+?))
    \s*[:—–-]\s*
    (?P<definition>\S.+)
    $""",
    re.VERBOSE,
)


def _parse_index_pages(pages_text: str) -> list[int]:
    """Parse ``"5, 17-19, 42"`` into ``[5, 17, 18, 19, 42]``."""
    out: list[int] = []
    for chunk in pages_text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r"^(\d+)\s*[-–—]\s*(\d+)$", chunk)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b:
                out.extend(range(a, b + 1))
            else:
                out.append(a)
                out.append(b)
        elif chunk.isdigit():
            out.append(int(chunk))
    return out


def _separate_bracket_bib_entries(page_text: str) -> str:
    """Insert blank lines between adjacent ``[N] ...`` bibliography entries.

    Several OCR backends (mineru, paddleocr) emit bibliographies as a
    block of consecutive lines:

        [1] Author, Title, Journal, Year.
        [2] Another, Title, Journal, Year.
        ...

    The block-splitter below uses blank lines as paragraph boundaries,
    so the whole bib ends up as a single paragraph. The downstream
    footnote / reference-item detector then only matches the first
    ``[N]`` line, leaving the remaining 50+ entries invisible. Inserting
    a blank line between adjacent bib entries puts one entry per block
    instead.

    Heuristic — only act inside a *bib run* (a stretch of lines that has
    already produced at least one ``[N]\\s+\\S`` line and hasn't been
    broken by a blank line). This catches:

    * canonical ``[1] ... \\n [2] ...`` adjacency, and
    * wrapped entries (``[31] long title that wraps\\n more wrap\\n
      [32] ...``) — the second ``[N]`` line gets separated even though
      the immediately preceding line is the wrap of the previous entry.

    Lines that don't start with ``[N]`` between bib entries are kept
    inside the preceding entry's block (wraps).
    Single ``[N]`` lines outside a bib run (e.g. ``[2] is also true``
    as a one-off sentence in body text) are NOT split — only the second
    and subsequent ``[N]`` lines within a non-blank-separated stretch
    are.
    """
    lines = page_text.splitlines(keepends=False)
    n = len(lines)
    out: list[str] = []
    in_bib_run = False
    for i, line in enumerate(lines):
        if _BIB_LINE_RE.match(line):
            if in_bib_run and out and out[-1] != "":
                out.append("")
            in_bib_run = True
            out.append(line)
        elif not line.strip():
            # Blank line. Only EXIT the bib run if no further ``[N]``
            # entry shows up within the next ~3 non-blank lines. This
            # tolerates OCR backends that wedge a blank between the
            # hyphen-break and continuation of a single bib entry
            # (``...Ul-\\n\\nrich Schollwock...``).
            ahead_bib = False
            seen_nonblank = 0
            for j in range(i + 1, n):
                lj = lines[j]
                if not lj.strip():
                    continue
                seen_nonblank += 1
                if _BIB_LINE_RE.match(lj):
                    ahead_bib = True
                    break
                if seen_nonblank >= 3:
                    break
            if not ahead_bib:
                in_bib_run = False
            out.append(line)
        else:
            # Non-blank, non-``[N]`` line — likely a wrap of the
            # previous bib entry; keep ``in_bib_run`` so the next
            # ``[N]`` still gets separated.
            out.append(line)
    return "\n".join(out)


# Plan 17 A5 — inline image extraction.
# Matches a single `<img ... src="...">` (self-closing or non-) and
# captures the src URL. The full tag, optionally wrapped in
# `<div>...</div>`, is what gets lifted out.
_INLINE_IMG_RE = re.compile(
    r"(?:<div\b[^>]*>\s*)?"                  # optional wrapping <div>
    r"<img\b[^>]*?\bsrc\s*=\s*(?P<q>[\"'])(?P<src>[^\"']+)(?P=q)[^>]*?/?>"
    r"(?:\s*</div>)?",                       # optional closing </div>
    flags=re.IGNORECASE,
)
# A block that consists ENTIRELY of one lifted `<img>` HTML fragment
# — the marker `_separate_inline_images` writes so the block-creation
# loop can re-route it to a FIGURE block with the right metadata.
_IMG_BLOCK_RE = re.compile(
    r"^\s*<img\b[^>]*?\bsrc\s*=\s*[\"'](?P<src>[^\"']+)[\"'][^>]*?/?>\s*$",
    flags=re.IGNORECASE,
)


# Plan 17 A4 — footnote post-processing patterns.
# Inline `\footnote{...}` LaTeX residual. The body inside the braces
# is what becomes a separate FOOTNOTE block; the host paragraph keeps
# a clean anchor in its place.
_LATEX_FOOTNOTE_RE = re.compile(
    r"\\footnote\s*\{(?P<body>[^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
)
# Numbered footnote line that looks like "1. some body" or "[1] body"
# sitting alone in a block at the bottom of the page. Conservative: a
# block whose entire content matches this pattern is rewritten as
# a FOOTNOTE only when it sits in the bottom third of the page's
# block list.
_NUMBERED_FOOTNOTE_LINE_RE = re.compile(r"^\s*(?P<marker>\d+)\s*[. ]\s+(?P<body>\S.*)$", re.S)


def _extract_footnote_blocks(
    blocks: list[ExtractionBlock],
    *,
    backend: str,
    document_id: str,
    page_no: int,
    raw_ref: str | None,
) -> list[ExtractionBlock]:
    """Pull footnote content out of paragraph blocks into FOOTNOTE blocks.

    Two patterns handled:

    1. **LaTeX residual** — ``\\footnote{...}`` inside a paragraph.
       The braced body becomes its own FOOTNOTE block; the host
       paragraph keeps a clean ``[^N]`` marker in place of the macro.
    2. **Bottom-of-page numbered footnotes** — a paragraph in the
       bottom third of the page whose entire content matches
       ``N. ...`` and that lives after at least one non-trivial
       paragraph. These get retagged FOOTNOTE in place (no host
       paragraph to clean).

    Returns the (possibly extended) block list with stable monotonic
    ``order`` values.
    """
    if not blocks:
        return blocks
    out: list[ExtractionBlock] = []
    next_marker = 1
    n_blocks = len(blocks)
    bottom_start = max(1, (2 * n_blocks) // 3)
    for idx, block in enumerate(blocks):
        text = block.text or ""
        # (1) LaTeX `\footnote{...}` residual inside any block kind.
        if "\\footnote" in text and (matches := list(_LATEX_FOOTNOTE_RE.finditer(text))):
            new_text = text
            new_footnotes: list[tuple[str, str]] = []  # (marker, body)
            for m in matches:
                marker = str(next_marker)
                next_marker += 1
                new_footnotes.append((marker, m.group("body").strip()))
                new_text = new_text.replace(m.group(0), f"[^{marker}]", 1)
            out.append(
                block.model_copy(
                    update={
                        "text": new_text,
                        "metadata": {
                            **(block.metadata or {}),
                            "footnote_anchors": [m for m, _ in new_footnotes],
                        },
                    }
                )
            )
            for marker, body in new_footnotes:
                out.append(
                    ExtractionBlock(
                        id=extraction_id(backend, document_id, page_no, len(out)),
                        backend=backend,
                        page_no=page_no,
                        kind=BlockKind.FOOTNOTE,
                        order=len(out),
                        text=body,
                        raw_ref=raw_ref,
                        metadata={
                            "footnote_marker": marker,
                            "footnote_host_block_id": block.id,
                            "footnote_source": "latex_command",
                        },
                    )
                )
            continue
        # (2) Bottom-of-page numbered footnote line. Operates on
        # PARAGRAPH and LIST_ITEM blocks — PaddleOCR's `1. body` style
        # footnotes get classified as LIST_ITEM by the upstream
        # markdown classifier, but at the bottom of the page they are
        # almost always footnotes, not list items.
        if (
            block.kind in {BlockKind.PARAGRAPH, BlockKind.LIST_ITEM}
            and idx >= bottom_start
            and (fm := _NUMBERED_FOOTNOTE_LINE_RE.match(text.strip()))
        ):
            # Require at least one preceding non-trivial paragraph on
            # the page so we don't retag the very first line.
            has_prior_paragraph = any(
                b.kind == BlockKind.PARAGRAPH and len((b.text or "").strip()) > 30
                for b in blocks[:idx]
            )
            if has_prior_paragraph:
                out.append(
                    block.model_copy(
                        update={
                            "kind": BlockKind.FOOTNOTE,
                            "metadata": {
                                **(block.metadata or {}),
                                "footnote_marker": fm.group("marker"),
                                "footnote_source": "bottom_of_page_number",
                            },
                        }
                    )
                )
                continue
        out.append(block)
    # Re-mint ids + order so the sequence stays contiguous after
    # any insertions / kind changes.
    return [
        block.model_copy(
            update={
                "id": extraction_id(backend, document_id, page_no, new_order),
                "order": new_order,
            }
        )
        for new_order, block in enumerate(out)
    ]


def _separate_inline_images(page_text: str) -> str:
    """Lift each inline ``<img src=...>`` (or ``<div><img/></div>``) into
    its own block by surrounding it with blank lines.

    The block-creation loop afterwards reads any line that is purely
    ``<img src="..."/>`` as a standalone figure (see :data:`_IMG_BLOCK_RE`).
    Wrapped ``<div>`` containers and any leading whitespace are stripped.
    """
    def _repl(m: re.Match[str]) -> str:
        return f"\n\n<img src=\"{m.group('src')}\"/>\n\n"
    return _INLINE_IMG_RE.sub(_repl, page_text)


def markdown_to_pages(
    text: str, *, backend: str, backend_version: str | None, document_id: str, raw_ref: str | None, warnings: list[str]
) -> list[PageExtractionIR]:
    """Split backend markdown into per-page extraction IR with blocks.

    Splits on the known page markers emitted by the supported backends
    (PaddleOCR-style ``<--- Page Split --->`` and ``<!-- pagebreak -->``,
    DeepSeek-style ``<!-- page N -->``, and form feed), then breaks each
    page on blank lines to form blocks and classifies each block via
    :func:`classify_block`. Appends ``raw_text_missing`` /
    ``page_size_missing`` warnings as appropriate.

    Args:
        text: Raw markdown emitted by the backend.
        backend: Backend identifier embedded in block IDs.
        backend_version: Optional version stamp recorded on each page.
        document_id: Document identifier embedded in IDs.
        raw_ref: Optional relative path to the source markdown, recorded
            on every block.
        warnings: Mutable warning list that this function appends to.

    Returns:
        One PageExtractionIR per detected page; empty if ``text`` is
        empty.
    """
    if not text.strip():
        warnings.append("raw_text_missing")
        return []
    warnings.append("page_size_missing")
    # Page split markers we know about:
    #   - paddleocr-style "<--- Page Split --->" / "<!-- pagebreak -->" / form-feed
    #   - deepseek-style "<!-- page N -->" (one per page, inclusive of page 1)
    chunks = re.split(r"<---\s*Page Split\s*--->|\f|<!--\s*pagebreak\s*-->|<!--\s*page\s+\d+\s*-->", text, flags=re.I)
    # Drop the leading empty chunk that appears when text starts with a marker
    # (e.g. deepseek emits `<!-- page 1 -->` at the very top).
    chunks = [c for c in chunks if c.strip()]
    pages: list[PageExtractionIR] = []
    for page_no, page_text in enumerate(chunks, start=1):
        page_text = _separate_bracket_bib_entries(page_text)
        # Plan 17 A5 — pull inline `<img>` HTML out of paragraph
        # text into standalone FIGURE blocks. Done before block
        # splitting so each image lands as its own paragraph (and
        # therefore its own block via the existing blank-line split).
        page_text = _separate_inline_images(page_text)
        blocks = []
        order_counter = 0
        for chunk in [c.strip() for c in re.split(r"\n\s*\n", page_text) if c.strip()]:
            # Detect image-only blocks emitted by _separate_inline_images.
            img_match = _IMG_BLOCK_RE.match(chunk)
            if img_match:
                blocks.append(
                    ExtractionBlock(
                        id=extraction_id(backend, document_id, page_no, order_counter),
                        backend=backend,
                        page_no=page_no,
                        kind=BlockKind.FIGURE,
                        order=order_counter,
                        text=chunk,
                        raw_ref=raw_ref,
                        metadata={
                            "image_src": img_match.group("src"),
                            "image_origin": "inline_html",
                        },
                    )
                )
                order_counter += 1
                continue
            cleaned, ref_tag = _strip_deepseek_tags(chunk)
            kind, metadata = classify_block(cleaned, ref_tag=ref_tag)
            blocks.append(
                ExtractionBlock(
                    id=extraction_id(backend, document_id, page_no, order_counter),
                    backend=backend,
                    page_no=page_no,
                    kind=kind,
                    order=order_counter,
                    text=cleaned,
                    raw_ref=raw_ref,
                    metadata=metadata,
                )
            )
            order_counter += 1
        # Plan 17 A4 — footnote post-processing. Operates on the
        # constructed block list so it can both inspect block order
        # and emit new FOOTNOTE blocks.
        blocks = _extract_footnote_blocks(
            blocks,
            backend=backend,
            document_id=document_id,
            page_no=page_no,
            raw_ref=raw_ref,
        )
        pages.append(
            PageExtractionIR(
                document_id=document_id,
                backend=backend,
                backend_version=backend_version,
                page_no=page_no,
                page_size=PageSize(width=1.0, height=1.0),
                blocks=blocks,
                raw_artifact_ref=raw_ref,
                metadata={"connector": "markdown_fallback"},
            )
        )
    return pages


def classify_block(text: str, *, ref_tag: str | None = None) -> tuple[BlockKind, dict[str, Any]]:
    """Infer a BlockKind for a markdown chunk.

    If a DeepSeek ``<|ref|>`` tag was stripped upstream, the tag is
    consulted first. Otherwise the chunk is matched against markdown
    heuristics for headings, formulas, tables, figures, captions, and
    list items, with PARAGRAPH as the fallback.

    Args:
        text: Block text after page-split processing.
        ref_tag: Optional lowercased DeepSeek reference tag (e.g.
            ``title``, ``equation``).

    Returns:
        ``(kind, metadata)`` where ``metadata`` may carry
        ``markdown_heading_level`` or ``source_tag``.
    """
    if ref_tag is not None:
        mapped = _DEEPSEEK_TAG_TO_BLOCK_KIND.get(ref_tag)
        if mapped is not None:
            metadata: dict[str, Any] = {"source_tag": ref_tag}
            if mapped == BlockKind.HEADING:
                first = text.strip().splitlines()[0].strip() if text.strip() else ""
                if m := re.match(r"^(#{1,6})\s+(.+)$", first):
                    metadata["markdown_heading_level"] = len(m.group(1))
                elif ref_tag == "title":
                    metadata["markdown_heading_level"] = 1
                elif ref_tag == "sub_title":
                    metadata["markdown_heading_level"] = 2
            return mapped, metadata
    text_stripped = text.strip()
    lines = text_stripped.splitlines() if text_stripped else []
    first = lines[0].strip() if lines else ""

    # Markdown `#` headings — existing behaviour.
    if m := re.match(r"^(#{1,6})\s+(.+)$", first):
        return BlockKind.HEADING, {
            "markdown_heading_level": len(m.group(1)),
            "heading_source": "markdown_hash",
        }
    # HTML `<h1>...</h6>` headings (Plan 17 A3) — PaddleOCR
    # PP-StructureV3 emits headings as `<h1>Title</h1>` blocks.
    if m := re.match(r"^\s*<h([1-6])\b[^>]*>(.*?)</h\1>\s*$", text_stripped, re.I | re.S):
        return BlockKind.HEADING, {
            "markdown_heading_level": int(m.group(1)),
            "heading_source": "html_tag",
        }
    # LaTeX residual headings (Plan 17 A3) — `\section{...}` /
    # `\subsection{...}` / `\subsubsection{...}` / `\chapter{...}`.
    if m := re.match(r"^\\(chapter|section|subsection|subsubsection|paragraph|subparagraph)\b\*?\s*\{(.+?)\}", first):
        kw = m.group(1).lower()
        level = {
            "chapter": 1,
            "section": 1,
            "subsection": 2,
            "subsubsection": 3,
            "paragraph": 4,
            "subparagraph": 5,
        }[kw]
        return BlockKind.HEADING, {
            "markdown_heading_level": level,
            "heading_source": "latex_command",
        }
    if re.search(r"^\\\[.*\\\]$", text_stripped, re.S) or re.search(r"\$\$.*\$\$", text_stripped, re.S):
        return BlockKind.FORMULA, {}
    if re.search(r"<table\b.*?</table>", text_stripped, re.I | re.S):
        return BlockKind.TABLE, {}
    if re.match(r"!\[[^\]]*\]\([^)]+\)", first):
        return BlockKind.FIGURE, {}
    if re.match(r"^(Figure|Fig\.|Table)\s+\d+[\.:]?.*", first, re.I):
        return BlockKind.CAPTION, {}
    if re.match(r"^([-*+]\s+|\d+[.)]\s+)", first):
        return BlockKind.LIST_ITEM, {}
    # Formatting-heuristic heading (Plan 17 A3) — a SHORT single line
    # that's mostly upper-case or title-case, with no trailing
    # punctuation, sitting alone as its own block. Conservative
    # thresholds because false positives here mis-tag body lines:
    #   * single line only (block has 1 line of content)
    #   * 2..12 words
    #   * no trailing colon / period / comma / semicolon
    #   * either ALL CAPS or every non-stopword word starts uppercase
    if len(lines) == 1 and 6 <= len(first) <= 80 and not re.search(r"[.,:;!?]$", first):
        words = first.split()
        if 2 <= len(words) <= 12:
            letters = [c for c in first if c.isalpha()]
            upper_ratio = (sum(1 for c in letters if c.isupper()) / len(letters)) if letters else 0
            title_case = all(w[0].isupper() or w.lower() in _HEADING_STOPWORDS for w in words if w)
            if upper_ratio >= 0.85 or title_case:
                return BlockKind.HEADING, {
                    "markdown_heading_level": 2,
                    "heading_source": "formatting_heuristic",
                }
    return BlockKind.PARAGRAPH, {}


# Title-case heading detection ignores these (they may be lower-case
# inside a heading like "On the Theory of Groups").
_HEADING_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "and", "as", "at", "but", "by", "de", "for", "from", "in",
    "of", "on", "or", "the", "to", "via", "vs", "with",
})


def recognize_entities(
    pages: list[PageExtractionIR], *, backend: str, backend_version: str | None, document_id: str, warnings: list[str]
) -> EntityProposalDocument:
    """Recognise entities and relations across all pages of a document.

    Applies the markdown-fallback heuristic detectors (sections, TOC
    entries, page numbers, footnotes/reference items, equations,
    captions, figures, tables, headers, footers) and emits adjacency,
    caption, TOC, and sequence relations.

    Args:
        pages: Per-page extraction IR produced by
            :func:`markdown_to_pages`.
        backend: Backend identifier embedded in entity/relation IDs.
        backend_version: Optional backend version recorded on the
            document.
        document_id: Document identifier embedded in IDs.
        warnings: Warning list propagated to the resulting document.

    Returns:
        An EntityProposalDocument with proposed entities, relations,
        and the input warnings.
    """
    entities: list[EntityProposal] = []
    idx = 0

    def add(
        entity_type: EntityType,
        block: ExtractionBlock,
        confidence: float,
        detector: str,
        *,
        subtype: str | None = None,
        metadata: dict[str, Any] | None = None,
        evidence_kind: EvidenceKind = EvidenceKind.BLOCK_TEXT,
        canonical_text: str | None = None,
    ) -> EntityProposal:
        """Append a new EntityProposal anchored on ``block`` and return it.

        ``canonical_text`` may be supplied to override the entity's
        canonical text (default: ``_strip_heading(block.text)``). Use
        this when one block contains multiple list-shaped entries —
        e.g. an index paragraph holding ``Hall, 5\\nBerry, 12`` — and
        each entry should carry its own line text rather than the full
        block.
        """
        nonlocal idx
        idx += 1
        md = {"detector": detector, **(metadata or {})}
        ev = EntityEvidence(
            kind=evidence_kind,
            page_no=block.page_no,
            source_block_id=block.id,
            raw_ref=block.raw_ref,
            text=block.text,
            bbox=block.bbox,
            weight=1.0,
            reason=detector,
            metadata={},
        )
        ent = EntityProposal(
            id=entity_id(backend, document_id, entity_type, idx),
            entity_type=entity_type,
            subtype=subtype,
            canonical_text=canonical_text if canonical_text is not None else _strip_heading(block.text),
            page_no=block.page_no,
            block_ids=[block.id],
            confidence=confidence,
            confidence_source=ConfidenceSource.HEURISTIC,
            evidence=[ev],
            calibration_key=f"{backend}:{entity_type.value}:{detector}",
            metadata=md,
        )
        entities.append(ent)
        return ent

    refs_started = False
    index_started = False
    glossary_started = False
    # Track the heading level that activated each back-matter section so
    # we can close it cleanly when a same-or-higher-level heading appears.
    index_heading_level: int | None = None
    glossary_heading_level: int | None = None
    for page in pages:
        for pos, block in enumerate(page.blocks):
            text = block.text.strip()
            plain = _strip_heading(text)
            lower = plain.lower()
            if block.kind == BlockKind.HEADING:
                heading_level = block.metadata.get("markdown_heading_level")
                numbering = _numbering(plain)
                # Close back-matter sections when a same-or-higher-level
                # heading appears (mirrors how a new top-level heading
                # ends a Bibliography in practice).
                if index_started and heading_level is not None and index_heading_level is not None and heading_level <= index_heading_level and lower not in _INDEX_HEADING_WORDS:
                    index_started = False
                    index_heading_level = None
                if glossary_started and heading_level is not None and glossary_heading_level is not None and heading_level <= glossary_heading_level and lower not in _GLOSSARY_HEADING_WORDS:
                    glossary_started = False
                    glossary_heading_level = None
                add(
                    EntityType.SECTION,
                    block,
                    0.75,
                    "heading_section_detector",
                    metadata={
                        "heading_level": heading_level,
                        "numbering": numbering,
                    },
                )
                # Chapter detection — fires on either:
                #   (a) explicit "Chapter N" prefix (matches \chapter{...} in
                #       LaTeX books and most non-LaTeX book conventions), or
                #   (b) an H1-level heading with a leading top-level number
                #       (e.g. "1 Overview", "5 Conclusions") on documents
                #       that use H1 for chapters.
                # We emit CHAPTER *in addition to* SECTION so existing
                # consumers that look for SECTION on every heading keep
                # working; semantic-layer resolvers that want chapter
                # anchors can filter on entity_type=CHAPTER.
                chapter_match = re.match(r"^chapter\s+([ivxlcdm0-9]+(?:\.\d+)*)\b", lower)
                is_h1_top_level = (
                    heading_level == 1
                    and numbering is not None
                    and "." not in numbering
                )
                if chapter_match or is_h1_top_level:
                    chapter_number = (
                        chapter_match.group(1) if chapter_match else numbering
                    )
                    add(
                        EntityType.CHAPTER,
                        block,
                        0.80 if chapter_match else 0.65,
                        "chapter_detector",
                        metadata={
                            "chapter_number": chapter_number,
                            "heading_level": heading_level,
                            "numbering": numbering,
                            "match": "keyword" if chapter_match else "h1_top_level",
                        },
                    )
                if lower in {"references", "bibliography", "works cited"}:
                    refs_started = True
                    add(EntityType.REFERENCE_SECTION, block, 0.88, "reference_section_detector")
                if lower in _INDEX_HEADING_WORDS:
                    index_started = True
                    index_heading_level = heading_level
                    add(EntityType.INDEX_SECTION, block, 0.88, "index_section_detector")
                if lower in _GLOSSARY_HEADING_WORDS:
                    glossary_started = True
                    glossary_heading_level = heading_level
                    add(EntityType.GLOSSARY_SECTION, block, 0.88, "glossary_section_detector")
            # TOC entries — iterate per line so multi-entry TOC blocks
            # (which arrive fused on most OCR backends) each emit their
            # own TOC_ENTRY anchored on the parent block.
            for toc_line in plain.splitlines():
                tl = toc_line.strip()
                if not tl:
                    continue
                if m := re.match(r"^(.+?)\s+\.{3,}\s+(\d+)\s*$", tl):
                    add(
                        EntityType.TOC_ENTRY,
                        block,
                        0.74,
                        "toc_entry_detector",
                        metadata={
                            "target_page_candidate": int(m.group(2)),
                            "target_title_candidate": m.group(1).strip(),
                        },
                        canonical_text=tl,
                    )
            # Index entries — iterate per line for the same reason.
            if index_started and block.kind == BlockKind.PARAGRAPH and plain:
                for line in plain.splitlines():
                    line_s = line.strip()
                    if not line_s:
                        continue
                    idx_m = _INDEX_ENTRY_RE.match(line_s)
                    if not idx_m:
                        continue
                    pages_list = _parse_index_pages(idx_m.group("pages"))
                    if not pages_list:
                        continue
                    add(
                        EntityType.INDEX_ENTRY,
                        block,
                        0.72,
                        "index_entry_detector",
                        metadata={
                            "index_term": idx_m.group("term").strip(),
                            "index_pages": pages_list,
                        },
                        canonical_text=line_s,
                    )
            # Glossary entries — same per-line iteration. Two shapes
            # accepted, tried in order per line; only ONE emits per
            # line:
            #   (a) ``Term, 5, 17-19`` — index-style with explicit pages.
            #   (b) ``Term: definition...`` / ``**Term** — definition...``
            #       — definition-only entry, no page list.
            if glossary_started and block.kind == BlockKind.PARAGRAPH and plain:
                for line in plain.splitlines():
                    line_s = line.strip()
                    if not line_s:
                        continue
                    emitted_glossary = False
                    if (idx_m := _INDEX_ENTRY_RE.match(line_s)) is not None:
                        pages_list = _parse_index_pages(idx_m.group("pages"))
                        if pages_list:
                            add(
                                EntityType.GLOSSARY_ENTRY,
                                block,
                                0.72,
                                "glossary_entry_detector",
                                metadata={
                                    "glossary_term": idx_m.group("term").strip(),
                                    "glossary_pages": pages_list,
                                    "has_page_list": True,
                                },
                                canonical_text=line_s,
                            )
                            emitted_glossary = True
                    if not emitted_glossary:
                        def_m = _GLOSSARY_DEF_RE.match(line_s)
                        if def_m:
                            term = (def_m.group("term_bold") or def_m.group("term") or "").strip()
                            definition = def_m.group("definition").strip()
                            if term and definition:
                                add(
                                    EntityType.GLOSSARY_ENTRY,
                                    block,
                                    0.65,
                                    "glossary_entry_detector",
                                    metadata={
                                        "glossary_term": term,
                                        "glossary_definition": definition,
                                        "has_page_list": False,
                                    },
                                    canonical_text=line_s,
                                )
            if re.fullmatch(r"\d+|[ivxlcdm]+", lower) and (pos == 0 or pos == len(page.blocks) - 1):
                add(EntityType.PAGE_NUMBER, block, 0.68, "page_number_detector", evidence_kind=EvidenceKind.POSITION)
            if m := re.match(r"^(?:\[(\d+)\]|(\d+)\.|([¹²³]))\s+.+", plain):
                marker = next(g for g in m.groups() if g)
                add(
                    EntityType.FOOTNOTE if not refs_started else EntityType.REFERENCE_ITEM,
                    block,
                    0.70,
                    "footnote_detector" if not refs_started else "reference_item_detector",
                    metadata={"marker": marker},
                )
            elif refs_started and block.kind == BlockKind.PARAGRAPH and plain:
                add(EntityType.REFERENCE_ITEM, block, 0.62, "reference_item_detector")
            # Equation detection. Two failure modes the old version had:
            #   1) Bibliography entries like "[14] Smith, ... 2020." end
            #      with "(2020)" and got mis-tagged as equations.
            #   2) Real `\[ ... \]` math blocks rarely contain their
            #      printed equation number — that lives in the next
            #      block (often as a standalone "(11)" paragraph).
            # Guard against (1) and look at the next block for (2).
            is_bib_entry = bool(re.match(r"^\[\s*\d+\s*\]\s+\S", plain))
            if not is_bib_entry and (
                block.kind == BlockKind.FORMULA
                or re.search(r"\([0-9]+(?:\.[0-9]+)*\)\s*$", plain)
            ):
                num = (re.search(r"\(([0-9]+(?:\.[0-9]+)*)\)\s*$", plain) or [None, None])[1]
                if num is None and block.kind == BlockKind.FORMULA:
                    # DeepSeek emits ``\[ math \quad (N) \]`` — the
                    # ``(N)`` sits inside the LaTeX delimiters before
                    # the closing ``\]``. Look for the rightmost
                    # ``(N)`` in the block, optionally followed by
                    # ``\]`` / whitespace / end-of-text.
                    inner = re.search(
                        r"\(([0-9]+(?:\.[0-9]+)*)\)\s*\\?\]?\s*$",
                        plain,
                    )
                    if inner:
                        num = inner.group(1)
                    # LaTeX `\tag{N}` form — emitted by some VLM /
                    # docling outputs of authored equations.
                    if num is None:
                        tag_m = re.search(r"\\tag\{([0-9]+(?:\.[0-9]+)*)\}", plain)
                        if tag_m:
                            num = tag_m.group(1)
                # FORMULA blocks without trailing (N): peek at the next
                # block on the same page. If it BEGINS with a "(N)" or
                # is just "(N)" alone, attribute that number here.
                if num is None and block.kind == BlockKind.FORMULA and pos + 1 < len(page.blocks):
                    next_plain = _strip_heading(page.blocks[pos + 1].text).strip()
                    nm = re.match(r"^\(?([0-9]+(?:\.[0-9]+)*)\)?(?:\s|$)", next_plain)
                    if nm:
                        num = nm.group(1)
                add(
                    EntityType.EQUATION,
                    block,
                    0.76,
                    "equation_detector",
                    metadata={"equation_number": num, "sequence_key": f"equation:{num}" if num else None},
                )
            if block.kind == BlockKind.CAPTION:
                # Preserve chapter-relative numbering ("Figure 3.2" stays
                # "3.2" — losing it to "3" makes the semantic-layer
                # resolver mis-target on long books).
                cm = re.match(r"^(Figure|Fig\.|Table)\s+(\d+(?:\.\d+)*)", plain, re.I)
                kind = "table" if cm and cm.group(1).lower().startswith("table") else "figure"
                add(
                    EntityType.CAPTION,
                    block,
                    0.78,
                    "caption_detector",
                    metadata={"caption_kind": kind, "caption_number": cm.group(2) if cm else None},
                )
            if block.kind == BlockKind.FIGURE:
                add(EntityType.FIGURE, block, 0.82, "figure_table_detector")
            if block.kind == BlockKind.TABLE:
                add(EntityType.TABLE, block, 0.82, "figure_table_detector")
    entities.extend(_header_footer_entities(pages, backend, document_id, idx))

    # Post-pass: detect an *implicit* bibliography — a contiguous tail
    # run of "[N] author..." paragraphs that the main loop misclassified
    # as FOOTNOTE because no "References" / "Bibliography" heading
    # appeared above them. Common on arXiv physics + CS preprints that
    # drop the heading. Re-tags the affected entities in place and emits
    # a synthetic REFERENCE_SECTION anchored on the first one.
    next_idx = _detect_implicit_bibliography(
        entities=entities,
        pages=pages,
        backend=backend,
        document_id=document_id,
        next_id_index=idx + 1,
    )
    if next_idx is not None:
        idx = next_idx

    relations = _relations(entities, backend, document_id)

    # Document-class classification (Plan 7) — runs after every other
    # detector so it sees the full entity set, including the Plan 6
    # Index / Glossary sections and the implicit-bibliography
    # promotions. The result is written to metadata so downstream
    # stages (ensemble mixer, semantic backends) can adapt without
    # re-deriving the classification.
    classification = _classify_document(
        EntityProposalDocument(
            document_id=document_id,
            backend=backend,
            backend_version=backend_version,
            page_count=len(pages),
            entities=entities,
            relations=relations,
            warnings=warnings,
            metadata={},
        ),
        pages,
    )

    return EntityProposalDocument(
        document_id=document_id,
        backend=backend,
        backend_version=backend_version,
        page_count=len(pages),
        entities=entities,
        relations=relations,
        warnings=warnings,
        metadata={
            "connector": "markdown_fallback",
            "document_class": classification.document_class.value,
            "document_class_confidence": classification.confidence,
            "document_class_features": classification.features,
        },
    )


# Minimum size of a contiguous run of "[N]" paragraphs to be treated
# as an implicit bibliography. 5 strikes a balance: bibliographies are
# almost always ≥5 entries, while an incidental short footnote cluster
# in body text stays under the threshold.
IMPLICIT_BIBLIOGRAPHY_MIN_RUN = 5

# How much of the longest ascending sequence must be sequential to
# count as a bibliography (e.g. 1,2,3,4,5 → 1.0; 1,2,4,5,7 → 0.66).
# Real bibliographies are typically near-perfect ascending integers.
IMPLICIT_BIBLIOGRAPHY_MIN_ASCENDING_FRACTION = 0.80


def _detect_implicit_bibliography(
    *,
    entities: list[EntityProposal],
    pages: list[PageExtractionIR],
    backend: str,
    document_id: str,
    next_id_index: int,
) -> int | None:
    """Re-tag the longest ascending sequential run of FOOTNOTE entities as REFERENCE_ITEM.

    Many arXiv preprints and conference PDFs ship a bibliography that
    begins with ``[1] Author, ...`` and has **no** "References" or
    "Bibliography" heading above it. The single-pass detector in
    :func:`recognize_entities` only flips ``refs_started`` on an
    explicit heading, so these papers' bib entries get tagged as
    :class:`EntityType.FOOTNOTE`. The semantic-layer bridge then maps
    them to :class:`RefType.FOOTNOTE`, leaving every ``[N]``
    bibliography marker emitted by GROBID / regex / VLM with no
    candidate to resolve against.

    This post-pass identifies the bibliography by its **shape**: a
    contiguous run of FOOTNOTE entities whose markers form an
    ascending integer sequence (1, 2, 3, …). Real bibliographies are
    long and near-perfectly sequential; legitimate footnote clusters
    in body text rarely run more than 2–3 deep and don't reset to 1.

    The previous "last 30 % of pages" heuristic was too restrictive —
    on documents where the OCR doesn't emit page breaks, all entities
    live on one synthesized page, and a bibliography on page 5 of 10
    would be invisible to a tail-only check.

    Steps when a qualifying run is found:

    1. Re-tag each entity in the run from FOOTNOTE → REFERENCE_ITEM
       (with audit-trail metadata).
    2. Emit a synthetic REFERENCE_SECTION anchored on the first entity.

    Args:
        entities: All entities so far, in detection order. Mutated in
            place; new REFERENCE_SECTION (if any) is appended.
        pages: The page IR — kept for anchoring the synthetic
            REFERENCE_SECTION on a real block.
        backend: Backend id for entity_id minting.
        document_id: Document id for entity_id minting.
        next_id_index: The next free idx to use when minting the new
            REFERENCE_SECTION entity.

    Returns:
        The updated idx after any new entity has been emitted, or
        ``None`` if no implicit bibliography was found.
    """
    if not pages or not entities:
        return None

    def _is_bracket_footnote(ent: EntityProposal) -> bool:
        """A FOOTNOTE entity whose source text starts with ``[``.

        Body numbered lists use ``1.`` form; bibliographies use ``[1]``.
        Restricting to the bracket form keeps the detector specific to
        the bibliography shape.
        """
        if _entity_type_value(ent) != EntityType.FOOTNOTE.value:
            return False
        if ent.metadata.get("detector") != "footnote_detector":
            return False
        text = (ent.canonical_text or "").lstrip()
        return text.startswith("[")

    # Walk entities, find every maximal run of consecutive bracket-form
    # FOOTNOTE entities. Entities are in detection order so consecutive
    # in the list = consecutive in the document.
    runs: list[tuple[int, int]] = []
    i = 0
    while i < len(entities):
        if _is_bracket_footnote(entities[i]):
            j = i
            while j + 1 < len(entities) and _is_bracket_footnote(entities[j + 1]):
                j += 1
            if j - i + 1 >= IMPLICIT_BIBLIOGRAPHY_MIN_RUN:
                runs.append((i, j))
            i = j + 1
        else:
            i += 1

    if not runs:
        return None

    # Keep every run whose markers form an ascending integer sequence
    # above the threshold. OCR backends occasionally capture the same
    # bibliography twice (page-1 dual-column + page-2 single-column
    # extracts of the same References block), producing two separate
    # ascending runs. Promoting only the longest leaves the duplicate
    # copy as FOOTNOTE, hiding 12+ valid candidates from the resolver.
    qualifying: list[tuple[int, int]] = []
    for start, end in runs:
        run = entities[start : end + 1]
        try:
            nums = [int(e.metadata.get("marker", "")) for e in run]
        except (TypeError, ValueError):
            continue
        if not nums:
            continue
        ascending = sum(1 for a, b in pairwise(nums) if b == a + 1)
        ascending_pairs_max = len(nums) - 1
        if ascending_pairs_max == 0:
            continue
        ascending_fraction = ascending / ascending_pairs_max
        if ascending_fraction >= IMPLICIT_BIBLIOGRAPHY_MIN_ASCENDING_FRACTION:
            qualifying.append((start, end))

    if not qualifying:
        return None

    # Re-tag every entity in every qualifying run.
    for start, end in qualifying:
        for ent in entities[start : end + 1]:
            # Pydantic v2 models are mutable by default unless frozen.
            ent.entity_type = EntityType.REFERENCE_ITEM
            ent.metadata = {
                **ent.metadata,
                "detector": "implicit_bibliography_detector",
                "previous_detector": "footnote_detector",
            }
            ent.calibration_key = f"{backend}:{EntityType.REFERENCE_ITEM.value}:implicit_bibliography_detector"

    # Anchor the synthetic REFERENCE_SECTION on the LONGEST qualifying
    # run's first entity — there's one canonical bibliography section
    # even when the OCR captured it twice.
    longest_run = max(qualifying, key=lambda r: r[1] - r[0])
    run = entities[longest_run[0] : longest_run[1] + 1]
    first = run[0]
    first_block_id = first.block_ids[0] if first.block_ids else None
    # Find the block from pages by id (we kept block_ids in detection order).
    anchor_block: ExtractionBlock | None = None
    for page in pages:
        for b in page.blocks:
            if b.id == first_block_id:
                anchor_block = b
                break
        if anchor_block is not None:
            break
    if anchor_block is None:
        return next_id_index  # ran but couldn't anchor; entities still re-tagged

    md = {
        "detector": "implicit_bibliography_detector",
        "trigger": "tail_run_of_numbered_paragraphs",
        "run_size": len(run),
        "qualifying_runs": len(qualifying),
    }
    evidence = EntityEvidence(
        kind=EvidenceKind.POSITION,
        page_no=anchor_block.page_no,
        source_block_id=anchor_block.id,
        raw_ref=anchor_block.raw_ref,
        text=anchor_block.text,
        bbox=anchor_block.bbox,
        weight=1.0,
        reason="implicit_bibliography_detector",
        metadata={},
    )
    entities.append(
        EntityProposal(
            id=entity_id(backend, document_id, EntityType.REFERENCE_SECTION, next_id_index),
            entity_type=EntityType.REFERENCE_SECTION,
            subtype=None,
            canonical_text=_strip_heading(anchor_block.text),
            page_no=anchor_block.page_no,
            block_ids=[anchor_block.id],
            confidence=0.70,  # lower than the explicit-heading detector (0.88)
            confidence_source=ConfidenceSource.HEURISTIC,
            evidence=[evidence],
            calibration_key=f"{backend}:{EntityType.REFERENCE_SECTION.value}:implicit_bibliography_detector",
            metadata=md,
        )
    )
    return next_id_index + 1


def _entity_type_value(ent: EntityProposal) -> str:
    """Return the entity_type as a plain string regardless of pydantic mode."""
    et = ent.entity_type
    return et.value if hasattr(et, "value") else str(et)


def _relations(entities: list[EntityProposal], backend: str, document_id: str) -> list[RelationProposal]:
    relations: list[RelationProposal] = []
    by_page: dict[int, list[EntityProposal]] = {}
    for ent in entities:
        if ent.page_no is not None:
            by_page.setdefault(ent.page_no, []).append(ent)
    for ents in by_page.values():
        for i, ent in enumerate(ents[:-1]):
            nxt = ents[i + 1]
            if (ent.entity_type == EntityType.CAPTION and nxt.entity_type in {EntityType.FIGURE, EntityType.TABLE}) or (
                nxt.entity_type == EntityType.CAPTION and ent.entity_type in {EntityType.FIGURE, EntityType.TABLE}
            ):
                relations.append(
                    _rel(
                        backend,
                        document_id,
                        len(relations) + 1,
                        RelationType.CAPTION_OF,
                        ent,
                        nxt,
                        0.55,
                        "adjacent caption and media",
                    )
                )
            relations.append(
                _rel(backend, document_id, len(relations) + 1, RelationType.NEAR, ent, nxt, 0.25, "adjacent entities")
            )
    sections = [e for e in entities if e.entity_type == EntityType.SECTION]
    chapters = [e for e in entities if e.entity_type == EntityType.CHAPTER]
    section_like = sections + chapters
    sections_by_page: dict[int, list[EntityProposal]] = {}
    for sec in section_like:
        if sec.page_no is not None:
            sections_by_page.setdefault(sec.page_no, []).append(sec)
    for toc in [e for e in entities if e.entity_type == EntityType.TOC_ENTRY]:
        # Title-text match (existing behaviour).
        target_title = str(toc.metadata.get("target_title_candidate", "")).lower()
        matched_by_title = False
        for sec in sections:
            title = str(sec.canonical_text or "").lower()
            if title and (title in target_title or target_title in title or _tokens_overlap(title, target_title)):
                relations.append(
                    _rel(
                        backend,
                        document_id,
                        len(relations) + 1,
                        RelationType.TOC_POINTS_TO,
                        toc,
                        sec,
                        0.50,
                        "toc title matches section",
                        extra_metadata={"match_strategy": "heading_text"},
                    )
                )
                matched_by_title = True
                break
        # Page-number match (formalised in Plan 6). Independent of title
        # match — we want both edges when both apply, since a downstream
        # consumer can filter by match_strategy.
        target_page = toc.metadata.get("target_page_candidate")
        if isinstance(target_page, int):
            for sec in sections_by_page.get(target_page, []):
                # Skip if the same edge already came in via the title path.
                if matched_by_title and any(
                    r.source_entity_id == toc.id and r.target_entity_id == sec.id
                    for r in relations
                ):
                    continue
                relations.append(
                    _rel(
                        backend,
                        document_id,
                        len(relations) + 1,
                        RelationType.TOC_POINTS_TO,
                        toc,
                        sec,
                        0.55,
                        "toc target page matches section page",
                        extra_metadata={"match_strategy": "page"},
                    )
                )

    # Index entries — emit one TOC_POINTS_TO edge per (page-match) AND
    # per (heading-text-match). Per Plan 6, "more relations is better"
    # so we don't dedupe between the two strategies — each carries a
    # distinct match_strategy tag.
    for idx_entry in [e for e in entities if e.entity_type == EntityType.INDEX_ENTRY]:
        term = str(idx_entry.metadata.get("index_term", "")).lower().strip()
        # Page-number match.
        for page_no in idx_entry.metadata.get("index_pages", []) or []:
            for sec in sections_by_page.get(int(page_no), []):
                relations.append(
                    _rel(
                        backend,
                        document_id,
                        len(relations) + 1,
                        RelationType.TOC_POINTS_TO,
                        idx_entry,
                        sec,
                        0.60,
                        "index entry page matches section page",
                        extra_metadata={
                            "match_strategy": "page",
                            "index_target_page": int(page_no),
                        },
                    )
                )
        # Heading-text match — case-insensitive substring in either
        # direction. Catches ``Hall effect, 5, 17`` → ``# Hall effect``.
        if term:
            for sec in section_like:
                title = str(sec.canonical_text or "").lower().strip()
                if title and (title in term or term in title):
                    relations.append(
                        _rel(
                            backend,
                            document_id,
                            len(relations) + 1,
                            RelationType.TOC_POINTS_TO,
                            idx_entry,
                            sec,
                            0.55,
                            "index term matches section title",
                            extra_metadata={
                                "match_strategy": "heading_text",
                                "index_term": term,
                            },
                        )
                    )

    # Glossary entries — emit one GLOSSARY_DEFINES edge per (body block
    # on a page explicitly listed in the entry). No substring scan of
    # the body for term occurrences (Plan 6 §3.3).
    for gl_entry in [e for e in entities if e.entity_type == EntityType.GLOSSARY_ENTRY]:
        if not gl_entry.metadata.get("has_page_list"):
            continue
        for page_no in gl_entry.metadata.get("glossary_pages", []) or []:
            for body_block in by_page.get(int(page_no), []):
                # Skip linking to back-matter / structural entities.
                if body_block.entity_type in {
                    EntityType.GLOSSARY_ENTRY,
                    EntityType.GLOSSARY_SECTION,
                    EntityType.INDEX_ENTRY,
                    EntityType.INDEX_SECTION,
                    EntityType.REFERENCE_ITEM,
                    EntityType.REFERENCE_SECTION,
                    EntityType.PAGE_NUMBER,
                    EntityType.HEADER,
                    EntityType.FOOTER,
                    EntityType.TOC_ENTRY,
                }:
                    continue
                relations.append(
                    _rel(
                        backend,
                        document_id,
                        len(relations) + 1,
                        RelationType.GLOSSARY_DEFINES,
                        gl_entry,
                        body_block,
                        0.55,
                        "glossary entry references this page",
                        extra_metadata={
                            "glossary_target_page": int(page_no),
                            "glossary_term": gl_entry.metadata.get("glossary_term"),
                        },
                    )
                )

    sequence_groups = [
        [e for e in entities if e.entity_type == EntityType.EQUATION],
        [e for e in entities if e.entity_type == EntityType.CAPTION and e.metadata.get("caption_kind") == "figure"],
        [e for e in entities if e.entity_type == EntityType.CAPTION and e.metadata.get("caption_kind") == "table"],
        [e for e in entities if e.entity_type == EntityType.REFERENCE_ITEM],
    ]
    for seq in sequence_groups:
        numbered_raw: list[tuple[EntityProposal, tuple[int, ...] | None]] = [
            (entity, _sequence_number(entity)) for entity in seq
        ]
        numbered: list[tuple[EntityProposal, tuple[int, ...]]] = [
            (entity, number) for entity, number in numbered_raw if number is not None
        ]
        for (a, a_number), (b, b_number) in pairwise(numbered):
            if _numbers_are_consecutive(a_number, b_number):
                relations.append(
                    _rel(
                        backend,
                        document_id,
                        len(relations) + 1,
                        RelationType.SEQUENCE_NEXT,
                        a,
                        b,
                        0.45,
                        "consecutive numbered sequence",
                    )
                )
    return relations


def _rel(
    backend: str,
    document_id: str,
    index: int,
    rtype: RelationType,
    source: EntityProposal,
    target: EntityProposal,
    confidence: float,
    reason: str,
    extra_metadata: dict[str, Any] | None = None,
) -> RelationProposal:
    ev = EntityEvidence(
        kind=EvidenceKind.DOCUMENT_CONTEXT,
        page_no=source.page_no,
        source_block_id=source.block_ids[0] if source.block_ids else None,
        raw_ref=None,
        text=None,
        bbox=None,
        weight=1.0,
        reason=reason,
        metadata={},
    )
    md: dict[str, Any] = {"detector": f"{rtype.value}_detector"}
    if extra_metadata:
        md.update(extra_metadata)
    return RelationProposal(
        id=relation_id(backend, document_id, index),
        relation_type=rtype,
        source_entity_id=source.id,
        target_entity_id=target.id,
        confidence=confidence,
        confidence_source=ConfidenceSource.HEURISTIC,
        evidence=[ev],
        metadata=md,
    )


def _sequence_number(entity: EntityProposal) -> tuple[int, ...] | None:
    value = None
    if entity.entity_type == EntityType.EQUATION:
        value = entity.metadata.get("equation_number")
    elif entity.entity_type == EntityType.CAPTION:
        value = entity.metadata.get("caption_number")
    elif entity.entity_type == EntityType.REFERENCE_ITEM:
        value = entity.metadata.get("marker")
    if value is None:
        return None
    text = str(value).strip()
    if not re.fullmatch(r"\d+(?:\.\d+)*", text):
        return None
    return tuple(int(part) for part in text.split("."))


def _numbers_are_consecutive(first: tuple[int, ...], second: tuple[int, ...]) -> bool:
    if len(first) != len(second):
        return False
    if first[:-1] != second[:-1]:
        return False
    return second[-1] == first[-1] + 1


def _header_footer_entities(
    pages: list[PageExtractionIR], backend: str, document_id: str, start: int
) -> list[EntityProposal]:
    if len(pages) < 2:
        return []
    out: list[EntityProposal] = []
    for pos, etype, detector in [
        (0, EntityType.HEADER, "header_footer_detector"),
        (-1, EntityType.FOOTER, "header_footer_detector"),
    ]:
        values: dict[str, list[ExtractionBlock]] = {}
        for page in pages:
            if page.blocks:
                b = page.blocks[pos]
                if len(b.text.strip()) <= 80:
                    values.setdefault(b.text.strip(), []).append(b)
        for text, blocks in values.items():
            if text and len(blocks) >= 2:
                for block in blocks:
                    start += 1
                    ev = EntityEvidence(
                        kind=EvidenceKind.POSITION,
                        page_no=block.page_no,
                        source_block_id=block.id,
                        raw_ref=block.raw_ref,
                        text=block.text,
                        bbox=None,
                        weight=1.0,
                        reason=detector,
                        metadata={},
                    )
                    out.append(
                        EntityProposal(
                            id=entity_id(backend, document_id, etype, start),
                            entity_type=etype,
                            canonical_text=text,
                            page_no=block.page_no,
                            block_ids=[block.id],
                            confidence=0.52,
                            confidence_source=ConfidenceSource.HEURISTIC,
                            evidence=[ev],
                            calibration_key=f"{backend}:{etype.value}:{detector}",
                            metadata={"detector": detector},
                        )
                    )
    return out


def _find_markdown(raw_dir: Path, config: BackendConnectorConfig) -> Path | None:
    for name in config.markdown_file_candidates:
        candidate = raw_dir / name
        if candidate.is_file():
            return candidate
    matches = sorted([*raw_dir.glob("*.md"), *raw_dir.glob("*.mmd")])
    return matches[0] if len(matches) == 1 else None


def _find_manifest(raw_dir: Path, config: BackendConnectorConfig) -> Path | None:
    for name in config.manifest_file_candidates:
        candidate = raw_dir / name
        if candidate.is_file():
            return candidate
    return None


def _read_manifest(path: Path, warnings: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        warnings.append("manifest_invalid")
        return {}


def _relative(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def _strip_heading(text: str) -> str:
    return re.sub(r"^#{1,6}\s+", "", text.strip())


def _numbering(text: str) -> str | None:
    m = re.match(r"^(\d+(?:\.\d+)*)\s+", text)
    return m.group(1) if m else None


def _tokens_overlap(a: str, b: str) -> bool:
    aset = set(re.findall(r"[a-z0-9]+", a.lower()))
    bset = set(re.findall(r"[a-z0-9]+", b.lower()))
    return bool(aset and bset and len(aset & bset) / max(len(aset), len(bset)) >= 0.5)
