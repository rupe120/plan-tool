> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Let scope-review confirm a flat decision record after unrelated edits, checking bucket existence instead of the plan fingerprint

## Summary

Reshape `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` so it confirms the flat decision record (step 1's `record_kind="decision-record"`) instead of re-deriving a whole concept tree. The command loads the record (step 1 makes `load_concepts` skip the fingerprint staleness check for the flat kind), branches on `record_kind`, and for a flat record signs off exactly the scoped `--concept` decisions, with a bucket check that only **warns** (never blocks) when a scoped node's `bucket` no longer names a current plan body section — so a missing-bucket record stays confirmable, not stranded. The old whole-tree path (`bootstrap_concepts` + `rederive_concepts` + review of a fresh derivation) is **kept for legacy `full-tree` records** (dual-mode, plan Architecture H) so existing records still confirm; only a plan with no record is refused with `SCOPE_REVIEW_INVALID_STATE_EXIT`. On green, an operator can confirm a pending `defer`/`wont_do` after unrelated prose edits (the fingerprint mismatch no longer blocks), a scoped concept whose section was deleted can still be resolved (signed off `wont_do`/`defer` with an advisory warn — not hard-refused, so the surfaced missing-bucket finding is clearable), and unscoped pending nodes in the same record survive the confirm untouched.

## Table of Contents

- [Why](#why) — the whole-tree derivation and fingerprint gate are wrong for a lazily-confirmed flat record
- [Input](#input) — the flat record shape (step 1) and total coverage detector (step 3) this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — one code file, one test file
- [Implementation](#implementation) — branch on record kind, the bucket gate, neutralized fingerprint, refusals
- [Tests](#tests) — confirm-after-edit, missing bucket, unscoped preservation, refusals, conflict exit
- [Acceptance criteria](#acceptance-criteria) — observable behaviors on green
- [References](#references) — argparse / dataclasses / pytest docs
- [Deferred](#deferred) — the shared bucket-lookup helper, legacy migration, direct fresh-defer

## Why

`cmd_scope_review` today confirms decisions by re-deriving the whole concept tree: it calls `bootstrap_concepts` over the current plan body, `rederive_concepts` against the loaded record, and reviews the candidate — a flow built for the hierarchical full-tree record. Two things make it wrong for the lazy model. First, `load_concepts(plan_path, fingerprint)` raises `StaleConceptTreeError` on any `plan_fingerprint` mismatch (`plan_tool/concept_tree.py:load_concepts`), and `cmd_scope_review` maps that to `SCOPE_REVIEW_INVALID_STATE_EXIT` — so a deferral recorded by `create`/`detail` and confirmed *later*, after more edits, dead-ends exactly when the operator tries to sign it off. Second, even past the load, `review_concept_scope` checks `expected_source_state != tree.plan_fingerprint` (`plan_tool/concept_review.py:_validate_request`), so a flat record carrying its write-time fingerprint would be rejected as stale. A flat decision record is an operator decision, not a cache of plan text; its only validity question is whether its `bucket` still points at a real section. This step replaces the whole-tree confirm walk with a per-bucket confirm gate that skips the fingerprint entirely.

## Input

This step reads two sibling steps' outcomes; depend on the outcome, not the mechanism.

- **Flat decision record — step 1.** Step 1 adds `ConceptTree.record_kind` (defaults to the legacy `"full-tree"`; the flat kind is `"decision-record"`) and `ConceptNode.bucket` (defaults `""`), and makes `plan_tool/concept_tree.py:load_concepts` skip the `StaleConceptTreeError` fingerprint check for a `decision-record` while still raising it for a `full-tree` record and raising `InvalidConceptTreeError` on a malformed record. A flat node carries a non-empty `bucket`, an empty `parent_path`, and a `decision` of `defer`/`wont_do`. Read those field names and load behavior; do not restate step 1's decoder/validator work.
- **Body-section name lookup — the bucket target.** The `bucket` is a coarse section-level tag equal to the normalized H2 name that `plan_tool/parser.py:parse_body_sections` produces as `BodySection.name` (lowercased, trailing `:`/`.` stripped). The bucket-existence gate reads the current plan body's section names through this same helper so its "gone" verdict agrees with step 3's.
- **Total coverage detector — step 3.** Step 3 makes `plan_tool/review.py:check_concept_coverage` total and adds the same name-lookup bucket check that produces the non-blocking `concept-bucket-missing` finding. This step uses the *same* rule (`bucket in current section names`) at confirm time, but its action is an **advisory `warn` that still lets the confirm proceed**, not a block — step 3 surfaces the missing bucket, and this step lets the operator clear it. See [Deferred](#deferred) for consolidating the two lookups into one helper.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/scope_review_cmd.py` — in `cmd_scope_review`: branch after `load_concepts` on `record_kind`; **keep** the existing `bootstrap_concepts` + `rederive_concepts` + review block for the `full-tree` branch (unchanged); add the new flat path (include-decision refusal, per-bucket existence check, neutralized-fingerprint sign-off, existing `synchronize_concepts` persistence) for the `decision-record` branch; refuse only a no-record plan with `SCOPE_REVIEW_INVALID_STATE_EXIT`.
  - `tests/cli/test_scope_review_cmd.py` — keep the whole-tree tests (legacy path is unchanged behavior — they must stay green); add the flat-path tests: confirm-after-edit, missing-bucket-resolves, unscoped-preservation, include-refusal, no-record refusal, and a `legacy-full-tree-still-confirms` case asserting the old path still works.

## Implementation

**Branch on record kind right after the load, then take one of three paths.** Keep the current preamble (`_load_context`, `resolve_plan_for_context`, `source_plan_text = plan_path.read_text(...)`, `plan = parse_plan(plan_path)`, `fingerprint = compute_plan_fingerprint(plan_path)`, `slug`). Keep the existing `try/except (InvalidConceptTreeError, StaleConceptTreeError)` around `load_concepts` — a malformed record still returns `SCOPE_REVIEW_INVALID_STATE_EXIT`, and a legacy `full-tree` record whose fingerprint drifted still raises there. After the load succeeds, dispatch:

- **No record (`original_tree is None`)** — refuse with `SCOPE_REVIEW_INVALID_STATE_EXIT` and a clear `warn` (there is nothing to confirm; `create`/`detail` are the producers of pending decisions). This replaces the old "bootstrap a fresh tree and persist it" behavior — scope-review no longer mints a record from nothing.
- **Legacy full-tree (`original_tree.record_kind == "full-tree"`)** — **keep the existing confirm path** (dual-mode, plan Architecture H): `bootstrap_concepts` over the current plan body, `rederive_concepts` against the loaded record, `review_concept_scope` on the candidate — the flow that confirms deferrals on full-tree records today. Do **not** refuse it: this repo already holds full-tree records (the shipped concept plans, archived `concept-write-integrity`/`concept-remediation-*`), and refusing would strip their ability to confirm deferrals until #131 migration. So `cmd_scope_review` retains its current bootstrap+rederive+review block *for the full-tree branch only*; the new flat path below is an additional branch, not a replacement. (Keep the `bootstrap_concepts`/`rederive_concepts` import — it's still used by this branch.)
- **Flat record (`original_tree.record_kind == "decision-record"`)** — the confirm path below.

**The flat confirm path — gate, then sign off, then persist through the existing writer.** Order matters: run every refusal check *before* any candidate is built or written, so a rejected request leaves both artifacts untouched (the same fail-fast the invalid-record case already gives).

1. **Reject an `include` decision.** A flat record can only hold `defer`/`wont_do` (step 1's flat validation). If any scoped `--decision` is `include`, refuse with `SCOPE_REVIEW_INVALID_STATE_EXIT` and a message naming the concept — a targeted pre-check gives an actionable error instead of letting `synchronize_concepts`'s `_validate_tree` reject the assembled tree with an opaque one. Read the decision values off `args.decision` (a list of `(concept_id, decision)` pairs).
2. **Per scoped concept, resolve the node and gate its bucket.** Build the current section-name set once — `{section.name for section in parse_body_sections(split_plan_document(source_plan_text).body)}` — and a lookup `{node.id: node for node in original_tree.concepts}`. For each `--concept` id:
   - **Unknown id** (not in the record) → refuse `SCOPE_REVIEW_INVALID_STATE_EXIT`. (`review_concept_scope` would also reject an unknown id, but resolving the node first is what lets the bucket check run and keeps the message specific.)
   - **Bucket gone** (`node.bucket` not in the current section-name set) → **do not refuse the confirm** — resolving a missing-bucket record is exactly what step 3's surfaced `concept-bucket-missing` finding asks the operator to do, so hard-refusing here would strand it as a non-clearable standing finding (the plan's `[missing-bucket-resolution]` fix). Allow the sign-off to proceed for a `defer`/`wont_do` decision, emitting a `warn` that names the concept and its missing bucket (so the operator knows the section is gone); `wont_do` is the natural clear-it choice since the deferred thing's home no longer exists. A full **dismiss/remove** (drop the record) is deferred to BACKLOG #132; here the operator resolves it by deciding it. The bucket check thus drives *surfacing* (step 3) and an *advisory warn* here, not a confirm-time refusal.
3. **Sign off with a neutralized fingerprint check.** Call `review_concept_scope(original_tree, concept_ids, decisions, original_tree.plan_fingerprint, sign_off=True)`. Passing `original_tree.plan_fingerprint` (the record's own stored value) as `expected_source_state` makes `_validate_request`'s `expected_source_state != tree.plan_fingerprint` a deliberate no-op — the whole-bundle staleness check is intentionally satisfied because the per-bucket gate in step 2 is the real currency check. **Pass the full loaded record as the candidate**, not a subset built from the scoped ids: `review_concept_scope` deep-copies it and signs off only the scoped nodes, so every unscoped pending node stays `review_state="unreviewed"` and survives the republish. Wrap the call in the existing `try/except ConceptReviewError` → `SCOPE_REVIEW_INVALID_STATE_EXIT`.
4. **Persist through `synchronize_concepts` unchanged.** Reuse the existing call — `synchronize_concepts(plan_path, plan, original_tree, reviewed_tree, source_plan_text=source_plan_text)` — and the existing result handling that maps `SyncStatus.SOURCE_DIVERGENCE`/`MAPPING_CONFLICT` to `SCOPE_REVIEW_CONFLICT_EXIT` and everything else to `SCOPE_REVIEW_INVALID_STATE_EXIT`. `synchronize_concepts` already works for a flat record: flat nodes have no `step_id`, so `_mapped_scopes` yields an empty mapping; `render_scope_decisions` renders the approved `defer`/`wont_do` nodes into `## Deferred` / `## Out of scope`; and it re-fingerprints the stored record to the current plan, which is harmless because load ignores that fingerprint for the flat kind. Keep the success message.

**Constraints and gotchas:**

- **Do not touch `synchronize_concepts`, `review_concept_scope`, or `load_concepts`.** They are out of this step's files. The flat behavior comes from *how* `cmd_scope_review` calls them (record as candidate, record's own fingerprint as `expected_source_state`), not from changing them.
- **Keep the exit-code contract.** `SCOPE_REVIEW_CONFLICT_EXIT = 3` for a sync divergence/mapping conflict; `SCOPE_REVIEW_INVALID_STATE_EXIT = 4` for every refusal (invalid/malformed record, no record, include, unknown id, review error). A **legacy full-tree record is not a refusal** — it takes the kept legacy confirm path (dual-mode). A **missing bucket is not a refusal** — it warns and proceeds (above). Every refusal must write nothing.
- **Keep all imports.** `bootstrap_concepts` and `rederive_concepts` are still used by the retained `full-tree` branch (dual-mode); `parse_body_sections` / `split_plan_document` feed the flat branch's bucket check; `parse_plan` feeds `synchronize_concepts`. Nothing is dead now.
- **Match step 3's extraction exactly.** The bucket "gone" verdict must key on the same normalized `BodySection.name` step 3 uses, or the confirm gate and the `concept-bucket-missing` finding could disagree on the same record. Reuse `parse_body_sections`; do not hand-roll a different section split or normalization.

**Alternative rejected:** *refusing* a legacy `full-tree` record. It reads as clean (single model), but this repo already holds full-tree records (the shipped concept plans, archived `concept-write-integrity`/`concept-remediation-*`), so refusing would strip their ability to confirm deferrals until #131 migration — a silent regression on exactly the deferrals this plan protects. Dual-mode (keep the legacy path, add the flat path) is the coherent choice; the two persistence models coexist only until #131 retires the legacy shape.

## Tests

All in `tests/cli/test_scope_review_cmd.py`. Add a small helper that writes a flat `decision-record` sidecar for a plan (a hand-built `ConceptTree(record_kind="decision-record", ...)` saved via `save_concepts`, or raw JSON at `concepts_path`) so the confirm cases start from a real pending record.

- `test_scope_review_confirms_flat_decision_after_unrelated_edit` — flat record with an unreviewed `defer` node whose `bucket` names an existing section; edit an *unrelated* section so the plan fingerprint changes; scope-review confirm → exit 0, the node is `review_state="approved"`, the plan `## Deferred` renders the decision, and the unrelated edit is preserved. This is the title behavior.
- `test_scope_review_confirms_after_edit_to_own_bucket_body` — the deferral's **own** bucket section has its *body* rewritten (but not its H2 name); confirm → exit 0, no missing-bucket warn (the lookup keys on the section name, so a body edit does not read as a missing bucket). Pins the plan-wide "an edit to a section's *body* leaves the record valid" risk (`bucket-body-edit-noise`).
- `test_scope_review_flat_missing_bucket_resolves_with_warn` — a flat record whose `bucket` names a deleted/renamed section is **still resolvable**: `scope-review --concept <id> wont_do` signs it off (exit 0, not `SCOPE_REVIEW_INVALID_STATE_EXIT`), emits a warn naming the missing bucket, and renders it into `## Out of scope`; the surfaced `concept-bucket-missing` finding is thereby clearable.
- `test_scope_review_flat_preserves_unscoped_pending_nodes` — flat record with two unreviewed nodes; confirm only one → the confirmed node is approved and rendered, the other stays `review_state="unreviewed"` in the sidecar and is not dropped or rendered.
- `test_scope_review_flat_include_rejected` — flat record, `--decision id=include` → `SCOPE_REVIEW_INVALID_STATE_EXIT`, no writes.
- `test_scope_review_no_record_refused` — no `concepts.json` → `SCOPE_REVIEW_INVALID_STATE_EXIT`, no writes (reworks `test_scope_review_bootstraps_and_persists_scoped_result`, which asserted the removed full-tree bootstrap).
- `test_scope_review_legacy_full_tree_still_confirms` — a `record_kind="full-tree"` sidecar takes the kept legacy bootstrap+rederive+review path and confirms a deferral successfully (no `SCOPE_REVIEW_INVALID_STATE_EXIT`), proving dual-mode does not regress existing records.
- `test_scope_review_flat_sync_conflict_maps_to_conflict_exit` — flat confirm where `synchronize_concepts` returns `SyncStatus.SOURCE_DIVERGENCE` (monkeypatch `scope_review_cmd.synchronize_concepts`) → `SCOPE_REVIEW_CONFLICT_EXIT`, no writes. (The existing full-tree derivation-conflict test stays green — its `rederive_concepts` path is retained by the legacy branch, not removed.)
- Keep unchanged: `test_scope_review_invalid_record_has_distinct_exit_and_writes_nothing` (broken JSON → `InvalidConceptTreeError` → exit 4) and `test_scope_review_parser_rejects_malformed_decision`.

### Test-creation order (feature step)

This is a **feature** step. Add each test alongside the code path it covers: the confirm-after-edit and missing-bucket tests with the flat confirm branch, the refusal tests with the record-kind dispatch, and the sync-conflict test with the persistence-result handling. Green-before-done gate: every new and reworked test in `tests/cli/test_scope_review_cmd.py` must pass before this step is finished; run `uv run pytest tests/cli/test_scope_review_cmd.py -q`.

## Acceptance criteria

- `cmd_scope_review` returns `0` when confirming a scoped `defer`/`wont_do` on a `decision-record` whose `bucket` still names a current section, even after the plan text (and thus the fingerprint) changed since the record was written.
- Confirming sets the scoped node's `review_state` to `"approved"` and renders the decision into the plan's `## Deferred` / `## Out of scope` section via the existing `synchronize_concepts` path.
- A scoped concept whose `bucket` no longer names a current section **still resolves**: `cmd_scope_review` signs off the `defer`/`wont_do` (exit `0`) with an advisory `warn`, and does **not** return `SCOPE_REVIEW_INVALID_STATE_EXIT` — so the surfaced `concept-bucket-missing` finding is clearable (dismiss verb → #132).
- Unscoped pending nodes in the same flat record keep `review_state="unreviewed"` after a partial confirm.
- A **legacy `full-tree` record still confirms** via the kept bootstrap+rederive+review path (exit `0` on success) — it is **not** refused (dual-mode, Architecture H), so no existing full-tree record loses confirmation ability.
- A no-record plan, an `include` decision, and an unknown concept id each return `SCOPE_REVIEW_INVALID_STATE_EXIT` with no writes.
- A `synchronize_concepts` divergence/mapping conflict returns `SCOPE_REVIEW_CONFLICT_EXIT` with no writes.
- `bootstrap_concepts` and `rederive_concepts` remain imported and are exercised by the retained `full-tree` branch (they are **not** removed — dual-mode).
- `uv run pytest tests/cli/test_scope_review_cmd.py -q` passes.

## References

- [argparse — Parser for command-line options (Python 3.13)](https://docs.python.org/3/library/argparse.html) — for the `--concept` / `--decision` wiring and the `_decision` pair type this command already uses.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — for reading the `ConceptTree`/`ConceptNode` fields (`record_kind`, `bucket`, `review_state`) the branch keys on.
- [pytest — full documentation](https://docs.pytest.org/en/stable/) — for the monkeypatch-based sync-conflict test and the confirm-after-edit fixtures.

## Deferred

- **A shared `bucket in current section names` helper** — the same name-lookup lives in `plan_tool/review.py:check_concept_coverage` (step 3, the `concept-bucket-missing` finding) and here as the confirm gate. Consolidating both onto one helper is a cross-module refactor `detail` cannot mint; route it to reconcile. This step reuses `parse_body_sections` so the two agree today.
- **Migrating a legacy `full-tree` record to a flat decision record** — dual-mode *keeps* the legacy confirm path (no regression); converting legacy records to the flat shape is out of scope for the MVP and tracked in BACKLOG #131.
- **Directly deferring a not-yet-proposed concept via scope-review** — scope-review is confirm-only over records `create`/`detail` write; minting a fresh flat record from a bare concept id is not added here. Track as follow-up if operators need it.
- **A dismiss/re-home verb for a decision whose bucket is gone** — this step lets the operator *clear* a missing-bucket record by deciding it (`wont_do`), but an active **dismiss/remove** (drop the record without a decision) is deferred to BACKLOG #132.
