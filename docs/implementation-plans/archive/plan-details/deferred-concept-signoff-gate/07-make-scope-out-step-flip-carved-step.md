# Step 7 — Make `scope_out_step` flip a carved step's concepts include→defer and carry them into the rendered forward-seed with an all-or-recoverable transaction

## Summary

Teach `plan_tool/scope_out.py:scope_out_step` to treat a carve as a deferral of the concepts the carved step(s) covered. When a carve is applied, any `include` concept in `plan-details/<slug>/concepts.json` that is covered **only** by the carved step(s) — no surviving committed step covers it — flips to `defer`, keeps its `signed_off` flag, and is written into the rendered forward-seed as a `## Deferred concepts` bullet. The seed, plan narrow, and concept-tree transition use one all-or-recoverable commit protocol that restores every artifact to its pre-operation bytes or absence after a partial failure. The renderers `render_carved_seed` / `render_carved_region_seed` gain one optional `deferred_concepts` parameter and a block helper that is omitted when empty, so a plan with no `concepts.json` produces the same seed as before. On green, carving a covering step out defers its orphaned concept, records it in the seed, and a follow-up audit raises no `concept-coverage` finding on it (it is now `defer`), while `signed_off` is preserved.

## Table of Contents

- [Why](#why) — the one structural remedy that is a semantic deferral, not just a renumber
- [Input](#input) — the step 1 concept-tree contract this reads and mutates
- [Files (creates vs edits)](#files-creates-vs-edits) — one code edit, one test edit
- [Implementation](#implementation) — the flip predicate, the renderer block, the transaction ordering, the gotchas
- [Tests](#tests) — renderer block, flip, preserve-signed-off, survivor coverage, treeless, recommend-only
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — dataclasses, hashlib
- [Deferred](#deferred) — the shared coverage predicate, covered_by persistence, other remedies

## Why

Scope-out is the one structural remedy that is a **semantic transition** from delivery to deferral. The plan's §H gives the other remedies explicit replacement matching: split partitions matching feature ownership among children, merge unions source feature ownership on its replacement, and re-ground preserves the covering title/features or carries their union to a replacement; coverage is then recomputed against those resulting steps. But carving a step to a forward-seed genuinely **defers** the work — and with it, any concept the carved step was the sole cover for. Today `scope_out_step` narrows the plan and writes a re-plan seed but never touches the concept tree, so a carved-out step leaves its concept sitting `include` with no covering step. The next completeness audit (step 6's `check_concept_coverage`) would then raise a blocking `concept-coverage` finding on a concept the operator already deferred by the carve — a false alarm that never converges. This step closes that gap: the carve itself flips the orphaned concept to `defer` (preserving the operator's sign-off) and carries it into the seed, so coverage stays honest and the just-deferred concept never re-raises.

## Input

This step reads and mutates the concept-tree contract owned by **step 1** (`depends_on: 1`) — reference it, do not re-specify it. What this step touches:

- **`read_concepts(plan_path)` / `save_concepts(plan_path, …)`** — step 1's fail-soft loader and single-writer. Step 1 pins their signatures as canonical on the **plan path**, mirroring `plan_tool/grounding.py`'s `read_grounding(plan_path)` / `write_grounding(plan_path, …)` (which resolve the sidecar path internally via `grounding_path`); the sidecar path is resolved inside, so `concepts_path(plan_path)` is not threaded through the call. Sibling step 6 binds to the same plan-path arity. `read_concepts` returns `None` on a missing or unreadable sidecar; this step returns early (no flip, no write) on `None`, so a treeless plan is unchanged. If the tree exists but its fingerprint is stale, abort before changing the plan, seed, or sidecar and report `scope-review --rederive`; never compute or persist a flip from stale decisions.
- **`ConceptNode.state`** — one of `include` / `defer` / `wont_do`. This step flips only `include` → `defer`; it never writes `wont_do` and never touches an already-deferred node.
- **`ConceptNode.signed_off` / `signed_off_at`** — the operator sign-off flags. The flip **preserves both** — it changes `state` only. An operator-signed carve stays signed; an unattended one stays `signed_off=False`.
- **`ConceptNode.id`** — the content hash of title + parent path. Step 1 keeps `state` out of the hash, so flipping `state` leaves the id unchanged and any coverage/annotation join keyed on it stays valid. Cite this, do not re-derive it.
- **`ConceptNode.title` / `rationale`** — read for the coverage match (title) and for the seed bullet (title + rationale).

This step does **not** depend on step 6. It recomputes coverage itself rather than reusing step 6's `check_concept_coverage`, because step 6 is not a prerequisite and may not exist when step 7 runs (see Implementation and Deferred).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/scope_out.py` —
    - Add an optional `deferred_concepts: Sequence[tuple[str, str]] = ()` parameter to `render_carved_seed` and `render_carved_region_seed`, plus a `_deferred_concepts_block(deferred_concepts)` helper (mirrors `_upstream_block`: emit a heading + bullets, omit the whole block when empty).
    - Add the flip logic to `scope_out_step`'s apply branch: read the tree, compute the concepts covered only by the carved region, flip them, feed them to the renderer, and publish the seed, plan narrow, and sidecar through the all-or-recoverable commit protocol.
    - Add a small coverage predicate (recommended name `_step_covers_concept(step, node)`) and a driver (recommended `_flip_carved_concepts(...)`).
    - Add a module-top `from plan_tool.concept_tree import read_concepts, save_concepts` (step 1's stdlib-only leaf — a clean downward edge, no cycle).
  - `tests/test_scope_out.py` — the renderer-block and flip tests enumerated below.

## Implementation

**The core rule this step adds: a carve defers the concepts it orphans.** After a safe, opted-in, confirmed carve, a `state=include` concept flips to `defer` when **the carved step(s) cover it and no surviving committed step covers it**. Everything else in the tree is left alone.

**Where the flip runs — the apply branch of `scope_out_step` only.** The flip and the concept write must never happen on the blocker, opt-in, or declined-confirm paths — only after the existing confirm gate passes, in the block that renders the seed and calls `apply_narrow`. This matters: a recommend-only or blocked scope-out must leave `concepts.json` untouched, exactly as it leaves the plan untouched.

**Recommended shape:**

- **A coverage predicate** — `_step_covers_concept(step, node, plan_features) -> bool`. A step covers a concept when the concept's title-slug matches the step. The miss risk is **asymmetric**: a miss on the *carved-covers* side is a safe no-flip, but a miss on the *survivor-covers* side is a **false flip** — `include → defer` on a concept a surviving step still delivers, which step 6's include-only coverage check will not re-surface. So the survivor-coverage match must be **at least as generous as step 6's `check_concept_coverage`**, which cross-references step titles, `step.features`, **and the plan's `features` registry titles**. Give the predicate (and its driver) the `plan.features` registry so it can make that plan-level feature-title match — the bare `(step, node)` signature structurally can't reach it. One reasonable rule: slugify both `node.title` and `step.title` with a single kebab-case slugify and compare, also test the slug against `step.features` ids and the titles of the plan's `features` entries owned by the step. Leave the exact token set to the implementer, but use **one** slugify for every side so they never drift.
- **A driver** — `_flip_carved_concepts(plan_path, plan, carved_steps, survivors) -> tuple[ConceptTree | None, list[tuple[str, str]]]`:
  - `read_concepts(plan_path)` — step 1's canonical plan-path arity (see Input); return `(None, [])` on `None` (treeless plan → no-op).
  - Compute `survivor_committed = [s for s in survivors if s.scope is StepScope.COMMITTED]` (match step 6, which counts only committed steps as covering).
  - For each node with `state == "include"`: if any carved step covers it **and** no `survivor_committed` step covers it, set `node.state = "defer"` (leave `signed_off` / `signed_off_at` / `id` untouched) and collect `(node.title, node.rationale)`. Pass `plan.features` into `_step_covers_concept` for **both** sides so the survivor-covers test is as generous as step 6's — the false-flip guard above.
  - Return the mutated tree and the flipped `(title, rationale)` pairs.
- **In the apply branch**, call `_flip_carved_concepts` **before** rendering the seed (using `survivors = [s for s in plan.steps if s.id not in carved_set]`), pass the flipped pairs as `deferred_concepts=` to whichever renderer runs (single vs region), and execute the seed write, `apply_narrow`, and conditional `save_concepts(plan_path, tree)` through the commit protocol below.

**All-or-recoverable multi-artifact commit protocol.** Treat the plan markdown, forward-seed path, and `concepts.json` as one logical carve:

- Before publishing anything, capture each artifact's exact bytes and whether it existed, and retain that recovery material until the carve commits or rollback completes. Compute the concept flip and render/stage all replacement content before the first publish so preparation failure leaves the filesystem untouched.
- Publish in this order: forward-seed, narrowed plan through `apply_narrow`, then `concepts.json` when a flip occurred. The sidecar is last so no persisted deferral can precede its seed and plan carve.
- If any publish fails, roll back every artifact that may have been published: atomically restore its captured bytes, or remove it when it did not exist before the carve. Do not return an ordinary scope-out result until rollback has completed, and re-raise the original failure after a successful rollback.
- If rollback itself fails, raise a distinct actionable recovery error that names every artifact not restored and the retained recovery material needed to restore it manually. Never report the carve as successful in this state.
- Delete the retained recovery material only after all publishes succeed or a full rollback succeeds. This makes a successful carve all-artifact and every partial write either automatically reversed or explicitly recoverable.

**Renderer change — one optional parameter and an omit-when-empty block.**

- Add `deferred_concepts: Sequence[tuple[str, str]] = ()` to `render_carved_seed` and `render_carved_region_seed`. Default empty keeps every existing call and every existing seed the same.
- Add `_deferred_concepts_block(deferred_concepts)` modeled on `_upstream_block`: when the list is non-empty, emit a `## Deferred concepts (carried from the concept tree)` heading with one bullet per `(title, rationale)`; when empty, return `[]` so nothing renders. Insert the block after the done-context / upstream blocks and before `## Provenance`.
- The block lists **only the concepts this carve flipped** (the include→defer transition), not the plan's whole defer subtree — the seed is about what the carve just deferred.
- For a region carve, pass the union of flipped pairs across the whole carved region (one merged block).

**Constraints and gotchas that are not free to vary:**

- **The flip changes `state` only.** Do not touch `signed_off`, `signed_off_at`, `id`, `parent_id`, `path`, or `covered_by`. The `id` staying stable (state is not a hash input — step 1) is what keeps the concept's coverage/annotation key valid across the flip.
- **Treeless plans stay unchanged.** `read_concepts` returning `None`, or zero flips, must produce no `concepts.json` write and the same seed as today. This is the guard that keeps the existing `test_scope_block_*` seed tests green.
- **Only `include` nodes flip.** A concept already `defer` / `wont_do` is left alone and is **not** added to the seed's deferred block.
- **Survivor coverage uses committed survivors, and must be no weaker than step 6's.** A concept still covered by a surviving committed step stays `include` and is **not** flipped or added to the seed — it is still delivered. Because a survivor-side miss is a false flip (not a safe no-op), the survivor match must be **at least as generous as step 6's `check_concept_coverage`**, including the plan `features`-registry-title cross-reference — hence the `plan.features` argument threaded into the predicate.
- **Serial-only write.** `scope_out_step` runs in a serial context (both entry points — `plan-tool scope-out --apply` and `convergence … --apply-scope-out`). The plan's §D hard rule forbids concept writes inside a parallel `completeness-apply` worker; this write is safe because scope-out is never that worker. Do not move the write anywhere a worktree worker could reach it.

**Foundational logic shared with step 6 — flag it, do not couple to it.** The "does step S cover concept C" slug match is the same rule step 6's `check_concept_coverage` (`plan_tool/review.py`) applies. Step 7 does **not** depend on step 6, so it must not import a step-6 helper (which may not exist yet) — implement the conservative predicate locally in `plan_tool/scope_out.py`. Consolidating the two into one shared `step_covers_concept` predicate would touch `plan_tool/review.py`, outside this step's files, and is a refactor `detail` cannot mint — routed to Deferred for reconcile.

## Tests

Add to `tests/test_scope_out.py` (unit tests, hermetic, own `tmp_path`). Renderer tests are pure; flip tests build a plan file plus a `concepts.json` via step 1's `save_concepts`. Write these **with** the implementation; every one must be green before the step is done.

### Test-creation order (feature step)

This is a **feature** step. Enumerate the tests below with the implementation; the green-before-done gate is that all of them pass before the step is considered finished.

- `test_deferred_concepts_block_rendered` — `render_carved_seed(..., deferred_concepts=[("Auth MFA", "no live scenario yet")])` includes a `## Deferred concepts` heading and a bullet naming the concept and its rationale.
- `test_deferred_concepts_block_omitted_when_empty` — with `deferred_concepts=()` (the default) the seed has no `## Deferred concepts` heading (guards existing seed tests).
- `test_region_seed_renders_deferred_concepts` — `render_carved_region_seed` with a non-empty `deferred_concepts` renders one merged deferred-concepts block.
- `test_scope_out_flips_include_only_covered_by_carved` — carve a step whose title matches an `include` concept; assert the on-disk `concepts.json` shows that node `state=defer` and the written seed contains it under `## Deferred concepts`.
- `test_scope_out_preserves_signed_off_on_flip` — a flipped node that was `signed_off=True` stays `True` (and `signed_off_at` unchanged); a `signed_off=False` node stays `False`.
- `test_scope_out_leaves_concept_covered_by_survivor` — an `include` concept also covered by a surviving committed step stays `include`, is not written to the seed, and `concepts.json` is unchanged.
- `test_scope_out_survivor_coverage_via_plan_features` — an `include` concept delivered by a surviving committed step **only** through the plan's `features`-registry title (not the step title) stays `include` and is not flipped — the survivor match is as generous as step 6's, so no false flip.
- `test_scope_out_flip_leaves_no_include_for_coverage_check` — after the flip the node's `state == "defer"`, so step 6's include-only coverage check would raise nothing on it (assert on `state`, not on step 6 internals).
- `test_scope_out_treeless_plan_writes_no_concepts` — a plan with no `concepts.json`: the carve succeeds, no sidecar is created, and the seed has no `## Deferred concepts` block.
- `test_scope_out_recommended_does_not_flip` — `allow_scope_out=False` (recommend-only): `concepts.json` is byte-unchanged, no flip persisted.
- `test_scope_out_blocked_does_not_flip` — a blocked carve (e.g. `step-missing` / `unsafe`) leaves `concepts.json` unchanged.
- `test_node_id_stable_across_flip` — the flipped node keeps the same `id` before and after the carve (state is not a hash input).
- `test_region_carve_flips_concepts_covered_only_by_region` — carving a contiguous region flips a concept covered only within the region and leaves a concept covered by a survivor as `include`.
- `test_scope_out_persists_concepts_after_narrow` — the concept write lands only when the carve applies (assert `concepts.json` reflects `defer` on an applied carve and is unchanged on a recommended one).
- `test_scope_out_rolls_back_each_partial_publish` — inject failure after the seed publish, after the plan narrow, and during the sidecar publish; for each boundary assert the plan, seed, and `concepts.json` are byte-equal to their pre-operation contents, and artifacts absent before the carve remain absent.
- `test_scope_out_reports_recoverable_rollback_failure` — inject a publish failure and then a rollback failure; assert the raised recovery error names every unrestored artifact, identifies retained recovery material, and never reports success.

## Acceptance criteria

- Carving a step that solely covers an `include` concept flips that concept to `state=defer` in `plan-details/<slug>/concepts.json` and writes it into the carved forward-seed under a `## Deferred concepts` heading.
- The flip preserves `signed_off` and `signed_off_at`; a signed concept stays signed, an unsigned one stays unsigned.
- A concept still covered by a surviving committed step is **not** flipped and **not** added to the seed.
- A plan with no `concepts.json` produces no sidecar write and a seed identical to today's (no `## Deferred concepts` block).
- A recommend-only or blocked scope-out never writes `concepts.json`.
- A publish failure at any scope-out commit boundary restores the plan, forward-seed, and `concepts.json` byte-for-byte to their pre-operation state, including restoring absence; a rollback failure raises an actionable recovery error naming unrestored artifacts and retains recovery material.
- The flipped node keeps its `id` (a state change is not an identity change).
- `render_carved_seed` and `render_carved_region_seed` accept `deferred_concepts` and omit the block when it is empty; all existing seed-render tests stay green.
- `uv run pytest tests/test_scope_out.py -q` passes.

## References

- [dataclasses — Data Classes (Python 3.13 docs)](https://docs.python.org/3/library/dataclasses.html) — the `ConceptNode` / `ConceptTree` shape this step reads and mutates, and the frozen `ScopeOutResult` it returns.
- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — background for why the node `id` (a content hash of title + parent path) is stable across a `state` flip.

## Deferred

- **Consolidating the coverage predicate with step 6** — a single shared `step_covers_concept` that both `scope_out.py`'s flip and `review.py`'s `check_concept_coverage` call. It touches `plan_tool/review.py` (outside this step's files), and step 7 does not depend on step 6, so it is reconcile-owned; this step keeps a conservative local copy of the rule.
- **Persisting `covered_by` on flipped nodes** — coverage stays recomputed-by-slug per audit (step 6's decision); this step does not stamp `covered_by`.
- **The other three structural remedies (split / merge / re-ground)** — their executors preserve coverage through the explicit replacement title/feature semantics in plan §H, and the audit recomputes the match without writing `concepts.json`. Only `scope_out_step` changes concept state and writes the sidecar.
- **A concept-decision telemetry event for the flip** — a natural `kind="concept-signoff"` `DecisionEvent` is out of scope for this feature (plan Out of scope).
