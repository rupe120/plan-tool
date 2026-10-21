# Step 11 — Remove the unversioned fallback branches from roadmap readers, and add a guard that no production code reads RoadmapStage.artifact_path, the resume directory outside the stage run, or INDEX.md, or reads or writes source.json

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step finishes the one-reader-path property after steps 3 and 6–10. It removes the unversioned branch from `plan_tool/roadmap_view.py:load_roadmap`. Step 10 already removed the unenrolled `--settle-decision` runner and its CLI fallback. This step removes the unenrolled arms in `plan_tool/roadmap_decision_settlement.py` and `plan_tool/roadmap_decision_settlement_receipt.py`. A folder with no accepted head makes `--view` and `--settle-decision` refuse with the step 6 no-published-version error. A new guard test scans production code for the four forbidden reads. On green, the version store is the only place any reader resolves roadmap content, and `source.json` cannot return.

## Table of Contents

- [Why](#why) — what unversioned branches remain after steps 3–10
- [Input](#input) — what earlier steps supply and what the trace must settle first
- [Files (creates vs edits)](#files-creates-vs-edits) — edits and the declared additions
- [Implementation](#implementation) — reader removal, settlement removal, the guard
- [Tests](#tests) — rewritten, deleted, and added cases
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left to other steps

## Why

- `load_roadmap` still falls back to the top-level `0N-*.md` files through `domain_path`, `constraints_path`, `components_path`, `plans_path` when `load_accepted_version` returns `None`. Step 3 no longer writes those files, so the branch only serves hand-converted or older folders and can show content that is not the accepted head.
- Step 10 removed the unenrolled `--settle-decision` runner and its CLI fallback, so the enrolled runner is the only dispatch target. What remains unversioned here is the reader arms in `plan_tool/roadmap_decision_settlement.py` and `plan_tool/roadmap_decision_settlement_receipt.py`.
- `plan_tool/roadmap_decision_settlement.py:build_decision_settlement_candidate` and `plan_tool/roadmap_decision_settlement_receipt.py:_unenrolled_receipt_proves_completion` both read stage files for a roadmap with no head.
- The plan's intent is one stored copy that every command reads. Without a guard, a later change can reintroduce a top-level read, a resume-directory read outside the stage run, an `INDEX.md` read, or any `source.json` access, and no test would fail.

## Input

- **Step 9 output:** `plan_tool/roadmap_escalation_selection.py` is deleted or trimmed. Its `admit_versioned_artifact_source` (imported by `plan_tool/roadmap_decision_settlement.py`) exists only for the unenrolled arm. Read the landed file. If a symbol the settlement leaf still needs was trimmed away, correct step 9's disposition rather than re-adding it here.
- **Step 10 output:** `require_unenrolled_roadmap_writer`, `publish_stage_artifact`, and the `source.json` helpers are gone. `RoadmapStage.artifact_path` still exists only if step 10 or an earlier step left it; this step removes the field if any producer remains.
- **Step 6 output:** `NoPublishedRoadmapVersionError` in `plan_tool/roadmap_seed_manifest.py`. Read its landed name, base class, and message. The landed names win over any name in this detail.
- **Step 2 output:** `plan_tool/roadmap_stage_resume.py` is the only module that builds, reads, or deletes the resume directory. Step 3 owns the stage-run call sites.
- **Step 5 output:** `plan_tool/roadmap_index.py` is the only module that writes `INDEX.md`. Only the wrapper in `plan_tool/roadmap.py` may call it.
- **Step 1 output:** the `BACKLOG.md` #441 record lists every `source.json` reader. Take the guard's `source.json` scope from there.
- **Caller trace (run first, at HEAD).** Run `rg` by identifier and by vocabulary: `artifact_path`, `domain_path`, `constraints_path`, `components_path`, `plans_path`, `is_roadmap_enrolled`, `ENROLLED_ROADMAP_FALLBACK_REFUSAL`, `enrolled-roadmap-rejected`, `unenrolled`, `source.json`, `INDEX.md`, `roadmap-stage-resume`. Write down every production hit and the disposition (removed here, removed by an earlier step, allowed).
- **Limit:** unit tests use literal version stores. They cannot show that Integration's hand-converted folder behaves; the post-ship hand run covers that.

## Files (creates vs edits)

- **New files:** none. The guard lives in an existing declared test file (see Tests), not a new module.
- **Existing files (edits only):**
  - `plan_tool/roadmap_view.py` — `load_roadmap` reads only the accepted head. Drop the unversioned branch, the `_load` closure, the loader and path imports, and the `absent` list if nothing else uses it. Update the module docstring paragraph that describes the unversioned roadmap.
  - `plan_tool/roadmap_decision_settlement.py` — remove the unenrolled arm of `build_decision_settlement_candidate`, the `stage.artifact_path` read, `admit_versioned_artifact_source` use, and `artifact_path` from `_DecisionSettlementStage`. Remove `"source-not-admitted"` and `"source-not-canonical"` verdicts if only that arm produced them. Add the no-head refusal.
  - `plan_tool/roadmap_decision_settlement_receipt.py` — remove `_unenrolled_receipt_proves_completion` and the `artifact_path` field of `_DecisionSettlementReceiptStage`. Decide the receipt `lineage` field per the constraint below.
  - `plan_tool/cli/roadmap_cmd.py` — step 10 already made `_cmd_roadmap_decision_settlement` call the enrolled runner directly. Update the module docstring paragraph for `--settle-decision`, and report the no-published-version error through the same rc 2 path as other refusals.
  - `tests/test_roadmap_view.py`, `tests/test_roadmap_decision_settlement.py`, `tests/test_roadmap_decision_settlement_receipt.py`, `tests/test_roadmap.py` — see Tests.
- **Declared additions (not in the step's file list; add them and say so in the commit):**
  - `plan_tool/roadmap_decision_settlement_enrolled.py` and `tests/test_roadmap_decision_settlement_enrolled.py` — the enrolled runner returns `"unenrolled-roadmap-rejected"` for a folder with no head. That branch becomes the no-published-version refusal. Edit only if the trace shows the old verdict leaks.
  - `tests/cli/test_roadmap_cmd.py` — settlement dispatch cases that assert the fallback.

## Implementation

**Behavior that must hold when the step is done:**

- **One reader path.** `load_roadmap` returns content only from `load_accepted_version`. A folder with no accepted head makes `--view` refuse with the step 6 no-published-version error, not a degraded partial view. All six views (`summary`, `walk`, `ledger`, `index`, `seeds`, `html`) share the single `load_roadmap` call at the top of `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view`, so the one refusal there covers each of them; no view form reads only the ledger, seed state, or draft seeds.
- **Settlement has one lineage.** `--settle-decision` always calls the enrolled runner. A folder with no head is refused with the same error. No path reads or writes a top-level artifact.
- **Per-artifact parse tolerance stays.** `_parse_accepted_artifact_bundle` still parses members independently, so one unparseable stored member does not hide the others. This is a read-only view contract, not an unversioned fallback.
- **A corrupt head is not "no head".** `load_accepted_version` raising `RoadmapVersionError` must keep propagating as it does today, distinct from `None`.

**Recommended approach:**

- Run the caller trace first. Then remove `load_roadmap`'s fallback, then the settlement arms, then the dispatch, then add the guard.
- For the no-head case, raise the step 6 error from `load_roadmap`. Then catch it at the `--view` call sites in `plan_tool/cli/roadmap_cmd.py` and map it to the existing rc 2 error output. Find the sites with `rg load_roadmap plan_tool`; other callers (for example `plan_tool/roadmap_html.py`) must be classified edit-or-unchanged.
- Rejected alternative: keep `load_roadmap` non-raising and return an empty `LoadedRoadmap` with every artifact listed absent. That keeps a degraded view that hides the missing head, which the plan's refusal rule forbids.

**Receipt `lineage` field.** `_DecisionSettlementSemanticFields.lineage` carries `"unenrolled"` or `"enrolled"`, and stored receipts may use either. Stored records stay on disk and nothing is migrated. Keep the field and keep the parser accepting both values, or readers of old receipts break. Stop producing `"unenrolled"`. If dropping the value from the `Literal` is cleaner, raise it under the plan's stop rule instead of deciding here.

**The guard (the key new behavior).** One test class in `tests/test_roadmap.py` scans `plan_tool/**/*.py` text and fails on each forbidden read. Reuse the repo's existing source-scan idiom (`tests/test_rate_limit_loop.py:test_leaf_has_no_first_party_runtime_import` reads module text). Do not hand-roll a regex over free text without checking; consider walking the AST for attribute and name nodes so a comment or docstring mentioning the term does not trip it.

- **Top-level artifact reads.** No production access to the attribute `artifact_path` on a stage, and no call to `domain_path`, `constraints_path`, `components_path`, or `plans_path` outside their defining module `plan_tool/roadmap_artifacts.py`. If step 3 or 10 left `RoadmapStage.artifact_path` as a dead field, delete it and assert the name is absent from `plan_tool/roadmap.py`.
- **Resume directory.** The resume directory name constant and `resume_dir_path` are referenced only by `plan_tool/roadmap_stage_resume.py` and the stage run in `plan_tool/roadmap.py`. Assert no other module imports `plan_tool.roadmap_stage_resume`.
- **`INDEX.md`.** The literal `INDEX.md` appears only in `plan_tool/roadmap_index.py`. No module other than `plan_tool/roadmap.py`'s wrapper imports that module, and nothing reads the file back.
- **`source.json`.** The literal `source.json` appears in no production module. Include `plan_tool/run_log.py` and `plan_tool/roadmap_artifacts.py`, which carry run-log event docstrings and fields for it today. If step 10 left a docstring mention, reword it rather than allowlist it.
- **Allowlist discipline.** Any allowlist entry carries a stated reason in the test. An entry with no reason is a disabled test.

**Constraints:**

- Do not touch `plan_tool/roadmap_evidence_store.py` or `plan_tool/roadmap_versions.py`. Settlement receipts still use the evidence store.
- Do not change candidate, review-seal, promotion, or version-record contracts, or the ledger format.
- A removed run-refusal literal (`"enrolled-roadmap-rejected"`, `"unenrolled-roadmap-rejected"`) also appears in `plan_tool/run_log.py` event sets. Sweep every site, by identifier and by the word "unenrolled". A site left behind stays green only because its own test pins the old value.

## Tests

Green-before-done gate: every test below, plus `tests/cli/test_roadmap_cmd.py`, must be green before this step is finished.

- `tests/test_roadmap_view.py`
  - `test_load_roadmap_without_accepted_head_raises_no_published_version` — no head, even with top-level files present, raises the step 6 error and reads none of them.
  - `test_load_roadmap_ignores_top_level_artifacts_when_head_exists` — stale top-level files differ from the head; the loaded roadmap shows the head's content.
  - `test_load_roadmap_corrupt_head_is_not_reported_as_no_head` — an invalid head raises `RoadmapVersionError`, not the no-head error.
  - `test_unparseable_member_does_not_hide_other_artifacts` — keeps per-member tolerance, pinned as deliberate.
  - Delete or rewrite the unversioned cases (the "absent artifact names" cases built from top-level files).
- `tests/test_roadmap_decision_settlement.py`
  - `test_no_accepted_head_is_refused_before_any_stage_file_read` — refusal with a top-level file present.
  - Delete the unenrolled-lineage and recorded-baseline admission cases.
- `tests/test_roadmap_decision_settlement_receipt.py`
  - `test_receipt_with_unenrolled_lineage_still_parses` — a stored legacy receipt parses, pinned as the live-legacy-record contract.
  - Delete `_unenrolled_receipt_proves_completion` cases.
- `tests/test_roadmap.py`
  - `test_no_production_module_reads_stage_artifact_path_or_top_level_path_helpers` — scan.
  - `test_resume_directory_is_referenced_only_by_the_stage_run_and_its_owner` — scan.
  - `test_index_md_is_written_only_by_the_index_module_and_never_read` — scan.
  - `test_source_json_appears_in_no_production_module` — scan.
  - `test_guard_flags_a_planted_violation` — run each scanner over a synthetic source string that contains the forbidden read and assert it is flagged. Verify each guard by mutation: add a forbidden read to a temp copy and watch it go red.
- `tests/cli/test_roadmap_cmd.py` — `test_settle_decision_without_accepted_head_exits_2`, a case that dispatch no longer calls an unenrolled runner, and `test_every_view_refuses_on_a_folder_with_no_accepted_head`, parametrized over `summary`, `walk`, `ledger`, `index`, `seeds`, and `html`, each exiting 2 with the no-published-version message.

## Acceptance criteria

- `load_roadmap` returns content only from `load_accepted_version`. A no-head folder raises the step 6 error, and each of the six `--view` forms exits 2 with that message.
- `rg 'run_unenrolled_decision_settlement|ENROLLED_ROADMAP_FALLBACK_REFUSAL|require_unenrolled_roadmap_writer' plan_tool tests` returns nothing.
- `rg 'source\.json' plan_tool` returns nothing.
- The four guard tests pass, and each goes red when a forbidden read is planted.
- `--settle-decision` on an enrolled roadmap still settles and writes its receipt.
- A stored receipt with `lineage: unenrolled` still parses.
- `uv run pytest tests/ -q -n auto` is green, and `tests/test_duplication.py` stays at zero groups.

## References

- `BACKLOG.md` #441 — source entry, scope contract, step 1 inventory.
- `ROADMAP_FORMAT.md` § "Immutable candidate-version authority" — accepted head and direct-reader boundary. Update it if it still names `load_roadmap`'s unversioned branch as a deferred reader.
- `plan_tool/roadmap_versions.py` — `load_accepted_version`, `ResolvedRoadmapVersion`.
- `plan_tool/roadmap_decision_settlement_enrolled.py` — the surviving settlement runner.
- `docs/ARCHITECTURE.md` "Decision-settlement receipts" — update the lineage description.
- `tests/test_rate_limit_loop.py:test_leaf_has_no_first_party_runtime_import` — source-scan idiom to mirror.

## Applicable guardrails

- The plan's "## Out of scope", candidate/seal/promotion/version-record contracts: this step reads those records only through `load_accepted_version` and the enrolled runner, and edits none of their contracts.
- The plan's "## Out of scope", ledger format: the step removes no ledger state here; `migration-pending` removal belongs to step 10.
- The plan's "## Out of scope", no tool-driven migration and no read-only top-level mirror: the no-head refusal names hand conversion and offers no import path.
- The plan's "## Out of scope", no dates in `INDEX.md` or version records: the guard only scans for reads and adds no field to either.
- The plan's "## Out of scope", no version-store route for structural rewrites or restore: do not add a replacement for anything removed here.
- Step intent: the guard asserts binary facts about code (a name or file is referenced or not). Do not extend it to judge meaning, and do not add exit-code gates.

## Deferred

- Hand conversion of Integration's roadmap folders — the plan converts Integration by hand after this ships; no tool route.
- Rewriting `docs/how-to/roadmap.md` and the `ROADMAP_FORMAT.md` sweep — owned by the plan's docs step.
- Dropping `"unenrolled"` from the stored receipt schema — a record-format decision for a separate backlog entry, if wanted.
- Consolidating the `unenrolled`/`enrolled` run-log refusal vocabulary beyond removing dead literals — out of this step's footprint.
