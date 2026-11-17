# Runbook: presenting the getting-started demo

*Part of the [getting-started demo](README.md). That page owns building the
repository and the `step.sh` reference; this page owns running the demo in front
of an audience.*

**Audience:** the person presenting or rehearsing.
**Outcome:** walk all eight steps from baked checkpoints, with a known fallback
when a live step misbehaves.

## Verified versus unverified

| Claim in this runbook | Status |
| --- | --- |
| Building, `step.sh next/prev/goto/live/transcript`, the dirty-tree refusal, `git checkout -f` recovery and `live/*` cleanup | Run against a built demo repo. |
| `plan-tool validate` and `status` on every plan branch; tests at steps 6–8 | Run; they pass. |
| Any live model command, its duration, its cost, and how its output differs from the baked copy | **Not run.** Measure on your first rehearsal and write the numbers into § "Rehearsal notes". |
| Whether `create` prompts for confirmation when its output is piped through `tee` (it accepts `-y`/`--yes` to auto-accept confirmation prompts) | **Not run.** If step 2 appears stuck, check `.tmp/due-dates.create.log`, then decide whether to re-run with `-y`. |
| Backend authentication check | Use whatever you normally use; this runbook does not prescribe one. |

## Before the session

1. Build a fresh repository: `docs/demos/getting-started/build.sh --force`.
   Only a directory the script created is removed.
2. `cd` into it and run `./step.sh`. The step 1 card prints.
3. Confirm `git status` is clean and `git branch` lists `demo/1-seed` through `demo/8-code-review` and no `live/*`.
4. Confirm `plan-tool --version` prints, then run `plan-tool status due-dates` after `./step.sh goto 2` to see the plan resolve.
5. Only if a step will run live: confirm your backend is authenticated and that you have the budget for the calls.
6. Return to `./step.sh goto 1`.

## Choose a path

| Path | Steps live | Use when |
| --- | --- | --- |
| All baked | none | Short slot, flaky network, or no backend access. Nothing can stall. |
| One live step | one of 3, 4 or 5 | You want the audience to see real streaming output once, with the rest baked. |
| Fully live | 2 through 8 | Rehearsed in advance, with time to wait on each command. |

Step 1 has no command (a seed is written with an assistant). Step 8 is a
`/code-review` session activity, not a shell command.

## Per-step talk track

Run `./step.sh goto N` (or `next`) first. Each row names the one point to land.

| Step | Open | Say | Land this point |
| --- | --- | --- | --- |
| 1. Seed | the seed file | "The brief carries decisions and a fence, not instructions." | Read **Out of scope**. Every later audit stays inside it. |
| 2. Plan | `due-dates.md` | "The seed's Outcome became the plan intent; each step has its own." | Frontmatter is the source of truth; the prose is for people. Show `plan-tool status due-dates`. |
| 3. Bare audit | `./step.sh transcript`, then the acceptance criteria | "Audit the design before details multiply it." | Missing details are not a defect at this stage. The finding was applied by a judged hand-edit, not by the tool. |
| 4. Detail | one detail file | "Each step gets an implementation route and checkable criteria." | Read the **Acceptance criteria** bullets; later steps are judged against them. |
| 5. Detail audit | `./step.sh transcript` | "Now the audit reads the details and the code." | Read the coverage and convergence lines. A clean exit code alone is not a clean audit. |
| 6. Run | `git diff demo/5-detail-audit demo/6-run -- todo tests` | "Each step runs in a fresh subprocess." | Two gates: a test file changed, and `test_command` passes. Run `uv run pytest -q` (10 pass); the first run needs network to install pytest, so run it once on `demo/6-run` or later before the session. The install persists across checkouts because `.venv` and `uv.lock` are ignored. |
| 7. Reconcile code | `git diff demo/6-run demo/7-reconcile-code -- todo tests` | "The plan is canonical; the code moves." | The run omitted showing the due date. Never use `reconcile-plan` after a run: it edits the plan toward the code. |
| 8. Code review | `git diff demo/7-reconcile-code demo/8-code-review -- todo tests` | "A review finds what the plan could not see." | Verify a finding against the code and tests before applying it. Run `uv run pytest -q` (12 pass). |

## Run a step live

1. `./step.sh goto N`, then `./step.sh live`. You land on `live/N-name`, branched from the state step N-1 left, and the command prints.
2. Run the printed command. It tees to `.tmp/due-dates.<verb>.log`, and `set -o pipefail` stops a failure from reporting as success.
3. `run` refuses to execute on the repository's default branch; `./step.sh live` puts you on a `live/` branch, so keep that branch. Let the command finish. Do not interrupt a plan-tool command because it is quiet; read the log instead.
4. Compare: `git diff --stat demo/N-name live/N-name -- . ':!DEMO.md' ':!DEMO.transcript.txt'`. A difference from the baked result is expected; the pathspec hides the card and transcript, which always differ.
5. Leave the live result: § "Return to the baked path".

## When something goes wrong

| Symptom | Action |
| --- | --- |
| `./step.sh` says `working tree not clean` | `git status`, then either commit or discard: `git checkout -f demo/N-name` drops tracked changes. |
| A live command is slow or silent | Read `.tmp/due-dates.<verb>.log`. If the audience is waiting, switch to the baked state: `git checkout -f demo/N-name` and `./step.sh transcript`. |
| A live command fails or the result looks wrong | Switch to the baked state and say so. Baked output is authored, so call it "the shape of the result", not a captured run. |
| You are lost | `git branch --show-current`, then `./step.sh goto N`. |
| Branches look damaged | Rebuild: `docs/demos/getting-started/build.sh --force` (restarts at step 1). |

### Return to the baked path

```bash
git checkout -f demo/N-name          # discards tracked changes from the live run
git status --porcelain               # untracked files from a live run can remain
git clean -fdn                       # preview what clean would delete
git branch -D live/N-name            # drop the throwaway branch when finished
```

`.tmp/` is gitignored, so live logs survive checkouts and are not removed by `git clean`.
Review the `git clean -fdn` preview before running `git clean -fd`.

## Rehearsal notes

*(none yet — record live timings, cost, and how each live result differed from its baked copy here after the first rehearsal)*

## Deliberately not included

- **Timings and cost for live steps.** Unmeasured; see § "Verified versus unverified".
- **Backend authentication steps.** They depend on your backend; use your usual procedure.
- **Pushing or publishing the `demo/*` branches.** A separate decision.
