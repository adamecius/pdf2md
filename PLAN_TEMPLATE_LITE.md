# PLAN_TEMPLATE_LITE.md

Use this abbreviated template for docs-only, governance-only, and low-risk small changes where the full `PLAN_TEMPLATE.md` would be disproportionate. Lite plans are not an escape hatch: they use the same status values, mode rules, whitelist discipline, dependency graph, failure taxonomy, review expectations, and hand-off protocol as the full template.

Choose the full `PLAN_TEMPLATE.md` instead when the plan changes production source code, introduces dependencies, changes backend/runtime behavior, requires more than one substantial human checkpoint, or creates a new long-lived subsystem.

Plan ID and title:
Plan X — Short Descriptive Name

Status:
draft

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
Phase N — Phase name, or `governance/docs only`

Owner:
Agent team / human reviewer

Dependency graph:

```text
depends_on: []
supersedes: []
related_parallel_plans: []
next_plan_after_completion: none | Plan Y — Name
```

Branch name:
plan-X-short-name

---

## 1. Purpose and scope

Describe in one paragraph what this small plan makes true and why a lite plan is sufficient.

In scope:

```text
- <item>
```

Out of scope:

```text
- production source-code changes unless explicitly justified
- dependency or environment changes unless explicitly declared below
```

State-surface impact:

```text
STATE.md update required: yes | no
Reason: <why subsystem status/in-flight/next action changes or does not change>
```

---

## 2. Whitelist, dependencies, and constraints

Files the agent may create or modify:

```text
allowed/path.md
run_log.md
```

Files explicitly forbidden:

```text
src/**
backend/**
<other files>
```

Allowed Python dependencies:

```text
none
```

Allowed external tools and environment-modifying commands:

```text
none
```

Hard constraints:

```text
- Do not modify files outside the whitelist.
- Do not edit production source code for docs/governance-only plans.
- Do not mark `human_verified` or `finished`; those remain human/hand-off actions.
- If scope grows beyond this template, stop and convert to the full PLAN_TEMPLATE.md.
```

---

## 3. Agent tasks

Task L1:

```text
title: <short title>
goal: <concrete result>
files allowed: <subset of whitelist>
requirements:
  - <requirement>
automated checks:
  - <exact command, or `git diff --check` / `git status --short` for docs-only>
completion evidence:
  - files changed
  - commands run and exit codes
  - blockers, if any
```

Add Task L2/L3 only when necessary. If the plan needs many tasks, use the full template.

---

## 4. Verification checkpoint

Lite plans must have at least one exact checkpoint.

Checkpoint H1:

```text
purpose: <what the reviewer confirms>
verification surface: cli | document_review | in_product
verification artifact: <plan_id>.verification.json | path/to/artifact | none with reason
required environment: <environment or `none`>
preconditions: <required state>
exact command: <command, or `document review only`>
input files: <files reviewed>
expected output files: <files/artifacts expected, or `none`>
verification procedure:
  - <step>
pass criteria:
  - <criterion>
fail criteria:
  - <criterion>
evidence to record:
  - <evidence>
```

Failure classes are inherited from `PLAN_TEMPLATE.md`: `repository_defect`, `environment_missing`, `test_expectation_wrong`, `human_procedure_error`, `upstream_dependency_issue`, `permission_or_filesystem_error`, and `timeout`.

---

## 5. Hand-off and reviewer checklist

Before review:

```text
- all lite tasks attempted
- all automated checks run or classified
- no forbidden files modified
- run_log.md or PR body records `mode`, branch, changed files, checks, and blockers
```

Before archival/promotion:

```text
- status is human_verified
- history.md is appended when this is a milestone-level change
- STATE.md is updated when the plan changed subsystem status, in-flight work, or next action
- next_plan.md is promoted only when the plan names a next plan and the human authorizes promotion
```

Reviewer checklist:

```text
- Is lite scope still appropriate, or should this have used PLAN_TEMPLATE.md?
- Did the agent modify only whitelisted files?
- Were exact checks run and recorded?
- Was the verification surface/artifact recorded?
- Is the dependency graph accurate?
- Is STATE.md updated or explicitly not needed?
- Is it safe for a human to mark human_verified?
```
