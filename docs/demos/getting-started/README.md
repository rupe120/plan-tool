# Getting started: a pre-baked walkthrough

Step through the whole plan-tool pipeline in minutes without waiting for any
command to finish. Every step is a ready-made git branch holding that step's
output, so moving between steps is a `git checkout`. Each step also has the real
command, so the same step can be run live on a separate branch.

**Audience:** a developer seeing plan-tool for the first time, or presenting it.
**Scenario:** add optional due dates and `todo list --overdue` to a tiny Python
task-list CLI. The scaffold is real and its tests pass at every checkpoint that
has code.

Presenting this? See the [presenter runbook](RUNBOOK.md) for pre-flight, a
per-step talk track and recovery.

## Start

Build the disposable demo repository outside the plan-tool checkout:

```bash
docs/demos/getting-started/build.sh                 # ~/plan-tool-getting-started-demo
docs/demos/getting-started/build.sh /path/to/demo   # or choose a location
docs/demos/getting-started/build.sh --force         # rebuild (removes only a directory this script created)
cd ~/plan-tool-getting-started-demo && ./step.sh    # prints the step 1 card
```

The build makes no network calls, calls no model, and pushes nothing.

## The steps

| Step | Branch | What to open | What the audience learns |
| --- | --- | --- | --- |
| 1. Create seed | `demo/1-seed` | `docs/implementation-plans/plan-seeds/due-dates.md` | A seed carries decisions and an explicit scope fence. |
| 2. Create plan | `demo/2-plan` | `docs/implementation-plans/due-dates.md` | The seed's Outcome becomes the plan intent; steps carry intent and files. |
| 3. Bare plan audit | `demo/3-bare-audit` | the plan's acceptance criteria and risks | The audit judges the plan body before details exist; findings are applied by judged hand-edit. |
| 4. Detail creation | `demo/4-detail` | `docs/implementation-plans/plan-details/due-dates/` | Each step gets an implementation route, tests and checkable criteria. |
| 5. Detail audit | `demo/5-detail-audit` | the three detail files | The grounded audit reads details and code; read coverage and convergence, not the exit code. |
| 6. Run | `demo/6-run` | `git diff demo/5-detail-audit demo/6-run -- todo tests` | Steps run in fresh subprocesses, gated on a changed test and `test_command`. |
| 7. Reconcile code | `demo/7-reconcile-code` | `git diff demo/6-run demo/7-reconcile-code -- todo tests` | The plan is canonical; code is edited to match it. |
| 8. Code review | `demo/8-code-review` | `git diff demo/7-reconcile-code demo/8-code-review -- todo tests` | `/code-review` finds what the plan could not; verify each finding before applying. |

Each branch is cumulative and carries a `DEMO.md` card (artifact to open,
decision to explain, live command) and `DEMO.transcript.txt` (the console output
for that step).

## Move between steps

| Command | Effect |
| --- | --- |
| `./step.sh` | Show the current step's card. |
| `./step.sh next` / `prev` | Move one checkpoint, instantly. |
| `./step.sh goto N` | Jump to step N (1–8). |
| `./step.sh transcript` | Print the console output the step would show. |
| `./step.sh live` | Branch to `live/N-name` from the previous checkpoint and print the real command. |

`step.sh` refuses to switch with a dirty working tree.

## Run a step live

1. `./step.sh goto N`, then `./step.sh live`. This checks out the state step
   N-1 left, on a throwaway `live/N-name` branch, so the prepared `demo/*`
   branches are never overwritten.
2. Run the command the card prints. It tees to `.tmp/due-dates.<verb>.log` and
   sets `set -o pipefail`, so a failing command is not reported as success.
3. Compare with the baked result: `git diff --stat demo/N-name live/N-name -- . ':!DEMO.md' ':!DEMO.transcript.txt'` (the pathspec hides the card and transcript, which always differ).
4. Return to the walkthrough with `./step.sh goto N`.

Live steps need an authenticated backend, take real time and cost tokens, and
their output will differ from the baked copy. Step 1 has no command (a seed is
written with an assistant); step 8 is a `/code-review` session activity.
Before running step 2 with a seed you write yourself, check its References and
guardrail headings against the [seed format](../../../SEED_FORMAT.md#core-directives).

## What is real and what is authored

| Item | Provenance |
| --- | --- |
| Scaffold app, code and tests at steps 6–8 | Real; the tests pass at each checkpoint. |
| Plan frontmatter | Real; `plan-tool validate` and `status` pass on every plan branch. |
| Detail files | Authored; each passes the real `parse_detail_response` gate. |
| Seed, plan body, audit findings, reconcile and review findings | Authored to the shape of real output. Not captured from a model run. |
| `[real]` lines in transcripts | Verbatim output of the deterministic command named. |
| Audit report JSON | Deliberately not baked; a live run writes it under `plan-details/due-dates/reports/`. |

Nothing here is evidence of model reliability or audit convergence. After a live
run, a different result from the baked one is expected, not a defect.

## Deliberately not included

- **Jira export and `verify`.** The pipeline's other branch; outside the eight requested steps.
- **Pushing the branches.** Publishing `demo/*` refs is a separate decision; the older `demo/1-seed`–`demo/4-jira` refs already exist on the remotes, and `demo/1-seed` and `demo/2-plan` share names with the generated branches. Do not push under these names; choose a distinct prefix first.
- **Captured live transcripts.** Replacing the authored transcripts with real captures is future work, once a live run is trusted.
