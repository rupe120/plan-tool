# Roadmap plan-row selector documentation

The starting-point guide describes artifact publication, selected seed
materialization/review and separate plan creation. It no longer claims stage
runs emit seeds or implementation plans. Related README, common-workflows,
roadmap-guide and TTRPG demo examples use `<roadmap-plan-id>` instead of
`first-plan` / `my-first-plan` and explain its existing `plans[].id` source.

The plan row and declared seed path exist before first materialization. The
selector is neither a seed filename nor a newly assigned plan name. Omitting
it processes all recoverable drafts. Actual reported draft/promoted paths
replace assumed basenames, and later create remains a separate action.

## Scope and sites

Invariant: intake guidance distinguishes existing roadmap plan-row selection
from generating a seed and creating an implementation plan. Identifier searches
cover `first-plan`, `my-first-plan`, `--materialize` and `plans[].id`; vocabulary
searches cover emitted plans, draft plan seeds and plan naming. The five
reading surfaces above receive the same bounded clarification. Runtime CLI
syntax, stage-4 decomposition and lifecycle behavior are unchanged.

Sources: `plan_tool/cli/roadmap_cmd.py` resolves the optional materialize operand
against accepted row classifications; `ROADMAP_FORMAT.md` defines plan ids and
seed destinations; `docs/how-to/roadmap.md` section 7 owns later seed state.

- Seed-path and CLI-reference tests: **15 passed**.
- All five surfaces name the selector; the added guide anchor resolves.
- `git diff --check` passes.
- Two independent actual built-in Claude Code reviews target
  `e1eae0c0a..c2cb06e3f903d364753e09ecf8011d19d2aac1b4`, with
  `claude-sonnet-5-5 --effort high`. Round 1 finds no correctness defect;
  round 2 returns only low-severity wording feedback. This is **low-yield
  convergence**, not a claim that both reviews have no advisory output.
- Retained wording advisories: explicitly name materialize output as the
  source of the repo-relative draft path (the seeds view is for state), and
  say the tool's later create handoff reuses the selected roadmap ID. Current
  examples use that same placeholder and actual reported paths, so neither
  changes the selector contract. Optional line wrapping is also retained.
- Other candidates are refuted or declined: explained placeholders are
  substitution notation; no-ID versus selected-ID examples are alternatives;
  missing per-state lifecycle detail belongs to the linked guide. A current
  draft's selected-ID refusal does not contradict what the selector identifies.
- The fulfilled starting-point backlog entry is removed. Runtime promotion
  summary wording remains separately tracked and unchanged.

Review 1 session: `3046877a-4e3b-4c16-a60c-c30dc4814c00`.

Review 2 session: `fe1891fe-3f2e-47d6-9a27-7a703bc7f04b`.
