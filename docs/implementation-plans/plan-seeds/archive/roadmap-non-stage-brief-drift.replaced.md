> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-non-stage-brief-drift.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap non-stage brief-drift policy

## Outcome

Every non-stage Roadmap route that reads a recorded concept brief will apply an
explicit, route-appropriate policy when its current decoded text differs from
the digest accepted in `source.json`, or when that digest is absent on a legacy
record. Each route will preserve its existing authority boundary and expose a
redacted result that tells an operator whether its work proceeded, refused, or
produced stale evidence.

## Overview

This slice gives structural rewrite, impact analysis, and root-version
enrollment a deliberately selected source-drift policy. It preserves the
delivered stage-run admission boundary while ensuring each non-stage route
states what the accepted concept-brief baseline means to its own persisted
claims. It changes no AI-DLC, Integration, multi-source, or source-rebinding contract.

## Problem statement

Stage runs now admit their source before artifact work, but structural rewrite,
impact analysis, and root-version enrollment capture the current brief through
`capture_roadmap_impact_snapshot` without comparing its digest with the
accepted digest in the recorded source. A route can therefore bind or publish
current brief facts without declaring whether those facts are authority for the
route. Reusing the stage-run admission event or its same-path rebind would
silently give evidence and enrollment writers authority they do not own.

## Architecture

The plan will select, document, and test one explicit result for each row. A
route may refuse, report non-publishable stale evidence, or establish that its
authority is independent of brief admission only when its existing persisted
contract proves that outcome safe.

| Route | Existing responsibility | Decision required | Must not gain |
| --- | --- | --- | --- |
| Structural rewrite (`--rewrite-structural` with `--rewrite-analysis`) | Publishes one selected feedback rewrite from an exact receipt-analysis pair. | Whether changed or legacy current brief facts invalidate the structural preflight, become stale evidence, or do not affect structural authority. | Permission to treat source identity as publication permission, stage lifecycle events, or same-path rebind. |
| Impact analysis (`--impact-analysis`) | Publishes bounded, immutable analysis evidence from a receipt and a coherent snapshot. | Whether analysis generated from changed or legacy brief facts is invalid, stale/non-publishable, or independent of the accepted source baseline. | Stage-run admission telemetry, artifact-write authority, or a baseline rebind. |
| Root-version enrollment (`--enroll-version`) | Captures existing live authority into immutable version storage once. | Whether the recorded brief baseline is required before capture and which redacted result records refusal or independent operation. | Authority to accept or replace the baseline while enrolling. |

### Scope

- The three named routes, their snapshot capture and recheck ordering, and
  narrow shared digest-comparison helpers where the selected policies prove a
  common read contract.
- Explicit current, changed, and legacy-record behavior per route, before any
  route reads unadmitted brief facts into a persisted writer result.
- Route-specific persisted evidence or result vocabulary, redaction, CLI or
  operator documentation, and focused unit and CLI tests.
- A compatible read/write transition for existing `source.json` records,
  including an unambiguous legacy outcome.

## Out of scope

- A generic source-admission framework, multi-source or role-tagged intake,
  source manifests, and any AI-DLC names, paths, artifact kinds, or runtime
  stage names.
- Stage-run source-admission lifecycle events, same-path rebind on a non-stage
  route, or the changed-stage-run operator-intent decision owned by BACKLOG
  #366.
- Any Integration source, connector, application, workflow, corpus, or AI-DLC process
  change.
- Semantic re-grounding of roadmap artifacts, new prompts or stages, broader
  rewrite authority, and changes to current deterministic gates.

### Contracts and constraints

- `brief_digest` remains the SHA-256 digest of decoded UTF-8 text; it is not
  interchangeable with the raw `source.json` digest or immutable stored-brief
  byte digest.
- A present source record without `brief_digest` remains a legacy, unknown
  baseline. A malformed recorded digest continues to fail as malformed data,
  never as a match.
- Every selected policy captures then rechecks the same source state across its
  writer window. A comparison must occur before a route makes a persisted claim
  that depends on the current brief.
- Result records disclose no brief text, absolute paths, receipt bodies, or
  other sensitive evidence beyond the route's existing redacted contract.
- Hand-written-brief Roadmap projects retain their current behavior unless the
  selected route policy supplies a compatible transition and pins it with tests.

## Risks

- **Authority leakage:** a shared helper can make a non-stage writer appear to
  own stage admission or source acceptance. Each route retains an explicit
  result contract and tests that no rebind or stage event occurs.
- **Stale publication:** comparing only the current snapshot can persist claims
  derived from an unaccepted brief. Each policy checks the accepted digest
  before its route writes ordinary output and rechecks the capture window.
- **Compatibility break:** treating an absent legacy digest as a match hides
  uncertainty, while treating it as malformed destroys the migration state.
  Tests pin a distinct legacy result.
- **Disclosure:** a diagnostic could expose a brief, absolute path, or evidence
  body. Route results retain only their existing redacted identity fields.

## Testing

Add focused current, changed, legacy, malformed, and unchanged-source tests at
the snapshot helper and each route owner. Extend
`tests/test_roadmap_impact_snapshot.py`, `tests/test_roadmap_impact_run.py`,
`tests/test_roadmap_structural_revision.py`, `tests/test_roadmap.py`, and
`tests/cli/test_roadmap_cmd.py` where the selected contracts require them.
Tests will prove preflight order, final recheck, no ordinary publication on a
refusal or stale result, redaction, and the absence of source-baseline
acceptance outside a stage run. Run the affected Roadmap suites and the full
pytest suite before the slice closes.

## Acceptance criteria

- Each route has a documented, tested current, changed, and legacy behavior;
  the plan states why its selected policy follows that route's authority.
- Structural rewrite, impact analysis, and enrollment cannot publish a claim
  derived from a changed or legacy brief unless the selected policy explicitly
  establishes that source admission is irrelevant to that claim.
- No route emits `roadmap_source_admission`, performs same-path rebinding, or
  changes stage-run lifecycle semantics.
- Every refusal or stale result is terminal, route-specific, redacted, and
  occurs before the route writes its ordinary output.
- The tests prove capture/recheck ordering, no-publication on refusal or stale
  evidence, legacy compatibility, changed-text detection, unchanged behavior,
  and the absence of new baseline-acceptance authority.
- Documentation, route results, helpers, and tests use the same policy
  vocabulary; identifier and vocabulary sweeps cover all three routes.

## Deferred

Stop and create a focused backlog entry if the selected policy needs an AI-DLC
runtime concept, a source without committed approval-bound identity, a
multi-source carrier, a generic confirmation mechanism, or a broader
compatibility schema. If a route demonstrably does not depend on source
admission, record and test that result rather than forcing a refusal.

## References

- `BACKLOG.md` #365 — authoritative scope contract and priority.
- `handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md` — delivery order
  and Plan-tool/Integration scope fence.
- `plan_tool/roadmap_impact_snapshot.py` — recorded-source capture and
  snapshot recheck seam.
- `plan_tool/roadmap_structural_revision.py`, `plan_tool/roadmap_impact_run.py`,
  and `plan_tool/roadmap.py:enroll_roadmap_root` — the three route owners.
- `ROADMAP_FORMAT.md` and `DATA_CONTRACT.md` — source identity and existing
  redacted event/result contracts.
