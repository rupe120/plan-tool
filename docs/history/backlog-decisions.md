# Historical backlog decisions

This is the durable home for closed backlog decisions and retired composite
records. `BACKLOG.md` is a forward-looking work queue; completed delivery
history belongs in archived implementation plans and git history, while these
short records preserve decisions that would otherwise invite re-investigation.

## Queue cleanup, 2026-09-16

The following delivered IDs remain citable after queue cleanup. Their plans
or the named contract carry implementation detail. The compact completion
records that #315, #327, #328, #351 and the brief-drift closeouts once kept in
`BACKLOG.md` live here and in the table below since 2026-11-14; `BACKLOG.md`
holds open work only.

On 2026-09-16, three roadmap compatibility entries that shared IDs with
authored-artifact version work were renumbered: former roadmap #362 → #383
(per-stage supplements), #363 → #384 (carried settled decisions), and #364 →
#385 (JSON status). The authored-artifact version entries retain #362–#364.

| ID | Delivery record or current contract |
| --- | --- |
| #164 | The side-by-side Jira-grade detail route shipped 2026-07-30, stopped new authoring 2026-08-24, and is selected for full retirement by live #308. |
| #181, #182 | [Risk-profile declaration](../implementation-plans/archive/2-risk-profile-1.md) and [advisory detail context](../implementation-plans/archive/2-risk-profile-2.md). #314 was a separate evidence-gated follow-up and is since discarded. |
| #247 | The read-only saved-audit ledger in `plan_tool/review_persistence.py` and `plan_tool/completeness_report.py`; #303 remains the separate comparison proposal. |
| #293 | [Jira developer handoff plan](../implementation-plans/archive/2-jira-developer-handoff-companion.md); the current paired export contract is `JIRA_FORMAT.md`. |
| #295 | [Recommendation confidence plan](../implementation-plans/archive/2-recommendation-confidence.md); #316 and #382 were independent follow-ups and are since discarded. |
| #305 | `plan_tool.response_contract.coerce_response_id`, the shared cycle-free grammar for `gates`, `foundational_logic`, `create`'s dependency/note-key parsers, `intent_proposal`, and `concept_sync`; each caller keeps its own `None` disposition. |
| #309 | The `retire-roadmap-v1-evidence` post-run review fixes, recorded in commits `55a989df`, `9a676e7d`, `74a4e23e` and the subsequent review commits cited by Git history. #311, which owned the remaining efficiency work, is since discarded. |
| #315 | [Confirmed feedback reopen proof](../implementation-plans/archive/2-roadmap-confirmed-feedback-reopen.md); #242 remains a separate retention redesign. |
| #327 | [Seed-ingestion routing plan](../implementation-plans/archive/2-seed-ingestion-routing.md) and the [seed-ingestion contract](../reference/contracts/seed-ingestion.md). #102 and #353 remain separate. |
| #328 | [Immutable candidate versions plan](../implementation-plans/archive/2-roadmap-immutable-candidate-versions.md). #329 remains separate persistence-integrity work; #330 is since discarded. |
| #334 | [Mechanism-reach authoring plan](../implementation-plans/archive/2-mechanism-reach-01-authoring.md); #336 consumes its shipped rule; #335 is since discarded. |
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

- **Outcome:** enrollment captures one immutable root; an admitted feedback
  lineage produces inert candidates, questions, answer-bound replacements, and
  exact review seals; only exact promotion changes the accepted head. The
  promoted version is the selected source for the completed downstream reader,
  while every stored version remains immutable and legacy in-place writers
  refuse an enrolled roadmap.
- **Direct-reader migration boundary:** `plan_tool/roadmap_view.py:load_roadmap()`
  is the completed proof. Defer accepted-head migration scope selection for:
  `plan_tool/create.py:_load_roadmap_research_targets()`,
  `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed()`,
  and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()`.
- **Real-backend observation (2026-09-01, redacted):** candidate phase;
  13,212 prompt bytes; context membership is 2 full members and 19 inventory
  entries; expansion is not used; terminal outcome is `failed`. This records
  operational facts only, with no prompt, response, or model-quality claim.
- **Deferred hardening:** #329 keeps a persistence-integrity finding that the
  representative happy-path proof did not need; #330, the other, is since
  discarded.
- **Status:** closed 2026-09-01 after the deterministic lifecycle tests and
  the recorded real-backend observation; moved here from `BACKLOG.md`
  2026-11-14.

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

Superseded 2026-11-05: `roadmap-versioned-from-birth` removed
`--confirm-brief-rebind` and the non-stage brief-drift routes. A stage run now
refuses once an accepted head exists, and a changed product definition goes
through feedback and candidate review or a successor lineage.

### #384 — Carried settled decisions

Completed by 2026-09-17 (plan archived that day). A closed set of confirmed upstream decisions reaches
`roadmap` through the single brief as inherited decision rows that cite the
confirmed answer that settled them; options an upstream question did not select
are never recorded as rejected alternatives. The 2026-09-16 comparison selected
it over per-stage supplements (#383): both inputs preserved the material facts
but recast confirmed answers as `settled` Roadmap decisions without citation
([evidence](../evidence/roadmap-aidlc-intake-comparison-20260916.md)). The plan
is [`2-roadmap-carried-settled-decisions.md`](../implementation-plans/archive/2-roadmap-carried-settled-decisions.md).

## Resolved and retired bug-backlog records

Records marked **Resolved** include a shipped behavior change and regression
coverage. Records marked **Retired** are not behavior fixes; their retained
re-open condition identifies the evidence or scope change that will justify a
new entry.

### `BACKLOG.md` recipes that run `detail` straight after `create`

Retired 2026-11-15. The four recipe blocks the entry named left `BACKLOG.md`
with their entries, and the file now holds no fenced block, so there is no
recipe to correct. A repo-wide sweep of tracked documents for a fenced
`plan-tool create` followed by `plan-tool detail` with no
`plan-tool completeness-audit` between finds six pairs: the headless syntax
examples in `integrations/shared/DIRECTIVES.md` and the three router
`SKILL.md` files (and their `.claude/skills/plan-tool/` copies), each labelled
"independent syntax examples, not a stage sequence" next to the two audit
gates. Reopen when a `BACKLOG.md` entry carries a copyable recipe that runs
`plan-tool detail` after `create` with no `completeness-audit` before it.

### `--commit`'s post-commit clean check on paths git keeps reporting as modified

Resolved 2026-11-15, in two halves. **Fixed:** untracked content inside a
committed submodule shows as ` M vendor/lib` after the parent commits, though
the commit could not have held it; the check now reads status with
`--ignore-submodules=untracked` (`commit_all`'s `_dirty_footprint_paths`), while
a tracked change in a submodule still counts. **Retired, by design:** a path
that a non-idempotent clean filter keeps reporting as modified. Git itself says
the commit did not absorb it, which is the same state as a hook rewriting a
committed file, so the check keeps counting it and the commit is reported as
committed with the remaining dirt named. Both are pinned in
`tests/cli/test_gitcommit.py`. Reopen the second half only if git offers a way
to tell a filter's re-modification from a hook's rewrite.

### The tracked `.claude/skills/plan-tool/` copy of the skill

Resolved 2026-11-15 (owner decision). The copy was untracked and ignored: it had
drifted 87 lines from `integrations/` and an assistant in this checkout loaded the
stale text. `plan-tool install-skill` installs the skill from `integrations/`, so
nothing tracked can drift from its source. Reopen only if a fresh clone or CI must
carry the skill without running the installer; then regenerate it with
`plan-tool install-skill --copy` and add a test that fails when it differs from
`integrations/`.

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

### `_append_added_row_prose` copies an artifacts mapping its sole caller no longer uses

Retired 2026-11-15, owner-confirmed. The copy (`dict(artifacts)`) holds a
handful of stage-artifact keys once per candidate, and the entry confirmed no
aliasing exists at the call site, so removing it changes cost only. Mutating in
place also widens the parameter from `Mapping` to a mutable type, a signature
change for no behavioral gain. Reopen when the mapping grows past a handful of
keys or a second caller appears.

### `review_plan_full` re-runs the audit-input snapshot capture `cmd_review` already ran

Retired 2026-11-15, owner-confirmed. Both captures are error probes whose
results are discarded; neither feeds a snapshot onward. `review_plan_full` has
three callers (`bench.py`, `review.py`, `cli/review_cmd.py`) and its capture is
the guard for all of them, while `cmd_review`'s preflight capture maps a
failure to exit 2 before the run log is committed to. Removing or threading
either one changes an error path on all three callers to save one extra read
per step's detail file. Reopen with a measured review latency attributable to
the second capture on a large plan.

### `install-skill` recomputes a resolved path and re-reads source bytes

Retired 2026-11-15, owner-confirmed. The redundancy is one `resolve()` and one
small file read per invocation, with no correctness effect. The change would
thread new return values through `_classify_dest`, the function the open
destination-recheck race entry also reshapes, so the two should land together
if either does. Reopen alongside that race entry, or if the installed set grows
to files large enough for the second read to matter.

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
and #197 retained independent provenance, reconciliation, retrieval,
and contradiction contracts; #197 is since discarded.

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
retired; #241 (bare-prompt generation) is since discarded; #262
(detail-readiness guidance) remains.

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
causal-provenance proposal is retired. The two seeds that still specified that
design, `impact-recurrence-01-classifier.md` and `impact-recurrence-02-loop-stop.md`,
were deleted 2026-11-15 (owner decision): `create --from-existing` refused both
for a missing `## References`, and adding one would have made the retired design
executable.

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
demote only when classified as documentation. Reporting polish (#260) is since discarded; #231's
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
route shows an unowned hop; see the discarded #435 for the advisory precedent) and a seed
audit verb (the seed-altitude audit stays a session procedure after
`--materialize`). PR #105's separate plan-set layer was withdrawn as out of
scope; do not reintroduce it under this id. #462 stays separate; #493 and #494 are since discarded.

Evidence: [comparison](../evidence/roadmap-plan-derivation-comparison.md),
[corrected-evidence iteration](../evidence/roadmap-corrected-evidence-iteration.md),
and [handoff-content trace](../evidence/roadmap-handoff-content-trace.md).

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

### #423 — Structural roadmap feedback goes through one revision approval gate

Closed 2026-09-23 by the Roadmap Structural Feedback Approval plan, opened
2026-09-21 from Integration focused-feedback retries. Ordinary ledger feedback
validates typed operations into a bounded or structural inert candidate without
user route selection. A structural candidate receives one exact
approve/edit/reject decision; approval seals that candidate and promotion alone
advances the accepted head. Edit requires a fresh decision, and failed,
rejected, interrupted, and stale proposals preserve canonical artifacts and
seeds. Decision settlement remains a separate selector-shaped route (structural
escalation, impact analysis, and exact-pair structural rewrite were removed
2026-11-05 by `roadmap-versioned-from-birth`). Workflow authoring, automatic
approval, grouping, and multi-user approval stay out of scope.

### #461 — The technology stack is a roadmap layer

Shipped 2026-10-09 (PR #46; plan
[`2-roadmap-stack-layer.md`](../implementation-plans/archive/2-roadmap-stack-layer.md);
contract in `ROADMAP_FORMAT.md` § stack collection). The `stack` collection in
`02-constraints.md` records each concern (deployment platform, store engine,
language/runtime) as chosen or open. It is called out at first publish, in
`INDEX.md`, and in every candidate review, and is rendered into the `## Stack`
seed section. A version without the collection reads as "stack not recorded".

Decisions kept (2026-10-08; do not reopen): no fifth roadmap artifact; stack
rows are authoritative over hosting and store `product` fields with no
agreement gate or comparison rule (candidate review lists them side by side);
any bound feedback item authorizes a stack-row add; the callout is display only
and never a defect class or an approval gate. Hand enrollment is deliberately
excluded from the callout.

### #533 — Roadmap requirements stay; the smallest proof governs how they are met

Shipped 2026-11-14. Settled owner rule, do not re-open: the brief's stated
requirements are the roadmap's requirements, and the smallest-proof rule applies
to how each is met and to refusing unrequested work, never to narrowing a stated
requirement unless the brief or the owner directs it. The shared header
`roadmap-smallest-proof-boundary-header.md` carries the rule to stages 1–4. Stage
1 keeps a requirement it reads as optional modeled and records a `pending`
decision whose chosen option keeps it; stage 4 gives a plan row (`cross-cutting`
when no component owns it) to any requirement the brief states that no upstream
artifact carries, and prefers several small, independently verifiable plans
without a count target. Work a stated requirement needs in order to be met
(integration, delivery, deployment) counts as part of it. Deliberately not done:
a revision-prompt guard, since the revision prompts are not given the brief, and
a `pending` decision at stages 2–3 for an upstream omission, since it has no row
to anchor to. `roadmap-seed.md` deliberately keeps its own paragraph,
scoped to its plan row, instead of the shared header: the seed model drafts one
row and never sees the brief, so a brief-level rule there would invite pulling
sibling rows' scope into the seed. The cause was
Loom's stage 1 cutting the brief-required repository browser
(`docs/evidence/roadmap-run-measurements.md` §8). #534 measures the effect; #535
owns the separate question of stage-authored `settled` decisions.

## Closed decisions

### #363 (authored-artifact upgrade route) — a release rule, not the roadmap #363 renumbered to #384

Moved 2026-11-14 to `DATA_CONTRACT.md` § "Version-evolution policy", where the next format bump meets it. The first format release that refuses a previously supported live plan or detail artifact ships an operator-invocable upgrade route in that same release; version 1 refuses nothing new, so no route ships now. It was never work with its own deliverable, so no backlog entry remains.

### #396 — No operator view of the decision-settlement receipt proof

Decided 2026-11-14. `roadmap_decision_settlement_receipt.py:decision_settlement_receipt_proves_completion` and its helpers are called only from tests; the function is a test oracle for the read-back proof rule, and receipt visibility lives in git history by the `roadmap-decision-settlement` plan's own design. No `--view decision-settlements` or status command is built. Re-open only when an operator asks for one, with the question they need answered. Origin: 2026-09-18 post-run `/code-review` of that plan, round 3.

### #269 — No hermetic roadmap-stage harness or production partial-stage mode

Closed 2026-08-28. The existing `_Env` / injected-`StageInvoker` seam in
`tests/test_roadmap.py` already supplies disposable roots, the real
`run_roadmap` path, stage-output and no-write-on-failure assertions, and
run-log / in-flight lifecycle coverage. Do not add a named harness, developer
CLI, or external-backend smoke entry point: each would duplicate that proof and
risk creating the production partial-stage mode the item forbade. A
demonstrated transport or logging gap may add the smallest deterministic test
to the existing seam. Reopen only when that seam cannot exercise a required
stage behavior without a new production surface.

### Retired conversational impact transaction

Superseded 2026-08-31. The proposal let a model-authored impact manifest become
the authority for a candidate transaction; its audit exposed recurring binding,
route-admission, snapshot, and redaction contradictions. The WIP plan is
archived as `2-roadmap-conversational-feedback.superseded.md`. Do not author or
reopen this route; the immutable accepted-head lifecycle (#328) supersedes it.
Its pre-merge branch-local `#325` label is unrelated to the live #325.

### #492 — Shared application evidence for roadmap-derived plans: use existing

Closed 2026-10-15. The reviewed record
[`docs/explanations/roadmap-plan-handoff.md`](../explanations/roadmap-plan-handoff.md)
identifies the accepted-head authority, separates the remaining provider
question from settled owner decisions, and records `use-existing` for `create`,
`detail`, and `completeness-audit`. Follow-on dispositions: #493 (shared-context
delivery) and #494 (prerequisite view) are `no-action` unless a delivery or
status-reporting need is separately demonstrated; #462 (cross-plan advisory)
keeps its own evidence gate. Evidence:
[Integration handoff evidence](../evidence/integration-roadmap-to-plan-handoff.md).
Seed: `plan-seeds/archive/roadmap-plan-handoff-investigation.replaced.md`.

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

## Onboarding and router guidance entry removed, two residuals corrected, 2026-11-13

Removed from `BUG_BACKLOG.md` on 2026-11-13: "Onboarding and installed skill
instructions conflict with canonical audit and iteration rules" (unnumbered).
The first-task paths and routers it named already read correctly at `1d8a47974`.
Two passages outside them were corrected in the same change:
`docs/how-to/roadmap.md` ran `detail` straight after `create` with no bare-plan
audit, and `RUNBOOK.md` recommended `detail --iterate` without the "only when
explicitly requested" qualifier and called the audit loop a narrow variant of
authoring.

**What was reported.** `docs/how-to/common-workflows.md` told readers to detail
before auditing and treated absent details as audit defects, and the three
`integrations/*/SKILL.md` routers described detail iteration as on by default
despite their own one-shot instruction.

**What was checked, at `1d8a47974`.**

- The authority is `integrations/shared/DIRECTIVES.md`: Gate 1 is the bare-plan
  audit before `detail`, Gate 2 the detail-grounded audit after it, and `detail`
  stays one-shot unless the user asks for its loop.
- The generated `docs/cli/` reference gives the real defaults: `create
  --iterate` is on, `detail` and `completeness-audit` are off, and `run
  --iterate` has no effect (`docs/cli/run.md`). `docs/ITERATION.md` states the
  first three.
- `README.md` (the first-task path and the lifecycle line), all three routers
  (the recipe row, the authoring-pipeline line and the iteration paragraph,
  identical across the three) and `common-workflows.md` (the lifecycle line and
  the `detail` and audit sections) state that order and those defaults. That a
  missing detail file is coverage at the bare gate, not a design defect, is
  stated in `common-workflows.md`, `DIRECTIVES.md` Gate 1 and
  `docs/how-to/pipeline/audit.md`; `README.md` and the routers give the order
  without repeating that sentence.
- Two sweeps of the tracked instructional documents (everything outside
  `docs/implementation-plans/`, `docs/history/`, `docs/evidence/`,
  `docs/concepts/`, the root `plan-seeds/`, `handoffs/`, `.tmp/` and
  `.plan-tool/`). A
  vocabulary sweep for text that recommends or defaults detail iteration found
  the `RUNBOOK.md` closing line, which contradicted the same file's "Detail with
  iteration" section and `DIRECTIVES.md`. A command-sequence sweep over fenced
  blocks, for a `plan-tool detail` command that follows a `plan-tool create` with
  no `plan-tool completeness-audit` between, returned 24 hits: two real gaps in
  `docs/how-to/roadmap.md` (the command list and section 8), eleven
  `Iterate:`/`Iteration:` recipes in `BACKLOG.md`, and eleven independent
  examples (see below).

**Provenance.** `common-workflows.md` already read correctly at the `9c10d74ca`
snapshot (2026-10-21), so that half of the report is stale from the earliest
retained history. At the snapshot the routers' recipe row ran `detail`
(one-shot) before any audit, and their iteration paragraph called `--iterate`
"on by default for `create`/`detail`"; `31fdf2f22` ("correct skill audit,
recovery and reconciliation recipes", 2026-10-21) reordered the row around the
two gates and replaced the paragraph. The entry outlived that repair as far as
the routers go.

**Filed separately, not fixed here.** The eleven `BACKLOG.md` recipes (queue
records, edited when each entry is picked up) are a `BUG_BACKLOG.md` entry; the
stale 300-second iteration budget in `RUNBOOK.md` was filed too and fixed
afterwards in `9f8c67e9b`.

**Left as is, deliberately.**

- The shorthand `create → detail → audit → run` (or `→ run steps 1–N`) in
  `docs/how-to/pipeline/run.md`, `RUNBOOK.md`, `MISSION.md`,
  `experiments/contract-trace-audit/LESSONS.md` and `CLAUDE.md` (`AGENTS.md` is a
  symlink to it) collapses the two audit gates into one word. It does not
  contradict the gates, and edits to `CLAUDE.md` need architect-tier review.
- Independent examples that list `create` and `detail` side by side without
  being a stage sequence: the headless-syntax blocks in the three routers and in
  `docs/OPERATIONS.md` (both say so), `integrations/shared/DIRECTIVES.md` (which
  now says so too) and the tracked copy under `.claude/skills/plan-tool/` (a
  copy that lags `integrations/` elsewhere and is not refreshed here), the
  opt-in loop examples in
  `RUNBOOK.md`'s "Create with iteration" and "Detail with iteration" sections,
  and the prompt-mode comparison in `docs/explanations/prompt-ab-testing.md`.
- As of 2026-11-13, `docs/explanations/lessons-learned.md` lists `run` among the
  commands that support `--iterate`; `run` accepts the flag and ignores it. It is
  outside this entry's class (a `run` flag, not gate order or the `detail`
  default).
- Restructuring the first-task path belongs to onboarding #510, open on
  2026-11-13.

**Re-open only when** a quoted passage in a first-task path, a router or a
how-to contradicts `DIRECTIVES.md`'s gate order or the parser's iteration
defaults.

## Closed owner decisions, 2026-11-14

Three entries closed during the 2026-11-14 backlog reconciliation. Each
record keeps the decision and its re-open condition.

### #280 — Saved-audit lookup duplication between `completeness_phases.py` and `data_contract_cmd.py`

Closed as no action. The entry's one remaining candidate compared a saved-audit
sidecar load and "newest current, qualified audit" scan in
`cli/completeness_phases.py` against `cli/data_contract_cmd.py`
(`_load_payloads`, `_newest_saved_completeness_with_contract_payload`). At HEAD
`completeness_phases.py` has no such lookup, so there is no second copy to
consolidate; the other `is_current_final_qualified` consumers (`gate_status.py`,
`cli/review_cmd.py`) read a different projection. **Re-open only when** a second
module grows its own scan for the newest qualified saved audit.

### #284 — Roadmap escalation/impact consolidation candidates

Closed. Three of the four candidates (a shared runner lifecycle, closure
traversal, and `RoadmapImpactSnapshot`'s parallel tuples) named
`plan_tool/roadmap_impact_run.py` and `RoadmapImpactSnapshot`, which no longer
exist. The fourth, a shared strict-JSON decoder, stays separate. An AST pass
that normalizes docstrings, names, and annotations finds five
`_reject_duplicate_keys` definitions (`concept_tree.py`,
`roadmap_candidate.py`, `roadmap_candidate_run.py`,
`roadmap_candidate_review.py`, `roadmap_revision.py`) with the same loop and
five different bodies: each raises its own typed error with its own message
(`InvalidConceptTreeError`, `CandidateDeltaError`,
`CandidateProposalResponseError`, `CandidateQuestionResponseError`,
`RevisionContractError`), and callers and tests pin those types. A shared
helper would need the error type and message as parameters, which saves about
six lines per site and adds an import edge. **Re-open only when** a sixth
decoder is added or the duplicate-key policy changes in one of the five.

### #310 — Whether `roadmap_reader_guard` should cover the recorded-brief path

Closed as moot. The entry's subject was the impact-snapshot capture path
reading the recorded brief while a reader guard was held. That path no longer
exists: `roadmap_reader_guard` and `read_brief_text` have no production caller
(tests only). The two helpers were deleted on 2026-11-14, on the owner's instruction, together with
`_acquire_reader_lock` and `bootstrap_roadmap_reader_lock`, the same dead
family, and the tests that exercised them. **Re-open only when** a read-only
roadmap view needs to hold a lock against a concurrent writer; the writer
guard (`roadmap_writer_guard`) is unchanged.

## Discarded entries, 2026-11-14

Removed from `BACKLOG.md` after a value review against `MISSION.md` and the anti-creep rules in `CLAUDE.md`. Each row keeps the id citable and states why the entry is not worth its cost; none is scheduled. Re-file only with the new evidence the reason names or implies, as a fresh entry with its own scope contract. Deliberately not carried: the full entry text, which `git log -S` on the id recovers.

| ID | Title | Reason |
| --- | --- | --- |
| #36 | Does per-plan `lessons.md` add value? | The opt-in still exists (`create.py:1717`, default off), but there are zero `plan-details/*/lessons.md` files in this repo. Nobody uses it, so there is nothing to investigate. If anything, file a one-line removal of the wizard prompt. |
| #43 | Synthesis output caching across reruns | No measured cost. Within-run memo and checkpoints already cover resume, and a cross-run cache of stochastic synthesis silently defeats the usual reason to rerun (a fresh sample) while adding a stale-cache hazard. |
| #49 | `detail` authoring wizard | An untriaged TTY UX feature for a pipeline driven almost entirely by headless sessions (including Loom). It adds a draft-vs-edit merge model to the seven-section write gate for no cited need. |
| #54 | Lesson 7 audit on `_iterate_reconcile_loop` wiring | Rests on "may not be tested". No failure observed and no principle named. |
| #55 | mtime short-circuit for content hash | No profile exists, and the premise is unsound: mtime can be preserved (checkout, `touch -r`, tools that copy mtime) or fall within the same coarse timestamp tick. Drift detection is P3-critical, so trading correctness for an unmeasured speedup is backwards. |
| #74 | Speed up loops: remaining caching + parallelism levers | Everything cheap has shipped or been measured not worth doing. The only open lever is in-process per-step parallelism, which CLAUDE.md discourages. A future speed need should come back as a fresh, measured entry. Shipped slices that code and tests still cite as #74: the stream-json batch form with usage and cache capture, a cache-reusable static prompt prefix (lever A1), and the dedup lever; only the heavy slice (direct-API caching, per-step parallelism) is discarded. |
| #82 | Deferred: structural-observation ledger | Its own reason (most #79 duplicate claims were false) argues against ever building it. The trigger is vague. |
| #90 | `--worktree` convenience on run/detail | Pure sugar over a working two-command flow, with real risk surface (resolving the wrong tree's manifest, silent re-provisioning) and no demand cited since July. |
| #97 | Per-step embed budget (remaining half) | The symbol-aware excerpt leaf has shipped to all five surfaces; only the cross-file budget remains, with no observed failure behind it. Audit and detail surfaces mandate Read/Grep, and the #95 advisory already flags clipping. It should not occupy the T3 band. |
| #108 | Durable per-step run marker for structural gates | It closes a narrow SIGKILL window whose stated consequence is "soft mis-attribution" of one lesson. A new schema field, run wiring and three gate refinements are disproportionate to that harm. |
| #124 | Floor-breaker: shorter or async `claude` calls | Its substrate #88 is itself marked mostly superseded. Async detached execution would add exactly the invoker/rate-limit complexity the architecture rules warn against, and splitting calls costs output quality. If one specific call is measured overrunning a real cap, file a per-verb entry for it. |
| #126 | Concept publication-transaction machinery | The entry's own rationale settles it: git is the journal, fingerprints already trigger re-derivation, and this is a 13-step transaction manager for a single-user CLI. The revisit trigger has not fired in four months. |
| #127 | Concept authoring-boundary validation residue | Its "revisit if malformed envelopes show up" trigger has not fired since 2026-07-13. The concept lane is dormant. |
| #128 | Concept non-delivery ledger + lifecycle accounting | A 27-step second decision store. The entry itself says the bureaucracy grows faster than the failures it prevents, and existing nets (`concept-coverage`, decision fields) cover the case. |
| #129 | Deferred program-scale decomposition observations | A placeholder with no work in it. The verdict layer is already retired, and "name a consumer first" applies to any new entry anyway. |
| #130 | On-demand sub-concept drill | The entry admits the flat MVP fully closes the founding incident, and the drill would bring back a producer that was cut on purpose. No need has been observed. |
| #131 | Migrate legacy full-tree `concepts.json` | Checked: the dual-shape `record_kind` branch is still in `concept_tree.py`. Retiring it is only worth doing as part of a wider decision on whether the concept subsystem stays at all, which nothing has asked for. |
| #132 | Dismiss verb for wrong pending deferral | The entry says this is not a correctness need: an unconfirmed deferral is inert. |
| #133 | Speed up per-step purity check | `--purity` is off by default and the pass has not produced a finding in 90 reports, so speeding it up optimizes something #210 may cut. #210 decides whether the pass survives; if it does, re-file with a profile. |
| #134 | E2E founding-incident test (detail→status) | A cheap hermetic test, but it protects a dormant feature whose producer and consumer already agree on the record shape. If the concept lane is ever reactivated, write it then as a 30-minute direct test. |
| #136 | Generalize rate-limit helper family (shell/launcher) | Contradicts #79's measured do-not-merge list, which says the `_can_prompt_on_rate_limit` duplication *is* the injection seam. The remaining two helpers are coupled to deliberately distinct per-lane ContextVars. Consolidation would put backend-switch scoping at risk with no bug to fix. |
| #139 | "Implementation-time" finding class | Largely superseded by the shipped bare/detail stage split: bare-stage completeness findings at medium don't block, the `bare_mechanism_findings` advisory exists, and detail-owned remedies are already routed to `detail`. The proposed classifier ("only a real run reproduces") is a semantic proxy that will have a high false-positive rate. |
| #155 | Harden purity-cache below-floor heuristic edges | A low-yield heuristic tail with no corruption risk, on a pass (#210) that has never produced a finding. If #210 keeps the pass, revisit only the success-gate end anchor. |
| #184 | Configurable repository seed directory | The original motivation (repo layout disagreed with the hardcoded path) went away when the nested default shipped. What's left is a speculative config knob ("a consuming repository can still need…"), and CLAUDE.md prefers a literal over a knob. |
| #187 | Shorter carved-seed filenames | Cosmetic, and the entry itself says nothing consumes the filename. |
| #191 | Conceptual audit treats `done` steps as context | The prompt half shipped and the enforcement half is #192, so this entry only restates. |
| #197 | Contradiction gate: fence denylist vs injected content | A vocabulary denylist that has to handle negation is exactly the high-false-positive proxy the "kill, not tune" rule names. Its observed trigger (a lesson contradicting a fence) goes away once #195's reshape stops default injection. |
| #199 | Git-native archive (delete instead of move) | Trades a cosmetic problem (greps hit `archive/`, which an exclude glob fixes) for a migration, a retrieval verb, a citation sweep and a silent loss of discoverability. Many live docs cite archive paths. The `docs/history` design depends on those artifacts staying readable. |
| #207 | Concept-naming discontinuity detector (bundle) | n=1 (the depth/grade incident, which was caught and swept anyway). Deciding "which noun names a shipped surface" is itself semantic, the validation-feature trap CLAUDE.md says to treat as guilty until it names an observable. Its own stop rule is likely to fire. |
| #217 | Roadmap rejected-response evidence (consolidated) | Provenance only; BUG_BACKLOG owns the remaining work. |
| #234 | Last-attempt test-command cost bound | Everything with value shipped. The remainder ("evaluate a cost bound") names no decision that would use the answer. |
| #241 | Narrow bare-plan audit prompt to correctness only | The premise conflicts with the current bare-gate policy. CLAUDE.md says bare-stage `plan-completeness` findings are read and corrected by hand-edit before `detail`, so they aren't "generated to be shelved", and the prompt already narrows detail-level findings. Suppressing them would remove input that the bare gate is designed to act on. |
| #246 | Measure private-vs-public helper splits elsewhere | One case, and nothing consumes the measurement. The entry's own guardrail ("no visibility change without a named caller") means the default answer is no action. Fix visibility per site when a caller needs it. |
| #256 | Defer automatic analogous-site sweeps | A "do not build" decision, gated on a labelled corpus nobody is building. Manual Check 0 is the standing rule in CLAUDE.md. |
| #260 | Parked: stage-bar reporting polish | A placeholder whose own reopen trigger says "file a small direct defect instead", plus a commented-out superseded block that breaks the forward-looking-docs rule. |
| #263 | scope-out seed lacks commit/report provenance | The entry admits nothing downstream reads the block. One instance, already fixed by hand. The blame/attribution logic costs more than the audit trail is worth. |
| #266 | Page `roadmap --view` through a pager | Piping to `less` already solves it. A TTY-detecting pager wrapper plus a `--no-pager` flag is permanent test surface for a convenience. |
| #273 | Shared advisory-lock-release leaf | Two ~6-line release functions in different modules. Merging them means a new leaf and new import edges for no correctness gain, which is the low-value consolidation CLAUDE.md warns about. The allowlist rationale has already been corrected, so leave the pair allowlisted. |
| #277 | `roadmap_writer_guard` maybe redundant with repo lock | Even the entry says "not a confirmed bug". The guard has 10 call sites, carries the `writer_token` that the reuse/validate paths depend on, and is the finer lock that parked #353 (artifact contention) would want. Removing defense-in-depth to save "machinery" is risk with no payoff. |
| #296 | Bound `render_detail_prompt`'s `prior_body_block` | Speculative: the advisory already names the block, truncation is ruled out by design, and the entry's own stop rule says close if no merge has approached `warn`. No such incident is cited. |
| #304 | Evaluate shared feedback-operation lifecycle | Not work: it's a standing rule ("don't extract without a concrete cross-route change") written as an entry. The anti-creep rule already covers it. |
| #311 | `load_pending_generation` decodes payloads for existence checks | Item 1 is done and item 2 is moot. Item 3 is a micro-efficiency with no measured cost, and its safe fix needs a shape change or a second parser, which is the drift the entry itself warns about. |
| #314 | Risk-profile advisory: declaration-authority guardrail? | No observed failure is cited, and the default outcome is "retain advisory, no change". This is an investigation no decision is waiting on. |
| #316 | Shared confidence-tag rendering helper | Cosmetic consistency across ~25 sites in 12 files whose grammars differ by surface (the original review declined a single formatter for that reason). No correctness stake, and it would churn a lot of pinned tests. |
| #319 | Naming discontinuity, reconcile lane | Depends entirely on #207, which is discarded. |
| #320 | Concept input/output alignment check | No observed instance, unknown effort, and every design question is open. The conceptual audit already judges interface contracts between steps. |
| #330 | Revalidate persisted admission before resumed call | The only benefit is saving one model call on corrupt state the materialization boundary already rejects. Not worth a fixture. |
| #335 | Audit lens for unjustified shared semantic commitments | A semantic-judgment lens with no cited incident, added to the convergence-sensitive audit loop. It is the "validate a semantic property" class CLAUDE.md says to kill, and its own stop rule anticipates low precision. plan-audit.md's proportionality rules already cover the intent. |
| #339 | Open questions on stage-loop "stopped" emission (Ctrl-C gap, post-write vocabulary) | Both questions concern a stderr status line. On Ctrl-C the operator already knows the run stopped. The `BaseException`-from-callback case is hypothetical for a caller-supplied callback. The "published but run not confirmed" wording is cosmetic. The delivered `_stage_run_guard` closed the real issue. |
| #340 | Bounded-truncate-with-digest idiom | Seven sites that agree only on policy (character vs byte budget, digest length, inline marker vs returned boolean). The entry itself shows that a naive merge would reintroduce a fixed crash (the lone-surrogate encode). Merging would be harmful, not just unhelpful. |
| #341 | Shared `"stage N (name)"` format string | Four literals, each pinned by an exact-text test, with no drift observed. The churn is worth more than the dedup. |
| #343 | Status-emission helper family's repeated patterns | Both patterns are "currently safe in practice", and the fix restructures four signatures for terminal status lines. If #349 is ever pursued, it replaces this family anyway. |
| #345 | Test recorder fixture for `TestRoadmapStageStatus` | Test boilerplate hygiene with no defect behind it. |
| #346 | "Stopped" emission relies on per-branch discipline | No live bug. The current branch is verified correct, and the concern is a hypothetical future branch. The durable run log, not the stderr status line, is the record. |
| #352 | Phase-timing scaffold repeated in `create.py` | The sites differ in outcome classification and parameters, there is no bug, and it would need a context-manager design (the entry even routes it to plan-tool). This is the "validated-but-unnecessary" pattern. |
| #357 | Judged bare-gap classifier on restated findings | It adds a second model judgement on whether a finding is "real", which is a semantic property with no binary observable. The deterministic `classify_bare_mechanism_advisory` already exists, and no failure is cited that it missed and this would catch. Validity is local, necessity is global, and nothing here shows the need. |
| #358 | Compound condition computed twice | True (`create.py:3859`, `:3863`), but it is a two-line drive-by, not a backlog entry. As an entry it adds noise to triage. |
| #359 | Four more path-display idioms (unverified) | By its own analysis, none of the four idioms may be merged with each other or into the existing helpers. That leaves no mergeable set, only resemblance. |
| #361 | Consolidate candidate failure-diagnostics finalization (remainder) | The part that mattered (core fallback metadata under a second interrupt) is done (`3590939e`). What remains is deduplication of a block that is currently correct, justified by "could drift". |
| #364 | Version-contract drift in completeness + registry fingerprint | `tests/test_data_contract.py` already pins the registry to the schema constants. The completeness drift channel reads plan-tool's own DATA_CONTRACT.md, so it only self-hosts. Wiring it in adds a second detector for drift CI already catches, with no consumer. |
| #366 | Survey aidlc-workflows multi-harness patterns | No decision consumes the result, and it is "untriaged; may close with no action" by its own text. |
| #369 | Inventory other `apply_finding` authorities | No decision consumes the inventory. The #376 it is "separate from" is gone, and lessons line 1181 already enumerates the four serial callers. It is an investigation without a consumer. |
| #382 | Inspectable evidence-support provenance on findings | Speculative. It asks "which decisions would improve", with no observed misjudgement behind it. It also edges toward persisting a model self-score as if it were proof, which the entry itself flags as a risk. |
| #407 | Verify/resolve JSON-value-projection duplication | The divergences already found (mapping-key sorting, coercion vs refusal) are real behavioral differences, and some of these functions feed canonical identity hashes, so merging could change persisted digests. High risk, no bug. |
| #408 | Git subprocess per artifact on `--compare` | At most 4 subprocesses per interactive call, and the short-circuit shifts the documented "Git owns identical-or-not" boundary. A micro-optimization off the hot path. |
| #412 | Relation matching O(n·m) | Unmeasured, and roadmap relation counts are in the tens to hundreds, so quadratic matching is negligible. The entry itself says not to act on the finding alone. |
| #413 | Artifact bytes SHA-256'd up to 3× | The entry admits it's microseconds on KB-scale markdown. Threading digests through the shapes costs more than it saves. |
| #414 | Each comparison output mode computes more than it uses | Unmeasured, and the inputs are KB-scale. Making it lazy would break the single shared read path that keeps the three modes consistent, which is a correctness property worth keeping. |
| #415 | `CandidatePredecessorDiff` alias | Cosmetic rename across ~18 sites in the fragile candidate module. The drift risk is hypothetical: a `TypeAlias` can't grow fields without someone deliberately replacing it. |
| #418 | `before_digest`/`after_digest` never consumed | They're part of the persisted candidate `predecessor_diff` shape and back an existing tamper-refusal test, so "unused" is false at the persistence layer. Removing them is a format change with no payoff. |
| #420 | `raw_evidence_identity` stored though derived | Single construction site on a frozen model. The entry calls it "a simplification, not a fix", and a computed field adds serialization risk. |
| #422 | Ordering-row card carve-out is a name check | The entry itself says not to build this until a second all-relation-fields row type exists. |
| #424 | Record create-time plan-altitude re-cut evidence | Typed telemetry with no consumer, from n=1. The directive's detector-miss record can be a dated note in the evidence doc, not a new persisted fact. |
| #434 | Should candidate decision commands write run logs? | The candidate lifecycle records already are the authority for decisions, so a run-log event duplicates them and adds a versioned contract. |
| #435 | Model-judged narrative review for candidates | A semantic property with no binary observable (the CLAUDE.md "kill" class). One case, caught by a person. Four audit rounds already showed the shape spirals. |
| #436 | Labeled prose-correction cards in comparison | Pure presentation. Approval time already shows the exact before and after, so nothing is hidden. |
| #465 | Two absent stack-callout tests (self-labelled low value) | Self-admitted optional and low value. Display-only feature, structural tests already exist, and the new ones would be brittle output pins. |
| #471 | Intern relation node identities in candidate context | The ceiling was raised (PR #58). The byte saving alone doesn't justify a new model-facing representation with readability risk. |
| #476 | Bulk-convert `Approach:` to `Route:` with presence test | Backlog-format churn plus a new guard test. Label-on-touch already works. Pruning delivered, closed and discarded entries comes first; relabelling entries that are then deleted would be wasted work. |
| #493 | Supply shared context to authoring/audits | #492 decided no-action for this entry. A gated entry kept "in case" is clutter; re-file on a demonstrated delivery need. |
| #494 | Show unresolved prerequisites in `status` | #492 decided no-action. Same reasoning as #493. |
| #498 | Plan body should point to `plan-tool status` | The gain is one wording change. The cost is five pinned test files, the `annotate.md` placeholder check, and permanent recognition of both pointer strings. That tax outweighs a pointer that is read mostly by tools. |
| #506 | Total budget across a multi-round audit loop | plan-tool doesn't own the multi-round loop; the external driver does, and it already has the shipped per-invocation `run_end.usage` totals (#505) to sum and stop on. Principle `none`. |
| #516 | Which seed files directory-wide annotate includes | The entry says it is not evidence of a failure, and explicit file paths are unaffected. |

## Merged entries, 2026-11-14

Each entry below was folded into the entry named, which now carries its scope in an "Absorbs" bullet (the `--compare` items sit in a `BUG_BACKLOG.md` entry). The merged id stays citable here; the full text is recoverable with `git log -S` on the id.

| ID | Folded into | What carried over |
| --- | --- | --- |
| #425 | #518 | The routers point at the shared model-selection rule. Not covered: a repository with no skill installed, which was #425's motivating incident. |
| #388 | #518 | Router-table drift handled with the skill split; the generated-template versus drift-lint decision is settled there. |
| #88 | #455 | Re-evaluate post-call gates against the tree on disk instead of re-spending the `run` call. Memoizing the call's output is dropped as the wrong frame. |
| #151 | #210 | Over-requested purity-path grounding is decided only after #210 decides keep or cut; a narrow purity-only mode applies only if the pass is kept. |
| #379 | #378 | The closing rule with its safeguards: verify first, citation sweep, surface instead of changing a parked or decision-needed entry, tracker-only commit, and the #337 and #315 incidents. |
| #360 | #355 | The duplicate interruption-log write is removed if #355's `RunLogWriter` best-effort contract covers it, otherwise recorded there as accepted; no standalone helper. |
| #342 | #349 | One design question: whether the status callback and the run logger are one seam. |
| #300 | #79 | The two heading regexes migrate with the JSON slice; `_REDIRECT_HEADING_RE` keeps its blank-line anchoring. |
| #257, #258 | #259 | One change renders the existing `depends_on_notes` entry in grounding, the Jira story body and the detail prompt. |
| #410, #416, #421 | `--compare` entry in `BUG_BACKLOG.md` | A `default=` parameter on `_option_occurrences`, a fail-closed type check in `design_row_collections`, and one parametrized test of the companion-mode rejection list. |
| #427 | #458 | Its 212 cited / 95 defined / 117 undefined test-name counts become #458's false-positive corpus. The archived plan's detail files are not rewritten. |
| #485 | #490 | A deliberate departure from a roadmap row is a disposition of kind `departure`; the authority question is assigned to #490 to settle. |
