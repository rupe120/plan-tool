# Common workflows

*Back to [Your first plan](../../README.md#your-first-plan).*

The authoring pipeline runs in order, then branches at the terminal
output: *(`roadmap`)* → `create` → bare-plan audit → `detail` →
detail-grounded audit → `run` *or* `jira`.
Each section below covers one step and the options that go with it — no
separate scenarios to hunt through.

Assumptions: run from the repo root with the manifest
(`.plan-tool/plans.json`) in use. Substitute `--plans-dir <dir>` if
you've opted out of the manifest.

## Ask an assistant to prepare the work

> Inspect this repository and draft a grounded seed for [change], with a scope
> fence and references. Link it and summarize changes for my review before
> creating a plan. Use the plan-tool skill to create and bare-audit the reviewed
> seed, then link the plan and report for review before details. After approval,
> author details and run the grounded audit; link both and summarize changes,
> verification and unresolved decisions. Ask for corrections or continuation at
> each boundary and wait unless I explicitly delegate that transition. Stop
> before implementation or export.

Follow the [planning demo](../demos/planning-demo.md) and its
[authored samples](../demos/dark-mode-example.md), or the
[TTRPG roadmap demo](../demos/roadmap-demo.md) for a larger concept. These examples
teach artifact review; they do not establish successful live model runs.

After detail review, choose a separate request:

| Result | Request |
| --- | --- |
| Status | “Inspect the plan, reports and any active invocation; report state and next decisions without implementation.” |
| Resume | “Check the original invocation first; after confirmed exit, use its recorded outcome to resume the next incomplete stage within the agreed scope.” |
| Execution | “Execute the reviewed plan, reconcile code against it and review changes to convergence; report results.” |
| Local export | “Export local stories and their paired developer handoff; link both and summarize validation for review. Leave tracker publication for a separate request.” |

Quiet output and backend completion do not prove command exit. Follow
[monitoring and recovery](../../integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely)
before resuming; do not overlap invocations. The sections below retain direct
operator procedures.

## 0. `roadmap` — stage a project-sized concept *(optional)*

Reach for `roadmap` when the work is **project-sized** and you can't yet name
its domain or say what it trades away. If you can already write a `create`
seed, do that instead. `roadmap` costs four Claude calls, and what they buy
you is shared vocabulary and a citable decision record — not a better design
(measured in
[`docs/evidence/roadmap-layering-measurement.md`).

```bash
plan-tool roadmap my-project --from-existing docs/concepts/my-project.md
```

Feed it one markdown brief, written in your own words. Say the scale and load
shape, say what already went wrong, and leave open calls open — that's the
point of writing it this way. Four staged Claude calls then produce four
artifacts, published as one immutable version under
`<plans-dir>/roadmaps/my-project/`, plus one draft seed per proposed plan under
`seeds/`:

| Artifact | What it fixes |
| --- | --- |
| `01-domain.md` | Entities, business rules, workflows — the vocabulary everything downstream cites. |
| `02-constraints.md` | One disposition per quality attribute (`prioritized` / `traded-away` / `not-load-bearing`), plus the constraints behind them. |
| `03-components.md` | Logical components: the entity ids each owns, the patterns it applies, the constraints it discharges. |
| `04-roadmap.md` | The ordered plan list: each row's intent, component-owned or cross-cutting delivery shape, non-goals, and `draft_seed_path`. |

Each stage's gate-clean result is held in a resume directory, and every
held stage is re-gated by the same deterministic gates that judged the model's
output. A failing gate feeds its violations back into a bounded retry of the
same stage. The verb is non-interactive by construction and exits non-zero
only when a stage runs out of attempts.

Roadmap artifacts are **not plans** — nothing lands in the manifest, and
`list` / `status` / `run` won't resolve one.

**A changed brief.** A rerun over held stages with a different brief refuses
before any backend call and names the resume directory; restore the brief,
delete that directory by hand, or start a successor slug. A roadmap with an
accepted head refuses a stage run. Send semantic changes to ledger feedback or
a successor roadmap lineage. See `docs/how-to/roadmap.md`.

**Stage-run status.** An ordinary `roadmap` stage run writes bounded, confirmed lifecycle lines to
**stderr**. You'll see one after each of these:

- accepted selection
- a stage start
- a retry or stop
- a write, or a re-gate of a held stage
- the returned result

Each line records only the last confirmed transition, so a quiet call is not
a red flag — it gives no heartbeat or backend-liveness guarantee either way.
Roadmap summaries and result payloads on stdout stay unchanged, so consumers
must not parse these lifecycle lines. Views, seed operations (`--apply`,
`--refresh-seeds`, and `--materialize`), the separate `--revise-feedback`
command, and other non-stage routes don't emit this
status surface at all.

**Review what it guessed.**

#### Two review channels

- **`pending` decisions** — a load-bearing guess the stage recorded rather than
  interviewing you about. Settle one with `plan-tool roadmap <slug>
  --settle-decision <artifact>:<decision-id> --settlement-evidence
  <artifact>:<feedback-id> --confirm-decision-settlement`, citing a named,
  live feedback row that approves it. It publishes a committed receipt instead
  of hand-editing `status`. See `docs/how-to/roadmap.md` § 5 for the
  enrolled-lineage limits and for recovering a row already hand-edited under
  the old advice.
- **Ledger feedback** — for when you'd rather *say* what's wrong than fix it by
  hand. Submit an item with `plan-tool roadmap <slug> --submit-feedback ITEM_ID
  --feedback-target <artifact>:<kind>[:ROW_ID] --feedback-request TEXT`, then
  `--propose-candidate` snapshots the eligible `open` items into an inert
  candidate. The reviewer owns close, defer, and reopen
  (`--close-feedback`, `--defer-feedback`, `--reopen-ledger-feedback`); none
  invokes a backend. See `docs/how-to/roadmap.md` § 6.

#### Feedback and seed state

An accepted local feedback request invalidates tracked seed state before its
one backend request and leaves existing seed bytes alone. It does not retry
or refresh seed content, including after a failed request — that's
deliberate: it stops a roadmap revision from silently replacing a seed
already under review or already handed to `create`. Review the artifact
response, then run `plan-tool roadmap <slug> --refresh-seeds` when you're
ready to regenerate against the current codebase; it restores a
consumed/archived seed at its original path and writes a diff report. Until
then, `create --from-existing` asks for an explicit confirmation before
continuing with an invalidated roadmap seed.

**Then it's the ordinary pipeline.** A full run prints one ordered
`create --from-existing` line per plan row:

```bash
plan-tool roadmap my-project --apply     # optional: promote accepted drafts into plan-seeds/
plan-tool create first-plan --from-existing plan-seeds/first-plan.md
```

`--apply` runs no stages and invokes no backend — it previews, confirms (or
`-y`), and copies. You can skip it and point `create` straight at a
`seeds/<plan>.md` path instead. Order the seeds by dependency yourself;
inter-plan assumptions live in `04-roadmap.md` and in each seed's scope
fence.

**Read it back with `--view summary`.** The compact summary shows artifact
health, design and review counts, plan review-context coverage, seed
lifecycle, indexed-reference problems, and the highest-priority drill-down
commands.

For more depth, reach for one of these:

- `plan-tool roadmap <slug> --view {walk,ledger,index,seeds}` — the full
  traceability walk, decision ledger, reverse citation index, or per-plan
  draft seed state report. Every cross-row id resolves to the row it names,
  without opening all four files separately.
- `--view html` — renders every row of all four artifacts as one
  self-contained, print-formatted page, for reading the design rather than
  auditing its state. Its domain section opens with an ER-style diagram of
  the entities and their reference fields, and draws no cardinality because
  the artifact records none. Written to `<roadmap-dir>/review.html` by
  default (`--output <path>` chooses the destination; `--output -` prints
  instead, the default every other view uses).

`--mode current` (the default) renders the design state; `--mode review`
adds `feedback` rows and their removals. See `ROADMAP_FORMAT.md` § "See also"
or the generated [`roadmap` command reference for the full
flag list.

Full narrative — a real run, what to read each artifact for, and the direct
fallback when stage 4 is skipped:
[`docs/how-to/roadmap.md`. Schema and gate
table: [`ROADMAP_FORMAT.md`.

## 1. `create` — author a new plan

Registers a new plan in the manifest. The four variants below are mutually
exclusive — pick the one that matches what you're starting from.

```bash
plan-tool create my-slug                                       # interactive wizard (no source)
plan-tool create my-slug --from "1-2 sentence description"     # short prose seed
plan-tool create my-slug --from-existing path/to/source.md     # draft with ## References
plan-tool create my-slug --reprocess                           # fill _(TODO)_ from archive (no Claude)
```

`create --from-existing` selects `seed_body` when it's present, even when
it's empty; otherwise it falls back to `from_description`. Unmatched fences
and a missing, duplicate, empty, or placeholder `## References` section
refuse before a run record or model call — before anything happens, in
other words.

A direct-ready source gets a raw-source split assessment and publishes as
`direct` only after a single-plan result. Every other file-backed source
takes one preparation decision, landing on exactly one of:

- `normalized` — publishes
- a no-plan `split` worksheet (exit 0)
- `refused` (exit 2)

Direct and normalized publication are route-owned: the CLI archives only
after clean finalization, while public library calls leave their supplied
source untouched.

Inline `--from` keeps its own, separate compatibility behavior, and
`--no-distill` belongs to that inline path — it's not a file-backed bypass.
Use
[`docs/how-to/pipeline/create-from-existing.md` for
the concise flow and
[`docs/reference/contracts/seed-ingestion.md`
for selected outcomes, authority, checkpoint, and archival behavior.

Options applied *during* create:

- `--no-synthesize-body` — skip the `create-body-sections` round-trip;
  body sections fall back to H2-extraction → `_(TODO)_`. Useful for
  cost-sensitive runs, regression tests pinning pre-synthesis output
  bytes, and operators who know the seed is already canonical and
  want to bypass the canonical-skip detection's read pass.
- `--no-fetch-docs` — skip the `create-reference-docs` fetch that
  grounds body synthesis in reference-URL content. By default `create`
  fetches each reference (gathered by `create-references`), strips it to
  readable text, and folds that text into the synthesis prompt. The
  fetch only runs when synthesis runs, never blocks a create (a dead
  link or timeout just drops that doc), and is checkpointed by URL set.
  Pass this for offline / air-gapped / cost-sensitive runs; the
  References section still renders the links either way.
- `--iterate` / `--no-iterate` (**on by default for `create`**):
  loop completeness primitives → `apply-finding` → re-audit until
  convergence or budget. Pairs with `--max-iterations N` (default 3)
  and `--iteration-budget SECONDS` (default 1800; a debounced
  no-progress deadline, not a cap on total loop time — see
  [Defaults). Pass `--no-iterate`
  to skip the post-write loop. Detail authoring defaults to one shot;
  enable its quality loop only when explicitly requested. Neither
  `detail --reconcile` nor `run --reconcile` accepts `--iterate`.
- `-y` + closed stdin (`< /dev/null`): headless mode. Default-
  accepts every wizard prompt with a declared default and fails fast
  if Claude can't extract steps (no interactive fallback).
- `--reprocess` (deterministic, no Claude): lifts H2 section bodies
  from `<plan-dir>/archive/<slug>.replaced.md` to fill `_(TODO)_`
  placeholders. Leaves `## Steps` and already-populated sections
  alone.
- **Per-step `change_type` classification.** After step proposal, the
  wizard prints each step's machine-guessed `change_type` and rationale
  and prompts `(r)efactor / (f)eature / (n)on-code / (s)plit / Enter`
  (Enter accepts the guess). `(s)plit` decomposes a step that mixes
  behavior-preserving restructuring with new behavior into type-pure
  halves wired by a `depends_on` edge, and is offered **only when an
  invoker is present**. `-y` accepts every machine guess verbatim and
  leaves any unproposed step unset. The plan body's `## Testing` section
  then carries a per-step strategy block derived from the
  classifications, and classified steps render an inline
  `[refactor]`/`[feature]`/`[non-code]` tag in `status`, `run`, and
  detail/jira step views. See
  [`PLAN_FORMAT.md` for the field.

`create` does not propose `gate:` commands — for gates grounded in a
plan's already-built steps (or, with `--all-steps`, speculatively from
a not-yet-built step's detail), use `suggest-gates` (below).

`--output-dir` is not required — the wizard picks the conventional
plan directory and `--yes` accepts that default. Pass it only when
you want a non-default location.

## 2. `detail` — draft per-step detail files

Run the bare-plan `completeness-audit --iterate` after `create`, judge its
plan-level findings, and commit bounded corrections before authoring details.
Then `detail` drafts developer-actionable Why / Files / Implementation / Tests /
Acceptance criteria for each step and wires `step.detail` automatically. Audit
the completed bundle again before execution or export. A bare-plan audit records
missing detail coverage without treating the missing files as a design defect;
see [the two audit gates](pipeline/audit.md).

```bash
plan-tool detail my-slug                     # every step missing a detail file
plan-tool detail my-slug --step 3            # one step
plan-tool detail my-slug --force             # rewrite even if file exists
plan-tool detail my-slug --no-resume         # ignore checkpoint cache
```

Options applied *during* detail:

- `--iterate`: opt in only when explicitly requested; the normal authoring route
  uses one-shot detail followed by the grounded audit. After each write, the
  optional detail-quality loop drives 2–3 revisions tightening citations
  and pinning vague prose. Budget is **per step**; one step
  exhausting doesn't block the next.
- `-y < /dev/null`: headless. Skips the re-run Y/N gates.
- `--lessons`: opt into lessons capture — a second Claude call per
  step distilling the written body into the shared lessons store.
  **Off by default** (it costs an extra call per step); pass
  `--lessons` when you want the store to keep learning.

## 3. Audit a plan's quality

`completeness-audit` is the primary authoring audit: run it before detail,
then again on the completed bundle, following the [audit procedure](pipeline/audit.md):

```bash
plan-tool completeness-audit my-plan --iterate --commit  # both authoring gates
```

A free deterministic layer catches the cheap problems first (missing body
sections and lessons gaps). Missing details are coverage at the bare gate,
not a defect by themselves. A sampled Claude audit judges the plan against
code at HEAD, with detail grounding only for the available bundle.
The same audit can surface `data-contract` findings: plan/detail `## Input`
reference drift is repaired in the authored files, while saved
`DATA_CONTRACT.md` documentation drift is walked with
`plan-tool data-contract-apply <name>` and then verified by re-running the
audit.

`reconcile-plan` is the **stale-plan** audit — reach for it when a plan
has not been executed and the code has moved on under it, so the plan
body and frontmatter may no longer describe reality. It compares every
step against the current code and its apply walk edits the plan/detail
files to match. It's also a useful **supplement** to `completeness-audit`
when you want an explicit code-fit pass on an otherwise-current plan:

```bash
plan-tool reconcile-plan my-plan             # plan-vs-code fit (one Claude call)
```

`plan-tool validate` checks frontmatter schema only. Every other
subcommand re-validates on load, so it's a niche debugging tool for
directly edited frontmatter, not a peer audit verb.

## 4. `run` — execute the plan

```bash
plan-tool status my-plan                     # what's the current step?
plan-tool run                                # no name: pick from plans with open steps
plan-tool run my-plan --commit               # execute the current step
plan-tool run my-plan --step 3 --commit      # run a specific step
plan-tool reconcile-code my-plan --step 3    # post-execution; verify and commit edits separately
```

**Interactive plan picker.** `plan-tool run` with no plan name — or a
name that doesn't resolve — prints a numbered list of the plans that
still have open steps and asks you to pick one. Then it asks whether to
run **all** runnable steps (`--all`) or just the **next** step.

Two defaults make repeat runs fast: the list defaults its selection to the
last plan you ran, and the all/next question defaults to the last choice you
made for that plan (both remembered in `.plan-tool/run-prefs.json`).

The picker is TTY-only. With stdin redirected or piped (CI, `-y` scripts), a
missing name is a hard error and an unresolved name re-raises — automation
fails fast instead of blocking on a prompt.

After the last green step, run `plan-tool reconcile-code my-plan --all`, retain
reports and drive code review under the [post-run contract](../../integrations/shared/DIRECTIVES.md#after-run-finishes-a-plan).
Dry runs render prompts only; completeness audits do not belong in this tail.

**Pre-execution entry point for plan-vs-codebase reconciliation:**
`plan-tool reconcile-plan <name>` (section 3) — most useful on an
**older plan the code has drifted under**, or as a supplement to
`completeness-audit`. One claude call audits every step's plan body and
frontmatter against the current code. Reach for
`plan-tool detail <name> --reconcile --step N` as a drill-down only when
`reconcile-plan` flags concrete drift in a specific step's detail body.

See [the two reconcile verbs](../../integrations/shared/DIRECTIVES.md#the-two-reconcile-verbs-are-not-interchangeable)
for the split between code-is-truth and plan-is-truth audits.

## 4a. `suggest-gates` — lock in built work against later steps

```bash
plan-tool suggest-gates my-plan             # confirm each suggestion, write the kept ones
plan-tool suggest-gates my-plan -y          # report suggestions without writing
plan-tool suggest-gates my-plan --all-steps # no built steps yet: propose speculative gates from the step details
```

Once some steps are `done`, this reads those built steps (their
detail, file footprint, and the real diff) and asks the backend for
`gate:` commands that protect their invariants — things like a `--help`
golden diff, a `grep` that a removed identifier stays gone, or a `pytest`
of the suite a step established. It then attaches the ones you keep to the
**remaining** steps' frontmatter, so a later step's `run` is blocked if it
regresses earlier work.

Gates are grounded in artifacts that exist now, and they stay
operator-controlled: each suggestion is shown for
`(k)eep / (e)dit / (m)ove / (d)rop`, and `-y` / non-TTY **reports
without writing** rather than applying an unvetted shell command — no
surprise commands land on your machine without a look first. With
**`--all-steps`** the done-steps precondition relaxes: on a plan with
nothing built yet, it proposes *speculative* gates from each not-done
step's detail instead, with every not-done step a valid target. `create`
does not propose gates — this is the only surface that does. See
[`PLAN_FORMAT.md` (the `gate:` field)
for how gates run.

## 5. `verify-all` — CI gate after the `jira` branch (conditional)

Primary use case: the team ships Jira stories, flips each step's
`status:` to `done` in the plan frontmatter as stories merge, and CI
runs `verify-all` to catch drift between the plan and the merged code.
Non-zero exit on any FAIL gives CI a clean gate.

```bash
plan-tool verify-all --rollup my-plan                     # done-step rollup against code
plan-tool verify-all --rollup my-plan --deep              # per-acceptance-bullet drill-down
```

Emits `[OK]` / `[WARN]` / `[FAIL]` per done step. Read-only — `verify-all`
never edits code or flips step status; failure recovery uses a direct edit.
Reach for `--deep` only when the rollup is ambiguous — it spends one
extra Claude call per acceptance bullet.

After local `run`, `verify-all` works but largely duplicates `run`'s
post-flight checks (a missing `## Summary` warning; `run` itself already
blocks a step that changed none of its declared files). Skip unless you want the structured verdict format or are
chasing per-acceptance-bullet drift with `--deep`.

## 6. `register` — adopt an external plan into the manifest

Use when another tool (or a previous session) wrote a structured
plan file that isn't yet listed in `.plan-tool/plans.json`. Required
before `completeness-audit`, `run`, `reconcile-plan`, etc. will find it.

```bash
plan-tool register path/to/some-plan.md      # by path
plan-tool register some-slug                 # by slug (scans known plan dirs)
```

## 7. `deregister` — remove a plan from the manifest

The inverse of `register`: drops the plan's entry from
`.plan-tool/plans.json` so the rest of the tool stops seeing it. The
plan **file on disk is left untouched** — to archive a *completed*
plan and move its file, use `sweep`. Accepts a path or slug; unlike
`register`, the file need not exist or parse, so stale entries (the
"not found on disk" rows `list` warns about) and malformed plans can
be pruned this way.

```bash
plan-tool deregister path/to/some-plan.md    # by path
plan-tool deregister some-slug               # by slug (registered + stale entries)
```

## 8. `sweep` — manifest housekeeping

Collapses the steady-state housekeeping a long-lived plan list
accumulates, in one pass:

- **Archives completed plans** — top-level `status: completed` AND
  every step `done` (strict AND; either alone stays put). The file and
  its `plan-details/<slug>/` move to `archive/` beside the plan, and
  the manifest entry is removed.
- **Reports partial plans** — status, done counts, last-edited date,
  and any in-progress step titles, without opening each file.
- **Offers to prune missing entries** — manifest rows whose files no
  longer exist on disk.
- **Reports unregistered plan files** — valid plan files found beside
  registered plans that the manifest doesn't list. Register an intended
  file explicitly with `plan-tool register <path>`; sweep never adopts
  it as a side effect. Files with frontmatter that fails validation are
  listed but cannot be registered; fence-less `.md` files (notes) are
  ignored.

```bash
plan-tool sweep                 # interactive: archive + missing-entry prompts
plan-tool sweep -y              # headless: archive + prune
plan-tool sweep --dry-run       # preview every mutation, touch nothing
plan-tool sweep --report-only   # just the status report, no offers
plan-tool sweep -y --commit     # archive + prune, then commit the result
```

`--commit` requires a clean working tree up front and is incompatible
with `--dry-run` / `--report-only`; it makes one commit (`sweep: archive
N completed plans`) capturing the archived plans + manifest edits, and
no-ops when the sweep moved nothing.

Manifest-mode only (`--plans-dir` / `PLAN_TOOL_PLANS_DIR` have no
manifest to maintain).

## 9. `withdraw` — archive a plan being abandoned

The abandon-path counterpart to `sweep`'s completion path: a plan whose
premise turned out false, that was carved wrong, or that's otherwise
being dropped mid-flight — not finished, and not superseded by a
replacement (`create --from-existing` handles that case). One command
replaces four separate plan-management actions:

- Moves the plan file to `archive/<stem>.withdrawn.md` — the
  `.withdrawn` marker (distinct from a completed sweep's bare filename)
  so a reader can tell abandonment from completion at a glance.
- Moves its `plan-details/<slug>/` alongside it.
- Prepends a dated `> **Withdrawn YYYY-MM-DD** — <reason>` header above
  the frontmatter.
- Deregisters it from the manifest.

`--reason` is required — an archived plan with no stated reason reads
as completed to the next reader.

```bash
plan-tool withdraw some-slug --reason "premise disproved on replay"
plan-tool withdraw path/to/some-plan.md --reason "carved wrong"
```

Target resolution matches `deregister`: path or slug, and the plan
need not currently be registered (already deregistered, or
never registered, both still withdraw). Manifest-mode only, same
refusal as `register` / `deregister` / `sweep`.
