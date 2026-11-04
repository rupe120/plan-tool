# plan-tool directives (shared across coding assistants)

**Canonical source for how to *drive* `plan-tool` from an AI coding assistant.**
Repo-agnostic: everything here applies when authoring, auditing, or executing a
plan in **any** consuming repository. Rules specific to developing `plan-tool`
itself stay in this repo's `CLAUDE.md`.

**Who reads this, and how it is wired.** This file is tracked in the `plan-tool`
repo, so it reaches every clone and contributor. Three distribution paths:

- **`plan-tool install-skill`** — the primary way most consuming repos get
  this file. It installs this exact file as a literal sibling of the chosen
  backend's `SKILL.md` router at the resolved destination (`<root>/skills/
  plan-tool/`, or the `--user`/`--root .agents` variants), for `--integration
  claude`, `codex`, or `cursor` alike — reaching a Claude Code, Codex, or
  Cursor session directly, with no dependency on either path below.
- **The machine-local symlink** — on a workstation this repo's own clone is
  also exposed at a stable path so assistants that do not auto-load a
  user-level config can be pointed at it:

  ```
  ~/.claude/directives/plan-tool.md   ->  <plan-tool repo>/integrations/shared/DIRECTIVES.md
  ```

  - **Claude Code** — `~/.claude/CLAUDE.md` references it; project `CLAUDE.md`
    files reference it too.
  - **Codex / Cursor** — no user-level auto-load. When a project `CLAUDE.md` is
    supplied as the directive file, that file must carry an explicit pointer here
    so these assistants read it as well. Each consuming repo's `CLAUDE.md` is
    responsible for carrying that pointer.
- **A project `CLAUDE.md` pointer** — covers a session working in this repo
  before `install-skill` has been run.

If the symlink is missing (fresh clone, other machine), read this file directly
from the repo — the repo copy is canonical and the symlink is a convenience.

---

## Optional companion skills

Use companion skills for expertise the consuming project needs: its language
and framework, testing, root-cause debugging, code review, security,
documentation, release preparation, or handoffs. Choose a focused skill for a
recurring task; these recommendations add no package prerequisite or audit
gate. Keep plan-tool's workflow and the repository's contracts authoritative
under the session's instruction hierarchy.

Read a candidate's instructions, scripts, dependencies, and supported tools
before installing. Prefer skills that complement the workflow rather than
introducing a second planner, execution loop, or automatic parallelism. Check
conflicting advice against the repository's scope, test, and review rules.

Verify discovery in the current Claude Code, Codex, or Cursor Agent CLI.
Availability in an editor or parent session does not prove availability in a
fresh plan-tool backend subprocess. Keep required project contracts in tracked
guidance and plan artifacts; an optional personal skill is not their only home.
The source repository's `docs/how-to/companion-skills.md` has the selection
guide; `plan-tool install-skill` installs only the bundled integration.

## Invocation and discovery

`plan-tool` is a global CLI (`uv tool install --editable .`). Invoke directly:

```bash
plan-tool <subcommand> [args]
```

**Repo root** is auto-discovered by walking up to `.git` / `.plan-tool`; nested
checkouts are scored by manifest resolution. `--repo-root` is only for
overriding a wrong auto-selection. **Plans** are discovered per project via
`<repo-root>/.plan-tool/plans.json`.

**Artifact layout in a consuming repo:**

| What | Where |
| --- | --- |
| Plans | `docs/implementation-plans/<N>-<slug>.md` |
| Per-step detail | `docs/implementation-plans/plan-details/<slug>/NN-*.md` |
| Seeds | `docs/implementation-plans/plan-seeds/` (where `SEED_FORMAT.md` and `roadmap --apply` write them) |
| Tool state | `<repo>/.plan-tool/` (`plans.json`, `runs/<slug>/`, `checkpoints/<slug>/`) |

The `<N>-` tier prefix on the plan filename is **added by the tool** — pass a
bare slug to `create`, or you get `2-2-<slug>.md` and a detail directory whose
name breaks the convention every other plan follows.

## Running from chat / automation (no TTY)

Treat every assistant-driven run as **headless**: close stdin and pass `-y`.

```bash
plan-tool create <slug> --from-existing <seed> --output-dir docs/implementation-plans -y < /dev/null
plan-tool detail <slug> -y < /dev/null
```

**Never** pipe an infinite empty-line source (`yes "" |`) — the input loop spins
against it. Closed stdin (`< /dev/null`) is the only safe choice.

**Every `create` / `detail` / `run` / audit call is long-running.** Run it in the
background, tee to a durable named log, and prefix any pipeline with
`set -o pipefail` — without it a failing command reports the exit status of
`tee` and a failure is read as success. Announce at launch what is running and
where to watch it.

### Monitor command liveness and recover safely

**Track the command, not only its output.** Retain the terminal session handle
and parent `plan-tool` process id from launch, and poll that same execution
until the shell reports its exit status. A yielded terminal cell, quiet log,
checkpoint, published artifact, or completed wrapper is not an exit signal
while an underlying command session or process remains live. Match
`.plan-tool/runs/<slug>/in-flight.json` to its `run_id` and inspect the
corresponding JSONL run log. `backend_terminated` with
`termination_reason: completed` means only that the backend call ended;
`plan-tool` can still publish, iterate, or finalize. Report completion only
after the original shell has exited and that run records `run_end`.

**Keep one active invocation per plan.** While the original parent process is
live or its exit remains unconfirmed, continue monitoring it. Do not start a
second `create`, attempt a checkpoint resume, or advance to `detail` or an
audit based only on a backend result. An interruption of a later attempted
resume says nothing about the original process; inspect the original process
and run id separately. After a confirmed exit, use its recorded outcome and
published artifacts to choose the next command.

**Diagnose a post-backend stall before intervening.** Take at least two
separated read-only observations of the original process, the matching run-log
tail, and the in-flight snapshot. Record the elapsed time since the last event
and distinguish an `awaiting_retry` phase from an idle post-backend phase.
Continue monitoring and report that evidence; ask the user before stopping or
killing a live `plan-tool` process. Consider recovery or resume only after the
original command has definitely exited.

**Classify preflight refusals accurately.** A seed or command preflight refusal
is a normal no-authoring outcome, not a backend or execution failure. That
covers a missing required `## References` section and a
`route: refused — file-backed source: …` exit 2 from the distill route: both are
a defect in the seed, not model variance. Do not retry the same input; read the
reason printed after `file-backed source:`, correct the seed to clear it,
commit the correction, and start a new invocation only after any prior
invocation has exited.

**A run another session launched is not yours to poll.** Watching a
`plan-tool` command you did not start — reading its `in-flight.json` or run log
until it disappears — is not an endorsed procedure. Ask the user how they want
to follow it (wait for its own exit, or have the launching session report).

## Creating several plans in one session

**The batch is a set the user names; never infer it from what exists.** Accept
specific plan rows or seed files, or a roadmap, which names all of that
roadmap's plan rows. Never default to every file in `plan-seeds/`, every seed
`roadmap --apply` promoted, or every row of a roadmap the user did not name.
Asked to create plans with neither a selection nor a roadmap named, ask which
ones.

- **Order.** For roadmap-derived plans, order the named rows by the roadmap's
  `ordering`; for seeds not tied to a roadmap, use the order the user gave.
- **A dependency outside the batch stops it.** A named plan that depends on an
  unnamed roadmap row with no plan yet stops the batch with a question; do not
  pull the row in.
- **Resume, don't restart.** Each plan resumes at its first incomplete stage of
  `create` → bare audit → `detail` → detail-grounded audit. A completed stage is
  skipped and reported. A plan whose latest audit has not converged on its
  current committed snapshot finishes that convergence before the next plan.
- **Sequential, stop at the first refusal.** Each `create` writes
  `.plan-tool/plans.json`, so plans are handled one at a time, and the batch
  stops at the first refusal (see "Classify preflight refusals accurately").

## Subcommands by intent

- **Roadmap** (project-altitude, above the pipeline): `roadmap <slug>` — see
  [Roadmap](#roadmap) below.
- **Discovery** (read-only, never calls the model): `list`, `status <name>`,
  `validate <name>`, `runs`, `checkpoint`, `convergence <name>`,
  `gate-status <name> --json` (saved final audit verdicts), `split-criteria`.
- **Authoring**: `create [slug]`, `detail <name>`, `split`, `merge`,
  `scope-out`, `scope-review`, `annotate <plan-file>`.
- **Audit — completeness** (judges the plan's own design): `completeness-audit`
  → `convergence` (loop trend). `gate-status <name> --json` reads the latest
  saved final verdict per stage; it runs no audit. It cannot report an
  invocation that writes no final sidecar, including
  terminal plan-quota stops. (`completeness-apply` still exists but is deprecated and
  going away — BACKLOG #376 — see "The session-directed convergence loop" below.)
- **Audit — reconcile/verify** (plan vs. code): `reconcile-plan`
  (**pre-execution only**), `reconcile-code` (**post-execution**),
  `verify-all --rollup`, `run --mode <review>`.
- **Execution**: `run <name>`, `run <name> --all`.
- **Integration**: `jira <name>`.

`validate` checks **format, not design** — it is never a substitute for an audit.

## Versioned persisted contracts

When a plan introduces, changes, defaults, or retires a persisted schema,
identity, or protocol version, treat existing projects and their stored data as
first-class scope. Before authoring detail or implementation, put one explicit
transition in the plan and its acceptance tests:

- compatible read plus safe rewrite;
- a bounded migration with its eligibility, interruption/recovery, and
  rollback or repair behavior; or
- a user-approved retirement after every known consumer and live record has
  migrated or been deliberately archived.

Name the legacy reader/CLI outcome and test both a successful transition and
an unsupported or unsafe legacy record. A new default writer version is not an
upgrade path, and a reader must never infer or silently upgrade an ambiguous
record. If any existing project or data cannot safely follow the selected path,
stop and surface that decision rather than shipping a compatibility break by
assumption.

## When a chat concludes a plan is mis-decomposed, audit the instruments before moving on

**Trigger:** you decide outside a `plan-tool` surface — in conversation, from reading code, from a
measurement — that a plan should be split, carved, re-cut, or withdrawn, and no
`plan-tool` surface told you so. That is a detector miss, and the only moment the
evidence is cheap to collect is right then.

**Do this before you act on the decision** (read-only, no model calls):

1. Read what telemetry recorded for that plan:
   `plan-tool telemetry`, or filter `.plan-tool/telemetry/decisions.jsonl` on the
   plan slug for kinds `granularity` (both `create-review` and `assessed`),
   `escalate-split`, and `step-provenance`.
2. Classify the miss into exactly one of three, because the fix differs:
   - **(a) It fired and nobody read it** — the signal is in the log with a
     non-zero `split`. The gap is surfacing/routing, not detection.
   - **(b) It ran and concluded otherwise** — assessments exist with `split=0`.
     The detector had inputs and was wrong, *or* was answering a different
     question than the one that mattered. Note which.
   - **(c) It never ran, or ran with no inputs** — an instrumentation gap.
3. **Record the case in `BACKLOG.md`** with the plan slug, the conclusion, and
   which of (a)/(b)/(c) it was. A decision that leaves no trace
   teaches the tool nothing; the instruments cannot learn from a decision they
   do not record.

**Worked example, 2026-08-08 — and it landed on (b), with a twist worth
expecting.** `audit-trajectory-instrumentation` was withdrawn in a session
after its premise was disproved. Telemetry showed **17** granularity assessments across the
plan's life — one `create-review` plus 16 completeness-stage — reporting
**`split=0` every single time**, and `merge=1` on most of them: the instrument
pointed the *opposite* direction from the truth, consistently, and nothing
recorded the withdrawal. The twist is that the detector was not simply wrong: all
17 are **step-altitude** questions ("is any step over-packed?"), and the defect
was **plan-altitude** ("is this one effort or two?"). That question is asked
exactly **once**, at `create`'s distill pass, and never revisited — so the
altitude that mattered got one look and the altitude that didn't got seventeen.
Expect to find an altitude mismatch, not only a wrong answer.

## Which model to run a subcommand with

**Use `gpt-6.1-sol` for all Codex model-backed work. For Claude Code, use Opus for roadmap, seed, and plan
creation and Sonnet for subsequent work.** This includes roadmap generation
and candidate authoring, seed authoring/regeneration (`--refresh-seeds`,
`--materialize`, and `annotate` when producing a forward seed), and `create`
including its distill and step-proposal passes. After creation, use the working
tier for audits, detail, execution, reconciliation, and reviews. Deterministic
commands that make no model call need no model selection.

**Select both backend and model explicitly on every model-backed invocation.**
Do not rely on the default backend or a per-backend model default, and use
`gpt-6.1-sol` for every Codex invocation. Pass the model per invocation —
`--model` is resolved
`--model` flag > `.plan-tool/backends.json` > manifest default, and every
shipped manifest sets `default_model: null`, so the backend CLI's own default
applies when nothing is passed. The project file's override is
**per-backend, not per-subcommand**, so there is no config that says "create
uses one model, run uses another." This is operator discipline today.

| Backend | Roadmap, seed, and plan creation | Subsequent model-backed work |
| --- | --- | --- |
| Codex | Sol: `gpt-6.1-sol` | Sol: `gpt-6.1-sol` |
| Claude Code | Opus: `claude-opus-5-5` | Sonnet: `claude-sonnet-5-5` |
| Cursor | no `--model`; Cursor's Auto | no `--model`; Cursor's Auto |

Codex model selection updated by owner instruction 2026-10-14; confirm against the backend's own model
list (`codex -m`, `agent models`) before relying on a name.

- **Creation tier — roadmap, seeds, and `create`.** These establish scope and constrain
  everything downstream: the seed scope, step list, `depends_on` graph, and file
  footprints that every later `detail`, `run`, and audit round inherits. A wrong
  decomposition compounds because it gets
  *elaborated* by every step that follows. `create`'s two conceptual sub-passes
  are the reason — the distill "one plan, or many?" decision, and the step
  proposal that authors the dependency graph.
- **Working tier — subsequent work,** including `detail`, `run`, both reconcile
  verbs, `verify-all`, `jira`, and the completeness audit. These scale with
  steps and iterations, and a weaker call surfaces as a failing test or a
  refuted claim rather than compounding.

**Why the completeness audit stays on the working tier, despite looking like
the conceptual surface.** Its *frame* is the limit, not its model: it is handed the
plan and asked whether the plan's ideas are sound, so it structurally cannot ask
whether the plan should exist. Measured 2026-08-08 — eight bare-plan rounds on
one plan, every finding real and correctly applied, none able to notice that the
plan's motivating symptom did not reproduce; a single conceptual question and a
throwaway replay script settled it in ~15 minutes. A stronger model there buys
sharper findings inside the frame that was already the problem. Spend it at
`create`, where the frame is still being chosen.

---

# Roadmap

`plan-tool roadmap <slug> --from-existing <concept.md>` turns a project-sized
concept brief into four gated artifacts — `01-domain.md` (entities, business
rules, workflows), `02-constraints.md` (each quality attribute with exactly
one disposition, plus the constraints discharging them), `03-components.md`
(logical components and pattern discharge), and `04-roadmap.md` (plan
mapping, ordering, assumptions) — plus draft seeds, all written under
`docs/implementation-plans/roadmaps/<slug>/`. The stage run is first-run only:
it holds each gate-clean stage in the resume directory
(`.plan-tool/runs/<slug>/roadmap-stage-resume/`), and publishes one immutable
version, a ledger-native feedback ledger, and the accepted head only after all
four stages pass. A failed run leaves only the resume directory and the next
run resumes from the first stage that is missing or fails its re-gate; a
changed brief refuses with a remedy (restore the brief, delete the named
resume directory by hand, or start a successor slug). Once an accepted head
exists, a stage run refuses: a roadmap with a head changes through ledger
feedback and candidate review (`docs/how-to/roadmap.md` § 6). The backend runs
only inside a stage; deterministic gates between stages retry a stage with
its violations quoted back, and stage runs are non-interactive (no prompt or
`-y`). Two non-zero exits: `1` when a stage spends its retry budget (backend
failure, unparseable reply, or gate rejection), `2` for a pre-flight failure
before any stage runs (for example an unreadable brief). Every command that reads the roadmap
reads the accepted version; a folder with no accepted head refuses with
`no published version`, and `docs/how-to/roadmap.md` § 1 owns the hand
conversion of an older folder (no tool migrates one).
Settle a `pending` decision with `roadmap <slug>
--settle-decision <artifact>:<decision-id> --settlement-evidence
<artifact>:<feedback-id> --confirm-decision-settlement`, citing an open
ledger item that approves it — never by hand-editing `status` in the
artifact (see `docs/how-to/roadmap.md` § 5); to ask for a change instead of
making it, submit a ledger item (`--submit-feedback`) and propose a candidate
(`--propose-candidate`); `--reopen-ledger-feedback ITEM_ID` reopens a
retained ledger item. `roadmap <slug> --apply` (plus a TTY
confirm, or `-y` under `--apply`) promotes draft seeds into `docs/implementation-plans/plan-seeds/`;
writes no plan and no manifest entry, and prints `create --from-existing`
lines on stage-4 completion. Feedback invalidates existing seeds without
replacing them; use `roadmap <slug> --refresh-seeds` to regenerate them
from current code, restoring archived sources and saving a diff report.
Until refresh, `create --from-existing` asks for stale-seed confirmation.
`roadmap <slug> --view {walk,ledger,index} [--mode {current,review}] [--id
ROW_ID]` is the read-only third mode: renders the traceability walk,
decision ledger, or reverse citation index over the accepted version — no
backend call, no stage run, no mutation. `roadmap <slug> --compare`
compares the accepted head with the active candidate (an omitted
`--comparison-target` means the active candidate and refuses when none is
active). `INDEX.md` in the roadmap folder is generated for people, rewritten
after every version-store change, and read by no command.

---

# The two audit gates

**A plan is audited twice: once bare, before any detail exists, and again once
the detail bundle is complete.** They catch different classes of defect, and the
early one is the cheaper of the two by a wide margin — a missing plan-level
contract, ordering rule, risk, or acceptance criterion caught before detail
authoring is one fix, not one fix multiplied across every detail file that
elaborated the gap.

**Parse every plan's YAML frontmatter before an audit or a commit.** A hand edit
that puts `: ` inside a plain scalar (an unquoted `title:` or step field) breaks
the YAML, and the audit then exits 2 without judging anything. Load each edited
plan's frontmatter with a YAML parser and fix the error first. Treat an audit
exit code 2 as a failed run, not a clean one: read its log.

## Gate 1 — the bare-plan audit (before `detail`)

**Run `plan-tool completeness-audit <slug> --iterate` on the plan as soon as
`create` lands, and again after any material change to the plan body — before
authoring detail.**

A plan is **bare** when one or more steps have no detail file.
`completeness-audit --iterate` supports that state deliberately: it judges the
plan body and the code at HEAD at the **plan/concept level**, labels the report
with exact `N of M` detail coverage, and does **not** treat a missing detail
file as a defect or claim its conceptual calls were detail-grounded.

**Read a bare-plan result by axis:**

- **`plan-correctness`** findings are actionable plan-body defects. Fix them.
- **`plan-completeness`** and detail-level findings are recorded, but their
  `completeness-apply` actions are **withheld** until the bundle is complete.

A withheld command is **not** a deferral. Withholding stops an automatic walk
from writing unreviewed detail-level content; it does not put an explicit
plan-level contract, ordering rule, risk, acceptance criterion, or
reader-selection decision out of reach. **When the suggested fix changes the
plan body, step graph, or acceptance criteria, apply the compatible findings by
hand as one bounded batch, then re-audit.**

Leave a finding for `detail` only when its remedy genuinely specifies
implementation mechanics, a per-step detail contract, or fixture-level coverage.
Never copy those mechanics into the plan just to satisfy the early audit — and
never use a missing detail file as licence to invent detail content in the plan.

**Triage each bare finding before editing anything.** Label it: **R** (conflicts
with an accepted roadmap artifact), **B** (a plan contract), **P** (an owner's
product decision), **D** (a detail mechanism), **I** (settled by code or a
platform spike), or **T** (a tool artifact). Edit the plan body only for B.
Route R to roadmap feedback, P to the owner, D to `detail`, I to a step's test
or spike, and T to the bug backlog. Fix from the finding's plan-altitude
restatement, not from its `Fix` line, which often names a mechanism. The
labels exist because the default reading of a bare report — every finding is
a plan-body edit — is what pulls detail into plans.

- **R — a conflict with an accepted roadmap is not a plan-body fix.** Either
  align the plan to the roadmap, or record the departure as roadmap feedback
  with the owner's decision (`roadmap <slug> --submit-feedback`) and cite that
  record in the plan, so re-audits stop re-flagging it.
- **T — tool artifacts.** A finding that cites a path another plan in the same
  roadmap creates as missing, or a stale roadmap or seed path, is a known false
  positive: verify it once, file or cite the bug entry, and leave the plan alone.

**Diff a bare-round fix before committing it.** If it adds a table, algorithm,
schema constraint, state machine, file layout, or platform-specific behavior,
cut it to the one-sentence property and move the rest to the step's detail
hint. If a plan body grows by more than about a quarter across bare rounds,
stop and re-check altitude before the next audit: growth is the visible sign
that mechanism is landing in the body.

**Choose the artifact by the contract, not by the proposed implementation.** If
the plan names a safety, ordering, ownership, compatibility, bypass, or
acceptance property and a route does not uphold it, make a session-directed
plan-body correction that names the property and uncovered route. Leave a delivery choice
to `detail` when the finding only selects a mechanism. The narrow exception is
plan text that explicitly makes that mechanism the observable contract for a
named property; do not infer it from a plausible implementation choice.

This is the same altitude discipline as the plan-vs-step mismatch above: a
bare-stage finding stays at **plan altitude** (the contract) and never
descends into **detail altitude** (the mechanism) unless the plan text itself
made the mechanism the contract. A fix authored at the wrong altitude either
invents detail-level content the bare gate cannot yet ground, or leaves a
plan-level contract gap standing because its remedy was mistaken for
detail's job.

**Altitude also governs the language itself, not only which stage owns a
decision.** When several sections restate what is really one underlying claim
in slightly different words — the same condition list copied near-verbatim
into Architecture, Risks, Testing, and Acceptance criteria — that repetition
is itself a tell: the prose sits one altitude too low, each restatement is a
separate place to drift out of sync, and a reader has to reconcile N
phrasings to find the one rule that actually governs. State the shared shape
once — "these N items reduce to M independently-checkable ones; the rest are
consequences of them" — and have every other section refer back to it, rather
than repeating each instance mechanically.

**Keep the work proportional to the chosen intent.** A plan, detail, or audit
fix does not absorb a broader abstraction, adjacent workflow, or future
capability merely because it would be useful. Before adding it, name the
current outcome, acceptance property, authority boundary, safety invariant, or
ordering rule that cannot hold without it. If none exists, retain the fence and
defer the concern rather than enlarging the arc. The bar is the smallest proof
that satisfies that named property today, not the eventual, more general
capability the mechanism could someday support.

**Every correction is true and proportional to the intent at its current
altitude.** At bare-plan altitude, state and prove the smallest plan-level
property that completes the intent; leave delivery mechanics to `detail`.
Before editing, sweep both the cited identifier and the concept's vocabulary,
then judge the proposed remedy against the goal and the bug's shape. Do not
mistake replaying one mechanism at every matched site for proof that the
mechanism produces the intended property.

The run-grade bare-mechanism / same-finding `edit_drift` advisory helps an
operator reconsider a likely detail-owned request. It is recommend-only, not
causal proof or an automatic deferral, and it changes no gate, continuation,
failure, or exit behavior. The
detail-grounded audit remains the stage that judges the selected mechanism.

**Proceed to `detail` when** a re-audit is confirmed-dry (or confirmed-low-yield
per the stopping rule below) against a fresh unchanged snapshot. Record the
report path, the `N of M` detail coverage, the audit-coverage verdict
(including a budget-limited result), and which axes were withheld. **After three
bare rounds, proceed to `detail` when the remaining findings are D, I, or about
text the previous round added**, and carry them as detail inputs; a fourth bare
round on them audits your own edits (the second of the three exits below), not the plan.

## Gate 2 — the detail-grounded audit (after `detail`)

Once every step has a detail file, run the **same iterative audit again** before
implementation. This is the final gate; only here are the detail-level axes
un-withheld. Apply its conceptual findings by the same session-directed loop below.

## Infrastructure plans: claim scope only for resources the plan creates

**An infrastructure plan makes scoping, isolation, and least-privilege claims
only for resources whose creation pattern it defines.** Resources the toolchain
or the platform creates and needs to operate (a deployment tool's bootstrap
roles, account-level services, managed roles) are out of scope, because the plan
cannot change them: a fix that wraps one in a mechanism the plan does not own,
or claims isolation over it, is false. List them in the plan as named
exceptions, one reason each, as a closed list. Judge findings against a listed
exception as informational; a finding against any resource not on the list,
including a toolchain resource the plan forgot to list, still stands. An
exception never covers a resource the plan's own code creates.

**Both gates use the same session-directed convergence loop and the same
judgment, but different conceptual blocking bars** (see below). The bare-plan
gate is an early design gate, not a lighter one.

**Withhold vs audit stage.** `DetailBundleStatus.is_bare` (withhold: which axes
get `completeness-apply` actions) is separate from the **audit stage** that
selects the conceptual bar. Stage is derived once per invocation by
`derive_audit_stage`: `total == 0 → bare` even when `is_bare` is false.

## Stage-differentiated conceptual bar (`completeness-audit`)

Closed stage vocabulary: `bare` | `detail`, hoisted once per
`completeness-audit` invocation (`derive_audit_stage` in
`plan_tool/cli/completeness_phases.py`).

| Stage | Conceptual bar (`is_blocking_finding`) | Notes |
| --- | --- | --- |
| **bare** (Gate 1) | `plan-correctness` medium demotes only on `classify_domain` → `docs`; `plan-completeness` blocks only at high/critical (medium never blocks, any domain); nit/info never | `classify_domain=classify_finding_domain` at both stages now |
| **detail** (Gate 2) | `is_blocking_finding(..., stage="detail", classify_domain=classify_finding_domain)` | Medium demotes only on **docs**; **code-logic**, **unit-test**, and unknown domain all stay blocking |

Non-conceptual findings (deterministic layer, self-consistency, etc.) always use
`is_blocking(severity)` — the stage bar applies only to `plan-correctness` and
`plan-completeness` conceptual recs.

**Mid-run steering.** When deterministic convergence finishes but conceptual bar
blockers remain, the iterate loop stop kind becomes **`terminal_hand_apply`**
(not `converged`). Close those gaps through a session-directed assistant edit or via
`completeness-apply` (human at a TTY) — the iterate loop does not auto-apply
conceptual gaps in assistant-driven mode.

**Finalize / CI.** Clean eligibility requires a qualifying pass-conformance
sample that is **not** `budget_limited` ∧ bar-aware `has_blocking_findings` ∧
an eligible `outcome.stop_reason`. `audit_incomplete` is true when either
axis fails — pass-conformance (a malformed/failed pass) or `budget_limited`
(a well-formed sample that is still discovering at the pass cap) — and means
re-run with a live sample, not "raise `--audit-passes` first." Inspect
`--json` fields `stage`, `conceptual_bar_blocking_ids`, `audit_incomplete`,
and bar-aware `has_blocking_findings`.

**Three predicates — do not conflate:**

- `is_blocking(severity)` — pure severity floor; unchanged callers.
- `is_blocking_finding(rec, *, stage, classify_domain=...)` — **completeness-audit**
  conceptual bar only (bare vs detail above).
- `is_blocking_impact(rec)` — reconcile-loop blocking refresh and conceptual
  `material_new` only; **not** the completeness stage bar. `material_new` also
  takes `classify_domain` for the same docs-only demotion (stage-agnostic);
  reconcile-loop calls deliberately omit it.

The severity-aware **stopping rule** (BACKLOG #125) governs audit pass budget
and low-yield convergence — it is orthogonal to the stage bar.

**Deferred reporting polish** (full stop-reason vocabulary, set-aside handoff,
gate-2 tail copy): BACKLOG **#260**. BACKLOG **#261** settled (2026-08-11,
closed) that create/detail/reconcile deliberately stay on their own
predicates — not a pending unification.

---

# The session-directed convergence loop

> **`completeness-apply`, `direct-jira`, and `direct-run` are deprecated and
> going away (BACKLOG #376 in the `plan-tool` repo).** There is nothing
> unsafe about the mechanism itself. Why: walking findings one gap at a
> time — interactively, or via `--jobs N` — is slower than reading the whole
> saved report and applying a bounded, judged batch of edits, and that slow,
> piecemeal pace obscures whether the plan is actually converging (a
> recurring gap, a self-seeded finding, an arm-clustering pattern only shows
> up across the whole finding set and across rounds, not one gap at a time).
> `direct-jira` and `direct-run` exist only to chain that same gap-by-gap
> apply. Conceptual-finding application is moving entirely to whoever is
> driving `plan-tool` — a human at a TTY, or an assistant session — who
> already reads the whole report at once. The sections below still describe
> today's real, working behavior and the commands still run (each now prints
> its own deprecation warning); do not build new automation, scripts, or
> documentation on top of them. Read the saved report and make a
> session-directed edit to the plan/detail prose instead of reaching for
> `completeness-apply`.

This governs **both** audit gates above.

## Who is driving decides how conceptual gaps get closed

`completeness-audit --iterate` converges only its **deterministic
well-formedness** findings. The conceptual `plan-correctness` /
`plan-completeness` gaps are persisted **unapplied**; `completeness-apply` is
their sole mutator. *How* you close them depends on who is driving:

Interpret a completed audit report as a working hypothesis before treating its
findings as a plan-gap decision surface: verify cited code claims, group related
in-scope gaps, and apply bounded corrections that serve the stated plan intent.
An ordinary final with confirmed, current evidence is required to certify
convergence or to support a scope-changing disposition; it is not required to
begin the session-directed edit → commit → re-audit loop. If
`no-qualified-current-evidence` applies, do not re-run unchanged plan text
merely to obtain qualified evidence. First triage and correct through the session the
actionable in-scope plan gaps from the completed report, then run a fresh
grade-matched audit against the changed committed snapshot to measure the
effect. A budget-limited report alone cannot justify expanding, splitting, or
withdrawing a plan; those scope decisions remain user-owned.

- **Assistant-driven (the default whenever you auto-drive, non-interactively):**
  do **not** invoke `completeness-apply`. It is a human-review surface and it
  misbehaves when auto-driven — its interactive `--jobs 1 -y` walk **skips on
  non-interactive stdin** (applies nothing, reports the pending gaps, exits 2),
  and `--jobs N` applies every gap **without judgment**. Instead: run
  `completeness-audit --iterate` to converge the deterministic findings, then
  read every completed saved report. Treat budget-limited or unqualified
  conceptual findings as hypotheses: map the in-scope plan-level gaps as below,
  verify their code claims, and edit the plan/detail prose **yourself** where
  the correction serves the plan intent. A qualified final is required before
  declaring convergence, not before correcting the identified gaps. Commit the
  correction batch and re-audit the changed snapshot, while **pausing on any
  genuine product question rather than blind-applying** — see "Pause on a
  product question — ask, don't infer" below for the test and the required
  stop-and-ask.
- **A human at a TTY:** `completeness-apply`'s interactive `--jobs 1` walk **is**
  the intended review-and-apply path. Reserve the command for that.

The same split governs **every** interactive surface (review/reconcile walks,
structural-escalation confirms): a human uses the walk; when you auto-drive,
supply the session's judgment wherever the interactive path would skip or
blind-apply. Packaged unattended pipelines (`direct-jira` / `direct-run`) are a
distinct third mode and legitimately auto-apply — that is what they are for.

## A plan's target (`run` vs `jira`) changes the remedy, not the audit bar

`completeness-audit`'s blocking bar is identical whether a plan will execute
through `plan-tool run` or ship as Jira stories for a human developer. Do not
invent a leniency mode — relaxed `is_blocking_finding`, a skipped ambiguity
check, "a human will read it so this can stay unresolved" — keyed on the
downstream consumer. Run-grade detail stays the one canonical, fully-audited
artifact regardless of who or what consumes it next.

Two settled decisions establish this rather than leaving it to instinct.
`detail --grade jira` (the compact Jira-grade detail lane) was disabled
2026-08-24 because that contract sheds the implementation facts — call sites,
exact edits, test rosters — that ground confident findings; a thinner artifact
audits worse, it does not audit more leniently on purpose. BACKLOG #169–171
(withdrawn 2026-08-21) rejected letting a Jira-facing artifact carry
implementation-planning confidence before a grounded implementation route
exists. A target-aware leniency mode reopens the same gap through a different
door: relaxing the check instead of shrinking the artifact still loses the
class of finding that matters most — a missing shared function, a wrong claim
about what a queried call actually does, anything a human implementer needs
exactly as much as an unattended one.

**What legitimately differs by target is the remedy you pick once a finding is
confirmed real, not whether it is raised or how severely:**

- An **ambiguity finding** — a genuinely unselected mechanism, not a
  factual or structural defect — on a `run`-targeted plan usually needs a
  deterministic guard in code: an unattended worker cannot ask a human.
- The same class of finding on a plan whose output is a Jira handoff can
  instead be closed by narrowing scope plus an explicit, documented
  Risk/Deferred note — a human implementer reads it and applies judgment. This
  is exactly what `jira --developer-handoff` already renders as suggested
  guidance rather than a binding requirement (`JIRA_FORMAT.md`'s
  "Developer-handoff companion" section).
- Findings about **factual accuracy, missing shared functions or call-site
  consistency, or architectural soundness are never eligible for the lenient
  remedy** — they are implementation facts, not ambiguity, and need the same
  fix regardless of target.

**State the target once, explicitly, when it is `jira`.** Add a line to the
plan's Overview/Outcome or scope fence — e.g. "this plan targets Jira handoff;
a human implements from the resulting stories, not `plan-tool run`" — so
whoever applies a confirmed finding later picks the right remedy shape without
re-deriving the distinction from scratch. This is guidance for the applier,
not a new audit input: it changes no gate, prompt, or blocking predicate.

## Before applying anything: audit the why, not the what

Every expensive audit mistake has one shape: **the mechanism stays correct while
the purpose goes unserved** — findings get *applied* instead of *interpreted*.
It recurs structurally, not through carelessness: **validity is local, necessity
is global, and only validity is visible from inside the loop.** A finding is
judged against the artifact in front of it, so it can be entirely right about a
thing that should not exist. No lens asks whether the step it names belongs. If
the session does not ask, nothing does.

**This is one half of a two-sided test.** *True to intent* — this section's
subject — means the mechanism actually makes the plan's stated intent hold; a
finding can be applied everywhere and still leave the purpose unserved.
*Proportional to intent* is the other bound (`Keep the work proportional to
the chosen intent`, Gate 1 above): the mechanism is no bigger, no more
general, and no more configurable than that same intent requires. A
correct-but-disproportionate mechanism is scope creep with a clean audit
trail; a proportionate-but-untrue one is exactly the failure this section
names. Check both, not whichever one the finding in front of you happens to
raise.

**The six named tells:** `arm-clustering` (material conceptual findings form a
strict-majority, contiguous proper arm of committed plan steps),
`check-saturation` (every part is correct but no producer delivers the intended
value), `measurement-instrument-adequacy` (a measurement instrument can't see
the data a decision relies on), `self-seeded-finding` (findings describe the
prior audit edit rather than the artifact), `remedy-proportionality` (the
proposed remedy outgrows the defect), `premise-conditioned-design` (a step's
design differs by the outcome of an investigation the same plan contains).

**The override rule.** When one of the registry's shapes fires it is a **scope
decision**, and the standing rule for scope decisions applies: **surface it to
the user rather than self-adjudicating.** You may not proceed to apply findings
until you have, *in the user-facing response*, (1) named which arm/step the
findings cluster in, with the count; (2) stated why that arm belongs — or
proposed carving it; (3) said plainly that you are overriding the signal, if you
are. A silent override is the defect.

**Count the clusters explicitly.** The one shipped detector cannot see most
real cases: `--audit-passes 1` disables it outright (no consensus target from a
single sample), a one-step concentration can never fire it (the arm must also be
a step majority), and a `detail` completeness tail computes none at all. Silence
from the detector is not evidence the tell is absent, and a single over-packed
step is the *common* shape.

**Present plan gaps before making a scope decision.** When current qualified
evidence leaves in-scope, plan-level gaps — findings whose remedy could change
the plan body, step graph, acceptance criteria, or stated contract — use this
format. The raw audit list is ordered by source and severity, which can hide
that several plan gaps describe one contract or one contiguous arm. Before
applying those gaps or asking the user to override a shape signal, group them by
the responsibility they describe. Start with `Plan intent:` and one short,
faithful restatement of the plan's stated intent. Then present a compact map
with these columns:

| Related findings | Relevant steps and intent | What happened | Possible next step |
| --- | --- | --- | --- |
| source, severity, stable anchors, and a short neutral finding label | named step ids/titles plus each step's intended outcome in short plain language | a direct conversational summary of the relationship between the findings and the plan | a suggestion to review, clarify, apply, defer, carve, or otherwise investigate — not a decision for the user |

- **Keep non-plan output separate.** Do not force deterministic diagnostics,
  detail-only implementation mechanics, out-of-scope suggestions, or audit
  telemetry into the plan-gap map. Present them separately when they matter,
  with the context needed to understand them.
- **Group by responsibility, not phrasing.** Findings with different anchors or
  sources can still describe one shared result contract; conversely, repeated
  wording can name independent responsibilities. State that connection plainly.
- **Attribute plan-level findings explicitly.** Saved recommendations can have no
  `step_id`; map them from their cited step title, file, acceptance criterion, or
  architecture concept. Mark an uncertain target rather than silently assigning
  it.
- **Restate intent as a scope anchor.** Quote or faithfully summarize the plan
  intent before the map, then state the intended outcome of every step named in a
  row. This gives the reader enough context to see whether a finding serves the
  plan or has drifted into adjacent work. Do not infer an intent the plan does not
  state; say that it is not stated. This is presentation and scope context, not
  permission to re-audit or weaken the plan's settled intent.
- **Add an arm assessment under the table.** Give the contiguous affected steps
  as `N of M`, the material findings in that arm as `N of K`, and say whether the
  group is one coherent contract with its consumers or an accidental feature arm
  that should be carved.
- **Explain what happened, not what it means.** Preserve the auditor's source,
  severity, and anchors, but do not add role labels, status labels, blocking
  declarations, or a verdict such as “ready” or “not ready.” Explain the facts
  in short conversational language, then offer a possible next step.
  The user decides its priority, meaning, and disposition.
- **Keep this advisory.** The map improves the human scope discussion; it is not
  a new gate, does not force a split, and does not choose an apply target. If it
  reveals a credible arm, use the override rule above and surface the choice to
  the user even when the shipped detector was silent.
- **Keep decisions human-owned.** Preserve source, severity, and stable anchors
  so the user can assess the evidence, but do not label the plan ready, choose
  apply/defer/carve, or turn the map into a verdict. Deterministic diagnostics,
  implementation mechanics, out-of-scope suggestions, and telemetry remain
  separate from this advisory plan-gap map.

> The authoritative shape registry is the marked table in the `plan-tool` repo's
> `CLAUDE.md` (`<!-- plan-tool:audit-shapes -->`) — it is tool-owned and
> drift-checked by `plan_tool/cli/inspect.py`, so it lives there, not here.

## Pause on a product question — ask, don't infer

Some findings the audit loop surfaces are not correctness bugs a session can
resolve by reading more carefully — they are **product/design questions**: the
plan (often the Architecture section itself, or Architecture against a step)
states two mutually exclusive behaviors, each written with real deliberateness
— its own prose, its own test names, its own acceptance criteria — and no
other passage in the plan, detail bundle, or code already picks a side.
Closing that finding is not *discovering* which statement was already
authoritative; it is *choosing* one, and the choice has downstream behavioral
consequences (what the code does, not just what the prose says). The session
has no standing to make that choice alone.

**Test it before applying anything.** For every conceptual finding that names
a contradiction, ask: does an already-written passage elsewhere in the plan —
a more specific Architecture clause, a Testing/Acceptance criterion, a
sibling step's established pattern, or a hard constraint like execution order
— already settle which side wins? If yes, this is an ordinary correctness fix:
apply it through the session-directed loop above, citing the passage that
settles it. If no tie-breaker exists and both sides are independently
deliberate (not a stray or clearly-stale line), it is a product question.

Two findings that look identical on the surface — "step X contradicts
Architecture" — can resolve differently under this test. A step that merely
drifted from an unambiguous, singular Architecture statement (nothing else in
the plan disagrees, and the drifting step shows no sign of a considered
alternative) is a correctness fix: align the step to the stated intent. A step
that contradicts Architecture with its own dedicated test name, its own
acceptance criterion, and its own implementation rationale is a fork between
two considered designs — the volume and specificity of the disagreeing text is
itself evidence of deliberateness, not proof that either side is "right."

**When a genuine product question fires, stop and ask — do not narrate and
proceed.** This is stricter than the override rule above: narrating a scope
decision and proceeding under your own judgment is what the six named shapes
allow, because those are signals about the artifact's *shape* (does this arm
belong), not its *substance* (what should this mechanism do). A product
question is about the substance itself. Before writing any plan/detail edit
for that finding:

1. State the contradiction in plain terms — what the plan currently says on
   each side, quoting both, and why they cannot both be true.
2. Give the concrete resolutions actually available (not just "please
   clarify") — including what each one costs or changes elsewhere in the plan
   (a test that needs renaming, a dependency that needs adding, a mechanism
   that needs specifying on the other side of the fork).
3. Ask the user directly and wait for the answer before touching the plan or
   detail bundle for that finding. Use the interactive-question tool your
   environment provides; a question buried in a longer status update that the
   session then proceeds past is not a pause.

The same holds when a finding has no contradiction but its only remedy is
choosing between valid product behaviors (single or parallel runs, cookie or
token, block on stale or warn): ask; never invent the choice to clear the
finding. **Record the answer as one decision line in the plan, with its date
and the audit report id**, so the next audit reads it as settled. A choice the
owner explicitly deferred stays deferred: state the property every option must
meet, not a pick.

**Only the product-question subset blocks.** Every other finding in the same
report — the ordinary correctness fixes the test above already resolved —
keeps flowing through the session-directed loop in the same round: apply,
commit, and re-audit. Do not let one open question stall the rest of the
report, and do not widen it into a reason to delay applying findings that the
test already settled.

## Fix the class, not the cited spot

A finding names **one instance** of a defect that usually has siblings. Run all
five checks — they are mechanical and none needs another model call. **Check 0
runs *before* you edit; 1–4 before you call the gap closed.**

0. **Enumerate the sites before editing any of them — an explicit step with a
   written-down result, not an instinct.** Name the defect as a *class* in one
   sentence, then run two searches and record what they return: **by identifier**
   (the symbol, id, path, flag, predicate the finding names) and **by
   vocabulary** (the concept's *words*, in other phrasings). Apply at every site
   returned, or state per site why it stays. An enumeration you didn't write
   down is one you didn't do. Doing this up front is what makes the edit itself
   class-wide, and it is markedly cheaper than re-deriving the class after a
   partial sweep shipped.
1. **Read `suggested_action`, not just the body.** The auditor already computes
   the remedy's scope and renders it as a `- Fix:` sub-bullet.
2. **Restatement: grep the changed *phrase*, not the changed identifier.** The
   same contract is restated in the plan body, the format doc, and every
   consuming step; an identifier sweep misses prose saying the same thing in
   other words. This is the vocabulary half of check 0, run as a post-hoc audit.
3. **Set completeness and implication.** If the change touches one member of a
   set, do all N; and if it adds a rule, add what the rule obliges — a test, an
   acceptance criterion, a result field, an error message. A rule with no test
   is the single most common re-seed.
4. **Check the remedy against the *goal*, not just against the finding.** Checks
   0–3 all ask "did I apply this everywhere?" and none asks "does what I applied
   actually work?" Write down the property the fix is supposed to produce, then
   trace the mechanic against it on the **common** input, not the edge case.

**When a remedy's justification is a claim about the code, verify it against the
code before applying.** A one-command `grep` for the call sites routinely
invalidates the stated reason, and the false half is usually load-bearing for
the placement.

**A green test suite is not evidence the sweep was complete.** Each un-swept
site carries tests pinning *its* current behavior, so a one-site fix stays green
**because** the class is incomplete. Green is evidence about the site you
changed and **no evidence at all** about the ones you didn't. **A red sibling
test during a class sweep is the expected outcome, not a reason to narrow the
fix** — read each one to decide whether the site is a genuine carve-out (assert
it as one) or a missed instance (update it). Prefer one parametrized test over
the whole consumer set so the next site added fails loudly instead of silently
inheriting the old behavior.

**Check 0's sweep and check 4's goal-check are not sequential stages — replaying
the same remedy at every matched site is not the same as checking that remedy's
*shape* against the goal.** Enumerating sites, applying the cited finding's
specific mechanism symmetrically to each one, then checking once at the end
can pass every step and still be wrong: a remedy that only ever *grows* (an
exclusion naming one more bad case each round) can satisfy every site it is
swept onto and still never satisfy the goal, because the goal was never
restated as a positive property to test the mechanism's shape against — only
as "does this cover the sites found so far." Before sweeping a remedy across
sites, write the goal as what must be **true** (a positive property), not only
what must be **excluded**; when the remedy itself is exclusion-shaped (a
blocklist, a `!=`, a "not X"), that shape is a tell to ask whether an
inclusion-shaped remedy (an allowlist, a `==`, an "is X") states the same
property more simply and more completely, before propagating the exclusion
shape to every site the sweep finds.

**Measured 2026-09-18 in `plan-tool` on `roadmap-revision-rollback`'s
checkpoint-reconciliation mechanism (steps 2 and 3).** Four consecutive
detail-grounded audit rounds found a real, code-verified defect at the
identical two sites (a continuing stage run, and restore), each self-seeded by
the previous round's own fix. Three of the four rounds were closed by
*sweeping* — correctly, by check 0's own rule, applying the same fix
symmetrically to both sites — while the remedy's shape stayed an exclusion
list (first excluding one other writer's journal kind, then adding a
members-must-be-tracked check beside it), which is provably incomplete against
a journal shared by eight legitimate writers, no enumeration of which the
audit (or the session re-deriving it) got complete on the first two tries.
Round four replaced the exclusion list with a one-line allowlist — the single
kind the site's own code can ever produce — collapsing an open-ended
enumeration into an equality check correct regardless of how many other
writers exist, known or not yet written. The first three rounds were not
failures of check 0 (the sweep was genuinely complete each time, for the
remedy as stated) or of check 4 as normally applied (each fix was verified
against its own cited finding); they were a failure to ask, before sweeping,
whether the remedy's *shape* — not just its coverage — could ever be complete.

### A finding that names another plan is fixed in every plan at once

When a finding names another plan's section, the class spans plans. Write the
shared contract once (owning plan, operation, invariant), apply it to every
named plan in one batch, and re-audit them together. Before closing a class
such as owner-only access, list every operation in every plan it governs.
Fixing one plan per round re-seeds the finding in its sibling.

## Filing a backlog or bug entry

**Write every entry, ticket, and heading for a person who has not seen the
code.** Plain words and full detail go together: keep the precision in the body
and say it simply.

- The heading is one plain sentence naming what goes wrong (or what is wanted),
  when it happens, and the visible effect. Name the command a user runs, not
  only the internal module; put file paths and function names in the body.
- Say what fails: an error, a wrong result, or a lost record, and what triggers
  it. A verb such as "raises", "trips", "discards", or "leaks" on its own does
  not say what happened.
- Expand abbreviations, terms of art, lint or error codes, and review shorthand
  ("the same shape as a sibling fix") on first use.
- Keep every fact. Plain is not shorter: keep the numbers, ids, paths, line
  references, and reproduction steps.

Before: "`manifest sweep` can raise while printing an archive target reached
through a symlinked repository path". After: "`plan-tool sweep` fails with an
error while printing its report when the repository path goes through a
symlink".

Follow the repository's own entry format when it has one. In the plan-tool
repository that is `docs/TRACKING.md` § "Adding a new entry".

## Trajectory, stopping, and the three exits

**Use three completed audit snapshots as the minimum trajectory window.** One
establishes a baseline; the second shows whether the correction moved the
finding set; the third distinguishes a real trend from reviewer variation.
Compare stable finding identities and material severities, not raw counts. A
falling count is evidence to continue only when the remaining findings are
becoming less material or narrower.

**Severity-aware stopping rule.** Treat **two consecutive diminishing-return
passes** as operational convergence when each adds at most one new
`low`/`info`/`nit` finding, or only advisory-severity findings. Report that as
**low-yield convergence**, not a clean audit, and retain the advisory findings.
Any new material correctness/completeness finding resets the streak;
deterministic/data-integrity failures never qualify. `[out-of-scope-deferred]`
findings must not reset the streak nor justify raising the pass cap. A singleton
tail is **not** converged merely because its count is one — severity is
load-bearing.

**Before spending a `plan-tool split`, `plan-tool scope-out`, or a re-seed on a
recurring finding, trace its provenance first.** A finding that recurs because *your own
last edit was wrong* is not evidence of mis-decomposition. Compare retained reports (or
their retained conclusion summaries), documented decisions, current code and existing
tests to distinguish an original defect from an incorrect prior fix. Use `git log -S` on
the finding's subject when relevant revisions are available. If retained evidence cannot establish why the finding recurs, report that
uncertainty to the user before proposing structural rework; do not infer a structural
defect or invent provenance. (The retired region-trending `spinning`/`FORK_*` layer —
BACKLOG #251 — once mistook that pattern for a mis-decomposition; the layer is gone, the
judgment rule remains.)

**Keep driving rounds until one of exactly three exits fires — a falling count
is not one of them.**

1. **Converged** — a clean audit, or the low-yield condition above. Go execute.
2. **The loop is auditing your own edits** — new findings predominantly describe
   your last round's applications rather than the plan. Do **not** stop
   applying; finish the application completely, then go execute, where a
   mismatch becomes a failing test instead of a finding.
3. **Non-converging** — the same finding or region resurfaces across rounds, or
   a fix needs structural rework you cannot land inline. Stop and surface it to
   the user, or file it in the repo's `BACKLOG.md` / `BUG_BACKLOG.md`.

Distinguishing 2 from 3 is **per finding, not per round**: classify each new
finding as plan-defect or self-seeded before reading the round. A round that is
mostly self-seeded still contains real gaps worth applying.

---

# Execution and the post-run tail

## `--iterate`

**Use `--iterate` on every command that supports it except `detail`; never pass
`--no-iterate` by default.** Availability and defaults differ: `create` defaults it
**ON**; `completeness-audit` defaults it **OFF**, so pass it there explicitly; `detail` defaults it **OFF** (a one-shot write
— don't opt back in unless asked). Neither `detail --reconcile` nor
`run --reconcile` accepts `--iterate`; standalone reconcile verbs do not
accept iteration flags. Read saved reports and drive judged corrections
through separate committed invocations instead.
Don't tack it onto commands where it is a no-op (`run`,
`review`, `verify`, `jira`) — it warns or errors.

**"Make the plan as complete as possible" is not a request for `detail
--iterate`.** `detail` stays one-shot unless the user explicitly asks for its
loop. That request means: `create` (which iterates by default), then `detail`,
then the detail-grounded `completeness-audit <name> --iterate` (Gate 2).

## `--commit`

**Commit before every `plan-tool` invocation, and prefer `--commit` where the
verb accepts it.** Before launching `create`, `detail`, `completeness-audit`,
`run`, or any other long-running plan-tool command, land a git commit of the
working tree so the pre-call baseline is clean and the next call has a durable
checkpoint. Session-directed audit fixes use the same rhythm: apply batch → commit
→ re-audit (never audit against an uncommitted apply). Prefer the tool’s
`--commit` flag on every surface that supports it rather than relying only on
separate mid-command commits.

Only five surfaces accept `--commit` — `run`, `detail`, `completeness-audit`,
`completeness-apply`, `manifest sweep`; don't tack it onto one that doesn't.
Pass it by default on those five when you drive the pipeline.

On `run` specifically, `--commit` commits each **green step**. This is
load-bearing for the **test-authoring gate**, which isolates a step's coverage
as the post-call git-changed delta against a pre-call baseline. Run steps
back-to-back **without** committing and an earlier step's files stay dirty, so
a later step's edits to an already-dirty shared file fall inside the baseline,
get masked out, and the gate **wrongly blocks advancement** even though the
step did author a test. This standing mandate authorizes those commits while
you drive the pipeline. Withholding commits to inspect first means advancing
**one step at a time**, committing separately between steps or audits.

`detail --commit` is also per-step — it commits each converged step as it lands,
keeping an interrupted batch's completed steps durable.

**A worktree that is dirty on purpose.** When the tree holds changes the user
means to keep out of the plan's history, do not `git add -A` or sweep them into a
commit. Commit by explicit path (`git commit <paths>`), so the baseline holds
only your edits and theirs stay untouched; `--commit` on a verb that refuses a
dirty tree cannot be used there, so land the commits by path and run without it,
one step at a time.

### When a `run` step's own tests fail

**Fix the defect by hand, commit it, and accept the step with `run --accept`.** A
step that clears its claude call but fails a gate stays `current` with a
`status_note`, and the tree keeps its edits. When the failing test is the step's
own defect (a wrong assertion, an invalid fixture, a missed case), the tool's
re-run path cannot land it: it does not tell the model which tests failed, so the
re-run changes no test file and the test-authoring gate blocks the step even though
its tests exist. `--commit` also refuses to start over a dirty tree. `--accept`
is the route that lands it. Recover in this order:

1. **Inspect.** Read `git diff` and the failing test. Confirm the implementation
   delivers the step's stated outcome; a failure that shows missing or wrong
   behavior is not covered here (revert and re-run, per `RUNBOOK.md` § "Step failed
   with uncommitted edits left in the tree").
2. **Fix the smallest defect by hand** in the step's own files, then sweep the
   step's other new tests for the same defect before re-running anything.
3. **Run the full suite to green** (`uv run pytest tests/ -q -n auto`). A hand-fixed
   step is certified by the whole suite, not by the one test that failed.
4. **Commit the step's code and tests as one bounded commit**, leaving the plan
   file out. The failed gate left a `status_note` in the plan, so the plan being
   dirty is expected; `--accept` tolerates the plan file and its lessons log and
   refuses any other uncommitted change.
5. **Accept the step through the tool:** `plan-tool run <slug> --step N --accept
   --commit`. It runs the plan's `test_command` and the step's `gate`, and only
   when they pass marks the step `done`, clears its `status_note`, promotes the
   next runnable step (or completes the plan), appends the lessons entry, and
   commits the plan and lessons files only. On a red gate it writes nothing. It
   accepts only a step a failed gate left behind (`current`, or `pending` with a
   failed-gate `status_note`), so a mistyped id is refused. Build output the suite
   left untracked is not committed: ignore or remove it before step 6.
   It refuses a plan with neither a `test_command` nor a step `gate`; there, hand
   the decision to the user rather than editing `status:` yourself.
6. **Continue with `run --commit`** from the clean tree for the remaining steps.

Never hand-fix and then bare re-run: the re-run re-drives the model over the dirty
tree and trips the test-authoring gate. Never mark a step `done` by hand-editing
`status:` (it skips promoting the next step and can leave a step runnable), and
never use `--skip-merge-check` or a plan-wide `enforce_step_tests` change to get
past a test failure. Record the failing test, the hand fix, and the
suite result in the handoff. Redoing the step from a clean tree is the alternative
when the implementation itself is wrong; it costs a model pass and can reproduce the
same test defect.

## Feature-branch durability and merge order

**The default branch is protected: use a plan pull request before `run` reads
the bundle.** Start a plan branch from the intended default-branch base and
keep only plan artifacts on it: the seed commit, generated plan, every
session-directed audit correction, and each `detail --commit`. Push that plan
branch after each bounded commit and merge its pull request only after both
completeness-audit gates converge. Never push directly to the default branch,
even when credentials allow it. The merged plan and detail bundle must be on
the default branch before an implementation run starts.

In a repository with an `origin`, `run` enforces the same requirement
regardless of route: it refuses on the default branch itself, and refuses
until the plan and a detail file for every committed step are on
`origin/<default>` (`git fetch` first). Verify the merged plan pull request
through that remote branch before creating the implementation branch. Do not
pass `--skip-merge-check` to get past the refusal when the bundle has not
actually landed; merge the plan pull request, or ask the user.

Then branch from the updated `main` and `run --commit` there. Push that branch
after every green `run --commit` step and every bounded review or
reconciliation fix. A local commit is a checkpoint; its pushed feature-branch
copy protects it from checkout loss, machine loss, and accidental cleanup.

Completion means the plan's implemented steps are green and committed, its
required post-run `reconcile-code` and code-review tails have converged, its
documentation and tracking records are reconciled, and the final worktree is
clean. Then merge the reviewed run branch through its pull request; never push
directly to `main`. Do not merge a partially executed plan's code merely
because some steps are durable; leave it on its feature branch until its
stated completion contract is met.

### Select the pull-request system before use

Before creating, inspecting, commenting on, or merging a pull request, verify
the target system and repository rather than inferring them from the checkout:

```bash
git remote get-url origin
git branch --show-current
```

- An `origin` on `bitbucket.org` uses `bkt`. Run `bkt context list` and
  `bkt repo view` to confirm that the active context selects the expected
  Bitbucket host, workspace, and repository before any `bkt pr` command.
- An `origin` on `github.com` uses `gh`. Run
  `gh repo view --json nameWithOwner,defaultBranchRef` to confirm the expected
  GitHub repository and base branch before any `gh pr` command.
- For another host, an ambiguous remote, or a mismatched CLI context, stop and
  resolve the target with the user. Do not create a pull request through the
  other CLI or by guessing a repository flag.

Use the verified source branch and default branch in the create command. A
configured CLI context is not evidence that it matches the current checkout.

### Opening Bitbucket pull requests with `bkt`

Use the Bitbucket CLI (`bkt`, <https://github.com/avivsinai/bitbucket-cli>) for
all Bitbucket pull-request lifecycle work: create, inspect, comment, review,
and merge. Do not use an Atlassian MCP tool for Bitbucket pull requests;
reserve that integration for Jira and Confluence. Resolve the Bitbucket
workspace and repository from the verified remote; internal workstation
settings may live in ignored local context.

**One-time setup.** `bkt auth login` (the OAuth token expires; `bkt auth status`
shows when), then bind the repository so commands need no flags:

```bash
bkt context create plan-tool --host https://api.bitbucket.org/2.0 --workspace <workspace> --repo <repository> --set-active
```

The host is the key `bkt auth status` prints for the Cloud login
(`https://api.bitbucket.org/2.0`); `--host bitbucket.org` is refused with
`host "bitbucket.org" not found`.

Without an active context `bkt pr list` refuses with `no active context`.

**Creating the pull request.** Opening one publishes the branch's content to
the team, so confirm with the user before the first `bkt pr create` for a
branch; approval for one pull request does not carry to the next.

```bash
bkt pr create --source <branch> --target main \
  --title "IPPT-123: <one concern>" --description "$(cat .tmp/<slug>.pr-body.md)"
```

- **Title** leads with the ticket key (`CONTRIBUTING.md` § "Commits"). Read the
  body from a file, never inline: bodies carry backticks and quotes.
- **Body** carries what `CONTRIBUTING.md` § "Pull-request review: team
  checkpoint" requires: outcome and settled decisions, the merge-base review
  range, checks run, changelog fragment or the reason for none, and the
  related backlog entry and ledger.
- **`--draft`** while a gate is still open (an unconverged completeness audit,
  an unfinished review tail); `bkt pr publish <id>` when the branch is ready
  for a bounded review.
- **Plan and code are separate pull requests** (§ above): the plan pull request
  holds only plan artifacts and merges before `run` reads the bundle; the run
  branch's pull request follows. Create each from its own branch.
- **Link it:** comment the pull request URL on the Jira ticket
  (`docs/TRACKING.md` § "Labels, statuses, and comments").

**Checking state.** `bkt pr view <id>`, `bkt pr checks <id>` for CI, and
`bkt pr comments <id>` for review threads (record each with its disposition in
the review ledger). Verify a plan pull request has merged with `bkt pr view <id>`
*and* `git fetch` then `origin/main`: `run` reads the remote branch, not the
pull-request state.

**Deliberately not done by a session:** `bkt pr merge`, `approve`, `decline`,
and `auto-merge`. Merging is the Architect's approval (`docs/TRACKING.md`), and
a session approving or merging its own pull request removes the review the pull
request exists for. Run them only when the user explicitly asks for that one
action.

**If `bkt` is unavailable or unauthenticated,** report it and give the user the
compare URL `git push` prints; do not fall back to a direct push to `main`.

### Opening GitHub pull requests with `gh`

For a verified GitHub target, use `gh pr create`, not `bkt` or an Atlassian MCP
tool. Write the review body to a file and pass it with `--body-file` so quotes,
backticks, and newlines remain intact:

```bash
gh pr create --head <branch> --base <default-branch> \
  --title "<one concern>" --body-file .tmp/<slug>.pr-body.md
```

Use `gh pr view`, `gh pr checks`, and `gh pr comment` for the corresponding
GitHub review work. The same review, validation, and merge-authorization rules
above apply regardless of the hosting system.

## The two reconcile verbs are not interchangeable

They differ in **which side is canonical**, which makes each correct in exactly
one direction of time.

- **`reconcile-plan` — code is canonical, mutates the plan.** Legitimate use is
  **before** execution: re-grounding a plan whose codebase moved on since
  authoring. `--refresh` is its cheap fingerprint-gated form.
- **`reconcile-code` — plan is canonical, mutates the code.** This is the
  **post-execution** direction.

**Never run `reconcile-plan` against work a `run` or `jira` execution already
produced.** After a step runs, the code exists *because of* the plan; pointing a
code-canonical audit at it hands the implementation authority over the intent
that produced it, so under-delivery reads as an over-promising plan. The
prompt's refusals (no scope-narrowing, no criterion-softening, flip `status`
instead) are a guardrail on a verb pointed the wrong way, not permission to
point it that way — and the `status` flip does nothing for a step a green run
already marked `done`. On an executed plan use `annotate` (never mutates its
source) to judge it and seed the next iteration.

**The sharp case:** a plan/detail claim that is *false about the code* is **not**
a reason to run `reconcile-plan` post-execution, despite superficially matching
its direction. Correct it through a session-directed edit, and state which way the discrepancy resolved — a
code-canonical audit pointed at the same discrepancy would just as readily
propose the inverse.

## After `run` finishes a plan

Green steps are not the finish line. Drive two more loops:

1. **Plan-canonical code reconciliation** — `reconcile-code <name> --all`.
   It has no built-in `--iterate`. Run a complete sweep, save every per-step
   report, and use its real audits as the drift signal; `--dry-run` only
   *renders the prompts*. A complete sweep is the whole eligible step set, not
   one clean step or a partially interrupted run.
2. **Code review** — a `/code-review` pass, fixing confirmed logic defects and
   re-reviewing to convergence. The convergence question is whether the plan's
   behavioral properties, authority boundaries, ordering rules, error paths,
   callers, and regression coverage are true in the shipped code — not whether
   a reviewer has exhausted wording or future-maintenance suggestions. Triage
   each finding against code and tests; keep documentation accuracy and
   speculative refactors separate from a logic verdict. Against the latest
   logic-changing commit, require two independent consecutive clean or
   explicitly low-yield passes that record their reviewed range, method, and
   finding verdicts. A documentation-only correction must be tested and
   reviewed for accuracy, but does not reset that logic-convergence window.

For a Claude Code CLI review, commit the reviewed snapshot first and name a
findings file under the project's `.tmp/` directory. Prompt the Claude instance
to run `/code-review` in report-only mode and **write its consolidated findings
to that exact file before returning**. The file must identify the reviewed
commit or range, method, and each finding with its failure scenario, or state
an explicit clean verdict. A subagent note or terminal-only summary is not the
review artifact. Permit the findings-file write, but forbid code edits in the
review prompt. Use `claude -p --output-format stream-json --verbose` to observe
progress — or `claude-personal -p …` on a machine where plain `claude` is not
the launcher, where it is an alias that only prints a reminder and starts no
session, so a review launched through it never runs. Give each launch a fresh
`--session-id`: a stopped or failed launch has already registered its id, and
reusing it exits immediately with "already in use". Retain the session ID for
`--resume` if the file is missing, and read
the saved file before triage. A quiet review remains running until it exits or
the operator explicitly authorizes stopping it.

Do **not** insert `completeness-audit` / `completeness-apply` into this tail —
those audit the plan's own design and detail bundle, not the implementation.
Both loops exit by the three exits above.

### Post-run reconcile-tail stop rule

After **three completed full sweeps**, do not launch a fourth merely because a
report still contains model-suggested work. First record a short handoff triage
for every remaining finding: the governing plan property, the existing test or
reproduction checked, its direct code sites, and the next bounded action.
Treat the report as a lead, not a classification oracle: its source, impact,
severity, wording, and named file never by themselves decide whether the loop
continues or blocks.

Continue with a focused action when the triage proves one of these cases:

- A plan acceptance property, authority boundary, safety invariant, ordering
  rule, or contradiction in the shipped implementation is false. Apply the
  class-wide code correction, add the focused regression test, and re-run the
  affected tests.
- The implementation is correct but a concrete test or test fixture is absent.
  Add that focused coverage and validate it; do not use another model sweep to
  discover adjacent coverage ideas.
- The outstanding item depends on an unavailable external runtime,
  configuration, credential, or capability contract. Preserve the fail-closed
  behavior, record the evidence required to unblock it, and defer it rather
  than weakening an invariant or recasting it as an implementation defect.

A further **full** `reconcile-code --all` sweep is warranted only after a
verified class-wide implementation correction, a newly reproduced
safety/authority failure, or a material code change that can invalidate the
previous sweep. Otherwise move to code review. Reports persist per-step
results rather than a sweep boundary, so the handoff must name each completed
sweep and its report range. This is a judgment-only policy guard: it does not alter
blocking predicates, exit codes, prompts, or model-generated finding labels.

## Direct changes get the same loop

A change implemented directly (Edit/Write, outside `create` / `detail` / `run`)
gets no automatic convergence loop unless you drive one through the session: audit the change
for correctness *and* completeness, fix what surfaces, re-audit until it
converges, re-running affected tests and a review pass each round. A one-shot
direct edit is the same unconverged hazard `--no-iterate` is. Close the finding
with the smallest change that makes it true, not the most general, complete, or
reusable version of the fix — a fixed check over a rule engine, one direct call
over a pluggable interface, a literal over a config knob. Broaden it only when
the finding itself cannot be closed without the broader change.

---

# Authoring hygiene

**Feed `create` a seed file via `--from-existing <path>`, not an inline `--from`
string.** A seed file is reviewable, diffable, and re-runnable; a long inline
`--from` is none of those. Reserve `--from` for throwaway one-liners.

**Use the canonical H2 section names** so the seed's prose lands in the plan body
instead of falling through to `_(TODO)_` placeholders — `_render_plan_body`
matches by case-insensitive exact name, with no synonym mapping:

`## Overview` · `## Problem statement` · `## Architecture` ·
`## Scope of work` (extracted to `## Steps`) · `## Out of scope` · `## Risks` ·
`## Testing` · `## Acceptance criteria` · `## Deferred`

Free-form sections that don't fit (design decisions, context already in place)
fold into `## Architecture`; if they fit nowhere canonical they belong in
per-step detail files, not the seed.

**Seed size:** below 16 KB a seed skips distillation (assumed canonical-shaped);
above it, a distill pass either reorganizes into canonical sections or returns a
multi-plan split proposal. No truncation. Opt out with `--no-distill`.

**State the seed's commitments explicitly — the audit traces what a seed stakes
out.** Completeness audits discover defects by inventorying commitments (closed
vocabularies, guarantees, lifecycles, precedence rules, checkable code claims)
and tracing each end-to-end; a commitment the seed implies but never states is
reconstructed one finding arc at a time. Concretely: a guarantee ("never X")
names its mechanism, owning destination, and ordering fence; a named enum or
state set carries a per-value contract (definition, producer, precedence,
consumers, operator exit path) or assigns it to `create` in one line; every
checkable claim about existing code is grep-verified with a named anchor before
`create` runs; and an In-scope item whose core design question sits in the same
seed's Deferred list is a second effort — fence it out. Full directives and the
measured evidence: `SEED_FORMAT.md` in the plan-tool repo.

**Do not kill the iterate loop mid-flight.** The convergence pass is what fills
remaining TODO body sections. Killing the process before convergence leaves
TODOs that must be hand-filled.

**Backlog-derived seeds carry backlog reconciliation forward.** Name the source
entry in the seed and require the resulting plan to update the originating
backlog file when the work ships — usually in its final docs/status step and
acceptance criteria. Authoring the plan alone does not remove the entry. A
backlog-derived seed also **inherits the source entry's full scope contract**;
the seed elaborates that fence rather than inventing a different one. Where a
repo promotes backlog items to tracker tickets and leaves a one-line stub (the
entry's id, title, and ticket key) in the backlog, the seed also names the
ticket, copies the scope contract from it, and the plan's final step removes
the stub.

**Route out-of-scope findings to the backlog files**, not standalone findings
docs. A `steps: []` findings stub falls outside plan discovery, never converges,
and rots; a backlog entry is triaged and removed when fixed.

---

# Documentation is forward-looking

Write plans, detail files, seeds, backlog entries, and docs in the
present/future tense — what the thing *is* and *will do*. Past-tense content
earns its place only when a reader needs it to act correctly: don't-reopen
decisions, don't-repeat failures (with the reason), live legacy contracts, and
provenance for a claim. Everything else describing a former state is **deleted,
not archived in place**; warranted history is **dated and framed as past**
("cut 2026-07-29", "superseded by #171"), never left in present tense beside
current design.

After any cut / split / merge / scope-out / renumber / reversed decision, sweep
**both** the invalidated **identifiers** and the removed concept's
**vocabulary** — across the plan body, every detail file, the seeds, *and* the
backlog. The vocabulary half is the one that gets skipped, and it leaves prose
still arguing for the thing you removed.

---

# Escape hatch

Applies to every loop above: if it won't converge — the same finding or region
keeps resurfacing across rounds, or a fix needs structural rework you can't land
inline — **stop looping and surface the issue to the user**, or file it in the
repo's backlog / issue tracker, rather than iterating indefinitely.
