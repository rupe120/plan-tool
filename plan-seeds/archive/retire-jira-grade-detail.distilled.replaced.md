> **Replaced**: this file has been superseded by `docs/implementation-plans/2-retire-jira-grade-detail.md`.
> Preserved here for history; do not edit.

## Overview

Retire the legacy `plan-details/<slug>/jira/` artifact lane and every writer selector, reader selector, and schema for Jira-grade detail. Run-grade detail remains the sole implementation-detail input for concise Jira stories and the paired developer handoff. This is an explicit breaking change with no compatibility reader, migration, or fallback from a removed selector.

## Problem statement

Legacy Jira-grade artifacts and selectors remain alongside the run-grade detail route, contrary to the user-confirmed full-retirement decision tracked by BACKLOG #308 / IPPT-17. Removing `plan_tool/jira_grade.py` also affects finding parsers that depend on its `fenced_spans` helper, while grade-dependent saved-audit handling must continue supporting run-grade evidence without allowing retired evidence to certify it.

## Architecture

Remove `plan_tool/jira_grade.py`, Jira-grade paths in `plan_tool/detail_artifacts.py`, and reader selectors in `jira`, `run`, `completeness-audit`, `convergence`, and `gate-status`, together with the retired writer's `detail --grade` selector. This includes `plan_tool/cli/completeness_cmd.py`'s `GRADE_JIRA`/`JIRA_GRADE_VALUES` branches and the diagnostic selectors at `plan_tool/cli/gate_status_cmd.py:register` and `plan_tool/cli/convergence_cmd.py:register`. Remove live legacy bundles without touching canonical details or archived evidence.

Remove grade-dependent saved-audit selection, freshness, and fingerprints while preserving supported run-grade records. `plan_tool/review_persistence.py:AuditInputSnapshot.capture` and `normalize_audit_revision` are the named captured-input and saved-evidence anchors. Legacy Jira-grade evidence cannot certify a run-grade bundle and is not migrated into run-grade evidence.

Relocate `fenced_spans` because `plan_tool/review.py` uses it for non-Jira-grade finding parsers. It is not a drop-in for `scope_fence._fenced_code_spans`: preserve acceptance of fences indented past three spaces, pinned by `test_indented_citation_fence_protects_the_boundary`, and explicitly decide how to handle a line that opens with an inline code span rather than silently inheriting another helper's behavior.

Limit cleanup to dependencies that block deletion of the legacy lane, its tests, and related format/CLI documentation, including `JIRA_FORMAT.md` and `DETAIL_FORMAT.md`. Keep run-grade authoring and Jira story/developer-handoff output contracts unchanged. The final docs/status work removes BACKLOG #308's promotion stub only after full shipment; plan authoring leaves it in place.

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

`scope_fence._fenced_code_spans`: `review.py` deliberately accepts fences
indented past three spaces (pinned by
`test_indented_citation_fence_protects_the_boundary`), and `fenced_spans`

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

## Scope guardrails

This is the full retirement tracked by BACKLOG #308 / IPPT-17. Do not add a
compatibility reader, artifact migration, replacement grade, output redesign,
or compact-schema re-baseline. Preserve the run-grade authoring contract and
Jira story/developer-handoff output contract. Move only dependencies that
block deletion of the legacy lane; leave unrelated consolidation separate.

## References

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
