> **Auto-archived**: this plan was swept on 2026-06-19 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Merge Steps Executor
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add _apply_step_merge pure transform + merge renumber map to create.py
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/merge-steps-executor/01-apply-step-merge-pure-transform-merge.md
  status: done
- id: 2
  title: Add merge_steps orchestrator with _merge_is_safe, _migrate_downstream_details_after_merge,
    _confirm_merge, and MergeResult to detail.py
  files:
  - plan_tool/detail.py
  - plan_tool/prompts/detail.md
  - tests/test_detail.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/merge-steps-executor/02-merge-steps-orchestrator-merge-safe.md
  status: done
- id: 3
  title: Add cmd_merge CLI command + merge subparser, register beside split, and regenerate
    docs/cli reference
  files:
  - plan_tool/cli/authoring.py
  - plan_tool/cli/app.py
  - plan_tool/cli/__init__.py
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  - tests/cli/test_authoring_cmds.py
  - docs/cli/README.md
  creates:
  - docs/cli/merge.md
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/merge-steps-executor/03-cmd-merge-cli-command-merge-subparser.md
  status: done
- id: 4
  title: Document the merge command in PLAN_FORMAT.md and RUNBOOK.md, alongside split
  files:
  - PLAN_FORMAT.md
  - RUNBOOK.md
  complexity: low
  change_type: non-code
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/merge-steps-executor/04-document-merge-command-plan-format-md.md
  status: done
---
# Merge Steps Executor

## Overview

Build a **merge executor** — the structural inverse of the split engine — that folds a contiguous set of plan steps into one. Adds `_apply_step_merge` (a pure transform beside `_apply_step_split` in `create.py`), a `merge_steps` orchestrator beside `split_step` in `detail.py`, and a `plan-tool merge` CLI command beside `split` in `cli/authoring.py`. Reuses split's discipline invariant-for-invariant so the two operations are symmetric. This is the **executor only**: the decision of whether to merge comes from the granularity advisor (`step-granularity-advisor.md`), which emits `granularity-merge` findings — this gives those findings something to act on, mirroring how `escalate-structural-findings-to-split.md` executes `granularity-split`.

## Problem statement

Splitting a step has a full engine; merging two has nothing. A plan can be over-decomposed — a trivial refactor step feeding one feature step, or two adjacent *dependency-linked* steps touching the same files — and today there is no way to fold them back. This seed builds the missing structural inverse so an over-decomposed plan can be recombined.

## Architecture

**Mirror the split engine, invariant for invariant.** Split's pure transform `create._apply_step_split` (`create.py:3193`) splices replacements in for one step, renumbers to contiguous `1..N`, and rewires edges. The merge transform `_apply_step_merge` is its inverse, folding a **contiguous set** of step ids into one:

| Split (`_apply_step_split`) | Merge (`_apply_step_merge`) |
| --- | --- |
| 1 step → N replacements | N steps → 1 merged step |
| Ids stay contiguous `1..N` | Ids stay contiguous `1..N` |
| First replacement inherits target's `depends_on` | Merged step's `depends_on` = **union of the set's external deps**, remapped; edges *internal* to the set drop |
| Replacements chain refactor→feature | (no internal chain — they collapse) |
| Dependents of target repoint to the *terminal* replacement | Dependents of **any** merged step repoint to the single merged id |
| Edges after insertion shift **down** by `len-1` | Edges after the region shift **down** by `len-1` |
| Validated by constructing a dry-run `Plan`; raises `CreateError`, never mutates input | Same — pure list→list, dry-run `Plan` validation, raises on cycle/dangling |

Constraint: require the merged set to be **contiguous ids that are dependency-connected** (undirected connectivity over intra-set edges, so the collapse *target* is unambiguous). Contiguity and connectivity do not preclude a cycle — folding can still close one (e.g. an external step depends on one member while another member depends on that external step), which the dry-run `Plan` validation catches. Reject non-adjacent (gapped) or disjoint (unconnected) sets with a clear `CreateError` rather than guessing; an internally-branching but connected set (e.g. fork/join among members) is connected and collapses legally.

**Safety gate — `_merge_is_safe`.** Mirror `detail._split_is_safe`: refuse to merge if **any** step in the set — or **any step after the merged region** — has already run or started; you must not restructure completed work. A merge rewrites the folded members *and* renumbers/renames every downstream step (shifting ids down by `len-1` and renaming detail files via `_migrate_downstream_details_after_merge`), so a non-PENDING downstream step would be orphaned from its id-keyed run state — the exact hazard `_split_is_safe` blocks with `s.id >= target_id`. Pre-region steps (`id < min(merge_ids)`) never renumber and don't block. Honors the non-PENDING run-state gate already established for split.

**Detail-file handling (the asymmetry to get right).** Split *creates and authors* new detail files; merge must *combine* them: re-author/re-audit a single valid detail file *informed by* the merged steps' prior bodies and pass it through the seven-section gate — don't naively staple, the merged step needs one coherent Implementation/Tests/etc. The re-author must receive the **full member bodies** through a `$prior_body` placeholder that feeds each folded step's complete detail file without silent truncation — the `_MAX_PROMPT_FILE_BYTES`-truncated sibling seam is a tone/structure reference only and is **not** the combine mechanism, since a ~4 KB prefix of a multi-KB member body drops content the merged step must absorb. **The no-truncation guarantee is bounded by a practical ceiling:** because the combine concatenates every member's full body, a merge of many or very large members can push the assembled `$prior_body` past the model's prompt/context budget. This is acceptable because the granularity advisor emits `granularity-merge` findings only for small folds (a refactor step into one feature step, or a couple of adjacent dependency-linked steps), so concatenated bodies stay well within budget in practice; the executor does **not** add a per-member byte cap or summarization fallback (that would reintroduce the silent truncation this guarantee exists to prevent). If a pathological set does exceed the budget, the combine fails loudly at the re-author Claude call and falls under the same leave-and-resume partial-failure posture below — it is not silently degraded. Steps after the merged region renumber (shift **down** by `len-1`); rename their detail files via the mirror of `detail._migrate_downstream_details_after_split`. Archive the now-vanished detail files for the folded-away ids (best-effort, non-destructive, via `_archive_existing_detail`, mirroring split's posture) — **after** the re-author, so the archival can exclude the merged step's own file that the `force` re-author overwrote in place. **Partial-failure posture (mirrors split — leave-and-resume, no rollback):** the frontmatter renumber/rewire and downstream detail rename land **before** the combined detail is re-authored/re-audited through Claude and the seven-section gate; the folded-away archival lands **after**. If the re-author/re-audit fails after the pre-author mutations, `merge_steps` does **not** roll back — it leaves the merged step renumbered-but-undetailed, siblings already renamed, **and the folded-away detail files un-archived as orphan `NN-` files for ids that no longer exist in the renumbered plan**, then surfaces the failure (as split leaves a freshly-split step pending re-detail). Recovery is to re-run `plan-tool detail` (or re-invoke the merge's detail/completeness tail) against the persisted, already-renumbered plan, then delete the orphan folded-away files by hand; recovery does not reconstruct the pre-merge state or auto-clean the orphans.

**A merged step takes the dominant `change_type` — never a mixed/impure type.** A headline fold — "a trivial refactor step feeding one feature step" — combines members of differing `change_type`. The merged step is **not** marked as mixed or "type-impure"; it takes the **dominant** `change_type` among its members under the precedence **`feature > refactor > non-code`** (the most behaviorally-significant member wins), and the lower-ranked members' work is absorbed into the merged step's Implementation prose. This is consistent with the tool's model: a normal `feature` step routinely carries incidental refactoring in its body — the refactor is *how* the feature is built, not a separate type. So the merged step stays a single, pure-typed step and the purity/granularity gates see nothing to flag; it converges with no special handling. Beyond `change_type`, the merged step **unions its members' `features`** and **carries forward `gate` and `enforce_test_authoring`** so no per-step linkage is lost in the fold — folding a member that declared `features: [X]` into a merged step that defaulted `features=[]` would drop the live plan↔feature-registry linkage and make feature X read as unimplemented to the feature-ref/smell checks the merge's own completeness tail then re-runs.

**The prose must match the type, or the mixed-step audit re-trips.** Setting the dominant `change_type` neutralizes the *field*, but the conceptual mixed-step audit keys on the step's **prose** — whether the Implementation describes both behavior-preserving restructuring *and* new behavior. So the combine re-author must **integrate the absorbed lower-ranked members' work as incidental implementation detail woven into the dominant type's narrative** — not carried forward as a labeled standalone "Refactor" phase/section. This steer is carried by the deterministic lever: the `${prior_body_block}` prompt section that feeds the folded members' `$prior_body` content (step 2) must instruct the re-author in-prompt to weave each lower-ranked member's work into the dominant type's single coherent narrative — never to emit a labeled standalone refactor section — so the combine output is type-pure and the mixed-step audit finds no surface to flag. A merged `feature` step whose Implementation reads as one coherent feature (with the refactor described as part of how the feature lands) presents no refactor+feature split surface; a step that staples a labeled refactor section beside a feature section will re-trip the mixed-step finding on every re-audit and churn the convergence loop — the exact failure this rule exists to prevent. If an imperfect integration does re-trip the conceptual mixed-step finding through `cmd_merge`'s completeness tail, that finding is a **Correctness** finding (source `plan-correctness`, in `APPLY_ELIGIBLE_SOURCES`) and **is** auto-applied by the `--iterate` loop — `completeness_cmd.py` excludes only `plan-completeness` from convergence, not `plan-correctness`. The merge is never undone **not** because the finding is recommend-only, but because the prose-only apply pass can only **rewrite the merged step's narrative** to integrate the absorbed work more cleanly — it cannot create a new step to re-split the merge — so each round tightens the prose toward type-purity and the merged step survives. Reserve **recommend-only** for the `detail-purity` self-check and the advisor's `granularity-*` findings (including `granularity-split`), which genuinely require an operator to invoke `plan-tool split`.

> **Rejected alternative — do NOT implement, and do NOT reintroduce via the audit.** An earlier draft proposed a persisted `type_impure: bool` flag on the `Step` schema (to survive `model_config = ConfigDict(extra="forbid")`) plus a `cmd_completeness` finding-downgrade gate that suppressed the mixed-step / `granularity-split` finding so the convergence loop wouldn't re-split the just-merged step. **None of that is in scope.** No `type_impure` field, no schema change for it, no completeness-loop suppression special-case, no per-step "intentionally impure" marking. Adding durable schema state to silence a quality gate the merge itself trips is the wrong shape. Collapsing to the dominant `change_type` removes the mixed-type step entirely, so there is no finding to suppress and nothing to converge around. If a completeness/audit pass surfaces a "mixed-step / `granularity-split`" finding on a merged step, the resolution is to confirm the dominant-type assignment and prose absorption — **never** to add a suppression flag or a loop downgrade.

During the combine re-author the merged step is authored with `allow_split=False` so `generate_detail`'s purity self-check does not split the freshly-merged step back apart mid-combine; with a single dominant `change_type` assigned the self-check has nothing to act on regardless. Resolving or deliberately re-splitting a merged step later is the operator's call, never the convergence loop's.

**CLI — `plan-tool merge`.** Mirror `cmd_split` (`cli/authoring.py:1359`) and register beside `split`:

```
plan-tool merge <name> --steps 3 --steps 4 [--title "Merged title"] \
    [--no-detail] [--no-completeness] [--iterate] [--dry-run]
```

`--steps` repeated — `cmd_merge` guards only `len(set(ids)) < 2` at the CLI layer; contiguity + connectivity are validated by `_apply_step_merge` inside `merge_steps` (before any mutation, but after the optional `_confirm_merge` gate), so a gapped/disjoint set can be confirmed at the TTY and only then rejected with a `DetailError`. `--title` optional — `cmd_merge` parses `--title` and passes it straight through to `merge_steps`, which **derives the default inside the orchestrator when it is `None`: the lowest-id (survivor-position) member's title**. This minimal default keeps the derivation in one place (`merge_steps`), testable at the orchestrator layer; a smarter join/summarization of member titles is Deferred. Like `cmd_split`: renumber + rewire, combine + re-author detail, then — unless `--no-detail` / `--no-completeness` — loop the conceptual completeness audit, applying blocking findings to convergence under `--iterate`. Offer `reconcile-plan` as the follow-up next-step (the merged step may describe unbuilt work; merge makes no plan-vs-code claim). Returns a `MergeResult` mirroring `SplitResult` (`detail.py`).

**Acyclic layering.** Put `_apply_step_merge` beside `_apply_step_split` in `create.py`; the `merge_steps` orchestrator beside `split_step` in `detail.py`; the command in `cli/authoring.py`. No new import cycles.

## References

- [argparse — Parser for command-line options, arguments and subcommands — Python documentation](https://docs.python.org/3/library/argparse.html) — Official reference for building the `plan-tool merge` subcommand, including the `action='append'` pattern needed for the repeatable `--steps` flag and subparser wiring.
- [graphlib — Functionality to operate with graph-like structures — Python documentation](https://docs.python.org/3/library/graphlib.html) — Documents `TopologicalSorter` and `CycleError`, the basis for validating the merged dependency graph and rejecting cycle/dangling edges in `_apply_step_merge`.
- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Reference for defining the `MergeResult` (mirroring `SplitResult`) and frozen/immutable plan structures used by the pure list→list transform.
- [How to use temporary directories and files in tests — pytest documentation](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Covers the `tmp_path` fixture pattern the project's hermetic unit tests rely on for exercising merge transforms and detail-file migration in isolation.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Reference for `safe_load`/`safe_dump` used to read and rewrite the machine-readable YAML frontmatter that is the source of truth when renumbering and rewiring merged steps.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- The *decision* of when to merge — that's the granularity advisor (`step-granularity-advisor.md`), which emits the `granularity-merge` findings this executor acts on.
- Auto-merging in the convergence loop unattended — recommend-only there, like split.
- Non-adjacent (gapped) / disjoint (unconnected) merge sets — explicitly rejected with `CreateError`, not handled. An internally-branching but connected set still collapses legally.

## Risks

- **Collapsing a set could create a dependency cycle or dangling edge.** Severity: correctness. Mitigation: `_apply_step_merge` validates by constructing a dry-run `Plan` and raises `CreateError` on a malformed graph, never mutating its input list.
- **Merging steps that have already run/started would restructure completed work.** Severity: data loss. Mitigation: `_merge_is_safe` (mirror of `detail._split_is_safe`, honoring the non-PENDING run-state gate) runs before any mutation, blocking on a non-PENDING **member or any step after the merged region** — since the merge renumbers/renames every downstream step and would otherwise orphan its id-keyed run state; optional operator confirmation lives in `cmd_merge` (step 3), not the orchestrator. `_confirm_merge` itself **mirrors `_confirm_split` exactly** — default NO, and non-TTY *declines* (returns `False`). The unattended-proceed behavior is the **CLI-layer bypass**: `cmd_merge` *skips calling* `_confirm_merge` entirely when `getattr(args, "yes", False) or not sys.stdin.isatty()`, so an explicit `--yes` or a non-interactive context runs the merge to completion rather than auto-declining with rc 2 (reconciling with split's CLI path, which carries no interactive confirm gate at all — only `_split_is_safe` raising). The bypass is safe only because `_merge_is_safe` gates run-started steps first — it blocks every non-PENDING member or downstream step before the bypass can mutate anything, so an unattended merge never restructures completed work.
- **Naively stapling N detail bodies yields an incoherent detail file.** Severity: quality. Mitigation: re-author/re-audit through the `detail` authoring + seven-section gate, *informed by* the merged steps' prior bodies, so the merged step has one coherent Implementation/Tests/etc. The combine feeds each folded step's **full body** to the re-author via a `$prior_body` placeholder — no silent truncation; the `_MAX_PROMPT_FILE_BYTES`-truncated sibling seam is a tone/structure reference only, not the content-combine mechanism, so the re-author absorbs the complete member bodies rather than a ~4 KB prefix of each.
- **Ambiguous (non-adjacent or disjoint) merge sets.** Severity: correctness. Mitigation: reject a gapped or unconnected set with a clear `CreateError` rather than guessing the collapse; an internally-branching but connected set is unambiguous and collapses legally.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool merge <name> --steps 3 --steps 4` folds the contiguous chain into a single step and renumbers remaining ids to contiguous `1..N`.
- `--steps` requires ≥2 ids (the only check `cmd_merge` enforces at the CLI layer); contiguity + connectivity are validated by `_apply_step_merge` inside `merge_steps` before any mutation, after the optional `_confirm_merge` gate.
- Merging a non-adjacent (gapped) or disjoint (unconnected) set raises `CreateError` and mutates nothing; an internally-branching but connected set collapses legally.
- A merge whose set contains any non-PENDING (run/started) step — or whose merged region is followed by any non-PENDING step — is refused by `_merge_is_safe` before any mutation.
- `_apply_step_merge` is a pure list→list transform: it validates via a dry-run `Plan`, raises `CreateError` on cycle/dangling edge, and never mutates its input list.
- After merge, the merged step's `depends_on` equals the union of the set's external deps (remapped), internal edges drop, dependents of any merged step repoint to the single merged id, and edges after the region shift down by `len-1`.
- Detail files for folded-away ids are archived (best-effort, non-destructive, via `_archive_existing_detail`) and downstream detail files are renamed via the mirror of `detail._migrate_downstream_details_after_split`.
- A re-author/re-audit failure *after* the pre-author mutations is **leave-and-resume, not rollback**: `merge_steps` persists the renumbered-but-undetailed merged step and the already-renamed siblings, leaves the folded-away files as orphan `NN-` files for ids no longer in the plan, and surfaces the failure; recovery is re-running `plan-tool detail` against the persisted plan and deleting the orphans by hand (no auto-rollback, no auto-clean). A step-2 `TestMergeSteps` case drives a failing invoker and asserts this orphan/renumber posture.
- The combined detail file is re-authored/re-audited — informed by the folded members' **full prior bodies** fed through a `$prior_body` placeholder without silent truncation (not the `_MAX_PROMPT_FILE_BYTES`-truncated sibling seam) — and passes the seven-section gate.
- `plan-tool merge` returns a `MergeResult` mirroring `SplitResult`.
- Unless `--no-detail` / `--no-completeness` is passed, the completeness audit loops and applies blocking findings to convergence under `--iterate`.
- `merge_steps` assigns the merged step the **dominant** `change_type` among its members (precedence `feature > refactor > non-code`); the result is a single pure-typed step with **no** `type_impure` flag, **no** schema change, and **no** completeness-loop suppression — a refactor+feature fold yields a `feature` step that converges with no mixed-step finding to suppress.
- The command's exit code reflects completion, not findings (exit-code convention).
- No new import cycles are introduced (`backend.py`/`create.py`/`detail.py`/`cli/authoring.py` layering stays acyclic).
- `docs/cli/` (drift-guarded) and the split-documented sections of `PLAN_FORMAT.md` / `RUNBOOK.md` are updated to cover `merge`.

## Deferred

- Wiring `granularity-merge` findings from the `step-granularity-advisor` to auto-invoke this executor — recommend-only for now; closing the decision→execution loop is a separate change once the executor is proven.
- A `--dry-run` diff preview that renders the before/after step graph — the flag exists, but a rich graph-diff renderer is postponed in favor of the basic no-write path.
