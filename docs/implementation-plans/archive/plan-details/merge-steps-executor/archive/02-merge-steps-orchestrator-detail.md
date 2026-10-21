> **Auto-archived**: this plan was swept on 2026-06-19 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add `merge_steps` orchestrator + `_merge_is_safe`, `_migrate_downstream_details_after_merge`, `_confirm_merge`, `MergeResult` to `detail.py`

## Summary

Add the deterministic, operator-driven merge orchestrator `merge_steps` to `plan_tool/detail.py` beside `split_step`, plus its four supporting symbols — the `_merge_is_safe` run-state gate, the `_migrate_downstream_details_after_merge` detail-file mover, the `_confirm_merge` TTY prompt, and the frozen `MergeResult` dataclass. `merge_steps` is the structural inverse of `split_step`: it folds a contiguous, dependency-connected set of step ids into one by reusing step 1's pure `plan_tool/create._apply_step_merge` transform, renumbers the survivors, renames/removes the affected detail files, and re-authors a single combined detail body through the existing seven-section authoring path. The load-bearing decision is the detail-file asymmetry — split *creates* files, merge *combines and removes* them: member bodies are captured into a deterministic concatenation written as the merged step's seed body, and the downstream rename walks ids **ascending** (the inverse of split's descending walk) because the merge shift is **downward**. On green, `merge_steps` on a clean pending plan returns a `MergeResult` whose `merged_id` is the survivor (lowest) id, with the folded-away detail files gone, downstream detail files renamed to their new ids, and a coherent re-authored detail file on disk.

## Table of Contents

- [Why](#why) — the missing inverse of the split orchestrator
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — `merge_steps`, the three helpers, `MergeResult`, and the detail-combination design
- [Tests](#tests) — unit cases in `tests/test_detail.py` and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — stdlib/test docs relevant to this orchestrator
- [Deferred](#deferred) — the CLI command, completeness loop, and richer combination left to later steps

## Why

`plan_tool/detail.py:split_step` is the full deterministic split engine — it reuses `create._apply_step_split`, gates on `_split_is_safe`, migrates downstream detail files via `_migrate_downstream_details_after_split`, and re-authors the new halves through `generate_detail`. Merge has only its lowest layer: step 1's pure `create._apply_step_merge` transform exists, but nothing wires it to disk. This step builds the orchestration layer — the mirror of `split_step` — so an over-decomposed plan can actually be folded back: validate the set is mergeable and run-safe, apply the transform, reconcile the detail files on disk (the part split and merge diverge on), and produce one coherent merged detail file. The CLI verb that drives it (`plan-tool merge`) and the completeness loop land in step 3 (`depends_on: 2`); this step is the engine the command calls.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — add `MergeResult`, `merge_steps`, `_merge_is_safe`, `_migrate_downstream_details_after_merge`, `_confirm_merge`, `_merge_renumber_map`, and `_combine_detail_bodies`. Place each beside its split sibling (`MergeResult` after `SplitResult`; `merge_steps` after `split_step`; `_merge_is_safe` after `_split_is_safe`; `_migrate_downstream_details_after_merge` after `_migrate_downstream_details_after_split`; `_confirm_merge` after `_confirm_split`; `_merge_renumber_map` after `_split_renumber_map`). No new module-level imports — `Step`/`StepStatus`/`Plan`, `parse_plan`/`write_plan`, `IterativeBudget`, `ProgressReporter`, `RunLogWriter`, the `_repo_relative`/`_archive_existing_detail`/`_DETAIL_ID_PREFIX_RE`/`derive_detail_path`/`update_step_detail_field` helpers, and `generate_detail` are all already defined/imported in this module. `create._apply_step_merge` is imported **body-locally** inside `merge_steps` (mirror `split_step`'s `from plan_tool.create import ...` lazy import that dodges the create↔detail cycle).
  - `tests/test_detail.py` — add `class TestMergeStepsOnDemand` mirroring `TestSplitStepOnDemand`, plus a `_MERGE_PLAN_PENDING` fixture and a `_MERGE_PLAN_RUN_STARTED` fixture. Import the new symbols (`merge_steps`, `MergeResult`, `_merge_is_safe`, `_migrate_downstream_details_after_merge`, `_confirm_merge`) where the tests use them, matching the file's existing local-import style for split (`from plan_tool.detail import split_step`).

## Implementation

### Consumer-before-dependency note (read first)

- **Step 1 (`create._apply_step_merge`) is unimplemented at HEAD** — only `create._apply_step_split` exists. Pin the transform's contract to step 1's detail (`docs/implementation-plans/plan-details/merge-steps-executor/01-apply-step-merge-pure-transform-merge.md`): signature `_apply_step_merge(steps: list[Step], merge_ids: list[int], merged: Step) -> list[Step]`; sets only the merged step's `id` and `depends_on`; raises `create.CreateError` on a non-contiguous / fork-join / unknown-id / cycle-producing set; on a canonical plan the survivor's new id is `lo = min(merge_ids)` and steps after `hi = max(merge_ids)` shift down by `eliminated = hi - lo`.
- **Confirm the seam at HEAD before wiring.** If step 1 shipped a different signature or error type, adapt the call/`except` arm to the real symbol rather than this prose. Wrap its `CreateError` into `DetailError` exactly as `split_step` wraps `_apply_step_split`'s.

### `plan_tool/detail.py` — `MergeResult`

- **Mirror `SplitResult`** (frozen dataclass). Fields:
  - `merged_id: int` — survivor (lowest) id the set folded into.
  - `merged_title: str` — the merged step's final title.
  - `original_ids: list[int]` — the pre-merge ids that were folded (sorted).
  - `original_titles: list[str]` — those steps' titles, in id order.
  - `detail_results: list[DetailResult]` — the merged step's re-authoring outcome; empty when `author_details=False` or `dry_run=True`.
  - `dry_run: bool = False`.
  - `renumber: list[tuple[int, int]] = field(default_factory=list)` — `(old_id, new_id)` for every pre-merge step; populated only on a `dry_run` preview.
  - `new_plan: list[tuple[int, str, list[int]]] = field(default_factory=list)` — post-merge `(id, title, depends_on)` rows; populated only on `dry_run`.
- **Per-arm field matrix** (state in the docstring): `renumber`/`new_plan` populated **only** on `dry_run=True`; `detail_results` populated **only** on a real run with `author_details=True`. A real run leaves `renumber`/`new_plan` empty; a dry run leaves `detail_results` empty.

### `plan_tool/detail.py` — `_merge_is_safe`

- **Signature:** `def _merge_is_safe(plan: Plan, merge_ids: list[int]) -> tuple[bool, list[int]]:` — returns `(safe, blocking_ids)`, mirroring `_split_is_safe`'s shape.
- **Gate the SET, not downstream.** Merge rewrites the merged steps themselves, so refuse if **any** member is non-`PENDING`:
  ```
  members = set(merge_ids)
  blocking = sorted(s.id for s in plan.steps if s.id in members and s.status != StepStatus.PENDING)
  return (not blocking, blocking)
  ```
- **Contrast with split** (state in the docstring): `_split_is_safe` blocks on any step `>= target_id` that is non-PENDING (renumbering orphans downstream run state); `_merge_is_safe` blocks only on the **merged set's own** non-PENDING members. A parked (`scope: deferred`/`wont_do`) member is still `PENDING` and merges cleanly, same as split.

### `plan_tool/detail.py` — `_migrate_downstream_details_after_merge`

- **Signature:** `def _migrate_downstream_details_after_merge(new_steps: list[Step], *, repo_root: Path, member_old_ids: list[int], eliminated: int) -> None:` — mutates `new_steps` detail pointers in place, mirroring `_migrate_downstream_details_after_split`.
- **Two responsibilities (split has only the second):**
  1. **Remove the folded-away member detail files.** The caller captures member bodies *before* calling this (see `merge_steps`); here, archive each member's pre-merge on-disk detail file via `_archive_existing_detail` so the merged step's slot is clean. The survivor's own canonical file is rewritten fresh during re-authoring, so archiving all member files here is correct — none carry forward unrenamed.
  2. **Rename downstream files into the freed slots.** Downstream = steps whose **new** id is below their pre-merge id (the shifted-down survivors). Rename each `{old:02d}-<slug>.md` → `{new:02d}-<slug>.md` (slug preserved verbatim from the on-disk name via `_DETAIL_ID_PREFIX_RE`) and repoint `step.detail`.
- **Walk ids ASCENDING (the load-bearing inverse of split).** Split renames **high→low** because it shifts ids **up** (a low step's new file must not clobber the next step's not-yet-moved file). Merge shifts ids **down**, so a step's new (lower) id targets a slot a *lower-numbered* downstream step has already vacated — rename **low→high** so each target slot is free when reached. Renaming descending here would clobber a not-yet-moved lower step's file.
- **Clobber/missing tolerance:** best-effort per step, mirroring the split helper — a member or downstream source file that is missing or lacks an `NN-` prefix repoints the pointer without a move; `_archive_existing_detail` is the archive-on-collision guard.
- **Computing the downstream set:** a step is downstream iff its new id `< its old id`. Since `merge_steps` re-parses to map old→new (the survivor carries `merged_id`, members are gone), pass `member_old_ids` + `eliminated` so the helper can identify members (skip — already archived) vs shifted survivors (rename). State the old-id source explicitly: the helper receives `new_steps` (post-transform) and the old-id context as kwargs, since a post-transform `Step` no longer carries its pre-merge id.

### `plan_tool/detail.py` — `_confirm_merge`

- **Signature:** `def _confirm_merge(prompt_fn: Callable[[str], str], *, steps: list[Step], merged_title: str) -> bool:` — mirror `_confirm_split`.
- **Default NO; non-TTY auto-declines** (`if not sys.stdin.isatty(): return False`). A structural plan edit never happens without explicit assent.
- **Prompt body:** list the merged set (`Step N (title)`) and the resulting `merged_title`, ending `Apply this merge and re-author the combined detail? [y/N]`. Accept `{"y", "yes"}`.

### `plan_tool/detail.py` — `_combine_detail_bodies`

- **Signature:** `def _combine_detail_bodies(captured: list[tuple[int, str, str]]) -> str:` — `(old_id, title, body)` per member in id order; returns one markdown blob.
- **Deterministic concatenation, not a staple.** For each member, drop its leading H1 line, prepend a `## Merged from step {old_id} — {title}` separator, and join with blank lines. This is the **seed** body: always written (even with `author_details=False`), and the starting point a re-author refines.
- **Pure, I/O-free, no Claude** — reads nothing; the caller passes already-read bodies. Members with no detail file contribute nothing (filtered by the caller).

### `plan_tool/detail.py` — `_merge_renumber_map`

- **Signature:** `def _merge_renumber_map(old_steps: list[Step], merge_ids: list[int]) -> list[tuple[int, int]]:` — mirror `_split_renumber_map`, preview-only for `dry_run`.
- On a canonical plan: members all map to `lo`; steps `< lo` keep their id; steps `> hi` map to `id - eliminated`. The real renumber is `_apply_step_merge`'s dict; this is the preview echo.

### `plan_tool/detail.py` — `merge_steps`

- **Signature:**
  ```
  def merge_steps(
      plan_path: Path, *, merge_ids: list[int], title: Optional[str] = None,
      repo_root: Path, author_details: bool = True, dry_run: bool = False,
      invoker: DetailInvoker = shell_detail_invoker,
      reporter: Optional[ProgressReporter] = None,
      run_logger: Optional[RunLogWriter] = None,
      prompt_fn: Optional[Callable[[str], str]] = None,
      budget: IterativeBudget = IterativeBudget(enabled=False),
  ) -> MergeResult:
  ```
  The deterministic, operator-driven counterpart to the reactive Phase-B split — the caller names the set and (optionally) the merged title, typically to act on a `granularity-merge` finding.
- **Pre-flight validation (raise `DetailError`, no I/O before the transform):**
  - `len(set(merge_ids)) < 2` → `DetailError("merge needs at least two step ids")` (mirror `split_step`'s two-title guard).
  - **Canonical-numbering refusal:** re-use `split_step`'s exact check — `[s.id for s in plan.steps] != list(range(1, len(plan.steps)+1))` → `DetailError("cannot merge … step ids are not canonical …")`. The renumber + migration primitives equate id with position.
  - **All ids exist:** any id in `merge_ids` absent from the plan → `DetailError(f"step {missing} not found in {plan_path.name}")`.
  - **`_merge_is_safe`:** `safe, blocking = _merge_is_safe(plan, merge_ids)`; if not safe → `DetailError(f"cannot merge step(s) {blocking}: already run/started, so merging would restructure completed work — restructure via re-plan instead")`.
  - Contiguity + dependency-connectivity are enforced inside `_apply_step_merge`; let its `CreateError` raise and wrap it (`except CreateError as exc: raise DetailError(f"merge failed: {exc}") from exc`). No I/O happens before the transform, so the acceptance criterion "contiguity + chain validated before any I/O" holds.
- **Assemble the merged `Step`** (the transform sets only `id`/`depends_on`; everything else comes from here):
  - `title`: the `title` arg if given, else `" + ".join(member_titles)` derived from the set's titles in id order. Note the chosen default explicitly — a derived title keeps the merge self-describing without forcing the caller to name it.
  - `files`: order-preserving dedup of each member's `files`; `creates`: same over each member's `creates`. Use the `list(dict.fromkeys(...))` idiom (cite step 1's external-edge dedup for the same idiom).
  - `change_type`: the common member `change_type` if uniform, else `ChangeType.FEATURE` (the more general — a mixed-type fold is a feature). `complexity`: the highest member complexity (folding raises complexity).
  - `detail=None` (set after the combined body is written).
- **Compute `lo`/`hi`/`eliminated`** from `merge_ids` (`lo=min`, `hi=max`, `eliminated=hi-lo`); `merged_id = lo` on a canonical plan.
- **Capture member bodies BEFORE mutation:** for each member with a `detail` pointer whose file exists, read the body into `captured: list[(old_id, title, body)]` in id order. This must precede the transform/migration, which removes those files.
- **`dry_run=True`:** return early with the preview — no write, no rename, no authoring:
  ```
  return MergeResult(
      merged_id=merged_id, merged_title=merged.title,
      original_ids=sorted(merge_ids),
      original_titles=[<member titles in id order>],
      detail_results=[], dry_run=True,
      renumber=_merge_renumber_map(plan.steps, merge_ids),
      new_plan=[(s.id, s.title, list(s.depends_on)) for s in new_steps],
  )
  ```
  Build `new_steps` via `_apply_step_merge` first so the preview reflects the real rewire (mirrors `split_step` computing `new_steps` before the `dry_run` branch).
- **Real run, in order:**
  1. `new_steps = _apply_step_merge(plan.steps, merge_ids, merged)` (wrap `CreateError`).
  2. `_migrate_downstream_details_after_merge(new_steps, repo_root=repo_root, member_old_ids=sorted(merge_ids), eliminated=eliminated)` — archives folded-away member files, renames downstream files ascending, repoints pointers.
  3. `write_plan(plan_path, plan.model_copy(update={"steps": new_steps}))`.
  4. **Write the combined seed body:** compute `derive_detail_path` for the merged step (id `merged_id`), write `_combine_detail_bodies(captured)` to it, and `update_step_detail_field(plan_path, merged_id, <rel>)` so the pointer is set before re-authoring.
  5. **Re-author (`author_details=True`):** `generate_detail(plan_path, repo_root=repo_root, step_id=merged_id, force=True, invoker=invoker, reporter=reporter, resume=False, prompt_fn=prompt_fn, run_logger=run_logger, budget=budget, allow_split=False)` — re-authors the merged step from its union-of-files into one coherent seven-section body, archiving the seed via `_archive_existing_detail` and sweeping same-prefix orphans. Mirror `split_step`'s authoring call shape (`force=False` there because the halves are detail-less; here `force=True` because the seed already occupies the path).
  6. Return `MergeResult(merged_id, merged.title, sorted(merge_ids), member_titles, detail_results, dry_run=False)`.
- **Load-bearing combination decision (state explicitly; the create prose admits several readings):**
  - **Chosen:** deterministic concatenation (`_combine_detail_bodies`) is the durable combined body; when `author_details`, re-author **fresh from the merged step's union-of-files** (the source of truth), exactly as `split_step` authors each half fresh from *its* files rather than seeding from the parent body. The seven-section gate (`parse_detail_response`) validates the result. This reuses `generate_detail` with zero new surface and keeps merge invariant-symmetric with split.
  - **Rejected/deferred:** feeding the concatenated predecessor bodies *into* the authoring prompt (a `generate_detail` seed param or a `sibling_details` injection) — a richer "semantic merge of the prior prose" that needs a new `generate_detail` parameter; out of this step's scope. Without it, the concatenation is still what `--no-detail` leaves and the seed a re-author starts from on disk.
- **Body-local import** of `_apply_step_merge` (and `CreateError`) inside `merge_steps`, citing the cycle proof: `create.py` top-imports nothing from `detail.py` at call time, but `detail.py` would close a cycle importing `create` at module top (mirror the existing `split_step` lazy import comment).

### Foundational logic / shared call sites

- **Foundational rule:** "fold a contiguous run-safe step set into one and reconcile its detail files on disk." The structural fold is single-sourced in step 1's `create._apply_step_merge`; the run-state gate idiom is single-sourced here as `_merge_is_safe` (sibling of `_split_is_safe`); the canonical-numbering precondition and the `_DETAIL_ID_PREFIX_RE`-based rename are reused from the split helpers — **do not** re-implement them.
- **Detail-rename duplication (Deferred — consolidation reconcile can pick up):** `_migrate_downstream_details_after_merge` and `_migrate_downstream_details_after_split` share the per-file `_DETAIL_ID_PREFIX_RE` rename + archive-on-clobber loop, differing only in walk direction (ascending vs descending) and the extra member-removal pass. Folding them into one direction-parametrized helper is a cross-cutting refactor `detail` cannot mint — route to `## Deferred`, keep two siblings for now.

## Tests

All cases live in a new `class TestMergeStepsOnDemand` in `tests/test_detail.py`, mirroring `TestSplitStepOnDemand`. Use a `_MERGE_PLAN_PENDING` fixture (≥4 contiguous PENDING steps with detail files on disk) and a `_MERGE_PLAN_RUN_STARTED` fixture (a member with non-PENDING status). Stub Claude via `invoker=lambda _p: _GOOD_BODY` (the existing seven-section fixture body) and `prompt_fn=lambda _m: "n"`; the autouse `_stub_lessons_extraction` fixture already neutralizes lesson extraction.

- `test_merges_renumbers_and_reauthors` — merging `{2,3}` in a 4-step chain returns `merged_id == 2`, `original_ids == [2, 3]`; the plan has 3 steps with contiguous ids; the merged step's detail file exists and is non-empty.
- `test_downstream_ids_shift_down_and_files_renamed` — old step 4 becomes id 3; its detail file is renamed `04-…` → `03-…` and the pointer matches.
- `test_folded_away_detail_files_removed` — the non-survivor member's pre-merge detail file no longer exists at its old path (archived under `archive/`).
- `test_merged_depends_on_is_external_union` — the merged step's `depends_on` is the remapped union of the set's external deps; an intra-set edge is absent (asserts the step-1 transform is wired, not re-derived).
- `test_merged_step_inherits_union_of_files` — the merged step's `files`/`creates` are the order-preserving dedup'd union of members'.
- `test_requires_at_least_two_ids` — `merge_ids=[2]` raises `DetailError(match="at least two")`.
- `test_unknown_id_raises` — an id absent from the plan raises `DetailError(match="not found")`.
- `test_non_contiguous_set_raises_and_no_mutation` — `{2,4}` raises `DetailError` (wrapped `CreateError`) and the plan/detail files are unchanged.
- `test_fork_join_set_raises` — a contiguous but unconnected set raises `DetailError`.
- `test_non_canonical_ids_refused` — a gapped/hand-edited plan raises `DetailError(match="not canonical")`.
- `test_run_started_member_refused_by_merge_is_safe` — a set containing a non-PENDING member raises `DetailError(match="already run")` before any mutation (plan + files byte-identical).
- `test_merge_is_safe_gates_set_not_downstream` — drive `_merge_is_safe` directly: a non-PENDING step *outside* the set does not block; a non-PENDING *member* does, and `blocking_ids` names it.
- `test_dry_run_previews_without_mutation` — `dry_run=True` returns a `MergeResult` with `renumber`/`new_plan` populated and `detail_results == []`, and the plan + every detail file are unchanged on disk.
- `test_no_detail_leaves_combined_seed` — `author_details=False` leaves the deterministic `_combine_detail_bodies` concatenation as the merged step's detail (both members' section markers present) and makes no Claude call (pass an `invoker` that raises, assert it never fires).
- `test_confirm_merge_non_tty_declines` — `_confirm_merge` returns `False` when stdin is not a TTY (monkeypatch `sys.stdin.isatty`).
- `test_migrate_ascending_avoids_clobber` — drive `_migrate_downstream_details_after_merge` on a fixture where a descending walk would clobber: assert every downstream file lands at its new id with content intact.
- `test_combine_detail_bodies_drops_h1_and_separates` — unit-drive `_combine_detail_bodies`: each member body's leading `#` H1 is dropped and a `## Merged from step N` separator precedes it.
- `test_merge_result_field_matrix` — a real run leaves `renumber`/`new_plan` empty; a dry run leaves `detail_results` empty (guards the documented per-arm matrix).

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write each `TestMergeStepsOnDemand` case **with** the symbol it covers (`merge_steps` and its helpers). Green-before-done gate: every new case must pass (`uv run pytest tests/test_detail.py::TestMergeStepsOnDemand -q`) **and** the existing `tests/test_detail.py` suite must stay green before this step is complete.

## Acceptance criteria

- `merge_steps`, `_merge_is_safe`, `_migrate_downstream_details_after_merge`, `_confirm_merge`, `_merge_renumber_map`, `_combine_detail_bodies`, and `MergeResult` exist in `plan_tool/detail.py`, each beside its split sibling.
- `merge_steps` with `merge_ids` of fewer than two ids, an unknown id, a non-canonical plan, a non-contiguous set, a fork/join set, or a run-started member each raise `DetailError`; the non-contiguous/fork-join/run-started cases mutate neither the plan nor any detail file.
- Merging a contiguous, dependency-connected, all-PENDING set folds it into the survivor (`merged_id == min(merge_ids)`), renumbers remaining ids to contiguous `1..N`, and the merged step's `depends_on` is the remapped external union with intra-set edges dropped.
- Folded-away member detail files are removed (archived); downstream detail files are renamed to their new (lower) ids with pointers repointed; the rename is clobber-free.
- `author_details=True` re-authors the merged step into one detail file passing the seven-section gate; `author_details=False` leaves the deterministic combined seed and spawns no Claude call.
- `_merge_is_safe` returns `(False, [member_ids])` for a non-PENDING member and `(True, [])` when only non-members are non-PENDING.
- `dry_run=True` returns a `MergeResult` with `renumber`/`new_plan` populated and `detail_results` empty, mutating nothing on disk.
- `merge_steps` returns a `MergeResult` mirroring `SplitResult`'s shape.
- No new import cycle: `create._apply_step_merge` is imported body-locally inside `merge_steps`.
- `uv run pytest tests/test_detail.py -q` is green, including `TestMergeStepsOnDemand`.

## References

- [dataclasses — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Reference for the frozen `MergeResult` mirroring `SplitResult`, including `field(default_factory=list)` for the preview-only fields.
- [argparse — Python documentation](https://docs.python.org/3/library/argparse.html) — Background for the `--steps`/`--title`/`--no-detail` surface that step 3's `cmd_merge` will pass into `merge_steps`; not edited here, but it pins the kwargs this orchestrator must accept.
- [How to use temporary directories and files in tests — pytest](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — The hermetic `tmp_path` pattern these orchestrator tests use to build a plan + detail files on disk and assert renames/removals.

## Deferred

- `plan-tool merge` CLI command, `--steps`/`--title`/`--no-detail`/`--no-completeness`/`--iterate`/`--dry-run` parsing, and subparser registration — step 3 (`plan_tool/cli/authoring.py:cmd_merge`), `depends_on: 2`.
- The conceptual completeness audit loop + `apply_finding` convergence under `--iterate`, and the `reconcile-plan` follow-up next-step pointer — step 3's `cmd_merge` (the mirror of `cmd_split` + `_run_completeness_tail`), not `merge_steps` itself.
- Feeding the concatenated predecessor bodies *into* the re-authoring prompt (a `generate_detail` seed param / `sibling_details` injection) for a richer semantic merge — needs a new `generate_detail` surface; out of scope. The deterministic `_combine_detail_bodies` concatenation is the durable body in the interim.
- Consolidating `_migrate_downstream_details_after_merge` and `_migrate_downstream_details_after_split` into one direction-parametrized helper — a cross-cutting refactor for `reconcile`, not mintable by `detail`.
- `PLAN_FORMAT.md` / `RUNBOOK.md` / `docs/cli/` documentation of `merge` — steps 3–4.
- A `--dry-run` rich before/after step-graph diff renderer — the no-write preview path exists; the graph-diff view is postponed.
