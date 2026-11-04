# `detail` workflow

This document maps the happy-path flow of `plan-tool detail <name>`, centered on
the **per-step author → converge → capture** pipeline. Source-of-truth references
are inline.

> The next lifecycle phase, **audit** (`completeness-audit` + `reconcile`), is documented
> separately in [`AUDIT_FLOW.md`](audit.md). Per-step resume + crash
> recovery for this flow are in [`DETAIL_RESUME_FLOW.md`](../recovery/detail.md)
> (shared engine: [`RESUME_FLOW.md`](../recovery/README.md)).

## TL;DR

- `detail` authors a **developer-actionable detail markdown file per step**
  (`prompts/detail.md`), wires the plan's `step.detail` pointer to it, and drives
  a **per-step convergence loop** that tightens the freshly-written body via
  `detail-quality` review + `apply_finding` until findings stabilize.
- Each step is processed independently and in order.
- Every authored step gets a
  **refactor-vs-feature purity self-check**; a mixed step is warned and, with
  `--split` (default on), offered an interactive split. The check runs only at
  author time — re-author with `--force` to apply it to an existing file (see
  [Reprocessing](#reprocessing-a-detailed-step)).
- With `--lessons` (**off by default**), a second pass after each run-grade
  write **distills lessons** from the body into the shared lessons store.

## High-level flow

```
              plan-tool detail <name>
                       |
                       v
        cmd_detail (plan_tool/cli/authoring.py): resolve plan, open run log
                       |
                       v
             generate_detail (detail.py)
                       |
          parse plan -> steps (in order)
                       |
        +========== per step ==========+
        |                              |
        |  render_detail_prompt         |
        |    (detail.md + file contents |
        |     + siblings + references    |
        |     + heuristic + lessons)     |
        |              |                |
        |              v                |
        |  invoke claude                |
        |  parse_detail_response         |
        |              |                |
        |              v                |
        |  write detail file            |
        |  update_step_detail_field      |
        |  (plan frontmatter)            |
        |              |                |
        |              v                |
        |  convergence loop:            |
        |    detail-quality -> apply     |
        |    -> reaudit (until findings  |
        |     stabilize)                 |
        |              |                |
        |              v                |
        |  distill + append lessons      |
        |    (only with --lessons)       |
        +==============================+
                       |
                       v
        cmd_detail: print per-step outcomes,
        suggest `reconcile` then `run`
```

## The per-step author round-trip

For each step:

- **Prompt:** `render_detail_prompt` fills `prompts/detail.md` with the plan
  metadata, the step (id/title/complexity/files/depends_on), **inlined declared
  file contents**, the **sibling detail files** already in
  `plan-details/<slug>/` (tone/structure reference), the plan's **`## References`
  block** (`extract_plan_references`), the **already-implemented heuristic**
  scoped to this step, and the **accumulated lessons**.
- **Output:** the raw markdown body of the detail file, parsed by
  `parse_detail_response`. Required H2s (`_REQUIRED_H2_TOKENS`): Summary, Table of
  Contents, Why, Files, Implementation, Tests, Acceptance. `References` and
  `Deferred` are optional.

## Write + plan wiring

On a parsed body:

- **Output path:** `derive_detail_path` →
  `<plan-dir>/plan-details/<plan-slug>/<NN>-<step-slug>.md`. `<step-slug>` comes
  from `derive_step_slug` (kebab-case, capped at 40 chars on a `-` boundary).
- **Frontmatter:** `update_step_detail_field` round-trips the plan to set
  `step.detail` to the new file's repo-relative path. Downstream subcommands
  (`run`, `reconcile`, `jira`, `verify`) load that body into their prompts, so
  authoring detail up front improves every later claude call.

## The convergence loop

After a successful write, the just-written body is tightened in place:

1. **Scan:** `collect_detail_quality_findings` renders
   `prompts/detail-quality.md` (a *grounding* check — the LLM Reads/Greps the
   producers, IaC, and siblings the body cites to confirm its claims hold at
   HEAD) and lifts `## Findings` into `Recommendation`s. It also merges the
   deterministic per-step grounding findings (`collect_step_grounding_findings`:
   path resolution, cited-vs-declared coherence, detail-body completeness) at no
   token cost — structural ones surface as deferred, the rest drive the apply.
2. **Iterate** until findings stabilize: each open finding is applied via
   `apply_finding` (which edits the detail file in place), then the body is
   **re-audited** against the now-edited version.
3. The on-disk detail file *is* the durable artifact — there's no separate
   per-iteration save.

The loop is gated by `--iterate`: under `--no-iterate` the per-step
convergence loop is a **no-op** (the body is written once and left as-is). Only
`--iterate` runs the scan → `apply_finding` → re-scan cycle to convergence
(`--max-iterations` / `--iteration-budget` cap it). With the default
`--max-iterations 3`, `detail` scales the effective per-step iteration cap by
step complexity: low-complexity steps get cap 1, medium-complexity steps get
cap 2, and high or unset complexity keeps the full cap 3. The initial scan still
runs; when it finds apply-eligible issues, the cap limits how many apply/re-scan
rounds follow.

For fast bulk authoring, `--detail-only` explicitly skips the per-step
detail-quality loop while leaving the whole-plan completeness tail enabled and
iterating. This is a lossy speed mode: per-step grounding is deferred to the
final pass rather than removed silently, and `--detail-only --no-completeness`
is rejected.

### `detail` re-scans every round; `completeness-audit`/`reconcile` audit once

The defining difference from the [audit flow](audit.md): **`detail` re-runs
its conceptual `detail-quality` claude scan on every iteration**
(`collect_detail_quality_findings` is called fresh each round —
[`detail.py`](../../../plan_tool/detail.py) initial scan + the loop's re-scan), whereas
`completeness-audit`'s conceptual claude audit runs **once up front** and only its
deterministic layer is re-checked between rounds.

The asymmetry is deliberate, and it follows from *what each audit measures*:

- `detail-quality` is a **grounding** check on a body that `apply_finding`
  rewrites every round. After an edit the body genuinely changed, so a re-scan
  reads the new text and surfaces new signal — it doesn't re-phrase the same gap
  into a fresh id. Re-scanning is the only way to confirm an apply actually
  closed the finding it targeted.
- `completeness-audit`'s `plan-correctness` / `plan-completeness` is a **conceptual
  design** audit. Re-running it each round would re-describe the same unresolved
  design gaps under new anchor ids, defeating the union-by-id convergence
  detection — so it audits once, applies the blocking correctness subset, and
  lets the cheap deterministic layer drive the stop condition.

So both loops converge, but on different signals: `detail` stops when a
re-scanned body stops yielding apply-eligible findings; `completeness-audit` stops when
its deterministic gaps clear (or the open count stalls / budget runs out).

## Step-purity self-check + split

The authoring prompt asks the model to flag the step it just wrote if it mixes
behavior-preserving **refactor** with new-behavior **feature** work — emitted as
a `## Structural findings` / `MIXED-STEP` block that `generate_detail` strips
from the saved body and lifts into a `detail-purity` finding. Every authored
step gets this check at no extra token cost; under `--iterate` the
`detail-quality` pass re-detects it as a deferred finding too.

A flagged step is **surfaced as a `mixed-step detected` warning**, and — with
`--split` (default on) on an interactive run — offered as a split in a pass
after the per-step loop: `_propose_step_split` → confirm `y/N` →
`_apply_step_split` renumbers the plan into a refactor-then-feature pair and
both halves are re-authored. The split is **skipped when any step at or after
the target is `done`** (only a `DONE` step's id-keyed run state — its `step N
green` commit subject — can't survive a renumber; a `CURRENT` step is "next
runnable", not mid-execution, and renumbers cleanly); downstream detail files
are renamed to their new ids (`_migrate_downstream_details_after_split`).
`--no-split` reduces this to detection-only.

## Lessons capture

**Off by default; `--lessons` opts in.** When on, a second claude call
(`extract_and_append_detail_lessons`, `prompts/extract-lessons-detail.md`)
distills general + project lessons from the
written body and appends them after dedupe — general to
`~/.plan-tool/lessons/general.md`, project to
`<repo>/.plan-tool/lessons/project.md`. Best-effort: failures print to stderr but
never roll back the file.

## Outcomes

`cmd_detail` prints `Step N → wrote draft to <path>` per step, then a next-steps
hint: `plan-tool reconcile-plan <name>` (audit the new detail files), then
`plan-tool run <name>` (execute the first step).

## Committing the result (`--commit`)

`detail --commit` commits **each converged step as it lands** (BACKLOG #122) —
the way `run --commit` commits each green step — instead of one commit at the
end. As `generate_detail` finishes a step (detail file written, `detail:` pointer
set, and — under `--lessons` — that step's lessons extracted), it fires a
per-step commit callback; a
**residual sweep** after the run catches anything not tied to a single step's
completion (the completeness tail's auto-applied edits, a final plan edit). This
keeps an **interrupted batch's completed steps durable** — a crash after step *k*
leaves *k* commits, not an uncommitted tree needing manual recovery — and keeps
the tree clean between steps (load-bearing for the test-authoring gate, same as
`run`). Mechanics (shared with the other verbs via
[`cli/gitcommit.py`](../../../plan_tool/cli/gitcommit.py)):

- **Clean-tree gate up front:** rejects (rc 2) if the working tree is dirty, so
  `git add -A` can't fold unrelated edits into a commit. Skipped under `--dry-run`.
- **Per-step:** each written step commits with subject
  `plan(<slug>): detail step N — <title>`; a step that skips (already authored)
  or splits does **not** commit. A clean tree at a step's turn is a silent no-op
  (no spurious "nothing to commit" failure).
- **Safety invariant — per-step `git add -A` is only safe while no prior step
  left the tree dirty.** The per-step commit stages *everything* (`git add -A`)
  to capture a step's full footprint (detail file, plan pointer, lessons, orphan
  archives) without enumerating it. So it is **skipped once any earlier step
  failed** (e.g. a frontmatter-update failure that orphaned a written file) — an
  otherwise-clean later step's `git add -A` would sweep that debris into the
  wrong commit. After a failure the run is rc-gated off, so the debris is never
  committed. The concurrent path and split re-authoring likewise route to the
  end-of-run commit, not per-step, for the same reason.
- **Residual sweep:** if the tree is still dirty after the run (e.g. completeness-
  tail edits), one final commit `plan(<slug>): detail — residual authoring edits`.
- **Hook-aware:** no `--no-verify` — a pre-commit hook rejection surfaces as a
  non-zero rc that flags the run (the files are still on disk).

The completeness tail invoked from `detail` never commits on its own — `detail`
owns the commits (per-step + residual). Standalone `completeness-audit --iterate --commit` commits its deterministic
repairs.

## Reprocessing a detailed step

`detail` is **idempotent**: a step whose `step.detail` is set *and* whose file
exists on disk is **skipped** on re-run, so re-running only fills in steps that
are still missing a file. On a TTY you're offered `Replace? [y/N]` per existing
step (default no); non-interactive runs auto-skip. (Resume/checkpoint detail:
[`DETAIL_RESUME_FLOW.md`](../recovery/detail.md).)

To deliberately re-author an existing step, pass `--force` — usually scoped to
one step:

```bash
plan-tool detail <name> --step 3 --force
```

Re-author a step when:

- its **frontmatter or context changed** — regenerate the body against the new
  shape. The resume cache keys on `title` / `complexity` / `files` /
  `depends_on` (not `change_type`, and not file *contents*), so those four
  auto-invalidate it; a `change_type`-only edit, a source-file edit, or a
  template change leaves the cache valid, so use `--force` / `--no-resume` to
  re-run anyway;
- you want to **re-run the step-purity self-check**. It runs only while a step
  is *authored*, so a plain re-run — which skips existing files — will **not**
  catch a mixed refactor+feature step already on disk. `--force` re-authors it
  and (with `--split`, on by default) offers the refactor-then-feature split.
  The read-only alternative that needs no re-authoring is
  `plan-tool completeness-audit <name>`, whose `plan-correctness` pass flags
  mixed steps across the whole plan.

## Source map

| Concern                              | File                                                            |
|--------------------------------------|-----------------------------------------------------------------|
| Orchestrator (author → converge → capture) | `plan_tool/detail.py` (`generate_detail`)                  |
| Authoring prompt template            | `plan_tool/prompts/detail.md`                                   |
| Prompt render                        | `plan_tool/detail.py` (`render_detail_prompt`)                  |
| Response parse                       | `plan_tool/detail.py` (`parse_detail_response`)                 |
| Output path / slug derivation        | `plan_tool/detail_artifacts.py` (`derive_detail_path`, `derive_step_slug`), re-exported by `plan_tool/detail.py` |
| Frontmatter wiring                   | `plan_tool/detail.py` (`update_step_detail_field`)              |
| Convergence loop                     | `plan_tool/detail.py` (`collect_detail_quality_findings`), `plan_tool/convergence.py` |
| Detail-quality review prompt         | `plan_tool/prompts/detail-quality.md`                           |
| Step-purity self-check               | `plan_tool/detail.py` (`_parse_purity_findings`), `plan_tool/prompts/detail.md` |
| Interactive split + file migration   | `plan_tool/split_safety.py` (`split_is_safe`), `plan_tool/detail.py` (`_migrate_downstream_details_after_split`), `plan_tool/create.py` (`_apply_step_split`) |
| Lessons capture                      | `plan_tool/detail.py` (`extract_and_append_detail_lessons`), `plan_tool/prompts/extract-lessons-detail.md` |
| CLI wiring                           | `plan_tool/cli/authoring.py` (`cmd_detail`)                     |
| Tests                                | `tests/test_detail.py`                                          |
```
