---
format_version: 1
title: Completeness Apply Retirement
intent: '`plan-tool` retires the dedicated conceptual (`plan-correctness` / `plan-completeness`)
  application commands. `completeness-apply` — its interactive walk and its `--jobs
  N` blind-apply mode — and `direct-run` / `direct-jira`, which exist only to chain
  that auto-apply into an unattended pipeline, are retired. Completeness-audit conceptual
  findings are reported for whatever is driving `plan-tool` — a human at a TTY, or
  an orchestrating Codex/Claude Code session — to read and hand-edit. Create/detail
  deterministic repair and existing reconcile and review routes stay unchanged. Existing
  saved reports, run logs, and legacy artifacts remain readable.'
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/archive/completeness-apply-retirement.replaced.md
steps:
- id: 1
  intent: Every saved report and audit message tells the reader to read the findings
    and edit the plan or detail files themselves, so no guidance points at a command
    that is about to disappear.
  files:
  - plan_tool/completeness_report.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/authoring.py
  - docs/cli/completeness-audit.md
  - docs/cli/detail.md
  - docs/cli/README.md
  - tests/cli/package_surface_help.golden.txt
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_authoring_cmds.py
  - tests/test_cli.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/completeness-apply-retirement/01-point-completeness-reports-audit-stop.md
  status: current
  description: Point completeness reports, audit stop messages, and help text at hand-editing
    instead of completeness-apply, retaining the surviving conceptual hand-edit guidance
    and replacing remaining retired-command remedies
- id: 2
  intent: The direct pipelines exist only to chain unattended conceptual auto-apply,
    and retiring them first leaves cmd_completeness_apply with no caller outside its
    own command.
  files:
  - plan_tool/cli/direct_cmd.py
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/jira_cmd.py
  - plan_tool/cli/run_cmd.py
  - CAPABILITIES.md
  - docs/cli/direct-jira.md
  - docs/cli/direct-run.md
  - docs/cli/README.md
  - tests/cli/package_surface_help.golden.txt
  - tests/cli/test_direct_cmd.py
  - tests/cli/test_cli_reference.py
  - tests/cli/test_cli_parser.py
  - tests/cli/test_run_cmd.py
  - tests/test_cli.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/completeness-apply-retirement/02-retire-direct-run-direct-jira-commands.md
  description: Retire the direct-run and direct-jira commands by deleting plan_tool/cli/direct_cmd.py
    and its parser, dispatch, lock-set, capability, and reference entries (its mid-chain
    authoring and applied-gap commits and relocated-root dirt guard retire with it;
    create, detail, jira, run, and reconcile-code keep their own write paths unchanged)
- id: 3
  intent: No dedicated completeness application command remains; preserved create,
    detail, review, reconcile, and benchmark callers keep their behavior, while reports
    still load through their existing readers.
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_apply_parallel.py
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/__init__.py
  - plan_tool/cli/gitcommit.py
  - plan_tool/cli/review_cmd.py
  - plan_tool/cli/review_actions.py
  - plan_tool/review_walk.py
  - plan_tool/review.py
  - plan_tool/convergence.py
  - plan_tool/convergence_diagnosis.py
  - plan_tool/backend_runner.py
  - plan_tool/claude_errors.py
  - CAPABILITIES.md
  - DATA_CONTRACT.md
  - TESTING.md
  - tests/cli/COVERAGE_BASELINE.md
  - docs/cli/completeness-apply.md
  - docs/cli/README.md
  - tests/cli/package_surface_help.golden.txt
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_completeness_apply_parallel.py
  - tests/test_data_contract.py
  - tests/cli/test_cli_parser.py
  - tests/test_review_persistence.py
  - tests/test_convergence_diagnosis.py
  - tests/test_cli.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: reports and audit output no longer name completeness-apply, so removing it
      leaves no dangling pointer
    2: removes direct_cmd.py, the only caller of cmd_completeness_apply outside its
      own command
  description: Retire the completeness-apply command, both its interactive walk and
    its --jobs N parallel lane, by deleting cmd_completeness_apply, its apply-walk
    helpers in completeness_phases.py, and plan_tool/cli/completeness_apply_parallel.py
    (retires the allowed_mentions files-coherence writer, the --commit commit, parallel
    replay overwrite/restore, and worktree/branch cleanup; apply_finding and its other
    callers stay unchanged; existing saved annotations, sidecars, and run logs stay
    readable)
- id: 4
  intent: Sessions and operators driving plan-tool get one consistent instruction
    — read the report and edit by hand — and no retained rationale still argues for
    a removed command, such as the bare-stage non-block justified by completeness-apply
    being withheld.
  files:
  - CLAUDE.md
  - integrations/shared/DIRECTIVES.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  - integrations/cursor/SKILL.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: direct-run/direct-jira are gone, so the carve-out has nothing left to describe
    3: completeness-apply is gone, so the human-vs-session split collapses to hand-apply
      only
  description: 'Rewrite the driving directives so hand-applying conceptual findings
    is the only path: drop the human-at-a-TTY completeness-apply branch, the direct-run/direct-jira
    unattended carve-out, and completeness-apply from the --commit surface list in
    CLAUDE.md, DIRECTIVES.md, and all three backend SKILL.md files'
- id: 5
  intent: No live doc tells a reader to run completeness-apply, direct-run, or direct-jira,
    or describes them as current architecture, while the doc-reading suites (test_roadmap_format.py,
    test_model_specs.py) stay green.
  files:
  - docs/ARCHITECTURE.md
  - docs/GATES.md
  - docs/how-to/pipeline/audit.md
  - docs/reference/commands.md
  - docs/how-to/use-cases.md
  - RUNBOOK.md
  - CONTRIBUTING.md
  - README.md
  - JIRA_FORMAT.md
  - docs/how-to/pipeline/detail.md
  - docs/how-to/recovery/README.md
  - docs/TRACKING.md
  - docs/demos/roadmap-demo.md
  - docs/GLOSSARY.md
  - docs/how-to/pipeline/direct-pipeline.md
  complexity: high
  change_type: non-code
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: direct pipeline surfaces no longer exist to document
    3: completeness-apply and its parallel module no longer exist to document
  description: Remove retired-command instructions from the reference, workflow, and
    demo docs and delete docs/how-to/pipeline/direct-pipeline.md, leaving historical
    plans, reports, and docs/history/backlog-decisions.md as written
- id: 6
  intent: 'The backlog records the retirement as shipped, stops tracking work on commands
    that no longer exist, and keeps #369''s separate apply_finding inventory independent.'
  files:
  - BACKLOG.md
  - BUG_BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 3
  - 4
  - 5
  depends_on_notes:
    3: 'the last code removal has landed, so #376 is fully shipped'
    4: directive sweep complete
    5: reference-doc sweep complete
  description: 'Close BACKLOG #376 as shipped by completeness-apply-retirement, retire
    or trim backlog entries that exist only for the removed commands, and file follow-ups
    for the now-unreachable granularity-split walk opt-in and stale .plan-tool/lessons/project.md
    entries, leaving #369 exactly as it is'
---
# Completeness Apply Retirement

## Overview

`completeness-audit` already applies only its own deterministic
well-formedness findings during `--iterate`; conceptual gaps are persisted
unapplied by design (BACKLOG #85, the read-only-audit split). `completeness-apply`
(`plan_tool/cli/completeness_cmd.py:cmd_completeness_apply`) is the sole
mutator of those conceptual gaps, walking each through
`plan_tool/launcher.py:apply_finding` one gap at a time — either interactively
(`--jobs 1`, a human-reviewed apply/skip per gap) or in parallel
(`--jobs N`, still one gap per worker, with no aggregate view across the
finding set). `direct-jira` and `direct-run`
(`plan_tool/cli/direct_cmd.py:cmd_direct_jira`/`cmd_direct_run`) chain
`create → detail → completeness-apply → {jira, run --all --commit →
reconcile-code}` in one process specifically so a small plan can ship without
a separate `completeness-apply` invocation.

There is nothing unsafe about either mode. The reason is pace and
visibility: walking findings one gap at a time is slower than reading the
whole saved report and applying a bounded, judged batch of edits, and that
slow, piecemeal pace obscures whether the plan is actually converging — a
recurring gap, a self-seeded finding, or an arm-clustering pattern only shows
up across the whole finding set and across rounds, not one gap at a time.
The driving human or session already reads the whole report at once (this
repo's own `CLAUDE.md` § "Distinguish a Claude-session-driven run from a
human operator" already prescribes hand-apply for a session), so this plan
makes session-directed edits the supported path for completeness-audit
conceptual findings. The explicitly excluded callers below keep their behavior.

## Problem statement

Two commands currently apply conceptual findings one gap at a time:
`completeness-apply` (both `--jobs 1` and `--jobs N`), and `direct-run`/
`direct-jira`, which use `--jobs N` as their mid-chain stage
(`plan_tool/cli/direct_cmd.py` docstrings: "commits mid-chain because
`completeness-apply --jobs N` isolates its workers in worktrees cut off
HEAD"). This repo's own `CLAUDE.md` currently calls the two direct commands a
deliberate carve-out because they are "designed for small unattended runs."
This effort removes the carve-out along with the mechanism it depends on:
`direct-run`/`direct-jira` exist only to chain `completeness-apply`'s
gap-by-gap apply, so once that apply mode retires, both direct commands
retire with it rather than being narrowed to some other mechanism.

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
`direct-jira` (create's own `--iterate`, detail's own `--iterate`, generic review,
benchmark fixtures, and `run --reconcile`/`reconcile-plan-walk`/`detail --reconcile`), and this
plan makes no claim about whether those callers share the same gap-by-gap
pace and convergence-signal cost. BACKLOG #369 inventories them separately;
until that inventory ships, this plan changes none of their behavior.

Existing saved reports, run logs, and `plan-details/*/reports/` artifacts
remain readable exactly as today — this is a command retirement, not a data
migration. No compatibility shim re-creates `completeness-apply`'s behavior
under a new name or flag.

## References

- `BACKLOG.md` #376 — the owner-confirmed decision this seed elaborates,
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

## Steps

See the `steps:` block in the frontmatter.

## Scope guardrails

Retire only `completeness-apply`, `direct-run`, `direct-jira`, their exclusive
machinery, and their live guidance. Preserve deterministic repair, existing
review/reconcile behavior, benchmark fixtures, audit blocking and exit-code
policy, and legacy readers. Do not introduce a renamed private conceptual
auto-apply route, a workflow engine, or historical-artifact migrations. File
adjacent findings in the backlog rather than expanding this plan.

## Out of scope

`apply_finding`'s use inside create's own `--iterate`, detail's own
`--iterate`, `completeness-audit`'s own deterministic well-formedness
auto-fix, generic review, benchmark fixtures, and
`run --reconcile`/`reconcile-plan-walk`/`detail --reconcile`
(BACKLOG #369's territory — this plan does not presume they share the same
problem and does not change them). Rewriting or migrating historical saved
reports merely to remove `completeness-apply` vocabulary from their own text.
A CI gate, a provider integration, or any generic workflow-engine
abstraction. Reader-only documentation for surfaces this plan does not touch.

## Risks

Removing `direct-run`/`direct-jira` removes the only unattended small-run path
those two commands offered; this is the owner-confirmed, intended effect
(BACKLOG #376), not an oversight to mitigate. The larger risk is a hidden
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
- No production caller retains or privately re-creates the retired
  completeness-apply authority. Existing create/detail deterministic repair,
  review/reconcile routes, and benchmark fixtures retain their behavior; shared
  `apply_finding` caller inventory remains #369 work.
- Saved-report continuation guidance, `docs/cli/`, and every doc/prompt named
  In scope describe hand-applying conceptual findings as the only path, with
  no reference to the retired commands remaining in live (non-historical)
  prose.
- Legacy saved reports, run logs, and detail-bundle artifacts remain readable
  unchanged.
- BACKLOG #376 is marked shipped/removed with this plan's name, and BACKLOG
  #369 is left exactly as it was (unassigned, independent).
- Focused tests and the full suite are green.

## Deferred

BACKLOG #369's inventory of `apply_finding`'s other callers (create, detail,
generic review, reconcile) is separate work this plan does not fold in. Any
caller #369 later finds to share this problem becomes its own backlog item,
not a late addition here.
