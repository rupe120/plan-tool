> **Withdrawn 2026-08-11** — Withdrawn after the detail-stage audit exposed an unresolved high-severity provenance-ordering defect and non-convergent correctness contracts; re-seed the capability from the audited invariants before implementation.
> Preserved here for history; do not edit.

# Step 3 — Add the completeness-record command for hand-applied findings

## Summary

Add `plan-tool completeness-record` as a completeness-family command that writes one hand-applied finding disposition to a selected saved completeness sidecar. The handler and parser registration live in `plan_tool/cli/completeness_cmd.py`; `plan_tool/cli/app.py`, `plan_tool/cli/parser.py`, and `plan_tool/cli/__init__.py` expose it consistently. The key rule is to validate the selected report, finding selector, disposition, and note before calling the Step 2 annotation writer. On green, an operator can record an applied remedy or deliberate decline without running Claude or mutating the plan.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the new command and its result.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why hand-applied findings need a durable record path.
- [Input](#input) — Saved-review, annotation, and lock contracts this command uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — Code, generated reference, catalog, and test changes.
- [Implementation](#implementation) — Command behavior, selection rules, lock timing, and CLI wiring.
- [Tests](#tests) — Focused command, lock, help, and generated-doc coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Standard-library references for the command and sidecar write.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this command.
- [Deferred](#deferred) — Related work intentionally left to later steps.

## Why

A manual remedy can close a completeness finding without passing through `plan_tool/review_walk.py:walk_recommendations`, leaving no annotation for later history to inspect. Step 2 makes `plan_tool/review_persistence.py:Annotation` capable of carrying qualified operator evidence, but operators still need a safe command that attaches that evidence to the exact saved finding they edited. This command closes that gap while retaining the existing sidecar as the only provenance store.

## Input

- **Step 2 annotation contract:** Step 2 provides the provenance-bearing `plan_tool/review_persistence.py:Annotation` and the shared `plan_tool/review_persistence.py:update_annotation` writer. This command supplies an explicit operator disposition and note; the writer remains responsible for durable sidecar handling and report identity.

- **Saved completeness report contract:** Follow `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` when selecting the newest `*-completeness.json` sidecar by default and when applying its `--id` override. Use `plan_tool/review_persistence.py:list_saved_reviews`, `resolve_saved_review`, and `load_review` without silently falling back from a requested report.

- **Finding identity contract:** Select from the loaded `Recommendation` objects by their distinct `id` and `anchor` fields. A record-id selector and an anchor selector have different meanings; do not overload the saved-report `--id` option as a finding selector.

- **Lock contract:** `plan_tool/repo_lock.py:repo_mutation_lock` already gives `plan_tool/cli/app.py:main` a repo-wide lock around mutating command dispatch. No lock-protocol change is expected; the new command must join the existing policy before its handler reads or rewrites a sidecar.

## Files (creates vs edits)

- **New files:**
  - `docs/cli/completeness-record.md` — generated command reference for the new parser surface.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` — add `cmd_completeness_record` and register its parser with the completeness commands.
  - `plan_tool/cli/app.py` — re-export the handler into the application namespace and add the command to `_LOCKED_MUTATING_COMMANDS`.
  - `plan_tool/cli/parser.py` — place `completeness-record` beside the completeness commands in `CANONICAL_COMMAND_ORDER`.
  - `plan_tool/cli/__init__.py` — add the command to the intent catalog and curated command export surface.
  - `CAPABILITIES.md` — add `completeness-record` to the `plan-completeness` capability’s surfaces in the same change as registration.
  - `docs/cli/README.md` — regenerate the CLI reference index so it links to the new command.
  - `tests/cli/package_surface_help.golden.txt` — rebaseline the intentional top-level help change.
  - `tests/cli/test_completeness_cmd.py` — add command-level selection, validation, persistence, and contention coverage.
  - `tests/test_repo_lock.py` — extend the generic lock coverage to include the new command as a contending writer.

## Implementation

- **Foundational logic: validate one selected finding before one annotation write.** Add `cmd_completeness_record` in `plan_tool/cli/completeness_cmd.py` as a small read-select-validate-write handler. It must not invoke Claude, alter a plan file, re-run an audit, or walk unrelated findings.

- **Match completeness-apply’s report selection.** Use the selection behavior in `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply`: with no `--id`, choose the newest path whose name ends in `-completeness.json`; with `--id`, select only that exact saved report. Load the result and reject a non-completeness save rather than choosing another report.

- **Require an unambiguous finding.** Require a record id, an anchor, or both. A record id must identify one `Recommendation.id`; an anchor must identify exactly one `Recommendation.anchor` unless the supplied record id identifies that same recommendation. Reject missing selectors, unknown selectors, an ambiguous anchor without a matching record id, and record-id-plus-anchor conflicts before calling `update_annotation`.

- **Make disposition explicit.** Expose a documented way to record either `applied` or a deliberate decline. Do not infer the disposition from whether a note exists. For an applied record, strip the supplied remedy text and reject an empty result; construct operator-authored evidence for the Step 2 writer. A deliberate decline must persist `status="skip"` with an empty `halt_reason`; an optional manually entered decline note remains operator text, while no note remains non-evidence.

- **Preserve write ordering.** Resolve the report and recommendation, validate all inputs, then call `plan_tool/review_persistence.py:update_annotation` once for the selected recommendation id. All validation failures must leave the sidecar unchanged. Do not create a second history file or rewrite report recommendations.

- **Acquire the lock before handler work.** Add `completeness-record` to `plan_tool/cli/app.py:_LOCKED_MUTATING_COMMANDS` so `plan_tool/cli/app.py:main` enters `repo_mutation_lock` before dispatching `cmd_completeness_record`. A held lock must return the existing lock error without the handler loading or changing the selected sidecar.

- **Keep CLI wiring coherent.** Extend `plan_tool/cli/completeness_cmd.py:register` and its dispatch map, add the handler import in `plan_tool/cli/app.py`, add the normal `cmd_completeness_record` export in `plan_tool/cli/__init__.py`, and place the command after `completeness-apply` in `plan_tool/cli/parser.py:CANONICAL_COMMAND_ORDER`. Do not add a second `COMMAND_MODULES` entry because `completeness_cmd` is already registered.

- **Regenerate derived surfaces.** Update `CAPABILITIES.md` with the command surface at registration time. Regenerate `docs/cli/completeness-record.md` and `docs/cli/README.md` through `plan_tool/cli_reference.py`; do not hand-edit generated CLI reference text. Rebaseline `tests/cli/package_surface_help.golden.txt` from the assembled parser after the catalog and canonical ordering are final.

## Tests

### Tests for this step

- `tests/cli/test_completeness_cmd.py:TestCompletenessRecord.test_defaults_to_newest_completeness_sidecar` — confirms a valid record writes only the newest eligible completeness sidecar.

- `tests/cli/test_completeness_cmd.py:TestCompletenessRecord.test_id_selects_exact_older_sidecar` — confirms `--id` updates the named older sidecar and leaves the newer sidecar unchanged.

- `tests/cli/test_completeness_cmd.py:TestCompletenessRecord.test_requires_finding_selector_without_mutation` — confirms no selector returns an error and preserves the selected sidecar bytes.

- `tests/cli/test_completeness_cmd.py:TestCompletenessRecord.test_ambiguous_anchor_requires_matching_record_id` — confirms an ambiguous anchor fails unless the record id identifies one member of that anchor set.

- `tests/cli/test_completeness_cmd.py:TestCompletenessRecord.test_conflicting_record_id_and_anchor_do_not_write` — confirms conflicting selectors fail without a sidecar rewrite.

- `tests/cli/test_completeness_cmd.py:TestCompletenessRecord.test_applied_record_requires_and_persists_operator_remedy` — confirms whitespace-only remedy text is rejected and a valid applied record persists stripped operator evidence through the Step 2 writer.

- `tests/cli/test_completeness_cmd.py:TestCompletenessRecord.test_decline_persists_deliberate_skip` — confirms a deliberate decline writes `status="skip"` with an empty `halt_reason`.

- `tests/cli/test_completeness_cmd.py:TestCompletenessRecord.test_held_lock_prevents_sidecar_read_or_write` — holds the repo lock, drives the command through `main`, and proves the handler does not load or modify the sidecar.

- `tests/test_repo_lock.py:test_repo_mutation_lock_refuses_completeness_record_contender` — confirms the generic lock reports `completeness-record` as the blocked contender without changing lock ownership.

- `tests/cli/test_package_surface.py:TestHelpGoldenSnapshot.test_help_matches_golden` — confirms top-level help, command ordering, and the intent catalog match the rebaselined snapshot.

- `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk` — confirms the new reference file and regenerated index exactly match the parser.

- `tests/test_capability_catalog.py:test_check_real_repo_catalog_is_honest` — confirms the registered command has an owning capability and the catalog names only live surfaces.

Every listed test must be green before this step is considered finished.

## Acceptance criteria

- A valid `completeness-record` invocation records exactly one selected completeness finding through `plan_tool/review_persistence.py:update_annotation` and makes no Claude call or plan-file edit.

- With no report override, the command updates the newest saved `*-completeness.json`; with `--id`, it updates only the named completeness report.

- Missing, unknown, ambiguous, or conflicting finding selectors return an error before the sidecar changes.

- An applied record rejects an empty or whitespace-only remedy note and persists stripped operator-authored note evidence through the Step 2 annotation contract.

- A deliberate decline persists `status="skip"` with an empty `halt_reason` and never becomes an applied remedy.

- A held repo mutation lock prevents the command from reading or writing the selected sidecar and returns the existing lock failure result.

- `completeness-record` appears in the parser dispatch, package command catalog, capability catalog, generated `docs/cli/` reference, generated index, and top-level help snapshot.

- The tests listed in `## Tests` are green.

## References

- [Python argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — Review subparser registration, required arguments, and mutually exclusive command inputs.

- [Python dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Review the immutable `Annotation` value passed to the shared writer.

- [Python json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Review the saved-sidecar representation that the command selects and updates.

- [Python os — `os.replace`](https://docs.python.org/3/library/os.html#os.replace) — Review the atomic replacement behavior used beneath the existing durable annotation writer.

## Applicable guardrails

- **The plan’s “## Plan intent”, recommend-only evidence boundary** — record hand-applied evidence only; do not add a bad-fix advisory, convergence decision, stop reason, or exit-code policy.

- **The plan’s “## Step intent”, selected-report and remedy boundary** — use completeness-apply’s default report selection and `--id` override, and require explicit remedy text only for an applied record.

- **The plan’s “## Out of scope”, storage and mutation boundary** — use the existing annotations sidecar and shared writer; do not add plan mutation, automatic remediation, or another provenance store.

- **The plan’s “## Out of scope”, identity and audit-loop boundary** — do not change `plan_tool/convergence_diagnosis.py:_matches`, stage-bar behavior, audit replay, or finding similarity rules.

## Deferred

- **Same-issue matching and bad-fix advisory rendering** — Steps 4 and 5 own the identity helper, history evaluation, and recommend-only output.

- **Broader provenance documentation** — Step 6 owns `DATA_CONTRACT.md`, guidance surfaces, and backlog closure; this step documents only the generated CLI command reference.

- **Shared completeness-report selector extraction** — `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` and `plan_tool/cli/data_contract_cmd.py:cmd_data_contract_apply` have related but intentionally different selection policies. Keep this feature scoped to matching completeness-apply and route any cross-command consolidation to a later reconcile step.
