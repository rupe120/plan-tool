---
format_version: 1
title: Roadmap Concept Comparison
intent: An operator can compare two resolved roadmap snapshots in one read-only command,
  review complete concept-level changes, and inspect Git's complete unified diff as
  the exact evidence for the same four artifact pairs before taking a separate acceptance
  action.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-concept-comparison.md
steps:
- id: 1
  title: Extract the shared typed roadmap diff while preserving candidate add, replace,
    and remove behavior
  intent: Candidate review and the new comparison command need one deterministic owner
    for concept-level differences.
  files:
  - plan_tool/roadmap_candidate.py
  - tests/test_roadmap_candidate.py
  creates:
  - plan_tool/roadmap_diff.py
  - tests/test_roadmap_diff.py
  allowed_mentions:
  - plan_tool/roadmap_candidate_run.py
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/roadmap_version_promotion.py
  - plan_tool/roadmap_versions.py
  - plan_tool/roadmap_view.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-concept-comparison/01-extract-shared-typed-roadmap-diff-while.md
  status: done
- id: 2
  title: Add typed comparison and raw patch evidence
  intent: A reviewer can inspect every structured roadmap change beside exact evidence
    without losing raw-only artifact changes or inventing ownership for mixed patch
    bytes.
  creates:
  - plan_tool/roadmap_compare.py
  - tests/test_roadmap_compare.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the shared base-first row, ordering, and relation delta used by comparison
      and candidate review.
  detail: docs/implementation-plans/plan-details/roadmap-concept-comparison/02-typed-comparison-raw-patch-evidence.md
  status: done
- id: 3
  title: Add complete read-only loading for an explicit stored roadmap version
  intent: An explicit comparison base or target can use the same immutable-version
    integrity checks as the version named by the accepted-head selector.
  files:
  - plan_tool/roadmap_versions.py
  - tests/test_roadmap_versions.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-concept-comparison/03-complete-read-only-loading-explicit.md
  status: done
- id: 4
  title: Resolve comparison snapshots and capture all four controlled Git patches
    without writing roadmap state
  intent: Every comparison binds two complete, identified snapshots to Git's exact
    unified evidence and refuses missing, corrupt, mismatched, undecodable, or partial
    inputs.
  creates:
  - plan_tool/roadmap_compare_run.py
  - tests/test_roadmap_compare_run.py
  allowed_mentions:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_compare.py
  - plan_tool/roadmap_versions.py
  - plan_tool/roadmap_view.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: Provides the pure comparison and raw-patch evidence contract.
    3: Provides integrity-checked loading for an explicitly selected immutable version.
  detail: docs/implementation-plans/plan-details/roadmap-concept-comparison/04-resolve-comparison-snapshots-capture.md
  status: done
- id: 5
  title: Render base-then-target-ordered comparison cards, complete patches, and deterministic
    JSON
  intent: Operators and tools can inspect the same snapshot identities, counts, typed
    changes, unmapped evidence, and complete patches in stable human- and machine-readable
    forms.
  creates:
  - plan_tool/roadmap_compare_render.py
  - tests/test_roadmap_compare_render.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 4
  depends_on_notes:
    2: Defines typed cards, raw-only unmapped evidence, and raw-evidence identity
      for rendering.
    4: Supplies resolved snapshot metadata, artifact digests, and the four complete
      Git patches.
  detail: docs/implementation-plans/plan-details/roadmap-concept-comparison/05-render-base-then-target-ordered.md
  status: done
- id: 6
  title: Add the exclusive read-only roadmap comparison CLI while preserving the HTML
    view overwrite path
  intent: An operator can select a working or stored target, default safely to the
    accepted base or name a stored base, and request cards, patches, or JSON in one
    model-free command.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  - docs/cli/roadmap.md
  complexity: high
  change_type: feature
  depends_on:
  - 4
  - 5
  depends_on_notes:
    4: Provides the read-only comparison operation and its explicit failure outcomes.
    5: Provides the terminal, patch, and machine-readable renderers.
  detail: docs/implementation-plans/plan-details/roadmap-concept-comparison/06-exclusive-read-only-roadmap-comparison.md
  status: done
  status_note: '2026-09-21: original test-authoring gate passed; after regenerating
    the CLI reference, the full suite passed (13,204 passed, 190 skipped).'
- id: 7
  title: 'Document roadmap comparison and mark BACKLOG #402 shipped'
  intent: The command's selectors, evidence guarantees, read-only boundary, module
    ownership, and operator workflow remain discoverable and consistent across the
    project references.
  files:
  - ROADMAP_FORMAT.md
  - CAPABILITIES.md
  - README.md
  - CLAUDE.md
  - docs/ARCHITECTURE.md
  - docs/reference/commands.md
  - docs/how-to/roadmap.md
  - BACKLOG.md
  - tests/test_roadmap_format.py
  allowed_mentions:
  - docs/cli/roadmap.md
  - plan_tool/cli/roadmap_cmd.py
  complexity: high
  change_type: non-code
  depends_on:
  - 6
  depends_on_notes:
    6: Settles the shipped CLI names, output modes, refusal behavior, and generated
      command reference that the documentation records.
  detail: docs/implementation-plans/plan-details/roadmap-concept-comparison/07-document-roadmap-comparison-mark.md
  status: done
---
# Roadmap Concept Comparison

## Overview

The comparison surface resolves an explicit target against the immutable
version named by the current accepted-head selector by default, or against an
explicitly selected stored base. It reports
typed roadmap changes in deterministic base-then-target source order while
retaining every byte difference, including text that no structured row
explains. The report binds
both sides to their snapshot kind, version identity when present, artifact
digests, and recorded brief identity.

## Problem statement

Existing roadmap views explain one snapshot, and `git diff --no-index` records
exact bytes, but neither lets a reviewer understand two snapshots as roadmap
concepts. Multi-line decisions, entities, rules, constraints, components,
plans, ordering entries, and declared relations otherwise have to be rebuilt
mentally from independent hunks. Candidate review already derives most of this
typed delta, but it is coupled to candidate authority rather than exposed as a
general read-only comparison.

## Architecture

Snapshot resolution has one closed selector contract: a target is either the
current four working artifacts or an immutable roadmap version id; a base is
either the immutable version named by the current accepted-head selector or an
immutable roadmap version id. The accepted-head version is the default base
only when the selector exists. Absence of an accepted-head selector requires
an explicit stored-version base, and invalid, incomplete, or
identity-mismatched snapshots refuse rather than falling back to another
source.

The comparison core reuses a small public read-only seam extracted from
`roadmap_candidate`'s predecessor diff rather than creating a second semantic
diff engine. A comparison concept has the identity `(artifact key, row kind,
stable id)` and retains complete before/after typed rows, plan-ordering deltas,
and relation-occurrence deltas; `roadmap_view` remains the owner of roadmap-wide
indexing and display labels. A dependency-neutral comparison leaf owns typed
comparison facts and raw patch evidence without claiming a byte-level partition
of a mixed artifact. It reports an unmapped/raw-text fact only for an artifact
whose bytes differ without a typed delta; a mixed artifact retains its complete
Git patch as evidence rather than assigning narrative, comments, or formatting
to a nearby row by inference. Candidate admission, authority, review identity,
and publication stay private to the candidate workflow.

For each of the fixed four artifact pairs, a controlled Git no-index invocation
with external diff disabled produces the complete unified patch. Its exact
bytes and invocation outcome are evidence, not a rendering aid: structured
cards explain the evidence but never replace, normalize, truncate, or silently
discard it. Status `0` is successful identical evidence and status `1` is
successful differing evidence; any other status, launch failure, or decoding
failure refuses the comparison. An artifact whose bytes differ without a typed
row, ordering, or relation delta appears in an unmapped/raw-text section. A
mixed artifact retains its complete patch without a claimed byte-to-concept
split.

The default terminal report starts with artifact and concept counts, then emits
one complete card per concept identity in fixed artifact-inventory and row-kind
order. Within a row kind, removed and changed identities retain base source
order, followed by target-only additions in target source order. A stable row
whose bytes only move without a typed value change has no invented concept
delta; it appears in unmapped/raw-text evidence. A mixed typed and byte-only
artifact retains its complete patch without an invented split. A card names
`added`, `removed`, or `changed`, uses the established display label, shows only changed
non-relation fields as before/after values, and lists added and removed declared
relations separately. Terminal and machine-readable renderers consume this same
ordered comparison stream. A patch view prints the complete Git evidence.
Machine-readable output carries the same typed comparison, unmapped-text facts,
snapshot identities, per-snapshot artifact digests, and an identity derived from
the exact framed raw evidence without model-authored interpretation.

## Scope guardrails

- The command never writes, accepts, enrolls, promotes, settles, repairs, or
  otherwise mutates a roadmap snapshot or its metadata.
- Git's complete unified diff over exactly the resolved four artifact pairs is
  the source of record. Structured output explains typed concepts and may report
  raw-only artifacts, but it does not partition mixed patch bytes by concept or
  suppress, rewrite, or substitute for that evidence.
- Stable ids establish concept identity. An id change is a removal plus an
  addition, never semantic matching by label or prose.
- Comparison remains deterministic and model-free. No output field contains a
  generated judgment, summary, or acceptance recommendation.
- Existing roadmap views and lifecycle writers remain byte- and behavior-
  compatible.
- Discoveries involving other artifact families or acceptance policy stop and
  return to the backlog; they do not expand this plan.

## References

- `BACKLOG.md` #402 (closed, entry removed on shipment) — the source feature
  contract this plan implemented.
- `ROADMAP_FORMAT.md` — fixed roadmap artifacts, typed rows, declared
  relations, version identities, and roadmap presentation contracts.
- `plan_tool/roadmap_versions.py:VERSION_ARTIFACT_INVENTORY`,
  `load_accepted_version`, and `load_stored_version` — fixed inventory and
  accepted snapshot and stored-version-record ownership.
- `plan_tool/roadmap_candidate.py:CandidatePredecessorDiff`,
  `_build_predecessor_diff`, `_artifact_row_diffs`, and
  `candidate_impact_atoms_for_diff` — existing typed row, ordering, and
  relation comparison logic to expose or extract.
- `plan_tool/roadmap_view.py:display_label` and its roadmap-wide index builders
  — established concept identity and human-label presentation.
- `SEED_FORMAT.md` — plan-seed scope, density, and verification directives.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Accepting, promoting, enrolling, settling, repairing, or mutating either
  snapshot, and any change to candidate proposal or review policy.
- Model-written summaries, semantic matching across changed stable ids, or
  generalized repository diffing.
- Comparing seeds, implementation plans, source briefs, receipts, run logs, or
  artifacts beyond the fixed roadmap inventory.
- HTML or another interactive renderer; it may follow only after the terminal
  and machine-readable contracts have shipped and supplied separate evidence.

## Risks

- **Two truths drift:** a new comparison implementation could disagree with
  candidate review. Both callers share the typed diff owner and regression
  cases rather than duplicating it.
- **Pretty output hides evidence:** field projection or parsing could hide
  comments, narrative, or formatting. The raw patch remains complete, and a
  raw-only artifact difference is reported explicitly without inferring
  ownership for mixed patch bytes.
- **Selector ambiguity:** a missing accepted-head selector or malformed stored
  version could prompt an unsafe fallback. Resolution is closed and fail-closed,
  with both selected identities printed.
- **Relation double counting:** relation-bearing row fields could appear as
  ordinary field edits and relation changes. The report separates declared
  relations from the row's non-relation fields while preserving occurrence
  changes.
- **Git environment variance:** user diff drivers or configuration could alter
  evidence. The invocation disables external diff behavior and reports command
  or decode failure explicitly.

## Testing

Prove one replay across the accepted-head-version default, explicit stored-version
base, and working/stored target routes: the bare plan retains the invariant
that one resolved pair yields both a complete Git patch and a typed concept
report, while detail chooses fixtures and invocation mechanics. The
detail-grounded suite covers unchanged bundles; one-field decision settlement;
added, removed, changed-and-reordered, reorder-only, field-only, ordering-entry,
relation-only, duplicate-relation, raw-only, mixed typed-and-byte-only, and
byte-identical changes; and
simultaneous changes across all four artifacts. It proves the shared
base-then-target terminal and machine-readable ordering,
per-snapshot identities and digests, explicit refusal for missing or
unparseable working artifacts, no accepted-head selector without a base,
unknown or corrupt versions, Git statuses `0` and `1` as successful evidence,
an abnormal Git status as refusal, and launch and decoding failures. It also
proves comparison changes no artifact, baseline, seed state, version selector,
receipt, run log, or Git index on success or refusal. Existing candidate-diff
behavior remains covered through the shared seam.

## Acceptance criteria

- An explicit working or stored target compares with the immutable version
  named by the current accepted-head selector by default, while an explicit
  stored version can replace that base; no accepted-head selector means the
  operator must select a base.
- Every report identifies both snapshots, their available version and brief
  identities, and each snapshot's four artifact digests.
- Terminal and machine-readable output give compact counts and the same complete
  concept-card order: fixed artifact/row-kind order, base-ordered removed and
  changed identities, then target-ordered additions. Changed non-relation fields
  and relation deltas remain separated.
- Raw-only artifact changes remain visible in an unmapped section, byte-identical
  artifacts are identified, and the patch view emits the complete controlled Git
  diff for all four pairs, including mixed typed-and-byte-only artifacts.
- Machine-readable output represents the same typed and unmapped comparison
  plus raw-evidence identity, with no model-authored interpretation.
- Git statuses `0` and `1` produce complete identical or differing evidence;
  any other status, launch/decoding failure, or snapshot-resolution failure is
  explicit and does not mutate state or silently degrade to partial evidence.
- The implementation reuses the candidate typed-diff and roadmap label/index
  owners without importing candidate authority into comparison.

## Deferred

An HTML or interactive concept-card view requires separate evidence after the
terminal and machine-readable contracts ship. Broader artifact comparison,
semantic id matching, and acceptance actions remain separate efforts.
If a selector requires a lifecycle recovery or migration path, exclude it from
the first release rather than inventing that path here.
