# Plan-tool feature backlog and triage

## Purpose

This document is the forward-looking backlog for the plan-tool skill.
It catalogs candidate features and improvements that have been
considered but not yet implemented, with enough context per item to
compare them and pick what to work on next.

**This file is for forward-looking work.** Known-broken behavior
(incorrect output, contract violations, dormant correctness bugs,
race conditions, leaked resources, mis-reported run logs) lives in
[`BUG_BACKLOG.md`](BUG_BACKLOG.md), not here. See [Which file does
my entry go in?](docs/TRACKING.md#which-file-does-my-entry-go-in) for the
decision rule.

How to use it:

- **Start at the [Now board](#now--next--blocked--parked-working-set)** under
  Priority when picking the next session — full catalog below; that board is
  the short competing set.
- **Browse the Backlog.** Each entry carries effort, dependencies,
  risks, and value notes so you can judge fit against the time you
  have and the surface you're willing to touch.
- **Use the Triage framework** at the top as a coarse grouping
  (well-scoped capability vs. UX change vs. investigation vs.
  hygiene vs. cosmetic). Within a bucket, sort by your own priorities.
- **Check the Quality/accuracy lens.** Cutting across the buckets,
  the [Quality/accuracy lens](#qualityaccuracy-lens-cross-cutting)
  flags — and rolls up — every entry that bears on the accuracy or
  quality of the tool's own output or analysis. Start there when you
  want trust-core ROI: a defect in this class silently degrades every
  plan the tool produces, so it outranks equal-effort work that only
  adds surface.
- **Check the Readiness lens (concrete vs. theoretical).** Also
  cross-cutting: the
  [Readiness lens](#readiness-lens-concrete-vs-theoretical) in the
  Priority section separates items **ready to implement** from those
  that need a **decision or investigation first** (`readiness:
  decision-needed` / `evidence-gated` — formerly "bucket C" /
  `Approach:` "decision first", retired 2026-09-17). Prefer concrete
  items for shippable ROI; the theoretical ones carry schedule risk
  their tier alone doesn't show.
- **Read the entry's Approach tag.** Each entry carries an
  **Approach:** field (`direct`, `plan-tool`, or a conditional
  like `direct unless …`) that pre-resolves the
  direct-implement-vs-plan-it-first question. The tag is a
  recommendation, not a contract — if you disagree, the
  [Direct vs. plan-tool plan](docs/TRACKING.md#direct-implementation-vs-plan-tool-plan)
  heuristic tells you when to override.
- **Remove a feature's entry when it ships.** A promoted entry shrinks to
  a one-line stub (id, title, ticket key) until then; see
  [`docs/TRACKING.md`](docs/TRACKING.md#promotion-stubs). This doc is supposed
  to stay current — historical "we did X in session Y" content
  belongs in git log, in the feature's implementation plan file
  under `implementation-plans/`, and in
  [`docs/explanations/lessons-learned.md`](docs/explanations/lessons-learned.md) for
  design-level insights worth preserving. Closed decisions that need
  a short re-open condition live in
  [the backlog decisions record](docs/history/backlog-decisions.md).
- **Roadmap items are owner-tracked, not promoted.** The `roadmap` verb is
  experimental work the project owner develops on their own schedule, and the
  lead does not promote its items to Jira. They are the items
  [`backlog-arc-roadmap.md`](docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md)
  routes (listed under § "Execution-routing arcs"), plus any entry whose
  **Arc assignment** names `backlog-arc-roadmap`. Integration's runbook,
  `backlog-arc-integration-mvp.md`, routes no items of its own: a plan-tool finding
  Integration surfaces is an ordinary entry, and the lead can promote it unless it is
  roadmap-owned. See [`docs/TRACKING.md`](docs/TRACKING.md#roadmap-boundary).
- **Add new candidates** as they surface. A useful entry has at
  minimum: a one-line description, an effort estimate, the main
  risks or test-fallout you'd hit, any blocking dependencies on
  other items, and an **Approach** tag picking direct or plan-tool
  per the heuristic.

The rules for tracking work (which file an entry goes in, direct vs plan,
the entry format, the scope contract, the architectural map, plan
authoring, and useful commands) live in `docs/TRACKING.md`. This file
keeps a heading and a pointer for each and no copy, so a change to a rule
needs no edit here.

---

## Execution-routing arcs

`docs/implementation-plans/backlog-arcs/` holds execution-guide documents that
sequence backlog items into an ordered working route for a session, in four
kinds: a **feature-breakout arc** scopes a themed push through a handful of
items; a **priority-band baseline arc** is the generic fallback ordering
(T1–T5) when no themed push applies; a **project runbook** drives one
specific external project through `plan-tool`, routing every tool-side
finding elsewhere rather than owning it; and an **archived** arc is a
complete, historical record kept only to stop re-litigation — never a
routing target. This file catalogs *what* the candidates are within each
kind; an arc file itself says *which order* to work them in and why, with
its own "Choose this arc when" trigger, delivery cadence, and exit/handoff
rule. Read the doc matching your session's constraint and kind, not the
whole folder top to bottom.

**Feature-breakout arcs** — a scoped, themed push through a handful of
backlog items, with its own decision gates and exit rule. Prefer one of these
over a tier doc whenever your session is already committed to its theme:

- [`backlog-arc-convergence-evidence.md`](docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md)
  — making convergence/audit signals trustworthy before they influence plan
  decomposition, scope, or remediation decisions.
- [`backlog-arc-mechanism-reach.md`](docs/implementation-plans/backlog-arcs/backlog-arc-mechanism-reach.md)
  — keeping focused plans on their requested property while reusing suitable
  common structures and carving shared semantic changes into intentional work.
- [`backlog-arc-seed-ingestion.md`](docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md)
  — completed record of the shipped file-backed ingestion route; it is not an
  active routing target. #102 remains separate heading-alias work.
- [`backlog-arc-operator-workflow.md`](docs/implementation-plans/backlog-arcs/backlog-arc-operator-workflow.md)
  — operator visibility, deferred-work selection, and reader-facing surface
  quality, without changing correctness or ownership contracts; #510/#515 add the public
  onboarding walkthrough and fresh-repository verification. Draws on the
  idle-plans list (T3's exit hands off there) and gates T5 hygiene work.
- [`backlog-arc-headless-process.md`](docs/implementation-plans/backlog-arcs/backlog-arc-headless-process.md)
  — the evidence-first route for remaining headless human-input and
  human-availability paths; it selects no shared policy before #322's fresh
  route inventory. #322 is untiered — this arc is its sole router.
- [`backlog-arc-roadmap.md`](docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md)
  — roadmap-level capability and evidence work, from durable artifact facts
  through the bounded consumers that rely on them. Its items (#328, #242,
  #208, #366, the structured-upstream group #383–#384, and #385) are untiered —
  this arc is their sole router. #384's implementation and review tail are
  complete; #383 remains the active structured-upstream route. The
  roadmap-to-plan subroute starts at #492; #493 and #494 remain gated follow-ons,
  and existing #462 retains its own advisory-audit scope.
- [`backlog-arc-installed-skill.md`](docs/implementation-plans/backlog-arcs/backlog-arc-installed-skill.md)
  — what an installed Claude Code/Codex/Cursor skill gives a driving session
  before it has to find the answer itself: the thin router/shared-reference
  split, skill trigger fields, seed authoring, and out-of-scope/stale-entry
  backlog capture. Public onboarding additions #508/#509/#511/#512 also route
  here. Its items (#377, #378, #379) are untiered — this arc is
  their sole router; #371 (skill frontmatter trigger fields) also shipped
  from this arc, 2026-09-17. #443 (`DIRECTIVES.md` beside the tracked
  skill) and #444 (quote the routers' `argument-hint`) shipped 2026-10-06.
- [`backlog-arc-driver-contract.md`](docs/implementation-plans/backlog-arcs/backlog-arc-driver-contract.md)
  — what an unattended driver can read from `plan-tool` without inferring it:
  the result of `create`/`detail`, a refused `create`, a plan's gate verdict,
  per-finding triage labels, and run usage totals. Its items (#499, #502,
  #506) are untiered — this arc is their sole router; #504 and #385 stay with
  `backlog-arc-roadmap`.
- [`backlog-arc-run-gates.md`](docs/implementation-plans/backlog-arcs/backlog-arc-run-gates.md)
  — what happens around a `run` step's gates: the prompt before it finishes,
  what a retry sees, the outcome a failed step reports, and what the gates
  observe. Its items (#454–#459) are untiered — this arc is their sole router;
  #87, #88, and #108 stay routed elsewhere.

**Release coordination** — an explicit cross-arc route, preserving each lane’s
ownership:

- [`backlog-arc-public-release.md`](docs/implementation-plans/backlog-arcs/backlog-arc-public-release.md)
  — distribution, update and sync guidance (#514),
  then portable skill guidance, setup and fresh-user onboarding through the
  installed-skill and operator-workflow arcs.

**Priority-band baseline arcs** — the fallback when no feature-breakout arc
or the Now/Next/Blocked/Parked board (below) is your session's constraint.
Each catalogs `BACKLOG.md`'s own curated band membership from § "Priority
(mission-grounded)" and chains to the next: T1 → T2 → T3 → idle plans →
T4/T5. The arc filenames keep `tier` so existing citations still resolve; a
band is not the `Tier` label (`beginner`/`experienced`/`architect`), which
names the experience the work needs.

- [`backlog-arc-tier-t1.md`](docs/implementation-plans/backlog-arcs/backlog-arc-tier-t1.md) — P1, the highest band; `BUG_BACKLOG.md` leads it while unblocked.
- [`backlog-arc-tier-t2.md`](docs/implementation-plans/backlog-arcs/backlog-arc-tier-t2.md) — P1/P3, convergence & structural-remedy machinery.
- [`backlog-arc-tier-t3.md`](docs/implementation-plans/backlog-arcs/backlog-arc-tier-t3.md) — P2, deterministic verifiability & grounding (larger).
- [`backlog-arc-tier-t4.md`](docs/implementation-plans/backlog-arcs/backlog-arc-tier-t4.md) — P3, grounding/workflow refinements + blocked.
- [`backlog-arc-tier-t5.md`](docs/implementation-plans/backlog-arcs/backlog-arc-tier-t5.md) — export leg / UX / hygiene / cosmetic, the lowest band.

**Project runbooks** — not a priority router at all; a live operational
playbook for driving one specific external project through `plan-tool`. Do
not read these looking for "what's next in the backlog" — they route to the
feature arcs and `BUG_BACKLOG.md`/`BACKLOG.md` for any tool-side finding
instead of owning tool work themselves:

- [`backlog-arc-integration-mvp.md`](docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md)
  — driving the Integration MVP through the roadmap → seeds → plan → run pipeline on
  the first real project that exercises the `roadmap` verb; the standing
  assessment of the Integration roadmap, the milestone commands, and the ledger of
  tool findings Integration surfaces (each routed to its owning file, never fixed
  in the arc). **The sequence it serves is Integration's**, in that repository's
  `handoffs/README.md` order of operations (settled 2026-09-09); this file
  supplies the operating detail each of its steps needs and carries no
  competing route.

**Archived** — complete, historical, kept only to confirm what shipped and
stop re-litigation. Never a routing target:

- [`archive/backlog-arc-trust-core.md`](docs/implementation-plans/backlog-arcs/archive/backlog-arc-trust-core.md) — complete 2026-08-19.
- [`archive/backlog-arc-jira-grade.md`](docs/implementation-plans/backlog-arcs/archive/backlog-arc-jira-grade.md) — complete 2026-08-22.
- [`archive/backlog-arc-structural-rewrite-safety.md`](docs/implementation-plans/backlog-arcs/archive/backlog-arc-structural-rewrite-safety.md) — complete 2026-08-18; never reopen.

[`BUG_BACKLOG.md`](BUG_BACKLOG.md) is a separate list with no arc doc of its
own — its own `## Triage` section carries its drain order and closure
checklist directly, since it is worked from directly rather than routed.

---

## Which file does my entry go in?

The rules for this live in [`docs/TRACKING.md` § "Which file does my entry go in?"](docs/TRACKING.md#which-file-does-my-entry-go-in).
`BACKLOG.md` keeps no copy, so the two cannot drift apart.

---

## Direct implementation vs. plan-tool plan

The rules for this live in [`docs/TRACKING.md` § "Direct implementation vs. plan-tool plan"](docs/TRACKING.md#direct-implementation-vs-plan-tool-plan).
`BACKLOG.md` keeps no copy, so the two cannot drift apart.

---

## Triage framework

Buckets are by *character* of the work, not strict priority. Within
a bucket, recency-of-relevance and dependency order drive the call.

| Bucket | When to pick from it |
|---|---|
| **A. New capability, well-scoped** | First choice when you want clear ROI. Focused surface, familiar implementation pattern, bounded tests. |
| **B. Significant UX changes** | Pick when you're willing to deal with broad test fallout in exchange for a meaningful behavior shift. |
| **C. *(retired 2026-09-17)*** | Folded into the `readiness` label (`docs/TRACKING.md#labels-every-entry-carries`): what Bucket C meant — needing a decision or investigation before implementation — is now `decision-needed` / `evidence-gated`. Read an existing `bucket C` citation as one of those values. |
| **D. Process / hygiene** | Pick to close completeness gaps, refactors, or performance hints. Often touch infrastructure rather than user-facing features. |
| **E. Cosmetic / churn** | Last. Renames, branding, low-value cleanups. |

### Quality/accuracy lens (cross-cutting)

The buckets above sort by *character*; this lens is orthogonal to
them. It flags entries whose work bears on the **accuracy or quality
of plan-tool's own output or analysis** — the plans it authors
(frontmatter, step decomposition, detail bodies, jira stories) and the
analysis it produces (completeness / reconcile audits, review
findings, granularity / convergence diagnostics). A defect *here* is
the most expensive kind: it doesn't fail loudly, it silently degrades
**every** plan the tool touches, and a shallow or wrong finding reads
as authoritative. These items map directly onto MISSION's trust core
(P1 converge/correctness, P2 deterministic verifiability, P3
grounded-in-live-code), so they skew toward the top of the
[Priority](#priority-mission-grounded) tiers regardless of which
bucket A–E they sit in.

**`Quality:` marker.** Entries that bear on output/analysis quality
carry a `Quality:` field naming the facet(s) they touch (analogous to
the `Approach:` tag). Omit the field on entries that don't (pure
ergonomics, throughput/perf, refactors, cosmetic) — its *absence* is
information too. Facet vocabulary:

- `grounding` — keeps findings/plans tied to the **live code at
  HEAD**, not stale, snippet-only, or truncated context (the
  head-only-4 KB / Read-Grep / drift-detection family).
- `audit-coverage` — whether the analysis **catches what it should**
  and doesn't misfire: deterministic complements to the stochastic
  sampler, discovery/apply separation, re-ground precision.
- `convergence` — whether the output actually **converges to complete
  + correct** rather than leaving `_(TODO)_` gaps or spinning on a
  mis-decomposition.
- `gate-signal` — whether gates and blocking stops **block/pass the
  right things** (domain-aware severity, gate robustness) so the exit
  signal is trustworthy.
- `heuristic-tuning` — **foundational**: the data that lets every
  threshold behind the facets above be calibrated from the
  distribution rather than single-session anecdote.

**File split still applies.** A quality item that is *forward-looking*
("the analysis could be sharper") lives here; a quality item that is
*already wrong* on a supported flow (a shallow or incorrect finding
the code produces **today** because of a real defect) is a bug and
lives in [`BUG_BACKLOG.md`](BUG_BACKLOG.md). The `Quality:` facet
vocabulary applies to bug entries too when you want to flag the blast
radius — use the [decision rule](docs/TRACKING.md#which-file-does-my-entry-go-in)
to pick the file, then tag the facet in whichever file it lands.

**Current quality/accuracy-impacting items** (roll-up; grouped by
facet, highest-leverage first — this is the interim index while
inline `Quality:` tags are backfilled, and it is the highlight the
lens exists to produce; keep it in sync as entries land or are added):

- **grounding:** **#97** (symbol-aware excerpts replace head-only 4 KB),
  **#38** (reconcile precision — detail-write annotation + `review` pre-filter),
  **#312** (ground `detail` authoring in fetched reference-doc content
  instead of a bare link list), **#30** (verify plan against developer-doc
  links; detail-level half depends on #312), **#208** (a parked
  `roadmap` framework-lens route — a framework lens replaces an inferred
  quality-attribute vocabulary with an external one, so constraint coverage
  becomes checkable rather than plausible), **#291** (the seed-materialization
  prompt states the greenfield case explicitly, so empty-repo seeds stop
  carrying invented file references into `create`), **#271** (stage 4 steers
  a greenfield roadmap's first plan toward the runnable substrate later
  plans' verification presumes), **#296** (the one detail-prompt content
  block with no byte ceiling of any kind — `prior_body_block` — gets a
  remedy specific to its faithful-combine constraint instead of the generic
  advisory), **#314** (a source-linked review determines whether advisory
  risk context leaves a concrete declaration-authority or safety gap).
- **audit-coverage:** **#66** (contract-trace / path-enumeration deterministic
  audit mode — complements the stochastic sampler), **#175** (jira-readiness audit
  lane — deterministic anchor verification, frontmatter↔detail footprint
  coherence, and decided-scope compliance as a minutes-scale gate on `jira`
  export, reporting only ticket-blocking findings), and the run-log coverage
  arc **#176** / **#177** (four verbs spend Claude with no log at all;
  `create`'s slug call precedes its own log; an unsinked call now warns once
  per process naming its call site, so the remaining gaps announce themselves),
  **#295** (give `Recommendation` a confidence signal distinct from severity,
  so a shakily-supported finding stops rendering with the same authority as a
  well-grounded one), **#301** (version saved conceptual-audit coverage before
  the next additive field), and **#302** (one checked completion path preserves
  rate-limit recovery notification coverage).
- **convergence:** **#238** (report plan mass beside the finding count — the
  stopping rule measures findings, not the artifact, so a plan that grows while
  its findings fall reads as a clean convergence), **#164** (invert the detail
  contract — author at jira grade so a scope change invalidates one paragraph
  instead of a bundle of stale implementation facts; the largest observed
  source of audit churn), **#163** (tell a *folded* guardrail section apart
  from a genuinely dropped one, so the shipped preservation warning does not
  train operators off the channel — evidence-gated, see the entry),
  **#102** (widen deterministic seed-extraction so fewer body sections strand
  as `_(TODO)_` awaiting the stochastic loop), **#129**
  (deterministic program-scale observations only; no wrong-altitude verdict), **#156**
  (make the sampler key on the `[out-of-scope-deferred]` tag so a
  scope-bound audit converges instead of grinding on correctly-deferred
  adjacent findings), **#181** (proportionality detection at create time; also
  `heuristic-tuning`),
  **#262** (surface a non-gating detail-readiness recommendation after repeated
  bare-plan audits, so a user advances to the artifact that can resolve the
  remaining implementation contracts rather than re-sampling the same plan).
- **gate-signal:** the shipped calibrated impact-aware convergence policy
  (high-impact findings and high/critical severities block; evidence-qualified
  low-impact medium findings may be demoted), the settled four-loop blocking
  boundary (see
  [the backlog decisions record](docs/history/backlog-decisions.md)),
  **#87** (harden the test-authoring gate
  against a dirty working tree), **#108** (durable per-step run marker so the
  structural-remedy gates block interrupted-`current`, not
  authored-`current`), **#314** (evidence decides whether advisory
  risk-profile context needs a declaration-authority or escalation guardrail),
  **#217** (a stage that dies on an
  unusable reply keeps no copy of it — the per-attempt event shipped, the byte
  sink did not), **#472** (a Claude window before the
  first call, so the first send and the reconcile refusal gate stop using the
  200K default).
- **heuristic-tuning:** **#216** (the corpus-replay benchmark whose first
  deliverable is each metric's *own* rerun noise floor — the data every other
  threshold here would need before it could be calibrated from a distribution
  instead of a single session). Entries already carrying this facet inline
  (e.g. **#181**) are **not** rolled up here; the bullet names only the evidence
  prerequisites.

When you have bandwidth for trust-core work, start from this list.

---

## Priority (mission-grounded)

Ranked against [`MISSION.md`](MISSION.md): trust = **verifiable + scoped +
grounded**, and the five principles are themselves roughly priority-ordered —
converge/correctness (P1) → deterministic verifiability (P2) →
keep-true-to-live-code (P3) → survive-interruption (P4) → write-for-the-human
(P5). So **P1–P3 (the trust core) outrank P4–P5**; within a band, favor cheap,
foundational, or principle-*violation*-fixing work. This index spans both the
backlog entries below **and the authored plans** in
`docs/implementation-plans/` — those are past `create`/`detail`, so executing a
mission-aligned one is the cheapest path to shipped value, but *authored ≠
priority*; the mission decides.

**Current queue facts (checked 2026-09-16):**

1. **`BUG_BACKLOG.md` has unresolved BUG entries.** Triage its live BUG
   section before selecting a new feature route; each entry owns its own
   readiness and approach.
2. **#102 remains independent of the delivered seed-ingestion route.** Its
   future alias-matching decision does not reopen the source-selection or
   preparation contract.
3. **The manifest contains planning and completed plans.** Choose an authored
   plan only after checking its current body and detail coverage; archive
   membership is delivery history, not a queue item.

### Now / Next / Blocked / Parked (working set)

Short queue — refresh when a plan ships, a seed is consumed, or the pick
changes. Full catalog stays in the buckets below; this board answers "what
competes for the next session?"

| Lane | Item | Why |
|---|---|---|
| **Now — bug triage** | `BUG_BACKLOG.md` | Work from the live BUG section and its triage rules; the earlier bounded direct batch is no longer the current queue. |
| **Roadmap — Integration** | Replay the prose-only follow-up on candidate c886d0f | The 384 KiB candidate context ceiling shipped (PR #58): the follow-up's 211,712-byte context should now be admitted once this build is installed. The model-aware budget warning shipped (PR #60 and its review follow-up); #472 (a Claude window before the first call) is the next item; #471 (relation compaction) and #468 (targeted retry) stay parked. Existing ROADMAP bug entries remain tracked. |
| **Next (evidence-gated)** | `quality-bench-01` (#216), position 01 | Preserve its noise-floor question, but first perform one disposable current-model observation rather than build its runner/CLI. A fresh plan is justified only if that exercise demonstrates a durable replay surface is needed. `roadmap-05` (#208) remains unauthored until a named framework-specific roadmap need exists. |
| **Next (idle plans)** | `lessons-reuse-instrumentation` (9) · `jira-sweep-deterministic` (9) · `deferred-scan-digest` (11) + `deferred-select-promote` (9) | Authored; execute or explicitly park — don't re-author beside them |
| **Ready seeds** | `premise-ledger` · `audit-shape-saturation-and-provenance` · `audit-shape-advisory-generic-walk` · `walk-advisory-chat-mode` · `completeness-output-quality` · `audit-finding-staleness-classification` · `feature-health-2-attribution-and-ledger` · `lessons-store-restructure` | Keep; `create` only when that lane is the pick. Two more seeds sit on disk but are **blocked**, not ready — `jira-sweep-verify-code-truth` and `deferred-findings-digest`, each on the plan it cites |
| **Blocked** | #194 on #193 · #199 on #198 · `detail-verbosity-compact-summary` on #308 re-baseline · `deferred-findings-digest` on `deferred-scan-digest` · `jira-sweep-verify-code-truth` on `jira-sweep-deterministic` | A blocked seed on disk is not ready work. |
| **Parked / defer** | #353 Integration-compatible artifact-contention handoff · `security-check-command` (10 steps, open design issues in-plan) · #173 incremental completeness cache (deferred; #299 coverage-replay withdrawn 2026-08-20) · convergence evidence #256 (labelled-corpus prerequisite) · #260 (needs a concrete misleading-output fixture) · concept residue #126–#134 · Bucket D consolidation #79–#81 | #353 waits for the narrow normalized-artifact collision correction to stabilize and for explicit selection; the rest are edge / dormant / evidence-gated — and #79's claims need re-verification before any merge |

**Authored plans** (manifest; every plan below is `status: planning`):

| Plan | Steps | Disposition |
|---|---|---|
| `lessons-reuse-instrumentation` | 9 | Next — pairs with lessons integrity work |
| `jira-sweep-deterministic` | 9 | Next — export-leg hygiene; `jira-sweep-verify-code-truth` waits on it |
| `detail-verbosity-compact-summary` | 6 | Blocked — re-baseline after #308 removes the Jira-grade schema authority |
| `deferred-scan-digest` | 11 | Next — deferred-work triage surface |
| `deferred-select-promote` | 9 | Next — the promote half of the same surface |
| `security-check-command` | 10 | **Parked** — open design issues recorded in the plan |
| `batch-observability-forensics-and-view` | 5 | Deferred observability work carved from the completed batch plan |
| `arm-clustering-cross-round-consensus` | 5 | Consensus follow-up; validate its premise before execution |
| `roadmap-revision-retention` | 8 | Paused — redesign after the Integration receipt preflight |

**Priority bands:**

- **T2 — convergence & structural-remedy machinery (P1/P3):** **#71**
  (theoretical — decision-first).
- **T3 — deterministic verifiability & grounding (P2), larger:** **#66**
  (contract-trace audit mode), **#97** (symbol-aware prompt excerpts replacing
  head-only 4 KB; mission P3 "grounded in live code" — run its excerpt-strategy
  spike before the build).
- **T4 — grounding/workflow refinements (P3) + blocked:** **#69**, **#38**,
  **#30**, **#74**'s heavy slice (A2/A3 direct-API / CLI-session caching and
  broader per-step parallelism — large, per-backend design choices with
  determinism risk; the cheap slice A1/C1/C2 and the authoring-only B slice
  have shipped, and `CLAUDE.md` § "Architecture" sets the burden of proof any
  new in-process fan-out must clear).
- **T5 — export leg / UX / hygiene / cosmetic:** **#308** (retire legacy Jira-grade detail), **#107** (deferred pending a demonstrated export blocker), **#49**, **#102**,
  **#43**, **#54**, **#55**, **#56**, **#36** (theoretical), **#89** (commit-hygiene
  coverage — observed orphaning gap on `reconcile-code`, see its entry's
  "Evidence it recurs"), **#366** (theoretical — aidlc-workflows
  pattern-applicability survey; may close with "no action" per its own
  Output-of-investigation gate), and the Bucket D
  consolidation cluster **#79**–**#81** — where **#79 carries a warning**: four
  of its five original "duplicated helper" claims were wrong in the direction
  that breaks things, so treat every line of it as a claim to re-verify.

### Readiness lens (concrete vs. theoretical)

Orthogonal to the tiers: the tiers say *what's worth doing*; this says *whether
it's ready to be done*. An item is **theoretical** when a decision or
investigation must land **before** any implementation — its output may be "no
action" or a refined concrete item, so it carries schedule risk a tier alone
doesn't show. The formal marker is the `readiness` label
(`docs/TRACKING.md#labels-every-entry-carries`): `decision-needed` or
`evidence-gated` means theoretical, `ready` means concrete. (Bucket C and an
`Approach:` opening with *"decision first"* or *"investigation"* meant the
same thing and are retired as of 2026-09-17 — read an entry still carrying
either as theoretical until it's relabeled.) Prefer concrete items for
shippable ROI; reach for a theoretical one only when a concrete item is
**blocked** on its unanswered question, or when the investigation is itself
the highest-leverage move (e.g. a `heuristic-tuning` unlock).

- **Theoretical (decide/investigate first):** **#71** (refusal-token shape —
  the one theoretical item in a top tier),
  **#111** (orphaned-deliverable identity model), **#110** (claim-vs-delivery
  FP rate), **#87** (test-authoring gate hardening), **#113** (budget-limited
  under-decomposed false-positive — needs a disambiguating signal; carries a
  cheap `direct` wording slice), **#141** (jira story-size floor vs. the
  configurable ceiling), **#210** (keep/cut the purity pass — passive
  observation only; do not schedule a dedicated audit), **#36** (per-plan
  `lessons.md` value), **#366** (aidlc-workflows pattern-applicability
  survey), **#381** (lesson-confidence threshold measurement), and **#382**
  (finding evidence-provenance decision), plus **#499**, **#502**, **#504** and
  **#506** (each `decision-needed`). Two more carry a
  **spike-gated front** — theoretical before their concrete build: **#66**
  (validate the trace approach) and **#97** (excerpt-strategy spike). The
  archived `review.py` decision is the worked example of this lens paying off:
  the investigation cost a read and returned "don't build it", which is the
  outcome a theoretical item is *supposed* to be allowed to have.
- **Concrete (ready to implement):** every other open entry, plus all ten
  planning plans.

**Recommended execution order:** T1 → T2 → T3 → the remaining idle plans →
T4/T5, per the chained band-baseline arcs in § "Execution-routing arcs"
above (`backlog-arc-tier-t1.md` through `backlog-arc-tier-t5.md`).
`BUG_BACKLOG.md` leads this order while it contains an unblocked BUG, and an
active feature-breakout arc or a Now/Next/Blocked/Parked board pick outranks
working straight down the tiers.

---

## Backlog

### A. New capability, well-scoped

> **Priority:** see [Priority (mission-grounded)](#priority-mission-grounded)
> above for the cross-bucket execution order. This bucket's trust-core cluster
> has no active T2 feature request. The deterministic-verifiability pair
> **#66** and **#97**
> (symbol-aware excerpts) at T3. Everything else here sits below them.


**#499 — Audit sidecars record each finding's triage label and carry-forward status**

- **What:** the version-4 completeness sidecar has no field for a finding's
  altitude (R, B, P, D, I or T) or for whether the finding is carried to
  `detail`. The label exists only in the session that triages the report.
  Record the audit's own altitude classification per finding, and mark the
  findings a bare audit withholds as detail-level.
- **Why:** an external driver cannot verify the directive's normal Gate 1
  exit ("after three bare rounds, proceed to `detail` when the remaining
  findings are D, I, or about text the previous round added"). Integration's
  Construction batch driver therefore asks the owner to confirm that case with
  `proceed`, trusting the session's labels. A recorded label lets the driver
  check the D arm itself; I (settled by code or a platform spike) is not one an
  audit can reliably assign, so it stays a session or owner gate. The third arm ("about text the previous round
  added") is a finding's relation to the last edit, which an altitude label
  cannot express, so that arm keeps its human gate unless a separate
  mechanism is chosen.
- **Effort:** medium; a prompt field, the sidecar schema (a version bump in
  `DATA_CONTRACT.md`), and the parser. Related to #192 (findings carry a step
  id), which touches the same finding record.
- **Scope contract:**
  - **Outcome:** each saved conceptual finding carries a closed altitude
    label and a carried-to-detail flag at the bare stage. The label does not
    decide the "about the previous round's text" arm.
  - **In scope:** the audit prompt's output field, the sidecar schema and
    its version, the reader.
  - **Out of scope / Non-goals:** changing blocking predicates or exit codes;
    auto-routing findings by label; recording a finding's relation to the
    previous round's edit (a separate decision if the driver needs it).
  - **Allowed behavior changes:** new sidecar fields under a new version.
  - **Allowed reorganization:** none.
  - **Verification:** a bare audit of a plan with a known D-level finding
    saves that finding with label D and the carried flag.
  - **Stop / defer:** if label agreement between passes is too low to be
    useful, record the measurement and stop.
- **Route:** `plan` · **Readiness:** `decision-needed` (who owns the label: the
  audit or the triaging session. I means settled by code or a platform spike
  and P means an owner's product decision, so an audit may not be able to
  assign either; the first slice may cover D only) · **Tier:** `architect`.
- **Principle:** `converge-on-correct-plan`.
- **Origin:** 2026-10-19, Integration `construction-batch-driver` design and its
  Gate 1 rounds.

**#502 — A refused `create` leaves a record an external driver can read**

- **What:** `create` refuses on the seed paths before it resolves a slug and
  opens its run log, for example when a roadmap-tracked seed's accepted
  version is absent. The run log is keyed by the resolved
  slug, so those refusals have no log to write to, and a later branch-collision
  decline also opens none by design.
- **Why:** an external driver cannot tell a refused `create` from one that
  never ran, so Integration's design needs a special rule mapping "no run log" to a
  create failure. `DATA_CONTRACT.md` does not promise a run log for every
  invocation, so this is a capability gap and not a bug.
- **Effort:** small to medium; the open question is where a pre-slug refusal
  records itself.
- **Scope contract:**
  - **Outcome:** a `create` refused on a seed path leaves a record naming the
    refusal and its closed reason, at a location settled by the decision.
  - **In scope:** the pre-slug seed refusal paths, the record's location and
    outcome value (reusing an existing `run_end` outcome where one fits),
    `DATA_CONTRACT.md`, tests.
  - **Out of scope / Non-goals:** other subcommands (file separately if they
    share the gap); a log for a bad plan name (`detail` deliberately opens no
    ghost JSONL for an unknown name, and `create` keeps the same rule).
  - **Allowed behavior changes:** a record on a pre-slug refusal.
  - **Allowed reorganization:** none.
  - **Verification:** each pre-slug `create` refusal path produces the record
    with the closed reason, and a successful `create` is unchanged.
  - **Stop / defer:** if the decision is a log keyed by the seed's filename
    slug, confirm it cannot collide with a real plan slug before building.
- **Route:** `direct` · **Readiness:** `decision-needed` (the record's key and
  location) · **Tier:** `architect` (a persisted run-record contract).
- **Principle:** `deterministic-non-determinism`.
- **Origin:** 2026-10-19, Integration `construction-batch-driver` design §2.2.

**#504 — Plans declare dependencies on other plans**

- **What:** plan frontmatter has `depends_on` between steps but nothing between
  plans. Add a plan-level field naming the plans this plan builds on.
- **Why:** a batch driver can only order plans by the roadmap's `ordering`; it
  cannot check that plan k+1's prerequisites are complete. The unbuilt-sibling
  bug ("`create` writes a single 'record unbuilt upstreams and stop' step…")
  has the same root: no stated relationship between plans.
- **Effort:** medium; the field, `PLAN_FORMAT.md`, `create`'s use of it, and
  status/audit checks.
- **Scope contract:**
  - **Outcome:** a plan names the plans it depends on, and `status` reports
    whether each is complete.
  - **In scope:** the field, its validation, `create` filling it from the
    roadmap, a status check.
  - **Out of scope / Non-goals:** scheduling or running plans in dependency
    order.
  - **Allowed behavior changes:** a new optional frontmatter field.
  - **Allowed reorganization:** none.
  - **Verification:** a plan created from a roadmap row with an upstream lists
    it, and `status` reports the upstream's state.
  - **Stop / defer:** if the fix for the unbuilt-sibling bug settles the
    contract another way, follow it.
- **Route:** `plan` · **Readiness:** `decision-needed` (field shape and its
  relation to roadmap `depends_on`) · **Tier:** `architect`.
- **Principle:** `keep-the-plan-true-to-code`.
- **Origin:** 2026-10-19, Integration `construction-batch-driver` design.

**#506 — A total budget across a multi-round audit loop**

- **What:** `--time-budget` bounds one invocation, not the sum across a
  multi-round audit loop. Decide whether to add an optional total budget, in
  tokens or minutes, and where it is held.
- **Why:** Integration's batch driver runs many invocations per plan and has no
  bound on their sum.
- **Effort:** medium; needs the shipped `run_end.usage` totals (#505) and a place to persist the
  running sum.
- **Scope contract:**
  - **Outcome:** a decision, then (if built) an optional budget that stops a
    loop between rounds.
  - **In scope:** the budget's unit, persistence, and stop behavior.
  - **Out of scope / Non-goals:** changing any default; reading a
    subscription's allowance.
  - **Allowed behavior changes:** an opt-in flag.
  - **Allowed reorganization:** none.
  - **Verification:** a loop with a budget smaller than one round stops with a
    stated reason; one without a budget is unchanged.
  - **Stop / defer:** builds on the shipped `run_end.usage` totals (#505).
- **Route:** `plan` · **Readiness:** `decision-needed` (unit and where the
  running sum lives) · **Tier:** `architect`.
- **Principle:** `none` — usage reporting.
- **Origin:** 2026-10-19, Integration `construction-batch-driver` cost review.

**#362 — Roadmap staged artifacts declare their format version (deferred)**

- **What:** the four roadmap staged artifacts (`01-domain.md` …
  `04-roadmap.md`) are the third authored class with no in-band format
  version, beside the plan and run-grade detail classes that already declare
  one. This class needs two things settled first that the plan/detail classes
  did not: an interaction with the accepted-head version store's exact-byte
  digests, and a relationship to an *existing*, differently-scoped
  `format_version` field already living in the same subsystem. Both are
  explained in full below so a session re-entering this later does not have
  to re-derive them.
- **Why a declaration-only change is unsafe here:** the obvious approach — a
  roadmap reader gate and a matching writer stamp, structured exactly like
  the plan and detail classes — is unsafe to ship as written. Two verified
  code facts show why:

  1. **A stamp is a byte change, and the accepted-head roadmap-version store
     is bound to exact bytes.** `plan_tool/roadmap_versions.py` digests raw
     staged-artifact bytes with `hashlib.sha256(artifact_bytes)`, and
     `_require_content_matches_record` raises `RoadmapVersionError("stored
     artifact bytes do not match their record digests")` on any mismatch.
     Writing a version declaration into the four staged artifacts changes
     those bytes. Every roadmap enrolled in the accepted-head store — six
     roadmaps exist today, all in the `integration` repository — would fail that
     digest check the moment its artifacts were stamped. A declaration-only
     change, safe for the other two classes, is a breaking change here.
  2. **A field named `format_version` already ships in the same subsystem,
     meaning something else.** `plan_tool/roadmap_source_identity.py` defines
     `BASELINE_FORMAT_VERSION = 1` and carries a `format_version` field on
     both `BaselineRecord` and `CanonicalSourceIdentity`, bound to a
     `stage_key` and persisted inside escalation receipts and impact
     analyses (documented in `ROADMAP_FORMAT.md`'s escalation-receipt and
     impact-analysis examples). It versions the **semantic projection** used
     for baseline identity, not the staged artifact's on-disk markdown
     structure. A second, differently-scoped in-band structure version on the
     same artifact class needs that relationship settled before either field
     is touched. Merging or renaming the two for label convenience is
     explicitly refused — they answer different questions.

  Full reasoning, including the evidence that led to deferring rather than
  solving inline, is recorded in
  [`docs/evidence/authored-artifact-structure-versioning.md`](docs/evidence/authored-artifact-structure-versioning.md)
  § "Roadmap staged artifacts — deferred". Read that section before starting
  design work here; do not re-derive it from scratch.
- **Why deferring costs nothing right now:** six roadmaps exist, all in one
  repository (`integration`), all owned by one person. No roadmap format break is
  currently pending. The one roadmap-format break to date — required entity
  `fields`, added 2026-08-02 in commit `4c60b3ab` — was absorbed with no
  migration code, and all six roadmaps carry the field today. There is no
  schedule pressure to settle the digest-and-lineage interaction now, and
  settling it under no pressure is safer than settling it while also shipping
  a breaking roadmap change.
- **Effort:** unknown until the design questions below are answered — do not
  estimate effort before that design work happens. The mechanical part (a
  reader gate and a writer stamp at the four staged parsers) is small; the
  actual cost lives in the accepted-head interaction, which could be as cheap
  as "publish the upgraded bundle as a new accepted-head version whose record
  marks it structure-only" or could require store changes if that recommendation
  does not hold up under design review.
- **Risks / fallout:** shipping the declaration without settling the digest
  interaction breaks every enrolled roadmap outright, which is why this class
  stays a separate, deferred entry rather than shipping alongside the plan
  and detail classes. Conflating this field with
  `CanonicalSourceIdentity.format_version` — by reusing its name, its constant,
  or its persisted location — would corrupt an unrelated, already-shipped
  contract (`#328`'s accepted-head content/lineage authority) that this entry
  must leave untouched.
- **Dependencies:** none blocking. Independent of the shipped plan and
  detail format-version work. Independent of paused **#242**
  (roadmap revision retention) — do not resume #242 through this entry; they
  touch adjacent roadmap machinery but answer unrelated questions. Does not
  reopen closed **#328** (the accepted-head content/lineage store), whose
  contract this entry must preserve unchanged.
- **Scope contract:**
  - **Outcome:** each of the four roadmap staged artifacts declares its
    format version in-band as one bundle version (not four independently
    versioned stages), a reader rejects an unsupported version with a named,
    actionable result, and the interaction with the accepted-head version
    store's exact-byte digests and with `CanonicalSourceIdentity.format_version`
    is explicitly resolved rather than left implicit.
  - **In scope (once re-entered):** `plan_tool/roadmap_artifacts.py`
    (`_parse_frontmatter` and the four staged parsers/renderers),
    `plan_tool/roadmap_versions.py` (the digest interaction),
    `plan_tool/roadmap_source_identity.py` (the `format_version` relationship),
    `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`.
  - **Out of scope / Non-goals:** version 2 of any artifact, a migration
    engine, on-read upgrading, content revision/lineage/history, and
    versioning `BACKLOG.md` / `plan-seeds/` / jira exports; resuming paused
    #242; reopening closed #328; renaming or merging
    `CanonicalSourceIdentity.format_version` with the new field for label
    convenience alone.
  - **Allowed behavior changes:** none yet — this entry is design work before
    it is implementation work. Behavior changes are scoped when the design
    questions below are answered.
  - **Allowed reorganization:** none yet, for the same reason.
  - **Verification:** deferred to the design phase; must include a fixture
    proving an already-enrolled roadmap either stays valid under the new
    declaration or is re-enrolled through an explicit, described transition —
    never silently invalidated.
  - **Stop / defer:** this entire entry stays deferred until the re-entry
    trigger below fires. Do not begin implementation from this entry's Outcome
    alone; the design questions must be answered first, in a fresh bare plan.
- **Approach:** `plan-tool`, once re-entered — design first (a fresh bare plan
  answering the three questions below), then the standard
  author/detail/audit/run loop. Not `direct`: the accepted-head digest
  interaction is real design surface, not a mechanical change.
- **Re-entry trigger:** re-enter only when an actual breaking change to a
  staged roadmap artifact is needed — not on a schedule. At that point, open a
  fresh bare plan of its own, never a resumed one, and settle these three
  questions before writing code:
  1. Whether a structure upgrade republishes the bundle as a new accepted-head
     version whose record marks it structure-only, preserving lineage at the
     cost of one record field; or whether enrolled roadmaps are exempt from
     upgrade; or whether re-enrollment with an accepted lineage break is
     correct. The current recommendation, not yet designed against the store's
     actual code, is the first option.
  2. How an in-band structure version relates to
     `CanonicalSourceIdentity.format_version`, without renaming or merging
     either field.
  3. Whether all four staged artifacts must always declare the same version.
     The current recommendation is yes — one bundle version, with a
     mixed-version bundle refusing — because a four-way compatibility matrix
     across the staged artifacts is not itself a policy.
- **Origin:** 2026-09-08, carved out during the authored-artifact
  format-version design review, recorded in
  [`docs/evidence/authored-artifact-structure-versioning.md`](docs/evidence/authored-artifact-structure-versioning.md);
  user-confirmed the roadmap class is out of scope for the plan and detail
  format-version work.
- **Status:** deferred. No plan, seed, or design document exists yet — that is
  correct; do not author one before the re-entry trigger fires. Do not rerun
  or re-verify anything about the shipped plan/detail classes through this
  entry.

**#363 — Ship the authored-artifact raw-upgrade operator route at the first legacy refusal**

- **What:** version 1 exposes raw plan and detail upgrade entry points as
  library APIs because it newly refuses no previously supported on-disk
  representation. The first format release that makes a previously supported
  live plan or run-grade detail artifact hit a reader or writer refusal must
  ship an operator-invocable route for the affected class in that same release.
  It must preflight reader/writer compatibility before every affected mutating
  command's first state change, then prove upgrade-and-rerun leaves no partial
  state.
- **Effort:** medium when triggered — the exact command set depends on the
  format break, but the raw entry points and compatibility contract already
  exist as seams.
- **Dependencies:** a concrete post-version-1 plan or detail format change
  that causes an existing on-disk representation to reach a refusal. Nothing
  in version 1 blocks on this entry.
- **Scope contract:**
  - **Outcome:** an operator encountering the newly live refusal gets a named
    route that upgrades the affected raw artifact before a mutating command
    changes plan-adjacent state.
  - **In scope:** the selected operator command, both raw upgrade entry points
    as needed, the affected mutating-command preflights, command help, and
    upgrade-then-rerun/no-partial-state tests.
  - **Out of scope / Non-goals:** a version-1 command surface, upgrade-on-read,
    a general migration engine, multi-hop conversion, roadmap staged artifacts
    (#362), and a transform for a version that has not been designed.
  - **Verification:** exercise each affected class from a real legacy fixture;
    prove refusal before preflight mutation, successful explicit upgrade, and a
    clean rerun with no partially changed plan state.
  - **Stop / defer:** if the proposed break cannot state which live artifact
    representation refuses and why, stop at a fresh bare plan rather than
    inventing a generic command.
- **Approach:** `plan-tool` — this is a cross-command behavior change whose
  exact route is selected by the future format break.
- **Re-entry trigger:** the first approved plan or detail format bump that
  makes a previously supported live on-disk artifact reach a reader or writer
  refusal.
- **Origin:** filed 2026-09-09 while restructuring the authored-artifact
  format-version plan after its detail-grounded audit identified the missing
  operator route for reader-only detail breaks.
- **Status:** deferred until the re-entry trigger fires.

**#364 — Detect authored-artifact version-contract drift in completeness and registry metadata**

- **What:** `artifact_format_version_contracts()` records the plan and detail
  format constants, but `cli/completeness_phases.py:_collect_data_contract_drift`
  does not inspect that record and `registry_fingerprint()` excludes it. Add
  the narrow drift check, then include the record in the fingerprint only once
  the check makes it an invalidation-relevant contract.
- **Effort:** small — the source registry and the completeness drift seam are
  already explicit; the work is wiring plus focused regression tests.
- **Dependencies:** the authored-artifact version-contract registry landing.
  It does not require a future format bump or the operator route in #363.
- **Scope contract:**
  - **Outcome:** a changed authored-artifact format constant or documented
    version rule surfaces through the same completeness/data-contract drift
    channel as comparable registered contracts, and its fingerprint changes
    only because that channel consumes it.
  - **In scope:** `artifact_format_version_contracts()`, the named completeness
    drift collector, `registry_fingerprint()`, their focused tests, and the
    documented fingerprint rationale.
  - **Out of scope / Non-goals:** a new artifact schema registry, arbitrary
    documentation linting, a `CLAUDE.md` guard, changes to version-policy
    semantics, and any artifact upgrade path.
  - **Verification:** mutate a registered authored-artifact constant and a
    documented rule independently; prove the intended drift result and
    fingerprint invalidation, while an unrelated registry consumer stays
    unchanged.
- **Approach:** `direct` — a bounded integration with named callers and
  fixtures; use the direct-change review/convergence loop.
- **Origin:** filed 2026-09-09 while restructuring the authored-artifact plan
  after its detail-grounded audit found the version-only registry deliberately
  excluded from the completeness drift and fingerprint paths.
- **Status:** ready when the version-contract registry implementation has
  landed; not part of version-1 delivery.

**#365 — Reconcile authored-artifact documentation and planning-manifest discoverability**

- **What:** document `plan_tool/detail_artifacts.py` as the owner of the live
  run-grade detail version contract in `docs/ARCHITECTURE.md`, reconcile the
  `Authored plans` manifest with the current planning-plan set (including the
  missing `roadmap-source-baseline-recovery` row), and review the three
  `CLAUDE.md` reference-doc bullets for a bounded drift guard only if the sweep
  shows one is justified.
- **Effort:** small for the documentation and manifest sweep; any automated
  guard remains a separate decision after that evidence exists.
- **Dependencies:** the authored-artifact plan and detail contract landing for
  the architecture entry; the manifest repair itself is otherwise independent.
- **Scope contract:**
  - **Outcome:** an architecture reader can discover the detail version owner,
    the planning manifest matches its stated coverage, and the reference-doc
    guard decision has explicit evidence rather than an assumed need.
  - **In scope:** `docs/ARCHITECTURE.md`, the authored-plans manifest in
    `BACKLOG.md`, the three existing `CLAUDE.md` reference-doc bullets, and a
    focused read of their current consumers.
  - **Out of scope / Non-goals:** changing artifact-version behavior, making
    `CLAUDE.md` itself versioned, a broad documentation linter, and #362's
    roadmap design.
  - **Verification:** compare the manifest to the current `status: planning`
    plans, verify the architecture entry names the correct owning module and
    contract, and record the guard decision with its evidence.
- **Approach:** `direct` for the bounded sweep; decide separately before adding
  an automated guard.
- **Origin:** filed 2026-09-09 while restructuring the authored-artifact plan
  after the detail-grounded audit surfaced the architecture/manifest and
  reference-doc discoverability gaps.
- **Status:** ready for the documentation and manifest sweep; guard work is
  decision-gated.

**#383 — Per-stage supplementary sources for `roadmap`, with declared roles**

- **What:** every roadmap stage receives exactly one prose input, the whole
  brief (`plan_tool/roadmap.py:_render_stage_prompt` builds `${brief}` plus
  one `${<key>_artifact}` per upstream stage). When the brief is produced
  upstream by another lifecycle engine, its material is already separated by
  purpose — a constraint register, a decision log, a prioritized backlog — and
  flattening it into one document is what forces a composer to choose between
  withholding grounding stage 2 needs and pasting a list stage 4 will return
  one row per. Give `source.json` an optional `supplements` map keyed by stage
  key, render it as `${supplements}`, and require each entry to declare a
  **role** — `grounding` (facts a stage must use) versus `judgment` (material
  the stage is measured against afterward and must not enumerate from).
- **Effort:** medium. `source.json` is read by
  `plan_tool/roadmap_source.py:read_recorded_brief_source` and written by
  `roadmap.py:_write_brief_source`; the prompt seam is one `variables` dict;
  the four stage templates need the new placeholder. The volume is in the
  identity contract: `roadmap_source_identity.py`'s digest must cover the
  supplements or a receipt's currentness claim becomes false.
- **Risks / fallout:** a supplement is another enumeration channel, which is
  the exact hazard the brief-shape lesson names — a `judgment`-role entry
  handed to stage 4 as grounding reproduces the nine-row outcome through a new
  door. The role must be enforced at the prompt boundary (a `judgment`
  supplement is not rendered into a stage prompt at all), not left as
  documentation. Second: supplements widen what a stage reads without widening
  what it may write, so the existing gates stay the only authority.
- **Dependencies:** none. This remains separate from the shipped #384
  carried-decision input and must not reuse it as a general supplementary-source
  mechanism.
- **Review aids that become worth having once #383 ships (not in scope here):**
  each is read-only and small, and none changes what a stage receives. (1) A
  dry-run view of each stage's rendered prompt, so a pre-freeze review reads the
  actual input instead of inferring it from the source files. (2) A review view
  listing `judgment`-role sources beside the accepted plan rows, so a human
  judges coverage semantically and the tool does not. (3) A source-set summary
  in #385's `--view status --json`, so the projection also answers "what fed
  this roadmap". File them as their own entries when #383 is selected. Origin:
  2026-09-11 intake-ideas handoff, retired 2026-09-29.
- **Origin:** 2026-09-09, Integration's AI-DLC Ideation route
  (`handoffs/2026-09-09-roadmap-from-ideation.md` there). Stage 2 requires one
  hosting row per facet and one disposition per quality attribute and guesses
  when the brief is silent; the facts exist in an upstream
  `constraint-register.md` that has no way to reach it except by being pasted
  into the brief.

**#385 — `roadmap --view status --json`: one machine-readable state projection**

- **What:** no roadmap view emits JSON
  (`--view {summary,walk,ledger,index,seeds,html,escalations,impact-analyses}`
  are all human renders; the only `json.dumps` calls in
  `plan_tool/cli/roadmap_cmd.py` are inside escalation/analysis evidence
  lines). A caller that wants to know where a roadmap *is* — which stages have
  artifacts, which are baseline-enrolled, which feedback rows are open or
  awaiting review, which draft seeds classify `current`, and the last run's
  outcome — has to parse human output or re-implement the classifiers. Add one
  read-only projection over facts the tool already computes:
  `classify_draft_seeds`, the baseline records, the feedback collections, and
  the run log's terminal event.
- **Effort:** small to medium. Every input already has a function; the work is
  the schema, its `DATA_CONTRACT.md` registration, and the fail-closed
  behavior when a roadmap is partially written.
- **Risks / fallout:** a state projection invites callers to treat it as
  authority. It is a *view*: the artifacts and their baselines remain the
  record, exactly as the run log is a monitoring projection rather than the
  execution record. Version it from the first release or a consumer will pin
  its field names by accident.
- **Dependencies:** none. Complements the shipped stage-lifecycle stderr
  contract (#337) rather than extending it — that reports transitions during a
  run, this reports state between runs.
- **Origin:** 2026-09-09, Integration's control-plane work
  (`handoffs/2026-09-09-control-plane-mvp-shape.md` there). Integration presents two
  engines through one contract; the other engine offers both an event log and
  `--status --json`, where `plan-tool` offers `plan-tool runs` and no state
  projection, so the presentation layer is asymmetric for reasons that are not
  about the engines' actual capabilities.

**#386 — Prefer stating a parity/consistency relationship over enumerating one side of it, in plan authoring and audit remedies**

- **What:** When a plan's steps must keep several parallel structures
  consistent with each other (multiple backend integrations, multiple
  environments, multiple config profiles, repeated instances of one
  pattern), give `create`'s step-authoring guidance
  (`plan_tool/prompts/synthesize-body.md`) and `plan-audit.md`'s
  remedy-suggestion guidance a preference for stating the consistency
  relationship itself ("these N structures carry the same set of X") as an
  explicit Architecture-level principle, rather than only enumerating one
  side's current instances (a row count, a file list, a table). A finding
  whose remedy is "here's the specific gap in the enumeration" should be
  answered by widening the stated relationship, not by patching the
  enumeration to add one more instance.
- **Why:** measured directly on 2026-09-16 while driving `BACKLOG.md` #370
  (`skill-router-and-shared-reference`) to a bare-plan completeness audit.
  Three consecutive audit rounds found the plan's own parity language for
  the Claude/Codex/Cursor router trio drifting — first naming one of four
  roadmap decision-tree rows, then four of seven total roadmap rows, then
  roadmap rows without the parallel convergence-tail rows — each fix
  technically correct and each still incomplete, because every fix
  enumerated a snapshot instead of stating the actual invariant ("whatever
  one router keeps, the others keep too"). Restating the fix as one
  symmetry principle in the plan's Architecture section closed all three
  findings at once and stopped the recurrence. This is the same lesson
  `~/.claude/CLAUDE.md`'s "Prefer the explicit over the implicit" section
  establishes for machine-parsed formats ("mark the boundary structurally,
  not positionally"), applied here to plan-authoring and audit-remedy prose
  instead of a text delimiter — the "boundary" lost to positional drift is
  a consistency relationship between parallel structures, not a marker in a
  finding.
- **Effort:** small — prompt-text guidance in two files, no code.
- **Risks / fallout:** could read as license to under-specify concrete
  facts (which files, which functions, exact acceptance criteria) — those
  stay as explicit as ever; the preference is specifically for the
  *relationship between* parallel structures, not a general excuse for
  vagueness. This is advisory prompt guidance, not a gate, and rests on a
  single measured instance so far — worth a second real instance before
  treating the wording as settled.
- **Dependencies:** none.
- **Approach:** `direct` — prompt-text edits in
  `plan_tool/prompts/synthesize-body.md` and `plan_tool/prompts/plan-audit.md`,
  no code or schema change.
- **Origin:** 2026-09-16, observed while driving `BACKLOG.md` #370's
  bare-plan completeness audit to convergence — three rounds of enumeration
  drift on router parity, resolved by switching to a stated symmetry
  principle instead of another enumerated patch.
- **Status:** not started.

**#387 — `DIRECTIVES.md`'s model-selection guidance has no Claude-model analog for `roadmap`**

- **What:** `integrations/shared/DIRECTIVES.md` § "Which model to run a
  subcommand with" names which *Codex* model to run each subcommand with
  (GPT-6 Sol for `create`/`roadmap`, Terra elsewhere) but says nothing
  about which *Claude* model to prefer for any subcommand, `roadmap`
  included. A driving session has to fall back to this user's own general
  standing rule (`~/.claude/CLAUDE.md` § "Spend the stronger model where a
  mistake compounds") and re-derive that `roadmap` qualifies — it runs each
  stage once and constrains everything downstream, so it's conceptual work,
  the same shape that rule spends the stronger model on.
- **Effort:** small — a paragraph in one section of one file, mirroring the
  existing Codex subsection's structure. No code.
- **Risks / fallout:** low for the edit itself. `plan-tool install-skill`
  copies `DIRECTIVES.md` into consuming repositories, where this user's
  `~/.claude/CLAUDE.md` does not exist, so a citation to it cannot be followed
  there. Stating a Claude-model preference for `roadmap` could also drift from
  that standing rule if either is edited without the other in mind. Whether
  the section states the one-line rule itself or cites the personal file (as
  the project `CLAUDE.md` § "Model selection" does) is the open decision.
- **Dependencies:** none. #425 coordinates with this entry for its Claude
  wording.
- **Route:** `direct`.
- **Readiness:** `decision-needed` — the citation question above comes first.
- **Tier:** `architect` — it changes the canonical directives every driving
  session reads.
- **Origin:** 2026-09-16,
  `handoffs/2026-09-16-roadmap-orchestration-primer.md` § "Model selection",
  carried forward when that handoff was retired — its own stated retirement
  condition (`DIRECTIVES.md` gaining roadmap operational guidance) covered
  the file's router/how-to-use content, not this observation, which had no
  other recorded home.
- **Status:** not started.

**#425 — Installed skills make per-command model selection explicit before invoking plan-tool**

- **What:** update the installed Claude, Codex, and Cursor skill routers so a
  driving session consults `integrations/shared/DIRECTIVES.md` § "Which model
  to run a subcommand with" before constructing every model-backed plan-tool
  command, then passes the selected backend and model explicitly when the
  mapping names one. Keep the model mapping in the shared directives; the
  routers should point to and operationalize that rule rather than copying raw
  model ids into three skill files.
- **Why:** a real Integration roadmap revision was launched as plain `plan-tool
  roadmap ...`, so it silently used the local Claude default. The shared
  directives already require GPT-5.6 Sol for Codex `create` and `roadmap` and
  Terra elsewhere, but the consuming Integration session had no installed plan-tool
  skill exposed and therefore never loaded that guidance. A rule that exists
  only in the plan-tool development checkout does not govern an assistant in a
  consuming repository.
- **Outcome:** when a plan-tool skill is installed and triggered, the assistant
  can state the selected execution backend/model before launch and the emitted
  command carries explicit flags for model-backed operations. A missing or
  unavailable installed skill is surfaced as an installation/readiness issue;
  it does not silently fall back to reconstructing model policy from unrelated
  host-repository instructions.
- **Scope contract:**
  - **In scope:** the three installed `SKILL.md` routers, their pointer to the
    existing shared model-selection section, the command-construction guidance
    for model-backed subcommands, install/format coverage needed to preserve
    the pointer, and one consuming-repository exercise proving `roadmap` and an
    audit command select their intended Codex models explicitly.
  - **Out of scope / Non-goals:** moving model policy into Integration or another host
    repo's general coding-assistant directives; duplicating vendor model ids in
    each router; changing backend/model precedence in the CLI; implementing
    per-subcommand configuration (#254); selecting the missing Claude analog
    (#387); installing skills automatically; or changing any plan-tool command
    semantics.
  - **Allowed behavior changes:** installed skills emit explicit backend/model
    flags according to the already documented shared policy. Direct CLI users
    and repositories without an installed skill retain current behavior.
  - **Allowed reorganization:** add one small shared router instruction or
    generated/pinned fragment only if needed to keep all three routers
    symmetric; do not fold this into the broader router-template refactor
    tracked by #388.
  - **Verification:** install each integration skill into a temporary project;
    verify its router reaches the shared model section; exercise command
    construction for Codex `create`, `roadmap`, `completeness-audit`, and
    `run`; confirm the first two explicitly select Sol and the latter two
    explicitly select Terra; verify an explicit user model choice still wins;
    and confirm skill absence produces no claim that the policy was applied.
  - **Stop / defer:** if the installed router cannot reliably know the backend
    selected by the driving session, limit the change to requiring an explicit
    backend/model choice before invocation rather than inventing inference in
    prompt text.
- **Dependencies:** the shared Codex mapping already exists. Coordinate with
  #387 for Claude wording, #388 for router-template ownership, and #403 in the
  other active clone for eventual doctor/readiness inspection; none blocks the
  narrow installed-skill guidance change.
- **Approach:** `direct` — this is an orchestration-guidance and installation-
  coverage change with no product schema or runtime behavior change.
- **Origin:** 2026-09-21, the Integration full-MVP roadmap feedback revision. The
  driving session discovered after launch that the command used the default
  Claude backend because no plan-tool skill was available in Integration.
- **Status:** not started.

**#388 — Extract one shared template for the three SKILL.md routers' decision-tree and subcommands tables**

- **What:** `integrations/claude/SKILL.md`, `integrations/codex/SKILL.md`,
  and `integrations/cursor/SKILL.md` each hand-maintain a near-verbatim copy
  (~80-150 lines) of the "Decision tree for common user asks" and
  "Subcommands at a glance" tables — content that is backend-agnostic except
  for a handful of substitutions (the backend name, whether a row "calls
  <backend>", one Codex-specific doc citation). They have already drifted
  independent of any real backend difference: Codex cites
  `docs/OPERATIONS.md` for the Worktrees caveat where Claude/Cursor cite
  `README.md` for the identical claim, and Codex's "Project setup" row sits
  in a different table position than Claude/Cursor's "Project context" row
  for the same `init` command.
- **Why:** `BACKLOG.md` #370 (`skill-router-and-shared-reference`, shipped
  2026-09-16) already proved the extraction pattern works — it collapsed the
  old per-file "Convergence tail" prose and the roadmap flag-semantics rows
  into single `DIRECTIVES.md` pointers precisely to stop three-way drift —
  but left these two backend-agnostic tables as three hand-maintained
  copies. Every future subcommand change now needs the identical edit
  applied three times, with no mechanical way for a reviewer to tell an
  intentional backend delta from a missed copy.
- **Effort:** medium — needs a design decision (a build step generating the
  three files from one template plus a substitution map, vs. a lint/test
  that diffs the tables and fails on an unexplained divergence) before any
  code lands.
- **Risks / fallout:** picking a build-step design changes how routers are
  authored and reviewed; picking a diff-lint design only catches drift after
  it happens, not before. Either choice touches `install-skill`'s packaging
  story if the routers stop being static files.
- **Dependencies:** none.
- **Route:** `plan` — the design choice (generation vs. drift-lint) needs a
  bare-plan audit before detail multiplies either direction.
- **Readiness:** `decision-needed`.
- **Tier:** `architect` — changes how every installed router is authored and
  kept in sync.
- **Origin:** 2026-09-17, `/code-review high` on the
  `skill-router-and-shared-reference` plan, independently flagged by 3 of 8
  finder angles.
- **Status:** not started.

**#389 — A newly added backend is rejected by `plan-tool install-skill --integration` with "invalid choice" until someone edits its hard-coded list of three names** → promoted to IPPT-7 (2026-09-24)

**Closed — Route-local brief-drift policy for non-stage Roadmap routes**

- **Delivered (2026-09-14):** `--analyze-escalation` refuses `changed-brief`
  and `legacy-brief` redacted with status `1` and no immutable analysis
  publication, while
  log-free `--view impact-analyses` returns status `0` with no route or workflow.
  `--rewrite-structural` keeps evaluator admission and guarded recovery before
  its redacted status-`1` refusal, without artifact, baseline, or seed
  publication. Backend-free, exclusive `--enroll-version` returns the same
  redacted status-`1` states without an immutable version or accepted-head claim.
- **Boundary:** matching recorded decoded-text baselines retain each route's
  existing behavior. Stage-run lifecycle events and same-path `--from-existing`
  baseline acceptance remain exclusive to `plan_tool/roadmap.py:_run_roadmap`.
- **Evidence:** [`Roadmap Non Stage Brief Drift`](docs/implementation-plans/archive/2-roadmap-non-stage-brief-drift.md), its [final detail-grounded audit — retained historical summary](docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions), and the [guide-contract review guard](tests/test_roadmap_format.py).
- **Status:** closed.

**Closed (2026-09-16) — #367: Require explicit operator confirmation for changed-brief rebind**

- **Decision (2026-09-15, user-confirmed):** Repeating `--from-existing` at
  the recorded path is not sufficient consent to accept changed or legacy brief
  text. A stage run must require a distinct explicit confirmation before it
  replaces the recorded baseline.
- **Delivered:** `--confirm-brief-rebind` is a documented, stage-run-only,
  headless consent signal. A changed or legacy brief rebind requires it and
  the recorded `--from-existing` path; repeating the recorded path alone
  refuses.
- **Boundary:** matching and initial stage runs retain normal behavior, a
  different path remains refused, and non-stage routes reject the flag. The
  accepted-rebind lifecycle remains baseline-only and does not grant artifact,
  feedback, seed, multi-source, generic-confirmation, or Integration authority.
- **Evidence:** [Roadmap Brief Rebind Confirmation](docs/implementation-plans/archive/2-roadmap-brief-rebind-confirmation.md), its three saved
  `reconcile-code --all` sweeps, and the Sonnet 5 review records named in the
  AI-DLC delivery handoff.
- **Convergence:** the final production-logic change is `48b0957c`; two
  independent Sonnet 5 reviews after it find no live logic/property failure.
  The full suite passes with `12633 passed, 190 skipped`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** 2026-09-12 independent review of
  `roadmap-brief-source-drift`, Finding 36; this dated closeout replaces the
  then-pending successor status.
- **Status:** closed.

**#376 — Retire completeness/direct auto-apply; the orchestrating session makes session-directed edits**

- **What:** Retire `completeness-apply`'s interactive and parallel conceptual
  application paths and the `direct-run` / `direct-jira` chains that depend on
  them. A human at a TTY or an orchestrating session reads the saved report and
  applies a bounded, judged edit; no unattended command retains that authority.
- **Scope:** parser/help/reference entries, direct pipelines, hidden callers,
  active guidance, legacy report readers, and focused/full regression tests.
  Create/detail deterministic well-formedness repair and reconcile routes stay
  out of scope; #369 inventories those independently.
- **Boundary:** do not retain a renamed private auto-apply path, add a generic
  workflow engine, or rewrite historical reports merely to remove vocabulary.
- **Evidence:** the parked bare plan is
  `docs/implementation-plans/2-completeness-apply-retirement.md`; the existing
  deprecation warnings are interim mitigation only.
- **Route:** `plan`; **Readiness:** ready from `detail`; **Status:** parked bare,
  0/6 detailed and no execution started.

**#369 — Inventory other `apply_finding` authorities separately from #376**

- **What:** Trace `apply_finding` in create, detail, generic review, and
  reconcile, then record one evidence-backed disposition per caller.
- **Boundary:** do not change callers or infer shared authority from lexical
  similarity. Each migration-worthy caller becomes a separate backlog item.
- **Route:** `plan`; **Readiness:** ready; **Status:** not started.

**#338 — Extend stage-lifecycle status output to `roadmap --refresh-seeds` and `--materialize`**

- **What:** `_cmd_roadmap_refresh_seeds` and `_cmd_roadmap_materialize`/
  `_cmd_roadmap_materialize_owned` (`plan_tool/cli/roadmap_cmd.py`) drive the
  same shape of long-running, per-item backend work
  (`refresh_roadmap_seeds`, `materialize_and_diff_one_plan`) that the
  `roadmap <slug>` stage-run path now reports concise stderr transitions for
  (`2-roadmap-stage-lifecycle-output.md`), but neither orchestrator accepts or
  wires a `status_callback`. An operator running either subcommand against a
  large seed/plan set gets no incremental visibility into which seed or plan
  is being processed or retried — only the final summary render.
- **Effort:** medium — `refresh_roadmap_seeds` and
  `materialize_and_diff_one_plan` (and their per-item backend call sites)
  need a `status_callback` parameter threaded from the CLI, plus a bounded
  event vocabulary for this path (started/retrying/done per seed or plan) and
  deterministic tests proving the sequence.
- **Risks / fallout:** same class as the shipped stage-run reporter — an
  event emitted before its state transition actually lands could mislead an
  operator; keep the existing final summary and JSON/machine-readable
  contracts unchanged.
- **Dependencies:** none. `_emit_roadmap_fact`/`_bounded_status_text` in
  `plan_tool/roadmap.py` are the existing bounded-emission primitives to
  reuse rather than re-derive.
- **Scope contract:**
  - **Outcome:** `roadmap --refresh-seeds` and `roadmap --materialize`
    report concise, ordered stderr facts identifying which seed or plan is
    being processed or retried.
  - **In scope:** `refresh_roadmap_seeds`, `materialize_and_diff_one_plan`
    (wherever each lives), their per-item backend call sites, and
    `cli/roadmap_cmd.py`'s two dispatch functions.
  - **Out of scope / Non-goals:** any change to the stage-run reporter
    itself, streaming backend prompts/model output, a heartbeat or live
    dashboard, progress output for any other subcommand.
  - **Allowed behavior changes:** these two subcommands' interactive stderr
    output gains bounded transition facts; final summaries, exit status, and
    JSON contracts stay unchanged.
  - **Allowed reorganization:** none beyond threading the existing
    `status_callback` type through the two orchestrators.
  - **Verification:** deterministic tests assert event order for a
    multi-item refresh/materialize run including a retry, mirroring the
    stage-run reporter's own test shape.
  - **Stop / defer:** a need for cross-command job observation or durable
    progress persistence becomes a separate entry.
- **Approach:** direct — reuses an existing primitive and pattern; no design
  decision open.
- **Related follow-up, same scope boundary:** `_render_seed_materialize_prompt`
  (`plan_tool/roadmap.py:3363`) still does an unguarded `Path.read_text()`,
  unlike `_render_stage_prompt`/`_render_stage_feedback_prompt` (hardened to
  convert an unreadable/malformed template into a clean `RoadmapError`,
  matching `_load_stage_artifact`'s established pattern). An eighth
  `/code-review` round flagged it, but it's reachable only via
  `--materialize`/`--refresh-seeds` — the same code path this entry already
  scopes — so the hardening belongs alongside this entry's own work, not as
  a standalone fix against a path with no status output to protect yet.
- **Origin:** 2026-09-02 `/code-review` pass on
  `2-roadmap-stage-lifecycle-output.md`'s landed diff
  (`plan_tool/roadmap.py` + `plan_tool/cli/roadmap_cmd.py`); the diff's own
  scope was the `roadmap <slug>` stage-run path, so this sibling gap was
  deliberately not folded into it.
- **Status:** not started.

**#336 — Preserve deferred shared semantic work as a manual follow-up handoff**

- **What:** preserve a split-create foundational-logic `defer` result as a
  durable, operator-visible manual handoff that names the focused property,
  affected shared contract, and reason it stays out of the current plan. The
  operator uses that handoff to author a separately intentional follow-up plan;
  it never creates, approves, or schedules that plan automatically.
- **Scope contract:**
  - **Outcome:** a required shared semantic change cannot be silently dropped
    after it is correctly excluded from a focused vertical plan.
  - **In scope:** the smallest create/foundational-logic persistence and
    rendering path, its durable artifact or existing plan-side decision
    surface, and focused create/foundational-logic tests.
  - **Out of scope / Non-goals:** an automatic plan, backlog item, seed,
    prerequisite ordering, or shared-mechanism implementation; a general
    decision-event framework; changing create's combined/split selection; and
    automatic scope expansion of the focused plan.
  - **Allowed behavior changes:** a `defer` result may produce one manual
    handoff that survives the create run and tells the operator how to start a
    separate plan. It is informational and never mutates the focused plan's
    steps, files, scope fence, status, or exit code.
  - **Allowed reorganization:** only a local helper if create and the sweep
    otherwise duplicate the same handoff rendering.
  - **Verification:** hermetic split-create fixtures prove a deferred shared
    semantic candidate is visible after create, contains its property and
    reason, adds no focused-plan step or file, and emits no automatic seed or
    backlog entry. Unchanged reuse and a compatible bounded extension emit no
    handoff.
  - **Stop / defer:** if the handoff cannot faithfully identify the candidate
    without inventing shared-contract facts, retain the fail-closed `defer`
    behavior from #334 and do not publish a speculative record.
- **Dependencies:** #334; it supplies the semantic-reach rule and the
  fail-closed split-create `defer` classification.
- **Approach:** `plan-tool` — a dedicated cross-plan handoff is intentional
  work, distinct from the focused authoring rule that detects it.
- **Quality:** `handoff` — preserves a material deferral without treating it
  as permission to broaden the current plan.
- **Iterate:** author `plan-seeds/mechanism-reach-03-handoff.md` only after
  #334 ships, then drive the resulting plan through the normal gates.
- **Status:** not started.

**#335 — Audit only explicit, unjustified shared semantic commitments**

- **What:** add a manual-only conceptual-audit/detail-quality lens for a plan
  or detail that explicitly commits a focused property to a broader shared
  contract without naming why a common owner, local adapter, or bounded
  extension cannot deliver it. The recommendation identifies the property,
  affected contract, and decision still owned by the author; it neither
  invents a wider mechanism nor selects a local implementation.
- **Scope contract:**
  - **Outcome:** an explicit, unjustified cross-owner semantic commitment is
    visible before implementation, while ordinary reuse and an unselected bare
    implementation choice remain silent.
  - **In scope:** `plan_tool/prompts/plan-audit.md`,
    `plan_tool/prompts/detail-quality.md`, their finding parsing/routing,
    `docs/AUDIT_FLOW.md`, and focused audit/detail tests.
  - **Out of scope / Non-goals:** inferring a natural owner from a bare plan;
    a numeric fan-out rule; a new Claude call, schema field, exit-code change,
    or blocking-policy change; auto-applying a narrow rewrite; and changing an
    existing shared mechanism or its consumers.
  - **Allowed behavior changes:** one non-apply-eligible manual recommendation
    source may render on the existing audit paths when the explicit commitment
    and missing necessity proof are both present.
  - **Allowed reorganization:** only the smallest shared parser/renderer helper
    needed to keep the two existing audit surfaces consistent; do not extract a
    general scope-control framework.
  - **Verification:** hermetic invoker fixtures cover an unjustified shared
    semantic change, unchanged reuse, a bounded additive extension, a genuine
    multi-owner contract, and a bare plan that leaves delivery open. Tests also
    prove the recommendation is never apply-eligible or an exit-code gate.
  - **Stop / defer:** if the lens cannot classify only explicit commitments at
    high precision, remove it rather than tuning a broad scope classifier.
- **Dependencies:** #334; its authoring rule supplies the terminology and
  positive cases this lens must preserve.
- **Approach:** `plan-tool` — the manual decision route crosses two existing
  audit surfaces and their recommendation handling.
- **Quality:** `audit-coverage` — adds a bounded lens for architectural reach
  without treating scope judgment as automatic remediation.
- **Iterate:** author `plan-seeds/mechanism-reach-02-audit.md` only after #334
  ships, then drive the resulting plan through the normal gates.

  ```bash
  plan-tool create mechanism-reach-02-audit --iterate -y --from-existing plan-seeds/mechanism-reach-02-audit.md
  plan-tool detail mechanism-reach-02-audit --commit -y
  plan-tool completeness-audit mechanism-reach-02-audit --iterate --commit -y
  plan-tool run mechanism-reach-02-audit --commit -y
  ```

- **Status:** not started.

**#332 — Preserve developer-doc research failure evidence in create run logs**

- **What:** make an unsuccessful developer-doc research call diagnosable from
  the create run record. The run must retain the call's phase, attempt,
  transport outcome, token/cost fields when supplied by the backend, and a
  bounded pointer to parse-failure evidence instead of only printing a
  progress-line summary.
- **Scope contract:**
  - **Outcome:** a create run that reaches `propose_references` always has an
    active compatible run-log sink for the Claude invocation, and an
    unparseable response produces a queryable failure record distinct from an
    intentional empty reference result.
  - **In scope:** the create caller-to-invoker logging seam; existing
    `claude_call_*`, backend-termination, and `parse_failure` event carriers;
    a size-capped, secret-redacted diagnostic artifact with a run-log pointer;
    and hermetic command-level tests for success, an unparseable response, and
    an injected/alternate invoker path.
  - **Out of scope / Non-goals:** unrestricted raw model-response retention;
    a new cross-command telemetry framework; changing the reference-selection
    policy; or making a developer-doc research failure fatal. The failure
    policy belongs to the linked bug.
  - **Allowed behavior changes:** the run log may add a reference-research
    failure event and a bounded diagnostic artifact, and the command may name
    its saved report path. It must not expose secrets or make an otherwise
    successful create fail only because persistence of optional diagnostics
    fails.
  - **Allowed reorganization:** reuse the current run-log writer and shell
    sink lifecycle; extract at most one local create helper for the failure
    artifact/pointer. Do not introduce a general telemetry abstraction.
  - **Verification:** command-level fake-backend tests prove the reference
    call has `claude_call_end` token/cost fields, the unparseable path records
    its phase/reason and a bounded pointer, the empty-list path has neither
    parse-failure record nor artifact, and a sink-installation regression emits
    no unsinked-call warning. Tests also prove the artifact is redacted and
    capped.
  - **Stop / defer:** if an alternate invoker cannot provide raw response or
    usage safely, record that capability as unavailable with the parse reason;
    do not synthesize missing fields or add backend-specific persistence.
- **Dependencies:** related to the developer-doc research parse-failure bug in
  `BUG_BACKLOG.md`; neither item blocks the other.
- **Approach:** `plan-tool` — this adds narrowly scoped failure observability
  across create, shell/run-log integration, and their contract tests.
- **Quality:** `failure-evidence` — makes a non-happy-path model call
  inspectable without widening the create plan's product scope.
- **Origin:** observed 2026-09-01 alongside the developer-doc research parse
  failure: the only diagnostic was the progress-line summary, and the call
  warned that no run-log sink saved its raw response, usage, cost, or lower-
  level failure evidence.
- **Status:** not started.

**#268 — Per-step contract asks in the step proposal (failure modes and criterion mapping)**

- **What:** a proposed step today is title + classification + file list +
  one-line intent — the proposal prompt never asks what the step guarantees,
  what can fail and each failure's disposition, or which acceptance criterion
  proves it. The first three audit rounds of both 2026-08-12/13 plans
  (`batch-authoring-observability`, `roadmap-seed-materialization`) were
  dominated by exactly this mass: missing failure/atomicity contracts,
  unowned mechanisms, dangling criteria, `change_type` mislabels.
- **Blocked on #110.** The right carrier (prompt-only prose vs. new `Step`
  fields) can't be decided yet — #110's measurement may conclude "keep
  claim-vs-delivery advisory" rather than promote it, which changes how much
  of this gap #110 already closes on its own. Wait for #110 to resolve, then
  decide the carrier and write the full design.
- **Effort:** medium–large, design-first, once unblocked.
- **Dependencies:** #110.
- **Approach:** plan-tool (seed first), once unblocked.

**#269 — Hermetic roadmap-stage integration harness, without a production partial-stage mode**

- **Closed 2026-08-28:** the existing `_Env` / injected-`StageInvoker` seam in
  `tests/test_roadmap.py` already supplies disposable roots, the real
  `run_roadmap` path, stage-output and no-write-on-failure assertions, and
  run-log / in-flight lifecycle coverage. Its focused suite passes **403
  passed, 166 skipped**.
- **Decision:** do not add a named harness, developer CLI, or external-backend
  smoke entry point. Each would duplicate the present proof and risk creating
  the production partial-stage mode this item forbids.
- **Future evidence:** a demonstrated transport or logging gap may add the
  smallest deterministic test to the existing seam. Reopen only when that
  seam cannot exercise a required stage behavior without a new production
  surface.

**#173 — Keep incremental completeness scans deferred**

- **What:** retain only a possible fingerprint-gated step-scan cache and an
  anchored re-check lane. Cross-invocation low-yield reporting belongs to
  #303, not this item.
- **Precondition:** #299's withdrawal is recorded in
  `docs/history/backlog-decisions.md`: its evidence boundary needs a hermetic
  capture runner. Do not author or implement a cache or re-check lane. Reconsider
  only when measured operational audit cost justifies a new, bounded design that
  selects and proves a full-discovery cadence.
- **Scope contract:**
  - **Outcome:** if the precondition is met, unchanged inputs reuse a labelled
    prior scan while every report states the exact coverage and the required
    full-discovery cadence.
  - **In scope:** cache/recheck design only after the cadence decision; a reuse
    identity covering the complete captured audit input, including plan body,
    detail, repository code state, audit stage/grade, and sampler/configuration
    state; truthful skipped/rechecked/full-discovery reporting.
  - **Out of scope / Non-goals:** #303's cross-history result, any low-yield
    decider, resolution-label evidence, cache reuse across different
    captured inputs, parallel scans, and a missing `K` chosen during coding.
  - **Verification:** a labelled replay proves no discovery loss at the chosen
    cadence; fixtures prove code, detail, stage/grade, or sampler drift misses
    the cache and that the required full discovery still occurs.
- **Stop / defer:** no seed or implementation is authored. Continue full fresh
  completeness audits.
- **Approach:** `deferred` — a future decision must begin from measured need,
  then select a bounded evidence path before re-scoping implementation.
- **Quality:** `audit-coverage` — any cost reduction remains explicitly bounded
  by evidence that it does not hide a finding.
- **Status:** deferred 2026-08-20 (user-confirmed). Fresh completeness audits
  remain the operating path.

<!-- Superseded 2026-08-19: the following draft bundled an unspecified
cadence, a cross-history decider now deferred as #303, and resolution-label
evidence. It is not an active implementation contract.

- **What:** three loop-shape changes sharing a per-step fingerprint/cache
  substrate: (1) **fingerprint-gated step scans** — key each step's
  conceptual scan on (step frontmatter + detail-file hash + plan-body
  scope-section hash) and reuse the saved scan for unchanged steps
  (the `reconcile-plan --refresh` / #165 posture applied to completeness);
  (2) **anchored re-check mode** — after a hand-apply round, verify the
  previously-open findings against their anchors instead of running full
  discovery; full discovery every K rounds or as the final convergence
  confirmation; (3) **encoded low-yield decider** — N consecutive rounds
  of full prior-closure with strictly decaying materiality auto-labels
  `confirmed-low-yield` (the shipped severity-aware rule extended to round-over-round
  trajectories), instead of an operator hand-rolling the stop rule.
- **Why (measured on jira-grade-01, 2026-07-22):** five audit rounds each
  re-scanned all 9 steps while hand-applies touched 2–4 steps per round —
  most of rounds 3–5's scan spend re-confirmed unchanged steps. By the shipped
  severity-aware rule's
  own logic round 4 (all-fresh findings, 100% prior-round closure,
  materiality down to wording/footprint) already qualified as low-yield;
  the un-encoded rule cost a full extra round. Re-check mode also emits
  per-finding resolution verdicts for operator review.
- **Second, independent instance — 2026-08-07 on `roadmap-view`, and it
  narrows the root cause.** Driving `roadmap-view`'s detail-grounded audit
  by hand across four `completeness-audit --audit-passes 1` invocations (one
  per commit, per CLAUDE.md's mandated Claude-session-driven pattern) produced
  the trajectory 9 → 2 → 2 → 1 material findings, with the final round's
  lone finding self-seeded (a leftover word-count from the prior round's own
  edit, confirmed fixed by a manual repo-wide grep). Every one of the four
  saved reports' `audit_coverage` block shows `confirmation_kind: null` and
  `recommendation_kind: null`, checked directly in the persisted JSON — the
  shipped #125 decider (`audit_plan_until_stable` in `plan_tool/review.py`)
  never fires here, not because the decider is wrong, but because its
  `consecutive_dry` / `dry_streak_grew` streak is **local loop state scoped
  to passes within one process invocation**, and `cap == 1` means the loop
  runs exactly once and can never accumulate a streak to confirm against.
  This is architecturally inert for exactly the operating mode the tool's own
  directives prescribe: `--audit-passes 1` is the CLAUDE.md-recommended
  default for scope-contract-bound audits, and *every* hand-applied,
  session-driven round in this repo's own convergence loop runs that way.
  The gap #173 names is real; this instance pins the precise mechanism —
  the decider needs to compare **against the most recently saved report for
  the same plan** (matched by `plan_slug`, findings diffed by the same
  stable anchor-id `_make_rec_id` already uses for intra-run union), not
  only against sibling passes held in memory this call. Verify this by comparing
  persisted reports from separate invocations, including single-pass audits.
- **Effort:** large — cache substrate, scan-skip wiring, a re-check prompt
  lane, decider logic, coverage-reporting honesty for skipped steps.
- **Risks / fallout:** a stale-cache bug silently narrows audit coverage —
  the report must label every skipped step with the fingerprint it was
  skipped under (no silent caps); re-check mode must not become the only
  lane (discovery cadence is load-bearing); fingerprint field set must
  avoid over-triggering (title reword ≠ rescan; see #165's severity-tier
  note).
- **Dependencies:** pairs with **#165** (same fingerprint family) and the
  shipped severity-aware low-yield rule (the decider extends its rule).
- **Scope contract:**
  - **Outcome:** an audit round after a hand-apply spends Claude only on
    changed steps and open findings, and the loop self-labels low-yield
    convergence under the encoded rule.
  - **In scope:** `plan_tool/completeness_report.py`,
    `plan_tool/cli/completeness_phases.py`/`completeness_cmd.py`, the
    grounding/fingerprint sidecar, prompt for the re-check lane,
    `docs/AUDIT_FLOW.md`, `DATA_CONTRACT.md`, tests.
  - **Out of scope / Non-goals:** weakening any finding or severity;
    parallelizing scans (the serial-by-default architecture rule stands);
    changing `completeness-apply`; a convergence diagnostic.
  - **Allowed behavior changes:** skipped-step reuse with labeled coverage;
    the re-check lane; the auto low-yield label.
  - **Allowed reorganization:** only the cache substrate extraction.
  - **Verification:** a fixture plan where one step changes between rounds
    scans exactly that step; a stale-cache fixture proves the skip label
    names its fingerprint; the jira-grade-01 trajectory replayed as a
    fixture stops at round 4 with `confirmed-low-yield`.
  - **Stop / defer:** cross-plan caching; any `--jobs` fan-out.
- **Approach:** `plan-tool` — multi-module loop redesign with an open
  cadence question (K).
- **Quality:** `audit-coverage` — coverage becomes explicit per-step
  (labeled skips) instead of implicit; `convergence` — the stop rule stops
  depending on operator judgment at the costliest moment.
- **Iterate:** default recipe.

  ```bash
  plan-tool create incremental-completeness-audit --iterate -y --from-existing plan-seeds/incremental-completeness-audit.md
  plan-tool detail incremental-completeness-audit --commit -y
  plan-tool completeness-audit incremental-completeness-audit --iterate --commit -y
  ```
- **Status:** not started; measured evidence in
  `.tmp/jira-grade-01-detail-instrument.audit-process-handoff.md`.

-->

**#256 — Defer automatic analogous-site sweeps pending evidence**

- **What:** do not add a model call after every conceptual-audit pass. The
  mandated manual Check 0 identifier-and-vocabulary sweep remains the current
  class-wide application control.
- **Future trigger:** reconsider only if a labelled corpus demonstrates both
  that the manual sweep lacks a deterministic locator and that bounded
  candidate suggestions improve complete class sweeps.
- **First permissible cut, if triggered:** advisory candidate locations only:
  no automatic persistence as `related_sites`, no changed finding identity,
  no schema change, and no new per-pass Claude call.
- **Scope contract:**
  - **Outcome:** a recorded evidence decision to keep manual Check 0 or to
    author the small advisory candidate experiment.
  - **In scope:** a labelled comparison of complete manual sweeps with a
    bounded deterministic-locator/candidate method.
  - **Out of scope / Non-goals:** a new audit subphase, automatic carry-forward
    enrichment, `Recommendation` or sidecar changes, inference from prose,
    and automatic application or code edits.
  - **Verification:** the corpus measures locator coverage, false candidates,
    and whether the complete sweep improved; a plausible anecdote is not
    sufficient.
  - **Stop / defer:** absent that result, leave the manual sweep explicit and
    close this entry as deferred rather than adding an unproven automation.
- **Approach:** `decision first` — validate that an automatic helper adds value
  before it changes the convergence-sensitive audit loop.
- **Status:** deferred pending labelled corpus evidence.

<!-- Superseded 2026-08-19: the following design adds an unproven Claude
subphase and persistent class inference. It is not an active implementation
contract.

- **What:** after every *successful conceptual-audit pass*, take that pass's
  newly discovered, anchored, in-scope `plan-correctness` and
  `plan-completeness` findings as one bounded batch and run a focused,
  read/grep-only **finding-impact sweep**. For each original finding, search
  both by identifier (named symbols, files, flags, or APIs) and by the finding
  concept's vocabulary, then return only verified repository locations that
  exercise the same contract: duplicate logic, parallel call sites, sibling
  implementations, the tests that oblige the behavior, and documentation that
  restates the contract. The sweep enriches the *existing* finding with its
  class-wide extent and either says all locations belong in the plan or marks a
  location `defer` with the scope reason. It never mints a second conceptual
  finding merely because the first one has several sites.
- **Why:** `audit_plan_until_stable` already gives later passes the prior
  finding list and asks them to find the concepts it has not covered, but it
  has no explicit post-finding operation that asks, "where else does this
  exact rule live in the code?" The plan-audit prompt only tells the proposed
  **plan/detail fix** to cover sibling *plan* sites; the run-reconcile prompt
  separately tells a code-drift reviewer to report a defect class across all
  code sites. A conceptual finding can therefore identify a real missing or
  unsound rule at one concrete site, carry a narrow one-site fix into
  `completeness-apply`, and force a later pass to rediscover the same defect at
  a sibling. That reads as non-convergence when the actual failure was
  under-scoping the first finding. The existing foundational-logic sweep has
  the right search vocabulary (duplicate / parallel-call-site /
  sibling-implementation), but is an opt-in create/detail authoring aid with a
  plan-or-step-shaped output; it is not wired to the conceptual audit's
  finding identity, pass union, carry-forward context, or saved sidecar.
- **Pass contract — sequence and call discipline:**
  1. Run `check_plan_audit` exactly as today, including its own malformed-output
     retry if needed, and parse the two conceptual finding lists.
  2. Diff that parsed output against the pass-start union by stable finding id.
     Select every new finding with an `[anchor-slug]` and no
     `[out-of-scope-deferred]` marker, across both conceptual axes. A pass with
     no selected findings spends **no** extra Claude call.
  3. Make exactly one batch sweep call for the selected findings. Its prompt
     receives each finding's stable id, anchor, axis, prose, suggested fix,
     plan/seed scope fence, current plan/detail bundle, and the same repository
     root at HEAD; it must return structured rows keyed back to the supplied
     finding id. The result may add sites only to a supplied id — a new gap,
     a renamed anchor, or a free-standing recommendation is invalid output.
  4. Validate every returned repo-relative path on disk and require a symbolic
     anchor plus a relation and an in-scope `update-in-place` / `consolidate`
     or scope-fenced `defer` disposition. Invalid rows are dropped
     independently; an unusable whole response is best-effort, warns, and
     leaves the primary audit finding unchanged.
  5. Merge accepted rows into the original `Recommendation` before rendering
     the pass union line, calculating materiality/newness, persisting the
     sidecar, or assembling `CarriedFinding` records. The next conceptual pass
     therefore sees the finding's known extent and is instructed to audit what
     it has **not** covered, rather than rediscovering the same class at one
     sibling at a time.
- **Convergence invariants:** the primary audit's stable id remains the sole
  identity for unioning, `--anchor`, annotations, and `completeness-apply`.
  Related-site rows are evidence attached to that id, not recommendations and
  not a source of extra `new` count, severity, materiality, dry-streak reset,
  or arm-clustering membership. Re-finding an existing id on a later pass does
  not re-sweep it; first valid evidence wins unless a deliberate future
  freshness rule replaces it. The extra sweep may improve the prose/extent of
  a finding, but it must not make a previously dry pass productive or turn a
  clean stop into a budget-limited one. A failed sweep is neutral on exactly
  the same principle as an unavailable optional advisory: it cannot be read as
  proof the primary finding has no siblings.
- **Presentation and persistence:** add an optional, additive structured
  `related_sites` field on conceptual recommendations, with path, symbolic
  anchor, relation, disposition, and a short evidence note. Render a compact
  "also applies at" extent under the original finding in the grouped report,
  saved markdown, JSON, carried-findings block, and the
  `completeness-apply` / `apply_finding` context so an apply is deliberately
  class-wide. Preserve legacy sidecars with an absent field, document the
  read/write contract in `DATA_CONTRACT.md`, and ensure an old or malformed
  optional field cannot block a walk. The terminal must separately show the
  per-pass `finding-impact sweep` start/heartbeat/done line and record it as a
  distinct run-log phase, so the additional cost is visible rather than hidden
  inside `plan_audit`.
- **Effort:** large — it adds one Claude subphase to the bounded
  `audit_plan_until_stable` loop, a strict structured-output parser and
  validator, additive recommendation/sidecar/report data, carried-prompt
  rendering, progress/run-log accounting, and focused unit/integration
  coverage across the audit's most convergence-sensitive code path.
- **Risks / fallout:** a broad prompt will turn one finding into an excuse for
  repo-wide cleanup, so the sweep must receive and enforce the existing scope
  contract, preserve `done`-step immutability, and defer rather than expand a
  non-goal. A loose association heuristic can fabricate siblings and make a
  plan look larger or more urgent than it is; rows without disk-verifiable
  path/symbol evidence must disappear, not reach an apply prompt. The second
  call can double the conceptual Claude spend in finding-rich passes; batching
  only newly surfaced findings, skipping empty passes, one sweep per pass, and
  displaying its cost are load-bearing. Do not silently repurpose
  `foundational_logic.py`'s create/detail schema: its `step_id` and
  consolidation-step proposal semantics are not a safe representation of a
  saved conceptual finding.
- **Dependencies:** none hard. **Related:** #173's fingerprint-gated
  per-step scan/re-check work changes what a pass reads and may later need a
  fresh-related-sites policy; it must not be absorbed here. #66's deterministic
  contract-trace mode is complementary (mechanical enumeration versus this
  evidence-grounded semantic sweep). The existing `foundational_logic.py`
  parser/invoker helpers may be reused only if their contracts fit without
  changing create/detail behavior; otherwise keep a narrow audit-owned shape.
- **Scope contract:**
  - **Outcome:** every new, actionable conceptual finding receives one explicit
    same-pass search for other verified code/doc/test sites sharing its
    contract, and later passes/apply see the resulting class-wide extent under
    that finding's unchanged stable id.
  - **In scope:** `plan_tool/review.py` (`Recommendation`, conceptual-pass
    orchestration, prompt rendering/parsing, carry-forward); a new
    `plan_tool/prompts/finding-impact-sweep.md`; completeness progress and
    timeout wiring in `plan_tool/cli/completeness_phases.py`; persisted review
    serialization/reporting in `plan_tool/review_persistence.py` and
    `plan_tool/completeness_report.py`; `DATA_CONTRACT.md`,
    `docs/AUDIT_FLOW.md`, and focused review/completeness/persistence/run-log
    tests.
  - **Out of scope / Non-goals:** changing the deterministic completeness
    detectors; retrying the primary audit or changing `--audit-passes`,
    `new_threshold`, low-yield, materiality, or convergence diagnosis; a sweep
    after deterministic iterations, after `completeness-apply`, or as a new
    standalone user command; automatic code edits, automatic application of
    advisory completeness gaps, or new plan steps; generic duplication cleanup
    unrelated to a supplied finding; a cache/freshness strategy for prior
    related-site results (#173 or a separate entry owns that decision);
    changing create/detail's foundational-logic experiment.
  - **Allowed behavior changes:** each successful conceptual pass with at least
    one newly found, actionable anchored finding may make one additional,
    visible, read-only Claude call; reports, saved sidecars, carried context,
    and the interactive apply prompt may display verified related-site extent
    beneath the original finding. Nothing applies or mutates a plan/code file
    merely because the sweep ran.
  - **Allowed reorganization:** none by default. A small private helper shared
    only by the audit prompt renderer/parser is allowed if duplicated
    validation would otherwise make the stable-id merge inconsistent; do not
    extract a general sweep framework.
  - **Verification:** hermetic invoker tests prove (a) a two-pass audit calls
    the sweep once for each pass that contributes a new eligible anchor, (b)
    the sweep receives only the new ids and scope fence, (c) valid path/symbol
    rows enrich the original rec while preserving its id, axis, severity, and
    new-count/materiality result, and the enriched extent is carried into the
    next audit prompt, (d) a repeated id, empty pass, unanchored finding, or
    explicit out-of-scope deferred finding emits no sweep call, (e) malformed
    JSON, a foreign id, nonexistent path, missing symbol, invalid relation, or
    failed sweep produces a warning but leaves primary-audit convergence and
    findings unchanged, (f) JSON/markdown sidecars round-trip the optional
    field and legacy/malformed fields remain walkable, and (g) one focused
    integration fixture shows `completeness-apply` receives one class-wide
    finding with all verified sites rather than several sibling findings.
    Assert the separate progress/run-log phase and its one-call-per-eligible-
    pass budget. Run the full suite after the data-model change.
  - **Stop / defer:** if experiments show the sweep mostly repeats evidence
    already present in the primary audit or materially harms audit precision,
    remove the subphase rather than weakening the scope/evidence rules; retain
    the measurement in this entry. A need for cross-invocation revalidation,
    code execution, generalized duplication detection, or changed convergence
    policy becomes a separate backlog entry.
- **Approach:** `plan-tool` — this is a multi-module, persisted-contract change
  to the audit loop, with a new Claude phase and convergence invariants that
  need a stepwise plan rather than a direct patch.
- **Quality:** `audit-coverage` — turns a discovered conceptual defect into a
  checked class of verified sites instead of trusting the first site the audit
  noticed; `grounding` — every added extent claim must be rooted in code at
  HEAD; `convergence` — prevents false-looking repetition caused by
  one-sibling-at-a-time fixes without altering the stopping policy itself.
- **Iterate:** use the default author/detail/audit/run/post-audit recipe; the
  plan's own conceptual-audit detail is load-bearing and should be exercised
  with at least a two-pass stubbed fixture before real Claude validation.

  ```bash
  plan-tool create conceptual-pass-impact-sweep --iterate -y \
    --from-existing plan-seeds/conceptual-pass-impact-sweep.md
  plan-tool detail conceptual-pass-impact-sweep --commit -y
  plan-tool completeness-audit conceptual-pass-impact-sweep --iterate --commit -y
  plan-tool detail conceptual-pass-impact-sweep --reconcile --step N --commit -y
  plan-tool run conceptual-pass-impact-sweep -y --step N
  plan-tool run conceptual-pass-impact-sweep --mode reconcile --iterate -y --step N
  plan-tool completeness-audit conceptual-pass-impact-sweep --iterate --commit -y
  ```
- **Status:** not started.

-->

<!-- Superseded 2026-08-19: the following draft assumed anchor identity was
adequate for a cross-invocation confirmation verdict. It is not an active
implementation contract.

- **What:** a small, zero-Claude slice of #173's third piece ("encoded
  low-yield decider"), separable from that entry's larger fingerprint-gated
  scan cache and anchored re-check lane. `plan-tool convergence <name>`
  already loads a plan's full saved report history
  (`convergence_diagnosis.load_report_history`) to print its current
  convergence state, read-only, zero-Claude, and always exits 0. This entry
  adds a **second, independent** printed signal to
  that same command: whether the audit loop across the plan's saved reports
  looks `confirmed-dry` / `confirmed-low-yield` / `still-open` /
  `insufficient-history` — reusing `audit_plan_until_stable`'s existing
  productive/`low_yield_reason`/`dry_streak_grew` classification (BACKLOG
  #125, `plan_tool/review.py`), but computed over **saved report snapshots
  for the plan** instead of in-memory passes within one process. Diff each
  consecutive pair of saved reports' `recommendations` by the same stable
  anchor-id `_make_rec_id` already uses for intra-run union; apply the
  identical severity-aware rule to that sequence.
- **Why now — this is the CLI surface the operator needs and does not have.**
  Measured 2026-08-07 driving `roadmap-view`'s detail-grounded audit by hand
  across four separate `plan-tool completeness-audit --audit-passes 1`
  invocations (CLAUDE.md's mandated pattern for Claude-session-driven work):
  every saved report's `audit_coverage.confirmation_kind` read `null` —
  checked directly in the persisted JSON — because that field's dry-streak
  state is scoped to passes *within one invocation*, and `cap == 1` means the
  loop runs once and never accumulates a streak. The operator judgment this
  session made by hand (read four report files, compare finding counts and
  content: 9 → 2 → 2 → 1, decide the last round was low-yield) is exactly
  what a CLI query should answer in one command, at zero cost, since every
  saved report the comparison needs is already on disk.
- **Honest limit — this does not solve the judgment call it looks like it
  solves.** The existing #125 rule counts a round as low-yield only when its
  new findings are *all* `low`/`info`/`nit` severity; a `medium`-severity
  finding never qualifies, regardless of how trivial its actual content
  turns out to be. This session's own round 4 is the concrete case: one
  `MEDIUM` finding (`[citation-map-field-count]`), mechanically trivial (a
  leftover word left unswept from the prior round's own edit) but not
  low/info/nit by the auditor's own severity label. Under this entry's exact
  mechanism, that round would report `still-open`, not `confirmed-low-yield`
  — correctly reflecting what the severity label says, not what a human
  reading the finding's prose would conclude. This entry automates the
  **mechanical trajectory read** (counts, stable severity-classified streak
  across saved reports); it does not, and must not, attempt to classify a
  finding as "really" trivial despite its stated severity — that stays a
  human/session judgment call, per `self-seeded-finding`'s `judgment_only`
  status in CLAUDE.md's audit-shapes table. Say so in the printed output
  (e.g. "severity-labeled, not content-judged") so an operator does not
  over-trust a `still-open` read as proof another round will find something
  real, the way an under-triaged severity can make it look that way.
- **Effort:** small — a diff-and-classify function reusing #125's existing
  predicate, wired into `cmd_convergence`'s already-loaded report history;
  no new caching substrate, no new prompt lane, no new Claude call, no new
  CLI verb.
- **Risks / fallout:** anchor-id stability across *separately generated*
  audit runs is not airtight — the model free-generates each finding's
  `[anchor-slug]` per invocation, and while a genuinely recurring issue
  usually reproduces the same slug, it is not guaranteed the way intra-run
  dedup is.
  A slug drift on an otherwise-resolved finding would read as "new" and
  under-report the trajectory's true convergence — verify against a fixture
  with slug drift before shipping, not just the clean case. Two verdicts
  reported by one command (this signal + the existing mis-decomposition
  diagnosis) must stay visibly separate, never merged into one line.
- **Dependencies:** none hard on #173 landing first — this is a strict subset
  of its third piece, factored out precisely so it does not wait on the
  larger caching/re-check machinery. #173's remaining two pieces (scan cache,
  anchored re-check lane) stay a separate, larger entry.
- **Scope contract:**
  - **Outcome:** `plan-tool convergence <name>` prints a second, clearly
    labeled signal — the cross-invocation audit-confirmation verdict over
    the plan's saved report history — alongside the current convergence state,
    at zero Claude cost.
  - **In scope:** `plan_tool/cli/convergence_cmd.py` (the added print),
    `plan_tool/review.py` (factoring the existing productive/low-yield
    predicate so it can run over saved-report pairs, not only in-memory
    passes), `docs/AUDIT_FLOW.md`, `DATA_CONTRACT.md`, tests.
  - **Out of scope / Non-goals:** the fingerprint-gated scan cache and the
    anchored re-check prompt lane (#173's other two pieces); any new Claude
    call; any new CLI verb or flag beyond the added print; classifying a
    finding's *content* as trivial independent of its stated severity;
    merging this signal into, or replacing, the existing mis-decomposition
    verdict; any exit-code change (`convergence` stays always-0).
  - **Allowed behavior changes:** one new printed signal on
    `plan-tool convergence`'s existing output. Nothing else user-visible.
  - **Allowed reorganization:** factoring `audit_plan_until_stable`'s
    classification predicate into a reusable function is allowed; no other
    move.
  - **Verification:** replay this session's four `roadmap-view` reports as a
    fixture — the sequence must report `still-open` after round 4 (the
    `MEDIUM` case above), not `confirmed-low-yield`, pinning the honest-limit
    behavior rather than a more "helpful"-looking but false positive; a
    fixture whose last two rounds add only `low`/`info`/`nit` findings must
    report `confirmed-low-yield`; a single-report plan must report
    `insufficient-history`; a fixture with a deliberately drifted anchor-slug
    on an otherwise-closed finding must not silently misreport (name the
    drifted id, don't just miscount).
  - **Stop / defer:** #173's scan-cache and re-check-lane pieces stay filed
    there, not pulled in here on the way past.
- **Approach:** `direct` — one function factored for reuse, one CLI print,
  tests.
- **Quality:** `convergence` — gives the mandated hand-apply workflow the
  same stop signal the tool already computes for multi-pass invocations,
  without inventing a new judgment the tool cannot make.
- **Origin:** 2026-08-07, split out of #173 at user request after this
  session measured `confirmation_kind: null` across all four of
  `roadmap-view`'s hand-driven audit rounds.
- **Status:** not started.

-->

**#175 — Jira-readiness audit lane: goal-directed, ticket-blocking findings only, deterministic-first**

- **What:** a fast audit lane (`jira-readiness <name>`, or
  `completeness --jira`) that judges a detailed plan against one
  question — *can each step be handed to an implementer as an atomic
  story?* — instead of exhaustive conceptual completeness. Four checks,
  cheapest first: (1) **deterministic anchor verification** — extract the
  grep-verifiable code claims detail files make about HEAD (backticked
  paths, symbols, config keys, version pins in Input / "verified at
  HEAD" sections) and verify them against the repo with no model call,
  reporting only broken anchors; (2) **frontmatter↔detail footprint
  coherence** — each step's `files:`/`creates:` lists match the detail's
  declared footprint, including detail-flagged "noted additions";
  (3) **decided-scope compliance** — findings whose remedy falls inside a
  plan's explicit decided/guardrail sections (a decided threat model, a
  hard-boundary file list) are auto-rejected and logged as
  `rejected-by-decided-scope`, not surfaced as gaps; (4) **ticket-blocking
  triage** — only contradictions, deliverables with no owning step, and
  test suites with no runnable owner block; everything else is advisory.
- **Why (evidence 2026-07-22, example-app `mobile-initial-release-password-gate`):**
  a full completeness-audit round costs 30+ min and its conceptual sweep
  re-derives already-decided scope — the plan's first incarnation spun 3
  rounds re-surfacing pool-level-enforcement findings the re-scoped plan
  had explicitly decided against (the re-scope wrote a "decided threat
  model — do not re-derive" section precisely to fence this, but no audit
  lane reads it). A hand audit reached jira-ready confidence in ~10 min:
  read 9 detail files, batch-grep-verified ~35 HEAD anchors (all held),
  found exactly one ticket-blocking gap (step 8's detail declared a test
  file absent from the step's `creates:` — check 2), and dismissed
  vocabulary false positives (the suppression-shape smell tripping on a
  feature literally named "gate" with "bypass" semantics). Everything
  that mattered for story generation was deterministic or
  near-deterministic; the expensive conceptual sweep contributed nothing
  at that stage.
- **Effort:** medium — checks 1–2 are extraction + file/grep work (the
  detail format's backticked-citation convention is already
  near-machine-readable); check 3 needs a marker convention for decided
  sections plus a filter in the finding pipeline; check 4 is a triage
  policy on existing finding kinds.
- **Risks / fallout:** anchor extraction can misread speculative prose as
  a HEAD claim — scope extraction to citation-bearing sections (Input,
  acceptance-criteria greps) and treat "dependency contract" /
  "verification limit" labels as exempt; the decided-scope filter could
  suppress genuine findings if guardrail sections are abused — reject
  only findings whose remedy is inside the explicit boundary list, log
  every rejection visibly, and never filter correctness findings *within*
  the decided scope.
- **Dependencies:** complements **#173** (fingerprint-gated completeness
  — that caches the expensive lane, this adds a cheap goal-directed
  lane); output could gate `jira` story generation (green
  jira-readiness before export). It remains independent of the terminal
  developer-handoff projection in #293.
- **Scope contract:**
  - **Outcome:** a jira-gating audit verdict produced in minutes without
    a full conceptual sweep, reporting only ticket-blocking findings,
    each labeled with the check that produced it.
  - **In scope:** a new audit lane/verb and its report format; anchor
    extraction over `DETAIL_FORMAT.md`-shaped detail files; a
    decided-section marker convention documented in `PLAN_FORMAT.md`;
    triage policy for the lane; tests with a fixture plan.
  - **Out of scope / Non-goals:** changing the full completeness audit's
    behavior or prompts; #173's caching substrate; the suppression-shape
    smell's domain-vocabulary false positives (separate heuristic-tuning
    entry if pursued); auto-fixing findings.
  - **Allowed behavior changes:** the new verb/flag and its report;
    `jira` may learn an advisory warning when the lane has not been run.
  - **Allowed reorganization:** none.
  - **Verification:** on a fixture plan with (a) one broken anchor,
    (b) one undeclared detail-noted file, (c) one finding inside a
    decided boundary, the lane reports exactly (a) and (b) as blocking
    and (c) as rejected-by-decided-scope, with zero model calls for
    checks 1–2.
  - **Stop / defer:** convergence-verdict interaction (a no-progress trend
    driven by re-audits with no intervening edits is BUG_BACKLOG territory);
    story-quality linting beyond what `jira --lint` already
    does; the smell-vocabulary tuning.
- **Approach:** `plan-tool` — the anchor-citation and decided-section
  conventions are cross-cutting format design; the deterministic checks
  alone would qualify for `direct`, but landing them without the
  conventions bakes in ad-hoc parsing.
- **Quality:** `audit-coverage` + `gate-signal` — a deterministic
  complement to the sampled conceptual audit, aimed at the one exit
  signal (`jira` export) that hands work to humans; `grounding` — anchor
  verification keeps detail claims tied to HEAD at story-generation time.
- **Iterate:** default recipe.

  ```bash
  plan-tool create jira-readiness-audit-lane --iterate -y --from-existing plan-seeds/jira-readiness-audit-lane.md
  plan-tool detail jira-readiness-audit-lane --commit -y
  plan-tool completeness-audit jira-readiness-audit-lane --iterate --commit -y
  ```
- **Status:** not started. Use the example-app-amplify password-gate plan at
  `docs/implementation-plans/2-mobile-initial-release-password-gate.md` as a
  representative case: its decided scope, detail bundle and Jira-story artifacts
  show the readiness questions this lane must address.

**#163 — Claude-judged fold detector for dropped guardrail sections**

- **What:** when the shipped preservation check fires (seed carried heading H,
  body lacks H — `create.py:_find_dropped_guardrail_headings`), a bounded model
  judgment on whether H's substance
  was *materially folded* into another section or genuinely lost — verdict per
  missing section, nothing more.
- **Why:** the observed incident had both shapes. `Audit guardrails` was
  dropped outright (deterministic check catches it), but `Scope guardrails`
  and `Expected placement` were **folded into `Architecture`** as unstructured
  prose — heading absent, content arguably present. The deterministic check
  reports both identically, so the fold case produces a finding the author
  will correctly read as noise, and repeated noise trains the fence off.
- **Design sketch — the anti-creep constraints are the design.** Three, all
  load-bearing:
  1. **One-way valence, enforced in the output schema.** The judge may only
     report *loss relative to the seed*. Fixed record per missing section:
     `verdict ∈ {preserved-elsewhere, weakened, dropped}` + the body section
     it was folded into + the seed span. There is **no field** in which to
     write "the scope should also cover X", so expansion is not discouraged,
     it is unrepresentable. This is the whole reason the entry is safe to
     build; without it, a "check the scope for gaps" call is an unbounded gap
     generator pointed at the fence it is supposed to protect.
  2. **Closed cardinality.** Output length = number of seed guardrail
     headings missing from the body. Zero missing → zero tokens, zero
     findings.
  3. **Deterministic-first gating.** Exact heading match → no call. Tier 2
     fires only on the ambiguous absent-heading case. Most runs never reach
     it. (The cut-work-before-spending rule in `CLAUDE.md`.)
  Posture matches `granularity.py`: advisory `info`, out of
  `APPLY_ELIGIBLE_SOURCES`, recommend-only, never flips an exit code.
- **Effort:** small — the tier-1 check it layers on already exists, so this is
  a second tier on live behavior rather than speculative work.
- **Risks / fallout:** this is a scope-judging Claude call, i.e. the exact
  shape that creeps. The three constraints above are not style preferences;
  relaxing any one of them (open-ended prompt, unbounded output, always-on)
  reproduces the failure mode. If review can't hold them, **don't build it** —
  the deterministic check alone is a real improvement over today.
- **Dependencies:** none — tier 1 (the deterministic preservation warning)
  shipped as `2-scope-fence-continuity`.
- **Scope contract:**
  - **Outcome:** a folded-but-present guardrail section is reported
    differently from a genuinely dropped one.
  - **In scope:** the tier-2 judgment, its prompt, its fixed output schema,
    the finding source, and tests.
  - **Out of scope / Non-goals:** proposing scope *additions* in any form;
    judging whether the scope is correct, sufficient, or has "gaps"; any
    verdict about the plan other than per-missing-section preservation; a
    general-purpose scope auditor; auto-applying anything.
  - **Allowed behavior changes:** one additional bounded Claude call on
    plans where a guardrail heading is missing.
  - **Allowed reorganization:** none.
  - **Verification:** a fixture where the seed's `Scope guardrails` is folded
    into `Architecture` yields `preserved-elsewhere` naming that section; a
    fixture where `Audit guardrails` is absent entirely yields `dropped`; a
    plan with all headings present makes **no call at all** (assert the
    invoker is never invoked).
  - **Stop / defer:** any request to widen the verdict vocabulary beyond the
    three values, or to let the judge comment on scope adequacy, is a
    rejection — not a new entry.
- **Approach:** `direct`.
- **Quality:** `convergence` — this closes the preservation check's
  false-positive tail rather than adding new judgment surface.
- **Priority note:** gated on evidence rather than on order. #162 (shipped
  2026-08-19) grounds the audit deterministically and spends no extra Claude;
  this spends a call to refine a finding's phrasing. The deterministic
  preservation check is live, so the question is answerable: **count how
  often its warning fires on a folded section rather than a dropped one.** If
  that tail is not actually noisy, do not build this.

**#97 — Symbol-aware prompt file excerpts + per-step embed budget (replace head-only 4 KB)**

- **Principle:** `keep-the-plan-true-to-code` — the T3 band: prompt excerpts grounded in the live code.
- **What:** Replace blind `body[:4096]` head clipping in prompt file-embedding
  with a **shared excerpt strategy** and a **per-step byte budget** across all
  declared files — so inlined context is *relevant* and *bounded*, not merely
  the top of every file. Unify the five copies of the same pattern
  (`detail._format_files_contents_block`, `review` file/detail blocks,
  `jira._render_step_files_contents`, `annotate._bound_for_block`,
  `review._format_audit_detail_bundle` / `_AUDIT_DETAIL_FILE_BYTES`).
- **Why:** The 4 KB cap exists to prevent **N files × full file size** from blowing
  the context window — a real failure mode. But head-only truncation systematically
  misses the code regions a step actually touches (implementations at the bottom of
  large modules). Worse: **15 × 4 KB of partial previews** can feel informative
  while being wrong. Detail/audit surfaces recover when the model Read/Greps
  (review's Read/Grep gap is closed); this item makes the **inline preview** itself
  useful when tools are used or skipped. `annotate` already labels truncation and
  asks for `confidence_low` past the cut — the excerpt leaf should reuse that
  posture (explicit marker, never silent clip).
- **Proposed design (spike before implementation):**
  1. **New stdlib-only leaf** `plan_tool/prompt_excerpt.py` (or extend a single
     `prompt_embed.py` leaf): given `(path, body, step_context, budget_bytes) →
     ExcerptResult(text, truncated, strategy)`.
  2. **Excerpt priority** (deterministic, no Claude):
     - Always include: file header region (imports / module docstring — first
       ~512–1 KB or to first blank line after imports).
     - Add: grep hits for symbols already known from `step.title`, `step.files`
       basenames, and `heuristic_already_done` / existing review heuristics
       (reuse `review.py` token patterns where cheap).
     - Fill remaining budget with head or tail windows around hits; never exceed
       per-step total (default TBD — e.g. **32–48 KB per step** across all files,
       tunable; per-file floor so one giant file can't starve siblings).
  3. **Keep `_MAX_PROMPT_FILE_BYTES` as a per-file ceiling** but raise modestly
     (e.g. 8–16 KB) only where tools are mandated (detail, audits); keep lower
     on jira/export if unchanged behavior is desired.
  4. **Surface policy table** (document in module docstring + `RUNBOOK.md`):

     | Surface | Tools mandated? | Inline embed role |
     |---------|-----------------|-------------------|
     | `detail` / `detail-quality` | yes | orient + symbol anchors |
     | `plan-audit` / completeness | yes | bundle summary |
     | `review` / reconcile | yes | preview until Read |
     | `jira` | no | structural — keep conservative |
     | `annotate` | partial | grounding — keep label on cut |
     | `run` (`renderer._load_detail`) | N/A (execution) | **full detail today** — document asymmetry; optional follow-up cap (folded here from **#95**) |

  5. **Operator signal:** when excerpting drops >50% of a declared file or any
     symbol hit lies past the cut, include `_(truncated; Read/Grep for full file)_`
     and count toward **#95** advisory.
- **Effort:** medium–large — shared leaf + migrate five call sites + fixture
  tests for excerpt selection (large file with symbol at line 2000, multi-file
  budget starvation, audit bundle N×step).
- **Risks:** excerpt heuristics false-negative (miss the relevant symbol) —
  mitigate with grep-based hits, not title-only guessing; test against real
  plan-tool modules (`review.py`, `create.py`) as fixtures. Raising caps without
  per-step budget reintroduces context overflow — **#95** (the pre-send budget
  advisory) has shipped, so its operator visibility is already in place.
  `gates.py` uses `_DETAIL_HEAD_CHARS = 4000` for a different purpose
  (gate prompts, not claude file embed) — don't conflate.
- **Dependencies:** review Read/Grep contract shipped;
  **#95** (budget advisory) — **shipped**, so operator visibility is in place
  when excerpts still clip; `plan_tool/telemetry.py` is the optional recording
  surface for tuning signals such as `embed_truncated_files` and `embed_bytes`.
- **Approach:** `plan-tool` — excerpt strategy and per-surface policy are design
  choices worth a plan; touches detail, review, jira, annotate, completeness.
- **Quality:** `grounding` — replaces head-only 4 KB previews with symbol-aware,
  budget-bounded excerpts so the inline context shows the code regions a step
  actually touches, not just the top of every file.
- **Iterate:** default recipe; spike the excerpt priority in a plan step before
  migrating all call sites.
- **Status:** partial — the shared `prompt_excerpt.build_prompt_excerpt` leaf has
  shipped and is wired into all five surfaces (`review` ×3, `annotate`, `jira`,
  `detail`). **Remaining:** the per-step embed budget is unbuilt — each surface still
  caps every file individually at `_MAX_PROMPT_FILE_BYTES = 4096` with no cross-file
  per-step byte budget or per-file floor.
- **Origin:** 2026-07-06 — concern that `_MAX_PROMPT_FILE_BYTES = 4096` head-only
  embedding produces incomplete assistant analysis; design discussion concluded
  "truncate smarter + mandate tools" beats "remove the cap" or "raise 4 KB globally."

**#98 — Rate-limit handling under parallel workers: non-interactive policy under `--jobs N` (de-dup half → #136)**

- **What:** The interactive rate-limit recovery (prompt + key-polling wait) is now
  thread-serialized by a shared `claude_errors.RATE_LIMIT_PROMPT_LOCK`, so parallel
  workers (`detail` / `completeness-apply --jobs N`, which share one process-global
  stdin) can no longer corrupt the terminal by driving `input()`/termios
  concurrently. That fix (landed 2026-07-06) stops the corruption but leaves two
  follow-ups:
  - **Non-interactive under `--jobs N`:** with the lock, N rate-limited workers now
    prompt *sequentially* — the operator is asked N times. Parallel apply/detail
    should resolve the rate-limit policy **once** (or force a non-interactive
    wait/STOP) rather than re-prompting per worker. Cleanest is to thread a
    "non-interactive" signal into the invoker so `_can_prompt_on_rate_limit()`
    returns False in worker context even on a TTY, mirroring how `--jobs N`
    already pre-resolves `_confirm_replace`/`_confirm_resume` serially.
  - **De-dup the forked helpers → tracked at #136.** The near-verbatim copies of
    `_can_prompt_on_rate_limit` / `_select_rate_limit_backend` /
    `_ask_rate_limit_action` across `shell.py` and `launcher.py` are the remaining
    seam-extraction work now owned by **#136** (post-#101 `rate_limit_loop`
    extraction). This entry keeps only the non-interactive-policy half above.
- **Effort:** small (the non-interactive signal touches the invoker call sites in
  `detail.py` / `completeness_apply_parallel.py`). **Approach:** `direct`.
- **Dependencies:** the landed `RATE_LIMIT_PROMPT_LOCK` fix; interacts with the
  `BUG_BACKLOG.md` entry "`--on-rate-limit switch`/`ask` silently collapse to
  `stop`" (fix that policy plumbing first so the shared helper carries the correct
  4-way behavior).
- **Origin:** 2026-07-06 — high-effort workflow code-review of
  `read-only-audit-split`; the TTY-collision finding plus the shell/launcher
  duplication finding.

**#107 — Deferred: project-configurable story layer vocabulary**

- **Principle:** `none` — deferred; export vocabulary with no demonstrated blocker.
- **Decision (2026-08-19): defer.** Do not add a story-layer schema,
  model-assisted discovery, path inference, or generalized user-facing-tier
  behavior before a non-web Jira export shows that the fixed vocabulary blocks
  a user from producing a usable artifact.
- **Trigger:** preserve the failing export and the project-specific vocabulary
  it requires. A hypothetical service, mobile, or data-only repository is not
  a trigger.
- **If triggered:** begin with an explicit operator configuration for that one
  project. Keep model discovery, path inference, and cross-project
  generalization out until the minimal configuration proves insufficient.
- **Reason:** this is premature generalization, not an observable-property
  failure. The former combined feature assumed consumers and a configuration
  model before either existed.
- **Status:** deferred pending a demonstrated non-web Jira-export blocker.

**#90 — `--worktree` convenience on `run` / `detail` (provision-and-execute in one call)**

- **What:** A `--worktree` flag on `run` (and `detail`) that provisions the plan's
  isolated workspace (the same path/branch resolution `worktree add` does) and then
  executes the command *inside* it in one invocation — so an operator kicks off a
  parallel plan run without a separate `worktree add` + `cd` first. Kept **separable**
  from the `worktree add` primitive: `add` stays the pure provisioning verb, and
  `--worktree` composes it with execution rather than duplicating the resolution logic.
- **Why:** The shipped `worktree` group is provision-then-`cd`-then-run — three steps.
  For the common "run plan B in its own worktree" ask, a single `plan-tool run B
  --worktree` is the ergonomic path, mirroring how `run --switch-branch` folds branch
  provisioning into the run. The primitive already exists; this is pure convenience
  sugar over it.
- **Effort:** small–medium; the resolution (`derive_worktree_path` / `_resolve_branch`
  / `_resolve_start_point` / `_reuse_or_fail`) is already factored in
  `plan_tool/cli/worktree_cmd.py` — the flag reuses it, then re-dispatches the command
  with the worktree as the cwd/repo-root.
- **Risks:** the executed command must resolve *the worktree's* manifest (per-cwd
  discovery), not the main tree's; a dirty/foreign path at the derived location must
  fail the run the same way `worktree add` refuses it, not run against the wrong tree;
  the flag must not silently re-provision when the plan isn't committed on the base
  branch (the per-branch caveat).
- **Dependencies:** `plan_tool/cli/worktree_cmd.py` (the provisioning + resolution
  helpers), `plan_tool/cli/run_cmd.py` / the `detail` entry (where the flag wires in),
  `locator.py` (per-cwd manifest discovery for the re-dispatch).
- **Approach:** `plan-tool` — spans two command surfaces plus the provisioning seam and
  needs test coverage for the resolve/reuse/fail and per-branch-visibility paths.
- **Iterate:** default recipe.
- **Origin:** 2026-07-05 — deferred from the `parallel-plan-worktrees` plan's
  `## Deferred`, which shipped the `worktree add`/`list`/`remove`/`prune` primitives and
  intentionally kept the provision-and-execute convenience out of that scope.

**#74 — Speed up `detail --iterate` (and the create/completeness loops): remaining caching + parallelism levers**

- **Principle:** `none` — a throughput lever; the cheap slice already shipped.
- **What shipped:** the cheap slice (2026-06-25 — stable-prefix prompt
  reorder, complexity-scaled audit cap, `--detail-only` bulk opt-in,
  re-dispatch dedup) and the authoring-only parallelism slice (B1 `detail
  --jobs N`, 2026-07-04; B2 `completeness-apply --jobs N`, 2026-07-06,
  including its run-log ordered-flush fix 2026-07-17). Usage-capture landed
  2026-07-04, which let a real measurement run: A1's stable-prefix reorder
  already banks ~80% cache-hit rate, so A2 (session reuse) and A3 (direct-API
  invoker) dropped to low priority — they would only recover the residual
  ~20% churn from mid-run git-status changes. The reconcile-prompt reorder
  and the `plan-audit.md` context trim were both measured separately and
  found not worth doing (see git history for the profiling detail).
- **What's still open:** per-step parallelism for the audit loop itself
  (lever B) — ⚠️ **discouraged per CLAUDE.md's anti-parallelism directive**;
  pursue further cut-work levers first. Not worth pursuing until cut-work is
  genuinely exhausted and hurting.
- **Status:** low priority. The one open lever needs explicit user sign-off
  per the anti-parallelism directive before it's picked up.

**#66 — Contract-trace / path-enumeration audit mode (deterministic complement to the conceptual sampler)**

- **Principle:** `deterministic-non-determinism` — the T3 band: a deterministic complement to the conceptual sampler.
- **What:** A second completeness-audit mode that, instead of asking Claude to
  read the plan's prose and stochastically reason about it, materializes the
  plan's **declared seams/contracts** — function signatures, dataclass
  field-discipline (which field is populated on which outcome), the enum of
  outcomes/verdicts, and the call-site list — into a checkable skeleton, then
  **walks the `(caller × outcome × edge-input)` grid** and reports cells that
  are uncovered, crash, or violate a declared contract. Runs *alongside* the
  conceptual sampler, not instead of it.
- **Why:** The conceptual sampler catches **control-flow / contract-coverage**
  bugs only *stochastically* — each sample hits random cells of the path matrix,
  which is the root of the sampling-variance "long tail" (the now-reverted
  sample-count tuning fought the symptom; this addresses the cause for one
  finding class). A
  deterministic grid-walk enumerates the whole matrix once. Motivating evidence
  (escalate-structural-findings-to-split, 2026-06-22): three findings — step 8
  `escalate_to_split(step_id=None)` → `step_by_id(None)` KeyError; step 7 silently
  dropping the `unsafe`/`proposal-unusable` outcomes; step 3 a gate that leaks the
  verdict literal past guard (a) — are all cells of a
  `(caller × EscalateResult.outcome × step_id∈{None,concrete})` grid. Sampling
  found them across three separate audit runs at varying severities; a grid-walk
  would have found all three in one pass.
- **Complements, never replaces:** conceptual/intent findings (a stale premise
  like #61's `detail-purity`, "is this the right design", a dangling acceptance
  criterion) need the prose reasoning the sampler does — a trace has no opinion
  on intent. Two columns: control-flow/contract → trace (deterministic);
  conceptual/intent → sampler (judgment).
- **Effort:** large; **spike first.** Open design questions: how to extract the
  declared contracts from plan/detail prose without a full executable mock; how
  to keep it at *plan altitude* (check only what the plan declares, not invent
  implementation); how to avoid auditing **mock artifacts** (the exact false-
  positive we hit — a review flagged an empty-`()` render of a *hand-built
  unreachable* `ConvergenceDiagnosis` state; a sloppy skeleton manufactures
  findings about itself). Prefer materializing *declared seams* over full
  behavior to dodge both fidelity and altitude traps.
- **Risks:** garbage-in (an inaccurate skeleton → false findings); scope creep
  toward a full mock; only pays off for control-flow-contract-heavy plans (weak
  for conceptual/architectural ones — gate the mode, don't make it default).
- **Dependencies:** orthogonal to but motivated by the now-reverted
  sample-count tuning experiment — this is the structural answer to "is deep
  sampling worth it" for the control-flow finding class. Pairs with the
  granularity advisor's structural view.
- **Approach:** `plan-tool` (after a `direct` spike to validate the
  skeleton-extraction approach produces deterministic findings without
  mock-artifact noise on the escalate plan's three known findings as a fixture).
- **Quality:** `audit-coverage` — a deterministic, path-enumerating audit mode that
  catches the contract/control-flow gaps the stochastic conceptual sampler surfaces
  only intermittently (the motivating HIGH an 11-sample run missed).
- **Origin:** 2026-06-22 — user, after watching the conceptual sampler surface
  the escalate plan's control-flow findings stochastically across multiple audit
  runs (a HIGH that an earlier 11-sample run missed), asked whether tracing logic
  paths through a mock implementation would find correctness/completeness gaps
  more reliably than feeding the plan prose.

**#312 — Ground `detail` authoring in the plan's fetched reference-doc content instead of a bare link list**

- **What:** `detail.py` hands each step's authoring prompt only the plan's
  `## References` bullets — title/url/one-line description, lifted verbatim
  by `extract_plan_references` — and instructs the subprocess to
  independently web-search when that list "leaves a gap"
  (`prompts/detail.md`'s `## References` section). The actual page text was
  already fetched once, at `create` time, by `fetch_reference_docs`
  (`plan_tool/fetch.py`) to ground the plan body's synthesis
  (`synthesize-body.md`'s `## Reference documentation` block) — then
  discarded; the `create-reference-docs` checkpoint holding it is swept on
  every successful `create` (`create.py:_finalize_create_plan`). Reuse the
  same stdlib-only fetch primitive from `detail.py`: fetch the plan-level
  reference URLs once per `detail` invocation (not once per step) and inline
  the real extracted text into each step's prompt, mirroring the existing
  `synthesize-body.md` grounding pattern, instead of leaving every step's
  subprocess to independently re-derive doc content via its own live
  WebSearch/WebFetch tool calls.
- **Why it matters:** every step today either trusts a one-line description
  or performs its own live re-search of URLs `create` already fetched once —
  non-deterministic (different steps can turn up different content for the
  same URL), redundant (up to N re-fetches of the same page across an
  N-step plan), and untraceable (a claim in a detail body about a
  referenced doc has no reliably capturable link back to what that doc
  actually said at authoring time). That untraceability is also what blocks
  **#30** from usefully verifying detail-level claims against docs — see
  #30's Dependencies.
- **Effort:** small–medium. `fetch.py`'s primitives are already built,
  tested, and used by `create`; the work is wiring `detail.py` to call them
  (cached across one `detail` invocation's steps, not globally — a doc can
  legitimately change between separate `detail` runs on the same plan) and
  adding a new templated block to `prompts/detail.md`. The existing
  "web-search for a step-specific gap" instruction stays, but becomes the
  fallback rather than the default path.
- **Risks:** same as #30 names for the fetch layer — network/404/gated-doc
  failures must degrade gracefully (fall back to today's bare-bullet-list
  behavior, never abort a `detail` run), and fetched content must be cached
  within one `detail` invocation so an N-step run fetches each URL once, not
  N times.
- **Dependencies:** none — the fetch layer (`fetch.py`) is already in the
  tree, same as #30 notes.
- **Approach:** plan-tool. Prompt-template change + a caching/reuse decision
  across steps within one `detail` run + failure-mode design — matches
  #30's own scale assessment for the sibling verify half.
- **Iterate:** default recipe.
- **Origin:** 2026-08-25, investigation into how `detail` authoring uses
  documentation links, alongside scoping #30's detail-level extension.

**#30 — Verify plan against developer-doc links during iteration** → promoted to IPPT-15 (2026-09-27)

**#38 — Reconcile recommendation: detail-write annotation + `review` pre-filter** → promoted to IPPT-14 (2026-09-27)

**#102 — Deterministic seed-extraction pre-fill for body sections (widen rung 2 before the stochastic loop)** → promoted to IPPT-11 (2026-09-27)

**#43 — Synthesis output caching across reruns**

- **Principle:** `none` — a cost and latency cache.
- **What:** Cross-run cache keyed by
  `hash(seed_content + prompt_version) → synthesized_body_json`.
  Resumable checkpoints already cover within-run resume; this
  would let repeated `create --reprocess` against an unchanged
  seed reuse the prior synthesis without a Claude call.
- **Effort:** small-medium. New cache file at
  `.plan-tool/cache/body-sections/<hash>.json`, lookup in
  `propose_body_sections` before the Claude call, TTL or LRU
  expiry policy.
- **Risks:** stale cache if the prompt template changes — must
  include prompt version in the hash key. Confusion if cache hits
  silently across plan iterations.
- **Dependencies:** ✅ UNBLOCKED — body-synthesis shipped
  (default-ON, `--no-synthesize-body`; `synthesize-body.md` +
  `create.py` machinery, verified 2026-06-16). `propose_body_sections`
  is the documented insertion point for the lookup; ready to schedule.
- **Origin:** Deferred from
  `2-from-existing-body-synthesis.md` (2026-05-22).
- **Approach:** direct. Single helper + lookup + invalidation
  key — no design ambiguity once prompt-version is part of the
  hash.

**#49 — `plan-tool detail` authoring wizard**

- **Principle:** `untriaged` — guided-authoring UX; its text does not tie it to a principle.
- **What:** Add an interactive wizard to `plan-tool detail`, mirroring
  `create`'s step-entry wizard. Today `detail` is one-shot: it fires a
  Claude call that drafts the whole seven-section template (Summary /
  Why / Files / Implementation / Tests / Acceptance / Deferred) and
  writes it, leaving the operator to read-and-edit after the fact. The
  wizard makes that a guided flow on a TTY: pick the target step (the
  ones still lacking a detail file are listed, à la the `run` picker),
  optionally seed each section from a Claude draft, then walk the
  sections — accept the draft, hand-edit it, or skip — before the file
  is written. Confirm-before-write keeps a bad draft from landing
  silently.
- **Effort:** medium. New interactive flow in `detail.py` +
  `cli/authoring.py` wiring; reuses the section template the prompt
  already pins and the TTY/`-y` discipline `create`'s wizard
  established. The step-picker is the same shape just landed for
  `plan-tool run` (numbered list of incomplete steps, last-used
  default).
- **Risks:** the headless path must NOT prompt — `-y` / non-TTY keeps
  today's one-shot draft-and-write behavior exactly, same as `create`'s
  wizard fails fast under `--yes`. Merging a Claude draft with
  per-section operator edits needs a clean "draft vs. final" model so a
  half-edited section can't corrupt the seven-section gate that `detail`
  enforces on write. Decide whether the wizard is opt-in (`--wizard`)
  or the default-on-TTY behavior with `--no-wizard` to opt out.
- **Dependencies:** none. Shares the interactive-picker pattern with the
  `run` no-name picker; a shared "pick an incomplete step" helper could
  back both.
- **Approach:** plan-tool. Multi-surface (detail orchestrator + CLI
  wiring + interactive section walk), an open design decision on
  opt-in vs default-on-TTY and on the draft-vs-edit merge model, and
  TTY/headless discipline to keep consistent with `create` — all
  paper-trail material.
- **Iterate:** default recipe. **Phase 3 load-bearing** on the
  interactive section-walk step — the TTY/non-TTY split and the
  seven-section write gate are exactly the acceptance criteria a
  `run --iterate` loop converges against fixtures. **Phase 4** catches
  drift between the new wizard path and `create`'s established wizard
  conventions (both must honor the same `-y` / non-TTY contract).

  ```bash
  plan-tool create detail-authoring-wizard --iterate -y \
    --output-dir .agents/skills/plan-tool/implementation-plans \
    --from "..."
  plan-tool detail detail-authoring-wizard --commit -y   # phase 1.5
  plan-tool completeness-audit detail-authoring-wizard --iterate --commit -y   # phase 2
  plan-tool run detail-authoring-wizard --mode reconcile --iterate -y --step N   # phase 3
  plan-tool reconcile-code detail-authoring-wizard --all   # post-run tail
  ```
- **Status:** not started — design notes only.

**#82 — Deferred: structural-observation ledger**

- **Decision (2026-08-19): defer.** Do not add a telemetry kind, listing
  command, or generalized typed observation ledger before a specific marker
  class has both a predeclared threshold and a named operator decision it will
  inform.
- **Retained slice:** if that trigger appears, a direct deterministic check may
  count only that marker class and report the threshold crossing. The operator
  remains responsible for promotion, dismissal, and acceptable-duplication
  judgment.
- **Reason:** #79's review showed that most apparent duplicate-helper claims
  were false. Accumulating and formalizing candidates before proving they are
  reliable and useful would turn a one-off consolidation cue into backlog rot.
- **Status:** deferred pending a demonstrated marker class, threshold, and
  decision consumer.

**#108 — Durable per-step run marker so structural-remedy gates can distinguish authored-`current` from interrupted-`current`**

- **What:** Add a **durable, renumber-stable per-step signal** that a `run`
  actually *started* executing a step — e.g. a `Step.run_started` flag (or a
  first-run timestamp) set when `run` begins on a step and carried in the plan
  frontmatter. Then refine the structural-remedy safety gates
  (`split_safety.split_is_safe`, `detail.merge_is_safe`, the scope-out blocker)
  to block a `current` step **only when it carries this marker** (interrupted
  mid-run), while still allowing an authored-but-unrun `current` step.
- **Why:** The `split` unrun-`current` fix (shipped) had to fall back to a
  **`DONE`-only** gate because the tool has **no reliable per-step "a run
  reached this step" signal**. The obvious candidate — scanning run logs — is
  unsound: run logs are written by `detail`/`create` too (false positives),
  keyed to **pre-renumber** ids (a prior split/scope-out aliases them), and
  **TTL-evictable** (they disappear). `DONE`-only is correct for the common
  cases, but it leaves the documented `_persist_step_completion` **partial-state
  window** uncatchable: a SIGKILL between the lesson-append and the `DONE` flip
  leaves a step `CURRENT` on disk with a landed `step N:` lesson, and a
  subsequent split renumbers that lesson's step reference (soft mis-attribution).
  A marker that lives **on the `Step`** is renumber-stable (it travels with the
  step) and non-evictable (it's in the plan file), so it soundly closes the
  window the run-log approach couldn't — and gives merge/scope-out the same
  precision.
- **Scope:** a schema field (`Step.run_started` / timestamp, elided on rewrite
  when unset, migration-tolerant like the other optional fields); `run` sets it
  at step start (before the mutating body) and it coexists with the
  `pending → current → done` status axis; the three gates consult it; docs
  (`PLAN_FORMAT.md`, `DATA_CONTRACT.md` if tracked) + drift guard. Composes with
  the shipped split fix and the filed merge/scope-out sibling (see
  `BUG_BACKLOG.md`) — those gates become precise once the marker exists.
- **Effort:** medium — schema + `run` wiring + three gate refinements + tests;
  **spike** whether a boolean flag or a timestamp (and whether it clears on a
  re-open) is the right shape.
- **Risks:** a stale/incorrect marker would wrongly block a split — set it only
  at genuine run start and treat its absence as "not started" (fail-open toward
  the current `DONE`-only behavior); don't let it become a second source of
  truth that can disagree with `status`.
- **Dependencies:** builds on the shipped split fix (`split_safety`,
  `_apply_step_split`) and the merge/scope-out sibling bug; unrelated to #88
  (that is within-run *stage* resume, not a per-step execution marker).
- **Approach:** `plan-tool` — a schema change with wiring across `run` and the
  three structural gates, plus a real field-shape design choice.
- **Quality:** `gate-signal` — makes the structural-remedy safety gates block
  the *right* thing (interrupted-`current`, not authored-`current`), closing the
  partial-state window the `DONE`-only gate accepts as residual risk.
- **Iterate:** default recipe; spike the marker shape before wiring the gates.
- **Origin:** 2026-07-09 — surfaced fixing the `split` unrun-`current` bug: the
  DONE-only gate is a deliberate simplification because no durable per-step run
  signal exists; this item adds one so the gates can be precise.

**#88 — Granular resume — mostly SUPERSEDED; narrowed to `run`-step claude memoization**

- **Status (2026-07-12):** the original broad "per-stage operation manifest" is
  **superseded** — I built the `stage_manifest.py` leaf, then traced the actual
  persistence code and found resume is **already durable at per-`claude`-call
  granularity across every long op**, so a second stage ledger would only
  duplicate that state (drift risk, two sources of truth) for zero gain. Reverted
  the leaf. Existing machinery: **detail** — `checkpoint.py` saves right after
  parse; re-run takes the `cached` path and skips the invoke (`detail.py:1651,
  1844`). **completeness-apply** (serial *and* `--jobs>1`) — annotations persist
  **per finding** (`review_walk.py:756`, `completeness_phases.py:1100`); re-walk
  pre-skips already-`applied` findings before dispatch, and a `failed` annotation
  is non-terminal (retried). **completeness-audit** — reuses the saved conceptual
  audit, "skipping the conceptual Claude call" (`completeness_cmd.py:303`).
  **detail batch** — plan detail-pointers skip already-detailed steps.
  **Per-step commit durability** shipped 2026-07-11 — the real fix for the
  "uncommitted work lost at kill" pain the seed cited; its one residual (a
  durable per-step converged-vs-authored marker for resume re-entry) folds into
  this entry's resume scope.
- **Related (2026-10-06):** #455 asks whether a failed gate gets one bounded in-run
  repair attempt; any such attempt must reuse this memoized call rather than
  re-spend it.
- **Residual (the one genuine gap):** the `run` step executor
  (`launcher.py:run_step`) does **not** memoize its `claude` call the way
  `detail` does. So a `run` step whose call **succeeded** but whose downstream
  **test-authoring / drift gate failed** re-spends the whole `claude` call on
  re-run (the #88 origin case — B1's test-authoring gate). **Targeted fix:**
  memoize `run_step`'s output with the *existing* `checkpoint.py` (mirror
  `detail`'s save-after-parse), so a post-call gate failure reuses the cached
  output instead of re-invoking. Small, single-op, reuses the primitive — **not**
  a new cross-op manifest.
- **Acceptance (narrowed):** a `run` step that fails a post-`claude` gate re-runs
  reusing the cached call output (no re-invoke) when inputs are unchanged;
  parity with `detail`'s checkpoint staleness + auto-discard-on-success.
- **Dependencies:** `checkpoint.py` (reuse as-is), `launcher.py:run_step`.
- **Effort:** small (one op, existing primitive). **Approach:** direct or
  plan-tool. **Iterate:** default.
- **Origin:** 2026-07-04 — user, after B1 (`parallel-detail-authoring`) step 2's
  test-authoring gate failed *after* a successful authoring `claude` call.
- **Seed:** `plan-seeds/granular-stage-resume.md` — its §A (stage manifest) is now
  **obsolete**; its cooperative time-budget portion has shipped on the
  convergence loops and extends to the remaining durable boundaries in #230.

**#151 — Stop the audit purity path from requesting full detail-quality grounding it discards**

- **What:** Close the one known request/response mismatch at
  `completeness_phases._collect_purity_split_findings`. That caller invokes
  `detail.collect_detail_quality_findings` / `prompts/detail-quality.md`
  (~140 KB, ~130–255s/step per #133), which asks for semantic grounding
  (Read/Grep beyond declared files), altitude advisories, and a MIXED-STEP
  purity verdict — then keeps only medium `granularity-split` recs and
  discards the rest. Prefer, in order: (1) **no Claude call** when a cache
  hit / reuse-or-advise path can satisfy the audit (the shipped per-step
  purity cache), (2) **reuse the
  purity subset** as a byproduct of `detail`'s fully-consumed authoring call,
  (3) only if a live audit miss still needs a fresh purity verdict, add a
  **narrow purity-only mode** that requests the structural verdict from
  step metadata + `## Implementation`/`## Tests` and does **not** ask for
  repo-wide grounding.
- **Do not weaken `detail`'s authoring call.** Its two sites consume the full
  merged result (`initial_findings` / `open_findings`); grounding that reads
  outside `step.files` is intentional and must stay. A declared-files cache
  key cannot safely stand in for that grounding.
- **File scope (keep tight):**
  - Primary: `plan_tool/cli/completeness_phases.py`,
    `tests/cli/test_completeness_cmd.py`.
  - Only if a live miss still needs Claude past the purity cache: a small mode flag on
    `plan_tool/detail.py:collect_detail_quality_findings` /
    `render_detail_quality_prompt` plus a slim purity section in
    `prompts/detail-quality.md` (or a tiny sibling template), and matching
    unit coverage in `tests/test_detail.py`.
  - **Out of scope:** repo-wide LLM call-site inventories; new prompt-contract
    descriptor frameworks; create / review / reconcile / jira / run prompt
    rewrites; parallel purity fan-out (retired 2026-08-27); generalizing the purity cache
    to semantic grounding; prompt-excerpt / payload-size work (#38 family).
- **Relationship to the shipped purity cache:** With the per-step purity cache
  shipped, the audit purity path becomes reuse-or-advise with zero Claude calls
  on a cache hit, so this item mostly collapses to a short verification that the
  discard path is gone — **do not add a purity-only prompt just because the
  pre-cache caller needed one**. Only implement the narrow mode if a remaining
  live miss still invokes the full grounding contract.
- **Acceptance:**
  - Audit purity never invokes the full detail-quality grounding contract
    solely to retain the MIXED-STEP subset (zero calls under the shipped purity
    cache, or a purity-only mode if a miss still calls).
  - `detail` authoring still runs full grounding and feeds all finding
    classes into its convergence loop.
  - Tests cover the audit no-discard / no-over-request path; if a mode is
    added, also pin that the narrow mode cannot request broad tool
    exploration and that authoring still uses the full mode.
- **Effort:** small if the shipped purity cache removes the call; small–medium
  only if a purity mode is still required. **Approach:** `plan-tool` (or fold
  the residual into that cache's reconcile if it is already the natural home).
- **Quality:** `performance` — cut discarded request work without weakening
  authoring-time grounding.
- **Origin:** 2026-07-18 — operator concern about requesting more from an LLM
  call than the caller consumes; scoped to the known audit purity discard
  rather than a cross-surface rewrite.

**#156 — Make the conceptual-audit sampler key on the `[out-of-scope-deferred]` tag (currently prompt/operator convention only)**

- **What:** The scope-contract reconciliation (see [Scope contract and
  anti-creep](docs/TRACKING.md#scope-contract-and-anti-creep) and `prompts/plan-audit.md`) has
  the audit emit valid-but-adjacent findings tagged `[out-of-scope-deferred]`
  (INFO/LOW) and routes them to the backlog rather than expanding the plan. The
  docs state such findings "must not be treated as productive for dry-streak /
  low-yield convergence and must not justify raising `--audit-passes`" — but
  **the sampler doesn't key on the tag**; today it is purely a prompt/operator
  convention (`audit_plan_until_stable` / the low-yield productivity logic in
  `plan_tool/review.py` keys on severity via `convergence.is_blocking`, not on
  this tag). Wire the tag in: an `[out-of-scope-deferred]` finding must count as
  **non-productive** for the dry-streak / low-yield stop and must never keep the
  loop running or bump the pass recommendation.
- **Why it matters:** without this, a scope-contract-bound audit that keeps
  surfacing (correctly deferred) adjacent findings never reaches a clean dry
  tail — the exact non-draining oscillation the impact-convergence arc
  diagnoses. An `[out-of-scope-deferred]` finding is the purest "zero downstream
  impact" signal, so this is a direct sibling of the impact-keyed gate: the same
  productivity/stop logic that the shipped impact-aware policy uses should also drop
  out-of-scope-tagged findings from the count.
- **Effort:** small–medium (the sampler productivity predicate + the pass
  recommender + tests; no prompt change — the tag is already emitted).
- **Risks:** low — an additive exclusion in the productivity count; the main
  risk is a mis-parsed tag silently dropping a real finding, mitigated by keying
  only on the exact kebab anchor + INFO/LOW severity the prompt mandates.
- **Dependencies:** none to start; **coordinate with the shipped calibrated
  demotion and severity-aware low-yield rule** so the tag exclusion and the impact-keyed / severity-aware stop live in one predicate
  rather than three.
- **Outcome:** the low-yield / dry-streak stop and `--audit-passes` recommender
  treat `[out-of-scope-deferred]` findings as non-productive.
- **In scope:** `plan_tool/review.py` (`audit_plan_until_stable`, the
  low-yield productivity predicate, `recommend_audit_passes`) + tests.
- **Out of scope / Non-goals:** the shipped impact-aware convergence policy, the
  closed impact-recurrence advisory (and its withdrawn hard loop stop), the scope-contract
  authoring prose itself (already landed), and any new plan-body schema section.
- **Allowed behavior changes:** only the documented stop/recommendation change
  above — a scope-bound audit converges instead of grinding on deferred findings.
- **Allowed reorganization:** none — extend the existing predicate in place.
- **Verification:** a synthetic audit history whose only new findings are
  `[out-of-scope-deferred]` reaches `confirmed-dry`/`confirmed-low-yield` and
  does not bump the pass recommendation; a real in-scope finding still resets.
- **Stop / defer:** any adjacent sampler refactor → separate entry.
- **Approach:** `plan-tool` — `plan_tool/review.py` + `tests/test_review.py`.
- **Quality:** `convergence` (primary) + `gate-signal` — closes the gap between
  the documented tag convention and what the sampler actually enforces.
- **Iterate:** `plan-tool` — standard four-phase recipe once seeded.
- **Status:** not started — surfaced 2026-07-19 reviewing the example-app
  scope-contract reconciliation, which introduced the tag as convention-only.
- **Origin:** 2026-07-19 — the reconciliation's own note "prompt/operator
  convention until the sampler keys on the tag" names this as unfinished; filed
  per the scope-contract rule (a described-but-unimplemented behavior becomes a
  tracked entry).

**#106 — Finer completeness-apply detail-bundle gate: don't skip a split finding against an already-detailed step on a partial plan**

- **What:** After the axis-split bare-plan fence (bare-plan-correctness-apply,
  2026-08-03), `cmd_completeness_apply` walks `plan-correctness` on a bare/partial
  plan but still withholds every other saved source — including `granularity-split`.
  So a partially-detailed plan can persist a `medium` `granularity-split` finding
  against a **fully-detailed mixed step** that the walk never dispatches — neither
  applying the split nor printing the recommend-only `plan-tool split …`. Make the
  gate finer: skip only findings whose **target step** lacks detail, so an
  actionable split against an already-detailed step still surfaces.
- **Why:** on a partial plan the shipped split bridge's acceptance-criterion
  "without the opt-in … recommends only" is silently inert, and step 1's Claude
  spend produced a finding that can never be acted on until every sibling step is
  detailed. Documented as a known limitation in the (now-archived)
  `completeness-apply-split-bridge` plan; captured here so it isn't lost.
- **Scope caution:** per-finding target-detailed-ness applies only to sources
  that carry a reliable `step_id` (e.g. `granularity-split`, this entry's own
  example) — not to the conceptual audit sources: only **6.0%** of conceptual
  findings resolve to a step (116 of 1,933), so a per-finding gate over
  `plan-correctness`/`plan-completeness` would classify ~94% as ungrounded and
  collapse to the binary the axis-split already provides. This must **narrow**
  the skip, not remove the bare-plan invariant ("a completeness action can only
  target what exists").
- **Effort:** small. **Approach:** `plan-tool`. **Iterate:** default recipe.
- **Origin:** 2026-07-08 — `[bare-plan-split-gate]` finding from the
  `completeness-apply-split-bridge` completeness audit; deferred as out of scope
  for that plan.

**#105 — Stable per-step identity to close the directive-signature same-`(title, change_type)` collision**

- **What:** The precise per-directive staleness signature shipped for #93
  (`review_walk.compute_target_signature`) identifies a target step by
  `(id → title + change_type)`. Two distinct steps that share **both** title and
  change_type produce the same digest, so a renumber that aligns the *other*
  same-identity step onto a target id reads as **fresh** — and if that step also
  passes the bridge's own re-validation (already-built / mergeable / split-safe),
  the structural remedy mutates the **wrong step**. Give steps a **stable
  identity that survives renumbers** (e.g. a per-step uuid/slug stamped at
  `create` time, carried in frontmatter) and key the signature on it, closing the
  collision the `(title, change_type)` heuristic leaves open.
- **Why:** #93 replaced the coarse whole-plan fingerprint guard (which
  over-fired but never mis-targeted) with a precise per-target check. The precise
  check is strictly better in the common case, but introduces this **rare unsafe
  under-fire** the coarse guard didn't have. The bridges catch *most* wrong
  targets (existence/scope/already-built/mergeable) but **not** a
  same-`(title, change_type)` collision that also passes those checks — the
  residual documented in `compute_target_signature`'s docstring. A stable id is
  the only thing that fully distinguishes two otherwise-identical steps across a
  renumber.
- **Scope note:** the collision is genuinely rare (duplicate title+change_type
  **and** a renumber aligning them **and** the bridge accepting the wrong step),
  and strictly narrower than the pre-#93 blanket over-fire — so this is a
  hardening follow-up, not a hair-on-fire regression. A per-step uuid touches the
  schema, `create` authoring, and the data contract, so it is deliberate
  structural work, not an in-line patch.
- **Related robustness (minor):** the `BLOCKED-STRUCTURAL` split-escalation
  caller runs no staleness guard (it's a live verdict, not a saved directive), so
  a plan deleted mid-live-apply would reach `escalate_to_split`'s own `parse_plan`,
  which is wrapped only for `KeyError` (step lookup), not `FileNotFoundError`.
  Far-fetched (the apply just read/wrote the plan), but `escalate_to_split` could
  degrade to recommend-only on a gone plan instead of raising. Fold in if this
  entry touches the bridge.
- **Quality:** `audit-coverage` — sharpens how precisely the walk reasons about
  which step a saved directive still targets. Sibling of #93 (shipped) and its
  remaining test-authoring cross-link (#87).
- **Effort:** medium. **Approach:** `plan-tool`. **Iterate:** default recipe.
- **Origin:** 2026-07-08 — high-effort code review of the shipped
  `precise-directive-staleness` (#93) change; confirmed the `(title, change_type)`
  signature collides and the bridge re-validation does not fully defeat it,
  correcting that plan's "bridges re-validate → never a wrong flip" overclaim.

**#119 — Snapshot-restore-then-retry for a partial-mutation streaming failure (response B)**

- **What:** Restore transient/rate-limit *resilience* on the streaming `run`
  path without reintroducing the double-apply corruption. Same detection as the
  shipped response A (an aborted turn left uncommitted edits when a re-invoke is
  predicted), but instead of refusing the retry, snapshot the tree before
  attempt 1, and on a dirty-tree retry **restore to that pre-attempt snapshot,
  then re-drive** — idempotent recovery that keeps the previously-recovered
  transients recovered.
- **Why:** Response A (shipped, closed `BUG_BACKLOG.md` RISK) trades resilience
  for correctness: it turns some previously-recovered transients into surfaced
  terminal failures. B is the resilience-restoring follow-up so the operator no
  longer has to hand-revert-and-re-run for the common "aborted turn left
  incomplete edits" case.
- **Design:** B is a **caller-side** branch in the launcher's `retry_guard`
  closure (`plan_tool/launcher.py:shell_invoker`), which already has git — it
  restores then returns `RETRY`. The stdlib-only leaf
  (`plan_tool/rate_limit_loop.py`) needs **no change**: its contract stays
  `RETRY`/`STOP` (restore is caller-side, as the leaf's own docstring already
  notes). So B is a later branch, not a rewrite.
- **Effort:** medium — one closure branch plus a snapshot mechanism (stash or
  captured diff) and its tests; the detection/seam wiring already exists from A.
- **Risks:** the restore must **not clobber a `--commit`-less run's earlier
  legitimate dirty edits** — it may only revert paths the aborted turn itself
  changed, not the pre-existing dirty baseline. Getting that scoping wrong
  silently drops operator work.
- **Dependencies:** builds on the shipped response A (`retry_guard` seam +
  streaming git-delta guard); no other backlog items.
- **Approach:** `plan-tool` — touches the run invoker's retry contract and needs
  a snapshot/restore design decision, not a one-line fix.
- **Iterate:** default recipe (author + converge). Load-bearing: `create`,
  one-shot `detail --commit`, a `completeness-audit --iterate --commit`
  pass, then `run --commit --iterate` per step and the post-run
  `reconcile-code --all` tail.

  ```bash
  plan-tool create partial-mutation-snapshot-restore --iterate -y --from-existing plan-seeds/partial-mutation-snapshot-restore.md
  plan-tool detail partial-mutation-snapshot-restore --commit -y
  plan-tool completeness-audit partial-mutation-snapshot-restore --iterate --commit -y
  plan-tool run partial-mutation-snapshot-restore --commit --iterate -y
  ```
- **Status:** not started — backlog entry only.
- **Origin:** deferred response B of the transient-retry-partial-mutation-guard
  plan (shipped response A closed the `BUG_BACKLOG.md` RISK), 2026-07-11.

**#120 — Harden the partial-mutation retry guard against git-read and path-level blind spots**

- **What:** Close the residual robustness gaps in the shipped response-A guard
  (`plan_tool/launcher.py:shell_invoker._retry_guard`), which detects partial
  mutations via a git changed-**paths** delta. Three accepted-but-imperfect
  limits: (a) **same-path masking** — a file already dirty in the baseline that
  the aborted turn edits *further* has an empty delta, so the re-drive
  double-applies (only mitigated today by the `--commit` mandate, which keeps
  the between-step tree clean); (b) **git-read uncertainty** — `git status` can
  transiently fail (an `index.lock` during a concurrent git op), and a single
  read can't tell "not a git repo" (→ inert) from "real repo, momentarily
  unreadable" (→ should fail closed); the guard fails closed on a mid-run error
  but stays inert on a baseline-instant error (a narrow fail-open residual), and
  a spurious mid-run failure now converts a recoverable transient into a step
  failure; (c) **benign-artifact false STOP** — an untracked-non-ignored write
  the turn causes as a side effect (e.g. `__pycache__` in a repo that doesn't
  gitignore it) trips the guard even though no source was partially mutated.
- **Why:** (a) is a latent double-apply *corruption* in the no-`--commit` path;
  (b) and (c) are resilience/UX regressions (safe direction — a surfaced failure,
  never corruption — but they turn previously-auto-recovered transients into
  manual re-runs). Surfaced by two adversarial code-review rounds on the shipped
  guard; each round ping-pongs fail-open↔fail-closed because the fixes are
  structural, not one-liners.
- **Design sketch:** (a) content-level detection — hash the baseline paths and
  compare at the guard check so a further edit to an already-dirty file is
  caught, not just a *new* path; (b) detect whether `spawn_cwd` is a git work
  tree once (e.g. `git rev-parse --is-inside-work-tree`) to split "non-git tree"
  (inert) from "real repo unreadable" (retry the read on lock with short
  backoff, then fail closed), removing the baseline-instant fail-open; (c)
  optionally scope the delta to the step's declared/expected files or ignore a
  configurable artifact set.
- **Effort:** medium — touches the guard closure and `_git_changed_paths_or_none`
  plus tests; no leaf change (the `RETRY`/`STOP` contract is unaffected).
- **Risks:** content-hashing adds I/O per baseline path; the read-retry must not
  stall the loop; over-scoping the delta to declared files could *miss* a real
  out-of-declared-scope partial mutation (weakening the guard) — the scoping
  must stay conservative.
- **Dependencies:** builds on shipped response A; independent of #119 (response B),
  though B's snapshot mechanism could share the content-capture from (a).
- **Approach:** `plan-tool` — a guard-correctness design decision (detection
  granularity + git-read policy), not a one-line fix.
- **Iterate:** default recipe (author + converge). Load-bearing: `create`,
  one-shot `detail --commit`, a `completeness-audit --iterate --commit`
  pass, then `run --commit --iterate` per step and the post-run
  `reconcile-code --all` tail.

  ```bash
  plan-tool create partial-mutation-guard-hardening --iterate -y --from-existing plan-seeds/partial-mutation-guard-hardening.md
  plan-tool detail partial-mutation-guard-hardening --commit -y
  plan-tool completeness-audit partial-mutation-guard-hardening --iterate --commit -y
  plan-tool run partial-mutation-guard-hardening --commit --iterate -y
  ```
- **Status:** not started — backlog entry only.
- **Origin:** two adversarial `/code-review` rounds on the shipped
  transient-retry-partial-mutation-guard response A, 2026-07-11.

**#230 — Extend the shipped `--time-budget` stop to durable batch boundaries**

- **What:** `--time-budget` already stops the convergence loops cleanly. Extend
  the same cooperative deadline posture to the three long-lived surfaces that do
  not route through `convergence.should_continue`: the `completeness-apply`
  per-finding walk, the non-reconcile `run` per-step batch, and the outer
  `detail` step-to-step batch boundary. Each has a durable progress boundary
  (finding annotation, plan pointer, or per-step commit), so check the deadline
  only between units and emit an accurate resume hint.
- **Outcome:** a time-budgeted invocation of each named surface exits cleanly at
  its next durable boundary, preserves completed work, reports
  `time_budget_exceeded`, and provides a resume command.
- **In scope:** the three batch/walk boundaries, shared budget resolution, their
  reporter/resume-hint wiring, and focused tests.
- **Out of scope / Non-goals:** interrupting a running Claude call; changing the
  shipped convergence-loop behavior; reworking checkpointing or commit policy;
  argparse consolidation (owned by #80); and a broad reason-to-hint refactor.
- **Effort:** small–medium — three boundary integrations over an established
  budget contract. **Approach:** `plan-tool` because the three caller contracts
  and resume semantics must stay coherent.
- **Quality:** `survive-interruption` — extends an existing safe-stop contract
  only where progress is already durable.
- **Verification:** each surface stops after a completed durable unit rather
  than beginning another; zero/off preserves current behavior; a natural stop
  retains its more-specific reason; and rerunning resumes without repeating
  completed work.
- **Origin:** retired cooperative-time-budget follow-up, 2026-08-04.
- **Status:** not started.

**#124 — Floor-breaker: shorten or async-execute a single `claude` round-trip so it fits under a tight cap**

- **What:** Cross the **granularity floor** that #88 plus the shipped
  `--time-budget` backstop cannot: the finest
  atomic unit of durable progress is **one `claude` round-trip** (~3–6 min), and
  you cannot checkpoint *inside* a call — so a single over-long call still overruns
  a tight execution cap even with perfect stage-resume and a time-budget backstop.
  Two levers: **(a) shorter calls** — split a long single-call op into several
  smaller `claude` calls (fewer responsibilities / less context per call), each an
  independently-checkpointed #88 stage; **(b) async execution** — run the `claude`
  subprocess **detached** so the orchestrator's foreground clock isn't held, and
  resume when it completes.
- **Why:** #88 makes a kill lose ≤1 call and the shipped `--time-budget` stops
  cleanly at a boundary, but
  neither can help when a *single* call is longer than the remaining budget — the
  irreducible floor named in `plan-seeds/granular-stage-resume.md` §E. The long
  single calls are known: a `detail` step's authoring call, and a
  `completeness-audit` conceptual pass (~6 min alone, observed 2026-07-11).
- **Scope (levers, measure before splitting):**
  - **Op decomposition** — where a big single call can become several shorter
    ones that each checkpoint: e.g. `completeness-audit` per-step or per-section
    instead of one whole-plan conceptual pass; `detail` authoring in sub-passes.
    Each shorter call is a #88 stage, so partial progress survives.
  - **Async invoke** — run `claude` detached (background job), decoupling wall-clock
    from the foreground command; poll/resume on completion. Touches the invoker
    seam and the rate-limit loop.
- **Risks:** splitting a call **can degrade output quality** — the model sees less
  context per call; more calls = more latency overhead, token cost, and prompt-cache
  churn. Async execution complicates the invoker seam (`shell.py`/`backend.py`), the
  run log, and `rate_limit_loop.py`. **Measure the single-call durations first** and
  split only where the quality cost is acceptable.
- **Dependencies:** **#88** (the substrate — each shorter call is a stage) and
  the shipped `--time-budget` backstop — #124 is the *third* layer, only worth
  it once #88 lands and a call is measured to overrun even so. Invoker seam (`shell.py`, `backend.py`),
  `rate_limit_loop.py`, `prompt_budget`; relates to **#43** (synthesis caching).
- **Approach:** `plan-tool` — author via `create --from-existing` (seed only after
  #88 lands and profiling confirms a specific call needs it).
- **Iterate:** default recipe (author + converge): `create --iterate`,
  one-shot `detail --commit`, `completeness-audit --iterate --commit`, then
  `run --commit --iterate` per step and the post-run `reconcile-code --all`
  tail.
- **Status:** not started — backlog entry only. **Elevated 2026-07-12:** under the
  ≤5-min-per-unit design target of the shipped time budget, a single 3–6 min `claude` call already
  overruns, so #124 is a **co-equal** layer of the resume/timeout arc (**#88**
  granularity → **#124** call-length → shipped time-budget backstop), not a deferred nicety.
  Sequence right after #88 lands; profile the long calls first.
- **Origin:** 2026-07-11 — while seeding the granularity arc
  (`granular-stage-resume.md`), the user flagged that hitting the 10-min cap means
  *units are not granular enough*; the floor beneath even per-call granularity is a
  single call's own length, captured here so it is not orphaned in the seed.

**#126 — Concept publication-transaction machinery (deferred from the archived remediation program)**

- **What:** A single all-or-recoverable publication authority for every operation
  that changes a plan + its concept record: typed publication intents, a durable
  rollback journal, CAS/fingerprint staging, repo-lock ownership, a
  `publication-recovery` operator command, and resumable create-time concept
  review. Full 13-step design preserved at
  `docs/implementation-plans/archive/2-concept-remediation-1-publication-transactions.md`.
- **Effort:** large — the archived plan's own decomposition is 13 steps across
  `concept_sync.py`, `concept_tree.py`, `create.py`, `detail.py`, `scope_out.py`,
  a new CLI command, and data-contract changes.
- **Risks:** builds a transaction manager for a single-user local CLI whose files
  are VCS-tracked; high structural churn in the create/detail publication tails.
- **Dependencies:** `concept-write-integrity` (the distilled bug-fix plan) should
  land first — it removes the known divergence/ordering bugs this machinery was
  designed around.
- **Approach:** `plan-tool` — re-activate the archived plan (or re-seed from it)
  rather than authoring fresh.
- **Status:** deferred 2026-07-13 when the six-plan concept-remediation program
  was distilled to `concept-write-integrity`. Rationale: git is the recovery
  journal, a stale `plan_fingerprint` already reads as "re-derive", and the
  concrete write-ordering/single-writer bugs ship in the distilled plan. Revisit
  only if real-world usage surfaces an interrupted publication that git +
  fingerprint re-derivation cannot recover.
- **Origin:** reconcile audit `0129c29` (2026-07-13) on the shipped
  concept-signoff integrations.

**#127 — Concept authoring-boundary validation residue (deferred rem-2 steps 3, 4, 6)**

- **What:** The authoring-boundary hardening not covered by
  `concept-write-integrity`: tighten the detail response envelope + deferral
  validation, remove the sidecar-dependent legacy-Markdown fallback for detail
  responses, and bound/deduplicate include-triggered detail regeneration. Design
  preserved at
  `docs/implementation-plans/archive/2-concept-remediation-2-authoring-boundary-hardening.md`.
- **Effort:** small/medium — three of that plan's six steps (the other three —
  evidence-provenance tightening, fail-soft concept parse, detail replacement
  safety — ship in `concept-write-integrity`).
- **Risks:** stricter envelope validation can reject currently-tolerated model
  output; removing the Markdown fallback changes behavior for legacy plans with
  no concept tree.
- **Dependencies:** `concept-write-integrity` (shares the same boundaries).
- **Approach:** direct unless the envelope tightening balloons — each item is a
  localized validator change with tests.
- **Quality:** gate-signal — sharpens what the detail-response gate accepts as a
  valid authored artifact.
- **Status:** deferred 2026-07-13 (remediation-program distillation). Revisit if
  malformed detail envelopes or runaway include-regeneration show up in practice.
- **Origin:** reconcile audit `0129c29` (2026-07-13).

**#128 — Concept non-delivery ledger + lifecycle/seed accounting (deferred 3a/3b/3c)**

- **What:** The conservation-law accounting program: first-class
  `NonDeliveryRecord`s with review transitions and resumable include-regeneration
  (3a), candidate-generation prep + a versioned seed-accounting envelope through
  split/merge/scope-out/re-baseline (3b), and create-side deterministic
  restoration of reviewed accounting from modern seeds (3c). Designs preserved at
  `docs/implementation-plans/archive/2-concept-remediation-3a-accounting-core.md`,
  `…3b-lifecycle-publication.md`, `…3c-seed-restoration.md` (and the superseded
  monolith `…3-ownership-lifecycle-accounting.md`).
- **Effort:** large — 27 steps across the three archived plans.
- **Risks:** a second decision store beside `concepts.json` (the ledger) and a
  versioned envelope format to keep in sync; the accounting bureaucracy grows
  faster than the failure modes it prevents.
- **Dependencies:** #126 (the plans consume its publication API); 3b needs 3a,
  3c needs both.
- **Approach:** `plan-tool` — re-activate the archived plans in order if revived.
- **Status:** deferred 2026-07-13 (remediation-program distillation). Rationale:
  `concepts.json` nodes already carry decision/rationale/review_state (the
  non-delivery record in substance), the blocking `concept-coverage` completeness
  finding already catches a signed-off concept losing its owner, and carved/
  re-baseline seeds already carry concept IDs as prose for the next `create` to
  re-derive. Revisit only if a real lost-concept incident survives those nets.
- **Origin:** reconcile audit `0129c29` (2026-07-13); step expansion 14 → 27 on
  the 3a/3b/3c split was the severity-aware unbounded-tail signal that triggered the
  distillation.

**#130 — On-demand sub-concept drill for deferred concepts (deferred from the lazy-deferral MVP)**

- **What:** Let a deferred concept be finer-grained than its coarse **bucket** (body
  section), and let the operator **drill into a bucket on demand** to navigate the
  concepts under it — the "drill into the high-level list to land on a deferred
  concept" vision. Needs a scoped, lazy sub-concept producer (a per-bucket, on-demand
  version of the removed `emit_concept_tree` enrichment) that derives sub-concepts only
  when a bucket is navigated, and a record/surface that distinguishes `bucket` from a
  finer `title`.
- **Why deferred:** the lazy-deferral MVP (`docs/implementation-plans/2-lazy-deferral-confirmation.md`)
  is **flat** — the bucket *is* the leaf, so `bucket == title == section name`. The
  first audit of the guide-post attempt (v2) found the drill had nothing to drill into
  once enrichment was removed (`[lazy-drill-subconcepts]`), so the MVP dropped it. Flat
  bucket-level deferrals fully close the founding incident without a hierarchy;
  the drill is a genuine additional capability, not a gap.
- **Effort:** medium — a new on-demand per-bucket derivation producer plus the
  navigate/drill surface; the record already carries a `bucket` field the drill would
  refine.
- **Risks:** re-introduces a concept producer the lazy work deliberately cut — keep it
  strictly on-demand and per-bucket so it never re-creates eager whole-plan
  decomposition; sub-concept identity must be stable enough to key a deferral to.
- **Dependencies:** the flat lazy-deferral MVP shipped first (it establishes the
  `bucket`-tagged decision record this refines).
- **Approach:** `plan-tool` — seed after the flat MVP ships and a real need for
  sub-bucket granularity is observed.
- **Status:** deferred 2026-07-15 (lazy-deferral simplification to flat records).
- **Origin:** 2026-07-15 — the operator's drill vision; deferred when the flat MVP
  proved sufficient for confirming deferrals and the drill's producer was cut.

**#131 — Migrate legacy eager full-tree `concepts.json` to the flat decision-record shape**

- **What:** A one-time migration from the shipped **eager full-tree** `concepts.json`
  (a node per section + ~20 enrichment nodes, whole-bundle fingerprinted) to the lazy
  MVP's **flat decision record** (`{bucket, title, decision, review_state}`, not
  fingerprint-validated). Until migrated, the load path carries a record-kind branch so
  both shapes remain loadable.
- **Why deferred:** the lazy MVP keeps legacy records loadable rather than forcing a
  migration, so it ships without touching existing plans. A migration is only worth it
  to retire the dual-shape load branch once few legacy records remain.
- **Effort:** small/medium — a deterministic transform + a `plan-tool` migrate verb or
  a sweep pass; no Claude.
- **Risks:** an eager tree carries `include` nodes and owners a flat record drops —
  decide explicitly whether that accounting is discarded (it is inert under the lazy
  model) or preserved.
- **Dependencies:** #130-adjacent — the flat lazy-deferral MVP shipped.
- **Approach:** `direct` unless the transform proves to need per-plan judgment.
- **Status:** deferred 2026-07-15 (lazy-deferral MVP keeps legacy loadable instead).
- **Origin:** 2026-07-15 — lazy-deferral seed's coexistence risk (legacy full-tree vs
  flat decision record).

**#132 — Dismiss/remove verb for a wrong pending deferred concept**

- **What:** A way for an operator to actively **dismiss** a pending deferral they judge
  wrong — drop the decision record entirely — rather than only `include`/`defer`/
  `wont_do` it. `scope-review` has no remove action today, and on a lazy plan `include`
  is not a dismissal (it produces an approved-include node with no owner, tripping a
  blocking `concept-coverage` finding).
- **Why deferred:** in the lazy MVP a wrong pending deferral is **inert until
  confirmed** (never rendered, never counted), so it is harmless if simply left
  unconfirmed — active dismissal is an ergonomic nicety, not a correctness need.
- **Effort:** small — a `scope-review` (or new `scope-dismiss`) action that deletes the
  named record; no Claude.
- **Risks:** minimal; ensure a dismissed record cannot silently resurrect on the next
  `create`/`detail` proposal (or that a re-proposal is acceptable).
- **Dependencies:** the flat lazy-deferral MVP shipped.
- **Approach:** `direct`.
- **Status:** deferred 2026-07-15 (lazy-deferral MVP: inert-until-confirmed is the
  interim guard).
- **Origin:** 2026-07-15 — surfaced across the lazy-deferral audits as the missing
  "reject a mis-proposed deferral" path.

**#134 — End-to-end founding-incident test: a real `detail` deferral proposal surfaced in `status` and the completeness report**

- **What:** A single integration test that runs the actual producer→surface path —
  `detail` records a flat pending decision (step 6), then `status` and the
  completeness report surface it with its bare `node.id` (step 5) — rather than the
  two halves being verified independently. Today step 6 stops at "a flat pending
  record is written," step 5 drives its surfaces from synthetic `decision-record`
  fixtures / patched recs and does **not** `depends_on` step 6, so the plan's central
  "none silently dropped" guarantee is verified only by producer and consumer
  *agreeing on the record's source/anchor/bucket shape*, never by a test that a real
  proposal reaches the surfaces. A shape mismatch between producer and consumer would
  pass every existing test.
- **Why deferred:** the shipped halves do agree on the shape (both key identity on
  `concept_id(title, [])`, `record_kind="decision-record"`, anchor `concept-{id}`),
  so this is a coverage-strength gap, not a known defect; and closing it is
  structural test work (a producer→surface integration test plus the step-5↔step-6
  test dependency), not a doc reconciliation, so it belongs here rather than in the
  run-tail. Surfaced by loop-2 completeness audit `[founding-incident-e2e]`.
- **Effort:** small–medium — one integration test driving `generate_detail` (fake
  invoker emitting a deferral envelope) then `status`/`build_report_md`, asserting the
  proposed `node.id` surfaces; no Claude.
- **Risks:** minimal; hermetic test, no production change.
- **Dependencies:** the flat lazy-deferral MVP shipped.
- **Approach:** `direct`.
- **Status:** deferred 2026-07-16 (lazy-deferral run-tail: halves-agree coverage is
  the interim guard).
- **Origin:** 2026-07-16 — lazy-deferral run-tail completeness audit
  (`[founding-incident-e2e]`).

**#135 — `reconcile-code` needs a real drift-check signal, and concurrent invocations should fail cleanly**

- **Shipped 2026-08-16:** the `--all` sweep gap this item originally opened with is
  closed. `reconcile-code <name> --all` now sweeps every plan step in order
  (including `done` steps — the point of a post-run sweep is checking landed code,
  not skipping it), skips steps declared explicit `non-code` (mirrors
  `direct_cmd._is_code_step`), is mutually exclusive with both `--step` and
  `--reuse-id` (a pinned save can't mean anything sensible across N steps), and
  halts on the first per-step *execution* failure (a redirect or critical finding
  does not halt it — read each step's printed verdict, per
  `_cmd_run_reconcile`'s docstring). CLAUDE.md's run-tail loop 1 now cites `--all`
  directly. What remains open is gap 2 below, plus the concurrency note.
- **What (remaining):** `--dry-run` only *renders the prompt* (no Claude, no audit),
  yet the "no remaining drift" convergence signal a run-tail loop needs has no cheap
  form today — you must run the full per-step audit (`--no-walk`) to learn whether
  drift remains. Either add a real drift-summary mode (a `--check`/rollup that
  reports per-step drift counts without walking or landing edits) or keep leaning on
  the full sweep's printed verdicts as the signal (already the documented behavior;
  see CLAUDE.md's run-tail loop 1).
- **Also (smaller, unchanged):** concurrent `reconcile-code` on the same plan should
  either serialize safely or fail with a clear message instead of a bare exit-2
  collision.
- **Also (new, 2026-08-16):** `direct_cmd.py:cmd_direct_run`'s step-7 reconcile loop
  still hand-rolls a per-code-step `cmd_reconcile_code` call rather than calling
  `reconcile-code <name> --all` once — now that `--all` filters non-code steps the
  same way, the two are policy-equivalent and the hand-rolled loop is a candidate to
  collapse into the single call. Separately, `_cmd_detail_reconcile_all` (skips
  `done` steps), `_cmd_run_reconcile_all` (includes them, filters non-code instead),
  and `_cmd_run_sweep` (runs executable steps) are three distinct sweep-loop shapes
  across `cli/reconcile.py` and `cli/run_cmd.py`. A 2026-08-16 `/code-review` pass
  left a shared abstraction deferred because their selection and persistence policies
  differ; revisit it if a behavior change requires common machinery or the paths
  drift out of sync.
- **Effort:** small — the drift-check is either a doc fix (already applied) or a
  no-walk rollup summarizer; the `direct-run` consolidation is a small, low-risk
  simplification once someone verifies run-log/rc parity between the two paths.
- **Approach:** `direct`.
- **Origin:** 2026-07-16 — lazy-deferral run-tail loop 1; friction driving
  `reconcile-code` step-by-step across a completed plan. `--all` sweep shipped
  2026-08-16 in the `reconcile-code-all` diff, applying its own `/code-review`
  round-1 findings.

**#139 — Plan-authoring completeness audit has no "implementation-time" finding class**

- **What:** The conceptual completeness audit surfaces findings only
  resolvable/observable **once the code exists** — this session's round-3 audit
  flagged, e.g., a stubbed-test blind spot with its own note *"the unit tests stub
  `cmd_completeness_apply`, so they cannot catch the missing fields; only a real
  chained run crashes."* Such findings keep resurfacing as **plan-design gaps**,
  inflating the audit/apply tail even though the plan can only *describe* the intended
  handling, not close them — they close at implementation/`run` time.
- **Why it matters:** these implementation-time edges drive the "each design change
  spawns new stage-edge findings" long tail that makes the authoring audit hard to
  converge. Treating them as plan gaps pressures the author to over-specify integration
  detail the build will settle anyway, and muddies the "is this plan design-sound yet?"
  signal.
- **Fix direction:** let the audit **classify/route** a finding as *implementation-time*
  (resolve during `run`, not in the plan) vs a *plan-design* gap — a distinct
  disposition bucket that renders as a **build-time checklist** on the plan (as done by
  hand here in the plan's `## Deferred > Known limits`) rather than a blocking authoring
  gap. The author acknowledges the checklist; it does not reset convergence.
- **Effort:** medium — a new finding disposition + its render surface; the classifier
  heuristic (code-anchored / test-blind-spot / "only a real run reproduces") is the hard
  part.
- **Approach:** `plan-tool` — audit disposition + report rendering.
- **Quality:** `convergence` — separates "plan not design-sound yet" from "sound plan
  with build-time residuals," so the authoring loop can terminate.
- **Relation to the shipped severity-aware rule:** distinct — it is the stopping
  rule; this is finding **classification/routing**. They compose (a
  well-classified implementation-time finding should not reset the
  diminishing-return streak).
- **Origin:** 2026-07-16 — #118 direct-pipeline authoring; round-3 audit's own note
  that stubbed tests can't catch the flagged integration edges.

**#140 — `direct_cmd.py` hardening: dedupe the verb prologues, lift the size gate, expose jira flags**

- **What:** Four cleanups a high-effort `/code-review` pass surfaced on the
  shipped `plan_tool/cli/direct_cmd.py` (the #118 direct verbs):
  1. **Dedupe the ~110-line prologue.** `cmd_direct_jira` and `cmd_direct_run`
     copy-paste the entire clean-tree gate + sink hand-off + split/iteration
     guards + size gate + detail stage + authoring commit + completeness-apply
     block, differing only in message strings and (formerly) one commit guard.
     That drift already shipped one bug — the direct-jira unconditional-commit
     asymmetry (fixed 2026-07-17). Extract a shared
     `_author_detail_apply(args, verb) -> tuple[rc, plan_name | None]` so the
     invariant lives once.
  2. **Lift the size gate out of the thin CLI leaf.** `gate_create_result_size`
     / `SizeGateResult` encode a plan-sizing *policy* (step-count threshold,
     verdict) — domain logic that belongs in a top-level orchestrator, not
     `cli/`, per the CLI-layering rule.
  3. **Expose the jira-stage flags.** `direct-jira` hardcodes/`getattr`-defaults
     `epic`, `max_hours`, `format`, `output`, `no_write`, `stdout` with no
     parser flags, so an operator can never assign an epic, choose JSON, or set
     max-hours — capabilities the standalone `jira` verb has. Decide which to
     surface on `direct-jira` (at least `--epic` / `--format`) vs leave as the
     small-work default.
  4. **Drop the redundant plan re-parse.** `gate_create_result_size` parses the
     plan to count steps; `cmd_direct_run` re-parses it for the reconcile loop.
     Thread the parsed `Plan` through instead of reading + parsing twice.
- **Also (dead state, low):** `gate_create_result_size`'s `plan_path is None`
  split-short-circuit branch (and `SizeGateResult.split_short_circuit`) is
  unreachable from both callers (they return before calling the gate) — it exists
  only for a unit test. Remove it, or keep it as a deliberate defensive guard and
  note that intent.
- **Also (behavior decision):** `cmd_direct_run` leaves every reconcile-code
  step's inline edits **uncommitted**, so a `direct-run` that reaches the reconcile
  tail ends with a **dirty tree** — even though its `run --commit` stage committed
  each green step. Currently documented as intentional (matches standalone
  `reconcile-code`, whose edits the operator reviews) in the plan's Known limits,
  but the review re-raised it: the dirty end-state surprises an operator who
  assumes an unattended verb leaves a clean committed tree, and the reconcile
  edits can be lost to a stray `checkout`/`stash` or block a later `--commit`-gated
  command. Decide: commit the reconcile edits at the end (clean end-state, at the
  cost of un-reviewed committed edits), leave them (status quo), or gate the
  choice behind a flag. Capture the decision here so it survives the plan's
  eventual archival.
- **Effort:** medium — (1) is the bulk (a careful extract of a shared helper both
  verbs call); (2)/(4) are small; (3) is arg plumbing + a scope decision.
- **Approach:** `plan-tool` — CLI leaf + a new/again orchestrator seam.
- **Quality:** `gate-signal` — (1) removes the drift class that already shipped a
  commit bug; (2) keeps domain policy testable outside the CLI shell.
- **Origin:** 2026-07-17 — #118 direct-pipeline post-run `/code-review` (high
  effort); cleanup findings on the freshly-generated `direct_cmd.py`.

**#142 — Jira ID-linking sweep: map local plan-story IDs to real Jira keys via summary bracket-token**

- **What:** A read-only sweep that scans a Jira project and links each local
  plan-story ID (the epic-scoped label the plans use, e.g. `AIHARD-S38b`,
  `VNDSFTP-S29`, `NOTIF-S01`) to its real Jira issue key (e.g. `PS-197`) and
  live status, then persists the mapping so downstream verbs can reconcile
  local `[status: …]` markers against Jira. Emits an `id → key + status`
  table and flags: unmatched local IDs (no Jira issue yet — often placeholder
  IDs), Jira issues with no local story, and status divergences (local
  `done` vs Jira `To Do`, or local `todo` vs Jira `Done`).
  **Scope boundary (sharpened after a manual dry run, see Status below): this
  item stops at *surfacing* divergences. It must NOT auto-write local
  `[status:]` from Jira's status.** Jira status turned out to be an unreliable
  ground truth on its own — see #143, the mandatory follow-up before any
  divergence is resolved by overwriting either side.
- **Why:** Plans carry two disconnected identity systems — the human-authored
  local IDs and the real Jira keys — and today nothing reliably bridges them.
  The existing `jira-sweep`/`report.md` matches by **issue title**, which is
  fragile: titles drift after creation (observed: `AIHARD-S32` reported
  "unmatched" purely because its Jira summary was reworded, when `PS-175`'s
  summary still carried the exact `[AIHARD-S32]` bracket token and was `Done`).
  Reconciliation built on title-match produces false "not in Jira" verdicts and
  misses real status drift.
- **Proposed design:**
  1. Rely on the **`[<PREFIX>-S<NN>]` bracket token** that Jira summaries
     already carry as the join key — exact, drift-proof, and independent of
     the rest of the title. Fall back to title similarity only when a token is
     absent.
  2. Fetch epic children via `parent = <epicKey>` (company-managed) with just
     `key, summary, status`; page past 100. Resolve the epic key from the
     plan's `jiraEpicId`.
  3. Handle **token collisions** (same local token reused across epics/plans —
     observed `VNDSFTP-S19` → both `PS-115` "Vendor SSO" and `PS-226`
     "CourseCardData mapper", reproduced identically across two independent
     dry-run passes) by disambiguating on the plan file's own story title.
  4. Persist `{localId, jiraKey, jiraStatus, sweptAt}` to
     `.plan-tool/jira-sweep/` and expose it to `reconcile`/`verify` so those
     verbs can annotate or diff without re-querying. The persisted record is
     an *input to arbitration* (#143), not a resolved verdict.
- **Effort:** medium — one read-only MCP/REST sweep leaf + a persisted mapping
  artifact + join/collision logic + fixtures. No write-back to Jira in scope.
- **Risks:** MCP Jira responses are large (epic-child queries blow the token
  budget with default fields — must request minimal fields / markdown format);
  bracket-token regex must tolerate suffixed IDs (`S38a`) and non-story tokens.
  **Confirmed risk, not just theoretical:** a naive version of this sweep that
  trusted Jira and auto-synced local status was tried by hand on
  `example-app-amplify` — it got 24 of 29 divergent stories **wrong**,
  including flipping two stories to `done` that actually had eligibility
  checks disabled in production code. This is why the scope boundary above
  exists.
- **Dependencies:** none hard to build; complements the existing `jira`
  subcommand and the `jira-sweep` artifact it would supersede for the matching
  step. #143 depends on this item's output (the divergence list) as its input.
- **Approach:** `plan-tool` — new read-only CLI leaf plus a mapping artifact
  other verbs consume; touches an orchestrator seam, not a one-file change.
- **Quality:** `grounding` — replaces fragile title-match with an exact key so
  reconciliation reports (matched/unmatched/divergent) are trustworthy instead
  of noisy with false "not in Jira" verdicts. (The deeper accuracy question —
  *which side is actually true* — is #143's job, not this item's.)
- **Origin:** 2026-07-17 — surfaced doing a manual bracket-token reconciliation
  of the `example-app-amplify` plan-details `jira-stories.md` files against the
  live `PS` project (epics `PS-1`=AIHARD, `PS-3`=VNDSFTP); title-match in the
  saved `report.md` had mislabeled already-`Done` stories as unmatched.
- **Status:** not started as a plan-tool feature. A manual, by-hand dry run of
  exactly this workflow was carried out in `example-app-amplify` on 2026-07-17
  (bracket-token join across 99 stories / 3 Jira epics) — see #143's Origin
  for what happened next when the naive trust-Jira version was tried.

**#143 — Code-truth verification pass: adjudicate status divergences (and spot-check agreements) against real code, not Jira**

- **What:** a follow-up to #142 that takes its divergence list (plus a sample
  of stories where local and Jira *agree*, since agreement isn't proof) and
  produces a third, independent verdict per story — Done / Partial / Absent —
  by reading each story's acceptance criteria and files-in-scope against the
  actual working tree, rather than trusting either recorded status.
- **Why:** #142 (and any Jira-status sweep) can say two records disagree but
  can't say which is right. Tested for real: a code-blind sync that trusted
  Jira's "Done" and overwrote local `todo` markers was wrong for 24 of 29
  divergent stories — including silently endorsing two production regressions
  (an eligibility flag hardcoded to `true` behind a "Temporarily disable"
  comment, and a gate commented out entirely, both with their test suites
  rewritten to assert the disabled behavior) as "done" work.
- **Full design authored as a seed:** `plan-seeds/jira-sweep-verify-code-truth.md`
  — the 10-parallel-agent architecture, the two special-case classifiers
  (behavioral-regression detection, superseded-plan detection), and the
  cost/effort profile all live there rather than here. Already sequenced in
  `docs/implementation-plans/backlog-arcs/backlog-arc-operator-workflow.md`'s
  Ordered route (step 2): execute `jira-sweep-deterministic` (#142) first,
  then evaluate this one.
- **Dependencies:** #142 (needs its divergence list as input).
- **Origin:** 2026-07-17 — directly follows the #142 dry run; the manual
  10-parallel-agent run (`example-app-amplify`) is the reference
  implementation the seed is built from.
- **Status:** seed authored, blocked on #142 executing first (per the
  operator-workflow arc's ordered route).

**#146 — Support nested / ancestor-repo relocation in the `direct-jira` / `direct-run` pipeline**

- **What:** the `direct-pipeline-repo-root-resolution` plan (fixing the
  stale-`repo_root` "plan not found" bug) deliberately **scopes out** the case
  where `create`'s seed-derived relocation lands on a root that is *nested
  inside* the cwd root, or is a strict *ancestor* of it — i.e. where the
  original `repo_root` and the relocated `created_repo_root` are not disjoint
  trees. In that scoped-down plan, `direct-jira`/`direct-run` **refuse** a
  nested/ancestor relocation with a clear error ("nested-repo relocation
  unsupported; run from the target repo directly") rather than trying to handle
  it. This item is the deferred full-support follow-up.
- **Why deferred (the thorny findings a completeness audit surfaced
  2026-07-18):** git's embedded-repository semantics make the non-disjoint case
  genuinely hard, and three distinct HIGH/MEDIUM findings all trace to it:
  - **`nested-repo-dirty-precondition`** (HIGH): a nested `.git` under the cwd
    tree makes the *original* root read dirty to git before `create` runs (git
    reports an embedded repo as a single collapsed `?? nested/` porcelain line;
    `--untracked-files=all` does **not** expand it), so the step-0 clean-tree
    precondition rejects the chain with "requires a clean working tree" before
    relocation logic ever runs.
  - **`original-root-commit-embeds-nested-repo`** (HIGH): the original-root
    archival commit (`commit_all(repo_root, ...)` → `git add -A`) silently
    stages a nested `created_repo_root` as an embedded gitlink (`mode 160000`,
    "warning: adding embedded git repository") the instant it has a commit,
    corrupting the intended "small, seed-archival-only" commit.
  - **`relocated-root-collision-replace-dirt`** (HIGH, ancestor half):
    `find_umbrella_root` case 1 (`plan_tool/locator.py`) can return a strict
    *ancestor* of cwd, which `cmd_create`'s `startswith` relation check
    mislabels "broader (outside)" — the same bucket as a true sibling — so
    `repo_root` ends up nested inside `created_repo_root` and its own committed
    state collapses to one opaque embedded-repo entry that step 3's expected
    dirty-path set never accounts for, aborting a chain that did nothing wrong.
- **Fix (indicative):** detect the non-disjoint relocation up front (one root
  is `.is_relative_to` the other) and handle it deliberately — options include
  scoping every commit to explicit pathspecs instead of `git add -A` (so a
  nested repo is never staged as a gitlink), teaching the step-0 precondition
  to ignore an embedded-repo boundary, and fixing `cmd_create`'s
  relation-string classifier to distinguish the ancestor case from a true
  sibling. Each needs a design decision, hence deferred rather than crammed
  into the bug-fix plan.
- **Separately, a narrower correctness gap in the same area
  (`relocated-root-collision-replace-dirt`, the collision half):** step 3's
  relocated-root expected-dirt allowlist (`_relocated_root_unexpected_dirt`)
  omits the extra writes `create_plan`/`cmd_create` make under the relocated
  root when a `--from-existing` seed **collides with and replaces** an existing
  same-slug plan (`replaced_archives`, manifest-entry removal, and a
  `plan_details_renamed_to` rename — the `should_replace` branch,
  `plan_tool/create.py` ~line 6218). This one is **independent of nesting** — it
  fires in the plain sibling case too — so it may be worth folding into the
  scoped-down bug-fix plan rather than here; tracked here so it isn't lost if
  the bug-fix plan defers it.
- **Approach:** `plan-tool` — multiple call sites, git-semantics design
  choices, its own decomposition.
- **Quality:** `grounding` + `gate-signal` — the failure mode is a chain that
  aborts (or silently corrupts a commit) on a legitimate relocation.
- **Origin:** 2026-07-18 — carved out of `direct-pipeline-repo-root-resolution`
  when its completeness audit surfaced the embedded-repo cluster above and the
  operator chose to ship the disjoint (sibling) + internal-manifest-divergence
  core and defer the nested/ancestor case. See that plan's `## Out of scope`.

**#150 — Have `create` report its complete touched-path set on `CreateResult` so the direct-* relocated-root guard can allowlist exhaustively**

- **What:** `direct_cmd.py:_relocated_root_unexpected_dirt` allowlists
  `create`'s writes under the relocated root to distinguish them from a
  stranger's dirt, but `CreateResult` doesn't enumerate every write, so the
  set is best-effort. Four rounds of audit/review each found another missed
  write (grounding.json, collision archives, `.plan-tool/` telemetry, the
  deleted-original side of a collision-replace). The common cases are now
  covered exactly; two residual best-effort gaps remain: (a) a seed physically
  under the relocated root (its seed-archives land there, not exposed on
  `CreateResult`), and (b) a collision-replace that `rmtree`s a *pre-rename*
  detail-dir source (`rename_plan_details_to_slug`; `CreateResult` exposes only
  `plan_details_renamed_to`, the destination).
- **Fix:** have `create`/`create_plan` record every path it touches under each
  root (writes + deletions) on `CreateResult` (e.g. a `touched_paths` field),
  so the guard allowlists exactly instead of guessing. Failure mode today is a
  *spurious abort* (safe), never corruption — hence deferred, not urgent.
- **Approach:** `plan-tool` (CreateResult contract change + guard rewrite +
  DATA_CONTRACT.md).
- **Origin:** 2026-07-18, direct-pipeline-repo-root-resolution audit/review tail.

**#155 — Harden the purity-cache below-floor (#144) reuse heuristic and success-gate against their documented edge cases**

- **What:** the shipped purity-findings-cache (#145) below-floor reuse
  (`completeness_phases._grade_purity_cache_miss`) and the write success-gate
  (`detail._response_reached_findings`) are deliberately **best-effort
  heuristics** — the plan's `## Deferred` and `## Risks` already document that
  they can serve a stale "pure" verdict on edge cases (the cache trades away the
  incidental re-roll of a non-deterministic judgment). Two completeness-audit
  rounds and two `/code-review` rounds kept surfacing new *facets* of that same
  heuristic imperfection; the concrete, cheap ones were fixed inline, and the
  residual facets are gathered here rather than chased with ever-more heuristic
  complexity:
  - **Below-floor magnitude is scoped to `## Implementation` + `## Tests`** — a
    substantive edit confined to `## Why`/`## Summary`/`## Files`/`## Acceptance`
    moves `detail_hash` (→ miss) but scores ~0% and reuses. Documented accepted
    window (the purity verdict tracks what the step *implements/tests*); revisit
    if a real case shows a prose-only reframe changing the verdict.
  - **Success-gate can be fooled by an echoing/reordering reply** — `## Findings`
    (the last required section) is the completion signal; a reply that echoes the
    prompt headers or truncates oddly could read as succeeded. Harden with an
    end-of-text anchor or a structured-envelope contract.
  - **Proportional floor** — partially hardened already (an absolute
    `PURITY_REUSE_ABS_FLOOR` companion now bounds the large-step case); revisit
    the constant against real audit history if it proves mis-sized.
- **Why deferred:** these are the low-yield tail of an intrinsically non-
  deterministic judgment being cached; the *core* exact-hit cache is sound, and
  the worst case is a re-used stale verdict on a narrow edge (same class as the
  documented verdict-nondeterminism tradeoff), never corruption. A durable fix
  is either a sampled/TTL forced re-check (bounding staleness in time) or a
  structured purity-only response contract (bounding the success-gate) — a
  design decision, hence its own item.
- **Approach:** `plan-tool` — its own scoping; touches `completeness_phases.py`
  (grading), `detail.py` (`_response_reached_findings`, `_impl_tests_section_text`),
  and possibly `prompts/detail-quality.md`.
- **Quality:** `audit-coverage` — the failure mode is a silently under-checked
  step, so calibrate any change against real audit history.
- **Origin:** 2026-07-19 — purity-findings-cache (#145) post-run reconcile +
  `/code-review` tail; the recurring-heuristic-edge escape-hatch (stop patching,
  file the structural hardening).

**#190 — Refuse `reconcile-plan` on steps an execution already implemented**

- **What:** `reconcile-plan` is code-canonical — it treats the code on disk as
  truth and mutates the plan/detail to match. That is correct **before**
  execution (re-grounding a plan whose codebase moved on since authoring) and a
  hazard **after** it. Add a preflight guard to `plan_tool/cli/review_cmd.py`
  that refuses a `--step N` aimed at an implemented step, skips implemented
  steps on the whole-plan default, and names the right verb instead:
  `reconcile-code` for plan-canonical drift, `annotate` to judge an executed
  plan and seed the next iteration.
- **Why:** after a step runs, the code exists *because of* the plan. Point a
  code-canonical audit at it and the implementation gains authority over the
  intent that produced it — under-delivery reads as an over-promising plan, and
  the proposed remedy is to edit the plan toward the code. `prompts/reconcile.md`
  already fences the worst of it (refuses scope-narrowing and
  criterion-softening edits, routes a shortfall to a `status`/`status_note`
  flip), but that is a guardrail on a verb pointed the wrong way, and the
  `status`-flip escape does nothing for a step a green run already marked
  `done`. Today the rule lives only in prose (`CLAUDE.md` § "`reconcile-plan` is
  a *pre-execution* verb"); this makes it mechanical at the point of misuse.
- **The design question to settle first — what counts as "implemented".**
  `status: done` is the cheap proxy and is deliberately over-broad:
  `reground.py:reground_bridge`'s `DISPOSITION_MARK_DONE` flips steps to `done`
  *because the code was already built outside this plan*, and for those steps
  code-canonical reconciliation is arguably the right direction. The precise
  signal is run-log evidence that **this plan's** `run` advanced the step
  (`.plan-tool/runs/<slug>/`). Recommendation: ship `status == done` plus the
  explicit override below — it is total (works with no run-log and on legacy
  plans) and the override covers the re-ground case — and treat the run-log
  refinement as a possible follow-up, not a blocker.
- **Shape:**
  - `--step N` on an implemented step → refuse, mutate nothing, print the
    alternative verbs. Non-zero rc is correct here and does **not** violate the
    exit-code convention: this is failure-to-complete (the command cannot do
    what was asked), not a findings/verdict rc.
  - whole-plan default → skip implemented steps, audit the rest, report the
    skipped count. A partially-executed plan legitimately needs its
    *unexecuted* steps re-grounded — that is the common shape, not an edge case.
  - every step implemented → refuse the invocation and name `annotate`.
  - one explicit, single-purpose override (e.g. `--allow-implemented`),
    matching the tool's "detection unconditional, mutation gated" rule.
  - `--refresh` is the same verb's cheap form and inherits the same guard.
- **Risks / fallout:** over-blocking is worse than the status quo, because it
  removes a workflow that works today. The guard must leave the
  partially-executed pre-execution case untouched — the concurrent
  `remove-vendor-scraper-poc` session on 2026-07-29 was exactly that shape
  (step 1 `current`, later steps pending) and must keep working unchanged.
  Test churn is limited to `tests/cli/test_review_cmds.py` plus the `docs/cli/`
  drift guard.
- **Dependencies:** none.
- **Effort:** small — one preflight, one flag, tests, and a `docs/cli/`
  regeneration. No new schema. The done-vs-run-log question above is the only
  non-mechanical part.
- **Scope contract:**
  - **Outcome:** `reconcile-plan` cannot mutate a plan step that an execution
    already implemented, unless the operator passes the explicit override.
  - **In scope:** `plan_tool/cli/review_cmd.py` (the `reconcile-plan` preflight
    and its `--refresh` form), `plan_tool/cli/parser.py` for the override flag,
    `tests/cli/test_review_cmds.py`, regenerated `docs/cli/`, and any
    `RUNBOOK.md` recipe that currently points the verb the wrong way.
  - **Out of scope / Non-goals:** `reconcile-code`'s direction and its own
    preflight; `annotate`; `prompts/reconcile.md`'s refusal list (the guard
    makes the prompt fence redundant in this case, it does not replace it); any
    new run-log field or schema; extending the guard to `verify-all` or
    `run --mode <review>`.
  - **Allowed behavior changes:** the refusal, the skip-and-report on the
    whole-plan default, and the new override flag — nothing else.
  - **Allowed reorganization:** none.
  - **Verification:** `--step N` on a `done` step exits non-zero, names the
    alternative verb, and leaves plan and detail byte-identical; the whole-plan
    default on a mixed plan audits only the not-implemented steps and reports
    the skipped count; the override restores today's behavior exactly; a
    fully-implemented plan is refused with `annotate` named.
  - **Stop / defer:** if the run-log-evidence refinement turns out to be needed
    rather than optional, file it separately instead of widening this entry.
- **Approach:** `direct` — a preflight and a flag inside one command's wiring,
  too small to decompose usefully.
- **Quality:** `gate-signal` — converts a directional rule that currently
  survives only as prose into a refusal at the point of misuse, and stops a
  class of silent plan-intent rewrites.
- **Origin:** 2026-07-29. A session proposed and launched
  `reconcile-plan --step 2` against the just-executed step 2 of
  `jira-grade-01-detail-instrument`; the user caught the direction error. The
  call was killed mid-flight, so nothing was saved or applied — but only
  because someone was watching.
- **Status:** not started.

**#191 — Conceptual audit treats `done` steps as context, not targets**

- **What:** the deterministic battery already skips `done` steps at a dozen
  sites (they are pre-execution authoring signals). The conceptual audit has no
  such notion: `plan_tool/prompts/plan-audit.md` contained no mention of `done`,
  so the judge saw every step alike and could spend a finding proposing edits to
  a shipped step's spec. **The prompt half shipped 2026-07-29** — a Rules bullet
  stating that a `done` step is context, that contradictions against it are
  valuable but must be stated against the *unbuilt* step, and that a shipped
  step wrong about the code is a reconciliation concern, not a completeness gap.
- **What remains:** the instruction is **advisory** — nothing enforces it. See
  #192 for the deterministic half, which this entry deliberately does not
  attempt.
- **Do not "fix" this by excluding `done` steps from the bundle.** It is the
  tempting version (it would also cut ~123KB of this plan's 216KB detail
  bundle), and it is wrong. Round 17 on `jira-grade-01-detail-instrument`
  produced `[bare-jira-bundle]` — a real defect in unbuilt step 9 — *only*
  because the judge could compare it against shipped step 7: step 7 makes a
  missing jira artifact bare, step 9 makes the same artifact a blocking
  coverage finding, and the plan never picks one. Drop step 7's detail and that
  contradiction is invisible. The axis is context-vs-target, not include-vs-
  exclude.
- **Measured yield of the problem:** on that same round, 7 of 8 findings already
  landed on unbuilt steps unprompted; 1 proposed adding acceptance criteria to
  two shipped steps. So the instruction is worth having and the loss it prevents
  is real but modest — which is the argument for keeping this entry cheap.
- **Risks / fallout:** prompt-only, so the risk is finding-mix drift on plans
  with many `done` steps. No schema, code, or flag changes.
- **Dependencies:** none. #192 builds on it.
- **Effort:** small — shipped.
- **Approach:** `direct` — one prompt edit.
- **Quality:** `audit-coverage` — stops the audit spending findings on specs
  that can no longer change, without losing cross-step contradictions.
- **Origin:** 2026-07-29, user observation during the jira-grade round-17
  checkpoint: "it doesn't make sense to update a plan after implementation."
- **Status:** prompt half shipped 2026-07-29; enforcement tracked in #192.

**#192 — Conceptual findings carry a machine-readable step id**

- **What:** every conceptual finding (`plan-correctness` / `plan-completeness`)
  is saved with `step_id = None`; all eight findings in the reviewed sample
  carry that value. The step is named only in prose ("Step 9 (`slug`)"). Have the audit prompt attribute
  each finding to a step id and parse it into the existing
  `Recommendation.step_id` field, which already exists and is already populated
  by the deterministic checks.
- **Why:** `step_id` is the join key several wanted behaviors need and none can
  have today — deterministically filtering findings whose remedy lands on a
  `done` step (#191's enforcement half), a `--step`-scoped
  `completeness-audit` (no such flag exists), and per-step finding history in
  the report sidecar. Prose parsing is the alternative and is not one: titles
  vary, and a finding can legitimately name two steps.
- **The design question to settle first:** a finding often spans steps — round
  17's `[bare-jira-bundle]` cites shipped step 7 and unbuilt step 9, and its
  remedy belongs to 9. So the field wanted is the **step the remedy edits**, not
  every step mentioned. Decide whether that is one id or an id plus a
  `mentions` list before writing the prompt contract; a single "the step this
  finding is about" field will be filled inconsistently on exactly the
  cross-step findings that matter most.
- **Risks / fallout:** the parser must tolerate a missing or unparseable id
  (leave `None`) so an older saved report and a judge that omits the field both
  keep loading — the sidecar is drift-guarded by
  `tests/test_data_contract.py`.
- **Dependencies:** none, though it is what makes #191 enforceable.
- **Effort:** medium — prompt contract, findings parser, `DATA_CONTRACT.md`,
  and tests; no new storage.
- **Scope contract:**
  - **Outcome:** conceptual findings carry the step id their remedy targets,
    parsed into `Recommendation.step_id`.
  - **In scope:** `plan_tool/prompts/plan-audit.md`, the conceptual-findings
    parser in `plan_tool/review.py`, `DATA_CONTRACT.md`, and their tests.
  - **Out of scope / Non-goals:** adding a `--step` flag to
    `completeness-audit`; filtering or suppressing any finding on the strength
    of the new field; back-filling ids on saved reports; changing the
    deterministic checks, which already populate `step_id`.
  - **Allowed behavior changes:** the new field in the prompt contract and the
    saved sidecar. No change to which findings are produced or applied.
  - **Allowed reorganization:** none.
  - **Verification:** a stubbed-invoker audit whose findings name steps yields
    populated `step_id`s; a response omitting the field still parses with
    `None`; the data-contract drift guard passes.
  - **Stop / defer:** if attribution proves unreliable on cross-step findings,
    stop and record that rather than shipping a field consumers would wrongly
    trust.
- **Approach:** `direct` — one prompt contract plus its parser and tests.
- **Quality:** `gate-signal` — turns step attribution from prose a human must
  read into a field a gate can act on.
- **Origin:** 2026-07-29, jira-grade round-17 checkpoint; split from #191 so the
  cheap advisory half could ship without waiting on the schema work.
- **Status:** not started.

**#193 — Lesson provenance: code anchors, commit, and step outcome on every citation**

- **What:** extend the lesson citation record so a lesson can be reconciled
  against the repo later. Today `~/.plan-tool/lessons/general-citations.jsonl`
  (1,462 records since 2026-05-27) carries `rule_hash`, `rule_preview`, `added`,
  and `source` (`detail:<plan-slug>#<step-id>`) — so the thread **lesson → plan
  + step already exists**. Add the three fields that make validity checkable:
  the **code anchors** the lesson generalized from (paths + symbols), the
  **commit** it was distilled at, and the **step outcome** (did it go green; was
  its detail later corrected).
- **Why:** without them a lesson's truth is unfalsifiable. The
  capture-timing defect in `BUG_BACKLOG.md` produced a global lesson whose
  example asserts a ceremony its own source retracted, and nothing could detect
  that because nothing recorded what the lesson was grounded in. `source` alone
  tells you *where* a lesson came from; it cannot tell you whether that source
  still says what it said.
- **Implementation recommendation — reuse the grounding-fingerprint pattern,
  do not import a memory framework.** `reconcile-plan --refresh` already diffs a
  tracked grounding baseline against current code, spends **zero Claude** on the
  no-drift path, and reconciles only changed files. A lesson carrying code
  anchors is structurally identical: re-resolve the anchors, no drift → still
  valid, drift → flag for review. Off-the-shelf agent-memory systems (mem0, Zep,
  Letta) do model memory lifecycle and temporal validity, and Zep's
  valid-from/valid-to fact graph is close to what #194 needs — but they are
  built for conversational user memory and model **no repo state**, which is the
  entire predicate here ("is this still true about this code?"). Adopting an
  embedding stack for a 1.6 MB markdown store also runs straight into the
  accidental-complexity rule in `CLAUDE.md`. Steal the two ideas (provenance
  edges, temporal validity); implement them deterministically over the file that
  already exists.
- **Sequencing map for the whole lessons cluster** (this entry is the hub;
  the three defects are in `BUG_BACKLOG.md`):
  1. *Stale global lesson* (bug) — one-entry data fix, do first, no dependencies.
  2. *Project-scope leak* (bug) — deterministic gate, independent, cheapest gate.
  3. *Capture timing* (bug) — biggest single win, **no new data model**, independent.
  4. **#193** provenance — enables #194.
  5. **#194** reconciliation sweep — needs #193.
  6. **#195** retrieval instead of wholesale injection — independent of #193/#194.
  7. **#197** contradiction gate at injection — build last: 2, 3, 5 and 6 all
     shrink what it must catch, so its value is highest after them.

  **Retired 2026-08-19:** #196 does not infer lesson influence or add an
  eviction policy (see `docs/history/backlog-decisions.md`).
- **Capture is opt-in as of 2026-07-31 — re-read this cluster's urgency, not its
  content.** `detail` / `reconcile-plan` only distill lessons under `--lessons`
  (was: on by default), so the stores no longer grow on an ordinary run. That
  change was made *for* this cluster — capture was paused specifically so
  #193's provenance schema and #194's reconciliation sweep could land against
  a store that had stopped growing out from under them, not as an unrelated
  policy shift. The **capture-side** entries (this one, the two capture defects
  in `BUG_BACKLOG.md`) still describe real defects but accrue new instances only
  on opt-in runs — their cost-of-delay dropped, their fix did not change. The
  **injection-side** entries (**#195** retrieval, **#197** contradiction gate)
  are untouched: every run still injects the full matching set from the 1,462
  records already on disk, so a stale or contradicting entry keeps reaching
  authoring whether or not anything new is captured. **If this cluster is
  picked up, sequence #195 and #197 (injection-side) before #193 and #194
  (capture-side)** — capture's slowed growth makes its urgency lower, while
  injection of stale/contradicting lessons happens on every run regardless.
- **Risks / fallout:** the citations file is append-only JSONL read tolerantly;
  new fields must be optional so the 1,462 existing records keep loading with
  them absent. Do not attempt to back-fill anchors for historical lessons —
  the commits are known but the generalization is not recoverable; mark
  pre-provenance records as such and let #194 skip them.
- **Dependencies:** none. Blocks #194.
- **Effort:** medium — schema extension, capture-side plumbing, tolerant reader,
  `DATA_CONTRACT.md`, tests.
- **Scope contract:**
  - **Outcome:** every newly captured lesson carries code anchors, commit, and
    step outcome; existing records still load.
  - **In scope:** `plan_tool/lessons.py`, the distill call site in
    `plan_tool/detail.py`, `DATA_CONTRACT.md`, tests.
  - **Out of scope / Non-goals:** reconciliation itself (#194); retrieval
    (#195); contradiction detection (#197); back-filling
    historical anchors; any embedding or vector dependency.
  - **Allowed behavior changes:** the new citation fields only.
  - **Allowed reorganization:** none.
  - **Verification:** a fresh capture writes all three fields; a record lacking
    them loads without error; the drift guard passes.
  - **Stop / defer:** if step outcome cannot be resolved at capture time
    (capture may precede green), record it as pending and let the
    capture-timing fix supply it — do not widen this entry to move the trigger.
- **Approach:** `direct` — one schema plus its writer and reader.
- **Quality:** `grounding` — makes a lesson's basis inspectable instead of
  assumed.
- **Origin:** 2026-07-30, jira-grade authoring-model probe; the lessons cluster
  was discovered while checking whether a plan-body fence reaches
  `prompts/detail.md`.
- **Status:** not started.

**#194 — Reconcile lessons against the code they generalized from**

- **What:** a read-only sweep that re-resolves each lesson's recorded anchors
  (#193) against current code and flags the ones whose basis moved: anchor gone,
  source detail corrected, or the source step never shipped. Output is a report,
  not a mutation.
- **Why:** this is the retraction path the capture-timing defect showed missing.
  A lesson minted from prose that a later audit deleted stays authoritative
  forever; nothing re-examines it. Lessons are the one input to authoring that no
  audit inspects — `create`, `detail`, and every completeness pass scrutinize the
  plan and the detail, while the lessons shaping both go unchecked.
- **Implementation recommendation:** model it on `reconcile-plan --refresh`'s
  fingerprint gate — deterministic, no Claude on the no-drift path. Keep it
  **recommend-only** (detection unconditional, mutation gated), matching
  `escalate_to_split` and `scope-out`. A flagged lesson is reviewed by a human or
  an explicit opt-in verb; the sweep never edits the store.
- **Risks / fallout:** anchor churn from ordinary refactors will flag lessons
  that are still true — expect noise and tune on real data before adding any
  auto-action. Pre-provenance records (the existing 1,462) cannot be swept; skip
  them explicitly rather than reporting them as unverifiable.
- **Dependencies:** **#193** (hard — no anchors, nothing to resolve).
- **Effort:** medium.
- **Scope contract:**
  - **Outcome:** a read-only report naming every lesson whose recorded basis no
    longer resolves, with the reason.
  - **In scope:** the sweep over `~/.plan-tool/lessons` + the per-repo store,
    the anchor re-resolution, the report surface, tests.
  - **Out of scope / Non-goals:** editing or deleting any lesson (recommend-only);
    provenance capture (#193); retrieval (#195); back-filling
    anchors onto pre-provenance records.
  - **Allowed behavior changes:** the new report only — no store mutation.
  - **Allowed reorganization:** none.
  - **Verification:** a lesson whose anchor was deleted is flagged; one whose
    anchors still resolve is not; pre-provenance records are reported as
    unsweepable rather than as drifted.
  - **Stop / defer:** if flag noise from ordinary refactors is high, report the
    rate and stop — do not add auto-retraction to compensate.
- **Approach:** `plan-tool` — the flag-vs-noise policy is an open design call.
- **Quality:** `grounding` — closes the loop between a lesson and its source.
- **Origin:** 2026-07-30, jira-grade authoring-model probe.
- **Status:** not started; blocked on #193.

**#195 — Retrieve relevant lessons instead of injecting the matching set wholesale**

- **What:** replace `when:`-condition matching over a 1.6 MB store with
  relevance-ranked selection of the top-k lessons for the step being authored,
  with a floor below which nothing is injected.
- **Why:** two costs, one of which is correctness. Prompt budget is the obvious
  one. The other is that **every injected lesson is a chance to contradict the
  plan** — the rendered `detail` prompt for one step carried a plan fence
  forbidding export gates and a lesson asserting one, ~90 lines apart. Fewer,
  better-targeted lessons shrink that surface directly, which is why this
  outranks building a detector (#197).
- **Implementation recommendation:** stay deterministic first. Rank on signals
  already available — anchor overlap with `step.files`/`creates`, `change_type`
  match, recency, and citation count — before reaching for embeddings. If
  lexical ranking proves insufficient, `sqlite-vec` is the smallest step up (a
  single file, no service) and should be justified against a measured miss rate,
  not adopted by default. The determinism ladder in
  `docs/NONDETERMINISM_PLAN_DESIGN.md` applies.
- **Risks / fallout:** a relevance floor can drop a lesson that would have
  helped; that failure is silent. Log what was withheld, per the no-silent-caps
  rule.
- **Dependencies:** independent. Benefits from #193's anchors for ranking, but
  does not require them. Reduces #197's load.
- **Effort:** medium.
- **Scope contract:**
  - **Outcome:** `detail` receives a ranked, bounded lesson set instead of every
    `when:`-matching entry, and logs what it withheld.
  - **In scope:** the lesson selection path feeding `${lessons_block}`, the
    ranking signals, the withheld-count log line, tests.
  - **Out of scope / Non-goals:** changing lesson *content* or capture (#193 and
    the BUG_BACKLOG capture-timing entry); contradiction detection (#197);
    adopting an embedding or vector dependency without a measured miss rate
    justifying it.
  - **Allowed behavior changes:** which lessons reach the prompt, and the new
    withheld-count line.
  - **Allowed reorganization:** none.
  - **Verification:** an authoring run injects at most k lessons; the withheld
    count is logged (no silent caps); a store with no relevant entry injects
    none rather than filler.
  - **Stop / defer:** if lexical ranking cannot beat `when:`-matching on a
    measured sample, stop and record that rather than escalating to embeddings.
- **Approach:** `plan-tool` — ranking policy is an open design call.
- **Quality:** `audit-coverage` — fewer irrelevant lessons means fewer invented
  requirements downstream.
- **Origin:** 2026-07-30, jira-grade authoring-model probe.
- **Status:** not started.

**#197 — Contradiction gate: reject injected content that violates a plan's stated fence**

- **What:** when a plan supplies a `## Scope guardrails` denylist, check the
  other blocks the `detail` prompt injects — lessons, sibling details, jira
  stories — for content asserting the denied vocabulary, and fail or warn before
  the call.
- **Why:** the failure is observed, not hypothetical. A rendered prompt carried
  *"no export gate is needed"* (plan fence, reaching `detail` via
  `extract_plan_guardrails` → `${plan_guardrails_block}`) and *"the detail's
  export gate had to record…"* (global lesson) in the same 900 lines. Whichever
  wins, wins by chance.
- **Implementation recommendation, and the reason this is #8 not #1:** do **not**
  build a general prose-contradiction detector — that is an LLM judgment task
  with mediocre precision over a long prompt, and this arc already cut one
  speculative comparison mechanism (Decision 4 on
  `2-jira-grade-01-detail-instrument`) that gated nothing while generating ~29%
  of ten audit rounds' findings. Exploit the fact that a fence is a
  **denylist**: match its named prohibitions against injected blocks, the same
  shape as `jira_grade.py`'s filler-phrase denylist — deterministic, no Claude.
  The hard part is negation ("no export gate is needed" contains "export gate"),
  which is exactly why this stays a narrow gate rather than a general detector.
- **Risks / fallout:** false positives block authoring, so start as a **warning**
  and promote to blocking only on measured precision. Build it **after** the
  capture-timing fix, the scope gate, and #195 — each shrinks the input this has
  to police, and building first means tuning against noise those fixes remove.
- **Dependencies:** independent to build, but **sequence it last** (see #193's
  map). Requires no provenance.
- **Effort:** small-to-medium.
- **Scope contract:**
  - **Outcome:** a prompt-assembly check that surfaces injected content
    asserting what the plan's `## Scope guardrails` denylist forbids.
  - **In scope:** the denylist parse, the match over injected blocks, the
    warning surface, tests.
  - **Out of scope / Non-goals:** a general prose-contradiction detector or any
    Claude call to judge contradiction; auto-suppressing the offending block;
    editing the fence or the lesson; blocking authoring before precision is
    measured.
  - **Allowed behavior changes:** a new warning. Blocking is a later, separate
    decision.
  - **Allowed reorganization:** none.
  - **Verification:** a fence forbidding X plus an injected block asserting X
    warns and names both sides; a fence with no conflict is silent; a negated
    mention ("no X is needed") does not fire.
  - **Stop / defer:** a fence/content conflict means **examine both** — the
    fence may be the defective party (observed: a fence banning "multi-deploy
    ordering rules" outlawed a constraint the plan depended on). Never resolve
    it by suppressing content.
- **Approach:** `plan-tool` — the negation-handling and warn-vs-block policy are
  open calls.
- **Quality:** `gate-signal` — turns a silent prompt-level contradiction into a
  surfaced one.
- **Origin:** 2026-07-30, jira-grade authoring-model probe; the user's
  instinct was that contradiction detection is needed, and it is — but as the
  last layer, not the first.
- **Status:** not started.

**#198 — Plan provenance in git: structured trailers, a rebuildable archive ledger, and an archive *reason***

- **What:** make "which plans were actually implemented, and where did that land
  in git?" answerable by machine. Three parts: **(a)** structured trailers on
  per-step green commits; **(b)** a rebuildable archive ledger recording the
  landing SHAs;
  **(c)** an explicit archive **reason**, because implemented and superseded
  plans are indistinguishable today.
- **Why:** the only durable trail now is the green-commit *subject*
  (`plan(<slug>): step N green — <title>`, `cli/run_cmd.py:_green_commit_subject`),
  which is prose parsed by `--grep` and breaks on hand-advanced steps, hand
  commits, and `--commit`-less runs. No trailer mechanism exists on these
  commits today (the operator's no-attribution policy rules out an
  AI-attribution trailer as that mechanism), so this introduces new
  machinery rather than extending existing plumbing. **This entry is the
  enabler for #199**: deleting plans from the filesystem is only safe once
  the git record is reliable.
- **Implementation recommendation:**
  - **(a) Trailers.** Add `Plan-Slug: <slug>` and `Plan-Step: <n>` to green
    commits, so `git log --grep='^Plan-Slug: foo' ` and `git
    interpret-trailers` both work without parsing prose. Consider
    `Plan-Fingerprint:` for the plan revision the step ran against.
  - **(b) Archive ledger — and it has nowhere to live today.** The manifest
    (`.plan-tool/plans.json`) is a **bare list of repo-relative paths with no
    metadata field of any kind**, and an archived plan is *dropped from it
    entirely* — so there is currently **no index of archived plans at all**, and
    `list` has no `--archived` (only `--status`, over active plans). Add an
    append-only `.plan-tool/archive-ledger.jsonl`, one line per archived plan,
    rather than growing the manifest: the manifest answers "what is live", and
    mixing dead entries into it makes every consumer filter.
  - **The ledger must be a rebuildable cache, not a second source of truth.**
    Every field it holds is derivable from the archive commit's trailers, so a
    lost or stale ledger is regenerated by walking the log — never reconciled by
    hand. That property is what keeps this from repeating the archive-folder
    mistake (#200): a parallel store that drifts from the thing it mirrors. Same
    shape as the re-derivable grounding baseline behind
    `reconcile-plan --refresh`.
  - **Context worth capturing at archive time** — chosen because each is cheap
    then and expensive to reconstruct later: slug and title; archive **reason**
    (see (c)); the archive commit SHA and the step→landing-SHA map; a diffstat
    or touched-file summary; a **superseded-by** pointer to the plan or seed
    that replaced it; and the **verification verdict at archive time**
    (`verify-all --rollup`), which answers "was it actually done?" at the one
    moment the answer is cheap.
  - **(c) Reason.** `implemented` / `superseded` / `cut` — without it, "list of
    implemented plans" is unanswerable and #199 becomes unsafe.
  - **Cover both archival routes.** A plan reaches "implemented" either by the
    `run` pipeline (green steps, trailers present) **or** by jira tickets
    shipping the work outside `run`. For the second, the join key already exists:
    `plan-tool jira` emits stories carrying `steps:` and `<EPIC>-S<N>` ids, so a
    ticket→step map is derivable from the export without a backend call. Ticket
    *status* does need a backend query — keep that opt-in and treat its absence
    as "unknown", never as "not implemented".
  - **The strongest signal is neither**, and is worth naming as the fallback:
    `verify-all --rollup` / `reconcile-code` read whether the code actually
    covers each step's declared deliverables. That is process-independent — it
    works for a plan implemented by hand, by tickets, or by `run` — and should
    be the tiebreaker when the trailer record and the ticket record disagree.
- **Risks / fallout:** trailers only exist going forward; historical plans have
  subject-prose only. Do not back-fill by rewriting history — accept a
  `provenance: legacy` tier and let queries report it honestly.
- **Dependencies:** none. **Blocks #199.**
- **Effort:** medium — trailer emission is small; the reason field and the
  ticket-route join are the design work.
- **Scope contract:**
  - **Outcome:** every newly landed plan step and every newly archived plan is
    locatable in git by structured query, with its archive reason recorded.
  - **In scope:** `plan_tool/cli/run_cmd.py` green-commit path, the archive
    path, the new `.plan-tool/archive-ledger.jsonl` plus its rebuild-from-log
    path, `list --archived` as the index surface, `DATA_CONTRACT.md`, tests.
  - **Out of scope / Non-goals:** deleting plans from the filesystem (#199);
    rewriting historical commits; a live jira backend integration beyond the
    already-exported story→step map; changing what `run` commits.
  - **Allowed behavior changes:** new trailers on green commits; new manifest
    fields. Commit *subjects* stay byte-identical — they are load-bearing for
    existing greps.
  - **Allowed reorganization:** none.
  - **Verification:** a `--commit` run emits parseable trailers; `list
    --archived` names every archived plan with its reason; an archived plan
    resolves to its landing SHAs from the ledger alone; **deleting the ledger
    and rebuilding it from the log reproduces it byte-for-byte** (the property
    that makes it a cache); legacy plans report `legacy` rather than a wrong
    answer.
  - **Stop / defer:** if the ticket-status query needs credentials or a network
    call in a code path that must stay offline, defer that route and ship the
    `run` + `verify-all` routes.
- **Approach:** `plan-tool` — multi-surface with an open reason/tier design call.
- **Quality:** `grounding` — replaces prose-parsed provenance with a queryable
  record.
- **Origin:** 2026-07-30, from the archive-redundancy finding: git already holds
  what the filesystem archive duplicates, but nothing makes git *queryable* for
  which plans shipped.
- **Status:** not started.

**#199 — Git-native archive: delete the plan from the filesystem instead of moving it**

- **What:** replace the `archive/` directory convention with deletion — `git rm`
  the plan and its detail bundle, letting git history be the archive — plus a
  retrieval verb so the workflow never requires hand git archaeology.
- **Why:** the moved copy is redundant with git by construction (measured: an
  archived detail copy was **byte-identical** to its committed baseline), and a
  live `archive/` tree keeps superseded design in the working set where greps,
  audits, and readers still hit it — the exact hazard `CLAUDE.md`'s
  forward-looking-documentation directive names. Deleting also forces the
  "which plans shipped?" question to be answered properly (#198) rather than by
  listing a directory.
- **Implementation recommendation:**
  - **Retrieval is the load-bearing half.** Ship `plan-tool archive show <slug>`
    (and `restore`) resolving through the manifest's recorded archive SHA
    (#198b) to `git show <sha>:<path>` — O(1), no log search. Without this the
    change trades rot for friction.
  - **Fix the callers that read the archive from disk first.** `create
    --reprocess` fills `_(TODO)_` placeholders from an archived predecessor;
    `annotate --archive` writes numbered `.replaced.N` generations. Both need a
    git-backed read path before deletion is safe.
  - **Audit live citations before deleting anything.** Prose across the repo
    cites archived artifacts by path — e.g. the jira-grade handoff cites
    `docs/implementation-plans/archive/plan-details/jira-grade-detail-side-by-side-evaluation/reports/`
    as spin evidence. A path-resolution sweep must run first, and surviving
    citations must be rewritten to the retrieval form.
  - **Gate on reason.** Delete only `implemented` and `superseded` plans.
    A `cut` plan mid-decision should stay on disk until its decision lands.
- **Risks / fallout:** the failure mode is discoverability, and it is silent —
  nobody notices a plan is unfindable until they need it. Ship retrieval and
  the citation sweep **before** the first deletion, and keep deletion an
  explicit opt-in verb, never a side effect of completion.
- **Dependencies:** **#198** (hard — deletion without a queryable git record
  loses the plan). Composes with #200, which applies the same principle to
  detail files.
- **Effort:** medium.
- **Scope contract:**
  - **Outcome:** archiving a plan removes it from the working tree, and any
    archived plan is retrievable by slug without hand git archaeology.
  - **In scope:** the archive path, the retrieval verb, the git-backed read for
    `create --reprocess`, the citation sweep, migration of existing plan-level
    archives, tests.
  - **Out of scope / Non-goals:** provenance capture (#198, a hard dependency);
    per-detail `archive/` folders (#200/#201); `annotate --archive`'s
    `.replaced.N` generations; deleting a `cut` plan whose decision is unsettled.
  - **Allowed behavior changes:** archival deletes instead of moves; the new
    retrieval verb.
  - **Allowed reorganization:** none beyond removing the archive tree.
  - **Verification:** an archived plan is absent from the working tree and
    retrievable by slug; `create --reprocess` still resolves its predecessor;
    no doc cites a path that no longer resolves.
  - **Stop / defer:** if a caller needs archived content on disk in a way git
    retrieval cannot serve, stop and keep moving that class rather than
    weakening retrieval.
- **Approach:** `plan-tool` — multi-surface with a migration and open retrieval
  UX.
- **Quality:** `audit-coverage` — removes superseded design from the surface
  that audits and greps read.
- **Origin:** 2026-07-30, user proposal during the lessons-store investigation.
- **Status:** not started; blocked on #198.

**#202 — Claim-to-test coverage: every acceptance criterion should name a test**

- **What:** compare a step's declared `## Acceptance criteria` against its
  `## Tests` roster and the test functions actually present, and surface
  criteria with no corresponding case.
- **Why — measured this session, not hypothetical.** Four of the eight executed
  steps shipped **a named guarantee with no assertion behind it**, and every one
  passed the test-authoring gate, its step gate, and the full 6,749-test suite:
  - step 2: an assertion that passed **vacuously** (the fixture carried no
    `change_type`, so the check short-circuited before any logic ran);
  - step 3: a documented "keep in sync" invariant with **no test at all**;
  - step 5: the export promises *"an operator repairing a bundle wants the whole
    list, not the first line"* — **nothing asserts it**; truncating the problem
    list to one entry leaves the suite green (confirmed by mutation);
  - step 7: an acceptance criterion naming **three** side effects the guard must
    precede, with tests asserting **two**.
  All four are the same shape: *a claim in the detail with no test behind it.*
- **Why the tool can check this at all:** both halves are already
  machine-readable and required by the run-grade contract. Nothing compares
  them today.
- **Implementation recommendation:** model it on
  `review.py:detect_claim_vs_delivery`, which already does claim-vs-delivery for
  *deliverables* — this is the same shape applied to *assertions* for
  run-grade detail. Deterministic, no Claude. **Ship it advisory (`info`),
  not blocking**, matching the existing
  fuzzy claim matcher's own calibration (*"fuzzy prose matching can
  false-positive, so this never blocks"*); promote only on measured precision.
- **Scope note: there is no longer a `refactor` pre-change contract to cover.**
  A sibling entry once proposed verifying that a refactor step's tests pass
  against **pre-change** code. It was measured and **withdrawn 2026-07-30** —
  81–89% of real refactor steps cannot satisfy it for legitimate reasons (see
  `CLAUDE.md` § "Withdrawn: the per-`change_type` test-ordering contract").
  This entry stands on its own and must **not** be widened to revive it.
- **Risks / fallout:** naming-level matching is fuzzy in both directions — one
  test can satisfy several criteria, and one criterion can need several tests.
  Report unmatched criteria, never "excess" tests.
- **Dependencies:** none. Composes with #197 only insofar as both are
  prompt/plan consistency checks.
- **Effort:** medium — the extraction is easy, the matching heuristic and its
  precision calibration are the work.
- **Scope contract:**
  - **Outcome:** an advisory finding per acceptance criterion with no
    identifiable test case.
  - **In scope:** the run-grade claim/roster extraction, the matcher, its
    registry entry, and tests.
  - **Out of scope / Non-goals:** blocking on the finding before precision is
    measured; reviving any refactor pre-change ordering check; mutation testing; coverage
    thresholds; judging test *quality* beyond existence.
  - **Allowed behavior changes:** one new advisory finding source.
  - **Allowed reorganization:** none.
  - **Verification:** a step whose criterion has no test is flagged; a step whose
    criteria are all covered is silent; the finding never flips an exit code.
  - **Stop / defer:** if precision is poor enough that operators learn to ignore
    it, stop and report the rate rather than tuning indefinitely — a
    always-ignored advisory is worse than none.
- **Approach:** `plan-tool` — the matching heuristic is an open design call.
- **Quality:** `audit-coverage` — closes the gap between what a step promises
  and what it proves.
- **Origin:** 2026-07-30, from a 15-mutation spot-check over this session's
  shipped guards (14 caught, 1 unasserted guarantee) plus four review findings
  of the same shape.
- **Status:** not started.

**#208 — `roadmap` arc position 05: framework lenses** *(anchor entry for the `roadmap-NN-*` seed group)*

- **What ships today (positions 01–04, 2026-07-31 → 2026-08-05).**
  `plan-tool roadmap <slug> --from-existing <concept.md> [--from-stage N]` turns
  a concept brief into four gated artifacts — `01-domain.md`,
  `02-constraints.md`, `03-components.md`, `04-roadmap.md` under
  `docs/implementation-plans/roadmaps/<slug>/` — plus draft seeds at each plan
  row's `draft_seed_path`, non-interactively, retrying a stage with its gate
  violations quoted back and exiting non-zero only when one exhausts its retry
  budget. Revision mode carries `feedback` and `removals` rows so `--from-stage N`
  revises the reviewer's copy instead of regenerating over it. Completion prints
  runnable `create --from-existing` lines; `plan-seeds/` mutation is opt-in via
  `--apply` (+ confirm or `-y`). Contract in `ROADMAP_FORMAT.md`; operator
  workflow in `USE_CASES.md` (entry 11), `RUNBOOK.md`,
  `docs/ROADMAP_WALKTHROUGH.md`, and `integrations/claude/SKILL.md`; flags in
  `docs/cli/roadmap.md`.
- **What remains — position 05, and it is the whole of this entry.**
  `roadmap-05-framework-lenses`: the lens registry, an `aws-well-architected`
  descriptor, a `--framework` flag, a lens-driven stage-2 prompt, and a coverage
  gate that fails a response leaving a pillar undischarged and undeferred.
  Stages 1–4 ship on the generic default lens, so this is additive — no existing
  stage changes shape.
- **Why:** the constraints stage today ranks quality attributes the model infers
  from the brief. A lens supplies the attribute vocabulary from an external
  framework instead, so a reviewer can ask "did it discharge *every* pillar"
  rather than "is this list plausible" — a binary coverage question a gate can
  answer, which is the only kind this arc adds. **Greenfield runs are the
  highest-leverage case** (2026-08-13 greenfield-scenario review): stage 2 is
  repo-blind on every project, but on an existing one the reviewer can
  sanity-check the inferred attribute list against a stack and operational
  history they already know, while a greenfield brief gives the reviewer no
  such anchor — the external vocabulary is doing the most work exactly where
  the roadmap verb is the intended entry point (#270–#272 file the sibling
  greenfield gaps).
- **Effort:** medium — one new data-driven descriptor family plus a coverage
  gate, against four stages of existing pattern (invoker seam, response gates +
  reprompt, artifact re-parse discipline, run log).
- **Risks / fallout:** a lens that names pillars the brief cannot speak to turns
  the coverage gate into a spin generator — the gate must accept an explicit
  *deferred* disposition, not only a discharge. Multi-framework composition in
  one run stays out (below).
- **Dependencies:** none hard. **Related:** **#184** (seed-dir resolution).
- **Note the two numbering axes:** artifact stages 1–4 and seed positions 01–05
  do not line up (the components *artifact* stage 3 is seed position 03 only by
  coincidence of the later renumber). Prefer naming stages, not numbering them.
- **Scope contract:**
  - **Outcome:** `plan-tool roadmap <slug> --framework aws-well-architected`
    ranks and discharges that framework's attribute vocabulary in
    `02-constraints.md`, and the stage refuses a response that leaves a pillar
    neither discharged nor explicitly deferred.
  - **In scope:** the lens registry and its descriptor format, the
    `aws-well-architected` descriptor, the `--framework` flag, the lens-driven
    stage-2 prompt branch, the coverage gate, `ROADMAP_FORMAT.md`, `docs/cli/roadmap.md`.
  - **Out of scope / Non-goals:** multi-framework composition in one run;
    lens-driven stages 1, 3, or 4; interactive decision walks; roadmap-coherence
    audit machinery; auto-running `create`; manifest tracking of roadmap
    artifacts or seeds; any judgment-dependent gate — coverage is a set
    comparison or it does not ship.
  - **Allowed behavior changes:** the new flag and the stage-2 branch it selects.
    The default (no `--framework`) keeps today's generic behavior byte for byte.
  - **Allowed reorganization:** none.
  - **Verification:** hermetic fixture-driven tests with stubbed invokers — the
    coverage gate demonstrably rejects a reply leaving a pillar undischarged and
    undeferred, and passes one that defers it explicitly; a default-lens run is
    unchanged.
  - **Stop / defer:** taxonomy extensions beyond the one descriptor, and any
    second framework, are follow-ups — file them. Stop and re-scope if lens
    coverage cannot stay a set comparison.
- **Settled, do not re-open** — four decisions govern this arc and are recorded
  in `docs/history/backlog-decisions.md` (#208): the **collaborative framing**
  (the verb proposes and re-proposes against feedback; it is not a replacement
  for human authorship and is not measured as one — and components and lenses
  are *not* to be re-cut on one-shot-quality grounds); the **naming** reservation
  of "roadmap" for this pipeline; the **narrow** reading of decision-record
  Carve B; and the revision prompt's **scope-clarification** permission.
- **Live design constraint inherited from the arc:** emitted seeds anchor to
  **entity ids**, the only row kind stable enough to cite across a re-author.
  Nothing downstream may anchor to a field name across a *regeneration* — within
  a revision chain they are stable, which does not license the cross-re-author
  case. Evidence: `docs/ROADMAP_RUN_MEASUREMENTS.md` § 1.
- **Evidence:** `docs/ROADMAP_RUN_MEASUREMENTS.md` (both briefs, the feedback
  loop, the decision-record rule's four branches, and the first stage-3/stage-4
  runs) and `docs/ROADMAP_LAYERING_MEASUREMENT.md` (the 2026-08-01 three-arm
  comparison — read its "How to read this result" before citing it).
- **Residuals filed separately, not folded here:** **#217** (persist the reply
  bytes a dead stage discards).
- **Approach:** `plan-tool` — a new prompt branch plus a gate with a persisted
  descriptor format; the arc convention sends it through a seed.
- **Quality:** `grounding` — a lens replaces an inferred attribute vocabulary
  with an external one, so the constraints artifact's coverage becomes checkable
  rather than plausible.
- **Iterate:** standard recipe, current directives.

  ```bash
  plan-tool create roadmap-05-framework-lenses -y --from-existing plan-seeds/roadmap-05-framework-lenses.md
  plan-tool detail roadmap-05-framework-lenses -y --commit
  plan-tool completeness-audit roadmap-05-framework-lenses --iterate --audit-passes 1 -y
  # then close the conceptual gaps by hand
  plan-tool run roadmap-05-framework-lenses --all --commit
  # post-run tail: plan-tool reconcile-code roadmap-05-framework-lenses --all
  ```
- **Origin:** 2026-07-31, user request: project-concept → initial plan set with
  explicit domain/constraint/component/pattern layering, educated-guess decisions
  with alternatives called out, and architecture-framework alignment (AWS
  Well-Architected named). Positions 01–04 discharged everything but the
  framework half.
- **Status:** positions 01–04 shipped; **position 05 parked and unauthored**.
  Re-enter only for a named framework-specific roadmap need with a checkable
  coverage contract.

**#217 — Roadmap rejected-response evidence (consolidated)**

- **Consolidated 2026-09-21:** this is provenance for the completed roadmap
  rejected-response slice, not an implementation route. The shared
  `model_failure_receipt` now covers fresh stage authoring,
  `_run_bounded_stage_feedback`, and local `--revise-feedback`; `AttemptFailed`
  continues to record retry-spending failure kinds for the stage loop.
- **Owner:** [BUG_BACKLOG.md — "Model-backed commands do not share one complete
  terminal failure receipt"](BUG_BACKLOG.md#model-backed-commands-do-not-share-one-complete-terminal-failure-receipt)
  owns the receipt contract and all remaining producer migrations.
- **Related history:** #215 closed 2026-08-05 after `AttemptFailed` made retry
  pressure observable. The Integration evidence that expanded this scope originated
  in bounded feedback and local revision, which the shipped roadmap slice now
  covers.
- **Status:** consolidated provenance only; do not create a separate roadmap
  implementation route, retention policy, reader command, or cross-command
  completion claim here.

**#216 — A quality benchmark for plan-tool's own output, floors first** *(anchor entry for the `quality-bench-NN-*` seed group)*

- **What:** a `bench` verb group that replays a fixed corpus of seeds through
  an authoring stage, stores the artifacts, and reports metric deltas between
  two labelled runs **against each metric's own measured rerun spread**. The
  point is to make "did this change help?" answerable over time. The arc
  deliberately ships **no model-scored metric in position 01**.
- **Why floors come first, and why this entry is not #164 again.** Nobody
  knows what any of these metrics do when *nothing changes*. Measured on
  `roadmap` stage 2, 2026-08-01, three runs on byte-identical input (all three
  logged `prompt_bytes = 33942`): quality-attribute dispositions came back
  **7 of 7 identical** every time, constraint row ids shared **1 of 19**
  between two runs, and gate attempts went 3, 1, 1. A benchmark scoring
  "constraint set quality" across a code change would have reported a large
  delta caused by nothing; one scoring "disposition ranking" would have been
  reading real signal. **The dimension decides whether a metric is a metric**,
  and only replaying an unchanged tree tells you which is which.

  This repo has already paid for skipping that. **#164**'s one-off mechanism
  falsification check was cut 2026-07-29 — ~29% of findings across ten audit
  rounds traced to it or its `--bundle-framing` control, it gated nothing, and
  at n=1 sampler variance swamped the signal — and that entry's Out of scope
  now forbids re-introducing a comparison or control arm. This is not that: it
  is the missing prerequisite that would have told #164's evaluation it had no
  power before it spent ten rounds.
- **The question it asks, named:** **monitoring, not decision**
  (`docs/NONDETERMINISM_PLAN_DESIGN.md` Rule 6's fork) — floors and trends over
  a corpus, not controlled arms choosing between two futures. Rule 3 (climb the
  determinism ladder before adding a judge) is why position 01 has no judge,
  and CLAUDE.md § "Validating a semantic property you cannot observe" applies
  in full: the deliverable is a number computed from stored bytes, never an
  opinion about them.
- **Stage arc (this entry is the group anchor; later seeds stay unauthored
  placeholders until predecessors ship):**
  1. `quality-bench-01-corpus-and-noise-floor` — a future corpus/replay route
     only if the first disposable observation demonstrates a durable surface is
     needed. It is not a current runner, artifact store, or command.
  2. `quality-bench-02-judged-metrics` — the model-scored rubric layer,
     **admitting only metrics whose floor from position 01 is narrower than
     the effect they claim to detect**, with N-sample aggregation. Unauthored:
     its whole design input is position 01's floor table, which does not exist
     yet.
- **Benchmark-adjacent calibration route (not `quality-bench-NN` positions):**
  `risk-profile-1` (#181) persists an operator-confirmed work-shape tier;
  completed `risk-profile-2` (#182) supplies advisory context to run-grade
  detail authoring and review; completed #295
  adds a visible certainty signal to `Recommendation` findings; then position
  01 establishes the corpus and noise floors needed before confidence claims
  are generalized or calibrated. This order keeps risk (change impact),
  confidence (evidence support), and benchmark evidence distinct.
- **Re-triage (2026-08-28):** retain position 01's noise-floor question, but
  withdraw its current three-step plan. Even after its earlier scope reset,
  that plan builds a corpus format, persisted record, runner, CLI, and
  documentation before one current-model exercise demonstrates that a durable
  replay surface is needed. First run one disposable two-item, serial stage-2
  observation with an explicit Codex backend and record only the three factual
  measurements. It must create no new command or reusable storage. A fresh
  bare plan is justified only if that observation cannot answer the question or
  demonstrates a repeated durable replay need. It receives completed risk and
  confidence surfaces only as context for what later claims might concern; it
  does not score either field, turn either into a decision rule, or merge their
  contracts. `#316` renderer consolidation remains separate display hygiene.
- **Prior scope reset (2026-08-27; historical):** the seven-step
  `quality-bench-01-corpus-and-noise-floor` plan received repeated
  completeness-stage `split=1` then `split=2` assessments (for example,
  telemetry decisions `3a1543ba94050e6a`, `ab34e1d31cb647f8`, and
  `5975b3732a4fb9dd`). This is detector case **(a)**: the signal fired but was
  not acted on. The user-directed conclusion is that position 01 is a
  three-step smallest-proof feasibility effort, not a reusable benchmark
  subsystem. That conclusion reduced the plan but did not make its runner and
  CLI necessary; the plan is now historical, not the selected scope.
- **Current effort:** a single low-cost observation. Any future verb group,
  metric registry, artifact store, or data-contract row needs fresh evidence
  from that observation rather than inheriting this entry's old product shape.
- **Risks:** the corpus is a **recurring Claude spend** — the roadmap smoke run
  was ~$2.50 for two stages, so R reruns × N items is the whole budget
  conversation, and a floor needs R > 1 by construction. A corpus that drifts
  silently makes every historical label incomparable, so it changes only by
  committed edit. And the honest failure mode: if most deterministic metrics
  floor noisier than any plausible change effect, this corpus cannot support a
  benchmark at an affordable R — **that is a result, not a reason to grow the
  corpus.**
- **Dependencies:** none hard. **Related:** **#164** (the cut evaluation, and
  the reason for the ordering), **#215** (closed 2026-08-05; the per-verb
  variance question it raised is recorded in
  `docs/history/backlog-decisions.md`), the `gate_violations` run-log event (shipped
  2026-08-02), which makes gate-attempt metrics diagnosable rather than merely
  countable.
- **Future capability boundary** (not current scope; a later evidence-backed
  seed pins its own):
  - **Outcome:** a repeatable corpus replay that reports metric deltas between
    two labelled runs against each metric's measured rerun spread.
  - **In scope:** the `bench` verb group, the corpus directory format and its
    versioning, the artifact store under `.plan-tool/bench/`, the deterministic
    metric registry, floor computation and persistence, `DATA_CONTRACT.md`
    rows.
  - **Out of scope / Non-goals:** any model-scored metric in position 01; any
    metric asserting an artifact is good, better, or well-grounded; any
    agreement check between two prose artifacts; any gate, exit-code flip, or
    CI blocking; control arms or matched baselines; auto-tuning anything from a
    metric; expanding the corpus past one verb; shape or length caps; parallel
    fan-out to make the corpus faster.
  - **Allowed behavior changes:** the new `bench` verb group and its stored
    artifacts. No existing surface changes — the harness observes them through
    their CLI.
  - **Allowed reorganization:** none.
  - **Verification:** a two-item corpus replayed R times at one commit with a
    stubbed invoker produces a floor per metric; a constant metric floors at
    zero spread and a deliberately-varied one floors wider; two labels from the
    same commit compare `inside noise` on every metric; deleting computed
    metrics and recomputing from the store reproduces them exactly.
  - **Stop / defer:** if the floors show the corpus cannot support a benchmark
    affordably, report that and stop rather than widening. Per-verb variance
    findings go to that verb's entry.
- **Future approach:** `plan-tool` only if observation evidence justifies a
  persisted replay contract and staged arc.
- **Quality:** `heuristic-tuning` — this *is* the facet's definition: the data
  that lets every threshold behind the other facets be calibrated from a
  distribution rather than single-session anecdote.
- **Origin:** 2026-08-01, user request for a systematic LLM-judged quality
  suite to track the impact of changes over time; re-ordered floors-first
  against the rerun-variance data the same session produced.
- **Status:** no active position-01 seed or plan. The withdrawn plan and its
  audit reports preserve the rejected runner/CLI shape as history. Position 02
  remains unauthored until a future, reviewed floor record exists.

**#238 — Report plan mass in the completeness report, so a growing plan is visible beside a falling finding count**

- **What:** The convergence loop measures **findings**; it does not measure the
  **artifact**. Those curves can diverge: findings fall while the plan grows,
  because the fix for a finding is usually more plan. The stopping rule reads
  that as healthy convergence, correctly by its own definition, and no surface
  reports the other half. Emit a per-report `plan mass` line — step count and
  detail-bundle size, each with a delta against the first audit of the same
  plan, plus four structural ratios computed from the frontmatter — so the
  reader can see both curves at once.
- **Why now:** `split-criteria` has three altitudes. Altitudes 2 and 3 have
  computable predicates that fire or don't. Altitude 1 (*plan too big → split
  into multiple plans*) reports `not evaluated (Claude-judged)` because it is
  judged once, on the create-time seed, before the plan exists — so a plan can
  only be judged too big at the moment it is smallest. Everything that grows a
  plan afterward (audit-applied findings, added steps, added criteria) is
  invisible to the one altitude that would catch it.
- **The three convergence states**, of which only two have names today:
  - findings ↓, mass flat → **converging** (the intended exit)
  - findings flat, mass ↑ → manual scope/design review is required
  - findings ↓, mass ↑ → **absorbing** — no name, no signal
- **The four ratios**, all computable from `depends_on` / `files` / `creates`
  plus a grep over the detail bodies:
  - **Keystone fan-out** — `max(|depends_on|) / (N-1)`, excluding non-code
    aggregator steps. A step requiring most of the plan to exist before it can
    run is not a step; it is the plan with a runway.
  - **Satellite ratio** — share of steps whose only non-docs dependent is the
    keystone. These are preconditions, not features.
  - **Inert-step ratio** — share of steps whose detail states that nothing
    user-visible changes. Needs no new authoring: detail bodies already
    volunteer this in prose ("nothing renders differently", "is not edited").
  - **Audit-induced growth** — steps created by an apply rather than by the
    author. The run journal already carries the provenance; it is not surfaced.
    This is the ratio that exposes the reinforcing loop, where an audit finding
    mints a step whose new surface produces the next round's findings.
- **Prose-declared soft edges (reporting only).** Detail authors routinely
  annotate a declared dependency as ordering-only or test-only ("no file
  collision", "the two edit different apps", "depends on it for the behavior
  the suite observes"). Those sentences mark where a step graph would separate
  if cut. Surfacing the matching `depends_on` edges alongside the ratios costs
  a grep and points at a seam rather than merely announcing size.
- **Effort:** medium. Ratios and deltas are arithmetic over data already
  parsed; the audit-induced count needs a provenance tag persisted on applied
  findings; the inert-step and soft-edge greps are pattern lists that will need
  tuning. One new reporting block, no new verb.
- **Risks / fallout:** report-shape churn for anything asserting on report text
  or the JSON schema; a `DATA_CONTRACT.md` row for the new fields; the
  inert-step and soft-edge greps are heuristics over free prose and will
  mis-fire until tuned against real bundles.
- **Dependencies:** none hard. **Related:** the settled bare-vs-detail
  convergence bar acts on the pathology this entry makes visible — a "no new
  findings" rule cannot converge while each round grows the artifact, and its
  edit-drift exit observes this entry's audit-induced growth from the finding
  side. The corpus/noise-floor work, which
  is what would later turn these numbers into calibrated thresholds rather than
  single-session anecdote.
- **Scope contract**
  - **Outcome:** every completeness report carries a `plan mass` block —
    step count, detail-bundle size, both deltas against the plan's first audit,
    and the four ratios — in the Markdown report and the JSON.
  - **In scope:** the completeness report renderer and its JSON schema, the
    `split-criteria` Altitude 1 line (which cites the numbers instead of
    `not evaluated`), the provenance tag on applied findings, `DATA_CONTRACT.md`.
  - **Out of scope / Non-goals:** **any threshold, warning, gate, exit-code
    change, or split recommendation derived from these numbers.** Thresholds
    without a corpus distribution would fire on every large-but-correct plan —
    an infrastructure migration legitimately has a keystone with high fan-out.
    Also excluded: auto-splitting, changing `split`/`scope-out` behavior,
    re-scoring plans retroactively, and any model-judged mass metric.
  - **Allowed behavior changes:** the new report block and JSON fields, and the
    Altitude 1 line's content. No verb changes behavior; no exit code moves.
  - **Allowed reorganization:** none.
  - **Verification:** a plan whose steps and bundle are unchanged between two
    audits reports zero deltas; adding a step moves the step delta by one;
    a hand-built fixture with a known dependency graph reproduces the four
    ratios by inspection; the JSON block round-trips.
  - **Stop / defer:** threshold and advisory design becomes its own entry once
    a corpus distribution exists. Grep mis-fires found while tuning become
    separate entries rather than widening this one.
- **Approach:** `direct` — one reporting block over already-parsed data, with a
  hard fence against the gating half. The judgment-heavy part is deliberately
  deferred, which is what keeps this direct rather than plan-worthy.
- **Quality:** `convergence`, `gate-signal` — makes the artifact's own growth
  legible at the moment a stopping decision is made. Today the stopping rule
  can only see findings, so the one state where a plan quietly doubles while
  its findings fall is indistinguishable from a clean convergence.
- **Origin:** 2026-08-06, from a session where a plan went 8 → 10 steps and
  ~40% larger across three audit rounds while its finding count fell 23 → 17.
  Every finding applied was individually valid; the loop had no way to report
  that it was making the plan bigger, and the eventual split was prompted by a
  human asking whether the plan should be that size — a question no surface
  asks.
- **Status:** not started. Metrics are hypotheses from a single session; the
  entry deliberately ships the measurement, not the judgment, so the
  distribution can be gathered before anything fires on it.

**#242 — A `roadmap` revision discards what it resolves: retain the closed feedback and the decision behind a drop**

- **What:** two retention additions to the roadmap artifact schema so a revised
  roadmap can say what changed and why, rather than only what it currently holds.
  Today a revision is lossy in two specific ways, and each loss is structural
  rather than accidental:
  - **Closing feedback deletes it.** `FeedbackState` has exactly three members —
    `open`, `awaiting-review`, `deferred` — and no `closed`. A reviewer closes a
    row by deleting it (`roadmap_cmd.py:_feedback_summary_lines`: "close one by
    deleting the row (git keeps the record)"), so **the artifact can never hold a
    resolved review item.** Every feedback row on disk is unresolved by
    construction.
  - **No removal names its decision.** `DecisionRow.rejected_alternatives` is
    where captured reasoning about roads not taken lives — `(option, reason)`
    pairs — and no field links a dropped row to it. The join does not exist.
- **Why now (measured while authoring `roadmap-view`'s plan, 2026-08-07):** the
  read-surface work hit both of these as a wall. `roadmap-view`'s Non-goals
  refuse a standalone removals section because a removal record preserves only
  `removed_id` plus a rationale, never the row's content — that stays true here
  too (see "Rejected" below); this entry targets the two losses that *are*
  fixable without that graveyard risk. The same authoring pass found that a
  second mode intended to render "the revision arc" could only render a live
  queue and some tombstones, because a closed conversation and its decision are
  not retained anywhere but git.
- **The two changes:**
  1. **`FeedbackState` gains `closed`, and closed rows are retained rather than
     deleted**, ordered **at the end of the `feedback` collection** so the live
     queue reads first and the resolved conversation is below it. *(That is this
     entry's reading of "kept at the end of the document"; a literal
     document-tail section below the prose body would be a larger structural
     change and is not what is scoped here.)* Retention in the same collection,
     not a sibling one: a second collection means two places to look for a
     feedback id and splits the single set `check_feedback_integrity` resolves
     against.
  2. **`RemovalRecord` gains an optional decision reference**, closing the
     removal → `rejected_alternatives` join.
- **Rejected — a content snapshot on `RemovalRecord`. Do not re-open without new
  evidence.** The removed row's rendered content, once considered as a third
  change here, was cut 2026-08-27: it is exactly the "ever-growing graveyard
  that cannot show what was lost" risk `roadmap-view`'s own Non-goals already
  named, this entry's stored size would grow without bound per removal, and
  nothing currently needs a restorable copy — git already has the content, and
  a removal's `rationale` already says why it left. Revisit only if a concrete
  reader need for in-artifact removed-row content surfaces.
- **Closing stays a reviewer-only move.** The model may set no row to `closed`,
  exactly as it may not author a feedback row the predecessor lacks
  (`roadmap.py:_invented_review_rows`) and may not drop a carried removal
  (`check_design_row_continuity`). The immutability rule extends to the new
  field: a carried removal's decision reference is not the model's to edit.
- **Rejected alternative — revision numbering, timestamps, or per-row revision
  attribution. Do not re-open without new evidence.** That is re-implementing git
  inside a markdown file, competing with the tool that already does it properly,
  and timestamps are a determinism hazard besides. The retention above is about
  keeping *what a revision resolved*, never about reconstructing *when* or *in
  which run* it happened.
- **Effort:** medium — schema fields, their gates, the renderers, `ROADMAP_FORMAT.md`,
  and tests; no orchestrator change. The whole of it is additive.
- **Risks / fallout:** the sharp one is **back-compat**: every roadmap on disk has
  feedback with no `closed`, so both fields must
  parse as optional and absent must stay legal indefinitely — a required field
  would break every existing artifact and every fixture. Secondary: three gates whose
  interaction must be re-checked rather than assumed — `check_design_row_continuity`
  (carried-removal immutability now covers more), `check_feedback_integrity` (its
  `design rows ∪ removals` set now spans closed rows too), and
  `check_settled_decisions` (which today refuses the removal of a settled
  decision's anchor outright; that refusal should be re-examined *only* if the
  decision reference makes it tractable, and left alone otherwise).
- **Dependencies:** none. **Independent of `roadmap-view`**, which shipped
  against today's schema and renders richer at the same sites. `roadmap-view`'s
  `--mode review` is named for what the artifact holds today; **this entry
  carries the rename to `--mode history`**, which only becomes an honest name
  once retention ships.
- **Outcome:** a reader of a revised roadmap can see what a closed review
  request asked for and which decision drove a drop — from the artifact,
  without reading git.
- **In scope:** `plan_tool/roadmap_artifacts.py` (the two fields, their parse and
  render, the `closed` member and its ordering), `plan_tool/roadmap_gates.py` (the
  three gates named under Risks), the stage prompts' review-collection rules,
  `ROADMAP_FORMAT.md`, and `tests/`.
- **Out of scope / Non-goals:** a content snapshot on `RemovalRecord` (rejected
  above); revision numbering, timestamps, and per-row revision attribution, per
  the rejected alternative; any diff or compare-two-revisions surface; reading
  git from any roadmap code path; changing how `--from-stage` re-entry works;
  any change to `plan-tool`'s exit-code convention; and any rendering decision,
  which belongs to `roadmap-view` — this entry adds the data, never a view of
  it.
- **Allowed behavior changes:** the two new optional fields and the `closed`
  state; closed feedback persisting where it previously vanished. Nothing else
  user-visible, and no change to what a stage run does.
- **Allowed reorganization:** none. Both are additions to existing
  dataclasses.
- **Verification:** an artifact written before this entry parses unchanged with
  both fields absent — the back-compat case, asserted by **mutation** per
  CLAUDE.md § Tests rather than by reading; a `closed` row is retained, orders
  last within `feedback`, and is excluded from the active-guidance set the
  stage prompts consume; a model-authored revision that sets `closed` or edits
  a carried decision reference is rejected naming the field; and each of the
  three gates above keeps its current behavior on artifacts that use neither
  new field.
- **Approach:** `plan-tool` — two schema changes, three gate interactions to
  re-check, and a back-compat contract is multi-phase with real design surface,
  which is the heuristic's plan side.
- **Quality:** `grounding` — the artifact stops asserting a complete picture while
  silently having discarded the parts a reader most needs to judge it.
- **Origin:** 2026-08-07, found while authoring `roadmap-view`'s plan; user-directed, having
  reviewed the losses and settled the `closed`-state retention. Content-snapshot
  scope cut 2026-08-27 (user-directed).
- **Status:** the WIP plan `docs/implementation-plans/2-roadmap-revision-retention.md`
  (status `planning`, 8 steps) remains bare and paused after bare-audit round
  4 on explicit user direction. The 2026-08-27 Integration receipt preflight has
  completed: stale 2:3 source baselines reject the exact receipt before any
  structural retry, and baseline enrollment refuses to replace admitted
  records. The reusable recovery proposal is deferred; do not rerun the
  unchanged preflight or begin a fresh audit. Re-enter only for a second
  independently justified source-baseline recovery need or an explicit bounded
  one-time Integration 2:3 remedy, starting with a fresh bare plan. #315's delivered
  confirmation proof remains input to a later retention redesign, not a
  solution to it.

**#395 — A selector-era candidate lineage on an enrolled roadmap has no discard route**

- **What:** `--reject-candidate` and `--discard-candidate` release only an active
  *batch* candidate: `roadmap_candidate_review.py:_release_active_candidate`
  refuses a candidate with no batch receipt or root ("terminal review resolution
  requires an active batch candidate"). A selector-era candidate — stored under an
  admission whose `root_version_id` is `None`, on a ledger-less roadmap or left on
  disk from before the ledger existed — has no release route.
  `roadmap_candidate_run.py:candidate_admission_path` is one fixed file per
  enrolled roadmap, and `run_initial_candidate_proposal` refuses any other feedback
  selector ("roadmap admission already binds different feedback"). A selector-era
  lineage whose proposal was `response-rejected`, whose reviewer never answers its
  questions, or that the operator decides not to finish therefore occupies the one
  admission slot for the roadmap's life. While it sits unpromoted on the current
  accepted head it refuses enrolled decision settlement and the ledger-batch
  route, both as `unpromoted-candidate-lineage`.
- **Why now:** the exposure is legacy-only and matters when a ledger-less or
  freshly migrated roadmap holds an unfinished selector-era candidate.
  Ledger-batch candidates release through the routes above.
- **Outcome:** an operator can abandon a stalled, unpromoted selector-era candidate
  lineage on an enrolled roadmap, freeing the one candidate-admission slot, without
  weakening the "one admission per roadmap" invariant that protects a lineage still
  in progress.
- **Out of scope / Non-goals:** any change to `promote_review_seal` or the
  sealed-promotion boundary; discarding a lineage that has already produced a
  sealed, promotable review; the batch reject and discard routes; widening the
  narrower `unpromoted-candidate-lineage` predicate the batch route uses.
- **Approach:** `plan-tool` — needs a design decision (what counts as "stalled"
  versus merely slow, whether discard requires an explicit operator confirmation
  comparable to `--reopen-feedback`'s, or whether to retire the selector-era route
  instead, since it is legacy) before a bounded implementation.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** 2026-09-18, `roadmap-decision-settlement` bare-plan audit round 5,
  finding `enrolled-lineage-block-exit`; narrowed 2026-09-23 when
  `roadmap-versioned-feedback-revision-chain` shipped reject and discard for batch
  candidates.

**#396 — Decision-settlement's receipt read-back proof has no operator-facing entry point**

- **What:** `roadmap_decision_settlement_receipt.py:decision_settlement_receipt_proves_completion`
  (and its enrolled/un-enrolled helpers) — fully built, tested, and used
  internally by the settlement runners' own post-receipt currency
  recheck — has no caller anywhere outside its own module and its tests. The
  analogous escalation-receipt function `current_escalation_receipt`
  (`roadmap_escalation_run.py`) is wired into a production CLI path
  (`--view escalations`); no equivalent `--view` or status command exists for
  decision-settlement receipts, and `roadmap-decision-settlement`'s own plan
  schedules no such step (step 7 is documentation-only).
- **Why now:** found 2026-09-18 during `roadmap-decision-settlement`'s
  post-run `/code-review` loop (round 3). Likely intentional — the plan's own
  design treats receipt visibility as living in git history rather than a
  dedicated view — but nothing records that as a deliberate choice, so the
  gap was previously undocumented.
- **Outcome:** an operator can ask, for a given roadmap, whether a named
  decision-settlement receipt still proves its settlement completed, without
  reading git history or writing a throwaway script against the internal
  function.
- **Out of scope / Non-goals:** any change to the read-back proof rule
  itself; a general-purpose evidence-browsing UI beyond this one predicate.
- **Approach:** `plan-tool` — likely a `--view decision-settlements` (or
  similar) addition to `cli/roadmap_cmd.py`, mirroring `--view escalations`'
  existing shape; small enough to scope directly once picked up.
- **Origin:** 2026-09-18, `roadmap-decision-settlement` post-run `/code-review`
  round 3.

**#397 — Decision-settlement's CLI dispatch opens two non-atomic writer-guard leases on an enrolled roadmap**

- **What:** `cli/roadmap_cmd.py:_cmd_roadmap_decision_settlement` always tries
  `run_unenrolled_decision_settlement` first, which opens a full
  `roadmap_writer_guard` lease before it can even determine the roadmap is
  enrolled, then falls back to `run_enrolled_decision_settlement` on its
  `enrolled-roadmap-rejected` refusal, opening a second, independent lease.
  The already-existing, read-only `is_roadmap_enrolled` predicate
  (`roadmap_versions.py`) could pick the correct runner up front from a
  single dispatch point, avoiding both the redundant lock acquisition and
  the (narrow, self-revalidated by each runner's own lock-protected
  preflight) window between the two leases. Confirmed the fallback signal
  (`ENROLLED_ROADMAP_FALLBACK_REFUSAL`) is also not exclusively an
  enrollment signal: `require_unenrolled_roadmap_writer`
  (`roadmap_revision_publish.py:328-342`) catches `RoadmapVersionError`
  from a corrupt accepted-head store and re-raises it as the identical
  `EnrolledRoadmapWriteError` genuine enrollment produces, so a corrupted
  (never-enrolled) roadmap also triggers the fallback — wastefully, since
  the enrolled runner then hits the same corruption and reports it, so no
  distinct outcome is actually lost. The CLI dispatcher's own docstring has
  been corrected to state this rather than claim the fallback fires "only"
  on genuine enrollment.
- **Why now:** raised independently by all six `/code-review` rounds on
  `roadmap-decision-settlement`, always as an efficiency/robustness
  observation, never as a demonstrated live bug — each runner's own
  lock-protected preflight already refuses correctly if the roadmap's
  enrollment state changes between the CLI's dispatch and the lock
  acquisition, so today's behavior is safe. Filing so further review
  rounds on the same repo don't re-raise it as review noise; not urgent
  enough to fix under review-round time pressure against a working,
  tested dispatch.
- **Outcome:** the CLI dispatches to the correct settlement runner from one
  `is_roadmap_enrolled` check, opening exactly one writer-guard lease per
  settlement attempt.
- **Out of scope / Non-goals:** removing either runner's own independent
  enrollment check — that stays as defense in depth even after the CLI
  dispatches directly.
- **Approach:** direct — the fix itself is a small, well-scoped CLI change,
  but it also requires rewriting the two existing tests
  (`test_decision_settlement_falls_back_to_the_enrolled_runner_on_enrolled_roadmap_rejected`,
  `test_decision_settlement_never_falls_back_on_any_other_refusal`) whose
  whole premise is the current probe-and-fallback shape.
- **Origin:** 2026-09-18, `roadmap-decision-settlement` post-run
  `/code-review` rounds 1-4, 6, and 9 (recurring).

**#403 — Spike: define a read-only `plan-tool doctor` readiness contract**

- **What:** investigate and design a small, reliable `plan-tool doctor` command
  that tells an operator whether the local installation and current repository
  are ready for ordinary plan-tool work. The spike inventories current checks,
  their owners, their cost, their failure modes, and their actionable repair
  routes before selecting the command's first released check set and output
  schema. It then produces a reviewed recommendation or a tightly scoped seed
  for implementation; it does not ship a speculative kitchen-sink command.
- **Why:** `docs/GATES.md` already names `plan-tool doctor` as a deferred
  pre-everything gate, but the CLI has no doctor subcommand. Operators must
  separately discover whether the installed package contains the required
  bundled skill/directives, whether a configured skill installation still
  resolves to that package, and whether `.gitignore` excludes plan-tool state
  that must be shared or fails to exclude known local runtime state. Some
  narrow primitives already exist, including
  `cli.gitcommit.ignored_recommended_paths` for durable `.plan-tool` files and
  `cli.skill_cmd`'s packaged-source/destination classification, but there is no
  coherent read-only readiness report or ownership boundary for assembling
  them.
- **Spike questions:**
  - Which existing checks can be reused unchanged, and which would need a new
    read-only primitive rather than importing a mutating command handler?
  - Which conditions are universal prerequisites, and which are relevant only
    when an operator uses a particular feature such as installed skills,
    roadmap, a backend, Jira, or a commit-capable workflow?
  - How should doctor distinguish `pass`, `advisory`, `not-applicable`, and
    `cannot-determine` so a missing optional integration never reads as an
    installation failure?
  - Which Git-ignore rules concern plan-tool-owned paths that are known to be
    shared or local, without expanding into the general `.gitignore` audit
    already tracked by #318?
  - How should the command verify a skill install: bundled sources exist,
    symlinks resolve to the installed package, copied bytes still match, and
    the router's shared directives are present, while respecting project and
    user skill roots?
  - What JSON and terminal contracts let a human, an installed skill, and a
    CI wrapper consume the same report without making doctor a policy gate?
  - Does the stale `docs/GATES.md` reference describe the selected command, or
    should the documentation instead point to a narrower existing surface?
- **Candidate check inventory for evaluation:** packaged version and required
  resource availability; repository/worktree discovery; known durable
  `.plan-tool` paths accidentally ignored; known local plan-tool runtime paths
  accidentally unignored; skill-router and shared-directives installation
  state; supported configured backend executable availability without a model
  call; selected roadmap lifecycle files that are unreadable or malformed;
  and the presence of a usable Git executable. The spike must justify every
  selected check from an existing command or documented operator outcome; it
  may recommend deferring any candidate that lacks a clear owner or remedy.
- **Scope contract:**
  - **In scope:** current-code and documentation inventory; check ownership
    map; selected initial check set; status vocabulary; terminal and JSON
    report proposal; remediation text; false-positive and platform analysis;
    direct reuse candidates; and a narrow implementation seed or a recorded
    decision not to proceed.
  - **Out of scope / Non-goals:** changing `.gitignore` rules across arbitrary
    repositories; modifying skill installations; authenticating or invoking a
    model provider; changing project state, Git state, roadmap artifacts,
    baselines, seeds, receipts, or run logs; a general security scanner;
    broad environment inventory; and implementing doctor before the check set
    is selected.
  - **Allowed behavior changes:** none during the spike. A follow-up may add
    one read-only command only after its inputs, statuses, and remedies are
    explicitly selected.
  - **Verification:** reproduce the candidate checks in fixtures covering a
    healthy repository, ignored durable state, visible local runtime state,
    missing packaged integrations, valid and dangling skill symlinks, stale
    copied skill content, an unavailable optional backend, a non-Git directory,
    and platform path differences. Verify that every proposed doctor check is
    read-only and that every non-pass result names a specific, safe next step
    or reports `cannot-determine`.
  - **Stop / defer:** if the inventory cannot identify a small shared set of
    checks with stable remedies, document the existing command-specific checks
    and do not introduce a top-level doctor command. Any generic ignore-file
    linter remains #318.
- **Existing logic to evaluate for reuse:**
  `plan_tool.cli.gitcommit.path_is_gitignored` and
  `ignored_recommended_paths`; `plan_tool.cli.skill_cmd`'s bundled-source and
  destination classification; repository-root resolution in
  `plan_tool.cli.context`; backend/package discovery in `plan_tool.backend`;
  command registration in `plan_tool.cli.parser` and `plan_tool.cli.app`; and
  the existing read-only `status`, `validate`, `convergence`, and roadmap-view
  output conventions. The resulting doctor reader must not call mutating
  helpers merely because they contain nearby inspection code.
- **Risks / fallout:** an over-broad doctor can become a misleading release
  gate, report machine-local optional tooling as failure, or duplicate checks
  that should remain feature-specific. A check without a clear remedy creates
  noise rather than readiness. The spike must keep the command advisory and
  separate health facts from policy decisions.
- **Dependencies:** related to #318's broad ignore-rule audit but does not
  depend on it. The installed-skill entries #377–#379 are input to the skill
  inventory; this spike does not reopen their shipped routing behavior.
- **Approach:** `plan-tool` — the work spans CLI architecture, packaged
  resources, Git semantics, skill installation, documentation, and a new
  output contract. Start with a seed grounded in the inventory rather than a
  direct implementation.
- **Origin:** 2026-09-21, a Integration roadmap run left a persistent local writer
  lock that needed a precise `.gitignore` rule, alongside questions about the
  active plan-tool installation and installed skill readiness.
- **Status:** not started; spike only.

**#404 — Decide the completeness audit's intent-fidelity boundary**

- **What:** settle whether and how the bare-plan completeness audit judges a
  generated plan against its declared intent and originating seed. Replace the
  current blanket instruction — “do not raise a finding that work disagrees
  with the stated intent” — only if the replacement can distinguish a real
  delivery contradiction from the permanently refused class of open-ended
  prose-agreement checks.
- **Why:** the audit currently receives plan and step intents as authoritative
  scope input and receives the archived seed's Outcome and scope contract, but
  `plan_tool.review._format_intent_block` explicitly forbids comparing intent
  with the Overview, detail, or code and says not to report work that disagrees
  with intent. That protects the settled presence-only contract from subjective
  prose-conformance findings, yet it also suppresses the audit's existing
  correctness question: whether the plan's architecture and steps can achieve
  its stated goal. A plan may therefore be internally detailed and audit-clean
  while silently dropping the request that caused `create` to produce it.
- **Decision required:** define separate treatment for all three relations:
  1. **intent wording/quality** — whether this remains permanently unjudged;
  2. **plan delivery against its own intent** — whether an architecture, step
     graph, or acceptance set that cannot deliver or materially contradicts
     that intent is a `plan-correctness` finding; and
  3. **generated plan against originating seed** — which seed commitments are
     authoritative at the first bare audit, and what explicit provenance lets
     a later plan legitimately supersede them.
- **Required change directives:** any selected design and its later
  implementation instructions must require all four:
  - stay **true and proportional to the intent** — detect a delivery
    contradiction without widening the requested capability;
  - require the **smallest proof that completes the intent**, not proof of an
    eventual or generalized capability;
  - stay true to the active audit altitude — bare-plan checks name properties
    and routes, while detail-grounded checks may judge selected mechanisms; and
  - perform both an **identifier sweep and a vocabulary sweep**, then judge
    every matched site against the goal and the shape of the defect rather than
    replaying the same edit mechanically at every textual match.
- **Existing contracts to reconcile:**
  - `plan_tool.review._format_intent_block` and
    `tests.test_review.TestAuditPromptIntentBlock` deliberately forbid an
    agreement check.
  - `plan_tool/prompts/plan-audit.md` already defines an unsound design as one
    that cannot achieve the plan's own goal and permits the stated intent as a
    property anchor.
  - `create` deterministically maps a seed's `## Outcome` to `Plan.intent`;
    `AuditInputSnapshot` captures the live or archived seed and fingerprints
    its bytes; `_format_scope_contract_block` renders its canonical scope fields
    as informational input while declaring that the plan wins on conflict.
  - `CLAUDE.md` § “Validating a semantic property you cannot observe” records
    the user-settled presence-only rule and permanently refuses semantic
    agreement checking, while § “Audit the why, not the what” requires checking
    whether a mechanism actually delivers its goal.
- **Scope contract:**
  - **In scope:** an architect decision on the audit boundary; bare-stage versus
    detail-stage applicability; authoritative inputs and precedence; finding
    axis/severity; explicit-plan-evolution provenance; prompt wording; focused
    fixtures that distinguish delivery contradictions from harmless wording
    differences; and the smallest ready implementation item(s) after the
    decision lands.
  - **Out of scope / Non-goals:** grading prose quality, similarity scoring,
    requiring duplicate wording across artifacts, comparing code to an
    author's stylistic phrasing, weakening the plan toward an under-delivered
    implementation, or changing `create`'s deterministic Outcome-to-intent
    mapping without separate evidence.
  - **Allowed behavior changes during decision work:** none. Do not change the
    audit prompt, finding policy, blocking behavior, or `CLAUDE.md` rule until
    the architect decision is reviewed and recorded.
  - **Verification for the selected design:** distinguish at least (a) a plan
    that faithfully delivers differently worded seed intent, (b) a plan whose
    steps omit a material seed outcome, (c) a plan whose architecture
    contradicts its own intent, and (d) a plan that explicitly and legitimately
    supersedes its seed. The chosen observable must not reintroduce the high-
    noise prose-conformance shape the existing rule was written to prevent.
  - **Stop / defer:** if no bounded observable separates delivery from semantic
    prose agreement, retain the existing presence-only rule and document that
    the seed-to-plan review remains a human pre-audit gate.
- **Dependencies:** independent of the shipped roadmap concept comparison. The
  decision must read the shipped `intent-scope-fence` and `intent-required`
  records rather than treating the current sentence as accidental wording.
- **Approach:** `plan-tool`, `architect` tier — this changes what an audit gate
  means and reopens a recorded project rule. After the decision lands, create
  separately scoped ready items; the mechanical prompt/test edit may then be a
  direct implementation if no broader audit machinery changes.
- **Origin:** 2026-09-21, manual review of the bare roadmap-concept-comparison
  plan against its seed exposed that the audit sees both artifacts but is told
  not to judge whether the generated plan preserves or delivers their intent.
- **Status:** not started; architect decision required before implementation.

**#307 — Consolidate the duplicated "is this source current for its evidence
version" predicate `roadmap-canonical-source-identity` left scattered
(landed 2026-08-23; two genuine sites merged, four investigated and kept
separate)**

- **What:** `roadmap-canonical-source-identity`'s post-ship `/code-review`
  hotfix loop (seven rounds, 2026-08-21/23) repeatedly found the same
  underlying pattern at different sites: independent, hand-written
  reimplementations of "does this receipt/analysis still match its admitted
  baseline identity for its schema version." Three of the seven rounds'
  confirmed correctness regressions were direct consequences of this
  duplication: round 3's `_preflight_is_canonical` applied the wrong
  (version-1) rule to a version-2 snapshot; round 5's admission/consumption
  mismatch existed because two independently-coded predicates disagreed
  about "an admitted v2 source"; round 7 found the same dispatch logic had
  also dropped fail-closed behavior for an unsupported version at one site.
- **Landed:** `admitted_source_is_current(*, schema_version, recorded_digest,
  recorded_identity, current_digest, current_identity)` in
  `plan_tool/roadmap_source_identity.py` (commit `cbdd9a9e`), with a direct
  characterization test (`test_admitted_source_is_current_dispatches_by_
  schema_version`), replacing the identical hand-rolled dispatch at exactly
  two sites that shared its precise shape (compare a **recorded** digest/
  identity against a **freshly admitted** one, dispatched by version):
  - `plan_tool/roadmap_escalation_run.py`'s `current_escalation_receipt`
    freshness classification.
  - `plan_tool/roadmap_impact_analysis.py`'s `_receipt_matches_captured_artifact`
    (kept its pre-existing `canonical_source_identity is None` guard, which
    the shared function's contract doesn't need to know about — an
    `EscalationReceipt`'s own model validator already makes that state
    unreachable for a well-formed v2 receipt, but the call site's defensive
    check was cheap to preserve as-is).
  Full suite green throughout (`uv run pytest tests/ -q -n auto`), no
  behavior change — verified by running the existing test suite at each
  site immediately after its conversion, before moving to the next.
- **Do NOT merge (investigated and kept separate, each for a different
  mechanical reason — not the same predicate wearing different clothes):**
  - **`admit_versioned_artifact_source`** (`roadmap_escalation_selection.py`)
    — this is the **admission** step (derive an identity from a freshly
    parsed artifact), not a comparison against a previously recorded one.
    Different phase of the pipeline; nothing to compare yet.
  - **`snapshot_artifacts_match_captured_text`**
    (`roadmap_impact_snapshot.py`) — checks **self-consistency of one
    persisted snapshot** (do its own recorded `artifact_texts`/`artifacts`
    fields, when re-derived, match its own recorded `canonical_source_
    identities`), not "recorded value A vs. currently observed value B."
    The v2 branch's `canonical_source_identity(baseline_record(...)) !=
    identity` check is superficially close to the shared predicate's shape,
    but forcing it through `admitted_source_is_current` would mean passing
    unused v1 parameters into a call already known to be v2 — obscuring a
    plain `!=` behind a version-dispatching function that dispatches
    nothing, at a real readability cost for near-zero duplication removed.
  - **`_preflight_is_canonical`** (`roadmap_structural_revision_run.py`) —
    its v2 branch compares **parsed-artifact and text equality**
    (`snapshot.artifacts[selected_index] == preflight.selected_artifact`),
    not digest/identity equality, then delegates the rest to
    `snapshot_artifacts_match_captured_text` (already consolidated,
    see above). No genuine duplicate of the shared predicate's shape here.
  - **`current_impact_analysis`'s v1 branch** (`roadmap_impact_run.py`) —
    compares full canonical-JSON byte rendering
    (`render_impact_analysis(candidate) != data`), not a digest/identity
    field. Already shares its v2 logic via `version2_analysis_matches`
    (consolidated before this entry existed); its v1 branch's shape doesn't
    match the digest-vs-identity predicate either.
- **Why this matters for anyone re-opening this entry:** a duplicate-looking
  `!=`/`==` at a version-dispatch site is not sufficient evidence to route
  it through `admitted_source_is_current` — check whether the two sides
  being compared are actually "a recorded value" and "a freshly admitted
  value" for the same evidence record, the way the two landed sites are.
  Self-consistency checks, admission derivation, and full-byte-render
  comparison are a different shape even when they also branch on
  `schema_version`.
- **Already consolidated before this entry existed** (do not re-flag):
  `version2_analysis_matches`, `is_supported_evidence_schema_version`,
  `canonical_source_identity_for_stage`, `_canonical_source_identity_fields`,
  `admit_baseline_backed_source`/`_pending_generation_touches_baseline`.
- **Origin:** 2026-08-22, found while auditing whether the hotfix loop was
  addressing the concept behind its recurring findings or only their
  individual sites. Closed 2026-08-23 after the genuine duplication was
  extracted and the rest was verified, not assumed, to be a different shape.

**#296 — Bound (or at least backstop) `render_detail_prompt`'s uncapped `prior_body_block`**

- **What:** every content-bearing block `render_detail_prompt` assembles
  (`plan_tool/detail.py`) carries an individual `max_file_bytes` cap except
  `prior_body_block` (rendered by `_format_prior_body_block`, fed from
  `merge`'s folded step bodies) — deliberately uncapped per the function's
  own docstring, to preserve "the distinct, faithful combine seam." Its byte
  count is already visible in the pre-send budget advisory's breakdown
  (`collect_blocks.extend([("prior-body", ...)])`, `detail.py:814`), so this
  is **not** a visibility gap — the advisory already names it. The actual
  gap is narrower: when a `merge` combines steps whose total detail-body
  bytes are large, there is no per-block or aggregate ceiling at all, and no
  remedy path specific to this block beyond the same generic warn-only
  advisory every prompt gets, which never blocks the send.
- **Effort:** small — this doesn't need #97's excerpt-strategy machinery;
  truncating any individual folded body would break the faithful-combine
  guarantee `prior_body_block` exists to provide, so the fix is about the
  merge count/selection path or the failure remedy, not content truncation.
- **Risks:** the "right" fix might be "there isn't one, by design" — a
  `merge` of many/large-bodied steps has no better answer than "split the
  merge" or a clearer failure message, since truncating would corrupt
  combine fidelity. Don't let this drift into re-litigating #97's truncation
  strategy for a block that explicitly must not be truncated.
- **Dependencies:** none; distinct from #97, which scopes the five
  *declared-file* embed surfaces, not step-body embeds — related class, not
  the same site.
- **Outcome:** a `merge` whose folded step bodies would push the detail
  prompt into `prompt_budget`'s `high` level surfaces guidance specific to
  *this* block (e.g. "these N steps' combined detail bodies are `X` bytes;
  merge fewer at once") rather than the generic per-surface remedy text.
- **In scope:** `plan_tool/detail.py` (`render_detail_prompt`,
  `_format_prior_body_block`, the merge call site that assembles
  `prior_body`).
- **Out of scope / Non-goals:** truncating or excerpting
  `prior_body_block`'s content (breaks the faithful-combine contract);
  folding this into #97's scope or its per-step embed budget (different
  content class — step bodies, not declared files).
- **Allowed behavior changes:** a merge that would overflow gets a more
  specific message/guidance naming the prior-body block; no change to
  ordinary (non-overflowing) merge behavior.
- **Allowed reorganization:** none.
- **Verification:** a test constructing a merge with several large synthetic
  step bodies exercises the `high`-level path and asserts the block-specific
  remedy text; existing prompt-budget tests for the generic advisory stay
  green.
- **Stop / defer:** if no real merge in this repo's history has ever
  approached `prompt_budget`'s `warn` level from `prior_body_block` alone,
  this may not be worth a dedicated remedy over the generic advisory — check
  `plan_tool/telemetry.py`'s recorded `prompt_budget` events (if any exist
  for `detail`/merge) before building anything; close as "no observed need"
  if the data doesn't support it.
- **Approach:** `direct` — narrow, single-file scope once the telemetry
  check above either confirms or rules out real-world need.
- **Quality:** `grounding` — same class as #97 (prompt-budget-blind content
  embedding) but a distinct site; rolled up alongside it below rather than
  folded into its scope.
- **Origin:** 2026-08-19, found reconciling plan-tool's prompt-construction
  paths against general LLM context-window-limitation patterns —
  user-directed. Corrects an earlier framing of this gap that assumed the
  budget breakdown didn't name this block; it does (`detail.py:814`) — the
  remaining gap is narrower than first stated.
- **Status:** not started.

**#377 — Teach installed plan-tool skills to author and validate plan seeds**

- **What:** give an assistant driving `plan-tool` from chat an explicit route
  from a requested outcome or selected backlog item to a reviewable seed file,
  before it invokes `create --from-existing`. The installed guidance must make
  `SEED_FORMAT.md`'s scope contract and canonical heading rules available at
  the point of authoring, require a source and live-code claim check, and tell
  the assistant to validate the finished seed against those rules before the
  first `create` call. Keep the seed as a committed, reusable input and carry
  backlog reconciliation forward when the seed comes from a backlog entry.
- **Why:** the current skill routers route an existing plan or document into
  the CLI. `create --from-existing` consumes a seed; it does not author one.
  Chat orchestration frequently owns that preceding step, while the installed
  skill only points to `SEED_FORMAT.md` in the source repository. That pointer
  is not a usable authoring contract in a consuming repository with only the
  installed skill.
- **Dependencies:** none — the thin routers and installer-carried shared
  reference (formerly #370) shipped 2026-09-16. This item adds seed-authoring
  content and any necessary format access without expanding that plan's
  router and installer relocation work.
- **Outcome:** a Claude Code, Codex, or Cursor session using the installed skill
  can author and check a seed from a user request or backlog entry, then hand
  that seed to `create --from-existing` with its intent and scope intact.
- **In scope:** the shared installed guidance, a working installed path to the
  authoritative seed format or a bounded authoring contract derived from it,
  router entry points where needed, installation coverage for that path, and
  focused documentation and tests.
- **Out of scope / Non-goals:** changing `create` ingestion or seed semantics;
  making the CLI generate seeds; expanding the shipped router architecture
  (formerly #370) or the shipped skill trigger fields (formerly #371);
  requiring a fully canonical body when the documented preparation route is
  appropriate; recording discoveries outside a plan's fence (#378) or
  updating entries found already addressed (#379).
- **Allowed behavior changes:** the installed skills guide the orchestrating
  assistant through seed authoring and validation before `create`. No CLI
  command or artifact behavior changes.
- **Allowed reorganization:** only the guidance and packaging needed to give
  every installed backend the same seed-authoring contract.
- **Verification:** install each backend's skill from a source checkout and a
  wheel, including `--copy`; from the installed location, follow its seed
  authoring and format links without relying on the source checkout. Check
  example seeds from both a user request and a backlog item for `Outcome`,
  scope fence, usable `References`, testing and acceptance evidence, and
  documented direct-versus-preparation routing.
- **Stop / defer:** separate any proposed automatic seed generator, new seed
  lint command, or change to file-backed ingestion into its own backlog item.
- **Route:** `plan`.
- **Readiness:** `ready`.
- **Tier:** `architect` — it changes the guidance available to every driving
  assistant before plan creation.
- **Origin:** 2026-09-16, user clarification that chat orchestration often
  creates the seed and the router/reference plan (formerly #370) should stay
  focused on the router.
- **Status:** not started.

**#378 — Installed skills route discoveries outside a plan's intent, proportionality, or scope into the host repo's tracker**

- **What:** give the installed shared reference one rule for a discovery the
  driving session will not act on because it falls outside the plan's stated
  intent, the proportionality bound, or the scope contract. The rule picks the
  sink by the host repo's convention, checks for an existing record, writes a
  minimum-content entry, commits it on its own, and reports it. Every directive
  site that says "defer", "present separately", or "file it" without saying how
  cites that rule instead of restating it.
- **Why:** the practice works where its rules are loaded, and the installed
  skills carry almost none of them to any other repo. Verified 2026-09-16:
  - **Installed guidance.** `integrations/codex/SKILL.md` never mentions a
    backlog; `integrations/claude/SKILL.md` mentions one once, in exit (c);
    `integrations/cursor/SKILL.md` (shipped 2026-09-16, formerly tracked as
    #370) never mentions one either. `integrations/shared/DIRECTIVES.md` states
    the rule in one sentence (§ "Authoring hygiene": "Route out-of-scope
    findings to the backlog files") and defers or files without it in nine
    sections:
    - § "Gate 1 — the bare-plan audit": "defer the concern rather than
      enlarging the arc" names no destination.
    - § "Before applying anything": "Keep non-plan output separate" and "Keep
      decisions human-owned" present out-of-scope suggestions and never record
      them.
    - § "Fix the class, not the cited spot", check 0: "state per site why it
      stays" leaves an out-of-scope sibling unrecorded.
    - § "Trajectory, stopping, and the three exits": `[out-of-scope-deferred]`
      findings are only excluded from the streak; exit 3 names
      `BACKLOG.md` / `BUG_BACKLOG.md` with no entry shape.
    - § "After `run` finishes a plan": review keeps documentation accuracy and
      speculative refactors "separate" from the verdict, with no destination.
    - § "Post-run reconcile-tail stop rule": "record the evidence required to
      unblock it, and defer it" names no destination.
    - § "Direct changes get the same loop": the broader fix the
      smallest-change rule declines is not recorded.
    - § "When a chat concludes a plan is mis-decomposed", step 3: "Record the
      case in `BACKLOG.md`" means `plan-tool`'s tracker, and in a consuming
      repo it points at the host's.
    - § "Escape hatch": "the repo's backlog / issue tracker", with no rule for
      choosing either.
  - **Rules that do not install.** The capture discipline lives only in this
    repo: `docs/TRACKING.md` (the file-selection rule, the entry format,
    § "Stop / defer during create, detail, completeness, and implementation"
    including 3a, and "a finding that only lives in chat or `.tmp/` hasn't
    been filed"); `CLAUDE.md` § "Authoring hygiene and anti-creep" (file a
    consolidation opportunity; migrate a findings stub); and
    `backlog-arc-integration-mvp.md` (a `plan-tool` defect found while driving
    another project goes to the file that owns its subsystem, when observed).
  - **Measured.** All 9 distinct `[out-of-scope-deferred]` findings in this
    repo's saved reports (6 plans, 2026-08-03 to 2026-08-27) reached an entry,
    a seed, or an existing record — for example the `depends_on_notes`
    consumers became #257–#259 (`a1fa6c6e`) and the `seed-state.json` locking
    gap became #267 (`4b72f7f4`) — and `2b0273cc` filed three pre-existing
    defects found during validation. This is evidence that the rules work when
    loaded, **not** evidence of dropped findings; do not cite it as a failure
    rate.
  - **Consuming repo.** Integration, the one real consumer, has no `BACKLOG.md` or
    `BUG_BACKLOG.md`. Its only backlog-named file,
    `aidlc/spaces/default/intents/260909-integration-mvp/ideation/scope-definition/intent-backlog.md`,
    is an ideation artifact of prioritized proto-units. A literal "file it in
    the repo's backlog" has no correct target there, and one wrong one.
  - **Signals the tool already emits.** `plan_tool/prompts/plan-audit.md` has
    each `[out-of-scope-deferred]` finding state where it should be filed. The
    scope guard prints `plan-tool: wrote N out-of-scope finding(s) (<kind>
    scope) to <path>` and writes a stub whose `kept-by-impact` section records
    a scope expansion that already landed — a review item, not a deferral.
    #380 owns the tool side.
- **Proposed defaults (2026-09-16; confirm or revise before `create`):**
  1. **Triggers.** An `[out-of-scope-deferred]` finding; a finding declined
     under the proportionality rule; an out-of-scope sibling from check 0; a
     review or reconcile-tail remainder kept out of the verdict or deferred on
     an unavailable capability; a broader fix declined by the smallest-change
     rule; a scope-guard stub's reverted records; a defect noticed in passing,
     duplication included; a `plan-tool` defect found while driving another
     repo; an exit-3 item. **Not a trigger:** an in-scope advisory tail, which
     its saved report already retains.
  2. **Sink, in order.** The host repo's stated convention (its instruction
     file, or a contributing or tracking doc); an existing forward-work and
     defect tracker pair such as `BACKLOG.md` / `BUG_BACKLOG.md`, choosing by
     "would a user filing this as an issue be right?"; the plan's own
     `## Deferred` for later scope or an open decision that belongs to that
     plan; otherwise ask the user once. Unanswered in a headless run, the item
     is listed in the final report under an explicit *Not filed — no tracker
     identified* heading. Never create a tracker, or file into a
     similarly named artifact with another purpose, without the user. A
     `plan-tool` defect goes to `plan-tool`'s tracker, not the host's; with no
     writable `plan-tool` checkout, surface it with the evidence needed to
     file it.
  3. **Existing record first.** Search by identifier and by vocabulary (check
     0's two searches) and extend a matching entry with the new provenance
     rather than duplicating it.
  4. **Minimum content.** What was found; provenance (plan slug, command or
     phase, report path and finding anchor, or commit); the fence that
     excluded it, quoted — intent, proportionality, an explicit Non-goal, or a
     later stage; evidence status (verified at HEAD with an anchor, or marked
     unverified); and the host repo's entry format when it has one. No design
     beyond what the evidence supports.
  5. **When and how.** Recorded once classified and before the next
     `plan-tool` invocation's pre-call commit, as its own tracker-only commit
     and never inside a plan-correction batch. A chat message, handoff note,
     or scratch file is not a record.
  6. **Authority.** Recording belongs to the session and is reported by
     location in the user-facing response. Deferring a material,
     in-scope-looking finding that no explicit fence excludes, or accepting a
     `kept-by-impact` expansion, is a scope decision that the existing
     override rule surfaces first.
- **Effort:** medium — one new reference section, citation edits in the nine
  sections above plus the router pointers, and three hand-walk fixtures. No
  code.
- **Risks:** filing noise if the trigger list reads as "record every finding"
  — default 1's advisory-tail exclusion is load-bearing; drift if sites
  paraphrase the rule instead of citing it; misrouting in a repo with an
  unusual convention, which default 2's ask-once fallback contains. (Touching
  the Claude router's lines twice was a risk only while the router/reference
  split, formerly #370, hadn't landed; it shipped 2026-09-16, so the routers
  are already thin.)
- **Dependencies:** none — the shared reference is the installed
  `DIRECTIVES.md` file, shipped 2026-09-16 as the skill-router-and-shared-reference
  plan (formerly tracked as #370); that plan's own Non-goals excluded
  directive content changes beyond relocating roadmap guidance. This item
  edits the same files as #377 (and, before it shipped 2026-09-17, #371);
  sequence after #377 if it is also taken.
- **Outcome:** a session driving `plan-tool` through an installed skill
  reaches, from every site that defers, one rule that turns an out-of-scope
  discovery into a record in the host repo's own tracker or an explicit,
  reported "not filed".
- **In scope:** `integrations/shared/DIRECTIVES.md` (the new section and a
  citation in each section above); the router pointers as the shipped
  router/reference plan (formerly #370) leaves them; install and format tests
  only where the edits require it.
- **Out of scope / Non-goals:** updating an existing entry found already
  addressed (#379); the scope guard's stub output (#380); seed-time
  source-entry reconciliation (#377 and the existing "Backlog-derived seeds"
  rule); a CLI that harvests or promotes deferrals
  (`docs/implementation-plans/2-deferred-scan-digest.md`,
  `docs/implementation-plans/2-deferred-select-promote.md`); changing
  `docs/TRACKING.md`'s entry format. Deliberately not done, each with its
  reason:
  - a `.plan-tool/project.json` tracker-location key — a tool change with no
    evidence that the ask-once fallback falls short; file it if sessions keep
    asking;
  - an external issue tracker as a default sink — publishing is outward-facing
    and needs the user each time;
  - recording in-scope advisory tails — the saved report retains them;
  - qualifying the reference's own `BACKLOG #N` provenance citations as
    `plan-tool`'s — noticed, and not needed for this Outcome;
  - any lint, gate, or exit code keyed on unrecorded discoveries or entry
    fields — a semantic property (`CLAUDE.md` § "Validating a semantic
    property you cannot observe").
- **Allowed behavior changes:** guidance text only; no command, prompt,
  artifact, or exit behavior changes.
- **Allowed reorganization:** moving § "Authoring hygiene"'s one-sentence
  routing rule into the new section, because leaving it there would restate
  the rule. Nothing else.
- **Verification:**
  - Every section listed above cites the new section, and each router points
    to it (binary).
  - A `--copy` install into a scratch repo resolves the section without a
    source checkout (extends the install test from the shipped
    router/reference plan, formerly #370).
  - A hand walk of the rule reaches a sink or an explicit "not filed" for
    (a) a scratch repo with `BACKLOG.md` / `BUG_BACKLOG.md`, (b) a Integration-shaped
    repo with no tracker and a backlog-named ideation file, and (c) one real
    saved `[out-of-scope-deferred]` finding plus a synthetic scope-guard stub.
  - Deliberately not checked: whether a session records anything, entry
    quality, or the fence judgment.
- **Stop / defer:** if sink selection cannot be stated without a tool-side
  key, ship the ask-once and "not filed" fallback and file the key as its own
  entry.
- **Route:** `plan` — nine citation sites and an authority line whose paper
  trail matters; the bare-plan gate catches a missed site or a mis-drawn
  authority boundary before detail multiplies it.
- **Readiness:** `ready` — the router/reference split it depended on (formerly
  #370) shipped 2026-09-16.
- **Tier:** `architect` — it changes the canonical directives every driving
  assistant follows.
- **Iterate:** standard recipe. The seed is not yet authored.

  ```bash
  plan-tool create skill-backlog-capture --iterate -y --from-existing plan-seeds/skill-backlog-capture.md
  plan-tool completeness-audit skill-backlog-capture --iterate --commit -y
  plan-tool detail skill-backlog-capture --commit -y
  plan-tool completeness-audit skill-backlog-capture --iterate --commit -y
  plan-tool run skill-backlog-capture --commit -y --step N
  plan-tool reconcile-code skill-backlog-capture --all
  ```
- **Origin:** 2026-09-16, a user-directed review of the installed skills and
  this backlog for orchestration-layer duties when work surfaces outside a
  plan's intent, proportionality, or scope.
- **Status:** not started.

**#379 — Installed skills update a backlog entry the session finds already addressed**

- **What:** when a driving session observes that an existing tracker entry —
  other than the plan's own source entry — is already satisfied, partly
  satisfied, superseded, or based on a false premise at HEAD or after the
  session's own work, it verifies that against the entry's own terms and
  updates the entry so it stops reading as open work. The entry is closed by
  the host repo's closure convention, narrowed to its remainder, or annotated
  with dated evidence and surfaced. The current plan never absorbs the
  remainder.
- **Why:**
  - **No installed rule covers it.** The shared reference's backlog rules
    reach only the source entry (§ "Authoring hygiene": backlog-derived seeds
    carry reconciliation forward) and the sweep after a structural change to
    the plan (§ "Documentation is forward-looking"). `docs/TRACKING.md`
    § "The life of an item", step 5, closes only the entry being worked. The
    routers say nothing.
  - **Sessions encounter it in normal driving work:** grounding a seed or remedy claim at
    HEAD, `reconcile-plan` reporting steps that look already done, #378's
    existing-record search, full-suite validation, and code review.
    `2b0273cc` (2026-09-16) shows the right shape in miniature: a pre-existing
    defect "deliberately not filed", because it was "already fixed by
    a4316f87's regeneration".
  - **Closure has failed in two measured ways here.**
    - *Over-deletion:* `5042c3ba` (2026-09-02) restored #337 after a closure
      removed it under the general "remove when shipped" convention. The
      plan's own step detail required a dated completion record, and two arc
      docs cited the id.
    - *Dangling citation:* the 2026-08-27 `roadmap-feedback-evidence-reopen`
      audit (`shipped-entry-reference-sweep`) found a step that deleted #315
      and verified the deletion by grepping only `BACKLOG.md`, which missed a
      present-tense citation of #315 as an open gap in
      `bug-backlog-draining-arc.md`. `71a8ce8a` (2026-08-28) likewise edited
      `backlog-arc-roadmap.md` to close a redundant item.
  - **Resemblance is not closure.** Four of the five "duplicated helper"
    claims in BACKLOG #79 were wrong (`CLAUDE.md` § "Authoring hygiene and
    anti-creep"). An entry that looks shipped is a claim to check against its
    own Verification.
- **Proposed defaults (2026-09-16; confirm or revise before implementation):**
  1. **Incidental only.** The rule covers entries the session's own work
     touched or its searches returned, never a proactive staleness sweep.
  2. **Verify first.** Check against the entry's Outcome and Verification (a
     bug's Symptom) at HEAD, citing the satisfying commit or anchor. If
     checking needs a new run, measurement, or model call, annotate rather
     than close.
  3. **Dispositions.**
     - *Addressed:* close by the host convention (removal, a dated completion
       record, or a historical decision record). A more specific rule in the
       entry, its plan, or its detail wins over the general one.
     - *Partial:* narrow the entry to the verified remainder and cite what
       shipped.
     - *Superseded or false premise:* close with a dated reason.
     - *Uncertain:* add a dated evidence note.
  4. **Citation sweep before closing.** Search tracked docs for the id and
     the entry's title vocabulary — roll-up boards, arc and runbook docs,
     seeds, plans — and update or explicitly keep each hit.
  5. **Surface instead of changing** when the entry is `decision-needed` or
     `parked`, or records a user decision not to reopen.
  6. **Commit and report.** Use a tracker-only commit, separate from #378's
     records and from plan edits; the user-facing response lists each entry
     changed with its disposition and evidence.
- **Effort:** small — one subsection beside #378's rule. No code.
- **Risks:** a false closure hides live work (default 2); over-deletion and
  dangling citations (defaults 3–4, drawn from the measured incidents); drift
  into backlog grooming (default 1).
- **Dependencies:** none — the installed reference shipped 2026-09-16 as the
  skill-router-and-shared-reference plan (formerly tracked as #370). Sequence
  after #378 when both are taken: this rule reuses #378's convention discovery
  and commit rhythm. Taken alone, it states those two rules itself.
- **Outcome:** an existing entry that a driving session observes to be
  addressed stops reading as open work, through a verified, citation-swept,
  separately committed update or a surfaced evidence note.
- **In scope:** a subsection of `integrations/shared/DIRECTIVES.md` beside
  #378's rule, and router pointers only where #378 places them.
- **Out of scope / Non-goals:** the plan's own source entry (the existing
  rule and #377); recording new discoveries (#378); a command that detects or
  closes addressed entries; `docs/TRACKING.md`'s closure convention and this
  repo's board, tier, and lens roll-up rules, which the reference names only
  generically as "roll-up views the host repo maintains"; closing items in an
  external issue tracker.
- **Allowed behavior changes:** guidance text only.
- **Allowed reorganization:** none.
- **Verification:**
  - The subsection exists and names the dispositions, the citation sweep, and
    the surface-instead cases (binary).
  - A hand replay reaches the right outcome on the three measured incidents:
    #337 (the plan-specific retention rule beats general removal), #315 (the
    sweep finds the arc-doc citation), and `2b0273cc`'s already-fixed defect
    (verified, not filed).
  - Deliberately not checked: whether a session notices an addressed entry, or
    the soundness of its verification.
- **Stop / defer:** if a host repo's closure convention cannot be discovered
  generically, default to a dated evidence note and surfacing rather than
  inventing a removal policy.
- **Route:** `direct`. **Escalate to plan if:** the user wants per-entry
  confirmation before any closure (which also changes #378's authority line),
  or closure needs host-convention variants the reference must spell out.
- **Readiness:** `ready` — the router/reference split it depended on (formerly
  #370) shipped 2026-09-16.
- **Tier:** `architect` — it governs when a session may remove a record
  another author wrote.
- **Origin:** 2026-09-16, the same review as #378. Split out because recording
  a new discovery and retiring an existing record are separate outcomes with
  separate failure modes.
- **Status:** not started.

### B. Significant UX changes

**#262 — Surface a detail-readiness advisory after repeated bare-plan audit churn**

- **What:** when a plan remains bare after several fresh completeness audits,
  deterministic checks are clean, and no CRITICAL/HIGH conceptual-correctness
  finding remains, emit one report and terminal advisory that the next useful
  validation surface is step detail. The advisory names the qualifying bare-audit
  count, the remaining findings/owning steps, and the detail command; it says
  plainly that this is a stage-transition recommendation, **not** proof that the
  plan is complete. A budget-limited or still-discovering audit remains
  unconfirmed coverage, not a reason to hide the recommendation.
- **Why:** a bare plan has no detail bundle for the audit to ground against, so
  repeated conceptual samples can keep discovering increasingly fine
  implementation contracts. The retired #231 planning session reached eight
  bare-plan audits; initial high-level gaps were resolved, but later MEDIUM
  findings were schema, timestamp, event-history, and rendering choices that
  step details are designed to pin. The existing stage bars correctly preserve
  correctness findings; they do not tell the operator that further bare-plan
  sampling now has lower value than authoring detail.
- **Effort:** medium — this is a cross-plan audit/report policy with history
  filtering, stable report/JSON rendering, CLI summary copy, and fixture
  coverage; it must not be an uncalibrated counter hidden in a prompt.
- **Risks / fallout:** a premature recommendation could teach users to defer a
  genuinely unsound design into detailed prose, while an over-strict predicate
  recreates the current silent churn. Audit histories include legacy and
  checkpoint sidecars, so the counter must use only eligible final
  completeness reports and must degrade to no recommendation when the evidence
  is absent. Copy must not imply a changed exit code, bar, or pass/fail verdict.
- **Dependencies / related:** the settled bare-vs-detail convergence bar. #260
  is parked and supplies no prerequisite; this item consumes the shipped stage
  facts without adding a second blocking rule. #241 narrows what the bare prompt
  emits, and #139 separately routes implementation-time findings; neither is a
  substitute for telling the operator when detail is the better next artifact.
  #238's saved plan-mass snapshots provide supporting evidence but must not
  become a growth threshold.
- **Scope contract:**
  - **Outcome:** eligible bare-plan audits render a deterministic,
    recommendation-only detail-readiness signal with its evidence and a precise
    next command; ineligible audits render nothing new.
  - **In scope:** `plan_tool/review_persistence.py` history readers and saved
    audit metadata, `plan_tool/completeness_report.py` report/JSON display,
    `plan_tool/cli/completeness_cmd.py` terminal summary, relevant CLI/report
    fixtures, and user-facing CLI documentation.
  - **Out of scope / Non-goals:** changing conceptual finding severity or
    source; suppressing, auto-applying, or reclassifying findings; modifying
    `--audit-passes`; changing the bare/detail blocking bars or exit codes;
    automatically invoking `detail`; and adding a plan-mass or audit-count gate.
  - **Allowed behavior changes:** one informational report/terminal advisory
    and, if needed for machine consumers, a clearly non-blocking JSON advisory
    payload. Existing audit verdicts, findings, and exit codes stay unchanged.
  - **Allowed reorganization:** none beyond a small pure eligibility/rendering
    helper shared by the report and terminal surfaces.
  - **Verification:** fixtures cover (a) an eligible sequence of final bare
    reports with only MEDIUM-or-lower correctness findings, (b) a HIGH/CRITICAL
    correctness finding suppressing the signal, (c) a completed or partial
    detail bundle suppressing it, (d) checkpoint/legacy/unreadable reports not
    inflating the count, and (e) budget-limited coverage retaining its existing
    unconfirmed warning beside—not replaced by—the advisory. Assert unchanged
    return codes and blocking JSON fields.
  - **Stop / defer:** if replay across saved histories shows the predicate is
    either nearly universal or never useful, record the measurement and close
    this as a no-op rather than tuning thresholds to the retired #231 planning
    session.
- **Approach:** `plan-tool` — policy, persistence/history selection, two render
  surfaces, JSON compatibility, and calibration require a scoped plan rather
  than a direct copy edit.
- **Quality:** `convergence` and `gate-signal` — sharpens the operator's next
  action without weakening the audit's correctness or coverage verdicts.
- **Iteration:** use the current `integrations/shared/DIRECTIVES.md`
  authoring and audit gates. The scope fence is enforced by the plan's
  contract; it does not require a one-shot `create` pass.

  ```bash
  plan-tool create detail-readiness-advisory --iterate -y --from-existing BACKLOG.md
  plan-tool detail detail-readiness-advisory --commit -y
  plan-tool completeness-audit detail-readiness-advisory --iterate --commit -y
  plan-tool run detail-readiness-advisory --mode reconcile --iterate -y --step N
  ```
- **Origin:** 2026-08-11, operator decision during eight bare-plan audits of
  the now-retired #231 plan: the plan was materially ready for detail, but the
  audit offered only more findings and no stage-transition signal.
- **Status:** not started.

**#167 — Make plain English the default writing style for every generated plan-detail file**

- **What:** Change `plan-tool detail` so every generated per-step detail file is
  understandable in plain English on a first read. Keep concrete file paths,
  symbol anchors, constraints, test intent, acceptance criteria, and any required
  call order or compatibility rule. Those technical facts are non-negotiable;
  rewrite only the prose around them into short, direct sentences and familiar
  words. Detail should explain what to change, why it matters, and how to tell it
  worked without making the reader decode dense phrasing.
- **Why:** Detail is handed to people and executing agents after the planning
  context has faded. Dense abstractions, stacked clauses, unexplained jargon, and
  long lists of conditional mechanics make it hard to tell the required outcome
  from optional implementation suggestions. They also encourage stale,
  over-prescriptive prose. Plain English improves reviewability and supports
  #164's lower-altitude contract without removing the evidence an implementer
  needs to find the right code.
- **Design sketch:**
  1. Define a shared writing rubric for run-grade detail: lead with the outcome;
     use active voice and short sentences; **be to the point — say each thing
     once, no filler, no restated context**; expand or explain project
     abbreviations; separate required constraints from suggested implementation;
     and use a small concrete example instead of a dense abstract paragraph.
     Both directives (plain English and conciseness) target the descriptive
     prose only — they never reduce code anchors, paths, symbols, examples, or
     stated constraints.
  2. Update run-grade detail prompts and quality-review prompts to use that
     rubric. Preserve every full repo-relative path, symbol anchor,
     identifier, test reference, and required mechanical/compatibility sequence;
     make the explanatory sentences around those anchors easier to read instead
     of removing or generalizing the anchors themselves.
  3. Add conservative checks for mechanical signals (such as excessive sentence
     length, undefined acronyms, and outcomes buried under mechanics), plus model
     review guidance for clarity that heuristics cannot judge. Findings recommend
     a rewrite; they never silently delete facts. Sentence- and paragraph-length
     thresholds are stated directly in this repo's own words (see Decision
     below), not sourced from an external standard.
  4. Provide an opt-in re-author/review path for existing bundles. New detail is
     the default target; do not bulk-rewrite the corpus on upgrade.
- **Decision (2026-08-27): plain, self-stated rubric — not an external writing
  standard.** An earlier version of this entry proposed sourcing the
  sentence-length/mechanical-signal thresholds from ASD-STE100 (Simplified
  Technical English, an aerospace/defense controlled-language spec), reasoning
  that an externally validated source would beat thresholds invented per plan.
  Reconsidered: the core ask — short sentences, active voice, no filler — does
  not need a licensed external standard's provenance to be legitimate; this repo
  already states every other convention in its own words (this file, CLAUDE.md,
  the format docs), and importing ASD-STE100 added real cost with no
  corresponding benefit — a restricted-redistribution PDF to store and
  hand-transcribe, and a controlled dictionary that would have flagged
  legitimate API names (`invoker`, `fingerprint`, `worktree`) as violations had
  it been adopted. Do not re-open without a concrete case where a self-stated
  threshold produced a materially worse result than a sourced one would have.
- **Effort:** medium — `plan_tool/prompts/detail*.md`,
  `plan_tool/prompts/detail-quality.md`, `plan_tool/detail.py`,
  `DETAIL_FORMAT.md`, fixtures, and quality tests.
- **Risks / fallout:** simplistic readability rules can erase necessary precision
  or flag legitimate API names. Treat paths, symbols, identifiers, code spans,
  test references, and stated mechanical/compatibility constraints as immutable
  facts; keep heuristic signals advisory and pin both plain-English and
  precision-preserving technical fixtures.
- **Dependencies:** complements #149 (compact structure). Jira-grade detail is
  retired by #308, so this entry applies only to supported run-grade detail.
- **Scope contract:**
  - **Outcome:** newly authored plan detail is clear, direct plain English while
    retaining the actionable technical facts needed to implement and verify it.
  - **In scope:** detail prompts, detail-quality prompts/checks, the detail
    parser/quality loop as needed, `DETAIL_FORMAT.md`, fixtures, and tests.
  - **Out of scope / Non-goals:** changing plan-body prose; removing, weakening,
    or generalizing required evidence, file paths, symbols, tests, acceptance
    criteria, or mechanical constraints; changing implementation behavior; bulk
    rewriting existing bundles without opt-in; sourcing thresholds from an
    external writing standard (decided above).
  - **Allowed behavior changes:** new detail output and clarity findings may be
    more concise and less prescriptive; existing read compatibility remains.
  - **Allowed reorganization:** only the prompt/quality helpers required to
    share one rubric across supported detail grades.
  - **Verification:** tests demonstrate that clear detail passes, jargon-heavy or
    overly dense surrounding prose gets a targeted clarity finding, and every
    technical anchor/constraint stays byte-for-byte present through the rewrite.
    Review samples from each grade for direct, outcome-first language without loss
    of anchors.
  - **Stop / defer:** if a clarity check cannot distinguish verbosity from
    necessary precision, keep it advisory and defer blocking or auto-rewrite
    behavior rather than degrading implementation guidance.
- **Approach:** `plan-tool`, direct. The output contract and quality loop own
  this behavior; it does not require an open architectural experiment.
- **Status:** not started. 2026-07-22 — two directives recorded: (1) the
  rubric explicitly includes **conciseness** (prose to the point, not
  verbose) alongside plain English, both aimed at descriptions only — code
  anchors and examples are never reduced; (2) the then-supported Jira-grade
  authoring lane applied this rubric at birth. That lane is retired by #308;
  this entry now owns only existing run-grade surfaces. Extending the same
  rubric to **plan-body
  prose** (`create` output) is outside this entry's fence — promote it to
  its own entry when scheduling this work.

**#149 — Compact `detail` output: `--summary` review cards + a compact required-H2 authoring schema — PLAN-AUTHORED (`detail-verbosity-compact-summary`)**

- **What:** make `plan-tool detail` output less verbose in two reinforcing
  layers. (1) A read-only **summary review surface** (`plan-tool detail <name>
  --summary`) prints one compact review card per step from existing detail
  files (Intent/Summary + Footprint/Files + Done-when/Acceptance + short
  Tests/Deferred), spending no Claude and always exiting 0. (2) A **compact
  required detail schema** that changes what `detail` authors by default:
  merge Summary+Why into a single `Intent` and drop the Table of Contents.
  **Blocked by #308:** this plan's current compact-schema authority is the
  retiring Jira-grade lane. Do not preserve `plan_tool/jira_grade.py` as an
  alias source. Re-baseline the compact-schema phase on a run-grade-owned
  contract before execution; a complexity gate can then keep `low` steps
  always-compact while `medium`/`high` may expand only the section carrying
  the approach.
  Legacy seven-section files stay valid on the **read** path via dual-token
  lookup — nothing is force-migrated; the write path emits compact only. The
  read-only `--summary` layer (1) is untouched by the re-baseline: it renders from
  whatever sections a file has.
- **Why:** `_REQUIRED_H2_TOKENS` hard-requires seven sections, so even a
  one-line change authors ~70 lines and denser steps land at ~120–170; ToC is
  ceremony, Why duplicates Summary, and Implementation inflates into call-site
  inventories. Existing "intent over mechanics" guidance is inert because
  `detail-altitude` is advisory/non-apply-eligible and sibling tone-matching
  re-inflates new files. Length also compounds cost: `run` injects the full
  detail body into the implementer prompt (relates to #38's detail-length
  drift signal).
- **Approach:** `plan-tool` — its own decomposition (~6 steps across three
  phases: A summary cards, B compact authoring contract + complexity gate +
  sibling hygiene, C read-compat/migration). Touches `plan_tool/detail.py`
  (`_REQUIRED_H2_TOKENS`/`_REQUIRED_H2_DISPLAY`/parse gate + read
  compatibility), `plan_tool/cli/authoring.py`, `plan_tool/prompts/detail.md` +
  `detail-quality.md`, `DETAIL_FORMAT.md`, `docs/DETAIL_FLOW.md`, CLI-reference
  regen, and `tests/test_detail.py`. **Out of scope:** the retired Jira-grade
  lane, the #49 interactive wizard (only follows the contract change), #133
  purity-prompt size, and auto-rewriting historical detail files.
- **Status:** a WIP plan `docs/implementation-plans/2-detail-verbosity-compact-summary.md`
  (status `planning`, 6 steps) is authored for this; its detail bundle is
  **incomplete** (steps 1–3 detailed, 4–6 pending) and it is **not yet
  registered** in `.plan-tool/plans.json`. When the plan ships, its final step
  removes/marks this entry and updates #49's seven-section language if that
  entry remains open. **Blocked 2026-09-02:** #308 removes the former
  Jira-grade schema authority. Re-baseline the WIP plan and its incomplete
  detail bundle before phase B runs; it must not retain the removed module as
  a compatibility dependency. The terminal companion in #293 is a separate
  projected handoff, not this entry's target surface.
- **Origin:** 2026-07-18 — filed to close the plan's dangling forward-reference
  to "BACKLOG #149" (the plan's step 6 and detail files cite it). Companion to
  #38 (detail length as a drift signal) and #49 (the detail wizard).

**#114 — Give `detail`, `completeness-audit`, `completeness-apply` the same no-name plan-picker `run` already has, filtered to each command's applicable state**

- **What:** Today only `run` accepts a missing plan name and falls back to an
  interactive picker (`run_cmd.py:_select_open_plan` over `_open_plan_entries`,
  which keeps `e.plan is not None and not e.plan.all_steps_done`). `detail`,
  `completeness-audit`, and `completeness-apply` make `name` a required positional
  (`authoring.py` `p_detail`, `completeness_cmd.py` `p_completeness` /
  `p_completeness_apply`) and argparse-error when it's omitted — with no help
  discovering which plans are actually in the right state for that command.
  Generalize `run`'s picker so all four commands, given no name on a TTY, list the
  plans **applicable to that command** and let the user choose.
- **Per-command filter predicate (the applicable-state definition):**
  - `detail` → plans that **need detail**:
    `audit_detail_bundle_status(plan, path, repo_root).is_bare` (at least one step
    has no detail file). `.is_fully_bare` distinguishes freshly-created from
    partially-detailed.
  - `completeness-audit` / `completeness-apply` → plans with a **complete detail
    bundle** (`not .is_bare`) — surface only plans whose detail exists so the
    picker favors fully-actionable targets (mirrors `cmd_completeness_apply`'s
    `_BARE_PLAN_WALKABLE_SOURCES` gate, which walks only `plan-correctness` on
    bare plans). A bare plan named explicitly is still accepted (the audit runs
    and correctness gaps can be walked); the filter governs only what the picker
    *offers*, not a hard capability gate.
  - `run` → unchanged: plans with a runnable step (its current `_open_plan_entries`
    filter).
- **Display / filtering:** **hide** non-applicable plans from each picker (don't
  just label them), matching `run`'s existing filter-then-list behavior; print a
  one-line footer noting how many plans were hidden and why (e.g. "3 plans hidden
  (already detailed / complete)"). Each offered row still carries a state label —
  needs-detail / ready-to-run / partially-completed / complete — computed from
  `done_count` / `all_steps_done` / `next_runnable_step()` / `current_step()` so the
  user sees *why* a plan is offered.
- **Reuse (all cheap, no Claude):** enumerate via `ctx.entries` from
  `_load_context(args)` (`cli/context.py`); needs-detail axis via
  `plan_tool.review.audit_detail_bundle_status` → `DetailBundleStatus.is_bare` /
  `.is_fully_bare`; run/completion axis via `Plan.done_count` / `all_steps_done` /
  `next_runnable_step()` / `current_step()` (`schema.py`). Factor `run`'s picker
  (`_open_plan_entries`, `_open_step_hint`, `_select_open_plan`, `_read_plan_choice`,
  and the non-TTY hard-error-with-`plan-tool list`-hint guard) into a **shared helper
  parameterized by (a) the filter predicate and (b) the per-row state label**, rather
  than copy-pasting into three commands. Model row output on `cmd_list`'s row builder
  (`inspect.py:140–179`) and `_select_open_plan`'s menu.
- **Effort:** medium — one shared picker helper + three parser changes (`name` →
  `nargs="?"`, `default=None`) + three call-site fallbacks + tests. No new plan-state
  primitive is needed; the tri-state composes from the helpers above.
- **Risks:** small. Making `name` optional must preserve the non-TTY / piped path as a
  hard error (rc=2) exactly like `run` — a picker must never block a scripted/CI
  invocation. `completeness-apply --jobs > 1` is already non-interactive (requires
  `-y`), so the picker is a TTY-only affordance on the default `--jobs 1` path. Keep
  the MALFORMED handling (`e.plan is None`) `cmd_list` already does so unparseable
  entries don't crash the picker.
- **Dependencies:** none — every primitive already exists.
- **Approach:** `plan-tool` — cross-cuts four command surfaces + a shared helper +
  tests, a natural fit for the create→detail→run pipeline.
- **Origin:** 2026-07-09 — requested to make the plan-consuming commands
  self-discoverable, extending `run`'s existing picker to `detail` and the
  completeness verbs.

**#69 — Close (or explicitly document) the standalone `reconcile-plan` unattended-apply gap** → promoted to IPPT-13 (2026-09-27)

**#115 — Give the completeness per-step purity/quality sweep the same heartbeat the conceptual-audit and detailing phases already have (it currently runs silent for tens of minutes)**

- **What:** During `detail`'s post-detail completeness sweep,
  `_collect_purity_split_findings` (`plan_tool/cli/completeness_phases.py:515`)
  loops over every non-DONE code step and calls
  `detail.collect_detail_quality_findings(...)` **without a `reporter=`**
  argument. That producer is silent-by-default (`detail.py:1156` — "`reporter`
  opts the silent claude call into the same start + heartbeat lines… `None`
  (the default) keeps the original quiet-probe behavior"). So each step is a
  live 5–6 min `claude` call that emits **zero** terminal output; a 7-step plan
  produces ~35–40 minutes of total silence, which reads as a hang. The
  conceptual-audit loop (`completeness_phases.py:807`) and the main detailing
  loop (`detail.py` default `StderrReporter`) both already pass a reporter and
  animate the `▸ … / ⋯ step N · Ns elapsed / ✓ done in Ns` heartbeat; this one
  sweep is the gap. Thread a `StderrReporter()` plus an `[i/n]` step counter
  into the loop so each step's scan shows the same liveness
  (`▸ [3/7] step 3 · scanning… / ⋯ step 3 · 45s elapsed / ✓ step 3 · done in 312s`).
- **Reuse (no new machinery):** `collect_detail_quality_findings` already
  accepts `reporter=` and wires the 15s heartbeat at `detail.py:1189-1199`
  (`HEARTBEAT_INTERVAL_S = 15.0`, `progress.py:53`); two of its existing callers
  already pass a reporter, so the idx/total param convention is established —
  confirm the exact kwarg names (`invoke_idx` / `invoke_total`) before wiring.
  Precompute the applicable-step list (the `status != DONE and change_type !=
  NON_CODE` filter already in the loop) so the `[i/n]` total counts only steps
  that actually invoke claude, not all `plan.steps`.
- **Effort:** small — one `StderrReporter()` construction + a filtered
  enumerate + three added kwargs at the single call site, plus a test asserting
  the sweep emits start/done lines (mirror the conceptual-audit reporter test).
- **Risks:** small. Keep the non-TTY / piped path byte-stable (the reporter
  already falls back to line-per-tick off a TTY, `progress.py:234`); don't let
  the heartbeat thread spin on the quiet-probe early-return path (a step with no
  `detail` pointer returns `[]` before any claude call — `start_step` must not
  wrap that no-op, or guard it the way the resumed-checkpoint branch does at
  `detail.py:1660`).
- **Dependencies:** none — every primitive exists.
- **Approach:** `direct` — one call site, established reporter pattern, one test.
- **Origin:** 2026-07-09 — a `detail geographic-filter-recommendations --commit`
  run appeared hung during the post-detail sweep; traced to this call site
  running `collect_detail_quality_findings` in quiet-probe mode while each
  per-step claude call ran for minutes with no terminal output.

### C. Investigations / decision-making





**#507 — A recorded `single` decision should stop the audit's mixed-step finding from recurring**

- **What:** `plan-tool decide <name> --outcome single --anchor step:N` records
  that a step is deliberately one unit. The conceptual audit's mixed-step rule
  (the `plan-audit.md` finding for a step that combines a behavior-preserving
  change with new behavior) does not appear to read that record, so the same
  finding returns on every re-audit. Decide whether a recorded `single`
  decision on the step should suppress it, and whether the decision's
  rationale should be shown to the auditor.
- **Why:** an owner can accept a mixed step on purpose, and `decide` is the
  documented place to record it, but the audit keeps blocking the gate on that
  step. In Integration's `construction-batch-driver` plan, steps 2 and 12 were
  recorded as `single` after Gate 2 round 2, and the finding recurred in rounds
  3, 4, 5, 6 and 8. The code path was not traced; the recurrence is the only
  evidence, and a round with no finding does not show the decision was read.
- **Effort:** small to medium; the audit needs the step's decision records in
  its prompt context, and the finding needs a way to be excused.
- **Scope contract:**
  - **Outcome:** a decision, then (if built) an audit that excuses a mixed-step
    finding on a step with a recorded `single` outcome and says so in the
    report.
  - **In scope:** reading `decide` records at audit time, the finding's
    excuse, and the report line.
  - **Out of scope / Non-goals:** changing what counts as mixed; excusing any
    other finding class; hiding the finding without a recorded decision.
  - **Allowed behavior changes:** fewer mixed-step findings on steps with a
    recorded `single` decision.
  - **Allowed reorganization:** none.
  - **Verification:** a plan with a mixed step and a recorded `single`
    decision audits without that finding, and the report names the decision;
    the same plan without the decision still reports it.
  - **Stop / defer:** if the audit already reads the record and the recurrence
    has another cause, record that and close.
- **Route:** `plan` · **Readiness:** `decision-needed` (whether a recorded
  decision excuses the finding) · **Tier:** `architect`.
- **Principle:** `converge-on-correct-plan`.
- **Origin:** 2026-10-19, Integration `construction-batch-driver` Gate 2 rounds 3 to 8.

**#495 — Decide the default number of conceptual-audit passes from measured per-pass yield**

- **What:** once enough audits carry `audit_pass_end` run-log events, compute
  how often audit passes 2 and 3 add a material finding that pass 1 did not,
  and decide whether the default `--audit-samples` (3 passes) can drop. The
  conceptual audit (`plan_audit`) was 47% of the tokens in a 1,480-call
  run-log ledger (193M of 406.8M non-cached input plus output tokens), and
  24.8% of saved audits (218 of 879) ended budget-limited at the 3-pass cap.
  Until now nothing recorded what each pass found, so the value of later
  passes could not be measured.
- **Why:** `plan_tool/review.py:audit_plan_until_stable` writes one
  `audit_pass_end` event per pass since 2026-10-16: pass number, outcome, the
  finding ids first seen that pass, the material subset, exact counts, and the
  running unique total. Saved completeness reports keep only the final union.
  Runs before 2026-10-16 have no such events and cannot be back-filled.
- **Effort:** small; a read-only analysis of `.plan-tool/runs/*/*.jsonl` with no
  model calls. Any change to the default is a separate, small edit.
- **Risks:** the id lists in the event are capped at 40, so compare the exact
  `new_count` and `material_new_count`, not list lengths. Audits that end early
  (plan quota, errored passes) are neutral and must not be counted as dry
  passes. A small or one-plan sample can make later passes look useless or
  essential; report the number of audits and plans behind the figure.
- **Dependencies:** about 20 audits recorded after 2026-10-16 (count with
  `grep -l '"event": "audit_pass_end"' .plan-tool/runs/*/*.jsonl`). Cost per
  pass uses `claude_call_end` events with phase `plan_audit` and the pass
  number as the attempt; non-cached input is `input - cache_read` when
  `input_includes_cached` is true and `input + cache_creation` when false.
- **Scope contract:**
  - **Outcome:** a recorded decision (keep, lower, or change the cap) with the
    measured yield table: per pass number, audits observed, share adding at
    least one material finding, and the tokens that pass cost.
  - **In scope:** reading run logs; the table; the decision.
  - **Out of scope / Non-goals:** changing audit convergence, blocking
    predicates, qualification, or exit codes; persisting per-pass ids in saved
    reports; any prompt change; lessons injection (a separate, shelved
    experiment).
  - **Allowed behavior changes:** none in this entry. If the decision is to
    lower the default, that edit is filed as its own entry.
  - **Allowed reorganization:** none.
  - **Verification:** the table can be recomputed from the same logs by
    another reader.
  - **Stop / defer:** if pass 2 or 3 adds material findings in a non-trivial
    share of audits, the default stays and this entry closes with that table.
- **Route:** `direct` · **Readiness:** `evidence-gated` (needs the audits above)
  · **Tier:** `experienced`.
- **Principle:** `none` — token cost of the conceptual audit; no grounding
  principle is served directly.
- **Origin:** 2026-10-16 token-ledger analysis; logging shipped in Bitbucket pull
  requests 101 and 102 (not backlog ids).

**#381 — Measure whether lesson-equivalence confidence supports its drop threshold**

- **What:** judge a small, representative set of lesson duplicate and conflict
  pairs, including cases on both sides of the current `0.6` floor. Compare the
  model's reported confidence with correct duplicate/conflict decisions and
  with the lessons that `strict_check` would drop. Report false drops, missed
  duplicates, and variation across the supported model backends.
- **Why:** `plan_tool/lessons.py:find_lesson_equivalences` filters model-authored
  numeric confidence at `DEFAULT_EQUIVALENCE_CONFIDENCE = 0.6`; unlike
  `Recommendation.confidence`, that value can affect a write decision. The
  present floor matches prompt guidance, not a measured correctness boundary.
- **Effort:** small investigation first; any later policy change is separate.
- **Risks:** a tiny or easy corpus can make a threshold appear reliable when
  real borderline pairs are not. Preserve each pair, model output, and judged
  disposition so another reader can reproduce the comparison.
- **Dependencies:** none for a disposable measurement. Coordinate with #216's
  corpus/noise-floor route before creating a durable benchmark, calibrated
  probability, or shared confidence policy.
- **Outcome:** a short evidence table and a recommendation to keep, change,
  or stop using the numeric floor for lesson-drop decisions. No threshold or
  write behavior changes in this item.
- **Approach:** `direct` investigation; propose a scoped implementation only
  if the measured result warrants one.
- **Status:** not started.

**#382 — Decide whether findings need inspectable evidence-support provenance**

- **What:** sample `Recommendation` findings from completeness audit, review,
  and reconcile reports and determine which reader decisions would improve if
  a `supported` or `limited` label named its supporting predicate, code
  reference, or missing proof. Specify a narrow producer-owned evidence shape
  only for a demonstrated gap; check existing finding body and report excerpts
  before proposing another persisted field.
- **Why:** #295 makes evidence support visible, but the label alone does not
  explain what earned it. The same label crosses several report and prompt
  surfaces, while `annotate` already carries its own low-grounding reasons.
- **Effort:** small investigation; a later persisted-schema change would be
  medium because saved reviews and caches need compatibility handling.
- **Risks:** duplicating prose evidence in a second field can drift, and a
  source name or model self-score can look like proof without verifying the
  finding. Keep confidence separate from severity, audit qualification, and
  blocking.
- **Dependencies:** completed #295. Coordinate any human-facing rendering
  with #316; do not absorb its mechanical formatter migration.
- **Outcome:** either a concrete evidence-provenance contract with named
  producers and consumers, or a no-change decision supported by sampled
  reports. No finding selection, priority, or gate changes in this item.
- **Approach:** `direct` investigation; use a plan if the selected follow-up
  changes the `DATA_CONTRACT.md` persisted shape across readers.
- **Status:** not started.

**#380 — Decide what the scope guard emits instead of an `out-of-scope-findings` plan stub**

- **What:** decide where an iterate loop's scope-guard records go.
  `plan_tool/scope_guard.py:write_out_of_scope_plan` writes
  `<N>-out-of-scope-findings-from-<slug>.md`, with `status: planning` and
  `steps: []`, into a plans directory, and nothing registers it in the
  manifest. It is reached through `plan_tool/cli/reconcile.py:_emit_scope_guard_plan`
  from six call sites in `reconcile.py:_iterate_reconcile_loop` and five in
  `plan_tool/cli/completeness_phases.py:_run_iterate_convergence_loop`.
  `CLAUDE.md` § "Authoring hygiene and anti-creep" and
  `integrations/shared/DIRECTIVES.md` § "Authoring hygiene" both call that
  artifact a defect that falls outside plan discovery, never converges, and
  rots.
- **Evidence:**
  - Run-created stubs were cleaned up by hand in `701f3fda` and `fa1f03b2`
    (both 2026-06-22). No stub has been committed since. Whether any supported
    session-driven flow still populates `scope_buffer` is unverified;
    `docs/TRACKING.md` phase 3b's `run --mode reconcile --iterate` is the
    likeliest remaining path.
  - The stub mixes two kinds of record: `reverted` records are deferred work,
    while `kept-by-impact` records are scope expansions that already landed
    and need review.
  - `classify_plan_scope` routes skill- and agent-scoped records to
    `<root>/skills/<name>/implementation-plans/` or
    `<root>/<name>/implementation-plans/`. Whether any consumer still uses that
    layout is unverified.
  - `docs/implementation-plans/2-deferred-scan-digest.md` harvests plan-body
    sections, report JSON, and `concepts.json`, and names no stub source.
- **Options (none selected):**
  - (a) Keep the stub and amend the routing rule to expect it, with #378
    carrying the migration — the cheapest option, and it keeps the rot.
  - (b) Persist the records in the loop's saved report under
    `plan-details/<slug>/reports/` and print a filing checklist that names the
    report — the digest plans already read that source.
  - (c) Append entries to the host repo's tracker — rejected up front, because
    the tool cannot know a host repo's tracker or entry format, and Integration has
    none.
  - (d) Print a stderr checklist only — this loses durability, and a terminal
    line is not a record.
  - Whichever option is chosen keeps `kept-by-impact` review separate from
    deferred records.
- **Effort:** small — read-only analysis and a decision record.
- **Risks:** the answer may be "unreachable in practice; no action", which is
  an acceptable outcome for a decision item.
- **Dependencies:** none. It informs #378's stub trigger, and #378 does not
  wait on it.
- **Outcome:** one recorded decision on the destination for scope-guard
  records, consistent with the backlog-routing rule, plus either the follow-up
  entry that implements it or a dated no-action close.
- **In scope:** reading `plan_tool/scope_guard.py`,
  `plan_tool/cli/reconcile.py`, `plan_tool/cli/completeness_phases.py`, their
  tests, and the two deferred-digest plans; the decision record.
- **Out of scope / Non-goals:** implementing the chosen option; the scope
  guard's classification (revert, keep-by-impact, keep-documentation) and its
  snapshot and revert mechanics; orchestrator guidance (#378); the digest
  plans' harvest sources.
- **Allowed behavior changes:** none.
- **Allowed reorganization:** none.
- **Verification:** the decision names the chosen option, each rejected
  option's reason, the evidence on whether session-driven use reaches the stub
  writer, and the follow-up entry.
- **Stop / defer:** if no supported flow reaches the writer, close with that
  evidence and a dated note rather than designing a replacement.
- **Route:** `direct` (a decision record).
- **Readiness:** `decision-needed`.
- **Tier:** `experienced` — it stays within existing contracts, but the
  records it decides on are written by `scope_guard.py` and emitted by both
  the reconcile and completeness loops, so the choice changes behavior across
  modules. A wrong choice shows up as a review finding against the
  backlog-routing rule, not as a failing test.
- **Origin:** 2026-09-16, found during #378's review of where out-of-scope
  findings land. Filed rather than folded into #378 because it changes tool
  output, not orchestration guidance.
- **Status:** not started.

**#366 — Survey aidlc-workflows's multi-harness patterns (core/adapter split, provider-agnostic tier aliasing, build-determinism guard) for plan-tool applicability**

- **Principle:** `untriaged` — a survey that may close with no action.
- **What:** plan-tool and the sibling project `aidlc-workflows`
  (`<methodology-root>`) solve a similar
  shape of problem — one authored behavior projected into multiple
  heterogeneous CLI backends (aidlc: Claude Code, Codex, Kiro, Cursor,
  opencode, Copilot; plan-tool: its own multi-backend `--backend` /
  `--fallback-backend` invoker seam) — but arrived at it independently. A
  read-through of aidlc's Claude-Code-vs-Codex hook wiring turned up three
  concrete mechanisms worth checking against plan-tool's own architecture,
  not yet compared in either direction.
- **Output of investigation:** for each of the three candidate patterns
  below, either (a) confirm plan-tool's existing architecture already has
  the equivalent property and cite where, (b) name a concrete gap and the
  smallest surface a fix would touch, or (c) rule it inapplicable and say
  why. No code changes land from this entry itself.
  1. **Single behavioral core + thin per-backend adapter, not per-backend
     logic forks.** aidlc ships 17 identical hook scripts
     (`core/hooks/aidlc-*.ts`) used verbatim by every harness; Claude Code's
     native `hooks` block in `settings.json` invokes them directly, while
     Codex — despite having its own native hook-event system with matching
     event names — routes every event through one adapter
     (`harness/codex/hooks/aidlc-codex-adapter.ts`) that normalizes
     payload-shape differences (patch-envelope edits, a different
     plan-tracking tool, duplicate event delivery, no native `SessionEnd`)
     before invoking the same core file. Per-backend logic lives only in the
     adapter; the 17 hook files never fork per harness. Check plan-tool's own
     invoker seam (`CLAUDE.md` § "Architecture", the module map in
     `docs/ARCHITECTURE.md`) for whether backend-specific logic has leaked
     into shared modules anywhere, or whether it is already cleanly isolated
     the same way.
  2. **Provider-agnostic vocabulary for model/effort selection, resolved at
     the harness boundary, never hardcoded upstream.** aidlc's
     tier-projection module (`core/tools/aidlc-tiers.ts`) names three tiers
     by *how much judgment the work needs* (`judgment` / `balanced` /
     `templated`), and a single `TIER_PROJECTIONS` table maps each tier to
     each harness's native model/effort knob — Claude gets `model: inherit`
     or an alias like `sonnet`, Codex gets an omitted key or a pinned model
     string, Kiro always inherits. No file outside that one module ever
     names a raw model ID. Check whether plan-tool's own `--model` /
     `--backend` / `--fallback-backend` / `--on-rate-limit` flags have an
     equivalent single-source-of-truth resolution point, or whether
     model/backend choice is threaded through call sites in a way a future
     provider addition would have to touch in more than one place.
  3. **Byte-identical double-build determinism guard.** `bun
     scripts/package.ts --check` builds aidlc's generated output twice into
     independent temp roots and byte-compares them as a standing regression
     guard against nondeterministic generation (path leakage, timestamp
     embedding, unstable iteration order). Check whether any of plan-tool's
     own generated artifacts (`install-skill`'s symlink/copy output, `jira`
     emission, `roadmap --view html`) have an equivalent guard, and whether
     one would be cheap to add given plan-tool's existing test infra
     (`tests/cli/test_cli_reference.py` already drift-guards the flag
     reference the same way).
- **Effort:** small (the investigation itself, read-only against both
  repos' source); each finding that clears investigation becomes its own
  backlog entry with its own effort estimate.
- **Dependencies:** none — read-only against `aidlc-workflows` (external
  repo, not a plan-tool dependency) and plan-tool's own current source.
- **Approach:** `direct` (investigation only) — decision first; do not seed
  or `create` any of the three candidate patterns until this entry names a
  concrete gap for it.
- **Origin:** 2026-09-10 — raised while producing a report on
  `aidlc-workflows`'s Claude Code / Codex hook integration
  (`aidlc-workflows-rupe120/tmp/2026-09-10-claude-codex-hooks-report.md`);
  not yet compared against plan-tool's own architecture in either
  direction.
- **Status:** not started.

**#357 — Judged bare-gap classifier: does a restated correctness finding actually name an unrouted plan-level property?**

- **What:** `Recommendation.restated_property` (`plan_tool/review.py`) carries
  a plan-altitude restatement of each cited bare-step `plan-correctness`
  finding — the `### Restated` sub-block `plan-audit.md`'s "Property coverage
  versus delivery mechanisms" rule requires, parsed by
  `_split_audit_restated_and_fix` — but renders no verdict on purpose — the
  human/session still decides whether the restated claim is a real gap. This
  entry asks whether a second, judged pass can go further: given the
  finding, its citation, and its restatement, classify it into a closed,
  anchored, recommend-only disposition (e.g. `bare-gap` / `likely-detail-owned`
  / `uncertain`) — the direct analog of the already-shipped, deterministic
  `classify_likely_bare_mechanism` (`plan_tool/review.py:2526`) /
  `classify_bare_mechanism_advisory`
  (`plan_tool/convergence_diagnosis.py:1413`) pair, but judged instead of
  phrase-matched, and fed by the restatement's cleaner input.
- **Output of investigation:** a decision, not yet an implementation. Before
  any `create`, name (a) the closed disposition vocabulary and its total
  mapping (every qualifying finding gets exactly one label, no "other"); (b)
  the false-positive mode — what kind of real bare-plan gap this would
  misclassify as detail-owned, and how that gets caught before a real finding
  is silently deprioritized; and (c) a concrete test fixture that would
  refute the classifier (a case it should get right and a case designed to
  fool it). If those three can't be named crisply, this stays deferred rather
  than becoming a seed.
- **Why judged, not deterministic:** the specific failure this responds to —
  a real, verbatim-quoted plan sentence whose *meaning* is misread (a
  scope/non-goal statement cited as an affirmative guarantee) — is a
  comprehension error a phrase list cannot catch; `classify_likely_bare_mechanism`
  already covers the vocabulary-tell version of this problem and stays as-is.
- **Why this is not the impact-recurrence mistake:** that classifier spun (10
  correctness findings, 0 steps shipped —
  `docs/NONDETERMINISM_PLAN_DESIGN.md`) because it judged an open-ended,
  unanchored, ungated question and its plan prose asserted judgment *content*
  as fact (Rule 2 there). This proposal is anchored to material
  `restated_property` already produces, and per Rules 1/4 must ship
  closed-vocabulary, anchored, total, and recommend-only by construction — the
  same shape `classify_bare_mechanism_advisory` already proved out (BACKLOG
  #290, shipped, not spun). The investigation above is what confirms that
  shape actually holds here before any code gets written.
- **Effort:** small (the investigation), if scoped as design-only; the
  resulting classifier, if the investigation clears it, is `plan-tool`
  (`create`/`detail`/`run`) — a judged feature needs
  `docs/NONDETERMINISM_PLAN_DESIGN.md`'s full seed-time checklist, not a
  direct edit.
- **Dependencies:** none blocking — `restated_property` already ships
  (landed as a direct edit to `plan_tool/prompts/plan-audit.md`'s
  property-coverage rule and its parser, not the separate downstream plan
  originally proposed; see below).
- **Approach:** `direct` (investigation only) — decision first; do not seed or
  `create` until the three items above are answered.
- **Origin:** 2026-09-01 — raised as a follow-on during the restatement
  feature's design conversation; deliberately kept out of that feature's
  scope (its non-goals explicitly exclude "any verdict, disposition,
  classification" on the restatement) so as not to reopen a settled non-goal
  mid-flight. The restatement itself was first designed as a separate
  downstream plan (`bare-correctness-restatement`), then withdrawn
  2026-09-01 and redone as an inline addition to the same audit call once it
  became clear a separate pass has less grounding than the pass that
  actually traced the plan, and so risks misrepresenting the finding it
  restates — see `docs/implementation-plans/archive/2-bare-correctness-restatement.withdrawn.md`
  for the withdrawal record.
- **Why the inline redesign doesn't reopen the withdrawn plan's own
  self-defense-bias concern:** that plan argued a separate pass was needed
  because "a self-check inside the same call that just produced the finding
  is prone to defending it rather than re-examining it." The inline
  restatement was never relying on the model catching its own mistake —
  its job is to hand a human/session evidence to check against the
  finding's own quoted citation, not to self-correct — so that specific
  risk doesn't bear on it. The place self-defense bias would actually
  bite — severity decided once, then revised by a later pass defending the
  first — is what plan-audit.md's severity-calibration instruction
  forecloses: severity is the finding's one judgment, reasoned from the
  restated framing from the start, never a second pass revising an earlier
  one.
- **Status:** not started.

**#246 — Measure whether private-vs-public helper splits are inconsistent elsewhere, before touching any of them**

- **What:** authoring `roadmap-view`'s plan hit one measured case of an
  inconsistent public/private split within a single conceptual family:
  `roadmap_gates.py` exports `design_row_ids` publicly (with a docstring
  explaining why — a sibling module needs the same set and "two
  implementations would drift") while `_domain_rows` and `_constraints_rows`,
  the same family of per-artifact row-set helpers, stay private in the same
  file, with `plans_design_rows` and `components_design_rows` public one
  module over in `roadmap_artifacts.py`. That forced `roadmap-view`'s plan to
  widen a placement rule mid-authoring rather than hitting a clean API. This
  entry asks whether that is a one-off oversight or a recurring pattern worth
  a general pass.
- **Output of investigation:** grep-and-read across the modules named in
  CLAUDE.md § "Architecture"'s cycle-free import list for the same shape — a
  private helper computing something a sibling module also needs and either
  duplicates or is one import away from reusing. Produce a short table of real
  sites (module, helper, who would import it, what breaks without it) or, if
  the roadmap case turns out to be isolated, close this as "measured, not
  recurring" and say so. **Do not propose a visibility change for any site
  without naming the concrete caller that needs it** — a private helper with no
  current or near-term consumer is not a finding, it is guessing at future
  reuse, and CLAUDE.md's anti-creep section already refuses exactly that move
  ("a consolidation opportunity you notice while doing something else is an
  out-of-scope finding — file it, don't take it").
- **Scope note:** this is explicitly **not** a mandate to audit or change
  visibility app-wide. BACKLOG #79's history is the cautionary precedent here —
  four of its five "duplicated helper" claims were wrong in the direction that
  breaks things once machine-checked, because resemblance was mistaken for
  evidence. The same discipline applies to a "should be public" claim: it needs
  a named caller, not a hunch that it looks like it should be reusable. If the
  measurement finds real recurring sites, promoting each one is ordinary
  `direct` work, not a redesign.
- **Effort:** small (the measurement); any resulting visibility changes are
  separate, per-site `direct` items. **Approach:** `direct` (investigation) —
  read the modules, name real sites or close it.
- **Dependencies:** none.
- **Origin:** 2026-08-07 — found while authoring `roadmap-view`'s plan,
  where `design_row_ids`'s public/private asymmetry with its siblings forced a
  placement-rule decision mid-authoring.

**#111 — Rework the `orphaned-deliverable` identity model — the per-condition directory-token tension is irreducible under a single symbol set**

- **What:** `detect_orphaned_deliverable` (`plan_tool/review.py`) keys its four
  conditions on a deliverable's path-derived identity symbols. A five-round
  review of the shipped detector showed no single identity breadth satisfies all
  conditions, because they pull opposite ways:
  - Conditions 2 (consumer found) and 3 (claim found) are **suppressors** — more
    symbol matching → more suppression → *fewer* spurious orphans (nags). They
    want the **broad** full-path identity (incl. the directory/package token).
  - Condition 4 (the step defers its own wiring) is a firing **trigger** — more
    matching → *more* firing → *more* nags. It wants the **narrow**
    filename-only identity.
  A directory/package token (`billing` from `billing/report.py`) is shared by
  every file in the package, so putting it in the identity broadly over-matches
  across steps (condition 2 cross-suppression) yet is a legitimate self-reference
  in a step's own claim/deferred prose (conditions 3/4). The current equilibrium
  (`review.py`: full identity for conditions 3/4, filename-only `consumer_symbols`
  for condition 2) is the one state the review found **no clear-cut bug** in, but
  it still carries accepted tradeoffs: a consumer naming the deliverable only by
  package word doesn't suppress (cond 2 nag); a same-package sibling can over-fire
  when the step defers by package word (cond 4 nag); an unrelated claim naming the
  package word over-suppresses (cond 3 false negative).
- **Output of investigation:** decide the detector's **conservatism target** for
  a blocking gate (the plan's stated bias is "prefer false negative over
  nagging") and a **principled identity model** to hit it — candidates: a
  path-anchored match (compare the specific deliverable path consistently rather
  than loose tokens), per-condition identity breadth (broad for suppressors,
  narrow for the trigger), or token weighting that de-rates directory/common
  stems. Then either land the chosen model or accept the current equilibrium and
  close this as documented.
- **Scope note:** the detector is deliberately conservative ("when in doubt,
  don't flag"), so this is a **precision-hardening** decision, not a hair-on-fire
  bug — the shipped equilibrium is defensible. Distinct from #109 (footprint
  over-work / dead fields) and #110 (`claim-vs-delivery` FP rate), though all
  three touch the same self-consistency detectors.
- **Effort:** small (the decision); the model that follows is a separate
  `plan-tool` item. **Approach:** decision first (`direct` write-up), then
  `plan-tool` if a model change is chosen.
- **Dependencies:** none — #100 shipped the detector.
- **Origin:** 2026-07-09 — five-round high-effort workflow review of the
  `plan-self-consistency-gate` step commits; rounds 2–5 each fixed one direction
  of the tension and re-surfaced the other, converging only at "no CONFIRMED
  finding, accepted PLAUSIBLE tradeoffs" (the `stop-patching-file-a-backlog-entry`
  rule for a non-converging region).

**#110 — Measure `claim-vs-delivery` false-positive rate (incl. fuzzy near-miss misses) and decide promotion to blocking**

- **What:** `detect_claim_vs_delivery` (shipped in #100) is deliberately
  **advisory** on `smell_recs` — it never flips rc — until its false-positive
  rate is measured on real plans; a follow-up then decides whether to promote it
  onto the blocking `self_consistency_recs` bucket. This entry rescues that
  follow-up from #100's now-archiving `## Deferred` section and pins a concrete
  data point: the fuzzy match `_claim_delivered` uses `SequenceMatcher.ratio()
  >= _NEAR_MISS_RATIO` (0.85) over whole tokens, so a claim clearly delivered by
  a related-but-differently-named symbol misses (`parse_plan` vs a declared
  `parser` scores ~0.75) and is reported as undelivered — advisory noise today,
  but exactly the kind of FP that must be characterized (and the threshold /
  tokenization tuned) before any promotion.
- **Output of investigation:** run the detector across the repo's real plans,
  bucket the findings into true/false positives, and either (a) "precision is
  adequate" → spawn a Bucket A/D item to promote it to the gate-read bucket, or
  (b) "FP rate too high" → tune `_NEAR_MISS_RATIO` / token normalization (or keep
  it advisory) with the measured rate as justification.
- **Where to promote it, once precision is adequate:** both `create --iterate`'s
  own deterministic loop and the completeness-audit smell layer — the former
  doesn't run this check at all today, which is why a seam can surface rounds
  later in the audit instead of at `create` time — plus the inverse direction
  (a step whose headline intent maps to no acceptance criterion), which the
  current detector checks neither way.
- **Risks / fallout:** the detector's advisory status is a **settled
  decision, not an oversight** — `detect_claim_vs_delivery`'s docstring pins
  "stays advisory" on fuzzy-matching false positives (this entry's own
  `_NEAR_MISS_RATIO` data point above is exactly that risk). Promotion must
  not adopt the raw fuzzy `SequenceMatcher` matcher wholesale — measured
  precision or an exact-match-only subset first. A false positive on a
  criterion legitimately delivered by a non-step mechanism gets an explicit
  carve plus a test, never a severity retreat.
- **Scope contract** (carried forward from the folded-in #267, 2026-08-13 —
  do not re-widen without updating this fence):
  - **Outcome:** the measurement decides whether `claim-vs-delivery`
    promotes; if it does, promotion lands in both `create --iterate`'s
    deterministic loop and the completeness-audit smell layer, plus the
    inverse (intent with no criterion) direction.
  - **In scope:** `plan_tool/review.py`'s `detect_claim_vs_delivery` and its
    deterministic-collector wiring; `create`'s convergence severity mapping;
    the plan-side `smell_recs`→`self_consistency_recs` routing move (below);
    tests.
  - **Out of scope / Non-goals:** any Claude-judged check on claim quality;
    the completeness-audit conceptual bar (`is_blocking_finding`); step
    schema changes (that is #268's carrier decision, not this entry's);
    exit-code conventions.
  - **Allowed behavior changes:** `create --iterate` may iterate (or stop
    with a blocking finding) on a criterion↔step mismatch it previously
    converged past at INFO.
  - **Allowed reorganization:** the `smell_recs`→`self_consistency_recs`
    routing move `#100`'s Architecture already describes for
    `suppression-shape`; no other reorganization.
  - **Verification:** the measurement's bucketed true/false-positive counts;
    once promoted, unit tests for both directions including the
    previously-INFO-would-have-converged case now blocking, and one carve
    asserted as a deliberate exemption.
  - **Stop / defer:** newly noticed criterion patterns needing judgment (not
    delivery tracing) go to the backlog, not into this check.
- **Effort:** small (the measurement); the promotion/tuning that follows is a
  separate item, medium once create-loop wiring and the inverse check are
  included. **Approach:** `direct` for the measurement; if promotion is
  chosen, `plan-tool` for the wiring — it now spans two integration points
  (`create --iterate`'s loop and the completeness-audit smell layer) plus
  the open precision decision above, which is exactly the multi-module/
  open-design-choice shape BACKLOG.md's own direct-vs-plan-tool heuristic
  routes to a plan. This **supersedes** the folded-in #267's "direct, with
  the hand convergence loop" note (2026-08-13) — reconciled rather than
  left standing beside it.
- **Dependencies:** none — #100 shipped the detector.
- **Origin:** 2026-07-09 — #100's `## Deferred` ("Promoting `claim-vs-delivery`
  to blocking … until its false-positive rate is measured") plus the high-effort
  workflow review's fuzzy near-miss finding on `review.py:2449`.

**#87 — [Investigation] Harden the test-authoring gate against a dirty working tree (don't depend on `--commit` discipline)**

- **What:** The test-authoring gate isolates a step's test coverage as the
  *post-call git-changed delta against a pre-call baseline* (`launcher.py`). On a
  multi-step `run` **without `--commit`**, an earlier step's edits to a shared
  test file (e.g. `tests/test_split_criteria.py`) stay dirty, so a later step's
  additions to that same file fall **inside** the baseline, get masked out of the
  delta, and the gate **wrongly blocks advancement** even though the step did
  author a test. CLAUDE.md now documents this as the gate's known limit and
  mandates `--commit` on multi-step `run` to avoid it.
- **Observed:** `run 2-visualize-split-criteria --all` (run **without**
  `--commit`) halted at step 3 and again at step 5 with "no test file
  created/modified," though both steps *did* modify `tests/test_split_criteria.py`
  — the deltas were masked by the still-dirty tree from the prior step. The steps
  were cleared with `enforce_test_authoring: false`; the correct fix is to run
  `--all --commit` so each green step commits and the next starts clean. (An
  earlier note here misdiagnosed this as a `granularity-merge` / step-2-absorbs-
  step-3 over-delivery — corrected: the tests were never authored by the prior
  step; they were the same step's edits, masked by the dirty baseline.)
- **Two more causes seen 2026-10-06 (`roadmap-versioned-from-birth`, ran *with*
  `--commit`):** (1) a retry whose tests were already in the tree from an earlier
  attempt made no edits, so the delta was empty and the gate failed it (step 3,
  attempt 3); `enforce_test_authoring: false` was then added by hand to steps 3
  through 9 so a retry could advance. (2) The model committed its own work inside
  the call (a 49-file commit, step 10), so the working-tree delta was empty, the
  gate reported "no test file modified", and the suite gate never ran. Candidate
  fixes for the open question below: pass when the step's declared test files
  already differ from the last green commit, and compute the delta from the
  pre-call HEAD to the post-call tree *and* HEAD (or state in the run prompt that
  the model must not commit; a prompt rule alone is not a guarantee). The gate's
  observable stays binary; test quality is not graded. Exemptions added by hand
  persist in plan frontmatter after the run. Related: #455.
- **Cause (1) again, 2026-10-08 (`roadmap-stack-propagation`):**
  - Two times, a re-run after a hand fix of the step's own failing test changed
    nothing, and the gate reported "no test file ... created or modified during
    the call", although the step's tests were in the tree: step 1
    (`.tmp/roadmap-stack-propagation.run-step1-fix.log`) and step 2
    (`run-steps3-4.log`, 24 s, 2.0 KB reply).
  - Separately, the step-1 retry ran without `--commit` (refused on the dirty
    tree, `run-step1-retry.log`). Its baseline already held the failed
    attempt's test edits, which is the original masking cause
    (`run-step1-retry2.log`).
  - `run --step N --accept` (shipped 2026-10-10) gives the hand-fix case a route
    that needs no re-run. Since 2026-10-13 a no-edit re-run of a step that
    declares files is reported as "no edits applied" before this gate runs, so
    whether the gate should pass a no-edit retry whose tests already differ from
    the last green commit stays this entry's open question only for steps that
    declare no files.
- **Cause (2) again, 2026-10-15 (`sibling-planned-input-paths`):** steps 1
  and 2 start clean under `run --all --commit`, author regression tests, and
  commit them inside the backend call (`373997be9`, `bf44003f3`). Both return
  with an empty working-tree test delta and fail the authorship gate. Inspection,
  mutation verification and independent full-suite runs establish authored
  coverage; `run --step N --accept --commit` runs the suite again and advances
  each step. No gate exemption is needed. This reproduces the committed-delta
  case independently of the dirty-baseline case; keep both in any remedy matrix.
- **Open question:** should the gate be made robust to a dirty baseline
  (e.g. snapshot each step's pre-call state per-file and diff against that, rather
  than the raw working tree) so correctness doesn't depend on operator `--commit`
  discipline — or is the documented `--commit` mandate a sufficient floor?
- **Effort:** small (decision) → medium (if the gate baseline is reworked).
- **Approach:** decision first (`direct` write-up), then `plan-tool` if a gate
  change follows.
- **Dependencies:** the `--commit`-on-multi-step-`run` mandate in CLAUDE.md is the
  current workaround this would supersede.
- **Origin:** 2026-07-04 — surfaced running visualize-split-criteria without
  `--commit`; root cause corrected 2026-07-05 after the `--commit` known-limit
  rule landed upstream.

**#71 — [Decision] Define the `detail --reconcile` refusal-token shape (enforce vs. record)**

- **Principle:** `converge-on-correct-plan` — the T2 band (P1/P3): a refusal token the apply layer can check.
- **What:** Decide the shape of a machine-readable *refusal* marker for
  `detail --reconcile`'s plan-side audit — the token Claude emits when it
  declines an edit because it would `blocked`/narrow scope/soften an
  acceptance criterion. Today those three refusals are prose-only policy in
  `prompts/detail-reconcile.md`, with no token the apply layer can check.
- **Why it's a decision, not a build:** run-reconcile's `## Redirect` is a
  *reroute* signal ("this code finding's fix belongs in the plan" — code→plan).
  `detail --reconcile` is already the plan-side audit emitting plan edits, so
  there's no analogous reroute; the needed signal is a *refusal* ("declining
  this edit — it would narrow scope"), a different shape. Porting `## Redirect`
  mechanically doesn't fit, so the shape has to be designed before anything is
  built.
- **Open questions to resolve:**
  - **Token shape:** a `## Refusal` block mirroring `## Redirect`'s parse path?
    A per-finding verdict token (like apply's `BLOCKED` / `NOT-APPLICABLE`)? A
    reason-coded marker (`scope-narrowing` / `criterion-softening` / `blocked`)?
  - **Enforce vs. record:** does the apply layer *enforce* the refusal
    (reject/halt the edit, like a guard) or merely *record* it (annotate the
    finding, surface it, no action)? The prose policy works correctly today,
    so enforcement is the riskier, higher-cost path; recording is the cheaper
    floor.
  - **Parser seam:** where it threads through `review.py` (alongside `Redirect`
    / `parse_redirect_block`) and the `Recommendation` / `Annotation` model.
- **Output:** a short design note (chosen token shape + enforce-vs-record
  stance + parser seam) that converts the decision into a buildable
  `plan-tool` item.
- **Effort:** small (the decision + write-up); the build that follows is the
  separate MINOR.
- **Approach:** decision first (`direct` write-up), then `plan-tool` to build
  the chosen shape.
- **Dependencies:** none.
- **Origin:** 2026-06-22 — draining the bug backlog surfaced the
  refusal-signal work as a forward-looking design decision, not a correctness
  bug.

**#36 — Investigate whether `create`-generated per-plan `lessons.md` adds value**

- **Principle:** `untriaged` — an investigation that may close with no action.
- **What:** `plan-tool create` writes a `lessons.md` next to the plan
  (e.g., `docs/implementation-plans/plan-details/app-parameter-standardization/lessons.md`).
  It isn't clear whether these files surface enough signal to justify
  their existence, or whether they're noise that competes with the
  developer [lessons record](docs/explanations/lessons-learned.md).
- **Output of investigation:**
  - "Per-plan lessons.md adds value" → close; possibly tighten its
    prompt.
  - "Per-plan lessons.md is noise" → spawn a Bucket A item to remove
    the auto-write or gate it behind a flag.
- **Effort:** small. Have claude review several existing per-plan
  lessons files, compare against the developer lessons record,
  judge overlap and unique signal.
- **Approach:** direct. Same shape as #19 — investigation, not
  implementation.

**#113 — [Investigation] The budget-limited "likely under-decomposed" verdict false-positives on detailed-but-sound plans (conflates structural churn with prose-treadmill)**

- **What:** `_classify_budget_limited_stop` (`plan_tool/review.py:5611`, the
  message at `:5681`) decides why a conceptual audit hit its pass cap by keying
  **only on the per-pass new-finding count series** (tapering vs flat/cliff). On
  a flat/non-tapering tail it asserts *"the plan is likely under-decomposed; run
  `plan-tool convergence`"*. But a **non-tapering count has (at least) two
  distinct causes** the heuristic can't tell apart: (a) a genuinely
  under-decomposed plan (structural findings that a re-split would resolve), and
  (b) the tool's own documented **body-hash treadmill** — a subjective audit
  finding ever-finer *prose-precision* nuances in a large, necessarily-detailed
  plan whose **decomposition is sound** (the same audit validates the step
  structure/deps/purity every pass). Case (b) is a false positive: the verdict
  tells the operator to re-decompose a plan that does not need it.
- **Observed:** authoring `rate-limit-loop-extraction`, a 4-step
  refactor. Four hand-edit convergence rounds each fixed real *prose-precision*
  gaps (an 11-seam boundary gives an LLM auditor unbounded surface); the
  count series oscillated (2→3→2, then 2→1→1) and the tool repeatedly warned
  "likely under-decomposed" even though every pass validated the decomposition
  as sound. The operator correctly read it as repeated audit churn, not
  under-decomposition.
- **Why:** a confident-but-often-wrong diagnosis erodes trust in the audit's
  headline signal and can push an operator to wastefully re-decompose a sound
  plan (the opposite of the mission's *always surface the more-correct plan*).
- **Direction (needs a disambiguating signal — the investigation):** teach the
  classifier to distinguish the two causes before asserting a cause. Candidate
  signals it does **not** consult today: whether the recurring findings are
  **structural** (`granularity` / dependency / step-boundary sources) vs
  **prose-precision** (body-completeness / conceptual-wording), whether the
  decomposition is being **validated sound** each pass, and cross-run region
  recurrence (the `convergence` diagnostic already reasons over region trends —
  reuse it rather than a raw count series). Grounds naturally in
  `plan-tool telemetry` (tune the threshold + the cause split from the
  distribution).
- **Cheap first slice (bug-flavored):** independent of the full redesign, soften
  the `:5681` wording to present **both** hypotheses ("either the plan is
  under-decomposed, or the audit is finding prose-precision nuances on a
  sound-but-detailed plan — check whether the recurring findings are structural
  before re-decomposing") rather than asserting one. Low cost, removes the
  actively-misleading claim while the disambiguating signal is designed.
- **Effort:** medium (the disambiguation) / small (the wording slice).
  **Approach:** `decision first` — decide the disambiguating signal before
  wiring; the wording slice is `direct` and can land immediately.
- **Origin:** 2026-07-09 — surfaced while driving the `rate-limit-loop-extraction`
  detail bundle to convergence; the heuristic fired on every round of a
  plan its own audit validated as well-decomposed.

**#129 — Deferred: deterministic program-scale decomposition observations**

- **What remains:** three separately selectable observations: a declared
  step-count band, remediation-chain depth from explicit seed provenance, and
  footprint-overlap plan counts. Each may report a bounded fact to an operator.
- **Decision (2026-08-19): retire the re-think-altitude verdict.** Counts,
  ancestry, and overlap cannot establish that a plan is conceptually at the
  wrong altitude. The retired region-trending layer already produced that false
  verdict from different metrics.
- **Trigger:** name the operator decision and the particular observation that
  will inform it. Do not build a coupled monitoring product or a generic
  decomposition advisory in advance.
- **Out of scope:** a wrong-altitude, re-think, split, scope-out, re-seed,
  gate, exit-code, or automatic action inferred from these measurements. An
  explicit human conclusion belongs to `plan-tool decide`, not a metric verdict.
- **Status:** deferred pending a named decision consumer for one observation.

**#141 — Decide how the fixed 4h jira story-size floor relates to the configurable `--max-hours` ceiling**

- **What:** The jira story-size soft floor (`_STORY_SIZE_SOFT_FLOOR_HOURS = 4`
  in `plan_tool/jira.py`, feeding `lint_story_size` and the `prompts/jira.md`
  decomposition-floor rule) is a **fixed constant**, while `--max-hours` (the
  advisory *ceiling* target, default 8) is **user-configurable with no lower
  bound** (`plan_tool/cli/jira_cmd.py`). When a user sets `--max-hours` below 4
  (a ceiling below the floor — pathological but permitted), the two soft signals
  overlap: the prompt tells Claude the target wins (so it emits sub-4h stories),
  but `lint_story_size` still advisory-warns every one of them as "below the 4h
  floor." Both surfaces are advisory-only (exit 0, never block a write), so this
  is noise, not a correctness break — but the noise fires on the whole export.
- **Why deferred (not patched):** two high-effort review rounds churned on this
  exact region. A first attempt clamped the *prompt* floor to `min(4, max_hours)`
  but left the *lint* floor fixed, which made the two diverge (worse). Making
  them agree requires either (a) threading `max_hours` into `lint_story_size` /
  `partition_lint_findings` / `_emit_story_warnings` — but the `jira --lint`
  path lints an existing artifact with **no `--max-hours` context** (it would
  default to 8, so the surfaces still disagree between `export` and `--lint`), or
  (b) forbidding / clamping `--max-hours` below the floor (changes `--max-hours`
  semantics), or (c) accepting the overlap as a pathological-config non-issue and
  documenting it. The current shipped state is a **fixed 4h floor everywhere**
  (lint + prompt), with the prompt prose deferring to a lower `--max-hours`
  target so the *prompt* is self-consistent; only the lint-vs-prompt overlap at
  `--max-hours < 4` remains.
- **Effort:** small (option c: one doc line + maybe a `--max-hours < 4` warning)
  → small–medium (option a/b: signature threading or arg validation). **Approach:**
  `direct` — narrow, single-surface, no plan needed once the option is chosen.
- **Quality/accuracy lens:** low — advisory-only noise reachable only by a
  ceiling-below-floor misconfiguration; the default (`--max-hours 8`) is unaffected.
- **Origin:** 2026-07-16 — surfaced by the round-2 code review of the story-size
  floor feature (the fixed-floor-vs-configurable-ceiling tension), deferred here
  rather than patched a third time per the convergence escape hatch.

**#210 — Decide whether the per-step purity Claude pass earns its cost: it has never reported a finding, and 87.5% of its calls never return**

- **What:** the `completeness-audit` phase-1 per-step MIXED-STEP purity pass
  (`purity_scan` phase) spends one Claude call per step per audit. Decide,
  on measurement, whether to keep it, invert its default to off, or cut it
  — the same measure-then-decide treatment that retired the
  per-`change_type` test-ordering contract (CLAUDE.md § "Withdrawn").
- **Measurement, 2026-07-31:** across 90 saved completeness reports, no
  `granularity-split`/`detail-purity` finding anchor appears — not one. But
  the zero can't be read as "the corpus is clean": `purity_scan` events
  carried rc=124 (timeout) in 14 of 16 calls (87.5%), and a timed-out scan
  and a clean one render byte-identical downstream (both `[]`) — most of
  the corpus was never actually scanned. The pass was not evaluable before
  any keep/cut call.
- **Landed so far:** (1) **default inverted, 2026-07-31** — `--purity` is
  now opt-in. (2) **loud failure + reachable budget, 2026-08-03/04**
  (`a41a77db`, `b173b51b`) — a timed-out scan now reports honestly instead
  of rendering as a clean `[]`, with per-pass timeout/budget settings. A
  plan that duplicated this scope was never executed and is marked
  `completed` retroactively. (3) **passive observation only, settled
  2026-08-20 (user-confirmed)** — do not schedule a dedicated audit to
  measure this; record an outcome only when another independently
  justified audit invokes `--purity`.
- **Still open:** keep it opt-in, promote it back to default, or cut it —
  decided from those observed outcomes. If it still fires zero after it
  genuinely runs, the withdrawn-contract precedent says cut it.
- **What's not at stake:** MIXED-STEP detection as a concept —
  `granularity.py`'s split/merge detectors never shell out and
  `detail --split` has its own actuator; only the Claude increment on top
  is in question.
- **Approach:** `passive observation` — no dedicated measurement; later
  keep/cut uses outcomes from independently justified `--purity` audits.
- **Origin:** 2026-07-31, after a completeness tail timed out under
  `--purity` and the yield/cost census above was run to answer whether the
  check was worth it.
- **Status:** passive observation only, settled 2026-08-20 (user-confirmed).

**#229 — Have detail prompts reference plan fences instead of copying them**

- **What:** the detail prompt currently encourages step files to repeat the
  plan's scope fence, including `## Out of scope` and allowed-behavior clauses.
  Those copies become stale when the plan changes and generated multiple
  unrelated conceptual findings. Update the prompt and focused tests so a detail
  references the authoritative plan section rather than reproducing it.
- **Outcome:** generated detail preserves the applicable scope boundary without
  verbatim plan-fence copies that can drift across the bundle.
- **In scope:** the detail prompt/template, its rendering or fixture tests, and
  operator-facing documentation if the generated wording requires it.
- **Out of scope / Non-goals:** a repository-wide restatement index; changing
  the plan's scope contract; regenerating existing detail bundles; and causal
  provenance features (retired #231).
- **Effort:** small. **Approach:** direct — one prompt-output contract with
  bounded fixture coverage.
- **Quality:** `grounding` — one authoritative fence, fewer stale copies.
- **Origin:** completed detail-bundle convergence investigation, 2026-08-04.
- **Status:** not started.

**#212 — `apply_finding` rewrites a step but never clears its `intent`, leaving an authoritative stale why**

- **What:** `Step.intent` has shipped (plan `2-intent-scope-fence.md`), and
  `plan_tool/launcher.py:apply_finding` rewrites a step's title, files, and
  acceptance criteria from an audit finding while leaving `intent` untouched.
  The result is a one-line why that no longer describes the step but still
  renders into the `detail`, `run`, and conceptual-audit prompts as
  authoritative input — the "a stale intent is worse than an absent one" hazard
  that plan's Risks section names, arriving through a verb that plan does not
  cover.
- **Why it is filed rather than folded in:** `2-intent-scope-fence.md` scopes
  propagation to the four **structural** verbs (`split`, `merge`, `scope-out`,
  `reground`). `apply_finding` is not one of them, and that plan's
  `## Audit guardrails` fences propagation past those four out **by
  construction**. Surfaced by its own round-1 conceptual audit, which correctly
  tagged it `[out-of-scope-deferred]` and cited the guardrail as its reason for
  not expanding the plan.
- **Dependencies:** none — `2-intent-scope-fence.md` shipped the field, so the
  one blocker this entry had is clear.
- **Effort:** small — one clearing rule plus a test, if the answer is "clear
  it". Deciding *whether* a rewritten step should keep, clear, or re-derive its
  intent is the actual work.
- **Scope contract:**
  - **Outcome:** a step rewritten by `apply_finding` never carries an intent
    that contradicts it.
  - **In scope:** `apply_finding`'s step-rewrite path and its tests.
  - **Out of scope / Non-goals:** re-deriving a new intent with a Claude call;
    any intent-vs-work agreement check (permanently refused — see CLAUDE.md
    § "Validating a semantic property you cannot observe", "The two intent
    reversals"); the four structural verbs, which `2-intent-scope-fence.md`
    already owns.
  - **Allowed behavior changes:** one field cleared on one existing path.
  - **Allowed reorganization:** none.
  - **Verification:** a step carrying an intent, rewritten by `apply_finding`,
    ends with no stale intent; a step with no intent is byte-identical to today.
  - **Stop / defer:** if clearing proves wrong for some finding classes, record
    which and defer the per-class rule rather than widening.
- **Approach:** `direct` — one path, one rule, one test.
- **Quality:** `grounding` — keeps an authoritative input from going stale.
- **Origin:** 2026-08-01, round-1 conceptual audit of `2-intent-scope-fence.md`.
- **Status:** not started; unblocked (that plan's step 1 landed the field).

**#228 — A deterministic enumeration/count drift check across a plan and its detail bundle**

- **What:** a no-Claude check that flags a *count or enumeration* in a plan's
  prose that some other part of the same plan bundle falsifies — "three
  failure kinds", "all three traps", "15 new `VIOLATION_*` constants", "four
  collections", "meet all six". It reads only the plan body and its detail
  files; it proposes no edit and flips no exit code.
- **Why — measured, not conjectured.** Driving
  `roadmap-02-feedback-channel` through five completeness rounds on
  2026-08-04 gave 25 → 12 → 7 → 8 → 10 findings, and rounds 3–5 were each
  **dominated by findings seeded by the previous round's own applications**
  (round 5: ~8 of 10, every traced subject introduced by commits `ff747c5c`,
  `70da4943`, `5881383f`, `c2fdab03`). Classifying the re-seeds showed one
  shape carrying nearly all of them: **a count or enumeration restated in
  several places, where an edit satisfied one instance and left the others
  false.** Concretely — adding a fourth failure kind falsified a three-kind
  enumeration in `CLAUDE.md`, `integrations/claude/SKILL.md`,
  `ROADMAP_FORMAT.md`, `RUNBOOK.md`, `USE_CASES.md`, and a docstring, and it
  was missed in two consecutive rounds; retiring one gate rule left a
  `15`-vs-`14` constant budget and three dangling references; adding a fourth
  Risk left a criterion reading "all three traps"; and stating a collection
  override as "six" was wrong for the stage whose wrapped prompt declares
  three. This is the vocabulary half of the sweep rule in `CLAUDE.md`
  § "Documentation is forward-looking", and it is the half that keeps being
  skipped — because a *number* is not a greppable identifier and the sweep
  discipline is aimed at identifiers.
- **Why a deterministic check and not more audit rounds.** The Claude audit
  *does* find these — one instance at a time, at one round's latency and cost
  each, and each fix seeds the next round's instance. That is the loop this
  entry exists to cut. Counting is exactly what a deterministic pass is good
  at and a sampled prose audit is bad at.
- **Effort:** medium. The hard part is precision, not detection: number-words
  and digits beside a noun are cheap to find and mostly benign, so this
  earns its place only if it fires on drift rather than on prose. Start from
  the observed corpus above, and treat a high false-positive rate as a kill
  signal per `CLAUDE.md` § "Validating a semantic property you cannot
  observe" rule 5 — the honest first cut may be **only** the cases where the
  same noun phrase carries two different counts inside one bundle, which is
  a fact about state rather than a judgment about prose.
- **Risks:** the advisory-noise trap that killed the `change_type`
  test-ordering matcher. Ship it as an advisory finding with a named
  instance pair ("`three failure kinds` here vs `four` there"), never a gate.
- **Dependencies:** none. **Related:** `CLAUDE.md`'s four apply-checks
  (this is check 2, restatement, made mechanical), and the shipped
  severity-aware stopping rule this would let converge sooner.
- **Scope contract:**
  - **Outcome:** a plan bundle whose own prose disagrees with itself about a
    count or enumeration says so, deterministically, before execution.
  - **In scope:** a read-only check over the plan body + detail files; an
    advisory finding source; tests over the observed corpus.
  - **Out of scope / Non-goals:** checking a count against *code* (that is
    reconcile's direction); auto-applying any fix; a gate or exit-code flip;
    natural-language number agreement beyond same-noun-two-counts; extending
    it to `BACKLOG.md` or the reference docs in the first cut.
  - **Allowed behavior changes:** one new advisory finding source in the
    completeness report. No stdout change elsewhere, no exit-code change.
  - **Verification:** it fires on the four `roadmap-02-feedback-channel`
    instances above at the commits that introduced them, and does not fire
    on the plan corpus at HEAD.
  - **Stop / defer:** if the false-positive rate on the existing plan corpus
    exceeds roughly one in five, kill it rather than tune it.
- **Approach:** `direct` — a read-only leaf plus a finding source.
- **Quality:** `grounding` — keeps a plan's own statements consistent.
- **Origin:** 2026-08-04, five-round completeness convergence on
  `roadmap-02-feedback-channel`; filed under the escape hatch rather than
  opening a sixth round.
- **The class is not confined to authored prose — a model produces it too**
  (observed 2026-08-04, same day, in a real `roadmap` revision). The spelling
  run's `proposed_response` said *"the four other reader-facing names in the
  file"* and then listed **eleven**. Same defect, same shape, different
  producer: a count stated beside the enumeration it contradicts. This does
  **not** widen the first cut — a model reply is not a plan bundle, and the
  `Out of scope` fence above still holds — but it is evidence that the
  detector's *value* is larger than the corpus it is scoped to, and a reason
  to keep the check's core reusable rather than welded to the plan reader.
- **Status:** not started.

**#213 — Conceptual-audit lens: a plan proposing a check must name the binary observable it asserts**

- **What:** add one lens to `plan_tool/prompts/plan-audit.md` that fires **only
  when the plan under audit proposes a check, gate, finding, or enforcement**,
  and asks two questions:
  1. Does the plan **name the mechanically observable fact** the check asserts?
  2. Does any proposed check **compare two prose artifacts for agreement**
     (a doc against a doc, a field against a section, a claim against a diff)?

  Advisory finding in the existing conceptual channel. No gate, no exit-code
  flip, not apply-eligible — the same posture as the granularity advisor, which
  is deliberately kept out of `APPLY_ELIGIBLE_SOURCES`.
- **Why:** question 2 alone would have caught both known instances of the class
  in CLAUDE.md § "Validating a semantic property you cannot observe" — the
  withdrawn test-ordering contract (a matcher over `## Tests` prose) and
  `2-intent-scope-fence.md` (intent-vs-`## Why`). Question 1 is the positive
  form of the rule the section states: a validation feature with no nameable
  observable has no bounded scope, so it grows until someone carves it back.
  The audit is the cheapest place to ask: the judge already reads the plan
  body, so marginal cost is ~0 and no new Claude call is spent.
- **Evidence base — read honestly:** two instances, 2026-07-30 and 2026-08-01.
  That is enough to justify an advisory lens and **not** enough to justify a
  deterministic checker (see Non-goals). If the lens itself proves noisy,
  CLAUDE.md rule 5 applies to it too: kill, don't tune.
- **Dependencies:** none.
- **Effort:** small — prompt prose plus tests over stubbed audit responses.
- **Scope contract:**
  - **Outcome:** a plan proposing a check whose observable is unnamed, or which
    compares two prose artifacts, surfaces one advisory finding.
  - **In scope:** `plan_tool/prompts/plan-audit.md` and its tests.
  - **Out of scope / Non-goals:** a **deterministic phrase matcher** over seed
    or plan prose — refused, it is `collect_change_type_test_order_findings`
    reborn and would fire on any plan containing the word "validate"; the same
    lens in `create`, `detail-quality`, or the reconcile prompts (one consumer
    only — CLAUDE.md rule 4); any gate, exit-code flip, or apply-eligibility;
    judging whether a *named* observable is a good one.
  - **Allowed behavior changes:** one new advisory finding class on one prompt.
  - **Allowed reorganization:** none.
  - **Verification:** a plan proposing a prose-vs-prose agreement check draws
    the finding; a plan proposing no check at all draws nothing; the finding
    never flips an exit code.
  - **Stop / defer:** if the lens fires on plans that are fine, remove it
    rather than narrowing it repeatedly.
- **Approach:** `direct` — one prompt lens plus tests; no decomposition needed.
- **Quality:** `audit-coverage` — gives the conceptual audit a lens for a
  failure class that has twice cost real work and that no current check sees.
- **Origin:** 2026-08-01, generalizing the withdrawn test-ordering contract and
  the intent scope fence into a class.
- **Status:** not started.

**#320 — Check that a concept's declared inputs and another concept's declared outputs actually align**

- **What:** for a plan's (or roadmap's) set of concepts — components, entities,
  steps — check whether what one concept says it needs (its inputs) and what
  another concept says it produces or returns (its outputs) actually describe
  the same shape. Distinct from an earlier, retired proposal (#222, an
  external ODCS-shaped published-data-product contract standard — see
  `docs/history/backlog-decisions.md`): this is internal — data/interface
  alignment *between concepts already inside one plan or roadmap*, not a
  contract with an outside consumer.
- **Why:** the domain model that shipped 2026-08-02 (`EntityRow.fields` +
  `check_entity_fields`) states what an entity *holds*, but deliberately
  carries **no producer/consumer framing** —
  nothing currently checks whether a concept's stated needs match what its
  supposed source actually delivers. A misalignment here is a real class of
  bug: a step assumes a shape another step doesn't actually produce, and
  nothing catches it until execution (or later). Degree-of-alignment findings
  would inform updates, fixes, and audits directly — the same kind of
  deterministic, structural signal #228 (enumeration/count drift) and #207
  (naming discontinuity) already use to cut audit churn.
- **Open design questions — decision-first, do not build without resolving
  these:** does this apply at the `roadmap` level (`EntityRow`-to-`EntityRow`
  across components) or at the `plan`/step level (step N's declared
  `files`/`creates` output vs. step M's stated input need), or both; what
  "alignment" means concretely (exact field-name match, or a looser
  shape/type compatibility); and whether this is a completeness-audit-style
  check (plan-centric, no code needed) or a reconcile-style check (grounded
  against real code), per this file's own completeness-vs-reconcile split.
- **Effort:** unknown until the design questions above are resolved.
- **Approach:** `direct` — investigation/decision first.
- **Origin:** 2026-08-27, raised by the user during the backlog-tightening
  review as a refinement of #222 — an internal interface-alignment check
  between plan/roadmap concepts, not an external data-contract standard.
- **Status:** not started; needs a design pass before it's buildable.

**#310 — Decide whether `roadmap_reader_guard` should cover the recorded-brief path**

- **What:** `roadmap_reader_guard` / `roadmap_writer_guard` flock only
  `.roadmap-<slug>.writer.lock`, which coordinates against another roadmap
  *writer*. The recorded brief text (`read_brief_text`, consumed by
  `capture_roadmap_impact_snapshot` via `_capture_recorded_brief_digests`) is
  read from a `repo_root`-relative path that lives outside `roadmap_dir` and
  is never covered by that lock. Nothing currently defends against the brief
  file being mutated by something other than a roadmap writer while a reader
  guard is held.
- **Why not fixed on the spot:** surfaced by `/code-review` while landing
  BACKLOG #309's `snapshot_cache` addition to `current_impact_analysis`
  (2026-08-24) — the review's framing was that caching widens the staleness
  window from "per-record read time" to "the first record's read time reused
  for the rest of the call." That framing is contestable rather than settled:
  giving every record in one CLI view call a **consistent** snapshot of
  roadmap state as of the start of the call is arguably the *more* correct
  behavior (closer to snapshot-isolation semantics) than re-reading fresh
  per record, which could already show different records different states
  within one logical view call. Either resolution — widen the lock, or decide
  the current guard's scope (roadmap-writer coordination, not arbitrary
  filesystem mutation of every consumed source) is intentional and sufficient
  — is a real decision, not a proportional fix to make inside a residual
  code-quality cleanup entry.
- **Effort:** small to investigate (read `roadmap_reader_guard` and every
  brief-consuming call site, decide the intended contract); a fix, if one is
  warranted, is a separate follow-up sized by that decision.
- **Approach:** `direct` (investigation) — decide the contract, document it
  or extend the lock; no plan-tool plan needed to reach a decision.
- **Dependencies:** none.
- **Origin:** 2026-08-24, `/code-review 917fecc4..HEAD high` on BACKLOG
  #309's landed fixes.
- **Status:** not started.

**#311 — Two remaining pre-existing efficiency gaps noticed while landing BACKLOG #309's caching fix**

- **What:** a second `/code-review 917fecc4..HEAD high` round (2026-08-24,
  verifying #309's round-1 fixes) surfaced three inefficiencies, none
  introduced by #309's own diff and none addressed by it — incidentally
  discovered while reading the surrounding code, not caused by anything #309
  changed. Item 1 is done; items 2 and 3 remain and turned out larger than
  first scoped:
  1. **Done (`4ab38889`):** `_load_requested_receipt`
     (`roadmap_impact_run.py`) called `scan_evidence`, which read the full
     bytes of *every* file in the escalations directory just to find the one
     record matching `requested_final` — an O(records in directory) read to
     answer an O(1) lookup, called once per impact-analysis record
     inspected. Switched to `read_evidence_final`, the existing targeted-read
     primitive `roadmap_structural_revision.py` already uses for the same
     purpose; preserved the exact `"receipt-missing"` vs `"receipt-
     unreadable"` verdict distinction the run log depends on, with a direct
     test pinning both outcomes (`test_load_requested_receipt_
     distinguishes_missing_from_unreadable`).
  2. **`build_impact_analysis`** re-derives `_snapshot_evidence` (full
     canonicalization + SHA-256 hashing of all 4 stage artifacts) every time
     it runs, even when its `RoadmapImpactSnapshot` argument came from
     #309's own `snapshot_cache` cache hit and was already validated at
     capture time. **Confirmed load-bearing, not dead work**: of
     `build_impact_analysis`'s 3 call sites
     (`roadmap_impact_run.py:299`, `roadmap_impact_run.py:578`,
     `roadmap_structural_revision.py:173`), only the second ever receives a
     cached snapshot — the other two always pass a freshly captured one this
     revalidation is the only thing that checks. A safe fix needs a way to
     tell "freshly captured, unvalidated by this path" apart from "cache hit,
     already validated at capture time" — `RoadmapImpactSnapshot` carries no
     such provenance today, so this is a real design question, not a
     one-line skip.
  3. **`load_pending_generation`** (`roadmap_source_identity.py:363`) fully
     JSON-parses the journal and base64-decodes every member's `old`/`new`
     byte payload, even when the caller this session touched
     (`_pending_generation_touches_baseline`) reads solely
     `member.relative_path`. **Not a quick fix**: `load_pending_generation`
     has 4 other call sites, at least one of which
     (`recover_roadmap_publication`, `roadmap_revision_publish.py:315`)
     genuinely needs the full decoded `old_bytes`/`new_bytes` to compare
     against on-disk state for recovery. A safe fix needs either lazy
     per-member decoding (a real change to `GenerationMember`'s shape) or a
     second targeted reader — and a second reader risks re-deriving the
     JSON-envelope-parsing logic `load_pending_generation` already owns,
     which is exactly the duplication-drift class this whole line of work
     exists to stop.
- **Why not fixed on the spot:** each is a real but separate concern from
  what #309 was landing (a residual code-quality cleanup on a different,
  already-closed plan), matches none of #309's named findings, and each
  needs its own proportional fix. Bundling them into #309 would have been
  exactly the "while I'm here" scope creep this repo's own anti-creep rule
  refuses.
- **Effort:** item 1 was genuinely small (done). Items 2 and 3 are medium,
  not small — each needs a real design decision (snapshot provenance
  tracking; lazy member decoding or a second reader that doesn't duplicate
  the envelope parser) before a safe fix, not a quick patch.
- **Approach:** `direct` — items 2 and 3 each need their design question
  settled first, then a small, targeted fix; no plan-tool plan needed.
- **Dependencies:** none.
- **Origin:** 2026-08-24, `/code-review 917fecc4..HEAD high` round 2 on
  BACKLOG #309's round-1 fixes.
- **Status:** item 1 done, items 2 and 3 not started.

**#391 — Optional handoff-register reconciliation in the installed `plan-tool` skill routers**

- **What:** define one optional, generic handoff-register protocol for the
  installed plan-tool skill routers. When a user supplies a register path, or
  explicitly accepts a router suggestion after a cross-runtime handoff,
  the router can review the register against accepted Roadmap, seed, and plan
  artifacts and present a read-only reconciliation: register item, matching
  artifact ID, relevance rationale, and suggested disposition. The router
  asks for review at the Roadmap acceptance, seed-promotion, plan-creation,
  plan-acceptance, and material source/profile-change checkpoints.
- **Effort:** medium. The protocol spans the Claude, Codex, and Cursor skill
  routers plus their shared reference and focused contract tests. The work is
  behavioral guidance and test coverage, not a new planning engine surface.
- **Risks / fallout:** a register can become a second backlog or silently
  widen a Roadmap source if the router treats its entries as requirements.
  Automatic mutation would make conversational observations look like durable
  decisions. The protocol must preserve a strict prompt/review boundary.
- **Dependencies:** evidence-gated on the Integration AI-DLC-to-plan-tool register
  and its first controlled Roadmap/seed reconciliation. That register is an
  external consumer example, not a required path or format dependency.
- **Outcome:** a user can opt into one handoff register and receive consistent,
  human-approved reconciliation prompts across installed routers without that
  register becoming Roadmap input or seed content.
- **In scope:** `integrations/{claude,codex,cursor}/SKILL.md`, their shared
  router/reference material, the generic register template or schema guidance,
  and router-contract tests that prove the same protocol on every supported
  harness.
- **Out of scope / Non-goals:** `plan_tool/` CLI or persistence changes; a
  register subcommand, manifest, source-reader, or Roadmap schema; parsing
  AI-DLC, Integration, or any external runtime paths; automatically creating,
  editing, linking, closing, or promoting register entries; passing a register
  to `roadmap --from-existing`, a Roadmap supplement, or a plan seed; and
  changing candidate, feedback, gate, lineage, or seed semantics.
- **Allowed behavior changes:** an installed skill may ask a user to review an
  explicitly selected register at the named checkpoints and may render a
  read-only relevance map. A register edit occurs only after the user supplies
  or explicitly confirms its exact content.
- **Allowed reorganization:** none. Keep the protocol in the existing shared
  router/reference boundary; do not create a new runtime subsystem.
- **Verification:** fixture a generic register and accepted Roadmap/seed/plan
  identifiers; assert each router renders the same review-only mapping, leaves
  the register absent from Roadmap and seed inputs, never writes without an
  explicit user confirmation, and preserves ordinary sessions when no register
  is supplied.
- **Stop / defer:** if evidence requires machine-readable persistence,
  automatic lifecycle transitions, source ingestion, or a generic register
  store, file a separate architect-tier item. If the first reconciliation
  finds no relevant accepted artifact, record `no roadmap impact` rather than
  inventing a plan row.
- **Route:** `plan`.
- **Readiness:** `evidence-gated`.
- **Tier:** `architect` — defines an installed-skill contract at the boundary
  between external handoff context and plan-tool's authoritative artifacts.
- **Origin:** 2026-09-17, Integration AI-DLC-to-plan-tool handoff work. The first
  register tracks cross-engine evidence without becoming Roadmap or seed input;
  the reusable capability is its optional, human-controlled reconciliation
  protocol rather than Integration-specific connector behavior.
- **Status:** not started.

### D. Process / hygiene

**#497 — Keep one plain-words swap list for the detail, audit, and apply prompts**

- **What:** `plan_tool/prompts/detail.md` and `plan_tool/prompts/plan-audit.md`
  each carry their own "Use plain, everyday words" swap list (for example
  "key" not "load-bearing"). Extracting every quoted alternative after "not" from that
  bullet in each file (so "fall-through" and "falls through" count separately)
  gives 19 terms in `detail.md` and 17 in `plan-audit.md`;
  14 are in both. Only `detail.md` has "fall-through", "falls through",
  "kind-dispatch", "resolves", and "spans its footprint"; only `plan-audit.md`
  has "a tautology", "footprint", and "vacuously". A swap added to one list does
  not reach the other, so a reviewer sees different rules depending on which
  prompt wrote the text. The roadmap stages already share one fragment
  (`plan_tool/prompts/roadmap-writing-style.md`).
- **Also decide:** both lists tell the model to swap "byte-identical" for
  "unchanged" and "short-circuit" for "stop early". Those are exact claims (a
  byte comparison, a control-flow behavior), and `synthesize-body.md` now says
  not to loosen such terms. The merged list should keep or drop them on purpose.
- **Why:** the lists are maintained by hand in two files, and they have already
  drifted.
- **Effort:** small; one shared fragment loaded as a template variable, as the
  roadmap stages do.
- **Risks:** the two prompts address different readers (an implementer for
  `detail.md`, an operator triaging a finding for `plan-audit.md`), so the
  lead-in sentence must stay per prompt; only the swap list is shared. Identity
  was established by a regex over each bullet's quoted terms (counts above), not
  an AST comparison, so re-run it before merging. Deliberately not merged:
  `apply-finding.md` (no swap list, only a short style note),
  `detail-quality.md` (a reviewer checklist of style nits, not a rewrite list),
  `jira.md` (a plain-English summary rule for a product manager), and
  `roadmap-writing-style.md` (roadmap prose, a different reader and rule set).
- **Scope contract:**
  - **Outcome:** one swap list included by both prompts.
  - **In scope:** the two lists and the loader that renders them.
  - **Out of scope / Non-goals:** changing any other prompt text; adding a
    readability checker (the style guide and `CLAUDE.md` refuse one).
  - **Allowed behavior changes:** each prompt gains the other's missing swaps.
  - **Allowed reorganization:** none beyond the shared fragment.
  - **Verification:** a test that both rendered prompts contain every term in
    the shared list.
  - **Stop / defer:** if the two readers need different lists, close this entry
    with that reason.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `experienced`.
- **Principle:** `write-for-the-human`.
- **Origin:** 2026-10-19 review of generated plan and roadmap prose.

**#498 — Tell a plan reader where the step list lives**

- **What:** the plan body's `## Steps` section says only "See the `steps:` block
  in the frontmatter." A reviewer reading the body gets no outline. `plan-tool
  status <name>` already prints a step-by-step view, but nothing in the plan
  mentions it.
- **Why:** a step list written into the body once at `create` would go stale as
  `split`, `merge`, `scope-out`, and reconcile edit the steps, which is the
  drift the pointer exists to avoid. Naming the command that reads the live
  list adds no stale text.
- **Effort:** small, but the pointer string is pinned by `tests/test_create.py`,
  `tests/test_annotate.py`, `tests/test_reprocess.py`, `tests/test_detail.py`,
  `tests/test_scope_fence.py` and by the placeholder check in
  `plan_tool/prompts/annotate.md`, and existing plans on disk carry the old
  text, so every reader of the old string must accept both.
- **Scope contract:**
  - **Outcome:** new plans point to both the frontmatter and `plan-tool status`.
  - **In scope:** the pointer text, its tests, and the `annotate.md` check.
  - **Out of scope / Non-goals:** writing a generated step list into the body;
    rewriting existing plans.
  - **Allowed behavior changes:** the new pointer wording.
  - **Allowed reorganization:** none.
  - **Verification:** old and new pointers are both recognized as the
    placeholder.
  - **Stop / defer:** if more than the listed readers depend on the exact text,
    defer.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `experienced`.
- **Principle:** `write-for-the-human`.
- **Origin:** 2026-10-19 review of generated plan and roadmap prose.

**#431 — `_gate_correction`'s kind→remedy classification is a vocabulary-prefix matcher with hand-curated exceptions, not a type-checked decision**

- **What:** `roadmap_candidate._gate_correction` routes each `Violation.kind`
  to a remedy string by matching `kind.startswith((...))` prefix tuples, with
  `_DROP_EXTRA_ROWS_GATE_KINDS` as a hand-maintained set of exact kinds pulled
  *out* of the `duplicate-` bucket because their prefix is a false friend (the
  same class this repo's own withdrawn per-`change_type` test-ordering
  contract names: a prose/vocabulary matcher that looks structural but is
  positional in disguise). The current mapping is verified correct for every
  `VIOLATION_*` kind that exists today (checked by running each kind through
  `_gate_correction`, not by reading), and
  `test_gate_correction_classifies_every_known_kind_by_name` (plus its
  test-local `_INTENTIONALLY_GENERIC_GATE_KINDS` allowlist) guarantees a new
  kind can't silently fall through to the generic fallback unnoticed — but
  nothing guarantees a new kind lands in the *correct* specific bucket, only
  that it lands in *some* bucket deliberately.
- **Why:** four kinds already needed a hand-curated override
  (`duplicate-inherited-decision`, `duplicate-feedback-id`,
  `duplicate-store-reference`, `ordering-plan-id-duplicate`) after shipping
  with the wrong, rename-shaped remedy — direct evidence the prefix heuristic
  gets it wrong in practice, not just in theory. A future `VIOLATION_*` kind
  whose string happens to start with an already-claimed prefix but needs a
  different remedy will silently render the wrong retry instruction to a
  model, and the exhaustiveness test stays green because it only checks
  generic-vs-specific, never specific-vs-*correct*-specific.
- **Approach sketch:** an explicit `remedy_shape` (or similar closed
  enum/field) set at each `Violation(...)` construction site in
  `roadmap_gates.py`, read directly by `_gate_correction` instead of
  re-derived from the kind string in a different module. Turns "does this
  kind's vocabulary look like X" into "did the check that raised this
  violation say it needs X" — a decision made once, where the defect's actual
  shape is known, not guessed at a distance.
- **Scope contract:**
  - **Outcome:** a new `VIOLATION_*` kind cannot land in a wrong
    specifically-routed remedy bucket without a test failing.
  - **In scope:** `Violation`'s shape, its ~90 construction sites in
    `roadmap_gates.py`, and `_gate_correction`'s dispatch.
  - **Out of scope / Non-goals:** any change to a violation's `message` text,
    to `_INTENTIONALLY_GENERIC_GATE_KINDS`'s membership, or to which kinds are
    routed where today — this is a mechanism change, not a remedy re-audit
    (the current mapping is already verified correct).
- **Effort:** medium — touches every `Violation(...)` call site in
  `roadmap_gates.py`, a stdlib-plus-leaves module with no first-party
  dependents besides its own consumers; mechanical but wide.
- **Approach:** direct, or a small plan if the construction-site sweep proves
  large enough to want its own convergence loop.
- **Origin:** 2026-09-27, roadmap-candidate gate-correction review pass 5,
  finding 3 (`plan_tool/roadmap_candidate.py:_gate_correction`) — raised after
  three prior passes (R1.5, P2.1, P3.1) each fixed one more instance of the
  same false-friend-prefix shape.
- **Status:** not started.

**#432 — `render_candidate_question_prompt` still reads its template with a bare, unguarded `read_text()`**

- **What:** `roadmap_candidate_review.render_candidate_question_prompt` (two
  call sites, lines ~767 and ~796) reads `roadmap-candidate-questions.md` via
  `(prompts_dir() / name).read_text(encoding="utf-8")`, with no domain-error
  mapping — unlike `roadmap_candidate_run.render_candidate_delta_prompt`,
  which reads its own template through `read_roadmap_text` with a small local
  closure that maps a missing file, permission error, or invalid UTF-8 to
  `CandidateProposalError` instead of a bare `OSError`/`UnicodeDecodeError`.
- **Why:** functionally harmless today — the sole caller's `except OSError`
  already absorbs the resulting bare `FileNotFoundError` into a normal
  `"failed"` result — but it is the same read-a-prompt-file shape, in the same
  file that already imports `roadmap_candidate_run`, left on the older,
  weaker pattern. Two separate `/code-review` passes have now flagged this
  same function (2026-09-27 passes 4 and 5); a third flag on an unfixed,
  low-cost finding is the tell to stop declining it and do the small fix.
- **Scope contract:**
  - **Outcome:** a missing/unreadable `roadmap-candidate-questions.md` raises
    a domain error (`CandidateReviewError`, this module's own convention, not
    `CandidateProposalError`) with a message naming the file, not a bare
    `OSError`.
  - **In scope:** both `render_candidate_question_prompt` read sites.
  - **Out of scope / Non-goals:** any other prompt-file read in the codebase;
    changing the caller's `except OSError` handling (already correct).
- **Effort:** small — two read sites. Follow the established idiom
  (`read_roadmap_text` plus a small local closure defined at the call site,
  as `render_candidate_delta_prompt` and several `roadmap.py` functions
  already do) rather than a new named per-module wrapper function — a
  single-use wrapper of that shape was itself flagged and removed from
  `roadmap_candidate_run.py` in pass 7 of the same review (finding P7.1).
- **Approach:** direct.
- **Origin:** 2026-09-27, roadmap-candidate gate-correction review passes 4
  (finding P4.4, declined as out of that diff's scope) and 5 (finding P5.5,
  same observation independently re-raised).
- **Status:** not started.

**#360 — Share best-effort candidate interruption logging without sharing typed result construction**

- **What:** `run_initial_candidate_proposal` records `run_interrupted` with
  `contextlib.suppress(KeyboardInterrupt)` inline, while
  `roadmap_candidate_review.py` records the same operation inside
  `_interrupted_result`. Extract only the best-effort interruption-log write
  into one candidate-flow leaf helper. Each caller continues to construct its
  own `CandidateProposalResult` or `CandidateReviewResult` locally.
- **Why:** the two paths implement the same interruption-recording property
  but present different local shapes. A future candidate interruption path
  can otherwise copy the inline proposal form and drift from the reviewed
  safe-logging behavior.
- **Scope:** introduce one helper with the inputs needed to record
  `run_interrupted` safely (logger, phase, attempt, and source); route the
  proposal handler and the review helper through it. Keep outcome text,
  result types, return points, phases, and attempt calculation at their
  existing callers.
- **Acceptance:** both proposal and review interruption paths use the shared
  helper; a second `KeyboardInterrupt` during `run_interrupted` still leaves
  the caller able to return its existing interrupted result; neither result
  type nor its externally visible outcome/detail changes.
- **Out of scope:** a generic result-builder, terminal `phase_end`/`run_end`
  handling, changing `RunLogWriter` behavior, or a global second-interrupt
  contract. #355 owns the shared-class contract question.
- **Proof:** retain and run the existing proposal and review tests that inject
  a second interrupt during `run_interrupted`; add a focused regression only
  if the refactor no longer demonstrates that both callers reach the shared
  helper.
- **Effort:** low — two callers and one leaf operation.
- **Dependencies:** none. This is compatible with #355 but neither requires
  nor resolves it.
- **Approach:** direct bounded change, followed by the normal focused tests,
  caller/vocabulary sweep, and review convergence for the changed snapshot.
- **Origin:** 2026-09-07, roadmap candidate-context review pass 6, finding 3
  (`plan_tool/roadmap_candidate_run.py:828`).
- **Status:** not started.

**#361 — Consolidate candidate failure-diagnostics finalization across proposal and review flows**

- **What:** proposal finalization and review `_finish_log` still each build
  `failure_extras` and conditionally call
  `record_candidate_failure_diagnostics` inside
  `contextlib.suppress(KeyboardInterrupt)`. Complete extraction of that
  diagnostics-finalization operation into one candidate-flow helper while
  retaining the distinct proposal and review result objects.
- **Completed slice (2026-09-08, `3590939e`):**
  `candidate_failure_diagnostic_extras` now supplies the shared core
  `phase_end` metadata before interruptible receipt capture. A second
  interrupt during receipt setup therefore reports the failure detail,
  attempt, call count, and `response_capture="unavailable"`, without
  changing the terminal outcome.
- **Why:** the duplicated block determines when a failed candidate response
  receives diagnostic metadata and which response text is retained. A change
  to one copy can silently leave the other copy with different diagnostics or
  interruption behavior.
- **Scope:** extend the existing core-metadata primitive into one shared
  finalization operation with the needed logger, phase, last response/attempt,
  terminal outcome, call count, fallback detail, and response-accepted state.
  Both callers continue to own their terminal result, duration calculation,
  `phase_end`, `run_end`, and returned result type.
- **Acceptance:** proposal and review derive the whole diagnostics-finalization
  result through one helper; stored outcomes still produce no diagnostics;
  accepted responses still exclude response text; rejected or failed
  responses preserve the same diagnostic fields; a second interrupt during
  diagnostics retains the established core `phase_end` metadata and does not
  prevent later terminal-record attempts.
- **Out of scope:** a generic candidate lifecycle framework, a shared result
  class, changing receipt or log schemas, altering exit outcomes, or a
  `RunLogWriter`-wide safety change. #355 remains the place for the latter.
- **Proof:** retain and run the proposal and review failure-logging tests,
  including response-accepted and second-interrupt cases. The completed slice
  adds assertions on the interrupted-receipt path for both callers; add a
  narrow finalization-helper regression only if the caller tests do not prove
  the unchanged diagnostics contract after the remaining extraction.
- **Effort:** low to medium — the operation is local, but its response and
  outcome inputs must preserve two established caller contracts exactly.
- **Dependencies:** none. #360 may land independently; the two helpers must
  remain separate unless a concrete shared input/output contract proves they
  are one operation.
- **Approach:** direct bounded change, followed by focused tests, an
  identifier-and-vocabulary sweep for candidate terminal diagnostics, and
  review convergence for the changed snapshot. Since
  `roadmap_candidate_run.py` is not imported by `roadmap_candidate_review.py`
  (only the reverse), the shared helper can live in
  `roadmap_candidate_run.py` alongside `record_candidate_failure_diagnostics`
  without an import cycle (confirmed by pass 7). While touching these two
  call sites, also fold the duplicated `interrupt_digest`/`original_digest`
  `_digest`-patching test closure (`tests/test_roadmap_candidate_run.py:960`,
  `tests/test_roadmap_candidate_review.py:1131`) into one shared test helper,
  the same way round 5 already factored `_interrupting_invoker`/
  `_raise_interrupt_for_run_log_events` — no separate backlog entry for this;
  it is the same consolidation, in the same two files, the moment this item
  lands.
- **Origin:** 2026-09-07, roadmap candidate-context review pass 6, finding 2
  (`plan_tool/roadmap_candidate_review.py:2088`); no-import-cycle detail and
  the test-closure duplication folded in from pass 7 on 2026-09-08, findings
  3 and 4 (`plan_tool/roadmap_candidate_run.py:842`,
  `tests/test_roadmap_candidate_run.py:960`).
- **Status:** partially complete — core fallback metadata is done; terminal
  finalization and test-helper consolidation are not started.

**#355 — "second-KeyboardInterrupt-safe" is a per-call-site convention in the roadmap candidate flows, not a property `RunLogWriter` enforces**

- **What:** `RunLogWriter`'s `phase_end`, `run_end`, `parse_failure`, and
  `run_interrupted` methods do not guarantee that a second
  `KeyboardInterrupt` is best-effort only. The eight terminal-record calls
  inside the candidate proposal and review flows' `try`/`finally` blocks are
  individually guarded today, but each future caller must remember the
  convention with no API, lint, or type-level enforcement — and the
  convention's own reach is incomplete: `logger.phase_start(...)` is called
  *before* the `try:` block in all three candidate-flow entry points
  (`run_initial_candidate_proposal`, `generate_candidate_question`,
  `request_replacement`), so a `KeyboardInterrupt` landing during that call
  (a real `os.open`/`os.write` plus a lock-guarded in-flight snapshot write)
  still escapes every guard uncaught.
- **Why deferred:** one live gap is now known (the pre-`try` `phase_start`
  calls in the candidate flows) rather than only a future-enforcement
  risk, but it is a narrow-window, best-effort-diagnostics path — not the
  primary interruption/result semantics — and patching them one more time at
  the call site would repeat the same per-site pattern that produced four
  rounds of "one more missed site" (rounds 2, 3, 5, 7) in this exact class. A
  `RunLogWriter`-level guarantee changes behavior for every current and
  future caller and needs an explicit decision about which lifecycle writes
  may absorb a second interrupt, rather than a fifth incremental patch.
- **Scope:** decide and document the shared contract, then inventory every
  direct terminal-record caller — including `phase_start` (not just
  `phase_end`/`run_end`/`parse_failure`/`run_interrupted`, per the gap
  above). Compare a guarded
  public method, a wrapper helper, and preserving raw methods with an
  explicit caller-only boundary; migrate only the callers the chosen
  contract covers.
- **Acceptance:** the selected API makes the intended second-interrupt
  behavior explicit; every in-scope caller is enumerated and either migrated
  or documented as intentionally outside that behavior — the candidate-flow
  `phase_start` calls included; tests
  prove the chosen path preserves the primary interruption/result semantics
  while the terminal write remains best effort.
- **Out of scope:** silently changing all `RunLogWriter` methods, assuming
  every logger write may suppress interrupts, or folding the separate
  `claude_errors.py` instance into this item without first confirming the
  shared contract applies there.
- **Proof:** add focused `RunLogWriter` and representative-caller tests for
  the selected contract, then run a full caller and vocabulary sweep for
  terminal-record operations (including `phase_start`) and the proportionate
  suite.
- **Effort:** medium — a shared-class design decision plus a codebase caller
  inventory and migration boundary.
- **Dependencies:** account for the related `claude_errors.py` entry in
  `BUG_BACKLOG.md`, the known gap above, and any further unguarded
  direct caller discovered by the inventory; none block the design decision.
- **Approach:** `plan-tool` — this shared-class contract change needs its own
  scoped plan and bare/detail audit gates, rather than a direct edit.
- **Origin:** 2026-09-04, roadmap candidate-context review pass 5; confirmed
  as the appropriate deferred structural concern by pass 6 on 2026-09-07
  (`plan_tool/roadmap_candidate_run.py:844`); two further live instances
  deferred here by pass 7 on 2026-09-08 (`plan_tool/roadmap_candidate_run.py:628`,
  `plan_tool/roadmap_candidate_review.py:728,885`; a third
  site in the since-deleted `roadmap_revision_run.py`), per explicit user direction not
  to patch a fifth site inline.
- **Status:** not started.

**#359 — Candidate consolidation: four more repo-relative path-display idioms left duplicated after the `literal_path` sweep (unverified — needs identity check before any merge)**

- **What:** the `literal_path` consolidation (this session) unified only the
  platform-native, non-resolving `try: p.relative_to(repo_root) except
  ValueError: str(p)` idiom. Four more distinct idioms remain independently
  hand-rolled, none in `literal_path`'s scope:
  - **POSIX-forced, non-resolving** (`path.relative_to(repo_root).as_posix()`
    / `except ValueError: path.as_posix()`): `review.py`'s
    `_repo_relative_posix`, `annotate.py`'s `_repo_relative_excerpt_path`,
    `cli/completeness_cmd.py`'s `_jira_grounding_line`, and the inline
    directory-announcement branch in `launcher.py`'s
    `preflight_step_paths` (kept inline deliberately in commit `87539cfa`
    — see that commit's message for why the platform-native swap was
    reverted there).
  - **Root-resolved, POSIX-forced on success only** (`path.relative_to(
    repo_root.resolve()).as_posix()` / `except ValueError: str(path)` — the
    fallback is plain `str()`, not `.as_posix()`, an inconsistency of its
    own): `cli/reconcile.py`'s two saved-review/reuse announcements (the
    site around `saved_path.relative_to(repo_root.resolve())` and its
    sibling a bit further down) and `cli/review_cmd.py`'s equivalent
    saved-review announcement.
  - **Resolved on both sides, POSIX-forced throughout, including the
    fallback** (`path.resolve().relative_to(repo_root.resolve()).as_posix()`
    / `except ValueError: str(path.resolve())`): `cli/reconcile.py`'s three
    canonical-plan-path persistence sites, `auto_reconcile.py`'s
    detail-reconcile save, `cli/review_actions.py`'s nested detail-reconcile
    save, and `cli/review_cmd.py`'s review save. Distinct from the previous
    idiom by resolving on *both* the target and the fallback, not just the
    root — a real semantic difference (a symlinked path component changes
    the fallback string), not a formatting one.
  - **Resolved target/root, POSIX-forced only on success** (`path.resolve().
    relative_to(repo_root.resolve()).as_posix()` / `except ValueError:
    str(path)`): `cli/completeness_phases.py`'s persisted `plan_rel` value.
    The lexical fallback is distinct from the fully resolved fallback above.
  - This is a **resemblance observation, not verified evidence** — no
    AST-normalized comparison has been run, per this repo's CLAUDE.md
    consolidation-entry rule. The first two idioms were surfaced by
    `/code-review` round 4 on the `literal_path` sweep (`0a11fde0`..
    `0bf27acc`); the third was found by round 5, which also caught that
    round 4's own count of "two idioms" was itself incomplete — a reminder
    that this entry's own idiom count should be re-verified, not assumed
    exhaustive, before any merge is scoped.
- **Do-not-merge look-alikes, stated up front:** none of the four idioms
  above may be merged with each other (they disagree pairwise on whether
  the target resolves, whether the root resolves, and whether the fallback
  resolves or forces POSIX), and none may be merged into `literal_path`
  (resolves nothing, platform-native) or `display_path` (resolves both
  sides, platform-native). Four function bodies already carry their own
  docstrings asserting a specific, deliberate contract
  (`_repo_relative_posix`'s "the single labeler for both the finding paths
  and `_format_audit_detail_bundle`'s bundle listing", `_jira_grounding_line`'s
  "Deliberately POSIX-always ... unlike this file's `literal_path` use") —
  a merge proposal must re-verify each of those claims against current
  callers, not assume the docstring is still accurate.
  `roadmap_seed_state.py:render_seed_state_marker` remains an intentional
  inline look-alike: it resolves both operands before using the platform-
  native form, but the module is a stdlib lifecycle leaf and therefore must
  not import `pathutil`. Its persisted seed-state locator preserves that
  resolve-before-render contract; a future consolidation must leave this
  site inline unless the architecture boundary itself changes.
- **Fix:** not yet designed. Before proposing a merge: (1) run the same kind
  of AST-normalized identity check BACKLOG #79 required, and treat its
  output count as authoritative over this entry's manual tally; (2) for
  each pair the check groups, re-verify the docstring claims above against
  current callers.
- **Approach:** direct, once the identity check above produces a real
  mergeable set — do not merge on resemblance alone.
- **Arc assignment:**
  [`backlog-arc-operator-workflow.md`](docs/implementation-plans/backlog-arcs/backlog-arc-operator-workflow.md) —
  the direct continuation of the delivered lexical path-display consolidation, the
  arc this entry's own idiom inventory was surfaced auditing.
- **Origin:** 2026-09-04, `/code-review` rounds 4 and 5 on the
  `literal_path` consolidation (commits `0a11fde0`, `87539cfa`, `0bf27acc`,
  `6717a05e`).
- **Status:** not started.

**#352 — `propose_references_from_claude`'s phase-timing scaffold is a third repetition of a pattern already duplicated twice in `_prepare_create_plan`**

- **What:** the new iteration-branch reference-research block
  (`plan_tool/create.py`, ~line 9641) repeats the same
  `phase_start`/`t0 = time.monotonic()`/`outcome = "ok"`/
  `try: ... except Exception: outcome = "error"; raise`/
  `finally: phase_end(...)` scaffold already present at
  `_prepare_create_plan`'s roadmap branch (~line 8643) and its
  generic-origin branch (~line 8684) — three sites, not two, once this
  plan landed.
- **Why not filed as a strict consolidation entry:** verified by reading
  all three sites directly, not merely by resemblance — the SHAPE
  repeats but the bodies are not close to byte-identical: the new site
  additionally classifies `reference_result.outcome` into the phase
  outcome (`unparseable` → `"error"` + sets `stage_failure`; `empty` →
  `"skipped"`) and threads an `iteration=` kwarg through both
  `phase_start`/`phase_end` that the other two sites don't carry. A
  consolidation needs to parameterize both of those differences (a
  context manager or helper taking the phase name, an optional
  iteration, and an outcome-classifying callback), not a straight
  extract — this is a real repeated pattern, not a `tests/test_duplication.py`-catchable
  exact duplicate.
- **Effort:** medium — designing the shared shape without over-fitting
  it to only these three call sites' current needs.
- **Dependencies:** none.
- **Approach:** `plan-tool` if pursued — touches three call sites across
  two functions and changes an established internal idiom; a direct edit
  risks under-testing one of the three outcome-classification paths.
- **Origin:** 2026-09-02 code-review pass over `developer-doc-research-parse-failure`.
- **Status:** not started.

**#358 — `dump is not None and repo_root is not None` computed twice in the same unparseable-response branch**

- **What:** `propose_references_from_claude`'s terminal-unparseable
  branch (`plan_tool/create.py`, ~lines 3477 and 3481) computes
  `dump is not None and repo_root is not None` twice in adjacent
  statements — once to gate the "raw response saved to ..." hint string,
  once to gate the `run_logger.parse_failure` call. Not a bug, purely
  repeated code the two use sites could drift apart under a future edit.
- **Effort:** small — hoist the compound condition into one local
  variable, reuse at both use sites.
- **Dependencies:** none.
- **Approach:** direct, whenever someone is next in this function.
- **Origin:** 2026-09-02 code-review pass over `developer-doc-research-parse-failure`.
- **Status:** not started.

**#349 — Consider migrating the roadmap stage loop's hand-rolled status channel onto `progress.py`'s shared reporter**

- **What:** the stage-lifecycle status machinery this diff built
  (`_emit_roadmap_status`, `_emit_stage_retry_status`,
  `_StageStopReporter`/`_stage_run_guard`, `_bounded_status_text`) is a
  second, independent implementation of the same problem
  `plan_tool/progress.py`'s `ProgressReporter`/`StepHandle` already solves
  for every other silent backend-invoking command (`detail`, `jira`,
  `review`, `create --from*`): give a minutes-long Claude call
  human-readable stderr status. `progress.py`'s own module docstring
  states that exact purpose, with a `start_step()` → `StepHandle` lifecycle,
  `notice(kind="retry")` for retries, `complete()`/`fail()` for one-shot
  terminal reporting, and a heartbeat thread — none of which the roadmap
  stage loop's independent, heartbeat-free, differently-shaped vocabulary
  gets or can get without hand-porting each future `progress.py` fix
  (a heartbeat cadence change, a color/`NO_COLOR` fix) separately.
- **Why not fixed inline:** a real architectural migration — every
  `_emit_roadmap_status`/`_emit_stage_retry_status`/`_StageStopReporter`
  call site across the stage loop, both revision flows, and their tests
  would need to move onto `ProgressReporter`'s lifecycle and vocabulary,
  which may not even fit roadmap's per-stage-not-per-attempt reporting
  shape without its own extension — a decision and a design pass, not a
  proportional fix to make now. Overlaps, and may subsume,
  `BACKLOG.md` #342 (`status_callback` vs. `RunLoggerLike` unification) —
  resolve that question as part of scoping this one, not independently.
- **Effort:** large — a genuine cross-cutting migration, not a local
  refactor.
- **Dependencies:** informs, and may subsume, `#342`.
- **Approach:** decision first.
- **Origin:** 2026-09-02, round-14 `/code-review` pass (full
  `77e1aeb7..HEAD` to-be-pushed range) on
  `2-roadmap-stage-lifecycle-output.md`'s landed diff.
- **Status:** not started.

**#346 — The stage-run guard's "stopped" emission still relies on per-branch discipline, not structural enforcement**

- **What:** `_stage_run_guard`/`_StageStopReporter` (`plan_tool/roadmap.py`) make a double "stopped" report impossible, but they don't make a *missing* report impossible: each of the six failure branches inside `_run_roadmap`'s per-stage loop still has to remember to call `stop_reporter.emit(...)` by hand before its `break` — a `break` never reaches the guard's own `except Exception:` backstop, so a future seventh failure branch that adds a `break` without calling `.emit()` first (and without raising) would silently stop the stage with no `"stopped"` status line ever printed.
- **Why not fixed inline:** no live bug today — all six current branches already call `.emit()` correctly, verified in round 12's review and by this session's own trace. Closing the gap structurally means either converting every break-with-failure branch into a raise (so the guard's `except` becomes the *only* place "stopped" is reported), which is a real control-flow restructuring with correctness risk of its own, or accepting the current discipline-based design and relying on test coverage / code review to catch a future omission — a design call, not a proportional fix to make now against a hypothetical future site.
- **Effort:** medium if restructured to raise-based control flow; small if the answer is instead "add a completeness check/test that fails if a break site in this loop has no accompanying `.emit()` call" (a lower-cost alternative worth considering first).
- **Dependencies:** none.
- **Approach:** decision first.
- **Origin:** 2026-09-02, round-12 `/code-review` pass (first at the corrected full to-be-pushed-range scope, `77e1aeb7..HEAD`) on `2-roadmap-stage-lifecycle-output.md`'s landed diff. A round-14 pass named a third option worth weighing alongside the two above: the five failure branches don't only repeat `stop_reporter.emit(...)`, each also hand-writes the same `run_logger.phase_end(...)` + build-a-`RoadmapResult`-via-`stage_invalid(...)` + `break` sequence around it — one shared helper taking the failure detail and returning the loop action could make omitting any one of the three steps structurally impossible, without the larger raise-based restructuring the first option needs.
- **Status:** not started.

**#345 — Share a fixture/recorder for `TestRoadmapStageStatus`'s repeated status-list boilerplate**

- **What:** `tests/test_roadmap.py::TestRoadmapStageStatus` (~20 methods)
  repeats `statuses: list[str] = []` plus a hand-built
  `"roadmap storefront: stage 1 (domain) ..."` prefix-string in nearly
  every method, instead of a shared fixture or recorder — this file
  already has that convention elsewhere (`_GateRecorder`, `_CallRecorder`)
  for other repeated test setup, just not applied here.
- **Why not fixed inline:** purely a test-hygiene nit against passing
  tests, not a correctness or coverage gap — no defect it would close.
  Touching ~20 methods to introduce a shared recorder is a proportionate
  amount of churn for its own change, not something to fold into an
  unrelated fix.
- **Effort:** small — one recorder helper (or fixture) plus a mechanical
  rewrite of each method's status-list setup to use it.
- **Dependencies:** none.
- **Approach:** direct.
- **Origin:** 2026-09-02, round-9 verification `/code-review` pass on
  `2-roadmap-stage-lifecycle-output.md`'s landed diff (the
  `_stage_run_guard` centralization).
- **Status:** not started.

**#343 — Consolidate the status-emission helper family's repeated internal patterns**

- **What:** `plan_tool/roadmap.py`'s four status-emission helpers
  (`_emit_roadmap_fact`, `_emit_roadmap_status`, `_emit_accepted_stage_selection`,
  `emit_roadmap_terminal_status`) share two undocumented structural patterns
  rather than one shared implementation. First, `_bounded_status_text`'s
  `escaped: bool` parameter gives its `value` argument two incompatible
  contracts (raw-to-escape vs. already-safe-only-clip) enforced purely by
  caller discipline — a first review round flagged this as untested by
  mutation, and a sixth round independently re-derived it as a "latent
  foot-gun", making this a recurring rather than one-off observation.
  Second, `_emit_roadmap_status` and `_emit_accepted_stage_selection` each
  independently re-implement the `if status_callback is None: return`
  guard plus a `try/except Exception: return` fail-open wrapper that
  `_emit_roadmap_fact` (which both of them call immediately afterward)
  already provides — a change to the fail-open contract has to be applied
  in three near-identical places instead of one.
- **Why not fixed inline:** both patterns are currently safe in practice
  (every `escaped=True` caller pre-escapes; the duplicated fail-open
  wrappers behave identically today) and fixing either means restructuring
  four function signatures or their call boundaries — a moderate refactor
  disproportionate to a hand-fix, and exactly the kind of "while I'm here"
  cleanup the anti-creep convention in `docs/TRACKING.md` defers to an entry.
- **Effort:** medium — likely two smaller changes: split `_bounded_status_text`
  into an escape-then-bound path and a bound-only path (removing the
  `escaped` flag from all four functions), and have `_emit_roadmap_status`/
  `_emit_accepted_stage_selection` delegate their None-check and fail-open
  behavior to `_emit_roadmap_fact` rather than re-implementing it.
- **Risks / fallout:** low — both changes are internal to this helper
  family; the public behavior (bounded, escaped, fail-open status lines) is
  unchanged either way, so the risk is limited to introducing a regression
  in the refactor itself, catchable by the existing lifecycle-status tests.
- **Dependencies:** none.
- **Approach:** direct.
- **Origin:** 2026-09-01 (`escaped` flag, first `/code-review` round) and
  2026-09-02 (fail-open duplication and the `escaped` flag's independent
  re-discovery, sixth `/code-review` round) on
  `2-roadmap-stage-lifecycle-output.md`'s landed diff.
- **Status:** not started.

**#342 — Decide whether `status_callback` and `RunLoggerLike` should be one seam**

- **What:** `roadmap.py`'s stage-run functions thread two independent
  "tell something what's happening" parameters through nearly identical
  signatures: `status_callback` (bounded stderr facts, this feature) and
  `run_logger: RunLoggerLike` (structured JSONL events, pre-existing).
  `RunLoggerLike.phase_start`/`phase_end` already fire at close to the same
  transition points `status_callback` fires at, and the two are already
  wired inconsistently even within one file: the normal `roadmap <slug>`
  path (`cli/roadmap_cmd.py`'s `cmd_roadmap`) passes `status_callback=note`
  and never constructs a `run_logger` (stays `None`); `_cmd_roadmap_materialize`
  builds a real `run_logger` via `_roadmap_command_lifecycle` and never wires
  `status_callback` (the gap `#338` already tracks from the other direction).
- **Why not fixed inline:** this is a genuine "should these be one seam or
  two" design question, not a proportionate hand-fix — unifying them would
  mean deciding whether `status_callback` becomes a thin projection of
  `RunLoggerLike` events, or the two stay deliberately separate (one for a
  human's terminal, one for durable structured audit). Either answer touches
  every stage-run function's signature.
- **Effort:** medium-to-large — touches `_run_stage`, `_run_bounded_stage_feedback`,
  `_run_feedback_free_stage`, `_run_roadmap`, `run_roadmap`, and every CLI
  dispatch function in `cli/roadmap_cmd.py`, plus their tests.
- **Risks / fallout:** a bad unification could couple the terminal-facing
  vocabulary (concise, operator-readable) to the structured-logging
  vocabulary (exhaustive, machine-readable) in a way that degrades either.
- **Dependencies:** informs, and is informed by, `#338` (extending
  `status_callback` to `--refresh-seeds`/`--materialize`) — resolving this
  first could change how `#338` is implemented.
- **Approach:** decision first.
- **Origin:** 2026-09-02, third `/code-review` round on
  `2-roadmap-stage-lifecycle-output.md`'s landed diff.
- **Status:** not started.

**#341 — Share the `"stage N (name)"` format string across `roadmap.py`**

- **What:** the literal format `f"stage {stage.number} ({stage.name}) ..."`
  (or the equivalent with pre-bounded `number_label`/`name_label`) is
  hand-repeated at 7 sites in `plan_tool/roadmap.py`: the new lifecycle-status
  composition (`_emit_roadmap_status`, line 687) and six pre-existing error
  messages (lines 1083, 1259, 1297, 1332, 1345, 1372).
- **How identity was established:** by grepping the literal `f"stage `
  pattern across the file and reading each of the 7 matches — the format
  itself (`stage {number} ({name})`) is identical at every site; what
  follows it differs (a status fact vs. one of six distinct error messages).
- **Do-not-merge look-alikes:** none identified yet — a shared formatter
  would need to accept either a raw `RoadmapStage` (the six error-message
  sites) or the already-bounded `number_label`/`name_label` strings
  (`_emit_roadmap_status`, which bounds before composing for the terminal),
  so unifying the two calling shapes is part of the scoping work, not a
  given.
- **Effort:** small — one shared formatter plus 7 call-site updates, each
  already covered by an existing test asserting its exact message text.
- **Risks / fallout:** none beyond the mechanical test-text churn from
  routing 7 existing messages through one function instead of 7 literals.
- **Approach:** direct.
- **Origin:** 2026-09-02, second `/code-review` round on
  `2-roadmap-stage-lifecycle-output.md`'s landed diff.
- **Status:** not started.

**#340 — Consolidate the bounded-truncate-with-digest-suffix idiom**

- **What:** `plan_tool/roadmap.py:_bounded_status_text` (cap a string, append
  `...#<digest>` when it needs clipping) duplicates the same underlying
  concern — bound a string for terminal/log display and mark that it was
  clipped — already solved several other ways in this codebase:
  `plan_tool/progress.py:_truncate` (cap+ellipsis for progress labels),
  the sha256-short-id idiom in `plan_tool/review.py:_make_rec_id`,
  `plan_tool/bench.py`/`plan_tool/telemetry.py`,
  `plan_tool/lessons.py:1282`, and `plan_tool/scenario_capture.py:188`,
  `plan_tool/run_log.py:_truncate_long_strings`'s
  `…<elided N chars>` elision marker, and
  `plan_tool/prompt_excerpt.py:414`'s `clip_text_to_byte_budget` (a
  byte-budget cap with a boolean truncated flag rather than an inline
  marker).
- **How identity was established:** by reading all seven call sites, not an
  AST duplicate-group pass — the bodies are not textually identical (digest
  length varies 8/10/12/16 hex chars, marker format varies
  `…<elided N chars>` vs `...#<digest>` vs bare `…`, and
  `clip_text_to_byte_budget` signals truncation via a returned boolean
  instead of an inline marker at all), so `tests/test_duplication.py` does
  not and would not group them. The shared thing is the policy (bound +
  mark-as-clipped), not the code.
- **Do-not-merge look-alikes:** none identified yet — this entry needs a
  read of all five sites' callers before proposing one shared helper, since
  each may have a reason for its specific digest length, marker format, or
  truncation-signaling shape (inline marker vs. returned boolean) that a
  merge would need to preserve or deliberately drop.
  `clip_text_to_byte_budget` in particular caps by *byte* budget (for
  content headed into a prompt), not *character* count (for terminal
  display) — that distinction may turn out to be load-bearing rather than
  incidental. `_bounded_status_text`'s own digest hashes with
  `errors="backslashreplace"` (a 2026-09-02 fix — its plain `utf-8` encode
  raised `UnicodeEncodeError` on a lone surrogate); `plan_tool.roadmap_source
  .digest_decoded_text`, the sibling a fourth review round suggested reusing
  here, does not carry that guard. Confirm each site's crash-safety
  requirement before merging — a naive reuse of the "already exists" digest
  helper would reintroduce the bug this fix closed.
- **Why now — not fixed inline:** found incidentally while fixing a
  truncation-budget bug local to `_bounded_status_text` during a
  `/code-review` pass; per the anti-creep convention in `docs/TRACKING.md`, a
  consolidation opportunity noticed mid-task is an entry, not a "while I'm
  here."
- **Effort:** medium — seven call sites across seven modules, each with its
  own tests to keep green.
- **Risks / fallout:** a shared helper has no single place to fix a bug in
  the clipping arithmetic today (`_bounded_status_text`'s own
  `limit < len(suffix)` edge case was one such bug, fixed directly rather
  than waiting on this consolidation); consolidating fixes that once, but a
  merge that gets the format wrong for one caller regresses whatever reads
  its output (logs, terminal, telemetry, prompts).
- **Approach:** direct, once the per-site read above confirms no caller
  depends on its specific digest length, marker format, or byte-vs-character
  budget for a reason worth preserving separately.
- **Origin:** 2026-09-02 `/code-review` pass on
  `2-roadmap-stage-lifecycle-output.md`'s landed diff; the
  `clip_text_to_byte_budget`, `lessons.py`, and `scenario_capture.py`
  siblings were each found by a later `/code-review` round the same day.
- **Status:** not started.

**#339 — Two open design questions on the `roadmap` stage loop's "stopped" emission**

- **Delivered, no longer part of this entry:** `_run_roadmap`'s stage loop
  used to emit `_emit_roadmap_status(..., fact="stopped")` by hand at 10
  separate `except`/early-return points. Eight consecutive `/code-review`
  rounds on this diff (2026-09-01/02) each found a *different* exception
  type or unguarded window escaping whatever the prior round had
  enumerated, including one round whose own summary claimed completeness
  and was proven wrong by the very next round — the strongest evidence
  available that a hand-maintained list of guarded sites cannot be trusted
  to stay complete. The stage loop is now wrapped in one
  `_stage_run_guard` context manager (`plan_tool/roadmap.py`, modeled on
  the existing `_roadmap_writer_owner` precedent) covering the whole body
  from `"started"` through the end of each iteration: any exception raised
  anywhere inside emits `"stopped"` exactly once and re-raises; a normal
  `break`/`continue`/fall-through is not an exception and never triggers
  it, so every already-correct exit path (a successful write, a re-gate,
  a handled admission failure) is untouched. This closes both the
  exception-completeness question and the duplication risk a future added
  branch could reintroduce — landed 2026-09-02, direct tests included
  (`TestStageRunGuard` in `tests/test_roadmap.py`, plus the full existing
  lifecycle-status suite passing unchanged, proving no behavior moved).
  **A round-9 verification `/code-review` pass on that centralization
  disproved the "exactly once" half of this claim**: six branches inside
  the guarded block report `"stopped"` themselves (a gate rejection, an
  exhausted budget, an admission error) and then call
  `run_logger.phase_end(...)` immediately after, still inside the `with`
  block — if that `phase_end` call itself raised, the guard's own `except
  Exception:` fired again and reported a second, bare `"stopped"` for the
  same attempt. Reproduced directly (monkeypatched `phase_end` to raise
  `RunLogLineTooLarge` on an `"exhausted"` outcome; a gate-failing stage
  produced two `"stopped"` facts instead of one) before fixing: the six
  sites now report through a shared `_StageStopReporter` (yielded by
  `_stage_run_guard`) whose `emit()` is idempotent per attempt, and the
  guard's `except` calls the same `emit()` instead of reporting directly —
  so whichever side reports first wins and the second is a no-op. Landed
  2026-09-02 alongside a regression test pinning the corrected sequence
  and a new `TestStageRunGuard` case pinning the reporter's idempotency
  directly.
- **Still open — the `KeyboardInterrupt` gap:** a `KeyboardInterrupt` is a
  `BaseException`, not an `Exception`, so `_stage_run_guard`'s `except
  Exception:` deliberately does not catch it — a Ctrl-C anywhere in a
  stage's processing, including inside the status write itself, still
  loses the terminal fact (recoverable only via `__context__`, not by
  type). `_emit_roadmap_fact`'s `except Exception: return` and
  `test_status_callback_keyboard_interrupt_propagates` both pin that an
  interrupt must propagate, so a correct fix has to let a genuine interrupt
  through while still preserving the original error when the interrupt is
  spurious relative to it — a real design decision, not a proportional
  catch. `plan_tool/launcher.py` (~line 651) has a precedent worth copying
  for an analogous retry loop: an explicit `except (KeyboardInterrupt,
  SystemExit): raise` ahead of its generic `except BaseException`, so the
  interrupt passes through untouched before the broader handler ever sees
  it. `_stage_run_guard` is now the single place to make that call once,
  rather than at 10 scattered sites. **A round-9 verification pass named a
  broader instance of the same gap**, worth resolving together: if the
  `status_callback` itself raises a `BaseException` while
  `_StageStopReporter.emit()` is mid-way through reporting a *different*,
  real original exception's `"stopped"` fact, that new `BaseException`
  propagates before the guard's own `raise` line ever executes — discarding
  the original exception's identity (recoverable only via `__context__`,
  not by type) and surfacing at `cmd_roadmap`'s boundary as a generic
  "interrupted"/rc=130 instead of the real failure. Not a `Ctrl-C`-only
  case: any caller-supplied `status_callback` that can raise `SystemExit`
  or another non-`KeyboardInterrupt` `BaseException` triggers it too, so the
  eventual fix should cover `BaseException` in general, not just the one
  named type.
- **Still open — "stopped" after a successful write:** three windows
  (`_write_brief_source`'s block, the post-`"wrote"` window, and the
  post-`"re-gated without write"` window) can report "stopped" after the
  stage's real outcome is already known and reported — the guard's own
  docstring now says "stopped" means the *run* didn't confirm, not that
  nothing happened, but a status vocabulary that can say "published, but
  the run did not confirm" directly would be more precise than relying on
  a reader having found the comment.
- **Effort:** small for either remaining question — both are now scoped to
  one function (`_stage_run_guard`) instead of a design that had to be
  checked against 10 scattered sites.
- **Dependencies:** none.
- **Approach:** decision first for the `KeyboardInterrupt` question (a real
  design call); direct for a new "stopped"-family status word once the
  vocabulary is chosen.
- **Origin:** 2026-09-02, eight consecutive `/code-review` rounds on
  `2-roadmap-stage-lifecycle-output.md`'s landed diff, plus a ninth
  direct-implementation pass that delivered the centralization itself.
- **Status:** not started (both remaining questions).

**#326 — Reconsider where the sampler checkpoint lives (bolted onto `SavedReview`/`save_review`)**

- **What:** the `audit-pass-persistence` plan's sampler-checkpoint feature
  (`plan_tool/review.py`'s `audit_plan_until_stable` resume machinery) persists
  through the general-purpose `SavedReview`/`save_review` shape in
  `review_persistence.py` rather than a purpose-built artifact. Across a
  7-round `/code-review` convergence pass on that plan (2026-08-31/09-01),
  three independent review angles converged on the same underlying tension
  from different sides: round 1 noted it reinvents `plan_tool/checkpoint.py`'s
  existing content-hash-gated resume primitive (already used identically by
  `create.py`/`detail.py`) instead of using it, storing a transient recovery
  artifact in the reports directory whose stated purpose is durable evidence;
  round 4 found the sampler-specific validation bolted onto
  `_normalize_checkpoint_role`, a classifier built for a different two-state
  concept; round 5 found `save_review` grew three special-case validation
  branches (`_checkpoint_path`'s single-legal-value enforcement,
  `sampler_state` requiring the checkpoint form, `checkpoint_audit_revision`
  requiring it too) whose entire purpose is detecting misuse of parameters
  that are structurally single-valued for this one caller, added to an
  already-large (~24-parameter) shared function.
- **Why now — not fixed inline:** each individual finding was proportionate
  to decline on its own (a working, tested mechanism; the fix shape for any
  one of them is a moderate structural change, not a one-line patch), but the
  *pattern* recurring across three independently-run review passes is a
  stronger signal than any single finding — it means the current home is
  fighting the abstractions it's built on rather than fitting them. A
  redesign (e.g., migrating to `checkpoint.py`'s primitive, or giving the
  sampler checkpoint its own persisted shape instead of overloading
  `SavedReview`) is a deliberate architectural decision, not something to
  hand-apply mid-review per this file's own "Audit the why" convention.
- **Effort:** medium-to-large — touches the writer (`save_sampler_checkpoint`),
  every reader (`list_saved_reviews`, `load_audit_evidence_ledger`,
  `resolve_saved_review`, the CLI ineligibility predicates), and their tests.
  **Value:** removes the recurring special-casing at every one of those sites
  (a fixed, non-timestamped filename living alongside timestamped saved
  reviews already needs a `path != checkpoint_path` / `path.name !=
  SAMPLER_CHECKPOINT_FILENAME` exclusion at each reader today) and the
  parameter-bloat/role-overload findings above.
- **Approach:** decision first — plan-tool (the redesign itself, once scoped,
  is squarely a `create`/`detail`/`run` effort, not a direct edit).

**#323 — Share the ordering/plan reconciliation between `--view walk` and `--view html`**

- **What:** `roadmap_view.py:render_traceability_walk` (the ordering loop) and
  `roadmap_html.py:_plans_block` each encode the same three-case reconciliation
  of `PlansArtifact.plans` against `PlansArtifact.ordering`: group rows by id,
  walk `ordering`, track what has rendered, and mark a dangling entry, a
  repeated entry, and a plan row the ordering never names.
- **How the duplication was established:** by reading both, not by an AST
  duplicate-group pass — the two bodies are *not* textually identical (one
  appends to `lines` and returns joined text, the other appends HTML fragments),
  so `tests/test_duplication.py` does not and would not group them. The shared
  thing is the **decision table**, not the emission. That is why this is a
  candidate for a shared classifier returning the three cases, not for folding
  one renderer into the other.
- **Evidence it drifts:** it already did. The HTML copy shipped 2026-08-29 with
  three divergences from the walk it claimed parity with — the duplicate-entry
  marker printed the raw id where the walk prints `display_label(matches[0])`,
  and both ambiguous branches dropped the competing labels the walk lists.
  All three were caught by review, not by a test, because each view's tests
  assert its own output. Fixed in place the same day; the *structural* cause —
  one rule, two encodings — is what this entry tracks.
- **Deliberately not merged when found:** the divergence was a bug and was
  fixed; consolidating the rule needs a home decision (a third leaf both import,
  since `roadmap_view` must not import `roadmap_html` and the reverse edge is
  the one that exists), a call-site sweep, and its own tests. Per CLAUDE.md
  § anti-creep that is an entry, not a "while I'm here".
- **Do-not-merge look-alikes:** the two `_render_plan_body` / `_plan_card`
  bodies are **not** part of this — they render genuinely different field sets
  for different media (the walk descends into components and entities; the HTML
  card is flat and links instead). Merging those would be the mistake this
  entry's scope exists to prevent.
- **Effort:** small-to-medium. **Value:** removes a rule that must be changed
  twice and has already been changed inconsistently once.
- **Second instance found the same day:** the dangling-ordering-entry-
  resolves-to-a-non-plan-row defect, and its repeated-entry variant, were the
  identical gap in both copies — `roadmap_html.py`'s was fixed first;
  `roadmap_view.py`'s walk was fixed inline afterward. A shared classifier
  would have made that one fix instead of two.

**#324 — Move `--output` directory/trailing-slash/permission validation to shared CLI infrastructure**

- **What:** `roadmap --view html --output PATH`
  (`cli/roadmap_cmd.py:cmd_roadmap`, the html branch) rejects a destination
  that names a directory, carries a trailing separator on a path that
  doesn't exist yet, or raises `PermissionError` out of `Path.is_dir()` —
  with one specific message and exit code for each. `jira --output PATH`
  (`cli/jira_cmd.py:158`, `Path(args.output).resolve() if args.output else
  None`) performs none of this: the identical operator mistake
  (`jira <slug> --output some_dir/`) proceeds straight to opening a file at
  that path with no directory/trailing-slash check at all.
- **Why now — not fixed alongside `--view html`:** the validation was
  authored and hardened for one new surface; `jira_cmd.py` is
  pre-existing, unrelated code this session's diff never touched. Moving
  the check to shared infrastructure is a real improvement but changes a
  second command's behavior, which is out of the scope that motivated the
  `roadmap --view html` work.
- **Fix:** extract the validation
  (`plan_tool/cli/roadmap_cmd.py`'s destination-name / `is_dir()` /
  trailing-separator / `PermissionError` handling) into a small shared
  helper — e.g. `plan_tool/cli/console.py` or a new leaf — returning either
  a validated `Path` or an error message + exit code, and have both
  `roadmap --view html --output` and `jira --output` call it. Every future
  `--output`-shaped flag inherits the same behavior for free.
- **Also closes a CLI-layering gap in the same spot:** `cmd_roadmap`'s
  `--view html` branch (`cli/roadmap_cmd.py:_cmd_roadmap_view`) inlines the
  full validation-plus-exception-to-return-code mapping directly in the
  dispatcher, unlike every sibling `--view` branch (a one/two-line call into
  a renderer). CLAUDE.md's CLI-layering rule keeps handlers thin and the
  real work in top-level orchestrators; extracting the shared helper this
  entry already calls for resolves both complaints with one change, not two.
- **Effort:** small. **Value:** one operator mistake gets one consistent
  experience across every `--output` surface instead of per-command
  reinvention (or, for `jira`, none at all).

**#325 — Extend `resolve_id_of_kind`'s wrong-kind check past entity-typed references**

- **What:** the domain entity ER diagram work (`--view html`) added
  `roadmap_view.resolve_id_of_kind` and wired it into every place a
  `REFERENCE`-typed field or an `entity_ids` list is rendered
  (`roadmap_html.py`'s table/diagram, `roadmap_view.py`'s `--view walk`),
  so a resolved-but-wrong-row-kind id now warns instead of rendering a
  confident link. The same hazard is unaddressed for every other
  cross-artifact reference-id list `roadmap_html.py` renders:
  `component.pattern_ids`, `component.constraint_ids`, `component.store_ids`,
  `plan.component_ids`, a decision/constraint row's `anchor_ids`, and
  ordering's `depends_on` / `assumption_targets` — all still resolved
  through plain `_ref_list` / `resolve_id`, with no kind check. Separately,
  `roadmap_html.py:_plans_block` already hand-rolls its own one-off
  "ordering entry does not name a plan" check via a raw `resolve_id(...).status`
  branch, duplicating the general mechanism's purpose for one specific kind.
- **Why now — not fixed alongside the ER diagram work:** `design_row_index`
  is one shared id→entries map across every row kind in the roadmap, so an
  id collision across kinds is exactly as reachable for a `pattern_id` /
  `constraint_id` / `store_id` / `component_id` / `anchor_id` reference as
  it was for the `entity_id` references that work fixed — this is
  pre-existing behavior, not something the ER diagram introduced, and the
  diagram itself only draws entities and entity-to-entity edges, so it has
  zero interaction with these other reference kinds. Extending the fix to
  every cross-artifact reference-id list in the file is a substantially
  broader change than "add an ER diagram" — explicitly deferred rather than
  pulled in while touching the same file. (Found and scoped out
  2026-08-31; user confirmed leaving it deferred rather than extending in
  the same session.)
- **Fix:** `resolve_id_of_kind(ref_id, loaded, *, kind: str)` takes exactly
  one expected kind, but `component.pattern_ids` resolves across **both**
  `KIND_SYSTEM_PATTERN` and `KIND_COMPONENT_PATTERN` per
  `ROADMAP_FORMAT.md`'s "resolves across both" contract — the signature
  needs a multi-kind form (e.g. `kind: str | tuple[str, ...]`) before that
  site can use it, not just a new call site. `component.constraint_ids`
  routes through `kind=KIND_CONSTRAINT`, `component.store_ids` through
  `kind=KIND_STORE`, `plan.component_ids` through `kind=KIND_COMPONENT`,
  and each row kind's `anchor_ids` through whatever kind vocabulary anchors
  actually resolve against (anchors may be polymorphic too — check before
  assuming a single `kind=` fits, the same discovery that already applies
  to `pattern_ids`). Fold `_plans_block`'s ad hoc "does not name a plan"
  branch into a `resolve_id_of_kind(..., kind=KIND_PLAN)` call so there is
  one mechanism, not two. `depends_on` / `assumption_targets` need the same
  treatment.
- **Scope contract:**
  - **Outcome:** every `_ref_list`-rendered id in `roadmap_html.py` warns
    on a resolved-but-wrong-kind target the same way entity references
    already do, with no remaining ad hoc kind check duplicating
    `resolve_id_of_kind`.
  - **In scope:** `plan_tool/roadmap_html.py` (every remaining
    `_ref_list`/`resolve_id` call site listed above, and `_plans_block`'s
    hand-rolled check), `plan_tool/roadmap_view.py` only if an equivalent
    gap exists there for these same fields (not yet audited — check first).
  - **Out of scope / Non-goals:** the entity-typed sites this backlog entry
    describes as already fixed; any change to `resolve_id_of_kind`'s own
    signature or `KIND_*` vocabulary beyond adding call sites; the ER
    diagram's own rendering (`roadmap_er.py`) — it has no reference-id-list
    concept at all.
  - **Allowed behavior changes:** a wrong-kind id in any of the listed
    fields now renders a warning marker instead of a confident link/label;
    no other output changes.
  - **Verification:** a fixture per newly-covered field with a same-page
    kind collision, asserting the warning marker and no link — mirroring
    the existing entity-typed tests in `tests/test_roadmap_html.py`.
  - **Stop / defer:** if anchors turn out to be genuinely polymorphic
    (multiple valid kinds per anchor), that's a separate design question,
    not a blocker — defer with a new entry rather than generalizing
    `resolve_id_of_kind` to accept multiple kinds speculatively.
- **Effort:** small-to-medium (mechanical per site, ~7 call sites plus
  `_plans_block`'s consolidation). **Value:** closes the same defect class
  round 4/5 of the ER-diagram code-review loop fixed for entity references,
  for every other reference kind this file renders.

**#133 — Speed up the completeness-audit phase-1 per-step purity check (large prompt, ~130–255s/step)**

- **What:** the per-step mixed-refactor purity check sends a ~140 KB prompt
  per step and takes ~130–255s to return — over 6–7 steps, ~15–25 min of
  phase-1 wall-clock before the conceptual passes even start.
- **Re-triage 2026-08-20 — do not start this on #210's behalf.** The pass
  is now off by default (`--purity` opts in), so it no longer lengthens an
  ordinary audit, which was this entry's entire motivation. #210 is
  passive observation only and may conclude the pass should be cut
  outright — it has reported zero findings across 90 saved reports. Do not
  construct a dedicated audit to settle #210 or optimize this pass;
  revisit only if independently justified `--purity` audits produce
  evidence that the pass should be kept.
- **Levers, if revisited (measure before cutting):** trim the prompt
  (`render_detail_quality_prompt` likely carries more context than the
  judgment needs); cache/opt-in reuse across fingerprint-stable runs (the
  finding is advisory, never blocks). Parallelizing the independent
  per-step calls is **discouraged per CLAUDE.md's anti-parallelism
  directive** — prefer the other two levers first.
- **Dependencies:** relates to #43 (synthesis caching) and #124 (shorten a
  single long Claude round-trip).
- **Approach:** `decision first` — profile before choosing trim vs. cache.
- **Origin:** 2026-07-16 — diagnosed while making the purity check
  hang-resilient; the hang was fixed separately, this is the residual
  slowness.
- **Status:** not started, paused pending #210.

**#270 — `CliBackend.batch_output` is set by every backend but never read**

- **What:** `plan_tool/backend.py`'s `CliBackend.batch_output` field
  (`"stdout"`/`"json"`) is populated by every built-in backend registration
  and round-tripped through `backend.json`, but no production code path
  consults it: `backend_runner.py:_pump_stdout` always calls
  `parse_stream_line` regardless of the value, since the batch lane moved
  onto the shared streaming runner (`batch-authoring-observability` step 6).
  Decide whether to wire it back in (e.g. gate `_pump_stdout`'s parse call on
  it, for a hypothetical backend whose batch output is genuinely plain text)
  or drop it from `CliBackend`, `backend.json`'s schema, and
  `DATA_CONTRACT.md`.
- **Why:** a maintainer registering a new backend with `batch_output="stdout"`
  based on the field's own docstring would reasonably expect it to skip
  structured parsing; it silently does nothing.
- **Approach:** `direct` — either a one-line gate in `_pump_stdout` or a
  schema removal; no open design choice beyond wire-in vs. drop.
- **Status:** not started — backlog entry only.
- **Origin:** 2026-08-13, `/code-review` pass on the
  `batch-authoring-observability` plan's diff.

**#288 — Drop the redundant "Per-step test strategy" block from rendered plan bodies**

- **What:** `create.py:6119`'s `_render_testing_strategy()` appends a
  "Per-step test strategy" block to every plan's `## Testing` section (called
  from `_render_plan_body` at `create.py:6252`), one bullet per step. For
  code steps the bullet text is byte-identical regardless of `change_type` —
  `_TESTING_STRATEGY_BY_CHANGE_TYPE` at `create.py:367-377` maps both
  `refactor` and `feature` to the same sentence ("tests covering the
  behavior this step changes; green before completion."); only `non_code`
  differs. Nothing downstream reads the rendered block back: the run-time
  test-authoring gate (`launcher.py:890`'s `_test_directive()` and
  `launcher.py:953`'s `_step_requires_test_authoring()`) derives its
  directive from `step.change_type` directly, independent of plan-body
  prose. Remove the rendered block; leave `change_type` and its real
  consumers (`launcher.py`, `detail.py`) untouched.
- **Why:** confirmed 2026-08-17 reviewing a bare plan's rendered Testing
  section — 8 of 9 step bullets stated the identical sentence, distinguishing
  nothing per step beyond code/non-code, and no consumer parses the text
  back. It is leftover shape from the withdrawn per-`change_type`
  test-ordering contract (CLAUDE.md § "Withdrawn: the per-`change_type`
  test-ordering contract (2026-07-30)"): the concept still does real work in
  `launcher.py`'s run-time directive and `detail.py`'s authoring prompt, it
  just no longer needs a redundant restatement baked into the plan artifact
  itself.
- **Effort:** small — delete `_render_testing_strategy()` and its call site;
  drop the parts of `_TESTING_STRATEGY_BY_CHANGE_TYPE` that only fed it.
- **Risks / fallout:** `tests/test_create.py` assertions covering the
  block's presence/ordering need updating or removing; any saved fixture
  plan bodies containing the section may need regenerating.
- **Dependencies:** none.
- **Scope contract:**
  - **Outcome:** newly-created plan files no longer render a "Per-step test
    strategy" block in `## Testing`; `change_type`-driven test guidance is
    unchanged everywhere it is actually consumed (`launcher.py`'s run-time
    directive, `detail.py`'s authoring prompt).
  - **In scope:** `plan_tool/create.py`'s `_render_testing_strategy()`, its
    call site in `_render_plan_body`, and `tests/test_create.py` coverage of
    the rendered block.
  - **Out of scope / Non-goals:** the three-way duplication of
    per-`change_type` phrasing across `create.py`/`detail.py`/`launcher.py`
    (flagged but explicitly deferred by `create.py:360-366`'s own comment) —
    do not consolidate those copies here; any change to `launcher.py`'s
    run-time test directive or `detail.py`'s authoring prompt; retrofitting
    already-authored plan files to strip the section from existing
    artifacts.
  - **Allowed behavior changes:** the rendered `## Testing` section in new
    plan files loses the per-step enumeration; no other plan-body section
    changes.
  - **Allowed reorganization:** none.
  - **Verification:** a fresh `create` run's plan body has no "Per-step test
    strategy" block; `tests/test_create.py` updated and green; full suite
    green.
  - **Stop / defer:** if removing the block turns out to break a
    completeness-audit or schema check that silently depended on its
    presence, stop and re-scope rather than patching around it.
- **Approach:** `direct` — a deletion with no open design question, scoped
  to one function and its call site.
- **Status:** not started — backlog entry only.
- **Origin:** 2026-08-17 — user flagged the rendered per-step test-strategy
  block as apparently non-value-add while reviewing
  `docs/implementation-plans/2-roadmap-same-artifact-structural-revision.md`;
  confirmed by tracing the generator (`create.py`) and downstream consumers
  (`launcher.py`, `detail.py`).

**#273 — Consider a shared advisory-lock-release leaf for `_release_writer_lock`/`_release_append_lock`**

- **What:** `tests/test_duplication.py`'s `ALLOWED_DUPLICATE_GROUPS`/`DO_NOT_MERGE["advisory-lock-release-boundaries"]` entry keeps
  `plan_tool/roadmap_revision_publish.py:_release_writer_lock` and
  `plan_tool/telemetry.py:_release_append_lock` separate, citing "each
  release stays coupled to its acquisition policy." Both bodies are
  byte-identical modulo parameter names (confirmed by the test's own AST
  normalization, which is why the pair needed the allowlist entry at all):
  each dispatches on `implementation == "fcntl"` / `"msvcrt"` and calls the
  matching unlock, with no reference to whether its own acquire was
  required (`roadmap_revision_publish.py:_acquire_writer_lock` raises
  `RoadmapWriterGuardError` when no lock implementation exists) or
  best-effort (`telemetry.py:_acquire_append_lock` returns `None`). A shared
  `_release_advisory_lock(fd, implementation)` leaf could serve both
  callers with that differing acquisition policy still enforced entirely at
  each `_acquire_*` call site, which is what makes the rationale as stated
  inaccurate for the *release* pair (see the fixed entry text — it now
  points here instead).
- **Why:** the repo's own duplication rule is that a "deliberately not"
  comment is a claim to pin, not trust; this one didn't hold up when the
  release bodies were read rather than taken on faith. Not fixing it now
  because a merge needs a home for the shared leaf (avoiding an import
  cycle between `roadmap_revision_publish.py` and `telemetry.py`, both of
  which already carry their own `fcntl`/`msvcrt` try/except pair) and its
  own tests — a mid-review consolidation is exactly what CLAUDE.md's
  anti-creep rule says to file, not take.
- **Approach:** `direct` — extract `_release_advisory_lock(fd, implementation)`
  into a small leaf both modules can import without a cycle, point both
  call sites at it, remove the `ALLOWED_DUPLICATE_GROUPS`/`DO_NOT_MERGE`
  entry, and keep the *acquire* functions exactly as they are (that policy
  difference is real and stays put).
- **Status:** not started — backlog entry only.
- **Origin:** 2026-08-14, `/code-review` pass on the
  `roadmap-incremental-revision` / `roadmap-seed-materialization-observability`
  merge.

**#276 — `_TrackFromStage` argparse Action duplicates the `default=None` idiom it sits beside**

- **What:** `plan_tool/cli/roadmap_cmd.py:_TrackFromStage` is a custom
  `argparse.Action` subclass that exists solely to set a second namespace
  field (`from_stage_supplied`) when `--from-stage` is passed — duplicating
  what argparse's own `default=None` plus an `is not None` check at the one
  production use site would express with no custom Action at all.
- **Why:** two fields (`from_stage`, `from_stage_supplied`) set by two
  different mechanisms must stay in sync by hand for no behavioral gain.
- **Approach:** `direct` — remove the Action subclass, default `from_stage`
  to `None` in the parser, and resolve "was it supplied" at the one
  consuming call site.
- **Status:** not started — backlog entry only.
- **Origin:** 2026-08-14, `/code-review` pass on the local-revision-observability
  merge's follow-up direct fixes.

**#277 — `roadmap_writer_guard`'s per-slug cross-process lock may be fully redundant with `repo_mutation_lock`**

- **What:** `roadmap_revision_publish.py:roadmap_writer_guard` is a new
  blocking, per-slug, cross-process fcntl/msvcrt lock. `repo_lock.py`'s
  `repo_mutation_lock` already serializes every CLI-driven `roadmap`
  invocation repo-wide before this code runs.
- **Why:** for every CLI-driven caller, `roadmap_writer_guard` may add no
  protection `repo_mutation_lock` didn't already provide — just extra
  machinery and a second concurrency primitive with different contention
  behavior (see #5's msvcrt bound, tracked separately). If a non-CLI caller
  genuinely needs the finer-grained per-slug lock, that should be stated;
  if not, one of the two locks is dead weight.
- **Approach:** `direct` once the design question is settled — determine
  whether any caller reaches `roadmap_writer_guard` without already holding
  `repo_mutation_lock`, and drop whichever lock turns out to be redundant.
- **Status:** not started — backlog entry only. Not a confirmed bug: noted
  by the reviewing pass as "a documented, not-yet-consolidated design choice
  rather than a clear bug."
- **Origin:** 2026-08-14, `/code-review` pass on the local-revision-observability
  merge's follow-up direct fixes.

**#278 — `materialize_plan_seed` and `materialize_and_diff_one_plan` duplicate their "acquire-or-reuse a writer guard" branch**

- **What:** Both functions in `plan_tool/roadmap.py` repeat an identical
  "acquire a fresh writer guard if none was supplied, else validate and
  reuse the caller's" branch before delegating to their own private twin
  implementation.
- **Why:** a bug fix to the reuse/validation logic must be applied in both
  places by hand, with nothing enforcing they stay in sync.
- **Approach:** `direct`, but not fully mechanical — extraction needs
  `_materialize_plan_seed` to gain a `writer_token` parameter to forward,
  which it does not currently have.
- **Status:** not started — backlog entry only.
- **Origin:** 2026-08-14, `/code-review` pass on the local-revision-observability
  merge's follow-up direct fixes.

**#136 — Finish the #101 seam extraction: generalize the rate-limit helper family onto shared notify + scope params**

- **What:** The #101 `rate_limit_loop` extraction single-sourced the recovery
  *control-flow loop* and the cleanly-shareable seam adapters (the enum→category
  maps, the `classify` seam via `build_classification_from_outcome`, and the
  `wait` seam via `make_wait_seam` — all now in `claude_errors`). It left three
  seam *helpers* still duplicated near-verbatim between `shell.py` and
  `launcher.py`: `_can_prompt_on_rate_limit` (byte-identical),
  `_select_rate_limit_backend`, and `_ask_rate_limit_action` — differing only in
  the notify call (`_notify_or_tool(notifier, …)` vs `_notify_or_print(…)`).
- **Why deferred (structural, not a nit):** `_select_rate_limit_backend` reads a
  **per-module `_rate_limit_backend_scope` ContextVar** — two *deliberately
  distinct* vars (`plan_tool_rate_limit_backend_scope` vs
  `plan_tool_launcher_rate_limit_backend_scope`) whose per-lane scoping is the
  contract the shipped `parallel-rate-limit-switch-scope` plan established.
  Sharing these helpers means threading both the notify sink and that ContextVar
  through a shared implementation (or unifying the two vars) — a real design
  choice with a risk to the invoke-scoped backend-switch semantics, not a
  mechanical hoist. `_can_prompt_on_rate_limit` is a free trivial move; bundle it
  so the family lands together.
- **Effort:** medium. **Approach:** `plan-tool` — a shared `notify`-parameterized
  helper set in `claude_errors`, with the scope-var design decision documented;
  keep shell/launcher rate-limit tests green as the parity oracle.
- **Dependencies:** builds on the shipped #101 extraction; interacts with
  `parallel-rate-limit-switch-scope`'s ContextVar scoping. **Subsumes the
  "de-dup the forked helpers" half of #98** (the same three helpers) — #98 now
  keeps only its non-interactive-`--jobs N`-policy work.
- **Origin:** 2026-07-10 — surfaced by round 6 of the convergence code review of
  the `rate-limit-loop-extraction` run; the loop was stopped here per the
  don't-patch-the-same-region-forever rule (correctness had converged with zero
  bugs across six rounds; the remainder is this structural completion).

**#109 — Reduce `build_plan_footprint` over-work: thread one footprint across the two self-consistency detectors (double build)**

- **Shipped (sub-items 2–4, 2026-07-09, `direct`):** the **over-heavy claim
  build** (`detect_claim_vs_delivery` now uses the zero-I/O `_declared_footprint`
  helper instead of a full footprint), the **double plan read**
  (`detect_orphaned_deliverable` parses the plan body once and threads
  `plan_sections` into `build_plan_footprint`), and the **dead footprint fields**
  (`referenced_paths` / `referenced_symbols` / `declared_symbols_by_step` dropped)
  all landed, adversarially verified behavior-preserving.
- **Remaining (sub-item 1) — double build:** `detect_orphaned_deliverable`
  (battery → `self_consistency_recs`) and `detect_claim_vs_delivery` (via
  `review.collect_smell_findings` → `smell_recs`) **each** call
  `build_plan_footprint`, so it runs twice per audit pass, each re-reading every
  detail body. Thread one `PlanFootprint` through both.
- **Why deferred:** the two detectors sit on **different fan-outs** with no
  shared call frame, so hoisting one build means reshaping the call graph across
  the advisory (`smell_recs`) and blocking (`self_consistency_recs`) lanes.
- **Scope caution:** those lanes are only loosely coupled today; a shared pass
  must not over-couple them for a negligible saving (both read only cheap
  plan/detail markdown). Confirm the redundant cost is worth removing before
  reshaping the call graph.
- **Dependencies:** none — sub-items 2–4 have shipped; `_declared_footprint`
  now exists as the zero-I/O declared side, which a shared build would reuse.
- **Effort:** small. **Approach:** `plan-tool`. **Iterate:** default recipe.
- **Origin:** 2026-07-09 — the double-build was noted during
  `plan-self-consistency-gate` detail authoring (the `[cross-step]` lesson +
  step 4's Deferred note); the high-effort workflow review of the step commits
  surfaced sub-items 2–4 as sibling efficiency findings (now shipped).

**#89 — Extend `--commit` to more mutating commands (wider, consistent commit-hygiene coverage)**

- **Principle:** `untriaged` — commit hygiene; it may bear on `survive-interruption`, which the entry does not say.
- **What:** `--commit` today is accepted by only five surfaces — `run` (per-step
  green commits), `detail`, `completeness-audit`, `completeness-apply`, and
  `manifest sweep`/archive. Several other commands *mutate the repo* (plan files,
  detail files, or code) but leave the working tree dirty for the operator to
  commit by hand. Extend the flag — with each command committing **its own**
  authoring/mutation edits (the `detail`-style meaning, not `run`'s per-step
  green commits) — so unattended pipelines end on a clean tree.
- **Candidates (audit each for a sensible commit unit):**
  - `create` — commit the authored plan file + `.plan-tool/plans.json` manifest
    update + seed archival as one "plan authored" commit. (Today it writes all
    three and leaves them staged-by-hand; this session committed them manually.)
  - `reconcile-plan` / `reconcile-code` — commit the reconcile edits (plan-side or
    code-side) the audit applied, **and** the saved audit report itself:
    `save_review` (`review_persistence.py`) writes `<ts>-run-reconcile.json` /
    `<ts>-detail-reconcile.json` to `plan-details/<slug>/reports/`
    unconditionally (unless `--no-save`) with no git operation of its own, so
    the report is exactly as orphan-prone as the code/plan edits the audit
    makes.
  - `split` / `merge` / `scope-out` — commit the structural mutation (renumber +
    detail migrate/rename, or the narrowed plan + carved seed) atomically.
  - `annotate` — commit the `<name>.annotated.md` + `<name>.seed.md` (and the
    `--archive` move) it emits.
- **Why:** consistency (one flag, one meaning of "commit what you just did"), and
  it closes the manual-commit gap after every mutating verb — the same
  clean-tree discipline the `run --commit` mandate enforces between steps, which
  also avoids the dirty-tree test-authoring-gate masking (see [#87](#c-investigations--decision-making)).
- **Evidence it recurs:** two `reconcile-code` `run-reconcile.json` reports
  (`audit-pass-persistence`, step 3, 2026-08-31 23:12/23:18 UTC) sat orphaned
  — untracked, uncommitted — for a day. The operating habit at the time was to
  sweep saved reports into their own dedicated commit (`644be98a` "save
  reconcile-code reports", `881f8ba3`), but that habit lapsed once six
  subsequent code-fix commits (`08af949d` through `306c9bd9`) landed
  back-to-back with no report files staged at all — nothing in the tool
  forced or reminded either commit to happen. Confirms this entry's
  `reconcile-code` candidate is a real, observed gap, not a theoretical one.
- **Design notes:** keep the two meanings distinct in help text (`run`'s per-step
  green commits vs the other verbs' single authoring-edit commit — CLAUDE.md
  already draws this line). Respect "commit only when the user asks": `--commit`
  is the explicit opt-in. Bounded-commits rule still applies — one concern per
  commit, so a verb touching unrelated areas should say so or stay opt-out.
- **Effort:** small per command (each is a `git add <its outputs> + commit`
  behind the flag), medium in aggregate; do it as one sweep for a consistent UX.
- **Approach:** `plan-tool` (a flag + commit-unit decision per verb, worth a
  paper trail) or `direct` if scoped to one verb at a time.
- **Dependencies:** none; complements the `run --commit` mandate and [#87](#c-investigations--decision-making).
- **Origin:** 2026-07-05 — user, after `create` had to be hand-committed while
  building the auto-bridge-structural-remedies plan.

**#83 — End-to-end bare-plan action-surface regression harness**

- **What:** Add a single integration fixture that drives `completeness-audit`
  and `completeness-apply` on a bare/partially-detailed plan and asserts the
  post-split baseline across every renderer: conceptual-**completeness** gaps
  and deterministic detail-level writers stay withheld; conceptual-**correctness**
  gaps name `plan-tool completeness-apply`; the bare BLOCKED bullet leads with
  `plan-tool detail` on purpose (with `plan-tool split` second); stderr banner,
  stdout/grouped report, saved markdown, saved sidecar replay, and console next
  steps all read one fence via `next_step_gaps`. This complements
  the narrower unit/command pins for #70/C; it is a cross-surface consistency
  harness, not a new behavior change.
- **Provenance:** narrowed 2026-08-03 by the bare-plan-correctness-apply plan
  (axis-split bare-plan fence shipped; this entry no longer pins a
  structural-only surface or forbids `plan-tool detail` in next steps).
- **Effort:** small. Build one temp repo with a bare step plus a partial-detail
  variant, stub the conceptual audit, and inspect the emitted/persisted
  artifacts.
- **Risks:** low. The main risk is brittleness from asserting exact prose; assert
  command/action absence and the presence of one stable bare-plan marker instead
  of full text.
- **Dependencies:** **#70/C shipped in `53b6438`**; this is now a standalone
  regression harness over the shipped gate.
- **Approach:** direct. Test backfill over existing behavior; no design choice.
- **Iterate:** not needed; run the focused CLI/report suites.
- **Origin:** surfaced 2026-06-28 while tightening #70/C. The active change pins
  the summary builders, grouped-report renderer, banner, and
  `completeness-apply` / iterate-loop action gates separately; this item adds
  the end-to-end leak check across all surfaces.

**#79 — Extract the *verified* duplicated leaf helpers (measured, not eyeballed — most of the original list turned out not to be duplication)**

- **Principle:** `none` — consolidation; its claims need re-verifying before any merge.
- **What:** Extract only the helpers proven identical by an AST pass that
  normalizes away docstrings, function names, and argument names. Measured
  2026-08-02 over `plan_tool/` (~91k lines): the whole package holds **6
  exact-duplicate function groups / 7 redundant copies**. This entry ships
  that set and **documents the rest as deliberately separate**, because the
  earlier version of this entry mandated at least three merges that are wrong.
- **Extract (verified pure duplication):**
  - **Durable atomic write** — `_atomic_write_text` is byte-identical in
    `grounding.py:67`, `purity_cache.py:111`, `review_persistence.py:90`
    (`NamedTemporaryFile` → `write` → `flush` → `fsync` → `os.replace`).
    Extract **one** stdlib-only leaf for these three.
  - ~~UTC timestamp~~ — **withdrawn 2026-08-02, see the do-not-merge list.**
    The four bodies are identical, and merging them is still the wrong call.
  - **Repo-relative path display** — three identical pairs:
    `cli/console.py:26` `_short_path` ↔ `create.py:883` `_display_path`;
    `cli/console.py:222` `_repo_rel` ↔ `cli/inspect.py:396` `_display_path`;
    and `review.py:1369` `_repo_relative_posix` ↔ `review.py:6401`
    `_repo_relative_display` (**same file** — the cheapest fix in the repo).
  - **Working-tree dirty check** — `cli/gitcommit.py:23 working_tree_dirty`
    ↔ `cli/run_cmd.py:563 _working_tree_dirty`.
  - **Small pairs** — `launcher.py:485` ↔ `shell.py:259`
    `_can_prompt_on_rate_limit`; `run_log.py:894` ↔ `run_log.py:948` `_sink`
    (same file); `progress.py:110` ↔ `progress.py:164` `notice` (same file);
    `foundational_logic.py:205 _soft_str` ↔ `jira.py:750
    _optional_stripped_str`.
  - **Lenient JSON-envelope slice** — 10 sites across 6 files in **two**
    bracket shapes: object `find("{")…rfind("}")` (`lessons.py` ×2,
    `create.py` ×2, `foundational_logic.py`) and array `find("[")`
    (`create.py` ×2, `gates.py:272`, `annotate.py:430`, `jira.py:1214`). Down
    from the 20 sites this entry once claimed. These are statement blocks
    inside larger parse functions, not standalone functions, so the AST pass
    does not see them — verify each by hand before folding, and parameterize
    the bracket rather than minting two helpers.
    **2026-08-20:** the bracket-parameterized helper landed as
    `plan_tool/response_contract.py:JsonResponseContract` (built for a
    different, broader purpose — pairing a prompt's format instructions
    with its parser — not specifically to close this entry) and was wired
    into 3 of the 10 sites: `foundational_logic.py`, `gates.py:272`, and
    `annotate.py:430`. The remaining 7 — `lessons.py` ×2, `create.py` ×4
    (2 object, 2 array — `create.py` was mid-migration onto the same
    contract as of this note, so recheck before assuming these are still
    local), and `jira.py:1214` — are still local slicing. Migrating them
    onto `JsonResponseContract` is the natural way to finish this bullet.
- **Do NOT merge (measured, with the reason each stays separate):**
  - **`fileio.atomic_write_text` and `lessons._atomic_write_text` are *not*
    the same helper as the trio above — they are three different durability
    contracts.** `fileio` (public, live: `jira_config`, `roadmap`, `create`)
    does `write_text` + `os.replace` — atomic but **not** durable, and it
    `mkdir(parents=True)`. `lessons.py:1009` uses `mkstemp` + `mkdir(parents)`
    and does **not** fsync. The trio fsyncs and does not mkdir. Folding the
    trio onto `fileio.atomic_write_text` is a **silent durability
    regression**. `cli/console.py:189 _atomic_write` is a **fourth exact
    copy**, not a variant: it differs only in parameter names and in importing
    `tempfile`/`contextlib` inside the function body. (An earlier revision of
    this entry called it a near-copy with a different cleanup posture — wrong;
    all four use an inner `finally` for `close` and an outer
    `except BaseException` for the tempfile unlink.)
  - **The 11 `[y/N]` confirm gates.** **Zero** appear in the exact-duplicate
    set at any threshold — they share an *idiom*, not an implementation.
    `scope_out.py:1313 _confirm_scope_out` takes an injectable `prompt_fn`
    seam and composes its message from domain fields (`plan_slug`,
    `carved_ids`); `cli/worktree_cmd.py:285 _confirm` takes a prepared
    prompt string and imports `builtins` locally. Folding them means either
    widening the API for every site that doesn't need the seam or dropping
    `scope_out`'s test seam. The earlier "~10 near-identical sites, fold
    them" instruction was wrong.
  - **The five UTC-timestamp helpers — leave all of them.** Four are identical
    (`annotate.py:580 _utc_timestamp`, `checkpoint.py:221`, `run_log.py:333`
    the public `utc_now_iso`, `telemetry.py:88`) and the fifth,
    `review_persistence.py:265`, **has already diverged**: it emits
    `strftime("%Y-%m-%dT%H:%M:%SZ")` → `2026-08-02T16:06:02Z`, where the others
    emit `.replace(microsecond=0).isoformat()` → `2026-08-02T16:06:02+00:00`.
    Two different wire formats. That divergence is the evidence: these are
    **per-artifact format choices**, not one utility — each feeds a different
    persisted schema (run-log JSONL, checkpoint state, telemetry JSONL, the
    annotate report, saved review sidecars), several drift-guarded through
    `DATA_CONTRACT.md`. Collapsing them makes the *next* per-format change a
    breaking edit to a shared symbol. The arithmetic also fails on its own:
    merging buys ~6 lines of a one-line stdlib call while adding three
    cross-module import edges, and `telemetry.py` currently has **zero**
    first-party imports — a property CLAUDE.md calls load-bearing, because it
    is what lets cycle-sensitive leaves record telemetry at all.
  - **`scope_out._archive_file_strict` ↔ `detail._archive_existing_detail`
    are not byte-identical** (the earlier claim). They have deliberately
    **opposite failure policies**, each stated in its own docstring: strict
    raises `NarrowError` so the apply journal can roll back; detail's is
    best-effort and returns `None` so a permissions error never derails the
    write the caller is about to perform.
  - **`drift_detection.compute_content_hash` ↔
    `review_persistence._hash_file_into`** — different contracts (whole-file
    digest returning `Optional[str]` vs. fold-into-a-caller's-hash returning
    `None`), and `review_persistence`'s docstring says the inline copy is the
    deliberate price of staying a stdlib-only leaf. A shared chunked-read
    core in a new stdlib-only leaf is permissible; collapsing the two
    signatures is not.
  - **`shell_*_invoker` (6 copies: `annotate`, `create`, `detail`, `jira`,
    `review`, `roadmap`)** — identical bodies, and the **highest-risk merge in
    the codebase**. This is the invoker seam; `tests/conftest.py`'s autouse
    gate depends on overriding them *per orchestrator*. Out of scope
    permanently, not just for now.
  - **`backend.py`'s `_*_batch_argv`/`_*_streaming_argv` pairs (×3)** —
    identical today, but two distinct contract points pinned by
    `docs/CODEX_CLI_CONTRACT.md` / `docs/CURSOR_AGENT_CLI_CONTRACT.md` and
    their fixtures. Divergence is the expected evolution.
  - **`bench.py`'s six 2-line `to_dict`** — merging means a shared base class
    across six unrelated result records.
  - **`launcher.py:485` ↔ `shell.py:259` `_can_prompt_on_rate_limit`** —
    identical bodies, and the duplication **is** the seam. Both are passed to
    `rate_limit_loop.run_with_rate_limit_recovery(can_prompt=...)`, and
    CLAUDE.md states that caller-specific concerns there "stay caller-side and
    are **injected**, not unified into the leaf". Unifying them removes the
    streaming and batch invokers' ability to diverge on what "can prompt"
    means.
  - **`foundational_logic.py:205 _soft_str` ↔ `jira.py:750
    _optional_stripped_str`** — `_soft_str` is half of a local two-function
    family (`_soft_str` / `_soft_str_list`, both consumed at
    `foundational_logic.py:195-196`) and only the scalar half is duplicated.
    Extracting one half and leaving its sibling behind is worse than the
    duplicate line.
  - **`renderer.py:207 _display_path`** looks like a fourth path-display copy
    and is not: it catches `(OSError, ValueError)` where the others catch only
    `ValueError`, and falls back to `path.as_posix()` rather than `str(path)`.
- **Constraint:** the homes must stay **stdlib-only leaves** — `fileio.py`
  (writes) and `pathutil.py` (read-only path helpers) are the two that exist;
  a new one (`hashutil.py`) is fine if it imports nothing first-party. This
  keeps `telemetry.py`'s zero-first-party-imports property intact, which is
  what lets cycle-sensitive leaves record at all. Note the same claim about
  `lessons` and `review_persistence` is **false** and was never true here:
  both import `plan_tool.review` (and `lessons` also `checkpoint`/`shell`) at
  module level, so neither is a stdlib-only leaf. Keep `--iterate`/`--no-iterate` and
  per-command help-text variants out of scope (those vary intentionally).
- **Effort:** small — ~180 redundant lines total; one helper per commit. The
  three same-file pairs are minutes each.
- **Risks:** low **for the extract list**, because identity is machine-verified
  rather than eyeballed. The risk this entry now guards against is the
  opposite one: merging a look-alike. Re-run the AST check before folding
  anything not listed above. Direct change → audit → fix → re-audit with
  affected tests each round (CLAUDE.md).
- **Approach:** direct. The extract list is mechanical — extract the leaf,
  migrate call sites, one concern per commit. Two items carry a real decision
  and should land last or not at all: folding `cli/console._atomic_write` into
  the trio (which cleanup posture wins) and the JSON-envelope slice (whether
  one bracket-parameterized helper beats 10 explicit sites).

**#80 — Consolidate duplicated argparse parent parsers into `parser.py`**

- **Principle:** `none` — consolidation of shared argparse parents.
- **What:** Shared flag groups are rebuilt per command module instead of
  in the `parser.py` leaf: `yes_parent` (**15** construction sites as of
  2026-08-02, **12 byte-identical** by an exhaustive args+kwargs AST compare —
  several carry the comment "mirroring the other command modules until the
  shared flag is consolidated into `plan_tool.cli.parser`"),
  `fail_on_findings_parent` (3×: `inspect`/`review_cmd`/`completeness_cmd`),
  `iterate_parent` (~60-line block ×3: `run_cmd`/`completeness_cmd`/`authoring`),
  and the `name` plan positional + its help string (14×, 13 identical).
  Add `make_yes_parent()`, `make_fail_on_findings_parent()`,
  `make_iterate_parent()`, `add_plan_name_arg()` to `parser.py`; each
  `register()` calls them. **Folds in the time-budget cleanup follow-up** — the shared
  `add_iterate_args(parser)` builder that registers the `--iterate` companions
  (incl. `--time-budget`) once belongs in this consolidation.
- **Caveat:** keep the `--iterate`/`--no-iterate` **action itself**
  per-subparser — its default differs (ON for create, OFF for run) and
  argparse parents copy by reference (NOTE at `run_cmd.py:1536`).
  Consolidate only the *companion* iterate flags, not `--iterate`. **Three**
  intentional help-text outliers take an override variant and must keep their
  own text: `gates_cmd.py:216` (where `-y` means "print the suggested gates as
  a report instead of prompting" — *different flag semantics* under the same
  name, so the generic string would be actively false), `scope_out_cmd.py:160`
  (documents the `--apply` mutation gate), and `worktree_cmd.py:509` (explicit
  `dest`/`default`; added with the `worktree` verb group after this entry was
  first written, which is why the count moved from 14 to 15). Re-derive the
  identical set before consolidating — compare every
  `yes_parent.add_argument(...)` call's args **and** kwargs after implicit
  string-concatenation folds, not the source text, or the differently-wrapped
  `bench_cmd.py` copy reads as a variant when it is not.
- **Effort:** small. ~300+ lines removed, mechanical.
- **Risks:** low. `--help` text becomes consistent (a behavior change, but
  a desired one). Guard with the existing CLI-reference drift test
  (`tests/cli/test_cli_reference.py`) — regenerate `docs/cli/` after.
- **Approach:** direct. Explicitly TODO'd in-code; natural home already
  exists.

**#81 — Extract the byte-identical sub-blocks shared by the 4 convergence loops (NOT a unified driver)**

- **Principle:** `none` — extraction of sub-blocks shared by the convergence loops.
- **What:** The `gates → apply_finding → re-audit` convergence loop is
  implemented four times (`create.py`, `detail.py`,
  `cli/completeness_cmd.py`, `cli/reconcile.py`). The **outer while-loop
  skeleton + per-iteration body is intentionally duplicated** — see
  **Lessons learned, Lesson 12** ("The convergence module is intentionally
  narrow"): a unified `run_iteration_loop` driver is a documented trap
  because each caller's body genuinely diverges (regenerate steps JSON /
  re-render one detail body / `BLOCKED-STRUCTURAL`→`escalate_to_split` /
  persist a report sidecar / `run_step` walk), and `convergence.py` stays a
  pure-logic primitive with no first-party imports. **This entry does NOT
  propose a driver** — only the extraction of the *incidental* verbatim
  sub-blocks that are not the divergent body:
  - pre/post-apply drift guards — 31 body-local re-imports of
    `check_drift`/`emit_drift_halt_warning` across the four →
    `pre_apply_drift_guard`/`post_apply_drift_guard` in `drift_detection.py`.
  - the `apply_finding`+run_logger phase-wrap (identical `finding_label`
    lambda) → `dispatch_apply_finding_logged`. **Now a 5th call site**
    (`cli/completeness_apply_parallel.py:replay_results`, added 2026-07-17
    closing the #74/B2 run-log gap) — same phase name/extras, its own
    `_finding_label` copy (which collides in *name*, not contract, with an
    unrelated `_finding_label` already in `cli/data_contract_cmd.py`). Fold
    this site in too when the extraction lands; consider sourcing the label
    from `Recommendation.title` (already the same "first body line"
    derivation, per `review.py`'s `_parse_plan_audit_findings`) instead of
    each site re-splitting `rec.body`. **Historical 2026-08-28:** the two
    behavior bugs found in this shared shape shipped independently in
    `2c4eae3c`, with their own tests, rather than being silently absorbed as
    an incidental behavior change inside a "pure move" refactor.
  - the triage-partition + "all-deferred → halt" short-circuit
    (`reconcile.py:1795` comments "Mirrors the peer short-circuits in
    cmd_completeness / create.py / detail.py") → `partition_and_maybe_halt`.
  - the loop-stop banner → `render_loop_stop_banner` (create's
    `_open_findings_hints` already exists but is unreused).
- **Effort:** medium.
- **Risks:** medium — four behaviors must stay identical. Land each
  sub-block incrementally, green on the full suite before the next. The
  autouse invoker gate in `tests/conftest.py` catches any accidental
  real-Claude spawn from the extracted apply-wrap. Keep the extracted
  helpers as leaves (don't add first-party imports to `convergence.py`).
- **Approach:** plan-tool. Multi-module refactor; paper-trail worthy.
  **Bounded by Lesson 12 — stop at sub-block extraction; do not unify the
  loop driver.** If a sub-block can't be extracted without threading
  caller-specific state through it, that block IS part of the divergent
  body — leave it duplicated.
- **Explicitly NOT in scope:** (a) a unified convergence driver (Lesson 12);
  (b) unifying `launcher.escalate_to_split` and
  `scope_out.scope_out_step` apply-or-recommend gates — their parallelism is
  intentional design symmetry (divergent outcome enums; one spends Claude via
  an `invoker=` seam, the other is deliberately zero-Claude). Skip unless a
  third actuator appears; (c) the two run-log behavior bugs named above —
  see `BUG_BACKLOG.md`, fixed independently of this refactor.

**#54 — Lesson 7 audit on `_iterate_reconcile_loop`'s auto-reconcile wiring**

- **Principle:** `untriaged` — a test-coverage slice; which principle it serves is a judgment call.
- **What:** `cmd_completeness`'s auto-reconcile path is well-tested;
  the equivalent wiring in `_iterate_reconcile_loop`, `create_plan`,
  and `generate_detail` may not be. Mirror the test pattern to each.
- **Effort:** small per call site.
- **Approach:** direct. Pattern-mirror across three call sites with
  a known reference test; no design decisions.

**#55 — Performance: short-circuit `_compute_content_hash` via mtime**

- **Principle:** `none` — performance; its own entry says the value is uncertain until profiled.
- **What:** If a watched file's mtime is unchanged since the
  snapshot was taken, skip the SHA-256 hash entirely. Cheap mtime
  check + correct semantics (mtime change is a necessary precondition
  for content change).
- **Effort:** trivial.
- **Value:** uncertain — only matters if profiling shows the hash
  cost is meaningful on a real repo. Defer until there's a profile.
- **Approach:** direct. Trivial change to a single function once
  profiling motivates it.

**#56 — Add a linter (ruff) + pre-commit gate**

- **Principle:** `none` — a repository lint gate, not a property of the tool's output.
- **What:** The repo has no lint step (CLAUDE.md: "no separate
  lint/build step beyond pytest"). Adopt `ruff` (lint + format,
  subsumes flake8/isort/pyupgrade/black) as the standard: add it to
  the dev dependency group, add a `[tool.ruff]` config to
  `pyproject.toml`, and wire a `pre-commit` hook into the existing
  tracked `scripts/hooks/` setup (alongside the `pre-push` suite guard)
  that lints staged Python.
- **Effort:** small for the wiring; **medium once the existing-code
  cleanup is counted.** A probe on 2026-06-16 found **368 violations**
  under ruff's default `E,F` ruleset (264 `F401` unused-import, 59
  `E402` import-not-at-top, 15 `F811` redefine, 8 `F541`, 8 `F821`
  undefined-name, 6 `F841`, 5 `E741`, 3 `E731`); 287 are
  `--fix`-autofixable. The 8 `F821` undefined-name hits are worth a
  look — they may be real bugs, not style.
- **Risks:** a strict repo-wide ruleset blocks every commit until the
  backlog of violations is cleared. Mitigations to decide in the plan:
  (a) autofix the 287, hand-fix the rest, then enable repo-wide; or
  (b) lint only staged/changed files in the hook so legacy code doesn't
  gate day-one, and tighten later; or (c) start with a narrow ruleset
  (e.g. `F` only) and grow it. `E402` (59 hits) is often legitimate in
  this codebase (deferred imports to keep leaf modules cycle-free) — it
  likely needs a per-file ignore rather than a fix.
- **Dependencies:** none. The tracked-hooks scaffold
  (`scripts/hooks/install.sh`, `core.hooksPath`) already exists, so the
  pre-commit hook slots in beside `pre-push`.
- **Origin:** Requested 2026-06-16 while adding the CLI-reference
  pre-push hook; deferred to backlog rather than implemented inline
  because the existing-code violation count makes it a scoped task, not
  a one-liner.
- **Approach:** plan-tool. The wiring is trivial, but the
  rollout strategy (which rules, fix-vs-ignore the 368, staged-only vs
  repo-wide, the `F821`/`E402` judgment calls) is a multi-decision
  cleanup worth a paper trail.

**#176 — Run-log writers for the remaining Claude-spending verbs (`jira`, `annotate`, `merge`, `reconcile-plan-walk`)**

- **What:** these four spend Claude and open no run log at all — no cost
  record, no `in-flight.json`, nothing in `plan-tool runs list`. Verified
  empirically against every saved log in this repo: the only `run_start`
  commands ever recorded are `run`, `completeness`, `detail`, `create`,
  `completeness-apply`, `run-reconcile`, `detail-reconcile`, `split`,
  `suggest-gates`, and (as of `741fdf6`) `reconcile-plan` / `verify-all`.
  Statically, `cli/jira_cmd.py` and `cli/annotate_cmd.py` contain no
  `RunLogWriter` reference; `merge` and the standalone `reconcile-plan-walk`
  likewise. `annotate` is one call per file, so a batch run multiplies it.
- **Why:** an unlogged verb is invisible to the whole observability surface —
  `runs list` / `runs diff` / `runs profile`, the in-flight "is it hung?"
  recipe in RUNBOOK, and any cost attribution. The 2026-07 purity-scan
  failures were undiagnosable for weeks for exactly this reason and only
  became measurable once `8b7615c` logged the phase.
- **How:** the shape is settled — `741fdf6` did it for `reconcile-plan` and
  `verify-all`: a thin wrapper owning `RunLogWriter.start` plus one `finally`
  recording the body's real rc, and a `bind_shell_sink` around the
  orchestrator call. Reuse `cli/review_cmd.py:_run_logged_audit` /
  `_audit_sink` rather than re-deriving it (moving them to a shared leaf is
  a judgment call for whoever takes this — see Allowed reorganization).
- **Scope contract:**
  - **Outcome:** each of the four verbs writes one run log per invocation,
    with its Claude calls recorded under a named phase.
  - **In scope:** `plan_tool/cli/jira_cmd.py`, `plan_tool/cli/annotate_cmd.py`,
    the `merge` handler in `plan_tool/cli/authoring.py`, `cmd_review_walk` in
    `plan_tool/cli/review_cmd.py`; their tests.
  - **Out of scope / Non-goals:** #177 (the slug pre-log ordering), the
    already-satisfied `run` phase attribution, adding new run-log *event kinds* or
    fields; changing `DATA_CONTRACT.md`; any orchestrator signature change
    (bind the sink at the command level, as `741fdf6` did).
  - **Allowed behavior changes:** a `.plan-tool/runs/<slug>/` log appears for
    these four verbs. Nothing else — no output, rc, or prompt changes.
  - **Allowed reorganization:** promoting `_run_logged_audit` / `_audit_sink`
    out of `review_cmd.py` into a shared CLI leaf **is** permitted here,
    since three of the four callers live in other modules and importing from
    `review_cmd` would create a new edge between command modules. Smallest
    move only: the two helpers, no adjacent refactor.
  - **Verification:** per verb, one test asserting `run_start`'s `command`,
    a single `run_end` with the real rc, and no leftover `in-flight.json`;
    plus a sink test on at least one (drive `shell._emit_call_end` and assert
    the phase override), mirroring `tests/test_review.py`'s.
  - **Stop / defer:** if a verb turns out to need a *nested* log (e.g.
    `direct-jira` chaining `jira`), file that separately rather than
    inventing nesting semantics here.
- **Risks / fallout:** low. The one live trap is a test asserting no
  `.plan-tool` directory as a proxy for "nothing was saved" — `741fdf6` hit
  exactly that in `test_no_save_skips_persistence`. Decide per verb whether
  a `--dry-run` opens a log; the precedent set in `741fdf6` is **no** (the
  log exists iff the verb may spend Claude, matching `--refresh` and
  `convergence`).
- **Dependencies:** none. `741fdf6` is the reference implementation.
- **Effort:** small — four mechanical wrappers against a settled pattern.
- **Approach:** `direct` — the design question was answered by `741fdf6`;
  what's left is applying it four times.
- **Quality:** `audit-coverage` — makes the spend of four verbs observable at
  all, which is the precondition for diagnosing anything about them.
- **Origin:** 2026-07-28, logging-gap audit run after the empty-response
  entry in `BUG_BACKLOG.md` proved only measurable once `8b7615c` added
  `purity_scan` logging.

**#177 — Decide how `create`'s slug proposal gets logged (it runs before the log exists)**

- **What:** `create.py:suggest_slug` makes a Claude call that no run log can
  currently record. `cli/authoring.py` must resolve the slug **before**
  `RunLogWriter.start` because the log's path is keyed by the resolved slug
  (the comment at `authoring.py:486` says so explicitly). So this is not a
  missing sink — it is an ordering constraint that needs a decision.
- **Options:** (a) start the log under a provisional slug and rename the
  directory once resolved; (b) buffer the call's `ClaudeCallEnd` and flush it
  after `start`; (c) accept it as a documented pre-log call and say so in
  `RUNBOOK.md` so the gap is known rather than surprising.
- **Update 2026-10-02:** `create` with an explicit slug, which skips the slug
  proposal, still prints the unsinked-call warning (after the distill step), so
  `suggest_slug` is not the only unlogged call in `create`. Which call it is
  stays unproven until the warning can name its caller (BUG_BACKLOG, "The
  unsinked-call warning names the rate-limit retry loop instead of the call that
  ran"); settle that before choosing among (a)–(c).
- **Why it matters:** every `create` makes this call, so it is a small but
  permanent hole in cost accounting — and (c) is a legitimate outcome, which
  is what makes this a decision entry rather than a fix.
- **Scope contract:**
  - **Outcome:** one decision, recorded, and implemented (option c = a doc
    change).
  - **In scope:** `plan_tool/create.py:suggest_slug`,
    `plan_tool/cli/authoring.py`'s slug-then-start ordering, `RUNBOOK.md`.
  - **Out of scope / Non-goals:** #176 and the already-satisfied `run` phase
    attribution; changing how run-log paths are keyed for any other command;
    retrofitting historical logs.
  - **Allowed behavior changes:** under (a), the run-log directory name may
    change mid-run — that is the option's whole cost and must be weighed
    against `runs`/`in-flight` readers.
  - **Allowed reorganization:** none.
  - **Verification:** whichever option ships, a test pins it — the rename
    under (a), the flush under (b), or the RUNBOOK sentence under (c).
  - **Stop / defer:** if (a) or (b) turns out to need `run_log.py` schema
    changes, stop and re-file — this entry is capped at the ordering.
- **Risks / fallout:** (a) touches the in-flight snapshot path that RUNBOOK's
  hung-run recipe reads; (b) adds a buffer to a module that has none today.
  (c) has no code risk.
- **Dependencies:** none.
- **Effort:** small (c) to medium (a).
- **Approach:** `decision first`, then `direct` — the implementation is small
  under every option; picking the option is the work.
- **Quality:** `audit-coverage` — closes or documents a known hole in
  per-command cost accounting.
- **Origin:** 2026-07-28, same logging-gap audit as #176. Filed after an
  initial read wrongly called it a mechanical sink wrap; the ordering
  constraint is what makes it a decision.

**#180 — Make structural renumbering comprehensive: split/merge/scope-out must update detail-file headings and cross-references, not just file names**

- **What:** `plan-tool split` (and the same renumber path used by `merge` and
  `scope-out`) renames detail files and repairs `depends_on`, but leaves every
  human-readable step reference stale. After a split it does not update: the
  `# Step N — …` H1 **inside** each renamed detail file; prose cross-references
  in sibling detail files and the plan body (`step 7 owns …`, `steps 3–7
  shipped …`, `owned by step 9`); execution-order strings such as
  `1 → 2 → 3 → 5 → 6 → 7 → 4`; and Deferred/Input bullets that assign ownership
  by step number.
- **Evidence:** two consecutive splits of `jira-grade-01-detail-instrument`
  (2026-07-28/29) each required a hand sweep afterwards — roughly 90
  references across eleven detail files plus the plan body, and both times a
  renamed file kept an H1 naming its old number (`10-run-one-off-…md` titled
  `# Step 8`). A `scope-out` carve on the same plan (2026-07-29) confirmed the
  gap covers all three verbs: the docs step's file was renamed `11-…` → `10-…`
  while its H1 still read `# Step 11`. The plan's own completeness audit then
  filed the leftovers as findings (`step7-split-attribution`, and a recurring
  `validator-before-producer` whose latest form was a stale execution-order
  string), so the tool's incomplete rename becomes audit churn the operator
  pays for twice.
- **A carve is worse than a renumber, and needs its own handling.** After a
  split, a stale reference is off by one — wrong but visibly odd. After a
  `scope-out`, the referent is *gone* and its id is inherited by a different
  step, so every surviving "step 10 owns X" points at a real but **wrong**
  step. That misleads silently. For carved ids, the rewrite cannot renumber;
  it must flag each surviving reference to the removed step ("referred to the
  carved step; now in <seed>") and let the operator resolve the sentence —
  reporting, not guessing, same as the ambiguity policy below.
- **Why it matters:** the renumber is *already* the tool's job — it repairs
  `depends_on` precisely because dangling ids are a correctness problem. Prose
  references are the same class of dangling pointer, just unenforced: nothing
  validates them, so they rot silently and mislead the implementer that a later
  step reads. It also undercuts the structural remedies the tool recommends: an
  operator told to `split` pays an invisible hand-fix tax, which is a reason not
  to take the advice.
- **Staged first slice — ship the read-only report before any rewriting.**
  After a renumber or carve, grep the surviving detail files and plan body for
  `[Ss]tep N` references to moved or carved ids and print them ("7 references
  to carved step 10 survive — review these"), rewriting nothing. This needs no
  ambiguity policy, so it can land first and independently; it turns the manual
  sweep into a checklist even before the rewriter exists, and the rewriter then
  reuses its scan.
- **Sketch:** the renumber already computes an old→new id map. Apply it to (a)
  the H1 of each detail file it renames, (b) `[Ss]tep N` / `[Ss]teps A–B`
  references in every detail file and the plan body. Do it in one pass with the
  map applied atomically (descending, or via a single-pass regex) so shifts do
  not cascade. Ambiguity is real — a reference may mean either half of a split
  step — so report what it rewrote and flag references it could not resolve
  rather than guessing silently.
- **Scope contract:**
  - **Outcome:** after a `split`/`merge`/`scope-out`, no detail file's H1 names
    a stale step number and no `[Ss]tep N` prose reference points at an id the
    renumber moved; anything ambiguous is reported, not silently rewritten.
  - **In scope:** the shared renumber path (`plan_tool/scope_out.py`'s
    `apply_narrow` / the split executor's migrate-and-renumber), the detail-file
    H1, prose references in detail files and the plan body, and a report of
    what changed.
  - **Out of scope / Non-goals:** rewriting prose that names a step by *title*
    rather than number; touching archived plans; renaming test functions or
    code symbols that embed a step number; any change to `depends_on` repair,
    which already works.
  - **Allowed behavior changes:** split/merge/scope-out diffs grow to include
    sibling detail files and the plan body — that is the point, and it must be
    visible in the command's summary so the operator can review it.
  - **Allowed reorganization:** extracting the renumber's reference-rewriting
    into a small helper shared by the three verbs.
  - **Verification:** a test that splits a fixture plan whose detail files carry
    H1s and cross-references, and asserts every H1 matches its step id and no
    reference points at a moved id; plus a case pinning that an ambiguous
    reference is reported rather than rewritten.
  - **Stop / defer:** if disambiguating "which half of the split does this
    reference mean" needs a Claude call, stop — report the ambiguous references
    and let the operator resolve them. This entry is deterministic text
    rewriting, not a judgment surface.
- **Dependencies:** none.
- **Effort:** medium — the map exists; the work is applying it widely and
  deciding the ambiguity policy.
- **Approach:** `plan-tool` — touches three verbs' shared renumber path and
  changes what a mutation writes, so it goes through a plan.
- **Quality:** `audit-coverage` — stale cross-references are a recurring source
  of completeness findings that the tool itself creates.
- **Origin:** 2026-07-29, after two splits of `jira-grade-01-detail-instrument`
  each needed a manual reference sweep and the audit filed the leftovers.

**#183 — `scope-out`'s blocked-path advice should name the small fix, not jump to re-decomposition**

- **What:** when the carve safety gate refuses (correctly), the only remedy the
  warning offers is total: "To restructure anyway, re-seed and re-decompose the
  whole plan." Observed 2026-07-29 carving step 10 of
  `jira-grade-01-detail-instrument`: the gate reported
  `[inbound-dependent] step(s) [11] depend_on carved step(s) [10]` — and the
  actual fix was deleting one id from step 11's `depends_on`, under a minute of
  work. The tool already knows the exact blocking edge (it printed it) but
  recommends the most expensive remedy that exists.
- **Why it matters:** an operator who trusts the printed advice re-decomposes a
  whole plan to remove one edge. The gate's job is to stop an unsafe carve; the
  message's job is to route to the *cheapest* safe path, and today it routes to
  the dearest.
- **Sketch:** per blocking reason, print the targeted remedy first, derived from
  the edge the gate already computed:
  - `inbound-dependent` → "step(s) [11] depend on the carved step; if that
    dependency should not survive the carve, remove `10` from step 11's
    `depends_on` (edit the frontmatter) and re-run — or repoint it to the step
    that inherits the carved work." Then, and only then, the re-seed line as
    the fallback for when the dependency is real.
  - Same treatment for each other refusal reason the gate can emit — enumerate
    them and give each its cheapest remedy.
- **Scope contract:**
  - **Outcome:** every scope-out refusal message names the specific blocking
    edge(s) and the smallest edit that clears each, with re-seed demoted to the
    explicit fallback.
  - **In scope:** the refusal-message construction in `plan_tool/scope_out.py`
    (and `cli/scope_out_cmd.py` if the wording lives there); a test per refusal
    reason pinning that the targeted remedy is printed.
  - **Out of scope / Non-goals:** auto-applying the remedy (editing
    `depends_on` for the operator is a mutation and stays behind the existing
    apply gates); changing what the gate blocks; the convergence command's
    printed recipes.
  - **Allowed behavior changes:** message text only.
  - **Allowed reorganization:** none.
  - **Verification:** a fixture plan with an inbound dependent; assert the
    refusal names the edge and the one-line fix before any re-seed suggestion.
  - **Stop / defer:** if a refusal reason has no safe cheap remedy, say so in
    its message rather than inventing one.
- **Dependencies:** none.
- **Effort:** small — message construction from data the gate already has.
- **Approach:** direct — bounded wording change with tests.
- **Quality:** `advice-quality` — the tool's printed guidance is part of its
  output; advice that escalates a one-line edit into a re-decomposition is a
  defect in that output.
- **Origin:** 2026-07-29, first real scope-out exercise (jira-grade-01).

**#184 — Configure the repository seed directory**

- **What:** seed writers share the default
  `docs/implementation-plans/plan-seeds/`; existing root-level seeds and recorded
  roadmap publication layouts remain in place. A consuming repository can still
  need a different project-owned seed destination. This entry owns project-level
  configuration, not the shipped nested-default choice.
- **Why it matters:** the seed is the carve's whole output; writing it where
  the operator's convention does not look is a quiet way to lose the carved
  scope. The tool already has layered config (`project_config.py`) for exactly
  this kind of per-repo path decision.
- **Sketch:** resolve the seeds directory the same way other per-repo paths
  resolve — a `seeds_dir` key in `.plan-tool/config.json` (project) falling
  back to the `docs/implementation-plans/plan-seeds/` default — and use it from every default seed writer, preserving explicit
  per-command overrides
  and existing roadmap publication destinations.
  Print the resolved path in the success line (already done) so the operator
  sees where it went either way.
- **Scope contract:**
  - **Outcome:** one config-resolvable seeds directory used by every seed
    writer; default unchanged.
  - **In scope:** `plan_tool/scope_out.py`, `plan_tool/reground.py`, the
    config read (`project_config.py` pattern), docs of the key, tests.
  - **Out of scope / Non-goals:** migrating existing seeds; changing
    `create --from-existing`'s reading side (it takes an explicit path);
    reconciling this repo's own two directories (that is a repo-hygiene
    decision, not tool code).
  - **Allowed behavior changes:** none by default — only when the new key is
    set.
  - **Allowed reorganization:** extracting a shared `resolve_seeds_dir` helper.
  - **Verification:** with the key set, both writers land seeds there; without
    it, retain the nested default and existing publication destinations.
  - **Stop / defer:** if config layering questions grow (env override? user
    level?), ship project-level only and note the rest here.
- **Dependencies:** none.
- **Effort:** small.
- **Approach:** direct — a path-resolution change behind existing config
  machinery.
- **Quality:** `output-placement` — output written where the operator's
  convention does not look is output lost.
- **Origin:** 2026-07-29, scope-out exercise; noticed the repo's own layout
  disagrees with the hardcoded path.

**#185 — `scope-out --into-seed <path>`: carve into an existing seed instead of always minting a standalone**

- **What:** `scope-out` always writes a new standalone seed, even when the
  carved scope already has a named owner. Observed 2026-07-29: the plan body of
  `jira-grade-01-detail-instrument` explicitly named
  the now-withdrawn Jira-grade quality-ledger seed as the home of the scope
  being carved, yet the carve minted a competing standalone seed that then had
  to be folded into that seed by hand and deleted — manual work the command
  created for itself.
- **Sketch:** an `--into-seed <path>` option that appends a clearly-marked
  section to the named seed (e.g. `## Carved from <plan> step N (<date>)`,
  followed by the same rendered scope the standalone seed would carry) instead
  of creating a file. Keep the seed-first ordering guarantee: the append lands
  and is flushed before the plan is narrowed, exactly like the standalone
  write. Refuse politely if the target does not exist or is not a seed-shaped
  markdown file — no implicit creation, since a typo'd path silently minting a
  new seed is the confusion the flag exists to remove.
- **Scope contract:**
  - **Outcome:** a carve can land its scope inside an existing seed, marked and
    attributed, with the same all-or-nothing ordering as the standalone path.
  - **In scope:** `plan_tool/scope_out.py` (seed rendering/writing),
    `plan_tool/cli/scope_out_cmd.py` (the flag), tests, `RUNBOOK.md`'s
    scope-out walkthrough.
  - **Out of scope / Non-goals:** merging or de-duplicating against the target
    seed's existing prose (append-only; reconciling is the operator's edit);
    any Claude call; `reground`'s re-baseline seed (separate writer, can adopt
    the flag later).
  - **Allowed behavior changes:** none without the flag.
  - **Allowed reorganization:** none.
  - **Verification:** append lands before the narrow (crash between the two
    leaves the target seed appended and the plan untouched); marked section
    carries plan, step, and date; missing target refuses without mutating
    anything.
  - **Stop / defer:** if append-position choices multiply (before/after which
    section?), ship end-of-file append and note refinements here.
- **Dependencies:** none; composes with #184 (the default directory only
  matters when no explicit target is given).
- **Effort:** small/medium — the rendering exists; the work is the append
  path and its ordering guarantee.
- **Approach:** direct — a bounded option on an existing deterministic writer.
- **Quality:** `advice-quality` — the tool told the operator the scope's owner
  and then ignored it.
- **Origin:** 2026-07-29, scope-out exercise (jira-grade-01 falsification
  carve folded into the stage-03 ledger seed by hand).

**#186 — Carved seeds inherit no fence: the seed must state what the parent kept, so the carve can't be silently re-absorbed**

- **What:** a backlog-derived seed is required to carry its source entry's
  scope contract forward (see the scope-contract rule in `docs/TRACKING.md`), but a *carved*
  seed inherits nothing about the parent: the 2026-07-29 carve of
  `jira-grade-01-detail-instrument`'s falsification step produced a faithful
  copy of the step with no statement of what the parent plan retained, why the
  scope was carved, or any fence against re-absorbing it. The carve is usually
  *performed to enforce a boundary* — and its own output is the one document
  that doesn't mention the boundary.
- **Why it matters:** the seed becomes a future `create --from-existing` input.
  Without a fence, the next plan authored from it can legitimately expand back
  into everything the parent kept — the audit loop will even help it, since
  completeness audits chase uncovered scope. The anti-creep machinery exists
  everywhere except the artifact most likely to reintroduce the creep.
- **Sketch:** the carved seed gains a deterministic fence section rendered from
  data the carve already has — no Claude call:
  - **Carved from:** parent plan, step id/title, date (already rendered).
  - **The parent keeps:** the narrowed plan's remaining step titles, so the
    boundary is explicit.
  - **Why carved:** taken verbatim from a new optional `--reason "…"` flag;
    omitted (with a placeholder telling the author to fill it in) when not
    given — the tool must not invent a rationale.
  - **Fence:** one sentence template — "A plan authored from this seed covers
    the carved scope only; the items under 'The parent keeps' are out of
    scope here, and audits of that plan defer findings about them to the
    parent or the backlog."
- **Scope contract:**
  - **Outcome:** every carved seed states its origin, the parent's retained
    scope, and an explicit out-of-scope fence, deterministically rendered.
  - **In scope:** `plan_tool/scope_out.py:render_carved_seed`, the optional
    `--reason` flag in `cli/scope_out_cmd.py`, tests,
    `docs/CREATE_FROM_EXISTING_FLOW.md` (a note that `create` should respect a
    seed's fence section).
  - **Out of scope / Non-goals:** making `create`/the audit *enforce* the fence
    (that is seed-content-honoring behavior with its own entry if wanted);
    retrofitting existing seeds; `reground`'s re-baseline seed (same idea,
    separate writer — adopt after this proves out).
  - **Allowed behavior changes:** carved-seed content grows a section; no
    behavior change elsewhere.
  - **Allowed reorganization:** none.
  - **Verification:** a carve's seed carries all four parts; `--reason` text
    lands verbatim; without `--reason` the placeholder is present; rendering is
    deterministic (no invoker seam).
  - **Stop / defer:** if writing "The parent keeps" needs summarization beyond
    listing retained step titles, list the titles and stop — summarizing is a
    judgment surface this entry deliberately avoids.
- **Dependencies:** none; composes with #185 (the fence section rides the
  append) and #180 (the fence names the parent, which the reference report can
  point at).
- **Effort:** small — template rendering from data in hand.
- **Approach:** direct — deterministic renderer change with tests.
- **Quality:** `anti-creep` — the carve exists to enforce a boundary its own
  artifact never states.
- **Origin:** 2026-07-29, scope-out exercise; the carved falsification seed
  carried no fence against the re-expansion the carve was performed to prevent.

**#207 — Detect concept-naming discontinuity: one concept, two words within a plan's own bundle**

- **What:** a check that flags when a plan's own artifacts (plan body, detail
  bundle, seeds) name one concept two ways — the *vocabulary* half of
  `CLAUDE.md` § "Documentation is forward-looking", whose sweep rule has two
  halves and says outright that this is the half that gets skipped. **#180**
  mechanizes the other half (identifiers: step numbers, cross-references,
  headings); **#189** is a one-time retroactive doc sweep. Neither recurs, and
  neither looks at nouns.
- **Why — measured on this repo, twice.** The `jira-grade` arc shipped its
  axis as **grade** everywhere in code (`--grade`, `--detail-grade`,
  `plan_tool/jira_grade.py`, `detail_grade`) while the plan body, all eight
  detail files, the then-active forward seeds, BACKLOG #164, and two reference
  docs called it **depth** — roughly 60 sites, missed piecemeal across four
  `reconcile-code` rounds because no check looks for it directly.
- **The design constraint that decides whether this is worth building.** The
  naive form — match prose against a synonym list — is the **exact shape** of
  the withdrawn `change_type` test-ordering checker (`CLAUDE.md` §
  "Withdrawn: …"), measured at an ~85–89% false-positive rate, whose lesson is
  that an advisory at that rate becomes noise operators learn to ignore. **Do
  not build that.** Key on a **referent**, not a phrase: a noun the plan uses
  *as the name of a surface it ships* which appears in **no shipped
  identifier** (symbol, CLI flag, path, doc heading). Homonyms
  (`probe --depth`, "history depth", "Link depth", "complexity-scaled audit
  depth") survive because they name no shipped surface; a genuine rename does
  not.
- **Scoped to the completeness lane only** — internal consistency, no code
  needed: the plan body, its detail bundle, and its seeds use two different
  words for one concept. Deterministic and cheap. **The reconcile lane**
  (checking a shipped-surface noun against the actual code identifier it
  names, which needs a shipped-identifier index) is split into its own entry,
  **#319**, contingent on this lane proving its false-positive rate is
  acceptable first.
- **Effort:** small–medium.
- **Risks / fallout:** false positives are the whole risk, and the precedent
  above says an advisory that cries wolf takes the channel down with it. Ship
  advisory-only, out of `APPLY_ELIGIBLE_SOURCES`, and measure the rate on this
  repo's own corpus **before** widening — the jira-grade arc is a ready
  labeled fixture, since the correct answer for every "depth" site is now
  recorded in commits `8b33a77e`, `fa454b8b`, and `c66f5c9b`.
- **Dependencies:** independent of #180 (identifiers) but the natural sibling;
  land after it so the two halves of the sweep rule are mechanized together.
- **Scope contract:**
  - **Outcome:** a plan whose own artifacts name one concept two ways gets one
    advisory finding naming both words and the sites, before the divergence
    reaches a seed or a shipped surface.
  - **In scope:** the detection, its finding source, and tests.
  - **Out of scope / Non-goals:** the reconcile (against-code) lane — see
    #319; auto-renaming (a rename is a judgment call — which word wins is the
    author's); a general prose style or synonym linter; flipping any exit
    code; anything keyed on a phrase list rather than a referent.
  - **Allowed behavior changes:** one new advisory finding source.
  - **Allowed reorganization:** none.
  - **Verification:** the jira-grade corpus at the commit before the sweeps
    yields the depth/grade finding; the same corpus after them yields none;
    and the recorded homonyms (`probe --depth`, "history depth", "Link depth",
    "in-depth") do **not** fire. Report the measured false-positive rate.
  - **Stop / defer:** if the false-positive rate on this repo's corpus lands
    anywhere near the withdrawn checker's, **withdraw it the same way** and
    record the measurement.
- **Approach:** `plan-tool`, measurement-first — build the detector, run it
  over the labeled jira-grade corpus, and let the false-positive rate decide
  whether it ships.
- **Origin:** 2026-07-31, proposed by the user during the `jira-grade-01`
  post-run tail, after the depth→grade sweep spanned four commits and ~60
  sites across code, docs, backlog, plan, and bundle.
- **Status:** not started.

**#319 — Extend concept-naming discontinuity detection to shipped code (reconcile lane), contingent on #207**

- **What:** the *external* half of #207's naming-discontinuity check: flag
  when a noun a plan uses as the name of a surface it ships resolves to no
  identifier in the code that surface lives in. This is where an instance
  like the jira-grade `depth`/`grade` split would have been caught at its
  most expensive point — after `create` has already run and the vocabulary
  has propagated into shipped surfaces.
- **Why split from #207:** this lane needs a shipped-identifier index (medium
  effort) that the completeness-only lane doesn't, and it inherits the same
  false-positive risk #207 names — a naming advisory nobody trusts is worse
  than no advisory. Building it before #207's measured false-positive rate is
  known would spend on the more expensive lane before the cheaper one has
  proven the detection approach works at all.
- **Dependencies:** #207 must ship and measure an acceptable false-positive
  rate first. Do not start this on #207's behalf.
- **Effort:** medium — needs the shipped-identifier index in addition to the
  detection logic #207 already builds.
- **Approach:** `plan-tool`, measurement-first, same discipline as #207.
- **Origin:** split from #207 on 2026-08-27 — the two lanes have different
  cost and different evidence-readiness, and bundling them risked building
  the expensive one before the measurement that would justify it.
- **Status:** not started; blocked on #207.

**#189 — Retroactive forward-looking sweep of the reference docs**

- **What:** apply `CLAUDE.md` § "Documentation is forward-looking" to the docs
  that predate it. The directive governs new work from the moment it landed;
  the existing corpus was written under no such rule and carries change-
  narration and dead references. **Bounded cleanup, not a rewrite** — fix the
  defects the directive names, leave the prose alone otherwise.
- **Why:** stale rationale is worse than none — it argues for the wrong thing,
  and both a human reader and the completeness audit act on it. Proven on the
  jira-grade arc the same day: prose still motivating steps by a cut
  comparison survived a numbering sweep and cost an extra audit round.
- **Concrete findings already in hand** (2026-07-29 scan, so this is not a
  vague cleanup task):
  - **Dead module `plan_tool/iteration_lock.py`, cited by four docs** —
    `TESTING.md`, `docs/RESUME_FLOW.md`, `docs/AUDIT_RESUME_FLOW.md`,
    `docs/DETAIL_RESUME_FLOW.md` (plus `tests/test_iteration_lock.py`). The
    file does not exist; `plan_tool/repo_lock.py` is the likely successor and
    the name still appears inside `plan_tool/drift_detection.py`. Determine
    which, then fix all four. Highest-value item here.
  - Other dead citations: `reformat.py` and `prompts/reconcile.md`
    (`TESTING.md`), `plan-seeds/jira-grade-01-detail-instrument.md`
    (`docs/NONDETERMINISM_PLAN_DESIGN.md` — consumed into a plan),
    `plan-seeds/escalate-structural-findings-to-split-redecomposed.md`
    (`RUNBOOK.md`).
  - Change-narration to rewrite as current-state, ~8 sites, mostly
    `RUNBOOK.md`: "keep the **old behavior**" (519), "the staleness that
    **used to** make reuse a gamble" (1108), "saved reconciles **used to**
    drift into" (1131), "you **no longer** edit `status:` by hand" (1891),
    "you **no longer have to** eyeball" (2452), "citations **no longer** flag"
    (2702), "**no longer** falls through" (3051); plus `README.md` 989 ("want
    the **old behavior**"), `docs/AUDIT_FLOW.md` 159, `docs/RUN_FLOW.md` 289.
    `reconcile-plan is no longer exposed as a --mode` (`RUNBOOK.md` 3664) is
    the one worth **keeping** — mark it as past rather than deleting, since it
    stops a reader hunting a removed flag.
- **Explicitly not defects** (the scan's false positives — do not "fix"):
  "no longer" describing a current *condition* (`DATA_CONTRACT.md` 257,
  `CAPABILITIES.md` 14, `JIRA_FORMAT.md` 233), the archive
  superseded-by-new-plan *rule* (`docs/CREATE_FROM_EXISTING_FLOW.md`),
  "previously-saved/marked" describing reuse of real artifacts, and
  illustrative example paths in `DEMO-BAKING.md`, `docs/BENCHMARK_DESIGN.md`,
  `PLAN_FORMAT.md`, and `README.md` that were never meant to resolve.
- **Method (re-runnable):** grep the corpus for the backward-looking markers
  (`previously|formerly|used to|no longer|originally|superseded|old behaviou?r`
  …) and resolve every backticked `*.py` / `*.md` citation against
  `plan_tool/`, `plan_tool/cli/`, `plan_tool/prompts/`, `tests/`, `docs/`.
  Both passes are deterministic and cost no Claude.
- **Effort:** small-to-medium, and **strictly bounded** — `RUNBOOK.md` (3.8k
  lines) and `README.md` (1.7k) dominate the corpus, so work from the found
  sites rather than reading them end to end.
- **Scope contract:**
  - **Outcome:** every cited path in the reference docs resolves, and no doc
    narrates a change where it should describe current behavior.
  - **In scope:** the root `*.md` reference docs and `docs/*.md`.
  - **Out of scope / Non-goals:** `BACKLOG.md` / `BUG_BACKLOG.md` (entries are
    inherently historical), `docs/explanations/lessons-learned.md` (a deliberate record of the
    past), `docs/cli/` (generated, drift-guarded), archived plans, and any
    rewrite of prose that is merely wordy rather than stale.
  - **Allowed behavior changes:** none — documentation only.
  - **Verification:** the two scans above return only the listed false
    positives; `plan-tool validate`'s capability-catalog check stays green.
  - **Stop / defer:** if a dead citation turns out to document a real gap in
    the code rather than a stale doc, file that separately instead of papering
    over it with a path fix.
- **Approach:** `direct` — mechanical, verifiable by re-running the scans, and
  too diffuse to decompose usefully.
- **Quality:** `audit-coverage` — removes stale prose that both readers and
  the completeness audit currently act on.
- **Origin:** 2026-07-29, filed when applying the new directive retroactively
  turned into an unbounded sweep mid-session. The directive itself already
  governs new work; this is the backlog of what predates it.

**#200 — Retire the detail archive folder; git is the archive, and the real loss case already has an owner**

- **What:** stop writing `plan-details/<slug>/archive/`. Remove the copy
  `plan_tool/detail.py:_archive_orphan_details` makes before an overwrite, and
  guard the one residual loss case with a precondition instead of an artifact.
- **Why — every case it exists for is already covered, or is better prevented:**
  - **Committed content → git.** Measured 2026-07-30: re-authoring
    `remove-vendor-scraper-poc` step 2 archived a file **byte-identical** to
    its committed baseline. Pure duplication.
  - **Uncommitted content destroyed by an in-place mutator → the change-collision
    sidecar.** `plan_tool/change_collision.py` already owns exactly this:
    `apply_finding` carries a `pre_snapshot`, drift-during-apply writes the
    post-apply content to `<stem>-change-collision<ext>`, restores the original,
    prints merge-tool invocations, and pauses for a 3-way merge. That is
    strictly better ergonomics than a timestamped copy with no reader, and it is
    the mechanism a naive reading would have duplicated.
  - **Uncommitted content destroyed by a deliberate `--force` overwrite → the
    only residual**, and it is narrow: hand-edit a detail file, do not commit,
    then explicitly pass a flag that means "overwrite".
- **Implementation recommendation:** cover the residual with a **dirty-file
  precondition**, not an archive — refuse `--force` when the target detail file
  has uncommitted changes (or require a clean tree), mirroring `--commit`'s
  existing clean-tree gate. One check, no artifacts, and it converts a silent
  loss into a loud, actionable precondition. Delete the archive-writing path and
  the directory convention with it; leave existing `archive/` directories on
  disk for operators to remove, since deleting another repo's files is not this
  change's business.
- **The noise argument is not aesthetic.** Superseded design sitting in the
  working tree is what greps, audits, and readers hit and act on — the failure
  `CLAUDE.md`'s forward-looking-documentation directive names. Every `--force`
  re-author and every orphan sweep deposits another near-identical wrong
  version with no reader, and the audit surface grows with them.
- **Risks / fallout:** the residual guard must key on the *detail file* being
  dirty, not the whole tree, or it blocks routine authoring on a normal working
  branch. If that proves too strict in practice, fall back to warn-and-proceed
  rather than reinstating the folder.
- **Dependencies:** independent. **Same principle as #199 at file scope** — git
  is the archive; #199 applies it to plans, this to detail files. (An earlier
  revision of this entry split them on a committed-vs-uncommitted line; that
  split dissolved once the collision sidecar was found to own the uncommitted
  case.)
- **Effort:** small — delete a path, add one precondition, update tests and the
  `DETAIL_FORMAT.md`/flow-doc references to the convention.
- **Scope contract:**
  - **Outcome:** no new `archive/` copies are written, and a `--force` overwrite
    cannot silently destroy uncommitted detail prose.
  - **In scope:** `plan_tool/detail.py:_archive_orphan_details` and its callers,
    the `--force` precondition, tests, and docs naming the convention.
  - **Out of scope / Non-goals:** the change-collision sidecar (already correct);
    plan-level archival (#199); deleting existing `archive/` directories in any
    repo; `annotate --archive`'s `.replaced.N` generations, which are a
    different mechanism with a different purpose.
  - **Allowed behavior changes:** the removed archive write and the new
    precondition.
  - **Allowed reorganization:** none.
  - **Verification:** a `--force` re-author on a clean detail file writes no
    `archive/` entry; on a dirty one it refuses with a message naming the file;
    the collision sidecar's drift path is unchanged.
  - **Stop / defer:** if a real recovery need for `--force`-overwritten prose
    surfaces, reopen with that evidence rather than restoring the folder
    speculatively.
- **Approach:** `direct`.
- **Quality:** `audit-coverage` — removes superseded design from the surface
  audits read.
- **Origin:** 2026-07-30, jira-grade authoring-model probe. Revised twice: first
  to keep the folder for uncommitted content, then retired once
  `change_collision.py` was found to already own that case.
- **Status:** not started.
**#201 — Detect and clean up the archive folders #200 retires**

- **What:** find existing `archive/` directories under
  `docs/implementation-plans/` and remove the ones whose contents are fully
  recoverable from git. #200 stops *writing* them and deliberately leaves
  existing ones alone; this is the sweep that clears what is already on disk.
- **Measured scale in this repo (2026-07-30):** **14** archive directories,
  **1,290** files, of which **1,289 are tracked** — so the redundancy is near
  total, and the cleanup is almost entirely mechanical. Two shapes worth knowing
  before writing the sweep:
  - **Nested archives.** 11 of the 14 are `archive/plan-details/<slug>/archive/`
    — a detail archive *inside* an archived plan. The sweep must handle
    archive-within-archive rather than assuming one level.
  - **The single untracked file is `.DS_Store`**, not plan content. Real, and a
    useful calibration: the "irreplaceable content" case the safety gate exists
    for did not occur once across 1,290 files here. Do not conclude the gate is
    unnecessary — conclude it will almost never fire, which is what makes an
    unattended sweep tolerable.
- **The safety rule is #200's, applied in reverse:** delete a file only when its
  **exact bytes** are retrievable from git (`git cat-file`-verified, not merely
  "the path is tracked" — a tracked file with uncommitted edits fails this).
  Anything that fails the check is **reported, never removed**, and left for a
  human. A sweep that deletes unrecoverable prose to tidy a directory is
  strictly worse than the noise it removes.
- **Implementation recommendation:**
  - **Detection is read-only and belongs where plan health is already reported**
    — `plan-tool validate` is the natural surface, listing archive directories
    found with a recoverable/unrecoverable file count each. **Removal is a
    separate explicit opt-in** (a flag or a `manifest`-family subcommand),
    matching the standing detection-unconditional / mutation-gated rule.
  - **Do not couple it to plan archival.** This sweeps directories; #199 decides
    how plans get archived. A repo can run this today, before #198/#199 land.
  - **Ignore-file hygiene is in scope only as far as `.DS_Store`-class noise
    goes** — report it, do not grow a general gitignore linter here.
- **Risks / fallout:** deleting a directory a doc still cites by path. The
  jira-grade handoff cites
  `docs/implementation-plans/archive/plan-details/jira-grade-detail-side-by-side-evaluation/reports/`
  as spin evidence, and citations like it must survive — so the sweep either
  skips plan-level `archive/` trees entirely (scoping to the per-detail
  `archive/` folders #200 retires) or runs the same citation sweep #199
  requires. **Recommended: scope to the detail-level folders**, and leave
  plan-level archival to #199 where the citation problem is already owned.
- **Dependencies:** independent of #198/#199. Pairs with **#200** — that entry
  stops the bleeding, this one cleans the wound. Landing this without #200
  means the directories come back.
- **Effort:** small — a walk, a `git cat-file` check per file, a report, and a
  gated delete.
- **Scope contract:**
  - **Outcome:** every per-detail `archive/` directory whose contents are fully
    recoverable from git is reported and, under an explicit opt-in, removed.
  - **In scope:** the detection walk, the recoverability check, the report
    surface on `plan-tool validate`, the opt-in removal path, tests.
  - **Out of scope / Non-goals:** plan-level `docs/implementation-plans/archive/`
    trees (#199 owns those, along with the citation sweep they need); deleting
    anything in another repo; a general gitignore linter; changing what writes
    archives (#200).
  - **Allowed behavior changes:** a new advisory in `validate` and the new
    opt-in removal.
  - **Allowed reorganization:** none.
  - **Verification:** a repo with a redundant detail `archive/` reports it and,
    with the opt-in, ends with the directory gone and the tracked history
    intact; a directory holding a file whose exact bytes are absent from git is
    reported and **left in place**; nested archives are found, not just
    top-level ones.
  - **Stop / defer:** if a doc-citation to a detail-level archive path turns up,
    stop and fold the citation sweep in from #199 rather than breaking the
    reference.
- **Approach:** `direct` — a walk plus a gated delete, no open design choices
  once the scoping decision above is taken.
- **Quality:** `audit-coverage` — removes superseded design from the surface
  greps and audits read.
- **Origin:** 2026-07-30, user request while retiring the archive convention.
- **Status:** not started.

**#209 — `--commit` should stage only the files the verb touched, not `git add -A`**

- **What:** every `--commit` surface routes through
  `plan_tool/cli/gitcommit.py:182` `commit_all(repo_root, subject)`, which runs
  a bare **`git add -A`** and so commits *whatever is in the working tree* —
  not what the verb produced. Give `commit_all` an explicit touched-path set
  and stage `git add -A -- <paths>` instead, so a `--commit` run can only ever
  commit its own output.
- **Why (near-miss, 2026-07-31):** a `detail --commit` run authoring steps 5–8
  of `roadmap-01-domain-constraints` was in flight while a second session
  edited `plan_tool/{detail,review}.py` and
  `plan_tool/cli/{authoring,review_cmd}.py` in the **same working tree** (one
  worktree, no clone). The next per-step commit would have swept four unrelated
  source files into a commit subjected
  `plan(roadmap-01-domain-constraints): detail step 6 — …`. Caught and the run
  stopped before step 6 committed; steps 1–5 are clean. The failure mode is
  nasty precisely because it is quiet: the change lands under a message
  describing someone else's work, on a branch the author never targeted, and is
  discovered when it "vanishes" from the tree.
- **Why the existing gate doesn't cover it:** `--commit` requires a clean tree
  **up front**, which makes "everything in the tree is mine" true at t=0 and
  false thereafter. Anything appearing *during* a multi-step run — a concurrent
  session, an editor writing a sidecar, a hook — is swept. The single-session
  assumption is also increasingly wrong by the tool's own direction: it ships
  parallel plan worktrees, `--clone` full isolation, and
  `completeness-apply --jobs N`, all of which normalize more than one plan-tool
  process against one repo.
- **The precedent already exists.** `gitcommit.py:42`
  `unexpected_dirty_paths(repo_root, expected)` already takes a
  caller-supplied *expected*-path set and reasons about nesting and
  `--untracked-files=all`; `launcher._git_changed_paths_or_none` already
  computes a changed-path delta for the test-authoring gate. Callers therefore
  largely know their footprint — this threads it into staging rather than
  inventing the notion.
- **Effort:** medium. The helper change is small (`git add -A -- <pathspec>`
  keeps deletes and renames working *within* scope, so seed-archive moves and
  frontmatter rewrites still stage correctly). The work is the ~10 call sites
  across four modules — `cli/authoring.py:212`, `cli/completeness_cmd.py`
  (609, 780, 1401), `cli/manifest.py:611`, `cli/direct_cmd.py` (185, 413, 444,
  595, 625) — each of which must state its touched paths.
- **Risks / fallout:** the failure direction **inverts** — today's risk is
  over-staging, tomorrow's is *under*-staging, where a file the verb genuinely
  wrote is silently left uncommitted and the run looks clean. That is arguably
  worse, so the change needs a post-commit assertion that no expected path
  remains dirty. Two interactions to settle rather than discover:
  **gitignored paths** (`git add -A` skips them silently, which is why
  `path_is_gitignored`/`warn_recommended_paths_ignored` exist; an explicit
  pathspec errors instead, so the ignored-but-expected case needs a decided
  behavior), and **`direct_cmd`'s unattended pipelines**, which may lean on
  sweep semantics across a whole staged phase.
- **Dependencies:** none.
- **Scope contract:**
  - **Outcome:** a `--commit` run commits exactly the paths the verb touched;
    an unrelated dirty file present at commit time is never included.
  - **In scope:** `cli/gitcommit.py:commit_all` and its ~10 call sites; the
    touched-path plumbing each verb needs; tests.
  - **Out of scope / Non-goals:** changing the clean-tree precondition,
    commit subjects/trailers, which verbs accept `--commit`, per-step
    commit granularity, or anything about branch selection; the
    `run --commit` test-authoring-gate interaction (`launcher.py`'s delta)
    stays as-is.
  - **Allowed behavior changes:** `--commit` no longer includes unrelated
    working-tree changes; a decided, documented behavior for an
    ignored-but-expected path. Nothing else user-visible.
  - **Allowed reorganization:** none beyond adding the parameter — if
    consolidating `unexpected_dirty_paths`' expected-set construction with the
    new staging set proves necessary, name the duplication first.
  - **Verification:** a test per surface that an unrelated dirty file present
    at commit time is *not* committed; that deletes and renames inside the
    touched set still stage (the seed-archive move); that every expected path
    is non-dirty after the commit; and that an ignored expected path takes the
    decided branch rather than silently vanishing.
  - **Stop / defer:** if any caller cannot enumerate its footprint without new
    bookkeeping, ship the surfaces that can and file the remainder rather than
    widening this into a footprint-tracking refactor.
- **Approach:** `plan-tool` — mechanical per call site, but "what did this verb
  touch" is a real per-verb design question across four modules, and the
  under-staging inversion plus the gitignore branch are decisions worth
  auditing before they land.
- **Origin:** 2026-07-31, caught mid-run when a concurrent session's edits were
  one step away from being committed under a detail-authoring subject.
- **Status:** not started.

**#234 — Pair `enforce_step_tests` with qualified `test_command` emission so a green step means the suite still passes**

- **Delivered:** `create` writes `enforce_step_tests: true` on new plans and
  conditionally writes `test_command`. It writes `uv run pytest tests/ -q -n
  auto` only when the fixed candidate qualifies from local markers and passes
  preflight; otherwise an interactive operator can supply a concrete command,
  while `--yes` and non-TTY creation omit the field. `PLAN_FORMAT.md` now
  distinguishes that conditional creation behavior from the optional field's
  `null` default. These delivered levers do not retrofit existing plans or
  authorize guessed commands.
- **Deferred:** evaluate a last-attempt test-command cost bound. The benchmark
  for that decision is the 2026-08-05 measurement of this repository's 8004-test
  suite at 47.7s / 46.2s / 45.0s with `-n auto` and 184s serial. This is the only
  remaining work for #234.
- **Origin:** 2026-08-05, a green step left red assertions in an untouched test
  module until a manual suite run found them.

**#241 — Narrow the conceptual-audit prompt on a bare plan, so it stops generating findings the report withholds**

- **What:** on a bare plan (`bundle_status.is_bare`), the conceptual audit runs
  the full finding taxonomy and the report then **withholds** the
  completeness half — `completeness_report.py:823`, "Completeness gaps are
  withheld on a bare plan", with `:832` filtering `advisory_conceptual` out.
  But `prompts/plan-audit.md` carries **no bare-plan narrowing at all**; the
  word appears there only in unrelated prose-style rules. So every pass pays
  full generation cost for a category that is shelved on arrival. Tell the
  prompt it is judging a bare plan and to produce `plan-correctness` only.
- **Why now:** measured 2026-08-06 on the TTRPG demo's `visibility-gate`
  (bare, 6 steps, 0 detailed). Three passes cost **353s / 379s / 462s ≈ 20
  minutes** and produced 26 unique findings, of which **17 were withheld** —
  two-thirds of the output generated to be shelved. Response sizes were
  11.7 / 8.5 / 7.5 KB, so generation, not input reading, is where the time
  went. Use these measured generation costs when evaluating the optimization;
  compare actionable findings as well as elapsed time.
- **Do not reduce the pass count instead — that is the wrong knob and it is
  the tempting one.** In the same run, passes 2 and 3 contributed **3 of the 9
  actionable correctness findings**, and coverage still came back
  `budget-limited` / UNCONFIRMED at the 3-pass cap. `--audit-passes 1` would
  have bought ~11 minutes and lost a third of the actionable set, and it
  disables `arm-clustering` outright (a consensus target needs ≥2 samples).
  The passes are a recall sampler; the waste is in what each pass *emits*.
- **This is cut-work, not concurrency.** § "Architecture" names "tighten
  prompts" as a sanctioned deterministic-serial lever and puts in-process
  fan-out behind an explicit burden of proof. Nothing here proposes `--jobs`.
- **Effort:** small-to-medium. One conditional block in the audit prompt plus
  the flag that reaches it; the `is_bare` signal already exists and is already
  threaded to the report layer.
- **Risks / fallout:** a narrowed prompt could suppress a *correctness* finding
  that today only surfaces because the model was also reasoning about
  completeness — that is the thing the verification below has to disprove, and
  it is why this is not a pure win. Prompt-text assertions in
  `tests/test_completeness*.py` will churn.
- **Dependencies:** none. **Related:** the settled bare-vs-detail convergence
  bar owns the policy half this entry fences out — the bare-plan stage getting
  its own, lower exit bar.
  #133, the same class of problem on the
  per-step purity check (large prompt, 130–255s/step).
- **Scope contract**
  - **Outcome:** on a bare plan the conceptual audit emits `plan-correctness`
    findings only, and its wall-clock falls, with the correctness finding set
    no smaller than today's.
  - **In scope:** `plan_tool/prompts/plan-audit.md`, the call site that selects
    the prompt variant, and the tests pinning the prompt's keys.
  - **Out of scope / Non-goals:** changing the pass count or its default;
    changing which findings the **report** withholds (that half is correct
    today); the detailed-plan prompt; `--audit-passes`, `arm-clustering`, the
    convergence policy, or `Recommendation`. Explicitly **not** a concurrency
    or `--jobs` change.
  - **Allowed behavior changes:** fewer emitted completeness findings on a
    bare plan, and the wall-clock drop that follows. Nothing else.
  - **Allowed reorganization:** none.
  - **Verification:** re-run the audit above on the same plan at the same
    commit and compare (a) wall-clock per pass and (b) the **correctness**
    finding set by key. The win is real only if correctness is unchanged or
    larger. The demo repo pins a usable baseline: 9 correctness keys —
    `note-status-input`, `access-without-a-grant`, `decision-function-shape`,
    `cross-world-share`, `revocation-shape`, `owner-carve-out-basis`,
    `grant-composition`, `note-status-vs-grant-composition`,
    `group-membership-lookup`.
  - **Stop / defer:** if correctness recall drops, the narrowing is wrong and
    the entry closes as a measured **no** — record it here rather than tuning
    the prompt until the number comes back.
- **Approach:** `direct` — one prompt branch and a measurement.
- **Quality:** `audit-coverage` — it changes what the audit spends its budget
  producing on the one plan state where most of that output is unusable.
- **Origin:** 2026-08-06, operator observation that bare-plan audits "feel like
  they are taking longer than they need to", checked against the run above.
- **Status:** not started. The counterfactual is **inferred, not measured** —
  the saving is argued from response sizes, so the verification step above is
  the entry's real content.

**#260 — Parked: stage-bar reporting polish**

- **Decision:** the stage-bar prerequisite ships, so the former "after core
  ships" umbrella is stale. No report defect is currently named precisely
  enough to justify a broad renderer redesign.
- **Re-open trigger:** a preserved terminal, Markdown, or JSON output identifies
  a concrete misleading message, its reader/action, and a focused acceptance
  fixture. File that as a small direct defect rather than restoring this
  umbrella.
- **Out of scope:** generic stop-reason vocabulary, report/exit/JSON redesign,
  and a new follow-up plan without an observed incorrect output.
- **Status:** parked 2026-08-19.

<!-- Superseded 2026-08-19: the following pre-shipment renderer umbrella no
longer describes current work. It is retained only as dated carve-out context.

- **What:** after the core two-bar + mid-run plan ships, land the reporting
  arm carved out of Gate 1: full stop-reason vocabulary and precedence,
  clean-bare medium-completeness set-aside handoff, withheld-completeness
  intro rewrites, gate-2 tail bar naming through `authoring.py`, jira-grade
  clean next-steps, and audit-revision qualification on report/exit/JSON.
- **Why deferred:** Gate 1 on the combined plan kept expanding on this arm
  while the core bars stayed unsettled under rate-limit/budget noise; core
  must ship without waiting on display completeness.
- **Depends on:** `stage-differentiated-blocking` executed (stage +
  bar-blocking available to report consumers).
- **Approach:** `plan-tool` — multi-module report/CLI surface.
- **Origin:** 2026-08-10 Gate 1 carve on `stage-differentiated-blocking`.

-->

**#294 — Model deployment units before treating a runtime/store pair as a roadmap contradiction**

- **What:** introduce a per-deployable-unit representation only if a real
  roadmap needs the tool to reject an incompatible runtime/store pair. Bind a
  unit's execution model to the stores it owns or uses, then decide whether a
  small fixed contradiction rule is observable at that level.
- **Why:** the shipped hosting schema records one application-level `compute`
  value. A mixed system
  can have both long-lived workers and per-request handlers, so an
  application-wide rule would reject a valid store merely because it belongs
  to a different unit. The former single pair rule was therefore removed
  before implementation rather than documented around.
- **Scope:** model units and their ownership relation; prove a claimed
  contradiction on mixed and single-unit fixtures; preserve the existing
  vendor-neutral category altitude. Do not add a compatibility matrix,
  service-specific policy, or a rule that guesses a component's deployment
  unit.
- **Dependencies:** the shipped hosting and store facts, because the future
  work consumes them.
- **Priority:** high when a concrete roadmap needs the judgment; otherwise it
  remains a deferred design, not a blocker for recording those facts.
- **Approach:** plan-tool — a new persisted relation and cross-artifact gate
  require staged design and migration decisions.
- **Status:** not started.

**#300 — Finish migrating hardcoded heading/verdict regexes onto `response_contract.py`**

- **What:** `plan_tool/response_contract.py` centralizes a prompt's
  machine-response contract (format instructions + parser) so the two can't
  drift apart, and most `## Findings` / `## Verdict` / two-section audit
  regexes were migrated onto it. Two known sibling regexes of the identical
  shape were not: `launcher.py:845 _VALIDATION_RE` and `review.py`'s
  `_REDIRECT_HEADING_RE` (~line 5656), both hand-rolled `^##\s*<Heading>\b`
  patterns that predate the shared contract.
- **Why:** a future correctness fix to heading-matching (trailing-content
  tolerance, case handling, retry wiring) applied to `MarkdownSectionsContract`
  / `VerdictContract` won't reach either regex — the same "fix the class, not
  the cited spot" gap the response-contract migration itself was meant to
  close. One instance already surfaced during that migration: the shared
  `heading_pattern()` briefly regressed `## Findings` heading tolerance
  before being caught in code review and fixed 2026-08-20.
- **Effort:** small — each is a narrow single-heading contract like
  `DEEP_VERDICT_RESPONSE_CONTRACT`; wrap and swap the call site.
- **Risks:** low; verify each site's exact current match behavior (anchoring,
  case sensitivity) before swapping, per the response-contract migration's
  own lesson that "shared" and "identical" are not the same claim.
- **Dependencies:** none.
- **Outcome:** both regexes sourced from a `response_contract.py` contract
  instead of a local pattern.
- **In scope:** `plan_tool/launcher.py:845`, `plan_tool/review.py`'s
  `_REDIRECT_HEADING_RE`, and their existing tests.
- **Out of scope / Non-goals:** the 7 still-local JSON-envelope slice sites
  tracked separately under #79.
- **Allowed behavior changes:** none — this is a source-of-truth move, not a
  contract change.
- **Approach:** direct.
- **Evidence:** 2026-08-20 code review of the `response_contract.py`
  migration (`plan_tool/annotate.py`, `concept_tree.py`, `foundational_logic.py`,
  `gates.py`, `intent_proposal.py`, `launcher.py`, `renderer.py`, `review.py`).
- **Numbering:** #300. Historical #299 is the withdrawn completeness-coverage-
  replay record in `docs/history/backlog-decisions.md` and step 3 of
  `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md`;
  do not reopen it as this leftover.
- **Status:** not started.

**#301 — Version saved conceptual-audit coverage records before their next additive field**

- **What:** Give persisted `audit_coverage` records an explicit schema version
  and a versioned reader, replacing the current exact-key-set recognition of
  legacy and current shapes.
- **Why:** The coverage record has gained fields incrementally. A versioned
  reader will make the next addition predictable and define how a partially
  migrated or older sidecar is handled.
- **Effort:** medium — the writer, reader, sidecar compatibility fixtures, and
  public projection all share this persisted shape.
- **Risks / fallout:** a bad migration could reject existing saved audits or
  falsely treat incomplete coverage as trustworthy. Older sidecars must keep
  their present semantics.
- **Dependencies:** none.
- **Scope contract:**
  - **Outcome:** every supported `audit_coverage` version has a named accepted
    key set and normalizes to one current internal shape.
  - **In scope:** `plan_tool/review_persistence.py`, coverage producers and
    projections, saved-sidecar fixtures, and `DATA_CONTRACT.md`.
  - **Out of scope / Non-goals:** changing what counts as qualifying or
    confirmed coverage; audit-revision schema changes; silently repairing
    malformed sidecars.
  - **Allowed behavior changes:** newly written coverage carries its version;
    existing valid sidecars remain readable with their current meaning.
  - **Allowed reorganization:** the coverage reader/writer boundary only.
  - **Verification:** fixtures for every supported historical version,
    malformed combinations, and a current plan-quota stop preserve their
    public report and sidecar-withholding behavior.
  - **Stop / defer:** a new coverage field is not a reason to bypass the
    versioned reader; extend its contract and fixtures first.
- **Approach:** `plan-tool` — a persisted-format migration with several
  producers and readers needs an explicit compatibility contract.
- **Quality:** audit-coverage — preserves the meaning and trust boundary of
  saved audit evidence as the format evolves.
- **Origin:** 2026-08-20, `plan-quota-recovery` whole-feature review round 5,
  finding 3.
- **Status:** deferred 2026-08-20; no live bug, retained for the next
  intentional coverage-format change.

**#302 — Funnel rate-limit recovery notifications through one checked completion path**

- **What:** Restructure `run_with_rate_limit_recovery` so every non-success
  result records its retry outcome once and one shared completion path invokes
  `on_nonsuccess`.
- **Why:** The loop currently invokes the callback at nine separate exits. A
  future recovery arm could otherwise omit the notification or give it the
  wrong retry state, losing quota-drift telemetry.
- **Effort:** medium — the loop has distinct guard, switch, prompt, wait, and
  transient branches whose visible retry behavior must remain unchanged.
- **Risks / fallout:** a control-flow rewrite can regress retry counts,
  backend switching, prompt handling, or the raw-exit suppression signal.
- **Dependencies:** the shipped #101 recovery-loop extraction. This is
  separate from #136's caller-side helper consolidation.
- **Scope contract:**
  - **Outcome:** each non-success attempt invokes `on_nonsuccess` exactly once
    with the same actual and predicted retry signals it has today.
  - **In scope:** `plan_tool/rate_limit_loop.py` and its focused tests.
  - **Out of scope / Non-goals:** shell/launcher seam consolidation (#136),
    retry-policy changes, new recovery actions, and telemetry-format changes.
  - **Allowed behavior changes:** none.
  - **Allowed reorganization:** the loop's internal exit control flow only.
  - **Verification:** a table-driven test covers every existing terminal and
    re-invoking arm, asserting callback count and both retry booleans.
  - **Stop / defer:** any behavior change discovered while consolidating exits
    becomes a separate decision rather than an incidental refactor.
- **Approach:** `plan-tool` — preserving nine recovery arms requires an
  explicit behavior matrix before restructuring them.
- **Quality:** audit-coverage — keeps terminal quota-drift observation
  complete as new recovery exits are added.
- **Origin:** 2026-08-20, `plan-quota-recovery` whole-feature review round 5,
  finding 4.
- **Status:** deferred 2026-08-20; no live bug, retained for a deliberate
  recovery-loop hardening pass.

**#303 — Compare saved audit history only with provenance-backed admission**

- **What:** add a separately scoped cross-invocation audit comparison only
  after saved evidence can prove the history is eligible for comparison.
- **Why deferred:** #247 makes artifacts visible, but saved metadata alone
  cannot establish that two model-generated findings refer to the same plan,
  audit contract, or finding. The delivered ledger is a visibility prerequisite,
  not admission evidence; a verdict built on that uncertainty would look more
  certain than its evidence.
- **Scope contract:**
  - **Outcome:** an operator receives a pairwise comparison only when the
    persisted evidence admits it; every other history remains visible without
    a trajectory or convergence verdict.
  - **In scope:** provenance and lifecycle contracts, plan identity, audit
    revision and coverage admission, comparison semantics, renderer states,
    and fixtures for eligible and ineligible history.
  - **Out of scope / Non-goals:** changing the audit model, altering exit
    codes or gates, new Claude calls, content-similarity matching, #173's
    caching/recheck route, and automatic scope or decomposition decisions.
  - **Verification:** tests prove unknown, copied, stale, malformed, or
    incompatible evidence cannot produce a comparison or a convergence claim.
  - **Stop / defer:** retain the ledger-only behavior until a single
    persistence design can prove the required evidence at every writer and
    reader boundary.
- **Approach:** `plan-tool` — this crosses persistence, audit, and reporting
  contracts and requires a plan before implementation.
- **Quality:** `convergence` — comparisons fail closed instead of presenting
  uncertain history as an operator decision.
- **Origin:** 2026-08-21 — user-directed reorientation of #247 after the
  expanded trajectory design did not yet have an adequate evidence boundary.
- **Status:** deferred 2026-08-21; #247's delivered ledger is a prerequisite
  for visibility, not proof that comparison is safe.

**#304 — Evaluate a shared feedback-operation attempt lifecycle only when a concrete change requires it**

- **What:** Decide whether normal stage feedback and `--revise-feedback` need
  a shared helper for their operation-attempt lifecycle: prompt construction,
  one or bounded backend attempts, operation parsing, candidate gates, final
  source rechecks, and terminal telemetry.
- **Why:** The two routes now share enough lifecycle shape that a behavior
  change can drift if it lands in one route only. They also have intentional
  differences: normal stage feedback can retry and continues through the stage
  table, while `--revise-feedback` is one selected artifact and one request.
- **Scope contract:** A successor may extract only a behavior-preserving
  helper after it names one concrete cross-route change and proves the helper
  keeps route-specific selection, attempt budget, publication scope, and
  outcome contracts explicit. It must not turn either route into a generic
  artifact writer or merge their distinct entry points.
- **Verification:** A successor runs both route suites and adds a paired test
  for the concrete shared behavior, including each route's deliberately
  different retry and publication result.
- **Stop / defer:** Do not extract a helper solely for visual similarity. Keep
  this entry deferred until a real cross-route change makes duplicated behavior
  a correctness risk.
- **Approach:** plan — it crosses two orchestrators and their run-log
  contracts.
- **Numbering:** #304. Assigned #301 on 2026-08-21, remapped to #303 when
  origin/main kept quota-recovery as #301/#302, then remapped to #304 because
  this clone had already published #303 for provenance-backed audit comparison.
- **Status:** deferred pending a concrete cross-route behavior change.

**#257 — Thread a `depends_on` edge's consumption note into bridging-edge grounding**

- **What:** `create.py`'s `_render_dependency_cohesion_block` feeds
  a plan's bridging `depends_on` edges — edges sharing no declared production
  file — into the body-synthesis prompt as "the claims most worth verifying."
  `_BridgingDependencyEdge` carries no note text and the render function only
  prints the file mismatch, so a bridging edge that already has a
  `depends_on_notes` entry still reaches synthesis looking
  exactly like an edge with no explanation.
- **Why:** this is precisely the set of edges the shipped grounding rule flags as least backed
  by structural evidence — exactly where a consumption note matters most, and
  exactly where its absence is most informative. Surfacing it costs nothing new
  to compute; the note is already on the step.
- **Effort:** small — thread `depends_on_notes.get(antecedent_id)` into
  `_render_dependency_cohesion_block`'s per-edge line when present.
- **Dependencies:** builds on shipped `depends_on_notes` and the shipped
  bridging-edge grounding rule.
- **Scope contract:**
  - **Outcome:** a bridging edge's rendered grounding line shows its note when
    one exists, unchanged when one doesn't.
  - **In scope:** `plan_tool/create.py` (`_render_dependency_cohesion_block`,
    `_BridgingDependencyEdge`), tests.
  - **Out of scope / Non-goals:** any check, gate, or verdict on the note's
    content; changing which edges count as bridging; changing `depends_on_notes`
    note-content non-goals.
  - **Allowed behavior changes:** the rendered grounding block's per-edge line
    gains an optional note suffix.
  - **Allowed reorganization:** none.
  - **Verification:** a bridging edge with a note renders it; one without
    renders exactly as today.
  - **Stop / defer:** anything beyond rendering the note text as-is.
- **Approach:** `direct` — a small, additive rendering change.
- **Quality:** `audit-coverage` — closes the gap between two already-shipped
  features that should have composed on day one.
- **Origin:** 2026-08-08, found in BACKLOG #253's own round-3 bare-plan audit;
  split out rather than absorbed (remedy-proportionality).
- **Status:** not started.

**#258 — Render a `depends_on` edge's consumption note in `jira`'s exported story body**

- **What:** `jira.py`'s story-rendering code prints each story's `Depends on:`
  ids with no accompanying note text. A human reading an exported Jira ticket —
  arguably the most likely non-`plan-tool` reader of a dependency edge — loses
  exactly the "what does this consume" context `depends_on_notes` exists to capture.
- **Why:** the export is the one surface where a `depends_on_notes` reader is
  guaranteed to have no access to the source plan file to look the note up
  themselves.
- **Effort:** small — render the note alongside each `Depends on:` id when
  present.
- **Dependencies:** builds on shipped `depends_on_notes`.
- **Scope contract:**
  - **Outcome:** an exported story's `Depends on:` block shows each edge's note
    when one exists.
  - **In scope:** `plan_tool/jira.py` (story-rendering), `JIRA_FORMAT.md` if the
    rendered shape needs documenting, tests.
  - **Out of scope / Non-goals:** any check on note content; changing
    `Depends on:` semantics or which ids are exported.
  - **Allowed behavior changes:** the rendered story body gains optional note
    text per dependency.
  - **Allowed reorganization:** none.
  - **Verification:** a story whose source step has a note renders it; one
    without renders exactly as today.
  - **Stop / defer:** anything beyond rendering the note text as-is.
- **Approach:** `direct`.
- **Quality:** `audit-coverage`.
- **Origin:** 2026-08-08, found in BACKLOG #253's own round-3 bare-plan audit;
  self-flagged `[out-of-scope-deferred]` by that audit and split out rather
  than absorbed.
- **Status:** not started.

**#259 — Render a `depends_on` edge's consumption note in the run-grade `detail`-authoring prompt**

- **What:** `detail.py:render_detail_prompt` renders a step's `depends_on` as a
  bare comma list (`step_depends_on`) in the prompt that asks Claude to write
  that step's implementation detail file.
- **Why:** whoever (or whatever) authors the detail file benefits from seeing
  what a dependency actually delivers, the same reasoning as #257 and #258 one
  stage earlier in the pipeline.
- **Effort:** small — thread each edge's `depends_on_notes` text into the
  run-grade dependency block.
- **Dependencies:** builds on shipped `depends_on_notes`.
- **Scope contract:**
  - **Outcome:** the detail-authoring prompt's dependency block shows each
    edge's note when one exists.
  - **In scope:** `plan_tool/detail.py:render_detail_prompt`, tests.
  - **Out of scope / Non-goals:** any check on note content; changing what
    `depends_on` ids are listed.
  - **Allowed behavior changes:** the rendered prompt's dependency block gains
    optional note text per edge.
  - **Allowed reorganization:** none.
  - **Verification:** a step whose antecedent has a note renders it in the
    prompt; one without renders exactly as today.
  - **Stop / defer:** anything beyond rendering the note text as-is.
- **Approach:** `direct`.
- **Quality:** `audit-coverage`.
- **Origin:** 2026-08-08, found in BACKLOG #253's own round-3 bare-plan audit;
  self-flagged `[out-of-scope-deferred]` by that audit and split out rather
  than absorbed.
- **Status:** not started.

**#254 — Per-subcommand model tiers, so "strong for `create`, fast for the rest" is configuration rather than operator memory**

- **What:** let a project say which model each subcommand runs with, via a
  **named tier** rather than a raw model id: `backends.<name>.models.strong` and
  `.fast` in `.plan-tool/backends.json`, with the tier→subcommand mapping fixed
  in the tool (`create` and `roadmap` → strong; everything else → fast, per
  `integrations/shared/DIRECTIVES.md` § "Which model to run a subcommand with").
  Explicit `--model` keeps winning; an absent `models` block keeps today's
  single-model behavior exactly.
- **Why:** `BackendOverride` carries only `model` + `extra_*_argv` and is scoped
  **per-backend, not per-subcommand**, so the rule that `create` deserves the
  strong tier while `detail`/`run`/audit rounds do not is currently operator
  discipline — remembered per invocation, and silently lost the moment anyone
  scripts a pipeline or drives it unattended. The rule matters because `create`
  runs **once** and constrains the step list, the `depends_on` graph, and the
  file footprints every later call inherits: bounded cost, unbounded blast
  radius.
- **The design constraint that shapes this, and it is load-bearing.** Tiers
  cannot be *inferred*. `plan_tool/model_specs.py`'s own `pick_default_model`
  says so in its docstring — "there is no 'flagship' flag in the source" — and
  ranks by `(context_window, output_cost, id)` on a stated premise, calling
  itself "a guess, never authoritative." Model ids are also backend-specific and
  free-form (`--model` takes no choices; `opus` means nothing to codex or
  cursor). So **the operator names both tier members explicitly, per backend**;
  do **not** extend the catalog heuristic to guess a strong/fast split, and do
  not hardcode vendor model names in the tool.
- **Effort:** small — one config block, the fixed mapping, and the precedence
  wiring into the existing `--model` > project > manifest chain.
- **Risks / fallout:** it adds config surface to a tool with a deliberate
  anti-creep posture, and a second model per backend is a second thing to keep
  current as vendors rename. Absent config **must** behave exactly as today, or
  this becomes a breaking change for every existing project file.
- **Do not build this preemptively — it has a trigger.** The discipline works
  when a human types the invocation; file this as *ready* and build it when the
  discipline is observably decaying: a scripted or unattended pipeline that runs
  `create` on the fast tier, or a plan whose decomposition is traced back to one.
  Until then the cheaper fix is the directive that already exists.
- **Dependencies:** none. Adjacent to the shipped bridging-edge grounding rule
  and `depends_on_notes`, which improve what
  `create` produces; this decides what `create` runs on.
- **Scope contract:**
  - **Outcome:** the strong/fast split survives being scripted, instead of
    depending on whoever types the command.
  - **In scope:** `plan_tool/backend_config.py` (`BackendOverride`), the
    resolution chain in `backend.py`, the fixed tier→subcommand mapping,
    `docs/cli/` regeneration, tests.
  - **Out of scope / Non-goals:** inferring tiers from the models.dev catalog;
    hardcoding vendor model names; per-*step* or per-*phase* model selection;
    changing the tier→subcommand mapping itself (that lives in DIRECTIVES.md and
    is a separate decision); any gate or refusal keyed on which model ran.
  - **Allowed behavior changes:** which model a subcommand invokes, only when a
    `models` block is present.
  - **Allowed reorganization:** none.
  - **Verification:** a project file naming both tiers runs `create` on strong
    and `detail` on fast; an explicit `--model` overrides both; a project file
    with no `models` block is byte-identical in behavior to today.
  - **Stop / defer:** if naming two models per backend proves more annoying than
    typing `--model` on `create`, close it as a measured no.
- **Approach:** `direct` — a config field and a mapping, once the trigger fires.
- **Quality:** `operability` — makes a decided policy hold under automation.
- **Origin:** 2026-08-08, from the model-selection rule added to CLAUDE.md and
  DIRECTIVES.md during a convergence review; filed at operator request with the
  build trigger stated rather than building it immediately.
- **Status:** not started; ready, waiting on the trigger above.

**#280 — Verify and resolve the `completeness-cli-layering` code-review duplication candidates (5 findings, one review pass)**

- **What:** a `/code-review high` pass on the `completeness-cli-layering`
  refactor (2026-08-15, rounds 4–6) flagged 5 possible duplications, all
  inside `plan_tool/cli/completeness_phases.py` or against one sibling
  module. None has been independently re-verified past the reviewing
  agent's own citation — per the consolidation-evidence rule in `docs/TRACKING.md`
  (and #79's history: 4 of 5 claimed duplicates there were wrong in the
  direction that breaks things), re-derive each before consolidating
  anything.
- **Checklist — each resolves to "consolidated, with a test proving the
  preserved difference" or "documented as intentionally distinct, closed":**
  1. **Dataclass/dispatch boilerplate within this file.**
     `_SavedAuditResolution`/`_ApplyWalkTargets` (`:216`/`:479`) share an
     `ok`/`rc`/`message` field prefix and docstring sentence.
     `_run_apply_walk`/`_apply_walk_recs_parallel` (`:1131`/`:865`) share
     tail logic (gitignored-audit warning, `--commit` block, closing
     print) — **but their `--commit` guard conditions genuinely differ**
     (serial gates on `plan_path is not None`, parallel on `answered`) and
     must not be collapsed away. Both also build near-identical
     `RunLogWriter.start(...)` calls (`:805`/`:1018`) differing only in
     `"jobs": jobs`.
  2. **Conceptual-source membership hardcoded twice.**
     `_CONCEPTUAL_APPLY_SOURCE_RANK` and `_split_conceptual_recs`
     (`:372`/`~2654`) independently hardcode the
     `plan-correctness`/`plan-completeness` pair instead of deriving from
     `convergence.CONCEPTUAL_SOURCES`, though `_split_conceptual_recs`'s
     own docstring claims to centralize the split. Confirm a derivation
     preserves whatever ordering `_CONCEPTUAL_APPLY_SOURCE_RANK` encodes
     before swapping.
  3. **`parse_plan(plan_path)` called up to 4x per `completeness-apply`
     invocation** (`:195, 331, 423, 612`), no `Plan` threaded between
     calls. Check whether an intervening write — `_apply_files_coherence`
     writes `allowed_mentions:` back to the plan — means a later site
     depends on re-reading; collapsing to one parse could silently make it
     see stale content instead of the post-write state it gets today.
  4. **`_resolve_saved_completeness_audit` vs. `completeness_report.py`'s
     `resolve_reusable_audit`/`ReusableAudit`** (`:394, 434`) — same
     saved-sidecar-resolution shape, two independently written eligibility
     checks (`_saved_audit_revision_is_current` vs.
     `is_reusable_audit_sidecar`). May be testing genuinely different
     questions (reuse-across-a-fresh-run vs. still-actionable) — confirm
     before merging.
  5. **`completeness_phases.py` vs. `data_contract_cmd.py`.** Two
     suspected overlaps: sidecar load/target resolution with divergent
     error handling (swallow-to-`{}` vs. raise `ReviewLoadError`), and
     "find the newest current, qualified saved audit" scan logic.
- **Effort:** small per item to investigate/confirm; medium per item if a
  real consolidation follows.
- **Approach:** `direct` — investigation-first per item; no plan-tool plan
  needed.
- **Origin:** 2026-08-15, `/code-review high` rounds 4–6 on
  `completeness-cli-layering`.
- **Status:** not started.

**#284 — Verify and resolve the 2026-08-17 roadmap escalation/impact code-review consolidation candidates (4 findings)**

- **What:** a 2026-08-17 code review of the roadmap escalation/impact
  modules flagged 4 candidate consolidations/optimizations, none yet
  investigated or decided.
- **Checklist — each resolves to a landed change (with contract tests) or a
  documented "stays separate/deferred" decision:**
  1. **Shared lifecycle owner for the receipt and impact runners?**
     `roadmap_escalation_run.py` and `roadmap_impact_run.py` each own a
     similarly shaped lifecycle (start a run log, append a redacted
     preflight, persist one terminal event, generic cleanup, preserve a
     result when cleanup is interrupted) but differ in event payloads,
     publication admission, and terminal vocabularies. A parallel `run_end`
     interruption bug the review found is already fixed separately; only
     the consolidation decision remains. Risk: a generic helper can leak
     receipt-only fields into impact events or homogenize intentionally
     different telemetry-failure behavior.
  2. **Strict JSON decoder consolidation?** Receipt, impact-analysis,
     revision, and concept-tree paths each reject malformed JSON with local
     helpers — derive an AST-normalized comparison of error-type,
     float-policy, trailing-content, and persisted-contract differences
     before sharing anything. **2026-08-20 update:** `concept_tree.py`'s
     *emit* path already moved onto the unrelated shared
     `response_contract.py:JsonResponseContract`, and that migration
     initially dropped duplicate-JSON-key rejection — caught in code
     review, fixed by threading an `object_pairs_hook` through
     (`tests/test_concept_tree.py::TestParseEmittedConcepts`), a live
     instance of exactly the risk this item names. `concept_tree.py`'s
     on-disk `load_concepts` decoder is still local. When this runs, decide
     whether the remaining three roadmap decoders should fold onto
     `JsonResponseContract` too, rather than treating the emit path as
     still up for grabs.
  3. **Optimize impact-closure traversal/inspection?** Measure first — an
     adjacency index for closure traversal and per-view reuse of
     snapshot/classification work are only worth building if a reproducible
     large-graph/multi-analysis benchmark shows a material cost. Must
     preserve deterministic ordering, the current-state guarantee, and the
     existing capture/recheck boundary and lock-free empty-evidence scan —
     none of those may be removed as "deduplication."
  4. **Collapse `RoadmapImpactSnapshot`'s parallel tuples?** Parsed
     artifacts, captured text, and source digests are kept as aligned
     tuples; decide whether one per-artifact value can own that alignment
     without losing the independent evidence that proves a parsed artifact
     still matches captured bytes.
- **Approach:** `plan-tool` per item — each is a genuine design decision,
  not a mechanical dedup.
- **Origin:** 2026-08-17 code review of the roadmap escalation/impact
  modules.
- **Status:** not started.

**#318 — Audit `.gitignore` correctness and consolidate ignore-rule management onto a single tracked location**

- **What:** Two related checks. (a) **Audit the tracked root `.gitignore`
  for gaps**: `.pytest_cache` is listed explicitly, but the exactly-parallel
  `.ruff_cache` is not — it is ignored today only because ruff happens to
  drop its own self-generated `.ruff_cache/.gitignore` (a bare `*`) the first
  time it runs, an implicit, tool-version-dependent safety net rather than an
  explicit repo guarantee. Confirm there is no other cache/tool directory in
  the same situation. (b) **Consolidate ignore-rule *location*.** This repo's
  ignore rules are currently split across five places: the tracked root
  `.gitignore`; one tracked nested `experiments/refactor-characterization-replay/.gitignore`
  (narrowly scoped, single regenerable file, correctly explained — a good
  model to match); this machine's `.git/info/exclude`, which carries nine
  `**/.claude/*` runtime-state patterns (`scheduled_tasks.lock`,
  `scheduled_tasks.json`, `routines/.state/`, `worktrees/`, `checkpoints/`,
  `mailbox/`, `agent-registry.json`, `agent-memory-local`,
  `assistant-daemon-state.json`, `first-run`); and this user's global
  `~/.config/git/ignore`, which carries `**/.claude/settings.local.json`.
  None of those ten patterns ship with the repo — `git ls-files .claude/`
  returns empty today only because nothing has collided yet, not because
  anything tracked protects a fresh clone. Any other contributor (or this
  user on another machine) has zero built-in protection against
  `git add -A`/`run --commit` sweeping Claude Code session/runtime state into
  a commit. Evaluate folding the repo-relevant subset of those patterns into
  the tracked root `.gitignore` (or a new tracked `.claude/.gitignore` that
  travels with the directory) so the guarantee is explicit and portable
  instead of living in per-machine config.
- **Why:** this repo's own CLAUDE.md "Prefer the explicit over the implicit"
  directive: an ignore rule that exists only in one person's local git config
  or clone-local excludes is exactly the fact that should be stated once,
  explicitly, in the tracked repo rather than left to be inferred from
  "nothing has broken yet." The risk is not hypothetical — `run --commit` is
  standing policy for this tool's own pipeline and stages via `git add -A`.
- **Effort:** small — auditing and editing existing ignore files; no code
  changes.
- **Risks:** low. Worst case is over-broadly ignoring a path that should stay
  tracked; the verification step below catches that before it lands.
- **Dependencies:** none.
- **Outcome:** every ignore pattern that protects a repo-relevant,
  contributor-relevant path (not only this machine's) is tracked in one
  explicit, repo-committed location, and the tracked `.gitignore` is
  confirmed not to miss an equivalent-risk path the way it currently misses
  `.ruff_cache`.
- **In scope:** root `.gitignore`; whether to add a tracked
  `.claude/.gitignore` versus folding patterns into root `.gitignore`; the
  `.ruff_cache` gap; auditing `.git/info/exclude` and the user's global
  `~/.config/git/ignore` for any other repo-relevant (not genuinely
  machine-personal) pattern that belongs in the repo instead.
- **Out of scope / Non-goals:** genuinely machine-personal excludes (editor
  swap files, personal scratch directories unrelated to any repo tool) stay
  local — only patterns protecting repo/tool-generated state that any
  contributor's clone can produce move. No speculative new ignore categories
  without a real, currently-existing producer. No restructuring of the
  already-explicit, already-tracked `.plan-tool/*` entries.
- **Allowed behavior changes:** none beyond adding/relocating ignore
  patterns.
- **Allowed reorganization:** may introduce one new tracked
  `.claude/.gitignore` if that is the chosen consolidation shape; no other
  new files.
- **Verification:** `git check-ignore -v` on each moved pattern resolves to
  the new tracked location, not `.git/info/exclude` or the global
  excludesfile; `git status --ignored` diffs empty before/after (no newly
  untracked or newly ignored files as a side effect); confirm `.ruff_cache`
  is ignored by an explicit repo rule independent of ruff's self-generated
  file by temporarily removing `.ruff_cache/.gitignore` and re-checking
  `git status`.
- **Stop / defer:** if consolidating surfaces a genuine cross-repo question
  (e.g. whether `.claude/` runtime patterns belong in every plan-tool-adjacent
  repo, not just this one), defer that to a separate entry — this item is
  scoped to this repo's own ignore files only.
- **Approach:** `direct` — auditing and editing ignore files; the only design
  choice (root `.gitignore` vs. a new `.claude/.gitignore`) is small enough
  to resolve inline without a plan.
- **Status:** not started.
- **Origin:** 2026-08-24 — raised while reviewing this repo's ignore-file
  layout; confirmed via `git check-ignore -v` and `git ls-files` that the
  `.claude/*` runtime-state patterns currently live only in machine-local
  git config, not in any tracked file.

**#316 — Shared confidence-tag rendering helper (consolidate ~31 hand-authored call sites)**

- **What:** `plan_tool/review.py`'s `confidence_label`/`confidence_value` are
  the only shared primitives for rendering a `Recommendation.confidence`
  value; every call site that embeds the human-facing tag hand-authors its
  own surrounding format instead of a shared fragment — bracketed `[...]`,
  parenthesized-with-trailing-clause, middle-dot-joined, and
  em-dash-suffixed forms are all present, producing visibly inconsistent
  presentation for what rendered byte-identically before the
  `recommendation-confidence` plan (2026-08-26) introduced the field.
- **Why:** raised as a CONFIRMED finding (#13) in that plan's `/code-review`
  pass; declined for the plan's bounded fix sweep because a single
  whole-line formatter would conflate intentionally different report,
  prompt, CLI, and JSON grammars — but the underlying inconsistency itself
  was not disputed, only deferred as out of that sweep's proportion.
- **Effort:** small-medium — no design ambiguity in `confidence_label`
  itself; touches ~13 files at ~31 call sites, each a mechanical
  string-format edit with existing test coverage to catch drift.
- **Risks:** low individually; the volume is what makes an unswept partial
  pass worse than either finishing or not starting — a half-migrated
  call-site set leaves two conventions live instead of one.
- **Dependencies:** none.
- **Outcome:** one shared helper renders the "confidence tag" fragment
  consistently everywhere a human-facing string embeds a `Recommendation`'s
  confidence next to its severity/title, and every current call site is
  migrated to it.
- **In scope:** `plan_tool/review.py` (`confidence_label` plus the new
  helper), `plan_tool/review_walk.py`, `plan_tool/create.py`,
  `plan_tool/convergence_diagnosis.py`, `plan_tool/completeness_report.py`,
  `plan_tool/detail.py`, `plan_tool/launcher.py`,
  `plan_tool/cli/review_actions.py`, `plan_tool/cli/inspect.py`,
  `plan_tool/cli/completeness_phases.py`, `plan_tool/cli/reconcile.py`,
  `plan_tool/cli/data_contract_cmd.py`, `plan_tool/cli/review_cmd.py`, and
  each file's mirrored test module.
- **Out of scope / Non-goals:** the `--json` payload's `confidence_value`
  raw-enum projection (5 sites in `completeness_phases.py`) — that split is
  deliberate and `DATA_CONTRACT.md`-documented, stays a separate function,
  and is not migrated to the human-facing helper. No new confidence tiers,
  no verbosity gating, no change to which findings are supported vs.
  limited.
- **Allowed behavior changes:** none — rendered text may only change to the
  extent call sites currently disagree in bracket/punctuation style; no
  wording, tier, or field-selection change.
- **Allowed reorganization:** adding one new function to
  `plan_tool/review.py` (or extending `confidence_label`'s signature); no
  file moves.
- **Verification:** `grep -rn "confidence_label(\|confidence_value("
  plan_tool/` returns only the new helper's own definition/call sites plus
  the `confidence_value` JSON sites; full suite green; spot-check that each
  migrated site's rendered string is unchanged except for the specific
  inconsistency being fixed — existing tests pin most of these strings
  already, so expect several to need updating, which is the expected
  outcome of a class-wide sweep rather than a reason to stop (per this
  repo's own "a red sibling test during a class sweep is the expected
  outcome" rule).
- **Stop / defer:** if a call site's surrounding format encodes information
  the shared fragment can't represent generically (e.g.
  `review_walk.py:715`'s trailing "already ..." clause), defer that one
  site with a stated reason rather than force it, and record the exclusion
  here or in the follow-up plan.
- **Evidence:** identity established 2026-08-26 by
  `grep -rn "confidence_label(\|confidence_value(" plan_tool/` (not by
  inspection; re-verified 2026-08-26 during that plan's `/code-review` pass,
  which caught the original count drifting from re-running the same grep —
  keep this number reproducible-checked, not copied forward) — 31 call sites
  of `confidence_label` across 13 files outside
  `review.py`'s own definition, plus 5 `confidence_value` sites confined to
  `completeness_phases.py`'s `--json` rendering. At least four distinct
  surrounding-format families confirmed: bracketed `[...]` (majority —
  `completeness_phases.py`, `launcher.py`, `review_actions.py`,
  `inspect.py`, `reconcile.py`, `data_contract_cmd.py`, `review_cmd.py`,
  `detail.py`, and `review.py`'s own report/prompt renders),
  parenthesized-with-trailing-clause (`review_walk.py:715`,
  `"(...; already ...)"`), middle-dot-joined with no brackets
  (`review_walk.py:905`, `"source: X · confidence_label"`), and
  em-dash-suffixed with no brackets (`create.py:5584`). **Do-not-merge
  exclusion:** the 5 `completeness_phases.py` `confidence_value` sites are a
  distinct, deliberate raw-enum JSON projection and must not be folded into
  the human-facing helper.

  **Re-confirmed 2026-08-26 by a follow-up `/code-review high` pass on this
  same diff, surfacing 5 additional concrete duplicate-pair instances (all
  already inside the "In scope" file list above, none new in scope) plus
  one genuine functional divergence, not merely cosmetic:**
  `plan_tool/cli/completeness_phases.py:_render_grouped_report` hand-rolls
  the confidence-tagged bullet 6 times (`correctness_recs`,
  `data_contract_recs`, `conceptual_recs`, `smell_recs`,
  `self_consistency_recs`, `purity_coverage_recs`) instead of calling
  `plan_tool/completeness_report.py:_fmt_finding_line`, which already
  builds the identical bullet — and 5 of the 6 copies use
  `f" \`[{rec.anchor}]\`" if rec.anchor else ""` (omits the tag entirely on
  a falsy anchor) while `_fmt_finding_line` uses `_anchor_value(rec)` =
  `rec.anchor or rec.id` (always renders something) — verified by reading
  both, not by report alone. Also confirmed:
  `plan_tool/completeness_report.py:_fmt_finding_line`/`_fmt_pending_line`
  are near-duplicate formatters edited in lockstep for this diff (the
  latter's own docstring already says "the same shape as
  `_fmt_finding_line`"); `plan_tool/cli/reconcile.py`'s `_walk_saved` and
  `_save_and_walk_run_reconcile` print an identical two-line `[REDIRECT]`
  block; `plan_tool/cli/review_actions.py`'s resolves/introduces
  validation-print pair duplicates the same format string; and
  `plan_tool/cli/review_cmd.py`'s `_cmd_review_body` and `cmd_review_walk`
  contain a byte-identical non-interactive recommendation-listing loop
  body. Fold these named sites and the anchor-fallback divergence into the
  eventual fix rather than re-deriving them.
- **Approach:** `direct` — mechanical string-format migration across
  enumerated call sites with existing test coverage to catch drift; no
  design decision large enough to need a plan.
- **Status:** not started.
- **Scheduling:** follow the selected #216 position-01 benchmark work. This
  consolidation is worthwhile only as a complete class-wide migration; it is
  not a prerequisite for measuring noise floors and must not be combined with
  confidence calibration, new tiers, or behavior changes.
- **Origin:** 2026-08-26 — code-review finding #13 on the
  `recommendation-confidence` diff (handoff notes captured, at the time of
  filing, in the gitignored `.tmp/recommendation-confidence.code-review-handoff.md`
  scratch file — not a durable citation; the reproducible evidence is the
  grep above), declined for that bounded fix sweep as
  out-of-scope-for-that-pass rather than refused. Remapped from a colliding
  local `#313` during the 2026-08-26 merge that kept origin/main's `#313`
  for the long-running-process exposure.

**#308 — Retire legacy Jira-grade detail artifacts and readers** → promoted to IPPT-17 (2026-09-28)

**#406 — `roadmap_diff.py`/`roadmap_compare_run.py` import `plan_tool.roadmap`, contradicting the documented read-only layering**

- **What:** `docs/ARCHITECTURE.md` § "Read-only snapshot comparison" states the
  comparison branch (`roadmap_compare_run.py`, `roadmap_compare.py`,
  `roadmap_diff.py`, `roadmap_compare_render.py`) "imports version and
  artifact-reader leaves, owns no lifecycle transition, and does not import
  or invoke roadmap writers." At HEAD, `roadmap_diff.py` imports
  `RoadmapStage` and `roadmap_compare_run.py` imports `STAGES`, both from
  `plan_tool.roadmap` — the stage-execution/backend-invoking module the
  claim says this branch avoids. `RoadmapStage`/`STAGES` are themselves pure
  data (no functional dependency on the backend stack); the coupling is an
  artifact of where they happen to be defined. A second edge (2026-09-29):
  `roadmap_compare_run.py` imports `load_stored_candidate_proposal` from
  `roadmap_candidate_run.py`, which imports `roadmap_revision_publish`,
  `roadmap_feedback_ledger`, `shell`, and `RunLogWriter`; the comparison route
  only reads through it, but the graph reaches writer modules. Fix by moving
  the stored-candidate loader into a read-only leaf. Not a merge of look-alikes:
  the loader is a single function with one comparison caller.
- **Effort:** small in isolation (extract `RoadmapStage`/`STAGES` into a new
  leaf module importing only `roadmap_artifacts.py`/`roadmap_gates.py`,
  re-exported from `roadmap.py` for its own callers) — **but see Risks**.
- **Risks / fallout:** a same-session attempt at this exact extraction
  (2026-09-21) broke `roadmap_candidate.py`'s `GateCleanCandidate` Pydantic
  model: moving `RoadmapStage` out of `roadmap.py` changed import-order
  timing enough that `RoadmapGateOutcome`'s nested forward-ref
  (`violations: tuple[Violation, ...]`) stopped auto-resolving at class
  build, and neither an explicit `Violation` import into
  `roadmap_candidate.py` nor several other attempted workarounds fixed it
  within a reasonable session budget — the failure traced into
  Pydantic v2/Python 3.14 `annotationlib` internals for nested plain
  dataclasses resolved through an unrelated model's namespace. Revert
  commit/diff for the attempted fix is available in this session's history
  if useful as a starting point. Whoever picks this up should budget time to
  either fully understand that resolution path first, or land the
  extraction with `GateCleanCandidate`/`RoadmapGateOutcome` explicitly
  re-verified (not just the touched files' own test suites) before calling
  it done.
- **Dependencies:** none.
- **Approach:** `direct`, once the Pydantic risk above is retired — this is
  a pure import-graph fix with no behavior change, not new capability.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; the doc claim remains inaccurate at HEAD.

**#407 — Verify and resolve the JSON-value-projection duplication across roadmap comparison/candidate modules**

- **What:** a `/code-review high` pass on `roadmap-concept-comparison`
  flagged `roadmap_compare_render.py:_json_value` as re-implementing the
  same enum/dataclass/tuple/mapping→JSON walk already present as
  `roadmap_candidate.py`'s `_wire_value` (itself already duplicated
  verbatim in `roadmap_candidate_context.py` and `roadmap_candidate_run.py`
  and `roadmap_candidate_review.py`), `roadmap_source_identity.py`'s
  `_canonical_value`, and `roadmap_json.unwrap_enum_value`. `_json_value` is
  **not** flagged by `tests/test_duplication.py`'s AST-normalized exact-match
  guard, so byte/AST identity across these implementations has not been
  machine-established — per the consolidation-evidence rule in `docs/TRACKING.md` (and
  #79's history), re-derive identity before merging anything.
- **Checklist:**
  1. Run the normalized-body comparison `test_duplication.py` uses (or
     equivalent) across `_json_value`, `_wire_value` (all 4 sites),
     `_canonical_value`, `roadmap_json.unwrap_enum_value`, and
     `roadmap.py`'s `_prompt_json_value` to see which pairs actually match
     past docstrings/names/params, and which only resemble each other.
  2. For each confirmed-identical pair, consolidate onto one shared helper
     (`roadmap_json.py` is the existing shared home) with a test pinning the
     preserved behavior; for each look-alike that differs (e.g. a mapping
     key-sorting or non-JSON-safe-value refusal one has and another lacks),
     document the difference as the reason they stay separate.
  3. **Known divergence already confirmed (2026-09-21, round 4 of this same
     review), not yet re-derived against the checklist's normalization:**
     `_canonical_value` and `_json_value` both reject a non-string `Mapping`
     key with `TypeError`; `roadmap.py:_prompt_json_value` silently
     `str()`-coerces one instead. Whichever behavior the consolidation keeps
     is a real, user-visible choice (fail closed vs. permissive coercion) —
     decide and test it explicitly, don't let the merge pick one by
     accident of which implementation happened to "win." **Second
     divergence (2026-09-21, round 5):** `_json_value` sorts `Mapping` keys
     in its output; `_wire_value`'s sites don't. Same rule applies — decide
     and test which behavior the consolidation keeps.
- **Effort:** small–medium — mechanical once identity is established; the
  4-site `_wire_value` duplication alone touches 4 files.
- **Risks / fallout:** low if the checklist is followed; the risk is
  skipping step 1 and merging on resemblance alone (the #79 failure mode).
- **Dependencies:** none.
- **Approach:** `direct`.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started.

**#408 — `roadmap_compare_run.py` spawns a Git subprocess per artifact even when bytes are already known identical**

- **What:** `_capture_patches` writes both before/after bytes to disk and
  runs `git diff --no-index` for all four fixed roadmap artifacts on every
  `--compare` invocation, even for artifacts whose `before`/`after` bytes are
  already byte-equal (the common case — most comparisons change one
  artifact). A byte-equality short-circuit would skip the file writes and
  subprocess spawn for the unchanged artifacts.
- **Effort:** small.
- **Risks / fallout:** `roadmap_compare.py`'s own docstring states raw-patch
  collection deliberately "does not validate whether a patch was collected
  correctly; Git collection owns that boundary" — i.e. the code intentionally
  treats Git's own diff result, not an in-process byte comparison, as the
  single source of truth for "identical or not." A short-circuit needs to
  preserve that: skip the subprocess only when it can't change the *result*
  (status/patch), not as a trust shift from Git to Python. Cost today is
  negligible (≤4 subprocess spawns per interactive CLI invocation, not a hot
  loop) — this is a minor efficiency item, not a correctness fix.
- **Dependencies:** none.
- **Approach:** `direct`.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority.

**#409 — `build_roadmap_diff`'s `predecessor_bytes`/`candidate_artifacts_bytes` are positional, unlike its own keyed `*_artifacts` parameters**

- **What:** `roadmap_diff.py:build_roadmap_diff` takes
  `predecessor_artifacts`/`candidate_artifacts` as `Mapping[str,
  RoadmapArtifact]` keyed by artifact key, but `predecessor_bytes`/
  `candidate_artifacts_bytes` as plain positional `tuple[bytes, ...]`,
  zipped against `stages` with only a length check (`strict=True`). Nothing
  verifies index `i`'s bytes actually belong to `stages[i].artifact_key` —
  the correspondence is caller discipline, not construction.
- **Effort:** small–medium — 2 production call sites
  (`roadmap_compare_run.py`, and `roadmap_candidate.py`'s
  `_build_predecessor_diff` inside its candidate-materialization pipeline)
  plus test call sites in `tests/test_roadmap_compare.py`,
  `tests/test_roadmap_compare_render.py`, `tests/test_roadmap_diff.py`.
- **Risks / fallout:** **both current callers are verified correct today**
  (kept in sync by `tests/test_roadmap_versions.py::test_leaf_version_inventory_matches_the_orchestrator_stage_table`),
  so this is a latent robustness gap, not a live bug — no severity beyond
  "the contract relies on caller discipline with no assertion." The
  `roadmap_candidate.py` call site sits inside the candidate-materialization
  pipeline, a business-critical, heavily-used module **outside this plan's
  own diff** (touched only by this same review's round-1 dead-import
  cleanup) — a same-session round-2 attempt at a different `roadmap.py`/
  `roadmap_candidate.py`-adjacent extraction (see #406) broke an unrelated
  Pydantic model in that exact module in a way that took real effort to
  diagnose and was ultimately reverted rather than risk shipping unverified.
  Treat any change touching `roadmap_candidate.py`'s call site with the same
  caution: verify `tests/test_roadmap_candidate.py` fully, not just the
  touched call site's own test. **Prior art for the suggested fix already
  exists in this codebase:** `roadmap_candidate_context.py:_verify_predecessor`
  explicitly validates `STAGES` keys against `VERSION_ARTIFACT_INVENTORY`
  before trusting positional pairing, rather than assuming it — read that
  function before designing this one (found 2026-09-21, round 5 of this
  same review).
- **Suggested fix:** make `predecessor_bytes`/`candidate_artifacts_bytes`
  `Mapping[str, bytes]` too, matching the sibling parameters already on the
  same signature; look up `predecessor_bytes[stage.artifact_key]` instead of
  positional zip. Removes the risk by construction rather than by adding an
  assertion (there's nothing to assert against — the bytes carry no label of
  their own today).
- **Dependencies:** none.
- **Approach:** `direct`, once verified against `roadmap_candidate.py`'s full
  suite, not just this feature's own tests.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority (latent, not reachable today).

**#410 — `_has_roadmap_comparison` hand-inlines the default-value case `_option_occurrences` doesn't generalize**

- **What:** every sibling `_has_X` predicate in `cli/roadmap_cmd.py` is a
  one-line `bool(_option_occurrences(args, "..."))`, because every other
  exclusive-mode flag's argparse default is `None`. `--comparison-output`
  is the one flag in the comparison group with a non-`None` default
  (`"cards"`), so `_has_roadmap_comparison` instead hand-inlines:
  `bool(getattr(args, "_comparison_output_occurrences", ())) or
  getattr(args, "comparison_output", "cards") != "cards"`.
- **Effort:** small — add an optional `default=None` parameter to
  `_option_occurrences` (backward-compatible for every existing caller),
  then rewrite `_has_roadmap_comparison` as a one-liner matching its
  siblings.
- **Sharper framing (2026-09-21, round 11 of this same review):** this is
  not just cosmetic — `_option_occurrences`'s own contract ("not supplied →
  empty tuple") is actually **broken** for any tracked option whose
  argparse default isn't `None`, `--comparison-output` being the only
  current example. `_option_occurrences(args, "comparison_output")` with no
  flag given falls through to `getattr(args, "comparison_output", None)`,
  which returns the argparse default `"cards"` (not `None`), so it
  incorrectly returns `("cards",)` instead of `()`. Currently masked only
  because the sole call site checks `len(...) > 1`; a future caller that
  checks `not _option_occurrences(args, "comparison_output")` to mean
  "never supplied" would get the wrong answer. The `default=None` parameter
  above is exactly the fix for this, not just for the style inconsistency.
- **Risks / fallout:** `_option_occurrences` is called from most `_has_X`
  predicates in a large file (`cli/roadmap_cmd.py`) — low risk given the
  change is purely additive with a safe default, but touches a
  widely-shared helper, so verify the full `tests/cli/test_roadmap_cmd.py`
  suite, not just the comparison tests.
- **Dependencies:** none.
- **Approach:** `direct`.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority (style/consistency, not a bug).

**#411 — `--compare` can silently drop one of two duplicate-id rows instead of reporting them**

- **What:** `run_roadmap_comparison` goes straight from snapshot loading to
  `build_roadmap_diff` with no gate check, unlike `roadmap_candidate.py`'s
  materialization pipeline, which always calls `check_complete_roadmap_gates`
  first. `roadmap_artifacts.py` deliberately does not reject duplicate row
  ids at parse time (so the duplicate-id gate has something to report), and
  `roadmap_diff.py:artifact_row_diffs` builds `before_by_id = {row.id: row
  for row in before_rows}` — a plain dict that silently keeps only the last
  row for a duplicated id. Comparing a working roadmap directory that
  currently has a duplicate id (a realistic mid-revision state, before gates
  are re-run) silently omits one of the duplicated rows from `--compare`
  output with no error or warning — nothing tells the operator evidence was
  dropped. **Sharper reproduction (2026-09-21, round 11 of this same
  review):** the two directions of the bug are not symmetric. A duplicate
  id on the **after** side collapses via dict construction before the
  removed/changed loop even runs, so the surviving after-row masks the
  other — one of the two after-rows vanishes with **zero trace anywhere**
  in the output. A duplicate id on the **before** side instead produces
  **multiple** `RoadmapRowDiff`/`ComparisonCard` entries sharing one
  `row_id`, each showing a different stale "before" value diffed against
  the same collapsed "after" — misleading rather than silent. Both are the
  same root cause (`{row.id: row for row in rows}` collapsing on
  construction), now the shared `_diff_by_id` helper both `artifact_row_diffs`
  and `_ordering_diffs` call (round 9 of this review); fixing it fixes both
  row-kind and ordering-kind comparisons at once.
- **Effort:** small–medium. A standalone `check_duplicate_row_ids(envelope:
  ArtifactEnvelope) -> list[Violation]` already exists in `roadmap_gates.py`
  (noted there as "the one exception" to some rule worth reading before
  reusing) — likely cheaper than running the full gate battery, but wiring
  it needs understanding `ArtifactEnvelope` construction, which this review
  round didn't have budget to fully investigate.
- **Risks / fallout:** low — this only adds a pre-check in
  `roadmap_compare_run.py` (new code, this plan's own scope); does not
  require touching `roadmap_candidate.py` or `artifact_row_diffs`'s
  established dedup behavior (which has its own preservation contract from
  the plan that extracted it, "preserving candidate add, replace, and
  remove behavior" — do not change that function's behavior to fix this).
- **Dependencies:** none.
- **Approach:** `direct`.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority (narrow trigger — a roadmap must
  already be in a duplicate-id state, which gates normally prevent
  reaching).

**#412 — `--compare`'s relation matching is O(n·m) and now unconditionally reachable**

- **What:** `roadmap_diff.py:relation_occurrence_diffs` matches declared
  relations via a linear scan rather than a dict/counter keyed on relation
  identity. `build_roadmap_diff` calls it unconditionally, and
  `run_roadmap_comparison` calls `build_roadmap_diff` unconditionally with no
  gating flag — so a roadmap with many declared relations (components,
  constraints, and plans artifacts routinely carry many `entity_ids`/
  `component_ids`/`depends_on` relations) now pays O(n²) match time on every
  `--compare`, a route that previously only ran during candidate review.
- **Effort:** small, once measured.
- **Risks / fallout:** no measurement exists yet showing this is actually
  slow at realistic roadmap sizes — do not optimize on the finding's say-so
  alone; measure first (a roadmap with the largest realistic relation count
  this tool has seen), and only implement a keyed match if the measured cost
  is material.
- **Dependencies:** none.
- **Approach:** `direct`, gated on a measurement.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority, unmeasured.

**#413 — A `--compare`'d stored artifact's bytes get SHA-256'd up to three times in one call**

- **What:** for a stored/version snapshot, artifact bytes are hashed once
  during `load_resolved_stored_version`'s integrity check against the
  recorded digest, again in `roadmap_compare_run.py:_build_snapshot`, and
  again in `build_roadmap_diff` for any artifact found to differ — pure
  wasted CPU scaling with artifact size and comparison frequency, when the
  already-verified digest could be threaded through instead.
- **Effort:** small–medium — threading the digest through touches
  `ResolvedRoadmapVersion`/`RoadmapComparisonSnapshot`'s shapes.
- **Risks / fallout:** low severity — roadmap artifacts are markdown files
  (KB-scale), so SHA-256 cost here is microseconds even done 3x; this is a
  correctness-neutral efficiency item, not worth spending a structural
  change on without evidence it matters in practice.
- **Dependencies:** none.
- **Approach:** `direct`, low priority.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority.

**#414 — Each `--comparison-output` mode computes strictly more than it uses**

- **What:** two instances of the same shape, both in this plan's new code.
  (1) `run_roadmap_comparison` unconditionally parses both snapshots, runs
  `build_roadmap_diff` (row/relation diffing), and `build_roadmap_comparison`
  (card construction, field projection, hashing) before the CLI even
  selects a renderer; `render_patch_comparison` consumes only `run.patches`
  (the raw Git output) — the typed-diff/card work is computed and discarded
  on every `--comparison-output patch` call. (2) Conversely,
  `render_terminal_comparison` (the *default* `cards` mode) routes through
  `comparison_json_payload`, which always materializes the full
  `raw_evidence` list (complete unified-diff text for all four artifacts)
  even though no terminal-renderer helper reads that key — found 2026-09-21,
  round 6 of this same review.
- **Effort:** medium — making this lazy means either threading the
  requested output mode down into `run_roadmap_comparison` (changing its
  signature and its `RoadmapComparisonRun` return contract, which currently
  always carries a populated `.comparison`) or restructuring so `.comparison`
  is computed lazily. Either touches the shared read path all three output
  modes currently go through identically — a correctness-preserving
  property worth keeping in mind while changing it.
- **Risks / fallout:** no measurement exists showing this costs anything at
  realistic roadmap artifact sizes (KB-scale markdown) — do not restructure
  on the finding's say-so alone; measure first.
- **Dependencies:** none.
- **Approach:** `direct`, gated on a measurement.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority, unmeasured.

**#415 — `CandidatePredecessorDiff = RoadmapDiff` is a permanent alias across ~18 call sites**

- **What:** `roadmap_diff.py` keeps `CandidatePredecessorDiff` as a
  compatibility name for `RoadmapDiff` "while the shared module stays
  policy-free," while its 3 siblings (`CandidateArtifactDiff`,
  `CandidateRowDiff`, `CandidateRelationDiff`) were deleted outright once
  unused (see #406's sibling cleanup, landed). Two names for one type
  is a standing drift risk: a future edit could give `CandidatePredecessorDiff`
  its own fields, recreating the two-diff-engine problem this plan's
  extraction closed.
- **Effort:** small mechanically (rename ~18 references across
  `roadmap_diff.py`, `roadmap_candidate.py`, `roadmap_candidate_run.py`,
  `roadmap_candidate_review.py`, and their tests to `RoadmapDiff` directly),
  **but** touches the same candidate-materialization module family whose
  fragility this exact review loop hit once already this session (#406's
  reverted attempt broke an unrelated Pydantic model there). Purely
  cosmetic/preventive — no current bug — so budget verification time
  accordingly before starting, not just the mechanical rename time.
- **Risks / fallout:** low functional risk if done carefully (a rename, not
  a behavior change), but see the module-family caution above.
- **Dependencies:** none.
- **Approach:** `direct`, with the same caution as #409 about verifying
  `tests/test_roadmap_candidate.py` fully.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority (preventive, not a current bug).

**#416 — `design_row_collections`'s fallback branch has no type guard, affecting several pre-existing callers**

- **What:** `roadmap_artifacts.py:design_row_collections`'s final branch
  (for anything that isn't `DomainArtifact`/`ConstraintsArtifact`/
  `ComponentsArtifact`) unconditionally returns
  `{"plans": artifact.plans, "assumptions": artifact.assumptions,
  "decisions": artifact.decisions}` with no `isinstance(artifact,
  PlansArtifact)` check — a genuinely unsupported type reaching it degrades
  to a confusing `AttributeError` instead of a clear refusal, or (if the
  wrong object happens to expose similarly-named attributes) silently wrong
  data. `roadmap_diff.py:ordered_stage_collections` (this plan's own new
  code) was given a local fail-closed guard for exactly this reason, but
  `roadmap_revision_patch.py`, `roadmap_revision.py`'s
  `_design_rows_by_collection`/`_stage_rows_by_collection`, and
  `roadmap_structural_revision_proof.py:_require_row_inventory` all call
  the same underlying function through `stage_row_collections` with no
  equivalent guard — pre-existing code, outside this plan's diff, sharing
  the pre-existing gap.
- **Effort:** small — add one `isinstance` check to `design_row_collections`
  (or `stage_row_collections`) itself, which fixes it at the source for
  every current and future caller at once, rather than requiring each
  caller to carry its own local guard (as `ordered_stage_collections` now
  does — that local guard should stay regardless, as defense-in-depth, once
  this lands).
- **Risks / fallout:** `roadmap_artifacts.py` is a foundational, widely
  imported module — low functional risk (this only makes an already-invalid
  call fail with a clearer error; every well-formed caller is unaffected),
  but verify the full suite, not just the touched callers' own tests, given
  how many modules import this function.
- **Dependencies:** none.
- **Approach:** `direct`.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority (latent — every current caller
  already passes a valid artifact).

**#417 — A pure reorder of an ordering row's `depends_on`/`assumption_targets` produces a "changed" card with an empty field summary**

- **What:** `OrderingEntry`'s only non-id fields (`depends_on`,
  `assumption_targets`) are both declared relation fields
  (`_RELATION_FIELD_NAMES[OrderingEntry]`), so `_changed_projected_fields`
  is structurally always `()` for an ordering row — but
  `_card_for_row_diff`'s `row_diff.row_type != "ordering"` carve-out keeps
  the card alive anyway (ordering rows always get a card when matched-and-
  different). Reordering `depends_on` without changing its membership (e.g.
  `("a","b")` → `("b","a")`) is a real, detected change
  (`artifact_row_diffs` catches it via raw dataclass inequality), but
  relation matching (`same_declared_relation_occurrence`) is deliberately
  order-insensitive ("without conflating source position"), so it produces
  no added/removed relations either — the card says "changed" with an empty
  `changed_fields` list. **Not a full information loss**: the card's own
  `before`/`after` fields always carry the complete, unstripped
  `OrderingEntry` (rendered in both the terminal and JSON output), so the
  actual reordering is visible there — just not summarized in
  `changed_fields` the way other field changes are.
- **Effort:** medium — the clean fix (making ordering-relation matching
  order-sensitive) would change `relation_occurrence_diffs`'s shared,
  deliberately order-insensitive matching for every row type, not just
  ordering; a narrower fix (special-casing `changed_fields` for ordering
  rows only) needs to avoid reintroducing double-reporting for a genuine
  membership change, which the relation diff already covers correctly.
- **Risks / fallout:** low severity given the before/after mitigation above;
  untested edge case (`test_ordering_entry_is_a_separate_comparison_card`
  only exercises a membership addition, not a same-membership reorder).
- **Dependencies:** none.
- **Approach:** `direct`, once a fix shape is chosen — needs a design
  decision (widen relation matching vs. special-case ordering), not just an
  implementation.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority (narrow — same-membership reorder
  with no other field change).

**#418 — `RoadmapArtifactDiff.before_digest`/`.after_digest` are computed but never consumed**

- **What:** `build_roadmap_diff` computes `hashlib.sha256(...).hexdigest()`
  for both `before_digest` and `after_digest` on every changed artifact, but
  no caller anywhere in the codebase reads either field — only
  `.artifact_key` is ever consumed (`roadmap_compare.py:117`,
  `tests/test_roadmap_diff.py`). The comparison feature's JSON output
  already surfaces per-artifact digests through a different, more complete
  path (`RoadmapComparisonSnapshot.artifact_digests`, covering all 4
  artifacts, changed or not), making these two fields redundant as well as
  unused.
- **Effort:** small if removed — but `RoadmapArtifactDiff` is a public
  dataclass on `RoadmapDiff`, consumed by `roadmap_candidate.py`'s
  materialization pipeline too (via the `CandidatePredecessorDiff` alias,
  see #415); removing fields changes a shared type's shape, not just dead
  local code.
- **Risks / fallout:** verify nothing in `roadmap_candidate.py` relies on
  these fields' presence (even unread, e.g. via `_wire_value`'s generic
  dataclass-field walk feeding `_content_identity`'s hash) before removing
  them — the same candidate-pipeline caution as #406/#409/#415. A
  same-round-5 suggestion to instead just reuse the existing
  `sha256_digests()` helper here was declined as a wrong-shaped fit (that
  helper hashes a *sequence* of values; this is a single value each side —
  reusing it would mean an awkward one-element-tuple wrap for no real
  benefit over the plain `hashlib.sha256(x).hexdigest()` already here).
- **Dependencies:** none.
- **Approach:** `direct`, once verified against the candidate pipeline.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority.

**#419 — No working-roadmap reader (including `--compare`) locks against a concurrent writer**

- **What:** `roadmap_compare_run.py:_load_working_snapshot` reads the four
  working-roadmap artifact files with four independent, unsynchronized
  `read_bytes()` calls. If a `plan-tool roadmap <slug>` stage run is
  concurrently rewriting stage artifacts in the same directory while
  `--compare` reads them, the four reads can straddle the write, producing
  a torn cross-artifact snapshot (some files pre-write, some post-write).
- **Effort:** large if solved generally — **this is not specific to
  `--compare`**: no locking primitive exists anywhere in this codebase, so
  every reader of "working" roadmap state (not just this new feature) has
  the same latent exposure. A fix scoped to `_load_working_snapshot` alone
  would add asymmetric protection to one reader while leaving every other
  one unprotected — the wrong level to fix this at.
- **Risks / fallout:** requires an actual concurrency design decision (a
  lock file? a fingerprint-then-reread-to-verify pattern? accept it as a
  known limitation of a local, single-operator CLI tool where running two
  `plan-tool` invocations against the same roadmap directory simultaneously
  is already an unusual, self-inflicted usage pattern?) — not a mechanical
  fix. Judge whether this is worth solving at all before scoping an
  implementation.
- **Dependencies:** none.
- **Approach:** `plan-tool` (architect tier) if pursued — this is a
  cross-cutting design decision, not a `--compare`-local patch.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority (self-inflicted trigger; systemic,
  not feature-specific).

**#420 — `RoadmapComparison.raw_evidence_identity` is a stored field that's always derived from its sibling `raw_evidence` field**

- **What:** `build_roadmap_comparison` (the model's only construction site)
  always sets `raw_evidence_identity=raw_evidence_identity(raw_evidence)` —
  the field never varies independently of `raw_evidence` on the same
  object. Nothing prevents a hand-built `RoadmapComparison` (e.g. a test
  fixture) from setting the two inconsistently.
- **Effort:** small — convert to a computed property (or Pydantic
  `@computed_field`) deriving from `raw_evidence` at read time.
- **Risks / fallout:** low but needs care: `RoadmapComparison` is a frozen
  Pydantic `BaseModel`, so verify a computed property serializes correctly
  wherever the model (or its JSON projection) is consumed, not just that
  attribute access still works. Real risk is already near-zero today
  (single construction site, frozen/immutable model) — this is a
  simplification, not a fix for reachable drift.
- **Dependencies:** none.
- **Approach:** `direct`.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority.

**#421 — `--compare`'s companion-mode rejection list is only tested for 2 of ~9 sibling modes**

- **What:** `_roadmap_comparison_has_conflict` hand-enumerates roughly 9
  sibling mode-presence predicates (`_has_receipt_creation`,
  `_has_structural_rewrite`, `_has_feedback_reopen`,
  `_has_candidate_lifecycle_action`, `_broad_mode_companions_present`,
  etc.) that `--compare` must reject as companions. The guarantee is
  correct today (verified by reading the function), but
  `tests/cli/test_roadmap_cmd.py` only exercises 2 of the ~9 groups
  (`apply`, `confirm_brief_rebind`) against `--compare` — a future new
  roadmap mode added without a matching entry in this enumeration, or a
  reordering of `cmd_roadmap`'s dispatch relative to the `has_comparison`
  check, would have no test catching the regression.
- **Effort:** small — add one test case per untested companion group
  (~7 more), following the existing pattern in
  `test_comparison_rejects_companion_modes_before_comparison_loading` and
  its sibling `--confirm-brief-rebind` test.
- **Risks / fallout:** none — pure test-coverage addition, no production
  code change implied.
- **Dependencies:** none.
- **Approach:** `direct`.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority.

**#422 — `_card_for_row_diff`'s "ordering rows always get a card" carve-out is a hardcoded name check, not a structural derivation**

- **What:** `_card_for_row_diff` decides whether an empty-`changed_fields`
  row still produces a card via `row_diff.row_type != "ordering"` — a
  literal string match. `OrderingEntry` needs this carve-out because its
  entire non-id field set is declared relation fields
  (`_RELATION_FIELD_NAMES[OrderingEntry]`), so without it a genuine
  ordering-only change would silently produce no card (the same class of
  bug `#417` names for `OrderingEntry` specifically). The check is spelled
  as "is this literally the `ordering` row type," not "does this row type
  have any non-relation field" — the actual property that matters.
- **Effort:** medium — deriving the real property means mapping a
  `row_type` string back to its row class (no such table currently exists
  outside `ordered_stage_collections`'s literal tuples) and checking
  whether `_RELATION_FIELD_NAMES` covers every field `fields(row_type)`
  has other than the id.
- **Risks / fallout:** **deliberately not attempted this round** — this is
  a latent risk (only `OrderingEntry` has this all-relation-fields shape
  today; every other row type has at least one ordinary field), not a
  reachable bug. Building the general "detect an all-relation-fields row
  type automatically" mechanism now would be engineering for a row type
  that doesn't exist yet, not closing today's actual gap — the smaller,
  correct action is watching for this the next time a new row type is
  added to the schema, not building infrastructure preemptively.
- **Dependencies:** none — but re-evaluate whenever a new `StageRow` member
  is added (see the completeness test from round 7 of this review,
  `test_relation_field_names_covers_every_stage_row_type`, which will at
  least force a relation-field-coverage decision for any new type, even
  though it doesn't check *this* specific carve-out).
- **Approach:** `direct`, once (if ever) a second all-relation-fields row
  type is actually added.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** not started; low priority, deliberately deferred (latent,
  not reachable today).

### E. Cosmetic / churn

**#393 — `ROADMAP_FORMAT.md` calls a field "discharges" where the schema keyword is `constraint_ids`**

- **What:** `ROADMAP_FORMAT.md`'s component section describes a component as
  "discharging" prioritized constraints in prose, but the actual
  frontmatter/schema keyword the gates read is `constraint_ids`
  (`check_component_constraint_references`,
  `check_prioritized_constraint_discharge`). The prose name and the schema
  name don't match, which reads as if `discharges` were a quotable field name
  when it isn't one.
- **Effort:** small — doc wording only, no code or schema change.
- **Approach:** direct.
- **Origin:** 2026-09-17, noticed incidentally while reading
  `ROADMAP_FORMAT.md`'s component/constraint-discharge description during an
  AI-DLC comparison pass.
- **Status:** not started.

**#187 — Shorter carved-seed filenames**

- **What:** `scope-out` names its seed `<plan-slug>-carved-<full-step-slug>.md`
  — e.g. `jira-grade-01-detail-instrument-carved-run-the-one-off-mechanism-falsification.md`.
  Truncate the step slug to its first few words (keeping the collision-safe
  numbered-suffix behavior), or accept a name via flag. Cosmetic: nothing
  consumes the filename.
- **Effort:** small. **Approach:** direct. **Origin:** 2026-07-29 scope-out
  exercise.

**#223 — `RUNBOOK.md`'s self-consistency walkthrough omits the blocking intent finding**

- **What:** `RUNBOOK.md`'s "Completeness reports two concept-specific sources"
  passage names a medium `concept-coverage` finding as the blocking
  self-consistency example. `intent-presence` now blocks through the same
  bucket at `medium`, and the walkthrough never mentions it — so an operator
  reading the runbook after hitting the finding gets no remedy. The fix is one
  bullet naming the one-line `intent:` edit, alongside the existing note that
  neither source is `completeness-apply`-eligible (still true).
- **Effort:** small — prose only, no code, no tests.
- **Approach:** direct. **Origin:** 2026-08-02, `intent-required` step 8; the
  file was in neither that step's nor its sibling doc step's file list.
- **Status:** not started.

**#226 — `_preserve_on_disk_step_fields` carries `status` across a positional id match, with no identity check**

- **What:** the create `--iterate` loop merges a re-proposal onto the on-disk
  plan by **step id**, and ids are positional (`_parse_steps_json` assigns them
  from `enumerate`). A round that inserts, drops, or reorders steps therefore
  puts a *different* step under the same id, and `status` is carried across
  regardless.
- **Why:** a `done` status stamped onto a different step is worse than the
  intent case that motivated this entry — a later `run` skips work that was
  never performed, silently. The intent half was fixed 2026-08-03 by gating the
  carry-over on title equality (`prior.title == proposed.title`); `status` was
  deliberately **left alone** because it predates that branch (it was
  `existing_statuses.get(s.id, ...)` inline before step 5 extracted the
  function) and changing transition semantics is not a review-fix.
- **The fix is probably the same one-line gate**, but it needs its own test
  sweep: several existing tests assert status carry-over by id, and at least one
  (`test_prior_status_still_outlives_the_reproposal`) would need to state
  whether a retitled step at the same id keeps its status.
- **Dependencies:** none. `2-intent-required.md` shipped 2026-08-03.
- **Effort:** small — one condition, plus deciding what a retitled step's status
  should be.
- **Scope contract:**
  - **Outcome:** no step inherits another step's `status` from a positional id
    collision.
  - **In scope:** `_preserve_on_disk_step_fields`' status branch and its tests.
  - **Out of scope / Non-goals:** the intent branch (already fixed); changing
    where transitions are owned (`plan-tool run`, not create); any new identity
    scheme such as stable step uuids — that is a much larger change and would
    need its own entry.
  - **Allowed behavior changes:** one field stops transferring across a
    retitled step.
  - **Allowed reorganization:** none.
  - **Verification:** a re-proposal that retitles the step at id N leaves that
    step `pending` rather than inheriting N's prior status; an unchanged title
    still carries status as today.
  - **Stop / defer:** if the right answer turns out to need stable step
    identity rather than a title heuristic, stop and file that instead.
- **Approach:** `direct` — one condition, one decision, one test sweep.
- **Quality:** `grounding` — stops a positional collision from asserting work
  was done.
- **Origin:** 2026-08-03, xhigh review of `intent-required`; surfaced as the
  pre-existing half of the intent finding at `create.py:4919`.
- **Status:** not started.

**#263 — `scope-out`'s forward-seed doesn't reference the commits/reports carrying the carved region's prior design work**

- **What:** `scope-out --apply` writes a forward-seed from the carved step
  range's own **current** frontmatter (title/intent/files), so it already
  preserves whatever design content sits in `intent:` at carve time — hand-applied
  audit-finding fixes included, since those land as edits to that same
  `intent:` prose. What the generated seed carries **none** of is the
  *provenance* — which commits and which completeness-report findings
  produced that prose, and why it reads the way it does. A reader (human or a
  later audit) has no trail back to the reasoning.
- **Verified 2026-08-12 — this is a provenance gap, not a re-derivation
  risk, and appending commit hashes to the seed does not by itself fix
  anything `create --from-existing` mechanically does.** Checked
  `plan_tool/prompts/distill-seed.md`, the first pass `create --from-existing`
  runs over the raw seed: it states explicitly *"Do not inspect the
  codebase (no file reads, no searches)... work solely from the seed
  below"* — no git access of any kind. The only later codebase-reading
  step, `_render_local_code_grounding` (`plan_tool/create.py`), resolves
  `path:symbol` Architecture anchors against **current HEAD file text**; it
  has no git-history awareness and does not parse commit hashes out of
  prose. So a manually added "see commit `abc123`" citation in a seed is
  inert to today's pipeline — advisory for a human, or for a later,
  general-purpose tool-using Claude call that happens to decide on its own
  to go look, never something `create --from-existing` consults by design.
- **Concrete instance:** `batch-authoring-observability`'s round-2 audit
  (report `20260812-165729-completeness.md`) sharpened steps 10–12's design
  materially — the raw-transcript trigger definition (terminal outcomes only,
  not the transient stall marker), the transcript's own raw-line redaction
  requirement distinct from parser-level summary redaction, and `runs show`'s
  liveness-pid and exec-not-found distinctions — all landed in commit
  `050aea18`, folded directly into steps 10–12's `intent:` text. Carving
  those steps out with `scope-out --step 10 --through 12` correctly carried
  the fixed prose into the seed's "Scope to re-plan" sections (so the design
  itself was never at risk) but named no commit or report, so nothing in the
  seed explained *why* the prose said what it said. Added by hand afterward.
- **Fix sketch:** deterministic, no Claude call — `scope-out` already knows
  the plan slug and the carved step-id range. Append a short "prior context"
  block to the generated seed naming: (a) commit hashes since the plan's
  first commit that touched the plan file's carved step ids (a `git log -L`
  or per-line blame over the carved YAML block would locate these), and
  (b) paths under
  `docs/implementation-plans/plan-details/<slug>/reports/*.md` for
  completeness reports whose findings cite the carved step ids. This is worth
  doing purely as an audit trail even though nothing downstream reads it
  automatically today. **A separate, larger, explicitly out-of-scope-for-this-entry
  question**: whether `create --from-existing` should ever be allowed to
  consult such a block (loosening `distill-seed.md`'s "no inspection" rule
  for exactly this one carved-provenance case) is a prompt-design change,
  not a `scope-out` change, and needs its own seed if pursued.
- **Effort:** small-medium — no Claude call, but needs the carved-step-id →
  commit/report attribution logic, not just a static string.
- **Approach:** `direct`.
- **Origin:** 2026-08-12, carving `batch-authoring-observability` down to its
  core (steps 1–9) and filing steps 10–12 to a follow-on plan.
- **Status:** not started.

**#264 — `arm-clustering`'s consensus requirement could be satisfied across audit rounds, not only within one `--audit-passes` execution**

- **What:** `evaluate_arm_clustering` (`plan_tool/audit_shapes.py:194`) needs
  every material finding to carry a consensus target across ≥2 samples before
  it will fire — today those samples can only come from ≥2 passes inside one
  `completeness-audit` call, which is exactly what `--audit-passes 1` (the
  setting `CLAUDE.md`'s own stopping rule *recommends* for scope-contract-bound
  audits) disables. The two settings are mutually exclusive by construction, so
  the detector goes dark on the audits this repo's own convention steers
  towards.
- **Why this is fixable, not just a known limitation:** `evaluate_arm_clustering`
  takes `consensus_targets: Mapping[str, int]` as a plain input and its own
  docstring says it "deliberately keeps all... persistence concerns out of the
  registry leaf" — the ≥2-samples rule lives in whatever caller builds that
  mapping today (same-execution multi-pass), not in the detector. Meanwhile
  `classify_impact_recurrence` / `classify_edit_drift`
  (`plan_tool/convergence_diagnosis.py:895,950`) already read
  `build_collapsed_completeness_passes(history)` — cross-round persisted-history
  plumbing that a caller could equally use to build `consensus_targets` from
  round-over-round findings instead of live same-invocation passes. Nothing
  architectural blocks it; it would be a new caller, not a new leaf.
- **This is a different signal, not just a substitute — worth building
  deliberately, not by reflex.** Same-execution consensus answers "is the
  model's judgment about this arm stable on one frozen plan snapshot?"
  Cross-round persistence would answer "does this arm keep generating
  findings despite genuine remediation attempts between rounds?" — closer in
  spirit to `remedy-proportionality`/`check-saturation` (CLAUDE.md's other
  audit shapes) than to what the current detector measures, and arguably
  stronger evidence for "should this arm exist" than same-snapshot agreement.
  A round-over-round version needs its own judgment call about what counts as
  "the same target" across a plan that changed shape between rounds (a
  renumbered or split step shouldn't silently break the consensus chain) —
  not a mechanical swap of the input source.
- **Effort:** medium — a new caller wiring `consensus_targets` from collapsed
  history, plus the cross-round target-identity question above.
- **Approach:** `plan-tool` — explicitly needs its own scoped plan per
  `CLAUDE.md`'s convergence-policy-boundary rule ("[arm-clustering] adds no
  caller class, convergence gate, continuation rule, or dispatch path... without
  separately scoped work") — not an ad hoc `direct` patch to
  `convergence_diagnosis.py`.
- **Origin:** 2026-08-12, mid-audit on `batch-authoring-observability`,
  discussing why `--audit-passes 1` and `arm-clustering` are currently
  mutually exclusive.
- **Status:** not started.

**#265 — `split` (and similar detail-authoring commands) should default to `--no-detail` when the target plan is bare**

- **What:** `plan-tool split --step N --into ... --into ...` defaults
  `--iterate` ON, which fully authors detail-grade content for the new
  sub-steps and quality-converges it — even when the source plan is bare (0 of
  N steps detailed). The rule should be exactly this simple: **if there is no
  detail file, don't create one.** A structural operation like `split`
  shouldn't silently make a bare plan partially-detailed as a side effect —
  that changes which completeness-audit gate (bare vs. detail-grounded) the
  plan is judged under going forward, without the operator choosing it.
- **Concrete instance:** `batch-authoring-observability` was a fully bare
  9-step plan; `plan-tool split --step 2 --into ... --into ...` (no
  `--no-detail` passed) triggered ~15+ minutes of detail authoring plus a
  3-round quality-convergence loop per new half, before any completeness-audit
  tail — none of which was needed for a plan whose other 8 steps are still
  bare.
- **Fix sketch:** when the source plan/target step is bare, default the
  detail-authoring behavior to off (equivalent to `--no-detail`) unless the
  operator explicitly opts in (e.g. `--detail`). Likely touches the same
  commands' shared authoring-default logic (`split`, and check whether
  `merge`/other structural verbs share the pattern) — reuse whatever bare-plan
  detection `completeness-audit`'s bare-plan gate already has rather than
  reimplementing it.
- **Effort:** small-medium — needs the bare-plan/bare-step detection wired into
  the default-resolution for `--iterate`/`--no-detail`, plus tests and a
  CLI-reference regen (`python -m plan_tool.cli_reference --write`).
- **Approach:** `direct`.
- **Origin:** 2026-08-12, mid-session on `batch-authoring-observability`, after
  `split` ran its full detail-authoring default against a bare plan.
- **Status:** not started.

**#266 — `roadmap --view` should page its output through the user's pager, like `git log` does**

- **What:** `plan-tool roadmap <slug> --view {walk,ledger,index,summary}`
  builds its entire projection as one string (`roadmap_view.py`'s
  `render_traceability_walk` / `render_decision_ledger` / `render_reverse_index`)
  and `roadmap_cmd.py` prints it in a single `print(...)` call — no pager, no
  chunking. `--view walk` is the sharpest case: it renders *every* plan out
  to its full component/entity/constraint/business-rule tree, unbounded by
  roadmap size. On a roadmap with more than a handful of plans this routinely
  exceeds the terminal scrollback buffer, so the earliest plans are simply
  gone by the time the command finishes.
- **Fix:** pipe the existing full-text render through the user's configured
  pager at an interactive TTY, the same way `git log`/`git diff` already do —
  not custom per-concept chunking logic. Keep the existing full-text render
  functions exactly as they are (they stay the data source for `--json`/
  piping/tests); wrap the print call in a pager subprocess (`$PAGER`/`less`
  fallback) when stdout is a TTY, matching how `color_enabled` already gates
  ANSI. Non-TTY / piped / `--json` output stays a single unpaged write.
- **Effort:** small — a pager-wrapping helper around the existing print call,
  TTY detection, tests (non-TTY/`--json` stays byte-identical; a TTY run
  invokes the pager).
- **Approach:** `direct`.
- **Scope contract:**
  - **Outcome:** interactively running `plan-tool roadmap <slug> --view walk`
    (and `ledger`/`index`) on a large roadmap lets the operator page through
    the output using their normal pager instead of losing it to scrollback.
  - **In scope:** `plan_tool/cli/roadmap_cmd.py`'s `--view` print call, a
    small pager-invocation helper, tests.
  - **Out of scope / Non-goals:** changing what any view renders or how it's
    worded; custom per-concept/per-decision-group chunking; touching `--view
    summary` (already bounded via `_SUMMARY_ATTENTION_LIMIT`);
    `--json`/non-TTY output shape; any other `plan-tool` subcommand's output.
  - **Allowed behavior changes:** interactive `--view` runs page through the
    user's pager by default; add an explicit opt-out (e.g. `--no-pager`) for
    an operator who wants the old single-blob behavior at a TTY.
  - **Allowed reorganization:** none.
  - **Verification:** a fake-TTY run invokes the pager wrapper with the
    existing render's full text; a non-TTY or `--json` run is byte-identical
    to today's output.
  - **Stop / defer:** paging any other `plan-tool` command's output is a
    separate entry if ever wanted.
- **Origin:** 2026-08-12, operator note that `roadmap --view` output can
  exceed the console scrollback buffer before it can be read. Re-scoped
  2026-08-27 from custom per-concept chunking to a standard pager wrap —
  smaller surface, same result, no bespoke chunking logic to maintain.
- **Status:** not started.

**#267 — `seed-state.json`'s load-modify-write cycle has no cross-process locking**

- **What:** `plan_tool/roadmap_seed_state.py`'s `load_seed_state`/
  `write_seed_state` read the whole sidecar, let a caller mutate it, and write
  it back with no lock. Every entry point that touches an individual plan's
  entry — `--refresh-seeds`, `--apply`, and (once
  `roadmap-seed-materialization` ships) `--materialize` and `--accept-seed` —
  goes through this same unlocked cycle. Two concurrent operator-run
  processes touching the same roadmap's sidecar (even for different plan
  ids) silently drop whichever wrote first, with no warning either side
  could act on.
- **Why now:** `roadmap-seed-materialization`'s completeness audit surfaced
  this while auditing step 2's per-plan write primitive — the plan adds two
  new entry points onto the same unlocked sidecar without making the
  contention worse in kind, only in frequency (more surfaces writing the
  same file). The audit tagged it `[out-of-scope-deferred]`: pre-existing,
  general-purpose CLI file safety, not something this plan's own scope
  (per-plan seed materialization) should absorb.
- **Fix sketch:** the codebase already has a process-global lock pattern for
  concurrent-CLI-invocation safety (the rate-limit prompt lock named in
  `CLAUDE.md`'s Architecture section) — evaluate reusing that shape for a
  per-roadmap-directory lock around `load_seed_state`/`write_seed_state`'s
  combined cycle, rather than inventing a new locking primitive. A minimum
  viable fix: an advisory file lock (`fcntl`/`msvcrt`-appropriate, or a
  lockfile-with-PID-staleness-check like the existing `--force-lock`
  mechanism) held for the duration of one load-modify-write cycle.
- **Effort:** small-medium — one shared lock helper, wiring it into every
  `load_seed_state`/`write_seed_state` call site, plus a concurrency test
  (two processes/threads racing a write, one wins cleanly, neither drops the
  other's unrelated-plan-id entry).
- **Approach:** `direct`.
- **Origin:** 2026-08-13, `roadmap-seed-materialization` completeness audit,
  finding `seed-state-concurrent-cli-race`.
- **Status:** not started.

**#291 — Seed materialization states the greenfield case explicitly instead of asking the model to match code that doesn't exist**

- **What:** `prompts/roadmap-seed.md` instructs the backend to "inspect the
  **current repository**" and make the seed's implementation-facing language
  "match the code that exists now." The four stage prompts deliberately never
  read the repository, so this prompt is the roadmap arc's only repo-aware
  surface — and it has no posture for a repository with no code yet.
  `_render_seed_materialize_prompt` (`plan_tool/roadmap.py:2263`) interpolates
  only `slug`, `plan_id`, and the four artifact texts; nothing tells the model
  the tree is empty, so on a greenfield run the model is left to infer
  structure from a README or invent plausible file paths, and the seed carries
  those inventions into `create`.
- **Fix sketch:** detect the greenfield state deterministically at
  materialization time and render an explicit repo-posture line into the
  prompt via a new template variable — greenfield: "this repository has no
  code yet: name no existing files or modules; describe what the plan
  creates"; otherwise an equally explicit "existing code — match it" line, so
  both arms are stated rather than one being an absent variable. The one
  design decision is the detection predicate; a candidate: zero tracked files
  outside the roadmap's own artifact directory and top-level docs. Define it
  once and test both sides.
- **Effort:** small — one detection helper, one template variable plus prompt
  edit, tests for both arms of the predicate and the rendered prompt.
- **Risks:** low — prompt-only behavior change; the predicate's definition of
  "no code" is the only judgment call, and a wrong call degrades to today's
  behavior (the model inspects the repo and decides for itself).
- **Dependencies:** none.
- **Scope contract:**
  - **Outcome:** a seed materialized in a repository with no code receives an
    explicit greenfield statement in its prompt and is no longer asked to
    match nonexistent code.
  - **In scope:** `plan_tool/roadmap.py` (`_render_seed_materialize_prompt`
    and its callers' variable supply), `plan_tool/prompts/roadmap-seed.md`,
    `tests/test_roadmap.py`.
  - **Out of scope / Non-goals:** the four stage prompts (repo-blind by
    design — do not add repo state to them); any check of the produced seed's
    file references; #271's stage-4 ordering guidance; #272's docs.
  - **Allowed behavior changes:** the rendered seed prompt gains exactly one
    repo-posture line in each arm; no other output changes.
  - **Allowed reorganization:** none.
  - **Verification:** unit tests assert the predicate on empty and populated
    fixture trees and that the rendered prompt carries exactly one of the two
    posture lines, matching the tree state.
  - **Stop / defer:** any richer repo summary in the prompt (file listings,
    language detection) is a separate entry.
- **Approach:** `direct` — a predicate and a template variable, no design
  fork.
- **Quality:** grounding — greenfield seeds stop carrying invented file
  references into `create`.
- **Origin:** 2026-08-13, greenfield-scenario review of the roadmap verb.
- **Status:** not started.

**#271 — Stage 4 steers a greenfield roadmap's first plan toward the runnable substrate**

- **What:** `prompts/roadmap-plans.md` enforces ordering mechanics — every
  plan id exactly once in `ordering`, every dependency earlier in the
  sequence — but says nothing about what the first plan must establish when
  the concept brief describes a project with no existing code. A greenfield
  roadmap whose first plan presumes a repo, toolchain, or test harness yields
  derived plans that cannot execute in sequence: every derived plan runs
  under `enforce_step_tests`, which presumes a harness exists to author tests
  into.
- **Fix sketch:** delivered guidance, not a gate — add stage-4 prompt
  language: when the brief describes a project with no existing code, the
  first `ordering` entry establishes the runnable skeleton (repo scaffold,
  toolchain, test harness) that later plans' verification presumes. Per
  CLAUDE.md § "Validating a semantic property you cannot observe," whether a
  plan row "counts as" bootstrap is not machine-checkable, so this ships as
  prompt content only.
- **Effort:** small — a stage-4 prompt edit plus a prompt-content test.
- **Risks:** minimal — no gate, no schema, no parser change.
- **Dependencies:** none.
- **Scope contract:**
  - **Outcome:** a roadmap generated from a no-existing-code brief orders a
    substrate-establishing plan first.
  - **In scope:** `plan_tool/prompts/roadmap-plans.md`, its prompt-content
    test.
  - **Out of scope / Non-goals:** any new `PLANS_GATES` check or semantic
  judgment of plan rows; changes to `ROADMAP_FORMAT.md`'s schema; #291's
    seed prompt; #272's docs.
  - **Allowed behavior changes:** stage-4 prompt wording only.
  - **Allowed reorganization:** none.
  - **Verification:** the prompt-content test pins the new directive; a
    fixture-brief stage-4 run is not required (the property is delivered, not
    checked).
  - **Stop / defer:** a deterministic first-plan-substrate advisory, if ever
    wanted, is a separate entry that must first answer the semantic-property
    objection.
- **Approach:** `direct` — one prompt edit.
- **Quality:** grounding — greenfield roadmaps order plans that are
  executable in sequence from an empty repository.
- **Origin:** 2026-08-13, greenfield-scenario review of the roadmap verb.
- **Status:** not started.

**#272 — Document the greenfield roadmap path: the USE_CASES carve-out and the execute → refresh → create cadence**

- **What:** two doc gaps that together argue against a designed use. First,
  `USE_CASES.md`'s "When not to use it" says "No repo to ground against …
  greenfield-with-no-code gets little benefit" with no carve-out — yet all
  four roadmap stage prompts work from the concept brief alone ("Do not read
  the repository"), making `roadmap` precisely the greenfield entry point.
  Second, no doc states the greenfield cadence: stage 4 materializes every
  draft seed eagerly, so later plans' seeds are grounded in a repository that
  does not yet contain their predecessors' output; the re-grounding machinery
  ships (`--refresh-seeds`, `--materialize PLAN_ID`, seed staleness) but the
  loop — execute the first plan, refresh or re-materialize the next seed,
  `create` the next plan — lives in no document.
- **Fix sketch:** carve the exception into the USE_CASES bullet (roadmap
  stages read only the brief; grounding value accrues as the repository
  grows) and add a greenfield section to `docs/ROADMAP_WALKTHROUGH.md`
  stating the cadence.
- **Effort:** small — two doc edits, no code.
- **Risks:** none beyond ordinary doc drift.
- **Dependencies:** none — the cadence documents machinery that already
  ships.
- **Scope contract:**
  - **Outcome:** a reader planning a greenfield project finds an explicit
    statement that `roadmap` is the intended entry point and a stated
    execute → refresh → create loop.
  - **In scope:** `USE_CASES.md` (§ "When not to use it" and § 11),
    `docs/ROADMAP_WALKTHROUGH.md`.
  - **Out of scope / Non-goals:** prompt or code changes (#291, #271); any
    change to what `--refresh-seeds` / `--materialize` do.
  - **Allowed behavior changes:** none — docs only.
  - **Allowed reorganization:** none.
  - **Verification:** the USE_CASES bullet names the roadmap exception; the
    walkthrough section names the cadence commands in order.
  - **Stop / defer:** a stage-4 stdout `Next steps:` nudge printing the
    cadence (plan-tool commands only, per the printed-suggestions rule) is a
    separate small code entry if wanted.
- **Approach:** `direct` — doc edits with no plausible design fork.
- **Origin:** 2026-08-13, greenfield-scenario review of the roadmap verb.
- **Status:** not started.

**#313 — Long-running `plan-tool` processes can silently act on stale in-process rules across a live source edit — audit exposure and design a general guard**

- **What:** nearly every `plan-tool` surface (`run`, `detail --commit`,
  `completeness-audit --iterate`, a multi-stage `roadmap` session) is
  designed to execute for an extended period, and on an editable-install
  development machine that source can be edited while such a process is
  still running. A module-level constant, schema version, gate threshold, or
  feature flag is bound into memory once, at import time; if the on-disk
  source changes while a process is already running, Python does not
  re-import the already-loaded module, so that process keeps acting on
  whatever it imported for the rest of its life — with no detection,
  fingerprinting, or warning anywhere in the codebase today. The archive-safe,
  Integration-local version-1 incident is unverified stale-process provenance rather
  than a confirmed instance: fresh current code cannot write version-1
  evidence. This item starts only if fresh-process reproduction, another
  project, or supported-route provenance supplies a concrete unsafe instance.
- **Effort:** medium for the audit; unknown for any resulting fix until the
  audit names real instances. Explicitly decision-first — see Stop/defer.
- **Risks / fallout:** the inverse failure mode matters here too. "Is this
  process stale relative to disk" is checkable in principle (compare a
  source fingerprint captured at start against a fresh one), but "does that
  staleness matter at this call site" is not something a generic detector
  can judge — the same trap this file's "Validating a semantic property you
  cannot observe" section describes. Scope the audit to naming real,
  evidenced instances before designing any mechanism, or this becomes
  another unfalsifiable "vetting" surface.
- **Dependencies:** do not start from the closed Integration-local incident. A fresh
  reproduction, another project, or supported-route provenance must supply
  the concrete data point this audit needs.
- **Outcome:** a named, evidence-backed list of the `plan-tool` surfaces
  where an in-process value captured at start can diverge from the on-disk
  source during a long-running invocation, each judged as (a)
  impossible/theoretical, (b) possible but harmless, or (c) possible and
  unsafe — and, only for the (c) cases,
  a scoped design for detection or refusal.
- **In scope:** an audit of module-level constants and gate thresholds bound
  at import time across `plan_tool/roadmap_*.py`, `launcher.py` (`run`),
  `detail.py`, `completeness_report.py` / `cli/completeness_phases.py`, and
  any other long-running orchestrator named in `docs/ARCHITECTURE.md` once a
  concrete unsafe instance is available.
- **Out of scope / Non-goals:** a general hot-reload or process-restart
  mechanism; changing the editable-install deployment model itself; a
  generic filesystem-watch daemon; re-litigating the already-shipped
  version-1 evidence-schema retirement.
- **Allowed behavior changes:** none beyond what a scoped (c)-case fix
  requires, decided per instance found.
- **Allowed reorganization:** none until instances are enumerated.
- **Verification:** the audit's own list, reviewed by the user; any shipped
  guard gets a test that starts a process, mutates the relevant on-disk
  constant's analog, and proves the guard fires rather than silently
  proceeding.
- **Stop / defer:** if no concrete unsafe instance arrives, leave this
  decision-first item unstarted rather than building general machinery for a
  class with no confirmed member.
- **Approach:** the audit itself is `direct` (a reading/tracing pass, no
  design choice); any resulting (c)-case fix is `plan-tool` if it touches
  more than one module.
- **Origin:** 2026-08-26, raised by the user after tracing the roadmap
  evidence-schema incident to a plausible long-running-process cause, with
  the observation that this is a structural exposure class — "almost all
  processes of the tool are long running" — not a one-off worth a narrow fix
  alone.

**#315 — Delivered 2026-08-27: confirmed feedback reopen proof**

> **Historical record.**
> [`docs/implementation-plans/archive/2-roadmap-confirmed-feedback-reopen.md`](docs/implementation-plans/archive/2-roadmap-confirmed-feedback-reopen.md)
> delivers one explicitly confirmed operator path for a safe selected
> `awaiting-review` row. The redacted transition returns that row to `open`
> and gives its next receipt a fresh identity; confirmation is the authority
> for the unavailable-evidence determination.

- **Scope boundary:** This proof neither classifies nor recovers evidence,
  retains response history, permits ordinary feedback reopening, or reissues a
  historic Integration receipt. It remains a bounded input to #242's later retention
  redesign, not a solution to that work.

**#314 — Establish whether advisory risk-profile context needs a declaration-authority or escalation guardrail**

- **What:** assess the completed advisory risk-profile context against a
  bounded set of explicit-declaration detail runs before proposing any further
  behavior. The assessment will distinguish a proportionate result, a mismatch
  ordinary review corrects, and a concrete invariant the advisory boundary
  leaves unprotected; it will separately settle whether an automated detail
  rewrite may change a risk declaration or only explain the proposed change.
- **Effort:** small for the decision record and evidence review; implementation
  effort is deliberately unknown until a specific failed property is found.
- **Risks / fallout:** a hand-picked example could overstate the need for
  enforcement, while a broad telemetry or policy system would create a new
  cross-pipeline authority surface without proving it helps. The evidence set
  therefore remains bounded and source-linked.
- **Dependencies:** **#181** supplies the persisted declaration; **#182**
  supplies the completed advisory authoring context.
- **Outcome:** one dated record, linked from
  `plan-seeds/risk-profile-3-advisory-effectiveness.md`, classifies each
  reviewed case and records a user-selected disposition: retain advisory
  context, investigate a human-confirmation boundary, or investigate one
  evidence-backed escalation. No implementation behavior changes in this
  item.
- **In scope:** the completed risk-profile detail artifacts and their saved
  reports, explicit-declaration detail runs, the detail-loop declaration-edit
  path, authoring/audit cache-isolation evidence, and
  `plan-seeds/risk-profile-3-advisory-effectiveness.md` with its dated design
  reference.
- **Out of scope / Non-goals:** a ceremony taxonomy, policy module, audit
  suppression, custom finding grammar, generic automatic-edit refusal, broad
  telemetry, or an implementation plan selected before the evidence identifies
  a failed property.
- **Allowed behavior changes:** none.
- **Allowed reorganization:** none.
- **Verification:** every reviewed case cites its plan/detail artifacts and
  source locations; the record distinguishes grounding and safety obligations
  from procedural preference; and the selected disposition names either no
  code change or one bounded next question.
- **Stop / defer:** no observed material failure closes the item with advisory
  context retained. A discovered concern outside declaration authority,
  targeted escalation, or authoring/audit isolation becomes its own backlog or
  bug entry.
- **Approach:** `direct` — this is evidence collection and a user decision,
  not a committed implementation surface.
- **Quality:** `grounding`, `gate-signal` — turns a broad concern about risk
  honoring into a source-backed question without weakening ordinary safety or
  correctness work.
- **Status:** design notes only at
  `plan-seeds/risk-profile-3-advisory-effectiveness.md`; the dated independent
  reference is
  `plan-seeds/archive/risk-profile-escalation-options.20260826.md`.

**#317 — Pause-and-poll for restored connectivity instead of exhausting the transient retry budget**

- **What:** a real network outage (WiFi drop, laptop sleep/wake, VPN
  reconnect) is indistinguishable today from an ordinary blip in both shapes a
  backend call can fail in, and both under-serve it. Fast:
  `rate_limit_loop.run_with_rate_limit_recovery`'s `TRANSIENT` arm
  (`ECONNRESET`, `network error`, `timeout`, `connection reset`, matched by
  `backend._CLAUDE_TRANSIENT_PATTERN`) gets only
  `DEFAULT_MAX_TRANSIENT_RETRIES=2` attempts at
  `DEFAULT_TRANSIENT_BASE_DELAY=2.0`s exponential backoff (`shell.py:156-157`)
  before `TERMINAL`, halting `run_step()`'s blocking claude-call gate
  (`docs/RUN_FLOW.md` step [6]) within ~6 seconds with no automatic resume.
  Long-running: a call already deep into real work whose connection dies
  silently blocks; `backend_runner.py`'s heartbeat kills it after 900s
  (`_KILL_AFTER_SILENCE_S`), recording `TerminationReason.SILENCE_TIMEOUT` and
  classifying `ClaudeFailureKind.TIMEOUT` — deliberately terminal, never
  retried (`claude_errors.py:98-100`, `:576-580`). Add a real, injectable
  connectivity probe so a call in either shape, with local connectivity
  *confirmed* down, pauses and polls, resubmitting only once a fresh probe
  confirms it is actually back — never on a blind fixed delay — instead of
  burning a fixed budget or surfacing terminal within seconds.
- **Effort:** medium — a new probe/poll-wait seam pair (default implementation
  in `claude_errors.py`, mirroring `make_backend_recovery_wait_seam` /
  `make_backend_recovery_sleep_seam`), a widened retry-candidate computation in
  the stdlib-only leaf (`rate_limit_loop.py`) that must still route through the
  existing partial-mutation `retry_guard`
  (`git_state.make_partial_mutation_retry_guard`) before polling, a
  poll-eligibility rule keyed on the existing `get_last_termination_reason()`
  to admit a `SILENCE_TIMEOUT` kill while permanently excluding a caller's own
  `CONFIGURED_TIMEOUT`, a new budget-independent opt-out (mirroring the
  existing `recover_rate_limit` toggle) so `roadmap_revision_run.py`'s
  explicitly no-recovery `shell_local_revision_invoker` doesn't silently gain
  recovery it disclaims, a new `backend_recovery_wait` `reason="connectivity"`
  value, and tests for both callers (`shell.claude_invoke`,
  `launcher.shell_invoker`).
- **Risks / fallout:** a captive-portal/proxy false-positive (probe reaches a
  public IP; the actual backend stays unreachable) could poll-succeed into
  another immediate transient failure — the design self-corrects this since
  the ordinary transient-attempt count is never advanced while polling, so the
  bounded-backoff budget is still fully available on the next attempt. An
  unattended/no-TTY run needs a real ceiling (mirroring
  `MAX_RATE_LIMIT_WAIT_SECONDS`'s existing 86400s cap) or a permanently broken
  network spins forever with no operator watching to abort it.
  `SILENCE_TIMEOUT` and `CONFIGURED_TIMEOUT` currently produce the identical
  `ClaudeFailureKind.TIMEOUT` and `BACKEND_TIMEOUT_SENTINEL` text, so getting
  the exclusion wrong would either make a caller's explicit elapsed-time
  ceiling connectivity-contingent or leave the motivating long-running-call
  case unrecovered — mitigated by keying exclusively off
  `get_last_termination_reason()`'s enum value, never stderr text. Any new
  test that doesn't stub the probe risks a real socket call and
  machine-dependent flakiness.
- **Dependencies:** none. Independent of #119/#120 (snapshot-restore-then-retry
  and retry-guard hardening) — those harden *what happens when a retry is
  allowed*; this changes *how long the loop waits before giving up*, and both
  compose through the same `retry_guard` ordering fence.
- **Outcome:** a backend call whose failure is plausibly a local connectivity
  loss — fast `TRANSIENT`, or a `SILENCE_TIMEOUT`-killed long-running call,
  never a `CONFIGURED_TIMEOUT` — pauses and polls (interruptible on a TTY,
  capped on a non-TTY run) and resubmits only once connectivity is confirmed
  back, instead of exhausting a fixed budget or surfacing `TERMINAL` within
  seconds.
- **In scope:** `plan_tool/rate_limit_loop.py` (widened retry-candidate
  computation, new opt-out), `plan_tool/claude_errors.py` (default probe +
  poll-wait, the poll-eligibility rule reading the existing
  `get_last_termination_reason()`), `plan_tool/launcher.py` (wiring, unchanged
  unless a caller needs a non-default override), `plan_tool/shell.py`
  (`claude_invoke`/`claude_invoke_outcome` gain the new opt-out parameter and
  forward it — `run_with_rate_limit_recovery` has only two direct call sites,
  `launcher.py:679` and `shell.py:760`, and `shell_local_revision_invoker`
  reaches the leaf two layers down through `claude_invoke`, which already
  declares and forwards `wait_on_rate_limit`/`max_transient_retries` by name
  with no generic passthrough), `roadmap_revision_run.py:shell_local_revision_invoker`
  (sets the new opt-out), `docs/RUN_FLOW.md`, `DATA_CONTRACT.md` (the
  `backend_recovery_wait.reason` table, `DATA_CONTRACT.md:850`, currently
  documents only `"rate_limit"` / `"transient"`), `RUNBOOK.md`, `TESTING.md`,
  `tests/`. **Not** `plan_tool/backend_runner.py` — it already exposes the
  termination-reason accessor read-only.
- **Out of scope / Non-goals:** any new `ClaudeFailureKind`, `AttemptCategory`,
  or `TerminationReason` member; making a `CONFIGURED_TIMEOUT` kill
  poll-eligible under any condition; making a `SILENCE_TIMEOUT` kill
  poll-eligible when connectivity reads up (stays exactly as terminal as
  today); a new CLI flag (poll interval / non-interactive cap / probe hosts
  stay code-level constants, matching how `max_transient_retries` and
  `_KILL_AFTER_SILENCE_S` are handled today); probing the backend's own API
  host (conflates "my network is down" with "the provider is down," which
  `RATE_LIMIT`/`PLAN_QUOTA`/ordinary `TRANSIENT` already own); any change to
  `backend_runner.py`'s kill ladder or thresholds.
- **Allowed behavior changes:** the new poll-instead-of-terminal path for a
  connectivity-confirmed-down `TRANSIENT` failure and for a
  `SILENCE_TIMEOUT`-killed call; a third `backend_recovery_wait.reason` value
  (`"connectivity"`). No change to ordinary transient-blip behavior with
  connectivity up, a `CONFIGURED_TIMEOUT` kill, a genuinely wedged call with
  connectivity up, `RATE_LIMIT`/`PLAN_QUOTA` handling, or the partial-mutation
  guard's precedence.
- **Allowed reorganization:** none.
- **Verification:** § Testing of the seed below — the ordering fence
  (`retry_guard` still refuses a poll-eligible retry over a dirty tree), the
  `SILENCE_TIMEOUT`/`CONFIGURED_TIMEOUT` exclusion, the self-correcting budget
  property, the non-TTY cap, and that no test exercises a real socket.
- **Stop / defer:** any CLI-flag surface, and probing the backend's own host,
  become their own backlog entries if real operator demand emerges; anything
  the iteration loop surfaces outside this fence goes to `BACKLOG.md` /
  `BUG_BACKLOG.md`, never applied as plan expansion.
- **Approach:** `plan-tool` — a design decision (probe target, ordering fence
  relative to the partial-mutation guard, non-interactive cap), not a
  one-line fix.
- **Iterate:** default recipe (author + converge). Load-bearing: `create`,
  one-shot `detail --commit`, a `completeness-audit --iterate --commit`
  pass, then `run --commit --iterate` per step and the post-run
  `reconcile-code --all` tail.

  ```bash
  plan-tool create connectivity-pause-and-poll --iterate -y --from-existing plan-seeds/connectivity-pause-and-poll.md
  plan-tool detail connectivity-pause-and-poll --commit -y
  plan-tool completeness-audit connectivity-pause-and-poll --iterate --commit -y
  plan-tool run connectivity-pause-and-poll --commit --iterate -y
  ```
- **Status:** plan-seed authored at
  `plan-seeds/connectivity-pause-and-poll.md`; `create` not yet run.
- **Origin:** 2026-08-26, investigation requested into making long-running
  `plan-tool` processes resistant to a lack of connectivity.

**#322 — Migrate remaining human-input and human-availability routes after the vertical proof**

- **What:** evaluate and migrate the remaining prompt and human-availability
  routes through the landed record protocol or a deliberately revised
  successor. `HUMAN_IO_FORMAT.md`, the focused review-walk proof, and the
  completed closed `cmd_review` non-TTY entry establish the narrow starting
  point; they do not select a repository-wide policy.
- **Why:** the remaining routes can have different destructive-confirmation,
  defaulting, or free-text requirements. A fresh inventory must establish
  whether they share a policy before migration groups are selected.
- **In scope:** a fresh inventory of remaining direct-input and
  human-availability paths, each route's behavior and owner, and only the
  migration groups justified by that inventory. The completed `cmd_review`
  entry stays out of scope unless its selected skip-or-quit contract fails.
- **Inventory rule:** before authoring, enumerate sites both by identifier and
  by vocabulary — including direct input, `isatty` aliases, readiness checks,
  and helper gates that decide whether a prompt runs. Record why every match
  migrates or stays. Do not treat the focused review-walk proof as the current
  inventory.
- **Scope fence:** choose remote defaults, advisory delivery, parallel-job
  behavior, and any transport generalization only when a named remaining route
  requires them. A consumer that preserves an existing absent outcome does not
  imply a shared default-policy table.
- **Record lifecycle:** the landed protocol never deletes resolved
  request/resolution record pairs, so a long or retry-prone session
  accumulates them indefinitely with no documented owner. Decide a retention
  or cleanup policy — and who owns it — as part of the shared policy this
  entry selects, rather than assuming the current no-cleanup behavior
  generalizes to every migrated route.
- **Risks / fallout:** a route missed by the fresh inventory can still call
  `builtins.input()` and wait forever in a headless process. Classify every
  direct-input match by its operator consequence before selecting a migration
  group; this entry does not select one now.
- **Dependencies:** the landed protocol, focused remote and terminal tests,
  and the completed bounded `cmd_review` entry establish the accepted starting
  contracts.
- **Approach:** `plan-tool` — create a fresh seed from current code, audit its
  bare plan before detail, and split independent behavior classes if they do
  not share one selected contract.
- **Status:** the current-code inventory is recorded in
  [`analysis/headless-process-route-inventory.md`](docs/implementation-plans/backlog-arcs/analysis/headless-process-route-inventory.md).
  Its standalone saved-review selection is complete as
  [`headless-review-walk-annotation-entry`](docs/implementation-plans/archive/2-headless-review-walk-annotation-entry.md).
  No follow-on route, shared policy, or lifecycle change is selected. Refresh
  the inventory against post-proof code before selecting another route.

**#329 — Validate the exact root-enrollment journal before pre-enrollment recovery**

- **What:** Before `plan_tool/roadmap.py:enroll_roadmap_root()` recovers a
  pending root-enrollment journal, verify that its members are exactly the
  root version record, brief, fixed artifact inventory, and final accepted-head
  selector for one root version. Refuse any other journal without recovery or
  capture.
- **Why deferred:** Normal lifecycle writers do not create a falsely labelled
  `root-enrollment` journal. The shipped #328 happy-path proof already refuses
  actual pending legacy journals before capture; this adds persistence-integrity
  hardening for corrupt or forged journal content.
- **Effort:** small — one narrow generation recognizer, the enrollment
  preflight, and focused recovery fixtures.
- **Risks / fallout:** An over-broad recognizer could prevent a legitimate
  interrupted root enrollment from recovering. Keep unversioned recovery and
  every other generation kind unchanged.
- **Dependencies:** #328 remains the source of the published root-generation
  contract; complete final sign-off on #328 before selecting this work.
- **Scope contract:**
  - **Outcome:** root enrollment recovers only the exact writer-produced root
    generation for one root version.
  - **In scope:** `plan_tool/roadmap_versions.py`,
    `plan_tool/roadmap.py`, and focused root-enrollment recovery tests.
  - **Out of scope / Non-goals:** a general journal-ownership framework,
    changes to unversioned recovery, new recovery commands, or candidate and
    promotion journal changes.
  - **Allowed behavior changes:** a corrupt or falsely labelled pending root
    journal refuses before recovery; normal root-enrollment recovery remains
    available.
  - **Allowed reorganization:** one shared exact-root-generation recognizer
    only if the enrollment preflight and its tests cannot otherwise express
    the fixed member set.
  - **Verification:** fixtures prove a partially applied exact root generation
    recovers, while a root-labelled journal with any legacy member refuses
    before capture and leaves every live artifact and journal byte unchanged.
  - **Stop / defer:** requirements for cross-kind recovery validation,
    broader corruption repair, or operator repair tooling become separate
    backlog items.
- **Approach:** direct — the fixed member inventory and required refusal are
  already selected by #328.
- **Arc assignment:** intentionally unassigned. Another branch is updating
  backlog-arc documentation structure; add this entry to the appropriate arc
  only after #328 final sign-off completes.
- **Origin:** 2026-09-01 post-run reconciliation report
  `20260901-151003-run-reconcile.json`, finding `step4-run-reconcile-cad5fa58`;
  user-confirmed as deferred hardening.
- **Status:** deferred pending #328 final sign-off and subsequent arc assignment.

**#330 — Revalidate a persisted proposal admission before a resumed model call**

- **What:** When `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal()`
  resumes an admission without a stored candidate, reproduce its persisted
  capsule and receipt against the bound predecessor before it renders or sends
  a backend request.
- **Why deferred:** Normal lifecycle writers do not create a canonical-but-
  conflicting admission. The shipped materialization boundary already rejects
  it before candidate storage or accepted-head movement; this hardening avoids
  one unnecessary model invocation on corrupt persisted state.
- **Effort:** small — reuse the existing candidate binding verifier at the
  resumed-admission boundary and add one no-invocation fixture.
- **Risks / fallout:** Reusing the wrong verifier could compile fresh context
  or change the normal one- or two-call budget. The check must consume only
  the stored admission and its bound predecessor.
- **Dependencies:** #328 supplies the admission, capsule, receipt, and
  candidate-binding contracts; complete final sign-off on #328 before selecting
  this work.
- **Scope contract:**
  - **Outcome:** a corrupt persisted admission refuses before the backend call
    and cannot consume the lineage's request budget.
  - **In scope:** `plan_tool/roadmap_candidate_run.py` and
    `tests/test_roadmap_candidate_run.py`.
  - **Out of scope / Non-goals:** admission-schema redesign, repair or rewrite
    of persisted admissions, retry-policy changes, context recompilation, and
    candidate-review or promotion changes.
  - **Allowed behavior changes:** a conflicting stored capsule or receipt
    refuses before invocation; every writer-produced admission retains its
    current bounded request behavior.
  - **Allowed reorganization:** none beyond extracting a local verifier call
    if the existing step-6 binding verifier cannot be invoked directly.
  - **Verification:** a canonical-but-conflicting admission fixture produces a
    refusal with zero invoker calls, while normal initial and expanded
    continuations retain their existing one- and two-call bounds.
  - **Stop / defer:** any need to validate arbitrary persisted lifecycle
    records or repair corrupt storage becomes a separate hardening entry.
- **Approach:** direct — the binding source and the zero-call property are
  already explicit.
- **Arc assignment:** intentionally unassigned. Another branch is updating
  backlog-arc documentation structure; add this entry to the appropriate arc
  only after #328 final sign-off completes.
- **Origin:** 2026-09-01 post-run reconciliation report
  `20260901-152024-run-reconcile.json`, finding `step7-run-reconcile-539f65f0`;
  user-confirmed as deferred hardening.
- **Status:** deferred pending #328 final sign-off and subsequent arc assignment.

**Historical retired conversational impact transaction**

> **Superseded 2026-08-31.** The proposal let a model-authored impact manifest
> become the authority for a candidate transaction. Its audit exposed recurring
> binding, route-admission, snapshot, and redaction contradictions. The WIP plan
> is archived as `2-roadmap-conversational-feedback.superseded.md`; do not author
> or reopen this route. Its pre-merge branch-local `#325` label is historical;
> the immutable accepted-head lifecycle in closed #328 supersedes it.

**Closed #328 — Immutable accepted-head roadmap versions**

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
- **Deferred hardening:** #329 and #330 preserve the two persistence-integrity
  findings that are not required for this representative happy-path proof.
  Both intentionally remain outside a backlog arc until #328 final sign-off
  completes and the other branch's backlog-arc documentation structure lands.
- **Status:** closed 2026-09-01 after the deterministic lifecycle tests and
  the recorded real-backend observation.

**#327 — Intentional seed ingestion with automatic normalization and split routing**

- **Status:** complete 2026-09-03 through
  [`2-seed-ingestion-routing.md`](docs/implementation-plans/archive/2-seed-ingestion-routing.md).
- **Delivered route:** file-backed create selects `seed_body` when present,
  otherwise `from_description`; rejects unmatched fences and unusable
  References before a run record; and then selects `direct`, `normalized`,
  `split`, or `refused`. Direct source authority, one visible preparation
  decision, `SplitProposal`'s successful no-plan shape, route-owned
  checkpoint retention, no-plan branch rollback, and CLI-only clean archival
  ship together.
- **Documentation:**
  [seed-ingestion contract](docs/reference/contracts/seed-ingestion.md)
  owns the route and lifecycle table; the create, resume, CLI, and seed-format
  pages link to or summarize that shipped contract.
- **Related:** #102 remains independent semantic alias-matching work. It does
  not reopen this route's canonical-title normalization, source-authority,
  split, or lifecycle decisions.

**#353 — Durable artifact-contention handoff for terminal and headless operators**

- **What:** when a normalized-artifact destination becomes occupied again
  after one bounded recovery and publication retry, preserve both sides and
  expose a durable decision instead of treating the event as an ordinary
  archive failure. A terminal operator can respond to the warning; a headless
  orchestrator such as Integration can surface the same decision to a person and
  resume it later.
- **Design caution:** a path collision proves only that the destination
  changed or reappeared during the publication window. It does not prove who
  wrote it, whether that writer is still active, or whether it is another
  `plan-tool` process. The feature reports observable contention and asks for
  a choice; it never claims to identify or lock out a competing writer.
- **Effort:** medium-to-large — this adds a persisted conflict/pending-payload
  lifecycle, a typed waiting outcome, an idempotent resolution path, terminal
  presentation, and a headless contract across CLI, storage, tests, and docs.
- **Risks / fallout:** a careless resolver can overwrite a person's edit,
  expose generated source through an over-broad receipt, strand pending
  payloads, or apply a stale choice after the destination changes again.
  Resolution must revalidate the contested path and fail closed on new drift.
- **Dependencies:** the current narrow `_archive_normalized_artifact`
  correction must first stabilize its boundary: recover an observed
  pre-existing collision, retry publication once, and leave a reappearing
  destination untouched. `HUMAN_IO_FORMAT.md` and #322 provide the existing
  headless request/resolution proof, but this item must explicitly decide
  whether that record shape can carry artifact contention rather than assume
  it generalizes.
- **Scope contract:**
  - **Outcome:** after post-recovery contention, the competing destination,
    newly generated normalized payload, and raw source remain recoverable,
    while one durable typed decision can be completed from a terminal or a
    headless orchestrator and resumed idempotently.
  - **In scope:** `plan_tool/cli/authoring.py`'s normalized-artifact publication
    boundary; the plan-tool-owned pending-payload and conflict-record format;
    a typed CLI/result outcome; an explicit resolve/resume surface; terminal
    warning/choice presentation; headless request/resolution integration where
    the selected design proves it fits; focused lifecycle, race, and restart
    tests; and the owning format/flow documentation.
  - **Out of scope / Non-goals:** generic filesystem locking; detecting writer
    identity or liveness; preventing manual edits; silently deleting,
    overwriting, or archiving unknown competing content; a repository-wide
    conflict framework; Integration UI, transport, worker, or notification code; and
    any expansion of #327's seed-selection, preparation, split, or ordinary
    archival contract.
  - **Allowed behavior changes:** only a destination that reappears after the
    bounded recovery/retry enters the durable waiting outcome. Ordinary clean
    publication and recoverable pre-existing collisions retain their current
    behavior. An explicit resolution may retry after external cleanup, keep
    the competing destination and pending payload, or preserve-and-replace the
    destination; no choice destroys either side silently.
  - **Allowed reorganization:** none unless the existing CLI/result boundary
    cannot persist and resume the selected decision safely. Any extraction is
    limited to one owner for the contention record and its state transition.
  - **Verification:** inject both file and symlink collisions before recovery,
    after recovery, and during resolution; assert byte-for-byte preservation
    of the raw source, competing destination, and pending generated payload;
    prove non-TTY execution returns without blocking; prove terminal and
    record-driven choices share the same transition; replay each choice; and
    reject a stale choice when the destination has changed again.
  - **Stop / defer:** broader collision classes, generalized multi-writer
    coordination, cleanup/retention beyond this record's named owner, and Integration
    product implementation become separate entries. A collision signal that
    cannot safely support one of the proposed choices narrows the choice set;
    it does not authorize a lock manager or overwrite policy.
- **Approach:** `plan-tool` — persistence, restart semantics, human authority,
  and race revalidation form a multi-surface state-machine contract rather
  than a bounded direct fix.
- **Iterate:** when selected, first author
  `plan-seeds/artifact-contention-handoff.md` from this scope contract. Then
  use the default author/detail/audit/run and post-run reconciliation loop;
  the bare-plan audit is load-bearing for the human-authority and stale-choice
  rules, and the detail-grounded audit is load-bearing for persistence and
  idempotence.

  ```bash
  plan-tool create artifact-contention-handoff --iterate -y --from-existing plan-seeds/artifact-contention-handoff.md
  plan-tool detail artifact-contention-handoff --commit -y
  plan-tool completeness-audit artifact-contention-handoff --iterate --commit -y
  plan-tool run artifact-contention-handoff --commit --iterate -y
  plan-tool reconcile-code artifact-contention-handoff --all
  ```
- **Arc assignment:**
  [`backlog-arc-headless-process.md`](docs/implementation-plans/backlog-arcs/backlog-arc-headless-process.md),
  with Integration recorded only as an intended headless consumer.
- **Origin:** 2026-09-04 user-confirmed scope carve during the external
  `seed-ingestion-routing` review, after recurring collision findings showed
  that durable human coordination is useful but exceeds the narrow correction.
- **Status:** not started; parked until the narrow collision correction reaches
  external review convergence and the user explicitly selects this item.

---

**#405 — Suggest focused roadmap feedback subsets after a failed revision**

- **What:** add a read-only diagnostic for a failed `plan-tool roadmap`
  feedback revision. It analyzes the active feedback rows and suggests a small,
  ordered set of coherent subsets that can be processed through the existing
  full revision, approval, commit, and enrollment lifecycle one at a time.
- **Why:** Integration's first full-MVP revision attempted 23 related requests at once
  and produced responses without material structural changes. The recovery was
  to retain the 23-row ledger, expose only one focused cross-artifact concern
  in the working artifacts, and rerun the normal revision lifecycle.
- **Effort:** medium. The diagnostic needs failure evidence, relation-aware
  grouping, dependency ordering, and an operator-readable report, but no writer
  or new roadmap lifecycle.
- **Risks:** suggestions must not imply that semantic completeness is proven;
  grouping by artifact alone can split one concern across stages, while overly
  broad groups can recreate the original failure.
- **Dependencies:** reuse current roadmap parsing, feedback metadata, reverse
  references, and failed-run evidence. It must not depend on or extend writer,
  accepted-head, candidate, structural-rewrite, or seed authority.
- **Outcome:** after a failed broad revision, an operator receives a justified
  breakdown of every active feedback row into ordered, cross-artifact subsets,
  with no row omitted or duplicated and with dependencies called out.
- **In scope:** classify whether the failed attempt is plausibly a
  breadth/heterogeneity failure rather than a transport, parse, response-
  protocol, gate, source-admission, or writer failure; read-only detection of a
  likely breadth/heterogeneity failure;
  suggested subset membership; reasons for each assignment; dependency order;
  coverage accounting over all active rows; and a handoff/checklist suitable
  for manually exposing one subset before rerunning `roadmap`.
- **Out of scope / Non-goals:** modifying artifacts or feedback state; applying
  revisions; creating a group manifest; atomic publication; automatic approval;
  inferred acceptance; concurrent revision management; or a general roadmap
  editor.
- **Allowed behavior changes:** one optional read-only diagnostic/report path;
  every existing roadmap writer and approval command remains unchanged.
- **Allowed reorganization:** none unless a current read-only relation owner
  prevents complete row accounting.
- **Verification:** use a 23-row four-artifact fixture plus focused parse- and
  gate-failure fixtures; prove non-breadth failures receive no breakdown
  suggestion, every grouped row appears
  exactly once, concern-spanning rows stay together, dependencies are ordered,
  the report performs no writes or logging mutations beyond ordinary diagnostic
  telemetry, and ambiguous evidence is reported instead of guessed.
- **Stop / defer:** stop at suggestions. Any request to edit feedback, execute a
  subset, approve a revision, or publish artifacts belongs to the existing
  roadmap lifecycle or a separate backlog item.
- **Approach:** `plan-tool` — the grouping judgment and failure classification
  need an explicit design and grounded examples before implementation.
- **Quality:** `gate-signal` — makes an over-broad revision failure actionable
  without weakening existing publication authority.
- **Origin:** 2026-09-21, Integration full-MVP roadmap review.
- **Status:** not started; use the Integration 23-row failure as the first design
  fixture.

**Closed #423 — Route structural roadmap feedback through one revision approval gate**

- **Outcome:** ordinary ledger feedback now validates typed operations into a
  bounded or structural inert candidate without user route selection. A
  structural candidate receives one exact approve/edit/reject decision;
  approval seals that candidate and promotion alone advances the accepted head.
  Edit requires a fresh decision, and failed, rejected, interrupted, and stale
  proposals preserve canonical artifacts and seeds.
- **Boundary:** structural escalation, decision settlement, impact analysis,
  and exact-pair structural rewrite remain separate selector-shaped routes.
  Workflow authoring, automatic approval, grouping, and multi-user approval
  remain out of scope.
- **Provenance:** opened 2026-09-21 from Integration focused-feedback retries; closed
  2026-09-23 by the Roadmap Structural Feedback Approval plan.

**#424 — Record and surface create-time plan-altitude re-cut evidence**

- **What:** preserve a create-time decision record whenever a session replaces
  a plan's central lifecycle framing without splitting or merging its steps,
  and surface that record to the next plan author or audit reader.
- **Why:** On 2026-09-22,
  `roadmap-versioned-feedback-revision-chain` was re-cut from one permanently
  selected feedback lineage to accepted-head-scoped batch admission after its
  bare audit exposed that the first contract could never support a second
  ordinary revision. Telemetry contained only two duplicate completeness-stage
  granularity assessments (`split=0`, `merge=0`) and no create-time,
  plan-altitude measurement. The detector therefore supplied no evidence about
  the design choice that changed.
- **Effort:** medium. The work needs a narrow lifecycle-decision fact, a
  create/audit handoff surface, and fixtures that distinguish a plan-altitude
  re-cut from ordinary step granularity.
- **Risks:** a vague "plan changed" record becomes another unreviewed activity
  log; surfacing it as an automatic split recommendation would confuse a
  replacement of one contract with a decomposition into multiple plans.
- **Dependencies:** current `plan-tool telemetry` granularity records and the
  create/audit report persistence path. It is independent of #423's roadmap
  lifecycle implementation.
- **Outcome:** a plan whose core framing is replaced records whether create
  produced a plan-altitude assessment and gives the next author enough bounded
  evidence to distinguish a missed re-cut from a step split or merge.
- **In scope:** a typed record for the create-time assessment or its absence;
  a narrow session-directed re-cut record; report rendering; and focused
  fixtures for the 2026-09-22 batch-feedback case.
- **Out of scope / Non-goals:** deciding whether a plan belongs at runtime;
  automatic seed or plan rewrites; changing step-level granularity heuristics;
  a general decision ledger; or roadmap feedback implementation.
- **Allowed behavior changes:** create/audit telemetry and rendered reports may
  show the bounded re-cut evidence. No plan is split, merged, or rewritten
  automatically.
- **Allowed reorganization:** reuse the existing telemetry and report writers;
  extract at most one owner for the typed re-cut record if an existing owner
  cannot preserve its provenance.
- **Verification:** fixtures prove a normal create records its plan-altitude
  assessment, an externally identified re-cut records an absent or contrary
  assessment with the cited reason, and step-only `split=0` records do not
  satisfy the create-time evidence requirement.
- **Stop / defer:** defer automatic remediation, new convergence exits, or a
  generalized planning-history system to separate entries.
- **Approach:** `plan-tool` — telemetry shape, create-time ownership, report
  consumption, and false-signal handling need one scoped design.
- **Quality:** `heuristic-tuning` — makes plan-decomposition evidence reflect
  the altitude at which the design actually changed.
- **Status:** not started; detector-miss record required by
  `integrations/shared/DIRECTIVES.md` after the 2026-09-22 re-cut.

**#428 — A ledger proposal's current-or-stale status is defined but never computed**

- **What:** `roadmap-versioned-feedback-revision-chain` defines a stored
  ledger proposal as *current* only while its bound candidate revision is one
  member of the current processing pair (the accepted root or the active
  candidate), and *stale* once supersession, rejection, discard, or an
  accepted-head change leaves it outside that pair
  (`docs/implementation-plans/2-roadmap-versioned-feedback-revision-chain.md`,
  `ROADMAP_FEEDBACK_FORMAT.md`). Every proposal now records the candidate that
  produced it (`ProposalFields.candidate_version_id`), but nothing compares
  that id with the current root and active pointer, so no surface says whether
  an `awaiting-review` item's proposal is current.
- **Why:** a reviewer reading the ledger cannot tell a reviewable proposal
  from one whose candidate was rejected, discarded, or replaced without
  re-deriving the processing pair by hand.
- **Effort:** small–medium — one deterministic read-only classifier and the
  one existing listing that renders it.
- **Risks / fallout:** the label must stay derived and advisory. Writing it
  into the reviewer-editable ledger form would turn derived state into mutable
  input, and a model call, a gate, or an exit-code flip would all exceed the
  outcome.
- **Dependencies:** `roadmap-versioned-feedback-revision-chain` closed (it
  introduces the binding field and the pointer).
- **Outcome:** each ledger item with a stored proposal reports `current`,
  `stale`, or `unbound` from its `candidate_version_id` and the current
  root/active pair, in the existing feedback listing.
- **In scope:** one classifier beside `plan_tool/roadmap_feedback_ledger.py`
  or `plan_tool/roadmap_feedback_ledger_run.py`; one rendering site in the
  existing feedback listing.
- **Out of scope / Non-goals:** automatically reopening, retargeting, or
  closing a stale item; a new lifecycle state; changing eligibility; target
  staleness (`target_fingerprint` already covers it); writing the label into
  the ledger. A proposal migrated from legacy feedback records no producing
  candidate and reports `unbound`, deliberately not `stale`.
- **Allowed behavior changes:** a `current`/`stale`/`unbound` label appears
  where proposals are listed.
- **Allowed reorganization:** none.
- **Verification:** classifier tests for a proposal bound to the active
  candidate (`current`), to a superseded, rejected, or discarded candidate
  (`stale`), to a promoted version that is now the root (`current`), to an
  older root after the head moved (`stale`), and with no producing candidate
  (`unbound`).
- **Stop / defer:** an unclear promoted-version case is settled by the plan's
  definition above; anything wider becomes a separate entry.
- **Approach:** `direct` — one pure function and one rendering site.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `standard` — a
  read-only derived label with no persisted state.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Renumbered:** filed as #425 on this branch on 2026-09-23 and cited that way in its commit history; renumbered to #428 on merging `main`, which had already allocated #425.
- **Origin:** 2026-09-23, post-run review of
  `roadmap-versioned-feedback-revision-chain`
  (`handoffs/2026-09-23-roadmap-versioned-feedback-revision-chain-code-review.md`).
- **Status:** not started.

**#430 — Investigate whether the same-receipt re-entry return in the batch proposal path can ever fire**

- **What:** `_run_batch_candidate_proposal` in
  `plan_tool/roadmap_candidate_run.py` (~line 1445) returns the stored active
  candidate without a model call when
  `active.evidence.batch_receipt == capsule.receipt`. While a candidate is
  active, the new capsule is built with that candidate as its `source`
  (`plan_tool/roadmap_candidate_context.py`, the batch receipt binds `source`),
  and the stored candidate's receipt names that candidate's own source: the
  accepted root for an initial candidate, the initial's source for an edit or
  an answered replacement. The two receipts therefore appear never to compare
  equal, so re-running `--propose-candidate` makes a fresh model call against a
  different capsule instead of returning the stored candidate. Observed
  2026-09-23: after a first batch was stored, re-running it made a second model
  call (call count 1) and the reply was rejected because the admitted items had
  changed. The only test of re-entry,
  `test_reentry_returns_the_bound_candidate_without_another_backend_call` in
  `tests/test_roadmap_candidate_run.py`, drives the selector-era path, not the
  batch path. The branch has not changed since `30484873`. Found in code review
  of `roadmap-structural-feedback-approval` and re-verified in a later pass.
- **Why:** if the branch is dead, its line reads as a guarantee of idempotent
  re-entry that the batch path does not give; if it can fire in a state nobody
  has traced, deleting it would be wrong. The output may be "no action."
- **Effort:** small — one investigation: build each batch state (no active
  candidate, active initial, active edit-produced, active answered replacement,
  after release, after promotion), compute both receipts in each, and record
  whether they can be equal. Then one of: delete the branch and say so, keep it
  and add the missing batch-path test, or leave it and record why.
- **Risks / fallout:** none for the investigation. Deleting a branch that can
  fire would change model-call counts.
- **Dependencies:** none.
- **Outcome:** a recorded verdict — "can fire in states X" or "cannot fire in
  any batch state" — backed by an executed check over every state.
- **In scope:** `plan_tool/roadmap_candidate_run.py`
  (`_run_batch_candidate_proposal`), the receipt construction in
  `plan_tool/roadmap_candidate_context.py`, a probe over the batch states, and
  the single test or removal that follows from the verdict.
- **Out of scope / Non-goals:** changing what a re-run does when the receipts
  differ (it stays a fresh proposal), making `--propose-candidate` idempotent by
  another mechanism, and the selector-era proposal path.
- **Allowed behavior changes:** none, unless the verdict is "cannot fire": then
  removing an unreachable branch changes no behavior.
- **Allowed reorganization:** none.
- **Verification:** a test or script that builds each state and asserts the
  receipts differ (or names the state where they match); the full suite passes.
- **Stop / defer:** if a state is found where the receipts match and the branch
  fires, keep it, add the missing test, and stop; any wider question about
  idempotent re-entry becomes its own entry.
- **Approach:** `direct` — a bounded investigation that may end in "no action."
- **Route:** `direct` · **Readiness:** `evidence-gated` · **Tier:**
  `experienced` — it needs a trace of the batch states, not a design decision.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** found 2026-09-23 in code review of
  `roadmap-structural-feedback-approval`; filed 2026-09-24 at the owner's
  direction. It sits outside that plan's range and breaks nothing.
- **Status:** not started.

**#427 — `roadmap-versioned-feedback-revision-chain` step details cite 96 test names that do not exist**

- **What:** the eleven step detail files under
  `docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/`
  name tests in backticks. Machine-verified 2026-09-23 (method: every backticked
  `test_*` identifier in a detail file, matched against every `def test_*` in
  `tests/**/*.py`): 212 names cited, 116 defined, 96 not defined. Per step
  (cited/defined): 1: 15/10, 2: 8/1, 3: 12/0, 4: 16/2, 5: 34/25, 6: 34/22,
  7: 22/13, 8: 29/20, 9: 17/17, 10: 16/2, 11: 9/4. The executor may have covered a
  behavior under another name, so a missing name is a claim to check, not proof the
  behavior is untested. Equally, a defined name does not prove the test asserts what
  the detail says; this entry does not audit that.
- **Why:** a detail that names tests that do not exist misleads its readers and
  re-triggers the same `reconcile-code` finding. The run's `enforce_step_tests` gate
  only checks that a test file was touched, so it cannot catch this.
- **Effort:** medium — 96 names, about 40 of them in steps 3, 4 and 10. Each is a
  lookup (is the behavior covered under another name?) followed by a corrected
  citation, a new test, or a dropped claim.
- **Risks / fallout:** small. Detail edits are text and any new test is additive.
- **Dependencies:** none; `roadmap-versioned-feedback-revision-chain` is closed.
- **Outcome:** every backticked `test_*` name in the eleven detail files matches a
  defined test, and the identifier match in **What** reports 0 missing.
- **In scope:** the eleven detail files; a new test only where a named behavior is
  genuinely uncovered.
- **Out of scope / Non-goals:** changing plan bodies or acceptance criteria;
  auditing whether existing tests assert what a detail says; other plans' details;
  renaming an existing test to match a detail (change the detail to cite the real
  name).
- **Allowed behavior changes:** none.
- **Allowed reorganization:** none.
- **Verification:** rerun the identifier match described in **What** and get 0
  missing; the full suite passes.
- **Stop / defer:** a behavior found genuinely untested and not trivial to cover
  becomes its own entry; do not widen this one.
- **Approach:** `direct`.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `experienced` — each
  name needs a judgment about whether its behavior is covered.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** 2026-09-23, closing `roadmap-versioned-feedback-revision-chain`; the
  coverage note in
  `handoffs/2026-09-23-roadmap-versioned-feedback-revision-chain-code-review.md`.

**#426 — Following 13 links in `RUNBOOK.md` and two dated handoffs lands on a missing file, because the docs they name were renamed or deleted** → promoted to IPPT-4 (2026-09-24)

**#433 — Expose truthful terminal progress for ledger-batch candidate proposals**

- **What:** make `plan-tool roadmap <slug> --propose-candidate` report concise
  stderr lifecycle status while a ledger-batch candidate proposal is running:
  batch accepted, model attempt started, periodic local-process progress with
  elapsed and backend-silence time, response validation, retry/correction,
  stored candidate, and terminal rejection or failure.
- **Why:** Integration candidate proposals commonly take one to four minutes. The
  command currently writes `claude_call_progress` events into
  `.plan-tool/runs/<slug>/...jsonl` every 20 seconds, but prints no incremental
  terminal status. An operator cannot tell whether the local process is still
  alive without manually locating and tailing the run log.
- **Effort:** medium. The underlying run-log events and candidate attempt
  lifecycle already exist, but the command needs a bounded stderr reporter,
  stable wording, tests, and a decision on reuse of the existing status seam.
- **Risks / fallout:** progress output must not claim that the backend is
  healthy merely because the local process emits a timer tick. It must say
  elapsed time and backend silence explicitly, preserve machine-readable
  command output, avoid model/prompt content, and never report candidate
  storage or approval before the corresponding durable transition succeeds.
- **Dependencies:** evaluate `#349`'s `progress.py`/roadmap-status seam before
  adding another reporter. This item may reuse that reporter but must not
  expand `#337`'s completed stage-run contract by implication.
- **Outcome:** a terminal operator can see that a ledger-batch candidate
  proposal is locally progressing or has reached a named terminal result
  without inspecting JSONL files by hand; a quiet backend remains visibly
  "waiting" rather than being represented as confirmed backend progress.
- **In scope:** batch `--propose-candidate` status only; attempt start,
  periodic elapsed/silence reports, response-received validation, retry with a
  closed correction category, stored/rejected/failed terminal lines, stderr
  routing, and focused CLI/reporter tests.
- **Out of scope / Non-goals:** streaming model output or prompts; job control,
  cancellation, dashboards, persistent live-job state, candidate review or
  promotion status, generic status expansion across all commands, and changing
  JSONL schema or candidate authority.
- **Allowed behavior changes:** additional human-readable stderr lines during
  batch candidate proposals. Candidate bytes, feedback state, retries, exit
  codes, and machine-readable output retain their existing semantics.
- **Allowed reorganization:** only the smallest extraction needed to reuse a
  current progress/status reporter after the `#349` seam decision; do not
  refactor unrelated roadmap status paths.
- **Verification:** use an injected delayed candidate invoker to assert ordered
  start, periodic waiting, validation, retry, stored, and rejected messages;
  assert silence time is labelled as silence rather than success; verify no
  model content appears; and prove JSONL lifecycle records and command results
  remain unchanged.
- **Stop / defer:** if `#349` selects a shared reporter contract that changes
  the implementation shape, route this item through that contract rather than
  adding a second status channel. A request for real backend liveness or job
  control is separate work.
- **Approach:** `plan-tool` — user-visible lifecycle semantics and the shared
  reporter boundary need a focused design.
- **Route:** `plan` · **Readiness:** `decision-needed` · **Tier:** `standard`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** Integration ledger-batch candidate acceptance attempts on 2026-09-28.
- **Status:** not started.

**#434 — Decide whether the roadmap candidate decision commands should write run logs**

- **What:** at HEAD, four roadmap candidate flows write a run log
  (`generate_candidate_question`, `request_replacement`,
  `_edit_structural_candidate`, and the `--propose-candidate` batch flow in
  `roadmap_candidate_run.py`). The commands that change candidate state write
  none: `decide_structural_candidate` (approve), `reject_candidate_review`,
  `discard_candidate_review`, `seal_review`, and `promote_review_seal` contain
  no `RunLogWriter`. The owner recorded the aim of wider run-log coverage on
  2026-09-24; whether and how to log them is undecided.
- **Why:** `plan-tool runs` and the JSONL under `.plan-tool/runs/<slug>/` show a
  proposal, a question, a replacement, and a structural edit, but not the
  decision that accepted, rejected, discarded, or promoted the result. An
  operator reconstructing why a candidate became the accepted head has to read
  the candidate lifecycle records instead of the run log.
- **Effort:** medium if selected. Each command needs an event shape, a place in
  the run-log schema, and tests; the decision itself is small.
- **Risks / fallout:** a run-log event is a persisted, versioned shape, so a
  new event is a contract, not a print statement. A log write must never become
  an authority: the candidate lifecycle records stay the only record of a
  decision, and a failed log write must not change a decision's outcome. Events
  must carry ids and outcome only, no model or prompt content. Logging every
  decision command also changes which commands leave a `.plan-tool/runs/`
  file, which `plan-tool runs clear` and the profile view then see.
- **Dependencies:** none. `#430` (whether a batch re-entry return can fire) is
  adjacent but independent.
- **Outcome:** a recorded owner decision on whether approve, reject, discard,
  and promote write run logs, and if yes, which events they write. Two
  outcomes (the decision, then its implementation) are two steps: implement
  only after the decision is recorded here.
- **In scope:** the four state-changing commands named above and the run-log
  event shape they would use; the decision to log some, all, or none of them.
- **Out of scope / Non-goals:** logging read-only views or `--compare`, which
  are deliberately log-free by contract (`ROADMAP_FORMAT.md`); changing the
  existing four flows' events; making a run log an authority or a recovery
  source; a generic audit trail or event bus; `--propose-candidate` progress
  output (`#433`).
- **Allowed behavior changes:** none until the decision is recorded. If the
  decision is yes, new run-log files and events for the commands it names.
- **Allowed reorganization:** none.
- **Verification:** for each command decided in scope, a test that the event is
  written with ids and outcome only, that a failed log write leaves the
  decision's outcome and exit code unchanged, and that the candidate lifecycle
  records are byte-identical with and without the log.
- **Stop / defer:** if logging requires a run-log schema version bump or a new
  reader, stop and file that as its own entry rather than absorbing it here.
- **Approach:** decision first, then `direct` if the answer is a small event
  per command and `plan-tool` if it needs a schema change.
- **Route:** `direct` · **Readiness:** `decision-needed` · **Tier:** `architect`
  (it defines a persisted event contract). **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** the structural-feedback-approval review ledger's owner direction
  of 2026-09-24 (`handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md`,
  "Wider run-log coverage"), filed 2026-09-29.
- **Status:** not started.

**#435 — Decide whether candidate review needs a model-judged narrative review for contradictions a deterministic check cannot see**

- **What:** IPPT-19 (`plan-tool` plan `candidate-narrative-review-evidence`) ships
  the deterministic half of narrative review evidence: a check that live prose
  names a design row the candidate or its accepted lineage removed, a
  non-refusing reconciliation-response basis, and an evidence display computed
  from the candidate. It deliberately does not run a model-judged review of
  whether prose is internally consistent (a decision called pending that is
  settled, current assertions versus history), store evidence, or record reviewer
  dispositions. Whether any of that is wanted is undecided.
- **Why:** the Integration Group 5 candidate's Decisions paragraph calls a settled
  decision pending, which only a meaning-level reading can see. IPPT-19 surfaces
  the removed-decision reference in the same paragraph; a person caught the
  pending-versus-settled contradiction, and IPPT-18 gives them the tool to
  correct it. Four audit rounds on the first IPPT-19 plan, which carried the
  model-judged half, each exposed a new interaction (stored evidence and its
  staleness, dispositions, an unavailable-review state, regeneration timing, the
  answer-and-seal path), so the half was carved out on 2026-10-02 rather than
  built.
- **Effort:** large if selected. A stored, identity-bound evidence record, a
  bounded model call behind an invoker seam, a disposition vocabulary, and the
  approval and CLI changes that tie them together.
- **Risks / fallout:** this is a semantic property with no binary observable. A
  proxy measures vocabulary, and a high false-positive rate means kill, not tune
  (`CLAUDE.md` § "Validating a semantic property you cannot observe"). Any design
  here that gates approval on a model finding, flips an exit code on one, or
  decides consistency by keyword matching is out of bounds. The unresolved
  interactions above (what approval does with missing or stale findings, what a
  reviewer sees before a one-invocation seal) must be answered before a plan.
- **Dependencies:** IPPT-18 (the correction operation a reviewer uses to act on a
  finding) and IPPT-19 (the deterministic evidence this would extend) land first.
- **Outcome:** a recorded decision on whether a model-judged narrative review is
  built, and if yes, the one thing it delivers (findings shown to the reviewer,
  never a gate). Decision first, then at most one plan.
- **In scope:** the decision; if yes, a bounded model call per candidate that
  returns meaning-level findings for the reviewer, and the minimum record needed
  to show them.
- **Out of scope / Non-goals:** a semantic gate or refusal; an exit-code flip; an
  unbounded audit loop; keyword matching as the deciding rule; quality, length,
  or agreement checks between two prose artifacts; rewriting prose (IPPT-18);
  changing the deterministic evidence IPPT-19 ships.
- **Allowed behavior changes:** none until the decision is recorded.
- **Allowed reorganization:** none.
- **Verification:** the decision is recorded here with the evidence it rests on.
  If yes, the plan's Testing names its binary observable, or the plan is not
  authored.
- **Stop / defer:** if no binary observable can be named for what the review
  delivers, stop and record "do not build" here.
- **Approach:** decision first, then `plan-tool` if the answer is yes.
- **Route:** `plan` · **Readiness:** `evidence-gated` (gate: a second
  observed candidate where a person missed a meaning-level contradiction that
  the deterministic evidence did not show; "no action" is a valid outcome) ·
  **Tier:** `architect` (persisted evidence, blocking-policy boundary).
  **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** the IPPT-19 plan carve, 2026-10-02; Integration Group 5 review, 2026-10-01.

**#436 — Show prose corrections as labeled cards in structured roadmap version comparison**

- **What:** the read-only roadmap version comparison prints the raw text patch,
  and for a candidate whose direct predecessor is the base it also shows
  verified row-linked prose amendments (`roadmap_compare_run.py`). IPPT-18 adds a
  candidate operation that replaces one existing paragraph. This entry is the
  option to teach the comparison to show that replacement as a labeled
  before-and-after card, beside the add-row evidence, instead of only a raw text
  difference.
- **Why:** a reviewer reading the comparison later sees a plain diff of the
  paragraph with no statement that it was an authorized correction. Approval time
  already shows the exact before and after (IPPT-18's review step), so nothing is
  hidden; this only improves the later read.
- **Effort:** small. One step: bind the stored correction records into the
  comparison's evidence and renderer, with tests.
- **Risks / fallout:** widening the comparison's evidence contract changes a
  read-only surface other code reads (`ROADMAP_FORMAT.md` documents its outcome
  vocabulary), and the comparison route must stay read-only.
- **Dependencies:** IPPT-18 lands first, so the stored correction operation exists.
- **Outcome:** the comparison shows each correction as a labeled before-and-after
  record, with the raw patch unchanged.
- **In scope:** `plan_tool/roadmap_compare.py`, `roadmap_compare_run.py`,
  `roadmap_compare_render.py`, their tests, and the `ROADMAP_FORMAT.md` /
  `docs/reference/commands.md` lines that describe the comparison.
- **Out of scope / Non-goals:** changing the raw patch output; making the
  comparison accept, enroll, promote, settle, or repair anything; changing how a
  correction is stored or approved.
- **Allowed behavior changes:** comparison cards and JSON gain one record kind.
- **Allowed reorganization:** none.
- **Verification:** a comparison of a candidate containing a correction shows the
  labeled before and after, the raw patch is byte-identical to before, and the
  existing add-row evidence cases are unchanged.
- **Stop / defer:** if the evidence contract needs a version bump, stop and file
  that as its own entry.
- **Approach:** `direct`.
- **Route:** `direct` · **Readiness:** `blocked-on IPPT-18` · **Tier:**
  `experienced` (a CLI-adjacent evidence contract across modules).
  **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** the IPPT-18 plan carve, 2026-10-02; the comparison-amendments work
  (PR #13).
- **Status:** not started.

**#437 — Let a candidate reconciliation response state its basis, and show when it does not**

- **What:** when the model answers a piece of feedback inside a roadmap
  candidate, its answer is free text. This entry is the option to let that answer
  also state a basis: either the corrective operations it made, or a no-change
  justification that cites specific source spans and settled rows. The code would
  check that each citation points at real text, and the reviewer would see "no
  basis given" or "citation does not resolve" as non-blocking notes. The answer
  would still be accepted exactly as today.
- **Why:** a response can claim a reconciliation is done without saying what it
  changed or why nothing needed to. IPPT-19 shows the deterministic part of the
  gap (live prose that still names a removed row) and deliberately leaves this
  part out, because it is a separate idea from that check and the Integration case does
  not need it.
- **Effort:** medium. An optional field on the response record with additive
  parsing, a prompt change in `roadmap-candidate-delta.md`, the citation check,
  and the display lines, with legacy candidates still loading.
- **Risks / fallout:** it changes a persisted candidate shape (additively) and a
  model prompt. A response without a basis must stay accepted, because rejecting
  it would change ingest behavior and conflicts with "evidence only"; a check
  that decides whether a justification is *good* is a semantic check and is out
  of bounds (`CLAUDE.md` § "Validating a semantic property you cannot observe").
- **Dependencies:** IPPT-18 and IPPT-19 land first. IPPT-19's computed-evidence
  function is where the basis check would plug in.
- **Outcome:** a response may carry its basis; the reviewer sees when it is
  missing or cites something that does not exist; nothing is refused for it.
- **In scope:** the optional response field and its additive parse, the prompt
  asking for it, a citation-resolves check, and the display lines.
- **Out of scope / Non-goals:** refusing or retrying a response that lacks a
  basis; judging whether a justification is good; changing feedback eligibility
  or the ledger's response text; any model-judged review (#435).
- **Allowed behavior changes:** the candidate response record gains an optional
  field; the prompt asks for it.
- **Allowed reorganization:** none.
- **Verification:** a response with a basis parses and replays; a stored
  pre-change candidate still loads and replays; a response without a basis is
  accepted unchanged and shows as a missing basis; an unresolvable citation shows
  as a note and refuses nothing.
- **Stop / defer:** if the response record cannot gain an optional field without
  a schema version bump, stop and file that as its own entry.
- **Approach:** `plan-tool`.
- **Route:** `plan` · **Readiness:** `blocked-on IPPT-19` · **Tier:**
  `experienced` (a prompt and an additive persisted field within existing
  contracts). **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** the IPPT-19 plan carve, 2026-10-02.
- **Status:** not started.

**#438 — Widen the narrative check's removed-id source to a candidate's own removals and a stack's root**

- **What:** IPPT-19's narrative check finds live prose that names a removed row,
  but only for removals recorded in the candidate artifact's own carried
  `removals` (or, for a feedback-free candidate, its immediate predecessor's).
  Two removals escape it: a row dropped by the candidate's own `remove-row`
  operation, which writes no removal record, and a removal recorded at the
  accepted root of a stack of feedback-free batches, which the tip's immediate
  predecessor no longer carries. This entry is the option to derive the set from
  the row-id difference between predecessor and candidate, and from the recorded
  root's removals, so those cases show the same evidence.
- **Why:** the code review of IPPT-19 (round 6, 2026-10-05) found both by static
  reading. Integration Group 5 now supplies observed evidence for the candidate's
  own-removal case; the stacked-root case remains unobserved.
- **Evidence:** in the Integration repository, candidate
  `8a802c3cca9a73b7bf543e86b4abfa9173bc88f03b9ba65ff063ad1c800db95f`
  stores a `remove-row` for `assumption-connector-inputs-checkable` under
  `fb-constraints-checkable-connectors` in
  `docs/implementation-plans/roadmaps/integration-aidlc-mvp/.roadmap-versions/8a802c3cca9a73b7bf543e86b4abfa9173bc88f03b9ba65ff063ad1c800db95f/candidate-evidence.json`.
  Its sibling `04-roadmap.md:168` still presents that assumption as a current
  risk, and `04-roadmap.md:172` still says the transition plan consumes it.
  Candidate generation succeeds and stores this inconsistent artifact bundle.
  Running the approval-time narrative evidence
  (`roadmap_candidate_narrative.py:candidate_narrative_evidence_from_bytes`,
  read-only) on this candidate against its source version
  `d063e01dd10e9336cc5d995640927e80babea2c4696b4cb09eb31b1494c625fa` returns
  no blocking findings and no evidence items (2026-10-05), so approval would
  pass both stale references unflagged.
- **Effort:** medium. A second removed-id source in `check_removed_ids_in_live_prose`
  and `compute_candidate_narrative_evidence`, a root load for stacked tips, the
  contract section "Source of the removed ids", and tests for each source.
- **Risks / fallout:** a row-id difference counts a row the candidate replaced
  under a new id as removed, so the ambiguous kind needs a second look; the
  check stays evidence-only and a widened source widens the blocking class, so
  the false-positive rate on real candidates must be measured first.
- **Dependencies:** IPPT-19 lands first.
- **Outcome:** a candidate that removes a row itself, or a stack whose root
  records a removal, shows the same removed-id evidence as a carried removal.
- **In scope:** the removed-id source and its contract text.
- **Out of scope / Non-goals:** any model-judged review (#435); a new defect
  class; changing what blocks approval or the operator exits; storing evidence.
- **Allowed behavior changes:** more candidates are shown, and may be refused,
  for prose that names a removed id.
- **Allowed reorganization:** none.
- **Verification:** a candidate with its own `remove-row` and prose naming the row
  is refused with both exits; a three-hop stack whose root carries a removal is
  checked at the tip; the existing carried-removal cases are unchanged.
- **Stop / defer:** if the row-id difference mislabels replaced rows as removed
  on real candidates, stop and record the rate here.
- **Approach:** `plan-tool`.
- **Route:** `plan` · **Readiness:** `decision-needed` (own-removal case
  observed above; stacked-root case remains traced) · **Tier:**
  `architect` (widens a blocking policy source).
  **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** the IPPT-19 code review, round 6, 2026-10-05.

**#439 — Decide whether one candidate may replace a row and correct the paragraph that describes it**

- **What:** `plan-tool roadmap --propose-candidate` refuses a candidate that
  corrects a paragraph (`correct-prose`) while also adding, replacing, or
  removing any row that paragraph names, the paragraph's *owning set*
  (refusal `owning-set-interaction`). The fix is therefore always split: the
  first candidate changes the rows and drops the prose correction, and a
  stacked follow-up candidate, built on the first, corrects the prose. One
  stack approval covers both. This entry decides whether a replacement and
  its paragraph correction should be allowed in one candidate instead.
- **Why:** the rule was set deliberately by IPPT-18
  (`2-candidate-prose-correction`) and is stated in `ROADMAP_FORMAT.md` §
  "Shared-narrative correction"; no reason beyond caution is recorded, and a
  code read found no mechanical conflict for replacement (replacing a row
  changes only frontmatter, never its id). The split route works but costs a
  reviewer a second round: they must notice the dropped correction in the
  first candidate's responses, submit new feedback items, and run a second
  proposal.
- **Evidence:** Integration Group 5, 2026-10-05. Candidate
  `8a802c3cca9a73b7bf543e86b4abfa9173bc88f03b9ba65ff063ad1c800db95f` dropped
  four requested corrections and said so in its responses to
  `fb-components-settled-prose`, `fb-plans-all-connectors`,
  `fb-plans-three-step-workflow`, and `fb-plans-both-handoffs`. Two new
  artifact-level items (`fb-components-narrative-reconcile`,
  `fb-plans-narrative-reconcile`) then produced stacked candidate
  `191f815687045215deeb2248f612a40ce20d14ca608481279602dc03d800f6e7` with
  exactly those four `correct-prose` operations and no row changes. Its
  approval preview reports narrative evidence `none` and
  `approve confirmation-required`. The same route covers removal: once the
  first candidate removed `assumption-connector-inputs-checkable`, it was no
  longer in the later paragraphs' owning sets.
- **Effort:** medium. One compatibility rule in
  `plan_tool/roadmap_candidate.py:_resolve_corrections`, the candidate prompt
  (`plan_tool/prompts/roadmap-candidate-delta.md`), the format contract, and
  tests in the `tests/test_roadmap_candidate*.py` modules.
- **Risks / fallout:** reverses part of a settled, architect-reviewed
  contract; `test_correction_with_row_edit_in_owning_set_refuses` pins the
  current rule and inverts for replacement.
- **Dependencies:** none; IPPT-18 has shipped.
- **Outcome:** one candidate can replace rows and correct the paragraph that
  describes them, against the same predecessor version.
- **In scope:** the `owning-set-interaction` rule for `replace-row`, the
  candidate prompt, and `ROADMAP_FORMAT.md` § "Shared-narrative correction".
- **Out of scope / Non-goals:** `add-row` or `remove-row` with a correction of
  the same paragraph (stacking covers removal); arbitrary narrative editing;
  new span authority; weaker gates; automatic approval.
- **Allowed behavior changes:** a `replace-row` plus `correct-prose` pair on
  the same paragraph succeeds instead of being refused. Nothing else.
- **Allowed reorganization:** none.
- **Verification:** the pair materializes, replays, and shows both the row and
  prose diffs for approval; `add-row` and `remove-row` on an owning row still
  refuse; the approval-time narrative check still runs on the final body.
- **Stop / defer:** if allowing replacement needs span authority beyond the
  issued paragraph, stop and raise it.
- **Approach:** `plan-tool`.
- **Route:** `plan` · **Readiness:** `decision-needed` (whether the
  second review round justifies changing the IPPT-18 rule; the stacked route
  is the working alternative) · **Tier:** `architect` (changes a settled
  candidate contract). **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** Integration Group 5 prose correction diagnosis, 2026-10-05; moved from
  `BUG_BACKLOG.md` after the stacked route was shown to work.

**#440 — Measure whether listing uncorrected paragraphs that name changed rows would help a candidate reviewer**

- **What:** after `plan-tool roadmap --propose-candidate`, show a non-blocking
  list of the issued paragraphs that name a row the candidate added, replaced,
  or removed but that the candidate did not correct. It is a fact about the
  candidate (paragraph owners intersect changed rows, no `correct-prose` on
  that paragraph), not a judgment that the paragraph is stale. Today the only
  signal that a correction was dropped is free text in the model's response.
- **Why:** on Integration Group 5 the first candidate dropped four corrections because
  of `owning-set-interaction`. The model named each dropped span in its
  responses, but the prompt does not ask it to, and a reviewer who misses those
  sentences approves stale narrative. The stacked follow-up that fixes it
  (`ROADMAP_FORMAT.md` § "Shared-narrative correction", Delivery route) depends
  on the reviewer noticing.
- **Evidence:** Integration candidate
  `8a802c3cca9a73b7bf543e86b4abfa9173bc88f03b9ba65ff063ad1c800db95f`
  (2026-10-05) changed eleven rows; its responses to
  `fb-components-settled-prose`, `fb-plans-all-connectors`,
  `fb-plans-three-step-workflow`, and `fb-plans-both-handoffs` each name an
  omitted span. How many other issued paragraphs name a changed row and are
  still accurate is not measured.
- **Effort:** small to measure: one read-only script over the Integration candidate
  stack. Medium to build: a display line in candidate disclosure and its tests.
- **Risks / fallout:** a paragraph that names a changed row is often still
  accurate, so the list can be mostly noise. At a high false-positive rate a
  reviewer learns to skip it, which is the reason to measure first and kill
  rather than tune (`CLAUDE.md` § "Validating a semantic property you cannot
  observe").
- **Dependencies:** none.
- **Outcome:** a measured false-positive rate on real candidates, and a
  build-or-drop decision recorded here.
- **In scope:** the measurement on the Integration Group 5 candidates; if built, one
  non-blocking disclosure line.
- **Out of scope / Non-goals:** judging whether a paragraph is stale; any gate,
  refusal, or exit-code change; validating feedback request text; the
  response-basis field (#437) and model-judged narrative review (#435).
- **Allowed behavior changes:** if built, one extra non-blocking line in
  candidate disclosure. None from the measurement.
- **Allowed reorganization:** none.
- **Verification:** the measurement reports, for each Integration Group 5 candidate,
  how many listed paragraphs were in fact stale; a built line lists the four
  Group 5 spans on `8a802c3c…` and nothing on its stacked follow-up
  `191f815687045215deeb2248f612a40ce20d14ca608481279602dc03d800f6e7`.
- **Stop / defer:** if most listed paragraphs are accurate, record the rate and
  drop the idea.
- **Route:** `plan` · **Readiness:** `evidence-gated` (gate: the measured
  false-positive rate) · **Tier:** `experienced`. **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** Integration Group 5 stacked-route trial, 2026-10-05.

**#449 — Remove the code the retired escalation, impact-analysis, and structural-rewrite routes left callerless**

- **What:** step 9 of `roadmap-versioned-from-birth` removed the three routes
  and the modules only they used. Seven leftovers have no production caller
  and were outside that step's file list:
  - `plan_tool/shell.py:structural_codex_invoke` (callers: `tests/test_shell.py`
    and `tests/test_backend_config.py` only);
  - the four run-log event families `RoadmapEscalationPreflight/Result`,
    `RoadmapImpactPreflight/Result`, `RoadmapStructuralRevisionPreflight/Attempt`
    in `plan_tool/run_log.py`, with their writer methods, validators, the
    hand-copied reason list citing `roadmap_escalation_selection.ReceiptReason`,
    their tests in `tests/test_run_log.py`, and their `DATA_CONTRACT.md` /
    `plan_tool/data_contract.py` entries;
  - `EvidenceNamespace.ESCALATIONS` and `IMPACT_ANALYSES` in
    `plan_tool/roadmap_evidence_store.py` (no writer remains; stored records
    stay unread on disk). `scan_evidence` then has only test callers;
  - the module name `plan_tool/roadmap_escalation_run.py`, which now holds only
    the Git receipt head-state helpers decision-settlement receipts use;
  - `plan_tool/backend.py:structural_codex_backend` and
    `STRUCTURAL_CODEX_VERSION` (callers: `structural_codex_invoke`, `tests/test_backend.py`,
    `tests/test_backend_config.py` only);
  - `plan_tool/prompts/roadmap-structural-feedback-revision.md` (loaded by no
    production code; listed only in the shipped-prompt inventory in
    `tests/test_roadmap.py`);
  - `plan_tool/roadmap.py:render_update_judgment_section`,
    `UPDATE_JUDGMENT_PROMPT_FILENAME`, and
    `plan_tool/prompts/roadmap-revision-update-judgment.md` (no caller remains
    for the function; the prompt file is read only by it).
- **Why:** an event nothing emits and a namespace nothing writes read as live
  contract. The run-log and `DATA_CONTRACT.md` shapes are a persisted-schema
  decision, so the removal is its own change, not a rider on step 9.
- **Effort:** medium — one deletion per item plus the drift-guarded
  `DATA_CONTRACT.md` sections; the module rename is a call-site sweep.
- **Approach:** `direct`.
- **Dependencies:** `roadmap-versioned-from-birth` step 9 landed. Not before
  Integration has been converted by hand, because its stored receipts and analyses
  sit in the namespaces item three removes.
- **Outcome:** no run-log event, namespace, shell wrapper, or module name
  refers to a retired route.
- **In scope:** the four items above and the tests, docs, and contract entries
  that pin them.
- **Out of scope / Non-goals:** deleting or migrating stored records in any
  roadmap; the evidence store's `DECISION_SETTLEMENTS` namespace; any new
  route for structural rewrites.
- **Allowed behavior changes:** run logs no longer define the removed event
  names. None otherwise.
- **Allowed reorganization:** renaming `roadmap_escalation_run.py` and updating
  its importers.
- **Verification:** `rg -n "roadmap_(escalation|impact|structural_revision)_(preflight|result|attempt)|structural_codex_invoke|ESCALATIONS|IMPACT_ANALYSES" plan_tool tests *.md docs`
  returns only dated history; the full suite and the `DATA_CONTRACT.md` drift
  test pass.
- **Stop / defer:** if a run-log reader outside this repo parses the removed
  event names, keep the event classes and record the reader here.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `experienced`.
  **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** `roadmap-versioned-from-birth` step 9 caller trace, 2026-10-06.

**#450 — Remove retired roadmap routes from the docs outside the version-only docs sweep**

- **What:** `roadmap-versioned-from-birth` step 12 swept the roadmap docs, but
  these live docs still name a removed route (`--from-stage`,
  `--confirm-brief-rebind`, `--enroll-version`, `--reopen-feedback`, escalation,
  impact analysis, or structural rewrite) or link a deleted `ROADMAP_FORMAT.md`
  anchor: `CAPABILITIES.md` (including its `#stage-re-entry-selection-and-bounded-feedback`
  link), `docs/how-to/use-cases.md`, `docs/how-to/common-workflows.md`,
  `docs/reference/commands.md`, `docs/reference/contracts/codex-cli.md`, and
  `BUG_BACKLOG.md`'s settled-decision source-admission entry.
- **Why:** each reads as current behavior and sends a reader to a refusal.
- **Effort:** small — doc edits plus extending the removed-route guard's file list.
- **Approach:** `direct`.
- **Outcome:** no live doc names a removed roadmap route outside dated history.
- **In scope:** the files above; adding them to `_REMOVED_ROUTE_DOC_FILES` in
  `tests/test_roadmap_format.py`.
- **Out of scope / Non-goals:** any replacement route for structural rewrite or
  revision restore.
- **Verification:** the extended `test_live_roadmap_docs_name_no_removed_route`
  passes.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `experienced`.
  **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** `roadmap-versioned-from-birth` step 12 sweep, 2026-10-06.

**#451 — Remove the stage-feedback revision path and result fields the stage-run rewrite left callerless**

- **What:** the stage run no longer revises a stage from reviewer feedback, but
  the machinery for it remains. Each name below has zero production callers,
  checked with `rg -n "\bNAME\b" plan_tool` minus its definition (2026-10-06):
  - no caller in `plan_tool/` or `tests/` (definition only):
    `roadmap.py:_run_bounded_stage_feedback`, `_check_predecessor_review_rows`,
    `_awaiting_review_count`, `_newly_settled_decision_ids`,
    `_feedback_counts_by_state`, `_has_open_feedback`;
  - no caller outside `tests/`: `roadmap.py:_run_feedback_free_stage`,
    `cli/roadmap_cmd.py:_revise_feedback_has_conflict`,
    `roadmap_artifacts.py:domain_path`, `constraints_path`, `components_path`,
    `plans_path`, `roadmap_view.py:LoadedRoadmap.directory_exists` (and its
    computation in `load_roadmap`);
  - referenced only from the dead functions above (zero live callers once they
    go): `roadmap.py:recheck_feedback_snapshot`, `_render_stage_feedback_prompt`,
    `_stage_feedback_corrections_block`;
  - `RoadmapResult.feedback_awaiting_review`, `.newly_settled_decisions`, and
    `.invalidated_seed_count`: neither `RoadmapResult(...)` construction in
    `roadmap.py` sets them (no `replace(result, ...)` either), so the three CLI
    helpers that read them (`_feedback_summary_lines`,
    `_newly_settled_summary_lines`, `_seed_invalidation_summary_lines`, called
    at `cli/roadmap_cmd.py:533-537`) always print nothing in production; only
    `tests/cli/test_roadmap_cmd.py` builds results that populate the fields;
  - producer-less stage-loop names (added 2026-10-06, code review 2; checked with
    `rg -n "\bNAME\b" plan_tool tests`): the `source_recheck` parameter of
    `roadmap.py:_run_stage` (no production caller passes it; one test does) and
    the `RoadmapSourceAdmissionError` raises and handlers it feeds (its only
    raise sites are in `recheck_feedback_snapshot`, listed above);
    `_StageOutcome.invalid_detail` (set, never read) and `.reused_predecessor`
    (set only in `_run_feedback_free_stage`, read only by one test);
    `OUTCOME_STAGE_INVALID` with `cli/roadmap_cmd.py:_print_invalid`, and
    `OUTCOME_COMPLETED_NO_CHANGE` with `_print_completed_no_change` (no
    `RoadmapResult(...)` construction uses either outcome; the tests that pin
    them build results by hand);
  - the `stages` parameter of
    `roadmap_decision_settlement_receipt.py:decision_settlement_receipt_proves_completion`
    is unused in its body; the function itself has only test callers, so
    check the test call sites before dropping the parameter.
- **Why:** unreachable summary lines still print reviewer-edit advice, and the
  tests that pin them keep the dead path green, so a reader can mistake it for
  the live feedback contract.
- **Effort:** medium — delete the functions, fields, and CLI helpers together
  with the tests that pin only them.
- **Approach:** `direct`.
- **Dependencies:** none; independent of #449.
- **Outcome:** no function, result field, or CLI summary helper describes a
  stage-feedback revision the stage run cannot perform.
- **In scope:** the names above, their tests, and any doc sentence that
  describes them.
- **Out of scope / Non-goals:** the `invalidated_seed_count` field on the
  run-log `RoadmapStructuralRevisionAttempt` event in `plan_tool/run_log.py`
  (a different record that shares the name; #449 owns it, do not remove it
  here); the
  `ledger`-based feedback intake and decision-settlement routes; the callerless
  leftovers #449 lists.
- **Allowed behavior changes:** the `--run` summary no longer carries the three
  feedback/settlement/invalidation blocks, which already print nothing.
- **Allowed reorganization:** none.
- **Verification:** `rg -n "\b(_run_bounded_stage_feedback|_run_feedback_free_stage|recheck_feedback_snapshot|_check_predecessor_review_rows|_awaiting_review_count|_feedback_counts_by_state|_has_open_feedback|_revise_feedback_has_conflict|_feedback_summary_lines)\b" plan_tool tests`
  returns nothing; the full suite passes.
- **Stop / defer:** if a name gains a production caller before this lands, drop
  it from the list and record why. Claims not machine-verified: none beyond the
  `rg` counts above; the "always print nothing" statement rests on reading the
  two `RoadmapResult(...)` constructions.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `experienced`.
  **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** `roadmap-versioned-from-birth` code review 1, 2026-10-06; producer-less
  stage-loop names added from code review 2, 2026-10-06.

**#452 — Recover an interrupted publication journal before any writer publishes, and make non-root journals recoverable beside a head**

- **What:** `publish_roadmap_generation` refuses with "an interrupted publication
  left its journal" when a journal exists, and recovery runs only inside the stage
  run (`roadmap.py`) and `--settle-decision`
  (`roadmap_decision_settlement_enrolled.py`). After a crash with a journal left,
  `--submit-feedback`, `--propose-candidate`, `--promote`, and the ledger edits
  refuse until the operator runs the stage command, which recovers a root journal
  and then refuses with `already has an accepted head`. With a head present,
  `recover_roadmap_publication` accepts only root, selector, and
  decision-settlement journals, so a crash inside a ledger edit or candidate
  store (journal and head both present) is refused with "enrolled roadmap refuses
  recovery of a non-version-owned generation" and the journal is removed by hand.
  The root-kind recognizer also compares the initial ledger bytes, so a hand
  edit of the reviewer-editable ledger between a crash and recovery makes
  recovery refuse with no stated remedy (`roadmap_revision_publish.py`, expected
  ledger member and the `states != expected` check).
- **Why:** versioned-from-birth removed the other recovery entry points, so a
  crash leaves most writers blocked behind a command that reports failure while
  succeeding at recovery.
- **Effort:** medium — a recover-before-publish step in the shared writer guard,
  plus a recognizer decision per journal kind.
- **Approach:** `direct`; the per-kind recovery policy is a design choice to
  settle first (roll back, adopt, or refuse by kind).
- **Dependencies:** none. The refusal wording and the `RUNBOOK.md` /
  `docs/how-to/roadmap.md` § 3 text name the current route in the meantime.
- **Outcome:** a leftover journal from any writer kind is recovered or refused
  with its own actionable remedy by the next command that needs the roadmap, not
  only by a stage run or settlement.
- **In scope:** `roadmap_revision_publish.py` (`publish_roadmap_generation`,
  `recover_roadmap_publication`, `_is_completed_version_owned_generation`, the
  root recognizer's ledger-member comparison: exempt it once the head names the
  published version, or name the hand-removal remedy), the
  call sites of recovery, the refusal text, and the tests and docs that pin them.
- **Out of scope / Non-goals:** changing the journal format; the first-run
  rollback semantics; any new CLI command for recovery.
- **Allowed behavior changes:** a writer beside a recoverable journal recovers it
  first instead of refusing.
- **Allowed reorganization:** none.
- **Verification:** a test per journal kind (root, selector, ledger edit,
  candidate store, settlement) with a leftover journal and a head: the next writer
  either recovers and publishes or refuses naming the remedy; the full suite
  passes.
- **Stop / defer:** if recovering a non-root kind needs a new member-state
  invariant the recognizer cannot derive, keep refusing that kind and record it
  here.
- **Route:** `direct` · **Readiness:** `decision-needed` · **Tier:** `experienced`.
  **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** `roadmap-versioned-from-birth` code review 2, 2026-10-06.

**#453 — Scope the first-run resume directory by plans directory, and stop `INDEX.md` from naming a stale accepted head after a failed refresh**

- **What:** two derived-state scoping gaps from the version-only stage run.
  (a) The resume directory is `.plan-tool/runs/<slug>/roadmap-stage-resume/`,
  keyed by (repo root, slug) in `roadmap_stage_resume.resume_dir_path`, while the
  accepted head and the writer guard are keyed by plans directory. Two plans
  directories (`--plans-dir` or `PLAN_TOOL_PLANS_DIR`) in one repo that share a
  slug share one resume directory: `_require_no_accepted_head` deletes it beside
  plans dir A's head although plans dir B's aborted run holds paid stages in it,
  and a first run against B reuses stages an aborted run against A held when the
  brief text matches. `brief.digest` records only the brief digest, and the
  writer lock does not span the two plans directories.
  (b) `refresh_roadmap_index` warns and returns when `collect_index_rows` raises
  `RoadmapVersionError` (one unreadable `version.json`, `candidate-evidence.json`,
  terminal resolution, or admission file), so the previous `INDEX.md` stays on
  disk after a promotion and still labels the old version `accepted head`.
- **Why:** (a) a destructive cleanup and a reuse check act on state they cannot
  show belongs to the current plans directory; (b) a file generated for people
  can name the wrong head with only a transient stderr line as the signal.
- **Verified:** by reading `roadmap_stage_resume.py` (`resume_dir_path`,
  `delete_resume`, `write_brief_digest`), `roadmap.py` (`_require_no_accepted_head`,
  `_run_roadmap`, `refresh_roadmap_index`, `load_accepted_head(plans_dir=...)`),
  and `roadmap_index.py` (`collect_index_rows`, `write_roadmap_index`). No
  program was run for (a) or (b); a reproducing test is the first step of the fix.
- **Effort:** small — (a) one scoping decision and its tests; (b) one degrade
  rule and its tests.
- **Approach:** `direct`; the scoping choice for (a) is a design decision to
  settle first: a plans-dir digest in the directory path, or the resolved plans
  dir recorded beside `brief.digest` and a mismatch treated like a digest
  mismatch. For (b): unlink `INDEX.md`, rewrite it with a one-line could-not-refresh
  body, or degrade per version in `collect_index_rows` (list an unreadable
  version with status `unreadable`).
- **Dependencies:** none; independent of #452.
- **Outcome:** a resume directory is only deleted or reused by the plans directory
  that wrote it, and a refresh failure never leaves an `INDEX.md` that names a
  superseded accepted head without saying it is stale.
- **In scope:** `roadmap_stage_resume.py`, its call sites in `roadmap.py`,
  `roadmap_index.py`, `refresh_roadmap_index`, and the tests and docs
  (`ROADMAP_FORMAT.md`, `docs/how-to/roadmap.md` § 3) that pin them.
- **Out of scope / Non-goals:** changing the head, journal, or version-store
  formats; a cross-plans-dir lock; resuming across plans directories.
- **Allowed behavior changes:** the resume path (or its recorded owner) changes;
  a refresh failure rewrites or removes `INDEX.md`.
- **Allowed reorganization:** none.
- **Verification:** a test with two plans directories sharing a slug (one with a
  head, one holding stages) showing the held stages survive the head refusal and
  are not reused across directories; a test with one unreadable historic record
  after a promotion showing `INDEX.md` does not name the old head as current; the
  full suite passes.
- **Stop / defer:** if scoping the directory needs a migration for existing
  held stages, discard them (they cost only regeneration) and record that here.
- **Route:** `direct` · **Readiness:** `decision-needed` · **Tier:** `experienced`.
  **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** `roadmap-versioned-from-birth` code review 4, 2026-10-06.

**#454 — Make a `run` step verify its own edits and sweep the tests that pin the old behavior before it finishes**

- **What:** the `run` prompt (`launcher.py`) does not require a step to run the
  tests it touched, check that every deleted or renamed symbol has no remaining
  use, or search the tests and docs for fixtures, phrases, and helpers that
  encode the behavior being changed. Defects of exactly those three kinds
  surfaced only at the full-suite gate.
- **Why:** each is a cheap local check (a targeted test run, a `grep`) that the
  suite gate repeats later at the cost of a whole failed step and a manual
  repair. `CLAUDE.md` § "Fix the class, not the cited spot" already names the
  sweep for direct changes; a `run` step is the same situation.
- **Evidence (n=1 plan, `roadmap-versioned-from-birth`, 2026-10-06):** a comment
  naming a module that a same-step test forbids (step 4, 1 test red); a dropped
  import still used (step 8, `NameError`, 9 red); a deleted helper still called by
  a kept function although the detail warned the module stays (step 9,
  `NameError`, 10 red); fixtures building the old top-level artifact shape (step 6,
  132 red; step 7, 7 red, one file outside the declared files); snapshot helpers
  not ignoring a newly generated file (step 5, 6 red); a 168-line doc deletion
  leaving prose-pinned assertions red (step 10, 4 red, each needing a per-phrase
  keep-or-retire judgment).
- **Verified:** not yet. The run prompt and gate logic were not read when this was
  filed; the first step is to read the prompt and see whether it already asks for
  any of the three checks and whether the model skipped them.
- **Effort:** small.
- **Approach:** `direct`; a prompt change. Not a gate: the suite gate already
  catches these, and a gate on "ran its tests" would grade a process the tool
  cannot observe.
- **Dependencies:** none; related to #455 (what happens after the gate fails).
- **Outcome:** the run prompt tells the model, before it finishes, to run the
  step's own test files, to search for remaining uses of every symbol it deleted
  or renamed, and to search the tests and docs for the old behavior's fixtures
  and phrases and update (not delete) them.
- **In scope:** the run prompt text and the test that pins its contents.
- **Out of scope / Non-goals:** any new gate, exit-code change, or check of test
  quality (`CLAUDE.md` § "Validating a semantic property you cannot observe");
  per-step runtime budgets; changing the suite gate.
- **Allowed behavior changes:** the prompt grows by a short block.
- **Allowed reorganization:** none.
- **Verification:** the prompt-content test names the three instructions; the
  full suite passes. Effect on real runs is not measurable from one test; record
  step-failure counts from the next multi-step plan.
- **Stop / defer:** if the prompt already contains these instructions, close the
  entry with that finding and keep the evidence for #455.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `experienced`.
  **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-run-gates`.
- **Origin:** `roadmap-versioned-from-birth` run, 2026-10-06.

**#455 — Give a failed `run` step's retry the complete failure list, and decide whether the run gets one bounded repair attempt**

- **What:** (a) the failure note a retry sees keeps a short pytest tail. In step 3
  attempt 2, 3 of the first 6 failures were not visible to the model, and the step
  needed manual repair. A stale tail also persists in `status_note` after the step
  later advances. (b) The run halts after one failed suite gate with no in-run
  repair attempt: it halted at steps 3 through 9, and steps 4, 5, 7, 8, and 9 were
  small mechanical fixes (a comment, an import, a helper, snapshot helpers,
  fixtures) that each cost a manual round trip and a WIP commit.
- **Why:** a retry that cannot see the failures it must fix cannot fix them, and a
  halt costs a human turn for failures the model could repair when shown the
  full list.
- **Verified:** not yet. `launcher.py`'s attempt and retry limits, how
  `status_note` is built, and whether the tail truncation is in the gate output or
  in the note were not read. Read them first.
- **Verified (2026-10-08, partial):** a retry's prompt carries no failure
  information at all. `plan_tool/prompts/run.md` has no `status_note` variable,
  and `plan_tool/renderer.py` never reads `status_note`. The note exists only in
  the plan file: the first 400 characters (`launcher.py:1982`) of the
  500-character tail that `_run_test_gate` returns (`launcher.py:931`). So (a)
  renders the previous gate's failed test ids into the retry prompt, not only a
  longer note. A run that advances the step clears the note
  (`launcher.py:2087`). A stale note survives only a hand-advanced step, which
  `run --accept` (shipped 2026-10-10) closes. Second instance: `roadmap-stack-propagation` step 1, observed
  2026-10-08. After `.tmp/roadmap-stack-propagation.run.log` failed on one test,
  the re-run (`run-step1-retry2.log`, 48 s) modified no declared file.
- **Effort:** small for (a); medium for (b), which interacts with the attempt
  limits and with #88 (a repair attempt must not re-spend an already-successful
  call).
- **Approach:** (a) `direct`: carry the failed test ids with one error line each
  (`pytest -rf` summary) and clear the note when the step advances. (b) decide
  first: a bounded repair attempt that passes the full failure list back, or keep
  halting and rely on (a).
- **Dependencies:** #88 (memoize the call), #87 (same gate family).
- **Outcome:** a retry sees every failed test id from the previous gate with a
  one-line error; (b) has a recorded decision.
- **In scope:** failure-note construction, `status_note` lifecycle, the decision
  on (b), and their tests.
- **Out of scope / Non-goals:** raising the attempt limit by default; changing
  what the gate checks; unattended retry loops without a bound.
- **Allowed behavior changes:** failure notes get longer; a stale note is cleared.
- **Allowed reorganization:** none.
- **Verification:** a test with more failures than the old tail holds, showing all
  ids reach the retry prompt; a test showing the note is cleared on advance; the
  full suite passes.
- **Stop / defer:** if (b) needs a new run state machine, file it separately and
  ship (a) alone.
- **Route:** `direct` for (a); `plan` if (b) is taken · **Readiness:**
  `decision-needed` (on (b)) · **Tier:** `experienced`. **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-run-gates`.
- **Origin:** `roadmap-versioned-from-birth` run, 2026-10-06.

**#457 — Re-run only the failed tests once before a `run` step fails on the suite gate**

- **What:** a suite-gate failure that does not reproduce in isolation fails the
  step. Step 4, run 6: 2 failures (`tests/test_split_pr.py` and one case in
  `tests/test_roadmap_impact_run.py`) on a 362 s suite against about 180 s
  normally; both passed alone (88 passed) and the next run passed unchanged. The
  cause of the slowdown was not identified.
- **Why:** a failed step costs a human round trip; a single re-run of the failed
  ids costs seconds.
- **Evidence:** one instance. A different, order-dependent flake already in
  `BUG_BACKLOG.md` (a pydantic `model_rebuild` flake in
  `test_roadmap_version_promotion.py`) is not the same cause; this entry is the
  gate's response to any flake, not a fix for either.
- **Effort:** small.
- **Approach:** `direct`: on a failed suite gate, re-run only the failed ids once;
  pass only if they all pass, and report both results. A test that fails twice
  fails the step.
- **Dependencies:** none.
- **Outcome:** a non-reproducing failure reports both runs and does not halt the
  step; a reproducing failure behaves as today.
- **In scope:** the gate's failure path and tests.
- **Out of scope / Non-goals:** hiding failures (the second result is always
  reported); re-running more than once; diagnosing the slowdown.
- **Allowed behavior changes:** a step can pass after a first failing run.
- **Allowed reorganization:** none.
- **Verification:** a test with a stub test command that fails once then passes
  (step passes, both results reported) and one that fails twice (step fails); the
  full suite passes.
- **Stop / defer:** gated on a second instance of a load flake failing a gate;
  with one instance, hold at `evidence-gated`.
- **Route:** `direct` · **Readiness:** `evidence-gated` (gate: a second
  non-reproducing gate failure) · **Tier:** `experienced`. **Principle:**
  `untriaged`.
- **Arc assignment:** `backlog-arc-run-gates`.
- **Origin:** `roadmap-versioned-from-birth` run 6, 2026-10-06.

**#458 — Report the test names a step's detail lists that no test file contains (advisory only)**

- **What:** a step can write production code and no tests; the test-authoring
  gate knows only whether a test file was touched. Step 6's first pass edited
  production code and no test file, and 14 test cases named in the detail's
  `## Tests` section were absent.
- **Why:** the information is already in front of the tool (the detail names the
  cases, the tree holds the tests). Delivering it costs one scan.
- **Evidence:** one instance. The false-positive rate is unmeasured, and test
  identifiers in prose drift when tests are renamed during a step.
- **Effort:** small to build; the measurement is the work.
- **Approach:** `direct`: list backticked identifiers in the detail's `## Tests`
  section that do not appear in any test file, after a step finishes, as a
  printed advisory. No gate, no exit-code change.
- **Dependencies:** none.
- **Outcome:** the printed advisory names the absent identifiers, or says none
  were checked.
- **In scope:** the scan, its output line, and tests.
- **Out of scope / Non-goals:** any gate or refusal to advance; judging whether a
  present test is a good one; renaming detection; any check of prose against code
  beyond identifier presence (`CLAUDE.md` § "Validating a semantic property you
  cannot observe").
- **Allowed behavior changes:** one advisory line per step.
- **Allowed reorganization:** none.
- **Verification:** replay the scan over the steps of three merged plans, count
  advisories against steps whose tests were in fact present, and record the rate
  here.
- **Stop / defer:** a high false-positive rate means kill, not tune (same section).
  If most flagged identifiers are renames, drop the entry.
- **Route:** `direct` · **Readiness:** `evidence-gated` (gate: the measured
  false-positive rate) · **Tier:** `experienced`. **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-run-gates`.
- **Origin:** `roadmap-versioned-from-birth` run, step 6, 2026-10-06.

**#459 — Decide what `reconcile-code --no-walk` promises, since an audit call still edited a test file**

- **What:** a sweep run as `reconcile-code --all --no-walk --no-reuse -y` (sweep 2,
  2026-10-06) wrote `test_post_head_stage_refusal_refreshes_the_index` into
  `tests/test_roadmap.py` during step 5's audit and left it uncommitted. The saved
  recommendation read "done, but not yet run ... please run ... before
  committing". The saved report and the tree disagreed about whether the audit was
  report-only.
- **Why:** `reconcile-code` is documented as plan-canonical and code-mutating, so
  `--no-walk` could mean "skip the interactive walk" or "findings only". An
  operator who reads it as the second runs a sweep expecting a clean tree.
- **Verified:** not yet. Read whether the edit is made by the model through its
  own tools and what `--no-walk` is documented to do.
- **Effort:** small (decision plus prompt or detection).
- **Approach:** decide first. Options: state in the prompt that the audit must not
  edit when `--no-walk` is set; or detect and report a changed tree after an audit
  call; or document that `--no-walk` still applies code fixes.
- **Dependencies:** none.
- **Outcome:** `--no-walk` has one documented meaning, and a call that violates it
  is reported.
- **In scope:** the prompt, the post-call tree check, `docs/cli/` regeneration, and
  tests.
- **Out of scope / Non-goals:** changing what the interactive walk applies.
- **Allowed behavior changes:** a sweep may print a changed-tree notice.
- **Allowed reorganization:** none.
- **Verification:** a stub audit invoker that edits a file under `--no-walk`
  showing the notice (or refusal); the full suite passes.
- **Stop / defer:** if the documented meaning is "findings plus fixes", the entry
  closes with a docs change only.
- **Route:** `direct` · **Readiness:** `decision-needed` · **Tier:** `experienced`.
  **Principle:** `untriaged`.
- **Arc assignment:** `backlog-arc-run-gates`.
- **Origin:** `roadmap-versioned-from-birth` reconcile-code sweep 2, 2026-10-06.

**#461 — Record the technology stack as a roadmap layer and call it out at publish and candidate review — PLAN-AUTHORED (`roadmap-stack-layer`)**

- **What:** Stack facts have no single home and no "open" state, and the first stage run publishes without review, so stack choices and open stack questions are accepted unseen; a `stack` collection in `02-constraints.md` records each concern as chosen or open and is called out at first publish, in `INDEX.md`, and in every candidate review.
- **Effort:** medium-large; crosses the constraints schema, gates, stage prompt, feedback/candidate operations, first-run output, `INDEX.md`, candidate review, and the format docs.
- **Risks / fallout:** existing accepted versions lack the collection and must read as "stack not recorded", with stack totality binding only first runs and lineages that already carry it; stack rows are authoritative over hosting and store `product` fields, with no agreement gate or comparison rule (candidate review lists them side by side, decided 2026-10-08).
- **Dependencies:** the shipped `## Stack` seed renderer (`_render_stack_section` in `plan_tool/roadmap.py`), which gains the stack collection.
- **Outcome:** A roadmap records its technology stack as a distinct concern layer — each concern either chosen or explicitly open — called out to the reviewer at first publish and in every candidate review, so a stack choice or open stack question reaching acceptance by a first run or a candidate is never unseen (hand enrollment is deliberately excluded).
- **In scope:** the `stack` collection's schema, parsing, totality gate, and feedback/candidate operations; constraints-stage authoring of chosen and open concerns (deployment platform, store engine, language/runtime); first-publish and `INDEX.md` callout; candidate-review stack summary and delta; inclusion in the `## Stack` seed rendering; format documentation.
- **Out of scope / Non-goals:** a fifth roadmap artifact (deliberately not built, decided 2026-10-08); concerns beyond the three named; a closed vendor vocabulary; a narrative-evidence defect class or any approval block on stack content; judging choice quality; Integration's HTML review aid, which follows separately in Integration; regenerating existing accepted versions.
- **Allowed behavior changes:** the constraints stage authors stack rows and records an open concern instead of inventing a choice; first-run output, `INDEX.md`, and candidate review display the stack; stack rows become feedback targets.
- **Allowed reorganization:** none beyond the stated outcome.
- **Verification:** a Integration-brief replay records the deployment platform as open and every required concern as chosen or open; first-run output and `INDEX.md` list open concerns separately; a candidate that opens, adds, or changes a stack row shows the delta in review; a version without the collection reads as "stack not recorded" and an unrelated candidate in that lineage is not refused for the absence; a stack row is feedback-targetable and revisable through a candidate; existing hosting gates and candidate-review evidence stay green.
- **Stop / defer:** surface a stack concern the collection cannot express or a conflict with an accepted hosting or store choice without inventing one; route unrelated defects separately.
- **Approach:** plan-tool.
- **Route:** `plan` · **Readiness:** `ready` · **Tier:** `architect`. **Principle:** `write-for-the-human`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Seed:** `plan-seeds/archive/roadmap-stack-layer.replaced.md`; plan `docs/implementation-plans/2-roadmap-stack-layer.md`.
- **Origin:** Integration roadmap review, 2026-10-08: the brief's "no AWS account or specific service is fixed yet" left no trace in the accepted roadmap, whose root version (hand-enrolled 2026-09-21) never passed candidate review. Follows the shipped `## Stack` seed section; the Integration HTML review aid is brought up to date after this lands.

```bash
plan-tool create roadmap-stack-layer --iterate -y --from-existing plan-seeds/roadmap-stack-layer.md
plan-tool completeness-audit roadmap-stack-layer --iterate -y
plan-tool detail roadmap-stack-layer --commit -y
plan-tool completeness-audit roadmap-stack-layer --iterate --commit -y
plan-tool run roadmap-stack-layer --commit -y --step N
plan-tool reconcile-code roadmap-stack-layer --all
```

**#462 — Audit every plan derived from an accepted roadmap against its settled decisions and against each other, reported in one saved advisory report**

- **What:** The per-plan completeness audit judges one plan against code at HEAD and never reads the accepted roadmap, so a plan that contradicts a settled roadmap decision or stack row, or two plans that each choose their own technology for a store the roadmap says is shared, pass unseen; a roadmap-level cross-plan audit holds the accepted roadmap version as its reference, puts it and every derived plan (optionally every draft seed) in front of one auditor, and saves the conflicts it reports.
- **Effort:** medium; one new read-only audit surface (prompt, invoker seam, report persistence, CLI), plus derived-plan discovery from the roadmap's existing plan rows and seed state.
- **Risks / fallout:** the property is semantic and unobservable, so the surface can grow into a checker; the not-built list below is the fence. Plan-vs-roadmap stack conflicts overlap the per-plan audit, since the shipped `## Stack` section carries the stack into the plan body, so the cross-plan audit's own value rests on what no single-plan audit can see. A shared report read as a verdict trains operators to treat silence as clearance.
- **Dependencies:** the shipped `## Stack` section (the stack rendered into seeds and carried into plan bodies). Independent of #461's completion: a version without a `stack` collection is judged against its hosting and store rows and settled decisions.
- **Outcome:** One command run against an accepted roadmap writes a saved report that names the accepted version id it was judged against, lists every derived plan (and draft seed, when included) it read, and records each conflict the auditor reports between a plan and a settled roadmap decision or stack row, or between two plans.
- **In scope:** a read-only cross-plan audit command over one roadmap slug; resolving the accepted-head version; discovering derived plans from the roadmap's existing plan rows and seed state; an audit prompt carrying the accepted version's settled decisions, stores, hosting rows (and `stack` rows when present), and each derived plan's body and detail files; the saved report and its listing; the invoker seam and its `TESTING.md` neutralization row; `docs/cli/` regeneration; the how-to and `ROADMAP_FORMAT.md` cross-reference.
- **Out of scope / Non-goals:** each of these is deliberately not built, with its reason:
  - a gate, refusal, or blocking state on any finding — the property is semantic ("does this plan contradict that decision"), and a check firing on prose with no runnable remedy is the refused shape in `CLAUDE.md` § "Validating a semantic property you cannot observe"; deliver, don't verify;
  - an exit-code flip or a new `--fail-on-findings` path — the exit-code convention holds: a completed audit exits 0 with findings;
  - a deterministic technology-name comparison (matching `PostgreSQL` against `SQLite` strings) — it measures vocabulary, not the property, misses a plan that names no product or a synonym, and a high false-positive proxy is killed, not tuned;
  - a new roadmap artifact or a fifth roadmap stage file — decided 2026-10-08 under #461; the report is a saved audit report outside the roadmap's versioned store and never enters a roadmap version;
  - auto-applying findings — `completeness-apply` is being retired (#376); whoever drives the plan reads the report and edits through that plan's own audit loop;
  - rewriting plans, seeds, or the roadmap — the audit is read-only; a conflict whose resolution changes an accepted decision goes through the roadmap feedback lifecycle;
  - feeding `is_blocking_finding`, `is_blocking_impact`, `should_continue`, or any per-plan convergence state — the report is a separate advisory channel;
  - judging plan quality, completeness, or ordering beyond conflicts with the reference or between plans;
  - plans derived from a different roadmap or from none, including cross-roadmap collisions in one repository.
- **Do-not-reopen decisions:** conflict-surfacing was cut from the `## Stack` seed work on 2026-10-08 because it tried to check a semantic property, and contradiction checks for a single plan belong to the per-plan completeness audit; this entry does not move them back into seed materialization or `create`/`detail`. The binary observable is the report's existence with the version id and the list of plans read; nothing past that is asserted.
- **Allowed behavior changes:** a new read-only command and the saved report it writes; nothing else changes for existing commands.
- **Allowed reorganization:** none.
- **Verification:** with a stub invoker, the command against a fixture roadmap writes a report naming the accepted version id and every derived plan, the prompt carries the settled decisions, store and hosting rows, and each plan body, the run exits 0 with findings present, and no file under the roadmap folder, `plan-seeds/`, or the plans changes (asserted by a before/after tree comparison); a two-plan fixture choosing different engines for one shared store carries both plans and the store row into one prompt. Real-model behavior on Integration `integration-aidlc-mvp` is observed separately and gates nothing.
- **Stop / defer:** stop if derived-plan membership cannot be read from the roadmap's existing records without a new link record; surface rather than invent one. Stop if, with `## Stack` carried into plan bodies, the per-plan audit reports every observed conflict, since the cross-plan surface then has no case of its own. Route unrelated defects separately.
- **Approach:** plan-tool; a new audit surface with its own prompt, persistence, and CLI crosses modules and defines what an audit reports.
- **Route:** `plan` · **Readiness:** `evidence-gated` · **Tier:** `architect` (it defines a new audit surface and what it may assert, where a wrong call is invisible because the report checks plans against themselves). **Principle:** `converge-on-correct-plan`.
- **Evidence gate:** executable once one accepted roadmap lineage shows a conflict that a per-plan completeness audit passes clean with `## Stack` carried into the plan body: two derived plans contradicting each other, or a plan contradicting a settled decision that the `## Stack` section does not carry into the plan body. Closing with "no action" is a valid outcome.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Seed:** none until the evidence gate is met.
- **Origin:** Integration owner request, 2026-10-08. Premise checked read-only on 2026-10-08 against Integration (`<integration-consumer-root>`) and found exactly one conflict:
  - **The one conflict (plan vs. roadmap):** the accepted version (`57e2912e…`, matching the working copy) declares `store-app-db` relational/pool with `product: PostgreSQL` (`roadmaps/integration-aidlc-mvp/03-components.md:20-23`) under settled `decision-shared-database` (`:134-141`); `2-connector-registry-seed.md:47` persists to "the shared SQLite database" while its own Architecture names only `store-app-db` with no product (`:78`). The plan was uncommitted, and its details folder held only `grounding.json`, so no per-plan audit had run.
  - **Draft seeds:** all six cite `store-app-db` by id; none names a database product, hosting product, or language, and none contradicts another or the roadmap.
  - **Plan vs. plan within the roadmap:** none possible; `connector-registry-seed` was the only plan derived from `integration-aidlc-mvp`.
  - **Outside this entry's reference:** `2-workspace-membership-selection.md` derives from the separate `project-workspace-membership-proof` roadmap, defers its store product (`:224`), and creates `pyproject.toml` with a `src/integration/` layout (`:22-23`) where the connector plan creates a flat `integration/` package (`:33-35`); that cross-roadmap collision is not a stack-decision conflict and is out of scope here.
  - The SQLite case is within the `## Stack` section's reach once the stack is carried into the plan body, so it does not yet show a conflict only a cross-plan audit can see; hence `evidence-gated`.
- **Evidence update (2026-10-10):** Integration now has nine plans derived from `integration-aidlc-mvp`. Their bare per-plan audits surfaced three plan-vs-plan conflicts. Each was seen from one side only, as a side effect of the auditor reading a sibling plan (reports under Integration `docs/implementation-plans/plan-details/<plan>/reports/`):
  - `step-completion-and-handoff` `20261010-004244` `[next-step-availability]`: "`workflow-catalog-core` owns `workflow-run` progress and `current_step`, while this plan owns handoff availability", with no transition boundary between them.
  - `chat-output-streaming` `20261010-010406` `[repository-reference-status-ordering]`: chat-output-streaming says `repository-browse-and-reference` depends on it, while repository-browse says it consumes the chat path, "so no status supplier exis[ts]".
  - `cdk-infrastructure-and-environments` `20261010-012102` `[fargate-executable-artifact]`: the CDK plan provisions Fargate engine execution but excludes application-artifact delivery, and `isolated-engine-worker` plans its image only in step 10.
  These conflicts were caught by per-plan audits, so the gate as worded ("a per-plan audit passes clean") is not met. Coverage was incidental, though: the counterpart audit did not report any of them, and some correctness findings were grounded on a stale roadmap copy (BUG_BACKLOG "Roadmap-derived plans cite bare `0N-*.md` names…"). Whether incidental one-sided detection is enough is the decision this entry's gate now needs.
- **Evidence update (2026-10-10, later the same day):** the per-plan loop
  could not converge on the between-plan contracts. Through audit rounds 6-9
  of `isolated-engine-worker`, `step-completion-and-handoff`,
  `repository-browse-and-reference`, `cdk-infrastructure-and-environments`,
  and `bitbucket-deployment-pipelines`, findings sat on contracts shared by
  two plans: the terminal-report producer and its consumer, an
  observation-sequence schema claimed by two plans, the `read_file` result
  shape, and the deployment role against the image registry. A fix in one
  plan reopened the counterpart's finding in the next round. Only a
  coordinated edit across the affected plans converged (Integration commits
  `17c28ca` and `40e1d89`, which settle the deployment-role and registry
  contract in the cdk and pipelines plans together). Three checks the
  cross-plan surface makes that no single-plan audit can: producer and
  consumer agree on one interface, no two plans' `files:` create lists claim
  the same path, and a closed vocabulary shared by two plans is defined once.
  This is the "conflict a per-plan audit passes clean" the gate asks for, in
  the sense that matters: each side's audit passes its own half while the pair
  disagrees.

- **Evidence and routing update (2026-10-15):** the bounded
  [Integration handoff record](docs/evidence/integration-roadmap-to-plan-handoff.md) adds a
  static seam replay (7 of 14 baseline items flagged) and a later layer-map/probe
  result that changes transport composition. A shared incorrect layer premise
  is not itself a between-plan conflict this item can detect. #492 owns that
  composition investigation; #493 owns any new context delivery. Preserve this
  entry's evidence gate and no-new-quality/ordering/gating fence; do not mark it
  ready solely because another per-plan audit needed manual coordination.

- **Owner decision (2026-10-15):** retain the existing evidence gate and
  `evidence-gated` readiness; no seed or implementation proceeds. The cited
  Integration audits detect the recorded cross-plan conflicts. Coordinated fixes
  demonstrate a resolution problem, not an additional detection capability.
  Use #492's shared contract record and coordinated session-directed edits for
  that case. Revisit this item only with a concrete case showing what its
  additional report catches or resolves that those existing routes cannot;
  changing the current gate requires a separate explicit owner decision.

**#464 — Twelve test assertions pin a line break inside a prompt or doc sentence, so rewrapping that text with no word changed fails the suite**

- **What:**
  - 12 assertions in 4 test files match a phrase containing a hard line break
    taken from hard-wrapped prose:
    - `tests/test_create.py:16872`
    - `tests/test_roadmap_candidate_run.py:1642`, `:1856`, `:1907`, `:1909`,
      `:1941`, and `:2000`
    - `tests/test_roadmap_format.py:544`, `:547`, and `:549`
    - `tests/cli/test_inspect_cmds.py:704` and `:706` (against `CLAUDE.md`)
  - This contradicts the rule the repository already states at
    `tests/test_roadmap.py:889-895` (`_flattened`): "a rewrap that changes no
    words must not redden a check".
  - Count method: a search over `tests/` for quoted literals containing
    `[a-z,;:\`)]\n[a-z\`(]` followed by ` in `. Structural line breaks were
    then excluded: heading-then-body, fenced blocks, paragraph boundaries, and
    multi-line record bodies. Those are `tests/test_concept_sync.py:177` and
    `:193`, `tests/test_jira.py:956` and `:974`, `tests/test_create.py:11508`,
    `:15767`, `:15783`, `:15801`, and `:15802`,
    `tests/test_roadmap_revision_patch.py:672-673`, and
    `tests/cli/test_roadmap_cmd.py:6908`. Those excluded assertions pin
    structure, not wrapping, and stay.
- **Why:** a no-word rewrap fails a test, and the fix that comes naturally is
  restoring the old wrap rather than correcting the test. Observed 2026-10-08:
  the step-2 hand fix of `roadmap-stack-propagation` was "restoring a pinned
  prompt line break" (`b77efc10`) for `tests/test_create.py:16872`.
- **Effort:** small. The same edit at 12 named sites.
- **Risks / fallout:** none expected. The flattened phrase still pins the words
  and their order.
- **Dependencies:** none.
- **Outcome:** each of the 12 assertions passes against its text rewrapped with
  no word changed.
- **In scope:** the 12 assertions, which compare a whitespace-collapsed phrase
  with whitespace-collapsed text.
- **Out of scope / Non-goals:**
  - Consolidating the whitespace normalizers that already exist in several test
    files (`tests/test_roadmap.py:889`, `tests/test_roadmap_feedback_format.py:91`,
    `tests/test_data_contract.py:840`, `tests/test_detail.py:1144`,
    `tests/test_roadmap_format.py:354`). That is consolidation without
    machine-verified identity evidence.
  - Changing the 12 structural assertions listed above.
  - A lint or guard test against new line-break pins: a matcher over string
    literals measures vocabulary.
  - Rewrapping any prompt or doc.
- **Allowed behavior changes:** none (tests only).
- **Allowed reorganization:** none.
- **Verification:** before the change, rewrap one pinned sentence per file in a
  scratch copy and confirm the assertion goes red. After the change, confirm it
  stays green and the full suite passes.
- **Stop / defer:** an assertion whose line break is structural, rather than
  wrapping, stays as it is, with the reason stated in the commit message.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `beginner`.
  **Principle:** `none` (test hygiene, and no principle is served directly).
- **Start here:** the 4 test files above.
- **Precedent:** `_flattened` at `tests/test_roadmap.py:889-895` and its uses at
  `:1316`, `:1409`, `:1416`, and `:1545`.
- **Settled decisions to respect:** assert keys, not words, where a key exists
  (`CLAUDE.md` § "Tests"). Changes to `CLAUDE.md` need `architect` review, but
  `tests/cli/test_inspect_cmds.py` only reads `CLAUDE.md`, so this item does not
  edit it.
- **Done when:** the 12 assertions compare flattened text, the scratch-rewrap
  check passes, and the full suite passes.
- **Reviewer:** unassigned.
- **Arc assignment:** none. Test hygiene that fits no arc's stated scope.
- **Origin:** `roadmap-stack-propagation` step 2 hand fix, observed 2026-10-08.
  The count was taken on 2026-10-08.

**#465 — Two step 6 tests of the stack callout are absent: a per-site print test and a behavioral "stack content adds no approval refusal" test — optional, low value**

- **What:**
  - `tests/cli/test_roadmap_cmd.py` pins the five candidate-review print sites
    only by counting `_print_candidate_stack_callout(` calls in the source of
    `roadmap_cmd.py`, and an autouse fixture stubs the callout out of every
    other test. No test shows each of proposal, review, answer, structural
    approve, and structural edit/reject printing the callout after
    `narrative evidence:`, a callout failure leaving a command's return code at
    its no-callout baseline, or structural approve keeping its digest and codes
    for a stack-bearing candidate.
  - `tests/test_roadmap_candidate_review.py` pins "stack content adds no
    approval refusal" only by grepping the source of
    `roadmap_candidate_narrative.py` and `roadmap_candidate_review.py` for the
    callout names, so a behavioral change making approval depend on stack
    content would stay green.
- **Why:** `reconcile-code` sweep 1 on `roadmap-stack-layer` (2026-10-08) raised
  both as 2 medium findings against step 6's detail. The callout is display
  only, so neither gap hides a known defect; the existing tests already fail if
  a print site is dropped or added without a callout, and if the callout raises.
- **Effort:** medium. End-to-end CLI fixtures for five commands, in a suite that
  stubs the callout elsewhere on purpose.
- **Risks / fallout:** brittle output-pinning tests over display text, which
  `CLAUDE.md` § "Validating a semantic property you cannot observe" warns
  against; the value is mostly ordering (callout after the evidence) and the
  approval-independence guarantee.
- **Dependencies:** none; `roadmap-stack-layer` has shipped.
- **Outcome:** either the two behavioral tests exist and fail when the callout
  moves before the evidence or when approval reads stack content, or this entry
  is deleted with the reason that the structural tests are enough.
- **In scope:** the two named test files.
- **Out of scope / Non-goals:**
  - Changing the callout, its wording, or where it prints.
  - Un-stubbing the autouse fixture for other tests.
  - Any gate, refusal, or exit-code behavior keyed on stack content
    (deliberately not built: the callout never blocks approval).
  - Assertions on callout prose beyond the row ids and the `open` marker
    (assert keys, not words).
- **Allowed behavior changes:** none (tests only).
- **Allowed reorganization:** none.
- **Verification:** break the code each test names (print the callout before the
  evidence; make approval refuse on an opened stack row) and confirm the test
  goes red, then restore it and run the full suite.
- **Stop / defer:** if the fixtures need more than the existing
  `tests/cli/test_roadmap_cmd.py` helpers, delete this entry rather than build
  new harness.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `beginner`.
  **Principle:** `none` (test depth for a display feature).
- **Start here:** `tests/cli/test_roadmap_cmd.py`
  `test_every_narrative_evidence_print_site_also_prints_the_stack_callout`, and
  `tests/test_roadmap_candidate_review.py`
  `test_stack_callout_is_not_wired_into_approval_or_narrative_evidence`.
- **Settled decisions to respect:** the stack callout is display only and never
  a defect class or an approval gate (decided 2026-10-08 under #461).
- **Done when:** the two tests exist and pass with their mutation checks, or the
  entry is deleted with its reason.
- **Reviewer:** unassigned.
- **Arc assignment:** none. Test depth that fits no arc's stated scope.
- **Origin:** `roadmap-stack-layer` `reconcile-code` sweep 1, 2026-10-08, step 6.

**#468 — Give roadmap retries the rejected proposal so they can correct specific defects**

- **What:** the second `plan-tool roadmap <slug> --propose-candidate` call
  receives the original batch context plus a rejection reason, but not the
  preceding rejected proposal. Give it that exact response as untrusted repair
  context so it can correct named defects while retaining the valid work.
- **Evidence:** `_build_candidate_delta_prompt` appends only
  `correction_reason` and requests one complete replacement JSON object;
  `_propose_batch_candidate` does not pass the first response into that prompt.
  Integration run `2026-10-09T12-33-44+00-00-796f4c` sends 303,959 bytes in call 1
  and 304,221 in call 2, while the rejected response is 68,210 bytes.
  Calls take about 535 and 451 seconds. The retry fixes the stack collection placement but
  still fails graph gates. A second run with
  explicit correction feedback repeats dependency-order failures.
  This is one consumer observation, not a latency benchmark or proof that
  repair context alone guarantees convergence.
- **Effort:** medium — proposal retry context, prompt assembly, bounds, and
  invoker tests; retain the current response parser and materializer.
- **Risks / fallout:** rejected model output is untrusted; extra context can
  increase token cost, reproduce bad operations, or distract from the issued
  receipt. A model may still change valid operations, so the existing complete
  admission checks remain authoritative.
- **Dependencies:** none open. The added-plan ordering defect and the ordering
  diagnostics it depended on were both fixed 2026-10-09; a forward ordering
  reference now reaches the retry as a named cycle.
- **Outcome:** a bounded second proposal attempt receives the exact preceding
  rejected response and safe complete diagnostics under the same issued batch
  and receipt, enabling specific correction without reconstructing the proposal
  from the original context alone.
- **In scope:** `plan_tool/roadmap_candidate_run.py` batch proposal loop and
  prompt builder, its prompt template/context boundary, existing response
  capture/digest evidence, and focused invoker/admission tests.
- **Out of scope / Non-goals:** more retry attempts or longer timeouts; automatic
  approval or promotion; gate relaxation; changing accepted versions or feedback;
  repairing unrelated engine commands; a generic patch/merge language; a new
  candidate writer; model selection; terminal progress (#433); review-aid
  presentation or the held Integration renderer transfer.
- **Allowed behavior changes:** only the repair context of the existing bounded
  second call. It still returns one complete candidate JSON object through the
  existing parser and admission path; malformed output remains refused.
- **Allowed reorganization:** none beyond threading that repair context through
  the existing batch proposal invocation.
- **Verification:** with a stub invoker, return one deliberately invalid proposal
  containing otherwise valid operations, assert call 2 includes the exact first
  response and every safe reported defect with unchanged batch/receipt, then
  return a corrected full response and assert admission. Keep the two-attempt
  limit, untrusted-data boundaries, current failure evidence, and stale receipt,
  broadened authority, and invalid replacement refusals. Observe a Integration replay
  separately; do not assert a semantic success rate or wall-clock reduction.
- **Stop / defer:** surface context-size limits before selecting a truncation or
  projection policy; do not silently drop part of the repair evidence. If a new
  partial-delta wire or persistence contract is required, scope it as a separate
  design decision rather than extending this entry.
- **Approach:** direct — one bounded input-context extension using the existing
  complete-response contract; escalate to a plan if a new repair wire is chosen.
- **Route:** direct · **Readiness:** parked — efficiency follow-up · **Tier:** architect.
  **Principle:** `converge-on-correct-plan`.
- **Status:** not started; efficiency follow-up.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** Integration owner requested these plan-tool updates on 2026-10-09.

**#471 — Intern repeated relation node identities in the roadmap candidate context**

- **What:** represent `relation_evidence` owner/endpoint objects as indices
  into a node table instead of repeating them per edge, under a new context
  schema version with the current reader retained.
- **Evidence:** on the Integration payload in
  `docs/evidence/integration-context-budget-2026-10-09/`, 93 unique nodes across 262 relationships;
  the relation section drops from 58,841 to about 33,420 bytes and the whole
  payload from 211,712 to about 186,290, with an exact round-trip (reproduced
  2026-10-09 from `docs/evidence/integration-context-budget-2026-10-09/`). No model
  readability measurement exists.
- **Trigger to un-park:** per-call cost or latency of roadmap candidate
  proposals becomes a measured problem after the 384 KiB ceiling shipped (PR #58),
  or a context approaches that ceiling. Without one, the byte saving alone does not justify a new
  model-facing representation.
- **Risks:** changes capsule identity for new contexts and the shape the model
  reads; index indirection can make relationships harder for the model to
  interpret. Assess readability separately from byte round-trip.
- **Out of scope / Non-goals:** rewriting stored capsules; dropping any
  relationship field or order.
- **Route:** direct · **Escalate to plan if:** the model-readability check
  needs a replay harness. · **Readiness:** parked · **Tier:** architect.
  **Principle:** `deterministic-non-determinism`.
- **Status:** not started.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** split on 2026-10-09 from the context-ceiling entry (shipped, PR #58).

**#472 — Learn a Claude model's context window before its first call**

- **What:** a Claude window is known only from a call's result envelope, so the first send of a process
  measures against the 200,000 default, and the selected run-reconcile refusal gate, which excludes windows
  learned mid-run, never leaves the default on Claude. Add a pre-call source that is local and
  deterministic: the `[1m]` suffix of the selected model id (a declaration, not process history).
  Deliberately not the `model_specs` catalog cache: it exists only when a caller passes `cache_path` and
  expires after `max_age_s`, so it is absent on a fresh machine and differs between machines.
- **Evidence:** with the shipped window resolution, a 605 KB roadmap prompt on a 1,000,000-token Claude model still prints `high` with
  `(default)` on its only send, and a selected run-reconcile prompt of that size is refused at 200,000
  (`docs/ARCHITECTURE.md` § "Prompt-budget window"). Whether the suffix is a reliable signal for every
  1M-window Claude model is not measured.
- **Outcome:** once the readiness gate confirms the suffix, a Claude model whose id declares a 1,000,000-token window is measured against it from the
  first send, by the advisory and by the selected run-reconcile refusal gate, with no `(default)` marker.
- **In scope:** `plan_tool/context_window.py` (a pre-call Claude source), the refusal gate in
  `launcher.run_step` (the suffix is deterministic, so the gate may use it), and tests with a stubbed source.
- **Out of scope / Non-goals:** a network fetch in the advisory path; exact token counting; Codex (its
  catalog already supplies the window).
- **Allowed behavior changes:** a suffixed Claude model measures against its declared window from the first
  send; an unsuffixed model, and every Codex path, are unchanged.
- **Stop / defer:** if the suffix is not a reliable signal for every 1M-window Claude model, stop and file
  what the real runs showed; do not guess a window from the family name.
- **Verification:** with a `[1m]`-suffixed model selected, the first advisory and the refusal gate measure
  against 1,000,000 and print no `(default)`; an unsuffixed model is unchanged.
- **Route:** direct · **Readiness:** evidence-gated (confirm the suffix against a real run first) ·
  **Tier:** experienced. **Principle:** `deterministic-non-determinism`.
- **Quality:** `gate-signal` — the advisory and the gate stop judging a 1M-window model against 200,000.
- **Status:** not started.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** deferred follow-up from the model-aware prompt-budget code review (2026-10-09).

**#476 — Convert the legacy `Approach:` tag to Route/Readiness in one mechanical pass and guard it with a presence test**

- **What:** two label vocabularies coexist. `BACKLOG.md` has 204
  `- **Approach:**` lines and 41 `- **Route:**` lines; `BUG_BACKLOG.md` has
  47 and 18. `docs/TRACKING.md:99-101` teaches readers to map the older
  `Approach:` tag onto Route. `:129-131` says "Label an entry when you next
  touch it. No bulk pass over the untouched entries", because
  keyword-style bulk *sizing* misjudged tiers.
- **Outcome:** every live entry carries `Route:`. The mapping from
  `Approach:` is mechanical (`direct` → `direct`, `plan-tool` → `plan`, and
  a conditional → `direct` plus `Escalate to plan if:`), so it is not the
  sizing judgment that rule refused. A test fails on any live entry without
  `Route:`.
- **In scope:** Route conversion in `BACKLOG.md` and `BUG_BACKLOG.md`;
  narrowing TRACKING.md's no-bulk-pass rule to Tier and Readiness; a
  presence test beside `tests/test_backlog_ids.py`.
- **Out of scope / Non-goals:** bulk-assigning Tier or Readiness. That is
  deliberately not done, because it is the judgment the existing rule
  protects.
- **Verification:** no live entry lacks `Route:`, and the new test fails on
  a fixture entry without it.
- **Stop / defer:** stop at any `Approach:` value the mapping cannot
  classify, and list those entries for hand triage.
- **Route:** direct · **Readiness:** decision-needed (the lead confirms the
  no-bulk-pass rule may be narrowed to Tier and Readiness) ·
  **Tier:** beginner.
- **Status:** not started.
- **Origin:** tracking-process review, 2026-10-10.

**#477 — Give `BUG_BACKLOG.md` entries stable ids so code and tests cite them by id instead of by title**

- **What:** `docs/TRACKING.md:756-757` says "`BUG_BACKLOG.md` entries are
  titled headings with no id", and `tests/test_backlog_ids.py` deliberately
  skips that file. Code therefore cites bugs by title or not at all: there
  are 23 `BUG_BACKLOG` mentions under `plan_tool/`, three of them a bare
  "See BUG_BACKLOG." with no title (`create.py:11787`,
  `data_contract.py:631`, `review.py:1776`). Two title citations no longer
  resolve, and only git history says why: `tests/test_launcher.py:2784`
  cites "`run` advances a step whose `creates:`…", an entry removed when the
  bug was fixed (`4fc168027`); `completeness_report.py:1293` cites "The
  persisted report withholds ``suggested_action``", fixed in `72de18d29`,
  a title no backlog file has ever carried. Both are stale citations of
  fixed bugs, to be cleaned up with the rest. A title is not a stable
  reference, because titles change and fixed entries are deleted.
- **Outcome:** each `BUG_BACKLOG.md` entry carries a stable id with its own
  prefix (for example `B-N`), code and tests cite that id, and the id guard
  covers it.
- **In scope:** ids on the live bug entries, the TRACKING.md rule,
  extending `tests/test_backlog_ids.py`, and rewriting the existing
  citations under `plan_tool/` and `tests/`.
- **Out of scope / Non-goals:** checking that a cited id is still live
  (removed entries stay cited from history, as in `BACKLOG.md`), and
  renumbering `BACKLOG.md`.
- **Verification:** the id test fails on a duplicate bug id, and no
  `BUG_BACKLOG "<title>"` citation remains under `plan_tool/` or `tests/`.
- **Stop / defer:** stop if promotion stubs (`docs/TRACKING.md` §
  "Promotion stubs") need a different id form; decide that before
  numbering.
- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Status:** not started.
- **Origin:** tracking-process review, 2026-10-10.

**#478 — Separate tracking guidance from the catalog and split the backlog catalog by area**

- **What:** `BACKLOG.md` is 12,943 lines, `docs/TRACKING.md` is 1,095, and
  `BUG_BACKLOG.md` is 1,849. Guidance (rules, recipes, label tables) is
  mixed in with the catalog, so a reader or a session loads most of a file
  to find one entry or one rule, and duplicated guidance drifts (the TRACKING.md recipe skipped the bare-plan audit until 2026-10-10).
- **Outcome:** a decision on whether to split. If yes, guidance lives only
  in TRACKING.md and the directives, and the catalog is split by area (for
  example by arc assignment) with an index. Ids, the id test, and
  promotion stubs keep working across the split.
- **In scope:** the decision, and the split once it is approved.
- **Out of scope / Non-goals:** the entry format and the labels (#476,
  #477).
- **Verification:** the id test sees every split file, and every existing
  `BACKLOG.md#…` link still resolves or is rewritten.
- **Stop / defer:** stop if the readability guard
  (`tests/test_backlog_readability.py`) or external Jira links depend on a
  single file.
- **Route:** plan · **Readiness:** decision-needed · **Tier:** architect.
- **Evidence gate:** before splitting, measure whether sessions currently
  fail to find entries or rules (missed duplicates, misapplied recipes).
  Closing with "no action" is a valid outcome.
- **Status:** not started.
- **Origin:** tracking-process review, 2026-10-10.

**#484 — Mark each completeness finding that a plan edit since the previous audit introduced, so fix-induced scope growth is visible**

- **What:** the audit reports findings without lineage, so a finding against
  surface the previous round's fix added reads the same as a defect in what
  the plan always promised. A loop can then chase a widening scope while each
  round looks like new evidence of an unsound plan.
- **Evidence:** a Integration fix added a deployment-role construct to
  `cdk-infrastructure-and-environments`. The next round produced 8 new HIGH
  findings across that plan and `bitbucket-deployment-pipelines`, all on the
  new construct (Integration reports under
  `plan-details/<plan>/reports/20261010-*-completeness.md`).
- **Effort:** medium; the previous audit's committed snapshot is already the
  re-audit baseline, so the work is a diff-to-finding attribution and its
  rendering.
- **Risks / fallout:** attribution from a text diff to a finding is a
  judgment; a wrong "fix-induced" mark could teach operators to dismiss a
  real defect.
- **Dependencies:** none.
- **Outcome:** a re-audit's report marks each finding whose cited plan
  region changed since the previous audit's snapshot, and states the count of
  marked findings beside the total.
- **In scope:** the completeness report and its JSON sidecar; the console
  summary line.
- **Out of scope / Non-goals:** suppressing, demoting, or excluding a marked
  finding from the blocking set; changing the stopping rule (#125).
- **Allowed behavior changes:** the new mark and count only.
- **Allowed reorganization:** none.
- **Verification:** a fixture with two audits around an edit that adds one
  section asserts that findings citing the new section are marked and others
  are not.
- **Stop / defer:** stop if a finding's cited region cannot be located in the
  plan text without inferring from prose; surface that rather than guess.
- **Approach:** plan-tool; it adds an audit report field and an attribution
  rule.
- **Route:** plan · **Readiness:** ready · **Tier:** experienced.
  **Principle:** `converge-on-correct-plan`.
- **Quality:** `convergence` — separates fix-induced growth from real
  non-convergence.
- **Status:** not started.
- **Origin:** Integration `integration-aidlc-mvp` nine-plan roadmap-to-plan run, 2026-10-10.

**#485 — Let a plan record a deliberate departure from an accepted roadmap row, so the audit stops re-reporting a decision the owner already made**

- **What:** when the owner decides mid-run against an accepted roadmap row,
  the plan has no structured way to say so. Every audit re-reports the
  contradiction at the same severity until the roadmap itself changes.
- **Evidence:** in Integration the owner chose "engine reports revision identity",
  contradicting the accepted row "`component-workflow-catalog` supplies
  revision identity". Gate 1 reported `[revision-identity-ownership]` HIGH in
  two consecutive rounds (`chat-output-streaming` `20261010-041508` and
  `-041509`), although the plan states the departure in prose and a roadmap
  feedback item was filed (Integration `BACKLOG.md` #2).
- **Effort:** medium; a plan frontmatter field, its validation, and audit
  prompt handling.
- **Risks / fallout:** an unchecked departure list becomes a way to silence
  any finding; each record must cite a real roadmap row and an open feedback
  item.
- **Dependencies:** #462 reads the same records when it judges plans against
  settled decisions.
- **Outcome:** a plan's `deliberate_departures:` entry naming the roadmap row
  and the feedback item id turns the matching contradiction finding into a
  reported, non-blocking "recorded departure" line.
- **In scope:** `PLAN_FORMAT.md`, the plan schema, `validate` (the row and the
  feedback item must resolve), and the completeness audit prompt and report.
- **Out of scope / Non-goals:** changing the roadmap, the feedback lifecycle,
  or any finding not about the cited row.
- **Allowed behavior changes:** the new field and the recorded-departure line.
- **Allowed reorganization:** none.
- **Verification:** a fixture plan with a departure record against a fixture
  roadmap row gets the recorded-departure line and no blocking finding; the
  same plan without the record gets the finding; a record citing a missing
  row or feedback id fails `validate`.
- **Stop / defer:** stop if matching a finding to a record needs prose
  inference instead of the cited row id.
- **Approach:** plan-tool; it adds a plan-format field the audit honors.
- **Route:** plan · **Readiness:** decision-needed · **Tier:** architect.
  **Principle:** `converge-on-correct-plan`.
- **Quality:** `gate-signal` — a settled owner decision stops reading as an
  open defect.
- **Status:** not started.
- **Origin:** Integration `integration-aidlc-mvp` nine-plan roadmap-to-plan run, 2026-10-10.

- **Authority decision still open (2026-10-15):** Integration's recorded owner
  decisions and native feedback ids are additional evidence, not automatic
  permission to suppress any contradiction. Decide how a record proves the
  owner's scope and distinguishes a pending departure from a promoted roadmap
  change before marking this entry ready. #490 owns finding dispositions;
  #493 only threads approved context and must not implement this entry's
  departure semantics. See the [handoff evidence](docs/evidence/integration-roadmap-to-plan-handoff.md).

**#486 — Say in `detail`'s description and console output that it runs a completeness audit and saves a report**

- **What:** `detail` runs a completeness audit after authoring and writes a
  report under `plan-details/<plan>/reports/`. `detail --help` states this
  only under `--no-completeness`, and the run does not announce it. Integration
  operators found the reports only by listing the reports folder during the
  2026-10-10 roadmap-to-plan run.
- **Effort:** small; help text, one console line, and the directive.
- **Risks / fallout:** none beyond help-text golden tests.
- **Dependencies:** none.
- **Outcome:** `detail --help`'s description and the run's console output
  both name the audit and the saved report path.
- **In scope:** `detail`'s argparse description, its post-authoring console
  output, `docs/cli/` regeneration, and `integrations/shared/DIRECTIVES.md`.
- **Out of scope / Non-goals:** changing whether `detail` runs the audit.
- **Allowed behavior changes:** the added text only.
- **Allowed reorganization:** none.
- **Verification:** a help test and a console-output test assert the text.
- **Stop / defer:** file anything else found as a separate entry.
- **Approach:** direct.
- **Route:** direct · **Readiness:** ready · **Tier:** beginner.
  **Principle:** `write-for-the-human`.
- **Status:** not started.
- **Origin:** Integration `integration-aidlc-mvp` nine-plan roadmap-to-plan run, 2026-10-10.

**#487 — Audit infrastructure-as-code plans only against resources the plan defines the creation of, and name the rest as exceptions**

- **What:** an infrastructure plan always runs on resources its own code does
  not create (the toolchain's bootstrap stack, account-level services, managed
  roles). The audit has no rule for them, so it reports their stock behavior
  as a defect in the plan, and a fix then either wraps the stock resource in
  a mechanism the plan does not own or claims isolation the plan cannot
  deliver.
- **Evidence:** Integration `cdk-infrastructure-and-environments` rounds 12-17: the
  audit reported that the stock CDK bootstrap roles (including the lookup
  role's account-wide read access) and `ecr:GetAuthorizationToken` on `*` break
  per-environment isolation. Both are the toolchain's or the service's own
  pattern, not something the plan defines. The owner ruled both an explicit,
  named exception (2026-10-10) and gave the general rule: a plan makes
  scoping and isolation claims only for resources whose creation pattern it
  defines; resources the toolchain creates and needs to operate are out of
  scope and stated as such.
- **Effort:** small to medium; a directive and a Gate 2 prompt clause, plus an
  audit-report field listing the plan's declared exceptions.
- **Risks / fallout:** an exception list can hide a real gap; the list must be
  explicit, each entry carrying its reason, and visible in the report.
- **Dependencies:** none.
- **Outcome:** an infrastructure plan lists its out-of-scope toolchain
  resources with a reason each, and the audit judges isolation, scoping and
  least-privilege claims only against resources outside that list.
- **In scope:** the directives text; the detail-grounded audit prompt; the
  completeness report's rendering of declared exceptions.
- **Out of scope / Non-goals:** deciding which resources a given toolchain
  creates; relaxing checks on resources the plan does define.
- **Allowed behavior changes:** findings against a declared exception are
  reported as informational, not blocking.
- **Allowed reorganization:** none.
- **Verification:** a fixture plan declaring the stock bootstrap roles as an
  exception produces no blocking finding for them, and a fixture claiming
  isolation over an undeclared toolchain resource still does.
- **Stop / defer:** stop if a declared exception covers a resource the plan's
  own code creates.
- **Approach:** plan-tool directives plus audit prompt.
- **Route:** plan · **Readiness:** ready · **Tier:** experienced.
  **Principle:** `converge-on-correct-plan`.
- **Quality:** `precision` — removes defects that no plan edit can close.
- **Integration-side use:** the same rule belongs in Integration's own audit and review
  guidance, since Integration will audit infrastructure plans for its users. The
  per-technology record of out-of-scope items is started in Integration at
  `docs/technology-shapes/` (CDK first); plan-tool consumption of such an
  index is a follow-up to this entry.

**#488 — Route a failed `run` step's stated reason to roadmap feedback, and list failure receipts never routed anywhere**

- **What:** a `run` step that stops on an upstream gap now records why, in a
  `model_failure_receipt` whose sidecar holds the executor's final reply
  (`reason: no-edits-applied`, shipped 2026-10-13). Nothing carries that reason
  to the roadmap feedback ledger, where an upstream gap belongs, and nothing
  shows which receipts were never acted on.
- **Why:** the gap goes back to the roadmap only if someone notices the receipt
  and retypes it as `roadmap --submit-feedback`. AI-DLC's construction loop
  treats this as a first-class move: a failure jumps back to the stage that owns
  the gap as a logged event, and recovery checks for a failure logged but never
  routed (`aidlc-workflows` `core/aidlc-common/protocols/stage-protocol-recovery.md`).
- **Evidence:** Integration, 2026-10-11 to 10-13: 22 declined `run` attempts across 12
  steps in four plans; every captured executor reason was a missing upstream
  contract or a blocked prerequisite, each routed back by hand. Record:
  Integration `docs/experiments/integration-cli-simulation/2026-10-13-declined-step-executor-messages.md`.
- **Effort:** medium. Plan frontmatter carries no roadmap provenance, so which
  roadmap and target a receipt belongs to has to be supplied or decided.
- **Risks / fallout:** the reply is unfiltered model output
  (`DATA_CONTRACT.md` § `ModelFailureReceipt`); copying it into a tracked
  ledger file publishes it. The request text must be the operator's, or the
  reply only after the same credential withholding Integration applies.
- **Dependencies:** none in plan-tool. Integration `BACKLOG.md` #5 (show the owner why a
  step stopped) is the consumer and lands first.
- **Outcome:** an operator turns one failure receipt into one open roadmap
  feedback item that names the receipt it came from, and can list the failure
  receipts no feedback item names.
- **In scope:** a `roadmap` feedback-submission path that takes a run id and step
  as the item's source reference; the listing of unrouted receipts (`plan-tool
  runs` or a `roadmap` read); the feedback item's source field; tests.
- **Out of scope / Non-goals:** choosing the roadmap target automatically;
  deciding whether the executor was right to stop; retrying the step; routing to
  anything other than the roadmap ledger; changing candidate proposal or
  approval.
- **Allowed behavior changes:** a new submission form and a new read; a
  feedback item may carry a source reference.
- **Allowed reorganization:** none.
- **Verification:** a fixture run with a `no-edits-applied` receipt, submitted
  against a named roadmap target, produces an `open` item whose source names the
  run and step; the unrouted listing shows the receipt before submission and
  not after; the full suite passes.
- **Stop / defer:** if binding a receipt to a roadmap needs plan provenance in
  plan frontmatter, file that as its own entry and ship with an operator-supplied
  roadmap slug and target.
- **Route:** `direct`; escalate to plan if a frontmatter provenance field is
  needed · **Readiness:** `ready` · **Tier:** `experienced`.
  **Principle:** `converge-on-correct-plan`.
- **Arc assignment:** `backlog-arc-roadmap` (adjacent to `backlog-arc-run-gates`,
  which shipped the receipt it consumes).
- **Origin:** comparison with `aidlc-workflows`' feedback model, 2026-10-13.

**#489 — Record who decided a structural roadmap approval or a decision settlement, as stated by the caller**

- **What:** `--decide-candidate … --confirm-stack-digest` proves the confirming
  caller saw that exact stack; it records nothing about who decided. A script and
  an operator confirm identically by design, so an agent can approve its own
  structural candidate and the seal reads the same as a human's approval.
- **Why:** Integration exists to put roadmap decisions in front of the run owner, and
  needs plan-tool's record to show whether an approval was the owner's or an
  agent's on their behalf. AI-DLC requires a recorded human turn after a gate
  opens, written by the harness hook that talks to the person, and stores the
  person's own words beside the agent's summary (`aidlc-workflows`
  `core/aidlc-common/protocols/stage-protocol.md`). The layer facing the person
  vouches; the engine checks only that the record exists.
- **Effort:** small to medium: one required field on the confirm and settlement
  responses, carried onto the `structural-approval` seal and the decision
  record.
- **Risks / fallout:** a required field breaks existing scripted confirms until
  they pass it. Plan-tool cannot authenticate the claim, and must not present it
  as verified.
- **Dependencies:** none to build. **Trigger:** Integration's `roadmap_driver.py` begins
  relaying an owner's approval into `--decide-candidate`; land this before that
  driver work.
- **Outcome:** every structural approval and decision settlement records a
  decider kind (`human` or `agent`) and a caller-supplied reference, and a
  confirm without one is refused.
- **In scope:** the confirm (`--confirm-stack-digest`) and settlement
  (`--respond-decision-settlement`) arguments; the seal and decision record
  fields (`roadmap_candidate_review.py`); the matching run-log context;
  `ROADMAP_FEEDBACK_FORMAT.md`; tests.
- **Out of scope / Non-goals:** verifying the claim (identity, TTY detection,
  signatures); policy such as "structural approvals need a human", which belongs
  to the caller; ledger item submission; non-roadmap surfaces.
- **Allowed behavior changes:** a confirm or settlement response without a
  decider is refused.
- **Allowed reorganization:** none.
- **Verification:** an approve with `human` and a reference produces a seal
  carrying both; one with `agent` does too; one with neither is refused with no
  write; the full suite passes.
- **Stop / defer:** if the seal's stored identity cannot take a new field without
  a schema version, ship the field on the run-log event only and file the seal
  change.
- **Route:** `direct` · **Readiness:** `blocked-on` the trigger above ·
  **Tier:** `architect` (changes an approval contract).
  **Principle:** `deterministic-non-determinism`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** comparison with `aidlc-workflows`' feedback model, 2026-10-13;
  owner direction that Integration facilitates human decisions rather than hiding them.

**#490 — Let an operator record a decision on an audit finding, and show it to the next audit so it is not re-raised**

- **What:** a completeness or reconcile finding that the operator declines,
  accepts as a known risk, or reopens has that decision recorded only in a
  handoff doc. The next audit cannot see it and re-reports the finding, so
  settled decisions get re-argued round after round.
- **Why:** CLAUDE.md's "do not re-open" rules and the convergence exits depend on
  a session remembering prose. AI-DLC records a per-finding human disposition in
  its ledger (accepted risk on approve, an explicit rejection carrying the
  person's exact reason, an explicit reopen) and states "never infer either
  decision from generic revision feedback"
  (`aidlc-workflows` `core/aidlc-common/protocols/stage-protocol-reviewer.md`).
- **Evidence:** the `no-edits-applied` review (2026-10-13,
  `handoffs/2026-10-13-no-edits-applied-code-review.md`) re-stated its declined
  items in every reviewer prompt by hand so later rounds would not re-raise them.
- **Effort:** medium: a disposition store keyed by stable finding identity, a
  command to record one, and the audit prompt and report reading it.
- **Risks / fallout:** a declined finding hides a later real regression at the
  same identity; a disposition must go stale when the finding's evidence or the
  cited text changes.
- **Dependencies:** stable finding identity across audit rounds (already used by
  the convergence diagnostics).
- **Outcome:** a finding the operator declined or accepted, with a reason, is
  shown to the next audit as settled and is not reported as new while its cited
  text is unchanged.
- **In scope:** a disposition record (`declined`, `accepted-risk`, `reopened`,
  each with a reason); the command that writes one; the completeness-audit
  prompt and report rendering; staleness on a changed cited text; tests. If #489
  ships first, the record carries its decider field.
- **Out of scope / Non-goals:** inferring a disposition from an edit or from
  review prose; changing blocking or exit behavior; dispositions for roadmap
  feedback items, which the ledger already owns; `/code-review`, a session
  activity outside the tool.
- **Allowed behavior changes:** the audit report shows settled findings
  separately and does not count them as new.
- **Allowed reorganization:** none.
- **Verification:** a fixture finding declined with a reason is not reported as
  new on the next audit of unchanged text, and is reported again once its cited
  text changes; the full suite passes.
- **Stop / defer:** if stable finding identity does not hold across rounds for
  the finding classes in scope, file that and stop.
- **Route:** `plan` · **Readiness:** `ready` · **Tier:** `experienced`.
  **Principle:** `converge-on-correct-plan`.
- **Arc assignment:** `backlog-arc-convergence-evidence`.
- **Origin:** comparison with `aidlc-workflows`' feedback model, 2026-10-13.

- **Evidence update (2026-10-15):** Integration's shared proposal keeps explicit
  contributor/owner decisions and finding destinations to avoid repeated
  arguments. This supports supplying dispositions to later review, not inferring
  them from a generic approval or overriding a settled roadmap. This entry stays
  owned by `backlog-arc-convergence-evidence`; #492's route only consults it.

**#492 — Decide what shared application evidence roadmap-derived plans need before authoring**

- **What:** define the smallest shared composition handoff that helps a driving
  session derive executable increments from an accepted roadmap, existing code
  and demonstrated integration boundaries. Determine whether existing references
  suffice before proposing new tool inputs.
- **Effort:** medium; a bounded architect investigation over one existing
  project and the named authoring/audit consumers, not implementation of a new
  workflow engine.
- **Evidence:** [Integration handoff evidence](docs/evidence/integration-roadmap-to-plan-handoff.md)
  records cross-plan contract churn, a layer-assignment error that survived
  individual plan audits, and a probe that changed the transport decomposition.
  Those observations motivate investigation; they do not measure savings.
- **Risks / fallout:** turning a useful shared record into another large design
  phase, interpreting observed code as approved contract, or making an
  unobservable feasibility judgment into an execution gate.
- **Dependencies:** the existing roadmap plan rows and immutable accepted-head
  reads; source evidence above. No dependency on an AI-DLC upgrade or new live
  probes. Inspect #490, #485, #262 and #403 to avoid duplicate ownership.
- **Outcome:** one reviewed design record identifies the minimum shared input,
  its source/version authority, and whether `create`, `detail` and
  `completeness-audit` need new support, with an explicit build/use-existing/no-action
  disposition for each follow-on. The observable is that record and its named
  consumer decisions, not a certified good decomposition.
- **In scope:** application journey and layer ownership; critical provider and
  consumer obligations, including required fields and behavior; versioned
  evidence and unresolved questions; pointers to full outcome coverage; bounded
  increment composition; existing-code versus approved-intent distinctions;
  compatibility treatment for projects without shared context. Start with two
  sections (ownership/authority and critical contracts/evidence) plus outcome
  references and unresolved decisions; add views only when a decision needs them.
- **Out of scope / Non-goals:** new CLI commands, schemas or persisted versions;
  implementing #493, #462, #494, #490, #485 or #484; a fifth roadmap artifact;
  rewriting accepted roadmaps; automatic splitting, blocking or semantic
  validation; a full inventory unrelated to the selected journey; treating CLI
  names as complete contracts; Integration product/runtime changes or live model probes.
- **Allowed behavior changes:** none; this investigation produces a design
  decision and proposed follow-on scopes only.
- **Allowed reorganization:** none.
- **Verification:** trace the selected Integration journey from approved outcome to
  responsible layer, relevant contract, available evidence and proposed increment.
  Include an unresolved provider question and an extension to an existing
  interface. Review whether existing source references already carry the needed
  information. The record names evidence limits and each follow-on disposition;
  no synthetic example or report silence is claimed as proven feasibility.
- **Stop / defer:** close with use-existing/no-action if no missing tool-side
  delivery is demonstrated. Unresolved product choices stay with their owner.
  If one consumer needs shared lifecycle/schema authority, separate that contract
  before authoring an implementation seed; do not absorb it into the study.
- **Approach:** plan-tool investigation; the design determines the later feature
  boundaries. No implementation seed until its scope and decisions are settled.
- **Route:** `plan` · **Readiness:** `evidence-gated` · **Tier:** `architect`.
  **Principle:** `converge-on-correct-plan`.
- **Arc assignment:** `backlog-arc-roadmap`, roadmap-to-plan subroute.
- **Stage arc (single authority for this group):**
  1. #492 decides the minimum handoff and per-consumer need. Tool state is unchanged.
  2. #493 delivers only approved shared-context inputs and provenance to the
     closed consumer set. Existing projects without context keep their behavior.
  3. #462 supplies its separate saved advisory cross-plan conflict report. This
     is the preferred evaluation order, not a new hard dependency on #493;
     #462 may proceed independently if its own evidence gate is met.
  4. #494 adds a read-only prerequisite view only if #492 and current operator
     evidence establish a distinct status-reporting need. It changes no run gate.
  Consult #490 through its convergence-evidence arc for finding dispositions,
  and resolve #485's authority question before relying on departure records.
  #484's reporting work is independent. Later seeds wait for their inputs; they
  cite this arc rather than reauthoring it. Evaluate shared-context/audit value
  before adding selective re-auditing or assisted automatic composition.
- **Status:** closed 2026-10-15 — the reviewed record at
  `docs/explanations/roadmap-plan-handoff.md` identifies the accepted-head
  authority, separates the remaining provider question from settled owner decisions,
  and records `use-existing` for `create`, `detail`, and `completeness-audit`.
- **Seed:** `plan-seeds/archive/roadmap-plan-handoff-investigation.replaced.md`. Proposed later seed names, only if approved:
  `roadmap-plan-handoff-01-shared-context` for #493 and
  `roadmap-plan-handoff-02-prerequisite-view` for #494.
- **Origin:** Integration owner request, 2026-10-15, after the roadmap-to-plan pilot
  and joint approach review. Recording the route is not approval to implement it.

**#493 — Supply selected shared application context to plan authoring and completeness audits**

- **What:** if #492 establishes missing delivery, make the approved shared
  composition record visible to `create`, `detail` and `completeness-audit`
  with its selected source and revision, without asking each plan to restate it.
- **Effort:** medium; bounded input/provenance threading through three consumers
  and their tests. Representation and admission rules depend on #492.
- **Risks / fallout:** stale or silently substituted context, ambiguous input
  authority, duplication of roadmap decisions or #490 dispositions, and unwanted
  changes to existing projects. A context reference is not proof its prose is true.
- **Dependencies:** #492's reviewed build decision, input contract and
  compatibility treatment. #490/#485 are related owners, not implicit features
  this entry may implement. Follow #492's stage arc.
- **Outcome:** each named consumer receives exactly the operator-selected
  shared context admitted under the approved contract, and its saved provenance
  identifies that source/revision. This observable input delivery, not semantic
  quality or reduced audit count, is the feature.
- **In scope:** the approved source-reference and provenance representation;
  `plan_tool/create.py`, `plan_tool/detail.py`, completeness prompt assembly
  and the corresponding owning input/format code only where the accepted design
  needs it; closed-set prompt threading, supported round trips and documentation.
  Include missing/changed-source outcomes and explicit refresh/reselection rules
  from #492; never silently substitute a new source at the same path.
- **Out of scope / Non-goals:** #462's cross-plan report; #494's prerequisite
  view; new semantic gates, quality judgments, prose agreement checks or shape/
  length caps; changing `run`, Jira or roadmap publication; new decision stores;
  marking roadmap conflicts resolved; selective audit caching; rewriting plans
  or sources automatically; rollout to additional consumers because they cannot
  see the input. No persisted field/schema change before #492 selects it.
- **Allowed behavior changes:** only selected-context delivery, its recorded
  provenance and the source-admission outcomes explicitly settled by #492.
  Commands and projects without that context retain existing behavior.
- **Allowed reorganization:** none unless the approved design demonstrates a
  specific ownership blocker; file any broader reorganization separately.
- **Verification:** neutralized-invoker tests inspect all three final prompt
  inputs and saved provenance against the selected source; cover absent context,
  missing/changed source, explicit reselection and unrelated-context isolation.
  If persistence changes, test the approved compatible read/transition and unsafe
  legacy case. Assert no automatic accepted-roadmap or shared-record writes.
  Real-model usefulness is an observation, never a passing semantic assertion.
- **Stop / defer:** use existing references or close with no action if #492
  finds no missing consumer delivery. If the chosen representation requires an
  unsettled lifecycle or migration, resolve that design before implementation.
- **Approach:** plan-tool after #492; later seeds inherit this fence and the
  settled context contract instead of selecting competing representations.
- **Route:** `plan` · **Readiness:** `evidence-gated` · **Tier:** `architect`.
  **Principle:** `converge-on-correct-plan`.
- **Arc assignment:** `backlog-arc-roadmap`, roadmap-to-plan subroute.
- **Seed:** none until #492 settles the handoff and build decision.
- **Origin:** Integration roadmap-to-plan evidence and owner direction, 2026-10-15.

**#494 — Show a plan's recorded unresolved prerequisites separately from its execution progress**

- **What:** if a distinct need is demonstrated, extend read-only `status`
  output to show recorded dependency/evidence/input obligations beside the
  existing progress state, so `current` is not mistaken for proven readiness.
- **Effort:** medium; approved input reads and one status projection, with
  explicit legacy behavior. No execution-policy engine.
- **Evidence:** Integration's discovery marked all remaining work blocked, although
  step 7 was not downstream of the blocked bindings in the declared graph.
  Its own provider inputs and later owner-selected sequence still mattered.
  This demonstrates the need to distinguish facts; it does not validate an
  inferred universal ready/blocked classifier.
- **Risks / fallout:** advisory output becoming de facto permission to run,
  semantic inference silently changing state, and duplication of #403's
  installation doctor, #262's detail-authoring advisory or #175's Jira lane.
- **Dependencies:** #492's readiness-information decision and selected source
  contract; #493 only if it delivers information the projection actually needs.
  Verify current `status` capabilities before selecting new output. Follow #492's
  stage arc; do not introduce an artificial dependency on #462's model verdict.
- **Outcome:** one `status` read preserves ordinary progress and identifies
  each explicitly recorded unresolved prerequisite with its source/revision,
  responsible owner or decision reference, and missing/unavailable evidence.
  Unspecified information is shown as unknown, never inferred satisfied.
- **In scope:** `plan_tool/cli/inspect.py:cmd_status` / `_print_status` and their
  owning input readers as confirmed during design; reads of shared-context and native
  dependency facts; an advisory, non-mutating projection and its documentation.
- **Out of scope / Non-goals:** automatic ready/blocked semantic judgments;
  new persisted step statuses; modifications to the scheduler, `run` admission,
  completion, dependency graph, audit blocking predicates or exit conventions;
  doctor or Jira changes; source/record writes; materializing deferred plans;
  executing probes, resolving owner decisions or manufacturing missing evidence.
- **Allowed behavior changes:** the selected advisory `status` information
  only; no additional execution authority. Existing projects without the new
  input keep their progress behavior and report evidence as unavailable where
  the approved display requires it.
- **Allowed reorganization:** none.
- **Verification:** fixture reads keep a current step current while listing its
  recorded missing input; distinguish a satisfied graph edge from an outstanding
  owner input, unrelated blocked work and unknown/stale context. Assert unchanged
  progress, no writes, unchanged scheduler/run decisions and output compatibility
  for existing projects under the approved representation.
- **Stop / defer:** close with no action if current status plus existing
  evidence references meet the need. Stop before implementation if truthful
  rendering requires unselected semantic policy or a new authority store.
- **Approach:** plan-tool after the evidence and input design are settled.
- **Route:** `plan` · **Readiness:** `evidence-gated` · **Tier:** `architect`.
  **Principle:** `deterministic-non-determinism`.
- **Arc assignment:** `backlog-arc-roadmap`, roadmap-to-plan subroute.
- **Seed:** none until #492 establishes the distinct need and representation.
- **Origin:** Integration roadmap-to-plan pilot, 2026-10-15.

**#516 — Decide which seed files directory-wide annotate includes**

- **What:** directory input to `annotate` recursively includes Markdown beneath
  seed directories, except `.seed.md` and `archive/` files. The nested seed
  directory already contains existing briefs; new default outputs add roadmap,
  scope-out and reground briefs plus an explanatory README to that traversal.
- **Outcome:** a documented owner decision defines whether those files belong
  in directory-wide annotation, with tests for the selected behavior.
- **In scope:** annotate directory expansion and its input-selection docs.
- **Out of scope / Non-goals:** seed migration, default placement, publication
  ownership and changing explicitly supplied file-path inputs.
- **Allowed behavior changes:** only the directory-selection rule the owner
  selects; do not silently classify this as a new default-placement regression.
- **Allowed reorganization:** none.
- **Verification:** directory fixtures distinguish plans, briefs, README,
  generated `.seed.md`, archives and explicit file selection.
- **Stop / defer:** settle inclusion policy before changing filters; file other
  output or classification changes separately.
- **Route:** direct · **Readiness:** decision-needed · **Tier:** experienced.
- **Origin:** seed-default review 3, 2026-10-22; advisory about a pre-existing
  recursive traversal, not evidence of data loss or a failed publication gate.

---

## Public onboarding and release candidates

These candidates retain clone plus editable `uv` installation. Existing arcs own
their lanes; `backlog-arc-public-release` coordinates the release sequence.

**#508 — Separate portable skill guidance from repository team policy**

- **Route:** direct · **Readiness:** ready · **Tier:** architect.
- **Principle:** write-for-the-human.
- **Arc assignment:** `backlog-arc-installed-skill`.
- **Effort:** small–medium.
- **Outcome:** Installed guidance works in a consuming repository without assuming this
  project’s organization, Jira keys, reviewer roles, or publication policy.
- **In scope:** Shared directives and all three skill routers; preserve this
  repository’s applicable policy in repository-owned developer guidance.
- **Out of scope / Non-goals:** New workflow rules, tracker configuration, automatic
  publication, or absorbing #378/#379 convention discovery.
- **Allowed behavior changes:** Relocate local policy and generalize examples without
  weakening this repository’s approval requirements.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no
  unrelated restructuring.
- **Verification:** Review the installed guidance from an unrelated consuming repository
  and verify local policy remains reachable. Changes to CLAUDE.md require architect-tier
  review.
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

**#509 — Configure the consuming repository Git hosting provider and remote**

- **Route:** plan · **Readiness:** ready · **Tier:** architect.
- **Principle:** write-for-the-human.
- **Arc assignment:** `backlog-arc-installed-skill`.
- **Effort:** medium.
- **Outcome:** A driving session selects GitHub or Bitbucket for the consuming
  repository through a defined configuration reader and verifies its PR target.
- **In scope:** Automatic detection from the selected remote; explicit provider override
  for custom hosts; configured remote with origin as the default;
  repository/default-branch resolution; gh/bkt target verification and ambiguous-target
  handling.
- **Out of scope / Non-goals:** A hosting plugin framework, automatic publishing,
  history rewriting, or coupling provider choice to Jira/team policy.
- **Allowed behavior changes:** Introduce the smallest repository configuration and
  assistant-facing reader needed for provider selection; preserve explicit publication
  authorization.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no
  unrelated restructuring.
- **Verification:** Cover GitHub/Bitbucket SSH and HTTPS remotes, explicit custom hosts,
  alternate remotes, ambiguous inputs and mismatched CLI context with hermetic tests.
  Inspect CLI help before backend lifecycle commands.
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

**#510 — Make onboarding skill-first with one bounded first-task walkthrough**

- **Route:** direct · **Readiness:** blocked-on #508 · **Tier:** experienced.
- **Principle:** write-for-the-human.
- **Arc assignment:** `backlog-arc-operator-workflow`.
- **Effort:** medium.
- **Outcome:** A new user installs the tool and skill, requests a small plan, and
  reviews it before implementation.
- **In scope:** Short README entry path, explicit assistant choices, prerequisites,
  sample request, expected artifacts and review points; retain direct CLI routing and
  link deeper reference material.
- **Out of scope / Non-goals:** A whole documentation rewrite, new pipeline rules,
  package publishing, or making roadmap a required first task.
- **Allowed behavior changes:** Change navigation and examples only; retain clone plus
  uv tool install --editable . as the supported installation method.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no
  unrelated restructuring.
- **Verification:** Walk the instructions in a consuming repository; check links and
  command examples. Complete #377 seed-authoring support before calling the walkthrough complete.
  The recipe-consistency prerequisite is satisfied by the
  [skill-router repair](handoffs/2026-10-21-skill-router-recipes-code-review.md).
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

**#511 — Explain skill installation, refresh and the next action**

- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Principle:** write-for-the-human.
- **Arc assignment:** `backlog-arc-installed-skill`.
- **Effort:** small.
- **Outcome:** Users understand where the skill is installed, how it updates, and what
  to do after installation.
- **In scope:** Destination, user/project scope, copy/symlink behavior, refresh command,
  and next action in setup guidance and installer success output; distinguish driving
  assistant from execution backend.
- **Out of scope / Non-goals:** Automatic updates, new installation modes, dependency
  provisioning, or redesigning the installer.
- **Allowed behavior changes:** Bounded installer success messaging and setup
  documentation; preserve existing destination and overwrite semantics.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no
  unrelated restructuring.
- **Verification:** Check success output for Claude, Codex and Cursor installations and
  copy/symlink variants using existing installer tests; verify refresh examples against
  command help.
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

**#512 — Explain backend and model choice with cost and evidence**

- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Principle:** write-for-the-human.
- **Arc assignment:** `backlog-arc-installed-skill`.
- **Effort:** small–medium.
- **Outcome:** Users can choose a backend/model and understand recommendations,
  configuration precedence, reasoning effort and cost limits.
- **In scope:** One authoritative explanation, linked from onboarding and routers:
  driving assistant versus subprocess backend versus model; Sol for Codex stages and
  Opus creation/Sonnet subsequent Claude work; explicit flags versus inherited defaults;
  reasoning-effort/token consumption and API versus subscription billing; date and
  source price comparisons.
- **Out of scope / Non-goals:** Automatic model routing, a pricing service, a benchmark
  framework, or claims of equal quality/task cost from equal token prices.
- **Allowed behavior changes:** Documentation only; reconcile stale Terra
  recommendations without changing runtime defaults. Explain why creation errors
  compound and distinguish measured evidence from owner-selected recommendations.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no
  unrelated restructuring.
- **Verification:** Check claims against backend resolution and current official
  provider documentation. Pricing baseline verified 2026-10-19: standard GPT-6.1 Sol and
  Sonnet 5.5 each list $2 input/$10 output per million tokens; reverify before
  publication. Sources: https://developers.openai.com/api/docs/models/gpt-6.1-sol and
  https://platform.claude.com/docs/en/models/sonnet-5-5/overview .
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

**#514 — Set the public distribution, license and history boundary**

- **Route:** direct · **Readiness:** ready · **Tier:** architect.
- **Principle:** write-for-the-human.
- **Arc assignment:** `backlog-arc-public-release` (release prerequisite).
- **Effort:** small–medium.
- **Settled decisions:** Apache-2.0 (owner choice, 2026-10-19); public GitHub
  repository with ongoing internal Bitbucket sync; clone plus editable uv
  installation. Owner decision, 2026-10-20: use
  `https://github.com/rupe120/plan-tool` (currently private, owner-reported),
  possibly transferring to the Protagona organization later. Start public history
  with one fresh sanitized root shared by Bitbucket and GitHub. Maintain the same
  ancestry on both hosts and reconcile changes locally in one designated clone.
  License file and package declaration are present. Publication, transfer and remote changes remain
  separate actions. Future sync uses the shared sanitized base; do not merge
  pre-snapshot branches into it.
- **Outcome:** A reviewed release decision names the license, accessible source URL,
  supported installation/update path and public Git-history boundary.
- **In scope:** Retain clone plus uv editable install; retain Apache-2.0, choose the exact public HTTPS
  source and release-tag/main guidance; explain keeping the clone, dependency refresh
  and copied-skill refresh; prepare the selected fresh sanitized snapshot and
  inspect it for client material and credentials. Define shared-base synchronization
  from either host through a designated integration clone. Draft guidance lives in
  `docs/how-to/install-and-update.md` and `docs/RELEASING.md`; final candidate and
  destination verification remain open.
- **Out of scope / Non-goals:** PyPI publishing, automatic updates, publication, remote
  changes, credential rotation or history rewriting without separate authorization.
- **Allowed behavior changes:** Decision and documentation/package metadata only;
  the publication/history boundary requires an explicit owner decision.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no
  unrelated restructuring.
- **Verification:** Check clean install and upgrade instructions against the chosen
  source strategy; record history-scan scope and unresolved findings. Working-tree
  sanitization alone cannot certify existing history.
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

**#515 — Verify public onboarding in a fresh consuming repository**

- **Route:** direct · **Readiness:** blocked-on #510 · **Tier:** experienced.
- **Principle:** write-for-the-human.
- **Arc assignment:** `backlog-arc-operator-workflow`.
- **Effort:** medium.
- **Outcome:** The supported onboarding path works outside the developer’s local
  configuration, with concrete failures fixed or filed.
- **In scope:** Fresh clone/editable installation, authenticated backend prerequisites,
  each supported skill install/discovery path, seed authoring, bare audit, detail and
  detail audit on one small change; expected progress/artifacts, interruption guidance,
  and stop before implementation.
- **Out of scope / Non-goals:** Product benchmarking, unattended publication, new
  workflow gates, exhaustive backend qualification or absorbing unrelated defects.
- **Allowed behavior changes:** Verification and bounded documentation corrections only;
  file runtime defects separately.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no
  unrelated restructuring.
- **Verification:** Record environment, commands, assistant/backend/model, observations
  and limitations. Require #377 and #508–#514 to be
  resolved or explicitly dispositioned before public onboarding sign-off. The
  recipe-consistency prerequisite is satisfied by the
  [skill-router repair](handoffs/2026-10-21-skill-router-recipes-code-review.md); missing
  credentials remain an explicit coverage gap.
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

---

## Adding a new entry

The rules for this live in [`docs/TRACKING.md` § "Adding a new entry"](docs/TRACKING.md#adding-a-new-entry).
`BACKLOG.md` keeps no copy, so the two cannot drift apart.

---

## Scope contract and anti-creep

The rules for this live in [`docs/TRACKING.md` § "Scope contract and anti-creep"](docs/TRACKING.md#scope-contract-and-anti-creep).
`BACKLOG.md` keeps no copy, so the two cannot drift apart.

---

## Architectural map

The rules for this live in [`docs/TRACKING.md` § "Architectural map"](docs/TRACKING.md#architectural-map).
`BACKLOG.md` keeps no copy, so the two cannot drift apart.

---

## How to author a new plan

The rules for this live in [`docs/TRACKING.md` § "How to author a new plan"](docs/TRACKING.md#how-to-author-a-new-plan).
`BACKLOG.md` keeps no copy, so the two cannot drift apart.

---

## Useful commands

The rules for this live in [`docs/TRACKING.md` § "Useful commands"](docs/TRACKING.md#useful-commands).
`BACKLOG.md` keeps no copy, so the two cannot drift apart.

---

## See also

- [`MISSION.md`](MISSION.md) — the five grounding principles this file's
  priority bands rank against.
- [`integrations/shared/DIRECTIVES.md`](integrations/shared/DIRECTIVES.md) —
  canonical directives for *driving* plan-tool from any assistant session.
- [`CLAUDE.md`](CLAUDE.md) — directives for developing plan-tool itself,
  including the audit-the-why shapes an apply loop must clear first.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module-by-module description
  of what ships.
- [Lessons learned](docs/explanations/lessons-learned.md) — design-level insights from prior
  work; several are load-bearing constraints, not advice.
- [`TESTING.md`](TESTING.md) — unit vs. integration convention and the
  invoker-neutralization table.
- [Backlog decisions](docs/history/backlog-decisions.md)
  — closed entries and settled decisions, so a closed id stays citable.
- [`docs/implementation-plans/`](docs/implementation-plans/) — authored plans,
  in-flight and archived.
