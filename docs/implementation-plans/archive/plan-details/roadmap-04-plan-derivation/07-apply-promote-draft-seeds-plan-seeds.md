> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Add `--apply` and `-y` to promote draft seeds into `plan-seeds/` with refuse-by-default collisions

## Summary

Add an **apply-only** path to `plan-tool roadmap` that reads on-disk `04-roadmap.md`, copies each ordered plan row's draft seed into `plan-seeds/` after opt-in confirm (or `-y`), and leaves slug-directory drafts untouched. The work splits across a deterministic orchestrator function in `plan_tool/roadmap.py` (mirror `scope_out_step`'s opt-in / confirm / apply shape) and CLI wiring in `plan_tool/cli/roadmap_cmd.py` that bypasses `run_roadmap` entirely when `--apply` is set. **Refuse-by-default** collision policy: if any target `plan-seeds/<plan-id>.md` already exists, or any advertised draft path is missing, the apply aborts with no writes. Promoted files drop the draft provenance YAML block so `plan-seeds/` stays prose-only. On green, `plan-tool roadmap <slug> --apply -y` copies seeds and prints ordered `plan-tool create <plan-id> --from-existing <promoted-path>` lines; stage runs without `--apply` stay unchanged from step 6.

## Table of Contents

- [Summary](#summary) — apply-only promotion, main design choice, green state
- [Why](#why) — gap after step 6 and why now
- [Input](#input) — contracts from steps 1 and 6 this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — paths touched
- [Implementation](#implementation) — apply orchestrator, CLI modes, copy semantics, collisions
- [Tests](#tests) — new and changed cases
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — stdlib docs for copy, paths, argparse
- [Applicable guardrails](#applicable-guardrails) — plan fences binding this step
- [Deferred](#deferred) — explicitly later steps

## Why

Step 6 closes the concept→artifacts→draft loop: a four-stage run writes `04-roadmap.md`, slug-relative draft seeds, and recommend-only `create --from-existing` lines pointing at those drafts. Operators still must hand-copy seeds into `plan-seeds/` before `create` can consume them — the plan's `#208` hand-off is incomplete. This step adds the scoped, confirm-gated promotion path the plan architecture names: read what stage 4 already wrote, copy on explicit opt-in, refuse silently destructive overwrites, and re-print create lines against the promoted paths.

## Input

Land step **6** before implementing. Open the landed modules and record what shipped — code on disk wins over this detail or the plan.

**From step 1 (`plan_tool/roadmap_artifacts.py`):**

- **`plans_path`**, **`PLANS_FILENAME`**, **`load_plans_artifact`**, **`parse_plans_artifact`** — read `04-roadmap.md` off disk
- **`PlansArtifact`**, **`PlanRow`**, **`OrderingEntry`**, **`PlanRow.draft_seed_path`** — slug-relative draft location per plan row
- **`resolve_draft_seed_path(plans_dir, slug, draft_seed_path)`** — absolute draft source path under the roadmap slug root
- **`parse_draft_seed_provenance`** — detect the draft provenance frontmatter block to strip on promotion (wire keys `DRAFT_SEED_ROADMAP_COMPONENTS_KEY`, `DRAFT_SEED_CROSS_CUTTING_KEY`)

**From step 6 (`plan_tool/cli/roadmap_cmd.py`):**

- **Create handoff printing** when stage 4 completes — load `04-roadmap.md`, walk **`artifact.ordering`**, resolve each row's draft via **`resolve_draft_seed_path`**, emit `plan-tool create <plan-id> --from-existing <short-path>` using **`_short_path`**
- **Stage-run path** — `cmd_roadmap` → **`run_roadmap`** with **`args.from_existing`** and **`args.from_stage`**; no `plan-seeds/` writes

**In-repo precedent (read, do not import orchestrators):**

- **`plan_tool/scope_out.py:scope_out_step`** — opt-in (`allow_scope_out`) → confirm (`yes` / TTY `[y/N]`) → mutate; non-TTY without `yes` returns **`recommended`** with no disk writes
- **`plan_tool/cli/scope_out_cmd.py:register`** — `-y` is a **second opt-in** under `--apply`, deliberately **not** `parser.make_yes_parent()`

**What this step cannot verify:** that promoted seed prose is good enough for `create` to converge — only that bytes land in the right place with the provenance block removed and create lines point at them.

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — add **`RoadmapApplyResult`**, shared **`ordered_plan_seed_targets`** (or landed name), and **`apply_roadmap_seeds`**; update module docstring to distinguish non-interactive stage runs from the apply path's confirm gate
  - `plan_tool/cli/roadmap_cmd.py` — add `--apply` / `-y`, branch apply-only vs stage-run in **`cmd_roadmap`**, render apply summary + create handoff; relax **`--from-existing`** to required only outside apply mode; update module docstring
  - `tests/test_roadmap.py` — unit cases for **`apply_roadmap_seeds`** (collisions, missing drafts, provenance strip, ordering)
  - `tests/cli/test_roadmap_cmd.py` — parser surface, mode branching, summary lines, mutual exclusion with **`--from-stage`**
  - `docs/cli/roadmap.md` — document apply-only usage, `-y`, and collision behavior (regenerate via `python -m plan_tool.cli_reference --write` if the repo's drift guard expects it)

## Implementation

### Design stance

- **Two modes, one verb.** `--apply` selects an apply-only invocation: no concept brief, no **`STAGES`** loop, no invoker call. Without `--apply`, behavior stays step 6's stage run. **Rejected alternative:** a separate subcommand — the plan explicitly models this on **`scope-out`**'s `--apply` flag on the same verb.
- **Orchestrator owns the gate chain; CLI owns exit codes and printing.** **`apply_roadmap_seeds`** in `plan_tool/roadmap.py` returns facts (**`RoadmapApplyResult`**); **`cmd_roadmap`** maps outcomes to messages and rc like today's stage path. Mirror **`scope_out_step`**, not **`run_roadmap`**.
- **Refuse-by-default, all-or-nothing.** Pre-scan every ordered plan row before writing anything. Any missing draft source or existing **`plan-seeds/<plan-id>.md`** destination → **`refused`** outcome, zero copies. **Rejected alternative:** auto-suffix destinations like **`scope_out.py:_carved_seed_path`** (`-2`, `-3`, …) — the plan's Risks section prefers refuse-by-default over silent displacement; numbered **`.replaced.N`** is deferred, not shipped here.
- **Copy, never move.** Slug-directory drafts remain the stage output for **`--from-stage 4`** re-entry. Use **`shutil.copy2`** or read/write through **`plan_tool/fileio.py:atomic_write_text`** after transformation.
- **Promoted seeds are prose-only.** Strip the draft provenance YAML frontmatter on write so **`plan-seeds/`** matches ordinary seed convention (step 4 documents this; step 7 owns the mechanics). Body text below the closing `---` passes through unchanged.

### Apply orchestrator (`plan_tool/roadmap.py`)

Add a frozen **`RoadmapApplyResult`** with at least:

- **`outcome`** — closed vocabulary: **`applied`**, **`recommended`**, **`refused`**
- **`promotions`** — tuple of **`(plan_id, source_path, dest_path)`** in **`artifact.ordering`** sequence (empty unless **`applied`**)
- **`collisions`** — destination paths that already exist (for **`refused`** messaging)
- **`missing_drafts`** — source paths advertised in **`04-roadmap.md`** but absent on disk

**`apply_roadmap_seeds(slug, *, repo_root, plans_dir, allow_apply, yes=False, prompt_fn=None) -> RoadmapApplyResult`**

Gate order (same shape as **`scope_out_step`**):

1. **Load** — **`load_plans_artifact(plans_path(plans_dir, slug))`**; let **`RoadmapArtifactError`** propagate for missing/malformed **`04-roadmap.md`**
2. **Resolve targets** — shared helper **`ordered_plan_seed_targets(plans_dir, slug, artifact)`** (name at implementer's discretion) walks **`artifact.ordering`**, looks up each **`PlanRow`** by **`plan_id`**, yields **`(plan_id, resolve_draft_seed_path(...), repo_root / "plan-seeds" / f"{plan_id}.md")`**. Using **`plan_id`** as the destination basename matches the walkthrough's **`plan-seeds/<create-slug>.md`** pattern and the plan row's create slug.
3. **Preflight scan** — collect **`missing_drafts`**, **`collisions`**, and **ordering↔plans bijection** failures (every ordering `plan_id` resolves to a plan row; every plan row appears exactly once in ordering); if any non-empty → return **`refused`** immediately (no prompt, no writes)
4. **Opt-in gate** — **`allow_apply=False`** → **`recommended`** with the resolved target list for preview
5. **Confirm gate** — mirror **`scope_out.py:_confirm_scope_out`**: **`yes`** skips prompt; non-TTY without **`yes`** prints a **`-y`** hint and returns **`recommended`**; TTY prompts **`[y/N]`** via injectable **`prompt_fn`**
6. **Apply** — for each target in order: read draft text; **`parse_draft_seed_provenance` must succeed** and strip the provenance block (write body only). If frontmatter is present but unparseable → **refuse** that promote (never copy the full file with provenance intact). **`atomic_write_text(dest, …)`**, append to **`promotions`**. Create **`plan-seeds/`** on first write if needed.

**Constraints (not free to vary):**

- Apply path **never** calls **`run_roadmap`**, **`shell_roadmap_invoker`**, or stage gates — no Claude, no retry budget
- Apply path **never** deletes or rewrites slug-directory drafts
- **`rg 'shell_roadmap_invoker|run_roadmap' plan_tool/roadmap.py`** inside **`apply_roadmap_seeds`** should find nothing (apply is a separate function, not a branch inside the stage loop)
- Stage-run loop stays non-interactive: **`rg 'input\(|isatty' plan_tool/roadmap.py`** may match only the apply confirm helper, not **`_run_stage`**

### CLI wiring (`plan_tool/cli/roadmap_cmd.py`)

**Parser surface:**

- Add **`--apply`** (`store_true`) — enter apply-only mode
- Add **`-y` / `--yes`** on a **`yes_parent`** sub-parser, **not** **`make_yes_parent()`** — help text states it is the second opt-in under **`--apply`** only (copy **`scope_out_cmd.register`** wording)
- **`--from-stage`** and **`--apply`** in an **`argparse` mutually exclusive group** — applying cannot combine with re-entry
- Change **`--from-existing`** to **`required=False`**; **`cmd_roadmap`** raises a usage-style error (rc **`_RC_USAGE`**) when **`not args.apply`** and brief path is missing

**`cmd_roadmap` branch:**

```text
if args.apply:
    result = apply_roadmap_seeds(..., allow_apply=True, yes=args.yes)
    render apply summary + create handoff for promoted paths
    map refused preflight → error + rc 2; recommended/applied → rc 0
else:
    existing stage-run path (unchanged except --from-existing check)
```

**Rendering (new helpers beside step 6's completed-run summary):**

- **`recommended`** — list each **`plan_id`**: **`draft → plan-seeds/<plan-id>.md`**, print the **`scope-out`**-style actuate hint (`--apply`, add **`-y`** for unattended)
- **`applied`** — success line with promotion count; detail each **`_short_path(dest, repo_root)`**; print ordered **`plan-tool create <plan-id> --from-existing <promoted-path>`** lines (reuse the ordering helper — draft-path handoff from step 6 and promoted-path handoff differ only in the path argument)
- **`refused`** — name every collision and every missing draft; state that nothing was copied

Refactor step 6's handoff loop to call the shared **`ordered_plan_seed_targets`** helper so ordering and **`PlanRow`** lookup stay in one place.

**Module docstring** — replace the blanket "no `-y`" claim with: stage runs stay non-interactive; **`--apply`** is the opt-in confirm surface.

### `docs/cli/roadmap.md`

Add a second usage line for apply-only mode, document **`--apply`**, **`-y`**, mutual exclusion with **`--from-stage`**, and that **`--from-existing`** is not used in apply mode. Keep stage-run docs accurate. Match tone of sibling CLI reference pages.

### Shared locations (read-only or other steps)

- **`plan_tool/roadmap_artifacts.py`**, **`plan_tool/roadmap_gates.py`** — consumed via load/resolve helpers; not edited
- **`plan_tool/cli/authoring.py`** create SplitProposal pointer — step 8
- **`CAPABILITIES.md` / operator walkthrough docs** — step 10
- Consolidating **`_confirm_scope_out`**, **`lessons_cmd`**, and roadmap apply into one shared confirm helper — cross-cutting refactor; Deferred

## Tests

Every listed test must be green before this step is done. Prefer `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q -n auto`.

### Tests for this step

**Orchestrator (`tests/test_roadmap.py`)**

- `test_apply_recommended_when_allow_apply_false` — resolves targets, writes nothing, outcome **`recommended`**
- `test_apply_refused_when_destination_exists` — pre-existing **`plan-seeds/<plan-id>.md`**, outcome **`refused`**, slug drafts unchanged
- `test_apply_refused_when_draft_missing` — row advertises a path with no file, outcome **`refused`**, no **`plan-seeds/`** writes
- `test_apply_refused_is_all_or_nothing` — one collision among N rows → zero destinations written
- `test_apply_yes_copies_in_ordering_sequence` — **`-y`** path writes N files; **`promotions`** order matches **`artifact.ordering`**
- `test_apply_leaves_slug_drafts_on_disk` — source draft bytes unchanged after **`applied`**
- `test_apply_strips_provenance_frontmatter` — promoted file has no **`roadmap_components`** frontmatter; body prose preserved
- `test_apply_refuses_unparseable_provenance_frontmatter` — malformed draft YAML frontmatter → **`refused`**, no destination written
- `test_apply_refused_when_ordering_plan_missing` — ordering cites unknown plan id → **`refused`**
- `test_apply_refused_when_plan_absent_from_ordering` — plan row not in ordering → **`refused`**
- `test_apply_creates_plan_seeds_dir` — **`plan-seeds/`** created when absent
- `test_apply_confirm_declined_returns_recommended` — TTY stub **`prompt_fn`** returns **`n`** → no writes
- `test_apply_non_tty_without_yes_returns_recommended` — no **`input()`**; outcome **`recommended`**

**CLI (`tests/cli/test_roadmap_cmd.py`)**

- `test_parser_apply_and_from_stage_mutually_exclusive` — argparse error when both passed
- `test_parser_from_existing_not_required_with_apply` — **`--apply`** parses without brief
- `test_parser_from_existing_required_without_apply` — missing brief → **`cmd_roadmap`** rc 2
- `test_cmd_apply_delegates_to_apply_roadmap_seeds` — stub orchestrator; **`run_roadmap`** not called
- `test_cmd_stage_run_still_calls_run_roadmap` — without **`--apply`**, stub **`run_roadmap`** receives brief + **`from_stage`**
- `test_apply_yes_prints_create_handoff_with_promoted_paths` — stdout contains **`plan-tool create <plan-id> --from-existing plan-seeds/...`**
- `test_apply_recommended_prints_preview_and_actuate_hint` — lists draft → destination mapping and **`--apply` / `-y`** guidance
- `test_apply_refused_prints_collision_detail` — stderr/info names blocking paths; rc 2
- `test_four_stage_run_still_does_not_touch_plan_seeds` — regression guard for step 6 (stage path only)
- `test_help_documents_apply_and_y` — **`register()`** help mentions apply-only mode and **`-y`** second opt-in

## Acceptance criteria

- `plan-tool roadmap <slug> --apply` with on-disk **`04-roadmap.md`** and drafts prints a recommend-only preview and writes nothing
- `plan-tool roadmap <slug> --apply -y` copies each ordered plan's draft to **`plan-seeds/<plan-id>.md`**, leaves slug-directory drafts in place, and prints **`plan-tool create <plan-id> --from-existing <promoted-path>`** lines in **`ordering`** sequence
- Promoted files under **`plan-seeds/`** contain no draft provenance YAML block; seed body text matches the draft body
- If any **`plan-seeds/<plan-id>.md`** already exists, **`--apply -y`** refuses with no copies and reports every blocking destination
- If any advertised draft path is missing, apply refuses with no copies and reports every missing source
- **`--apply`** and **`--from-stage`** cannot be passed together
- Stage run without **`--apply`** still requires **`--from-existing`**, still never writes **`plan-seeds/`**, and still prints draft-path create lines when stage 4 completes (step 6 regression)
- Apply path never invokes the roadmap backend / invoker (`tests` stub **`shell_roadmap_invoker`** and assert zero calls)
- `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` passes
- `docs/cli/roadmap.md` documents apply-only usage (and CLI reference drift test stays green if present)

## References

- [pathlib — Object-oriented filesystem paths (Python 3.13)](https://docs.python.org/3.13/library/pathlib.html) — compose **`plan-seeds/`** destinations and resolve slug-relative draft sources
- [shutil — High-level file operations (Python 3.13)](https://docs.python.org/3.13/library/shutil.html) — **`copy2`** semantics if used for promotion (preserve mtime/metadata)
- [argparse — Parser for command-line options (Python 3.13)](https://docs.python.org/3.13/library/argparse.html) — **`--apply`**, conditional **`--from-existing`**, mutual exclusion with **`--from-stage`**
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — frozen **`RoadmapApplyResult`**

## Applicable guardrails

- **The plan's step intent.** This step adds apply-only promotion and promoted-path create lines only; it does not run stage 4, auto-run **`create`**, or judge seed merit.
- **The plan's Out of scope — auto-running create/detail/run.** Hand-off stays printed lines plus optional copy into **`plan-seeds/`**.
- **The plan's Out of scope — merit and quality gates.** Apply checks existence and collision only; no prose scoring, plan-count caps, or disposition judgment.
- **The plan's allowed reorganization.** Reuse the **`scope-out`** confirm/`-y` idiom; do not invent a second confirm stack or a shared seed-emission helper beyond what this step needs.
- **The plan's Risks — collision policy.** Refuse-by-default on existing **`plan-seeds/`** targets; numbered **`.replaced.N`** archive generations are not in scope for this step.

## Deferred

- **Recommend-only roadmap pointer on `create` SplitProposal next steps** — step 8 (`plan_tool/cli/authoring.py`)
- **Real brief run and human-review record** — step 9 (non-code)
- **Operator doc sweep, BACKLOG #208 closure, CAPABILITIES entry** — step 10
- **Numbered `.replaced.N` collision escape hatch or `--force`** — plan Risks mention it as an alternative; refuse-only ships first
- **Shared interactive confirm helper** across **`scope_out`**, **`manifest`**, and roadmap apply — reconcile/backlog consolidation, not this step
- **Stripping provenance via a shared primitive in `roadmap_artifacts.py`** — only needed if a second caller appears; inline strip in apply is enough here
