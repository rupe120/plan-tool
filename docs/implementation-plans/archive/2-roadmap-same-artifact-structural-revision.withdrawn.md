> **Withdrawn 2026-08-17** — Superseded before execution on 2026-08-17: the bare-plan audit found generic structural operations need a candidate-aware scope proof. The replacement plan keeps only candidate-gated rewrite-only work; BACKLOG #289 retains generic operations for a real widening request.
> Preserved here for history; do not edit.

---
title: Roadmap Same Artifact Structural Revision
intent: '`plan-tool roadmap` will turn one current structural-escalation receipt and
  its one selected open feedback row into a bounded, reviewable revision of exactly
  one canonical roadmap artifact. It will support explicitly typed operations on that
  artifact''s prose and live rows—including controlled row creation, replacement,
  removal, and relationship changes—plus one proposed feedback response. It will validate
  the resulting artifact and its existing read-only upstream dependencies before atomically
  publishing the single artifact. This is the next practical expansion of feedback
  revision: it can address a whole-artifact request or a row request that needs a
  new rule, entity, flow, decision, relation, or prose section, without re-entering
  every later roadmap stage. It does not become a cross-artifact transaction, a generic
  document editor, or an automatic broad `--from-stage` run.'
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Extract current receipt and impact-analysis checks without changing receipt
    views or impact routing
  intent: Give structural revision one reusable way to prove that exact named receipt
    and impact-analysis records still describe the selected source, feedback row, and
    route.
  files:
  - plan_tool/roadmap_escalation.py
  - plan_tool/roadmap_escalation_run.py
  - plan_tool/roadmap_impact_analysis.py
  - plan_tool/roadmap_impact_run.py
  - tests/test_roadmap_escalation.py
  - tests/test_roadmap_escalation_run.py
  - tests/test_roadmap_impact_analysis.py
  - tests/test_roadmap_impact_run.py
  complexity: medium
  change_type: refactor
  status: current
- id: 2
  title: Add receipt-and-impact-bound structural preflight and a bounded row and relation
    inventory
  intent: Reject stale, mismatched, ineligible, noncanonical, non-same-artifact, or
    cross-artifact input before invalidation or backend work and expose only the selected
    artifact slice plus immutable endpoint identities.
  files:
  - plan_tool/roadmap_relations.py
  - tests/test_roadmap_relations.py
  creates:
  - plan_tool/roadmap_structural_revision.py
  - tests/test_roadmap_structural_revision.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies reusable current-evidence predicates that bind structural preflight to
      exact receipt, source, feedback, and route facts.
- id: 3
  title: Define strict versioned operations, canonical prose regions, and per-artifact
    allowlists
  intent: Keep backend proposals inside duplicate-free explicit create, replace, remove,
    final-order, marked-prose, relation, and selected-feedback operations for one artifact.
  creates:
  - plan_tool/roadmap_structural_operations.py
  - tests/test_roadmap_structural_operations.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Supplies the selected artifact, feedback identity, and immutable row and relation
      inventory against which operations are validated.
- id: 4
  title: Apply one conflict-free operation envelope with bounded prose and selected-feedback
    removal authority
  intent: Build one candidate through fixed operation phases while preserving unmentioned
    rows, relations, feedback, removals, decisions, prose regions, ordering, and serialized
    bytes.
  creates:
  - plan_tool/roadmap_structural_revision_patch.py
  - tests/test_roadmap_structural_revision_patch.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: Supplies the immutable baseline and preservation inventory.
    3: Supplies the parsed, artifact-qualified operations the merger applies.
- id: 5
  title: Gate current immutable endpoint references and keep atomic replacement limited
    to the selected artifact
  intent: Use existing continuity, feedback, decision, relation, and upstream gates plus
    the structural endpoint policy to reject unauthorized candidates before the single-path
    publication boundary.
  files:
  - plan_tool/roadmap_revision_publish.py
  - tests/test_roadmap_revision_publish.py
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  depends_on_notes:
    4: Supplies the complete candidate and its unchanged current-artifact predecessor.
- id: 6
  title: Add redacted structural revision events while preserving atomic snapshot
    replacement and run-end cleanup
  intent: Record receipt and selector identities, bounded-context counts, operation
    and validation verdicts, publication results, attempts, and termination without
    storing sensitive text.
  files:
  - plan_tool/run_log.py
  - tests/test_run_log.py
  - DATA_CONTRACT.md
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Supplies the closed operation and verdict vocabulary represented by the lifecycle
      events.
- id: 7
  title: Run one current same-artifact request, preserve pre-backend seed invalidation,
    and replace only the selected artifact
  intent: Join receipt-and-impact admission, bounded prompt context, one backend attempt,
    deterministic merging, gate validation, conservative failure handling, and atomic
    publication without broad re-entry.
  files:
  - TESTING.md
  creates:
  - plan_tool/roadmap_structural_revision_run.py
  - plan_tool/prompts/roadmap-structural-feedback-revision.md
  - tests/test_roadmap_structural_revision_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 4
  - 5
  - 6
  depends_on_notes:
    4: Supplies the deterministic candidate merger and preservation checks.
    5: Supplies predecessor-aware gates and selected-path atomic publication.
    6: Supplies the redacted preflight, attempt, and terminal event contract.
- id: 8
  title: Wire an exclusive structural revision command and block local or broad fallback
  intent: Let operators name one selector, receipt, and same-artifact impact analysis,
    see the complete one-artifact write set before backend contact, and receive the correct
    result without accidental mode widening.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/cli/__init__.py
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/package_surface_help.golden.txt
  - docs/cli/roadmap.md
  complexity: high
  change_type: feature
  depends_on:
  - 7
  depends_on_notes:
    7: Supplies the typed runner result, operator-selection callback, exit mapping
      facts, and injected backend seam.
- id: 9
  title: Document presentation, structural, escalation, and broad roadmap revision
    paths
  intent: Help reviewers choose the bounded path, inspect the proposed response, and
    explicitly accept, reopen, defer, or escalate feedback without confusing evidence
    with canonical authority.
  files:
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_format.py
  - README.md
  - CLAUDE.md
  - CAPABILITIES.md
  - docs/ARCHITECTURE.md
  - docs/ROADMAP_WALKTHROUGH.md
  - RUNBOOK.md
  - integrations/claude/SKILL.md
  complexity: high
  change_type: non-code
  depends_on:
  - 3
  - 6
  - 8
  depends_on_notes:
    3: Supplies the final operation schema and artifact-specific mutation boundaries.
    6: Supplies the landed lifecycle, redaction, and outcome vocabulary.
    8: Supplies the final command form, conflict rules, write-set output, and reviewer-facing
      result behavior.
---
# Roadmap Same Artifact Structural Revision

## Overview

`plan-tool roadmap` adds a bounded structural-revision path that consumes one
current structural-escalation receipt, one current `same-artifact` impact
analysis, and one selected open feedback row. It proposes strict typed changes
to exactly one canonical roadmap artifact and one feedback response. It
supports controlled replacement of existing canonical prose regions plus row
creation, replacement, removal, final ordering, and allowed relationship
changes without re-entering later roadmap stages. The command validates its
bounded candidate and immutable read-only dependencies before atomically
publishing the single artifact, while preserving reviewer ownership of
feedback.

## Problem statement

`roadmap-incremental-revision` permits only one same-artifact row, one allowlisted presentation-field replacement, and one feedback response. That boundary cannot fully answer feedback targeting an entire artifact such as `01-domain.md`, or row-targeted feedback that requires additional rules and relations such as a lifecycle map; treating either request as a local presentation edit would report a partial answer as satisfied.

`roadmap-structural-revision-escalation` supplies immutable receipt and selected-source evidence, but there is no write-capable structural path that consumes it. Broad `--from-stage` re-entry would rewrite later artifacts unnecessarily, while a cross-artifact transaction would exceed the current local publisher's atomic single-path guarantee.

## Architecture

The structural runner takes one artifact-qualified feedback selector, the
semantic id/digest of a current version-1 escalation receipt, and one named
current impact-analysis record bound to that same receipt and selector. Before
seed invalidation or a backend call, it revalidates the receipt's closed schema
and duplicate-member-free JSON, shared selector grammar, semantic identity,
source digest, source-derived target kind/id, and complete receipt-selection
predicate. It then revalidates the impact-analysis record's canonical bytes,
semantic binding, fresh full relation closure, and route class. Only a current
`same-artifact` route whose one affected artifact is the selected artifact is
admitted. A missing, stale, source-target-mismatched, selection-ineligible,
invalid, non-structural, scope-review, or cross-artifact record is refused;
the receipt's `requires-scope-review` handoff is never treated as route
authority. A normal `--revise-feedback` attempt never falls through into this
mode.

The selected artifact is the complete canonical write set. The selected
feedback may target a row or the artifact. Current upstream artifact objects
remain read-only gate inputs, and only their allowed endpoint identities and
relation kinds enter backend context. Sibling and downstream artifacts, draft
seeds, repository code, unselected feedback, other artifact prose, and
generated seeds stay outside backend context and the write set. Operator output
names this one-artifact write set before the backend call.

The backend returns a closed, versioned operation schema rather than a
replacement artifact. Its duplicate-member-free, finite JSON decoder rejects
ambiguous object members and nonstandard numeric values before strict model
validation. Variants cover `replace-prose-region`, create, replace, remove,
and one final collection-order operation, plus exactly one selected-feedback
response. Every row operation declares its row type and stable target identity
where one exists. New rows carry schema-valid stable IDs and explicit relation
endpoints.

Canonical prose regions use exactly the versioned Markdown comments
`<!-- plan-tool:prose-region <safe-id> begin -->` and
`<!-- plan-tool:prose-region <safe-id> end -->`. A region identifier must occur
exactly once in the predecessor, its delimited contents must be strictly smaller
than the artifact body, and a replacement preserves both delimiters and every
byte outside that region. The writer never creates, renames, infers, or expands
a region; absent, duplicate, overlapping, malformed, or full-body regions
refuse. A create may proceed only when declared replacement regions make every
new live row id visible to the existing prose-inventory gate. Artifact-specific
allowlists define which of the four canonical artifact row models can be
created, changed, removed, or ordered in each stage, which prose regions they
may update, and which gate protects every allowed relation change.

A deterministic merger applies operations in fixed phases, not backend reply
order: validate targets and conflicts; create or replace rows; record allowed
removals; apply at most one exact final order for each affected row collection;
replace prose regions; then attach the selected response. Two operations on one
existing row or prose region reject. A final-order operation is the only
collection-wide exception: it names an exact permutation of all post-mutation
ids in that row collection, so it can include newly created rows but cannot
omit, duplicate, or infer a row. Without that operation, retained row order is
unchanged. A new removal cites exactly the selected feedback id and rejects if
any unselected carried feedback targets the removed row.

The merger rejects ID collisions, unrecognized row types, target or phase
conflicts, inferred targets, invalid order permutations, operations outside the
selected artifact, and invalid relation endpoints. Rows, removals, feedback,
decisions, prose regions, ordering, and accepted serialized data absent from an
allowed operation remain unchanged. The selected artifact must first pass the
same render-canonical preflight used by local revision, so opaque or lossy
input is rejected instead of normalized.

Each backend reply contains exactly one `respond-feedback` operation for the selected open feedback row. A valid candidate may move only that row to `awaiting-review` with a proposed response; it cannot close feedback, change another feedback row, infer acceptance, or treat generated structural content as human approval.

Candidate construction flows through parser and gate validation before atomic
one-artifact publication. A relation field may name only an allowlisted
outgoing relation kind from the selected artifact to a current immutable
upstream endpoint id. It cannot change an upstream row, cite a sibling or
downstream endpoint, or admit a relation whose semantics require a second
canonical write; the current impact route and candidate gates refuse that
shape. The runner reuses the shared participating-writer guard, established
durable pre-backend seed-invalidation seam, local revision failure and
interrupt seams where their contracts fit, and existing conservative state and
writer guarantees. It never materializes, refreshes, accepts, or promotes seed
prose, and a failed attempt may leave drafts stale but cannot leave changed
roadmap content represented by a current derived draft.

Backend context contains only the current receipt and impact route facts, the
selected feedback, the selected artifact's canonical prose and rows, immutable
selected-row and allowed-upstream-endpoint inventories, and the closed
operation schema. The command records selector, receipt, and impact-analysis
semantic ids and digests, write-set summary, context bytes/counts, operation
verdicts, validation and publication result, termination reason, and one
explicit backend-attempt outcome. It does not retry through broad stage
authoring, and logs exclude feedback requests, roadmap prose, prompts, backend
replies, and raw seed content.

Shared selector, receipt-identity validation, operation-validation, candidate-gate, or writer-guard helpers may be extracted only when ownership remains clear between local and structural single-artifact modes. Broad stage generation, artifact schemas, seed machinery, and readers are not refactored merely to make revision modes uniform.

## Input

This plan consumes one artifact-qualified feedback selector, one selected open
feedback row, the semantic id/digest of a current version-1
structural-escalation receipt produced by `roadmap-structural-revision-escalation`,
and one named current impact analysis from `roadmap-escalation-impact-routing`.
It relies on the receipt's closed, duplicate-member-free JSON schema; shared
selector grammar; semantic identity; source digest; source-derived target
kind/id; structural classification; complete receipt-selection predicate; and
the analysis's fresh full closure, same receipt/selector binding, and exactly
`same-artifact` route.

It also reads the selected artifact's canonical prose and rows, its immutable
row/relation inventory, and any required upstream artifact objects used by
existing read-only gates. Backend context receives only allowed upstream
endpoint identities, never upstream prose or rows. Sibling and downstream
artifacts, repository code, unselected feedback, draft seeds, other artifact
prose, and generated seeds are neither writable nor supplied to the backend.

## References

- [Pydantic Unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions) — Explains discriminated unions for validating the backend's closed set of typed operation variants.
- [Pydantic Configuration](https://docs.pydantic.dev/latest/api/config/) — Documents strict, frozen, and extra-forbid model settings needed for immutable closed schemas.
- [Python 3.13 json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Covers strict JSON decoding hooks such as object_pairs_hook for rejecting duplicate members before model validation.
- [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Defines deterministic duplicate-free JSON serialization suitable for stable semantic identities and digests.
- [JSON Schema Draft 2020-12 Core Specification](https://json-schema.org/draft/2020-12/json-schema-core) — Defines versioned JSON schemas and applicator semantics relevant to a closed operation-envelope contract.
- [Python 3.13 os — Miscellaneous Operating System Interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Documents os.replace and filesystem synchronization primitives used for atomic single-artifact publication.
- [Python 3.13 fcntl — File and I/O Control](https://docs.python.org/3.13/library/fcntl.html#fcntl.flock) — Documents advisory shared and exclusive file locking needed to preserve participating-writer guarantees.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Selecting multiple feedback rows, coalescing requests, or inferring related feedback items; this command handles one explicitly selected row.
- Writing multiple canonical roadmap artifacts, deriving a dependency closure, or adding multi-file publication and recovery; the complete write set remains one artifact.
- Backend-created free-form YAML/Markdown replacement, arbitrary manual text editing, collaborative editing, or lossless editing of unknown extensions; mutations use the closed typed-operation schema.
- Initializing, migrating, or repairing canonical prose-region markers as part of a structural feedback request; the writer refuses an artifact that lacks an eligible predecessor region.
- Altering `--from-stage`, its prompts, retry/timeouts, or broad write and recovery semantics; structural revision is an exclusive path.
- Per-plan selective seed invalidation, seed generation or promotion, or changes to materialization state semantics; the runner reuses existing conservative behavior.
- Git checkpoints, worktree requirements, external tickets, identity changes, or a browser workflow; none belongs to this revision path.

## Risks

- **Cross-artifact widening — critical boundary risk.** A request may require another canonical artifact. The command mitigates this by requiring a fresh current `same-artifact` impact analysis before seed invalidation, rejecting every other route, preserving evidence, and routing the request to the cross-artifact seed rather than adding a second writer.
- **Ambiguous prose scope — mutation-boundary risk.** An opaque body, duplicate marker, overlapping region, or body-wide region could turn a local request into an uncontrolled document rewrite. The command accepts only eligible pre-existing canonical prose regions and preserves their delimiters and all out-of-region bytes.
- **Operation interaction — deterministic-merge risk.** Backend ordering or overlapping row actions could hide a remove/replace/order conflict. The fixed phases, one-target rule, exact post-mutation order permutation, and selected-feedback-only removal authority reject the envelope before a candidate exists.
- **Unrepresentable structural mutation — blocking schema risk.** A row type may not be safely expressible through explicit typed operations and existing gates. Work stops and records the schema gap; preflight, type checks, and conservative invalidation remain unchanged.
- **Lossy or opaque input mutation — publication risk.** Normalization could discard accepted serialized data or unknown content. The render-canonical preflight rejects such input before mutation.
- **Partial or unauthorized mutation — publication risk.** Collisions, duplicate JSON members, inferred targets, phase conflicts, invalid order permutations, invalid relation endpoints, unmentioned changes, a removed row targeted by unselected feedback, cross-artifact operations, and changes to unselected feedback could corrupt the bounded candidate. The strict parser, deterministic merger, operation allowlists, preservation rules, structural gates, and atomic publisher reject these cases before publication.
- **Stale derived state after failure — conservative state risk.** An accepted preflight invalidates seed state before the backend call, so a backend, parse, gate, or interrupt failure may leave drafts stale. The artifact remains byte-for-byte intact, and no changed roadmap content is represented by a current derived draft.
- **Sensitive content in lifecycle evidence — observability risk.** Logs could expose feedback, roadmap prose, prompts, backend replies, or raw seeds. Evidence is restricted to semantic ids, digests, counts, verdicts, results, and termination metadata.

## Testing

Unit and CLI coverage exercises receipt-and-analysis admission, every operation
type, artifact-specific allowlists, canonical prose-region preflight,
duplicate-member/non-finite JSON rejection, deterministic phase and conflict
behavior, forbidden write-set widening, stale and mismatched receipt or impact
analysis rejection, render-canonical preflight, byte preservation of
unmentioned content, parser and gate failures, writer interleavings, sidecar
invalidation, and observability redaction. Fixtures include Integration-shaped
artifact-level domain feedback with a bounded prose region and row-targeted
lifecycle-map feedback.

Candidate tests attempt an ID collision, duplicate JSON member, non-finite
value, overlapping row actions, a malformed, duplicate, overlapping, or
full-body prose region, an unmentioned-row change, mutation of an unselected
feedback row, removal of a row targeted by unselected feedback, a removal
citing another feedback id, an invalid final-order permutation, an upstream or
sibling artifact change, an invented or disallowed relation endpoint, a
whole-document replacement, and omission of the selected response; each must
fail before publication. Failure-path tests cover backend, parse, gate, and
interrupt outcomes after accepted preflight and verify that the artifact remains
byte-for-byte intact with only the existing conservative seed-state result.

Regression coverage keeps existing local `--revise-feedback`, structural escalation, `--from-stage`, materialize/refresh/apply, and roadmap view contracts passing. Tests use no live backend. One disposable opt-in smoke test exercises a real structural feedback row and verifies the event and redaction boundary.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.
- step 8 (feature) — tests covering the behavior this step changes; green before completion.
- step 9 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- Given a current artifact-target escalation receipt and a current same-artifact impact analysis for a fixture domain artifact, the command can replace one eligible prose region, add a new rule, entity, or flow and its declared relations, then publishes only the selected artifact and its selected feedback response after parser and gate success.
- Given a current row-targeted escalation receipt and a current same-artifact impact analysis, the command can add a multi-row lifecycle map and publishes only the selected artifact and selected feedback response after parser and gate success.
- Before any backend call, operator output names the complete one-artifact write set.
- Missing, stale, source-target-mismatched, selection-ineligible, invalid, or non-structural receipts, and missing, stale, invalid, mismatched, scope-review, or non-same-artifact impact analyses, are rejected before seed invalidation or backend contact.
- Noncanonical, opaque, or lossy artifact input; an absent, ambiguous, overlapping, malformed, or full-body prose region; and an ineligible new-row prose placement are rejected before seed invalidation or backend contact.
- Every accepted backend reply uses duplicate-member-free finite JSON, the closed typed-operation schema, and exactly one `respond-feedback` operation for the selected open feedback row.
- A candidate may move only the selected feedback row to `awaiting-review` with a proposed response; it cannot close feedback, alter another feedback row, or infer acceptance.
- A new removal cites exactly the selected feedback id and cannot remove a row targeted by unselected carried feedback.
- ID collisions, duplicate or conflicting operations, unrecognized row types, inferred targets, invalid final-order permutations, invalid or disallowed relation endpoints, whole-document replacement, unmentioned changes, and operations outside the selected artifact fail before publication.
- Content absent from an allowed operation remains byte-for-byte unchanged; a prose replacement preserves delimiters and all out-of-region bytes, and retained row order remains unchanged unless one exact allowed final-order operation names the full post-mutation collection.
- Backend, parse, gate, and interrupt failures after accepted preflight leave the canonical artifact byte-for-byte intact and retain only the existing conservative seed-state result.
- Successful publication is atomic and changes exactly one canonical roadmap artifact.
- Logs contain selector, receipt, and impact-analysis semantic ids and digests, write-set summary, bounded-context counts, operation verdicts, validation and publication result, termination reason, and one backend-attempt outcome, but no feedback request, roadmap prose, prompt, backend reply, or raw seed content.
- Existing local `--revise-feedback`, structural escalation, `--from-stage`, materialize/refresh/apply, and roadmap views retain their documented contracts.
- Documentation distinguishes presentation revision, structural same-artifact revision, escalation, and broad stage re-entry, and explains how a reviewer inspects the proposed response and explicitly accepts or reopens feedback through the existing lifecycle.

## Deferred

- Cross-artifact structural revision is routed to the cross-artifact seed when a request requires another canonical artifact; this command retains its one-artifact writer boundary.
- A row type that cannot be represented safely through explicit typed operations and existing gates is deferred as a recorded schema gap rather than admitted by weakening validation.
- An artifact without an eligible pre-existing canonical prose region is rejected for prose-changing structural work; marker initialization remains an explicit future format-migration decision rather than an implicit writer side effect.
