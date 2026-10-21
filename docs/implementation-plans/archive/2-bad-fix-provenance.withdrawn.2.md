> **Withdrawn 2026-08-19** — 2026-08-19 plan-level review rejected the premise: no demonstrated problem shows that a provenance advisory changes an operator decision.
> Preserved here for history; do not edit.

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
  title: Add immutable ordered remedy-event history to annotations, migrate legacy
    sidecars, and preserve serialized sidecar updates
  intent: Each remedy remains attributable to its source finding and report, in a
    total order that survives repeated annotations and legacy sidecars.
  files:
  - plan_tool/review_persistence.py
  - DATA_CONTRACT.md
  - tests/test_review_persistence.py
  - tests/test_review_walk.py
  - tests/test_data_contract.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/archive/plan-details/bad-fix-provenance.2/01-immutable-ordered-remedy-event-history.md
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
  detail: docs/implementation-plans/archive/plan-details/bad-fix-provenance.2/02-save-qualified-parallel-remedy-events.md
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
    remedy by id, anchor, issue skeleton, and title
  intent: The diagnostic separates an independently recurring seam from an issue connected
    to one qualifying earlier applied remedy in the same history stream.
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
  title: Show likely bad fix advice while leaving unmatched recurrence, plans, remediation,
    gates, and exits unchanged
  intent: Operators re-check the last remedy before treating a matched recurrence
    as evidence that the plan is mis-decomposed.
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

Implement BACKLOG #231 so the convergence diagnostic distinguishes a recurring structural seam from a finding connected to an intervening applied or deliberately declined remedy. Persist remedy notes through saved audit annotations for every apply path, and use them to render a recommend-only likely-bad-fix re-check-last-edit advisory. Preserve existing recurrence behavior when no matching note exists, without changing exits, gates, plans, or remediation.

## Problem statement

The convergence diagnostic currently cannot distinguish an independently recurring structural seam from a finding that follows an applied or deliberately declined remedy. Without that distinction, recurrence can be reported without directing the operator to re-check the intervening edit.

## Architecture

Reuse saved audit annotations as the durable store for immutable remedy events across interactive, parallel, and explicit hand-recording paths; do not introduce a separate store. An event identity is the source report identity, selected finding identity, disposition, and writer attempt identity. Retrying that same writer attempt is idempotent; a later accepted rewalk receives a new attempt identity and remains a distinct event. Each event carries a persisted sequence allocated under the shared writer serialization rule; `(source report order, sequence)` is the total order, including equal timestamps. Every writer serializes its whole sidecar update before atomically replacing it.

Record every disposition for operator visibility, but only an attributable, successfully applied remedy is qualifying causal evidence. A deliberate decline, failed/halted attempt, generated skip, or legacy record remains visible and never produces “re-check the last edit” advice.

An explicit hand record accepts only one final, current, qualified completeness-audit sidecar and one finding from that sidecar at the compatible stage; checkpoint, legacy, reconcile, stale, missing, or ambiguous selections write nothing. The diagnostic compares only that eligible completeness-audit history at a compatible audit stage. It preserves event evidence across report collapse, considers the newest current recurrence, and selects the closest qualifying earlier remedy under the persisted order. Equal finding id only narrows candidates. At each later tier, unavailable evidence falls through, while usable conflicting evidence rejects the candidate; a match requires the first usable anchor, normalized skeleton, or title tier to agree. Existing recurrence matching stays unchanged.

An explicit hand record selects exactly one saved audit and one recommendation by stable identity; a missing, stale, or ambiguous selection writes nothing. A qualifying match emits only the likely-bad-fix advisory and defers the structural recommendation for that same recurrence. Unrelated structural advice remains unchanged.

## Input

Saved audit annotations are the existing persistence contract consumed by this plan. They carry immutable, ordered remedy events used to associate one qualifying applied remedy with a later completeness recurrence; matching uses id as a candidate filter, then usable anchor, normalized issue skeleton, or title evidence.

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

## Risks

- **Legacy annotation migration loses, reorders, duplicates, or collapses remedy evidence (high).** Keep legacy sidecars readable, preserve each event's source report and finding evidence with its writer-attempt identity and total order across repeated annotations, and cover old-to-new round trips; malformed or future-schema sidecars remain an explicit read failure rather than evidence the diagnostic may silently trust.
- **A concurrent or failed sidecar update loses provenance (high).** Serialize every whole-file update before atomic replacement while preserving replay, rollback, worktree-reset, and cleanup guarantees; storage and operating-system failures can still prevent a note from being recorded, so absence of provenance is never proof that no remedy occurred.
- **Identity fallbacks associate a recurrence with the wrong remedy or miss a real association (high).** Test equal-id, anchor, issue-skeleton, and fuzzy-title tiers independently and preserve existing unmatched behavior; fuzzy or evolving titles remain advisory evidence rather than a basis for gates or automatic remediation.
- **An apply path omits, duplicates, or misqualifies a remedy event (medium).** Exercise interactive, parallel, and exact hand-recording paths with retries, applied and deliberately declined outcomes; only attributable applied events qualify, and edits outside the recording surfaces remain unattributed and require operator judgment.
- **Operators mistake likely-bad-fix advice for a structural verdict (medium).** Label and document the result as a recommend-only prompt to re-check the last remedy while preserving exits, gates, plans, and remediation; the final classification remains a human judgment.

## Testing

Cover persisted event identity, retry versus rewalk distinction, and total ordering (including ties); source-evidence preservation across collapsed reports; qualification and serialized writer contention; exact final/current/qualified compatible-stage hand selection and every write-nothing failure; unavailable versus conflicting identity tiers; and matched-advisory precedence with synthetic history fixtures.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (refactor) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- The convergence diagnostic distinguishes an independently recurring structural seam from a finding traceable to an earlier qualifying applied remedy in the eligible completeness history.
- Every writer records a durable, source-attributable event with a writer-attempt identity and persisted total-order key, serializes its whole sidecar update, deduplicates only retries, and preserves every distinct accepted rewalk across report collapse.
- A hand record names exactly one final, current, qualified compatible-stage completeness sidecar and one finding or writes nothing; declines and non-remedy dispositions remain visible but never causal.
- Issue matching uses id only to narrow candidates; unavailable later-tier evidence falls through, while usable conflict rejects, and the first usable anchor, normalized issue skeleton, or title tier must agree.
- A qualifying match renders a recommend-only likely-bad-fix re-check-last-edit advisory and defers only the matching structural recommendation; unmatched and unrelated recurrence behavior is retained.
- Exit codes, stop reasons, gates, plan files, and automatic remediation remain unchanged.

## Deferred

- No work is deferred by this plan.
