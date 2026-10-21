## Outcome

`plan-tool detail <plan> --grade jira` and the underlying Jira-grade authoring
dispatch will reject before a model call, checkpoint/run-log creation, or plan-detail
write. Operator-facing contracts will distinguish this retired authoring lane from
`plan-tool jira`'s generated developer-handoff output, while existing Jira-grade
artifacts remain readable until their separately scoped removal.

## Overview

The compact Jira-grade detail lane pre-dates the paired Jira developer handoff.
It is an independently authored input bundle, whereas the handoff is a terminal,
generated companion to Jira stories. Keeping the authoring entry point live makes
the two artifacts easy to mistake for alternatives. This stage disables creation of
new compact Jira-grade details without deleting legacy artifacts or their readers.

## Problem statement

At HEAD, `plan_tool/cli/authoring.py:build_authoring_parser` accepts `detail
--grade jira`; `cmd_detail` passes that grade to `generate_detail`, whose dispatch
routes it to Jira-grade writing. `plan_tool/jira.py:export_jira` instead captures
one selected-detail snapshot and publishes a paired story and developer-handoff
output. The authoring flag can therefore create a second Jira-named detail artifact
beside the newer generated handoff even though their authority and lifecycle differ.

## Architecture

The temporary compatibility boundary keeps `jira` as a recognized detail-grade
token for read-time consumers, but makes it unavailable at every detail-authoring
entry point. The CLI returns one stable, actionable refusal before context or plan
resolution; direct authoring callers receive the equivalent domain error before
parsing, invoking a backend, or writing. The refusal explains that a developer
handoff comes from `plan-tool jira` as generated output, and that the normal run
grade remains the only detail-generation path.

The paired Jira export remains an output projection: it may continue to read an
explicitly selected pre-existing legacy grade under its current read contract, but
it neither creates that grade nor treats its developer handoff as a detail artifact.
This stage preserves that compatibility so no existing artifact is deleted or
silently reinterpreted. A later removal will decide migration or retention of
legacy artifacts and then remove the remaining consumer-grade selectors together.

## Scope of work

- Add the fail-closed authoring boundary and its direct-call backstop.
- Update only live documentation that instructs Jira-grade detail authoring or
  directly compares that lane with the paired developer handoff; include the
  generated detail reference and the legacy Jira-grade backlog history.
- Replace the complete legacy CLI-routing and direct-authoring suites with one
  stable refusal contract across the bare form and every former mode-conflict
  combination; retain the existing run-grade and legacy-reader compatibility
  checks.
- Record the deferred full removal in `BACKLOG.md` with the remaining consumers,
  artifact-retention decision, and migration question.

## Out of scope

Removing `GRADE_JIRA`, `jira --grade jira`, `run --detail-grade jira`, or
`completeness-audit --grade jira`; rewriting, deleting, or migrating existing
`plan-details/<slug>/jira/` artifacts; changing the compact schema; changing Jira
story or developer-handoff rendering, destinations, provenance, or publication;
and silently falling back from a legacy artifact to run-grade detail are out of
scope. Reader-only documentation for unchanged grade selectors is also out of
scope unless it directly instructs authoring or compares the legacy detail with
the handoff. The deferred removal decision will not be made by this plan.

## Risks

A CLI-only rejection would leave programmatic callers able to create the same
legacy artifact. A broad grade-token removal would instead break established
readers and make a staged retirement look like an accidental data migration. The
implementation must reject both authoring routes while preserving each reader's
current explicit-selection and no-fallback behavior. A broad documentation sweep
would exceed this stage, but a surviving authoring instruction would keep the
confusion alive; update only the direct authoring and handoff-comparison texts.

## Testing

The bare-plan stage must retain the settled boundary: no detail-authoring route
creates a Jira-grade artifact, while a pre-existing artifact can still be read only
by an explicitly selected legacy consumer and the normal detail command authors run
grade. Detail-grounded work will prove the CLI refuses before context/plan
resolution for the bare form and every former mode-conflict combination, direct
dispatch refuses before parsing, and neither causes backend, checkpoint/log, or
detail-file effects. Existing no-fallback read tests remain the compatibility
proof.

## Acceptance criteria

- Jira-grade detail authoring is unavailable through both CLI and direct authoring
  dispatches, with no model, checkpoint/log, plan, or artifact write.
- Every `detail --grade jira` flag combination returns the same retirement refusal
  before context or plan resolution.
- Run-grade authoring remains the sole supported `detail` generation path.
- Generated developer handoffs are documented as terminal Jira output, never as
  detail authoring or an upstream plan/audit input.
- Existing Jira-grade detail readers retain their explicit, fail-loud behavior until
  a separately tracked removal plan resolves legacy artifacts and consumers.
- Every live detail-authoring instruction and direct handoff comparison uses the
  same distinction, and deferred full-removal work is discoverable in `BACKLOG.md`.

## Deferred

The later removal includes the remaining grade selectors and their readers,
`plan_tool/jira_grade.py`, the compact-schema documentation and tests, and a
user-visible policy for pre-existing artifacts. It will be planned from the backlog
entry this stage adds rather than folded into the authoring disablement.

## References

- `plan_tool/cli/authoring.py` — detail-command argument routing that exposes
  the retired authoring route.
- `plan_tool/jira.py` — Jira export boundary that remains terminal output,
  rather than a detail-authoring input.
- `BACKLOG.md` — deferred full-removal destination for legacy readers and
  artifacts.
