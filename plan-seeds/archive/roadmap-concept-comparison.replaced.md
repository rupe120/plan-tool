> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-concept-comparison.md`.
> Preserved here for history; do not edit.

# Plan seed: Compare roadmap revisions as concepts with Git diff evidence

## Outcome

An operator can compare two resolved roadmap snapshots in one read-only command,
review complete concept-level changes, and inspect Git's complete unified diff as
the exact evidence for the same four artifact pairs before taking a separate
acceptance action.

## Overview

The comparison surface resolves an explicit target against the active accepted
root by default, or against an explicitly selected stored base. It reports
typed roadmap changes in artifact and source order while retaining every byte
difference, including text that no structured row explains. The report binds
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
either the active accepted root or an immutable roadmap version id. The
accepted root is the default base only when it exists. Absence of an accepted
root requires an explicit stored-version base, and invalid, incomplete, or
identity-mismatched snapshots refuse rather than falling back to another
source.

The comparison core reuses a small public read-only seam extracted from
`roadmap_candidate`'s predecessor diff rather than creating a second semantic
diff engine. A comparison concept has the identity `(artifact key, row kind,
stable id)` and retains complete before/after typed rows, plan-ordering deltas,
and relation-occurrence deltas; `roadmap_view` remains the owner of roadmap-wide
indexing and display labels. A dependency-neutral comparison leaf owns the
deterministic attribution between parsed concept deltas and raw patch evidence:
it reports the residual evidence that no typed concept owns, without assigning
narrative, comments, or formatting to a nearby row by inference. Candidate
admission, authority, review identity, and publication stay private to the
candidate workflow.

For each of the fixed four artifact pairs, a controlled Git no-index invocation
with external diff disabled produces the complete unified patch. Its exact
bytes and invocation outcome are evidence, not a rendering aid: structured
cards explain the evidence but never replace, normalize, truncate, or silently
discard it. Git invocation and decoding failures are explicit comparison
failures. Any byte delta not attributable to a typed row, ordering entry, or
declared relation appears in an unmapped/raw-text section even when the typed
delta is empty.

The default terminal report starts with artifact and concept counts, then emits
one complete card per concept identity in artifact and source order. A card names
`added`, `removed`, or `changed`, uses the established display label, shows only
changed non-relation fields as before/after values, and lists added and removed
declared relations separately. A patch view prints the complete Git evidence.
Machine-readable output carries the same typed comparison, unmapped-text facts,
snapshot identities, per-snapshot artifact digests, and an identity derived from
the exact framed raw evidence without model-authored interpretation.

## In scope

- One read-only roadmap comparison surface with accepted-head,
  stored-version, and working-artifact selection under the contract above.
- Exact four-artifact Git evidence plus structured attribution of typed rows,
  ordering entries, declared relations, and unmapped text.
- A dependency-neutral read-only comparison leaf when direct reuse would make
  comparison depend on candidate policy; it owns pure row/relation records,
  raw-evidence attribution, and their shared tests without moving candidate
  admission, review requirements, impact identity, or mutation authority.
- Terminal summary/cards, complete patch presentation, machine-readable output,
  CLI help, roadmap format/reference documentation, and focused tests.
- Final reconciliation of `BACKLOG.md` #402 when the command ships.

## Scope guardrails

- The command never writes, accepts, enrolls, promotes, settles, repairs, or
  otherwise mutates a roadmap snapshot or its metadata.
- Git's complete unified diff over exactly the resolved four artifact pairs is
  the source of record. Structured output may attribute bytes to concepts but
  may not suppress, rewrite, or substitute for that evidence.
- Stable ids establish concept identity. An id change is a removal plus an
  addition, never semantic matching by label or prose.
- Comparison remains deterministic and model-free. No output field contains a
  generated judgment, summary, or acceptance recommendation.
- Existing roadmap views and lifecycle writers remain byte- and behavior-
  compatible.
- Discoveries involving other artifact families or acceptance policy stop and
  return to the backlog; they do not expand this plan.

## Out of scope

- Accepting, promoting, enrolling, settling, repairing, or mutating either
  snapshot, and any change to candidate proposal or review policy.
- Model-written summaries, semantic matching across changed stable ids, or
  generalized repository diffing.
- Comparing seeds, implementation plans, source briefs, receipts, run logs, or
  artifacts beyond the fixed roadmap inventory.
- HTML or another interactive renderer; it may follow only after the terminal
  and machine-readable contracts have shipped and supplied separate evidence.

## Allowed behavior changes

Add the comparison command, selectors, output modes, documented failures, and
shared read-only diff seams described here. Existing roadmap views, candidate
review, version admission, and mutation behavior do not change.

## Allowed reorganization

Move pure row/relation comparison records and functions into the
dependency-neutral comparison leaf only when direct reuse would create a
candidate-policy dependency. Do not duplicate them or relocate candidate
authority, admission, review requirements, impact identity, or publication
logic.

## Risks

- **Two truths drift:** a new comparison implementation could disagree with
  candidate review. Both callers share the typed diff owner and regression
  cases rather than duplicating it.
- **Pretty output hides evidence:** field projection or parsing could lose
  comments, narrative, or formatting. The raw patch remains complete and every
  unattributed byte delta is reported explicitly.
- **Selector ambiguity:** a missing accepted root or malformed stored version
  could prompt an unsafe fallback. Resolution is closed and fail-closed, with
  both selected identities printed.
- **Relation double counting:** relation-bearing row fields could appear as
  ordinary field edits and relation changes. The report separates declared
  relations from the row's non-relation fields while preserving occurrence
  changes.
- **Git environment variance:** user diff drivers or configuration could alter
  evidence. The invocation disables external diff behavior and reports command
  or decode failure explicitly.

## Testing

Prove one replay across the accepted-root default, explicit stored-version
base, and working/stored target routes: the bare plan retains the invariant
that one resolved pair yields both a complete Git patch and an attributable
concept report, while detail chooses fixtures and invocation mechanics. The
detail-grounded suite covers unchanged bundles; one-field decision settlement;
added, removed, field-only, ordering-only, relation-only, duplicate-relation,
raw-only, and byte-identical changes; and simultaneous changes across all four
artifacts. It proves deterministic terminal and machine-readable ordering,
per-snapshot identities and digests, explicit refusal for missing or
unparseable working artifacts, no accepted root without a base, unknown or
corrupt versions, Git failure, and decoding failure. It also proves comparison
changes no artifact, baseline, seed state, version selector, receipt, run log,
or Git index on success or refusal. Existing candidate-diff behavior remains
covered through the shared seam.

## Acceptance criteria

- An explicit working or stored target compares with the accepted root by
  default, while an explicit stored version can replace that base; no accepted
  root means the operator must select a base.
- Every report identifies both snapshots, their available version and brief
  identities, and each snapshot's four artifact digests.
- Terminal output gives compact counts and complete source-ordered concept
  cards with changed non-relation fields and relation deltas separated.
- Raw-only changes remain visible in an unmapped section, byte-identical
  artifacts are identified, and the patch view emits the complete controlled
  Git diff for all four pairs.
- Machine-readable output represents the same typed and unmapped comparison
  plus raw-evidence identity, with no model-authored interpretation.
- Git invocation/decoding and snapshot-resolution failures are explicit and do
  not mutate state or silently degrade to partial evidence.
- The implementation reuses the candidate typed-diff and roadmap label/index
  owners without importing candidate authority into comparison.
- The shipping documentation/status step reconciles `BACKLOG.md` #402.

## Deferred

An HTML or interactive concept-card view requires separate evidence after the
terminal and machine-readable contracts ship. Broader artifact comparison,
semantic id matching, and acceptance actions remain separate efforts.
If a selector requires a lifecycle recovery or migration path, exclude it from
the first release rather than inventing that path here.

## References

- `BACKLOG.md` #402 — source feature contract and lifecycle reconciliation.
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
