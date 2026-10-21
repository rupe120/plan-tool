> **Withdrawn 2026-10-16** — Owner correction 2026-10-16: improve existing roadmap mapping to seeds to plans; the separate opt-in plan-set layer exceeds the requested scope. Replacement effort: roadmap-plan-derivation, BACKLOG #496.
> Preserved here for history; do not edit.

# Step 4 — Expose opt-in plan-set creation through authoring

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Add an explicit plan-set source option to `plan_tool/cli/authoring.py` and connect it to step 3’s serial authoring orchestrator. Keep the CLI responsible for argument validation, configuration delivery and result presentation; retain set persistence and recovery in `plan_tool/roadmap_plan_set.py`. Preserve ordinary single-plan creation and accepted-row seed authoring. Update the parser tests, route tests, capability catalog and generated create reference so one invocation can derive and author a set with inspectable results.

## Table of Contents

- [Summary](#summary) — Deliverables and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — The missing authoring entry point.
- [Input](#input) — Upstream outcomes and existing command contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Changes within the declared footprint.
- [Implementation](#implementation) — Opt-in dispatch, compatibility and reporting.
- [Tests](#tests) — Routing, preservation and integration cases.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Relevant source and documentation owners.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on this route.
- [Deferred](#deferred) — Separate work and later-step ownership.

## Why

`plan_tool/cli/authoring.py:register` offers inline input, file input and placeholder reprocessing as mutually exclusive create sources. `plan_tool/cli/authoring.py:cmd_create` handles one plan, including file-backed split outcomes, while `plan_tool/roadmap.py:materialize_plan_seed` handles one accepted roadmap row. Neither entry point requests a complete derived set. An explicit source option makes step 3’s orchestration available without changing how existing input selects single-plan behavior.

## Input

- **Step 3’s outcome:** Consume its source-bound serial authoring entry point, saved-set recovery and result contract. Read the landed names and signatures in `plan_tool/roadmap_plan_set.py`; those names take precedence over suggestions in detail prose.
- **Steps 1–2’s contracts:** Use their accepted-source selection and validated set record through the orchestrator. The CLI must not parse another set schema or select a second source snapshot.
- **Existing source selection:** `plan_tool/cli/authoring.py:register` owns `p_create_source`; `cmd_create` performs file-backed preparation before slug suggestion and individual-plan authoring.
- **Configuration:** `plan_tool/cli/roadmap_cmd.py:_resolve_roadmap_execution_paths` demonstrates existing roadmap-directory resolution. `plan_tool/create.py:create_plan` owns individual authoring and manifest registration.
- **Evidence limits:** Hermetic routing tests establish configuration delivery and preservation. They do not establish semantic completeness or appropriate plan granularity.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py` — Register the opt-in source, validate its arguments, dispatch to the set orchestrator and present outcomes.
  - `tests/cli/test_authoring_cmds.py` — Add route, configuration, reporting and compatibility tests.
  - `tests/cli/test_cli_parser.py` — Add source-option defaults and exclusion tests.
  - `CAPABILITIES.md` — Describe the route under the existing plan-authoring capability.
  - `docs/cli/create.md` — Regenerate the create reference from parser declarations.
  - `plan_tool/roadmap_plan_set.py` — Add only bounded configuration or result integration needed by the CLI.
  - `tests/test_roadmap_plan_set.py` — Cover any added integration and one composed authoring case.

## Implementation

- **Foundational logic: select whole-set authoring only through an explicit create source.** Add `--from-roadmap ROADMAP_SLUG` to `plan_tool/cli/authoring.py:register` inside `p_create_source`. Its absence must preserve existing dispatch; passing an ordinary file through `--from-existing` must not imply set creation.

- **Define the positional argument for this route.** Require `create SET_SLUG --from-roadmap ROADMAP_SLUG`, with the positional slug naming the derived set rather than an individual member. Missing set identity must produce an input refusal before backend calls or writes; do not invoke single-plan slug suggestion for it. Member identities remain owned by the saved breakdown.

- **Dispatch before single-plan preparation.** In `plan_tool/cli/authoring.py:cmd_create`, select the new branch before file reading, `resolve_create_slug`, individual branch-collision handling and the single-plan success tail. Recommend a small handler helper that validates arguments, resolves configuration, calls the orchestrator once and renders its result. Read the new namespace attribute with an absent-value default so existing hand-built namespaces retain their behavior.

- **Keep configuration ownership explicit.** Resolve the repository through `plan_tool/cli/context.py:_resolve_cmd_repo_root` and retain the existing repository-confirmation behavior where applicable. Use existing plans-directory resolution for the source roadmap, including supported overrides; keep source lookup distinct from `--output-dir`, which controls authored destinations. Pass the selected repository, output location and manifest to step 3’s entry point without re-deriving its paths inside the handler.

- **Classify inherited options before enabling the route.** Carry supported authoring controls into the existing per-member create boundary, including iteration settings and native checkpoint behavior. Options that cannot apply safely must produce a clear input refusal when explicitly requested; they must not be silently ignored. In particular, `--no-resume` must not replace a saved set, regenerate completed members or bypass step 3’s ownership checks. Document whether it controls only unfinished members’ native create checkpoints or is rejected for this route.

- **Reuse set recovery unchanged.** One invocation must derive and author through step 3’s entry point; an interrupted invocation must re-enter that same saved-set contract. Do not duplicate accepted-version reads, dependency ordering, collision checks, progress writes or retry loops in `plan_tool/cli/authoring.py`. Add a narrow adapter in `plan_tool/roadmap_plan_set.py` only when the landed entry point needs configuration or presentation data.

- **Report actual results.** Present the saved set-record path, pinned source version, authored destinations and unfinished members or recovery reason. Preserve unresolved prerequisites as inspectable content rather than treating their presence as an authoring failure. Do not report intended destinations as completed plans or describe the result as completeness certification.

- **Preserve exit and follow-up behavior.** Return zero when requested authoring completes, including completion with explicit prerequisites. Use the existing create distinction between input refusals and hard authoring errors for failure-to-complete outcomes. Print follow-up commands for actual authored members without automatically running detail, completeness audit or execution; retain the existing fresh bare-audit guidance.

- **Leave parallel routes unchanged.** `plan_tool/cli/authoring.py:_cmd_create_reprocess`, ordinary `cmd_create` branches and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` remain separate consumers. Reuse `plan_tool/create.py:create_plan` through step 3; do not route members recursively through `cmd_create` or apply its source-archival tail to set seeds.

- **Document the registered surface.** Update `CAPABILITIES.md:Plan authoring` to identify the opt-in route and `plan_tool/roadmap_plan_set.py` without adding a new capability vocabulary. Generate `docs/cli/create.md` through `plan_tool/cli_reference.py:render_reference`; do not hand-maintain its flag table. Keep lifecycle procedures with step 6.

## Tests

### Tests for this step

Add or extend the following cases. Every case must be green before this step finishes. Run the focused suites, existing create regressions, capability and CLI-reference checks, then the full suite. Keep backend calls stubbed at the production seams.

- `tests/cli/test_cli_parser.py:test_create_roadmap_source_is_explicit_and_defaults_to_absent` — Existing create invocations retain their defaults, including iteration behavior.
- `tests/cli/test_cli_parser.py:test_create_roadmap_source_excludes_other_create_sources` — Parameterized combinations with inline input, file input and reprocessing fail argument parsing.
- `tests/cli/test_authoring_cmds.py:test_plan_set_requires_explicit_set_slug_before_backend_or_writes` — Missing set identity refuses without slug suggestion or side effects.
- `tests/cli/test_authoring_cmds.py:test_plan_set_dispatches_once_without_single_plan_preparation` — The explicit source reaches the set orchestrator once and skips individual preparation and success handling.
- `tests/cli/test_authoring_cmds.py:test_plan_set_keeps_source_lookup_separate_from_output_override` — Repository and plans-directory configuration select the source independently of member output destinations.
- `tests/cli/test_authoring_cmds.py:test_plan_set_forwards_supported_member_authoring_controls` — Supported iteration, manifest and checkpoint settings reach their existing owner.
- `tests/cli/test_authoring_cmds.py:test_plan_set_rejects_unsupported_options_before_authoring` — Every explicitly unsupported option fails before backend calls or writes.
- `tests/cli/test_authoring_cmds.py:test_plan_set_no_resume_cannot_bypass_saved_set_preservation` — The selected checkpoint policy cannot recreate completed members or replace saved set state.
- `tests/cli/test_authoring_cmds.py:test_create_without_plan_set_source_preserves_existing_routes` — Inline, file-backed and reprocess routes retain dispatch; namespaces without the new attribute remain supported.
- `tests/cli/test_authoring_cmds.py:test_plan_set_reports_actual_outputs_and_unfinished_members` — Presentation distinguishes completed destinations, prerequisites and failure-to-complete outcomes with the correct return code.
- `tests/cli/test_authoring_cmds.py:test_plan_set_followups_name_authored_members_without_running_next_stages` — Follow-ups use actual plans and do not launch downstream stages.
- `tests/test_roadmap_plan_set.py:test_authoring_entry_point_composes_derivation_and_serial_create` — Real set orchestration with stubbed backend proposals saves the record, authors members and registers actual outputs.
- `tests/test_roadmap_plan_set.py:test_cli_retry_retains_completed_outputs_and_accepted_row_state` — Re-entry skips completed members and leaves accepted artifacts and accepted-row lifecycle bytes unchanged.

## Acceptance criteria

- `create SET_SLUG --from-roadmap ROADMAP_SLUG` selects one set-authoring invocation; no existing source implicitly selects it.
- Source conflicts and missing required identity fail before backend calls or artifact writes.
- The route uses step 3’s persistence and recovery contract, including preservation under retry and source drift.
- Repository, source-directory, output-directory and manifest settings reach their correct owners.
- Existing single-plan, file-backed split, reprocess and accepted-row seed behavior remains unchanged.
- Result output names the pinned source, saved record, actual authored plans and unfinished work without claiming semantic certification.
- `CAPABILITIES.md` identifies the route, and `docs/cli/create.md` matches generated parser output.
- Focused tests, existing create regressions, `tests/test_capability_catalog.py`, `tests/cli/test_cli_reference.py` and `uv run pytest tests/ -q -n auto` pass.
- Production edits stay within this step’s declared files; shared create and accepted-row lifecycle owners receive no changes.

## References

- [BACKLOG.md](BACKLOG.md) — Read #496 for the effort’s outcome and scope contract.
- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Read accepted-head authority and accepted-row provenance boundaries.
- [plan_tool/cli/authoring.py](plan_tool/cli/authoring.py) — Read `cmd_create` and `register` for current source dispatch and presentation.
- [plan_tool/create.py](plan_tool/create.py) — Read `create_plan` for individual authoring and registration ownership.
- [plan_tool/roadmap.py](plan_tool/roadmap.py) — Read `materialize_plan_seed` for the separate accepted-row route.
- [SEED_FORMAT.md](SEED_FORMAT.md) — Read the seed contract that remains owned by upstream authoring.
- [plan_tool/cli_reference.py](plan_tool/cli_reference.py) — Read `render_reference` for generated command documentation.

## Applicable guardrails

- **The plan’s “Step intent”:** Keep this change to explicit entry-point wiring and the configuration needed to derive and author the set in one invocation.
- **The plan’s “Scope guardrails,” structural enforcement:** Limit CLI refusals to input and structural state. Result rendering must not introduce semantic approval or quality judgments.
- **The plan’s “Out of scope,” existing behavior:** Keep compatibility through a separate opt-in branch rather than changing shared single-plan or accepted-row contracts.
- **The plan’s “Out of scope,” execution boundaries:** Stop at base-plan authoring and follow-up guidance. Do not launch application work or add scheduling machinery.
- **The plan’s “Scope guardrails,” source ownership:** Delegate source verification and saved-state handling to step 3; the CLI must not mutate accepted roadmap content or accepted-row seed state.

## Deferred

- Shared-authority or lifecycle changes — Any requirement to alter `plan_tool/create.py:create_plan`, `plan_tool/roadmap_seed_manifest.py` or `plan_tool/roadmap_seed_state.py` needs separate intentional work rather than expansion of this adapter.
- Real-model decomposition evidence — Step 5 owns the isolated comparison; passing routing tests does not establish improvement.
- Recovery procedures and backlog shipment reconciliation — Step 6 owns those documents and the final disposition of BACKLOG #496.
- Adjacent cross-plan features — BACKLOG #462, #493 and #494 remain separate from this authoring route.
