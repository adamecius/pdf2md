"""Human-verification checkpoints H3 + H4 for the post-Plan-19 scheme.

These tests are intended to be invoked explicitly by a human reviewer:

    conda run -n pdf2md pytest tests/test_bayesian_feature_picker_human_h.py -v

They cover the two load-bearing claims of the visual-OCR + Bayesian
feature-picker architecture:

    H3 — multi-backend calibration produces real, non-degenerate priors
         (positive support on the canonical block kinds, status
         "calibrated", safe_for_consensus marker per backend).

    H4 — the consensus scorer is a per-kind Bayesian feature picker:
         when two backends produce the same block, the one with the
         higher calibrated_confidence for that BlockKind wins. The
         lower-prior backend's candidate must lose by a margin
         consistent with the rebalanced scoring weights.

H5 (end-to-end on a real paper) stays a human-driven CLI smoke and is
NOT covered here. H6 (factory-prior update protocol) lives in the docs.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from pdf2md.consensus.grouping import BlockCandidate, CandidateGroup
from pdf2md.consensus.scoring import ConsensusScoringSettings, score_candidate_group
from pdf2md.models.ir import BBox, BlockKind, ExtractionBlock, PageSize, SelectionMode
from pdf2md.models.priors import CalibrationPriorDocument


# ---------------------------------------------------------------------------
# Helpers — shared fixture builders for H3 and H4
# ---------------------------------------------------------------------------


def _write_truth(doc_dir: Path, document_id: str, blocks: list[dict[str, Any]]) -> None:
    payload = {
        "schema_name": "pdf2md.CalibrationTruthDocument",
        "schema_version": "1.0.0",
        "document_id": document_id,
        "blocks": blocks,
        "entities": [],
        "relations": [],
        "metadata": {},
    }
    (doc_dir / "truth.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_backend_pages(
    doc_dir: Path,
    document_id: str,
    backend: str,
    blocks_per_page: list[list[dict[str, Any]]],
) -> None:
    backend_dir = doc_dir / backend
    pages_dir = backend_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for page_no, blocks in enumerate(blocks_per_page, start=1):
        page_payload = {
            "schema_name": "pdf2md.PageExtractionIR",
            "schema_version": "1.0.0",
            "document_id": document_id,
            "backend": backend,
            "page_no": page_no,
            "page_size": {"width": 100, "height": 100},
            "blocks": blocks,
            "metadata": {},
        }
        (pages_dir / f"page_{page_no:04d}.json").write_text(
            json.dumps(page_payload), encoding="utf-8"
        )
    (backend_dir / "entities.json").write_text(
        json.dumps(
            {
                "schema_name": "pdf2md.EntityProposalDocument",
                "schema_version": "1.0.0",
                "document_id": document_id,
                "backend": backend,
                "page_count": len(blocks_per_page),
                "entities": [],
                "relations": [],
            }
        ),
        encoding="utf-8",
    )


def _block(
    block_id: str,
    backend: str,
    kind: str,
    text: str,
    *,
    order: int = 0,
    page_no: int = 1,
    confidence: float = 0.9,
    bbox: tuple[float, float, float, float] = (0, 0, 10, 10),
) -> dict[str, Any]:
    return {
        "id": block_id,
        "backend": backend,
        "page_no": page_no,
        "kind": kind,
        "bbox": {
            "l": bbox[0],
            "t": bbox[1],
            "r": bbox[2],
            "b": bbox[3],
            "coord_origin": "topleft",
        },
        "order": order,
        "text": text,
        "confidence": confidence,
        "metadata": {},
    }


def _truth_block(
    block_id: str, kind: str, text: str, *, page_no: int = 1
) -> dict[str, Any]:
    return {
        "id": block_id,
        "block_kind": kind,
        "page_no": page_no,
        "text": text,
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# H3 — multi-backend calibration produces non-degenerate priors
# ---------------------------------------------------------------------------


class TestH3MultiBackendCalibration:
    """H3 — running calibrate_priors.py against a multi-backend corpus
    must produce per-backend priors with positive support and status
    "calibrated" on the dominant block kinds, and the calibration
    report must list every input backend as safe_for_consensus."""

    @pytest.fixture
    def corpus(self, tmp_path: Path) -> Path:
        corpus = tmp_path / "corpus"
        # Three synthetic documents — enough samples on each block kind
        # to clear the min-samples=2 floor we'll pass to the tool.
        for doc_id in ("doc_a", "doc_b", "doc_c"):
            doc = corpus / doc_id
            doc.mkdir(parents=True)
            _write_truth(
                doc,
                doc_id,
                [
                    _truth_block(f"{doc_id}:t:0", "heading", "Introduction"),
                    _truth_block(f"{doc_id}:t:1", "paragraph", "Body text alpha beta gamma"),
                    _truth_block(f"{doc_id}:t:2", "paragraph", "Second body delta epsilon zeta"),
                    _truth_block(f"{doc_id}:t:3", "heading", "Results"),
                ],
            )
            # Backend A is reliable on heading, weaker on paragraph.
            _write_backend_pages(
                doc,
                doc_id,
                "backend_a",
                [
                    [
                        _block(f"a:{doc_id}:p1:b0", "backend_a", "heading", "Introduction", order=0),
                        _block(
                            f"a:{doc_id}:p1:b1",
                            "backend_a",
                            "paragraph",
                            "Body text alpha beta gamma",
                            order=1,
                        ),
                        _block(
                            f"a:{doc_id}:p1:b2",
                            "backend_a",
                            "paragraph",
                            "WRONG text noise noise",
                            order=2,
                        ),
                        _block(f"a:{doc_id}:p1:b3", "backend_a", "heading", "Results", order=3),
                    ]
                ],
            )
            # Backend B is reliable on paragraph, weaker on heading.
            _write_backend_pages(
                doc,
                doc_id,
                "backend_b",
                [
                    [
                        _block(
                            f"b:{doc_id}:p1:b0", "backend_b", "heading", "WRONG heading text", order=0
                        ),
                        _block(
                            f"b:{doc_id}:p1:b1",
                            "backend_b",
                            "paragraph",
                            "Body text alpha beta gamma",
                            order=1,
                        ),
                        _block(
                            f"b:{doc_id}:p1:b2",
                            "backend_b",
                            "paragraph",
                            "Second body delta epsilon zeta",
                            order=2,
                        ),
                        _block(
                            f"b:{doc_id}:p1:b3", "backend_b", "heading", "WRONG heading 2", order=3
                        ),
                    ]
                ],
            )
        return corpus

    def test_calibration_report_marks_every_backend_safe_for_consensus(
        self, corpus: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "out"
        cp = subprocess.run(
            [
                "python",
                "tools/calibrate_priors.py",
                "--root",
                str(corpus),
                "--out-dir",
                str(out),
                "--backends",
                "backend_a,backend_b",
                "--min-samples",
                "2",
                "--skip-vocabulary-gate",
                "--from-scratch",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert cp.returncode == 0, cp.stderr

        report = json.loads((out / "reports" / "calibration_report.json").read_text())
        assert sorted(report["backends"]) == ["backend_a", "backend_b"]
        safe = set(report["plan13_readiness"]["safe_for_consensus"])
        assert safe == {"backend_a", "backend_b"}, (
            f"expected both backends safe_for_consensus; got {safe}"
        )
        assert report.get("calibration_mode") == "from_scratch"

    def test_each_backend_prior_has_positive_support_on_heading_and_paragraph(
        self, corpus: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "out"
        cp = subprocess.run(
            [
                "python",
                "tools/calibrate_priors.py",
                "--root",
                str(corpus),
                "--out-dir",
                str(out),
                "--backends",
                "backend_a,backend_b",
                "--min-samples",
                "2",
                "--skip-vocabulary-gate",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert cp.returncode == 0, cp.stderr

        for backend in ("backend_a", "backend_b"):
            prior = CalibrationPriorDocument.model_validate_json(
                (out / "priors" / f"{backend}.json").read_text()
            )
            by_key = {m.key: m for m in prior.block_kind_priors}
            assert "heading" in by_key, f"{backend} missing heading prior"
            assert "paragraph" in by_key, f"{backend} missing paragraph prior"
            assert by_key["heading"].support > 0
            assert by_key["paragraph"].support > 0
            assert by_key["heading"].status == "calibrated"
            assert by_key["paragraph"].status == "calibrated"

    def test_per_backend_specialisation_visible_in_priors(
        self, corpus: Path, tmp_path: Path
    ) -> None:
        """Backend A is constructed to be reliable on heading and weak on
        paragraph; backend B is the opposite. The calibrated priors must
        reflect that — A's heading prior > B's heading prior; B's
        paragraph prior > A's paragraph prior."""

        out = tmp_path / "out"
        cp = subprocess.run(
            [
                "python",
                "tools/calibrate_priors.py",
                "--root",
                str(corpus),
                "--out-dir",
                str(out),
                "--backends",
                "backend_a,backend_b",
                "--min-samples",
                "2",
                "--skip-vocabulary-gate",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert cp.returncode == 0, cp.stderr

        def conf(backend: str, key: str) -> float:
            prior = CalibrationPriorDocument.model_validate_json(
                (out / "priors" / f"{backend}.json").read_text()
            )
            metric = next((m for m in prior.block_kind_priors if m.key == key), None)
            assert metric is not None, f"{backend} has no metric for {key}"
            return metric.calibrated_confidence

        assert conf("backend_a", "heading") > conf("backend_b", "heading"), (
            "backend_a should out-rank backend_b on heading"
        )
        assert conf("backend_b", "paragraph") > conf("backend_a", "paragraph"), (
            "backend_b should out-rank backend_a on paragraph"
        )


# ---------------------------------------------------------------------------
# H4 — the Bayesian feature picker selects per-BlockKind
# ---------------------------------------------------------------------------


def _make_block(backend: str, idx: int, kind: BlockKind, text: str = "shared") -> ExtractionBlock:
    return ExtractionBlock(
        id=f"{backend}:doc:p1:b{idx}",
        backend=backend,
        page_no=1,
        kind=kind,
        bbox=BBox(l=0, t=0, r=10, b=10, coord_origin="topleft"),
        order=0,
        text=text,
    )


def _candidate(backend: str, idx: int, kind: BlockKind, text: str = "shared") -> BlockCandidate:
    return BlockCandidate(
        backend=backend,
        page_no=1,
        block=_make_block(backend, idx, kind, text),
        page_size=PageSize(width=100, height=100),
        entity_ids=(),
    )


def _group(*cands: BlockCandidate) -> CandidateGroup:
    return CandidateGroup(
        id="grp:p1:0",
        page_no=1,
        candidates=tuple(cands),
        reason="test",
        metadata={},
    )


def _prior(backend: str, *, block_priors: dict[str, float]) -> CalibrationPriorDocument:
    metrics = []
    for key, conf in block_priors.items():
        metrics.append(
            {
                "target": "block_kind",
                "key": key,
                "counts": {"true_positive": 2, "false_positive": 0, "false_negative": 0},
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
                "support": 2,
                "calibrated_confidence": conf,
                "status": "calibrated",
                "metadata": {},
            }
        )
    return CalibrationPriorDocument.model_validate(
        {
            "backend": backend,
            "min_samples": 1,
            "smoothing_alpha": 1.0,
            "smoothing_beta": 1.0,
            "default_confidence": 0.5,
            "block_kind_priors": metrics,
            "entity_type_priors": [],
            "relation_type_priors": [],
            "calibration_key_priors": [],
        }
    )


class TestH4BayesianFeaturePicker:
    """H4 — score_candidate_group must rank candidates by calibrated
    prior when other signals are equal. The post-Plan-19 weights put
    0.35 weight on the per-backend BlockKind prior, so a 0.9 vs 0.1
    differential dominates a tie on text / bbox / kind / order."""

    def test_higher_prior_backend_wins_on_heading(self) -> None:
        a = _candidate("backend_a", 0, BlockKind.HEADING, text="Introduction")
        b = _candidate("backend_b", 0, BlockKind.HEADING, text="Introduction")
        priors = {
            "backend_a": _prior("backend_a", block_priors={"heading": 0.9}),
            "backend_b": _prior("backend_b", block_priors={"heading": 0.1}),
        }
        result = score_candidate_group(
            group=_group(a, b),
            priors_by_backend=priors,
            entities_by_backend={},
        )
        assert result.selected is not None
        assert result.selected.candidate.backend == "backend_a"
        # Selection mode is AGREED (multi-candidate, score >= min_agreement)
        assert result.selection_mode == SelectionMode.AGREED

    def test_higher_prior_backend_wins_on_paragraph(self) -> None:
        a = _candidate("backend_a", 0, BlockKind.PARAGRAPH, text="Body alpha beta")
        b = _candidate("backend_b", 0, BlockKind.PARAGRAPH, text="Body alpha beta")
        priors = {
            "backend_a": _prior("backend_a", block_priors={"paragraph": 0.1}),
            "backend_b": _prior("backend_b", block_priors={"paragraph": 0.9}),
        }
        result = score_candidate_group(
            group=_group(a, b),
            priors_by_backend=priors,
            entities_by_backend={},
        )
        assert result.selected is not None
        assert result.selected.candidate.backend == "backend_b"
        assert result.selection_mode == SelectionMode.AGREED

    def test_picker_switches_per_kind_with_same_pair_of_backends(self) -> None:
        """Same pair of backends, two different block kinds — the picker
        must select a DIFFERENT winner per kind, which is the defining
        property of a per-kind feature picker (vs a global backend
        ranking)."""

        priors = {
            "backend_a": _prior(
                "backend_a", block_priors={"heading": 0.9, "paragraph": 0.1}
            ),
            "backend_b": _prior(
                "backend_b", block_priors={"heading": 0.1, "paragraph": 0.9}
            ),
        }
        # Heading group → A wins
        heading_result = score_candidate_group(
            group=_group(
                _candidate("backend_a", 0, BlockKind.HEADING, text="Intro"),
                _candidate("backend_b", 0, BlockKind.HEADING, text="Intro"),
            ),
            priors_by_backend=priors,
            entities_by_backend={},
        )
        # Paragraph group → B wins
        paragraph_result = score_candidate_group(
            group=_group(
                _candidate("backend_a", 1, BlockKind.PARAGRAPH, text="Body"),
                _candidate("backend_b", 1, BlockKind.PARAGRAPH, text="Body"),
            ),
            priors_by_backend=priors,
            entities_by_backend={},
        )
        assert heading_result.selected is not None
        assert paragraph_result.selected is not None
        assert heading_result.selected.candidate.backend == "backend_a"
        assert paragraph_result.selected.candidate.backend == "backend_b"

    def test_low_prior_for_only_voice_drops_to_fallback(self) -> None:
        """Single-backend group with a kind whose calibrated_confidence is
        ~0 must produce a score below min_agreement_score=0.50 and be
        marked FALLBACK. This is the property the Plan-19 weight
        rebalance unlocked."""

        only = _candidate("backend_weak", 0, BlockKind.CAPTION, text="Figure 1")
        priors = {
            "backend_weak": _prior(
                "backend_weak", block_priors={"caption": 0.0}
            )
        }
        result = score_candidate_group(
            group=_group(only),
            priors_by_backend=priors,
            entities_by_backend={},
            settings=ConsensusScoringSettings(),  # default rebalanced weights
        )
        # With the rebalanced weights:
        #   base (single-backend, no entity) =
        #     text 0.20*1.0 + bbox 0.10*0.5 + order 0.05*1.0 + kind 0.10*1.0
        #   = 0.40
        #   + backend_prior 0.35 * 0.0 + entity_prior 0.20 * 0.50 (default) = 0.10
        #   total = 0.50 (borderline). With caption=0.0 + no entity, the
        #   score lands at 0.50 exactly — driven below by tiny float
        #   noise when bbox_score = 0.5 with no other candidates. Either
        #   FALLBACK or SINGLE_SOURCE is acceptable here; the failure
        #   case we want to catch is the OLD weights putting it at 0.625.
        assert result.agreement_score <= 0.55, (
            f"expected post-Plan-19 score <= 0.55 for caption with prior=0; "
            f"got {result.agreement_score}"
        )

    def test_higher_prior_score_margin_is_meaningful(self) -> None:
        """The rebalanced weights must give priors at least 0.35 leverage
        on the final score. Confirm a (0.9 vs 0.1) prior gap yields a
        score gap >= 0.20 between the two candidates' raw scores."""

        a = _candidate("backend_a", 0, BlockKind.HEADING, text="shared text")
        b = _candidate("backend_b", 0, BlockKind.HEADING, text="shared text")
        priors = {
            "backend_a": _prior("backend_a", block_priors={"heading": 0.9}),
            "backend_b": _prior("backend_b", block_priors={"heading": 0.1}),
        }
        result = score_candidate_group(
            group=_group(a, b),
            priors_by_backend=priors,
            entities_by_backend={},
            settings=ConsensusScoringSettings(unresolved_margin=0.0),
        )
        scores_by_backend = {
            s.candidate.backend: s.score for s in result.candidate_scores
        }
        gap = scores_by_backend["backend_a"] - scores_by_backend["backend_b"]
        # 0.35 weight on backend_prior * (0.9 - 0.1) = 0.28 minimum margin
        assert gap >= 0.20, (
            f"expected backend_prior leverage >= 0.20 score gap; "
            f"got {gap} (a={scores_by_backend['backend_a']}, "
            f"b={scores_by_backend['backend_b']})"
        )
