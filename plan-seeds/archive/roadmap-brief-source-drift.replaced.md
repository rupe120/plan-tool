> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-brief-source-drift.md`.
> Preserved here for history; do not edit.

# Roadmap brief-source drift refusal

## Outcome

Roadmap stage runs fail closed when the content at their recorded concept-brief
path no longer matches the content the roadmap accepted. An operator can make
one explicit, auditable choice to accept the current decoded text as the source
baseline without implying that existing roadmap artifacts were regenerated.

## In scope

- Extend the persisted roadmap source record so the first successful artifact
  write binds both the existing brief reference and the digest already computed
  for the decoded UTF-8 brief text.
- Compare the freshly read brief digest with the recorded digest during every
  stage-run preflight, before upstream admission, backend invocation, or
  artifact publication.
- Treat an existing source record without a digest as legacy/unknown. It must
  not be interpreted as a match.
- Refuse legacy/unknown and changed-content re-entry with guidance that names
  the supported semantic-change routes: reviewer feedback on the owning
  artifact or a successor roadmap lineage.
- Reuse the existing explicit source-binding gesture: supplying
  `--from-existing` with the already recorded path accepts the current digest.
  Persist that acceptance atomically and report that it changes only the source
  baseline; it does not re-ground or rewrite existing roadmap artifacts.
- Keep recorded-source parsing fail closed for a present but malformed digest.
- Update the canonical source-persistence and run-log contracts, architecture
  description, CLI help or summaries affected by the behavior, and the
  originating `BUG_BACKLOG.md` entry when the implementation ships.

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

## Allowed behavior changes

- A normal run against an unchanged recorded brief continues through existing
  stage selection and can still finish with the existing no-change outcome.
- A run against a changed brief, or a legacy record whose digest is unknown,
  refuses during source preflight instead of proceeding silently.
- Repeating `--from-existing` with the recorded path explicitly accepts and
  persists the currently read digest, then continues under the ordinary stage
  behavior without claiming artifact re-grounding.
- A present invalid digest field refuses as malformed persisted metadata.

## Allowed reorganization

Small source-record parsing and preflight helpers may move to the shared
roadmap-source module when that keeps parsing and validation single-sourced.
Do not create a generalized source-policy framework for this slice.

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
- Explicit acceptance updates the persisted baseline atomically, preserves all
  existing roadmap artifacts, and states that semantic changes still belong in
  feedback or a successor lineage.
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

## References

- `BUG_BACKLOG.md` — “A changed concept brief is silently ignored on every
  stage run after the first” is the originating risk contract.
- `plan_tool/roadmap.py` — `_resolve_brief_path`, `_run_roadmap`, and
  `_write_brief_source` own source selection, stage-run preflight, and initial
  persistence.
- `plan_tool/roadmap_source.py` — `RecordedBriefSource`,
  `read_recorded_brief_source`, and `digest_decoded_text` define the shared
  recorded-source representation and digest contract.
- `DATA_CONTRACT.md` — `RoadmapSourceResolved` and `RoadmapSourceRecorded`
  define the corresponding lifecycle records.
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
