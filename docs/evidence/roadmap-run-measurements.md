# Roadmap run measurements

Durable record of what the `roadmap` verb actually did on real briefs while arc
positions 01–04 were built (2026-08-01 through 2026-08-05). The raw artifacts,
run logs, and isolated plans dirs all live under `.tmp/` and `.plan-tool/runs/`,
which are gitignored and local to the machine that ran them — **this file is the
record**, not those paths.

**Companion documents.** The 2026-08-01 three-arm layering comparison has its
own write-up in [`ROADMAP_LAYERING_MEASUREMENT.md`](roadmap-layering-measurement.md)
— read its "How to read this result" before citing it. The verb's contract is
[`../ROADMAP_FORMAT.md`](../../ROADMAP_FORMAT.md); the end-to-end operator
walkthrough is [`ROADMAP_WALKTHROUGH.md`](../how-to/roadmap.md); the demo
runbook is [`ROADMAP_DEMO_ORCHESTRATION.md`](../demos/roadmap-demo.md).

## How to read every record here

**These records gate nothing.** No score, no threshold, no pass/fail. Each was
run once, with its outcome vocabulary fixed *before* the artifact was opened, so
that a negative result would be as reportable as a positive one — and several
are negative.

Every block is **n=1 or n=2**: one or two briefs, one reviewer, one first-pass
result. None of it establishes a hit rate, a typical retry count, or whether a
behavior generalizes. Where a block says something is unproven, that is the
finding, not a gap to be filled by reading the number more confidently.

Two outcome vocabularies recur, both fixed in advance:

- **Feedback responses:** accepted · partially accepted · declined · required
  clarification.
- **Artifact review** (stage 3 partitions, stage 4 mappings): reviewable ·
  reviewable with reservations · not reviewable · would redirect.

## 1. Id stability: regeneration versus revision

The measurement that shaped what emitted seeds are allowed to anchor to.

**Regeneration baseline (2026-08-02).** Two `--from-stage 1` runs on an
identical brief, neither carrying a predecessor, shared:

| Row kind | Shared across the two runs |
|---|---|
| entity ids | **85%** |
| workflow ids | **60%** |
| business-rule ids | **30%** |
| decision ids | **25%** |
| shared entities keeping their exact field-name set | **0 of 11** (47 vs 53 fields) |

Feedback naming a row ("decision-4's rationale is wrong") did not survive the
re-proposal it was feedback on. Feedback was durable only when edited in place
and the stage never re-run — precisely the case where the tool is *not*
collaborating. This is why emitted seeds anchor to **entity ids**, the only row
kind stable enough to cite across a re-author.

**Revision mode (position 02) answered it — measured 2026-08-04/05** on
`cfp-review`: **12 of 12** entities kept, **13 of 13** business rules, **12 of
12** decisions, **8 of 9** workflows (the ninth removed on request, with a cited
removal record).

Read that as the **gate working, not the model choosing well**:
`check_design_row_continuity` *enforces* survival — a row cannot vanish without a
cited removal.

**Field-name sets, captured 2026-08-05.** Missing from the first sample because
the baseline artifact had been overwritten in place; the fix was to copy both
artifacts aside and `chmod 444` them before running.

| | shared entities keeping their exact field-name set | total fields |
|---|---|---|
| **regeneration** (`--from-stage 1`, no predecessor) | **0 of 11** | 47 vs 53 |
| **revision** run A | **12 of 12** | 52 → 52 |
| **revision** run B | **11 of 12** | 52 → 54 |

Run B's single divergence is the entity the request named (`conflict` gaining
`override_note` and `overridden_at`, which "override it with a note" asks for);
no untouched entity moved a field. **So the standing rule that nothing
downstream may anchor to a field name is a statement about *regeneration*, not
about revision** — within a revision chain, field names are as stable as entity
ids. It does not license anchoring to them across a re-author.

## 2. Stages 1–2 on two briefs

**First real run, 2026-08-01** — `cfp-review`, a volunteer-conference CFP brief.
Exit 0, both artifacts gate-conformant and substantive: 13 entities / 13 rules /
9 workflows, then 19 constraints over a ranking that prioritized 3 of 7
attributes and marked one `not-load-bearing`, with every genuinely-open call
recorded `pending`.

**Second brief, 2026-08-05 — the verb runs on something that is not
`cfp-review`.** `toollib`, a community tool library: continuous weekly cadence
rather than an annual burst, physical inventory rather than documents, an
offline-capable desk as the hard environmental constraint, and a rota of
volunteers who each use it once a month as the constraint that outranks the
rest. Both stages passed first try on both runs (authoring $1.22, revision
$1.47), against `cfp-review`'s 3-of-3 and 2-of-3 on the constraints stage.

| | entities | rules | workflows | decisions | fields |
|---|---|---|---|---|---|
| `cfp-review` | 12 | 13 | 8 | 12 | 52 |
| `toollib` | 11 | 13 | 13 | 9 | 48 |

Two prompt-level negatives previously measured on one brief now hold on a
second: the ranking did **not** come back all-`prioritized` (4 / 2 / 1), and
`pending` was neither inflated nor abdicated — 3 of 9 domain decisions, and all
three are exactly the calls the brief left open. It also split a question the
brief posed as one: `decision-item-identity` came back **settled** (physical
copy as `item`, kind as `item-model`) while `decision-reservation-target` stayed
**pending** (does a reservation name *that* drill), which is a sharper reading
than the brief had.

**Row count does not explain retry pressure.** `toollib`'s constraints inventory
was 33 ids against `cfp-review` run 1's 35 — slightly smaller, and it passed
where the larger one spent every attempt. Whatever drives the retries is
content, not size; the prose-mention-gate hypothesis is not carried by this
pair.

**Constraints-stage attempts**, all samples: 3, 1, 1, 3, 1, 2 on `cfp-review`
and 1, 1 on `toollib`. Twelve samples across the two briefs never exceeded the
three-attempt budget, which is what closed the retry-budget question (recorded
in [`HISTORICAL_BACKLOG_DECISIONS.md`](../history/backlog-decisions.md) #215).

## 3. First real feedback loop, 2026-08-04

`cfp-review`, same brief, isolated under `--plans-dir`. A baseline run, then two
hand-written `open` feedback rows, then `--from-stage 1`.

| Run | Stage | Attempts | `prompt_bytes` | Cost |
|---|---|---|---|---|
| baseline | 1 · domain | 1 of 3 | 13,479 | $0.59 |
| baseline | 2 · constraints | **2** of 3 | 36,774 → 37,428 | $1.28 |
| revision | 1 · domain | 1 of 3 | 43,871 | — |
| revision | 2 · constraints | 1 of 3 | 67,624 | — |

Baseline $1.87, revision $1.62, **$3.49 total**. Carrying the predecessor
roughly triples stage-1 prompt size (13,479 → 43,871), and the revision run
still cleared both stages first try where the baseline spent a retry.

**Wall and advisory** (from the preserved run logs): baseline 275.0s, revision
224.5s, readability 163.5s, spelling 233.9s. **The prompt-budget advisory never
fired — `ok` on all ten calls**, worst headroom 0.902 at the largest prompt
(68,881 bytes ≈ 19,681 tokens against a 200,000 window), where `warn` needs
headroom below 0.40. Derived from the logged `prompt_bytes` through the shipped
thresholds rather than captured off stderr; the margin is wide enough that the
difference between the run-log byte count and the backend transport's cannot
change the level. The advisory reaches this verb through `shell.py:claude_invoke`'s
backstop, not a `roadmap.py` import — worth stating, because the absence of that
import reads as an absence of the advisory and is not one.

**Per-id outcomes:**

| Feedback id | Kind | Outcome | Document action |
|---|---|---|---|
| `fb-conflict` | redirect (row-target) | **accepted** | row deleted |
| `fb-heavy` | ambiguous (artifact-target) | **accepted** | row deleted |

- **`fb-conflict`** ("drop the `conflict` entity, express it as a rule on
  `assignment`") — **refused, correctly.** The model kept the row and answered:
  *"unlocking this is your move rather than mine.
  `decision-conflict-is-an-entity` is `settled` and anchors to `conflict`, so
  this revision cannot drop the row."* **Verified true**: that decision exists,
  is `settled`, and anchors to `conflict`. This is the transitive settled-anchor
  block firing in production on its first real exercise — without it the stage
  would have oscillated between gate 3 and `check_decision_records` until the
  budget was gone.
- **`fb-heavy`** ("the reviewer side feels too heavy") — answered with a
  concrete trim: `flow-declare-conflict` removed, cited to `fb-heavy`, folded
  into `flow-assign`, with what remains enumerated.

**Reviewer's verdict, 2026-08-04 — both responses accepted.** The reviewer read
both and agreed with each; both rows were closed by deletion. The clarifying
question inside `fb-conflict` was conditional on re-opening the decision, so
accepting the refusal made it moot.

Both accepted, so nothing was deferred or reopened at the close — an honest
result rather than a manufactured spread across the vocabulary. **The
clarification arm is recorded as a within-loop event, not a fifth outcome:** the
readability re-run's question fired *before* the verdict and its row still
closed as accepted, so "required clarification" describes a turn in the exchange
that this exercise never ended on.

**This is the position's first end-to-end proof.** A human wrote two requests in
their own words, the model revised rather than regenerated, the human read the
answers, judged them, and closed the loop in their editor. No gate can produce
that sentence.

### 3a. Readability round, 2026-08-04

Same brief, same two requests. The reviewer's verdict on the first pass was that
the response could not be read: it used `assignment`,
`rule-declared-conflict-wins`, `kind` and `source` bare, and leaned on "batch" —
a term the artifact never defines, so there was nothing to look up. The reviewer
proposed a static site for linking concepts; the diagnosis instead was that
presentation was not the defect. A site renders the same unreadable sentence,
and it would add a second review surface while the reviewer still has to act in
the editor.

Fixed in `plan_tool/prompts/roadmap-revision.md`: the old *"name those ids"*
instruction fought the *"in plain language"* one and won. It is now *say what a
thing is the first time you name it* plus *use no word the artifact does not
define*. **Not a checker** — response quality is unfalsifiable, and a matcher
over it is the withdrawn `change_type` contract again (`CLAUDE.md` § "Withdrawn").

Re-run with only the contract changed, both rows reopened, requests byte
identical ($1.50, both stages first try, `prompt_bytes` 44,968 / 68,881):

- invented vocabulary → **zero** ("batch", "pipeline", "downstream" all 0);
- every id now arrives introduced — `conflict` as *"the record saying one
  reviewer must never be given one proposal"*, `assignment` as *"the record that
  hands them one proposal"*;
- the refusal now names the unblocking edit: *"set
  `decision-conflict-is-an-entity` to `status: pending` in this file and
  re-run"*;
- **the clarification arm fired**, unprompted and for the first time: *"when a
  reviewer says 'I know this speaker' a week into reviewing, should the system
  keep that statement so the next round of assignments skips the pair too?"* The
  arm was never missing a mechanism — the prompt was letting the model hide
  ambiguity behind jargon. Writing for the reviewer forced it out.
- **The reopen path and a twice-carried removal both worked**: reopening two
  `awaiting-review` rows re-sent them, and `flow-declare-conflict`'s removal
  record survived a second revision — the model-permanent/reviewer-prunable
  contract holding across two revisions.

**Two design defects the reviewer found that no test or audit did**, both fixed
the same day and both discovered only by using the thing:

- *the response was unreadable* — bare ids and invented vocabulary; fixed in the
  response contract, which incidentally produced the first clarifying question
  above;
- *closing a row loses the decision it settled* — a `removals` record and a
  `settled` decision each carry their own trace, but a feedback-driven
  **modification** left none, and even a recorded removal keeps the model's
  one-line rationale rather than the exchange. Fixed by a rule in the revision
  prompt: record the conclusion in a `decisions` row citing the feedback id,
  rather than retaining the conversation. Retention was rejected on measured
  grounds — carrying the predecessor already took stage-1 `prompt_bytes` from
  13,479 to 43,871, so an ever-growing transcript spends the budget the loop
  needs.

## 4. The decision-record rule: four branches, all confirmed

Added 2026-08-04: a change a later reader would question must leave a
`decisions` row citing the feedback id, with explicit carves for changes that
need none. It reads as two branches and is four.

| Branch | Contract | Evidence |
|---|---|---|
| **Positive** — a change a later reader would question | *must* mint or update a row | ✅ confirmed 2026-08-05 |
| **Carve A** — typo, reword, field name made consistent | must **not** mint | ✅ 1 sample |
| **Carve B** — the change is a `removals` record | must **not** also mint about the **removed row** | ✅ confirmed 2026-08-05 (narrow) |
| **Carve C** — refusing a change a `settled` decision blocks | must **not** mint | ✅ confirmed 2026-08-05 |

**Positive.** A request softening `rule-conflict-blocks-review` for inferred
same-employer conflicts landed the change and minted
`decision-employer-conflict-is-overridable`, citing
`fb-employer-conflict-override` and anchored to the changed rule. It marked the
row **`pending`**, not `settled`, because the override carries a cost it would
not decide alone — the `pending` review channel used as designed rather than
manufactured certainty.

**Carve A.** A spelling request ("Talk proposal" → "Talk Proposal") landed the
change and added **zero** decision rows (12 → 12), with removals, entities,
rules and workflows untouched ($2.20, 233.9s wall). That was the failure mode to
fear — a model freshly told decisions matter minting one for a capital letter.

**Carve B — narrow.** Dropping `rule-one-review-per-pair` wrote the removal
(rules 13 → 12, citing `fb-drop-one-review-rule`) **and** minted
`decision-review-uniqueness-is-storage` on the surviving
`rule-three-review-threshold` — which holds under the narrow reading. The
narrow-vs-broad call is settled; see
[`HISTORICAL_BACKLOG_DECISIONS.md`](../history/backlog-decisions.md).

**Carve C — confirmed, and by accident.** A request to lower the three-review
threshold to two was **refused**, citing `decision-threshold-hides-not-warns`,
and minted **no** decision. It was authored as the *positive* case on a mistaken
reading, which is why it landed here — see the trap below.

**The methodological trap, worth more than the result.** The threshold request
was authored as the positive case after "verifying" no settled decision blocked
it. The verification was wrong: the check printed a `choice` key that does not
exist — the field is **`chosen_option`** — so it silently printed nothing and
the absence was read as absence of *content*. `chosen_option` pinned the number
outright ("Below **three** reviews the chair view shows no aggregate at all").
**A key lookup that returns nothing is not evidence; confirm the key exists
before reading meaning into its emptiness.**

**One retry nothing could explain, and the fix it motivated.** The Carve A
spelling run spent a stage-1 retry: the run log shows attempt 1 returning
`rc: 0` with 22,746 stdout bytes — a full reply, so not `FAILURE_INVOKE` — and
no `gate_violations` event, so not `FAILURE_GATES` either. That leaves
`FAILURE_PARSE` or `FAILURE_AUTHORED_REVIEW_ROWS`, and at the time **no event
recorded which**. Attempt 2 passed and Carve A's result stands, but the run was
not the clean first-try pass a cost figure alone implies. Suggestive of the new
rule and **unproven**: stage 1 is the prompt that gained it, and one sample
cannot separate that from ordinary variance. The `AttemptFailed` run-log event
(shipped 2026-08-04, BACKLOG #217's first half) makes such a retry readable, so
a repeat is scorable. Both 2026-08-05 runs passed every stage first try and
recorded zero `attempt_failed`, exercising its negative case in production.

## 5. First real stage-3 run (components), 2026-08-05

`toollib`, the community tool-library brief. Chosen because `01-domain.md` and
`02-constraints.md` already gate-clean from the same day's authoring/revision
runs, copied into an isolated plans dir.

```bash
plan-tool --plans-dir .tmp/roadmap-03-components.plans roadmap toollib \
  --from-existing .tmp/roadmap-measure.toollib-concept.md --from-stage 3
```

The parent `plan-tool run roadmap-03-components` held the repo mutation lock, so
execution called `run_roadmap(..., from_stage=3)` with the same paths —
identical orchestrator, no CLI wrapper.

| Gate-observable | Value |
|---|---|
| Entities (from `01-domain.md`) | 11 |
| Components | 9 |
| System patterns | 7 |
| Component patterns | 5 |
| Prioritized constraints (4 attributes) | 14 |
| Prioritized constraints discharged | 14 / 14 |
| Entity coverage | every `EntityRow.id` in ≥1 `ComponentRow.entity_ids` |
| `run_components_gates` | `[]` (re-parsed through `load_components_artifact`) |

**Operational:** **1** attempt of 3, `prompt_bytes` **69,118**, prompt-budget
advisory **ok** (headroom 0.901), wall **85.0s**, cost **$0.78**. Exit
`completed`; CLI view: one artifact written, 1 pending decision, 0 feedback
awaiting review. No `gate_violations` or `attempt_failed`.

**Partition outcome: reviewable with reservations.** Gate-clean and readable,
but two seams would get feedback before seed derivation. No stage-3 revision was
run, so the open `pending` decision is documented in the artifact rather than
exercised through a feedback row.

One line per component: `component-lending-desk` (checkout and return on the
volunteer's device; must survive Saturday bursts with the connection down) ·
`component-promises` (reservations and opening sessions) · `component-collection`
(what the library owns, lendability state, service history) ·
`component-membership` (member records and borrowing blocks) ·
`component-money-owed` (fees and waivers as a ledger outliving the loan) ·
`component-rulebook` (committee numbers and the opening calendar) ·
`component-sync` (background replay of device records after an outage) ·
`component-catalogue` (read-only browse during the week) · `component-reports`
(read-only quarterly aggregates).

**Seam judgment.** The offline-facts / online-promises cut matches the brief's
stated failure mode (two volunteers, two sheets) and the desk constraint. Sync
separated from counter screens is arguable and well-motivated. Sharing `session`
between rulebook and promises is explicit (`dec-session-shared-by-two`) rather
than accidental. Nine components is slightly fine-grained for seed sizing —
membership could ride with money-owed — but each bundle is coherent enough to
argue about.

**Pattern usefulness.** System patterns name redirectable ideas a reviewer could
push on (`pattern-past-tense-offline`, `pattern-device-first-write`) rather than
gate filler. Component patterns (`pattern-ledger`, `pattern-reference-data`) are
generic labels but tied to specific discharge claims in the prose.

**Pending decision.** `dec-copy-state-to-device` — whether the desk lends from a
stale offline copy of lendability state or stops when the connection drops. The
artifact states the tradeoff plainly; it is the one call a reviewer would settle
before trusting the partition for seeds.

## 6. First real stage-4 run (plan derivation), 2026-08-05

`toollib` again, continuing from the stage-3 artifacts.

```bash
plan-tool --plans-dir .tmp/roadmap-04-plan-derivation.plans roadmap toollib \
  --from-existing .tmp/roadmap-measure.toollib-concept.md --from-stage 4
plan-tool --plans-dir .tmp/roadmap-04-plan-derivation.plans roadmap toollib \
  --apply
```

Same lock situation as stage 3: `run_roadmap(..., from_stage=4)` directly. Apply
preview used `apply_roadmap_seeds(..., allow_apply=False)`; single-plan
promotion used `_promoted_seed_body` + `atomic_write_text`, matching step 7's
copy semantics.

| Gate-observable | Value |
|---|---|
| Components (from `03-components.md`) | 9 |
| Plans | 8 (`keep` 5, `merge` 2, `cross-cutting` 1) |
| Assumption rows | 6 |
| Draft seeds on disk | 8 under `seeds/` |
| Component coverage | every `ComponentRow.id` on ≥1 plan row |
| Plan ↔ seed bijection | 8 referenced, 8 on disk, 0 orphans |
| `run_plans_gates` | `[]` (re-parsed through `load_plans_artifact`) |
| Provenance parse | every draft's `roadmap_components` resolves |
| Ordering | 8 entries, every plan id once, dependencies resolve |
| Slug shape | all plan ids match `create`'s slug rule |
| Repo-root `plan-seeds/` | untouched by the stage-4 run itself |

**Operational:** **2** attempts of 3, `prompt_bytes` **88,592** then **89,015**,
prompt-budget advisory **ok** (headroom 0.873), wall **685.4s**, cost
**$1.38 + $1.35 = $2.73**. Exit `completed`. Attempt 1 failed with
`failure_kind: parse` (no `gate_violations`); attempt 2 passed. CLI view: one
artifact written, 2 pending decisions, 0 feedback awaiting review, eight ordered
`create` handoff lines.

**Mapping outcome: reviewable with reservations.** Gate-clean and readable, but
two `pending` decisions (`dec-stale-state-binds-two-plans`,
`dec-online-reserve-shapes-promises`) would get operator confirmation before
trusting the set for `create`. No stage-4 revision was run.

**Seed verdict: seeds reviewable.** Each draft carries a provenance block,
scope-contract fence, settled-decision fences, and inter-plan assumptions scoped
to consuming plans only; rejected-alternative *reasons* stay in `04-roadmap.md`
rather than being copied wholesale into seed bodies.

One line per plan row: `rulebook-and-calendar` (`keep`) — sized alone because
five downstream plans depend on it · `append-only-record-spine`
(`cross-cutting`, four components) — the append-only write discipline, carved
out so four owners adopt one shape · `collection-and-membership` (`merge`) —
item register, model catalogue, service notes and member records as one
reference-data slice · `desk-lending` (`keep`) — the two counter screens,
indivisible at checkout/check-in · `outage-catch-up` (`keep`) — getting device
records out and replaying them safely · `promises-on-items` (`keep`) —
reservations and renewal authority · `fees-and-waivers` (`keep`) — what a member
owes and a volunteer forgiving part of it · `catalogue-and-reports` (`merge`) —
weekday catalogue and quarterly report as one read-side slice, last in ordering.

**Mapping judgment.** The two merges match how a reviewer would size from nine
components — membership alone would be fence-heavy, and both read-side views
share the same slow-read contract. The `cross-cutting` carve for append-only
discipline is the strongest structural choice: replay safety depends on four
stores agreeing, and repeating it in each owning plan would multiply surface.
Eight plans for nine components is slightly fine-grained but arguable.

**Ordering judgment.** Rulebook first, spine early, desk before promises, sync
after desk, fees after returns exist, catalogue last — follows the offline line
and matches the runnable `create` lines as printed. Dependency targets resolve.

**Seed spot-check.** `desk-lending` (`keep`) — provenance cites
`component-lending-desk`; scope fence lists checkout/check-in screens, pending
upstream decisions flagged without re-litigating settled ones; inter-plan
assumptions (`assume-device-holds-its-own-copy`, etc.) appear only where this
plan consumes them. `collection-and-membership` (`merge`) — provenance cites
both merged components; the `dec-copy-state-to-device` pending call binds this
plan and `desk-lending` with the same recommended answer; rejected-alternative
prose from `04-roadmap.md` is not duplicated — the seed points at settled
decisions and pending rows by id.

**Apply exercise.** Preview recommended eight promotions with no collisions.
Promoted **`rulebook-and-calendar` only** — provenance YAML block stripped, body
starting at `# Seed: the rulebook and the opening calendar`. Batch `-y` was
deliberately not run, because eight destinations would write. The
slug-directory draft was left unchanged and the promoted copy removed before
commit, so the repo footprint stayed one file.

## 7. Bare-plan audit on a stack contradiction, 2026-10-08

One plan, one pair of conceptual passes (n=1, `limited`; gates nothing).

A one-step plan carried a `## Stack` that named PostgreSQL while its Architecture
and its step used a local SQLite file. `plan-tool completeness-audit --iterate`
at the bare stage returned a HIGH `plan-correctness` finding quoting both texts
in both conceptual passes. The audit prompt needed no change on this evidence.
The result supports `ROADMAP_FORMAT.md` § "Stack section" naming the plan audit as
the contradiction check; it does not show a hit rate, and the tool itself never
judges the contradiction.
