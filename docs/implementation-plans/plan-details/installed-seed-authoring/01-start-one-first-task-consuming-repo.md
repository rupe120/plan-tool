# Step 1 — Guide installed assistants from a request to a reviewed seed

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Add a first-task walkthrough and the file-backed seed intake rules to `integrations/shared/DIRECTIVES.md`. Link to `Authoring hygiene` from the Authoring row and big-document shortcut in each of the three installed routers, and extend the existing phase-link tests. Use the shared reference that already ships beside each router so a session can ground, check, and present a seed for user review in a standalone installation. The walkthrough ends with the assistant committing the approved seed and passing that file to `plan-tool create`.

## Table of Contents

- [Summary](#summary) — The installed authoring path this step delivers.
- [Table of Contents](#table-of-contents) — Where to find the procedure and checks.
- [Why](#why) — The gap between installed guidance and file-backed intake.
- [Input](#input) — The source contract and the intake decisions it describes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The shared reference, three routers, and routing tests.
- [Implementation](#implementation) — The first-task walkthrough, backlog variation, and intake rules.
- [Tests](#tests) — Link checks and documentation verification.
- [Acceptance criteria](#acceptance-criteria) — What a reviewer can observe when the step is complete.
- [References](#references) — The source contracts and implementation anchors.
- [Applicable guardrails](#applicable-guardrails) — Which plan limits bind these edits.
- [Deferred](#deferred) — Verification and tracking owned by later steps.

## Why

The three routers already ship with a shared reference and an Authoring row, but that row skips `Authoring hygiene`, and the big-document shortcut sends the document straight to `create`. The shared reference's authoring section assumes access to `SEED_FORMAT.md` in the tool checkout and describes a size threshold and heading rules that disagree with file-backed intake. A session following those instructions can invoke `create` before checking source evidence or getting the user's review, or misread a valid preparation case as a format defect.

## Input

- Use `SEED_FORMAT.md` sections `Explicit scope boundaries` and `Conventions` for authoring. Check the installed wording against `plan_tool/create.py:validate_from_existing_seed()` and `classify_file_backed_source()`. `FileBackedSourceIntake.direct_ready` and `needs_preparation` describe source shape. The route decision and evidence review still follow.
- Use `plan_tool/create.py:_intent_from_seed_outcome()` and `_extract_supplied_guardrails()` for what `create` reads from the raw selected seed before routing. Use `plan_tool/scope_fence.py:missing_required_guardrail_headings()` for the required guardrail sections. The intake checks establish structure and presence. The author must check the claims, references, and meaning of the limits against the request and repository.

## Files (creates vs edits)

- **New files** — None.
- **Existing files (edits only)**
  - `integrations/shared/DIRECTIVES.md` — Put the walkthrough, backlog variation, and usable intake rules under `Authoring hygiene`. Correct nearby file-backed route descriptions that would contradict those rules.
  - `integrations/claude/SKILL.md` — Link the Authoring row and big-document shortcut to the shared section.
  - `integrations/codex/SKILL.md` — Link the same two entry points to the shared section.
  - `integrations/cursor/SKILL.md` — Link the same two entry points to the shared section.
  - `tests/test_skill_router_phase_rules.py` — Require the Authoring phase-table link for each backend. Step 2 owns the installed shortcut test.

## Implementation

**Use the installed sibling as the authoring entry point.** The core rule is to check and review one grounded seed before handing it to file-backed `create`. `plan_tool/cli/skill_cmd.py:cmd_install_skill()` already installs the router and shared reference side by side, and `pyproject.toml` includes the integrations tree in the wheel. Put the rules and examples in that sibling. Shipping `SEED_FORMAT.md` as another installed file would expand the bundle for guidance the sibling can already carry. Identify `SEED_FORMAT.md` as the authoritative source in the tool repository and make the installed text usable on its own.

**Walk through one first task in a consuming repository.**

1. Start at the installed router and follow `DIRECTIVES.md#authoring-hygiene`. Pick one requested result with a small end-to-end proof. Show how the assistant checks the user's wording for the requested change and its limits, then opens the current entry point and relevant tests. For each claim about existing behavior, name a repo-relative path and symbol or test and say what it establishes. Show how an unresolved product choice goes back to the user before it becomes a seed commitment.
2. Write one readable brief under `docs/implementation-plans/plan-seeds/<slug>.md`. Put a measurable user result in the first non-empty paragraph of `## Outcome`. `plan_tool/create.py:_intent_from_seed_outcome()` reads that paragraph from the raw selected source, ignores standalone thematic breaks, and collapses whitespace for plan `intent`.
3. Keep all seven scope-contract fields. Cover Outcome, In scope, Out of scope or Non-goals, Allowed behavior changes, Allowed reorganization, Verification, and Stop / defer. Use `## Testing` for Verification and `## Acceptance criteria` for the observable results that must hold. A canonical `## Out of scope` can carry the non-goals field. Keep the allowed changes, allowed reorganization, and stop rules explicit even in a direct-ready seed.
4. Put each binding limit under its named guardrail. `## Scope guardrails` constrains the changes, `## Audit guardrails` constrains what the audit evaluates, and `## Expected placement` records any required home for the work. Use `None` only if the corresponding kind of boundary genuinely does not apply. The full scope contract describes the effort. These exact H2s carry the raw author-supplied limits forward into the plan and downstream prompts.
5. Show one usable `## References` with sources the assistant actually opens, including the local code or tests that support the brief. Give each reference enough context for a reviewer to find it and see what it supports. In `## Testing`, name the smallest end-to-end check and the relevant preserved behavior. In `## Acceptance criteria`, state what someone will observe when those checks pass.
6. Check the finished seed against its source, live code, full scope contract, and intake rules. Write a standalone seed and cite provenance in `## References`. Omit legacy YAML provenance that would select a separate seed. Present that file for review, incorporate requested changes, and recheck it. After approval, commit that file, then pass its exact path to `plan-tool create <slug> --from-existing <path>` using the shared headless and model-selection rules.

Use a concrete sample request with an observable change and a limit the reader can trace into its guardrail. An example could extend an existing report export to honor a selected status while preserving the output columns. Make any illustrative repository paths and symbols explicit as sample evidence, with enough context for step 2 to verify them in a temporary consuming repository. Present the request seed as a complete direct-ready example.

**Show a short backlog-derived preparation example.** Reuse the workflow for a single selected entry. Include the originating backlog path and entry ID, and the ticket key if the entry is promoted. Carry the full source contract verbatim and elaborate within its boundaries. For a promoted entry, get the contract from the ticket and name the local stub. Show where the seed requires the resulting plan to update the originating backlog when the work ships and to verify that update. Mark the unpromoted entry plan-authored and link the plan while execution is pending. Remove a shipped entry or promotion stub only after delivery and its verification. Omit a derivable heading such as `Overview` to demonstrate preparation. Keep the Outcome, source contract, guardrails, and evidence required by the preparation rule below.

**Give the walkthrough and the big-document shortcut one intake rule.**

- **Fix preflight refusals before calling `create`.** An unmatched Markdown code fence can hide later headings. Close it with a matching fence. Supply exactly one real `## References` with non-empty, non-placeholder evidence outside fenced code. A heading shown inside an example, or a References body made entirely of code fences, cannot satisfy that check. Supply each of the three guardrail H2s exactly once outside fenced code with a non-empty, non-placeholder body. `_(TODO)_` fails. An explicit `None` passes the guardrail presence check. The guardrail checker can also count fenced body content beneath a real heading. These preflight refusals happen before routing, model calls, or a run record.
- **Explain direct assessment using the actual heading set.** Once preflight passes, the seed is direct-ready when it has exactly one non-empty, non-placeholder `## Overview`, `## Problem statement`, `## Architecture`, `## Out of scope`, `## Risks`, `## Testing`, `## Acceptance criteria`, and `## Deferred` after fenced code is stripped. A Testing section containing only a fenced command selects preparation. Case and an optional closing ATX sequence normalize. `Outcome` and `In scope` still belong in the scope contract. Direct readiness selects a raw-source assessment. Only its single-plan outcome can publish directly, using strict `## Steps` when valid. A split produces a proposal and an invalid assessment produces a refusal. Neither publishes a plan. A prepared seed gets an ordinary step proposal.
- **Explain preparation using the same rule.** When preflight passes but a canonical body section is missing, duplicated, empty after fence stripping, or a placeholder, `create` takes the visible preparation route. Its decision can normalize the source for one plan, propose a split, or refuse. For all preparation seeds, state source evidence for scope exclusions, risks, testing, and acceptance criteria. State any actual deferrals and say when there are no known risks. Preparation may derive Overview, Problem statement, and Architecture from intent. Remove the 16 KB advice, `Scope of work` heading advice, and the `--no-distill` bypass suggestion for file-backed intake.
- **Read the result after exit.** A normalized plan can already be published and registered when iteration stops incomplete. Identify this case from the emitted incomplete-iteration message or its recorded `iteration_incomplete` outcome, together with the registered plan. Use `plan-tool completeness-audit <slug> --iterate` to continue that plan in place. Treat a split or refusal as a no-plan result and follow its emitted action.
- **Explain how to recover after exit.** Update the shared `Classify preflight refusals accurately` paragraph alongside the intake guide. Correct a preflight defect before retrying. For unsupported preparation evidence, check the named section against the approved seed. Add and review missing evidence before committing a correction. When the evidence already exists and preparation misses it, follow the emitted instruction to retry unchanged after confirmed exit. Keep the multi-plan pointer to the shared classification rule working.
- **Route the installed authoring entries to `DIRECTIVES.md#authoring-hygiene`.** Keep the phase-table links and checklist. Have the big-document shortcut ground a standalone seed for one effort and cite the original document under References. Have the complete-plan recipe explicitly use the same review, commit, and create sequence. State that all three routers pass the approved standalone seed to `create`.

## Tests

### Verification (non-code step)

This step changes guidance and its tests. The `enforce_step_tests` run gate applies to `feature` and `refactor` steps, so the `non-code` classification leaves the focused checks below as the verification for this step.

- `tests/test_skill_router_phase_rules.py:test_phase_table_is_identical_across_the_three_routers` — The three Authoring rows carry the same links and checklist.
- `tests/test_skill_router_phase_rules.py:test_every_section_a_router_names_exists_in_directives` — `#authoring-hygiene` and the other phase anchors exist in the shared reference.
- `tests/test_skill_router_phase_rules.py:test_each_phase_row_links_every_section_and_carries_its_checklist` — The Authoring row requires the new sibling link alongside its existing links and checklist.
- `tests/test_create.py:TestFileBackedSourceIntake` and `tests/test_scope_fence.py:TestMissingRequiredGuardrailHeadings` — Compare the guidance with the existing intake tests. Step 2 owns the classifier proof for the installed examples and fenced-only variant.
- Example walkthrough — Trace each claim to its evidence, each binding limit to its guardrail, and the review and commit to the exact standalone input. Check the step 2 proof of selected input and readiness when reviewing implementation.
- Route and recovery review — Compare the shared guide with the existing direct-split and unsupported-evidence tests and the seed ingestion lifecycle table. Check that it distinguishes split from publication, handles each refusal route, and continues an iteration-incomplete registered plan in place.
- Link regression check — Temporarily remove a required new link and confirm the targeted test fails. Restore it and rerun the focused suite.

## Acceptance criteria

- Each installed router's Authoring row and big-document shortcut point to `DIRECTIVES.md#authoring-hygiene`, and the focused routing tests pass.
- The shared reference and router entries put source checking, approval, commit, and file-backed `create` in that order. The approved standalone seed is the CLI-selected source, and References cite any originating document.
- Both examples contain a measurable Outcome, the full scope contract, usable source evidence, a proof under `Testing`, observable acceptance criteria, and the three guardrail sections. Every binding limit appears in the corresponding guardrail, and any `None` has a clear reason.
- The backlog variation identifies the source entry and any promoted ticket, preserves the source contract, links the unpromoted plan-authored entry while execution is pending, and makes the originating backlog update part of shipment verification.
- The guidance explains unmatched fences, References, guardrails, and canonical body readiness. The request example demonstrates direct readiness and the backlog example demonstrates preparation, with installed classification proof owned by step 2.
- The route guide explains fenced-only canonical bodies, limits strict source step import to direct-ready seeds, and states the evidence requirements for any preparation seed.
- The guide identifies direct and normalized publication outcomes, shows how to continue after incomplete iteration, and keeps both refusal recovery entry points consistent with the emitted instructions.

## References

- [Seed format — The full scope contract, guardrails, placement, and canonical heading conventions](../../../../SEED_FORMAT.md#conventions)
- [File-backed seed ingestion — Preflight, source authority, direct assessment, and preparation](../../../../docs/reference/contracts/seed-ingestion.md)
- [Shared directives — The installed Authoring hygiene section](../../../../integrations/shared/DIRECTIVES.md#authoring-hygiene)
- [File-backed classifier — `validate_from_existing_seed()` and the source-readiness predicates](../../../../plan_tool/create.py)
- [Skill installer — `cmd_install_skill()` and the sibling destinations](../../../../plan_tool/cli/skill_cmd.py)
- [Installed Seed Authoring — Step ownership, scope, and acceptance](../../2-installed-seed-authoring.md)
- [Backlog — Entry #377 and the source scope contract](../../../../BACKLOG.md)

## Applicable guardrails

- The plan's `## Scope guardrails`, installed guidance — Limit edits to the shared reference, its router links, and their focused verification. Keep the installer and intake as read-only sources for this step.
- The plan's `## Audit guardrails`, review scope — Judge the installed authoring path and its agreement with intake. Leave the adjacent policy and sign-off work to the owners named in the plan.
- The plan's `## Expected placement`, guidance ownership — Keep the runnable procedure within the installed sibling and use the source format to check the wording.
- The plan's `## Out of scope`, preparation and router boundaries — Preserve the preparation option and confine router edits to the relevant guidance links and shortcut text.

## Deferred

- Installed source and isolated wheel verification — Step 2 owns the supported install modes and the installed-example checks.
- `BACKLOG.md` #377 release bookkeeping — Step 3 owns closure after shipment and verification.
