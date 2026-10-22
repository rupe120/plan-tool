# `run` workflow

This document maps the **run** phase of the core lifecycle
(`create → detail → audit → run`) and, in particular, the **gates** a step
passes through on its way to `done` — which fire on every run, which fire only
under a flag, and which are advisory (warn) versus blocking (halt).
Source-of-truth references are inline; see the [source map](#source-map).

> Resume after a crashed or aborted run is covered by the shared engine in
> [`RESUME_FLOW.md`](../recovery/README.md) — `run` re-derives from the on-disk plan
> (the `status:` / `current` markers), so a re-invocation simply resolves the
> next runnable step.

## TL;DR

- **Two entry paths, one core.** A single-step `run` (`plan-tool run <name>`
  or `--step N`) and a sweep (`run <name> --all`) both funnel into
  `run_step()` (`plan_tool/launcher.py`). The sweep is `run_step()` in a loop,
  with extra pre-loop validation and per-step commit/archive hooks wrapped
  around it.
- **Gates come in two flavors.** **Blocking** gates halt the run with a
  non-zero rc and *leave the plan un-advanced* (pre-flight paths, the claude
  call itself, no declared file changed, the plan-level `test_command`,
  per-step `gate:` commands).
  **Advisory** gates only print a warning and let the run proceed (missing
  detail file, missing `## Summary` / `## Validation`, missing `creates:`
  entries).
- **Mode decides which gates run at all.** Only `--mode run` (the default,
  the one mutating mode) reaches the post-flight gates and advances the plan.
  Every audit mode (`check`, `optimize`, `document`, `test`, `security`,
  `lint`, and the `--reconcile` code-audit path) short-circuits right after
  the claude call: report only, plan untouched.
- **Grade is a separate axis from mode.** `--detail-grade` picks which detail
  *artifact* the step executes from; it changes no gate above. See
  [Executing from the jira-grade bundle](#executing-from-the-jira-grade-bundle---detail-grade-jira).
- **`--dry-run` skips everything past prompt render.** It prints the prompt
  and exits 0 — no claude call, no gates, no advancement.
- **Flags add gates, they don't remove them.** `--commit` adds a clean-tree
  precondition plus a per-green-step commit; `--archive` adds an
  on-completion move; `--allow-missing-parent` is the one flag that *removes*
  a gate (the pre-flight path check).

## High-level flow

```
                         plan-tool run <name> [--step N | --all] [--mode M] [flags]
                                              |
              ┌───────────────────────────────┴───────────────────────────────┐
              │  DISPATCH (before any plan write — plan_tool/cli/run_cmd.py)    │
              │    --all .................. → sweep loop (Path B, below)        │
              │    --reconcile ............ → code-audit path (mutex w/ --mode, │
              │                               --iterate; else rc=2)             │
              │    (otherwise) ............ → single step (Path A, below)       │
              └───────────────────────────────┬───────────────────────────────┘
                                               v
                              ┌────────────────────────────────┐
                              │  validate legacy loop flags      │  fail → rc=2
                              │  (compatibility only; no loop)   │
                              └────────────────┬───────────────┘
                                               v
                                         run_step()  ◄── the shared core
```

### `run_step()` — the gate gauntlet (the heart of the diagram)

Read top-to-bottom. `[BLOCK]` = halts the run, rc≠0, **plan not advanced**.
`[WARN]` = prints a warning, **continues**. `[SKIP-if]` = the gate does not run
when the condition holds.

```
  run_step()  (plan_tool/launcher.py:1461)
     │
     ├─[1] parse plan + resolve step ......................... [BLOCK] no runnable step → rc=2
     │
     ├─[2] PRE-FLIGHT: file paths exist? ..................... [BLOCK] missing parent dir → rc=2
     │        SKIP-if --allow-missing-parent
     │
     ├─[3] overlap with downstream steps? ................... [WARN]  cross-step refactor in flight
     │        runs only for the mutating mode
     │
     ├─[4] render prompt
     │        + append test directive (mutating mode only; per change_type;
     │          SKIP-if enforcement off — `enforce_step_tests`, or per-step
     │          `enforce_test_authoring` override)
     │
     ├─[5] --dry-run? ─── YES ──► print prompt, return rc=0   (no claude, no gates, no advance)
     │        │ NO
     │        v
     ├─[6] CLAUDE CALL ...................................... [BLOCK] rc≠0 (or is_error) → return rc,
     │        snapshot declared files first (mutating mode)            plan NOT advanced
     │
     ├─[7] mode != run? ─── YES ──► return rc=0, stdout       (AUDIT modes stop here: report only,
     │        │ NO  (mutating mode only, below)                plan untouched, no post-flight gates)
     │        v
     ├─[8] ## Summary present? .............................. [WARN]  contract miss
     ├─[9] any declared file modified? ..................... [BLOCK] none changed → "no edits applied",
     │        SKIP-if step declares no files                          status_note, return rc=1, NOT advanced
     ├─[10] ## Validation present? ......................... [WARN]  "step didn't declare what it tested"
     │
     ├─[11] TEST-AUTHORING gate ........................... [BLOCK] no test file changed → status_note,
     │        SKIP-if not (enforcement-on & feature/refactor)          return rc=1, plan NOT advanced
     │        combines working-tree delta and commits since pre-call HEAD
     │        excludes every path already dirty before the call
     │
     ├─[12] PLAN-LEVEL test_command gate ................... [BLOCK] rc≠0 → write status_note, return rc,
     │        SKIP-if plan has no `test_command:`                     plan NOT advanced
     │
     ├─[13] PER-STEP gate: commands (in order) ............. [BLOCK] first rc≠0 → write status_note,
     │        SKIP-if step has no `gate:` list                        return rc, plan NOT advanced
     │
     ├─[14] all `creates:` entries on disk? ............... [WARN]  "N creates entries missing"
     │
     ├─ re-read plan (concurrent-edit safe)                  ◄── no more failure branches past here
     ├─ mark step done, promote next → current,
     │   flip plan → completed if all done
     └─ persist plan + append lessons entry → return rc=0, advanced_to / done / plan_completed
```

### Path A — single step (after `run_step()` returns)

```
  result = run_step(...)            (plan_tool/cli/run_cmd.py:cmd_run)
     │
     ├─ --dry-run? .................... return rc=0
     ├─ result.exit_code ≠ 0? ......... print recovery hints, return that rc   (a gate halted)
     ├─ mode ≠ run? ................... print findings verdict, return rc=0     (audit report)
     │                                  (reconcile also saves + walks findings)
     └─ success (step green):
          ├─ --archive & plan_completed? . move plan → archive/, deregister manifest, print undo hint
          │     SKIP-if not complete / no --archive       (runs BEFORE the commit so it's captured)
          ├─ --commit & step done? ...... git add -A + one commit per green step   (clean-tree precheck
          │     SKIP-if no --commit            commit fails → return its rc          ran pre-run; dirty → rc=2)
          │                                    (captures the archive move when the step completed + archived)
          ├─ advanced_to set ............ "✓ step N done — advanced to step M"
          ├─ plan_completed ............. "✓ plan complete" (archived above when --archive)
          └─ neither .................... "✓ step N done — no next runnable step"
```

### Path B — sweep (`--all`)

`--all` implies `-y` (a sweep can't stall on prompts). Pre-loop validation runs
once; then `run_step()` repeats until no runnable step remains or a gate halts.

```
  _cmd_run_sweep()                  (plan_tool/cli/run_cmd.py:769)
     │
     ├─ PRE-LOOP GATES (all → rc=2 on violation):
     │     --step with --all? ........... mutually exclusive
     │     mode ≠ run? .................. review modes must use `verify-all`
     │     --max-steps < 1? ............. invalid ceiling
     │     --reconcile with --all? ...... audit is per-step
     │     --commit & tree dirty? ....... clean tree required   SKIP-if --dry-run
     │     iteration budget invalid? .... (same as single step)
     │
     └─ LOOP while a runnable step exists:
          ├─ steps_run ≥ --max-steps? ... stop, rc=0 (resume later)
          ├─ resolve next runnable ...... none → rc=0 ("sweep complete")
          ├─ run_step()  ◄── full gate gauntlet above
          │     ├─ pre-flight LauncherError → record halt in lessons:, rc=2
          │     ├─ --dry-run → rc=0 (first iteration's prompt only)
          │     └─ exit_code ≠ 0 → record halt in lessons:, return that rc  (gate halted the sweep)
          ├─ --archive & plan_completed? . move plan → archive/ + deregister (BEFORE the commit)
          ├─ --commit & step done? ...... git add -A + one commit per green step (captures the
          │     SKIP-if no --commit           archive move); commit fails → return its rc (left dirty)
          └─ --archive & plan_completed? . print "sweep complete", rc=0 (sweep done)
```

## The gates, one by one

### Always-on gates (every `--mode run`)

| Gate | When it runs | Blocking? | On failure |
|------|--------------|-----------|------------|
| **Step resolution** | always | yes | rc=2, nothing happens |
| **Pre-flight paths** | always, unless `--allow-missing-parent` | yes | rc=2; parent dir of a declared file is missing (likely a path typo or an undeclared new dir) |
| **Claude call** | always (skipped only by `--dry-run`) | yes | returns claude's rc (or rc=1 on `is_error`); plan not advanced |
| **`## Summary` present** | mutating mode | no — warn | contract reminder only |
| **Files modified** | mutating mode, if step declares files | yes | "no edits applied": none of the declared files changed (content-compared; an identical rewrite counts as unchanged); `status_note` written, rc=1, plan not advanced. Runs before the test-authoring gate so the failure is not misnamed as a missing test. `--accept` certifies a step whose files already hold the intended content (commit them first; accept needs a clean tree), but only when the plan has a `test_command` or the step has a `gate` (otherwise nothing certifies it). A directory or unreadable `files:` entry has no content digest and counts as modified |
| **`## Validation` present** | mutating mode | no — warn | "step didn't declare what it tested" |
| **`creates:` on disk** | mutating mode, if step has `creates:` | no — warn | "N creates entries missing"; step still advances |

The test-authoring gate combines newly dirty paths with added or modified
paths between the pre-call HEAD and the post-call HEAD, provided the latter
descends from the captured commit. Checkout/reset to unrelated or older history
supplies no committed evidence; amend/rebase can also lose that ancestry proof.
A backend may commit its tests before returning; those commits still provide
authorship evidence. Paths already dirty before the call remain excluded from
both sources. Unchanged committed tests and committed deletions do not count.
This is path-delta evidence, not author attribution: importing descendant
history can provide the same evidence as creating new commits during the call.
Without a readable pre-call HEAD (including an unborn repository), only the
existing working-tree evidence is available. In a non-git tree neither source
provides evidence, so an enforced step blocks rather than skipping the gate.
This gate checks file authorship, not coverage quality; test commands and
per-step gates still run afterward.

### Conditional gates (only when configured)

| Gate | Enabled by | Blocking? | On failure |
|------|------------|-----------|------------|
| **Plan-level `test_command`** | a `test_command:` in the plan frontmatter | yes | writes a `status_note` on the step, returns the command's rc, plan not advanced |
| **Per-step `gate:`** | a `gate:` list on the step (runs *after* `test_command`) | yes | first non-zero command halts; `status_note` names it; rc returned, plan not advanced |

Both gate commands shell out in the repo root with a 600 s timeout and surface
the tail of combined stdout/stderr in the failure banner. Per-step `gate:`
lives on the step it guards in the plan file — not in a shell script keyed by
plan slug. See [`PLAN_FORMAT.md`](../../../PLAN_FORMAT.md#field-semantics).

### Flag-driven behaviors (sweep-oriented)

| Flag | Effect | Notes |
|------|--------|-------|
| **`--dry-run`** | render + print prompt, exit 0 | skips the claude call and *all* gates past prompt render; no advancement |
| **`--allow-missing-parent`** | removes the pre-flight path gate | the only flag that *disables* a gate; use when a step legitimately creates a new dir |
| **`--commit`** | clean-tree precondition (rc=2 if dirty) + one commit per green step | works at both scopes — single-step (`--step N` / default "next") and the `--all` sweep; commit lands *after* the step's gates pass |
| **`--archive`** | move the plan to `archive/` and deregister the manifest the moment it goes N/N done | off by default; fires from the sweep's terminal step or a completing `--step N`; runs *before* the `--commit` commit so the move + manifest edit ride that commit (clean tree after) |
| **`--max-steps N`** | cap a sweep at N steps (resume-friendly) | sweep-only; `N < 1` → rc=2 |
| **`--accept`** | with `--step N`: certify a hand-fixed step and mark it done, no claude call | see [Accept a hand-fixed step](#accept-a-hand-fixed-step) |

### Accept a hand-fixed step

A step whose own test failed its gate stays `current`, and a re-run cannot
advance it once the fix is made by hand: the re-run makes no call that modifies
a test file, and a re-run that edits none of the step's declared files is
blocked as "no edits applied" before the test-authoring gate is reached.
`plan-tool run <slug> --step N
--accept` is the route after the hand fix is **committed**:

1. It refuses unless the tree is clean apart from the plan file and its lessons
   log (a failed gate leaves a `status_note` in the plan, so the plan being
   dirty is expected), unless the step is `committed` and either `current` or
   `pending` with a failed-gate `status_note` (a step run out of order), and for
   a plan with neither a `test_command` nor a step `gate` (nothing would
   certify it). It checks the same preconditions again on the re-read plan
   after the gates.
2. It runs `test_command`, then each step `gate`, exactly as the post-flight
   gauntlet does. On the first failure it prints the tail, writes nothing, and
   exits with that gate's rc.
3. When all pass it re-reads the plan, applies the ordinary done-and-advance
   (next step `current`, or the plan `completed`), clears `status_note`, appends
   the lessons entry a run would have, and writes the plan. With `--commit` it
   commits only the plan and lessons files (a gitignored lessons file is
   skipped), never build output the suite left behind; if the suite leaves
   untracked, non-ignored files, ignore or remove them before the next
   `run --commit`, which needs a clean tree.

Deliberately not run: the per-call test-authoring gate (its observable is a
per-call delta and there is no call), so `--accept` does not check that a test
file was authored; the green suite certifies. It makes no judgment on whether
the fix is right; the gate results are the binary fact. It writes no run log: a
run log records backend calls, and the plan edit and its commit are the record.
It cannot be combined with `--all`, `--reconcile`, `--dry-run`, `--archive`,
`--detail-grade`, or a review `--mode`; `--iterate` warns that it has no effect.

### Gates that *don't* run in audit modes

`--mode {check, optimize, document, test, security, lint}` and the
`--reconcile` code-audit path stop at step **[7]** above: they make the claude
call, print (and for reconcile, save + walk) findings, and return rc=0 **without
touching the plan**. None of the post-flight gates ([8]–[13]), the
`test_command` gate, the per-step `gate:`, advancement, `--commit`, or
`--archive` apply. An audit reporting CRITICAL findings still exits 0 — the
findings carry the verdict, not the rc (pass `--fail-on-findings` on the audit
verbs to gate CI on them).

## The merged-plan preflight

A merged plan pull request is the review that precedes `run`, so a `run` that
executes steps reads that fact from git before it executes anything. The check
is on by default and runs after the branch-awareness guard, before the run log
opens. Review modes, the `--reconcile` code audit, and `--dry-run` skip it.

| Situation | Result |
| --- | --- |
| The current branch is the default branch (`origin/HEAD`, else `origin/main`, else `origin/master`; for any other default, run `git remote set-head origin <branch>`) | refused, rc=2 |
| The plan file, or the detail file of any committed step, is not on `origin/<default>`; a committed step with no declared detail file counts as missing | refused, rc=2, listing up to eight paths |
| The plan or a detail file differs from `origin/<default>` beyond the `status` and `status_note` fields `run` writes | warning; the run proceeds |
| The repository has no `origin` remote | proceeds silently |
| `origin` has no resolvable default branch, the plan is outside the repository, or the plan does not parse | warning; the run proceeds |

Parked steps (`scope: deferred` or `wont_do`) need no detail file. The check
never fetches: after merging the plan, `git fetch` before running.

To skip it once, pass `--skip-merge-check`. To turn it off for a repository, set
`run.require_merged_plan` to `false` in `.plan-tool/config.json` (or the user
config), or set `PLAN_TOOL_REQUIRE_MERGED_PLAN=0`. Implementation:
`plan_tool/plan_merge_guard.py` (`check_plan_merged`) and
`plan_tool/cli/run_cmd.py` (`_preflight_merged_plan_guard`).

## Executing from the jira-grade bundle (`--detail-grade jira`)

`--detail-grade` selects which detail artifact grounds the implementation
prompt. It is an **input axis, deliberately separate from `--mode`**: the mode
stays `run` at every grade, so the lifecycle (mark-done, advance, the
test-authoring gate) and the `--all` sweep's mode allowlist are untouched. It is
**execution-only** — combining it with a review `--mode` or with `--reconcile`
is rejected up front (rc=2).

Under `jira`, `render_prompt` renders `prompts/run-jira.md` instead of
`prompts/run.md` and loads the step body from the `jira/` artifact
(`load_jira_grade_step_detail`) rather than `Step.detail`. The contract those
five sections must satisfy lives in
[`DETAIL_FORMAT.md`](../../../DETAIL_FORMAT.md#jira-grade--the-compact-contract).

**Two gate placements, both blocking, and neither is a warn** — one in the CLI
ahead of the gauntlet, one inside it:

```
  cmd_run / _cmd_run_sweep, before run_step()
     │
     ├─ JIRA-GRADE PREFLIGHT ............................. [BLOCK] rc=2, one message naming
     │     SKIP-if --detail-grade run                              every in-scope step whose
     │     runs BEFORE the run log opens, and under --dry-run      artifact is missing/off-contract
     │     scope: the step --step N resolves to, or every
     │            non-done step for --all
     v
  run_step()
     …
     ├─[4] render prompt
     │        JIRA-GRADE DEEP GATE (the prompt_build phase) [BLOCK] DetailGradeError re-raised as
     │        SKIP-if --detail-grade run                            LauncherError → rc=2; reached
     │                                                              before the invoker AND before
     │                                                              the --dry-run branch at [5]
```

Both route through `load_jira_grade_step_detail`, so the aggregated preflight
and the render-time gate cannot disagree about what a usable artifact is. The
preflight lands **before the run log opens**, so a broken bundle leaves no ghost
run dir; the deep gate sits **before** the `--dry-run` short-circuit at step
[5], so no grade can print a prompt built from an artifact it never validated.

Scope note: the preflight checks the steps this invocation would actually
execute — at or inside the bundle-coverage rule the export and audit apply — so
`run` never rejects a bundle they accept. An explicitly requested `done` step is
still checked (a step with no body cannot execute) but reported as an execution
problem, since coverage exempts `done` steps.

**The permissive missing-detail helpers are skipped**, not merely quieter: the
run-grade warn-and-confirm path reads `Step.detail` and recommends authoring it,
which is both the wrong check and the wrong shape — warn-and-proceed is exactly
the silent fallback this grade forbids. The hard preflight replaces it at both
scopes.

**The grade travels with the run.** It lands in the run log's `flags` as
`detail_grade` and in the resume command `_build_run_resume_command` prints, so
a rate-limit stop resumes at the same grade instead of silently reverting to
run-grade bodies.

## Why the ordering matters

1. **Pre-flight before the claude call** — a path typo is caught for free,
   before spending a claude invocation on a step that can't land cleanly.
2. **Gates after the claude call, before advancement** — `test_command` then
   per-step `gate:` run on the *post-edit* tree, so a green gate certifies the
   step's actual output. A failing gate leaves the step in its current status
   with a `status_note`, so a re-run resumes exactly there.
3. **`--commit` after gates pass** — the per-step commit captures a state that
   already cleared every blocking gate, so any later failure leaves precisely
   one step's work dirty (`git reset` to recover).
4. **`--archive` before `--commit`** — on the completing step the plan move +
   manifest deregister run first, so the green commit's `git add -A` captures
   them in one commit. The tree is clean afterward, so a follow-up `--commit`
   run isn't blocked by the clean-tree precheck. (A failed commit still leaves
   the move dirty for `git reset` recovery, same as the step's edits.)
5. **Sweep halts self-record** — a run failure or a refused gate appends
   `- <ts> step N halt (sweep): <reason>` to the plan's `lessons:` file, so the
   halt is recorded next to the plan it guards.

## After the plan completes — the two-loop verification tail

A green final step flips the plan to `completed`, but "every step ran" is not
"the code fully and correctly covers the plan." Once the last step lands (and is
committed — see the `--commit` gate above), drive two convergence loops before
calling the work done:

1. **Plan-canonical code reconciliation** — `plan-tool reconcile-code <name>
   --all` treats the plan as canonical and lands the edits the code still needs
   to *fully cover* it. The sweep includes `done` steps and skips only explicit
   `non-code` steps. It has no built-in `--iterate`, so re-run the full sweep
   until the real per-step audits report no remaining drift; `--dry-run` only
   renders prompts and reports no drift.
2. **Code review** — a `/code-review` pass, fixing what it finds and re-reviewing
   each round until it converges (no new findings).

Loop **(1)** is a plan-tool command; loop **(2)** `/code-review` is a **Claude
Code session activity, not a plan-tool surface** — it belongs to the driving
session (see `CLAUDE.md`), which is why the tool's own `Next steps:` output only
ever suggests `plan-tool …` commands and never a session activity like
`/code-review`. Correctness = sound + no bugs/edge-cases missed;
completeness = every call site, case, doc, and test the plan implied is covered,
and the code fully covers the plan. If any loop won't converge (a finding keeps
re-surfacing, or a fix needs structural rework), stop and file a `BACKLOG.md` /
`BUG_BACKLOG.md` entry naming the issue rather than looping indefinitely.

## Rate-limit / transient recovery seam

Both places that shell out to a backend — `shell.claude_invoke` (batch) and
`launcher.shell_invoker` (streaming, via `run`) — spawn through the same
shared Popen supervisor, `backend_runner.run_streaming_once`, and share one
ordinary-short-rate-limit 429-detect / wait-or-switch / transient-backoff
recovery state machine on top of it. That control flow lives **once** in `plan_tool/rate_limit_loop.py`
(`run_with_rate_limit_recovery`), a **stdlib-only leaf** with no first-party
import, so a fix to one caller can't silently diverge from the other
(BACKLOG #101).

**The shared runner.** `run_streaming_once` owns one Popen call end to end:
NDJSON-parsing stdout/stderr pump threads, a heartbeat daemon that emits a
progress signal roughly every 20s and a stall marker past ~300s of silence,
and a safety-net kill (SIGTERM, then SIGKILL after a grace window) once
silence crosses ~900s — closing the previously-silent window where a wedged
child pinned `plan-tool` indefinitely with no observable signal. Every ending
resolves to exactly one member of the closed `TerminationReason` vocabulary
(`backend_runner.py`) — completed, a configured-timeout or silence-timeout
kill, an operator interrupt, a spawn failure, a nonzero exit, or an
unclassified exception — readable via `get_last_termination_reason()`.
`claude_invoke`'s call additionally bounds total elapsed time
(`enforce_configured_timeout=True`, honoring
`PLAN_TOOL_CLAUDE_TIMEOUT`/`scoped_claude_timeout`); `run`'s call sites pass
neither kwarg and stay exempt from that timeout — the silence kill above is
the only bound they get.

**The observer contract.** A batch call builds a full `RunnerObserver`
(`shell.py`'s `_ClaudeInvokeRunnerObserver`, satisfying the Protocol in
`run_log.py`) around whatever `RunLogWriter` is bound, so it records the same
spawn / stream-event / progress / stall / termination signal `run` already
recorded, plus a `run_interrupted` event on a Ctrl-C caught out of
`proc.wait()`. `run`'s call sites still pass a bare `RunLogWriter` (or
`None`); the runner's own internal fallback gives a bare writer
`backend_spawn`/`backend_termination` for free but not `run_interrupted`.
Every observer call is individually swallowed (`_safe_observer_call`) so a
bad observer can't kill the pump/heartbeat threads or suppress the silence
kill.

**Recovery-wait visibility.** The `wait`/`sleep` seams the recovery loop calls
between a rate-limit or transient retry — built by
`claude_errors.make_backend_recovery_wait_seam` /
`make_backend_recovery_sleep_seam` — each emit one `backend_recovery_wait`
event before the wait/sleep blocks, and one `run_interrupted` event if a
Ctrl-C cuts it short. This closes the between-attempt window that previously
left no run-log trace at all.

**Tool-input-summary redaction.** A `-v`-verbosity `tool_use` line's
`tool_input_summary` redacts known secret shapes (`Authorization:`/`Bearer
`-carried tokens, provider-prefixed tokens, any other 20+-character
mixed-character-class run) to `[REDACTED]` before truncating, so a batch or
streaming call watched live can't leak a credential embedded in a tool
argument. `plan_tool/backend.py`'s `_redact_secrets` is the one pattern
definition, called from `_summarize_tool_input` (claude, and cursor's
claude-shaped blocks) and from `_codex_tool_use_summary` /
`_cursor_tool_use_summary` (codex's and cursor's own native tool-call event
producers) alike.

**Inject-don't-unify.** The loop owns only the shared control flow (the one-shot
rate-limit guard, the SWITCH / ASK / wait fork, transient exponential backoff,
honoring the wait's RETRY/STOP result). Every caller-specific concern is passed
in as a seam, so the leaf never touches a first-party type:

| Seam (kwarg)          | What the caller injects                                             | shell ↔ launcher difference |
|-----------------------|--------------------------------------------------------------------|-----------------------------|
| `run_once(attempt)`   | one attempt; opaque return read only by `classify`. Owns the per-attempt run-log / prompt-budget emit — the loop emits none | both spawn via `run_streaming_once`; shell passes a full `RunnerObserver` plus a configured elapsed-time bound, launcher passes a bare `RunLogWriter`/`None` and no elapsed-time bound |
| `classify(outcome)`   | → `AttemptClassification` (maps `ClaudeFailureKind` onto the neutral `AttemptCategory`) | same logic, different outcome tuple |
| `notify(msg, kind=)`  | user-facing progress line                                          | notifier object vs plain print |
| `select_backend(name)`| scope the fallback backend for this invoke                         | same |
| `ask_action()`        | interactive ASK menu → neutral `RecoveryAction`                    | shell passes the active notifier; launcher takes none |
| `can_prompt()` / `prompt_lock` | TTY check, the prompt lock                                    | same |
| `wait()` / `sleep()`  | reset-epoch wait / transient backoff sleep, each wrapped for `backend_recovery_wait`/`run_interrupted` observability | same wrapper (`claude_errors.make_backend_recovery_wait_seam`/`make_backend_recovery_sleep_seam`); differ only in the `writer`/`backend_name` accessors each caller binds |
| `on_nonsuccess(outcome, failure, will_retry, recovery_reinvoke_predicted)` | optional post-attempt surface: shell emits the missed-rate-limit canary + raw nonzero-exit line; both callers record a Cursor monthly-plan-quota near miss only when `will_retry` is false | `will_retry` is true only when the loop will re-invoke; the predictive fourth argument preserves shell's established raw-exit suppression when recovery later stops |
| `retry_guard(outcome)` | consulted **whenever the loop predicts a re-invoke** (both the transient backoff and the rate-limit wait/switch arms), before that backoff or wait; returns a `RetryDecision` (a `RetryPolicy` of `RETRY`/`STOP` plus a hint) — see `rate_limit_loop.py` for the exact contract | launcher wires the git-delta guard (STOP + partial-mutation hint if a retry would re-drive a dirty tree); shell wires the always-retry constant `ALWAYS_RETRY` |

**Terminal-on-partial-mutation.** On the streaming `run` path, a transient *or*
rate-limit failure whose aborted turn left uncommitted tracked (or untracked
non-ignored) edits is now returned as a **terminal** failure with an actionable
hint, instead of re-driving the same prompt over the partial tree — so a
double-apply can't corrupt the committed diff. Gitignored writes don't
false-trigger (git porcelain omits them). This is **response A only**: refusing
the retry turns some previously-recovered transients into surfaced failures —
the deliberate correctness-over-resilience trade. The resilience-restoring
follow-up (response B, snapshot-restore-then-retry) is tracked in `BACKLOG.md`.
Operator recovery for the terminal surface is in `RUNBOOK.md` (Recovery: common
failures).

**Neutral vocabulary.** The loop speaks `AttemptCategory` (SUCCESS / RATE_LIMIT /
TRANSIENT / TERMINAL) and `RecoveryAction` (WAIT / ASK / SWITCH / STOP), both
defined in the leaf. `ASK` is a *policy* value only — the interactive menu always
returns WAIT / SWITCH / STOP — and it is what keeps `wait` non-interactive: only
`ASK` opens the menu, and only when a TTY is present (otherwise it waits).
The first-party `ClaudeFailureKind` / `OnRateLimitAction` enums are
mapped onto them by `KIND_TO_CATEGORY` / `ACTION_TO_RECOVERY`, defined **once** in
`claude_errors.py` (the enums' owning module, which can import the stdlib-only leaf
without a cycle) and imported by both callers — so the mapping, like the loop, has
a single source of truth.

**Terminal plan quota.** The confirmed Cursor monthly plan-quota classifier is
mapped by `plan_tool/claude_errors.py:KIND_TO_CATEGORY` to
`AttemptCategory.TERMINAL`. It performs one failed attempt and enters none of
the wait, switch, prompt, backoff, or retry-guard seams. The provider-specific
detector stays above this neutral leaf; `run_with_rate_limit_recovery` neither
recognizes a provider nor owns a plan-quota policy.

## Raw backend stream log

Every backend call appends its raw stdout lines, verbatim and live, to
`.plan-tool/runs/<slug>/<run_id>.streams/claude-stream.<seq>.<phase>.a<attempt>.ndjson`
(`seq` is a per-process call counter, so calls in one run never share a
file). `tail -f` follows a running call.

- **Unredacted.** The file holds whatever the backend emitted. The directory
  carries its own `.gitignore` (`*`), so `run --commit`'s `git add -A` cannot
  stage it. There is no size cap and nothing prunes automatically;
  `plan-tool runs clear` (`--all`, `<slug>`, or `--older-than <DURATION>`)
  removes `<run_id>.streams/` directories by their newest file's age
  (`run_log.prune_stream_logs`). Each call's `backend_spawn` event names its
  file in `stream_log`.
- **Console.** The default and `-v` modes never print raw JSON. `--debug` prints
  the log's path, and falls back to raw stdout only when the log cannot be
  opened.
- **Not written** for calls that suppress content output (structural callers
  whose redaction is not ready).
- **Run log vs stream log.** The `<run_id>.jsonl` run log holds parsed,
  size-capped events; the stream log is the only place the full payload lives.

## Source map

| Concern                         | File                                                              |
|---------------------------------|------------------------------------------------------------------|
| Ordinary rate-limit / transient recovery loop | `plan_tool/rate_limit_loop.py` (`run_with_rate_limit_recovery`); maps in `plan_tool/claude_errors.py` (`KIND_TO_CATEGORY`, `ACTION_TO_RECOVERY`) |
| Terminal Cursor plan quota and audit-local stop | `plan_tool/claude_errors.py` (`ClaudeFailureKind.PLAN_QUOTA`, `KIND_TO_CATEGORY`); `plan_tool/review.py` (`audit_plan_until_stable`) |
| Shared Popen supervisor + termination vocabulary | `plan_tool/backend_runner.py` (`run_streaming_once`, `TerminationReason`, `get_last_termination_reason`, `_safe_observer_call`) |
| Batch-caller configured elapsed-time bound | `plan_tool/shell.py` (`scoped_claude_timeout`, `PLAN_TOOL_CLAUDE_TIMEOUT`) |
| Batch-caller observer contract  | `plan_tool/run_log.py` (`RunnerObserver`, `RunLogWriter`); adapted in `plan_tool/shell.py` (`_ClaudeInvokeRunnerObserver`) |
| Recovery-wait / interrupt events on the wait/sleep seams | `plan_tool/claude_errors.py` (`make_backend_recovery_wait_seam`, `make_backend_recovery_sleep_seam`) |
| Tool-input-summary redaction    | `plan_tool/backend.py` (`_redact_secrets`, `_summarize_tool_input`, `_codex_tool_use_summary`, `_cursor_tool_use_summary`) |
| Single-step dispatch + reporting| `plan_tool/cli/run_cmd.py` (`cmd_run`)                            |
| Sweep loop + commit/archive     | `plan_tool/cli/run_cmd.py` (`_cmd_run_sweep`, `_commit_green_step`, `_archive_on_completion`) |
| Core step execution + gates     | `plan_tool/launcher.py` (`run_step`)                             |
| Pre-flight path check           | `plan_tool/launcher.py` (`preflight_step_paths`)                 |
| Detail-grade selection + rejects| `plan_tool/cli/run_cmd.py` (`_detail_grade`, `_reject_detail_grade_conflicts`) |
| Jira-grade preflight (aggregated)| `plan_tool/cli/run_cmd.py` (`_preflight_jira_grade_details`)    |
| Jira-grade render gate + template| `plan_tool/renderer.py` (`render_prompt`, `load_jira_grade_step_detail`, `DetailGradeError`), `plan_tool/prompts/run-jira.md` |
| Jira-grade section contract     | `plan_tool/jira_grade.py`; schema in [`../DETAIL_FORMAT.md`](../../../DETAIL_FORMAT.md#jira-grade--the-compact-contract) |
| Test / per-step gate runner     | `plan_tool/launcher.py` (`_run_test_gate`)                       |
| Step resolution + advancement   | `plan_tool/launcher.py` (`resolve_step`, `mark_done_and_advance`, `_persist_step_completion`) |
| Findings verdict (audit modes)  | `plan_tool/launcher.py` (`summarize_findings`, `format_findings_verdict`) |
| Per-step `gate:` / `test_command` schema | `PLAN_FORMAT.md` (field semantics)                       |
| Gated-sweep operator walkthrough| [`../RUNBOOK.md`](../../../RUNBOOK.md) (Gated sweep: `run --all --commit`) |
