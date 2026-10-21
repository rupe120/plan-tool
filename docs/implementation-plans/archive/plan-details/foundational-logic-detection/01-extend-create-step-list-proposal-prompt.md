> **Auto-archived**: this plan was swept on 2026-06-11 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Teach create's step-proposal prompt to flag foundational logic shared across the app

## Summary

Add one numbered instruction to the audit list returned by `plan_tool/create.py:_render_from_prompt` directing claude to identify the plan's *foundational logic* (the core behavior the plan changes) and grep the rest of the app for other locations that share it, then fold those locations into the relevant step's `files:` list or a dedicated step. This is a string-literal edit to one function — no JSON-shape change, no parser change, no new `Step` field. The instruction tells claude to surface shared locations *inside existing step shapes*, never as a new JSON key. On green, `_render_from_prompt("...")` contains the new foundational-logic guidance and the existing seven-item audit list plus gate/JSON-shape text are unchanged; the new test class asserts the instruction's presence.

## Table of Contents

- [Why](#why) — what shared-logic blindness costs the proposal phase today
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the exact prompt edit and why it stays schema-free
- [Tests](#tests) — prompt-content assertions, feature-step gate
- [Acceptance criteria](#acceptance-criteria) — checkable prompt/test outcomes
- [References](#references) — the docs an implementer consults
- [Deferred](#deferred) — schema fields, detection mechanics, downstream phases left out

## Why

- **The step-proposal prompt audits paths but not shared logic.** `_render_from_prompt`'s numbered list (items 1–7) tells claude to verify paths, grep for implied symbols, note dependencies, add tests, apply lessons, classify `change_type`, and optionally suggest gates — but nothing asks it to notice that the behavior a plan changes also lives in *other* call sites.
- **A plan that touches foundational logic in one place silently misses its siblings.** When the same validation/dispatch/formatting logic is duplicated or shared across modules, a proposal that only lists the description's named file ships a plan that fixes one copy and leaves the others drifted — exactly the class of incompleteness later phases can't recover, since `detail`/`run` trust the `files:` list as the footprint.
- **Surfacing shared locations at proposal time is the cheapest fix.** The proposal is the foundation every later phase builds on; folding "this logic also appears in X, Y" into the step's `files:` (or a new step) at create time is far cheaper than discovering the omission during reconcile.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — append one numbered instruction as item 8 in `_render_from_prompt`, after the item-7 gate block and before the JSON-shape line (no renumber of existing items).
  - `tests/test_create.py` — add a test class asserting the new instruction text renders in the prompt.

## Implementation

### `plan_tool/create.py` — `_render_from_prompt`

- **Insert a foundational-logic audit instruction into the numbered list** built by `_render_from_prompt`. The function returns one concatenated string literal whose audit steps are numbered `1.`–`7.` (path verification → symbol grep → dependencies → test coverage → lessons → `change_type` classification → optional `gate:`). Add the new instruction as item **8**, placed *after* the existing item 7 gate block and *before* the `"Then respond with ONLY a JSON array..."` line, so the audit guidance stays grouped ahead of the response-shape contract.
- **Instruction content (single numbered bullet):** direct claude to —
  - **Identify the plan's foundational logic** — the core behavior/rule the plan adds or changes (e.g. a validation predicate, a parsing routine, a dispatch branch), stated in one phrase.
  - **Grep the rest of the app for other locations that exercise the same logic** — duplicated blocks, parallel call sites, sibling modules implementing the same rule — using the same Glob/Grep audit already mandated by items 1–2.
  - **Surface each shared location as a candidate for review** — list it for the author to weigh, and where it plausibly belongs, fold it into the relevant step's `files:` list or propose a dedicated step (linked by `depends_on`) — including a consolidation/refactor step that dedups the shared logic into a single source where that is the right fix, not only an update-in-place; these are suggestions, not mandatory edits. Reuse the full-path-from-repo-root rule already stated in item 1.
- **Do NOT add a new JSON key.** The response shape advertised in the `'{"title": str, ...}'` line and re-summarized in the trailing `` `files` is existing files modified... `` sentence must stay exactly as-is. Shared-location findings ride inside the existing `files:`/`creates:`/new-step machinery — adding a `shared_locations:`-style key would be a `Step`-schema change, which is out of scope (the plan's frontmatter declares no such field) and would require a separate `_parse_steps_json` edit.
- **Renumber, don't reorder.** If the new instruction lands before item 7, bump the gate instruction to 8; the simplest edit inserts it as item 8 immediately after the gate block, leaving items 1–6 byte-identical. Item 7 ends the audit list with a `\n\n` separator before the `"Then respond with ONLY a JSON array..."` line, so inserting item 8 must split that into `\n` (closing item 7) + `\n\n` (closing item 8); the gate substrings the tests assert (`"Most steps need no gate"`, `"ephemeral"`) survive that split, so no test breaks. Pick the insertion point that keeps the path-verification items (1–2) and the new logic-scan instruction adjacent if it reads better, but renumber every following item consistently — the numbers are prose, not parsed.
- **Leave the `lessons_section` and `f"\n\nPlan description:\n{description}\n"` tail untouched** — the new instruction belongs in the static audit list, not the per-call appendix.

### Why a prompt-only change

- **`_parse_steps_json` needs no edit** — it already reads `title`/`complexity`/`change_type`/`rationale`/`files`/`creates`/`gate`/`depends_on` leniently; shared locations arrive as ordinary `files:` entries or extra step objects, both already parsed.
- **No `Step` field, no `write_plan`/`PLAN_FORMAT.md` change** — the output is still the same step objects; the only difference is that claude is now instructed to populate `files:` more completely.

## Tests

All cases live in `tests/test_create.py`, mirroring the existing `TestRenderFromPromptGate` precedent (which asserts substrings of the rendered prompt). Add a sibling class, e.g. `TestRenderFromPromptFoundationalLogic`:

- `test_prompt_requests_foundational_logic_scan` — `_render_from_prompt("Build a thing")` contains the foundational-logic instruction (assert a stable keyphrase such as `"foundational logic"`).
- `test_prompt_asks_to_surface_shared_locations` — the rendered prompt instructs surfacing *other* locations that share the logic (assert a phrase like `"share"`/`"shared"` near the instruction).
- `test_prompt_folds_shared_locations_into_files` — the instruction tells claude to fold findings into `files:`/a step, not a new key (assert it mentions `files:` in the shared-logic context).
- `test_no_new_json_key_advertised` — the JSON-shape line is unchanged: `'"gate": [str, ...]'` is still present and no JSON-key-shaped substring (`shared_locations` / `"foundational_logic":`) appears in the `{"title": str, ...}` shape (assert absence of an invented key substring, not the bare word `"foundational"`, which the foundational-logic instruction legitimately uses). Guards against accidentally turning a prose instruction into a schema change.
- `test_existing_gate_instruction_preserved` — the existing gate guidance still renders (assert `"Most steps need no gate"` and `"ephemeral"` survive the renumber), proving the edit didn't displace item 7.
- `test_instruction_is_generic_not_project_root` — the instruction is generic, not specific to the seed bug: assert the foundational-logic instruction text omits concept-specific wording (`"project-root"`, `"project root"`, `"path calculation"`, `"root-of-project"`), locking the plan-level "generic (not specific to project-root path calculation)" acceptance criterion.

### Test-creation order (feature step)

- This is a **feature** step — it changes what `_render_from_prompt` emits. Author all cases above **with** the prompt edit in the same change.
- **Green-before-done gate:** every new test in `TestRenderFromPromptFoundationalLogic` must pass, and the pre-existing `TestRenderFromPromptGate` / `TestParseStepsJsonGate` classes must stay green (the renumber must not perturb gate or JSON-shape text), before the step is considered finished. Run `uv run pytest tests/test_create.py -q`.

## Acceptance criteria

- `_render_from_prompt("Build a thing")` returns a string containing a foundational-logic / shared-location instruction (a stable keyphrase like `"foundational logic"` is present).
- The rendered prompt instructs folding shared locations into `files:` / a step, and advertises **no** new JSON key — the `{"title": str, ...}` shape line is byte-identical to HEAD and `'"gate": [str, ...]'` is still present.
- The existing audit items (path verification, symbol grep, test coverage, `change_type`, gate) all still render; `"Most steps need no gate"` and `"ephemeral"` remain.
- The instruction is generic, not specific to project-root path calculation — the rendered foundational-logic text contains no `"project-root"` / `"path calculation"` / `"root-of-project"` wording (asserted by `test_instruction_is_generic_not_project_root`).
- `_parse_steps_json` is unchanged and `tests/test_create.py::TestParseStepsJsonGate` / `TestParseStepsJsonChangeType` stay green.
- `uv run pytest tests/test_create.py -q` passes.

**Scope limit — does not fire on every create.** A seed carrying canonical `### N.` steps routes through the deterministic `extract_steps_from_canonical` and never invokes `_render_from_prompt`, so this step's foundational-logic instruction is silently skipped for those plans (this plan's own seed likely among them); `detail` (Step 2) still covers each such step. Read these criteria as guarantees for the prompt-driven proposal path, not for canonical-seed creates.

## References

- [ast — Abstract Syntax Trees](https://docs.python.org/3/library/ast.html) — background on how claude could parse code to spot foundational constructs while auditing; informs the *kind* of shared logic the instruction asks it to find (not used by this step's code).
- [Anthropic — Tool use (function calling) overview](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview) — how create drives claude with Glob/Grep/Read during the audit the new instruction extends.

## Deferred

- **A `Step` frontmatter field for shared locations** — out of scope; would require a plan-level schema decision and a `_parse_steps_json` change. Shared locations ride in `files:` for now.
- **Deterministic/AST-based shared-logic detection** (the `ast`/`difflib`/`tokenize`/tree-sitter machinery in the plan-level references) — this step only instructs the model; no in-tree detector is built here.
- **Mirroring the instruction into the `reconcile` prompt** — a strong follow-on, not a clean out-of-scope: `detail-reconcile.md` already proposes plan/detail footprint edits (adding undeclared files, flagging declared-but-absent ones) and runs in the `--iterate` convergence loop, making it the cheapest place to catch a sibling shared location missed at create/detail time. It is a separate prompt surface under `plan_tool/prompts/`, so extending it is a later step. The create-from-existing step path is already covered: `--from-existing` step generation runs through `_render_from_prompt`, which this step edits.
- **The create wizard's interactive review of shared-location findings** (analogous to `_ask_gates`/`_review_step_gates`) — no interactive surface is added; the instruction only shapes claude's JSON.
