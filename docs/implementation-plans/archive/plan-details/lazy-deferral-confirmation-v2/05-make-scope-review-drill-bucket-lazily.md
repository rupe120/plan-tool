# Step 5 — Make scope-review confirm a pending guide post against its scoped anchor, drilling the bucket lazily and re-deriving on a bucket mismatch instead of dead-ending on staleness

## Summary

Rewrite `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` so it reads and writes the **guide-post** record (step 2's shape) instead of re-deriving and signing the whole bootstrapped tree. For each `--concept` in scope, the command drills only that concept's own **bucket** (the body section it lives in) out of the current plan text, recomputes the concept-scoped anchor (`compute_bucket_anchor` from step 1) over that one bucket, and compares it to the stored `bucket_anchor`. A match confirms the guide post as-is; a **mismatch re-derives** (re-anchors the node to the current bucket) and still confirms — never dead-ends. The staleness that used to block this (`load_concepts` raising `StaleConceptTreeError` on the whole-bundle fingerprint) is already skipped for guide-post records by step 2, so the confirm loop no longer refuses a deferral that was recorded before later unrelated edits. On green, a `scope-review defer` on a plan edited since the deferral was recorded exits 0 and renders the concept into `## Deferred` via the existing `render_scope_decisions` path; an edit to an **unrelated** section leaves the anchor unchanged, while an edit to the guide post's **own** bucket re-derives it. The primary files are `plan_tool/cli/scope_review_cmd.py` and `tests/cli/test_scope_review_cmd.py`.

## Table of Contents

- [Why](#why) — what the whole-tree re-derive breaks and what the lazy scoped-anchor confirm fixes
- [Input](#input) — the guide-post loader, the anchor primitive, the node recipe, and the sync contract this consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits
- [Implementation](#implementation) — the flow rewrite, the drill/confirm/re-derive rule, and the constraints that must hold
- [Tests](#tests) — reworked and new cases added with the code
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse, hashlib, pytest
- [Deferred](#deferred) — what this step deliberately leaves to later steps or the backlog

## Why

`cmd_scope_review` today bootstraps a concept node for **every** body section, three-way merges it against the stored record (`rederive_concepts`), signs the scoped decision against the **whole plan+detail bundle** fingerprint, and republishes the full tree. That model is exactly what the plan replaces: a pending deferral is confirmed *after* more edits by design, so the whole-bundle fingerprint has moved by confirm time, and the command dead-ends. Plan section **B** fixes this by validating each guide post against a hash scoped to only its own bucket's source text. Steps 1, 2, and 4 built the pieces: step 1 added `compute_bucket_anchor`, step 2 gave `load_concepts` a guide-post branch that skips the bundle-fingerprint check, and step 4 made `create` write pending guide posts carrying a `bucket` + `bucket_anchor`. This step is where `scope-review` stops re-deriving the whole tree and starts **confirming a guide post against its scoped anchor** — the read/confirm caller step 2's Deferred section pointed here.

## Input

This step consumes four upstream contracts; its correctness rests on each staying shaped as expected:

- **Step 2's guide-post loader** — `plan_tool/concept_tree.py:load_concepts(plan_path, expected_plan_fingerprint)` returns a `record_kind == "guide-post"` record **without** raising `StaleConceptTreeError` even when the stored `plan_fingerprint` differs from the current bundle fingerprint. It still raises `StaleConceptTreeError` for a legacy `full-tree` record on a mismatch, and `InvalidConceptTreeError` on a malformed record. This step keeps catching both (the current `except (InvalidConceptTreeError, StaleConceptTreeError)` arm) so a legacy/broken record still exits cleanly.
- **Step 1's `plan_tool/review_persistence.py:compute_bucket_anchor(bucket, bucket_source_text) -> str`** — the deterministic 64-char digest this step recomputes over the drilled bucket to compare against the stored `bucket_anchor`. It never raises and returns a stable value even for empty input.
- **Step 4's guide-post node recipe (shared contract — must match exactly).** A guide post's `bucket` is the **normalized body-section name** (`plan_tool/parser.py:BodySection.name`, which is the heading lowercased with trailing `:`/`.` stripped) and its `bucket_anchor` is `compute_bucket_anchor(bucket, section.body)` where `section.body` is that section's body as `parse_body_sections` returns it (surrounding newlines stripped). This step **must** re-extract the same label + text pair, or the anchor round-trip never matches and every confirm looks like a bucket change. Step 4 owns writing this; this step re-reads it — cite step 4's outcome, do not re-specify how create builds it.
- **`plan_tool/concept_sync.py:synchronize_concepts(plan_path, plan_snapshot, original_tree, reviewed_tree, *, source_plan_text=...)`** — the guarded publisher (unchanged by this step). It compares the on-disk sidecar against `json.dumps(asdict(original_tree))`, so `original_tree` must be the **unmutated** loaded record; it overwrites `reviewed_tree.plan_fingerprint` with its own freshly-rendered bundle fingerprint and preserves `record_kind`; and it renders only `review_state == "approved"` defer/wont_do nodes into `## Deferred` / `## Out of scope`. `_validate_tree(reviewed_tree)` runs inside it, so a guide-post `reviewed_tree` must satisfy step 2's per-kind rule (every node `defer`/`wont_do` with non-empty `bucket`/`bucket_anchor`).
- **`plan_tool/concept_review.py:review_concept_scope(tree, ids, decisions, expected_source_state, *, sign_off=True)`** — signs the scoped ids (`review_state="approved"`), and rejects with `StaleConceptReviewError` when `expected_source_state != tree.plan_fingerprint`. Every scoped id must be present in `tree.concepts` (it raises `InvalidConceptScopeError` on an unknown id).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/scope_review_cmd.py` — rewrite the body of `cmd_scope_review` to load the record, drill each scoped concept's bucket from current plan text, confirm against the scoped anchor (re-deriving on a mismatch), preserve unscoped pending guide posts, and synchronize a `record_kind="guide-post"` reviewed tree. Adjust imports: add `compute_bucket_anchor` beside the existing `compute_plan_fingerprint` import from `plan_tool.review_persistence`; add `ConceptTree`, `ConceptNode` (and `concept_id` if you resolve fresh ids by hand) from `plan_tool.concept_tree`; drop the now-unused `rederive_concepts` import. Keep `bootstrap_concepts` if you use it as the id→section resolver (see Implementation).
  - `tests/cli/test_scope_review_cmd.py` — rework the three existing behavioral tests (the bootstrap-and-persist test becomes a fresh-defer→guide-post test; the derivation-conflicts test loses its `rederive_concepts` monkeypatch and is replaced by a bucket-gone / sync-conflict test; the invalid-record test stays) and add the new scoped-anchor confirm, re-derive-on-bucket-edit, unrelated-edit, preserve-unscoped, and wont_do cases.

## Implementation

**Foundational logic of this step:** *confirm a guide post by re-deriving and comparing a per-bucket anchor over the current plan text, never by re-checking the whole-bundle fingerprint.* The same drill-and-compare-the-scoped-anchor rule is what step 6 adds to `plan_tool/review.py:check_concept_coverage` and its `collect_*` callers — that is a **parallel producer of the same rule in another module**, in scope for step 6, not here; keep the two consistent but do not touch `review.py`.

- **Load the record and drill lazily; don't re-derive the whole tree.** Keep the top of the function (context, `resolve_plan_for_context`, `source_plan_text`, `parse_plan`, `compute_plan_fingerprint`, `slug`) and the `load_concepts(...)` call with its `except (InvalidConceptTreeError, StaleConceptTreeError)` arm. Remove the `bootstrap_concepts` full-tree build + `rederive_concepts` + conflict-reporting block that follows. Parse the current body once — `parse_body_sections(split_plan_document(source_plan_text).body)` — into a name→section map for drilling. That map is the "lazy drill": you touch only the buckets the scope names.
- **Build the candidate from the loaded record plus fresh-derived nodes.** Deep-copy `original_tree` (or start an empty `ConceptTree(plan_slug=slug, plan_fingerprint=fingerprint, record_kind="guide-post")` when it is `None`) so `original_tree` stays unmutated for `synchronize_concepts`'s compare-and-swap. For each scoped `--concept` id:
  - **Existing guide post (in the loaded record):** look up its `bucket`, find the current section by that name, recompute `compute_bucket_anchor(bucket, section.body)`, and if it differs from the node's stored `bucket_anchor`, **re-derive** — set the node's `bucket_anchor` (and refresh its `source`) to the current values. A match leaves the node untouched. Either way it stays in the candidate and gets signed below.
  - **Fresh deferral (id not in the record):** resolve the id to a current section, then build a guide-post node the **same way step 4 does** (id, title = section name, order, source = section body, `bucket` = section name, `bucket_anchor = compute_bucket_anchor(bucket, source)`) and append it. One clean way to resolve the id and get a well-formed node is to reuse `bootstrap_concepts(plan, sections, ...)` as a cheap deterministic id→node lookup (no Claude, nothing persisted) and set `bucket`/`bucket_anchor` on the matched node — this keeps the fresh node byte-consistent with step 4's producer.
  - **Bucket section gone (renamed or deleted):** the concept's home no longer exists, so there is no text to re-derive from. `warn(...)` with a clear message and return `SCOPE_REVIEW_INVALID_STATE_EXIT` without writing anything. This is the one mismatch that legitimately cannot re-derive — it is a clean per-concept refusal, **not** a `StaleConceptTreeError`.
  - **Unknown id (not a guide post and not a current section):** `warn(...)` and return `SCOPE_REVIEW_INVALID_STATE_EXIT`. (`review_concept_scope` would also reject it, but a pre-check gives a clearer message and avoids a partially-built candidate.)
- **Preserve unscoped pending guide posts.** The candidate must carry every node from the loaded record, not just the scoped ones — otherwise `synchronize_concepts` republishes a sidecar that drops the other pending guide posts. Only the scoped ids get re-anchored (if needed) and signed; the rest stay `review_state="unreviewed"` and render nothing.
- **Sign off and synchronize.** Set the candidate's `plan_fingerprint = fingerprint` (current provenance) and its `record_kind = "guide-post"`, then `reviewed_tree = review_concept_scope(candidate, concept_ids, decisions, fingerprint, sign_off=True)`. Passing `expected_source_state=fingerprint` against a candidate whose `plan_fingerprint` is also `fingerprint` makes that whole-bundle check a no-op tautology **on purpose** — the scoped anchor you just checked is the real currency guard, replacing the bundle fingerprint (plan section **B**). Then call `synchronize_concepts(plan_path, plan, original_tree, reviewed_tree, source_plan_text=source_plan_text)` exactly as today, keeping the existing `result.succeeded` / conflict-vs-invalid exit-code handling and the `success(...)` line.
- **Reject `include` in the guide-post model.** A guide post holds only `defer`/`wont_do`; an `include` decision has no valid persisted form (a committed step is its own proof, and withdrawing a deferral is a *dismiss* verb the plan puts out of scope). Recommend detecting a scoped `include` decision and refusing with a clear message (`SCOPE_REVIEW_INVALID_STATE_EXIT`) rather than letting `_validate_tree` reject the guide-post record with an opaque error. You have latitude on the exact wording; the invariant is that no `include` decision reaches `save_concepts` as a guide-post node.
- **Constraints that must hold:**
  - The bucket label + body text you hash must equal step 4's (`bucket` = normalized section name, source = `parse_body_sections` body), or every confirm falsely reads as a bucket change. Extract with `parse_body_sections` (the same function the producer used), not a hand-rolled slice.
  - Pass the **unmutated** loaded `original_tree` to `synchronize_concepts`; build the candidate from a deep copy. A mutated `original_tree` breaks the sidecar compare-and-swap.
  - The reviewed tree must be `record_kind="guide-post"` with every node `defer`/`wont_do` and non-empty `bucket`/`bucket_anchor`, or `_validate_tree` inside `synchronize_concepts` rejects it.
  - A genuine bucket-level mismatch **re-derives and still confirms** (exit 0); it must never surface as a hard crash or a stale-record refusal. Only a missing bucket section or a sync-level conflict refuses.
- **Legacy full-tree records reaching scope-review are out of this step's scope.** `create` no longer writes `full-tree` records (step 4), and this plan does not migrate existing ones. If a loaded record is `record_kind == "full-tree"`, refuse with a clear "legacy full-tree record; migrate or remove it" message (`SCOPE_REVIEW_INVALID_STATE_EXIT`) rather than carrying the old bootstrap+rederive path forward — see Deferred.

## Tests

Reworked and new cases in `tests/cli/test_scope_review_cmd.py`. This is a **feature** step and the plan sets `enforce_step_tests: true`: author every case **with** the implementation, and each must be green before the step is done. Reuse the existing `_write_plan` / `_args` / `_resolve_to` helpers; extend `_write_plan` (or add a sibling) to stamp a pending guide-post `concepts.json` on disk for the confirm cases, and to allow editing an individual section.

- `test_scope_review_confirms_pending_guide_post_after_unrelated_edit` — a guide-post record with a pending `defer` on the `candidate` bucket, then an edit to the unrelated `tail` section; `scope-review defer` exits 0, the persisted node is `review_state="approved"`, its `bucket_anchor` is unchanged (matches `compute_bucket_anchor("candidate", <candidate body>)`), and the plan renders the concept into `## Deferred`.
- `test_scope_review_rederives_on_bucket_edit` — edit the `candidate` bucket's own body, then confirm; exit 0, and the persisted `bucket_anchor` equals `compute_bucket_anchor("candidate", <new candidate body>)` (re-derived), not the pre-edit value.
- `test_scope_review_confirms_without_stale_when_bundle_fingerprint_moved` — a guide-post record whose stored `plan_fingerprint` differs from the current bundle fingerprint confirms cleanly (exit 0), asserting no `StaleConceptTreeError` path and no invalid-state exit.
- `test_scope_review_missing_bucket_section_rejected_without_writes` — a guide post whose `bucket` section has been deleted from the plan returns `SCOPE_REVIEW_INVALID_STATE_EXIT` and leaves the plan and sidecar bytes unchanged.
- `test_scope_review_preserves_unscoped_pending_guide_posts` — a record with two pending guide posts; confirming one leaves the other in the sidecar with `review_state="unreviewed"`.
- `test_scope_review_wont_do_renders_out_of_scope` — a `wont_do` confirm renders the concept into `## Out of scope`.
- `test_scope_review_fresh_defer_writes_guide_post` — rework of `test_scope_review_bootstraps_and_persists_scoped_result`: an absent record, `scope-review defer` on a section writes a `record_kind="guide-post"` sidecar whose single node is `approved` `defer` with `bucket`/`bucket_anchor` set, renders into `## Deferred`, and writes no node for any other section.
- `test_scope_review_include_rejected` — a scoped `include` decision refuses with `SCOPE_REVIEW_INVALID_STATE_EXIT` and writes nothing (adjust to the exact refusal you land).
- `test_scope_review_invalid_record_has_distinct_exit_and_writes_nothing` — keep as-is (broken JSON → `SCOPE_REVIEW_INVALID_STATE_EXIT`, no writes).
- Replace `test_scope_review_reports_all_derivation_conflicts_without_writes` — the `rederive_concepts` monkeypatch it relied on is gone with the whole-tree path; cover the remaining conflict surface instead with a `synchronize_concepts`-conflict case (e.g. an owned-section or sidecar change between read and publish → `SCOPE_REVIEW_CONFLICT_EXIT`, no writes).
- `test_scope_review_parser_rejects_malformed_decision` — keep unchanged (the `--decision` parser is untouched).

### Test-creation order (feature step)

Author the confirm / re-derive / fresh-defer unit cases alongside the `cmd_scope_review` rewrite; land the invalid-state and conflict cases with the refusal branches. Every new and reworked case must be green (and `uv run pytest tests/cli/test_scope_review_cmd.py -q` clean) before the step is finished.

## Acceptance criteria

- A guide-post record with a pending `defer` whose stored `plan_fingerprint` no longer matches the current bundle fingerprint confirms via `scope-review defer` (exit 0), raising no `StaleConceptTreeError`.
- After an edit to an **unrelated** section, the confirmed node's persisted `bucket_anchor` is unchanged; after an edit to the guide post's **own** bucket, the persisted `bucket_anchor` equals `compute_bucket_anchor(bucket, <current bucket body>)` (re-derived) and the confirm still exits 0.
- A confirmed `defer` renders into `## Deferred` and a confirmed `wont_do` into `## Out of scope`, both via `render_scope_decisions`, on a plan edited since the deferral was recorded.
- Confirming one scoped concept preserves every other pending guide post in the sidecar with `review_state="unreviewed"`.
- A `scope-review defer` on a section with no prior record writes a `record_kind="guide-post"` sidecar whose only node is the confirmed deferral, with non-empty `bucket`/`bucket_anchor`.
- A guide post whose bucket section is missing, an unknown concept id, and a scoped `include` decision each return `SCOPE_REVIEW_INVALID_STATE_EXIT` and leave the plan and sidecar bytes unchanged.
- A `synchronize_concepts` divergence/mapping conflict returns `SCOPE_REVIEW_CONFLICT_EXIT` with no partial write.
- `grep -n "rederive_concepts" plan_tool/cli/scope_review_cmd.py` returns nothing (the whole-tree re-derive path is gone).
- `uv run pytest tests/cli/test_scope_review_cmd.py -q` passes, including the new and reworked cases.

## References

- [argparse — Parser for command-line options (Python docs)](https://docs.python.org/3/library/argparse.html) — the `append` action behind the repeated `--concept` / `--decision` options this command consumes (parser unchanged, but the flag semantics matter for the tests).
- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — background for the SHA-256 scoped anchor recomputed by `compute_bucket_anchor`.
- [pytest — How to use temporary directories and files in tests](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture used for the hermetic staleness/confirm-loop tests.

## Deferred

- **Consolidating the guide-post node recipe shared with step 4** — building a guide-post node from a section (`id`, `title`, `order`, `source`, `bucket = section name`, `bucket_anchor = compute_bucket_anchor(bucket, source)`) now exists in both `plan_tool/create.py` (step 4) and `plan_tool/cli/scope_review_cmd.py` (this step). Extracting a single shared helper (e.g. in `plan_tool/concept_bootstrap.py`) is a refactor this detail cannot mint; route it to reconcile so the two producers can't drift.
- **`check_concept_coverage` and its `collect_*` callers validating the scoped anchor** — the same drill-and-compare rule on the read/audit side is step 6.
- **`include` / dismiss semantics for a recorded guide post** — withdrawing a deferral is the dismiss verb the plan leaves out of scope; this step rejects `include` rather than persisting it.
- **Legacy `full-tree` record support and migration in scope-review** — `create` no longer writes `full-tree` records; a pre-existing one is refused with a clear message, and migrating it to the guide-post shape is out of scope plan-wide (step 2 keeps such records loadable).
- **Per-bucket drill caching** — the command re-parses the body and recomputes the anchor on each run; caching is an optimization the plan defers.
