# plan-tool runbook

Operational walkthroughs for common plan-tool tasks and the failure modes
you'll hit along the way. Conceptual stuff (schema, modes, architecture)
lives in [`README.md`](README.md),
[`DIRECTIVES.md`](integrations/shared/DIRECTIVES.md) (the driving rules — audit
gates, `--iterate`/`--commit`, the convergence loop, roadmap operation), and
[`PLAN_FORMAT.md`](PLAN_FORMAT.md) — start there if you're new to the tool.

This doc assumes `plan-tool` is installed as a global CLI (`uv tool install
--editable .` from a clone) and run from inside the project you're working on:

```bash
plan-tool <subcommand> ...
```

---

## Table of contents

- [Quick reference](#quick-reference)
- [Command families and ordering](#command-families-and-ordering)
- [Workflow: analyze heuristic outcomes with plan-tool telemetry](#workflow-analyze-heuristic-outcomes-with-plan-tool-telemetry)
- [Workflow: turn a concept brief into architecture artifacts (`roadmap`)](#workflow-turn-a-concept-brief-into-architecture-artifacts-roadmap)
- [Workflow: start a new plan](#workflow-start-a-new-plan)
- [Workflow: drive a plan to completion](#workflow-drive-a-plan-to-completion)
- [Workflow: lock in gates with suggest-gates](#workflow-lock-in-gates-with-suggest-gates)
- [Workflow: drive an authoring task to convergence (`--iterate`)](#workflow-drive-an-authoring-task-to-convergence---iterate)
- [Workflow: review concept decisions and ownership (`scope-review`)](#workflow-review-concept-decisions-and-ownership-scope-review)
- [Workflow: review before running](#workflow-review-before-running)
- [Workflow: export to JIRA for sprint planning](#workflow-export-to-jira-for-sprint-planning)
- [Workflow: author detail files for developer hand-off](#workflow-author-detail-files-for-developer-hand-off)
- [Workflow: annotate an existing plan to seed the next one](#workflow-annotate-an-existing-plan-to-seed-the-next-one)
- [Workflow: recover from an interrupted create/detail run](#workflow-recover-from-an-interrupted-createdetail-run)
- [Workflow: investigating a slow run](#workflow-investigating-a-slow-run)
- [Workflow: a seed that's too large or covers multiple plans](#workflow-a-seed-thats-too-large-or-covers-multiple-plans)
- [Workflow: per-subcommand reconcile](#workflow-per-subcommand-reconcile)
- [Workflow: completeness checks](#workflow-completeness-checks)
  - [Carve an over-packed step out of a plan (`plan-tool scope-out`)](#carve-an-over-packed-step-out-of-a-plan-plan-tool-scope-out)
  - [See a plan's split criteria (`plan-tool split-criteria`)](#see-a-plans-split-criteria-plan-tool-split-criteria)
- [Workflow: consolidate lessons files](#workflow-consolidate-lessons-files)
- [Workflow: run a plan on its own branch (branch-awareness)](#workflow-run-a-plan-on-its-own-branch-branch-awareness)
- [Workflow: run plans in parallel (worktrees)](#workflow-run-plans-in-parallel-worktrees)
- [Recovery: common failures](#recovery-common-failures)
- [Working in non-standard layouts](#working-in-non-standard-layouts)
- [Progress output during long claude calls](#progress-output-during-long-claude-calls)
- [Inspecting prompts before they run](#inspecting-prompts-before-they-run)
- [The prompt-budget advisory](#the-prompt-budget-advisory)
- [Mutating vs. read-only modes](#mutating-vs-read-only-modes)
- [Backends](#backends)
- [Backing up / undoing](#backing-up--undoing)

---

## Quick reference

The everyday commands, grouped by family in pipeline order. Niche flags
(`--no-iterate`, `--reuse-audit`, `--reuse`, `--dry-run`, gating, backends, …) live
in the per-workflow sections below and in `plan-tool <cmd> --help`; the
full intent map is in [Command families and ordering](#command-families-and-ordering).
The exhaustive per-subcommand flag reference (every flag, default, and
subaction) is generated under [`docs/cli/`](docs/cli/README.md).

**Roadmap (project-altitude, before `create`)**

| Run | …to |
| --- | --- |
| `plan-tool roadmap <slug> --from-existing <concept.md>` | Turn a project-sized concept brief into one immutable version of the gated `01-domain`, `02-constraints`, `03-components`, and `04-roadmap` artifacts, its ledger, and the accepted head, plus draft seeds under `docs/implementation-plans/roadmaps/<slug>/`; first run only, and a failed run resumes from `.plan-tool/runs/<slug>/roadmap-stage-resume/` |
| `plan-tool roadmap <slug> --submit-feedback ITEM_ID --feedback-target ARTIFACT:KIND[:ROW_ID] --feedback-request TEXT` | Record a reviewer request in the ledger, then run `--propose-candidate` to build an inert candidate |
| `plan-tool roadmap <slug> --compare` | Compare the accepted head with the active candidate (read-only; pass `--comparison-target` when none is active) |
| `plan-tool roadmap <slug> --decide-candidate CANDIDATE_VERSION_ID --candidate-decision approve\|edit\|reject` | Decide the active structural candidate; approve is two invocations and the second carries `--confirm-stack-digest` |
| `plan-tool roadmap <slug> --reopen-ledger-feedback ITEM_ID` | Reopen one retained reviewer ledger item |
| `plan-tool roadmap <slug> --apply` / `plan-tool roadmap <slug> --apply -y` | Promote draft seeds from the accepted `04-roadmap` artifact into `plan-seeds/` without invoking stages (preview by default; `-y` is the second opt-in) |
| `plan-tool roadmap <slug> --refresh-seeds` | Reprocess invalidated derived seeds against current code, restore archived ones, and write a diff report without rewriting roadmap artifacts |

A stage run is refused once the roadmap has an accepted head; the roadmap then
changes through the ledger routes above. A failed first run resumes only for the
same brief content. See
[Recover from a first run that didn't finish](#recover-from-a-first-run-that-didnt-finish).

**Discovery & inspection**

| Run | …to |
| --- | --- |
| `plan-tool list` | See registered plans |
| `plan-tool list --status` | Roll up cached annotate reports for active plans |
| `plan-tool status <name>` | Inspect one plan's steps + status |
| `plan-tool validate <name>` | Schema-check frontmatter |
| `plan-tool split-criteria [<name>]` | See the tool's split criteria (no arg) or why one plan is shaped as it is |
| `plan-tool telemetry` | Show the human-readable cross-plan heuristic outcome report |
| `plan-tool telemetry --json` | Emit the same analysis in machine-readable form |

**Project context**

| Run | …to |
| --- | --- |
| `plan-tool init --intent "…" [--non-goal "…"] [--decision "…"]` | Create the tracked, operator-confirmed project profile consumed by authoring and audit prompts |
| Edit `.plan-tool/project.json`, then commit | Revise the confirmed project intent, non-goals, or decisions |

**Authoring**

| Run | …to |
| --- | --- |
| `plan-tool create <slug>` | Start a new plan |
| `plan-tool create <slug> --from-existing <path>` | Start from notes / an old doc |
| `plan-tool detail <name>` | Author per-step detail files |
| `plan-tool detail <name> --all --commit` | Author every step's detail file in one pass, committing each |
| `plan-tool split <name> --step N --into "…" --into "…"` | Break step N into named sub-steps, author them, then re-audit (resolves a completeness BLOCKED "needs a new step") |
| `plan-tool merge <name> --steps ID --steps ID` | Fold a contiguous, dependency-connected set of steps into one (the structural inverse of `split`); re-author the combined detail file, renumber survivors to `1..N`, then re-audit |

**Annotate (forward seed)**

| Run | …to |
| --- | --- |
| `plan-tool annotate <path>` | Judge an old plan against current code; emit `<name>.annotated.md` + a `<name>.seed.md` for the next `create` |
| `plan-tool annotate <path-or-glob>...` | Batch-annotate multiple sources and print a coverage / grounding summary table |
| `plan-tool annotate <path> --archive` | …and move the original (and its `plan-details/<slug>/` bundle for an `N-slug.md` plan) into `archive/` with a notice pointing at the report |

**Plan audit**

| Run | …to |
| --- | --- |
| `plan-tool completeness-audit <name>` | Audit the plan's design + coverage (the primary authoring audit) |
| `plan-tool completeness-audit <name> --iterate --commit` | Converge the audit loop (gates → apply-finding → re-audit) and stage the applied edits |
| `plan-tool completeness-apply <name>` | Apply the conceptual gaps from the last audit |
| `plan-tool completeness-apply <name> --commit` | Apply the conceptual gaps from the last audit and stage the result |
| `plan-tool data-contract-apply <name>` | Walk saved `DATA_CONTRACT.md` drift findings from the last audit |
| `plan-tool reconcile-plan <name>` | Re-audit an older plan whose code may have drifted (also supplements the completeness audit) |
| `plan-tool detail <name> --reconcile` | Fix a step's detail to match the code |

**Code audit**

| Run | …to |
| --- | --- |
| `plan-tool verify-all --rollup <name>` | Pass/warn/fail verdict over done steps before merge |
| `plan-tool verify-all <name> --mode <m>` | Sweep a read-only review mode across done steps |
| `plan-tool reconcile-code <name>` | Fix the code to match the plan |

**Execution**

| Run | …to |
| --- | --- |
| `plan-tool run` | Pick a plan with open steps interactively (no name) |
| `plan-tool run <name>` | Run the next pending step |
| `plan-tool run <name> --step N` | Run one specific step |
| `plan-tool run <name> --all --commit` | Run every step, committing each green step |

**Branch-awareness (opt-in)**

**Branch-awareness ships OFF.** Enable it per-repo in `.plan-tool/config.json`
as `{"branch_awareness": {"enabled": true}}` (or set
`PLAN_TOOL_BRANCH_AWARENESS=1`); with it off — every repo today — `run` and
`create` behave exactly as before. The commands below refuse with a non-zero
exit until it's enabled.

| Run | …to |
| --- | --- |
| `plan-tool attach-branch <name> <branch>` | Bind a plan to an ad-hoc branch (untracked local git config) |
| `plan-tool detach-branch <name>` | Clear that ad-hoc override (quiet no-op when nothing was bound) |
| `plan-tool run <name> --switch-branch` | On an unowned branch, create-if-missing + switch to the plan's expected branch on a clean tree |

**Workspaces (parallel plans)**

| Run | …to |
| --- | --- |
| `plan-tool worktree add <name>` | Provision (or reuse) the plan's isolated worktree on its branch; prints a `cd` hint |
| `plan-tool worktree add <name> --clone` | Provision a full standalone clone instead of a worktree (total `.git` isolation) |
| `plan-tool worktree list` | Report kind / branch / path / dirty state for every plan's workspace |
| `plan-tool worktree remove <name> [--force]` | Delete one plan's worktree (a dirty one needs `--force`; a clone is surfaced, not deleted) |
| `plan-tool worktree prune` | Sweep dead (deregistered / path-gone) worktrees; dirty ones are surfaced, not deleted |

**Integration**

| Run | …to |
| --- | --- |
| `plan-tool jira <name>` | Export copy-paste JIRA stories |
| `plan-tool jira <name> --lint` | Lint the conventional jira-stories artifact without invoking Claude or assigning an epic |
| `plan-tool jira --lint --input <path>` | Lint an existing markdown/json export directly |

**State management**

| Run | …to |
| --- | --- |
| `plan-tool sweep` | Archive finished plans / report stray ones |
| `plan-tool sweep --commit` | Archive finished plans, then stage the manifest + moves |
| `plan-tool withdraw <name> --reason "..."` | Archive a plan being *abandoned* (premise disproved, carved wrong) — distinct from `sweep`'s completion path; `--reason` is required |
| `plan-tool checkpoint list` · `plan-tool runs list` | Recover or profile an interrupted run |

**Placeholders used across this runbook:**

- `<name>` — flexible identifier for an **existing** registered plan.
  Resolves by slug (`my-feature`), by filename stem (`1-my-feature`),
  or with the `.md` suffix (`my-feature.md`). Priority prefixes are
  tried automatically. Used by every read/audit/run subcommand.
- `<slug>` — canonical lowercase-dashes plan slug (no priority
  prefix, no `.md`). Used by `create` (the new plan doesn't exist
  yet, so only a slug applies) and by `checkpoint clear` /
  `runs clear`, whose on-disk directories are keyed by slug.
- `<slug>/<checkpoint>` — checkpoint identifier. `<slug>` is the plan
  slug; `<checkpoint>` is the per-plan checkpoint name shown in the
  `name` column of `plan-tool checkpoint list` (e.g.
  `detail-step-02`, `create-initial-steps`).
- `<slug>/<run_id>` — run identifier. `<slug>` is the plan slug;
  `<run_id>` is the timestamp-derived id shown by
  `plan-tool runs list` (e.g. `2026-05-14T12-34-56-9f3a1c`).
- `<path>` — filesystem path (absolute or repo-relative). Used by
  `register`, `create --from-existing`, and `annotate` (the positional
  is a path, not a registered plan slug).

---

## What's in `.plan-tool/` (commit vs. delete)

Everything plan-tool writes for this repo lives under `.plan-tool/`. When
you're cleaning up or wondering whether a file is safe to `rm`, use this split:

**Committed — durable, shared; don't delete:**

- `plans.json` — the plan manifest. Deleting it loses plan discovery.
- `lessons/` — accumulated project lessons (`project.md` + citations).
- `bench/runs/<pinned>/` — pinned benchmark fixtures.

**Git-ignored — per-run / per-machine / debug exhaust; safe to delete anytime:**

- `runs/`, `checkpoints/` — run transcripts and resumable mid-run state.
  Clear with `plan-tool runs clear <slug>` / `plan-tool checkpoint clear <slug>`,
  or just `rm -rf` them — a fresh run re-creates what it needs.
- `reviews/`, `parse-failures/`, `crashes/`, `scenarios/`, `harness/` — review
  outputs and debugging artifacts.
- `.plan-tool/telemetry/decisions.jsonl` and its lock sidecar
  `decisions.jsonl.lock` — local input for heuristic outcome analysis. Deleting
  either is safe; deleting the JSONL removes local telemetry history.
- `lessons-warnings.jsonl`, `run-prefs.json` — runtime logs and local picker prefs.
- ad-hoc `bench/runs/` output (anything but the pinned fixture).

Rule of thumb: commit what's durable and shared (manifest, lessons, pinned
fixtures); ignore — and freely delete — what's per-run, per-machine, or debug exhaust.

---

## Command families and ordering

Subcommands group by **intent** — the same grouping `plan-tool --help`
renders (the catalog lives on the `plan_tool.cli` package docstring; keep
this table in sync with it). The families line up along the pipeline
`create → detail → audit ──┬── run` / `└── jira → verify`: you author a
plan, audit it against the codebase, then either drive it to completion
(`run`) or hand it off (`jira`).

| # | Family | What it does | Touches claude? | Commands |
| --- | --- | --- | --- | --- |
| 1 | **Discovery & inspection** | Read plan state | No | `list`, `status`, `validate` |
| 2 | **Authoring** | Produce / restructure plan files on disk | Yes | `create`, `detail` |
| 3 | **Plan audit** | Judge the plan's design/coverage, or fix the PLAN to match code; **never edits code, never advances step status** | Yes | `completeness-audit`, `completeness-apply`, `data-contract-apply`, `reconcile-plan`, `detail --reconcile`, `reconcile-plan-walk` |
| 4 | **Code audit** | Judge finished (`done`) steps, or fix the CODE to match the plan; **never edits the plan, never advances step status** | Yes | `verify-all`, `run --mode`, `reconcile-code` |
| 5 | **Execution** | Drive code edits by running plan steps | Yes | `run`, `run --all` |
| 6 | **Integration** | Emit artifacts for external systems | Yes | `jira`, `jira config` |
| 7 | **State management** | Inspect / clear plan-tool's own caches + manifest | No | `checkpoint`, `runs`, `lessons`, `register`, `deregister`, `sweep`, `withdraw` |

Audit is **two** families, split by **what's under audit**. Pick the
target first — the plan (family 3) or the code (family 4) — then the
posture (read-only judgement vs. a mutating fix) follows. Neither family
advances step status.

**Plan audit (3)** — is the plan itself correct and complete? Any edits
land on the plan / detail files; the codebase is read-only here.

| Command | Posture | Question / effect |
| --- | --- | --- |
| `completeness-audit` | Read-only | **The primary authoring audit** — are the plan's concepts correct + complete? Sampled audit grounded in the detail bundle. Bare vs detail gates use different conceptual bars (correctness-focused at Gate 1). |
| `completeness-apply` | Mutating | Apply the conceptual-completeness gaps from the last audit. |
| `data-contract-apply` | Mutating | Apply saved `DATA_CONTRACT.md` documentation drift payloads from the last completeness audit. |
| `reconcile-plan` | Mutating | Plan-wide drift: edit the PLAN to match the code (aliases `reconcile`, `review`). Reach for it mainly on **older plans the code has drifted under**, or as a code-fit supplement to `completeness-audit`. |
| `detail --reconcile` | Mutating | Per-step: edit a step's detail to match the code (`--all` sweeps not-yet-done steps). |
| `reconcile-plan-walk` | Mutating | Apply a saved reconcile's findings interactively, no claude call. |

**Code audit (4)** — does the code hold up against the plan / intent? Any
edits land on the code; the plan is read-only here.

| Command | Posture | Question / effect |
| --- | --- | --- |
| `verify-all --rollup` | Read-only | Pass/warn/fail verdict over every `done` step (add `--deep` for per-criterion). |
| `verify-all --mode <m>` | Read-only | Sweep a review mode (check/optimize/document/test/security/lint) across `done` steps. |
| `run --mode <review>` | Read-only | Run one of those review modes against a single step. |
| `reconcile-code` | Mutating | Edit the CODE to match the plan — lands edits inline (legacy `run --reconcile`). |

**`annotate` sits outside the numbered families** — it's a forward-seed
bridge *into* the pipeline, not a stage on it (so there's no family 8;
the numbered families mirror the `create → … → run/jira` spine, and
annotate isn't on it). It judges an existing plan against the current
code and emits a `create --from-existing` seed for the *next* iteration,
read-only on both the plan and the code except the opt-in `--archive`. A
reader who knows `reconcile-plan` should note the contrast:
`reconcile-plan` mutates a *live* plan in place to match code that
drifted under it (code-canonical upkeep); `annotate` never touches its
source — it emits a `<stem>.seed.md` to seed the next `create`.
Live-plan progress upkeep → `reconcile-plan`; starting the next plan from
"what we built vs. what we wrote" → `annotate`. See
[Workflow: annotate an existing plan to seed the next one](#workflow-annotate-an-existing-plan-to-seed-the-next-one).

**`roadmap` also sits outside the numbered families**, for the mirror-image
reason: where `annotate` bridges *backward* from an old plan into the next
`create`, `roadmap` bridges *forward* from a project-sized concept brief toward
a `create` seed — one rung above authoring (2), before any plan exists. It
publishes one version holding the `01-domain`, `02-constraints`,
`03-components`, and `04-roadmap` artifacts plus draft seeds under
`docs/implementation-plans/roadmaps/<slug>/`, and touches no existing plan, no
detail bundle, and no manifest entry. See
[Workflow: turn a concept brief into architecture artifacts (`roadmap`)](#workflow-turn-a-concept-brief-into-architecture-artifacts-roadmap).

Reconcile straddles **both** families (3 and 4) because it's the seam
where the two meet: the verb you pick declares the direction of truth.
`reconcile-plan`
/ `detail --reconcile` treat the code as truth and fix the plan;
`reconcile-code` treats the plan as truth and fixes the code. If a
`reconcile-code` run finds the real fault is in the plan, it emits a
`[REDIRECT]` to `detail --reconcile` rather than editing code — switch
sides, don't retry (see [per-subcommand reconcile](#workflow-per-subcommand-reconcile)).

**Logical ordering.** Run the families roughly top-to-bottom: inspect
(1) to see where a plan stands, author (2) to write or extend it, audit
the plan (3) before doing anything destructive, execute (5), then audit
the code (4) and integrate (6). State management (7) is the housekeeping
layer — reach for it to recover an interrupted run, profile a slow one,
or archive a finished plan, not as a pipeline step. Note the two audit
families bracket execution: plan audit (3) runs *before* you `run`, code
audit (4) judges the `done` steps *after*. The two terminal branches
diverge after execution: `run` drives the plan to `N/N done`; `jira`
hands it off as stories, and `verify-all` judges the done steps before
merge.

Two registered commands sit outside the pipeline families:
[`suggest-gates`](#workflow-lock-in-gates-with-suggest-gates) (propose
`gate:` commands for a plan's remaining steps — an authoring helper;
grounds on already-built steps by default, or pass `--all-steps` to
propose speculative gates on a plan with nothing built yet) and `bench`
(benchmark the backends across the corpus — tool-dev tooling). Both are
real subcommands; they're just auxiliary to the author → audit →
run/jira flow.

---

## Workflow: analyze heuristic outcomes with plan-tool telemetry

Run the repository-wide report to group recorded decisions by
`(kind, decision)`:

```bash
plan-tool telemetry
```

Each group separates four outcome counts: `acted-on` means the decision led to
the corresponding change, `no-op` means no change was needed, `reverted` means
a later state reversed the effect, and `still-open` means the decision has not
reached a completed outcome. Read `resolved` and `unresolved` separately:
unresolved events lack enough correlation evidence and are not evidence that a
heuristic performed poorly.

For scripts or CI-side inspection, request one JSON object:

```bash
plan-tool telemetry --json
```

See [`docs/cli/telemetry.md`](docs/cli/telemetry.md) for the complete flag
contract. Recommendations are advisory tuning evidence only;
`plan_tool/telemetry_analysis.py:analyze_decisions` never changes thresholds,
plans, or configuration. If the local log is absent or empty, the text command
prints `No telemetry recorded yet.` and still exits successfully.

Producer hardening keeps the evidence trustworthy without changing this
workflow: fingerprint-heavy events store a compact code-state identity, create
child outcomes join to one assessment occurrence, failed primary and follow-up
applies remain visible, and parallel or interactive apply records only the
canonical landed result. The command makes no backend call, writes no run log,
and mutates neither the plan nor `.plan-tool/telemetry/decisions.jsonl`.

---

## Workflow: turn a concept brief into architecture artifacts (`roadmap`)

Reach for `roadmap` when what you have is **project-sized** — a concept brief,
not a feature — and you can't yet name the domain or say which quality
attributes it trades on. It sits one rung above `create`: it produces the
architecture output a `create` seed should be grounded in, and never a plan.

```bash
plan-tool roadmap my-project --from-existing docs/concepts/my-project.md
```

`--from-existing` belongs to the **first run** only. The run publishes one
immutable roadmap version (four artifacts), its ledger-native feedback ledger,
and the accepted head (written last), plus draft seeds under
`docs/implementation-plans/roadmaps/my-project/`. A roadmap folder holds a
closed set of files: the feedback ledger, `seed-state.json`, `INDEX.md`, the
draft-seed directory, `.plan-tool/evidence/`, and the version store
`.roadmap-versions/`. `INDEX.md` is a generated, human-facing listing of the
stored versions and their statuses; no command reads it.

**Stage-run status.** The first stage run writes bounded confirmed lifecycle
lines to **stderr** after a stage start, a retry or stop, a write, and the
returned result. They report the last confirmed transition only: silence is not
a heartbeat or a backend-liveness signal. Roadmap summaries and result payloads
on stdout remain unchanged, so do not parse lifecycle text. Views, seed
operations (`--apply`, `--refresh-seeds`, and `--materialize`), candidate and
ledger operations, and every other non-stage route do not emit these lines.

The published version holds four artifacts:

| Artifact | What it holds |
| --- | --- |
| `01-domain` | Entities, business rules, and workflows. Every rule and workflow names the entity ids it touches, so the domain is a connected graph rather than three lists. |
| `02-constraints` | Every quality attribute with exactly one disposition — `prioritized`, `traded-away`, or `not-load-bearing` — plus the constraints that discharge them, each anchored to an id `01-domain` defines. |
| `03-components` | Logical components, system and component patterns, and discharge claims tying prioritized constraints to patterns; traceability gates in `ROADMAP_FORMAT.md` enforce entity-id coverage and constraint discharge. |
| `04-roadmap` | Ordered plan list with component→plan mapping (merge / split / `cross-cutting` dispositions), inter-plan assumptions, and `draft_seed_path` pointers to slug-relative draft seeds. |

All carry YAML frontmatter (the row inventory the gates judge) over a prose
body written for humans. The schema is
[`ROADMAP_FORMAT.md`](ROADMAP_FORMAT.md). Read a roadmap with
`plan-tool roadmap my-project --view summary` (or `walk`, `ledger`, `index`,
`seeds`, `html`).

**Claude runs only inside a stage; the checks between stages are
deterministic.** A gate that fails doesn't fail the run — it retries the same
stage with its violations quoted back into the prompt, and only a stage that
spends that budget halts the arc — that's exit **1**, whether the attempts went
to a failing backend, an unparseable reply, a reply that authored `feedback` or
`removals` rows you never wrote, or gate violations. The other non-zero exit
is **2**, a pre-flight failure that stops the run before any stage is invoked:
an unreadable brief, an existing accepted head, leftover pre-head state, or a
changed brief against held stages (see
[Recover from a first run that didn't finish](#recover-from-a-first-run-that-didnt-finish)).
A run that finishes exits 0 no matter what the artifacts say.

### Reviewing what it guessed

`roadmap` is **non-interactive by construction** — no confirm, no prompt, no
`-y` to pass. At an option point a stage guesses, records the guess as a
decision row naming what it rejected and why, and marks a genuinely load-bearing
tradeoff `pending`. Those `pending` rows are the review channel, not defects:
no gate reads a decision's status, so they never block, and a completed run
reports how many are outstanding.

Settle a `pending` decision with `plan-tool roadmap <slug> --settle-decision
<artifact>:<decision-id> --settlement-evidence <artifact>:<feedback-id>
--confirm-decision-settlement`, citing a named, live feedback row that
approves it. It invokes no backend and publishes a committed receipt before the
settled version. Never edit a decision's `status` by hand: the accepted version
is immutable. Citable feedback is an open, eligible ledger item, so new
feedback stays citable. See [`docs/how-to/roadmap.md`](docs/how-to/roadmap.md)
§ 5 for the full contract.

That scoping is load-bearing, because the two review channels are not the same
thing and only one of them is a request the model must act on. A **pending
decision** is the model's own unsettled guess, and settling it is your own
confirmed action — the whole resolution. A **ledger feedback item** is *your
instruction*, and it gets a response only from a candidate built from it. See
[Redirecting a proposal with feedback](#redirecting-a-proposal-with-feedback).

### Redirecting a proposal with feedback

A roadmap with an accepted head changes through feedback and review, never
through a stage run. Record the request in the ledger, build an inert
candidate, compare it, and decide it:

```bash
plan-tool roadmap my-project --submit-feedback rename-order \
  --feedback-target domain:row:order --feedback-request "Rename Order to Purchase."
plan-tool roadmap my-project --propose-candidate
plan-tool roadmap my-project --compare
plan-tool roadmap my-project --decide-candidate CANDIDATE_VERSION_ID --candidate-decision approve
plan-tool roadmap my-project --decide-candidate CANDIDATE_VERSION_ID --candidate-decision approve --confirm-stack-digest DIGEST
```

`--propose-candidate` takes no selector: validated typed operations create a
bounded or structural inert candidate, and you never choose the route. Approve
is two invocations — the first prints the whole unpromoted stack and its digest
and writes nothing; the second supplies `--confirm-stack-digest` to seal and
promote it. `--compare` with no companion flag shows the accepted head against
the active candidate and writes nothing. Edit, reject, discard, failed
validation, interruption, and staleness leave the accepted version unchanged.
The ledger schema is in
[`ROADMAP_FEEDBACK_FORMAT.md`](ROADMAP_FEEDBACK_FORMAT.md).

A request bears on one design row or on a whole artifact, per its
`--feedback-target ARTIFACT:KIND[:ROW_ID]`. Change a retained ledger item with
the ledger routes:

| To… | Run |
| --- | --- |
| **Edit** its target or request | `--edit-feedback ITEM_ID` with `--feedback-target` and/or `--feedback-request` |
| **Retarget** it | `--retarget-feedback ITEM_ID --feedback-target ARTIFACT:KIND[:ROW_ID]` |
| **Defer** it | `--defer-feedback ITEM_ID` |
| **Close** it | `--close-feedback ITEM_ID` |
| **Reopen** it | `--reopen-ledger-feedback ITEM_ID` |

The tool proposes; it never decides one of these for you. Whether a candidate
answered your request is your call, permanently.

**When a candidate's review asks you a question**, read the stored question with
`--review-candidate INITIAL_CANDIDATE_VERSION_ID` and record the answer with
`--answer-question QUESTION_ID --answer TEXT`.

### Recover from a first run that didn't finish

A first run holds each gate-clean stage in memory and in the resume directory
`.plan-tool/runs/<slug>/roadmap-stage-resume/` (`stage-<N>.md` plus
`brief.digest`). Only a fully passing run publishes the version, ledger, and
accepted head and then deletes that directory. A failed run leaves only the
directory. Re-run the same command with the same brief: it resumes from the
first stage that is missing or fails its re-gate, and regenerates a damaged held
stage with a warning rather than refusing. The directory is not an input to
edit.

| Refusal | Remedy |
| --- | --- |
| `the brief changed since the held stages in <dir> were written. Restore the original brief, delete <dir> by hand, or start a successor slug.` | Restore the original brief, or delete exactly the named `roadmap-stage-resume/` directory (never the whole run-log directory, which also holds run logs), or start a successor slug. |
| `roadmap <slug> already has an accepted head (...)` on a stage run | Use the ledger routes above; a roadmap with a head is changed through feedback and review. |
| `roadmap <slug>: an interrupted publication left its journal at <path>; recover it before publishing` from a ledger, candidate, promote, or settle route | A crash during a publication left its journal. Run `plan-tool roadmap <slug> --from-existing <brief>`: it recovers a first-run journal (rolling a head-less one back, or recognizing a completed one) and then refuses with `already has an accepted head`, which is the expected result. Retry the original command. A journal of another kind beside a head is refused by recovery and is removed by hand. |
| A stage run on a folder with no head that holds pre-head state (top-level `0N-*.md`, `feedback-ledger.yaml`, `seed-state.json`, a populated `.roadmap-versions/`, or draft-seed directories) | Move or delete the listed paths and run again, or start a successor slug. Deleting `feedback-ledger.yaml` discards its feedback rows. |
| `roadmap '<slug>' has no published version` from a view, `--compare`, a seed route, or `create --from-existing` on a roadmap seed | The folder has no accepted head. Convert it by hand per [`docs/how-to/roadmap.md`](docs/how-to/roadmap.md) § 1: delete the top-level files and regenerate under the same slug, or start a successor slug from the brief. |

A folder that already has an accepted head and still carries
leftover top-level files (`0N-*.md`, `source.json`, `.roadmap-baselines/`, `.roadmap-rollbacks/`):
delete the leftovers; no command reads them.

The resume directory is unrelated to `plan-tool checkpoint list`/`clear`'s
create/detail authoring cache — see
[Workflow: recover from an interrupted create/detail run](#workflow-recover-from-an-interrupted-createdetail-run)
for that one instead.

#### What the run records

The run log records each accepted artifact write (path, digest, replacement
status, and stage-4 draft-seed count) and a typed preflight failure before any
stage call; references and digests are recorded, never brief text.
`roadmap --apply` opens its own run boundary and ends with aggregate
target/promotion/collision counts, even though it invokes no backend.

### Where the arc stops today

A full run publishes the four artifacts as one version and writes draft seeds
under the slug directory. The default hand-off is **automated**: the CLI prints
runnable `create --from-existing` lines against each draft path. Optional
`plan-tool roadmap <slug> --apply` (+ confirm or `--apply -y`) copies accepted
drafts into `plan-seeds/`; you can also run `create` directly against
slug-relative draft paths without promoting. See
[`docs/how-to/roadmap.md`](docs/how-to/roadmap.md) for the full operator
narrative and a manual fallback when stage 4 is skipped or rejected.
Arc position **05** (framework lenses) remains unauthored (BACKLOG #208).

### Promoting draft seeds (`--apply`)

Apply-only mode reads the accepted version's `04-roadmap` artifact — no brief,
no Claude, no stage run. Preview by default; `-y` is a second opt-in that
bypasses the TTY confirm. Collisions with existing `plan-seeds/` paths refuse by
default. Copies do not remove slug-relative drafts. Stage runs stay
non-interactive and do not accept `-y`.

Roadmap artifacts are **not plans** — nothing nests them in the manifest, and
`list` / `status` / `run` won't resolve one. The full flag reference is the
generated [`docs/cli/roadmap.md`](docs/cli/roadmap.md).

---

## Workflow: start a new plan

Prepare a reviewed bundle before requesting execution:

> Inspect this repository and draft a grounded seed for [change] with a scope
> fence and verified references. Link it, summarize changes and unresolved
> decisions, and ask me for corrections or continuation before creating a plan.
> Use the plan-tool skill for the reviewed seed: create and bare-audit the plan,
> then link the plan and report and summarize changes before asking to author
> details. After approval, author details and run the grounded audit; link both,
> summarize changes and verification, and ask for review. Wait at each boundary
> unless explicit prior delegation covers it. Stop before execution or export.

See the [planning demo](docs/demos/planning-demo.md) and
[authored samples](docs/demos/dark-mode-example.md), or the
[roadmap demo](docs/demos/roadmap-demo.md) for project-sized concepts. The examples
are preparation guidance, not proof of live audit convergence. Direct operator
routes follow; use [both audit gates](docs/how-to/pipeline/audit.md) before
separately requested execution or local export.

### From scratch

```bash
plan-tool create my-feature
```

The wizard prompts for: title, priority, optional lessons-log
path, then at least one step (title, complexity, files, depends_on).
Output is written to `docs/implementation-plans/<N>-my-feature.md` by
default and registered in `.plan-tool/plans.json` automatically.

For each step it also asks for the step's `change_type`, prompting
`(r)efactor / (f)eature / (n)on-code / Enter` (Enter leaves it unset).
This manual-entry path has no claude proposal to decompose, so the
`(s)plit` key the `--from` / `--from-existing` wizard offers (gated on
an invoker being present) is absent here — only `(r)/(f)/(n)/Enter` are
shown. The classification seeds a per-step strategy block in the plan
body's `## Testing` section; see
[`PLAN_FORMAT.md`](PLAN_FORMAT.md#field-semantics) for the field.

**Filename prefix.** `<N>` is the priority bucket — `1` for high, `2`
for medium, `3` for low. Multiple plans with the same priority share a
prefix and are disambiguated by their slugs (e.g. `1-auth-rewrite.md`
and `1-mentor-chat.md` are both high-priority).

**Body skeleton.** The wizard seeds a structured H2 outline with
`_(TODO)_` placeholders for Overview / Problem statement / Architecture
/ Steps / Out of scope / Risks / Testing / Acceptance criteria /
Deferred. Replace each placeholder with the section content; the
machine-readable step list lives in the frontmatter, so the `Steps`
section is just a pointer.

To skip the interactive step-list and let claude propose steps from a
description:

```bash
plan-tool create my-feature --from "Refactor the auth middleware to use JWTs"
```

You still answer metadata prompts; claude only proposes the steps. If
claude returns junk, the wizard falls back to interactive step entry —
unless `-y` / `--yes` is set, in which case the wizard fails fast with
a `CreateError` (no interactive fallback under `--yes`; see
[Running headlessly](README.md#running-headlessly) in the README for
the full headless invocation pattern).

After claude proposes the steps, the wizard runs a change-type review
loop over them, offering `(r)efactor / (f)eature / (n)on-code` plus —
because there is a claude proposal to decompose — the invoker-gated
`(s)plit` action. When an invoker is present and a step looks splittable
(a mixed refactor+feature title, a two-clause conjunction, or an
unrelated file span), the prompt prints a deterministic split hint from
the granularity advisor next to the proposal — the existing `(s)plit`
choice, made informed, with no extra Claude spend. Merge advice never
appears here; it surfaces only in the whole-plan completeness audit
(see [Workflow: completeness checks](#workflow-completeness-checks)).

`create` does not propose `gate:` commands. For gates on a freshly
written plan (nothing built yet), use
[`suggest-gates --all-steps`](#workflow-lock-in-gates-with-suggest-gates);
for the post-build path — locking in real artifacts after some steps
are `done` — see that workflow section.

### From an existing notes file or older plan

```bash
plan-tool create my-feature --from-existing docs/old-notes.md
```

Reads the file, feeds it to claude as the description, then runs the
normal wizard. After the new plan is written, the source file is moved
to `<source-parent>/archive/<stem>.replaced.md` with a header pointing
at the new plan. If the source has a sibling `plan-details/<slug>/`
directory (typical for legacy plans), that whole tree is archived
alongside.

`create --from-existing` handles arbitrary seed structures — prose
drafts, enumerated checklists, partially-canonical plans, exports
from other tooling. Three Claude round-trips conceptualize the seed:
step decomposition, external references, and canonical body-section
synthesis. Pass the seed straight to `create --from-existing` —
no preprocessing step is needed. Sources already in the strict
canonical step layout (`## Steps` + `### N. Title` + `Files:`
bullets — see [`PLAN_FORMAT.md`](PLAN_FORMAT.md#canonical-step-layout-input-shape-for-create---from-existing))
have their steps extracted deterministically, skipping the
step-decomposition Claude round-trip.

### Seed conceptualization (the three Claude round-trips)

**The pipeline.** Three round-trips fire in order against the seed:

- `create-initial-steps` — proposes the step graph.
- `create-references` — proposes external doc / API links.
- `create-body-sections` — synthesizes the canonical body sections
  (Overview / Problem statement / Architecture / Out of scope / Risks
  / Testing / Acceptance criteria / Deferred) from the full seed
  prose.

**Renderer precedence.** Synthesized non-null → H2-extracted (matches
a seed H2 by canonical name) → `_(TODO)_` placeholder.

**Canonical-skip optimization.** When every canonical body H2 is
present in the seed with non-empty content, the synthesis round-trip
is skipped — H2-extraction already covers it. `plan-tool runs show
<slug>` records the skip as
`phase_outcome=skipped, skip_reason=canonical_seed`.

**Empty-section semantics.** Sections without seed-derivable content
render `_(TODO)_`; synthesis returns `null` rather than inventing
content (e.g., risks the seed never raised). Read the synthesized
body before running `plan-tool detail` — invented-looking content in
a populated section is the regression to watch for, since the
`completeness` primitive only flags TODOs.

**Escape hatch — `--no-synthesize-body`.** Opt out of the synthesis
round-trip; the body falls back to H2-extraction → `_(TODO)_`.
`plan-tool runs show` distinguishes this from canonical-skip via
`skip_reason=no_synthesize_body`. Reach for it when:

- Running a regression test that pins pre-synthesis output bytes.
- The seed is canonical-by-construction and the operator wants to
  bypass the canonical-skip detection's read pass.
- Token cost is under a hard cap and the operator accepts `_(TODO)_`
  body sections that `plan-tool detail` will fill later.

**Checkpoint resume.** The synthesis round-trip caches at
`.plan-tool/checkpoints/<plan-slug>/create-body-sections-*.json`.
Interrupted runs replay completed iterations' cached payloads; only
the in-flight iteration re-invokes Claude. See
[Workflow: recover from an interrupted create/detail run](#workflow-recover-from-an-interrupted-createdetail-run)
below.

To pick a non-default output location:

```bash
plan-tool create my-feature --output-dir custom/path/
```

---

## Workflow: drive a plan to completion

After reviewing the seed, plan and details, request execution separately:

> Execute this reviewed plan through the plan-tool skill, reconcile code against
> the plan and review changes to convergence. Link reports and summarize changes,
> validation and unresolved decisions.

For inspection alone, ask: “Inspect the plan, saved reports and any active
invocation; report state and next decisions without implementing.” To hand off
instead, ask: “Export local Jira stories and their paired developer handoff;
link both and summarize changes and validation for review.” Local export does
not authorize tracker publication. Reading a demo or requesting planning does
not authorize execution.

```bash
# 1. See where you left off.
plan-tool status my-feature

# 2. Only before execution, refresh a stale, unexecuted plan if needed.
# plan-tool reconcile-plan my-feature --refresh

# 3. Run the next pending step (the launcher picks it automatically).
plan-tool run my-feature --commit

# 4. Check status; the step you just ran is now `done` and the next
# runnable step is `current`.
plan-tool status my-feature
```

Repeat 3–4 until `progress=N/N`. Then run a complete
`plan-tool reconcile-code my-feature --all` sweep, save the reports and drive
code review under the [post-run contract](integrations/shared/DIRECTIVES.md#after-run-finishes-a-plan).
Use actual audits as drift evidence; `--dry-run` renders prompts only. Do not
insert completeness audits into this execution tail. The launcher only advances on a clean
exit from claude; a non-zero exit leaves the plan untouched.

At a milestone — some steps `done`, more still pending — consider
[`suggest-gates`](#workflow-lock-in-gates-with-suggest-gates) to lock in
what the built steps established before running the rest.

**Forgot the slug?** Run `plan-tool run` with no name (or a name that
doesn't resolve) in a terminal and it lists every plan that still has
open steps, lets you pick one, then asks whether to run **all** runnable
steps or just the **next** one. The plan list defaults to the last plan
you ran, and the all/next question to the last choice you made for that
plan (both remembered in `.plan-tool/run-prefs.json`). It's TTY-only —
piped / `-y` invocations keep the old behavior (missing name errors, bad
name re-raises) so scripts fail fast instead of hanging on the prompt.

**Missing-detail gate.** Before `run` executes — a single step or an
`--all` sweep — it checks the in-scope steps' `detail` files (a single
run checks the one step; a sweep checks the whole plan up front). If any
are unset or point at a file missing on disk, it prints a `warning:` line
naming the step(s) and the `plan-tool detail <slug> --step <id>`
remediation, then **asks to confirm** before opening a run log or
spending a claude call: `Proceed without these detail file(s)? [y/N]`
(default No). `-y` proceeds without asking; a non-interactive stdin
(pipe / CI) proceeds with the warning rather than hanging — pass `-y` to
silence it. Declining aborts cleanly (exit 0, no run log written). The
gate is suppressed under `--dry-run` (no claude call to ground). During a
sweep, each swept step still gets its own one-line recommendation right
before its call.

**Per-step test directive.** When test enforcement is on (see below) the
`run` prompt carries a test directive for a `change_type` step: both code
types (`refactor` and `feature`) are asked for tests covering the behavior
the step changes, green before it finishes. non-code / unclassified steps
get no directive. Classified steps also show an inline
`[refactor]`/`[feature]`/`[non-code]` tag in `status` and `run` step lines.

*Withdrawn 2026-07-30 — do not reintroduce:* the directive used to differ
by type, telling `refactor` steps to pin characterization tests green
*before* touching the code and keep them passing unchanged after. A retrospective
replay of every refactor step in this repo's history, against its own
pre-change source, found **81–89% cannot satisfy that** for legitimate
reasons — a refactor that renames or re-shapes what tests name leaves them
unable to import pre-change. The contract, not the checker, was wrong.
What remains enforced is the part the tool can verify: that a test file
really changed.

**Test-authoring enforcement (`enforce_step_tests`).** A plan with
`enforce_step_tests: true` (the default on plans `create` writes; legacy
plans without the key stay off) adds the directive above **and** a
post-flight gate: after a feature/refactor step's claude call exits 0,
`run` blocks advancement unless a test file (`tests/…` or `__tests__/…`,
`test_*.py`, `conftest.py`, `*.test.ts` / `*.spec.tsx` and siblings) was
created or modified during the call. It runs before
`test_command` / per-step `gate`, and is detected by diffing `git status`
before vs. after — so outside a git tree it never blocks. When it fires,
the step stays `current` with a `status_note`; fix it by adding a test,
exempting the step (`steps[].enforce_test_authoring: false`, e.g. a
test-less wiring step or one whose test lands later), or unsetting
`enforce_step_tests` plan-wide. The gate only checks that *a* test
changed — pair it with `test_command` to also require the suite passes.
**Known limit:** an uncommitted multi-step sweep (`run --all` without
`--commit`) can false-block a step that only re-edits a test left dirty
by an earlier step; `--commit` avoids it.

To re-execute a specific step (e.g. you noticed it landed something
wrong and want to redo):

```bash
# First, manually flip the step's status: from `done` back to `pending`
# in the plan's frontmatter (with your editor — plan-tool has no
# "unmark" command).
plan-tool run my-feature --step 4
```

When the plan is still being authored (not just executed),
`create --iterate`, the bare audit, one-shot `detail`, and the grounded audit
prepare the reviewed bundle before the per-step `run` cycle starts.
See [Workflow: drive an authoring task to convergence](#workflow-drive-an-authoring-task-to-convergence---iterate).

### Gated sweep: `run --all --commit`

`plan-tool run <name> --all` sweeps every runnable step in one
invocation (halting on the first failure; `--all` implies `-y`). A few
behaviors turn that sweep into a gated, committing runner — natively,
with no shell harness. For a visual map of the full gate gauntlet (which
gates fire on every run, which only under a flag, and which are advisory
vs blocking), see [`docs/how-to/pipeline/run.md`](docs/how-to/pipeline/run.md):

- **`--commit` — one git commit per green step.** `plan-tool run
  <name> --all --commit` makes exactly one commit each time a step goes
  green, so any later failure leaves precisely one step's work dirty and
  rollback is `git reset` to the last commit. The commit subject is
  `plan(<slug>): step <id> green — <title>` (em dash U+2014), with no
  AI-attribution trailer — the operator's own git identity is the sole
  author of record. A **dirty working tree at start is rejected with
  `rc=2`** before
  any claude call (the one-commit-per-step guarantee breaks if
  pre-existing edits fold into the first step's commit). `--commit` also
  works at single-step scope (`plan-tool run <name> --step N --commit`,
  or the default "next" run) — it commits that one green step the same
  way; without it the run makes zero commits.

- **Per-step `gate` (frontmatter field).** Each step's `gate:` commands
  (see [`PLAN_FORMAT.md`](PLAN_FORMAT.md#field-semantics)) run after the
  step's claude call and the plan-level `test_command` gate, before
  advancement. The first non-zero exit halts the sweep with the step
  left in its current status and a `status_note` naming the failing
  command. A gate is **declared on the step whose work just finished**
  but typically **checks an invariant from earlier work** — e.g. step 1
  established `tests/test_foo.py`, step 4 carries
  `gate: pytest tests/test_foo.py`, and that command runs after step 4's
  claude call to catch step 4 regressing step 1 before the plan
  advances. Author gates with
  [`suggest-gates`](#workflow-lock-in-gates-with-suggest-gates) or by
  editing frontmatter directly — not in a shell script keyed by plan slug.

- **Halt capture.** When a sweep halts — a run failure, or a refused
  per-step `gate` / plan-level `test_command` — a one-line entry
  `- <ts> step N halt (sweep): <reason>` is appended to the plan's
  declared `lessons:` file, so a halt self-records next to the plan it
  guards (your post-mortem lesson can extend the line after the fix).
  Plans with no `lessons:` field are unaffected. See
  [Workflow: consolidate lessons files](#workflow-consolidate-lessons-files)
  for reading the log.

- **`--archive` — auto-archive the plan the moment it goes N/N done.**
  When a step takes the plan to `status: completed` with every step
  `done`, the plan file moves to `<plan-dir>/archive/`, its
  `plan-details/<slug>/` moves alongside, and its manifest entry is
  deregistered — the same move `plan-tool sweep` performs, fired at the
  exact completion moment instead of as a remembered second command. The
  run then prints the archived path and a `plan-tool register
  <archived-path>` undo line.
  - Fires from both the `--all` sweep's terminal step and a completing
    `--step N` run. A non-terminal `--step N` run prints a brief
    `--archive: plan not complete (<done>/<total> done); nothing
    archived.` no-op note; the `--all` sweep prints no per-step note on
    non-terminal steps.
  - **Off by default.** A completing plan should not silently leave the
    manifest mid multi-PR ship unless the operator opts in — `--archive`
    keeps `sweep`'s explicit-trigger contract. Without it, `run --all`
    completes a plan with the file in place and the manifest entry intact
    (behavior unchanged).
  - **Ordering with `--commit`:** on the completing step the archive runs
    **before** the commit, so the plan move + manifest deregister ride the
    terminal step's green commit (`git add -A` captures them). The tree is
    clean afterward — a follow-up `--commit` run isn't blocked by the
    clean-tree precheck.

```bash
# One command: execute every runnable step, commit each green step,
# then archive the plan the moment it goes N/N done.
plan-tool run my-feature --all --commit --archive
```

---

## Workflow: lock in gates with suggest-gates

Per-step `gate:` commands are post-flight checks `run` executes after a
step's claude call (and after the plan-level `test_command`, if any),
before marking the step `done` and advancing. Use them for
*ephemeral / structural / cross-artifact / per-milestone* invariants that
would rot or be wrong as permanent unit tests — a `--help` golden diff, a
`grep` that a removed identifier stays gone repo-wide, a scoped `pytest` of
the suite a milestone established. Durable behavioral checks belong in real
unit tests (`test_command` / the suite). See
[`PLAN_FORMAT.md`](PLAN_FORMAT.md#field-semantics) for the three-layer
split (`test_command` vs `gate` vs unit test).

**When to run `suggest-gates`.** Not "after the whole plan is finished."
Run it **mid-run**, at a milestone, when some steps are already `done` and
you want to arm the **remaining** steps before continuing:

```text
create → detail → run steps 1–N (done)
                        ↓
              suggest-gates   ← grounding: what steps 1–N actually built
                        ↓
              run steps N+1…  ← gates on later steps fire after their work
```

The default path needs at least one **built** (`done`) step — the command
reads those steps' detail and the real repo/diff, proposes commands grounded
in artifacts that exist *now* (real test paths, symbols, the actual diff),
and attaches the ones you keep to **not-done** steps' frontmatter. A gate
on step 4 that runs `pytest tests/test_foo.py` is protecting work step 1
established: it fires **after** step 4's claude call, blocking advance if
step 4 broke step 1.

```bash
# After steps 1–3 are done; propose gates for steps 4+.
plan-tool suggest-gates my-feature

# Each suggestion: (k)eep / (e)dit / (m)ove to another remaining step / (d)rop.
# Confirmed gates are written to the plan file.
```

`-y` / non-TTY: prints the suggestions as a report and **writes nothing**
— a gate is an executable shell command, so with no operator present the
safe default is to surface it rather than apply it unvetted.

**No steps built yet (`--all-steps`).** When **no** step is built yet —
a freshly-written, still-skeletal plan — pass `--all-steps` to propose
gates from each not-done step's stated intent and detail instead of the
real diff. Weaker grounding (speculative, since the code doesn't exist
yet), but the only way to get gates on a plan with nothing built:

```bash
plan-tool suggest-gates my-feature --all-steps
```

**Two authoring moments (don't confuse them).**

| Moment | Command | Grounding |
| --- | --- | --- |
| Plan just written, no code yet | `suggest-gates --all-steps` | Speculative — from step intent / detail |
| Some steps `done`, rest pending | `suggest-gates` (default) | Real — from built steps, diff, repo |

You can also hand-edit `steps[].gate` in frontmatter; `suggest-gates`
only *proposes* candidates you confirm. `create` does not propose gates.

**At runtime.** Once gates are on the plan, every `plan-tool run` in
mutating mode runs them in the post-flight gauntlet — see
[`docs/how-to/pipeline/run.md`](docs/how-to/pipeline/run.md) steps [12]–[13]. A failing gate
leaves the step `current` with a `status_note`; fix the regression and
re-run that step. When the failing test is the step's own defect, fix it by
hand, run the full suite, commit, and certify the step with
`plan-tool run <slug> --step N --accept` instead — see
`integrations/shared/DIRECTIVES.md` § "When a `run` step's own tests fail".

---

## Workflow: drive an authoring task to convergence (`--iterate`)

`--iterate` turns five CLI surfaces into convergence loops:
`create`, `detail`, `detail --reconcile`, `run --reconcile`, and
`completeness`. **`create` and `detail` opt INTO the loop by
default** (pass `--no-iterate` to skip); the two reconcile
subcommands and `completeness` are opt-in (pass `--iterate` to
enable). Each loop runs its deterministic correctness/completeness
primitives after every write, hands the findings back to claude via
`apply-finding` (or, under `run --reconcile`, lands code edits
inline), and stops when findings converge, the budget exhausts, or
the loop stops making progress. `completeness --iterate` exists for
CLI symmetry and is largely a no-op in practice — reach for it only
when automation needs the flag threaded uniformly; reach for
`create --iterate` or `detail --iterate` to actually drive
authoring convergence.

See [README.md → Iterating to convergence](README.md#iterating-to-convergence---iterate)
for the canonical "when to use" decision tree. This section covers
the operational recipes.

> **Convergence is the plan's correctness signal — not just a loop
> mode.** A plan that converges under audit→apply is sound. A plan that
> *won't* converge — the same region re-flagged each pass, findings not
> shrinking, the body only growing — is telling you the plan is the
> wrong **shape**, and `apply_finding` (a prose editor) can't fix shape.
> The response is to **re-decompose** (re-split one step, or re-seed the
> plan), not to patch a fourth time. See
> [When repeated audit/apply doesn't converge](#when-repeated-auditapply-doesnt-converge--re-decompose-dont-keep-patching)
> for the signature and the re-split-vs-re-seed fork.

### Create with iteration

```bash
# --iterate is the default for `create`; shown explicitly here for clarity.
plan-tool create my-feature --iterate \
    --from-existing /tmp/seed.md \
    --output-dir docs/implementation-plans \
    -y < /dev/null

# Opt out of the post-write loop:
plan-tool create my-feature --no-iterate \
    --from-existing /tmp/seed.md \
    --output-dir docs/implementation-plans \
    -y < /dev/null
```

Default budget: 3 iterations × 300s wall-clock. After the initial
`write_new_plan`, the loop runs the body-section / detail-coverage /
references-coherence primitives (from `review.py`'s deterministic
completeness check), passes any findings to `apply-finding` against
the just-written plan body, and reauditions. Each iteration's claude
call invalidates the `create-initial-steps` checkpoint cache (the
iteration index is folded into the hash key), so a resumed run
replays completed iterations and re-invokes claude only for the
in-flight one.

### Detail with iteration

Use this optional per-step loop only when explicitly requested; normal planning
uses one-shot detail followed by the detail-grounded audit.

```bash
plan-tool detail my-feature --iterate
plan-tool detail my-feature --iterate --step 3
```

Each step gets its own per-step budget — exhausting step 2's budget
does not block step 3's iteration. The per-step loop runs the
`detail-quality.md` review (a claude call that produces findings on
the just-written detail body), hands those findings to
`apply-finding`, and re-renders. The detail file is mutated in place
between iterations, so iteration N+1 reads the prior pass's output
as its starting point.

### Reconcile with iteration

```bash
plan-tool detail my-feature --reconcile --step 3 --iterate
plan-tool detail my-feature --reconcile --step 3 --iterate -y
plan-tool run    my-feature --reconcile --step 3 --iterate
plan-tool run    my-feature --reconcile --step 3 --iterate -y
```

Reconcile's loop is the audit→edit→audit cycle. Under
`detail --reconcile` (prompt mode `detail-reconcile`), claude
proposes plan/detail edits, the walk applies them via
`apply_finding`, the deterministic primitives re-audit the post-edit
plan, and the loop reinvokes the audit if new findings surfaced. The
inner walk defaults to `apply-all` (via the `WalkState(yes_to_all=True)`
seed) under `-y` or non-TTY so iteration N+1 isn't blocked on
per-rec prompts.

Under `run --reconcile` (prompt mode `run-reconcile`), there is no
recommendation walk — claude lands code edits inline under
`--permission-mode acceptEdits`. The loop is audit → code edits →
re-audit; iteration N+1 reads the post-edit working tree as its
starting state.

### Completeness with iteration

```bash
plan-tool completeness-audit my-feature --iterate
plan-tool completeness-audit my-feature --iterate -y < /dev/null
```

`completeness-audit` accepts the same `--iterate` / `--max-iterations` /
`--iteration-budget` surface as the other three subcommands. Off by
default — like `detail`, and unlike `create`, which iterates by default —
so you must pass `--iterate` explicitly to drive the loop.

`--reuse-audit` substitutes the up-front `audit_plan_until_stable` call with the
saved sidecar's findings when fresh, so a second `--iterate` run on an unchanged
plan+code skips the conceptual re-sample — see
[Reusing a saved conceptual audit](#reusing-a-saved-conceptual-audit---reuse-audit).

The loop iterates correctness and structural findings: each iteration
re-runs the deterministic audit, hands open findings to claude via
`apply-finding`, and re-audits the now-mutated artifact.
Conceptual-*completeness* findings (orphaned concepts, uncovered risks,
…) are deliberately excluded from this loop because a fresh conceptual
audit always surfaces more — chasing them would never converge. Address
those with the paired `plan-tool completeness-apply <name>` verb (see
the "Address conceptual gaps" workflow below).

When deterministic findings converge but conceptual bar blockers remain,
the iterate loop stops with **`terminal_hand_apply`** (not `converged`) —
hand-apply or `completeness-apply` the remaining conceptual gaps. Bare vs
detail bars differ; see [`integrations/shared/DIRECTIVES.md`](integrations/shared/DIRECTIVES.md).

Reach for `completeness-audit --iterate` only as the narrow variant —
audit-only convergence without the rest of the create/detail authoring
loop. For actual convergence-driving authoring, reach for
`create --iterate` (drives completeness findings to convergence as part
of the create flow) or `detail --iterate` (drives the
`detail-quality.md` review per step).

### The escalate-to-split bridge (auto split-or-recommend)

When the convergence loop meets a step that *mixes* a behavior-preserving
refactor with new behavior — the one shape `apply_finding` (a prose
editor) can never fix — `plan_tool/launcher.py:escalate_to_split` decides
between **applying** the 1→2 refactor+feature split and **recommending**
it. Two invariants govern that choice:

- **Always surface the more-correct plan.** Even when the bridge declines
  to auto-edit, it emits a `structural-split` recommendation pointing at
  `plan-tool split` — you always see that the step should be split.
- **Never mutate plan structure unattended.** The bridge writes a split
  only on a safe, opted-in, interactively-confirmed path; every other
  path recommends without touching the plan.

**Apply vs. recommend.** The split is auto-applied only when *all* hold:
it is **safe** (no downstream non-`PENDING` / run-started step depends on
the step being split), the caller **opted in** (`allow_split`, set by
interactive `detail --split`), and an **interactive confirm answers
yes**. Any other path — unattended, unsafe, off a TTY, or a declined
confirm — recommends only, mutating nothing; on the default
(non-`--split`) path no Claude is spent reaching that decision.

**The two `detail` triggers.** Map output back to its cause:

- **Trigger 1 — granularity purity check.** Before the apply loop, the
  MIXED-STEP purity check flags an over-packed / mixed step (the
  `granularity-split` finding from `plan_tool/granularity.py`), handled in
  `plan_tool/detail.py:generate_detail`'s Phase B.
- **Trigger 2 — `BLOCKED-STRUCTURAL` verdict.** Mid-apply on an ordinary
  finding, Claude returns the `BLOCKED-STRUCTURAL` verdict (its only
  correct fix is a split); the convergence apply loop routes that through
  the bridge.

**Where you see it.** Four surfaces render the escalation:

- The `structural-split` recommendation, rendered by
  `plan_tool/review.py:triage_reason` / `emit_triage_summary` with the
  split rationale and the concrete `plan-tool split …` invocation on
  sub-lines.
- The post-loop `plan_tool/detail.py:_emit_split_recommendations` emitter
  on default (non-`--split`) `detail` runs.
- The interactive review / reconcile apply walk: a `BLOCKED-STRUCTURAL`
  verdict there routes through
  `plan_tool/cli/review_actions.py:_dispatch_apply_finding` to the same
  bridge — recommend-only unless the walk opts in via `allow_split`.
- The `completeness-apply` serial walk: a saved `medium` `granularity-split`
  MIXED-STEP finding routes through
  `plan_tool/cli/review_actions.py:_dispatch_structural_escalation` to the
  same bridge — recommend-only unless the walk opts in via
  `--apply-structural` (see [Address conceptual gaps](#address-conceptual-gaps-completeness-apply)).

The **`create` path surfaces no escalate-bridge recommendation yet** — its
change-type review loop still shows the pre-existing `granularity-split`
`(s)plit` hints, but those never reach `apply_finding`, so the bridge is
not wired into `create` (create-side trigger deferred).

The bridge is the **automatic front-end** to the manual re-split fork in
[When repeated audit/apply doesn't converge](#when-repeated-auditapply-doesnt-converge--re-decompose-dont-keep-patching)
— its path 2a (`plan-tool split` / interactive `detail --split`). It
handles only the localized one-step split; the cross-step re-seed fork
(path 2b) stays manual.

### How the loop terminates

- **Converged** — claude returned no new findings vs the prior pass.
  Exit code 0. The artifact is in the converged state.
- **Marginal stagnation** — iteration N's findings overlap iteration
  N-1's without introducing anything new. Exit code 0. The artifact
  is no worse than the prior iteration; further iteration yields
  nothing new.
- **Budget exhausted** — iteration count hit `--max-iterations` (3
  by default) or wall-clock hit `--iteration-budget` (300s by
  default). Exit code 0 — the audit completed; the remaining open
  findings are in the report (and, for `completeness --json`,
  bar-aware `has_blocking_findings`) for CI gates to inspect. Pass
  `--fail-on-findings` to exit non-zero when stage-bar blockers remain
  (`audit_incomplete` or any id in `conceptual_bar_blocking_ids` — see
  `--json` `stage` and [`integrations/shared/DIRECTIVES.md`](integrations/shared/DIRECTIVES.md)).

### Tuning the budget

```bash
plan-tool detail my-plan --iterate --max-iterations 5
plan-tool detail my-plan --iterate --iteration-budget 600
plan-tool detail my-plan --iterate --max-iterations 1 # one pass only
```

`--max-iterations 1` runs the loop once (write → audit → apply →
stop). **Not** equivalent to `--no-iterate`, which short-circuits
the loop entirely (skipping the `apply-finding` call too):

- **`--max-iterations 1`** — exactly one fix pass.
- **`--no-iterate`** — skip the convergence loop.

---

## Workflow: review concept decisions and ownership (`scope-review`)

Create presents each derived concept's `include`, `defer`, or `wont_do`
decision and the owning committed step IDs before it writes an interactive
plan. Accepted owners are persisted as exact IDs in `Step.concept_ids`. Detail
then shows signed-off decisions and owners in its authoring context and records
any step-specific deferral in the concept record's structured metadata. It does
not treat generated detail prose as a decision or sign off a proposed
deferral.

Use `scope-review` to reopen review for an explicit set of concept IDs at the
plan's current source state. The validated
`plan-details/<slug>/concepts.json` record is authoritative; the command
synchronizes its accepted decisions to the plan Markdown. Inspect that record
to select IDs and to reconcile any reported conflict. A parent ID covers only
that ID: repeat the flags for every descendant that belongs in the review.

Select the known plan and explicit concept IDs before using this workflow.

```bash
plan-tool scope-review my-plan \
  --concept CONCEPT_ID \
  --decision CONCEPT_ID=include

# Review a grouped scope; supply exactly one decision per listed concept.
plan-tool scope-review my-plan \
  --concept FIRST_ID --decision FIRST_ID=defer \
  --concept SECOND_ID --decision SECOND_ID=wont_do
```

The three decisions are `include` (committed scope), `defer` (parked for
later), and `wont_do` (out of scope). A successful command signs off only the
listed IDs, leaves unlisted concepts unchanged, synchronizes the concept record
and plan, prints the reviewed count, and exits 0.

Interactive create is the ownership sign-off gate. `create -y`, piped input,
and other non-TTY create runs may retain proposed decisions in the record, but
they do not approve those decisions or copy proposed owners into
`Step.concept_ids`; `detail -y` likewise never signs off an unreviewed concept.
Use `scope-review` for explicit sign-off, then assign every included concept to
at least one committed step when ownership is absent. The durable coverage
contract is the exact `Step.concept_ids` link or a valid structured deferral.
Step titles, `features`, file lists, and body/detail prose are explanatory only.

Completeness reports two concept-specific sources:

- A medium `concept-coverage` self-consistency finding is blocking when a
  signed-off concept has neither an exact committed owner nor a valid
  structured deferral. An approved `wont_do` decision is also explicitly
  accounted for.
- An info `concept-unsigned-deferral` smell means a proposed `defer` or
  `wont_do` decision still needs review. It is advisory and cannot stand in for
  sign-off.

Neither finding is eligible for `completeness-apply`: a prose editor cannot
choose an owner or approve a scope decision. Resolve it by editing explicit
ownership, running `scope-review`, or making a reviewed structured scope
decision, then re-run `plan-tool completeness-audit <name>`.

Structural remedies preserve the same contract. Split replacements must
exactly conserve the source step's concept-ID set; merge computes the ordered,
deduplicated union of all merged steps. Mark-done keeps each step's ownership,
and a re-baseline seed prints the source `concept_ids` so the next create run
can carry them forward. `scope-out --apply` retains concept IDs in its forward
seed and signs off a structured `defer` decision for each carved concept that
has no committed surviving owner.

If the plan changes, re-run the same command against the current concept IDs
and source state. The command re-derives unchanged concepts before applying the
requested review; it never overwrites a reviewed conflict automatically.

- **Exit 3 / `scope-review conflict`, `source_divergence`, or
  `mapping_conflict`:** the derived, persisted, or plan state has competing
  edits. No changes are written. Inspect the reported concept/field, the plan,
  and `concepts.json`, reconcile the intended authority explicitly, then retry
  the command.
- **Exit 4 / `scope-review invalid state`:** the record is malformed or stale,
  the requested scope/decision set is invalid or incomplete, or synchronization
  cannot validate/publish the candidate. No changes are written. Inspect the
  complete message, confirm every `--concept` has exactly one matching
  `--decision`, and repair or explicitly remove an invalid concept record before
  retrying.
- **Argparse exit 2:** a required flag is absent or a decision is not one of
  `include`, `defer`, or `wont_do`. Correct the invocation shown by
  `plan-tool scope-review --help` and retry.

There is no automatic conflict-resolution flag. Do not treat plan prose or a
prompt response as approval; only a successfully validated and synchronized
concept record carries sign-off for the requested source state.

## Workflow: review before running

`plan-tool reconcile-plan` audits the plan body and frontmatter against
the code on disk. It's most valuable on a **plan that has aged** — one
authored a while ago, where the codebase has moved on underneath it and
the steps/paths/detail may no longer match reality. For a freshly
authored plan, `plan-tool completeness-audit` is the primary audit (see
[Workflow: completeness checks](#workflow-completeness-checks)); reach
for `reconcile-plan` there only as a **supplement** when you also want an
explicit plan-vs-code fit pass before running.

### Single-step audit

```bash
plan-tool reconcile-plan my-feature --step 5
```

Produces a markdown report with three sections: a top-level "Plan-wide
path issue" diagnostic (when ≥80% of declared paths don't resolve), a
per-step OK/WARN line with abs-path-aware diagnostic text, and Claude's
semantic review using the step's `detail:` body for acceptance criteria.

To inspect the prompt that *would* be sent to claude without invoking
it:

```bash
plan-tool reconcile-plan my-feature --step 5 --dry-run
```

### Saved reviews and the walk-through

Every `plan-tool reconcile-plan` run persists a JSON artifact under the plan's
reports directory —
`<plan-dir>/plan-details/<plan-slug>/reports/<timestamp>.json` — by
default, alongside the plan's detail files (so reports travel with the
plan in version control). The artifact contains the rendered markdown
report plus a structured list of `Recommendation` items extracted from
the review (file-check warnings, heuristic hits, dep issues, path-style
hint, and any `## Findings` bullets claude emitted).

The closing line of `plan-tool reconcile-plan` names the saved path so you can
inspect or step through it later:

```
Saved to /repo/docs/plan-details/my-feature/reports/20260505-123456.json (4 recommendations)
```

To opt out for a one-off run that shouldn't clutter history:

```bash
plan-tool reconcile-plan my-feature --no-save
```

**Reuse-last-review prompt.** When you run `plan-tool reconcile-plan <name>`
in an interactive shell and a **fingerprint-fresh** saved review exists
for that plan, the CLI offers to reuse the saved one instead of spending
a fresh claude call:

```
A saved review for 'my-feature' exists (5m ago, 4 rec(s), 1 annotated):
  docs/plan-details/my-feature/reports/20260505-123456.json
Walk that one instead of running a fresh review? [y/N]
```

The offer now fires **only when the saved sidecar is fingerprint-fresh**
— its captured plan AND code fingerprints both still match disk; the
freshness gate catches the staleness that used to make reuse a gamble,
so a stale save never even prompts. Unset still defaults to a prompt:
hit Enter or `n` to run a fresh review, type `y` to load and walk the
saved one, or script the decision with `--reuse` / `--no-reuse` /
`--reuse-id` (see
[Reusing a saved reconcile](#reusing-a-saved-reconcile---reuse)). The
prompt is suppressed for `--dry-run`, `--no-save`, `--no-walk`,
`--step N`. On non-TTY stdin (CI / pipes), an eligible fresh save is
auto-accepted instead: the command prints its findings and skips the
per-finding walk, without spending a fresh claude call.

**Reuse-last-reconcile prompt.** The same offer fires for
`plan-tool detail <name> --reconcile` when a saved reconcile
exists for the resolved target step:

```
A saved reconcile for 'my-feature' step 3 exists (12m ago, 4 rec(s), 0 annotated):
  docs/plan-details/my-feature/reports/20260505-130000-detail-reconcile.json
Walk that one instead of running a fresh reconcile? [y/N]
```

Reconciles are step-specific, so the prompt only fires when the
saved file's `step_id` matches the step the user is now reconciling
**and the save is fingerprint-fresh** (plan AND code fingerprints
match disk). The same freshness gate now catches the staleness that
saved reconciles used to drift into; `--reuse` / `--no-reuse` /
`--reuse-id` script the decision (see
[Reusing a saved reconcile](#reusing-a-saved-reconcile---reuse)).
Suppression rules match the review prompt (`--dry-run`, `--no-save`,
`--no-walk`, non-TTY).

**Walking recommendations.** The walk is **on by default** when stdin
is a TTY and the review produced at least one recommendation —
non-interactive contexts (CI, pipes, redirected stdin) skip it
silently. Three flows reach the same loop:

```bash
# 1. Run review (walks automatically; offers reuse if a saved one exists):
plan-tool reconcile-plan my-feature

# 2. Walk a previously-saved review (newest by default):
plan-tool reconcile-plan-walk my-feature
plan-tool reconcile-plan-walk my-feature --id 20260505-123456
plan-tool reconcile-plan-walk my-feature --rewalk # re-prompt annotated items

# 3. Opt out of the walk for a one-off review:
plan-tool reconcile-plan my-feature --no-walk
```

For each recommendation the walk prints title, severity, source/step,
body, and suggested action, then prompts:

```
[2/4] [MEDIUM] Step 3: declared file path doesn't resolve
  source: file-check · step 3

  `src/foo.py` (resolved to /abs/src/foo.py; parent /abs/src missing under repo root /abs)

  suggested: verify the path or pass --allow-missing-parent if the step legitimately creates `src/foo.py`

  (a)pply [default] / (s)kip / (f)eedback / (r)un / (q)uit / (?) help >
```

- `a` / `apply` — apply this recommendation. The apply dispatch forks
  by finding shape:
  1. **Recognized command shape** (`plan-tool detail … --reconcile
     --step N`, `plan-tool run … --reconcile --step N`, or
     `plan-tool detail … --step N [--force]`) — the walk runs the
     command directly.
  2. **Reconcile or claude finding** (`source ∈ {reconcile, claude}`,
     freeform body describing a plan edit) — the walk invokes Claude
     against the finding via `apply-finding` mode, shows the resulting
     unified diff over the plan + step detail file, runs the
     correctness + completeness primitives against pre and post
     plan state, and surfaces a `Validation:` block listing any
     findings the edit *introduced* (`✗`) or *resolved* (`✓`).
     **Self-healing follow-up**: when the initial apply lands but
     the validation surfaces new regressions, `apply-finding`
     automatically makes one bundled follow-up Claude call asking
     it to fix every regression in a single edit, then recomputes
     the diff and validation against the original pre-edit state.
     The follow-up is skipped when the post-edit plan won't parse
     (broken YAML — piling more edits on top would muddy the
     eventual revert). After (the optional follow-up), the walk
     prompts `Keep these changes? [Y/n]` (or `Keep these changes
     despite N new finding(s)? [Y/n]` when regressions survived).
     **Default keeps**; `n` reverts both files to the pre-call
     snapshot. `BLOCKED` / `NOT-APPLICABLE` verdicts auto-revert
     without prompting. The validation pass uses the same
     deterministic primitives that back `plan-tool completeness`
     and the file-existence / dep / path-style checks in
     `plan-tool reconcile-plan` — heuristic and Claude-semantic findings
     are excluded since they're advisory, not regressions a plan
     edit can introduce.
  3. **MISSING_PARENT file-check** (`declared file path doesn't
     resolve`) — apply prompts `(c)reate / (f)ix`: `c` moves the path
     from the step's `files:` into `creates:` and writes the plan (the
     finding stops firing for good); `f` (the path is a typo) leaves the
     plan untouched and records the rec `skip` with a note so you fix the
     path by hand. Apply-all auto-picks `c`.
  4. **Structural-directive findings** (`granularity-merge` carrying a
     `merge` or `reground` directive kind) — behind `--apply-structural`
     the walk actuates them by directive *kind*: a `reground` directive
     dispatches to `plan_tool/reground.py:reground_bridge` (mark the
     already-built steps `done`), a pairwise `merge` directive to
     `plan_tool/detail.py:merge_bridge` (fold the steps). Either renders one
     status line and records `applied` only when the bridge actually mutated
     (otherwise `skip`); a **stale saved directive** (the plan changed since
     the finding was computed) is blocked before the bridge and downgraded to
     recommend-only. An **applied merge halts the walk**: the fold renumbers
     step ids, so every remaining saved rec now names the wrong step — re-run
     the diagnosis (whose fingerprint the fold changed) and re-walk for the
     rest. Only a **contiguous** (adjacent-id) pair carries a dispatchable
     `merge` directive; a **gapped** pair stays recommend-only prose (reorder
     the steps first, then `plan-tool merge` by hand). A `merge` directive is
     visible without `--include-info`; a `reground` directive still needs it.
     Without `--apply-structural` both recommend only — or use the per-remedy
     opt-ins `--merge` / `--reground` to enable just one bridge (`--apply-structural`
     is the enable-both superset). `--reground-rebaseline` makes an applied
     re-ground **also** write a `create --from-existing` re-baseline seed (still
     needing `--reground`/`--apply-structural` to apply and `--include-info` to
     surface the re-ground finding — visibility and apply are independent gates).
     See the walk-dispatch wiring (`plan_tool/cli/review_actions.py`).
  5. **Anything else** (deps, files drift, body-completeness, etc.) —
     the rec is recorded `applied` for you to address manually.

  **This is the Enter default** — blank input applies because the walk
  assumes you'll address each rec it surfaces.
- `s` / `skip` — defer (won't re-prompt unless `--rewalk`)
- `f` / `feedback` — type guidance for how to apply this rec. It's recorded
  as the rec's note AND fed into the next apply (injected into
  `apply-finding` as authoritative steering) so Claude makes the edit the
  way you described; then re-prompts for status. `n` / `note` are
  back-compat aliases.
- `r` / `run` — execute the rec's suggested action and re-prompt for
  status. Use this when you want to inspect the outcome (e.g. a nested
  reconcile walk's findings) before deciding `applied` vs `skip`. For
  shapes apply already auto-dispatches, `r` is the inspect-then-decide
  variant.
- `q` / `quit` — exit; previously-marked items keep their state
- `?` / `help` — print the keymap

Items already marked `applied` or `skip` are not re-prompted; pass
`--rewalk` to revisit them. Annotations persist after each response,
so a Ctrl-C between prompts loses only the in-flight question.

The walk's underlying status field is `"applied"` (older saves used
`"done"`; the loader silently rewrites `"done"` → `"applied"` so they
keep loading without manual migration).

### The "looks already done" heuristic and `--no-heuristic`

Per-step WARN lines that say *"looks already done (symbol `Foo`
present in `bar.py`)"* come from a deterministic symbol-token scan
that pulls identifier candidates from the step title and looks for
matching definitions in the declared files. The intent is to flag
steps whose work appears to be on disk already (so you run
`reconcile-plan` to confirm before re-implementing).

Two precision mechanisms keep false positives down:

- **Whole-token regex.** Patterns like `def foo` only match `def foo(`
  / `def foo:` / etc., not `def foobar`. Same for `class Foo`,
  `function foo`, and the various export-form prefixes.
- **Detail cross-check.** When a step has a `detail:` pointer and
  the file exists, only symbols that *also* appear in the detail body
  count. The detail file is the design intent — symbols the author
  didn't name there are unlikely to be the ones the step is "already
  done" about.

When the heuristic still trips structurally (e.g., refactor plans
across files full of existing same-named symbols), opt out for that
invocation:

```bash
plan-tool reconcile-plan my-feature --no-heuristic
```

File-existence, dep, path-style, and Claude's semantic review still
run; only the "looks already done" lines are suppressed. The flag is
per-invocation; there's no persistent opt-out.

### Plan-wide audit across done steps

```bash
plan-tool verify-all my-feature --mode check
```

Runs the chosen prompt mode against every step that's already `done`,
one claude subprocess per step. Useful right before merging or
shipping. Modes:

- `check` — does the code match the step's intent?
- `optimize` — perf review.
- `document` — gaps in inline docs.
- `test` — test-coverage gaps.
- `security` — security review.
- `lint` — style/convention issues.

Add `--max-steps N` to only audit the last N done steps. Add
`--dry-run` to print prompts without invoking.

### Aggregated reconcile across done steps (`verify-all`)

```bash
plan-tool verify-all --rollup my-feature
plan-tool verify-all --rollup my-feature --max-steps 3
plan-tool verify-all --rollup my-feature --dry-run
```

`verify-all` runs the reconcile prompt against every `done` step (one
subprocess each, same as `verify-all`) and prints one pass/warn/fail
verdict per step plus a summary. A completed run exits 0 even with
`[FAIL]` steps — the `[FAIL]` lines carry the verdict, so CI gates
parse the output rather than the rc, or pass `--fail-on-findings` to
exit non-zero on any `[FAIL]`.

How verdicts are assigned:

- **`[FAIL]`** — claude exited non-zero, OR its `## Findings` block
  contained a `CRITICAL:` bullet.
- **`[WARN]`** — `HIGH`, `MEDIUM`, or unspecified-format findings, OR
  no `## Findings` block at all (contract miss).
- **`[OK]`** — `## Findings` parsed cleanly with only `NIT:` items, or
  `_(none)_`.

Use `verify-all` when you want a single rollup verdict rather than the N
raw claude reports `verify-all` dumps. Both run the same per-step
reconcile prompt; `verify-all` adds the aggregation layer.

For a freshly-created plan with no done steps, `verify-all` prints
`nothing to verify (no done steps in '<name>')` and exits 0. The
distinct message keeps an empty plan from looking like a successful
audit.

---

## Workflow: export to JIRA for sprint planning

```bash
plan-tool jira my-feature
```

Renders the **whole plan** in a single claude call and emits a
consolidated set of JIRA stories, each sized to be an **atomic PR** —
work that merges on its own (once its `depends_on` land) without
breaking the build or tests. `--max-hours` (default 8) is an
**advisory** size target, not a hard cap. Each story has a title,
description, acceptance criteria, files in scope, plan-step coverage
(`steps: [int, ...]`), and `depends_on` references to other stories in
the same response.

Stories may **consolidate** multiple adjacent plan steps into one story
when they only make sense together, or **split** a single step into
multiple stories **only when each slice merges green on its own**; a
large-but-atomic story is kept whole rather than fragmented into
build-breaking pieces. Every plan step must appear in at least one story
(the parser rejects responses that drop a step).

By default the formatted markdown is **written to disk alongside the
plan** at:

```
<plan-dir>/plan-details/<plan-slug>/jira-stories.md
```

Stdout shows a one-line summary (`wrote N stories to <path>`). The
path mirrors the convention `plan-tool detail` uses, so the JIRA
artifact lives next to the per-step detail files.

Nudge toward smaller stories (advisory target only — atomicity still
wins, so a story that can't be split without breaking the build is kept
whole even above the target):

```bash
plan-tool jira my-feature --max-hours 2
```

JSON output (writes `jira-stories.json` instead):

```bash
plan-tool jira my-feature --format json
```

Pick a non-conventional output path:

```bash
plan-tool jira my-feature --output ./scratch/stories.md
```

Render the complete story/handoff pair without writing either file:

```bash
plan-tool jira my-feature --no-write
```

Print both written artifacts to stdout as well:

```bash
plan-tool jira my-feature --stdout
```

Migrate a readable legacy story export after verifying that every carried Jira
key maps to regenerated coverage:

```bash
plan-tool jira my-feature --adopt-existing
```

Every normal Jira export writes `jira-stories.{md,json}` and the paired Markdown
developer handoff under
`jira-handoffs/<plan-slug>/<normalized-story-stem>.developer-handoff.md`.
It requires structurally valid selected detail for every committed step that is
not done; deferred and `wont_do` steps remain only in the handoff's parked
history.

### Re-running after the plan changes

Every re-run regenerates the current committed stories and developer handoff
from one captured snapshot. A recognized same-plan pair may be replaced only
when its provenance names the same story path, handoff path, and format.

- **Jira keys survive only an exact coverage match.** A regenerated story keeps
  its prior `jira_issue_key` and lifecycle state only when its canonical covered
  committed-step set exactly matches one prior record.
- **Changed created tickets need a Jira update.** The output names them so the
  operator can update the real Jira ticket by hand.
- **Newly dropped created tickets remain a human decision.** The output names
  them; canceling or repurposing the real ticket stays in Jira.

An unproven legacy story file fails closed by default. Use `--adopt-existing`
only to convert the selected readable story source. A Markdown/JSON switch
shares the default normalized handoff stem and is a different generated pair,
so keep both formats by supplying a distinct `--handoff-output` path.

### Once a story is in JIRA

Create the ticket, then **write its key into the export by hand** —
`[jira: PROJ-4412]` on the story's header line. That is the handoff
record: it marks the story `created`, and it is how the next re-run knows
which stories still need creating.

From that point **JIRA is canonical**. Every transition, assignment, and
closure happens there. plan-tool holds the key and nothing else about the
ticket's life — it does not track In Progress, In Review, or Done, and it
never edits JIRA.

Two things still need you:

- **The plan changed under a created story.** The export is rewritten to
  match the plan and the run summary names the story, because the real
  JIRA ticket now says something different. Go update it.
- **A created story was dropped.** There is a live ticket the plan no
  longer backs. plan-tool names it and stops there — cancel, repurpose,
  or leave it is a call to make in JIRA.

---

## Workflow: author detail files for developer hand-off

Detail files are markdown specs (typically
`<plan-dir>/plan-details/<plan-slug>/NN-<step-slug>.md`) that explain
a step in enough depth for a developer to execute. `run`, `reconcile-plan`, and
`jira` all embed them in their claude prompts when present, so authoring
them up-front improves every downstream subcommand's output.
Detail prompts can also include focused current-file excerpts as grounding;
the detail files themselves remain developer hand-off specs, not generated
source excerpts.

```bash
# Draft a detail file for one step. Reviews and edits expected after.
plan-tool detail my-feature --step 3

# Generate for every step that lacks a detail file. Steps that already
# have one are skipped (use --force to overwrite).
plan-tool detail my-feature

# Inspect the prompt before invoking claude (no files written, plan
# file untouched).
plan-tool detail my-feature --step 3 --dry-run

# Regenerate an existing detail file (e.g. after the step's scope changed).
plan-tool detail my-feature --step 3 --force
```

Output is **a draft** — strong starting point, not final spec. Read
and edit each file before running the step.

The seven-section template is fixed by the prompt:

- **Summary** — 3–5 sentence reviewer-facing overview.
- **Table of Contents** — anchor index of the H2s.
- **Why** — motivation.
- **Files** — creates vs. edits.
- **Implementation** — intent over mechanics: what must hold + a recommended approach, exact code left to the implementer.
- **Tests** — test cases and paths.
- **Acceptance criteria** — observable, CI-checkable behaviors.
- Optional: **References**, **Deferred**.

If a step needs a different shape, generate then restructure.

After generating, the step's `detail:` field is set automatically.
`plan-tool reconcile-plan <name> --step N` then loads the file in its prompt
— verify with `--dry-run`.

**Exit codes from `plan-tool detail`:**

| rc | meaning |
| --- | --- |
| 0 | success, or every targeted step idempotently skipped |
| 1 | at least one step had a real failure (claude unparseable, write failed, frontmatter update failed) |
| 2 | plan-level error: bad name, malformed frontmatter, unknown explicit `--step` |

**Partial-success recovery.** If the detail file gets written but the
plan-frontmatter update fails (rare; e.g. someone else mutated the plan
mid-run), the file stays on disk without a `detail:` pointer. The error
message names the file path. Either delete the file and re-run, or
hand-add the `detail:` field to the step's frontmatter and validate
with `plan-tool validate <name>`.

---

## Workflow: annotate an existing plan to seed the next one

`plan-tool annotate <path-or-glob>...` judges existing plans (or
rough-notes files) against the current code and emits two artifacts per
source that seed the *next* iteration. `reconcile-plan` mutates a *live*
plan in place to match code that drifted under it (code-canonical
upkeep); `annotate` never touches its source unless you pass
`--archive` — it judges an old plan against current code and emits a
`<stem>.seed.md` to seed the next `create`. Live-plan progress upkeep →
`reconcile-plan`; starting the next plan from "what we built vs. what we
wrote" → `annotate`.

```bash
plan-tool annotate docs/implementation-plans/2-old-plan.md
plan-tool create next-plan --from-existing 2-old-plan.seed.md --iterate
```

The first command writes `2-old-plan.annotated.md` and
`2-old-plan.seed.md` beside the source; the second feeds the seed into a
fresh `create`.

For a batch, pass multiple paths and/or shell globs:

```bash
plan-tool annotate "docs/implementation-plans/archive/*.md" --report-dir .plan-tool/annotate-reports --seed-dir plan-seeds
```

Each source still gets its own report and seed. After the per-file
`annotated`, `seed`, and `grounding` lines, a batch run prints an
`annotate batch summary` table with `source`, `result`, implemented
coverage, grounding (`grounded/candidate (skipped skipped)`), and section
counts (`I/P/N/R`).

### Flags

- **`path-or-glob`** (positional, repeatable) — path or glob for the
  existing plan / notes file(s) to judge against the current repo.
  Non-files error per source (`CreateError` → rc 1), exactly like
  `create --from-existing`. These are filesystem paths, not registered
  plan slugs.
- **`--output-dir <dir>`** — directory for the derived
  `<stem>.annotated.md` / `<stem>.seed.md`. Defaults beside the source
  file.
- **`--report <path>`** — explicit path for the annotated report;
  overrides the derived name and `--output-dir` for that one artifact.
  Only valid with a single source.
- **`--seed <path>`** — explicit path for the create-seed; overrides the
  derived name and `--output-dir` for that one artifact. Only valid with
  a single source.
- **`--report-dir <dir>`** — directory for derived
  `<stem>.annotated.md` reports. Defaults to `--output-dir` or beside
  each source file.
- **`--seed-dir <dir>`** — directory for derived `<stem>.seed.md`
  carryover files. Defaults to `--output-dir` or beside each source
  file.
- **`--archive`** — the **only** mutation of the source: move the
  original (and, for an `N-slug.md` plan, its sibling
  `plan-details/<slug>/` bundle) into `archive/` with a one-line notice
  pointing at the report. Default: leave the source in place. **Caveat —
  manifest-registered plans:** archiving moves the file but does **not**
  touch `.plan-tool/plans.json`, so archiving a plan registered there
  leaves a dangling entry that `locator` resolution then fails on;
  annotate warns when it detects this but does not deregister (manifest
  mutation is out of scope), so update or remove the entry by hand.
  annotate's typical input is an unregistered old plan or rough-notes
  file, where this doesn't arise.
- **Archive collisions** — if `archive/<stem>.replaced.md` or the
  matching archived detail bundle already exists, annotate keeps the
  old archive intact and writes the next generation as
  `<stem>.replaced.1.md`, `<stem>.replaced.2.md`, and so on. When a
  `plan-details/<slug>/` bundle moves with the source, its archive
  directory uses the same generation suffix so the pair stays together.
- **`--iterate` / `--no-iterate`** — **unsupported**: annotate is
  single-pass today (one classification + two renderers, no convergence
  loop). Passing `--iterate` exits 2 before writing artifacts; use a new
  `create --from-existing <stem>.seed.md --iterate` run for convergence.

### The two outputs

- **`<stem>.annotated.md`** — the verbatim original plus per-section
  IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED status blocks and a coverage
  summary.
- **`<stem>.seed.md`** — the carryover brief ready for
  `create --from-existing`: every NOT-IMPLEMENTED section whole plus each
  PARTIAL's remaining work as scope; IMPLEMENTED sections plus each
  PARTIAL's already-implemented half as done-context (a PARTIAL is split,
  never re-planned whole).

Re-running overwrites both (idempotent refresh, no prompt). When every
section classifies IMPLEMENTED, the carryover is empty and annotate says
so explicitly — no next plan is needed.

### Grounding floor

Annotate grounds classifications in file-path candidates extracted from
the source. The report header records `grounded_files`,
`candidate_text_files`, and `skipped_or_unreadable_files`; the CLI prints
the same counts as a one-line `grounding` note. If grounding is too thin
to trust confident done verdicts, the annotated report shows a **Low
grounding** banner. Confident IMPLEMENTED sections become NEEDS-REVIEW,
and PARTIAL sections keep their status but carry a review-required note
into the seed so the next plan verifies the thin evidence instead of
silently treating it as done.

### Cached rollup

`plan-tool list --status` reads cached `*.annotated.md` reports for the
active manifest entries and prints one row per plan: whether a report was
found, IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED / NEEDS-REVIEW counts,
grounded file count, last annotation timestamp, and file path. It never
invokes Claude and never writes. Use `--report-dir DIR` to include a
non-conventional report cache and `--format md` for a markdown table.

---

## Workflow: recover from an interrupted create/detail run

> Inspect the plan, saved reports and original invocation first. Confirm that
> command has exited, then use its recorded outcome to select the next incomplete
> stage within my requested scope; show the recovery choice before continuing.

Follow [monitoring and safe recovery](integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely).
While the original process is live or its exit is unconfirmed, keep monitoring
it; do not start another invocation or checkpoint resume. Quiet output, a
checkpoint and a backend completion message do not establish command exit.

`plan-tool create` and `plan-tool detail` cache every successful
Claude response to `<repo>/.plan-tool/checkpoints/<plan-slug>/`. If
a run dies between a successful parse and the durable on-disk write
(write error, plan-update error, Ctrl-C, killed shell, model stall),
the next invocation reuses the cached body instead of re-invoking
Claude.

Looking for the *roadmap* recovery route instead? A `plan-tool roadmap` first
run that fails or is cut short leaves an unrelated resume directory of its
own — see
[Recover from a first run that didn't finish](#recover-from-a-first-run-that-didnt-finish).

### Re-run after a failure

After confirming the original command has exited, inspect its recorded outcome
and artifacts before selecting the retry. When the same command remains appropriate:

```bash
plan-tool detail my-plan -y < /dev/null
```

The `[N/M]` step counter reflects actual invocations — resumed
steps don't bump the denominator and appear with a
`(resumed from checkpoint)` suffix in the progress line.

### Force a fresh call

When the cache should NOT be reused (e.g. you edited a source file
that the hash doesn't track):

```bash
plan-tool detail my-plan --no-resume
# OR for one step:
plan-tool detail my-plan --step 3 --no-resume
```

`--force` also bypasses the cache (in addition to the file-exists
skip), so `plan-tool detail my-plan --step 3 --force` is appropriate
when both the on-disk file and any cached body should be replaced.

### Inspect what's cached

```bash
plan-tool checkpoint list
# slug name age bytes
# my-plan detail-step-02 42m 12340
# my-plan create-body-sections 1h 4521
# other-plan create-initial-steps 3h 892

plan-tool checkpoint show my-plan/detail-step-02 | bat
```

`show` writes the metadata (created_at / input_hash / schema_version)
to stderr and the raw payload to stdout, so it pipes cleanly.

### Clear stale state

When you abandon a plan or want a fresh start:

```bash
plan-tool checkpoint clear my-plan # one slug
plan-tool checkpoint clear --all # everything
```

Checkpoints older than 30 days are auto-expired by `load_if_valid`,
so manual cleanup is rarely needed — but operators can clear sooner.

### Caveats

- **Two simultaneous runs against the same plan are undefined.**
  No lockfile; both runs may invoke Claude, both may write, and the
  last writer wins for the checkpoint *and* the plan file. Don't
  overlap. If you need to deliberately interleave, pass
  `--no-resume` on the second run.
- **The hash is intentionally narrow.** It covers the inputs the
  prompt template needs (step shape; for `create`, the seed and
  output dir). Editing source file contents, sibling detail files,
  lessons, plan metadata, or the plan body between runs does NOT
  invalidate. Pass `--no-resume` to force a fresh call.

---

## Workflow: investigating a slow run

> Inspect the original invocation and matching run records, report its current
> phase and progress, and keep monitoring it to confirmed exit. Do not restart
> or advance stages while its exit remains unconfirmed.

Use the [canonical liveness procedure](integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely),
including its intervention rule: ask before stopping a live command. For a run
launched by another session, ask how the reader wants that session to report
completion rather than polling it as your own.

The run-log surface supports these diagnostic questions:

| Question | Where to look |
| --- | --- |
| What phase does the run record? | Match `in-flight.json` and JSONL by `run_id`; check the original process and shell separately |
| Which phase is taking so long? | `plan-tool runs show <slug>/<latest>` |
| Did a parse-retry fire? | grep `parse_failure` in `runs show` output |
| Was the cost different from yesterday? | `plan-tool runs diff <slug>/<yesterday> <slug>/<today>` |

### 1. Check the live snapshot first

When stderr looks frozen, `in-flight.json` is the authoritative
record of what the invocation is doing right now:

```bash
cat .plan-tool/runs/my-plan/in-flight.json | jq .
```

Sample output during a slow `cmd_run`:

```json
{
  "schema_version": 1,
  "run_id": "2026-05-14T12-34-56-9f3a1c",
  "command": "run",
  "plan_slug": "my-plan",
  "current_phase": "claude_call",
  "started_at": "2026-05-14T12:34:56+00:00",
  "last_event_ts": "2026-05-14T12:36:22+00:00",
  "step_id": 4
}
```

Use `current_phase` to locate the last recorded activity: `claude_call` records
backend work and `prompt_build` records prompt preparation. A stale timestamp
alone proves neither a hang nor its cause. Compare separated observations of
the original process, matching run-log tail and snapshot under the liveness
procedure before considering intervention.

Snapshot writes are atomic (tempfile + `os.replace`) on every phase
and claude-call boundary, so `cat` never races the writer.

### 2. Replay the events that already landed

Once the run finishes (or you Ctrl-C it), the full event stream is on
disk at `.plan-tool/runs/<slug>/<run_id>.jsonl`. Use `runs show` to
render it with phase / claude-call indentation:

```bash
# Newest first; pick the run_id you care about.
plan-tool runs list --slug my-plan

# Render it.
plan-tool runs show my-plan/2026-05-14T12-34-56-9f3a1c
```

Read the `phase_end.duration_ms` field to find the slow phase. Read
the `claude_call_end.duration_ms` for the slow call within that
phase. `claude_call_end.tokens_input` / `tokens_output` tell you
whether you spent more tokens or just waited longer.

**If a call you expected is missing**, look for this on stderr:

```
warning: claude call at <file>:<line> (phase='…') ran with no run-log
sink installed — its duration, tokens and cost are unrecorded.
```

`claude_call_end` events land only while a sink is installed, so a call
made outside one is spent but unrecorded — the log looks healthy and
under-reports. The warning fires **once per process** (naming the first
such call site); later unsinked calls in the same run are silent. Not
every unsinked call is a defect — some verbs legitimately run without a
log — but a missing phase you expected to see starts here. Which verbs
still lack a log is tracked in `BACKLOG.md` (#176–#178).

### 3. Diff today's run against a known-good one

When you have a baseline (yesterday's identical command):

```bash
plan-tool runs diff my-plan/<yesterday_run_id> my-plan/<today_run_id>
```

Per-phase delta table:

- Phases present in both runs sort to the top (alphabetical), then
  `only-in-A`, then `only-in-B`.
- **Large positive `Δwall`** on phases you didn't touch = regression.
- **Large positive `Δtokens`** on unchanged phases = prompt-template
  bloat regression.

### 4. Cross-check against the parse-failure archive

A spike in `claude_call_end.duration_ms` under the `per_step_body`
phase that includes more than one `claude_call_start` (attempt index
≥ 2) means the parse-retry loop fired. The `parse_failure` event
carries a relative path under `.plan-tool/parse-failures/`:

```bash
plan-tool runs show my-plan/<run_id> | grep parse_failure
# parse_failure phase=per_step_body attempt=1 failure_path=.plan-tool/parse-failures/my-plan/04-attempt1-2026-05-14T12-34-56.txt

cat .plan-tool/parse-failures/my-plan/04-attempt1-2026-05-14T12-34-56.txt
```

The raw model response is in that file; the run log carries only the
pointer (avoids duplicating multi-KB payloads across two on-disk
locations).

### 5. Clean up when you're done

Run logs accumulate; 30 days is the recommended retention cliff
(matches `.plan-tool/checkpoints/`'s `DEFAULT_MAX_AGE_SECONDS`).

```bash
plan-tool runs clear --older-than 30d # whole repo
plan-tool runs clear my-plan --older-than 7d # under one slug
```

`in-flight.json` is preserved by `--older-than` (using its mtime as
an age proxy would race the active writer); `plan-tool runs clear
<slug>` and `plan-tool runs clear --all` do remove it.

---

## Workflow: a seed that's too large or covers multiple plans

There is no seed size limit on `create --from-existing` (or `--from`). A
distill first-pass reads the whole seed and either reorganizes it into the
canonical body sections (single plan) or — when the seed describes several
independent efforts — proposes splitting it into multiple plans.

```bash
# Just create from the seed; distillation happens automatically.
plan-tool create my-slug --from-existing docs/big-draft.md -y < /dev/null
```

**When the seed is really multiple plans.** The distill pass returns a split
proposal instead of writing a plan. `create` prints the proposed plans
(title, slug, rationale, seed line range), saves a worksheet to
`<output-dir>/<slug>-split-proposal.md`, leaves the seed in place, and exits 0
(a split proposal is a success, not an error). Carve the seed into one file per
proposed plan using the printed `sed -n 'start,endp'` ranges, then run
`plan-tool create <slug> --from-existing <file>` for each.

**Skip distillation** with `--no-distill` to feed the raw seed straight to the
step/reference/body round-trips (a huge seed can then only fail via the model's
own context limit).

**Archival.** On the single-plan path the new plan supersedes the seed, so the
raw seed and the distilled artifact are archived beside it under
`<plan-dir>/archive/` (with the `.replaced` suffix). The split-proposal path
archives nothing — you still need the seed to carve from.

---

## Workflow: per-subcommand reconcile

Reconcile splits along the direction of truth. When the code on disk
is the source of truth and the plan should change to match, use
`plan-tool detail <name> --reconcile`. When the plan is the source
of truth and the code should change to match, use `plan-tool run
<name> --reconcile`. The subcommand IS the direction declaration —
the operator picks the verb up-front, the prompt and apply path do
the rest.

Four near-neighbors share the `reconcile`/`refresh` keyword; their
distinguishing axis is *when (and whether) a Claude call fires*:

| Verb | What it does | Claude call? |
|------|--------------|--------------|
| `reconcile-plan <name>` | Plan-vs-code audit that mutates the plan to match drifted code. | **Every run** (one call). |
| `reconcile-plan-walk <name>` | Replay a *saved* reconcile's findings interactively — runs no audit. | **None** (replays disk). |
| `reconcile-plan <name> --refresh` | Cheap fingerprint gate: reconcile **only** the drifted files, skip Claude on no drift. | **Only if code drifted.** |
| `create <name> --reprocess` | Fill `_(TODO)_` placeholders from an archived predecessor — nothing to do with code. | **None** (deterministic merge). |

One-line discriminator: **reconcile-plan = audit now; reconcile-plan-walk
= replay a saved audit; reconcile-plan --refresh = audit only if code
drifted; create --reprocess = fill placeholders from an archive.**

> **Code-grounded re-ground finding.** `reconcile-plan` now surfaces a
> plan-wide **re-ground** finding when **≥2 distinct steps** already appear
> implemented in the code (its unique code-centric signal — the plan's
> decomposition looks stale against HEAD). It is **advisory**, sourced
> `granularity-merge`, tallied in the `Findings:` banner, and **never flips
> the exit code**. The remedy is **re-ground / re-baseline** — mark the
> already-built steps `done`, or re-decompose — **not** a blind
> `plan-tool merge`: the flagged steps may be non-adjacent or already `done`,
> which `merge` forbids. Applying this finding in the review/reconcile walk
> actuates that mark-done for you via `plan_tool/reground.py:reground_bridge`
> (behind the walk's `--apply-structural` gate, or its per-remedy `--reground`
> opt-in) — you no longer edit `status:` fields by hand to re-baseline. Add
> `--reground-rebaseline` to also write a `create --from-existing` re-baseline
> seed alongside the mark-done. It is a low-confidence heuristic
> (superficial symbol overlap can false-positive), so confirm the steps
> really are built before re-baselining.

> **Code-grounded split finding.** `reconcile-plan` also surfaces a per-step
> **split** finding — the inverse of re-ground — when **one non-`DONE`
> step's** code reveals it fuses a built part (some of its declared files
> already appear implemented) and an un-built non-test part. It is
> **advisory**, sourced `granularity-split` at `info`
> (`review.py:_code_reveals_split_recommendations`), tallied in the
> `Findings:` banner, and **never flips the exit code**. It is
> **recommend-only** — it points at `plan-tool split <plan> --step N` and is
> **not** auto-applied (its `info` severity keeps it out of the
> `escalate_to_split` bridge, which dispatches only `medium` splits). Like
> re-ground it is a low-confidence heuristic (the built/un-built seam is a
> proxy, not proof), so confirm the step genuinely fuses two *separable*
> concerns before splitting.

### `detail --reconcile` — fix the plan to match the code

```bash
plan-tool detail my-feature --reconcile --step 3
plan-tool detail my-feature --reconcile --step 3 --no-walk # save only
plan-tool detail my-feature --reconcile --step 3 --no-save # neither save nor walk
plan-tool detail my-feature --reconcile --step 3 --iterate
plan-tool detail my-feature --reconcile --step 3 --iterate -y
```

Findings are **plan/detail edits** — `step.files` lists to trim or
extend, status flips (`done` → `current` / `blocked`), detail-body
updates. The audit is read-only with respect to the codebase. After
claude returns, findings are saved to
`<plan-dir>/plan-details/<plan-slug>/reports/<ts>-detail-reconcile.json`
(kind `"detail-reconcile"` in the JSON payload). When stdin is a
TTY, the CLI walks the recommendations interactively — same loop as
`plan-tool reconcile-plan`, same keys (`a` / `s` / `n` / `r` / `q`). Each
finding is dispatched through `apply_finding`.

The prompt context is intentionally plan/detail-edit oriented: it may
emphasize plan frontmatter, the detail body, and declared-file evidence
needed to repair the spec. It can carry different current-file excerpts
than `run --reconcile` for the same step because the target artifact is
the plan, not the implementation.

If the audit finds the code lags the plan (the right fix is in
code, not in the plan), the correct verb is `run --reconcile`, not
a plan-status flip.

### `reconcile-code` — fix the code to match the plan

Canonical form is `plan-tool reconcile-code <name>`; `run --reconcile` is the
kept legacy form.

```bash
plan-tool reconcile-code my-feature --step 3
plan-tool run my-feature --reconcile --step 3            # legacy form
```

Findings are **code edits**. They land inline via claude's
Edit/Write tools under `--permission-mode acceptEdits` — *not*
through `apply_finding`. Findings are saved to
`<plan-dir>/plan-details/<plan-slug>/reports/<ts>-run-reconcile.json`
(kind `"run-reconcile"` in the JSON payload). There is no
recommendation walk on this side; the loop is audit → land code
edits → re-audit when `--iterate` is set.

The prompt context is intentionally code-edit oriented: it may emphasize
the implementation excerpt and only enough plan/detail material to judge
the requested code change. That asymmetry is expected even when
`detail --reconcile` and `run --reconcile` discuss the same plan step.

If the audit finds the plan misnames a path or the step itself is
the wrong shape (the right fix is in the plan, not in the code),
the prompt emits a `## Redirect` sub-block instead of a code edit
— see below.

### `## Redirect` and the `[REDIRECT]` signal

Under `run --reconcile`, when a finding's root cause is in the plan
rather than the code, the prompt instructs claude to emit a
`## Redirect` sub-block naming `detail --reconcile` as the target.
The walk parses the redirect (`review.py: parse_redirect_block`) and
prints `[REDIRECT] step N — see detail --reconcile` on stderr. The
audit exits 0 either way — act on the `[REDIRECT]` line, not the rc.

Switch subcommands — do not retry. A redirect is the expected
signal that the operator picked the wrong direction of truth for
this finding.

### Triggering reconcile from inside review walk

When `plan-tool reconcile-plan <name>` walks recommendations and one suggests
running reconcile (e.g., the heuristic-already-done path), press `r`
during the walk to execute the suggestion. The walk:

1. Invokes `run_step` for that step under `detail --reconcile`.
2. Saves the reconcile findings as a separate `-detail-reconcile.json` artifact.
3. Walks the reconcile findings interactively (same prompts).
4. Returns control to the outer review walk when the inner walk
   finishes (or quits).

The outer review walk's progress is preserved — you'll be re-prompted
to mark the original recommendation `d` / `s` after the nested walk
ends. Quitting the inner walk with `q` returns to the outer walk; it
doesn't quit both.

This keeps the two concerns separated: `reconcile-plan` updates the plan's
authoring (paths, deps, completeness); `detail --reconcile` updates
the plan to match what code actually delivered; `run --reconcile`
updates the code to match what the plan asked for.

### Reusing a saved reconcile (`--reuse`)

The single claude call is the expensive half of every reconcile. When
neither the plan nor the in-scope code has changed since a prior reconcile,
re-running that call buys nothing, so the tool can reuse the saved sidecar's
findings instead — the reconcile analog of `completeness-audit`'s
[`--reuse-audit`](#reusing-a-saved-conceptual-audit---reuse-audit).

- **Applies to all three reconcile commands** — `reconcile-plan`,
  `reconcile-code`, and `detail --reconcile`. The `--reuse` / `--no-reuse` /
  `--reuse-id` family attaches to `p_review` (`reconcile-plan`),
  `p_reconcile_code` / `p_run` (`reconcile-code` / `run --reconcile`), and
  `p_detail` (`detail --reconcile`).
- **What's reused.** Only the single-claude-call reconcile axis. The
  deterministic primitives (file-existence, deps, path-style, the
  looks-already-done heuristic) run every invocation; reuse never weakens a run.
- **When reuse is offered.** Only when the newest **eligible** saved reconcile
  sidecar for that kind is **fresh** — its captured **plan fingerprint AND code
  fingerprint** both match current disk. The per-kind suffix differs:
  `reconcile-plan` writes a bare `<ts>.json` (kind `review`), `reconcile-code`
  writes `<ts>-run-reconcile.json`, and `detail --reconcile` writes
  `<ts>-detail-reconcile.json` — but on `reconcile-plan` the filename only
  *locates* a candidate. It loads each one newest-first and reuses only an
  ordinary-final `kind="review"` payload, skipping unreadable sidecars,
  pre-apply audit checkpoints, unknown roles, and other kinds; freshness is
  then judged once, against that newest eligible save.
- **The tri-state flag.** `--reuse` / `--no-reuse` is a `BooleanOptionalAction`
  whose **unset default prompts** on a TTY and auto-decides under `--yes` /
  non-TTY stdin. `--reuse` forces reuse-when-fresh; `--no-reuse` always
  re-audits; unset = ask. Unset is **not** off — pin the flag when you need a
  definite answer.
- **`--reuse-id STEM`.** Pins a specific saved sidecar by its filename stem
  instead of newest-wins. An unresolved id prints a note and falls back to a
  fresh audit. On `reconcile-plan` the pin is exact in both directions: an
  unreadable or ineligible sidecar declines with its own distinct reason and
  runs fresh — it never quietly reuses a different save.
- **Plan-stale decline.** A plan edit declines with a one-line staleness note on
  stderr; there's no per-file detail (the plan change is the operator's own edit).
- **Code-drift decline + attributed warning.** An in-scope **code** change (or a
  deleted / newly-landed in-scope file) declines and emits a per-file warning
  naming each drifted path with its owning step as `path (step N: title)`, closed
  by the `detail --reconcile` recovery hint. This warning shares the
  byte-for-byte shape of the live-edit drift warnings — both render through
  `render_attributed_path_line` / `reconcile_drift_hint` in
  `plan_tool/drift_detection.py`.
- **Exit code unchanged.** A staleness decline is never a failure — it falls back
  to a fresh audit and exits 0 (the failure-to-complete-only exit convention).

```bash
plan-tool reconcile-plan my-feature                  # prompt (TTY) / auto-decide (non-TTY)
plan-tool reconcile-plan my-feature --reuse          # reuse when fresh, no prompt
plan-tool reconcile-plan my-feature --no-reuse       # always re-audit
plan-tool reconcile-plan my-feature --reuse-id 20260505-123456
plan-tool reconcile-code my-feature --step 3 --reuse
plan-tool detail my-feature --reconcile --step 3 --reuse
```

### Refresh a stale plan against code (`reconcile-plan --refresh`)

`--refresh` answers a narrower question than a plain audit: *are the
plan's premises still valid against the code right now?* It gates on a
**code fingerprint** before spending anything, so on an untouched tree
it costs nothing.

Two outcomes:

- **No drift** — the plan's stored grounding baseline still matches the
  current code fingerprint. The command prints `✓ '<slug>' is still
  grounded …` and exits 0 having spawned **no Claude call** and rewritten
  nothing.
- **Drift** — a watched file changed. The command runs a reconcile
  **scoped to exactly the changed file(s)**, saves the findings for
  `reconcile-plan-walk`, and re-stamps the grounding baseline. Apply the
  saved findings with `plan-tool reconcile-plan-walk <name>`.

The **grounding baseline** is a tracked sidecar at
`<plan-dir>/plan-details/<slug>/grounding.json`, stamped after a
successful `create` / `detail`. A plan that has none (authored before the
feature, or a deleted sidecar) is treated as "needs grounding": the first
`--refresh` reconciles over the whole declared surface and writes a first
baseline so the next run's gate clears — it never crashes.

```bash
plan-tool reconcile-plan my-feature --refresh        # cheap gate: no Claude unless code drifted
```

Contrast the other three family verbs (see the table at the top of this
section): a plain `reconcile-plan` always spends one Claude call;
`reconcile-plan-walk` only replays a saved audit; `create --reprocess`
fills placeholder text from an archive and never looks at code.

---

## Workflow: completeness checks

Five verbs cover the audit-then-address pairs plus the lighter checks:

| Verb | Question | Cost |
| --- | --- | --- |
| `plan-tool validate <name>` | Is the frontmatter schema-valid? | Instant. Schema-only; never fails on body content. |
| `plan-tool reconcile-plan <name>` | Are paths/deps correct? Does claude have concerns? | One claude call. Includes correctness *and* completeness findings inline. |
| `plan-tool completeness-audit <name>` | Are there authoring gaps + conceptual coverage gaps (orphaned concepts, uncovered risks, …) that the detail bundle doesn't already resolve? | Deterministic checks instant; the conceptual audit samples claude until findings run dry (typically 2-3 calls; `--audit-samples` / `--audit-dry-rounds`). |
| `plan-tool completeness-apply <name>` | Address the conceptual gaps from a saved audit. | One claude call per gap addressed (interactive by default). |
| `plan-tool data-contract-apply <name>` | Address saved `DATA_CONTRACT.md` documentation drift from a saved audit. | Instant checks plus an interactive saved-finding walk; no claude call. |

`completeness-audit` is the lightest non-trivial audit. Run it after
authoring or mid-sprint to catch silent gaps the schema doesn't enforce:
body sections that still hold `_(TODO)_`, steps without detail files,
detail files whose `## Acceptance criteria` section drifted out of sync
with the implementation, and `done` steps that never landed an entry in
the configured `lessons:` log.

The conceptual layer is **grounded in the per-step detail bundle**: the
audit prompt embeds every step's detail file and may Read/Grep the repo
at HEAD, so a gap a detail file already specifies is not re-flagged.
Because one audit sample is non-deterministic, the layer is **sampled
until findings run dry** and unioned by stable anchor id — typically
2-3 claude calls (`--audit-samples` / `--audit-dry-rounds` tune the
cost/coverage trade; `--audit-samples 1` reproduces a single-call run).

```bash
plan-tool completeness-audit my-feature
plan-tool completeness-audit my-feature --json # for CI gating
plan-tool completeness-audit my-feature --audit-samples 1 # cheapest: one sample
```

With `--json`, inspect `stage` (`bare` | `detail`), `conceptual_bar_blocking_ids`,
bar-aware `has_blocking_findings`, and `audit_incomplete`. Schema details in
[`DATA_CONTRACT.md`](DATA_CONTRACT.md). `--fail-on-findings` keys off the stage
bar, not a flat severity floor.

The report is grouped by check kind (Body sections / Detail coverage /
Detail body completeness / Files coherence / Lessons coverage /
Test-strategy). Findings are advisory — `medium` for actionable gaps,
`info`/`nit` for hints.

`data-contract` findings appear in the same grouped report and in `--json`.
Applyable contract-document findings target `DATA_CONTRACT.md` and carry a
structured sidecar payload saved next to the completeness audit. Stale
plan/detail `## Input` contract references are different: those are repair
findings for the authored plan or detail file, not `DATA_CONTRACT.md` edits, so
`data-contract-apply` reports them as non-applyable.

The report also emits a `Smells (advisory)` section carrying **cross-step
granularity advice** from the granularity advisor: `granularity-split` (a
step that looks too big / mixes concerns) and `granularity-merge` (two
adjacent dependent steps that look fragmented). This whole-plan audit is
the **only surface that shows merge advice** — `create`'s change-type
loop surfaces only `granularity-split` (next to its `(s)plit` action) and
drops merge recs. Here in the completeness audit the merge advice is
advisory only; to actuate it, the review/reconcile walk folds the flagged
pair through `plan_tool/detail.py:merge_bridge` behind `--apply-structural`
(or its per-remedy `--merge` opt-in — the merge-directive dispatch,
recommend-only without either flag), while
`plan-tool merge <name> --steps ID --steps ID` (the
[Quick reference](#quick-reference) Authoring row) remains the hand-run
form. (The reconcile lane's code-grounded **re-ground** finding
reuses the same `granularity-merge` literal but is *not* this merge
advice: applying it in the review/reconcile walk actuates
`plan_tool/reground.py:reground_bridge` (mark done) behind the same
`--apply-structural` gate — see the reconcile callout above. The reconcile
lane likewise emits a code-grounded **split** finding reusing the
`granularity-split` literal at `info` — distinct from the advisor's static
split hint here, recommend-only, actuated by hand via `plan-tool split`.)
rc stays 0 —
granularity advice never gates (obeys the exit-code convention;
`--fail-on-findings` is the only way to flip rc, same as every other
advisory finding).

### Test-strategy alignment checks

When some steps carry a `change_type`, `completeness-audit` adds
deterministic `test-strategy` findings:

- a plan-level `info` nudge when some steps are classified and siblings
  aren't;
- a per-step `medium` when a `non-code` step's `files`/`creates` include
  a production source path (the declared type contradicts the footprint).

(The ordering-contract check this section once also listed — a `medium` when
a refactor step's detail `## Tests` described after-the-change testing — was
withdrawn 2026-07-30 along with the directive itself; see above.)

The sampled `plan-audit` conceptual pass adds a **purity probe** that
flags a code step mixing behavior-preserving restructuring with new
behavior (docs/config riding along is not mixing; the recommended fix is
splitting it into type-pure steps). Plans with no classified steps
produce none of these. See
[`PLAN_FORMAT.md`](PLAN_FORMAT.md#field-semantics) for the
classification.

### Reusing a saved conceptual audit (`--reuse-audit`)

The conceptual audit (`audit_plan_until_stable` — the minutes-each Claude
sampling) is the expensive half of `completeness-audit`. When neither the plan
nor the in-scope code has changed since a prior audit, re-sampling Claude buys
nothing, so the tool can reuse the saved sidecar's conceptual findings instead.

- **What's reused.** Only the conceptual axis. The deterministic battery
  (`_run_deterministic_checks` — body sections, detail coverage, deps,
  files-coherence, lessons) runs every time; reuse never weakens a run.
- **When reuse is offered.** Only when the newest **eligible** saved
  `-completeness.json` is **fresh** — its captured **plan fingerprint AND code
  fingerprint** both match current disk. Any plan edit or in-scope code change
  declines and re-audits.
- **What's eligible.** Only an ordinary **final** report. An `--iterate` run
  also saves a **pre-apply checkpoint** under the same `<ts>-completeness`
  names before its first apply; that sidecar is marked in its payload as
  crash-recovery evidence and is skipped for reuse, as is any sidecar whose role
  metadata is unrecognized or whose payload is not a completeness audit. See
  [`docs/how-to/pipeline/audit.md`](docs/how-to/pipeline/audit.md#pre-apply-checkpoint-vs-final-report--the-persisted-role).
- **The tri-state flag.** `--reuse-audit` / `--no-reuse-audit` is a
  `BooleanOptionalAction` whose **unset default prompts** under an interactive TTY
  and auto-decides (auto-accept) under `--yes`, `--json`, or non-TTY stdin.
  `--reuse-audit` forces reuse-when-fresh (winning even over an explicit
  `--audit-samples N`); `--no-reuse-audit` always re-audits; unset = ask. Unset is
  **not** off — pin the flag explicitly when you need a definite answer.
- **`--reuse-audit-id STEM`.** Pins a specific saved sidecar by its filename stem
  (the bare `<ts>` or full `<ts>-completeness` form, e.g.
  `20260611-123456-completeness`) instead of newest-wins. It stays an exact
  request: an id naming an ineligible sidecar supplies no findings and never
  falls back to an older report. An unresolved or ineligible id prints a note
  and runs a fresh audit.
- **Plan-stale decline.** A plan edit declines with a one-line staleness note on
  stderr; there's no per-file detail (the plan change is the operator's own edit).
- **Code-drift decline + attributed warning.** An in-scope **code** change (or a
  deleted / newly-landed in-scope file) declines and emits a per-file warning
  naming each drifted path with its owning step as `path (step N: title)`, closed
  by the `detail --reconcile` recovery hint. This warning shares the byte-for-byte
  shape of the live-edit drift warnings — both render through
  `render_attributed_path_line` / `reconcile_drift_hint` in
  `plan_tool/drift_detection.py`.
- **Stream split.** The reuse line, the plan-stale note, and the code-drift
  attribution all go to **stderr**; the grouped report goes to **stdout**. So
  `2>/dev/null` hides the reuse chatter but keeps the report.
- **Exit code unchanged.** A staleness decline is never a failure — it falls back
  to a fresh audit and exits 0 (the failure-to-complete-only exit convention). The
  warning is purely informational.

```bash
plan-tool completeness-audit my-feature                      # prompt (TTY) / auto-decide (non-TTY)
plan-tool completeness-audit my-feature --reuse-audit        # reuse when fresh, no prompt
plan-tool completeness-audit my-feature --no-reuse-audit     # always re-audit
plan-tool completeness-audit my-feature --reuse-audit-id 20260611-123456-completeness
```

### Address conceptual gaps (`completeness-apply`)

The audit's conceptual findings — both *correctness* (unsound or
contradictory design) and *completeness* (orphaned concepts, uncovered
risks, dangling acceptance criteria, missing edge-case concepts) — are
reported but **never auto-applied by the audit's iterate loop**
(read-only-audit split, #85). The iterate loop spends its apply budget
only on the deterministic well-formedness findings, which genuinely
converge; each conceptual gap is a judgment call and a fresh audit always
surfaces more, so an apply loop over them would never converge.
`completeness-apply` is the explicit, paired verb — the sole mutator of
the conceptual gap map — that walks **both** sources (correctness first,
then completeness) and applies gap-closing edits without re-running the
audit. When `completeness-audit --iterate` stops with **`terminal_hand_apply`**
(deterministic findings converged but the conceptual stage bar still blocks),
this is the intended next step.

```bash
plan-tool completeness-apply my-feature                  # interactive per-gap walk (the only mode)
plan-tool completeness-apply my-feature --anchor cache-invalidation
                                                          # address one gap by its [anchor-slug]
```

The walk is always per-gap and interactive — every conceptual gap is a
scoping judgment call, so there is no blanket auto-apply. On a
non-interactive stdin (CI / pipe) the walk is skipped, the pending gaps are
reported, and the command exits **2** — nothing was applied, so a script
must not read that run as convergence. (The deterministic files-coherence
fix is mechanical and runs unconditionally.)

**Faster on many gaps: `--jobs N`.** When a saved audit has several
independent gaps, the serial per-gap Claude round-trips dominate wall-clock.
`completeness-apply --jobs N` (N>1) applies up to N gaps concurrently, each in
its own isolated git worktree, then replays the results onto your tree in a
deterministic order (correctness first), re-running any gap whose file another
apply already touched:

```bash
plan-tool completeness-apply my-feature --jobs 4 -y   # up to 4 concurrent applies
```

`--jobs > 1` is **non-interactive** — it auto-applies every gap, so it requires
`-y` and a **clean working tree** (the isolation worktrees are cut off HEAD, so
uncommitted plan/detail edits would be invisible to the parallel applies;
commit or stash first). Because parallel applies can't see each other's
verdicts (degraded carried context), follow a `--jobs N` run with a serial
`completeness-apply` (no `--jobs`) or a `completeness-audit` re-verify for a
converged pass. A single `--anchor` gap has nothing to parallelize and degrades
to the serial walk.

Each finding in the saved report carries its anchor slug (e.g.
`` `[cache-invalidation]` ``) plus the exact `--anchor` invocation —
copy-paste from the report into the shell. The walker dispatches each
confirmed gap through `apply_finding` (the same Claude-driven prose
editor `reconcile-plan-walk` uses), so the propose-then-confirm flow is the
default: Claude proposes a diff, you keep or revert. After applying,
re-run `completeness-audit` to verify addressed gaps drop off — anchor
slugs are stable across re-audits, so a gap that comes back unchanged
either wasn't really addressed or the audit found a new sibling.

**Correctness always renders first.** If the plan also has structural
problems (path-style mismatch, blocked deps), those appear under a
"Correctness (run these first)" header above the completeness sections.
Fix structural blockers before chasing authoring gaps.

**Splitting a mixed step: `--apply-structural`.** When the audit saved a
`medium` `granularity-split` MIXED-STEP finding ("this step mixes a
behavior-preserving refactor with new behavior"), the serial walk can route
it to the
[escalate-to-split bridge](#the-escalate-to-split-bridge-auto-split-or-recommend)
instead of leaving you to edit the plan by hand:

- **`--apply-structural` is the opt-in.** With it, the walk dispatches the
  saved split finding through the bridge and, on a safe plan with an
  interactive confirm, *applies* the 1→2 refactor+feature split. Without
  it the finding is **recommend-only** — it prints the runnable
  `plan-tool split <plan> --step N --into "…" --into "…"` and touches
  nothing.
- **Recommend-only in every unsafe or unattended path.** No
  `--apply-structural`, under `-y`, in the `--jobs > 1` parallel lane, on
  an unsafe plan (a non-`PENDING` step at or after the target), or a
  declined / non-TTY confirm all recommend without mutating. Only the
  safe + opted-in + interactively-confirmed path writes the split.
- **Halt-on-applied.** An applied split renumbers every step from the
  target onward, so the other saved findings now name the wrong step; the
  walk **halts and tells you to re-audit** rather than applying stale-id
  edits — the same halt the walk-dispatch list documents for an applied
  merge under "Structural-directive findings".
- **No exit-code change; no Claude on the recommend-only path.** The split
  finding never flips `--fail-on-findings`, and when the walk only
  recommends it spends no Claude reaching that decision.

### Repair data-contract docs (`data-contract-apply`)

`data-contract-apply` is the documentation-repair pair for saved
`source="data-contract"` findings. Use it only after a `completeness-audit`
has saved drift for `DATA_CONTRACT.md`; it replays the saved structured
payloads and annotates the saved audit, rather than re-running detection or
guessing edits from the prose report:

```bash
plan-tool completeness-audit my-feature
plan-tool data-contract-apply my-feature
plan-tool completeness-audit my-feature   # verify the data-contract drift dropped off
```

The command verifies the saved registry and document fingerprints before
editing. If a payload is stale, rerun `plan-tool completeness-audit <name>` to
refresh the payload, then apply again. `completeness-apply` stays focused on
conceptual plan/detail gaps; when it encounters data-contract drift, it reports
or redirects rather than acting as a data-contract batch mode. For many saved
contract findings, walk them with `data-contract-apply` itself.

**Concurrent-editing hazard.** `data-contract-drift` and the two
`input-contract-references-*` checks resolve the code-owned contract
registry (`persisted_dataclass_contracts()`) by live attribute access
across nine modules (`concept_tree`, `review_persistence`, `run_log`,
…) each time `completeness-audit` runs. Running the installed
`plan-tool` binary against a repo *while another process has that same
working tree open for edits* can race an in-flight import against a
mid-write source file — a transient `AttributeError` naming a class
that exists and imports cleanly moments later on inspection. This
detector battery catches and reports that specific failure rather than
crashing the whole audit; the fix is to re-run the audit against a
quiescent tree, not to chase the reported class.

### When repeated audit/apply doesn't converge — re-decompose, don't keep patching

The intended authoring loop is a cycle:

```bash
# Repeat until a fresh audit returns no new correctness findings:
plan-tool completeness-audit my-feature --iterate   # surface findings
plan-tool completeness-apply my-feature             # walk + apply the conceptual gaps
#   …re-run the audit, fix the next batch, re-run again…
```

Each `completeness-audit` is a *sample*, not an enumeration — the
conceptual layer is Claude-driven, so one pass surfaces a subset of the
true finding set. Cycling audit → apply → re-audit is how you drive the
plan toward soundness: real progress looks like **the finding count
trending down and the surviving findings getting smaller** (HIGH →
MEDIUM → INFO), with no new HIGH appearing in a region you already fixed.

But watch for the **non-convergent signature** — it means the loop is
fighting the plan's *shape*, and no amount of further apply will fix it:

- **Findings keep reappearing in the same region** of the plan (one
  step, one paragraph) under new anchor slugs each run.
- **Each fix spawns the next finding in the same patch** — you close
  "the recommendation isn't surfaced," the next audit finds "the
  *null-recommendation* case isn't surfaced," then "it re-emits every
  iteration." Whack-a-mole, not convergence.
- **The plan body is growing with each pass** — `completeness-apply`
  closes a finding by *adding prose*, never by simplifying or
  restructuring (`apply_finding` edits text; it can't delete a concern,
  move it to another step, or re-decompose). A step whose paragraph keeps
  accreting clauses is over-packed, and the accretion is feeding the next
  audit more surface to find holes in.
- **A finding comes back `[BLOCKED]`** because the right fix is
  structural (split a step, author a new detail file) — the iterate loop
  has no move for that and can only report it.

When you see this, **stop applying and re-decompose.** The obstruction is
that an LLM prose-editor can fix *under-specification* but never
*over-complexity* or *mis-decomposition*. A deterministic `no_blocking_findings`
or iterate `converged` result does **not** mean the plan is clean for
completeness — the conceptual stage bar may still block via
`terminal_hand_apply`; see [`integrations/shared/DIRECTIVES.md`](integrations/shared/DIRECTIVES.md).
It also does not mean the plan is sound when remaining problems are
structural — a plan whose remaining problems are all structural will always
report converged prematurely on the deterministic iterate state.

The re-decomposition move — **first identify the hot region, then pick the
repair path that matches the failure's shape.** The two paths are not
interchangeable; the wrong one wastes work:

1. **Identify the hot region** — the step/concept every run keeps
   flagging. Then read its *spread*:
   - findings recur on a **single step** (that one step is doing too
     much), the rest of the plan is sound, **or**
   - findings spread **across steps** or concern inter-step shape (deps,
     ordering, a dead branch, two control-flow shapes merged) — the
     decomposition itself is wrong.

2a. **Localized over-pack → in-place re-split.** When it's one step,
    `plan-tool split <plan> --step N --into "<first>" --into "<second>"`
    (or interactive `detail --split`) bisects it and authors both halves'
    detail files, preserving the rest of the plan and any run state. Cheap;
    reach for it first when the spine is otherwise sound. The
    [escalate-to-split bridge](#the-escalate-to-split-bridge-auto-split-or-recommend)
    now surfaces this localized split automatically — recommending it on
    every `detail` authoring run and review/apply walk, and applying it on
    a safe interactive opt-in — so a recognized mixed step is often
    proposed for splitting before you reach for it by hand. The bridge
    handles only this one-step split; the cross-step re-seed fork (2b)
    stays manual.

2b. **Structural / cross-step → author a fresh seed and re-decompose.**
    When it's not one step, a 1→2 split can't fix it. Hand-write (or
    `annotate` into) a `create` seed that splits the hot step(s) into
    single-concern steps (one `change_type` each), pulls any scattered
    cross-cutting contract into its own step, and *defers any branch you
    can't name a live scenario for* rather than hardening dead wiring. Then
    **re-run `create --from-existing <seed> --iterate`** and `detail` per
    step. See the worked example in
    `plan-seeds/escalate-structural-findings-to-split-redecomposed.md`,
    which re-seeds a plan that took eight non-convergent audit cycles — its
    failure was cross-step (one over-packed step merging two triggers plus a
    likely-dead branch), so a re-seed, not a single split, was the fix.

2c. **Over-packed step that won't shrink → scope-out / defer.** When the
    hot region is one step that stays severe and *stops shrinking* —
    in-place patching is backfiring — re-splitting a third time won't help.
    The right move is to **carve that step out of the plan and defer it**
    (lift it into a forward-seed, let the rest of the plan converge, re-plan
    the carved work on its own):
    `plan-tool scope-out <plan> --step N` writes the carved step's
    `create --from-existing` forward-seed, then narrows the plan
    (recommend-only by default; `--apply` + a TTY confirm to mutate;
    seed-first). For a contiguous multi-step band, use the range form
    `--step N --through M`, carving the whole region into one seed. See
    [Carve an over-packed step out of a plan](#carve-an-over-packed-step-out-of-a-plan-plan-tool-scope-out)
    for the full gate.

The fresh, smaller steps converge because each is small enough for the
prose-editor to actually complete. Use `plan-tool convergence` to read
loop health from saved report history (three-state verdict + advisories);
pick split / scope-out / re-seed by judgment from the signatures above —
see [Diagnosing convergence with `plan-tool convergence`](#diagnosing-convergence-with-plan-tool-convergence).

Rule of thumb: **three audit/apply cycles in the same region with no
shrinkage is the signal to re-plan, not to patch a fourth time.**

### Diagnosing convergence with `plan-tool convergence`

`plan-tool convergence <name>` reads a plan's saved completeness/reconcile
report sidecars and reports whether the audit/apply loop has enough history
to look healthy. It is diagnose-only: it does **not** recommend or actuate
`split` / `scope-out` / re-seed (those stay on their own commands, chosen by
operator judgment from the re-decompose section above).

```bash
plan-tool convergence my-feature
plan-tool convergence my-feature --grade jira   # match a jira-grade completeness-audit
```

It spends **zero Claude**, writes no run-log entry, mutates nothing, and
**always exits 0** — there is no `--fail-on-findings` and no `--min-runs`.
`--grade` selects which detail bundle resolves the plan's bare/detail audit
stage — match whichever grade `completeness-audit` was run at, or the two
commands can disagree about a plan audited only at jira grade.

It prints a three-state headline:

- **`no-history`** — no completeness/reconcile reports saved yet.
- **`insufficient-history`** — some runs, but fewer than the 3-audit
  window the certificate needs.
- **`converging`** — the loop looks healthy on the available history
  (no re-decomposition signal from this diagnostic).

Below the headline it prints a per-series breakdown. On any verdict, three
newest-run advisories may ride alongside without changing the headline:

- **`latest_blocking`** — unresolved critical/high findings in the newest
  audit (run-readiness: resolve them before running; see the saved report).
- **`code_drift`** — the code fingerprint moved under the plan since the
  prior run (rebase with `plan-tool reconcile-plan`, then re-audit).
- **`finding_churn`** — same-kind open count and severity ceiling both rose
  across the latest two audits of that kind (findings are churning without
  recurring; measure the source before another iteration — not a
  re-decomposition signal). Uses the same stage-differentiated conceptual
  bar `completeness-audit` uses (see docs/how-to/pipeline/audit.md § "Stage bar and
  mid-run steering"), not a blanket medium+ floor — a medium conceptual
  finding the audit would demote at the plan's resolved stage doesn't count
  as open here either.

**The four structural remedies, as one model.** Split, scope-out, merge /
re-ground, and re-seed are one `split`/`merge` axis parameterized by
**altitude** (a *step* → two siblings, vs the *plan's scope* → a narrowed
plan + a carved-out remainder) and **disposition of the carved side**
(kept as a sibling step, vs carved out to a forward-seed). Choose among
them by judgment when the re-decompose signatures fire; `convergence`
does not auto-pick:

- **re-split** — step-altitude split, both halves kept →
  `plan-tool split <plan> --step N --into "…" --into "…"`.
  `reconcile-plan`'s code-grounded split finding (`granularity-split` at
  advisory `info`) recommends that same line — recommend-only, never
  auto-applied. The escalate-to-split bridge also surfaces it on
  detail/review/apply walks.
- **scope-out** — plan-scope split, carved side deferred to a forward-seed;
  triggered local (one over-packed step) but acts at plan scope →
  `plan-tool scope-out <plan> --step N` (recommend-only; `--apply` to
  mutate), or the range form `--step N --through M` to carve a contiguous
  `N..M` region into one seed. Standalone only — not actuated from
  `convergence`.
- **merge / re-ground** — the inverse of split. A pairwise
  `granularity-merge` merge finding now has a bridge: the review/reconcile
  walk folds the flagged pair through `plan_tool/detail.py:merge_bridge`
  behind `--apply-structural` (recommend-only without it), while
  `plan-tool merge <plan> --steps ID --steps ID` remains the hand-run form.
  For reconcile's already-built re-ground finding, re-baseline a ≥2-step
  set — the walk actuates that via `plan_tool/reground.py:reground_bridge`
  (mark done) behind the same flag, distinct from `merge` by directive kind.
  `--merge` / `--reground` are the per-remedy opt-ins that narrow
  `--apply-structural` to a single bridge, and `--reground-rebaseline` makes
  an applied re-ground also write a `create --from-existing` re-baseline seed
  (mark-done stays the default disposition).
- **re-seed** — the limit, split everything / restart →
  `plan-tool create <slug> --from-existing <seed.md> --iterate`.

A plan is narrowed only through `scope_out_step`'s `--apply` + TTY-confirm
gate on `plan-tool scope-out … --apply`.

### See a plan's split criteria (`plan-tool split-criteria`)

`plan-tool convergence` answers *is this loop's history looking healthy?*;
`plan-tool split-criteria` answers the companion question *which criteria
decided this plan's shape?*. Run it two ways:

```bash
# No argument → the plan-independent legend: every split criterion the tool
# applies across the three altitudes, plus the remedy vocabulary.
plan-tool split-criteria

# A plan name → the per-plan breakdown: which criteria fire, on which steps,
# with a one-line reason each.
plan-tool split-criteria my-feature
```

Like `plan-tool convergence` and `plan-tool status`, it is a read-only
diagnostic — it spends **no claude**, mutates nothing, writes no run-log
entry, and criterion findings do not change its exit code. Input-resolution,
parsing, and unsupported-detail-format errors still exit non-zero.

### Carve an over-packed step out of a plan (`plan-tool scope-out`)

When an over-packed step (or contiguous band) won't shrink under
audit/apply — the scope-out / defer path of
[the re-decompose section](#when-repeated-auditapply-doesnt-converge--re-decompose-dont-keep-patching)
— `plan-tool scope-out` is the carve tool. It carves that step out of the
plan into a `create --from-existing` forward-seed and narrows the plan, so
the rest converges and the carved work is re-planned on its own. It spends
**no claude** — both halves are deterministic. `plan-tool convergence` does
not recommend or actuate this carve; pick the step (or range) yourself.

```bash
# Preview (recommend-only): show the would-be carve, write nothing.
plan-tool scope-out my-feature --step 4

# Actuate interactively: write the seed + narrow the plan after a TTY confirm.
plan-tool scope-out my-feature --step 4 --apply

# Actuate unattended: the deliberate second opt-in, no TTY confirm.
plan-tool scope-out my-feature --step 4 --apply -y

# Carve a contiguous region: the inclusive N..M range into ONE seed.
plan-tool scope-out my-feature --step 2 --through 4 --apply
```

`--through M` carves the inclusive `N..M` region (from `--step N`) as a
single carve — one `create --from-existing` seed for the whole region, one
atomic narrow. The CLI rejects an out-of-order range (`--through` before
`--step`). `--step N` alone stays the single-step carve.

- **Recommend-only by default.** Without `--apply` the command previews the
  carve and writes nothing. `--apply` is the opt-in to mutate, and it still
  asks for an interactive confirm first; `-y` is the deliberate second
  opt-in that bypasses the confirm for scripted/unattended runs.
- **Seed-first ordering.** The `create --from-existing` forward-seed is
  written to `plan-seeds/` **before** the plan is narrowed, so the carved
  work survives as a durable artifact even if the narrow rolls back. The
  narrow itself is all-or-nothing: drop the step, renumber survivors to
  `1..N`, repair `depends_on`, and migrate/archive the carved detail file,
  with a rollback if any part fails.
- **Four refusal blockers** (each refuses with no write):
  - **inbound-dependent** — a surviving step still `depends_on` the carved
    step.
  - **downstream-orphan / non-canonical-numbering** — a downstream
    non-`PENDING` (run-started or `done`) step would be renumbered by the
    drop, so the carve would rewrite committed run state.
  - **empty-plan** — the carved step is the last committed step, so the
    narrowed plan would be permanently dead.
  - **step-missing** — no step with that id is in the plan.
  On any blocker, re-seed and re-decompose the whole plan instead
  (`plan-tool create <slug> --from-existing <seed.md> --iterate`; `annotate`
  can forward-seed it).
- **Post-carve history caveat.** The saved completeness/reconcile report
  sidecars keep their **pre-carve** step numbering after a narrow, so a
  `plan-tool convergence` read taken immediately after a carve can
  mis-attribute prior findings to whichever survivor now holds a
  renumbered id. Run a fresh completeness/reconcile pass over the narrowed
  plan to re-ground the history before trusting a post-carve
  `convergence` verdict.

### Suppressing a body-section finding

If a section legitimately doesn't apply to the plan, suppress with an
HTML comment marker:

```markdown
## Risks

<!-- completeness:skip Risks -->
```

The marker is matched case-insensitively against the section name and
suppresses both `missing` and `placeholder` findings for that section.
Other completeness checks don't honor the HTML-comment marker —
files-coherence drift has its own endorsement mechanism (see below);
the rest require fixing the underlying condition.

### Near-miss filtering (why most citations don't flag)

A detail body legitimately backtick-cites many files the step *reads*
but never *modifies* — inputs it produces from, downstream consumers,
anchors to verify against. `step.files:` is the **edit** set, not the
mention set, so "cited but not declared" is the normal case. Flagging
one finding per such path floods the report (a single 5-step plan
produced ~30–45 of them), burying the findings that matter.

So `check_files_coherence` only emits a `detail_only` finding when the
cited path is a **near-miss of a declared path** — a likely typo or a
stale/moved path the author forgot to re-sync, rather than an arbitrary
context reference. A path qualifies as a near-miss when:

- it has the **same basename as a declared file but sits in a different
  directory** — and the basename isn't ubiquitous (`index.ts`,
  `__init__.py`, `main.go`, `README.md`, … — see `_GENERIC_BASENAMES`
  in `review.py`). Canonical case: `files: [packages/web/Foo.tsx]` but
  the detail cites `apps/web/src/Foo.tsx`.
- **or** its full path string is ≥ 85% similar to a declared one
  (`_NEAR_MISS_RATIO`), catching a typo *inside* the basename
  (`Fooo.tsx` vs `Foo.tsx`).

Everything else — `amplify/backend.ts` cited by a step that only edits
`docs/secrets-and-parameters.md`, two unrelated `index.ts` files, or a
genuinely distinct neighbor like `apps/bar.py` next to a declared
`apps/foo.py` — is a context reference and produces **no finding**.
There's no flag to widen this; the lever is the data (declare the file
in `files:`, or endorse it in `allowed_mentions:`). The finding names
the near-match target so it reads *"detail cites `X` resembling declared
`Y`"* — actionable as either a path fix or an endorsement.

### Endorsing a near-miss citation with `allowed_mentions`

When a near-miss finding is a *false* alarm — the look-alike path is an
intentional context citation, not drift — endorse it so the check stays
silent. (After near-miss filtering this is rare: ordinary context
citations no longer flag at all, so `allowed_mentions` is now only
needed for the residual same-basename look-alikes.) The mechanism is a
plain frontmatter list — no CLI flag, no comment marker:

```yaml
steps:
  - id: 3
    title: Build the parser
    files:
      - plan_tool/parser.py
    allowed_mentions:
      - plan_tool/schema.py # cited for context; not edited
      - tests/test_parser.py # sibling test referenced for tone
    detail: plan-details/my-plan/03-build-the-parser.md
```

The reviewer (`check_files_coherence` in `review.py`) treats
`files: ∪ allowed_mentions` as the recognized path set — citations
into that union are silent.

Remaining `INFO` findings are the near-misses that survived filtering:
a path that closely resembles a declared file but isn't recognized is
more likely a typo or stale reference than a coincidence, so it
surfaces at `info` severity — advisory, not a failing gate.

When to reach for `allowed_mentions:`:

- The detail cites lines *this* step builds on (e.g. *"this step
  extends the validator at `schema.py:40-50`"*) — the file isn't
  edited; the citation is the design context.
- The detail names a sibling test for tone (*"see
  `tests/test_parser.py:120-160` for the convention this step's tests
  follow"*).
- The detail names a downstream caller affected by the change
  (*"`callers.ts:45` consumes this; verify the contract still holds"*).

When NOT to reach for it:

- The step actually edits the cited path — that belongs in `files:`,
  not `allowed_mentions:`. Overlap is harmless (the union dedupes)
  but `plan run --mode check` and `jira` consume `files:` only, so
  the edit needs to be declared there.
- The citation is a typo or rotted reference — leave the `INFO`
  surface and fix the citation. Endorsing a stale path hides drift.

See [`PLAN_FORMAT.md` → field semantics](PLAN_FORMAT.md) for the
schema entry and validation behavior. The pydantic model rejects
the singular `allowed_mention` (via `extra="forbid"`) so typos fail
schema validation rather than silently dropping.

### Deep verification (`verify --deep`)

Standard `verify-all` runs reconcile per done step and rolls up the Findings
block. `--deep` adds a second pass: for each done step's detail-file
acceptance bullets, render `prompts/reconcile-deep.md` and ask claude
"does the codebase satisfy *this specific* bullet?". Output is one
PASS / FAIL / UNKNOWN per bullet.

```bash
plan-tool verify-all --rollup my-feature --deep
plan-tool verify-all --rollup my-feature --deep --max-steps 1
```

Per-step rollup with `--deep`:

- Any `FAIL` bullet → step `fail` (overrides the reconcile verdict).
- All `PASS`, no `UNKNOWN` → step `pass`.
- Mixed `PASS`/`UNKNOWN`, no `FAIL` → step `warn`.
- Step has no parseable acceptance bullets → reconcile verdict stands;
  no override.

Cost: N done steps × (1 reconcile + M acceptance bullets) claude calls.
Use `--max-steps` to cap per-run cost when iterating.

### First-run rollout

Plans authored without complete coverage surface findings on the next
`reconcile-plan` / `completeness` invocation: missing body sections, steps
without detail files, lessons gaps.

- All findings are advisory (`medium` or below).
- `validate` stays schema-only — CI gates that depend on it don't
  break.
- Backfill the gaps, or use the suppression marker for sections that
  don't apply.

---

## Workflow: consolidate lessons files

Lessons files accumulate near-duplicates and the occasional outright
contradiction as iteration sessions append to them. `plan-tool lessons
consolidate` scans the three lessons scopes plan-tool maintains —
the per-user `~/.plan-tool/lessons/general.md`, the per-repo
`<repo-root>/.plan-tool/lessons/project.md`, and every per-plan
`lessons.md` resolved through a plan's `lessons:` frontmatter — for
duplicate and conflict findings. The posture is **fail-safe: it diffs
by default and never touches disk**; only `--apply` rewrites, and only
duplicates drive a removal (conflicts are surfaced for manual editing,
never auto-removed). See
[README.md → Lessons consolidation](README.md#lessons-consolidation)
for the conceptual overview.

### Default flow

```bash
plan-tool lessons consolidate                # 1. scan + diff (no writes)
plan-tool lessons consolidate --plan my-plan # scope to one plan's lessons.md
plan-tool lessons consolidate --apply        # 3. rewrite (confirms on a TTY)
```

1. `plan-tool lessons consolidate` — scans every discovered lessons
   file and prints a recurrence-weighted summary plus a unified diff
   of the proposed cleanup. Nothing is written.
2. Review the diff and the summary. Findings re-flagged across prior
   sessions sort first and carry a `recurrence=N` annotation (read
   from `.plan-tool/lessons-warnings.jsonl`); pass
   `--ignore-recurrence` to see the raw primitive order, or
   `--min-confidence 0.9` to require higher equivalence confidence
   before a duplicate drives a drop.
3. `plan-tool lessons consolidate --apply` to rewrite behind the Y/N
   confirmation gate, or hand-edit the lessons file directly when the
   conflicts need a judgement call the tool won't make.

### Headless

```bash
plan-tool lessons consolidate --apply -y < /dev/null
```

`--apply` against a non-TTY refuses to rewrite unless `-y` is passed —
without it the command exits non-zero so a scripted run fails loudly
rather than silently skipping the rewrite (the same non-TTY contract
the rest of the mutating subcommands follow). The default diff-only
mode is always safe headless and never needs `-y`.

### Recovery: I applied a bad consolidation

`plan-tool lessons consolidate` keeps no backup of its own beyond what
git already tracks. To undo a rewrite, `git checkout` the affected
lessons file — there is no `--undo` flag. Run the default diff mode
first whenever you're unsure; that's what it's for.

### See also

- [README.md → Lessons consolidation](README.md#lessons-consolidation)
  — the conceptual overview, the opt-in `strict_check` / `warn_check`
  write-path hooks, and the recurrence-weighting cap.
- `tests/test_lessons.py` and `tests/test_cli.py` — the regression
  pins for the equivalence primitive, the `append_lessons` hooks, and
  the `lessons consolidate` handler; start here to extend the workflow.

---

## Workflow: run a plan on its own branch (branch-awareness)

**Branch-awareness ships OFF.** Enable it per-repo in `.plan-tool/config.json`
as `{"branch_awareness": {"enabled": true}}` (or set
`PLAN_TOOL_BRANCH_AWARENESS=1`); with it off — every repo today — `run` and
`create` behave exactly as before. Until it's enabled, `attach-branch` /
`detach-branch` refuse with a non-zero exit and `run --switch-branch` is inert.

When on, a registered plan's branch is **derived from its slug** —
`<primary-prefix><slug>`, default `plan/<slug>`. The primary (first) configured
prefix names the branch; all configured `branch_prefixes` are accepted when
matching, so a dev who used a secondary prefix is still recognized.

### Enable it

```bash
# Project-wide (committed alongside the repo):
#   .plan-tool/config.json → {"branch_awareness": {"enabled": true}}
# Or per-shell, no file:
export PLAN_TOOL_BRANCH_AWARENESS=1
```

### Attach / detach an ad-hoc branch

```bash
plan-tool attach-branch my-feature feature/my-feature   # bind to an arbitrary branch
plan-tool detach-branch my-feature                      # clear the override
```

- `attach-branch` records the binding in **untracked local git config**
  (`plan-tool.binding.<slug>`) — machine-local, never committed. Binding to a
  name another registered plan owns by convention strong-warns and, on consent
  (`-y` / interactive yes) with a clean tree, **re-homes** the plan onto its own
  branch; binding to another plan's *ad-hoc* branch is a hard refuse.
- `detach-branch` clears the override and is a quiet no-op when nothing was
  bound. Neither command touches the branch on disk.

### What `run` does per branch tier

With branch-awareness on, `run` classifies the current branch and reacts:

- **Owned by this plan** — proceeds.
- **Owned by another plan** (ad-hoc or convention) — blocks; switch branches or
  re-home first.
- **Orphan pattern** (looks like a convention branch, nobody local owns it) —
  warns and proceeds.
- **Unowned** — nudges toward the plan's expected branch; pass
  `run <name> --switch-branch` to create-if-missing + switch to it on a clean
  tree (refuses on a dirty tree).

### Create-time namespace-collision warning

When branch-awareness is on, `create` warns if the slug's derived branch
collides with a branch another plan already owns, and offers to cut a
disambiguated branch **from the default branch**. The default is resolved via
`origin/HEAD` (or `PLAN_TOOL_DEFAULT_BRANCH` when set). On a local-only repo
with no `origin/HEAD` and no `PLAN_TOOL_DEFAULT_BRANCH`, the default is
undeterminable, so disambiguation is **skipped with an info note** — set
`PLAN_TOOL_DEFAULT_BRANCH` to restore it.

---

## Workflow: run plans in parallel (worktrees)

A `create` / `detail` / `run` on one plan holds the repo's single index,
branch, and checkout for the duration. When you want several plans making
progress at once, give each its own **isolated working copy** with the
`worktree` command group. A worktree is the natural home for a plan's
branch — it pairs cleanly with branch-awareness above.

### Provision

```bash
plan-tool worktree add my-feature          # provision (or reuse) the plan's worktree
```

- The bare command works on a **local-only repo with no remote** — the
  branch is born inside the `add` off `HEAD` when there's no default
  branch to resolve.
- On success it prints a `cd <path>` hint; the workspace lands at
  `<repo-parent>/<repo-name>.worktrees/<slug>` by default (override with
  the `worktree_base` config key — see the caveats).
- Re-running `add` on a **healthy** existing workspace of the expected
  kind and branch **reuses** it (idempotent) and reprints the `cd` hint;
  a foreign / wrong-branch directory at the path is refused, not
  overwritten.
- **Up front:** if the plan's `.md` or its `plans.json` manifest entry
  isn't committed on the worktree's base branch, the plan won't resolve
  inside the new worktree ("plan not found") — commit the plan on the
  base branch before (or right after) provisioning.

### Run concurrently

```bash
cd ../my-repo.worktrees/my-feature
plan-tool run my-feature --all --commit     # runs against this worktree's checkout
```

Per-cwd discovery (`locator.py`) resolves *this* worktree's manifest, and
each worktree keeps its own untracked `.plan-tool/` caches (run logs,
checkpoints), so two plans' runs never collide.

### Inspect

```bash
plan-tool worktree list
```

Reports `kind` (worktree / clone) / `branch` / `path` / `state`
(clean / dirty) for every registered plan that has a workspace on disk.

### Tear down

```bash
plan-tool worktree remove my-feature          # delete this plan's worktree (clean tree)
plan-tool worktree remove my-feature --force  # delete even a dirty worktree
plan-tool worktree prune                      # sweep dead (deregistered / path-gone) worktrees
```

- `remove` / `prune` refuse a **dirty** worktree without `--force`;
  `prune` **surfaces** a dead-but-dirty worktree (pointing you at
  `remove --force`) and never silently deletes it, even under `-y`.
- **`remove` / `prune` delete the worktree directory but never the
  branch** born inside the `add`. Clean the branch up the normal git
  way once you're done: `git branch -d my-feature` (or the derived name).
- **A `--clone` workspace is never deleted by `remove` or `prune`** —
  they print a manual-cleanup message and leave it in place. A clone is
  an independent repo whose commits (possibly committed-but-unmerged)
  live only in its own `.git`, which the uncommitted-only dirty gate
  can't see, so plan-tool won't delete it for you. After confirming no
  unmerged commits, remove it by hand: `rm -rf <path>`. `list` keeps it
  visible until you do.

### Worktree vs `--clone`

```bash
plan-tool worktree add my-feature --clone
```

The default and recommended path is a git **worktree**: it shares the
repo's object store, remote, and config, so it's cheap. `--clone` opts
into a full standalone **clone** — an independent repo that duplicates
the object store, remote, and config. Reach for it only when a run needs
total isolation from the shared `.git`.

### Caveats

- **Don't change `worktree_base` while workspaces exist.** The per-slug
  path is re-derived from the base on every `list` / `remove` / `prune`.
  Move the base and those verbs look at a *different* location, so they
  can no longer find already-provisioned workspaces — worktrees survive
  (git's own registry still tracks them), clones do not. Re-provision
  after any base change.
- **Don't `git gc` aggressively across parallel runs.** Worktrees share
  `.git/objects`; an aggressive `gc` while other runs are live can
  disturb their objects.
- **Plans are per-branch.** A plan resolves inside a worktree only when
  its `.md` and manifest entry are committed on that worktree's base
  branch.

---

## Recovery: common failures

### "no plan matching '<name>' among registered plan entries"

Cause: the plan isn't in `.plan-tool/plans.json`, or the manifest entry
points to a path that doesn't exist under the resolved repo root.

Fixes (in order of likelihood):

1. **Newly-created plan but not auto-registered** — shouldn't happen
   with `create`/`create --from-existing`; if it does, edit the
   manifest:

   ```json
   {
     "plans": [
       "implementation-plans/1-existing.md",
       "implementation-plans/3-my-new-plan.md"
     ]
   }
   ```

2. **Manifest path doesn't resolve under repo root.** Run
   `plan-tool list` — entries with no on-disk file emit a warning
   listing the absolute path tried, plus a `if no longer needed,
   remove "<entry>" from <manifest-path>` line. If the path is wrong,
   fix the manifest entry; if the file is genuinely gone, follow the
   suggestion. If the resolution is wrong, see "Wrong repo root"
   below.

3. **Slug/filename typo.** `plan-tool list` shows the canonical slug
   for every registered plan.

A *registered* plan whose frontmatter is broken no longer falls through
to this error — it resolves and surfaces as a `MALFORMED` row / `INVALID:`
verdict instead. If a plan you know is in the manifest "vanished," see
[Malformed frontmatter](#malformed-frontmatter) below.

### "Plan-wide path issue" diagnostic dominates the review

Cause: ≥80% of the plan's declared file paths don't resolve under the
repo root that plan-tool picked. Almost always means the plan was
authored against a different repo root than the one walk-up to `.git`
finds.

Fix:

```bash
plan-tool --repo-root <correct-root> review my-feature
```

Or set persistently:

```bash
export PLAN_TOOL_REPO_ROOT=/path/to/project
plan-tool reconcile-plan my-feature
```

The diagnostic itself names two or three example offending paths, so
you can verify the override fixed the issue by re-running.

### Per-step `MISSING_PARENT` warnings without the top-level diagnostic

These surface from the `run` pre-flight, or from `plan-tool reconcile-plan
<name> --no-allow-missing-parent` — `reconcile-plan` allows missing parents by
default and won't emit them otherwise.

Cause: a few specific paths are wrong (typo, moved file, stale path).
The full plan-wide threshold isn't crossed, so it's a per-file issue.

Fix: read the WARN line — it shows the abs path it expected and the
missing parent. Update the step's `files:` entry to the real path, or
move the file into place if it's a creation step.

### Wrong repo root detected

Symptom: every path in the report shows a doubled directory like
`<root>/.agents/.agents/...`, or a clearly-bogus root in the suggestions
block.

Cause: usually a nested `.git` directory inside plan-tool's parent
folder (e.g. `.agents/.git` alongside the project's `.git`), so the
walk-up stops at the inner repo.

Fix: pin the repo root explicitly:

```bash
plan-tool --repo-root /path/to/project <subcommand> ...

# Or persistently:
export PLAN_TOOL_REPO_ROOT=/path/to/project
```

### Malformed frontmatter

Symptom: `plan-tool list` shows the plan with a `MALFORMED` value in its
`STATUS` column, followed by an indented `error: <error>` continuation
line (and a `N plan(s) failed to validate` footer), or `plan-tool
validate <name>` prints `INVALID: <path>` with the error. Ordinary
malformed frontmatter exits 0 by default (`--fail-on-findings` flips
that) — the `INVALID:` line is the verdict, not the exit code, unless
the plan declares an unsupported `format_version`: that one named case
still prints `INVALID:`, but `validate` exits 1 unconditionally, because
this build cannot safely interpret the declared format at all. A
registered plan with broken frontmatter is surfaced here, not silently
dropped — a plan that "disappeared" from `list` after a hand edit is
found under this entry.

The `MALFORMED` / `INVALID:` signal fires for **both** malformed kinds:

- **Unparseable frontmatter** — invalid YAML, a missing or unbalanced
  `---` fence, or non-mapping frontmatter; `parse_plan` raises a
  `ParseError` before schema validation and the `error` is the parse
  message.
- **Schema-invalid frontmatter** — parses as YAML but violates the
  schema; the `error` is the field-level validation message.

Fix: open the plan, fix the YAML. The validator points at the field.
Common offenders:

- The **YAML colon-in-title trap** (the most common parse failure): a
  bare colon-space (`: `) inside a plain scalar, e.g. `title: a: b`,
  which YAML reads as `mapping values are not allowed here`. Fix by
  quoting the value (`title: "a: b"`).
- Schema violations: `priority` not in `high|medium|low`, duplicate step
  ids, `depends_on` referencing a nonexistent step id, two steps marked
  `current`.

After the fix:

```bash
plan-tool validate my-feature # confirm
plan-tool status my-feature # double-check
```

### Step exited non-zero — plan not advanced

Expected. The launcher refuses to advance state when claude exits
non-zero. Fix the underlying issue (read the step's stdout/stderr
above the launcher message), then re-run:

```bash
plan-tool run my-feature --step <same-id>
```

The step is still `current` from the failed attempt; explicit `--step`
isn't required, but it's clearer.

### Step failed with uncommitted edits left in the tree

Symptom: on the streaming `run` path a step aborts and the launcher
surfaces a terminal failure that names uncommitted edits — either the
partial-mutation hint (a transient or rate-limit failure whose aborted
turn had already written files, so the retry was **refused** rather than
re-driven over the dirty tree), or the generic non-zero-exit hint (a
transient past its backoff budget, or a second rate-limit, that went
terminal *without* a retry but still left partial edits). Either way the
recovery below applies to **any** terminal step failure that left
uncommitted edits.

Why: re-driving the same prompt over a partially-mutated tree can
double-apply the aborted turn's edits (a function/import added twice) and
corrupt the committed diff, so the guard stops instead. This is the
intended response-A behavior, not a regression — resolve the tree
yourself; there is no auto-recovery.

Recover — first inspect, then pick a branch:

```bash
git status          # what the aborted turn left
git diff            # the actual partial edits
```

- **Revert and re-run (the default).** An aborted turn's edits are
  usually *incomplete*, so discard them and let the step run cleanly:

  ```bash
  git restore .       # or: git checkout -- .  — reverts *modified* files only
  git clean -f        # remove newly-created files; restore/checkout leave
                      # untracked files in place, and the guard counts them
  plan-tool run my-feature --step <same-id>
  ```

  **Do not commit-then-re-run, and do not re-run without reverting
  first.** A bare re-run snapshots the leftover partial edits into its
  own retry baseline, so the guard no longer catches them and the
  re-drive double-applies (the re-guard-after-`STOP` known limit) —
  reverting is what resets the baseline. A **`--commit`** run's
  clean-tree preflight refuses to start over a dirty tree, so the silent
  re-baseline can only bite a `--commit`-less bare re-run; that is
  exactly where reverting first is load-bearing.

- **Accept as complete (only if inspection confirms it).** If the
  partial edits genuinely constitute the finished step, **do not re-run**
  — re-running would re-drive them. Instead commit the edits, then run
  `plan-tool run <slug> --step <id> --accept`: it runs the plan's
  `test_command` and the step's `gate`, and only when they pass marks the step
  `done` and promotes the next one.
  Reserve this for a turn that aborted *after* completing the work; it is
  the exception, not the default.

### `--iterate` exhausted the iteration budget

Symptom: the run exits 0 but the final stderr line names a
`budget_exhausted` stop (e.g. after 3 iteration(s) / 300s) rather
than `converged`; the artifact on disk is the last iteration's
output and findings may still be open.

Cause: the loop hit either `--max-iterations` or
`--iteration-budget` without converging. Either claude keeps finding
new issues each pass, or the issues themselves keep introducing
regressions on the next iteration.

Fix in this order:

1. **Inspect the last iteration's findings** — re-run the read-only
   audit to see what's still flagged: `plan-tool reconcile-plan <name>`,
   `plan-tool completeness <name>`, or `plan-tool verify-all --rollup <name>
   --step N` depending on which subcommand owned the loop.
2. **Bump the cap** if the loop was nearly converging:
   `--max-iterations 5 --iteration-budget 600`. Each iteration is
   one or more claude calls; expect proportional cost.
3. **Fall back to one-shot** if the loop is thrashing rather than
   converging: re-run with `--no-iterate` and hand-edit the surviving
   findings.

### `--iterate` halted on marginal stagnation

Symptom: the run exits 0 but the stderr final line names a
`marginal-stagnation` halt rather than `converged`. The artifact is
the iteration-N output; iteration N+1 would have produced the same
findings.

Cause: claude can't improve further on this artifact. The remaining
findings are either fundamentally out of scope for the loop (e.g.
"this section needs a human decision") or false-positives the
primitives flag every pass.

Fix: read the final stderr block to see which findings survived; if
they're false-positives, file an issue against the primitive; if
they're real, hand-edit the artifact.

### Iteration N produced no diff — loop ran but artifact unchanged

Symptom: the run exits 0; `[N/M]` progress lines show the loop ran;
but `git diff` against the pre-run state shows no changes.

Cause: claude refused to apply or `apply-finding` short-circuited
(e.g. all findings were already in the artifact from a prior
manual pass). The deterministic re-audit confirms there's nothing
to apply.

No action needed — the loop did its job and stopped early.

### `run` refuses with "step N declared file paths don't resolve"

Cause: the step's pre-flight check found one or more `files:` entries
whose **parent directory** doesn't exist under the resolved repo root.
The same diagnostic `plan-tool reconcile-plan --no-allow-missing-parent` would
emit (plain `reconcile-plan` allows missing parents by default), but at the
invocation point so claude never sees a wrong-pathed prompt.

Fix in this order:

1. **Typo or moved file?** Update the step's `files:` entry to the real
   path. Re-run.
2. **Step legitimately creates files under a new directory?** Pass
   `--allow-missing-parent`:

   ```bash
   plan-tool run my-feature --step 4 --allow-missing-parent
   ```

3. **Plan-wide path issue (≥80% mismatch)?** The diagnostic itself
   names the systemic cause. Pin the repo root with
   `--repo-root /path/to/project` instead of overriding per-step.

The pre-flight runs for every mode, including read-only review modes.
A wrong path is wrong regardless of whether the prompt asks claude to
implement or audit — `--allow-missing-parent` is the same escape hatch
in both cases.

### `run` fails with "no edits applied"

Cause: post-flight check observed that none of the step's `files:`
entries changed content during the call. The step is not advanced and
exits 1; its `status_note` reads "no edits applied". The executor's final
reply is saved under `.plan-tool/parse-failures/_run/<plan>/` and the run
log's `model_failure_receipt` (`reason: no-edits-applied`) carries its
digest and path — read it first, it usually says why the model stopped
(a missing upstream contract, a blocked prerequisite). Possible causes:

- claude may have completed the prompt by editing files outside the
  declared `files:` list (legitimate but unusual);
- or the step's prompt didn't ask for any code changes (review-only
  step that should have been authored as a different mode);
- or the step is a no-op (description didn't match what was needed).

Investigate before re-running. If the work landed in unexpected files,
update the step's `files:` to match reality, since a re-run that edits
none of the declared files is blocked as "no edits applied" again. If the
files already hold the intended content, commit them (`--accept` needs a
clean tree apart from the plan and lessons files), then
`plan-tool run <plan> --step N --accept` certifies the step with the plan's gates — provided the plan has a
`test_command` or the step has a `gate`; with neither, `--accept` refuses
and the step has to be marked done by hand.

### `run` warns "step N produced no `## Summary` line"

Cause: claude's final response didn't include the prompt-mandated
`## Summary` section. The step still advances; the lessons-log entry
just lacks a one-line takeaway. Common when claude ends a long step
with a bulleted recap instead of the one-line format the prompt asks
for.

No action needed unless the takeaway matters for your records — in
which case re-run the step (after manually flipping its status back
to `pending`) or hand-edit the lessons file.

### `run --mode <review>` reports a critical finding

Cause: claude's `## Findings` block contained at least one
`CRITICAL:` finding. The verdict line shows the counts — read the
review body above it for the issues. (The command still exits 0; the
verdict is in the output, not the rc.)

Fix the underlying problems and re-run, or accept the findings and
move on — the plan isn't mutated by review modes.

### `verify-all` reports a `[FAIL]`

Same shape as the review-mode finding: at least one done step has an
unresolved `CRITICAL:` reconcile finding (or claude failed). The
command exits 0 regardless (pass `--fail-on-findings` to make a
`[FAIL]` exit non-zero in CI); the verdict block names which steps
failed. Investigate per-step with
`plan-tool detail <name> --reconcile --step N` (plan-side audit) or
`plan-tool run <name> --reconcile --step N` (code-side audit) for
the full report.

`verify-all` is read-only — it doesn't flip a `done` step back to
`pending` on failure. If a step needs to be redone, manually edit the
plan's frontmatter to change the step's `status` to `pending` and
re-run with `plan-tool run`.

### Detail file declared but not on disk

Symptom: a step's review prompt says
`_detail file 'X' declared but not on disk_`, or `run` produces
`_Detail file declared at X but not found on disk._`

Causes & fixes:

- Wrong repo root (see above) — fix with `--repo-root`.
- Detail file genuinely missing — restore from git, or remove the
  `detail:` field from the step until you write the file.
- Path typo — fix the step's `detail:` field.

### codex backend prerequisites / auth

These fire when Codex is selected by `--backend codex`,
`PLAN_TOOL_BACKEND=codex`, or a matching `--model` family; the default
`claude` backend is unaffected.

**Symptom:** `codex backend selected but its 'codex' executable was not
found on PATH`, exit code `127`.

Cause: Codex was explicitly selected or inferred from `--model`, but isn't
installed or isn't on `PATH`. An explicit or non-default selection preflights
the binary before any step runs, so the failure is up front rather than
mid-run.

Fix: install codex and make the `codex` command available, or correct
`PATH` if it's installed in a non-standard location. To fall back to the
default, run `plan-tool --backend claude …`, unset `PLAN_TOOL_BACKEND`, or
remove/change the model that selected Codex.

**Symptom:** a run surfaces `codex not authenticated; check credentials
and re-login`.

Cause: codex's credentials under `~/.codex/auth.json` are missing or
invalid. This is the `AUTH` failure class — unlike a rate limit, it does
**not** wait or retry, since waiting can't fix a credential problem.

Fix: re-authenticate (`codex login`) so `~/.codex/auth.json` is populated,
then re-run the command.

Safe probe for maintainers: do not move or corrupt the real `~/.codex`.
To recapture auth copy, run codex with an isolated empty `CODEX_HOME`, closed
stdin, and a disposable cwd; sanitize request ids and paths before committing
any transcript. The pinned fixture is
`tests/fixtures/codex/exec-auth-failed.jsonl`.

### backend rate-limit choice

Ordinary recoverable short rate limits are handled by a process-wide policy set
before subcommand dispatch. Default behavior is `wait`: sleep until the
backend's parsed reset time, then retry the same backend.

```bash
plan-tool --on-rate-limit stop run my-feature
plan-tool --on-rate-limit switch --fallback-backend codex run my-feature
PLAN_TOOL_ON_RATE_LIMIT=ask plan-tool run my-feature
PLAN_TOOL_ON_RATE_LIMIT=switch PLAN_TOOL_FALLBACK_BACKEND=codex plan-tool run my-feature
```

Policy precedence is: `--on-rate-limit wait|switch|stop|ask`, then
`--no-wait-on-rate-limit` as the legacy alias for `stop`, then
`PLAN_TOOL_ON_RATE_LIMIT`, then `wait`. `switch` requires
`--fallback-backend` or `PLAN_TOOL_FALLBACK_BACKEND`; the flag overrides
the env var. A switch retries only the current rate-limited invoke with the
fallback backend, then restores the backend that was active before that
invoke. Later calls, sibling parallel workers, and serial replay do not
inherit the fallback backend.

Interactive `ask` prints `rate limit [w/b/s]:`: `w` waits and retries,
`b` prompts for a registered backend name and retries the current invoke with
that backend before restoring the prior active backend, and `s` stops so you
can resume later. In headless runs, `ask` stops instead of blocking on input.

### Cursor monthly plan quota

**Symptom:** Cursor reports its confirmed monthly plan-quota message, including
`ActionRequiredError`, `Switch to a different model`, `set a Spend Limit`, and
`monthly cycle ends on <date>`.

**Result:** the current call returns after its first failed attempt. This
terminal provider result does not wait, prompt, select `--fallback-backend`,
sleep for backoff, consult the retry guard, or retry; `--on-rate-limit` applies
only to ordinary short rate limits.

**Fix:** resolve the provider quota or wait for Cursor's actual reset, then
start a new command invocation. The displayed monthly-cycle value is a
calendar date, not a local reset time or a delay plan-tool can schedule.

### cursor agent backend prerequisites / auth

These fire only when you select the `cursor` backend (via `--backend
cursor` or `PLAN_TOOL_BACKEND=cursor`).

**Symptom:** `cursor backend selected but its 'agent' executable was not
found on PATH`, exit code `127`.

Fix: install the Cursor Agent CLI and ensure `agent` is on `PATH`, or fall
back with `plan-tool --backend claude …`.

**Symptom:** a run surfaces `cursor not authenticated; check credentials
and re-login`.

Cause: neither `agent login` credentials nor a valid `CURSOR_API_KEY` is
available. This is the `AUTH` failure class — no wait or retry.

Fix: run `agent login` or export a valid `CURSOR_API_KEY`, then re-run.

See [`docs/reference/contracts/cursor-agent-cli.md`](docs/reference/contracts/cursor-agent-cli.md)
for the pinned argv and event schema.

---

## Working in non-standard layouts

### Skill installed somewhere other than `.agents/`

Pin the project root:

```bash
plan-tool --repo-root ../.. list
# or
export PLAN_TOOL_REPO_ROOT=$(realpath ../..)
```

### CI sparse checkout (no `.git`)

Either pin the root explicitly:

```bash
plan-tool --repo-root /workspace <subcommand> ...
```

…or scan a directory directly without manifest mode:

```bash
plan-tool --plans-dir /path/to/plans list
```

### Two repos nested inside each other

`--repo-root` overrides walk-up entirely. Use it when the walk-up
hits the wrong `.git` first.

### Driving a non-registered directory of plans

```bash
plan-tool --plans-dir /path/to/plans list
plan-tool --plans-dir /path/to/plans status my-plan
plan-tool --plans-dir /path/to/plans run my-plan
```

The directory is scanned for top-level `*.md`; same parsing rules as
manifest mode. Same effect as setting `PLAN_TOOL_PLANS_DIR`.

---

## Progress output during long claude calls

Ask the assistant to monitor the original command and report progress using
[the liveness procedure](integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely).
A `done in` line or `backend_terminated` event closes a backend call only;
publication, iteration and finalization can remain. Completion requires the
original shell's exit status and the matching run's `run_end`. Quiet output or
a checkpoint supplies no shortcut and never authorizes a second invocation.

Every claude-invoking subcommand — `run`, `verify-all`, `detail`, `jira`,
`reconcile-plan`, and `create --from*` — emits human-facing status lines on
**stderr** while the call is in flight. Each call can take minutes;
the lines tell you which step is running and how long it has been
running.

Sample stderr from `plan-tool detail my-feature` against a 3-step plan:

```
[1/3] step 1: Wire up the renderer…
        15s elapsed
        30s elapsed
        done in 47s (4.2 KB response)
[2/3] step 2: Build the parser…
        15s elapsed
        FAILED in 18s: claude returned an unparseable response
[3/3] step 3: Add the smoke test…
        done in 22s (2.1 KB response)
```

For `run` and `verify-all`, the label includes the prompt mode so you
can tell at a glance which template is in flight:

```
[1/1] step 4: Wire up the API (mode=reconcile)…
        15s elapsed
        30s elapsed
        done in 51s (12.4 KB response)
```

- `[N/M]` reflects the number of *invocations*, not raw target steps —
  steps that are skipped (`detail`'s already-has-a-file idempotent
  skip) don't count toward the total.
- Heartbeat ticks fire every 15s. A 5-minute call emits ~20 lines.
- `done in Xs (YKB response)` closes a successful call. `FAILED in Xs:
  <reason>` closes a failed call. Failures continue to the next step
  for `detail` and `verify-all`; `jira` raises on the first parse
  failure; `run` returns a non-zero rc and leaves the plan untouched.
- `run` and `verify-all` *also* stream `claude --verbose` output on
  **stdout**. The two channels are independent — verbose tool-use lines
  on stdout, framing on stderr — so neither interferes with the other.

### Stdout vs. stderr — implications for scripting

- **stderr** carries progress (human-facing chatter).
- **stdout** carries the structured payload — `detail` per-step
  status, `reconcile-plan` markdown report.
- **`jira`** writes its output to disk by default and emits a
  one-line summary on stdout. Pass `--no-write` (and optionally
  `--stdout`) to stream the full payload.

```bash
# Clean JSON on stdout, progress on stderr:
plan-tool jira my-feature --format json --no-write | jq '.stories'
```

To pipe to a parser that expects merged streams, redirect stderr
separately:

```bash
# Suppress progress, skip the file write:
plan-tool jira my-feature --format json --no-write 2>/dev/null | my-parser

# Or capture both:
plan-tool jira my-feature --format json --no-write 2>progress.log | my-parser
```

`--dry-run` paths (no claude invocation) emit no progress.

### Disabling progress output

There is no `--quiet` flag. For silent progress output, redirect stderr
(`2>/dev/null`). This also hides diagnostics, so capture stderr in a file when
you need to retain them.

---

## Inspecting prompts before they run

Commands that render prompts without invoking Claude support `--dry-run`:

```bash
plan-tool run my-feature --step 4 --dry-run
plan-tool detail my-feature --step 3 --dry-run
plan-tool reconcile-plan my-feature --step 4 --dry-run
plan-tool verify-all my-feature --mode test --dry-run
```

Use this to verify:

- The right files made it into the prompt's "Current file contents"
  block.
- "Current file contents" is a bounded, symbol-aware preview. It may
  start near a matching function, class, constant, markdown section, or
  other title-derived symbol instead of at the top of the file.
- Readable source and markdown detail previews use the shared prompt
  excerpt policy. If no useful symbol or markdown section match exists,
  the prompt keeps a bounded fallback preview instead of failing.
- Each prompt family still owns its own context budget. The shared policy
  changes which part of a readable file is shown, not whether a command
  can exceed its prompt budget.
- The detail file (if `step.detail` is set) loaded cleanly — look for
  "from `<path>`" near the top vs. "declared but not on disk".
- Missing/unreadable file markers are accurate. `_(truncated)_` still
  means an incomplete bounded preview, and a focused excerpt does not
  mean the rest of the file is absent.
- For `jira`: `max_hours` interpolated correctly into the schema
  section.

---

## The prompt-budget advisory

Before a command sends a prompt to the backend, the tool estimates the
prompt's size against the model's context window and, **only when headroom
is tight**, prints a `warning:` line to stderr with a per-block breakdown of
which sections dominate. It is **advisory**: it does not change the exit code, the same "surface
unconditionally, block never" stance as the
[`plan-tool convergence`](#diagnosing-convergence-with-plan-tool-convergence) diagnostic, with the one
exception under "The one refusal" below. When nothing is known about the model's window the estimate
uses 200,000 tokens and the warning says `(default)`.

| Lane | Window it is measured against |
| --- | --- |
| Codex | The usable share of the model's entry in `models_cache.json` under `$CODEX_HOME` (default `~/.codex`; refresh with `codex debug models`). |
| Claude | The window an earlier call of the run reported, when that call used one model or listed the selected model's id. A result that mixes models gives only its smallest window, shown without `(default)`. The first call of a run uses the default. |

- **The one refusal.** A selected `run-reconcile` prompt is refused before the backend runs when its
  budget is `high`. That verdict uses the Codex catalog's window or the 200,000 default, never a
  window learned earlier in the run, so it does not depend on which calls happened first.
- **When it fires.** On the real send of every claude-invoking command. A
  named-block breakdown is wired into `detail`, `create` (its distill / steps
  / synthesis phases), the plan-audit loop, and `run` / `check` / `security`
  / `reconcile` steps. Commands with no named blocks — `jira`, `lessons`,
  `annotate`, `roadmap` — still get a total-bytes backstop at the shared batch
  seam. That backstop is the only budget signal a `roadmap` revision gets, and
  a revision prompt carries the whole prior artifact, so it is the roadmap case
  most likely to trip it. It warns and does not fail a run, except
  the selected run-reconcile refusal above. It does **not** fire on a step resumed from a checkpoint or under `--dry-run`
  (no send happens).
- **The three levels.** The advisory stays silent at `ok` and warns at `warn`
  and `high` (tighter headroom). The token estimate rounds **up** on purpose,
  so it errs toward warning early rather than missing an overflow — an
  occasional early warning is the intended bias, not a bug.
- **Inspect before you spend.** `detail --dry-run` and `run --dry-run` print
  the full per-block breakdown to stderr **at every level** (even `ok`) for
  each step they would author or run, so you can see headroom before burning a
  call. The breakdown goes to stderr because the dry-run prompt itself goes to
  stdout; a dry run records no telemetry. A dry run has made no call, so a Claude dry run is
  always measured against the default window. Pair this with
  [Inspecting prompts before they run](#inspecting-prompts-before-they-run)
  above.
- **What to do about a warning.** The advisory tells you a prompt is large; it
  does not shrink it. Reach for a structural remedy rather than squeezing
  harder: carve an over-packed step with
  [`plan-tool scope-out`](#carve-an-over-packed-step-out-of-a-plan-plan-tool-scope-out),
  split a step (`plan-tool split`),
  [re-decompose when audit/apply doesn't converge](#when-repeated-auditapply-doesnt-converge--re-decompose-dont-keep-patching),
  split a seed that covers multiple plans
  ([a seed that's too large](#workflow-a-seed-thats-too-large-or-covers-multiple-plans)),
  or lower an audit's pass count (`--max-passes`).
- **Telemetry.** Each real send records one `prompt-budget` decision event
  locally under `.plan-tool/telemetry/` for later threshold tuning; a dry run
  records nothing. The event shape lives in
  [`DATA_CONTRACT.md`](DATA_CONTRACT.md).

---

## Mutating vs. read-only modes

`run` (default mode) **mutates** the plan: it advances step status on
success. Other modes are read-only audits and never touch the plan
file:

| Mode | Mutates? |
| --- | --- |
| `run` | yes — advances `pending` → `current` → `done` |
| `check` | no |
| `optimize` | no |
| `document` | no |
| `test` | no |
| `security` | no |
| `lint` | no |

`reconcile-plan` is no longer exposed as a `--mode`. See
[Workflow: per-subcommand reconcile](#workflow-per-subcommand-reconcile)
for the `detail --reconcile` / `run --reconcile` split.

`annotate` is read-only on both the plan and the code — it never
advances step status and never edits its source — **except** the opt-in
`--archive`, which moves (not edits) the original. See
[Workflow: annotate an existing plan to seed the next one](#workflow-annotate-an-existing-plan-to-seed-the-next-one).

If you accidentally run `--mode run` and the step was wrong, you'll
need to manually flip the step's `status` back to `pending` in the
plan's frontmatter. There's no `unrun` command by design.

---

## Backends

plan-tool drives a CLI subprocess per step. The default backend is
`claude`; registered alternatives are `codex` (OpenAI Codex CLI) and
`cursor` (Cursor Agent CLI, binary `agent`). Select per-run with the
global `--backend` flag, or for a shell session with `PLAN_TOOL_BACKEND`:

```bash
plan-tool --backend codex run my-feature          # OpenAI Codex
plan-tool --backend cursor run my-feature         # Cursor Agent
export PLAN_TOOL_BACKEND=codex                    # every run this session
plan-tool run my-feature
```

Backend selection precedence is: the explicit `--backend` flag, then a
recognized `--model` family, then the `PLAN_TOOL_BACKEND` environment
variable, then the default `claude`. `gpt-*`, `chatgpt-*`, `o1`/`o3`/`o4`, and
`codex-*` select Codex; `claude-*` selects Claude; and `gemini-*` selects the provisional
`gemini` backend until a packaged Gemini integration is available. Other model
names stay on the configured backend. An explicit `--backend` remains the
escape hatch for an intentional non-default pairing.

Rate-limit policy is independent of backend selection. For ordinary
recoverable short rate limits, use `--on-rate-limit wait|switch|stop|ask` or
`PLAN_TOOL_ON_RATE_LIMIT` to choose the default response; use
`--fallback-backend` or `PLAN_TOOL_FALLBACK_BACKEND` only as the retry target
for the current rate-limited invoke when the action is `switch`. The fallback
backend is restored afterward; it does not become the selected backend for
later work. A confirmed Cursor monthly plan quota bypasses those actions,
returns the current call, and requires provider recovery before a new
invocation. The legacy `--no-wait-on-rate-limit` flag is equivalent to
`--on-rate-limit stop`.

codex must be installed, on `PATH`, and authenticated (`~/.codex`). For
the install/PATH and auth failure modes, see
[codex backend prerequisites / auth](#codex-backend-prerequisites--auth)
under Recovery. cursor requires `agent` on `PATH` and auth via
`agent login` or `CURSOR_API_KEY` — see
[cursor agent backend prerequisites / auth](#cursor-agent-backend-prerequisites--auth).
The conceptual overview — sandbox-mode mapping and which run-log stats
each backend omits — lives in
[README.md → Backends](README.md#backends). Pinned contracts:
[`docs/reference/contracts/codex-cli.md`](docs/reference/contracts/codex-cli.md),
[`docs/reference/contracts/cursor-agent-cli.md`](docs/reference/contracts/cursor-agent-cli.md).

### Which backend for which task family

[`docs/evidence/backend-recommendations.md`](docs/evidence/backend-recommendations.md) names the
recommended backend per task family (proposal / detail / reconcile /
implementation / apply), with the evidence row and a confidence caveat. It is a
**generated artifact** — rendered from a committed benchmark run, never
hand-edited. The corpus, rubric, and 66-invocation envelope behind it live in
[`docs/evidence/benchmark-design.md`](docs/evidence/benchmark-design.md).

#### When to re-benchmark

Re-run the matrix and regenerate the recommendations when any of these holds:

- **The header shows `⚠️ STALE`.** `bench report` recomputes
  `corpus_hash(corpus_root)` at render time; a `⚠️ STALE` marker on the doc's
  corpus-hash line means the live corpus differs from the hash the published run
  recorded — the corpus changed since the run, so the numbers describe a corpus
  that no longer exists.
- **A backend version bump.** `claude` or `codex` was upgraded. A backend
  carries no static version — the doc's version line is a live `--version`
  snapshot captured into `run_meta.json` at run time, so a newer installed
  binary makes the published numbers a *different* binary's results.
- **The corpus changed.** A new family/cell, an edited fixture, or a rubric
  change — all of which also move `corpus_hash` and trip the `⚠️ STALE` marker
  above.

#### How to re-run

Repeat the publish sequence with a **fresh stamp**, then commit the new run dir
and the regenerated doc:

```bash
plan-tool bench run --trials 3                 # all registered backends, all families
plan-tool bench report --stamp <stamp> --write-recommendations
```

`bench run` prints the stamp it wrote under `.plan-tool/bench/runs/<stamp>/`;
pass that stamp to `bench report`. If a run is interrupted mid-matrix, re-invoke
`bench run --stamp <stamp>` to resume — completed cells (including ones that
recorded a classified failure) are skipped; only cells with no record re-run.
**Never hand-edit `docs/evidence/backend-recommendations.md`** — its header says so, and a
re-render would overwrite the edit.

#### How to read the confidence caveats

Quality is reported as **median + (min, max)** over **3 trials per backend across
11 corpus cells** (2–3 cells per family) — not percentiles, not a p-value. Each
family's `confidence_caveat` names the trial and cell counts and states the
result is **directional, not statistically significant**: 3 trials per cell can't
support a significance claim, and the doc says so. Treat a small median gap
between two backends as noise, not a verdict; a `_No clear winner_` line means
the medians tied and the tiebreak (wall-clock, then cost) decided it.

---

## Backing up / undoing

There is no built-in undo. Recovery options:

- **Plan file** — `.agents/` is gitignored by default; if you keep it
  in version control, `git checkout -- <plan>` reverts.
- **Lessons log** — append-only by claude; safe to manually edit if a
  step's lesson is wrong.
- **Detail files** — same; safe to edit.
- **Files claude wrote during `run`** — recoverable from version
  control. Use `git diff` between the pre-run commit and post-run to
  see the blast radius.

For high-stakes runs, commit before each `run` so a `git reset --hard
HEAD~1` is always available.
