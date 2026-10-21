> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Brief Source Drift
intent: Roadmap stage runs fail closed when the content at their recorded concept-brief
  path no longer matches the content the roadmap accepted. An operator can make one
  explicit, auditable choice to accept the current decoded text as the source baseline
  without implying that existing roadmap artifacts were regenerated.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
enforce_step_tests: true
source_seed: plan-seeds/roadmap-brief-source-drift.md
steps:
- id: 1
  title: Read saved brief digests and distinguish legacy absence from malformed metadata
  intent: Give stage preflight one trusted representation of matched, legacy, and
    invalid source records.
  files:
  - plan_tool/roadmap_source.py
  - tests/test_roadmap_source.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-brief-source-drift/01-read-saved-brief-digests-distinguish.md
  status: done
- id: 2
  title: Persist and check brief digests before artifact admission, preserving the
    atomic source write, artifact replacements, and seed cleanup
  intent: Prevent changed or unknown brief content from reaching artifact loading,
    backend calls, or publication while leaving matched runs unchanged.
  files:
  - plan_tool/roadmap.py
  - plan_tool/run_log.py
  - tests/test_roadmap.py
  - tests/test_run_log.py
  - DATA_CONTRACT.md
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the validated recorded-digest and legacy-state contract used by preflight.
  detail: docs/implementation-plans/plan-details/roadmap-brief-source-drift/02-persist-check-brief-digests-before.md
  status: done
- id: 3
  title: Accept same-path rebinding while isolating the baseline operation from artifact
    and seed effects
  intent: Let an operator deliberately accept current brief text without implying
    that roadmap artifacts were regenerated or semantically reconciled.
  files:
  - plan_tool/roadmap.py
  - plan_tool/run_log.py
  - plan_tool/cli/__init__.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap.py
  - tests/test_run_log.py
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/package_surface_help.golden.txt
  - DATA_CONTRACT.md
  - docs/cli/roadmap.md
  complexity: high
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Provides fail-closed digest admission and initial persisted baselines for the
      explicit acceptance exception.
  detail: docs/implementation-plans/plan-details/roadmap-brief-source-drift/03-accept-same-path-rebinding-while.md
  status: done
- id: 4
  title: Document source admission and lifecycle, then retire the drift risk
  intent: Keep every current source-persistence description aligned with the shipped
    refusal and explicit baseline-acceptance boundary.
  files:
  - ROADMAP_FORMAT.md
  - docs/ARCHITECTURE.md
  - README.md
  - RUNBOOK.md
  - USE_CASES.md
  - docs/how-to/roadmap.md
  - BUG_BACKLOG.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: Supplies the final digest-persistence and refusal behavior the references describe.
    3: Supplies the final acceptance, lifecycle, and operator-message vocabulary the
      references describe.
  detail: docs/implementation-plans/plan-details/roadmap-brief-source-drift/04-document-source-admission-lifecycle.md
  status: done
---
# Roadmap Brief Source Drift

## Overview

The roadmap already fixes one concept-brief path at its first successful write
and logs a digest of the content read on each run. The persisted record does not
retain that digest, so a later edit at the same path is indistinguishable from
an unchanged source. This change completes the existing one-shot binding rather
than introducing automatic re-grounding.

## Problem statement

A feedback-free re-entry can currently read changed brief content, invoke no
backend, rewrite no artifact, and still return the same no-change outcome as an
unchanged source. That fail-silent result can lead an operator to believe the
roadmap reflects a revised brief when the artifacts were only re-gated.

## Architecture

The source-record reader remains the shared owner of persisted source identity.
The roadmap orchestrator remains the owner of selection, preflight comparison,
explicit acceptance, lifecycle reporting, and the point at which the initial
record is written. The comparison occurs before artifact loading so every
selected stage and every feedback/no-feedback route sees the same source
admission result.

The accepted digest uses the same decoded-text digest contract as the existing
`roadmap_source_resolved` event. A present record with an absent digest carries
an explicit legacy/unknown state; malformed metadata is an error, not a legacy
record.

Every stage run that reaches a digest-admission decision emits exactly one
durable `roadmap_source_admission` lifecycle result before artifact admission.
Its closed disposition is `initial` for the first supplied source, `matched`
for an unchanged recorded source,
`accepted-rebind` for explicit same-path baseline acceptance,
`refused-legacy` for a record whose digest is absent, `refused-changed` for a
digest mismatch, or `refused-malformed` for invalid persisted source metadata.
The event always records the source-record path, repository-relative when
possible and absolute otherwise, which is safe even when malformed metadata
yields no usable brief reference. Malformed
metadata emits its decision from source-record preflight before any brief read;
the other dispositions follow a successful brief read. The event records the
admission decision, not semantic agreement between the brief and existing
roadmap artifacts. Existing resolved/recorded and generic preflight-failure
events retain their narrower facts.

Source-record preflight also distinguishes a missing writable target from an
existing directory that the atomic writer cannot replace. The directory case
is a malformed source target and refuses before artifact publication; only an
eligible absent target can wait for the first successful artifact before the
initial source record is written.

## References

- `BUG_BACKLOG.md` — “A changed concept brief is silently ignored on every
  stage run after the first” is the originating risk contract.
- `plan_tool/roadmap.py` — `_resolve_brief_path`, `_run_roadmap`, and
  `_write_brief_source` own source selection, stage-run preflight, and initial
  persistence.
- `plan_tool/roadmap_source.py` — `RecordedBriefSource`,
  `read_recorded_brief_source`, and `digest_decoded_text` define the shared
  recorded-source representation and digest contract.
- `DATA_CONTRACT.md` — `RoadmapSourceAdmission`, `RoadmapSourceResolved`, and
  `RoadmapSourceRecorded` define the decision, read, and persistence lifecycle
  records.
- `docs/ARCHITECTURE.md` — “Brief-source persistence” defines the one-shot
  source binding and re-entry boundary.
- `ROADMAP_FORMAT.md` — source/re-entry and feedback ownership rules constrain
  the refusal guidance and exclude automatic re-grounding.
- `tests/test_roadmap.py` and `tests/test_roadmap_source.py` — existing source
  persistence, same-path re-entry, different-path refusal, and run-log
  behavior provide the regression surface.
- `handoffs/2026-09-11-roadmap-aidlc-inception-fit.md` — the broader AI-DLC
  roadmap seam design establishes this fix as the first dependency.
- `handoffs/2026-09-11-integration-seam-resume-order.md` — the approval and sequencing
  handoff keeps Integration execution separate until the roadmap seam converges.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Automatically regenerating, reconciling, or rewriting roadmap artifacts from
  changed brief content.
- Adding a new source-acceptance flag or an interactive prompt inside a stage
  run.
- Expanding the source record into the multi-source, role-tagged seam frame,
  item-level citation snapshots, or change-control policies planned by the
  AI-DLC intake evolution work.
- Changing candidate-lineage source checks, feedback semantics, artifact gate
  meanings, stage retry/exit behavior, or source path identity rules.
- Deciding which additional AI-DLC inception outputs become roadmap stages.

## Risks

- An acceptance message that merely says “accepted” can imply the artifacts now
  represent the changed brief. The observable summary must distinguish source
  baseline acceptance from semantic re-grounding.
- Treating legacy absence as a match preserves the defect. Treating all absent
  fields as malformed removes the bounded migration path.
- Comparing after artifact loading or backend contact spends work and admits
  state before the fail-closed decision.
- Digest computation must stay aligned with the existing decoded-text logging
  contract or unchanged briefs can appear to drift.

## Testing

Add focused tests at the source-reader, orchestrator, and CLI boundary, then run
the affected roadmap suite and the full test suite.

The binary observable is whether a stage run reaches artifact admission or the
backend when the current brief digest lacks a confirmed match. It must not.
Tests cover initial digest persistence, unchanged re-entry, same-path content
drift, legacy missing-digest records, malformed digest values, explicit
same-path acceptance and persisted rebinding, different-path refusal, run-log
preflight classification, and user-facing guidance that distinguishes
acceptance from re-grounding.

Initial-binding tests also place a directory at the computed `source.json`
target and prove preflight refuses it before artifact publication or backend
contact instead of treating it as an absent source record.

Lifecycle tests assert that each source-decision path emits exactly one
`roadmap_source_admission` event with the corresponding closed disposition;
refusal cases emit it before the terminal preflight failure, and no admitted or
refused run can omit or duplicate the decision record.

The validation must not judge prose quality, inspect semantic agreement between
the brief and artifacts, add shape or length caps unrelated to digest validity,
or alter existing artifact gates, retry budgets, advancement rules, or terminal
outcomes beyond the new source-preflight refusal and explicit acceptance path.

## Acceptance criteria

- Every newly recorded roadmap source contains its existing brief reference and
  a valid digest of the exact decoded brief text admitted for the first write.
- Normal re-entry proceeds only when the current and recorded digests match.
- Changed, legacy/unknown, and malformed recorded sources fail before upstream
  artifact admission, backend invocation, or artifact write unless the
  legacy/changed source is explicitly accepted through the existing
  same-path `--from-existing` gesture.
- An existing directory at the `source.json` target is a malformed,
  non-replaceable source target and refuses before artifact publication; it is
  never treated as an absent record eligible for initial binding.
- Explicit acceptance updates the persisted baseline atomically without
  artifact or seed effects from the baseline-replacement operation itself, and
  states that semantic changes still belong in feedback or a successor
  lineage. After rebinding, the same invocation retains ordinary stage
  behavior; any later artifact or seed effects remain attributable to those
  existing routes.
- Each initial, matched, explicitly rebound, legacy-refused, changed-refused,
  and malformed-refused source decision emits exactly one durable
  `roadmap_source_admission` result with the closed disposition defined in the
  data contract; this result never claims artifact re-grounding.
- A different explicit path remains refused under the existing source-identity
  rule.
- Persistence, lifecycle/run-log, documentation, compatibility, and regression
  tests cover the complete behavior class.
- The shipped implementation updates or removes the originating changed-brief
  RISK entry in `BUG_BACKLOG.md` without disturbing unrelated backlog items.

## Deferred

Role-tagged source sets, root digests, item-level citation snapshots, strict and
relaxed source-change policies, inherited/derived decision classes, open
question propagation, accepted-risk obligations, workflow-rule routing, seam
frames, coverage/status projections, and AI-DLC inception-step coverage remain
in their dependency-ordered follow-up slices.
