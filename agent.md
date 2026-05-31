# AGENT.md

Generic protocol for any LLM-based coding agent (Claude Code, Codex, Gemini CLI, etc.) operating on this repository.

## 1. Canonical files

The agent must read these before any action:

- `project.md` — global project context (what, why, architecture, open architecture decisions).
- `ROADMAP.md` — durable product roadmap and phase estimates.
- `history.md` — completed milestones, append-only log.
- `current_plan.md` — sole authoritative source for current work (goal, tasks, tests, whitelist, dependencies, status, PR reviews, feedback).
- `next_plan.md` — next planned execution contract to be promoted after the current plan is human-verified and archived.
- `PLAN_TEMPLATE.md` — canonical plan structure, status machine, test matrix, and hand-off sections.
- `run_log.md` — evidence log of agent runs. Whitelisted in every plan by default.

`agent.md` is the operating protocol. `PLAN_TEMPLATE.md` is the plan schema. They must be read together; if they appear to disagree, halt and record the contradiction as a repository defect rather than choosing one silently.

`current_plan.md` declares:

- a single goal;
- the whitelist of files that may be created, modified, moved, or deleted;
- the optional dependencies section listing Python packages or external tools the plan is allowed to install or use;
- the ordered tasks;
- the tests that define completion (automated by default, possibly tagged human);
- the allowed status values and current status;
- PR review and feedback sections or their template-equivalent review checkpoints.

## 2. Modes

The agent operates in exactly one mode per session. The mode is declared in the first line of the human invocation as:

- `mode: agent`
- `mode: review`
- `mode: feedback`

If no mode is declared, the agent stops and asks unless the human explicitly provides a governance or recovery plan that names the mode in prose (for example, "execute this plan in feedback mode"). The agent never silently assumes a mode for ordinary implementation work.

### 2.1 Agent mode

Purpose: execute `current_plan.md`.

Allowed:

- Read all canonical files and the working tree.
- Write only files listed in the plan whitelist.
- Append entries to `run_log.md` for the current PR when the plan allows or implicitly whitelists the evidence log.
- Run the plan's automated tests after each task and record outcomes.
- Install or use Python packages and external tools, but only when declared in the plan's dependencies section or in the current human prompt. All such installs and tool invocations must be reported in `run_log.md` under `dependencies_added` and `external_tools_used`.

Forbidden:

- Modify `current_plan.md` status, tasks, whitelist, dependencies, PR review sections, or feedback sections unless the active plan explicitly authorizes plan/governance edits.
- Mark tasks as done. Agent reports task attempts in `run_log.md`; only review mode or human verification promotes task state.
- Modify `project.md`, `history.md`, `ROADMAP.md`, `README.md`, `PLAN_TEMPLATE.md`, or `agent.md` unless the active plan explicitly authorizes governance/documentation synchronization.
- Touch any file not in the whitelist, including formatting, lint, or refactor sweeps.
- Install or use any Python package or external tool not declared in the plan dependencies section or in the current human prompt. If a task seems to require an undeclared package or tool, the agent writes a blocker in `run_log.md` and halts.
- Invent tests not declared in the plan.
- Retry a test that failed with an environmental error after re-tagging it.

Test handling:

- An automated test that fails for environmental reasons (missing CUDA, missing conda env, no network, missing license) is re-tagged as `human` only in `run_log.md` for that PR. The plan stays untouched unless the plan explicitly authorizes status edits.
- A real failure (logic, regression) is reported as such and the agent halts the affected task chain.

Dependencies and external tools:

- The plan's dependencies section is the canonical list of Python packages and external tools allowed for the current plan. The current human prompt may add to this list for the duration of the session.
- When the agent installs a Python package declared in dependencies, `pyproject.toml` and any lockfile produced by the package manager may be modified implicitly, without being listed in the plan whitelist. This is the only file-write exception to the whitelist rule.
- Conflict case: if `pyproject.toml` appears in the plan whitelist and the plan also declares packages in dependencies, the agent halts and asks the human which mechanism applies. The two channels must not be mixed in a single plan.
- External system tools that change the environment or install software are subject to the same declare-or-halt rule. Read-only tools the plan implicitly relies on (`pytest`, `git status`, `git diff`) need no declaration.

Blockers:

- If the plan is internally inconsistent, missing prerequisite information, asks for files not in the whitelist, or requires an undeclared package or tool, the agent writes a blocker in `run_log.md` and halts. It does not patch the plan unless the session is explicitly in feedback mode and the human directs a governance correction.

Completion:

- When all automated tests in the plan pass and no blockers remain, the agent appends `status: ready_for_review` to its PR entry in `run_log.md` or reports the equivalent evidence in the PR. It does not set `human_verified`; that is a human action.

### 2.2 Review mode

Purpose: verify that the most recent agent-mode PR respected the plan, and update task state accordingly.

Allowed:

- Read all canonical files, the working tree, the diff of the PR under review, and `run_log.md`.
- Append exactly one review section to `current_plan.md`, matching the plan's review format.
- Update the status/task checklist in `current_plan.md`, promoting tasks only when the PR's verdict is `pass` and the task's automated tests are all green or properly classified as environmental/human.

Forbidden:

- Modify any file other than `current_plan.md`, and within `current_plan.md` only the appended review section and status/task state.
- Modify the goal, tasks, tests, whitelist, dependencies, prior review entries, or feedback entries.
- Re-run tests not defined in the plan.
- Promote a task to done if any of its automated tests failed for real reasons or was skipped without environmental justification.

Required checks:

1. Every modified, moved, or created file is in the plan whitelist, with the single exception of `pyproject.toml` updated as a result of declared dependencies.
2. Every plan task attempted in this PR has a corresponding evidence entry in `run_log.md` or the PR report.
3. Every automated test attached to attempted tasks was executed; failures are properly classified.
4. Tests re-tagged human/environment are genuinely outside the agent's control.
5. The diff is minimal and does not include opportunistic refactors.

### 2.3 Feedback mode

Purpose: apply human review feedback, governance corrections, or hand-off/archive actions.

Allowed:

- Read all canonical files and the PR/review context.
- Modify files named by the feedback or by the active governance plan whitelist.
- Append feedback evidence to `run_log.md` when permitted.
- Correct plan/governance files when the feedback explicitly authorizes that correction.
- Execute the hand-off mechanic in §7 after human verification: archive the finished plan, append `history.md`, promote `next_plan.md` to `current_plan.md`, and create a new `next_plan.md`.

Forbidden:

- Expand scope beyond the feedback.
- Edit source code during docs/governance-only plans.
- Set `human_verified`; only the human reviewer can do that.
- Merge to `main`.

Feedback mode must preserve the `PLAN_TEMPLATE.md` status machine. An agent may set `agent_complete`, `human_verification_required`, `blocked`, or `superseded` when authorized by the plan. `human_verified` is reserved for the human, and `finished` is set only as part of the archival hand-off after human verification or by an explicit state-synchronization plan that records already-merged work.

## 3. Whitelist discipline

The whitelist is mandatory. It applies to edits, moves, generated files, formatting changes, and test fixture updates. If a file is not listed and no explicit exception applies, do not touch it.

For governance/state-synchronization plans, the whitelist may include canonical docs and plan archive moves. That exception applies only to the named governance plan and never authorizes source-code edits by implication.

## 4. Evidence and tests

Every run must report:

- branch;
- files changed;
- tasks attempted;
- exact test commands and outcomes;
- skipped/environmental failures with reason;
- source files touched, if any;
- blockers;
- final status.

Docs-only governance plans should still run their declared guard commands when feasible and must at least show `git diff --stat`/`git status --short` proving that only allowed docs/plans changed.

## 5. Failure classification

Use the plan's failure taxonomy when present. Otherwise classify failures as:

- `repository_defect` — code or docs contradict the contract;
- `test_expectation_wrong` — a test or plan assertion does not match intended behavior;
- `environment_missing` — missing tools, environments, models, credentials, or network;
- `upstream` — external service/package failure;
- `timeout` — command exceeded reasonable runtime;
- `permission_or_filesystem_error` — path or filesystem operation failed;
- `human_procedure_error` — required human review/verification was skipped or inconsistent.

## 6. Pull requests

A PR must summarize:

- plan id and status;
- files changed;
- source files touched (explicitly `none` for docs/governance-only plans);
- tests/checks run with outcomes;
- human verification still required, if any;
- blockers or known follow-ups.

Do not claim a human checkpoint passed unless the human supplied the evidence.

## 7. Hand-off and archival protocol

The repository uses the `PLAN_TEMPLATE.md` status-machine + promotion model:

```text
draft -> active -> agent_in_progress -> agent_complete
      -> human_verification_required -> human_verified -> finished
```

Other allowed terminal/exception states are `blocked` and `superseded`.

When the human says a plan is `human_verified` and authorizes archival, feedback mode performs one hand-off transaction:

1. Move the completed plan file into `plans/archive/` and set its `Status:` to `finished` (or `superseded` for an explicitly replaced plan).
2. Append a milestone entry to `history.md` in the existing `M<n>` format, citing PR/commit evidence, tests, key artifacts, and human-verification evidence.
3. Promote `next_plan.md` to `current_plan.md` exactly as the next active execution contract.
4. Create a new `next_plan.md` placeholder or the next human-supplied plan.
5. Reset `run_log.md` only if the promoted plan or human explicitly says to start a fresh evidence log; otherwise preserve it as historical evidence.
6. Confirm with `git status --short` and `git diff --stat` that only intended docs/plans changed.

This protocol replaces the older blank-reset model. Agents must not empty `current_plan.md` as an archive action and must not leave `next_plan.md` unpromoted after finishing a plan.
