> **Auto-archived**: this plan was swept on 2026-06-19 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add `merge_steps` orchestrator (`_merge_is_safe`, `_migrate_downstream_details_after_merge`, `_confirm_merge`, `MergeResult`) to `detail.py`

## Summary

Add the merge orchestrator to `plan_tool/detail.py` as the structural inverse of `split_step`, reusing step 1's pure `create._apply_step_merge` transform exactly as `split_step` reuses `create._apply_step_split`. Ships four new symbols beside their split siblings: `_merge_is_safe` (run-state gate over the **merged set and every step after the merged region**), `_migrate_downstream_details_after_merge` (renames downstream detail files **down** by the eliminated count), `_confirm_merge` (TTY yes/no, default NO), and the `MergeResult` dataclass. The load-bearing design decision is to treat `split_step` as a **shape/sequence template only** — every index direction inverts (downstream ids shift *down*, migration processes *low→high*) and detail-file handling is *combine-then-re-author*, not *create*. On green, calling `merge_steps` on a contiguous all-PENDING chain folds it to one step, renumbers survivors to contiguous `1..N`, re-authors one coherent merged detail file — fed each folded member's **full prior body** through a dedicated `$prior_body` placeholder (no lossy truncation), not the `_MAX_PROMPT_FILE_BYTES`-truncated sibling seam — through the existing seven-section gate, archives the folded-away files, and returns a populated `MergeResult`; an unsafe (run-started) or malformed set raises `DetailError` before any disk mutation.

## Table of Contents

- [Why](#why) — the executor needs an orchestrator + safety/migration layer above the pure transform
- [Files (creates vs edits)](#files-creates-vs-edits) — the files this step touches
- [Implementation](#implementation) — `_merge_is_safe`, `_migrate_downstream_details_after_merge`, `_confirm_merge`, `MergeResult`, `merge_steps`
- [Tests](#tests) — unit cases in `tests/test_detail.py` and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — stdlib/test docs for this step's surfaces
- [Deferred](#deferred) — CLI, completeness loop, prompt-seam, and the migrate-helper consolidation

## Why

Step 1 ships `create._apply_step_merge` — a pure list→list fold with no I/O, no detail-file handling, and no run-state gate. It cannot be driven from anything: there is no safety check, no detail-file combination/migration, and no result object. `split_step` (`plan_tool/detail.py`) is the proven counterpart for the forward direction — it wraps `_apply_step_split` with `_split_is_safe`, `_migrate_downstream_details_after_split`, `_confirm_split`, and `SplitResult`, then re-authors the new halves. This step builds the symmetric wrapper for merge so step 3's `plan-tool merge` CLI has a single orchestrator to call, exactly as `cmd_split` calls `split_step`. Keeping the orchestrator in `plan_tool/detail.py` (beside `split_step`) and the transform in `plan_tool/create.py` (beside `_apply_step_split`) preserves the existing `create`↔`detail` layering — `merge_steps` lazily imports `_apply_step_merge` from `create` inside the function body, mirroring `split_step`'s `from plan_tool.create import (...)` to avoid the import cycle.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — add `_merge_is_safe`, `_migrate_downstream_details_after_merge` (reusing the existing module-level `_DETAIL_ID_PREFIX_RE`), `_confirm_merge`, the `MergeResult` dataclass, and the `merge_steps` orchestrator, all placed immediately after the existing split cluster (`_split_is_safe` → `split_step` → `_split_renumber_map`). No edits to existing split symbols. Lazily import `_apply_step_merge` (and `CreateError`) from `plan_tool.create` inside `merge_steps`, mirroring `split_step`'s in-body import. Thread the merged members' **full prior bodies** into the re-author by adding a `prior_body` kwarg to `render_detail_prompt` (substituting a new `${prior_body_block}` placeholder) and to `generate_detail`, so `merge_steps` can pass the concatenated member bodies untruncated (the load-bearing combine mechanism, replacing the lossy sibling seam).
  - `plan_tool/prompts/detail.md` — add a `${prior_body_block}` placeholder section (e.g. "### Prior detail bodies being merged (combine these into one coherent file)") that receives the folded members' complete seven-section bodies verbatim, distinct from the existing tone/structure-only `${sibling_details_block}`. Inert (empty) for non-merge `generate_detail` calls. **Stale-guidance note:** the earlier lesson that Deferred this placeholder and reused the truncating sibling-glob seam is superseded — the dedicated `$prior_body`/`${prior_body_block}` placeholder is in scope for this step and is the load-bearing combine mechanism.
  - `tests/test_detail.py` — add `TestMergeIsSafe`, `TestMigrateDownstreamDetailsAfterMerge`, `TestConfirmMerge`, and `TestMergeSteps` classes; extend the top-of-file `from plan_tool.detail import (...)` block to import `merge_steps`, `_merge_is_safe`, `_migrate_downstream_details_after_merge`, `_confirm_merge`, and `MergeResult`. Include a `TestMergeSteps` case asserting a refactor+feature fold yields a single `change_type=feature` step (dominant-type rule) — **no** `type_impure` field is read or written.

## Implementation

### `merge_steps` consumes step-1's seam — confirm the shape at HEAD first

- **Step 1 is `depends_on: 1` and unimplemented at HEAD.** Pin the consumed seam to step 1's detail (`docs/implementation-plans/plan-details/merge-steps-executor/01-apply-step-merge-pure-transform-merge.md`): signature `_apply_step_merge(steps: list[Step], merge_ids: list[int], merged: Step) -> list[Step]`, raising `create.CreateError` on `<2` ids / unknown id / non-contiguous / fork-join / cycle, and **never mutating** `steps` or `merged`.
- **Confirm the seam at HEAD before wiring.** If step 1 shipped a divergent name/arity, adapt the call to the real seam rather than this prose. Do **not** author against fields that exist only here.

### Index direction — every axis inverts split (load-bearing)

- **Downstream ids shift DOWN, not up.** A merge eliminates `eliminated = len(set) - 1` steps, so every step after the merged region renumbers *down* by `eliminated`. Step 1's renumber map is authoritative (`steps > hi` → `id - eliminated`), and the plan's own split/merge comparison table row reads "Edges after the region shift **down** by `len-1`".
- **Migration processes LOW→HIGH** (split processes high→low). Because downstream ids *decrease*, rename the lowest downstream step first — into the slot freshly vacated by the fold — so a rename never clobbers a not-yet-moved lower step's file. This is the exact inverse of `_migrate_downstream_details_after_split`'s high→low ordering.

### `_merge_is_safe(plan: Plan, merge_ids: list[int]) -> tuple[bool, list[int]]`

- **Gate the merged set AND every step after the merged region.** Mirror `_split_is_safe`'s body, blocking on both the folded members and the downstream steps a merge renumbers: `blocking = sorted(s.id for s in plan.steps if (s.id in set(merge_ids) or s.id > max(merge_ids)) and s.status != StepStatus.PENDING)`; return `(not blocking, blocking)`.
- **Rationale.** A merge rewrites the very members being folded **and** renumbers every step after the merged region (shifting ids down by `len-1` and renaming their detail files via `_migrate_downstream_details_after_merge`). So a non-PENDING member that has run (`DONE`) or is running (`CURRENT`) blocks, *and* so does a non-PENDING downstream step — renumbering/renaming it while it carries id-keyed run state (run logs, "step N green" commit subjects, lessons, saved reviews) would orphan that state. This is the exact orphaning hazard `_split_is_safe` blocks with `s.id >= target_id`, applied to the post-region steps a merge likewise renumbers. A parked (`scope: deferred`/`wont_do`) step is still `PENDING` and carries no run state → run-state-safe here, identical to `_split_is_safe`'s treatment; whether a parked member may join the set at all is a separate scope-commitment gate enforced in the assembly (the merge requires a uniform `scope` and rejects a mixed-scope set).
- **Stale-guidance note — do NOT regress to a members-only gate.** A project lesson describes `_merge_is_safe` as a members-only gate paired with a `test_downstream_nonpending_does_not_block` case; that guidance is **superseded** by this design. The gate **must** also block a non-PENDING step after the merged region (per the rationale above), and the binding test is `test_downstream_nonpending_blocks` (see Tests) — **not** `test_downstream_nonpending_does_not_block`. Do not narrow the selector back to `s.id in set(merge_ids)` on the strength of the stale lesson.

### `_migrate_downstream_details_after_merge(new_steps, *, repo_root, merged_new_id) -> None`

- **Mirror `_migrate_downstream_details_after_split`'s body, inverting only the selector and sort.** Reuse the module-level `_DETAIL_ID_PREFIX_RE` (already defined for split) to swap the leading `NN-` prefix while preserving each file's slug exactly as it appears on disk.
- **Downstream selector:** `downstream = sorted((s for s in new_steps if s.id > merged_new_id and s.detail), key=lambda s: s.id)` — ascending. `merged_new_id` is the survivor id (= `lo`); the merged step at `merged_new_id` is excluded by `>`, and pre-region steps (`id < lo`) never renumber.
- **Per step:** read the old `NN-` prefix from `repo_root / step.detail`'s filename; rename to `{step.id:02d}-{slug}`; archive any pre-existing file at the destination via `_archive_existing_detail` before `rename` (silent-overwrite guard, same as split); repoint `step.detail` via `_repo_relative`. A missing but `NN-`-prefixed source file repoints the pointer without a move; an odd-named (non-`NN-`-prefixed) source file leaves the pointer unchanged (best-effort, same as split).
- **No `eliminated` parameter.** The rename is prefix-swap-based (reads the old prefix off disk) and does not arithmetic-derive the old id, so an `eliminated` count would be dead — do not carry it merely to mirror split's `shift` shape; the selector keys on `merged_new_id` alone.

### `_confirm_merge(prompt_fn, *, steps_to_merge: list[Step], merged_title: str) -> bool`

- **Mirror `_confirm_split` exactly:** default **NO**; non-TTY (`not sys.stdin.isatty()`) auto-declines (the structural edit never happens unattended); parse `y`/`yes` (case-insensitive, stripped) as assent.
- **Prompt body:** name the ids+titles being folded (`steps_to_merge`) and the resulting `merged_title`, then ask "Apply this merge and re-author the combined detail? [y/N] ".
- **Caller — step 3's `cmd_merge` calls it, not `merge_steps`.** Merge has no Phase-B seam (split's confirmation lives in `generate_detail`, not the CLI); because `cmd_merge` re-authors over the members' **existing** detail bodies, the **CLI owns the gate**: on an interactive TTY without `--yes`, `cmd_merge` calls `_confirm_merge` after its id/safety guards and before `merge_steps`, and a decline returns rc 2 before any mutation; when `--yes` is passed or stdin is non-interactive the gate is **bypassed** and the merge proceeds (the `getattr(args, "yes", False) or not sys.stdin.isatty()` pattern — reconciling with `cmd_split`'s no-gate posture so an explicit, assented merge runs headlessly rather than auto-declining with rc 2). See step 3's detail. `merge_steps` itself does **not** prompt, so the gate fires at most once. This delivers the plan's Risks mitigation ("operator confirmation via `_confirm_merge` … at a TTY") at the CLI layer. `_confirm_merge` is still **defined here** (beside `_confirm_split`) and imported by `cmd_merge`.

### `MergeResult` dataclass (mirror `SplitResult`)

- **Fields** (`@dataclass(frozen=True)`, mirroring `SplitResult`'s shape):
  - `merged_id: int` — survivor id (post-renumber, = `lo`).
  - `merged_title: str` — the merged step's title.
  - `folded_ids: list[int]` — the original ids folded (sorted); analogous to `SplitResult.new_ids` but for the *input* set.
  - `folded_titles: list[str]` — the original member titles, in id order.
  - `detail_results: list[DetailResult]` — the merged step's re-author outcome; empty when `author_details=False` or `dry_run=True`.
  - `dry_run: bool = False`.
  - `renumber: list[tuple[int, int]] = field(default_factory=list)` — `(old_id, new_id)` for every step; populated only on `dry_run`.
  - `new_plan: list[tuple[int, str, list[int]]] = field(default_factory=list)` — post-merge `(id, title, depends_on)` rows; populated only on `dry_run`.
- **Per-arm field-population matrix** (state explicitly — a consumer must not misread an empty field):
  - `renumber` / `new_plan` — **only** on `dry_run=True`; empty on a real run.
  - `detail_results` — empty on `dry_run=True` **and** on `author_details=False`; otherwise the single merged re-author's results.
  - `merged_id` / `merged_title` / `folded_ids` / `folded_titles` — populated on **every** non-error return (including dry-run).

### `merge_steps(...)` orchestrator (mirror `split_step`)

- **Signature** (mirror `split_step`'s kwargs):
  ```
  def merge_steps(
      plan_path: Path,
      *,
      merge_ids: list[int],
      title: Optional[str] = None,
      repo_root: Path,
      author_details: bool = True,
      dry_run: bool = False,
      invoker: DetailInvoker = shell_detail_invoker,
      reporter: Optional[ProgressReporter] = None,
      run_logger: Optional[RunLogWriter] = None,
      prompt_fn: Optional[Callable[[str], str]] = None,
      budget: IterativeBudget = IterativeBudget(enabled=False),
  ) -> MergeResult:
  ```
- **In-body import** (avoid create↔detail cycle, mirroring `split_step`): `from plan_tool.create import CreateError, _apply_step_merge`.
- **Validation order (raise `DetailError`, all before any mutation):**
  1. **≥2 ids.** `len(set(merge_ids)) < 2` → `DetailError`. (`_apply_step_merge` also rejects this; gate early for a clean message and to skip parse work.)
  2. **Canonical numbering.** Parse the plan; require `[s.id for s in plan.steps] == list(range(1, len(plan.steps)+1))`, else `DetailError` — `_migrate_downstream_details_after_merge` equates id with 1-based position (same guard and wording as `split_step`).
  3. **All ids resolve.** Any id in `merge_ids` absent from the plan → `DetailError` (mirror split's not-found guard; `_apply_step_merge` also catches it).
  4. **Safety.** `safe, blocking = _merge_is_safe(plan, merge_ids)`; on `not safe` raise `DetailError(f"cannot merge step(s) {blocking}: already run/started — restructure via re-plan instead")`.
- **Assemble the `merged` Step** (caller-built, exactly as `split_step` assembles `replacements` and lets the transform set `id`/`depends_on`):
  - `title` = the passed `title`, else the **derived default**: the lowest-id member's title. State this as a load-bearing decision — the plan says "derive from the merged set's titles"; the lowest-id (survivor-position) member's title is the soundest minimal default. A smarter join/summarization is **Deferred**.
  - `files` and `creates` = preserve the members' partition: `files` is the order-preserving dedup of members' `files` and `creates` is the order-preserving dedup of members' `creates`. Do **not** fold created paths into `files` (via `Step.all_files` or otherwise) — a member's to-be-created path must stay in `creates`, since a merge requires an all-PENDING set and those paths do not exist on disk yet; collapsing them into `files` makes them `created=False`, which `review.py:check_file_existence` then flags as a missing modify-target (NEW/MISSING_PARENT) that the merge's own completeness tail re-chews. Keeping the partition lets `created=True` entries stay exempt.
  - `change_type` = the **dominant** member type under the precedence `feature > refactor > non-code` — rank with `{ChangeType.NON_CODE: 0, ChangeType.REFACTOR: 1, ChangeType.FEATURE: 2}`, filter out `None`-typed members, and pick the highest-ranked (default `None` only if no member carries one). The merged step is a single pure-typed step; the lower-ranked members' work is absorbed into its re-authored Implementation prose. **Do NOT set `change_type=None` to signal a mix, and do NOT add a `type_impure` flag or any `Step` schema field** — see the plan's "A merged step takes the dominant `change_type`" architecture note and its rejected-alternative callout. Collapsing to the dominant type removes the mixed-type step, so the purity/granularity gates have nothing to flag and the merged step converges with no suppression machinery.
  - `complexity` = the **rank-max** of members' complexities (a fold is at least as complex as its largest part). `plan_tool/schema.py:Complexity` is a `str`-Enum whose string-value ordering is `high < low < medium`, so bare `max()` returns the wrong member (MEDIUM as "most complex") and raises `TypeError` on a `None`-complexity member. No complexity-rank helper exists in the tree — rank explicitly with `{Complexity.LOW: 0, Complexity.MEDIUM: 1, Complexity.HIGH: 2}`, filtering out `None`-complexity members, and pick the highest-ranked (default `None` when no member carries a complexity).
  - `scope` = the members' **shared** `StepScope`. **Require every member to carry the same `scope`; reject a mixed-scope set with `DetailError` before any mutation** (raise in the validation order, alongside the safety check). `Step.scope` defaults to `StepScope.COMMITTED`, so an unguarded assembly would silently mark the merged step `committed` — folding a parked (`scope: deferred`/`wont_do`) member into a committed merged step would resurrect abandoned work back into runnable-selection and the completion tally, and the inverse would abandon committed work. With a uniform set the merged step inherits that single shared scope. This is a scope-commitment gate, **separate** from `_merge_is_safe`'s run-state gate (a parked member is run-state-safe yet still rejected here when the set is mixed-scope); a smarter mixed-scope merge policy is **Deferred**.
  - `features` = the **order-preserving dedup** (`list(dict.fromkeys(...))`) of members' `features`. `Step.features` defaults to `[]`, so an unguarded assembly drops every member's feature linkage — folding a member that declared `features: [X]` into a merged step that defaulted `features=[]` would sever the plan↔feature-registry linkage and make feature X read as unimplemented to the feature-ref/smell checks the merge's own completeness tail re-runs.
  - `allowed_mentions` = the **order-preserving dedup union** (`list(dict.fromkeys(...))`) of members' `allowed_mentions` — unioned across members, **not** regenerated by the re-author. `Step.allowed_mentions` defaults to `[]`, so an unguarded assembly drops every member's allow-listed mentions, and the merge's re-audit / scope-guard tail would re-flag references that were previously permitted on a member. Unioning preserves each member's scope-guard posture across the fold.
  - `gate` and `enforce_test_authoring` = **carried forward** from the members so no per-step linkage is lost in the fold: union the members' `gate` (order-preserving dedup) and carry forward `enforce_test_authoring` (`True` if any member sets it `True`, else preserve a member's explicit `False`, else `None`).
  - `id=0`, `depends_on=[]` placeholders — `_apply_step_merge` overwrites both deterministically. `detail=None` so the merged half is authored fresh.
- **Apply the transform:** `new_steps = _apply_step_merge(plan.steps, merge_ids, merged)`, wrapping `CreateError` → `DetailError(f"merge failed: {exc}")`. `merged_new_id = min(merge_ids)` (= `lo`; the contiguous-set fold puts the survivor at `lo`); `eliminated = len(set(merge_ids)) - 1`.
- **`dry_run=True` short-circuit:** `_apply_step_merge` returns only `list[Step]` (no renumber dict), so build the `(old_id, new_id)` rows with an inline walk over `plan.steps` — `_apply_step_merge`'s renumber arithmetic restated, no helper minted here. With `lo = min(merge_ids)`, `hi = max(merge_ids)`, and `eliminated = len(set(merge_ids)) - 1`:
  ```
  def _old_to_new(old_id: int) -> int:
      if old_id < lo:          # pre-region — unchanged
          return old_id
      if old_id in set(merge_ids):  # folded set — collapses to the survivor
          return lo            # = merged_new_id
      return old_id - eliminated    # post-region (old_id > hi) — shifts down
  renumber = [(s.id, _old_to_new(s.id)) for s in plan.steps]
  ```
  Then return `MergeResult(merged_id=merged_new_id, merged_title=merged.title, folded_ids=sorted(set(merge_ids)), folded_titles=[…], detail_results=[], dry_run=True, renumber=renumber, new_plan=[(s.id, s.title, list(s.depends_on)) for s in new_steps])`. No write, no rename, no authoring — exactly `split_step`'s dry-run arm. (If step 3's caller needs `renumber` outside dry-run, promote this walk to a `_merge_renumber_map` helper mirroring `_split_renumber_map` — Deferred; not minted in this step.)
- **Real run, in order:**
  - **No confirmation here — the caller owns it.** `merge_steps` does **not** call `_confirm_merge`; the TTY confirmation gate is invoked by step 3's `cmd_merge` *before* it calls `merge_steps` (see step 3's detail). The orchestrator trusts that an interactive caller has already confirmed; a non-interactive caller is responsible for its own gate.
  1. **Collect folded-away bodies first.** Before any write, snapshot each member's existing detail path **and read its full body**: `folded_paths = [repo_root / s.detail for s in plan.steps if s.id in set(merge_ids) and s.detail]`, then read each path's text in id order. These full bodies feed the re-author through the `$prior_body` placeholder (below); the paths are archived after. **The `s.detail` filter intentionally tolerates undetailed members — a merge requires only an all-PENDING set, and a PENDING member may have no detail body yet.** When *all* members lack a detail body, `folded_paths` is empty, `$prior_body` is empty, and the re-author authors the merged step **fresh from its assembled fields** (title/`files`/`creates`/`change_type`/`complexity`) through the seven-section gate — there is no prior content to combine. When *some* members are detailed and others are not, the combine carries forward only the available bodies and the re-author fills the rest from the assembled fields. Both cases are intended behavior, not oversight.
  2. `_migrate_downstream_details_after_merge(new_steps, repo_root=repo_root, merged_new_id=merged_new_id)`.
  3. `write_plan(plan_path, plan.model_copy(update={"steps": new_steps}))`.
  4. **Re-author the merged half** (when `author_details` and not `dry_run`): `generate_detail(plan_path, repo_root=repo_root, step_id=merged_new_id, force=True, invoker=invoker, reporter=reporter, resume=False, prompt_fn=prompt_fn, run_logger=run_logger, budget=budget, allow_split=False, extract_lessons=False, prior_body=<the folded members' full bodies, in id order>)`. `force=True` regenerates from scratch through the seven-section gate; `allow_split=False` prevents a re-split of the just-merged step; `prior_body` carries the combine content.
  5. **Combine via the `$prior_body` placeholder — full bodies, no truncation (load-bearing).** The merged step's detail must be one coherent file built *from* the folded members' complete seven-section bodies, not a naive staple. The combine mechanism is the dedicated `${prior_body_block}` placeholder added to `plan_tool/prompts/detail.md`: `merge_steps` reads each folded member's **full** detail body and passes it through `generate_detail`'s new `prior_body` kwarg → `render_detail_prompt` substitutes it verbatim into `${prior_body_block}`, with **no `_MAX_PROMPT_FILE_BYTES` truncation**. This is distinct from — and is **not** — the existing `${sibling_details_block}` seam, which `_format_sibling_details_block` (`detail.py:3528`) truncates each entry at `max_file_bytes` = `_MAX_PROMPT_FILE_BYTES` = 4096 and `render_detail_prompt`'s docstring frames as a *tone/structure* reference only. Routing the combine through `$prior_body` (not siblings) is what makes the merged re-author absorb the complete bodies rather than a ~4 KB prefix of each, satisfying the plan's "concatenate + re-author/re-audit, don't naively staple, full bodies without silent truncation" requirement. (The sibling seam still fires incidentally — the folded files are on disk at re-author time — but as a tone reference only; faithful content combine is owned by `$prior_body`.) **Integrate to the dominant type, do not staple sections.** With the merged step assigned a single dominant `change_type` (above), the re-author must weave any lower-ranked member's work (e.g. a folded refactor under a `feature` survivor) into the dominant type's narrative as **incidental implementation detail** — *not* a labeled standalone "Refactor" phase/section. The conceptual mixed-step audit reads the Implementation prose, not just the `change_type` field: a stapled refactor-beside-feature body re-trips the mixed-step / `granularity-split` finding on every re-audit and churns the convergence loop, whereas one coherent feature narrative presents no split surface. (Do **not** reach for a `type_impure` flag or a completeness-loop suppression to paper over a stapled body — see the plan's rejected-alternative callout; the fix is integrated prose.)
  6. **Archive the folded-away files after re-author.** For each `p` in `folded_paths` that still exists and is not the merged step's current detail path, `_archive_existing_detail(p)` (best-effort, mirroring split's overwrite-time archival posture; archive, not hard-delete). The merged step's own file (when its slug coincided with a member's) was overwritten in place by the `force` re-author and is excluded.
- **Return** `MergeResult(merged_id=merged_new_id, merged_title=<merged step's title from new_steps>, folded_ids=sorted(set(merge_ids)), folded_titles=[member titles in id order], detail_results=<from generate_detail or []>)`.

### Foundational logic / shared call sites (audit)

- **This step's foundational logic:** the run-state safety gate + deterministic detail-file renumber/migration for a structural plan edit.
- **Shared locations (mirror templates, cite — do not refactor here):** `_split_is_safe`, `_migrate_downstream_details_after_split`, `_confirm_split`, `SplitResult`, `split_step`, and the Phase-B split block in `generate_detail` (all in `plan_tool/detail.py`). This step writes **parallel** merge siblings; it must not alter the split symbols.
- **Consolidation candidate → Deferred (not this step):** `_migrate_downstream_details_after_split` and `_migrate_downstream_details_after_merge` will be ~90% identical (same prefix-swap body, inverted selector + sort). Folding them into one `_migrate_downstream_details(new_steps, *, repo_root, first_renumbered_id, ascending)` is a behavior-preserving consolidation `detail` cannot mint mid-feature — route it to `reconcile` rather than expanding this step's footprint.

## Tests

All cases live in `tests/test_detail.py`, hermetic (`tmp_path`), no real Claude (pass a fake `DetailInvoker` or `author_details=False`; the autouse `_stub_lessons_extraction` fixture neutralizes lesson extraction). Reuse the `_write_detail_plan` fixture pattern already in the file for plan/file scaffolding.

**`TestMergeIsSafe`**
- `test_all_pending_set_is_safe` — a set of all-PENDING members returns `(True, [])`.
- `test_done_member_blocks` — a `DONE` member in the set returns `(False, [that id])`.
- `test_current_member_blocks` — a `CURRENT` member blocks.
- `test_parked_member_is_safe` — a parked (`scope: deferred`) but PENDING member does not block.
- `test_downstream_nonpending_blocks` — a non-PENDING step *after* the merged region blocks (the merge renumbers/renames it, so its id-keyed run state would orphan — same hazard `_split_is_safe` guards).
- `test_upstream_nonpending_does_not_block` — a non-PENDING step *before* the merged region (`id < min(merge_ids)`) does not block, since a merge never renumbers pre-region steps.

**`TestMigrateDownstreamDetailsAfterMerge`**
- `test_renames_downstream_down_and_repoints` — downstream files get `NN-` prefixes decreased by `eliminated`, `step.detail` repointed.
- `test_processes_low_to_high_without_clobber` — adjacent downstream renames don't clobber when slugs coincide (ascending order + archive guard).
- `test_missing_source_file_repoints_only` — a missing but `NN-`-prefixed source file repoints the pointer without a move; an odd-named (non-`NN-`-prefixed) source leaves the pointer unchanged.
- `test_pre_region_steps_untouched` — steps with `id < merged_new_id` are not renamed.

**`TestConfirmMerge`**
- `test_non_tty_auto_declines` — `sys.stdin.isatty()` patched False → returns `False` without prompting.
- `test_yes_confirms` / `test_default_declines` — `y`/`yes` confirm; empty/`n` decline (TTY patched True, `prompt_fn` stubbed).

**`TestMergeSteps`** (feature behavior end-to-end with a fake invoker / `author_details=False`)
- `test_dry_run_computes_renumber_and_newplan_no_writes` — `dry_run=True` populates `renumber`/`new_plan`, writes nothing, renames nothing.
- `test_rejects_fewer_than_two_ids` — `merge_ids=[2]` raises `DetailError`.
- `test_rejects_non_canonical_numbering` — gapped/out-of-order ids raise `DetailError`.
- `test_rejects_unknown_id` — an id absent from the plan raises `DetailError`.
- `test_unsafe_set_raises_before_mutation` — a `DONE` member raises `DetailError` and leaves plan/files byte-identical.
- `test_reauthor_failure_leaves_renumbered_plan_and_orphans` — a fake invoker that raises mid-re-author (after the pre-author mutations) leaves the plan persisted with the merged step renumbered-but-undetailed, the downstream siblings already renamed, and the folded-away detail files un-archived as orphan `NN-` files for ids absent from the renumbered plan (no rollback, no auto-clean) — pinning the Architecture's leave-and-resume partial-failure posture and its manual-cleanup recovery path.
- `test_mixed_scope_set_raises_before_mutation` — a set pairing a `committed` member with a `deferred`/`wont_do` member raises `DetailError` and mutates nothing; a uniform-scope set assigns that shared `scope` to the merged step.
- (Confirmation is owned by `cmd_merge`, not `merge_steps` — the decline-aborts behavior is tested in step 3's `tests/cli/test_authoring_cmds.py`. `_confirm_merge` itself is covered by `TestConfirmMerge` above.)
- `test_invalid_graph_raises` — a fork/join or cycle-closing set surfaces `_apply_step_merge`'s `CreateError` as `DetailError`, no mutation.
- `test_folds_set_and_renumbers` (`author_details=False`) — folds `{2,3}` in a 4-step plan to 3 steps, merged at id 2, downstream old-4 → id 3.
- `test_merged_step_inherits_assembled_fields` — merged step's title (derived default = lowest member), `files` union, `complexity` = max, survive into the written plan.
- `test_merged_step_carries_features_gate_and_enforce_test_authoring` — folding members that declare `features`, `gate`, and `enforce_test_authoring` yields a merged step whose `features` is the order-preserving dedup union, whose `gate` is the dedup union, and whose `enforce_test_authoring` is carried forward (`True` if any member sets it), so no per-step linkage is lost in the fold.
- `test_folded_files_archived_after_merge` — the folded members' detail files are archived (not left as live `NN-` orphans) after a real run.
- `test_reauthor_receives_full_member_bodies_via_prior_body` — with a fake invoker capturing the rendered prompt, assert **every** folded member's full body (including the **lowest-id** member, which the sibling seam would exclude) reaches the re-author prompt through the `${prior_body_block}` placeholder. Crucially, give at least one member a body **larger than `_MAX_PROMPT_FILE_BYTES` = 4096 bytes** and place a unique marker **past the 4 KB cut-off**: the marker must appear in the rendered prompt, proving the `$prior_body` combine is **not** truncated (the exact failure the truncated sibling seam would exhibit).
- `test_returns_populated_mergeresult` — `MergeResult.folded_ids`/`folded_titles`/`merged_id`/`merged_title` match; `detail_results` empty when `author_details=False`.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write each test above **with** the symbol it covers (`_merge_is_safe` tests with `_merge_is_safe`, etc.). Green-before-done gate: every new case must pass (`uv run pytest tests/test_detail.py -q`) and the full existing `tests/test_detail.py` suite must stay green before this step is complete.

## Acceptance criteria

- `merge_steps`, `_merge_is_safe`, `_migrate_downstream_details_after_merge`, `_confirm_merge`, and `MergeResult` exist in `plan_tool/detail.py` immediately after the split cluster, with no edits to the existing split symbols.
- `_merge_is_safe(plan, merge_ids)` returns `(False, blocking)` iff any **member** of `merge_ids` *or any step after the merged region* (`id > max(merge_ids)`) is non-PENDING; a non-PENDING step before the region does not block.
- `merge_steps` raises `DetailError` (before any disk mutation) for `<2` ids, non-canonical numbering, an unknown id, an unsafe (run-started) set, a mixed-scope set, or an invalid graph from `_apply_step_merge`.
- The merged step's `scope` is the members' shared `StepScope`; a mixed-scope set (e.g. a `committed` member with a `deferred`/`wont_do` member) raises `DetailError` and never resurrects parked work into the merged step.
- On a successful real run over a contiguous all-PENDING chain: the set folds to one step at id `min(merge_ids)`, survivors renumber to contiguous `1..N` shifted **down** by `len(set)-1`, downstream detail files are renamed down and repointed, and the folded-away files are archived.
- The merged detail file is re-authored via `generate_detail(force=True, allow_split=False, prior_body=…)` and passes the seven-section gate; the folded members' **full bodies** reach the re-author through the `${prior_body_block}` placeholder **without `_MAX_PROMPT_FILE_BYTES` truncation** — the load-bearing combine mechanism, distinct from the tone/structure-only `${sibling_details_block}` seam.
- The merged step **unions its members' `features`** (order-preserving dedup) and **carries forward `gate` (dedup union) and `enforce_test_authoring`** (`True` if any member sets it), so no per-step plan↔feature-registry linkage is lost in the fold.
- `MergeResult.renumber`/`new_plan` are populated **only** on `dry_run=True`; `detail_results` is empty on `dry_run` or `author_details=False`.
- A re-author/re-audit failure after the pre-author mutations is leave-and-resume, not rollback: the renumbered-but-undetailed merged step and renamed siblings persist, the folded-away files remain as orphan `NN-` files for ids no longer in the plan, and the failure surfaces — recovery is re-running `plan-tool detail` then manually deleting the orphans (no auto-rollback or auto-clean), verified by `test_reauthor_failure_leaves_renumbered_plan_and_orphans`.
- `merge_steps` performs no plan write, file rename, or authoring when `dry_run=True`.
- `_confirm_merge` is defined in this module but invoked by step 3's `cmd_merge` before `merge_steps` (the CLI owns the TTY gate); `merge_steps` itself performs no confirmation prompt.
- `uv run pytest tests/test_detail.py -q` is green, including the four new test classes.
- No new import cycle: `_apply_step_merge`/`CreateError` are imported lazily inside `merge_steps` (mirroring `split_step`).

## References

- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Reference for the `@dataclass(frozen=True)` `MergeResult` mirroring `SplitResult`, including `field(default_factory=list)` for the dry-run-only collections.
- [How to use temporary directories and files in tests — pytest documentation](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — The hermetic `tmp_path` pattern the new `tests/test_detail.py` classes use for plan/detail-file fixtures and rename assertions.
- [argparse — Parser for command-line options, arguments and subcommands — Python documentation](https://docs.python.org/3/library/argparse.html) — Read for step 3's `--steps`/`--title` wiring; this step only defines the `merge_steps` shape the CLI will call, but the kwarg surface (`merge_ids`, `title`, `author_details`, `dry_run`) is what `cmd_merge` maps flags onto.

## Deferred

- **`plan-tool merge` CLI command + `--steps`/`--title`/`--no-detail`/`--no-completeness`/`--iterate`/`--dry-run` parsing and the completeness loop** — step 3 (`plan_tool/cli/authoring.py`), `depends_on: 2`. The completeness audit + `--iterate` convergence and the `reconcile-plan` next-step pointer live at the CLI layer (mirroring how `cmd_split`, not `split_step`, runs `_run_completeness_tail`), not in this orchestrator.
- **Consolidating `_migrate_downstream_details_after_split` + `_migrate_downstream_details_after_merge`** into one direction-parametrized helper — a behavior-preserving refactor `detail` can't mint mid-feature; route to `reconcile`.
- **A smarter merged-title derivation** (join/summarize member titles) — the lowest-id-member title default is sufficient; refine later if the granularity advisor's emitted merges need it.
- **`PLAN_FORMAT.md` / `RUNBOOK.md` / `docs/cli` documentation** — steps 3–4.
