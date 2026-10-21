> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Read saved completeness artifacts as an ordered evidence ledger

## Summary

Add a read-only `AuditEvidenceLedger` reader in `plan_tool/convergence_diagnosis.py` and cover it with fixture-driven tests. The reader will pair saved completeness Markdown reports and JSON sidecars, preserve incomplete or unreadable artifacts as ledger rows, and project only saved metadata. Harden `load_review` so malformed bytes and annotations become its existing `ReviewLoadError` contract instead of aborting either reader. Its key design decision is to keep this evidence inventory separate from convergence decisions. On green, a caller can receive immutable, deterministically ordered rows without rendering output or changing diagnosis behavior.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the reader and its result.
- [Table of Contents](#table-of-contents) — Quick links to every section.
- [Why](#why) — Why the current history reader cannot provide this evidence view.
- [Input](#input) — Saved artifact contracts and limits the reader must honor.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files added and changed by this step.
- [Implementation](#implementation) — Reader behavior, state precedence, and ordering rules.
- [Tests](#tests) — Fixture-driven coverage for every reader state and invariant.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for filesystem, JSON, time, models, and tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep the ledger read-only.
- [Deferred](#deferred) — Later rendering, documentation, and comparison work.

## Why

`plan_tool/convergence_diagnosis.py:load_report_history` intentionally reads only JSON sidecars accepted as eligible convergence runs, so it skips report-only files, malformed sidecars, checkpoints, and unknown roles. Operators therefore cannot see the full saved completeness evidence without opening the reports directory themselves. This step adds a separate inventory that makes every completeness artifact visible without treating separate audits as comparable evidence.

## Input

- **Canonical directory:** Use `plan_tool/review_persistence.py:plan_reports_dir` for the requested plan. Read only `*-completeness.md` and `*-completeness.json`; do not treat the writer’s `*-completeness-data-contract.json` artifact from `plan_tool/completeness_report.py:_report_artifact_paths` as a ledger row.

- **Structured sidecars:** Parse JSON through `plan_tool/review_persistence.py:load_review` and retain `ReviewLoadError` as row state rather than letting it remove the artifact. Normalize invalid UTF-8 and malformed annotation maps to that same error contract. Project the persisted role, qualified result, audit revision, audit stage, and creation time exposed by `plan_tool/review_persistence.py:SavedReview`, plus `project_audit_coverage`, only as saved data.

- **Stored time fields:** Derive row ordering from the completeness filename timestamp, not `SavedReview.created_at`. Display a readable saved `created_at` value when valid and `invalid` when it is not; never repair it from filesystem metadata or current state.

- **No live validation:** Do not call `project_saved_completeness_result` or inspect current plan, detail, code, fingerprint, identity, sampling, or coverage inputs. A readable sidecar remains saved evidence even when its stored plan path or fingerprints do not match the requested plan.

## Files (creates vs edits)

- **New files:**
  - `tests/fixtures/convergence/audit-history-ledger.json` — Fixture data for paired, unpaired, malformed, checkpoint, final, and unknown-time completeness artifacts.

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — Add immutable ledger models and the saved-artifact reader without changing `load_report_history`, diagnosis helpers, or rendering.
  - `plan_tool/review_persistence.py` — Make malformed file bytes and malformed annotation maps raise `ReviewLoadError`, preserving the loader's malformed-sidecar contract for both readers.
  - `tests/test_convergence_diagnosis.py` — Materialize the fixture in a temporary reports directory and assert reader states, saved-field projections, pairing, ordering, and isolation.
  - `tests/test_review_persistence.py` — Prove invalid UTF-8 and `annotations: null` raise `ReviewLoadError` rather than leaking parser exceptions.

## Implementation

- **Add a separate reader:** Introduce a public reader such as `load_audit_evidence_ledger(plan_path)` plus frozen, display-ready row models in `plan_tool/convergence_diagnosis.py`. Return an empty ledger when `plan_reports_dir` is absent, and make the rows sufficient for step 2 to render paths, state, and saved metadata without reopening files.

- **Discover and pair artifacts from disk:** Scan the canonical reports directory directly because `plan_tool/review_persistence.py:list_saved_reviews` intentionally lists JSON only. Pair a Markdown report and JSON sidecar sharing the same `-completeness` stem; keep either unmatched file as its own row.

- **Use filename time for deterministic order:** Parse only the `YYYYMMDD-HHMMSS` prefix immediately before `-completeness`. Sort valid timestamps first, then each row’s normalized relative stem/path; keep invalid or manually named artifacts visible with filename time `unknown` after all valid-time rows, also ordered by normalized relative path. Do not use directory iteration order or saved `created_at` as a fallback.

- **Apply one state precedence rule:** Classify each row exactly once in this order:
  1. Markdown without a same-stem sidecar is `report-only`.
  2. Sidecar without a same-stem Markdown report is `orphan-sidecar`, regardless of readability or role.
  3. A paired unreadable, parser-rejected, invalid-UTF-8, malformed-annotation, or non-completeness sidecar is `malformed-sidecar`.
  4. A remaining paired sidecar whose persisted role is a checkpoint or unknown is `checkpoint`.
  5. A remaining paired readable completeness sidecar with the ordinary final role is `saved-final`.

- **Preserve readable orphan facts:** Attempt to load an orphan sidecar for saved metadata, but never promote its state to `saved-final` or `checkpoint`. Keep parser failures available as opaque metadata for later rendering while the row remains `orphan-sidecar`.

- **Project only safe saved facts:** Carry the filename time, saved creation time status, audit stage, captured detail grade, projected coverage state, and qualified-result headline, coverage, and revision state when they are present. Represent absent or malformed optional values as `unknown`; do not add fields to `SavedReview` or write normalized data back to disk.

- **Keep existing readers separate:** Leave `load_report_history` and its `HISTORY_KINDS`/ordinary-final eligibility rules unchanged. Do not reuse it for the ledger because its filtering is correct for convergence diagnosis but hides the evidence states this step must show.

- **Make saved-sidecar reads total:** In `load_review`, map `UnicodeDecodeError` during UTF-8 decoding and malformed annotation-map access such as `annotations: null` to `ReviewLoadError`. Do not catch unrelated programming errors and do not change save or annotation-rewrite behavior. `load_report_history` already skips `ReviewLoadError`, so this keeps its eligible-final policy while preventing one malformed sidecar from aborting `cmd_convergence`; the ledger then renders that sidecar under its defined opaque state.

- **Keep writing and prose out of this step:** Do not alter `plan_tool/completeness_report.py:write_completeness_report` or `plan_tool/review_persistence.py:save_review`. Step 2 owns rendered state-specific actions and integration with `plan_tool/cli/convergence_cmd.py:cmd_convergence`.

## Tests

### Tests for this step

- `test_load_audit_evidence_ledger_empty_without_reports_directory` — An absent canonical reports directory returns an empty immutable ledger.

- `test_load_audit_evidence_ledger_pairs_fixture_artifacts_and_projects_saved_metadata` — Fixture-backed paired entries retain report and sidecar paths plus saved stage, grade, coverage, qualified-result, and creation-time projections.

- `test_audit_evidence_entry_state_precedence` — Every pairing, parser, kind, and role combination yields exactly one of `report-only`, `orphan-sidecar`, `malformed-sidecar`, `checkpoint`, or `saved-final`.

- `test_orphan_sidecar_keeps_readable_saved_facts_without_state_promotion` — A readable unpaired final or checkpoint sidecar retains its saved facts while its state remains `orphan-sidecar`.

- `test_load_audit_evidence_ledger_marks_invalid_saved_created_at_and_optional_metadata_unknown` — Invalid stored timestamps and missing or malformed optional metadata display as opaque unknown values rather than failing or being inferred.

- `test_load_review_maps_invalid_utf8_and_null_annotations_to_review_load_error` — The saved-review loader preserves its malformed-sidecar contract for bad bytes and a null annotation map.

- `test_load_audit_evidence_ledger_keeps_loader_rejections_visible` — Paired and unpaired invalid-UTF-8 or malformed-annotation sidecars remain visible with their precedence-defined opaque state while the existing history reader skips them.

- `test_load_audit_evidence_ledger_orders_filename_timestamps_then_unknown_relative_paths` — Valid completeness filename timestamps sort first, same-stem pairs occupy one row, and manually named artifacts sort after them by normalized relative path.

- `test_load_audit_evidence_ledger_ignores_non_completeness_report_artifacts` — Review sidecars, notes, and completeness data-contract payloads do not become ledger entries.

- `test_load_audit_evidence_ledger_does_not_validate_saved_identity_or_freshness` — A readable final sidecar with stale-looking fingerprints or a mismatched stored plan path remains saved evidence without current-tree checks.

- `test_audit_evidence_ledger_rows_are_immutable` — Callers cannot mutate a returned row and change what step 2 renders.

Every listed test in `tests/test_convergence_diagnosis.py` and `tests/test_review_persistence.py` must be green before this step is complete.

## Acceptance criteria

- `load_audit_evidence_ledger` returns one ordered row for every `*-completeness.md` and `*-completeness.json` artifact in the requested plan’s canonical reports directory.

- A Markdown report and JSON sidecar with the same completeness stem produce one paired row; each unmatched artifact remains visible.

- Rows use the specified state precedence, including parser-rejected sidecars and unknown checkpoint-role metadata.

- Filename timestamps determine order; invalid filename timestamps display as `unknown` and sort after valid timestamps by normalized relative path.

- Readable rows expose only saved metadata, and malformed or absent optional data remains `unknown` rather than being validated against the current repository.

- Invalid UTF-8 and malformed annotation maps become `ReviewLoadError`; they remain visible in the ledger and cannot abort the existing history reader or command.

- `plan_tool/convergence_diagnosis.py:load_report_history` retains its current eligible-final history behavior.

- `uv run pytest tests/test_convergence_diagnosis.py tests/test_review_persistence.py -q` passes.

## References

- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3.13/library/pathlib.html) — Use for canonical directory discovery and deterministic path handling.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use for fixture payloads and malformed-sidecar cases handled by the saved-review reader.

- [datetime — Basic date and time types](https://docs.python.org/3.13/library/datetime.html#datetime.datetime.strptime) — Use for strict filename timestamp parsing and ordering.

- [dataclasses — Data Classes](https://docs.python.org/3.13/library/dataclasses.html) — Use for the frozen ledger and row models.

- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use to cover the complete state-precedence matrix without duplicating setup.

## Applicable guardrails

- **The plan’s `## Plan intent`, read-only saved-audit ledger:** Keep the reader an evidence display seam. It must not create a relationship, result, or decision across separate saved artifacts.

- **The plan’s `## Step intent`, accurate on-disk evidence:** Show missing, malformed, and incomplete artifacts instead of filtering them out for convenience.

- **The plan’s `## Out of scope`, no new authority:** Keep the work to classification and saved-data projection; do not add writes, persistence changes, freshness checks, or new command behavior.

## Deferred

- Ledger rendering, state-specific operator actions, and command integration — Step 2 consumes these ordered reader rows.

- Operator documentation for ledger states and limits — Step 3 owns the landed output and documentation.

- Trusted cross-invocation comparison — Deferred #303 owns any future provenance-backed trajectory feature.
