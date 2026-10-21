> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Fix create's manifest path to use the repo root it already resolved

## Summary

`create_plan` in `plan_tool/create.py` computes its manifest path with `mf = manifest_path or default_manifest_path()` — a bare, no-argument call that walks from the current working directory instead of using the `repo_root` parameter `create_plan` was actually called with. Every other root-sensitive call in the same function (`resolve_output_dir`, `validate_output_dir_in_repo`) already uses `repo_root` directly, so when a caller relocates `repo_root` away from cwd (as `cmd_create`'s seed-derived override does), the plan file and its manifest registration can land under two different roots from a single call. The fix is a one-line change: pass `repo_root` into `default_manifest_path(repo_root)`, which already accepts and forwards it. Everything downstream — `find_collisions`, `append_to_manifest`, and both `CreateResult(manifest_path=mf, ...)` construction sites — already flows off the corrected `mf`, so no other call site needs to change. The observable result on green: a `create_plan` call with `manifest_path=None` and a `repo_root` different from the cwd-resolved root registers the plan in that `repo_root`'s manifest, not cwd's.

## Table of Contents

- [Why](#why) — what's broken today and why it matters
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files, edits only
- [Implementation](#implementation) — the one-line fix and why nothing else needs to change
- [Tests](#tests) — the coverage gap and the new test to add
- [Acceptance criteria](#acceptance-criteria) — observable behaviors to check
- [References](#references) — relevant docs
- [Deferred](#deferred) — what the rest of the plan covers instead

## Why

`create_plan` (`plan_tool/create.py`) takes `repo_root` as an explicit parameter and uses it consistently for `resolve_output_dir(repo_root, ...)` and `validate_output_dir_in_repo(output_dir, repo_root)` — both calls sit just above the manifest-path line. But the very next line, `mf = manifest_path or default_manifest_path()`, calls `default_manifest_path()` with no argument. Per its own docstring (`plan_tool/locator.py:default_manifest_path`), omitting `repo_root` makes it re-derive a root by walking up from `Path.cwd()` — a completely independent resolution from the `repo_root` the function was actually given. In the common case cwd and `repo_root` agree, so the bug is invisible. But `cmd_create` (`plan_tool/cli/authoring.py`) can relocate `repo_root` away from cwd when a `--from-existing` seed's body references files under a different `.git` ancestor, and when it does, this call silently re-resolves the *original* cwd-derived root instead of honoring the relocation — so the plan file (written under the relocated root via `output_dir`) and its manifest entry (written under the stale cwd root) end up split across two different repos. That's the bug this plan exists to fix, and this step fixes it at its source.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — change the `mf = manifest_path or default_manifest_path()` assignment inside `create_plan` (just after `validate_output_dir_in_repo(output_dir, repo_root)`, before `find_collisions(...)` is called) to pass `repo_root` through.
  - `tests/test_create.py` — add coverage for the `manifest_path=None` + relocated-`repo_root` case, which the existing suite doesn't exercise (see [Tests](#tests)).

## Implementation

- **The fix is scoped to one assignment.** Change `mf = manifest_path or default_manifest_path()` to `mf = manifest_path or default_manifest_path(repo_root)`, using the same `repo_root` local that `resolve_output_dir`/`validate_output_dir_in_repo` already consumed a few lines above. `default_manifest_path(repo_root: Optional[Path] = None)` (`plan_tool/locator.py`) already accepts and forwards a `repo_root` argument — when given one it returns `repo_root / ".plan-tool" / "plans.json"` directly and skips its own `find_repo_root_from_cwd()` walk entirely. No locator-side change is needed; this step is purely the caller passing the argument it already has in scope.
- **Explicit `--manifest` callers are unaffected.** The `manifest_path or default_manifest_path(repo_root)` short-circuit means any caller that already supplies `manifest_path` (which is most of the existing test suite and every CLI invocation with `--manifest`) keeps using that path unchanged — only the `manifest_path is None` fallback branch changes behavior.
- **Nothing downstream of `mf` needs touching.** Every other use of the manifest path inside `create_plan` already reads from the `mf` local, so fixing its one source assignment propagates automatically:
  - `find_collisions(output_dir, slug, manifest_path=mf, repo_root=repo_root)`
  - `append_to_manifest(mf, repo_root, plan_path)`
  - the normal-completion `return CreateResult(..., manifest_path=mf, ...)`
  - the multi-plan split-proposal short-circuit `return CreateResult(plan_path=None, manifest_path=mf, ...)` (the early return inside the distill-first-pass branch) — this path gets the fix too, for free, since it reads the same `mf`.
- **Don't widen scope to the relocation logic itself.** `cmd_create`'s seed-derived override (`find_umbrella_root`, `plan_tool/cli/authoring.py`) is what decides *whether* `repo_root` gets relocated in the first place — that logic is untouched here. This step treats `repo_root` as an opaque, already-resolved value handed to `create_plan`; it doesn't matter to this fix *how* the caller arrived at it.
- **Don't thread the result further downstream.** Propagating the create-resolved root into `direct_cmd.py`'s later pipeline stages (detail, completeness-apply, jira/run) is step 2's job, via `CreateResult.manifest_path`/`plan_path`, which this step makes trustworthy. Nothing in `direct_cmd.py` is in scope here.

## Tests

The existing suite almost never exercises the buggy branch: nearly every `create_plan(...)` call in `tests/test_create.py` already passes an explicit `manifest_path=`, which short-circuits before `default_manifest_path()` is ever invoked. The one call that omits it (`test_invalid_slug_rejected_before_prompts`, `tests/test_create.py:668`) raises `CreateError` on an invalid slug before execution reaches the manifest-path line at all — so no test today calls `default_manifest_path()` for real with a `repo_root` that diverges from cwd. That gap is exactly what let this bug through.

### Test-creation order (feature step)

Add the new test to `TestCreatePlanBlankSkeleton` (`tests/test_create.py:607`), modeled on its existing `test_happy_path` (`tests/test_create.py:622`) — same blank-skeleton input flow, and it inherits the class's autouse `_stub_propose_references` fixture so nothing shells out.

- `test_manifest_lands_under_repo_root_not_cwd` — set up two independent project roots under `tmp_path` (each with its own `.git` marker: one as the simulated cwd, one as `repo_root`), `monkeypatch.chdir` into the cwd root, call `create_plan("demo", repo_root=<the other root>, output_dir_override=<a dir under that root>, manifest_path=None, input_fn=_queue_input(_basic_metadata_answers() + _single_step_answers()))`, and assert `result.manifest_path == repo_root / ".plan-tool" / "plans.json"`, that the manifest file exists there (not under the cwd root), and that `result.plan_path` is also under `repo_root` — pinning that plan file and manifest entry now agree on the same root even when it differs from cwd. This is the regression test for the bug described in [Why](#why).

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `create_plan` called with `manifest_path=None` and a `repo_root` that differs from the cwd-resolved project root writes the manifest entry under that `repo_root`, not the cwd-derived one.
- `CreateResult.manifest_path` reflects the same `repo_root`-derived path on both the normal-completion return and the split-proposal short-circuit return.
- Callers that pass an explicit `manifest_path` see no behavior change — the fix touches only the `manifest_path is None` fallback.
- `test_manifest_lands_under_repo_root_not_cwd` (new) passes, and `uv run pytest tests/test_create.py -q` stays green.

## References

- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path.resolve()` and path equality are what the new test relies on to assert the manifest landed under the correct root rather than cwd's.

## Deferred

- Threading the create-resolved root into `direct_cmd.py`'s downstream stage namespaces (`_stage_namespace`'s `repo_root` field) — step 2, depends on this step.
- The relocated-root cleanliness guard before the first post-create commit — step 3.
- End-to-end `direct-jira`/`direct-run` tests that drive a seed causing relocation — step 4.
- Removing the `BUG_BACKLOG.md` entry this plan closes — step 5, once the whole plan ships.
- The same stale-manifest-path pattern in `plan_tool/cli/manifest.py` (register/deregister/sweep) and `plan_tool/cli/inspect.py` (list) — step 6, depends on this step.
