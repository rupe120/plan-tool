> **Auto-archived**: this plan was swept on 2026-06-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Stamp the grounding fingerprint after a successful `create` / `detail`

## Summary

- **Add one fail-soft helper** `_stamp_grounding(plan_path, repo_root)` to `plan_tool/cli/authoring.py` that parses the just-written plan, computes its code map + plan digest, and records the grounding sidecar via step 2's `plan_tool/grounding.py:write_grounding`.
- **Wire two call sites:** `cmd_create` (on the happy path, after `result.plan_path` exists and the split-proposal early return) and `cmd_detail` (in the existing `rc == 0 and wrote and not args.dry_run` clean-productive guard, after the completeness tail).
- **Load-bearing decision:** stamping is **advisory and fail-soft** — the helper wraps parse + compute + write in a guard that swallows any exception to a warning, so a stamp hiccup can never flip a successful authoring run's rc. It is the function-param analog of the [detail-authoring] fail-soft advisory-tail rule.
- **Cross-step dependency:** `plan_tool/grounding.py` does **not exist at HEAD** (step 2, `depends_on: 2`, is unimplemented). The `write_grounding` arity below is pinned to step 2's detail; confirm the seam at HEAD before wiring and adapt to the shipped shape if it diverged.
- **On green:** after `create`/`detail` writes a plan, a tracked `grounding.json` sidecar sits at `<plan-dir>/plan-details/<slug>/grounding.json` carrying the current `compute_code_fingerprint` map, `compute_plan_fingerprint` digest, and an ISO-8601-Z timestamp; a split-proposal create, a dry run, and a skipped-only detail run write nothing; a stamp failure leaves rc unchanged.

## Table of Contents

- [Why](#why) — the persistence half of the refresh gate that has no producer-side caller yet
- [Files (creates vs edits)](#files-creates-vs-edits) — the one helper plus two call-site wirings, and the test file
- [Implementation](#implementation) — the fail-soft helper, the `cmd_create` placement, the `cmd_detail` placement, the pinned `write_grounding` seam
- [Tests](#tests) — stamp-on-success, no-stamp on split/dry/skip, fail-soft, round-trip
- [Acceptance criteria](#acceptance-criteria) — observable post-change behaviors
- [References](#references) — the grounding/fingerprint surfaces this step calls
- [Deferred](#deferred) — re-stamp after reconcile/refresh, `split`/`reprocess` call sites, plan-digest gating

## Why

- **The refresh gate (steps 2–4) reads a grounding baseline that nothing writes on the producer side yet.** Step 2's `plan_tool/grounding.py:write_grounding` exists as a primitive; step 3's `refresh_plan` re-stamps *after a reconcile*. But a plan only ever gets a *first* grounding baseline when it is authored — `read_grounding` returns `None` (treated as "needs grounding") for every plan until `create`/`detail` stamps one. This step is that first-stamp wiring.
- **The plan's *Architecture* point 1 mandates it:** "Persist a grounding fingerprint on the plan whenever it is grounded — **after `create`/`detail`**, and after any reconcile/refresh." The reconcile/refresh half is step 3; the `create`/`detail` half is here.
- **The stamp must never destabilize authoring.** `create`/`detail` are the two most-run authoring verbs; a parse or I/O hiccup in a decorative grounding write must not turn a green author into a failure. Fail-soft is the load-bearing posture.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py`
    - Add top-level imports: `from plan_tool.grounding import write_grounding`, `from plan_tool.fingerprint import compute_code_fingerprint`, `from plan_tool.review_persistence import compute_plan_fingerprint`, and extend an existing `from plan_tool.parser import …` (add `parse_plan`) — or add it if no such import line exists.
    - Add the `_stamp_grounding(plan_path: Path, repo_root: Path) -> Optional[Path]` helper (a sibling of `_read_seed_body`).
    - Call `_stamp_grounding(result.plan_path, repo_root)` in `cmd_create` on the happy path.
    - Call `_stamp_grounding(path, ctx.repo_root)` in `cmd_detail` inside the existing clean-productive guard.
  - `tests/cli/test_authoring_cmds.py` — new `TestStampGrounding` cases (helper-level + `main([...])` end-to-end), per the split-proof conventions already in that module.

## Implementation

### `plan_tool/cli/authoring.py` — the fail-soft helper

- **Add `_stamp_grounding(plan_path, repo_root) -> Optional[Path]`**, sited beside `_read_seed_body` / `_emit_split_proposal` (the pure-ish authoring helpers). Behavior:
  - Parse the on-disk plan: `plan = parse_plan(plan_path)`.
  - Compute both digests off the same `plan` / `plan_path` / `repo_root`:
    - `code_fp = compute_code_fingerprint(plan, plan_path, repo_root)` — the `{repo-relative-posix-path: sha256-hex}` map (`plan_tool/fingerprint.py`).
    - `plan_fp = compute_plan_fingerprint(plan_path)` — the plan-markdown-plus-`*.md`-bundle digest (`plan_tool/review_persistence.py`).
  - Write the sidecar: `return write_grounding(plan_path, plan_fingerprint=plan_fp, code_fingerprint=code_fp)` (leave `now` defaulted — production stamps wall-clock UTC; tests inject via the writer's own `now` param at the `grounding.py` layer, not here).
  - **Wrap the whole body in one `try/except Exception` that warns and returns `None`** — `warn(f"could not stamp grounding for {_short_path(plan_path, repo_root)}: {exc}")`. This is the load-bearing fail-soft boundary: parsing a freshly-authored plan, hashing its code surface, and a tracked file write are three new failure surfaces a decorative stamp introduces; defaulting any exception to "no sidecar, run stays green" preserves authoring.
- **Re-parse inside the helper, do not thread a `Plan` from the call sites.** Per the [domain-shape] fact about `cmd_detail`'s tail: `generate_detail` returns per-step `results`, not a `Plan`, and `cmd_create`'s `result` is a `CreateResult` (no parsed `Plan`). Re-parsing in one shared helper keeps both call sites a single line and single-sources the `Plan` the two digests read.

### `plan_tool/cli/authoring.py` — `cmd_create` call site

- **Call `_stamp_grounding(result.plan_path, repo_root)` on the happy path**, after the `success(f"created …")` / archive-summary cluster and before the `_print_next_steps("Next steps:", …)` block.
- **Placement covers both terminal-0 returns** — the normal `rc = 0; outcome = "ok"` return *and* the `iteration_stage_failure is not None → rc = 0; outcome = "iteration_incomplete"` return both fall *after* this line, so a plan written-but-not-fully-converged still gets a baseline (the sidecar records "examined at this code state"; the next refresh re-derives from it).
- **Structurally excluded from the no-plan paths:** the multi-plan split-proposal branch `return 0`s at the `_emit_split_proposal` block *before* this line, so a split proposal (no plan written) never stamps. The `KeyboardInterrupt` / `except Exception` paths re-raise after `_rollback_branch_collision` and never reach the stamp.
- **Emit it as its own self-contained call**, not folded into the archive/next-steps blocks — keeping it single-axis so a later step that gates or relocates grounding wraps exactly this emission ([cross-step] distinct-emission rule).

### `plan_tool/cli/authoring.py` — `cmd_detail` call site

- **Call `_stamp_grounding(path, ctx.repo_root)` as the first statement inside the next-steps guard `if rc == 0 and wrote and not args.dry_run:` (authoring.py:1196)**, before the `_print_next_steps("Next steps:", …)` block. This guard runs *after* the separate preceding `_run_completeness_tail(args, what="detail")` block (its own `if auto_completeness` condition), so the stamp lands after the completeness tail has applied.
- **After the completeness tail on purpose:** the tail applies blocking correctness/completeness findings to the plan/detail `.md` files. Stamping after it makes the stored `plan_fingerprint` reflect the *converged* plan markdown. (The completeness tail's `.md` edits do not perturb `code_fingerprint` — `compute_code_fingerprint`'s watched surface excludes the plan markdown and per-step detail files — but they do move `compute_plan_fingerprint`, so order matters for the plan digest.)
- **Reuse the existing guard, don't widen it:** `rc == 0 and wrote and not args.dry_run` is exactly the "clean, productive, files-written" gate the next-steps block already uses. The skipped-only branch (`rc == 0 and skipped and not wrote …`) and the dry-run branch fall outside it, so an "already exists" no-op run and a `--dry-run` preview write no sidecar.
- **`path` is the resolved plan path** (from `resolve_plan_for_context(ctx, args.name)` at the top of `cmd_detail`); no re-resolution needed.

### Pinned `write_grounding` seam (step 2, not yet on disk)

- **`plan_tool/grounding.py` does not exist at HEAD.** Pin the call to step 2's detail (`docs/implementation-plans/plan-details/plan-refresh-against-code/02-plan-tool-grounding-py-leaf-read-write.md`):
  - `write_grounding(plan_path, *, plan_fingerprint, code_fingerprint, now=None) -> Path` — keyword-only `plan_fingerprint` / `code_fingerprint`; derives `plan_slug` internally; returns the absolute sidecar path.
  - `grounding_path(plan_path) -> Path` → `<plan-dir>/plan-details/<slug>/grounding.json` (the path tests assert against).
  - `read_grounding(plan_path) -> Optional[Grounding]` with fields `plan_slug` / `grounded_at` / `plan_fingerprint` / `code_fingerprint` / `schema_version` (the round-trip tests read these back).
- **Confirm the seam at HEAD before wiring.** If step 2 shipped a different `write_grounding` signature (e.g. a positional `plan_slug` or a renamed kwarg), adapt this call to the real definition rather than authoring against this prose — do not invent kwargs that exist only here ([cross-step] pin-to-predecessor-detail rule).

## Tests

All cases in `tests/cli/test_authoring_cmds.py` (the declared CLI test file), under a new `TestStampGrounding` class. No claude is invoked — the `create_plan` / `generate_detail` orchestrators are patched to write a minimal plan/detail on disk (the existing suites' stub pattern), and `_stamp_grounding` then runs for real against that on-disk plan. `write_grounding` / `compute_*` run unstubbed so the assertions exercise the real sidecar.

### Test-creation order (feature step)

Author each test alongside the implementation; **every case must be green before this step is done.**

- `test_stamp_grounding_writes_sidecar` — `_stamp_grounding(plan_path, repo_root)` on a real on-disk plan returns `grounding_path(plan_path)` and the file exists.
- `test_stamp_grounding_records_current_code_fingerprint` — `read_grounding(plan_path).code_fingerprint` equals `compute_code_fingerprint(parse_plan(plan_path), plan_path, repo_root)` for the same tree.
- `test_stamp_grounding_records_plan_digest` — the stored `plan_fingerprint` equals `compute_plan_fingerprint(plan_path)`.
- `test_stamp_grounding_fail_soft_on_parse_error` — patch `parse_plan` (or `compute_code_fingerprint`) to raise; `_stamp_grounding` returns `None`, writes no sidecar, raises nothing, and warns on stderr.
- `test_main_create_stamps_grounding` — `main(["create", "demo", "--from", "an idea", "--no-iterate", "--yes"])` (orchestrator stubbed to write `1-demo.md`) leaves `grounding.json` under the plan's `plan-details/demo/` dir.
- `test_main_create_split_proposal_does_not_stamp` — a `create` whose stubbed result carries a `split_proposal` writes no `grounding.json` (no plan was written).
- `test_main_detail_stamps_grounding` — `main(["detail", "demo", "--no-iterate", …])` with a stubbed `generate_detail` returning one `written=True` result stamps `grounding.json`.
- `test_main_detail_skipped_only_does_not_stamp` — a `detail` run whose every result is an "already exists" skip (no `wrote`) writes no sidecar.
- `test_main_detail_dry_run_does_not_stamp` — `detail … --dry-run` writes no sidecar.
- `test_main_create_failure_does_not_stamp` — a `create_plan` that raises `CreateError` (existing stub) returns 1 and leaves no `grounding.json`.

## Acceptance criteria

- `_stamp_grounding` exists in `plan_tool/cli/authoring.py`, returns the sidecar `Path` on success and `None` on any exception, and never raises.
- After a successful `plan-tool create <slug>` (plan written), `grounding_path(plan_path)` exists and `read_grounding` reproduces the current `compute_code_fingerprint` map and `compute_plan_fingerprint` digest.
- After a successful productive `plan-tool detail <name>` (≥1 file written, non-dry, rc 0), the same sidecar exists and reflects the post-completeness-tail plan.
- A multi-plan split-proposal `create`, a `detail --dry-run`, a skipped-only `detail`, and a failed `create` each write **no** `grounding.json`.
- Patching the parse/compute step to raise leaves the `create`/`detail` rc unchanged (0 on the otherwise-green path) with a warning and no sidecar.
- The grounding writes go through `plan_tool/grounding.py:write_grounding` only — no new fingerprint or persistence logic is minted in `authoring.py`.

## References

- [Python Frontmatter — load/parse files with YAML front matter](https://python-frontmatter.readthedocs.io/) — how `parse_plan` splits the plan's YAML frontmatter from the body, the input `compute_plan_fingerprint` digests.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the sha256 primitives behind `compute_code_fingerprint` / `compute_plan_fingerprint` whose outputs this step persists.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — patching `create_plan` / `generate_detail` (and the raise-to-verify-fail-soft stub) to drive `main([...])` network-free.

## Deferred

- **Re-stamp after reconcile/refresh** — step 3's `plan_tool/refresh.py:refresh_plan` re-stamps after a scoped reconcile; this step only covers the first stamp at author time.
- **`cmd_split` / `create --reprocess` stamping** — `cmd_split` and `_cmd_create_reprocess` also produce/edit plan content but are out of this step's `files:`-scoped call-site work; wire them when their grounding semantics are decided (a `split` lands new steps with no code yet; `reprocess` fills `_(TODO)_` prose only).
- **Plan-digest staleness gating** — `plan_fingerprint` is stored but never gated by `check_grounding_drift` (code-axis only, per step 2); any plan-digest comparison belongs to the reconcile engine's reuse path, not here.
- **Skipping the stamp when the code map is unchanged** — this step always writes on a productive author; the "no-op leaves the tree byte-identical" optimization is step 3's refresh-gate concern, not the first stamp's.
