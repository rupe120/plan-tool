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
| Live model output | The headless rehearsal reaches detail review with a registered plan, four details, and a current grounded report. See [Live first-plan walkthrough](#live-first-plan-walkthrough). |
| Whether `create` prompts for confirmation when its output is piped through `tee` | **Not run.** Check `.tmp/due-dates.create.log` and monitor the original invocation. Consider a retry with `-y`/`--yes` only after it exits and you have reviewed its outcome. |
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
| Continuous live plan | One branch through detail review | You want each stage to consume the output of the previous live stage. [Planning workflow](../planning-demo.md) |

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
4. After confirmed exit, review the output and commit any result you want to
   compare. Run `git diff --stat demo/N-name live/N-name -- . ':!DEMO.md' ':!DEMO.transcript.txt'`.
5. Leave the live result: § "Return to the baked path".

## When something goes wrong

| Symptom | Action |
| --- | --- |
| `./step.sh` says `working tree not clean` | Run `git status` to inspect the changes, then follow [Return to the baked path](#return-to-the-baked-path). |
| A live command is slow or silent | Read `.tmp/due-dates.<verb>.log` and monitor the original invocation through confirmed exit. To show the authored output while you wait, read it without switching branches with `git show demo/N-name:DEMO.transcript.txt`. [Monitoring procedure](../../../integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely) |
| After confirmed exit, `create` reports unsupported preparation evidence | Check the whole approved seed for evidence that supports the named section. If any is missing, add it, get user approval of the revised seed, and commit it before retrying. If the evidence is present, follow the printed instruction to retry unchanged. [File-backed intake](../../../integrations/shared/DIRECTIVES.md#file-backed-intake) |
| Headless `create` omits `test_command` | The demo does not meet automatic test-command preflight. If you continue to implementation, run `uv run pytest -q` in the demo repo and record the passing command as `test_command` in the plan frontmatter before approving implementation. [Test command reference](../../../PLAN_FORMAT.md#field-semantics) |
| A live command exits with an error or produces an unexpected result | Inspect the log and saved artifacts. Keep the live result if you need it, then return to the baked path and describe the output as an authored example. |
| You are lost | `git branch --show-current`, then `./step.sh goto N`. |
| Branches look damaged | Build into a new directory to restart at step 1. To rebuild in place, confirm any live command has exited and preserve results you want to keep before using `docs/demos/getting-started/build.sh --force`. |

### Return to the baked path

Confirm that the original invocation has exited. From a clean working tree,
`./step.sh goto N` switches to the prepared checkpoint. If there are local
changes, inspect `git status` and commit any results you want to keep.
Use the commands below only when you intend to discard the live changes and
delete the throwaway branch.

```bash
git checkout -f demo/N-name          # discards tracked changes from the live run
git status --porcelain               # untracked files from a live run can remain
git clean -fdn                       # preview what clean would delete
git branch -D live/N-name            # drop the throwaway branch when finished
```

`.tmp/` is gitignored, so live logs survive checkouts and are not removed by `git clean`.
Review the `git clean -fdn` preview before running `git clean -fd`.

## Rehearsal notes

An isolated plan-tool 1.6.0 wheel with Codex `gpt-6.2-sol` on macOS arm64
refused the first prepared seed after 24 seconds because it lacked explicit
Risks evidence. With Risks, Acceptance criteria, and Deferred supplied, the
retry selected preparation and registered a four-step plan in 135 seconds.
The prepared plan has three steps. Its two authored audit transcripts remain
available on their demo branches.

### Live first-plan walkthrough

On 2026-11-18, a clone at `f6e6a6f7e` supplied an isolated editable
installation of plan-tool 1.6.0. A fresh Codex session with `gpt-6.2-sol`
followed the project-local skill from the README request, proposed a seed that
passes file-backed intake, and paused for approval. An initial check resolved
another `plan-tool` executable with the same version string. The retry used
the selected executable and only the consuming repository and its skill for
authoring context. [Executable check](../../how-to/install-and-update.md#install-from-source)

The live continuation starts from the reviewed, prepared due-dates seed and
its registered four-step plan. The initial bare audit covers 0 of 4 steps,
with confirmed current evidence and one blocking finding. The plan asks its
storage step to prove CLI behavior that later steps introduce. The reviewed
correction keeps the storage round trip in step 1 and moves the whole CLI
proof to step 4. The bare re-audit is confirmed-dry and current with zero
blocking gaps.

`detail --commit` writes four detail files. Its automatic audit reaches its
pass limit with four findings, including one repeated across two categories.
The corrected details require the invalid-date test to catch saves that leave
the same bytes and call for rerunning the earlier plain-list and full-save
tests. They retain the separate-process check for due-date persistence.

The grounded re-audit covers 4 of 4 details with confirmed, current evidence.
It reports `awaiting-human-action` for one question about where to enforce
valid dates on writes that bypass the CLI. The sampler's `confirmed-dry`
result records a pass with no new findings. The remaining finding still
needs review. This is the rehearsal's stopping point. The application and
test files match the scaffold, and its four baseline tests still pass.
[Read the final qualified result](../../how-to/pipeline/audit.md#reading-the-final-qualified-result)

The rehearsal saves reports under
`docs/implementation-plans/plan-details/due-dates/reports/`. Compare the
status, coverage, and next action at each checkpoint.

| Checkpoint | Saved report | What the reader does |
| --- | --- | --- |
| Bare audit, 0 of 4 details | `20261119-023418-completeness.md` | Move the CLI proof after the steps that supply its prerequisites. |
| Bare re-audit, 0 of 4 details | `20261119-023533-completeness.md` | Confirm the corrected plan can proceed to detail. |
| Automatic grounded audit | `20261119-024228-completeness.md` | Read the reported gaps and pass limit before editing the details. |
| Grounded re-audit, 4 of 4 details | `20261119-024505-completeness.md` | Review the saved-date validation question and stop at detail review. |

## Deliberately not included

- **Backend authentication steps.** They depend on your backend; use your usual procedure.
- **Pushing or publishing the `demo/*` branches.** A separate decision.
