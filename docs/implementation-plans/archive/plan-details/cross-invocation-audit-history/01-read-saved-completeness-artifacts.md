> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Read saved completeness artifacts as an ordered evidence ledger

## Summary

Add a read-only ledger reader for saved completeness Markdown reports and JSON sidecars. Update `plan_tool/convergence_diagnosis.py` with immutable ledger models and `plan_tool/review_persistence.py` so malformed saved bytes consistently become `ReviewLoadError`. The key decision is that the ledger inventories saved artifacts without feeding `ReportHistory` or any convergence decision. On green, later command rendering can consume ordered, state-classified rows with saved metadata and a state-specific next action.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the ledger reader and its boundary.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why saved completeness evidence needs a separate reader.
- [Input](#input) — Saved-artifact and persistence contracts the reader consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files created or changed by this step.
- [Implementation](#implementation) — Ledger discovery, state rules, ordering, and isolation.
- [Tests](#tests) — Reader and persistence coverage for every artifact state.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for paths, parsing, models, and fixtures.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep the ledger read-only and non-decisional.
- [Deferred](#deferred) — Follow-up work outside this reader step.

## Why

`plan_tool/convergence_diagnosis.py:load_report_history` correctly hides malformed, checkpoint, report-only, and non-history artifacts from convergence verdicts, but that leaves an operator with no single view of what completeness evidence exists on disk. A separate reader makes those artifacts visible and actionable while preserving the current rule that visibility is not evidence of a trajectory, freshness, or valid comparison.

## Input

- **Canonical artifact location:** Use `plan_tool/review_persistence.py:plan_reports_dir` for the requested plan’s reports directory. Do not re-derive the directory layout or scan another plan’s artifacts.

- **Report producer shape:** `plan_tool/completeness_report.py:write_completeness_report` writes a `*-completeness.md` report and may write its same-stem `*-completeness.json` sidecar. A Markdown-only report is valid evidence for this ledger.

- **Sidecar parser:** Use `plan_tool/review_persistence.py:load_review` and `ReviewLoadError` as the sole JSON parser boundary. The persisted kind must be a string before the existing history reader tests it against `HISTORY_KINDS`; a non-string kind is malformed rather than readable evidence. Load each JSON sidecar once through the shared reader cache, then project the remaining saved role, audit stage, audit revision, qualified result, and creation time exposed by `plan_tool/review_persistence.py:SavedReview`, plus `project_audit_coverage`, only as saved metadata without consulting current plan or code state.

- **Existing decision path:** Keep `plan_tool/convergence_diagnosis.py:load_report_history`, `_is_final_report_role`, and `diagnose_convergence` separate. They continue to select eligible final history; the ledger reads a wider completeness-artifact inventory.

## Files (creates vs edits)

- **New files:**

  - `tests/fixtures/convergence/audit-history-ledger.json` — Define a reusable artifact matrix with expected ledger order, state, and saved-metadata projections.

- **Existing files (edits only):**

  - `plan_tool/convergence_diagnosis.py` — Add immutable ledger models and the public reader for completeness artifacts.

  - `plan_tool/review_persistence.py` — Normalize invalid UTF-8 and malformed annotation structures to `ReviewLoadError`.

  - `tests/test_convergence_diagnosis.py` — Cover pairing, ordering, state precedence, saved-field projection, and reader isolation.

  - `tests/test_review_persistence.py` — Cover the new `ReviewLoadError` normalization cases.

## Implementation

- **Foundational logic:** Build an ordered, immutable inventory of saved completeness artifacts, with exactly one state per Markdown/JSON pair or orphan.

- **Expose a reader-owned model:** Add frozen `AuditEvidenceLedger` and `AuditEvidenceRow` models, plus a public `load_audit_evidence_ledger` reader in `plan_tool/convergence_diagnosis.py`. A row must carry its artifact path or paths, filename-time display value, state, saved metadata, and display-safe next action; do not expose mutable `SavedReview` instances as the ledger contract.

- **Discover only completeness artifacts:** Enumerate the canonical directory from `plan_tool/review_persistence.py:plan_reports_dir` and consider only `*-completeness.md` reports and `*-completeness.json` sidecars. Do not treat `*-completeness-data-contract.json` payloads or other review kinds as ledger artifacts.

- **Pair by exact stem:** Treat same-stem Markdown and JSON files as one row. Keep a Markdown-only artifact as `report-only`; a readable unpaired `kind="completeness"` sidecar is `orphan-sidecar`, while an unreadable or wrong-kind sidecar is malformed even without Markdown.

- **Preserve the state precedence:** Classify a JSON sidecar as `malformed-sidecar` when it cannot be loaded through `load_review`, including invalid UTF-8, parser rejection, or a non-string kind, regardless of whether a Markdown pair exists. A readable string kind other than `completeness` is also `malformed-sidecar`. Classify a remaining unpaired sidecar as `orphan-sidecar`; then classify a paired sidecar with a confirmed pre-apply role as `checkpoint` and one with an unknown persisted role as `unknown-role`; only a paired, readable completeness sidecar with the ordinary final role becomes `saved-final`.

- **Keep readable orphan facts visible:** An `orphan-sidecar` may project the readable saved fields, but its state and next action remain orphaned. Do not let a readable final or checkpoint sidecar bypass that precedence.

- **Order from filenames, not payload claims:** Parse the generated `YYYYMMDD-HHMMSS` portion immediately before `-completeness` as the filename timestamp. Order valid timestamp rows chronologically and break ties with normalized relative artifact paths. Keep manually named or invalid-timestamp artifacts visible with filename time `unknown`, after valid-time rows and ordered by normalized relative path.

- **Project saved facts only:** For a readable sidecar, show a timezone-aware ISO-8601 saved `created_at` value or `invalid`, audit stage, captured detail grade from `SavedReview.audit_revision`, projected audit coverage, and qualified-result fields when they exist. This timestamp projection is independent of filename-time parsing and ordering. Represent absent or malformed optional values as `unknown`; do not call `project_saved_completeness_result`, recompute fingerprints, validate the saved plan identity, or inspect current files.

- **Assign actions without comparison:** Give `report-only`, `orphan-sidecar`, `malformed-sidecar`, `checkpoint`, and `unknown-role` rows an inspect-or-fresh-audit action. A `saved-final` whose saved headline is `no-qualified-current-evidence` directs a fresh audit; another known saved result directs the operator to the saved report and result; an unknown final result directs inspection and a fresh audit only when a qualified result is needed. The action must depend only on the row’s saved state.

- **Normalize parser failures:** Keep `plan_tool/review_persistence.py:load_review` as the single saved-sidecar boundary. Invalid UTF-8, structurally malformed annotation mappings, a non-string `kind`, and any type-incompatible required field that convergence history or diagnosis consumes must raise `ReviewLoadError`, like malformed JSON and unsupported versions. Validate the report text plus the recommendation id, source, severity, step id, title, body, action, and anchor shapes before `load_report_history` filters, matches, or renders them; do not add semantic validation or a new schema version. A malformed optional `qualified_result` or `audit_coverage` remains readable as `None`/`unknown`, and their normalizers must return that result for every JSON shape rather than raise. The kind check is required before `load_report_history` tests membership in `HISTORY_KINDS`; this changes no recognized string kind, no eligibility rule, and no writer. Preserve existing legacy annotation normalization and unknown-role behavior so an unknown role is readable `unknown-role` evidence, not a malformed sidecar or a claimed checkpoint.

- **Leave diagnosis untouched:** Do not route ledger rows through `ReportHistory`, `RunSnapshot`, finding matching, or advisory helpers. `load_report_history` remains the one filtered reader for convergence history.

- **Keep supplied snapshots coherent:** A caller-provided artifact snapshot or saved-review cache must contain only paths below the requested plan's reports directory, and a ledger cache must cover every supplied completeness sidecar. Reject a mismatch instead of treating an omitted or foreign sidecar as malformed evidence.

## Tests

- `test_load_audit_evidence_ledger_empty` — No completeness Markdown or JSON artifact returns an empty ledger for the renderer’s `no-saved-audits` state.

- `test_load_audit_evidence_ledger_pairs_same_stem_report_and_sidecar` — A same-stem Markdown report and readable final sidecar become one `saved-final` row.

- `test_load_audit_evidence_ledger_orders_filename_times_then_paths` — Valid filename timestamps order chronologically, equal times use normalized paths, and unknown filename times sort last.

- `test_load_audit_evidence_ledger_report_only_precedes_sidecar_interpretation` — A Markdown report without its JSON sidecar is `report-only`.

- `test_load_audit_evidence_ledger_orphan_sidecar_precedes_final_and_checkpoint_states` — Unpaired readable final and checkpoint sidecars remain `orphan-sidecar`.

- `test_load_audit_evidence_ledger_marks_unreadable_or_non_completeness_pairs_malformed` — Invalid JSON, invalid UTF-8, parser-rejected payloads, malformed annotations, non-string kinds, and non-completeness payloads become visible `malformed-sidecar` rows.

- `test_load_audit_evidence_ledger_unknown_role_is_distinct_not_malformed` — A paired, readable sidecar with unknown role metadata is `unknown-role`, not a confirmed checkpoint or malformed row.

- `test_load_audit_evidence_ledger_projects_saved_metadata_without_current_validation` — A readable row exposes only saved metadata and remains visible without checking current plan identity or freshness, including `created_at` as `invalid` when its saved value is not a timezone-aware ISO-8601 string.

- `test_load_audit_evidence_ledger_unknown_qualified_result_stays_unknown` — A supported final sidecar without a usable qualified result does not invent result metadata or a fresh-state claim.

- `test_load_audit_evidence_ledger_state_actions_depend_on_one_row_only` — Each action follows its row state and saved result without using another ledger row.

- `test_load_review_invalid_utf8_raises_review_load_error` — `plan_tool/review_persistence.py:load_review` converts invalid UTF-8 into `ReviewLoadError`.

- `test_load_review_malformed_annotations_raise_review_load_error` — A malformed annotations container or entry cannot leak an unrelated parser exception.

- `test_load_review_nonstring_kind_raises_review_load_error` — A JSON list, object, number, boolean, or null kind is rejected before a history consumer can use it as a membership key.

- `test_load_review_rejects_unsafe_convergence_fields` — A malformed required report field or diagnosis-consumed recommendation field is rejected before history filtering, matching, or severity rendering can use it.

- `test_load_review_optional_audit_metadata_is_total` — JSON collection values for optional qualified-result and coverage metadata load as unknown rather than raising.

- `test_audit_evidence_ledger_does_not_change_report_history` — Ledger discovery leaves `load_report_history` eligibility and final-history ordering unchanged.

### Tests for this step

Every listed test in `tests/test_convergence_diagnosis.py` and `tests/test_review_persistence.py` must be green before this step is complete.

## Acceptance criteria

- `load_audit_evidence_ledger` returns one immutable row for every saved completeness Markdown report and JSON sidecar, paired by exact stem where possible.

- Each row is exactly one of `report-only`, `orphan-sidecar`, `malformed-sidecar`, `checkpoint`, `unknown-role`, or `saved-final`, with the documented precedence.

- Invalid UTF-8, malformed annotation structures, non-string kinds, and unsafe required history fields surface as visible malformed ledger evidence and never abort the reader; malformed optional audit metadata remains readable as `unknown`.

- Rows expose only saved metadata; missing or invalid optional values display as `unknown`, with no plan-identity, freshness, coverage-admission, finding-match, or cross-row decision.

- Valid filename timestamps sort before unknown filename times, with deterministic normalized-path tie breaking.

- `load_report_history` and `diagnose_convergence` receive no ledger rows and retain their existing eligibility behavior.

- `uv run pytest tests/test_convergence_diagnosis.py tests/test_review_persistence.py -q` passes.

## References

- [pathlib — Object-oriented filesystem pathshttps: — Use for canonical directory enumeration, pairing, and normalized path ordering.

- [json — JSON encoder and decoderhttps: — Use for the parser failure boundary owned by `load_review`.

- [datetime — Basic date and time typeshttps: — Use for generated filename timestamp parsing.

- [dataclasses — Data Classeshttps: — Use for frozen ledger rows and the ledger container.

- [How to parametrize fixtures and test functionshttps: — Use to cover the artifact-state matrix consistently.

## Applicable guardrails

- **The plan’s `## Plan intent`, separate read-only ledger:** Keep rows as independent saved evidence. This reader cannot compare entries or produce a convergence decision.

- **The plan’s `## Step intent`, accurate on-disk view:** Preserve malformed and incomplete artifacts as visible rows rather than hiding them or repairing them.

- **The plan’s `## Out of scope`, no new authority:** Do not add persistence fields, live validation, mutation, backend work, or a new decision path while reading artifacts.

## Deferred

- Trusted cross-invocation comparison — #303 owns the provenance and evidence-admission work required before rows can be compared.

- Audit cache and recheck behavior — #173 remains outside this read-only inventory.

- Persisted coverage-format migration — #301 owns any saved-sidecar schema change.
