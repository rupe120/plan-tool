> **Auto-archived**: this plan was swept on 2026-06-14 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Gate the four reuse-prompt helpers on fingerprint freshness

## Summary

- **Inserts a fingerprint-freshness gate** between "a saved sidecar was located" and "offer to reuse it" in the reuse-prompt helpers, so reuse is offered only when the saved plan- and code-fingerprints still match current disk. A stale save declines to a fresh audit — never a non-zero exit.
- **Two implementation sites.** `plan_tool/cli/reconcile.py:_prompt_reuse_saved` (the parametrized core both `_prompt_reuse_saved_detail_reconcile` and `_prompt_reuse_saved_run_reconcile` delegate to — they inherit the gate for free) consumes step 3's `resolve_reusable_reconcile`, pinned by the located sidecar's stem. `plan_tool/cli/review_cmd.py:_prompt_reuse_saved_review` gates inline (recompute + three-way diff) because its `"review"`-kind sidecar has no `resolve_reusable_*` sibling.
- **Load-bearing decision:** the gate is a **best-effort interactive UX gate** — it swallows parse/fingerprint failures and declines (returns `None` → fresh audit), unlike step 3's resolver which propagates `ParseError`. It sits *before both* the `--yes` fast path and the interactive `_ask_reuse_saved` prompt, so `--yes` accepts only a *fresh* save.
- **On green:** a fresh sidecar reuses exactly as today; a code-drifted save emits the attributed `path (step N: title)` warning + `detail --reconcile` hint and runs fresh; a plan-drifted or legacy (`code_fingerprint_present=False`) save emits a one-line note and runs fresh. Existing prompt-reuse tests are updated to seed fingerprint-fresh saves; new stale/legacy cases are added.

## Table of Contents

- [Why](#why) — what an ungated reuse prompt risks today
- [Files (creates vs edits)](#files-creates-vs-edits) — two production files, one test file, plus the out-of-footprint review test file
- [Implementation](#implementation) — the gate at both sites, the shared warning emitter, the best-effort posture
- [Tests](#tests) — repointed prompt tests + new fresh/stale/legacy cases
- [Test-creation order (feature step)](#test-creation-order-feature-step) — author-with-implementation, green-before-done
- [Acceptance criteria](#acceptance-criteria) — observable gate behavior
- [References](#references) — fingerprint producers, the resolver, the attribution renderer
- [Deferred](#deferred) — the three-diff consolidation and the two warn-emitter merge

## Why

The four reuse-prompt helpers locate the newest saved audit for a step (`_find_saved_for_step`) or plan (`list_saved_reviews`) and offer to **substitute saved findings for a fresh Claude call** — but they never check whether that save still describes the code on disk. Steps 1–3 made every reconcile-family and plan-wide sidecar carry a `plan_fingerprint` + `code_fingerprint`, and step 3 added `resolve_reusable_reconcile` to verdict them; nothing reads those fingerprints at the prompt yet. So today a user who edited a step's files since the last audit is still offered (and under `--yes`, silently handed) a stale save, masking real drift. This step closes that gap: the prompt offers reuse only on a fresh save, and on drift declines to a fresh audit with the same attributed-warning UX the completeness reuse path (step 5 of the completeness plan) already ships.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/cli/reconcile.py`:
    - **Add the freshness gate to `_prompt_reuse_saved`** — after `matched = _find_saved_for_step(...)` resolves `(saved_path, saved)`, call `resolve_reusable_reconcile` (step 3, same module) pinned to `saved_path.stem`, and branch on the verdict before the `--yes` / `_ask_reuse_saved` paths. The two named wrappers (`_prompt_reuse_saved_detail_reconcile`, `_prompt_reuse_saved_run_reconcile`) stay one-line delegators — untouched.
    - **Add `_warn_reuse_code_drift(drifted_code, plan, repo_root, *, loop_name="reconcile")`** — the shared attributed code-drift emitter, reusing `_print_attributed_files` (already in this module), `scope_guard.build_file_to_step_map`, and `drift_detection.reconcile_drift_hint`.
    - **Imports:** the module imports only `error` from `plan_tool.style` today — add `warn` and `tool` to that block for the new emitter's stale note and recovery hint; reference `build_file_to_step_map` (`plan_tool.scope_guard`) and `reconcile_drift_hint` (`plan_tool.drift_detection`) body-locally per reconcile.py's convention.
  - `plan_tool/cli/review_cmd.py`:
    - **Add the inline freshness gate to `_prompt_reuse_saved_review`** — after `saved = load_review(most_recent)`, recompute `compute_plan_fingerprint` / `compute_code_fingerprint` and run the changed|deleted|new diff against the loaded sidecar; decline on stale before printing the offer.
    - **Imports:** add `compute_plan_fingerprint` to the existing `from plan_tool.review_persistence import (...)` block; add `from plan_tool.fingerprint import compute_code_fingerprint`; add `parse_plan, ParseError, ValidationError` from `plan_tool.parser`; add `warn` to the existing `from plan_tool.style import (...)` block; add `from plan_tool.cli.reconcile import _warn_reuse_code_drift` (mirrors `completeness_cmd`'s top-import of `_print_attributed_files` from `reconcile` — acyclic, since `reconcile` never imports `review_cmd`).
  - `tests/cli/test_reconcile_engine.py`:
    - Add a `_seed_fresh_save(...)` helper (writes a real plan + in-scope code file, computes both fingerprints, persists a save carrying them); repoint the two `--yes` prompt tests onto it; add the new stale/legacy/parse-failure cases.

- **Out-of-footprint edit (flagged, not in `files:`):** `tests/test_review_walk.py` — the `_prompt_reuse_saved_review` integration tests (`test_yes_walks_saved_skips_claude` and siblings, the `TestReviewReuse`-style block near `_seed_saved_review`) seed un-fingerprinted reviews and **break under the gate** (a `plan_fingerprint=""` save is now stale → runs fresh). They must be updated to seed fingerprint-fresh reviews, plus one new stale-runs-fresh case. No production edit lives there; the review helper's gating tests are added in `test_reconcile_engine.py` where possible, but the `main([...])`-level review-reuse cases stay in their existing home.

## Implementation

### Foundational logic

**The gate is one predicate applied at two prompt sites:** *given a located saved sidecar, is it still fresh (saved plan- AND code-fingerprint == current disk)?* Fresh → offer reuse (existing path, unchanged). Stale → decline (`return None`, the caller runs a fresh audit) after emitting drift feedback. The same predicate already drives the completeness reuse decision (`plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse` → `_warn_code_drift`); this step brings the reconcile and plan-wide-review prompts to parity.

### `plan_tool/cli/reconcile.py:_prompt_reuse_saved` (covers both reconcile wrappers)

- **Insert the gate after the locate, before the accept paths.** Keep every existing cheap suppression first (`--dry-run`; `--no-walk`/`--no-save` when `kind.honor_no_walk_no_save`; non-TTY without `--yes`; `_find_saved_for_step` miss) so a suppressed prompt never recomputes a fingerprint. Then:
  - Require a real `plan_path` — when `plan_path is None`, decline (`return None`); the verdict can't be computed without it.
  - Compute the verdict by **pinning step 3's resolver to the located sidecar's stem**:
    `ru = resolve_reusable_reconcile(plan_slug, ctx.repo_root, plan_path=plan_path, review_id=saved_path.stem, kind_filter=kind.noun)`.
    - `kind.noun` is the `_RECONCILE_KINDS` key (`"detail-reconcile"` / `"run-reconcile"`) — `kind_filter` resolves the same descriptor.
    - Pinning by `saved_path.stem` collapses the resolver's *newest-of-kind* selection onto exactly the **step-scoped** sidecar `_find_saved_for_step` already chose, so the verdict matches the located save even when the newest sidecar of that kind belongs to a different step.
    - **Confirm the exported name and arity at HEAD before consuming.** `resolve_reusable_reconcile` and its `ReusableReconcile` verdict (the `.fresh` / `.plan_match` / `.code_match` / `.drifted_code` fields this gate reads) are minted by step 3 and absent from `plan_tool/cli/reconcile.py` at this step's HEAD — grep the module for the symbol and its signature before wiring the call, and match it exactly rather than inventing a shape; if step 3's landed export diverges from the `(plan_slug, repo_root, *, plan_path, review_id, kind_filter)` signature documented here, follow the actual export.
  - **Best-effort posture (load-bearing):** wrap the `resolve_reusable_reconcile` call in `try/except (ParseError, ValidationError, OSError)` and decline on failure (`return None`). This deliberately **does not** mirror step 3's resolver, which propagates a `ParseError` (a deterministic resolver fed a known-good path). The prompt is an interactive UX seam — a malformed plan must drop to a fresh audit, never crash the command (`never a non-zero exit`). Same posture as the helper's existing `except _RLE: return None` on a load miss.
  - On `ru is None` (pin missed / nothing resolved) → decline.
- **Branch on the verdict:**
  - `not ru.fresh and not ru.code_match and ru.drifted_code` → parse the plan best-effort (`try: plan = parse_plan(plan_path) except (ParseError, ValidationError): plan = None`) and, when parsed, call `_warn_reuse_code_drift(ru.drifted_code, plan, ctx.repo_root)`; then decline.
  - `not ru.fresh and not ru.plan_match` → one-line `warn(f"saved {kind.noun} for step {saved.step_id} is stale (plan changed since {saved.created_at}); running fresh")`; then decline.
  - `ru.fresh` → fall through to the **unchanged** `--yes` fast-path (byte-exact `(--yes) walking saved …` line) and `_ask_reuse_saved` prompt; return `saved_path` on accept.
- The two wrappers (`_prompt_reuse_saved_detail_reconcile`, `_prompt_reuse_saved_run_reconcile`) and `_find_saved_for_step` / `_ask_reuse_saved` are **untouched** — they inherit the gate through the core.

### `plan_tool/cli/reconcile.py:_warn_reuse_code_drift` (new shared emitter)

- **Signature:** `_warn_reuse_code_drift(drifted_code, plan, repo_root, *, loop_name="reconcile") -> None`. Mirrors `completeness_cmd._warn_code_drift` but lives in `reconcile.py` (the canonical home of `_print_attributed_files`) so both the reconcile core (same module) and `review_cmd` (import) reuse one emitter.
- **Body:** build `file_to_step = build_file_to_step_map(plan, repo_root)`; `warn(f"saved audit is stale ({len(drifted_code)} code file(s) changed since the audit); running fresh. Drifted files:")`; `_print_attributed_files(drifted_code, repo_root, file_to_step)` (the `path (step N: title)` lines, path-then-owning-step, byte-for-byte the live drift-warning format); close with `tool(reconcile_drift_hint(loop_name), stream=sys.stderr)`. `loop_name="reconcile"` (non-`None`) yields the `detail --reconcile`-only recovery line per `reconcile_drift_hint`'s contract.
- `drifted_code` from `ru.drifted_code` is already absolute-resolved-sorted, so it aligns key-for-key with `build_file_to_step_map`'s resolved-absolute keys without re-resolving.

### `plan_tool/cli/review_cmd.py:_prompt_reuse_saved_review` (plan-wide review, inline gate)

- **Why inline, not the resolver:** the plan-wide review sidecar is `kind="review"` (the `save_review` default at `cmd_review`'s save), which is **not** in `_RECONCILE_KINDS` — `resolve_reusable_reconcile`'s `name_includes` (`-detail-reconcile` / `-run-reconcile`) never matches it, and there is no `resolve_reusable_review`. So this helper recomputes the verdict itself, mirroring `plan_tool/completeness_report.py:resolve_reusable_audit`'s three-way diff. (The helper's existing selection — `"-reconcile" not in p.name` — is not strictly review-kind: it can also pick a `-completeness.json` save. The fingerprint diff is kind-agnostic, so it verdicts whichever sidecar is selected; the inline gate inherits that pre-existing selection unchanged.)
- **Placement:** after `saved = load_review(most_recent)` succeeds and before the metadata print. Require `plan_path` (the helper already takes `plan_path: Optional[Path]`); when `None`, decline.
- **Compute, wrapped in `try/except (ParseError, ValidationError, OSError) → return None`:**
  - `plan_match = bool(saved.plan_fingerprint) and saved.plan_fingerprint == compute_plan_fingerprint(plan_path)`.
  - Code axis: if `not saved.code_fingerprint_present` → `code_match = False`, `drifted_rel = set()` (legacy/never-computed is stale, never a spurious all-`new` diff — same gate as `resolve_reusable_audit`); else `plan = parse_plan(plan_path)`, `current = compute_code_fingerprint(plan, plan_path, ctx.repo_root)`, `changed | deleted | new` over `saved.code_fingerprint`, `code_match = not drifted_rel`.
  - `drifted_code = sorted((ctx.repo_root.resolve() / rel).resolve() for rel in drifted_rel)`.
- **Branch identically to the reconcile core:** code drift → `_warn_reuse_code_drift(drifted_code, plan, ctx.repo_root)` then `return None`; plan drift → one-line `warn(...)` then `return None`; fresh → fall through to the **unchanged** metadata print + `--yes` / `input_fn` accept path.

### Non-obvious decisions

- **`--yes` is gated too.** `--yes` means "accept the offered reuse without prompting" — it must not accept a *stale* save. The gate precedes the `--yes` branch at both sites, so `--yes` over a drifted save declines + runs fresh (and the stale-feedback still prints).
- **Deterministic checks stay ungated.** Only the expensive Claude reconcile/review axis is skipped on reuse; the freshness recompute runs on **every** invocation, fresh or stale (cheap, deterministic) — consistent with the reuse-path invariant captured across the completeness plan.

## Tests

`tests/cli/test_reconcile_engine.py` (helpers driven directly with explicit args — no module-global monkeypatch, per the file's split-proof convention):

- `_seed_fresh_save(...)` helper (new) — writes a minimal valid plan `demo.md` (frontmatter + one step whose `id` matches and whose `files:` names a real in-scope code file, extending `tests/cli/conftest.py:_minimal_plan_text`), writes that code file, then `save_review(..., plan_fingerprint=compute_plan_fingerprint(plan), code_fingerprint=compute_code_fingerprint(parse_plan(plan), plan, repo))` so the located sidecar reads fresh against disk.
- `TestPromptReuseDetailReconcile::test_yes_returns_path_with_byte_exact_line` — **repoint** onto `_seed_fresh_save`; still returns the path with the byte-exact `(--yes) walking saved detail-reconcile …` line.
- `TestPromptReuseRunReconcile::test_yes_returns_path_with_byte_exact_line` — **repoint** the run-reconcile twin identically.
- `test_stale_code_declines_with_attributed_warning` — seed fresh, edit a `step.files` code file, `--yes` → returns `None`; stderr carries a `path (step N: title)` line and the `detail --reconcile` hint.
- `test_stale_plan_declines_with_oneline_note` — seed fresh, edit the plan/detail bundle → returns `None`; stderr carries the one-line plan-stale note and **no** attributed file list.
- `test_legacy_save_without_fingerprints_declines` — seed via the plain `_seed_save` (no fingerprints, `code_fingerprint_present=False`), `--yes` → returns `None` (legacy is never fresh).
- `test_fresh_save_offers_via_prompt` — fresh, non-`--yes`, `input_fn` → `"y"` returns the path; `""` returns `None`.
- `test_parse_failure_declines_not_raises` — `plan_path` points at a malformed plan → returns `None`, raises nothing (best-effort posture).
- `test_both_wrappers_share_the_gate` — drive `_prompt_reuse_saved_detail_reconcile` and `_prompt_reuse_saved_run_reconcile` against a stale fixture; both decline (the gate lives in the shared core).

`tests/test_review_walk.py` (out-of-footprint, `main([...])`-level review reuse):

- `test_yes_walks_saved_skips_claude` (+ siblings) — **update** `_seed_saved_review` to write matching `plan_fingerprint`/`code_fingerprint`; reuse still skips `review_plan_full`.
- `test_stale_review_runs_fresh` (new) — seed a review whose code file is then edited → `review_plan_full` runs; stderr carries the attributed drift warning.

### Test-creation order (feature step)

This is a **feature** step — new gating behavior. Author the unit tests in `tests/cli/test_reconcile_engine.py` alongside the gate: write `_seed_fresh_save` and the fresh-path repoints first (prove fresh still reuses), then the stale-code / stale-plan / legacy / parse-failure cases (prove each declines). Update the `tests/test_review_walk.py` review-reuse cases in the same change so the suite is green end to end. **Green-before-done gate:** every new and repointed test — across both files — must pass before this step is considered finished; a red `test_review_walk.py` case left by the gate is an incomplete step, not a separate follow-up.

## Acceptance criteria

- `_prompt_reuse_saved` over a **fresh** detail-reconcile / run-reconcile sidecar returns the saved path (byte-exact `--yes` line unchanged).
- `_prompt_reuse_saved` over a **code-drifted** sidecar returns `None`, prints a `path (step N: title)` line per drifted file and a `detail --reconcile` recovery hint to stderr, and exits no command non-zero.
- `_prompt_reuse_saved` over a **plan-drifted** or **legacy** (`code_fingerprint_present=False`) sidecar returns `None` with a one-line stale note and no attributed file list.
- A malformed plan at `plan_path` makes the gate return `None` without raising.
- `_prompt_reuse_saved_review` exhibits the same fresh/stale-code/stale-plan/legacy behavior for the plan-wide `"review"` sidecar.
- `_warn_reuse_code_drift` renders byte-identically to the live drift warnings (`render_attributed_path_line` via `_print_attributed_files`).
- The full `tests/cli/test_reconcile_engine.py` and `tests/test_review_walk.py` suites pass (`uv run pytest tests/cli/test_reconcile_engine.py tests/test_review_walk.py -q`).

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the SHA-256 backing `compute_plan_fingerprint` / `compute_code_fingerprint` the gate recomputes.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path.stem` (the resolver pin key) and the repo-root-relative resolution that aligns `drifted_code` with `build_file_to_step_map`.
- `plan_tool/completeness_report.py:resolve_reusable_audit` (in-repo) — the canonical three-way (changed|deleted|new) diff the inline review gate mirrors.
- `plan_tool/cli/reconcile.py:resolve_reusable_reconcile` (in-repo, step 3) — the reconcile-family verdict producer the core consumes, pinned by stem.
- `plan_tool/cli/completeness_cmd.py:_warn_code_drift` / `_resolve_audit_reuse` (in-repo, step 5 of the completeness plan) — the parity template for the warning + decline-to-fresh decision.
- `plan_tool/drift_detection.py:render_attributed_path_line` / `reconcile_drift_hint` (in-repo) — the `path (step N: title)` line format and the `detail --reconcile` recovery sentence.
- `plan_tool/scope_guard.py:build_file_to_step_map` (in-repo) — per-step attribution keyed on resolved-absolute paths.

## Deferred

- **Consolidate the three fingerprint diffs** (`resolve_reusable_audit`, `resolve_reusable_reconcile`, and this step's inline review diff) into one shared `diff_fingerprint_maps` / verdict helper — a cross-module refactor `detail` can't mint; the third consumer landing here is the signal, but the extraction is its own step.
- **Merge `completeness_cmd._warn_code_drift` with the new `reconcile._warn_reuse_code_drift`** — two near-identical attributed emitters now exist; collapsing them is a follow-up consolidation, left separate here to keep this step's footprint to the two `files:` modules.
- **A `resolve_reusable_review` sibling for the `"review"` kind** — would let `_prompt_reuse_saved_review` drop its inline diff onto a resolver like the reconcile core; deferred because adding a `"review"` row to `_RECONCILE_KINDS` (or a parallel resolver) is a step-3-shaped producer addition, not part of gating.
