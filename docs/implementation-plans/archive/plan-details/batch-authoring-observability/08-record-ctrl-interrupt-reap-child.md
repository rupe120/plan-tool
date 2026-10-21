> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Record a Ctrl-C as an interrupt and reap the child for roadmap and run

## Summary

Closes the operator-interrupt story for both lanes. `plan_tool/backend_runner.py:run_streaming_once`'s internal bare-writer fallback (step 7) gains the interrupt half it deliberately withheld, so `run`'s own step execution — whose `RunLogWriter` reaches the runner through `launcher.py`'s ContextVar plumbing — now emits `run_interrupted` on Ctrl-C through the same runner mechanism batch callers got in step 7, with the child killed and reaped by step 3's existing net. `plan_tool/roadmap.py`'s two owned-writer `run_end` wrappers mark a `KeyboardInterrupt` as rc 130 / `"interrupted"` instead of today's generic rc-1 row with an empty error string. At the CLI layer, `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` gets its first `except KeyboardInterrupt` (clean exit 130, one stderr line, no traceback), and `plan_tool/cli/run_cmd.py`'s two existing `rc = 130`-then-bare-`raise` sites convert that re-raise into a real exit 130. Green when Ctrl-C during either command exits the process with 130 and no traceback, and the run-log JSONL shows the interrupt instead of an ambiguous generic error.

## Table of Contents

- [Summary](#summary) — what lands in each of the four production files
- [Why](#why) — the four interrupt gaps left after steps 3–7
- [Input](#input) — the step-3/4/5/7 contracts and HEAD facts this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — no new files; seven edits
- [Implementation](#implementation) — the fallback widening, the run_end marking, and the two CLI exit fixes
- [Tests](#tests) — the roster across the three declared test files
- [Acceptance criteria](#acceptance-criteria) — observable, checkable facts
- [References](#references) — signal, subprocess, and exit-code background
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step hardest
- [Deferred](#deferred) — the sibling CLI sites, `apply_finding` callers, and rendering work this step leaves out

## Why

Four related gaps survive steps 3–7, and each one makes an operator's Ctrl-C look like something else:

- **`run`'s lane records no `run_interrupted`.** Step 7's observer contract carries an interrupt hook, but its internal fallback for a bare `RunLogWriter` — the shape `run`'s `shell_invoker` passes, unedited since step 2 — deliberately covers only spawn and termination. Step 7's own detail names this step as the one that closes it, and pins the gap with `test_bare_run_logger_receives_no_interrupted_call_on_keyboard_interrupt` in `tests/test_backend_runner.py`. So after step 7, a Ctrl-C during a `run` step's claude call classifies `operator_interrupt` and reaps the child (steps 3–4), but writes no `run_interrupted` row.
- **`run`'s Ctrl-C exits 1 with a raw traceback.** Both `except KeyboardInterrupt` sites in `plan_tool/cli/run_cmd.py` — one in `cmd_run`, one in `_cmd_run_sweep`'s per-iteration loop — set a local `rc = 130` consumed only by the `finally:` block's `run_end` record, then bare-`raise`. `plan_tool/cli/app.py:main`'s catch-all handles only `Exception` (its own comment says `KeyboardInterrupt`/`SystemExit` pass straight through by design), so the interrupt reaches Python's default handler: traceback, exit 1. `BUG_BACKLOG.md`'s entry "A Ctrl-C during most CLI commands prints a raw traceback and exits 1, not the intended 130" documents the repo-wide class and explicitly assigns `run_cmd.py`'s two sites to this step.
- **`roadmap` has no handler at all.** `plan_tool/cli/roadmap_cmd.py` contains no `except KeyboardInterrupt` anywhere, so a Ctrl-C during a stage run tracebacks the same way.
- **`roadmap`'s `run_end` row is ambiguous on interrupt.** `plan_tool/roadmap.py:run_roadmap`'s `except BaseException`/`finally` wrapper already guarantees `run_end` and `in-flight.json` cleanup on every exit path — but its failure arm emits `outcome="error", rc=1, error=str(failure)`, and `str(KeyboardInterrupt())` is the empty string. An operator reading the JSONL cannot tell their own Ctrl-C from a real crash.

The event-side work for `roadmap` itself is already done: once step 7's `claude_invoke` observer is live, a roadmap stage call's Ctrl-C produces `run_interrupted` with no roadmap-specific code. What this step adds is narrower — the missing `run` lane adapter, the honest `run_end` bookkeeping, and clean exit codes at both CLI layers.

## Input

- **Step 5's `run_interrupted` event and `RunLogWriter.run_interrupted` method** — the record this step's fallback widening emits; its field vocabulary (including the `source` discriminator, with `"recovery_wait"` already used by step 5's wait-seam wrapper) is step 5's to own.
- **Step 7's observer contract on `run_streaming_once`** — the `run_logger` parameter accepts a bare `RunLogWriter`/`None` or a fuller observer; the internal fallback for a bare writer adds spawn/termination but not interrupt, and `claude_invoke` builds the full kind. Step 7 also settled `source="proc_wait"` for an interrupt caught at the runner's `proc.wait()`.
- **Steps 3–4's kill-and-classify path** — the `except BaseException` arm around `proc.wait()` kills and reaps the child before re-raising (step 3), and classifies a caught `KeyboardInterrupt` as `operator_interrupt` in the termination vocabulary (step 4). This step adds no reaping code; it rides that path.
- **`plan_tool/launcher.py`'s ContextVar plumbing at HEAD** — `run_step` is the *only* setter of `_run_logger_var` (one `set` site, in its `claude_call` phase); `shell_invoker` reads it and forwards it as `run_logger=` into `_run_streaming_once`, which after step 2 is a thin wrapper over `backend_runner.run_streaming_once`. `apply_finding` calls its invoker without setting the var. This single-setter fact is what scopes the fallback widening to `run_step`'s direct call — verify it still holds at implementation time before relying on it.
- **`BUG_BACKLOG.md`'s Ctrl-C entry** — prescribes the fix shape (`raise SystemExit(130)` at each site rather than translating in `main()`, so the run-log `finally` cleanup stays local) and carves `run_cmd.py`'s two sites out of its own scope into this step. The entry needs no edit when this step ships; it already describes the split.

## Files (creates vs edits)

**New files:** none — `plan_tool/backend_runner.py` and `tests/test_backend_runner.py` exist once step 2 lands.

**Existing files (edits only):**

- `plan_tool/backend_runner.py` — widen the bare-`RunLogWriter` fallback observer so the interrupt notification also reaches it, emitting `run_interrupted(source="proc_wait")`.
- `plan_tool/roadmap.py` — in both owned-writer `finally:` wrappers (`run_roadmap` and `apply_roadmap_seeds`), detect a captured `KeyboardInterrupt` failure and emit `run_end` with rc 130 and `error="interrupted"` instead of rc 1 with an empty error.
- `plan_tool/cli/roadmap_cmd.py` — add the module's first `except KeyboardInterrupt` in `cmd_roadmap`, covering its dispatch; return 130 after one stderr line; extend the docstring's exit-code enumeration.
- `plan_tool/cli/run_cmd.py` — at both existing `except KeyboardInterrupt` sites (`cmd_run`, `_cmd_run_sweep`), make the re-raise reach a real process exit 130 (`raise SystemExit(130)` per the backlog entry's fix shape); the `finally:` blocks stay as they are.
- `tests/test_backend_runner.py` — rewrite step 7's no-interrupt-for-bare-writer pin into the positive case; add the `None`-writer regression.
- `tests/cli/test_roadmap_cmd.py` — stub-based exit-130 cases per dispatch branch, plus one real-orchestrator case that reads the interrupt `run_end` row off the JSONL.
- `tests/cli/test_run_cmd.py` — exit-130 cases for both sites, plus a JSONL check that the `run_end` record still carries rc 130.

## Implementation

### The runner's bare-writer fallback gains the interrupt half (`plan_tool/backend_runner.py`)

- **The change:** when `run_streaming_once` catches a `KeyboardInterrupt` out of `proc.wait()` (step 3's arm, classified `operator_interrupt` by step 4), the internal fallback observer it builds for a bare `RunLogWriter` now also calls the writer's `run_interrupted` method (step 5) with `source="proc_wait"`, alongside the termination notification it already makes — mirroring step 7's pairing for caller-built observers, where the termination reason and the interrupt marker are two complementary facts about the same event. `run_logger=None` still produces no events at all.
- **Why this placement is the design decision.** `run_step` calls `shell_invoker`, not `claude_invoke`, so it never benefits from step 7's `claude_invoke`-built observer. Its writer reaches the runner as a bare `RunLogWriter` through the existing ContextVar chain (`launcher.py:run_step` sets `_run_logger_var` → `shell_invoker` reads it → the runner's `run_logger` parameter). The translation from that bare writer into the full observer protocol therefore belongs where the bare writer arrives: the runner's own fallback. The rejected alternative — a caller-built observer assembled in `launcher.py`, the way `claude_invoke` builds one — would duplicate an adapter the runner already has internally, and `plan_tool/launcher.py` is outside this step's declared files. `run` gets the event through the same mechanism batch callers use, not a second one.
- **Scope falls out of the plumbing, but say it in a comment.** Because `run_step` is the only setter of `_run_logger_var`, and `apply_finding` and `run --reconcile`'s paths never bind it, no `apply_finding` caller can deliver a bare writer to the runner today — widening the fallback reaches exactly `run_step`'s direct call, which is the step-intent fence. A short comment on the fallback should state that this reach is deliberate, so a future caller that starts passing a writer knows it is opting in.
- **Expected red sibling:** step 7's `test_bare_run_logger_receives_no_interrupted_call_on_keyboard_interrupt` pins the intermediate state this step retires. Rewrite it into the positive case (see Tests) rather than narrowing the change.
- **Wrap the new callback call the same way step 7 wraps every observer call** (`except Exception`, one stderr line, never a JSONL write from the handler) so a failing writer cannot break the unwind path that is in the middle of re-raising the interrupt.

### Honest `run_end` bookkeeping on interrupt (`plan_tool/roadmap.py`)

- Both owned-writer wrappers share one shape at HEAD: `except BaseException as exc: failure = exc; raise`, then a `finally:` whose failure arm emits `owned_logger.run_end(outcome="error", rc=1, error=str(failure))`. The class has exactly two members in this file — `run_roadmap`'s and `apply_roadmap_seeds`'s; `refresh_roadmap_seeds` opens no writer (it passes `run_logger=None` into `_run_stage`), so it has no third site. Fix both.
- **The edit:** in each failure arm, when `failure` is a `KeyboardInterrupt`, emit `rc=130` and `error="interrupted"` (matching `run_cmd.py`'s existing wording) instead of `rc=1` and the empty string `str(KeyboardInterrupt())` produces. Keep `outcome="error"` — minting a new outcome token would be a schema-vocabulary decision (`DATA_CONTRACT.md`) this plan does not make, and rc 130 plus the error text is unambiguous on its own. Step 5's termination-reason tracking additionally lets `run_end` report `operator_interrupt` when the runner saw the interrupt; that is step 5's mechanism, not something this edit re-implements.
- Nothing else in the wrappers changes: the `raise` stays, cleanup ordering stays, a caller-supplied writer stays the caller's to end.

### A clean exit for `roadmap` (`plan_tool/cli/roadmap_cmd.py`)

- `cmd_roadmap` gains one `except KeyboardInterrupt` covering its dispatch — one handler for the whole verb rather than per-branch copies, since every branch (stage run, `--refresh-seeds`, `--apply`, `--view`) should map Ctrl-C the same way. One way: wrap the dispatch body after the pre-dispatch `--mode`/`--id` validation. The stage-run and `--refresh-seeds` branches are the ones that actually invoke the backend and matter most; covering the others costs nothing.
- On catch: print one short line to stderr (e.g. `interrupted`) and return 130. No re-raise is needed here — `cmd_roadmap` already communicates by return code, and `run_roadmap`'s own wrapper has already run `run_end`/`in-flight.json` cleanup underneath by the time the exception reaches the CLI layer. A `KeyboardInterrupt` from the stage loop propagates cleanly to this handler: the attempt loop's invoker call at `plan_tool/roadmap.py:_run_stage` has no broad `except` around it, so nothing swallows the interrupt into a `FAILURE_INVOKE` retry.
- `cmd_roadmap`'s docstring enumerates its exit codes (2 / 1 / 0); add the 130 clause so the enumeration stays complete.

### A real exit 130 for `run` (`plan_tool/cli/run_cmd.py`)

- At both sites — `cmd_run`'s handler and `_cmd_run_sweep`'s per-iteration handler — replace the bare `raise` with `raise SystemExit(130)`, the fix shape `BUG_BACKLOG.md`'s entry prescribes for the whole class. The `finally:` blocks still run (`run_end` with rc 130 and `error="interrupted"`, then the telemetry-scope reset), `SystemExit` passes through `app.py`'s `Exception` catch-all untouched by design, and the process exits 130 with no traceback. `app.py` itself is not edited.
- Keep the local `rc = 130` / `err_msg = "interrupted"` assignments — they feed the `finally:` record and are correct as they stand.
- In the sweep, `SystemExit` ends the loop the same way the bare `KeyboardInterrupt` did; no other loop-exit bookkeeping changes. `cmd_direct_run` (which reaches `cmd_run` with a copied namespace) inherits the fix with no edit.
- A Ctrl-C landing *outside* these two `try` blocks (e.g. during context loading) still tracebacks — that is the repo-wide gap `BUG_BACKLOG.md` owns, deliberately not fixed here.

## Tests

### Tests for this step

Every test below must be green before this step is finished.

`tests/test_backend_runner.py`:

- `test_bare_run_logger_receives_run_interrupted_on_keyboard_interrupt` — rewrite of step 7's `test_bare_run_logger_receives_no_interrupted_call_on_keyboard_interrupt` (the old pin goes red by design): a bare fake writer passed as `run_logger`, with a fake proc whose `wait()` raises `KeyboardInterrupt`, receives exactly one `run_interrupted` call with `source="proc_wait"` alongside the `operator_interrupt` termination notification; the exception still propagates; the fake proc's kill and reap calls fired (step 3's net, re-asserted through this new path).
- `test_run_logger_none_gets_no_events_on_keyboard_interrupt` — `run_logger=None` on the same interrupt: no writer calls, child still killed and reaped, exception propagates — pins that callers without a writer keep today's behavior.
- `test_bare_writer_interrupt_callback_exception_does_not_break_the_unwind` — a bare writer whose `run_interrupted` raises; the `KeyboardInterrupt` (not the callback's exception) still propagates and the child is still reaped.
- Step 7's full-observer interrupt case (`test_full_observer_receives_interrupted_with_source_proc_wait_on_keyboard_interrupt`) stays green unchanged.

`tests/cli/test_run_cmd.py`:

- `test_cmd_run_keyboard_interrupt_exits_130` — monkeypatch `plan_tool.cli.run_cmd.run_step` to raise `KeyboardInterrupt`; `cmd_run` raises `SystemExit` with code 130, and no `KeyboardInterrupt` escapes.
- `test_sweep_keyboard_interrupt_exits_130` — same through `_cmd_run_sweep`, using the file's existing `_sweep_args`/`_ctx` helpers.
- `test_interrupt_run_end_row_still_records_rc_130` — after the interrupt, the run-log JSONL's `run_end` row carries `rc=130` and `error="interrupted"` — proves the `SystemExit` conversion did not skip the `finally:` record.

`tests/cli/test_roadmap_cmd.py` (module convention: stub `run_roadmap` as imported into `roadmap_cmd`'s namespace):

- `test_stage_run_keyboard_interrupt_exits_130` — stubbed `run_roadmap` raising `KeyboardInterrupt`; `cmd_roadmap` returns 130, prints one interrupted line to stderr, and no exception escapes.
- `test_refresh_seeds_keyboard_interrupt_exits_130` — same through the `--refresh-seeds` branch's stub.
- `test_apply_keyboard_interrupt_exits_130` — same through the `--apply` branch's stubbed `apply_roadmap_seeds`; `cmd_roadmap` returns 130 with the same one-line stderr message and no exception escapes — the third of the three branches the docstring's "every branch" claim names, and the only one this file's stub-level cases were missing before this step.
- `test_interrupted_stage_run_records_interrupt_run_end` — the third deliberate real-orchestrator exception in this file (precedent: `TestOverwriteAdviceIsPrintedExactlyOnce`): drive `cmd_roadmap` over the real `run_roadmap` with a stage `invoker` stub raising `KeyboardInterrupt`; assert the return is 130 *and* the run-log JSONL under `.plan-tool/runs/<slug>/` carries a `run_end` with `rc=130` and `error="interrupted"` — the only test that can see the `plan_tool/roadmap.py` wrapper edit and the CLI mapping paired, which neither layer-isolated side can show alone (and the reason no `tests/test_roadmap.py` addition is needed).
- `test_interrupted_apply_records_interrupt_run_end` — the same real-orchestrator pairing for the `--apply` branch: drive `cmd_roadmap --apply` over the real `apply_roadmap_seeds` with a stubbed step that raises `KeyboardInterrupt` mid-apply; assert the return is 130 and the run-log JSONL carries `run_end` with `rc=130` and `error="interrupted"` — `apply_roadmap_seeds`'s own `finally:` wrapper edit (Files) is otherwise unverified by any test in this step's roster, since the stub-level `test_apply_keyboard_interrupt_exits_130` above never opens a real writer to check.

Cross-file regression: `tests/test_cli.py`'s `test_keyboard_interrupt_passes_through` (app-level passthrough via `cmd_list`) stays green — `app.py` is untouched.

## Acceptance criteria

- Ctrl-C during a `plan-tool run` step execution exits the process with status 130 and no traceback, from both the single-step and `--all` sweep paths; the run-log `run_end` row for that run carries `rc=130` and `error="interrupted"`.
- Ctrl-C during a `plan-tool roadmap` stage run exits with status 130, one stderr line, no traceback; `run_roadmap`'s `run_end` row carries `rc=130` and `error="interrupted"` (not `rc=1` with an empty error), and `in-flight.json` is removed.
- Ctrl-C during `plan-tool roadmap --apply` exits with status 130 the same way; `apply_roadmap_seeds`'s `run_end` row carries `rc=130` and `error="interrupted"`, proven by a real-orchestrator test the same way the stage-run path already is.
- A `KeyboardInterrupt` during `backend_runner.run_streaming_once`'s `proc.wait()` with a bare `RunLogWriter` bound produces exactly one `run_interrupted` row (`source="proc_wait"`) and a termination notification with reason `operator_interrupt`; the child's kill and reap calls fire; the exception propagates.
- The same interrupt with `run_logger=None` produces no run-log rows and still kills and reaps the child.
- `rg 'except KeyboardInterrupt' plan_tool/cli/roadmap_cmd.py` returns exactly one site; `rg '\braise\b\s*$' -A0` on `run_cmd.py`'s two interrupt handlers returns nothing (both now raise `SystemExit(130)`).
- No edit to `plan_tool/cli/app.py`, `plan_tool/launcher.py`, or any `apply_finding` call path — `git diff --stat` for this step touches only the seven declared files.
- The full suite passes, including the rewritten `tests/test_backend_runner.py` interrupt pin and the untouched `tests/test_cli.py` passthrough test.

## References

- [signal — Set handlers for asynchronous events (Python)](https://docs.python.org/3/library/signal.html) — SIGINT→`KeyboardInterrupt` translation and the fact that it only ever lands on the main thread, which is what makes the runner's `proc.wait()` arm the single interception point.
- [subprocess — Subprocess management (Python 3.13)](https://docs.python.org/3/library/subprocess.html) — `terminate`/`kill`/`wait` semantics behind the reap this step's tests re-assert.
- [Built-in exceptions — SystemExit (Python)](https://docs.python.org/3/library/exceptions.html#SystemExit) — why `raise SystemExit(130)` reaches the process exit code while running `finally:` blocks on the way out; the mechanism behind the `run_cmd.py` fix shape.
- [JSON Lines specification](https://jsonlines.org/) — the record-per-line format the interrupt tests parse mid-file.

## Applicable guardrails

- **The step intent's scope fence (`run_step`'s direct call only)** — the fallback widening must not become a new cross-cutting parameter through the shared `walk_recommendations`/`_dispatch_apply_finding` dispatch, and no `apply_finding` call site gains events. This step satisfies the fence structurally (only `run_step` binds the ContextVar the runner's bare-writer path can see) rather than by adding per-caller machinery.
- **The plan's "## Out of scope", `apply_finding` exclusion** — every `apply_finding` caller keeps today's generic interrupt handling; nothing in this step's files may special-case one of them.
- **The plan's "## Out of scope", roadmap semantics** — the `plan_tool/roadmap.py` edit is bookkeeping in the `run_end` wrappers only; stage gates, retry budgets, feedback, and seed behavior are untouched.
- **The plan intent's `(rc, stdout)` contract** — `claude_invoke` and `shell_invoker` return shapes are unchanged; this step alters what is *recorded* and how the *process* exits, never what a caller receives.
- **The repo's exit-code convention** (non-zero only on failure-to-complete) — 130 on interrupt is a failure-to-complete, consistent with the convention; no findings-driven exit changes here.

## Deferred

- The roughly eight other CLI `rc = 130`-then-bare-`raise` sites (`plan_tool/cli/authoring.py`, `plan_tool/cli/review_cmd.py`, `plan_tool/cli/reconcile.py`) — owned by `BUG_BACKLOG.md`'s existing Ctrl-C entry, which already carves this step's two `run_cmd.py` sites out of its scope; no backlog edit is needed when this step ships.
- A repo-wide characterization test asserting every command exits 130 on `KeyboardInterrupt` — the backlog entry's suggested guard; it belongs with that entry's fix, not with this step's two-command scope.
- `run_interrupted`/spawn/termination for `apply_finding`'s call sites and the interactive walk paths — the plan's Out of scope; they keep today's generic `run_end(outcome="error")` handling.
- Rendering the interrupt in a `runs show`/`runs watch` view — the carved-out follow-on plan; this step's acceptance is satisfied by reading the JSONL directly.
- Handling other termination signals (SIGTERM, SIGHUP) — only SIGINT/`KeyboardInterrupt` is in this plan's liveness scope; other signals bypass Python's `KeyboardInterrupt` translation entirely and would need a signal-handler design of their own.
