# Step 3 — Add the interactive `navigate_concepts` walker with a drill-down level stack and per-selection persistence

## Summary

Add `navigate_concepts` to the `plan_tool/concept_tree.py` leaf (step 1): an interactive walk that lets an operator drill through the concept tree to any depth and mark each concept **include** / **defer** / **wont_do**, persisting after every change through an injected `save_fn`. The walk uses a **level stack** for indeterminate depth (generalizing the `_SPLIT` sentinel idea from `plan_tool/create.py` into a `_DRILL` action) and returns a frozen `ConceptDecision`, mirroring `plan_tool/scope_out.py:ScopeOutResult` and `plan_tool/launcher.py:EscalateResult`. The key decision: **sign-off is terminal and operator-only** — only the interactive `c` keystroke sets `signed_off=True` and stamps `signed_off_at`, and it may do so only after every descendant-bearing frame has been displayed for explicit review or accepted at that frame; `--yes` and non-TTY runs accept the suggested states but leave `signed_off=False`, matching the `yes → non-TTY → interactive` gate `plan_tool/scope_out.py:_confirm_scope_out` already uses. On green, a fake `prompt_fn` can cycle all three states and drill through a tree, each change is saved via `save_fn` without collapsing an existing `wont_do` decision, root confirmation cannot approve unseen descendants, and only an eligible `c` path returns a signed-off decision.

## Table of Contents

- [Why](#why) — what the leaf still lacks and why the navigator lands now
- [Input](#input) — the step 1 contract this walk reads and mutates
- [Files (creates vs edits)](#files-creates-vs-edits) — one leaf edit, one test-file edit
- [Implementation](#implementation) — level stack, keystrokes, per-selection save, terminal sign-off, the leaf-purity constraint
- [Tests](#tests) — toggle/drill/confirm/gating/re-entry coverage
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — dataclasses, datetime, RFC 3339
- [Deferred](#deferred) — gate wiring, coverage stamping, helper consolidation

## Why

Step 1 gave the concept tree a shape, a place on disk, and a stable id; step 2 populates it from Claude with every node `signed_off=False`. Nothing yet lets a **human** review those concepts and sign off. The whole feature exists to turn a silent deferral into an **operator-gated** choice (see the plan's Problem statement), and the sign-off flag flips only through an interactive walk. This step adds that one walk — reused by all three wiring surfaces (`create`, `detail`, `scope-review` in steps 4/5/8) — so those steps wire one already-tested navigator instead of inventing three copies. It lives **in the leaf** so those three callers reuse it with no import cycle: it reimplements the ~10-line choice/number-list/yes-no input logic locally rather than importing `_ask_int_list` / `_ask_choice` from `plan_tool/create.py`.

## Input

This step depends only on **step 1's `plan_tool/concept_tree.py` leaf** (`depends_on: 1`). It reads and mutates that step's shipped contract; do not re-specify it here — follow the names step 1 lands. What the walk touches:

- **`ConceptNode` fields** — the walk reads `title`, `depth`, `parent_id`, `order`, `path`, `rationale` for display; cycles `state` through `include`, `defer`, and `wont_do`; and on the terminal confirm sets `signed_off` and `signed_off_at`. It never edits `id`, `covered_by`, or `source`.
- **`ConceptTree`** — the walk operates on a passed-in tree and hands the same object to `save_fn`. It does not recompute `plan_fingerprint` or `updated_at`; step 1's `save_concepts` owns those when the injected `save_fn` closure calls it.
- **`save_concepts` / `read_concepts`** — the caller (a later step) loads the tree with `read_concepts` and injects a `save_fn` closure bound to `concepts_path(plan_path)` and `save_concepts`. This step's tests can inject a spy `save_fn` instead of touching disk.

If step 1's final field names differ from the above, follow step 1's shipped contract — it is the owner.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — add `navigate_concepts`, the frozen `ConceptDecision` result, a local `InputFn` type alias, the `_DRILL` action sentinel, the local input helpers (number-list / choice / yes-no), and a small helper that summarizes a node's descendant states for the display marker. Keep every added first-party import (if any) function-local so the leaf-purity check from step 1 stays green.
  - `tests/test_concept_tree.py` — add the navigator tests listed below (toggle, drill, confirm, gating, re-entry, marker, empty-tree).

## Implementation

**Add `navigate_concepts` with the signature the plan pins.** From the plan's Architecture §C:

```
navigate_concepts(tree, *, prompt_fn: InputFn, yes: bool,
                  save_fn: Callable[[ConceptTree], None]) -> ConceptDecision
```

- **`prompt_fn: InputFn`** — the input seam, `Callable[[str], str]`. Define `InputFn` locally in the leaf (both `plan_tool/create.py` and `plan_tool/review_walk.py` already define the same alias; the leaf can't import either without a cycle, so it declares its own — mirror-not-share).
- **`yes: bool`** — the unattended flag; drives the gate below.
- **`save_fn: Callable[[ConceptTree], None]`** — the single writer. The walk calls it after every state change; it never calls `save_concepts` directly. This keeps the leaf pure and lets the caller bind the closure to `concepts_path(plan_path)`.
- Add a clock seam so `signed_off_at` is testable — one way: a `clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)` param, or a `now: datetime | None` like step 1's `save_concepts`. Either is fine; the hard rule is **sample it once at the confirm** so every node's `signed_off_at` matches. Step 1 declares `ConceptNode.signed_off_at` as `str | None`, so **format the sampled `datetime` to the ISO-8601 UTC string** with `"%Y-%m-%dT%H:%M:%SZ"` (exactly how `save_concepts` formats `updated_at`) before assigning it — never stamp the raw `datetime`, which would break `asdict`/JSON round-trip.

**Return a frozen `ConceptDecision`, mirroring `ScopeOutResult` / `EscalateResult`.** A `@dataclass(frozen=True)` whose `outcome` is one of a small fixed set — recommend:
- `"signed-off"` — the interactive `c` path ran; nodes are stamped.
- `"accepted-unsigned"` — `--yes` or non-TTY accepted the suggested states; `signed_off` stays `False`.
- `"empty-tree"` — the tree has no nodes; nothing prompted, nothing saved.

Carry the final `tree` on the result so a caller can read it back without re-loading. Keep the field set minimal, like the two sibling results.

**The level stack is the core mechanism — generalize `_SPLIT` into `_DRILL`.** `plan_tool/create.py` uses a `_SPLIT` sentinel (`_ask_change_type` returns it, `_review_step_change_types` branches on it) to signal "this isn't a normal answer, it's a structural action". Do the same here with a `_DRILL` sentinel for the drill keystroke. Loop shape:
- Keep a stack of frames; each frame is the current parent whose children are being reviewed (the root frame reviews `parent_id is None` nodes).
- Render the current frame's children in `order`, numbered, each line showing an include/defer/won't-do marker, the title, and the `rationale`.
- Read one line from `prompt_fn`, dispatch on it, repeat until the walk ends.
- Popping past the root ends the walk unsigned (or an eligible `c` ends it with sign-off).

**Keystrokes (from plan §C) — dispatch these:**
- **Comma-separated numbers** — cycle the named children `include → defer → wont_do → include`. Reuse the validate-and-reprompt shape of `plan_tool/create.py:_ask_int_list` (parse ints, reject out-of-range, reprompt on bad input) but validate against the current frame's child indices, not step ids. An existing `wont_do` node is displayed and retained unchanged unless the operator explicitly selects it to advance the cycle.
- **`d N`** — drill into child `N`: push a frame for that node's children. This is where `_DRILL` comes in. If `N` has no children, print a note and stay put rather than pushing an empty frame.
- **`u` / Enter** — pop up one frame; popping the root frame ends the walk.
- **`a`** — explicitly accept this frame as suggested (leave the children at their current suggested `state`), mark the frame reviewed, and persist; does **not** sign off.
- **`c`** — confirm and sign off only when every descendant-bearing frame has been displayed for explicit review or accepted at that frame. If any such frame remains unresolved, report it and keep the walk open without stamping any node. Once eligible, set `signed_off=True` and stamp `signed_off_at` (from the once-sampled clock) across the tree, persist, and end the walk with `outcome="signed-off"`.

Track reviewed frames by their parent node id (with a root sentinel) for the duration of the walk. Rendering a frame marks it explicitly reviewed; `a` also records explicit acceptance for that frame. Eligibility for `c` is computed against every frame whose parent has children, so visiting only the root never authorizes sign-off of an unvisited deeper frame.

**Persist after every change — no all-or-nothing at the end (plan §C).** Call `save_fn(tree)` after each toggle and each level `a`ccept, not only at `c`. Before saving a changed decision, clear that node's prior approval with `signed_off=False` and `signed_off_at=None`; only a subsequent interactive `c` restores the stamp for the affected approval scope. This is the key correctness rule: a SIGINT, crash, or closed TTY mid-walk must never lose a deep sign-off session or leave a changed state carrying an obsolete approval. The walk operates on the tree it was handed; a caller resumes by loading the saved tree with `read_concepts` and calling `navigate_concepts` again, which **continues from that state** rather than restarting. The navigator itself invalidates-then-saves; the seed-from-saved-state behavior is a property of the caller passing the already-saved tree. A mid-walk save leaves changed decisions unsigned; only `c` flips them back.

**Sign-off is terminal and operator-only.** `signed_off=True` + `signed_off_at` are set only on an eligible interactive `c` path after every descendant-bearing frame was reviewed or explicitly accepted. Every state-changing toggle or level accept invalidates the affected approval before its mid-walk `save_fn` write; a non-changing accept does not restore or forge a stamp. This is the whole point of the gate — it is *operator* sign-off, so an unattended run or a root-only review must not forge it.

**Gate `yes → non-TTY → interactive`, mirroring `plan_tool/scope_out.py:_confirm_scope_out`.** Before entering the interactive loop:
- **`yes=True`** — accept the tree's current suggested states as the safe default, persist once through `save_fn`, and return `outcome="accepted-unsigned"` with `signed_off=False`. No prompting.
- **Non-TTY and not `yes`** (`not sys.stdin.isatty()`) — same as `yes`: accept-and-persist, unsigned, `accepted-unsigned`. Never block on input with no operator present. `plan_tool/create.py` guards its gates the same way (`sys.stdin.isatty() and not yes`).
- **Interactive TTY** — run the level-stack loop above.

**The descendant-state marker.** Add a small helper that summarizes a node's subtree for the display marker (plan §C: `[x]` include, `[ ]` defer, `[!]` won't-do, `[-]` mixed-descendants). For a node with children, the marker is derived: all descendants `include` → `[x]`, all `defer` → `[ ]`, all `wont_do` → `[!]`, otherwise `[-]`. A leaf node shows its own state's marker. The three-state cycle is the persistence rule for both emitted and operator-changed nodes; rendering, accepting a level, resuming, or signing off never normalizes `wont_do` to `defer`.

**Parent and child states are independent.** A toggle changes only the selected node; `a` accepts only the current states and never propagates a parent state downward; descendant mixtures never derive or overwrite the parent's persisted state. The descendant marker is therefore display-only. Mixed subtrees remain signable once every descendant-bearing frame satisfies the review rule, with each node signed off in its own current state.

**Leaf-purity constraint (must hold).** `plan_tool/concept_tree.py` is a stdlib-only leaf: `grep -E '^(from|import) plan_tool' plan_tool/concept_tree.py` must still return nothing after this step (step 1's acceptance criterion). So:
- Reimplement the number-list / choice / yes-no input logic **locally** — do not import `_ask_int_list` / `_ask_choice` / `_ask_yn` from `plan_tool/create.py` (that import would create the very cycle the leaf avoids).
- Any stdlib-only need (`sys` for `isatty`, `datetime` for the stamp) imports normally at module top; those aren't first-party.

**Foundational logic and its siblings.** The core behavior is an *interactive multi-level walk with per-selection persistence and a terminal operator confirm*. The same shape already exists at three sites, all kept separate on purpose:
- `plan_tool/create.py:_review_step_change_types` / `_ask_change_type` (the `_SPLIT` sentinel + numbered-choice loop) — the closest analog; `_DRILL` mirrors `_SPLIT`.
- `plan_tool/create.py:_ask_int_list` / `_ask_choice` / `_ask_yn` — the input primitives this step re-derives locally.
- `plan_tool/scope_out.py:_confirm_scope_out` — the `yes → non-TTY → interactive` gate idiom this step follows.

Consolidating these input helpers into one shared module is a refactor `detail` can't mint and would touch files outside this step (`create.py`, `scope_out.py`) — route it to `## Deferred` for reconcile, don't expand this step's set of files.

## Tests

Add to `tests/test_concept_tree.py` (unit, unmarked, hermetic, own `tmp_path`). Inject a fake `prompt_fn` returning a scripted list of keystrokes and a spy `save_fn` that records the trees it's handed. Each test below must be green before the step is done.

- `test_state_cycle_persists_each_selection` — selecting a child cycles `include → defer → wont_do → include` and calls `save_fn` for each change.
- `test_existing_wont_do_is_preserved_without_explicit_selection` — rendering, accepting, resuming, and confirming leave an existing `wont_do` state intact.
- `test_toggle_reprompts_on_bad_input` — a non-numeric / out-of-range number reprompts (like `_ask_int_list`) and does not raise.
- `test_drill_pushes_and_pops_levels` — `d N` enters child `N`'s children; `u` returns to the parent frame; toggles at the deeper level persist.
- `test_drill_into_childless_node_stays` — `d N` on a leaf prints a note and does not push an empty frame.
- `test_accept_level_persists_unsigned` — `a` persists the current level via `save_fn` and leaves `signed_off=False`.
- `test_confirm_requires_every_descendant_frame_reviewed_or_accepted` — `c` at the root reports unresolved descendant-bearing frames, stamps nothing, and keeps prompting until each frame has been displayed or explicitly accepted at that frame.
- `test_confirm_signs_off_and_stamps` — after every descendant-bearing frame is reviewed or accepted, `c` sets `signed_off=True` and a non-null `signed_off_at` on the nodes and returns `outcome="signed-off"`.
- `test_clock_sampled_once_at_confirm` — with an injected fixed clock, all `signed_off_at` values are equal and the clock is read once.
- `test_yes_accepts_suggested_but_unsigned` — `yes=True` keeps suggested states, `signed_off` stays `False`, `outcome="accepted-unsigned"`, and `save_fn` is called once (safe default persisted).
- `test_non_tty_leaves_unsigned` — patch `sys.stdin.isatty()` to `False` with `yes=False`: accept-and-persist, unsigned, `accepted-unsigned`, no prompt read.
- `test_state_change_invalidates_prior_signoff` — toggling a previously signed node clears its `signed_off` and `signed_off_at` before `save_fn` observes it; a later interactive `c` restores the stamp for the affected approval scope.
- `test_reentry_continues_from_saved_state` — passing a tree that already has some toggles/sign-off continues from that state (does not reset), proving interrupt-safe resume.
- `test_empty_tree_returns_empty_outcome` — a tree with no nodes returns `outcome="empty-tree"`, prompts nothing, saves nothing.
- `test_descendant_marker_include_defer_wont_do_mixed` — the marker helper returns `[x]` for all-include descendants, `[ ]` for all-defer, `[!]` for all-won't-do, and `[-]` for mixed.
- `test_parent_state_does_not_propagate_to_descendants` — toggling or accepting a parent leaves every descendant state unchanged, and a mixed marker does not rewrite the parent state.
- `test_result_is_frozen` — `ConceptDecision` is a frozen dataclass (attribute assignment raises), matching `ScopeOutResult`.
- `test_navigator_uses_only_injected_save_fn` — the walk writes only through `save_fn`; assert the spy is the sole writer (no direct `save_concepts` call).

Also keep the step 1 leaf-purity test green: `grep -E '^(from|import) plan_tool' plan_tool/concept_tree.py` returns nothing.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Land each test above **with** the code that makes it pass. Green-before-done gate: `uv run pytest tests/test_concept_tree.py -q` passes and the full suite stays green.

## Acceptance criteria

- `navigate_concepts(tree, *, prompt_fn, yes, save_fn, …) -> ConceptDecision` exists in `plan_tool/concept_tree.py`.
- Comma-separated numbers cycle a child through `include`, `defer`, and `wont_do`; existing `wont_do` states persist unless explicitly cycled; `d N` drills in; `u`/Enter pops up; `a` accepts a frame without state normalization; `c` signs off only after every descendant-bearing frame was displayed for explicit review or accepted at that frame.
- Every toggle and every level accept calls `save_fn` before the walk ends (per-selection persistence); each changed decision clears any prior `signed_off` and `signed_off_at` before that save.
- An eligible interactive `c` path is the only one that sets `signed_off=True` and stamps `signed_off_at`; root `c` cannot sign unseen descendants, and `--yes` and non-TTY runs return `outcome="accepted-unsigned"` with `signed_off=False`.
- All `signed_off_at` values from one `c` confirm are equal (clock sampled once).
- An empty tree returns `outcome="empty-tree"` and prompts/saves nothing.
- `ConceptDecision` is a frozen dataclass.
- `grep -E '^(from|import) plan_tool' plan_tool/concept_tree.py` still returns nothing (all first-party imports function-local).
- `uv run pytest tests/test_concept_tree.py -q` passes.

## References

- [dataclasses — Data Classes (Python 3.13 docs)](https://docs.python.org/3/library/dataclasses.html) — the `@dataclass(frozen=True)` used for `ConceptDecision`, matching `ScopeOutResult` / `EscalateResult`.
- [datetime — Basic date and time types (Python docs)](https://docs.python.org/3/library/datetime.html) — producing the timezone-aware UTC `signed_off_at` stamp (`datetime.now(timezone.utc)`), sampled once at confirm.
- [RFC 3339 — Date and Time on the Internet: Timestamps](https://www.rfc-editor.org/rfc/rfc3339) — the ISO-8601/RFC 3339 UTC format for `signed_off_at`, consistent with step 1's timestamp fields.

## Deferred

- **Wiring `navigate_concepts` into `create` / `detail` / `scope-review`** — steps 4, 5, 8. This step ships the walk and its `save_fn` seam only; no orchestrator calls it yet, so the resume-from-saved-state behavior is exercised here only through a test that passes a pre-populated tree.
- **The concept-emit producer (`emit_concept_tree`)** — step 2. Step 3 depends only on step 1's tree shape; it navigates whatever tree it's handed and does not emit.
- **Computing / stamping `covered_by` and the two completeness checks** — step 6. The walk never edits `covered_by`.
- **The serial-only mutation invariant for the parallel `completeness-apply` path** (never write `concepts.json` inside a worker) — enforced at the caller/gate level in step 6, not in this leaf. The navigator's single injected `save_fn` already keeps it a caller-controlled, serial write.
- **Cascade-on-state-change to descendants** — not required; state changes apply to the explicitly selected node only.
- **Consolidating the interactive input helpers** (`_ask_int_list` / `_ask_choice` / `_ask_yn` in `plan_tool/create.py`, the `_confirm_scope_out` gate in `plan_tool/scope_out.py`, and this leaf's local copies) into one shared module — reconcile-owned; it touches files outside this step and `detail` cannot mint a refactor step.
