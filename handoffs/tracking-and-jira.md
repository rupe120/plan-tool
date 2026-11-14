# Tracking, Jira and backlog

Work tracking, the Jira board and tickets, backlog guards, branch hygiene and the settled tracking decisions. Each section below is one change or route in this workstream, ordered by the date it was opened; new work in the workstream appends a section here instead of creating a file (`README.md` § "Naming").

| Section | Opened |
| --- | --- |
| [Team handoff: tracking-model decisions and remaining work](#team-handoff-tracking-model-decisions-and-remaining-work) | 2026-09-17 |
| [Unpushed `main` code review](#unpushed-main-code-review) | 2026-09-21 |
| [first Jira tickets, the short ticket format, and the `run` merge guard](#first-jira-tickets-the-short-ticket-format-and-the-run-merge-guard) | 2026-09-24 |

## Team handoff: tracking-model decisions and remaining work

*Opened 2026-09-17.*

The tracking-model decisions are recorded in `docs/TRACKING.md`, `CONTRIBUTING.md`, `docs/RELEASING.md` and `docs/evidence/README.md`. Only the owner-held items below remain open.

### Open owner items

- **Future Architect promotion criterion** (decision 7): proposed as "land `plan`-route changes without the same `plan-correctness` finding recurring across rounds". `CONTRIBUTING.md` now says internal contributors may rotate with no fixed file-owner roster, which may supersede it. Record one sentence in the `CONTRIBUTING.md` Architect section, or record the criterion as dropped.
- **Bitbucket host settings** (decision 2), UI only: the required-approval count and the merge-queue setting on `main`. `CONTRIBUTING.md` lists both as "Deliberately not yet decided".
- **Finish the Jira configuration** (decision 11) through `docs/how-to/jira-management.md`. Confirm done, or name what remains.
- **Bucket C to readiness, per entry** (decision 7): proposed `declined`, since `BACKLOG.md` § "Readiness lens" and `docs/TRACKING.md` already say to relabel an entry when it is next touched. Owner confirms.
- **PR #14 `CLAUDE.md` commits** (`b0b21e8c`, `8ecef0c2`, `bdd8e6b1`): the PR is squash-merged and the commits are not on `main`. Owner confirms the review requirement is closed.
- **One stale citation** in the archived detail `docs/implementation-plans/archive/plan-details/roadmap-decision-settlement/07-document-settlement-route-retire-every.md` (line 77 cites `BUG_BACKLOG.md:275`): proposed `declined`, because the file is frozen (`README.md` § "Policy") and an archived completed plan has no next re-audit. Owner confirms. Also listed in `docs-and-onboarding.md`.

## Unpushed `main` code review

*Opened 2026-09-21.*

| Field | Value |
| --- | --- |
| Review range | `origin/main..main` (69 commits), then each round's own fix commits; base `f0f4c3ab` |
| Checks run | `/code-review` (report-only), effort `high`, four rounds |
| Current disposition | **Converged after 4 rounds.** An earlier "Converged" call made on a partial round-2 report was retracted. Rounds 3-4 were consistency polish on the loop's own edits, not new runtime defects. |

Findings R1-1 through R4-14 other than those below are `fixed` or `refuted` and are not carried. The materialize-disposition tag and the `RoadmapEnvironmentalError` rc=1 rule are recorded in code and tests (`plan_tool/cli/roadmap_cmd.py`, `tests/cli/test_roadmap_cmd.py`). `plan_tool/roadmap_revision_run.py` no longer exists, so the declined findings about that module (R2-10, R4-7) are void.

- **R2-1 / R4-1 — `run_roadmap` teardown `OSError` replaces a successful result.** Disposition: `tracked` in `BUG_BACKLOG.md` (heading "`run_roadmap`'s primary success path can discard a fully-completed `RoadmapResult`…"). The fix is a disposition-contract decision.
- **R4-8 — bindings hashed twice from one `content`** (`roadmap_candidate_review.py`, `roadmap_candidate_run.py`): pre-existing, no correctness impact. **Disposition:** `pending` — not filed; a numbered `BACKLOG.md` slot costs more than the item is worth. Do a bind-once-reuse pass when either function is next touched. (Source: "noted, not filed"; set to `pending` by the owner 2026-09-29.) `handoff-directory.md` § "Still open" cites this item.

Out-of-range / recall-mode findings: *(none)*.

## first Jira tickets, the short ticket format, and the `run` merge guard

*Opened 2026-09-24.*

The ticket format, tier rules and promotion procedure live in `docs/TRACKING.md`, `docs/how-to/jira-management.md` and `.claude/skills/jira-ticket/SKILL.md`. Only the open owner items below remain. Jira state was not read when this section was compressed.

### Open owner items

1. **Merge guard on by default.** `run` refuses on the default branch, or until the plan and a detail file for every committed step are on `origin/<default>`. It shipped default-on (`CHANGELOG.md` 0.1.0; `docs/how-to/pipeline/run.md`; `project_config.require_merged_plan`). No confirmation of the default is recorded; the alternative is opt-in per repository. Owner confirms.
2. **`DIRECTIVES.md` reversal** (`c8d2022b`): "the plan merges before `run`" replaced "merge only after the plan is complete" (`integrations/shared/DIRECTIVES.md`). It is a canonical directive change that needs `architect`-tier review; none is recorded. Owner confirms reviewed or accepted.
3. **`#387`** stays out of the first batch; `BACKLOG.md` #387 carries its open question. `BACKLOG.md` #425 still names the model "GPT-5.6 Sol"; `integrations/shared/DIRECTIVES.md` now says `gpt-6.1-sol`.
4. **Widen the third `beginner` condition?** `docs/TRACKING.md` § "Choosing the tier" reads "the same small edit at a few named sites plus their tests". `IPPT-4` (15 named sites in three docs, checked by a script) and `IPPT-8` (six comment edits, checked by a search and the suite) fit it loosely. Proposed wording: "named sites, each checked by a test or a script". Apply to TRACKING or drop.
5. **Board check by eye:** columns read To Do, In Progress, In Review, Done, with `IPPT-1`, `2`, `4`, `5`, `8` where the lead wants them. No `twg` read exposes column order. Do it or drop it.
6. **Saved-filter queries on multi-label tickets:** `labels not in (...)` (`docs/TRACKING.md`) and `labels != no-changelog` (`docs/RELEASING.md`) are untested against tickets with several labels (`IPPT-9`, `IPPT-10` carry several). Record the result under "Completion condition" in the Jira handoff, or drop.
7. **Two review findings without a closed-set disposition:** the `origin/main` then `origin/master` fallback when `origin/HEAD` is unset (documented in `docs/how-to/pipeline/run.md`; proposed `declined <documented>`), and a third near-copy of a config-block reader in `plan_tool/project_config.py` (`_read_run_block`, `_read_smell_block`, a third unverified; needs AST evidence before filing per `CLAUDE.md`). Owner sets `declined`, or files with machine-verified evidence.
