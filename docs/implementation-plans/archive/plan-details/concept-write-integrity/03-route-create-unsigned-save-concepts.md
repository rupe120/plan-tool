# Step 3 — Route create's unsigned save_concepts fallbacks through synchronize_concepts

## Summary

Replace the two direct `save_concepts` writes in `plan_tool/create.py:create_plan` — the `else` arm below the `signed_concept_scope` check and the `elif budget.enabled` arm just before `return CreateResult(...)` — with calls to `plan_tool/concept_sync.py:synchronize_concepts`, which step 1 taught to handle unsigned trees (sidecar-only publication, plan file untouched). The key design decision is that the caller stops computing the fingerprint itself: the sync's unsigned arm owns it, and step 1 pins that its stored value equals `compute_plan_fingerprint(plan_path)`, so the on-disk result is unchanged. On green, `create.py` no longer imports `save_concepts` at all, every concept sidecar write from create flows through the guarded synchronizer, and the existing unsigned-create and resume tests pass unmodified. Files: `plan_tool/create.py` and `tests/test_create.py`.

## Table of Contents

- [Summary](#summary) — what the step does and the main design decision
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — why the direct writes exist and why they can go now
- [Input](#input) — the step-1 contract and serialization equalities this routing rests on
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched and the edits per file
- [Implementation](#implementation) — the two call sites, the recommended call shapes, and the parts that must not vary
- [Tests](#tests) — characterization tests first, then the new routing tests
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [Deferred](#deferred) — the sibling direct writers and the guard test owned by steps 4–5

## Why

`create_plan` bypasses the designed single writer on its unsigned path because, before step 1, `synchronize_concepts` erased `## Deferred` / `## Out of scope` prose for a tree with no approved node. The two bypasses persist the sidecar with `save_concepts` after hand-computing `plan_fingerprint` via `compute_plan_fingerprint` — duplicating the fingerprint logic and skipping every validation and compare-and-swap guard the synchronizer runs. Step 1 removed the reason for the bypass: an unsigned tree now takes a sidecar-only arm that leaves the plan file untouched while still running all the guards. This step deletes the create-side duplicates so the sidecar has one writer from create, which is the precondition for step 5's no-writer-outside-`concept_sync` guard test.

## Input

- **Step 1's unsigned arm** (`plan_tool/concept_sync.py:synchronize_concepts`): when no concept in `reviewed_tree` has `review_state == "approved"`, the function publishes only the `concepts.json` sidecar, never touches the plan file, skips `refresh_plan_provenance`, and stores a fingerprint of the current on-disk plan bytes. Step 1 pins the equality `sync_result.plan_fingerprint == compute_plan_fingerprint(plan_path)` in `tests/test_concept_sync.py` — that equality is what makes this step a pure call-site swap. The signature and `ConceptSyncResult` field set are frozen by step 1's acceptance criteria; mode detection is a predicate over the tree, never a caller flag.
- **`ConceptSyncResult`** (`plan_tool/concept_sync.py`): `status` (a `SyncStatus`), `message`, `plan_fingerprint`, `rollback_error`, plus the `succeeded` property. On the unsigned success path `plan_fingerprint` is set; on any failure the sync has already rolled its own publication back.
- **Sidecar serialization equality**: `plan_tool/concept_tree.py:save_concepts` writes `json.dumps(asdict(tree), indent=2, allow_nan=False) + "\n"` — the same bytes `synchronize_concepts` builds for both its `expected_sidecar` compare-and-swap value and its published sidecar. This equality is what lets the iterate-tail call pass the in-memory tree as `original_tree` and have the sidecar compare pass against what the first call wrote.
- **Call-site state in `create_plan`**: at the post-write site, the sidecar never exists on disk (a colliding or resumed plan's bundle was already moved by `archive_existing_source` before `write_new_plan`), so `original_tree=None` is correct — the signed arm in the same branch already relies on this. At the iterate-tail site, the sidecar written by the first call is on disk and `concept_tree` is not mutated between the two sites.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — replace the two unsigned fallback bodies with `synchronize_concepts` calls; drop `save_concepts` from the `plan_tool.concept_tree` import block (keep `concepts_path`, still used by the signed failure cleanup); remove the two function-local `compute_plan_fingerprint` imports inside the fallback arms (the resume-load site near `load_concepts` and the apply-verdict telemetry site keep theirs — those are reads, not writers).
  - `tests/test_create.py` — add the characterization and routing tests listed below; existing concept-integration tests stay unmodified.

## Implementation

Two call sites change, each mirroring the signed call already sitting in the same branch.

**Post-write site** — the `else` arm below the `signed_concept_scope` check (currently: deepcopy, `compute_plan_fingerprint`, `save_concepts`):

- Read the plan text fresh and call the sync the way the signed arm above it does: `synchronize_concepts(plan_path, parsed_written_plan, None, concept_tree, source_plan_text=...)`. `original_tree=None` because no sidecar exists at this point in any create flow (see Input).
- On success, mirror the signed arm's tail: deepcopy `concept_tree` and set `plan_fingerprint` from `sync_result.plan_fingerprint`. Step 1's pinned equality makes this the same value the arm computes today, so the resume flow's `load_concepts(prospective_plan_path, compute_plan_fingerprint(...))` check still passes on the next create.
- On failure, raise `CreateError(f"failed to synchronize concepts: {sync_result.message}")`. Recommended: share the signed arm's cleanup (unlink `concepts_path(plan_path)` and `plan_path` under `contextlib.suppress(FileNotFoundError)`) so both arms have one failure contract. This deliberately normalizes an error path — today a failed `save_concepts` propagates a raw `OSError` and leaves the unregistered plan file behind — and it matches what step 2's restore handler expects (it tolerates already-absent files). If you prefer strict minimalism, raise without the unlinks; the raise itself is the part that is not optional, because step 2's restore window fires on an exception escaping this region.
- Skip the signed arm's post-sync reparse: the unsigned arm never touches the plan file, so `parsed_written_plan` is still the bytes on disk.

**Iterate-tail site** — the `elif budget.enabled` arm after `advise_path_issues`, just before `return CreateResult(...)` (currently: `parse_plan`, `compute_plan_fingerprint`, `save_concepts`):

- Mirror the signed `if budget.enabled and signed_concept_scope` arm above it: reparse the plan, read its text fresh, and call `synchronize_concepts(plan_path, <reparsed plan>, concept_tree, concept_tree, source_plan_text=...)`. Passing the in-memory tree as `original_tree` works because its serialization equals the sidecar the post-write call published (see Input) — the same reasoning the signed arm already uses.
- On failure, raise `CreateError` like the signed sibling — no unlinks here; the manifest commit (`append_to_manifest`) has already happened, so the plan is validly registered and must survive (the same boundary step 2 pins with its past-commit negative test).
- The compare-and-swap is a new, correct refusal at this site: if something rewrote the sidecar mid-loop, the sync returns `SOURCE_DIVERGENCE` instead of silently overwriting. Nothing in the convergence loop writes the sidecar today, so behavior is identical on every current path.

**Parts that must not vary:**

- **The sync owns the fingerprint.** Do not compute `compute_plan_fingerprint` in either arm before the call — deleting the caller-side computation is the point of the step. `concept_tree` still carries its existing non-empty bootstrap fingerprint (the `concept_fingerprint` hash set near `bootstrap_concepts`), which is what lets it pass `_validate_tree` on the way in.
- **No new parameters, no mode flag.** Step 1 detects unsigned state from the tree itself. `create_plan` keeps its local `signed_concept_scope` predicate only to pick the failure-handling tail, not to tell the sync which mode to run.
- **Ordering holds.** The post-write call stays before `append_to_manifest` (inside step 2's restore window); the iterate-tail call stays gated on `budget.enabled` and after `advise_path_issues`.
- **On-disk success result is unchanged.** Sidecar bytes, stored fingerprint, and the untouched plan file must all match what the direct writes produce today — the characterization tests below are the proof.

The step's core rule — persist the concept sidecar only through the guarded synchronizer — has two more production call sites: `plan_tool/detail.py` (the `save_concepts` call in its deferral-persistence tail) and `plan_tool/scope_out.py` (the `save_concepts` call near the end of its narrow flow). Both are owned by later steps; see Deferred.

## Tests

All in `tests/test_create.py`, alongside `TestCreatePlanConceptIntegration`.

### Test-creation order (refactor step)

Write or confirm these characterization tests **first**, against the current direct-write implementation, and require them to stay green **unmodified** after the routing:

- `test_retains_deterministic_concepts_and_uses_independent_invoker` (exists) — pins that an unsigned create writes an all-unreviewed sidecar whose fingerprint satisfies `load_concepts(plan_path, compute_plan_fingerprint(plan_path))`.
- `test_resume_reuses_saved_concepts_without_enrichment` (exists) — pins that the stored fingerprint passes the resume load's stale check on a second create of the same slug.
- `test_core_sync_failure_leaves_no_plan_or_manifest` (exists) — pins the signed arm's failure contract, which must not change.
- `test_unsigned_create_preserves_seed_scope_prose` (new, write before refactoring) — an unsigned create from a seed carrying `## Deferred` / `## Out of scope` text writes a plan that still contains that prose; this is the erasure bug the plan exists for, proven safe end-to-end through the new routing.
- `test_unsigned_iterate_tail_refreshes_sidecar_fingerprint` (new, write before refactoring) — an unsigned create with a non-default enabled `budget=` ends with the sidecar fingerprint equal to `compute_plan_fingerprint` of the final plan bytes.

Then land the routing, keep the five above green, and add the routing-specific tests:

- `test_unsigned_create_sync_failure_raises_create_error` — monkeypatch `plan_tool.create.synchronize_concepts` to return a failed `ConceptSyncResult` on an unsigned create; assert `CreateError` matching "failed to synchronize concepts", and (if the recommended shared cleanup is adopted) no plan file, no sidecar, no manifest entry — the unsigned twin of `test_core_sync_failure_leaves_no_plan_or_manifest`.
- `test_unsigned_iterate_tail_sync_failure_keeps_registered_plan` — a failed sync at the iterate-tail site raises `CreateError` but leaves the plan file and its manifest entry intact (the window closed at `append_to_manifest`).
- `test_unsigned_create_calls_synchronize_once_per_site` — a recording wrapper around the real `synchronize_concepts` sees exactly one call on a plain unsigned create and two when `budget` is enabled, each with an unsigned `reviewed_tree`.

## Acceptance criteria

- `grep -n "save_concepts" plan_tool/create.py` returns nothing — no call and no import.
- The only `compute_plan_fingerprint` uses left in `plan_tool/create.py` are the resume-load read (beside `load_concepts`) and the apply-verdict telemetry read.
- An unsigned create writes `concepts.json` with every node `unreviewed` and `load_concepts(result.plan_path, compute_plan_fingerprint(result.plan_path))` returns the tree.
- An unsigned create from a seed with `## Deferred` / `## Out of scope` prose ships a plan still containing that prose.
- A failed unsigned sync before the manifest commit raises `CreateError` and leaves no usable partial outputs; a failed unsigned sync at the iterate tail raises `CreateError` and leaves the registered plan in place.
- The five characterization tests pass unmodified; the full suite (`uv run pytest tests/ -q`) is green.

## Deferred

- Routing `plan_tool/detail.py`'s `save_concepts` call (deferral persistence) through `synchronize_concepts` — owned by step 4.
- Routing `plan_tool/scope_out.py`'s `save_concepts` call (carved-tree save in the narrow flow) through `synchronize_concepts` — owned by step 5.
- The no-writer-outside-`concept_sync` guard test (source scan asserting no production `save_concepts` call outside `plan_tool/concept_sync.py`) — owned by step 5; this step merely makes `create.py` pass it.
- Restore-on-failure for the collision-archive window that wraps these call sites — owned by step 2; this step only guarantees a failed sync raises so that window fires.
