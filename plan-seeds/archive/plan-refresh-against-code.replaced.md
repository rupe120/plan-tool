> **Replaced**: this file has been superseded by `docs/implementation-plans/2-plan-refresh-against-code.md`.
> Preserved here for history; do not edit.

# Plan seed: fingerprint-gated plan re-grounding (refresh a plan against current code)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/plan-refresh-against-code.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose
below and proposes a step decomposition; the author then runs
`plan-tool detail` per step.

---

## Goal

Give an existing registered plan a cheap, deterministic way to tell
whether its grounding is **stale relative to the current code**, and to
**re-ground** itself when it is — reusing the fingerprint and reconcile
machinery that already exists, not minting a new engine.

The trigger case: a plan is drafted against the codebase at one moment,
then sits through review / merges to `main` while other developers' work
lands. By the time someone picks it up, its premises may have drifted —
files it targets moved, symbols renamed, or another merge already
implemented part of it. Today there is no first-class way to (a) know the
plan needs a refresh without re-reading everything, or (b) refresh it
short of a full manual reconcile.

This is useful **independently** ("update the plan, I'm not starting work
yet") and as the **hook** the branch-awareness plan names at branch-
creation time. It is intended to *largely* — not perfectly — resolve
re-grounding; see "What it can't catch".

## How it works — reuse, don't reinvent

plan-tool already has the exact primitives, built for "did the code drift
since a saved audit":

- **`plan_tool/fingerprint.py:compute_code_fingerprint(plan, plan_path,
  repo_root)`** → a reproducible `{repo-relative-path: sha256}` **map**
  over the plan's in-scope code surface (exactly
  `scope_guard.compute_drift_watched_paths` — every `step.files`/`creates`
  entry, minus the plan markdown and per-step detail files). Built in
  sorted order, byte-for-byte stable across machines.
- **`plan_tool/review_persistence.py:compute_plan_fingerprint(plan_path)`**
  → a digest of the plan itself, and a saved-record shape that already
  carries `plan_fingerprint` + `code_fingerprint` (the path→hash map) +
  `code_fingerprint_present`, used by `auto_reconcile.py` for reuse-
  staleness checks.
- **The reconcile engine** (`launcher.py:verify_plan` /
  `reconcile-plan`) already judges plan-vs-code and mutates the plan to
  match — and already consumes these fingerprints for reuse.

So this feature is mostly *wiring*, not new judgement:

1. **Persist a "grounding fingerprint" on the plan** whenever it is
   grounded — after `create`/`detail`, and after any reconcile/refresh:
   the `compute_code_fingerprint` map + the `compute_plan_fingerprint`
   digest, plus a timestamp.
2. **A refresh command recomputes and diffs.** Recompute the code
   fingerprint against the current tree and diff it against the stored
   map:
   - **No drift** (maps equal) → fast **no-op**: "plan still grounded,
     nothing to do" — **no Claude call**. This is the cheap gate.
   - **Drift** → the diff names the **exact set of changed files**; run
     the existing reconcile engine **scoped to those files**, update the
     plan, then **re-stamp** the grounding fingerprint.
3. **Surfaces both standalone and as a hook.** A standalone command the
   user can run anytime; and a reusable entry the branch-awareness plan's
   branch-creation flow can call (drift → prompt/refresh, clean → proceed
   silently).

## Where the grounding fingerprint lives (load-bearing — and deliberately the opposite of the branch binding)

Persist it as a **tracked plan property** — plan frontmatter (e.g.
`grounded_code_fingerprint` / `grounded_plan_fingerprint` / `grounded_at`)
or the existing saved-audit sidecar under the plan-details `reports/`
dir, whichever churns less. **Tracked is correct here**, and this is the
explicit contrast with the branch-awareness plan, which stores the branch
binding in *untracked, per-clone* state:

- A branch binding is per-clone **session** state ("which branch is *this
  checkout* on") → untracked/local.
- A grounding fingerprint is a **shared fact about the plan** ("the code
  state this plan was last grounded against") → it *should* travel with
  the plan through PR/merge, diff in review, and be the same for everyone.

So the two decisions don't conflict; each datum lands in its correct home.

## Naming — rationalize the family (don't add a fourth confusing verb)

The reconcile/refresh surface is already crowded and one entry is
mis-named: `create --reprocess` actually means "fill `_(TODO)_`
placeholders from an archived predecessor" — nothing to do with code.
Part of this plan's job is to make the family legible:

- Prefer expressing this as a **mode of the existing reconcile** (e.g.
  `reconcile-plan --refresh` / `--pre-start`) over a brand-new top-level
  verb, since it reuses that engine. A thin sibling verb is acceptable
  only if it reads more clearly.
- Whatever the surface, it must **dedupe hard against `reconcile-plan`'s
  engine** — share the judgement/grounding code, never re-mint it. The
  difference from plain `reconcile-plan` is the **fingerprint gate**
  (skip when nothing drifted) and the **all-PENDING / pre-start framing**
  (the useful axis is "are the premises still valid", not "does code
  satisfy a done step").
- Clarify `--reprocess` in help text (or rename) as part of the same
  pass, so users can tell the four apart.

## What it can't catch (why "largely", not "fully")

`compute_code_fingerprint`'s watched surface is the plan's **declared**
`files`/`creates`. So the fingerprint reliably catches drift in code the
plan already knows about, and is a sound **trigger** (drift → re-ground)
and a fast **skip** (no drift → no Claude call). It **cannot** detect
"the world moved around an area the plan never referenced" — a new
sibling that now conflicts, or another merge that already did the work in
a file the plan doesn't list. So it is not a *proof of validity*.

- Mitigation: optionally widen the watched surface using the existing
  foundational-logic shared-file sweep (the same instinct that finds
  sibling call-sites) so the fingerprint covers shared logic, not just
  literally-declared paths. Keep this opt-in / bounded.
- The residual is exactly why a deeper, explicit reconcile still earns
  its place; the fingerprint just makes sure you only pay for it when
  something actually moved.

## Scope of work (rough — `create` will decompose)

1. **Compute + persist the grounding fingerprint** at the points a plan
   is grounded (`create`/`detail` completion, and after each
   reconcile/refresh). Reuse `compute_code_fingerprint` +
   `compute_plan_fingerprint`; store on the tracked plan property; choose
   frontmatter vs. sidecar to minimize churn.
2. **The drift check** — recompute and diff the code-fingerprint map;
   return the changed-path set (empty = fresh). Pure/deterministic, no
   Claude. Reuse the map-diff already implied by `auto_reconcile`'s
   staleness logic.
3. **The refresh command/mode** — on empty diff, no-op + exit 0 (report
   "still grounded"); on non-empty, invoke the existing reconcile engine
   **scoped to the changed files**, mutate the plan, re-stamp the
   fingerprint. Reuse `reconcile-plan`; do not duplicate its judgement.
4. **A reusable entry point** the branch-awareness branch-creation hook
   can call (and any future command), separate from the CLI wrapper.
5. **Naming pass** — settle the reconcile/refresh/`--reprocess` surface
   and clarify help text.
6. **Tests** — fingerprint persist + reload round-trip; **no-drift →
   zero Claude calls** (stub the invoker; assert it's never spawned) +
   fast exit; drift → reconcile invoked over **exactly** the changed-file
   set + fingerprint re-stamped after; `creates:` file not yet on disk is
   omitted (no crash); the off/edge cases (no fingerprint stored yet →
   treat as "needs grounding"). Follow TESTING.md's invoker-seam rules.
7. **Docs** — RUNBOOK walkthrough (refresh a stale plan; the cheap-gate
   behavior), and the naming clarification.

## Non-goals

- **No new judgement engine.** Reuse `reconcile-plan`/`fingerprint.py`;
  this is wiring + a gate + framing, not a new plan-vs-code brain.
- **No branch-awareness coupling baked in.** This ships standalone; the
  branch-creation hook is the *branch-awareness* plan's job to call this,
  not this plan's job to know about branches.
- **No manifest-as-derived-index work.** Rebuilding `plans.json` from
  on-disk plan files + a union-merge driver is a separate concern
  (registry consistency), tracked elsewhere.
- **No guarantee of full validity.** The fingerprint is a trigger/skip,
  not a proof; "the world moved around an unreferenced area" is out of
  scope beyond the optional shared-file widening.
- **No auto-apply without surfacing.** A refresh that mutates the plan
  reports what changed; it doesn't silently rewrite premises.

## Acceptance criteria (plan-level)

- After `create`/`detail`, a plan carries a stored grounding fingerprint
  (code map + plan digest + timestamp) on a tracked property.
- The refresh command on an **unchanged** tree makes **no Claude call**
  and reports the plan is still grounded (exit 0).
- The refresh command after a watched file changes detects exactly the
  changed path(s), runs reconcile scoped to them, updates the plan, and
  re-stamps the fingerprint.
- The refresh logic is exposed as a reusable entry point (callable by the
  branch-awareness hook) in addition to its CLI surface.
- The reconcile/refresh/`--reprocess` surface is documented so the four
  are distinguishable; `--reprocess`'s help no longer reads as a code
  reconcile.
- Existing `reconcile-plan` / fingerprint / auto-reconcile tests still
  pass; the engine is reused, not duplicated.

## Risks

- **Fingerprint noise.** A whole-file hash flips on a comment/format
  change → a "drift" that triggers reconcile needlessly. Acceptable for a
  gate that errs toward re-checking, but reuse `compute_content_hash`
  semantics and consider normalized hashing if noise is bad.
- **Persistence churn.** Stamping the fingerprint into frontmatter on
  every grounding edits the plan file each run; a sidecar avoids plan-file
  churn but adds a file to keep in sync. Pick deliberately and document.
- **Declared-surface blind spot** (see "What it can't catch") — don't
  oversell the gate as full validity; keep the deep-reconcile escape hatch.
- **Stale/absent fingerprint.** A plan created before this feature has no
  stored fingerprint → treat as "needs grounding" (run reconcile), never
  crash on the missing field.
- **Scope coupling to reconcile internals.** Scoping reconcile to a file
  subset must use a supported seam, not reach into private state, so the
  reuse doesn't fossilize `reconcile-plan`'s internals.
```
