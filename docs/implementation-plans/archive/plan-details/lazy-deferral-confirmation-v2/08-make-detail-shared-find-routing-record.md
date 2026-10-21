# Step 8 — Make detail's shared-find routing record a new deferral as a bucket-tagged pending guide post, deriving the target lazily, never signed under `-y`

## Summary

Today `plan_tool/detail.py` can only *link* an already-approved `defer` concept to a step — it never records a brand-new deferral, and its tail skips entirely when there is no `concepts.json`. This step makes detail's structured-deferral routing record a **new** deferral as a **pending guide post**: the model names a plan **bucket** (a body section) to defer, and detail creates an unreviewed `defer` node carrying that bucket's `bucket` label and step 1's `bucket_anchor`, drilling the bucket's source text lazily from the current plan body. The primary files are `plan_tool/detail.py` and `tests/test_detail.py`. The key decision: derive candidate buckets and their anchors from the **current plan body** (reusing the same `bootstrap_concepts` recipe create uses), so recording works with a **narrowed or absent** record and never depends on a pre-materialized section tree. On green, a detail run that defers a bucket writes a `record_kind="guide-post"` record with the bucket's node at `review_state="unreviewed"` — never signed, even under `-y` — and it works whether or not a `concepts.json` already exists.

## Table of Contents

- [Why](#why) — what detail's deferral routing can't do today and what this step fixes
- [Input](#input) — the guide-post shape, the anchor primitive, and the bootstrap recipe this consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits
- [Implementation](#implementation) — surfacing proposable buckets, relaxing the gate, and the lazy-derive tail
- [Tests](#tests) — unit + integration cases added with the code
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — hashlib, dataclasses, json
- [Deferred](#deferred) — what this step leaves to other steps or reconcile

## Why

Detail's deferral routing is built for the old eager model, so it breaks against this plan's guide-post record. Three things block it today:

- **It can only defer an already-approved concept.** `plan_tool/detail.py:parse_structured_detail_response` rejects any deferral whose target node is not `review_state == "approved"` and `decision == "defer"`. After step 4, `create` writes only **unreviewed** guide posts, so there is nothing approved for detail to name — every deferral the model proposes is rejected.
- **It does nothing when there is no record.** In `_author_step_detail`, the `concept_tree is None` arm parses shape only and drops the deferrals, and the tail publish block (`generate_detail`, the `if concept_tree is not None and not dry_run:` guard) is skipped entirely. So detail can never *create* a record from a deferral — it can only edit one that already exists.
- **It reaches into a stored node instead of deriving one.** The tail helper `_replace_detail_deferrals` looks the concept up by `nodes[deferral.concept_id]` and would raise `KeyError` for a bucket that is not already a node.

Design point **F** of the plan replaces this with a producer that records a **new** deferral as a bucket-tagged pending guide post, deriving the bucket lazily from the current plan body — so it works on any plan, including one already carrying a narrowed record (the conflict that broke the prior plan). Steps 1 and 2 built the pieces: step 1 added `compute_bucket_anchor`, and step 2 added the guide-post record shape (`ConceptNode.bucket`/`bucket_anchor`, `ConceptTree.record_kind`) and the loader branch that skips the bundle-fingerprint staleness check for guide-post records. This step makes detail a **second producer** of guide posts alongside create (step 4).

## Input

This step consumes three upstream contracts; correctness rests on each staying shaped as expected:

- **Step 2's guide-post record shape and loader** (`plan_tool/concept_tree.py`): `ConceptNode.bucket` / `ConceptNode.bucket_anchor`, `ConceptTree.record_kind`, and `load_concepts(plan_path, expected_plan_fingerprint)`. A `record_kind == "guide-post"` record loads without raising `StaleConceptTreeError` even when the bundle fingerprint drifted; a legacy `full-tree` record still raises it, and a malformed record raises `InvalidConceptTreeError`. Detail's load at `generate_detail`'s top (the `load_concepts(plan_path, compute_plan_fingerprint(plan_path))` call) keeps catching both and raising `DetailError` — unchanged.
- **Step 1's `plan_tool/review_persistence.py:compute_bucket_anchor(bucket, bucket_source_text) -> str`** — the deterministic 64-char digest each new guide post stores in `bucket_anchor`. The `bucket` label and `bucket_source_text` detail feeds it **must** match what create (step 4) writes and what scope-review (step 5) and `check_concept_coverage` (step 6) re-drill, or the anchor never round-trips and every later confirm reads as a bucket change. This is the shared producer recipe — see Implementation.
- **The existing bucket-derivation recipe** (`plan_tool/concept_bootstrap.py:bootstrap_concepts` + `plan_tool/parser.py:parse_body_sections` / `split_plan_document`). `bootstrap_concepts` turns the current plan body into candidate nodes where `id == concept_id(section.name, [])`, `title == section.name`, and `source == section.body`. `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` already builds candidates this exact way. Reuse it so the bucket label, id, and source text all come from one function and stay identical across producers and consumers — do not hand-roll a section split.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — surface proposable buckets in `_format_concept_scope_block`; relax `parse_structured_detail_response`'s ownership gate so a deferral may target an **unreviewed** bucket the step owns or that no step owns; let `_author_step_detail` validate and capture deferrals even when the loaded record is absent; and rework the tail publish so it creates pending guide-post nodes (bucket + `bucket_anchor`, `review_state="unreviewed"`, `decision="defer"`), builds a `record_kind="guide-post"` record even from an absent record, and persists — never signing. Add imports for `ConceptNode` (from `plan_tool.concept_tree`), `bootstrap_concepts` (from `plan_tool.concept_bootstrap`), the parser body-section helpers, and `compute_bucket_anchor`.
  - `tests/test_detail.py` — add the unit + integration cases below; reconcile the couplings in `TestParseStructuredDetailResponse` and `TestStructuredDetailDeferrals` that assume approved-only targets and a present record.

## Implementation

The behavior that changes: **a proposed deferral becomes a new pending guide post derived from the current plan body**, instead of a link onto a pre-approved node. Approach it as three widenings plus a tail rework, all keyed off one lazily-built candidate set.

- **Build the candidate buckets once, lazily, from the current plan body.** Recommended: `bootstrap_concepts(plan, parse_body_sections(split_plan_document(plan_text).body), plan_slug=…, plan_fingerprint=…)`, the same call `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` makes. This gives, for every body section (bucket), a candidate node with `id`, `title` (= bucket label), and `source` (= bucket text) — no stored tree required. Key it by `id` for lookup. This candidate set is the single source both the prompt surface and the tail read, so the bucket label / id / source stay identical everywhere.

- **Surface proposable buckets to the model** (`_format_concept_scope_block`). Today it lists only `review_state == "approved"` nodes and otherwise renders `_the concept record has no signed-off decisions_`. Add a **proposable** sub-list: one line per candidate bucket the model may defer (its bare `id` + bucket title, marked proposable), so the model can name a bucket by its exact id. The model can only reference an id this block shows — a relaxed gate with no widened surface is unreachable. **Keep the approved-node lines byte-unchanged** (they carry `decision={node.decision}`, which `test_dry_run_reports_include_regeneration_without_writes` asserts as `decision=include`).

- **Relax the ownership gate** (`parse_structured_detail_response`). Its per-deferral `all(...)` check bundles separable rejections; drop **only** the two pre-approval ones — `node.review_state != "approved"` and `node.decision != "defer"`. Keep every other guard: `deferral.step_id == step.id`, the owner check (`concept_owners` empty or `step.id` in it), and the `## Deferred`-mentions-the-id check. Replace the "node exists in the loaded `concept_tree`" lookup with "id resolves to a **known bucket** — a candidate from the current plan body (or an existing node in the record)". A brand-new bucket is unowned, so the owner check passes. This is additive: an already-approved `defer` node still validates.

- **Validate and capture deferrals even with no record** (`_author_step_detail`). Today the `concept_tree is None` arm parses shape only and forces `body = None` when a deferral is present, dropping the response. Change it so deferrals validate against the current-body candidate set regardless of whether a stored record exists, and the parsed deferrals ride onto the `DetailResult` (`result.deferrals`) the same way the present-record arm already does. This is the "no dependency on a pre-materialized section tree" requirement — pass the candidate set (built above) into the parse call so the `None`-record path is no longer a dead end for deferrals.

- **Rework the tail publish to create guide posts and handle an absent record.** In `generate_detail`, the block that collects `(step_id, deferrals)` for written results and calls `_replace_detail_deferrals` + `save_concepts`:
  - **Run it when there are deferrals to record, not only when a record was loaded.** Widen the `if concept_tree is not None …` guard so a run that defers a bucket against an **absent** record still publishes — start from a fresh `ConceptTree(plan_slug, plan_fingerprint, [], record_kind="guide-post")` in that case, otherwise extend the loaded tree.
  - **Create a pending guide-post node for any deferred bucket not already in the record.** For each deferred id, look it up in the candidate set to get its bucket label and source, and build (or update) a `ConceptNode` with `decision="defer"`, `review_state="unreviewed"` (the default — never set `"approved"`), `bucket = <bucket label>`, and `bucket_anchor = compute_bucket_anchor(bucket, <bucket source>)`. This is the exact recipe create (step 4) uses and scope-review (step 5) / `check_concept_coverage` (step 6) re-drill — cite it, don't re-specify a different slice. `_replace_detail_deferrals` can keep writing the `detail_deferral_step_ids` step-link **after** the node exists; adjust it (or add a pre-pass) so a missing node is created rather than raising `KeyError` at `nodes[deferral.concept_id]`.
  - **Tag the record and persist.** Set `record_kind = "guide-post"` on the published tree and `plan_fingerprint = compute_plan_fingerprint(plan_path)` (the guide-post loader ignores it for staleness, but `_validate_tree` needs it non-empty). Persist through `save_concepts` — the writer detail already uses. Keep the existing failure arm that, on a persistence error, flips the affected results to `written=False` with the "prior deferral links retained for recovery" reason.

- **Constraints that must hold:**
  - **Never sign.** No path may set `review_state = "approved"` on a deferral — under `-y` or interactively. Detail records pending; scope-review (step 5) is the only signer. This keeps `test_yes_does_not_sign_off_unreviewed_concept` green.
  - **Preserve other pending guide posts.** When extending a loaded guide-post record, carry every existing node forward unmutated — publishing must not drop a bucket the model didn't touch this run.
  - **Anchor round-trip.** `bucket_anchor` must equal `compute_bucket_anchor(bucket, <that bucket's current source>)` so step 5/6's re-drill matches; the bucket label must be the section name `bootstrap_concepts` produces, not a hand-normalized variant.
  - **Re-parse at the tail if you read plan state there.** After the authoring loop, the top-of-run `plan` is stale (each written step round-tripped the plan). If the tail drills buckets, parse the plan body fresh from disk (the auto-split arm's `final_plan` re-parse is the in-file precedent).

## Tests

Add these to `tests/test_detail.py` **with** the implementation — this is a feature step, so every new test must be green before the step is done. Reconcile the existing `TestParseStructuredDetailResponse` and `TestStructuredDetailDeferrals` cases that assume an approved-only, present-record target.

- `test_defers_unreviewed_bucket_records_pending_guide_post` — a detail run naming a current body bucket writes a node with `decision="defer"`, `review_state="unreviewed"`, non-empty `bucket`, and `record_kind="guide-post"`.
- `test_records_pending_guide_post_with_absent_concepts_json` — no `concepts.json` on disk; a deferral creates a fresh guide-post record (the "no pre-materialized tree / absent record" case).
- `test_records_pending_guide_post_on_narrowed_record` — a loaded guide-post record with one pending bucket; a new deferral adds a second and keeps the first.
- `test_bucket_anchor_matches_current_bucket_source` — the stored `bucket_anchor` equals `compute_bucket_anchor(bucket, <current section body>)`, proving the round-trip with steps 5/6.
- `test_yes_does_not_sign_off_new_deferral` — companion to the existing `test_yes_does_not_sign_off_unreviewed_concept`: a newly-recorded `defer` guide post stays `review_state="unreviewed"` under `yes=True`.
- `test_parse_accepts_unreviewed_bucket_owned_or_unowned` — `parse_structured_detail_response` returns the deferral for an unreviewed bucket the step owns and for an unowned one.
- `test_parse_still_accepts_approved_defer_node` — the pre-existing approved-`defer` path still validates (additive relaxation).
- `test_parse_rejects_wrong_step_owner_and_unmentioned_id` — the retained guards still reject a wrong `step_id`, a bucket owned by a different step, and a body whose `## Deferred` omits the id.
- `test_concept_scope_block_lists_proposable_buckets` — `_format_concept_scope_block` renders each proposable bucket's bare id so the model can name it, and keeps the approved-node line format (`decision=include`) intact.
- Confirm the existing `test_concurrent_deferrals_save_once_in_step_order`, `test_valid_deferral_persists_after_detail_write`, `test_failed_regeneration_retains_link_and_old_body`, and `test_dry_run_reports_include_regeneration_without_writes` still pass (adjust their `_save_detail_concept` fixtures only where the approved-only assumption no longer holds).

## Acceptance criteria

- A detail run that defers a current body bucket writes `concepts.json` with a node at `decision="defer"`, `review_state="unreviewed"`, a non-empty `bucket`, and the record's `record_kind == "guide-post"`.
- The same run works with `concepts.json` **absent** and with a **narrowed** guide-post record, preserving any pre-existing pending guide posts.
- The stored `bucket_anchor` equals `compute_bucket_anchor(bucket, <current bucket source>)`.
- No detail path sets `review_state="approved"`; both `test_yes_does_not_sign_off_unreviewed_concept` and the new `test_yes_does_not_sign_off_new_deferral` pass under `yes=True`.
- `parse_structured_detail_response` returns the deferral for an unreviewed bucket owned by or unowned by the step, still returns it for an approved-`defer` node, and still returns `None` on wrong `step_id`, wrong owner, or an id the `## Deferred` section doesn't mention.
- `_format_concept_scope_block` renders every proposable bucket's bare id.
- `uv run pytest tests/test_detail.py -q` is green.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — SHA-256 behind step 1's `compute_bucket_anchor` over the bucket's source text.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — the `ConceptNode` / `ConceptTree` guide-post record this step constructs and mutates.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — the deferral envelope payload and the persisted `detail_deferral_step_ids` metadata.

## Deferred

- **Signing off a pending guide post** — owned by `plan-tool scope-review` (step 5); detail only records pending.
- **Surfacing pending guide posts in `status`, the completeness report, and the create run-summary** — owned by step 7.
- **The prompt template's "Signed-off concept scope" heading** (`plan_tool/prompts/detail.md`) — not in this step's files; the proposable buckets ride in the `${concept_scope_block}` content instead. Route the heading-wording reconciliation to reconcile.
- **Consolidating the two `detail_deferral_step_ids` readers** — `plan_tool/review.py:_structured_concept_deferral_is_valid` still parses the key independently; folding it onto the shared reader is reconcile-owned, not this step.
- **Legacy `full-tree` record migration** — a fresh, non-stale legacy record could still load; detail publishes its new deferral as a guide-post record rather than migrating the whole tree. Leave any deeper legacy handling to reconcile.
