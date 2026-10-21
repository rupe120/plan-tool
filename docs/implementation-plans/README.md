# Implementation plans

Keep structured, developer-ready plans here: intent, scope, ordered steps,
dependencies, acceptance criteria and the metadata the runner reads. The plan's
frontmatter owns its execution state; its detail files explain each step.

| Content | Owner |
| --- | --- |
| Plan structure and lifecycle metadata | [Plan format](../../PLAN_FORMAT.md) |
| Per-step instructions under `plan-details/` | [Detail format](../../DETAIL_FORMAT.md) |
| Backlog routing under `backlog-arcs/` | [Tracking rules](../TRACKING.md) and the originating backlog entries |
| Seed content, including retained local `plan-seeds/` material | [Seed format](../../SEED_FORMAT.md); new repository seeds live in top-level `plan-seeds/` |
| Archived plans | The plan lifecycle and [manifest housekeeping](../how-to/common-workflows.md#8-sweep--manifest-housekeeping) |

Do not add explanatory READMEs to individual `plan-details/` or report folders;
the artifact contracts above own those structures. Keep session pickup notes in
[handoffs](../../handoffs/README.md), reusable procedures in
[how-to](../how-to/README.md), and measured conclusions in
[evidence](../evidence/README.md). A backlog arc coordinates work; it does not
replace a plan or change its scope contract.
