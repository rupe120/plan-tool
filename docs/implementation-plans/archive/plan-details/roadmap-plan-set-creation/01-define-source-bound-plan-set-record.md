> **Withdrawn 2026-10-16** — Owner correction 2026-10-16: improve existing roadmap mapping to seeds to plans; the separate opt-in plan-set layer exceeds the requested scope. Replacement effort: roadmap-plan-derivation, BACKLOG #496.
> Preserved here for history; do not edit.

# Step 1 — Define the source-bound plan-set record and structural checks

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Create `plan_tool/roadmap_plan_set_artifacts.py` to define, parse, render and structurally validate the derived plan-set record. Keep derived member identities separate from accepted roadmap-row identities, with explicit source attribution and responsibility assignments. Document the contract in `ROADMAP_PLAN_SET_FORMAT.md` and cover it in `tests/test_roadmap_plan_set_artifacts.py`. On green, callers can round-trip an inspectable record and detect invalid references, dependencies and destinations without judging semantic completeness.

## Table of Contents

- [Summary](#summary) — Deliverables and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Why the set needs its own record.
- [Input](#input) — Existing source contracts and authority.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three new files.
- [Implementation](#implementation) — Record contents, checks and ownership boundaries.
- [Tests](#tests) — Cases that establish the contract.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Relevant source contracts.
- [Applicable guardrails](#applicable-guardrails) — Limits on this step.
- [Deferred](#deferred) — Work owned by later steps.

## Why

`plan_tool/roadmap_artifacts.py:PlanRow` describes accepted roadmap rows, while `plan_tool/roadmap_seed_state.py` tracks their seed lifecycle. Neither represents an implementation set in which one accepted row produces several slices or several rows share one producer. The new record gives that breakdown an inspectable home without changing accepted roadmap membership or treating generated plans as proof that every accepted obligation is covered.

## Input

- **Pinned source:** `plan_tool/roadmap_versions.py:ResolvedRoadmapVersion` pairs a `StoredRoadmapVersion` with the selected brief and artifact bytes. Its record carries `roadmap_slug`, `version_id`, `brief_digest` and `artifact_members`.
- **Accepted authority:** `plan_tool/roadmap_versions.py:load_accepted_version` selects accepted content; `load_resolved_stored_version` reads and verifies an explicit stored version. An arbitrary stored candidate is not evidence of accepted selection.
- **Source rows:** `plan_tool/roadmap_artifacts.py:PlansArtifact`, `PlanRow`, `OrderingEntry` and `AssumptionRow` describe accepted attribution, ordering and assumptions. Preserve their interpretation.
- **Validation boundary:** The caller supplies the pinned source inventory and resolved destination roots. This module checks relationships against those inputs; it does not select a head, interpret repository implementation quality or inspect providers.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_plan_set_artifacts.py` — Record types, text parser, loader, renderer, path helpers and structural checks.
  - `tests/test_roadmap_plan_set_artifacts.py` — Contract, relationship, path and documentation-example tests.
  - `ROADMAP_PLAN_SET_FORMAT.md` — Persisted schema, ownership boundaries, check definitions and a complete example.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic: validate a derived set against one pinned source.** Keep this module below the authoring orchestrator. It must not import `plan_tool/roadmap.py`, `plan_tool/create.py`, `plan_tool/cli/authoring.py` or review orchestration. Recommend small immutable records and explicit validation inputs rather than a general artifact framework.

- **Define the complete record contract here.** Settle persisted field names and supported format version in this step, then document the landed names. The record must represent:
  - Set identity and the pinned roadmap slug/version, with source digests sufficient to compare the selected bundle.
  - Derived member identity, title and bounded authoring intent.
  - Attribution from each member to accepted roadmap rows.
  - Responsibility assignments identifying one producer owner and its consumers, including integration and acceptance responsibilities expressed as content.
  - Member dependencies and explicit unresolved prerequisites.
  - Intended seed/plan destinations, authoring progress and actual authored destinations when available.

- **Separate identity namespaces.** Member identities must be unique within the set and must not double as accepted-row membership. A member may cite several source rows, and several members may cite the same row. Responsibility and prerequisite references must identify their own record kind so equal strings across kinds do not create ambiguous lookup.

- **Keep unknown prerequisites valid.** Represent the unknown evidence and affected members without requiring a fabricated provider, owner or mechanism. An unresolved prerequisite is inspectable authoring content, not an invalid set or an application-readiness verdict.

- **Ship parsing and rendering together.** Provide text-based parsing, a path-based loader and rendering in `plan_tool/roadmap_plan_set_artifacts.py`; choose clear public names and use them consistently in the format document. Parsing must reject malformed field types and unsupported versions. Preserve ordered sequences and duplicate entries so relationship checks can report them. Loading errors must name the input path.

- **Separate shape errors from relationship violations.** Recommend a small frozen violation type carrying `kind` and `message`, without severity, approval or semantic-blocking fields. Structural validation must return violations rather than raise for a well-shaped record with bad relationships. Report every independent offender in stable order, with duplicate identities reported once per duplicated identity.

- **Check only declared structural relationships.**
  - Member, responsibility and prerequisite identities must be unique in their respective namespaces.
  - Source references must exist in the supplied pinned inventory, and recorded source identity must match that inventory.
  - Dependencies, owners, consumers and prerequisite member references must name existing members.
  - Each declared shared responsibility must have one owner; consumers must not create competing ownership declarations.
  - Dependencies must reject self-links and cycles. A valid serial order must place dependencies before consumers; preserve source order as the tie-breaker for unrelated members.
  - Require every accepted plan row to appear in at least one member attribution and every member to cite at least one accepted plan row. Report omitted rows and unattributed members by identifier. Do not infer missing responsibilities or semantic coverage from prose; those remain content judgments.

- **Make messages useful outside a report.** Each violation must name the set/member or expected identifier and every relevant reference target. Use identifiers and field names rather than line numbers. Missing-record messages must name the expected identifier because no offending record exists.

- **Validate destinations against supplied roots.** Path helpers must take already-resolved directories rather than hardcode the default plans location. Reject absolute paths, traversal, unsafe path components and symlink escapes. Detect equal resolved targets and file/directory ancestor conflicts across declared outputs, including conflicts with the set record or pinned source files. Existing-file ownership and overwrite decisions remain with step 3.

- **Keep set storage separate from accepted state.** Choose and document a dedicated nested set location beneath the caller-resolved plans directory. It must not appear as a top-level discoverable plan or reuse accepted-row seed-state paths. Path computation must not create directories or write files.

- **Reuse existing owners without changing them.** `plan_tool/roadmap_versions.py` owns source verification. `plan_tool/roadmap_artifacts.py:resolve_draft_seed_path` demonstrates resolved-path containment, while `plan_tool/roadmap_gates.py:check_plan_ordering_totality` demonstrates accepted-row relationship checks. The new checks concern derived members; they must not change those accepted-row rules or introduce a shared-rule refactor.

- **Document the boundary as part of the format.** `ROADMAP_PLAN_SET_FORMAT.md` must name the enforcing symbols, distinguish intended from actual destinations, describe progress as authoring state, and explain that structural validity does not certify coverage or granularity. Include a complete example with shared ownership, source attribution and an unresolved prerequisite. Cite later orchestration modules by path only until their symbols exist.

## Tests

### Tests for this step

Add these cases in `tests/test_roadmap_plan_set_artifacts.py`. Every case must be green before the step finishes; run the focused suite and the repository suite. Verify tightened checks by temporarily disabling the check and confirming its named test fails.

- `test_every_accepted_plan_row_has_a_member_attribution` — An omitted accepted row produces a structural violation naming that row.
- `test_every_member_has_accepted_row_attribution` — An unattributed member is rejected, while one member may cite several rows and several members may cite one row.
- `test_attribution_presence_does_not_certify_semantic_coverage` — Valid references pass without a prose-quality classifier or coverage verdict.
- `test_record_round_trip_preserves_source_members_and_progress` — Parsing rendered records preserves source bindings, ordered members, responsibilities, prerequisites and authored destinations.
- `test_parser_rejects_malformed_types_and_unsupported_versions` — Shape errors fail explicitly rather than coercing incompatible values.
- `test_loader_errors_name_the_record_path` — File and parse failures identify the input path.
- `test_parser_preserves_duplicate_records_for_structural_validation` — Parsing retains duplicates and source order instead of silently collapsing them.
- `test_duplicate_identity_is_reported_once_per_namespace` — Duplicate declarations produce one violation per identity without conflating typed namespaces.
- `test_one_source_row_can_have_several_members` — Several derived slices may cite the same accepted row.
- `test_one_member_can_cite_several_source_rows` — Shared implementation work retains all supplied source attributions.
- `test_source_identity_and_references_match_the_pinned_inventory` — Mismatched source bindings and unknown source rows produce identifier-bearing violations.
- `test_every_unknown_member_reference_is_reported` — Dependencies, responsibility assignments and prerequisite references report every missing member.
- `test_shared_responsibility_has_one_owner_and_valid_consumers` — A valid owner/consumer assignment passes; conflicting ownership fails.
- `test_unresolved_prerequisite_is_valid_inspectable_content` — Unknown evidence remains valid without fabricated resolution.
- `test_dependencies_reject_self_links_and_cycles` — Invalid dependency graphs produce structural violations.
- `test_serial_order_places_dependencies_first_with_stable_ties` — Valid graphs produce a repeatable order while preserving declaration order among unrelated members.
- `test_validation_does_not_infer_semantic_coverage_or_plan_count` — Structurally valid sets pass without prose coverage judgments or target counts.
- `test_destinations_reject_absolute_traversal_and_symlink_escape` — Unsafe destinations fail against caller-supplied roots.
- `test_conflicting_targets_include_aliases_and_ancestor_conflicts` — Resolved aliases, nested file targets and protected-source collisions fail.
- `test_path_helpers_use_supplied_roots_without_writing` — Alternate plans locations work and path computation creates nothing.
- `test_set_record_is_not_a_top_level_plan_or_seed_state_file` — The storage convention keeps derived state outside existing discovery and accepted seed-state ownership.
- `test_violation_messages_name_records_and_missing_targets` — Messages remain actionable without surrounding report text.
- `test_format_example_parses` — The complete example in `ROADMAP_PLAN_SET_FORMAT.md` satisfies the real parser.
- `test_format_example_round_trips` — Rendering and reparsing the documented example preserves its record.
- `test_format_example_passes_structural_checks` — The documented example passes against its explicit source inventory and destination roots.
- `test_artifact_module_has_no_authoring_or_cli_imports` — Import-time and source-level checks catch prohibited imports, including lazy imports.

## Acceptance criteria

- All three declared files exist, with no existing production module changed.
- A valid record survives parse/render/parse equality, including unfinished authoring progress.
- Structural checks detect invalid identities, references, source bindings, dependency graphs and output targets.
- Valid many-to-many source attribution, shared ownership and unresolved prerequisites pass.
- Destination checks honor caller-supplied roots and reject resolved escapes and collisions.
- Parsing, rendering, validation and path computation leave accepted roadmap files and seed state unchanged.
- `ROADMAP_PLAN_SET_FORMAT.md` names the landed enforcing symbols, and its complete example parses, round-trips and passes validation.
- `uv run pytest tests/test_roadmap_plan_set_artifacts.py -q` and `uv run pytest tests/ -q -n auto` pass.

## References

- [BACKLOG.md](../../../BACKLOG.md) — Read entry #496 for the originating outcome and scope contract.
- [ROADMAP_FORMAT.md](../../../ROADMAP_FORMAT.md) — Read accepted-version authority, plan-row relationships and seed provenance.
- [plan_tool/roadmap_versions.py](../../../plan_tool/roadmap_versions.py) — Use the existing immutable version identity and verified source inventory.
- [plan_tool/roadmap_artifacts.py](../../../plan_tool/roadmap_artifacts.py) — Orient around accepted row types, parse/render pairs and destination containment.
- [plan_tool/roadmap_seed_state.py](../../../plan_tool/roadmap_seed_state.py) — Preserve separate ownership of accepted-row seed lifecycle.
- [MISSION.md](../../../MISSION.md) — Keep deterministic checks limited to observable structure.

## Applicable guardrails

- **The plan’s “## Scope guardrails,” structural enforcement:** Checks in `plan_tool/roadmap_plan_set_artifacts.py` must evaluate recorded state and relationships; prose quality remains outside their decision surface.
- **The plan’s “## Architecture,” accepted-source ownership:** The new record must refer to accepted content without becoming another source selector or changing accepted-row membership.
- **The plan’s “## Out of scope,” existing behavior:** This step must remain additive within its declared files and introduce no command, execution-policy or approval changes.
- **The plan’s “## Deferred,” unknown evidence:** Prerequisite records must preserve uncertainty without supplying an invented implementation.
- **The plan’s “## Scope guardrails,” source contract:** `ROADMAP_PLAN_SET_FORMAT.md` must describe this derived artifact without replacing or weakening the source scope contract.

## Deferred

- Whole-set derivation and source selection — Step 2 consumes this contract and owns model prompting and repository grounding.
- Durable writes, source rechecks and safe retry — Step 3 owns persistence, existing-output ownership decisions and preservation of completed plans and seeds.
- CLI dispatch and existing-create compatibility — Step 4 owns the opt-in route and its callers.
- Live decomposition-quality evidence — Step 5 owns the isolated comparison; this suite establishes structural behavior only.
- Operator recovery documentation and backlog reconciliation — Step 6 documents the landed workflow and updates shipment status.
- Shared accepted-row validation or lifecycle changes — `plan_tool/roadmap_gates.py:check_plan_ordering_totality`, `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds` and `plan_tool/roadmap_seed_state.py:validate_seed_state` keep their current authority; changing that authority requires separately scoped work.
