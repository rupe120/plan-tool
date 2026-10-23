# Read a dark-mode planning example

These are **authored reading samples**, not captured model outputs or evidence
of successful authoring, reliability or audit convergence. All artifact blocks
are intentionally incomplete excerpts, not files to feed to a parser or execute.
Return to the [planning walkthrough](planning-demo.md) for copyable assistant
requests and review checkpoints.

The scenario is a light/dark toggle that retains a user's explicit choice after
reload. The paths `src/theme.ts`, `src/ThemeToggle.tsx` and `src/theme.test.ts`
below are **illustrative application paths**, not paths in this repository.
For a real consuming repository, ask the assistant to verify its actual layout,
existing theme behavior and test commands before drafting artifacts.

## Request and seed review

> Inspect this repository and draft a grounded dark-mode seed. Link it, summarize
> the outcome, constraints, non-goals and unresolved decisions, and ask me for
> corrections or continuation before creating the plan.

**Authored seed excerpt** — the full seed follows [Seed format](../../SEED_FORMAT.md),
including an explicit scope contract and usable References:

```markdown
## Outcome
Users can switch between light and dark themes and retain their choice after reload.

## In scope
The existing application shell gains an accessible theme control and saved preference.

## Out of scope
No account synchronization, new design system or unrelated layout changes.

## Allowed behavior changes
An explicit theme choice changes appearance and persists across reloads.

## Allowed reorganization
Keep changes within the existing theme and application-shell boundaries.

## Testing
Check keyboard operation, both themes and preference persistence with the app's tests.

## Stop / defer
Bring incompatible existing theme behavior or missing test support back for a decision.

## References
Cite the consuming repository's verified theme, shell and test documentation here.
```

The References line is an instruction for completing this excerpt, not a usable
source reference for `create`. Review whether the seed matches the application
and whether default-theme behavior needs a product decision. The assistant links
the actual seed, summarizes changes and asks for corrections or continuation;
it waits for a response unless explicit prior delegation covers plan creation.

## Plan and bare audit review

**Authored plan excerpt** — the complete artifact uses [Plan format](../../PLAN_FORMAT.md):

```yaml
intent: Let users choose a readable theme and retain that choice across reloads.
steps:
  - id: 1
    description: Add a persistent theme preference
    intent: Keep the selected appearance after reload.
    change_type: feature
  - id: 2
    description: Expose an accessible theme toggle
    intent: Let users change the selected appearance from the application shell.
    change_type: feature
    depends_on: [1]
```

Inspect whether dependencies and acceptance criteria serve the seed's scope.
Request the **bare-plan audit before detail authoring**. The assistant links the
actual plan and saved report, summarizes changes and asks for corrections or
continuation before details. It waits unless explicit delegation covers that transition.

**Authored audit review questions, not an audit result:** Where is the saved
report? What detail coverage does it record? Is its qualification sufficient for
its stated conclusion? What convergence outcome and unresolved decisions does it
report? At bare stage, conceptual calls are not detail-grounded, and missing
details do not by themselves establish a plan defect. Interpret findings and
withheld axes using the [audit procedure](../how-to/pipeline/audit.md).

## Detail and grounded audit review

**Authored run-grade detail excerpt** — a full detail needs the format marker and
all required sections in [Detail format](../../DETAIL_FORMAT.md); this excerpt
shows only part of the implementation and verification guidance:

```markdown
## Implementation
Use the existing theme boundary to apply a saved explicit preference. Keep the
control accessible by keyboard and expose its current state to assistive technology.
Illustrative paths: src/theme.ts and src/ThemeToggle.tsx; resolve actual paths first.

## Tests
Cover preference restoration after reload and keyboard activation of the control.
Use the consuming repository's verified test command.

## Acceptance criteria
- A chosen theme survives reload.
- Keyboard users can operate the toggle and determine its state.
```

Review the complete detail bundle, then its **detail-grounded audit**. Ask the
assistant to link both, summarize changes and report actual detail coverage,
qualification, convergence outcome and unresolved decisions. A successful exit
alone does not establish a clean result. These are authored review instructions;
no saved report location or audit outcome is asserted here.

The assistant asks for corrections or continuation and waits before execution or
local export unless explicit prior delegation covers the transition. For this
demo, authorize export only; feature implementation remains outside the task.

## Local story and developer handoff

> Export local stories and their paired developer handoff from the reviewed
> bundle. Link both outputs, summarize validation and warnings, and leave remote
> Jira and feature implementation untouched.

**Authored story excerpt**, not a generated or validated export:

```markdown
## Add a persistent theme preference
Let users retain their selected appearance after reload.

Acceptance: selecting either theme and reloading restores that choice.
Scope: the existing theme boundary; no account synchronization.
```

The story gives a tracker reader a bounded outcome, dependencies and acceptance
criteria. A real export supplies all fields required by [Jira format](../../JIRA_FORMAT.md).

**Authored developer-handoff excerpt**, not a captured companion:

```markdown
## Plan path
Step 1 — Add a persistent theme preference
Status: pending
Depends on: none
Purpose: keep the selected appearance after reload.

Suggested implementation route: inspect the existing theme boundary, persist the
explicit selection and cover restoration. Illustrative files: src/theme.ts and
src/theme.test.ts. A developer may choose a different compliant mechanism that
still fulfills the plan path above.
```

The companion provides implementation context from the same export snapshot;
the plan's stated outcome and purpose bind the work while the implementation
route is a suggestion. See [Paired developer handoff](../../JIRA_FORMAT.md#paired-developer-handoff)
and [Not a detail, audit, or reconciliation input](../../JIRA_FORMAT.md#not-a-detail-audit-or-reconciliation-input).
The companion does not replace canonical run-grade details or become an audit
input. Review both local outputs together; local export does not create remote
Jira issues.
