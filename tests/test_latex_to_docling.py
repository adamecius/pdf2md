import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from docling_core.types.doc import DoclingDocument

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.latex_to_docling import build_docling_from_tex, run


def write_fixture(tmp_path: Path, doc_id: str, tex: str) -> Path:
    fixture = tmp_path / doc_id
    fixture.mkdir()
    tex_path = fixture / f"{doc_id}.tex"
    tex_path.write_text(tex, encoding="utf-8")
    return tex_path


def labels(doc):
    return [item["label"] for item in doc["texts"]]


def texts(doc):
    return [item["text"] for item in doc["texts"]]


def test_title_and_paragraph_parse_to_valid_docling_document(tmp_path):
    tex_path = write_fixture(
        tmp_path,
        "simple",
        r"""
        \documentclass{article}
        \title{A Test Title}
        \begin{document}
        \maketitle
        This is the first paragraph.
        \end{document}
        """,
    )

    doc, meta = build_docling_from_tex(tex_path)

    DoclingDocument.model_validate(doc)
    assert doc["name"] == "simple"
    assert labels(doc)[:2] == ["title", "text"]
    assert texts(doc)[:2] == ["A Test Title", "This is the first paragraph."]
    assert meta["document_id"] == "simple"
    assert "missing_latexml_xml:simple" in meta["warnings"]


def test_section_hierarchy_and_starred_variants(tmp_path):
    tex_path = write_fixture(
        tmp_path,
        "sections",
        r"""
        \begin{document}
        \section*{Overview}\label{sec:overview}
        Parent text.
        \subsection{Details}
        Child text.
        \end{document}
        """,
    )

    doc, meta = build_docling_from_tex(tex_path)

    headers = [item for item in doc["texts"] if item["label"] == "section_header"]
    assert [header["text"] for header in headers] == ["Overview", "Details"]
    assert headers[0]["level"] == 1
    assert headers[1]["level"] == 2
    assert headers[1]["parent"]["$ref"] == headers[0]["self_ref"]
    assert meta["labels"]["sec:overview"] == headers[0]["self_ref"]


def test_equation_extraction_and_cross_reference_resolution(tmp_path):
    tex_path = write_fixture(
        tmp_path,
        "equations",
        r"""
        \begin{document}
        \section{Math}
        See Equation \ref{eq:energy}.
        \begin{equation}
        E = mc^2 \label{eq:energy}
        \end{equation}
        Inline $a+b=c$ math.
        \end{document}
        """,
    )

    doc, meta = build_docling_from_tex(tex_path)

    formulas = [item for item in doc["texts"] if item["label"] == "formula"]
    assert [item["text"] for item in formulas] == ["E = mc^2", "a+b=c"]
    assert meta["labels"]["eq:energy"] == formulas[0]["self_ref"]
    assert meta["references"] == [
        {
            "source_ref": "#/texts/1",
            "target_label": "eq:energy",
            "resolved_ref": formulas[0]["self_ref"],
        }
    ]


def test_table_cell_grid_figure_caption_and_sidecar_pointers(tmp_path):
    tex_path = write_fixture(
        tmp_path,
        "floats",
        r"""
        \begin{document}
        \begin{figure}
        \fbox{diagram}
        \caption{Box diagram}\label{fig:box}
        \end{figure}
        Figure \ref{fig:box} and Table \ref{tab:data} are related.
        \begin{table}
        \caption{Data table}\label{tab:data}
        \begin{tabular}{cc}
        A & B \\
        1 & 2
        \end{tabular}
        \end{table}
        \end{document}
        """,
    )

    doc, meta = build_docling_from_tex(tex_path)

    assert doc["pictures"][0]["captions"][0]["$ref"] == "#/texts/0"
    table = doc["tables"][0]
    assert table["data"]["num_rows"] == 2
    assert table["data"]["num_cols"] == 2
    assert [cell["text"] for cell in table["data"]["table_cells"]] == ["A", "B", "1", "2"]
    assert meta["labels"]["fig:box"] == "#/pictures/0"
    assert meta["labels"]["tab:data"] == "#/tables/0"
    for pointer in list(meta["labels"].values()) + [rel["target_ref"] for rel in meta["caption_relations"]]:
        assert pointer.startswith(("#/texts/", "#/pictures/", "#/tables/"))


def test_nested_lists_and_footnotes(tmp_path):
    tex_path = write_fixture(
        tmp_path,
        "lists",
        r"""
        \begin{document}
        Intro before the note\footnote{A note body}.
        \begin{enumerate}
        \item First
        \item Second
          \begin{itemize}
          \item Nested
          \end{itemize}
        \end{enumerate}
        \end{document}
        """,
    )

    doc, meta = build_docling_from_tex(tex_path)

    assert [group["label"] for group in doc["groups"]] == ["ordered_list", "list"]
    assert meta["ordered_list_groups"] == ["#/groups/0"]
    list_items = [item for item in doc["texts"] if item["label"] == "list_item"]
    assert [item["text"] for item in list_items] == ["First", "Second", "Nested"]
    assert any(item["label"] == "footnote" and item["text"] == "A note body" for item in doc["texts"])
    assert meta["footnote_anchors"][0]["footnote_ref"].startswith("#/texts/")


def test_unknown_environment_and_command_warn_without_exception(tmp_path):
    tex_path = write_fixture(
        tmp_path,
        "unknowns",
        r"""
        \begin{document}
        \begin{mystery}
        Hidden content.
        \end{mystery}
        \mysterycmd{Skipped content.}
        \end{document}
        """,
    )

    doc, meta = build_docling_from_tex(tex_path)

    DoclingDocument.model_validate(doc)
    assert "unknown_environment:mystery" in meta["warnings"]
    assert "unknown_command:mysterycmd" in meta["warnings"]


def test_hash_gating_skips_unchanged_outputs_and_force_regenerates(tmp_path):
    write_fixture(
        tmp_path,
        "gated",
        r"""\begin{document}First version.\end{document}""",
    )

    assert run(tmp_path, force=False) == 0
    out_json = tmp_path / "gated" / "gated.docling.json"
    first_mtime = out_json.stat().st_mtime_ns

    time.sleep(0.01)
    assert run(tmp_path, force=False) == 0
    assert out_json.stat().st_mtime_ns == first_mtime

    time.sleep(0.01)
    assert run(tmp_path, force=True) == 0
    assert out_json.stat().st_mtime_ns > first_mtime


def test_latexml_enrichment_checks_sections_paragraphs_refs_and_bibliography(tmp_path):
    tex_path = write_fixture(
        tmp_path,
        "xml_doc",
        r"""
        \begin{document}
        \section{Intro}\label{sec:intro}
        See Section \ref{sec:intro}.
        Body paragraph.
        \end{document}
        """,
    )
    tex_path.with_suffix(".latexml.xml").write_text(
        """
        <document>
          <section><title>Intro</title></section>
          <p>Body paragraph.</p>
          <ref labelref="sec:intro">Section 1</ref>
          <bibitem>Smith 2024.</bibitem>
        </document>
        """,
        encoding="utf-8",
    )

    _, meta = build_docling_from_tex(tex_path)

    assert meta["bibliography_entries"] == ["Smith 2024."]
    assert meta["latexml_checks"] == {
        "sections_checked": 1,
        "paragraphs_checked": 1,
        "references_checked": 1,
        "bibliography_entries": 1,
    }
    assert not any(warning.startswith("missing_latexml_xml") for warning in meta["warnings"])
    assert not any(warning.startswith("latexml_section_mismatch") for warning in meta["warnings"])
    assert not any(warning.startswith("latexml_paragraph_mismatch") for warning in meta["warnings"])
    assert not any(warning.startswith("latexml_unresolved_ref") for warning in meta["warnings"])


def test_cli_help_exits_zero():
    result = subprocess.run(
        [sys.executable, "tools/latex_to_docling.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout
