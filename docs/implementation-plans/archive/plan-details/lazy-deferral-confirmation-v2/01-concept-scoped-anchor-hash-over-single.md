# Step 1 — Add a concept-scoped anchor hash over one bucket's source text

## Summary

Add a small hash function to `plan_tool/review_persistence.py` that turns a single bucket's source text into a stable SHA-256 hex digest — the per-guide-post "anchor" that later steps store on a guide post and re-check to decide if that one bucket went stale. It hashes only the text the caller hands in (one section), not the whole plan+detail bundle, so an edit to an unrelated section can't move it. This step adds the primitive only; it does not wire it into any loader, record, or read path (those are step 2 and later). On green, `review_persistence.py` exposes one new deterministic function that returns a 64-character hex digest for any bucket label + source text, and its unit tests pass.

## Table of Contents

- [Why](#why) — what's broken with the bundle-wide fingerprint and why a scoped anchor
- [Input](#input) — the sibling hash contract this primitive parallels
- [Files (creates vs edits)](#files-creates-vs-edits) — the one file this step touches
- [Implementation](#implementation) — the new function, its framing, and the leaf constraint
- [Tests](#tests) — unit cases added with the code
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — hashlib
- [Deferred](#deferred) — what this step deliberately leaves to later steps

## Why

A pending deferral is confirmed *after* more edits by design, so the current bundle-wide guard (`plan_tool/concept_tree.py:load_concepts` comparing stored `plan_fingerprint` against `compute_plan_fingerprint` over the whole plan + every detail file) treats it as stale on the next unrelated edit and dead-ends `scope-review` with `StaleConceptTreeError`. The fix (plan section **B**) is to validate a guide post against a hash scoped to only its own bucket's source text. Before any loader or record can use that idea, the codebase needs the primitive that computes it — a deterministic hash over one bucket's text. This step adds exactly that and nothing else, so step 2's record shape and loader have a stable function to call.

## Input

This step reads no persisted data. It parallels one existing contract:

- **`plan_tool/review_persistence.py:compute_plan_fingerprint`** — the sibling digest over the whole plan + `plan-details/<slug>/*.md` bundle, framed as `name\0content` per file. The new function is the *scoped* counterpart: same module, same SHA-256 / hex-digest / stdlib-only-leaf posture, but over a single caller-supplied text instead of walking the bundle. Match its "always return a non-empty 64-char hex, never raise" behavior.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review_persistence.py` — add one new public function computing the concept-scoped anchor hash. No change to `compute_plan_fingerprint`, `_hash_file_into`, or any existing symbol.

## Implementation

- **Add one function that hashes a single bucket's source text into a stable hex digest.** A good name is `compute_bucket_anchor(bucket: str, bucket_source_text: str) -> str`, placed near `compute_plan_fingerprint` in `plan_tool/review_persistence.py`. It builds a fresh `hashlib.sha256()`, feeds it the bucket text, and returns `h.hexdigest()`.
- **Recommended framing: `bucket\0bucket_source_text`, encoded UTF-8** — mirror `compute_plan_fingerprint`'s `name\0content` framing (`h.update(name.encode("utf-8")); h.update(b"\0"); h.update(text)`). This makes the digest move when either the bucket label *or* its text changes, so renaming a section forces a re-derive even if the text is byte-for-byte the same, and two different buckets that happen to share text get different anchors (no cross-bucket collision).
  - *One alternative, rejected:* hash only `bucket_source_text` and rely on the caller storing the bucket label separately as the lookup key. It's defensible — a rename already means "the old bucket can't be found → re-derive" — but the label-framed version is the safer default and keeps this function shaped like its sibling. The implementer has latitude here; if you pick content-only framing, say so and keep step 2's loader consistent with it.
- **Take the source text as a plain string, not a path or a parsed section object.** `review_persistence.py` is a **stdlib-only leaf** — it must not import `parser`, `concept_bootstrap`, `concept_tree`, or `drift_detection` (the module docstring and the `_hash_file_into` note both call this out; `compute_plan_fingerprint` keeps its code axis opaque for the same reason). Section extraction — deciding *which* text is a bucket's source — belongs to the callers in later steps, not here. Keeping the input a bare string is what preserves the leaf.
- **Always return a 64-character hex digest; never raise.** An empty `bucket_source_text` (a caller that couldn't locate the bucket) must still return a stable non-empty digest — the caller decides "re-derive" by comparing a stored anchor against a freshly computed one, so the function itself never needs to signal "not found". This matches `compute_plan_fingerprint`'s non-empty-even-when-plan-missing guarantee.
- **Do not add normalization** (whitespace trimming, line-ending folding) in this step. "Material change" granularity is governed by *what text the caller extracts* (the bucket-granularity judgment the plan owns as a risk), not by smoothing bytes here. A straight byte hash keeps this primitive honest and its behavior obvious.
- **No existing call sites change.** The foundational logic — "SHA-256 over a scoped piece of text" — has two relatives that are deliberately left alone: `compute_plan_fingerprint` (whole bundle, different scope) and `plan_tool/drift_detection.py:compute_content_hash` (a single file's bytes, and off-limits to import from this leaf). This is a new primitive, not a consolidation; there is no duplicated block to fold together.

## Tests

Add a new class `TestComputeBucketAnchor` in `tests/test_review_persistence.py` (mirror the existing `TestComputePlanFingerprint` style; no `tmp_path` needed — the function takes strings). Import the new symbol alongside `compute_plan_fingerprint`.

- `test_bucket_anchor_deterministic` — same `(bucket, source_text)` returns the identical digest across two calls.
- `test_bucket_anchor_changes_on_source_text_edit` — same bucket label, changed source text → different digest.
- `test_bucket_anchor_changes_on_bucket_label` — same source text, different bucket label → different digest (asserts the label is part of the hash; adjust/drop only if you deliberately chose content-only framing).
- `test_bucket_anchor_is_pure_function_of_its_two_inputs` — the digest for bucket A's text does not depend on any other bucket; two independent calls with unrelated inputs don't interfere (guards the "unrelated edit leaves it valid" property at the primitive level — the function sees only the one bucket).
- `test_bucket_anchor_non_empty_hex` — an empty `source_text` still returns a truthy 64-character hex string (never `""`, never raises).

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add all five unit tests above in `tests/test_review_persistence.py` **with** the implementation of `compute_bucket_anchor`. Every new test must be green before the step is considered finished.

## Acceptance criteria

- `plan_tool/review_persistence.py` exposes a new public function that takes a bucket label and a bucket source-text string and returns a 64-character lowercase hex SHA-256 digest.
- The digest is deterministic: equal inputs → equal output across calls.
- Changing the source text (label fixed) changes the digest; changing the label (text fixed) changes the digest under the recommended framing.
- An empty source-text input returns a non-empty 64-character hex string and raises nothing.
- No existing symbol in `plan_tool/review_persistence.py` changes; `compute_plan_fingerprint` and its tests still pass unchanged.
- `uv run pytest tests/test_review_persistence.py -q` passes, including the new `TestComputeBucketAnchor` cases.
- `review_persistence.py` imports no first-party module it didn't already import (stays a stdlib-only leaf).

## References

- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — the `sha256()` constructor, `.update()`, and `.hexdigest()` used to build the anchor.

## Deferred

- The guide-post record shape that stores this anchor and the loader that validates against it instead of the bundle fingerprint — step 2 (`plan_tool/concept_tree.py`, `DATA_CONTRACT.md`).
- Extracting a bucket's source text from plan/section structure (which text to feed this function) — later steps that read the plan (steps 4, 5, 6, 8); this leaf never parses.
- Wiring the anchor into `scope-review`, `status`, `check_concept_coverage`, and its `collect_*` callers so a bucket-level mismatch means "re-derive" not a crash — steps 5 and 6.
- Any normalization of bucket text before hashing — not in the plan; revisit only if the bucket-granularity risk demands it.
