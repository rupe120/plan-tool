> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Add a recommend-only roadmap pointer to create split-proposal next steps

## Summary

When `create`'s distill pass short-circuits with a `SplitProposal`, extend `plan_tool/cli/authoring.py:_emit_split_proposal` and `_render_split_proposal_markdown` to print **generic, recommend-only** guidance naming the `roadmap` verb — prose only, no runnable `plan-tool roadmap … --from-existing …` line. The main design choice matches the plan architecture and `convergence` → `scope-out`: **detect decomposition here, point at the actuator there, never fabricate operands create does not have** (roadmap slug, concept-brief path). Keep the existing carve-and-`create --from-existing` next steps unchanged. On green, every new test in `tests/cli/test_authoring_cmds.py` passes, split-proposal stdout and the saved worksheet both mention `roadmap`, and no output contains a copy-pastable roadmap invocation with concrete slug or brief operands.

## Table of Contents

- [Summary](#summary) — what lands, the design choice, and green state
- [Why](#why) — gap after step 6 and why the pointer belongs in create's split path
- [Input](#input) — contracts from step 6 and the existing split-proposal surface
- [Files (creates vs edits)](#files-creates-vs-edits) — the two paths this step touches
- [Implementation](#implementation) — guidance text, call sites, constraints, rejected alternative
- [Tests](#tests) — new cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — plan fences binding this step
- [Deferred](#deferred) — explicitly later steps and docs

## Why

Step 6 closes the roadmap → create hand-off: a four-stage run prints runnable `plan-tool create <plan-id> --from-existing <draft-path>` lines from `plan_tool/cli/roadmap_cmd.py`. The inverse path — `create` detecting that a seed describes several independent plans — already exists: distill returns `CreateResult(split_proposal=…)` and `cmd_create` calls `_emit_split_proposal`, which prints per-plan slugs, saves a worksheet, and tells the operator to carve the seed and run `create --from-existing` for each. That advice stops at manual carving; it never names `plan-tool roadmap` as the structured decomposition path #208 adds. Operators who hit the split short-circuit get no pointer to the verb that now derives ordered plans and draft seeds from a concept brief. This step closes that one-way gap with operator text only — no new flags, no create→roadmap subprocess, no invented slug or brief path.

## Input

Land step **6** before implementing (`depends_on: 6`). Open the landed modules — code on disk wins over this detail.

**From step 6 (roadmap verb ships):**

- **`plan-tool roadmap <slug> --from-existing <concept.md>`** — the actuator this step names in generic prose; operands come from the operator, not from `create`'s split path
- **Roadmap → create handoff** in `plan_tool/cli/roadmap_cmd.py` — runnable `create --from-existing` lines against draft paths; the inverse direction this step completes

**Existing split-proposal surface at HEAD (`plan_tool/cli/authoring.py`):**

- **`cmd_create`** — when `result.split_proposal is not None`, calls `_emit_split_proposal(…)` and **`return 0`** immediately (no plan written; no `_print_next_steps` success block)
- **`_emit_split_proposal`** — stdout headline, optional worksheet save, final **`next:`** paragraph with carve + per-plan `create --from-existing` guidance
- **`_render_split_proposal_markdown`** — worksheet body with intro prose and per-entry carve commands

**From `plan_tool/create.py` (read-only — no edits in this step):**

- **`SplitProposal`**, **`SplitProposalEntry`**, **`CreateResult.split_proposal`** — unchanged; detection stays in the orchestrator, display stays in the CLI

**Precedent (read-only):**

- **`plan_tool/convergence_diagnosis.py:_scope_out_command`** — recommend-only preview without `--apply`/`-y`; **`_reseed_command`** uses a `<seed.md>` placeholder because the diagnosis has a plan slug — create's split path has **neither** roadmap slug **nor** concept brief, so this step must **not** mirror that command template for roadmap

## Files (creates vs edits)

- **New files:** none
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py` — add shared roadmap guidance text; append it in `_emit_split_proposal` stdout and in `_render_split_proposal_markdown` intro; update module docstring if it lists split-proposal outputs
  - `tests/cli/test_authoring_cmds.py` — extend `TestEmitSplitProposal` and `TestRenderSplitProposalMarkdown` with cases for the new guidance and the no-fabricated-command guard

## Implementation

### Foundational rule

**Whenever a split proposal is emitted, unconditionally append generic roadmap guidance.** No heuristic gate on seed size, plan count, or entry rationales — the plan's architecture treats detection as unconditional and recommend-only (same stance as the existing split short-circuit itself).

### Shared guidance text (single source)

- **Mint one module-level string** (constant or zero-argument helper) used by **both** `_emit_split_proposal` and `_render_split_proposal_markdown` so stdout and the saved worksheet never drift
- **Content requirements:**
  - **Name the verb** — the substring `plan-tool roadmap` or equivalent unambiguous reference to the `roadmap` subcommand must appear
  - **State the purpose in plain language** — decompose a concept brief into gated plans and draft seeds before running `create` on each seed (wording is flexible; intent is not)
  - **Stay generic** — do **not** print `plan-tool roadmap <slug> --from-existing …` with concrete or placeholder slug/brief operands; the audit finding `[split-proposal-roadmap-pointer]` exists because create cannot know those operands
  - **Recommend-only** — prose guidance only; no `--apply`, no `-y`, no suggestion that create will invoke roadmap

One acceptable shape (implementer may rephrase):

> For a project-sized concept, consider **`plan-tool roadmap`** with a concept brief to derive an ordered plan list and draft seeds before creating each plan individually.

### Where to attach it

**`_emit_split_proposal` (stdout):**

- Keep the existing per-plan listing, save prompt, and **`next:`** carve/create paragraph **unchanged in meaning**
- **Append** the roadmap guidance **after** the existing next-steps text (separate paragraph or continuation — either is fine if both blocks remain readable)
- **Do not** route this through `_print_next_steps` with a fake `(command, description)` tuple — that helper formats runnable commands; this step deliberately has no command operand

**`_render_split_proposal_markdown` (worksheet):**

- Add the same guidance near the **intro** (after the existing “no plan was created” explanation, before the per-plan H2 sections) so headless runs that only read `<slug>-split-proposal.md` see the pointer

**`cmd_create`:**

- **No signature or branch changes** — the only call site stays the existing `if result.split_proposal is not None:` block

### Rejected alternative

**Printing a templated roadmap command** — e.g. `plan-tool roadmap <slug> --from-existing <concept.md>` — even with angle-bracket placeholders. That reads as runnable and implies create knows which slug and brief to fill in; it does not (only the seed file and create slug are in scope). Step 6's roadmap handoff **can** print runnable `create` lines because roadmap loaded `04-roadmap.md` and resolved draft paths; create's split path has no symmetric inputs. Generic prose naming the verb is the correct asymmetry.

### Constraints (not free to vary)

- **Files footprint** — edits only in the two declared paths; no `roadmap.py`, `create.py`, or parser changes
- **No actuation** — do not subprocess, import `run_roadmap`, or add a `--roadmap` flag to `create`
- **Exit code** — split proposal remains **`return 0`**; guidance is advisory output only
- **Existing behavior preserved** — worksheet save rules (`yes` / non-TTY auto-save), seed left in place, no manifest write, per-entry `sed` carve lines when ranges exist
- **Stdout contract** — keep the headline `no plan created — the seed describes N independent plans:` intact for scripts that branch on it (`docs/CREATE_FROM_EXISTING_FLOW.md`, run-log `split_proposed` outcome)

### Shared locations (unchanged by this step)

- **`plan_tool/create.py`** — distill detection and `SplitProposal` construction; no edit
- **`plan_tool/cli/roadmap_cmd.py`** — roadmap → create handoff (step 6); inverse pointer only
- **`plan_tool/convergence_diagnosis.py`** — recommend-only fork rendering precedent; read-only
- **`docs/CREATE_FROM_EXISTING_FLOW.md`** — Multi-plan split proposal section; step 10 doc sweep

## Tests

Every listed test must be green before this step is done. Prefer `uv run pytest tests/cli/test_authoring_cmds.py -q -n auto`.

### Tests for this step

**Positive — guidance appears**

- `test_emit_split_proposal_prints_roadmap_guidance` — call `_emit_split_proposal` with `_proposal()` and assert stdout contains an unambiguous `roadmap` reference (e.g. `plan-tool roadmap`)
- `test_render_split_proposal_markdown_includes_roadmap_guidance` — rendered markdown from `_render_split_proposal_markdown` includes the same roadmap guidance theme

**Negative — no fabricated runnable roadmap line**

- `test_emit_split_proposal_does_not_print_runnable_roadmap_command` — stdout must **not** match a copy-pastable `plan-tool roadmap … --from-existing …` invocation (use a regex that forbids `--from-existing` on the same line as `plan-tool roadmap`, or equivalent strict check)
- `test_render_split_proposal_markdown_does_not_include_runnable_roadmap_command` — same guard on worksheet text

**Regression — existing split behavior unchanged**

- `test_yes_autosaves_worksheet_and_prints_summary` — still autosaves and prints the headline (update only if the shared constant changes unrelated substrings)
- `test_tty_decline_skips_save_but_prints_next_steps` — still prints carve/create next steps **and** includes roadmap guidance even when save is declined

**Optional (only if the implementer extends an existing case rather than duplicating):**

- Extend `test_main_create_split_proposal_does_not_stamp` in the same file to assert `main([...])` stdout/stderr mentions `roadmap` when the stubbed `create_plan` returns a split proposal — not required if helper-level tests above cover the behavior

## Acceptance criteria

- Calling `_emit_split_proposal` with any non-empty `SplitProposal` prints generic guidance that names the `roadmap` verb
- Neither `_emit_split_proposal` stdout nor `_render_split_proposal_markdown` output contains `plan-tool roadmap` followed by `--from-existing` with operand tokens
- The existing split-proposal headline, worksheet save behavior, per-plan slug listing, and carve/`create --from-existing` next steps still work (existing `TestEmitSplitProposal` cases pass)
- `uv run pytest tests/cli/test_authoring_cmds.py -q` passes
- `rg '_emit_split_proposal' plan_tool/` shows a single production call site in `cmd_create` — no new callers that skip the guidance

## Applicable guardrails

- **The plan's step intent (recommend-only, no invented roadmap invocation)** — this step adds prose only; it must not print a runnable `plan-tool roadmap … --from-existing …` line or call roadmap
- **The plan's Out of scope, auto-running downstream verbs** — no subprocess, no flag that invokes `roadmap`, `create`, `detail`, or `run` from the split path
- **The plan's Out of scope, merit / quality gates** — no check on whether roadmap is the "right" decomposition; unconditional text whenever `SplitProposal` fires
- **The plan intent, end-to-end hand-off** — completes the inverse of step 6's roadmap→create lines; both directions stay recommend-only printed guidance, not cross-verb automation

## Deferred

- **`docs/CREATE_FROM_EXISTING_FLOW.md` Multi-plan split proposal section** — step 10 operator-doc sweep; not in this step's `files:` list
- **`docs/ROADMAP_WALKTHROUGH.md` and `BACKLOG.md` #208 reconciliation** — step 10
- **Conditional "concept-sized" detection** — plan requires unconditional guidance; sizing heuristics belong in a different scope
- **Runnable roadmap command with placeholders** — rejected in Implementation; do not revisit without a create-side source for roadmap slug and concept-brief path
- **Auto-invoking `run_roadmap` from `cmd_create`** — explicitly out of plan scope
- **`plan_tool/cli/direct_cmd.py` split-proposal handling** — direct pipeline stops on split at the gate; no new surface required unless a later plan scopes it
