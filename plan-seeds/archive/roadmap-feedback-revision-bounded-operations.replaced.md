> **Replaced**: this file has been superseded by `docs/implementation-plans/archive/2-roadmap-feedback-revision-bounded-operations.md`.
> Preserved here for history; do not edit.

# Bounded operations for stage-level roadmap feedback revision

Seed for BACKLOG **#297**. It implements the recommendation in
`docs/implementation-plans/backlog-arcs/analysis/roadmap-feedback-revision-architecture.md`.
The resulting plan updates `BACKLOG.md` when the work ships. It unblocks a
later re-scope of `roadmap-canonical-source-identity` and a later redesign of
`roadmap-revision-retention` (#242); it does not resume either effort.

## Outcome

A feedback-driven roadmap stage revision returns only a closed, typed JSON
operation set, and deterministic code applies those operations to the
canonical artifact before the existing stage gates judge the result. The model
does not re-emit untouched artifact content or the authoring contract, so a
large artifact's untouched rows cannot drift during a revision.

## In scope

- The stage-level feedback-revision route that currently wraps an authoring
  prompt and asks the model to re-emit a predecessor artifact.
- The shared local-revision operation and merge contract, widened from one
  presentation replacement plus one feedback response to the bounded
  stage-level vocabulary: authorized row add, edit, and removal operations;
  feedback response plus the existing `open` → `awaiting-review` lifecycle
  transition; and a
  removal-with-content operation when a reviewer-authorized row drop needs
  its existing continuity evidence.
- A self-contained bounded stage-revision prompt that supplies only the
  feedback, selected row data, and relation facts needed to decide those
  operations, never a whole artifact or a nested whole authoring prompt.
- The revision section of `ROADMAP_FORMAT.md` and the tests that define the
  operation envelope, deterministic merge, stage routing, and gate-preserving
  result contract.

## Overview

`roadmap.py:_render_revision_prompt` currently gives a model the predecessor
artifact, active feedback, and the full authoring prompt, then asks it to
re-emit the entire artifact. A 2026-08-12 first-use run on the `integration`
roadmap exposed the design at real artifact scale: a stage-1 revision made a
roughly 70 KB prompt and exhausted attempts through an invocation timeout, a
YAML parse failure, and a gate rejection caused by an altered
`awaiting-review` response.

Two sibling routes already use the intended shape. `--revise-feedback`
parses a closed JSON operation envelope and
`roadmap_revision_patch.merge_feedback_revision` merges it into one
canonical artifact. Structural revision similarly constrains model output to
typed operations and applies them in code. This effort generalizes that
bounded, code-owned pattern to the ordinary feedback route rather than adding
more defenses around whole-artifact regeneration.

## Problem statement

The current route makes output fidelity proportional to the size of the
artifact it asks the model to reproduce. Its deterministic gates correctly
refuse parse errors and changes to retained review content, but they do so
only after a long model call has reconstructed content that the feedback did
not authorize changing. Retrying repeats the same oversized reproduction
task.

The local feedback route cannot substitute directly: it selects one open
row, permits one presentation replacement, and requires one response. A
stage-level revision must carry the broader set of reviewer-authorized
changes the existing stage gates accept. The shared typed merge contract is
therefore widened compatibly instead of creating a second, stage-only patch
language.

## Architecture

The revision response remains one ordered, closed JSON envelope. Each
operation has a typed discriminator, a narrowly defined target, and only the
values needed for that operation. Code validates the complete envelope against
the current predecessor and active reviewer feedback, applies the approved
operations atomically to the canonical parsed artifact, renders the candidate,
and runs the existing id-continuity, settled-decision, feedback-integrity, and
design-row-continuity gates on that result. The completed-revision contract
remains the gates' current contract; only the model's input and reply format
change.

The bare plan derives a per-operation contract before detail: its only
producer, eligible target, required reviewer authority, deterministic merge
effect, ordering/combination rule, and rejection outcome. Detail then fixes
the concrete JSON fields and tests. This is a closed vocabulary, not an
extensible operation registry; the current presentation replacement and
feedback-response pair remain the backward-compatible subset.

The widened operation vocabulary owns stage-level feedback changes, while the
existing `--revise-feedback` and structural-revision routes retain their
current selection and publication contracts. Backward-compatible callers may
continue using the presentation-only subset of the shared merge contract.
The vocabulary does not introduce #242's retention semantics: any future
`closed` feedback state, retained closed feedback, removal snapshot policy,
or decision-reference policy remains #242 work after this merge layer ships.

Feedback-driven stage revision owns the bounded route. With no `open`
feedback, it applies no operations and preserves the artifact without a model
call, matching the format contract's no-op rule. A broad re-entry or recovery
need that is not a response to active reviewer feedback remains an explicit
existing-route behavior; it must not silently restore whole-artifact
regeneration as a fallback for feedback handling. The plan and detail stages
will ground that boundary against the current re-entry callers and preserve
their observable contracts.

## Out of scope

- A general-purpose patch or diff language for arbitrary artifact edits.
- Changes to what the existing stage gates check, their retry behavior, or
  their completed-result contract.
- Redesigning `--revise-feedback` or structural revision; this work reuses
  their bounded-pattern lessons without widening either route's scope.
- #242's retention semantics, including `closed` feedback, retained closed
  rows, removal snapshots, and removal-to-decision references.
- The independent hand-authored YAML-scalar corruption defect recorded in
  `BUG_BACKLOG.md`; the bounded model reply is JSON, but it does not mediate
  a reviewer editing raw YAML.
- Canonical-source identity, receipt freshness, evidence retention, framework
  lenses, or any new roadmap stage.

## Allowed behavior changes

Stage-level feedback revision changes from a whole-artifact authoring prompt
and artifact-text reply to a bounded JSON-operation prompt and reply. An empty
active-feedback set takes the deterministic no-op route instead of invoking a
model. A nonempty revision can fail when its closed operation response is
invalid, just as it can now fail when the re-emitted artifact cannot parse or
pass gates. The result accepted after deterministic merge continues to satisfy
the existing stage gates.

## Allowed reorganization

The shared `RevisionOperations` and deterministic merge may grow to own the
closed stage-level operation vocabulary and its existing callers may adapt to
that generalized contract. No separate stage-only patch subsystem or renaming
of the local or structural revision routes is allowed.

## Risks

- **Vocabulary creep.** A convenient catch-all operation would recreate the
  unbounded surface under another name. Every operation must express a
  currently reviewer-authorized stage change; if a real case needs arbitrary
  patching, stop and re-scope it as separate design work.
- **Shared-leaf regression.** Structural revision and `--revise-feedback`
  consume neighboring bounded machinery. The presentation-only local path
  and structural path need explicit compatibility coverage as the common
  contract expands.
- **Incomplete feedback context.** A prompt that omits a relation needed to
  choose a valid operation can produce a deterministic rejection loop. The
  detail phase must derive the minimum context from the existing gate
  obligations, not reintroduce whole-artifact or whole-authoring-prompt
  payloads as a shortcut.
- **False confidence from unit scale.** The reported defect appears on a
  large artifact and must be checked at that scale, not inferred from a small
  fixture alone.

## Testing

Use hermetic fixture-driven tests with stubbed invokers. A integration-scale
artifact (tens of KB) with multiple feedback rows demonstrates that a
stage-level feedback revision receives and returns bounded JSON operations,
changes only operations' named rows, and preserves an untargeted
`awaiting-review` row's response exactly. Mutating an operation target,
lifecycle transition, or removal evidence must fail through the existing
validation or gate boundary; mutating unaffected canonical content must be
impossible because it is absent from the model reply.

An existing artifact with no `open` feedback makes no backend request and
remains byte-identical. This confirms the format's feedback-free no-op rule
without relying on a model to reproduce it.

Run compatibility tests for the existing presentation-only local revision
and structural revision routes. Replay a stage-1 revision against the actual
`integration`-scale artifact or an equivalent captured fixture: it completes without
the whole-artifact `invoke`, YAML `parse`, or untouched-row `gates` failure
shape and preserves the untargeted awaiting-review response.

## Acceptance criteria

- A feedback-driven stage revision's model reply is a closed typed JSON
  operation envelope, never a complete roadmap artifact.
- The bounded prompt does not embed a whole predecessor artifact or a nested
  whole authoring prompt; its revision payload grows with selected feedback
  context rather than unrelated artifact text.
- Deterministic code applies only the operations named in the response before
  the existing stage gates judge the candidate.
- A stage with no open feedback makes no backend request and preserves its
  predecessor byte-for-byte.
- A tens-of-KB fixture proves a named change lands while an untargeted
  `awaiting-review` response remains byte-for-byte unchanged.
- Existing `--revise-feedback` presentation replacements and structural
  revision keep their current contracts under the widened shared machinery.
- A real-size stage-1 replay completes without re-emitting untouched content
  and without the production failure shape that motivated #297.
- `ROADMAP_FORMAT.md` states the bounded stage-revision response and merge
  contract, and `BACKLOG.md` #297 is updated only when the work ships.

## Stop / defer

If the minimal operation vocabulary cannot cover a real stage-level feedback
revision without approximating a general patch language, stop and file a
separate design decision instead of expanding this seed's scope.

## Deferred

- Re-scoping `roadmap-canonical-source-identity` after this outcome is
  verified.
- Redesigning #242 around the shipped merge layer.
- A safe interface for reviewers who manually add or edit YAML feedback rows.
