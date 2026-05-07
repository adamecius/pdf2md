from __future__ import annotations

from pathlib import Path

from pdf2md.export.markdown import MarkdownExportSettings, build_markdown_preview
from pdf2md.models.linked import LinkedStructure

FIX = Path("tests/data/export_fixtures")


def load(name: str) -> LinkedStructure:
    return LinkedStructure.model_validate_json((FIX / name / "linked_structure.json").read_text())


def test_markdown_renders_simple_document_readably():
    md, warnings = build_markdown_preview(linked=load("simple_document"))
    assert "## Introduction" in md
    assert "This is the introduction." in md
    assert "[Figure]" not in md
    assert "*Figure 1. Example figure.*" in md
    assert warnings == []


def test_markdown_renders_rich_major_node_types_and_excludes_artifacts():
    md, _ = build_markdown_preview(linked=load("rich_document"))
    assert "# Rich Export Fixture" in md
    assert "1 Methods" in md
    assert "Table data" in md
    assert "```math\nE = mc^2\n```" in md
    assert "[^]: A clarifying footnote." in md
    assert "[1] Example Author" in md
    assert "Running header" not in md
    assert "\n\n1\n" not in md


def test_headers_footers_and_page_numbers_can_be_included():
    md, _ = build_markdown_preview(linked=load("rich_document"), settings=MarkdownExportSettings(include_page_numbers=True, include_headers_footers=True))
    assert "Running header" in md
    assert "\n\n1\n" in md


def test_unresolved_warning_and_unknown_render():
    md, warnings = build_markdown_preview(linked=load("unresolved_conflicts"))
    assert "<!-- unresolved:node:doc-conflict:2 -->" in md
    assert "<!-- unknown:node:doc-conflict:2 -->" in md
    assert any(w.startswith("unresolved_node_emitted") for w in warnings)

import pytest


@pytest.mark.parametrize("snippet", [
    "# Rich Export Fixture",
    "1 Methods ........ 1",
    "## Methods",
    "We describe a method",
    "Table data: alpha beta",
    "*Table 1. Example measurements.*",
    "Workflow diagram",
    "```math\nE = mc^2\n```",
    "[^]: A clarifying footnote.",
    "[1] Example Author. Example Work.",
])
def test_rich_markdown_contains_expected_snippets(snippet):
    md, _ = build_markdown_preview(linked=load("rich_document"))
    assert snippet in md
