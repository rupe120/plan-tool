# Roadmap walkthrough — one concept brief to implementation plans

This is a command-first walkthrough of `plan-tool roadmap`. It follows a project-sized concept from a brief, through four reviewable artifacts, into draft seeds and ordinary plans. The artifact observations use the real `cfp-review` run — a volunteer conference's CFP system — but the commands use `my-project`; replace that slug and brief path on the initial command.

Run every command from the consuming repository's root. `roadmap` writes there, not in the `plan-tool` source repository.

Recipes and recovery live in [`RUNBOOK.md`](../../RUNBOOK.md); the artifact schema and gates are in [`ROADMAP_FORMAT.md`](../../ROADMAP_FORMAT.md); every option is in [`docs/cli/roadmap.md`](../cli/roadmap.md). This page concentrates on the order in which an operator uses the commands and what each command leaves behind.

## Command sequence at a glance

Replace `<roadmap-plan-id>` with an existing `plans[].id` from the accepted
`04-roadmap.md`; substitute its actual reported seed paths for the draft and
promoted path placeholders. These are not commands to run blindly as one script. The two promotion forms and the two seed paths are alternatives: use the form that matches the handoff you want.

```bash
plan-tool roadmap my-project --from-existing docs/concepts/my-project.md
plan-tool roadmap my-project --view walk
plan-tool roadmap my-project --view ledger
plan-tool roadmap my-project --view index --id <row-id>
plan-tool roadmap my-project --view walk --mode review
plan-tool roadmap my-project --view html --output .tmp/my-project.roadmap.html
plan-tool roadmap my-project --compare [--comparison-base VERSION_ID] [--comparison-target VERSION_ID] [--comparison-output {cards,patch,json}]
plan-tool roadmap my-project --submit-feedback ITEM_ID --feedback-target domain:row:ROW_ID --feedback-request TEXT
plan-tool roadmap my-project --propose-candidate
plan-tool roadmap my-project --reopen-ledger-feedback ITEM_ID
plan-tool roadmap my-project --settle-decision domain:<decision-id> --settlement-evidence domain:<feedback-id> --confirm-decision-settlement
plan-tool roadmap my-project --materialize
plan-tool roadmap my-project --materialize <roadmap-plan-id>
plan-tool roadmap my-project --accept-seed <roadmap-plan-id>
plan-tool roadmap my-project --apply
plan-tool roadmap my-project --apply -y
plan-tool create <roadmap-plan-id> --from-existing <reported-draft-path>
plan-tool detail <roadmap-plan-id>
plan-tool completeness-audit <roadmap-plan-id>
plan-tool run <roadmap-plan-id> --commit
```

---

## 1. Start with a concept brief

Use `roadmap` when the work is project-sized and you cannot yet name its domain or explain its important trade-offs. If you can already write a focused `create` seed, use `create` directly: `roadmap` makes four backend calls to establish shared vocabulary and a citable decision record, not to replace design work.

Write one markdown brief in your own words. It should state:

- the scale and load shape;
- what has gone wrong before or must not go wrong; and
- the calls that are still open.

For `cfp-review`, the brief described roughly 1,500 proposals and 400 reviewers, 60% of submissions arriving in the final two days, two volunteer maintainers, blind review in both directions, and an actual colleague-scoring incident. That is enough context for the later artifacts to distinguish a real trade-off from a generic checklist.

### Reuse the slug, or start a successor

A roadmap slug identifies one concept lineage, not one execution attempt.

| Situation | Action |
| --- | --- |
| The recorded brief is still the intended product definition, and reviewer feedback asks for a bounded correction | Reuse the slug and revise through feedback (section 6). |
| The product domain, outcome, or intended artifact lineage changes, and the prior roadmap must stay readable as evidence | Start a successor: a new slug with a fresh brief. |
| The work is already a focused, plan-sized slice | Skip the successor roadmap and write a `create` seed. |

Name a successor `<product>-<concept-boundary>` in lowercase kebab case, and pair it with `<slug>-concept.md`. Do not use dates or `v2` merely to tell a rerun apart.

`roadmap` has no rename, migration, or successor command, and none is planned. A consumer that needs a tool-owned lineage record, not one it keeps itself, first names the specific failure in the current new-slug and source-identity contract, then writes a bounded plan.

### Convert an older roadmap folder by hand

Every roadmap stores its content once, as immutable versions under an accepted head. A folder written before that model keeps its four artifacts as top-level `01-domain.md` through `04-roadmap.md` files, which no command reads. No tool converts such a folder. Two cases need a hand step.

**A folder with no accepted head.** Every command that reads the roadmap (the views, `--compare`, the seed routes, and `create --from-existing` on a roadmap seed) refuses with `roadmap '<slug>' has no published version`. When top-level artifact files exist, the refusal adds that they predate versioned roadmaps and are not read. A stage run refuses the same folder and lists every path that blocks it: top-level `0N-*.md` files, `feedback-ledger.yaml`, `seed-state.json`, a populated `.roadmap-versions/`, and the draft-seed directories. Either:

1. Move or delete the listed paths, then run `plan-tool roadmap my-project --from-existing docs/concepts/my-project.md` again. Deleting `feedback-ledger.yaml` discards its feedback rows.
2. Start a successor slug from the brief (see the table above).

**An enrolled folder with leftovers.** A folder that already has an accepted head keeps working. Delete the leftover top-level `0N-*.md` files, `source.json`, `.roadmap-baselines/`, and `.roadmap-rollbacks/`; no command reads any of them. A reader that opens a bare `04-roadmap.md` would ground on the superseded copy, so `--view`, `--materialize`, `--refresh-seeds`, `--accept-seed`, and `--apply` print a warning on stderr naming each top-level `0N-*.md` file that sits beside an accepted head. The warning never changes an exit code or a rendered view.

A roadmap folder holds only these files: the version store (`.roadmap-versions/`, which holds the accepted-head record), the feedback ledger, `seed-state.json`, `INDEX.md`, the draft-seed directory, and `.plan-tool/evidence/` inside the roadmap folder (not the repository's run-log `.plan-tool/`).

## 2. Generate the roadmap

Run the full four-stage pipeline against the brief.

```bash
plan-tool roadmap my-project --from-existing docs/concepts/my-project.md
```

The command is non-interactive. It holds each gate-clean stage in memory and in the resume directory (see section 3). Once all four stages pass, it publishes one immutable version holding the four artifacts, a ledger-native feedback ledger, and the accepted head (written last), then deletes the resume directory and writes `INDEX.md`. It writes under `docs/implementation-plans/roadmaps/my-project/` and does not create a plan manifest entry. Roadmap artifacts are not plans, so `list`, `status`, and `run` cannot resolve the roadmap slug.

The stage run is first-run only. Once an accepted head exists, a stage run refuses and names the head. A roadmap with a head changes through ledger feedback and candidate review (section 6); put semantic changes there, or start a successor slug.

`INDEX.md` in the roadmap folder is generated for people. It lists the accepted head and every stored version with its status (`accepted head`, `promoted`, `active`, `superseded`, or `unrecorded`), and the tool rewrites it after every version-store change. No command reads it; edit nothing in it.

If an upstream choice is already approved, add the optional closed `## Carried decisions`
JSON block to that submitted brief; `ROADMAP_FORMAT.md` defines its exact shape.
Roadmap preserves each accepted decision as one inherited `decisions` row in its
declared owner artifact. During review, inspect its source citation, `settled`
status, owner artifact, and local anchor. That row records an upstream-approved
choice rather than a Roadmap trade-off, so it may omit rationale and rejected
alternatives when the upstream record did not supply them. Feedback and ordinary
revisions cannot add, edit, or remove it; an unrelated revision preserves it and
must revalidate its citation against the current accepted brief before publishing.
This narrow input does not add per-stage supplementary sources or multi-source
identity; those remain deferred under #383.

For normal roadmap stage runs, lifecycle lines on stderr report only the last
confirmed transition. Silence after a line is not a heartbeat or proof that the
backend remains live; inspect `.plan-tool/runs/my-project/*.jsonl` for detailed
attempt diagnosis, including an exhausted stage. This lifecycle guidance does
not apply to views, seed operations, or other non-stage routes.

| Stage | Artifact | What to read for |
|---|---|---|
| 1 | `01-domain.md` | Entities, business rules, workflows, and decisions — especially the domain seams. |
| 2 | `02-constraints.md` | One disposition for every quality attribute and the constraints that support the ranking. |
| 3 | `03-components.md` | Logical component ownership, selected patterns, and constraint discharge. |
| 4 | `04-roadmap.md` | Ordered plan rows with intent, delivery shape, and non-goals; cross-plan assumptions; and draft-seed destinations for later materialization. |

A gate failure retries the current stage; a completed run can still contain `pending` decisions. Pending is a review queue, not a failed run.

### Stage 1 — read the domain for seams

The `cfp-review` run produced twelve entities, thirteen business rules, nine workflows, and twelve decisions. Its valuable calls were structural:

- `assignment` and `review` were separate entities, allowing a batch to be reassigned before a review is written.
- `conflict` was an entity rather than a reviewer flag, so it could outlive an assignment and carry the kind and source that support `rule-declared-conflict-wins`.

A missing entity is cheap to add. A wrong seam becomes expensive once plans start citing it. Treat non-entity IDs as revision-local names; entity IDs are the most stable ones, but still review them before depending on them.

### Stage 2 — read the constraints as a ranking

The `cfp-review` disposition table ranked `reliability`, `security`, `maintainability`, and `availability` as `prioritized`; it traded away `fault-tolerance` and `performance`; and it marked `scalability` as `not-load-bearing`.

That is useful because the conference's load is calendar-bounded and the submission spike must preserve the accept path, not because every quality attribute is important. An all-`prioritized` table ranks nothing; that usually means the brief did not state what the project will spend.

### Stage 3 — read components for ownership and discharge

Each component names the entity IDs it owns, the patterns it applies, and the prioritized constraints it discharges. Gates verify the traceability relations, but they cannot decide whether the decomposition has good seams. That is the reviewer's job.

### Stage 4 — read the plan mapping before creating plans

`04-roadmap.md` maps components to ordered plan rows. Start each review with the
row's **intent** (the operational outcome), **delivery shape**
(component-owned or cross-cutting), and **non-goals** (what it deliberately
does not deliver); these say why the row exists before its dependencies and
assumptions explain how it fits. Each row has a slug-relative `draft_seed_path`
where its draft will live after materialization. A stage-completion handoff line
is runnable only when that draft classifies `current`; a fresh stage-4 run has
no materialized drafts. Then read the ordering, assumptions, and seed fences
before materializing, promoting, or creating anything. Read these artifacts
through the accepted head; top-level leftovers do not override its immutable
stored version. Materialization carries each selected row into a seed without
repartitioning the accepted mapping.

Review the plan rows as one **smallest end-to-end proof**, not as an eventual
product backlog. Identify the one concrete path and observable result they
collectively establish. Every row must be necessary to that result; nearby
roles, workflows, integrations, operating modes, and generalized mechanisms
belong in a row's non-goals or a later roadmap, not as extra current slices.
Keep that review at roadmap altitude: it judges outcome, tradeoffs, ownership,
and ordering, while `create` and `detail` own repository-grounded files, APIs,
storage schema, implementation mechanics, and tests.

### Compare two snapshots before choosing a separate action

Use comparison when a review needs the accepted head and another stored
immutable version in one evidence-bound view:

```bash
plan-tool roadmap my-project --compare
plan-tool roadmap my-project --compare --comparison-base VERSION_ID --comparison-target VERSION_ID --comparison-output patch
```

The first form compares the accepted head with the active candidate. With no
active candidate it refuses and asks for `--comparison-target VERSION_ID`; an
omitted `--comparison-base` always means the accepted head. The second form
selects both stored versions explicitly. Cards are the default,
`json` is deterministic machine-readable output, and `patch` prints Git's
complete unified diff across the exact four artifact pairs. The cards and JSON
explain that evidence; they do not replace it. Raw-only bytes remain identified,
and a stable-id change is a removal plus an addition rather than a guessed
semantic match. When the target is a stored candidate whose direct predecessor
is the base, cards and JSON also list its row-linked prose amendments
(artifact, row id, fragment) under the outcome `bound`. A directly bound
candidate that stored no operation evidence says `no-operation-evidence`;
other pairs say `not-applicable` or `not-directly-bound`. The patch is
unchanged. The command refuses incomplete, invalid, or unselected default
snapshots instead of producing partial evidence.

Comparison is read-only and accepts no companion roadmap option. It does not
accept, promote, settle, repair, or otherwise change either snapshot.
After review, choose any acceptance or lifecycle action separately and
explicitly; comparison output is not an acceptance action.

---

## 3. Recover from a stage run that didn't finish

Any way a first stage run can stop before publication — an invalid stage, an
exhausted attempt budget, an operator interrupt, a crash — leaves the resume
directory, `.plan-tool/runs/my-project/roadmap-stage-resume/`. It holds one
`stage-<N>.md` per gate-clean stage and a `brief.digest`. The roadmap folder
stays empty: nothing is published until all four stages pass.

A crash *during* publication differs: it leaves a publication journal and
possibly some version members in the roadmap folder. The next stage run
recovers the journal first, rolling back a head-less publication to the held
stages or recognizing a completed one, and then proceeds. A completed one
ends in the refusal `already has an accepted head`, with the journal cleared;
that is the expected outcome, and the roadmap is published.

Re-run the same command to resume:

```bash
plan-tool roadmap my-project --from-existing docs/concepts/my-project.md
```

The run re-gates the held stages in order and resumes from the first stage
that is missing or fails its re-gate. A held stage that is unreadable or fails
its re-gate is regenerated with a warning, not refused. The directory is the
tool's state, not an input: do not edit its files.

**A changed brief refuses.** The held stages belong to the brief whose digest
they recorded. When the brief's text differs, the run refuses before any
backend call and names the directory. Pick one:

1. Restore the original brief and re-run.
2. Delete the named `roadmap-stage-resume/` directory by hand, then re-run to
   start over. Delete only that directory, never the run-log directory
   `.plan-tool/runs/my-project/`, which also holds the run logs.
3. Start a successor slug (section 1).

A completed run deletes the resume directory. A stage run beside an accepted
head refuses (section 2).

An unwritable resume directory is fatal by design: the run holds each stage
before it continues, so it stops at the first write (after stage 1 passes its
gates) with `cannot hold stage 1 for resume`, and that stage's reply is not
kept. Make `.plan-tool/runs/my-project/` writable and re-run.

This resume directory is unrelated to `plan-tool checkpoint list`/`clear`,
which is a different subsystem: the create/detail authoring cache that
memoizes a Claude round-trip by content hash. See
[`RUNBOOK.md`'s "Workflow: recover from an interrupted create/detail
run"](../../RUNBOOK.md#workflow-recover-from-an-interrupted-createdetail-run)
for that one instead.

---

## 4. Inspect the roadmap without calling the backend

The inspection views make the relationship between the artifacts easier to check. They read the accepted version and need no brief, invoke no backend, and leave canonical roadmap state unchanged; html writes its derived page.

Start with the compact summary. It reports the highest-priority artifact,
reference, seed, decision, and feedback concerns, followed by copy-pasteable
commands for the detailed views.

```bash
plan-tool roadmap my-project --view summary --mode review
```

Show the traceability walk across all stages.

```bash
plan-tool roadmap my-project --view walk
```

Show the decision ledger to review settled and pending choices together.

```bash
plan-tool roadmap my-project --view ledger
```

Show the reverse citation index for every design row.

```bash
plan-tool roadmap my-project --view index
```

Trace the rows that cite one specific ID. Use an ID from your artifacts — for example, the `cfp-review` entity ID `conflict`.

```bash
plan-tool roadmap my-project --view index --id conflict
```

Include feedback rows and removals in the traceability walk while reviewing a revision.

```bash
plan-tool roadmap my-project --view walk --mode review
```

Read the artifacts themselves, rather than a projection of their state, as one
self-contained page formatted to be read — and printed — on paper, not a dump
of the files into markup: each artifact section
(Domain/Constraints/Components/Plans) frames its own card in one artifact
accent, and each collapsible block inside it — Entities, Decisions,
Feedback, and the rest — carries its own concept accent so the blocks read
as distinct at a glance; table headers repeat on every printed page, the
first artifact follows the page header, and each later artifact begins on
its own sheet. Every parsed row of all four artifacts
renders — including the quality-attribute dispositions, hosting rows, stores,
and pattern statements the text views above do not carry — with each resolvable
forward reference linking to the row it names and dangling or ambiguous
references visibly marked. `--mode review` adds the feedback rows and removals
here too.

The domain section opens with an ER-style diagram: one box per entity carrying
its id and its fields, and an arrow from each `reference` field to the entity
it names. Clicking a box jumps to that entity's row in the table below it, and
a field whose target is missing, ambiguous, or not an entity is marked in the
picture with the same wording the table uses. Two things it deliberately does
not draw: **cardinality and optionality**, which the domain schema records
nowhere — so no crow's feet, and no mark to mistake for "exactly one" — and
business rules and workflows, which relate any number of entities at once and
stay in the tables where a row can list them all.

Unlike every other view, `html` writes a file **by default** — a review page
is meant to be opened (and printed), not piped. Omit `--output` to write
`<roadmap-dir>/review.html`; pass a path to choose the destination instead;
pass `--output -` to print the page to stdout instead.

```bash
plan-tool roadmap my-project --view html
plan-tool roadmap my-project --view html --output .tmp/my-project.roadmap.html
```

The page loads nothing over the network and runs no script, so it opens
straight from disk, and its bytes are a pure function of the artifacts — two
renders of an unchanged roadmap are identical, so it diffs cleanly. It
deliberately does not repeat `--view index`'s reverse citations or
`--view seeds`' draft freshness, and it prints artifact prose verbatim rather
than interpreting the markdown.

Each of the other views starts with a named banner. In an interactive terminal,
plan titles,
section labels, decision states, citation IDs, and artifact-read warnings are
styled separately so the hierarchy is easier to scan; redirected output stays
plain and keeps the same text structure. `--view html` takes neither the banner
nor the styling: its output is a document, and framing it would corrupt it.

---

## 5. Settle a pending decision

Settle a load-bearing `pending` decision with:

```bash
plan-tool roadmap my-project --settle-decision domain:decision-id \
  --settlement-evidence domain:feedback-id \
  --confirm-decision-settlement
```

One decision per settlement: `--settle-decision <artifact>:<decision-id>` names the
selected `pending` row; `--settlement-evidence <artifact>:<feedback-id>` names
the reviewer evidence that cites it and carries reviewer-authored `request`
text — an open ledger item that is still eligible for the accepted version;
`--confirm-decision-settlement` is the required, explicit confirm. It
invokes no backend and refuses an inherited row, a non-`pending` decision,
unreviewed evidence, or a stale source.

Before any canonical write it publishes an immutable, redacted receipt to
`<roadmap-dir>/.plan-tool/evidence/decision-settlements/`, committed to
`HEAD`. The receipt proves the settlement for as long as the settled version
stays in the accepted head's predecessor chain.

Ledger submission and candidate review do not settle a decision. Settlement is
a separate selector-bound operation with its own confirmation evidence.

**Settling while a candidate is active.** A settlement that would stale the active candidate does not write anything on the first
call. It returns `confirmation-required` and prints the exact
confirmation-evidence receipt final. Apply the response in a separate
invocation with `--respond-decision-settlement RECEIPT_FINAL
--decision-settlement-yes` (or `--decision-settlement-no` to decline); there is
no prompt and `-y` is not a confirmation. With no active candidate, the single
call above settles. To take that route, release the candidate first with
`--reject-candidate` or `--discard-candidate` (§ 6).

**Two permanent limits** (neither is a bug this capability owes a fix for —
each is documented, not worked around):

1. **An unpromoted selector-era candidate lineage blocks settlement, with no
   way to abandon it.** The runner refuses as
   `unpromoted-candidate-lineage` whenever a stored selector-era admission
   (no recorded root) has a `predecessor_version_id` equal to the current
   accepted head, regardless of the admission's age or state (`BACKLOG.md`
   #395). A ledger-batch candidate is not subject to this limit: release it
   with `--reject-candidate` or `--discard-candidate`.
2. **Non-canonical accepted bytes block settlement, with no repair path.** A
   stored version's bytes are immutable by design, so there is nothing to
   normalize or rewrite.

---

## 6. Turn reviewer ledger feedback into a candidate

The ordinary workflow begins in the mutable reviewer ledger, not in an
immutable artifact. Submit a row or artifact target, then propose the
selector-free exact batch:

```bash
plan-tool roadmap my-project --submit-feedback rename-order --feedback-target domain:row:workflow-review --feedback-request 'Clarify the review workflow order.'
plan-tool roadmap my-project --propose-candidate
```

The proposal snapshots eligible `open` ledger items and current roadmap-derived
context under one accepted root and direct source. Reviewers do not choose a
structural feedback type: validated typed operations classify the stored batch
as bounded or structural. It stores an inert candidate and does not rewrite the
accepted artifact. A bounded candidate follows its stored review requirement.

A new proposal takes the active candidate as its source, structural or not, so
a second batch stacks on top of a candidate nobody has approved yet. The
unpromoted candidates above the accepted root form the stack. A stack is
structural when any of them stores a structural route, even when the top one is
presentation-only, and the `--propose-candidate` output then prints the whole
stack. One exact decision on the top candidate covers every hop beneath it.

Stacking is also how a narrative correction reaches rows the same candidate
changed. A candidate cannot both change a row and correct a paragraph that names
it; the proposal drops that correction (refusal `owning-set-interaction`) and its
response for the item says so, naming the paragraph's span. When a response
reports a dropped correction, submit feedback for the stale narrative and
propose again:

```bash
plan-tool roadmap my-project --submit-feedback plans-narrative --feedback-target plans:artifact --feedback-request 'Correct only narrative prose that still contradicts the replaced plan rows. Change no typed rows.'
plan-tool roadmap my-project --propose-candidate
```

The new candidate stacks on the first and carries only the correction. Approve
the top candidate as below, and one decision covers both. An edit of the first
candidate cannot carry the correction, because it reproposes against the same
source; see `ROADMAP_FORMAT.md` § "Shared-narrative correction".

Approve takes two invocations:

```bash
# First: prints the stack and a digest, writes nothing, exits 2
plan-tool roadmap my-project --decide-candidate CANDIDATE_VERSION_ID --candidate-decision approve
# Second: the same command plus the digest exactly as printed
plan-tool roadmap my-project --decide-candidate CANDIDATE_VERSION_ID --candidate-decision approve --confirm-stack-digest DIGEST
```

1. The first invocation prints every unpromoted hop above the accepted root, the
   cumulative diff from the root to the top candidate, the top candidate's
   disclosure, and a `stack digest:` line. It changes nothing and exits with
   status `2` (`approve confirmation-required`), so a script never reads it as
   an approval. It is also the read-only view of a pending candidate.
2. Read the printed stack, then run the second invocation with the digest. The
   library recomputes the digest under the writer guard. A differing digest,
   such as a mistyped one or one copied from another candidate's stack, refuses
   with no write. The
   confirm is a flag value, not a terminal prompt, so headless runs use the same
   two invocations; `-y` is refused beside a candidate decision and is not
   confirmation.
3. A matching digest creates a `structural-approval` seal bound to the top
   candidate, then publishes it as a second, separately-durable write.
   `promote_review_seal` rechecks the accepted root,
   active candidate, stored candidate, seal, and gates before its journaled
   publication advances the accepted head to the top candidate, which carries
   every hop beneath it. Promotion re-derives the stack, and when any hop above
   the accepted root stores a structural route it requires the
   `structural-approval` seal and applies the seed-state effect;
   recovery of an interrupted promotion asks the same question.

A seal left by an interrupted confirm stays promotable while its candidate is
still the active one: re-run the confirmed approve with the same digest, or run
`--promote-review-seal`. A completed structural confirmation needs no second
promotion command; a later invocation with its seal exits successfully and
reports `already promoted` without writing. A later stacked batch makes an
interrupted seal stale; approve the new top candidate, which covers the sealed hop.

Edit and reject take no confirm, and each prints the stack first:

```bash
plan-tool roadmap my-project --decide-candidate CANDIDATE_VERSION_ID --candidate-decision edit --candidate-correction 'Clarify the replacement.'
plan-tool roadmap my-project --decide-candidate CANDIDATE_VERSION_ID --candidate-decision reject
```

Edit stores a replacement candidate that requires a fresh decision and prints
the replacement's stack; it is accepted when that stack carries a structural
hop, even if the replacement's own route is presentation-only. Reject promotes
nothing: rejection releases only the active candidate, drops every unpromoted
hop above the accepted root, and names the dropped hops in its output. Both
preserve immutable history, and the dropped hops stay stored.

The reviewed nonstructural route remains; it refuses a stack that carries a
structural hop and names `--decide-candidate`:

```bash
plan-tool roadmap my-project --review-candidate INITIAL_CANDIDATE_VERSION_ID
plan-tool roadmap my-project --answer-question QUESTION_ID --answer TEXT
plan-tool roadmap my-project --promote-review-seal REVIEW_SEAL_ID
```

`--promote-review-seal` promotes answered seals. It also completes an
interrupted structural confirmation; it reports an already completed structural
confirmation without rewriting lifecycle state.

Deliberately not built:

- **A separate show command.** An unconfirmed approve prints the same stack and
  writes nothing, so it is how a pending candidate is viewed (owner decision,
  2026-09-24). Re-running `--propose-candidate` is not a view: it builds a new
  candidate on top of the active one.
- **A confirm step for edit or reject.** Only approve seals and promotes a
  structural stack, which advances the accepted head and invalidates
  seed state. Edit stores an inert replacement and reject releases a pointer, so
  neither changes canonical content.
- **Stack output on the answered route and on standalone `--reject-candidate`
  and `--discard-candidate`.** None asks for or confirms a structural approval,
  because the answered route refuses a structural stack, and each keeps its own
  output. Only the structural decision's reject names the dropped hops.

Candidate, review, and promotion records use their stored batch rather than
later ledger state. An unrelated ledger edit preserves recorded evidence; a
changed processing pair or admitted item refuses candidate storage without
consuming the reviewer edit. Invalid output, failed validation or gates,
interruption, rejection, edit, and stale bindings do not advance the accepted
head or rewrite canonical artifacts or seeds. Only selected ledger items change
where their lifecycle records say so; unselected feedback remains unchanged.
After a promotion whose stack carries a structural hop, the
publication contract invalidates seed state but does not rewrite seed bodies.
The next proposal starts from the promoted accepted version, never a pending
candidate or the live ledger.
`ROADMAP_FEEDBACK_FORMAT.md` owns the ledger schema, editing rules,
and lifecycle vocabulary.

### Reopen a retained ledger item

Reopen one retained reviewer ledger item by id:

```bash
plan-tool roadmap my-project --reopen-ledger-feedback rename-order
```

This replaces the removed `--reopen-feedback` route. It changes only that
ledger item and invokes no backend. `ROADMAP_FEEDBACK_FORMAT.md` owns the
lifecycle states an item can reopen from.

Until a draft classifies `current`, using it (or its promoted copy) to create a
plan requires a `y/N` confirmation. Use `-y` only when an unattended caller
intentionally accepts a non-current input.

The `cfp-review` run shows bounded-route outcomes. A request to remove the
settled `conflict` entity was refused because a settled decision anchored it.
An artifact-level request that fit the active-feedback authority led to
`flow-declare-conflict` being removed and folded into `flow-assign`, with a
removal record citing the feedback row. Feedback proposes; the reviewer decides.

---

## 7. Promote accepted draft seeds, or create directly from them

Stage 4 publishes the plan mapping but materializes no drafts, so every plan
starts as `missing`. Materialize all recoverable drafts before promotion, or
select one existing `plans[].id` from the accepted `04-roadmap.md` to materialize
only that row's draft. Substitute that ID for `<roadmap-plan-id>` in these
examples; it is not a seed filename or a newly assigned plan name. The row and
its declared `draft_seed_path` exist before any seed file. Omitting the ID
processes all recoverable drafts. Materialization produces a draft;
it does not review or approve it. The seed carries the selected row’s supplied
responsibilities, sibling prerequisites, eventual proof obligations, and local
References. A sibling prerequisite provides context for this plan; it does not
authorize absorbing the sibling’s work.

```bash
plan-tool roadmap my-project --materialize
plan-tool roadmap my-project --materialize <roadmap-plan-id>
```

If a reviewer hand-edits a draft, it classifies `digest-mismatched` even when
the edit is otherwise well-formed. After reviewing that edit, preserve it with
`--accept-seed` rather than regenerating it; this records the live digest as
`current` without invoking the backend.

```bash
plan-tool roadmap my-project --accept-seed <roadmap-plan-id>
```

Every draft includes a tool-written `## Stack` section listing the accepted
hosting and store choices. `create --from-existing` preserves it in the plan, and
`detail` and the plan audit read it. Do not hand-edit it: a rematerialization
overwrites the edit, so change the roadmap through feedback instead. The
contract is in [`ROADMAP_FORMAT.md`](../../ROADMAP_FORMAT.md#stack-section).

Once a draft is current and its content is accepted, promotion is optional. It
is an apply-only copy operation: it does not rerun stages or invoke the backend.
Materialization, digest acceptance, promotion, and ordinary create do not approve
a roadmap candidate or advance the accepted head. Changes to accepted scope use
the [feedback and review procedure](#6-turn-reviewer-ledger-feedback-into-a-candidate).

Inspect the promotion and confirm interactively to copy the accepted drafts into `docs/implementation-plans/plan-seeds/`.

```bash
plan-tool roadmap my-project --apply
```

For an unattended, deliberate promotion, use the second opt-in.

```bash
plan-tool roadmap my-project --apply -y
```

You can instead keep a materialized, current draft under the roadmap directory
and create a plan from it directly. The ordered handoff uses this form only for
plan rows whose drafts classify `current`.

```bash
plan-tool create <roadmap-plan-id> --from-existing <reported-draft-path>
```

After promotion, use the corresponding copied seed.

```bash
plan-tool create <roadmap-plan-id> --from-existing <reported-promoted-path>
```

Choose one source for a plan: the slug-relative draft or its promoted copy.
Both deliver the seed’s supplied obligations and local References to ordinary
create authoring and the published plan. This is context delivery for judgment,
not a guarantee of semantic completeness or model understanding. See
[Create from existing material](pipeline/create-from-existing.md) for source
selection and retention.

The ordered plan rows and their seed fences carry inter-plan assumptions;
preserve those fences, and the `## Stack` section beside them, when you amend a
seed. If `create` reports a `SplitProposal`, its recommendation to use `roadmap`
is advice only — it does not run this workflow for you.

### Direct fallback

Use the direct fallback when you deliberately author a seed outside the normal
per-row handoff. Slice the domain into coherent behavior bundles: business rules,
the workflows that exercise them, and the entities they govern. This is seed
authorship, not materialization repartitioning an accepted row.

Write a seed following [`SEED_FORMAT.md`](../../SEED_FORMAT.md) that cites the
four artifacts resolved through the accepted head, binds its rules and entity
IDs, fences settled decisions (including rejected alternatives and reasons), and
names the constraints it discharges. Then use ordinary `create --from-existing`.
Do not edit immutable roadmap artifacts directly; use the feedback and review
procedure above when the accepted scope needs to change.

---

## 8. Continue as an ordinary plan

After `create`, continue with an ordinary bounded plan grounded against current
code. Keep the accepted responsibilities, prerequisite boundaries, and eventual
proof obligations while authoring implementation detail. Audit the completed
plan, then execute it in its declared order.

```bash
plan-tool detail <roadmap-plan-id>
```

```bash
plan-tool completeness-audit <roadmap-plan-id>
```

```bash
plan-tool run <roadmap-plan-id> --commit
```

The roadmap's decision fence should travel into the seed, but `create` should still ground the plan against the current repository. In the measurement behind this walkthrough, a brief-only plan found more current PostgreSQL RLS caveats than the frozen roadmap rationale. Carry forward the settled decision; let later commands re-ground the supporting reasons.

## What the roadmap is for

The useful outcome is four gated artifacts, a materializable draft destination
for every plan row, and a review loop — not a substitute for authorship. Once a
draft is materialized and current, its ordered `create` handoff is available.
The real `cfp-review` comparison found the same architecture whether plans began
from a roadmap seed or directly from the brief. The roadmap's value was making
the decision, rejected alternatives, and don't-re-open boundary explicit and
traceable. See [`ROADMAP_LAYERING_MEASUREMENT.md`](../evidence/roadmap-layering-measurement.md)
for the full design and results.
