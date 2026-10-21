> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Document the concept decision contract and scope-review workflow

## Summary

Document the concept decision record shipped by steps 1–6 across `CLAUDE.md`, `RUNBOOK.md`, `TESTING.md`, and `BACKLOG.md`. Add an Architecture entry for the new concept subsystem, an operator workflow for `plan-tool scope-review`, and a testing-matrix row that points maintainers to the correct unit and CLI suites. Treat the persisted record and scoped sign-off rules as the authority; do not describe plan prose or a CLI prompt as a second source of truth. On green, all four documents agree with the shipped command, conflict behavior, exit outcomes, and the remaining work under backlog item `#121`.

## Table of Contents

- [Summary](#summary) — The documentation surfaces and expected result.
- [Why](#why) — Why the shipped concept contract needs one consistent explanation.
- [Input](#input) — The step 6 command contract and earlier domain outcomes this step verifies.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four documentation files updated.
- [Implementation](#implementation) — The contract, workflow, testing guidance, and backlog update.
- [Tests](#tests) — Documentation checks against the shipped implementation.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for complete and accurate docs.
- [References](#references) — The plan and source surfaces used to verify the prose.
- [Deferred](#deferred) — Integration and hardening work outside this core plan.

## Why

Steps 1–6 add a persisted concept record, deterministic derivation, three-state scoped review, synchronization, and a public `scope-review` command, but the repository’s maintainer, operator, testing, and backlog guides do not yet explain that combined contract. Leaving those guides unchanged would make the new leaf invisible in the Architecture registry, give operators no recovery path for conflicts or invalid state, and leave maintainers guessing which tests cover changes to the subsystem. This step makes the shipped behavior discoverable without expanding the core into the separate create, detail, ownership, and completeness integrations still tracked by `#121`.

## Input

- **Steps 1–5 — domain contract:** Use their shipped outcomes as the authority for record identity and integrity, deterministic bootstrap and conflict-aware re-derivation, three-state scoped sign-off, and canonical concept-to-plan synchronization. Do not restate their internal mechanisms.
- **Step 6 — public command contract:** Verify the final parser help, flags, scope selection, success behavior, conflict and invalid-state messages, and process exit outcomes from `plan_tool/cli/scope_review_cmd.py:register`, `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, and `docs/cli/scope-review.md` before writing operator prose.
- **Backlog boundary:** Treat `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree` as still open unless every item in that entry has shipped. This plan delivers the reusable core and standalone command, while create/detail wiring, explicit ownership linkage, and completeness enforcement belong to the follow-up integration plan.
- **Checked-in behavior only:** If any step 1–6 surface is missing or differs from its plan, stop the documentation claim and route the gap back to its owning step. Do not patch production code in this non-code step.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `CLAUDE.md` — Add a sibling Architecture paragraph for the concept decision subsystem, its command surface, and its key authority and conflict invariants.
  - `RUNBOOK.md` — Add a `scope-review` operator workflow and a matching entry in `RUNBOOK.md:Table of contents`.
  - `TESTING.md` — Add the concept decision subsystem to `TESTING.md:When to run integration tests`, naming its source modules and focused unit and CLI suites.
  - `BACKLOG.md` — Update `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree` to credit the shipped core while keeping the unshipped integration work explicit and open.

## Implementation

The foundational rule is: **the validated concept record is the decision authority, and `scope-review` changes only an explicit scope while reporting stale, conflicting, or invalid state instead of choosing a winner silently**.

- **Verify before documenting.** Read the final step 1–6 modules and tests at HEAD. In particular, confirm the persisted model and integrity surface in `plan_tool/concept_tree.py`, derivation outcomes in `plan_tool/concept_bootstrap.py`, review outcomes in `plan_tool/concept_review.py`, synchronization outcomes in `plan_tool/concept_sync.py`, and command policy in `plan_tool/cli/scope_review_cmd.py`.
- **Add one Architecture entry.** In `CLAUDE.md:Architecture`, add a paragraph modeled on the existing bold-lead subsystem entries. Name the concept modules, `plan-tool scope-review`, the persisted record as the authority, exact scoped review, three decision states, source-state binding, and conflict-first behavior. Keep CLI orchestration separate from the reusable domain modules.
- **Describe only the shipped core.** Do not claim that `create`, `detail`, scope-out, or completeness already maintain concept ownership unless their integration work is present at HEAD. The Architecture paragraph should distinguish the standalone core from the follow-up integrations without reproducing the follow-up plan’s design.
- **Add an operator workflow.** In `RUNBOOK.md`, place a focused subsection near the other plan-review or completeness workflows. Explain when to run `plan-tool scope-review <name>`, how to select the supported scope, what the three review states mean, what successful sign-off changes, and how to re-run the command after plan changes.
- **Use exact command behavior.** Copy flag spelling, accepted values, and exit meanings from `plan_tool/cli/scope_review_cmd.py:register`, `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, and the generated `docs/cli/scope-review.md`. Do not invent numeric exit codes, flags, prompts, or recovery commands from the plan title.
- **Make failures actionable.** For each shipped conflict, stale-record, and invalid-state outcome, give the operator a short “what you saw / why / what to inspect / how to retry” path. Preserve the core rule that automatic conflict resolution is not available; the docs must not tell users that a re-run silently overwrites reviewed state.
- **Keep sign-off scope precise.** State that review and sign-off apply only to the requested concept scope and current source state. Do not imply that selecting a parent automatically signs descendants unless the shipped step 4 contract explicitly does so.
- **Maintain the Runbook ToC.** Add the new subsection to `RUNBOOK.md:Table of contents`. Compute the GitHub-style anchor from the exact heading and verify that the link points to that heading.
- **Register the testing area.** Add one row to `TESTING.md:When to run integration tests` for the concept decision subsystem. List the shipped source modules from steps 1–6 and point to their direct unit suites plus `tests/cli/test_scope_review_cmd.py` for command wiring.
- **Keep test guidance proportional.** Explain that domain-only changes should run the matching unit suite, while command orchestration or cross-module persistence and synchronization changes should also run `tests/cli/test_scope_review_cmd.py`. Preserve `TESTING.md:Default to unit tests` and `TESTING.md:Add an integration test when (and only when) a unit test can't prove what you need`.
- **Update `#121` as partial progress, not retirement.** In `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree`, add credit for the shipped concept decision core and standalone `scope-review` surface, citing `docs/implementation-plans/2-concept-decision-record-core.md`.
- **Retain the open integration scope.** Rewrite stale statements that say no structured concept record or standalone review command exists, but keep `#121` open for the create/detail integration, explicit concept-to-step ownership, scope-changing preservation, and completeness enforcement described by `docs/implementation-plans/2-concept-signoff-integrations.md`.
- **Remove superseded blockage wording carefully.** The old `coverage-linkage` design gap must not continue to claim it blocks this core plan once the core ships. Preserve the underlying ownership concern as remaining follow-up work rather than declaring it solved.
- **Do not redo step 6 registration docs.** `CAPABILITIES.md`, `docs/cli/README.md`, `docs/cli/scope-review.md`, and CLI help goldens belong to step 6 and remain unchanged here.
- **Avoid a second contract.** `CLAUDE.md`, `RUNBOOK.md`, and `TESTING.md` should summarize and point to the shipped surfaces. They must not define new persisted fields, scope semantics, or exit outcomes absent from steps 1–6.

## Tests

- `verify_architecture_entry_matches_shipped_concept_modules` — confirms `CLAUDE.md:Architecture` names only modules and invariants present after steps 1–6.
- `verify_scope_review_runbook_commands_match_help` — compares every documented command and flag with `plan-tool scope-review --help` and `docs/cli/scope-review.md`.
- `verify_scope_review_failure_guidance_matches_cli_outcomes` — confirms conflict, stale, and invalid-state guidance agrees with `tests/cli/test_scope_review_cmd.py`.
- `verify_scope_review_runbook_toc_anchor` — confirms the new `RUNBOOK.md:Table of contents` link points to the exact workflow heading.
- `verify_testing_matrix_names_real_suites` — confirms the new `TESTING.md:When to run integration tests` row points to existing source and test paths.
- `verify_backlog_121_records_partial_progress` — confirms `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree` credits the core plan while retaining the unshipped integration work.
- `verify_docs_do_not_claim_followup_integrations_shipped` — confirms none of the four edited files describe create/detail ownership or completeness enforcement as implemented without matching code at HEAD.

### Verification (non-code step)

- Run `plan-tool scope-review --help` and compare its command form, flags, choices, and help text with the new `RUNBOOK.md` workflow.
- Run the focused step 6 CLI suite in `tests/cli/test_scope_review_cmd.py` to confirm the documented success and failure outcomes still match the implementation.
- Run the step 6 package-surface and CLI-reference checks in `tests/cli/test_package_surface.py` and `tests/cli/test_cli_reference.py`; this step does not regenerate their artifacts.
- Check every path and symbolic anchor named in the four edited documents with `rg`.
- Check the new Runbook ToC anchor against the exact heading text.
- Review the `BACKLOG.md:#121` status and remaining-work bullets against `docs/implementation-plans/2-concept-decision-record-core.md:Out of scope`, `docs/implementation-plans/2-concept-decision-record-core.md:Deferred`, and `docs/implementation-plans/2-concept-signoff-integrations.md:Overview`.
- Run the repository’s Markdown or documentation validation checks if present; do not add a new test framework in this step.

## Acceptance criteria

- `CLAUDE.md:Architecture` contains one concept decision subsystem paragraph naming the shipped leaf modules, `scope-review`, and the record-authority, explicit-scope, source-state, and conflict invariants.
- `RUNBOOK.md` contains an operator workflow whose commands and outcomes match `plan-tool scope-review --help` and `docs/cli/scope-review.md`.
- `RUNBOOK.md:Table of contents` contains a working link to the new workflow heading.
- `TESTING.md:When to run integration tests` contains a concept decision subsystem row with real source paths and the matching unit and CLI test paths.
- `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree` credits `docs/implementation-plans/2-concept-decision-record-core.md` as shipped core work and remains open for the follow-up integrations.
- No edited document claims that create/detail concept ownership, scope-changing preservation, or completeness enforcement shipped as part of this core plan.
- No edited document defines a flag, review state, persisted field, conflict policy, or exit outcome that is absent from the step 1–6 implementation.
- `tests/cli/test_scope_review_cmd.py`, `tests/cli/test_package_surface.py`, and `tests/cli/test_cli_reference.py` pass.

## References

- [`docs/implementation-plans/2-concept-decision-record-core.md`](../../2-concept-decision-record-core.md) — Use the plan’s Out of scope and Deferred sections to keep the core documentation boundary accurate.
- [`docs/implementation-plans/2-concept-signoff-integrations.md`](../../2-concept-signoff-integrations.md) — Use this follow-up plan to identify the create, detail, ownership, completeness, and scope-change work that remains open.
- [`plan_tool/concept_tree.py`](../../../../plan_tool/concept_tree.py) — Verify the persisted concept record and integrity contract before describing it.
- [`plan_tool/concept_review.py`](../../../../plan_tool/concept_review.py) — Verify the three-state, explicit-scope, and source-state sign-off rules.
- [`plan_tool/concept_sync.py`](../../../../plan_tool/concept_sync.py) — Verify the canonical synchronization and conflict behavior.
- [`plan_tool/cli/scope_review_cmd.py`](../../../../plan_tool/cli/scope_review_cmd.py) — Verify the public flags, command flow, messages, and exit outcomes.
- [Python argparse — Parser for command-line options](https://docs.python.org/3/library/argparse.html) — Use only to check the general help and exit behavior relied on by the operator workflow.

## Deferred

- **Create and detail integration** — The follow-up concept-signoff integration plan owns inserting concept review into those authoring flows.
- **Explicit concept-to-step ownership and completeness enforcement** — `docs/implementation-plans/2-concept-signoff-integrations.md` owns the linkage and missing-owner findings.
- **Ownership preservation across split, merge, re-ground, and scope-out** — The follow-up integration plan owns those mutation boundaries.
- **Automatic conflict resolution** — The core plan explicitly keeps re-derivation and synchronization conflicts operator-visible.
- **Transactional recovery across concept-record and Markdown writes** — This remains a separate durability concern beyond documenting the shipped per-artifact behavior.
