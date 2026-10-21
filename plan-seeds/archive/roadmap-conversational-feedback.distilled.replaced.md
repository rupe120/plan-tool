> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-conversational-feedback.md`.
> Preserved here for history; do not edit.
> **Identifier correction 2026-09-01:** the `#325` citations below are
> historical branch-local labels for the retired proposal, not references to
> the current `BACKLOG.md` #325 entry.

## Overview

This plan adds the missing writer route for `BACKLOG.md` #325: one conversational roadmap-feedback message can produce one reviewed, validated revision across every affected roadmap artifact. Reviewer prose remains immutable input; a model proposes an impact manifest, deterministic code validates it against the declared-relation closure, and a human must explicitly accept it before candidate construction or publication. The route reuses `resolve_impact_closure`, the sealed evidence store, and `_publish_generation`, while widening only `check_full_roadmap_gates` and `_publication_members` for a combined multi-artifact transaction. Every rejection, stale snapshot, ambiguity, invalid manifest, or gate failure leaves canonical artifacts, baselines, and seed state byte-for-byte unchanged.

## Problem statement

The Integration `project-workspace-membership-proof` review (2026-08-31) exposed a case the current bounded routes cannot express: one natural reframing moved ownership between components, retargeted a business rule, reordered a plan row, touched three artifacts, and necessarily changed declared relations.

Three existing authorities jointly force the reviewer to decompose that single thought by hand. `roadmap_revision.py:515 STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK = 1` and `:516 STAGE_SPLIT_FEEDBACK_ACTION = "split the feedback into smaller requests"` permit one material operation per feedback item. `roadmap_relations.py:183 same_declared_row_relations`, `roadmap_revision.py:1653 _validate_unchanged_relations`, `roadmap_revision_patch.py:521`, and `roadmap_structural_revision_proof.py:346 _require_relation_inventory` prevent existing row-edit and structural routes from changing the declared-relation inventory; no gate in `roadmap_gates.py` owns that restriction. Finally, `roadmap_revision_publish.py:792 _publication_members` accepts a scalar `artifact_path`, so every writer publishes one artifact.

Those restrictions remain correct for their existing routes, but coherent intermediate per-artifact edits cannot satisfy them. The missing capability is a separate, more strongly reviewed route that consumes the already-named `roadmap_impact_analysis.py:69 CROSS_ARTIFACT_WORKFLOW = "roadmap-cross-artifact-revision-transaction"` and performs one all-or-nothing cross-artifact revision.

## Architecture

**Authority phases.** The route is strictly `Reviewer prose → (model) proposed impact manifest → (human) acceptance → (deterministic) candidate, gates, publication`. The model participates only in manifest proposal and never receives write authority. Manifest analysis and acceptance create no `PendingGeneration`; candidate construction and the transaction publisher remain unreachable until explicit acceptance. As with `roadmap_impact_run.py`, the analysis phase may write evidence, a run log, and a lock file, but no canonical artifact.

**Closure reconciliation.** `resolve_impact_closure` remains unchanged and runs before the model call as the deterministic floor. A proposed impact inside the declared closure is reviewable; an impact outside it is permitted only as a flagged semantic extension requiring explicit acceptance; and every closure member omitted by the model is surfaced. The model may extend the closure but never shrink or replace it. The route refuses before invoking the model when closure returns `invalid-target`, `target-not-live-in-selected-artifact`, or `unmappable-relation`.

**Manifest evidence and lifecycle.** The manifest uses `roadmap_evidence_store.py`'s immutable, content-addressed publication rather than a new storage protocol. Whether it receives a third `EvidenceNamespace` or uses an existing namespace is left for `create` to decide; `_valid_namespace` (`:95`) requires a real enum member, while the store's write and read primitives remain unchanged. `create` also derives the manifest lifecycle as a closed state set, defining each value, producer, precedence, consumers, and exit path. Every state other than the applied state leaves canonical artifacts, baselines, and seed records untouched, and every state an operator can reach has an exit.

**Combined gating.** `plan_tool/roadmap_impact_snapshot.py` widens `check_full_roadmap_gates` from one `CandidateSubstitution | None` to a set of candidate substitutions. The combined candidate is checked as one roadmap against every stage registry—`DOMAIN_GATES` 9, `CONSTRAINTS_GATES` 12, `COMPONENTS_GATES` 15, and `PLANS_GATES` 13 in `roadmap_gates.py:2475-2520`—rather than checking each artifact independently. This preserves cross-artifact checks such as `check_duplicate_row_ids` (`:601`).

**Atomic publication.** `plan_tool/roadmap_revision_publish.py` widens `_publication_members` to construct one N-artifact `PendingGeneration`: one artifact member and one baseline member per affected stage, plus exactly one seed-state member for the transaction. `_publish_generation` remains unchanged and continues to provide journal → replace → verify → clear publication with rollback-only recovery. `PendingGeneration.kind` in `roadmap_source_identity.py:113` remains a non-empty free string under `:534`; the new kind is checked at its consumers rather than adding enum machinery.

**Placement and route selection.** `roadmap_revision_publish.py` remains the layer-2 journal owner, using its `:85 _RoadmapStage` Protocol and lazy imports to stay decoupled from `roadmap.py`. A new conversational-analysis module sits at layer 4–5 beside `roadmap_impact_analysis.py`, its guarded runner sits beside `roadmap_impact_run.py`, and its prompt is added under `plan_tool/prompts/`. A new route flag in `plan_tool/cli/roadmap_cmd.py` uses `_TrackExclusiveOption` and rejects companion roadmap options, following `--escalate-feedback`, `--analyze-escalation`, and `--rewrite-structural` rather than the last-wins `--revise-feedback` outlier.

**Frozen contracts and compatibility.** `FeedbackState` in `roadmap_artifacts.py:247` remains exactly `open`, `awaiting-review`, and `deferred`; closing still deletes the row under `ROADMAP_FORMAT.md:676`. `RelationKind` in `roadmap_relations.py:28` remains exactly thirteen values with the single `OWNER_TO_ENDPOINT` direction at `:49`, and `ImpactClosureVerdict` in `roadmap_impact_relations.py:20` remains exactly four values. Existing restrictions—including `STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK`, `_validate_unchanged_relations`, and `_require_relation_inventory`—remain intact on every existing route. Documentation updates cover `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, `docs/ARCHITECTURE.md`, and generated `docs/cli/roadmap.md` via `python -m plan_tool.cli_reference --write`.

## Out of scope

- A Integration or browser-chat transport, or another feedback-ingestion surface; the reviewer message arrives through the current feedback path.
- A generic document editor, free-form writer, or backend prompt/response streaming.
- #242 revision retention, including `closed` feedback, retained closed rows, removal snapshots, and removal-to-decision references; it remains paused behind the unrelated Integration source-baseline stop.
- The declined `roadmap-source-baseline-recovery` proposal from 2026-08-27; do not re-enter it.
- `roadmap-05` framework lenses (#208), which remain parked.
- Operations or implementation-plan feedback; this route handles roadmap-artifact feedback only.
- Changes to `resolve_impact_closure`'s algorithm or verdicts, or new `FeedbackState`, `RelationKind`, `ImpactClosureVerdict`, or `ImpactRouteClass` members.
- Relaxing `STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK`, `_validate_unchanged_relations`, or `_require_relation_inventory` on existing routes.
- Automatic acceptance, including treating `-y` as acceptance.
- Free-form or textual patch languages, whole-artifact re-emission on failure, evidence-store update/delete/overwrite operations, roll-forward recovery, a second writer lock, or concurrent publication.
- Changes to `--from-stage`, `--revise-feedback`, `--reopen-feedback`, `--escalate-feedback`, `--analyze-escalation`, `--rewrite-structural`, or `--enroll-baselines`.
- Broad roadmap-subsystem cleanup or consolidation of existing revision routes; reorganization is limited to the two named widenings and the new module pair.

## Risks

- **Capability inflation:** This is a large-capability shape that can expand into rebuilding shipped infrastructure. The budget remains two signature widenings and one module pair while reusing closure, evidence storage, and N-member journalled publication.
- **Model omission:** The model may omit a semantically affected row. Deterministic closure runs first, omissions are surfaced, and the manifest may extend but never shrink the closure.
- **Incomplete generation membership:** A multi-artifact write could expose an invalid intermediate state if its member list omits an artifact, baseline, or singleton seed-state member. The existing journal-first protocol records every member's `old_bytes` and `new_bytes`; explicit coverage verifies the new membership construction.
- **Per-artifact gating:** Independently valid artifacts may be invalid together, especially under `check_duplicate_row_ids`. The route widens `check_full_roadmap_gates` and checks one combined roadmap instead of invoking it N times.
- **Snapshot staleness:** Analysis and acceptance may be separated by days. The manifest binds to an exact snapshot and uses `recheck_roadmap_impact_snapshot`; stale input refuses without rebasing and leaves all canonical bytes untouched.
- **Acceptance bypass:** Existing `-y` behavior could be mistaken for authorization. The new route follows `--confirm-feedback-reopen`'s rule that `-y` is not confirmation and tests that boundary.

## Testing

Tests are hermetic and fixture-driven with stubbed invokers; `tests/conftest.py:63` continues to prevent real backend spawning. New coverage follows the existing one-test-file-per-module convention, while `tests/cli/test_cli_reference.py` drift-checks regenerated `docs/cli/roadmap.md`.

- Reproduce the Integration shape with one conversational message that changes declared relations across multiple artifacts, then verify one generation publishes every affected artifact.
- Verify analysis alone writes a manifest and run log but leaves every artifact, baseline, and seed-state file byte-identical.
- Byte-compare all four artifacts, every baseline, and `seed-state.json` after rejection, stale snapshot, schema-invalid manifest, unknown row id, `unmappable-relation`, combined stage-gate failure, and `-y` without explicit acceptance.
- Mutate manifest replies to verify omitted closure members are surfaced, outside-closure impacts are flagged as extensions requiring acceptance, shrinkage is refused, and deterministic closure is computed independently of the model.
- Inject failure partway through `_replace_generation_members`, retain a recoverable journal, and verify `recover_roadmap_publication` restores every member's `old_bytes`, including stages not reached by the failure.
- Assert the transaction contains exactly one artifact member and one baseline member per affected stage and exactly one seed-state member regardless of artifact count.
- Construct two artifacts that are individually valid but jointly violate `check_duplicate_row_ids`, and verify combined gating refuses them.
- Pin `FeedbackState` at exactly three members and `RelationKind` at exactly thirteen members.
- Keep regression coverage for `--revise-feedback`'s positional two-operation contract, the stage route's one-material-operation limit, structural rewrite's single-artifact publication, and `--enroll-baselines`' unenrolled-prefix rule under the widened signatures.
- Keep `tests/test_roadmap_revision_publish.py` passing while leaving `_publish_generation` and rollback-only recovery unchanged.

## Acceptance criteria

- One conversational feedback message produces one validated revision across every affected roadmap artifact, published as a single recoverable generation or not at all.
- Reviewer prose never has write authority: no canonical artifact, baseline, or seed record changes before explicit acceptance, and `-y` does not count as acceptance.
- Code computes the deterministic declared-relation closure independently of the model; a manifest is validated against it, may extend it only through an explicitly accepted flag, and may never shrink it.
- `check_full_roadmap_gates` evaluates the combined candidate against all four stage registries, and refuses a jointly invalid pair of individually valid artifacts.
- Rejected, stale, ambiguous, schema-invalid, and gate-failing proposals leave all four artifacts, every baseline, and `seed-state.json` byte-for-byte unchanged.
- Each transaction contains one artifact member and one baseline member per affected stage and exactly one seed-state member; interrupted publication recovers every member to its recorded `old_bytes`.
- `resolve_impact_closure`, `_publish_generation`, and the evidence store's publication and read primitives remain unchanged.
- `FeedbackState` remains at 3 members, `RelationKind` at 13 members, and `ImpactClosureVerdict` at 4 members.
- `--from-stage`, `--revise-feedback`, `--reopen-feedback`, `--escalate-feedback`, `--analyze-escalation`, `--rewrite-structural`, and `--enroll-baselines` retain their current selection, authority, and publication contracts with existing tests passing.
- An analysis classified as `cross-artifact` through `CROSS_ARTIFACT_WORKFLOW` identifies a route an operator can run.
- `ROADMAP_FORMAT.md` documents the route's authority boundary, and `BACKLOG.md` #325 is updated when the work ships.

## Deferred

- Reconcile or retire `roadmap_revision_publish.py:301 preinvalidate_roadmap_seeds`, which has zero production call sites and only appears in `tests/test_roadmap_revision_publish.py`; file the mismatch with `ROADMAP_FORMAT.md:862-864` in `BUG_BACKLOG.md` rather than fixing it here. Current production routes invalidate at publication through `on_seed_state_published` at `roadmap_revision_publish.py:566-567` and `:696-697`, wired by `roadmap_revision_run.py:585` and `roadmap_structural_revision_run.py:340`.
- Register `--revise-feedback` with `_TrackExclusiveOption`; repeated-option last-wins behavior is adjacent and separately filable.
- #242's retention redesign; this transaction may inform it later but neither delivers nor unblocks it.
- A reviewer-facing transport for conversational feedback, pending separate product authorization.
- Support for operations or implementation-plan feedback.

## Input

This plan consumes several shipped contracts rather than replacing them:

- `roadmap_impact_relations.py:65 resolve_impact_closure` computes a fixed point over all four roadmap artifacts. `_relation_touches_reached` (`:212`) matches owner keys or endpoint `row_id`, `_unambiguous_endpoint` (`:230`) resolves global row ids, and ambiguity fails closed as `unmappable-relation` under `roadmap_impact_relations.py:20 ImpactClosureVerdict`.
- `roadmap_impact_analysis.py:69 CROSS_ARTIFACT_WORKFLOW = "roadmap-cross-artifact-revision-transaction"` is assigned by `_classify_route` (`:785`) when closure spans multiple artifacts, then stored in the immutable v2 analysis record and logged by `roadmap_impact_run.py:114`, `run_log.py:727`, and `:2850`. It currently has no consumer.
- `roadmap_revision_publish.py:847 _publish_generation` accepts an ordered `PendingGeneration` with arbitrary `GenerationMember`s and records `old_bytes` and `new_bytes` before replacement. `roadmap_revision_publish.py:315 recover_roadmap_publication` provides rollback-only recovery, and `enroll_stage_baselines` already publishes a multi-stage generation through this protocol.
- `roadmap_impact_snapshot.py:176 capture_roadmap_impact_snapshot` requires the whole roadmap to satisfy every stage gate, and `roadmap_impact_snapshot.py:180 recheck_roadmap_impact_snapshot` revalidates the bound snapshot before acceptance proceeds.
- `roadmap_evidence_store.py:38 EvidenceNamespace` currently contains `ESCALATIONS` and `IMPACT_ANALYSES`. Finals are immutable, content-addressed 64-hex records published through exclusive `os.link` after `fsync` and darwin `F_FULLFSYNC`, with deterministic exact-name reads and `created`, `existing`, `invalid-input`, or `write-failed` outcomes. The store exposes no update, delete, or overwrite operation.
- `roadmap_artifacts.py:247 FeedbackState`, `roadmap_relations.py:28 RelationKind`, and `roadmap_impact_relations.py:20 ImpactClosureVerdict` are frozen inputs to this work. Their existing membership and semantics cannot be widened by the new route.
