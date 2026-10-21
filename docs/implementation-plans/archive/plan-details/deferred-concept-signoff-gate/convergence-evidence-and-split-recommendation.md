# Deferred Concept Signoff Gate — Convergence Evidence and Split Recommendation

## Decision

Do not execute `deferred-concept-signoff-gate` as a single implementation plan. Replace it with two narrower plans:

1. `concept-decision-record-core` — stable identity, persistence, deterministic bootstrap/re-derivation, three-state navigation, approval semantics, atomic record-to-plan synchronization, and `scope-review`.
2. `concept-signoff-integrations` — explicit concept-to-step ownership, `create` and `detail` producers, completeness enforcement, and structural-remedy integration, consuming the shipped core contract.

The split is structural, not scheduling-only. The original plan repeatedly assigned the same invariants to different steps and surfaces, so gap-by-gap edits moved contradictions instead of eliminating them.

## Supporting audit evidence

All model-backed runs used the Codex backend through `PLAN_TOOL_BACKEND=codex`.

### Saved audit history before remediation

- `reports/20260712-000810-completeness.md`: 4 conceptual-correctness findings and 2 conceptual-completeness findings.
- `reports/20260712-003155-completeness.md`: 3 conceptual-correctness findings and 4 conceptual-completeness findings.

The finding mix changed and expanded rather than monotonically approaching zero. Important recurring themes included missing three-state navigation, unreliable title-based coverage, stale-tree behavior, uncovered structural-remedy ownership, and inconsistent `covered_by` semantics.

### Fresh three-pass readiness audit

Command shape:

```sh
PLAN_TOOL_BACKEND=codex .venv/bin/plan-tool completeness-audit \
  deferred-concept-signoff-gate \
  --no-iterate --no-reuse-audit \
  --audit-passes 3 --audit-dry-rounds 1 --json
```

Result:

- 13 unique conceptual findings.
- 9 correctness findings, including 7 high severity.
- 4 completeness findings, including 3 high severity.
- New findings were still discovered at the pass cap: `7 → 4 → 2`.
- `has_blocking_findings` was true and coverage was unconfirmed.

### Four-pass baseline used for manual remediation

Saved report: `reports/20260713-005856-completeness.md`.

Result:

- 15 unique conceptual findings.
- The pass sequence still discovered new findings: `7 → 5 → 2 → 1`.
- Coverage was unconfirmed at the four-pass cap.

The saved findings were walked with `completeness-apply`. Fourteen conceptual findings produced plan edits and one overlapping finding was already satisfied. The edits attempted to centralize three-state navigation, approval invalidation, review depth, deterministic candidate collection, stale-tree handling, structural-replacement ownership, and atomic scope-out behavior.

### Five-pass post-remediation audit

Saved report: `reports/20260713-014211-completeness.md`.

Result:

- 16 unique conceptual findings after the remediation cycle.
- 11 correctness findings.
- 5 completeness findings.
- New findings per pass: `5 → 3 → 4 → 3 → 1`.
- Coverage remained unconfirmed at the five-pass cap.

The count and discovery pattern demonstrate non-convergence. The second cycle did not merely rephrase the first audit: it surfaced new contradictions in identity, approval preservation, explicit versus heuristic coverage, tree/prose synchronization, post-authoring include decisions, invalid-sidecar behavior, and ownership of structural-remedy transformations.

## Recurring architectural conflicts

### Identity versus hierarchy refresh

The original design derived node identity from title plus parent path while promising that re-derivation could enrich hierarchy and preserve existing decisions. Re-parenting necessarily changed the id; duplicate sibling titles could collide. Stable approval and ownership therefore could not be guaranteed across refresh.

The replacement core uses opaque stable ids retained across hierarchy changes. Deterministic source keys support matching but are not primary identity.

### Source of truth without a single writer

The plan declared `concepts.json` the source of truth and required `## Deferred` / `## Out of scope` to render from it, but `detail` and `scope-review` could change the record without re-rendering the plan. This reopened the explicitly named two-sources-of-truth risk.

The replacement core owns one atomic synchronization operation. Every decision-bearing write must update the record, rendered plan sections, mapped step scope, and fingerprint together or roll back.

### Guaranteed coverage versus heuristic matching

The plan promised that an included concept could never be silently dropped while defining coverage through title, feature, or detail-body slug matching. A heuristic can produce false positives and false negatives and cannot support a deterministic guarantee. Title edits and structural replacements also changed the match corpus.

The integration replacement persists stable concept ids on owning steps. Heuristics may suggest ownership but never count as coverage.

### Approval versus state transitions

Several surfaces changed state while preserving or clearing approval inconsistently. In particular, scope-out could turn an approved inclusion into an approved deferral, while unattended review could erase approval from unchanged decisions.

The replacement core defines a small transition table: changed decisions clear their own approval; unchanged decisions retain approval; unattended runs never create approval. The integration plan requires scope-out to invalidate approval when it changes include to defer.

### Post-authoring decisions versus completed artifacts

The original `detail` flow reviewed candidate deferrals after authoring. If an operator changed a candidate to include, the already-written detail still contained deferred prose. Accepting malformed candidate output could also leave prose outside the machine record.

The integration replacement requires structured candidate/prose parity and regeneration of affected details when a post-authoring candidate becomes included.

### Structural remedies without an ownership contract

The original plan claimed coverage survived split, merge, and re-ground, but no step owned the explicit transformation and existing split proposals did not carry the required feature ownership.

The integration replacement makes ownership transformation explicit: split partitions concept ids, merge unions them, re-ground preserves them, and scope-out removes carved ownership and defers only concepts without a surviving owner.

## Split boundaries

### Plan 1: Concept Decision Record Core

Owns:

- Stable persisted node identity independent of title and hierarchy.
- Missing, invalid, current, and stale read outcomes.
- Deterministic bootstrap and conflict-aware re-derivation.
- Independent `include` / `defer` / `wont_do` state.
- Three-state navigation and review-depth enforcement.
- Per-node approval invalidation and unattended approval preservation.
- Atomic record-to-plan synchronization.
- Standalone `scope-review` and its CLI/doc surfaces.

Excludes:

- `create` and `detail` model producers.
- Delivery coverage.
- Split, merge, re-ground, and scope-out integration.

Seed: `plan-seeds/concept-decision-record-core.md` at authoring time. `create --from-existing` may archive it under `plan-seeds/archive/` after successful plan creation.

### Plan 2: Concept Signoff Integrations

Consumes the shipped core and owns:

- Explicit stable concept ids on implementation steps.
- Evidence-only producer enrichment.
- Pre-finalization `create` decisions and ownership.
- Pre-authoring detail scope and post-authoring structured candidates.
- Regeneration when a post-authoring candidate changes to include.
- Blocking explicit-link coverage and advisory-only heuristic suggestions.
- Split partition, merge union, re-ground preservation, and scope-out deferral/approval invalidation.
- Final documentation and backlog reconciliation.

Seed: `plan-seeds/concept-signoff-integrations.md` at authoring time. `create --from-existing` may archive it under `plan-seeds/archive/` after successful plan creation.

## Readiness criteria for the replacement plans

Each replacement plan should be audited independently. It is ready to run only when:

- A fresh multi-pass completeness audit reaches a confirming dry pass before the cap.
- No conceptual-correctness findings remain.
- No high-impact conceptual-completeness findings remain.
- Any deterministic diagnostics for files intentionally created by later steps are reviewed as plan-order artifacts rather than mistaken for existing-code drift.
- `plan-tool validate <slug>` and `git diff --check` pass.

The integration plan should not execute before the core plan has shipped and its named public contracts exist at HEAD.
