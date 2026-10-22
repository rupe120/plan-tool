# Choose a starting point

*Back to the [README decision flow](../../README.md#decision-flow).*

Choose the input that best matches what you have. Each route names the first
supporting operator command, what it produces, and the guide that owns the next stage.

Ask the assistant to prepare inputs; you do not need a prewritten seed. Follow
[the planning walkthrough](../demos/planning-demo.md): review the linked seed and
scope summary before plan creation, the plan and bare audit before details, and
the details and grounded audit before a separate execution or local-export request.
At each boundary the assistant summarizes changes, asks for corrections or
continuation and waits for your response unless explicit prior delegation covers
it. Status inspection alone authorizes no implementation. For resumption, inspect
the original invocation and reports first; choose the next incomplete stage within
the requested scope only after confirmed command exit, using its recorded outcome.
See [monitoring and recovery](../../integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely).

After detail review, request one outcome explicitly: “Execute the reviewed plan,
then reconcile code and review changes,” or “Export local stories and their paired
developer handoff; link both and summarize validation for review.” Tracker
publication needs a separate request. For inspection, ask “Report the plan status,
reports and active invocation without implementing.”

## Start from nothing

> Help me frame this change, inspect the repository and draft a grounded seed for review before creating a plan.

Use this when you want the interactive wizard to help name and frame a new
plan.

```bash
plan-tool create my-feature
```

The wizard writes a new registered plan. Continue with
[Common workflows](common-workflows.md).

## Start from a short idea

> Inspect the repository and draft a seed for [idea], with a scope fence and verified references; link it for my review.

Use this when one or two sentences describe the change.

```bash
plan-tool create my-feature --from-existing docs/implementation-plans/plan-seeds/my-feature.md
```

`create` turns the reviewed seed into a plan. Operators can also use `--from` for a short throwaway description. Continue with
[Common workflows](common-workflows.md).

## Start from an existing draft

> Assess and ground path/to/draft.md against this repository; show the proposed seed and scope changes before creating a plan.

Use this when a draft already has rich body sections such as problem,
architecture, risks, or testing.

```bash
plan-tool create my-feature --from-existing path/to/draft.md
```

`create` evaluates the supplied source and either publishes a plan, produces a
split worksheet, or refuses an unusable input before a model call. The
[create-from-existing flow](pipeline/create-from-existing.md) owns the route
details and recovery behavior.

## Start from a canonical plan-shaped draft

> Check this draft against the code and canonical intake requirements; link the reviewed input before creating a plan.

Use this when the draft already uses the canonical `## Steps` and `### N.`
layout.

```bash
plan-tool create my-feature --from-existing path/to/draft.md
```

`create` recognizes the canonical layout and skips the step-decomposition model
call. Read the [create-from-existing flow](pipeline/create-from-existing.md)
for the source requirements.

## Start the next iteration from an old plan

> Assess carryover from this old plan against current code and link the forward seed for review; preserve the source.

Use this when an earlier plan exists and current code shows what carried over.

```bash
plan-tool annotate path/to/old-plan.md
plan-tool create my-feature --from-existing <stem>.seed.md
```

`annotate` writes a forward seed and does not mutate its source unless you opt
into `--archive`. Continue with [Common workflows](common-workflows.md).

## Assess several old plans or notes

> Assess these sources against current code and summarize coverage, grounding and proposed forward seeds for review; do not execute them.

Use this when you need a carryover view before deciding which work to plan.

```bash
plan-tool annotate path/to/notes-or-plans/*.md
plan-tool list --status --report-dir <dir>
```

`annotate` writes coverage and grounding reports; `list --status` rolls them up
for active plans. See the [command guide](../reference/commands.md) for its
report and seed options.

## Stage a project-sized concept

> Use the plan-tool skill to prepare a grounded concept brief for review, then a roadmap; link its artifacts and ask for review before deriving individual plans.

Use this when the work is too large for one plan and you cannot yet name its
domain or trade-offs.

```bash
plan-tool roadmap my-project --from-existing path/to/brief.md
```

`roadmap` produces staged architecture artifacts and draft plan seeds. Follow
the [roadmap walkthrough](roadmap.md) and [TTRPG demo](../demos/roadmap-demo.md) before creating the emitted plans.
