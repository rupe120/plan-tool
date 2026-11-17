# Step 1 — One sibling-path selection helper, captured in the audit snapshot, fingerprint and public revision (v4)

<!-- plan-tool:detail-format-version: 1 -->

## Summary

- Add one helper in `plan_tool/review.py` that returns the same-roadmap sibling `creates:` paths for a plan. It reuses `_eligible_planned_paths` and `_sibling_roadmap_identity` and writes no new selection rule.
- `AuditInputSnapshot.capture` in `plan_tool/review_persistence.py` stores the result once as a sorted-tuple field, and `_audit_input_fingerprint` folds it in only when it is non-empty.
- The public `qualified_result.audit_revision` moves to audit-revision version 4 and gains `sibling_paths_digest`. The validator `normalize_audit_revision` accepts v1–v4.
- On green, a sibling `creates:` edit changes the snapshot fingerprint and the v4 digest, so prior results go stale. Plans with no siblings keep byte-identical fingerprints.

## Table of Contents

- [Why](#why) — what the audit cannot see today
- [Input](#input) — existing contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint
- [Implementation](#implementation) — helper, snapshot, fingerprint, revision v4, docs
- [Tests](#tests) — per-file case roster
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — what this step leaves out

## Why

- The deterministic missing-file check already merges sibling `creates:` through `_eligible_planned_paths`, but the model-driven audit snapshot carries no sibling facts.
- Later steps in the plan deliver the sibling set to the auditor, so the set has to be captured once and pinned. Otherwise a sibling edit between `--iterate` passes would not count as drift, and a saved report would read as current after a sibling changed.
- Capture, fingerprint and public revision are the existing places audit inputs are pinned. The plan seeds `source_seed_digest` (v2) and `project_context_digest` (v3) the same way.

## Input

- **`_eligible_planned_paths(plan, plan_path, repo_root)`** in `plan_tool/review.py`:
  - It returns the plan's own raw `creates:` plus registered sibling paths.
  - It catches `(OSError, UnicodeError, ValueError, ManifestError)` and returns `own`.
  - It also returns `own` when the manifest is not a JSON object.
  - Own paths are kept raw (un-normalized) in its result.
- **`_sibling_roadmap_identity`** in `plan_tool/review.py`:
  - It returns `None` for ordinary non-roadmap plans.
  - It returns `(owner, slug)` for a roadmap plan.
  - It raises `ValueError` for uncertain evidence. A seed that is unreadable or cannot be read as text raises `OSError` or `UnicodeError` from `source.read_text`, which is not wrapped.
- **`_planned_paths(plan)`** in `plan_tool/review.py` returns the plan's own raw `creates:`.
- **`normalize_declared_path`** in `plan_tool/pathutil.py` strips a `(…)` annotation and a leading `./`.
- **Two version numbers must not be confused:**
  - `_AUDIT_REVISION_SCHEMA_VERSION` in `plan_tool/review_persistence.py` is the sidecar schema, already 4, and is not changed here.
  - The `"version"` inside the `audit_revision` dict is separate, currently 3.
  - Only the second moves to 4.
- **Revision producers:** the `"version": 3` literal appears in `plan_tool/fingerprint.py:audit_input_revision` and in the `normalized` dict at the end of `normalize_audit_revision`. Both move to 4.
- **Check limits:** the existing tests use `tmp_path` repos with a manifest. Verify uncertainty cases (unreadable seed, bad identity) with real files, not mocks.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py`:
    - Add the selection helper.
    - Lift the uncertain-evidence exception tuple into one module constant, used by both the helper and `_eligible_planned_paths`. Selection logic is unchanged.
  - `plan_tool/review_persistence.py`:
    - Add the `AuditInputSnapshot` field and the `capture` change.
    - Add the `_audit_input_fingerprint` parameter and its label.
    - Update `normalize_audit_revision`.
  - `plan_tool/fingerprint.py`: `audit_input_revision` emits v4 with `sibling_paths_digest`.
  - `DATA_CONTRACT.md`: three paragraph updates, listed below.
  - `tests/test_review.py` and `tests/test_review_persistence.py`: new cases.
  - `tests/test_fingerprint.py`: **addition to the declared list.** The plan's test duties for v4 live there, and it already holds the `audit_input_revision` tests.

## Implementation

**Helper (`plan_tool/review.py`)**
- Name it something direct, such as `_sibling_creates_paths(plan, plan_path, repo_root) -> frozenset[str]`.
- Flow:
  1. Call `_sibling_roadmap_identity`. If it returns `None`, return an empty set. This is what keeps the all-registered-plans set from being delivered to a plan with no roadmap.
  2. Call `_eligible_planned_paths`.
  3. Subtract own paths by comparing `normalize_declared_path` on both sides, so `./a.py` or `a.py (new)` as a sibling path is excluded when the plan itself creates `a.py`.
- Wrap the whole body in `except` on the shared tuple and return an empty set. No partial set escapes, and `capture` never raises because of sibling selection.
- Rejected alternative: add a roadmap-only argument to `_eligible_planned_paths`. That edits the deterministic check's selection, which the plan's scope fence forbids.
- `_eligible_planned_paths` already swallows its own failures and returns `own`, so the helper's own `try` mainly guards the identity call. Call identity directly, since the helper needs to know whether it is `None`.
- The identity gets computed twice per capture (once here, once inside `_eligible_planned_paths`). Accept it. Passing it in would change that function's signature, which this step does not need.
- Return normalized or raw strings: pick one and keep it consistent for hashing. Recommended: return the sibling's declared strings after dropping own-colliding ones, since later steps render them.

**Snapshot (`plan_tool/review_persistence.py`)**
- Add a field such as `sibling_creates_paths: tuple[str, ...] = ()` to `AuditInputSnapshot`. Store it sorted.
- In `capture`, use a lazy import of the review helper inside the method, as `capture` already does for `resolve_detail_artifact` and `project_profile_context`. `plan_tool/review.py` imports `review_persistence` lazily too, so no import-time edge is added.
- Pass the tuple to `_audit_input_fingerprint` and store it on the instance.

**Fingerprint**
- Add a keyword parameter, default empty, to `_audit_input_fingerprint`.
- When non-empty, add one framed `add("sibling-paths", …)` entry. Join the sorted paths with a separator that cannot occur in a path, such as `\0`, or add one framed entry per path.
- When empty, add nothing, as `project_context` does. Existing fingerprints for plans without siblings stay byte-identical, and the `audit-input-v3` label is **not** changed.
- No caller edit is needed. `audit_input_fingerprint_matches_disk` and `AuditInputSnapshot.matches_disk` recompute through `capture`.

**Public revision v4**
- In `plan_tool/fingerprint.py:audit_input_revision`:
  - Set `"version": 4`.
  - Add `"sibling_paths_digest"`: `None` when the set is empty, else `_audit_input_digest` over the same canonical encoding the fingerprint uses (a sorted, stable join).
  - Read the snapshot field with `getattr(snapshot, "sibling_creates_paths", ())`, because existing tests pass `SimpleNamespace` snapshots.
- In `normalize_audit_revision`:
  - Accept versions `(1, 2, 3, 4)`.
  - For v4, add `sibling_paths_digest` to `expected_keys`, and require `None` or a non-empty string.
  - Fill an absent v1–v3 value with `None`.
  - Emit `"version": 4` in the normalized dict, as the existing v1–v3 path emits 3.
  - Never rewrite an archived sidecar. Reads only.
- Update the docstring that says "Accepts v1 through v3".
- Behavior to expect and keep: on upgrade, a saved v3 record with siblings reads as stale once. This was owner-confirmed 2026-11-17. Ship between Loom batches.
- **Version tolerance lives in the normalizer; no comparison code changes.** All three saved-versus-current comparisons receive a normalized revision: `project_saved_completeness_result` and `completeness_report.py`'s `audit_revision_match` read `SavedReview.qualified_result`, which `load_review` stores as `normalize_qualified_result(...)`; `cli/authoring.py`'s freshness tail calls `normalize_qualified_result` itself. Making `normalize_audit_revision` emit version 4 with `sibling_paths_digest` `None` for a v1–v3 record (above) is what keeps a no-sibling report current. Do not add a comparison helper: it would duplicate the normalizer. If a site is found that compares a raw saved dict, stop and surface it rather than patching it alone.

**`DATA_CONTRACT.md`**
- The paragraph that names `AuditInputSnapshot` as the exact-input source (near the arm-clustering `source_plan_fingerprint` text) names the new captured input.
- The `qualified_result.audit_revision` paragraph names v4 and `sibling_paths_digest` (`null` when no sibling paths apply). It stays accurate that older revisions read missing digests as `null`.
- The "Run-grade-only saved audit evidence" paragraph lists audit-revision versions 1–4 as supported and says `None` for absent v1–v3 `sibling_paths_digest`. Word it as "audit-revision version" so it is not confused with the checkpoint schema's "version-4" sidecars in the same file.

**Constraints**
- Do not alter the missing-file check, `_eligible_planned_paths` selection, or any caller of `_eligible_planned_paths`.
- Do not filter model findings.
- Do not change the `audit-input-v3` fingerprint label or `_AUDIT_REVISION_SCHEMA_VERSION`.

## Tests

**`tests/test_review.py`** (new class beside the existing `_eligible_planned_paths` tests; reuse their roadmap fixtures where they exist)
- `test_sibling_helper_returns_same_roadmap_sibling_paths_and_excludes_own` — two-plan roadmap: the sibling's path is present, own `creates:` are absent.
- `test_sibling_helper_empty_for_no_identity_even_when_other_registered_plans_create_paths` — a plan with no roadmap identity beside registered plans that declare `creates:` returns an empty set, not the all-registered set.
- `test_sibling_helper_excludes_plan_from_a_different_roadmap` — other-roadmap path absent.
- `test_sibling_helper_empty_when_identity_is_uncertain` — an ambiguous or conflicting identity returns an empty set.
- `test_sibling_helper_empty_when_source_seed_is_unreadable_and_does_not_raise` — an unreadable source seed (for example invalid UTF-8) returns an empty set instead of raising. This is the unreadable-seed case beside the uncertain-identity case.
- `test_sibling_helper_own_subtraction_compares_normalized_paths` — a sibling path `./a.py` (or `a.py (new)`) is excluded when the plan creates `a.py`.

**`tests/test_review_persistence.py`**
- `test_changing_a_sibling_creates_changes_the_snapshot_fingerprint` — edit the sibling's `creates:` and recapture.
- `test_unchanged_sibling_set_leaves_the_fingerprint_unchanged` — recapture with no edit gives the same value.
- `test_plan_with_no_siblings_keeps_its_existing_fingerprint` — compare against `_audit_input_fingerprint` called without the new argument. This pins the byte-identical, empty-adds-nothing guarantee.

**`tests/test_fingerprint.py`**
- `test_v4_revision_carries_sibling_paths_digest_null_with_no_siblings`.
- `test_sibling_edit_changes_sibling_paths_digest`.
- `test_v3_record_decodes_with_sibling_paths_digest_none` — follow the existing v2 legacy case that deletes `project_context_digest` in `tests/test_review_persistence.py`.
- `test_saved_v4_record_round_trips_through_normalize_audit_revision`.

**`tests/test_review_persistence.py`** (freshness view)
- `test_saved_v3_report_of_a_plan_without_siblings_stays_current_after_upgrade` — a saved v3 sidecar loaded through `load_review`, whose other fields match the current capture, reads `current`.
- `test_saved_v3_report_of_a_plan_with_siblings_reads_stale_after_upgrade`.
- `test_a_changed_plan_still_reads_stale_after_upgrade` — normalization does not hide a real edit.
- `test_completeness_report_counts_a_saved_v3_no_sibling_report_as_a_plan_match` (`tests/test_completeness_report.py`) — the second comparison site.
- `test_authoring_tail_does_not_report_a_saved_v3_no_sibling_report_as_moved` (`tests/cli/test_authoring_cmds.py`) — the third comparison site.

**Sibling set form**
- The set holds `normalize_declared_path` results, deduplicated and sorted; the snapshot field, the digest and step 2's prompt block all use it.
- `test_sibling_set_normalizes_annotated_and_dot_slash_paths` — a sibling `creates:` of `./src/x.py (new module)` appears once as `src/x.py`.

**Green gate:** every case above must be green, and the existing suite must stay green, before this step is finished. Existing tests that assert `"version": 3` or exact v3 key sets will need updating to v4. That is expected, not a reason to narrow the change.

## Acceptance criteria

- The helper returns the sibling path for a two-plan roadmap fixture, and returns an empty set for the no-identity, different-roadmap and uncertain-identity cases.
- It does not raise for an unreadable source seed.
- A sibling path that normalizes to one of the plan's own `creates:` is excluded.
- Changing a sibling's `creates:` changes `AuditInputSnapshot.fingerprint`; leaving it alone does not.
- A plan with no siblings has the same fingerprint and the same `audit_revision` content (apart from `version` and the added `null` key) as before.
- `audit_input_revision` returns `version == 4` with a `sibling_paths_digest` key. `normalize_audit_revision` accepts v1–v4 and fills `None` for absent v1–v3 values.
- `DATA_CONTRACT.md` names the new input, the v4 digest, and "audit-revision version" 1–4.
- `git diff` shows no change to `_eligible_planned_paths` logic beyond the shared exception tuple, and none to the callers of `audit_input_fingerprint_matches_disk`.

## Applicable guardrails

- **The plan's "## Scope guardrails":** this step adds no new sibling selection rule and does not touch the deterministic missing-file check or its selection. The helper only reuses the existing functions.
- **The plan's "## Out of scope", filtering findings:** this step delivers facts to the snapshot only. It does not inspect or post-process model findings.
- **The plan's "## Audit guardrails":** a roadmap-plans-only set. Plans without a roadmap identity get an empty set, and an ambiguous identity yields an empty set rather than a wider selection.

## Deferred

- Rendering the sibling set into `plan_tool/prompts/plan-audit.md` and its empty-state statement — a later step of this plan owns the prompt change.
- Removing the triage note in `integrations/shared/DIRECTIVES.md` § "T — tool artifacts" — owned by the plan's docs step.
- Folding the repeated identity computation into one call — not needed for this step's outcome; it would change `_eligible_planned_paths`'s signature.
