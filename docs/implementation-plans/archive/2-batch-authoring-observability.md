> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Batch Authoring Observability
intent: 'Batch authoring calls that share `plan_tool.shell.claude_invoke` — starting
  with `roadmap`, the initial rollout target — expose the same in-progress liveness
  signal `run` already gets from `launcher._run_streaming_once`: heartbeat, stall
  suspicion, a safety-net silence kill, and a normalized termination reason, all durable
  in the JSONL run log and `in-flight.json`. `claude_invoke`''s `(rc, stdout)` contract
  and all existing roadmap/detail/audit parsing and gate logic are unchanged.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Pin today's batch-call logging and timeout behavior with tests
  intent: Gives the runner swap a regression net that states exactly what a batch
    claude call does today before anything moves, including today's `subprocess.TimeoutExpired`
    → `BACKEND_TIMEOUT_SENTINEL` → `ClaudeFailureKind.TIMEOUT` classification path
    for a configured timeout — the non-retryable contract step 4's runner-initiated
    kill must also reach, by a different mechanism, once the swap lands. Also pins
    `_normalize_batch_stdout`'s collapse rule — `final_text` alone when the terminal
    `result` line supplies one, never `final_text` joined with the streamed chunks
    that preceded it — since `_run_streaming_once`'s own `stdout_buffer` joins every
    chunk unconditionally and would duplicate that text if reused as-is for the `(rc,
    stdout)` return value once step 6 lands. Also pins today's silent-wait behavior
    on both lanes before step 5 gives it an event — `claude_invoke`'s and `shell_invoker`'s
    rate-limit `wait` and transient `sleep` seams both currently sleep with no run-log
    record on either side, `run` included, contradicting Overview's claim that `run`
    already has this solved (that claim only covers a subprocess actively running,
    not this retry-loop quiet window).
  files:
  - tests/test_shell.py
  - tests/test_roadmap.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/batch-authoring-observability/01-pin-today-batch-call-logging-timeout.md
  status: done
- id: 2
  title: Move the streaming Popen runner out of launcher.py into a shared module
  intent: Puts one subprocess supervisor where both the run lane and the batch lane
    can reach it. A pure relocation, byte-compatible with `run`'s current behavior
    — the Popen spawn, stdout pump, heartbeat thread, and silence-kill ladder move
    unchanged. The one mechanical change the move requires — `backend.streaming_transport(prompt)`
    is hardcoded inside `_run_streaming_once` today; the moved function takes the
    transport call as an explicit parameter instead, with `run`'s call site passing
    `streaming_transport` — same argv, same everything, just no longer hardcoded,
    so `claude_invoke` can later pass `batch_transport` instead without another change
    to the runner itself. `.plan-tool/backends.json`'s `extra_batch_argv` and `extra_streaming_argv`
    can differ per project (`docs/design-plans/BACKEND_SELECTION.md`), so this selector
    is a call-contract requirement, not a convenience — without it, step 6 would silently
    start sending every batch caller the streaming extra args instead of the batch
    ones on any project using that override. No other new behavior lands in this step;
    step 3 adds the one thing the move does not carry forward. The move also carries
    over `_run_streaming_once`'s existing dormant `sibling_log_dir` parameter — a
    raw, unredacted NDJSON transcript writer (`claude-stream.<attempt>.ndjson`) no
    production caller currently activates — unchanged and still unwired; a test confirms
    no caller sets it through step 6, so this scaffolding stays inert under both lanes
    rather than silently becoming reachable from batch calls. The follow-on plan (`2-batch-observability-forensics-and-view.md`)
    should know this dormant writer already exists before designing its own transcript
    capture.
  files:
  - plan_tool/launcher.py
  - tests/test_launcher.py
  - tests/subprocess_doubles.py
  - TESTING.md
  - CLAUDE.md
  - docs/ARCHITECTURE.md
  - docs/CODEX_CLI_CONTRACT.md
  creates:
  - plan_tool/backend_runner.py
  - tests/test_backend_runner.py
  complexity: high
  change_type: refactor
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the characterization tests that prove the move changed nothing observable.
  detail: docs/implementation-plans/plan-details/batch-authoring-observability/02-move-streaming-popen-runner-out.md
  status: done
- id: 3
  title: Add a kill-on-any-exception safety net around the shared runner's proc.wait()
  intent: '`_run_streaming_once` has no kill-on-any-exception net today — its `finally`
    only stops the heartbeat thread and never touches the child. This step wraps `proc.wait()`
    so any exception, including `KeyboardInterrupt`, kills the child — matching what
    `subprocess.run`''s bare except already guarantees the batch path today. Without
    this, a step 6 batch caller would newly orphan its child on Ctrl-C before step
    8''s richer interrupt classification lands; with it, `run` also gains the same
    protection for the first time — genuinely new behavior for `run`, not an upgrade
    of anything that exists. A test proves a KeyboardInterrupt during `proc.wait()`
    kills the child, for both lanes.'
  files:
  - plan_tool/backend_runner.py
  - tests/test_backend_runner.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/batch-authoring-observability/03-kill-on-any-exception-safety-net-around.md
  status: done
- id: 4
  title: Add a configured-timeout kill and a termination reason to the shared runner
  intent: Lets the batch path keep its configured-timeout contract once it moves onto
    the runner, and gives every ending one closed name. Both lanes call the same shared
    runner, so the exemption is a call-contract flag, not an inference — the runner
    takes an explicit boolean `enforce_configured_timeout` parameter, set `True` only
    at `claude_invoke`'s own call site and left `False` (the default) everywhere `run_step`/`apply_finding`
    call it — so `run`'s existing call sites stay exempt from `PLAN_TOOL_CLAUDE_TIMEOUT`/`scoped_claude_timeout`,
    exactly as they are today, guaranteed by the parameter rather than by however
    step 4 happens to be built. Also bridges a runner-initiated kill (both `configured_timeout`
    and the new `silence_timeout`) into the existing `ClaudeFailureKind`/`BACKEND_TIMEOUT_SENTINEL`
    classification `_run_once` used to reach via `subprocess.TimeoutExpired` — `claude_errors.py`'s
    `BACKEND_TIMEOUT_SENTINEL` constant and its check inside `classify()` are not
    `_run_once`'s to delete; that module is the shared bridge both lanes' classification
    already goes through (`build_classification_from_outcome` for `claude_invoke`,
    `build_streaming_classification_from_outcome` for `run`), so it survives unchanged.
    A monitor-thread kill calls `proc.terminate()`/`proc.kill()` directly and never
    raises `TimeoutExpired`, so without an explicit bridge neither kill reaches the
    non-retryable classification the Testing section requires — the runner's kill
    path writes the same synthetic `BACKEND_TIMEOUT_SENTINEL`-bearing stderr string
    `_run_once` writes today (`shell.py`'s `TimeoutExpired` handler), feeding `classify()`
    unchanged rather than replacing it with a different signal. Only `shell._run_once`
    itself, and its own copy of that glue, go away with the function (see Acceptance
    criteria, which scopes the removal to `shell._run_once`/`_normalize_batch_stdout`,
    not to `claude_errors.BACKEND_TIMEOUT_SENTINEL`). Also builds the per-caller silence-threshold
    override hook (Risks) — a developer-set, code-level override mirroring `scoped_claude_timeout`'s
    existing pattern, sitting beside this step's other monitor-thread work regardless
    of whether step 1's characterization surfaces an immediate caller for it. Also
    wraps the runner's `Popen()` call itself, not only the monitor thread's kills
    — a spawn-time exception (the binary removed between the `shutil.which` check
    and `Popen`, a permissions error, a resource limit) raises straight out today
    with `proc.wait()` never starting, so step 3's exception net can't reach it. This
    step classifies that failure as the closed enum's `spawn_failure` value — the
    one termination reason no earlier step produces — with a test proving it, since
    nothing exercises this path today. Both `spawn_failure` and step 3's `unknown`
    (a non-`KeyboardInterrupt` exception from `proc.wait()`, e.g. a stray `OSError`)
    reach the shared rate-limit/transient retry loop as `ClaudeFailureKind.UNKNOWN_NONZERO`
    — the same terminal, no-retry bucket an unclassified nonzero exit already uses
    today — rather than `TRANSIENT`, since neither is safe to assume recoverable (a
    missing binary or permissions error will not resolve itself on retry, and retrying
    blind against a genuinely broken environment risks a hot loop); an operator sees
    the failure surfaced once, not silently retried. This needs no new stderr-sentinel
    bridge the way `configured_timeout`/ `silence_timeout` do — the runner returns
    a plain nonzero `rc` with no `BACKEND_TIMEOUT_SENTINEL` marker, which `classify()`
    already buckets as `UNKNOWN_NONZERO` unchanged.
  files:
  - plan_tool/backend_runner.py
  - plan_tool/claude_errors.py
  - tests/test_backend_runner.py
  - tests/test_claude_errors.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/batch-authoring-observability/04-configured-timeout-kill-termination.md
  status: done
- id: 5
  title: Add the backend_spawn, backend_termination, run_interrupted, and backend_recovery_wait
    run-log events
  intent: Gives the run log somewhere to record that a child started, how it ended,
    that an operator stopped it, and — the gap found on `roadmap` stage 4 (plan-derivation)
    but true of every `claude_invoke` caller, and of `run`/`apply_finding` too via
    `shell_invoker`, contradicting Overview's claim that `run` already has this solved
    (that claim only covers a subprocess actively running, not this retry-loop quiet
    window) — that the shared rate-limit/transient retry loop (`rate_limit_loop.run_with_rate_limit_recovery`)
    is intentionally sleeping between attempts, not hung. `backend_recovery_wait`
    (reason, delay_ms, next_attempt, backend) covers the quiet window between one
    attempt's `backend_termination`/`claude_call_end` and the next attempt's `backend_spawn`,
    which today has no event at all on either lane — indistinguishable from a genuine
    hang from the JSONL alone. `next_attempt` is the upcoming attempt's ordinal number,
    matching the `attempt` field the other call events already carry, not a timestamp
    — `delay_ms` already carries the duration. The recovery loop has two separate
    sleep seams, not one — `wait(target)` on the RATE_LIMIT path, and a distinct `sleep(delay)`
    callable the TRANSIENT path calls directly, bypassing `wait` entirely — and `reason`
    already covers both values (`rate_limit` or `transient`), so both seams need wrapping,
    or the event only ever fires for rate-limit waits and a transient backoff stays
    exactly the silent window this event exists to close. `rate_limit_loop.run_with_rate_limit_recovery`
    (the actual sleep loop) never emits it itself — `rate_limit_loop.py` is a stdlib-only
    leaf with no first-party imports (repo-wide cycle-free import rule) and cannot
    hold a `RunLogWriter`/observer reference. Both `claude_invoke` and `shell_invoker`
    already build the `wait`/`sleep` seams they hand to that loop; each wraps both
    of its own seams to emit `backend_recovery_wait` before sleeping, keeping the
    leaf untouched — the general rule for any future event covering behavior inside
    that loop is that the seam-wrapping caller emits, never the leaf. `shell_invoker`
    wraps its seams unconditionally, same as `claude_invoke`, but only produces a
    visible event when a sink is bound at call time — today that means `run_step`'s
    calls specifically, via its ContextVar-set `run_logger`, matching the `run_step`-only
    / `apply_finding`-excluded scope step 8 already sets for the sibling events, with
    no new caller-identifying plumbing needed. Both wrapped seams also give a Ctrl-C
    landing during the wait its own handling — the only interrupt path this plan builds
    that isn't inside the shared runner's `proc.wait()` (steps 3/4/7/8), since there
    is no child process alive during a recovery wait to kill or reap. A `KeyboardInterrupt`
    raised out of `wait`/`sleep` is caught here, classified `operator_interrupt` (step
    4's vocabulary), reported via `run_interrupted` with `source` distinguishing this
    recovery-wait case from a `proc.wait()` interrupt, and re-raised so the caller's
    own `KeyboardInterrupt` propagation is otherwise unchanged — closing the one Ctrl-C
    window the runner's own kill-on-any-exception net cannot reach. `claude_invoke`
    needs a real `RunLogWriter` reference to write either of these two events, not
    the narrow `Callable[[ClaudeCallEnd], None]` closure `shell.get_active_sink()`
    already returns (Architecture's Observer wiring bullet) — this step is where that
    writer-carrying ContextVar is actually created in `shell.py`, set alongside the
    existing `MetaSink` wherever `bind_shell_sink`/`install_call_end_sink` run, and
    `claude_invoke` reads it directly for these two events, mirroring how `shell_invoker`
    already reads the real writer off `launcher._run_logger_var` today — no observer-protocol
    layer needed for this narrow purpose. Step 7 reuses this same ContextVar when
    it builds the fuller multi-callback observer; it does not create a second one.
    This step also gives `run_end.termination_reason` (Architecture) an actual owner
    — `RunLogWriter.run_end()` takes only `outcome`/`rc`/`error` at HEAD and is called
    from 23 production sites this plan does not touch, so no per-call-site plumbing
    is added. Instead, `RunLogWriter` itself tracks the most recent termination reason
    internally, updated whenever its own `backend_termination`/`run_interrupted`-writing
    methods run (applying the interrupt-wins precedence Architecture states), and
    `run_end()` reads that tracked value by default when its own explicit argument
    is absent — every existing call site keeps working unchanged. Populates for every
    caller that actually reaches a `backend_termination`/`run_interrupted` event —
    every `claude_invoke` caller with a bound `RunLogWriter` once step 7's observer
    wiring lands (`roadmap`, `create`'s and `review`'s own call sites, and the rest;
    Architecture's allowed-changes item 4 and "runner extraction is global" bullet
    already establish this scope, unchanged here), plus `run` via step 8's adapter.
    `annotate.py`, `jira.py`, and `create.py`'s slug-generation call never open a
    `RunLogWriter` at all (Problem statement) and so never reach these events either
    — `termination_reason` stays unset only for those three, not for every non-`roadmap`/`run`
    caller.
  files:
  - plan_tool/run_log.py
  - plan_tool/data_contract.py
  - plan_tool/shell.py
  - plan_tool/launcher.py
  - plan_tool/claude_errors.py
  - DATA_CONTRACT.md
  - tests/test_run_log.py
  - tests/test_data_contract.py
  - tests/test_shell.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  depends_on_notes:
    4: Owns the closed termination-reason vocabulary; run_log records the string the
      way it already records roadmap's lifecycle states.
  detail: docs/implementation-plans/plan-details/batch-authoring-observability/05-backend-spawn-backend-termination-run.md
  status: done
- id: 6
  title: Run batch claude calls through the shared runner instead of subprocess.run
  intent: Stops a wedged batch child from pinning plan-tool indefinitely for all seven
    claude_invoke callers — the silence-kill protection is unconditional, independent
    of whether a caller has an active run-log sink (see Architecture). The JSONL event
    trail step 7 adds is a narrower claim that depends on a sink being active. `claude_invoke`'s
    call site passes `batch_transport` through step 2's transport selector, not `run`'s
    `streaming_transport` default. And `claude_invoke`'s returned `(rc, stdout)` applies
    step 1's pinned collapse rule — `final_text` alone when available, else the runner's
    own `stdout_buffer` (which already accumulates both parsed text chunks and, for
    a plain-`stdout` custom backend whose lines never parse as JSON, the raw lines
    themselves — the same fallback shape `_normalize_batch_stdout` has today, so the
    collapse rule generalizes to that case without special-casing it). `shell._run_once`
    has exactly one caller in the codebase — `claude_invoke`'s `_run_once_seam` —
    so once this step lands it becomes dead code, along with two things that exist
    only to serve it — `_normalize_batch_stdout` (its only caller is `_run_once`;
    step 6 sources `final_text`/the buffer directly from the runner's already-parsed
    state instead of re-parsing a raw joined string, so nothing calls it either),
    the `BACKEND_TIMEOUT_SENTINEL` synthetic-timeout return, and the `PLAN_TOOL_SHELL_DEBUG`
    env var gating its debug prints. This step deletes all of it rather than leaving
    unreachable code behind. Fail-closed by design, not by landing order — `claude_invoke`
    passes the runner an explicit boolean, `redaction_ready=False` at this step (`True`
    for `run`'s existing call sites — unchanged at this step, since this flag only
    gates whether the runner *prints* the `-v` line at all, not what `_summarize_tool_input`
    puts inside it), and the runner's `-v` tool-input-summary print suppresses the
    line with the literal `[OMITTED]` (Architecture, step 7) whenever the flag is
    `False`, rather than printing the field verbatim. This is what makes step 6 safe
    to land and commit on its own — no window where a batch caller's `-v` flag prints
    an unredacted summary, regardless of whether step 7 has landed yet. Step 7 flips
    the flag to `True` once its redaction is in place, replacing suppression with
    the real, redacted summary. `run` never carries a suppressed summary — but once
    step 7 redacts inside `_summarize_tool_input`, `run`'s own `-v` line and JSONL
    trail start showing that same redacted content too, since `claude_invoke` and
    `run`'s streaming path parse tool input through the identical shared function
    (see Architecture's allowed-changes item 6). `redaction_ready` only gates the
    console `-v` print — it does nothing for the JSONL. `_run_streaming_once`'s stdout
    pump writes a `claude_stream_event` for every parsed event, including `tool_input_summary`,
    whenever a `run_logger` is bound, with no redaction check of its own. Step 5 already
    gives `claude_invoke` a real writer to bind, so this step explicitly does not
    bind it to the runner call — `claude_invoke`'s call passes no `run_logger`/observer
    here, the same way it passes none today, deferring every event the runner would
    otherwise write through one (`claude_stream_event`, `claude_call_progress`, `claude_call_stall_suspected`,
    `backend_spawn`, `backend_termination`) to step 7, which is where `claude_invoke`
    first builds and passes its observer. The silence-kill and configured-timeout
    protections still apply in full at this step, since they are unconditional and
    do not depend on a bound writer (Architecture) — only the JSONL/event trail is
    deferred, not the safety net.
  files:
  - plan_tool/shell.py
  - plan_tool/backend_runner.py
  - tests/test_shell.py
  - tests/subprocess_doubles.py
  - TESTING.md
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 4
  depends_on_notes:
    1: Its pinned rc/stdout/timeout behavior is what proves the swap preserved the
      (rc, stdout) contract.
    4: Without the runner's timeout kill, completeness-audit's two scoped_claude_timeout
      callers would silently lose their bound.
  detail: docs/implementation-plans/plan-details/batch-authoring-observability/06-run-batch-claude-calls-through-shared.md
  status: done
- id: 7
  title: Widen the active shell sink so batch calls record spawn, progress, stall
    and termination
  intent: Flips step 6's `redaction_ready` flag to `True` at `claude_invoke`'s call
    site, so the runner's `-v` tool-input-summary line switches from suppressed to
    the real, redacted summary for batch callers — the two steps need no special co-landing
    discipline; each is independently safe. Makes a long roadmap stage call readable
    in the JSONL while it is still running, not only after it exits. Redaction lives
    in exactly one place — the parser layer's `_summarize_tool_input` in `plan_tool/backend.py`,
    the same location step 10 completes — never a second check at the sink; this step
    adds the actual scrubbing rule that function does not have today (at HEAD its
    `Bash` branch returns `str(inp.get("command", ""))[:200]` verbatim — truncation,
    not redaction, so an inline secret reaches `tool_input_summary` untouched). The
    rule — pattern-match two concrete shapes inside a command/path/pattern value —
    a known secret-prefix token (the existing `Authorization:`/ `Bearer `-prefixed
    shapes, plus a bare token starting with `sk-`, `ghp_`, `gho_`, `AKIA`, or `xox`)
    or any other contiguous run of 20 or more alphanumeric/`-`/`_` characters containing
    at least two of the three character classes — an uppercase letter, a lowercase
    letter, a digit (a length/character-class heuristic, not true entropy scoring)
    — and replace each match with a fixed `[REDACTED]` placeholder before truncation,
    not after — truncating first could still leak a secret's leading bytes. Over-redaction
    is the accepted failure mode here — a hash, commit SHA, or UUID caught by the
    length/character-class heuristic losing its value in a diagnostic summary is a
    usability cost, not a guarantee violation; under-redaction is not acceptable,
    since this pattern list is the plan's actual enforcement point for the credential
    guarantee, not a best-effort heuristic. `_summarize_tool_input`'s five branches
    each truncate to `_TOOL_INPUT_SUMMARY_CAP` (200 characters) inside their own `return`
    expression today, so "before truncation, not after" cannot mean scanning the function's
    returned value — by the time a caller sees it, it is already truncated, and redacting
    that string would reproduce the exact leaked-leading-bytes bug this rule exists
    to prevent for any secret spanning the 200-character cutoff. This step is a redact-then-truncate
    rewrite of the function instead — each branch's own untruncated candidate value
    gets the pattern-match pass first, then the existing `[:_TOOL_INPUT_SUMMARY_CAP]`
    slice, in that order — including both catch-all return sites, which are textually
    separate, not one "fourth branch" — an early one for any non-dict `inp` (top of
    the function), and a later one for a dict whose `tool_name` matches none of the
    five enumerated names (bottom of the function). Each returns its own raw `json.dumps(inp)`
    preview today with no field-level hook to scrub, so both need the same redact-then-truncate
    treatment on their own candidate string, not a separate mechanism. No existing
    pattern-matching utility in the codebase does this today (checked); the rule is
    new, not reused, and step 10's "same pass" means "the pattern this step defines,"
    not an existing mechanism. This baseline covers both of `_summarize_tool_input`'s
    call sites (claude's `_claude_parse_stream_line` and cursor's own `_cursor_parse_assistant_blocks`),
    and step 10 extends the same rule, not a reinvented one, to the two remaining,
    genuinely separate producers (`_codex_tool_use_summary`, `_cursor_tool_use_summary`)
    — noting those two hand back pre-formatted strings ("path (kind), path (kind)",
    raw command text) rather than the `(tool_name, dict)` shape `_summarize_tool_input`
    expects, so step 10 must either reshape their input to route through it or apply
    the same pattern match as a shared helper both call; either way, one scrubbing
    rule, not three. `--backend`/`PLAN_TOOL_BACKEND` is a global, per-invocation selector
    with no gating tied to which command runs, so until step 10 lands this step suppresses
    `tool_input_summary`, replacing it with the literal `[OMITTED]` (Architecture)
    for any backend whose parser has no redaction yet — codex today, and cursor's
    own `tool_call` producer — rather than forwarding an unredacted summary for whichever
    `--backend` an operator happens to have selected. New spawn/progress/stall/stream
    events ride an additive observer channel; the existing single-argument ClaudeCallEnd-only
    sink contract stays byte-identical for its ~two dozen existing installers. This
    step is also where the shared runner's own parameter changes from step 2's carried-over
    `run_logger` (typed `Optional[RunLogWriter]`) to the observer protocol Architecture
    describes (spawn / stream-event / progress / stall / termination callbacks) —
    `claude_invoke` builds its observer from the writer-carrying ContextVar step 5
    already adds to `shell.py`, reusing it rather than creating a second one; step
    5's own `backend_recovery_wait`/ `run_interrupted` wrap reads that ContextVar
    directly (no observer protocol needed for its narrower purpose), and this step
    is what builds the fuller observer on top of the same reference. `claude_invoke`
    is the first caller to pass a full observer to the runner, so the runner's own
    signature changes here, not in step 2's pure relocation or step 8's `run_step`-side
    adapter. Backward-compatible by design, not by co-landing discipline — the runner
    keeps accepting a bare `run_logger`/`None` at this step too, wrapping it internally
    in a trivial default observer (spawn/termination only, no interrupt-specific handling)
    when what's passed isn't already an observer, so `run_step`'s still-unchanged
    call through `shell_invoker` keeps working exactly as before once this step lands,
    without step 8. Step 8 replaces that internal fallback with `run_step`'s own purpose-built
    adapter, which is what adds the interrupt-specific richness (`run_interrupted`
    with real phase/attempt context) the trivial fallback can't provide — a step 7-only
    landing is safe, just not yet as rich for `run` as after step 8. Building it here
    is also what gives every batch caller with a bound sink, `roadmap` included, `run_interrupted`
    without any roadmap-specific code (see Architecture and step 8). Each observer
    callback invocation is wrapped so a callback exception cannot kill the stdout-pump
    or heartbeat thread it runs on, or suppress the runner's own kill ladder — the
    heartbeat thread carries the 900-second silence kill, so an unwrapped, faulty
    observer callback (a bug in `claude_invoke`'s own observer, or in step 8's `run_step`
    adapter) would silently disable that safety net for the rest of the call, with
    no run-log record explaining why, which is exactly the "indistinguishable from
    a hang" failure this plan exists to close. A caught callback exception is logged
    once (to the console, not the JSONL, since the run-log sink is the thing that
    might be failing) and the runner's own supervision continues unaffected.
  files:
  - plan_tool/shell.py
  - plan_tool/run_log.py
  - plan_tool/backend.py
  - plan_tool/cli/review_cmd.py
  - tests/test_shell.py
  - tests/test_run_log.py
  - tests/test_roadmap.py
  - tests/test_backend.py
  complexity: high
  change_type: feature
  depends_on:
  - 5
  - 6
  depends_on_notes:
    5: Supplies the event types the widened sink forwards.
    6: Puts the batch path on the runner, which is what produces the spawn/progress/stall
      callbacks in the first place.
  detail: docs/implementation-plans/plan-details/batch-authoring-observability/07-widen-active-shell-sink-so-batch-calls.md
  status: done
- id: 8
  title: Record a Ctrl-C as an interrupt and reap the child for roadmap and run
  intent: Leaves no orphan backend child and no ambiguous generic error run_end when
    an operator stops a run, for every `claude_invoke` caller with a bound observer
    as well as for `run`. Once step 7's `claude_invoke` observer is live, `roadmap`'s
    own Ctrl-C already gets `run_interrupted` the same way any other batch caller's
    does — the shared runner's kill-on-any-exception path (step 3), sharpened by step
    4 to classify a caught `KeyboardInterrupt` specifically as `operator_interrupt`,
    notifies whichever observer is bound, and the observer (built from the active
    sink, holding its own phase/attempt state) is what turns that notification into
    a `run_interrupted` record — no roadmap-specific code is needed for the event
    itself (see step 7). What roadmap still needs, and what this step actually adds
    for it, is narrower than the whole event — a clean, non-traceback exit at the
    CLI layer (`cli/roadmap_cmd.py` has no `except KeyboardInterrupt` today) with
    exit code 130; `roadmap.py`'s own `except BaseException`/`finally` wrapper already
    runs `run_end`/`in-flight.json` cleanup underneath, so this part is genuinely
    CLI-layer-only, unlike the event itself. `run` needs the identical CLI-layer fix,
    not a pattern to match — at HEAD, `cli/run_cmd.py`'s `except KeyboardInterrupt`
    handler only sets a local `rc = 130` variable consumed by the run-log record,
    then bare-`raise`s, and `cli/app.py`'s dispatcher catches only `Exception` (`KeyboardInterrupt`/`SystemExit`
    pass straight through by design), so `run`'s Ctrl-C hits Python's default handler
    today — a raw traceback and exit 1, the same failure this plan otherwise attributes
    only to `roadmap`. Since this step already touches `run_cmd.py`, it also makes
    that re-raise reach `sys.exit(130)` for `run`, closing both commands' exit codes
    together rather than treating one as already solved. The same `rc = 130`-then-bare-`raise`
    pattern, with the same missing enforcement, repeats at roughly eight other CLI
    sites (`authoring.py`, `review_cmd.py`, `reconcile.py`) — a pre-existing, repo-wide
    gap this plan does not fix (see `BUG_BACKLOG.md`). For `run`, this step also builds
    `run_step`'s own observer adapter — `run_step` calls `shell_invoker` directly
    rather than `claude_invoke`, so it needs its own translation from `_run_streaming_once`'s
    existing `run_logger` parameter into the observer protocol step 7 puts on the
    runner, giving `run` calls `backend_spawn`/ `backend_termination`/`run_interrupted`
    through the same mechanism batch callers get from step 7, not a second one. Scoped
    to `run_step`'s own direct call only — `apply_finding` is a distinct caller of
    `_run_streaming_once`/`shell_invoker`, and `run --reconcile` is not one of its
    callers at all — its whole audit-and-edit happens inside one claude call under
    `--permission-mode acceptEdits` (`prompts/run-reconcile.md`), with no per-finding
    apply step for `apply_finding` to enter — a dedicated regression test (`test_run_reconcile_does_not_reach_apply_finding`)
    asserts `apply_finding` must not run during `run --reconcile`. Of `apply_finding`'s
    actual callers, five call it directly with no caller-identifying parameter — `create`,
    `detail --iterate`, `bench`, `completeness-audit --iterate` (its own convergence
    loop in `plan_tool/cli/completeness_cmd.py`), and `completeness-apply --jobs N`
    (its own worker in `plan_tool/cli/completeness_apply_parallel.py`) — and several
    more reach it through the shared `walk_recommendations`/`_dispatch_apply_finding`
    dispatch (`plan_tool/cli/review_actions.py`) from multiple interactive/iterate
    walks — the interactive `review` apply walk, `reconcile-plan-walk`'s saved-review
    walk, and `detail --reconcile`'s own fresh-walk, saved-reuse, and `--iterate`
    sub-paths all build their `action_fn` through it. `detail --reconcile`'s saved-reuse
    path (`_walk_saved_detail_reconcile`) is this step's real shared-dispatch example,
    not `run --reconcile`; `run --reconcile` needs no exclusion reasoning at all,
    since it is not reachable, not merely excluded on scope grounds like every other
    caller here. Building a parameter through the shared dispatch (so one caller specifically
    could opt in while its shared-dispatch siblings stayed on today's generic bare-
    `KeyboardInterrupt`-to-`run_end(outcome="error")` handling) is a new cross-cutting
    mechanism this plan does not build; every `apply_finding` caller is out of scope
    here (see Out of scope) and keeps today's behavior. This is the step that makes
    Architecture's "serves both the run lane and the batch lane" true for the full
    event vocabulary for `run`'s own lane specifically, and gives `runs show` one
    schema to render against for either lane within that narrowed scope.
  files:
  - plan_tool/backend_runner.py
  - plan_tool/roadmap.py
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/cli/run_cmd.py
  - tests/test_backend_runner.py
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/test_run_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  - 7
  depends_on_notes:
    5: Supplies run_interrupted and the run_end termination_reason field.
    7: cli/run_cmd.py has two KeyboardInterrupt sites and cli/roadmap_cmd.py none
      — both commands are swept here, not just the one the seed names.
  detail: docs/implementation-plans/plan-details/batch-authoring-observability/08-record-ctrl-interrupt-reap-child.md
  status: done
- id: 9
  title: Keep in-flight.json current for the whole life of a call
  intent: Lets an operator answer 'is it alive?' from one small file without reading
    the whole JSONL. `in_flight_path` is an attribute of `RunLogWriter` — a caller
    with no open `RunLogWriter` has nothing to write a snapshot against, so `in-flight.json`
    follows the same sink-scoped boundary Architecture already draws for the JSONL
    trail — `annotate.py`, `jira.py`, and `create.py`'s slug-generation call produce
    no snapshot, same as they produce no JSONL trail, stated explicitly rather than
    left implied by that code fact. Also refreshes on `backend_recovery_wait` (step
    5), writing a distinct "awaiting retry" status — without this, the snapshot would
    show a plain "terminated" state during `claude_invoke`'s own retry-loop sleep,
    identical to the call actually being over. `write_in_flight()` has exactly one
    call site today, inside `RunLogWriter.start()` — a single write at run start,
    never refreshed again until this step. This step adds the other four triggers
    Architecture already names, each a new `write_in_flight()` call inside the `RunLogWriter`
    method that already owns that event — `phase_start()` refreshes at phase start;
    `backend_spawn()` (step 5) refreshes at spawn; the observer's heartbeat callback
    (step 7) refreshes on each heartbeat, with a snapshot carrying `elapsed_ms`/`silent_ms`
    — the fields Acceptance criteria promises an operator can read — not just the
    run-start fields the single existing write carries; `backend_termination()` (step
    5) refreshes at termination. `RunLogWriter` owns every write, the same component
    that already owns `in_flight_path` and the termination-reason tracking (step 5)
    — no separate caller-side refresh logic.
  files:
  - plan_tool/run_log.py
  - tests/test_run_log.py
  - README.md
  complexity: medium
  change_type: feature
  depends_on:
  - 7
  - 8
  depends_on_notes:
    7: Supplies the heartbeat and spawn callbacks the snapshot refreshes on.
    8: Termination classification has to exist before the snapshot can report a reason.
      README already claims the snapshot is written on every phase and call boundary
      with current_phase / last_event_ts fields; this step makes that claim true.
  detail: docs/implementation-plans/plan-details/batch-authoring-observability/09-keep-flight-json-current-whole-life-call.md
  status: done
- id: 10
  title: Redact tool-input summaries in all three backend parsers
  intent: Extends the parser-level redaction step 7 ships for the shared `_summarize_tool_input`
    function to the two producers step 7 doesn't reach — `_codex_tool_use_summary`
    and `_cursor_tool_use_summary` — using the same pass rather than a reinvented
    one. `_summarize_tool_input` already has two call sites at HEAD — `_claude_parse_stream_line`
    (claude) and `_cursor_parse_assistant_blocks` (cursor's own parser, for the claude-shaped
    assistant/user blocks cursor also emits) — so step 7's redaction already covers
    cursor's shared path, and this step's actual scope is the two genuinely separate
    producers — `_codex_tool_use_summary` (codex's own `tool_call` event type) and
    `_cursor_tool_use_summary` (cursor's own `tool_call` event type, distinct from
    the blocks it shares with claude). Both hand back pre-formatted strings rather
    than `_summarize_tool_input`'s `(tool_name, dict)` shape, and both truncate to
    `_TOOL_INPUT_SUMMARY_CAP` inside their own branches the same way `_summarize_tool_input`
    does, so this step applies step 7's redact-then-truncate rewrite the same way,
    on each branch's own untruncated candidate value before its existing slice — never
    a scan over the already-returned, already-truncated string, and never a field-by-field
    scan either, so neither producer needs its own enumerated-field list to stay covered.
    The concrete pattern definitions step 7 names (the secret-prefix list, the length/
    character-class heuristic for the rest) apply unchanged here — this step reuses
    the pattern, not just the general approach. As the last step, it also brings `docs/RUN_FLOW.md`'s
    "Rate-limit / transient recovery seam" section and source map current — both still
    describe today's start/end-only `_run_streaming_once` and the single sleep seam,
    not the shared runner, the closed termination-reason vocabulary, the observer
    protocol, or the dual wait/sleep wrap steps 2-9 build; leaving that doc stale
    is exactly the failure mode this repo works hardest to avoid.
  files:
  - plan_tool/backend.py
  - tests/test_backend.py
  - docs/RUN_FLOW.md
  complexity: medium
  change_type: feature
  depends_on:
  - 7
  depends_on_notes:
    7: 'Batch calls start emitting tool summaries here, which is what makes redaction
      load-bearing rather than optional. Two producers remain unswept after step 7:
      _codex_tool_use_summary and _cursor_tool_use_summary (cursor''s own tool_call
      type — _summarize_tool_input''s existing call site inside _cursor_parse_assistant_blocks
      is already covered by step 7).'
  detail: docs/implementation-plans/plan-details/batch-authoring-observability/10-redact-tool-input-summaries-all-three.md
  status: done
---
# Batch Authoring Observability

## Overview

`roadmap`'s stage-generation calls, like every other batch-authoring call
routed through `plan_tool.shell.claude_invoke`, run the backend under
buffered `subprocess.run` and parse its `stream-json` output only after the
child exits. The JSONL run log records `claude_call_start`, then nothing,
then a terminal `claude_call_end`. `launcher._run_streaming_once` already
solves this for `run`/`apply_finding` while a subprocess is actually
running: it pumps `stream-json` incrementally, emits a 20-second heartbeat,
flags a 300-second stall suspicion, and kills a child silent for 900 seconds
— but that capability isn't reachable from the batch path. Neither lane has
an event for the separate quiet window between attempts, when the shared
rate-limit/transient retry loop is sleeping with no subprocess running at
all — step 5 closes that gap for both.

## Problem statement

An operator watching a long `roadmap` stage call cannot tell, from the run
directory alone, whether the backend is working, has gone quiet, or is
already dead. `claude_invoke` is shared by seven files (`annotate.py`,
`create.py`, `detail.py`, `jira.py`, `lessons.py`, `review.py`,
`roadmap.py`) plus `shell.py`'s own `shell_concept_invoker` wrapper
(`phase="concept_emit"`, serving `create.py`'s concept-tree sign-off flow
via the `create` orchestrator's `concept_invoker` parameter, alongside its
main `claude_invoker`); none of them get incremental visibility today. Not
all of these gain a JSONL trail from this plan, though: `annotate.py` and
`jira.py` (and `create.py`'s own slug-generation call, made before a plan
slug — and so a run log — exists) never open a `RunLogWriter`, so
`shell.get_active_sink()` returns `None` for their `claude_invoke` calls.
See Architecture.

## Architecture

- **The runner extraction is global, not staged per command.** `claude_invoke`
  is one function; there is no per-caller gate proposed or needed. The moment
  the "wire batch calls" step lands, every caller named above gets
  the new Popen-based runner and its silence kill, unconditionally —
  simultaneously. "Roll out by command class" (roadmap, then detail, then
  reconciliation/audit) describes staging **richer event wiring and operator
  rendering** per call site, not staged activation of the runner itself —
  these are different axes and must not be conflated in the step graph.
  **The heartbeat/spawn/stream-event JSONL trail is a narrower claim than the
  runner itself**: it needs an active sink, which needs an open
  `RunLogWriter`, which `annotate.py`, `jira.py`, and `create.py`'s
  slug-generation call never have (see Problem statement) — those calls keep
  today's silence-kill-only, no-JSONL-trail behavior. `create.py`'s and
  `review.py`'s other call sites do bind a sink and get the full trail, but
  only once step 7 lands — step 6 explicitly withholds the writer from the
  runner call even for a caller with an active sink, so the silence kill is
  live from step 6 but the JSONL trail is gated on both conditions together
  (an active sink *and* step 7), not the sink alone.
- **The 900-second silence kill applies unconditionally, to every batch
  caller, from the moment the runner switches over.** This is a deliberate,
  allowed behavior change, not an accidental side effect — `_run_streaming_once`
  already applies its kill ladder unconditionally even with no run-log attached
  (the safety net is intentionally outside the `run_logger is not None`
  branch), and this effort adopts the same stance for batch calls rather than
  gating it behind per-caller opt-in.
- **The allowed behavior changes this plan makes, stated once, here — every
  other "(see Allowed behavior changes)" reference in this document points
  back to this bullet:** (1) every `claude_invoke` caller gains the
  900-second silence kill above; (2) `run`'s call sites gain the
  kill-on-any-exception net step 3 adds; (3) every `claude_invoke` caller
  with a bound observer — every batch caller that opens a `RunLogWriter` (see
  Problem statement), `roadmap` included — plus `run`'s call sites via step
  8's own adapter, gains a distinct `run_interrupted` event and explicit
  child terminate/reap in place of today's generic bare-`KeyboardInterrupt`-
  to-`run_end(outcome="error")` handling; (4) those same callers gain
  `backend_spawn` / `backend_termination` events they do not emit today;
  (5) both `roadmap` and `run` gain a clean, non-traceback Ctrl-C exit with
  code 130 at the CLI layer (step 8) — neither has one today. `roadmap.py`'s
  stage-running function already wraps its whole run in
  `except BaseException as exc: failure = exc; raise` plus
  `finally: owned_logger.run_end(outcome="error", ...)`, so a Ctrl-C today
  already produces a `run_end` record and cleans up `in-flight.json`; what's
  missing there is a handler at the CLI layer — `cli/roadmap_cmd.py` has no
  `except KeyboardInterrupt` at all, so today's Ctrl-C during roadmap prints
  a raw traceback and exits 1 (Python's default), not 130.
  `cli/run_cmd.py` is not the already-working counterpart this used to
  assume — its `except KeyboardInterrupt` handler only sets a local
  `rc = 130` variable consumed by the run-log record, then bare-`raise`s past
  `cli/app.py`'s dispatcher, which catches only `Exception`
  (`KeyboardInterrupt`/`SystemExit` pass straight through by design) — so
  `run`'s Ctrl-C hits the identical raw-traceback/exit-1 failure today, and
  both commands' exit codes are fixed together in step 8, not one matched to
  an already-solved other. Item (3)'s `run_interrupted` event, unlike the
  exit-code fix, is not CLI-layer-only for the callers other than `run` — it
  comes from the shared runner/observer path (steps 3, 4, and 7), the same
  mechanism every other batch caller with a bound sink gets, and needs no
  roadmap-specific code. The same `rc = 130`-then-bare-`raise` pattern, with
  the same missing enforcement, repeats at roughly eight other CLI sites
  (`authoring.py`, `review_cmd.py`, `reconcile.py`) — a pre-existing,
  repo-wide gap outside this plan's scope (see `BUG_BACKLOG.md`); (6) `run`'s
  and `apply_finding`'s own `-v` tool-input summaries, and their JSONL
  `claude_stream_event` records, also start showing `[REDACTED]`/`[OMITTED]`
  text once steps 7 and 10 land, in place of the real command/path/pattern
  value they show today — `claude_invoke`'s batch calls and `run`'s
  streaming calls parse tool input through the identical shared
  `_summarize_tool_input` function (`CliBackend.parse_stream_line` is one
  function wired to both `batch_argv` and `streaming_argv`), so redacting it
  redacts every caller, not only batch ones; step 6's `redaction_ready` flag
  only gates whether the runner *prints* the `-v` line at all, not what that
  shared function puts inside it, so it does not (and cannot) confine this
  change to batch callers; (7) `_pump_stderr`'s raw live streaming — today
  unconditional, with no verbosity gate, for every caller of the shared
  runner — gains a new verbosity gate, live only at `-v`/`--debug` and
  suppressed at default verbosity, built in step 6 alongside that step's own
  `redaction_ready` parameter since both touch `backend_runner.py`'s console
  paths. This is a *broader* threshold than `_pump_stdout`'s own existing raw-
  NDJSON gate, which fires only at `--debug` (`_CONSOLE_VERBOSITY_DEBUG` —
  `plan_tool/launcher.py`'s `_CONSOLE_VERBOSITY_QUIET`/`_VERBOSE`/`_DEBUG`
  ladder) and stays silent at plain `-v` — the new stderr gate does not reuse
  that condition; it is a new one, `-v`-or-`--debug`, that the codebase does
  not have today. This is a real narrowing of `run`'s own long-standing default-
  verbosity stderr visibility, not only a new gate for batch callers — `run`
  already streamed raw stderr live at every verbosity level before this
  plan, and after step 6 that stops at default verbosity — accepted here
  because raw backend stderr can carry paths or prompt fragments outside the
  redaction rule item (6) above scopes, the same leakage surface this plan's
  step 10 exists to close for structured tool-input summaries. Every
  other behavior stays as it is today — most
  sharply, `run`'s call sites stay exempt from
  `PLAN_TOOL_CLAUDE_TIMEOUT`/`scoped_claude_timeout` (step 4), and the
  default unbounded total-duration timeout for every command is unchanged
  (see Out of scope).
- **Configured-timeout enforcement (`PLAN_TOOL_CLAUDE_TIMEOUT` /
  `scoped_claude_timeout`) does not exist on the streaming side today** — only
  the buffered `_run_once` path enforces it, via `subprocess.run(timeout=...)`.
  The shared runner adds this as new functionality (an elapsed-time check
  alongside the existing silence check in the same monitor thread), not a
  reused capability.
- **Observer wiring**: `_run_streaming_once`'s callers already pass a
  `run_logger` directly; `claude_invoke`'s callers cannot — its invoker
  protocols (`StageInvoker`, `DetailInvoker`, …) are fixed at
  `Callable[[str], tuple[int, str]]` across many call sites and must not
  change. Step 7 is where the shared runner's own parameter changes from
  step 2's carried-over `run_logger` (typed `Optional[RunLogWriter]`) to an
  explicit observer (a narrow protocol: spawn / stream-event / progress /
  stall / termination callbacks) — `claude_invoke` is the first caller to
  pass one. `shell.get_active_sink()` cannot supply it: at HEAD that
  ContextVar accessor returns only `Optional[MetaSink]`
  (`Callable[[ClaudeCallEnd], None]`), the narrow single-event closure
  `RunLogWriter.bind_shell_sink` installs today, with no path back to the
  writer itself — unlike `run_step`'s side, where `launcher._run_logger_var`
  already carries the real `Optional[RunLogWriter]` directly (which is why
  step 8's adapter is buildable as described). Step 5 is where the second
  ContextVar in `shell.py` is actually created, set alongside the existing
  `MetaSink` wherever `bind_shell_sink`/`install_call_end_sink` run, that
  carries the writer itself — step 5 needs it first, to write
  `backend_recovery_wait`/`run_interrupted` for `claude_invoke`'s own
  wait/sleep wrap, reading the ContextVar directly with no observer protocol
  involved. Step 7 reuses that same ContextVar to build the fuller observer
  on top of it, rather than creating a second one; `claude_invoke` builds
  its observer from it, not from `get_active_sink()`. This is also what
  gives every batch caller with a
  bound sink, `roadmap` included, `run_interrupted` without any
  roadmap-specific code once steps 3 and 4 classify an operator interrupt
  (see the allowed-changes item 3 above and step 8). `_run_streaming_once`'s
  `run_step` caller adapts its own `run_logger` into an observer
  implementing the same protocol — step 8 is where this adapter is built.
  `apply_finding`'s calls keep passing through unadapted, matching step 8's
  own scope and Out of scope: `run --reconcile` is not one of
  `apply_finding`'s callers at all (its whole audit-and-edit happens inside
  one claude call, with no per-finding apply step); of `apply_finding`'s
  actual callers, five call it directly with no caller-identifying
  parameter (`create`, `detail --iterate`, `bench`, `completeness-audit
  --iterate`, `completeness-apply --jobs N`), and several more — the
  interactive `review` apply walk, `reconcile-plan-walk`'s saved-review
  walk, and `detail --reconcile`'s own fresh-walk, saved-reuse, and
  `--iterate` sub-paths — reach it through the shared dispatch.
  `detail --reconcile`'s saved-reuse path is the real shared-dispatch
  example step 8's scope fence needs, not `run --reconcile`. None of these
  callers gets `backend_spawn`/`backend_termination`/
  `run_interrupted` from this plan. **The existing
  single-argument, `ClaudeCallEnd`-only sink contract does not change shape** —
  roughly two dozen production and test sites install a plain single-argument
  callable against that exact contract and none of them are touched. The new
  spawn/stream-event/progress/stall/termination events ride a separate,
  additive observer channel that `bind_shell_sink` installs alongside the
  existing sink, not through it.
- New event types on `run_log.py` — every one of the four also carries
  `phase`/`attempt` (and `backend_spawn`/`backend_termination` also carry
  `backend`) as its correlation-key pair, the same two field names across all
  four event types rather than a per-event `active_phase`/`active_attempt`
  spelling — `backend_spawn` (phase, attempt, backend, transport,
  child_pid, effective_timeout_ms, prompt_bytes — `effective_timeout_ms` is
  the earlier of the configured timeout and the silence threshold when both
  apply to this caller (a `claude_invoke` caller under
  `PLAN_TOOL_CLAUDE_TIMEOUT`/`scoped_claude_timeout`), or the silence
  threshold alone when only that applies (`run`'s call sites, which stay
  exempt from the configured timeout, and any `claude_invoke` caller with no
  configured timeout set) — never `null` at the one production bracket that
  emits it once step 7 lands, since every spawn has at least the silence
  threshold; step 5's own short-lived batch-lane bracket, retired once step 7
  lands, is the one caller that legitimately leaves the four extra fields at
  their `None` default, since `_run_once`'s buffered `subprocess.run` call
  exposes none of them), `backend_termination`
  (phase, attempt, backend, reason, duration_ms, signal_or_timeout,
  silent_ms — `duration_ms` is this bundle's name for total elapsed call
  time, the same duration-field convention `backend_recovery_wait`'s
  `delay_ms` already uses; `signal_or_timeout` and `silent_ms` are populated
  only by step 7's runner-native bracket, which is the only producer that
  knows which kill mechanism fired and how long the child had been silent),
  `run_interrupted`
  (phase, attempt, source, signal — `signal` is `"SIGINT"` for every
  interrupt this plan produces, since Python's `KeyboardInterrupt` is always
  the SIGINT translation on the main thread; reserved for a future non-SIGINT
  source rather than doing real classification work today), `backend_recovery_wait`
  (reason, delay_ms, next_attempt, backend; `next_attempt` is the upcoming
  attempt's ordinal number, matching the `attempt` field the other events
  already carry, not a timestamp — `delay_ms` already carries the duration)
  — covers the rate-limit/transient backoff sleep in the shared recovery
  loop both `claude_invoke` and `shell_invoker` drive, a quiet window
  between attempts that today produces no event at all on either lane,
  first identified as a gap on `roadmap` stage 4 but real for every caller
  of that loop. `reason` is `rate_limit` or `transient` — the loop has two
  separate sleep seams, one per reason (`wait` for rate-limit, `sleep` for
  transient), and both must be wrapped for `reason` to actually cover what
  it claims — matching the existing
  `claude_errors.ClaudeFailureKind` vocabulary rather than inventing a second
  one. `backend_spawn`'s `transport`
  field is a safe descriptor only — e.g. which of argv/stdin carries the
  prompt, or the transport kind — **never** the `PromptTransport` object
  itself, which carries the literal prompt text. The "never log prompt
  content, environment values, credentials, or complete provider messages"
  guarantee (below) applies to every new event type — `backend_spawn`,
  `backend_termination`, `run_interrupted`, and `backend_recovery_wait` — not
  only `claude_stream_event`. Closed termination-reason enum: `completed`,
  `configured_timeout`, `silence_timeout`, `operator_interrupt`,
  `spawn_failure`, `backend_nonzero`, `unknown` — `unknown` covers a
  `proc.wait()` exception that is neither a `KeyboardInterrupt`
  (`operator_interrupt`) nor a monitor-thread-initiated timeout kill
  (`configured_timeout`/`silence_timeout`); step 3's kill-on-any-exception
  net (Architecture's allowed-changes item 1/2) still kills and reaps the
  child for this case, it just has no more specific reason to report than
  `unknown`. `run_end` carries a
  normalized `termination_reason` alongside its existing compatibility
  fields, for every caller that reaches a `backend_termination`/
  `run_interrupted` event — the same scope item (4) above already grants,
  plus `run` via step 8 (step 5) — `RunLogWriter` tracks the
  most recent reason internally as its own `backend_termination`/
  `run_interrupted`-writing methods run, and `run_end()` reads that tracked
  value by default rather than every one of its ~23 existing call sites
  passing one explicitly. Under a multi-spawn bracket (Risks),
  `run_end.termination_reason`
  reflects the terminal spawn's own reason — the one that decided the
  bracket's outcome — not the first spawn's, because each new spawn's
  termination overwrites the tracked value. `RunLogWriter`'s own tracking is
  deliberately simple and unlocked: it always receives an already-resolved
  reason, once, in a fixed sequential order — one `backend_termination`/
  `run_interrupted` call per exit point, never two threads writing to the
  writer concurrently for the same call — so plain last-write-wins on that
  one attribute is correct as written, with no bookkeeping of its own to
  add. The genuine race lives one layer down, entirely inside
  `backend_runner.py`, and is fully resolved *before* `RunLogWriter` is ever
  called: the heartbeat thread's kill and the main thread's
  `KeyboardInterrupt` are two genuinely independent threads that can both
  decide a call is ending around the same moment, so plain last-write-wins
  on `backend_runner.py`'s own per-call termination-reason cell (step 4)
  cannot guarantee which one lands last — that cell's write is instead a
  priority write, guarded by one lock around the
  read-check-write: writing `operator_interrupt` always overwrites whatever
  is tracked; writing any monitor-thread reason
  (`silence_timeout`/`configured_timeout`) is refused if the tracked value
  is already `operator_interrupt`. This holds regardless of which thread's
  write reaches the lock first — an operator interrupt landing the same
  moment any monitor-thread kill fires (step 4 puts both
  `configured_timeout` and `silence_timeout` on that same thread) always
  resolves to `operator_interrupt`, since an explicit operator action takes
  precedence over an inferred one, for either kill.
- `in-flight.json` updates atomically at phase start, backend spawn, each
  heartbeat, termination, and `backend_recovery_wait`, staying a small
  current-status projection; the JSONL stays append-only and authoritative for
  history. The `backend_recovery_wait` trigger matters specifically: without
  it, the termination write for a failed attempt inside `claude_invoke`'s own
  retry loop would leave `in-flight.json` showing a plain "terminated"
  snapshot between that attempt and the next one's `backend_spawn` — the same
  signature as the call being over, when it is actually about to retry. That
  update writes a distinct "awaiting retry" status, not just a refreshed
  timestamp.
- Structured `claude_stream_event` payloads stay summarized: tool type and a
  redacted path/pattern/command summary only, never stdin prompt content,
  environment values, credentials, or complete provider messages. A field
  with a matched secret substring keeps its summary with each match replaced
  by `[REDACTED]`; a field suppressed wholesale, because its backend has no
  redaction yet, carries the literal string `[OMITTED]` instead of the real
  summary — never `None`, an empty string, or a silent drop, and never
  `[REDACTED]`, which stays reserved for an actual matched substring so a
  reader can tell "redaction ran and found something" apart from
  "redaction hasn't shipped for this backend yet."
  Raw NDJSON transcript capture and `runs show`/`runs watch` liveness
  rendering are carved out to a follow-on plan (see Deferred) — this plan
  delivers the redacted JSONL events and `in-flight.json` snapshot those
  features consume, not the forensic transcript or the operator-facing view
  themselves.
- Ordering constraint on the work itself: characterize today's start/end-only
  behavior in tests before touching anything; extract the shared runner
  byte-compatible with `run`'s existing behavior before wiring `claude_invoke`
  to it, carrying forward a baseline kill-on-any-exception safety net so the
  extraction itself never regresses today's Ctrl-C behavior even before richer
  interrupt classification lands; add termination classification (including
  `roadmap`'s net-new `KeyboardInterrupt` handling) after the runner is live;
  refresh `in-flight.json` after termination classification exists to report
  against; land redaction before batch stream events start reaching the run
  log — a batch caller must never emit an unredacted tool-input summary, even
  for a single call, from any surface. This project's own execution model
  commits each green step individually, so no pair of steps in this plan may
  depend on landing as a single atomic unit — each step must be safe on its
  own once committed, which is why steps 6 and 7 (and steps 7 and 8) are each
  designed fail-closed rather than ordering-dependent, not merged or required
  to land together: step 6's `redaction_ready` flag suppresses the
  runner's `-v` tool-input line for batch callers by default, so step 6 alone
  never exposes an unredacted summary — step 7 flips the flag once its
  redaction is in place. Step 7's runner keeps accepting `run_step`'s
  existing `run_logger`-shaped call via a trivial internal fallback observer,
  so a step-7-only landing never breaks or silently drops `run`'s logging —
  step 8 replaces that fallback with `run_step`'s own richer, purpose-built
  adapter. The carved-out
  follow-on plan's own ordering constraint (redaction before its transcript
  writer ships) depends on this plan's redaction landing first.

## References

- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — Authoritative list of Claude Code CLI flags including `-p` and `--output-format stream-json`, which defines the exact backend invocation the shared Popen runner must spawn and keep byte-compatible.
- [Run Claude Code programmatically (headless mode)](https://docs.claude.com/en/docs/claude-code/headless) — Documents non-interactive invocation and the JSON/stream-json message objects the CLI emits, which is what the incremental pump parses into `claude_stream_event` and `backend_*` run-log records.
- [Streaming Messages — Claude API](https://docs.anthropic.com/en/api/messages-streaming) — Defines the underlying SSE event taxonomy (message_start, content_block_start/delta/stop, message_delta, ping, message_stop) and where usage/cost fields appear, so heartbeat resets and summarized event payloads key on real event boundaries rather than guesses.
- [subprocess — Subprocess management (Python 3.13)](https://docs.python.org/3/library/subprocess.html) — Primary reference for Popen, incremental pipe reads and the deadlock hazard, plus terminate/kill/wait/TimeoutExpired semantics needed for the silence kill, configured-timeout check, and child reaping.
- [signal — Set handlers for asynchronous events (Python)](https://docs.python.org/3/library/signal.html) — Explains SIGINT→KeyboardInterrupt translation, that Python handlers always run on the main thread, and why complex apps should install an explicit SIGINT handler — directly governs the new `run_interrupted` handling around roadmap's stage loop and the monitor thread.
- [os — Miscellaneous operating system interfaces (os.replace)](https://docs.python.org/3/library/os.html#os.replace) — Specifies that os.replace is an atomic, cross-platform overwrite (POSIX requirement) and fails across filesystems — the contract behind atomically refreshing `in-flight.json` at spawn, heartbeat, and termination.
- [JSON Lines specification](https://jsonlines.org/) — The one-valid-JSON-value-per-\n-line, UTF-8 format rules the append-only run log and the raw NDJSON transcript capture must satisfy to stay parseable record-by-record while a run is still in flight.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Percent-complete estimation for a model call — liveness only.
- Any change to roadmap semantics, gates, retry budgets, feedback, or seed
  invalidation behavior.
- Changing the default (unbounded) total-duration timeout for any command.
  The new silence-based kill is a distinct mechanism (see Architecture's
  "allowed behavior changes" bullet) — it must not be described or
  implemented as a global timeout, and `run`'s call sites stay exempt from
  `PLAN_TOOL_CLAUDE_TIMEOUT`/`scoped_claude_timeout` exactly as they are
  today (step 4).
- Raw provider transcripts, in any form — capture, redaction-of-raw-lines, and
  retention are entirely the carved-out follow-on plan's concern (see
  Deferred); this plan makes no transcript.
- `runs show` and `runs watch` — neither the one-shot render nor a
  tailing/follow mode is built here; both are the carved-out follow-on plan's
  concern (see Deferred). This plan's acceptance criteria are satisfied by an
  operator reading the JSONL/`in-flight.json` directly, not by a CLI view.
- A browser or network consumer of the event stream.
- Wiring `create`, `annotate`, `detail`, `jira`, `lessons`, and `review`
  (reconciliation/audit) with their own phase/attempt event labels — all seven
  `claude_invoke` callers inherit the shared-runner mechanics automatically the
  moment `claude_invoke` switches (see Architecture), but giving any of them
  roadmap-quality operator rendering — including `detail` and `review`, the
  next two named in the "roll out by command class" staging order — is
  deferred to follow-up work; no step in this plan builds it.
- Making per-command silence/stall thresholds configurable.
- Wiring `run_interrupted`/`backend_spawn`/`backend_termination`/
  `backend_recovery_wait` into any `apply_finding` call site — `apply_finding`
  is a distinct caller from `run_step`, and `run --reconcile` is not one of
  its callers at all (its whole audit-and-edit happens inside one claude
  call, with no per-finding apply step — a regression test asserts
  `apply_finding` never runs during `run --reconcile`). Five call sites call
  `apply_finding` directly, with no caller-identifying parameter (`create`,
  `detail --iterate`, `bench`, `completeness-audit --iterate`, and
  `completeness-apply --jobs N`), and several more — the interactive
  `review` apply walk, `reconcile-plan-walk`'s saved-review walk, and
  `detail --reconcile`'s own fresh-walk, saved-reuse, and `--iterate`
  sub-paths — reach it through the shared `walk_recommendations`/
  `_dispatch_apply_finding` dispatch with no caller-identifying parameter to
  scope by; all are excluded here on cost/scope grounds. All of these keep
  today's generic `except KeyboardInterrupt: ... run_end(outcome="error")`
  handling, with no `backend_recovery_wait` either. Step 8 is scoped to
  `run_step`'s direct
  call only.
- Giving concurrent same-slug calls separate `in-flight.json` identities or
  cross-process locking. `in_flight_path` stays one file per slug, and writes
  (spawn, heartbeat, termination) stay last-writer-wins exactly as they are
  today — a second call against an already-running slug's snapshot writes
  overwrite the first call's, with no run-id-scoped file names. What is in
  scope (step 9): a completing call's teardown must not delete a *newer*
  same-slug call's still-live snapshot out from under it — a total loss of
  signal, not an overwrite, and not what "last-writer-wins" was ever meant to
  produce. That is a single read-check-skip guard on `run_end()`'s existing
  unlink, not a second file or a lock. "Concurrent runs don't clobber
  snapshot/log state" (Testing) means distinct slugs.

## Risks

- The universal silence kill (see Architecture's "allowed behavior changes"
  bullet) could terminate a
  legitimate batch call — from any of the seven `claude_invoke` callers, not
  only `roadmap` — whose usage pattern includes a long single tool-use burst
  with no incremental stream event. Mitigate by keeping the threshold
  centrally defined and test-injectable (already required), and treat any such
  caller surfaced during characterization as a signal to raise *that caller's*
  threshold via a developer-set, code-level override — the same
  `scoped_claude_timeout` context-manager pattern `shell.py` already uses for
  per-caller timeout scoping, not an operator-facing flag or env var, which
  stays excluded by Out of scope/Deferred — rather than abandoning the global
  kill. Step 4 builds the override hook outright, as part of its own scope —
  not conditionally on step 1 surfacing a caller that needs it, and not
  deferred to an unnamed follow-up, since no follow-up plan owns this (the one
  named follow-up, `2-batch-observability-forensics-and-view.md`, covers raw
  transcripts and `runs show`, not this). The monitor thread's
  timeout/termination-reason machinery step 4 already adds is where the hook
  belongs regardless of whether step 1 finds an immediate caller for it.
- Once step 6 lands, an operator's global `-v`/`--debug` flag becomes live for
  batch callers for the first time — before this plan, `subprocess.run` never
  streamed anything for a batch call, so those flags were no-ops there. The
  shared runner's console paths read verbosity directly and do not depend on a
  run-log observer being attached, so `-v`'s per-tool-use summary line would
  print unredacted at step 6 if it printed at all — closed by step 6's own
  `redaction_ready`-gated suppression (Architecture), not by requiring steps 6
  and 7 to land together.
  `--debug`'s raw NDJSON passthrough is a separate surface: it bypasses
  `_summarize_tool_input` entirely by design (it never parses the line), so no
  step's redaction touches it regardless of ordering. **Decided:** `--debug`'s
  raw passthrough stays unredacted, matching the risk `run` already carries
  today and accepting that `--debug` is an explicit, operator-chosen
  diagnostic flag, not a default. Testing's "never reaches... verbose terminal
  output" guarantee is scoped to `-v`'s per-tool-use summary line (which does
  go through `_summarize_tool_input`) and the JSONL, not to `--debug`'s raw
  passthrough — stated explicitly here so it isn't read as an unsatisfiable
  requirement.
- Two genuinely different retry layers exist per roadmap call: the
  roadmap-level attempt loop (`_run_stage`, parse/gate failures) and
  `claude_invoke`'s own internal rate-limit/transient retry loop, which can
  spawn more than one subprocess per single `claude_call_start`/
  `claude_call_end` bracket. The event model must account for multiple
  `backend_spawn`/progress sequences nesting inside one bracket — this is
  compatible with the sink's existing phase/attempt-override behavior, but is
  not automatic and needs its own test, proving `run_end.termination_reason`
  reflects the terminal spawn's reason (Architecture), not the first spawn's.
  Step 5 owns this test, at the writer level (two `backend_termination()`
  calls with different reasons through one `RunLogWriter`, then `run_end()`
  reading back the second), plus a caller-level case driving a
  rate-limit-then-success `claude_invoke` bracket whose owning `run_end()`
  reflects the terminal attempt's reason — the writer mechanism is what the
  property depends on, and step 5 is the step that builds it.
- Migrating `_run_streaming_once` risks a behavior regression in `run` — no
  caller of the shared runner may observe stdout/stderr/timing changes versus
  today.

## Testing

Prove: full event ordering on a roadmap call (start, spawn, stream activity,
periodic progress, end, phase end, run end); `in-flight.json` refreshes at
each of its five triggers (phase start, backend spawn, each heartbeat,
termination, `backend_recovery_wait`), with a heartbeat-time snapshot
carrying `elapsed_ms`/`silent_ms`, not just the run-start fields the single
pre-existing write carries; with step 6 landed and step 7
not yet landed, none of `claude_stream_event`, `claude_call_progress`,
`claude_call_stall_suspected`, `backend_spawn`, or `backend_termination` is
written to the JSONL for any of the seven `claude_invoke` callers — the
silence kill still reaps a wedged child in that state, with no event trail
at all, not a redacted one; `run_end.termination_reason`
reflects `RunLogWriter`'s internally tracked value with no change to any of
its ~23 existing call sites, populated for `roadmap`, `create`'s and
`review`'s own call sites, `run`, and every other caller that reaches a
`backend_termination`/`run_interrupted` event, and stays unset only for
`annotate.py`, `jira.py`, and `create.py`'s slug-generation call, which
never open a `RunLogWriter` at all;
`backend_spawn.effective_timeout_ms` reports the configured timeout when a
`claude_invoke` caller has both thresholds active and it is shorter than the
silence threshold, and the silence threshold alone for a `run` step call or
any caller with no configured timeout; a `run` step call also emits
`backend_spawn`/`backend_termination` through the same observer protocol, not
only `run_interrupted`; a `run` step call and a `roadmap` batch call each emit
`backend_recovery_wait` for a rate-limit wait *and* for a transient backoff
sleep, proving both of the recovery loop's seams are wrapped on both lanes,
not only the rate-limit one; growing `silent_ms` with reset on stream activity;
exactly one stall marker per call; a 900-second-silent call is reaped and
records `silence_timeout` with no extra-budget retry, via the same
`ClaudeFailureKind` bridge a `configured_timeout` kill already uses; a
caller using step 4's silence-threshold override hook gets reaped on its own
shorter (or longer) threshold while a concurrent caller with no override
still reaps at the global 900-second default, proving the override is
per-caller, not global; a backend process that exits on its own with a
nonzero code, outside any timeout/interrupt/spawn-failure path, is classified
`backend_nonzero`, not lumped under `completed` or `unknown`; a stray
non-`KeyboardInterrupt` exception from `proc.wait()` (e.g. an `OSError`) is
classified `unknown`, and the child is still killed and reaped by step 3's
net exactly as for any other exception; a
spawn-time exception (`Popen` itself failing) is classified `spawn_failure`
and reaches `backend_termination`, not an uncaught traceback, and neither it
nor `unknown` triggers a retry in the shared rate-limit/transient loop —
both classify `UNKNOWN_NONZERO` and surface once; an operator
interrupt landing the same moment a call crosses the silence threshold, or
the same moment a configured-timeout kill fires, records `operator_interrupt`
in both cases, not `silence_timeout`/`configured_timeout` (Architecture's
precedence rule);
`PLAN_TOOL_CLAUDE_TIMEOUT` records `configured_timeout` distinctly from
`silence_timeout` for a `claude_invoke` caller, and is never checked at all for
a `run` step call; Ctrl-C records `run_interrupted` and leaves no in-flight
snapshot or orphan child, for both `roadmap` and `run` — `roadmap`'s proven
through the shared runner/observer path (steps 3, 4, 7), `run`'s through
step 8's own adapter, and separately for a Ctrl-C landing inside
`backend_recovery_wait` (step 5's own seam wrap), not only during an active
subprocess; a Ctrl-C during either `roadmap` or `run` actually terminates the
process with exit code 130 (a subprocess check, not just an internal `rc`
variable), proving step 8's `sys.exit(130)` fix reaches the real exit code
for both, not only `roadmap`'s — the pre-existing gap this corrects for `run`
(see Architecture); gate-failure/retry
logs still pair the right phase/attempt with each terminal call event,
including when the shared recovery loop fires more than once per bracket, for
either lane; a faulty observer callback that raises on every invocation still
lets the 900-second silence kill and the configured-timeout kill fire on
schedule, proving a callback exception can't disable the runner's own
supervision; usage/cache/request-id/cost fields stay populated; a known secret
fixture never reaches JSONL or `-v`'s per-tool-use summary line, proven with
steps 6 and 7 landed together as Architecture requires, proven again for
step 10's own two producers — a codex `tool_call` item and a cursor
`tool_call` block each carrying the same fixture — since closing that gap is
step 10's whole purpose, and proven a fourth time for a `run` step call
itself once steps 7/10 land (Architecture's allowed-changes item 6) — the
same fixture, run through `run`'s existing `-v`/JSONL path, shows
`[REDACTED]`/`[OMITTED]` there too, not only for a batch caller; `--debug`'s
raw NDJSON passthrough is explicitly excluded from this guarantee (see Risks);
concurrent runs
against **distinct slugs** don't clobber each other's snapshot/log state
(same-slug concurrent invocation keeps today's last-writer-wins
`in-flight.json` contract — see Out of scope). Raw-transcript redaction and
`runs show` liveness rendering are proven by the carved-out follow-on plan
(see Deferred), not here — this plan proves the JSONL and `in-flight.json`
carry the data, not that a CLI renders it.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion. This step's entire deliverable is characterization tests, so the test-authoring gate applies here more than anywhere else in the plan.
- step 2 (refactor) — a test proving the relocated pump/heartbeat/silence-kill behavior is byte-identical to today's `run`; no new behavior in this step to test beyond that.
- step 3 (feature) — a test proving a KeyboardInterrupt during `proc.wait()` kills the child, for both lanes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.
- step 8 (feature) — tests covering the behavior this step changes; green before completion.
- step 9 (feature) — tests covering the behavior this step changes; green before completion.
- step 10 (feature) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

The next time a roadmap backend call goes quiet, an operator reading the run
directory's JSONL and `in-flight.json` directly can tell: whether the child
started and which phase/attempt it belongs to; elapsed and silent duration and
the last safe observable activity; whether the call crossed the
stall-investigation threshold; and whether it ended normally, timed out, was
silence-terminated, or was interrupted — with exactly one reason recorded even
when a bracket spans multiple spawns (the terminal spawn's reason wins) or an
interrupt and any monitor-thread kill (`silence_timeout` or
`configured_timeout`) become true near-simultaneously (the interrupt always
wins). A friendly `runs show` rendering of
this same data is the carved-out follow-on plan's acceptance criterion, not
this plan's. No change weakens existing prompt, credential, artifact, or
run-log size/atomicity protections. A Ctrl-C during a batch call is never
worse than today's behavior at any point in the rollout, because the child is
always reaped, never orphaned — every step in this plan is individually safe
to land and commit on its own (see Architecture's ordering-constraint
bullet). `shell._run_once`, `shell._normalize_batch_stdout`, `_run_once`'s
own `subprocess.TimeoutExpired`-to-synthetic-stderr glue, and
`PLAN_TOOL_SHELL_DEBUG` no longer exist in the codebase once step 6 lands —
`claude_errors.BACKEND_TIMEOUT_SENTINEL` and its `classify()` check are not
part of that removal; they survive, fed by the runner's kill path instead
(see step 4). `docs/RUN_FLOW.md` describes the shared
runner, the closed termination-reason vocabulary, and the observer protocol,
not the design this plan replaces, once step 10 lands.

## Deferred

Steps carved out to a follow-on plan — raw NDJSON transcript capture,
`runs show` liveness rendering, and the corresponding docs/backlog updates —
now `docs/implementation-plans/2-batch-observability-forensics-and-view.md`
(created from the carved forward-seed; the seed itself is archived at
`plan-seeds/archive/batch-authoring-observability-carved-save-a-raw-ndjson-transcript-only-through-12.replaced.md`).
That plan carries forward the design work already done on this content in
this plan's history (commits `6e674648` and `050aea18`, and completeness
reports `20260812-162406` / `20260812-165729`) — the transcript-trigger
precision (terminal outcomes only, not the transient stall marker), the raw
transcript's own redaction requirement (separate from the parser-level
summary redaction), and the `runs show` liveness-pid and exec-not-found
distinctions — so authoring its detail does not re-derive them from scratch.
It also inherits this round's `stream-redaction-backend-selection-gap` fix
(step 7/10's redaction split): the carved plan's raw-transcript writer should
be checked against whichever parsers actually have redaction once both plans
have landed, not assumed complete.

Also deferred: configurable per-command silence/stall thresholds; a
repository policy restricting which tool summaries are safe across
Claude/Codex/future backends beyond the shared redaction pass; a `runs watch`
polling/tailing mode; giving
`create`/`annotate`/`detail`/`jira`/`lessons`/`review` their own phase/attempt
event labels.
