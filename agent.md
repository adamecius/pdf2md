# AGENT.md

Generic protocol for any LLM-based coding agent (Claude Code, Codex, Gemini CLI, etc.) operating on this repository.

## 1. Canonical files

The agent must read these before any action:

- `project.md` — global project context (what, why, architecture).
- `history.md` — completed milestones, append-only log.
- `current_plan.md` — sole authoritative source for current work (goal, tasks, tests, whitelist, dependencies, status, PR_reviews, feedback).
- `run_log.md` — evidence log of agent runs. Whitelisted in every plan by default.

`current_plan.md` declares:

- a single `goal`,
- the `whitelist` of files that may be created or modified,
- the optional `dependencies` section listing new Python packages or external tools the plan is allowed to install or use,
- the ordered `tasks`,
- the `tests` that define completion (automated by default, possibly tagged human),
- the `## Status` section, maintained by review mode,
- the `## PR_reviews` section, appended only by review mode,
- the `## Feedback` section, appended only by feedback mode.

## 2. Modes

The agent operates in exactly one mode per session. The mode is declared in the first line of the human invocation as:

- `mode: agent`
- `mode: review`
- `mode: feedback`

If no mode is declared, the agent stops and asks. The agent never silently assumes a mode.

### 2.1 Agent mode

Purpose: execute `current_plan.md`.

Allowed:

- Read all canonical files and the working tree.
- Write only files listed in the plan whitelist.
- Append entries to `run_log.md` for the current PR.
- Run the plan's automated tests after each task and record outcomes.
- Install or use Python packages and external tools, but only when declared in the plan's `dependencies` section or in the current human prompt. All such installs and tool invocations must be reported in `run_log.md` under `dependencies_added` and `external_tools_used`.

Forbidden:

- Modify `current_plan.md` (goal, whitelist, dependencies, tasks, tests, status, PR_reviews, feedback) for any reason.
- Mark tasks as done. Agent reports task attempts in `run_log.md`; only review mode promotes a task to `done` in `current_plan.md`.
- Modify `project.md`, `history.md`, or `agent.md`.
- Touch any file not in the whitelist, including formatting, lint, or refactor sweeps.
- Install or use any Python package or external tool not declared in the plan's `dependencies` section or in the current human prompt. If a task seems to require an undeclared package or tool, the agent writes a blocker in `run_log.md` and halts.
- Invent tests not declared in the plan.
- Retry a test that failed with an environmental error after re-tagging it.

Test handling:

- An automated test that fails for environmental reasons (missing CUDA, missing conda env, no network, missing license) is re-tagged as `human` only in `run_log.md` for that PR. The plan stays untouched.
- A real failure (logic, regression) is reported as such and the agent halts the affected task chain.

Dependencies and external tools:

- The plan's `dependencies` section is the canonical list of Python packages and external tools allowed for the current plan. The current human prompt may add to this list for the duration of the session.
- When the agent installs a Python package declared in `dependencies`, `pyproject.toml` (and any lockfile produced by the package manager) may be modified implicitly, without being listed in the plan whitelist. This is the only file-write exception to the whitelist rule.
- Conflict case: if `pyproject.toml` appears in the plan whitelist *and* the plan also declares packages in `dependencies`, the agent halts and asks the human which mechanism applies. The two channels must not be mixed in a single plan.
- External system tools (e.g., `latexmk`, `lualatex`, `biber`, `apt`, `conda`, `pip`) that change the environment or install software are subject to the same declare-or-halt rule. Read-only tools the plan implicitly relies on (e.g., `pytest`, `git status`) need no declaration.

Blockers:

- If the plan is internally inconsistent, missing prerequisite information, asks for files not in the whitelist, or requires an undeclared package or tool, the agent writes a `blockers` entry in `run_log.md` and halts. It does not patch the plan.

Completion:

- When all automated tests in the plan pass and no blockers remain, the agent appends `status: ready_for_review` to its PR entry in `run_log.md`. It does not mark any task as done; that is review's job.

### 2.2 Review mode

Purpose: verify that the most recent agent-mode PR respected the plan, and update task state accordingly.

Allowed:

- Read all canonical files, the working tree, the diff of the PR under review, and `run_log.md`.
- Append exactly one section to `current_plan.md` titled `## PR_review #N`, where `N` matches the PR number from `run_log.md`.
- Update the `## Status` section of `current_plan.md`, promoting tasks to `done` only when the PR's verdict is `pass` and the task's automated tests are all green. Review never demotes; only feedback can.

Forbidden:

- Modify any file other than `current_plan.md`, and within `current_plan.md` only the appended `## PR_review #N` section and the `## Status` section.
- Modify the goal, tasks, tests, whitelist, dependencies, prior PR_review entries, or feedback entries.
- Re-run tests not defined in the plan.
- Promote a task to `done` if any of its automated tests failed for real reasons or was skipped without environmental justification.

Required checks:

1. Every modified or created file is in the plan whitelist, with the single exception of `pyproject.toml` updated as a result of declared dependencies.
2. Every plan task attempted in this PR has a corresponding evidence entry in `run_log.md`.
3. Every automated test attached to attempted tasks was executed; failures are properly classified.
4. Tests re-tagged human in the log have a plausible environmental cause; if the cause looks like a real failure being hidden, the review flags it.
5. Every package or external tool reported in `run_log.md` was declared in the plan's `dependencies` section or in the prompt of the PR's session. Undeclared installs are flagged.
6. No silent retries, no auto-passing.
7. Determine which tasks are eligible for `done` promotion. A task is eligible iff:
   - every automated test attached to it in the plan executed and passed,
   - no whitelist violation involves files for that task,
   - no undeclared dependency or tool was used by the PR,
   - the PR verdict is `pass`.
   Tasks with attached human tests are eligible on automated tests alone; the human tests gate `archive plan`, not task `done`.

PR_review section content:

- `verdict`: `pass` or `fail`.
- `whitelist_violations`: list of out-of-scope file changes, if any.
- `test_contract_violations`: list of skipped or mis-tagged tests.
- `dependency_violations`: list of installed packages or used tools not declared, if any.
- `tasks_promoted`: list of task IDs promoted to `done` in `## Status` by this review.
- `notes`: brief findings, one bullet each.

### 2.3 Feedback mode

Purpose: incorporate human feedback into the plan.

Allowed:

- Read everything.
- Modify `current_plan.md` only:
  - clarify the goal,
  - add, remove, or edit tasks,
  - add, remove, or edit tests (including tagging tests as human up front),
  - update the whitelist,
  - update the `dependencies` section,
  - close out PR_review entries by appending a `## Feedback #N` section that responds to `PR_review #N`,
  - demote a task in `## Status` from `done` back to `in_progress` or `pending` when human inspection reveals a regression or unmet requirement that review missed. Demotion must be paired with a `## Feedback #N` entry explaining the cause.

Forbidden:

- Modify `project.md`, `history.md`, `run_log.md`, `agent.md`, or any source file.

Plan archival (single exception):

- Only feedback mode, only with the explicit human instruction `archive plan`, may:
  1. append a milestone summary to `history.md`,
  2. reset `current_plan.md` to an empty plan template,
  3. reset `run_log.md` to empty for the new plan.

## 3. Hard rules

- Whitelist enforcement is absolute. Before any write, the agent checks the path against the whitelist; if absent, halt. The single exception is `pyproject.toml` (and lockfiles) when the write is the direct result of a package declared in the plan's `dependencies` or in the current prompt.
- The agent never edits its own protocol (`agent.md`).
- Tests live in `current_plan.md` only. Agent and review modes never invent or alter tests.
- Task state lives in `## Status` of `current_plan.md`. Agent mode never writes to it. Review mode promotes only on pass. Feedback mode can demote; only feedback can.
- New Python packages and environment-modifying external tools require explicit declaration in the plan's `dependencies` section or in the current human prompt; otherwise halt as blocker.
- Every write is attributable to a task ID from the plan.
- Refactor, format, or lint sweeps outside whitelisted files are forbidden, even if the diff looks tempting.
- Prefer extending existing modules over creating new ones. A new file is justified only when the new concept is reused by ≥2 consumers or exceeds ~250 lines of independent logic, or has its own CLI/lifecycle.

## 4. PR numbering

- Each agent-mode session opens PR #N, where N is the next integer after the last entry in `run_log.md`.
- Review mode for PR #N writes `## PR_review #N` in `current_plan.md`.
- Feedback mode responding to PR_review #N writes `## Feedback #N` in `current_plan.md`.
- Numbers are global per plan. They reset only when feedback mode archives the plan.

## 5. Run log format

`run_log.md` is whitelisted by default in every plan. Append-only within a session. One entry per PR:

    ## PR #N — <ISO timestamp> — mode: agent
    - tasks_attempted:
        - T1: files_touched=[...], tests_pass=[A1,A2], tests_fail_env=[A4], tests_fail_real=[]
        - T2: ...
    - dependencies_added: [pikepdf==9.x, pymupdf==1.27.x]
    - external_tools_used: [lualatex, biber]
    - blockers: []
    - status: in_progress | ready_for_review | halted

The agent reports `tasks_attempted`, not `tasks_completed`. Promotion of a task to `done` is review's prerogative and lives in `## Status` of `current_plan.md`, not here. `dependencies_added` lists Python packages installed during this PR. `external_tools_used` lists environment-modifying external commands invoked. Read-only tools (pytest, git status) are not listed.

## 6. Test taxonomy

- `automated`: runnable in the agent's sandbox without external resources beyond the repo and listed dependencies. Default tag.
- `human`: requires a resource the agent cannot provide (GPU, licensed API key, specific backend conda env, network, manual visual check). Either declared `human` in the plan or re-tagged in `run_log.md` after a verifiable environmental failure.

A test re-tagged human in `run_log.md` after a verifiable environmental failure is reported but does not block `ready_for_review`. Automated tests gate per-task `done` promotion in `## Status`; human tests gate `archive plan` only.

A human-tagged test does not block agent-mode `ready_for_review`. It does not block per-task `done` promotion either, provided the task's automated tests pass. It blocks plan archival, which only feedback mode can perform after the human supplies the result.