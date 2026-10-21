> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Inventory live evidence, reissue eligible records as version 2, retain only non-routable legacy history, and block retirement on unresolved legacy finals without overwriting immutable finals

## Summary

Create `docs/history/roadmap-evidence-v1-retirement.md` as the release record for version-1 roadmap evidence. The record states an explicit project/roadmap roster, inventories every roster entry's active receipt and impact-analysis namespaces, validates each discovered final, and assigns each version-1 final one disposition. The key decision is to reissue through the existing version-2 writers or retain immutable bytes only as non-routable history; never infer a missing baseline identity or replace an existing final. Green means retirement has a reviewable proof that no usable version-1 route is lost or silently hidden.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the retirement record and completion result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why reader retirement needs an evidence release record first.
- [Input](#input) — Existing evidence storage, parsing, and route contracts this record reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The document created by this non-code step.
- [Implementation](#implementation) — Required inventory, disposition, and release-gate rules.
- [Tests](#tests) — Existing contract tests that support the record’s assumptions.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks for the record.
- [References](#references) — Validation and serialization references for the evidence contracts.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain the inventory.
- [Deferred](#deferred) — Work intentionally left to later steps or future planning.

## Why

The active evidence store treats every hash-named final in its namespaces as readable evidence, while the receipt, impact, and structural routes can still use version 1 under different freshness rules. Removing those readers without a project-by-project record could strand an active route or hide it as “history.” This step makes retirement a release decision backed by the current namespaces, current writer outcomes, and explicit owner confirmation.

## Input

- **Active evidence locations:** Use `plan_tool/roadmap_artifacts.py:roadmap_dir` with the already-resolved plans directory, then use `plan_tool/roadmap_evidence_store.py:EvidenceNamespace`, `namespace_relative_components`, and `scan_evidence` to identify receipt and impact-analysis finals without hard-coding a plans path. `roadmap_dir` resolves a supplied slug against the plans directory; `scan_evidence` then scans the resulting root's namespace. Neither discovers a roster on its own. The operator supplies both the project/roadmap roster and the consumer roster explicitly; see the Implementation's roster requirements.
- **Receipt facts:** Validate each receipt’s bytes and storage name through `plan_tool/roadmap_escalation.py:parse_receipt` and `validate_receipt_final_name`. Record its `schema_version`, selector, reason, source provenance, and final name; a version-1 receipt has no writer-owned canonical source identity to copy into a replacement.
- **Analysis facts:** Validate each analysis through `plan_tool/roadmap_impact_analysis.py:parse_impact_analysis` and `validate_impact_analysis_final_name`. Record its `schema_version`, final name, and embedded receipt final so the release record can bind a legacy analysis to its receipt route.
- **Live-route evidence:** Use the existing inspection and creation boundaries as the source of operational results: `plan_tool/roadmap_escalation_run.py:current_escalation_receipt`, `run_roadmap_escalation_receipt`, `plan_tool/roadmap_impact_run.py:current_impact_analysis`, and `run_roadmap_impact_analysis`.
- **Human confirmation:** A scan and a freshness result cannot prove that no workflow still needs a final. The record needs an accountable owner confirmation for every archive-safe disposition.

## Files (creates vs edits)

- **New files:**
  - `docs/history/roadmap-evidence-v1-retirement.md` — Release record covering discovery, validation, disposition, retained history, replacements, blockers, and the retirement decision.

- **Existing files (edits only):**
  - None. This step changes no production code, tests, or existing documentation.

## Implementation

- **Use one complete disposition rule:** The foundational rule is that every discovered version-1 final is exactly one of `reissue`, `archive-safe`, or `blocking`. Do not leave a record unclassified, assign multiple dispositions, or treat a scan failure as an empty namespace.

- **State the inventory roster explicitly, before scanning anything.** Name the closed set of every project and roadmap slug known to use this package's roadmap evidence store, as of a stated cutoff date. This named, dated roster — not an unstated "everything reachable" scan — is what the rest of this step and its verification exhaust; a document that claims "every known project" without stating the roster it means fails `verify_inventory_coverage`.

- **State the consumer roster explicitly, alongside the inventory roster.** `_load_requested_receipt` and `load_structural_revision_preflight` take a caller-supplied final name — neither can discover who calls them, the same way `roadmap_dir`/`scan_evidence` can't discover which projects exist. Name the closed set of every known system or workflow (human-operated or automated — Integration, as of this plan's Problem Statement, is the only one currently known) that names a receipt or receipt-analysis pair by its exact final name, as of the same stated cutoff date. This is the operator's own attestation, not a scan result; it is what "Capture the route graph" and every "named consumer" reference below mean by consumer.

- **Inventory both active namespaces for every roster entry:** For each project and roadmap slug in that roster, record the resolved roadmap root, the scan date, and the results from `plan_tool/roadmap_evidence_store.py:scan_evidence` for both `EvidenceNamespace.ESCALATIONS` and `EvidenceNamespace.IMPACT_ANALYSES`. Record empty namespaces and storage failures explicitly; a storage failure is blocking until it is resolved.

- **Validate before deciding:** Use the receipt and analysis parsers plus their final-name validators to distinguish a valid version-1 final from malformed, substituted, or unreadable bytes. Record invalid or unreadable finals as unresolved evidence; they cannot be silently dropped from the release decision.

- **Capture the route graph, not just file presence:** For each receipt, record whether `plan_tool/roadmap_escalation_run.py:current_escalation_receipt` can still expose it as fresh. For each analysis, record its embedded receipt final and whether `plan_tool/roadmap_impact_run.py:current_impact_analysis` can still expose a route. Also check the exact-consumer paths: `plan_tool/roadmap_impact_run.py:_load_requested_receipt` consumes a named receipt, and `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` consumes a named receipt-analysis pair.

- **Reissue only through current writers:** A reissuable record must have current, eligible feedback that the version-2 receipt writer can admit with its writer-owned baseline. Use `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt`, which issues through `NEW_RECEIPT_SCHEMA_VERSION`, then use `plan_tool/roadmap_impact_run.py:run_roadmap_impact_analysis` to derive the replacement analysis from that new receipt. Record both replacement final names and their successful validation; do not rebuild a version-2 payload from retained version-1 fields.

- **A reissue is not complete until every consumer roster entry has cut over.** `plan_tool/roadmap_impact_run.py:_load_requested_receipt` and `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` take an exact final name from their caller — they resolve no "current" pointer and offer no redirect. A workflow on the consumer roster that still names the original final after retirement gets the fail-closed refusal steps 2–5 introduce, not an automatic route to the replacement. Treat every reissued original's applicable consumer-roster entries exactly like an archive-safe route: each needs the same accountable owner confirmation that it has switched to the replacement final name before the original can leave `reissue` status. A reissued record without every applicable confirmation is not resolved.

- **A reissue is not resolved until the original is retired the same way an archive-safe original is.** Once every named consumer confirms cutover, the original is non-routable — nobody has a reason to read it by its own final name again. Leaving it in the active namespace contradicts this document's own Overview ("move only non-routable history out of active evidence namespaces") and means `scan_evidence` and the escalation/impact-analyses CLI views keep surfacing a stale `invalid` record indefinitely, with no recorded reason. Apply the same treatment "Archive only non-routable history" describes: preserve the original bytes under a dated history location outside every active `EvidenceNamespace` path, and record the original namespace and final name, the history path, and matching before-and-after byte digests. The disposition stays `reissue`, not `archive-safe` — the two describe why the original left service, not how its bytes are retained.

- **Keep reissue order explicit:** Reissue the receipt before its analysis. A legacy analysis is not independently upgraded: its replacement must bind the newly issued receipt, not the legacy receipt or an inferred identity.

- **Archive only non-routable history:** Mark a legacy final archive-safe only after its owner confirms that no current workflow needs it as a route. A `resolved`, `stale`, or `requires-scope-review` status alone is not that confirmation. Preserve the original bytes under a dated history location outside every active `plan_tool/roadmap_evidence_store.py:EvidenceNamespace` path, then record the original namespace and final name, the history path, and matching before-and-after byte digests.

- **Keep immutable finals immutable:** Do not modify a version-1 final in place, publish replacement bytes under its name, or overwrite an occupied replacement final. `plan_tool/roadmap_evidence_store.py:publish_evidence` and `tests/test_roadmap_evidence_store.py:test_publish_reuses_exact_final_without_overwriting` establish the required immutable-publication behavior. Remove an original from an active namespace only after the retained history is verified and a fresh scan proves it is absent from active evidence.

- **Block on uncertainty:** Classify as blocking any final that remains an active route, cannot complete reissue, has a reissued replacement with an unconfirmed named-consumer cutover or an unretained/unproven-absent original, lacks owner confirmation, has an unproven history copy, is malformed or unreadable, or has a missing required receipt/analysis counterpart. Blocking records remain visible in their active namespace and prevent reader retirement.

- **Make the release decision checkable:** One way is to use one project section per roadmap with a per-final table and a short release-gate summary. Every row should retain the original final’s namespace, final name, byte digest, validation result, disposition, replacement or history path, route/owner verification, and final status. The document must state whether retirement is blocked and name every blocking row without changing any runtime behavior.

- **Record a dated, named approval — distinct from a zero-blocker record.** `DATA_CONTRACT.md`'s version-evolution policy requires "a user-approved retirement," not only a technically clean record. A zero-blocker record proves the rosters were exhausted and every final resolved; it does not by itself prove an accountable owner reviewed and approved retiring reader support. Record the approver, the date, and that they reviewed the final roster set, the disposition table, and the retirement decision before it takes effect.

- **Do not broaden the document into implementation work:** `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_escalations_view` and `_cmd_roadmap_impact_analyses_view` are useful inspection surfaces, but this step does not alter them. Later steps remove version dispatch and add the post-retirement refusal coverage.

## Tests

- `tests/test_roadmap_evidence_store.py::test_scan_returns_only_matching_records_in_raw_name_order` — Confirms that the inventory is limited to exact final-name records and remains deterministic.
- `tests/test_roadmap_evidence_store.py::test_publish_reuses_exact_final_without_overwriting` — Confirms that a reissue must not replace immutable evidence.
- `tests/test_roadmap_escalation_run.py::test_v2_receipt_creation_rechecks_semantic_admission_before_publication` — Confirms that version-2 receipt issuance observes current admission before publication.
- `tests/test_roadmap_impact_run.py::test_v2_run_publishes_without_mutating_roadmap_source_or_baseline` — Confirms that derived version-2 analysis publication does not rewrite source or baseline state.

### Verification (non-code step)

1. `verify_inventory_coverage` — Confirm the document states an explicit, dated project/roadmap roster and records both active evidence namespaces for every roster entry, including empty and unreadable results. A document that asserts "every known project" with no stated roster behind it fails this check.
2. `verify_consumer_roster` — Confirm the document states an explicit, dated consumer roster (Integration, plus any other named system or workflow known to reference a final by exact name) alongside the project/roadmap roster. A document that identifies "named consumers" per reissue row without a stated closed roster behind them fails this check.
3. `verify_disposition_exclusivity` — Confirm every valid version-1 final has exactly one disposition and every unresolved record is blocking.
4. `verify_reissue_chain` — For each reissue row, confirm the replacement receipt validates as version 2, the replacement analysis binds that receipt, both new final names are recorded, every applicable consumer-roster entry has confirmed cutover to the replacement, and — once that cutover is confirmed — the original's dated history bytes match its recorded digest and a fresh active-namespace scan no longer finds it (the same proof `verify_archive_retention_and_absence` requires for archive-safe rows). A reissue row missing consumer-cutover confirmation or retention-and-absence proof is not complete.
5. `verify_archive_retention_and_absence` — For each archive-safe row, confirm the dated history bytes match the recorded final digest and a fresh active-namespace scan no longer finds that final.
6. `verify_archive_confirmation` — Confirm every archive-safe row includes owner confirmation that the final is no longer needed as a route.
7. `verify_blocking_gate` — **This step is not complete while any blocking row remains.** Confirm the release decision is blocked whenever any blocking row remains and that those originals stay unchanged in the active namespace. Do not report this step done, and do not advance to step 2, until every discovered final is `reissue` (with confirmed consumer cutover) or `archive-safe` — a documented blocker that this step's own status does not enforce is exactly the gap this verification item exists to close.
8. `verify_approval` — Confirm the document records a dated, named approval of the final roster set, disposition table, and retirement decision, distinct from the zero-blocker record itself, per `DATA_CONTRACT.md`'s user-approved-retirement requirement.
9. `verify_scope` — Confirm `git diff --check` passes and the diff changes only `docs/history/roadmap-evidence-v1-retirement.md`.

## Acceptance criteria

- `docs/history/roadmap-evidence-v1-retirement.md` states an explicit, dated project/roadmap roster and a separate dated consumer roster, and records the discovery result for both active evidence namespaces for every roster entry.
- Every discovered, valid version-1 receipt or analysis final has exactly one `reissue`, `archive-safe`, or `blocking` disposition with its original namespace, final name, and byte digest.
- Every reissue row records a validated version-2 receipt and the analysis derived from that receipt, confirmed cutover for every applicable consumer-roster entry, and — once cutover is confirmed — the same dated history location, retained bytes, and post-move active-namespace absence an archive-safe row proves; no row describes an in-place conversion or inferred canonical identity.
- Every archive-safe row records owner confirmation, a dated history location outside active evidence namespaces, matching retained bytes, and a post-archive scan that no longer finds the original final.
- Every unresolved, malformed, unreadable, active-route, failed-reissue, unconfirmed-consumer-cutover, or unconfirmed-archive record is marked blocking and prevents the document from declaring retirement ready. **While any blocking row remains, this step is not complete and steps 2–5 must not begin** — a documented blocker is a precondition on this step's own status, not only a fact recorded in the document.
- The document records a dated, named approval of the final roster set, disposition table, and retirement decision, distinct from the zero-blocker record itself.
- The document preserves the unrelated structural operation-envelope version contract as outside this inventory.
- The step’s diff creates only `docs/history/roadmap-evidence-v1-retirement.md`.

## References

- [Validators | Pydantic Docshttps: — Review the validation rules that distinguish supported evidence schemas from malformed records.
- [Fields | Pydantic Docshttps: — Review required and optional field behavior when comparing version-1 and version-2 evidence shapes.
- [Serialization | Pydantic Docshttps: — Review serialization behavior behind immutable, schema-versioned evidence records.

## Applicable guardrails

- **The plan’s “## Architecture”, legacy-evidence disposition:** Keep the document as the proof that retirement preserves usable routes before later steps remove reader support.
- **The plan’s “## Out of scope”, version-2 contract:** Do not change version-2 semantics, admission, baseline identity, or canonical-identity behavior while recording the inventory.
- **The plan’s “## Out of scope”, in-place conversion:** Reissue through existing writers or retain history; do not propose a generic converter.
- **The plan’s “## Out of scope”, structural operation envelope:** Do not classify the independent structural-operation protocol as roadmap evidence or change its documentation.
- **The plan’s step intent:** Treat uncertainty as a release blocker so no project loses a usable evidence route.

## Deferred

- Reader, schema, and CLI refusal changes — Steps 2 through 5 implement the version-2-only runtime contract after this record clears retirement.
- Automated migration or archival tooling — Requires a separate planned capability; this step records operational evidence and uses existing writers.
- Structural-operation protocol changes — Remain outside the roadmap-evidence retirement scope.
