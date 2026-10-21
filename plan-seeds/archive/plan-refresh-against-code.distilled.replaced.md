> **Replaced**: this file has been superseded by `docs/implementation-plans/2-plan-refresh-against-code.md`.
> Preserved here for history; do not edit.

## Overview

Give an existing registered plan a cheap, deterministic way to tell whether its grounding is **stale relative to the current code**, and to **re-ground** itself when it is — by reusing the existing fingerprint and reconcile machinery rather than minting a new engine. A refresh command recomputes the plan's code fingerprint, diffs it against a stored grounding fingerprint, and on no drift exits as a fast no-op with **no Claude call**; on drift it runs the existing reconcile engine scoped to the exact changed files, then re-stamps the fingerprint. The feature ships standalone and also exposes a reusable entry point the branch-awareness plan's branch-creation flow can call.

## Problem statement

A plan is drafted against the codebase at one moment, then sits through review / merges to `main` while other developers' work lands. By the time someone picks it up, its premises may have drifted — files it targets moved, symbols renamed, or another merge already implemented part of it. Today there is no first-class way to (a) know the plan needs a refresh without re-reading everything, or (b) refresh it short of a full manual reconcile. This is useful **independently** ("update the plan, I'm not starting work yet") and as the **hook** the branch-awareness plan names at branch-creation time.

## Architecture

plan-tool already has the exact primitives, built for "did the code drift since a saved audit", so this feature is mostly *wiring*, not new judgement:

- **`plan_tool/fingerprint.py:compute_code_fingerprint(plan, plan_path, repo_root)`** → a reproducible `{repo-relative-path: sha256}` **map** over the plan's in-scope code surface (exactly `scope_guard.compute_drift_watched_paths` — every `step.files`/`creates` entry, minus the plan markdown and per-step detail files). Built in sorted order, byte-for-byte stable across machines.
- **`plan_tool/review_persistence.py:compute_plan_fingerprint(plan_path)`** → a digest of the plan itself, plus a saved-record shape that already carries `plan_fingerprint` + `code_fingerprint` (the path→hash map) + `code_fingerprint_present`, used by `auto_reconcile.py` for reuse-staleness checks.
- **The reconcile engine** (`launcher.py:verify_plan` / `reconcile-plan`) already judges plan-vs-code, mutates the plan to match, and consumes these fingerprints for reuse.

The wiring:

1. **Persist a "grounding fingerprint" on the plan** whenever it is grounded — after `create`/`detail`, and after any reconcile/refresh: the `compute_code_fingerprint` map + the `compute_plan_fingerprint` digest, plus a timestamp.
2. **The drift check** recomputes the code fingerprint against the current tree and diffs it against the stored map — empty diff = fresh, non-empty diff = the exact set of changed files. Pure/deterministic, no Claude; reuse the map-diff already implied by `auto_reconcile`'s staleness logic.
3. **The refresh command/mode** — on empty diff, no-op + exit 0 ("still grounded", no Claude call); on non-empty, invoke the existing reconcile engine **scoped to the changed files**, mutate the plan, re-stamp the fingerprint.
4. **A reusable entry point** the branch-awareness branch-creation hook (and any future command) can call, separate from the CLI wrapper.

**Where the grounding fingerprint lives** (load-bearing). Persist it as a **tracked plan property** — plan frontmatter (e.g. `grounded_code_fingerprint` / `grounded_plan_fingerprint` / `grounded_at`) or the existing saved-audit sidecar under the plan-details `reports/` dir, whichever churns less. **Tracked is correct here**, the deliberate contrast with the branch-awareness plan: a branch binding is per-clone **session** state (which branch is *this checkout* on) → untracked/local; a grounding fingerprint is a **shared fact about the plan** (the code state it was last grounded against) → it should travel with the plan through PR/merge, diff in review, and be the same for everyone.

**Naming — rationalize the family.** The reconcile/refresh surface is already crowded and `create --reprocess` is mis-named (it means "fill `_(TODO)_` placeholders from an archived predecessor", nothing to do with code). Prefer expressing refresh as a **mode of the existing reconcile** (e.g. `reconcile-plan --refresh` / `--pre-start`) over a brand-new top-level verb; a thin sibling verb is acceptable only if it reads more clearly. Whatever the surface, it must **dedupe hard against `reconcile-plan`'s engine** — share the judgement/grounding code, never re-mint it. The difference from plain `reconcile-plan` is the **fingerprint gate** (skip when nothing drifted) and the **all-PENDING / pre-start framing** (the useful axis is "are the premises still valid", not "does code satisfy a done step"). Clarify `--reprocess` in help text (or rename) in the same pass so users can tell the four apart.

## Out of scope

- **No new judgement engine** — reuse `reconcile-plan`/`fingerprint.py`; this is wiring + a gate + framing, not a new plan-vs-code brain.
- **No branch-awareness coupling baked in** — this ships standalone; the branch-creation hook is the *branch-awareness* plan's job to call this, not this plan's job to know about branches.
- **No manifest-as-derived-index work** — rebuilding `plans.json` from on-disk plan files + a union-merge driver is a separate registry-consistency concern, tracked elsewhere.
- **No guarantee of full validity** — the fingerprint is a trigger/skip, not a proof; "the world moved around an unreferenced area" is out of scope beyond the optional shared-file widening.
- **No auto-apply without surfacing** — a refresh that mutates the plan reports what changed; it doesn't silently rewrite premises.
- **Declared-surface blind spot** — `compute_code_fingerprint`'s watched surface is the plan's **declared** `files`/`creates`, so it reliably catches drift in code the plan already knows about but **cannot** detect a new sibling that now conflicts or another merge that did the work in an unlisted file. Optional mitigation: widen the watched surface using the existing foundational-logic shared-file sweep so the fingerprint covers shared logic, not just literally-declared paths — keep this opt-in / bounded. The residual is exactly why a deeper, explicit reconcile still earns its place.

## Risks

- **Fingerprint noise.** A whole-file hash flips on a comment/format change → a "drift" that triggers reconcile needlessly. Acceptable for a gate that errs toward re-checking, but reuse `compute_content_hash` semantics and consider normalized hashing if noise is bad.
- **Persistence churn.** Stamping the fingerprint into frontmatter on every grounding edits the plan file each run; a sidecar avoids plan-file churn but adds a file to keep in sync. Pick deliberately and document.
- **Declared-surface blind spot.** Don't oversell the gate as full validity; keep the deep-reconcile escape hatch (see Out of scope).
- **Stale/absent fingerprint.** A plan created before this feature has no stored fingerprint → treat as "needs grounding" (run reconcile), never crash on the missing field.
- **Scope coupling to reconcile internals.** Scoping reconcile to a file subset must use a supported seam, not reach into private state, so the reuse doesn't fossilize `reconcile-plan`'s internals.

## Testing

Follow TESTING.md's invoker-seam rules — stub the invoker and assert it is never spawned on the no-drift path. Cover:

- **Fingerprint persist + reload round-trip** — a grounded plan carries the stored code map + plan digest + timestamp and reloads identically.
- **No-drift → zero Claude calls** — on an unchanged tree the refresh makes **no** Claude call (assert the stubbed invoker is never spawned) and exits 0 fast.
- **Drift → scoped reconcile** — after a watched file changes, reconcile is invoked over **exactly** the changed-file set and the fingerprint is re-stamped afterward.
- **`creates:` file not yet on disk** is omitted from the fingerprint (no crash).
- **Edge: no fingerprint stored yet** → treated as "needs grounding" without crashing on the missing field.

Existing `reconcile-plan` / `fingerprint.py` / `auto_reconcile.py` tests must still pass — the engine is reused, not duplicated. The drift-check unit is pure/deterministic and should be exercised in isolation; reserve integration coverage for the CLI refresh surface and the reusable entry point wired end-to-end.

## Acceptance criteria

- After `create`/`detail`, a plan carries a stored grounding fingerprint (code map + plan digest + timestamp) on a tracked property.
- The refresh command on an **unchanged** tree makes **no Claude call** and reports the plan is still grounded (exit 0).
- The refresh command after a watched file changes detects exactly the changed path(s), runs reconcile scoped to them, updates the plan, and re-stamps the fingerprint.
- The refresh logic is exposed as a reusable entry point (callable by the branch-awareness hook) in addition to its CLI surface.
- The reconcile/refresh/`--reprocess` surface is documented so the four are distinguishable; `--reprocess`'s help no longer reads as a code reconcile.
- A plan with no stored fingerprint is treated as "needs grounding" and does not crash on the missing field.
- Existing `reconcile-plan` / fingerprint / auto-reconcile tests still pass; the engine is reused, not duplicated.
- RUNBOOK carries a walkthrough for refreshing a stale plan (the cheap-gate behavior) plus the naming clarification.
