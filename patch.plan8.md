# Manual patch for Plan 8

Target file:

```text
plans/plan-8-groundtruth-validation.md
```

Purpose:

Clarify that Plan 8 may perform two narrow documentation consistency fixes before activation:

1. Update README.md Section 12 only, to remove obsolete validator/generator flags from the `tools/local_groundtruth_validate.py` example, especially `--run-validator`.
2. Update agent.md only, to add a compatibility note explaining that PLAN_TEMPLATE.md governs lifecycle/checkpoint terminology for template-based plans where it conflicts with older agent.md terminology.

Do not update ROADMAP.md, project.md, current_plan.md, next_plan.md, PLAN_TEMPLATE.md, or any code outside the existing Plan 8 whitelist.

---

## Patch 1 — Sequence wording

Find:

```text
Sequence:
Plan 8 of the MVP implementation plan sequence.
```

Replace with:

```text
Sequence:
Plan 8 of the pre-MVP implementation sequence, ending at Plan 16.
```

---

## Patch 2 — Purpose section

Find this paragraph:

```text
It also performs a narrow documentation consistency check to ensure that the remaining legacy documentation files do not contradict ROADMAP.md.
```

Replace with:

```text
It also performs a narrow documentation consistency check. That check is limited to legacy documentation, agent governance compatibility, and one README command example that still documents an obsolete validator flag.
```

---

## Patch 3 — Section 4, In scope

Find item 10:

```text
10. Perform narrow documentation consistency edits if ROADMAP.md is contradicted by allowed documentation files.
```

Replace with:

```text
10. Perform narrow documentation consistency edits if ROADMAP.md or PLAN_TEMPLATE.md is contradicted by allowed documentation files.
11. Align README.md Section 12 with the inspect-only Plan 8 CLI by removing the obsolete `--run-validator` example flag if present.
12. Add a narrow compatibility note to agent.md if its older mode/status terminology conflicts with PLAN_TEMPLATE.md for template-based plans.
```

---

## Patch 4 — Section 4, Out of scope

Find:

```text
14. Changing ROADMAP.md.
15. Changing README.md.
16. Changing project.md.
17. Changing current_plan.md.
18. Changing next_plan.md.
```

Replace with:

```text
14. Changing ROADMAP.md.
15. Changing README.md outside Section 12.
16. Changing project.md.
17. Changing current_plan.md.
18. Changing next_plan.md.
```

---

## Patch 5 — Section 5, documentation whitelist

Find:

```text
README_latex_docling_groundtruth.md
docs/docling_layer.md
history.md
agent.md
```

Replace with:

```text
README_latex_docling_groundtruth.md
docs/docling_layer.md
history.md
agent.md
README.md
```

Then replace the paragraph immediately below it:

```text
Documentation edits are allowed only to remove direct contradiction with ROADMAP.md, mark legacy material as legacy, or clarify source-of-truth hierarchy. Broad rewriting, style polishing, and new architectural claims are out of scope.
```

with:

```text
Documentation edit limits:

```text
README_latex_docling_groundtruth.md:
  Only to remove direct contradiction with ROADMAP.md or clarify the ground-truth corpus role.

docs/docling_layer.md:
  Only to mark legacy material as legacy or clarify its relationship to the current canonical Docling export path.

history.md:
  Only to add or correct completed governance milestones such as ROADMAP.md or PLAN_TEMPLATE.md if missing.

agent.md:
  Only to add a narrow compatibility note that, for plans written using PLAN_TEMPLATE.md, the PLAN_TEMPLATE.md lifecycle, checkpoints and human-verification rules supersede older status terminology where they conflict.

README.md:
  Only Section 12, only to align the `tools/local_groundtruth_validate.py` example with the Plan 8 inspect-only CLI by removing obsolete validator/generator flags such as `--run-validator`.
```

Broad rewriting, style polishing, and new architectural claims are out of scope.
```

Important: because this patch block contains nested markdown fences, use a text editor carefully when applying it.

---

## Patch 6 — Section 5, forbidden files

Find:

```text
The agent must not modify these files:
```

Replace with:

```text
The agent must not modify these files, except where explicitly allowed above:
```

Then remove this line from the forbidden file list:

```text
README.md
```

Do not remove any of these forbidden files:

```text
ROADMAP.md
PLAN_TEMPLATE.md
project.md
current_plan.md
next_plan.md
```

---

## Patch 7 — Task A4 title and goal

Find:

```text
Goal:
Ensure allowed documentation files do not contradict ROADMAP.md.
```

Replace with:

```text
Goal:
Ensure allowed documentation files do not contradict ROADMAP.md, PLAN_TEMPLATE.md, or the inspect-only Plan 8 CLI.
```

---

## Patch 8 — Task A4 allowed files

Find:

```text
README_latex_docling_groundtruth.md
docs/docling_layer.md
history.md
agent.md
```

Replace with:

```text
README_latex_docling_groundtruth.md
docs/docling_layer.md
history.md
agent.md
README.md
```

---

## Patch 9 — Task A4 implementation requirements

Find the current Task A4 implementation requirements and replace them with:

```text
1. Read each allowed documentation file and compare key claims against ROADMAP.md, project.md, PLAN_TEMPLATE.md, and this plan.
2. In `README_latex_docling_groundtruth.md`, ensure ground truth is not described as temporary if ROADMAP.md treats it as the calibration corpus.
3. In `docs/docling_layer.md`, mark legacy Docling inspection paths as legacy or clarify their relationship to the current canonical export path.
4. In `history.md`, update only if it omits already-completed roadmap governance milestones such as ROADMAP.md or PLAN_TEMPLATE.md.
5. In `agent.md`, add a narrow compatibility note if older mode, status, run_log, or review terminology conflicts with PLAN_TEMPLATE.md for template-based plans.
6. In `README.md`, edit only Section 12 to ensure the `tools/local_groundtruth_validate.py` example matches the inspect-only Plan 8 CLI and does not include `--run-validator`, generator, compiler, or validator flags.
7. Do not perform style-only edits.
8. Do not edit README.md outside Section 12.
9. Do not edit project.md, ROADMAP.md, current_plan.md, or next_plan.md.
10. If no contradictions exist, record “no contradictions found” in the agent report and make no documentation changes.
```

---

## Patch 10 — H4 command

Find:

```bash
git diff -- README_latex_docling_groundtruth.md docs/docling_layer.md history.md agent.md
```

Replace with:

```bash
git diff -- README.md README_latex_docling_groundtruth.md docs/docling_layer.md history.md agent.md
```

---

## Patch 11 — H4 verification procedure

Find H4 verification procedure and replace it with:

```text
1. Inspect the diff for each changed documentation file.
2. Confirm each change is limited to one of:
   source-of-truth hierarchy,
   legacy Docling layer clarification,
   ground-truth corpus role,
   history update for ROADMAP.md or PLAN_TEMPLATE.md,
   PLAN_TEMPLATE.md compatibility note in agent.md,
   README.md Section 12 CLI alignment.
3. Confirm README.md changes, if any, are limited to Section 12 and remove obsolete validator/generator flags from the `tools/local_groundtruth_validate.py` example.
4. Confirm agent.md changes, if any, are limited to a compatibility note for PLAN_TEMPLATE.md-based plans.
5. Confirm there are no broad style-only rewrites.
6. Search for outdated claims:

```bash
grep -R "PDF-to-Markdown only\|scanned image PDFs only\|Docling later\|semantic_document.json is canonical\|temporary ground truth\|--run-validator" README.md README_latex_docling_groundtruth.md docs/docling_layer.md history.md agent.md
```

7. Confirm either no matches exist, or matches are explicitly marked as legacy, non-canonical, or outside the Plan 8 local_groundtruth_validate.py example.
```

Important: because this patch block contains nested markdown fences, use a text editor carefully when applying it.

---

## Patch 12 — H4 pass criteria

Find H4 pass criteria and replace them with:

```text
Documentation changes are narrow.
No allowed doc contradicts ROADMAP.md, project.md, PLAN_TEMPLATE.md, or the Plan 8 CLI.
Legacy paths are marked as legacy or non-canonical.
README.md changes, if any, are limited to Section 12.
README.md Section 12 no longer documents --run-validator for tools/local_groundtruth_validate.py.
agent.md has no unqualified contradiction with PLAN_TEMPLATE.md for template-based plans.
No ROADMAP.md, project.md, current_plan.md, or next_plan.md change is included.
```

---

## Patch 13 — H4 fail criteria

Find H4 fail criteria and replace them with:

```text
Documentation diff contains broad rewrites.
A doc still contradicts ROADMAP.md or PLAN_TEMPLATE.md.
README.md is changed outside Section 12.
README.md still documents --run-validator for tools/local_groundtruth_validate.py.
A canonical claim points to an obsolete path.
Forbidden documentation files are modified.
```

---

## Patch 14 — Reviewer checklist

In the reviewer checklist, after the item about documentation edits staying narrow, add:

```text
Were README.md edits, if any, limited to Section 12 and CLI flag alignment?
Was agent.md updated only with a PLAN_TEMPLATE.md compatibility note, if needed?
```

---

## Expected final constraints

After applying the patch:

```text
Allowed narrow README.md edit:
  README.md Section 12 only, for local_groundtruth_validate.py CLI flag alignment.

Allowed narrow agent.md edit:
  compatibility note for PLAN_TEMPLATE.md-based plans only.

Still forbidden:
  ROADMAP.md
  project.md
  current_plan.md
  next_plan.md
  PLAN_TEMPLATE.md
```

The Plan 8 CLI remains inspect-only and must not include `--run-validator`.
