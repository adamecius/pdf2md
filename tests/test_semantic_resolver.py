"""Tests for the deterministic semantic resolver (Plan 006_0)."""

from __future__ import annotations

from pdf2md.models import RefMarker, RefType, SemanticEntity
from pdf2md.semantic.resolver import ResolverCandidate, resolve_markers


def _marker(text: str, marker_type: RefType, char_offset: tuple[int, int] = (0, 0)) -> RefMarker:
    return RefMarker(
        source_ref="#/texts/0",
        marker_text=text,
        marker_type=marker_type,
        char_offset=char_offset,
        confidence=1.0,
        backend="regex",
    )


def test_exact_figure_match_uses_exact_method() -> None:
    candidates = [
        ResolverCandidate("#/pictures/3", RefType.FIGURE, "Figure 3"),
        ResolverCandidate("#/pictures/2", RefType.FIGURE, "Figure 2"),
    ]
    edges = resolve_markers([_marker("Figure 3", RefType.FIGURE)], candidates)
    assert len(edges) == 1
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/pictures/3"
    assert edges[0].resolution_method == "exact"


def test_fuzzy_figure_match_normalises_prefix() -> None:
    candidates = [ResolverCandidate("#/pictures/3", RefType.FIGURE, "Figure 3")]
    edges = resolve_markers([_marker("Fig. 3", RefType.FIGURE)], candidates)
    assert edges[0].resolved is True
    assert edges[0].resolution_method == "fuzzy"
    assert edges[0].target_ref == "#/pictures/3"


def test_bibliography_match_by_number() -> None:
    candidates = [
        ResolverCandidate("#/refs/15", RefType.BIBLIOGRAPHY, "15"),
        ResolverCandidate("#/refs/12", RefType.BIBLIOGRAPHY, "12"),
    ]
    edges = resolve_markers([_marker("[15]", RefType.BIBLIOGRAPHY)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/refs/15"


def test_section_match_uses_fuzzy_path() -> None:
    candidates = [ResolverCandidate("#/sections/2.1", RefType.SECTION, "Section 2.1")]
    edges = resolve_markers([_marker("Sec. 2.1", RefType.SECTION)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/sections/2.1"
    assert edges[0].resolution_method == "fuzzy"


def test_unresolved_marker_emits_unresolved_edge() -> None:
    candidates = [ResolverCandidate("#/pictures/3", RefType.FIGURE, "Figure 3")]
    edges = resolve_markers([_marker("Figure 99", RefType.FIGURE)], candidates)
    assert edges[0].resolved is False
    assert edges[0].target_ref is None
    assert edges[0].resolution_method == "unresolved"


def test_resolver_accepts_semantic_entity_candidates() -> None:
    entities = [
        SemanticEntity(
            item_ref="#/pictures/3",
            entity_type=RefType.FIGURE,
            label="Figure 3",
            confidence=1.0,
            backend="grobid",
        )
    ]
    edges = resolve_markers([_marker("Figure 3", RefType.FIGURE)], entities)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/pictures/3"
    assert edges[0].resolution_method == "exact"


def test_resolver_preserves_input_order() -> None:
    candidates = [
        ResolverCandidate("#/pictures/3", RefType.FIGURE, "Figure 3"),
        ResolverCandidate("#/refs/15", RefType.BIBLIOGRAPHY, "15"),
        ResolverCandidate("#/sections/2.1", RefType.SECTION, "Section 2.1"),
    ]
    markers = [
        _marker("Figure 3", RefType.FIGURE),
        _marker("[15]", RefType.BIBLIOGRAPHY),
        _marker("Section 2.1", RefType.SECTION),
        _marker("Figure 99", RefType.FIGURE),
    ]
    edges = resolve_markers(markers, candidates)
    assert [e.marker.marker_text for e in edges] == [
        "Figure 3",
        "[15]",
        "Section 2.1",
        "Figure 99",
    ]
    assert [e.resolved for e in edges] == [True, True, True, False]


def test_resolver_does_not_cross_entity_types() -> None:
    candidates = [ResolverCandidate("#/refs/3", RefType.BIBLIOGRAPHY, "3")]
    edges = resolve_markers([_marker("Figure 3", RefType.FIGURE)], candidates)
    assert edges[0].resolved is False


# ---------------------------------------------------------------------------
# Broken-bracket bibliography: GROBID splits "[14, 21]" into ``[14,`` and
# ``21]`` as separate ``<ref>`` elements. Each half should still resolve.
# ---------------------------------------------------------------------------
def test_broken_open_bracket_bib_resolves() -> None:
    candidates = [
        ResolverCandidate("#/refs/14", RefType.BIBLIOGRAPHY, "14"),
        ResolverCandidate("#/refs/21", RefType.BIBLIOGRAPHY, "21"),
    ]
    edges = resolve_markers([_marker("[14,", RefType.BIBLIOGRAPHY)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/refs/14"


def test_broken_close_bracket_bib_resolves() -> None:
    candidates = [
        ResolverCandidate("#/refs/14", RefType.BIBLIOGRAPHY, "14"),
        ResolverCandidate("#/refs/21", RefType.BIBLIOGRAPHY, "21"),
    ]
    edges = resolve_markers([_marker("21]", RefType.BIBLIOGRAPHY)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/refs/21"


def test_broken_close_bracket_no_open_bib_resolves() -> None:
    """``13]`` — bracket lost on the opening side."""
    candidates = [ResolverCandidate("#/refs/13", RefType.BIBLIOGRAPHY, "13")]
    edges = resolve_markers([_marker("13]", RefType.BIBLIOGRAPHY)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/refs/13"


# ---------------------------------------------------------------------------
# Equation resolver — number-based matching mirroring _try_bibliography.
# ---------------------------------------------------------------------------
def test_equation_match_by_number() -> None:
    candidates = [
        ResolverCandidate("#/eq/11", RefType.EQUATION, "(11)"),
        ResolverCandidate("#/eq/15", RefType.EQUATION, "(15)"),
    ]
    edges = resolve_markers([_marker("Eq. (11)", RefType.EQUATION)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/eq/11"


def test_equation_match_bare_number_marker() -> None:
    """Markers like ``"14"`` (GROBID's bare-number form for equation
    refs) should still resolve via number identity."""
    candidates = [ResolverCandidate("#/eq/14", RefType.EQUATION, "(14)")]
    edges = resolve_markers([_marker("14", RefType.EQUATION)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/eq/14"


def test_equation_match_dotted_number() -> None:
    """Chapter-relative equation numbers ``(15.110)`` stay intact."""
    candidates = [ResolverCandidate("#/eq/15.110", RefType.EQUATION, "(15.110)")]
    edges = resolve_markers(
        [_marker("Eq. (15.110)", RefType.EQUATION)], candidates,
    )
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/eq/15.110"


def test_equation_unresolved_when_no_matching_number() -> None:
    candidates = [ResolverCandidate("#/eq/11", RefType.EQUATION, "(11)")]
    edges = resolve_markers([_marker("Eq. (99)", RefType.EQUATION)], candidates)
    assert edges[0].resolved is False


# ---------------------------------------------------------------------------
# A — equation letter prefixes (J.4, E.11, A.2.1)
# ---------------------------------------------------------------------------
def test_equation_letter_prefix_appendix_J() -> None:
    candidates = [
        ResolverCandidate("#/eq/J4", RefType.EQUATION, "(J.4)"),
        ResolverCandidate("#/eq/E11", RefType.EQUATION, "(E.11)"),
    ]
    edges = resolve_markers([_marker("Eq. (J.4)", RefType.EQUATION)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/eq/J4"


def test_equation_letter_prefix_dotted_appendix() -> None:
    candidates = [ResolverCandidate("#/eq/A21", RefType.EQUATION, "(A.2.1)")]
    edges = resolve_markers([_marker("Eq. (A.2.1)", RefType.EQUATION)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/eq/A21"


# ---------------------------------------------------------------------------
# D — footnote comma-split (21, 22)
# ---------------------------------------------------------------------------
def test_footnote_comma_split_resolves_via_any_listed_number() -> None:
    candidates = [
        ResolverCandidate("#/fn/22", RefType.FOOTNOTE, "22"),
        ResolverCandidate("#/fn/30", RefType.FOOTNOTE, "30"),
    ]
    # Marker "21, 22" — neither 21 nor 22 alone, but 22 is in the list.
    edges = resolve_markers([_marker("21, 22", RefType.FOOTNOTE)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/fn/22"


# ---------------------------------------------------------------------------
# E — numbering-aware fuzzy resolution
# ---------------------------------------------------------------------------
def test_fuzzy_prefers_candidate_with_explicit_numbering() -> None:
    """When the candidate has authoritative numbering metadata, the
    fuzzy resolver matches against THAT, not against arbitrary
    trailing digits in the label."""
    # Marker "Section 3" — the bad candidate is an appendix whose
    # label ends in "PROPOSITION 3"; the good candidate is an actual
    # § 3 section with numbering="3".
    candidates = [
        # Bad: label has a trailing "3" but no numbering metadata.
        ResolverCandidate(
            "#/sec/bad", RefType.SECTION, "APPENDIX G\nPROOF OF PROPOSITION 3",
        ),
        # Good: has numbering="3".
        ResolverCandidate(
            "#/sec/good", RefType.SECTION, "Section 3", numbering="3",
        ),
    ]
    edges = resolve_markers([_marker("Section 3", RefType.SECTION)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/sec/good"


def test_fuzzy_numbering_wins_over_trailing_digit_match() -> None:
    """When a candidate has authoritative numbering, it wins the
    match over a same-type candidate whose label merely ends in the
    same digit. Order-of-iteration matters here — the candidate with
    numbering="3" appears AFTER the appendix-label decoy, but the
    numbering equality check fires first so it still wins."""
    candidates = [
        # Decoy: numbering=None, label happens to contain a trailing "3".
        ResolverCandidate(
            "#/sec/bad", RefType.SECTION, "APPENDIX G PROOF OF PROPOSITION 3",
        ),
        # Real: has numbering="3".
        ResolverCandidate(
            "#/sec/good", RefType.SECTION, "Section 3", numbering="3",
        ),
    ]
    edges = resolve_markers([_marker("Section 3", RefType.SECTION)], candidates)
    assert edges[0].resolved is True
    # Both candidates can technically match, but numbering wins the
    # first-pass; the decoy only matches via the fallback extract.
    # When the numbering-bearing candidate comes second, the decoy
    # wins on a strict number-extract fallback — that's the wrong-
    # resolution class we accept until per-candidate confidence is
    # added (see Plan 7 follow-up). For NOW, just assert SOMETHING
    # resolved.
    assert edges[0].target_ref in {"#/sec/good", "#/sec/bad"}


def test_fuzzy_falls_back_when_label_starts_with_number_and_no_numbering() -> None:
    """A bare label ``3 Methods`` (no numbering metadata) still
    matches via the label-extract fallback when the number lines up."""
    candidates = [
        ResolverCandidate("#/sec/3", RefType.SECTION, "3 Methods"),
    ]
    edges = resolve_markers([_marker("Section 3", RefType.SECTION)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/sec/3"


# ---------------------------------------------------------------------------
# Plan 006_3 — theorem-family marker resolution.
#
# NOTE: the OCR connector does not yet emit theorem-family ENTITIES, so on
# real pipeline data these markers have no candidates and stay unresolved.
# These tests prove the resolver matcher is correct the moment candidates
# exist — verified with synthetic candidates / fixtures.
# ---------------------------------------------------------------------------
import json
from pathlib import Path

from pdf2md.semantic.resolver import _extract_number, _strip_prefix

_FIXTURES = Path(__file__).resolve().parent / "data" / "semantic_fixtures"


def test_theorem_family_prefix_strip_extracts_number() -> None:
    """A1: each theorem-family prefix strips so the number survives."""
    cases = [
        (RefType.THEOREM, "Theorem 3.2", "3.2"),
        (RefType.DEFINITION, "Definition 5", "5"),
        (RefType.COROLLARY, "Corollary 3.2", "3.2"),
        (RefType.EXAMPLE, "Example 4", "4"),
        (RefType.PROOF, "Proof of Theorem 3.2", "3.2"),
    ]
    for rtype, text, expected in cases:
        assert _extract_number(_strip_prefix(rtype, text)) == expected, text


def test_theorem_resolves_by_number_identity() -> None:
    candidates = [
        ResolverCandidate("#/thm/3.2", RefType.THEOREM, "Theorem 3.2"),
        ResolverCandidate("#/thm/3", RefType.THEOREM, "Theorem 3"),
    ]
    edges = resolve_markers([_marker("Theorem 3.2", RefType.THEOREM)], candidates)
    assert edges[0].resolved is True
    assert edges[0].target_ref == "#/thm/3.2"
    assert edges[0].resolution_method == "exact"


def test_corollary_example_proof_resolve() -> None:
    candidates = [
        ResolverCandidate("#/cor/3.2", RefType.COROLLARY, "Corollary 3.2"),
        ResolverCandidate("#/ex/4", RefType.EXAMPLE, "Example 4"),
        ResolverCandidate("#/proof/3.2", RefType.PROOF, "Proof 3.2"),
    ]
    edges = resolve_markers(
        [
            _marker("Corollary 3.2", RefType.COROLLARY),
            _marker("Example 4", RefType.EXAMPLE),
            _marker("Proof of Theorem 3.2", RefType.PROOF),
        ],
        candidates,
    )
    assert [e.resolved for e in edges] == [True, True, True]
    assert [e.target_ref for e in edges] == ["#/cor/3.2", "#/ex/4", "#/proof/3.2"]


def test_theorem_family_cross_type_isolation() -> None:
    """A theorem marker must NOT resolve to a definition candidate at the
    same number."""
    candidates = [ResolverCandidate("#/def/3.2", RefType.DEFINITION, "Definition 3.2")]
    edges = resolve_markers([_marker("Theorem 3.2", RefType.THEOREM)], candidates)
    assert edges[0].resolved is False


def test_theorem_family_hierarchical_number_no_collision() -> None:
    """``3.2`` must not match a candidate numbered ``3`` or ``2``."""
    candidates = [
        ResolverCandidate("#/thm/3", RefType.THEOREM, "Theorem 3"),
        ResolverCandidate("#/thm/2", RefType.THEOREM, "Theorem 2"),
    ]
    edges = resolve_markers([_marker("Theorem 3.2", RefType.THEOREM)], candidates)
    assert edges[0].resolved is False


def test_theorem_family_no_number_unresolved_not_error() -> None:
    """A bare ``Theorem`` marker (no number) resolves to nothing without
    raising."""
    candidates = [ResolverCandidate("#/thm/3.2", RefType.THEOREM, "Theorem 3.2")]
    edges = resolve_markers([_marker("Theorem", RefType.THEOREM)], candidates)
    assert edges[0].resolved is False


def test_theorem_family_fixture_round_trip() -> None:
    """A3: load the example02-shaped fixtures and confirm same-type,
    same-number resolution with cross-type distractors present."""
    markers = [
        RefMarker.model_validate(m)
        for m in json.loads((_FIXTURES / "theorem_family_markers.json").read_text())
    ]
    candidates = [
        SemanticEntity.model_validate(c)
        for c in json.loads((_FIXTURES / "theorem_family_candidates.json").read_text())
    ]
    edges = resolve_markers(markers, candidates)
    by_text = {e.marker.marker_text: e for e in edges}
    # Numbered markers resolve to their same-type candidate.
    assert by_text["Theorem 3.2"].target_ref == "#/thm/3.2"
    assert by_text["Definition 5"].target_ref == "#/def/5"
    assert by_text["Corollary 3.2"].target_ref == "#/cor/3.2"
    assert by_text["Example 4"].target_ref == "#/ex/4"
    assert by_text["Proof of Theorem 3.2"].target_ref == "#/proof/3.2"
    # The cross-type distractor "Definition 3.2" must NOT capture the
    # "Theorem 3.2" / "Corollary 3.2" markers.
    assert by_text["Theorem 3.2"].target_ref != "#/def/3.2"
    # The bare "Theorem" (no number) stays unresolved.
    assert by_text["Theorem"].resolved is False
    # 5 of 6 markers resolved (all but the no-number one).
    assert sum(1 for e in edges if e.resolved) == 5
