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
handoffs. Small, straightforward edits can skip plan-tool.

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

Add optional [companion skills](docs/how-to/companion-skills.md) for the
project's stack, testing, debugging, review, or release work. The guide covers
selection and compatibility across Claude Code, Codex, and Cursor.

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git,
then keep a dedicated clone for the CLI that the skill invokes. `uv` manages
the Python runtime:

```bash
git clone https://github.com/rupe120/plan-tool.git
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

For a first exercise, choose a small, independently testable feature to learn
the planning workflow. For a single obvious edit, skip plan-tool: edit, test
and review directly. Open the repository in your assistant and ask:

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

After reviewing the plan, details and audits, choose a separate follow-up request.
Before execution in a repository with `origin`, publish the plan and all step
details through your normal review process, merge them into the remote default
branch, and fetch it. Create an implementation branch from that default branch;
`run` normally refuses execution on the default branch or when planning artifacts
are missing from its remote copy. Repositories without `origin` skip this check.
See the [execution prerequisites](docs/how-to/pipeline/run.md#before-execution).

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
[common workflows](docs/how-to/common-workflows.md), and [command reference](docs/reference/commands.md).

## Core subcommand workflow

```
(roadmap) → create → bare audit → detail → detail audit ──┬── run → reconcile-code → review
                                                        └── jira → verify
```

| Step | What it does |
| --- | --- |
| **`roadmap`** | *(optional, project-sized)* Stage a concept brief into four gated architecture artifacts; materialize and review selected draft seeds separately before `create`. |
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
| [A project-sized concept](docs/how-to/choose-a-starting-point.md#stage-a-project-sized-concept) | `roadmap <slug> --from-existing <brief.md>` | `roadmap` publishes staged artifacts; review the mapping, then materialize and review selected seeds. |

<a id="table-of-contents"></a>

## Plan format

Each plan is markdown with YAML frontmatter. Frontmatter is the machine-readable source of truth; prose below it is for humans.

```markdown
---
format_version: 1
title: Example Plan
intent: Parse and validate plan frontmatter before execution.
status: in-progress
priority: medium
steps:
  - id: 1
    title: Add YAML schema validator
    intent: Reject invalid frontmatter with actionable errors.
    files: [plan_tool/schema.py]
    complexity: low
    status: done
  - id: 2
    title: Build the parser
    intent: Load valid frontmatter into typed plan models.
    files: [plan_tool/parser.py]
    allowed_mentions: [plan_tool/schema.py]
    complexity: medium
    depends_on: [1]
    status: current
---

# Example Plan
...
```

The example shows the frontmatter structure; `create` authors the full plan
body. See [Plan format](PLAN_FORMAT.md) for the complete contract,
[Seed format](SEED_FORMAT.md) for input briefs, [Detail format](DETAIL_FORMAT.md)
for per-step instructions, [Roadmap format](ROADMAP_FORMAT.md) for staged
architecture, and [Jira format](JIRA_FORMAT.md) for exported stories.

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

<a id="plan-workflow"></a>

## Common workflows

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

## Current code layout

<a id="the-plan-tool-directory"></a>

See [Architecture](docs/ARCHITECTURE.md) for module ownership and import boundaries.
The [data contract](DATA_CONTRACT.md) describes persisted state; commit durable
project records and retain runtime evidence needed for review or recovery.

## Develop and test

<a id="git-hooks"></a>

Follow [Contributing](CONTRIBUTING.md#develop-and-test) for checkout setup, tests,
and git hooks. Use `uv run plan-tool` from your development checkout to test
that build; the global editable install can point at a different clone.

## CLI usage

<a id="placeholders"></a>
<a id="plan-tool-detail"></a>

Use the [command guide](docs/reference/commands.md) for command summaries and
argument conventions, or the generated [CLI reference](docs/cli/README.md) for
every option. [Detail authoring](docs/how-to/pipeline/detail.md) explains the
per-step draft and review workflow.

## Running headlessly

<a id="plan-tool-create-headlessly"></a>
<a id="plan-tool-detail-headlessly"></a>
<a id="plan-tool-reconcile-plan--reconcile-plan-walk-headlessly"></a>
<a id="streaming-output-back-to-a-chat-agent"></a>
<a id="iterating-headlessly"></a>

See [headless operation](docs/OPERATIONS.md#running-headlessly) for closed stdin,
confirmation flags and output capture. Read saved reports and monitor the
original invocation to confirmed exit before starting another invocation.

## Resuming after a failure

<a id="managing-checkpoints"></a>

Use [recovery guides](docs/how-to/recovery/README.md) and
[checkpoint operations](docs/OPERATIONS.md#resuming-after-a-failure). Inspect the
original process and its recorded outcome before resuming; a quiet process is
not evidence that it has exited.

## Iterating to convergence (`--iterate`)

<a id="carve-an-over-packed-step-out-plan-tool-scope-out"></a>
<a id="see-a-plans-split-criteria-plan-tool-split-criteria"></a>
<a id="defaults"></a>
<a id="when-to-use---iterate"></a>
<a id="how-the-loop-terminates"></a>
<a id="checkpoint-interaction"></a>
<a id="headless"></a>
<a id="operational-recipes"></a>

`create` iterates by default. Pass `--iterate` explicitly to
`completeness-audit`; keep `detail` one-shot unless iterative detail authoring
is explicitly requested. Read conceptual findings, make judged edits, commit,
and re-audit. See the [audit guide](docs/how-to/pipeline/audit.md) for coverage,
qualification and stopping rules, and [iteration reference](docs/ITERATION.md)
for supported routes and flags.

## Run logs

<a id="roadmap-seed-actions"></a>
<a id="inspecting-recent-runs"></a>
<a id="reading-one-run"></a>
<a id="comparing-two-runs"></a>
<a id="the-in-flight-snapshot"></a>
<a id="cleanup"></a>

Use [Operations](docs/OPERATIONS.md#run-logs) to inspect runs, lifecycle evidence
and in-flight snapshots. Logs and checkpoints support diagnosis and recovery;
retain evidence until the active work and review no longer need it.

## Worktrees (parallel plans)

<a id="caveats-sharp-edges"></a>

See [worktree operations](docs/OPERATIONS.md#worktrees-parallel-plans) for
isolation choices and their limits. Keep invocation state and branches separate
when running multiple plans.

## Modes

See [run modes](docs/cli/run.md) for execution and report modes. A rendered
`--dry-run` prompt does not execute or verify the work.

## Backends

<a id="selecting-a-backend"></a>
<a id="rate-limit-recovery"></a>
<a id="codex-prerequisites"></a>
<a id="cursor-prerequisites"></a>
<a id="sandbox-mode-mapping"></a>
<a id="stats-unavailable-under-codex"></a>

Install and authenticate the backend CLI separately from the assistant skill.
[Backends](docs/BACKENDS.md) covers selection, prerequisites, sandbox mapping and
rate-limit recovery. The default backend is Claude; choose another explicitly
with the global `--backend` option before the subcommand.

## Lessons log behavior

See [project lessons](docs/explanations/lessons-learned.md) for the working model
and [lesson commands](docs/cli/lessons.md) for inspection.

## Lessons consolidation

Use the [consolidation command reference](docs/cli/lessons.md#plan-tool-lessons-consolidate) for
reviewing and condensing accumulated lessons.

## Console progress reporting

See [console progress](docs/OPERATIONS.md#console-progress-reporting) for
progress lines and verbosity. Monitor long commands through their confirmed
exit; backend completion alone does not establish command completion.

## Correctness gates

See [Gates](docs/GATES.md) and the [run flow](docs/how-to/pipeline/run.md) for
blocking checks, advisory findings and execution advancement.

## Per-subcommand reconcile

<a id="plan-tool-detail-name---reconcile--code-is-truth"></a>
<a id="plan-tool-reconcile-code-name--plan-is-truth"></a>
<a id="the--redirect-sub-block"></a>

`reconcile-plan` uses current code to update an unexecuted plan. After
execution, use `reconcile-code` to bring code into line with the plan. See
[reconciliation gates](docs/GATES.md#per-subcommand-reconcile) for the contract.
A completed execution continues through a full `reconcile-code --all` sweep
and code review to convergence.

## Completeness gates

Audit the bare plan before details, then audit the complete detail bundle
before execution or export. The [audit guide](docs/how-to/pipeline/audit.md)
explains saved reports, qualified results and judged session-directed fixes.

Read the saved report, verify and judge the findings, edit the appropriate plan or detail text, commit bounded corrections, and re-run `completeness-audit --iterate --commit` against the changed snapshot.

<a id="0-roadmap--stage-a-project-sized-concept-optional"></a>

## Roadmap review

Use the [roadmap walkthrough](docs/how-to/roadmap.md) for the complete lifecycle.
`roadmap --compare` provides read-only two-snapshot review of Git revisions or
accepted versions. Ordinary feedback uses `--propose-candidate` to snapshot
eligible ledger items into an inert candidate; review and promotion are separate.

## Related work and alternatives

AI-assisted development is a new space, and no single approach has settled it.
plan-tool is one take; it is not the only reasonable one.

- **AI-DLC (AWS Labs).** An open-source methodology
  ([awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows), MIT-0)
  that steers your coding assistant through structured phases with human approval
  gates. It is a good alternative, and the two projects can learn from each other.
  - **How it compares:** both work through your coding assistant and back their
    prompts with deterministic code. AI-DLC pairs steering rules with an engine
    and hooks that enforce stage order and plan approval, and it covers the
    lifecycle through operation. plan-tool focuses on the plan: machine-readable
    frontmatter, audits iterated to convergence before anything runs, and
    reconciliation between plan and code in both directions.
  - **They compose:** an orchestration layer can drive both
    ([details](docs/integrations/aidlc-integration.md)).
  - Compared from each project's documentation on 2026-11-06, not line by line.
- **Other spec-driven tools.** GitHub's
  [Spec Kit](https://github.com/github/spec-kit) and
  [OpenSpec](https://github.com/Fission-AI/OpenSpec) take lighter-weight
  approaches to the same problem and support many more assistants.
- **An example governance policy.** The
  [AI-assisted development policy](docs/reference/ai-assisted-development-policy.md)
  (also available as [`AI_SDLC_POLICY.pdf`](AI_SDLC_POLICY.pdf)) shows what a team
  policy around AI-assisted work might look like. It is an example to adapt, not
  a standard.

If you are building something in this space, issues and pull requests on the
GitHub repository are welcome, including corrections to how another project is
described here.

## License

plan-tool is licensed under the [Apache License 2.0](LICENSE).
