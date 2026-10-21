# Roadmap feedback revision keeps failing on real artifacts because it regenerates the whole file — the 2026-08-19 analysis

Real-world first use of the `roadmap` verb, on the `integration` repository, failed
repeatedly on feedback iterations. This record traces the failure to its
architecture, shows the codebase already has the fix pattern in two other
places, and states what should happen to the roadmap arc's in-flight
hardening plans as a result.

## In plain English

Here's what actually happened, in plain terms.

The `roadmap` tool asks a model to write a big YAML file — domain facts,
constraints, components, whatever. When a reviewer leaves feedback on that
file and asks for a revision, the tool's current approach is: hand the model
the entire file back, plus the entire prompt that wrote it in the first
place, plus a page of "here's what's different this time" instructions, and
ask it to retype the *whole thing* — changing only the parts the feedback
asked about, and reproducing every other line exactly.

That works fine on a small demo file. It stopped working on `integration`, where
the real artifact was 35 KB — 783 lines of structured YAML frontmatter.
Asking a model to retype nearly 800 lines byte-for-byte and change only a
few of them is a
hard task, and it has a failure rate that gets worse as the file gets
bigger. On `integration` it failed three different ways in one evening: one attempt
just died mid-call, one came back with output that didn't parse as valid
YAML, and one came back parseable but had quietly rewritten a line of text
it wasn't supposed to touch — which the tool correctly caught and rejected,
but only after a 15+ minute round trip, and the retry asks the model to do
the exact same hard thing again. On top of that, a *human* reviewer typing
feedback directly into the file once broke its YAML: one possessive
apostrophe in a hand-written sentence ("the roadmap's model-authored
content") sat inside a quoting style that treats a bare apostrophe as a
syntax error. The tool's own error message told the operator to delete the
file and start over; in practice the operator instead hand-fixed the
quoting in under a minute and moved on. That the file can be broken by
typing a normal English possessive into it is itself worth noticing,
independent of the model-regeneration problem above.

The good news: this codebase already solved this problem twice, in two
*other* corners of the same roadmap feature. Instead of "retype the whole
file," those two paths ask the model for a tiny, closed answer — "here's
the one field to change, here's the new value" — as JSON, and then plain
Python code (not the model) makes that one change to the file. The model
never touches anything it wasn't asked about, so there's nothing for it to
accidentally corrupt, and the prompt is a few hundred bytes instead of tens
of thousands. That pattern just was never extended to cover the main case —
the case that broke on `integration`.

Separately, a lot of the roadmap feature's recent work has been building
safety nets underneath the "retype the whole file" approach: making sure a
corrupted or drifted file gets caught, making sure removed content isn't
silently lost, sealing evidence so a bad rewrite can't erase history. Those
efforts are reasonable reactions to a design that regenerates a whole
document from scratch — but if the regeneration goes away, most of what
those safety nets exist to catch goes away with it. Building more of that
safety net right now is arguably solving the same problem twice: once by
preventing whole-file rewrites from happening, and again by cleaning up
after them when they do.

The recommendation: extend the existing small, closed, code-applied pattern
to cover ordinary feedback revision, instead of continuing to harden the
big-rewrite path. That fixes the actual failure, and it likely makes several
of the in-flight hardening plans unnecessary or much smaller.

## How to read this record

This is one operator's first real use of the verb, on one repository,
producing three failed runs in one session. It is **n=1**. It does not
establish a failure rate, prove every stage-1 revision on every brief fails
this way, or rule out an unrelated environmental cause for the `invoke`
failure specifically (the `parse` and `gates` failures are unambiguous —
their causes are visible in the run log and the rejected diff). Treat this
as a traced root cause with supporting evidence, not a statistically
validated defect rate. The architecture argument below does not depend on
the failure rate being high; it depends on required output fidelity growing
with artifact size while a model's verbatim-reproduction fidelity does not,
which is a property of the design, not of this one run.

## What happened

Source: `<integration-consumer-root>/.plan-tool/runs/integration/`,
2026-08-12. The canonical artifacts under
`docs/implementation-plans/roadmaps/integration/` total 83 KB across four stages
(`01-domain.md` 35.8 KB, `02-constraints.md` 10.8 KB, `03-components.md`
10.3 KB, `04-roadmap.md` 26.0 KB) — a real brief, not the small technology
demo the capability was first shown on.

For context: an earlier same-day run (`18:17:39`) revised stage 1 (resolving
3 open feedback rows) and continued cleanly through all four stages,
`stdout_bytes` growing from 35 KB to 74 KB and `prompt_bytes` from 54 KB to
110 KB by stage 4 — that run completed (`rc: 0`), though stage 4 itself
needed one `gates`-triggered retry before it passed. So whole-artifact
regeneration does not fail *every* time at this scale; it failed the three
times recorded below, later the same evening, on a stage-1 artifact that had
since grown further from added feedback:

| Run | What happened |
|---|---|
| `2026-08-12T20-35-11` | Failed in 28 ms, before any model call. The on-disk artifact had invalid YAML: a hand-written `feedback` row's `request` field was a single-quoted scalar containing the reviewer's own prose, and one bare apostrophe in "the roadmap's model-authored content" (line 701) broke the quoting — the same sentence correctly escaped an earlier possessive, `plan-tool''s`, and missed this one. The tool's own error message suggested deleting the file for a fresh authoring pass; the operator instead hand-repaired the field (commit `2bc458d`, 22 seconds later, converting it to a block scalar) and re-ran. |
| `2026-08-12T20-35-42` | Attempt 1 (`prompt_bytes: 69824`) failed `failure_kind: invoke` after a call lasting `duration_ms: 720021` — within 21 ms of exactly 12 minutes, consistent with hitting a fixed invoker timeout on a long verbatim-reproduction generation rather than an unrelated hang. Attempt 2 launched with no further per-attempt event logged; the run errored after 23.5 minutes wall clock. |
| `2026-08-12T20-59-35` | Attempt 1 (`prompt_bytes: 69824`) failed `failure_kind: parse` — the re-emitted file didn't parse. Attempt 2 (`prompt_bytes: 70061`) failed `failure_kind: gates`: the model rewrote the `proposed_response` of a feedback row that was in `awaiting-review` state — a row the prompt explicitly told it to reproduce untouched. Attempt 3 launched with no further per-attempt event logged; the run errored after 17.4 minutes. |

Every stage-1 revision prompt was ~70 KB: the revision template, the full
predecessor artifact, the active feedback, and the entire stage-1 authoring
contract nested inside it. That is well within the model's context window —
reading 70 KB is not the bottleneck. Reproducing 35 KB of it verbatim, on
every attempt, is.

## Why it happened

`plan_tool/roadmap.py`'s stage-level revision path
(`_render_revision_prompt`, template `roadmap-revision.md`) builds a prompt
as: the revision template (~12 KB) plus **the full predecessor artifact**
plus the active feedback plus **the entire authoring prompt that first wrote
the artifact** — which itself embeds the brief and every upstream artifact
verbatim via `{artifact_key}_artifact` substitution. A stage-4 revision on a
real brief would embed the domain, constraints, and components artifacts
*and* the roadmap artifact *and* two layered contracts in one prompt.

The revision template then asks the model to hold two documents at once — the
original authoring contract, and a "Five things the authoring contract says
that are wrong here" correction sheet that overrides it — and to **"re-emit
the whole file… the parts the feedback asks you to change, and every part it
does not."** `roadmap_gates.py`'s ~2,600 lines of deterministic checks (id
continuity, settled decisions, feedback integrity, design-row continuity)
then reject any drift in the untouched 99% of the file, and a rejection
means retrying the same large prompt from scratch.

This has a structural cost that scales with size, not a hard pass/fail line
at one artifact size — the earlier same-day run above shows a large
whole-artifact revision *can* succeed. But **required output fidelity grows
with artifact size while a model's verbatim-reproduction fidelity does not**,
so the probability of a costly failure rises with it, and every failure kind
recorded above is a plausible symptom of exactly that: `invoke` (a call that
ran to what looks like a fixed ~12-minute timeout generating a long verbatim
reproduction), `parse` (malformed output on a long structured re-emission),
`gates` (drift in content the model wasn't supposed to touch). Each failed
attempt also costs 5–24 minutes before the same oversized prompt is retried
unchanged — so even a design that merely fails *sometimes* at this scale is
expensive per occurrence, which is reason enough to remove the exposure
rather than tolerate its rate.

## The codebase already has the fix, in two other places

Two other roadmap revision surfaces do not regenerate anything. They ask for
a small, closed set of operations and apply them with plain code:

| | Stage-level feedback revision (what failed) | Local feedback revision (`--revise-feedback`) | Structural revision |
|---|---|---|---|
| Prompt size | ~70–190 KB, scales with artifact + upstream artifacts | ~1 KB, fixed | ~1–2 KB, fixed |
| What the model returns | The entire re-emitted artifact | A closed JSON object: one optional field replacement + one response | A closed JSON envelope: `row-field` / `prose-region` operations, at most one prose region |
| What applies the change | The model's own re-emission, checked after the fact by ~2,600 lines of gates | `roadmap_revision_patch.merge_feedback_revision` — pure typed code | The structural patch/proof machinery — targeted, byte-strict |
| Can drift an untouched row | Yes — this is what `gates` failures catch, after the fact | No — the model never sees or returns rows it wasn't asked about | No — same reason |
| Failure mode on a large artifact | Grows with artifact size (this record) | Independent of artifact size | Independent of artifact size |

The local feedback-revision prompt (`roadmap-feedback-revision.md`) and the
structural-revision prompt (`roadmap-structural-feedback-revision.md`) both
already prove the pattern works in this codebase: bound the model's job to a
small typed decision, and let deterministic code own the merge. Stage-level
feedback revision — the path a reviewer actually hits first, and the one
that failed on `integration` — is the one place that still asks the model to
reproduce a whole document.

## Scale relative to delivered value

Independent of the failure above, the roadmap arc's *size* is disproportionate
to what it has been shown to deliver, and the two facts share a cause.

- Roadmap is 26 modules, ~17.8k source lines (about 19% of `plan_tool`), and
  ~30.7k test lines. `ROADMAP_FORMAT.md` is 2,195 lines — larger than
  `PLAN_FORMAT.md` + `DETAIL_FORMAT.md` + `SEED_FORMAT.md` combined (1,040
  lines), i.e. the roadmap's own intermediate-artifact contract outweighs the
  contract for everything the tool ships to a user.
- The verb's entire real-usage record before this session
  (`docs/evidence/roadmap-run-measurements.md`) is two briefs, every block n=1 or
  n=2, and that document says plainly its records gate nothing. The one
  controlled comparison (`docs/evidence/roadmap-layering-measurement.md`) found all
  three arms reached the same architecture — the layering's demonstrated
  value is a decision record (provenance, rejected alternatives), not better
  designs.
- Roughly 40% of the roadmap code is not the four-stage pipeline; it is the
  revision/feedback/evidence superstructure around it
  (`roadmap_revision*`, `roadmap_structural_revision*`,
  `roadmap_escalation*`, `roadmap_impact*`, the evidence store). Every
  roadmap plans hardened that superstructure —
  `roadmap-hosting-and-stores`, `roadmap-immutable-evidence-storage`,
  `roadmap-revision-retention`, `roadmap-structural-review-remediation`, and
  `roadmap-canonical-source-identity` — while position 05 (framework lenses),
  the arc's next user-facing value, remains unauthored.

This matches `CLAUDE.md`'s `check-saturation` shape: every one of those
hardening steps is individually correct, and none of them was the thing
standing between the verb and a successful real-world run. What was standing
in the way was the regeneration design itself, which the hardening plans
largely defend the *consequences* of rather than remove.

## Recommendation

Generalize the bounded-operations pattern to stage-level feedback revision,
and retire whole-artifact re-emission for revision:

1. Widen the operation vocabulary beyond `roadmap_revision_patch`'s current
   presentation-field replacement — row add/edit/remove, feedback lifecycle
   transitions (`open` → `awaiting-review` → `closed`), removal-with-content
   — enough to cover what stage-level revision needs today.
2. Route stage-level feedback revision through that vocabulary and a
   deterministic merge, the same shape `merge_feedback_revision` and the
   structural-revision patch machinery already use. The model proposes
   operations as closed JSON; code applies them.
3. Stop embedding the full authoring prompt inside the revision prompt. The
   "five things the authoring contract says that are wrong here" pattern is
   a symptom of asking the model to reconcile two documents; a self-contained
   revision contract removes the need.
4. This does not require discarding stage-level revision's three existing
   gates — `check_design_row_continuity`, `check_feedback_integrity`,
   `check_settled_decisions` — which all remain meaningful checks on the
   *result* of a bounded merge. What it removes is the failure surface where
   the model accidentally drifts content nobody asked it to touch, because
   that content never passes through the model at all.

## Disposition of existing plans and seeds

**Plans:**

- **`roadmap-canonical-source-identity`** (`status: planning`, actively
  mid bare-plan audit as of today) — **pause now.** Do not continue its
  audit loop or move it to `detail`. A material share of its threat model
  (a roadmap consumer accepting source text that differs from its
  persisted canonical baseline) is motivated by the whole-artifact
  regeneration path's drift risk; once revision stops regenerating
  untouched content, that share of the surface shrinks. Its remaining
  concern — human hand-edits to a canonical file between runs, and
  escalation-receipt freshness — is real and independent of this decision,
  so this is a **re-scope**, not necessarily a full withdrawal: re-derive
  its plan body against the smaller remaining surface once the
  bounded-operations work (above) exists, rather than resuming it as
  currently authored.
- **`roadmap-revision-retention`** (#242, already paused after bare-audit
  round 4 by prior user direction) — **stay paused.** Its three retention
  additions (removed-row content snapshot, retained `closed` feedback,
  removal→decision reference) target the canonical artifact regardless of
  how revision is authored, so this plan is not obsoleted — but it is
  currently designed against the discipline of "the model re-emits the
  whole file, gates catch drift after the fact." Implementing the same
  three additions as explicit, code-owned merge operations (once the
  bounded-operations layer exists) is very likely simpler and more
  correct than layering them onto whole-file regeneration. Redesign
  against the merge layer before resuming, rather than resuming as
  authored.
- **`roadmap-immutable-evidence-storage`** — **completed 2026-08-15 and
  archived.** Its small sealed-storage primitive serves escalation receipts
  and structural-revision proofs independently of the revision architecture.
- **`roadmap-hosting-and-stores`** (#243) and
  **`roadmap-structural-review-remediation`** — both `status: completed`,
  unaffected. Structural revision was already bounded/patch-based (see the
  comparison table above), so this arc's finding does not implicate it.
- **`roadmap-render-canonical-tolerance`** — already withdrawn 2026-08-19
  ("parser-round-trip tolerance cannot detect semantic source drift;
  roadmap canonical source identity owns the replacement contract"),
  archived at
  `docs/implementation-plans/archive/2-roadmap-render-canonical-tolerance.withdrawn.md`.
  No action; stays as the historical record. `BUG_BACKLOG.md`'s RISK entry
  citing it needs one correction: it still says "create its replacement
  from `plan-seeds/roadmap-canonical-source-identity.md`," but that
  replacement plan already exists and is now paused per this record — see
  the update made alongside this analysis.
- **`roadmap-05-framework-lenses`** (#208) — unaffected directly, but its
  case to wait strengthens: the higher-leverage next spend is making
  ordinary feedback revision work on real-sized artifacts, since that is
  what blocked real usage before framework lenses would matter at all.

**Seeds:** every roadmap seed on disk has already been consumed and moved to
`plan-seeds/archive/*.replaced.md` by the normal `create` lifecycle,
including `roadmap-canonical-source-identity.replaced.md`,
`roadmap-revision-retention.replaced.md`, and
`roadmap-feedback-revision-bounded-operations.replaced.md`. The latter was
used to create #297's bare plan; no live roadmap seed remains to act on.

## Next steps, in order

The two sections above say *what* to build and *what each existing plan's
disposition is*, but not the sequence for getting from today's state to a
shipped fix. This is that sequence. All three affected plans remain
`status: planning` with no `progress:` recorded — none has reached `detail`,
so nothing below has to unwind in-flight step work.

1. **Done (2026-08-19):** author the #297 seed and run `create
   --from-existing`. The resulting bare plan is
   `docs/implementation-plans/archive/2-roadmap-feedback-revision-bounded-operations.md`;
   its consumed seed is archived as
   `plan-seeds/archive/roadmap-feedback-revision-bounded-operations.replaced.md`.
2. **Done (2026-08-19):** five bare-plan `completeness-audit --iterate`
   snapshots produced material correctness counts `3 → 2 → 3 → 1 → 3`. The
   fifth saved report's three HIGH findings were resolved by explicit user
   decision rather than a sixth automated round: a feedback-free re-gate
   success is its own terminal outcome; a non-feedback hand edit to the
   predecessor is detected and reconciled before any stage-envelope
   operation, with feedback rows excluded from the check (a reviewer
   hand-writing a feedback request is the artifact's normal input path); and
   the anchor/consumer no-retarget protection applies to pending decisions,
   not only settled ones. A related, deliberately deferred idea — using the
   artifact's row relations to narrow hand-edit detection further — was
   filed as **#298**, gated on #297 shipping and real usage evidence rather
   than built now.
3. **In progress (2026-08-19):** a fresh bare-plan audit (round 6) is
   confirming the applied decisions converge, rather than treating the
   resolved sequence as converged on its own.
4. **`detail`**, then **detail-grounded `completeness-audit --iterate`** to
   convergence.
5. **`run --commit`** the plan: widen `RevisionOperations`/
   `merge_feedback_revision`, wire the new bounded stage-revision prompt,
   retire `_render_revision_prompt`'s whole-artifact path.
6. **Post-run tail**: `reconcile-code --all` sweep, then a `/code-review`
   loop to convergence, per the standing post-run mandate.
7. **Verify against the actual failure, not only new unit tests.** Replay a
   stage-1 feedback revision against a `integration`-scale artifact (tens of KB) and
   confirm it completes without an `invoke`/`parse`/`gates` failure, and that
   an `awaiting-review` row's response survives untouched. This step is the
   one this whole record exists to justify — do not call #297 done on a green
   suite alone; the production failure is the acceptance test.
8. **Only after #297 ships and step 7 confirms it**, re-scope
   `roadmap-canonical-source-identity`: re-derive its plan body against the
   smaller remaining surface (cross-run hand-edits, receipt freshness) and
   run a fresh bare-plan audit round — do not resume its paused round as if
   nothing changed, since the scope itself is different now.
9. **Only after step 8**, resume `roadmap-revision-retention` (#242):
   redesign its three retention additions as explicit merge-time operations
   against #297's now-existing merge layer, then re-enter its bare-plan audit
   loop. Its round-4 finding count (12 → 7 → 6 → 5) does not carry forward
   as-is — the redesign changes what the plan says, so treat the next round
   as round 1 of the redesigned body, not a continuation of round 4.
10. **`roadmap-immutable-evidence-storage` is complete.** Do not reopen its
    reduced primitive through this revision route; a hardened storage boundary
    requires its own threat-model decision.
11. **Bookkeeping as each stage lands:** flip `backlog-arc-roadmap.md`'s step
    0 to done, update or remove `BACKLOG.md` **#297** per its own final step,
    and update #242's status bullet and `roadmap-canonical-source-identity`'s
    disposition once steps 8–9 actually happen — this record and the arc doc
    describe today's state and will drift the same way any other plan
    documentation does if left unedited after the fact.

## Cross-references

- `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — ordered
  route, updated alongside this analysis.
- `docs/implementation-plans/backlog-arcs/archive/backlog-arc-structural-rewrite-safety.md`
  — historical record with a follow-up section, updated alongside this
  analysis.
- `BACKLOG.md` **#297** — the forward-looking entry for the bounded-operations
  generalization.
- `BUG_BACKLOG.md` — the render-canonical-mismatch RISK entry, corrected
  alongside this analysis; two new BUG entries record the `integration` failure
  itself — the whole-artifact-regeneration failures, and the separate,
  independent YAML-corruption gap #297 does not fix.
- `docs/evidence/roadmap-layering-measurement.md`, `docs/evidence/roadmap-run-measurements.md`
  — the prior evidence base this record's proportionality argument draws on.
- `plan_tool/roadmap.py` (`_render_revision_prompt`, `_render_stage_prompt`),
  `plan_tool/roadmap_revision_patch.py` (`merge_feedback_revision`),
  `plan_tool/prompts/roadmap-revision.md`,
  `plan_tool/prompts/roadmap-feedback-revision.md`,
  `plan_tool/prompts/roadmap-structural-feedback-revision.md` — the code and
  prompts this record traces.
