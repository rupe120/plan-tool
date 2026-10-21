# Handoff: developer docs and work tracking

## Status

**Done and green; open for review as
[PR #13](https://github.com/rupe120/plan-tool/pull/13).** The work sits on
branch `docs/developer-front-door`, based on `origin/main` at `b1114783`.

The branch also carries the convergence-evaluation withdrawal described below.
The evaluator plan did not earn implementation; the convergence judgment stays
in the orchestrating session, and BACKLOG #367/#369 carry the resulting direct
authority-migration work instead.

The goal was to reshape the project docs for a team of developers who both
use `plan-tool` and use it to change `plan-tool`. The README is now a short
front door. The reference material lives in focused guides, and the backlog
rules have their own home. All of it is written in one voice (plain, to the
point, a little light-hearted, nothing lost), with the developer framed as
the guardian and mentor of the coding assistants.

## What landed

| Commit | What it does |
| --- | --- |
| `652c18e7` | Moves the README's reference sections verbatim into `docs/COMMANDS.md`, `WORKFLOWS.md`, `ITERATION.md`, `OPERATIONS.md`, `BACKENDS.md`, and `GATES.md`. Links from other docs follow; two doc-sweep tests re-point at the new files. |
| `755f6d73` | Fixes six links that were already broken in the docs the split touched. |
| `06d4cac0` | Rewrites [`README.md`](../README.md) as a developer front door. Adds [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`docs/DEVELOPMENT_MODEL.md`](../docs/explanations/development-model.md), and a module map in [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md). |
| `9460a204` | A plain-English pass over the six reference guides. |
| `f4260749` | Retires the `completeness` command name (about 45 places) and corrects the `--iterate` defaults against the parser. Only `create` defaults on; `detail` and `completeness-audit` default off. |
| `0b9ab03a` | Files the `GateCleanCandidate` import-order test flake in [`BUG_BACKLOG.md`](../BUG_BACKLOG.md) (RISK). |
| `d222a338` | Moves about 600 lines of backlog rules into [`docs/TRACKING.md`](../docs/TRACKING.md). Adds the route, readiness, and tier labels and the tier checklist. |
| `1e6f2c79` | Replaces the never-shipped `.agents/plan-tool.sh` wrapper path with `plan-tool` (72 places). |

## How it was checked

- **Links:** a link checker covers relative paths and GitHub anchors. Every
  touched file ends with zero broken links.
- **Facts:** the voice pass was guarded by a script that compares old and new
  text. Every heading, inline code span, link target, and number had to
  survive. Test-pinned text stayed verbatim.
- **Meaning:** two independent reviews compared each rewrite with its
  original. They found five places where the meaning had drifted (for
  example, "is sound" softened to "a good sign"), and all five were reverted.
- **Stories:** the case studies in `docs/DEVELOPMENT_MODEL.md` were checked
  against their sources before being copied in. Two details were corrected
  that way, and one story was dropped because its record no longer exists.
- **Tests:** the full suite passed on every batch: 12,251 passed, 190
  skipped.

One run hit the known `GateCleanCandidate` flake. That module passes 18/18 on
its own and reads none of these docs, and the re-run passed.

## Settled in this work: don't reopen

- **AI attribution (owner, 2026-09-14).** The no-attribution rule covers
  client work only. This project is internal, so assistant commit trailers
  and provenance notes are welcome here, as `AI_SDLC_POLICY.md` describes.
  `CONTRIBUTING.md` § Commits states it.
- **Framing (owner, 2026-09-14).** The developer is the guardian and mentor
  of the coding assistants. Assistant behavior is described as plain fact
  to plan around, not as something to fight. Ordinary engineering hygiene,
  such as whole-class fixes, running tests, and small commits, isn't
  presented as new. It's written down often because assistants need the
  reminder.
- **Voice (owner, 2026-09-14).** Plain English, to the point, a little
  light-hearted, with no detail lost.
- **Self-contained docs (owner, 2026-09-14).** Anything that ships stays
  inside this repo. Examples from elsewhere get copied in with their facts;
  never link to another clone or a scratch folder.
- **Tier is a judgment, not a computation.** A keyword-based sizing of the
  backlog misjudged entries in both directions. For example, it let in #55,
  which runs into Lesson 15, and left out #266, which is a good starter item.
  Nothing derives, scores, or gates on a tier. `docs/TRACKING.md` records
  this.
- **Where test-pinned text lives now:**
  - The roadmap source-admission, structural-route, and stage-feedback
    guidance is in `docs/WORKFLOWS.md`.
  - The model-family tokens are in `docs/BACKENDS.md`.
  - The routing arcs, the Now board table, and the #328 record stay in
    `BACKLOG.md`.
  - Anyone moving that text updates the guide maps in
    `tests/test_roadmap_format.py` and `tests/test_model_specs.py`.
- **`completeness` mentions left on purpose:**
  - the persisted sidecar `kind` value;
  - ARCHITECTURE's list of the code that imports the granularity module;
  - RUNBOOK's "`completeness` primitive";
  - the dated lessons in `LESSONS_LEARNED.md`;
  - archived plans, seeds, and reports.
- **Convergence scope reset (2026-09-15, superseded by the withdrawal
  below).** This 2026-09-15 reset gated the 2026-09-14 proposal to retire
  `completeness-apply` and launch several evidence adapters together behind
  evaluator evidence (BACKLOG #367/#369). The withdrawal below returns to the
  2026-09-14 direct-retirement direction instead: `completeness-apply`,
  direct pipelines, and other application authorities are scoped for direct
  migration under #367/#369, not gated on an evaluator that did not ship.
- **Historical convergence stop (2026-09-15, superseded by the withdrawal
  below).** Three committed bare-plan audits did not converge: the
  material conceptual set moved from 6 findings
  ([16:15 report — retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)),
  to 5 ([16:59 report — retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)),
  then to 7 HIGH findings
  ([17:34 report — retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)).
  At audit time the latest report was current but budget-limited and returned
  `no-qualified-current-evidence`. Its new requirements touch unique plan
  selection, grade-bound persistence, audit-produced direct evidence,
  protected code inputs, exclusive run-log events, and trajectory
  classification. Do not add detail files or implement the then-current plan by
  extending that list. The withdrawal below supersedes the required-decision
  state entirely. This history does not reopen or block BACKLOG #367 or #369;
  they remain separately selectable and unassigned.

- **Run-grade evaluator reset (2026-09-15, superseded by the withdrawal
  below).** V1 was narrowed to one explicit final run-grade plan-audit report
  for one uniquely resolved plan, validating only the report's canonical-plan
  and run-grade detail-bundle binding at envelope construction. This reset is
  kept as provenance for why the evaluator's judged surface had shrunk to
  almost nothing by the time it was withdrawn.

- **Second plan-audit evaluator convergence stop (2026-09-15, superseded by
  the withdrawal below).** The owner-confirmed narrow slice completed one
  structural repair round and then two manual conceptual snapshots: the
  [18:21 report — retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)
  contained two HIGH gaps, while the budget-limited
  [18:42 report — retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)
  contained four HIGH gaps and reported `no-qualified-current-evidence` with
  unconfirmed coverage — one interlocked fixed-judge contract (explanation
  authority, confirmed-low-yield evidence, command-bound generic
  backend/recovery policy, and exclusion of user configuration and rules).
  All four were checkable at HEAD as real code/plan defects, not model
  variance turned into prose; see the withdrawal record below for why the
  slice was withdrawn instead of fixed.

- **Convergence-evaluator withdrawal (owner-confirmed, 2026-09-15).** 25
  bare-plan audits across 2026-09-14/15 (28 plan commits, 95 findings) never
  converged: the scope moved under the audit four times — four evidence
  contexts collapsed to one, 13 steps to 8, persistent run logs to none — and
  each reshape brought new surface rather than the same gap recurring. Only
  16 of the 95 findings touched the judge seam at all (invocation profile,
  input isolation, outcome eligibility, output gate); none asked what the
  judge would conclude. The conceptual reason: after the v1 narrowing the
  eligibility gate leaves the model almost nothing to decide (at most
  `converged` vs `continue` on a qualified low-yield report with remaining
  material findings), and the orchestrating session driving `plan-tool`
  already makes that same choice with more evidence (history, live code, the
  source seed) than the evaluator's envelope permits, without stacking a
  second judge on top of the audit. This also matches BACKLOG #231's
  2026-08-19 retirement: keep the convergence pause in the driving workflow,
  do not recreate it as a persisted classifier or CLI route. The plan and its
  plan-details bundle moved to
  [`docs/implementation-plans/archive/2-orchestrator-owned-convergence-eval.md`](../docs/implementation-plans/archive/2-orchestrator-owned-convergence-eval.md)
  with a superseded banner; its seed moved to
  `plan-seeds/archive/convergence-eval-plan-audit-v1.replaced.md`. BACKLOG
  #368 and #370–#375 (evaluator adapters and governance) are retired as
  moot. BACKLOG #367 and #369 continue as the direct
  `completeness-apply`/`apply_finding` authority migration this decision also
  motivated, decoupled from the evaluator's evidence gate — see
  `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md`
  item 10 for the durable record.

## Follow-up added to the branch

- [`docs/GLOSSARY.md`](../docs/GLOSSARY.md) defines the recurring plan-tool
  vocabulary, including the difference between the convergence process, an
  automated stop, and the convergence diagnostic.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md),
  [`docs/DEVELOPMENT_MODEL.md`](../docs/explanations/development-model.md), and
  [`handoffs/README.md`](README.md) make pull-request review the team checkpoint
  after local loops and give local/PR findings one durable ledger.
- [`docs/implementation-plans/archive/2-orchestrator-owned-convergence-eval.md`](../docs/implementation-plans/archive/2-orchestrator-owned-convergence-eval.md)
  and `plan-seeds/archive/convergence-eval-plan-audit-v1.replaced.md` record
  the withdrawn run-grade, explicit-report evaluator; see the withdrawal entry
  above and `backlog-arc-convergence-evidence.md` item 10. BACKLOG #367 and
  #369 retain the direct application-authority migration and inventory as
  separately selectable developer handoffs; #368 and #370–#375 are retired.
- The added internal links resolve. The fast suite passes: 11,432 passed, 158
  skipped.

## Open decisions for the owner

1. **Tracking model.** Options:
   - (A) one file per item, with a generated index;
   - (B) an external tracker only;
   - (C) a hybrid: the tracker holds status and assignment, the repo holds
     the scope contract;
   - (D) keep the single `BACKLOG.md`.

   The recommendation is A, or C if a tracker is already in daily use. D
   keeps a merge hotspot: about 14% of recent commits touch `BACKLOG.md`.
2. **Remote of record:** GitHub or Bitbucket. The PR, CI, and review
   tooling depend on the answer.
3. **Committed evidence.** Keep committing every saved report (4,334 files
   so far), or only the ones a PR or handoff cites.
4. **Code-review tail rules.** A round cap (three is suggested), reviewing
   only the new commits after round 1, and whether cleanup-only findings
   count toward convergence.
5. **Checker independence.** Whether the reviewer must be a different
   person, or can be a fresh session given only the review inputs.
6. **`CLAUDE.md` split.** Where the dated evidence moves, and who approves
   changes to the rules half.
7. **Persona tiers:**
   - tiers on work items only, or on people too (leaning items only, with
     explicit architect review on high-stakes surfaces);
   - whether to fold the readiness lens and bucket C into the readiness
     label, and whether to retire buckets A–E;
   - a minimum number of ready starter items (5 is suggested);
   - when a newcomer drives a guided plan;
   - who the first Architects are. Roughly 76 items look architect-tier by
     a rough keyword count, and today there is one Architect.
## Next actions

In rough order. Each is its own bounded piece of work.

1. **In the next clone, fetch `docs/developer-front-door` and read this
   handoff's convergence-evaluator withdrawal record. The evaluator plan is
   archived; do not revive it. BACKLOG #367 and #369 (the direct
   `completeness-apply`/`apply_finding` authority migration) remain
   unassigned until scoped. Review and merge
   [PR #13](https://github.com/rupe120/plan-tool/pull/13) when the documentation
   branch is ready** (owner).
2. **Resolve the backlog-id collision before other unpublished work lands.**
   A development clone holds unpublished entries numbered #365 and #366.
   `origin/main` already has different #365 and #366 entries. Before
   publishing that work, renumber its entries above the highest id on
   `origin/main`, and update every place that cites them, by number and by
   name. BACKLOG #233 (a duplicate-id check) would catch the next one; it's
   also a good starter item. (The check is `tests/test_backlog_ids.py`.)
3. **Tag the backlog.** Draft route, readiness, and tier labels for the 17
   bug entries (including the two filed in this work) and the 60 open direct
   entries, then have an Architect review them.
   Tidy the fields while you're there:
   - 40 entries have no `Approach:` tag, or a nonstandard one;
   - about 45 have no usable `Effort:`;
   - 11 are marked done but still listed: #181, #191, #217, #295, #305,
     #309, #331, #333, #334, #337, #351.
4. **Fix the two filed code bugs:**
   - `create` and `reprocess` still print the retired `plan-tool
     completeness` (direct);
   - the `GateCleanCandidate` flake needs its import order reproduced in a
     fresh interpreter first.
5. **Remaining documentation:**
   - **Review case studies:** tracked pages under `docs/review-case-studies/`,
     one per lesson. The sources are review ledgers kept outside this repo,
     so copy the facts in before those are cleaned up.
   - **`docs/TRACKING.md`:** its "Iterate convention" block repeats
     `DIRECTIVES.md` and has drifted. Replace it with a pointer.
   - **`DIRECTIVES.md`:** describe the code-review tail as a
     backend-neutral step with its own stop rule, once decision 4 lands.
   - **`CLAUDE.md`:** split rules from dated evidence, once decision 6
     lands.
6. **Tooling candidates.** File these as backlog entries; don't bundle
   them:
   - `--version`, or the source commit, in `--help`;
   - the tool build recorded in saved reports;
   - a CI workflow;
   - a PR template;
   - a changelog and release tags;
   - the code-review-loop skill tracked in the repo, with `install-skill`
     support.

## Things worth knowing

- **Which `plan-tool` runs.** The global command is an editable install of
  one clone, so it runs whatever that clone has checked out.
  `CONTRIBUTING.md` § "Which plan-tool is running?" shows the check. Do it
  before trusting a run that depends on a recent change.
- **A red full suite isn't automatically your change.** Read the error
  first. If it's `GateCleanCandidate` "not fully defined", it's the filed
  flake: run the module alone, then re-run the suite.
- **Doc sweeps: check the claim, not just the name.** Renaming
  `completeness` to `completeness-audit` at first kept a wrong default and
  made it look current. The parser, not the prose, settled it.

## Fence for the next session

- Don't mass-tag the backlog without Architect review.
- Don't rebase or renumber another clone's commits without the owner's
  go-ahead.
- Don't turn the tier into a computed or gating field.
- Code fixes for the two filed bugs go through their own backlog-entry
  route, not a docs change.
