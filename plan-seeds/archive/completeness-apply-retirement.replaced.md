> **Replaced**: this file has been superseded by `docs/implementation-plans/2-completeness-apply-retirement.md`.
> Preserved here for history; do not edit.

## Outcome

`plan-tool` will no longer auto-apply a conceptual (`plan-correctness` /
`plan-completeness`) finding anywhere. `completeness-apply` — its interactive
walk and its `--jobs N` blind-apply mode — and `direct-run` / `direct-jira`,
which exist only to chain that auto-apply into an unattended pipeline, are
retired. Every conceptual finding is reported for whatever is driving
`plan-tool` — a human at a TTY, or an orchestrating Codex/Claude Code session —
to read and hand-edit. Existing saved reports, run logs, and legacy artifacts
remain readable.

## Overview

`completeness-audit` already applies only its own deterministic
well-formedness findings during `--iterate`; conceptual gaps are persisted
unapplied by design (BACKLOG #85, the read-only-audit split). `completeness-apply`
(`plan_tool/cli/completeness_cmd.py:cmd_completeness_apply`) is the sole
mutator of those conceptual gaps, walking each through
`plan_tool/launcher.py:apply_finding` either interactively (`--jobs 1`, a
human-reviewed apply/skip) or blind (`--jobs N`, applying every gap with no
judgment). `direct-jira` and `direct-run`
(`plan_tool/cli/direct_cmd.py:cmd_direct_jira`/`cmd_direct_run`) chain
`create → detail → completeness-apply → {jira, run --all --commit →
reconcile-code}` in one unattended process specifically so a small plan can
ship with nobody reviewing the conceptual gaps in between.

This repo's own `CLAUDE.md` already documents why the blind and unreviewed
paths are unsafe for a Claude session driving the tool: `completeness-apply`'s
non-interactive skip silently drops pending gaps, and its `--jobs N` path
applies every gap with no judgment (§ "Distinguish a Claude-session-driven run
from a human operator"). The session-driven half of that split — hand-apply by
reading the report yourself — becomes, with this change, the *only* apply
path there is; nothing in the tool applies a conceptual finding unattended
anymore, for a human or a session.

## Problem statement

Two commands currently let a conceptual finding be applied without anyone
judging it: `completeness-apply --jobs N`, and `direct-run`/`direct-jira`,
which use exactly that mode as their mid-chain stage
(`plan_tool/cli/direct_cmd.py` docstrings: "commits mid-chain because
`completeness-apply --jobs N` isolates its workers in worktrees cut off
HEAD"). This repo's own `CLAUDE.md` currently calls the two direct commands a
deliberate carve-out because they are "designed for small unattended runs."
This effort removes the carve-out along with the mechanism it depended on:
without unattended auto-apply, `direct-run`/`direct-jira` are not doing the
thing they were built to do, so both retire rather than being narrowed.

## Architecture

`completeness-apply` and `direct-run`/`direct-jira` stop being recognized CLI
commands. Their parser entries, help text, and CLI reference pages are
removed, not left as a silent no-op. A saved report's "Suggested next steps"
continuation text (`plan_tool/completeness_report.py`) stops recommending
`completeness-apply` and instead points at reading the report and editing the
plan/detail files directly — the existing wording this repo's own workflow
docs already use for the session-driven path.

`plan_tool/launcher.py:apply_finding` — the underlying mutator — is untouched
by this effort. It has callers outside `completeness-apply`/`direct-run`/
`direct-jira` (create's own `--iterate`, detail's own `--iterate`,
`run --mode reconcile`/`reconcile-plan-walk`/`detail --reconcile`), and this
plan makes no claim about whether those callers share the same
unattended-application problem. BACKLOG #369 inventories them separately;
until that inventory ships, this plan changes none of their behavior.

Existing saved reports, run logs, and `plan-details/*/reports/` artifacts
remain readable exactly as today — this is a command retirement, not a data
migration. No compatibility shim re-creates `completeness-apply`'s behavior
under a new name or flag.

## In scope

- `completeness-apply` (both `--jobs 1` interactive and `--jobs N` blind
  modes) and its dispatcher.
- `direct-run` and `direct-jira` in full, including their size-gate and
  multi-plan-split behavior that has no analog once the mid-chain apply stage
  is gone.
- The saved-report continuation text that currently recommends
  `completeness-apply` as a next step.
- Every active (non-historical) doc, prompt, and CLI reference page that
  documents, recommends, or distinguishes these commands: this repo's own
  `CLAUDE.md`, `integrations/shared/DIRECTIVES.md`, `TESTING.md`,
  `docs/ARCHITECTURE.md`, `docs/GATES.md`, `docs/AUDIT_FLOW.md`,
  `docs/COMMANDS.md`, `docs/WORKFLOWS.md`, `USE_CASES.md`, `CAPABILITIES.md`,
  `RUNBOOK.md`, `CONTRIBUTING.md`, and `docs/cli/`.
- Their regression coverage, narrowed to prove the commands are gone and that
  legacy report/run-log reading is unaffected.

## Out of scope

`apply_finding`'s use inside create's own `--iterate`, detail's own
`--iterate`, `completeness-audit`'s own deterministic well-formedness
auto-fix, and `run --mode reconcile`/`reconcile-plan-walk`/`detail --reconcile`
(BACKLOG #369's territory — this plan does not presume they share the same
problem and does not change them). Rewriting or migrating historical saved
reports merely to remove `completeness-apply` vocabulary from their own text.
A CI gate, a provider integration, or any generic workflow-engine
abstraction. Reader-only documentation for surfaces this plan does not touch.

## Risks

Removing `direct-run`/`direct-jira` removes the only unattended small-run path
those two commands offered; this is the owner-confirmed, intended effect
(BACKLOG #367), not an oversight to mitigate. The larger risk is a hidden
consumer surviving the sweep: `plan_tool/launcher.py:apply_finding` is a
shared engine, so a naive removal that deletes `cmd_completeness_apply`
without also removing `direct_cmd.py`'s calls into it, or that leaves a
parser alias, a golden-help fixture, or a doc pointer behind, reads as
finished while a caller or a doc still assumes the retired command exists.
Sweep by both identifier (`completeness-apply`, `completeness_apply`,
`direct-run`, `direct_run`, `direct-jira`, `direct_jira`) and vocabulary
("unattended", "blind apply", "small unattended runs") per CLAUDE.md's
class-sweep rule, not just the cited call sites.

## Testing

Prove the parser no longer recognizes `completeness-apply`, `direct-run`, or
`direct-jira` (including every former flag/mode combination they accepted),
that `plan_tool/cli/direct_cmd.py` and
`plan_tool/cli/completeness_apply_parallel.py` are gone or reduced to nothing
these commands need, and that no remaining production code path calls
`cmd_completeness_apply`. Prove a saved report's continuation text no longer
suggests the retired commands. Prove every doc/reference page in scope no
longer instructs or recommends them, while an unrelated mention of
`apply_finding` in create/detail/reconcile context is left untouched. Prove
existing saved reports, run logs, and `plan-details/*/reports/` artifacts
from before this change still read correctly. Run the full suite
(`uv run pytest tests/ -q -n auto`) green at completion.

## Acceptance criteria

- `plan-tool completeness-apply`, `plan-tool direct-run`, and
  `plan-tool direct-jira` are no longer recognized subcommands, at every flag
  combination they previously accepted.
- No production code path constructs an unattended, unjudged application of a
  conceptual finding; `apply_finding` remains reachable only through
  interactive human/session-driven paths this plan does not remove.
- Saved-report continuation guidance, `docs/cli/`, and every doc/prompt named
  In scope describe hand-applying conceptual findings as the only path, with
  no reference to the retired commands remaining in live (non-historical)
  prose.
- Legacy saved reports, run logs, and detail-bundle artifacts remain readable
  unchanged.
- BACKLOG #367 is marked shipped/removed with this plan's name, and BACKLOG
  #369 is left exactly as it was (unassigned, independent).
- Focused tests and the full suite are green.

## Deferred

BACKLOG #369's inventory of `apply_finding`'s other callers (create, detail,
generic review, reconcile) is separate work this plan does not fold in. Any
caller #369 later finds to share this problem becomes its own backlog item,
not a late addition here.

## References

- `BACKLOG.md` #367 — the owner-confirmed decision this seed elaborates,
  including the direct-run/direct-jira retire-outright disposition and its
  rationale.
- `BACKLOG.md` #369 — the separate, non-removing inventory of
  `apply_finding`'s other callers.
- `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md`
  item 10 — the withdrawn evaluator decision that motivated returning to
  direct retirement.
- `CLAUDE.md` § "Distinguish a Claude-session-driven run from a human operator
  using `plan-tool`" — the existing session-vs-human split this plan makes
  universal by removing the unattended alternative.
- `plan_tool/cli/direct_cmd.py` — `direct-run`/`direct-jira`'s docstrings
  naming `completeness-apply --jobs N` as their load-bearing mid-chain stage.
- `CLAUDE.md` § "Driving the convergence loops" — the carve-out this plan
  removes, describing `direct-run`/`direct-jira` as "designed for small
  unattended runs."
