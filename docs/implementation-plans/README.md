# Implementation plans

Keep structured, developer-ready plans here: intent, scope, ordered steps,
dependencies, acceptance criteria and the metadata the runner reads. The plan's
frontmatter owns its execution state; its detail files explain each step.

| Content | Owner |
| --- | --- |
| Plan structure and lifecycle metadata | [Plan format](../../PLAN_FORMAT.md) |
| Per-step instructions under `plan-details/` | [Detail format](../../DETAIL_FORMAT.md) |
| Backlog routing under `backlog-arcs/` | [Tracking rules](../TRACKING.md) and the originating backlog entries |
| Seed content, including retained local `plan-seeds/` material | [Seed format](../../SEED_FORMAT.md); new repository seeds live in `docs/implementation-plans/plan-seeds/`, and existing root-level `plan-seeds/` files stay in place |
| Archived plans | The plan lifecycle and [manifest housekeeping](../how-to/common-workflows.md#8-sweep--manifest-housekeeping) |

Archived and audited plan and detail files are frozen. They are not edited for
link hygiene or stale citations, because an edit makes their saved audit reports
stale; a dead path in one is expected.

Do not add explanatory READMEs to individual `plan-details/` or report folders;
the artifact contracts above own those structures. Keep session pickup notes in
[handoffs](../../handoffs/README.md), reusable procedures in
[how-to](../how-to/README.md), and measured conclusions in
[evidence](../evidence/README.md). A backlog arc coordinates work; it does not
replace a plan or change its scope contract.
