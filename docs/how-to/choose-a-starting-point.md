# Choose a starting point

*Back to the [README decision flow](../../README.md#decision-flow).*

Choose the input that best matches what you have. Each route names the first
command to run, what it produces, and the guide that owns the next stage.

## Start from nothing

Use this when you want the interactive wizard to help name and frame a new
plan.

```bash
plan-tool create my-feature
```

The wizard writes a new registered plan. Continue with
[Common workflows](common-workflows.md).

## Start from a short idea

Use this when one or two sentences describe the change.

```bash
plan-tool create my-feature --from "Add a dark-mode toggle"
```

`create` turns the description into a plan. Continue with
[Common workflows](common-workflows.md).

## Start from an existing draft

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

Use this when the draft already uses the canonical `## Steps` and `### N.`
layout.

```bash
plan-tool create my-feature --from-existing path/to/draft.md
```

`create` recognizes the canonical layout and skips the step-decomposition model
call. Read the [create-from-existing flow](pipeline/create-from-existing.md)
for the source requirements.

## Start the next iteration from an old plan

Use this when an earlier plan exists and current code shows what carried over.

```bash
plan-tool annotate path/to/old-plan.md
plan-tool create my-feature --from-existing <stem>.seed.md
```

`annotate` writes a forward seed and does not mutate its source unless you opt
into `--archive`. Continue with [Common workflows](common-workflows.md).

## Assess several old plans or notes

Use this when you need a carryover view before deciding which work to plan.

```bash
plan-tool annotate path/to/notes-or-plans/*.md
plan-tool list --status --report-dir <dir>
```

`annotate` writes coverage and grounding reports; `list --status` rolls them up
for active plans. See the [command guide](../reference/commands.md) for its
report and seed options.

## Stage a project-sized concept

Use this when the work is too large for one plan and you cannot yet name its
domain or trade-offs.

```bash
plan-tool roadmap my-project --from-existing path/to/brief.md
```

`roadmap` produces staged architecture artifacts and draft plan seeds. Follow
the [roadmap walkthrough](roadmap.md) before creating the emitted plans.
