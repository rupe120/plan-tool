# Step 1 — Stop eager concept enrichment in create

## Summary

`create` stops enriching the concept tree with speculative sub-concepts. In `plan_tool/create.py:create_plan`, the no-saved-tree branch that calls `emit_concept_tree` is replaced with a direct use of the deterministic `bootstrap_concepts` result, so no plan gets ~20 model-invented sub-concepts up front. `emit_concept_tree` stays defined in `plan_tool/concept_tree.py` but becomes dormant for the create path — `create.py:5956` is its only app-wide caller. The coupled tests in `tests/test_create.py` that asserted enrichment ran (the `emit` prompt count) are reconciled to a no-enrichment world; `tests/test_concept_emit.py` keeps its unit tests green as the guard for the retained function. On green: a `create` whose `concept_invoker` raises no longer raises, and the written `concepts.json` holds only the deterministic section nodes.

## Table of Contents

- [Why](#why) — what eager enrichment costs and why it goes now
- [Input](#input) — the record shape and derive path this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files and their edits
- [Implementation](#implementation) — remove the emit call, keep a thin bootstrap record, reconcile tests
- [Tests](#tests) — the coupled tests to fix and the new ones to add
- [Acceptance criteria](#acceptance-criteria) — checkable observable behaviors
- [References](#references) — the docs relevant to this step
- [Deferred](#deferred) — what this step leaves for steps 2–4

## Why

Today `create` builds a full concept tree for every plan whether or not anything is deferred. `plan_tool/concept_bootstrap.py:bootstrap_concepts` emits one node per body section (~8), then `plan_tool/concept_tree.py:emit_concept_tree` enriches that to ~20 more speculative sub-concepts — all `review_state="unreviewed"`, `decision="include"`. Almost none are ever deferred. They are the plan's prose re-encoded as a second structure that has to be kept in sync, and that coupling (plus the whole-bundle `compute_plan_fingerprint` on load) is what produced the write-integrity bugs and the audit staleness that broke the `concept-write-integrity` plan twice during authoring. This step removes the eager enrichment — the bloat, the sync surface, and the staleness driver — while leaving the enrichment function in place for possible reuse (`scope-review` already derives non-enriched trees). It is the first change (A) of the lazy-materialization plan; steps 2–4 replace the confirm gate and move materialization to the defer points.

## Input

- **`bootstrap_concepts` output** — `plan_tool/concept_bootstrap.py:bootstrap_concepts` returns a `ConceptTree` of one node per body section, each `review_state="unreviewed"`, `decision=""`. This step makes that tree the create-path record as-is (no enrichment on top). Its shape is what the reconciled tests assert against.
- **The unsigned save path** — in `create_plan`, the `else` arm below `signed_concept_scope` (the `save_concepts(plan_path, concept_tree)` call after `compute_plan_fingerprint`) still writes the record for `-y`/unsigned runs. This step leaves that write in place, so the record stays present but thin.
- **`scope-review`'s derive path** — `plan_tool/cli/scope_review_cmd.py` already builds its tree from `bootstrap_concepts` + `rederive_concepts` and never calls `emit_concept_tree`, tolerating an absent record. It is the precedent that a bootstrap-only (non-enriched) tree is a valid record shape.

Verification limit: legacy plans with empty ownership must stay parseable, so a thin bootstrap record (or an absent one) is a valid input state, not an error.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — in `create_plan`, replace the no-saved-tree `else` arm that computes `enriched = emit_concept_tree(...)` / `concept_tree = enriched or fresh_concepts` with `concept_tree = fresh_concepts`. Drop the now-unused `emit_concept_tree` name from the `plan_tool.concept_tree` import block.
  - `tests/test_create.py` — reconcile the tests coupled to enrichment running (see Tests): fix `test_retains_deterministic_concepts_and_uses_independent_invoker`, verify the `TestCreatePlanConceptIntegration` cases, and add the no-enrichment regression tests.
  - `tests/test_concept_emit.py` — no behavior change to the emit unit tests; they stay green as the guard for the retained-but-dormant function. If any comment there implies create invokes emit, correct it; otherwise the file needs only the confirmation that its suite still passes.

## Implementation

- **The one behavior change: stop calling `emit_concept_tree`.** In `plan_tool/create.py:create_plan`, the branch that runs when there is no saved concept tree currently enriches `fresh_concepts` through `emit_concept_tree` (the `enriched = emit_concept_tree(...)` / `concept_tree = enriched or fresh_concepts` pair). Replace it so the branch uses the deterministic bootstrap tree directly: `concept_tree = fresh_concepts`. That is the whole functional change — create's concept record is now the section-level bootstrap, never the model-enriched tree.
- **Keep a thin section-only bootstrap record at create — do not go fully record-absent here.** The plan left the "absent vs thin bootstrap" choice to detailing. Choose **thin bootstrap** for this step: `bootstrap_concepts` still runs and the existing unsigned `else` arm still writes `concepts.json`. Reason: going fully record-absent means changing create to "persist only defer/wont_do decisions," which is step 2's declared title and owns the review/persistence rework. Scoping step 1 to the emit removal alone keeps its breakage surface to the enrichment-count coupling, not the record-existence coupling — the `concepts_path(...).is_file()` assertions keep passing.
- **Remove the dead import.** `create.py:5956` is the only app-wide caller of `emit_concept_tree` (confirmed by grep across `plan_tool/`). Once the call is gone, drop `emit_concept_tree` from create.py's `from plan_tool.concept_tree import (...)` block so no unused import is left. Leave the function defined in `plan_tool/concept_tree.py` untouched — the plan wants it retained for reuse.
- **Keep the `concept_invoker` parameter.** `create_plan` still uses `concept_invoker` in the interactivity heuristic at the `_review_create_concepts` call (`concept_invoker is not shell_concept_invoker`). Do not remove the parameter — that would churn every test call site and is out of this step's scope. After this step, `concept_invoker` no longer feeds enrichment; that is expected.
- **Do not touch the signed sync path or the review walk.** The `signed_concept_scope` synchronize path and the iterate-tail sync stay as they are — they only fire on a signed tree. The whole-tree confirm walk in `_review_create_concepts` is step 2's target; leave it here.
- **Constraint — the record must stay valid.** `fresh_concepts` already carries the bootstrap `concept_fingerprint`, which is what the unsigned save and any later `load_concepts` need. Using it directly preserves that; do not strip or blank the fingerprint.

Foundational logic for this step: *create's concept-tree assembly no longer enriches with speculative sub-concepts.* There is no duplicate of this logic elsewhere — `emit_concept_tree` has a single caller, and `scope-review` already derives without it — so the change is contained to create.py.

## Tests

Reconcile in `tests/test_create.py`:
- `test_retains_deterministic_concepts_and_uses_independent_invoker` — its `assert len(concept_prompts) == 1` breaks (emit is never called, so the concept invoker is never consulted). Flip it to assert the concept invoker is **not** consulted (`concept_prompts == []`), keep the assertions that the record holds the deterministic section titles and that `concepts_path(...).is_file()`, and rename it to reflect no enrichment (e.g. `test_bootstrap_record_written_without_enrichment`).
- `test_resume_reuses_saved_concepts_without_enrichment` — confirm it still passes: its second `create` passes a raising `concept_invoker`, which is now safe because enrichment never runs. Adjust its intent comment if it implies emit is the thing being skipped.
- `test_assigns_signed_concept_id_to_written_committed_step` — verify the `["defer"] * 9` answer margin still covers the (now smaller) bootstrap node set; `_queue_input` ignores leftover answers, so a smaller node count is fine, but confirm it does not under-supply.
- `TestCreatePlanConceptIntegration` class as a whole — re-run; these drive `create_plan` end-to-end and must stay green.

Keep in `tests/test_concept_emit.py`:
- The 15 `emit_*` unit tests (e.g. `test_emit_enriches_deterministic_tree`, `test_emit_additions_are_unsigned`, `test_emit_rejects_unsupported_claim_without_evidence`) — they now guard the retained-but-dormant function. No behavior edit.

### Test-creation order (feature step)

This is a **feature** step. Add these unit tests in `tests/test_create.py` alongside the implementation; every one must be green before the step is done:

- `test_create_does_not_invoke_concept_enrichment` — a `create` whose `concept_invoker` raises `AssertionError` completes without raising (proves emit is off the create path).
- `test_create_record_holds_only_bootstrap_section_nodes` — after `create`, the loaded `concepts.json` node titles equal the deterministic section set (no extra sub-concepts), and every node is `review_state="unreviewed"`.

Green-before-done gate: both new tests pass, and the reconciled `test_create.py` / `test_concept_emit.py` suites pass, before this step is considered finished.

## Acceptance criteria

- `create_plan` contains no call to `emit_concept_tree`, and `emit_concept_tree` is no longer imported in `plan_tool/create.py` (`grep -n emit_concept_tree plan_tool/create.py` returns nothing).
- A `create` run whose `concept_invoker` raises completes and writes a plan (the raising invoker is never consulted).
- The `concepts.json` written by a `-y`/unsigned `create` contains only the deterministic bootstrap section nodes — no model-enriched sub-concepts — all `review_state="unreviewed"`.
- `emit_concept_tree` remains defined in `plan_tool/concept_tree.py` and its unit tests in `tests/test_concept_emit.py` pass unchanged.
- `uv run pytest tests/test_create.py tests/test_concept_emit.py -q` is green, including the two new tests above.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — the `ConceptTree`/`ConceptNode` record this step keeps writing is a dataclass; reference for its `field()`/frozen semantics.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — `concepts.json` is read/written via `json.load`/`dump`; reference for the thin record this step leaves on disk.
- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture the reconciled and new `test_create.py` cases use to write and reload `concepts.json`.

## Deferred

- Going fully record-absent for un-deferred plans (change E) — step 2 ("persists only defer/wont_do decisions") owns the persistence rework; this step keeps a thin bootstrap record.
- Replacing the whole-tree confirm walk in `_review_create_concepts` and recording unconfirmed deferrals under `-y` — step 2.
- Promoting an unconfirmed proposed deferral to a blocking/surfaced signal — step 3.
- Materializing a new deferral at detail's shared-find routing — step 4.
- Deleting `emit_concept_tree` outright — out of scope; the plan keeps the function for possible `scope-review` reuse.
