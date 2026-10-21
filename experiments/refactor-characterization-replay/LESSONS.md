# Spike: would a refactor characterization-pinning check ever fire? (2026-07-30)

**Question.** `plan-tool run` told every `refactor` step to write characterization
tests that pass **before** the code change and unchanged after. Nothing verified
it, and a plan was authored to mechanize the check. Before building it: on the
repo's own history, how often would that check have fired — and would firing
mean a real contract violation?

**Run a new measurement.** Use a repository containing the refactor changes
you want to evaluate and their parent revisions. Keep its corpus and test results
separate from the 2026-07-30 measurement below.

```
uv run python experiments/refactor-characterization-replay/classify.py   # writes corpus.json
uv run python experiments/refactor-characterization-replay/replay.py     # writes results.json
```

`classify.py` reads each green-step commit's plan file *as of that commit* to
recover the step's declared `change_type` (a commit subject does not carry it).
`replay.py` then, per refactor step: worktree at the step's **parent** commit
detached, copy that step's **post-change** test files in **unmodified**, run only
those, and classify on pytest's exit code (`0` silent / `1` red / `2`
uncollectable). Worktrees are removed in a `finally` and the run asserts none leak.

## Result

| | |
|---|---|
| Green-step commits parsed | **313** |
| `refactor` | **32 (10.2%)** — vs 206 feature, 66 non-code, 9 pre-`change_type` |
| Replayable (changed ≥1 test file) | **28** — 4 refactor steps changed *no* test file |
| **Would fire** | **25 of 28 — 89%** |
| Excluding `cli-package-split` (one mass rename, 12 steps) | **13 of 16 — 81%** |

Composition outside that one plan: **10 uncollectable, 3 failing, 3 clean.**

## What it decided

**The check was not built, and the contract it enforced was withdrawn.** The
dominant failure mode is *uncollectable*, not *failing*: the tests import symbols
the refactor **created**. That is inherent to any refactor changing test-visible
structure — not evidence anyone wrote tests after the fact.

So "passes before *and* after" is satisfiable only for refactors that preserve
the **test-visible interface**, and most real refactors do not. The directive
asserted a property most refactor steps *cannot have*. At an ~85% false-positive
base rate an advisory becomes noise operators learn to ignore, which kills the
whole finding channel. The contract — not the checker — was wrong.

Two incidental findings, both correcting assumptions the plan had written down:

- **Cost was a non-issue.** The plan carried a risk that building an interpreter
  environment in the sandbox would dwarf the worktree cost. A worktree plus
  `uv run pytest` completes in **~3 s**, resolving the worktree's own source with
  no path coaxing. The risk was speculation and it was wrong.
- **Whole-file granularity cannot carry the signal.** The check copies changed
  test *files*, so `3 failed / 376 passed` and `248 failed / 1436 passed` both
  surface as one undifferentiated "FAIL".

Durable record of the removal: `CLAUDE.md` § "Withdrawn: the per-`change_type`
test-ordering contract".

## Two methodology traps — the reusable part

**1. A silent corpus filter dropped 20% of history.** The first pass matched plan
files under `docs/implementation-plans/` only. Plans authored before that
directory move lived at `implementation-plans/`, so 62 commits were dropped with
no error — they simply never appeared. The first reported rate was **5.6%
refactor; the true figure is 10.2%**, nearly double. A filter that silently
yields fewer rows looks identical to a corpus that is genuinely smaller. Always
reconcile *found* against *parsed* and explain the difference before quoting a
rate.

**2. Validate the harness against a known answer before trusting a batch.** One
case had been verified by hand beforehand: `jira-grade-01`'s step 8, whose
characterization file could only be made to run after `sed`-ing away an import of
a symbol that step created. Replayed here **without** that edit, it reproduced
exactly that collection error unaided. Only after the harness recovered a
known-correct result was the 28-case batch trusted.

Both traps are instances of the same discipline the spike itself was testing:
**a surviving mutant indicts the mutation before it indicts the test.** An
unexpected measurement is a claim about your instrument first.

## When to reach for this again

The shape — *replay history against pre-change source to ask whether a proposed
check would ever have fired* — generalizes to any gate someone wants to add. It
cost about twenty minutes and displaced a nine-step build. Prefer it to shipping
a check and measuring afterward; a measurement sequenced *after* the build cannot
prevent the build.
