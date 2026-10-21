> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Warn on prompt budget in `create_plan` across the distill, steps, and synthesis phases

## Summary

Wire the step-1 prompt-budget leaf into the three prose-heavy Claude phases of the create wizard: seed distillation, initial step proposal, and body-section synthesis. Just before each phase actually sends its prompt, estimate the prompt against a context-window budget, emit the advisory only when headroom is tight, and record one telemetry event tagged with that phase. The key design decision: `create_plan` has **three separate real-invoke functions** (`plan_tool/create.py:propose_distilled_seed_from_claude`, `propose_steps_from_claude`, `propose_body_sections`) — not one funnel like `detail.py:_author_step_detail` — so the hook is a single shared private helper called once from each function's real-invoke `else:` branch, which the resumed-from-checkpoint branch skips (no send → no advisory). On green, a large seed or step-proposal prompt warns on stderr, telemetry carries one `prompt-budget` event per invoked phase, and the advisory never changes the return value or blocks the invoke. Edits land only in `plan_tool/create.py` and `tests/test_create.py`.

## Table of Contents

- [Why](#why) — the gap this closes on the create path.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits.
- [Implementation](#implementation) — the shared hook, the three call sites, the per-phase blocks, and the constraints.
- [Tests](#tests) — the unit cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the token-counting docs that ground the heuristic.
- [Deferred](#deferred) — the other create phases, per-model window, and dry-run left out of scope.

## Why

The create wizard assembles some of the largest prompts the tool sends. The distill prompt (`plan_tool/create.py:_render_distill_prompt`) embeds the whole raw seed. The step-proposal prompt (`_render_from_prompt`) embeds the description plus the accumulated lessons block (`render_lessons_block(load_lessons(...))`). The synthesis prompt (`_render_synthesis_prompt`) embeds the seed source text plus the fetched reference docs. Any of these can overflow the context window on a big seed or a large lessons/reference bundle, and today the tool only learns that **after** the call fails — `plan_tool/claude_errors.py:ClaudeFailureKind.CONTEXT_OVERFLOW` is classified on a burned call. Each phase already measures `prompt_bytes = len(prompt.encode("utf-8"))` for the run log (see the `run_logger.install_call_end_sink` / `reporter.start_step(..., prompt_bytes=...)` blocks in each function) but nothing compares it to a budget before sending. Step 1 landed the shared measuring stick (`plan_tool/prompt_budget.py`) and step 2 landed the recorder (`plan_tool/telemetry.py:record_prompt_budget`); this step feeds the three create prompts into that stick and surfaces the result. No prompt-budget wiring exists in `plan_tool/create.py` yet — this step is net-new.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/create.py`:
    - Add a module-level import of the step-1 leaf function `maybe_warn_prompt_budget` from `plan_tool.prompt_budget`, and step-2's `record_prompt_budget` folded into the existing `from plan_tool.telemetry import (...)` block. Import at module top (not lazily) so tests can monkeypatch `plan_tool.create.<name>`, mirroring why `apply_finding` is imported module-level.
    - Add one small private helper (see Implementation) that runs the warn-and-record for a phase, single-sourced so all three call sites are identical.
    - Call that helper once in each of the three functions' real-invoke `else:` branch — `propose_distilled_seed_from_claude`, `propose_steps_from_claude`, `propose_body_sections` — right after `prompt_bytes = len(prompt.encode("utf-8"))` and before the invoke, passing that phase's content blocks.
  - `tests/test_create.py` — add the unit tests below (spy on the leaf/recorder module-level names; drive each `propose_*` function directly with a fake invoker and `NullReporter`, per this file's convention in `TestProposeStepsFromClaudeProgress` and `TestProposeBodySectionsFromClaude`).

## Implementation

**Fire the advisory once per phase, from a single shared helper.** Unlike the detail path — where every send funnels through `_author_step_detail`, so step 3 needed one edit — the create path sends from three sibling functions. Rather than triplicate the warn-and-record logic, add one private helper and call it from each phase. This keeps the three hooks identical (same best-effort guard, same one-advisory-per-send discipline) and shrinks each call site to one line.

- **Add the shared helper, one way `_maybe_warn_create_budget(...)`.** Suggested shape: `_maybe_warn_create_budget(*, total_bytes, blocks, phase, surface, repo_root, plan_slug)`. First **confirm `maybe_warn_prompt_budget`'s actual parameters and arity at HEAD** — step 1 owns and merges that signature, and it is not landed yet — then call it passing only the arguments its signature accepts (`total_bytes` plus whatever of `blocks=` / `surface=` / remedy hints it declares; drop `surface` from the helper's own params if the leaf takes no such kwarg). It emits to stderr only at `warn`/`high`, is `color_enabled`-gated, and returns the `PromptBudget`. Then record the decision with step-2's `record_prompt_budget(repo_root, plan_slug=plan_slug, phase=phase, total_bytes=total_bytes, advisory=budget.level, estimated_tokens=budget.estimated_tokens, context_window=budget.context_window, headroom_ratio=budget.headroom_ratio, blocks=budget.blocks)`. Project the `PromptBudget` to plain primitives at this call site — the recorder takes ints/strings, never the `PromptBudget` type. Wrap the whole body so it cannot raise into the wizard (best-effort by contract, but the helper must also swallow its own slips); guard the `record_prompt_budget` call on `repo_root is not None` since the recorder needs a repo root to write and tests often omit it.

- **Resolve `context_window` as `None`.** The create invoker shells out to a backend CLI; resolving that backend's real window is out of scope (see Deferred). Pass nothing for `context_window` so the leaf falls back to its `DEFAULT_CONTEXT_WINDOW`, matching the plan's deferral of per-model window resolution and step 3's choice.

- **Place the call in each phase's real-invoke branch, before the send.** In all three functions the structure is the same: a `if cached is not None:` branch that reuses the checkpointed `raw` (no send), paired with an `else:` branch that computes `prompt_bytes = len(prompt.encode("utf-8"))` and then calls `raw = invoker(prompt)`. Put the helper call inside the `else:` branch, right after `prompt_bytes` is computed and before the invoke. Reuse that existing `prompt_bytes` as `total_bytes`. Because the resumed branch never enters the `else:`, a phase that resumes from a checkpoint never warns — a warning for a prompt that is never sent is a false positive, and advisory fatigue is a named risk in the plan.

- **Warn once per phase, on the initial send — not the repair retry.** Each phase has a one-shot repair retry (`_render_distill_prompt(..., repair_error=...)`, `_render_synthesis_prompt(..., repair_error=...)`, and the second-attempt reprompt in `propose_steps_from_claude`). Do **not** add a second advisory on the repair path: it is an error-recovery branch, the size delta is small, and one advisory per phase is the intent. Fire only before the initial `raw = invoker(prompt)`.

- **Per-phase blocks are the local content strings — compute them inline.** The breakdown is display-only; it does not need to sum to `total_bytes` (template scaffolding is omitted on purpose), and each phase already holds its content strings in local scope. Keep the block lists to pure byte-length reads (they cannot raise), dropping any empty block:
  - **distill** (`propose_distilled_seed_from_claude`): `[("seed", len(source_text.encode("utf-8")))]` — `source_text` is the raw seed.
  - **steps** (`propose_steps_from_claude`): `[("description", len(description.encode("utf-8"))), ("lessons", len(lessons_block.encode("utf-8")))]` — both are already in scope (`lessons_block` is built at the top of the function). Drop the lessons entry when the block is empty.
  - **synthesis** (`propose_body_sections`): `[("seed", len(source_text.encode("utf-8"))), ("reference-docs", len(reference_docs.encode("utf-8")))]` — `source_text` and `reference_docs` are the function's inputs. Drop the reference-docs entry when empty.

- **Tag each phase distinctly in telemetry.** Pass `phase="create-distill"`, `phase="create-steps"`, and `phase="create-synthesis"` respectively, following step 2's `"create-steps"` example so the recorded distribution separates the three assembly points. Pass `plan_slug=slug or ""` (the `slug` kwarg each function receives may be `None`; empty string matches step 2's unresolved-slug convention). Use a matching `surface` label per phase for the advisory body (e.g. `"create seed distillation"`), and pass any phase-relevant remedy hints only if step 1's `maybe_warn_prompt_budget` accepts them — treat that signature as step 1's contract; reference it, don't restate it.

- **The hook lives in the function, so every call site is covered.** `propose_steps_from_claude` is called twice in `create_plan` (the initial proposal and the later re-propose); putting the hook inside the function means one edit covers both without touching the call sites.

Constraints and gotchas that are **not** free to vary:

- **The advisory must never block or change rc.** The invoke, the parse/validate, and each function's return value (`DistillOutcome`, `list[Step]`, the body-sections dict) must be identical whether the level is `ok`, `warn`, or `high`. The hook only reads bytes and emits.
- **Never let the advisory raise into the wizard.** `maybe_warn_prompt_budget` and `record_prompt_budget` are best-effort by contract, but the shared helper must also swallow its own errors — a formatter slip or an unwritable telemetry path must not sink a create run.
- **One advisory per invoked phase.** Fire before the initial send; skip the resumed branch and the repair retry.
- **Keep the leaf names module-level in `create.py`.** Import at module top so tests monkeypatch `plan_tool.create.maybe_warn_prompt_budget` / `record_prompt_budget`. `plan_tool.telemetry` is a stdlib-only leaf and `plan_tool.prompt_budget` a near-leaf (stdlib + `plan_tool.style`), so neither top-level import creates a cycle with `create.py`.

**Foundational logic and its siblings.** The core rule this step adds is *measure the assembled create prompt, judge headroom, warn + record before sending*. The same byte→budget check is wired into the detail path by step 3 (`plan_tool/detail.py`) and will be wired into `run`/`shell` by steps 5–7. The single-source of the measuring rule is step 1's `plan_tool/prompt_budget.py`; this step only feeds it from three new call sites and adds no second copy of the estimate. The `prompt_bytes` byte-counting already present in each phase (the `install_call_end_sink` / `start_step(prompt_bytes=...)` blocks) is accounting for the run log — this step reuses that number and leaves those accounting paths untouched.

## Tests

All in `tests/test_create.py`. The distill function's round-trip tests live in `tests/test_distill.py` and synthesis has `TestProposeBodySectionsFromClaude`; keep the new **advisory** tests together in `tests/test_create.py` (the declared file) since all three `propose_*` functions are importable from `plan_tool.create` and these tests exercise the create-phase budget wiring, not phase-specific round-trip behavior. Spy on the leaf/recorder by monkeypatching the module-level names on `plan_tool.create`; drive each function directly with a fake `invoker` and `NullReporter`.

This is a **feature** step: write these unit tests alongside the implementation, and every one must be green before the step is done.

- `test_distill_warns_before_invoke` — `propose_distilled_seed_from_claude` calls `maybe_warn_prompt_budget` once with `total_bytes == len(prompt.encode("utf-8"))` and a `seed` block; the fake invoker still fires and the outcome is unchanged.
- `test_distill_records_prompt_budget` — one `record_prompt_budget` with `phase="create-distill"` and `advisory` equal to the returned budget's level.
- `test_steps_warns_before_invoke` — `propose_steps_from_claude` calls the advisory once with a non-empty blocks list including a `description` block; steps still parse and return.
- `test_steps_records_prompt_budget_phase` — one `record_prompt_budget` with `phase="create-steps"`.
- `test_synthesis_warns_before_invoke` — `propose_body_sections` calls the advisory once with a `seed` block; the body-sections dict is returned unchanged.
- `test_synthesis_records_prompt_budget_phase` — one `record_prompt_budget` with `phase="create-synthesis"`.
- `test_advisory_does_not_change_result` — with the warn spy forced to report level `high`, each phase still returns its normal result and the invoker was still called (advisory never blocks or flips rc).
- `test_resumed_phase_does_not_warn_or_record` — with a valid checkpoint seeded so the phase resumes from cache, neither `maybe_warn_prompt_budget` nor `record_prompt_budget` is called (no invoke → no advisory).
- `test_repair_retry_warns_once` — a phase whose first response fails validation and retries once still emits exactly one advisory (fired on the initial send, not the repair).
- `test_advisory_never_raises` — with the recorder spy set to raise, the phase completes normally (the shared helper swallows it).
- `test_no_record_when_repo_root_none` — driving a phase with `repo_root=None` warns but does not attempt to record (guard on `repo_root`).

**Green-before-done gate:** every test above must pass before this step is done. The existing `TestProposeStepsFromClaudeProgress`, `TestProposeBodySectionsFromClaude`, and `tests/test_distill.py` round-trip tests must stay green unchanged — the advisory is additive and must not perturb the prompt, the parse, or the returned result.

## Acceptance criteria

- Each of `propose_distilled_seed_from_claude`, `propose_steps_from_claude`, and `propose_body_sections` calls the step-1 advisory exactly once on the real-invoke path, with `total_bytes` equal to the rendered prompt's UTF-8 byte length and a non-empty per-phase block breakdown.
- Each phase records exactly one `prompt-budget` telemetry event tagged `phase="create-distill"` / `"create-steps"` / `"create-synthesis"` respectively, with `advisory` equal to the returned `PromptBudget.level`.
- A phase that resumes from a valid checkpoint triggers no advisory and no telemetry event.
- A phase that takes its one repair retry still emits exactly one advisory (on the initial send).
- The advisory never changes any phase's return value or rc and never blocks the invoke: with the level forced to `high`, distillation/step-proposal/synthesis all return their normal results.
- The shared helper never raises into the wizard — a raising recorder or a formatter slip does not sink a create run.
- With `repo_root=None`, the phase warns but records nothing.
- All new `tests/test_create.py` cases pass; existing create/distill/synthesis tests remain green.

## References

- [Anthropic — Token counting](https://docs.anthropic.com/en/docs/build-with-claude/token-counting) — how Claude counts prompt tokens, grounding the byte/token estimate the advisory compares against the window.
- [Anthropic — Models overview (context windows)](https://docs.anthropic.com/en/docs/about-claude/models/overview) — per-model context-window sizes behind the ~200K-class default window this step relies on via `context_window=None`.
- [Python — io.IOBase.isatty / sys streams](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — TTY detection behind `color_enabled`, the reason the advisory prints plain on a pipe/non-TTY.

## Deferred

- **The other create-wizard Claude phases** — reference-doc fetch, `propose_create_gates`, the foundational-logic sweep, and slug suggestion each send their own prompt but are smaller and not named in this step's scope. Wire them only if a later step or reconcile calls for it.
- **Per-model context-window resolution** — this step passes `context_window=None` and uses the leaf's default window; resolving the backend's real window from `plan_tool/model_specs.py` is plan-level Deferred.
- **A `create --dry-run`-style breakdown print** — the detail path prints an unconditional breakdown on `detail --dry-run` (step 3); create has no equivalent inspection mode in scope here.
- **Shared-seam double-fire** between these named-block advisories and the generic `shell.claude_invoke` backstop — the backstop (step 7) also fires on these sends, so each emits an extra advisory line + a blockless `shell-backstop` telemetry record. Accepted, not suppressed here; filed as **BACKLOG #99**.
- **Outcome-linkage** of a recorded advisory to the actual `CONTEXT_OVERFLOW` failure it predicted — BACKLOG #72 later phases, not here.
