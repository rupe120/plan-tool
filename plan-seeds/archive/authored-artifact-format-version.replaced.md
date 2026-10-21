> **Replaced**: this file has been superseded by `docs/implementation-plans/2-authored-artifact-format-version.md`.
> Preserved here for history; do not edit.

# Seed: authored-artifact format version

## Outcome

A plan file, a run-grade detail file, and a roadmap staged artifact each
declare their format version in-band, and each of the three readers refuses an
unsupported declared version with a named, actionable result instead of a
generic parse error.

An absent declaration reads as version 1, so every artifact already on disk
parses exactly as it does today.

## In scope

- The plan frontmatter declaration and its gate at `parser.py:parse_plan_text`,
  which already exposes the parsed `raw` mapping before `Plan.model_validate`.
- The roadmap staged-artifact declaration and its gate at the four staged
  parsers in `roadmap_artifacts.py` (`parse_domain_artifact`,
  `parse_constraints_artifact`, `parse_components_artifact`,
  `parse_plans_artifact`).
- The run-grade detail declaration, its body-marker carrier, and its reader.
- The writers that stamp each declaration, including `parser.py:write_plan`.
- `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, `ROADMAP_FORMAT.md`,
  `DATA_CONTRACT.md`, and the `data_contract.py` registry entry carrying the
  new version constants.
- Removing `BACKLOG.md` #356 when the work ships.

## Overview

Every record `plan-tool` persists declares a schema version: review sidecars
(`review_persistence.SCHEMA_VERSION`), telemetry, grounding, the project
profile, the purity cache, checkpoints, the run log, roadmap evidence, and the
roadmap version store each carry one. Every artifact
`plan-tool` authors carries none. This effort closes that asymmetry for the
three authored classes and stops there: it ships version 1 and the refusal,
and no second version of anything.

`DATA_CONTRACT.md` § "Version-evolution policy" already governs how a durable
version must behave — readers fail closed and never guess a version. Its
§ Scope excludes the authored-artifact formats, delegating them to
`PLAN_FORMAT.md` / `DETAIL_FORMAT.md`. This effort brings those three under
the same policy without moving ownership of their schemas.

## Problem statement

`Plan` sets `extra="forbid"` (`schema.py:208`), and `PLAN_FORMAT.md`
validation rule 8 rejects any unknown frontmatter key. A plan written by a
newer `plan-tool` is therefore a hard parse rejection by an older one,
surfaced as an unknown-field typo, with nothing in the artifact saying the
format moved. The rejection is correct and the diagnosis is wrong, and no
amount of care in a future format change can fix that from the newer side —
the older reader has to be able to recognize a version it does not support.

The two sibling classes have the same hole with different shapes: roadmap
staged artifacts carry a row inventory in frontmatter and no version, and a
detail file is pure markdown with no frontmatter at all (`DETAIL_FORMAT.md`
§ Format), so it has nowhere to put one today.

## Architecture

Five decisions are settled here; the mechanics belong to `detail`.

**The gate runs before strict validation.** A version read that happens inside
`Plan.model_validate` is inert: a newer plan's other new keys raise
unknown-field errors first and the version is never reached. The plan gate
reads the declaration from the already-parsed `raw` mapping in
`parse_plan_text` and refuses an unsupported value before validation runs.
The same ordering holds per class — recognize the version, then apply the
shape contract.

**Absent means version 1, by an explicit default at each gate.** The
mechanism is the default applied in the three gates; they own it; and the
reader gates land before any writer stamps a declaration, so no artifact ever
carries a version that no shipped reader understands. This is what keeps every
existing artifact parsing unchanged.

**The roadmap gate is per-caller, not inside `_parse_frontmatter`.**
`roadmap_artifacts.py:_parse_frontmatter` has five callers: the four staged
parsers and `parse_draft_seed_provenance`. A draft seed is a different
artifact class and is out of scope, so the gate attaches at the four staged
parsers — or `_parse_frontmatter` receives the supported set explicitly —
and `parse_draft_seed_provenance` is left unchanged.

**The detail carrier is a body marker, not frontmatter.** Giving detail files
YAML frontmatter would break `DETAIL_FORMAT.md`'s pure-markdown contract and
every body parser keyed on `detail.py:_REQUIRED_H2_TOKENS`. The precedent for
a machine-read marker inside a markdown body is
`roadmap_seed_state.py:render_seed_state_marker` and its parser at
`roadmap_seed_state.py:33-36`. The carrier's exact spelling and placement are
`detail`'s to fix.

**The plan declaration must survive `write_plan`'s elision.**
`parser.py:write_plan` serializes via
`model_dump(exclude_defaults=True, exclude_none=True)`, so an optional field
whose value equals its model default is never written — adding a field with a
default would silently produce plans that declare nothing. The written
declaration is a property of the writer, not a by-product of the model
default.

The supported set is a single value per class, `{1}`: this build produces it,
the three gates consume it, no other value is producible by this build, and
every other value is refused. There is no precedence question and no operator
state to exit.

## Scope guardrails

The check asserts exactly one binary observable: **the artifact's declared
format-version value is one this build supports.** Nothing else.

Not allowed, enumerated rather than implied:

- Checking whether an artifact's *content* conforms to the version it
  declares. The declaration is taken at its word; agreement between a declared
  version and the artifact's actual shape is not observable here and is not
  checked.
- Any quality judgment, prose-agreement check between two artifacts, or shape
  or length cap.
- Any new gate, exit-code flip, or refusal-to-advance beyond the parse
  refusal itself. A refused artifact fails where an unparseable artifact
  already fails today; no command grows a new failure mode.
- Emitting a warning, finding, or advisory about a *supported* version.
- Inferring, repairing, or upgrading a version the reader does not support.

## Out of scope

- Any version 2 of any artifact. This ships the version-1 declaration and the
  refusal; the first real format change is a separate effort under the
  version-evolution policy.
- A migration engine, a `plan-tool migrate` verb, or rewriting artifacts on
  read.
- Content revision, lineage, generation counters, or history. Retired #92
  holds that axis behind a re-open bar, `BACKLOG.md` #198 owns git-native plan
  provenance, and closed #328 already ships the roadmap content-version store.
- Declaring the detail *grade* in the artifact. A detail reader is handed its
  grade by its caller (`jira_grade.py:GRADE_DEFAULT`), which is a separate
  gap; this effort does not close it and must not widen the marker to carry
  it.
- Legacy jira-grade detail artifacts, whose creation is already disabled.
- Versioning `BACKLOG.md` / `BUG_BACKLOG.md`, `plan-seeds/`, roadmap draft
  seeds, or jira story exports.
- Changing any existing version constant, `audit_input_revision`'s `version`,
  or `PURITY_VERDICT_LOGIC_VERSION`; relaxing `extra="forbid"`; and giving
  detail files YAML frontmatter.

## Allowed behavior changes

- Newly written plan, detail, and roadmap staged artifacts carry a version
  declaration. An existing artifact gains one the next time its writer
  rewrites it.
- A reader given an unsupported declared version fails with a message naming
  the artifact's declared version and the version this build supports.
- No other user- or operator-visible delta. An artifact with no declaration
  parses to the same result as today.

## Allowed reorganization

None. Each gate attaches at the parse seam that already exists for its class.
Do not unify the three parsers, do not move the detail body readers onto a
frontmatter path, and do not fold the roadmap gate into the shared
`_parse_frontmatter` that draft seeds also use.

## Risks

- A gate placed after strict validation is inert and reads as shipped. The
  plan class is the one that proves this, because `extra="forbid"` makes the
  failure mode concrete.
- A field added with a model default is elided by `write_plan` and produces
  plans that declare nothing, while every test that constructs a `Plan`
  in-process still passes.
- The refusal is the one new failure path; wording it without the declared and
  supported values leaves an operator with the same undiagnosable state the
  effort exists to remove.
- Widening the detail marker into a general metadata block reopens the
  frontmatter question the pure-markdown contract settled.

## Testing

Per class, prove three states: an artifact with no declaration reads as
version 1 and parses identically to today; an artifact declaring version 1
parses identically; an artifact declaring an unsupported value is refused with
the named result. Pin each by mutation — break the gate and watch the
assertion go red — rather than by reading, per CLAUDE.md § Tests.

Prove the two traps directly, since both stay green under a naive suite: a
plan carrying an unknown key *and* an unsupported version is refused for the
version, not the key; and a plan round-tripped through `write_plan` comes back
carrying its declaration.

Stage-separated replay. The bare-plan audit owns the carrier decision for
detail and the per-caller placement of the roadmap gate — both are plan-level
contracts, and neither may be deferred to detail. The detail-grounded audit
owns the gate-before-validation ordering and the `write_plan` elision
mechanism. A bare-stage finding that proposes checking content against a
declared version is out of scope by the guardrails, not a gap to close.

## Acceptance criteria

- Each of the three classes declares its format version in-band, and each
  reader refuses an unsupported declared value with a message naming both the
  declared and the supported version.
- An artifact with no declaration parses to the same result as before this
  effort, for all three classes.
- The plan gate refuses an unsupported version before `Plan.model_validate`
  runs, demonstrated on a plan that also carries an unknown key.
- A plan written by `write_plan` carries its declaration.
- `parse_draft_seed_provenance` is unchanged and draft seeds gain no
  declaration.
- No new gate, exit code, or advisory exists beyond the parse refusal.
- `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, `ROADMAP_FORMAT.md`, and
  `DATA_CONTRACT.md` describe the declaration and the refusal, and the
  `tests/test_data_contract.py` drift guard covers the new constants.
- `BACKLOG.md` #356 is removed when the work ships; a deferred follow-up is
  left in the backlog rather than carried in this plan.

## Deferred

Out-of-scope discoveries are filed in `BACKLOG.md` or `BUG_BACKLOG.md` per
that file's decision rule, never applied as plan expansion. Named candidates:
declaring the detail grade in the artifact; a version declaration for draft
seeds, plan seeds, or jira exports; and any migration path, which belongs to
the effort that first needs version 2.

If the detail carrier turns out to require a body-schema change rather than a
marker, stop and file that decision instead of widening this effort — a
detail-format change is a second Outcome.

## References

- `BACKLOG.md` #356 — the source entry whose scope contract this seed
  inherits, and which this effort removes on shipping.
- `DATA_CONTRACT.md` § "Version-evolution policy" — the fail-closed reader
  rule this effort extends to the authored-artifact layer, and § Scope, which
  currently excludes it.
- `PLAN_FORMAT.md` § "Validation rules" — rule 8, the unknown-field rejection
  that makes a newer plan undiagnosable to an older reader.
- `DETAIL_FORMAT.md` § Format — the pure-markdown, no-frontmatter contract the
  detail carrier must respect.
- `ROADMAP_FORMAT.md` — the staged-artifact frontmatter contract, and closed
  #328's content-version store that this effort is orthogonal to.
- `plan_tool/parser.py:parse_plan_text`, `plan_tool/parser.py:write_plan`,
  `plan_tool/schema.py:208`, `plan_tool/roadmap_artifacts.py:_parse_frontmatter`,
  `plan_tool/roadmap_seed_state.py:render_seed_state_marker`,
  `plan_tool/detail.py:_REQUIRED_H2_TOKENS`, `plan_tool/data_contract.py` —
  the seams verified at HEAD.
