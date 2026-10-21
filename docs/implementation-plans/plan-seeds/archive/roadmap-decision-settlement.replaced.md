> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-decision-settlement.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap decision settlement

Source backlog entry: `BUG_BACKLOG.md` "Approved roadmap decisions cannot
transition from `pending` to `settled`". The resulting plan's final step
removes that entry from `BUG_BACKLOG.md` only after the capability ships.

## Outcome

`plan-tool roadmap` gains one bounded, operator-confirmed action that
transitions a single Roadmap-derived `decisions` row from `status: pending` to
`status: settled` in place, bound to explicit reviewed evidence, publishing a
durable receipt — for both an un-enrolled and an enrolled roadmap — with no
hand-edit of a canonical artifact and no bulk/batch form.

## Overview

Today the only way to settle a load-bearing `pending` decision is a manual
edit of the artifact's `status` field followed by re-entering at that stage
(`docs/how-to/roadmap.md` §4: "That edit is the resolution; there is no
separate settle command"). `--revise-feedback` can record approval prose, but
its field-authority allowlist excludes `status`, so a decision an operator has
already approved through ordinary review stays `pending`, contradicting its
own recorded rationale and feedback. This effort adds the missing narrow
transition route, following the same shape this roadmap subsystem already
uses for other single-row, evidence-bound, confirmed state changes
(`--reopen-feedback`, `--escalate-feedback`).

## Problem statement

`DecisionStatus` (`plan_tool/roadmap_artifacts.py`) has exactly two members,
`pending` and `settled`; `DecisionRow` carries `chosen_option`,
`rejected_alternatives`, `rationale`, `anchor`, `status`, and an optional
`source`. `decisions` is a field on all four staged artifacts
(Domain/Constraints/Components/Plans), not one file. `TEXT_FIELDS_BY_ROW_TYPE`
in `plan_tool/roadmap_revision.py` is the field-authority allowlist for
`--revise-feedback`; it names only `("rationale",)` for `decisions`, so
`status` is structurally excluded — there is no explicit denial to relax,
only an absent grant to add. `check_settled_decisions`
(`plan_tool/roadmap_gates.py`) already refuses a *settled* decision's id,
status, chosen option, or anchor from drifting; it does not, and must not
start to, gate `pending → settled` itself. Nothing today reaches `settled`
except a hand-edit (un-enrolled) or authoring a full model candidate through
propose → review → promote (enrolled) — both bypass the operator-confirmed,
evidence-bound shape every other narrow roadmap action already has.

## References

- `docs/how-to/roadmap.md` §4 ("Settle a pending decision or re-gate an
  existing stage") — current documented hand-edit-only procedure this effort
  replaces with a real action.
- `ROADMAP_FORMAT.md` "Decision row forms" and "Local feedback revision
  contract" — current schema and field-authority prose to extend, not
  contradict.
- `plan_tool/roadmap_artifacts.py` — `DecisionStatus`, `DecisionRow`,
  `FeedbackState` (exactly `open` / `awaiting-review` / `deferred`; no
  reviewer-terminal state exists yet).
- `plan_tool/roadmap_revision.py` (`TEXT_FIELDS_BY_ROW_TYPE`,
  `preflight_feedback_revision`) — the field-authority allowlist to extend,
  and the existing refusal of any operation targeting an inherited
  (`source is not None`) decision row, which a settlement route must match.
- `plan_tool/roadmap_gates.py` (`check_settled_decisions`) — the complementary
  gate that must keep making a settled decision immutable once this route
  produces one.
- `plan_tool/roadmap_feedback_reopen.py` and
  `plan_tool/roadmap_escalation_selection.py`
  (`ReceiptSafeSelector`, `CanonicalArtifactSnapshot.source_digest`,
  `FeedbackSelector`) — the structural precedent this route's selector,
  predecessor-digest staleness check, and named-reason refusal shape should
  follow; both are wired only for an un-enrolled roadmap today via
  `require_unenrolled_roadmap_writer` (`plan_tool/roadmap_revision_publish.py`),
  confirming the enrolled side has no narrow-route precedent to reuse as-is.
- `plan_tool/roadmap_version_promotion.py` (`promote_review_seal`) — the sole
  existing path an enrolled roadmap's accepted head changes today.
- `plan_tool/cli/roadmap_cmd.py` (`--reopen-feedback` / `--confirm-feedback-reopen`
  / `--revise-feedback`) — the CLI shape precedent: a selector flag paired
  with one required, argument-less confirm flag, exclusive of every other
  roadmap option, no backend call.
- `docs/implementation-plans/archive/2-roadmap-carried-settled-decisions.md` —
  shipped, adjacent, and distinct: it creates decision rows *already*
  `status: settled` from a cited, admitted upstream source at authoring time.
  This effort's route never touches an inherited row and never runs at
  authoring time; it transitions a live Roadmap-derived row after the fact.
- `BACKLOG.md` #242 and `docs/implementation-plans/2-roadmap-revision-retention.md`
  (bare, in progress) — adjacent, unshipped work proposing a `closed`
  `FeedbackState` and a `RemovalRecord` decision reference. This effort must
  not depend on either landing.

## Architecture

- **Scope of the transition.** The route accepts exactly one decision
  selector (artifact key + decision id, mirroring `ReceiptSafeSelector`) and
  performs only `pending → settled` on that row. `chosen_option`,
  `rejected_alternatives`, `rationale`, `anchor`, and every other row in every
  artifact are byte-preserved. A decision whose `source is not None`
  (inherited) is refused the same way `preflight_feedback_revision` already
  refuses inherited-row edits — settlement is for Roadmap-derived decisions
  only.
- **Evidence is a binary fact, not a semantic judgment.** The route cannot
  determine whether a human genuinely reviewed a decision — that property is
  unobservable. It requires and checks only checkable facts: a second
  selector naming one live `feedback` row in the same artifact that targets
  the decision and carries non-empty reviewer-authored response text, plus
  the operator's own required, argument-less confirm flag (no `-y`
  substitute, matching `--confirm-feedback-reopen`). The route asserts
  "this evidence exists and was named," never "the approval was sound."
- **Feedback disposition: retain, don't invent a close state.** The cited
  feedback row's `FeedbackState` is left unchanged. The settlement receipt
  (below) is the durable record binding that row to the decision it
  evidenced; a future ability to also close it belongs to BACKLOG #242, not
  this route.
- **Predecessor-digest staleness.** The route re-parses the artifact's
  current canonical bytes and requires the digest to match a snapshot taken
  when evidence was selected, following `CanonicalArtifactSnapshot.source_digest`;
  a changed artifact since evidence was gathered refuses rather than settling
  against stale content.
- **Un-enrolled roadmap:** the route publishes directly through the existing
  narrow-write boundary (`require_unenrolled_roadmap_writer` /
  `publish_roadmap_generation`), the same guard every other narrow un-enrolled
  action already uses.
- **Enrolled roadmap:** the route produces a deterministic, non-model
  exact-diff candidate that changes only the one decision's `status`, admitted
  through an evidence-only preflight (no free-form model authoring), then
  proceeds through the existing `promote_review_seal` boundary. It must never
  write the accepted head directly. A journal mid-flight (`PendingGeneration`)
  refuses rather than attempting recovery — that repair belongs to the
  separate, already-tracked "Incomplete immutable lifecycle journals" bug
  entry, deferred pending BACKLOG #328 sign-off.
- **Receipt.** The route publishes one durable, immutable record — following
  the existing immutable-evidence pattern already used for escalation and
  impact-analysis receipts, not a new ad hoc log — naming the artifact key,
  decision id, predecessor digest, and the cited feedback row's id and digest.

## Scope guardrails

- The route performs only `pending → settled` on exactly one selected,
  Roadmap-derived decision row per invocation. It never settles an inherited
  (`source is not None`) row, never reopens a `settled` row back to `pending`,
  and never accepts more than one decision selector.
- It never mutates `chosen_option`, `rejected_alternatives`, `rationale`,
  `anchor`, or any row other than the one selected.
- It never judges whether cited feedback constitutes genuine reviewer
  approval — only that a named, live feedback row targeting the decision
  carries response text. Confirmation is the operator's, via the required
  confirm flag.
- It never mutates the cited feedback row's `FeedbackState` and never depends
  on BACKLOG #242's unshipped `closed` state landing first.
- On an enrolled roadmap it never writes the accepted head directly; it
  always goes through the existing candidate/promotion boundary.
- It is not a hand-edit substitute for any other field or row type, and it is
  not a batch/bulk operation.

## In scope

- A decision selector and a feedback-evidence selector, both mirroring the
  existing `ReceiptSafeSelector` / `FeedbackSelector` shape.
- Preflight checks: target resolution, inherited-row refusal, non-pending
  refusal, feedback-evidence resolution and non-empty-response check,
  predecessor-digest staleness, and (enrolled only) pending-generation and
  accepted-head-in-place refusal.
- The un-enrolled publish path and the enrolled deterministic-candidate +
  promotion path.
- One immutable settlement receipt type.
- One CLI action (selector flag + a required, argument-less confirm flag),
  exclusive of every other roadmap option, invoking no backend.
- `ROADMAP_FORMAT.md`, `docs/how-to/roadmap.md` §4, and `DIRECTIVES.md`'s
  roadmap section, updated to document the action and retire the hand-edit
  instruction it replaces — including `DecisionStatus`'s own docstring
  (`plan_tool/roadmap_artifacts.py`), which currently states the operator
  "accepts a `PENDING` decision by editing its status to it" as the intended
  mechanism.
- Focused/mutation tests across both lineages and every refusal class below.

## Out of scope

- Any change to `check_settled_decisions`'s existing settled → changed
  refusal, or to how a settled decision later becomes eligible for revision
  (a reopen-style route for decisions, symmetric to `--reopen-feedback`, is a
  separate, later effort if ever needed).
- BACKLOG #242's `closed` `FeedbackState` and `RemovalRecord` decision
  reference; this effort neither ships nor depends on them.
- Any judgment, scoring, or heuristic about whether cited feedback text
  constitutes real approval; whether the response is persuasive is never
  checked or gated.
- Batch/bulk settlement, and any change to `--apply`'s existing
  count-only reporting of pending decisions.
- Recovery of a malformed or interrupted immutable lifecycle journal; the
  route refuses cleanly and leaves that repair to its own tracked entry.

## Risks

- **Silent semantic overreach:** a future round could be tempted to add a
  quality check on the cited feedback response ("does this really approve
  the decision?"). That is an unobservable property; keep the check to
  existence and non-empty text, per CLAUDE.md § "Validating a semantic
  property you cannot observe".
- **Enrolled/un-enrolled divergence:** the two paths must produce the same
  observable row-level result (only `status` changes) even though their
  publication mechanics differ; a test asserting identical before/after row
  content across both lineages is required, not just parallel "it runs"
  coverage.
- **Gate interaction:** a settlement that races a concurrent artifact edit
  must refuse via the digest check rather than silently overwriting; verify
  against a changed-baseline fixture, not just an unchanged one.
- **Inherited-row confusion:** an operator selecting an inherited decision by
  mistake must get the same refusal `preflight_feedback_revision` already
  gives other inherited-row edits, not a new, differently-worded one.

## Testing

Cover both lineages with the same row-level assertion: before/after content
of every other decision, and of `chosen_option`/`rejected_alternatives`/
`rationale`/`anchor` on the settled row itself, is byte-identical except
`status`. Cover every refusal class as its own case: missing or mismatched
decision target; an inherited decision selected as target; a non-pending
decision (already settled); missing, mismatched, or empty-response feedback
evidence; a changed source baseline between evidence selection and
confirmation; an in-flight pending generation (enrolled only); and an attempt
to write an accepted head directly (enrolled only). Confirm the settlement
receipt records the artifact key, decision id, predecessor digest, and cited
feedback id/digest, and that a legacy roadmap with no receipts directory
still parses and settles correctly. Confirm `check_settled_decisions` still
refuses drift on the row this route just settled.

## Acceptance criteria

- An operator can settle one live, Roadmap-derived `pending` decision to
  `settled` by naming the decision, naming one feedback row with recorded
  response text, and passing the required confirm flag — with no hand-edit of
  any artifact file, on both an un-enrolled and an enrolled roadmap.
- Every field on the settled row other than `status`, and every other row in
  every artifact, is unchanged.
- Each of the six refusal classes above stops the action before any
  publication, with a distinct, named reason.
- A durable receipt exists after every successful settlement and can be read
  back to prove which evidence justified it.
- `ROADMAP_FORMAT.md` and `docs/how-to/roadmap.md` describe the action and no
  longer instruct a hand-edit as the only path.
- The final plan step removes the `BUG_BACKLOG.md` entry only after every
  step above ships.

## Deferred

A symmetric "un-settle" / reopen route for a `settled` decision, BACKLOG
#242's feedback-closing work, and any repair path for a malformed immutable
lifecycle journal all remain separate efforts. File any newly discovered gap
in `BACKLOG.md` or `BUG_BACKLOG.md` rather than expanding this plan.
