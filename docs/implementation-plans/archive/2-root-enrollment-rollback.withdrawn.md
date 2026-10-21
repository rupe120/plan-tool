> **Withdrawn 2026-09-18** — Solved the wrong problem. The Integration case it came from was a feedback revision that was cut short (a --from-stage run that ran out of attempts at stage 3, then was interrupted), not a need to un-enroll a valid root. The work that does need doing is rolling back a revision that fails or is cut short; it is tracked as its own BACKLOG entry and seed. Six bare-plan audit rounds each found a new defect in step 1's receipt and idempotence design before this was caught.
> Preserved here for history; do not edit.

---
format_version: 1
title: Root Enrollment Rollback
intent: An operator who enrolled a roadmap as an immutable root before recording review
  feedback has one explicit, operator-confirmed command that clears the root's active
  `accepted-head` selection and returns the roadmap to a feedback-driven revision
  state, without deleting the immutable root content and without ever asking the operator
  to delete a file by hand.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/root-enrollment-rollback.md
steps:
- id: 1
  title: Add a roadmap_rollback module that clears the accepted-head selector under
    the writer lock while preserving all immutable root storage
  intent: Give the roadmap lifecycle a deterministic, fail-closed way to reopen a
    root's accepted-head selection once no candidate, review, seal, pending generation,
    or seed state depends on it, publishing a durable, content-addressed rollback
    receipt via roadmap_evidence_store.py before clearing the selector, so
    post-enrollment feedback recorded before any candidate exists stops being
    permanently stranded and idempotent replay can tell "already rolled back"
    apart from "never enrolled."
  files:
  - plan_tool/roadmap_evidence_store.py
  - tests/test_roadmap_evidence_store.py
  creates:
  - plan_tool/roadmap_rollback.py
  - tests/test_roadmap_rollback.py
  complexity: high
  change_type: feature
  status: current
- id: 2
  title: Add a --rollback-root / --confirm-root-rollback CLI command dispatching into
    roadmap_rollback
  intent: Give an operator the one explicit, confirmation-gated command that exposes
    the rollback route, so recovering from stranded post-enrollment feedback never
    requires deleting accepted-head.json by hand.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: delivers the eligibility predicate, receipt, and atomic selector-clear this
      command's dispatch calls into
- id: 3
  title: Correct every pinned accepted-head-exclusivity claim to name the rollback
    writer and close out the BUG_BACKLOG entry
  intent: Rollback is a second writer that changes the accepted head (by clearing
    it), which falsifies every existing claim that only promotion changes it.
    Revise ROADMAP_FORMAT.md's "Immutable candidate-version authority" section
    (its pinned "changes only the accepted head" / "Promotion is terminal
    consumption of the exact review seal" wording) and its drift-guard test in
    the same change, plus the same exclusivity claim restated in BACKLOG.md's
    closed entry 328 and docs/history/backlog-decisions.md's entry 328, so all
    four sites name both writers (promotion advances the head forward under
    review; rollback clears it under explicit confirmation) instead of claiming
    exclusivity for either. Then remove the backlog entry now that its exact fix
    has shipped and is tested.
  files:
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_format.py
  - BACKLOG.md
  - docs/history/backlog-decisions.md
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: names the shipped module and its receipt mechanism for the doc update
    2: delivers the shipped flag names and confirms tests pass before the backlog
      entry is removed
---
# Root Enrollment Rollback

## Overview

`enroll_roadmap_root` captures a roadmap's four staged artifacts into
immutable version storage and points `accepted-head.json` at that root. Once
enrolled, `require_unenrolled_roadmap_writer` refuses every legacy stage
writer, and `--propose-candidate` builds its feedback view strictly from the
frozen bytes captured at enrollment (`roadmap_candidate_context.py:
_verify_predecessor` parses `predecessor.artifact_bytes`, not the live
working artifacts). Feedback recorded in the working artifacts after
enrollment is therefore invisible to both the legacy writer and candidate
proposal, and today no supported command reopens the lineage.

## Problem statement

An operator who enrolls a clean root and only then records valid feedback has
no way back to a feedback-driven revision state. The legacy writer refuses
because the roadmap reads as enrolled; candidate proposal refuses because it
resolves feedback against the accepted root's frozen snapshot, which predates
the feedback; and no command exists to bind that feedback to the root or
unwind the selection. The root itself is not wrong — it is a valid, unpromoted
version with no candidate, review seal, or materialized seed depending on
it — so the correct remedy is reopening the *selection*, not repairing or
discarding the root.

## Architecture

Rollback is a state transition on the accepted-head selector alone, not a
mutation of immutable version storage. It runs under the same writer lock
every other lifecycle writer uses, and it composes with the existing recovery
boundary without invoking it: it calls `load_pending_generation` directly, a
pure read, never `recover_roadmap_publication` — that function can unlink a
journal or raise as a side effect of running it, and calling it from inside
rollback's eligibility gate would make *checking* eligibility trigger or
complete unrelated in-flight publication recovery, exactly the interrupted-
journal-recovery mechanism this plan's Out of scope keeps separate.

Rollback resolves every invocation — the first attempt and any replay —
through one fixed sequence for a given (slug, operator-named target root
version id): compute the receipt's content address from that version id and
a fixed confirmed-intent marker (never from the timestamp or any other
call-specific input); check for an existing receipt at that address with
`read_evidence_final`. If one exists, that target version id was already
rolled back — this is the idempotent-replay case, and it never runs the
eligibility check below — but the receipt alone does not prove the *whole*
mutation finished, because the receipt write and the selector clear are two
separate file operations: an interruption between them (a kill, a crash, a
host reboot) can leave a receipt durably written with `accepted-head.json`
still naming the target root. So on a receipt match, rollback also reads the
current selector: if it still names exactly this target version id, clear it
now — completing the interrupted mutation rather than merely re-reporting
it — before returning the idempotent already-rolled-back outcome; if the
selector already differs (absent, because a prior call already cleared it,
or naming a different, later-enrolled root), leave it untouched, since
either state already correctly reflects that this target was rolled back.
Only when no receipt exists at all does rollback evaluate the eligibility
predicate below, and only on eligibility does it perform the first-time
mutation (publish the receipt, then clear the selector). This ordering is
what makes idempotence possible at all: `accepted-head.json`'s absence is
indistinguishable between "never enrolled" and "already rolled back"
(`load_accepted_head` returns `None` for both), so nothing downstream of the
eligibility gate can ever tell the two apart — the receipt pre-check is the
only thing that can, and it must run first, with its own completion guard
covering the interruption window the eligibility gate can't see at all.

The eligibility check is a closed predicate over four independently-triggerable
conditions: the accepted head names exactly the operator-named target root
version, no candidate admission exists, no pending generation is recorded,
and no roadmap seed state with `status: "current"` is tracked for the slug.
An `"invalidated"` seed entry (`roadmap_seed_state.py`'s only other
recognized status) does not count: ordinary stage revision invalidates a
tracked seed entry in place
rather than removing it, so a roadmap that ever generated a seed before its
final clean revision would otherwise be permanently ineligible even with
nothing live depending on the root. "No accepted descendant" and "no
review/seal record" are true statements the plan also cares about, but under
every current writer they are direct consequences of the first two, not
independently violable:
`accepted-head.json` names exactly one version at a time, so an accepted head
that names the root already rules out an accepted descendant; and every
review/seal artifact is keyed off a materialized candidate, which cannot exist
before its `CandidateProposalAdmission` is written and which no writer ever
unlinks, so no candidate admission already rules out a review/seal record.
Both are still evaluated as defense-in-depth alongside their governing
condition, not as separate standalone fixtures. Any one violated condition is
a refusal, not a partial rollback.

Once eligible, rollback publishes the receipt through
`roadmap_evidence_store.py`'s `publish_evidence` (a new namespace alongside
the existing `ESCALATIONS` and `IMPACT_ANALYSES`), then clears the selector.
The receipt's content address is derived only from the roadmap slug, the
target root's version id, and a fixed literal confirmed-intent marker
constant — never from the rollback timestamp, the operator's own
confirmation text, or any other call-specific value — mirroring
`roadmap_escalation.py`'s `EscalationReceipt`, whose `semantic_id` hash
excludes its own `created_at` for the same reason; the timestamp is recorded
inside the receipt payload, not its address. Because the address is a pure
function of (slug, target version id), it is identical between the pre-check
`read_evidence_final` call above and this `publish_evidence` write, and
identical across any later replay. If `publish_evidence` returns anything
other than `EVIDENCE_CREATED` (or, defensively, `EVIDENCE_EXISTING` on a
benign race with a concurrent identical call), rollback aborts before
clearing the selector, leaving `accepted-head.json` and the stored root
untouched.

The CLI surface mirrors the codebase's existing paired action/confirm shape
for a one-off, operator-confirmed lifecycle transition
(`--reopen-feedback SELECTOR` / `--confirm-feedback-reopen`,
`plan_tool/cli/roadmap_cmd.py`): `--rollback-root TARGET_VERSION_ID` carries
the target root version id, and `--confirm-root-rollback` is a bare boolean
required exactly once (`-y` is not confirmation) — not a default-yes flag,
since this is a state transition on an immutable lineage, not a convenience
toggle. `TARGET_VERSION_ID` is the one input the receipt pre-check, the
eligibility check, and the receipt write all key off, so the same invocation
shape handles the first call and any later idempotent replay without
confusing the two.

## References

- `BUG_BACKLOG.md` — source bug, its exact symptom trace, and its fail-closed
  requirement.
- `BACKLOG.md` #328 (closed) — the immutable accepted-head lifecycle contract
  this route reopens; #329/#330 are separate pending-generation and admission
  hardening, not this route.
- `plan_tool/roadmap.py:enroll_roadmap_root`,
  `_roadmap_writer_owner` — enrollment and the writer lock rollback reuses.
- `plan_tool/roadmap_versions.py:load_accepted_version`,
  `is_roadmap_enrolled`, `accepted_head_path` — the selector this route
  clears.
- `plan_tool/roadmap_revision_publish.py:require_unenrolled_roadmap_writer` —
  the legacy-writer refusal that flips once rollback clears the selector.
- `plan_tool/roadmap_candidate_context.py:_verify_predecessor` — why
  candidate proposal cannot see post-enrollment feedback today.
- `plan_tool/roadmap_candidate_run.py:load_candidate_admission`,
  `plan_tool/roadmap_source_identity.py:load_pending_generation`,
  `plan_tool/roadmap_seed_state.py` — the three other independently-checked
  eligibility conditions (see Architecture for why "no accepted descendant"
  and "no review/seal record" are not a fourth and fifth).
- `plan_tool/roadmap_evidence_store.py:publish_evidence`, `read_evidence_final`,
  `EvidenceNamespace` — the content-addressed receipt mechanism this route
  uses: `read_evidence_final` is the pre-check that detects an already-rolled-
  back replay before eligibility runs; `publish_evidence` is the one write,
  reached only on a genuinely eligible target.
  `plan_tool/roadmap_escalation.py`'s receipt shape was evaluated and its
  model rejected — its `EscalationReceipt` models one open feedback row
  (`ReceiptSelector`, `ReceiptTarget`, a required `feedback_state: "open"`),
  none of which describes un-enrolling a root, and its companion
  worktree/commit flow is built for escalation, not a lightweight lifecycle
  fact — but its `semantic_id`/`created_at` split (hash stable identifying
  facts, keep the timestamp out of the address) is the pattern this route's
  content address follows.
- `plan_tool/cli/roadmap_cmd.py:--reopen-feedback`/`--confirm-feedback-reopen`
  — the existing paired action/confirm CLI shape (`metavar="SELECTOR"` on the
  action flag; `nargs=0, const=True` bare boolean on the confirm flag,
  required exactly once, `-y` does not satisfy it) that
  `--rollback-root`/`--confirm-root-rollback` follows.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Rolling back an enrolled root that already has a candidate, review, seal,
  or promoted descendant. That state has no rollback target and is unrelated
  to this route.
- The separate incomplete-journal recovery bug (interrupted candidate
  proposal, review, replacement, or promotion) — that route resumes a
  mid-write journal; this route reopens the selection of a *complete,
  valid* root after the fact. Keep the two mechanisms and their tests
  separate.
- Deleting or rewriting immutable version storage content. The stored root
  version, its record, and its artifact/brief members are never modified or
  removed by this route.
- A general-purpose accepted-head repair, journal-inspection, or operator
  repair framework.
- Binding post-enrollment feedback into the root's stored content. Rollback
  only reopens the selection so the existing legacy writer can record that
  feedback the normal way; it does not itself materialize or migrate
  feedback.

## Risks

- An eligibility check that is too permissive could clear a selection that a
  candidate, review, or seed already depends on, silently orphaning that
  dependent state. Each of the four independently-triggerable conditions
  (root-only accepted head, no candidate admission, no pending generation, no
  tracked *current* seed state) needs its own mutation test (violate one
  condition at a time, prove refusal, prove no write); the accepted-descendant
  and review/seal checks are proven together with their governing condition,
  per Architecture.
- A receipt address that includes any fact that changes between calls (the
  timestamp, or the operator's own confirmation text) can never be
  recomputed on replay, defeating idempotence the same way a skipped or
  wrong-content receipt would. The address must be provably a pure function
  of (slug, target version id, the fixed confirmed-intent marker constant)
  named in Architecture.
- The eligibility gate alone cannot distinguish "never enrolled" from
  "already rolled back," because `accepted-head.json`'s absence means the
  same thing in both cases. Skipping or misordering the receipt pre-check
  ahead of the eligibility check collapses that distinction and turns every
  idempotent replay into an ordinary ineligibility refusal.
- An interruption between the receipt write and the selector clear (a kill,
  a crash, a host reboot) leaves the receipt durably written with
  `accepted-head.json` still naming the target root — the exact stranded-
  root symptom this plan exists to fix, reproduced by its own remedy. The
  receipt pre-check must complete the interrupted clear when it finds a
  matching receipt and the selector still names the exact target, not just
  report success with no mutation. This guard must also not fire when the
  selector already names something else (a different, later-enrolled root):
  clearing *that* selector on the strength of an older target's receipt
  would silently un-enroll unrelated live state.
- An eligibility check that reads live working-artifact state instead of the
  stored root's own record could refuse or allow based on drift unrelated to
  enrollment. Validate against the stored `StoredRoadmapVersion` and its
  digests, not the working tree.
- Running rollback concurrently with another lifecycle writer for the same
  slug must not race; both must serialize through the existing writer lock.
- A `publish_evidence` failure between the eligibility check passing and the
  selector clearing must abort the whole rollback rather than leaving
  `accepted-head.json` cleared with no matching receipt, or a receipt
  written with the selector still pointing at the root.

## Testing

- Add focused tests alongside the existing immutable-lifecycle/recovery
  suites (`tests/test_roadmap_versions.py`, `tests/test_roadmap.py`, and
  wherever the new route's module lands).
- Prove the eligibility boundary by mutation: for each of the four
  independently-triggerable conditions (root-only accepted head, no candidate
  admission, no pending generation, no tracked *current* seed state),
  construct a fixture that violates only that one condition and assert
  refusal with the accepted-head selector and stored root untouched. Include
  a fixture with only an `"invalidated"` seed entry and assert it does
  *not* block rollback. Cover the accepted-descendant and review/seal cases
  as part of the "no candidate admission" and "root-only accepted head"
  fixtures they are consequences of, not as separate standalone fixtures.
- Prove the happy path: enroll a root, record feedback in the working
  artifacts with no candidate ever admitted, roll back, then run the existing
  legacy stage writer and `--propose-candidate` flow through to a normal
  admitted proposal.
- Prove the first successful rollback checks for an existing receipt first
  (finds none), passes eligibility, then publishes a receipt via
  `publish_evidence` naming the target root's version id, with the rollback
  timestamp recorded only in the payload — and that recomputing the address
  from the same (slug, target version id) is byte-identical regardless of
  when it's computed or what confirmation text the operator typed.
- Prove idempotence in the order rollback actually checks it: roll back
  twice with the same named target version id and assert the second call's
  `read_evidence_final` pre-check finds the first call's receipt *before*
  evaluating eligibility, reports the already-rolled-back state, and neither
  re-evaluates eligibility nor calls `publish_evidence` again.
- Prove crash recovery: construct a fixture with a receipt already published
  for a target version id but `accepted-head.json` still naming that exact
  version (simulating an interruption between the two writes), and assert
  the next invocation completes the clear and reports the idempotent
  already-rolled-back outcome, rather than reporting success with the
  selector left stale.
- Prove the crash-recovery guard is scoped correctly: with a receipt
  published for an older target version id, but `accepted-head.json` now
  naming a *different*, later-enrolled root, assert rollback for the old
  target reports already-rolled-back without touching the current selector.
- Prove that a target version id with no accepted head and no existing
  receipt (genuinely never enrolled, or already-enrolled-and-promoted-away)
  refuses as ordinary ineligibility, distinct from the idempotent
  already-rolled-back outcome above.
- Prove a `publish_evidence` failure (simulate `EVIDENCE_WRITE_FAILED` /
  `EVIDENCE_INVALID_INPUT`) aborts rollback with `accepted-head.json` and the
  stored root both untouched.
- Prove rollback serializes rather than races: hold the writer lock (or
  otherwise drive a concurrent lifecycle writer) for the same slug while
  rollback is attempted, and assert it waits for or refuses against the
  lock rather than proceeding concurrently.
- Prove rollback succeeds using only the stored root's record when the
  roadmap's live working artifacts have already diverged from it (the normal
  case, since post-enrollment feedback lives in the working tree by design),
  so Risk 3 gets the same explicit proof as the other risks rather than
  relying on `load_accepted_version` avoiding the working tree by construction.
- Run the complete test suite and review every root-enrollment and
  candidate-proposal call site for a rollback bypass.

## Acceptance criteria

- A root enrolled with no candidate, review, seal, pending generation, or
  tracked *current* seed can be rolled back by one explicit, operator-named,
  operator-confirmed command, after which the legacy stage writer and
  `--propose-candidate` both operate normally against the (now unenrolled)
  working artifacts. A tracked `"invalidated"` seed entry does not block it.
- Any accepted descendant, candidate admission, review/seal record, pending
  generation, or tracked current seed state blocks rollback with a clear
  refusal and no mutation.
- The stored root version, its record, and its artifact/brief members are
  byte-identical before and after a rollback, regardless of whether the
  roadmap's live working artifacts have diverged from that stored content.
- Every invocation checks for an existing receipt (via `read_evidence_final`
  at the address derived from the roadmap slug, the target version id, and a
  fixed confirmed-intent marker constant — never the timestamp or any
  call-specific value) *before* evaluating eligibility. Only its absence
  proceeds to eligibility.
- A matching receipt reports the idempotent already-rolled-back outcome with
  no eligibility check. If `accepted-head.json` still names exactly the
  matched target, that pre-check completes the interrupted clear (recovering
  from a crash between the original receipt write and selector clear)
  instead of merely re-reporting success; if the selector already differs —
  absent, or naming a different, later-enrolled root — it is left untouched.
- On a genuinely eligible target with no existing receipt, rollback
  publishes the receipt through `publish_evidence` (which root, when, under
  what confirmed operator intent) and only then clears the selector; a
  `publish_evidence` failure aborts before the selector is touched.
- Rollback is idempotent — a repeated call with the same named target
  version id is caught by the receipt pre-check above, never falls through
  to an ordinary ineligibility refusal, never writes a second receipt, and
  never leaves a receipt permanently orphaned from a stale selector — and
  never instructs the operator to delete a file by hand.
- Concurrent rollback and another lifecycle writer for the same slug
  serialize through the existing writer lock rather than racing.
- `--rollback-root TARGET_VERSION_ID` carries the target and
  `--confirm-root-rollback` is the required bare confirmation boolean,
  matching the existing `--reopen-feedback`/`--confirm-feedback-reopen`
  shape.
- Every pinned or restated "only promotion changes the accepted head"
  exclusivity claim (`ROADMAP_FORMAT.md` and its drift-guard test,
  `BACKLOG.md` #328, `docs/history/backlog-decisions.md` #328) names both
  writers instead of claiming exclusivity, with the drift-guard test updated
  in the same change as the wording it pins.
- `BUG_BACKLOG.md` no longer lists this bug after focused tests and the
  complete suite pass.

## Deferred

If an eligible-but-ambiguous state turns up (for example a candidate
admission that was itself rolled back or abandoned), leave it refused and
record the separate requirement in `BUG_BACKLOG.md` or `BACKLOG.md` rather
than widening this route's eligibility predicate.
