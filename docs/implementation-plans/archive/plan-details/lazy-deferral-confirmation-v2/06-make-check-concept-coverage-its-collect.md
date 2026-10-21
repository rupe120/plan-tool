# Step 6 — Make `check_concept_coverage` validate a guide post's scoped bucket anchor and never crash on a bucket-level mismatch

## Summary

Teach `plan_tool/review.py:check_concept_coverage` about the guide-post record shape so the completeness/coverage audit stops relying on the whole-bundle fingerprint and instead validates each guide post against its own **scoped bucket anchor** (step 1's `compute_bucket_anchor`, over the current bucket text — the same recipe step 4 wrote and step 5 re-drills). Two behaviors change: (1) an approved guide-post deferral whose stored `bucket_anchor` matches its current bucket text counts as a valid accounting link (no `concept-coverage` medium finding), alongside the existing committed-owner / `wont_do` / structured-detail-deferral paths; (2) the whole function becomes total — it never raises for any on-disk record shape (guide-post, legacy stale full-tree, malformed) or any plan-body state (bucket renamed, deleted, or empty). The only files touched are `plan_tool/review.py` and `tests/test_review.py`; the two in-file `collect_*` callers (`collect_smell_findings`, `collect_self_consistency_findings`) inherit the totality unchanged, and the out-of-file completeness caller inherits it too. On green, a plan edited since a deferral was recorded no longer crashes the audit and no longer produces a spurious blocking finding, while pending guide posts still surface the existing `concept-unsigned-deferral` info reminder.

## Table of Contents

- [Why](#why) — what the bundle-wide guard breaks in the audit and what the scoped anchor fixes
- [Input](#input) — the guide-post loader, the anchor primitive, and the extraction recipe this consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits
- [Implementation](#implementation) — the crash guard, the scoped-anchor accounting path, and the constraints that must hold
- [Tests](#tests) — unit cases added with the code
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — hashlib, pytest
- [Deferred](#deferred) — what this step leaves to other steps or the backlog

## Why

`check_concept_coverage` calls `load_concepts(plan_path, compute_plan_fingerprint(plan_path))` with no `try/except`, then reasons about approved concepts. After step 2, `load_concepts` skips the whole-bundle staleness check for guide-post records but still raises `StaleConceptTreeError` for a legacy `full-tree` record whose bundle fingerprint drifted, and `InvalidConceptTreeError` for a malformed record — both propagate out of `check_concept_coverage` and crash the audit and every `collect_*` caller. Worse, the audit has no idea how to account for a guide-post deferral: those are signed off by `scope-review` (step 5) but carry no `detail_deferral_step_ids` step link, so `_structured_concept_deferral_is_valid` returns `False` and the audit would falsely emit a blocking `concept-coverage` medium finding for a concept the operator already deferred. This step is the read/confirm caller step 2's Deferred section pointed to for `check_concept_coverage`: it validates a guide post against its own bucket's scoped anchor instead of the whole bundle, so a deferral recorded before later unrelated edits is still accounted for — and it makes the audit degrade gracefully instead of dead-ending on staleness (plan design point **B**).

## Input

This step consumes three upstream contracts; correctness rests on each staying shaped as expected:

- **Step 2's guide-post record shape and loader** (`plan_tool/concept_tree.py`): `ConceptNode.bucket` / `ConceptNode.bucket_anchor`, `ConceptTree.record_kind`, and the `load_concepts(plan_path, expected_plan_fingerprint)` seam whose staleness rule branches on the decoded record kind. For a `record_kind == "guide-post"` record it returns without raising `StaleConceptTreeError` even when the bundle fingerprint differs; for a legacy `full-tree` record it still raises `StaleConceptTreeError` on a mismatch, and `InvalidConceptTreeError` on a malformed record. This step keeps passing `compute_plan_fingerprint(plan_path)` (the guide-post loader ignores it) and wraps the call to catch both exceptions.
- **Step 1's `plan_tool/review_persistence.py:compute_bucket_anchor(bucket, bucket_source_text) -> str`** — the deterministic 64-char digest. It is total (never raises, returns a stable digest even for empty text), so a missing/renamed bucket yields a digest that simply won't match rather than an error. This step re-computes it and compares against the stored `bucket_anchor`; it never writes.
- **The shared extraction recipe from step 4 (producer) / step 5 (consumer).** A guide post's `bucket` is the normalized plan body section name and its source text is that section's body. This step must re-extract the **identical** slice under the **identical** label, or the round-trip anchor comparison reports a false change. Cite step 4's producer recipe and step 5's `scope-review` re-drill; do not re-specify or hand-roll the extraction.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — in `check_concept_coverage`: wrap the `load_concepts` call so `InvalidConceptTreeError` / `StaleConceptTreeError` return `[]` (inert, matching the absent-record contract); add a scoped-anchor accounting path for guide-post deferrals; drill the current plan body once for the anchor comparison. No signature change. `collect_smell_findings` and `collect_self_consistency_findings` are unchanged (they inherit the totality) — verify, don't edit.
  - `tests/test_review.py` — add the guide-post fixture and the new cases in `TestConceptCoverage` (or a sibling `TestConceptCoverageGuidePost` class).

## Implementation

- **Make `check_concept_coverage` total — it must never raise.** Wrap the `load_concepts(...)` call in `check_concept_coverage` in `try/except (InvalidConceptTreeError, StaleConceptTreeError): return []`. A legacy stale full-tree record and a malformed record both become inert, the same way an absent record already is. Import the two exception classes alongside the existing `from plan_tool.concept_tree import concepts_path, load_concepts` (function-local, matching the current local import style in this function). This is the direct fix for "never crash": the guard mirrors step 5's `scope-review` handling of the same two exceptions.
- **Add a scoped-anchor accounting path for guide-post deferrals.** In the approved-node branch, an approved concept is currently accounted by `node.id in committed_concept_ids`, `node.decision == "wont_do"`, or `_structured_concept_deferral_is_valid(node, plan)`. Add a fourth OR-ed condition: a valid guide-post deferral — a node carrying a non-empty `bucket` and `bucket_anchor` whose stored `bucket_anchor` matches `compute_bucket_anchor(node.bucket, current_bucket_text)`, where `current_bucket_text` is that bucket's body in the current plan. Gate the path on `node.bucket` being non-empty so legacy full-tree nodes (empty bucket) never take it — this keeps the change additive and avoids needing `record_kind` here. Keep `_structured_concept_deferral_is_valid` intact: detail-authored deferrals (step 4's `detail_deferral_step_ids`) stay valid through that path; the new path is for `scope-review`-signed guide posts that have no step link.
- **Drill the current plan body once, near the top of the function.** Read `plan_path.read_text(encoding="utf-8")`, split off the frontmatter, and build a `name -> body` map. `review.py` already imports `split_body_sections` and `_split_frontmatter` from `plan_tool.parser`; `split_body_sections(_split_frontmatter(plan_text).body)` produces exactly the normalized section keys and bodies step 5's `parse_body_sections`/`BodySection.name` recipe produces — reuse it rather than minting a new extraction. Look up each guide post's text with `sections.get(node.bucket, "")`. A missing key yields `""`, and `compute_bucket_anchor` over `""` is a stable non-matching digest — no crash. If `plan_path.read_text` fails (`OSError`), treat sections as empty and continue; the function still returns and never raises.
- **A bucket-level mismatch must not become a new blocking finding.** When a signed-off guide post's anchor does not match (the bucket text drifted, or the section is gone), do not emit a `concept-coverage` medium finding for it and do not invent a new source. `scope-review` (step 5) is the only surface that re-confirms/re-anchors a guide post; a `concept-coverage` medium is in `SELF_CONSISTENCY_SOURCES` and would block the `--iterate` loop forever on a finding the loop cannot resolve (the "surface, never block" rule for operator-only-resolvable findings). **One way** that satisfies this cleanly: treat a well-formed signed-off guide-post deferral (non-empty `bucket`/`bucket_anchor`) as accounted regardless of whether the current bucket text still matches — the sign-off is durable and drift is self-healing via `scope-review` — so the anchor recompute is primarily the never-crash / bucket-exists check. The implementer has latitude here; the hard constraints are only that a mismatch (a) never raises and (b) never produces a blocking `concept-coverage` finding.
- **Leave the pending (unreviewed) guide-post path unchanged.** A node with `review_state != "approved"` and `decision in {"defer", "wont_do"}` still emits the `concept-unsigned-deferral` info reminder exactly as today. `check_concept_coverage` stays the single owner of that predicate — do not duplicate it.
- **The `collect_*` callers need no edits.** `collect_smell_findings` and `collect_self_consistency_findings` already pass `plan_path` and call `check_concept_coverage`; once the detector is total they are crash-free, and `collect_self_consistency_findings` (which filters to `CONCEPT_COVERAGE_SOURCE`) stays quiet for anchor-accounted guide posts. The completeness caller at `plan_tool/cli/completeness_phases.py:audit_detail_bundle_status`'s report assembly (the `check_concept_coverage(...)` call filtered to `"concept-coverage"`) is out of this step's file scope and also inherits the totality — no edit there, and this is the "single detector owns the predicate" design, not an omission.

## Tests

New unit tests in `tests/test_review.py` (add a `_write_guide_post_fixture` helper that writes a plan with a `## <Section>` body and a `ConceptNode` carrying `bucket` = that normalized section name and `bucket_anchor` = `compute_bucket_anchor(bucket, section_body)`). Each new test must be green before this step is done.

- `test_guide_post_anchor_match_accounts_for_concept` — approved guide-post deferral whose stored anchor matches the current bucket text → `check_concept_coverage` returns `[]` (no `concept-coverage` finding).
- `test_guide_post_bucket_mismatch_does_not_crash_or_block` — approved guide post, then edit the plan body so the bucket text changes → the call returns without raising and emits no `concept-coverage` medium finding.
- `test_missing_bucket_section_does_not_crash` — approved guide post whose `## <Section>` was deleted/renamed → no crash, no blocking finding.
- `test_legacy_stale_full_tree_record_is_inert` — a `record_kind="full-tree"` record whose stored `plan_fingerprint` no longer matches (so `load_concepts` raises `StaleConceptTreeError`) → `check_concept_coverage` returns `[]` instead of raising.
- `test_malformed_record_is_inert` — a concepts.json that decodes to `InvalidConceptTreeError` → returns `[]` instead of raising.
- `test_pending_guide_post_still_surfaces_unsigned_advisory` — unreviewed guide post → still exactly one `("concept-unsigned-deferral", "info")` rec, no crash.
- `test_collectors_stay_crash_free_on_guide_post` — `collect_smell_findings` and `collect_self_consistency_findings` over a guide-post record neither raise nor emit a `concept-coverage` finding for an anchor-accounted concept.

## Acceptance criteria

- `check_concept_coverage(plan, plan_path, plan_name=...)` returns a `list[Recommendation]` and raises nothing for: a matching guide post, a drifted-bucket guide post, a deleted-bucket guide post, a stale legacy full-tree record, and a malformed record.
- An approved guide-post deferral whose `bucket_anchor` matches `compute_bucket_anchor(bucket, current_bucket_text)` produces no `concept-coverage` finding.
- A bucket-level anchor mismatch produces no `concept-coverage` finding and no new finding source.
- An unreviewed guide post still produces exactly one `concept-unsigned-deferral` info reminder.
- `collect_smell_findings` and `collect_self_consistency_findings` do not raise on a guide-post record.
- All new tests in `tests/test_review.py` pass; the existing `TestConceptCoverage` cases (committed owner, structured deferral, `wont_do`, missing-owner, non-committed owner, stable finding id, missing record) still pass.
- `uv run pytest tests/test_review.py -q` is green.

## References

- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — the SHA-256 construction behind `compute_bucket_anchor`, whose totality lets the mismatch path never raise.
- [pytest — How to use temporary directories and files](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture used to write the hermetic guide-post / stale-record / malformed-record cases.

## Deferred

- **Anchor re-write / re-confirm of a drifted guide post** — this step only reads and never mutates the record; re-anchoring a drifted guide post and re-rendering `## Deferred` is `scope-review`'s job (step 5).
- **Consolidating the `detail_deferral_step_ids` reader onto `concept_sync`'s public reader** — `_structured_concept_deferral_is_valid` still parses that key independently; unifying it is a reconcile-owned follow-up, not this step (noted in step 4's cross-step lesson).
- **The `plan_tool/cli/completeness_phases.py` caller** — out of this step's declared file scope; it inherits `check_concept_coverage`'s totality and needs no edit, so no code change there.
