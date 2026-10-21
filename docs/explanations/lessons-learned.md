# Lessons learned: plan-tool iteration feature

Hard-won judgment from five sessions of building, self-testing, and
bug-fixing the iteration loop feature (sessions 1-2 built the core;
session 3 closed 6 queued tasks plus shipped concept-completeness,
the pytest integration marker, plan-creation testing guidance, the
auto_reconcile module, and stale-lockfile auto-recovery; session 4
closed #29 SIGINT-safe release + #27 rollup partition plus shipped
the change-collision sidecar and impact-weighted apply triage;
session 5 closed #14 per-finding scope guard + #14a per-finding
drift halts, refactoring ``_iterate_reconcile_loop``'s
in-walk drift handling from iteration-boundary to per-finding
granularity).
19 numbered lessons span the design space below; the
sharp-edges table at the bottom is the quick-reference for
"have we already seen this failure mode?" Read this before
extending the iteration work — most of these were rediscovered
the hard way during the session that surfaced them.

The per-repo iteration lockfile mutex and its SIGINT-safe-release
machinery were later removed (the "Remove Iteration Lock" plan); the
session-by-session build history below still records what was built
then, but the surviving in-loop protection is content-hash **drift
detection** in `plan_tool/drift_detection.py`. Recover detected drift
by re-reconciling via `plan-tool detail --reconcile`.

---

## Lesson 1: Procedural completeness ≠ conceptual completeness

**The trap:** "I shipped everything in the task description, mark it
done."

**Why it matters:** Task descriptions capture intent, not always
mechanism. A task can have every checklist item completed while
leaving the underlying problem only partially solved. Example: task
#13 (lockfile + drift guard) shipped detection but not prevention —
the original race condition was *detected* not *prevented*.

**What to do instead:**

1. After implementing, **re-read the original motivation** (not just
   the bullet list).
2. **Ask: does the shipped code actually solve the problem that
   motivated the task?**
3. If only partially, **say so explicitly** when marking complete and
   queue follow-ups for the gap.

The user pushed back on premature "done" twice during the session and
was right both times. Plan to be pushed back on at least once per task.

---

## Lesson 2: Token preservation > strict spec integrity

**The trap:** "When drift is detected mid-iteration, revert the
apply_finding to keep the spec clean."

**Why it matters:** Claude calls cost real money and real time
(10–15 min for a long apply). Reverting throws away that spend. The
final design for task #30 changed FROM "halt + revert" TO "halt + keep
output + flag for review." Token preservation wins.

**What to do instead:**

- Before invoking claude, check whether the call is likely to be
  wasted (drift detected, scope check failed, etc.). **Fail fast,
  before spending tokens.**
- After invoking claude, if the result is suspect, **keep the output
  and flag it** rather than reverting. The user reviews via `git diff`;
  if the apply was bad, they reject it; if it was salvageable, they
  keep parts.
- Never auto-revert claude's work unless the work itself failed
  (e.g., the verdict was BLOCKED or the exit was non-zero).

This applies broadly: scope-guard's revert-on-out-of-scope (#13's
sibling concern) is borderline — it reverts to keep scope clean, which
costs the apply's tokens. Worth revisiting in a future pass.

---

## Lesson 3: The plan is canonical (don't auto-rewrite it)

**The trap:** "Reconcile found drift between spec and code; let me
update the spec to match the code."

**Why it matters:** Over many iterations, this turns the plan from
"specification of what should be built" into "documentation of what
got built." Intent is lost. Mistakes in the initial implementation
become permanent.

**What to do instead (task #22's philosophy):**

- Default direction is **code-update** ("the code is wrong, fix it to
  match the plan").
- Plan-update is **privileged** — granted only when the code's
  divergence fulfills the plan's stated intent AND improves on the
  spec along a named, allow-listed dimension: `efficiency`,
  `alignment` (with repo/application conventions), `robustness` /
  `less-brittle`, `simplicity`, `testability`.
- Future improvement categories require a **code change** to
  allow-list (prevents the model from inventing rationalizations).
- Every finding's resolution carries an explicit `Direction:` and
  `Justification:` (the `## Decision` block) so the audit trail is
  human-reviewable.

The implementation of this lives in (or is being landed in) the
intent-preserving-reconcile plan. The code shape has partial wiring
already — `cmd_completeness` passes `allowed_justifications` to
`apply_finding`, and `args.strict_intent` is referenced.

---

## Lesson 4: Reconcile and apply have different scope semantics

**The trap:** "Tell reconcile to stay in scope so apply doesn't have
to deal with out-of-scope findings."

**Why it matters:** Reconcile (finding generation) wants to see the
WHOLE picture so it can surface cross-cutting findings ("step 2's code
conflicts with step 5's interface"). Apply (edit landing) needs to
respect scope so it doesn't wander.

The user caught this when I added a "prefer in-scope findings"
directive to the reconcile prompt. The right fix: keep reconcile
holistic, restrict apply.

**What to do instead:**

- **Reconcile prompt:** holistic. Surface cross-cutting findings even
  when the fix lives outside `step.files`. Phrase the scope-guard
  presence as **informational** ("the guard will classify edits at
  apply time"), not as a constraint on what findings to raise.
- **Apply prompt:** restricted. Explicitly forbid edits outside
  plan/detail files. The scope guard catches violations.
- **Rollup:** distinguishes in-scope from cross-cutting findings so
  the cross-cutting value is visible to humans (task #27).

> "A holistic plan-level finding the audit didn't surface is strictly
> worse than one the guard has to classify."

---

## Lesson 5: Symbolic anchors > line numbers in citations

**The trap:** "Cite the bug with `cli.py:1820` so the user can find
it."

**Why it matters:** Line numbers drift on every commit. The
`iterative-correctness-completeness-passes` self-test produced ~30
findings about `cli.py:NNNN` drift across its 100+ apply calls — pure
churn, no value.

**What to do instead:**

- Cite by **symbolic anchor**: file path + function/class/section/
  symbol name. E.g., `cli.py:cmd_completeness` or `review.py:
  BLOCKING_SEVERITIES constant`.
- Line numbers only as **secondary disambiguator** when a symbol
  genuinely appears more than once in a file.
- Fix this at the **authoring** prompt (`detail.md`) too, not just
  the **audit** prompts (`reconcile.md`, `check.md`, etc.) — the
  authoring prompt is what teaches the model to embed line numbers in
  the first place.

Task #12 landed this across 6 prompt templates. Future prompt edits
should preserve the convention.

---

## Lesson 6: Don't edit source while iteration is running

**The trap:** "I'll just fix this little thing in cli.py while the
iteration loop processes the next finding…"

**Why it matters:** The iteration loop reads the live filesystem each
round. Your in-flight edit becomes part of the next round's reconcile
input. Reconcile reasonably flags drift between the (now-edited) code
and the spec. apply_finding mutates the spec to match your edit. You
just drove a spec change you didn't intend.

This is exactly the race condition that motivated task #13.

**What to do instead:**

- **Don't edit plan-tool source while `--iterate` runs.** Period. If
  you must, kill the iteration first and restart.
- Content-hash drift detection makes this auditable, but doesn't
  prevent it. (Task #13 originally paired that detection with a
  lockfile mutex; the mutex is removed — drift detection is the
  survivor.) Task #30's mid-iteration drift halt makes it louder.
  Task #33 extends that beyond cmd_completeness.
- If you spot drift findings about line-number anchors after running
  reconcile, suspect this. The drift warning's stderr output will name
  the files.

---

## Lesson 7: Test the WIRING, not just the helper

**The trap:** "I wrote a unit test for `compute_drift_watched_paths`;
that proves the drift check works correctly."

**Why it matters:** The helper can be perfectly correct while the
call sites pass the wrong argument. The integration is where bugs
live. Example: `compute_in_scope_paths` returns the full set; if a
caller forgot to use `compute_drift_watched_paths`, the false-positive
drift warning fires again, and the unit test on the helper is silent.

**What to do instead:**

- For each public helper, **also write an integration test** that
  exercises the real call site through the CLI surface.
- For helpers that exist to AVOID a class of bug (like
  `compute_drift_watched_paths` avoiding false-positive drift),
  **add a regression test that simulates the bug** and asserts the
  helper is called.
- Don't rely on `grep` audits across the call sites — they catch
  imports but not "did the right argument get passed."

---

## Lesson 8: `--iterate` refines, it does not generate

**Principle:** `--iterate` runs correctness and completeness
refinement passes on a subcommand's output. The base subcommand
(without `--iterate`) is responsible for producing complete,
valid output. Iteration is not a substitute for foundational
content generation.

**Applies to:** Every plan-tool subcommand that supports
`--iterate` — `create`, `detail`, `completeness-audit`, `run`,
`review-walk`, `verify`.

**What this means in practice:**

- If `create` produces `_(TODO)_` placeholders, fix `create`. Do
  not rely on `--iterate` to fill them.
- If `detail` produces an empty section, fix `detail`. Same
  rule.
- `--no-iterate` skips refinement; it is not a workaround for
  missing base output.

Empty or stub output from the base path is a base-path bug —
treat it as such.

---

## Lesson 9: Body-section findings need content shape

**The trap:** "completeness --iterate flagged 8 placeholder sections
but claude refused to fill them, saying 'too vague to act on.'"

**Why it matters:** A finding like "`## Risks` body is a `_(TODO)_`
placeholder" gives claude no target. It correctly refuses (intent-
preserving!) because guessing content would be confabulation. 8 of 11
applies during bug #24 verification refused with this exact reason.

Now fixed (task #25): `PLAN_BODY_SECTION_SHAPES` dict in `create.py`
embeds a per-section content shape recommendation into the finding
body. apply_finding now has something concrete to act on.

**What to do instead:**

- When adding a new completeness primitive that flags "section X is
  empty", **also provide a content-shape recommendation** for X.
- Generalize: any finding that says "field Y is missing" should
  describe what Y looks like when present.

---

## Lesson 10: The deadline-budget needs debounce, not wall-clock

**The trap:** "Set `budget_seconds=300` so the iteration can't run
forever."

**Why it matters:** A single `apply_finding` call can take 10–15
minutes. If `budget_seconds` is wall-clock from loop start, the
deadline trips after iteration 2 even though work is still progressing.

The original implementation hit this — self-test steps 1–3 all halted
at `deadline_exceeded` after just 2 rounds.

**What to do instead (already landed):**

- `budget_seconds` is **idle time**, not wall-clock total. The
  `ConvergenceState` tracks `last_activity_at` and `should_continue`
  checks against that, not `started_at`.
- Callers call `touch(state)` after each productive operation
  (apply_finding return, walk completion, etc.) to refresh the timer.
- `record_iteration` auto-touches, so even callers that forget to
  call `touch` still get debouncing at iteration boundaries.

---

## Lesson 11: Run-log line cap is non-obvious

**The trap:** "`plan-tool create --from '<very long description>'`
crashed with `RunLogLineTooLarge: event line is 5624 bytes (cap
4096)`."

**Why it matters:** The 4096-byte cap is intentional — POSIX
`PIPE_BUF` for write atomicity under concurrent appenders. You can't
just raise it without losing the atomicity guarantee.

Now fixed (bug #23): per-string truncation with elision marker. Any
single string field > 1024 chars is truncated to ~1000 + `…<elided N
chars>` marker.

**What to do instead:**

- When adding a new event type that carries user-supplied strings,
  trust the truncation to handle it. Long strings get the elision
  marker; pathological payloads with many medium strings still raise.
- If you find yourself wanting to raise `_MAX_LINE_BYTES`, **don't.**
  Audit what's pushing the size up; it's probably a fixable shape
  issue.

---

## Lesson 12: The convergence module is intentionally narrow

**The trap:** "Let me add a 'run_iteration_loop' higher-order driver
to convergence.py so callers can just call one function."

**Why it matters:** Each caller (`cmd_create`, `cmd_detail`,
`cmd_run`, `cmd_completeness`) has a different per-iteration body
shape: regenerate steps JSON, re-render one detail body, apply-finding
on each open finding. A unified driver would require a
discriminated-union body type that's worse than four thin per-caller
loops.

**What to do instead:**

- `convergence.py` stays a **pure-logic primitive**:
  `IterativeBudget`, `ConvergenceState`, `should_continue`,
  `record_iteration`, `touch`, `is_blocking`, `BLOCKING_SEVERITIES`.
- Callers wrap their per-iteration body around these primitives. The
  while-loop shape is duplicated 4 times; this is **acceptable
  duplication**.
- Don't add first-party imports to `convergence.py` — keep it
  importable from any caller without risk of load-order cycles.

Same rule applies to `checkpoint.py`, `drift_detection.py`,
`scope_guard.py` (which only imports `schema` for typing).

---

## Lesson 13: Audit beats observe — structured findings > raw signals

**The trap:** "Drift detected on `cli.py`. Halting." — sufficient.

**Why it matters:** A raw signal ("file X drifted") puts the analytic
burden on the user. They have to inspect the diff, compare against
the spec, decide what the implications are. The same machinery you
already have (reconcile) can do that work for them and present
structured findings.

This came up via the user's question "Do we need to add a
reconciliation of the file when drift is detected?" — yes. Whenever
the tool surfaces a raw signal that the user will need to follow up
on anyway, consider running the follow-up *for them* and presenting
structured output instead.

**What to do instead:**

- When the tool detects a state change worth flagging (drift,
  scope-creep, max_iterations exhausted with late HIGH findings,
  etc.), don't just emit "this happened." If a downstream analysis
  primitive exists (reconcile, completeness, validate), **run it on
  the affected scope and emit the findings inline.**
- Cost: one extra claude call (bounded to the affected target).
- Value: turns "warning + manual investigation" into "warning +
  structured findings the user can act on."

This is the design pattern behind task #34. Apply it broadly:
- max_iterations + late HIGH/CRITICAL → could also run a
  focused review of the unresolved findings, not just count them.
- Out-of-scope plan stub from scope guard → could reconcile each
  out-of-scope finding against the broader codebase to identify
  which other steps might own it.

The principle: **never make the user do work the tool could do for
them.**

---

## Lesson 14: The user's intuition is usually right; investigate before pushing back

The user surfaced two design issues during the session:
1. "Scope-aware reconcile may restrict holistic review" — was correct;
   I had to revert my scope-restrictive directive in `reconcile.md`.
2. "Rollback functionality concerns me in the lost tokens" — was
   correct; I refactored task #30 from revert-on-drift to keep-and-
   flag.

In both cases my initial instinct was to defend the design. In both
cases the user's concern surfaced a real architectural flaw.

**What to do instead:**

- Treat user feedback as a free design review. Don't defend; analyze.
- Specifically: when the user pushes back, **try to articulate the
  user's concern in your own words** before responding. If you can't
  steelman their position, you don't understand it yet.
- The questions I framed for the user during the session
  (AskUserQuestion calls) were one of the highest-leverage tools.
  Use them when the design decision genuinely has trade-offs.

---

## Lesson 15: Content hashes > mtime for drift detection

**The trap:** "I'll use ``os.stat(p).st_mtime`` to detect when a
file's been edited mid-iteration. Cheap, simple, idiomatic."

**Why it matters:** mtime advances on a lot of operations that
DON'T change content:

- IDE re-saves with no edit (some editors `os.utime` on every save)
- ``git checkout`` of a blob that matches HEAD's version
- ``touch`` for build-system cache invalidation
- Atomic-replace patterns from build tools (rename in identical
  content)

Each of these triggered a false-positive drift halt mid-iteration
under the legacy mtime check. The iteration aborted, the operator
got a noisy stderr warning, and the operator had to inspect git
diff to discover the false positive — wasted attention budget.

**What to do instead:** SHA-256 hash the content at acquire
time; re-hash at check time; compare. Cost is one streaming hash
per watched file per check call — typically a handful of small
files; the cost is well under a tenth of a second. The
``_compute_content_hash`` helper handles missing/unreadable files
(returns None → skip) and large files (streaming chunked read).

**Generalizable rule:** when "detect change to X" matters, hash X
directly. Use indirect proxies (mtime, size, inode number) only
when they're load-bearing — they have false-positive classes that
the operator pays attention budget to resolve.

---

## Lesson 16: Factor shared logic into a new module BEFORE rolling out

**The trap:** "I implemented X as a private helper in cli.py. Time
to extend it to create.py and detail.py — I'll just import it from
cli."

**Why it matters:** create.py and detail.py shouldn't depend on
cli.py. cli.py is the top of the dependency tree (it imports
everything); making lower modules depend on it creates load-order
cycles and breaks the project's "dependency graph is a tree"
invariant.

**Example from session 3 (#34 auto-reconcile rollout):** the
initial #34 implementation lived as ``cli._run_auto_reconcile_on_drift``.
When the user asked to extend it to the other 3 iteration entry
points, the wrong move was to import from cli.py in create.py and
detail.py. The right move was to extract a new module
``plan_tool/auto_reconcile.py`` that depends on launcher, review,
and review_persistence (all lower than cli.py). cli.py's
``_run_auto_reconcile_on_drift`` became a thin re-export wrapper for
backward test compat.

**What to do instead:**

1. When a private helper in cli.py / create.py / detail.py becomes
   useful to a second iteration entry point, **extract the helper
   to a new module** before wiring the new caller.
2. The new module's dependencies should all be LOWER in the tree
   than any caller. If they aren't, the helper probably belongs
   higher in the tree (e.g., in cli.py with a different shape).
3. Keep the old private name as a thin re-export shim so existing
   tests don't break. Plan a follow-up to migrate them when
   convenient.

This pattern composes with **Lesson 12** ("convergence module is
intentionally narrow"): both prefer thin, low-dependency modules
that callers consume rather than fat module hierarchies.

---

## Lesson 17: Expose paired install/restore alongside any context-manager guard

**The trap:** "I'll add a context manager and wrap the iteration
body with ``with sigint_safe_release(...): ...``."

**Why it matters:** Python's idiomatic guard shape is the context
manager, and it's correct for new code. But retrofitting one around
a pre-existing function body forces re-indentation of every line
inside the ``with`` block. Each of plan-tool's four iteration entry
points has a 130–300 line iteration body; wrapping all four would
require ~540 lines of mechanical re-indentation across `create.py`,
`detail.py`, and `cli.py`. The mechanical risk (whitespace bugs,
hidden control-flow shifts in the diff) outweighs the small
ergonomic win of a single ``with`` line over paired
install/restore calls.

**Example from session 4 (#29 SIGINT-safe release):** the initial
implementation exposed only ``sigint_safe_release`` as a context
manager. Wiring it into the four entry points required re-indenting
the iteration bodies — quickly abandoned after the first attempt
introduced subtle indent bugs. The fix: refactor the helper to
expose `install_sigint_release_handler` + `restore_sigint_release_handler`
as paired functions (returning/accepting an opaque "saved state"
token), and keep `sigint_safe_release` as a `with`-wrapper around
them for new callers. Each iteration entry point then used
``_sigint_saved = install_sigint_release_handler(...)`` after
acquire and ``restore_sigint_release_handler(_sigint_saved)`` at
each exit path -- zero re-indentation, full SIGINT coverage. (This
paired-call shape was later superseded — see the Update below.)

**What to do instead:**

1. When you build a context-manager-style guard for plan-tool, ALSO
   expose paired install/restore (or equivalent enter/exit) functions
   alongside it. The context manager is a thin wrapper over the pair.
2. Document the paired API as the "use this when control flow
   doesn't lend itself to a single ``with`` block" form. (The four
   iteration entry points used it until the migration in the Update
   below; new callers use the `with`.)
3. Make the install function return an opaque "saved state" token
   that the restore function consumes. Use a sentinel (e.g.
   ``_SIGINT_NOT_INSTALLED``) for the "install was a no-op" case so
   restore can be called unconditionally.
4. When operations need to be idempotent for the paired form to be
   safe (e.g. lock release fires both from explicit cleanup AND
   from the SIGINT handler), build the idempotency into the
   primitive — see ``IterationLock.released`` as the
   reference pattern.

This pattern composes with **Lesson 16** ("Factor shared logic into
a new module BEFORE rolling out"): the paired API keeps the helper
self-contained inside one module rather than spreading its setup
across multiple call sites' indent levels.

**Update (later session): the re-indent risk was paid down, not
avoided forever.** The paired-call shape left a real gap — the calls
weren't wrapped in ``try/finally``, so a non-``KeyboardInterrupt``
exception escaping a loop body leaked both the lockfile and the
handler (the lockfile leak was the serious half for in-process
callers; #28 stale-lock recovery only saved dead-PID CLI runs). The
durable fix was *not* re-indenting four bodies by hand — it was
extracting the whole ``acquire + install + (finally) release +
restore`` lifecycle into a single context manager,
``drift_detection.iteration_session``, and migrating each entry point
to one ``with iteration_session(...) as lock:`` line. That gave the
``finally`` guarantee (no leak on any exit) without per-body
re-indentation, because the indented block is the *loop body the loop
already had*, not newly-nested code. So the refined lesson: when a
paired install/restore guard accumulates more than one or two call
sites, consolidate the entire lifecycle into one context manager and
migrate the sites — the open-coded paired form is an intermediate, not
a destination. The single-entry-shape invariant (every iteration entry
point goes through ``iteration_session``) is pinned by
``tests/test_drift_detection.py::TestIterationSessionIsTheOnlyEntryShape``.

**Superseded (Remove Iteration Lock).** The mutex, the lockfile, and
the entire SIGINT-safe-release machinery — ``install_sigint_release_handler``,
``restore_sigint_release_handler``, ``sigint_safe_release``, the
``_SIGINT_NOT_INSTALLED`` sentinel, and the ``IterationLock.released``
idempotency guard — are all deleted. The whole paired install/restore
narrative above is history: those symbols no longer exist.
``iteration_session`` survives in ``plan_tool/drift_detection.py`` as a
drift-only context manager (``snapshot → yield →
finally(emit_drift_warning(check_drift(lock)))``); its ``finally`` no
longer releases a lock or restores a handler — it only re-hashes the
watched paths and emits the live-edit drift warning on every exit.

---

## Lesson 18: Triage tokens by cost-vs-benefit, not by completeness

**The trap:** "The iteration loop should apply every finding claude
raises — that's what makes it converge."

**Why it matters:** Some findings just aren't worth the apply
cost. A typo nit in a 200-line file (low impact, low complexity)
is cheap; apply it. A cross-cutting rename across three files (medium
impact, high complexity) is expensive; skip-and-report unless the
operator explicitly wants it. The iteration loop should weigh
each apply, not blindly process every finding to "achieve
completeness." Otherwise the loop converges in name only — every
finding is applied, the spec is technically correct, but the token
budget is exhausted on low-value work.

**Example from session 4:** the apply triage shipped after the
user pointed out that the iteration loop's "apply everything"
behavior was a token-economy bug. The fix: ``Impact:`` and
``Complexity:`` tags emitted by claude in each finding's
``## Decision`` block, plus a ``should_apply_by_triage`` gate
that skips applies when ``complexity > impact``. Deferred findings
are reported on stderr + in the rollup so the operator decides
manually if the cost is worth the payoff.

**What to do instead:**

1. **Let the producer score the cost.** Claude (or whatever
   primitive generates findings) is in the best position to
   estimate impact + complexity at generation time. Bake the
   scoring into the prompt shape (here: two extra fields in the
   Decision block). Don't try to compute it heuristically after
   the fact — without the producer's reasoning, you only have
   severity, which is a different signal.
2. **Skip-and-report, don't drop.** Deferred findings get
   surfaced on stderr AND in the rollup so the operator has full
   visibility. The on-disk saved review carries the full set; the
   in-memory walk filters. This preserves the audit trail without
   wasting apply cost.
3. **Fail-open on missing signal.** Findings without the new tags
   (deterministic checks, legacy reconcile output, malformed
   claude responses) flow through to the apply path. The new
   feature must not regress legacy behavior — only enhance it.
4. **Short-circuit when only deferred remain.** If every finding
   is deferred, the next iteration would produce the same set
   again. Halt explicitly rather than letting the convergence
   loop's "marginal" detector catch it after one wasted token-
   spend.
5. **Provide a kill switch.** ``--no-triage`` opts back into
   "apply every finding" so operators doing a completeness sweep
   don't have to relax the prompt or override per-finding.

**Generalizable rule:** when an iteration loop's individual
operations are expensive (here: claude calls @ 10-15 min each),
give the loop a way to **NOT** do every operation. The "apply
every finding to converge" framing optimizes for spec correctness
but ignores the operator's token budget. Cost-aware iteration is
strictly more useful than completeness-only iteration.

---

## Lesson 19: Halt signals between cooperating loops belong on shared state, not exceptions

**The trap:** "The inner callback (``action_fn``) needs to stop the
outer loop (``walk_recommendations``). I'll raise a sentinel
exception and have the outer loop catch it."

**Why it matters:** If the outer loop already catches a *generic*
exception around the callback for a different reason (here:
``walk_recommendations`` catches ``Exception as exc`` to treat
``action_fn`` failures as "action failed; fall back to interactive
prompt"), the sentinel gets confused with the failure path. Result:
the loop doesn't halt; it falls back to interactive prompt mode
which, in a headless context, dead-locks on ``input()``.

**Example from session 5:** the per-finding drift halt needed
to break the walk after ``_dispatch_apply_finding`` detected drift.
Raising a ``WalkHalt`` exception would have hit
``_auto_apply``'s ``except Exception`` (line 348 of review_walk.py)
which clears ``state.yes_to_all`` and returns ``None`` -- the
walker then prompts interactively. Bad in headless ``-y`` mode.
The fix: extend ``WalkState`` with halt fields
(``halt_requested`` / ``halt_merged`` / ``halt_finding_id`` /
``halt_drifted``). action_fn writes; walker checks
``state.halt_requested`` after persisting each rec's annotation
and breaks. No exception path involved; no risk of conflating with
``action failed``.

**What to do instead:**

1. **Default to mutable shared state for halt signals.** When the
   outer loop's existing exception handling has its own semantics,
   raising for halt collides with those semantics. State fields
   carry intent unambiguously.
2. **Document the protocol on the state class.** The
   ``WalkState`` docstring spells out which side writes each field
   and when the other side reads. Without that, the next refactor
   forgets to check the flag or forgets to reset it between runs.
3. **Provide a reset helper.** ``WalkState.reset_halt()`` clears
   all halt fields together; the consumer (iteration body) calls
   it after handling a halt so subsequent passes start clean.
   Without the helper, callers cherry-pick which fields to clear
   and inevitably leave one behind.
4. **Exception channels are still fine for genuine failures.**
   ``LauncherError``, ``KeyboardInterrupt``, etc. still propagate
   normally; the rule applies specifically to "I want the outer
   loop to stop early but the work succeeded."

**Generalizable rule:** when a caller wants to interrupt a callee
that's running it in a loop, look at the callee's existing
exception handling. If exceptions are already overloaded with a
different meaning (failure recovery, fallback, retry), introduce a
*field* on the shared state instead of a new exception class. The
state-based protocol is also strictly easier to test (set the flag
in a fake action_fn; assert the walker breaks) than catching and
re-raising sentinel exceptions in tests.

---

## Lesson 20: Characterization tests pin actuals through public surfaces

**The trap:** "I'm writing tests to pin current behavior before a
refactor — I'll assert what the docs/help text promise, locate
internals by introspection, and match the prose I expect."

**Why it matters:** Three distinct failures of this shape halted the
gated cli-package-split / change-type executions, all caught by the
test gate at one-step blast radius:

1. **Pinning intent instead of actuals.** Tests asserted the
   documented `validate` contract (`INVALID:` verdict, exit 0/1)
   against an unparseable fixture — but unparseable plans are
   silently dropped by the locator (a real gap, now in
   BUG_BACKLOG.md). Characterization pins what the code *does*;
   divergence from documented intent means pin the actual AND file
   the bug — never assert the aspiration in a behavior-preserving
   plan.
2. **Introspecting internals.** Locating `main()`'s dispatch table
   via `__code__.co_consts` spelunking broke on CPython 3.13 and
   would have broken again when dispatch became registry-derived.
   Couple to the public contract (every subcommand resolves to a
   callable `cmd_*` attr) — the thing that survives the refactor is
   the surface, never the implementation shape.
3. **Over-pinning prose.** Asserting the literal substring
   "pass unchanged" failed against the contract term
   "pass-unchanged-after gate". Pin contract tokens and exit codes,
   not word sequences.

**Corollary for gated multi-step runs:** run the full suite green
*before* step 1 — the first milestone full-suite gate otherwise
bills pre-existing latent failures to whatever step it lands on
(session: a stale test_lessons expectation surfaced at step 7 of an
unrelated plan).

---

## Lesson 21: Plan audits converge by *grounding level* and *severity*, not to zero findings

**The trap:** "the audit still surfaces findings, so the plan isn't done —
keep reworking the plan body until it's clean."

**Why it matters:** A sufficiently complex plan has an **asymptotic conceptual
tail** — each conceptual-audit pass independently re-audits the whole plan, so
`COVERAGE UNCONFIRMED` ("still discovering at the pass cap") is the normal
steady state, not a failure. Worse, plan-body rework *introduces its own new
edge-case findings*, so finding-count never reaches zero by iterating at one
level. Observed on `parallel-plan-worktrees` (2026-06-22): 3 bare HIGHs → fixed
→ 2 *new* HIGHs → fixed → 0 HIGH + an 11-finding MEDIUM tail still discovering.

**What to do instead:**
- **Read the severity trend, not the count.** HIGH→0 across rounds = the design
  has converged; a persistent MEDIUM/INFO tail is implementation detail, not a
  blocker. Stop plan-body rework when HIGHs clear.
- **Escalate the grounding level instead of re-sampling one.** Bare-plan audit →
  `detail`-grounded audit → `run`/code each surface *their own* layer of real
  findings (design assumptions are unvalidated until grounded against code).
  Move to the next level rather than chasing the conceptual tail at the current
  one — the audit banner even says "re-audit after `plan-tool detail`."
- **Distinguish converging from stalled by *what recurs*.** *Different* findings
  each round + falling severity = converging (keep going / next level). The
  *same* finding recurring without progress means stop patching and consider
  `split` / `scope-out` / re-seed by judgment — `plan-tool convergence` reports
  loop health (`no-history` / `insufficient-history` / `converging`) plus
  newest-run advisories, not a spinning/`FORK_*` re-decompose verdict
  (region-trending retired with BACKLOG #251, 2026-08-08).

## Lesson 22: Per-step run gates are necessary, not sufficient — full-suite after every multi-step run

**The trap:** "`run --all` finished green, every step's gate passed — ship it."

**Why it matters:** A step's gate runs only that step's *declared* test file
(`enforce_step_tests`). A step can break **cross-module tests it doesn't
declare** and the run still reports all-green. Observed 2026-06-22: the escalate
run passed all 9 per-step gates but the full suite caught 3 regressions — incl.
a real bug where the run *mechanically mis-placed* a `@spawn_cwd_from_repo_root`
decorator off `apply_finding` onto a dataclass (the backend would've edited in
the wrong cwd), caught only by `test_bench`, which step 4 never declared.

**What to do instead:** always run the **full suite** (`uv run pytest tests/ -q`)
after a multi-step `run`, and a review pass — the per-step gates are a
fast-fail, not the acceptance check. Also regenerate the drift-guarded
CLI-reference + help-golden (a prompt/flag tweak in one step drifts guards a
later full run catches).

## Lesson 23: `completeness` is plan-centric; `reconcile` is code-centric — and the structural check belongs in both

**The distinction:** `completeness` asks *is the plan correct, complete, and
comprehensive on its own terms?* (plan-centric). `reconcile` asks *is the plan
up to date with the current state of the code?* (code-centric, plan focus).
Keep each in its lane — `reconcile`'s LLM review leaking into plan-internal
structure/file-allocation is where it emits false-positives (see BUG_BACKLOG).

**The shared piece:** the **structural-decomposition** check — does the plan
need a **re-seed**, a **merge** of existing steps, or a **split** of a step? —
belongs in *both*, grounded differently: `completeness` from plan internals
(over-packed/fragmented/mis-shaped); `reconcile` from **code state** — its
unique signal being *a collection of steps already partially implemented in the
code → merge/re-ground*. The remedies share one vocabulary already in the tree:
`split`→`granularity-split`/`plan-tool split`/the escalate-to-split bridge;
`merge`→`granularity-merge`/`plan-tool merge`; `re-seed`→the `convergence`
diagnostic's structural fork. Today only `completeness` runs it; giving
`reconcile` a code-grounded version is BACKLOG #67.

---

## Lesson 24: Before consolidating duplication, grep the markers and check the "acceptable duplication" ledger

**The trap:** "Five copies of this helper — obviously DRY it up into one
shared function." You extract, and either (a) you create an import cycle a
leaf was deliberately copy-pasting to avoid, or (b) you fuse genuinely-divergent
bodies behind a discriminated-union parameter that's worse than the copies.

**Why it matters:** This codebase makes duplication *self-flagging* and records
which copies are deliberate. Skipping that record means re-litigating decisions
the maintainers already made — and the answer is sometimes "leave it." Lesson 12
(convergence loop) and Lesson 16 (factor into a *new lower* module, never import
across the layer) are the two poles: some duplication is an extraction waiting
for its threshold; some is the permanent cost of a stdlib-only acyclic leaf.

**The recipe — run this pass before proposing any consolidation:**

1. **Grep the in-code extraction-threshold markers first.** They name the copy
   sites and state *when* to extract:
   `grep -rniE "duplication is the signal|until a (second|third|fourth) call site|standing .* item|inlined rather than imported|not minted here" plan_tool`.
   When a count crosses the stated threshold (e.g. `review_persistence.py`'s
   atomic-write "until a fourth call site appears" — now at four), it's a
   ready-made backlog item.
2. **Cross-check each hit against this file (the "acceptable duplication"
   ledger).** Lesson 12 marks the 4× convergence *driver* a trap and the
   while-loop shape acceptable; the leaf-isolation rule covers
   `convergence`/`checkpoint`/`drift_detection`/`scope_guard`/`telemetry`. If a
   lesson blesses the copy, stop — note it and move on.
3. **Classify each survivor: incidental vs. leaf-isolation cost.** *Incidental*
   (an atomic-write, a `[y/N]` gate, a timestamp) → extract. *Leaf-isolation
   cost* (a copy that exists so a stdlib-only leaf adds no first-party import) →
   the fix is a **new lower leaf** both can import (Lesson 16), never a
   cross-layer import.
4. **Prefer descriptor-or-new-leaf over a parameterized super-function.**
   `backend.py`'s `CliBackend` (one descriptor, N backends share its
   parsers/regexes) is the codebase's answer to "N near-clones of a
   parser/gate/classifier." Reach for a fat `if kind == …` only when the bodies
   truly converge.
5. **Land behind the existing drift guards.** `test_data_contract.py`,
   `test_capability_catalog.py`, `tests/cli/test_cli_reference.py`, and the
   backend fixture goldens make mechanical extractions verifiable
   (regenerate-and-diff, not eyeball). The autouse invoker gate in
   `tests/conftest.py` catches any extraction that accidentally spawns real
   Claude.

**Worked example (this session):** a consolidation sweep surfaced four copies of
`_atomic_write_text`, ~10 `[y/N]` confirm gates, four `utc_now_iso` clones, and a
4× convergence loop. Steps 1–2 separated the real wins — the leaf helpers
(BACKLOG #79) and the argparse parents (#80) — from a trap: the convergence
*driver*, which Lesson 12 already forbids.

**How that inventory held up when it was finally measured (2026-08-02).** Only
two of the four candidates above were real. The atomic-write copies were
genuine and shipped as `fileio.durable_write_text`; the argparse parents were
genuine (12 of 15 identical) and shipped. But the *"~10 confirm gates"* were
never duplication at all — **zero** of the eleven share an implementation; they
share an idiom, and two carry an injectable test seam the others lack. The four
`utc_now_iso` clones were identical and were still **withdrawn**, because a
fifth sibling had already diverged to a different wire format, proving they are
per-artifact choices rather than one utility. The lesson generalizes past this
sweep: an eyeballed duplication inventory is a hypothesis, and roughly half of
this one was wrong in the direction that breaks things. #81 was scoped down to the
*incidental* sub-blocks (drift guards, triage-halt, banner) only, leaving the
divergent per-iteration body duplicated as Lesson 12 prescribes.

**Tooling this pass:** BACKLOG #82 proposes formalizing the freeform threshold
markers into a structured, greppable annotation with a no-Claude threshold check
(fires when a stated call-site count crosses) plus a telemetry kind (#72) that
accumulates candidates over time — turning this manual recipe into a tool
surface. Its guardrails are this lesson's: feed `BACKLOG.md` (don't rot a
parallel store) and carry an "acknowledged-acceptable" suppression set so it
never relitigates Lesson 12's deliberate duplication.

---

## Lesson 25: Prefer cut over dead-defer — never ship a deliverable whose completion you can't land

**The trap:** a fix can't fully land this cycle, so you ship the
*primitive* now and defer its *wiring* — and, to look complete, you
state in the plan's Risks table that the thing is mitigated. Both
halves are brittle: the primitive is dead-on-arrival (no in-scope
consumer), and the "mitigation" is a claim no step delivers.

**Why it matters:** the `prompt-budget-advisory` plan (#95) did exactly
this — step 7 shipped `note_prompt_budget_advised()` while the only
caller-side wiring was deferred, and the Risks table claimed the
double-warn was suppressed. The re-audit then showed the deferred fix
was **unimplementable as scoped** (a per-invoke read-and-clear mark
can't suppress the audit's N-pass loop; the telemetry dedup it leaned
on had no per-invoke correlation id). The plan looked done and was
internally incoherent. The tool's own signals fired —
`detect_suppression_shape` (INFO) and `COVERAGE UNCONFIRMED` — but only
**advisorily and late** (the deep findings surfaced on a second,
un-budget-limited audit pass), so nothing blocked the brittle plan
before detail/execution.

**What to do instead:**
- Before deferring a fix, verify the deferred completion is actually
  **implementable given the shape the step commits to**. If it isn't,
  **cut the feature to a `BACKLOG.md` item** rather than ship a dead
  primitive (this is the plan-scope analog of the "re-decompose, don't
  keep patching" rule).
- **Never state a Risk mitigation a step doesn't deliver this cycle.**
  An accepted residual is fine — say it's accepted and point at the
  backlog item; do not dress it up as mitigated.
- A step whose deliverable **suppresses a quality gate** is almost
  always wrong (fix what trips the gate, not the gate). Treat
  `suppression-shape` as a stop sign, not a footnote.
- This whole failure class is deterministically detectable at plan
  altitude — see **BACKLOG #100** (claim-vs-delivery / dead-deliverable /
  elevate-suppression-shape gate), the intent-consistency complement to
  #66.

---

## Quick-reference: known sharp edges

| Edge | Mitigation |
|---|---|
| Long `--from` description → `RunLogLineTooLarge` | Fixed. Just works now. |
| `create --iterate` clobbers body fills | Fixed. Body fills survive. |
| Step statuses flipped to `done` during create | Fixed. Statuses preserved from on-disk. |
| Iteration lockfile leaks on Python exception | Removed: there is no lockfile to leak. The surviving in-loop protection is content-hash drift detection (`plan_tool/drift_detection.py`); recover detected drift via `plan-tool detail --reconcile`. |
| Ctrl-C during iteration leaks lockfile | Removed: no lockfile, no SIGINT-release handler. `iteration_session`'s `finally` runs `check_drift` + `emit_drift_warning` on every exit (including `KeyboardInterrupt`), emitting the re-reconcile hint. |
| Drift during apply leaves a half-merged plan/detail file the user must reconcile via `git diff` | Replaced (session 4) with `plan_tool/change_collision.py`'s sidecar + pause-for-merge flow. claude's edits land in `<stem>-change-collision<ext>` next to the original; the original is restored to its pre-apply state; the iteration loop pauses interactively so the user can merge with their preferred tool (`code --diff` / `vimdiff` / `meld`). Pressing Enter continues iteration against the merged state; the legacy halt path is the fallback for headless / declined / Ctrl-D. `--no-collision-sidecar` opts back into legacy keep-on-disk behavior. |
| Iteration loop applies every finding regardless of cost-vs-benefit, burning tokens on low-priority + high-complexity work | Fixed (session 4): impact-weighted triage. The reconcile prompt asks claude to score each finding's `Impact:` and `Complexity:`; `review.should_apply_by_triage` skips applies when `complexity > impact` (low+medium, low+high, medium+high). Deferred findings surface on stderr via `review.emit_triage_summary` AND in the decision rollup's `### Deferred by triage` section with `[DEFERRED: impact=X, complexity=Y]` suffix on each bullet. Findings without triage tags (deterministic checks, legacy reconcile output) flow through to apply (fail-open default). `--no-triage` disables the gate. Wired into all four iteration entry points; reconcile loop short-circuits when only deferred findings remain (avoids one wasted `run_step` call). |
| Drift detection fires only at release | Fixed in #30 for cmd_completeness; extended in #33 (session 3) to all 4 iteration entry points. |
| Drift fires on harmless mtime touches (IDE re-save, `git checkout` of unchanged content) | Fixed in #31 (session 3): content-hash drift detection via SHA-256. |
| Line-number citations drift between iterations | Fixed at the authoring + audit prompts. Future details should follow the symbolic-anchor convention. |
| Body placeholder findings refused by apply | Fixed. Content-shape recommendations embedded. Session 3 hardened the Testing + Acceptance criteria shapes with unit-first + concept-audit guidance. |
| Drift warning fires on apply_finding's own legitimate plan/detail edits | Fixed in #13's late round. `compute_drift_watched_paths` excludes plan+detail. |
| Concurrent iterations clobber `.plan-tool/` state | No lockfile guards this — don't overlap iteration runs on one repo. Content-hash drift detection (`plan_tool/drift_detection.py`) surfaces a live-edit collision after the fact; recover via `plan-tool detail --reconcile`. |
| Drift halts surface "drift on file X" with no path → step mapping | Fixed in #32 (session 3): drift + scope-guard warnings annotate each path with `(step N: title)` via `scope_guard.build_file_to_step_map`. |
| "Drift on file X" gives operator a raw signal with no action guidance | Fixed in #34 (session 3): auto-reconcile-on-drift runs `reconcile` against the owning step(s), saves findings, prints a `review-walk` pointer. Opt-out via `--no-auto-reconcile-on-drift`. |
| Procedural completeness ≠ conceptual completeness | Session 3 made this concrete: `check_concept_completeness` audits whether DONE-step code fulfills `## Acceptance criteria`. Wired into `cmd_completeness`. |
| Concept findings could drive plan-update under non-strict mode (weakening criteria) | Use `--strict-intent`. Test `TestCmdCompletenessConceptWiring::test_strict_intent_passes_empty_frozenset_to_concept_apply` pins this. |
| Default-ON costly behaviors (auto-reconcile, concept-check) make tests slow | Pass `auto_reconcile_on_drift=False` / `--no-auto-reconcile-on-drift` and mock `shell_review_invoker` when not exercising those paths. See TESTING.md for the mocking convention. |
| `completeness --iterate` may over-apply | Open question — task #19 investigates. Session 3's mixed-stream behavior (deterministic + concept) makes this less clear-cut; re-examine with fresh data. |
| Plan audit "still finds things" → keep reworking the body | Lesson 21: complex plans have an asymptotic conceptual tail (`COVERAGE UNCONFIRMED` is normal). Read the **severity trend** (HIGH→0 = converged; MEDIUM tail = detail-stage), and **escalate the grounding level** (bare→detail→run) rather than re-sampling one. Same finding recurring without progress = stalled (stop patching); converging = *different* findings + falling severity (`plan-tool convergence`'s region-trending `spinning` verdict was retired with BACKLOG #251, 2026-08-08 — read the severity trend by hand). |
| `run --all` green per-step → ship | Lesson 22: per-step gates run only each step's *declared* tests; a step can break cross-module tests it doesn't declare (escalate run mis-placed a decorator, caught only by full suite). Always full-suite + regenerate CLI-ref/help-golden after a multi-step run. |
| `reconcile` review opining on plan structure | Lesson 23 / BUG_BACKLOG: `reconcile` is code-centric (plan-vs-code currency); plan-internal structure is `completeness`'s lane. The shared structural-decomposition check (re-seed/merge/split) belongs in both, grounded differently — code-grounded reconcile version is BACKLOG #67. |
| `--iterate` is opt-in by default | User wants this flipped to opt-out — biggest remaining UX change. |
| "Five copies — obviously DRY it up" | Lesson 24: run the consolidation pass first. Grep the in-code threshold markers, cross-check this ledger (Lesson 12/16 may bless the copy), classify incidental-vs-leaf-cost, prefer a new lower leaf or descriptor over a cross-layer import or a parameterized super-function, land behind the drift guards. |
| Ship a primitive now, defer its wiring, and call it mitigated | Lesson 25: dead-on-arrival + a claim no step delivers. Verify the deferred fix is *implementable as scoped*; if not, **cut it to a backlog item** rather than ship a dead primitive. Never state a Risk mitigation a step doesn't deliver — an accepted residual is fine, say so and point at the backlog. `suppression-shape` is a stop sign. Deterministic gate proposed as BACKLOG #100. |
