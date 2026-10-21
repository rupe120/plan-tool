> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Saved Audit Evidence Ledger
intent: '`plan-tool convergence <name>` renders a separate, read-only ledger of saved
  completeness-audit artifacts. Each entry displays its saved metadata or opaque state
  and a next action, but never compares findings across invocations or claims a trajectory.'
status: completed
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/cross-invocation-audit-history.md
steps:
- id: 1
  title: Read saved completeness artifacts as an ordered evidence ledger
  intent: This gives an operator one accurate view of the evidence already on disk
    without inventing a relationship between separate audits.
  files:
  - plan_tool/convergence_diagnosis.py
  - plan_tool/review_persistence.py
  - tests/test_convergence_diagnosis.py
  - tests/test_review_persistence.py
  creates:
  - tests/fixtures/convergence/audit-history-ledger.json
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/cross-invocation-audit-history/01-read-saved-completeness-artifacts.md
  status: done
- id: 2
  title: Render the separate ledger and preserve the convergence diagnosis's meaning
  intent: This exposes artifact state and next actions while preserving existing verdicts,
    advisories, telemetry, and exit behavior and correcting its no-history wording.
  files:
  - plan_tool/convergence_diagnosis.py
  - plan_tool/cli/convergence_cmd.py
  - tests/test_convergence_diagnosis.py
  - tests/cli/test_convergence_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: The renderer consumes the ledger's ordered rows and their display-safe metadata
      rather than the existing convergence history.
  detail: docs/implementation-plans/plan-details/cross-invocation-audit-history/02-render-separate-ledger-preserve.md
  status: done
- id: 3
  title: Document the audit-evidence ledger and its limits
  intent: This tells operators what each saved-artifact state means, which action
    to take, and why the ledger does not make a trajectory decision.
  files:
  - docs/cli/convergence.md
  - docs/how-to/pipeline/audit.md
  - docs/ARCHITECTURE.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  depends_on_notes:
    2: The landed names and output are the source of truth for operator-facing docs.
  detail: docs/implementation-plans/plan-details/cross-invocation-audit-history/03-document-audit-evidence-ledger-its.md
  status: done
- id: 4
  title: 'Record the reoriented #247 delivery and defer trusted trajectory comparison'
  intent: 'This retires the old trajectory promise from #247 while preserving a separately
    scoped backlog route for the provenance-backed comparison feature.'
  files:
  - BACKLOG.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md
  complexity: low
  change_type: non-code
  depends_on:
  - 3
  depends_on_notes:
    3: The documented delivered ledger defines the boundary of the deferred trajectory
      feature.
  detail: docs/implementation-plans/plan-details/cross-invocation-audit-history/04-record-reoriented-247-delivery-defer.md
  status: done
---
# Saved Audit Evidence Ledger

## Overview

`plan-tool convergence <name>` will add a separate, read-only ledger of the
plan's saved completeness-audit artifacts. Each row will show the artifact's
saved metadata or an opaque state and a concrete next action. It will not
compare findings between audits, match anchors, calculate a trend, or claim a
cross-invocation result. The feature will remain zero-Claude. Its read-only
boundary means it creates or changes no plan or report artifact and no new
telemetry event; the command's existing telemetry append remains unchanged.

## Decision

**Reoriented 2026-08-21, user-directed:** #247 delivers a ledger rather than
a cross-invocation trajectory. The prior trajectory design requires new
persisted provenance and a larger set of evidence-admission safeguards. A
separate backlog item will own that future feature; this plan will not create
its persistence schema or comparison policy.

## Problem statement

An operator currently has to open several saved completeness reports to learn
what evidence exists, whether a report has structured data, and whether its
saved coverage or qualified result is known. `list --status` rolls up cached
annotate reports, not completeness-audit artifacts. A single ledger will make
the audit evidence visible without overstating what separate model-generated
findings mean together.

## Architecture

The ledger reader will inspect the requested plan's canonical reports directory
and enumerate the union of `*-completeness.md` reports and
`*-completeness.json` sidecars. It will parse the generated
`YYYYMMDD-HHMMSS` prefix immediately before `-completeness` as a filename
timestamp. Entries with a valid filename timestamp sort by that time and then
normalized relative path. An artifact without that valid prefix remains
visible, displays filename time as `unknown`, and sorts after every valid-time
entry by normalized relative path. A Markdown report and a JSON sidecar with
the same stem form one ledger entry. An unmatched JSON sidecar remains a
visible entry at its own timestamp or `unknown` filename time.

Each ledger entry will have exactly one display state. State selection is
mutually exclusive and ordered:

1. A Markdown report with no same-stem JSON sidecar is `report-only`.
2. A readable `kind="completeness"` JSON sidecar with no same-stem Markdown
   report is `orphan-sidecar`, regardless of whether its contents would
   otherwise be final or checkpoint.
3. With or without a paired Markdown report, unreadable JSON, invalid UTF-8,
   any `load_review` parser rejection (including unsupported schema version, missing required
   fields, malformed annotations, a non-string persisted kind, or an unsafe
   required report/recommendation field that convergence consumes), or a
   non-completeness payload is `malformed-sidecar`. `load_review` will
   normalize those malformed inputs to `ReviewLoadError`, so neither the
   existing history reader nor the ledger aborts the command because one
   artifact is unreadable or carries an unsafe history value. A malformed
   optional qualified result or coverage payload stays readable and projects
   as `unknown`; it does not make the whole sidecar malformed.
4. A remaining paired sidecar marked confirmed pre-apply is `checkpoint`.
5. A remaining paired sidecar with an unknown persisted role is
   `unknown-role`; it remains visible but does not claim a checkpoint fact.
6. A remaining paired, readable `kind="completeness"` sidecar with the
   ordinary final role is `saved-final`.

An `orphan-sidecar` can still display its readable saved facts, but its state
and operator action remain `orphan-sidecar`. Tests will cover unpaired final,
checkpoint, unknown-role, and malformed sidecars so no implementation can
apply a second state.

For a readable sidecar, the ledger will show only saved facts: filename time,
saved `created_at` or `invalid`, audit stage, captured detail grade, projected
coverage state, and qualified-result headline/coverage/revision state when
present. A saved timestamp is displayed only when it is a timezone-aware
ISO-8601 string; an invalid timestamp displays as `invalid` independently of
the filename-time ordering rule. Missing or malformed optional metadata will
display as `unknown`.
The reader will not validate a sidecar's plan identity, infer current freshness,
or treat any displayed field as proof that two entries are comparable.

The section will render `no-saved-audits` when no completeness artifact exists.
For a `report-only`, `orphan-sidecar`, `malformed-sidecar`, `checkpoint`, or
`unknown-role` entry, it will name the path and tell the operator to inspect
that artifact or run a fresh completeness audit if it needs new structured
evidence. For a
`saved-final` entry whose saved qualified-result headline is
`no-qualified-current-evidence`, it will direct the operator to run a fresh
audit because that saved result itself has no reusable qualified evidence. For
other known qualified results, it will direct the operator to the saved report
and that result. If a supported final sidecar has an unknown qualified result,
it will direct the operator to inspect the saved report and run a fresh audit
only if a qualified result is needed. It will not recommend another audit
merely because the ledger has more than one row.

The ledger uses a new reader and renderer. It will share one saved-sidecar
load between its artifact inventory and `load_report_history`, without
changing the diagnosis verdict policy, existing advisories,
`record_convergence(..., runs=...)`, or the command's always-zero return path.
The diagnosis's `no-history` state will continue to mean no eligible ordinary
final completeness or reconcile sidecar, not no artifact in the report
directory. Its empty-state text will say that explicitly, so a separately
rendered `report-only` or non-final ledger entry does not contradict it. The
ledger will not alter a saved sidecar, introduce a sidecar field, or reuse the
ledger as input to any decision. It will add no write: the command will retain
its one existing telemetry append with the same verdict and `runs` value.

## Input

The feature consumes only saved Markdown reports, saved JSON sidecars, and the
existing `SavedReview` loader/projections for one plan's reports directory.
It presents their serialized state as evidence, including unknown or malformed
state. It does not consume recommendation ids, anchors, titles, current plan
or code fingerprints, audit sampling configuration, or model output beyond
the already-saved report artifacts.

## References

- [pathlib — Object-oriented filesystem pathshttps: — Covers locating and ordering the saved report artifacts.
- [json — JSON encoder and decoderhttps: — Covers malformed JSON handling through the existing saved-review reader.
- [datetime — Basic date and time typeshttps: — Covers parsing generated filename timestamps without changing their ordering.
- [dataclasses — Data Classeshttps: — Covers the immutable ledger-row model used by reader and renderer.
- [How to parametrize fixtures and test functionshttps: — Explains fixture coverage for every artifact state.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- New Claude calls, CLI verbs, changed exit codes, gates, plan mutations, or
  saved-sidecar schema changes.
- Finding matching, anchor identity, severity classification, trend reporting,
  or a cross-invocation confirmation decision.
- Current-freshness or saved-plan-identity validation, audit sampling/purity
  provenance, and coverage admission policy.
- #173's caching/recheck design and #301's coverage-format migration.

## Risks

- A readable sidecar can be stale, incomplete, or copied from another plan.
  The ledger will show it only as saved evidence and make no validity claim.
- A malformed, report-only, or orphaned artifact can otherwise be invisible.
  The reader will display it with its path and state.
- A new section could alter the existing diagnostic accidentally. CLI tests
  will preserve the eligible-history verdict, advisories, telemetry call, and
  exit code while pinning the corrected no-history wording.

## Testing

Tests cover no artifacts; paired readable finals with known and unknown
qualified results; paired checkpoints and distinct unknown roles; a report-only
Markdown file; and unpaired final, checkpoint, and malformed sidecars. They
also cover paired malformed JSON, an unexpected sidecar kind, missing optional
metadata, an invalid saved timestamp, a parser-rejected sidecar, and
invalid UTF-8, malformed annotations, unsafe history-consumed recommendation
fields, and total optional-metadata projection normalized by `load_review`, and
deterministic filename ordering including a manually named artifact without a
filename timestamp. They cover every display state and its operator next
action, including a saved `no-qualified-current-evidence` result. CLI tests
prove that an unsafe persisted kind cannot abort the command; that the ledger
renders after the existing convergence block; and that
`no-history` means no eligible final sidecar even when the ledger has a
report-only or non-final entry; and that its verdict, advisories, one existing
telemetry call (including `runs`), and zero exit code are unchanged.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — reader and fixture tests cover every artifact state and
  saved-field projection; green before completion.
- step 2 (feature) — renderer and command-isolation tests cover output,
  corrected no-history wording, the one existing telemetry call, and return
  behavior; green before completion.
- step 3 (non-code) — verify the documentation matches the landed output and
  preserves the no-trajectory boundary.
- step 4 (non-code) — verify the backlog and arc distinguish delivered ledger
  from deferred trajectory comparison.

## Acceptance criteria

- `convergence` renders one ordered, separate saved-audit ledger for the
  requested plan, remains zero-Claude, and adds no artifact or telemetry
  write beyond the command's unchanged existing telemetry append.
- Every completeness Markdown report and JSON sidecar is visible as a paired
  entry or as a named orphan; no artifact state silently disappears.
- Each entry uses only its saved metadata and one precedence-defined display
  state, with confirmed checkpoints and unknown roles distinguished, unknown
  data shown as `unknown`, a missing filename timestamp sorted after valid
  timestamps, and a state-specific next action.
- An invalid UTF-8, malformed annotation, unsafe history-consumed required
  field, or non-string kind sidecar remains a visible malformed row and cannot
  abort the existing convergence command; malformed optional coverage or
  qualified-result metadata stays readable as `unknown`.
- The section makes no matching, trajectory, comparison, freshness, or
  confirmation claim across entries.
- Existing convergence diagnosis eligibility, verdicts, advisories, telemetry,
  and exit behavior for readable saved data remain separate and unchanged; a
  malformed sidecar is normalized to an opaque row instead of aborting the
  command, and `no-history` says no eligible final history is saved.
- Tests cover every state, ordering, and isolation property, and documentation
  tells the operator what the ledger does and does not decide.

## Deferred

- Deferred #303 owns any future trusted cross-invocation trajectory feature,
  including persisted provenance, lifecycle preservation, evidence admission,
  plan identity, and pairwise comparison. Step 4 will retain that boundary
  after this ledger is delivered.
- Cross-invocation cache/recheck behavior remains #173.
- Persisted audit-coverage schema versioning remains #301.
- Retry-loop notification restructuring remains #302.
