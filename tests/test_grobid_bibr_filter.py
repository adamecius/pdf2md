"""Tests for the GROBID TEI bibliography filter (Case B).

GROBID's TEI parser occasionally tags non-bibliography fragments
with ``<ref type="bibr">`` — page references, orphan brackets on
Example/Corollary refs, bare equation numbers. The bridge has no
candidate to resolve these against, so they show up as unresolved
"bibliography" markers and pollute the resolution-rate metric.

End-to-end impact (measured on the cached arxiv example02 +
deepseek OCR): 6 of 116 GROBID bibliography markers were
garbage. After the filter, those become 5 rerouted to other types
(equation, example, corollary) and 1 dropped (`p. 539;`), so the
bibliography output is clean.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


# tei_parser lives under `backend/semantic/grobid/`, which is intentionally
# not a Python package on sys.path. Import by file path, matching the
# pattern used by `src/pdf2md/semantic/grobid_adapter.py`.
_PARSER_PATH = Path(__file__).resolve().parent.parent / "backend" / "semantic" / "grobid" / "tei_parser.py"


def _load_tei_parser():
    spec = importlib.util.spec_from_file_location("_test_tei_parser", _PARSER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tei_parser = _load_tei_parser()


def _wrap_tei(body_refs: str) -> str:
    """Wrap a fragment of `<ref>` elements in a minimal TEI envelope."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <text>
    <body>
      <p>Some text {body_refs}.</p>
    </body>
  </text>
</TEI>"""


# ---------------------------------------------------------------------------
# _classify_bibr unit tests
# ---------------------------------------------------------------------------
def test_classify_bibr_accepts_canonical_numeric_brackets() -> None:
    assert tei_parser._classify_bibr("[15]") == "bibliography"
    assert tei_parser._classify_bibr("[12, 14]") == "bibliography"
    assert tei_parser._classify_bibr("[12-14]") == "bibliography"
    assert tei_parser._classify_bibr("[12–14]") == "bibliography"
    assert tei_parser._classify_bibr("[ 7 ]") == "bibliography"


def test_classify_bibr_accepts_author_year() -> None:
    assert tei_parser._classify_bibr("(Smith, 2020)") == "bibliography"
    assert tei_parser._classify_bibr("(Smith and Jones, 2020)") == "bibliography"
    assert tei_parser._classify_bibr("(Smith et al., 2020a)") == "bibliography"


def test_classify_bibr_reroutes_equation_fragments_with_keyword() -> None:
    """Only `Eq.` / `Equation` keyword-prefixed forms reroute. Bare
    numbers (with or without parens) stay as bibliography — see
    ``test_classify_bibr_keeps_bare_numbers_as_bibliography``."""
    assert tei_parser._classify_bibr("Eq. (15.110)") == "equation"
    assert tei_parser._classify_bibr("Eqs. (15)") == "equation"
    assert tei_parser._classify_bibr("Equation 11") == "equation"


def test_classify_bibr_keeps_bare_numbers_as_bibliography() -> None:
    """Bare digits / parenthesised digits stay as bibliography.

    GROBID's bibr text rendering often strips the outer brackets so
    ``[15]`` arrives as ``"15"``. Rerouting these to equation would
    steal hundreds of legitimate bibliography markers (verified on
    example02: an aggressive bare-number reroute moved 87 bib markers
    to equation, dropping resolution from 116/141 to 42/121)."""
    assert tei_parser._classify_bibr("15") == "bibliography"
    assert tei_parser._classify_bibr("11") == "bibliography"
    assert tei_parser._classify_bibr("(11)") == "bibliography"
    assert tei_parser._classify_bibr("(15.113)") == "bibliography"


def test_classify_bibr_reroutes_math_style_fragments() -> None:
    assert tei_parser._classify_bibr("Ex. 3.3]") == "example"
    assert tei_parser._classify_bibr("Example 3.3") == "example"
    assert tei_parser._classify_bibr("Corollary 3.3]") == "corollary"
    assert tei_parser._classify_bibr("Theorem 3.2") == "theorem"
    assert tei_parser._classify_bibr("Definition 1.1") == "definition"
    assert tei_parser._classify_bibr("Proof of Theorem 3.2") == "proof"


def test_classify_bibr_drops_garbage() -> None:
    # Page references, orphan brackets, single letters.
    assert tei_parser._classify_bibr("p. 539;") is None
    assert tei_parser._classify_bibr("[L]") is None
    assert tei_parser._classify_bibr("") is None
    assert tei_parser._classify_bibr("   ") is None


# ---------------------------------------------------------------------------
# parse_tei integration tests
# ---------------------------------------------------------------------------
def test_parse_tei_keeps_canonical_bib_markers() -> None:
    tei = _wrap_tei(
        '<ref type="bibr" target="#b0">[1]</ref> '
        '<ref type="bibr" target="#b14">[15]</ref> '
        '<ref type="bibr">(Smith, 2020)</ref>'
    )
    result = tei_parser.parse_tei(tei)
    bib_markers = [m for m in result.markers if m.marker_type == "bibliography"]
    assert len(bib_markers) == 3
    assert {m.marker_text for m in bib_markers} == {"[1]", "[15]", "(Smith, 2020)"}


def test_parse_tei_drops_garbage_bib_markers() -> None:
    tei = _wrap_tei(
        '<ref type="bibr">[1]</ref> '
        '<ref type="bibr">p. 539;</ref> '
        '<ref type="bibr">[L]</ref>'
    )
    result = tei_parser.parse_tei(tei)
    # Only the canonical [1] survives as a bibliography marker.
    bib_markers = [m for m in result.markers if m.marker_type == "bibliography"]
    assert [m.marker_text for m in bib_markers] == ["[1]"]
    # The dropped fragments produce a warning so audits can see what happened.
    assert any("dropped" in w for w in result.warnings)


def test_parse_tei_reroutes_misclassified_bib_markers() -> None:
    """Math-keyword-prefixed bibr fragments reroute.

    Note: bare numbers like ``(15.113)`` are intentionally NOT
    rerouted — GROBID's bibr text rendering often strips brackets,
    so a default-keep policy is needed to avoid stealing legitimate
    bibliography markers. See
    ``test_classify_bibr_keeps_bare_numbers_as_bibliography``."""
    tei = _wrap_tei(
        '<ref type="bibr">[1]</ref> '
        '<ref type="bibr">Eq. (15.110)</ref> '
        '<ref type="bibr">Corollary 3.3]</ref> '
        '<ref type="bibr">Theorem 3.2</ref>'
    )
    result = tei_parser.parse_tei(tei)
    by_type = {}
    for m in result.markers:
        by_type.setdefault(m.marker_type, []).append(m.marker_text)
    assert by_type.get("bibliography") == ["[1]"]
    assert by_type.get("equation") == ["Eq. (15.110)"]
    assert by_type.get("corollary") == ["Corollary 3.3]"]
    assert by_type.get("theorem") == ["Theorem 3.2"]
    # Rerouting also produces audit warnings.
    assert any("rerouted" in w for w in result.warnings)


def test_parse_tei_does_not_affect_non_bibr_markers() -> None:
    """Markers tagged with a non-bibr type are untouched by the filter."""
    tei = _wrap_tei(
        '<ref type="figure">Figure 1</ref> '
        '<ref type="formula">(11)</ref> '
        '<ref type="section">Section 2</ref>'
    )
    result = tei_parser.parse_tei(tei)
    by_type = {m.marker_type: m.marker_text for m in result.markers}
    assert by_type == {"figure": "Figure 1", "equation": "(11)", "section": "Section 2"}
    # No bib filter warnings on a doc with no bibr markers.
    assert all("bibr" not in w for w in result.warnings)
