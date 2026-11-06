# Historical backlog decisions

This is the durable home for closed backlog decisions and retired composite
records. `BACKLOG.md` is a forward-looking work queue; completed delivery
history belongs in archived implementation plans and git history, while these
short records preserve decisions that would otherwise invite re-investigation.

## Queue cleanup, 2026-09-16

The following delivered IDs remain citable after queue cleanup. Their plans
or the named contract carry implementation detail. #315, #327, #328, and
#351 and the brief-drift closeouts also retain compact backlog completion
records required by their plans.

On 2026-09-16, three roadmap compatibility entries that shared IDs with
authored-artifact version work were renumbered: former roadmap #362 → #383
(per-stage supplements), #363 → #384 (carried settled decisions), and #364 →
#385 (JSON status). The authored-artifact version entries retain #362–#364.

| ID | Delivery record or current contract |
| --- | --- |
| #164 | The side-by-side Jira-grade detail route shipped 2026-07-30, stopped new authoring 2026-08-24, and is selected for full retirement by live #308. |
| #181, #182 | [Risk-profile declaration](../implementation-plans/archive/2-risk-profile-1.md) and [advisory detail context](../implementation-plans/archive/2-risk-profile-2.md). #314 remains the separate evidence-gated follow-up. |
| #247 | The read-only saved-audit ledger in `plan_tool/review_persistence.py` and `plan_tool/completeness_report.py`; #303 remains the separate comparison proposal. |
| #293 | [Jira developer handoff plan](../implementation-plans/archive/2-jira-developer-handoff-companion.md); the current paired export contract is `JIRA_FORMAT.md`. |
| #295 | [Recommendation confidence plan](../implementation-plans/archive/2-recommendation-confidence.md); #316 and #382 remain independent follow-ups. |
| #305 | `plan_tool.response_contract.coerce_response_id`, the shared cycle-free grammar for `gates`, `foundational_logic`, `create`'s dependency/note-key parsers, `intent_proposal`, and `concept_sync`; each caller keeps its own `None` disposition. |
| #309 | The `retire-roadmap-v1-evidence` post-run review fixes, recorded in commits `55a989df`, `9a676e7d`, `74a4e23e` and the subsequent review commits cited by Git history. #311 owns the remaining independent efficiency work. |
| #315 | [Confirmed feedback reopen proof](../implementation-plans/archive/2-roadmap-confirmed-feedback-reopen.md); #242 remains a separate retention redesign. |
| #327 | [Seed-ingestion routing plan](../implementation-plans/archive/2-seed-ingestion-routing.md) and the [seed-ingestion contract](../reference/contracts/seed-ingestion.md). #102 and #353 remain separate. |
| #328 | [Immutable candidate versions plan](../implementation-plans/archive/2-roadmap-immutable-candidate-versions.md). #329 and #330 remain separate persistence-integrity work. |
| #334 | [Mechanism-reach authoring plan](../implementation-plans/archive/2-mechanism-reach-01-authoring.md); #335 and #336 consume its shipped rule. |
| #337 | [Roadmap stage lifecycle output plan](../implementation-plans/archive/2-roadmap-stage-lifecycle-output.md). |
| #351 | [Seed References fallback plan](../implementation-plans/archive/2-seed-source-references-fallback.md). |

### #331 and #333 — Seed-to-create source boundary

Decided 2026-09-02. `## References` is the required file-backed source
fallback before model cost. Other canonical headings select direct ingestion;
their absence routes free-form source through visible preparation rather than
a universal H2 refusal. Generated annotate and scope-out carryover seeds can
have noncanonical headings. The [seed-ingestion contract](../reference/contracts/seed-ingestion.md)
owns the current route; #327 delivered it. Do not reopen a universal heading
preflight without a new source-evidence failure.

### #205 — Jira-grade renumber migration withdrawn

Withdrawn 2026-09-02. The user selected full Jira-grade artifact and reader
retirement in #308. A renumber migration for that lane has no live consumer;
do not revive it as a compatibility path.

### #293 — The former opt-in Jira handoff is superseded

Superseded 2026-08-23. The delivered opt-in `--developer-handoff` companion
became a mandatory paired Jira export. `JIRA_FORMAT.md` owns the current
contract: the plan fixes coverage and order; explanatory implementation prose
is a suggestion and cannot amend the plan.

### #328 — Accepted-head versions and reader migration

Closed 2026-09-01. Enrollment captures one immutable root; candidate,
question, replacement, and review-seal records stay inert until exact
promotion changes the accepted head. `plan_tool/roadmap_view.py:load_roadmap`
is the completed direct-reader proof. Other reader migrations require their
own selected scope; #329 and #330 retain independent hardening findings.

### #367 and non-stage routes — Brief rebind authority

Decided 2026-09-15 and delivered 2026-09-16. A changed or legacy recorded
brief requires stage-run-only `--confirm-brief-rebind` with the recorded
`--from-existing` path. Repeating the path alone is insufficient consent.
Non-stage analysis, structural rewrite, and version-enrollment routes refuse
changed or legacy brief baselines redacted without publishing an artifact,
baseline, or seed. [Brief rebind confirmation](../implementation-plans/archive/2-roadmap-brief-rebind-confirmation.md)
and [non-stage brief drift](../implementation-plans/archive/2-roadmap-non-stage-brief-drift.md)
record the separate delivered boundaries. A matching recorded baseline keeps
its existing route behavior; this decision grants no broader rebind authority.

## Resolved and retired bug-backlog records

Records marked **Resolved** include a shipped behavior change and regression
coverage. Records marked **Retired** are not behavior fixes; their retained
re-open condition identifies the evidence or scope change that will justify a
new entry.

### Roadmap evidence-storage hardening

Retired 2026-09-01. No current roadmap consumer requires the configured tree
to defend against a same-owner process that can rewrite it. The reduced storage
contract excludes capability gates, ownership proofs, and unsafe-entry results,
so a local hardening change is not proportionate. A hardened boundary will need
descriptor-relative non-link traversal, regular-final attestation, and an
explicit unsafe-entry result. Reopen when a roadmap consumer must reject
same-owner or otherwise untrusted symlink/non-regular-entry replacement and
can own that result contract.

### Concept enrichment of flat decision records

Resolved 2026-09-01. `emit_concept_tree` now declines a flat decision record
without invoking the model because a generic emitted node has neither its
required bucket nor a final decision. Its full-tree branch also fails closed
when rederivation reports a conflict. Reopen only with a production,
on-demand, per-bucket drill (#130): it must not restore eager whole-plan
decomposition, must carry existing flat decisions into its bucket-specific
candidate through `carry_forward_decisions` or an equivalent operation, and
must surface any rederivation conflict its new input path can produce.

### Cursor monthly-plan-quota banner wording

Retired 2026-09-01. The confirmed matcher remains intentionally narrow, while
the terminal near-miss path preserves a redacted observed banner for a future
targeted update. Reopen only when telemetry supplies a representative Cursor
banner; update both matcher copies with positive and nearby-fragment negative
fixtures instead of admitting hypothetical wording.

### Retry-wait second-interrupt guard

Retired 2026-09-24. Wrapping `log.run_interrupted(...)` in
`make_backend_recovery_sleep_seam` (`plan_tool/claude_errors.py`) with
`contextlib.suppress(KeyboardInterrupt)` would not change what is recorded.
`RunLogWriter.run_interrupted` emits the event and then sets the termination
reason, and a second Ctrl+C that lands inside it skips both with or without the
guard. Only which `KeyboardInterrupt` propagates would change, and no caller
tells them apart. The roadmap fix in `d1cb57bf` differed: code after its guard
set the outcome. Reopen only if a run log must keep the "interrupted" event and
reason through a second Ctrl+C. That needs the reason set before the event is
emitted (`plan_tool/run_log.py`), not a guard at the call site.

## Retired composite records

### #92 — Plan lineage with model-authored summaries

Retired 2026-08-19. #198's structured Git provenance and rebuildable
archive ledger answer the concrete questions this item was meant to
support: what landed and why a plan was archived. A second semantic
history and its summarizer are not proportionate to the residual
split/merge narrative. Reopen only when a specific debugging decision
cannot be answered from #198's structured provenance and Git history.

### #169 / #170 / #171 — Jira-grade arc: consumer-probe, blocker-recurrence materiality, canonical inversion

Withdrawn 2026-08-21. The probe, quality-ledger, materiality, and
canonical-inversion route (jira-grade arc stages 02/04/05) asked a thinner
Jira-grade artifact to carry implementation-planning confidence before a
grounded implementation route existed. #293 (delivered) now projects the
selected implementation-grade bundle into concise stories and a
developer-handoff companion; the plan retains authority for non-negotiable
outcomes. Stage 01 (#164, jira-grade contract/selection/consumers) shipped
and remains; the former stage-02 proposal is retained at
`plan-seeds/archive/jira-grade-02-consumer-probe.withdrawn.md`. No seed was
authored for stages 04/05.

### #188 — Narrative audit as a product feature

Retired 2026-08-19. Do not add a narrative-audit command, prompt, sidecar
kind, finding source, or deterministic gates around a model retelling of a
plan or arc. One transient exercise produced useful discussion but omitted
a load-bearing stage; the user, not the lens, caught the omission, and the
proposed gates could prove only that a retelling names elements, not that
it establishes global coherence — not proportionate to the evidence. An
operator may still use narrative review as an optional human technique
when it helps; it produces no product verdict or workflow requirement (see
`docs/implementation-plans/backlog-arcs/backlog-arc-operator-workflow.md`).

### #196 — Infer lesson influence and evict inert lessons

Retired 2026-08-19. Do not build an influence resolver, value verdict, or
eviction policy from authoring outcomes. A record can show that a lesson
reached a prompt, but cannot show that it changed the result or that the
result would be unchanged without it. #193's citation store already
records the injection-count residual, so no distinct bounded feature
remains after the unsupported influence claim is cut. #193, #194, #195,
and #197 retain their independent provenance, reconciliation, retrieval,
and contradiction contracts.

### #222 — Published-data-interface (ODCS) roadmap lens

Retired 2026-08-27 (requirement decided no 2026-08-02; opt-in lens
question closed 2026-08-27). `roadmap` will not require every project to
author an ODCS-shaped external data-interface artifact — most `roadmap`
subjects aren't published data products, and a gate over sections a
project can't fill honestly just manufactures ceremony. The opt-in lens
form was left open pending #208's unbuilt framework-lens machinery; closed
without building it because that layering's own premise is unvalidated (a
real test found it changed the record, not the architecture) and no real
data-product project has asked for this. Revisit only if framework lenses
get built for their own independently justified reason, *and* a real
data-product project wants a data-interface artifact. Distinct from #320,
which asks a different, internal question — whether concepts *within* one
plan or roadmap declare matching input/output shapes to each other; #320
does not reopen this one.

### #231 — Infer a bad fix from a later audit finding

Retired 2026-08-19. Do not implement durable apply-to-finding provenance,
same-issue matching, or a product `requires-scope-review` route. The
proposed evidence model can stabilize an interpretation of saved model
output but cannot establish that an earlier edit caused a later model
finding; its persistence, ordering, and identity machinery is
disproportionate to that uncertainty. The bounded stage-revision plan's
five bare-plan reports (`3 → 2 → 3 → 1 → 3`) exposed a pause decision, not
a causal feature gap. **The one operational rule this investigation
surfaced is retained, but lives in `CLAUDE.md` now, not here**: when audit
findings begin examining the session's own latest edits, stop the
hand-apply loop and surface an explicit scope decision rather than
self-adjudicating (`CLAUDE.md`'s `self-seeded-finding` audit shape and its
`git log -S` provenance-tracing rule). Do not revive this request without
a new, independently measured operator need and a claim the available
evidence can actually support.

### #147 — Parallelize the per-step purity scan

Retired 2026-08-27, never built. Marked discouraged/last-resort from filing
(2026-07-18) under CLAUDE.md's anti-parallelism directive: pure wall-clock
gain, no correctness change, another `ThreadPoolExecutor` fan-out on an
already-dense app. The cheaper cut-work lever (the per-step purity cache,
shipped) already removed this entry's original motivation — an audit
routinely exceeding its background/exec window — and no evidence emerged
that the cache was insufficient. Revisit only with the explicit user
sign-off the directive requires, naming the complexity cost and a measured
win the cache genuinely can't reach.

### #289 — Candidate-aware structural roadmap operations

Retired 2026-08-27, never built. A generic create/remove/reorder/
relation-change roadmap writer was deferred pending a real widening request
since the 2026-08-17 bare-plan audit that named it; no such request
materialized. Do not build a generic structural writer speculatively —
revisit only when a real request identifies the operation class and its
affected artifacts, per the entry's own original Stop/defer condition.

### #298 — Bridge non-feedback roadmap hand edits into proposed feedback

Retired 2026-08-27, never built. Proposed a review workflow that would
interpret a reviewer's direct (non-feedback) hand edit to a roadmap artifact
and turn it into a proper feedback request, but stayed blocked on real
hand-edit evidence from the day it was filed (2026-08-19) — no concrete
case ever supplied the review-surface shape. `2-roadmap-canonical-source-
identity.md` and `backlog-arc-roadmap.md` both cited this as
deferred/pending; both now point to this record instead. Revisit only if a
real case surfaces where a hand-edit's intent is silently lost and that
turns out to matter.

### #178 — Run phase attribution

Retired 2026-08-18 after current-source verification; no new implementation
is required. `launcher.run_step()` records step execution as `claude_call`,
while `launcher.apply_finding()` records its calls as
`apply_finding_dispatch`. `runs diff` and `runs profile` aggregate phase names
dynamically, so historical `claude_call` rows remain readable beside the
separate current rows. Existing launcher and CLI tests pin both attribution and
arbitrary-phase aggregation. This is distinct from #176 and #177's remaining
run-log coverage work.

### #92 / #188 / #196 — Proportionate evidence boundaries

Retired 2026-08-19. #92's second plan-history and model summaries duplicate
#198's structured Git provenance without a remaining concrete consumer.
#188's narrative retelling can remain an optional human technique, but its
gates cannot establish global coherence. #196 cannot infer lesson influence
or justify eviction from injection/outcome records; #193 already retains the
bounded injection evidence. Do not recreate these as product surfaces.

### #290 — Bare-plan audit altitude policy

Retired 2026-08-18. Bare audits keep uncovered routes for named safety,
ordering, ownership, compatibility, bypass, and acceptance properties
actionable, while unselected delivery mechanisms remain detail-owned unless the
plan explicitly makes one the observable contract. Run-grade mechanism and
same-finding `edit_drift` advice remains recommend-only, non-causal comparison
evidence that changes no enforcement or outcome; Jira-grade audits suppress it.
On 2026-08-17, a cross-route replay of create's combined and split proposal
paths established the boundary: keep the missing property catchable and let
detail select its delivery mechanism. #231's causal-provenance follow-on is
retired; separate live work remains #241 (bare-prompt generation) and #262
(detail-readiness guidance).

### #299 — Completeness coverage replay

Withdrawn 2026-08-20 (user-confirmed). The proposed replay would select a
full-discovery cadence before #173 could design a cache or re-check lane. Its
[detail-grounded audit — retained historical summary](../evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)
established that proving the model-visible input boundary requires a hermetic
capture runner, not a bounded measurement. This is a **proof-burden inversion**:
the proof system costs more than the decision it would support. Do not recreate
the corpus, capture runner, or cache/re-check work from this record. Keep #173
deferred and use fresh completeness audits. Re-open only when measured
operational audit cost warrants a new, bounded evidence path. This id stays
retired; later leftover heading-regex work is #300, not a reuse of this
record.

### #103 — Completeness-audit purity cleanup umbrella

Retired 2026-08-04. Its opt-in request shipped as `--purity`; call-end logging
is installed around the deterministic purity pass; parallelism was
considered separately (retired 2026-08-27, see #147's own record above); and
the prompt-work question is owned by #151. The keep/cut decision remains
#210. No umbrella work remains.

### #211 — Detail-bundle re-seeding investigation

Closed 2026-08-04. The original question is answered: complete application of
conceptual findings converges, and CLAUDE.md's four checks capture the workflow
remedy. Bundle size was not the driver. The two distinct residuals were split
into #231 (the causal-provenance follow-on, retired 2026-08-19) and #229
(detail prompts reference rather than copy plan fences).

### #153 / #158 — Impact-recurrence handling

Closed 2026-08-11. `plan-tool convergence` and completeness stderr report a
recommend-only pause when the same open, explicit high-impact seam persists
without shrinking across compatible audit history. It neither stops iteration
nor mutates a plan. Do not restore the older structural-stop design; #231's
causal-provenance proposal is retired.

### #261 — Convergence policy-channel ownership

Closed 2026-08-11. `create`, `detail`, `completeness-audit`, and reconcile
converge over different evidence channels, so they do not share one blocking
predicate. Reconcile keeps its independent impact-calibration overlay. Reopen
only if a caller combines conceptual and impact-calibrated findings in one
finalization decision.

### #251 — Region-trending convergence layer

Retired 2026-08-08. The `spinning` / `FORK_*` region-trending subsystem fired
once on a false alarm and had no durable signal population. Its removal keeps
MIXED-STEP findings, standalone `split` and `scope-out`, and the current
diagnostic state. Do not revive the removed vocabulary or its gated actuators;
re-premise any future remediation on a currently observed property.

### #116 / #148 / #159 / #160 / #168 — Fork-actuation candidates

Retired 2026-08-08 with the region-trending layer. These entries depended on
the removed `spinning` / `FORK_*` verdicts and therefore have no live trigger
or evidence contract. A future split, scope, or seed-writing capability needs a
fresh observable premise rather than a renamed fork path.

### #91 / #248 — Stage-differentiated audit bars

Shipped 2026-08-10. Bare and detail-grounded audits use their separate
conceptual bars, with the bare stage retaining named-property correctness gaps
and deferring unselected implementation mechanics. Medium conceptual findings
demote only when classified as documentation. Reporting polish is #260; #231's
bad-fix-provenance proposal is retired.

## Shipped records

### #121 — Deferred-concept sign-off

Shipped as the flat lazy-deferral MVP. The remaining concept work is owned by
#126–#134; archived implementation plans preserve the delivery history.

### #122 — Per-step detail commits

Shipped 2026-07-11. `detail --commit` commits each converged step. The separate
resume-state question belongs to #88.

### #123 — Cooperative convergence-loop time budget

Shipped 2026-07-12 for `create`, `detail`, `completeness-audit`, and
`detail --reconcile` iteration loops. The remaining deadline checks at the
`completeness-apply` walk, `run` batch, and outer `detail` batch boundaries are
owned by #230; argparse deduplication belongs to #80.

### #125 — Severity-aware low-yield audit convergence

Shipped 2026-07-17. The two-pass severity-aware low-yield rule is documented in
`docs/how-to/pipeline/audit.md`; the former `--reuse-audit` coverage-persistence gap is
resolved.

### #249 — Distill shared-implementation criterion

Shipped 2026-08-08. A split proposal accepts shared implementation only when
the seed names a concrete common function, module, or file; a shared data
source alone is not evidence for one plan. The withdrawn audit-trajectory seed
is the regression fixture.

### #250 — Plan withdrawal

Shipped 2026-08-08. `plan-tool withdraw <name> --reason ...` moves the plan and
its detail bundle into the withdrawn archive and deregisters it. The command
does not judge whether withdrawal is appropriate or implement a `revive`
inverse.

### #252 — Dependency-cohesion grounding

Shipped 2026-08-08. `create` prioritizes `depends_on` claims between steps with
no shared production file, excluding test paths. This is grounding order, not a
topology verdict or a plan-admission gate.

### #161 — Seed guardrail sections survive `create`

Shipped as `2-scope-fence-continuity` (2 steps, both green). A seed's
`Scope guardrails`, `Audit guardrails`, and `Expected placement` sections are
recognized as author-supplied plan-body sections, rendered verbatim over model
output, and a create stage that drops one emits an advisory
(`create.py:_extract_supplied_guardrails` / `_find_dropped_guardrail_headings`;
the shared recognition/rendering leaf is `plan_tool/scope_fence.py`). The
grounding half — giving the audit the *originating seed's* contract rather than
whatever survived into the body — is still open as #162, and the Claude-judged
fold detector on top of the deterministic check is #163.

### #208 — The `roadmap` arc, positions 01–04

Shipped 2026-07-31 through 2026-08-05 as `roadmap-01-domain-constraints`,
`roadmap-02-feedback-channel`, `roadmap-03-components`, and
`roadmap-04-plan-derivation`. Arc position 05 (framework lenses) stays open and
keeps the #208 entry alive in `BACKLOG.md`. Run evidence across both briefs is
in [`ROADMAP_RUN_MEASUREMENTS.md`](../evidence/roadmap-run-measurements.md); the four
settled decisions below governed the arc and still govern position 05.

**Framing — settled 2026-08-02, user-confirmed; do not re-open.** The verb
**collaborates**: it proposes, a human reviews and gives feedback, it
re-proposes against that feedback. It is **not** a replacement for human
authorship, and must not be justified or measured as one.

The 2026-08-01 three-arm comparison was read as the arc's premise failing and
acted on the same day — the Outcome was narrowed to "provenance and finality",
and the components artifact and framework lenses were cut. **That action was
reverted the same day**, because the experiment compared two *one-shot* outputs
and asked which was the better plan, which is a **replacement** benchmark. Under
the collaborative Outcome, a proposal that lands where a competent human's first
draft lands is a *good proposal*; the failure mode would have been a proposal
materially worse, and that is not what came back. Components and lenses were cut
for failing a test that does not apply to them, and both are restored. **Do not
re-cut them on one-shot-quality grounds.** What the measurement does still say:
the arm's rejected-alternative rationale was *weaker* than what the control
derived live, because the roadmap's reasons are frozen at authoring time while
`create` grounds against fetched reference docs — an argument for letting a
later stage re-ground a decision, not against the arc. Full write-up and its
citation rules: [`ROADMAP_LAYERING_MEASUREMENT.md`](../evidence/roadmap-layering-measurement.md).

What survived and is promoted rather than demoted: the roadmap arm recorded
decisions as `settled` with rejected alternatives and a don't-re-open fence,
where both controls left the central decision open in prose while their steps
silently committed to it. Under the collaborative Outcome the decision rows and
the `pending` marker **are the product** — they are what a reviewer reacts to.

**Naming — settled 2026-07-31, user-confirmed; do not re-open.** "roadmap" is
**reserved for this pipeline** (the verb, the seed group, and the
`04-roadmap.md` artifact). Two unrelated doc senses were renamed rather than
this verb, because each was a broad word over a narrower concept: `SEED_FORMAT.md`'s
"Roadmap, not schematic" → **"Destinations, not turn-by-turn"**, echoed in
`CLAUDE.md` as `destinations-not-turn-by-turn`; and the ordered stage sequence a
seed group ships → **arc**, which was already the native term.

**Carve B of the decision-record rule — settled 2026-08-05, user-confirmed:
narrow.** A revision must not mint a decision **about the removed row itself**;
the `removals` record already cites that drop. A decision anchored to a
**surviving** row about a gap the removal opened is the positive branch, not a
Carve B failure. Rejected alternative: the broad reading ("must not mint *any*
decision beside a removal"), which is over-prescriptive — it would silence
gap-filling judgments the positive branch exists to record. `roadmap-revision.md`
states the narrow reading.

**The clarification permission covers scope — settled 2026-08-04,
user-confirmed; do not re-open.** The revision prompt lifts the authoring
prompts' "do not ask a question back" when a request is ambiguous *or implies a
scope the model cannot infer from the reviewer's words*, capped at one question
rather than a checklist, with the requested change still made rather than held
for the answer. No test separates the readings — the only observable is that a
question was asked, never whether it was warranted — so the scope clause is
pinned by `test_revision_prompt_overrides_the_authoring_no_questions_rule`.
**Rejected:** tightening to action-ambiguity only, which loses a measurably
useful behavior; and leaving it implicit, which either inflates into a question
on every request or gets tightened away later by an unrelated edit.

**The shipped position-01 plan is deliberately left alone.**
`docs/implementation-plans/archive/2-roadmap-01-domain-constraints.md` and its detail
bundle name the later positions under their old numbering. That is an execution
record of what that plan chose not to do, not live design, and retro-editing a
completed plan's fence to match a later decision is the code-canonical hazard
`CLAUDE.md` warns about. Do not "fix" it in a sweep.

### #233 — Duplicate `BACKLOG.md` ids fail a test

`tests/test_backlog_ids.py` fails an id that opens two entries, and
[`docs/TRACKING.md`](../TRACKING.md#adding-a-new-entry) § "Adding a new entry"
holds the id-selection rule. When two entries share an id, the entry cited
elsewhere keeps it; with equal citations, the one filed later moves. The `#404`
collision the test found is settled: "Decide the completeness audit's
intent-fidelity boundary" keeps #404, and "Installed skills make per-command
model selection explicit before invoking plan-tool" is #425.

Whether the id test can read the whole file is a separate check in its own file,
`tests/test_backlog_readability.py`. It refuses a `BACKLOG.md` with a malformed
opener, a code fence left unclosed, or no entries, because each lets a duplicate
pass unseen. It stays separate because a scope contract has one Outcome: the id
test is the entry's one fact, and the readability check is a precondition on it,
not a `BACKLOG.md` format validator. Neither test checks any other entry
structure. Not guarded: `BUG_BACKLOG.md` (no ids), an id held only by a
`**Closed …**` record, and reuse of a removed id.

### #496 — Roadmap mapping and seed-to-plan derivation in the existing pipeline

Shipped 2026-10-16 in PR #107 (merge `b90edb570`, code head `1ddc48bf9`, full
suite 14,642 passed / 67 skipped); closed 2026-10-19. The plan is
[`2-roadmap-plan-derivation.md`](../implementation-plans/archive/2-roadmap-plan-derivation.md).
The change improves the existing route only: stage-four guidance in
`roadmap-plans.md` (shared producers and consumers, production/update
operations, and an owner for every hop of a source-required transition),
per-row seed materialization, create's step-proposal guidance (conditional
implementation behind pending prerequisites), and protected `## References`
retention through `create`. No new mode, CLI entry, record, lifecycle or gate.

**Demonstrated, each on the Integration benchmark with one or a few samples:**

- **Granularity.** On frozen upstream artifacts the candidate mapping has ten
  rows against the baseline's five, separating session execution, chat,
  streaming, repository references and revision review, which the baseline
  combined in one eight-step plan. Counts alone do not establish improvement.
- **Implementation survives prerequisites.** The unchanged handoff seed went
  from one prerequisite-check step to five implementation and proof steps.
- **Operation ownership.** A fresh mapping assigns the corrected-output and
  renewed-evidence operation to its producer, and the seed and six-step base
  plan keep it. Three hop-trace mapping samples (10, 10 and 9 rows) all name an
  owner for every hop of the handoff-content route.
- **References retention.** Under byte-identical seed input the baseline
  loses all four local References and the candidate keeps them.

**Deliberately not done, by owner decision 2026-10-16** (stop at base plans,
focus on application business logic):

- no base plans for the AWS delivery and end-to-end proof rows; 8 of the 10
  candidate rows have base plans, and observed-deployment proof was not traced;
- no ordering or integration-owner trace beyond the business routes above;
- no detail files, application code, deployments or live provider runs;
- no semantic-coverage, success-rate, causal or efficiency claim.

**Accepted limits:**

- The producer seed does not say the worker releases handoff content for the
  successor; detail authoring and its audit own that mechanism.
- A partially edited protected References block is restored as a second full
  copy beside the edited one. Block integrity (no dropped content) was chosen
  over line-level append after review rounds pulled in opposite directions;
  the defect is filed in `BUG_BACKLOG.md` ("A partially edited protected
  References block is restored as a second full copy").
- The prerequisite guidance sits in both the roadmap prompts and the shared
  step-proposal prompt, so the two can drift.

**Deliberately not filed:** a mapping-altitude audit (reopen only if a second
route shows an unowned hop; see #435 for the advisory precedent) and a seed
audit verb (the seed-altitude audit stays a session procedure after
`--materialize`). PR #105's separate plan-set layer was withdrawn as out of
scope; do not reintroduce it under this id. #462, #493 and #494 stay separate.

Evidence: [comparison](../evidence/roadmap-plan-derivation-comparison.md),
[corrected-evidence iteration](../evidence/roadmap-corrected-evidence-iteration.md),
[handoff-content trace](../evidence/roadmap-handoff-content-trace.md) and the
[testing handoff](../../handoffs/2026-10-16-roadmap-business-logic-base-plan-loop.md).

### #521 — A short core path for newcomers

Shipped 2026-11-06. A bare `plan-tool` prints the core path (user-level skill
install, create, both audits, detail, `run --all`, `reconcile-code --all`); a
test parses every command line in it against the real parser. It stays a usage
error, printed to stderr with exit 2, so a script whose subcommand expanded to
nothing still fails; a terminal check was tried and dropped because it cannot
tell a script from a person. `--help` deliberately stays the full catalog,
with one pointer line to the short screen, because the skill and directives
cite `--help` as the catalog. `init` is deliberately not a command line on the
screen: a copied placeholder intent would be written as the real one, and
setup runs through the skill instead (#522).

### #522 — One-command repository setup

Superseded 2026-11-06 before shipping: repository setup runs through the
skill instead (DIRECTIVES.md § "Setting up a repository: the project
profile"), which asks for the intent, confirms the exact text and runs `init`.
An `init --install-skill` flag was built and withdrawn unshipped: once setup
runs through the skill, the skill is already installed, and the flag's Claude
and Cursor installs were project symlinks that work only on the machine that
made them. Do not reintroduce it for the skill route. PyPI or `uvx`
distribution remains #514's decision.

## Closed decisions

### #117 — Keep and instrument the code-reveals-a-split detector

Decided 2026-07-10. The detector remains additive, advisory, and
recommend-only. Telemetry is the re-open condition; no work is currently open.

### #218 — Do not consolidate generate/parse/retry loops

Decided 2026-08-01. The `detail`, `create`, and `roadmap` loops differ in
validation, correction accumulation, budget semantics, failure recording, and
return contracts. Reconsider only after one named behavior demonstrably drifts
across all three; retain caller-specific behavior at the edge.

### #215 — The roadmap constraints stage keeps its three-attempt budget

Decided 2026-08-05: **no action.** Twelve samples across **two** briefs never
exceeded the budget. `cfp-review` spent 3-of-3 once and 2-of-3 once; a second
brief (`toollib`, a community tool library — continuous cadence, offline-first
desk, physical inventory) passed **1-of-1 on both stages in both an authoring
and a revision run**. The pressure is brief-specific, not a budget shortfall.

The row-count hypothesis does **not** explain it: `toollib`'s constraints
inventory was 33 ids against `cfp-review` run 1's 35 — slightly *smaller*, and
it passed where the larger one spent every attempt. Whatever drives the retries
is content, not size.

Re-open only on a brief that actually exhausts the budget. A larger budget
remains the wrong first reach; #217's `AttemptFailed` event now names the
failure kind on every spent attempt, so the next such sample is diagnosable
rather than guesswork.

### #232 — A roadmap revision does not add design rows nobody asked for

Answered 2026-08-05 by measurement, as the entry's own Stop rule prescribed
("if two briefs show no unrequested growth, close it as answered rather than
building anything"). **Nothing was built, and nothing should be.**

Six revision runs across two briefs, every one measured against a
write-protected baseline: **every collection delta traced to a feedback row,
and no collection grew without one.** `cfp-review` held 12 entities / 8
workflows across five runs, its rule drop and both decision mints being
requested; `toollib` held 11 / 13 / 13 with a single requested decision.
Entity **field-name sets** were preserved 12/12, 11/12 and 11/11 — the one
divergence being the entity the request named.

This stays unguarded on purpose: addition must remain legal, since feedback
routinely asks for a new row, so a check would have to judge *whether the
reviewer wanted it* — the unobservable-property trap. The binary fact is the
count, and the judgment is the reviewer's.

Method worth reusing: copy both artifacts aside and `chmod 444` them **before**
the run. An earlier attempt at this comparison was impossible because the
baseline had been overwritten in place.

### #219 — Do not split `review.py`

Decided 2026-08-02. Size alone does not block any outcome, and a banner-seam
split would create a facade or scatter imports. Re-open only for a concrete
outcome blocked by the module boundary or a genuine import cycle. Cross-module
As of 2026-08-19, cross-module apply-eligibility invariants are pinned by the
table test.

### Root-enrollment rollback as a standalone feature (BUG_BACKLOG, unnumbered)

Withdrawn 2026-09-18. The entry proposed an operator command to clear a valid
root's accepted-head selection so hand-written feedback could reach the
legacy revision writer again. Its motivating Integration case was not that: it was a
cut-short `--from-stage` revision of a pending decision that no supported
route can accept (BUG_BACKLOG "No supported route can accept a pending roadmap
decision"). The plan built for it,
`docs/implementation-plans/archive/2-root-enrollment-rollback.withdrawn.md`,
drew a new step-1 defect in five of six bare-plan audit rounds and never
converged. Rolling back a revision that fails or is cut short shipped
2026-09-18 as `roadmap-revision-rollback`. Re-open only for a concrete case
that needs a valid, fully revised root un-enrolled for a reason neither of
those covers.

### No supported route can accept a pending roadmap decision (BUG_BACKLOG, unnumbered)

Removed 2026-09-18, not fixed here. The gap was real (neither a hand edit nor
feedback can settle a `pending` decision, and a model reply could claim a
settlement that never happened — see `roadmap-revision-rollback`'s own
former backlog entry, "Roll back a roadmap revision that fails or is cut
short" (shipped and removed 2026-09-18), for the Integration trace that found it),
and it landed 2026-09-18 as `roadmap-decision-settlement`, a dedicated
settle action with its own preflight and receipt
(`docs/implementation-plans/archive/2-roadmap-decision-settlement.md`).

### Dangling-journal reconciliation cut from `roadmap-revision-rollback`

Cut 2026-09-18, filed forward as BACKLOG #399. Steps 2 and 3 of
`docs/implementation-plans/archive/2-roadmap-revision-rollback.md` built, then removed,
a mechanism that peeked a dangling `recover_roadmap_publication` journal
before recovery and folded its members into the revision checkpoint when
eligible, so the checkpoint's `last_written_bytes` would not go stale across
a crash-then-silently-recovered write. Five consecutive detail-grounded audit
rounds each found a real, code-verified defect in this one mechanism — the
eligibility rule went through a bare kind exclusion (`kind !=
"revision-restore"`), then a kind exclusion plus a tracked-members-only
check, before landing on the correct, final shape: an exact-match allowlist,
`kind == "stage-publication"` (the one kind the checkpoint-owning call site
can itself ever produce), which is complete regardless of how many other
`PendingGeneration` producers exist, known or future. Ten were confirmed at
cut time (`stage-publication`, `revision-restore`, `root-enrollment`,
`review-seal-promotion`, `baseline-enrollment`, `feedback-publication`,
`confirmed-feedback-reopen`, `structural-feedback-publication`,
`candidate-proposal`, `candidate-review-replacement`) by grepping every
`kind=` construction in the codebase directly — the completeness-audit's own
finding that motivated the allowlist had itself enumerated only eight,
missing the last two, which is exactly the class of gap an allowlist (name
the one legitimate case) closes that an exclusion list (name every
illegitimate one) cannot. An eleventh, `decision-settlement`
(`plan_tool/roadmap_decision_settlement_enrolled.py`), landed the same day via
`roadmap-decision-settlement`'s merge into this clone (2026-09-21) — the
allowlist's own design already covers it without modification, since it names
the one legitimate kind rather than excluding every illegitimate one; this
note exists only so a future re-grep isn't needed to notice the count moved.

The mechanism was cut, not further hardened, on a conceptual re-evaluation
(model: Opus) after the fifth round: the seed's own `## Deferred` clause
("if covering it requires reasoning about another writer's state, stop and
file a separate backlog item instead of widening restore") pre-authorized
exactly this deferral, the mechanism closed only a narrow crash window while
an adjacent, equally narrow window was already an accepted residual
elsewhere in the same plan, and the `"revision-restore"` case the allowlist
existed partly to protect already resolves correctly with no mechanism at
all (a completed prior restore lands every tracked file at `pre_run_bytes`,
which the ordinary whole-vector comparison already matches uniformly). The
allowlist shape (`kind == "stage-publication"`) is recorded here so BACKLOG
#399 does not have to re-derive it from zero.

### #392 — No durable per-repo codebase profile

Answered 2026-09-17 by measurement, as the entry's own Output-of-investigation
field prescribed. **Nothing was built, and nothing should be.**

713 run logs (`.plan-tool/runs/**/*.jsonl`) measured directly: 89.7% of
aggregate wall-clock (315,287s) sits inside logged Claude calls. The residual
10.3% is not a systematic per-invocation cost — the median gap at every
measured transition point is 0ms — but a small number of large one-off tail
gaps that always land in the same position (after the last step, before
`run_end`) regardless of step count or repo content, the signature of process
suspension or unlogged rate-limit backoff (`rate_limit_loop.py`), not repeated
repo scanning. Existing per-plan caches (`grounding.json`, `purity-cache/`,
`checkpoints/`) already cover what plan-tool's own Python side touches;
`create`'s anchor walk is a 3KB-capped excerpt (`_LOCAL_CODE_EXCERPT_BYTES`),
not a tree walk.

Re-open only on a *measured* hotspot naming which invocation redoes what real
work — not on a resemblance to another tool's design.

### #390 — The skill routers do not set `model:`

Decided 2026-10-06, owner-confirmed. All three routers
(`integrations/{claude,codex,cursor}/SKILL.md`) and the tracked
`.claude/skills/plan-tool/SKILL.md` leave `model:` unset, with a frontmatter
comment saying so; they previously forced `model: opus`.

The field switches the *driving session* while the skill is loaded. It does
not reach the subcommands, which take their model from `--model`, then
`.plan-tool/backends.json`, then the backend default. Dropped because:

- it overrode a model the user or host chose on purpose (a Sonnet session,
  or an AI-DLC project's model policy — see #442);
- most driving work (running commands, reading saved reports, bounded edits,
  re-running tests) is implementation and validation, the working tier's
  job, so forcing Opus on every loaded turn cost more without buying much;
- `opus` is a Claude model name, meaningless in the Codex and Cursor routers.

Not a reason: `integrations/shared/DIRECTIVES.md` § "Which model to run a
subcommand with" governs the `--model` passed to subcommands, a different
layer from the session model, so the override never conflicted with it.

Considered and rejected: keeping the override so conceptual driving decisions
(whether an arm belongs, whether a plan's premise holds) land on Opus. A
frontmatter field applies to every turn the skill is loaded and cannot tell
those decisions from routine command-running; switching the session model at
the decision is the operator's call.

Re-open only with evidence that driving sessions on the working tier make
conceptual mistakes that a skill-level override would have prevented.

### #442 — AI-DLC errors with the plan-tool skill installed: closed as not reproducible

Closed 2026-10-06, owner-confirmed. Do not reopen without a captured error.

**What was reported.** In Integration (AI-DLC 2.9.0), adding the plan-tool skill as a
symlink produced AI-DLC errors. The error text, the install location, and
whether AI-DLC's tooling or the model raised it were never captured, and the
skill is no longer installed in Integration.

**What was checked, and found clean.** A scratch copy of Integration with the skill
installed six ways (`install-skill --root .agents` symlinked and `--copy`,
`--root .claude`, a folder symlink under `.agents/skills/` and under
`.codex/skills/`, a real folder under `.codex/skills/`) passed `aidlc doctor`,
`aidlc-runner-gen.ts check`, `scopes --check`, and the `write` pruning pass,
which leaves the plan-tool folder in place. AI-DLC's frontmatter reads are
regexes over `scopes/*.md`, never YAML over skills. Exit codes from those
checks were not captured; results were read from each tool's own output.

**What was not checked.** AI-DLC's runtime `PreToolUse` guards
(`plan-approval-guard`, `state-transition-guard`, `review-freeze`,
`reviewer-scope`): none was exercised with the skill loaded mid-stage. AI-DLC
2.10.0 exists (`aidlc update --check`, 2026-10-06) and was not tried, so a bug
fixed upstream cannot be ruled in or out. The skill's `paths` and
`when_to_use` triggers overlap AI-DLC's stages in Integration; whether that loads the
skill mid-stage is unmeasured.

**Considered and rejected:**

- narrowing `paths` and `when_to_use` now: no evidence ties them to an error,
  and the skill's load rate is unmeasured;
- keeping #442 open and gated: with the failing setup gone and no error text,
  the gate cannot be met by anything but a recurrence.

**Split out.** The invalid YAML in the routers' `argument-hint` was found on
the way and is independent of AI-DLC: BACKLOG #444, shipped 2026-10-06.

**Re-open only when** the error recurs with its text and which hook or tool
printed it. A refusal from an AI-DLC guard points at the runtime-hook
candidate above; a stage run with the skill installed on AI-DLC 2.10.0 is the
first thing to try.

## Same-batch relation follow-ups, 2026-11-04

The self-reference bug entry also carried two lower-severity observations.
The endpoint-kind exhaustiveness concern was already pinned by
`test_relation_endpoint_table_types_every_kind_but_the_deliberately_untyped_decision_anchor`
in `tests/test_roadmap_candidate.py`: every relation kind has a typed target
except the deliberately generic decision anchor. That concern requires no new
policy or implementation.

The same-batch endpoint helper is also evaluated for removed relation atoms.
No supported failing input was established for that observation; the source
entry described it as unreachable under the predecessor gates. Retire that
contingent change rather than widen the self-reference fix. Reopen only with a
valid admitted predecessor and candidate for which a removed relation is
incorrectly authorized through a same-batch addition. This is a retirement of
an unproven risk, not a claim that removed-relation behavior changes.
