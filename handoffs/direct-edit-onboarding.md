# Direct-edit onboarding clarity

Single obvious edits can skip plan-tool's plan-authoring and execution pipeline
while retaining tests and review. The README's small first-plan example is a
learning exercise; small scope alone does not require a plan.

## Scope and review

The user authorizes clarifying the README opening and first-plan exercise,
contributor route selection, how-to index, and use-case entry-point table.
Identifier search covers `direct-pipeline`, `direct-run`, and direct-edit links;
vocabulary search covers `small`, `straightforward`, `lightweight`, `single
obvious edit`, and route selection. The index's deprecated pipeline recommendation
is removed. Small work that needs a durable plan or local Jira handoff retains
its reviewed planning route. Assistant policy and runtime behavior stay unchanged.

Two session review passes check the distinction between direct editing and the
deprecated direct pipeline, retained testing/review obligations, and the learning
example versus ordinary work. Neither pass identifies a further material gap.
These are session reviews, not independent backend reviews. Local links and
README heading anchors pass validation, and `git diff --check` passes.

Full validation: `uv run pytest tests/ -q -n auto` — **15,154 passed, 66 skipped**.
