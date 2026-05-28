# Plan 006_2 — Convention-Agnostic Equation Resolution

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
Post-MVP semantic refinement. No ROADMAP.md percentage change until human
approval. Lifts MinerU equation cross-reference resolution from ~1% toward
the DeepSeek level (~95%), removing the last blocker to MinerU becoming the
default candidate source (Plan 006_4).

Note:
This is a sub-plan of the finished Plan 006_0 (Semantic Layer Integration),
slotting into the project's `_N` deferred-sub-plan convention alongside the
reserved 006_1. It is a FIX to existing modules — `resolver.py` and
`connectors/common.py` already exist and are tested. PR #136
(`marker-resolver-fixes`) already made the DeepSeek equation conventions
resolve; this plan finishes the MinerU conventions that PR #136 did not cover.

Owner:
Agent team / human reviewer / local acceptance layer

Sequence:
First milestone of the cross-reference fix set (006_2 → 006_3 → 008_4 →
007_1 → 007_2; 006_1 and 006_4 interleave). The designated UNBLOCKER.

Previous plan:
Plan 008_0 — Semantic CrossReferenceGraph Viewer & D3 Export (human_verified,
history M23). Active plan today is Additional Plan 1.

Required previous plan status:
human_verified

Next plan after completion:
Plan 006_3 — Math-environment marker resolution.

Branch name:
plan-006_2-equation-normalization

---

## 1. Purpose

Make equation cross-references resolve regardless of the OCR backend's
equation-numbering convention. Today, equation resolution is backend-confounded:
DeepSeek equations resolve ~95% but MinerU ~1%, not because MinerU's OCR is
worse but because MinerU writes equation numbers in a surface form the
connector's extractor does not capture.

The defect is in **candidate construction** (`connectors/common.py`
`recognize_entities`), not the resolver's matching logic. The resolver's
`_extract_equation_number` already searches for a number anywhere in a label;
the problem is that MinerU equation entities never get an `equation_number`
written into their metadata, so the candidate label is empty of a number and
there is nothing for the resolver to match.

Measured state on the `examples-only` example3 snapshot (791-page book), AFTER
PR #136:

```text
backend    equation entities    with equation_number
deepseek   1102                 1052   (95.5%)
mineru     1122                 15     (1.3%)
```

This plan closes that gap. It is the prerequisite for Plan 006_4 (making MinerU
the default candidate source), because MinerU cannot be the default until its
equations resolve.

The core question:

```text
After this plan, does MinerU equation cross-reference resolution on
example01/02/03 rise from ~1% toward the DeepSeek level (target example3
> 80%), with bibliography / section / figure / table resolution rates
unchanged?
```

---

## 2. Source-of-truth hierarchy

ROADMAP.md is the durable product roadmap (Phase 4b).

project.md is the durable architecture description. The "no input classifier"
rule applies to the extraction layer; this plan does not introduce routing.

history.md records M19–M23 (the finished 006_0–008_0 chain). This sub-plan
extends 006_0 without modifying any other finished subsystem.

PLAN_TEMPLATE.md is the canonical plan shape.

This plan controls only the work explicitly described here.

---

## 3. Repository and environment protocol

Before any implementation, the agent must run:

```bash
git status --short
git fetch --all --prune
git checkout main
git pull --ff-only
git switch -c plan-006_2-equation-normalization
```

Rules:

1. Do not work directly on main.
2. Do not start from a dirty working tree.
3. Do not modify files outside the §5 whitelist.
4. Do not change ROADMAP.md progress.
5. No runtime behaviour change outside equation-number extraction and
   equation entity construction. Every other detector's output must be
   byte-identical.
6. Do not mark this plan human_verified or finished. Only the human
   reviewer may do that.

Main conda environment:

```text
pdf2md
```

This plan does not require backend (OCR) conda environments — it operates on
the cached markdown already produced for example01/02/03.

---

## 4. Scope, constraints, and dependencies

In scope:

1. **Convention-agnostic equation-number extraction** in
   `connectors/common.py`. The extractor must capture the number from ALL of
   these surface forms (the union observed across the three OCR backends):
   * trailing parenthesised: `... (11)` / `... (15.110)` / `... (J.4)`
     — already handled by PR #136.
   * inside LaTeX delimiters: `\[ math \quad (11) \]` — already handled.
   * `\tag{N}` — already handled for the **no-space** form.
   * **`\tag {N}` with whitespace** — MinerU's actual output is `\tag {2.3}`
     (space between `\tag` and the brace). NEW: the regex must tolerate
     optional whitespace.
   * **un-delimited equation lines** — MinerU emits numbered equations as a
     bare line `\chi = \frac{...}, \tag {2.3}` with NO `\[ \]` / `$$`
     wrapper, so `classify_block` never tags it FORMULA and the equation
     detector skips it entirely. NEW: an equation line carrying a `\tag{N}`
     (or trailing display-number) must be recognised even without math
     delimiters.
2. **Fragmented display-equation merge.** MinerU splits one numbered
   `align*` / `aligned` environment across multiple adjacent block entities;
   only the fragment carrying the number resolves. NEW: merge adjacent
   FORMULA fragments that belong to one numbered display equation so the
   number attaches to the whole.

Out of scope:

1. New marker types (theorem/definition/corollary) — Plan 006_3.
2. The profiler/router and GROBID-book weighting — Plan 006_1.
3. Candidate-source restructure / dropping PaddleOCR — Plan 006_4.
4. The resolver's matching strategy ladder — unchanged; only its equation
   number extractor is already convention-agnostic and stays as-is.
5. Phase 3 block-level ConsensusIR — untouched.

Hard constraints:

1. No regression on DeepSeek equation resolution (currently ~95%).
2. No regression on any non-equation marker type across all three examples.
3. No new third-party dependency.

Allowed dependencies: none beyond the existing standard library + pydantic.

---

## 5. File whitelist and forbidden files

The agent may modify only:

```text
src/pdf2md/connectors/common.py
src/pdf2md/semantic/resolver.py
tests/test_semantic_resolver.py
tests/test_connector_common.py
run_log.md
```

The agent must NOT modify:

```text
src/pdf2md/consensus/*           (Phase 3 block-level — untouched)
src/pdf2md/semantic/ensemble.py
backend/*
ROADMAP.md  project.md  README.md  PLAN_TEMPLATE.md
webui/cross_ref/data/*           (regenerated by the bench scripts, not edited)
```

---

## 6. Agent tasks

### Task A1 — Convention-agnostic equation-number extraction

Title:
Extend the equation_number extractor to every observed surface form.

Files allowed:
```text
src/pdf2md/connectors/common.py
tests/test_connector_common.py
```

Implementation requirements:

1. Tolerate whitespace in the LaTeX tag form: `\tag\s*\{(<EQ_NUM>)\}`
   (MinerU emits `\tag {2.3}`).
2. Recognise an equation line that carries a `\tag{N}` / `\tag {N}` even when
   the line is NOT wrapped in `\[ \]` or `$$`. Concretely: if a PARAGRAPH /
   FORMULA block's text contains a `\tag{...}` or ends in a display number
   `(N)` AND looks like math (contains a LaTeX control sequence such as
   `\frac`, `\sum`, `=`, `\chi`, etc.), classify it as an equation and
   attach the number. Keep the existing bib-entry guard so `[14] Smith ...
   2020.` is never mis-tagged.
3. Preserve the existing `_EQ_NUM` letter-prefix support (`J.4`, `E.11`).
4. Document each accepted convention with a one-line comment + the backend
   that emits it.

Automated tests required:
```text
tests/test_connector_common.py:
  - \tag {2.3}  (space) → equation_number == "2.3"
  - bare line "\chi = \frac{...}, \tag {2.3}" (no delimiters) → equation entity
  - regression: DeepSeek "\[ ... \quad (11) \]" still → "11"
  - regression: a bibliography line ending "(2020)" is NOT an equation
```

Human verification required:
no. Covered by H1.

---

### Task A2 — Fragmented display-equation merge — DEFERRED (no corpus case)

Title:
Merge adjacent FORMULA fragments belonging to one numbered display equation.

Status: **deferred during implementation — the pattern does not occur in the
available corpus.** Investigation on 2026-05-28:

```text
align/aligned/split/gather environments in mineru example01:  0
align/aligned/split/gather environments in mineru example3:   0
multi-$$ FORMULA runs on example01 mineru page 1:             4
  → ALL fragments are unnumbered ($$ \tilde\sigma... $$ split
    across two $$ blocks, no (N) / \tag{N} on EITHER fragment)
74 unnumbered equation entities on example3 mineru:
  → genuinely unnumbered display equations ($$ P = -(dE/dΩ) $$);
    the book does not number them, so there is no number to merge in.
```

A2's premise was "merge a run where ONLY THE LAST fragment carries the
number, propagating it to the whole." No such run exists in either example —
the fragmented runs are uniformly *unnumbered*, so merging them would add no
`equation_number` and produce zero resolution gain, while adding non-trivial
merge-correctness risk. Per the project's "no features for hypothetical
requirements" rule, A2 is NOT implemented.

If a future fixture surfaces a real numbered-align* split, reopen A2 with that
fixture as the driving test. The A1 pass criterion (below) is already met
without A2.

Human verification required:
no.

---

## 7. Human verification checkpoint H1

Title:
Re-bench equation resolution with MinerU candidates.

Required environment:
pdf2md (no OCR backends — uses cached markdown under
`pdf2md/.tmp/papers_run/example{01,02,3}/`).

Preconditions:
Tasks A1–A2 complete.

Procedure:

1. Regenerate the connector entities for the three examples from cached
   markdown.
2. Regenerate the resolved-with graphs for `*+mineru`.
3. Compare equation resolution rate before/after for MinerU on each example.

Pass criteria:

```text
MinerU equation resolution on example3 rises from ~1% to > 80%.
DeepSeek equation resolution unchanged (~95%, no regression).
Non-equation marker types (bibliography / section / figure / table)
  byte-identical resolution counts on all three examples.
Full test suite green.
```

Fail criteria:

```text
Any non-equation type's resolution count changes.
DeepSeek equation resolution drops.
MinerU equation resolution stays < 50% on example3 (extraction still
  missing a convention — investigate which).
```

Evidence to record:

```text
Per-example, per-backend equation resolved/total before and after.
Count of merged_equation_fragments entities produced.
pytest summary line.
```

---

## 8. Test matrix and failure classification

```bash
conda run -n pdf2md pytest tests/test_semantic_resolver.py tests/test_connector_common.py -q
conda run -n pdf2md pytest tests/ -q --ignore=tests/_legacy_temp
```

Failure classes:

* repository_defect — extraction captures the wrong number or mis-merges
  unrelated blocks.
* test_regression — a previously-passing test fails. Revert; this plan must
  not change non-equation behaviour.
* evidence_shortfall — MinerU equation rate doesn't reach target → a
  convention is still unhandled; add it to the A1 table with a fixture.

---

## 9. Checkpoints, push policy, and hand-off

```text
The agent may push the branch and open a PR.
The agent must not merge to main.
The PR diff is connector + resolver + tests only — no behaviour change to
  other detectors, no edits to webui data (those are regenerated artifacts).
```

---

## 10. Report template

```text
Plan: 006_2
Status:
Branch:
Commit or PR:
Conventions added to the extractor:
MinerU equation resolution before / after (per example):
DeepSeek equation resolution before / after (regression check):
Non-equation resolution counts (must be unchanged):
merged_equation_fragments entities produced:
Tests run / passed / failed:
Blockers:
```

Reviewer checklist:

1. Whitelist respected; `consensus/*` untouched.
2. DeepSeek equation resolution did not regress.
3. No non-equation marker type's resolution changed.
4. Each new convention has a unit test + a named backend that emits it.
5. The fragment-merge is conservative (no prose absorbed).
6. Full suite green.

Status history:

```text
2026-05-28 — draft — agent — Plan 006_2 expanded from the plan-set skeleton;
  anchored to PR #136 state (DeepSeek conventions done, MinerU \tag {N} +
  un-delimited lines + align* fragmentation remaining).
2026-05-28 — agent_complete — agent — A1 implemented (\tag {N} whitespace +
  un-delimited math-line detection via _looks_like_math). A2 deferred: no
  numbered-align*-fragment case exists in example01/02/03 (0 align envs;
  multi-$$ runs are uniformly unnumbered). MinerU equation-number coverage
  on example3: 15/1122 → 1048/1122 (93%); GROBID equation markers resolve
  64/64 against MinerU (was ~0). DeepSeek unchanged. 6 new connector tests;
  full suite 1146 → 1152 passed.
```

---

## 11. Design notes

### Why this is candidate-construction, not resolver logic

The resolver's `_extract_equation_number` (`semantic/resolver.py`) already
finds a number anywhere in a label via `(?:[A-Z]\.)?\d+(?:\.\d+)*`. Equation
matching works the moment a candidate carries a number in its label. The
failure is upstream: `recognize_entities` never writes `equation_number` into
MinerU equation entities, so `_equation_label` returns `None` and the candidate
is dropped before it ever reaches the resolver. Fixing the extractor fixes the
whole chain.

### The two MinerU-specific surface forms (concrete)

From the example3 cached markdown:

```text
1711:  \chi = \frac {N (0)}{1 - I N (0)}, \tag {2.3}
```

Two defects in one line:
* `\tag {2.3}` has a space — PR #136's `\\tag\{` regex requires no space.
* The line has no `\[ \]` / `$$` wrapper — `classify_block` returns PARAGRAPH,
  so the equation detector's `block.kind == FORMULA` gate is never satisfied.

Both must be handled for MinerU equations to surface a number.

### Why MinerU as default matters (forward link to 006_4)

MinerU is the intended production default candidate source (006_4). Equation
resolution is the one dimension where it currently looks far worse than
DeepSeek, and that gap is purely a normalisation artifact. Closing it here
unblocks 006_4's "MinerU default" decision on equal footing.
