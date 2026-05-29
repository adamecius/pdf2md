# Plan 006_3 — Math-Environment Marker Resolution

Status:
agent_complete

Allowed status values:
draft
active
agent_in_progress
agent_complete
human_verification_required
human_verified
finished
blocked
superseded

Linked ROADMAP phase:
Phase 4b — Semantic cross-reference layer

Current roadmap estimate:
From 55% to 58% (Phase 4 / 4b semantic reconstruction). No ROADMAP.md change
until human approval.

Owner:
Agent team / human reviewer

Sequence:
Plan 006_3 (semantic sub-plan track). Previous: 006_2 (equation normalization).

Previous plan:
Plan 006_2 — Convention-agnostic equation resolution

Required previous plan status:
human_verified

Next plan after completion:
Plan 008_4 — Unresolved-marker diagnostic and human teaching loop

Branch name:
plan-006_3-math-environment-markers

---

## IMPORTANT — corrected premise (verified 2026-05-28)

The drafted plan stated *"the defect is in the resolver, not in detection."*
Repo verification found this is **only half true**:

```text
Marker side (semantic backends):  EXISTS
  regex example02:  theorem 16, corollary 18, definition 13, example 10, proof 2
  vlm_v4 example02: theorem 10, corollary 9, example 9, definition 3, proof 4
  patterns.py emits all five theorem-family marker types.

Candidate side (OCR connector):   ABSENT
  EntityType has NO theorem-family members.
  connectors/common.py has NO theorem-family detection.
  example02 OCR entities: 0 theorem-family candidates (deepseek + mineru).
```

Consequence: a resolver-only change **cannot lift real theorem-family
resolution above 0%**, because there are no candidate entities to match
against. The H1 "rate > 0% on example02" criterion is therefore NOT
achievable by this plan alone.

Decision (human, 2026-05-28): implement **resolver-only, fixture-proven**.
This plan delivers and unit-proves the matcher; real-data lift is deferred to
a follow-up that adds the connector-side theorem-family entity detector
(EntityType members + `connectors/common.py` detector + `candidates.py`
mapping — the same two-sided shape Plan 6 used for index/glossary). H1 below
is restated accordingly.

---

## 1. Purpose

Make theorem-family cross-reference markers (THEOREM / DEFINITION / COROLLARY /
PROOF / EXAMPLE) resolvable by hierarchical number identity. The semantic
backends already DETECT these markers; the resolver had no matcher for them, so
they fell through to the generic fuzzy fallback and (absent same-type
candidates) stayed unresolved. This plan adds the matcher and proves it correct
with synthetic candidates / fixtures, so the moment a connector-side detector
emits theorem-family entities, resolution works with no further resolver change.

---

## 2. Source-of-truth hierarchy

ROADMAP.md / project.md / history.md as canonical. This plan is a resolver-only
sub-plan of the finished 006_0 chain and controls only the work described here.

---

## 3. Repository and environment protocol

Standard: branch from clean main; no OCR/VLM/GROBID execution; pdf2md env only;
stdlib + resolver work validated by unit tests and static JSON fixtures.

---

## 4. Scope, constraints, and dependencies

In scope:

1. Theorem-family prefix patterns in `_PREFIX_PATTERNS` for COROLLARY, EXAMPLE,
   and PROOF (THEOREM / DEFINITION already present). PROOF tolerates the
   "Proof of Theorem/Lemma/Proposition/Corollary N" form.
2. `_try_theorem_family` matcher resolving by hierarchical number identity,
   wired into `_resolve_one` after `_try_footnote` and before `_try_fuzzy`,
   with cross-type isolation.
3. Hierarchical-number non-collision (``3.2`` ≠ ``3`` ≠ ``2``), no-number
   markers → unresolved (not an exception).

Out of scope (unchanged from the draft):

1. Equation normalization (006_2).
2. Detection-pattern changes (patterns.py forbidden).
3. New RefType / EntityType members.
4. Candidate-source restructure (006_4); router (006_1).
5. **The connector-side theorem-family entity detector** — this is the piece
   that would move real resolution above 0%; explicitly deferred to a
   follow-up plan (call it 006_5 or fold into 006_4).

Hard constraints:

1. No file outside the §5 whitelist.
2. No previously-resolving marker type may regress.
3. No new dependency.

---

## 5. File whitelist

```text
src/pdf2md/semantic/resolver.py
tests/test_semantic_resolver.py
tests/data/semantic_fixtures/theorem_family_markers.json
tests/data/semantic_fixtures/theorem_family_candidates.json
```

Forbidden (notably): `backend/semantic/regex/patterns.py`,
`src/pdf2md/models/*`, `src/pdf2md/semantic/candidates.py`,
`src/pdf2md/connectors/common.py`, `consensus/*`.

---

## 6. Agent tasks (all complete)

* **A1** — COROLLARY / EXAMPLE / PROOF prefix patterns added; unit test asserts
  prefix-strip + number extraction per type. DONE.
* **A2** — `_try_theorem_family` matcher + ladder wiring; positive resolution,
  cross-type isolation, hierarchical non-collision, no-number cases tested.
  DONE.
* **A3** — `theorem_family_markers.json` + `theorem_family_candidates.json`
  fixtures (example02-shaped, with a cross-type distractor); fixture
  round-trip test asserts 5/6 markers resolve to the correct same-type
  candidate and the cross-type distractor is not captured. DONE.

---

## 7. Human verification checkpoint H1 (RESTATED)

Original H1 ("example02 theorem-family resolution > 0%") is **not achievable by
this resolver-only plan** — no theorem-family candidate entities exist on the
OCR side yet. Restated H1:

```text
With the theorem_family fixtures (synthetic same-type candidates):
  - all numbered theorem-family markers resolve to their correct same-type
    candidate (fixture round-trip test);
  - cross-type isolation holds (theorem ≠ definition at same number);
  - hierarchical numbers do not collide (3.2 ≠ 3 ≠ 2);
  - no previously-resolving marker type regresses (full suite green).
Real example02 theorem-family resolution remains 0% by design until the
connector-side detector lands; this is documented, not a defect of this plan.
```

Verified: full suite 1152 → 1159 passed (+7 theorem-family tests); ruff clean
on resolver.py.

---

## 8–10. Test matrix / hand-off / reviewer checklist

```bash
conda run -n pdf2md pytest tests/test_semantic_resolver.py -q   # 28 passed
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp # 1159 passed
```

Reviewer checklist: whitelist respected; patterns.py / models / candidates
untouched; no RefType/EntityType added; cross-type isolation preserved; full
suite green; the real-data-0%-until-detector caveat understood and accepted.

Status history:

```text
2026-05-28 — draft — human — drafted from examples-only analysis
2026-05-28 — agent_complete — agent — resolver matcher + prefixes + fixtures
  implemented per the resolver-only decision. Premise corrected: candidate
  side absent, so real resolution stays 0% until a connector detector is
  added (deferred). Matcher fixture-proven. 1159 passed; ruff clean.
```

---

## 11. Design note — why this is correct-but-dormant

The matcher is identical in shape to `_try_equation` / `_try_bibliography` and
enforces the same cross-type isolation. It is exercised only by fixtures today
because the OCR connector emits no theorem-family entities. The honest framing:
this plan makes the resolver *ready* — when a follow-up adds an
`EntityType.THEOREM` (etc.) detector to `connectors/common.py` and maps it in
`candidates.py`, theorem-family markers will resolve with zero further resolver
work. Until then the live metric is unchanged, by design.
