# Plan seed: advisory chat in the interactive walk (ask, don't just steer)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/walk-advisory-chat-mode.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose
below and proposes a step decomposition; the author then runs
`plan-tool detail` per step.

---

## Guiding principle

**Let the operator *ask about* a recommendation, not only *steer* its
application.** Today the walk's only conversational key is
`(f)eedback`, and feedback is write-side: the text is recorded as the
rec's note **and** stashed on `state.pending_feedback` to steer the
*next apply* (`review_walk.py:709-720` → `review_actions.py:381-383` →
`apply_finding(operator_feedback=...)`). There is no read-side path: no
way to put a question to Claude — "would you recommend folding this into
the plan or doing it as a separate action?" — get a recommendation
back, discuss it, and *then* decide apply / skip / feedback. The
operator must commit to applying or skipping before they can consult.

Add a **`(c)hat`** mode: a bounded, multi-turn advisory exchange about
the current recommendation that **lands no edit and sets no steering by
default**, then returns the operator to the same status prompt. Asking
must be cheap, safe, and non-committal — the opposite of feedback's
"this changes the edit" contract.

## Where it lives (one loop, three commands)

The interactive loop is shared: `walk_recommendations()`
(`review_walk.py:321`) → the per-rec prompt `_prompt_for_annotation()`
(`review_walk.py:609`, menu at `:646-649`, dispatch `:650-739`). Adding
a key there lights it up for **every** caller at once —
`completeness-apply` (`cli/completeness_cmd.py:277`), `review`
(`cli/review_cmd.py:392/472/541`), and the reconcile walks
(`cli/reconcile.py:568/2061/2071`). Build it **once** in the shared
loop; do not fork three near-copies.

## The chat key — behavior

Add `c` / `chat` (alias `ask`) to the prompt string and dispatch
(`review_walk.py:646-739`), alongside the existing `a`/`s`/`f`/`r`/`aa`/
`q`/`?`. Check the alias table first: `d`/`done` are **already** apply
aliases and `n`/`note` are **already** feedback aliases — `c`/`chat`/
`ask` are free; don't reuse a taken letter.

On `c`:

1. Open a small REPL: prompt `  ask: `, read one line.
2. Invoke an injected **advisor** (see the seam below) with the current
   recommendation's context + the operator's question + the running
   chat transcript, and print the answer indented under the rec.
3. Loop for follow-ups, accumulating the transcript so each turn has the
   prior exchange. Exit chat on blank line / `done` / `q`.
4. On exit, `continue` back to the **status** prompt — chat resolves
   nothing on its own. The operator still picks apply / skip / feedback.

**Read-side contract (load-bearing):**

- Chat **never** mutates the plan, never dispatches `action_fn`, and
  never sets `state.pending_feedback`. It is purely advisory.
- Chat **does not** record an annotation by itself (unlike feedback,
  which sets `pending_note`). Leaving chat returns the rec to limbo and
  re-prompts, exactly as `(r)un` does.
- It must be impossible to confuse chat output with an applied edit:
  label answers distinctly (e.g. a `  advisor:` prefix), the way
  `(f)eedback` echoes `feedback noted (steers the next apply): …`.

**Optional promote-to-feedback (decide during create; keep it
explicit if kept):** offer an exit that copies the operator's last
question or a one-line takeaway into `pending_feedback` (e.g. typing
`use`/`steer` at the `ask:` prompt). Default exit must **not** do this —
promotion is an explicit act, so a consult never silently rewrites the
next apply. If this adds ambiguity, drop it; the core value is the
read-side consult.

## The advisor seam (this is the part tests gate on)

Every function that shells out to Claude takes an injectable invoker
defaulting to a real-CLI shell-out (`shell_claude_invoker`
`create.py:440`, `shell_review_invoker`, `shell_annotate_invoker`
`annotate.py:115`), and `tests/conftest.py` installs an autouse gate
that **raises** if a backend binary is spawned (opt out only with
`@pytest.mark.allow_real_claude`). The chat path must honor that seam:

- Add an injected `advisor_fn` (a `prompt: str -> str` callable, the
  same shape as the existing invokers) parameter to
  `walk_recommendations()` / `_prompt_for_annotation()`, threaded like
  the existing `action_fn`. When `advisor_fn is None`, `c` prints a
  "no advisor wired; use another shell" notice and re-loops — mirroring
  `(r)un`'s "no action handler registered" branch (`review_walk.py:722`).
- Wire the real default at the **CLI** call sites (where `action_fn =
  _build_review_action_fn(...)` is built today,
  `review_actions.py:38`), backed by a `shell_*`-style invoker — not in
  the leaf loop. Keep `review_walk.py` free of a real-backend default so
  the loop stays unit-testable without the autouse gate firing.
- Tests inject a stub `advisor_fn`; no real `claude`. Add the new seam
  to **TESTING.md**'s neutralization table.

## Advisor prompt

Build a focused, **read-only** prompt from: the `Recommendation`
(`review.py:279-343` — `title`, `body`, `suggested_action`, `severity`,
`source`, `step_id`), the plan identity/path, and the operator's
question + transcript. Frame it as: *answer the operator's question and
give a recommendation (include-in-plan / defer / separate-action / etc.);
do not propose or make edits.* The advisor is a Claude subprocess in the
repo, so it can read plan and code files for grounding; keep the prompt
itself bounded. A single advisor with a caller-supplied context label
(completeness rec vs review finding vs reconcile finding) — **not** three
variants.

## Non-interactive / `-y` / non-TTY

Chat is interactive-only. Under `-y` / apply-all / non-TTY the loop
already forces apply-all so the per-rec prompt is bypassed (e.g.
`reconcile.py:1579`); chat simply never prompts there. Never block
automation waiting on `ask:` input; never read stdin when there is no
TTY.

## Help text

Extend `HELP_TEXT` (`review_walk.py:276-300`) with the `c`/`chat`/`ask`
entry, and state the distinction plainly: **chat asks and advises and
changes nothing; feedback steers the next apply.** Keep it terse (repo
norm: concise docs).

## Scope of work

1. **Loop wiring** in `review_walk.py` — add the `advisor_fn` parameter
   to `walk_recommendations()` and `_prompt_for_annotation()`; add the
   `c`/`chat`/`ask` branch (multi-turn REPL, exit → re-prompt, no
   annotation, no `action_fn`, no `pending_feedback`); add the
   no-advisor-wired notice; update the prompt string and `HELP_TEXT`.
2. **Advisor builder + default** at the CLI seam (near
   `_build_review_action_fn`, `review_actions.py`) — construct the
   read-only advisory prompt from the rec + plan context and back it
   with a `shell_*`-style invoker; pass `advisor_fn` into every
   `walk_recommendations(...)` call site (`completeness_cmd.py:277`,
   `review_cmd.py:392/472/541`, `reconcile.py:568/2061/2071`).
3. **(Optional) promote-to-feedback** exit — only if kept explicit per
   the contract above.
4. **Tests** (`tests/test_review_walk.py`) — stub `input_fn`/`output_fn`
   and a stub `advisor_fn`: `c` recognized and aliased (`chat`/`ask`);
   advisor called with rec + question + accumulated transcript across
   turns; exit (blank/`done`/`q`) returns to the status prompt; chat
   leaves **no** annotation, dispatches **no** `action_fn`, and leaves
   `pending_feedback` untouched; `advisor_fn is None` → notice + re-loop;
   non-TTY/`-y` never reaches chat; existing keys/aliases unchanged.
   No real `claude`.
5. **Docs** — `RUNBOOK.md` walk walkthrough (when to chat vs feedback vs
   run); **TESTING.md** neutralization table (new advisor seam);
   `docs/cli/` regen only if a flag changes (likely none — chat is an
   in-loop key, not a flag).

## Non-goals

- **Not feedback.** Chat must not steer an apply or record a note by
  default; that's `(f)eedback`'s job and it stays exactly as-is
  (`review_walk.py:709-720`).
- **Not run.** Chat never invokes `action_fn` / never executes the
  recommendation's suggested action; that's `(r)un`.
- **No plan/code edits from chat**, ever — advisory only.
- **No new CLI flag / subcommand.** It's a key inside the existing walk.
- **No persistent chat transcript / saved-review schema change** by
  default. The saved review JSON and `Annotation` shape are unchanged.
  (A logged transcript could be a later additive step; don't expand the
  schema here.)
- **No three forked loops.** One shared implementation for all walk
  callers.
- **No always-on auto-advice.** Chat is opt-in per rec via the key; the
  walk never volunteers advice unprompted.

## Acceptance criteria (plan-level)

- In any walk (`completeness-apply`, `review`, `reconcile-plan-walk`),
  typing `c` (or `chat`/`ask`) opens an advisory exchange about the
  current rec; the operator can ask follow-ups; exiting returns to the
  `(a)pply/(s)kip/(f)eedback/(r)un/(aa)/(q)/(?)` prompt with the rec
  still unanswered.
- The advisor receives the rec context + question + transcript and its
  answer is printed, distinctly labeled — never mistakable for an edit.
- Chat lands no edit, sets no annotation, and does not touch
  `pending_feedback` (verified by test).
- With no `advisor_fn` wired, `c` prints a notice and re-loops; the rest
  of the walk is unaffected.
- Under `-y` / non-TTY, the walk behaves byte-for-byte as before (chat
  unreachable); automation never blocks on input.
- All existing walk keys, aliases, and feedback semantics are unchanged;
  the full suite passes with no real `claude` spawned.

## Risks

- **Key/alias collision.** `d`/`done` and `n`/`note` are taken; confirm
  `c`/`chat`/`ask` collide with nothing before wiring.
- **Seam leakage.** A real-backend default in the leaf loop would trip
  the conftest gate and spawn `claude` in tests — keep the default at
  the CLI seam, inject in tests.
- **Contract bleed.** The whole point is that chat ≠ feedback; an
  accidental `pending_feedback` write or `action_fn` call collapses the
  distinction. Assert the negatives explicitly in tests.
- **Token cost / unbounded chat.** Multi-turn re-invokes the backend per
  turn; keep the prompt focused and the transcript bounded, and make
  exit obvious so a consult doesn't run away.
- **Non-TTY hangs.** Reading `ask:` with no TTY would wedge CI — gate on
  the same interactive/`-y` condition the per-rec prompt already
  respects.

## References

- `plan_tool/review_walk.py` — shared interactive-loop and annotation seams
  that host the proposed chat key.
- `plan_tool/cli/review_actions.py` — existing feedback/action boundary that chat
  must not cross.
- `TESTING.md` — backend-neutralization contract for the injected advisor seam.
