> **Replaced**: this file has been superseded by `docs/implementation-plans/archive/2-create-default-test-command.md`.
> Preserved here for history; do not edit.

## Overview

`create` writes `enforce_step_tests: true` on every new plan but never a `test_command`, so new plans gate on *a test file was touched* and never on *the suite still passes*. This plan adds a deterministic, table-driven test-runner detection seam that `create`'s plan assembly consumes, so a plan authored in a repo whose runner is detectable carries a non-empty `test_command` and `run` refuses to advance a step that reddened a module the step never touched. Detection is never a Claude call: a fixed marker table maps repo evidence to a command (`pyproject.toml` + `uv.lock` → `uv run pytest tests/ -q -n auto`, and so on). Ambiguous detection degrades to prompting the operator interactively, and under `--yes` or non-TTY stdin omits the field with one stderr note — `create` still exits 0. Lever (b) ships alongside: `PLAN_FORMAT.md:82`'s stale 24-minute claim is corrected and reconciled with `:84`.

## Problem statement

`create` writes `enforce_step_tests: true` on every new plan (`create.py:6592`) and never writes a `test_command`. New plans therefore gate on *a test file was touched* and never on *the suite still passes* — the exact asymmetry `PLAN_FORMAT.md:84` already prescribes closing ("pair with `test_command` for the latter"). Measured today: nothing populates this field, so **0 of 11** plans have one while **10 of 11** set `enforce_step_tests`.

Commit `08e672ae` is the cost: it added a field to the public coverage projection, updated four test modules, left two assertions red in a module it never touched, and advanced as "step 1 green". The breakage survived four commits and reached two remotes.

`PLAN_FORMAT.md:82` argues against the fix with a stale number — "a 24-minute full-suite run is impractical when it fires after every step". The real cost on this repo at 8004 tests is **46s** with `-n auto` and **184s** serial. That paragraph contradicts `:84`, and the discouraging one is the one that got followed.

## Architecture

Decisions a later reader must not re-litigate.

**Detection is deterministic and table-driven — never a Claude call.** A fixed marker table maps repo evidence to a command (`pyproject.toml` + `uv.lock` → `uv run pytest tests/ -q -n auto`, and so on). A new detection seam owns this; `create`'s plan assembly consumes it.

**A detected command needs no operator vetting; a guessed one does.** This is the trust distinction that shapes the whole feature. `_review_step_gates` drops *model-suggested* `gate:` commands unreviewed because the model may propose anything. A command produced by plan-tool's own fixed table is the same trust class as `enforce_step_tests: true` — emitted directly.

**Ambiguous detection degrades to asking, then to omitting.** Three modes, mirroring `_review_step_gates`' matrix:

- interactive → prompt the operator for the command, checkpointed so `--resume` does not re-ask;
- `--yes` or non-TTY stdin → **omit the field** and name the omission in one stderr note, the `gates_auto_dropped` shape;
- detected → emit, no prompt.

The omit-and-name tail is forced, not chosen: `test_command` is executed via `shell=True` and `PLAN_FORMAT.md:82` names it a code-execution vector, so an unvetted guess carries the same hazard `_review_step_gates` refuses. A wrong command is also worse than none — it fails every step in that repo and teaches operators to strip the field.

**Never emit a placeholder.** The field is executed, so a `_(TODO)_` value is a broken gate, not a reminder. Absence is the only safe unknown.

**Lever (b) ships with (a).** `PLAN_FORMAT.md:82` is corrected and reconciled with `:84` in the same effort. Shipping the default while the doc still calls it impractical re-seeds the contradiction.

**In scope** — `create.py`'s plan assembly and its review/checkpoint family (the seam that already owns `enforce_step_tests` and the suggested-gate review); a new deterministic test-runner detection seam, with the marker table as its contract; `PLAN_FORMAT.md`'s `test_command` and `enforce_step_tests` prose.

**Allowed behavior changes.** Only these: new plans gain a `test_command` when detection is confident; in those plans a red suite then blocks step advancement, including a suite that was *already* red before the plan started. `create` gains one prompt on the ambiguous interactive path and one stderr note on the ambiguous unattended path. No change to any existing plan, or to `run`'s gate mechanics.

**Allowed reorganization.** None beyond adding the detection seam as a new leaf below `create`.

**The binary observable, and what may not be checked.** The check this feature asserts is one fact about state: **the authored plan's `test_command` field is present and non-empty.** Nothing downstream judges its content. Not allowed, and a finding proposing one is invalid rather than deferrable:

- judging whether a detected or operator-supplied command is a *good* test command, or whether the suite it runs is meaningful or adequately covering;
- any agreement check between `test_command` and a repo's CI config, Makefile, or README;
- an exit-code flip or refusal-to-complete on `create` when detection is ambiguous — `create` still completes 0 and simply omits the field;
- a gate, finding, or advisory keyed on an *existing* plan lacking the field.

## Out of scope

- **`run`'s gate semantics** (`launcher.py`). The `test_command` gate already works; this effort only populates the field.
- **The `pre-push` hook** — shipped, and repo-local. Not extended, not re-scoped.
- **Lever (c)**, bounding cost by running the suite only on a step's last attempt. Stays in #234.
- **Retrofitting existing plans.** No migration, no backfill, no requirement on plans authored before this ships.
- **CI adoption.** Still no `.github/`, and this effort does not add one.
- **Detection beyond the fixed table** — no heuristic scoring, no model call, no filesystem crawl for test directories.

## Risks

- A **pre-existing red suite** blocks step 1 of every new plan in that repo. Defensible, and the point — but it is a real behavior change on an already broken tree, and the stderr/`status_note` path must make the cause obvious rather than reading as a plan-tool defect.
- **Detection breadth is the creep vector.** The marker table invites "just one more ecosystem" indefinitely. Ship the table small; new entries are backlog items, not audit findings.
- Added wall-clock per step (~46s here) on long plans.

## Testing

What would prove the Outcome: each marker-table case emits its command; an undetectable repo prompts interactively and honors the answer; the same repo under `--yes` and under non-TTY stdin omits the field and names it; a resumed `create` does not re-ask. The `PLAN_FORMAT.md` correction is checked for drift against the measured figures, not against the withdrawn 24-minute claim.

## Acceptance criteria

- `create` in this repo produces a plan whose `test_command` runs the suite.
- An undetectable repo yields a plan with no `test_command` and a stderr note under `--yes`/non-TTY, and an operator-supplied one interactively.
- `PLAN_FORMAT.md:82` no longer carries the 24-minute claim and no longer contradicts `:84`.
- `BACKLOG.md` **#234** is reconciled when this ships: levers (a) and (b) are removed as delivered, lever (c) is left as the remaining deferred follow-up, and the entry is deleted outright only if nothing remains. Authoring this plan does not discharge that — it lands in the final docs/status step.

## Deferred

Lever (c) cost-bounding; any second ecosystem beyond the initial marker table; CI adoption.
