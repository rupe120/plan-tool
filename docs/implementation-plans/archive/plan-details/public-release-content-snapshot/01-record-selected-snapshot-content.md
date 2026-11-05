> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Record snapshot selection and content dispositions

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Create `docs/evidence/public-release-content-snapshot.md` as the durable record of selected content, ownership decisions and exclusions. Record captured reports as excluded by default, with exact tracked paths and any useful conclusions identified for preservation. Update `BACKLOG.md` and `handoffs/2026-10-19-public-onboarding-and-release.md` to point to this record and distinguish settled decisions from unresolved rights. Completion gives later steps an explicit content selection without modifying reports or claiming release clearance.

## Table of Contents

- [Summary](#summary) — Deliverable and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Why the selection needs a durable owner.
- [Input](#input) — Existing decisions and identity contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Allowed document changes.
- [Implementation](#implementation) — Selection, ownership and exclusion rules.
- [Tests](#tests) — Document verification.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Grounding sources.
- [Applicable guardrails](#applicable-guardrails) — Boundaries affecting this step.
- [Deferred](#deferred) — Work owned by later steps and other efforts.

## Why

Content preparation needs one exact selected-path record and explicit ownership
dispositions. Use it to keep linked evidence, examples, policy artifacts and
verification aligned. Identify the meaning of each digest so a sanitized example
cannot silently replace a measurement input or qualified report.

## Input

- **Scope and decisions:** Read `BACKLOG.md` #513 and #514 alongside `handoffs/2026-10-19-public-onboarding-and-release.md`, especially “Current decisions” and “Preparation result.” Attribute owner decisions separately from recommendations and scan observations.
- **Report identity:** `plan_tool/fingerprint.py:audit_input_revision(snapshot)` hashes the ordered detail revision entries into `detail_bundle_digest`. `plan_tool/review_persistence.py:normalize_audit_revision(value)` validates the revision, including its detail entries and digest. Treat these as unchanged contracts.
- **Example provenance:** `docs/evidence/integration-context-budget-2026-10-09/provenance.json` distinguishes `historical_payload_sha256` from `sanitized_payload_sha256`; `docs/evidence/integration-context-budget-2026-10-09/sizing.md` explains the replay limits. Use this distinction when describing retained evidence.
- **Inventory limits:** Ignored scratch inventories are optional leads. Derive the recorded selection from tracked paths at an identified checkout baseline; do not require another clone to possess ignored files.

## Files (creates vs edits)

**New files:**

- `docs/evidence/public-release-content-snapshot.md` — Record the selection baseline, exact path dispositions, ownership evidence, report exclusions, preserved conclusions and unresolved decisions.

**Existing files (edits only):**

- `BACKLOG.md` — Update #513’s planning status and remaining-review notes; link to the selection record and reconcile its PDF review with the newer handoff evidence. Keep #513 open.
- `handoffs/2026-10-19-public-onboarding-and-release.md` — Point pickup instructions to the selection record and replace superseded report-treatment alternatives with the selected route. Preserve remaining prerequisites and authority boundaries.

## Implementation

- **Foundational logic: explicit publication disposition backed by ownership evidence.** Make `docs/evidence/public-release-content-snapshot.md` the owner of this plan’s content selection. Keep `BACKLOG.md` as the work-status owner and the handoff as the pickup route; link to the record rather than maintaining competing inventories.

- **Bind the selection to tracked content.** Record the baseline commit and inventory method. One approach is a baseline tracked-file set with exact exclusions and exceptions, supplemented by ownership rows for content classes. The record must let a reviewer determine which paths are selected, excluded or awaiting a decision without ignored scratch files.

- **Separate ownership from treatment.** For each reviewed class, record its paths or membership rule, ownership classification, evidence or decision source, selected treatment and unresolved dependency. Distinguish owner-controlled projects, client-derived material, approved technical references and approved distribution identifiers. Do not copy private identifiers into the evidence record merely to document their removal.

- **Record report omission as the default.** Enumerate the exact captured-report paths excluded from the snapshot, covering active and archived reports. Use the handoff’s report counts as dated inventory evidence, not fixed expected totals; reconcile differences against the current tracked set, including newly generated reports.

- **Preserve useful conclusions without preserving misleading qualification.** Identify which excluded reports contain conclusions needed by retained documents and name their destination in the evidence record or an existing canonical owner. Label summaries as summaries, without implying original-byte replay or reusable audit qualification. Step 2 owns the content preparation and reference repairs.

- **Keep report identity intact.** Explain the path/digest relationship using `plan_tool/fingerprint.py:audit_input_revision` and `plan_tool/review_persistence.py:normalize_audit_revision`. Reject path-only report rewriting or digest replacement as release cleanup. This step must not alter report bytes, report readers or qualification rules.

- **Classify historical documents and hash references separately.** Identify retained, excluded and decision-pending historical plans, handoffs and evidence. For proposed exclusions, name any live decisions or inbound references that require preservation or repair before omission. Distinguish Git citations from content digests; step 3 owns retained-citation treatment.

- **Record policy rights without inventing approval.** Track `AI_SDLC_POLICY.pdf` and `docs/reference/ai-assisted-development-policy.md` separately where their dispositions differ. Carry forward the rebuild decision and evidence, while recording redistribution rights as unresolved unless an explicit owner decision supplies them. Unresolved rights must prevent dependent content from being marked publishable.

- **Keep verification claims bounded.** Record intentional survivors, reviewed exclusions and remaining coverage gaps. A candidate match must not become an ownership verdict automatically, and a clean scan must not become rights or secrets clearance.

- **Update routing without claiming shipment.** In `BACKLOG.md` #513 and the handoff, identify this record as the input to steps 2–5. Keep implementation, rights decisions and final verification visibly pending. Do not remove #513 or revise #514’s settled distribution choices.

## Tests

This is a `non-code` step. The test-authoring gate does not apply because it keys on `change_type: feature` or `change_type: refactor`. No new unit tests are required; `tests/test_fingerprint.py` and `tests/test_review_persistence.py` remain the existing coverage for the unchanged report contracts.

### Verification (non-code step)

1. `verify_selection_matches_recorded_tracked_baseline` — Every selected or excluded path exists in the recorded tracked set, and the selection rule accounts for that set without unexplained overlaps.
2. `verify_report_exclusions_include_active_archived_and_new_reports` — Compare the exact exclusion list against tracked captured reports; explain differences from the handoff’s dated counts.
3. `verify_ownership_decisions_have_evidence` — Every content-class disposition cites a decision or evidence source; unknown ownership and rights remain explicit.
4. `verify_omitted_evidence_has_a_preservation_destination` — Every useful conclusion and live dependency identified during exclusion review has a named destination or required repair.
5. `verify_report_identity_claims_match_existing_contracts` — Check the record against `plan_tool/fingerprint.py:audit_input_revision` and `plan_tool/review_persistence.py:normalize_audit_revision`; distinguish historical hashes from sanitized-example identity.
6. `verify_status_and_rights_are_consistent` — The evidence record, #513 and the handoff agree on report omission, the PDF rebuild, unresolved redistribution rights and pending shipment.
7. `verify_document_links_and_change_scope` — Check links and symbolic anchors, then inspect the diff to confirm only the three declared documents change and no report bytes change.

## Acceptance criteria

- `docs/evidence/public-release-content-snapshot.md` identifies a tracked baseline and an unambiguous selection rule with exact exclusions and exceptions.
- Every reviewed content class has an ownership classification, publication disposition and supporting source; unresolved decisions remain visible.
- Captured-report exclusions cover the current tracked inventory, including active, archived and newly generated reports.
- Useful conclusions and live dependencies affected by proposed exclusions have named preservation destinations or reference repairs for subsequent steps.
- The record distinguishes Git citations, content digests, historical measurements and sanitized examples without claiming changed bytes are original evidence.
- PDF rebuilding and redistribution rights have separate recorded dispositions; unresolved rights do not appear as approval.
- `BACKLOG.md` #513 remains open and links to the record; the handoff points to the same selection without competing report-treatment instructions.
- All numbered verification checks pass, and the diff contains only the declared document changes.

## References

- [BACKLOG.md](../../../../BACKLOG.md) — Read #513’s scope contract and #514’s settled distribution boundary.
- [Public onboarding and release pickup](../../../../handoffs/2026-10-19-public-onboarding-and-release.md) — Read owner decisions, inventory limits and report/PDF evidence.
- [Public-release coordination arc](../../backlog-arcs/backlog-arc-public-release.md) — Check prerequisite ownership and ordering.
- [Integration evidence provenance](../../../evidence/integration-context-budget-2026-10-09/provenance.json) — Compare historical input identity with sanitized-example identity.
- [Integration sizing evidence](../../../evidence/integration-context-budget-2026-10-09/sizing.md) — Read the limits on reproducing historical measurements.
- [Report revision producer](../../../../plan_tool/fingerprint.py) — Inspect `audit_input_revision` for the hashed revision contract.
- [Report revision normalizer](../../../../plan_tool/review_persistence.py) — Inspect `normalize_audit_revision` for revision validation.
- [AI-assisted development policy source](../../../reference/ai-assisted-development-policy.md) — Identify the tracked source whose redistribution disposition needs recording.
- [Developer documentation style](../../../reference/documentation-style.md) — Structure ownership mappings and distinguish current routes from dated evidence.

## Applicable guardrails

- **The plan’s “Scope guardrails,” content-only authority:** Record decisions and selections within the declared documents; do not perform release or repository-boundary actions.
- **The plan’s “Scope guardrails,” runtime contracts:** Use existing report identity rules as evidence. Do not change their implementation or reinterpret qualification to retain sanitized reports.
- **The plan’s “Scope guardrails,” evidence limits:** Keep ownership decisions separate from scan findings and state the limits of each verification claim.
- **The plan’s “Scope guardrails,” retained references and settled choices:** Carry approved retention decisions into the record without reopening them.
- **The plan’s “Scope guardrails,” protected guidance:** Leave protected guidance edits to their owning step and required review.
- **The plan’s “Out of scope,” adjacent release work:** Identify external prerequisites by owner; do not turn the selection record into their implementation or a new validation system.

## Deferred

- Content edits, report omissions and dependent reference repairs — Step 2 applies the selection and preserves needed conclusions.
- Maintainer guidance — Step 3 keeps decisions, evidence and procedures self-contained.
- Policy retention and any bounded PDF replacement — Step 4 applies explicit rights decisions; this step records their availability and effect on selection.
- Independent snapshot verification — Step 5 checks the prepared selection without internal ancestry or ignored configuration.
- Final #513 reconciliation — Step 6 records shipment only after the plan’s required evidence and rights decisions exist.
- Report identity implementation changes — `plan_tool/fingerprint.py` and `plan_tool/review_persistence.py` remain unchanged shared authorities; release preparation does not require changing them.
- Distribution/update guidance and fresh-consumer onboarding — Remain with the backlog owners named in the plan’s “Deferred” and “Out of scope” sections.
