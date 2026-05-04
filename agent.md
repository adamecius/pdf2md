# AGENT.md

Generic protocol for any LLM-based coding agent (Claude Code, Codex, Gemini CLI, etc.) operating on this repository.

## 1. Canonical files

The agent must read these before any action:

- `project.md` — global project context (what, why, architecture).
- `history.md` — completed milestones, append-only log.
- `current_plan.md` — sole authoritative source for current work (goal, tasks, tests, whitelist, PR_reviews, feedback).
- `run_log.md` — evidence log of agent runs. Whitelisted in every plan by default.

`current_plan.md` declares:

- a single `goal`,
- the `whitelist` of files that may be created or modified,
- the ordered `tasks`,
- the `tests` that define completion (automated by default, possibly tagged human),
- the `PR_reviews` section, appended only by review mode,
- the `feedback` section, appended only by feedback mode.

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
- New package can be added, it shall be also reported.
- Mark tasks as done. Agent reports task attempts in run_log.md; only review mode promotes a task to done in current_plan.md.

Forbidden:

- Modify `current_plan.md` (goal, whitelist, tasks, tests, PR_reviews, feedback) for any reason.
- Modify `project.md`, `history.md`, or `agent.md`.
- Touch any file not in the whitelist, including formatting, lint, or refactor sweeps.
- Invent tests not declared in the plan.
- Retry a test that failed with an environmental error after re-tagging it.

Test handling:

- An automated test that fails for environmental reasons (missing CUDA, missing conda env, no network, missing license) is re-tagged as `human` only in `run_log.md` for that PR. The plan stays untouched.
- A real failure (logic, regression) is reported as such and the agent halts the affected task chain.

Blockers:

- If the plan is internally inconsistent, missing prerequisite information, or asks for files not in the whitelist, the agent writes a `blockers` entry in `run_log.md` and halts. It does not patch the plan.

Completion:

- When all automated tests in the plan pass and no blockers remain, the agent appends `status: ready_for_review` to its PR entry in `run_log.md`.

### 2.2 Review mode

Purpose: verify that the most recent agent-mode PR respected the plan.

Allowed:

- Read all canonical files, the working tree, the diff of the PR under review, and `run_log.md`.
- Write exactly one section appended to `current_plan.md`, titled `## PR_review #N`, where `N` matches the PR number from `run_log.md`.
- Append exactly one section to current_plan.md titled ## PR_review #N, where N matches the PR number from run_log.md.
- Update the ## Status section of current_plan.md, promoting tasks to done only when the PR's verdict is pass and the task's automated tests are all green. Review never demotes; only feedback can.


Forbidden:

- Modify any file other than that single appended section in `current_plan.md`.
- Modify the goal, tasks, tests, whitelist, or any other PR_review or feedback section.
- Re-run tests not defined in the plan.
- Modify any file other than current_plan.md, and within current_plan.md only the appended ## PR_review #N section and the ## Status section.

Required checks:

1. Every modified or created file is in the plan whitelist.
2. Every plan task has a corresponding evidence entry in `run_log.md`.
3. Every automated test was executed; failures are properly classified.
4. Tests re-tagged human in the log have a plausible environmental cause; if the cause looks like a real failure being hidden, the review flags it.
5. No silent retries, no auto-passing.
6. Determine which tasks are eligible for done promotion: a task is eligible iff (a) every automated test attached to it in the plan executed and passed, (b) no whitelist violation involves files for that task, (c) the PR verdict is pass. Tasks with attached human tests are eligible on automated tests alone; the human tests gate archive plan, not task done.

PR_review section content:

- `verdict`: `pass` or `fail`.
- `whitelist_violations`: list of out-of-scope file changes, if any.
- `test_contract_violations`: list of skipped or mis-tagged tests.
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
  - close out PR_review entries by appending a `## Feedback #N` section that responds to `PR_review #N`.
  - Demote a task in ## Status from done back to in_progress or pending when human inspection reveals a regression or unmet requirement that review missed. Demotion must be paired with a ## Feedback #N entry explaining the cause.

Forbidden:

- Modify `project.md`, `history.md`, `run_log.md`, `agent.md`, or any source file.

Plan archival (single exception):

- Only feedback mode, only with the explicit human instruction `archive plan`, may:
  1. append a milestone summary to `history.md`,
  2. reset `current_plan.md` to an empty plan template,
  3. reset `run_log.md` to empty for the new plan.

## 3. Hard rules

- Whitelist enforcement is absolute. Before any write, the agent checks the path against the whitelist; if absent, halt.
- The agent never edits its own protocol (`agent.md`).
- Tests live in `current_plan.md` only. Agent and review modes never invent or alter tests.
- Every write is attributable to a task ID from the plan.
- Refactor, format, or lint sweeps outside whitelisted files are forbidden, even if the diff looks tempting.
- Task state lives in ## Status of current_plan.md. Agent mode never writes to it. Review mode promotes only on pass. Feedback mode can demote; only feedback can.

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
    - blockers: []
    - status: in_progress | ready_for_review | halted


## 6. Test taxonomy

Tests are automated by default. A test re-tagged human in run_log.md after a verifiable environmental failure is reported but does not block ready_for_review. Automated tests gate per-task done promotion in ## Status; human tests gate archive plan only.

- `automated`: runnable in the agent's sandbox without external resources beyond the repo and listed dependencies. Default tag.
- `human`: requires a resource the agent cannot provide (GPU, licensed API key, specific backend conda env, network, manual visual check). Either declared `human` in the plan or re-tagged in `run_log.md` after a verifiable environmental failure.

A human-tagged test does not block agent-mode `ready_for_review`. It blocks plan archival, which only feedback mode can perform after the human supplies the result.

## Status

Maintained by review mode. Agent never writes here.

- T1: pending
- T2: pending
- T3: pending
- T4: pending
- T5: pending