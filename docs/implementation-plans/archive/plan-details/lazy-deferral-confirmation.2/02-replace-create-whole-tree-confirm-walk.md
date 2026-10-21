> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Replace create's whole-tree confirm walk with a deferral-only gate that stays pending under `-y`, and stop calling `emit_concept_tree`

## Summary

Reshape `plan_tool/create.py`'s create-time concept step so it records only `defer`/`wont_do` decisions as a flat decision record, and stop enriching the concept tree. Two changes in `create_plan`: drop the single `emit_concept_tree` enrichment call (use the deterministic bootstrap tree directly), and narrow `_review_create_concepts` from a whole-tree owner-assignment walk to a **deferral-only gate** that returns a `record_kind="decision-record"` tree holding only the deferred nodes (each tagged with its section `bucket`). The gate signs a decision off only when interactive; under `-y` a proposed deferral is recorded **pending** (`review_state="unreviewed"`), never auto-signed. The common (un-deferred) plan produces an empty record, so both create-side persistence writes are guarded on a non-empty record and no `concepts.json` is written at all. On green: an ordinary `create` writes no concept sidecar and makes no enrichment call, a proposed `defer` under `-y` lands as an unreviewed decision-record node, and an interactive `defer` still signs off and renders into `## Deferred`.

## Table of Contents

- [Why](#why) — the eager enriched tree and the skip-means-accept gate are the founding incident
- [Input](#input) — step 1's flat decision-record shape this gate writes against
- [Files (creates vs edits)](#files-creates-vs-edits) — one code file, one test file
- [Implementation](#implementation) — drop enrichment, deferral-only gate, guard both save arms
- [Tests](#tests) — gate behavior, persistence guards, and the coupled create-integration tests to rework
- [Acceptance criteria](#acceptance-criteria) — observable behaviors on green
- [References](#references) — dataclasses / json docs for the record shape
- [Deferred](#deferred) — enrichment removal, hierarchy teardown, and the three-surface founding-incident test

## Why

`create` over-solves BACKLOG #121. Today `create_plan` bootstraps a node per body section (`plan_tool/concept_bootstrap.py:bootstrap_concepts`, called in `create_plan`), then `emit_concept_tree` enriches roughly twenty more sub-concepts nobody signs off on, and `_review_create_concepts` walks every node to assign step ownership. That whole tree gets fingerprint-validated on load, so a pending deferral goes stale by the time an operator confirms it later. Worse, the confirm walk is skipped when non-interactive: under `-y` it silently applies the tool's own suggestions with no operator in the loop — the exact "silently drop a deferral" incident this plan closes. This step keeps only what a lazy deferral needs: the coarse `bucket` from the bootstrap tree, a `defer`/`wont_do` decision, and a review state that stays **pending under `-y`**. It removes the enrichment call and the include-ownership walk, so the ordinary plan writes no record and the only thing `create` ever persists is a genuine deferral awaiting confirmation.

## Input

This step writes the **flat decision record** that step 1 added to `plan_tool/concept_tree.py`. Depend on step 1's outcome, not its mechanism:

- **Record kind** — step 1 added `ConceptTree.record_kind` (defaults to the legacy full-tree value) and the `"decision-record"` literal for the flat kind. This step sets that kind on the tree the gate returns.
- **Node shape** — step 1 added `ConceptNode.bucket` (defaults `""`). A decision-record node requires a **non-empty `bucket`**, an empty `parent_path`, and a `decision` of `defer` or `wont_do`. This step fills `bucket` from the bootstrap node's section name (`node.title`).
- **Load behavior** — step 1's `load_concepts` skips the `plan_fingerprint` staleness check for `record_kind="decision-record"`, so a record this step writes stays loadable after later edits. This step does not touch `load_concepts`.

The gate keeps using `plan_tool/concept_review.py:review_concept_scope(..., sign_off=...)` to apply and (interactively) sign decisions — that seam is unchanged.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — in `create_plan`, remove the `emit_concept_tree` enrichment call and its now-unused import so the no-saved-tree branch uses the bootstrap tree directly; reshape `_review_create_concepts` into a deferral-only gate that returns a `record_kind="decision-record"` tree of only the deferred nodes (bucket-tagged, signed iff interactive) and stops assigning step ownership; guard the two create-side `save_concepts` writes on a non-empty record.
  - `tests/test_create.py` — rework the concept-gate unit tests and the coupled create-integration tests (drop the include-ownership tests, flip the enrichment-count / sidecar-presence assertions, delete the dead enrichment branch in the fake-backend stub), and add coverage for the deferral-only record and the empty-record no-write path.

## Implementation

**Foundational logic of this step:** create records only confirmed-or-pending deferrals as a flat decision record, and never enriches or eagerly persists a whole concept tree. The gate `plan_tool/create.py:_review_create_concepts` is the single app-side owner of that rule; there is no duplicate confirm walk elsewhere in `create.py` to consolidate. `scope-review`'s confirm path (`plan_tool/cli/scope_review_cmd.py`) is a **separate** surface owned by step 4 — leave it out of this step.

**Stop enriching — use the bootstrap tree directly.**
- In `create_plan`, the no-saved-tree branch currently calls `emit_concept_tree(fresh_concepts, ..., invoker=concept_invoker)`. Replace that branch so `concept_tree = fresh_concepts` (the deterministic bootstrap tree).
- Drop the now-unused `emit_concept_tree` import. **Keep `emit_concept_tree` defined** in `plan_tool/concept_tree.py` — it is dormant, guarded by its own `tests/test_concept_emit.py` unit tests (plan Out of scope: the hierarchy machinery is left, not deleted).
- **Keep the `concept_invoker` parameter and the `shell_concept_invoker` import.** After enrichment is gone, `concept_invoker` is still read by the interactivity heuristic (the `concept_invoker is not shell_concept_invoker` clause in the `_review_create_concepts` call). Grep confirms `concept_invoker` has exactly one other use besides the removed enrichment call; removing the parameter would churn every caller and test that passes it — out of scope.
- The saved-tree branch (`rederive_concepts`, for `--from-existing`) is unchanged: legacy records stay loadable and dormant.

**Reshape `_review_create_concepts` into a deferral-only gate.** Keep its signature `(tree, steps, *, input_fn, yes, interactive=None) -> tuple[ConceptTree, list[Step]]`. What must hold when it's done:
- **Only `defer`/`wont_do` decisions are recorded.** Walk the bootstrap nodes, collect a decision per node (interactive prompt, else the node's suggested decision — bootstrap suggests `include`). Build the returned tree from **only** the nodes whose decision is `defer` or `wont_do`; `include`/`""` nodes contribute nothing.
- **The returned tree is a flat decision record.** Set `record_kind="decision-record"` and, on each retained node, `bucket = node.title` (the section name; bootstrap nodes already have empty `parent_path`, so they satisfy the flat-kind validation). One way: apply decisions with the existing `review_concept_scope(tree, [all ids], decisions, tree.plan_fingerprint, sign_off=interactive)` call, then construct a new `ConceptTree` from the `defer`/`wont_do` subset. Keep the node `id` (scope-review consumes the bare `node.id` later); dropping the section body (`source`) keeps the record a decision rather than a cache, but that trim is intent, not a validity requirement — leave it to the implementer.
- **Pending under `-y`, signed when interactive.** Reuse `sign_off=interactive`: interactive → `review_state="approved"`; non-interactive/`-y` → the node keeps its `decision` but stays `review_state="unreviewed"`. Skipping the walk under `-y` must **record the proposal unreviewed, never silently sign it** — that is the founding-incident fix, not behavior to preserve.
- **Interactive decline drops the proposal.** When an operator answers `include` for a proposed deferral (declines it), it produces no node — no record for that concept.
- **Stop assigning step ownership.** Included concepts get nothing — a committed step is proof — so return `steps` unchanged (no `concept_ids` writes) and remove the owner-prompt / `accepted_owner_ids` / `owners` machinery. `Step.concept_ids` stays defined but dormant (plan Out of scope).
- **The common plan returns an empty decision record.** Bootstrap nodes all suggest `include`, so an ordinary `create` (interactive or `-y`) produces a tree with zero concepts.

**Guard both create-side persistence writes on a non-empty record.** `create_plan` persists the tree in two places; the empty common case must write no file:
- **Post-write arm** — the `else` (unsigned) branch currently calls `save_concepts(plan_path, concept_tree)`. Guard it so `save_concepts` runs only when the record has concepts. An empty record writes nothing — record-absence is the downstream signal for "no deferral, no staleness to invalidate."
- **Iterate-tail arm** — the `elif budget.enabled:` branch also calls `save_concepts`. Guard it the same way.
- **The signed (`synchronize_concepts`) arms need no new guard.** Both fire on `signed_concept_scope = any(node.review_state == "approved")`, which is already `False` for an empty tree.
- **Mid-flow uses tolerate the empty tree** — `render_scope_decisions(concept_tree)` returns `{}` and the any-approved predicate returns `False`, so only the two save sites change (no null-guarding every use). Do not switch the gate's return to `Optional`; an empty `ConceptTree` flows harmlessly through the intermediate uses.

**Constraints and gotchas:**
- **The signed interactive path passes the decision-record tree through the existing `synchronize_concepts` call unchanged.** Confirming a `defer` renders it into `## Deferred` via `render_scope_decisions`; rely on step 1's load/save accepting `record_kind="decision-record"` rather than adding new handling here.
- **`bucket` must be non-empty on every recorded node** or step 1's flat-kind validation rejects the record. `node.title` (the section name) is always non-empty for bootstrap nodes.
- **Keep the interactivity computation intact** — the gate still derives `interactive` from `sys.stdin.isatty()`, `yes`, and the `concept_invoker` heuristic. This step changes what the gate records, not when it prompts.

## Tests

All in `tests/test_create.py`.

**Gate unit tests (add / keep):**
- `test_review_create_concepts_unattended_keeps_proposals_unsigned` — keep and adapt: a proposed `defer` node under `-y` returns in a `record_kind="decision-record"` tree with `decision="defer"`, `review_state="unreviewed"`, `bucket` set, and `steps` unchanged (no `concept_ids`). This pins the founding-incident invariant.
- `test_review_create_concepts_records_only_deferrals` — a mix of `include` and `defer` nodes returns a decision-record holding only the `defer`/`wont_do` nodes; `include` nodes are dropped.
- `test_review_create_concepts_interactive_defer_signs_off` — interactive confirm of a `defer` returns `review_state="approved"`.
- `test_review_create_concepts_interactive_decline_drops` — interactive `include` answer for a proposed deferral yields no node.
- `test_review_create_concepts_all_include_returns_empty_record` — an all-`include` bootstrap tree returns a decision-record with zero concepts.

**Gate unit tests (remove):**
- `test_review_create_concepts_assigns_explicit_owner_interactively`, `test_review_create_concepts_allows_shared_explicit_ownership`, `test_review_create_concepts_rejects_uncommitted_owner`, `test_review_create_concepts_does_not_infer_owner_from_title` — their premise (include-ownership assignment) is gone; delete them.

**Persistence-arm tests (add):**
- `test_undeferred_create_writes_no_concept_record` — an ordinary `create` writes no `concepts.json` (`concepts_path(...).exists()` is `False`) on both the default and `--iterate` (`budget.enabled`) paths.
- `test_deferral_under_yes_persists_unreviewed_record` — a `create` whose gate returns a non-empty decision-record (e.g. by injecting the gate) writes a `concepts.json` whose node is `review_state="unreviewed"`; `-y` never flips it to `approved`.

**Coupled create-integration tests (rework — `TestCmdCreateRunLog` and neighbors):**
- `test_retains_deterministic_concepts_and_uses_independent_invoker` — flip to the no-enrichment / no-record world: `concept_prompts == []`, no `"deterministic concept record"` prompt, and `concepts_path(result.plan_path)` does **not** exist (un-deferred plan). Rename to reflect it (e.g. `test_no_enrichment_and_no_record_on_undeferred_plan`).
- `test_assigns_signed_concept_id_to_written_committed_step` — includes no longer own concepts; rework so its answer sequence drops the owner prompt and it asserts deferred nodes land in the record / `## Deferred` rather than asserting `steps[0].concept_ids`, or remove it if the ownership assertion is its whole point.
- `_stdout_for_prompt` stub — delete the dead `prompt.startswith("You enrich an existing deterministic concept record")` branch; nothing calls it once enrichment is gone.
- Resume / saved-tree tests (e.g. `test_resume_reuses_saved_concepts_without_enrichment`) — verify they still hold given the saved-tree branch is unchanged; adjust only assertions that assumed the enrichment call fired.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write each test with the code:
1. Reshape the gate and land the gate unit tests first (`records_only_deferrals`, `interactive_defer_signs_off`, `interactive_decline_drops`, `all_include_returns_empty_record`, and the adapted `unattended_keeps_proposals_unsigned`).
2. Remove the enrichment call and the include-ownership tests; delete the stub's enrichment branch.
3. Guard the two save arms and add the persistence tests.
4. Rework the coupled integration tests.

Green-before-done gate: every new and reworked test above is green, and the full `tests/test_create.py` suite stays green, before this step is finished.

## Acceptance criteria

- `create_plan` makes no `emit_concept_tree` call; `emit_concept_tree` remains defined with its own unit tests green.
- `_review_create_concepts` returns a `record_kind="decision-record"` tree containing only `defer`/`wont_do` nodes, each with a non-empty `bucket`; `include`/`""` nodes are absent, and returned steps carry no new `concept_ids`.
- Under `-y`, a proposed deferral returns `review_state="unreviewed"`; interactively, a confirmed deferral returns `review_state="approved"` and a declined one produces no node.
- An ordinary (un-deferred) `create` writes no `concepts.json` on both the default and `--iterate` paths.
- A `create` that records a deferral writes a decision-record `concepts.json`; under `-y` the persisted node is `review_state="unreviewed"`.
- `tests/test_create.py` passes in full, including the reworked integration tests and the removed include-ownership tests.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — constructing the flat decision-record nodes and copying/replacing fields (`bucket`, `record_kind`) on the returned tree.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — the on-disk shape `save_concepts` serializes for the decision record this gate produces.

## Deferred

- Removing the dormant hierarchy machinery (`emit_concept_tree`, `Step.concept_ids`) — left defined and unused; deletion is plan Out of scope.
- Migrating legacy full-tree `concepts.json` records — the saved-tree/`rederive_concepts` branch stays as-is; migration is a separate concern (plan Out of scope).
- The three-surface founding-incident test (a pending deferral shown in `status`, the completeness report, and a `create` run-summary line) — those surfaces are step 5; this step covers the gate-level and persistence-level invariants only.
- `scope-review` confirming a decision record after unrelated edits, and the bucket-existence check — owned by steps 3 and 4.
