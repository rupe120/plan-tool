# Roadmap capability and evidence backlog arc

## File intent

This file is the execution guide for roadmap-level capability and evidence
work, from durable artifact facts through the bounded consumers that rely on
them.

## Details

It records the dependency order for hosting, technology research, revision
history, immutable evidence, stage confidence, lifecycle progress, and the
next framework lens; it also states the ownership boundaries between storage,
receipts, stages, and derived plans.

## Choose this arc when

The next value comes from making roadmap artifacts more grounded, testable, or
durable. This route keeps product-shape decisions and evidence persistence
separate even when they touch the same roadmap subsystem.

For the transition from accepted artifacts to executable plans, use the bounded
[roadmap-to-plan subroute](#roadmap-to-plan-subroute) below. Its anchor is
BACKLOG #492; it does not reopen the completed roadmap-stage implementations.

## Delivery cadence

Commit each resolved backlog item before starting the next one. Plan-tool work
uses committed green-step checkpoints; direct changes include their regression
coverage and backlog retirement in one bounded commit.
Do not push automatically; push only when the user explicitly requests it.

## Real-world evidence source

Integration (see `docs/history/roadmap-evidence-v1-retirement.md`'s project/roadmap roster)
is the one known real production consumer of the `roadmap` verb — real
domain/constraints/components artifacts under active revision, not a
synthetic fixture. Real usage keeps surfacing what synthetic tests don't: the
failed-revision case that drove step 0's bounded stage-feedback rewrite, the
still-open `domain:fb-plan-tool-lifecycle-responsibilities` / `row-structure`
receipt step 3 gates on, and the 2026-08-26 version-1-schema escalation write
that is now an archive-safe Integration-local won't-do. `BACKLOG.md` #313 remains
conditional on fresh-process reproduction, another project, or supported-route
provenance. A finding from Integration routes to whichever step or backlog file owns
the affected subsystem — this arc, or `BUG_BACKLOG.md`/`BACKLOG.md` directly
as a fresh item when the subsystem is `archive/backlog-arc-structural-rewrite-safety.md`'s
completed, archived scope — never to a separate "vetting" arc: continuous
real usage has no terminal exit condition, so tracking it as its own arc
would never converge. This section is a pointer, not a new backlog owner.

Delivery of an external application built on the `roadmap` verb is tracked in
that application's own repository; a `plan-tool` finding it surfaces is filed
here or in the bug files like any other. (The runbook that once routed it was
removed 2026-11-05.)

On 2026-08-31, Integration's `project-workspace-membership-proof` run supplied a
separate, direct operator-workflow finding: the long-running `roadmap` command
emitted no live terminal progress while it successfully completed four Codex
stages and corrected one validation retry. #337 now records the bounded result
in [the stage-lifecycle plan](../archive/2-roadmap-stage-lifecycle-output.md):
concise, ordered stderr facts identify the accepted range and confirmed roadmap
transitions. A quiet period after a transition remains ambiguous; the direct
stderr scope is not a liveness claim and grants neither backend-output
streaming, job control, nor a general observability surface.

The same representative Integration review supplied the next roadmap-capability
finding. A reviewer described one natural membership-capability reframing, but
the current feedback mechanism requires that thought to be pre-split into
local row operations: one feedback item allows at most one material operation,
row edits preserve every declared relation, and publication selects one
artifact. The existing impact reader can deterministically traverse already
declared relations, but it does not interpret reviewer prose or create an
immutable candidate version. Closed `BACKLOG.md` #328 records the resulting
capability: one conversational feedback message is immutable reviewer input;
model output can create an inert complete candidate, while deterministic diff,
gates, and exact accepted-head promotion remain authority. This is direct
real-use evidence for a new route, not permission to loosen or repurpose the
bounded same-artifact route.

On 2026-09-04, the same `project-workspace-membership-proof` feedback exposed
the next boundary in that route. After the candidate-delta wire contract was
corrected, its diagnostic normalized delta reached `relation-authority`: it
removes `entity-project-selection` and makes the capsule-authorized
membership-scope relation changes that follow. The delivered candidate-policy
lifecycle now carries an otherwise valid, exact policy impact through the
existing selected-feedback → candidate-question → answer-bound replacement →
review-seal path. It adds no relation-specific feedback, confirmation command,
or authority escape. The materializer keeps malformed, ungrounded, broadened,
and out-of-lineage changes as hard refusals that publish no candidate. Its
review-required candidates and gate-clean candidates remain inert until exact
review-seal promotion; review-required replacements reuse their admitted
initial capsule and their recomputed impact must be contained by the initial
disclosure. `ROADMAP_FORMAT.md` owns the complete candidate-policy lifecycle
contract.

On 2026-09-09, Integration changed how its brief is produced, and that supplied the
next three capability findings plus one defect. Integration now authors its concept
brief from an AI-DLC Ideation run rather than by hand, which makes a structured
upstream producer the normal case rather than a hypothetical one. Three
consequences reach this arc. Stage 2 requires one hosting row per facet and
one disposition per quality attribute and guesses when the brief is silent,
while those facts exist in an upstream `constraint-register.md` with no route
to the stage except being pasted into the brief (#383). Questions the upstream
engine already asked and a human already answered are re-derived here and land
as `pending` guesses (#384). And a control plane presenting `plan-tool`
alongside another engine has this engine's run log but no state projection to
render between runs (#385). The brief record now binds its path and decoded-text
baseline: changed or legacy content refuses before roadmap work until an
operator deliberately accepts current text at the same path. Acceptance replaces
only that baseline; it does not re-ground artifacts, feedback, or seeds. #383
and #384 widen what a stage may *read*; they grant no new write authority, and
the gates remain the only publication authority. The delivered stage-run
source-admission boundary converges under independent review on 2026-09-14.
The closed route-local brief-drift record closes the three non-stage policies: analysis creation and immutable
root enrollment refuse changed or legacy briefs redacted with status `1`, impact
inspection remains log-free with successful no-route status `0`, and structural
rewrite preserves evaluator admission and guarded recovery before its redacted
refusal. #367 closes the separate stage-run operator-intent decision:
`--confirm-brief-rebind` is required with the recorded `--from-existing` path
to accept changed or legacy content, while matching and initial runs retain
ordinary behavior and no non-stage route receives the flag.

### Canonical Plan-tool delivery gate

Before testing any session-made `plan-tool` update against Integration, complete that
update in its originating checkout, commit its verification, **push it to
`origin`, and pull it into the canonical checkout** at
`<installed-plan-tool-root>` — resolve it through
[Which plan-tool is running?](../../../CONTRIBUTING.md#which-plan-tool-is-running),
the directory the installed
`plan-tool` is an editable install of, and therefore the only tree whose
contents actually run. Every clone tracks `origin/main`, so this is normally a
fast-forward pull rather than a branch merge. This applies to every session
checkout outside that path, including a temporary clone used for planning,
audit, implementation, or direct fixes. A clone-local change is not eligible
for a Integration preflight, receipt creation, structural rewrite, or other real
project test. Run the Integration command from the canonical checkout only after that
pull, and record the pulled commit with the resulting evidence. This gate does
not authorize an automatic push or pull; the user authorizes those actions
separately.

The same 2026-08-26 incident also surfaced `BACKLOG.md` #315. Its canonical
delivery record is now
[the confirmed-feedback-reopen plan](../archive/2-roadmap-confirmed-feedback-reopen.md):
one explicitly confirmed operator reopen for a safe selected `awaiting-review`
row, recorded as a redacted transition with a fresh next-receipt identity. Its
safety checks protect the write; confirmation, not an artifact category, is
authority for the unavailable-evidence determination. The superseded
`roadmap-feedback-evidence-reopen` plan described an eventual response-history
and evidence-recovery capability and remains unauthorized. #315's delivered
proof informs #242's future redesign but neither redesigns nor resolves #242.

## Ordered route

**Completed (2026-09-01) — #337.**
[the stage-lifecycle plan](../archive/2-roadmap-stage-lifecycle-output.md)
delivers the smallest stderr transition-status contract on the normal stage-run
path: accepted stage range, confirmed stage start, validation retry, completed
stage write, and normal terminal outcome. It reports the last confirmed
transition only; a quiet period remains ambiguous and does not show liveness.
The delivered contract keeps model prompts/responses captured and leaves JSON
output, artifact writes, stage gates, retry policy, and cancellation behavior
unchanged. Its deterministic injected-stage seam does not justify a heartbeat,
live dashboard, or cross-command progress framework.

**Completed — #328.**
[the immutable-candidate-versions plan](../archive/2-roadmap-immutable-candidate-versions.md)
delivers the smallest candidate-version happy path from the representative Integration
case. Its feedback message is not an instruction to mutate a named row; it
produces an inert complete candidate, then deterministic diff questions and
reviewer answers produce a replacement candidate. Only an approved immutable
review seal's exact bound candidate may become the accepted head. The bounded
feedback, local revision, and structural-rewrite routes remain unversioned; after
explicit enrollment, those in-place writers refuse rather than bypass the
accepted head. #329 and #330 retain persistence-integrity hardening outside
this proof.

**Delivered (2026-09-04) — Candidate policy review.**
[the candidate-policy-review plan](../archive/2-roadmap-candidate-policy-review.md)
extends the completed candidate route without creating another user-feedback
surface. A candidate whose only remaining concern is a deterministic, bounded
policy impact carries its exact initial disclosure into the existing review
inventory. Its answer-bound replacement recomputes its impact and must either
eliminate it or prove multiplicity-preserving containment within that
disclosure while reusing the initial admitted capsule; every broader, new, or
unauthorized impact refuses. The accepted head remains unchanged until the
existing review-seal promotion. `ROADMAP_FORMAT.md` carries the lifecycle
detail.

0. **Shipped (2026-08-20).** The bounded stage-feedback route replaces
   whole-artifact regeneration with a closed JSON operation set and a
   deterministic merge. Its integration-scale regression coverage proves untargeted
   content stays outside the model reply; the published contract retains the
   feedback-free `completed-no-change` re-gate, `invalid` gate failures, the
   writer-owned baseline, and selector-bounded authority. `ea6b41fe` supplies
   a block-scalar reviewer stub and a targeted parser recovery hint for the
   independent hand-authored raw-YAML scalar failure; it does not change the
   canonical renderer's supported scalar styles.
   [the feedback-revision architecture analysis](analysis/roadmap-feedback-revision-architecture.md)
   remains the traced failure and design record. The reader-only
   `roadmap-canonical-source-identity` work is complete. The 2026-08-27 Integration
   receipt preflight has run and leaves #242 paused; do not rerun it without a
   newly authorized recovery route.
   (The hand-edit-to-feedback bridge once tracked as #298 was retired
   2026-08-27 for lack of real hand-edit evidence — see
   `docs/history/backlog-decisions.md`.)
1. **Done (2026-08-19).** `roadmap-hosting-and-stores` shipped —
   status `completed`, progress 4/4. The existing constraints and components
   artifacts carry explicit hosting and store facts; do not reopen for
   reuse-only or view/relation-expansion cleanup (see the plan's own review
   closure).
2. **Done (2026-08-25).** #244 (`research-chosen-technology`) shipped —
   status `completed`, 4/4 steps. `create`'s web research now consumes a
   plan's recorded hosting/store rows and their disclosure decisions, and
   refuses to proceed when it cannot ground a technology and no operator
   description exists.
3. **Paused.** #242 (retain a removed row's content, closed feedback, and
   the decision behind a removal) has a bare plan authored at
   `docs/implementation-plans/2-roadmap-revision-retention.md`. Four bare-plan
   completeness-audit rounds landed (finding count 12 → 7 → 6 → 5, genuinely
   converging but still coverage-`unconfirmed`/budget-limited every round);
   paused after round 4 on explicit user direction. Round 4 flagged a design
   gap — the plan's render-time closed-row sort collides with three
   already-completed plans' shared render-canonicality checks (structural
   revision, incremental/local revision, and the impact-snapshot leaf they
   both call) — which the plan does **not** resolve itself. The reader-only
   `roadmap-canonical-source-identity` plan resolves that gap and is complete
   (4/4 steps). It preserves raw-only version-1 capture, baseline-backed
   version-2 presentation admission, guarded receipt observation,
   order-independent mixed-version views, exact-raw version-1 analysis
   creation, and a structural publisher allowance limited to its exact active
   pending generation. The saved 2026-08-19 reports cover its superseded
   seven-step baseline-publication shape and are historical, not current audit
   evidence.

   The 2026-08-27 Integration receipt preflight for
   `domain:fb-plan-tool-lifecycle-responsibilities` with `row-structure`
   reused receipt `ce95b880271698ad9feabcb41a70d5f62dfcd6acd754b1770e2edb0837c47e11`
   and failed closed at snapshot admission: the committed 2026-08-26 feedback
   cycle changed the constraints and components source projections without
   updating their existing baselines. It published no impact analysis and
   admitted no structural retry. The same day's explicit Codex-configured
   `roadmap integration --enroll-baselines` attempt correctly refused: enrollment
   bootstraps only a wholly unenrolled prefix and never replaces an admitted
   baseline. Every current re-entry and evidence route first admits the source
   against that baseline, so neither a stage run, local revision, impact
   analysis, nor structural writer can repair this state or reach a model call.
   Keep #242 paused. **Deferred 2026-08-27 (user-confirmed):** the bare
   `roadmap-source-baseline-recovery` proposal does not proceed. Its latest
   audit showed that a reusable route would need confirmation binding, writer
   ownership, derived-seed source binding, and a delivery/re-evaluation
   boundary — a recovery subsystem, not the smallest proof for this one 2:3
   Integration stop. Do not run a recovery command or re-evaluate the unchanged
   receipt. Re-enter only if a second independently justified source-baseline
   recovery need appears, or the user explicitly requests a bounded one-time
   Integration 2:3 remedy. Either case begins with a fresh bare plan grounded in the
   then-current code and evidence; it does not revive this deferred proposal.
   The #315 proof remains a retention-design input, not retained response
   history or #242 delivery; #242 may receive a fresh bare-plan audit only
   after a newly authorized route admits current evidence.
4. **Done (2026-08-15).** `roadmap-immutable-evidence-storage` ships the
   reduced opaque-evidence primitive independently of the revision
   architecture. It owns sealed `ESCALATIONS` and `IMPACT_ANALYSES`
   namespaces, exclusive final-name publication, deterministic reads, and
   the documented file and directory synchronization boundary. The old
   0-of-2 bare audit predates implementation; do not reopen it to elaborate a
   hardened storage protocol. The separate matching-final/namespace-symlink
   risk remains in `BUG_BACKLOG.md` and needs a new threat-model decision.
5. **Closed (2026-08-28).** #269's existing deterministic test seam already
   supplies stage-level integration confidence (`tests/test_roadmap.py`: 403
   passed, 166 skipped). Do not add a harness, CLI, or smoke mode; a future
   demonstrated gap gets only the smallest deterministic test.
6. **Parked.** #208's position-05 framework lens stays unauthored: the Integration
   receipt preflight is complete and does not select an AWS taxonomy. Re-enter
   only when a named framework-specific roadmap need requires a checkable
   coverage contract. It must remain one ordered stage, not an opportunistic
   rewrite of the completed positions.
7. **Closed (2026-09-14).** Source admission records a decoded-text digest on
   `source.json`'s first write and refuses changed or legacy content before
   roadmap work. An operator may accept current text only at the same recorded
   path, replacing the source baseline without re-grounding artifacts. Semantic
   changes remain owning-artifact feedback or a successor lineage. Its
   independent review converged.
8. **Closed (2026-09-14).** The route-local brief-drift record gives each
   non-stage route a tested,
   route-local changed-brief and legacy-brief policy. Analysis creation and
   immutable-root enrollment refuse redacted with status `1`; log-free impact
   inspection returns status `0` with no route or workflow; structural rewrite
   preserves evaluator admission and guarded recovery before its refusal. None
   gains stage-run rebind or lifecycle authority.
9. **Closed (2026-09-16).** #367 requires
   `--confirm-brief-rebind` with the recorded `--from-existing` path before a
   changed or legacy stage-run brief can replace its source baseline. It keeps
   matching and initial behavior unchanged, rejects the flag on non-stage
   routes, and grants no artifact or broader source authority. Three complete
   reconcile sweeps and two final independent Sonnet 5 reviews find no live
   logic/property failure after the final production fix.
10. **#384 review-converged; #383 remains held.** #384 carries settled
   upstream decisions in as gated `settled` `decisions` rows; #383 generalizes
   to per-stage supplements with declared `grounding`/`judgment` roles. They
   overlap deliberately, and #384 is the narrower half: it reuses the
   existing `DecisionRow` gates, adding a `source` citation that marks a row
   as carried and scoping the rejected-alternative gate to decisions the
   stage made. If #383 ships, it treats a settled decision as a `grounding`
   supplement with this closed shape rather than adding a second mechanism. The role
   enforcement in #383 is the load-bearing part and belongs at the prompt
   boundary, not in documentation: an enumeration handed to stage 4 as
   grounding reproduces the measured nine-row outcome through a new door.
11. **#385 is independent of 7–10 and can be taken in any order.** A read-only
   `--view status --json` projection over facts the tool already computes. It
   is the one item here driven by a consumer rather than by the verb's own
   quality, so it waits on a real consumer needing it; Integration's connector is
   that consumer, and until Integration has code, this is evidence-gated rather than
   ready.
12. **#488 is `ready` and independent of 7–11.** It turns a failed `run` step's
   `model_failure_receipt` into one open feedback item naming the receipt, and
   lists receipts never routed. It is the follow-on to Integration `BACKLOG.md` #5,
   which shows the owner why a step stopped and deliberately leaves routing
   out. The operator names the roadmap and target; a plan-provenance field is
   a separate entry if one turns out to be needed.
13. **#489 waits on its trigger.** Record who decided a structural approval or
   a decision settlement (`human` or `agent`, as the caller states it) before
   Integration's roadmap driver begins relaying an owner's approval into
   `--decide-candidate`. Plan-tool records the claim and does not verify it;
   approval policy stays with the caller.

### Roadmap-to-plan subroute

Choose this subroute when the next question is what shared application evidence
derived plans need, rather than how to publish or revise a roadmap artifact.
The [Integration evidence record](../../evidence/integration-roadmap-to-plan-handoff.md)
identifies the observed gaps and the limits of the pilot results.

BACKLOG **#492 owns the single staged arc**, including each stage's deliverable,
tool state and follow-on seed placeholders. This section routes to that entry;
it does not duplicate its scope contracts or create another backlog owner.

| Work | Route and prerequisite |
| --- | --- |
| #492 composition-handoff investigation | Start here; evidence-gated architect work. A use-existing/no-action result is valid. |
| #493 selected shared-context delivery | Wait for #492's explicit input/consumer/compatibility decision; no implementation seed yet. |
| #462 advisory cross-plan conflict report | Keep its existing scope and evidence gate. Preferred after the context decision for this subroute; it remains independently eligible when its own gate is met. |
| #494 recorded-prerequisite view | Wait for its distinct operator need and input contract; not a new readiness authority or scheduler policy. |
| #490 finding dispositions | Consult its convergence-evidence arc; do not duplicate its store or transfer ownership. |
| #485 roadmap departures | Resolve its authority decision before relying on departure semantics; a pending feedback id alone does not approve a roadmap change. |
| #484 fix-induced finding marks | Independent reporting work; not a prerequisite or a hidden expansion of shared-context delivery. |

Do not bulk-author future implementation plans from unresolved design choices.
The next small selected plan still requires its complete detail bundle and
ordinary audit gates. No new command, fifth roadmap artifact, automatic split,
semantic feasibility gate or migration is authorized by this route.

This subroute exits when #492's per-consumer and follow-on dispositions are
recorded and each selected feature reaches its own bounded completion or
no-action outcome. Unselected work remains explicitly gated in the backlog.
Only then consider selective re-auditing or assisted composition as separately
evidenced work. Publishing or testing a session-made tool change on Integration still
uses the canonical delivery gate above and its separate owner authorizations.

## Decision gates

- A new field belongs on an existing roadmap row only when it changes a
  derived plan's contract; storage types and implementation mechanisms remain
  plan-owned.
- Evidence storage owns sealed publication only. Receipt semantics, commit
  outcome, telemetry, and user-facing handoffs remain consumer-owned.
- Existing injected-stage tests use disposable roots and deterministic invokers.
  Do not introduce an external-backend smoke surface or production
  partial-stage mode without a newly demonstrated gap and separate decision.
- Lifecycle output reports only the command's own accepted, started, retried,
  written, and terminal transitions. It must not relay backend prompts or
  model output, declare success before a gate admits it, or alter
  machine-readable output contracts. A quiet period after a confirmed
  transition remains ambiguous and does not establish liveness.
- Conversational feedback is reviewer-owned input, not write authority. The
  system creates an immutable candidate from the accepted head, then requires
  a deterministic diff and explicit approval of an immutable review seal's
  exact candidate binding before any downstream reader changes.
- A cross-artifact candidate validates as one complete roadmap. Model output
  cannot publish or replace the accepted head; declared relation closure and
  full-roadmap gates remain deterministic.
- The concept brief is bound at the first artifact write. A later change to it
  is expressed as feedback on the owning artifact or as a successor lineage;
  no route re-grounds a written roadmap from a changed brief, and the fix for
  a silently accepted change is a refusal, never a re-ground.
- A new source input widens what a stage may read, never what it may write. An
  input whose role is judgment — material the roadmap is measured against
  afterward — is not rendered into a stage prompt at all, because an
  enumeration reaching stage 4 becomes a row count.

## Exit and handoff

#337 is complete through
[the stage-lifecycle plan](../archive/2-roadmap-stage-lifecycle-output.md):
roadmap consumers can cite gated hosting, storage, feedback, and evidence facts
without inventing them, and an operator can see a roadmap command's last
confirmed transition without inspecting its process or inferring liveness from
a quiet period. #328 is complete and does not expand #337. Its #329 and #330
hardening follow-ups remain deliberately unassigned until #328 final sign-off;
a later route may be quality/risk profiling if the remaining question is how
plans should react to those facts.

## Out of scope

This arc does not create a production single-stage execution flag, infer
technology choices without evidence, add filesystem hardening beyond the
separately approved threat model, or absorb the bounded structural-rewrite
safety work in `archive/backlog-arc-structural-rewrite-safety.md`. The completed
#337 scope does not add a heartbeat or liveness signal, stream backend prompts
or model output, add a dashboard, persist job progress, provide cancellation
controls, or create a broader observability surface. #328 does not create a
Integration/browser feedback transport, a generic document-chat capability, or a
direct free-form writer; those require separate product authorization.
