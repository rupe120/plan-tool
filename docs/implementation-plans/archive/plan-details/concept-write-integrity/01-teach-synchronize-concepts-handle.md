# Step 1 — Teach synchronize_concepts to handle unsigned scope state without erasing scope prose

## Summary

Add an unsigned arm to `plan_tool/concept_sync.py:synchronize_concepts()`: when no concept in the reviewed tree is approved, the synchronizer publishes only the `concepts.json` sidecar and leaves the plan file — including its `## Deferred` and `## Out of scope` prose — completely untouched, while still running every validation and compare-and-swap guard the signed path runs. The key design decision is a whole-tree signed/unsigned gate (mirroring `create.py`'s `signed_concept_scope` predicate) rather than a per-section skip, so signed behavior stays exactly as it is. On green, an unsigned tree can be persisted through the canonical synchronizer with the same on-disk result create's direct `save_concepts` fallback produces today, which is what lets steps 3–5 route the three direct sidecar writers through this function. Files: `plan_tool/concept_sync.py` and `tests/test_concept_sync.py`.

## Table of Contents

- [Summary](#summary) — what the step does and the main design decision
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — the erasure bug that forces callers to bypass the synchronizer
- [Input](#input) — the persisted contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched and the edits per file
- [Implementation](#implementation) — the unsigned arm's contract, the recommended shape, and the parts that must not vary
- [Tests](#tests) — new unit tests and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [Deferred](#deferred) — the caller routing and guard test owned by later steps

## Why

`synchronize_concepts()` is the designed single writer that keeps plan prose, rendered scope, and the concept record aligned — but today it only handles signed trees. `render_scope_decisions()` renders only nodes with `review_state == "approved"`, so for a tree with no approved node it returns empty strings for both owned sections, and `replace_body_sections()` (`plan_tool/parser.py`) then replaces each matched section body with a bare newline — erasing whatever `## Deferred` / `## Out of scope` prose the plan already had. That erasure is the reason `create_plan()` bypasses the synchronizer on its unsigned path and calls `save_concepts` directly (the `else` arm below the `signed_concept_scope` check in `plan_tool/create.py`, and the matching `elif budget.enabled` arm near the end of `create_plan`). Those bypasses are two of the three direct writers this plan exists to eliminate; steps 3–5 can only route them through `synchronize_concepts` once it handles unsigned state safely.

## Input

- **Concept sidecar contract** (`plan_tool/concept_tree.py:ConceptNode`, documented in `DATA_CONTRACT.md`): `plan_tool/concept_tree.py:ConceptNode.review_state` ranges over `CONCEPT_REVIEW_STATES` = `{"unreviewed", "approved", "rejected"}`; `decision` uses `include` / `defer` / `wont_do`. The unsigned predicate reads `review_state` only.
- **Plan document contract** (`plan_tool/parser.py`): `split_plan_document`, `parse_body_sections`, and `replace_body_sections` define the owned-section compare-and-swap the function already performs; the owned sections are the two normalized names `"deferred"` and `"out of scope"`.
- **Fingerprint framing** (`plan_tool/review_persistence.py:compute_plan_fingerprint`): plan bytes, then each `plan-details/<slug>/*.md` detail file framed as `name\0content`, sorted by name. `plan_tool/concept_sync.py:_fingerprint` applies the same framing to staged bytes — this equality is what makes the unsigned arm's stored fingerprint identical to what `plan_tool/create.py`'s fallback computes via `compute_plan_fingerprint(plan_path)`.
- **Caller expectations for steps 3–5**: `plan_tool/create.py`'s unsigned arms persist the tree with a fingerprint of the current on-disk plan and never touch the plan file. The unsigned arm must reproduce that on-disk result so the later routing steps are behavior-preserving.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/concept_sync.py` — add the signed/unsigned gate inside `synchronize_concepts()` and the unsigned publication arm (sidecar-only publish, current-bytes fingerprint, sidecar-only rollback). Optionally a small module-level helper (e.g. `_has_signed_decision(tree)`) so step 3's caller can reuse the same predicate.
  - `tests/test_concept_sync.py` — extend the `_node` helper to accept a `review_state` argument (it currently hardcodes `"approved"`), and add the unsigned-arm tests listed below.

## Implementation

The behavior change: `synchronize_concepts()` gains two modes keyed on whether any concept is signed, with the signed mode unchanged.

- **Unsigned predicate — mirror create's.** A tree is unsigned when no node has `review_state == "approved"` — the same predicate as `signed_concept_scope` in `plan_tool/create.py` (computed just before its first `synchronize_concepts` call). Compute it from `reviewed_tree`. A rejected alternative was a per-section gate (skip replacing only sections whose rendered replacement is empty): that would also change *signed* behavior — a signed tree whose approved decisions are all `include` must still be able to clear a stale section, because for signed state the record is the authority.
- **Signed input: no behavior change.** Every existing branch — scope mapping, owned-section replacement, plan re-render, dual publication, rollback — stays as it is. All five existing tests in `tests/test_concept_sync.py` must pass unchanged.
- **Unsigned input: all guards still run, then sidecar-only publication.** In order:
  - `_validate_tree(reviewed_tree)`, the `_mapped_scopes` call (an unsigned tree yields an empty mapping, since `_accepted_decisions` iterates approved nodes only), the plan/sidecar read, the frontmatter + owned-section divergence check against `source_plan_text`, and the sidecar compare against `original_tree`'s serialization all behave exactly as on the signed path. Unsigned state weakens none of the compare-and-swap.
  - **Do not rewrite the plan file.** Skip `replace_body_sections`, `render_plan_text`, and the plan `publish`. This is the constraint that fixes the bug — but it is also *stronger* than "don't erase the sections": routing an unsigned tree through `render_plan_text` anyway (with pass-through section bodies) was rejected because it re-serializes the frontmatter from `plan_snapshot`, so a sidecar-only persistence could still change plan bytes through YAML normalization.
  - **Fingerprint the current plan bytes**: `_fingerprint(path, current_plan_text.encode("utf-8"))`. Because `_fingerprint` applies `compute_plan_fingerprint` framing and the plan bytes are unchanged, this equals `compute_plan_fingerprint(path)` — pin that equality in a test, since step 3 relies on it to make the create routing behavior-preserving.
  - Build the final tree the same way the signed path does: deep-copy `reviewed_tree`, `replace(...)` the fingerprint in, `_validate_tree`, serialize with `json.dumps(asdict(final_tree), indent=2, allow_nan=False) + "\n"`.
  - **Publish only the sidecar**, through the same injected `publish` seam (default `_atomic_publish`). On publication failure, restore the prior sidecar (`_restore` with `current_sidecar_text` — which unlinks when the sidecar didn't exist) and return `PUBLICATION_FAILURE`. The plan never entered `published`, so no plan restore is needed; keep the existing rollback loop's shape so the failure arm stays one code path for both modes if that reads cleaner — the observable contract is what matters, not the exact branch layout.
  - Return `SUCCESS` with `plan_fingerprint` set, same as the signed path. Keep `ConceptSyncResult`'s field set unchanged — steps 3–5 consume it as-is; if a caller later needs to distinguish sidecar-only success, that is a decision for the routing steps.
- **Skip `refresh_plan_provenance` on the unsigned success arm** (recommended). Provenance records the last frontmatter the tool *published* for a path; the unsigned arm publishes no plan text and leaves the on-disk frontmatter unchanged, so any existing provenance entry stays valid and there is nothing new to record.
- **Shared-logic note.** The rule this step adds — "unsigned trees persist the sidecar only and never touch plan prose" — is implemented inline today at the two `create.py` fallback arms (`save_concepts` after `compute_plan_fingerprint`), and the other two direct writers (`plan_tool/detail.py`, the `save_concepts` call in its deferral-persistence path; `plan_tool/scope_out.py`, the `save_concepts` call inside `apply_narrow`'s concept handling) will also depend on this arm. Do not modify those call sites here — steps 3, 4, and 5 own the routing (see Deferred).

Gotchas that are not free to vary:

- **Signature stays put.** `synchronize_concepts(plan_path, plan_snapshot, original_tree, reviewed_tree, *, source_plan_text=None, publish=_atomic_publish)` is the seam the three later routing steps target; don't add required parameters. The mode must be detected from `reviewed_tree`, not passed by the caller — a caller-supplied flag could disagree with the tree.
- **Sidecar serialization must stay byte-compatible** with what `save_concepts` and the compare-and-swap's `expected_sidecar` expression produce (`json.dumps(asdict(...), indent=2, allow_nan=False) + "\n"`), or the next sync's divergence check would false-positive.
- **`_atomic_publish` and `_restore` stay as they are** — this step adds no new publication mechanics.

## Tests

All in `tests/test_concept_sync.py`. The `_node` helper needs a `review_state` parameter (default `"approved"` to keep existing tests untouched).

- `test_unsigned_tree_sync_preserves_scope_prose_and_plan_bytes` — a tree of only `unreviewed` nodes (including one with `decision="defer"`) syncs with `SUCCESS`, the plan file bytes are unchanged, and the existing `## Deferred` prose is still present.
- `test_unsigned_tree_sync_maps_no_step_scopes` — an unreviewed node with a `step_id` mapping does not change that step's `scope` on disk.
- `test_unsigned_tree_sync_writes_sidecar_with_current_plan_fingerprint` — the sidecar is written and its stored `plan_fingerprint` equals `compute_plan_fingerprint(path)`.
- `test_unsigned_tree_sync_still_detects_owned_section_divergence` — a concurrent edit to the `## Deferred` body between snapshot and sync returns `SOURCE_DIVERGENCE` with no writes.
- `test_unsigned_tree_sync_still_detects_sidecar_divergence` — a current sidecar that differs from `original_tree`'s serialization returns `SOURCE_DIVERGENCE` with no writes.
- `test_unsigned_sidecar_publication_failure_restores_prior_sidecar` — a failing injected publisher returns `PUBLICATION_FAILURE`, the prior sidecar bytes are restored, and the plan file is untouched.
- `test_unsigned_sidecar_publication_failure_without_prior_sidecar_leaves_none` — with `original_tree=None` and no sidecar on disk, a failing publisher leaves no sidecar file behind.
- `test_mixed_tree_takes_signed_path` — a tree with one approved `defer` plus one unreviewed node re-renders the owned sections (signed behavior), and the unreviewed node neither renders into a section nor maps a step scope.

### Test-creation order (feature step)

This is a feature step: add the tests above together with the implementation, in the same change. Gate: every new test green, and the five pre-existing tests in `tests/test_concept_sync.py` green without modification (beyond the backward-compatible `_node` helper default), before this step is considered done.

## Acceptance criteria

- `synchronize_concepts()` with a tree containing no `approved` node returns `SUCCESS`, writes `concepts.json`, and leaves the plan file's bytes unchanged — the `## Deferred` and `## Out of scope` bodies are exactly what they were before the call.
- The unsigned arm's stored `plan_fingerprint` equals `plan_tool/review_persistence.py:compute_plan_fingerprint(plan_path)` for the same on-disk state.
- The unsigned arm still returns `SOURCE_DIVERGENCE` on a changed owned section, changed frontmatter, or changed sidecar, and `INVALID_STATE` on a tree that fails `_validate_tree` — with no file written in any of those cases.
- A sidecar publication failure on the unsigned arm returns `PUBLICATION_FAILURE` and restores the prior sidecar (or leaves none when none existed); the plan file is never touched.
- Signed-tree behavior is unchanged: the five pre-existing tests in `tests/test_concept_sync.py` pass without modification.
- All new tests listed above pass; no test spawns a real backend (the function is deterministic — no `invoker=` seam exists or is added).
- `synchronize_concepts()`'s signature and `ConceptSyncResult`'s field set are unchanged.

## Deferred

- Routing `create.py`'s two unsigned `save_concepts` fallback arms through the new unsigned arm — step 3 owns that refactor.
- Routing `detail.py`'s deferral persistence (its direct `save_concepts` call) through `synchronize_concepts` — step 4.
- Routing `scope_out.py:apply_narrow`'s carved-sidecar `save_concepts` call through `synchronize_concepts`, plus the guard test that no production `save_concepts` caller exists outside `concept_sync.py` — step 5.
- Per-section ownership granularity (replacing one owned section while passing the other through) — deliberately out: signed state keeps whole-record authority over both sections, and no caller needs the split.
- Consolidating the four inlined atomic-write copies (`concept_sync.py:_atomic_publish` and siblings) into a shared helper — reconcile-owned, per the existing extract-at-the-fourth-site note in `plan_tool/grounding.py`.
