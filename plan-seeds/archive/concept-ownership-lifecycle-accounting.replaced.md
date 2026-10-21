> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-ownership-lifecycle-accounting.md`.
> Preserved here for history; do not edit.

# Plan seed: Concept Ownership Lifecycle Accounting

This file is a `plan-tool create` input. Use the Codex backend after
`concept-publication-transactions` has shipped its public mutation/publication
contract. Consume the already-reconciled explicit ownership schema, merge
conservation, and re-ground preservation from `concept-signoff-integrations`;
do not reimplement them.

Evidence source:
`docs/implementation-plans/plan-details/concept-signoff-integrations/convergence-evidence-and-split-recommendation.md`.

## Overview

Make concept accounting survive every supported lifecycle transformation. A
reviewed concept is accounted for only when it has an exact active owner or a
valid structured non-delivery record. A decision value such as `wont_do` is not
by itself an accounting link. Split, merge, re-ground, scope-out, and create from
a re-baseline/forward seed must preserve or deliberately transform both active
ownership and structured deferral references without title inference.

This plan owns accounting policy, structural conservation, seed restoration, the
completeness test matrix, and generated documentation parity. It consumes the
publication contract from `concept-publication-transactions` and the structured
authoring protocol from `concept-authoring-boundary-hardening`.

## Problem statement

The completed integration made `Step.concept_ids` authoritative, and merge and
re-ground preserve those IDs. Several lifecycle gaps remain:

- `check_concept_coverage()` treats any approved `wont_do` node as covered even
  when it has no structured record explaining the non-delivery decision.
- Structured detail deferrals identify an emitting step, but split and merge can
  remove or renumber that step while transforming only `concept_ids`.
- Split conservation tests do not pin invented extra IDs or prove that dry-run
  replacement proposals preserve the exact ownership distribution.
- Re-ground and scope-out render concept IDs into seeds, but create does not
  consume those IDs as authoritative restoration metadata or resolve conflicts
  with the signed concept record.
- Scope-out's direct-save publication gap is fixed by the prerequisite plan, but
  this plan must prove its prepared accounting transformation is correct before
  publication.
- CLI documentation describing explicit-link coverage is generated from parser
  help; editing the generated README/index without its source fails drift checks.

The missing invariant is a conservation law over both delivery and deliberate
non-delivery.

## Reconciliation and completeness evidence to close

- `step5-run-reconcile-69028ee5` — `wont_do` bypasses explicit accounting.
- `step5-run-reconcile-6b8b7ab0` — missing multiple-concept, unsigned,
  renumbering, producer-parity, and advisory-rendering cases.
- `step6-run-reconcile-cb54717a` — missing direct extra-ID rejection coverage.
- `step6-run-reconcile-be1832fa` — dry-run test does not assert ownership
  distribution.
- Completeness finding `structural-deferral-links` — split/merge leave structured
  deferrals pointing at deleted or wrong steps.
- Completeness finding `forward-seed-ownership-restoration` — seeds carry IDs but
  create does not restore their authoritative mapping.
- `step10-run-reconcile-d05fb53f` — generated CLI documentation has the wrong edit
  boundary.

Use the clean reconciliation of original steps 1, 7, and 8 as frozen evidence:
the persisted `concept_ids` schema, merge union, and re-ground preservation are
prerequisites and regression fixtures, not work to regenerate.

## Accounting model

### Accounted concept invariant

For each reviewed concept whose decision is active in the signed record, exactly
one of these forms must be valid after every operation:

1. **Delivery accounting:** one or more committed/done steps contain the exact
   stable concept ID.
2. **Non-delivery accounting:** a structured record identifies the concept ID,
   decision (`defer` or `wont_do`), rationale/evidence, review/approval state, and
   a stable source/artifact reference that remains meaningful after step
   transformations.

The decision enum alone is not an accounting link. Unsigned proposals remain
advisory and cannot satisfy blocking completeness. Heuristic title/body matches
may suggest an owner but never count as accounting.

Define how multiple owners and multiple deferral sources behave. Avoid an
exclusive-one-owner rule: `Step.concept_ids` intentionally supports many owners.
Reject contradictory simultaneous delivery and signed non-delivery unless the
data contract explicitly models a partial decision.

### Stable deferral references

Prefer a stable deferral identity independent of mutable step number. If an
emitting step/artifact reference remains part of the record, structural remedies
must provide an explicit mapping:

- split maps the source link to the child or children that inherit the relevant
  concept/body, without inventing or dropping IDs;
- merge maps source links to the replacement step and deduplicates equivalent
  records deterministically;
- re-ground preserves links for unchanged artifacts and carries machine-readable
  restoration metadata for replacements;
- scope-out converts concepts with no surviving owner into structured
  non-delivery records and clears approval when the decision changes;
- include-triggered regeneration removes resolved deferrals only after the new
  artifact is durable.

If a stable artifact ID can eliminate step-number remapping, introduce it only
when its persisted contract and migration/default behavior are bounded in this
plan. Do not fall back to title matching.

### Seed restoration envelope

Re-baseline and forward seeds must carry a machine-readable ownership/accounting
envelope, not prose that the model is expected to reinterpret. It must include
stable concept IDs, source step/artifact identity, disposition, and enough
provenance to detect whether the originating signed record matches.

Create consumes the envelope before model proposal, restores exact mappings onto
replacement steps through an explicit proposal/review phase, and detects:

- unknown concept IDs;
- stale or mismatched source record fingerprints;
- one source step mapping ambiguously to multiple proposed steps;
- dropped concepts;
- invented IDs; and
- conflicts between seed restoration and current signed decisions.

Unattended create must not silently guess a mapping. It may retain unsigned
restoration proposals or stop with an actionable review requirement.

### Completeness behavior

`check_concept_coverage()` remains read-only and inert when no record exists.
For a current record it emits one stable finding per unaccounted reviewed concept,
regardless of whether its decision is include, defer, or `wont_do`, using policy-
appropriate remediation. Unsigned parked decisions retain their separate
nonblocking advisory. Dangling ownership and deferral links must be reported
without being mistaken for valid coverage.

## Proposed implementation sequence

### 1. Define structured non-delivery accounting

Files likely involved:

- `plan_tool/concept_tree.py`
- `plan_tool/detail.py`
- `plan_tool/data_contract.py`
- `DATA_CONTRACT.md`
- `tests/test_concept_tree.py`
- `tests/test_data_contract.py`

Define the durable identity and fields of a deferral/`wont_do` accounting record,
including stable source/artifact linkage and conflict rules. Reuse the structured
detail candidate model where possible; do not maintain two incompatible local
schemas. Provide pure validation and transformation helpers consumed by create,
detail, completeness, and structural remedies. Persist only through the
prerequisite publication API.

### 2. Correct completeness semantics and diagnostics

Files likely involved:

- `plan_tool/review.py`
- `plan_tool/completeness_report.py`
- `plan_tool/cli/completeness_phases.py`
- `tests/test_review.py`
- `tests/cli/test_completeness_cmd.py`

Remove the unconditional `wont_do` suppression. Validate exact owners and
structured non-delivery records, emit stable findings for missing/dangling/
contradictory links, and preserve advisory-only unsigned behavior. Add multiple
missing concepts, unsigned included and parked candidates, renumber-stable IDs,
producer parity, and report rendering/nonblocking cases.

### 3. Conserve deferral links across split and merge

Files likely involved:

- `plan_tool/create.py`
- `plan_tool/detail.py`
- `tests/test_create.py`
- `tests/test_detail.py`

Extend split/merge proposal validation and apply transforms to cover structured
accounting records as well as `concept_ids`. Reject dropped and invented IDs,
ambiguous link mappings, and links to removed steps. Add direct proposal and
dry-run assertions. Keep the already-shipped exact split union, ordered merge
union, and clean merge behavior; change only what is necessary to conserve the
new accounting link.

### 4. Make re-baseline and forward seeds round-trip accounting

Files likely involved:

- `plan_tool/reground.py`
- `plan_tool/scope_out.py`
- `plan_tool/create.py`
- the relevant seed/distillation prompt or parser
- `tests/test_reground.py`
- `tests/test_scope_out.py`
- `tests/test_create.py`

Render a bounded machine-readable restoration envelope for done-context,
remaining, deferred, and carved concepts. Parse it deterministically before
model synthesis. Require create proposals to map every carried ID exactly or
retain unresolved unsigned state for operator review. Test stale fingerprints,
unknown/invented/dropped IDs, ambiguous replacement mappings, legacy seeds with
no envelope, and exact round trips through re-ground and scope-out.

### 5. Exercise the full lifecycle conservation matrix

Files likely involved:

- `tests/test_create.py`
- `tests/test_detail.py`
- `tests/test_reground.py`
- `tests/test_scope_out.py`
- integration tests for completeness/reconcile behavior

Build fixtures with multiple concepts, shared owners, sole owners, defer and
`wont_do`, unsigned proposals, and structured records. Run create restoration,
split, merge, re-ground, scope-out, include regeneration, and completeness after
each transition. Assert exact IDs/links and absence of title inference. Include
dry-run, blocked, declined, stale/malformed, publication failure, and rollback
paths, consuming the prerequisite transaction API.

### 6. Update source-owned CLI/docs and reconcile the backlog

Files likely involved:

- parser/help source for completeness commands
- generated CLI reference/index via its repository generator
- `docs/cli/completeness-audit.md`
- `docs/cli/completeness-apply.md`
- `RUNBOOK.md`
- `CLAUDE.md`
- `BACKLOG.md`

Document exact ownership, structured non-delivery accounting, lifecycle
conservation, seed restoration, and routing of non-apply-eligible ownership gaps.
Edit parser/help sources first and regenerate derived CLI documentation with the
existing generator; do not hand-edit a generated row. Update backlog status only
after verifying the named production and test surfaces at HEAD.

## Out of scope

- Canonical publisher internals, rollback journals, create collision staging, or
  sidecar-only review persistence.
- Evidence grounding, Unicode fail-soft behavior, structured-response parsing,
  and detail active-file replacement.
- Heuristic matching as coverage authority.
- Automatically inventing implementation steps to cover concepts.
- General migration of arbitrary experimental sidecars/seeds without the shipped
  schema/provenance.
- Reimplementing already-clean merge union or re-ground preservation.

## Risks and controls

- **Deferral identity duplicates concept identity:** keep concept ID and accounting
  record ID/source identity distinct and document their roles.
- **Step-number coupling remains:** use stable artifact identity or explicit
  transform maps; never assume renumbered IDs mean the same step.
- **Seed prose becomes authority:** parse a bounded envelope and validate against
  the signed record; prose remains context only.
- **Many-owner semantics collapse:** conserve ordered sets without requiring one
  owner; test shared and sole ownership separately.
- **`wont_do` becomes impossible to satisfy:** define its structured record and
  operator workflow before enabling the blocking finding.
- **Cross-plan persistence bypass:** every durable update must use the publisher
  shipped by `concept-publication-transactions`.
- **Generated docs drift:** modify source help and run the documented generator.

## Testing matrix

- Included concept with zero, one, and multiple committed/done owners.
- Deferred and `wont_do` concepts with valid, missing, unsigned, dangling, stale,
  and contradictory structured records.
- Multiple simultaneous missing concepts and stable recommendation IDs.
- Split with partitioned/shared ownership, missing ID, invented ID, ambiguous
  deferral mapping, dry-run, and rejected proposal.
- Merge with ordered deduplicated ownership and deferral-link remapping.
- Re-ground mark-done and re-baseline envelopes for done, remaining, and parked
  steps without ownership union.
- Scope-out with surviving external owner, sole owner, multiple carved owners,
  blocked/declined/dry-run, legacy no-sidecar, stale/malformed record, publication
  failure, and rollback.
- Forward/re-baseline seed create with exact restoration, unknown/invented/dropped
  IDs, stale source fingerprint, ambiguous mapping, legacy seed, interactive
  resolution, and unattended unresolved state.
- Generated CLI reference drift and backlog/doc claims against actual symbols.

## Acceptance criteria

- Every reviewed concept after every supported lifecycle operation has at least
  one exact committed/done owner or one valid structured non-delivery record.
- `wont_do` does not satisfy completeness merely because it is the node decision.
- Unsigned proposals and heuristic matches never satisfy blocking accounting.
- Split and merge conserve both exact concept IDs and valid deferral links; no
  link points at a removed or wrong step afterward.
- Re-ground and scope-out seeds carry machine-readable exact accounting metadata,
  and create restores or explicitly reviews it without title inference.
- Unknown, dropped, invented, stale, contradictory, and ambiguous restoration
  input fails or remains explicitly unsigned; it is never silently accepted.
- Scope-out's prepared accounting transformation is validated and published only
  through the prerequisite transaction API.
- Documentation changes originate in parser/help sources and generated artifacts
  pass drift checks.
- Focused lifecycle tests, the full suite, completeness audits, and
  `reconcile-code` pass without accounting or generated-doc redirects.

## Deferred

- Publication and rollback mechanics are owned by
  `concept-publication-transactions`.
- Model-output and detail replacement hardening are owned by
  `concept-authoring-boundary-hardening`.
- Automatic covering-step generation and concept-decision telemetry remain
  separate future work.

