> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-seed-materialization.md`.
> Preserved here for history; do not edit.

## Overview

Stage 4 roadmap plan derivation will keep the canonical roadmap manifest and each roadmap-derived draft plan seed independently materialized, validated, and traceable, so a roadmap revision no longer needs to carry or re-emit every seed body in `draft_seed_bundle`. A dedicated draft-seed materialization flow generates and validates one plan seed at a time — against its plan row, upstream roadmap context, and the current repository — making independent backend calls and recording per-seed progress, input/output identity, gate results, and failure state. The stage-4 manifest contract maps every roadmap plan row to its expected draft-seed path and a content identity, so a roadmap is seed-ready only when every manifest entry has a matching valid draft; `roadmap --apply` promotes only a complete, verified set of drafts that matches the accepted roadmap, and its preflight plus the roadmap views report manifest completeness and stale/missing/mismatched seed state.

## Problem statement

Today's stage-4 write couples `04-roadmap.md` to an all-or-nothing `seeds/` tree: producing any file requires one backend call to generate every plan's seed body via `draft_seed_bundle` before any file lands, and a canonical roadmap revision must carry or re-emit every seed body to stay consistent. This makes partial materialization impossible to represent, forces regeneration or embedding of unaffected valid drafts on every revision, and gives `roadmap --apply` no way to distinguish a missing, stale, or mismatched draft from a promotable one without re-deriving everything from the bundle.

## Architecture

Stage 4 has two distinct responsibilities and represents them separately: the canonical roadmap decides *which* implementation plans exist and their ordering, while draft-seed materialization supplies the independently reviewable `create --from-existing` input for each plan. The manifest is their durable join, using stable plan IDs and content identity rather than positional list order or a bundle copied into YAML. It extends the roadmap directory's existing `seed-state.json` lifecycle sidecar (already tracking each plan id's `draft_seed_path`, status, digest, and promotion state) rather than introducing a parallel store — the sidecar's fields are the join's foundation, not a new concept to invent.

One seed materialization job owns one draft path. It can retry or resume without asking a backend to reconstruct siblings, and it cannot modify the canonical plan rows. The promotion path reads the manifest plus draft state and refuses any incomplete or mismatched set before copying anything into `plan-seeds/`. State updates and file writes use a publish boundary that never presents a valid-looking manifest pointing at a half-written draft.

This effort composes with `roadmap-incremental-revision.md`: a targeted canonical revision determines which plan IDs become stale, and this effort materializes only those IDs once the revision is accepted. It does not assume that a user has accepted a draft simply because the system can generate one.

Consequently, stage 4 may publish roadmap plan metadata before all draft seed bodies exist, clearly reporting that the roadmap is not seed-ready until materialization completes; draft seed generation becomes individually resumable and may update one selected stale or missing draft without rewriting unrelated drafts; and promotion refuses partial, stale, or identity-mismatched draft sets instead of relying on a single embedded bundle as proof of completeness.

## Out of scope

- Changing how `create`, `detail`, Jira story generation, implementation, or plan/code reconciliation consume a promoted seed.
- Auto-promoting drafts, auto-accepting roadmap feedback, or treating draft materialization as user approval.
- Redesigning the plan-seed prose format, adding a second seed store beyond the existing `seed-state.json` sidecar, or introducing a remote database/object store for seed state.
- Regenerating every seed on a roadmap revision, deleting a stale seed to hide it, or writing a replacement without the explicit materialization/refresh action.
- General background scheduling, parallelism policy, or backend liveness instrumentation beyond the batch-observability work already under separate validation.
- A correctness gate on seed style, length, or model agreement — the binary observable is whether each manifest plan ID has exactly one valid draft with the recorded identity, and whether promotion refuses every other state.
- Reorganizing unrelated roadmap stages, `create`, or the generic plan-seed format — only the extraction necessary to separate stage-4 manifest handling from draft-seed materialization, while retaining one shared path-validation and promotion-preflight authority, is in scope.
- Folding targeted feedback revision, model-call observability, parallel job execution, seed approval workflow, or a new artifact storage system into this plan; route out-of-scope discoveries to `BACKLOG.md` or `BUG_BACKLOG.md`.

## Risks

- Migrating existing accepted roadmaps' `draft_seed_bundle` content onto the new manifest/materialization model could silently lose seed content if a content-identity or migration decision cannot preserve existing accepted drafts. Mitigation: stop and surface the compatibility decision before changing the on-disk contract, rather than proceeding with a lossy migration.

## Acceptance criteria

- A roadmap with several plans materializes, fails, resumes, and refreshes one draft at a time; each attempt leaves non-targeted draft files unchanged.
- Missing, stale, malformed, path-escaping, duplicate, and digest-mismatched drafts are visible in views and block promotion before any destination write.
- A complete matching set promotes exactly the manifest's drafts; a failure or interruption during materialization never leaves a manifest claiming a nonexistent or partial file is valid.
- Existing roadmaps with `draft_seed_bundle` migrate deterministically, retain their seed content and lifecycle meaning, and pass artifact/gate checks.
- Feedback invalidation and explicit refresh retain their current safety rule: derived prose changes only under the explicit writer, never as a side effect of a canonical roadmap revision.

## Input

This plan reads and extends the roadmap directory's existing `seed-state.json` lifecycle sidecar, which already tracks each plan id's `draft_seed_path`, status, digest, and promotion state — these fields are the manifest/draft join's foundation, not a new concept to invent. It also consumes the existing explicit `--refresh-seeds` safety model and its before/after reports; the plan decides whether refresh becomes the per-seed materializer's public surface or delegates to it, but retains the rule that feedback never silently overwrites a derived seed. It composes with `roadmap-incremental-revision.md`, consuming which plan IDs a targeted canonical revision marks stale so this effort materializes only those IDs once the revision is accepted.
