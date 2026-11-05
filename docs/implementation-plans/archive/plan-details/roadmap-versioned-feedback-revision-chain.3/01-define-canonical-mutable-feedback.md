> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Define the canonical mutable feedback ledger, target fingerprints, and eligibility rules

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Create `plan_tool/roadmap_feedback_ledger.py` and its focused test module to define the reviewer-owned feedback ledger contract. The module owns typed ledger records, canonical rendering and loading, stable item identities, target fingerprints, and the predicate that selects eligible reviewer-created feedback. The key decision is to bind an `open` item to one submitted-against source and an exact target fingerprint, rather than infer a new target after roadmap content changes. On green, callers can read one validated ledger snapshot with deterministic bytes and can distinguish eligible, stale, and intentionally ineligible items without touching immutable roadmap artifacts.

## Table of Contents

- [Summary](#summary) — Reviewer view of the step’s outcome.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why mutable feedback needs a separate trusted contract.
- [Input](#input) — Existing version and artifact contracts this module reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — New module and test footprint.
- [Implementation](#implementation) — Ledger records, canonical bytes, fingerprints, and eligibility.
- [Tests](#tests) — Focused contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary documentation for serialization and validation choices.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep this a ledger contract.
- [Deferred](#deferred) — Related work owned by later steps.

## Why

Current roadmap feedback lives inside artifacts that later become immutable versions, so reviewer edits and candidate processing share a state surface they must not share. This step establishes one separate, validated ledger contract so later candidate work can snapshot exactly what it saw, reject stale targets without changing reviewer input, and keep `AcceptedRoadmapHead` as the only selector of canonical artifact content.

## Input

- **Immutable-version authority:** Read `plan_tool/roadmap_versions.py:AcceptedRoadmapHead`, `ResolvedRoadmapVersion`, `VERSION_ARTIFACT_INVENTORY`, and `load_accepted_version` as the existing authority for a selected roadmap version. The ledger must refer to version ids without becoming another version selector.
- **Artifact target shape:** Use `plan_tool/roadmap_artifacts.py:FeedbackTarget`, `FeedbackTargetKind`, and the parsed roadmap artifact row identities as the existing artifact-or-row target vocabulary. Do not retain `FeedbackRow` as the ledger’s persisted shape.
- **Canonical source precedent:** Follow the deterministic JSON and SHA-256 behavior in `plan_tool/roadmap_source_identity.py:canonical_projection`, `feedback_snapshot`, and `_json_bytes` where it fits immutable snapshot evidence. The ledger’s human-edited format remains its own contract.
- **Publication boundary:** Later writers must use `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` and its guarded publication path. This step defines values those writers consume; it does not call, replace, or widen that boundary.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_feedback_ledger.py` — Typed mutable-ledger contract, canonical renderer/loader, target fingerprinting, and eligibility helpers.
  - `tests/test_roadmap_feedback_ledger.py` — Contract tests for ledger serialization, source binding, target checks, and eligibility.
- **Existing files (edits only):**
  - None.

## Implementation

- **Make the ledger the only mutable feedback contract introduced here.** Define explicit frozen record types and closed vocabularies in `plan_tool/roadmap_feedback_ledger.py` for the roadmap-scoped ledger, predecessor-grouped reviewer-created items, revision-bound derived context, item targets, proposal fields, and lifecycle states. Reject unknown fields and malformed values before callers can act on them.

- **Keep reviewer-created and roadmap-derived records separate.** Reviewer-created items must carry their stable id, target, request, reviewer-controlled state, submitted-against predecessor version, and admitted target fingerprint. Derived context must remain a separate revision-bound collection that later candidate storage replaces as a whole. Do not represent either collection with `plan_tool/roadmap_artifacts.py:FeedbackRow`, which belongs to the legacy embedded-artifact channel.

- **Preserve stable identity across ordinary mutable state changes.** An item id must remain unchanged when a reviewer defers, closes, reopens, retargets, or edits an item. Model-facing proposal fields are live mutable ledger fields, not immutable history: closing clears them; reopening an ineligible retained item or changing its request or target clears them and restores `open`. Preserve immutable process evidence for later candidate steps rather than adding item-history storage here.

- **Bind a target to its actual source content.** Provide a target-fingerprint helper that derives a stable SHA-256 value from the selected source version, target kind, and the exact artifact or row content addressed by `FeedbackTarget`. An artifact target must bind the selected artifact content; a row target must bind the selected row and fail if that row is absent, duplicated, or not valid for the configured artifact inventory. Do not use text matching, a row name, or a retargeting heuristic as a substitute for this check.

- **Make eligibility fail closed.** Define one shared eligibility predicate for reviewer-created items: it accepts only an `open` item whose submitted-against predecessor is the processing source and whose current target fingerprint exactly matches the target in that source. A missing source, changed fingerprint, invalid target, `awaiting-review`, `deferred`, or `closed` item must be preserved but excluded. Keep the predicate focused on reviewer-created items; later steps select current nondeleted derived context under their separate rule.

- **Render one deterministic reviewer-editable ledger form.** Provide paired parse/load and render operations for the ledger, following the text-versus-path split used by `plan_tool/jira_grade.py:validate_jira_grade_body` and its path-bearing loaders. The renderer must preserve the defined predecessor and item order, emit stable UTF-8 bytes, and reject a noncanonical persisted form on load rather than silently normalizing ambiguous input. Group the human-facing representation by direct predecessor, with the current root/active processing group available for later callers to place first.

- **Use canonical bytes for evidence, not as a global edit lock.** Expose a whole-ledger digest over the canonical rendered bytes and immutable per-item snapshot values for later batch evidence. The item snapshot must include every field that eligibility and later storage need to recheck, including item id, request, lifecycle state, target, predecessor binding, fingerprint, and live proposal values where present. A later unrelated ledger edit must not make a previously captured item snapshot appear changed.

- **Reuse existing authority instead of copying it.** Reuse `plan_tool/roadmap_versions.py:AcceptedRoadmapHead` and the version inventory for version and artifact validation, and reuse `plan_tool/roadmap_artifacts.py:roadmap_dir` for roadmap-scoped paths. Do not add an accepted-head writer, version namespace, candidate pointer, journal, lock implementation, review protocol, or artifact renderer to this module.

- **Define the ledger-state classification and its refusal shape here, not at each caller.** Add a closed `LedgerState` value (`ledger-native` or `migration-pending`) as a durable field of the roadmap-scoped ledger, and a small `check_ledger_processing_ready(...)` helper that reads it and returns either a pass or a deterministic `migration-required` result. This is the "step-1 state contract" step 2 writes at enrollment. Steps 3, 5, and 6 call this helper directly, since each can run before any active candidate exists. Steps 8 and 9 deliberately do **not** call it: an active candidate is proof migration already completed (step 5, via step 3, could not have admitted one for a `migration-pending` roadmap), so their refusal boundary is that upstream invariant, not a second call to the helper. Every one of the five routes still ends up refusing migration-pending state — some by calling the helper, the rest by construction — and no caller invents a second classification or refusal wording.

- **Keep legacy embedded feedback outside this contract.** `plan_tool/roadmap_source_identity.py:feedback_snapshot`, `plan_tool/roadmap.py:recheck_feedback_snapshot`, and `plan_tool/roadmap_candidate_context.py:build_candidate_context` still operate on embedded artifact feedback at HEAD. Leave those consumers unchanged in this step; steps 2 and 3 replace their ordinary processing path after the ledger authority boundary exists.

## Tests

### Tests for this step

- `test_ledger_round_trips_through_one_closed_canonical_schema` — Parsing canonical rendered bytes restores the same ledger, while unknown fields and malformed closed-vocabulary values fail.
- `test_ledger_rejects_noncanonical_serialization` — Semantically similar but noncanonical persisted bytes do not load as trusted ledger state.
- `test_ledger_digest_is_stable_for_unchanged_canonical_bytes` — Equivalent valid ledger values render to the same UTF-8 bytes and SHA-256 digest.
- `test_reviewer_item_id_survives_defer_close_reopen_and_retarget` — Ordinary reviewer lifecycle mutations retain one stable item identity.
- `test_closing_item_clears_live_proposal_fields_and_makes_it_ineligible` — Closing preserves the item but clears proposal data and excludes it from eligibility.
- `test_reopening_awaiting_review_item_clears_live_proposal_and_restores_open` — Reopening a retained ineligible item clears live proposal state and returns it to `open`.
- `test_editing_request_or_target_from_each_retained_ineligible_state_restores_open` — Editing an awaiting-review, deferred, or closed item clears proposal state and restores eligibility state without changing its id.
- `test_target_fingerprint_binds_exact_artifact_or_row_content` — Artifact and row targets produce fingerprints tied to their selected source content.
- `test_target_fingerprint_refuses_missing_or_duplicate_row_target` — A row target without one unambiguous row cannot receive a trusted fingerprint.
- `test_eligible_open_item_requires_matching_predecessor_and_target_fingerprint` — Only an `open` reviewer-created item bound to the processing source and unchanged target is eligible.
- `test_stale_or_ineligible_reviewer_items_are_preserved_and_excluded` — Changed targets and retained lifecycle states stay in the ledger unchanged while the eligibility result excludes them.
- `test_derived_context_is_distinct_from_reviewer_created_items` — Derived records remain revision-bound context and do not become eligible reviewer items.
- `test_item_snapshot_ignores_unrelated_ledger_item_edit` — A captured item snapshot remains equal after another item changes, while the whole-ledger digest changes.
- `test_ledger_path_uses_resolved_plans_dir_and_safe_roadmap_slug` — Ledger path derivation follows the configured plans directory and rejects traversal-bearing slugs.
- `test_check_ledger_processing_ready_refuses_migration_pending_and_passes_ledger_native` — `check_ledger_processing_ready` returns a deterministic `migration-required` result for `migration-pending` state and a pass for `ledger-native` state, from the same shared helper every ledger-lifecycle caller reads.

Green-before-done gate: every test above and `uv run pytest tests/ -q -n auto` must pass.

## Acceptance criteria

- `plan_tool/roadmap_feedback_ledger.py` defines one validated ledger model with separate reviewer-created and revision-bound derived collections.
- A valid ledger renders to deterministic UTF-8 bytes, reloads without loss, and produces a reproducible SHA-256 ledger digest.
- Every reviewer-created item has a stable id, target, request, lifecycle state, submitted-against predecessor, and target fingerprint.
- A row-target fingerprint refuses absent or ambiguous rows; an artifact-target fingerprint binds the selected artifact.
- The shared eligibility predicate returns reviewer-created items only when they are `open`, bind the processing source, and match the current target fingerprint.
- A changed or missing target leaves the item unchanged and ineligible.
- Closing, reopening, retargeting, and request edits preserve the item id and enforce the required proposal-clearing behavior.
- Derived context cannot be mistaken for an eligible reviewer-created item.
- Per-item snapshots remain usable after unrelated ledger edits; the whole-ledger digest records the complete rendered ledger state.
- `check_ledger_processing_ready` is the one shared shape and read path steps 3, 5, and 6 call directly to refuse `migration-pending` state; steps 8 and 9 refuse the same state by construction (no active candidate can exist for a migration-pending roadmap) rather than an independent call. No caller defines a second classification or refusal wording, and every route ends up refusing.
- `tests/test_roadmap_feedback_ledger.py` and the full required test command pass.

## References

- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Use strict, frozen models with forbidden extra fields for persisted ledger and snapshot records.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Use safe loading and controlled dumping for the reviewer-edited ledger representation.
- [json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Use stable JSON options for fingerprint and snapshot preimages.
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Read the canonicalization requirements when defining reproducible evidence bytes.
- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 over the exact canonical byte input.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, ledger ownership:** This step may define mutable reviewer input and its evidence values, but it must not make the ledger canonical artifact content or add an accepted-head writer.
- **The plan’s “## Scope guardrails”, exact batch evidence:** Item and ledger snapshots must preserve exact source, target, and reviewer-input facts for later callers without treating an unrelated live-ledger edit as a batch refusal.
- **The plan’s “## Scope guardrails”, existing publication authority:** Reuse the writer guard and established version, candidate, review, and publication owners. This module must not create a parallel lifecycle or transaction system.
- **The plan’s “## Out of scope”, automatic retargeting:** A changed target must become ineligible until a reviewer explicitly changes the ledger item; this module must not infer a replacement target.
- **The plan’s “## Out of scope”, user interface:** Limit this step to the ledger contract and focused validation helpers. Command wiring and reviewer mutations belong to step 6 and step 10.

## Deferred

- Ledger-native enrollment and explicit import of embedded feedback — Step 2 establishes the enrollment compatibility boundary; step 6 owns idempotent migration and reviewer-facing mutable operations.
- Root-and-active candidate batches and selection of current derived context — Step 3 consumes this step’s eligibility predicate, target fingerprints, and immutable item snapshots.
- Candidate storage transitions that write live proposals and derived context — Steps 4 and 5 own validated responses and guarded candidate publication.
- Rejection, discard, review replacement, and promotion behavior — Steps 8 and 9 own the active-candidate review and accepted-head lifecycle.
