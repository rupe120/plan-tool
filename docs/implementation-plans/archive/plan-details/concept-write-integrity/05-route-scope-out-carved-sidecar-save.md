# Step 5 — Route scope-out's carved sidecar save through synchronize_concepts and add the no-writer-outside-concept_sync guard test

## Summary

Replace the direct `save_concepts` write at the tail of `plan_tool/scope_out.py:apply_narrow` (the `if concept_update is not None:` block after `write_plan`) with a call to `plan_tool/concept_sync.py:synchronize_concepts`, and add the plan-wide guard test that no module outside `concept_sync.py` writes the `concepts.json` sidecar. The key design decision is that the routing forces a step-id remap: scope-out renumbers surviving steps, so `_prepare_concept_narrow_update` must rewrite each concept's `source_metadata["step_id"]` through `preview.renumber` (and drop it for carved steps) before handing the candidate tree to the sync — otherwise the sync's `_mapped_scopes` guard refuses on a stale mapping or applies a scope to the wrong renumbered step. On green, the last of the three direct sidecar writers named in the plan's problem statement is gone, a scope-out with signed-off deferrals renders them into the narrowed plan's `## Deferred` section (record and prose can no longer drift), and the guard test locks the single-writer invariant that steps 3 and 4 established for create and detail. Files: `plan_tool/scope_out.py`, `tests/test_scope_out.py`, `tests/test_concept_sync.py`.

## Table of Contents

- [Summary](#summary) — what the step does and the main design decision
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — why scope-out's direct sidecar write is the last divergence gap
- [Input](#input) — the step-1 contract, serialization equalities, and prep dataclass this routing rests on
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files touched and the edits per file
- [Implementation](#implementation) — the routed call shape, the step-id remap, the failure tails, and the parts that must not vary
- [Tests](#tests) — characterization tests first, then the routing, remap, and guard tests
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — stdlib docs for the serialization and atomic-replace semantics the routing relies on
- [Deferred](#deferred) — neighboring staleness gaps and consolidations owned elsewhere

## Why

`apply_narrow` persists scope-out's concept mutation (the ownerless-carved-concept deferrals `_prepare_concept_narrow_update` signs off through `concept_review.review_concept_scope(sign_off=True)`) by importing `save_concepts` function-locally, hand-setting `final_tree.plan_fingerprint = compute_plan_fingerprint(plan_path)`, and writing the sidecar directly — the third direct writer in the plan's problem statement. The direct write skips every validation and compare-and-swap guard `synchronize_concepts` runs, and it leaves the narrowed plan's prose stale: scope-out approves `defer` decisions in the record, but nothing renders them into the plan's `## Deferred` section, which is exactly the record/prose divergence this plan exists to close. It also leaves latent garbage behind: concept nodes carry `source_metadata["step_id"]` owner mappings (written by create's owner-recording block near `plan_tool/create.py:create_plan`'s concept gate), and a narrow renumbers steps without touching those mappings, so the record silently points at wrong or missing steps until some later sync trips over it. Steps 3 and 4 removed create's and detail's direct writers; this step removes scope-out's and then pins the whole invariant with the guard test — the test only becomes assertable now, because it needs all three writers gone.

## Input

- **Step 1's unsigned arm** (`plan_tool/concept_sync.py:synchronize_concepts`): a reviewed tree with no `review_state == "approved"` node publishes only the sidecar, leaves the plan file untouched, skips `refresh_plan_provenance`, and stores a fingerprint equal to `compute_plan_fingerprint(plan_path)`. The signature (`plan_path, plan_snapshot, original_tree, reviewed_tree, *, source_plan_text, publish`) and the `ConceptSyncResult` field set are frozen by step 1's acceptance criteria; signed/unsigned detection is a predicate over the tree, never a caller flag.
- **The signed path's guards** (`plan_tool/concept_sync.py`): `_validate_tree`, `_mapped_scopes` (reads each approved node's `source_metadata["step_id"]` and refuses unknown steps or conflicting decisions), the owned-section/frontmatter divergence check against `source_plan_text`, the sidecar compare-and-swap against `json.dumps(asdict(original_tree), indent=2, allow_nan=False) + "\n"`, then re-render via `render_scope_decisions` + `replace_body_sections` and republish of both artifacts with self-rollback on failure. The routed call inherits all of these.
- **Sidecar serialization equality**: `plan_tool/concept_tree.py:save_concepts` writes the same bytes the sync builds for its `expected_sidecar` value, so a sidecar last written by either passes the sync's compare-and-swap when the unmutated `load_concepts` result is passed as `original_tree`.
- **Scope-out's own prep contract** (`plan_tool/scope_out.py`): `_ConceptNarrowUpdate` carries `original_tree`, `updated_tree`, and `original_sidecar_text`; `_prepare_concept_narrow_update` loads the tree against the pre-narrow fingerprint, validates carved concept ids, and signs off ownerless deferrals; `apply_narrow` re-checks the sidecar text and the pre-narrow fingerprint before any destructive move, and `NarrowPreview.renumber` is the old→new id map (ids absent from it are unchanged survivors; `preview.carved_ids` are the dropped ids).
- **Steps 3 and 4's outcome**: after them, `plan_tool/create.py` and `plan_tool/detail.py` no longer call `save_concepts`. The guard test added here asserts the resulting repo-wide state; it does not re-test their routing.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — extend `_prepare_concept_narrow_update` with the step-id remap over the candidate tree; replace the `save_concepts` block in `apply_narrow` with a routed `synchronize_concepts` call whose non-success result raises `NarrowError` inside the existing try; delete the caller-side `compute_plan_fingerprint` assignment and the `save_concepts` import; update the except-arm comment that names "the atomic concept saver".
  - `tests/test_scope_out.py` — add the pre-refactor characterization tests, retarget the seam-coupled `test_concept_save_failure_rolls_back_narrow`, and add the signed-render, remap, and sync-refusal tests.
  - `tests/test_concept_sync.py` — add the no-writer-outside-`concept_sync` guard test.

## Implementation

**What changes.** `apply_narrow`'s concept-persistence tail stops writing the sidecar itself and instead hands the prepared trees to `synchronize_concepts`, which owns the fingerprint, the guards, and publication. Three distinct dispositions fall out of the routing, and all three are intended:

- **No concept record and no carved concept ids** — `_prepare_concept_narrow_update` returns `None`, `concept_update` is `None`, and no sync call happens. Scope-out must never create a sidecar; keep this short-circuit exactly as it is.
- **Unsigned tree** (no approved node anywhere, no ownerless carved concepts to sign off) — the routed call takes step 1's unsigned arm: sidecar-only publication with a fingerprint of the current on-disk plan, plan file untouched. This is the same on-disk result the direct write produces today, which is what makes this arm behavior-preserving.
- **Signed tree** (pre-existing approvals, or fresh ownerless sign-offs — `review_concept_scope(sign_off=True)` sets `review_state="approved"`, so any scope-out that defers a carved concept lands here) — the sync republishes the plan and re-renders `## Deferred` / `## Out of scope` from the record. This is the deliberate behavior change: carved deferrals now show up in the narrowed plan's prose, and any hand-written text in those two sections is replaced by the record's rendering, consistent with the record-is-authority rule every other signed sync follows. Say so in a test, not just here.

**The routed call.** In `apply_narrow`, after `write_plan(plan_path, preview.narrowed_plan)` and inside the same try block:

- Pass `preview.narrowed_plan` as `plan_snapshot` — it is the exact object `write_plan` just serialized, so the signed path's `render_plan_text` round-trip reproduces the frontmatter unchanged (the write-plan-was-the-last-writer condition from step 4's reasoning holds by construction here).
- Pass `concept_update.original_tree` (the unmutated `load_concepts` result) as `original_tree` and the remapped candidate as `reviewed_tree`.
- Leave `source_plan_text` at its default. `apply_narrow` itself just rewrote the plan, so a pre-narrow snapshot would refuse on every run; the real integrity guards at this call site are the sidecar compare-and-swap plus `apply_narrow`'s own pre-move checks (the frontmatter-hash staleness gate and the sidecar byte check against `original_sidecar_text`). Keep those pre-move checks: they fail fast *before* any rename or archive happens, while the sync's guards run after the narrow is already on disk and can only trigger a rollback.
- On a non-success `ConceptSyncResult`, raise `NarrowError` carrying `result.status` / `result.message` so the existing except arm replays the journal, restores the plan text, and re-raises. Note the sync **returns** statuses rather than raising — forgetting the conversion would silently commit a narrow whose concept publication was refused. On `PUBLICATION_FAILURE` the sync has already rolled back its own writes; the except arm's sidecar restore becomes a redundant-but-harmless backstop, and you may keep or drop it (keeping it is the lower-risk choice — the raise-and-rollback is the part that is not optional).
- Delete the `final_tree.plan_fingerprint = compute_plan_fingerprint(plan_path)` assignment and the function-local `save_concepts` import: the sync owns the fingerprint now, matching step 3's caller-stops-computing rule. The tree still carries its pre-narrow fingerprint from `load_concepts`, which is what keeps `_validate_tree` satisfied on entry — don't blank it.
- Import style: the file's existing convention keeps concept imports function-local (`_prepare_concept_narrow_update`, the current save block), and a function-local `from plan_tool.concept_sync import synchronize_concepts` stays patchable via the `plan_tool.concept_sync` module attribute, the same way today's failure test patches `plan_tool.concept_tree`. A module-top import is also cycle-safe (`concept_sync` imports only `concept_tree`, `parser`, `schema`); either works — match the file.

**The step-id remap (the part that is not free to vary).** The routing makes the sync's `_mapped_scopes` guard run against the *narrowed* plan while the record's `source_metadata["step_id"]` values still use pre-narrow numbering. Without a remap, a carved owner's step id either points at a step that no longer exists (the sync refuses with `MAPPING_CONFLICT`, rolling back every scope-out that defers a carved concept) or — worse, because renumbering keeps ids contiguous — points at a *different surviving step* and silently rewrites that step's scope. Extend `_prepare_concept_narrow_update` (it already has `carved_steps` and `preview`) to remap the **candidate tree only**, never `original_tree` (which must stay faithful to the on-disk sidecar for the compare-and-swap):

- a node whose `step_id` parses to an id in `preview.carved_ids` → remove the key (`source_metadata.pop("step_id", None)`, the same shape create uses when a concept has no owner). A deferred carved concept is plan-level work-to-re-plan; a dangling step mapping is exactly the stale state this fix removes. `_mapped_scopes` skips nodes without the key, and `render_scope_decisions` still renders the deferral.
- a node whose `step_id` appears as an old id in `preview.renumber` → rewrite to the string form of the new id.
- any other value (a surviving unchanged id, or a malformed value the sync will judge) → leave as-is.

**Guard test.** In `tests/test_concept_sync.py`, add a test that walks every `*.py` under the installed `plan_tool` package directory (resolve it from `plan_tool.__file__`, `rglob`) and asserts the tokens `save_concepts` and `write_concepts` appear only in an explicit allowlist: `concept_tree.py` (the definition and its alias) and `concept_sync.py` (the one module allowed to be the writer — it currently publishes through its own `_atomic_publish` and references neither token, but the allowlist states the designed boundary rather than the incidental one). A plain text scan is deliberate: it also catches comments and docstrings that still name the removed writers, which forces stale references out with the code. This test is only assertable after steps 3 and 4 removed create's and detail's writers; it is this step's second deliverable, not an afterthought.

**Interaction with the recommend-only paths.** `scope_out_step` calls `_prepare_concept_narrow_update` before its opt-in and confirm gates, and prep stays read-only — the remap mutates only the in-memory candidate. The existing `test_recommend_only_does_not_save_concept_record` behavior (no sidecar change without apply) must hold unchanged.

## Tests

All in `tests/test_scope_out.py` unless noted.

### Test-creation order (refactor step)

Write these characterization tests **first**, against the current direct-write implementation, and confirm they pass before touching `plan_tool/scope_out.py`:

- test_scope_out_without_concept_record_creates_no_sidecar — carving a step with no concept record and no `concept_ids` leaves `concepts_path(plan_path)` absent after a successful apply.
- test_unsigned_tree_scope_out_publishes_sidecar_only — an all-`unreviewed` tree whose carved step's concepts keep a surviving committed owner: after apply, the sidecar's stored fingerprint equals `compute_plan_fingerprint(plan_path)`, decisions and review states are unchanged, and the plan file contains exactly what the narrow wrote (no owned-section rendering).
- test_sidecar_fingerprint_fresh_after_scope_out — after any successful apply with a concept record, `load_concepts(plan_path, compute_plan_fingerprint(plan_path))` succeeds; pins the freshness-token obligation so a later skip-if-tree-unchanged "optimization" can't strand a stale fingerprint.
- test_publication_failure_restores_plan_and_sidecar — seam-neutral sibling of the existing `test_concept_save_failure_rolls_back_narrow`: a failure during concept publication leaves the plan text, detail-file layout, and sidecar bytes exactly as before the call, while the seed file persists (seed-first).

**Pass-unchanged-after gate:** the four tests above, plus the existing seam-neutral battery — `test_successful_apply_persists_narrow_and_deferrals`, `test_scope_out_changes_only_ownerless_carved_concepts`, `test_recommend_only_does_not_save_concept_record`, `test_unknown_owned_concept_id_refuses_before_writes`, the missing-record refusal, and `test_seed_persists_when_narrow_fails` — must stay green, unmodified, after the routing. The one permitted edit to the existing battery is the seam retarget below.

- test_concept_save_failure_rolls_back_narrow (retargeted) — the current test patches `plan_tool.concept_tree.save_concepts`, a seam the routing removes from the production path. Re-point the failure injection at the new seam (patch `plan_tool.concept_sync._atomic_publish` to write-then-raise, or patch `plan_tool.concept_sync.synchronize_concepts` to return a `PUBLICATION_FAILURE` result) and keep the asserted outcome identical: plan and sidecar restored, seed persists. The expected exception becomes `NarrowError` (the sync returns statuses; `apply_narrow` converts) — that match-string change is part of the sanctioned retarget, not a weakening.

New behavior tests, after the routing lands:

- test_signed_scope_out_renders_carved_deferral_into_deferred_section — carving a step whose concept has no surviving committed owner leaves the narrowed plan with a `## Deferred` section containing that concept's title, and the sidecar shows `decision == "defer"`, `review_state == "approved"`.
- test_scope_out_remaps_surviving_concept_step_ids — a concept mapped to a step downstream of the carve has its `source_metadata["step_id"]` rewritten to the renumbered id in the persisted sidecar.
- test_scope_out_drops_step_id_for_carved_concepts — a carved concept's `step_id` key is absent from the persisted sidecar, and the apply succeeds (no `MAPPING_CONFLICT` refusal).
- test_original_tree_keeps_prenarrow_step_ids — the remap touches only the candidate: the compare-and-swap against the on-disk sidecar still passes, i.e. the apply succeeds when the sidecar was written by `save_concepts` with pre-narrow mappings.
- test_sync_refusal_rolls_back_narrow — patching `plan_tool.concept_sync.synchronize_concepts` to return a `SOURCE_DIVERGENCE` result makes `apply_narrow` raise `NarrowError` and restores the plan text, detail-file layout, and sidecar.

In `tests/test_concept_sync.py`:

- test_no_concept_sidecar_writer_outside_concept_sync — scans every `plan_tool/**/*.py` and asserts `save_concepts` / `write_concepts` tokens appear only in `plan_tool/concept_tree.py` and `plan_tool/concept_sync.py`.

Run gate: `uv run pytest tests/test_scope_out.py tests/test_concept_sync.py -q` green, then the full suite.

## Acceptance criteria

- `grep -rn "save_concepts" plan_tool/` returns hits only in `plan_tool/concept_tree.py` (the definition and the `write_concepts` alias); `plan_tool/scope_out.py` has zero references.
- `apply_narrow` contains no `plan_fingerprint` assignment and no `compute_plan_fingerprint` call after `write_plan`; its concept tail is a `synchronize_concepts` call whose non-success result raises `NarrowError` inside the journaled try block.
- A scope-out on a plan with no concept record and no carved `concept_ids` completes without creating `concepts.json`.
- An unsigned-tree scope-out leaves the plan file exactly as `write_plan` wrote it and stores a sidecar fingerprint equal to `compute_plan_fingerprint(plan_path)`.
- A scope-out that defers a carved ownerless concept completes (no mapping refusal) and the narrowed plan's `## Deferred` section names the concept.
- The persisted sidecar after a narrow carries no `step_id` pointing at a carved id, and every surviving mapping uses post-renumber ids.
- After any successful apply with a concept record, `load_concepts(plan_path, compute_plan_fingerprint(plan_path))` succeeds.
- Every characterization test in the pass-unchanged-after gate is green with no edits other than the declared seam retarget of `test_concept_save_failure_rolls_back_narrow`.
- `test_no_concept_sidecar_writer_outside_concept_sync` passes.

## References

- [json — JSON encoder and decoder (Python 3 standard library)](https://docs.python.org/3/library/json.html) — the `json.dumps(..., indent=2, allow_nan=False)` behavior behind the sidecar serialization equality the compare-and-swap rests on.
- [os — Files and directories: os.replace (Python 3 standard library)](https://docs.python.org/3/library/os.html#os.replace) — the atomic same-filesystem rename the sync's `_atomic_publish` uses; relevant to reasoning about what a mid-publication failure can leave behind.
- [tempfile — mkstemp and NamedTemporaryFile (Python 3 standard library)](https://docs.python.org/3/library/tempfile.html) — the write-temp-then-replace pattern `_atomic_publish` implements, which the retargeted failure test injects into.

## Deferred

- Remapping `detail_deferral_step_ids` links through `preview.renumber` — the structured deferral links step 4 moved into `concept_sync` also go stale when a narrow renumbers steps; that staleness predates this plan, the routed sync does not validate them, and fixing it needs its own decision about carved-vs-surviving link semantics. **Step 8 owns filing this in `BACKLOG.md`** (its backlog-sweep implementation and acceptance criteria), shared with step 4's identical detail-side deferral-link gap — rather than widening this step. (Distinct from the concept **owner** mapping `source_metadata["step_id"]`, which both this step and step 4 *do* remap, because the signed sync's `_mapped_scopes` guard consumes it.)
- Consolidating `plan_tool/review.py:_structured_concept_deferral_is_valid` onto `concept_sync`'s public deferral reader — reconcile-owned follow-up, per step 4's note.
- Create's and detail's writer removal — owned and shipped by steps 3 and 4; this step only asserts the resulting repo-wide state through the guard test.
- Renormalizing `signoff_source_state` after the narrow — the sign-off deliberately binds to the fingerprint the decision was made against (pre-narrow); rewriting it would erase that provenance.
