# Roadmap stack propagation — code review ledger

The record of how BACKLOG #460 (plan `roadmap-stack-propagation`) was judged. The
change shipped in pull request #40 (merged as `cba602a8`); its plan shipped in #39.
One ledger, updated in place. Closure label (see `handoffs/README.md` § "Retention"):
**converged**.

| | |
| --- | --- |
| Review range | `bfc8b261..3991adb7` (pass 1 reviewed `bfc8b261..0af115dd`) |
| Last logic-changing commit | `ec368b44` |
| Branch head at merge | `6a834bb1`; merge commit `cba602a8` |
| Checks run | Full suite green at 13,465 passed, 67 skipped; touched test files (1,061 tests) green after the last docs commit; `reconcile-code --all` twice, steps 1-3 at 0 critical / 0 high / 0 medium / 0 nits both times (sweep 1's unreadable step 3 verdict was re-run clean); tests added by the review fixes mutation-checked (breaking the replacer, title normalization, frontmatter handling or the Jira whitelist turns them red); the tests the plan's steps authored were not mutation-checked |
| Reviewer | Four independent headless `claude -p` sessions at effort `high`, report-only |
| Disposition | Converged: passes 3 and 4 were consecutive, independent, and clean against `3991adb7`, which contains `ec368b44` |

## Settled decisions (hand to each reviewer)

- The tool owns the `## Stack` heading of a draft seed: it renders the section from the
  accepted version and replaces any model-authored `## Stack`. The checkable fact is that
  the seed's section equals the accepted rows.
- Hosting rows render `id`, `facet`, `value`, `product`; store rows render `id`,
  `category`, `sharing`, `product`. A missing product renders the explicit open wording.
  A plan row with no components renders the hosting rows alone.
- `Stack` is the fourth, last entry of `GUARDRAIL_BODY_SECTIONS`; `create` preserves the
  seed's section verbatim and the scope fence carries it into detail prompts.
- Conflict surfacing, notes, or technology-name comparison inside `create` and `detail`
  are deliberately not built; the plan audit is the contradiction check (decided
  2026-10-08).
- The Jira handoff deliberately omits `## Stack` (a whitelist).
- A draft not rematerialized after the accepted version changes keeps its older stack;
  detecting that is an accepted limit left to the existing digest.

## Findings

Pass 1 (`bfc8b261..0af115dd`; static traces, finding 1 reproduced by hand):

1. Model-authored heading variants (`## stack`, `## STACK`, `##  Stack`, `## Stack ##`) survived the replacer (4 of 5 variants won), so `create` read the model's text as the plan's stack; medium-high. fixed df4397f5: reuses the reader's own rules via `scope_fence.h2_section_spans`.
2. Replacer's fence scanner differed from the validator's (indentation, info strings). fixed df4397f5, same root cause.
3. A removed model section ran to the next H2 while readers end at the next H1. fixed df4397f5, same root cause.
4. Dead error branch and a second read of the accepted version that could cite a different version. fixed df4397f5: version id comes from the same load.
5. "No accepted store is used" asserted a fact for a plan row with no components. fixed df4397f5: the line says the components name no store.
6. Product values with newlines or markdown could start a heading inside the section. fixed df4397f5: values render on one line; blank product reads as open.
- D1 (“replaces any model-authored `## Stack`” held only for the exact spelling) fixed df4397f5; D2 “four recognized headings” comment declined (accurate); D3 prompt line width declined (cosmetic); D4 stale `#460` references refuted (none remain on the merged tree).

Pass 2 (`bfc8b261..df4397f5`):

7. The replacer scanned the draft's YAML frontmatter: a column-0 `## Stack` comment there deleted the closing `---` and the provenance block (reproduced); low-medium. fixed ec368b44: replacer works on the body only and returns frontmatter bytes untouched; two tests.
8. Nothing pinned that the Jira handoff omits `## Stack`, so a consolidation over `GUARDRAIL_BODY_SECTIONS` would turn it on silently; test gap, medium. fixed 1f8f5bb3.
- D5 `ROADMAP_FORMAT.md` superseded empty-stores sentence, D6 `SEED_FORMAT.md` and D7 `docs/how-to/pipeline/audit.md` heading lists missing the tool-written Stack: fixed 3991adb7. D8 `PLAN_FORMAT.md` “author-supplied” declined (section explains the tool-written case).

Pass 3 (`bfc8b261..3991adb7`): no logic findings; both pass-2 findings re-checked closed. D9 `SEED_FORMAT.md` lead sentence still says “three” headings: declined (accurate for a hand-authored seed; next sentence names the fourth). D10 `PLAN_FORMAT.md` wording: declined, as D8.

Pass 4 (`bfc8b261..3991adb7`, emphasis on tests and callers; 2,676 touched-file tests pass): no logic findings. W1 cross-cutting-listed-components test alone would stay green under another source of `store-checkout`: declined (the exclusion test covers that mutation). D11 `JIRA_FORMAT.md` silent on the Stack omission, D12 a prompt-key test comment claiming an assertion it does not make, D13 trailing blank line: fixed 93d53d41.

## Closure

Converged. The window restarted at each of `df4397f5` and `ec368b44`; after `ec368b44` two independent passes were clean. The two plan-canonical sweeps (steps 1-3 clean; sweep 1's unreadable step 3 verdict re-run) ran before and after the review fixes. Documentation-only commits after `ec368b44` did not reset the window.

## Run record

Steps 3 and 4 were committed by the tool. Steps 1 and 2 were accepted by hand
(`RUNBOOK.md` § "Accept as complete"): each failed the full-suite gate on a defect in the
step's own test or a pinned prompt line break; fixed, suite green, step committed
(`2621def3`, `9a771741`), status set to `done` (`edabfee5`, `b77efc10`). A bare re-run
after a hand fix cannot advance a step (the model changes nothing, so the test-authoring
gate fails, and `--commit` refuses a dirty tree). The recovery is written into
`integrations/shared/DIRECTIVES.md` on branch `docs/directives-hand-fix-on-step-test-failure`;
the gap is tracked below.

## Tracked

Items marked tracked are live in `BACKLOG.md` and `BUG_BACKLOG.md` since pull request #41
merged (`49ec6c5f`).

- **tracked** #463 — `run --step N --accept`, so a hand-fixed step is certified and marked
  done through the tool; the three "re-run" messages name it. Additions recorded on #455
  (the retry prompt never carries `status_note`) and #87 (the no-edit re-run's false
  positive, cause 1 again).
- **tracked** `BUG_BACKLOG.md`, "`create --from-existing` reads several seed sections
  without first removing the seed's YAML frontmatter" — the residual `create`-side
  counterpart of finding 7, with a reproduction and a counted enumeration.
- **tracked** #464 — twelve assertions pin a line break inside wrapped prose; the step 2
  hand fix was restoring one.

## Audit replay

Owed by plan step 3; gates nothing. A throwaway bare one-step plan whose `## Stack` listed
`store-app-db` as PostgreSQL while its `## Architecture` and step 1 used a local SQLite
file was run through `plan-tool --model claude-sonnet-5-5 completeness-audit <plan>
--iterate -y` (2 conceptual passes, bare-plan stage). Both passes reported the
contradiction as a HIGH `plan-correctness` finding quoting both texts, with a fix offering
either choice. One sample, bare-plan stage, `limited` confidence; no detail-grounded replay
or Integration-sized plan. The audit prompt needs no change on this evidence.

## Next session — pickup

State as of 2026-10-08, with `origin/main` at `49ec6c5f`.

| Item | State |
| --- | --- |
| #38, #39, #40, #41 | merged (backlog arc; plans #460, #461 and #462; the #460 implementation; the follow-up entries and the first version of this ledger) |
| `docs/directives-hand-fix-on-step-test-failure` | **local only**, two commits (`512e3aff`, `7fc2567b`): the directives section, a runbook pointer, and a router row in the three skills; no pull request yet |
| #461 plan | on `main`, `planning`, 0 of 8 steps run |
| `stash@{0}` | an abandoned first attempt at plan step 1, superseded by the committed step; safe to drop |

Do these in order. Only 2 still needs a model call (1 is done).

1. **Integration-style audit replay — done 2026-10-08.** See § "Audit replay" below. No action owed.
2. **Re-audit #461's detail bundle.** Its last fixes (duplicate concern, non-removal
   ownership, the narrowed "never unseen" claim) were never re-audited. Plan edits go
   through a plan branch and a plan pull request (the default branch is protected, and
   `run` refuses until the plan is on `origin/main`). `plan-tool status roadmap-stack-layer`
   reports **stale detail** for steps 2 and 3. That is advisory and expected: the step
   fingerprints hash a step's title, files and the plan's scope sections, and the titles
   changed after the details were written. The detail files were edited by hand to match,
   so their content is current. Do **not** run `detail --force` to clear the warning; it
   regenerates the files and discards those edits. Read `grounding.py` for a refresh route
   before touching it.
3. **Decide the directives branch's pull request.** It changes a shared rule, so the
   project `CLAUDE.md` asks for architect review. One small addition is still owed on that
   branch before it goes up: a sentence saying a step that never ran under the tool has no
   `status:` line, so the manual flip to `done` is an insertion that must be verified
   before committing.
4. **Execute #461 only after 2.** Step 7 of that plan extends the `## Stack` renderer,
   which is now shipped. Run it with `run roadmap-stack-layer --commit -y` from a branch
   off `main`.

Housekeeping, only when asked: `git stash drop` for the stash above; the merged local
branches whose remotes are gone belong to `handoffs/branch-cleanup.md`; local
`main` is far behind, so fast-forward it before branching.

## Operating notes for the next session

- A `run` step that fails the suite gate on its own test defect is recovered by hand
  (`integrations/shared/DIRECTIVES.md` § "When a `run` step's own tests fail", once it is
  on `main`; until then on the branch above). Never hand-fix and then bare re-run, and
  never use `--skip-merge-check` to get past the refusal.
- When flipping a step to `done`, assert that the edit landed before committing, and stop
  the command chain if it did not. A failed flip leaves the step runnable, and the next
  `run` re-drives it.
- A `reconcile-code` verdict reading "could not summarize (no findings block)" is not
  clean. Re-run that step.
- Headless review sessions: launch through the expansion of the `claude-personal` alias
  (`CLAUDE_CONFIG_DIR=~/.claude "$(command -v claude)"`), pass the prompt on
  stdin (the variadic `--allowedTools` swallows an argument prompt), grant the findings
  file with `Edit(//<absolute path>)` only, and verify findings dynamically yourself:
  probes through `uv run python -c` are refused inside the headless sandbox.
- This machine's shell has no `timeout`, does not expand aliases in tool calls, and its
  `sed -i` needs an empty suffix argument.
