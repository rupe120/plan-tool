# Contributing to plan-tool

Welcome, and thanks for jumping in. `plan-tool` is built by developers, for
developers, and it's built with `plan-tool`. That makes contributing a
little unusual, in a good way: the tool you're changing is often the tool
helping you change it.

This page covers the practical side. For the *why* behind the process, read
[`docs/explanations/development-model.md`](docs/explanations/development-model.md).

## The short version

1. **Set up:** clone, `uv sync`, install the git hooks.
2. **Pick a ready Jira ticket** using [Picking work](#picking-work).
   Backlog files hold discovery and triage records.
3. **Choose the route:** a direct edit, or a `plan-tool` plan.
4. **Work on a branch,** and commit before every `plan-tool` call.
5. **[Converge](docs/GLOSSARY.md#convergence-and-converged):** run the
   applicable audit, test, reconcile, and code-review loops until they reach
   one of three exits; then complete pull-request review before merge.
6. **Close the loop:** update the backlog entry, and leave a handoff if
   someone else will pick it up.

## New contributor path

Use this path when you are new to developing `plan-tool`. It gives you enough
context to make and review a small change before you take responsibility for a
plan-driven delivery loop.

| Stage | Read | Do next | Then |
| --- | --- | --- | --- |
| 1. Orient | [`README.md`](README.md) and this page's short version | State what the tool does and how developers and assistants share responsibility. | Set up the checkout. |
| 2. Set up and test | [Develop and test](#develop-and-test) | Run `uv sync`, a focused test, and install the git hooks. | Read the core working model. |
| 3. Learn the core model | [`TESTING.md`](TESTING.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), `CLAUDE.md` § Tests, [`BUG_BACKLOG.md`](BUG_BACKLOG.md) § Triage, and [`docs/explanations/development-model.md`](docs/explanations/development-model.md) | Trace one test from a module to its test file, then [choose a ready small item](#picking-work). | Make a starter change. |
| 4. Complete a starter change | [Direct edit or plan?](#direct-edit-or-plan) and [Driving a change to done](#driving-a-change-to-done) | Choose a doc fix, a small regression-tested bug, or a one-module direct feature; drive its edit → test → review loop to pull-request review. | Learn the plan route with an experienced contributor. |
| 5. Graduate to plan-driven work | [Experienced: mentoring the assistant through a loop](#experienced-mentoring-the-assistant-through-a-loop) | Run one small plan end to end with someone who has already driven the loop. | Take on an independent plan or deeper architecture work. |

**Save for later.** `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `RUNBOOK.md`
are lookup references, not first-week reading. Open them when your selected
work reaches a roadmap, persisted contract, or recovery question.

## Develop and test

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git,
and authenticate for repository access before cloning. See
[Install and update](docs/how-to/install-and-update.md) for source/version options.

```bash
git clone git@bitbucket.org:protagona/plan-tool.git
cd plan-tool
uv sync
uv run pytest tests/ -q -n auto                  # the full suite, in parallel (a minute or two)
uv run pytest -m "not integration" tests/ -q     # the fast loop while you work
uv run pytest tests/test_parser.py -q            # one focused test module
./scripts/hooks/install.sh                       # the pre-push + pre-commit hooks (please do)
```

`uv tool install --editable .` puts `plan-tool` on your PATH against this
clone. There's no separate lint or build step; pytest is the gate.

A few test conventions matter from day one. [`TESTING.md`](TESTING.md) has
the full guide.

- **Mirror the module:** `plan_tool/X.py` gets tests in `tests/test_X.py`.
- **Never let a test call a real backend.** Every function that shells out
  to a model takes an `invoker=` seam. `tests/conftest.py` raises if a test
  tries to spawn a real backend binary, and `TESTING.md` has the table of
  which seam to stub.
- **Keep tests hermetic.** Each test uses its own `tmp_path`. A failure that
  shows up only under `-n auto` means hidden shared state, so fix the test.
- **Break it to prove it.** To show a new test pins something, break the
  code it covers and watch the test go red.

### Git hooks

`scripts/hooks/install.sh` points this clone's `core.hooksPath` at the
tracked `scripts/hooks/` directory, installing two hooks.

The `pre-push` hook runs the test suite (`uv run pytest tests/ -q -n auto`)
and fails the push if anything is red, so a change can't land on a remote
while it breaks a module it never touched. It only verifies; it never edits
files. The full output is left at `/tmp/plan-tool-prepush.log`.

One member of that suite is the generated CLI reference under
[`docs/cli/`](docs/cli/README.md). It fails when the reference has drifted
from the argparse parser. Regenerate it with
`python -m plan_tool.cli_reference --write`, commit `docs/cli/`, and push
again. The hook prints that hint when this is the failing test.

Bypass once with `git push --no-verify`; uninstall with
`git config --unset core.hooksPath`.

The `pre-commit` hook (`scripts/hooks/pre-commit`, pure-stdlib Python — no
extra dependency) scans only the lines a commit newly stages — not whole
files, so it never re-flags something already sitting in the repo — for
provider token formats (AWS, GitHub, GitLab, Slack, Google, Anthropic,
OpenAI, Stripe, private-key blocks) plus a generic
`key/secret/token/password = "..."` literal heuristic, and separately
refuses to stage credential-shaped filenames (`.env`, `id_rsa`, `*.pem`,
`credentials.json`, …). It only verifies; it never edits or removes
anything.

A real match: remove the value, rotate the credential if it was ever
pushed, and load it from an env var or secrets manager instead. A false
positive: add a trailing `# pragma: allowlist secret` comment on that one
line, or bypass a single commit with `git commit --no-verify`.

## Which plan-tool is running?

The global `plan-tool` command is an editable install of **one** clone.
Whatever that clone has checked out is what runs, whichever directory you
call it from. That matters when your change touches a prompt, a gate, or an
audit: the tool judging your plan may not be the build you're editing.

- Find the source: the `_editable_impl_plan_tool.pth` file under
  `$(uv tool dir)/plan-tool/lib/python*/site-packages/` names the clone.
- Run `git -C <that clone> log -1 --oneline` to see which commit is live.
- To try your branch's build on purpose, run `uv run plan-tool …` from your
  checkout.

`plan-tool --version` prints the release version; in a clone it reads
`pyproject.toml`, so a bump shows without reinstalling. It does not name the
commit, so between releases the `.pth` target plus that commit is still the
check. When it matters, note in your handoff which build ran.

### Portable checkout paths

Resolve a checkout before using its files; each developer can keep clones in a
different location. From inside the intended Git checkout:

```bash
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
```

Use repo-relative paths in plans, lessons, seeds and source references. Markdown
links are relative to the document containing them. If a command runs elsewhere,
resolve the intended checkout with `git -C <checkout> rev-parse --show-toplevel`
and quote the resulting root when constructing paths. An absolute pathname in a
saved report records that run's environment; it is not a required checkout path.

| Root in a cross-repository reference | How to resolve it |
| --- | --- |
| `<repo-root>` | The current source checkout's `git rev-parse --show-toplevel`. |
| `<installed-plan-tool-root>` | Inspect the editable-install `.pth` target described above; it can differ from the current checkout. |
| `<integration-consumer-root>` | Read `integration_consumer.checkout` from ignored `.claude/local/project-context.json`, then verify its Git root. |
| `<integration-infra-root>`, `<methodology-root>`, `<platform-sample-root>` | Select the intended external checkout for that reference, record its location in local context if needed, and verify its Git root and cited revision. Do not infer a sibling directory from another developer's layout. |

Replace root placeholders before running cross-repository commands. If an
external checkout is unavailable, state the evidence limitation rather than
substituting the plan-tool source tree.

## Picking work

- **You pick up work from Jira, not straight from the backlog files.**
  **[`BACKLOG.md`](BACKLOG.md)** and
  **[`BUG_BACKLOG.md`](BUG_BACKLOG.md)** are the assistant's discovery/triage
  log, not an assignment board: any contributor's Claude session keeps
  filing new entries there, and the project lead periodically triages the
  log into Jira tickets (and a `plan-tool` seed, when the work will run
  through the pipeline). The rule for which file a new entry goes in: *if
  someone filed an issue about this, would they be right?* If yes, it's a
  bug.
- **The board is Kanban.** Pull the top **To Do** ticket whose Tier label
  matches work you can own through to merge, skipping tickets labelled
  `needs-triage` or `decision-needed`. Put questions and status detail in
  comments. [`docs/TRACKING.md`](docs/TRACKING.md#jira-board) has the types,
  labels, statuses, and priority rule.
- Most entries carry an **`Approach:`** tag (`direct` or `plan-tool`) with a
  one-line reason. Treat it as the author's advice, not a contract.
  Entries are also gaining **route**, **readiness**, and **tier** labels.
  [`docs/TRACKING.md`](docs/TRACKING.md#labels-every-entry-carries) explains
  them — they're now aimed at the lead's triage call as much as at whoever
  builds the item, including how an older `Approach:` tag maps onto them.
- Before changing a claimed bug, run the test module that covers it. A
  passing test that pins the current behavior beats a convincing argument.
- **New ideas and out-of-scope findings become entries.** A note in `.tmp/`
  doesn't count, because `.tmp/` is scratch and gets deleted. Search the
  backlog files first (a promotion stub means the item is already on the
  board) and, where you have Jira access, the board itself, so nothing is
  filed twice.
- **New ids:** take one above the highest id ever added on any ref your clone
  has, after `git fetch --all`, and run the check again right before you publish
  ([`docs/TRACKING.md`](docs/TRACKING.md#adding-a-new-entry) has the command).
  Ids have collided before, and a team means more concurrent appends.
  `tests/test_backlog_ids.py` fails a duplicate on the first test run over a
  tree that holds both entries, such as your pre-push hook after a rebase or
  merge. Nothing runs it when two branches merge cleanly on the server, so the
  check before you publish is the one that matters.

## Direct edit or plan?

Implement **directly** when the change fits in one step, the acceptance
criteria are obvious, you can name the tests it affects, and no design
choice is open. Examples: a surgical bug fix, a single-file refactor, a flag
default flip. Direct work skips plan-tool's plan-authoring and execution
pipeline; edit the files yourself or with an assistant, then test and review
through the [direct review loop](#driving-a-change-to-done).

Write a **plan** when the change spans modules, needs its acceptance
criteria discovered, has visible phases, or involves a decision worth a
paper trail. When in doubt, plan: an unused plan costs one `create` call,
while an under-scoped direct change costs a lot of debugging later.
[`docs/TRACKING.md`](docs/TRACKING.md#direct-implementation-vs-plan-tool-plan) has the
full heuristic.

## Driving a change to done

**The plan route** is seed → `create` → bare-plan audit → `detail` →
detail-grounded audit → `run --commit` → `reconcile-code --all` → code
review → pull-request review. [`integrations/shared/DIRECTIVES.md`](integrations/shared/DIRECTIVES.md)
holds the canonical rules for every local loop, and
[`docs/how-to/common-workflows.md`](docs/how-to/common-workflows.md) walks each stage.

**The direct route** is: edit, test, review, fix, and review again, until it
converges. A one-shot direct edit gets none of the safety the pipeline
gives a plan, so drive the loop through the session. Both routes then get pull-request
review before merge.

Habits that apply either way:

- **Commit before every `plan-tool` call.** Each call then starts from a
  clean baseline, and `run`'s test-authoring gate depends on it. Pass
  `--commit` where the command accepts it (`run`, `detail`,
  `completeness-audit`, `completeness-apply`, `manifest sweep`).
- **Long commands go in the background.** Tee them to a named log such as
  `.tmp/<slug>.<verb>.log`, and start the pipe with `set -o pipefail` so a
  failure doesn't get reported as success.
- **Every loop ends at one of three exits:**
  1. it converged (clean, or two quiet low-severity rounds in a row);
  2. the findings have started describing your own last edit, so finish
     applying and go test;
  3. it isn't converging (the same finding keeps coming back, or the fix
     needs a redesign), so stop and ask.

  A falling count on its own is not an exit.
- **Point each reconcile verb the right way.** `reconcile-plan` treats code
  as the truth and edits the plan, so it's for plans that *haven't* run yet.
  After a plan has run, use `reconcile-code`, which treats the plan as the
  truth and edits the code.
- **Add a changelog fragment for anything a user would notice.** One file,
  `changelog.d/IPPT-123.md`, in the same branch.
  [`changelog.d/README.md`](changelog.d/README.md) has the format, and
  [`docs/RELEASING.md`](docs/RELEASING.md) says how a release collects it.
- **Fix the whole class.** A finding names one place where a problem showed
  up. Search for the same thing by name and by wording, fix every instance,
  and expect sibling tests that pinned the old behavior to go red. This is
  plain good practice. It's repeated everywhere because assistants need the
  reminder every time.

## Code review: where the craft gets taught

Code review is the last local loop before pull-request review, and it's the
one outside `plan-tool`. In Claude Code it's the `/code-review` command. It's
also where most of the lessons about working with assistants were learned.
These habits keep review loops short:

- **Review a pinned range.** Compute the base from the merge-base with the
  shared branch; don't type it by hand. One loop reviewed 20 of the 46
  commits it meant to cover, for about 11 rounds.
- **Keep a ledger.** Record every finding and its disposition in a tracked
  file under [`handoffs/`](handoffs/README.md#review-ledgers):
  - `fixed <commit>`
  - `refuted <evidence>`
  - `declined <reason>`
  - `tracked <backlog id>`
  - `pending`

  A finding that only lives in chat gets lost.
- **Run the test before believing the bug.** A reviewer's reading of the
  code is a hypothesis. The covering test settles it.
- **Hand the reviewer the settled decisions.** Each pass starts fresh, so a
  declined finding comes back unless the reviewer is told it was already
  decided.
- **Same function, new bug every round?** Stop patching. Write down the rule
  the code has to satisfy and every combination of inputs it depends on, or
  step back and ask the bigger question.
- **Reviewers read; they don't write.** The person driving the review picks
  how deep it goes.
- **The checker doesn't have to be independent.** The
  same author/session can author and check, at any tier. A different
  checker gets used sometimes, but only for efficiency — parallelizing, or
  a fresh session skipping the cost of re-deriving context — never because
  independence is itself required.
- **Stop on signal, not on a round count.** A round is
  clean, or two rounds in a row only add cosmetic findings: converged, go
  execute. New findings mostly describe the previous round's own fix, not
  the code: finish applying the batch, then go execute. The same
  finding/region keeps resurfacing with no shrinking severity: it's
  spinning — stop and escalate, to the human operator or the orchestrating
  session. There's no fixed round cap either way: a legitimate convergence
  can take twenty rounds, and cutting the loop off at a fixed number risks
  calling it "done" only because a counter ran out, which is exactly what
  masks a real defect a later round would have caught. Whether a given
  round reviews the full pinned range or a deliberately narrower focus is a
  judgment call each round, not a fixed rule; the tail converges on the full
  scope, potentially through several full passes.

[`docs/explanations/development-model.md`](docs/explanations/development-model.md#stories-from-the-review-ledgers)
has the stories behind each habit.

## Pull-request review: team checkpoint

A pull request is the team's checkpoint before a branch merges. It makes the
intent, evidence, and unresolved risk visible to people beyond the author.
It follows the applicable local audit, test, reconcile, and code-review loops;
it does not replace any of them. A draft pull request can show work in
progress, but request review only when the branch is ready for a bounded
review.

Before requesting review, give the team enough context to make a real call:

- the intended outcome, scope, and decisions that are already settled;
- the review range, computed from the merge-base with the target branch;
- the checks run and their result, including any known flake or limitation;
- the changelog fragment, or the reason the change needs none;
- the related backlog entry, deferred work, and handoff or review ledger.

During review, record every substantive comment and its disposition in the
ledger: `fixed <commit>`, `refuted <evidence>`, `declined <reason>`,
`tracked <backlog id>`, or `pending`. When feedback changes the branch, run
the affected tests and local review loop again, then tell reviewers what
changed and which decisions remain settled. Do not let a decision live only
in a thread or chat.

Before merge, the current head has passed its required local checks, every
requested review has a disposition, and any remaining work has a visible
owner or backlog entry. The remote's policy decides its required approval,
CI, and merge-queue settings.

**Remote of record: Bitbucket.** There is no CD/
deployment pipeline; the tool is installed by `git clone` plus an editable
`uv tool install` (see [Which `plan-tool` is running?](#which-plan-tool-is-running)),
not published; a release is a tagged commit with a changelog entry
([`docs/RELEASING.md`](docs/RELEASING.md)). The
[`bitbucket-pipelines.yml`](bitbucket-pipelines.yml) pipeline runs the suite on
every pull request and on `main`. **Deliberately not yet decided:** the
required-approval count and the merge-queue setting on `main` — both are
branch-restriction settings in the Bitbucket repository, not something a
tracked file can hold.

### Review plan artifacts apart from code

**Plan artifacts** are everything under `docs/implementation-plans/` (plans,
details, saved audit reports, step statuses) and `plan-seeds/`. They can
outweigh the code they describe: a single pull request can carry 145 plan files
beside 45 other files. Reviewing them apart keeps each pull request about one
thing.

A plan-route ticket has two review moments:

1. **Before `run`: land the plan on `main` through a plan pull request.**
   `main` is protected — never push plan artifacts directly to it, even when
   credentials allow it. Branch from `main`, hold only plan artifacts on it
   (the seed commit, the generated plan, every session-directed audit
   correction, each `detail --commit`), push after each bounded commit, and
   merge its pull request once the completeness-audit gates have converged the
   bundle — this is also the review moment the Architect uses
   ([`docs/TRACKING.md`](docs/TRACKING.md#labels-statuses-and-comments)).
   `plan-tool run` enforces the same requirement: it refuses on `main` itself,
   and refuses until the plan and a detail file for every committed step are
   on `origin/main` (`git fetch` first) — verify the merged pull request
   through that remote branch before creating the implementation branch. No
   split is needed. Do not pass `--skip-merge-check`, or set
   `run.require_merged_plan` to `false` in `.plan-tool/config.json`, to get
   past the refusal when the bundle hasn't actually landed; merge the plan
   pull request, or ask the user.
2. **After `run`: split the branch.** It holds code plus step statuses and
   saved reports. Run `scripts/split_pr.py IPPT-123` (`--dry-run` previews the
   file counts). It builds `IPPT-123-plan` and `IPPT-123-code` from the
   branch's total change since its merge-base with `origin/main`, one snapshot
   commit each. Push both, open a pull request for each with `bkt pr create`
   ([`DIRECTIVES.md`](integrations/shared/DIRECTIVES.md#opening-bitbucket-pull-requests-with-bkt)),
   and lead both titles with the ticket key. The pre-push hook runs the suite on each push.

Merge the code pull request first when the plan branch marks steps done, so
`main` never records work that has not landed.

The script never touches your working tree or your branch and never pushes. It
creates both branches or neither, and it refuses a dirty tree or a target
branch that already exists. A change with no plan artifacts needs no split.

## Three ways in

These describe **work**, not people. Pick the path that matches the job in
front of you.

### Getting started: learning to read the assistant's work

Follow the [new contributor path](#new-contributor-path). It is the canonical
read → do → next sequence for a first contribution; this section keeps the
three role-shaped paths together for later reference.

### Experienced: mentoring the assistant through a loop

- **Read:** [`integrations/shared/DIRECTIVES.md`](integrations/shared/DIRECTIVES.md)
  in full, [`SEED_FORMAT.md`](SEED_FORMAT.md), [`PLAN_FORMAT.md`](PLAN_FORMAT.md),
  [`DETAIL_FORMAT.md`](DETAIL_FORMAT.md), [`docs/how-to/pipeline/audit.md`](docs/how-to/pipeline/audit.md),
  [`docs/how-to/pipeline/run.md`](docs/how-to/pipeline/run.md), and [`docs/explanations/lessons-learned.md`](docs/explanations/lessons-learned.md).
- **Owns:** getting a loop to an exit, deciding what each finding is worth,
  and reviewing newcomers' changes.
- **Hands up:** a question about scope, a persisted contract, or a policy
  that turns up mid-work goes to an Architect. It doesn't get quietly folded
  in.
- **Graduating in from Getting Started:** after landing
  1-2 `beginner`-tier direct items reviewed clean, drive an `experienced`-tier
  plan yourself, with an Architect reviewing the plan/detail bundle before
  `run`.

### Architect: guarding the intent

- **Read:** [`MISSION.md`](MISSION.md), `CLAUDE.md` § Architecture and
  § "Convergence policy boundary", `DATA_CONTRACT.md`'s version-evolution
  policy, [`docs/history/backlog-decisions.md`](docs/history/backlog-decisions.md),
  and the [AI-assisted development policy](docs/reference/ai-assisted-development-policy.md).
- **Owns:** decisions about persisted contracts, blocking policy, audit
  meaning, and plan scope; the stop and backtrack calls; and the rules the
  assistants are given.
- **Also owns:** turning each decision into ready work, including a small
  starter slice when one exists, and keeping a floor of at least 5
  `beginner`-tier `ready` items available.
- **Current Architect: the project owner (Josh Russo), the sole holder.**
  Internal contributors may rotate, and public contributors may submit pull
  requests. The maintainer selects reviewers per change according to its scope
  and review tier; there is no fixed file-owner roster. Request architect-tier
  review explicitly for the surfaces named in
  [`docs/TRACKING.md` § "Choosing the tier"](docs/TRACKING.md#choosing-the-tier),
  including `CLAUDE.md` rule changes.

## Where things go

| What | Where |
| --- | --- |
| Forward-looking work | [`BACKLOG.md`](BACKLOG.md) |
| Behavior that's wrong today | [`BUG_BACKLOG.md`](BUG_BACKLOG.md) |
| The rules for tracking work | [`docs/TRACKING.md`](docs/TRACKING.md) |
| Choosing the review tier | [`docs/TRACKING.md`](docs/TRACKING.md#choosing-the-tier) |
| Unreleased changes, and the release notes they become | [`changelog.d/`](changelog.d/README.md), [`CHANGELOG.md`](CHANGELOG.md) |
| Choosing a version and cutting a release | [`docs/RELEASING.md`](docs/RELEASING.md) |
| Closed decisions that shouldn't be reopened | [`docs/history/backlog-decisions.md`](docs/history/backlog-decisions.md) |
| Seeds and plans | New seeds: `docs/implementation-plans/plan-seeds/`; plans: `docs/implementation-plans/`; retained seeds: `plan-seeds/` |
| Handoffs and review ledgers | [`handoffs/`](handoffs/README.md#review-ledgers) (tracked) |
| Scratch notes and logs | `.tmp/` (ignored; name files `<slug>.<what>`, never `notes.md`) |
| Design-level lessons | [`docs/explanations/lessons-learned.md`](docs/explanations/lessons-learned.md) |

## Commits

- **One concern per commit.** Keep plan and doc changes apart from the code
  they motivate, and a refactor apart from the feature built on it.
- **Name the concern in the subject line.**
- **Ticket keys link work to Jira, and the links are many-to-many.** One
  ticket usually takes several commits, and a commit can serve more than one
  ticket.
  - **Branch:** `IPPT-123-short-slug`, named for the ticket the branch delivers.
  - **Commits you write:** the subject stays on its one concern. When a
    commit serves several tickets, list them all in a trailer,
    `Refs: IPPT-123, IPPT-130`. If it serves two only because it bundles two
    concerns, split it.
  - **Commits a `--commit` flag writes for you** have subject-only messages
    with no key. The branch name and the pull request carry the link for
    those.
  - **Pull request:** the title leads with the primary key, and the
    description lists the others.
- **Assistant attribution is welcome here.** This is an internal project, so
  commit trailers and notes about which assistant or model helped are fine.
  Client repositories follow their own rules.
- **Don't push red.** The pre-push hook runs the suite for you.

## Writing docs

- **Plain English, to the point, a little light-hearted, and nothing
  lost.** Keep the numbers, ids, and paths; say them simply. This covers
  backlog entries and ticket text too
  ([style guide](docs/reference/documentation-style.md#backlog-entries-and-tickets)).
- **Present and future tense.** Describe what the thing is and does. History
  earns a place only when a reader needs it to act correctly, and then it
  gets a date. (`CLAUDE.md` § "Documentation is forward-looking" has the
  full rule.)
- **Self-contained.** If an example comes from somewhere else, copy the
  facts in. Don't link to someone's clone or scratch folder.
- **Scan first, then read deeply.** State the purpose, show the normal path,
  and use tables, state matrices, or flows where they make the contract easier
  to follow. [`docs/reference/documentation-style.md`](docs/reference/documentation-style.md)
  gives the shared standard and review checklist.
- **Regenerate `docs/cli/`** after changing a flag.

## The rules the assistants follow

[`CLAUDE.md`](CLAUDE.md) (`AGENTS.md` is the same file) and
[`integrations/shared/DIRECTIVES.md`](integrations/shared/DIRECTIVES.md) are
the instructions coding assistants read when they work on or with this
tool. Read them as the mentor's notebook: they tell you what the assistant
has been told, which is also a good guide to what to expect from it.
