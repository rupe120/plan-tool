> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-seed-materialization.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap Seed Materialization

## Outcome

Stage 4 roadmap plan derivation will keep the canonical roadmap manifest and
each roadmap-derived draft plan seed independently materialized, validated, and
traceable. A roadmap revision will no longer need to carry or re-emit every
seed body in `draft_seed_bundle`, while `--apply` will promote only a complete,
verified set of drafts that matches the accepted roadmap.

## In scope

- A stage-4 manifest contract that maps every roadmap plan row to its expected
  draft-seed path and a content identity suitable for detecting a missing,
  stale, or mismatched draft without embedding every seed body in the roadmap
  artifact.
- A dedicated draft-seed materialization flow that generates and validates one
  plan seed at a time against its plan row, upstream roadmap context, and the
  current repository. It makes independent backend calls and records
  per-seed progress, input/output identity, gate results, and failure state.
- A deterministic completion rule: a roadmap is seed-ready only when every
  manifest entry has a matching valid draft. Partial materialization stays
  visible and resumable, but cannot be promoted.
- Safe handling of revisions and feedback: canonical roadmap changes mark
  affected drafts stale without overwriting them; explicit seed materialization
  or refresh is the only writer of a draft body. Unaffected valid drafts retain
  their identity and are not regenerated as collateral work.
- Replace the current stage-4 write — which couples `04-roadmap.md` to an
  all-or-nothing `seeds/` tree and forces one backend call to produce every
  plan's seed body via `draft_seed_bundle` before any file lands — with an
  atomic, migration-safe alternative that publishes one draft at a time.
  Existing accepted roadmaps and their drafts migrate without silent deletion
  or promotion.
- `roadmap --apply` preflight and the roadmap views so they explain manifest
  completeness, stale/missing/mismatched seed state, and the exact drafts that
  would be promoted. Apply remains opt-in and invokes no backend.
- Compatibility with the existing explicit `--refresh-seeds` safety model and
  its before/after reports. The plan decides whether refresh becomes the
  per-seed materializer's public surface or delegates to it, but retains the
  rule that feedback never silently overwrites a derived seed.

## Architecture

Stage 4 has two distinct responsibilities and will represent them separately:
the canonical roadmap decides *which* implementation plans exist and their
ordering; draft-seed materialization supplies the independently reviewable
`create --from-existing` input for each plan. The manifest is their durable
join. It uses stable plan IDs and content identity, not positional list order
or a bundle copied into YAML. It extends the roadmap directory's existing
`seed-state.json` lifecycle sidecar (already tracking each plan id's
`draft_seed_path`, status, digest, and promotion state) rather than
introducing a parallel store — the sidecar's fields are the join's
foundation, not a new concept to invent.

One seed materialization job owns one draft path. It can retry or resume
without asking a backend to reconstruct siblings, and it cannot modify the
canonical plan rows. The promotion path reads the manifest plus draft state and
refuses any incomplete or mismatched set before copying anything into
`plan-seeds/`. State updates and file writes use a publish boundary that never
presents a valid-looking manifest pointing at a half-written draft.

This effort composes with `roadmap-incremental-revision.md`: a targeted
canonical revision determines which plan IDs become stale; this effort
materializes only those IDs once the revision is accepted. It does not assume
that a user has accepted a draft simply because the system can generate one.

## Out of scope / Non-goals

- Changing how `create`, `detail`, Jira story generation, implementation, or
  plan/code reconciliation consume a promoted seed.
- Auto-promoting drafts, auto-accepting roadmap feedback, or treating draft
  materialization as user approval.
- Redesigning the plan-seed prose format, adding a second seed store beyond
  the existing `seed-state.json` sidecar, or introducing a remote
  database/object store for seed state.
- Regenerating every seed on a roadmap revision, deleting a stale seed to hide
  it, or writing a replacement without the explicit materialization/refresh
  action.
- General background scheduling, parallelism policy, or backend liveness
  instrumentation beyond the batch-observability work already under separate
  validation.
- A correctness gate on seed style, length, or model agreement. The binary
  observable is whether each manifest plan ID has exactly one valid draft with
  the recorded identity, and whether promotion refuses every other state.

## Allowed behavior changes

- Stage 4 may publish roadmap plan metadata before all draft seed bodies exist;
  it clearly reports that the roadmap is not seed-ready until materialization
  completes.
- Draft seed generation becomes individually resumable and may update one
  selected stale or missing draft without rewriting unrelated drafts.
- Promotion refuses partial, stale, or identity-mismatched draft sets instead
  of relying on a single embedded bundle as proof of completeness.

## Allowed reorganization

Only the extraction necessary to separate stage-4 manifest handling from
draft-seed materialization while retaining one shared path-validation and
promotion-preflight authority. Do not reorganize unrelated roadmap stages,
`create`, or the generic plan-seed format.

## Verification

- A roadmap with several plans materializes, fails, resumes, and refreshes one
  draft at a time; each attempt leaves non-targeted draft files unchanged.
- Missing, stale, malformed, path-escaping, duplicate, and digest-mismatched
  drafts are visible in views and block promotion before any destination write.
- A complete matching set promotes exactly the manifest's drafts; a failure or
  interruption during materialization never leaves a manifest claiming a
  nonexistent or partial file is valid.
- Existing roadmaps with `draft_seed_bundle` migrate deterministically, retain
  their seed content and lifecycle meaning, and pass artifact/gate checks.
- Feedback invalidation and explicit refresh retain their current safety rule:
  derived prose changes only under the explicit writer, never as a side effect
  of a canonical roadmap revision.

## Stop / defer

Put out-of-scope discoveries in `BACKLOG.md` or `BUG_BACKLOG.md`. Do not fold
targeted feedback revision, model-call observability, parallel job execution,
seed approval workflow, or a new artifact storage system into this plan. If a
content-identity or migration decision cannot preserve existing accepted drafts
without silent loss, stop and surface the compatibility decision before
changing the on-disk contract.
