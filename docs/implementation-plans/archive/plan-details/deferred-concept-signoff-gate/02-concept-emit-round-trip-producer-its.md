# Step 2 — Add the concept-emit round-trip producer and its prompt behind an injected `invoker=` seam

## Summary

Add the Claude round-trip that turns a plan's evidence into a candidate concept tree, living in the `plan_tool/concept_tree.py` leaf added by step 1. The step ships three things: a new prompt `plan_tool/prompts/concept-emit.md` that asks Claude for a hierarchical `{"concepts": [...]}` JSON with a suggested state and one-line evidence rationale per node; a producer function (recommended name `emit_concept_tree`) that renders that prompt, calls an injected `invoker=`, parses the JSON, and flattens it into a `ConceptTree` of `ConceptNode`s (ids via step 1's `compute_node_id`, every node `signed_off=False`); and a default real-CLI invoker (`shell_concept_invoker`) plus a row in TESTING.md's neutralization table. The most important decision: the producer stays behind the `invoker=` seam and never shells out with a bare `subprocess`, so the conftest real-backend gate catches any test that forgets to override it. On green, a fake invoker returning concept JSON produces a tree that saves and reads back equal through step 1's `save_concepts` / `read_concepts`, and the same JSON always yields the same node ids.

## Table of Contents

- [Why](#why) — what's missing today and why the producer comes now
- [Input](#input) — the step 1 contract this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the new prompt, the leaf edits, the test and doc edits
- [Implementation](#implementation) — the invoker seam, the prompt, the parse-and-flatten producer
- [Tests](#tests) — round-trip, gate coverage, parse failure, id stability
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — JSON parsing, string.Template, hashlib
- [Deferred](#deferred) — gate wiring, navigator, cold-start seeding, coverage stamping

## Why

Step 1 gave the concept tree a shape and a place on disk, but nothing populates it. Today the deferral decision is made silently by Claude with no machine record (see the plan's Problem statement and `plan_tool/create.py:propose_steps_from_claude`, where "a branch with no namable live scenario is NOT a step — defer it" drops that branch invisibly). This step adds the one Claude round-trip that surfaces those concepts as an explicit, evidence-only tree the operator can later sign off on. It comes before the gate wiring (steps 4/5/8) because `create`, `detail`, and `scope-review` all reuse the same producer and its `invoker=` seam — landing the producer and its prompt first means those steps wire an already-tested round-trip instead of inventing three copies.

## Input

This step builds directly on **step 1's `plan_tool/concept_tree.py` leaf** (`depends_on: 1`). It reads that step's shipped contract; do not re-specify it here — follow the names and shapes step 1 lands:

- **`ConceptNode` / `ConceptTree` dataclasses** — the producer builds these. Fields the producer sets: `id`, `path`, `title`, `depth`, `parent_id`, `order`, `state`, `rationale`, `source`, `signed_off` (always `False` here), `signed_off_at` (`None` here), `covered_by` (leave empty — no step stamps it; step 6 recomputes coverage from the title slug, never reading this field).
- **`compute_node_id(title, parent_path)`** — the content-hash id helper. The producer calls it for every node; it does not re-derive hashing.
- **`save_concepts` / `read_concepts`** — used only by the round-trip test to prove the produced tree persists and reads back equal. The producer itself does **not** persist — callers own that.
- **`CONCEPTS_SCHEMA_VERSION`** — set on the `ConceptTree` the producer returns (step 1's dataclass defaults it).

If step 1's final field names or the id-helper signature differ from the above, follow step 1's shipped contract — it is the owner.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/concept-emit.md` — the prompt asking Claude for the hierarchical candidate-concept JSON. Evidence-only, depth/breadth bounded, JSON-only output.
- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — add the `invoker=` seam type (e.g. `ConceptInvoker`), the default `shell_concept_invoker`, a prompt renderer (`render_concept_emit_prompt`), the parse helper (`_parse_concepts_json`), the flatten helper, and the producer `emit_concept_tree`.
  - `tests/test_concept_tree.py` — add the producer tests (round-trip, gate coverage, parse failure, id stability, state mapping, unsigned nodes).
  - `TESTING.md` — add one row to the **Backend fallback seams** table for the new producer's `invoker=` default.

## Implementation

**Keep the leaf import-clean at module top — reach Claude only through function-local imports.** Step 1's acceptance requires `grep -E '^(from|import) plan_tool' plan_tool/concept_tree.py` to return nothing. Preserve that: the default invoker and the prompt renderer pull their first-party helpers **inside the function body**, exactly as step 1's `concepts_path` imports `plan_tool.locator.slug_from_filename` function-locally. `from string import Template` and `import json` are stdlib and may sit at module top.

**Add the `invoker=` seam and its default, mirroring `detail.py:shell_detail_invoker`.**
- Define a type alias `ConceptInvoker = Callable[[str], str]` (returns stdout), matching `plan_tool/detail.py:DetailInvoker` and `plan_tool/create.py:ClaudeInvoker`.
- Define `shell_concept_invoker(prompt: str) -> str` that does a function-local `from plan_tool.shell import claude_invoke`, calls it, and returns the stdout string. Return `""` when the executable isn't on PATH (the producer treats that as a parse failure), copying `shell_detail_invoker`'s contract.
- Routing through `plan_tool/shell.py:claude_invoke` gets the shared backend / rate-limit-recovery path **and** the `_maybe_warn_shell_prompt_budget` backstop for free — this is why the seam must never use a bare `subprocess`.

**The producer `emit_concept_tree` is the step's foundational logic: render → invoke → parse → flatten into a `ConceptTree`.** Recommended signature shape (adapt as the callers in steps 4/5/8 need it):

```
emit_concept_tree(evidence, *, plan_slug, plan_title, source, invoker=shell_concept_invoker, ...) -> Optional[ConceptTree]
```

- **`evidence`** is the text context fed into the prompt — the distilled seed for `create`, the step context for `detail`. Keep it a plain string the caller assembles, so the leaf stays free of `Plan`/`Step` plumbing it doesn't need.
- **`plan_slug`** sets the returned `ConceptTree.plan_slug`; **`plan_title`** fills the prompt's `${plan_title}` placeholder (`render_concept_emit_prompt`). Both are plain strings the caller supplies.
- **`source`** is one of `create` / `detail` / `manual` (matches step 1's `ConceptNode.source` vocabulary) and is stamped on every produced node.
- **Return `Optional[ConceptTree]`** — return `None` on an unparseable response, mirroring how `plan_tool/create.py:propose_steps_from_claude` returns `None` and the caller falls back. Fail-soft, never raise.
- **The producer does not persist.** It returns the tree; callers persist via step 1's `save_concepts` (single-writer discipline). Do not call `save_concepts` inside the producer.

**Parse the JSON the way `create.py:_parse_distill_json` does.** Add `_parse_concepts_json(raw)`:
- Strip, find the first `{` and last `}`, `json.loads` the slice; on `JSONDecodeError`, non-dict top level, or a missing/`non-list` `concepts` key, return a "no tree" signal so `emit_concept_tree` returns `None`.
- Expected shape (pin it in the prompt): `{"concepts": [{"title": str, "suggested_state": "include"|"defer"|"wont_do", "rationale": str, "children": [ …same… ]}]}`.
- A single **optional** repair retry (as `propose_steps_from_claude` does) is reasonable latitude but not required for MVP.

**Flatten the nested `children` into step 1's flat `parent_id` list.** Walk the nested concepts depth-first, and for each node:
- **`state`** — map `suggested_state` 1:1 to `ConceptNode.state`. Validate membership in `{include, defer, wont_do}`. On an unknown value, default to `defer` (the safe, operator-visible choice) rather than dropping the node — a dropped concept is a silent loss, which is the exact failure this feature exists to close. Pick one behavior and test it.
- **`depth`** — 0 at the top, +1 per level.
- **`order`** — the sibling index at each level.
- **`path`** — the materialized dotted path, e.g. `auth.mfa.totp`. Build it as `parent_path + "." + segment` (or just `segment` at the top), where `segment` is a lowercased slug of the title. **Use a small local slug helper for path segments** — do **not** import `plan_tool/detail.py:derive_step_slug` (importing `detail` would break the leaf's no-first-party-import-at-module-top rule; the codebase's mirror-not-share convention says re-derive the tiny helper in place). Consolidating the two sluggers is reconcile-owned — note it in Deferred.
- **`parent_id`** — the parent node's `id` (`None` at the top).
- **`id`** — call step 1's `compute_node_id(title, parent_path)`. Because id keys only on title + parent path, the same JSON always produces the same ids.
- **`signed_off=False`, `signed_off_at=None`, `covered_by=[]`** — this is Claude output, never operator sign-off. The `c`-confirm sign-off is the navigator's job (step 3); `covered_by` stays empty (no step stamps it — step 6 recomputes coverage from the title slug, not this field).

**Render the prompt inline; don't touch `renderer.py`.** `render_concept_emit_prompt` does a function-local `from plan_tool.renderer import prompts_dir`, reads `prompts_dir() / "concept-emit.md"`, and fills it with `string.Template(...).safe_substitute(...)` — the same `${name}` convention `plan_tool/detail.py:render_detail_prompt` uses. `renderer.py` is not in this step's files, so keep the render logic in `concept_tree.py`.

**Write `plan_tool/prompts/concept-emit.md` evidence-only and bounded.** Model its tone on `plan_tool/prompts/distill-seed.md` (JSON-only output, "first character `{`, last `}`"). Key content:
- Ask for concepts **grounded in the supplied evidence only** — never derive from intent (matches the evidence-only stance of risks/scope/deferrals in `create.py`). Each `rationale` is one line of evidence.
- **Bound depth and breadth** to keep the prompt and tree small (the "concept over-generation" Risk) — e.g. cap nesting at ~3 levels and children per level at a small number. State the cap in the prompt.
- Placeholders the renderer fills: at minimum `${evidence}` (the context block) and `${plan_title}`. Keep the set small.

**Add the TESTING.md neutralization row.** In the **Backend fallback seams** table (the `| Production call site | Default invoker | How to neutralize in a test |` table), add a row for `concept_tree.py → emit_concept_tree(invoker=...)` with default `shell_concept_invoker` and the recipe "Pass `invoker=lambda p: ...` returning concept JSON." The conftest gate (`tests/conftest.py:_no_real_claude_subprocess` → `_looks_like_backend_binary` → `plan_tool/backend.py:registered_binaries`) already covers the new seam automatically, because the default routes through `shell.claude_invoke`, which spawns the registered `claude` binary — no conftest change is needed. The row is documentation of that coverage.

## Tests

Add to `tests/test_concept_tree.py` (unit, unmarked, hermetic, own `tmp_path`). Write these **with** the implementation; every one must be green before the step is done (this is a feature step).

- `test_emit_builds_tree_from_concept_json` — a fake invoker returning a two-level `{"concepts":[...]}` yields a `ConceptTree` whose flat nodes have the right `depth`, `parent_id`, `order`, `state`, `path`, and `source`.
- `test_emit_result_round_trips_through_save_read` — the produced tree, saved via step 1's `save_concepts` and re-read via `read_concepts`, equals the produced tree (the "round-trip").
- `test_default_invoker_is_caught_by_realbackend_gate` — patch `shell.shutil.which` to a truthy path (mirroring `tests/test_shell.py`) so the spawn is actually attempted rather than short-circuited by the PATH lookup, then call `emit_concept_tree` with the default invoker (no override) and assert it raises `RuntimeError` from the conftest gate, proving the seam routes through the gated backend binary and never a bare subprocess. Without the `which` patch the seam returns `""` on a `claude`-less PATH and `emit_concept_tree` returns `None`, so the gate never fires — the patch makes the test hermetically CI-checkable.
- `test_emit_returns_none_on_unparseable_response` — a fake invoker returning prose / garbage / non-JSON gives `None`, never raises.
- `test_emit_maps_suggested_state_and_handles_invalid` — valid `suggested_state` maps 1:1 to `state`; an unknown value becomes `defer` (or the chosen default) rather than dropping the node.
- `test_emit_nodes_are_all_unsigned` — every produced node has `signed_off=False` and `signed_off_at=None`.
- `test_emit_node_ids_stable_across_two_calls` — the same JSON through two `emit_concept_tree` calls produces identical node ids (delegates to step 1's `compute_node_id`).
- `test_render_concept_emit_prompt_embeds_evidence` — the rendered prompt contains the supplied evidence text and states the depth/breadth cap.

### Test-creation order (feature step)

This is a feature step. Enumerate and land each test above **with** the code that makes it pass. Green-before-done gate: `uv run pytest tests/test_concept_tree.py -q` passes, and the full suite stays green.

## Acceptance criteria

- `emit_concept_tree` exists in `plan_tool/concept_tree.py`, takes an `invoker=` kwarg defaulting to `shell_concept_invoker`, and returns a `ConceptTree` on parseable input and `None` on unparseable input.
- `plan_tool/prompts/concept-emit.md` exists, asks for JSON-only output of shape `{"concepts":[{"title","suggested_state","rationale","children":[…]}]}`, and bounds depth/breadth.
- A fake invoker returning concept JSON produces a tree whose nodes are all `signed_off=False` / `signed_off_at=None`, with ids from `compute_node_id`, and that tree round-trips equal through `save_concepts` / `read_concepts`.
- Calling `emit_concept_tree` with the default invoker inside a normal test trips the conftest real-backend gate (raises `RuntimeError`).
- `grep -E '^(from|import) plan_tool' plan_tool/concept_tree.py` still returns nothing — every first-party import the producer needs is function-local.
- TESTING.md's Backend fallback seams table has a row for `emit_concept_tree`'s `invoker=` default.
- `uv run pytest tests/test_concept_tree.py -q` passes.

## References

- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — `json.loads` and `JSONDecodeError` handling for the parse helper, mirroring `create.py:_parse_distill_json`.
- [string — Template strings (Python docs)](https://docs.python.org/3/library/string.html#template-strings) — the `${name}` `safe_substitute` convention used to render `prompts/concept-emit.md`.
- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — background for the stable node id (the hashing itself is step 1's `compute_node_id`).

## Deferred

- **Wiring the producer into `create` / `detail` / `scope-review`** — steps 4, 5, 8. This step ships the producer and prompt only; nothing calls `emit_concept_tree` from an orchestrator yet.
- **The interactive `navigate_concepts` walker and operator sign-off (`c` → `signed_off=True`)** — step 3. The producer always emits `signed_off=False`.
- **Deterministic cold-start seeding** from every `## Out of scope` / `## Deferred` bullet and committed step (plan §G) — owned by the wiring steps (`scope-review` create-if-missing and the `create` gate). The seed is guaranteed independently of this round-trip; callers may use the producer only to enrich it with hierarchy or additional evidence-backed concepts and must never let emitted output omit or replace a seeded node.
- **Coverage matching** — step 6, which recomputes from each concept's title slug against current steps; **no step stamps `covered_by`** (it stays empty — see the `coverage-linkage` design gap in BACKLOG #121). The producer leaves it empty.
- **`--rederive` append-new + preserve-existing + flag-conflicts merge** — deferred per the plan (the 3-way-merge refinement); the producer here just builds a fresh tree.
- **Consolidating the local path-segment slug with `plan_tool/detail.py:derive_step_slug`** — reconcile-owned; the leaf cannot import `detail`, so it mirrors a tiny slugger in place per the mirror-not-share convention.
