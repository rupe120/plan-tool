> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Make `check_concept_coverage` total and surface a decision record whose bucket no longer exists for re-review

## Summary

Harden `plan_tool/review.py:check_concept_coverage` so it never crashes and so it handles the new flat decision record from step 1. Two changes: (1) wrap the `load_concepts` call so it never crashes `status`, the completeness audit, or the `--iterate` gate — but distinguish the cases so a legacy record's findings are not silently lost (dual-mode, plan Architecture H): a **malformed** record (`InvalidConceptTreeError`) returns `[]` (truly unreadable), while a **stale legacy full-tree** record (`StaleConceptTreeError`, which only the legacy kind raises — step 1 skips the guard for flat records) surfaces **one non-blocking advisory** telling the operator the legacy record is fingerprint-drifted and needs re-sync to re-check coverage, rather than silently swallowing its (possibly blocking) findings to `[]`; (2) for a `record_kind="decision-record"` node, check whether its coarse `bucket` still resolves to a current plan body section and, when it doesn't, emit one **non-blocking** `concept-bucket-missing` finding that surfaces the record for operator re-review. The key design decision is that a confirmed (approved) flat `defer`/`wont_do` decision is itself the accounting, so it never produces the blocking `concept-coverage` finding — only bucket-existence and the existing unsigned-deferral reminder apply to flat records. On green, a stale/malformed `concepts.json` yields no exception anywhere, a flat record with a deleted section surfaces a non-blocking re-review finding, and legacy full-tree coverage behavior is unchanged.

## Table of Contents

- [Why](#why) — the load guard crashes the read paths and the flat record has no coverage handling
- [Input](#input) — step 1's flat decision-record shape and the body-section name lookup this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — one code file, one test file
- [Implementation](#implementation) — make the load total, branch on record kind, add the bucket-existence detector
- [Tests](#tests) — totality, bucket-gone surfacing, non-blocking, legacy unchanged
- [Acceptance criteria](#acceptance-criteria) — observable behaviors on green
- [References](#references) — dataclasses / json / pytest docs
- [Deferred](#deferred) — scope-review's parallel bucket check, step-5 surfacing, dismiss verb

## Why

`check_concept_coverage` calls `load_concepts(plan_path, compute_plan_fingerprint(plan_path))` with no guard. After step 1, a legacy full-tree record still raises `StaleConceptTreeError` on a fingerprint mismatch, and a malformed record raises `InvalidConceptTreeError` — either one crashes `status`, the completeness audit, and the `--iterate` gate through the `collect_smell_findings` / `collect_self_consistency_findings` callers. A pending deferral is confirmed *after* edits by design, so any crash on a "changed since written" record defeats the whole lazy model. Separately, the function has no handling for step 1's flat `decision-record` kind: run today's approved-node branch on a flat `defer` node and it falls through to the blocking `concept-coverage` finding (no committed owner, not `wont_do`, no structured `detail_deferral_step_ids`), which would wedge the `--iterate` loop on a confirmed decision. This step makes the detector total and teaches it the flat record's only validity question — does the `bucket` still exist — surfacing a gone bucket for re-review instead of crashing or silently standing.

## Input

This step reads step 1's outcome, not its mechanism:

- **Flat decision record (step 1).** Step 1 added `ConceptTree.record_kind` (defaults to the legacy `"full-tree"` literal; the flat kind is `"decision-record"`) and `ConceptNode.bucket` (defaults `""`). A flat node carries a non-empty `bucket`, empty `parent_path`, and a `decision` of `defer`/`wont_do`. Depend on those field names and defaults; do not restate step 1's decoder/validator work.
- **Load seam (step 1).** `plan_tool/concept_tree.py:load_concepts` skips the `StaleConceptTreeError` fingerprint check for the flat kind but still raises it for legacy full-tree records and raises `InvalidConceptTreeError` on a malformed record. This step wraps the call to absorb both.
- **Body-section name lookup — must match step 4 exactly.** The `bucket` is a coarse section-level tag equal to the normalized H2 section name (lowercased, trailing `:`/`.` stripped) that `bootstrap_concepts` used as the node title. "Bucket still exists" is a name lookup against `{section.name for section in parse_body_sections(split_plan_document(plan_path.read_text()).body)}` — the **identical** `parse_body_sections` normalization step 4's confirm-time bucket check uses, so a record can never be surfaced-missing by one and resolved-fine by the other (the `bucket-existence-lookup-consistency` risk). No hash, no fingerprint. If the lookup is worth a shared helper, both steps import it from one place rather than re-normalizing.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add a `CONCEPT_BUCKET_MISSING_SOURCE` constant beside `CONCEPT_COVERAGE_SOURCE` / `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` (and a `CONCEPT_LEGACY_STALE_SOURCE` for the re-sync advisory); wrap the `load_concepts` call in `check_concept_coverage` so `InvalidConceptTreeError` returns `[]` and `StaleConceptTreeError` (legacy only) returns one non-blocking `concept-legacy-stale` advisory (kept out of `SELF_CONSISTENCY_SOURCES`); branch the per-node loop on `concept_tree.record_kind` so decision-record nodes get the bucket-existence check and never emit the blocking `concept-coverage` finding, and full-tree nodes keep their existing coverage behavior unchanged.
  - `tests/test_review.py` — add totality, bucket-missing, non-blocking, and legacy-unchanged cases (extend `TestConceptCoverage` and its `_write_concept_coverage_fixture` helper, or add a flat-record sibling fixture).

## Implementation

**Make the load total — but distinguish malformed from stale-legacy (dual-mode).** Wrap the `load_concepts(plan_path, compute_plan_fingerprint(plan_path))` call in `check_concept_coverage` in a `try/except`. Import `InvalidConceptTreeError` / `StaleConceptTreeError` from `plan_tool.concept_tree` in the same function-local import that already pulls `concepts_path` / `load_concepts`. Handle the two cases differently:
- `InvalidConceptTreeError` (malformed, truly unreadable) → `return []`, matching the absent-record contract (the `if not concepts_path(...).is_file(): return []` and `if concept_tree is None: return []` guards already there).
- `StaleConceptTreeError` (only a legacy full-tree record raises it — step 1 skips the guard for flat records) → `return [<one non-blocking concept-legacy-stale advisory>]`, **not** `[]`. Its data is still there; a legacy record whose fingerprint drifted may carry unresolved *blocking* coverage findings, so swallowing to `[]` would hide them from `status`, the audit, and the `--iterate` gate. The advisory (source `CONCEPT_LEGACY_STALE_SOURCE`, kept out of `SELF_CONSISTENCY_SOURCES`) tells the operator the legacy record needs re-sync (`scope-review`) to re-check coverage.

Both exception classes still matter: catching only one leaves a live crash path.

- **Why an advisory (not `[]`) for a stale legacy record:** its findings might be *blocking*, so silently going inert would hide them (the `[legacy-stale-resync]` regression). Surface one non-blocking "needs re-sync" advisory instead — the operator is told the record is drifted and can re-confirm via scope-review (step 4). A **malformed** record, by contrast, is genuinely unreadable → `[]`.

**Branch the per-node handling on `concept_tree.record_kind`.** Keep the current logic exactly for `"full-tree"`. For `"decision-record"` nodes, the "signed-off concept has no accounting link" rule does not apply — a confirmed `defer`/`wont_do` decision *is* the accounting. The hard constraint:

- **A confirmed (approved) flat decision must never emit the blocking `concept-coverage` finding.** That finding is in `SELF_CONSISTENCY_SOURCES` and blocks at medium; firing it on a confirmed deferral would wedge the `--iterate` loop on something only an operator `scope-review` can clear. One clean way: for a decision-record node, treat an approved `defer`/`wont_do` with an existing bucket as accounted (no finding) and skip the committed-owner / structured-deferral checks entirely.

**Add the bucket-existence check for decision-record nodes.** Build the current body-section name set once, then for each decision-record node compare `node.bucket` against it:

- **Recommended derivation (reuse, don't hand-roll):** `sections = split_body_sections(_split_frontmatter(plan_path.read_text(encoding="utf-8")).body)` — both symbols are already imported at the top of `plan_tool/review.py`, so no new import. The bucket exists iff `node.bucket in sections`. This must match step 4's lookup exactly (same helper, same normalized key) or the two sites disagree on what "exists" means.
- **Missing bucket → surface for re-review, but only while unreviewed.** Emit one `Recommendation` with `source=CONCEPT_BUCKET_MISSING_SOURCE`, a below-threshold severity (recommend `"info"`, mirroring `concept-unsigned-deferral`), `step_id=None`, `anchor=f"concept-{node.id}"`, and a body naming the bucket and the `plan-tool scope-review` re-review action — **only for a node whose `review_state != "approved"`**. A signed-off (`approved`) decision is the operator's resolution, so a gone bucket on it must **not** re-surface — otherwise `wont_do`-ing a missing-bucket record never clears the finding and reproduces the "non-clearable standing finding" the plan exists to avoid (the `[missing-bucket-clearance]` bug). So `wont_do` *is* the clear-it path: it flips `review_state` to `approved`, and this detector then skips the node. When the bucket is missing on an unreviewed node, emit this finding and move on; do not also emit the unsigned-deferral reminder for the same node.
- **Present bucket, unreviewed → keep the existing unsigned-deferral reminder.** An unreviewed flat `defer`/`wont_do` whose bucket still exists keeps emitting the current `concept-unsigned-deferral` info finding — that path already works; don't duplicate it.

**Keep the new source non-blocking.** Do **not** add `CONCEPT_BUCKET_MISSING_SOURCE` to `SELF_CONSISTENCY_SOURCES`. That set is the blocking-capable battery; membership is what would flip an exit code and wedge the loop. Leaving it out is the non-blocking guarantee — the `collect_self_consistency_findings` filter keeps only `CONCEPT_COVERAGE_SOURCE`, and `_self_consistency_from_smells` keeps only `SELF_CONSISTENCY_SOURCES`, so the new finding rides through as advisory in both.

**Callers inherit totality with no edit.** The three callers — `collect_smell_findings` and `collect_self_consistency_findings` (in `plan_tool/review.py`) and `plan_tool/cli/completeness_phases.py:audit_detail_bundle_status` — carry no `try/except` around this call, so once the detector returns `[]` instead of raising, all three become crash-free with no change. State this to prove the fix is complete end-to-end; do not edit those files.

**Constraints and gotchas:**

- **Never raise.** The whole point is totality. If reading the plan body for the section lookup itself fails (`OSError`), do not raise and do not emit false `concept-bucket-missing` findings for every node — treat "can't read the body" as "can't determine bucket existence" and skip the bucket check for this run. `compute_plan_fingerprint` is already total, so the `load_concepts` argument is safe.
- **Legacy behavior frozen.** For `record_kind == "full-tree"`, every current output must be byte-for-byte unchanged — the `concept-coverage` and `concept-unsigned-deferral` findings, their severities, ids, and anchors all stay.
- **`bucket` is the section *name*, not the heading.** Match the normalized-name key that `split_body_sections` produces (lowercased, trailing punctuation trimmed), the same value `bootstrap_concepts` stored as the node title in step 2 — not the raw heading text.

## Tests

Add to `tests/test_review.py` (extend `TestConceptCoverage`; add a flat-record fixture helper or extend `_write_concept_coverage_fixture` with a `record_kind` / `bucket` path). This is a **feature** step: write every test with the implementation and get each green before the step is done.

- `test_stale_legacy_record_surfaces_resync_advisory` — a `record_kind="full-tree"` record whose stored `plan_fingerprint` no longer matches makes `check_concept_coverage` return exactly one non-blocking `concept-legacy-stale` advisory (not `[]`, and no `StaleConceptTreeError`), and that source is not in `SELF_CONSISTENCY_SOURCES`.
- `test_malformed_record_returns_empty` — a malformed `concepts.json` (`InvalidConceptTreeError`) makes `check_concept_coverage` return `[]` (truly unreadable).
- `test_malformed_record_returns_empty` — a corrupt `concepts.json` on disk makes the detector return `[]` (no `InvalidConceptTreeError`).
- `test_decision_record_missing_bucket_surfaces_rereview` — an **unreviewed** flat node whose `bucket` names no current body section emits exactly one `concept-bucket-missing` finding.
- `test_signed_off_missing_bucket_is_cleared` — an **approved** (`wont_do`) flat node whose `bucket` is gone emits **no** `concept-bucket-missing` finding, so `scope-review wont_do` clears the finding rather than leaving a non-clearable standing one.
- `test_bucket_missing_finding_is_non_blocking` — `CONCEPT_BUCKET_MISSING_SOURCE not in SELF_CONSISTENCY_SOURCES` and the finding's severity is below the blocking threshold (`"info"`).
- `test_approved_flat_defer_present_bucket_no_finding` — an approved `defer`/`wont_do` flat node whose bucket still exists yields no finding (specifically no `concept-coverage`).
- `test_unreviewed_flat_defer_present_bucket_still_unsigned` — an unreviewed flat `defer` with an existing bucket still emits `concept-unsigned-deferral` (info), unchanged.
- `test_missing_bucket_takes_priority_over_unsigned` — an unreviewed flat node with a missing bucket emits only `concept-bucket-missing`, not also `concept-unsigned-deferral`.
- `test_legacy_full_tree_coverage_unchanged` — the existing committed-owner / no-accounting-link / structured-deferral cases in `TestConceptCoverage` still pass for a full-tree record.

## Acceptance criteria

- `check_concept_coverage` returns `[]` (raises nothing) for a malformed `concepts.json`, and returns exactly one non-blocking `concept-legacy-stale` advisory (source `CONCEPT_LEGACY_STALE_SOURCE`, `anchor="concept-legacy-stale"`, `step_id=None`, below-threshold/info severity) for a stale legacy full-tree record — a drifted legacy record still carries possibly-blocking coverage, so it is surfaced for re-sync, never swallowed to `[]`.
- A `record_kind="decision-record"` node whose `bucket` is not a current body-section name produces exactly one `concept-bucket-missing` finding with `step_id=None` and `anchor="concept-<id>"`.
- `CONCEPT_BUCKET_MISSING_SOURCE` is defined in `plan_tool/review.py`, is not in `SELF_CONSISTENCY_SOURCES`, and its findings carry a below-threshold severity.
- An approved flat `defer`/`wont_do` node with an existing bucket produces no finding; an unreviewed one with an existing bucket still produces `concept-unsigned-deferral`.
- Full-tree records produce byte-identical findings to today.
- `uv run pytest tests/test_review.py -q` passes, including the new cases.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — field defaults on `ConceptNode.bucket` / `ConceptTree.record_kind` that this step reads.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — the `InvalidConceptTreeError` this step catches originates in `load_concepts`' JSON decode path.
- [pytest — full documentation](https://docs.pytest.org/en/stable/) — for authoring the totality, bucket-gone, and non-blocking cases.

## Deferred

- Scope-review's bucket-existence confirm gate — `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` (step 4) implements the same "does this bucket still resolve" rule as a confirm/reject gate and owns the re-home action; this step only surfaces the finding. Both sites must use the identical `split_body_sections`-over-current-body recipe so they agree; if that derivation should become one shared helper, route the consolidation to reconcile rather than expanding either step's footprint.
- Rendering and grouping the `concept-bucket-missing` finding in `status`, the completeness report, and the create run-summary line — owned by step 5, which fans pending decisions into a bucket-grouped list; this step only produces the finding and its source token.
- A dismiss/remove verb for a wrong or gone pending decision — the plan's Out of scope leaves active dismissal for later; the operator's `scope-review` is the only resolver.
