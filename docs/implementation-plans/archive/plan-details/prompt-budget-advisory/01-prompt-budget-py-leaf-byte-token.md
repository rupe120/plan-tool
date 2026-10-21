> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add `prompt_budget.py` leaf with the byte-to-token estimate and the color-gated advisory warning

## Summary

Add a new stdlib-only leaf `plan_tool/prompt_budget.py` that turns a prompt's byte count into a conservative token estimate, compares it against a model context-window budget, classifies headroom into `ok` / `warn` / `high`, and — only at `warn`/`high` — emits a color-gated advisory to stderr with a per-block breakdown. Two public functions: `estimate_prompt_budget(...)` (pure, returns a frozen `PromptBudget`) and `maybe_warn_prompt_budget(...)` (emits the advisory and returns the same `PromptBudget` so a later step can record telemetry). The advisory never blocks the invoke and never changes rc — same surface-and-return discipline as the `convergence` diagnostic. On green, the leaf plus its unit tests (`tests/test_prompt_budget.py`) exist and pass; no orchestrator wires it yet (that is steps 3–7).

## Table of Contents

- [Why](#why) — what's missing today and why the leaf comes first.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files this step adds.
- [Implementation](#implementation) — the estimate, the headroom classifier, the emit gate, and the leaf import rule.
- [Tests](#tests) — the unit cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the token-counting and TTY docs that ground the heuristic.
- [Deferred](#deferred) — orchestrator wiring, telemetry, and the shell backstop left to later steps.

## Why

The tool only learns a prompt was too big **after** a call fails: `plan_tool/claude_errors.py` classifies `ClaudeFailureKind.CONTEXT_OVERFLOW` on a failed invoke, and the operator has already burned the call. `prompt_bytes` is computed all over the codebase (`plan_tool/backend.py:prompt_bytes`, `plan_tool/launcher.py:_streaming_prompt_bytes`, logged through `plan_tool/shell.py` and `plan_tool/run_log.py`) but it is accounting, not a safeguard — nothing compares it to a budget before sending. This step lands the shared measuring stick every wiring step (3–7) will call: a single leaf that estimates tokens, judges headroom, and warns. Building it first, in isolation, lets its heuristic and thresholds be unit-tested against the `ok` / `warn` / `high` boundaries before any orchestrator depends on it.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompt_budget.py` — the leaf: `PromptBudget` dataclass, `estimate_prompt_budget`, `maybe_warn_prompt_budget`, and the named threshold/window constants.
  - `tests/test_prompt_budget.py` — unit tests for the estimate, the boundary classification, the emit gate, and color gating.

- **Existing files (edits only):** none. This step is self-contained; no orchestrator is wired here.

## Implementation

**Add one frozen dataclass and two functions to `plan_tool/prompt_budget.py`.** The estimate is pure; the emit function layers a color-gated warning on top of it.

- **`PromptBudget` — a frozen dataclass carrying the verdict.** Fields: `total_bytes: int`, `estimated_tokens: int`, `context_window: int`, `headroom_ratio: float`, `level: str` (`"ok"` / `"warn"` / `"high"`), and `blocks: tuple[tuple[str, int], ...]` (the per-block breakdown, name→bytes, empty when the caller passed none). Keep it in-memory only — it is a return value this step never writes to disk, so it carries no `DATA_CONTRACT.md` / drift-guard obligation (step 2 records a primitive projection into telemetry, not this dataclass).

- **Name the thresholds and the window as module constants** so BACKLOG #72 telemetry can retune them later without hunting magic numbers:
  - `BYTES_PER_TOKEN = 3.5` — the conservative bytes-per-token divisor.
  - `DEFAULT_CONTEXT_WINDOW = 200_000` — the ~200K-class fallback window when the caller passes no `context_window`, chosen as an illustrative Anthropic-class window size (actual per-model windows are loaded at runtime into `plan_tool/model_specs.py:ModelSpec.context_window` from an external limits catalog, not pinned in-repo).
  - `WARN_HEADROOM_RATIO = 0.40` and `HIGH_HEADROOM_RATIO = 0.15` — the headroom fractions below which the advisory fires.
  - `LEVEL_OK = "ok"`, `LEVEL_WARN = "warn"`, `LEVEL_HIGH = "high"` — the level literals, exported so wiring steps and step 2's telemetry key on them by name.

- **`estimate_prompt_budget(total_bytes, *, context_window=None, blocks=None) -> PromptBudget`** is the pure core:
  - Estimate tokens with `math.ceil(total_bytes / BYTES_PER_TOKEN)` — round **up**, so the estimate is conservative (never under-reports).
  - Resolve the window: `context_window or DEFAULT_CONTEXT_WINDOW`. Guard a non-positive window (fall back to the default) so a bad `context_window=0` from an upstream spec can't divide by zero.
  - Compute `headroom_ratio = (context_window - estimated_tokens) / context_window`. It goes **negative** when the estimate exceeds the window — that's fine, it lands in `high`.
  - Classify **high first, then warn, then ok** (order matters — a tight prompt satisfies both `< 0.40` and `< 0.15`): `high` when `headroom_ratio < HIGH_HEADROOM_RATIO`, else `warn` when `headroom_ratio < WARN_HEADROOM_RATIO`, else `ok`.
  - Normalize `blocks` (a mapping or a sequence of `(name, bytes)`) into a tuple sorted by bytes **descending** so the breakdown leads with the dominant block. Missing/empty → empty tuple.

- **`maybe_warn_prompt_budget(total_bytes, *, context_window=None, blocks=None, surface="", remedies=(), stream=None) -> PromptBudget`** is the emit gate:
  - Call `estimate_prompt_budget(...)` to get the `PromptBudget`.
  - Return it **silently** at `ok` — no output, this is the whole point of avoiding advisory fatigue.
  - At `warn`/`high`, format a short advisory and emit it, then return the budget. Include: the level, the `surface` label (which assembly point the advisory is for, when the caller passes one), estimated tokens vs window, the top few blocks from `budget.blocks`, and any `remedies` strings the caller passed (the runnable structural remedies for that surface — e.g. `--step`, distill/split, `scope-out`, lower `--max-passes`). Cap the block list to the top handful (e.g. 3–5) so the warning stays scannable.
  - **Emit through the shared diagnostic helper, not a raw `print`.** Reuse `plan_tool/style.py:warn` (yellow `warning:` prefix, stderr default) so this advisory looks like every other diagnostic the tool emits. `style.warn` already routes color through `plan_tool/style.py:color_enabled`, which honors the same `NO_COLOR` / `PLAN_TOOL_FORCE_COLOR` / TTY signals — so passing `stream` (default `sys.stderr`) gives you the required "plain on a pipe/non-TTY" gating for free. Let `stream` be injectable so tests can capture output.

- **Leaf import rule — keep it a leaf, keep the import graph acyclic.** The plan calls for a telemetry-style leaf. `plan_tool/telemetry.py` imports nothing first-party; this leaf needs color gating, so the one acceptable first-party import is `plan_tool/style.py` (`color_enabled`, `warn`) — `style` is itself a leaf (only `plan_tool.schema` under `TYPE_CHECKING`), so importing it introduces no cycle and reuses the tool's one owner of diagnostic formatting. Do **not** import any orchestrator (`create`, `detail`, `launcher`, `review`, `shell`) or `model_specs` — the caller resolves and passes `context_window` in; this leaf never fetches a catalog. One way to stay honest here: add a test asserting `plan_tool.prompt_budget`'s module imports are limited to stdlib plus `plan_tool.style`.

- **Foundational logic and its siblings.** The core rule this step adds is *byte→token estimate + headroom classification + advisory emit*. The byte-counting half already exists elsewhere as **accounting** — `plan_tool/backend.py:prompt_bytes`, `plan_tool/launcher.py:_streaming_prompt_bytes` — but none of those compares against a budget. This step does **not** touch them; the wiring steps (3–7) feed their byte totals into this leaf. Leaving those call sites unchanged here is deliberate, not an oversight (see Deferred).

## Tests

All cases live in `tests/test_prompt_budget.py`. This is a **feature** step: write these unit tests alongside the implementation, and every one must be green before the step is done.

- `test_estimate_rounds_tokens_up` — `estimated_tokens == ceil(total_bytes / 3.5)` for a byte count that isn't a clean multiple.
- `test_estimate_uses_default_window_when_none` — with `context_window=None`, the budget's `context_window` is `DEFAULT_CONTEXT_WINDOW`.
- `test_estimate_guards_nonpositive_window` — `context_window=0` falls back to the default rather than dividing by zero.
- `test_level_ok_above_warn_threshold` — a small prompt (headroom ≥ 0.40) classifies `ok`.
- `test_level_warn_between_thresholds` — headroom in `[0.15, 0.40)` classifies `warn`.
- `test_level_high_below_high_threshold` — headroom `< 0.15` classifies `high`.
- `test_level_high_when_estimate_exceeds_window` — estimate larger than the window gives a negative headroom and `high`.
- `test_boundary_at_warn_ratio` — headroom exactly at `WARN_HEADROOM_RATIO` stays `ok` (pins the `<` boundary).
- `test_blocks_sorted_by_bytes_descending` — a passed block map comes back as a tuple ordered largest-first.
- `test_maybe_warn_silent_at_ok` — `maybe_warn_prompt_budget` writes nothing to the captured stream when `ok`, and still returns the `PromptBudget`.
- `test_maybe_warn_emits_at_warn_and_high` — emits an advisory containing the top block name and any passed remedy strings when `warn`/`high`.
- `test_maybe_warn_includes_surface_label` — when a `surface` string is passed, the emitted advisory contains it.
- `test_maybe_warn_returns_budget` — the returned object is the same `PromptBudget` the caller can hand to telemetry later.
- `test_maybe_warn_plain_on_non_tty` — with a captured non-TTY stream (and no `PLAN_TOOL_FORCE_COLOR`), the emitted text carries no ANSI escapes.
- `test_maybe_warn_never_raises` — the function returns normally and produces no exception regardless of level (it is advisory, not a gate).
- `test_leaf_imports_are_cycle_free` — the module imports only stdlib plus `plan_tool.style` (asserts it stays a leaf).

## Acceptance criteria

- `plan_tool/prompt_budget.py` exists and exposes `estimate_prompt_budget`, `maybe_warn_prompt_budget`, `PromptBudget`, and the named constants (`BYTES_PER_TOKEN`, `DEFAULT_CONTEXT_WINDOW`, `WARN_HEADROOM_RATIO`, `HIGH_HEADROOM_RATIO`, the three level literals).
- `estimate_prompt_budget(total_bytes=…)` returns `estimated_tokens == math.ceil(total_bytes / 3.5)` and classifies `ok` / `warn` / `high` at the 0.40 / 0.15 headroom boundaries, checking `high` before `warn`.
- With `context_window=None`, the budget uses `DEFAULT_CONTEXT_WINDOW` (200_000); a non-positive `context_window` falls back to it without raising.
- `maybe_warn_prompt_budget` writes nothing at `ok`, emits a color-gated advisory at `warn`/`high`, and in every case returns the `PromptBudget` without raising and without any return value a caller could read as a block/rc change.
- When a `surface` string is passed, the emitted `warn`/`high` advisory contains it.
- On a non-TTY stream (no force-color), the emitted advisory contains no ANSI escape codes.
- `plan_tool/prompt_budget.py` imports only the standard library plus `plan_tool.style`; it imports no orchestrator and no `model_specs`.
- `uv run pytest tests/test_prompt_budget.py -q` passes.

## References

- [Anthropic — Token counting](https://docs.anthropic.com/en/docs/build-with-claude/token-counting) — how Claude counts prompt tokens; grounds the byte→token heuristic.
- [Anthropic API — Count Message tokens](https://docs.anthropic.com/en/api/messages-count-tokens) — the count-tokens endpoint, for sanity-checking the conservative `ceil(bytes / 3.5)` estimate against real counts.
- [Anthropic — Models overview (context windows)](https://docs.anthropic.com/en/docs/about-claude/models/overview) — per-model window sizes; the basis for the ~200K default window and the headroom thresholds.
- [Python — math.ceil / math module](https://docs.python.org/3/library/math.html) — `math.ceil`, used directly in the round-up token estimate.
- [Python — io.IOBase.isatty / sys streams](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — TTY detection behind `color_enabled`, ensuring plain output on a pipe/non-TTY.

## Deferred

- **Orchestrator wiring** (`generate_detail`, `create_plan`, `audit_plan_until_stable`, `run_step`) — steps 3–6 call this leaf at each assembly point and pass named blocks + surface-specific remedies.
- **The `shell.claude_invoke` total-bytes backstop** — step 7 owns it; this leaf neither emits from `shell.py` nor concerns itself with the shared-seam double-fire (accepted; BACKLOG #99).
- **`telemetry.record_prompt_budget` and its `DATA_CONTRACT.md` entry** — step 2. This step only returns the `PromptBudget`; it records nothing.
- **`detail --dry-run` breakdown printing** — step 3.
- **Resolving `context_window` from a real per-backend catalog** — the leaf takes a `context_window` parameter, but no wiring step in this plan resolves it; per-model window resolution (including `model_specs.context_window`) is deferred at the plan level, so callers leave it unset and the leaf uses `DEFAULT_CONTEXT_WINDOW`.
- **Changing what gets embedded** (raising the 4 KB embed, symbol-aware excerpting) — that is BACKLOG #97; this plan only measures and warns.
