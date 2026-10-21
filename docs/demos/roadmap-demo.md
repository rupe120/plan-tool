# TTRPG World Builder — demo orchestration runbook

**What this is.** The procedure for producing a demo that documents what it
looks like to take a project-sized concept brief all the way through
`plan-tool roadmap` → seed promotion → `create` → `completeness-audit` →
`detail`. It is the runbook, not the demo: executing it produces the four
deliverables in § 8.

**Input brief.** [`docs/concepts/ttrpg-world-builder.md`](../concepts/ttrpg-world-builder.md) — a TTRPG world-builder web app
(markdown notes, per-note and per-section visibility, a link graph, player
marginalia, maps, calendars, timelines, and two far-future AI features).

**Why this brief works as a demo.** It has the three properties
[`docs/how-to/roadmap.md`](../how-to/roadmap.md) § 1 says a brief needs, plus one bonus:

- **Explicit feature tiers** — `CORE FEATURE` / `FEATURE` / `FAR FEATURE` is a
  priority signal stage 2 can rank against instead of inventing one.
- **A real architectural fork** — visibility (draft/published, secrets, per-user
  and per-group marginalia sharing) cuts across *every* feature. Whether that
  becomes a permission check or a structural separation is exactly the kind of
  load-bearing call the decision rows exist to pin.
- **A stated non-goal boundary** — the two AI features are marked far-future, so
  the demo can show a `pending` decision or an explicit deferral rather than
  scope creep.
- **It is not a CRUD app.** The graph and timeline views make component seams
  genuinely arguable, which is what makes stage 3 worth watching.

---

## 1. Demo setup and outputs

Use a fresh scratch repository and carry one representative plan to full depth.
Produce a narrative walkthrough, terminal transcripts, a reveal.js deck and an
Artifact page. Author a thin scaffold after stage 3 from the component IDs it
produces. Publishing an Artifact remains a separately authorized action.

Roadmap artifacts and plans belong in the consuming repository. A separate demo
repository keeps them out of plan-tool's own manifest and implementation plans.
Keep recording progress, preparation status and changes to the presentation brief
in a session handoff; this runbook owns the repeatable procedure.

---

## 2. Why the demo repo carries a scaffold

`roadmap` grounds only in the brief, so all four stages run fine against an
empty repo. **`create` and `detail` do not** — they ground against live code and
docs. In an empty repo the plan and its detail bundle reference files that do
not exist and the prose reads visibly thin, which is a demo-quality problem
precisely where the demo makes its point.

So the repo gets a **thin** scaffold, and thin is a real boundary rather than a
hedge: **scaffold what the roadmap decided, stub nothing it left to the plans.**
The roadmap settled the component seams and the entity ids, so those become
modules and dataclasses. It deliberately did *not* decide behavior, so no
function stubs are invented — inventing a signature here would pre-empt the
plan's design and give `detail` a wrong thing to bind to.

**The stack is a scaffold decision, not a roadmap decision.** `ROADMAP_FORMAT.md`
keeps artifacts logical — `FieldType` is six logical members with no physical
types — so nothing under `roadmaps/` names a language. Python + `pytest` is
chosen here because the scaffold's one job is a **green** test command, and a
Node scaffold needs a network install that can leave that command broken. Swap
it freely; nothing upstream depends on it.

---

## 3. Phase 0 — scratch repo setup

Start inside the plan-tool source checkout so the concept brief resolves from
its Git root. The demo uses a new temporary directory, independent of your
checkout layout.

```bash
plan_tool_source_root="$(git rev-parse --show-toplevel)"
DEMO="$(mktemp -d "${TMPDIR:-/tmp}/plan-tool-demo.XXXXXX")"
mkdir -p "$DEMO" && cd "$DEMO"
git init
mkdir -p docs/concepts plan-seeds .tmp

# Bytecode and scratch, ignored from the first commit. Untracked .pyc files
# land inside the test-authoring gate's post-call git delta later, so this is
# load-bearing rather than tidiness.
printf '.tmp/\n__pycache__/\n*.pyc\n.pytest_cache/\n' > .gitignore

cp "$plan_tool_source_root/docs/concepts/ttrpg-world-builder.md" \
   docs/concepts/ttrpg-world-builder.md

git add -A && git commit -m "demo: concept brief for the TTRPG world builder"
```

**Why a `git init` is enough.** `locator.py` resolves the project root at the
nearest ancestor holding a `.git` entry **or** a `.plan-tool/plans.json`
manifest; the manifest is created on first write. No `register` step is needed
and no `--repo-root` flag is needed as long as every command runs from inside
`$DEMO`.

**The brief travels with the demo.** It lands at the same
`docs/concepts/ttrpg-world-builder.md` path in the demo repo that it holds here,
so the command on the slide is the command that ran.

**Do not** create `.plan-tool/` directly.

### Phase 0b — the scaffold, authored after stage 3

**Run this after Phase 1, never before.** The skeleton mirrors the component ids
stage 3 actually produced; guessing them in advance is how the scaffold and the
artifacts end up disagreeing. Per § 2 it carries seams and entity ids only.

What it ships:

- **One module per component**, named for the component but not identically —
  a component id is prose-shaped and a module name is not (`component-time` →
  `chronology.py`, dodging the stdlib `time`).
- **Each module declares `COMPONENT_ID` and `ENTITY_IDS`**, copied from
  `03-components.md`, plus a frozen dataclass per owned entity carrying only
  `id`. Fields land with the plan that builds the entity.
- **`README.md`** naming the stack, the test command, and the module ↔ component
  table.
- **A traceability test that reads the artifact.** `tests/` parses
  `03-components.md` and asserts the component set matches the module map and
  that every module's `ENTITY_IDS` equals the artifact's. This is what keeps
  scaffold and roadmap from drifting silently, and it makes the test command
  *mean* something instead of asserting `True`.

**Mutation-check the traceability test before trusting it** — the repo rule is
*verify by mutation, never by reading*, and a regex that silently matches
nothing would otherwise pass forever. Break it both ways: perturb one module's
`ENTITY_IDS`, and drop one component from the module map. Both must go red for
the right reason, and the suite must return green when restored.

Commit before Phase 4 so `create` sees a clean tree.

---

## 4. Phase 1 — the four roadmap stages

```bash
cd "$DEMO"
set -o pipefail && plan-tool roadmap ttrpg-world-builder \
  --from-existing docs/concepts/ttrpg-world-builder.md \
  2>&1 | tee .tmp/ttrpg-demo.roadmap-stage-run.log
```

Four Claude calls, one per stage, each gated before it is held. A run that
fails part-way leaves only the resume directory
`.plan-tool/runs/ttrpg-world-builder/roadmap-stage-resume/`, and re-running the
same command with the same brief resumes from the first stage that is missing or
fails its re-gate. Once all four stages pass, the run publishes one immutable
version, its ledger, and the accepted head, then deletes the resume directory.
The run leaves no top-level artifact files; the version store
`.roadmap-versions/` and the generated `INDEX.md` listing are what appear in
`docs/implementation-plans/roadmaps/ttrpg-world-builder/`. Read the artifacts
with `plan-tool roadmap ttrpg-world-builder --view summary` (or `walk`, `ledger`,
`index`, `seeds`, `html`).

| Artifact | Holds | Gates |
|---|---|---|
| `01-domain` | entities, business rules, workflows, decisions | 9 |
| `02-constraints` | one disposition per quality attribute + anchored constraints | 9 |
| `03-components` | components owning entity ids, applying patterns, discharging constraints | 12 |
| `04-roadmap` | ordered plan rows with intent, non-goals, and dispositions | 13 |

Twenty-two distinct `check_*` functions across the four tuples; seven are shared
by every stage. The run touches no plan manifest — roadmap artifacts are not
plans, and `list` / `status` / `run` will not resolve one.

**Capture for the demo:** the combined stdout-and-stderr terminal record. The
existing `2>&1 | tee` leaves stdout as the command's existing output and
includes lifecycle lines written to stderr, along with stage banners, gate
results, and retry lines if any. Capture it, then `git add -A && git commit`
the roadmap folder so the published version is a reviewable commit.

For normal roadmap stage runs, lifecycle lines confirm only the last transition
the command reached. A quiet period after one neither adds periodic reporting
nor proves that the backend remains live. The lines contain no backend-derived
content; use the per-run JSONL record for detailed attempt diagnosis.

### What to read for, per stage

Read for **seams**, not completeness — a missing entity is cheap, a wrong seam
is expensive three plans later.

- **Stage 1.** Is `secret` its own entity or a field on `note`? Is `marginalia`
  an entity anchored to a text range, or a note subtype? These are the
  `conflict`-entity call from the `cfp-review` run, and they are the demo's best
  material either way they land.
- **Stage 2.** The disposition table is the most useful thing the verb produces.
  For this brief `security` should come back `prioritized` — the secrets and
  marginalia rules are the whole product. Watch whether `performance` and
  `scalability` get ranked honestly against a small-group app, or reflexively.
  **An all-`prioritized` table means the brief never said what the project will
  spend, and no gate catches it.**
- **Stage 3.** Does visibility land as one cross-cutting component, or is it
  smeared across notes / graph / marginalia? Both are defensible; the demo wants
  whichever it chose stated as a decision row with the rejected alternative.
- **Stage 4.** Are the two `FAR FEATURE` AI items deferred explicitly, or did
  they become plan rows? Either is showable; silently dropping them is the one
  outcome worth a feedback row.

**Do not get attached to non-entity ids.** Measured re-run stability: entity ids
survive at 85%, business-rule and decision ids at 30% / 25%, field names not at
all. Anchor anything downstream to entity ids.

---

## 5. Phase 2 — the review loop (the part worth demoing)

This is the phase that shows the verb **collaborates**. Everything before it is
generation; this is the propose → review → re-propose loop. Budget real time
here — it carries the demo.

Two channels, and they are different moves:

### `pending` decisions — settle with the confirmed command

A stage that guessed at something load-bearing records `status: pending`. The
run still exits 0; pending is a queue, not a failure. Settle one with
`plan-tool roadmap <slug> --settle-decision <artifact>:<decision-id>
--settlement-evidence <artifact>:<feedback-id> --confirm-decision-settlement`,
citing a named, live feedback row that approves it. The accepted version is
immutable, so `status` is never hand-edited.

A stage run is refused once the accepted head exists, so the review loop runs
entirely through the ledger and candidate routes.

### Ledger feedback — say what is wrong and let the model propose

Submit a request to the ledger, then build an inert candidate from it:

```bash
plan-tool roadmap ttrpg-world-builder --submit-feedback note-type-weight \
  --feedback-target domain:artifact \
  --feedback-request "The note-type modelling feels too heavy."

set -o pipefail && plan-tool roadmap ttrpg-world-builder --propose-candidate \
  2>&1 | tee .tmp/ttrpg-demo.roadmap-candidate-1.log

plan-tool roadmap ttrpg-world-builder --compare
```

`--propose-candidate` takes no selector and prints the candidate's narrative
evidence; `--compare` shows the accepted head against the active candidate and
writes nothing. Decide the candidate with
`--decide-candidate CANDIDATE_VERSION_ID --candidate-decision approve|edit|reject`;
approve is two invocations, and the second carries the printed
`--confirm-stack-digest`. Reject or discard releases the candidate and leaves
the accepted version unchanged.

Change a retained ledger item with `--edit-feedback`, `--retarget-feedback`,
`--defer-feedback`, or `--close-feedback`, and reopen one with
`--reopen-ledger-feedback ITEM_ID`. When a candidate's review asks a question,
read it with `--review-candidate INITIAL_CANDIDATE_VERSION_ID` and answer with
`--answer-question QUESTION_ID --answer TEXT`.

**Capture for the demo:** the `--compare` output for every candidate, and each
candidate's narrative evidence verbatim.

### Two feedback items to write, chosen to show both outcomes

The demo needs one request the model **accepts** and one it **refuses**. The
accept is the easy half; the refusal is the one the demo cannot ship without.

**The accept-shaped request** — artifact-level and deliberately vague, e.g.
*"the note-type modelling feels too heavy; People/Place/Thing/Event look like one
entity with a discriminator."* Expect a concrete counter-proposal for the
candidate to carry.

**The refused request** gets its own section below, because it is the frame the
demo is actually for.

---

## 5a. The refused feedback row — the highest-value thing to film

**Do not skip this, do not save it for last, and do not wait for a request that
happens to be worth refusing. Manufacture one.** A deliberately silly request is
completely fine — better, even. The demo is not showing that the model has good
taste; it is showing that **the tool will not let the model overwrite a decision
the prior artifact marks `settled`**. A frivolous request makes that point *more*
legible, not less, because nobody can mistake the refusal for the model merely
disagreeing on the merits.

**Why this is the single most valuable frame in the demo.** Every other phase
shows generation, and generation is table stakes — any model writes a domain
model. This is the only place where the prior artifact's decision visibly wins
over the model's current opinion. It is the whole difference between a tool
that preserves a roadmap and one that regenerates over it, and it is the claim
the walkthrough makes in its closing line. Without this frame the demo asserts
that claim; with it, the demo shows it.

### Why the refusal is reliable, not hopeful

It is enforced by a deterministic gate. `check_settled_decisions` pins a settled
decision's `id`, `status`, `chosen_option`, and `anchor` against the
predecessor. Dropping it raises `dropped-settled-decision`; changing any of
those four raises `altered-settled-decision`. The docstring is explicit that **a
cited removal does not excuse dropping it**. And because the `anchor` is pinned
*and* `check_decision_records` requires every anchor to resolve
(`unresolved-decision-anchor`), the design row the decision points at cannot be
removed either.

**So the demo has no bad outcome.** If the candidate leaves the decision
untouched, film that. If a candidate would drop or alter it, the gate rejects
the candidate with the violation quoted — which films the *deterministic* half
of the fence instead. Either way the point lands; only the slide changes.

### The precondition that will bite

`check_settled_decisions` is **predecessor-only** — "without one there is no
settled commitment to break." Two consequences:

- It only fires against an **existing accepted version**. A first-ever run has no
  predecessor and nothing to refuse.
- **There must actually be a `settled` decision to violate.** A stage or an
  operator may have set the status, so **check first, and settle one with
  `plan-tool roadmap <slug> --settle-decision <artifact>:<decision-id>
  --settlement-evidence <artifact>:<feedback-id>
  --confirm-decision-settlement` if needed**, citing a live feedback row that
  approves it. That command records the operator's decision and publishes a
  receipt. Do that when the filmed claim specifically needs to show a human
  decision, rather than the general persistence fence.

```bash
cd "$DEMO"
plan-tool roadmap ttrpg-world-builder --view ledger
```

The decision ledger view lists every decision with its status; pick a `settled`
one.

### The recipe

1. **Pick a settled decision** (or settle one). For this brief the natural
   candidate is whatever stage 1 decided about `secret` — its own entity versus a
   field on `note`. Note its `id` and its `anchor`.
2. **Submit a ledger item that the decision blocks.** Either shape works, and
   silly is explicitly allowed:
   - *Flip it* — `--feedback-target domain:artifact`, request: *"change
     `decision-secret-is-an-entity` to the rejected alternative, I've changed my
     mind."*
   - *Drop what it anchors* — `--feedback-target domain:row:secret`, request:
     *"delete the secret entity entirely, players can just not read the note."*
   - *Or something plainly frivolous* — *"rename every entity to a Star Wars
     character."* It will still be refused where it collides with the settled row.
     Silliness costs nothing here.
3. **Run `--propose-candidate`** and read the narrative evidence it prints.
4. **Expect** the candidate to leave the decision row and its anchored design row
   untouched, or the gate to reject the candidate with the violation text.

**Capture:** the narrative evidence verbatim, the unchanged decision row beside
it, and, if the gate path fires, the `dropped-settled-decision` /
`altered-settled-decision` violation text — the messages name exactly which row
is pinned, and they read well on a slide.

**One caveat worth stating on the slide.** `check_settled_decisions` deliberately
does **not** compare `rationale` or `rejected_alternatives` — whether a reworded
rationale still means the same thing is not decidable by a gate, and an equality
check on prose would fail on formatting alone. What is pinned is the *commitment*
(id, status, chosen option, anchor), not the prose around it. Do not overclaim
the fence.

---

## 6. Phase 3 — promote the draft seeds

Stage 4 publishes the plan rows but no draft bodies, so a fresh roadmap has one
`missing` draft per row. Materialize each recoverable draft before promotion;
the batch command runs the per-plan materializer for every eligible row.

```bash
plan-tool roadmap ttrpg-world-builder --materialize    # backfill every eligible draft
plan-tool roadmap ttrpg-world-builder --apply          # preview, no writes
plan-tool roadmap ttrpg-world-builder --apply -y       # second opt-in, copies
```

`--apply` is apply-only: it reads the accepted version's `04-roadmap` artifact, never invokes a
backend, and previews by default. `-y` is the deliberate second opt-in that
bypasses the TTY confirm. Stage runs stay non-interactive and do not accept `-y`.

**Draft seeds for new roadmaps live under `<roadmap dir>/plan-seed-drafts/`.**
The path is enforced, not conventional: `_validate_draft_seed_path` accepts the
new prefix or the legacy `seeds/` prefix for an existing roadmap, and rejects
an absolute path or one containing `..`.

Running `create` directly against a slug-relative draft path also works and
skips promotion entirely:

```bash
plan-tool create <plan-id> --from-existing \
  docs/implementation-plans/roadmaps/ttrpg-world-builder/plan-seed-drafts/<plan-id>.md
```

**Capture:** the preview output and the printed ordered `create` lines — that
list *is* the roadmap-to-plans handoff, and it is one clean slide.

---

## 7. Phases 4–6 — one plan to full depth

### Choosing the plan

Target the **notes + secrets visibility** slice. It is the right pick because it
owns the brief's central architectural fork, it is exercised by both core
features, and every later feature (graph, marginalia, timeline) depends on its
answer — so the demo can show inter-plan assumptions pointing *at* it.

If stage 4 names it differently, apply the walkthrough's slice test rather than
forcing the name: one outcome statable in a sentence, a handful of rules
meaningless apart, a clear boundary against the rest. Rules that never share an
entity are probably two slices.

### Phase 4 — `create`

```bash
set -o pipefail && plan-tool create ttrpg-note-visibility \
  --from-existing plan-seeds/ttrpg-note-visibility.md \
  2>&1 | tee .tmp/ttrpg-demo.create.log
```

`--iterate` defaults **ON** here; do not pass `--no-iterate`.

**The one caveat to state in the walkthrough** (it is the honest half of the
measurement): the roadmap's rejected-alternative *reasoning* is frozen at
authoring time, while `create` grounds against live docs. Carry the settled
**decision** forward as a fence; let `create` re-ground the **reasons**.

### Phase 5 — audit the bare plan, before detail

```bash
set -o pipefail && plan-tool completeness-audit ttrpg-note-visibility --iterate \
  2>&1 | tee .tmp/ttrpg-demo.completeness-audit-bare.log
```

A plan is *bare* while any step has no detail file, and the audit supports that
state: it judges the plan body and code at HEAD at the plan/concept level and
labels the report with exact detail coverage. Read it by axis —
`plan-correctness` findings are actionable plan-body defects now;
`plan-completeness` and detail-level findings are recorded with their
`completeness-apply` actions **withheld**.

**This is a live demo of the session-vs-human split, so show it deliberately.**
`--iterate` converges only the deterministic well-formedness findings; the
conceptual gaps persist unapplied. Because a human is at a TTY for this demo,
`completeness-apply`'s interactive `--jobs 1` walk **is** the intended path and
is worth filming — it is the surface an auto-driving session must *not* use.
Note that distinction on the slide; it is the non-obvious bit.

Re-audit until clean or confirmed low-yield. Record the report path, the
`N of M` detail coverage, and which axes were withheld.

**Quota-stopped branch.** If the report records
`early_stop_reason: "plan-quota"`, record its unconfirmed coverage and actual
pass count, but do not treat it as a completed gate or apply/reuse its findings.
Resolve the provider condition, then rerun `completeness-audit` as a fresh
invocation before continuing to detail.

### Phase 6 — `detail`

```bash
set -o pipefail && plan-tool detail ttrpg-note-visibility --commit \
  2>&1 | tee .tmp/ttrpg-demo.detail.log
```

`detail`'s `--iterate` defaults **OFF** — it is a one-shot write. Do not opt it
back in. `--commit` is per-step, so an interrupted batch keeps its completed
steps durable.

Then audit again, now detail-grounded:

```bash
set -o pipefail && plan-tool completeness-audit ttrpg-note-visibility --iterate \
  2>&1 | tee .tmp/ttrpg-demo.completeness-audit-detailed.log
```

If this audit is quota-stopped, capture the unconfirmed report, resolve the
provider condition, and rerun the audit as a new invocation. Do not call the
gate complete or continue to execution from that incomplete result.

**Stop here.** The demo documents authoring, not execution — no `run`, no
`reconcile-code`, no `/code-review` tail. Those belong to a different demo, and
in a scaffold-only repo a `run` would produce nothing worth showing.

---

## 8. Phase 7 — build the four deliverables

All four were requested. Build them in this order; each feeds the next.

1. **Captured terminal transcripts** — already produced by the `tee` in every
   phase above. Keep them under `$DEMO/.tmp/ttrpg-demo.*.log`. These are the
   evidence base: every count and quote in the other three deliverables cites a
   log, so nothing is paraphrased from memory.
2. **Narrative markdown walkthrough** — the durable reference, built on
   `docs/how-to/roadmap.md`'s structure but told on the TTRPG run: real
   ids, real counts, the real disposition table, the accepted and refused
   feedback exchange verbatim, and the resulting plan + one detail file. Written
   forward-looking; history only where a reader needs it to act.
3. **reveal.js deck** — `docs/presentations/`, matching the two existing decks'
   shape. Roughly: the brief → four artifacts → the disposition table → **the
   refusal, then the unlock** → the seed list → the plan → one detail file.
   **Build the deck around the refusal pair (§ 5a) and the disposition table**;
   everything else is connective tissue. Give the refusal two slides, not one —
   the refused request beside the untouched decision row, then the same request
   honored after the unlock. That pair is the deck's argument.
4. **Published Artifact page** — the shareable version of (2), with diagrams for
   the stage arc and the entity → component → plan traceability chain. Starts
   private. **Load the `artifact-design` skill before writing it**, and
   `artifact-diagramming` for the diagrams.

**Sequencing note.** Do not start (2)–(4) until Phase 6 is complete. The demo's
value is that every number in it came from one real run; assembling narrative
against a partial run is how invented counts get in.

---

## 9. Capture discipline

- **Background anything that could exceed ~30s** and announce the task id and
  log path in the same turn. Every `roadmap`, `create`, `detail`, and audit call
  qualifies.
- **Prefix every pipe with `set -o pipefail`.** Without it a `| tee` reports the
  *tee's* exit status, so a failed run reads as success. Every command above
  already does this — keep it when improvising.
- **Name logs specifically** — `.tmp/ttrpg-demo.<phase>.log`, never `output.log`.
- **Never suppress progress** — no `/dev/null`, no discarded stderr.
- **Commit between phases** so each artifact set is a reviewable diff. The diffs
  are demo material in their own right.

---

## 10. Cost, time, and what can go wrong

**Claude calls:** 4 for the initial stage run, plus one bounded call for each
selected existing stage with active `open` feedback, one materialization call
per plan row after Phase 1 and before promotion, plus `create`'s iterate loop,
the two audits, and `detail` (one call per step). Feedback-free re-gates make no
backend call.

**Failure modes to expect and film rather than hide:**

| Symptom | Meaning | Move |
|---|---|---|
| `stage-exhausted` | one stage burned all 3 attempts | Each `retrying (attempt N) after <kind>` line and the final `stopped after <kind>` line already name every attempt's kind; inspect `.plan-tool/runs/<slug>/*.jsonl` for the specific violation or parse detail |
| Gate violations on retry | working as designed | This is the deterministic half of the design — worth showing, not editing out |
| All-`prioritized` stage 2 | the brief never said what the project spends | A brief problem. Fix the brief and re-run stage 2 |
| A feedback-free re-gate published nothing | no active `open` feedback selected a bounded stage route | Add feedback at the owning stage if a model change is needed |
| Ordinary shared-budget rate limiting | short retry window | Inherited backoff handles it; do not add concurrency |
| Confirmed Cursor monthly plan quota | terminal provider condition | Return after the failed attempt; resolve the provider condition and start a fresh command, not a retry or fallback |

**Measured 2026-08-06: stage 1 exhausted on the first run and passed on the
second, and the numbers are worth knowing before you budget.** The failing run
cost ~7.5 minutes and ~$1.45 and wrote nothing. Its three attempts:

| Attempt | Kind | Cause |
|---|---|---|
| 1 | gates | `decision-secret-is-a-block` inventoried but not named in prose |
| 2 | gates | `rule-everything-stays-in-one-world` inventoried but not named in prose |
| 3 | parse | reply unparseable; only its 400-char head survives |

**Read that as a brief-size effect, not bad luck.** The successful run's
`01-domain.md` carries 23 entities, 18 business rules and 21 workflows — **62
inventoried rows**, every one of which `check_inventory_has_prose` requires be
named by id in the prose body. It is all-or-nothing across all 62, so a model at
~98% compliance still fails, and it failed on exactly one row twice. A brief
with ten feature areas should expect roughly even odds on stage 1 and budget a
retry. Trim the brief's scope if a run has to be reliable.

**Two diagnostic notes this run proved out:**

- **At the time of this run (2026-08-06), the terminal display was not the
  per-attempt record** — it could name only the final attempt's failure kind:
  this run read `(parse failure)` when two of three attempts were *gate*
  failures on an unrelated axis. The terminal now reports every attempt's
  kind via a `retrying (attempt N) after <kind>` line per retry and a final
  `stopped after <kind>` line; open `.plan-tool/runs/<slug>/*.jsonl` for the
  specific violation message or parse detail, not to learn which kind failed.
- **The unusable reply is not kept** (the open half of BACKLOG #217). Attempt
  3's parse failure is undiagnosable: 400 characters survive of a 31,858-byte
  reply. Do not plan on root-causing a parse exhaustion.

**If the review loop will not converge** — the same objection resurfacing across
re-entries, or a fix needing structural rework — stop looping and surface it
rather than iterating indefinitely. A demo that shows the honest stopping rule
is better than one that hides four silent retries.

---

## 11. What the demo deliberately does not show

State these in the walkthrough so nobody reads absence as a gap:

- **Execution.** No `run`, no `reconcile-code`, no `/code-review` tail.
- **Framework lenses.** Arc position 05 is unauthored; stages run on the generic
  quality-attribute list, and `--framework` does not exist yet.
- **Decomposition quality scoring.** The gates enforce entity-id coverage and
  constraint discharge. Whether the seams are *right* is reviewer judgment and
  the tool does not score it — say so plainly.
- **A claim that roadmap produces better designs.** It does not, and the
  measurement says so: three plans for the same slice reached the same
  architecture. What layering buys is a **decision record** — settled calls with
  rejected alternatives, citable ids, and a do-not-re-open fence. Read
  `docs/evidence/roadmap-layering-measurement.md` § "How to read this result" before
  citing it; its null was misread once already, and that reversal is settled.
- **Any framing of the verb as a replacement for human authorship.** Settled
  2026-08-02, user-confirmed. It collaborates: it proposes, a human reviews, it
  re-proposes.

---

## 12. Execution checklist

- [x] Phase 0 — scratch repo, brief copied and committed
- [x] Phase 1 — four stages green, artifacts committed *(second run; see § 10)*
- [x] Phase 0b — scaffold authored from stage 3's components, mutation-checked
- [ ] Phase 2 — one **accepted** ledger item (candidate proposed, `--compare` output captured)
- [ ] Phase 2 — **≥1 decision confirmed `settled`** before submitting the refusal item
- [ ] Phase 2 — one **refused** ledger item, narrative evidence captured verbatim *(§ 5a — the frame the demo cannot ship without)*
- [ ] Phase 3 — `--materialize`, `--apply` preview, then `-y`; create lines captured
- [ ] Phase 4 — `create` on the visibility slice
- [ ] Phase 5 — bare-plan audit, conceptual gaps applied, re-audited
- [ ] Phase 6 — `detail --commit`, then detail-grounded re-audit
- [ ] Phase 7 — transcripts → walkthrough → deck → Artifact page
