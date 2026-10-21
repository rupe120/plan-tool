> **Auto-archived**: this plan was swept on 2026-06-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add `plan_tool/refresh.py`: a reusable refresh entry point (no-Claude drift gate, scoped reconcile on drift, re-stamp grounding)

## Summary

- **Add `plan_tool/refresh.py`**, a mid-tier orchestrator exposing one reusable entry point `refresh_plan(plan_path, repo_root, *, run_logger=None, file=None)` plus a `RefreshOutcome` dataclass — the function the step-4 `reconcile-plan --refresh` CLI and the branch-awareness branch-creation hook both call.
- **Load-bearing decision:** the entry point *wires* existing primitives, mints no judgement — `plan_tool/grounding.py:read_grounding` + `check_grounding_drift` (step 2) decide drift with **zero Claude**, and `plan_tool/auto_reconcile.py:run_auto_reconcile_on_drift` is the **supported seam** for scoping reconcile to the drifted files (no reach into reconcile-engine private state).
- **Three branches:** no stored grounding → treat as "needs grounding", reconcile over the whole declared surface, then write a first grounding baseline so the gate clears on the next run; stored grounding + no code drift → fast no-op, **no Claude call**, no sidecar rewrite; stored grounding + drift → reconcile scoped to exactly the drifted files, then re-stamp the grounding sidecar.
- **Surface, don't silently mutate:** the scoped reconcile runs through `run_auto_reconcile_on_drift`, which **saves findings** (for `reconcile-plan-walk`) rather than applying them — honoring the plan's *No auto-apply without surfacing* boundary. The re-stamp records "examined at this code state" so the next refresh's gate clears.
- **On green:** an unchanged tree returns `RefreshOutcome(drifted=False, reconciled=False)` having spawned no invoker; a changed watched file is reconciled over the exact changed-path set and the sidecar is re-stamped; a pre-feature plan with no sidecar never crashes.

## Table of Contents

- [Why](#why) — what the entry point gives the CLI and the branch hook, and why it's pure wiring
- [Files (creates vs edits)](#files-creates-vs-edits) — the new module and its test file
- [Implementation](#implementation) — `RefreshOutcome`, the three-branch gate, the scoped-reconcile seam, the re-stamp
- [Tests](#tests) — no-Claude gate, scoped reconcile, no-baseline, missing `creates:`, re-stamp
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer/CI can check
- [References](#references) — hashlib / pytest monkeypatch docs for this step's surfaces
- [Deferred](#deferred) — CLI surface, authoring stamp, finding application, force re-ground, widened surface

## Why

- **The drift gate and the reconcile engine both exist, but nothing composes them into a one-call "is this plan still grounded, and re-ground it if not."** Step 1 single-sourced the map-diff (`plan_tool/fingerprint.py:diff_code_fingerprint`), step 2 added the persisted baseline + pure check (`plan_tool/grounding.py`), and `plan_tool/auto_reconcile.py:run_auto_reconcile_on_drift` already runs a focused reconcile over the steps owning a drifted-file set. This step is the thin orchestrator that reads the baseline, decides drift with no Claude, and — only on drift — drives the existing reconcile seam and re-stamps.
- **A reusable entry point separate from the CLI wrapper is a plan requirement.** Per the plan's *Architecture* point 4 and acceptance criteria, the branch-awareness branch-creation hook must be able to call refresh without going through argparse. Putting the logic in `plan_tool/refresh.py` (not inside `plan_tool/cli/review_cmd.py`) gives step 4 a thin CLI shim and the branch hook a direct import, with one shared implementation.
- **The no-drift fast path must cost zero backend calls.** The plan's *Testing* and acceptance criteria mandate that an unchanged tree makes no Claude call and exits fast. Branching on `check_grounding_drift` *before* importing/invoking `run_auto_reconcile_on_drift` is what guarantees the invoker is never spawned on the fresh path.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/refresh.py` — the `RefreshOutcome` dataclass and `refresh_plan` entry point, plus module-level imports of the leaf primitives and a body-local import of the reconcile seam.
  - `tests/test_refresh.py` — unit coverage for the three branches, the no-Claude assertion, the scoped-reconcile call shape, the no-baseline path, missing-`creates:` resilience, and the re-stamp.
- **Existing files (edits only):** none. The CLI surface (`plan_tool/cli/review_cmd.py` + `plan_tool/cli/authoring.py` help text, step 4) and the authoring stamp (`plan_tool/cli/authoring.py`, step 5) are later steps — see [Deferred](#deferred).

## Implementation

### Module placement and imports

- **Confirm the step-1/step-2 cross-step contract at HEAD before relying on it.** This body treats `plan_tool/fingerprint.py:diff_code_fingerprint` and `plan_tool/grounding.py`'s `read_grounding` / `check_grounding_drift` / `write_grounding(plan_fingerprint=…, code_fingerprint=…)` / `Grounding.code_fingerprint` as already-exported surfaces, but they land in steps 1 and 2 — at HEAD `grounding.py` may not yet exist and `fingerprint.py` may export only `compute_code_fingerprint`. Before wiring against them, grep HEAD to verify each name, its arity, and its return shape actually match what this step assumes; if a predecessor step shipped a different signature, adapt the calls below to the real one rather than the names written here.
- **`plan_tool/refresh.py` is a mid-tier orchestrator** sitting above the leaves `plan_tool/fingerprint.py`, `plan_tool/grounding.py` (step 2), `plan_tool/scope_guard.py`, `plan_tool/review_persistence.py`, `plan_tool/parser.py`, and `plan_tool/locator.py`. Import these at module top — all are cheap and Claude-free.
- **Import `run_auto_reconcile_on_drift` body-locally inside the drift branch of `refresh_plan`** (`from plan_tool.auto_reconcile import run_auto_reconcile_on_drift`), matching the three existing direct importers (`plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/cli/reconcile.py`). Two reasons: (1) it keeps the no-drift path from even importing the reconcile seam, reinforcing the zero-Claude guarantee; (2) the body-local re-resolve is what lets `tests/test_refresh.py` patch `plan_tool.auto_reconcile.run_auto_reconcile_on_drift` and have the patch take effect through a direct `refresh_plan(...)` call.
- **Module-level stdlib imports:** `dataclasses` (`dataclass`, `field`), `pathlib.Path`, `typing.Optional`.

### The result record — `RefreshOutcome`

- **A `@dataclass`** the entry point returns so the CLI shim (step 4) and the branch hook can render/branch on the outcome without re-deriving it:
  - `plan_slug: str`
  - `needs_grounding: bool` — `True` when no sidecar existed (pre-feature plan); the baseline was synthesized as whole-plan drift.
  - `drifted: bool` — `True` when a reconcile ran (either `needs_grounding` or a non-empty code diff).
  - `drifted_files: list[Path]` — the absolute, resolved, sorted paths reconcile was scoped to (empty on the fresh path).
  - `findings: int` — the count returned by `run_auto_reconcile_on_drift` (0 on the fresh path).
  - `reconciled: bool` — `True` when the reconcile seam was invoked.
  - `grounding_path: Optional[Path]` — the re-stamped sidecar path, or `None` when nothing was written (the fresh no-op path).

### The entry point — `refresh_plan(plan_path, repo_root, *, run_logger=None, file=None) -> RefreshOutcome`

- **Parse once and derive the slug:** `plan = parse_plan(plan_path)` and `plan_slug = slug_from_filename(plan_path)` (`default_to_stem=True`, so non-`None`; assert it). Let `parse_plan`'s `ParseError`/`ValidationError` propagate — a malformed plan is a hard caller error, distinct from the soft "absent sidecar" case `read_grounding` swallows.
- **Compute the current code fingerprint:** `current_code_fp = compute_code_fingerprint(plan, plan_path, repo_root)` (`plan_tool/fingerprint.py`). A declared `creates:` file not yet on disk is already *omitted* by `compute_code_fingerprint` (digest `None`), so this never crashes on a not-yet-created file.
- **Read the baseline:** `grounding = read_grounding(plan_path)` (`plan_tool/grounding.py`, step 2) — returns `None` fail-soft for absent/malformed/old-schema sidecars.
- **Branch 1 — no baseline (`grounding is None`): "needs grounding" → whole-plan reconcile.** Per the plan's *Stale/absent fingerprint* risk ("treat as needs grounding (run reconcile), never crash on the missing field"), synthesize a whole-plan drift scope: `file_to_step = build_file_to_step_map(plan, repo_root)` then `drifted_files = sorted(file_to_step)`. Set `needs_grounding=True`, fall through to the reconcile-and-restamp tail.
- **Branch 2 — baseline present, no code drift: fast no-op, zero Claude.** `code_match, drifted_files = check_grounding_drift(grounding, current_code_fp, repo_root)`. When `code_match` is `True`, return `RefreshOutcome(plan_slug, needs_grounding=False, drifted=False, drifted_files=[], findings=0, reconciled=False, grounding_path=None)` **without importing or calling `run_auto_reconcile_on_drift`**. Do **not** rewrite the sidecar — the stored fingerprints are unchanged and a timestamp-only rewrite is needless churn on a tracked file; the fresh path leaves the working tree byte-identical.
- **Branch 3 — baseline present, code drift:** `code_match` is `False`. `check_grounding_drift` already returns `drifted_files` as the absolute, resolved, sorted `Path` set steps 1–2 produce (`diff_code_fingerprint` resolves each drifted key under `repo_root` before returning), exactly `build_file_to_step_map`'s key shape — so no re-resolution is needed. Use `drifted_files` as-is and fall through to the reconcile-and-restamp tail.
- **Reconcile-and-restamp tail (branches 1 and 3):**
  - `file_to_step = build_file_to_step_map(plan, repo_root)` (`plan_tool/scope_guard.py`) — for branch 3 this is computed here; for branch 1 it was already computed to synthesize the scope.
  - Body-local `from plan_tool.auto_reconcile import run_auto_reconcile_on_drift`, then `findings = run_auto_reconcile_on_drift(drifted=drifted_files, file_to_step=file_to_step, plan_path=plan_path, plan_slug=plan_slug, repo_root=repo_root, run_logger=run_logger, file=file)`. This runs a `detail-reconcile` per owning step and **saves findings** for `reconcile-plan-walk` — it does not apply them (the plan's *No auto-apply without surfacing*).
  - **Re-stamp the grounding sidecar:** `write_grounding(plan_path, plan_fingerprint=compute_plan_fingerprint(plan_path), code_fingerprint=current_code_fp)`.
    - **The seam is non-mutating:** `run_auto_reconcile_on_drift` doesn't touch *code* (`launcher.py:MUTATING_MODES == frozenset({"run"})`, so `detail-reconcile` neither marks steps done nor edits code) and saves findings rather than rewriting the plan markdown or the per-step detail `*.md` files.
    - **So the post-call fingerprints are valid:** `compute_plan_fingerprint` hashes the whole detail bundle alongside the plan markdown (`review_persistence.py`'s `compute_plan_fingerprint` folds the per-step detail files into the digest), so the untouched detail files mean `current_code_fp` and the post-call `compute_plan_fingerprint` still describe the just-examined tree.
    - **What the stamp records:** "this plan was examined against this code state," clearing the gate for the next refresh while the surfaced findings await `reconcile-plan-walk`.
  - Return `RefreshOutcome(plan_slug, needs_grounding=<branch-1?>, drifted=True, drifted_files=drifted_files, findings=findings, reconciled=True, grounding_path=<write_grounding result>)`.

### Shared-logic scan

- **Foundational logic:** the *order* drift-gate → scoped-reconcile → re-stamp. The gate (`check_grounding_drift`) and the reconcile seam (`run_auto_reconcile_on_drift`) already exist; this step adds only the composition and the re-stamp call. No new diff, no new reconcile loop, no new fingerprint logic.
- **Whole-plan scope synthesis** (`build_file_to_step_map(plan, repo_root)` → `sorted(...)` as `drifted`) draws its scope from `build_file_to_step_map`, the single source for the plan's declared-file surface — no copy of the map logic is introduced.
- **Re-stamp persistence** reuses `plan_tool/grounding.py:write_grounding` (step 2) verbatim; no parallel sidecar writer is introduced.
- **The reconcile-scoping seam** is `run_auto_reconcile_on_drift`, deliberately not a reach into reconcile-engine internals — addresses the plan's *Scope coupling to reconcile internals* risk.

## Tests

All tests live in `tests/test_refresh.py`, are hermetic (`tmp_path`), and call `refresh_plan(...)` directly (the CLI surface is step 4). Follow TESTING.md: stub the reconcile seam — patch `plan_tool.auto_reconcile.run_auto_reconcile_on_drift` (a spy returning an int) for drift cases, and patch `plan_tool.launcher.run_step` to **raise** `AssertionError` for the no-drift case to prove no invoker is spawned (the raising-stub discipline). A shared fixture builds a tmp plan with a couple of in-scope code files + detail files and writes a grounding sidecar via `plan_tool.grounding.write_grounding`.

### Test-creation order (feature step)

This is a **feature** step. Add every test below **with** the implementation; all must be green (`uv run pytest -m "not integration" tests/test_refresh.py -q`) before the step is considered finished.

- `test_no_drift_returns_clean_outcome` — grounded plan, unchanged tree → `RefreshOutcome(drifted=False, reconciled=False, findings=0, grounding_path=None)`.
- `test_no_drift_spawns_no_invoker` — same setup with `plan_tool.launcher.run_step` patched to raise `AssertionError`; `refresh_plan` returns normally, proving the reconcile seam is never reached on the fresh path.
- `test_no_drift_does_not_rewrite_sidecar` — the `grounding.json` bytes (and mtime-independent content) are unchanged after a no-drift refresh.
- `test_drift_runs_scoped_reconcile_over_exact_files` — mutate one watched file; assert the `run_auto_reconcile_on_drift` spy was called once with `drifted` equal to exactly that file's absolute resolved path (and `file_to_step`/`plan_slug`/`repo_root` correct).
- `test_drift_restamps_grounding` — after a drift reconcile, `read_grounding(plan_path).code_fingerprint` equals the current `compute_code_fingerprint`, so an immediately-following `refresh_plan` takes the no-drift path.
- `test_drift_outcome_reports_findings_count` — the spy returns `3`; `RefreshOutcome.findings == 3`, `reconciled is True`, `drifted is True`.
- `test_no_baseline_treated_as_needs_grounding` — no sidecar on disk → `needs_grounding is True`, reconcile runs over the whole declared surface (`drifted_files == sorted(build_file_to_step_map(...))`), and a sidecar is written.
- `test_no_baseline_does_not_crash_on_missing_field` — a malformed/old-schema sidecar (`read_grounding` → `None`) is treated identically to absent, no exception.
- `test_missing_creates_file_omitted_no_crash` — a `creates:` path absent from disk is omitted from the fingerprint and `refresh_plan` completes without error.
- `test_malformed_plan_propagates` — an unparseable plan markdown raises `ParseError`/`ValidationError` (not swallowed), distinguishing it from the soft absent-sidecar case.

## Acceptance criteria

- `plan_tool/refresh.py` exists, exporting `refresh_plan` and `RefreshOutcome`.
- `refresh_plan` on a grounded plan with an unchanged tree returns `drifted=False`, `reconciled=False`, `findings=0`, `grounding_path=None`, and spawns **no** Claude invoker (the patched `run_step`/seam is never called).
- `refresh_plan` after a watched file changes calls `run_auto_reconcile_on_drift` with `drifted` equal to **exactly** the changed-file set (absolute, resolved, sorted) and re-stamps `grounding.json` so a subsequent refresh reports no drift.
- `refresh_plan` on a plan with no stored sidecar sets `needs_grounding=True`, reconciles over the whole declared surface, and writes a baseline sidecar — without crashing on the missing field.
- A declared `creates:` file not yet on disk does not crash `refresh_plan`.
- `plan_tool/refresh.py` imports nothing from `plan_tool/cli/*`; the reconcile seam is imported function-locally.
- `uv run pytest -m "not integration" tests/test_refresh.py -q` is green; existing `reconcile-plan` / `fingerprint` / `auto_reconcile` / `grounding` suites still pass unmodified.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the SHA-256 digests `compute_code_fingerprint`/`compute_plan_fingerprint` produce and `check_grounding_drift` compares; this module only orchestrates them.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — `monkeypatch.setattr` for the spy on `plan_tool.auto_reconcile.run_auto_reconcile_on_drift` and the raising stub on `plan_tool.launcher.run_step` that proves no invoker on the no-drift path.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — for step 4's `reconcile-plan --refresh` shim that will wrap this entry point (not edited here; listed for the consuming step).

## Deferred

- **`reconcile-plan --refresh` CLI surface + `--reprocess` help clarification** — step 4 (`plan_tool/cli/review_cmd.py`, `plan_tool/cli/authoring.py`); this step provides only the importable entry point.
- **Stamping grounding after `create`/`detail`** — step 5 (`plan_tool/cli/authoring.py`); `refresh_plan` re-stamps only after a refresh-triggered reconcile, not at authoring time.
- **Applying the surfaced findings** — `run_auto_reconcile_on_drift` saves findings for `reconcile-plan-walk`; auto-application is out of scope (plan's *No auto-apply without surfacing*).
- **A `force` / re-ground-regardless knob** — a parameter to bypass the gate and reconcile the whole surface unconditionally is plausible for the branch hook but unneeded by step 4; add when a caller needs it.
- **Widened watched surface + normalized hashing** — plan-level deferrals; the scope is exactly `compute_code_fingerprint`'s declared surface with whole-file hashing.
