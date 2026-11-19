<a id="plan-tool---audited-plans-your-coding-assistant-can-carry-out"></a>

# plan-tool

**Audited plans your coding assistant can carry out.**

Give Claude Code, Codex, or Cursor a rough request. Review the plan and its
audits before asking the assistant to implement it step by step. The plan,
audit reports, and progress stay in your repo so you can resume the work or
hand it off.

[![version](https://img.shields.io/github/v/release/rupe120/plan-tool?label=version&color=blue&style=flat)](https://github.com/rupe120/plan-tool/releases/latest)
[![license](https://img.shields.io/github/license/rupe120/plan-tool?color=green&style=flat)](LICENSE)
[![tests](https://github.com/rupe120/plan-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/rupe120/plan-tool/actions/workflows/ci.yml)

Use it when the work has dependent changes, spans several sessions, or will be
handed off. For a small edit, skip it and just make the change.

<a id="start-here"></a>

## Your first plan

With the [skill installed](#install-the-skill), start with one sentence.

> use the plan tool skill to create a website scraper cli

In a real run, the scope settles on Python, one URL, CSS selectors and JSON.
The plan breaks the work into testable steps (condensed):

```text
1. Package and CSS text extraction
2. HTTP fetching with timeout and redirect limits
3. Installed CLI, JSON output and end-to-end tests
```

After approval to implement, code review catches an error the initial tests miss:

```text
[P2] Handle unsupported pseudo-elements as selector errors
p::before produces a traceback instead of the expected exit code 2.
```

The assistant fixes it and adds regression tests. The final suite passes
**98 tests**, followed by two clean code reviews. You get the plan, step details,
audit reports and tested code in Git.

[Install the skill](#install-the-skill) · [Follow a worked plan](#follow-a-worked-plan)

<a id="use-with-your-assistant"></a>
<a id="install"></a>

## Install the skill

<a id="requirements"></a>
<a id="install-the-cli"></a>

Install the `plan-tool` CLI, then register the skill with your assistant.
You’ll need uv, Git, and an installed and authenticated backend CLI. uv
provides Python 3.13 or newer. [Backend setup](docs/BACKENDS.md)

```bash
uv tool install git+https://github.com/rupe120/plan-tool
plan-tool --version
```

Before installing the skill, [check which `plan-tool` your shell selects](docs/how-to/install-and-update.md#check-the-selected-executable).

<a id="optional-the-agent-skill"></a>
<a id="install-the-assistant-skill"></a>
<a id="installation-options"></a>

| Assistant | Install its skill |
| --- | --- |
| Claude Code | `plan-tool install-skill --integration claude --user` |
| Codex | `plan-tool install-skill --integration codex --user` |
| Cursor | `plan-tool install-skill --integration cursor --user` |

Reload your assistant and open the Git repository you want to work on.
[Installation options and updates](docs/how-to/install-and-update.md#install-the-assistant-skill) ·
[Companion skills](docs/how-to/companion-skills.md)

## Follow a worked plan

In the worked example, a task-list CLI needs optional due dates and a way to
list overdue tasks. This request asks the assistant to pause at each review
checkpoint.

> Use the plan-tool skill to plan optional due dates and `todo list --overdue`.
> Leave reminders and changes to ordering outside the scope. Inspect the repo
> and show me a seed with verified references, then the plan and bare audit,
> then the details and grounded audit. Link the artifacts, summarize changes,
> and wait for my approval at each checkpoint. Bring scope or design questions
> back to me and stop after detail review, before implementation or export.

If you choose to set up a [project profile](integrations/shared/DIRECTIVES.md#setting-up-a-repository-the-project-profile),
give the assistant your project intent and confirm the exact text before it saves it.

| Review | What the example shows |
| --- | --- |
| [Seed](docs/demos/getting-started/fixtures/1-seed/files/docs/implementation-plans/plan-seeds/due-dates.md) | Store dates, accept them on `todo add`, and filter and display them in `todo list`. Existing task files still load. |
| [Plan](docs/demos/getting-started/fixtures/3-bare-audit/files/docs/implementation-plans/due-dates.md) and [bare audit](docs/demos/getting-started/fixtures/3-bare-audit/transcript.txt) | Three ordered steps. The audit flags an ambiguity about whether a task due today counts as overdue. |
| [Step detail](docs/demos/getting-started/fixtures/4-detail/files/docs/implementation-plans/plan-details/due-dates/03-list-overdue-show-due-dates.md) and [grounded audit](docs/demos/getting-started/fixtures/5-detail-audit/transcript.txt) | The filter test includes an open task due yesterday and excludes one due today. Check the saved report’s qualification and findings before choosing what to do next. |

The bare audit review adds an explicit acceptance criterion.

> A task due today is not overdue; only a due date strictly before today is.

You can step through the artifacts in a disposable Git repo and finish at
detail review. The audit transcripts are authored examples.
[Prepared demo](docs/demos/getting-started/README.md#start)

A live audit saves its report under
`docs/implementation-plans/plan-details/due-dates/reports/` in this example.

<a id="decision-flow"></a>
<a id="common-workflows"></a>
<a id="plan-workflow"></a>
<a id="table-of-contents"></a>

## Choose your next task

| I want to… | Open |
| --- | --- |
| Start from an idea, an existing draft, or an old plan | [Choose a starting point](docs/how-to/choose-a-starting-point.md) |
| Plan a project-sized concept | [Roadmap walkthrough](docs/how-to/roadmap.md) |
| Read a saved audit | [Interpret the final result](docs/how-to/pipeline/audit.md#reading-the-final-qualified-result) |
| Implement the reviewed plan | [Check execution prerequisites](docs/how-to/pipeline/run.md#before-execution) |
| Export local Jira stories and their developer handoff | [Export and review the handoff](RUNBOOK.md#workflow-export-to-jira-for-sprint-planning) |
| Check or resume a command | [Monitor the original invocation through confirmed exit](integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely) |
| Explore other worked examples | [Demonstrations](docs/demos/README.md) |
| Develop plan-tool | [New contributor path](CONTRIBUTING.md#new-contributor-path) |

Request implementation or local export separately after detail review. Tracker
publication needs its own request.

<a id="core-subcommand-workflow"></a>
<a id="placeholders"></a>
<a id="plan-tool-detail"></a>
<a id="modes"></a>

## CLI usage

```text
create → bare audit → detail → grounded audit → run → reconcile-code → review
                                              ↳ jira → verify
```

Run `plan-tool` for the core commands or `plan-tool --help` for the full
catalog. [Common workflows](docs/how-to/common-workflows.md) covers direct
operation. [Command guide](docs/reference/commands.md) · [CLI options](docs/cli/README.md)

## Reference and operations

<a id="plan-format"></a>
<a id="current-code-layout"></a>
<a id="the-plan-tool-directory"></a>
<a id="develop-and-test"></a>
<a id="git-hooks"></a>

### Plans and development

[Format specifications](docs/reference/README.md#format-specifications) ·
[Persisted state](DATA_CONTRACT.md) ·
[Architecture](docs/ARCHITECTURE.md) ·
[Development and tests](CONTRIBUTING.md#develop-and-test)

<a id="running-headlessly"></a>
<a id="plan-tool-create-headlessly"></a>
<a id="plan-tool-detail-headlessly"></a>
<a id="plan-tool-reconcile-plan--reconcile-plan-walk-headlessly"></a>
<a id="streaming-output-back-to-a-chat-agent"></a>
<a id="iterating-headlessly"></a>
<a id="headless"></a>
<a id="resuming-after-a-failure"></a>
<a id="managing-checkpoints"></a>
<a id="run-logs"></a>
<a id="roadmap-seed-actions"></a>
<a id="inspecting-recent-runs"></a>
<a id="reading-one-run"></a>
<a id="comparing-two-runs"></a>
<a id="the-in-flight-snapshot"></a>
<a id="cleanup"></a>
<a id="console-progress-reporting"></a>
<a id="worktrees-parallel-plans"></a>
<a id="caveats-sharp-edges"></a>

### Operating a run

[Headless commands](docs/OPERATIONS.md#running-headlessly) ·
[Recovery and checkpoints](docs/OPERATIONS.md#resuming-after-a-failure) ·
[Logs](docs/OPERATIONS.md#run-logs) ·
[Console progress](docs/OPERATIONS.md#console-progress-reporting) ·
[Worktrees](docs/OPERATIONS.md#worktrees-parallel-plans)

<a id="backends"></a>
<a id="selecting-a-backend"></a>
<a id="rate-limit-recovery"></a>
<a id="codex-prerequisites"></a>
<a id="cursor-prerequisites"></a>
<a id="sandbox-mode-mapping"></a>
<a id="stats-unavailable-under-codex"></a>

### Backend configuration

[Choose and configure a backend](docs/BACKENDS.md#selecting-a-backend)

<a id="iterating-to-convergence---iterate"></a>
<a id="carve-an-over-packed-step-out-plan-tool-scope-out"></a>
<a id="see-a-plans-split-criteria-plan-tool-split-criteria"></a>
<a id="defaults"></a>
<a id="when-to-use---iterate"></a>
<a id="how-the-loop-terminates"></a>
<a id="checkpoint-interaction"></a>
<a id="operational-recipes"></a>
<a id="correctness-gates"></a>
<a id="per-subcommand-reconcile"></a>
<a id="plan-tool-detail-name---reconcile--code-is-truth"></a>
<a id="plan-tool-reconcile-code-name--plan-is-truth"></a>
<a id="the--redirect-sub-block"></a>
<a id="completeness-gates"></a>

### Audit and reconcile

[Audit gates and result qualification](docs/how-to/pipeline/audit.md) ·
[Iteration and stopping rules](docs/ITERATION.md) ·
[Correctness and reconcile gates](docs/GATES.md)

<a id="0-roadmap--stage-a-project-sized-concept-optional"></a>
<a id="roadmap-review"></a>
<a id="lessons-log-behavior"></a>
<a id="lessons-consolidation"></a>

### Roadmaps and lessons

Use `roadmap --compare` for a read-only comparison of Git revisions or stored
versions. Use `--propose-candidate` to turn eligible ledger feedback into a
candidate for separate review. [Complete roadmap walkthrough](docs/how-to/roadmap.md)

[Lessons log](docs/OPERATIONS.md#lessons-log-behavior) ·
[Lessons consolidation](docs/OPERATIONS.md#lessons-consolidation)

[Full documentation map](docs/README.md) · [Project mission](MISSION.md)

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

## Contributing

Issues and pull requests are welcome. [CONTRIBUTING](CONTRIBUTING.md) explains how
changes are reviewed, [SUPPORT](SUPPORT.md) says where to ask questions,
[SECURITY](SECURITY.md) says how to report a vulnerability privately, and the
[code of conduct](CODE_OF_CONDUCT.md) sets the expectations for everyone taking part.

## License

plan-tool is licensed under the [Apache License 2.0](LICENSE).
