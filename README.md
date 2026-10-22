# plan-tool

**plan-tool helps you plan, carry out, and verify substantial work with a coding
assistant.** It keeps the agreed intent, implementation steps, audit findings,
and progress in your repository so the work is easier to review, resume, and
hand off.

Use the **plan-tool skill** to guide your assistant through the workflow:
ground the plan in your codebase, surface missing decisions before
implementation, execute reviewed steps or export Jira stories, and check the
resulting code against the plan.

It is most useful when work spans dependent changes, multiple sessions, or team
handoffs. Small, straightforward edits can stay lightweight.

The mission and the grounding principles the codebase is built to obey live in [`MISSION.md`](MISSION.md). New here, or unsure whether your work is a good fit? [`docs/how-to/use-cases.md`](docs/how-to/use-cases.md) is the situation-first guide — when to use the tool and which path to take.

## Start here

Start with the assistant skill for guided planning and execution. Use the CLI
guides when you want to operate individual stages yourself.

| I want to… | Start here | Next |
| --- | --- | --- |
| Use plan-tool with my coding assistant | [Use with your assistant](#use-with-your-assistant) | [Install the CLI and skill](#install), then ask for [your first plan](#your-first-plan). |
| Explore or present a demo | [Demonstrations](docs/demos/README.md) | Choose an example and check its preparation status. |
| Choose a planning starting point | [Use cases](docs/how-to/use-cases.md) | Describe your idea, existing draft or project concept to the assistant. |
| Run, recover, or operate a plan | [How-to guides](docs/how-to/README.md) | Use the [Runbook](RUNBOOK.md) for a failed or surprising result. |
| Look up a command, format, or exact rule | [Reference](docs/reference/README.md) | Use the generated [CLI reference](docs/cli/README.md) for every option. |
| Develop plan-tool itself | [New contributor path](CONTRIBUTING.md#new-contributor-path) | Read the [architecture reference](docs/ARCHITECTURE.md) when the change needs it. |

## Use with your assistant

The skill gives Claude Code, Codex or Cursor a shared procedure for driving
plan-tool. Tell your assistant the outcome you want and the boundaries of the
work; it selects the stages, reads their results and brings decisions back to
you. The CLI provides the persisted plans, audit reports and execution state.

[Install the CLI and skill](#install), reload your assistant, and open the
repository you want to work on. Planning runs in that consuming repository;
keep the installation clone for the tool itself.

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git,
then keep a dedicated clone for the CLI that the skill invokes. `uv` manages
the Python runtime:

```bash
git clone git@bitbucket.org:protagona/plan-tool.git
cd plan-tool
uv tool install --editable .     # puts `plan-tool` on PATH (uv's bin dir)
```

Keep the clone: `--editable` reads its source directly. Source updates take
effect immediately; refresh the tool environment when dependencies or metadata
change, and refresh copied skills separately. See
[Install and update](docs/how-to/install-and-update.md) for release-tag versus
`main` selection, access requirements and the complete update procedure.

<a id="optional-the-agent-skill"></a>

### Install the assistant skill

Install the bundled skill once for your assistant. A user-level installation
makes it available across your projects. The skill includes the workflow rules
for seed authoring, both audit gates, execution and reconciliation.

| Assistant | User-level installation |
| --- | --- |
| Claude Code | `plan-tool install-skill --integration claude --user` |
| Codex | `plan-tool install-skill --integration codex --user` |
| Cursor | `plan-tool install-skill --integration cursor --user` |

The Claude and Cursor installers default to `~/.claude/skills/plan-tool/`;
Cursor [supports Claude skill directories](https://cursor.com/docs/skills).
Codex uses `~/.agents/skills/plan-tool/` and installs copies.

Reload your assistant session and confirm it discovers the installed skill.
Choose a supported destination with `--root` when your assistant uses a
different skill root. Install and authenticate the backend CLI used for model
calls as described in [Backends](docs/BACKENDS.md); installing a skill does not
install or authenticate that backend.

## Your first plan

Open the repository you want to change in your assistant. Choose a small,
independently testable change and ask:

> Inspect this repository and draft a grounded seed for [describe a small feature],
> with an explicit scope fence and verified references. Use the plan-tool skill
> to prepare a reviewed plan through the bare-plan audit, then details and the
> detail-grounded audit. At each seed, plan/audit and detail/audit boundary, link
> the artifacts, summarize changes and ask me for corrections or continuation.
> Wait for my response unless I explicitly delegate that transition. Bring material
> scope or design questions back to me and stop before implementation or export.

The assistant grounds a seed in the code, creates the plan, reviews the bare
plan, authors details, then reviews the complete bundle. It reads the findings
and applies judged corrections between audits. You decide material scope and
design questions and when implementation begins.

After reviewing the plan, details and audits, choose a separate follow-up request:

| Goal | Ask your assistant |
| --- | --- |
| Implement the reviewed work | “Use plan-tool to execute this plan, then reconcile the code against the plan and review changes to convergence.” |
| Inspect status | “Inspect `my-plan`, saved reports and any active invocation; report the current state and next decision without implementing.” |
| Resume within the agreed scope | “Inspect the plan, reports and original invocation first. Only after its confirmed exit, use its recorded outcome to resume the next incomplete stage within my requested scope.” |
| Prepare work for a team | “Use plan-tool to export this reviewed plan as local Jira stories.” |
| Start with a larger concept | “Use the plan-tool skill to turn this concept into a roadmap before creating individual plans.” |

Ask for execution or export separately after detail review. Local export includes
stories and their paired developer handoff; ask for links, a change summary and
validation results. Tracker publication requires a separate request.

During long commands, ask the assistant to report progress and monitor the original
invocation to confirmed exit. Quiet output, checkpoints and backend completion do
not establish command completion or authorize an overlapping invocation. Follow
[monitoring and safe recovery](integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely).
See the [planning walkthrough](docs/demos/planning-demo.md) and
[authored reading samples](docs/demos/dark-mode-example.md) for review checkpoints;
these samples do not demonstrate live audit convergence.
For project-scoped skills, committed copies, refresh behavior and optional
extras, see [Installation options](#installation-options).

For direct command operation, use the [decision flow](#decision-flow),
[common workflows](docs/how-to/common-workflows.md), and [CLI usage](#cli-usage).

## Core subcommand workflow

```
(roadmap) → create → bare audit → detail → detail audit ──┬── run → reconcile-code → review
                                                        └── jira → verify
```

| Step | What it does |
| --- | --- |
| **`roadmap`** | *(optional, project-sized)* Stage a concept brief into four gated architecture artifacts, then emit one draft `create` seed per plan it proposes. |
| **`create`** | Author a plan from prose (`--from`) or an existing draft (`--from-existing`). |
| **`detail`** | Draft per-step detail files and wire each step's `detail:` pointer. |
| **audit** | `completeness-audit` checks coverage + concepts; `reconcile-plan` re-fits a stale plan to current code. |
| **`run`** | Execute one step at a time with the configured backend; plan state advances on success. |
| **`jira`** | Export steps as Jira-sized stories (markdown/JSON) with estimates + dependencies. |
| **`verify-all`** | *(optional CI gate)* read-only `[OK]/[WARN]/[FAIL]` rollup over done steps. |

The skill reviews a bare plan before detail authoring, then reviews the complete
bundle before execution or export. It uses session-directed edits to address
conceptual findings and re-audits changed, committed text. `detail` is a
one-shot write by default; audit convergence has its own rules and stopping
conditions. See [the audit guide](docs/how-to/pipeline/audit.md).

A few verbs sit off the main spine:

- **`annotate`** — judge old plans against current code and emit seeds for the *next* `create --from-existing`. A forward-seed bridge; never mutates its source except the opt-in `--archive` move (contrast `reconcile-plan`, which edits a live plan in place).
- **Branch-awareness** — optionally bind a plan to its own git branch. Ships **OFF**; see [Branch-awareness](docs/how-to/branch-awareness.md).
- **Worktrees** — provision an isolated working copy per plan so several plans' long `create`/`detail`/`run` processes run in parallel without sharing one index, branch, or checkout. See [Worktrees (parallel plans)](#worktrees-parallel-plans).

Plan discovery is manifest-driven via `.plan-tool/plans.json` (repo-relative `.md` paths); override with `--plans-dir` or `PLAN_TOOL_PLANS_DIR`.

## Decision flow

Pick your `create` entry point by what you're starting from. File-backed
`--from-existing` selects one supplied source, refuses unmatched fences and
unusable References before any model call, then selects `direct`, `normalized`,
`split`, or `refused`. Direct-ready source content stays authoritative; split
is a successful no-plan result with a carving worksheet. See
the [create-from-existing flow](docs/how-to/pipeline/create-from-existing.md) for
the flow and the [seed-ingestion contract](docs/reference/contracts/seed-ingestion.md)
for the full lifecycle contract.

| Starting point | First command | What happens |
| --- | --- | --- |
| [Nothing](docs/how-to/choose-a-starting-point.md#start-from-nothing) | `create <slug>` | The interactive wizard writes a plan. |
| [A 1–2 sentence idea](docs/how-to/choose-a-starting-point.md#start-from-a-short-idea) | `create <slug> --from "<description>"` | `create` drafts a plan from the description. |
| [A rich existing draft](docs/how-to/choose-a-starting-point.md#start-from-an-existing-draft) | `create <slug> --from-existing <path>` | The intake route publishes, splits, or refuses the source. |
| [A canonical plan-shaped draft](docs/how-to/choose-a-starting-point.md#start-from-a-canonical-plan-shaped-draft) | `create <slug> --from-existing <path>` | Step decomposition skips its model call. |
| [An old plan plus current code](docs/how-to/choose-a-starting-point.md#start-the-next-iteration-from-an-old-plan) | `annotate <old-plan-path>` | `annotate` emits a seed for the next `create`. |
| [Several old plans or notes](docs/how-to/choose-a-starting-point.md#assess-several-old-plans-or-notes) | `annotate <path-or-glob>...` | Reports show carryover coverage and grounding. |
| [A project-sized concept](docs/how-to/choose-a-starting-point.md#stage-a-project-sized-concept) | `roadmap <slug> --from-existing <brief.md>` | `roadmap` emits staged artifacts and draft seeds. |

## Table of contents

- [Start here](#start-here)
- [Use with your assistant](#use-with-your-assistant)
- [Install](#install)
- [Your first plan](#your-first-plan)
- [Core subcommand workflow](#core-subcommand-workflow)
- [Decision flow](#decision-flow)
- [Current code layout](#current-code-layout)
- [Plan format](#plan-format)
- [Develop and test](#develop-and-test)
- [Installation options](#installation-options)
- [CLI usage](#cli-usage)
- [Common workflows](#common-workflows)
- [Running headlessly](#running-headlessly)
- [Resuming after a failure](#resuming-after-a-failure)
- [Iterating to convergence (`--iterate`)](#iterating-to-convergence---iterate)
  - [Carve an over-packed step out (`plan-tool scope-out`)](#carve-an-over-packed-step-out-plan-tool-scope-out)
  - [See a plan's split criteria (`plan-tool split-criteria`)](#see-a-plans-split-criteria-plan-tool-split-criteria)
- [Run logs](#run-logs)
- [Worktrees (parallel plans)](#worktrees-parallel-plans)
- [Modes](#modes)
- [Backends](#backends)
- [Lessons log behavior](#lessons-log-behavior)
- [Lessons consolidation](#lessons-consolidation)
- [Console progress reporting](#console-progress-reporting)
- [Correctness gates](#correctness-gates)
- [Per-subcommand reconcile](#per-subcommand-reconcile)
- [Completeness gates](#completeness-gates)

Operational walkthroughs and recovery recipes live in
[`RUNBOOK.md`](RUNBOOK.md); the plan-file schema lives in
[`PLAN_FORMAT.md`](PLAN_FORMAT.md); authoring directives for the seed files
fed to `create --from-existing` live in [`SEED_FORMAT.md`](SEED_FORMAT.md);
the schema and gate table for the `roadmap` verb's four staged artifacts live
in [`ROADMAP_FORMAT.md`](ROADMAP_FORMAT.md), with the end-to-end narrative in
the [roadmap walkthrough](docs/how-to/roadmap.md).
In-depth workflow write-ups live
under [`docs/`](docs/) — e.g.
the [create-from-existing flow](docs/how-to/pipeline/create-from-existing.md)
maps the `create --from-existing` route and links to its lifecycle contract, and
the [run flow](docs/how-to/pipeline/run.md) visualizes the `run` gate gauntlet
(which gates fire on every run, which only under a flag, and which are
advisory vs blocking). The exhaustive per-subcommand flag reference is
generated under [`docs/cli/`](docs/cli/README.md).

## Current code layout

```
plan-tool/                  (repo root)
  README.md
  SEED_FORMAT.md            Plan-seed authoring directives.
  PLAN_FORMAT.md
  pyproject.toml
  docs/
    how-to/pipeline/
      create-from-existing.md  The file-backed create route and lifecycle links.
      run.md                   The run gate gauntlet — which gates fire when, advisory vs blocking.
  integrations/
    claude/
      SKILL.md  Assistant skill — install with `plan-tool install-skill`.
  plan_tool/
    __init__.py
    schema.py Pydantic models for frontmatter.
    parser.py Parse, validate, and write plan files.
    locator.py Plan discovery + repo-root context.
    renderer.py Prompt rendering (string.Template).
    launcher.py Step selection, subprocess run, plan updates.
    progress.py Stderr progress reporter for silent claude calls.
    canonical.py Deterministic read helpers for canonical-shape `--from-existing` sources.
    cli/ Command wiring and argument parsing (one module per intent group).
      __init__.py Package surface + intent-grouped subcommand catalog.
      app.py Thin entry: main() + dispatch + error-UX handlers.
      parser.py Parser assembly (make_base_parser / assemble / register seam).
      roadmap_cmd.py roadmap handler (stage a concept brief; promote or refresh derived seeds).
      authoring.py create / detail handlers.
      run_cmd.py run / sweep handlers.
      gates_cmd.py suggest-gates handler (writes confirmed gates onto remaining steps).
      review_cmd.py reconcile-plan / reconcile-plan-walk / verify-all handlers.
      completeness_cmd.py completeness-audit / completeness-apply handlers.
      jira_cmd.py jira integration handlers.
      bench_cmd.py bench run / report handlers.
      inspect.py list / status / validate handlers.
      manifest.py register / deregister / sweep handlers.
      checkpoints.py checkpoint handler.
      runs.py runs handler.
      lessons_cmd.py lessons / lessons-consolidate handlers.
      console.py Presentation + path helpers (leaf).
      context.py Workspace + budget resolution helpers (leaf).
      reconcile.py Saved-reconcile reuse engine (leaf).
      review_actions.py Review action factory (leaf).
    prompts/ Packaged prompt templates (run.md, check.md, …).
  tests/
    fixtures/
    test_parser.py
    test_locator.py
    test_renderer.py
    test_launcher.py
```

Plan discovery is per-project: each repo that uses `plan-tool` keeps its
own manifest at `<repo-root>/.plan-tool/plans.json` (the package ships none).

### The `.plan-tool/` directory

All per-project plan-tool state lives under `.plan-tool/`. It holds two
kinds of content, and the repo commits one and ignores the other:

- **Committed** — durable, shared across the team:
  - `plans.json` — the plan manifest (plan-discovery source of truth)
  - `project.json` — confirmed project intent, non-goals, and settled decisions
  - `lessons/` — accumulated project lessons (`project.md` + citations)
  - `bench/runs/<pinned>/` — pinned benchmark fixtures
- **Git-ignored** — per-run / per-machine / debug exhaust; safe to delete:
  - `runs/`, `checkpoints/`, `reviews/`, `parse-failures/`, `crashes/`,
    `scenarios/`, `harness/`, `lessons-warnings.jsonl`, `run-prefs.json`,
    and ad-hoc `bench/runs/` output

Rule of thumb: commit what's durable and shared (manifest, project context,
lessons, pinned fixtures); ignore what's per-run, per-machine, or debug exhaust.

`create` and `register` warn if a recommended-to-commit path (`plans.json`,
`project.json`, `lessons/`) is gitignored — e.g. because the repo excludes
`.plan-tool/` wholesale — so durable shared state doesn't silently go
uncommitted.

## Plan format

Each plan is markdown with YAML frontmatter. Frontmatter is the machine-readable source of truth; prose below it is for humans.

```markdown
---
title: Example Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Add YAML schema validator
    files: [plan_tool/schema.py]
    complexity: low
    status: done
  - id: 2
    title: Build the parser
    files: [plan_tool/parser.py]
    allowed_mentions: [plan_tool/schema.py]
    complexity: medium
    depends_on: [1]
    status: current
---

# Example Plan
...
```

See `PLAN_FORMAT.md` for the full schema and conventions.

## Develop and test

```bash
cd plan-tool
uv sync
uv run pytest
./scripts/hooks/install.sh   # optional: install the git hooks (see below)
```

### Git hooks

`scripts/hooks/install.sh` points this clone's `core.hooksPath` at the
tracked `scripts/hooks/` directory, installing two hooks.

The `pre-push` hook runs the full parallel test suite
(`uv run pytest tests/ -q -n auto`) and fails the push if anything is red, so a
change cannot land on a remote while it breaks a module it never touched. It is verify-only and
never edits files; the full output is left at `/tmp/plan-tool-prepush.log`.

One member of that suite is the generated CLI reference under
[`docs/cli/`](docs/cli/README.md), which fails when it has drifted from
the argparse parser — regenerate with
`python -m plan_tool.cli_reference --write`, commit `docs/cli/`, and push
again. The hook prints that hint when it is the failing test.

Bypass once with `git push --no-verify`; uninstall with
`git config --unset core.hooksPath`.

The `pre-commit` hook (`scripts/hooks/pre-commit`, pure-stdlib Python) scans
only the lines a commit newly stages for likely secrets — provider token
formats (AWS, GitHub, GitLab, Slack, Google, Anthropic, OpenAI, Stripe,
private-key blocks) plus a generic `key/secret/token/password = "..."`
literal heuristic — and separately refuses credential-shaped filenames
(`.env`, `id_rsa`, `*.pem`, `credentials.json`, …). It is verify-only.
A real match: remove and rotate the credential and load it from an env var
or secrets manager instead. A false positive: add a trailing
`# pragma: allowlist secret` comment on that line, or bypass one commit
with `git commit --no-verify`.

## Installation options

For project-scoped installation or a committed copy:

```bash
plan-tool install-skill            # symlink → <repo>/.claude/skills/plan-tool/
plan-tool install-skill --user     # → ~/.claude/skills/ (every project, once — recommended)
plan-tool install-skill --copy     # copy in (committable, but goes stale on upgrade)
```

Each run installs two files as one set: the bundled `SKILL.md` router and a
`DIRECTIVES.md` sibling carrying the shared driving rules it cites. A
per-project symlink is machine-local — it won't survive a fresh clone or CI
(use `--copy` to commit it). `--root .agents` selects that destination root;
`--integration` selects the bundled assistant variant. Codex also changes the default root, as below.

**Codex** reads `.agents/skills`, not `.claude`, and skips a symlinked
`SKILL.md` without logging. `--integration codex` therefore defaults to
`--root .agents` and always copies; `plan-tool install-skill --integration codex
--user` installs it once for every project. Re-run it with `--force` after a
plan-tool upgrade to refresh the copy.

To install by hand instead, put both files in one folder:
`integrations/<integration>/SKILL.md` and `integrations/shared/DIRECTIVES.md`.
Symlinking the `integrations/<integration>/` folder alone leaves
`DIRECTIVES.md` out, and the router's links to it break.

**Optional spell check.** Install the `spell` extra to enable an advisory
spell check on the plan slug/title at `create` time (a token-free, local
`pyspellchecker` dictionary — no Claude call). It flags likely typos like
`standardize-app-paramerters` → `parameters` before they get baked into the
filename/manifest, and is a silent no-op when the extra isn't installed:

```bash
uv tool install --editable ".[spell]"
```

Each project you drive with `plan-tool` declares its plans in a per-project
manifest at `<repo-root>/.plan-tool/plans.json` (a `{"plans": [...]}` array of
repo-relative `.md` paths), or point the CLI at a directory with `--plans-dir`.

## CLI usage

The cheat sheet below covers the common invocations. For the exhaustive
per-subcommand reference — every flag, default, and subaction, generated
from the parser — see [`docs/cli/`](docs/cli/README.md).

```bash
# Roadmap — stage a project-sized concept brief into architecture artifacts, one rung above create.
plan-tool roadmap <slug> --from-existing <concept.md>                    # first run only: four gated stages publish one immutable version, its ledger, and the accepted head; a failed run resumes from .plan-tool/runs/<slug>/roadmap-stage-resume/; refused once an accepted head exists
plan-tool roadmap <slug> --propose-candidate                             # one ordinary intake: validated typed operations create a bounded or structural inert candidate; users never select a structural route
plan-tool roadmap <slug> --decide-candidate CANDIDATE_VERSION_ID --candidate-decision approve|edit|reject # approve is two invocations (the first prints the whole unpromoted stack and a digest and writes nothing; --confirm-stack-digest DIGEST seals and promotes it), edit requires a fresh decision, reject releases only the active candidate
plan-tool roadmap <slug> --submit-feedback ITEM_ID --feedback-target ARTIFACT:KIND[:ROW_ID] --feedback-request TEXT # add mutable reviewer input to the ledger; see ROADMAP_FEEDBACK_FORMAT.md
plan-tool roadmap <slug> --reopen-ledger-feedback ITEM_ID                # reopen one retained reviewer ledger item
plan-tool roadmap <slug> --compare [--comparison-base VERSION_ID] [--comparison-target VERSION_ID] [--comparison-output cards|patch|json] # read-only; target defaults to the active candidate, base to the accepted head
plan-tool roadmap <slug> --settle-decision <artifact>:<decision-id> --settlement-evidence <artifact>:<feedback-id> --confirm-decision-settlement # transition one Roadmap-derived decision pending → settled; publishes a committed receipt
plan-tool roadmap <slug> --materialize [PLAN_ID]                         # regenerate every recoverable draft seed, or one named row, through the standalone seed materializer; no roadmap stages
plan-tool roadmap <slug> --refresh-seeds                                 # regenerate every source-order draft seed against current code through the standalone seed materializer; write their diff report
plan-tool roadmap <slug> --apply [-y]                                    # apply-only: promote the draft seeds into plan-seeds/ (no brief, no backend, no stages); preview + confirm unless -y
plan-tool roadmap <slug> --accept-seed PLAN_ID                           # accept one validated hand-edited draft as current (no backend, no stages)
plan-tool roadmap <slug> --view {summary,walk,ledger,index,seeds,html} [--mode {current,review}] [--id ROW_ID] [--output PATH]   # inspect: start with a compact review summary, or render the traceability walk, decision ledger, reverse citation index, draft-seed state report, or a self-contained print-formatted HTML page of every artifact row (writes <roadmap-dir>/review.html by default; --output PATH chooses the destination; --output - prints instead); no Claude call or roadmap mutation

# Author — create a plan, then draft per-step detail files.
plan-tool create [slug] [--from <description> | --from-existing <path>] [--no-synthesize-body] [--no-fetch-docs] [--output-dir <dir>] [--iterate | --no-iterate] [--max-iterations N] [--iteration-budget SECONDS]   # slug optional: suggested from --from/--from-existing when omitted (confirm/edit at the prompt, taken as-is under -y); warns when the discovered plan root isn't the cwd and lets you keep that root, switch to the current directory, or abort (keeps the root under -y / non-TTY; --repo-root pins it and skips the prompt); iterate ON by default, pass --no-iterate to skip the post-write loop
plan-tool detail <name> [--step N] [--force] [--dry-run] [--no-resume] [--iterate | --no-iterate] [--max-iterations N] [--iteration-budget SECONDS]

# Annotate — judge old plans against current code; emit forward seeds for the next create.
plan-tool annotate <path-or-glob>... [--output-dir <dir>] [--report-dir <dir>] [--seed-dir <dir>] [--report <path>] [--seed <path>] [--archive] [--iterate | --no-iterate]   # --iterate is rejected: annotate is single-pass today

# Audit — judge the plan's design/coverage, then reconcile drift (reconcile-plan is mainly for older/stale plans, or a supplement).
plan-tool completeness-audit <name> [--json] [--iterate | --no-iterate] [--max-iterations N] [--iteration-budget SECONDS]
plan-tool completeness-apply <name> [--id STEM] [--anchor SLUG] [--rewalk] [--include-info]   # interactive per-gap walk (no blanket auto-apply); skipped on non-TTY
plan-tool data-contract-apply <name> [--id STEM] [--anchor SLUG] [--rewalk] [--include-info]   # interactive walk for saved DATA_CONTRACT.md drift findings
plan-tool reconcile-plan <name> [--step N | --all] [--dry-run] [--refresh] [--no-heuristic] [--no-allow-missing-parent]   # --all explicitly selects the default plan-wide audit; --refresh: cheap fingerprint gate, skip Claude unless code drifted

# Execute — lock in built work with gates, then run steps.
plan-tool suggest-gates <name> [-y] [--all-steps]   # propose gate: commands for the remaining steps, grounded in the already-built ones; confirm each (or -y to report without writing). --all-steps: propose speculative gates when nothing is built yet
plan-tool run <name> [--step N | --all [--max-steps N]] [--mode M] [--dry-run] [--allow-missing-parent] [--iterate | --no-iterate] [--max-iterations N] [--iteration-budget SECONDS]

# Verify finished (done) steps before merge.
plan-tool verify-all --rollup <name> [--max-steps N] [--dry-run] [--deep]
plan-tool verify-all <name> --mode <m> [--max-steps N] [--dry-run]

# Export — hand off to external systems.
plan-tool jira <name> [--max-hours N] [--format markdown|json] [--output PATH] [--handoff-output PATH] [--adopt-existing] [--no-write] [--stdout]
plan-tool jira <name> --lint [--format markdown|json]          # lint the conventional jira-stories artifact without invoking Claude
plan-tool jira --lint --input <path>                           # lint an existing markdown/json export directly

# Direct pipeline — chain the stages in one process (small plans only).
plan-tool direct-jira [slug] [--from <description> | --from-existing <path>] [--output-dir <dir>] [--iterate | --no-iterate] [-y]   # chains create → detail → completeness-apply → jira; stops (exit 0) and steers to the full pipeline when create yields an over-large or split plan
plan-tool direct-run  [slug] [--from <description> | --from-existing <path>] [--output-dir <dir>] [--iterate | --no-iterate] [-y]   # chains create → detail → completeness-apply → run --all --commit → reconcile-code; commits the authoring artifacts and each green step (needs a clean tree)

# Inspect & manage state.
plan-tool list
plan-tool list --status [--report-dir DIR] [--format text|md]  # roll up cached annotate reports for active plans
plan-tool status <name>
plan-tool validate <name>   # niche: frontmatter-schema only — use `completeness-audit` for authoring audits, `reconcile-plan` for plan-vs-code
plan-tool root              # report the repo root discovered from here (source + manifest path; flags it when it isn't the cwd)
plan-tool register <path-or-slug>
plan-tool deregister <path-or-slug>
plan-tool checkpoint {list | show <slug>/<checkpoint> | clear [<slug> | --all]}
plan-tool lessons consolidate [--apply] [--dry-run] [--plan SLUG] [--min-confidence FLOAT] [--no-resume] [--ignore-recurrence] [-y]
```

A first run that stops part-way resumes from its held stages only for the same
brief content; a changed brief refuses until the original brief is restored,
the named resume directory is deleted by hand, or a successor slug is started.

### Placeholders

The angle-bracket placeholders above carry consistent meaning across
every subcommand:

| Placeholder | Meaning | Where it appears |
| --- | --- | --- |
| `<name>` | **Existing** registered plan, resolved by slug (`my-feature`), filename stem (`1-my-feature`), or filename (`my-feature.md`). Priority prefixes are tried automatically. | `status`, `validate`, `run`, `reconcile-plan`, `reconcile-plan-walk`, `verify-all`, `completeness-audit`, `completeness-apply`, `data-contract-apply`, `jira`, `detail` |
| `<slug>` | Canonical lowercase-dashes plan slug (no priority prefix, no `.md` suffix). Used when there's no other form to resolve from — either the plan doesn't exist yet, or the on-disk directory is keyed by slug. | `create <slug>`, `checkpoint clear <slug>`, `runs clear <slug>`, `--slug` filter on `runs list` / `runs profile` |
| `<slug>/<checkpoint>` | Checkpoint identifier. `<slug>` is the plan slug; `<checkpoint>` is the per-plan name shown in the `name` column of `plan-tool checkpoint list` (e.g. `detail-step-02`, `create-initial-steps`). | `checkpoint show` |
| `<slug>/<run_id>` | Run identifier. `<slug>` is the plan slug; `<run_id>` is the timestamp-derived id shown by `plan-tool runs list` (e.g. `2026-05-14T12-34-56-9f3a1c`). | `runs show`, `runs diff` |
| `<path>` | Filesystem path, absolute or repo-relative. | `register <path-or-slug>`, `create --from-existing <path>`, `annotate <path>`, `--output <path>` |

### `plan-tool detail`

Drafts per-step implementation markdown (Why / Files / Implementation /
Tests / Acceptance criteria / Deferred) and wires up the step's
`detail:` pointer automatically. Output is **a draft** — read and edit
before running the step.

Global flags (before subcommand):

- `--plans-dir <path>`: scan a directory for plans (overrides `PLAN_TOOL_PLANS_DIR`).
- `--manifest <path>`: use an explicit manifest JSON file in manifest mode.
- `--repo-root <path>`: pin the repo root explicitly (overrides
  `PLAN_TOOL_REPO_ROOT`). Use this when walk-up to `.git` finds the wrong
  directory — e.g. plan-tool's own folder is a nested git repo, the skill
  is installed somewhere other than `.agents/`, or the checkout has no
  `.git`.
- `--backend <name>`: pick the subprocess backend for all backend-invoking
  calls in this process. It overrides model-family inference and
  `PLAN_TOOL_BACKEND`; default `claude`.
- `--model <name>`: pick the model passed to the selected backend. Without an
  explicit `--backend`, OpenAI GPT/ChatGPT/o/Codex models select Codex, Claude models
  select Claude, and Gemini models select the provisional Gemini backend.
- `--on-rate-limit wait|switch|stop|ask`: choose the default response for an
  ordinary recoverable short rate limit (overrides `PLAN_TOOL_ON_RATE_LIMIT`;
  default `wait`). A confirmed terminal plan quota bypasses these actions.
  `switch` requires `--fallback-backend <name>` or `PLAN_TOOL_FALLBACK_BACKEND`.
- `--fallback-backend <name>`: backend to retry an ordinary rate-limited call
  with when `--on-rate-limit switch` is active (overrides
  `PLAN_TOOL_FALLBACK_BACKEND`).
- `--no-wait-on-rate-limit`: legacy alias for `--on-rate-limit stop`; do not
  combine it with `--on-rate-limit`.

If no overrides are provided, plan discovery uses `.plan-tool/plans.json`
and repo root is resolved by walking upward from `cwd` to the nearest
ancestor containing a `.git` **or** a `.plan-tool` directory (so a checkout
with no git history, or whose plan root sits below the git root, still
resolves where the manifest lives); when neither marker is found it defaults
to `cwd`. The override precedence is: `--repo-root` → `PLAN_TOOL_REPO_ROOT` →
walk-up. `plan-tool root` reports what gets resolved from the current
directory; `create` warns and lets you keep that root, switch to the current
directory, or abort when the discovered root isn't `cwd`.

Shared options (available on every subcommand, passed after it):

`-y` / `--yes` — auto-accept confirmation prompts. Useful for
scripted / unattended / chat-driven runs (see
[Running headlessly](#running-headlessly)).

- **Skips every Y/N gate:** the `create` split-proposal "save?" prompt,
  `reconcile-plan` / `detail --reconcile` "walk saved review instead?" prompts, the
  apply-finding "keep these changes?" prompt, and `jira config`'s
  epic-removal confirmation.
- **In walks** (`reconcile-plan`, `reconcile-plan-walk`, `detail --reconcile`):
  equivalent to typing `aa` (apply-all) at the first prompt — every
  remaining recommendation auto-applies and every apply-finding diff
  auto-keeps.
- **In `create`:** also default-accepts free-text wizard prompts
  (output dir, title, lessons path) — every prompt with a
  declared default resolves to that default. The interactive
  step-by-step fallback (when Claude can't propose parseable steps)
  is replaced with a fail-fast `CreateError`, so the wizard never
  spins against a no-input source.
- **Caveat:** free-text prompts without a default (epic name, plan
  path, etc.) still block on other subcommands.

Interactive walk shortcuts (during `reconcile-plan` / `reconcile-plan-walk` /
`detail --reconcile`):

- `aa` (or `apply-all` / `all`) at the per-recommendation prompt: apply
  this rec and auto-apply every remaining rec in the walk without
  re-prompting. Also silences the apply-finding "keep these changes?"
  confirmation for the rest of the session. Equivalent to retroactively
  enabling `--yes` mid-walk.
- `a` (or `all`) at the apply-finding "Keep these changes? [Y/n/a=all]"
  prompt: keep this diff and auto-keep every subsequent applied diff in
  the walk. Useful when you trust Claude's edits across the remaining
  findings and don't want to confirm each one.

## Common workflows

The authoring pipeline runs in order, then branches at the terminal
output: *(`roadmap`)* → `create` → `detail` → audit → `run` *or* `jira`.
Each step below lists the options you reach for *in that step* — no separate
scenarios.

Assumptions: run from the repo root with the manifest
(`.plan-tool/plans.json`) in use. Substitute `--plans-dir <dir>` if
you've opted out of the manifest.

### 0. `roadmap` — stage a project-sized concept *(optional)*

Reach for `roadmap` when the work is **project-sized** and you can't yet name
its domain or say what it trades away. If you can already write a `create`
seed, write the seed — four Claude calls buy shared vocabulary and a citable
decision record, not a better design (measured in
[`docs/evidence/roadmap-layering-measurement.md`](docs/evidence/roadmap-layering-measurement.md)).

```bash
plan-tool roadmap my-project --from-existing docs/concepts/my-project.md
```

The input is one markdown brief in your own words — say the scale and load
shape, say what already went wrong, and leave open calls open. Four staged
Claude calls then publish one immutable roadmap version under
`<plans-dir>/roadmaps/my-project/`, plus one draft seed per proposed plan under
`seeds/`. The version holds four artifacts:

| Artifact | What it fixes |
| --- | --- |
| `01-domain` | Entities, business rules, workflows — the vocabulary everything downstream cites. |
| `02-constraints` | One disposition per quality attribute (`prioritized` / `traded-away` / `not-load-bearing`), plus the constraints behind them. |
| `03-components` | Logical components: the entity ids each owns, the patterns it applies, the constraints it discharges. |
| `04-roadmap` | The ordered plan list: each row's intent, component-owned or cross-cutting delivery shape, non-goals, and `draft_seed_path`. |

Each stage is judged by the deterministic gates against its upstream stages.
A failing gate feeds its violations back into a
bounded retry of the same stage; the verb is non-interactive by construction and
exits non-zero only when a stage exhausts its attempts. Roadmap artifacts are
**not plans** — nothing lands in the manifest, and `list` / `status` / `run`
won't resolve one.

**First-run resume.** Each gate-clean stage is held in memory and in the resume
directory `.plan-tool/runs/<slug>/roadmap-stage-resume/`. Only after all four
stages pass does the run publish the immutable version, its ledger, and the
accepted head (written last), then delete the resume directory. A failed run
leaves only that directory, and the next run resumes from the first stage that
is missing or fails its re-gate. A changed brief refuses until the original
brief is restored, the named `roadmap-stage-resume/` directory is deleted by
hand, or a successor slug is started.

**Stage-run status.** The ordinary `roadmap` stage run writes bounded confirmed
lifecycle lines to **stderr** after a stage start, a retry or stop, a write, and
the returned result. Each line records only the last confirmed transition: a
quiet call provides no heartbeat or backend-liveness guarantee. Roadmap
summaries and result payloads on stdout stay unchanged, so consumers must not
parse these lifecycle lines. Views, seed operations (`--apply`,
`--refresh-seeds`, and `--materialize`), candidate operations, and other
non-stage routes do not emit this status surface.

**Compare versions before a separate action.** Review the accepted head against
the active candidate with `plan-tool roadmap my-project --compare`, or bind
stored versions explicitly with `--comparison-base VERSION_ID` and
`--comparison-target VERSION_ID`. With no active candidate, `--compare` asks for
`--comparison-target`. `--comparison-output cards` (the default) and `json`
explain the change; `patch` prints Git's complete unified diff across the four
roadmap artifacts. The comparison is read-only: it neither accepts nor promotes
a version and changes no roadmap state. A stable-id change is a removal plus
an addition, and raw-only bytes stay visible rather than being assigned to a
concept.

**Review what it guessed.** Two channels:

- **`pending` decisions** — a load-bearing guess the stage recorded rather than
  interviewing you about. Settle one with `plan-tool roadmap <slug>
  --settle-decision <artifact>:<decision-id> --settlement-evidence
  <artifact>:<feedback-id> --confirm-decision-settlement`, citing a named,
  live feedback row that approves it. The command publishes a committed
  receipt instead of hand-editing `status`. See `docs/how-to/roadmap.md` § 5.
- **Reviewer ledger items** — record mutable requests outside immutable
  artifact frontmatter with `--submit-feedback`, then run selector-free
  `--propose-candidate`. Validated typed operations create a bounded or
  structural inert candidate without user route selection. Structural approval
  is two invocations and covers the whole unpromoted stack its top candidate
  carries, but `promote_review_seal` alone advances `AcceptedRoadmapHead`; edit,
  rejection, failed validation, interruption, and staleness preserve the
  accepted version and seeds. Reopen one retained ledger item with
  `--reopen-ledger-feedback ITEM_ID`. The ledger schema is in
  `ROADMAP_FEEDBACK_FORMAT.md`.

`--refresh-seeds` regenerates draft seeds against current code, restores a
consumed or archived seed at its original path, and writes a diff report. Until
then, `create --from-existing` asks for an explicit confirmation before
continuing with an invalidated roadmap seed.

**A roadmap with an accepted head changes through feedback and review.** A
stage run refuses once the head exists; use the ledger routes above.

**Then it's the ordinary pipeline.** A full run prints one ordered
`create --from-existing` line per plan row:

```bash
plan-tool roadmap my-project --apply     # optional: promote accepted drafts into plan-seeds/
plan-tool create first-plan --from-existing plan-seeds/first-plan.md
```

`--apply` runs no stages and invokes no backend — it previews, confirms (or
`-y`), and copies. You can skip it and point `create` straight at a
`seeds/<plan>.md` path. Order the seeds by dependency yourself; inter-plan
assumptions live in the `04-roadmap` artifact and in each seed's scope fence.

**Read it back with `--view summary`.** The compact summary shows artifact
health, design and review counts, plan review-context coverage, seed lifecycle,
indexed-reference problems, and the highest-priority drill-down commands. Use
`plan-tool roadmap <slug> --view {walk,ledger,index,seeds}` for the full
traceability walk, decision ledger, reverse citation index, or per-plan draft
seed state report — every
cross-row id resolved to the row it names, without opening all four files by
hand. `--view html` renders every row of all four artifacts as one
self-contained, print-formatted page instead, for reading the design rather
than auditing its state; its domain section opens with an ER-style diagram of
the entities and their reference fields, and draws no cardinality because the
artifact records none — written to `<roadmap-dir>/review.html` by default
(`--output <path>` chooses the destination; `--output -` prints instead, the
default every other view uses). `--mode current` (the default) renders the design state; `--mode review`
adds `feedback` rows and their removals. See `ROADMAP_FORMAT.md` § "See also"
or the generated
[`roadmap` command reference](docs/cli/roadmap.md) for the full flag list.

Full narrative — a real run, what to read each artifact for, and the manual
fallback when stage 4 is skipped:
the [roadmap walkthrough](docs/how-to/roadmap.md). Schema and gate
table: [`ROADMAP_FORMAT.md`](ROADMAP_FORMAT.md).

### Plan workflow

For ordinary plan work, use the task guides as the source of operational
detail. They preserve the command options, state-specific behavior, and
recovery paths that would otherwise duplicate this README.

| When you need to… | Use | Then read |
| --- | --- | --- |
| Create a plan from an idea, draft, or archived predecessor | `create` | [Create from an existing draft](docs/how-to/pipeline/create-from-existing.md) and [Common workflows](docs/how-to/common-workflows.md) |
| Draft or refresh per-step implementation detail | `detail` | [Detail](docs/how-to/pipeline/detail.md) |
| Check the plan's design and detail coverage | `completeness-audit` | [Audit](docs/how-to/pipeline/audit.md) |
| Re-ground an unexecuted plan against changed code | `reconcile-plan` | [Common workflows](docs/how-to/common-workflows.md) |
| Execute a step and protect completed work | `run`, `suggest-gates` | [Run](docs/how-to/pipeline/run.md) |
| Export stories or verify merged work | `jira`, `verify-all` | [Command guide](docs/reference/commands.md) |
| Register, remove, archive, or withdraw a plan | `register`, `deregister`, `sweep`, `withdraw` | [Command guide](docs/reference/commands.md) |

`reconcile-plan` is for a plan that has not run yet: code is canonical and the
command edits the plan. After execution, `reconcile-code` treats the plan as
canonical and edits code. [Gates and reconcile](docs/GATES.md) owns that
directional boundary.

For every option, placeholder, and mode, use the [command guide](docs/reference/commands.md)
or generated [CLI reference](docs/cli/README.md).

## Running headlessly

Headless mode = non-interactive runs (chat agents, CI jobs, cron).
Two ingredients:

1. **`-y` / `--yes`** — skips confirmation gates and (for `create`)
   default-accepts free-text wizard prompts. See *Shared options*
   above for the full list.
2. **Close stdin** (`< /dev/null`) — guarantees the process can't
   block on terminal input.

**Don't** pipe an infinite empty-line source like `yes "" |` —
`_ask(..., required=True)` re-prompts on empty input and spins.
`< /dev/null` raises `EOFError`, which the wizard surfaces as a
clear `CreateError` under `--yes`.

### `plan-tool create` headlessly

```bash
plan-tool create my-plan-slug \
  --from-existing /path/to/seed.md \
  --output-dir docs/implementation-plans \
  -y < /dev/null
```

Notes:

- `--from-existing` is strongly preferred over `--from "<inline-text>"`
  in scripted use: a real file is easier to author, easier to inspect
  later, and large prose doesn't get mangled by shell quoting.
- `--output-dir` is required when stdin is closed — without it, the
  wizard prompts for the directory and `--yes` substitutes the default
  for you, but explicit is safer.
- If Claude can't extract parseable steps from the seed (either via
  canonical `## Steps` extraction or its proposal call), `--yes` mode
  raises `CreateError("--yes mode: no parseable steps from canonical
  or claude. Provide a richer --from-existing seed...")` and exits
  non-zero. Without `--yes`, the wizard would fall back to interactive
  per-step prompts — which would block under closed stdin.
- Collision handling defaults to N under `--yes` (the wizard does
  *not* auto-archive a colliding plan; it raises `FileExistsError`).
  Archive the existing plan manually before re-running.

### `plan-tool detail` headlessly

```bash
plan-tool detail my-plan-slug -y < /dev/null
# or, for a specific step:
plan-tool detail my-plan-slug --step 3 -y < /dev/null
```

Notes:

- `detail` is already mostly non-interactive: per-step idempotency
  short-circuits any step whose detail file already exists on disk,
  and the parser has one retry-with-clarifying-suffix attempt before
  giving up. `-y` covers the few Y/N gates around lessons capture and
  the optional re-run prompts.
- Lessons capture (the second Claude call per step) is **off by
  default** — headless and cost-sensitive runs need nothing extra.
  Pass `--lessons` to turn it on.
- A step whose claude response can't be parsed after two attempts is
  recorded as skipped with `"claude returned an unparseable response"`
  — the run continues for other steps and exits 0 overall. Check the
  per-step report at the end of stdout.

### `plan-tool reconcile-plan` / `reconcile-plan-walk` headlessly

```bash
plan-tool reconcile-plan my-plan-slug -y < /dev/null
plan-tool reconcile-plan-walk my-plan-slug -y < /dev/null
```

`-y` at the per-recommendation prompt is equivalent to typing `aa`
(apply-all) at the first prompt — every recommendation is auto-applied
and every `apply-finding` "Keep these changes?" diff is auto-kept.
Saved-review walks behave the same way when re-invoked.

### Streaming output back to a chat agent

Append `2>&1 | tee /tmp/plan-tool.log` to capture combined stdout +
stderr. The tool flushes section headers as it works (each `[N/M]`
step, each `done in Xs`), so a chat agent monitoring the log file
gets incremental progress rather than a single end-of-run dump. See
[Console progress reporting](#console-progress-reporting) for the
exact line format.

### Iterating headlessly

`--iterate` and `-y` compose: under `-y` (or closed stdin / non-TTY),
the walk inside every iteration defaults to `apply-all` so iteration
N+1 isn't blocked on `input()`. The same `WalkState(yes_to_all=True)`
seed that drives the inner walks under `-y` (per the step-4 wiring at
`plan_tool/cli/reconcile.py:_iterate_reconcile_loop`) also auto-keeps every apply-finding
diff. A completed loop exits 0 even when the budget is exhausted with
findings still open, so a CI job inspects the printed report / saved
findings rather than the rc — or, for the audit commands
(`completeness` / `verify-all` / `verify-all` / `validate`), passes
`--fail-on-findings` to gate the pipeline on the exit code directly:

These are independent syntax examples; commit a clean baseline before each
stage and follow both audit gates in the shared directives. Reconciliation
commands do not support iteration.

```bash
plan-tool detail my-plan --iterate -y < /dev/null # only when explicitly requested
plan-tool completeness-audit my-plan --iterate -y < /dev/null

```

See [Iterating to convergence](#iterating-to-convergence---iterate)
for the loop semantics and the "When to use" decision tree.

## Resuming after a failure

Both `plan-tool create` and `plan-tool detail` memoize every
successful Claude response to
`<repo>/.plan-tool/checkpoints/<plan-slug>/`. If a run fails between
a successful parse and the durable on-disk write — write error,
plan-update error, Ctrl-C, killed shell, model timeout in
post-implementation phase — the next run reuses the cached body
instead of re-invoking Claude.

```bash
plan-tool detail my-plan -y < /dev/null # default: resume enabled
plan-tool detail my-plan --no-resume # force fresh Claude calls
```

What's keyed:

- **`detail`**: per step. Hash covers plan slug + step id + title +
  complexity + files list + depends_on + the rendered confirmed project
  context. Editing the step's title, complexity, files, dependencies, or
  project profile invalidates that step's cache; editing unrelated metadata or
  the plan body does **not**.
- **`create`**: authoring slots include `create-initial-steps` (slug +
  description + output dir + iteration index), `create-references`
  (title + description + slug + output dir + iteration index), and
  `create-body-sections` (slug + seed source bytes + output dir +
  iteration index). The context-bearing initial-step and body-section slots
  also include the rendered confirmed project context; the reference-search
  slot does not. File-backed routing also owns direct-assessment or preparation
  checkpoints. Editing the seed file, relevant project profile, or output dir
  invalidates the affected slot; an interactive re-run with the same answers
  re-uses matching work.

Staleness:

- Checkpoints older than **30 days** are treated as expired and
  bypassed (see `DEFAULT_MAX_AGE_SECONDS` in `checkpoint.py`).
- Clean publication discards completed checkpoints. File-backed split and
  normalized iteration-incomplete outcomes retain their route-owned recovery
  state; see [create recovery](docs/how-to/recovery/create.md).
- `.plan-tool/checkpoints/` is gitignored.

Caveats:

- **Concurrent runs against the same plan are undefined.** The
  on-disk write is atomic per file, but two simultaneous
  `plan-tool detail` invocations against the same plan/step are a
  last-writer-wins race for the checkpoint, the detail file, *and*
  the plan frontmatter. There is no lockfile. Don't overlap.
- **`--force` bypasses both the file-exists skip and the cache.** If
  you want a fresh body without deleting state, this is the flag.
- **The hash is intentionally narrow.** Editing source files,
  sibling detail files, lessons, or the plan body between runs does
  NOT invalidate a cached body. Pass `--no-resume` if you've edited
  inputs the hash doesn't cover and want a fresh call.

### Managing checkpoints

```bash
plan-tool checkpoint list # show every cached checkpoint
plan-tool checkpoint show <slug>/<checkpoint> # print one (payload to stdout, meta to stderr)
plan-tool checkpoint clear <slug> # remove one plan's cache
plan-tool checkpoint clear --all # wipe everything
```

`show` writes metadata (created_at, input_hash, schema_version) to
stderr and the raw payload to stdout, so it pipes cleanly:
`plan-tool checkpoint show my-plan/detail-step-03 | bat`.

## Iterating to convergence (`--iterate`)

`--iterate` loops: write → audit → `apply-finding` → re-audit, until
no new findings remain or the budget exhausts.

**Why convergence matters.** Convergence is the plan's correctness
signal, not just a loop mode. A plan that converges under audit→apply is
sound; the loop ran out of things to fix because there was nothing left
to fix. A plan that *won't* converge — the same region re-flagged every
pass, the finding count not shrinking, the body only growing — is
telling you the plan is the wrong **shape** (an over-packed step, two
concerns merged, a branch with no live scenario). `apply_finding` edits
prose; it can fix under-specification but never over-complexity or
mis-decomposition, so patching again just grows the plan and feeds the
next audit more surface. The response is to **re-decompose** — re-split
one step, or re-seed the plan — not to patch a fourth time. (Note:
`no-blocking-findings` means "nothing left the loop may auto-touch," not
"sound" — a plan whose remaining problems are all structural reports
converged prematurely.) See
[RUNBOOK.md → When repeated audit/apply doesn't converge](RUNBOOK.md#when-repeated-auditapply-doesnt-converge--re-decompose-dont-keep-patching).

### Carve an over-packed step out (`plan-tool scope-out`)

When a step (or contiguous band) keeps re-flagging at high severity and
won't shrink under audit/apply — re-splitting it a third time only
backfires — carve it out of the plan instead of patching again:

- `plan-tool scope-out <name> --step N` lifts the over-packed step into a
  `create --from-existing` forward-seed and narrows the plan, so the rest
  converges and the carved work is re-planned on its own.
- **Recommend-only by default**; it mutates only under `--apply` plus a TTY
  confirm (`-y` is the deliberate non-interactive opt-in). It is
  **seed-first** — the forward-seed is written to `plan-seeds/` before the
  plan is narrowed — and spends no claude.
- `plan-tool convergence <name>` does not recommend or actuate this carve —
  it is a read-only loop/structure signal; pick the step (or range) yourself.

See [RUNBOOK.md → Carve an over-packed step out of a plan](RUNBOOK.md#carve-an-over-packed-step-out-of-a-plan-plan-tool-scope-out)
for the full gate (the four refusal blockers, seed-first ordering, the
post-carve history caveat).

### See a plan's split criteria (`plan-tool split-criteria`)

`plan-tool split-criteria [<name>]` shows the structural-split axis the tool
reasons over — the "why is this plan shaped this way?" companion to
`plan-tool convergence`. It has two modes:

- **No argument** → the plan-independent **legend**: every split criterion the
  tool applies across the three altitudes, plus the remedy vocabulary
  (re-split / scope-out / merge / re-seed).
- **A plan argument** → the per-plan **breakdown**: which criteria fire for that
  plan, on which steps, with a one-line reason each.

Like `plan-tool convergence` and `plan-tool status`, it is a read-only "tell me
the state" diagnostic — it spends no claude, mutates nothing, writes no run-log
entry, and criterion findings do not change its exit code. Input-resolution,
parsing, and unsupported-detail-format errors still exit non-zero.

- **On by default:** `create`. Pass `--no-iterate` to skip the
  post-write loop.
- **Off by default:** `detail` and `completeness-audit`. Pass `--iterate`
  explicitly for completeness audits. Keep detail authoring one-shot unless
  the user explicitly requests its quality loop.
- **Reconciliation:** neither `detail --reconcile` nor `run --reconcile`
  supports `--iterate`; both reject it with exit 2. Detail reconciliation
  also rejects `--no-iterate`. Standalone `reconcile-plan` and `reconcile-code`
  do not accept iteration flags. Use saved reports and session-directed
  corrections followed by a new invocation. Plan-side reconciliation is
  pre-execution only; after execution, keep the plan canonical with
  `reconcile-code`.
- **Other unsupported routes:** `annotate`, `verify-all`.
  `annotate --iterate` exits 2 before writing anything, because
  `annotate` is a single classification pass plus deterministic
  renderers, not a loop. The convergence step happens on the next run:
  `create --from-existing <seed> --iterate`.


### Defaults

| Flag | Default | Source | Effect |
| --- | --- | --- | --- |
| `--iterate` / `--no-iterate` | `create`: `--iterate` (on). `detail`, `completeness-audit`: `--no-iterate` (off). | `BooleanOptionalAction` + per-subparser `default=True` on `create`, `default=False` on `detail` | Master switch. Off ⇒ `IterativeBudget(enabled=False)` ⇒ `should_continue` short-circuits with `"disabled"` on the first call. |
| `--max-iterations N` | `3` | `convergence.DEFAULT_MAX_ITERATIONS` | Maximum iterations after the initial write. `--max-iterations 0` is rejected by `_resolve_iterative_budget`. |
| `--iteration-budget SECONDS` | `1800` | `convergence.DEFAULT_ITERATION_BUDGET_SECONDS` | Debounced no-progress deadline: fires only after SECONDS pass with zero forward progress. It resets on every round and every `apply_finding` call, so a single 15-20+ minute claude call never trips it — this is not a cap on total loop wall-clock (see `--time-budget` for that). |
| `--max-stall-rounds N` | `2` | `convergence.DEFAULT_MAX_STALL_ROUNDS` | Stop after N consecutive rounds whose open-finding **count** doesn't shrink. It's an ID-agnostic backstop for a subjective audit that re-phrases the same findings each round (fresh ids would otherwise defeat the `marginal` / `converged` checks). `0` disables. |


### When to use `--iterate`

**Reach for `--iterate` when:**

- You're authoring a brand-new plan with `create` and want the
  deterministic completeness primitives (body sections, detail
  coverage, references) to drive 2–3 author-fix-reaudit passes before
  you hand it to a developer.
- The user explicitly requests iterative detail authoring with `detail` and wants the
  `detail-quality.md` review to drive 2–3 quality revisions on the
  just-written body — citations tightened, vague prose pinned to real
  line ranges, generic bullets replaced with code-checkable ones.
- You're running headlessly (`-y < /dev/null`) and want the walk to
  apply every finding without stopping. Under `-y` / non-TTY, the inner
  walks default to `apply-all` so iteration N+1 isn't blocked on
  `input()` — there's no one there to answer the prompt.

**Skip `--iterate` when:**

- You only want a report: use `verify-all`, or pre-execution
  `reconcile-plan --no-walk` to save findings without applying them.
  (`completeness-audit --iterate` converges only its deterministic findings
  and leaves conceptual gaps for session-directed edits.)
- You're debugging a claude regression and need iteration-1 state to
  inspect before iteration 2 overwrites it. Pass `--no-iterate`
  explicitly for `create`, where omitting the flag opts you INTO the
  loop. `detail` already writes once unless you pass `--iterate`.
- You're in CI with a hard wall-clock cap and one extra claude call per
  iteration is too expensive (or pass `--max-iterations 1` for exactly
  one pass — see tiebreakers below).
- You want a single authoring pass: use `create --no-iterate` or plain
  `detail`. Do not add iteration flags to reconciliation commands.

**Tiebreakers:**

- **`--max-iterations 1` is *not* the same as `--no-iterate`.** Both
  stop after one claude apply pass, but `--no-iterate` short-circuits
  the loop entirely — no `apply-finding` call at all, no deterministic
  re-audit. `--max-iterations 1` runs the loop once: write → audit →
  apply once → stop. Choose `--no-iterate` for "I want the old
  behavior"; choose `--max-iterations 1` for "I want exactly one fix
  pass."
- **Per-step vs. per-plan scope.** `detail`'s budget is *per step* (the
  loop wraps each detail-file write independently). `create`'s budget
  is *per plan* (one loop around the post-`write_new_plan` reaudit).
  When you iterate across multiple steps with `detail` (no `--step`
  argument), each step gets its own fresh budget — one step exhausting
  its budget doesn't block the next.

### How the loop terminates

- **Converged.** `finding_set_delta` returns an empty introduced-
  set. Exit code 0.
- **Budget exhausted.** Iteration count hit `--max-iterations`, or
  wall-clock hit `--iteration-budget`. Exit code 0 — the loop
  completed; any findings still open are in the report (and, for
  `completeness --json`, the `has_blocking_findings` flag), which CI
  / aggregation scripts inspect instead of the rc. For
  `completeness`, add `--fail-on-findings` to turn "budget exhausted
  with medium+ findings still open" into a non-zero exit a CI step
  can gate on.
- **Marginal stagnation.** Iteration N introduced no *new* findings
  relative to iteration N-1 (intersection equals prior set). Halts
  cleanly with exit code 0 — the loop is making no further progress,
  but the artifact is no worse than the prior iteration.

### Checkpoint interaction

`create` includes the iteration index in `_initial_steps_input_hash`
/ `_references_input_hash` — so iteration N+1's claude call is
**not** served the cached body from iteration N when resuming. Each
completed iteration's payload caches at its own slot, and a resumed
run replays them in order.

`detail` does *not* extend its hash keys. `detail` relies on `apply_finding` mutating
the file in place between iterations, and `run` does not go through
the checkpoint module at all. When resuming an interrupted `create
--iterate` run, the cache replays each completed iteration; only the
in-flight iteration re-invokes claude.

### Headless

See [Iterating headlessly](#iterating-headlessly) for the `-y` ×
`--iterate` apply-all default and how a completed loop exits 0 with
any open findings carried in the report for CI gates to inspect.

### Operational recipes

See [RUNBOOK.md → Workflow: drive an authoring task to convergence](RUNBOOK.md#workflow-drive-an-authoring-task-to-convergence---iterate)
for end-to-end recipes against each subcommand.

## Run logs

Every backend-invoking subcommand (`run`, `verify-all`, `detail`,
`jira`, `reconcile-plan`, `create --from*`), plus roadmap stage,
seed-materialization, seed-refresh, and seed-apply runs, writes two artifacts
under `<repo>/.plan-tool/runs/<plan-slug>/`:

- `<run_id>.jsonl` — append-only structured event log.
- `in-flight.json` — atomically-updated liveness snapshot, refreshed on
  phase start, backend spawn, every heartbeat, backend termination, and
  backend recovery wait — see
  ["The in-flight snapshot"](#the-in-flight-snapshot) below.

Same surface as the live stderr progress reporter (start, heartbeat,
done; per-claude-call wall-clock, tokens, cache hits) — but
machine-readable and durable past the scroll buffer.

What's recorded per run:

- `run_start` — schema version, command, plan slug, argv, pid, cwd.
- `phase_start` / `phase_end` — one pair per logical phase (e.g.
  `propose_steps`, `propose_references`, `fetch_reference_docs`,
  `propose_body_sections`, `per_step_body`, `prompt_build`,
  `claude_call`, `reconcile_walk`, `apply_finding_dispatch`).
- `claude_call_start` / `claude_call_end` — one pair per logged `claude -p`
  invocation. `claude_call_end` carries wall-clock duration and (when
  `claude -p --output-format json` is supported) input/output tokens,
  cache-creation / cache-read tokens, request id, and cost.
  `claude_call_start` also carries `prompt_bytes` and `prompt_sha256` (hex
  SHA-256 of the prompt, never its text).
- `checkpoint_hit` / `checkpoint_save` / `checkpoint_discard` — every
  checkpoint cache interaction (the same cache `## Resuming after a
  failure` above documents).
- `parse_failure` — pointer to the existing
  `.plan-tool/parse-failures/<plan-slug>/<NN>-attemptK-<ts>.txt` body
  (`detail` parse-retry loop). The body is not duplicated.
- `gate_violations` — the gate messages that consumed one failed attempt
  (`roadmap` stage loop), so a stage that passed on its last attempt is
  distinguishable from a clean first-try pass. Messages are dropped whole
  past a size budget; `violation_count` stays exact.
- `attempt_failed` — which of the four failure kinds (`invoke`, `parse`,
  `authored-review-rows`, `gates`) consumed one attempt (`roadmap` stage
  loop). Emitted for every kind, so an attempt that fails and then
  **recovers** — the common case, and otherwise invisible because the stage
  goes on to write its artifact — still names its cause.
- `model_failure_receipt` — redacted rejected-reply evidence from roadmap
  model calls and from failed `run` steps (reasons `invoke`,
  `no-edits-applied`, `test-authoring-gate`, `test-gate`, `gate`; sidecar under
  `.plan-tool/parse-failures/_run/<plan-slug>/`). Use `plan-tool runs` to find the receipt for its phase and attempt. It records
  the producer-owned reason, response byte count and digest, and sidecar
  disposition (`written`, `no-response`, `not-retained`, or `write-failed`);
  follow `sidecar_path` only when the receipt provides one. A missing,
  unavailable, or failed sidecar capture remains a valid receipt outcome, not
  a command failure. JSONL never carries the raw response.
- `gate_violations` remains the structured diagnosis for stage
  gate failures, while `attempt_failed` remains the retry-spending
  classification. The receipt correlates with those events by phase and
  attempt; it does not replace or copy their diagnostics.
- `roadmap_preflight_failed` / `roadmap_stage_written` — a typed preflight
  failure (accepted head, pre-head state, brief source or read, publication
  recovery, resume brief digest, carried decisions), plus every accepted
  artifact's path, digest, replacement status, and draft-seed count. Brief text
  is never copied into the log.
- `roadmap_seed_apply_result` — the aggregate target, promotion, collision,
  missing-draft, and provenance failure counts for `roadmap --apply`, which
  has the same run boundary even though it makes no Claude call.
- Roadmap seed actions (`--materialize` and `--refresh-seeds`) carry one
  redacted command record and liveness snapshot. Their source-ordered row
  phases, attempt counters, terminal outcomes, and redaction boundary are in
  [DATA_CONTRACT.md](DATA_CONTRACT.md#roadmap-seed-action-context-and-lifecycle).
- `iteration_start` / `iteration_end` — per-step framing under
  `cmd_detail` so a multi-step `detail` call records each step's
  bounds.
- `run_end` — total duration, outcome (`ok` / `error` / `interrupted`),
  rc.

`.plan-tool/runs/` is gitignored alongside `.plan-tool/checkpoints/`
and `.plan-tool/parse-failures/`.

### Roadmap seed actions

`plan-tool roadmap <slug> --materialize [PLAN_ID]` and `--refresh-seeds`
each own one `command: "roadmap"` JSONL record and the active
`in-flight.json` snapshot. They call the standalone seed materializer, so they
are backend-backed even though they do not run roadmap stages. The command
record retains `roadmap_action`, `roadmap_slug`, the explicit
`requested_plan_id` when one was supplied, and the currently active row while
it is prepared or materialized. It uses the existing writer lifecycle:
`RunLogWriter.start()`, `phase_start()`, `phase_end()`, and `run_end()`.

Each attempted row has a `seed-materialize:<plan-id>` phase. The row sequence
follows `PlansArtifact.plans`, not its presentation `ordering`: an explicitly
selected materialization attempts its requested row, an unqualified
`--materialize` attempts every eligible row, and `--refresh-seeds` attempts
every row. After a row phase ends, the writer publishes inactive row context
before the next phase and before terminal cleanup. The snapshot is removed by
the terminal writer path on completed, no-op, partial, exhausted,
preflight-refused, interrupted, and error outcomes.

The seed-action records retain lifecycle timing, retry counts, safe failure
kind, numeric return code, and aggregate counts. They never retain prompts,
seed bodies, replies or reply heads, validation prose, `failure_detail`,
provider transcripts, or tool-input summaries. The seed-refresh report remains
the human-facing comparison, not a copy of recordable log content.

These boundaries stay separate from the other roadmap modes: `--apply` stays
backend-free but writes its existing apply-specific run record; `--accept-seed`
and `--view` stay backend-free and log-free. Roadmap views do not create a run
record; `--view html` only writes its derived output page.

### Inspecting recent runs

```bash
plan-tool runs list # every slug, run_id, command, duration, tokens
plan-tool runs list --slug my-plan # filter to one plan
```

Each row carries `slug`, `run_id`, `cmd`, `started_at`, `duration`
(or `in-flight` when no `run_end` is on disk), `events`, and
`tokens`. Symlinked slug directories are skipped.

### Reading one run

```bash
plan-tool runs show my-plan/<run_id>
plan-tool runs show my-plan/<run_id>.jsonl # trailing .jsonl is accepted
```

- **stdout** — event lines with phase / claude-call indentation.
- **stderr** — metadata (run_id, plan_slug, command, schema_version)
  as `# `-prefixed lines, so `runs show … | grep claude_call_end`
  works.
- **Exit 1** on schema_version mismatch on the first `run_start`,
  with `unsupported run-log schema_version` on stderr.

### Comparing two runs

```bash
plan-tool runs diff my-plan/<run_a> my-plan/<run_b>
```

Per-phase wall-clock + token delta table:

- Phases present in both runs sort first (alphabetical), then
  `only-in-A`, then `only-in-B`.
- Closing line summarizes `total Δwall`, `total Δtokens`, and the
  `only-in-A` / `only-in-B` counts.
- Token columns render as `-` when both calls hit the older-CLI
  fallback that returns no token meta.

### The in-flight snapshot

```bash
cat .plan-tool/runs/<plan-slug>/in-flight.json | jq .
```

- Written atomically (tempfile + `os.replace`) on every refresh, so
  `cat` always reads a complete snapshot, never a partial write.
- `RunLogWriter` refreshes it from five call sites, each merging its
  fields into the same held snapshot so one trigger's write never drops
  another trigger's fields: `phase_start` (`current_phase`),
  `backend_spawn` (`child_pid`, `transport`, `effective_timeout_ms`,
  `prompt_bytes`), `claude_call_progress` — the heartbeat —
  (`elapsed_ms`, `silent_ms`, `last_tool`), `backend_termination`
  (`termination_reason`), and `backend_recovery_wait` (`recovery_reason`,
  `recovery_delay_ms`, `recovery_next_attempt`).
- `status` is one of `running`, `awaiting_retry`, or
  `backend_terminated`. The heartbeat never writes `status` — a late
  heartbeat can only refresh the timing fields, never overwrite a
  termination or a recovery wait with a stale "running". The next
  `phase_start`/`backend_spawn` in a multi-phase run flips `status` back
  to `running`.
- Schema: `{schema_version, run_id, command, plan_slug, started_at,
  log_path, status, current_phase, last_event_ts, elapsed_ms,
  silent_ms, last_tool, child_pid, effective_timeout_ms, transport,
  prompt_bytes, termination_reason, recovery_reason,
  recovery_delay_ms, recovery_next_attempt, ...}` — each field appears
  only once its triggering event has fired at least once.
- Use this when `plan-tool run` looks frozen on stderr and you want to
  know which phase is actually in flight, whether the subprocess is
  still emitting activity, or whether it's intentionally sleeping in a
  rate-limit/transient recovery wait rather than hung.
- `annotate`, `jira`, and `create`'s slug-generation call open no
  `RunLogWriter`, so they produce no snapshot — same as they produce no
  JSONL trail.
- **Not removed by `runs clear --older-than`** (mtime would race the
  active writer). `runs clear --all` and `runs clear <slug>` do
  remove it.
- Teardown (`run_end`) skips the delete when a newer same-slug run has
  since claimed the file — its `run_id` no longer matches the ending
  writer's own — so a completing call can't erase a still-running
  sibling's only liveness signal.

### Cleanup

```bash
plan-tool runs clear --older-than 30d # evict everything older than 30d
plan-tool runs clear my-plan # remove one slug's runs (incl. in-flight.json)
plan-tool runs clear my-plan --older-than 7d # combine: only old runs under one slug
plan-tool runs clear --all # wipe every run log under .plan-tool/runs/
```

`--older-than` accepts `30d` / `48h` / `90m` / a bare integer
(seconds). The recommended default (citing `_DEFAULT_RUNS_TTL_SECONDS`
in `plan_tool/cli/runs.py`) is `30d` — same cadence as `.plan-tool/checkpoints/`'s
auto-expiry.

See [`RUNBOOK.md`](RUNBOOK.md#workflow-investigating-a-slow-run) for
a step-by-step walkthrough.

## Worktrees (parallel plans)

A long `create` / `detail` / `run` on one plan monopolizes the repo's
single index, branch, and checkout. The `worktree` command group gives
each plan its own **isolated working copy** so several plans' processes
run in parallel without stepping on each other. Four verbs:

```bash
plan-tool worktree add <plan> [--branch B] [--clone]  # provision (or reuse) the plan's workspace
plan-tool worktree list                               # kind / branch / path / dirty for every plan's workspace
plan-tool worktree remove <plan> [--force]            # delete one plan's worktree (dirty needs --force)
plan-tool worktree prune                              # sweep dead (deregistered / path-gone) worktrees
```

**Where they land.** The default base is `<repo-parent>/<repo-name>.worktrees/<slug>`
— a **sibling** of the repo, never inside it (a worktree under the main
tree corrupts git). Override the base with the `worktree_base` key in
project `.plan-tool/config.json`, falling back to user
`~/.plan-tool/config.json`; a value that resolves inside the repo is
rejected with a warning and the default is used.

**The branch.** `add` provisions the workspace on the plan's branch and
**the branch is born inside the add** — on the plan's slug-derived name
(branch-awareness OFF, the default) or the `derive_branch` name
(branch-awareness ON), off the resolved start point (the repo's default
branch, or `HEAD` on a local-only repo with no remote). Pass `--branch B`
to override. Re-running `add` on a healthy existing workspace of the
expected kind and branch reuses it (idempotent); a foreign or
wrong-branch directory at the path is refused, never overwritten.

**Worktree vs `--clone`.** The default and recommended path is a **git
worktree** — it shares the repo's object store, remote, and config, so
it is cheap. `--clone` opts into a full standalone **clone** (an
independent repo with its own duplicated object store, remote, and
config); reach for it only when a run needs total isolation from the
shared `.git`.

### Caveats (sharp edges)

- **Don't change `worktree_base` while workspaces exist.** The per-slug
  path is re-derived from the base on every `list` / `remove` / `prune`,
  so moving the base points those verbs at a *different* location and
  they can no longer find already-provisioned workspaces. Worktrees
  survive (git's own registry still tracks them); clones do not. Rule:
  re-provision after any base change.
- **Clones are manual-cleanup — plan-tool never auto-deletes one.**
  `remove` deletes a *worktree*; on a **clone** it prints a
  manual-cleanup message and deletes nothing, and `prune` (which sweeps
  the git worktree registry only) ignores clones entirely. A clone is an
  independent repo whose commits live only in its own `.git`
  (committed-but-unmerged work the uncommitted-only dirty gate can't
  see) and it carries no plan-tool provenance marker, so no scan can
  safely tell a dead plan-tool clone from an operator's unrelated repo.
  Delete a clone yourself — `rm -rf <path>` after confirming no unmerged
  commits; `list` keeps it visible until you do.
- **Plans are per-branch; don't `gc` aggressively across parallel runs.**
  A plan resolves inside a worktree only if its `.md` and `plans.json`
  entry are committed on that worktree's base branch (else "plan not
  found"). Worktrees share `.git/objects`, so an aggressive `git gc`
  while parallel runs are live can disturb another run's objects —
  avoid it. `remove` / `prune` refuse a dirty *worktree* without
  `--force`, and `prune` **surfaces** (never silently deletes) a
  dead-but-dirty worktree even under `-y`.
- **Removal never deletes the branch.** `remove` / `prune` delete the
  *worktree directory* but **not** the branch born inside the `add` —
  branch cleanup (`git branch -d <branch>`) stays the normal git flow.
  (Clones aren't deleted at all — see above.)

Operational walkthrough: [`RUNBOOK.md`](RUNBOOK.md#workflow-run-plans-in-parallel-worktrees).

## Modes

- **`run` (default)** — mutating. Executes a step and advances plan
  state on success. When the step declares a `change_type`, the prompt
  appends a test directive: both code types (refactor and feature) are
  asked for tests covering the behavior the step changes, green before it
  completes; non-code / unclassified steps get no directive. (The former
  per-type *ordering* contract was withdrawn 2026-07-30; see CLAUDE.md.) The post-flight
  `test_command` gate is unchanged. See
  [`PLAN_FORMAT.md`](PLAN_FORMAT.md#field-semantics) for the field.
- **Read-only modes** — render alternate prompts; never modify plan
  state: `check`, `optimize`, `document`, `test`, `security`,
  `lint`.
- **Reconcile** — two subcommands:
  `plan-tool detail <name> --reconcile` (code-is-truth) and
  `plan-tool run <name> --reconcile` (plan-is-truth).
- **`--dry-run`** — renders the prompt and prints it without
  invoking Claude.

## Backends

A *backend* is the CLI subprocess plan-tool spawns to execute and audit
steps. Three are registered: the default **`claude`**, **`codex`** (the
OpenAI Codex CLI), and **`cursor`** (the Cursor Agent CLI, binary `agent`).
Every claude-invoking subcommand (`run`, `detail`,
`reconcile-plan`, `jira`, …) routes through the active backend, so selecting
`codex` swaps the executable, its argv, its `--json` event parsing, and
its failure classification in one place.

For Codex, both streaming and batch calls use `codex exec --json`; the batch
wrapper collapses the JSONL stream to the final agent message before existing
authoring/audit parsers see it. That keeps `create`, `detail`, `review`, and
apply-style calls on the same final-message contract as `run`.

For Cursor Agent, both streaming and batch calls use
`agent -p --output-format stream-json --force --trust`; batch normalization
uses the terminal `result.result` string the same way.

For per-family backend guidance — which backend to prefer for proposal,
detail, reconcile, implementation, or apply work — see
the [backend recommendations](docs/evidence/backend-recommendations.md),
regenerated from the synthetic [backend-quality benchmark](docs/evidence/benchmark-design.md)
(re-run procedure in
[`RUNBOOK.md`](RUNBOOK.md#which-backend-for-which-task-family)).

### Selecting a backend

Backend selection precedence is: the explicit `--backend` flag, then a
recognized `--model` family, then the `PLAN_TOOL_BACKEND` environment
variable, then the default `claude`. `gpt-*`, `chatgpt-*`, `o1`/`o3`/`o4`, and
`codex-*` select Codex; `claude-*` selects Claude; and `gemini-*` selects the provisional
`gemini` backend until a packaged Gemini integration is available. Other model
names stay on the configured backend. An explicit `--backend` remains the
escape hatch for an intentional non-default pairing.

```bash
plan-tool --backend codex run my-feature        # one run against codex
plan-tool --backend cursor run my-feature       # one run against Cursor Agent
PLAN_TOOL_BACKEND=codex plan-tool run my-feature # same, via the env var
plan-tool --model gpt-5.6-terra run my-feature  # infers the Codex backend
```

`--backend` is a global flag (a sibling of `--no-wait-on-rate-limit`),
applied once in `main()` before dispatch. Its argparse default is `None`,
so an unset flag lets a recognized model family or the env var choose the
backend, while a literal `--backend claude` wins over both. Internally the
selection name is mapped to a registered backend via `resolve_backend(name)`.

### Rate-limit recovery

Rate-limit recovery is separate from backend selection. For an ordinary
recoverable short rate limit, the default is `--on-rate-limit wait`: plan-tool
sleeps until the parsed reset time, then retries the same backend. Selection
precedence is: `--on-rate-limit`, then the legacy `--no-wait-on-rate-limit`
alias (`stop`), then `PLAN_TOOL_ON_RATE_LIMIT`, then `wait`.

```bash
plan-tool --on-rate-limit stop run my-feature
plan-tool --on-rate-limit switch --fallback-backend codex run my-feature
PLAN_TOOL_ON_RATE_LIMIT=ask plan-tool run my-feature
PLAN_TOOL_ON_RATE_LIMIT=switch PLAN_TOOL_FALLBACK_BACKEND=codex plan-tool run my-feature
```

For an ordinary short rate limit, the actions are:

- `wait`: sleep until reset and retry the same backend.
- `switch`: retry the current rate-limited call with the fallback backend, then
  restore the backend that was active before the call. The fallback comes from
  `--fallback-backend` or `PLAN_TOOL_FALLBACK_BACKEND`; the flag wins. Later
  calls, sibling parallel workers, and serial replay do not inherit the
  fallback backend.
- `stop`: return immediately so the printed resume command can be run later.
- `ask`: on an interactive stdin+stderr, show `rate limit [w/b/s]:` for
  wait, backend switch, or stop; in headless runs it stops instead of waiting
  for input.

**Confirmed Cursor monthly plan quota.** Cursor's provider-confirmed monthly
plan-quota result is terminal for the current call. It returns after the first
failed attempt and does not wait, prompt, select a fallback backend, back off,
consult the retry guard, or retry. Its displayed `monthly cycle ends on
<date>` value is a calendar date, not a local reset time or timer target.
Resolve the provider quota or wait for Cursor's actual reset, then start a new
command invocation. Other short rate limits keep the policy above.

### codex prerequisites

The `codex` executable must be installed and on `PATH`, and authenticated:
its credentials live under `~/.codex` (`config.toml` + `auth.json`),
populated by `codex login`. When a backend is **explicitly** selected (via
the flag or the env var) and its binary is absent, the run fails fast with
an install/PATH hint and exit code `127` (`EXEC_NOT_FOUND_EXIT`). The
default-`claude` path keeps its lazy per-call guard instead, so
binary-less read-only commands (`list`, `status`, `validate`) still work
with nothing installed. A run against an unauthenticated codex surfaces an
auth-failure message and does **not** wait or retry — fix the credentials
and re-run (see [`RUNBOOK.md`](RUNBOOK.md#codex-backend-prerequisites--auth)).

### cursor prerequisites

The `agent` executable must be installed and on `PATH`, and authenticated via
`agent login` or the `CURSOR_API_KEY` environment variable. Explicit selection
(`--backend cursor` or `PLAN_TOOL_BACKEND=cursor`) fails fast with exit `127`
when `agent` is absent, same as codex. Unauthenticated runs surface an auth
failure on stderr and do not retry — see
[`RUNBOOK.md`](RUNBOOK.md#cursor-agent-backend-prerequisites--auth) and
the [Cursor Agent CLI contract](docs/reference/contracts/cursor-agent-cli.md).

See the [Codex CLI contract](docs/reference/contracts/codex-cli.md) for the exact
flags and event schema — it is the version-pinned contract (captured against
`codex-cli 0.142.0`) to re-capture when codex upgrades, rather than
restating drift-prone flag spellings here.

### Sandbox-mode mapping

codex's workspace-write sandbox with never-prompt approval is the
equivalent of claude's `--permission-mode acceptEdits`: edits are applied
without per-action prompts. The literal flag spelling
(`-s workspace-write` plus `--skip-git-repo-check` so scratch contexts
without `.git` still run) lives in the contract doc, where it is
version-stamped and pinned by the argv tests.

### Stats unavailable under codex

codex does not report per-call `cost_usd` or `cache_creation_tokens`, so
those fields stay `None` and the `runs` profile renders them as `-` (the
fields are `Optional` on `run_log.py:ClaudeCallEnd` and degrade gracefully
in `plan_tool/cli/runs.py`). Token in/out, `cache_read_tokens` (from
codex's `cached_input_tokens`), and wall-clock remain populated, so the
run-log surface and `runs diff` still work — just with empty cost/cache-
creation columns.

## Lessons log behavior

If frontmatter includes `lessons: <path>`, successful `run` mode appends a timestamped line to that file:

```
- 2026-04-22T15:30:45Z step 2: Build the parser
```

Review modes do not append. The log is append-only. See
[Lessons consolidation](#lessons-consolidation) for the consolidate
subcommand and the opt-in write-path hooks that operate on the same
files.

## Lessons consolidation

`plan-tool lessons consolidate` scans the lessons files plan-tool
maintains for near-duplicate and conflicting bullets, then either
diffs the proposed cleanup (the default) or rewrites the files in
place (`--apply`). Three discovery scopes are walked in a stable
order: the per-user `~/.plan-tool/lessons/general.md`, the per-repo
`<repo-root>/.plan-tool/lessons/project.md`, and every per-plan
`lessons.md` resolved through a plan's `lessons:` frontmatter field
(`--plan <slug>` scopes the run to one plan's file). The posture is
fail-safe: it diffs by default and never touches disk, `--apply`
rewrites behind a Y/N confirmation, and a non-TTY caller must pass
`-y` to apply or the command exits non-zero rather than rewrite
unattended. Only duplicates drive a removal; conflicts are surfaced
for manual editing and never auto-removed.

```bash
plan-tool lessons consolidate                       # diff the proposed cleanup; never writes
plan-tool lessons consolidate --apply               # rewrite in place (confirms on a TTY)
plan-tool lessons consolidate --min-confidence 0.9  # require higher equivalence confidence
```

**Opt-in write-path hooks.** `plan_tool.lessons.append_lessons` carries
two opt-in pre-write hooks, both defaulting to `False`:
`strict_check` runs `find_lesson_equivalences` against the substring
survivors and *refuses* to write a candidate the primitive flags as a
duplicate or conflict; `warn_check` is the audit-only sibling that
keeps the write but records the finding. Either hook's findings are
appended to `.plan-tool/lessons-warnings.jsonl` so the consolidate pass
can later rank repeat offenders. The defaults are unchanged, so
existing callers see the historical substring-dedupe behavior.

**Recurrence weighting.** The consolidate handler reads
`.plan-tool/lessons-warnings.jsonl` via `load_warnings` /
`recurrence_counts`, so findings flagged on prior sessions sort ahead
of first-time judgments and carry a `recurrence=N` annotation. The log
is rolling-cap trimmed (`DEFAULT_WARNINGS_CAP` records) and gitignored;
pass `--ignore-recurrence` to skip the read and see the raw primitive
order.

See [RUNBOOK.md → Workflow: consolidate lessons files](RUNBOOK.md#workflow-consolidate-lessons-files)
for end-to-end recipes.

## Console progress reporting

Every claude-invoking subcommand (`run`, `verify-all`, `detail`,
`jira`, `reconcile-plan`, `create --from*`) prints status lines on
**stderr** during in-flight calls. Stdout stays byte-identical (or
streams `claude --verbose` for `run` / `verify-all`).

```
[1/3] step 1: Wire up the renderer…
        15s elapsed
        30s elapsed
        done in 47s (4.2 KB response)
```

- **Start line** (`[N/M] <label>…`) — one per claude invocation.
  `run` and `verify-all` append `(mode=<mode>)`.
- **Heartbeat** (`Ns elapsed`) — every 15s while the call is in
  flight.
- **Close line** — `done in Xs (YKB response)` on success;
  `FAILED in Xs: <reason>` on failure.
- **`[N/M]` counts invocations**, not target steps. Idempotent skips
  and `--dry-run` paths emit nothing.
- **Stdout is preserved** — `plan-tool jira --format json | jq`
  works; `run` / `verify-all` continue to stream `claude --verbose`.

See [`RUNBOOK.md`](RUNBOOK.md#progress-output-during-long-claude-calls)
for sample output, scripting implications, and how to suppress.
Implementation: `plan_tool/progress.py` (`ProgressReporter`,
`StderrReporter`, `NullReporter`). Roadmap does not use this heartbeat
contract: its ordinary stage run owns separate, transition-only stderr status;
see [0. `roadmap`](#0-roadmap--stage-a-project-sized-concept-optional).

## Correctness gates

Validation primitives from `review.py`, applied across every
claude-invoking subcommand. Under `--iterate`, `create`, `detail` (when explicitly requested), and
`completeness-audit` loop their supported gates → hand
findings to `apply-finding` → re-audit until convergence. See
[Iterating to convergence](#iterating-to-convergence---iterate).

- **`run` pre-flight** — refuses on any `MISSING_PARENT` path or
  plan-wide path-style mismatch before invoking claude (every mode,
  including read-only review modes). `--allow-missing-parent` overrides
  for steps that legitimately create files under a new directory.
- **`run` post-flight** — warns when `## Summary` is missing (the plan
  still advances), and **blocks** a step that declares files when none of
  them changed content during the call (mutating mode only): exit 1, "no
  edits applied", plan not advanced. Steps that declare no files are exempt.
- **Review-mode result summarization** — every review prompt
  (`check`, `reconcile-plan`, `optimize`, `document`, `test`, `security`,
  `lint`) requires a `## Findings` block with severity tokens
  (`CRITICAL` / `HIGH` / `MEDIUM` / `NIT`). `run --mode <review>` and
  `verify-all` print per-step verdict lines; a completed audit exits 0
  even with critical findings — the verdicts carry the result, not the
  exit code. `verify-all` accepts `--fail-on-findings` to exit non-zero
  on a critical finding for CI gating.
- **`jira` parser hardening** — enforces a positive `estimate_hours`
  (advisory size; `--max-hours` is a soft target, not a cap), unique
  `S<N>` ids, intra-response `depends_on` resolution, and full
  plan-step coverage (every plan step must appear in at least one
  story's `steps`). Soft-warns to stderr on missing file paths instead
  of rejecting (claude may legitimately propose a new file).
- **`detail` response gate** — requires all seven mandatory H2 sections
  (Summary / Table of Contents / Why / Files / Implementation / Tests /
  Acceptance criteria); warns when fewer than half of `step.files` are
  mentioned in the body. Summary and Table of Contents are
  reviewer-facing scaffolding so a person auditing the file can orient
  before reading the implementation walkthrough.
- **`create` hardening** — re-parses the written plan from disk before
  returning success; validates the lessons path lives inside the repo root;
  routes file-backed source through preflight, direct assessment, or one
  visible preparation result without a size-based raw-source fallback.
- **`plan-tool verify-all --rollup <name>`** — runs the reconcile prompt across
  every done step and emits an aggregated `[OK]` / `[WARN]` / `[FAIL]`
  per step (versus `verify-all`, which dumps raw output). Empty
  done-step plans print `nothing to verify` and exit 0.

These items appear in the **Deferred** sections of the shipped
progress-reporting work and the correctness-checks plan above, and are
explicitly out of scope for those initial implementations:

**Progress reporter (shipped, follow-ups deferred):**

- `--quiet` / `--no-progress` flag for the progress reporter.
- `PLAN_TOOL_HEARTBEAT_SECONDS` env var to tune the tick interval; TTY
  detection for overwrite-in-place output; adaptive heartbeat cadence.
- Aggregate `Total: M/M done in Xs` summary line at end of multi-step
  runs.

**Correctness checks (shipped, follow-ups deferred):**

- `--strict-post-flight` flag that promotes `run` post-flight warnings
  to errors.
- `plan-tool doctor` — unified pre-everything gate that runs every
  correctness check at once.
- Auto-fix suggestions for jira stories that aren't atomic PRs (e.g.
  proposing a consolidation or an independently-shippable split).
- Cross-step coherence checks (e.g. step 3 deletes a symbol that step
  7's review still references). Sequential per-step audits remain the
  design.
- Backporting `verify-all` failures into plan state (e.g. flipping a
  `done` step back to `pending` on reconcile failure). Output stays
  read-only; mutating done state is reserved for the user.

## Per-subcommand reconcile

Reconcile splits along the **direction of truth**. The subcommand
*is* the direction declaration — no per-finding gate, no runtime
allow-list. Each side has its own prompt, persistence kind, and
apply path.

| Subcommand | Truth source | Findings produce | Persistence kind |
| --- | --- | --- | --- |
| `plan-tool detail <name> --reconcile` | Code on disk | Plan / detail edits (`step.files`, status flips, body updates) | `detail-reconcile` |
| `plan-tool reconcile-code <name>` (legacy: `run --reconcile`) | Plan | Code edits (inline via Claude Edit/Write under `--permission-mode acceptEdits`) | `run-reconcile` |

Persistence path:
`<plan-dir>/plan-details/<plan-slug>/reports/<ts>-<kind>.json`.

### `plan-tool detail <name> --reconcile` — code-is-truth

```bash
plan-tool detail my-feature --reconcile --step 3
plan-tool detail my-feature --reconcile --all
```

Prompt: `prompts/detail-reconcile.md`. Walk dispatches each finding
through `apply_finding` (the same helper that backs `plan-tool
review`).

`--all` sweeps the per-step audit across every step **not yet
`done`** (one claude call per step, mutually exclusive with
`--step`). Done steps are skipped by design: their detail files are
historical records of delivered work, so re-auditing them against
code that has since moved on produces churn, not signal — the
valuable targets are the remaining steps whose details may have
drifted from the evolving codebase before they execute. The plan is
re-parsed between steps, so a target marked `done` mid-sweep is
skipped too. The sweep halts on the first per-step failure and
propagates that rc. Unlike `run --all`, `-y` is **not** implied — on
a TTY you walk each step's findings interactively; pass `-y` for
unattended apply-everything runs.

### `plan-tool reconcile-code <name>` — plan-is-truth

The code-side counterpart to `reconcile-plan`. Legacy form: `run --reconcile` (still works).

```bash
plan-tool reconcile-code my-feature --step 3
plan-tool reconcile-code my-feature --all
```

Prompt: `prompts/run-reconcile.md`. Code edits land inline; no walk. `--all`
sweeps every plan step in order, including `done` steps, skipping only steps
declared explicit `non-code`, and stops at the first step whose audit fails to
*complete* (a redirect or a critical finding does not halt the sweep — read
each step's printed verdict). It is mutually exclusive with `--step` and with
`--reuse-id` (a pinned save can't mean anything sensible across every step).

### The `## Redirect` sub-block

When `run --reconcile` surfaces a finding whose root cause is in the
plan rather than the code, Claude emits a per-finding `## Redirect`
sub-block instead of attempting a code edit:

- CLI parses the redirect (`review.py: parse_redirect_block`).
- Surfaces it on stderr as `[REDIRECT] step N — see detail --reconcile`.
- The audit exits 0 whether or not a redirect was emitted — act on the
  `[REDIRECT]` line, not the rc.

The mirror holds for `detail --reconcile`: a finding rooted in the
code is the wrong subcommand; switch to `run --reconcile`.

## Completeness gates

Correctness gates check *structural* well-formedness (paths, deps,
response shapes). Completeness gates check *coverage* — is anything
missing? Both apply on three axes, distinguished by what is compared
against what:

- **Coverage** (`detail`) — does the plan cover the existing code?
  (plan ⊇ code)
- **Fulfillment** (`run` / `verify-all`) — do the code changes cover the
  plan? (code ⊇ plan)
- **Conceptual** (`completeness`) — are the plan's own concepts correct
  and complete, grounded in the per-step detail bundle and the code at
  HEAD? (plan ⊨ its own problem)

Within each axis there are two layers:

- **Deterministic** — no claude calls (path/dep/section/coverage
  checks).
- **Semantic** — claude calls. `completeness` samples the conceptual
  audit until findings run dry (typically 2-3 calls; tune with
  `--audit-samples` / `--audit-dry-rounds`); `reconcile-plan` and `verify-all` make
  theirs per the table below. Under `--iterate`, `create`, `detail`,
  `completeness-audit` re-audit until findings
  converge. See
  [Iterating to convergence](#iterating-to-convergence---iterate).

The audit verbs split by lifecycle phase:

| Verb | When | Asks | Claude? |
| --- | --- | --- | --- |
| `completeness` | Pre-handoff | Deterministic: any authoring gaps (sections, detail files, lessons)? Then a conceptual audit: are the plan's own concepts correct and complete, grounded in the detail bundle + code at HEAD? | Yes (sampled until dry, typically 2-3 calls — the conceptual audit) |
| `reconcile-plan` | Stale plans / supplement | Does the plan still match code that may have drifted since it was written? | Yes (one call) |
| `verify-all` | Post-implementation | Did each done step actually do what it claimed? | Yes (one call per done step) |
| `verify --deep` | Post-implementation | Does each acceptance bullet on each done step hold? | Yes (one call per bullet) |

`validate` checks frontmatter schema only — niche, since every other
subcommand re-validates on load.

Findings produced by these checks:

- **Body section completeness** — required H2s (Overview / Problem
  statement / Architecture / Steps / Out of scope / Risks / Testing /
  Acceptance criteria / Deferred) absent or filled with `_(TODO)_`.
  Suppress per-section with
  `<!-- completeness:skip <Section> -->` inside the section body.
- **Detail file coverage** — steps without a `step.detail` set
  (info-severity; pure-analysis steps with empty `files:` and
  low/null complexity are exempted). Steps with a declared-but-
  missing detail file (medium-severity). Skipped for `done` steps —
  the detail's briefing job is finished once a step is implemented.
- **Detail body completeness** — for each detail file on disk, the
  seven required H2 sections (Summary / Table of Contents / Why /
  Files / Implementation / Tests / Acceptance criteria) must exist
  with non-empty, non-placeholder bodies. Summary and Table of
  Contents are reviewer-facing scaffolding so a person auditing the
  file can orient before reading the implementation walkthrough.
  Skipped for `done` steps (a thin detail body is a pre-execution
  authoring gap, moot after implementation).
- **Files coherence** — drift between the detail body's backtick-
  cited paths and the step's recognized path set
  (`step.files ∪ step.allowed_mentions`). A detail body legitimately
  cites many *context* files it reads but doesn't edit, so only a
  cited path that **looks like a near-miss of a declared path** is
  flagged (`info`) — same basename in a different directory (the
  canonical `packages/web/Foo.tsx` declared vs `apps/web/src/Foo.tsx`
  cited drift) or a near-identical full path (a typo in the basename).
  An ubiquitous basename (`index.ts`, `__init__.py`, …) doesn't match
  on name alone. Citations bearing no resemblance to a declared path
  are treated as context references and produce **no finding**. A
  genuine near-miss that's actually an intentional citation can be
  endorsed by adding the path to the step's `allowed_mentions:` list.
  `nit` when `files:` declares a path the detail body doesn't mention.
  Neither severity fails `plan-tool completeness` — both are advisory.
  Skipped for `done` steps — coherence is a pre-execution authoring
  signal; code-vs-plan divergence on an implemented step is the semantic
  review's and `verify-all`'s job instead.
- **Lessons coverage** — when `plan.lessons` is set, every `done`
  step should have an entry naming `step <id>:` in the log. Missing
  log file or missing entries surface as warnings.
- **Test-strategy alignment** (`test-strategy` findings) — emitted only
  when some steps declare `change_type`. A plan-level `info` nudge when
  some steps are classified and siblings aren't; a per-step `medium`
  when a `non-code` step's `files`/`creates` include a production source
  path. The sampled `plan-audit` adds a **purity probe** that flags a
  code step mixing behavior-preserving restructuring with new behavior
  (docs/config riding along is not mixing; the fix is splitting it into
  type-pure steps). All render as advisory structural diagnostics, and
  plans with no classified steps produce none of them. See
  [`PLAN_FORMAT.md`](PLAN_FORMAT.md#field-semantics) for the
  classification.
- **`plan-tool completeness-audit <name>`** — aggregates the five
  deterministic checks plus a conceptual audit
  (`prompts/plan-audit.md`, sampled until findings run dry and unioned
  by stable anchor id; `--audit-samples` / `--audit-dry-rounds`) into a
  single grouped report. The audit reads the plan grounded in the
  per-step detail bundle (and may Read/Grep the repo at HEAD, so it
  doesn't re-flag gaps a detail file already specifies) and emits two
  finding lists: *correctness* (unsound or contradictory concepts) and
  *completeness* (orphaned concepts, uncovered risks, dangling
  acceptance criteria, missing edge cases). `--json` emits a
  CI-friendly object with a `plan_audit` array (each entry tagged
  `axis: correctness|completeness`). Correctness findings —
  deterministic (path-style, dep validation) and conceptual alike —
  render under a "Correctness (run these first)" header above the
  completeness groups, so users always see blockers ahead of coverage
  gaps. The conceptual coverage findings render under "Conceptual
  completeness". Every non-JSON ordinary final run writes a markdown report to
  `plan-details/<slug>/reports/<ts>-completeness.md` and a structured
  sidecar `plan-details/<slug>/reports/<ts>-completeness.json` that
  `completeness-apply` consumes. A non-JSON terminal Cursor plan-quota stop
  still saves the readable Markdown report, but withholds that reusable final
  findings sidecar; resolve the provider condition and run a fresh audit. Under
  `--iterate` the terminal shows
  only a concise summary + the report path; the conceptual-completeness
  gaps are advisory inside the audit's iterate loop (chasing every new
  gap would never converge), and the report explains how to address
  them via the apply pair.
- **`plan-tool completeness-apply <name>`** — paired with
  `completeness-audit`: walks the conceptual-completeness gaps from
  the most recent saved audit and applies gap-closing edits via claude,
  one finding at a time. Does NOT re-run the audit — it replays the
  saved findings, so addressing a single gap doesn't require a full
  re-audit. Always interactive propose-then-confirm, one gap at a time —
  every conceptual gap is a judgment call, so there is no blanket
  auto-apply; a non-interactive stdin skips the walk and reports the gaps.
  `--anchor <slug>` (repeatable) restricts the walk to specific gaps by
  their `[anchor-slug]` (each finding in the report carries its anchor).
  Run `completeness-audit` afterwards to verify addressed gaps drop off.
- **`plan-tool data-contract-apply <name>`** — paired with
  `completeness-audit` for saved `DATA_CONTRACT.md` drift. It walks only
  fresh structured `data-contract` payloads saved by the audit, annotates
  the same saved-review sidecar, and leaves conceptual gaps to
  `completeness-apply`. Stale payload fingerprints require a fresh audit
  before applying.
- **`plan-tool verify-all --rollup <name> --deep`** — extends `verify-all` with a
  per-acceptance-bullet check. For each done step, parses the
  detail file's `## Acceptance criteria` bullets and asks claude
  to verify each individually via `prompts/reconcile-deep.md`.
  Per-step rollup: any FAIL → fail; mixed PASS+UNKNOWN → warn; all
  PASS → pass.

**Completeness gates (shipped, follow-ups deferred):**

- `plan-tool plans-doctor` — cross-plan rollup of completeness
  findings across the whole manifest.
- `validate --strict-body` — promote body-completeness warnings to
  errors. Today they're advisory only.
- Auto-fill of missing sections via claude.
- Suppression markers for non-body completeness checks (the
  body-section skip marker is the only one today).
- Backporting `verify --deep` results into plan state.

## License

plan-tool is licensed under the [Apache License 2.0](LICENSE).
