> **Replaced**: this file has been superseded by `docs/implementation-plans/2-retire-roadmap-v1-evidence.md`.
> Preserved here for history; do not edit.

# Plan seed: retire the version-1 roadmap evidence path

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/retire-roadmap-v1-evidence.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below
and proposes a step decomposition; the author then runs `plan-tool detail`
per step.

> **Known-consumer transition evidence:** Integration — the only known real consumer
> of the roadmap escalation-receipt/impact-analysis evidence system — has
> migrated onto version 2 (confirmed 2026-08-23; see
> `<integration-consumer-root>/.tmp/roadmap-v2-evidence-onboarding.md`
> for how that was verified). No other consumer of this evidence is known. The
> release plan must still inventory every known deployment and live evidence
> location before removal; an undisclosed version-1 consumer or record blocks
> retirement until it has followed the transition below. This later user
> decision supersedes the Round-7 handoff's 2026-08-23 "v1 stays" guidance,
> which reflected Integration's earlier state.

## Outcome

Every receipt, impact-analysis, and structural-evidence reader in
`plan_tool/roadmap_*.py` supports exactly one evidence schema (today's
version 2) instead of dispatching between two, so the codebase carries one
freshness rule instead of two and stops paying the maintenance cost of a
path nothing exercises.

## Overview

**Provenance (2026-08-23).** `roadmap-canonical-source-identity` introduced a
versioned evidence contract: version 1 uses exact-raw-byte freshness and
version 2 uses writer-owned baseline-identity freshness while tolerating
presentation-only drift. Its seven-round `/code-review` hardening pass found
the scattered version-dispatch logic was the direct cause of three confirmed
regressions (a wrong-version rule on a v2 snapshot, an
admission/consumption mismatch between independently-coded currentness
predicates, and a fail-closed gap on an unsupported version). `BACKLOG.md`
#307 records that evidence, consolidates the one identical predicate, and
leaves four architecturally different sites unmerged. Version 1 had no real
second consumer beyond Integration, which has now migrated. Removing the alternate
path removes the generative cause of that regression class, not just its
symptoms.

## In scope

- `plan_tool/roadmap_source_identity.py` — the version-dispatch primitives
  (`EVIDENCE_SCHEMA_VERSIONS`, `is_supported_evidence_schema_version`,
  `admitted_source_is_current`, `admit_baseline_backed_source`) and every
  place they or their siblings branch on which version is being handled.
- Its version-dispatching consumers: `roadmap_escalation.py`,
  `roadmap_escalation_run.py`, `roadmap_escalation_selection.py`,
  `roadmap_impact_analysis.py`, `roadmap_impact_run.py`,
  `roadmap_impact_snapshot.py`, `roadmap_structural_revision.py`,
  `roadmap_structural_revision_run.py`, `roadmap_structural_operations.py`.
- The roadmap CLI surface (`plan_tool/cli/roadmap_cmd.py`) only insofar as
  it renders or gates on version-specific behavior.
- The published reader-only evidence contract: `ROADMAP_FORMAT.md`,
  `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md` (the originating plan's
  step-4 contract and architecture references currently document both
  versions side by side).
- Every test file mirroring a touched module.

## Architecture

- **Load-bearing decision: the `schema_version` field stays; only its
  second legal value goes away.** Integration already has real, persisted version-2
  evidence on disk carrying an explicit `"schema_version": 2` field. Dropping
  the *field* (not just the alternate value) would break an already-shipped,
  already-in-use wire format. What this plan removes is the *branch* — every
  `if schema_version == 1` / `!= 1` test and every version-1-only code path
  — not the discriminator itself. `is_supported_evidence_schema_version` (or
  its successor) keeps its name and call sites; its body collapses from a
  two-value set-membership test to a single legal-value check, so every call
  site keeps naming its intent instead of being inlined to a bare `== 2`.
- **Upgrade existing projects before retiring their reader.** Version 1 and
  version 2 bind different trust facts, so immutable version-1 finals never
  convert in place or acquire a baseline identity by inference. A project with
  live version-1 route evidence upgrades by establishing its writer-owned
  version-2 baseline, reissuing a fresh version-2 receipt from still-eligible
  current feedback, and regenerating its derived version-2 analysis. A project
  whose version-1 evidence cannot safely be reissued archives that evidence as
  history and remains on a version-1-capable release; it blocks this removal.
  The release gate inventories every known project and live evidence namespace,
  records the chosen reissue or archival result, and refuses retirement while
  any live version-1 record remains. This is an operator-visible transition,
  not a best-effort automatic conversion.
- **Two dispatch idioms exist today and both must be found.** Most sites
  write an explicit `schema_version == 1` (or `!= 1`) branch. At least one
  (`_preflight_is_canonical`, `roadmap_structural_revision_run.py:446`)
  instead checks only `evidence_version == 2` and falls through to
  version-1 logic for anything else — a grep for literal `== 1` alone will
  miss this shape. Enumerate both idioms explicitly during `detail` before
  removing anything (this repo's own "fix the class, not the cited spot"
  convention, applied to a removal instead of a fix).
- **`BACKLOG.md` #307's `admitted_source_is_current` loses its version-1
  branch, not its existence.** It stays the one shared "is this admitted
  source current" gate; it now has exactly one branch instead of two.
  Do not reopen #307's four do-not-merge findings — those were about
  genuinely different operations (admission vs. comparison vs.
  self-consistency vs. full-byte-render equality), and removing version 1
  changes none of that reasoning.
- **No new CLI syntax or version-2 creation behavior changes.** New
  receipt/analysis creation has defaulted to version 2 since the originating
  plan shipped (`NEW_RECEIPT_SCHEMA_VERSION = 2`, never overridden by the
  CLI). Inspection of an unarchived version-1 final will change visibly after
  retirement: it must return a defined fail-closed invalid/unavailable result
  with no route, never crash, silently upgrade, or label the record current.
  The implementation selects and documents that exact result, and tests it at
  every affected reader surface.

## Out of scope

- Any change to version-2 semantics, admission rules, or the
  baseline/canonical-identity contract itself. This plan deletes an
  alternate path; it does not redesign the surviving one.
- Reopening or re-litigating `BACKLOG.md` #307's already-closed
  consolidation or its do-not-merge findings.
- `BACKLOG.md` #242 / the Integration "receipt preflight" gate — unrelated,
  already in progress on Integration's side, not touched by this removal.
- A generic in-place version-1-to-version-2 evidence converter. It would have
  to infer a writer-owned baseline identity that version-1 evidence never
  carried, violating the transition's trust boundary. The scoped reissue or
  archival gate above is the upgrade path.

## Risks

- **A removed branch may be doing more than picking a comparison rule.**
  Some version-1 branches also perform validation or field population that
  the version-2 branch doesn't duplicate. Deleting the `if` without checking
  what else the branch does can silently drop that behavior for the one
  path that survives. Check each removed branch's full body against the
  version-2 branch before deleting, not just its comparison expression.
- **Half-fixing the implicit-fallthrough idiom re-creates a known
  regression.** Removing a version-1 fallthrough without also making the
  replacement fail closed on an unsupported value repeats the exact gap this
  repo's own review already found once at `_preflight_is_canonical`
  (round 7 of the hardening pass cited above). Every site converted from
  "checks == 2, else assumes v1" must explicitly reject anything that isn't
  2, with a test proving it.
- **Doc vocabulary sweep, not just identifier sweep.** `ROADMAP_FORMAT.md`
  and `DATA_CONTRACT.md` currently present both versions side by side as
  the shipped contract. Cutting the version-1 half must also remove
  version-1 *vocabulary* from surrounding prose (comparisons, "version-1
  vs. version-2" framing, cross-references to the removed section) — an
  identifier-only sweep leaves prose still arguing for the thing that was
  removed (this repo's own "documentation is forward-looking" convention).

## Testing

- Every mirrored test file for a touched module stays green with its
  version-1-only tests deleted (not skipped, not `xfail`) and any
  version-1-dependent fixture defaults updated to the sole remaining
  version.
- Every site converted from the implicit-fallthrough idiom gets a test
  asserting fail-closed behavior on a value other than 2 (see Risks).
- `tests/test_roadmap_format.py`'s identity-bound example-parsing tests
  keep passing with only the version-2 reference example remaining.
- Transition fixtures cover a version-1 record that reissues safely as
  version 2, an un-reissuable record that blocks release pending archival, and
  a post-retirement reader that refuses unarchived version-1 evidence without
  a route or implicit conversion.
- Full suite green (`uv run pytest tests/ -q -n auto`) with no remaining
  roadmap-evidence-owned production module, matching test, or versioned
  roadmap contract reference that treats 1 as an evidence schema version.
  This sweep deliberately excludes unrelated format versions such as
  `SOURCE_IDENTITY_VERSION = 1` and unrelated persisted schemas.

## Acceptance criteria

- No production code path branches on `schema_version`/`evidence_version`
  taking any value other than 2; the shared validity check enforces exactly
  one legal value.
- `schema_version: 2` remains a persisted, parseable field on every
  evidence type — Integration's existing real evidence parses unchanged.
- Every known project and live evidence namespace has a recorded reissue or
  archival result; an un-reissuable live version-1 record blocks retirement.
- `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md` describe
  one evidence contract, with no residual version-1 vocabulary or
  cross-reference beyond dated migration/retirement provenance.
- Every reader fails closed on an unarchived legacy record with the documented
  no-route result; none crashes, silently upgrades it, or treats it as current.
- Full suite green; no test retains version 1 as a supported evidence path or
  an `xfail`/skip. The explicit legacy fixture remains only to prove the
  documented fail-closed refusal.

## Deferred

_(none)_
