> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Prepare selected content and repair its references

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Prepare the content selected by step 1, recording report omissions and preserving useful conclusions in `docs/evidence/public-release-content-snapshot.md`. Update the declared evidence documents, handoff index, plan manifest and 13 retained document owners where the selection affects them. Keep historical measurements separate from sanitized example identity, and omit captured reports by default rather than rewriting their qualification metadata. Completion leaves an explicit selection with coherent references, honest provenance and unchanged runtime contracts.

## Table of Contents

- [Summary](#summary) — Deliverables and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Why selection requires reference and provenance repair.
- [Input](#input) — Step 1’s selection and existing identity contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Bounded document and manifest edits.
- [Implementation](#implementation) — Report treatment, replacements and reference repair.
- [Tests](#tests) — Artifact checks and existing regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Sources for scope and identity rules.
- [Applicable guardrails](#applicable-guardrails) — Boundaries affecting this preparation.
- [Deferred](#deferred) — Work outside this step.

## Why

`BACKLOG.md` #513 identifies saved reports whose local paths participate in audit revision identity, so replacing path text alone can invalidate their recorded digests. The context-budget evidence already distinguishes historical inputs from its sanitized example, but selected omissions can still leave handoff links and plan discovery pointing to unavailable documents. Preparing the selected content requires preserving useful conclusions without making changed evidence appear reusable or dependent on omitted material.

## Input

- **Step 1’s selection:** Read the exact tracked-path dispositions and ownership decisions in `docs/evidence/public-release-content-snapshot.md`. Step 1 creates this record; its absence is an unmet dependency, not permission to recreate the selection here.
- **Report identity:** `plan_tool/fingerprint.py:audit_input_revision(snapshot)` includes ordered detail revision entries in `detail_bundle_digest`. `plan_tool/review_persistence.py:normalize_audit_revision(value)` validates that digest, including the entries’ paths. Reuse both contracts unchanged.
- **Example identity:** Read `historical_payload_sha256`, `sanitized_payload_sha256`, `sanitized_payload_bytes` and `committed_raw_payload` in `docs/evidence/integration-context-budget-2026-10-09/provenance.json`. Read the “Sanitized example” notice and “How to read it” in `docs/evidence/integration-context-budget-2026-10-09/sizing.md`.
- **Discovery:** `.plan-tool/plans.json` stores a `plans` array of repository-relative paths. `plan_tool/locator.py:load_manifest_plan_paths` and `plan_tool/locator.py:list_plans_from_manifest` consume it; `plan_tool/locator.py:list_plans` separately discovers top-level plan files.
- **Evidence limits:** The selection and scans establish bounded preparation evidence. They do not establish redistribution rights, semantic privacy clearance or exact replay of unavailable original inputs.

## Files (creates vs edits)

**New files:**

- None. Step 1 owns creation of `docs/evidence/public-release-content-snapshot.md`.

**Existing files (edits only):**

- `docs/evidence/public-release-content-snapshot.md` — Record applied dispositions, useful conclusions preserved from omitted reports, reference repairs, digest checks and unresolved dependencies.
- `docs/evidence/integration-context-budget-2026-10-09/provenance.json` — Make bounded neutral wording or provenance corrections required by the selection; preserve historical identities and verify the sanitized example’s identity fields.
- `docs/evidence/integration-context-budget-2026-10-09/sizing.md` — Repair selection-dependent references and clarify retained evidence limits without changing historical measurements.
- `handoffs/README.md` — Align retained handoff and ledger listings with the selection; preserve relevant live decisions through the selection record.
- `.plan-tool/plans.json` — Align registered plan paths with selected retained plans while preserving the manifest structure and unrelated entries.

The following 13 retained document owners receive bounded report-reference repairs.
Their existing responsibilities and decisions remain unchanged:

- `docs/evidence/authored-artifact-structure-versioning.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `docs/explanations/audit-pass-persistence.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `docs/explanations/nondeterministic-plan-design.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `docs/history/backlog-decisions.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `docs/implementation-plans/archive/2-jira-grade-01-detail-instrument.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `handoffs/2026-09-14-developer-docs-and-tracking.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `handoffs/2026-09-25-roadmap-candidate-vocabulary-retry.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `handoffs/2026-10-20-public-release-content-snapshot-plan-review.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `plan-seeds/archive/jira-grade-01-detail-instrument.distilled.replaced.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `plan-seeds/archive/jira-grade-01-detail-instrument.replaced.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `BACKLOG.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.
- `handoffs/2026-10-19-public-onboarding-and-release.md` — Replace essential dependencies on omitted reports with retained conclusions or usable local references.

## Implementation

- **Foundational logic: apply explicit content dispositions without changing evidence identity.** Use step 1’s selected paths as the authority. Prefer omission of captured reports plus a self-contained conclusion in `docs/evidence/public-release-content-snapshot.md`; reject bulk report rewriting as the preparation approach.

- **Enumerate affected references before editing.** Search tracked content by exact selected path and by its title or topic. Record which references need repair, which remain valid and which require work outside the declared files; repeat both searches after editing.

- **Close the known retained-reader dependencies.** Review the 13 document owners above against the selection record's “Reference verification.” Read each cited report before extracting its useful non-identifying conclusion. Replace concrete links and instructions to open excluded captures with retained, self-contained explanations or local evidence references. Preserve pending decisions, historical measurement limits and ledger closure labels. Do not merely delete the citation or invent evidence.

- **Distinguish live instructions from historical provenance.** A source path may remain as dated measurement context when understanding or acting on the retained text does not require opening it. Runtime/template examples of newly generated reports may remain explicitly illustrative. Actual links and required capture-opening instructions must resolve within selected content. The release pickup and review record point to the maintained conclusions needed for the next action.

- **Keep omission separate from deletion in this checkout.** Record exact report and historical-document exclusions for step 5’s snapshot assembly. This step must not delete or rewrite report files outside its declared footprint, and the record must distinguish excluded snapshot content from files physically removed.

- **Preserve useful conclusions before excluding their sources.** Summarize necessary non-identifying findings and settled decisions in `docs/evidence/public-release-content-snapshot.md`. Give each summary its source path, relevant evidence limits and disposition without copying private text or implying that the summary carries the report’s audit qualification.

- **Keep report pairs out of reusable audit evidence.** Apply the selected treatment consistently to report Markdown and associated JSON sidecars. An illustrative summary must not become a saved-review sidecar or be described as a fresh, qualified audit; preserve `plan_tool/fingerprint.py:audit_input_revision` and `plan_tool/review_persistence.py:normalize_audit_revision` unchanged.

- **Use neutral replacements only where selection requires them.** Keep relationships and technical distinctions coherent across the declared files. Preserve approved technical names and distribution identifiers from `handoffs/2026-10-19-public-onboarding-and-release.md` under “Current decisions”; do not repeat the completed repository-wide naming sweep.

- **Preserve the context-budget bundle’s two identities.** Verify `sanitized_payload_sha256` and `sanitized_payload_bytes` against `docs/evidence/integration-context-budget-2026-10-09/canonical-payload.json`. Keep `historical_payload_sha256`, artifact hashes and historical byte/token measurements attached to their original inputs; do not substitute the sanitized example’s size for a historical measurement.

- **Treat existing provenance notices as work already present.** Retain accurate notices in `docs/evidence/integration-context-budget-2026-10-09/provenance.json` and `docs/evidence/integration-context-budget-2026-10-09/sizing.md`; change only remaining inaccuracies or selection-dependent references. Read `docs/evidence/integration-context-budget-2026-10-09/measurements.json` and `docs/evidence/README.md` as unchanged consistency checks, not additional edit targets.

- **Repair indexes against the selected tree.** In `handoffs/README.md`, remove links to excluded documents or point readers to the retained conclusion that serves their task. Preserve the distinction between live handoffs and review ledgers under “Retention”; exclusion must not silently discard an unresolved decision.

- **Keep manifest edits narrowly tied to selection.** Remove `.plan-tool/plans.json` entries only for plans explicitly excluded by step 1, and preserve retained entries and their ordering. Removing an entry alone does not prove exclusion because `plan_tool/locator.py:list_plans` also scans the plans directory; record the corresponding file exclusion for step 5.

- **Stop at the declared file boundary.** If a retained document outside these files depends on an excluded source, record the exact dependency and required repair in `docs/evidence/public-release-content-snapshot.md`. Keep that selection unresolved until the owning work repairs it; do not claim a coherent snapshot or silently expand this step.

## Tests

### Verification (non-code step)

The test-authoring gate does not apply: this step is `change_type: non-code`, while `enforce_step_tests` requires test-file authorship for code changes. Do not add unit tests solely for these document edits.

1. `verify_selection_accounts_for_report_pairs` — Every selected report exclusion identifies its Markdown and associated sidecar treatment; retained summaries make no reusable-audit claim.
2. `verify_preserved_conclusions_are_self_contained` — Required conclusions remain understandable without opening excluded documents or ignored evidence.
3. `verify_sanitized_payload_identity_matches_retained_bytes` — SHA-256 and byte count of `docs/evidence/integration-context-budget-2026-10-09/canonical-payload.json` match the corresponding sanitized fields in `docs/evidence/integration-context-budget-2026-10-09/provenance.json`.
4. `verify_historical_measurements_keep_original_identity` — Historical hashes and measurements remain unchanged, and both edited evidence documents explain why the sanitized example cannot reproduce the original measurement.
5. `verify_selected_links_and_anchors_exist` — Resolve local links across selected Markdown and check concrete capture-opening instructions at all 13 known owners. Each required explanation or action works from retained content; repeat identifier and vocabulary searches, distinguishing supporting citations and illustrative runtime paths from unresolved dependencies. Record any new out-of-footprint dependency explicitly; it prevents snapshot readiness.
6. `verify_manifest_matches_selected_plans` — `.plan-tool/plans.json` parses, retained entries point to selected plan files, and every removed entry has an explicit exclusion disposition.
7. `verify_omission_does_not_claim_deletion` — The selection record distinguishes snapshot exclusions from checkout changes and accounts for plans discoverable without the manifest.
8. `verify_preparation_preserves_scope_and_open_decisions` — Diff review confirms only declared files change, approved names remain, and unresolved rights or reference dependencies remain explicit.
9. `existing_identity_and_discovery_regressions` — Run `uv run pytest tests/test_fingerprint.py tests/test_review_persistence.py tests/test_locator.py tests/cli/test_manifest_cmds.py -q`; retain the existing assertions and record results in `docs/evidence/public-release-content-snapshot.md`.

## Acceptance criteria

- Every applied omission or replacement traces to step 1’s disposition in `docs/evidence/public-release-content-snapshot.md`.
- Useful conclusions from excluded reports remain available without private text, omitted sources or claims of qualified audit reuse.
- Report files and runtime identity contracts remain unchanged; exclusions account for associated report sidecars.
- The sanitized payload’s recorded SHA-256 and byte count match its retained bytes, while historical identity fields and measurements retain their original meaning.
- All 13 known retained document owners have their report dependencies repaired or explicitly shown to be non-actionable provenance/examples; useful conclusions and decisions remain available. Edited links and manifest entries agree with selected content. Any new unresolved dependency outside the footprint remains explicit and prevents a claim of complete preparation.
- Manifest removal is accompanied by a recorded snapshot file exclusion where directory discovery could otherwise find the plan.
- The numbered verification checks pass or record a concrete unresolved dependency, and the affected regression suite passes.
- No changes extend beyond the declared files, and no publication or full-shipment claim appears.

## References

- [Public Release Content Snapshot](../../2-public-release-content-snapshot.md) — Read “Architecture” for report omission, evidence identity and snapshot boundaries.
- [BACKLOG.md](../../../../BACKLOG.md) — Read #513 for the cleanup contract and #514 for the selected distribution boundary.
- [Public onboarding and release pickup](../../../../handoffs/2026-10-19-public-onboarding-and-release.md) — Read “Current decisions” and “Preparation result” for scope and evidence limits.
- [Context-budget provenance](../../../evidence/integration-context-budget-2026-10-09/provenance.json) — Distinguish historical input identity from the sanitized payload.
- [Context-budget sizing](../../../evidence/integration-context-budget-2026-10-09/sizing.md) — Preserve the measurement’s purpose and replay limitations.
- [Audit revision construction](../../../../plan_tool/fingerprint.py) — Read `audit_input_revision` for path-bearing detail identity.
- [Audit revision validation](../../../../plan_tool/review_persistence.py) — Read `normalize_audit_revision` for digest validation.
- [Developer documentation style](../../../reference/documentation-style.md) — Follow its guidance on document ownership and reference repair.

## Applicable guardrails

- **The plan’s “Scope guardrails,” runtime contracts:** Prepare content through the declared documents and manifest; do not alter report readers, qualification rules or artifact identity.
- **The plan’s “Scope guardrails,” ownership and approved references:** Apply recorded ownership decisions to replacements and preserve approved names; scan results do not settle uncertain dispositions.
- **The plan’s “Scope guardrails,” publication boundary:** Record local preparation only; this step grants no authority to publish or change remote state.
- **The plan’s “Scope guardrails,” protected guidance:** Keep `CLAUDE.md` outside this step’s edits and route any required change through its owning work and review requirement.
- **The plan’s “Out of scope,” bounded preparation:** Use direct document edits and verification rather than introducing a sanitizer, validator or shared identity mechanism.

## Deferred

- Maintainer guidance — Step 3 owns self-contained explanations and usable procedures.
- Policy rights and PDF disposition — Step 4 owns the dependent retention decision; neutral wording does not establish redistribution rights.
- Independent snapshot assembly and verification — Step 5 applies the selected exclusions in a separate repository and checks the resulting content without internal ancestry.
- Final backlog and pickup reconciliation — Step 6 owns shipment status and remaining prerequisites.
- Newly discovered reference repairs outside the expanded declared files — Record exact dependencies in `docs/evidence/public-release-content-snapshot.md` for scope reconciliation; the 13 known owners are this step’s responsibility, and this detail does not authorize further extra edits.
- Shared evidence and discovery behavior — Reuse `plan_tool/fingerprint.py`, `plan_tool/review_persistence.py` and `plan_tool/locator.py` unchanged; changing their authority or interpretation requires separate intentional work.
