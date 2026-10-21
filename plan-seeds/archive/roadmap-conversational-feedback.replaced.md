> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-conversational-feedback.md`.
> Preserved here for history; do not edit.
> **Identifier correction 2026-09-01:** the `#325` citations below are
> historical branch-local labels for the retired proposal, not references to
> the current `BACKLOG.md` #325 entry.

# Conversational roadmap feedback into a reviewed cross-artifact change set

Seed for `BACKLOG.md` **#325 — "Interpret conversational roadmap feedback into a
reviewed cross-artifact change set"**. The resulting plan updates that entry when
the work ships. Routed by
[`backlog-arc-roadmap.md`](../docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md)
§ "Ordered route" as the next priority **after** the roadmap lifecycle-output
entry ships, so an operator can watch this route's long analysis and authoring
calls. It inherits #325's scope contract and elaborates it; it invents no
different fence.

## Outcome

One conversational reviewer feedback message produces one auditable, validated,
all-or-nothing revision across every roadmap artifact it actually affects.
Reviewer prose is immutable input and never write authority: a model may
*propose* an impact manifest, deterministic code validates its identities and
declared-relation closure, an explicit acceptance is required before any
candidate is built, and a rejected, stale, ambiguous, or invalid proposal leaves
every canonical artifact, baseline, and seed record byte-for-byte untouched.

## Overview

The Integration `project-workspace-membership-proof` review (2026-08-31) supplied the
motivating case: a reviewer described **one** natural membership-capability
reframing, and the current mechanism required that single thought to be
pre-split by hand into per-row operations, because the shipped routes each bound
authority deliberately narrowly.

**What already exists is more than half of this, and the seed's first job is to
not rebuild it.**

- **Cross-artifact closure is shipped, deterministic, and read-only.**
  `roadmap_impact_relations.py:65 resolve_impact_closure` is a fixed-point loop
  over the node set of **all four** artifacts. `_relation_touches_reached`
  (`:212`) matches on owner key *or* endpoint `row_id` regardless of artifact,
  and `_unambiguous_endpoint` (`:230`) resolves by global row id — so traversal
  already hops artifacts in both directions and **fails closed** on ambiguity
  with verdict `unmappable-relation` (`:20`).
- **The handoff this seed fills is already named in code and has zero
  consumers.** `roadmap_impact_analysis.py:69 CROSS_ARTIFACT_WORKFLOW =
  "roadmap-cross-artifact-revision-transaction"`, assigned by `_classify_route`
  (`:785`) whenever the closure spans more than one artifact, persisted in the
  immutable v2 analysis record and logged (`roadmap_impact_run.py:114`,
  `run_log.py:727`, `:2850`). Nothing dispatches on it. It is a named
  destination with no road.
- **All-or-nothing publication is already N-member.**
  `roadmap_revision_publish.py:847 _publish_generation` is a journal → replace →
  verify → clear protocol over an ordered `PendingGeneration` of arbitrarily
  many `GenerationMember`s, with a recorded `old_bytes`/`new_bytes` per member
  and roll-*back*-only recovery (`:315 recover_roadmap_publication`).
  `enroll_stage_baselines` already publishes a multi-stage generation through
  it.

**So the gap is the writer side, not the analysis side.** Exactly two things pin
the system to one artifact: `_publication_members` (`roadmap_revision_publish.py:792`)
takes a **scalar** `artifact_path` and therefore emits one artifact member, and
`check_full_roadmap_gates` (`roadmap_impact_snapshot.py:298`) accepts **one**
`CandidateSubstitution` (`:65`, a single `stage_index` + artifact substituted
from that stage onward). Everything else about a transaction is present.

## Problem statement

Three bounded authorities, each individually correct, jointly make the Integration case
unexpressible:

1. **One material operation per feedback item.**
   `roadmap_revision.py:515 STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK = 1`,
   enforced at `:1394-1401`, whose remedy string is literally
   `:516 STAGE_SPLIT_FEEDBACK_ACTION = "split the feedback into smaller
   requests"` — the tool telling the reviewer to do the decomposition by hand.
2. **A row edit may not change a declared relation.** Enforced at bind and merge
   time — `roadmap_relations.py:183 same_declared_row_relations` via
   `roadmap_revision.py:1653 _validate_unchanged_relations` and
   `roadmap_revision_patch.py:521` — and again structurally by
   `roadmap_structural_revision_proof.py:346 _require_relation_inventory`, which
   compares `extract_declared_relations` across all four artifacts and rejects
   any change to the inventory. **Note: no gate in `roadmap_gates.py` does
   this**; it is not gate machinery to widen.
3. **Publication selects one artifact.** Structural, not asserted — every writer
   funnels through the scalar-`artifact_path` `_publication_members`.

A reframing that moves ownership between components, retargets a business rule,
and re-orders a plan row is one reviewer thought that touches three artifacts
and necessarily changes declared relations. Under (1)–(3) the reviewer must
pre-split it into a sequence of per-artifact requests, each of which must
individually preserve relations — which the intermediate steps cannot do while
remaining coherent. The bounded routes are right for what they own; the missing
piece is a separate, more strongly reviewed route for the case they exclude.

## Architecture

### Three phases, and the authority boundary between them is the whole design

**Reviewer prose → (model) proposed impact manifest → (human) acceptance →
(deterministic) candidate, gates, publication.** The model participates in
exactly one phase and its output is a *proposal*, never an edit. Deterministic
code owns identity validation, declared-relation closure, gating, and the write.

**Guarantee, must not drift: no canonical byte changes before an explicit
acceptance.** The mechanism is that manifest analysis and acceptance produce
**no `PendingGeneration` at all** — the transaction publisher is not reachable
from the analysis phase — and its owning destination is the analysis/manifest
module, ordered strictly before any candidate construction exists. This is the
same shape as the existing evidence routes: `roadmap_impact_run.py` writes an
evidence final, a run log, and a lock file, and touches no artifact.

### Reuse the shipped closure; the model proposes *beyond* it, never instead of it

`resolve_impact_closure` stays the deterministic floor and is **not modified**.
Its result is computed independently of the model and the two are reconciled:

- A model-proposed impact that is **inside** the declared closure is admissible
  for review.
- A model-proposed impact **outside** it is admissible only as an explicitly
  flagged extension the reviewer must accept — it is exactly the semantic
  judgment prose can carry and declared relations cannot.
- A closure member the model **omitted** is surfaced, never silently dropped.
  Omission is the backlog entry's named risk and must be visible.
- A closure verdict of `invalid-target`, `target-not-live-in-selected-artifact`,
  or `unmappable-relation` refuses the route before a model call.

**The model may never shrink the deterministic closure.** That is the property;
the mechanism is that closure is computed first, by code, and the manifest is
validated against it rather than replacing it.

### The manifest is evidence — reuse the sealed store, add no storage protocol

`roadmap_evidence_store.py` already owns immutable publication: two sealed
namespaces (`:38 EvidenceNamespace` — `ESCALATIONS`, `IMPACT_ANALYSES`),
content-addressed 64-hex finals, exclusive `os.link` publication, `fsync` +
darwin `F_FULLFSYNC` before the link, deterministic exact-name reads, four
outcomes (`created` / `existing` / `invalid-input` / `write-failed`), and **no
update, delete, or overwrite function**. A manifest is evidence and stores this
way. Whether it needs a third namespace or belongs in an existing one is
`create`'s call; **`_valid_namespace` (`:95`) requires a real enum member, so a
third namespace is a deliberate, reviewed addition, not an incidental one** —
and the store's write/read primitives are not modified either way.

### The two real widenings, named precisely

Everything else is reuse. These two are genuine signature changes and the plan
should treat them as its structural core:

1. **`check_full_roadmap_gates` must accept a set of candidate substitutions**
   rather than `candidate: CandidateSubstitution | None`. The combined candidate
   is gated **as one roadmap**, against every stage's registry
   (`DOMAIN_GATES` 9, `CONSTRAINTS_GATES` 12, `COMPONENTS_GATES` 15,
   `PLANS_GATES` 13 — `roadmap_gates.py:2475-2520`), not per artifact in
   isolation. `check_duplicate_row_ids` (`:601`) is the one already-cross-artifact
   gate and is the reason per-artifact gating would be unsound here.
2. **`_publication_members` must build an N-artifact generation** — one artifact
   member and one baseline member per affected stage, and **exactly one
   seed-state member for the whole transaction**, not one per artifact.
   `_publish_generation` itself needs no change. `PendingGeneration.kind`
   (`roadmap_source_identity.py:113`) is a free string validated only as
   non-empty (`:534`), so the new transaction kind adds one value and no enum
   work — and correspondingly buys no type safety, which is a reason to keep the
   kind checked where it is consumed.

`roadmap_revision_publish.py` is the right home: layer 2, already owning the
journal, and decoupled from `roadmap.py` through its `:85 _RoadmapStage`
Protocol and lazy in-function imports. A conversational-analysis module sits at
layer 4–5 beside `roadmap_impact_analysis.py`, its runner beside
`roadmap_impact_run.py`, and its prompt joins the roadmap templates in
`plan_tool/prompts/`.

### Closed vocabularies — one is `create`'s to derive, three are frozen

**`create` derives the manifest's per-value contract.** The manifest lifecycle
is a closed state set an operator can land in, so per `SEED_FORMAT.md` it owes
each value a definition, producer, precedence against siblings, consumers, and
an exit path. Deriving that table is `create`'s job, not this seed's. Two
invariants are **not** `create`'s to choose: every state other than the applied
one leaves all canonical artifacts, baselines, and seed records untouched, and
every state an operator can land in has a stated exit.

**Frozen, and a finding proposing a member is invalid rather than deferrable:**

- **`FeedbackState` stays exactly three** — `roadmap_artifacts.py:247`: `open`,
  `awaiting-review`, `deferred`. There is **no `closed` and no `refused` state**;
  closing a request is deleting the row (`ROADMAP_FORMAT.md:676`). A
  conversational route does not get a fourth state, and #242's retention
  semantics remain #242's.
- **`RelationKind` stays exactly thirteen** (`roadmap_relations.py:28`). This
  route changes *relation instances*; it adds no relation kind and no direction
  beyond the single `OWNER_TO_ENDPOINT` (`:49`).
- **`ImpactClosureVerdict` stays exactly four**
  (`roadmap_impact_relations.py:20`).

### Flag registration follows the majority convention

A new route flag uses `_TrackExclusiveOption` and refuses companion roadmap
options, matching `--escalate-feedback` / `--analyze-escalation` /
`--rewrite-structural` (`roadmap_cmd.py:2182-2251`). Note that
`--revise-feedback` (`:2172`) is the one exclusive route registered *without*
it, so a repeated `--revise-feedback` is silently last-wins — copy the majority,
not the outlier.

## In scope

A new conversational-analysis module and its guarded runner (layer 4–5, beside
the impact modules); one new prompt template under `plan_tool/prompts/`; the
manifest record, its lifecycle, and its evidence publication; the two widenings
named above in `plan_tool/roadmap_impact_snapshot.py` and
`plan_tool/roadmap_revision_publish.py`; one new `roadmap` route flag in
`plan_tool/cli/roadmap_cmd.py`; `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`,
`docs/ARCHITECTURE.md`, `docs/cli/roadmap.md` (regenerated via
`python -m plan_tool.cli_reference --write`, drift-guarded by
`tests/cli/test_cli_reference.py`); fixtures and deterministic tests mirroring
the existing one-file-per-module convention.

### Scope contract

- **Not-allowed list, enumerated:** no change to `resolve_impact_closure`'s
  algorithm or verdicts; no new `FeedbackState`, `RelationKind`,
  `ImpactClosureVerdict`, or `ImpactRouteClass` member; no relaxation of
  `STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK`, of
  `_validate_unchanged_relations`, or of `_require_relation_inventory` on the
  **existing** routes; no automatic acceptance of a proposal, and no `-y`
  shortcut standing in for the acceptance step; no free-form or textual patch
  language — operations stay typed and closed; no whole-artifact re-emission as
  a fallback on any failure path; no update, delete, or overwrite primitive on
  the evidence store; no roll-*forward* recovery; no second writer lock or
  concurrent publication path; no change to `--from-stage`, `--revise-feedback`,
  `--reopen-feedback`, `--escalate-feedback`, `--analyze-escalation`,
  `--rewrite-structural`, or `--enroll-baselines`.
- **Allowed behavior changes:** a new, explicitly selected route may publish a
  revision spanning more than one roadmap artifact after an explicit acceptance.
  Every existing route's selection, authority, and publication contract is
  unchanged.
- **Allowed reorganization:** only the smallest seam keeping model
  interpretation separate from deterministic validation and publication — the
  two widenings above and the new module pair. No broad roadmap subsystem
  cleanup, and no consolidation of the existing revision routes.
- **Verification:** § Testing.
- **Stop / defer:** § Deferred; anything outside this fence goes to
  `BACKLOG.md` / `BUG_BACKLOG.md`, never applied as plan expansion.

## Out of scope

- A Integration or browser chat transport, or any feedback ingestion surface. The
  reviewer's message arrives the way feedback arrives today.
- A generic document editor, a free-form writer, or backend prompt/response
  streaming.
- #242's revision retention (`closed` feedback, retained closed rows, removal
  snapshots, removal-to-decision references). It is **paused** and blocked
  behind an unrelated Integration source-baseline stop; this route must not become its
  back door. This seed adds no retention semantics and no feedback state.
- The deferred `roadmap-source-baseline-recovery` proposal (declined
  2026-08-27, user-confirmed). Do not re-enter it.
- `roadmap-05` framework lenses (#208), which stays parked.
- Operations or implementation-plan feedback; this is roadmap-artifact feedback
  only.

## Risks

- **This is the "large capability" shape that inflates.** The mitigation is the
  Overview's inventory: closure, evidence storage, and N-member journalled
  publication all ship today, so any design that rebuilds one of them has
  drifted. Two widenings and one module pair is the budget.
- **The model omits a semantically affected row** — the backlog entry's own
  named risk. Mitigated by computing the deterministic closure first and
  surfacing omissions rather than accepting the manifest as the impact set; the
  model can extend the closure but never shrink it.
- **A multi-artifact write leaves an invalid intermediate state.** Mitigated by
  the existing journal-first protocol, which records every member's old and new
  bytes before any member changes and verifies all members afterwards. The new
  risk is not the write — it is building a member list that is incomplete, so
  the seed-state singleton and the per-stage baseline members need explicit
  coverage.
- **Gating artifacts separately rather than as one roadmap.**
  `check_duplicate_row_ids` is cross-artifact by construction; per-artifact
  gating would pass a candidate that is invalid as a whole. Mitigated by the
  widening being to `check_full_roadmap_gates` itself rather than by calling it
  N times.
- **Snapshot staleness across a long analysis.** The manifest binds to an exact
  snapshot; `capture_roadmap_impact_snapshot` already requires the whole roadmap
  to pass every stage gate (`roadmap_impact_snapshot.py:176`), and
  `recheck_roadmap_impact_snapshot` (`:180`) exists for the recheck. A
  conversational review may sit for days between proposal and acceptance, so
  staleness is the *common* path here, not the edge case — it must refuse
  cleanly and leave everything untouched, not attempt a rebase.
- **Bypassing the acceptance step under `-y`.** `-y` is documented as skipping
  the promote confirmation, and `--confirm-feedback-reopen` already establishes
  that *"-y is not confirmation"* for a consequential action. This route needs
  the same stance stated and tested.

## Testing

Hermetic, fixture-driven, with stubbed invokers; `tests/conftest.py:63`'s autouse
gate already refuses a real backend spawn. Mirror the existing one-test-file-per-module
convention.

- **The representative case:** a fixture reproducing the Integration shape — one
  conversational message whose coherent resolution changes declared relations
  across more than one artifact — completes end to end and publishes every
  affected artifact in one generation.
- **Nothing publishes without acceptance:** analysis alone writes a manifest,
  a run log, and no canonical byte. Assert artifact, baseline, and seed-state
  files are byte-identical after a proposal.
- **Every refusal path leaves everything untouched**, asserted by byte
  comparison of all four artifacts, every baseline, and `seed-state.json`:
  a rejected proposal; a stale snapshot; a schema-invalid manifest; a manifest
  naming an unknown row id; a manifest whose closure verdict is
  `unmappable-relation`; a combined candidate failing a stage gate; and `-y`
  supplied without an explicit acceptance.
- **Closure reconciliation, by mutation:** a manifest omitting a closure member
  surfaces the omission; a manifest extending beyond the closure is flagged as
  an extension requiring acceptance; a manifest that would shrink the closure is
  refused. Assert the deterministic closure is computed independently of the
  model reply.
- **All-or-nothing, by fault injection:** a failure injected partway through
  `_replace_generation_members` leaves a recoverable journal, and
  `recover_roadmap_publication` restores every member's `old_bytes` — including
  artifacts in stages the failure never reached.
- **The transaction's member set:** exactly one artifact member and one baseline
  member per affected stage, and **exactly one** seed-state member regardless of
  how many artifacts the transaction spans. Assert the count, not just presence.
- **Combined gating:** a candidate whose two artifacts are each individually
  valid but jointly violate `check_duplicate_row_ids` is refused — the assertion
  that proves gating is combined rather than per-artifact.
- **Carve-outs asserted, not assumed** (CLAUDE.md § Tests): a test pins that
  `FeedbackState` still has exactly three members and that `RelationKind` still
  has exactly thirteen, so widening either fails loudly here rather than
  silently downstream.
- **Existing routes unchanged:** `--revise-feedback`'s positional two-operation
  contract, the stage route's one-material-operation limit, structural
  rewrite's single-artifact publication, and `--enroll-baselines`' unenrolled-prefix
  rule all keep their current behavior under the widened publisher and gate
  signature. This is the class-sweep half — the widenings have existing callers,
  and a green suite at the new call site says nothing about them.

## Acceptance criteria

- One conversational feedback message produces one validated revision across
  every affected roadmap artifact, published as a single recoverable generation
  or not at all.
- Reviewer prose is never write authority: no canonical artifact, baseline, or
  seed record changes before an explicit acceptance, and `-y` is not acceptance.
- The deterministic declared-relation closure is computed by code, independently
  of the model; the manifest is validated against it and can extend it only with
  an explicit flag the reviewer accepts, never shrink it.
- The combined candidate is gated as one roadmap against all four stage gate
  registries, and a jointly-invalid pair of individually-valid artifacts is
  refused.
- A rejected, stale, ambiguous, schema-invalid, or gate-failing proposal leaves
  all four artifacts, every baseline, and `seed-state.json` byte-for-byte
  unchanged.
- A transaction publishes one artifact + one baseline member per affected stage
  and exactly one seed-state member; an interrupted publication recovers to
  every member's recorded `old_bytes`.
- `resolve_impact_closure`, `_publish_generation`, and the evidence store's
  publication and read primitives are unchanged.
- `FeedbackState` (3), `RelationKind` (13), and `ImpactClosureVerdict` (4) gain
  no member.
- Every existing route — `--from-stage`, `--revise-feedback`,
  `--reopen-feedback`, `--escalate-feedback`, `--analyze-escalation`,
  `--rewrite-structural`, `--enroll-baselines` — keeps its current selection,
  authority, and publication contract, with its existing tests passing.
- `CROSS_ARTIFACT_WORKFLOW` stops being a named destination with no consumer:
  an analysis classifying `cross-artifact` names a route an operator can
  actually run.
- `ROADMAP_FORMAT.md` documents the route's authority boundary, and
  `BACKLOG.md` #325 is updated when the work ships.

## Deferred

- Retiring or reconciling `roadmap_revision_publish.py:301
  preinvalidate_roadmap_seeds`, which has **zero production call sites** (only
  `tests/test_roadmap_revision_publish.py`) and whose behavior
  `ROADMAP_FORMAT.md:862-864` still describes as live — *"After the local
  preflight accepts the request, it invalidates tracked seed state before
  making its one backend request."* Both routes actually invalidate **at
  publication**, through the `on_seed_state_published` callback
  (`roadmap_revision_publish.py:566-567`, `:696-697`), wired by
  `roadmap_revision_run.py:585` and `roadmap_structural_revision_run.py:340`.
  File the doc/code drift in `BUG_BACKLOG.md`; do not inherit the ordering claim
  and do not fix it inside this effort.
- Registering `--revise-feedback` with `_TrackExclusiveOption` so a repeated
  occurrence stops being silently last-wins. Adjacent, separately filable.
- #242's retention redesign, which this route's transaction may later inform but
  neither delivers nor unblocks.
- A reviewer-facing transport for conversational feedback, if one is ever
  product-authorized.
- Widening the route to operations or implementation-plan feedback.
