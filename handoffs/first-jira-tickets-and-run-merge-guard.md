# Handoff: first Jira tickets, the short ticket format, and the `run` merge guard

This handoff records where the first `IPPT` tickets stand, the ticket format and
tier rules settled while writing them, and the owner decisions still open. It is
the entry point for the next session. The policy lives in
[`docs/TRACKING.md`](../docs/TRACKING.md); the promotion procedure and the
recurring loop live in [`jira-management.md`](jira-management.md).
This file does not repeat either.

## State on 2026-09-25

| Surface | State |
| --- | --- |
| Repository | `origin/main` last contained `bc212011` of this work. Everything after it is local and unpushed (`git log origin/main..HEAD`): this handoff's first commit (`34341f8c`), the `jira-ticket` skill and its two lint-fix rounds (`73ef318b`, `aeba15f8`, `64d5c8ef`), the `IPPT-8` promotion stub (`7db46ee9`), and the commit that records this state. |
| Last full suite | 13788 passed, 189 skipped (2026-09-25), on the tree through `73ef318b`. The 2026-09-24 run through `9e504d6e` (the merge guard) was 13787 passed, 190 skipped; the one-test difference is not investigated. Later commits change only `.claude/skills/jira-ticket/` and one `BUG_BACKLOG.md` stub; on the stub, `test_backlog_ids.py`, `test_backlog_readability.py`, `test_data_contract.py`, `test_drift_detection.py`, and `test_roadmap_format.py` passed (348 tests). |
| Jira `IPPT` | Seven tickets, all in To Do (below). `IPPT-3` was created, then withdrawn and deleted; its number is not reused. |
| Beginner floor | 5 of 5, met 2026-09-25. The saved-filter query returns `IPPT-1`, `IPPT-2`, `IPPT-4`, `IPPT-5`, and `IPPT-8`. |
| To Do rank | `ORDER BY Rank ASC` returns `IPPT-1`, `2`, `4`, `5`, `6`, `7`, `8` (2026-09-25): creation order, so no reordering of To Do is visible. |
| Jira connector | Reads and writes work through `twg` and the `mcp__atlassian__` tools (2026-09-25). On 2026-09-24 one connector refused a read of `IPPT` and board `3971` because it could not verify that its saved default site belongs to the organization's site; the cause is not recorded. If a call is refused, report it and do not retry a write. |

| Ticket | Type | Priority | Tier label | What |
| --- | --- | --- | --- | --- |
| `IPPT-1` | Bug | High | `beginner` | `plan-tool sweep` can crash printing its report when the repository path goes through a symlink. |
| `IPPT-2` | Bug | High | `beginner` | `create` and `reprocess` tell users to run `plan-tool completeness`, which does not exist. |
| `IPPT-4` | Task | Medium | `beginner` | 13 broken links in `RUNBOOK.md` and two dated handoffs (backlog #426). Every target is known. |
| `IPPT-5` | Bug | Low | `beginner` | `ruff` reports an undefined `Plan` in `tests/cli/test_completeness_cmd.py`. |
| `IPPT-6` | Bug | Low | `experienced` | Docs still describe the deleted `--strict-intent` check. Covers `docs/TRACKING.md`, `lessons-learned.md` Lessons 3 and 18, and one table row. |
| `IPPT-7` | Story | Medium | `experienced` | `install-skill --integration` builds its choices by scanning `integrations/*/SKILL.md` (backlog #389, option (b)). |
| `IPPT-8` | Bug | Low | `beginner` | Six code comments say the reconcile prompts emit a `## Decision` block that holds the triage tags; no prompt does. Comments only (filed `95d87993`, created 2026-09-25). |

Each ticket's text is in Jira. Its backlog entry is now a promotion stub (`IPPT-8`'s in `7db46ee9`).

## Settled: do not reopen

- **A ticket is a short brief** (2026-09-24, owner direction: the first versions
  ran 500 to 1,300 words). Shape and length: `docs/TRACKING.md` § "Ticket
  contents". The full entry stays in git at the commit before promotion.
- **Open questions are settled before a ticket is created** (2026-09-24). The
  session researches them and puts the lead's choices to the lead. A
  `decision-needed` ticket is created only when the answer needs research the
  session cannot do.
- **Tier rules** (`docs/TRACKING.md` § "Choosing the tier", edited 2026-09-24 at
  the owner's direction after real tickets misfired):
  - `experienced` needs a behavior change that spans modules, not a module count.
    The same small edit at named sites is `beginner`.
  - A gate counts only for its behavior, or a message a test, CI, or a retry
    correction to the model reads.
  - A doc counts only when the change alters what it says about behavior; a link,
    path, or wording fix is exempt.
  - A `beginner` precedent may be an existing pattern in the code, named by file
    and line.
- **Section names:** "Where to start" (`beginner` tickets) and "Why this tier".
- **`IPPT-3` is withdrawn.** Wrapping `log.run_interrupted(...)` in
  `contextlib.suppress(KeyboardInterrupt)` changes nothing the run log records:
  in every case tried, the event and the termination reason were identical with
  and without the guard. Only which `KeyboardInterrupt` propagates differed. The
  record and its reopen condition are in
  [`docs/history/backlog-decisions.md`](../docs/history/backlog-decisions.md)
  § "Retry-wait second-interrupt guard".
- **`IPPT-7` uses option (b)**, the on-disk scan. It falls back to
  `choices=None` when the tree is missing or holds no `SKILL.md`, so the existing
  "no bundled SKILL.md" error reports it.
- **`IPPT-6` includes Lesson 3 and Lesson 18** of `lessons-learned.md`, because
  they describe the same removed apparatus.
- **Issue types follow the first-match table.** Backlog #389 is a Story (bucket
  A); #426 is a Task (bucket E).
- **`IPPT-5` gained a `Stop / defer` line** (2026-09-25, on the owner's go-ahead).
  `docs/TRACKING.md` § "Ticket contents" requires the section and the ticket had
  none; its entry never carried one either, so the line is new: stop and comment
  if the fix needs a change outside the one test file. No other part of the
  ticket changed.

## Owner decisions still owed

1. **The `run` merge guard is on by default.** `run` refuses on the default
   branch, or until the plan and a detail file for every committed step are on
   `origin/<default>`. That changes behavior for every user, so it carries the
   fragment `changelog.d/run-requires-merged-plan.md` (a minor bump under
   `docs/RELEASING.md`). It is on `origin/main`; no confirmation of the default
   is recorded. The alternative is to narrow it to repositories that opt in.
2. **The `DIRECTIVES.md` reversal** (`c8d2022b`) replaced "merge only after the
   plan is complete" with "the plan merges before `run`". That is a canonical
   directive change and needs `architect`-tier review. None is recorded.
3. **`#387` stays out of the first batch** (architect tier; the owner is editing
   that section). Its open question: does `DIRECTIVES.md` state the one-line
   model rule itself, or cite the personal `~/.claude/CLAUDE.md`? `install-skill`
   copies `DIRECTIVES.md` into consuming repositories, where that file does not
   exist. `#425` (`BACKLOG.md:861`) still says "GPT-5.6 Sol"; the current name is
   GPT-6 Sol (`gpt-6-sol`).
4. **Widen the third `beginner` condition?** It reads "the same small edit at a
   few named sites plus their tests". `IPPT-4` is 15 named sites in three docs
   with no test to change, checked by a script, and its ticket says the fit is
   loose. `IPPT-8` is a second case: six comment edits in three modules, no test
   to change, checked by a search and the suite, and its ticket says the fit is
   loose. The proposed wording is "named sites, each checked by a test or a
   script".
5. **Board check by eye:** the columns read To Do, In Progress, In Review, Done,
   and `IPPT-1`, `IPPT-2`, `IPPT-4`, `IPPT-5`, `IPPT-8` sit where the lead wants them. No
   `twg` read exposes column order.

## 2026-09-27: priority labelling, selection order, and IPPT-11

The feature backlog had a ranking basis (`BACKLOG.md` § "Priority
(mission-grounded)") but no per-entry label, so a session promoting from this
handoff's shortlist had no way to tell whether a candidate was actually the
next-highest-priority one. This closes that gap:

- **New `Principle` label** (`docs/TRACKING.md` § "Principle (`BACKLOG.md`
  only)"): one of `MISSION.md`'s five stable principle slugs, `none` (with a
  reason), or `untriaged`. Applied as a first pass to the 21 entries the
  T-band lists already named; 5 came back `untriaged` because their text
  doesn't tie to a principle (`#49`, `#54`, `#36`, `#89`, `#366`) — still
  owed a judgment call, not a machine one.
- **T1–T5 renamed "priority band"** everywhere except the arc filenames
  (`backlog-arc-tier-t1.md` etc., left alone so citations still resolve). It
  was colliding with the Jira `Tier` label (`beginner`/`experienced`/
  `architect`), a different axis (which the work needs, not how urgent it is).
- **New selection order**, `docs/TRACKING.md` § "Choosing what to promote
  next": unblocked `BUG_BACKLOG.md` BUG first, then `BACKLOG.md` ready
  entries ordered by `Principle`, then RISK/MINOR bugs (ranked against P1–P3
  features at the lead's judgment, deliberately not fixed by rule), then
  everything else. The `jira-ticket` skill gained a matching "Choose what to
  promote" step: build a ranked shortlist, verify the top candidates against
  the tree, show the shortlist and stop for the user's pick — promotion no
  longer starts from the first item in whatever order a candidate list happens
  to be written in.
- **Jira priority stays source-based, not `Principle`-mapped** — confirmed
  as a deliberate non-goal (`docs/TRACKING.md` § "Priority"), so the board
  and this label can't rank the same work two different ways.
- **Verified against the tree and promoted `#102`** (deterministic
  seed-extraction alias pre-fill; not on this handoff's 19-item shortlist,
  found via the new `Principle` ordering) → **IPPT-11** (Story, Medium,
  `experienced` + `plan`), with `plan-seeds/seed-extraction-alias-prefill.md`
  authored and the ticket description updated to name it. `BACKLOG.md`'s
  `#102` entry is now a promotion stub.
- **Verified three more candidates still live**, promoted the same session
  (below): `#69`, `#38`, `#30`.
- **Guard tests green after all of the above**: `tests/test_backlog_ids.py`,
  `test_backlog_readability.py`, `test_data_contract.py`,
  `test_drift_detection.py`, `test_roadmap_format.py` — 348 passed.

### Same day, continued: IPPT-12 through IPPT-15

- **Removed the stale create-wizard `BUG_BACKLOG.md` entry** (shortlist row 1
  below) as its own commit — confirmed fixed by `c48f29af`.
- **`#4`/`_classify_dest` → IPPT-12** (Bug, Low, `beginner`). Kept `beginner`
  on review: the `docs/ARCHITECTURE.md` status-list line only adds a value to
  an existing enumeration, and the ticket's own "Why this tier" already names
  the loose fit.
- **`#69` → IPPT-13** (Story, Medium, `experienced` + `plan`), direction
  chosen: wire `--apply`/`--iterate`, not document-only. Tracing the
  "existing loop" turned up a problem with the entry's own premise:
  `_iterate_reconcile_loop` (`cli/reconcile.py:2129`) is bound to a single
  `step_id` and drives `run --mode reconcile`'s per-step path — it does not
  fit `reconcile-plan`'s whole-plan / `--step` / `--all` scope. The ticket and
  seed (`plan-seeds/reconcile-plan-unattended-apply.md`) call for a new driver
  that follows that loop's *shape*, not a literal reuse, and this moved the
  entry from `direct` (its stale `Approach:` tag) to `plan` route.
- **`#38` → IPPT-14** (Story, Medium, `architect` + `plan`). A second premise
  problem: the entry proposes a new `reconcile_recommended` plan-frontmatter
  field and says existing plans "default to `maybe`" as if that's a soft
  addition. `DATA_CONTRACT.md`'s break rule says otherwise — `Plan`/`Step`
  declare `extra="forbid"`, so *any* new frontmatter key is a break, even an
  optional one. That requires a `PLAN_FORMAT_VERSION` bump and the explicit
  transition contract `MISSION.md` principle 2 requires (compatible
  upgrade path, fixtures for both the upgrade and its refusal boundary) —
  none of which the entry's own text names. The ticket and seed
  (`plan-seeds/reconcile-recommended-scoring.md`) make that contract the
  first thing the plan must design, and the tier moved to `architect` on
  that basis (an explicit `docs/TRACKING.md` criterion: "a persisted
  contract or version").
- **`#30` → IPPT-15** (Story, Medium, `experienced` + `plan`), scoped to its
  plan-body half only, per the entry's own stated dependency split — the
  detail-file half stays out of scope pending `#312`.
- Both premise problems were user-facing decisions, not silent
  reclassifications: each was surfaced and confirmed before drafting.
- **Guard tests green again**: `tests/test_backlog_ids.py`,
  `test_backlog_readability.py`, `test_data_contract.py`,
  `test_drift_detection.py` — 289 passed.
- **Still open:** the five `untriaged` `Principle` entries (`#49`, `#54`,
  `#36`, `#89`, `#366`) still want a judgment call; none of this session's
  local commits are pushed.

### 2026-09-28: board-wide lint pass, and the jira-ticket skill's audit gap

Linted every live `IPPT` ticket, per the new "Audit existing tickets" step
this session added to `.claude/skills/jira-ticket/SKILL.md`. 14 of 15 pass
with 0 errors; `IPPT-4`, `6`, `9`, `12`, `14`, `15` carry a word-count
warning, hand-checked on `IPPT-4` and `IPPT-6` as a genuine per-site list,
not padding.

**`IPPT-10` fails: 7 lint errors.** It uses a different template entirely
(`## Symptom`/`## Scope`/`## Verification`/`## Affected files`/`## Origin`,
no `Source:` line) and carries a stray `bug` label (redundant with its
issue type; not in `docs/TRACKING.md`'s label table). Its backlog origin was
legitimate — a `BUG_BACKLOG.md` promotion stub existed and was correctly
removed on shipment (`2b9395fa`) — but it was created 2026-09-25 13:18,
about 5.5 hours *after* the `jira-ticket` skill existed (`73ef318b`), so it
was hand-written outside the skill rather than through it: a compliance
gap, not a missing routing path.

**User decision, 2026-09-28: leave `IPPT-10` as historical.** It shipped;
rewriting its description has no functional effect, only the record. Do not
re-raise this as an open question — the closed-work exception is settled.

**Skill updated to catch the next one**, not this one: a new "Audit existing
tickets" section (loop `lint_ticket.py --jira` over `project = IPPT`) and a
new lint check flagging an issue-type-shaped label (`bug`/`story`/`task`/
`epic`/`subtask`). No routing change was needed — `IPPT-9` and `IPPT-10`
both trace to ordinary backlog entries and pick up the `roadmap` label per
the existing rules, so the gap was purely that nothing had run the audit
before this session asked for it.

### 2026-09-28, continued: an explicit `Route:` field

User question: for this team's first real exposure to plan-tool-integrated
ticket routing, do the tickets themselves make clear how to proceed — and do
`direct`-route tickets make clear they're *not* plan-tool work? Checked
every ticket type: no. A plan-route ticket either had no `Seed:` line at all
(`IPPT-9`, predates the convention) or a bare path with no verb (`IPPT-13`,
`14`); never the actual `plan-tool create --from-existing <path>` command. A
direct-route ticket (`IPPT-1`) had no explicit "implement directly" statement
either — both directions were inferred purely from the `plan` label's
presence or absence, cross-referencing `docs/TRACKING.md`.

**Fix:** `Route:` is now an explicit, always-present body field
(`docs/TRACKING.md` § "Ticket contents", third after `Source:`), naming the
route and its exact starting command; paired with `Seed:` for `plan`-route,
absent for `direct`-route. `lint_ticket.py` enforces the pairing (commit
`1758b68d`).

**Retrofit, user-decided 2026-09-28: only the still-open plan-route
tickets.** `IPPT-11`, `13`, `14`, `15` got the new `Route:` line (a
description edit, each re-linted clean). `IPPT-9` and `IPPT-10` are `Done` —
excluded, same disposition as the earlier `IPPT-10` decision: don't retrofit
shipped work. The 7 open direct-route tickets (`IPPT-1`, `2`, `4`, `5`, `6`,
`7`, `8`) are left as they are; a board-wide lint sweep after the retrofit
confirms exactly this set still fails on `Route:` and nothing else does.
This is a standing, accepted gap, not an oversight — don't re-raise it as a
new finding in a later audit pass.

## Next steps, in order

1. Take the owner decisions above.
2. Do the board check.
3. Run the saved-filter queries against a ticket that carries several labels.
   Not exercised as of 2026-09-27: `IPPT-9` (`architect`, `plan`, `roadmap`) and
   `IPPT-10` (`bug`, `experienced`, `plan`, `roadmap`) now carry several labels
   each, so `labels not in (...)` (`docs/TRACKING.md`) and `labels !=
   no-changelog` (`docs/RELEASING.md`) can be exercised against them without a
   new write. Record the result under "Completion condition" in the Jira
   handoff.
4. Keep the beginner floor at five. It is met today; as tickets ship, promote
   from the shortlist below or, for a `BACKLOG.md` feature entry, follow
   `docs/TRACKING.md` § "Choosing what to promote next" (added 2026-09-27).
   Find real candidates in the backlogs; do not relabel to fill the floor.
   Draft each ticket with the `jira-ticket` skill (which now runs its own
   "Choose what to promote" step first) and lint it before creating.
5. As each ticket ships, remove its stub and record its changelog disposition
   (`docs/RELEASING.md`).
6. Push the local commits (`git log origin/main..HEAD`) once the owner says to;
   the commits do not authorize it. Run the pre-push grep first (see "Things to
   know").
7. Judge the five `untriaged` `Principle` entries (`#49`, `#54`, `#36`, `#89`,
   `#366`) and give each a value (`docs/TRACKING.md` § "Principle").

## Potential Jira promotions (19-item shortlist)

This is a sourcing list, not approval to create tickets. It excludes promoted
items and the owner-tracked `BUG_BACKLOG.md` ROADMAP section. Start with the
ready, bounded work; settle a stated decision, gather the named evidence, or
profile before promoting an item marked otherwise. The source entry remains the
scope contract until promotion.

The shortlist is not the whole raw inventory. A mechanical source scan finds
242 active, unpromoted, non-parked records: 230 numbered `BACKLOG.md` entries
and 12 non-ROADMAP `BUG_BACKLOG.md` entries. The 19 below include all 12 of the
bug-backlog entries and seven selected `BACKLOG.md` entries, leaving 223 source
records to triage. Before any bulk promotion, remove owner-only roadmap routes,
resolve each entry's readiness and tier, check duplicates, and assign its
backlog-arc label where the source carries one. No current ticket carries an arc
label or is named in an arc document. The board's rank order is creation order
(state table).

| # | Candidate | Source | Promotion check |
| --- | --- | --- | --- |
| 1 | Three create-wizard phases leave their progress handle and heartbeat thread dangling when the invoker raises | `BUG_BACKLOG.md` RISK | **Verified 2026-09-27: already fixed** — all six call sites route through `_invoke_or_fail` (`c48f29af`), and `tests/test_create.py:8920` covers every phase. The `BUG_BACKLOG.md` entry is stale; remove it as its own docs commit rather than promoting. |
| 2 | `review_plan_full` captures its full audit-input snapshot twice | `BUG_BACKLOG.md` MINOR | Ready direct performance cleanup; choose threading the existing snapshot or a narrow fence helper. |
| 3 | `install-skill` Phase 1 and Phase 2 redundantly resolve paths and read source bytes | `BUG_BACKLOG.md` MINOR | Ready direct cleanup. |
| 4 | `_classify_dest` loses the already-known directory distinction in its generic collision result | `BUG_BACKLOG.md` MINOR | **Promoted 2026-09-27 → IPPT-12.** |
| 5 | Three documentation/backlog citations point to nonexistent `prompts/reconcile.md` | `BUG_BACKLOG.md` MINOR | Ready, but the `CLAUDE.md` edit needs its required architect-tier review. |
| 6 | `_code_anchor_resolves` falsely reports bare-filename and negated-existence citations | `BUG_BACKLOG.md` BUG | Do not promote until a safe, structured remedy is selected; prose-intent inference is rejected. |
| 7 | Model-backed commands lack one complete terminal-failure receipt contract | `BUG_BACKLOG.md` BUG | Defer until the active Seed Ingestion Routing work clears its required checkpoints; keep migrations deliberately sliced. |
| 8 | `extract_h2_sections` defaults to non-fence-aware behavior although all current production callers opt in | `BUG_BACKLOG.md` RISK | Needs the stated compatibility review before a default change. |
| 9 | `install-skill` has a Phase 1/Phase 2 destination TOCTOU window | `BUG_BACKLOG.md` RISK | Keep low priority unless a concurrent-install use case appears; then choose lock versus atomic-create semantics. |
| 10 | Unmatched-code-fence guards have an unverified duplication/consolidation candidate | `BUG_BACKLOG.md` MINOR | Run the required AST-normalized identity check before ticketing any merge. |
| 11 | `renderer.py` hardcodes `mode == "run"` rather than the mutating-mode authority | `BUG_BACKLOG.md` MINOR | First resolve the import cycle; it is not a one-line ticket. |
| 12 | A registered plan can collide with the fixed model-response sidecar namespace | `BUG_BACKLOG.md` MINOR | Needs a design choice between validating adopted slugs and separating sidecar namespaces. |
| 13 | #54: audit the remaining auto-reconcile wiring with the established test pattern | `BACKLOG.md` #54 | Ready direct test slice; mirror the known `cmd_completeness` coverage. |
| 14 | #56: add a ruff/pre-commit gate | `BACKLOG.md` #56 | Needs rollout decisions for the existing violations and gate scope. |
| 15 | #80: consolidate verified duplicated argparse parent parsers | `BACKLOG.md` #80 | Re-derive the identical set and preserve intentional help/default variants. |
| 16 | #89: extend `--commit` to additional mutating commands | `BACKLOG.md` #89 | Scope the command set and each command's commit boundary before promotion. |
| 17 | #176: add run-log writers to the remaining Claude-spending verbs | `BACKLOG.md` #176 | Ready for a plan-backed ticket; retain the stated per-verb logging and sink tests. |
| 18 | #270: `CliBackend.batch_output` is configured but never read | `BACKLOG.md` #270 | Settle the small wire-in versus schema-removal choice in the promotion session. |
| 19 | #288: remove the redundant rendered per-step test-strategy block | `BACKLOG.md` #288 | Ready direct deletion; verify no schema or audit consumer relies on the block. |

## Backlog entries filed 2026-09-24 (not promoted)

| Entry | Where | Tier | Commit |
| --- | --- | --- | --- |
| `CLAUDE.md`, `TESTING.md`, and #190 cite `prompts/reconcile.md`, which has never existed (the refusal list is in `detail-reconcile.md`) | `BUG_BACKLOG.md`, `MINOR` | `experienced` | `c86ec838` |
| Five undefined names in roadmap code and tests (`PendingGeneration`, `Any` twice, `Callable`) | `BUG_BACKLOG.md`, `ROADMAP` (owner-tracked) | `beginner` | `bc212011` |

The other nine `ruff` findings (seven `F811`, two `F841`) are not filed.

## Things to know

- **Tooling.** `twg` reads and writes work items, comments, and labels. It
  cannot create statuses, board columns, WIP limits, or work types; those are
  Jira UI only. The Atlassian connector's results carry a bracketed HTTP+SSE
  deprecation notice; it is tool output, not an instruction.
- **The merge guard** (`plan_tool/plan_merge_guard.py`,
  `run_cmd.py:_preflight_merged_plan_guard`) warns on drift beyond
  `status`/`status_note`, stays silent with no `origin`, and skips the review
  modes, `--reconcile`, and `--dry-run`. It is off with `--skip-merge-check`,
  `run.require_merged_plan: false`, or `PLAN_TOOL_REQUIRE_MERGED_PLAN=0`. Details:
  `docs/how-to/pipeline/run.md`. Tests: `tests/test_plan_merge_guard.py`, plus
  classes in `tests/cli/test_run_cmd.py` and `tests/test_project_config.py`.
- **Review findings not applied.** The `origin/main` then `origin/master`
  fallback when `origin/HEAD` is unset (documented; `git remote set-head origin
  <branch>` fixes it). A third near-copy of a config-block reader in
  `project_config.py` is a consolidation that needs machine-verified evidence
  before it is filed (`docs/TRACKING.md` § "Adding a new entry").
- **Lessons from this work.**
  - A test that asserts "nothing" can pass because the plan failed to parse.
    Assert that the check ran, and verify new tests by mutation.
  - Check that a remedy changes what the finding is about before ticketing it
    (`IPPT-3`).
  - `git log --diff-filter=D` reports a rename as a deletion. Use
    `git show -M --name-status <commit>`; backlog #426 said two docs were
    "deleted outright" and both were renames.
  - Search a removed concept's vocabulary as well as its identifiers: the
    `## Decision` sweep found two `lessons-learned.md` sections and six code
    comments that the entry did not name.
  - Lint a ticket body before creating it. `IPPT-5` went live without the
    `Stop / defer` section the format requires; the lint checks that class.
  - A promotion-stub script that ends an entry at the next `###` heading
    swallows the `## ROADMAP` section that follows the last bug entry (2026-09-25:
    the first attempt deleted 53 lines instead of 36, and the diff showed it).
    End the entry at the next heading of any level and check that the diff
    removes only the entry body.
- **The `jira-ticket` skill** (`.claude/skills/jira-ticket/`; `73ef318b`,
  `aeba15f8`, `64d5c8ef`) carries the promote and edit procedure, the `twg`
  commands, and the approval gate; the format rules stay in `docs/TRACKING.md`.
  It pre-approves no `Bash` or Jira tool, so every Jira write still prompts.
  `lint_ticket.py` checks section shape only, on a draft (`--tier`, `--title`) or
  a live ticket (`--jira KEY`); exit 0 is clean, 1 has lint errors, 2 could not
  run. Deliberately not checked: whether the claims are true, whether the tier
  fits, whether an open question remains, whether the brief is good. On
  2026-09-25 it passed `IPPT-1`, `2`, `4`, `6`, and `7` (word-count warnings on
  `IPPT-4` and `IPPT-6`) and flagged `IPPT-5`'s missing section, since fixed.
  Two `/code-review` rounds found six low-severity parsing bugs in the lint (four,
  then two), each reproduced and fixed; a third round was not run, so this is a
  stop on low yield, not a clean audit. The script has no test in the repo
  suite. `twg` reports errors as JSON on stdout with nothing on stderr.
- **A pre-push grep for `claude`** matches the file name `CLAUDE.md` in the
  message of `c86ec838`. On the unpushed diff (2026-09-25) it also matches the
  `.claude/skills/` paths and the lint's own `co-authored-by|generated with`
  detection pattern. None is an attribution line, and no commit message hits.
- **`IPPT-6` is docs only.** Its fence excludes the six code comments (now
  `IPPT-8`) and the `prompts/reconcile.md` citations (the entry above).

## Files and scratch

- Ticket format and tier rules: `docs/TRACKING.md`. Procedure and loop:
  `handoffs/jira-management.md`. Drafting, creating, editing, and
  linting a ticket: `.claude/skills/jira-ticket/`. Withdrawn-item record:
  `docs/history/backlog-decisions.md`.
- Scratch (`.tmp/`, gitignored, disposable): the ticket drafts and generators;
  `ippt-3.guard-effect.experiment.py`, the throwaway script behind the `IPPT-3`
  withdrawal (the decisions-log record states its result); the `IPPT-8` and
  `IPPT-5` bodies (`ippt-decision-comments.*`, `ippt-5.*`); and the lint's
  reproduction scripts (`jira-ticket-skill.*`).
