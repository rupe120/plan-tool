# Step 3 — Stop pre-computing the concept tree in create; drop the `emit_concept_tree` enrichment call and reconcile test_create.py's prompt-count couplings

## Summary

`create_plan` currently spends a Claude call speculatively enriching its bootstrap concept tree with model-proposed sub-concepts. This step removes that one enrichment call so the no-saved-tree branch uses the deterministic bootstrap tree directly, then fixes the two places in `tests/test_create.py` that were coupled to enrichment running. The main files are `plan_tool/create.py` (delete the `emit_concept_tree` call and its import) and `tests/test_create.py` (flip a prompt-count assertion and drop a now-dead enrichment branch in the fake-claude stub). `plan_tool/concept_tree.py:emit_concept_tree` stays defined and keeps its `tests/test_concept_emit.py` unit tests as the live guard — this step does not delete the function, only its single app-side caller. On green, a normal `create` records a bootstrap-only concepts.json without an enrichment Claude call, and the full suite passes.

## Table of Contents

- [Why](#why) — why remove speculative enrichment now
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits and the one it leaves alone
- [Implementation](#implementation) — the call removal, the retained parameter, and the test couplings to reconcile
- [Tests](#tests) — the assertions to flip and the stub branch to drop
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — hashlib
- [Deferred](#deferred) — what this step deliberately leaves alone

## Why

`create_plan` derives a deterministic bootstrap concept tree from the plan body, then — in the no-saved-tree branch — calls `plan_tool/concept_tree.py:emit_concept_tree` to ask Claude for extra evidence-backed sub-concepts and merge them in. This plan (Lazy Deferral Confirmation) is moving create toward recording only what the operator actually decides, surfaced later for `scope-review`, rather than pre-computing a rich tree up front. Speculative enrichment adds model-proposed nodes nobody reviewed, costs a Claude call on every fresh create, and enlarges the tree the operator must walk. The bootstrap tree is already a valid, supported record shape (`plan_tool/cli/scope_review_cmd.py` derives its tree from `bootstrap_concepts` + `rederive_concepts` with no enrichment and tolerates an absent record). Dropping the enrichment call makes create's tree deterministic and cheaper without losing a supported shape. The enrichment function itself stays defined for possible reuse; only its single create-side caller goes away.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — in `create_plan`'s no-saved-tree `else` branch, delete the `emit_concept_tree(...)` call and use `fresh_concepts` directly; drop `emit_concept_tree` from the `from plan_tool.concept_tree import (...)` block; update the nearby "optional enrichment" comment so it no longer describes a call that's gone.
  - `tests/test_create.py` — flip and rename `test_retains_deterministic_concepts_and_uses_independent_invoker` (it asserts enrichment ran via a prompt count); remove the now-dead enrichment branch in the `_stdout_for_prompt` fake-claude stub.
- **Explicitly unchanged (named to bound scope):**
  - `tests/test_concept_emit.py` — stays as-is. It is the live unit-test guard for the now-dormant `emit_concept_tree`; this step must not touch it.

## Implementation

- **Remove the enrichment call in `create_plan`'s no-saved-tree branch.** In `plan_tool/create.py:create_plan`, the `else` arm below the `if saved_concepts is not None:` block currently computes `enriched = emit_concept_tree(fresh_concepts, concept_source, plan_context=..., invoker=concept_invoker)` and then `concept_tree = enriched or fresh_concepts`. Replace the whole arm with `concept_tree = fresh_concepts`. The saved-tree arm (`rederive_concepts(...)`) is unchanged.
- **Drop the unused import.** Remove `emit_concept_tree` from the `from plan_tool.concept_tree import (...)` block near the top of `plan_tool/create.py`. Every other name in that block (`ConceptTree`, `load_concepts`, `concepts_path`, `save_concepts`, `InvalidConceptTreeError`, `StaleConceptTreeError`) is still used elsewhere in the module — leave them. A grep check (`grep -n emit_concept_tree plan_tool/create.py` returns nothing) confirms the removal is complete.
- **Keep the `concept_invoker` parameter — do not remove it.** `create_plan`'s `concept_invoker: ClaudeInvoker = shell_concept_invoker` parameter fed the enrichment call, but it is *also* read by the interactivity heuristic that builds the `interactive=` argument to `_review_create_concepts` (the `concept_invoker is not shell_concept_invoker` clause). That clause still needs the parameter. Removing the parameter would churn every caller and test that passes `concept_invoker=` and is out of this step's scope. After this step the parameter is no longer *called* (it is only compared by identity in the heuristic) — that is intended.
- **Fix the stale comment.** The comment above the concept-derivation block ("Concepts are derived before optional enrichment … an unusable enrichment response therefore cannot erase seed concepts") describes a call that no longer exists. Rewrite it to state the forward fact plainly — the bootstrap tree is used directly in the no-saved-tree branch — with no "used to enrich" narration.
- **Reconcile the enrichment-coupled tests in `tests/test_create.py`.** Two spots assert or simulate enrichment running:
  - `test_retains_deterministic_concepts_and_uses_independent_invoker` records every prompt its `malformed_concept_invoker` receives and asserts `len(concept_prompts) == 1` — an indirect assertion that enrichment ran once. After removal the invoker is never called for enrichment, so flip this to `concept_prompts == []` and rename the test to say enrichment no longer runs (e.g. `test_retains_deterministic_concepts_without_enrichment`). Keep the rest of the test's assertions (bootstrap section titles present, all nodes `review_state == "unreviewed"`, `concepts_path(...).is_file()`) — those still hold.
  - `_stdout_for_prompt` (the fake-claude stub for the `TestCmdCreateRunLog` integration suite) has a branch `if prompt.startswith("You enrich an existing deterministic concept record"): return '{"concepts":[]}'`. That enrichment prompt never fires after this step, so the branch is dead — remove it. The remaining branches (step-list, references, synthesis) are unaffected.
- **Verify the interactive answer margin still holds — likely no change.** `test_assigns_signed_concept_id_to_written_committed_step` supplies `concept_answers = ["", "include", "1", *(["defer"] * 9)]` to walk the concept nodes. Its `concept_invoker` already returns `"not-json"`, so enrichment already produced no nodes there today; removing the call leaves the bootstrap node count identical, so the `["defer"] * 9` margin still covers the walk (and `_queue_input` ignores any leftover answers). Confirm the test stays green; do not shrink the margin unless the run proves the node count dropped.

## Tests

`tests/test_create.py`:

- `test_retains_deterministic_concepts_without_enrichment` (renamed from `..._and_uses_independent_invoker`) — asserts the concept invoker is never called (`concept_prompts == []`), the deterministic bootstrap section nodes are still recorded, every node is `review_state == "unreviewed"`, and `concepts.json` is written.
- `test_assigns_signed_concept_id_to_written_committed_step` — unchanged assertions; confirm still green (the `["defer"] * 9` margin still covers the bootstrap node walk).
- `_stdout_for_prompt` stub — the removed enrichment branch means the `TestCmdCreateRunLog` integration tests still pass with the same run-log expectations (enrichment was never a logged phase they asserted on).

`tests/test_concept_emit.py` — unchanged; still passes as the guard for the retained `emit_concept_tree`.

### Test-creation order (feature step)

This is a **feature** step (it changes create's behavior — no more enrichment). No brand-new behavior needs a new test file; the work is reconciling existing coupled tests to the new behavior. Green-before-done gate: the flipped/renamed `test_retains_deterministic_concepts_without_enrichment`, the unchanged `test_assigns_signed_concept_id_to_written_committed_step`, the `TestCmdCreateRunLog` integration suite, and all of `tests/test_concept_emit.py` must be green before this step is finished. Run at least `uv run pytest tests/test_create.py tests/test_concept_emit.py -q`.

## Acceptance criteria

- `grep -n emit_concept_tree plan_tool/create.py` returns nothing (both the call and the import are gone).
- `create_plan`'s no-saved-tree branch assigns `concept_tree = fresh_concepts` with no Claude call in that arm.
- `create_plan` still accepts a `concept_invoker` parameter (kept for the interactivity heuristic); a `grep` for `concept_invoker` in `plan_tool/create.py` still shows the parameter and the heuristic use, and no enrichment call.
- A fresh `create` on a plan with no saved concept record makes no enrichment Claude call and still writes a bootstrap-only `concepts.json`.
- `tests/test_create.py` no longer asserts any enrichment prompt count > 0; the renamed test asserts `concept_prompts == []`.
- The `_stdout_for_prompt` stub has no `"You enrich an existing deterministic concept record"` branch.
- `plan_tool/concept_tree.py:emit_concept_tree` is still defined and `tests/test_concept_emit.py` passes unchanged.
- `uv run pytest tests/test_create.py tests/test_concept_emit.py -q` passes.

## References

- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — background for the deterministic `concept_fingerprint` computed just above the edited branch (the bootstrap tree this step keeps using).

## Deferred

- Deleting `plan_tool/concept_tree.py:emit_concept_tree` and its `render_concept_emit_prompt` helper / `CONCEPT_EMIT_MAX_*` constants — out of scope. The function stays defined for possible reuse and keeps its `tests/test_concept_emit.py` guard; this step removes only the app-side caller.
- Removing the `concept_invoker` parameter from `create_plan` and its callers — out of scope. The parameter is still read by the interactivity heuristic (`concept_invoker is not shell_concept_invoker`); dropping it would churn every call site.
- Any change to how the retained bootstrap tree is later reviewed, deferred, or persisted (the `_review_create_concepts` walk, `scope-review` confirm loop) — owned by other steps in this plan.
