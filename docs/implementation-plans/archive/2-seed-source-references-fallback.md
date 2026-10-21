> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Seed Source References Fallback
intent: Every maintained seed that instructs an operator to run `plan-tool create
  --from-existing` includes a non-placeholder `## References` fallback, so it reaches
  its intended authoring route instead of failing before slug inference or a model
  call.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/seed-source-references-fallback.md
steps:
- id: 1
  title: Make the References fallback body-only, then add it to the remaining plan
    seeds
  intent: Every live checked-in seed plus annotate and both scope-out forms reaches
    its existing authoring route; a YAML-frontmatter comment cannot counterfeit References,
    and missing or placeholder body input remains a pre-invoker no-write refusal.
  files:
  - plan_tool/create.py
  - plan_tool/annotate_render.py
  - plan-seeds/audit-finding-staleness-classification.md
  - plan-seeds/audit-shape-advisory-generic-walk.md
  - plan-seeds/audit-shape-saturation-and-provenance.md
  - plan-seeds/completeness-output-quality.md
  - plan-seeds/connectivity-pause-and-poll.md
  - plan-seeds/convergence-policy-channel-ownership.md
  - plan-seeds/create-detail-phase-decomposition.md
  - plan-seeds/deferred-findings-digest.md
  - plan-seeds/disable-jira-grade-detail-authoring.md
  - plan-seeds/feature-health-2-attribution-and-ledger.md
  - plan-seeds/jira-sweep-verify-code-truth.md
  - plan-seeds/lessons-store-restructure.md
  - plan-seeds/premise-ledger.md
  - plan-seeds/reseed-advisor.md
  - plan-seeds/risk-profile-3-advisory-effectiveness.md
  - plan-seeds/walk-advisory-chat-mode.md
  - tests/test_create.py
  - tests/cli/test_authoring_cmds.py
  - tests/test_annotate_render.py
  - tests/test_scope_out.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/seed-source-references-fallback/01-make-references-fallback-body-only-then.md
  status: done
- id: 2
  title: Admit roadmap seeds only when their body References cites all accepted artifacts
  intent: Materialized roadmap drafts, hand-accepted edits, and batch-promoted plan-seed
    copies are derived from bytes admitted by one draft-seed rule and satisfy the
    create preflight, while preserving separate roadmap-provenance validation.
  files:
  - plan_tool/prompts/roadmap-seed.md
  - plan_tool/roadmap_gates.py
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  - tests/test_roadmap_gates.py
  - tests/test_roadmap_seed_manifest.py
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/seed-source-references-fallback/02-admit-roadmap-seeds-only-when-their.md
  status: done
- id: 3
  title: Add source-plan References to rebaseline seeds and preserve the existing
    seed overwrite and plan replacement
  intent: Rebaseline seeds name their source plan so the recommended create command
    reaches authoring.
  files:
  - plan_tool/reground.py
  - tests/test_reground.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/seed-source-references-fallback/03-source-plan-references-rebaseline-seeds.md
  status: done
- id: 4
  title: 'Record the repaired seed sources and close BACKLOG #351'
  intent: The contract, backlog arc, and work queue describe the shipped compatibility
    state and hand off to the next scoped ingestion change.
  files:
  - docs/reference/contracts/seed-ingestion.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: The checked-in corpus and unchanged annotate and scope-out producers are validator-clean.
    2: Roadmap materialization and promotion produce create-compatible References.
    3: Rebaseline rendering produces create-compatible References.
  detail: docs/implementation-plans/plan-details/seed-source-references-fallback/04-record-repaired-seed-sources-close.md
  status: done
---
# Seed Source References Fallback

## Overview

`create --from-existing` rejects a source without a non-placeholder References
H2 before any authoring work. That H2 must be in the Markdown prose body: a
YAML-frontmatter comment must not satisfy a user-facing source-evidence
contract. The active seed corpus and maintained producers can nevertheless
write or advertise sources without that fallback. Align those producers and
live inputs with the existing deterministic contract, without adding a
universal requirement for other body sections.

## Problem statement

The one hard source preflight is correct because a failed reference-research
response cannot replace source evidence. Its guarantee is currently
undermined by inputs the project itself supplies: they promise a
`--from-existing` handoff, then deterministically refuse at that handoff. A
frontmatter comment can also make a source appear to meet the preflight while
leaving the visible body without evidence. The failure hides the intended
preparation route and blocks the active seed queue before a user can evaluate
it.

## Architecture

Keep `validate_from_existing_seed` as the single create-owned check and read
its References H2 only after stripping leading frontmatter. The annotate
fallback follows the same body-only interpretation; scope-out already extracts
from the parsed plan body. Each producer owns its fallback: hand-authored
seeds cite the source that already grounds their work, roadmap materialization
cites `01-domain.md`, `02-constraints.md`, `03-components.md`, and
`04-roadmap.md` in its body References H2, and rebaseline cites the source
plan.

Extend the existing `validate_draft_seed_content` admission gate with that
four-artifact References rule. Materialization calls it before its write and
hand acceptance calls it before it records a new digest or resynchronizes a
published copy. Batch promotion classifies first, then validates one fresh
read of each source and derives the promoted body from those same admitted
bytes; it never promotes a later unvalidated reread. The routes therefore
share one rule while roadmap provenance remains a separate check. Tests call
the real create preflight against rendered output rather than reimplementing
H2 or placeholder recognition.

## References

- [CommonMark Spec — ATX headingshttps: — Defines Markdown heading syntax, including optional closing hash sequences relevant to recognizing the References H2.
- [Python 3.13 — Regular expression operationshttps: — Documents multiline anchors, compiled patterns, and matching behavior used by heading and placeholder recognition.
- [Python 3.13 — Object-oriented filesystem pathshttps: — Covers Path globbing and text-file operations needed to enumerate seeds and load source artifacts.
- [Python 3.13 — Common string operationshttps: — Documents string.Template substitution semantics used to materialize roadmap-seed prompts from accepted artifacts.
- [pytest — How to parametrize fixtures and test functionshttps: — Explains parameterized test cases for validating every maintained seed and representative generated-source route.
- [pytest — How to use temporary directories and files in testshttps: — Covers isolated filesystem fixtures for testing generated seeds and fail-before-write preflight behavior.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Adding canonical-body H2 requirements beyond References.
- Altering distillation, body synthesis, direct-ready routing, split proposals,
  or model-call ordering; BACKLOG #327 owns those changes.
- Rewriting archived seeds or introducing a seed schema.
- Treating a placeholder, a generic fabricated URL, or an empty list as
  reference evidence.

## Risks

- A rote corpus sweep could add stale or irrelevant links. Each new block must
  cite the seed's actual source evidence and retain existing citations.
- A roadmap-only provenance test could pass while the emitted seed still fails
  `create` validation. Exercise materialization, hand acceptance, and batch
  promotion with a draft that omits one accepted-artifact reference, and call
  the create preflight on successful materialized and promoted bodies. Also
  change a draft after classification and prove batch promotion refuses rather
  than rereading and publishing unvalidated bytes.
- Parsing source headings before frontmatter removal can let a YAML comment
  counterfeit References. Use a frontmatter-only control for both create and
  annotate, alongside an ordinary body References success case.
- Rebaseline currently receives the parsed plan rather than its body text.
  Keep the repair minimal by naming the source plan rather than adding another
  source-body reader to preserve its References section.

## Testing

Run focused create, annotate, scope-out, reground, roadmap, and roadmap-seed
manifest suites. Add a parameterized preflight test that loads every root
`plan-seeds/*.md`, and test missing, placeholder, and frontmatter-comment
References controls through the actual validator with an invoker that would
fail if called. Exercise each generated source after its renderer/prompt path.
For roadmap, prove the shared gate rejects a missing one-of-four artifact
reference before materialization writes, hand acceptance records, or batch
promotion writes; prove successful materialized and promoted bodies pass
`validate_from_existing_seed`; and prove batch promotion stages its admitted
source snapshot rather than a later source reread.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering body-only References recognition, the root seed corpus, and annotate and scope-out rendered sources.
- step 2 (feature) — tests covering the shared four-artifact admission gate, exact-byte batch promotion, and the real create boundary for materialized and promoted outputs.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- Every top-level file under `plan-seeds/` passes
  `validate_from_existing_seed`; archive files are not changed.
- A References H2 in YAML frontmatter alone does not satisfy create validation
  or suppress annotate's fallback; a non-placeholder body H2 does.
- A roadmap materialized draft, a hand-accepted edit, and a batch-promoted
  `plan-seeds/` copy all require body References that cite
  `01-domain.md`, `02-constraints.md`, `03-components.md`, and
  `04-roadmap.md`, while roadmap provenance validation remains intact.
- Successful roadmap materialized and promoted copies carry a non-placeholder
  body References H2 and pass the create validator.
- Batch promotion refuses if source bytes change after classification and
  before its admitted snapshot is staged; it cannot publish an unvalidated
  reread.
- A rebaseline seed emits a source-plan References fallback, and both scope-out
  renderers and annotate remain validator-clean.
- A missing or placeholder References control still fails before the first
  authoring invoker, output, checkpoint, archive, plan, or manifest write.

## Deferred

- The direct-ready versus preparation result table, optional-section rendering,
  and source-authority changes belong to BACKLOG #327 after this compatibility
  repair. A section is optional there only when its absence passes intake,
  triggers no completion call, omits its rendered block, and cannot fail a
  later gate; this repair keeps References required under the current contract.
- Conservative aliases for near-miss canonical H2s remain BACKLOG #102.
