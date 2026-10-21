# Step 14 — Document lifecycle accounting and reconcile the concept backlog

## Summary

Update `CLAUDE.md` and `RUNBOOK.md` so their concept guidance matches the lifecycle accounting contract delivered by steps 5 and 12. Revise the existing concept-ownership and operator-workflow sections instead of adding a second description of the same subsystem. Reconcile `BACKLOG.md` by retiring `#121` after verifying the completed lifecycle behavior at HEAD and preserving any genuine follow-up work under a separate entry. On green, maintainer guidance, operator instructions, and backlog state all describe the same exact-owner-or-approved-non-delivery rule.

## Table of Contents

- [Summary](#summary) — Overview of the three documentation updates and their result.
- [Why](#why) — Why the existing concept guidance no longer describes the full accounting contract.
- [Input](#input) — Dependency outcomes and checked-in behavior this step must verify.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three documentation files changed by this step.
- [Implementation](#implementation) — Required documentation corrections and backlog retirement.
- [Tests](#tests) — Documentation-focused checks against real source and test surfaces.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completing the step.
- [References](#references) — Repository contracts that constrain the documentation.
- [Deferred](#deferred) — Code and generated-reference work owned by dependency steps.

## Why

`CLAUDE.md:Concept sign-off and ownership` and `RUNBOOK.md:Workflow: review concept decisions and ownership (scope-review)` still describe valid accounting partly in terms of an approved `wont_do` decision or a generic structured deferral. The completed plan requires a stricter rule: every reviewed concept must have exact committed ownership or a matching approved structured non-delivery record, and that rule must survive create restoration, detail regeneration, split, merge, re-ground, and scope-out without title inference. `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree` is already marked completed and retired but remains as a full tracking entry; once steps 5 and 12 prove the expanded lifecycle contract at HEAD, the entry should be removed rather than retained as open-backlog content.

## Input

- **Step 5 outcome:** document the blocking accounting rule enforced by `plan_tool/review.py:check_concept_coverage`, including its exact-identity requirement, structured non-delivery validation, dangling-link findings, and exclusion from prose apply.
- **Step 12 outcome:** use the lifecycle integration coverage as proof that create restoration, detail regeneration, split, merge, re-ground, scope-out, and completeness preserve or deliberately replace accounting. Do not restate the tests’ implementation.
- **Current operator surfaces:** verify `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, `plan_tool/scope_out.py:scope_out_step`, and the relevant authoring call sites before describing commands, refusal behavior, or approval rules.
- **Current tracking state:** inspect the complete `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree` block and sweep `BACKLOG.md` for every `#121` reference before deleting it.
- **Verification limit:** this step may describe only behavior present at HEAD after its dependencies finish. If a required source symbol or focused dependency test is missing, return the gap to its owning implementation step instead of compensating in these documentation files.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `CLAUDE.md` — revise `Concept sign-off and ownership` and any overlapping scope-out or correctness-gate prose so the architecture guidance states the final lifecycle accounting rule.
  - `RUNBOOK.md` — update `Workflow: review concept decisions and ownership (scope-review)`, its existing Table-of-contents link if the heading changes, and `Carve a spinning region out of a plan (plan-tool scope-out)` where its approval or accounting guidance is no longer accurate.
  - `BACKLOG.md` — retire the completed `#121` entry, repair any remaining cross-reference that still needs its rationale, and preserve only genuine unshipped follow-up work.

## Implementation

The foundational rule is: **a reviewed concept is accounted for only by an exact committed owner or a matching approved structured non-delivery record; every lifecycle operation must preserve or explicitly replace those links.**

- **Verify before documenting completion.** Confirm the step-5 behavior at `plan_tool/review.py:check_concept_coverage` and run the focused lifecycle tests owned by step 12. Treat a missing behavior or failing regression as an upstream implementation gap; this step must not weaken the prose to fit incomplete code.

- **Update the existing architecture paragraph.** Revise `CLAUDE.md:Concept sign-off and ownership` rather than adding a second concept-accounting paragraph. Keep the validated concept record as the decision authority and `Step.concept_ids` as the delivery link, but replace the claim that an approved `wont_do` decision alone accounts for a concept. State that `defer` and `wont_do` require the approved structured non-delivery record delivered by the dependency steps, including exact concept identity and a valid source or artifact link.

- **Describe the full lifecycle without duplicating implementation details.** In `CLAUDE.md:Concept sign-off and ownership`, name the supported operations and their shared outcome: create restoration, detail regeneration, split, merge, re-ground, and scope-out leave every reviewed concept with valid accounting or produce a blocking finding. Preserve many-owner semantics, and state that titles, feature tags, file lists, body prose, seed prose, and heuristic matches never become accounting authority.

- **Reconcile overlapping architecture prose.** Check `CLAUDE.md:Correctness gates` and the scope-out bullet under `CLAUDE.md:Structural remedy vocabulary` for claims that conflict with the revised paragraph. Update only the conflicting clauses. In particular, scope-out documentation must match `plan_tool/scope_out.py:scope_out_step` after step 12: a carve that removes the final owner must publish reviewed structured non-delivery accounting through the shipped workflow, while unattended or unreviewed paths must not be described as approving it automatically.

- **Revise the existing operator workflow.** Update `RUNBOOK.md:Workflow: review concept decisions and ownership (scope-review)` around `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`. Explain how an operator reviews `include`, `defer`, and `wont_do`; which non-delivery fields must be reviewed; when unchanged approval may remain valid; and why changing a disposition or accounting content requires approval of the replacement. Keep the command examples aligned with the live parser.

- **Make transition ordering clear.** Document that moving a concept to `include` does not remove its non-delivery record until the required regenerated delivery artifact is durable. Likewise, do not claim that a new `defer` or `wont_do` value is valid accounting before its replacement record is reviewed and approved. This ordering is fixed by the dependency contract even if the exact internal helper names change.

- **Explain completeness behavior in operator terms.** In `RUNBOOK.md:Workflow: review concept decisions and ownership (scope-review)`, distinguish a blocking `concept-coverage` finding from the advisory `concept-unsigned-deferral` reminder. State that `completeness-apply` does not choose ownership or approve non-delivery records; the operator must correct exact ownership or complete the explicit review workflow and then rerun `plan-tool completeness-audit`.

- **Update the scope-out walkthrough.** Reconcile `RUNBOOK.md:Carve a spinning region out of a plan (plan-tool scope-out)` with the final behavior of `plan_tool/scope_out.py:scope_out_step`. Cover final-owner detection, reviewed non-delivery accounting, interactive approval, unattended refusal or resume guidance, and the existing publication or rollback guarantees without presenting seed prose as restoration authority.

- **Keep the Table of contents valid.** `RUNBOOK.md` already links to `Workflow: review concept decisions and ownership (scope-review)`. Preserve that heading when practical. If wording changes, update the Table-of-contents entry and verify that its GitHub-style anchor points to the exact heading. Also verify the existing scope-out anchor after any heading edit.

- **Retire `BACKLOG.md` entry `#121`.** After the HEAD verification succeeds, delete the complete `#121 — Operator sign-off of a hierarchical deferred-concept tree` block. It has no remaining open work once this plan ships; keeping a completed entry in the open backlog would leave two competing status stories.

- **Sweep before deleting references.** Search all of `BACKLOG.md` for `#121`. Remove stale priority or roll-up mentions. When another entry still depends on the shipped behavior, replace the numeric dependency with the concrete capability or owning source, such as structured concept accounting, `plan_tool/review.py:check_concept_coverage`, or `plan-tool scope-review`; do not erase valid rationale blindly.

- **Preserve real follow-up work only.** Review this plan’s `Out of scope` section and the dependency details’ `Deferred` sections before deleting `#121`. If they name unshipped forward work that belongs in `BACKLOG.md`, retain it as a separately scoped entry without claiming this step implements it. Do not create entries for work already assigned to another plan or for internal consolidation marked reconcile-owned.

The rejected approach is to append a new lifecycle paragraph while leaving the older sign-off wording intact. That would create two authorities inside each guide and allow future readers to select the less strict rule.

## Tests

`verify_step_5_accounting_contract` — run the focused `tests/test_review.py`, `tests/test_completeness_report.py`, and `tests/cli/test_completeness_cmd.py` coverage required by step 5 before making shipped claims.

`verify_step_12_lifecycle_matrix` — run the lifecycle cases in `tests/test_create.py`, `tests/test_detail.py`, `tests/test_reground.py`, `tests/test_scope_out.py`, `tests/cli/test_authoring_cmds.py`, and `tests/cli/test_scope_out_cmd.py`.

`verify_documented_symbols_exist` — confirm every source symbol and command named in the edited prose exists at HEAD.

`verify_backlog_identifier_retired` — confirm `BACKLOG.md` contains no stale `#121` identifier after valid cross-entry dependencies have been rewritten.

### Verification (non-code step)

- Confirm `CLAUDE.md:Concept sign-off and ownership` states exact committed ownership or an approved structured non-delivery record, and does not treat `wont_do` alone as accounting.
- Confirm `CLAUDE.md` names create restoration, detail regeneration, split, merge, re-ground, and scope-out without claiming prose or heuristics can restore ownership.
- Confirm `RUNBOOK.md:Workflow: review concept decisions and ownership (scope-review)` matches the live `scope-review` parser and approval behavior.
- Confirm `RUNBOOK.md:Carve a spinning region out of a plan (plan-tool scope-out)` matches the live final-owner, review, unattended, and publication behavior.
- Confirm every edited RUNBOOK Table-of-contents link points to its exact heading-derived anchor.
- Confirm `rg -n '#121' BACKLOG.md` returns no matches after retirement.
- Confirm no remaining `BACKLOG.md` entry loses a valid dependency on the shipped capability.
- Run `uv run pytest tests/test_review.py tests/test_completeness_report.py tests/test_create.py tests/test_detail.py tests/test_reground.py tests/test_scope_out.py tests/cli/test_completeness_cmd.py tests/cli/test_authoring_cmds.py tests/cli/test_scope_out_cmd.py -q`.

## Acceptance criteria

- `CLAUDE.md:Concept sign-off and ownership` defines valid accounting as exact committed ownership or a matching approved structured non-delivery record.
- `CLAUDE.md` no longer says an approved `wont_do` decision alone satisfies concept accounting.
- `CLAUDE.md` states that lifecycle accounting is preserved or explicitly replaced across create restoration, detail regeneration, split, merge, re-ground, and scope-out.
- `RUNBOOK.md:Workflow: review concept decisions and ownership (scope-review)` explains approval, replacement, removal ordering, blocking coverage findings, and advisory unsigned findings consistently with HEAD.
- `RUNBOOK.md:Carve a spinning region out of a plan (plan-tool scope-out)` describes the final-owner and structured non-delivery workflow consistently with `plan_tool/scope_out.py:scope_out_step`.
- Every edited RUNBOOK Table-of-contents anchor points to an existing heading.
- `rg -n '#121' BACKLOG.md` returns no matches.
- The focused step-5 and step-12 test files listed under Verification pass before the documentation claims the lifecycle capability is shipped.
- No production code, generated CLI reference, schema document, or test file is modified by this step.

## References

- [Concept Ownership Lifecycle Accounting plan](https://github.com/rupe120/plan-tool/blob/main/docs/implementation-plans/2-concept-remediation-3-ownership-lifecycle-accounting.md) — Read the final accounting invariant, supported lifecycle operations, and declared out-of-scope work.
- [Concept coverage implementation](https://github.com/rupe120/plan-tool/blob/main/plan_tool/review.py) — Verify `check_concept_coverage` and the two concept finding sources before updating the guides.
- [Scoped concept review command](https://github.com/rupe120/plan-tool/blob/main/plan_tool/cli/scope_review_cmd.py) — Verify the live operator inputs, validation, and exit behavior described in `RUNBOOK.md`.
- [Scope-out lifecycle implementation](https://github.com/rupe120/plan-tool/blob/main/plan_tool/scope_out.py) — Verify `scope_out_step` and its final-owner accounting behavior before revising the scope-out walkthrough.

## Deferred

- Production lifecycle-accounting behavior and regression tests — owned by steps 1–12; this step only verifies and documents their shipped outcomes.
- Generated completeness CLI references — owned by step 5 and must already match parser help before this step begins.
- New lifecycle operations or automatic creation of covering implementation steps — outside this plan; this step documents only the supported lifecycle.
- Unrelated concept-publication refactors or persistence consolidation — leave with their existing owning plans or reconcile tracking.
