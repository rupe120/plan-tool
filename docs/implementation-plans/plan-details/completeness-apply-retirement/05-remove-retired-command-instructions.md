# Step 5 — Remove retired-command guidance from live documentation

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update the declared reference, workflow, and demo documents to describe the surviving completeness workflow. Remove instructions and architecture descriptions for the retired commands, and delete `docs/how-to/pipeline/direct-pipeline.md`. Direct readers to review saved conceptual findings, make judged edits, commit, and re-audit. Preserve historical artifacts and keep the existing documentation-reading suites green.

## Table of Contents

- [Summary](#summary) — Result and main boundaries.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Why live guidance needs updating.
- [Input](#input) — Dependency outcomes and documentation contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Edits and the deleted guide.
- [Implementation](#implementation) — Replacement workflow and preservation rules.
- [Tests](#tests) — Documentation checks and existing regression suites.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Scope decision and documentation style.
- [Applicable guardrails](#applicable-guardrails) — Limits on this documentation sweep.
- [Deferred](#deferred) — Work owned elsewhere.

## Why

The live documents still advertise dedicated conceptual application and chained execution commands. `docs/reference/commands.md` supplies runnable examples, `RUNBOOK.md` describes interactive and parallel application, and `docs/ARCHITECTURE.md` describes modules and dispatch paths that steps 2 and 3 remove. These instructions become unusable after retirement. The heuristic matches for command headings in `docs/reference/commands.md` and `RUNBOOK.md` do not indicate completed work; both files contain explicit removal targets.

## Input

- **Steps 2 and 3:** Consume their command-removal outcomes. Verify surviving command, module, and commit-surface claims against the resulting implementation; landed names take precedence over proposed names in sibling details.
- **Saved audit evidence:** Continue describing saved reports as evidence for review and re-audit. Command retirement does not change their readability or make report deletion part of this step.
- **Documentation consumers:** `tests/test_model_specs.py:test_model_family_docs_cover_every_supported_prefix()` reads `RUNBOOK.md` and `docs/ARCHITECTURE.md`. `tests/test_roadmap_format.py` checks live roadmap guidance, including `docs/demos/roadmap-demo.md` and `docs/ARCHITECTURE.md`. Preserve their unrelated contracts.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `docs/ARCHITECTURE.md` — remove retired module entries, application ownership, parallel application, and obsolete caller descriptions.
  - `docs/GATES.md` — replace conceptual-application instructions and preserve surviving gate and saved-report explanations.
  - `docs/how-to/pipeline/audit.md` — remove retired consumers and routes from audit guidance and bare/detail explanations.
  - `docs/reference/commands.md` — remove retired syntax, flag notes, and placeholder-table entries.
  - `docs/how-to/use-cases.md` — remove legacy availability guidance from the small-change workflow.
  - `RUNBOOK.md` — update command inventories, conceptual correction procedures, structural caller descriptions, and related troubleshooting.
  - `CONTRIBUTING.md` — correct the supported `--commit` inventory under “Driving a change to done.”
  - `README.md` — replace the retired-command paragraph and reference under “Completeness gates.”
  - `JIRA_FORMAT.md` — remove the retired pipeline consumer claim under “Which detail bundle grounds the export.”
  - `docs/how-to/pipeline/detail.md` — correct the applied-edit commit inventory.
  - `docs/how-to/recovery/README.md` — remove the retired walk from timeout-cap exceptions.
  - `docs/TRACKING.md` — replace human-TTY application advice and remove the retired command from “Useful commands.”
  - `docs/demos/roadmap-demo.md` — remove the operator-specific application contrast in “Phase 5 — audit the bare plan, before detail.”
  - `docs/GLOSSARY.md` — update the session-directed edit definition without changing the direct-route distinction.
  - `docs/how-to/pipeline/direct-pipeline.md` — delete the guide.

## Implementation

- **Foundational logic: live guidance names supported workflows.** Replace conceptual-application recipes with one ordered procedure: read the saved report, verify and judge findings, edit the appropriate plan or detail text, commit bounded corrections, and re-audit the changed snapshot. This procedure applies to human operators and orchestrating sessions.

- **Enumerate both command references and dependent explanations before editing.** Search the declared files for `completeness-apply`, `direct-run`, and `direct-jira`, then search for their concepts: sole mutator, paired apply, unattended pipeline, parallel apply, human-TTY walk, and withheld application routes. Record each site as an edit or an explained preservation; command-name replacement alone misses obsolete reasoning.

- **Update architecture ownership from the landed tree.** In `docs/ARCHITECTURE.md`, inspect “Module map,” “Detail-bundle state guides the audit route,” “Audit discovers; apply mutates,” “Parallel apply isolates then replays,” and “Completeness orchestration.” Remove descriptions of deleted machinery and correct handler and caller inventories. Keep the surviving audit orchestrator and shared review/reconcile machinery accurately described.

- **Preserve the distinction between audit repair and conceptual correction.** In `docs/GATES.md`, `docs/how-to/pipeline/audit.md`, and `RUNBOOK.md`, keep deterministic repair separate from judged conceptual edits. Bare-stage withheld actions must not imply that a material plan-body correction waits for detail authoring. Preserve qualification, freshness, checkpoint roles, blocking rules, convergence exits, and reconcile directionality.

- **Keep surviving application routes documented.** `docs/GATES.md` and `RUNBOOK.md` describe `data-contract-apply` beside conceptual application. Remove its comparison with the retiring command while preserving its saved-payload workflow. Likewise, retain generic review/reconcile walks, structural escalation callers that survive, and create/detail iteration behavior.

- **Remove obsolete inventories and examples completely.** In `docs/reference/commands.md`, remove the “Direct pipeline” subsection, runnable examples, and retired placeholder consumers. Sweep all occurrences in `RUNBOOK.md`, including “Address conceptual gaps,” command-cost tables, structural dispatch descriptions, and audit recipes. Replace the conceptual-gap section with the supported procedure rather than leaving an empty destination.

- **Keep configuration and flag descriptions grounded per consumer.** When trimming a shared option or commit inventory, check surviving consumers before removing the entry. Remove only claims belonging to retired routes; do not infer ownership from a section’s location.

- **Preserve demo review boundaries and glossary distinctions.** Edit `docs/demos/roadmap-demo.md` narrowly around conceptual correction; keep its review pauses, explicit delegation rules, coverage reporting, and roadmap settlement instructions. In `docs/GLOSSARY.md`, retain the distinction between session-directed edits and the broader direct-edit term.

- **Delete the pipeline guide and check inbound links.** Search for `docs/how-to/pipeline/direct-pipeline.md`, relative links to `direct-pipeline.md`, and the older `DIRECT_PIPELINE_FLOW.md` spelling. Update live links inside this step’s declared files. Leave historical references unchanged; identify any live inbound link outside the declared scope for reconciliation rather than silently expanding the edit.

- **Check heading links before renaming sections.** Removing the command suffix from `RUNBOOK.md`’s “Address conceptual gaps” heading changes its anchor. Search inbound links and local contents entries, then update affected links within scope. Use existing surviving guides as destinations instead of adding a replacement pipeline document.

## Tests

### Verification (non-code step)

The test-authoring gate does not apply to this `non-code` step; it keys on code change types. Use these checks without adding test files:

1. `retired_commands_absent_from_declared_live_docs` — search all surviving declared files for the three retired command names and confirm no matches remain.
2. `retired_architecture_and_workflow_claims_removed` — review vocabulary-search results and confirm no surviving prose describes the removed application walk, parallel replay, or chained pipelines as current behavior.
3. `deleted_pipeline_guide_has_no_in_scope_live_links` — confirm the guide is absent and declared live documents contain no links to it or its older spelling.
4. `changed_heading_links_point_to_existing_sections` — check local contents entries and inbound links for every changed heading.
5. `historical_artifacts_remain_unchanged` — inspect the diff and confirm historical plans, reports, and `docs/history/backlog-decisions.md` have no edits.
6. `tests/test_model_specs.py:test_model_family_docs_cover_every_supported_prefix` — passes with surviving model-family documentation intact.
7. `tests/test_roadmap_format.py` — passes with roadmap guidance and demo contracts intact.
8. `documentation_regression_suite` — run `uv run pytest tests/test_roadmap_format.py tests/test_model_specs.py -q`, followed by the required full-suite check, and inspect failures before changing documentation expectations.

## Acceptance criteria

- The surviving declared documents contain no `completeness-apply`, `direct-run`, or `direct-jira` references.
- `docs/how-to/pipeline/direct-pipeline.md` is deleted.
- Declared live documents contain no broken links caused by the deletion or changed headings.
- Conceptual correction guidance consistently directs readers through saved-report review, judged edits, commits, and re-audit.
- Architecture and command inventories match the surviving implementation from steps 2 and 3.
- Documentation preserves the audit and surviving-route contracts named in the plan’s scope fence.
- `tests/test_roadmap_format.py` and `tests/test_model_specs.py` pass.
- The diff contains only the declared documentation changes; historical plans, reports, and `docs/history/backlog-decisions.md` remain unchanged.

## References

- [BACKLOG.md](../../../BACKLOG.md) — Read entry #376 for the retirement decision and retire-outright disposition.
- [BACKLOG.md](../../../BACKLOG.md) — Read entry #369 for the separate boundary around surviving finding-application callers.
- [Documentation style](../../../docs/reference/documentation-style.md) — Follow its task-first structure, scanning guidance, and terminology for direct and session-directed edits.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent:** Keep this sweep focused on accurate live documentation for the surviving workflow.
- **The plan’s “## Scope guardrails”:** Describe the outcomes of retirement without changing runtime behavior or introducing replacement orchestration.
- **The plan’s “## Out of scope”:** Preserve documentation for surviving routes and leave historical evidence untouched.
- **The step’s declared file boundary:** Keep edits within the listed documents; report any necessary external link repair for scope reconciliation.

## Deferred

- Driving instructions and backend skills — step 4 owns their universal conceptual-correction guidance.
- Parser-generated command references and help snapshots — steps 2 and 3 own removal alongside command registration.
- Historical plans, reports, and `docs/history/backlog-decisions.md` — preserve their contents as the plan requires.
- Live references outside the declared files — identify any remaining actionable sites for reconciliation rather than broadening this documentation sweep.
