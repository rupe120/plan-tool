> **Auto-archived**: this plan was swept on 2026-06-14 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Reuse Saved Reconcile Audit (fingerprinted reconcile-family reuse)
status: completed
priority: medium
steps:
- id: 1
  title: Promote compute_code_fingerprint to a shared leaf module (plan_tool/fingerprint.py)
    so both the completeness and reconcile families compute the code-side digest without
    a completeness_report import edge; repoint the completeness caller (behavior-preserving)
  files:
  - plan_tool/fingerprint.py
  - plan_tool/completeness_report.py
  - plan_tool/cli/completeness_phases.py
  - tests/test_fingerprint.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/reuse-saved-reconcile-audit/01-promote-compute-code-fingerprint-shared.md
  status: done
- id: 2
  title: Compute + persist plan_fingerprint + code_fingerprint at every reconcile
    save seam (reconcile-plan, detail --reconcile, run-reconcile/reconcile-code, the
    automatic drift-reconcile, and the walk sub-reconcile) so each saved sidecar carries
    both axes
  files:
  - plan_tool/cli/review_cmd.py
  - plan_tool/cli/reconcile.py
  - plan_tool/auto_reconcile.py
  - plan_tool/cli/review_actions.py
  - tests/test_review.py
  - tests/cli/test_reconcile_engine.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/reuse-saved-reconcile-audit/02-compute-persist-plan-fingerprint-code.md
  status: done
- id: 3
  title: Add resolve_reusable_reconcile(plan_name, repo_root, *, plan_path, review_id=None,
    kind_filter) — locate the newest (or pinned) matching sidecar, recompute both
    fingerprints, return loaded SavedReview + fresh bool (plan AND code match) + drifted_code
    list (changed/deleted/new; deletions reported across the save/reload boundary;
    repo-root-resolved to absolute Paths to align with build_file_to_step_map attribution)
  files:
  - plan_tool/cli/reconcile.py
  - plan_tool/cli/app.py
  - tests/cli/test_reconcile_engine.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/reuse-saved-reconcile-audit/03-resolve-reusable-reconcile-plan-name.md
  status: done
- id: 4
  title: Gate the four reuse-prompt helpers (_prompt_reuse_saved_review, _prompt_reuse_saved,
    _prompt_reuse_saved_detail_reconcile, _prompt_reuse_saved_run_reconcile) on fingerprint
    freshness — only offer reuse when fresh; on code drift emit the attributed staleness
    warning (render_attributed_path_line + build_file_to_step_map, path-then-owning-step)
    closing with the detail --reconcile recovery hint; a stale plan- or code-fingerprint
    declines reuse with a one-line note and falls back to a fresh audit (never a non-zero
    exit)
  files:
  - plan_tool/cli/review_cmd.py
  - plan_tool/cli/reconcile.py
  - tests/cli/test_reconcile_engine.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/reuse-saved-reconcile-audit/04-gate-four-reuse-prompt-helpers-prompt.md
  status: done
- id: 5
  title: Add --reuse/--no-reuse + --reuse-id STEM flags to reconcile-plan, reconcile-code,
    and detail --reconcile for parity with completeness-audit's --reuse-audit family
    (unset default = prompt interactively, auto-accept under --yes / non-TTY; explicit
    --reuse reuses-when-fresh and warns-then-re-audits when stale; an unresolvable
    --reuse-id stem warns-and-proceeds to a fresh audit rather than erroring)
  files:
  - plan_tool/cli/review_cmd.py
  - plan_tool/cli/run_cmd.py
  - plan_tool/cli/authoring.py
  - tests/cli/test_review_cmds.py
  - tests/cli/test_run_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/reuse-saved-reconcile-audit/05-reuse-no-reuse-reuse-id-stem-flags.md
  status: done
- id: 6
  title: 'Add end-to-end integration coverage in tests/test_cli.py: main([reconcile-plan/reconcile-code/detail
    --reconcile, ...]) twice through stubbed invokers asserting zero claude calls
    on fresh reuse, stale re-audit on a plan edit AND on an in-scope code edit, deleted-in-scope-file
    flagged with the attributed warning, and the --no-reuse/--reuse-id matrix'
  files:
  - tests/test_cli.py
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/reuse-saved-reconcile-audit/06-end-end-integration-coverage-tests-test.md
  status: done
- id: 7
  title: Update docs/RESUME_FLOW.md and docs/AUDIT_FLOW.md to describe fingerprinted
    reconcile-family reuse (plan AND code fingerprints; the still-re-derived deterministic
    layer); add the new flags + code-drift staleness warning to RUNBOOK.md
  files:
  - docs/RESUME_FLOW.md
  - docs/AUDIT_FLOW.md
  - RUNBOOK.md
  complexity: low
  change_type: non-code
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/reuse-saved-reconcile-audit/07-update-docs-resume-flow-md-docs-audit.md
  status: done
---
# Reuse Saved Reconcile Audit

## Overview

Brings the plan/code fingerprint **save + freshness-validation** that the *Reuse Saved Completeness Audit* plan (`docs/implementation-plans/2-reuse-saved-completeness-audit.md`) adds to `completeness-audit` to the rest of the audit families — the **reconcile** verbs: `reconcile-plan`, `reconcile-code` (legacy `run --reconcile`), and `detail --reconcile` (plus the automatic drift-reconcile and the walk-time sub-reconcile). Today each of these already persists a JSON sidecar under `plan-details/<slug>/reports/<ts>-<kind>.json` and already *offers to reuse the newest save* before spending a Claude call (`_prompt_reuse_saved_review`, `_prompt_reuse_saved`, `_prompt_reuse_saved_detail_reconcile`, `_prompt_reuse_saved_run_reconcile`) — but that reuse is keyed only on **existence and recency**, with no check that the plan text or the code the findings were reasoned against is unchanged. A saved reconcile can therefore be replayed against a plan or codebase that has moved underneath it. This plan stores both fingerprints (`plan_fingerprint` over the plan + detail bundle; `code_fingerprint`, a per-file SHA-256 map over `step.all_files`) on every reconcile save, and gates each reuse prompt on **both** still matching — declining reuse on a stale fingerprint and, on a code drift specifically, naming exactly which in-scope files moved and which step owns each (`path (step N: title)`), closing with the `detail --reconcile` recovery hint.

**Prerequisite (shared substrate).** This plan consumes — and does not re-create — the fingerprint storage and plan-side compute helpers introduced by plan 2: the `SavedReview.plan_fingerprint` / `code_fingerprint` / `code_fingerprint_present` fields and their save/load/annotate round-trip (plan 2 step 1), the promoted `drift_detection.compute_content_hash` (plan 2 step 2), and `compute_code_fingerprint` (plan 2 step 3). Plan 2 steps 1–3 must land before this plan; step 1 here promotes `compute_code_fingerprint` out of `completeness_report.py` into a shared leaf so the reconcile seams can call it without importing the completeness module.

## Problem statement

The reconcile verbs are commonly re-run: `reconcile-plan` after each code change to catch drift, `detail --reconcile` to refresh a step's detail, `reconcile-code` to push the code back toward the plan — and `run` fires the automatic drift-reconcile on its own. Each persists a walkable sidecar and each will *offer to reuse the most recent one* (e.g. `_prompt_reuse_saved_review` in `plan_tool/cli/review_cmd.py:84` and the three `_prompt_reuse_saved*` helpers in `plan_tool/cli/reconcile.py`). But that reuse-offer is decided purely by "a save exists and you said yes" — `resolve_saved_review` (`review_persistence.py:352`) returns the newest sidecar with no freshness check. So accepting a reuse can replay findings computed against a plan/codebase that has since changed, masking real drift. This plan scopes the fix to those four interactive **reuse-offer prompts**; the non-interactive `reconcile-plan-walk` replay path (which re-walks a stored sidecar without a fresh Claude call) is deferred and stays uncovered for now — see the Deferred section. The completeness family is gaining exactly this protection in plan 2; the reconcile family — the audits *most* about plan↔code agreement — has none.

## Architecture

The sidecar substrate is already fingerprint-capable after plan 2 (`SavedReview` carries `plan_fingerprint` / `code_fingerprint` / `code_fingerprint_present`; `save_review` / `load_review` / `update_annotation` round-trip them). This plan does three things on top.

**Shared compute_code_fingerprint (step 1).** Plan 2 lands `compute_code_fingerprint(plan, plan_path, repo_root)` inside `completeness_report.py`. The reconcile seams must not import `completeness_report` (a non-leaf orchestrator), so step 1 promotes the helper into a new leaf `plan_tool/fingerprint.py` and repoints the completeness caller. `plan_tool/fingerprint.py` imports only `hashlib`, `pathlib`, `scope_guard.compute_drift_watched_paths`, and the promoted `drift_detection.compute_content_hash` — keeping the digest logic in one place both families share. `compute_plan_fingerprint` stays defined in `review_persistence.py` per plan 2's leaf rule; each seam imports the plan- and code-fingerprint producers from their own modules (`review_persistence` and `fingerprint`) — two import lines, not one surface.

**Persist at every reconcile save seam (step 2).** Each `save_review(...)` call in the reconcile family computes `plan_fingerprint = compute_plan_fingerprint(plan_path)` and `code_fingerprint = compute_code_fingerprint(plan, plan_path, repo_root)` and passes both. The seams: `reconcile-plan` (`review_cmd.py:289`, `kind="review"`), `detail --reconcile` (`reconcile.py:769` and the iterate-loop save at `reconcile.py:1425`, `kind="detail-reconcile"`), `reconcile-code` / `run --reconcile` (`reconcile.py:985`, `kind="run-reconcile"`), the automatic drift-reconcile (`auto_reconcile.py:172`, `kind="detail-reconcile"`), and the walk-time sub-reconcile (`review_actions.py:177`, `kind="detail-reconcile"`). The `Plan` is already parsed at each seam (or trivially available), so the code-side digest is computed where `scope_guard` is importable — never inside the leaf persistence module.

**resolve_reusable_reconcile (step 3).** A new helper locates the newest (or `--reuse-id`-pinned) sidecar of a given kind via `list_saved_reviews` + a `-<kind>.json` name filter, loads it, recomputes the current plan and code fingerprints, and returns the loaded `SavedReview`, a `fresh: bool` (`plan_fingerprint` match **AND** `code_fingerprint` match, gated on `code_fingerprint_present` so a legacy/never-computed capture is stale), and a `drifted_code: list[Path]` diff (changed = hash differs, **deleted** = key gone from disk, **new** = a `(new)` entry that has since landed). Unlike the live-edit `check_drift`, deletions are reported — a vanished in-scope file is a genuine staleness signal across a save/reload boundary. Returns `None` (with a one-line note) when no sidecar matches, so a bad `--reuse-id` pin falls back cleanly to a fresh audit.

**Gate the reuse prompts (step 4).** Three of the four `_prompt_reuse_saved*` helpers call `resolve_reusable_reconcile` directly; `_prompt_reuse_saved_review` (whose `kind="review"` sidecar sits outside `_RECONCILE_KINDS`) gates inline against the same recompute + diff, pinned to the resolver's verdict by a parity test. All only offer reuse when `fresh`. A stale plan fingerprint declines with a one-line note; a stale **code** fingerprint upgrades the note to a structured, attributed warning naming each `drifted_code` file with its owning step (reusing `drift_detection.render_attributed_path_line` + `scope_guard.build_file_to_step_map` — the same `path (step N: title)` rendering the live-edit drift warnings use) and the `detail --reconcile` recovery hint. The warning is informational (per the exit-code convention, failure-to-complete only — never a non-zero exit). Auto-accept under `--yes` / non-TTY still applies, but only to a **fresh** save; a stale save always declines and re-audits regardless of `--yes`.

**Flag parity (step 5).** `reconcile-plan`, `reconcile-code`, and `detail --reconcile` gain `--reuse` / `--no-reuse` (a `BooleanOptionalAction` whose unset default = prompt interactively) and `--reuse-id STEM`, mirroring `completeness-audit`'s `--reuse-audit` family: `--no-reuse` never reuses; `--reuse` reuses-when-fresh and warns-then-re-audits when stale; `--reuse-id` pins a specific sidecar (an unresolvable pin warns-and-proceeds to a fresh audit). Deterministic reconcile checks (file existence, deps, path-style) are always re-derived from disk; only the Claude-driven reconcile pass is reused.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the streamed SHA-256 used by `compute_content_hash` and the plan/code fingerprints.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — bundle globbing, sidecar location, and repo-root-relative path resolution for attribution.
- [argparse — BooleanOptionalAction](https://docs.python.org/3/library/argparse.html) — wiring the `--reuse` / `--no-reuse` toggle with an unset-default sentinel and `--reuse-id STEM`.
- `docs/implementation-plans/archive/2-reuse-saved-completeness-audit.md` (in-repo) — the template; this plan reuses its `SavedReview` fingerprint fields, `compute_plan_fingerprint`, `compute_code_fingerprint`, and `compute_content_hash`.
- `plan_tool/drift_detection.py` (in-repo) — `compute_content_hash` (per-file digest) and `render_attributed_path_line` (the `path (step N: title)` warning renderer).
- `plan_tool/scope_guard.py` (in-repo) — `compute_drift_watched_paths` (the `step.all_files` code surface, minus plan/detail) and `build_file_to_step_map` (per-step attribution).
- `plan_tool/review_persistence.py` (in-repo) — `save_review` / `load_review` / `resolve_saved_review` / `list_saved_reviews`, the seams every reconcile kind shares.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **The shared substrate itself** — `SavedReview`'s fingerprint fields, `compute_plan_fingerprint`, and the `compute_content_hash` promotion are added by plan 2 (its steps 1–2) and are a hard prerequisite, not re-created here.
- **Caching the deterministic reconcile checks** — file-existence / dep / path-style / heuristic checks are cheap and must reflect current disk; they always re-derive.
- **Promoting the fingerprint to a plan-level manifest** every reload path consults (so `run` / `jira` reload would also warn). The fingerprint lives in each kind's sidecar; a cross-command manifest is a broader, separate change.
- **Git-aware drift shortcuts** (recording `git rev-parse HEAD`, pre-filtering with `git diff --name-only`). Per-file hashing is the source of truth (it catches uncommitted edits); a git fast-path is a later optimization.
- **Auditor/prompt-version invalidation** — the freshness verdict keys only on plan and code content, not the `plan-tool` or reconcile-prompt version; folding a version component in is a separate follow-up.

## Risks

- A reused reconcile could mask plan changes if the fingerprint is too coarse; mitigated by hashing the plan plus every per-step detail file (`compute_plan_fingerprint`), so any edit invalidates the cache.
- A reused reconcile could mask **code** changes the audit was reasoned against; mitigated by the per-file `code_fingerprint` over `step.all_files`, folded into `fresh` (reuse requires plan AND code match) and surfaced as an attributed per-file drift warning.
- Six save calls across five conceptual seams (four files) risk an inconsistent capture (one seam forgets a fingerprint); mitigated by routing all seams through the single shared `compute_*_fingerprint` pair (step 1) and a direct sidecar-presence assertion on the four primary seams (`reconcile-plan`, `detail --reconcile`, `reconcile-code`, the automatic drift-reconcile), with the remaining two (`_iterate_reconcile_loop`, the `review_actions` walk sub-reconcile) covered transitively since they reuse the same persistence paths.
- A deleted in-scope file could be silently dropped (the live-edit `check_drift` ignores deletions); mitigated by `resolve_reusable_reconcile` diffing the saved map's keys against current disk and reporting a missing key as drift.
- Legacy fingerprint-less sidecars could be reused unsafely; mitigated by `load_review` defaulting a missing `plan_fingerprint` to `""` and a missing `code_fingerprint_present` to `False`, both treated as stale → a fresh audit.
- Gating four reuse helpers risks divergent behavior; mitigated by one shared warning renderer plus a parity test pinning the inline `review` gate (`_prompt_reuse_saved_review`, whose `kind="review"` sidecar sits outside `_RECONCILE_KINDS`) to `resolve_reusable_reconcile`'s verdict — the other three helpers funnel through the resolver directly.

## Testing

Unit tests (`tests/test_fingerprint.py`, `tests/cli/test_reconcile_engine.py`): the promoted `compute_code_fingerprint` round-trips its pre-promotion behavior; each reconcile save seam persists a sidecar carrying a non-empty `plan_fingerprint` and a `code_fingerprint` keyed by the on-disk `step.all_files`; `resolve_reusable_reconcile` returns the correct `fresh` verdict and `drifted_code` set for fresh / stale-by-plan / stale-by-code / deleted-in-scope-file / missing / pinned-by-id cases; the four reuse helpers offer reuse only when fresh and emit the attributed warning on code drift. `tmp_path`-hermetic; no Claude.

Integration tests (`tests/test_cli.py`): drive `main(["reconcile-plan", ...])`, `main(["reconcile-code", ...])`, and `main(["detail", ..., "--reconcile", ...])` twice through stubbed invokers — first run saves a fingerprinted sidecar; second run with reuse accepted issues zero reconcile Claude calls and still walks the findings; an edited plan between runs re-audits (stale-by-plan); editing or deleting an in-scope `step.files` code file re-audits (stale-by-code) and prints the attributed per-file drift warning; `--no-reuse` always re-audits and `--reuse-id` pins a save. Integration-tier per CLAUDE.md (drives the CLI end to end); invokers stubbed so no real `claude` spawns.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — behavior-preserving; the promoted helper's existing tests move/extend and stay green.
- steps 2–6 (feature) — tests authored with the implementation; green before completion.
- step 7 (non-code) — doc verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- After any reconcile save (`reconcile-plan`, `reconcile-code`, `detail --reconcile`, the automatic drift-reconcile, the walk sub-reconcile), the JSON sidecar carries a non-empty `plan_fingerprint` and a `code_fingerprint` map keyed by the repo-relative `step.all_files` paths that exist on disk.
- A second run on an unchanged plan AND unchanged code, with reuse accepted, replays the saved findings with zero new reconcile Claude calls while still re-deriving the deterministic checks from disk.
- Editing the plan body or any per-step detail file changes `plan_fingerprint`, so the next run declines reuse and re-audits with a one-line note.
- Editing or deleting any in-scope code file from `step.all_files` changes `code_fingerprint`, so the next run declines reuse, re-audits, and prints a structured warning naming each drifted file with its owning step (`path (step N: title)`) and the `detail --reconcile` recovery hint — without a non-zero exit.
- Reuse requires BOTH fingerprints to match: a plan-only change, a code-only change, or both decline reuse.
- `--no-reuse` always re-audits; `--reuse` reuses when fresh and warns-then-re-audits when stale; `--reuse-id <stem>` pins a sidecar; an unresolvable pin falls back to a fresh audit with a note.
- Under `--yes` / non-TTY, a *fresh* sidecar is reused without prompting; a stale one always declines regardless of `--yes`.
- `load_review` reads a legacy sidecar lacking the fingerprints without error and treats it as stale.
- `compute_code_fingerprint` lives in a shared leaf (`plan_tool/fingerprint.py`); neither the reconcile seams nor `review_persistence.py` import `completeness_report`.

## Deferred

- Whole-bundle granularity — any edit invalidates the entire cache; reusing the unaffected subset of a stale reconcile is a separate, larger effort.
- Garbage-collection of old `-<kind>.json` sidecars — accumulation is left to manual cleanup.
- Cross-command fingerprint surfacing (a plan-level manifest every reload path consults) — postponed to keep the fingerprint per-kind/per-sidecar.
- A post-apply re-audit before the `--iterate` sidecar rewrite (the same provenance limit plan 2 documents) — out of scope.
- Staleness signalling for the non-interactive `reconcile-plan-walk` replay path — this plan gates only the four interactive reuse-offer prompts; folding a fingerprint check into the walk replay is a separate follow-up.
