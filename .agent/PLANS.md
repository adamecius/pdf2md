# Codex Execution Plans (ExecPlans)

This file defines how to write and maintain an ExecPlan for this repository.
An ExecPlan is a self-contained, living specification that a coding agent can follow to deliver observable working behavior.

An ExecPlan is a repository convention, not a built-in Codex primitive. We use it because longer tasks go better when the agent has one file that explains the purpose of the work, the current repository state, the intended behavior, the exact validation commands, and the decisions made during execution.

## When to use an ExecPlan

Use an ExecPlan for any task that is likely to take more than about one hour, any new feature, any refactor touching multiple files, or any change where architecture, sequencing, or verification would otherwise be ambiguous.

You may skip an ExecPlan only for trivial edits such as typos, tiny documentation fixes, or a narrowly scoped one-file change with an obvious validation step.

## Non-negotiable requirements

Every ExecPlan must be self-contained. Assume the reader has only the current working tree, `AGENTS.md`, this file, and the single plan file being executed. Do not rely on hidden memory, prior conversation, or external documents.

Every ExecPlan must be beginner-friendly. Define repository-local terms in plain language. Name repository-relative paths precisely. Do not assume the reader already understands the architecture.

Every ExecPlan must be outcome-focused. Explain what a user will be able to do after the work is complete and how to observe it working.

Every ExecPlan must be verifiable. Include exact commands, where to run them, and what success looks like. Do not write “tested” without showing the command.

Every ExecPlan must be living. Keep the plan current while executing it. At every meaningful stopping point, update the living sections so another agent or a novice human can restart from the plan alone.

## Formatting

Write in plain prose. Prefer short paragraphs and direct instructions over long bullet lists. Use headings to organize the plan and use lists only where they make the plan clearer.

Use two blank lines after every heading.

When showing commands, transcripts, examples, diffs, or code snippets, use indented blocks with four leading spaces rather than fenced code blocks.

## Required sections

Use the following section names unless there is a strong repository-specific reason not to.

### 1. Title

Use a short, action-oriented title.

### 2. Why this exists

Explain the user-visible problem and why the milestone matters now. Start with purpose before implementation detail.

### 3. Scope

State what is in scope and what is explicitly out of scope. This keeps the implementation bounded.

### 4. Current known state

Describe the relevant repository state, file paths, assumptions, and known problems. Treat the reader as new to the repository.

### 5. Target behavior

Describe the observable behavior that should exist after completion. Phrase this in terms of commands a human can run and outputs they can inspect.

### 6. Design and decisions

Explain the implementation approach, interfaces, heuristics, dependencies, tradeoffs, and any assumptions the agent must follow. Resolve ambiguity here instead of leaving it to chance.

### 7. Milestones

Break the work into ordered milestones. Each milestone must end in a checkable state and must say which files are expected to change, what work is done in that milestone, and how to validate it.

### 8. Validation

List the exact commands to run and what success looks like. Validation must prove behavior, not merely that code compiles.

### 9. Risks and rollback notes

Describe likely failure modes, partial-failure states, idempotence, and how to recover safely.

### 10. Progress

This is a required living section. Use checkboxes and timestamps. Every stopping point must be reflected here. Split partially complete work into completed and remaining parts rather than leaving status ambiguous.

### 11. Surprises & Discoveries

This is a required living section. Record unexpected behaviors, bugs, failed assumptions, or important observations, with short evidence.

### 12. Decision Log

This is a required living section. Record each meaningful decision, why it was made, and when.

### 13. Outcomes & Retrospective

This is a required living section. Summarize what was achieved, what remains, and what was learned at major milestones or at the end.

## Milestone rules

Milestones must be sequential, concrete, and independently checkable. A milestone should describe what will exist at the end that did not exist before, which files are likely to change, and at least one validation step that proves the milestone worked.

If a milestone reveals new facts, update the plan before moving to the next milestone. Do not continue on stale assumptions.

When implementing a plan, do not stop after one milestone just to ask what to do next unless you are blocked by a real ambiguity or missing input.

## Validation rules

Validation should be as small as possible while still proving the intended behavior. Good validation includes a package import smoke test, a CLI smoke test, a focused unit test, or a single representative sample input run.

Validation must include the working directory and exact command. When useful, include a short expected transcript so the executor can compare what they saw to what the plan expected.

Prefer observable acceptance statements such as “after running `python -m doc2md input.pdf -o out/`, the file `out/input.md` exists and contains extracted text” over internal claims such as “added a class” or “wired the router.”

## Living-plan rules

An ExecPlan is a working document, not a static spec. While executing it, keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` up to date.

When discussing the plan and changing direction, record the change in `Decision Log` and make the rest of the plan consistent with that decision.

When a design contains unknowns, it is acceptable to add a prototyping milestone that isolates the uncertainty, runs a small experiment, and records the result before full integration.

## Skeleton

Use this template for new plan files.

    # <short action-oriented title>

    This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds. This plan follows the format described in .agent/PLANS.md.

    ## Why this exists

    Explain the user-visible problem and why this work matters now.

    ## Scope

    In scope:
    - ...

    Out of scope:
    - ...

    ## Current known state

    Describe the relevant repository state, assumptions, known problems, and file paths.

    ## Target behavior

    Describe what a user can do after this work and how to observe it.

    ## Design and decisions

    Explain the implementation approach, interfaces, heuristics, dependencies, and tradeoffs.

    ## Milestones

    ### Milestone 1 - <name>

    Files:
    - path/to/file

    Work:
    Describe the edits and additions in prose.

    Validation:

        cd /repo/root
        <command>

    Expected result:
    Describe what should happen.

    ### Milestone 2 - <name>

    Files:
    - path/to/file

    Work:
    Describe the edits and additions in prose.

    Validation:

        cd /repo/root
        <command>

    Expected result:
    Describe what should happen.

    ## Validation

    List the end-to-end validation commands and the expected success signals.

    ## Risks and rollback notes

    Describe failure modes, retry paths, rollback paths, and whether each step is safe to repeat.

    ## Progress

    - [ ] Not started

    ## Surprises & Discoveries

    - None yet.

    ## Decision Log

    - None yet.

    ## Outcomes & Retrospective

    - To be filled during execution and at completion.
