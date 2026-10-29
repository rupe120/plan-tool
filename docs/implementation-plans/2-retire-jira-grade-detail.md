---
format_version: 1
title: Retire Jira Grade Detail
intent: 'One implementation-detail input remains for Jira export: run-grade detail
  produces concise Jira stories and the paired developer handoff. Jira-grade detail
  has no artifact, selector, reader, or schema anywhere in the tree.'
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/archive/retire-jira-grade-detail.replaced.md
steps:
- id: 1
  intent: Finding annotations keep their fence protection after the Jira-grade module
    disappears.
  files:
  - plan_tool/jira_grade.py
  - plan_tool/review.py
  - tests/test_jira_grade.py
  - tests/test_review.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/retire-jira-grade-detail/01-move-fenced-spans-review-py-before.md
  status: current
  description: Move fenced_spans into review.py before deleting its Jira-grade owner.
    Preserve its citation-parsing behavior, including fences indented beyond three
    spaces, matching delimiter lengths, CRLF offsets, unclosed fences, and the current
    treatment of lines beginning with inline backtick spans. Keep scope_fence._fenced_code_spans
    unchanged. Pin these boundaries in unit tests, including test_indented_citation_fence_protects_the_boundary.
- id: 2
  intent: Detail authoring exposes only the supported implementation-detail route.
  files:
  - plan_tool/detail.py
  - plan_tool/cli/authoring.py
  - plan_tool/prompts/detail-jira.md
  - tests/test_detail.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/retire-jira-grade-detail/02-remove-detail-grade-remaining-jira.md
  description: Remove detail --grade and the remaining Jira-grade authoring functions
    and prompt; authoring already rejects that grade, so preserve the existing run-grade
    route rather than adding another rejection layer. Remove direct writer selectors
    as well. Retire Jira-grade overwrite and archive paths; preserve run-grade detail
    replacement, split migration and rollback renames, orphan archiving, temporary-input
    deletion, and saved-output writes. Add unit coverage for unchanged run-grade behavior
    and class-marked integration coverage for rejected CLI selectors.
- id: 3
  intent: Execution always uses the supported run-grade detail and its existing safeguards.
  files:
  - plan_tool/renderer.py
  - plan_tool/launcher.py
  - plan_tool/plan_merge_guard.py
  - plan_tool/cli/run_cmd.py
  - plan_tool/prompts/run-jira.md
  - tests/test_renderer.py
  - tests/test_launcher.py
  - tests/test_plan_merge_guard.py
  - tests/cli/test_run_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/retire-jira-grade-detail/03-remove-run-detail-grade-alternate.md
  description: Remove run --detail-grade, alternate-detail loading, run-jira prompt
    selection, and the Jira-grade merge-guard exception. Keep both single-step and
    sweep execution on their existing run-grade paths, including missing-detail handling,
    prompt accounting, and merge checks. Preserve preference-file overwrites and existing
    execution writes. Cover direct reader rejection and unchanged default rendering
    with unit tests, plus class-marked integration tests for both CLI execution paths.
- id: 4
  intent: Jira stories and developer handoffs share the supported run-grade source.
  files:
  - plan_tool/jira.py
  - plan_tool/cli/jira_cmd.py
  - tests/test_jira.py
  - tests/cli/test_jira_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/retire-jira-grade-detail/04-remove-jira-grade-direct-jira-grade.md
  description: Remove jira --grade and direct Jira-grade capture and prompt branches.
    Reuse the existing run-grade capture for concise stories and the paired developer
    handoff, preserving rendering, destinations, provenance, publication, and existing
    output-path safety checks. Preserve staged-file cleanup and paired os.replace
    publication; retiring the input lane must not change either operation. Extend
    unit tests and class-marked CLI integration tests to prove run-grade paired export
    and rejection of removed selectors.
- id: 5
  intent: Only evidence grounded in supported detail can certify the remaining audit
    gate.
  files:
  - plan_tool/review_persistence.py
  - plan_tool/fingerprint.py
  - plan_tool/completeness_report.py
  - tests/test_review_persistence.py
  - tests/test_fingerprint.py
  - tests/test_completeness_report.py
  - DATA_CONTRACT.md
  - tests/test_data_contract.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  description: Make captured audit inputs, fingerprints, normalization, freshness,
    and reuse run-grade-only. Preserve supported run-grade revision records and fingerprint
    behavior, including supported older revision versions; retain only the historical
    decoding needed for those records. Explicitly reject retired Jira-grade evidence
    rather than treating a rejected revision as missing provenance that can qualify
    through another path. Preserve durable saved-review and checkpoint replacement
    writes without rewriting archived records. Add unit tests for supported records,
    retired evidence, malformed evidence, and freshness boundaries, and update the
    saved-evidence contract.
- id: 6
  intent: Audits and diagnostics agree on the sole supported detail bundle and its
    evidence.
  files:
  - plan_tool/review.py
  - plan_tool/completeness_report.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/convergence_diagnosis.py
  - plan_tool/gate_status.py
  - plan_tool/cli/convergence_cmd.py
  - plan_tool/cli/gate_status_cmd.py
  - tests/test_review.py
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_convergence_diagnosis.py
  - tests/test_gate_status.py
  - tests/cli/test_convergence_cmd.py
  - tests/cli/test_gate_status_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 5
  depends_on_notes:
    5: Provides run-grade-only evidence qualification and historical run-grade record
      support.
  description: Remove grade selection from completeness-audit, its direct review readers
    and detector dispatch, convergence, and gate-status. Ground coverage, conceptual
    prompts, reports, history, and current-stage diagnostics in the existing run-grade
    bundle and the evidence rules from step 5. Remove Jira-only checks, framing, remediation
    commands, and persistence exceptions without changing run-grade convergence policy.
    Preserve markdown report and findings-sidecar replacement writes and their existing
    qualification guards. Cover the remaining predicates with unit tests and CLI wiring
    with class-marked integration tests.
- id: 7
  intent: No remaining schema or path helper can recreate or read the retired detail
    lane.
  files:
  - plan_tool/jira_grade.py
  - plan_tool/detail_artifacts.py
  - plan_tool/roadmap_gates.py
  - tests/test_jira_grade.py
  - tests/test_detail_artifacts.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  - 4
  - 6
  description: Delete jira_grade.py and its remaining schema tests, and remove Jira-grade
    path derivation from detail_artifacts.py after all consumers stop importing them.
    Remove obsolete schema references in roadmap_gates.py without changing its validation
    behavior. Add focused unit assertions that retired APIs and live Jira-grade bundles
    are absent and canonical resolution remains unchanged. No live plan-details/<slug>/jira/
    files exist at the audited snapshot; if any appear before execution, enumerate
    and delete only those live bundles, preserving canonical detail and every archive.
    Do not add a recurring cleanup workflow or new runtime dependency.
- id: 8
  intent: Users see the supported workflow and tracking closes only when retirement
    fully ships.
  files:
  - DETAIL_FORMAT.md
  - JIRA_FORMAT.md
  - CAPABILITIES.md
  - CLAUDE.md
  - TESTING.md
  - integrations/shared/DIRECTIVES.md
  - docs/ARCHITECTURE.md
  - docs/how-to/use-cases.md
  - docs/how-to/pipeline/detail.md
  - docs/how-to/pipeline/run.md
  - docs/how-to/pipeline/audit.md
  - docs/cli/detail.md
  - docs/cli/run.md
  - docs/cli/jira.md
  - docs/cli/completeness-audit.md
  - docs/cli/convergence.md
  - docs/cli/gate-status.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 7
  description: 'Update live format references, capability entries, operator guidance,
    and generated CLI references to describe run-grade detail as the sole input. Preserve
    Jira story and handoff documentation contracts and archived historical evidence.
    Verify the changed documentation, regenerate CLI references, and run the full
    pytest suite, including the paired-export and evidence-rejection integration coverage.
    Remove BACKLOG #308''s IPPT-17 promotion stub only after all retirement acceptance
    checks pass; leave #149''s re-baseline deferred.'
---
# Retire Jira Grade Detail

## Overview

Retire the legacy `plan-details/<slug>/jira/` artifact lane and every writer selector, reader selector, and schema for Jira-grade detail. Run-grade detail remains the sole implementation-detail input for concise Jira stories and the paired developer handoff. This is an explicit breaking change with no compatibility reader, migration, or fallback from a removed selector.

## Problem statement

Legacy Jira-grade artifacts and selectors remain alongside the run-grade detail route, contrary to the user-confirmed full-retirement decision tracked by BACKLOG #308 / IPPT-17. Removing `plan_tool/jira_grade.py` also affects finding parsers that depend on its `fenced_spans` helper, while grade-dependent saved-audit handling must continue supporting run-grade evidence without allowing retired evidence to certify it.

## Architecture

Remove `plan_tool/jira_grade.py`, Jira-grade paths in `plan_tool/detail_artifacts.py`, and reader selectors in `jira`, `run`, `completeness-audit`, `convergence`, and `gate-status`, together with the retired writer's `detail --grade` selector. This includes `plan_tool/cli/completeness_cmd.py`'s `GRADE_JIRA`/`JIRA_GRADE_VALUES` branches and the diagnostic selectors at `plan_tool/cli/gate_status_cmd.py:register` and `plan_tool/cli/convergence_cmd.py:register`. Remove live legacy bundles without touching canonical details or archived evidence.

Remove grade-dependent saved-audit selection, freshness, and fingerprints while preserving supported run-grade records. `plan_tool/review_persistence.py:AuditInputSnapshot.capture` and `normalize_audit_revision` are the named captured-input and saved-evidence anchors. Legacy Jira-grade evidence cannot certify a run-grade bundle and is not migrated into run-grade evidence.

Relocate `fenced_spans` because `plan_tool/review.py` uses it for non-Jira-grade finding parsers. It is not a drop-in for `scope_fence._fenced_code_spans`: preserve acceptance of fences indented past three spaces, pinned by `test_indented_citation_fence_protects_the_boundary`. The relocation preserves its current handling of a line that opens with an inline code span; correcting that behavior is a separate bug fix.

Limit cleanup to dependencies that block deletion of the legacy lane, its tests, and related format/CLI documentation, including `JIRA_FORMAT.md` and `DETAIL_FORMAT.md`. Keep run-grade authoring and Jira story/developer-handoff output contracts unchanged. The final docs/status work removes BACKLOG #308's promotion stub only after full shipment; plan authoring leaves it in place.

## Scope guardrails

This is the full retirement tracked by BACKLOG #308 / IPPT-17. Do not add a
compatibility reader, artifact migration, replacement grade, output redesign,
or compact-schema re-baseline. Preserve the run-grade authoring contract and
Jira story/developer-handoff output contract. Move only dependencies that
block deletion of the legacy lane; leave unrelated consolidation separate.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Documents option registration and argument rejection for removing grade selectors across CLI commands.
- [CommonMark Specification — Fenced code blocks](https://spec.commonmark.org/0.31.2/#fenced-code-blocks) — Defines fence delimiters, indentation, and closing rules for relocating the parser while preserving its deliberate indentation exception.
- [CommonMark Specification — Code spans](https://spec.commonmark.org/0.31.2/#code-spans) — Defines inline backtick syntax to inform the explicit handling of lines that begin with code spans.
- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Documents test parametrization for covering removed selectors, saved-evidence cases, and fence-parsing invariants.

- `plan_tool/jira_grade.py` — the lane being removed.
- `plan_tool/detail_artifacts.py`, `plan_tool/cli/completeness_cmd.py`
  (`GRADE_JIRA`, `JIRA_GRADE_VALUES`) — the reader selectors to remove.
- `plan_tool/review.py` — imports `fenced_spans` from `jira_grade.py`; the
  relocation target this seed's "Allowed reorganization" names.
- `plan_tool/review_persistence.py:AuditInputSnapshot.capture` and
  `normalize_audit_revision` — grade-dependent captured inputs and saved evidence.
- `plan_tool/cli/gate_status_cmd.py:register` and
  `plan_tool/cli/convergence_cmd.py:register` — diagnostic selectors.
- `JIRA_FORMAT.md`, `DETAIL_FORMAT.md` — the format docs to update.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing run-grade authoring or its detail contract.
- Recreating a separate Jira-detail route.
- Changing Jira story or developer-handoff rendering, destinations,
  provenance, or publication behavior.
- Rewriting archived historical evidence.

## Risks

Removing `jira_grade.py` can break finding parsers that use its fence helper
without consuming Jira-grade details. Grade-dependent audit fingerprints can
also make supported run-grade evidence stale or let retired evidence appear
current. Preserve the helper's deliberate parsing contract and run-grade
saved-evidence behavior while refusing retired inputs. Live legacy bundles
must be removed without touching canonical details or archived evidence.

## Testing

- `plan-tool jira <plan>` exports concise stories and the paired developer
  handoff from a run-grade bundle.
- No CLI or direct reader accepts a Jira-grade selector or artifact.
- Live plan details contain no Jira-grade bundle.
- Run-grade saved evidence retains its supported behavior; legacy Jira-grade
  evidence cannot satisfy the remaining run-grade audit gate.
- Finding annotations retain their fence-aware parsing behavior after the
  helper relocation, including the deliberate indented-fence exemption.
- The full suite is green.

## Acceptance criteria

Only run-grade detail can enter authoring, execution, audit, and Jira export.
The selectors and legacy lane are absent, Jira story export and its paired
developer handoff retain their contracts, and the verification above passes.
The final docs/status step removes BACKLOG #308's promotion stub only when
the full retirement ships and leaves #149's separate re-baseline deferred.

## Deferred

Any broader Jira-output redesign is a separate entry — this seed is removal
only, not a redesign of what ships to Jira.

None — the user has selected full retirement. `#149`'s compact-schema phase
stays blocked until it is re-baselined without this lane (do not fold that
re-baseline into this seed).
