> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-structural-revision-escalation.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap Structural Revision Escalation

## Outcome

`plan-tool roadmap` will provide an explicit, review-first escalation path for
feedback that cannot safely use the bounded local revision mode. Given one
artifact-qualified feedback row, the path will write durable, canonical-roadmap
adjacent evidence that explains why the request is structural, prose-scoped, or
cross-artifact; identifies the affected artifacts and stable targets known at
the current revision; estimates the bounded context required for a later broad
revision; and gives the operator an explicit next action. It will not rewrite a
roadmap artifact, seed, feedback row, or Git state.

The narrowed `roadmap-incremental-revision` plan remains the routine path for a
same-artifact row's allowlisted presentation fields. This seed supplies the
safe handoff when that contract is insufficient; it deliberately does not turn
an escalation into an automatic multi-artifact editor.

## Why this is a separate plan

The local revision plan's safety comes from its closed write set: one existing
artifact, one target row, a few scalar presentation fields, and one proposed
feedback response. Structural changes need a different safety model: they can
change prose, row membership, relations, decisions, or multiple artifacts. If
the local command silently widens to accommodate them, its most important
guarantee disappears. If it merely points operators at `--from-stage`, the
current broad path again receives full-stage context without a reviewable
explanation of scope, source revision, or expected impact.

This follow-on is therefore an escalation **report and routing contract**. It
makes a broad revision intentional and inspectable now. A later plan may use
observed reports to design a transactional, bounded multi-artifact patch
writer; it must not be implied here.

## Decisions this seed settles (the plan must not re-open them)

1. **Escalation is explicit and read-only.** An operator invokes a distinct
   command or subcommand with one stable `<artifact>:<feedback-id>` selector.
   The command may reject an unknown, duplicate, closed, or stale selector, but
   it never edits canonical artifacts, feedback lifecycle state, seed state,
   drafts, or Git state.
2. **The report is evidence, not a proposed rewrite.** It records canonical
   input digests, selected feedback and target identities, directly declared
   relation neighbors, target type, and a deterministic classification/reason.
   It may state that operator-supplied intent requires prose or structural
   review; it does not ask a backend to invent a patch, choose additional rows,
   or decide that a broad rewrite is safe.
3. **The report is revision-bound and stale-aware.** It includes the current
   digest of every artifact it names and the feedback row's identity/state. A
   later command or view can say when the report no longer describes the
   canonical roadmap; stale evidence must be regenerated rather than reused as
   an implicit approval.
4. **The report computes a conservative bounded-context estimate.** It reports
   the selected feedback, the owning artifact/target, the declared relation
   closure needed to understand that target, and the bytes/counts of each
   included slice. It must not read unrelated artifact prose, unselected
   feedback, plan-seed drafts, or repository code merely to make the estimate.
5. **Escalation routes; it does not execute.** The output names the existing
   broad `--from-stage` command only when a deterministic owner stage can be
   identified, and otherwise reports that a schema/ownership decision is
   required. The operator chooses whether to use that command after reviewing
   the report. No new automatic `--from-stage` invocation, retry policy, or
   timeout behavior belongs here.
6. **One report is scoped to one selected feedback row.** Batch selection,
   related-feedback clustering, and a persistent review queue are deliberately
   deferred. The first version must make the evidence and staleness contract
   correct for the smallest useful unit.

## In scope

- A strict feedback-selector preflight shared where appropriate with the local
  revision surface, while preserving that surface's own single-artifact write
  rules and error semantics.
- A deterministic escalation classifier that uses canonical target kind,
  artifact ownership, and an explicit operator-selected escalation reason.
  Supported reasons should cover at least prose, row/collection structure,
  relationship/decision semantics, and cross-artifact impact. It must not
  claim that feedback prose has been semantically solved.
- A compact, versioned escalation-report schema and renderer stored under the
  roadmap's own directory, with stable feedback/target IDs, source artifact
  paths and digests, relation summary, classification, context accounting,
  recommended next action, creation time, and a clear stale/current result.
- Deterministic ownership-stage resolution from the roadmap artifact model and
  a recommendation for the existing broad re-entry command when resolution is
  unambiguous.
- Read-only CLI and view output that makes the selected item, reason,
  artifacts, digest state, context estimate, and exact no-write guarantee easy
  to inspect. Existing read-only views remain canonical-artifact views; the
  escalation record is supporting evidence, not a fifth roadmap artifact.
- Command-lifecycle observability appropriate to a non-backend, read-only
  action: command start/result/failure with selector, report digest, and
  stale/current outcome, while retaining the rule that ordinary read-only
  views do not create run logs just by being read.
- Unit, CLI, and fixture tests for selector validation, classification,
  artifact ownership, relation closure, report determinism, digest staleness,
  read-only behavior, and output routing.

## Out of scope / Non-goals

- Any backend-generated patch, model-selected impact set, automatic broad
  revision, multi-artifact writer, or transaction/publication protocol.
- Editing roadmap prose, adding/removing/reordering rows, changing relations,
  changing decisions, responding to or closing feedback, or updating a
  reviewer-owned state.
- Changing the local `--revise-feedback` allowlist, its one-artifact atomic
  replacement behavior, its conservative seed invalidation policy, or its
  failure/recovery semantics.
- Changing `--from-stage` prompt construction, full-stage output schema,
  retry/timeouts, or broad-stage publication. The report may expose why that
  route is large; reducing that context is a separately evidenced follow-on.
- Seed materialization, refresh, promotion, acceptance, or the corresponding
  observability work. `roadmap-seed-materialization-observability.md` owns
  materialization lifecycle telemetry.
- Git commits, branches, pull requests, external tickets, user identities, or
  a general workflow/task-management system.
- A manual arbitrary-text edit interface or an external database/service.

## Allowed behavior changes

- An operator can create and inspect an immutable-by-convention, stale-aware
  escalation report for one selected feedback row.
- An unsupported local-revision request can be directed to a precise,
  reviewable escalation command instead of a bare generic `--from-stage`
  suggestion.
- A roadmap view or command can identify whether the latest report remains
  aligned with the current canonical artifact digests.

## Allowed reorganization

Only extract deterministic feedback selection, artifact digest, relation
summary, or owning-stage helpers when both the local revision and escalation
paths need the same definitions. Do not refactor broad stage generation,
artifact schemas, seed machinery, or run logging just to make the commands
look uniform.

## Verification

- A valid selected row and explicit structural reason produce a deterministic
  report whose input digests, relation summary, context counts, and recommended
  route match the fixture roadmap; repeating the command on unchanged inputs
  produces the same semantic report.
- Unknown, duplicate, closed, removed, and cross-artifact-invalid selectors
  fail before any report write or backend invocation. A selector that is valid
  for escalation remains valid even when it is not eligible for local revision.
- The report never includes unrelated artifact prose, unselected feedback,
  seed draft text, or repository-code content. Tests assert the reported
  context inputs and byte/count accounting.
- Editing any named canonical artifact or selected feedback row makes the
  report stale; editing an unrelated file does not. A stale report is visibly
  rejected as the basis for a later routing decision until regenerated.
- The command leaves every canonical roadmap artifact, feedback state,
  seed-state sidecar, draft seed, and Git worktree content byte-for-byte
  unchanged apart from its explicitly declared report location and permitted
  command telemetry.
- No backend is invoked in normal or error paths. The roadmap-focused test
  suite passes without credentials; an opt-in disposable-repository smoke
  confirms the report's no-write boundary against a real roadmap.

## Stop / defer

Record evidence for a future transactional multi-artifact revision protocol
only after reports show recurring structural cases and their actual relation
closures. Do not broaden this work to execute the recommended broad command or
to reduce broad-stage prompts. If the current artifact model cannot
deterministically identify an owner stage or relation summary, stop and surface
that schema decision rather than inventing a heuristic or reading full
artifacts.
