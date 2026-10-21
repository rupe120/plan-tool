> **Withdrawn 2026-08-11** — Withdrawn after the detail-stage audit exposed an unresolved high-severity provenance-ordering defect and non-convergent correctness contracts; re-seed the capability from the audited invariants before implementation.
> Preserved here for history; do not edit.

# Step 4 — Extract the shared fuzzy-title comparison

## Summary

Extract `_matches`’ existing tier-3 title comparison into a private shared predicate in `plan_tool/convergence_diagnosis.py`, then make `_matches` call it as its last fallback. Keep the current title normalization, `SequenceMatcher` comparison, and `TITLE_SIMILARITY_CUTOFF` unchanged. Update `tests/test_convergence_diagnosis.py` to pin the extracted predicate and the tier ordering around it. On green, current convergence matching returns the same results while Step 5 has one title-only comparison it can reuse.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the behavior-preserving extraction.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why the title comparison needs a single boundary before bad-fix work.
- [Input](#input) — Existing matching contracts and consumers the refactor preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two in-scope code and test files.
- [Implementation](#implementation) — The shared predicate and unchanged matcher tiers.
- [Tests](#tests) — Focused regression coverage for the extracted comparison.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Standard-library behavior behind the comparison.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this refactor.
- [Deferred](#deferred) — Later identity and telemetry work left out of this step.

## Why

`plan_tool/convergence_diagnosis.py:_matches` currently embeds its fuzzy-title fallback, so Step 5 could only reuse it by copying the normalization, ratio, and cutoff rule or by adopting `_matches`’ deliberately broad step-focus behavior. Extracting only the title predicate gives the later same-issue matcher a narrow shared rule without changing the recurrence and edit-drift matchers that already depend on `_matches`.

## Input

- **Tiered matcher contract:** `plan_tool/convergence_diagnosis.py:_matches` first decides on `_finding_step_focus`, then equal anchors when neither finding has a focus, and only then compares titles. `classify_edit_drift` and `classify_impact_recurrence` rely on that ordering.

- **Title comparison contract:** `plan_tool/convergence_diagnosis.py:_title_slug`, `_title_ratio`, and `TITLE_SIMILARITY_CUTOFF` define the current tier-3 result. Keep their meaning and cutoff source unchanged.

- **Finding shape:** `plan_tool/convergence_diagnosis.py:RunFinding.title` is the only finding field the extracted predicate needs. Do not add body-based identity or change flattened history in this refactor.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add the shared fuzzy-title predicate and route `_matches`’ tier-3 fallback through it without changing the earlier tiers.
  - `tests/test_convergence_diagnosis.py` — add direct coverage for the predicate and retain regression coverage for `_matches` tier precedence.

## Implementation

- **Foundational logic: compare two finding titles with the existing fuzzy fallback.** Add a private boolean predicate beside `plan_tool/convergence_diagnosis.py:_title_slug` and `_title_ratio`; `_fuzzy_title_match(left_title, right_title)` is a suitable name. Accept raw title text so every caller gets the same normalization as today.

- **Preserve the exact tier-3 rule.** Normalize each title through `_title_slug`, calculate the ratio through `_title_ratio`, and compare it with `>= TITLE_SIMILARITY_CUTOFF`. Do not change the cutoff, matching algorithm, normalization rules, or empty-title behavior.

- **Keep `_matches` tier ordering unchanged.** Replace only its inline tier-3 expression with the shared predicate. `_finding_step_focus` remains the first decisive tier; equal non-empty anchors remain the second immediate match; unequal anchors still reach the title fallback exactly as they do now.

- **Do not turn the helper into whole-finding identity.** The helper must not read `step_id`, `anchor`, `id`, source, severity, or annotations. Step 5 owns the dedicated same-issue predicate that combines this title-only fallback with stricter identity signals.

- **Retain the existing low-level helpers.** `plan_tool/telemetry_analysis.py:_strict_finding_match` directly uses `plan_tool/convergence_diagnosis.py:_title_slug`, `_title_ratio`, and `TITLE_SIMILARITY_CUTOFF`. Leave those symbols available and unchanged.

- **Reject broader matcher extraction.** Do not refactor `_matches`’ focus or anchor tiers, change `RunFinding`, or alter either `classify_edit_drift` or `classify_impact_recurrence`. This step is the behavior-preserving boundary before the advisory feature.

## Tests

### Tests for this step

- `tests/test_convergence_diagnosis.py:test_fuzzy_title_match_normalizes_titles_and_applies_cutoff` — assert case and punctuation normalization still feeds the same near-title match and far-title rejection at `TITLE_SIMILARITY_CUTOFF`.

- `tests/test_convergence_diagnosis.py:test_match_tier3_title_similarity_cutoff` — verify `_matches` still matches and rejects the existing near and far title pairs through its last fallback.

- `tests/test_convergence_diagnosis.py:test_match_tier1_step_focus_authoritative` — keep proving equal step focus wins over unrelated titles and differing step focus remains decisive.

- `tests/test_convergence_diagnosis.py:test_match_tier2_anchor_equality` — keep proving equal anchors match before title comparison and distinct anchors can continue to the title fallback.

Every listed test must be green before this step is considered finished.

## Acceptance criteria

- `_fuzzy_title_match` returns the same boolean as the former `_matches` tier-3 expression for normalized near and far title pairs.

- `plan_tool/convergence_diagnosis.py:_matches` delegates only its final title fallback to the shared predicate.

- `_matches` retains its current step-focus and anchor behavior, including its existing fallback from unequal anchors to title comparison.

- `plan_tool/convergence_diagnosis.py:_title_slug`, `_title_ratio`, and `TITLE_SIMILARITY_CUTOFF` retain their current behavior and remain available to existing consumers.

- All tests listed in `## Tests` are green.

## References

- [Python difflib — `SequenceMatcher`](https://docs.python.org/3/library/difflib.html#difflib.SequenceMatcher) — Review the ratio behavior that the retained fuzzy-title rule uses.

## Applicable guardrails

- **The plan’s “## Plan intent”, causal-evidence boundary** — prepare title identity reuse only; do not add a bad-fix conclusion or any operator-facing advisory.

- **The plan’s “## Step intent”, tier-3-only extraction** — move only the existing fuzzy-title comparison and preserve every current `_matches` result.

- **The plan’s “## Out of scope”, existing matcher semantics** — leave step-focus behavior for edit-drift and impact-recurrence unchanged.

- **The plan’s “## Out of scope”, identity-matcher boundary** — do not introduce body similarity, free-form prose grading, or a second matching policy in this step.

## Deferred

- **Dedicated same-issue identity and bad-fix advisory** — Step 5 owns the stricter multi-signal matcher, provenance join, rendering, and recommend-only output.

- **Telemetry adoption of the extracted predicate** — `plan_tool/telemetry_analysis.py:_strict_finding_match` has its own strict identity rules and is outside this step’s declared files; assess any consolidation with its dedicated tests in a later reconcile step.
