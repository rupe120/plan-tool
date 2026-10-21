# Step 3 — Add `## Stack` to the audit's authoritative sections and a settled store or hosting product to its commitment kinds

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`plan_tool/prompts/plan-audit.md` receives two prompt edits. The scope-contract rule's list of authoritative preserved sections gains `## Stack`, and its wording covers a settled technology constraint, so a stack contradiction is never dismissed as out of scope. The commitment-kinds list in "Method — audit commitments, not sites" gains a settled store or hosting product, so a step or detail file that contradicts the carried stack is traced as a finding. The audit stays advisory, with no gate, exit-code change, or technology-name comparison in code. `tests/test_review.py` gains key-based assertions on the rendered audit prompt. On green, the rendered prompt names `## Stack` as authoritative and lists the stack commitment kind.

## Table of Contents

- [Why](#why) — what the audit cannot see today
- [Input](#input) — the prompt text and plan body this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the footprint
- [Implementation](#implementation) — the two prompt edits and the replay observation
- [Tests](#tests) — the roster and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [Applicable guardrails](#applicable-guardrails) — the plan fence as it binds this step
- [Deferred](#deferred) — items left out

## Why

Steps 1 and 2 put a tool-rendered `## Stack` section into the seed and carry it into the plan body. The audit prompt names only `## Scope guardrails`, `## Audit guardrails`, and `## Expected placement` as authoritative. An auditor reading a plan whose `## Stack` says PostgreSQL and whose step says SQLite can treat the stack as ordinary prose or call the contradiction out of scope. The commitment-kinds list also has no entry for a settled technology choice. Without both edits, the carried stack is preserved but nothing checks that the steps honor it.

## Input

- **Prompt text:** the "Stay inside the declared scope contract" bullet in the Rules section of `plan_tool/prompts/plan-audit.md` holds the authoritative-section sentence. The "Method — audit commitments, not sites" section, step 1, holds the commitment-kinds bullet list.
- **Plan body (steps 1–2):** the plan body can carry a `## Stack` H2, preserved from the seed. A plan without one is unaffected; the prompt wording must not require it.
- **Renderer:** `plan_tool/review.py:render_plan_audit_prompt` renders the template. This step changes template text only; the renderer, its variables, and the prompt's section order stay the same.
- **Not verifiable here:** tests prove the prompt text is present, not that a model acts on it. The replay below is the only behavioral observation, and it is n=1.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/prompts/plan-audit.md` — add `## Stack` to the authoritative-section sentence and reword it for a settled technology constraint; add a settled store or hosting product to the commitment-kinds list.
  - `tests/test_review.py` — add the prompt-text assertions below, in the class that already tests `render_plan_audit_prompt` (`TestCheckPlanAudit`, which owns `_write_plan` and the prompt-render cases).

## Implementation

**Intended behavior**

- **Authoritative section.** In the scope-contract bullet, add `## Stack` to the heading list. Reword the clause so the preserved section is described as the seed's own scope, audit, placement, or technology decision. Keep the rest of the bullet as is, including the originating-scope-contract rule that the plan body wins over its seed.
- **Contradiction is in scope.** Say plainly that a step or detail file contradicting a `## Stack` choice is a correctness finding about the plan's own commitment, not an adjacent idea to defer. This keeps the stack out of the `[out-of-scope-deferred]` path.
- **Commitment kind.** Add one bullet to the commitment-kinds list: a settled store or hosting product the plan carries (a database, hosting facet, or named product), traced against every step and detail file that names a store or hosting choice. Match the list's existing style (short noun phrase, one example in parentheses).
- **Trace instruction.** Rely on the method's existing "trace each commitment end-to-end" step. Do not add a new procedure.

**Constraints that are not free to vary**

- The prompt must not name a specific product (PostgreSQL, SQLite) outside an example, and must not instruct the auditor to compare technology names by pattern. The auditor judges by reading.
- No gate, severity rule, exit-code change, or new finding source. The audit stays advisory.
- Keep the stable-prefix ordering: the edits are inside the static instruction sections, so the prefix-caching test (every stable section precedes all volatile content) must stay green unchanged.
- Use `$$` for any literal `$` and add no new `${...}` placeholder, since the template renders through `safe_substitute`.

**Replay observation (not a gate)**

- Run one Integration-style replay: a throwaway plan whose `## Stack` says PostgreSQL and whose step says SQLite, through `plan-tool completeness-audit` once, on a scratch branch so the report never joins a real plan's history.
- Record the outcome in this plan's handoff as an observation that gates nothing: whether a stack-contradiction finding appeared, and its severity.
- Do not tune the prompt to make the replay pass. A miss goes to the handoff as evidence, not into a second prompt edit.

**Approach rejected**

- A code-side comparison of stack technology names against step text is out. It would measure vocabulary and not intent, and the plan fence rules it out.

## Tests

All tests go in `tests/test_review.py`, in `TestCheckPlanAudit`, using its `_write_plan` helper and `render_plan_audit_prompt`. They assert keys, not loose words.

- `test_audit_prompt_names_stack_as_authoritative_preserved_section` — the rendered prompt lists `## Stack` in the same sentence as `## Scope guardrails`, `## Audit guardrails`, and `## Expected placement`, so dropping `Stack` from the list turns it red.
- `test_audit_prompt_treats_a_stack_contradiction_as_in_scope` — the scope-contract bullet states that a contradiction of the preserved technology choice is a finding, not an `[out-of-scope-deferred]` item. Name the invariant: the stack must not be read as out of scope.
- `test_audit_prompt_lists_settled_store_or_hosting_product_as_a_commitment_kind` — the commitment-kinds list in the Method section contains the settled store or hosting product entry, located between the Method heading and the Lenses heading.
- `test_audit_prompt_stack_edits_keep_the_static_prefix_ahead_of_volatile_content` — the existing prefix-caching test stays green unchanged; no new test is needed unless the edits add a section heading, which they must not.
- `test_audit_prompt_with_no_stack_section_renders_without_a_stack_requirement` — a plan body with no `## Stack` renders a prompt with no unresolved `${` and no instruction that a stack must exist. This pins that the edit is conditional on the section being present.

Verify the first three by mutation: delete the added text and watch each go red.

**Green-before-done gate:** every test above must be green, and the existing `TestCheckPlanAudit` and `TestAuditPromptScopeContractBlock` cases must stay green, before this step is finished.

## Acceptance criteria

- `render_plan_audit_prompt` output contains `## Stack` in the authoritative-section sentence.
- The rendered prompt states a stack contradiction is a correctness finding and not an out-of-scope deferral.
- The commitment-kinds list contains a settled store or hosting product entry.
- The diff touches only `plan_tool/prompts/plan-audit.md` and `tests/test_review.py`; `plan_tool/review.py` has zero diff.
- No new gate, severity rule, exit-code change, or technology-name comparison appears in code (`rg -i 'postgres|sqlite' plan_tool/review.py` returns nothing new).
- The replay observation is recorded in this plan's handoff with the audit command and outcome, and gates nothing.

## Applicable guardrails

- **Step intent and the plan's "## Out of scope":** the audit stays advisory. This step adds no gate, exit-code change, or technology-name comparison in code, and no conflict surfacing in `create` or `detail`.
- **Plan intent:** the edits serve the audit treating the carried stack as a commitment to trace. They do not extend to the Jira handoff, a cross-plan audit (BACKLOG.md #462), or correcting existing plans.
- **Anti-creep rule on prompt text:** the smallest prompt wording that makes the two properties true. Do not add a procedure, a severity table, or a rule engine.

## Deferred

- Carrying `## Stack` into the Jira handoff — the plan's "## Out of scope" lists it; the Jira section whitelist omits it by design.
- A cross-plan audit of derived plans against the roadmap — BACKLOG.md #462.
- Code-side checks of stack text against step text — deliberately not built (decided 2026-10-08); the audit prompt is the contradiction check.
- Measuring how often the auditor catches a stack contradiction — needs real roadmaps and a real backend, which the hermetic suite cannot supply; the single replay is an observation only.
