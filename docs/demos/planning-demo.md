# Prepare a planning demo

Ask a coding assistant to turn a dark-mode-toggle brief into a grounded plan,
reviewable details and local stories. Use the [authored reading samples](dark-mode-example.md)
to see what to inspect at each decision point; they are not captured model results.

> **Demo needs updating before its next presentation.** Remote checkpoints
> `demo/1-seed` through `demo/4-jira` still need review against the current tool.
> The [demo refresh handoff](../../handoffs/2026-10-21-demo-refresh.md) records
> local preparation and remaining verification. Documentation and fixture checks
> do not establish a verified live workflow or authorize replacement remote refs.
> Temporary preparation files may be absent.

## Prepare the example

Work in a disposable consuming repository with an authenticated backend. Start
with this request:

> Inspect this repository's actual application paths, conventions and tests.
> Draft `plan-seeds/dark-mode-toggle.md` using the seed format: users can switch
> between light and dark themes and retain their choice after reload. Identify
> constraints and unresolved product decisions from the repository rather than
> assuming an application layout. Keep implementation outside this planning task.
> Link the seed, summarize its scope and grounding, and ask me for corrections
> or permission to create the plan. Wait for my response unless I explicitly
> delegate that transition.

Review the outcome, scope fence, non-goals and references before continuing:

> Use the plan-tool skill to create the dark-mode-toggle plan from the reviewed
> seed and run its bare-plan audit before authoring details. Monitor commands to
> completion and report progress. Link the plan and saved audit, summarize changes,
> steps, dependencies, acceptance criteria and consequential unresolved decisions.
> Report detail coverage, qualification and convergence outcome using the audit
> procedure. Ask me for corrections or continuation and wait before detail
> authoring unless my explicit prior delegation covers it.

After reviewing the bare plan and its audit, request the next stage:

> Author run-grade details for the reviewed plan through the plan-tool skill,
> then run the detail-grounded audit. Link the detail bundle and saved report,
> summarize changes, verification guidance and unresolved decisions, and report
> coverage, qualification and convergence outcome. Bring consequential decisions
> back to me. Ask for corrections or continuation and wait before execution or
> export unless I explicitly delegate that transition. Do not implement the feature.

The order is seed review → plan → bare audit and review → detail → detail-grounded
audit and review → local export. Silence and elapsed time do not grant approval.
The [audit procedure](../how-to/pipeline/audit.md) owns exact reporting and
convergence rules; a successful process exit alone does not mean a clean audit.
Use the skill's existing procedure for checkpoints and judged corrections rather
than treating these requests as a second operating policy.

After detail review, request the local export:

> Produce local Jira stories and their paired developer handoff from the reviewed
> plan and details, without implementing the feature or creating remote issues.
> Link both outputs and summarize their scope, dependencies and validation results,
> including warnings. Show which context belongs to the story and which belongs
> to the developer companion so I can review the handoff.

See [Jira format](../../JIRA_FORMAT.md#paired-developer-handoff) for the paired
export contract and [the example](dark-mode-example.md#local-story-and-developer-handoff)
for the two audiences.

## Present the workflow

Prepare outputs before presenting so the audience can focus on artifacts and
decisions. Retain these checkpoint names when preparing a future refreshed demo:

| Checkpoint | Artifact to open | Reader decision |
| --- | --- | --- |
| `demo/1-seed` | Grounded brief and scope contract | Correct the seed or authorize plan creation |
| `demo/2-plan` | Bare plan and saved bare audit | Review steps and audit limits before details |
| `demo/3-detail` | Run-grade details and detail-grounded audit | Review implementation guidance before export |
| `demo/4-jira` | Local stories and paired developer handoff | Review tracker scope and implementation context |

These names describe intended presentation checkpoints, not verified current
remote contents. Add a `DEMO.md` card during checkpoint preparation with the
artifact to open, decision to explain and next checkpoint. Keep credentials and
local configuration out of prepared branches.

Switch only with a clean working tree. Run live model calls in another disposable
branch or repository so they cannot overwrite prepared examples. Compare actual
results with the authored samples without promising a fixed answer or duration.

## Refresh the demo

Use the [handoff's remaining verification](../../handoffs/2026-10-21-demo-refresh.md#remaining-demo-verification-and-publication)
before presenting a verified current workflow: rehearse in a real consuming
repository, retain actual audit evidence and validate both local export outputs.
Remote checkpoint replacement requires separate review and authorization.
