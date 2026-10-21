# Step 5 — Wire the concept sign-off gate into `detail`: scope before authoring, consolidated candidate sign-off after authoring

## Summary

Add the concept sign-off gate to `plan_tool/detail.py:generate_detail` in two phases. Before authoring, load persisted scope or derive it on a treeless run, navigate it once, and feed the resulting decisions into every detail prompt. After authoring, merge the structured candidate deferrals emitted by every result and run one consolidated sign-off over that union before returning. Both phases reuse step 3's walker and step 1's persistence contract; step 2's injected concept invoker supplies cold-start evidence. No walk or sidecar mutation occurs inside a concurrent worker.

## Table of Contents

- [Why](#why) — the silent-deferral gap `detail` still leaves open
- [Input](#input) — the step 1/2/3/4 contracts this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — two code edits, one prompt edit, tests
- [Implementation](#implementation) — where the gate slots in, the one-walk rule, the prompt edit, the gotchas
- [Tests](#tests) — inline, consolidated, gating, dry-run, resume, jobs>1
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — dataclasses, RFC 3339, string.Template
- [Deferred](#deferred) — coverage stamping, scope-review wiring, gate consolidation

## Why

`create` is not the only place a plan's deferral decisions get made. A plan can reach `detail` without ever having run the concept gate, and each fresh per-step body can route new material to `## Deferred`, including the foundational-logic route. Before any detail body is authored, this step ensures a scope decision exists and is navigated, so even a treeless run can constrain its prompts. It then makes every detail result expose fresh candidate deferrals, unions them into the plan tree, and gates that merged record once after authoring.

## Input

This step consumes contracts owned by earlier steps — reference them, do not re-specify them.

- **Step 2 — the concept-emit producer (`depends_on: 2`).** The injected concept invoker and producer remain the cold-start path when the run needs plan-level evidence derivation. Fresh detail deferrals do not depend on a second whole-tree emit: they come from the structured candidate-deferral block returned with each detail-generation result.
- **Step 3 — the navigator (`depends_on: 3`).** `generate_detail` calls `navigate_concepts(tree, *, prompt_fn, yes, save_fn)` and reads its frozen `ConceptDecision`. Step 3 owns the `yes → non-TTY → interactive` gate, the per-selection persistence, and the terminal sign-off stamp — this step does not re-implement any of it; it injects `prompt_fn`, `yes`, and a `save_fn` closure.
- **Step 1 — the sidecar (transitive).** `concepts_path(plan_path)` resolves `plan-details/<slug>/concepts.json`; `read_concepts` loads it fail-soft (`None` on anything wrong); `save_concepts` is the single writer the `save_fn` closure wraps. Follow step 1's shipped field names.
- **Step 4 — the `create`-side gate (sibling, not a dependency).** Step 4 demonstrates the shared navigator and injected `save_fn`; detail adds its own per-result candidate collection and deterministic merge because those contracts are specific to detail generation.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — derive/load and navigate scope before authoring, thread it into every `render_detail_prompt`, then parse candidate deferrals from every result, merge them deterministically, and run one consolidated post-authoring navigation; also wire the `yes` / invoker seams.
  - `plan_tool/prompts/detail.md` — require a parallel structured candidate-deferral JSON block for everything the body routes to `## Deferred`, and name the navigated plan scope so authoring respects prior decisions.
  - `plan_tool/cli/authoring.py` — at the `generate_detail(...)` call in `cmd_detail`, pass `yes=args.yes` so the walk honors `-y`. (Add this file to the step's `files:` list — the CLI call site is where `yes` gets wired; without it a headless `detail` run would forge sign-off. `prompt_fn` needs no wiring here: `generate_detail`'s signature defaults it to `None`, normalized to `builtins.input` inside the body (detail.py:2519-2521), so the walk is TTY-reachable on its own.)

## Implementation

**Separate pre-authoring scope from post-authoring candidates.** Before any serial prompt render or concurrent worker dispatch, load the persisted tree; if the run is treeless, derive plan-level scope through step 2's producer. Persist and run `navigate_concepts` once over that base scope, then build `concept_scope_block` from the resulting decisions and pass the same block to every authoring path. This pre-authoring phase ensures cold-start prompts are constrained rather than authored against an inert fallback.

After authoring, parse the parallel JSON block containing every concept each generated body routes to `## Deferred`, including foundational-logic deferrals, and retain the owning step context. Malformed candidate output is fail-soft for that result but must not erase candidates collected from other steps. Merge all candidates before `generate_detail` returns, then run one post-authoring walk: inline over the single result for `step_id`, or consolidated over the full/batch union. The full/batch phase never prompts per step.

The key constraint: **collect in the per-step paths, but never merge, save, or walk inside a concurrent worker.** Workers return their candidate blocks with their normal results. The serial tail performs the single deterministic merge, sidecar save, and navigation, avoiding N prompts and races on `concepts.json`.

**Deterministic merge contract.** Read the persisted tree, if present, then merge the run's candidate union into it by the stable node identity from step 1 (title + parent path). Preserve existing node state, sign-off fields, and identity for matches; append genuinely new candidate nodes as `state=defer`, `source=detail`, `signed_off=False`, with stable parent/sibling ordering derived from step order and candidate order. Deduplicate the same candidate emitted by multiple results without losing its hierarchy or owning-step context. This merged tree, not the pre-run tree, is the one saved and passed to `navigate_concepts`.

**Gate-helper split.** Keep cold-start/load plus pre-authoring navigation separate from the post-authoring merge/sign-off helper. Both resolve the sidecar with `concepts_path(plan_path)` and inject the same `save_concepts` closure. If no valid base scope can be formed, do not proceed with authoring without the scope contract; malformed candidate output after authoring remains fail-soft and does not discard completed detail results.

**Candidate output is part of every detail generation.** The normal detail prompt asks for the detail body plus the structured candidate-deferral block in the same result contract. The parser separates the body from that block, preserves the existing `## Deferred` rendering behavior, and passes the candidates to the run-level accumulator. An existing sidecar suppresses unnecessary whole-tree re-derivation, but never suppresses collection or merging of fresh per-step candidates.

**New seam, distinct from the existing invokers.** Add `concept_invoker` as its own kwarg on `generate_detail`, defaulting to step 2's `shell_concept_invoker`, next to the existing `invoker` / `lessons_invoker` / `foundational_invoker` seams. A separate seam lets a test hand a canned concept tree while leaving the unrelated detail-authoring stub alone. The default routes through step 2's `shell_concept_invoker` → `shell.claude_invoke`, so `tests/conftest.py`'s real-backend gate already covers an un-overridden call — no conftest edit needed.

**Add a `yes` param to `generate_detail`.** The walk's `yes → non-TTY → interactive` gate needs the unattended flag. `generate_detail` already carries `prompt_fn` (signature default `None`, normalized to `builtins.input` in the body); reuse it as the walk's `prompt_fn`. Add `yes: bool = False` and wire `yes=args.yes` at the `cmd_detail` call site in `plan_tool/cli/authoring.py`. Under `--yes` or non-TTY, `navigate_concepts` accepts the suggested states, persists once, and leaves every node `signed_off=False` — step 3 owns that; this step must not forge sign-off on a headless run.

**Skip the gate on `dry_run`.** A dry run makes no writes and no Claude calls; the concept walk (which can emit via Claude and mutates the sidecar) must not run. Guard the gate on `not dry_run`, matching how the rest of `generate_detail` treats `dry_run`.

**Interaction with `jobs > 1`.** Concurrent workers return parsed candidate deferrals alongside their authored results. After `_generate_detail_concurrent` returns, the serial tail unions those candidates in target-step order, merges and saves the persisted tree, and performs one consolidated sign-off. No worker writes `concepts.json`.

**The prompt edit — feed navigated scope into per-step authoring.** So a step's detail body does not re-plan a deferred concept, `render_detail_prompt` surfaces the plan's concept scope after the pre-authoring phase. The **caller** builds a small block from the navigated tree and threads it into `render_detail_prompt` as `concept_scope_block=` at every serial and concurrent call site. Build the block once after pre-authoring navigation and hand it to both paths before any body is authored. The kwarg fills a new `${concept_scope_block}` placeholder in `plan_tool/prompts/detail.md`; the template placeholder and substitution kwarg land together. Keep the block short and name only concept titles and state, not full rationale prose.

**Gotcha — the wrapped compute is caller code.** `read_concepts` is fail-soft, but the value-building around it (resolving the path, formatting the block) is `detail`'s own code. Wrap the scope-block build defensively so a malformed sidecar cannot crash the pre-authoring phase; recover through the same cold-start derivation path before rendering any detail prompt. A readable tree whose stored fingerprint is stale is different from a missing tree: report the mismatch and stop before authoring with an actionable `plan-tool scope-review <name> --rederive` message, never format stale decisions into a detail prompt or silently derive over them.

## Tests

All in `tests/test_detail.py`. Pass `extract_lessons=False` per call (the autouse `_stub_lessons_extraction` fixture is defense-in-depth) and override `concept_invoker` / `prompt_fn` on every call so no real Claude or real `input` is reached.

- `test_single_step_detail_signs_off_inline` — one result emits a structured candidate deferral; after authoring it is merged into `concepts.json` and the one interactive walk signs it off.
- `test_treeless_run_navigates_scope_before_authoring` — derive and navigate plan-level scope before the first serial render or concurrent dispatch, and assert every prompt receives those decisions.
- `test_full_run_collects_and_walks_merged_concepts_once` — multiple results emit distinct and duplicate candidates; assert deterministic union and exactly one consolidated `navigate_concepts` call after authoring, never one per result.
- `test_yes_accepts_unsigned` — `yes=True`: the walk accepts suggested states, persists once, and every node is `signed_off=False`; the spy `prompt_fn` is never called.
- `test_non_tty_accepts_unsigned` — non-TTY path returns an accepted-unsigned decision with `signed_off=False`.
- `test_dry_run_skips_concept_gate` — `dry_run=True`: the concept invoker is never called and no `concepts.json` is written.
- `test_existing_tree_preserves_decisions_and_adds_fresh_candidates` — a pre-written tree is not re-emitted; matching nodes retain state/sign-off, new per-result deferrals are appended unsigned, and the merged tree is walked.
- `test_malformed_candidate_block_does_not_drop_other_results` — one malformed block does not fail the detail run or erase valid candidates collected from sibling results.
- `test_concurrent_authoring_unions_candidates_and_signs_off_once` — `jobs > 1` workers return candidates without writing the sidecar; the serial tail merges them deterministically and walks once.
- `test_default_concept_invoker_is_shell_concept_invoker` — assert `generate_detail`'s default `concept_invoker` is step 2's `shell_concept_invoker` by identity, so the real-backend gate covers it.
- `test_detail_prompt_names_deferred_concepts` — with a persisted or cold-start-derived tree, `render_detail_prompt` output contains the navigated deferred concept titles and scope block.
- `test_concurrent_authoring_names_deferred_concepts` — with a signed tree on disk and `jobs > 1`, the concurrent `_generate_detail_concurrent` render path also passes the scope block, so per-step bodies see the deferred-concept scope (guards the concurrent render site, not just the serial loop).
- `test_detail_result_emits_every_deferred_candidate` — output routed to the body’s `## Deferred`, including foundational-logic routing, appears in the parsed candidate-deferral block with step context.
- `test_save_fn_persists_each_selection` — the injected `save_fn` spy is called after each toggle in the walk (proves the caller wired per-selection persistence, not a terminal-only save).

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add each test above alongside the implementation it covers; write the pre-authoring-scope and consolidated post-authoring timing tests first, then the gating, dry-run, resume, and prompt-edit tests. Green-before-done gate: every new test passes before the step is considered finished.

## Acceptance criteria

- `generate_detail` gains a `concept_invoker=` seam defaulting to step 2's `shell_concept_invoker` and a `yes: bool = False` param.
- Every detail-generation result emits a structured candidate-deferral block for everything its body routes to `## Deferred`, including foundational-logic deferrals.
- Before any detail prompt is rendered, persisted scope is navigated or treeless scope is derived, persisted, and navigated; every serial and concurrent prompt receives those decisions.
- After authoring, a single-step run merges and walks that result's candidates once; a full/batch run deterministically unions every result's candidates, merges and saves the tree, then calls `navigate_concepts` **exactly once** for the consolidated candidate set.
- Existing matching nodes preserve their state and sign-off fields; fresh detail candidates are added as unsigned `defer` nodes rather than discarded when a tree already exists.
- Under `--yes` / non-TTY, every concept node is `signed_off=False` after the run; only an interactive `c` produces `signed_off=True`.
- `dry_run=True` runs make no concept-emit call and write no `concepts.json`.
- Concurrent workers return candidates but never mutate `concepts.json`; the serial tail owns union, merge, persistence, and navigation.
- A malformed candidate block is fail-soft for that result and does not discard valid candidates from other results.
- `render_detail_prompt` names the navigated plan scope on both persisted-tree and treeless cold-start runs; `plan_tool/prompts/detail.md`'s new placeholder is filled by the `safe_substitute` call.
- `cmd_detail` in `plan_tool/cli/authoring.py` passes `yes=args.yes` into `generate_detail`.
- All new tests in `tests/test_detail.py` pass.

## References

- [dataclasses — Data Classes (Python 3.13 docs)](https://docs.python.org/3/library/dataclasses.html) — the frozen `ConceptDecision` this step reads back from `navigate_concepts` and the `ConceptNode` / `ConceptTree` shapes it walks.
- [string — Template.safe_substitute (Python docs)](https://docs.python.org/3/library/string.html#string.Template.safe_substitute) — how `render_detail_prompt` fills `plan_tool/prompts/detail.md`; unfilled placeholders stay literal, so template and kwarg must land together.
- [RFC 3339 — Date and Time on the Internet: Timestamps](https://www.rfc-editor.org/rfc/rfc3339) — the UTC format for the `signed_off_at` stamp step 3 writes on the terminal confirm.

## Deferred

- **Coverage stamping (`covered_by`)** — mapping a signed concept to the step(s) that cover it is step 6's job; this step neither reads nor writes `covered_by`, so the single-step walk still shows the whole tree rather than just one step's concepts.
- **`scope-review` wiring** — the third surface that reuses `navigate_concepts` is step 8; not touched here.
- **Consolidating the `create` / `detail` / `scope-review` concept gates into one shared helper** — detail's per-result candidate collection and merge remain local; folding only the common navigation shell across modules is a reconcile-owned refactor.
- **Re-rendering plan body sections from the tree** — step 4 makes the concept tree the source for `create`'s `## Out of scope` / `## Deferred`. `detail` authors per-step bodies, not plan-level prose, so it does no such overwrite; the plan sections stay owned by `create`.
