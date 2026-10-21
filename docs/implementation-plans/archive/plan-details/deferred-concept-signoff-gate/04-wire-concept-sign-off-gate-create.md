# Step 4 — Wire the concept sign-off gate into `create` and render `## Out of scope` / `## Deferred` from the tree

## Summary

Add a third operator decision gate to `plan_tool/create.py:create_plan`, right after the step-gate review, that emits a candidate concept tree, walks the operator through sign-off, persists it to `plan-details/<slug>/concepts.json`, and then renders the plan's `## Out of scope` and `## Deferred` sections from that tree instead of letting the body synthesis guess them. The gate reuses three things landed by steps 2 and 3: the `emit_concept_tree` producer + its injected `invoker=` seam (step 2), the `navigate_concepts` walker and its frozen `ConceptDecision` (step 3), and step 1's `concepts_path` / `save_concepts` / `read_concepts`. The key decision: the concept tree is the **one-directional source** for those two H2 sections — after body synthesis, `create_plan` overwrites `synthesized_sections["Out of scope"]` (from `wont_do` nodes) and `["Deferred"]` (from `defer` nodes), and `plan_tool/prompts/distill-seed.md` is edited to stop the distill pass from independently guessing them. On green, an interactive `create` with a fake concept invoker writes a `concepts.json` sidecar, renders both sections from the deferred subtree, sets `scope=deferred` on any proposed step a deferred concept maps to, and leaves every node `signed_off=False` under `--yes` / non-TTY.

## Table of Contents

- [Why](#why) — the silent-deferral gap this closes at create time
- [Input](#input) — the step 1/2/3 contracts and the distill-section shape this consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — two code edits, one prompt edit, tests
- [Implementation](#implementation) — where the gate slots in, the render overwrite, the distill edit, the gotchas
- [Tests](#tests) — create-wiring, gating, render, resume, TODO-gate coverage
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — dataclasses, RFC 3339, datetime
- [Deferred](#deferred) — detail/scope-review wiring, coverage recompute, telemetry

## Why

Today `create` decides deferral silently in two places the operator never sees. The distill pass and the body-synthesis round-trip synthesize `## Out of scope` / `## Deferred` prose with no sign-off (the plan's Problem statement points at `plan_tool/create.py`'s evidence-only Out-of-scope/Deferred synthesis), and the decomposition instruction "a branch with no namable live scenario is NOT a step — defer it" drops a branch with no structured trace. Steps 1–3 built the machine record (the `concepts.json` sidecar), the producer that fills it, and the interactive walker that signs it off — but nothing calls them yet. This step is the first of the three wiring surfaces (`create` here; `detail` in step 5; `scope-review` in step 8). It turns the two prose sections into a **render of an operator-signed tree**, so a concept can no longer be dropped without the operator seeing it and having a chance to flip it back to `include`.

## Input

This step consumes contracts owned by earlier steps — reference them, don't re-specify them.

- **Step 2 — the concept-emit producer (`depends_on: 2`).** `create_plan` calls step 2's producer (recommended name `emit_concept_tree`) with the plan's evidence and its injected `invoker=`, and gets back an `Optional[ConceptTree]` (fail-soft: `None` on an unparseable round-trip, never raises). The default real-CLI invoker is step 2's `shell_concept_invoker`. Follow step 2's shipped signature for the evidence envelope and the invoker kwarg name — step 2 is the owner; this step only wires the call and threads a seam.
- **Step 3 — the navigator (`depends_on: 3`).** `create_plan` calls `navigate_concepts(tree, *, prompt_fn, yes, save_fn)` and reads its frozen `ConceptDecision`. Step 3 owns the `yes → non-TTY → interactive` gate, the per-selection persistence, and the terminal sign-off stamp — this step does not re-implement any of it; it injects `prompt_fn=input_fn`, `yes=yes`, and a `save_fn` closure.
- **Step 1 — the sidecar (`depends_on: 2, 3` transitively).** `concepts_path(plan_path)`, `save_concepts`, `read_concepts`, and the `ConceptNode.state` vocabulary (`include` / `defer` / `wont_do`) come from step 1's `plan_tool/concept_tree.py` leaf. This step reads `state` to route nodes into sections and reads `signed_off` for the tests; it never recomputes the node id or the tree fingerprint.
- **The distill section contract (in this step's own file).** `plan_tool/create.py`'s `_canonical_body_section_keys()` fixes the exact 8 distill section keys, including `"Out of scope"` and `"Deferred"`, and `_validate_distilled_sections` requires all 8 present (`null` allowed). The distill-prompt edit must keep those keys — emit `null`, never drop a key.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — add the concept gate to `create_plan`: a new `concept_invoker` seam param, the emit → navigate → persist block after `_review_step_gates`, the post-synthesis overwrite of the two section keys in `synthesized_sections`, and the `scope=deferred` map onto proposed steps. Add a function-local or module-top import of step 1/2/3's `concept_tree` symbols (`emit_concept_tree`, `shell_concept_invoker`, `navigate_concepts`, `concepts_path`, `save_concepts`, `read_concepts`).
  - `plan_tool/prompts/distill-seed.md` — change the `[evidence-only]` guidance for `Out of scope` and `Deferred` so the distill pass emits only what the seed literally states (else `null`) and does not guess/derive them, noting they are rendered from the operator-signed concept tree. Keep the 8-key single-plan shape unchanged.
  - `tests/test_create.py` — a new test class (e.g. `TestCreateConceptGate`) plus additions covering the render, the gating matrix, resume, and the step-scope map.

## Implementation

**Foundational logic this step adds:** *the plan's `## Out of scope` / `## Deferred` sections are a one-directional render of the operator-signed concept tree, and a concept deferral is gated at create time.* The same "silent deferral" rule lives in two other spots the plan names — the decomposition instruction and `detail`'s `## Deferred` routing (`plan_tool/detail.py`, step 5's territory). Do **not** touch `detail.py` here; step 5 owns its surface. The decomposition instruction is addressed indirectly — the emit surfaces the would-be-dropped branch as a `defer` node — so leave that instruction string as-is.

**Slot the gate in after `_review_step_gates`, before body synthesis, per the plan's §D.** `create_plan` already runs two interactive gates in sequence (`_review_step_change_types`, then `_review_step_gates`). Add the concept gate as the third, reading the same `yes` / `resume` / `input_fn` context they read. At that point the reviewed `steps` list and the seed text are both in hand — that is the evidence the emit needs.

The gate block, in order:
- **Resolve the prospective path.** Compute the plan path the same way the later `write_new_plan` will (`output_dir / f"{slug}.md"`); it is computable before the plan `.md` is written. `read_concepts` / `save_concepts` take that plan path and resolve the sidecar internally via `concepts_path` (mirroring `grounding.py`), so the caller threads only `plan_path`.
- **Resume-or-emit.** Call `read_concepts(plan_path)` first. If a tree already exists with the unset fingerprint, treat it only as unsigned create-resume state and seed the navigator from its saved decisions. If a tree already exists and its stored fingerprint matches the current finalized plan, reuse it and skip the Claude round-trip — the sidecar is its own resume state, matching step 3's "re-entering seeds from saved state." If it has a nonempty stale fingerprint, report the mismatch and stop the concept gate with an actionable `plan-tool scope-review <name> --rederive` message; never render or navigate stale decisions. Only when there is no saved tree, call the step 2 producer with `invoker=concept_invoker`. If the producer returns `None` (fail-soft), skip the rest of the gate cleanly — no tree, no overwrite (see the fallback gotcha below).
- **Navigate, checkpoint, then finalize.** While the prospective plan markdown does not yet exist, inject a `save_fn` that persists every navigator selection with `plan_fingerprint=""`, `signed_off=False`, and `signed_off_at=None`; these writes are unsigned resume checkpoints, even if the in-memory result later reaches interactive confirmation. Hold the navigator's returned decision in memory, render and write the finalized plan markdown, then save the same decisions once more with `compute_plan_fingerprint(plan_path)` and the completed interactive sign-off stamp. This post-plan-write refresh is the authoritative sidecar; it prevents create from immediately staling its own tree while preserving interruption-safe incremental saves.

**Add a `concept_invoker` seam to `create_plan`.** Mirror the existing `claude_invoker: ClaudeInvoker = shell_claude_invoker` param: add `concept_invoker: ClaudeInvoker = shell_concept_invoker` (step 2's default). Routing the default through step 2's producer — which shells out via `plan_tool/shell.py:claude_invoke` — means `tests/conftest.py`'s real-backend gate already covers it; no conftest edit. Do **not** reuse `claude_invoker` for the concept round-trip: a distinct seam lets a test stub the concept emit without also stubbing step proposal.

**Render the two sections from the tree by overwriting `synthesized_sections`.** The body renderer `_render_plan_body` picks section bodies with precedence `synthesized_sections` (canonical keys) ≻ `seed_sections` ≻ `_(TODO)_`. The cleanest way to make the tree win over both distill and the body-synthesis round-trip is to let body synthesis run as today, then **overwrite** the two concept-owned keys in the `synthesized_sections` dict before the fail-loud TODO check and `write_new_plan`:
- `synthesized_sections["Deferred"]` ← markdown built from nodes with `state == "defer"`.
- `synthesized_sections["Out of scope"]` ← markdown built from nodes with `state == "wont_do"`.

Render each as one bullet per node using the node's `title` and one-line `rationale` (evidence-only). One way: a small local helper `_render_concept_section(tree, *, state)` returning the bullet list, or an empty-but-non-placeholder body (e.g. `_(none deferred)_`) when no node has that state, so the fail-loud TODO gate never trips on an over-written key. This overwrite is why the gate can run early (after `_review_step_gates`) yet still own the sections that body synthesis fills later — hold the tree, apply the overwrite after `propose_body_sections`.

Render by each node's own persisted state, never by an inherited or derived subtree state. A `defer` parent with an `include` child contributes only the parent to `## Deferred`; the child remains included and is left for step 6's coverage audit. Mixed-descendant markers are navigator display only and never select a prose section.

- **Rejected alternative:** adding a fourth precedence source or a new `write_new_plan` argument. The overwrite reuses the existing `synthesized_sections` plumbing with no signature churn.

**Map deferred concepts onto proposed steps.** Per §D and the create-wiring test, for each `defer` / `wont_do` node that maps to one of the reviewed steps, set that `Step.scope` to `deferred` (`StepScope` from `plan_tool/schema.py`) and add a short `status_note`. Keep the match conservative — a title/slug comparison between the node and the step titles is enough at create time. The durable, per-audit coverage recompute (`covered_by` slug matching) is **step 6's** job; this is only a best-effort create-time reconcile so the written plan is internally consistent. Do not stamp `covered_by` here — step 2 leaves it empty and step 6 owns it.

**Edit `plan_tool/prompts/distill-seed.md`.** Change the `[evidence-only]` field rule covering `Out of scope` and `Deferred` so the distill pass emits only what the seed literally states and otherwise emits `null` — it must not derive or guess these two, because they are rendered from the operator-signed concept tree. This directly closes the distill silent-synthesis site the Problem statement names. Keep the single-plan shape at exactly 8 keys so `_validate_distilled_sections` stays green; `null` is a valid value.

**Gotchas that are not free to vary:**
- **The overwrite must land before the fail-loud TODO check.** `create_plan` renders a candidate body and calls `_find_placeholder_body_sections` (skipped when `budget.enabled`, i.e. under `--iterate`). Overwrite the two keys before that check so a concept-rendered body is what the check (and `write_new_plan`) see.
- **Fail-soft on a `None` emit.** When the producer returns `None`, do not overwrite — the two sections fall back to whatever the seed literally stated (via `seed_sections`), or to `_(TODO)_`. Under `--iterate` the TODO gate is off so an empty fallback is tolerated; without `--iterate` the existing fail-loud behavior stands. Do not swallow the emit failure into a fabricated section.
- **The sidecar dir is born on checkpoint save.** `concepts.json` lives inside `plan-details/<slug>/`, which `create` does not otherwise create. Step 1's `save_concepts` writes atomically and creates parent dirs, so the sidecar dir appears before the plan `.md` is written. If `create` aborts later, the resume path re-reads this unsigned, unset-fingerprint checkpoint; only the post-plan-write refresh makes it authoritative and restores a completed interactive sign-off.
- **`wont_do` nodes are read, not produced here.** `navigate_concepts` toggles `include`↔`defer` only; `wont_do` comes from the emit's suggested state. The render reads final states as-is.

## Tests

All in `tests/test_create.py`, driving `create_plan` directly with `input_fn=_queue_input([...])`, a fake `claude_invoker`, and a fake `concept_invoker` returning canned concept JSON (never a real subprocess). Group under a new `TestCreateConceptGate` (and small additions to the render/gating classes). Enumerate each test with the behavior it covers; every one must be green before this step is done.

- `test_create_writes_concepts_sidecar` — a create run with a fake concept invoker writes `plan-details/<slug>/concepts.json` with per-node `state` / `signed_off` / `signed_off_at`.
- `test_deferred_section_rendered_from_tree` — a `defer` node's title/rationale appears under `## Deferred` in the written body.
- `test_out_of_scope_rendered_from_wont_do` — a `wont_do` node appears under `## Out of scope`.
- `test_render_uses_each_nodes_own_state` — a deferred parent with an included child renders only the parent under `## Deferred`; the child's mixed-subtree position does not defer it.
- `test_tree_overrides_synthesized_sections` — even when the body-synthesis fake returns different Out-of-scope/Deferred prose, the written sections come from the tree (assert the tree text present, the synthesized text absent for those two keys).
- `test_mapped_step_marked_deferred` — a deferred concept matching a proposed step sets that step's `scope=deferred` + a `status_note`; unmapped steps stay `committed`.
- `test_yes_accepts_unsigned` — under `yes=True`, the sidecar's nodes carry the suggested states with `signed_off=False`.
- `test_non_tty_accepts_unsigned` — with `sys.stdin.isatty()` patched False, same accept-unsigned outcome (mirrors the plan's gating matrix).
- `test_interactive_confirm_signs_off` — a scripted `input_fn` that reaches the confirm keystroke returns a tree with `signed_off=True` and a stamped `signed_off_at`.
- `test_concept_emit_none_falls_back` — a `concept_invoker` returning unparseable text yields no tree, no overwrite, and no crash; the two sections fall back (empty under `--iterate`).
- `test_resume_reuses_saved_tree` — a pre-written `concepts.json` makes the gate skip the emit round-trip (assert the `concept_invoker` is not called) and seed from the saved tree.
- `test_create_refreshes_fingerprint_after_plan_write` — capture incremental saves as unsigned records with an unset fingerprint, then assert the final sidecar fingerprints the written plan and retains the navigator's completed decisions/sign-off.
- `test_concept_invoker_is_the_only_emit_seam` — assert the concept emit is reached only via the injected `concept_invoker` (a spy), never the step-proposal `claude_invoker`.
- `test_rendered_sections_are_not_todo` — override the autouse `_disable_step3_todo_check` (as `TestCreatePlanRejectsTodoBody` does) so the real `_find_placeholder_body_sections` runs, and assert a tree-rendered create passes the fail-loud gate for these two sections.
- Distill-prompt behavior is covered by the existing distill unit tests staying green with the edited guidance and the unchanged 8-key `_DISTILL_SECTION_KEYS`.

## Acceptance criteria

- Running `create_plan` with a fake `concept_invoker` and scripted `input_fn` writes `plan-details/<slug>/concepts.json` with per-node `state`, `signed_off`, `signed_off_at`.
- The written plan's `## Deferred` section is built from `defer` nodes and `## Out of scope` from `wont_do` nodes; neither is independently synthesized when a tree exists.
- A deferred concept that maps to a proposed step sets that step's `scope=deferred` and a `status_note`.
- Under `yes=True` or a non-TTY stdin, suggested states are accepted and every node stays `signed_off=False`; only the interactive confirm keystroke sets `signed_off=True`.
- Re-running create over an existing `concepts.json` reuses the saved tree and does not call the concept emit invoker.
- Incremental pre-write saves remain unsigned resume state with an unset fingerprint; after the finalized plan markdown is written, the authoritative sidecar carries its current fingerprint and the completed navigator decision.
- `create_plan` exposes a `concept_invoker` seam defaulting to step 2's `shell_concept_invoker`; the conftest real-backend gate raises if a test leaves it defaulted to the real CLI.
- `plan_tool/prompts/distill-seed.md`'s single-plan shape still lists exactly 8 section keys; the distill unit tests pass unchanged.
- `uv run pytest tests/test_create.py -q` passes, including the new `TestCreateConceptGate` class and the live-TODO-gate render test.

## References

- [dataclasses — Data Classes (Python 3.13 docs)](https://docs.python.org/3/library/dataclasses.html) — the `ConceptTree` / `ConceptNode` / `ConceptDecision` shapes this step reads (owned by steps 1–3).
- [RFC 3339 — Date and Time on the Internet: Timestamps](https://www.rfc-editor.org/rfc/rfc3339) — the format of the `signed_off_at` / `updated_at` stamps the tests assert on.
- [datetime — Basic date and time types (Python docs)](https://docs.python.org/3/library/datetime.html) — timezone-aware UTC timestamps behind the sign-off stamp.

## Deferred

- Wiring concepts into `plan_tool/detail.py` (inline single-step sign-off; one consolidated sign-off after a full/batch run) — step 5.
- The two completeness concept checks (`concept-coverage` blocking, `concept-unsigned-deferral` advisory) and the per-audit, slug-keyed coverage recompute that stamps `covered_by` — step 6.
- `scope_out_step` flipping a carved step's concepts `include → defer` and carrying them into the forward-seed — step 7.
- The standalone `plan-tool scope-review` command and its drift-guard registration — step 8.
- Stamping `covered_by` on emitted concepts — step 2 leaves it empty; step 6 owns the durable recompute. This step's create-time step-scope map is a best-effort convenience, not the coverage source of truth.
- `--rederive` 3-way merge and reconcile → stale-tree flag linkage — plan-level Deferred.
