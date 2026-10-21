> **Retired 2026-08-19** — Durable remedy provenance and same-issue matching
> cannot establish that an earlier edit caused a later model finding. The
> proposed classifier is disproportionate to that uncertainty; retain the
> operator scope-decision workflow, not this product feature.
> Preserved here for history; do not resume.

---
title: Bad Fix Provenance
intent: Help operators distinguish structural recurrence from findings likely caused
  by an intervening remedy so they can re-check the last edit without changing convergence
  behavior.
status: planning
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
steps:
- id: 1
  title: Add immutable source-report and ordered remedy-event history to annotations,
    migrate legacy sidecars, and preserve serialized sidecar updates
  intent: Each remedy remains attributable to an immutable source finding and report,
    in a total order that survives repeated annotations and legacy sidecars.
  files:
  - plan_tool/review_persistence.py
  - DATA_CONTRACT.md
  - tests/test_review_persistence.py
  - tests/test_review_walk.py
  - tests/test_data_contract.py
  complexity: high
  change_type: feature
  status: current
- id: 2
  title: Save qualified parallel remedy events; preserve canonical replay overwrite/delete,
    rollback restore/delete, and worktree reset/removal cleanup
  intent: Unattended applied remedies produce causal provenance without weakening
    isolation, rollback, cleanup, or distinct-event history.
  files:
  - plan_tool/cli/completeness_apply_parallel.py
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_apply_parallel.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the ordered annotation history and shared persistence contract.
- id: 3
  title: Add exact completeness-record selection for hand-applied or declined remedies
    and serialize the chosen sidecar update
  intent: Assistant-driven edits and deliberate declines remain visible, while only
    an exact selected applied remedy can become causal provenance.
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/app.py
  - plan_tool/cli/__init__.py
  - CAPABILITIES.md
  - docs/cli/README.md
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_app_lock.py
  - tests/cli/test_cli_parser.py
  - tests/cli/test_package_surface.py
  - tests/cli/package_surface_help.golden.txt
  - tests/test_capability_catalog.py
  creates:
  - docs/cli/completeness-record.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the durable remedy-note writer and legacy-safe annotation schema.
- id: 4
  title: Share conservative issue-skeleton and fuzzy-title matching without changing
    current finding IDs or matches
  intent: The new diagnostic recognizes the same issue only through usable evidence,
    without broadening existing recurrence matching.
  files:
  - plan_tool/review.py
  - plan_tool/convergence_diagnosis.py
  - tests/test_review.py
  - tests/test_convergence_diagnosis.py
  complexity: low
  change_type: refactor
- id: 5
  title: Match eligible recurring completeness findings to the closest earlier qualified
    remedy using conservative anchor, issue-skeleton, and title identity
  intent: The diagnostic separates an independently recurring seam from an issue
    connected to one qualifying earlier applied remedy in the same history stream.
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  creates:
  - tests/fixtures/convergence/bad-fix-remedy-history.json
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  - 4
  depends_on_notes:
    1: Provides ordered, legacy-safe remedy-note history.
    2: Supplies provenance from the parallel apply path.
    3: Supplies provenance from assistant-driven hand application and deliberate decline.
    4: Provides the shared issue-skeleton and fuzzy-title identity helpers.
- id: 6
  title: Render provenance-backed likely-bad-fix and requires-scope-review advice while
    leaving unmatched recurrence, plans, remediation, gates, and exits unchanged
  intent: An auto-driven session stops additional hand-apply or re-audit churn for a
    matched recurrence and surfaces the operator's scope choice without claiming a cause.
  files:
  - plan_tool/convergence_diagnosis.py
  - plan_tool/cli/completeness_cmd.py
  - tests/test_convergence_diagnosis.py
  - tests/cli/test_convergence_cmd.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  depends_on_notes:
    5: Provides the matched finding and intervening remedy evidence consumed by both
      render surfaces.
- id: 7
  title: 'Document remedy-note provenance and close BACKLOG #231'
  intent: Future operators record hand-applied remedies and interpret likely-bad-fix
    advice without mistaking it for a gate or automatic remediation.
  files:
  - integrations/shared/DIRECTIVES.md
  - CLAUDE.md
  - docs/AUDIT_FLOW.md
  - docs/ARCHITECTURE.md
  - RUNBOOK.md
  - README.md
  - USE_CASES.md
  - BACKLOG.md
  complexity: high
  change_type: non-code
  depends_on:
  - 3
  - 6
  depends_on_notes:
    3: Provides the landed hand-apply recording command the workflow documentation
      names.
    6: Provides the final advisory semantics and unchanged enforcement boundaries.
---
# Bad Fix Provenance

## Overview

Implement BACKLOG #231 so the convergence diagnostic distinguishes a recurring structural seam from a finding traceable to an intervening successfully applied remedy. Persist immutable remedy evidence through saved audit annotations for every apply path, and use it to render a recommend-only likely-bad-fix and `requires-scope-review` advisory. An auto-driven session responds to that route by stopping further hand applies or re-audits and surfacing an operator choice; the CLI stays advisory. Existing recurrence behavior remains when no qualifying match exists, and exits, gates, plans, and remediation remain unchanged.

## Problem statement

The convergence diagnostic cannot distinguish an independently recurring structural seam from a finding that follows an attributable, applied remedy. Without immutable evidence for both the remedy and the later recurrence, an apparently repeating finding can be reported as a decomposition problem even when an operator must first inspect the last edit.

## Architecture

Reuse saved audit annotations as the durable store for immutable remedy events across interactive, parallel, and explicit hand-recording paths; do not introduce a separate store. Every newly saved final completeness audit receives a write-once `source_report_id` and `source_occurred_at`, captured before filename reservation. Its source-report order is `(source_occurred_at, source_report_id)`; the opaque identifier is a stable tie-breaker only for equal capture times. Filename, file modification time, collision-reserved timestamp, and a later sidecar rewrite never participate in temporal order.

Each remedy event retains its immutable source report id and source-report order, the full selected `Recommendation` snapshot, disposition, `writer_attempt_id`, and a per-source `event_sequence`. Event identity is `(source_report_id, recommendation_id, disposition, writer_attempt_id)`; an attempt id is created once when one selected finding is dispatched and stays unchanged through a persistence retry after a failed write. A repeated or re-walked dispatch creates a new attempt id, even when it selects the same finding. The shared serialized writer allocates `event_sequence` after loading the source report's retained event history, so the total order is `(source_report_order, event_sequence)` and every distinct accepted dispatch remains visible through report collapse.

Every disposition remains visible to an operator, but only an event with disposition `applied`, an attributable action result, and an eligible source report is qualifying causal evidence. A deliberate decline, failed or halted attempt, generated skip, persistence-only legacy annotation, or record without the new source/event fields remains non-causal and never produces “re-check the last edit” advice.

The hand-record command requires an explicit saved-report identity and one exact recommendation identity; it never selects the newest report implicitly. Before it writes, the selected sidecar must be a `completeness` report with an ordinary final role, a known `bare` or `detail` audit stage, and `project_saved_completeness_result(...).is_current_final_qualified` at recording time. The selected recommendation must occur exactly once in that sidecar. Checkpoint, legacy, reconcile, missing, duplicate, stale, unconfirmed, non-final, or unknown-stage selections write nothing. The resulting event retains the accepted stage; a later recurrence is eligible only when it is a newer final completeness report at that same stage.

The diagnostic preserves each event's source snapshot when adjacent reports collapse, considers the newest current recurrence, and selects the closest earlier qualifying remedy under the persisted order. Recommendation id is only an index hint because content-addressed ids can churn; it neither proves nor disproves identity. At each ordered identity tier, an unavailable signal falls through and a usable conflicting signal rejects the candidate: compare anchors when both are usable, otherwise normalized issue skeletons when both are usable, otherwise non-empty normalized titles at the existing fuzzy threshold. A candidate with no usable shared signal never matches. Existing structural recurrence matching stays unchanged for unmatched findings.

A qualifying match emits the likely-bad-fix advisory, the preserved evidence reference, and `requires-scope-review`; it suppresses only the structural recommendation for that same recurrence. The CLI does not change its exit status or stop reason. An auto-driven session treats the route as a stop for further hand applies and re-audits, then asks the operator to proceed, redesign, or defer after reviewing the evidence. The route reports correlation rather than asserting that the earlier remedy caused the later finding. Unrelated structural advice remains unchanged.

## Input

Saved audit annotations are the persistence contract consumed by this plan. New causal records carry the source-report identity and order, retained recommendation snapshot, disposition, writer-attempt identity, per-source event sequence, and source stage. Legacy annotations remain readable but lack the required evidence and are never promoted into causal records. The comparison consumes only the retained snapshot and the later final completeness finding; it does not compare full Claude prose, storage metadata, or Git history.

## References

- [Python 3.13 — dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Covers frozen records, field defaults, and asdict serialization for extending persisted annotation and advisory models.
- [Python 3.13 — json](https://docs.python.org/3.13/library/json.html) — Documents JSON encoding and decoding behavior needed to evolve saved audit sidecars compatibly.
- [Python 3.13 — os](https://docs.python.org/3.13/library/os.html#os.replace) — Documents replacement and synchronization primitives used for durable annotation-file updates.
- [Python 3.13 — argparse](https://docs.python.org/3.13/library/argparse.html) — Covers subcommands, required arguments, and validation for any remedy-recording CLI surface.
- [Python 3.13 — difflib.SequenceMatcher](https://docs.python.org/3.13/library/difflib.html#difflib.SequenceMatcher) — Defines the similarity algorithm and heuristics relevant to the existing fuzzy-title matching fallback.
- [Python 3.13 — datetime](https://docs.python.org/3.13/library/datetime.html) — Covers aware UTC timestamps, ISO parsing, and comparisons needed to identify intervening remedy events safely.
- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — Documents fixtures and capture APIs useful for synthetic history, persistence, and CLI advisory tests.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changes to exit codes, stop reasons, or gates — the diagnostic remains advisory only.
- Changes to plan files or automatic remediation — remedy notes affect diagnostic rendering only.
- A new persistence store — saved audit annotations remain the durable record.
- A generic “spinning” verdict or a retrospective causal classification of #297 — the route requires a qualifying persisted remedy event and is evidence for an operator choice, not a count-based classifier.

## Risks

- **Legacy annotation migration loses, reorders, duplicates, or collapses remedy evidence (high).** Keep legacy sidecars readable, preserve every new event's source report, full finding snapshot, writer-attempt identity, source stage, and total order across repeated annotations, and cover old-to-new round trips; malformed or future-schema sidecars remain an explicit read failure rather than evidence the diagnostic may silently trust.
- **Clock or filename collisions reverse a remedy and recurrence (high).** Capture source occurrence before filename reservation, compare only the persisted source-order key, and use the immutable report id only to break an equal capture time; tests must prove a reserved filename timestamp or a subsequent rewrite cannot create an advisory.
- **A concurrent or failed sidecar update loses provenance (high).** Serialize every whole-file update before atomic replacement while preserving replay, rollback, worktree-reset, and cleanup guarantees; storage and operating-system failures can still prevent a note from being recorded, so absence of provenance is never proof that no remedy occurred.
- **Identity fallbacks associate a recurrence with the wrong remedy or miss a real association (high).** Test anchor, issue-skeleton, and fuzzy-title tiers independently, including unavailable and conflicting higher-tier signals, and preserve existing unmatched behavior; fuzzy or evolving titles remain advisory evidence rather than a basis for gates or automatic remediation.
- **An apply path omits, duplicates, or misqualifies a remedy event (medium).** Exercise interactive, parallel, and exact hand-recording paths with retries, applied and deliberately declined outcomes; only attributable applied events qualify, and edits outside the recording surfaces remain unattributed and require operator judgment.
- **Operators mistake likely-bad-fix advice for a structural verdict (medium).** Label and document the result as a recommend-only `requires-scope-review` prompt to re-check the preserved remedy evidence while preserving exits, gates, plans, and remediation; the final classification remains an operator judgment.

## Testing

Cover write-once source report identity and order, filename-collision and rewrite independence, persisted event identity, persistence retry versus a re-walked dispatch, and total ordering including ties. Cover source-snapshot preservation across collapsed reports; qualification and serialized writer contention; explicit final/current/qualified same-stage hand selection and every write-nothing failure; unavailable versus conflicting anchor, skeleton, and title tiers; and matched-advisory precedence, `requires-scope-review`, unchanged CLI exits, and unmatched structural advice with synthetic history fixtures.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (refactor) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- The convergence diagnostic distinguishes an independently recurring structural seam from a finding traceable to an earlier qualifying applied remedy in the eligible same-stage completeness history.
- Every new final completeness report has immutable source identity and order independent of filename reservation and later rewrites; every writer records a durable, source-attributable event with its original recommendation snapshot, writer-attempt identity, and persisted total-order key, serializes its whole sidecar update, deduplicates only persistence retries, and preserves every distinct accepted rewalk across report collapse.
- A hand record names exactly one explicit final, current, qualified known-stage completeness sidecar and one exact finding or writes nothing; declines and non-remedy dispositions remain visible but never causal.
- Issue matching treats recommendation id as an index hint only; an unavailable tier falls through, a usable conflict rejects, and a match requires the first usable shared anchor, normalized issue skeleton, or non-empty title tier to agree.
- A qualifying match renders a recommend-only likely-bad-fix advisory and `requires-scope-review` route with its preserved evidence, suppresses only the matching structural recommendation, and causes an auto-driven session to surface an operator choice rather than continue automatic hand-apply or re-audit churn; unmatched and unrelated recurrence behavior is retained.
- Exit codes, stop reasons, gates, plan files, and automatic remediation remain unchanged.

## Deferred

- No work is deferred by this plan.
