> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Keep marked checkpoints out of reusable audit lookup

## Summary

Update `plan_tool/completeness_report.py:resolve_reusable_audit` and its focused tests in `tests/test_completeness_report.py`. Reuse lookup must select only loaded `SavedReview.kind="completeness"` sidecars with the ordinary-final role supplied by steps 1 and 2. A confirmed checkpoint, an unknown checkpoint role, or a filename/payload kind mismatch is not a stale audit; it is not a reuse candidate at all. On green, the newest eligible final sidecar remains reusable, while a marked checkpoint cannot be selected by default or by an explicit reuse ID.

## Table of Contents

- [Summary](#summary) — Scope and green result.
- [Table of Contents](#table-of-contents) — Section guide.
- [Why](#why) — Why checkpoint sidecars cannot enter audit reuse.
- [Input](#input) — Persisted role and existing lookup contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Safe sidecar-selection rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — JSON and pytest references for the persisted-role cases.
- [Applicable guardrails](#applicable-guardrails) — Scope and compatibility boundaries.
- [Deferred](#deferred) — Related reader work owned by later steps.

## Why

`plan_tool/completeness_report.py:resolve_reusable_audit` currently narrows by the `-completeness.json` filename and selects the newest match. Step 2 makes a pre-apply checkpoint look the same by name and kind as a final report, even though it captures findings before the apply work completes. If that checkpoint is fresh by fingerprints, the next completeness audit could reuse partial evidence instead of running a new audit or using the last completed one.

## Input

- **Saved-review role from step 1:** `plan_tool/review_persistence.py:SavedReview` exposes the normalized `is_pre_apply_checkpoint` role. Only the ordinary-final role is safe for reuse; confirmed checkpoints and unknown metadata are not.

- **Checkpoint producer from step 2:** `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` writes the version-3 confirmed checkpoint role through `plan_tool/completeness_report.py:write_completeness_report`. Ordinary final sidecars remain unmarked at their current versions under the step 1 compatibility policy.

- **Existing lookup contract:** `plan_tool/review_persistence.py:list_saved_reviews` returns paths newest first, while `plan_tool/completeness_report.py:resolve_reusable_audit` uses the `-completeness.json` suffix as a locator and supports both default selection and a bare or full `review_id` stem. The suffix does not prove the loaded payload's `kind`.

- **Caller behavior:** `plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse` already treats a `None` lookup result as a fresh audit. Keep that caller contract unchanged.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — select reusable completeness sidecars by their loaded checkpoint role before computing the existing freshness verdict.
  - `tests/test_completeness_report.py` — cover ordinary-final, checkpoint, unknown-role, and pinned-ID selection cases.

## Implementation

- **Foundational logic:** select only ordinary-final completeness sidecars for audit reuse.

- **Read the normalized role and payload kind.** Update `plan_tool/completeness_report.py:resolve_reusable_audit` to decide eligibility from the `SavedReview` returned by `plan_tool/review_persistence.py:load_review`: it must require `kind="completeness"` and the ordinary-final role. Do not trust filenames, timestamps, report content, or fingerprint values as evidence of either condition.

- **Fail closed for unsafe roles and kinds.** A confirmed version-3 pre-apply checkpoint, the unknown role defined by step 1 — including malformed, misplaced, role/version-mismatched, and marker-less version-3 sidecars — and a loaded non-completeness sidecar must all be skipped. Treat only a `kind="completeness"` ordinary-final role, including unmarked version-1/2 legacy sidecars and raw version-3 `false`, as eligible.

- **Keep newest-final selection.** For an unpinned lookup, preserve `plan_tool/review_persistence.py:list_saved_reviews` newest-first order and continue past newer unsafe sidecars to the newest eligible final sidecar. If none remains, return `None`.

- **Keep pinned selection exact.** Apply `review_id` narrowing before kind and role selection. If the requested sidecar is a checkpoint, has an unknown role, or has a non-completeness payload kind, return `None`; do not substitute an older final sidecar for an explicit ID.

- **Preserve the existing verdict work.** Once an eligible sidecar is selected, keep `plan_tool/completeness_report.py:ReusableAudit`, plan and code fingerprint comparison, coverage projection, and recommendation-axis splitting unchanged. An unsafe sidecar must be excluded rather than returned as a stale `ReusableAudit`.

- **Use the persistence seam.** Continue to use `plan_tool/review_persistence.py:list_saved_reviews` and `plan_tool/review_persistence.py:load_review`. Do not add raw JSON parsing, a second directory scan, or a filename convention for checkpoints.

- **Keep this reader-only.** Do not change `plan_tool/completeness_report.py:write_completeness_report`, saved-review schema handling, report filenames, or `plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse`.

## Tests

Every test below must be green before this step is complete.

### Tests for this step

- `test_resolve_reusable_audit_fresh` — retain the ordinary unmarked version-1/2-final case and confirm it remains eligible and fresh.

- `test_resolve_reusable_audit_v3_explicit_false_is_eligible` — a loaded version-3 completeness sidecar with the explicit ordinary-final role remains reusable.

- `test_resolve_reusable_audit_skips_newer_marked_checkpoint` — a newer checkpoint does not displace an older fresh final sidecar.

- `test_resolve_reusable_audit_skips_unknown_checkpoint_role` — a newer sidecar with invalid, misplaced, role/version-mismatched, or marker-less-version-3 metadata is not trusted for reuse, and an older final remains selectable.

- `test_resolve_reusable_audit_skips_filename_kind_mismatch` — a loadable non-completeness sidecar with a `-completeness.json` filename is not reused by default and a pinned ID for it returns `None` without fallback.

- `test_resolve_reusable_audit_pinned_unsafe_sidecar_returns_none` — a bare and full pinned ID for a checkpoint or unknown-role sidecar returns `None` without falling back to another report.

## Acceptance criteria

- `plan_tool/completeness_report.py:resolve_reusable_audit` returns the newest `kind="completeness"` ordinary-final sidecar when newer checkpoint, unknown-role, or filename/kind-mismatched sidecars exist.

- A marked checkpoint, an unknown-role sidecar, and a filename/kind-mismatched sidecar never produce a `ReusableAudit`, even when their plan and code fingerprints match.

- An explicit `review_id` for an unsafe role or payload kind returns `None` and does not select another sidecar.

- Unmarked version-1/2 legacy sidecars and raw version-3 explicit ordinary-final roles remain eligible for the existing freshness checks.

- `pytest tests/test_completeness_report.py` passes.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Review the JSON type distinctions behind the persisted checkpoint-role cases.

- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use a compact matrix for pinned unsafe-role cases.

## Applicable guardrails

- **Durable recovery evidence:** the plan’s “## Plan intent” means this step leaves checkpoints persisted and readable; it only removes them from reusable-audit selection.

- **Focused reader change:** the plan’s “## Step intent” limits the change to preventing partial checkpoints from supplying the next completeness audit.

- **Path compatibility:** the plan’s “## Out of scope”, report naming and filename compatibility, keeps report locations and timestamped sidecar names unchanged.

- **Historical compatibility:** the plan’s “## Out of scope”, historical sidecars, keeps legacy unmarked final sidecars in place without migration or rewriting.

- **Reader boundary:** the plan’s “## Out of scope”, allowed reader changes, keeps the work to checkpoint-role filtering and preserves the existing reuse and freshness policy otherwise.

## Deferred

- Convergence-history filtering in `plan_tool/convergence_diagnosis.py:load_report_history` — step 4 owns the corresponding exclusion from cross-run snapshots.

- Removal of the positional checkpoint handling in `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis` — step 5 owns replacement after shared history filtering exists.

- Saved-review migration or deletion — outside the plan’s compatibility boundary.
