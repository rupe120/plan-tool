---
name: plan-tool
description: Turn a feature idea or a project-sized concept into a developer-ready implementation plan, then audit, execute, or reconcile it against the code, spawning a fresh claude subprocess per step. Use when a user wants to plan non-trivial work before coding, resume or check status on an existing plan, audit a plan for completeness or code drift, run a plan step by step, reconcile plan and code, export a plan to JIRA, or turn a larger concept into a staged `roadmap` before a single plan exists. Only for plans whose markdown begins with `---` frontmatter; frontmatter-less markdown is a legacy plan for a different runner.
when_to_use: 'Use for: "I have an idea/concept, turn it into an implementation plan", "let''s roadmap this project", "make a plan for X", "what''s left on plan X" / "continue plan X", "audit plan X for completeness", "does the code match plan X", "reconcile the plan with the code", "export plan X to Jira".'
allowed-tools: Bash Read Grep Glob Edit Write
# model: deliberately unset; the session's own model drives the skill.
# See the plan-tool repo's docs/history/backlog-decisions.md § "#390".
paths:
  - docs/implementation-plans/**
  - plan-seeds/** # retained existing seeds; new seeds live under docs/implementation-plans
  - .plan-tool/plans.json
argument-hint: '[--backend claude|codex|cursor] [--on-rate-limit wait|switch|stop|ask] [--fallback-backend BACKEND] <plan-name> [--step N] [--mode check|optimize|document|test|security|lint] [--reconcile] [--dry-run]'
---

# plan-tool

A Python CLI that drives **YAML-frontmatter implementation plans**: author them,
audit them, then execute locally one step at a time (each step runs in a fresh
`claude` subprocess for context isolation) or export them as JIRA-sized stories.

This file is the router — when to reach for the tool and how to invoke it. For
the full subcommand reference, flag semantics, and operational recipes, follow
the pointers in [Going deeper](#going-deeper). The rules for *driving* a plan —
the two audit gates, the session-directed convergence loop, `--iterate` /
`--commit`, reconcile directionality, roadmap operation, and seed authoring —
live in one shared reference, [DIRECTIVES.md](DIRECTIVES.md), installed
alongside this file.

## Which tool

- Plan markdown **starts with `---` frontmatter** → use **plan-tool** (this skill).
- **No frontmatter** → it's a freeform/legacy plan: route to whatever legacy
  plan runner the project uses. Do **not** add frontmatter automatically — ask
  the user whether to migrate.

## Invocation

`plan-tool` is installed as a global CLI (`uv tool install --editable .` from a
clone of the repo), so invoke it directly via Bash:

```bash
plan-tool <subcommand> [args]
plan-tool run <name> --mode check
```

**Plan discovery** (per-project): `--plans-dir <path>` → `PLAN_TOOL_PLANS_DIR` →
the host repo's manifest at `<repo-root>/.plan-tool/plans.json` (a
`{"plans": [...]}` array of repo-relative `.md` paths; override with
`--manifest <path>`).
**Repo root:** `--repo-root <path>` → `PLAN_TOOL_REPO_ROOT` → walk up from cwd
to `.git`. Nested `.git` folders (sub-repos, submodules) are supported — the
root whose `.plan-tool/plans.json` resolves the most plans wins. Pass
`--repo-root` when auto-detection lands on the wrong directory.

**Backend:** the global `--backend <name>` flag (or
`PLAN_TOOL_BACKEND` env var) picks the CLI that runs steps; when no explicit
backend is set, a recognized `--model` family selects its matching CLI before
the env fallback. `gpt-*`, `chatgpt-*`, `o1`/`o3`/`o4`, and `codex-*` select Codex;
`claude-*` selects Claude; and `gemini-*` selects the provisional Gemini
backend. Precedence is flag > model family > env > default `claude`.
For ordinary recoverable short rate limits,
rate-limit handling is separate: `--on-rate-limit wait|switch|stop|ask` (or
`PLAN_TOOL_ON_RATE_LIMIT`) chooses whether to wait, switch, stop, or prompt;
`switch` needs `--fallback-backend` or `PLAN_TOOL_FALLBACK_BACKEND`. A
confirmed Cursor monthly plan quota bypasses those actions: neither closed
stdin, `-y`, nor an `--on-rate-limit` setting recovers it. Resolve the provider
condition and begin a new command; see RUNBOOK.md's Recovery section (in the
plan-tool repo).

## Running from chat / automation (no TTY)

When you (the agent) invoke plan-tool on the user's behalf, treat every run as
**headless**: close stdin and pass `-y`.

These are independent headless syntax examples, not a stage sequence. For
sequential authoring, use the completeness recipe below and the two audit
gates in DIRECTIVES.md; review and commit judged corrections between stages.

```bash
plan-tool create <slug> --from-existing /tmp/seed.md --output-dir docs/implementation-plans -y < /dev/null
plan-tool detail <slug> --commit -y < /dev/null # requires a clean tree; commit the plan first
plan-tool reconcile-plan <slug> -y < /dev/null # pre-execution only; -y auto-applies every recommendation without judgment
```

**Critical:** never pipe an infinite empty-line source (`yes "" |`) — the
input loop spins against it. Closed stdin (`< /dev/null`) is the only safe
choice. Under `-y`, `create` fails fast rather than dropping into the
interactive step-by-step fallback.

**Multi-step `run`: pass `--commit`.** It commits each green step, keeping the
tree clean before the next one starts — without it, an earlier step's dirty
files can mask a later step's test-authoring gate and wrongly block
advancement. Only `run`, `detail`, `completeness-audit`,
and `manifest sweep`/archive accept it — don't tack it onto a command that doesn't
(see [DIRECTIVES.md](DIRECTIVES.md) for the full mechanics). `--commit` refuses a
dirty tree, so a step that fails its own tests is recovered by hand, not re-run —
see DIRECTIVES.md's "When a `run` step's own tests fail".

## Decision tree for common user asks

| User says | Run |
|---|---|
| "set up plan-tool in this repo" / the first plan in a repo with no `.plan-tool/project.json` | Offer project setup; it is optional and never blocks `create`. If accepted, ask for the intent, non-goals and decisions, read back the exact text, then run `plan-tool init` — see DIRECTIVES.md's "Setting up a repository" |
| "work on plan X" / "continue X" | `plan-tool status X`, then `plan-tool run X` |
| "show me what's in progress" | `plan-tool list` |
| "what's left on X?" | `plan-tool status X` |
| "review the code I just wrote for X" | `plan-tool run X --mode check` |
| "add tests / docs / security review for the current step" | `plan-tool run X --mode test\|document\|security` |
| "audit every done step in plan X" | `plan-tool verify-all --rollup X` |
| "did step N actually get implemented?" | `plan-tool run X --step N --mode check` — request report-only correctness and implementation-mismatch review. Judge the evidence against the step; a clean report alone does not prove delivery. |
| "make the code match the plan" | `plan-tool reconcile-code X --step N` |
| "make the plan match the code" | Before execution only: `plan-tool detail X --reconcile --step N`. After execution, preserve plan authority; judge a code shortfall or correct a false plan claim through a session-directed edit. |
| "make the plan match the code for every remaining step" | Before execution only: `plan-tool detail X --reconcile --all` (skips done steps). Do not use plan-mutating reconciliation on executed work. |
| "is plan X still current / refresh it against the code" | Before execution only: `plan-tool reconcile-plan X --refresh` (fingerprint-gated; no backend call on no drift). For executed work, use plan-canonical code review/reconciliation or `annotate` to seed the next iteration. |
| "reconcile printed `[REDIRECT]` — is it broken?" | Read the saved redirect and judge its root cause. Before execution, plan-side reconciliation may be appropriate. After execution, preserve the plan’s authority: correct a false plan claim through a session-directed edit or surface a scope decision; do not automatically invoke `detail --reconcile` or `reconcile-plan`. See DIRECTIVES.md’s reconciliation directionality rule. |
| "show me the prompt without running it" | add `--dry-run` |
| "this run feels slow / hung" | `plan-tool runs list --slug X`, then `plan-tool runs show X/<run_id>`; or `cat .plan-tool/runs/X/in-flight.json` live |
| "make the plan as complete as possible" | Commit a clean baseline before each stage. Ground and review a seed, then `plan-tool create <slug> --from-existing <seed> --iterate -y < /dev/null` → `plan-tool completeness-audit <slug> --iterate --commit -y < /dev/null` (bare) → `plan-tool detail <slug> --commit -y < /dev/null # requires a clean tree; commit the plan first` (one-shot) → `plan-tool completeness-audit <slug> --iterate --commit -y < /dev/null` (detail-grounded). Read each report and apply judged conceptual corrections through the session; commit corrections before re-auditing and continue under the canonical convergence rules. Preserve user review/continuation boundaries and stop before implementation. |
| "I have a big doc — make a plan from it" | `plan-tool create <slug> --from-existing <path>` (a distill first-pass reorganizes the seed; if it spans several independent efforts, create proposes a multi-plan split and writes a `<slug>-split-proposal.md` worksheet instead of a plan) |
| "I have a project-sized concept, not a single feature" | `plan-tool roadmap <slug> --from-existing <concept.md>` — see DIRECTIVES.md's Roadmap section for artifact layout, resume, and refusal semantics |
| "reopen a retained roadmap feedback item" | `plan-tool roadmap <slug> --reopen-ledger-feedback ITEM_ID` — see DIRECTIVES.md's Roadmap section |
| "author a plan and classify each step" | `plan-tool create <slug>` — the wizard prints each step's proposed `change_type` + rationale and prompts `(r)efactor / (f)eature / (n)on-code / (s)plit` per step |
| "split step N of plan X into smaller steps" / completeness flagged a BLOCKED 'needs a new step' | `plan-tool split X --step N --into "<first>" --into "<second>"` — renumbers the plan, authors the new halves, then re-runs the completeness audit |
| "merge steps N and M of plan X into one" / a plan is over-decomposed | `plan-tool merge X --steps N --steps M` — folds the set into one step, renumbers the plan, re-authors the merged detail, then re-runs the completeness audit (confirmed at the TTY; bypassed under `--yes` / non-TTY) |
| "a step keeps re-flagging and won't shrink / carve it out and defer it" | `plan-tool scope-out X --step N` — carves the over-packed step out of the plan into a `create --from-existing` forward-seed and narrows the plan (recommend-only by default; `--apply` + a TTY confirm to mutate; seed-first, no model call) |
| "run plan X on its own branch" / "bind X to branch B" | `plan-tool attach-branch X B`, then `plan-tool run X --switch-branch` for the unowned-branch nudge — enable branch-awareness first (see the note below) |
| "run two plans at once" / "work on plan B without disturbing plan A" | `plan-tool worktree add B`, then `cd` into the printed path and run there — an isolated worktree per plan (caveats in README.md's Worktrees section / RUNBOOK.md's parallel-worktrees workflow section, both in the plan-tool repo) |
| "run several steps of X in a row" | `plan-tool run X --all --commit` (or step-by-step, `--commit` each time) — keeps the tree clean between steps |
| "a `run` step failed its own tests / the test-authoring gate blocked a step whose tests exist" | Do not hand-fix and bare re-run or use `--skip-merge-check`. For a confirmed test defect, fix it, run the full suite and commit code/tests without the plan. Then `plan-tool run X --step N --accept --commit` runs the acceptance gates and advances only on success; continue remaining steps with `run --commit`. Never hand-edit the status. If the implementation itself is wrong or no test/gate can certify acceptance, follow DIRECTIVES.md’s “When a `run` step’s own tests fail.” |
| "the plan finished running / every step is green" | not done yet — drive `reconcile-code` to convergence, then `/code-review` to convergence; see DIRECTIVES.md's session-directed convergence loop |
| "completeness flagged a plan-correctness/plan-completeness gap" | Read the saved report, verify and judge the findings, edit the files directly, commit, and re-audit the changed snapshot; see DIRECTIVES.md's session-directed convergence loop |
| "fix the bare-audit findings" | triage each finding first: R roadmap conflict, B plan contract, P owner decision, D detail mechanism, I settled by code or spike, T tool artifact. Edit the plan body only for B, from the finding's plan-altitude restatement, not its `Fix` line; see DIRECTIVES.md's Gate 1 |
| "audit plan X" after hand edits | parse every edited plan's YAML frontmatter first (`: ` inside a plain scalar breaks it); an audit exit code 2 is a failed run, so read its log |

**Branch-awareness ships OFF.** Enable it per-repo in `.plan-tool/config.json` as `{"branch_awareness": {"enabled": true}}` (or set `PLAN_TOOL_BRANCH_AWARENESS=1`); with it off — every repo today — `run` and `create` behave exactly as before.

## Subcommands at a glance

The authoring pipeline is
`create → bare audit → detail → detail-grounded audit → (run \| jira)`,
with `verify-all` as an optional CI gate. Follow the shared
directives for judged corrections, user review and continuation.

| Group | Subcommands | Calls claude? |
|---|---|---|
| **Roadmap** (project-altitude, above the pipeline) | `roadmap <slug> --from-existing <concept.md>` [`--apply` [`-y`]] [`--view ...`] [`--compare`] — see DIRECTIVES.md | Yes (`--apply`, `--view`, `--compare`: no) |
| **Discovery** | `list`, `list --status` (cached annotate rollup), `status <name>`, `validate <name>` | No |
| **Project context** | `init --intent '…' [--non-goal '…'] [--decision '…']` — create the tracked, operator-confirmed `.plan-tool/project.json` profile before scope-bearing authoring and audit prompts. Revise it by editing the file and committing the change. | No |
| **Authoring** | `create <slug>`, `detail <name>`, `split <name> --step N --into "..." --into "..."` (split one step into named sub-steps, author them, re-audit), `merge <name> --steps N --steps M` (fold a contiguous set of steps into one, re-author it, re-audit), `scope-out <name> --step N` (carve an over-packed step out into a `create --from-existing` forward-seed and narrow the plan; recommend-only, `--apply` to mutate) | Yes |
| **Annotate** (forward seed) | `annotate <path-or-glob>...` — judge old plans against current code, emit `<stem>.annotated.md` (verbatim + per-section IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED/NEEDS-REVIEW plus grounding) and a carryover `<stem>.seed.md` for the next `create --from-existing`; batch runs end with a coverage/grounding summary table; read-only on sources except opt-in `--archive` (numbered on archive collisions). `--iterate` is rejected; iterate the follow-up `create`, not annotate. | Yes |
| **Audit · reconcile** (plan↔code) | `reconcile-plan <name>` (pre-execution only; edit a stale plan against current code), `reconcile-code <name>` (post-execution; plan is canonical, edits code), `detail <name> --reconcile` (pre-execution, per-step plan side), `reconcile-plan-walk <name>` (apply saved findings), `reconcile-plan <name> --refresh` (cheap fingerprint gate — reconcile only the drifted files, skip claude on no drift) | Yes (walk/refresh-no-drift: no) |
| **Audit · verify** (read-only) | `verify-all <name> --rollup` (verdict), `verify-all <name> --mode <m>` (sweep), `run <name> --mode <review>` | Yes |
| **Audit · completeness** (design) | `completeness-audit <name>` (read the saved report, judge and hand-edit conceptual corrections, commit, and re-audit) | Yes |
| **Execution** | `run <name>` (advances plan state on success) | Yes (one per step) |
| **Workspaces** | `worktree add <plan> [--clone]`, `worktree list`, `worktree remove <plan> [--force]`, `worktree prune` — an isolated worktree (or `--clone`) per plan for parallel runs; caveats (`worktree_base`, clone manual-cleanup, per-branch/`gc`, orphan branch) in README.md's Worktrees section / RUNBOOK.md's parallel-worktrees workflow section (in the plan-tool repo) | No |
| **Integration** | `jira <name>`, `jira config`, `jira --lint` (read-only artifact lint; no claude / no epic assignment) | jira yes (`--lint`: no) |
| **State** | `checkpoint {list\|show\|clear}`, `runs {list\|show\|diff\|clear}`, `register`, `deregister`, `sweep`, `withdraw <name> --reason "..."` (archive an *abandoned* plan — reason required, distinct from `sweep`'s completion path), `attach-branch <plan> <branch>`, `detach-branch <plan>` (ad-hoc branch binding; pure git-config writes; refuse unless branch-awareness is enabled) | No |
| **Setup** | `install-skill [--user\|--copy\|--root .claude\|.agents]` — install this bundled skill so an agent can drive plan-tool (opt-in; the CLI is standalone) | No |

The three audit verbs answer different questions: `validate` = schema only
(no claude); `completeness-audit` = deterministic authoring gaps (sections/detail/
lessons), then a sampled claude audit of whether the plan's own concepts are
correct + complete, grounded in the per-step detail bundle + code at HEAD
(`--audit-samples` / `--audit-dry-rounds`); `reconcile-plan` = paths/deps + claude
semantic review of the plan against the code. When both correctness and
completeness findings exist, correctness renders first.

`create` iterates by default. `detail` defaults to a one-shot write; do not
opt it into iteration unless the user asks. Pass `--iterate` explicitly to
`completeness-audit`. Use iteration flags only where the invocation accepts them:
Neither `detail --reconcile` nor `run --reconcile` can combine with
`--iterate`, and standalone
`reconcile-plan` and `reconcile-code` do not accept that flag. Completed loops can exit 0 with unresolved findings or an
exhausted budget. Read saved findings, stop reason and audit qualification;
for `completeness-audit` CI gating, use its supported `--fail-on-findings` flag.
A successful exit alone does not establish convergence. See DIRECTIVES.md and
the repository’s `docs/ITERATION.md` for command-specific behavior.

**Maintenance note:** when adding a subcommand, update these together:
- add or extend the owning command module's `register(subparsers) -> dict[str,
  Handler]` (the `sub.add_parser(...)` block plus the returned `{name: handler}`
  dispatch entries); for a brand-new module, append it to `COMMAND_MODULES` in
  `plan_tool/cli/app.py`;
- update the intent-grouped subcommand catalog in the **package docstring** at
  the top of `plan_tool/cli/__init__.py` (the byte-exact source of the `--help`
  description, pinned by `tests/cli/package_surface_help.golden.txt`);
- update this "Subcommands at a glance" table;
- add characterization tests under `tests/cli/` (see `TESTING.md`).

## Authoring conventions

When you author or execute plans with this tool (and when editing the tool
itself), apply these conventions — they're also baked into the
`create` / `detail` / `run` / `optimize` prompts:

- **Intuitive, self-descriptive names.** A reader should grasp a variable,
  function, type, or concept without a glossary — prefer `multi_plan_split`
  over `decomposition`, and directional names like `skip_below_bytes` over an
  ambiguous `skip_bytes`.
- **No dead historical references.** When you rename or remove behavior, update
  every reference and describe only the **current** state in code, comments,
  and docs. Don't leave "the old X", "formerly", or "used to" narration behind
  — git history holds the past.
- **Classify each step's `change_type`.** When authoring, decide **code vs
  non-code first** for every step, then confirm each code step's **refactor vs
  feature** call (the field and its values are defined in `PLAN_FORMAT.md` —
  name and link it, don't restate the enum). **Both code types share one test
  directive**: cover the behavior the step changes, green before it finishes.
  Do not reintroduce an ordering contract that tells `refactor` steps to pin
  characterization tests green *before* the change and keep them passing
  *unchanged* after — that was tried, measured (most refactors change the
  test-visible interface, so "unchanged" is usually unsatisfiable), and
  withdrawn 2026-07-30; see `CLAUDE.md`'s "Withdrawn" section in the plan-tool
  repo. The only checked claim is the test-authoring gate: a test file was
  really created or modified. **Non-code steps carry no test directive** —
  verify them by artifact-appropriate means (config validation, doc
  link/accuracy checks) instead.

## Going deeper

These live in the plan-tool repo (paths relative to its root):

- **[`DIRECTIVES.md`](DIRECTIVES.md)** — the shared reference for driving any
  plan-tool pipeline: the two audit gates, the session-directed convergence
  loop, `--iterate`/`--commit`, reconcile directionality, roadmap operation,
  and seed authoring. Installed as a sibling of this file by `install-skill`, so this link
  resolves once installed. In the source repo, it lives at
  `integrations/shared/DIRECTIVES.md` instead — a different directory.
- **`README.md`** — full subcommand reference, flag semantics, `--iterate`
  decision tree, run-log schema, per-subcommand reconcile, correctness /
  completeness gates, headless matrix, resume/checkpoint keying, install.
- **`RUNBOOK.md`** — operational walkthroughs ("how do I X?"): start a plan,
  drive to completion, converge with `--iterate`, review before running,
  export to JIRA, recover an interrupted run, investigate a slow run.
- **`SEED_FORMAT.md`** — authoring directives for the `docs/implementation-plans/plan-seeds/*.md`
  briefs fed to `create --from-existing`: density, single-effort focus,
  destinations-not-turn-by-turn, and the required scope-contract fence.
- **`PLAN_FORMAT.md`** — the frontmatter schema, field semantics, and the
  canonical step layout.
- **`ROADMAP_FORMAT.md`** — the on-disk schema for `roadmap`'s four artifacts,
  `01-domain.md` through `04-roadmap.md`: frontmatter rows, closed
  vocabularies, and the gates each must clear.
- **`plan_tool/cli/`** — the CLI package; `app.py` holds `main()` + dispatch,
  per-intent command modules expose `register()`, and `__init__.py` carries the
  package surface + subcommand catalog. Start at `__init__.py`.
- **`plan_tool/prompts/*.md`** — `string.Template` prompt bodies; edit these to
  change per-step behavior without touching Python.

## Not yet implemented / out of scope

- `plan-tool migrate` (legacy → frontmatter) is unimplemented; migrate by hand
  and add the path to the project's `.plan-tool/plans.json`. Mass migration,
  parallel step execution, and multi-step prompt aggregation are permanently
  out of scope — the subprocess-per-step model is sequential by design.
