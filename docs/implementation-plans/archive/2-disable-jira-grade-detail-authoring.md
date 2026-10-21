> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Disable Jira-Grade Detail Authoring
intent: Disable creation of the legacy Jira-grade detail bundle and distinguish it
  from the generated Jira developer handoff without breaking existing explicit readers.
status: completed
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/disable-jira-grade-detail-authoring.md
steps:
- id: 1
  title: Fail closed at every Jira-grade detail-authoring boundary
  intent: No caller may create a new compact Jira-grade artifact after this stage,
    while the run-grade authoring path and legacy read paths retain their current
    contracts.
  files:
  - plan_tool/cli/authoring.py
  - plan_tool/detail.py
  - tests/cli/test_authoring_cmds.py
  - tests/test_detail.py
  complexity: high
  change_type: refactor
  status: done
- id: 2
  title: Update the focused authoring and handoff contract references
  intent: The docs that tell an operator how detail is authored or compare it to the
    developer handoff need one current boundary, plus a discoverable follow-up for
    full legacy removal.
  files:
  - DETAIL_FORMAT.md
  - JIRA_FORMAT.md
  - USE_CASES.md
  - docs/how-to/pipeline/detail.md
  - docs/reference/contracts/process.md
  - CAPABILITIES.md
  - docs/ARCHITECTURE.md
  - docs/cli/detail.md
  - BACKLOG.md
  - docs/implementation-plans/backlog-arcs/archive/backlog-arc-jira-grade.md
  - tests/cli/package_surface_help.golden.txt
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  depends_on_notes:
    1: The final CLI refusal and retained legacy-read contract supply the names and
      behavior the documentation records.
  status: done
---

# Disable Jira-Grade Detail Authoring

## Overview

The compact Jira-grade detail lane is an independently authored input bundle.
The paired Jira developer handoff is a terminal generated output. This plan
will disable new Jira-grade detail creation so the matching Jira names no longer
invite operators to treat them as alternatives.

## Problem statement

`detail --grade jira` currently routes through its own prompt, response gate,
and `plan-details/<slug>/jira/` artifact path. `jira` now captures selected
detail once and publishes both stories and a developer handoff. The two lanes
have different authority and lifecycle, but the live authoring flag makes them
easy to confuse.

## Architecture

`jira` remains a recognized grade token for its existing read-time consumers,
but becomes unavailable at every detail-authoring entry point. The CLI refuses
it before loading context or resolving the named plan; direct authoring dispatch
refuses it before parsing. Both paths therefore fail before any backend
invocation, checkpoint, run log, plan mutation, or detail write. The rejection
routes operators to normal run-grade detail authoring and identifies
`plan-tool jira` as the producer of the generated developer handoff.

Existing compact artifacts remain legacy inputs during this stage. Explicit
`jira`, `run`, and audit readers retain their current selected-grade,
fail-loud behavior; the paired export can read such an artifact only when it is
explicitly selected, and never authors one. No legacy artifact is deleted,
rewritten, or silently substituted with a run-grade file.

## Steps

1. **Fail closed at every Jira-grade detail-authoring boundary** — Refuse the
   legacy grade at the CLI before context/plan resolution and enforce the same
   rule in the direct detail-generation dispatch before parsing. Preserve
   run-grade generation and explicit legacy-reader semantics. Replace the
   complete Jira-grade CLI routing matrix—bare forwarding, defaulted split,
   mode-conflict flags, and Jira-specific next steps—with one stable retirement
   refusal contract for every flag combination, including a nonexistent plan
   name. Replace the complete direct Jira-grade authoring suite—writes, retry,
   force, dry-run, resume, and multi-step generation—with pre-parse refusal
   coverage that proves no authoring effect and proves direct callers cannot
   bypass the CLI.
2. **Update the focused authoring and handoff contract references** — Update
   only live documentation that tells users `detail` authors Jira grade or
   directly contrasts that lane with the developer handoff. Describe run grade
   as the only supported authoring path, compact Jira-grade files as legacy
   readable inputs, and the handoff as generated terminal Jira output. Do not
   widen into reader-only documentation for the unchanged `jira`, `run`,
   audit, or convergence selectors. Regenerate the detail CLI reference and
   add a `BACKLOG.md` item for the later consumer/artifact removal decision.

## Out of scope

Removing `GRADE_JIRA`, `jira --grade jira`, `run --detail-grade jira`, or
`completeness-audit --grade jira`; deleting, migrating, or rewriting existing
`plan-details/<slug>/jira/` artifacts; changing the compact schema; changing
story or developer-handoff rendering, destinations, provenance, or publication;
and falling back from a selected legacy artifact to run-grade detail are out of
scope. Updating reader-only documentation for unchanged grade selectors is also
out of scope unless it directly instructs a user to author Jira-grade detail or
compares that detail with the handoff. The later removal plan will decide
artifact retention and consumer retirement.

## Risks

A CLI-only refusal would leave direct callers able to create the artifact. A
global token removal would break existing readers and turn a staged retirement
into an accidental migration. Updating every document that mentions an
unchanged reader would turn this narrow boundary into a documentation rewrite,
but leaving a live authoring instruction would keep the confusion. The code,
tests, and focused authoring/comparison docs must therefore keep the block,
read compatibility, and output-only handoff boundary aligned.

## Testing

Tests will prove that the CLI rejects Jira grade before context and plan
resolution for the bare form and every former mode-conflict combination, that
direct dispatch rejects it before parsing, and that neither path causes backend,
checkpoint/log, plan, or artifact effects. The complete legacy CLI-routing and
direct-authoring suites will become refusal coverage; default run-grade
authoring remains covered. Existing reader tests continue to prove explicit
no-fallback compatibility, and the full suite runs through the plan test command.

## Acceptance criteria

- Jira-grade detail authoring fails through both CLI and direct dispatch without
  model, checkpoint/log, plan, or artifact writes.
- Every `detail --grade jira` flag combination returns the same retirement
  refusal before context or plan resolution.
- Run grade is the sole supported detail-generation path.
- The developer handoff is documented as a generated Jira output, never a
  detail-authoring or plan/audit input.
- Existing explicit Jira-grade readers retain their fail-loud, no-fallback
  compatibility until separately tracked removal work resolves them.
- Every live detail-authoring instruction and direct handoff comparison uses
  the same distinction, and `BACKLOG.md` records the full-removal follow-up.

## Deferred

A later plan will decide the fate of existing compact artifacts, remove the
remaining consumer-grade selectors, and retire `plan_tool/jira_grade.py`, its
schema documentation, and its test coverage together.
