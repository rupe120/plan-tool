> **Superseded 2026-08-31 — do not execute.** This direct model-proposal
> transaction is replaced by `BACKLOG.md` #328's immutable candidate-version and
> accepted-head direction. Preserved with its audit evidence for provenance.
> **Identifier correction 2026-09-01:** the `#325` citations below are
> historical branch-local labels for this retired proposal. They do not refer to
> the current `BACKLOG.md` #325 entry.

---
title: Roadmap Conversational Feedback
intent: 'One conversational reviewer feedback message produces one auditable, validated,
  all-or-nothing revision across every roadmap artifact it actually affects. Reviewer
  prose is immutable input and never write authority: a model may *propose* an impact
  manifest, deterministic code validates its identities and declared-relation closure,
  an explicit acceptance is required before any candidate is built, and a rejected,
  stale, ambiguous, or invalid proposal leaves every canonical artifact, baseline,
  and seed record byte-for-byte untouched.'
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-conversational-feedback.md
steps:
- id: 1
  title: Gate several candidate substitutions as one roadmap while keeping existing
    single-candidate structural proofs unchanged
  intent: Ensure cross-artifact revisions must satisfy all four stage registries together.
  files:
  - plan_tool/roadmap_impact_snapshot.py
  - plan_tool/roadmap_structural_revision_proof.py
  - tests/test_roadmap_impact_snapshot.py
  - tests/test_roadmap_structural_revision_proof.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Publish one artifact and baseline per affected stage plus one seed-state
    member, preserving writer-lock truncation, journal clearing, member deletion and
    replacement, and rollback-only recovery
  intent: Make an accepted cross-artifact revision visible as one recoverable generation
    or not at all.
  files:
  - plan_tool/roadmap_revision_publish.py
  - tests/test_roadmap_revision_publish.py
  complexity: high
  change_type: feature
- id: 3
  title: Add an IMPACT_MANIFESTS evidence namespace while preserving hard-link no-overwrite
    publication and private-temporary cleanup
  intent: Keep revision manifests immutable and prevent them from polluting impact-analysis
    scans.
  files:
  - plan_tool/roadmap_evidence_store.py
  - tests/test_roadmap_evidence_store.py
  complexity: low
  change_type: feature
- id: 4
  title: Define one immutable, complete impact manifest, reconcile every extension
    to a stable declared-relation closure, and build only its typed candidates after
    acceptance
  intent: Turn model interpretation into inspectable, complete evidence that cannot
    become canonical roadmap state by itself or authorize an unlisted write.
  creates:
  - plan_tool/roadmap_conversational_revision.py
  - tests/test_roadmap_conversational_revision.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the multi-substitution shape used to validate a constructed combined
      candidate.
- id: 5
  title: Record a closed redacted manifest lifecycle and the selected feedback transition
    while preserving run-log lock truncation, atomic snapshot replacement, temporary
    cleanup, and owner-guarded snapshot unlinking
  intent: Make proposal, refusal, staleness, validation failure, interruption, application,
    and the one successful feedback transition auditable without retaining reviewer or
    model text.
  files:
  - plan_tool/run_log.py
  - plan_tool/data_contract.py
  - tests/test_run_log.py
  - tests/test_data_contract.py
  - DATA_CONTRACT.md
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  depends_on_notes:
    4: Settles the manifest identities and lifecycle boundary that the redacted events
      describe.
- id: 6
  title: Run proposal and exact-manifest acceptance as one guarded flow, rechecking its
    snapshot under its complete journal, and replacing only its sealed members afterward
  intent: Let one conversational feedback message produce a reviewed all-or-nothing
    roadmap revision without giving model prose authority to reinterpret, expand, or
    reapply it.
  files:
  - TESTING.md
  creates:
  - plan_tool/roadmap_conversational_revision_run.py
  - plan_tool/prompts/roadmap-conversational-feedback-revision.md
  - tests/test_roadmap_conversational_revision_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  - 4
  - 5
  depends_on_notes:
    1: Supplies combined full-roadmap validation.
    2: Supplies the recoverable multi-artifact publisher.
    3: Supplies isolated immutable manifest storage.
    4: Supplies manifest validation, closure reconciliation, and candidate construction.
    5: Supplies the redacted lifecycle event contract.
- id: 7
  title: Add exclusive --revise-cross-artifact and --accept-impact-manifest options
    that bind one analysis, reviewed manifest final, and acceptance, keep -y
    non-authoritative, and preserve the existing review-page atomic overwrite
  intent: Give one eligible cross-artifact impact analysis a runnable proposal command,
    a read-only review of its exact manifest final, and a separate exact-manifest
    acceptance command.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/test_cli_reference.py
  - docs/cli/roadmap.md
  complexity: medium
  change_type: feature
  depends_on:
  - 6
  depends_on_notes:
    6: Provides the guarded runner and terminal outcomes the CLI dispatches and renders.
- id: 8
  title: 'Document the reviewed transaction route, replace every live public-guide
    future-handoff claim without weakening one-artifact routes, close BACKLOG #325,
    and record the unused pre-invalidation helper as a separate bug'
  intent: Leave operators and future authors with one consistent authority, recovery,
    and compatibility description for the shipped route.
  files:
  - ROADMAP_FORMAT.md
  - docs/ARCHITECTURE.md
  - CLAUDE.md
  - CAPABILITIES.md
  - README.md
  - RUNBOOK.md
  - docs/ROADMAP_WALKTHROUGH.md
  - docs/CODEX_CLI_CONTRACT.md
  - integrations/claude/SKILL.md
  - BACKLOG.md
  - BUG_BACKLOG.md
  - tests/test_roadmap_format.py
  complexity: high
  change_type: non-code
  depends_on:
  - 7
  depends_on_notes:
    7: Settles the final option names, help text, and operator-visible outcomes the
      documentation records.
---
# Roadmap Conversational Feedback

## Overview

This plan adds the missing writer route for `BACKLOG.md` #325: one conversational roadmap-feedback message can produce one reviewed, validated revision across every affected roadmap artifact. Reviewer prose remains immutable input; a model proposes an impact manifest, deterministic code validates it against the declared-relation closure, and a human must explicitly accept it before candidate construction or publication. The route reuses `resolve_impact_closure`, the sealed evidence store, and `_publish_generation`, while widening only `check_full_roadmap_gates` and `_publication_members` for a combined multi-artifact transaction. Every rejection, stale snapshot, ambiguity, invalid manifest, or gate failure leaves canonical artifacts, baselines, and seed state byte-for-byte unchanged.

## Problem statement

The Integration `project-workspace-membership-proof` review (2026-08-31) exposed a case the current bounded routes cannot express: one natural reframing moved ownership between components, retargeted a business rule, reordered a plan row, touched three artifacts, and necessarily changed declared relations.

Three existing authorities jointly force the reviewer to decompose that single thought by hand. `roadmap_revision.py:515 STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK = 1` and `:516 STAGE_SPLIT_FEEDBACK_ACTION = "split the feedback into smaller requests"` permit one material operation per feedback item. `roadmap_relations.py:183 same_declared_row_relations`, `roadmap_revision.py:1653 _validate_unchanged_relations`, `roadmap_revision_patch.py:521`, and `roadmap_structural_revision_proof.py:346 _require_relation_inventory` prevent existing row-edit and structural routes from changing the declared-relation inventory; no gate in `roadmap_gates.py` owns that restriction. Finally, `roadmap_revision_publish.py:792 _publication_members` accepts a scalar `artifact_path`, so every writer publishes one artifact.

Those restrictions remain correct for their existing routes, but coherent intermediate per-artifact edits cannot satisfy them. The missing capability is a separate, more strongly reviewed route that consumes the already-named `roadmap_impact_analysis.py:69 CROSS_ARTIFACT_WORKFLOW = "roadmap-cross-artifact-revision-transaction"` and performs one all-or-nothing cross-artifact revision.

## Architecture

**Authority phases.** The route is strictly `Reviewer prose → (model) proposed impact manifest → (human) acceptance → (deterministic) candidate, gates, publication`. The model participates only in manifest proposal and never receives write authority. The sealed manifest contains the complete, typed change set: its selected feedback transition, every affected artifact and baseline, and every declared-relation extension after reconciliation. Its final identity binds those semantic fields. Acceptance names that exact final; candidate construction may derive only its listed writes, with no later model interpretation or unlisted write. Manifest analysis and acceptance create no `PendingGeneration`; candidate construction and the transaction publisher remain unreachable until explicit acceptance. As with `roadmap_impact_run.py`, the analysis phase may write evidence, a run log, and a lock file, but no canonical artifact.

**Closure reconciliation.** `resolve_impact_closure` remains unchanged and runs before the model call as the deterministic floor. A proposed impact inside the declared closure is reviewable; an impact outside it is permitted only as a flagged semantic extension requiring explicit acceptance; and every closure member omitted by the model is surfaced. Each proposed extension is itself reconciled through the unchanged deterministic closure until the union is stable before review; manifest validation, candidate construction, gating, and transaction membership use that verified union. The model may extend the closure but never shrink or replace it. The route refuses before invoking the model when closure returns `invalid-target`, `target-not-live-in-selected-artifact`, or `unmappable-relation`.

**Manifest evidence and lifecycle.** The manifest uses `roadmap_evidence_store.py`'s immutable, content-addressed publication rather than a new storage protocol. It has a third `EvidenceNamespace`, `IMPACT_MANIFESTS`, with isolated reads and scans, while the store's write and read primitives remain unchanged. Step 5 defines the manifest lifecycle as a closed state set, including each value's producer, precedence, consumers, and exit path. Every state other than the applied state leaves canonical artifacts, baselines, and seed records untouched, and every state an operator can reach has an exit.

**Combined gating.** `plan_tool/roadmap_impact_snapshot.py` widens `check_full_roadmap_gates` from one `CandidateSubstitution | None` to a set of candidate substitutions. The combined candidate is checked as one roadmap against every stage registry—`DOMAIN_GATES` 9, `CONSTRAINTS_GATES` 12, `COMPONENTS_GATES` 15, and `PLANS_GATES` 13 in `roadmap_gates.py:2475-2520`—rather than checking each artifact independently. This preserves cross-artifact checks such as `check_duplicate_row_ids` (`:601`).

**Atomic publication.** `plan_tool/roadmap_revision_publish.py` widens `_publication_members` to construct one N-artifact `PendingGeneration`: one artifact member and one baseline member per affected stage, plus exactly one seed-state member for the transaction. The selected open feedback row transitions once to the existing `awaiting-review` state with its required proposed response in that same generation. `_publish_generation` remains unchanged and continues to provide journal → replace → verify → clear publication with rollback-only recovery. The runner performs the final snapshot recheck after that complete journal is durable and before the first replacement, admitting only its own exact pending generation; a refusal clears that journal and changes no member. `PendingGeneration.kind` in `roadmap_source_identity.py:113` remains a non-empty free string under `:534`; the new kind is checked at its consumers rather than adding enum machinery.

**Placement and route selection.** `roadmap_revision_publish.py` remains the layer-2 journal owner, using its `:85 _RoadmapStage` Protocol and lazy imports to stay decoupled from `roadmap.py`. A new conversational-analysis module sits at layer 4–5 beside `roadmap_impact_analysis.py`, its guarded runner sits beside `roadmap_impact_run.py`, and its prompt is added under `plan_tool/prompts/`. The exclusive proposal route selects one eligible immutable impact-analysis final, produces and renders a redacted read-only view of its one manifest final, and reports that final's identity. The exclusive acceptance route requires that exact current manifest identity and refuses a selector, analysis, or manifest mismatch. Both use `_TrackExclusiveOption` and reject companion roadmap options, following `--escalate-feedback`, `--analyze-escalation`, and `--rewrite-structural` rather than the last-wins `--revise-feedback` outlier.

**Frozen contracts and compatibility.** `FeedbackState` in `roadmap_artifacts.py:247` remains exactly `open`, `awaiting-review`, and `deferred`; closing still deletes the row under `ROADMAP_FORMAT.md:676`. `RelationKind` in `roadmap_relations.py:28` remains exactly thirteen values with the single `OWNER_TO_ENDPOINT` direction at `:49`, and `ImpactClosureVerdict` in `roadmap_impact_relations.py:20` remains exactly four values. Existing restrictions—including `STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK`, `_validate_unchanged_relations`, and `_require_relation_inventory`—remain intact on every existing route. Documentation updates cover `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, `docs/ARCHITECTURE.md`, and generated `docs/cli/roadmap.md` via `python -m plan_tool.cli_reference --write`.

## Input

This plan consumes several shipped contracts rather than replacing them:

- `roadmap_impact_relations.py:65 resolve_impact_closure` computes a fixed point over all four roadmap artifacts. `_relation_touches_reached` (`:212`) matches owner keys or endpoint `row_id`, `_unambiguous_endpoint` (`:230`) resolves global row ids, and ambiguity fails closed as `unmappable-relation` under `roadmap_impact_relations.py:20 ImpactClosureVerdict`.
- `roadmap_impact_analysis.py:69 CROSS_ARTIFACT_WORKFLOW = "roadmap-cross-artifact-revision-transaction"` is assigned by `_classify_route` (`:785`) when closure spans multiple artifacts, then stored in the immutable v2 analysis record and logged by `roadmap_impact_run.py:114`, `run_log.py:727`, and `:2850`. It currently has no consumer.
- `roadmap_revision_publish.py:847 _publish_generation` accepts an ordered `PendingGeneration` with arbitrary `GenerationMember`s and records `old_bytes` and `new_bytes` before replacement. `roadmap_revision_publish.py:315 recover_roadmap_publication` provides rollback-only recovery, and `enroll_stage_baselines` already publishes a multi-stage generation through this protocol.
- `roadmap_impact_snapshot.py:176 capture_roadmap_impact_snapshot` requires the whole roadmap to satisfy every stage gate, and `roadmap_impact_snapshot.py:180 recheck_roadmap_impact_snapshot` revalidates the bound snapshot before acceptance proceeds.
- `roadmap_evidence_store.py:38 EvidenceNamespace` currently contains `ESCALATIONS` and `IMPACT_ANALYSES`. Finals are immutable, content-addressed 64-hex records published through exclusive `os.link` after `fsync` and darwin `F_FULLFSYNC`, with deterministic exact-name reads and `created`, `existing`, `invalid-input`, or `write-failed` outcomes. The store exposes no update, delete, or overwrite operation.
- `roadmap_artifacts.py:247 FeedbackState`, `roadmap_relations.py:28 RelationKind`, and `roadmap_impact_relations.py:20 ImpactClosureVerdict` are frozen inputs to this work. Their existing membership and semantics cannot be widened by the new route.

## References

- [Structured outputs - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Defines schema-constrained Claude responses for producing a parseable impact manifest.
- [Messages - Claude API Reference](https://platform.claude.com/docs/en/api/http/messages) — Documents the request and response contract for invoking Claude to propose the manifest.
- [Models - Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Covers typed models, strict validation, forbidden extra fields, and JSON parsing for fail-closed manifest handling.
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12) — Specifies the schema vocabulary and validation semantics needed to define the manifest contract.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Documents custom actions and mutually exclusive options for implementing the guarded conversational route flag.
- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Defines os.link, os.replace, and os.fsync behavior relevant to immutable evidence and crash-safe publication.

## Steps

See the `steps:` block in the frontmatter.

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
- **Snapshot staleness:** Analysis and acceptance may be separated by days. The manifest binds to an exact snapshot; the final recheck runs after this transaction's complete journal is durable, admits only that journal, and runs before replacement. A stale input refuses without rebasing, clears the journal, and leaves all canonical bytes untouched.
- **Acceptance bypass:** Existing `-y` behavior could be mistaken for authorization. The new route follows `--confirm-feedback-reopen`'s rule that `-y` is not confirmation and tests that boundary.

## Testing

Tests are hermetic and fixture-driven with stubbed invokers; `tests/conftest.py:63` continues to prevent real backend spawning. New coverage follows the existing one-test-file-per-module convention, while `tests/cli/test_cli_reference.py` drift-checks regenerated `docs/cli/roadmap.md`.

- Reproduce the Integration shape with one conversational message that changes declared relations across multiple artifacts, then verify one generation publishes every affected artifact.
- Verify analysis alone writes a manifest and run log but leaves every artifact, baseline, seed-state file, and feedback row byte-identical; its review view names that manifest final without exposing reviewer or model text.
- Byte-compare all four artifacts, every baseline, `seed-state.json`, and the selected feedback row after rejection, a final snapshot refusal under the complete pending journal, a schema-invalid manifest, an unknown row id, `unmappable-relation`, a combined stage-gate failure, a selector/analysis/manifest mismatch, and `-y` without explicit acceptance.
- Mutate manifest replies to verify omitted closure members are surfaced, outside-closure impacts are flagged as extensions requiring acceptance and reclosed to a stable union, shrinkage is refused, and deterministic closure is computed independently of the model.
- Accept one manifest and prove candidate construction and every generation member, including the selected feedback transition, exactly matches its complete typed record; no later model call or unlisted write is possible.
- Inject failure partway through `_replace_generation_members`, retain a recoverable journal, and verify `recover_roadmap_publication` restores every member's `old_bytes`, including stages not reached by the failure.
- Assert the transaction contains exactly one artifact member and one baseline member per affected stage and exactly one seed-state member regardless of artifact count.
- Assert the successful transaction moves only its selected `open` feedback row to `awaiting-review` with a nonblank proposed response, in the same generation; a second attempt using that feedback is refused.
- Construct two artifacts that are individually valid but jointly violate `check_duplicate_row_ids`, and verify combined gating refuses them.
- Pin `FeedbackState` at exactly three members and `RelationKind` at exactly thirteen members.
- Keep regression coverage for `--revise-feedback`'s positional two-operation contract, the stage route's one-material-operation limit, structural rewrite's single-artifact publication, and `--enroll-baselines`' unenrolled-prefix rule under the widened signatures.
- Keep `tests/test_roadmap_revision_publish.py` passing while leaving `_publish_generation` and rollback-only recovery unchanged.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.
- step 8 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- One conversational feedback message produces one validated revision across every affected roadmap artifact, published as a single recoverable generation or not at all.
- Reviewer prose never has write authority: no canonical artifact, baseline, seed record, or feedback row changes before explicit acceptance, and `-y` does not count as acceptance.
- One immutable manifest final binds the complete typed change set and its semantic fields. Acceptance of that exact current final can construct and publish only its listed candidate and feedback-transition writes; no later model interpretation is used.
- Code computes the deterministic declared-relation closure independently of the model; a manifest is validated against it, may extend it only through an explicitly accepted flag whose declared-relation closure is rechecked to a stable union, and may never shrink it.
- `check_full_roadmap_gates` evaluates the combined candidate against all four stage registries, and refuses a jointly invalid pair of individually valid artifacts.
- Rejected, stale, ambiguous, schema-invalid, mismatched-identity, and gate-failing proposals leave all four artifacts, every baseline, `seed-state.json`, and feedback rows byte-for-byte unchanged. A stale final recheck occurs under only its own complete pending generation and clears that journal before refusal.
- Each transaction contains one artifact member and one baseline member per affected stage, exactly one seed-state member, and its one selected feedback transition; interrupted publication recovers every member to its recorded `old_bytes`.
- `resolve_impact_closure`, `_publish_generation`, and the evidence store's publication and read primitives remain unchanged.
- `FeedbackState` remains at 3 members, `RelationKind` at 13 members, and `ImpactClosureVerdict` at 4 members.
- `--from-stage`, `--revise-feedback`, `--reopen-feedback`, `--escalate-feedback`, `--analyze-escalation`, `--rewrite-structural`, and `--enroll-baselines` retain their current selection, authority, and publication contracts with existing tests passing.
- An analysis classified as `cross-artifact` through `CROSS_ARTIFACT_WORKFLOW` identifies a proposal route that renders its exact redacted manifest final, and only that current final can be accepted.
- `ROADMAP_FORMAT.md` documents the route's authority boundary, and `BACKLOG.md` #325 is updated when the work ships.

## Deferred

- Reconcile or retire `roadmap_revision_publish.py:301 preinvalidate_roadmap_seeds`, which has zero production call sites and only appears in `tests/test_roadmap_revision_publish.py`; file the mismatch with `ROADMAP_FORMAT.md:862-864` in `BUG_BACKLOG.md` rather than fixing it here. Current production routes invalidate at publication through `on_seed_state_published` at `roadmap_revision_publish.py:566-567` and `:696-697`, wired by `roadmap_revision_run.py:585` and `roadmap_structural_revision_run.py:340`.
- Register `--revise-feedback` with `_TrackExclusiveOption`; repeated-option last-wins behavior is adjacent and separately filable.
- #242's retention redesign; this transaction may inform it later but neither delivers nor unblocks it.
- A reviewer-facing transport for conversational feedback, pending separate product authorization.
- Support for operations or implementation-plan feedback.
