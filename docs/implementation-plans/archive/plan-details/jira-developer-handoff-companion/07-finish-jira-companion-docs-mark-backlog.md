> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Finish the Jira companion docs and mark BACKLOG #293 delivered

> **Historical delivery evidence — superseded 2026-08-23.** This detail records
> the completed opt-in companion design. The unified paired-export contract in
> `JIRA_FORMAT.md` replaces its story-only compatibility claims.

## Summary

Document the completed opt-in Jira developer-handoff mode in `JIRA_FORMAT.md`, keep `docs/reference/contracts/process.md` concise, regenerate the parser-owned `docs/cli/jira.md`, and retire the active #293 backlog route. The key decision is that the plan’s dependency-ordered path and scope constraints remain binding while the rendered implementation route remains guidance. On green, operators can find the command, output locations, authority boundary, regeneration rules, and completed delivery status without treating generated output as an upstream input.

## Table of Contents

- [Summary](#summary) — Reviewer-level result and documentation boundary.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why the completed companion needs one accurate public record.
- [Input](#input) — Landed command and export contracts the docs must reflect.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact documentation and backlog footprint.
- [Implementation](#implementation) — Documentation ownership, regeneration rules, and backlog closure.
- [Tests](#tests) — Existing generated-reference coverage and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation and retirement outcomes.
- [References](#references) — Primary references for generated CLI documentation and paths.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries this documentation must preserve.

## Why

Steps 1–6 add a second, generated terminal output, but the current Jira reference describes only story exports and the active backlog still presents #293 as unfinished work. Without a clear distinction between binding plan structure, suggested implementation guidance, and independently authored Jira-grade detail, an operator could treat the companion as authoritative or unsafe to regenerate. Finish the documentation after the CLI and export contracts land so the public guidance records the shipped behavior rather than an earlier proposal.

## Input

- **Step 6’s landed command contract:** Read the final parser and command behavior from `plan_tool/cli/jira_cmd.py:register` and `plan_tool/cli/jira_cmd.py:cmd_jira`. Use the landed flag names, validation order, output precedence, and direct-jira behavior; the code wins if it differs from this detail.

- **Steps 1–5’s landed export contract:** Use `plan_tool/jira.py:export_jira`, `plan_tool/jira.py:JiraResult`, and `plan_tool/jira.py:derive_jira_output_path` as the story-export anchors. Document only the companion behavior those steps actually ship.

- **Generated CLI reference:** `plan_tool/cli_reference.py:render_reference` and `plan_tool/cli_reference.py:write_reference` own `docs/cli/jira.md`. `tests/cli/test_cli_reference.py:TestCliReferenceDrift` contains the drift check.

- **Existing documentation ownership:** `JIRA_FORMAT.md:## What writes them` owns export behavior, while the `jira` row in `docs/reference/contracts/process.md` owns only process authority and handoff. `docs/implementation-plans/backlog-arcs/archive/backlog-arc-jira-grade.md:## Ordered route` owns the route’s status.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `JIRA_FORMAT.md` — Add the developer-handoff output, authority, provenance, and safe-regeneration contract beside the existing story-export reference.
  - `docs/reference/contracts/process.md` — Keep the `jira` process row concise and point readers to the detailed Jira format and CLI references.
  - `docs/cli/jira.md` — Regenerate the parser-derived command reference after step 6’s final CLI surface lands.
  - `BACKLOG.md` — Remove #293 from active backlog selection and close its delivered work without leaving a stale recommendation.
  - `docs/implementation-plans/backlog-arcs/archive/backlog-arc-jira-grade.md` — Convert the #293 route from an active execution guide into a dated delivered record.

## Implementation

- **Foundational logic — document a terminal, plan-led companion without granting it authority.** In `JIRA_FORMAT.md`, add a dedicated companion section near `## Output`. State that `--developer-handoff` produces the story source plus a generated Markdown companion from one captured input set, while the normal `plan-tool jira` path remains story-only.

- **Keep structure separate from guidance.** Document that every committed plan step appears in dependency-preserving order and that the step title and meaningful intent define the required outcome and purpose. Document deferred and `wont_do` steps as non-actionable parked history rather than current work. Label likely files, anchors, risks, and implementation mechanics as a suggested route. Make clear that present Scope guardrails and Expected placement constrain that route, while Audit guardrails do not enter the companion.

- **Document regeneration as current-source publication.** Distinguish companion regeneration from `JIRA_FORMAT.md:## Append mode`: companion mode rebuilds both generated sources from current captured inputs rather than preserving arbitrary old prose. Explain that target preflight rejects human-owned, pair-mismatched, prohibited, and either-grade detail destinations before model or renderer work, then that final ownership confirmation detects changes after capture without promising atomic protection against an external write after the final check.

- **Preserve human Jira handoff facts.** Extend the existing `JIRA_FORMAT.md:## Status` and `### Changes to a created ticket` guidance only as needed to explain companion-mode carry-forward: a Jira key survives only through proven same-plan, one-to-one covered-step ownership; dropped records remain story-source history; a changed created ticket requires a manual Jira update; and a keyed created ticket that becomes dropped requires a manual cancel, close, or repurpose decision. Do not describe companion output as posting to or synchronizing Jira.

- **Keep independent authoring separate.** Cross-link `DETAIL_FORMAT.md` for the Jira-grade detail contract. State that generated handoffs remain outside the detail bundle and are not detail-authoring, audit, reconciliation, or plan-mutation inputs.

- **Preserve process-document scope.** In `docs/reference/contracts/process.md`, retain one short `jira` row for authority, durable output, exclusions, and handoff. Link to `JIRA_FORMAT.md` and `docs/cli/jira.md` instead of copying flag precedence, paths, provenance fields, or lifecycle details.

- **Regenerate, do not hand-edit, the CLI reference.** Run `python -m plan_tool.cli_reference --write` after verifying step 6’s final `register` help. Keep the generated `docs/cli/jira.md` output that describes the companion flags and command behavior. If regeneration changes a file outside this step’s declared scope, inspect the parser change and reconcile the plan before accepting the extra file; do not leave generated docs stale.

- **Close active backlog routing.** Remove #293 from the `BACKLOG.md` Now board and next-pick guidance, and replace its active catalog treatment with the project’s dated delivered convention. Preserve only references that remain true historical context; no remaining #293 text may recommend starting or selecting this completed work.

- **Retire the Jira-grade arc accurately.** Update `docs/implementation-plans/backlog-arcs/archive/backlog-arc-jira-grade.md` so its file intent, selection guidance, and route status clearly say the companion route is complete and not a current pick. Keep the durable boundary between independent Jira-grade authoring and generated terminal output, but remove future-tense execution instructions for #293.

- **Use landed names and stable anchors.** Check every cited code symbol and path against the completed implementation before publishing prose. Keep the source-of-truth callout in `JIRA_FORMAT.md` accurate and avoid raw line-number references.

## Tests

- `tests/cli/test_cli_reference.py:TestCliReferenceDrift` — Regenerated `docs/cli/jira.md` exactly matches the live argparse parser.

### Verification (non-code step)

The test-authoring gate does not apply because step 7 has `change_type: non-code`.

1. Run `python -m plan_tool.cli_reference --write`, then run `uv run pytest tests/cli/test_cli_reference.py -q`.
2. Compare `plan-tool jira --help` with `docs/cli/jira.md` and confirm the documented companion flags, validation rules, and output behavior match `plan_tool/cli/jira_cmd.py:register`.
3. Check `JIRA_FORMAT.md` against `plan_tool/jira.py:export_jira` and `plan_tool/jira.py:JiraResult`, including story-only compatibility, companion regeneration, and manual Jira-update notices.
4. Confirm `docs/reference/contracts/process.md` links to detailed owners instead of repeating the format contract.
5. Check that every Markdown link, repository path, and symbolic anchor added in these five files exists, and that no new prose relies on line numbers.
6. Search `BACKLOG.md` and `docs/implementation-plans/backlog-arcs/archive/backlog-arc-jira-grade.md` for #293 and companion-route wording; active selection language must be gone, while retained history must be dated and clearly closed.

## Acceptance criteria

- `JIRA_FORMAT.md` documents the opt-in companion, its selected-detail grounding, the binding plan path, the suggested-route boundary, and scope/placement priority without presenting the companion as authoritative.

- `JIRA_FORMAT.md` distinguishes companion regeneration from story-only append behavior, explains pre-render target protection, safe same-plan replacement, Jira-key carry-forward, and keyed created-to-dropped manual follow-up, and does not promise external Jira synchronization or undetectable-write protection.

- `docs/reference/contracts/process.md` keeps the `jira` row at process level and directs format and command readers to `JIRA_FORMAT.md` and `docs/cli/jira.md`.

- `docs/cli/jira.md` is generated from the final parser and passes `tests/cli/test_cli_reference.py:TestCliReferenceDrift`.

- `BACKLOG.md` no longer lists #293 as Now, next, or open work; any retained #293 history identifies it as delivered.

- `docs/implementation-plans/backlog-arcs/archive/backlog-arc-jira-grade.md` records the route as complete and directs new needs to separate scope rather than reopening #293.

- Every new repository path and symbolic anchor resolves at HEAD, and the step changes no production code.

## References

- [argparse — Parser for command-line options, arguments and subcommandshttps: — Read for the parser-derived CLI reference and option help contract.

- [pathlib — Object-oriented filesystem pathshttps: — Read for the normalized story and companion destination terminology.

## Applicable guardrails

- **The plan’s “## Plan intent”, terminal handoff authority:** Document the companion as a generated terminal projection whose route helps implementation without replacing the plan’s binding outcomes.

- **The plan’s step 7 intent, documentation ownership:** Make authority, scope/placement treatment, regeneration, usage, and delivery status discoverable while keeping `docs/reference/contracts/process.md` free of duplicated implementation detail.

- **The plan’s “## Out of scope”, non-expansion boundary:** Limit this step to accurately recording the completed companion contract; do not imply additional product behavior or a broader workflow.
