> **Auto-archived**: this plan was swept on 2026-07-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Let `cmd_create` deposit its `CreateResult` into a caller-provided namespace sink

## Summary

This step teaches `plan_tool/cli/authoring.py:cmd_create` to hand its in-memory `CreateResult` back to an in-process caller when one asks for it, instead of only returning an `int` exit code. The caller sets a mutable list on the argparse `Namespace` (an attribute like `_create_result_sink`); `cmd_create` appends the `CreateResult` to it once, right after `create_plan(...)` returns, so every downstream return path (split proposal, clean success, `iteration_incomplete`) carries the object. This copies the existing `_next_steps_sink` idiom already used between `cmd_detail`/`split` and `cmd_completeness`. On green, `cmd_create`'s public contract is unchanged for every current caller (no sink attribute → identical behavior and rc), and a caller that sets the sink can read the created plan's `CreateResult` without re-discovering it on disk. The direct-pipeline verbs (steps 4–5) rely on this hand-off; this step only adds the deposit and its tests.

## Table of Contents

- [Why](#why) — what's missing today and why the sink is needed now.
- [Files (creates vs edits)](#files-creates-vs-edits) — the one handler edit plus its two test files.
- [Implementation](#implementation) — the sink attribute, where the deposit lands, and the invariants to hold.
- [Tests](#tests) — capture, split-path, and absent-sink regression cases.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — argparse Namespace and pytest monkeypatch docs.
- [Deferred](#deferred) — reprocess path and downstream field-reading, left to other steps.

## Why

Today `cmd_create` returns only an `int` exit code. Every consumer of a freshly created plan re-discovers it on disk (parse the manifest, re-read the plan file). The direct-pipeline verbs that step 1's flow note (`docs/DIRECT_PIPELINE_FLOW.md`) describes chain `create → detail → …` in one process, and they need `create`'s result — the `plan_path`, whether the seed short-circuited into a split proposal, whether iteration aborted — without a disk round-trip. This step adds the smallest possible seam for that: an opt-in output channel on the existing `Namespace`, mirroring the `_next_steps_sink` list that `cmd_completeness` already fills for its parent. It lands before the verbs (they list step 2 in `depends_on`) so steps 4–5 have the hand-off to build against.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py` — in `cmd_create`, read a caller-set sink attribute off `args` and append the `CreateResult` to it once, immediately after the `create_plan(...)` call returns successfully.
  - `tests/test_create.py` — add sink-capture tests driving `cmd_create` with a stubbed `create_plan` and a `Namespace` carrying the sink.
  - `tests/cli/test_authoring_cmds.py` — add an absent-sink regression test confirming the default path (no sink attribute) is unchanged.

## Implementation

**What changes:** `plan_tool/cli/authoring.py:cmd_create` gains one output side channel. A caller that wants the result sets a mutable list on the `Namespace` before calling `cmd_create`; the handler deposits its `CreateResult` there and still returns the same `int` rc. Callers that don't set it are unaffected.

**Follow the existing sink idiom — don't invent a new shape.** The codebase already does exactly this between commands: `plan_tool/cli/completeness_phases.py` reads `getattr(args, "_next_steps_sink", None)` and, guarded by `isinstance(sink, list)`, extends it; `plan_tool/cli/authoring.py` (the completeness-tail helper) sets `completeness_args._next_steps_sink = next_steps` before dispatching. Reuse that shape:
- Name the attribute descriptively — one way: `_create_result_sink` (leading underscore marks it an internal cross-command channel, like `_next_steps_sink` and `_suppress_run_log`).
- Type it as a `list`. Read it with `getattr(args, "_create_result_sink", None)`; deposit only when `isinstance(sink, list)`. The `list` (not `None`) is the "caller wants it" signal, same as `_next_steps_sink`.
- Append the `CreateResult`, don't assign — the caller owns the container. A single-element list after a successful create is the expected shape.

**Where the deposit lands — the one constraint that matters.** Put the append **immediately after `result = create_plan(...)` returns successfully**, before the `if result.split_proposal is not None:` branch (the split-proposal short-circuit that returns 0). `cmd_create` has several return points below that call — the split-proposal early return, the clean `ok` return, and the `iteration_incomplete` return — and all three must carry the result. A single deposit right after the `create_plan` call covers every one of them without duplicating the write. Do **not** scatter the append across each return arm.

**Preserve the `CreateResult` invariants — deposit the object as-is.** `plan_tool/create.py:CreateResult` documents that `plan_path` is `None` **only** on the multi-plan split-proposal short-circuit (`split_proposal` set, no plan written); every normal create sets it. The sink must carry the object unchanged on the split path too, so a downstream caller can branch on `result.split_proposal is not None` / `result.plan_path is None` itself. This step does **not** read or interpret any `CreateResult` field — it only passes the whole object through. Field interpretation is the direct verbs' job (steps 4–5).

**Failure and skip paths — leave the sink empty, don't fabricate.**
- The two `create_plan` failure arms (`FileExistsError` / `CreateError` → `return 1`) produce no `CreateResult`. The sink stays empty; a caller reads the non-zero rc plus an empty sink as "create failed, nothing to hand off". Don't deposit a placeholder.
- The `--reprocess` early return (`_cmd_create_reprocess(args)` near the top of `cmd_create`) returns before `create_plan` runs and fills no sink. Direct verbs never pass `--reprocess`, so this is acceptable; note it as a known limit rather than plumbing the sink through reprocess (see Deferred).

**Call sites that need no update.** `cmd_create` is wired into dispatch via `register`/`Handler`; ordinary CLI invocation builds the `Namespace` from argparse and never sets `_create_result_sink`, so it reads absent → the deposit is skipped → behavior is identical. No existing caller changes.

## Tests

Primary capture tests live in `tests/test_create.py`, which already monkeypatches the `plan_tool.cli.authoring.create_plan` module global (see the `TestCmdCreateRunLog` suite's `patched_create_plan`) — the sanctioned seam for intercepting the orchestrator. Drive `cmd_create` with a stubbed `create_plan` returning a known `CreateResult` and a hand-built `argparse.Namespace` carrying the sink:

- `test_create_result_sink_receives_result` — a `Namespace` with `_create_result_sink = []` and a stubbed `create_plan` returning a `CreateResult` with `plan_path` set → after `cmd_create`, the sink holds exactly that `CreateResult` and rc is 0.
- `test_create_result_sink_receives_split_proposal` — stubbed `create_plan` returns a `CreateResult` with `split_proposal` set and `plan_path=None` → the sink holds that object (split path still deposits) and rc is 0.
- `test_create_result_sink_empty_on_create_failure` — stubbed `create_plan` raises `CreateError` → rc is 1 and the sink stays empty (no placeholder deposited).
- `test_create_result_sink_deposits_once` — assert the sink has length 1 after a successful create (the deposit isn't duplicated across return arms).

Backward-compat regression in `tests/cli/test_authoring_cmds.py` (whose split-proof convention avoids patching cli globals — keep to that): drive a create path that does not set `_create_result_sink` and assert `cmd_create` behaves exactly as before — returns its `int` rc and never raises `AttributeError` for the missing attribute:

- `test_cmd_create_without_sink_unchanged` — a normal `main(['create', …])` run (fake backend, no sink attribute) still returns 0 and writes the plan, proving the absent-sink default path is untouched.

### Test-creation order (feature step)

This is a feature step. Author the tests above alongside the `cmd_create` edit; each covers one behavior — deposit on success, deposit on split, empty on failure, single deposit, and absent-sink parity. Green-before-done gate: every new test must pass (`uv run pytest tests/test_create.py tests/cli/test_authoring_cmds.py -q`) before the step is finished.

## Acceptance criteria

- `cmd_create` reads `getattr(args, "_create_result_sink", None)` and, when it is a `list`, appends the `CreateResult` produced by `create_plan` exactly once.
- The deposit happens on all three post-`create_plan` return paths: split-proposal short-circuit, clean `ok`, and `iteration_incomplete`.
- On the split-proposal path the deposited `CreateResult` still has `split_proposal` set and `plan_path is None` (object passed through unchanged).
- When `create_plan` raises (`FileExistsError`/`CreateError`), rc is 1 and the sink is left empty.
- A `cmd_create` call with no `_create_result_sink` attribute returns the same `int` rc as before and raises no `AttributeError`.
- `cmd_create`'s return type stays `int`; no signature change.
- New tests in `tests/test_create.py` and `tests/cli/test_authoring_cmds.py` pass; the full suite stays green.

## References

- [argparse — Namespace](https://docs.python.org/3/library/argparse.html#argparse.Namespace) — the object the sink attribute rides on; confirms attribute-style access and that arbitrary attributes can be set by a caller.
- [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — for stubbing `plan_tool.cli.authoring.create_plan` in the capture tests without spawning a backend.

## Deferred

- Reading and acting on `CreateResult` fields (`plan_path`, `split_proposal`, `iteration_stage_failure`) — owned by the direct-jira / direct-run verbs (steps 4–5); this step only deposits the object.
- Filling the sink on the `--reprocess` path (`_cmd_create_reprocess`) — direct verbs never pass `--reprocess`, so it's left unplumbed; revisit only if a reprocess-driven in-process caller ever appears.
- The size-gate helper that inspects the deposited result for an over-large plan — step 3 (`plan_tool/cli/direct_cmd.py`).
