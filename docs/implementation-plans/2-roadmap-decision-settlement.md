---
format_version: 1
title: Roadmap Decision Settlement
intent: '`plan-tool roadmap` gains one bounded, operator-confirmed action that transitions
  a single Roadmap-derived `decisions` row from `status: pending` to `status: settled`
  in place, bound to explicit reviewed evidence, publishing a durable receipt — for
  both an un-enrolled and an enrolled roadmap — with no hand-edit of a canonical artifact
  and no bulk/batch form.'
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/roadmap-decision-settlement.md
steps:
- id: 1
  title: Add a settle-one-decision helper to plan_tool/roadmap_artifacts.py and correct
    DecisionStatus's hand-edit docstring; replace_design_row keeps refusing enum fields
    and no existing write path is narrowed or retired
  intent: Give the whole plan one owner for the rule 'only status changes on exactly
    one Roadmap-derived decision row', so every later step preserves the other fields
    by construction instead of re-deriving the guarantee.
  files:
  - plan_tool/roadmap_artifacts.py
  - tests/test_roadmap_artifacts.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/01-settle-one-decision-helper-plan-tool.md
  status: done
- id: 2
  title: Add a decision-settlement preflight leaf that resolves the decision target,
    matches feedback evidence to it by FeedbackTargetKind.ROW/row_id rather than just
    resolving the feedback id, accepts any FeedbackState, requires un-enrolled baseline
    admission before reading the source, and computes the predecessor digest — reading
    enrolled content from the accepted version, not on-disk stage files — with one
    named refusal per rejection class
  intent: Prove, before any write, that exactly one live Roadmap-derived pending decision
    was named with no duplicate id in the artifact, that a named live feedback row
    (no duplicate id either) actually targets it (not just resolves) and carries non-empty
    reviewer-authored `request` text in any FeedbackState (never model-authored `proposed_response`),
    that an un-enrolled source is admitted against its recorded baseline and is render-canonical,
    and that the source bytes (on-disk artifact for an un-enrolled roadmap) and, on
    an enrolled roadmap, the accepted head's own identity have not moved since the
    evidence was read.
  creates:
  - plan_tool/roadmap_decision_settlement.py
  - tests/test_roadmap_decision_settlement.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the transition helper the preflight's candidate is built against, and the byte-preservation
      contract its staleness recheck re-verifies
  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/02-decision-settlement-preflight-leaf-that.md
  status: done
- id: 3
  title: Add the immutable settlement receipt record, its own evidence namespace in
    plan_tool/roadmap_evidence_store.py, and a read-back check that takes a receipt
    plus the roadmap's current state and reports whether it still proves a completed
    settlement (accepted-version-or-predecessor membership on the enrolled lineage;
    exact current-digest match, including a deleted evidence feedback row, on the
    un-enrolled one); the receipt names the exact resulting content digest settlement
    is about to produce, is committed to HEAD (created/reused/committed-existing vs.
    commit-failed/collision/storage-rejected/invalid-existing-receipt/no-worktree),
    and publication stays create-once and keyed on its own inputs so a retry resolves
    to the same already-published final, an existing final is returned rather than
    overwritten, and nothing is deleted
  intent: Make every successful settlement leave a durable, readable, committed record
    — created before the canonical write it proves, never after — of which artifact,
    decision, predecessor digest, feedback evidence, and resulting content digest
    justify it, with a shipped check (not a manual procedure) for whether that proof
    still holds later, so a receipt never outlives or outraces the settlement it names.
  files:
  - plan_tool/roadmap_evidence_store.py
  - tests/test_roadmap_evidence_store.py
  creates:
  - plan_tool/roadmap_decision_settlement_receipt.py
  - tests/test_roadmap_decision_settlement_receipt.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: the admitted selector, evidence identity, and source digest that are the receipt's
      recorded facts
  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/03-immutable-settlement-receipt-record-its.md
  status: done
- id: 4
  title: Settle one decision on an un-enrolled roadmap by publishing its receipt first,
    then, once source admission and staleness both hold, publishing through publish_stage_artifact's
    multi-member generation with its default seed-invalidation behavior (never invalidate_seeds=False),
    keeping the existing journal recovery (roll back or drop an in-flight generation)
    unchanged and updating the selected artifact's bytes, its stage baseline record,
    and tracked derived seed state (marked invalidated, exactly like any other stage-level
    content change) together — no other artifact or stage is rewritten
  intent: Let an operator settle an approved decision on an ordinary roadmap by naming
    it, naming its evidence, and confirming — with no hand-edit of a canonical artifact,
    and with a receipt that always precedes the write it proves.
  files:
  - plan_tool/roadmap_revision_publish.py
  - tests/test_roadmap_revision_publish.py
  creates:
  - plan_tool/roadmap_decision_settlement_run.py
  - tests/test_roadmap_decision_settlement_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: the preflight candidate, its source-admission check, and its final staleness
      recheck, called inside the writer lease before the artifact is replaced
    3: the receipt writer, called before the artifact write, not after
  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/04-settle-one-decision-on-un-enrolled.md
  status: done
- id: 5
  title: Settle one decision on an enrolled roadmap by storing the settled artifact
    bytes as an ordinary version_kind candidate record — via create_candidate_version,
    with a new dedicated no-review sentinel in place of INITIAL_EMPTY_REVIEW_LINEAGE_ID,
    a settlement-owned content_identity, and no candidate_evidence_path/replacement_evidence_path
    entries — then advancing the accepted head through a new additive PendingGeneration.kind
    recovery branch that reuses promote_review_seal's writer-token/journal selector-swap
    but never calls _load_complete_sealed_candidate or either evidence loader; recovers
    a recognized completed version-owned generation exactly as existing recovery does
    and refuses anything else; refuses whenever the current accepted head carries
    an admitted, unpromoted candidate lineage, clearing only once that same lineage
    is promoted (nothing time-bounds a response-rejected retry or an unanswered question,
    and no route abandons the admission early); root-enrollment and review-seal-promotion
    recovery stay exactly as they are, and stored version members are never overwritten
    or deleted
  intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one,
    for a decision whose approving feedback already exists in the accepted version
    (nothing can add feedback to an enrolled roadmap today), without ever editing
    its accepted head in place, without fabricating a synthetic model-authored candidate/review/seal
    chain, evidence file, or content_identity to satisfy promote_review_seal's existing
    preconditions, and without any accepted-head write path outside the guarded selector
    swap.
  files:
  - plan_tool/roadmap_revision_publish.py
  - tests/test_roadmap_revision_publish.py
  creates:
  - plan_tool/roadmap_decision_settlement_enrolled.py
  - tests/test_roadmap_decision_settlement_enrolled.py
  complexity: high
  change_type: feature
  depends_on:
  - 4
  depends_on_notes:
    4: the shared preflight-to-receipt sequence and the settled-artifact bytes, which
      this step stores as a version instead of writing over the stage file
  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/05-settle-one-decision-on-enrolled-roadmap.md
  status: done
- id: 6
  title: Add the decision selector, evidence selector, and required confirm flag to
    plan-tool roadmap as one exclusive action (missing-confirm and companion-option
    refusals named, matching --reopen-feedback's confirmation-required/mode-rejected
    precedent), extend every other broad roadmap mode's own _*_has_conflict check
    to refuse when the settlement flags are present (exclusivity in both directions,
    not only the settlement flags refusing others), regenerate docs/cli/roadmap.md,
    and prove both lineages produce the same settled row and that check_settled_decisions
    refuses drift on an un-enrolled settled row this route just settled
  intent: Give the operator the actual command, with the confirm flag that makes settlement
    their decision rather than the tool's and no backend call anywhere on the path,
    make that exclusivity hold no matter which side names the conflicting option rather
    than letting a combined command silently run a different action and drop the settlement
    request, then show the enrolled and un-enrolled paths are one capability rather
    than two look-alikes by asserting identical before/after row content across both
    — proving only the un-enrolled drift refusal, not any claim about the enrolled
    lineage, which step 7's docs disclose separately.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  - tests/test_roadmap_gates.py
  - docs/cli/roadmap.md
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  - 5
  depends_on_notes:
    4: the un-enrolled runner and its redacted terminal result the handler renders
    5: the enrolled runner the handler selects when the roadmap carries an accepted
      head
  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/06-decision-selector-evidence-selector.md
  status: done
- id: 7
  title: Document the settlement route; retire every live hand-edit settlement instruction
    (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md, RUNBOOK.md,
    docs/how-to/use-cases.md, integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md,
    docs/how-to/roadmap.md) with recovery guidance for an operator who already followed
    that advice; state that --revise-feedback still cannot change status; correct
    ROADMAP_FORMAT.md's Immutable candidate-version authority block and CAPABILITIES.md's
    accepted-head-authority statement to name both guarded writers, updating tests/test_roadmap_format.py::test_candidate_policy_reference_keeps_review_inert_until_exact_promotion
    to match, and separately correct the Decision status paragraph and gate-table
    row to confine the drift-protection claim to the un-enrolled lineage; add a settlement
    bullet to CAPABILITIES.md's roadmap entry beside the other roadmap actions, covering
    both lineages; state all three enrolled settlement limits with their backlog pointers
    (citable feedback must predate enrollment, backlog entry 394; an admitted candidate
    lineage the operator never finishes blocks settlement with no way to abandon it,
    backlog entry 395; non-canonical accepted bytes block settlement with no repair
    path) and that closing (deleting) the cited feedback row ends an un-enrolled receipt's
    proof; add the settlement receipt as a third EvidenceNamespace in docs/ARCHITECTURE.md;
    extend the "Incomplete immutable lifecycle journals" BUG_BACKLOG.md entry to name
    the new settlement generation shape(s); and remove the settlement BUG_BACKLOG.md
    entry now that the capability ships
  intent: Leave one honest account of how a decision is settled, which lineage's settled
    decisions are actually protected from later drift, and exactly when enrolled settlement
    can never succeed, so no reader is still told to hand-edit a canonical artifact
    (or left stranded after having done so), no shipped doc or pinning test still
    claims only one accepted-head writer exists, the app-level capability catalog
    lists this action like every other roadmap action, and no one re-files a bug that
    has shipped.
  files:
  - ROADMAP_FORMAT.md
  - docs/how-to/roadmap.md
  - README.md
  - docs/how-to/common-workflows.md
  - docs/how-to/roadmap-demo.md
  - RUNBOOK.md
  - docs/how-to/use-cases.md
  - docs/ARCHITECTURE.md
  - integrations/shared/DIRECTIVES.md
  - CLAUDE.md
  - CAPABILITIES.md
  - tests/test_roadmap_format.py
  - BUG_BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 6
  depends_on_notes:
    6: the shipped flag names, refusal messages, and cross-lineage proof the docs
      describe, read off the landed parser and tests rather than off this plan
  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/07-document-settlement-route-retire-every.md
  status: done
---
# Roadmap Decision Settlement

## Overview

The only *documented* way to settle a load-bearing `pending` decision is a
manual edit of the artifact's `status` field followed by re-entering at that
stage (`docs/how-to/roadmap.md` §4: "That edit is the resolution; there is no
separate settle command"). That documented procedure already fails on any
stage with a recorded baseline: a decision's `status` is part of
`canonical_projection`, so the hand-edited artifact no longer matches its
`.roadmap-baselines` record, and re-entry refuses it —
`roadmap.py:_admit_loaded_stage_artifact` raises "source changed outside
reviewer feedback" (pinned by
`tests/test_roadmap.py::test_semantic_reentry_drift_returns_invalid_
without_invocation`). `--revise-feedback` can record approval prose, but its
field-authority allowlist excludes `status`, so a decision an operator has
already approved through ordinary review stays `pending`, contradicting its
own recorded rationale and feedback. This effort adds the missing narrow
transition route, following the same shape this roadmap subsystem already
uses for other single-row, evidence-bound, confirmed state changes
(`--reopen-feedback`, `--escalate-feedback`), and its own preflight refuses
exactly the drifted-baseline state the documented hand-edit produces —
an operator who already followed that documented advice must restore the
row's pre-edit bytes before the settle command will run.

## Problem statement

`DecisionStatus` (`plan_tool/roadmap_artifacts.py`) has exactly two members,
`pending` and `settled`; `DecisionRow` carries `chosen_option`,
`rejected_alternatives`, `rationale`, `anchor`, `status`, and an optional
`source`. `decisions` is a field on all four staged artifacts
(Domain/Constraints/Components/Plans), not one file. `TEXT_FIELDS_BY_ROW_TYPE`
in `plan_tool/roadmap_revision.py` is the field-authority allowlist for the
generic, unconfirmed `--revise-feedback` local-revision path; it names only
`("rationale",)` for `decisions`, so `status` is structurally excluded from
it. Settlement does not add `status` to that allowlist or route through
`preflight_feedback_revision` — doing so would open an unconfirmed,
evidence-free path to flip a decision's status, the opposite of the
narrow, evidence-bound action this plan builds. `replace_design_row`
(`plan_tool/roadmap_artifacts.py`) already refuses any field whose current
value is an `enum.Enum`, so `status` needs its own dedicated transition
helper regardless; `check_settled_decisions`
(`plan_tool/roadmap_gates.py`) already refuses a *settled* decision's id,
status, chosen option, or anchor from drifting; it does not, and must not
start to, gate `pending → settled` itself. `settled` is not rare today: the
domain stage prompt instructs "Use `settled` otherwise" for a decision the
brief already resolves, so ordinary model-authored stage authoring is the
dominant route; an ordinary un-enrolled revision can newly settle a decision
too (`ROADMAP_FORMAT.md` lists "decisions the revision newly settled" as
expected run residue); a candidate proposal on an enrolled roadmap can
already change a decision's `status`, including to `settled`, as ordinary
delta content; and a hand-edit is the only *documented* way an operator
flips an existing `pending` row today, even though it already fails source
admission on re-entry for any stage with a recorded baseline. None of
these is operator-confirmed and evidence-bound the way every other narrow
roadmap action already is — that
absence, not the absence of any route to `settled` at all, is this plan's
actual gap.

## Architecture

- **Scope of the transition.** The route accepts exactly one decision
  selector (artifact key + decision id, mirroring `ReceiptSafeSelector`) and
  performs only `pending → settled` on that row. `chosen_option`,
  `rejected_alternatives`, `rationale`, `anchor`, and every other row in every
  artifact are byte-preserved. A decision whose `source is not None`
  (inherited) is refused under the same rule `preflight_feedback_revision`
  already applies to inherited-row edits (unconditionally refused), with
  settlement's own named reason and wording — settlement is for
  Roadmap-derived decisions only. The inherited-row check runs **before**
  the non-pending/"already
  settled" check: an inherited row is always `settled`
  (`check_inherited_decisions` requires it), so checking status first would
  make the inherited-row refusal unreachable and untestable.
- **Evidence is a binary fact, not a semantic judgment.** The route cannot
  determine whether a human genuinely reviewed a decision — that property is
  unobservable. It requires and checks only checkable facts: a second
  selector naming one live `feedback` row in the same artifact that
  **targets the decision** — defined exactly as `target.kind is
  FeedbackTargetKind.ROW and target.row_id == <decision id>`; a row whose
  `target.kind` is `ARTIFACT`, or whose `row_id` names a different row, does
  not target it and is refused under its own named reason, distinct from
  "the selector doesn't resolve at all" — whose `request` field — "the
  reviewer's own words," per `FeedbackRow`'s own docstring, and never
  rewritten by the model — is non-empty, plus the operator's own required,
  argument-less confirm flag (no `-y` substitute, matching
  `--confirm-feedback-reopen`). `proposed_response` is explicitly not
  eligible evidence: its own docstring states it "is what the model offered
  back." The route asserts "this reviewer-authored evidence exists, targets
  this decision, and was named," never "the approval was sound."
- **Feedback-state eligibility: any live state qualifies, no `OPEN`-only
  gate.** `request` is set once and never rewritten by the model regardless
  of the row's later `FeedbackState`, so evidence eligibility does not
  depend on state — `open`, `awaiting-review`, and `deferred` all qualify.
  This deliberately does **not** carry over
  `preflight_feedback_revision`'s `FeedbackState.OPEN`-with-no-
  `proposed_response` precondition: that precondition protects a different
  workflow (proposing a fresh response), and applying it here would refuse
  this plan's own motivating case — an ordinary `--revise-feedback` reply
  leaves the row `awaiting-review` with a `proposed_response` set, and
  `request` is exactly what an operator writes to record an approval
  through that reply. Today's only way to close (delete) a feedback row
  destroys its evidence value; an operator who also wants to close the
  cited row must settle first.
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
- **Un-enrolled roadmap.** A decision's `status` is part of
  `canonical_projection` (only `feedback` is excluded from the baseline
  digest), so a write touching only the artifact bytes — the shape
  `--reopen-feedback` gets away with, because feedback is the one thing the
  baseline ignores — would desync that stage's `.roadmap-baselines` record
  from the artifact on the very first settlement, permanently failing every
  later `admit_baseline_backed_source` check on that stage (another
  settlement, a `--reopen-feedback`, or an `--escalate-feedback`). The route
  instead publishes through `publish_stage_artifact`'s existing multi-member
  generation (`roadmap_revision_publish.py`) — the same primitive an
  ordinary stage revision uses — so the artifact bytes and the stage
  baseline record update atomically together, using
  `publish_stage_artifact`'s **default** seed-invalidation behavior
  (`invalidate_seeds=None` resolves to `True`), never `False`. A draft seed
  carries a decision's chosen option forward as a "settled fence"
  (`prompts/roadmap-seed.md`), and `ROADMAP_FORMAT.md` § "Invalidation and
  explicit refresh" already marks every tracked derived seed invalidated on
  exactly this kind of content change; settlement is not a special case
  that content change doesn't apply to. No other artifact or unrelated
  stage's baseline is touched.

  Before that write, settlement also requires the stage's on-disk artifact
  to be admitted against its recorded baseline — the same
  `admit_versioned_artifact_source`/`admit_baseline_backed_source` check
  `roadmap_feedback_reopen.py` and `roadmap_escalation_run.py` already run
  first — **in addition to, not instead of**, the predecessor-digest
  staleness recheck immediately before publish: baseline admission proves
  the source is the reviewed, canonical content before evidence is even
  read; the staleness recheck only catches a race after it was read.
  Without admission, an unreviewed hand edit to a different row in the same
  file — including a hand edit that flips a different decision to
  `settled`, the exact route this plan replaces — would become the stage's
  new admitted baseline as a side effect of settling the selected decision.
  A stage with no recorded baseline refuses rather than settlement silently
  creating one from unadmitted bytes.

  Baseline admission alone does not prove the source is in the parser's
  exact rendered form: `admit_baseline_backed_source` compares only
  `canonical_projection`, a semantic digest that ignores exact bytes.
  Settlement also requires a render-canonical check —
  `roadmap_escalation_selection.py:canonical_artifact_snapshot`, the same
  distinction `--reopen-feedback` (`source-not-canonical`) and
  `--revise-feedback` (`preflight_feedback_revision`'s
  `RenderCanonicalMismatch`) already enforce — and refuses a non-canonical
  source under its own named reason, never silently rewriting bytes outside
  the selected row to make it canonical. The common trigger is an operator
  hand-filling the `_NO_FEEDBACK_KEY_COMMENT` stub to write the very
  feedback row settlement will cite: that file is non-canonical until its
  owning stage is re-run with `--from-stage`, which an operator must do
  before the evidence becomes citable.
- **Enrolled non-canonical bytes are a standing, permanent limitation, not
  a repair target.** `roadmap_versions.py:prepare_root_version_from_snapshot`
  captures on-disk text with no render-canonical check, so an accepted
  version can hold non-canonical bytes for a decision's owning artifact
  indefinitely. Settlement refuses there exactly as it does on an
  un-enrolled roadmap, which means a decision on such an artifact cannot be
  settled until a future re-enrollment or repair path exists — this plan
  does not attempt one; it is a known residual limitation, stated plainly
  rather than silently.
- **Enrolled roadmap.** `promote_review_seal` (`roadmap_version_promotion.py`)
  is not a generic accepted-head write: it requires a full model-authored
  `CandidateProposalAdmission` → reviewer answer → `CandidateReviewSeal`
  chain (via `_load_complete_sealed_candidate`), and it is the sole existing
  writer of `accepted_head_path` after root enrollment. Reusing it as-is
  would mean fabricating a synthetic model-provenance record for a change
  nothing proposed or reviewed that way.

  Settlement stores its settled artifact bytes as an ordinary
  `version_kind: "candidate"` record via the existing
  `create_candidate_version` (`roadmap_versions.py`) — the closed
  `root`/`candidate` vocabulary is not widened, because
  `_load_complete_sealed_candidate`'s two evidence loaders
  (`load_stored_candidate_proposal`, `load_stored_candidate_review_replacement`)
  are reachable only from the model-authored propose→review→promote pipeline
  itself, never from `load_accepted_version` or any other generic content
  read — a candidate record with no matching on-disk evidence file is
  therefore safe as long as nothing routes it through that pipeline.
  `review_lineage_identity` is a new, distinct, digest-shaped sentinel
  constant named for what actually happened — "no review occurred" — never
  reusing `INITIAL_EMPTY_REVIEW_LINEAGE_ID` (which means "proposed, awaiting
  review," a state this version is never in) and never a hash of a real
  reviewer question/answer pair that was never asked. The settlement version
  never gets a `candidate_admission_path`, `candidate_evidence_path`, or
  `replacement_evidence_path` entry — those exist only for the model-authored
  pipeline this route never touches. `content_identity` — the version
  record's other required, non-null identity — is likewise settlement-owned,
  never `roadmap_candidate._content_identity` (which hashes a model-capsule
  `receipt` this route never produces): it is computed over the predecessor
  version id, the artifact key, the decision id, and the cited feedback
  row's id/digest, naming what changed and on whose evidence, not a model
  proposal that never happened.

  Evidence on an enrolled roadmap is limited to a feedback row already
  present in the accepted version: nothing can add or change a feedback row
  on an enrolled roadmap today (`roadmap_candidate.py`'s row-type delta set
  has no `feedback` entry, every writer that could add one refuses an
  enrolled roadmap through `require_unenrolled_roadmap_writer` or an
  `enrolled-roadmap-rejected` check, and `roadmap.py:enroll_roadmap_root`
  refuses re-enrollment). An approval recorded after enrollment has nowhere
  to be written and cannot be cited, so enrolled settlement only reaches a
  decision whose approving `request` predates enrollment. A route to record
  new enrolled feedback is a separate, forward-looking capability, filed as
  `BACKLOG.md` #394 rather than claimed here.

  **The candidate-lineage refusal has exactly three states, not two.** A
  roadmap's one candidate admission is created once and never deleted
  (`roadmap_candidate_run.py:candidate_admission_path`, `_create_admission`
  refuses if the file already exists) and binds permanently to one
  feedback selector. (a) **No admission exists** — settlement proceeds,
  subject to the other checks. (b) **An admission exists but its lineage
  has already been promoted** — its `predecessor_version_id` is no longer
  the current accepted head (a later version superseded it), so the
  refusal below does not fire and settlement proceeds. (c) **An admission
  exists, is unpromoted, and its predecessor is the current accepted
  head** — settlement refuses: promoting a settlement version out from
  under it would silently strand that lineage (its own
  predecessor-currency check, `_require_candidate_predecessor_is_current`,
  would then refuse the reviewer's own candidate on its next step) with no
  route left to resume it. This is a distinct refusal from an in-flight
  `PendingGeneration` journal.

  **State (c) is not a fixed set of terminal conditions — nothing in the
  code makes a `response-rejected` proposal or an unanswered question
  permanent.** A rejected proposal can be retried (re-running
  `--propose-candidate` with the same selector skips admission and calls
  the backend again); a stored candidate's question can be answered at any
  time. State (c) clears exactly when that same lineage is finally sealed
  and promoted, moving it to state (b) — there is no time limit and no
  code-level guarantee it happens, only that nothing prevents it. What is
  genuinely missing is a route to **abandon** an admission the operator no
  longer intends to finish and free the slot for a different proposal;
  without one, settlement stays blocked in state (c) for as long as the
  operator leaves that lineage unfinished, which in practice can be
  indefinite. That gap is filed as `BACKLOG.md` #395, stated as an
  accepted limitation in the acceptance criteria and step 7's docs, not a
  case this plan works around.

  Settlement's version files and the accepted-head selector swap are
  written together as members of **one** journaled `PendingGeneration`
  (the new `"decision-settlement"` kind) — matching root enrollment's
  bundled write, not the candidate pipeline's propose-then-promote split
  (where the version is stored by one generation and promoted by a later,
  separate one, because a proposal can be rejected and never promoted).
  Settlement has no such held-for-review state: preflight and gate
  validity are already fully resolved before either write begins, so
  bundling them removes the interrupted-between-the-two-writes case
  entirely — the existing journal-recovery/refuse behavior for an
  interrupted generation (case 12 below) already covers it, with no new
  retry-reuse rule needed.

  Content validity is proved with the existing
  `check_complete_roadmap_gates` evaluator (`roadmap_impact_snapshot.py` —
  the same evaluator `promote_review_seal` itself uses, and confirmed
  content-only with no version-provenance dependency); a gate violation
  refuses under its own named reason before either write in the bundled
  generation begins. `accepted_head_path` then advances under the existing
  writer-token lease and `PendingGeneration` journal — the same
  selector-swap mechanics `promote_review_seal` uses, under one new,
  additive `PendingGeneration.kind` value (`"decision-settlement"`)
  recognized by the recovery function's existing kind-branch alongside
  `"root-enrollment"`, not a change to that branch. Within **this plan's
  own new modules**, the accepted head is never written outside that
  guarded swap, and `_load_complete_sealed_candidate` or either evidence
  loader is never called; this is not a claim that no other site in the
  repository writes `accepted_head_path` — root enrollment creates it
  (not a swap) and `promote_review_seal` remains its other existing
  writer, both explicitly outside this plan's scope. Settlement runs the
  existing `recover_roadmap_publication` first, exactly as
  `--reopen-feedback` does, and refuses only a journal that recovery
  itself cannot resolve — on the enrolled side, anything other than a
  recognized, completed version-owned generation; repairing an
  unrecognized journal belongs to the separate, already-tracked
  "Incomplete immutable lifecycle journals" bug entry, deferred pending
  BACKLOG #328 sign-off and extended by step 7 to name this new generation
  shape. The preflight leaf (step 2) reads an
  enrolled roadmap's current content from
  `load_accepted_version(...).artifact_bytes` — the same source
  `roadmap_view.py:load_roadmap()` already uses for enrolled content,
  which resolves `version_id` and reads content by digest without touching
  either evidence loader — never from on-disk stage files or the
  un-enrolled `ReceiptSafeSelector` read path.
- **Receipt, written before the canonical write, never after.** The route
  creates one durable, immutable, create-once record — following the
  existing immutable-evidence pattern already used for escalation and
  impact-analysis receipts, not a new ad hoc log — naming the artifact key,
  decision id, predecessor digest, the cited feedback row's id/digest, and
  the exact resulting content digest (artifact digest for the un-enrolled
  lineage, version id for the enrolled one) settlement is about to produce.
  It follows the escalation-receipt shape and is **committed to `HEAD`
  before the canonical write begins**
  (`cli/gitcommit.py:commit_receipt`, `roadmap_escalation_run.py:
  run_roadmap_escalation_receipt`'s exact sequence), not the
  impact-analysis shape's local, gitignored evidence: a settlement receipt
  is exactly the kind of audit trail meant to travel with the repository
  and be visible to a reviewer, the same reason escalation receipts are
  committed. The receipt is created and keyed deterministically on its own
  inputs first, so a retry after an interrupted first attempt resolves to
  the same already-published final rather than minting a new one.

  **Every outcome other than `created`, `reused`, or `committed-existing`
  stops settlement before the canonical write**, exactly as the escalation
  precedent already treats them: no Git worktree
  (`receipt_worktree_for_plans_dir`), `storage-rejected`,
  `invalid-existing-receipt`, `commit-failed`, and `collision` are each
  their own named refusal reason, alongside the preflight refusals in
  Testing's numbered list. "Stops the action before any publication"
  (Testing, Acceptance criteria) means before any artifact, baseline, or
  accepted-head write — the canonical write every refusal case protects —
  not before the receipt itself: the receipt exists specifically so an
  interrupted attempt *after* a successful commit (during the canonical
  write that follows) leaves durable, inspectable evidence of what was
  attempted, never a silent retry hazard. A receipt alone proves intent
  and cited evidence, never completion by itself.

  **Read-back proof survives later change, per lineage; step 3 owns the
  check.** On the enrolled lineage, a receipt proves a completed
  settlement as long as its named version id is the accepted head **or
  any of its predecessors** — the immutable `predecessor_version_id`
  chain, not "current" alone, so a later promotion never invalidates an
  earlier settlement's proof. On the un-enrolled lineage, no digest
  history exists: `publish_stage_artifact` keeps no record of what it
  replaced, so the promise is narrower and stated as such — a receipt
  proves a completed settlement only while the named artifact digest
  still matches the stage's current content; a later edit to that same
  artifact (a second settlement, a `--revise-feedback` reply, a
  `--reopen-feedback`, a stage revision, or **closing the cited feedback
  row by deleting it** — feedback sits outside `canonical_projection`, so
  the baseline can't see that edit either) ends that proof, and the
  receipt then reads exactly like one left by a refused attempt. This is
  a stated limit, not a defect: proving completion indefinitely on the
  un-enrolled lineage would need a digest-history mechanism this plan
  does not build. The receipt module (step 3) is the one that ships this
  read-back check — a function that takes a receipt and the roadmap's
  current state and returns whether it still proves a completed
  settlement — not a manual procedure left for an operator to derive.

## Scope guardrails

- The route performs only `pending → settled` on exactly one selected,
  Roadmap-derived decision row per invocation. It never settles an inherited
  (`source is not None`) row, never reopens a `settled` row back to `pending`,
  and never accepts more than one decision selector.
- It never mutates `chosen_option`, `rejected_alternatives`, `rationale`,
  `anchor`, or any row other than the one selected.
- It never judges whether cited feedback constitutes genuine reviewer
  approval — only that a named, live feedback row targeting the decision
  (`target.kind is ROW and target.row_id == <decision id>`) carries
  non-empty `request` text (the reviewer's own words; never
  `proposed_response`, which is model-authored). Confirmation is the
  operator's, via the required confirm flag. It never gates evidence on
  `FeedbackState` — `open`, `awaiting-review`, and `deferred` are all
  eligible — and never reintroduces `preflight_feedback_revision`'s
  `OPEN`-only precondition, which would refuse this plan's own motivating
  case.
- It never mutates the cited feedback row's `FeedbackState` and never depends
  on BACKLOG #242's unshipped `closed` state landing first.
- On an enrolled roadmap it never writes the accepted head directly outside
  the guarded writer-token/journal selector swap, never fabricates a
  synthetic `CandidateProposalAdmission` or `CandidateReviewSeal` to route
  through `promote_review_seal` itself, and never writes a
  `candidate_admission_path`, `candidate_evidence_path`, or
  `replacement_evidence_path` entry — those belong only to the
  model-authored pipeline this route never touches. It never claims or adds
  a route for citing feedback recorded after enrollment — an enrolled
  roadmap's citable feedback set is exactly what the accepted version
  already carries.
- It is not a hand-edit substitute for any other field or row type, and it is
  not a batch/bulk operation.

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
  `preflight_feedback_revision`) — cited only as precedent for the existing
  refusal of any operation targeting an inherited (`source is not None`)
  decision row, which a settlement route must match. Settlement does not
  extend `TEXT_FIELDS_BY_ROW_TYPE` or route through this generic,
  unconfirmed, evidence-free `--revise-feedback` path.
- `plan_tool/roadmap_gates.py` (`check_settled_decisions`) and
  `plan_tool/roadmap_impact_snapshot.py` (`_evaluate_full_roadmap_gates`) —
  `check_settled_decisions` genuinely protects a settled decision against
  later drift on the un-enrolled lineage, where ordinary revision/reconcile
  paths build a real `predecessor`. `_evaluate_full_roadmap_gates` —
  the evaluator every enrolled candidate promotion runs through — always
  builds `predecessor=None`, so `check_settled_decisions` is a permanent
  no-op there; this is an already-live gap against existing
  settled-decision producers (tracked as its own `BUG_BACKLOG.md` entry,
  "An enrolled roadmap's candidate promotion never re-checks a settled
  decision against its predecessor"), not one this plan creates or fixes,
  and step 6 only demonstrates the protection that actually exists.
- `plan_tool/roadmap_feedback_reopen.py` and
  `plan_tool/roadmap_escalation_selection.py`
  (`ReceiptSafeSelector`, `CanonicalArtifactSnapshot.source_digest`,
  `FeedbackSelector`) — the structural precedent this route's selector,
  predecessor-digest staleness check, and named-reason refusal shape should
  follow. `roadmap_feedback_reopen.py`'s canonical-artifact write is wired
  only for an un-enrolled roadmap via `require_unenrolled_roadmap_writer`
  (`plan_tool/roadmap_revision_publish.py`), confirming the enrolled side
  has no canonical-artifact-mutation precedent to reuse as-is — this is
  what step 5 must build fresh. `roadmap_escalation_selection.py` and its
  runner `roadmap_escalation_run.py`, by contrast, call no writer guard and
  check no enrollment state at all: escalation-receipt creation already
  works unchanged on an enrolled roadmap because it writes only into the
  immutable evidence store, never a canonical artifact — an already-working
  enrolled-and-un-enrolled precedent for step 3's evidence-namespace
  receipt write. Neither touches `.roadmap-baselines`, because feedback is
  the one thing `canonical_projection` excludes from the digest; a
  decision's `status` is not excluded, so the un-enrolled write must
  instead follow `plan_tool/roadmap_revision_publish.py:publish_stage_artifact`'s
  multi-member generation, which updates the artifact and its baseline
  record together.
- `plan_tool/roadmap_version_promotion.py` (`promote_review_seal`,
  `_load_complete_sealed_candidate`), `plan_tool/roadmap_versions.py`
  (`create_candidate_version`, `load_accepted_version`,
  `INITIAL_EMPTY_REVIEW_LINEAGE_ID`), `plan_tool/roadmap_candidate_run.py`
  (`load_stored_candidate_proposal`), `plan_tool/roadmap_candidate_review.py`
  (`load_stored_candidate_review_replacement`), and
  `plan_tool/roadmap_impact_snapshot.py` (`check_complete_roadmap_gates`) —
  confirmed that the two evidence loaders are reachable only from the
  model-authored propose→review→promote pipeline (never from
  `load_accepted_version` or any other generic content read), so a
  settlement version can reuse the existing `"candidate"` `version_kind`
  unchanged — no closed-vocabulary widening — as long as it never enters
  that pipeline. `check_complete_roadmap_gates` is confirmed content-only,
  with no version-provenance dependency.
- `plan_tool/roadmap_revision_publish.py` (`recover_roadmap_publication`'s
  `generation.kind`-keyed recovery branches, including the existing
  `"root-enrollment"` branch) — the settlement promotion adds one new,
  additive `PendingGeneration.kind` value recognized alongside it, not a
  change to it.
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

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Any change to `check_settled_decisions`'s existing settled → changed
  refusal, or to how a settled decision later becomes eligible for revision
  (a reopen-style route for decisions, symmetric to `--reopen-feedback`, is a
  separate, later effort if ever needed).
- BACKLOG #242's `closed` `FeedbackState` and `RemovalRecord` decision
  reference; this effort neither ships nor depends on them.
- Any judgment, scoring, or heuristic about whether cited feedback text
  constitutes real approval; whether the `request` text is persuasive is
  never checked or gated.
- Batch/bulk settlement, and any change to `--apply`'s existing
  count-only reporting of pending decisions.
- Recovery of a malformed or interrupted immutable lifecycle journal; the
  route refuses cleanly and leaves that repair to its own tracked entry.

## Risks

- **Silent semantic overreach:** a future round could be tempted to add a
  quality check on the cited feedback `request` text ("does this really
  approve the decision?"). That is an unobservable property; keep the check
  to existence of non-empty, reviewer-authored `request` text, per
  CLAUDE.md § "Validating a semantic property you cannot observe".
- **Enrolled/un-enrolled divergence:** the two paths must produce the same
  observable row-level result (only `status` changes) even though their
  publication mechanics differ; a test asserting identical before/after row
  content across both lineages is required, not just parallel "it runs"
  coverage.
- **Gate interaction:** a settlement that races a concurrent artifact edit
  must refuse via the digest check rather than silently overwriting; verify
  against a changed-baseline fixture, not just an unchanged one. On the
  enrolled lineage, a race that replaces the accepted head with a
  different version while leaving the one edited artifact's bytes
  untouched must also refuse — checking only that one artifact's digest
  would silently drop whatever else changed in the new head.
- **Baseline desync:** an un-enrolled write that updates only the artifact
  bytes silently and permanently breaks every later baseline-admission check
  on that stage. The write must always go through `publish_stage_artifact`'s
  baseline-updating generation, never a feedback-reopen-style artifact-only
  write.
- **Synthetic provenance:** an enrolled settlement must never fabricate a
  fake `CandidateProposalAdmission`/`CandidateReviewSeal` chain, a fake
  on-disk candidate-evidence or review-replacement file, or reuse
  `INITIAL_EMPTY_REVIEW_LINEAGE_ID` (which asserts "awaiting review," not
  "no review occurred") to satisfy `promote_review_seal`'s preconditions;
  that would misrepresent a deterministic change as model-proposed and
  reviewer-sealed. The dedicated settlement sentinel and `PendingGeneration`
  kind exist precisely so nothing needs to be faked.
- **Inherited-row confusion:** an operator selecting an inherited decision by
  mistake must be refused by the same *rule* `preflight_feedback_revision`
  already applies to other inherited-row edits (`source is not None` is
  refused, unconditionally) — not its exact message, which names a
  `--revise-feedback` feedback id and local-revision framing that doesn't
  exist on the settlement path. Settlement's refusal carries its own named
  reason and wording for the same rule.
- **Overclaimed enrolled protection:** `_evaluate_full_roadmap_gates` (the
  evaluator every enrolled candidate promotion runs through) always builds
  `predecessor=None`, so `check_settled_decisions` is a permanent no-op on
  the enrolled lineage — an already-live gap (a candidate can already carry
  a `status` change on an existing settled decision today, with nothing
  refusing it; this plan does not make the gap reachable for the first
  time, only adds the first *operator-confirmed* route that lands in the
  same unprotected state), tracked as its own `BUG_BACKLOG.md` entry. This
  plan must not claim or test a drift protection on the enrolled lineage
  that does not exist; state the gap plainly instead.
- **One-sided CLI exclusivity:** the settlement flags refusing every other
  roadmap option is not the same guarantee as every other roadmap option
  refusing the settlement flags. `cmd_roadmap` dispatches each broad mode
  through its own independent `_*_has_conflict` check; adding a new
  exclusive mode requires extending every sibling's check
  (`_broad_mode_companions_present`'s documented contract). Skipping the
  other direction lets `--revise-feedback ID` plus the settlement flags
  silently run the revision and drop the settlement request with no error.

## Testing

Cover both lineages with the same row-level assertion: before/after content
of every other decision, and of `chosen_option`/`rejected_alternatives`/
`rationale`/`anchor` on the settled row itself, is byte-identical except
`status`.

**Refusal reasons — this is the canonical, complete list of preflight and
publication refusals; nothing else in this plan restates its count.**
Cover each as its own case, each with its own named, distinct reason:

1. Missing or mismatched decision target (selector doesn't resolve, or
   names an artifact that doesn't carry that id).
2. An inherited decision (`source is not None`) selected as target —
   checked, and reachable, before case 3.
3. A non-pending decision (already `settled`).
4. A decision id, or the cited feedback id, that matches more than one row
   in the selected artifact — following `roadmap_feedback_reopen.py`'s and
   `roadmap_escalation_selection.py`'s `duplicate-feedback` precedent; a
   duplicate id survives ordinary parsing and neither baseline admission
   nor un-enrolled settlement runs the gate that would otherwise catch it.
5. Missing or mismatched feedback-evidence selector (feedback id doesn't
   resolve, or resolves in the wrong artifact).
6. A resolved feedback row that does not target the decision
   (`target.kind`/`target.row_id` mismatch) — use a row that targets a
   *different* row, and separately one that targets the whole artifact.
7. Empty `request` text on an otherwise-resolved, correctly targeted
   feedback row.
8. Source not admitted against its recorded baseline, or no recorded
   baseline exists for the stage (un-enrolled only).
9. Source admitted but not in render-canonical form — `canonical_artifact_
   snapshot` returns a `NoncanonicalArtifactSnapshot` (both lineages). The
   fix is always to write the evidence row in exact rendered form (the
   route `--revise-feedback` already requires via
   `RenderCanonicalMismatch`), never to re-run the owning stage with
   `--from-stage` to "fix" canonicity — that call is model-authored and,
   per `roadmap.py:_newly_settled_decision_ids`, may itself newly settle
   the very decision settlement was about to confirm, refusing afterward
   as case 3.
10. A decision id or the cited feedback id that is not a receipt-safe id
    (`RECEIPT_SAFE_ID_RE`), matching `ReceiptSafeSelector`'s existing
    `unsafe-selector` precedent.
11. A changed source bytes digest between evidence selection and
    confirmation — the final staleness recheck (both lineages). This is
    distinct from case 8's up-front baseline-record admission: the test
    fixture edits the artifact's source bytes directly, never the
    `.roadmap-baselines` record, or the digest recheck this case exists to
    prove never fires. On the enrolled lineage this recheck also requires
    the accepted head to still name the version settlement was built on —
    not only that the one edited artifact's bytes are unchanged — since a
    different version could have become head in the meantime while
    leaving that one artifact untouched.
12. An in-flight or unrecoverable `PendingGeneration` journal — on each
    lineage, settlement first runs the existing `recover_roadmap_publication`
    exactly as `--reopen-feedback` does, then refuses only what that
    recovery itself refuses: an un-enrolled roadmap recovers a recorded
    half-written generation or drops a fully old/fully new one, refusing
    only an unrecoverable one; an enrolled roadmap drops only a
    recognized, completed version-owned generation and refuses anything
    else. Neither lineage skips recovery and refuses every in-flight
    journal outright.
13. An admitted, unpromoted candidate lineage whose predecessor is the
    current accepted head (enrolled only) — a checkable *now*-state
    condition; the three-state case matrix (no admission / promoted
    admission / unpromoted admission on the current head) is what this
    case tests, not a claim that any particular internal state (a
    `response-rejected` proposal, an unanswered question) is itself
    terminal. Separately, prove the refusal clears once that same lineage
    is promoted (state moves from unpromoted-on-head to promoted), and
    that nothing in the code bounds how long it can stay unpromoted or
    offers a way to abandon it early.
14. A `check_complete_roadmap_gates` violation on the candidate content
    (enrolled only) — for example, a gate rule that changed since the
    accepted version was stored.
15. Every settlement-receipt outcome other than `created`, `reused`, or
    `committed-existing` — no Git worktree, `storage-rejected`,
    `invalid-existing-receipt`, `commit-failed`, and `collision` — each
    stops settlement before the canonical write, matching the escalation-
    receipt precedent exactly.

**CLI-level refusals sit outside this list**, at the roadmap-command
dispatch layer (`cli/roadmap_cmd.py:cmd_roadmap`'s per-action
`_*_has_conflict` checks), matching `--reopen-feedback`'s own precedent: a
missing confirm flag (`confirmation-required`) and a companion roadmap
option (`mode-rejected`) verdict returned by the settlement runner itself.
Exclusivity holds in **both directions**: every other roadmap action's own
conflict check is extended to refuse when the settlement flags are
present, exactly as adding a new exclusive mode already requires
(`_broad_mode_companions_present`'s documented contract) — without it, a
combined command like `--revise-feedback ID` plus the settlement flags
would run the other action and silently drop the settlement request.

Separately, as a **structural guarantee, not an operator-triggerable
refusal case, and explicitly scoped to this plan's own new modules**:
prove by a test over the write call graph that none of settlement's own
modules ever writes `accepted_head_path` outside the guarded, journaled
selector swap. This does not claim no other site in the repository writes
that file — root enrollment creates it and `promote_review_seal` remains
its other existing writer, both named as deliberately out of this test's
scope, not silently excluded.

Cases 6 and 7 also need a positive case: a live feedback row eligible in
every `FeedbackState` (`open`, `awaiting-review` with a `proposed_response`
set, and `deferred`) is accepted as evidence, proving state is never a
gate. Prove the un-enrolled write leaves the stage's `.roadmap-baselines`
record matching the new artifact digest, and that a subsequent
`--reopen-feedback` or `--escalate-feedback` on the same stage still
passes `admit_baseline_backed_source` afterward. Prove the un-enrolled
write marks every tracked derived seed invalidated, using
`publish_stage_artifact`'s default seed-invalidation behavior — never
`invalidate_seeds=False`. Prove the enrolled write never constructs a
`CandidateProposalAdmission` or `CandidateReviewSeal`, never writes a
`candidate_evidence_path` or `replacement_evidence_path` entry, stores
`review_lineage_identity` as the dedicated settlement sentinel rather than
`INITIAL_EMPTY_REVIEW_LINEAGE_ID`, computes `content_identity` from the
predecessor version id, artifact key, decision id, and cited feedback
id/digest — never from `roadmap_candidate._content_identity` — and writes
its version files and accepted-head selector swap as one journaled
generation, never two separate writes. Confirm the settlement receipt is
committed to `HEAD`, is created before the canonical write, is keyed so a
retry after an interrupted first attempt resolves to the same
already-published final, names the exact resulting content digest, and
that a legacy roadmap with no receipts directory still parses and settles
correctly. Confirm a receipt's proof survives a later, unrelated change on
the enrolled lineage (the named version remains a valid predecessor of a
newer accepted head) and prove the un-enrolled lineage's proof does
**not** survive a later edit to the same artifact — the narrower, stated
promise, not a gap. Confirm `check_settled_decisions` refuses drift on an
un-enrolled row this route just settled. Do not test or claim the same
protection on the enrolled lineage: `_evaluate_full_roadmap_gates` always
builds `predecessor=None`, so `check_settled_decisions` is a documented
no-op on every enrolled candidate promotion today, already live against
existing settled-decision producers and tracked separately in
`BUG_BACKLOG.md`.

## Acceptance criteria

- An operator can settle one live, Roadmap-derived `pending` decision to
  `settled` by naming the decision, naming one feedback row with recorded
  reviewer `request` text in any `FeedbackState`, and passing the required
  confirm flag — with no hand-edit of any artifact file, on both an
  un-enrolled roadmap and an enrolled roadmap whose approving feedback
  predates enrollment, whose source artifact is render-canonical, and
  whose current accepted head carries no admitted, unpromoted candidate
  lineage. An admitted lineage the operator does not continue to
  promotion — nothing forces one to finish, and no route abandons it —
  blocks enrolled settlement on that roadmap for as long as it stays
  unpromoted; that is a stated, accepted limitation (`BACKLOG.md` #395),
  not a case this criterion claims to satisfy.
- Every field on the settled row other than `status`, and every other row in
  every artifact, is unchanged.
- Every refusal reason Testing enumerates stops the action before any
  artifact, baseline, or accepted-head write, with its own distinct, named
  reason; a refusal after the receipt was already created leaves it as
  durable evidence of the attempt, never a silent retry hazard. The
  accepted-head-write boundary is proven structurally, scoped explicitly
  to this plan's own new modules, not as a claim about every writer in the
  repository.
- The settlement flags and every other broad roadmap mode refuse each
  other in both directions: naming the settlement flags alongside another
  action's option refuses with no backend call and no write, exactly as
  naming that action's option alongside the settlement flags does.
- The un-enrolled write leaves the stage's baseline record consistent with
  the new artifact digest, so a later `--reopen-feedback` or
  `--escalate-feedback` on the same stage still succeeds, and marks every
  tracked derived seed invalidated using `publish_stage_artifact`'s default
  behavior. The enrolled write never constructs a synthetic model-authored
  candidate/review/seal chain, never claims a route to record
  post-enrollment feedback, and writes its version files and accepted-head
  selector swap as one journaled generation.
- `check_settled_decisions` is demonstrated to refuse drift on an
  un-enrolled settled row. The plan documents, rather than silently
  overclaims, that the enrolled lineage has no equivalent protection today
  (an already-live gap against existing settled-decision producers,
  tracked in `BUG_BACKLOG.md`, not fixed by this plan).
- A receipt is committed to `HEAD`, is created before the canonical write
  it proves, is retry-safe under the same inputs, names the exact
  resulting content digest, and can be read back — together with the
  current row (un-enrolled; proof holds only while the artifact still
  carries the named digest) or the accepted version or any of its
  predecessors (enrolled; proof survives later promotions) — to
  prove which evidence justified a completed settlement.
- `ROADMAP_FORMAT.md`, `docs/how-to/roadmap.md`, `README.md`,
  `docs/how-to/common-workflows.md`, `docs/how-to/roadmap-demo.md`,
  `RUNBOOK.md`, `docs/how-to/use-cases.md`, and
  `integrations/shared/DIRECTIVES.md` describe the action, no longer
  present a hand-edit as the only path, and tell an operator who already
  hand-edited a decision how to recover (restore the pre-edit bytes so the
  stage matches its baseline again).
- `ROADMAP_FORMAT.md`'s "Immutable candidate-version authority" block
  (the section carrying "Only `promote_review_seal()` changes the accepted
  head") and `CAPABILITIES.md`'s matching accepted-head-authority statement
  name both guarded writers (seal promotion and decision settlement);
  `tests/test_roadmap_format.py::test_candidate_policy_reference_keeps_
  review_inert_until_exact_promotion` — the test that actually pins that
  sentence — is updated to match. Separately, `ROADMAP_FORMAT.md`'s
  Decision status paragraph and `check_settled_decisions` gate-table row
  say the settled-decision drift protection holds only on the un-enrolled
  lineage, and `CAPABILITIES.md`'s roadmap entry gains a settlement bullet
  beside its existing per-action bullets, covering both lineages.
- `ROADMAP_FORMAT.md` and `docs/how-to/roadmap.md` state all three enrolled
  settlement limits, each with its backlog pointer: citable feedback must
  predate enrollment (`BACKLOG.md` #394); a stalled candidate lineage
  blocks settlement on that roadmap permanently (`BACKLOG.md` #395); and
  non-canonical accepted bytes block settlement with no repair path. They
  also state that closing (deleting) the cited feedback row ends an
  un-enrolled receipt's read-back proof.
- `docs/ARCHITECTURE.md`'s "Immutable roadmap evidence" section names the
  settlement receipt as a third `EvidenceNamespace` alongside escalations
  and impact analyses, and describes the four new settlement modules.
- The `BUG_BACKLOG.md` entry "Incomplete immutable lifecycle journals" is
  extended to name the new decision-settlement generation shape(s), and
  the entry "An enrolled roadmap's candidate promotion never re-checks a
  settled decision against its predecessor" is left as-is (owned
  separately, not by this step).
- The final plan step removes the `BUG_BACKLOG.md` entry for this feature
  only after every step above ships.

## Deferred

A symmetric "un-settle" / reopen route for a `settled` decision, BACKLOG
#242's feedback-closing work, and any repair path for a malformed immutable
lifecycle journal all remain separate efforts. Also deferred: giving
`_evaluate_full_roadmap_gates` a real predecessor so `check_settled_decisions`
actually protects a settled decision against a later enrolled candidate
promotion — an already-live gap against existing settled-decision
producers, filed as its own `BUG_BACKLOG.md` entry rather than bundled
into this feature, since it changes the shared evaluator every candidate
promotion runs through. A route to record new reviewer feedback on an
enrolled roadmap after enrollment is filed as `BACKLOG.md` #394; a route
to abandon an admitted candidate lineage the operator does not intend to
finish, freeing the slot for a different proposal, is filed as
`BACKLOG.md` #395. Both are separate forward-looking capabilities this
plan does not build. File any newly discovered gap in `BACKLOG.md` or
`BUG_BACKLOG.md` rather than expanding this plan.
