> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Run batch claude calls through the shared runner instead of subprocess.run

## Summary

Rewires `plan_tool/shell.py:claude_invoke`'s per-attempt seam to spawn through `plan_tool/backend_runner.py:run_streaming_once` (the shared Popen supervisor steps 2–4 built for `run`) instead of `subprocess.run`, so every one of `claude_invoke`'s seven callers picks up the 900-second silence kill, the configured-timeout kill, and the kill-on-any-exception net for free. `shell.py:_run_once` and `_normalize_batch_stdout` — the buffered-spawn function and its stream-json-collapse helper — are deleted outright, along with `_run_once`'s `PLAN_TOOL_SHELL_DEBUG`-gated debug prints and its own synthetic `subprocess.TimeoutExpired`-to-`BACKEND_TIMEOUT_SENTINEL` glue. The one new production behavior is `redaction_ready`, a boolean `run_streaming_once` gains (default `True`, so `run`'s call sites are untouched); `claude_invoke` passes `False`, which makes the runner's `-v` tool-input-summary line print the literal `[OMITTED]` instead of the real (still unredacted) summary — the fail-closed guarantee that lets this step land and commit on its own before step 7's redaction exists. `claude_invoke` still passes no `run_logger`/observer to the runner, so none of the runner's own `claude_stream_event` / `claude_call_progress` / `claude_call_stall_suspected` JSONL rows fire for a batch call yet (step 7); the silence-kill and configured-timeout protections apply regardless, and the `backend_spawn` / `backend_termination` / `backend_recovery_wait` / `run_interrupted` events step 5 already wired into `claude_invoke`'s recovery-loop seams keep firing exactly as before, now sourced from the runner's return value instead of `_run_once`'s. Green when `claude_invoke`'s `(rc, stdout)` contract, retry/backoff behavior, and run-log emission are unchanged from step 1's pinned baseline, a wedged batch child is reaped by the shared silence kill, and `shell._run_once` / `_normalize_batch_stdout` / `PLAN_TOOL_SHELL_DEBUG` no longer exist anywhere in the codebase.

## Table of Contents

- [Summary](#summary) — what moves onto the shared runner and the one new production flag
- [Why](#why) — the gap this step closes and what makes it safe to land alone
- [Input](#input) — the steps 2–5 contracts this step builds on, including one not in `depends_on`
- [Files (creates vs edits)](#files-creates-vs-edits) — the declared edits plus one justified addition
- [Implementation](#implementation) — the seam rewrite, the collapse rule, exception handling, `redaction_ready`, and the deletions
- [Tests](#tests) — the test roster, dominated by porting `test_shell.py`'s fakes onto Popen
- [Acceptance criteria](#acceptance-criteria) — observable, checkable facts
- [References](#references) — background reading for the mechanisms this step touches
- [Applicable guardrails](#applicable-guardrails) — plan fences this step's new behavior sits inside
- [Deferred](#deferred) — what stays out, and which later step (or backlog entry) covers it

## Why

Today `claude_invoke`'s `_run_once` spawns via `subprocess.run(capture_output=True, timeout=...)`: no heartbeat, no stall suspicion, and no silence kill — a wedged `roadmap` stage call (or any of `claude_invoke`'s other six callers) blocks `subprocess.run`'s read-to-EOF forever. `run`'s own call path already solved exactly this with `plan_tool/backend_runner.py:run_streaming_once` (relocated in step 2, given a kill-on-any-exception net in step 3, and a configured-timeout kill plus a closed termination-reason vocabulary in step 4) — but nothing wires `claude_invoke` onto it yet. This step is that wiring: the single point where all seven `claude_invoke` callers (`annotate.py`, `create.py`, `detail.py`, `jira.py`, `lessons.py`, `review.py`, `roadmap.py`, plus `shell.shell_concept_invoker`) simultaneously gain the same liveness protection `run` has had since step 3, with no per-caller code.

Because `_run_once` was the only caller of `_normalize_batch_stdout`, and both existed only to serve the now-deleted buffered spawn path, this step also removes them and their `PLAN_TOOL_SHELL_DEBUG` debug-print gate — carrying forward the plan's stated intent that this step "deletes all of it rather than leaving unreachable code behind." `claude_errors.BACKEND_TIMEOUT_SENTINEL` and `classify()` are explicitly **not** part of that removal (Acceptance criteria, plan-level): they survive unchanged, now fed exclusively by `backend_runner.py`'s own mirrored sentinel (step 4) instead of `_run_once`'s.

The `redaction_ready` flag exists because this step, on its own, would otherwise be the first time a batch caller's `-v`/`--debug` flags become live — before this step, `subprocess.run(capture_output=True)` never streamed anything to the terminal, so those flags were no-ops for `claude_invoke`'s callers. Once `claude_invoke` shares the runner's `_pump_stdout` closure, an operator running with `-v` would otherwise see the real, unredacted `tool_input_summary` for every batch tool use immediately — before step 7's redaction pass exists. Suppressing that one line behind an explicit flag (rather than requiring steps 6 and 7 to land together) is what the plan's ordering-constraint bullet means by "each step must be safe on its own once committed."

## Input

- **Step 2 produces `plan_tool/backend_runner.py:run_streaming_once(prompt, transport, *, run_logger=None, phase="claude_call", attempt=1, sibling_log_dir=None)`.** `transport` is a `Callable[[str], PromptTransport]`, not a resolved transport — `run`'s wrapper in `launcher.py` passes `get_active_backend().streaming_transport` (the bound method); this step's call site passes `get_active_backend().batch_transport` the same way. Passing the callable, not `backend.batch_transport(prompt)` already invoked, is what step 2's whole parameterization was for.
- **Step 3 wraps `proc.wait()` in a kill-then-reraise `except BaseException`** — any exception, `KeyboardInterrupt` included, kills and reaps the child before propagating unchanged. This step's own exception handling (see Implementation) sits entirely on top of that guarantee; it never needs to kill anything itself.
- **Step 4 adds `enforce_configured_timeout: bool = False` and `configured_timeout_s: Optional[float] = None`** (both keyword-only, both left at their exempting defaults for `run`'s untouched call sites), the closed seven-value termination-reason vocabulary (`completed`, `configured_timeout`, `silence_timeout`, `operator_interrupt`, `spawn_failure`, `backend_nonzero`, `unknown`) with a `get_last_termination_reason()` accessor, and wraps `Popen()` itself so a spawn-time failure classifies `spawn_failure` (or `operator_interrupt` for a `KeyboardInterrupt` during spawn) and re-raises rather than propagating an uncaught traceback. Step 4's own text names this step as the one that sets `enforce_configured_timeout=True` and resolves `configured_timeout_s` from `shell.py:_effective_subprocess_timeout()` — unchanged by this step, still the single source `scoped_claude_timeout` / `PLAN_TOOL_CLAUDE_TIMEOUT` feed. Step 4 also states explicitly that *this* step is where the caught `spawn_failure` / `unknown` exception gets converted into an ordinary nonzero `(rc, stdout, stderr)` outcome for `classify()` — the runner itself only makes the reason determinable, it does not build that conversion.
- **Step 5, though not a `depends_on` entry, lands before this step in execution order and already edits the exact closure this step rewrites.** Steps run in numeric id order regardless of `depends_on`, so by the time this step's code is written, `shell.py:claude_invoke`'s `_run_once_seam` closure already (a) wraps its `wait=` / `sleep=` recovery-loop seams through `claude_errors.py`'s `backend_recovery_wait` / `run_interrupted` factories, and (b) brackets its call to `_run_once(prompt)` with `shell.get_active_run_logger()`-gated `backend_spawn(...)` / `backend_termination(reason=..., duration_ms=..., ...)` calls, where `reason` comes from a small private `_classify_batch_termination_reason(rc, stderr) -> str` helper (three branches: `rc == 0` → `"completed"`, `BACKEND_TIMEOUT_SENTINEL in stderr` → `"configured_timeout"`, nonzero `rc` → `"backend_nonzero"`; else `"unknown"`). This step must **preserve and adapt** that bracket — not rebuild it — since it wraps the call this step is replacing, not the runner's own (deferred to step 7) observer wiring. `shell.get_active_run_logger()` is a *different* ContextVar from the runner's own `run_logger` parameter (step 5's Architecture note); this step's call to `run_streaming_once` still passes no `run_logger` at all, so nothing here creates the runner-internal event trail — only the caller-side bracket step 5 already built keeps firing, conditioned on a bound writer exactly as before.
- **`plan_tool/backend.py`'s `CliBackend.batch_transport` / `streaming_transport`, `PromptTransport`, `ClaudeRunStats`.** `ClaudeRunStats.final_text` is empty (`""`) by default and set only from a backend's terminal envelope (claude's `{"type": "result"}`, codex's `turn.completed`); `PromptTransport.prompt_bytes` is unchanged and still the source for the prompt-budget backstop and `ClaudeCallEnd.prompt_bytes`.
- **What the runner's stdout pump already does with parsed text**, confirmed by reading `_run_streaming_once`'s current body (moves to `backend_runner.py` unchanged in step 2): every parsed `text_chunk` — both intermediate `assistant` text blocks *and* the terminal `result` envelope's `final_text` — is appended to the same `stdout_buffer` unconditionally. For a response that streams incremental assistant text before its terminal envelope, `stdout_buffer` therefore contains that text **twice**: once as the streamed chunk, once as `final_text`. This is exactly the duplication step 1's pinned collapse rule exists to prevent, and it is the fact this step's collapse logic (see Implementation) has to work around.

## Files (creates vs edits)

No new production files. Both production files are steps 2–5's existing files; this step edits them and their direct test siblings.

**Existing files (edits only):**

- `plan_tool/shell.py` — delete `_run_once` and `_normalize_batch_stdout` in full, including the `PLAN_TOOL_SHELL_DEBUG` debug-print block; rewrite `claude_invoke`'s `_run_once_seam` closure to call `backend_runner.run_streaming_once` instead (see Implementation); add the module import for `plan_tool.backend_runner`.
- `plan_tool/backend_runner.py` — add `redaction_ready: bool = True` as a new keyword-only parameter on `run_streaming_once`; use it inside the existing `-v` (`_CONSOLE_VERBOSITY_VERBOSE`) tool-use print branch to choose between the real `tool_input_summary` and the literal `[OMITTED]`. Also gate `_pump_stderr`'s live line-by-line passthrough to `sys.stderr` behind verbosity (`-v`/`--debug` stream live; default verbosity stays silent) — see "stderr streaming is now gated" below. This is a *new*, broader threshold (`verbosity >= _CONSOLE_VERBOSITY_VERBOSE`), not a reuse of `_pump_stdout`'s existing raw-NDJSON gate, which fires only at `--debug` (`verbosity >= _CONSOLE_VERBOSITY_DEBUG`) and would leave stderr silent at plain `-v` if copied literally — that narrower condition does not satisfy this step's own acceptance criteria or `test_stderr_streams_live_at_verbose`. The pump still accumulates every line into the returned `stderr_buffer` at every verbosity; only the live terminal write is gated, so `claude_invoke`'s existing curated `warn()` tail on failure, and every classification path reading returned stderr, see exactly what they see today.
- `tests/test_shell.py` — the majority of this step's test work: port the existing `subprocess.run`-based fixtures (`_fake_run_factory`, `_multi_run_factory`) onto Popen-based fakes for every test that drives `claude_invoke` through a spawn, add the new cases under Tests, delete the tests that only made sense against `_run_once`'s buffered shape (see Tests).
- `tests/subprocess_doubles.py` — the shared `_FakePipe` / `_FakeProc` / `_make_popen_factory` trio step 2 relocates here from `tests/test_launcher.py` is this step's primary test dependency; add a small helper (or a thin wrapper over the existing factory) that builds claude-shaped `stream-json` NDJSON lines from a plain response string, so `test_shell.py`'s many single-response fixtures don't each hand-write a JSON envelope.
- `TESTING.md` — update the invoker-neutralization table's `claude_invoke` row (and any prose describing `_run_once`/`subprocess.run` as the batch spawn mechanism) to point at `plan_tool.backend_runner.subprocess.Popen` as the seam a test now patches, mirroring the pointer step 2 already added for `shell_invoker`.

**Justified addition — not in the plan's declared `files:` for this step:**

- `tests/test_backend_runner.py` — this step adds a new parameter (`redaction_ready`) to `run_streaming_once` and the verbosity gate on `_pump_stderr`, both in a function whose own dedicated test file already exists (created by step 2). Direct-call coverage for both mechanics belongs there, alongside the ~20 existing `TestRunStreamingOnceStreamJson` cases neither change may disturb; `tests/test_shell.py` covers only that `claude_invoke` passes `redaction_ready=False`, not the runner's own print-suppression mechanics. The stderr-gate cases: `test_stderr_stays_silent_at_default_verbosity` (a fake child writing stderr lines produces no live `sys.stderr` write at default verbosity, while the returned stderr text still carries every line — the buffer half is what the sentinel bridge and failure tails depend on) and `test_stderr_streams_live_at_verbose` (the same call at `-v` writes the lines through live, pinning that the gate opens rather than suppressing unconditionally).

## Implementation

### The seam rewrite

Replace `_run_once_seam`'s body (currently `rc, stdout, stderr_text, duration_ms, prompt_bytes, stats = _run_once(prompt)`) with a call to `backend_runner.run_streaming_once`. One shape:

```python
def _run_once_seam(attempt_number: int):
    backend = get_active_backend()
    prompt_bytes = backend.batch_transport(prompt).prompt_bytes
    started = time.monotonic()
    try:
        rc, stdout_text, stderr_text, stats = backend_runner.run_streaming_once(
            prompt,
            backend.batch_transport,
            phase=phase,
            attempt=attempt_number,
            enforce_configured_timeout=True,
            configured_timeout_s=_effective_subprocess_timeout(),
            redaction_ready=False,
        )
    except KeyboardInterrupt:
        raise
    except BaseException as exc:
        rc, stdout_text, stderr_text, stats = <synthetic terminal outcome>, None
    duration_ms = int((time.monotonic() - started) * 1000)
    response_text = stats.final_text if stats and stats.final_text else stdout_text
    ...  # step 5's backend_spawn/backend_termination bracket, then _emit_call_end,
         # both fed from this same (rc, response_text, stderr_text, duration_ms, stats)
    return rc, response_text, stderr_text
```

This is a shape to adapt, not a script — the exact split between this closure and any small private helper is the implementer's call. What is **not** free to vary:

- **`transport` is `backend.batch_transport` (the bound method), never `backend.streaming_transport`.** `.plan-tool/backends.json`'s `extra_batch_argv` / `extra_streaming_argv` can differ per project (`docs/design-plans/BACKEND_SELECTION.md`); passing the wrong selector would silently send every batch caller the streaming extra args on any project using that override, even though claude's own shipped `_claude_batch_argv` / `_claude_streaming_argv` happen to be identical today.
- **`prompt_bytes` still comes from `backend.batch_transport(prompt).prompt_bytes`, resolved once per attempt** (mirroring what `_run_once` used to compute) — `_maybe_warn_shell_prompt_budget`'s own separate resolution (once per `claude_invoke` call, for the backstop advisory) is unrelated and stays as is.
- **`_emit_call_end`'s `stdout_bytes` argument is the byte length of the *collapsed* `response_text`, not the raw `stdout_text` buffer** — matching today's behavior exactly, where `_run_once_seam` already computes `len(stdout.encode("utf-8"))` on `_normalize_batch_stdout`'s already-collapsed result, never on the pre-collapse buffer.
- **`duration_ms` is timed by this closure**, via `time.monotonic()` bracketing the `run_streaming_once` call — the function's own return tuple carries no duration field (unlike `_run_once`'s, which computed and returned one).

### The collapse rule

`run_streaming_once` returns `(rc, stdout_text, stderr_text, stats)` where `stdout_text` is `"".join(stdout_buffer)` and `stdout_buffer` accumulates both intermediate assistant-text chunks *and* the terminal envelope's `final_text` unconditionally (see Input) — reusing `stdout_text` as-is would duplicate a multi-chunk response's text exactly the way step 1's characterization suite pins as *not* today's behavior. `stats.final_text` (from `ClaudeRunStats`) carries only the terminal envelope's text and is empty when no terminal envelope arrived. The collapse rule step 1 pinned — `final_text` alone when the terminal line supplies one, else the joined buffer — reproduces exactly with:

```python
response_text = stats.final_text if stats and stats.final_text else stdout_text
```

This is the same `final_text if final_text else "".join(chunks)` logic `_normalize_batch_stdout` used, just read off the runner's already-parsed state instead of re-parsing a joined string. It also generalizes to a plain-`stdout` backend (`batch_output != "json"`) with no special-casing: such a backend's lines never parse as claude/codex JSON, so every line falls into the pump's non-JSON fallback (`stdout_buffer.append(line)` verbatim, no `text_chunks`), `stats` stays the `ClaudeRunStats()` default (`final_text == ""`), and `response_text` resolves to the raw joined buffer — the exact non-JSON branch `_normalize_batch_stdout` had (`return stdout, None`).

### Exception handling

`run_streaming_once` can now raise instead of returning, per steps 3–4's guarantees: a `KeyboardInterrupt` (classified `operator_interrupt`) or any other exception (`spawn_failure` at `Popen()`, `unknown` at `proc.wait()`) is re-raised **after** the child is already killed and reaped — this step never needs its own kill logic.

- **`KeyboardInterrupt` propagates unchanged out of `_run_once_seam`, out of `run_with_rate_limit_recovery` (which has no exception handling around its `run_once(attempt)` call — step 3's Input), out of `claude_invoke`.** This is not new: today, a `KeyboardInterrupt` during `_run_once`'s `subprocess.run` already propagates the same way, because `subprocess.run` itself kills-then-reraises on any exception. `claude_invoke`'s docstring already scopes its "no exceptions raised" guarantee to *normal subprocess outcomes* — an interrupt was never one of those, on either the old or new path. Callers that need a clean, non-traceback exit on Ctrl-C get one at the CLI layer in step 8, not here.
- **Any other exception must be caught and converted into a synthetic `(rc, stdout, stderr)` outcome — never left to propagate.** Per step 4's own stated design, this is this step's job specifically: the runner only makes `spawn_failure` / `unknown` *determinable*; turning the re-raised exception into an outcome `classify()` can bucket is this step's wiring. One way: `rc` any nonzero value (recommend a small named constant distinct from `EXEC_NOT_FOUND_EXIT`, e.g. `1`), `stdout=""`, `stderr=f"{type(exc).__name__}: {exc}"`. No `BACKEND_TIMEOUT_SENTINEL` marker is added — `classify()`'s existing fallback already buckets a plain nonzero `rc` as `UNKNOWN_NONZERO` (terminal, no retry), matching the plan's stated design that `spawn_failure` and `unknown` "surface once rather than [being] silently retried as TRANSIENT would be." `stats` is `None` on this path.
- **Match the runner's own two-arm classification, not a narrower one.** Steps 3–4's `except BaseException` blocks (both at `Popen()` and at `proc.wait()`) treat *only* `KeyboardInterrupt` specially; every other `BaseException` subclass (including `SystemExit`, `GeneratorExit`) is caught and classified `spawn_failure` / `unknown`. This step's own `except` should mirror that same two-way split — `except KeyboardInterrupt: raise` / `except BaseException as exc: <convert>` — for consistency with the reason the exception carries, not narrow to `except Exception`.
- **`_run_once_seam`'s name no longer describes what it does** (it doesn't call `_run_once` anymore). Renaming it is not required for correctness — nothing outside this closure references the name — but is worth considering while the body is already being rewritten.

### `backend_spawn` / `backend_termination` — adapt, don't rebuild

Step 5's existing bracket around this call — `backend_spawn(...)` before, `backend_termination(reason=_classify_batch_termination_reason(rc, stderr), duration_ms=duration_ms, ...)` after, both gated on `shell.get_active_run_logger() is not None` — needs to keep working against the new call's `(rc, stdout, stderr, duration_ms)` shape rather than `_run_once`'s. One thing worth flagging rather than silently deciding: `_classify_batch_termination_reason`'s existing four buckets (`completed` / `configured_timeout` / `backend_nonzero` / `unknown`) were built against `_run_once`'s outcomes, before `spawn_failure` and `operator_interrupt` existed as *reachable* batch-lane outcomes. Left unchanged, the exception-conversion path above (synthetic nonzero `rc`, no sentinel) falls into `_classify_batch_termination_reason`'s `"backend_nonzero"` branch even when the underlying cause was a `spawn_failure` or an `unknown` `proc.wait()` exception — a real precision loss the classifier's author couldn't have anticipated. `backend_runner.get_last_termination_reason()` (step 4) already has the precise answer available immediately after the call. Whether to thread it in now — feeding the exception-conversion branch specifically, or replacing `_classify_batch_termination_reason` outright now that the runner is reachable — is a design call this step's own scope doesn't settle; the plan's step 6 intent text never mentions this classifier. Leaving it as the coarser `"backend_nonzero"` for now is not a regression (nothing today distinguishes it either), so this is a recommendation, not a blocking requirement.

### `redaction_ready`

Add `redaction_ready: bool = True` as a new keyword-only parameter to `run_streaming_once`. `launcher.py`'s thin wrapper (unedited by this step — not in this step's `files:`) forwards a fixed set of keyword arguments established in step 2 and does not know this name exists, so `run`'s call sites inherit the default with zero edits, exactly the pattern step 4 already established for `enforce_configured_timeout`. Inside the `_pump_stdout` closure's existing `_CONSOLE_VERBOSITY_VERBOSE` branch:

```python
if verbosity == _CONSOLE_VERBOSITY_VERBOSE:
    for ev in parsed.events:
        if ev.get("kind") == "tool_use":
            name = ev.get("tool_name") or "?"
            summary = ev.get("tool_input_summary") or "" if redaction_ready else "[OMITTED]"
            ...
```

is one shape; the exact conditional placement is free, but the outcome is fixed: with `redaction_ready=False`, the printed line never contains the real `tool_input_summary` value, only the literal string `[OMITTED]`. This flag gates **only** this one console print — it does nothing to `claude_stream_event`'s own JSONL emission (already gated on `run_logger is not None`, which stays `None` for every batch call this step makes) and nothing to `--debug`'s raw NDJSON passthrough (a separate code path that never calls `_summarize_tool_input` at all, per Architecture's Risk entry — unaffected either way).

### stderr streaming is now gated by verbosity — a decided behavior change for both lanes

At HEAD, `_pump_stderr` writes every line to `sys.stderr` **unconditionally**, with no verbosity gate — unlike `_pump_stdout`'s raw-NDJSON passthrough, which is gated behind `--debug`. Moving batch calls onto the runner unchanged would have made every batch call's raw stderr stream live at every verbosity level (before this step, `_run_once`'s `subprocess.run(capture_output=True)` captured it silently, and `claude_invoke` only surfaced a curated tail via `warn()` on failure) — raw backend stderr can carry paths or prompt fragments that sit outside `_summarize_tool_input`'s redaction rule, the same leakage surface step 10 closes for structured summaries. **Decided (Architecture's allowed-changes item 7): this step gates `_pump_stderr`'s live write behind verbosity instead** — `-v`/`--debug` stream stderr live, default verbosity stays silent. This is a *new* threshold, `verbosity >= _CONSOLE_VERBOSITY_VERBOSE`, not a reuse of `_pump_stdout`'s existing gate: that one fires only at `--debug` (`verbosity >= _CONSOLE_VERBOSITY_DEBUG`) and would leave stderr silent at plain `-v` if copied as-is, contradicting this step's own acceptance criteria and `test_stderr_streams_live_at_verbose`. This narrows `run`'s own long-standing behavior too (its calls streamed raw stderr live at default verbosity before this plan; after this step they don't), which is why the change is named in the plan's one allowed-behavior-changes list rather than decided locally here. No return value changes: `_pump_stderr` still accumulates every line into the returned `stderr_buffer` at every verbosity, so `claude_invoke`'s failure-tail `warn()`, the `BACKEND_TIMEOUT_SENTINEL` bridge, and every classification path see today's exact bytes.

### The deletions

Remove `_run_once` and `_normalize_batch_stdout` in full, along with the `debug = bool(os.environ.get("PLAN_TOOL_SHELL_DEBUG"))` block and both of its `print(...)` call sites (both live inside `_run_once`, so they go with it). `claude_errors.BACKEND_TIMEOUT_SENTINEL` and `classify()` are untouched — they are fed exclusively by `backend_runner.py`'s own mirrored sentinel now (step 4). `plan_tool/claude_errors.py`'s module docstring and the comment above `BACKEND_TIMEOUT_SENTINEL` currently read "alongside `shell._run_once` (which survives until step 6 deletes it)" (step 4's own wording, anticipating this exact edit) — that phrase is now stale prose citing a deleted function and needs updating to name `backend_runner.py`'s monitor-thread kill path as the sole current producer. `plan_tool/claude_errors.py` is not in this step's declared `files:`; treat this as the same kind of small, directly-motivated addition as `tests/test_backend_runner.py` above (see Files) rather than leaving a dangling reference to a function that no longer exists.

`plan_tool/backend.py` carries six further docstring/comment citations of `shell._run_once` (its module docstring, `CliBackend.batch_output`'s docstring, `_claude_batch_argv`'s docstring, and three more), and `tests/test_backend.py` / `tests/test_distill.py` / `tests/test_create.py` each carry one comment referencing `shell._run_once` or `_normalize_batch_stdout` to explain a fixture's shape. None of these files are in this step's declared `files:`, and `backend.py` in particular is a heavily-shared module this step has no other reason to touch — routed to Deferred rather than pulled into this step's footprint.

## Tests

### Tests for this step

`tests/test_backend_runner.py` (new file for this step — see Files):

- `test_run_streaming_once_default_redaction_ready_prints_real_summary` — a `-v`-verbosity call with `redaction_ready` left at its default; the printed tool-use line contains the real `tool_input_summary`, unchanged from before this step.
- `test_run_streaming_once_redaction_ready_false_prints_omitted` — the same call with `redaction_ready=False`; the printed line contains the literal `[OMITTED]`, never the real summary text.
- `test_redaction_ready_does_not_affect_claude_stream_event_or_debug_passthrough` — with a bound `run_logger` and `redaction_ready=False`, the emitted `claude_stream_event`'s `tool_input_summary` field is unaffected (this flag gates the console print only); at `--debug` verbosity, the raw NDJSON passthrough is also unaffected.
- Every existing `TestRunStreamingOnceStreamJson` case (from steps 2–4) stays green with no changes to their bodies.

`tests/test_shell.py` (the bulk of this step's work — porting the existing roster onto Popen fakes, via `tests/subprocess_doubles.py`'s relocated `_make_popen_factory`):

- `test_claude_invoke_spawns_via_backend_runner_popen` — asserts `shell.subprocess` is no longer imported/used for the batch spawn and that patching `backend_runner.subprocess.Popen` is what intercepts a `claude_invoke` call (the direct proof `_run_once` is gone, not just a name check).
- `test_claude_invoke_passes_batch_transport_not_streaming_transport` — a fake backend whose `batch_transport` and `streaming_transport` return *different* argv; asserts the spawned argv matches `batch_transport`'s.
- Migrated argv / PATH-guard / stdin-transport / spawn-cwd / backend-routing cases (the existing `test_invoke_passes_stream_json_argv_to_subprocess`, `test_run_once_spawns_in_active_spawn_cwd`, `test_run_once_routes_through_active_backend_argv`, `test_run_once_supports_stdin_prompt_transport`, `test_path_guard_uses_active_backend_binary`) — same assertions, rebuilt against Popen-shaped fakes instead of `subprocess.run`-shaped ones.
- `test_claude_invoke_collapses_to_final_text_over_duplicated_stream_chunks` — a fake stdout stream carrying both an intermediate `assistant` text block and a terminal `result` envelope's `final_text`; asserts the returned stdout is `final_text` alone, not the two concatenated — step 1's pinned collapse rule, now proven end to end through `claude_invoke`.
- `test_claude_invoke_falls_back_to_joined_buffer_for_plain_stdout_backend` — a backend with `batch_output="stdout"`; asserts the returned stdout equals the raw joined lines, matching `_normalize_batch_stdout`'s old non-JSON branch.
- `test_claude_invoke_enforces_configured_timeout` — `scoped_claude_timeout` (or `PLAN_TOOL_CLAUDE_TIMEOUT`) set to a short value with a fake whose `wait()` never returns; the call is killed at the configured elapsed time and `classify()` reports `ClaudeFailureKind.TIMEOUT` — the direct replacement for the migrated `test_claude_invoke_timeout_is_terminal_no_retry`, now driven through the runner's monitor thread instead of `subprocess.run(timeout=...)`.
- `test_claude_invoke_no_configured_timeout_by_default` — the same long-running fake with no scope set; not killed by the elapsed-time check (only the far longer silence default could ever fire).
- `test_claude_invoke_silence_kill_reaps_a_wedged_batch_child` — a fake compressed past the (monkeypatched) silence threshold with no elapsed-time timeout set; the child is terminated, `classify()` reports `TIMEOUT`, and the call returns rather than hanging — proves the plan's headline guarantee for a caller with `enforce_configured_timeout=True` but no configured value.
- `test_claude_invoke_keyboard_interrupt_propagates_with_child_killed` — a fake whose `wait()` raises `KeyboardInterrupt`; asserts `claude_invoke` itself raises (not converted to a return value), the exception type is unchanged, and the fake's kill hook was called.
- `test_claude_invoke_spawn_failure_returns_unknown_nonzero_not_raised` — patches `backend_runner.subprocess.Popen` to raise `OSError`; asserts `claude_invoke` returns a normal `(rc, stdout)` pair (does **not** raise), `rc != 0`, and — driven through the full recovery loop — `classify()` buckets it `UNKNOWN_NONZERO` with no retry attempted.
- `test_claude_invoke_redaction_ready_is_false_for_batch_calls` — at `-v` verbosity, a fake `tool_use` event; asserts stderr shows `[OMITTED]`, never the real summary — the integration-level proof that `claude_invoke`'s own call site passes `redaction_ready=False`.
- `test_claude_invoke_backend_spawn_and_termination_still_fire_via_new_call` (extends step 5's fixture) — with a bound `run_logger`, `backend_spawn` / `backend_termination` still fire once per attempt through the rewritten seam, proving step 5's bracket survived the swap.
- `test_shell_run_once_and_normalize_batch_stdout_no_longer_exist` — `assert not hasattr(shell, "_run_once")` and `assert not hasattr(shell, "_normalize_batch_stdout")`.
- `test_plan_tool_shell_debug_env_var_has_no_effect` (or a source-scan asserting the string is absent from `shell.py`) — the removed debug gate leaves no residue.
- Existing rate-limit / transient / switch / interrupt-menu / concurrency tests (`test_claude_invoke_waits_then_retries_on_rate_limit`, `test_claude_invoke_retries_transient_with_exponential_backoff`, `test_claude_invoke_rate_limit_menu_switches_backend_and_retries`, `test_concurrent_rate_limit_prompts_are_serialized`, `test_claude_invoke_parallel_switches_do_not_leak_between_threads`, and the rest of that block) — ported onto Popen-shaped fakes with unchanged assertions on retry counts, backoff timing, and thread-isolation; these are the tests proving the recovery loop itself is unaffected by the spawn-mechanism swap.
- `test_effective_subprocess_timeout_precedence`, `test_phase_timeout_resolver_precedence`, `test_phase_timeout_resolver_disabled_value_masks_legacy` — pure-function tests of `_effective_subprocess_timeout` / `resolve_claude_timeout`; unchanged, since neither function's own logic moves.

`tests/subprocess_doubles.py`:

- `test_ndjson_response_builder_produces_a_parseable_result_envelope` (or equivalent) — a direct test of the new NDJSON-building helper this step adds, asserting the built lines round-trip through `plan_tool.backend._claude_parse_stream_line` into the expected `final_text` / stats.

**Green-before-done gate:** every test above, plus the full existing `tests/test_shell.py` roster (ported, not dropped) and `tests/test_backend_runner.py`'s existing steps 2–4 roster, must be green before this step is considered finished, along with `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- `plan_tool/shell.py` no longer defines `_run_once` or `_normalize_batch_stdout`; `PLAN_TOOL_SHELL_DEBUG` does not appear anywhere in `shell.py`.
- `claude_invoke`'s `(rc, stdout)` contract is unchanged for every existing caller: a successful call returns `(0, response_text)`; a failed call returns `(rc, response_text)` with `classify()` bucketing it identically to before this step for every failure kind step 1 pinned.
- `claude_invoke` spawns exclusively through `backend_runner.run_streaming_once`, passing `get_active_backend().batch_transport` as `transport`, `enforce_configured_timeout=True`, `configured_timeout_s=_effective_subprocess_timeout()`, and `redaction_ready=False`.
- A response with both an intermediate assistant text chunk and a terminal envelope's `final_text` returns `final_text` alone from `claude_invoke`, never the two concatenated.
- A `-v`-verbosity batch call never prints the real `tool_input_summary`; it prints `[OMITTED]`. A `-v`-verbosity `run` call is unaffected (still prints the real summary) with zero edits to `plan_tool/launcher.py`.
- Neither lane writes a child's raw stderr live to the terminal at default verbosity; both write it live at `-v`/`--debug`. Every verbosity level still returns the full joined stderr text from `run_streaming_once`, unchanged from today.
- A batch call configured with `PLAN_TOOL_CLAUDE_TIMEOUT` / `scoped_claude_timeout` is killed at the configured elapsed time, classified `ClaudeFailureKind.TIMEOUT`, with no same-budget retry; a batch call with no configured timeout is never killed by the elapsed-time check.
- A batch child silent past the shared silence threshold is terminated and the call returns (does not hang), classified `TIMEOUT`.
- A `KeyboardInterrupt` raised during a batch call's `proc.wait()` (or `Popen()`) propagates out of `claude_invoke` unchanged, with the child already killed and reaped.
- A non-interrupt exception from the runner (`spawn_failure` or `unknown`) does not propagate out of `claude_invoke`; the call returns a normal `(rc, stdout)` pair with `rc != 0`, classified `UNKNOWN_NONZERO`, no retry attempted.
- `plan_tool/backend_runner.py:run_streaming_once` accepts `redaction_ready: bool = True`; `run`'s call sites (through `launcher.py`'s unedited wrapper) are unaffected — `git diff --stat` against this step's base commit shows no change to `plan_tool/launcher.py`.
- Step 5's `backend_spawn` / `backend_termination` / `backend_recovery_wait` / `run_interrupted` emission from `claude_invoke`'s recovery-loop seams keeps firing exactly as before this step, now sourced from `run_streaming_once`'s outcome.
- None of `claude_stream_event`, `claude_call_progress`, or `claude_call_stall_suspected` is written for any batch call at this step — `claude_invoke` still passes no `run_logger` to the runner.
- `uv run pytest tests/test_shell.py tests/test_backend_runner.py tests/test_launcher.py -q` passes; `uv run pytest tests/ -q -n auto` passes.

## References

- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — confirms `batch_transport`'s `-p --output-format stream-json --verbose --permission-mode acceptEdits` argv is the same invocation shape this step now spawns via `Popen` instead of `subprocess.run`.
- [subprocess — Subprocess management (Python 3.13)](https://docs.python.org/3/library/subprocess.html) — `Popen`/`terminate`/`kill`/`wait` semantics this step now relies on indirectly through the shared runner, and the `TimeoutExpired` behavior this step's deletion of `_run_once` removes from `shell.py` entirely.
- [signal — Set handlers for asynchronous events (Python)](https://docs.python.org/3/library/signal.html) — SIGINT → `KeyboardInterrupt` on the main thread, the basis for this step's requirement that an interrupt propagate out of `claude_invoke` unchanged rather than being converted into a return value.

## Applicable guardrails

- **Plan's Architecture, "allowed behavior changes" item 1** — licenses the universal silence kill for every `claude_invoke` caller from the moment this step lands; this step must apply it unconditionally, not behind a per-caller opt-in.
- **Plan's Architecture, ordering-constraint bullet** — this step must land the runner wiring and the fail-closed `redaction_ready` suppression together (both inside this one step), since the plan's own execution model commits each step individually and step 6 must be safe to land alone before step 7's redaction exists.
- **Plan's Out of scope — the default unbounded total-duration timeout is unchanged for every command, and the silence/stall thresholds stay non-configurable.** This step must not add a CLI flag or env var for either threshold; `enforce_configured_timeout=True` at `claude_invoke`'s call site is a call-contract change, not a new operator surface.
- **Plan's Testing — "never reaches... verbose terminal output" is scoped to the `-v` per-tool-use summary line and the JSONL, not `--debug`'s raw passthrough (Risks).** This step's `redaction_ready` suppression must not attempt to touch `--debug`'s output; that path is explicitly, permanently unredacted per the plan's own decided Risk entry.
- **Plan's Acceptance criteria — `claude_errors.BACKEND_TIMEOUT_SENTINEL` and its `classify()` check are not part of this step's removal.** Only `shell._run_once`'s own copy of the timeout-to-sentinel glue goes away; the constant and the classifier function must be byte-identical after this step.

## Deferred

- **`plan_tool/backend.py`'s six docstring/comment citations of `shell._run_once`**, and the one-line comments in `tests/test_backend.py`, `tests/test_distill.py`, and `tests/test_create.py` referencing `shell._run_once` / `_normalize_batch_stdout` — stale once this step deletes both symbols, but `backend.py` is a widely-shared module not in this step's declared `files:`; left for a follow-up doc sweep (either the post-run `reconcile-code` pass, or a `BACKLOG.md` entry if that pass doesn't catch prose-only staleness).
- **Runner-internal `claude_stream_event` / `claude_call_progress` / `claude_call_stall_suspected` for batch calls, and any richer runner-sourced `backend_spawn` / `backend_termination` bracket around the Popen child itself** — this step passes no `run_logger`/observer to `run_streaming_once`; step 7 is where `claude_invoke` first builds and passes one.
- **Redacting `_summarize_tool_input` itself** — this step only suppresses the `-v` print via `redaction_ready`; the actual redaction pass (pattern-matching secrets before truncation) is step 7's work, extended to codex's and cursor's own tool-call producers in step 10.
- **A clean, non-traceback Ctrl-C exit at the CLI layer** — step 8; this step only guarantees the interrupt propagates with the child already killed and reaped, not that any particular command's process exits with a particular code.
- **Refining `_classify_batch_termination_reason` to consult `backend_runner.get_last_termination_reason()`** — named above as a real precision gap the exception-conversion path introduces, left as a recommendation rather than required work, since the plan's own step 6 intent text never names this classifier.
- **Any change to `plan_tool/launcher.py`** — `run`'s call sites reach both `enforce_configured_timeout`'s and `redaction_ready`'s exempting defaults with zero edits to that file, and it is not in this step's `files:` list.
