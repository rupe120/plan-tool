# Example-first documentation pilot

The README should let a new user see what a plan looks like, what an audit
asks them to decide, and where the assistant pauses for review. Put that path
up front. Keep the exact commands, exceptions, and recovery procedures in the
guides that own them. Pilot the pattern on the first-plan journey before
applying it to other entry points.

## Draft README opening

### Prepare your first plan

plan-tool turns a proposal into a plan your coding assistant can audit and
carry out. For example, a task-list CLI needs to store optional due dates,
accept them on `todo add`, and show overdue tasks. The plan orders those
changes and gives you a chance to review the behavior before implementation.

Install with uv and Git. Install and authenticate your backend CLI, then
choose the skill command for your assistant. Reload your assistant and open
the Git repository where you want to make the change. [Backend setup](../BACKENDS.md) ·
[Installation and updates](../how-to/install-and-update.md)

```bash
uv tool install git+https://github.com/rupe120/plan-tool
plan-tool --version
```

| Assistant | Install its skill |
| --- | --- |
| Claude Code | `plan-tool install-skill --integration claude --user` |
| Codex | `plan-tool install-skill --integration codex --user` |
| Cursor | `plan-tool install-skill --integration cursor --user` |

Try this request in the task-list repository.

> Use the plan-tool skill to plan optional due dates and `todo list --overdue`.
> Leave reminders and changes to ordering outside the scope. Show me the seed
> first, then the plan and bare-plan audit, then the step details and grounded
> audit. Link the artifacts and wait for my approval at each checkpoint. Stop
> after the detail review.

For a repository without a project profile, the assistant offers to set one
up. If you choose to do that, provide the project intent and confirm the exact
text before the assistant saves it. [Project setup](../../integrations/shared/DIRECTIVES.md#setting-up-a-repository-the-project-profile)

| Review | What the due-dates example shows |
| --- | --- |
| **Seed** | The scope covers storing and filtering dates. Reminders and changes to ordering stay outside this example request. |
| **Plan and bare audit** | Three steps cover storage, `todo add --due`, and filtering and display. The sample audit asks whether a task due today counts as overdue. |
| **Details and grounded audit** | The third step fixes the test date. The filter includes an open task due yesterday and excludes one due today. Check the saved audit’s qualification and findings before choosing what to do next. |

The bare audit review adds this acceptance criterion to the plan.

> A task due today is not overdue; only a due date strictly before today is.

Walk through these artifacts in the [prepared demo](../demos/getting-started/README.md).
Its authored audit examples show the review decisions you may encounter.

### Choose your next task

| I want to… | Open |
| --- | --- |
| Start from an existing draft, old plan, or project brief | [Choose a starting point](../how-to/choose-a-starting-point.md) |
| Review a saved audit | [Read the final audit result](../how-to/pipeline/audit.md#reading-the-final-qualified-result) |
| Implement the reviewed plan | [Check execution prerequisites](../how-to/pipeline/run.md#before-execution) |
| Export local Jira stories | [Export stories and review the handoff](../../RUNBOOK.md#workflow-export-to-jira-for-sprint-planning) |
| Check or resume a command | [Monitor progress and recover safely](../../integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely) |
| Look up command options or contribute to the tool | [CLI reference](../cli/README.md) · [New contributor path](../../CONTRIBUTING.md#new-contributor-path) |

Ask separately for implementation or local export after detail review. Local
export produces stories and a developer handoff. Ask separately for tracker
publication.

## Draft audit and recovery openings

The audit guide opens on two authored transcripts for the same plan. Both show
exit `0`. The decision changes with the evidence.

| What you see | What you do |
| --- | --- |
| **Bare audit, `0 of 3` detail files.** A finding asks whether a task due today counts as overdue. | Decide the boundary, update the acceptance criterion and risk, commit the correction, and re-audit before authoring details. |
| **Grounded audit, `3 of 3` detail files.** The example reports `confirmed-dry`. | Check the current revision and qualification, then read the report headline and suggested action before deciding whether to proceed. |
| **`no-qualified-current-evidence`.** The saved result lacks qualifying evidence for the current bundle. | Run a fresh audit before relying on the saved result for a decision. |

[Bare example](../demos/getting-started/fixtures/3-bare-audit/transcript.txt) ·
[Grounded example](../demos/getting-started/fixtures/5-detail-audit/transcript.txt) ·
[Result contract](../how-to/pipeline/audit.md#reading-the-final-qualified-result)

The recovery entry point starts with the situation the reader can observe.

| What you see | First action |
| --- | --- |
| The command goes quiet after a backend message. | Check the original invocation and keep monitoring it through confirmed exit. [Monitoring](../../integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely) |
| `detail` exits after writing two of three files. | Inspect the recorded outcome and the files on disk. Follow the detail recovery procedure to resume the remaining step. [Detail recovery](../how-to/recovery/detail.md#what-resumes-on-a-re-run) |
| `run` refuses because a detail file is missing from the remote default branch. | Check that the reviewed plan and its detail bundle landed on that branch, fetch, and start from the updated default branch. [Run prerequisites](../how-to/pipeline/run.md#before-execution) |

## Pilot scope and review

- **First change.** Use the README draft to implement the first-task slice of
  #510. Keep existing anchor destinations
  reachable. Move the format links into the reference index and replace its
  current link back to `#plan-format`. Keep that README anchor as a route to the
  index. Send project-scope installation,
  pinned versions, and skill refresh to the install guide. [Backlog](../../BACKLOG.md) ·
  [README format section](../../README.md#plan-format) ·
  [Reference index](../reference/README.md)
- **Verification.** Use #515 to have a fresh reader install the skill, find
  the seed and report, explain the due-today decision, and stop at detail
  review. For direct CLI readers, check that they can find the corresponding
  commands without going through a demo. Compare snippets with the parser and
  fixture artifacts, and check affected inbound links. #515 also owns the
  disposition of #508 before public sign-off. [Backlog](../../BACKLOG.md) ·
  [CLI start screen test](../../tests/cli/test_start_here.py)
- **Follow-up.** Use the draft audit and recovery openings where the walkthrough
  records a stumble within #530. Apply the pattern to roadmap and contributor
  guidance one reader task at a time. For roadmap, start with the accepted
  four-artifact version, then show how reviewing a plan row leads to separately
  materializing its draft. Bring exact flags, lifecycle variants, and rationale
  in through links beside the step that needs them. [Backlog](../../BACKLOG.md) ·
  [Roadmap seed workflow](../how-to/roadmap.md#7-promote-accepted-draft-seeds-or-create-directly-from-them)

Use the same two tiers inside task pages where a short opening serves the
normal path and deeper sections already have stable links. Review the pilot
by whether a reader can take the next step and find its governing rule.
