# Prepare a planning demo

Use a small feature, such as a dark-mode toggle, to show how a brief becomes an
implementation plan, detailed steps and Jira stories. Prepare the model-driven
outputs before presenting so the audience can focus on the decisions and artifacts.

> **Demo needs updating before its next presentation.** The refresh is deferred.
> Treat the existing `demo/1-seed` through `demo/4-jira` branches as examples that
> need review against the current tool. Use the
> [demo refresh handoff](../../handoffs/2026-10-21-demo-refresh.md) for the update
> checklist and prepared local artifacts. Resume that work before presenting the
> demo as a verified current workflow.

## Prepare the example

Work in a disposable repository. Create `plan-seeds/dark-mode-toggle.md` using
[the seed format](../../SEED_FORMAT.md). Describe the desired behavior, acceptance
criteria and scope: author a plan and Jira stories without implementing the feature.
If the application is hypothetical, identify its file paths as illustrative.

Commit a clean checkpoint before each authoring or audit command. Configure the
backend you intend to demonstrate; the commands below use that configuration.
Keep each prepared stage on its own branch:

| Branch | Contents to prepare | Command |
| --- | --- | --- |
| `demo/1-seed` | The brief and scope contract | `plan-tool create dark-mode-toggle --from-existing plan-seeds/dark-mode-toggle.md --iterate` |
| `demo/2-plan` | A bare plan with a reviewed design | `plan-tool completeness-audit dark-mode-toggle --iterate --commit`, then `plan-tool detail dark-mode-toggle --commit` |
| `demo/3-detail` | All detail files and a reviewed detail-grounded audit | `plan-tool completeness-audit dark-mode-toggle --iterate --commit`, then `plan-tool jira dark-mode-toggle` |
| `demo/4-jira` | The exported stories and their validation result | Inspect the generated story artifacts |

Run the bare-plan audit before detail authoring. Read each saved audit, judge its
conceptual findings, apply bounded corrections and re-audit changed committed
text until the applicable convergence condition holds. Keep the audit's actual
coverage and result visible in the demo. A zero exit code alone is not a clean
verdict. See [the audit procedure](../how-to/pipeline/audit.md).

Add a `DEMO.md` card to each branch with the artifact to open, the decision to
explain and the next branch to show. Do not put credentials or local configuration
in the prepared branches.

## Present the workflow

1. Switch to `demo/1-seed`. Show the requested behavior and the scope fence.
2. Switch to `demo/2-plan`. Show the ordered steps, dependencies and acceptance
   criteria. Explain what the bare-plan audit can establish before details exist.
3. Switch to `demo/3-detail`. Open one detail file, then its audit result. Explain
   how the implementation instructions and verification criteria support the plan.
4. Switch to `demo/4-jira`. Show how the same work becomes stories that a developer
   can pick up, including dependencies and acceptance criteria.

Switch only with a clean working tree. If a live model call is useful, run it in
another disposable branch so it cannot overwrite the prepared examples. Compare
its actual result with the prepared artifact rather than promising a fixed answer
or duration.

## Refresh the demo

Regenerate the prepared artifacts when command behavior, formats or the example's
scope changes. Use the current backend and command configuration, rerun both audit
gates, and validate the story export. Keep the demo's explanation aligned with
what the current tool does.
