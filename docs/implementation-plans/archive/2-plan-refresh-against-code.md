> **Auto-archived**: this plan was swept on 2026-06-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Plan Refresh Against Code
status: completed
priority: medium
steps:
- id: 1
  title: Extract the saved→current code-fingerprint map-diff into one shared fingerprint.py
    helper (dedup completeness_report + reconcile)
  files:
  - plan_tool/fingerprint.py
  - plan_tool/completeness_report.py
  - plan_tool/cli/reconcile.py
  - tests/test_fingerprint.py
  complexity: low
  change_type: refactor
  gate:
  - '! grep -rq ''set(saved_fp) - set(current_code_fp)'' plan_tool/completeness_report.py
    plan_tool/cli/reconcile.py'
  detail: docs/implementation-plans/plan-details/plan-refresh-against-code/01-extract-saved-current-code-fingerprint.md
  status: done
- id: 2
  title: 'Add plan_tool/grounding.py leaf: read/write a tracked grounding sidecar
    (code map + plan digest + timestamp) and a pure drift-check'
  creates:
  - plan_tool/grounding.py
  - tests/test_grounding.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/plan-refresh-against-code/02-plan-tool-grounding-py-leaf-read-write.md
  status: done
- id: 3
  title: 'Add plan_tool/refresh.py reusable entry point: drift-gate (no Claude on
    empty diff), scoped reconcile on drift, re-stamp grounding'
  creates:
  - plan_tool/refresh.py
  - tests/test_refresh.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/plan-refresh-against-code/03-plan-tool-refresh-py-reusable-entry.md
  status: done
- id: 4
  title: Surface refresh as `reconcile-plan --refresh` (skip Claude on no-drift) and
    clarify the --reprocess help text
  files:
  - plan_tool/cli/review_cmd.py
  - plan_tool/cli/authoring.py
  - tests/cli/test_review_cmds.py
  complexity: medium
  change_type: feature
  gate:
  - uv run plan-tool reconcile-plan --help 2>&1 | grep -q -- --refresh
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/plan-refresh-against-code/04-surface-refresh-reconcile-plan-refresh.md
  status: done
- id: 5
  title: Stamp the grounding fingerprint after a successful create / detail in the
    authoring handlers
  files:
  - plan_tool/cli/authoring.py
  - tests/cli/test_authoring_cmds.py
  complexity: low
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/plan-refresh-against-code/05-stamp-grounding-fingerprint-after.md
  status: done
- id: 6
  title: Document the refresh gate + distinguish reconcile-plan / reconcile-plan-walk
    / refresh / reprocess across operator surfaces
  files:
  - RUNBOOK.md
  - README.md
  - CLAUDE.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  - docs/AUDIT_RESUME_FLOW.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/plan-refresh-against-code/06-document-refresh-gate-distinguish.md
  status: done
---
# Plan Refresh Against Code

## Overview

Give an existing registered plan a cheap, deterministic way to tell whether its grounding is **stale relative to the current code**, and to **re-ground** itself when it is — by reusing the existing fingerprint and reconcile machinery rather than minting a new engine. A refresh command recomputes the plan's code fingerprint, diffs it against a stored grounding fingerprint, and on no drift exits as a fast no-op with **no Claude call**; on drift it runs the existing reconcile engine scoped to the exact changed files, then re-stamps the fingerprint. The feature ships standalone and also exposes a reusable entry point the branch-awareness plan's branch-creation flow can call.

## Problem statement

A plan is drafted against the codebase at one moment, then sits through review / merges to `main` while other developers' work lands. By the time someone picks it up, its premises may have drifted — files it targets moved, symbols renamed, or another merge already implemented part of it *in a file the plan declares*. (That last case is covered only on the plan's declared `files`/`creates` surface; a merge that did the work in an unlisted file is the declared-surface blind spot called out in Out of scope.) Today there is no first-class way to (a) know the plan needs a refresh without re-reading everything, or (b) refresh it short of a full manual reconcile. This is useful **independently** ("update the plan, I'm not starting work yet") and as the **hook** the branch-awareness plan names at branch-creation time.

## Architecture

plan-tool already has the exact primitives, built for "did the code drift since a saved audit", so this feature is mostly *wiring*, not new judgement:

- **`plan_tool/fingerprint.py:compute_code_fingerprint(plan, plan_path, repo_root)`** → a reproducible `{repo-relative-path: sha256}` **map** over the plan's in-scope code surface (exactly `scope_guard.compute_drift_watched_paths` — every `step.files`/`creates` entry, minus the plan markdown and per-step detail files). Built in sorted order, byte-for-byte stable across machines.
- **`plan_tool/review_persistence.py:compute_plan_fingerprint(plan_path)`** → a digest of the plan itself, plus a saved-record shape that already carries `plan_fingerprint` + `code_fingerprint` (the path→hash map) + `code_fingerprint_present`, used by `auto_reconcile.py` for reuse-staleness checks.
- **The reconcile engine** (`launcher.py:verify_plan` / `reconcile-plan`) already judges plan-vs-code, mutates the plan to match, and consumes these fingerprints for reuse.

The wiring:

1. **Persist a "grounding fingerprint" on the plan** at the grounding points this plan covers — after `create`/`detail` and after a `--refresh`: the `compute_code_fingerprint` map + the `compute_plan_fingerprint` digest, plus a timestamp. (A plain `reconcile-plan` / `reconcile-plan-walk` apply cycle is out of scope here and does not re-stamp; the next `--refresh` re-grounds it.) The stored **plan digest is reserved for `SavedReview` parity** — it is persisted so the grounding record carries the same `plan_fingerprint` + `code_fingerprint` shape the reuse-staleness machinery already reads, not consumed by this plan's drift gate (the drift decision in step 3 diffs the code map and consults the "examined, findings-pending" flag, but not the plan digest). It is not a write-only orphan: it keeps the grounding sidecar interchangeable with the saved-audit record and leaves room for a later plan-self-edit staleness check without a schema change.
2. **The drift check** recomputes the code fingerprint against the current tree and diffs it against the stored map — empty diff = fresh, non-empty diff = the exact set of changed files. Pure/deterministic, no Claude; reuse the map-diff already implied by `auto_reconcile`'s staleness logic.
3. **The refresh command/mode** — the cheap "still grounded" no-op (exit 0, no Claude call) fires only when the code diff is empty **and** the grounding is in a *clean* state (last grounded by `create`/`detail`, or by a refresh whose scoped reconcile fully succeeded with no findings left to apply). On a non-empty diff it invokes the existing reconcile engine **scoped to the changed files**, which **surfaces findings for `reconcile-plan-walk` (no auto-mutate)**. Because that examine saves findings without applying them — and is best-effort, silently skipping any owning step whose `detail-reconcile` errors or exits non-zero — the refresh must **not** clear the gate over that work. It records a **distinct "examined, findings-pending" grounding state** (a flag alongside the stamped code map), not a clean re-ground: while that state is set, the next refresh reports "examined at this code state, findings pending — run `reconcile-plan-walk`" rather than "still grounded", even on an empty code diff. The findings-pending state clears only when the findings are applied / the reconcile fully succeeds (e.g. a later clean re-ground), so the cheap gate never reports "still grounded" over unapplied drift. Any step the best-effort reconcile failed to examine is left **un-stamped / stale**, so the next refresh re-examines it instead of treating its drift as resolved.
4. **A reusable entry point** the branch-awareness branch-creation hook (and any future command) can call, separate from the CLI wrapper.

**No-baseline path is a full reconcile, not the cheap gate.** When a plan has no stored fingerprint (every pre-feature plan until step 5's stamping has run everywhere), there is no baseline to diff against, so the refresh synthesizes whole-plan drift over every declared file and drives the reconcile engine — one `detail-reconcile` Claude call per owning step. That first refresh is an N-step, N-Claude-call reconcile by design; the cheap deterministic skip applies only on a *subsequent* refresh against a present baseline. This cost is expected and not a regression in the gate.

**Where the grounding fingerprint lives** (load-bearing). Persist it as a **tracked plan property** — plan frontmatter (e.g. `grounded_code_fingerprint` / `grounded_plan_fingerprint` / `grounded_at`) or the existing saved-audit sidecar under the plan-details `reports/` dir, whichever churns less. **Tracked is correct here**, the deliberate contrast with the branch-awareness plan: a branch binding is per-clone **session** state (which branch is *this checkout* on) → untracked/local; a grounding fingerprint is a **shared fact about the plan** (the code state it was last grounded against) → it should travel with the plan through PR/merge, diff in review, and be the same for everyone.

**Naming — rationalize the family.** The reconcile/refresh surface is already crowded and `create --reprocess` is mis-named (it means "fill `_(TODO)_` placeholders from an archived predecessor", nothing to do with code). Prefer expressing refresh as a **mode of the existing reconcile** (e.g. `reconcile-plan --refresh` / `--pre-start`) over a brand-new top-level verb; a thin sibling verb is acceptable only if it reads more clearly. Whatever the surface, it must **dedupe hard against `reconcile-plan`'s engine** — share the judgement/grounding code, never re-mint it. The one **behavioral** difference from plain `reconcile-plan` is the **fingerprint gate** (skip when nothing drifted). The **all-PENDING / pre-start framing** (the useful axis is "are the premises still valid", not "does code satisfy a done step") is **positioning only** — refresh does not inspect step run-state, guard, or warn when run against a plan with non-PENDING steps; it runs the same gate + scoped reconcile regardless. Don't bill the framing as a behavioral precondition (no step operationalizes it); it names the situation refresh is *for*, not a state it enforces. **Documented caveat — run-state vs. external drift.** Because refresh does not inspect run-state and step 5 stamps the baseline at `create`/`detail` time (before the plan's `creates:` files exist), a refresh run *mid-implementation* — after `plan-tool run` has written the plan's own intended files — sees those just-written files as drift and reconciles the plan against its own in-progress implementation, treating intended work as external code drift. Refresh has no signal to distinguish the plan's own work from external drift, so this is a documented usage caveat rather than a guard: refresh is for the pre-start window (premises still valid before work begins), and running it against a partially-implemented plan will surface the plan's own writes as drift. Surface this caveat where the refresh surface is documented (step 6). Clarify `--reprocess` in help text (or rename) in the same pass so users can tell the four apart.

## References

- [hashlib — Secure hashes and message digests — Python documentation](https://docs.python.org/3/library/hashlib.html) — Official reference for sha256/hexdigest used to compute the deterministic code and plan fingerprints at the heart of the drift gate.
- [PyYAML Documentation (yaml module)](https://pyyaml.org/wiki/PyYAMLDocumentation) — Primary reference for safe-loading and dumping the YAML frontmatter where the grounding fingerprint fields (grounded_code_fingerprint / grounded_at) are stamped and read back.
- [Python Frontmatter — load/parse files with YAML front matter](https://python-frontmatter.readthedocs.io/) — Library guide for splitting YAML metadata from markdown body, relevant to persisting grounding fields as tracked plan frontmatter without disturbing prose.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — API reference for add_subparsers/add_parser and option flags, needed to add the refresh surface (reconcile-plan --refresh / --pre-start) and clarify --reprocess help text.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Official guide to monkeypatch.setattr for stubbing the Claude invoker seam and asserting it is never spawned on the no-drift path, per the plan's testing requirements.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **No new judgement engine** — reuse `reconcile-plan`/`fingerprint.py`; this is wiring + a gate + framing, not a new plan-vs-code brain.
- **No branch-awareness coupling baked in** — this ships standalone; the branch-creation hook is the *branch-awareness* plan's job to call this, not this plan's job to know about branches.
- **No manifest-as-derived-index work** — rebuilding `plans.json` from on-disk plan files + a union-merge driver is a separate registry-consistency concern, tracked elsewhere.
- **No guarantee of full validity** — the fingerprint is a trigger/skip, not a proof; "the world moved around an unreferenced area" is out of scope beyond the optional shared-file widening.
- **No auto-apply without surfacing** — a refresh that mutates the plan reports what changed; it doesn't silently rewrite premises.
- **Declared-surface blind spot** — `compute_code_fingerprint`'s watched surface is the plan's **declared** `files`/`creates`, so it reliably catches drift in code the plan already knows about but **cannot** detect a new sibling that now conflicts or another merge that did the work in an unlisted file. Optional mitigation: widen the watched surface using the existing foundational-logic shared-file sweep so the fingerprint covers shared logic, not just literally-declared paths — keep this opt-in / bounded. The residual is exactly why a deeper, explicit reconcile still earns its place.
- **Empty watched surface (the blind-spot extreme)** — a docs-only plan whose steps declare no code `files`/`creates` (e.g. step 6, all `non-code`) produces an empty `compute_code_fingerprint` map, so the drift check always returns `code_match=True` and refresh is a **permanent no-op by design**: with no watched code, there is nothing to ground against and the gate has no signal that the prose drifted from the code it describes. Refresh emits a one-line "nothing to ground (no code files declared)" notice rather than silently reporting "still grounded", so the operator can tell a no-watched-surface plan from a genuinely-fresh one. Re-validating docs against code is out of scope here — same residual as the declared-surface blind spot, only total.

## Risks

- **Fingerprint noise.** A whole-file hash flips on a comment/format change → a "drift" that triggers reconcile needlessly. Acceptable for a gate that errs toward re-checking, but reuse `compute_content_hash` semantics and consider normalized hashing if noise is bad.
- **Persistence churn.** Stamping the fingerprint into frontmatter on every grounding edits the plan file each run; a sidecar avoids plan-file churn but adds a file to keep in sync. Pick deliberately and document.
- **Declared-surface blind spot.** Don't oversell the gate as full validity; keep the deep-reconcile escape hatch (see Out of scope).
- **Stale/absent fingerprint.** A plan created before this feature has no stored fingerprint → no baseline to diff, so the refresh synthesizes whole-plan drift over every declared file and drives the reconcile engine (one `detail-reconcile` Claude call per owning step) before stamping a fresh baseline; never crash on the missing field. The cheap no-Claude skip is reserved for a subsequent refresh against a present baseline with no drift.
- **No-baseline refresh cost.** The first refresh of a pre-feature plan has no baseline to diff, so it synthesizes whole-plan drift and runs the reconcile engine over every declared file — one `detail-reconcile` Claude call per owning step, an N-step / N-call reconcile. This is the expected cost of grounding a plan that was never stamped; the cheap no-Claude skip only applies on later refreshes against a present baseline. Don't oversell refresh as always-cheap — the gate is cheap once a baseline exists.
- **Scope coupling to reconcile internals.** Scoping reconcile to a file subset must use a supported seam, not reach into private state, so the reuse doesn't fossilize `reconcile-plan`'s internals.

## Testing

Follow TESTING.md's invoker-seam rules — stub the invoker and assert it is never spawned on the no-drift path. Cover:

- **Fingerprint persist + reload round-trip** — a grounded plan carries the stored code map + plan digest + timestamp and reloads identically.
- **No-drift → zero Claude calls** — on an unchanged tree the refresh makes **no** Claude call (assert the stubbed invoker is never spawned) and exits 0 fast.
- **Drift → scoped reconcile** — after a watched file changes, reconcile is invoked over **exactly** the changed-file set and the grounding is stamped "examined, findings-pending" (not clean) afterward.
- **Findings-pending does not clear the gate** — after a drift refresh leaves findings pending, a subsequent refresh on the now-unchanged tree does **not** report "still grounded"; it surfaces the pending state, and clears only after the findings are applied / the reconcile fully succeeds. A step whose `detail-reconcile` errors is left stale, so the next refresh re-examines it.
- **`creates:` file not yet on disk** is omitted from the fingerprint (no crash).
- **Edge: no fingerprint stored yet** → no baseline to diff: the refresh synthesizes whole-plan drift, runs the reconcile engine over every declared file (one `detail-reconcile` Claude call per owning step), and stamps a fresh baseline, without crashing on the missing field (the cheap no-Claude skip applies only on a subsequent refresh against a present baseline).

Existing `reconcile-plan` / `fingerprint.py` / `auto_reconcile.py` tests must still pass — the engine is reused, not duplicated. The drift-check unit is pure/deterministic and should be exercised in isolation; reserve integration coverage for the CLI refresh surface and the reusable entry point wired end-to-end.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- After `create`/`detail`, a plan carries a stored grounding fingerprint (code map + plan digest + timestamp) on a tracked property.
- The refresh command on an **unchanged** tree whose grounding is clean makes **no Claude call** and reports the plan is still grounded (exit 0).
- The refresh command after a watched file changes detects exactly the changed path(s), runs reconcile scoped to them — surfacing findings for `reconcile-plan-walk` (no auto-mutate) — and records a distinct "examined, findings-pending" grounding state (it does not clean-re-ground).
- While the grounding is "examined, findings-pending" — or any owning step failed to be examined — the next refresh does **not** report "still grounded" even on an empty code diff; it surfaces the pending/unexamined state and clears only once the findings are applied / the reconcile fully succeeds.
- The refresh logic is exposed as a reusable entry point (callable by the branch-awareness hook) in addition to its CLI surface.
- The reconcile/refresh/`--reprocess` surface is documented so the four are distinguishable; `--reprocess`'s help no longer reads as a code reconcile.
- A plan with no stored fingerprint has no baseline to diff — the refresh synthesizes whole-plan drift, runs the reconcile engine over every declared file (one `detail-reconcile` Claude call per owning step), and stamps a fresh baseline, without crashing on the missing field; the cheap no-Claude skip applies only on a subsequent refresh against a present baseline.
- Existing `reconcile-plan` / fingerprint / auto-reconcile tests still pass; the engine is reused, not duplicated.
- RUNBOOK carries a walkthrough for refreshing a stale plan (the cheap-gate behavior) plus the naming clarification.

## Deferred

- **Widened watched surface via the foundational-logic shared-file sweep** — postponed; ships only if the declared-surface blind spot proves to bite in practice, kept opt-in / bounded so it doesn't balloon the fingerprint.
- **Normalized / whitespace-insensitive hashing** — deferred until comment/format-only churn is shown to trigger needless reconciles; the whole-file `compute_content_hash` is acceptable for a gate that errs toward re-checking.
