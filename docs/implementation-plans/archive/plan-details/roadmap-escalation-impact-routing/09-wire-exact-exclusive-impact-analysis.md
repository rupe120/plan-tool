> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Wire exact exclusive impact-analysis creation and coordinated log-free views while preserving canonical, seed, receipt, local-revision, and broad write paths

## Summary

Extend `plan_tool/cli/roadmap_cmd.py` with the exact `--analyze-escalation RECEIPT_FINAL` creation path and the `--view impact-analyses` inspection path supplied by step 8. Add a reader-only coordination guard in `plan_tool/roadmap_revision_publish.py` so a nonempty analysis view cannot inspect mixed writer state. Keep all existing roadmap modes on their established handlers, then update the command catalog, operator documentation, capability catalog, and top-level help snapshot. Green means an operator can create one analysis from one named receipt or inspect current analyses without a backend call, broad re-entry, canonical write, or view telemetry.

## Table of Contents

- [Summary](#summary) — The completed command surfaces and their observable result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The missing operator path and the state-coordination risk it closes.
- [Input](#input) — The step 8 runner, immutable evidence, and existing command contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped command, guard, test, and documentation edits.
- [Implementation](#implementation) — Exclusive dispatch, guarded inspection, safe rendering, and compatibility rules.
- [Tests](#tests) — Focused CLI, lock, help, and capability coverage.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Primary references for advisory locking and controlled interleavings.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this command-surface step.
- [Deferred](#deferred) — Follow-on work that remains outside this step.

## Why

`plan-tool roadmap` can create and inspect structural-escalation receipts, but it has no way to bind one exact receipt to current impact evidence or to inspect those results safely while canonical writers run. Reusing the ordinary roadmap view would mix two evidence contracts and bypass the snapshot coordination required for current routing. This step adds the narrow operator surface while leaving receipt creation, local revision, seed work, and broad generation authoritative in their existing paths.

## Input

- **Step 8 planned output (dependency):** After step 8 lands, consume its frozen redacted runner/result and single-record current-inspection contract. Step 8 owns creation status mapping; this step owns argument handling, coordination, and rendering. The runner module does not exist at the current baseline.

- **Impact evidence:** Use step 6’s planned impact-analysis namespace extension with `scan_evidence` and `namespace_relative_components`. The namespace member is created by step 6; the CLI treats stored bytes as opaque until the step 8 inspection operation validates them.

- **Existing exclusive modes:** Preserve the occurrence tracking and dispatch rules in `plan_tool/cli/roadmap_cmd.py:_TrackRoadmapMode`, `_TrackEscalationOption`, `_has_receipt_creation`, `_escalation_creation_has_conflict`, `_escalation_view_has_conflict`, and `_revise_feedback_has_conflict`.

- **Existing coordination:** Extend the lock boundary rooted at `plan_tool/roadmap_revision_publish.py:roadmap_writer_lock_path` and `roadmap_writer_guard`. Broad roadmap work uses `plan_tool/roadmap.py:_roadmap_writer_owner`; local revision uses `plan_tool/roadmap_revision_run.py:run_local_feedback_revision`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Add the analysis flag, exclusive dispatch, safe result rendering, guarded impact-analysis view, and complete conflict handling.
  - `plan_tool/cli/__init__.py` — Add the two operator command forms to the roadmap command catalog.
  - `plan_tool/roadmap_revision_publish.py` — Add a noncreating reader-only guard over the existing roadmap writer-lock file.
  - `tests/cli/test_roadmap_cmd.py` — Cover parsing, exclusive dispatch, log-free views, safe rendering, and unchanged existing modes.
  - `tests/test_roadmap_revision_publish.py` — Cover reader/writer coordination and the reader guard’s no-write contract.
  - `tests/cli/package_surface_help.golden.txt` — Update the intentional top-level help snapshot.
  - `docs/cli/roadmap.md` — Document both new command forms and their exclusivity and side-effect boundaries.
  - `CAPABILITIES.md` — Extend the existing `architecture-roadmap` capability with the impact-analysis surfaces and behavior.

## Implementation

- **Foundational logic — dispatch one named analysis or inspect guarded immutable analyses.** Extend `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` with two paths: `--analyze-escalation RECEIPT_FINAL` calls step 8 for that exact final, while `--view impact-analyses` scans only impact-analysis evidence and validates it under reader coordination. Neither path may choose a receipt from scan order.

- **Preserve every analysis-flag occurrence.** Register `--analyze-escalation` with occurrence tracking equivalent to `plan_tool/cli/roadmap_cmd.py:_TrackEscalationOption`, so absent, single, and repeated values remain distinguishable. A final argparse value alone cannot prove that the operator supplied exactly one receipt final.

- **Give analysis creation exclusive dispatch priority.** Recognize `--analyze-escalation` before the ordinary broad-mode replay, receipt creation, local revision, seed operations, and normal roadmap views. Resolve the repository and plans directory as the receipt path does, then call `plan_tool/roadmap_impact_run.py:run_roadmap_impact_analysis` without an invoker. Return its typed status unchanged and render only its safe terminal outcome, analysis identity, route class, publication outcome, and named workflow when present. A completed `requires-scope-review` render is status `0` with no workflow, not a refusal or a broad fallback.

- **Send parseable conflicts to the runner’s redacted preflight.** When one otherwise valid analysis flag appears beside another roadmap action or modifier, pass the rejection state to step 8 rather than dispatching the companion action or printing raw input. Repeated or malformed analysis values must also end as a redacted no-record result. Let argparse retain ownership of malformed option grammars it already rejects before dispatch.

- **Keep all exclusive predicates complete.** Update the existing receipt-creation, receipt-view, local-revision, and broad-companion checks so each rejects analysis creation where required. Add matching analysis-creation and impact-view predicates that reject every other exclusive route, including repeated `--view` occurrences. Preserve the existing `--mode` and `--id` rules for ordinary views; neither refines `impact-analyses`.

- **Keep impact inspection outside ordinary roadmap views.** Add `impact-analyses` to the `--view` choices, but route it before `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view`. It must not call `plan_tool/roadmap_view.py:load_roadmap`, run a stage, invoke a backend, or create telemetry.

- **Scan twice around the reader guard.** First call `plan_tool/roadmap_evidence_store.py:scan_evidence` for `EvidenceNamespace.IMPACT_ANALYSES`. An empty namespace renders an empty result immediately and never opens a lock. For a nonempty first scan, acquire the reader guard, rescan the same namespace, and pass each rescanned record to step 8’s current-record inspection while the guard remains held.

- **Render only current safe routes.** Render a current analysis only from step 8's exact-byte/current-final-verified typed inspection result, including its safe identity, route, and named workflow. Inspection never renders `created` or `reused`: publication outcome belongs only to creation. Invalid, stale, unavailable, or guard-failed records must render a safe no-current-route status and never print a workflow. Do not echo raw evidence bytes, reviewer prose, artifact or brief content, configured paths, or raw flag values; derive any displayed evidence location through `plan_tool/roadmap_evidence_store.py:namespace_relative_components`.

- **Keep view status distinct from creation status.** A pure `--view impact-analyses` that reaches rendering returns `0` for empty, current, stale, unavailable, invalid, and guard-failed states: it completed a read-only inspection even when it found no route. A malformed, repeated, or companion-conflicted impact view returns usage status `2` before evidence access. Do not reuse the creation runner's `1` status for a no-route view.

- **Add a genuinely read-only coordination guard.** Add `roadmap_reader_guard` beside `roadmap_writer_guard` in `plan_tool/roadmap_revision_publish.py`. It must use the same advisory lock file at `roadmap_writer_lock_path`, take a shared reader lock where the platform supports it while writers retain their exclusive lock, release and close it reliably, and never yield a `RoadmapWriterToken`. It must require an already-created, usable lock file: do not create directories or files, initialize or truncate the lock, publish evidence, or persist any state. A reader-guard failure leaves the view log-free and unable to report a current route.

- **Preserve writer behavior and boundaries.** Keep `RoadmapWriterToken`, `require_roadmap_writer_token`, `preinvalidate_roadmap_seeds`, and `publish_revision_candidate` writer-only. The new reader guard must serialize with `plan_tool/roadmap.py:_roadmap_writer_owner`, `plan_tool/roadmap_revision_run.py:run_local_feedback_revision`, and step 8’s writer-guarded runner without changing their public behavior.

- **Update the operator-facing surfaces together.** Add both command forms to `plan_tool/cli/__init__.py`, `docs/cli/roadmap.md`, and `tests/cli/package_surface_help.golden.txt`. Document that creation is backend-free but uses its runner-owned immutable evidence and telemetry lifecycle, while the impact view is read-only and log-free. Extend `CAPABILITIES.md`’s `architecture-roadmap` entry with the impact-analysis modules from steps 1 through 8, without creating a second capability or changing its principle mapping.

## Tests

### Tests for this step

- `tests/cli/test_roadmap_cmd.py:test_analyze_escalation_preserves_absent_single_and_repeated_receipt_finals` — The parser records every analysis-final occurrence and accepts `impact-analyses` as a view choice.

- `tests/cli/test_roadmap_cmd.py:test_analyze_escalation_dispatches_one_exact_final_to_the_impact_runner` — A valid creation call forwards only the requested final and resolved paths, returns the runner status, renders separate route and publication facts, and renders no raw input.

- `tests/cli/test_roadmap_cmd.py:test_analyze_escalation_scope_review_is_successful_no_route` — A durable `requires-scope-review` result exits `0`, renders its created or reused publication fact, and prints no workflow or broad command.

- `tests/cli/test_roadmap_cmd.py:test_analyze_escalation_conflicts_reach_redacted_preflight_before_other_dispatch` — Parseable companions and repeated analysis flags cannot reach receipt, local-revision, seed, broad, or ordinary-view handlers.

- `tests/cli/test_roadmap_cmd.py:test_existing_exclusive_mode_predicates_reject_analyze_escalation` — Receipt creation, receipt view, and local revision retain complete companion rejection.

- `tests/cli/test_roadmap_cmd.py:test_impact_analysis_view_rejects_every_companion_before_evidence_access` — Modifiers, actions, and repeated views return usage without scanning evidence or starting telemetry.

- `tests/cli/test_roadmap_cmd.py:test_impact_analysis_view_empty_namespace_is_log_free_and_never_creates_a_lock` — An empty view prints the empty state without a run log, evidence path, or writer-lock file.

- `tests/cli/test_roadmap_cmd.py:test_impact_analysis_view_rescans_and_inspects_records_under_reader_guard` — A nonempty view rescans after lock acquisition and validates only the guarded record set.

- `tests/cli/test_roadmap_cmd.py:test_impact_analysis_view_withholds_workflow_for_noncurrent_or_invalid_records` — Stale, unavailable, invalid, and guard-failed records produce no route or workflow and disclose only safe status facts.

- `tests/cli/test_roadmap_cmd.py:test_impact_analysis_view_uses_read_only_statuses_and_no_publication_fact` — Empty/current/no-route rendered views return `0` and never render `created`/`reused`; malformed, repeated, and companion-conflicted views return `2` without evidence access.

- `tests/cli/test_roadmap_cmd.py:test_analysis_modes_leave_receipt_local_seed_broad_and_ordinary_view_dispatch_unchanged` — Existing receipt, local revision, seed, broad, and ordinary-view routes retain their handlers and outcomes.

- `tests/test_roadmap_revision_publish.py:test_reader_guard_blocks_a_writer_for_the_same_roadmap` — A reader guard and writer guard serialize for one slug while a different slug remains independent.

- `tests/test_roadmap_revision_publish.py:test_reader_guard_requires_an_existing_lock_without_creating_or_initializing_one` — Missing or unusable lock state fails without directory, lock-file, or lock-byte mutation.

- `tests/test_roadmap_revision_publish.py:test_reader_guard_preserves_existing_lock_bytes_and_never_yields_a_writer_token` — Reader coordination leaves the lock unchanged and cannot authorize writer-only helpers.

- `tests/cli/test_package_surface.py:TestHelpGoldenSnapshot.test_help_matches_golden` — The package-level help text matches `tests/cli/package_surface_help.golden.txt`.

- `tests/test_capability_catalog.py:test_repo_capabilities_doc_is_self_consistent` — The expanded roadmap capability remains parseable and references only real post-step surfaces.

- **Green-before-done gate:** `uv run pytest tests/cli/test_roadmap_cmd.py tests/test_roadmap_revision_publish.py tests/cli/test_package_surface.py tests/test_capability_catalog.py -q` passes.

## Acceptance criteria

- `plan-tool roadmap <slug> --analyze-escalation RECEIPT_FINAL` passes one exact final to the step 8 runner, invokes no backend or broad re-entry, and returns the runner’s closed `0`/`1`/`2`/`130` status with redacted terminal, route, publication, and workflow output.

- A repeated, malformed, or parseably conflicting analysis request creates no analysis and cannot dispatch any existing roadmap action.

- `plan-tool roadmap <slug> --view impact-analyses` scans only the step-6 impact-analysis namespace; an empty namespace opens no lock, and a nonempty namespace is rescanned and inspected while the reader guard is held.

- The impact-analysis view creates no telemetry, evidence, lock file, or canonical, feedback, seed, or receipt mutation; it emits no workflow or publication outcome for invalid, stale, unavailable, or uncoordinated records; and every completed rendered view exits `0`.

- `roadmap_reader_guard` serializes with the existing writer guard for the same slug, never yields a writer token, and never creates, truncates, or initializes the lock it reads.

- Existing receipt creation and inspection, local revision, seed operations, broad stage runs, and ordinary roadmap views retain their established dispatch and output contracts.

- `plan_tool/cli/__init__.py`, `docs/cli/roadmap.md`, `CAPABILITIES.md`, and `tests/cli/package_surface_help.golden.txt` describe the same two command forms and side-effect boundaries.

- The focused green-before-done test command passes.

## References

- [fcntl — The fcntl and ioctl system calls](https://docs.python.org/3.13/library/fcntl.html) — Use this for the advisory locking behavior shared by reader and writer coordination.

- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Use this for safe existing-file opens, lock-file handling, and descriptor cleanup.

- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use this for controlled dispatch, rescan, guard-failure, and no-side-effect tests.

## Applicable guardrails

- **The plan’s “## Step intent,” exact operator surface** — Limit this step to one named receipt-final creation path and one coordinated read-only view; keep analysis construction and validation in step 8.

- **The plan’s “## Architecture,” exclusive command forms** — Preserve exact selector ownership and reject companion modes without allowing a fallback to receipt selection, broad generation, or ordinary views.

- **The plan’s “## Architecture,” reader coordination** — Use the existing per-roadmap coordination boundary for nonempty inspection and report no current route when that boundary is unavailable.

- **The plan’s “## Architecture,” immutable and redacted evidence** — Render only validated safe facts and never repair, replace, or treat telemetry as record authority.

- **The plan’s “## Out of scope,” existing roadmap workflows** — Do not change receipt creation, broad generation, seed machinery, local revision semantics, or follow-on patch execution.

- **The plan’s “## Out of scope,” writer boundary** — Extend coordination only as needed for a read-only guard; do not widen writer authority or allow a view to obtain a writer token.

## Deferred

- Follow-on same-artifact and cross-artifact revisions — The named workflows remain responsible for any later canonical mutation after their own admission checks.

- Schema and workflow reference documentation — Step 10 owns the broader format, walkthrough, architecture, and runbook updates.

- A shared abstraction over receipt and impact lifecycle rendering — Their evidence contracts differ; consider consolidation only through a later reconcile decision.
