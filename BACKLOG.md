# Plan-tool feature backlog and triage

## Purpose

**Naming.** "Integration" in this repository names an external application that consumes `plan-tool`. Paths and commits cited for it, such as `<integration-consumer-root>`, belong to that application's own repository and are not in this one. Entries that mention it are kept as dated provenance.

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
- **Read the entry's Route label.** Each entry's `Labels:` line carries a
  **Route** (`direct` or `plan`; a conditional route is `direct` plus an
  `Escalate to plan if:` bullet) that pre-resolves the
  direct-implement-vs-plan-it-first question. An older **Approach:** field,
  where one remains, describes the method only; the Route label decides. The
  route is a recommendation, not a contract — if you disagree, the
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
  **Arc assignment** names `backlog-arc-roadmap`. A plan-tool finding that an
  external consuming application surfaces is an ordinary entry, and the lead can
  promote it unless it is roadmap-owned. See [`docs/TRACKING.md`](docs/TRACKING.md#roadmap-boundary).
- **Add new candidates** as they surface. A useful entry has at
  minimum: a one-line description, an effort estimate, the main
  risks or test-fallout you'd hit, any blocking dependencies on
  other items, and a **Route** label picking `direct` or `plan`
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
  through the bounded consumers that rely on them. Its items (#242,
  #208, the structured-upstream group #383–#384, and #385) are untiered —
  this arc is their sole router. #384's implementation and review tail are
  complete; #383 is held until a named stage lacks essential grounded facts
  (see its Status). The
  roadmap-to-plan subroute's #492 is closed (use-existing; see
  `docs/history/backlog-decisions.md`); #493 and #494 are discarded (see the same record);
  existing #462 retains its own advisory-audit scope.
- [`backlog-arc-installed-skill.md`](docs/implementation-plans/backlog-arcs/backlog-arc-installed-skill.md)
  — what an installed Claude Code/Codex/Cursor skill gives a driving session
  before it has to find the answer itself: the thin router/shared-reference
  split, skill trigger fields, seed authoring, and out-of-scope/stale-entry
  backlog capture. Public onboarding additions #508/#509/#511/#512 also route
  here. Its items (#377, #378; #379 is merged into #378) are untiered — this arc is
  their sole router; #371 (skill frontmatter trigger fields) also shipped
  from this arc, 2026-09-17. #443 (`DIRECTIVES.md` beside the tracked
  skill) and #444 (quote the routers' `argument-hint`) shipped 2026-10-06.
- [`backlog-arc-driver-contract.md`](docs/implementation-plans/backlog-arcs/backlog-arc-driver-contract.md)
  — what an unattended driver can read from `plan-tool` without inferring it:
  the result of `create`/`detail`, a refused `create`, a plan's gate verdict,
  per-finding triage labels, and run usage totals. Its items (#499, #502)
  are untiered — this arc is their sole router; #504 and #385 stay with
  `backlog-arc-roadmap`.
- [`backlog-arc-run-gates.md`](docs/implementation-plans/backlog-arcs/backlog-arc-run-gates.md)
  — what happens around a `run` step's gates: the prompt before it finishes,
  what a retry sees, the outcome a failed step reports, and what the gates
  observe. Its items (#454–#459) are untiered — this arc is their sole router;
  #87 stays routed elsewhere (#88 is merged into #455).

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

**Project runbooks** — *(none)*. A project runbook would be a live operational
playbook for driving one specific external project through `plan-tool`, not a
priority router. The only one, for an external consuming application, was
removed on 2026-11-05 when the repository went public; that application's
findings are filed as ordinary entries in the owning backlog file.

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
the `Route` label). Omit the field on entries that don't (pure
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

- **grounding:** **#38** (reconcile precision — detail-write annotation + `review` pre-filter),
  **#312** (ground `detail` authoring in fetched reference-doc content
  instead of a bare link list), **#30** (verify plan against developer-doc
  links; detail-level half depends on #312), **#208** (a parked
  `roadmap` framework-lens route — a framework lens replaces an inferred
  quality-attribute vocabulary with an external one, so constraint coverage
  becomes checkable rather than plausible), **#291** (the seed-materialization
  prompt states the greenfield case explicitly, so empty-repo seeds stop
  carrying invented file references into `create`), **#271** (stage 4 steers
  a greenfield roadmap's first plan toward the runnable substrate later
  plans' verification presumes).
- **audit-coverage:** **#66** (contract-trace / path-enumeration deterministic
  audit mode — complements the stochastic sampler), **#175** (jira-readiness
  deterministic checks in `jira --lint` / `validate` — HEAD-anchor
  verification and frontmatter↔detail footprint coherence, no model call), and the run-log coverage
  arc **#176** / **#177** (four verbs spend Claude with no log at all;
  `create`'s slug call precedes its own log; an unsinked call now warns once
  per process naming its call site, so the remaining gaps announce themselves),
  **#295** (give `Recommendation` a confidence signal distinct from severity,
  so a shakily-supported finding stops rendering with the same authority as a
  well-grounded one), **#301** (version saved conceptual-audit coverage before
  the next additive field), and **#302** (a table-driven test pins
  rate-limit recovery notification coverage across the loop's arms).
- **convergence:** **#164** (invert the detail
  contract — author at jira grade so a scope change invalidates one paragraph
  instead of a bundle of stale implementation facts; the largest observed
  source of audit churn), **#163** (tell a *folded* guardrail section apart
  from a genuinely dropped one, so the shipped preservation warning does not
  train operators off the channel — evidence-gated, see the entry),
  **#102** (widen deterministic seed-extraction so fewer body sections strand
  as `_(TODO)_` awaiting the stochastic loop), **#156**
  (make the sampler key on the `[out-of-scope-deferred]` tag so a
  scope-bound audit converges instead of grinding on correctly-deferred
  adjacent findings), **#181** (proportionality detection at create time; also
  `heuristic-tuning`),
  **#262** (one static bare-stage report line saying detail-owned remedies are
  expected and `detail` is the next step, so a user advances to the artifact
  that can resolve the remaining implementation contracts rather than
  re-sampling the same plan).
- **gate-signal:** the shipped calibrated impact-aware convergence policy
  (high-impact findings and high/critical severities block; evidence-qualified
  low-impact medium findings may be demoted), the settled four-loop blocking
  boundary (see
  [the backlog decisions record](docs/history/backlog-decisions.md)),
  **#87** (harden the test-authoring gate
  against a dirty working tree), **#472** (a Claude window before the
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
| **Roadmap — Integration** | Replay the prose-only follow-up on candidate c886d0f | The 384 KiB candidate context ceiling shipped (PR #58): the follow-up's 211,712-byte context should now be admitted once this build is installed. The model-aware budget warning shipped (PR #60 and its review follow-up); #472 (a Claude window before the first call) is the next item; #468 (targeted retry) stays parked. Existing ROADMAP bug entries remain tracked. |
| **Next (idle plans)** | `lessons-reuse-instrumentation` (9) · `jira-sweep-deterministic` (9) · `deferred-scan-digest` (11) + `deferred-select-promote` (9) | Authored; execute or explicitly park — don't re-author beside them |
| **Ready seeds** | `premise-ledger` · `audit-shape-saturation-and-provenance` · `audit-shape-advisory-generic-walk` · `walk-advisory-chat-mode` · `completeness-output-quality` · `audit-finding-staleness-classification` · `feature-health-2-attribution-and-ledger` · `lessons-store-restructure` | Keep; `create` only when that lane is the pick. Two more seeds sit on disk but are **blocked**, not ready — `jira-sweep-verify-code-truth` and `deferred-findings-digest`, each on the plan it cites |
| **Blocked** | `detail-verbosity-compact-summary` on a run-grade re-baseline · `deferred-findings-digest` on `deferred-scan-digest` · `jira-sweep-verify-code-truth` on `jira-sweep-deterministic` | A blocked seed on disk is not ready work. |
| **Parked / defer** | Every entry labelled Readiness `parked` carries an `Unpark when:` line; list them with `grep -n 'Unpark when:' BACKLOG.md`. By area — roadmap: #208 (`roadmap-05`, unauthored until a named framework need), #242, #294, #329, #338, #349, #353, #362, #383, #409, #417, #437, #439, #462, #468, #489, #528 · run, audit and convergence machinery: #71, #81, #98, #105, #111, #119, #163, #173, #210, #264, #267, #268, #278, #301, #302, #303, #313, #322, #336, #355, #386, #457, #504 · lessons: #193, #194, #381 · other: #107, #114, #177, #185, #216 (`quality-bench-01`; one disposable observation, only when a named A/B question needs it), #391, #523, #524 · Deferred without the label: `security-check-command` (10 steps, open design issues in-plan), and the Bucket D consolidation #79–#80. | A parked entry is not ready work; its `Unpark when:` line is the only thing that moves it. #353 waits for the narrow normalized-artifact collision correction to stabilize and for explicit selection; #79's claims need re-verification before any merge |

**Authored plans** (manifest; every plan below is `status: planning`):

| Plan | Steps | Disposition |
|---|---|---|
| `lessons-reuse-instrumentation` | 9 | Next — pairs with lessons integrity work |
| `jira-sweep-deterministic` | 9 | Next — export-leg hygiene; `jira-sweep-verify-code-truth` waits on it |
| `detail-verbosity-compact-summary` | 6 | Blocked — re-baseline on run-grade-owned schema authority |
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
  (contract-trace audit mode).
- **T4 — grounding/workflow refinements (P3) + blocked:** **#69**, **#38**,
  **#30**.
- **T5 — export leg / UX / hygiene / cosmetic:** **#107** (deferred pending a demonstrated export blocker), **#102**,
  **#56**, **#89** (`--commit` for
  `reconcile-code`/`reconcile-plan` — observed orphaning gap, see its entry's
  "Evidence it recurs"), and the Bucket D
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
  FP rate measurement), **#210** (keep/cut the purity pass — passive
  observation only; do not schedule a dedicated audit), **#381** (lesson-confidence threshold measurement), plus **#499**
  and **#504** (each `decision-needed`). One more carries a
  **spike-gated front** — theoretical before its concrete build: **#66**
  (validate contract extraction from plan prose). The
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
> has no active T2 feature request. The deterministic-verifiability item
> **#66** sits at T3. Everything else here sits below it.


**#532 — `create --from-existing` refuses a seed that omits a guardrail heading, and accepts one that says `None`**

- **Labels:** Route `plan`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `converge-on-correct-plan`
- **What:** a seed's three author-supplied guardrail headings (`## Scope
  guardrails`, `## Audit guardrails`, `## Expected placement`) are optional
  today, so a seed with no fence and a seed whose author forgot the fence read
  the same. `create` captures each heading verbatim and carries it into
  `detail` and `run` prompts as a hard fence (`scope_fence.py:GUARDRAIL_BODY_SECTIONS`),
  so a missing one silently weakens every later stage. Make all three required
  in a `--from-existing` seed, refused before any model call like a missing
  `## References`, with an explicit `None` accepted as the answer.
- **Evidence:** `create.py:classify_file_backed_source` refuses only a missing,
  duplicate, empty or placeholder `## References`; `create.py`'s
  `OPTIONAL_PLAN_BODY_SECTION_SHAPES` labels the guardrail headings
  "conditional". On 2026-11-14, 2 of 28 live seeds (6 in
  `docs/implementation-plans/plan-seeds/`, 22 in `plan-seeds/`) carried `## Scope
  guardrails` and none carried all three. Four tools write seeds and none
  writes the headings: `roadmap.materialize_plan_seed`,
  `annotate_render.render_create_seed`, `scope_out.render_carved_seed` /
  `render_carved_region_seed`, and `reground.render_rebaseline_seed`.
  `scope_fence._is_placeholder_section` matches only `TODO` forms,
  so `None` already reads as content, not as a placeholder.
- **Effort:** medium. The refusal itself is small; the cost is the producers
  that write seeds, which must populate the headings from what they already
  read, the live-seed sweep, and the docs.
- **Risks / fallout:** every seed written without the headings stops working,
  including tool-written seeds already on disk. A carved or rebaselined seed
  inherits its source plan's fence, which can be wrong for the narrower plan. Test fixtures
  that feed `--from-existing` a minimal seed will go red and need the headings.
- **Dependencies:** none. Lands before the BUG_BACKLOG.md entry "`--commit`
  stages the whole working tree…" goes through `create` (owner ordering,
  2026-11-14).
- **Scope contract:**
  - **Outcome:** `create --from-existing` refuses, before any model call, a seed
    missing any of the three guardrail headings or carrying one that is
    duplicated, empty or a placeholder, and accepts a heading whose body is an
    explicit `None`.
  - **In scope:** the file-backed intake check; a test that an explicit `None`
    survives verbatim into the plan and downstream fence (the fence renderer
    already carries it); the four seed-writing tools populating all three
    headings (`roadmap --materialize` from its prompt; `annotate`, `scope-out`
    and `reground` by copying the source plan's guardrails, with `annotate`'s
    existing call writing them when the source has none, told in
    `prompts/annotate.md` to state only fences the source supports and to add no
    scope, mechanism or requirement, and a deterministic
    renderer writing `_(TODO)_` when its source plan has none); the live seeds
    in both seed directories, populated by hand; `SEED_FORMAT.md`,
    `PLAN_FORMAT.md` § "Scope fence",
    `docs/how-to/pipeline/create-from-existing.md` and `ROADMAP_FORMAT.md`.
  - **Out of scope / Non-goals:** deliberately not the tool-written `## Stack`
    heading, which only `roadmap` writes. Deliberately not `## Outcome` or `##
    In scope`, which have no guardrail capture; requiring them is a separate
    decision. Not inline `--from` or `--from-plan`, which have no seed file to
    hold a heading. Not archived seeds, which are not inputs to a future
    `create`. No new model call in any tool to compose guardrails. No check of what a guardrail says beyond presence: no quality
    judgment, no agreement check with `Out of scope`, no length cap.
  - **Allowed behavior changes:** the new refusal and its message; the four
    seed-writing tools write the three headings, and their printed next steps
    name inherited or unfilled headings.
  - **Allowed reorganization:** none.
  - **Verification:** a seed missing any one heading is refused with no model
    call, naming the heading; a duplicated, empty or `TODO` heading is refused;
    a `None` heading is accepted and appears verbatim in the plan and the
    downstream fence; a seed from each of the four tools passes the check when
    its source carries guardrails; every live seed passes it.
  - **Stop / defer:** a tool that cannot populate a heading from what it
    already reads writes `_(TODO)_` for the operator to fill, never `None` on
    the author's behalf; other discoveries are filed as their own entries.
- **Origin:** 2026-11-14, owner: "I feel that the guardrails are critical to
  plan creation, even if those guardrail designations are specified as none."

**#499 — Audit sidecars record each bare-stage finding's detail-level (D) label**

- **Labels:** Route `plan`
  · Readiness `decision-needed` (the measurement result, and who owns the D label: the audit or the triaging session)
  · Tier `architect`
  · Principle `converge-on-correct-plan`
- **What:** the version-4 completeness sidecar has no field marking a bare
  audit's finding as detail-level (D). The label exists only in the session
  that triages the report. Record the audit's own D classification per
  finding, as a closed boolean-shaped label, after a measurement shows passes
  agree on it.
- **Why:** an external driver cannot verify the directive's normal Gate 1
  exit ("after three bare rounds, proceed to `detail` when the remaining
  findings are D, I, or about text the previous round added"). Integration's
  Construction batch driver therefore asks the owner to confirm that case with
  `proceed`, trusting the session's labels. A recorded D label lets the driver
  check that one arm itself. The other two arms stay human gates: I (settled
  by code or a platform spike) is not one an audit can reliably assign, and
  "about text the previous round added" is a finding's relation to the last
  edit, which an altitude label cannot express.
- **Effort:** medium; the agreement measurement first, then a prompt field,
  the sidecar schema (a version bump in `DATA_CONTRACT.md`), and the parser.
  Lands with #192 (findings carry a step id), which edits the same finding
  record, so the two share one version bump.
- **Scope contract:**
  - **Outcome:** after the agreement measurement passes, each saved
    conceptual finding at the bare stage carries a D-or-not label. The label
    does not decide the I arm or the "about the previous round's text" arm.
  - **In scope:** a label-agreement measurement across audit passes on
    existing bare reports; then the audit prompt's output field, the sidecar
    schema and its version (shared with #192), the reader.
  - **Out of scope / Non-goals:** changing blocking predicates or exit codes;
    auto-routing findings by label; recording a finding's relation to the
    previous round's edit; labelling I, P, R, B or T; deliberately not a
    full altitude label, because a model-judged semantic label consumed by an
    external driver becomes a gate bypass for the arms the audit cannot
    assign.
  - **Allowed behavior changes:** a new sidecar field under a new version,
    only after the measurement.
  - **Allowed reorganization:** none.
  - **Verification:** the measurement records pass-to-pass agreement on the D
    label; then a bare audit of a plan with a known D-level finding saves that
    finding with the D label.
  - **Stop / defer:** if label agreement between passes is too low to be
    useful, record the measurement and stop before any schema bump.
- **Origin:** 2026-10-19, Integration `construction-batch-driver` design and its
  Gate 1 rounds. Cut to a D-only label 2026-11-14.

**#502 — A refused `create` prints a stable reason token an external driver can read**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `deterministic-non-determinism`
- **What:** `create` refuses on the seed paths before it resolves a slug and
  opens its run log, for example when a roadmap-tracked seed's accepted
  version is absent. The run log is keyed by the resolved slug, so those
  refusals have no log to write to, and a later branch-collision decline also
  opens none by design. Print a stable closed reason token on stderr for each
  pre-slug refusal.
- **Why:** the driver that invoked `create` already sees a non-zero exit, so
  "refused" versus "never ran" needs no new persisted location; what it lacks
  is a machine-readable reason. `DATA_CONTRACT.md` does not promise a run log
  for every invocation, so this is a capability gap and not a bug.
- **Effort:** small; one closed token set and one stderr line per pre-slug
  refusal path.
- **Scope contract:**
  - **Outcome:** a `create` refused on a seed path before slug resolution
    prints one stderr line carrying a closed reason token from a documented
    set.
  - **In scope:** the pre-slug seed refusal paths, the token set and its line
    format, `DATA_CONTRACT.md` (the token vocabulary), tests.
  - **Out of scope / Non-goals:** other subcommands (file separately if they
    share the gap); a log for a bad plan name (`detail` deliberately opens no
    ghost JSONL for an unknown name, and `create` keeps the same rule);
    deliberately not a persisted run record or record location, because the
    invoking driver already observes the non-zero exit and a pre-slug record
    would need an `architect`-tier run-record-location decision; deliberately
    not a `--json` result, because `create` has no `--json` surface.
  - **Allowed behavior changes:** one added stderr line on a pre-slug
    refusal; exit codes unchanged.
  - **Allowed reorganization:** none.
  - **Verification:** each pre-slug `create` refusal path prints the token
    line with its closed reason, and a successful `create` is unchanged.
  - **Stop / defer:** if a driver needs the record after the process has
    exited, file a persisted-record entry then; do not build it here.
- **Origin:** 2026-10-19, Integration `construction-batch-driver` design §2.2.

**#504 — Plans declare dependencies on other plans**

- **Labels:** Route `plan`
  · Readiness `parked`
  · Tier `architect`
  · Principle `keep-the-plan-true-to-code`
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
- **Unpark when:** the fix for the unbuilt-sibling bug settles the plan-to-plan
  contract and a plan-level field is still needed; derive that field from the
  roadmap's `depends_on` rather than authoring it by hand.
- **Origin:** 2026-10-19, Integration `construction-batch-driver` design.

**#362 — Roadmap staged artifacts declare their format version (deferred)**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** an actual breaking change to a staged roadmap artifact is
  needed (not on a schedule); then open a fresh bare plan of its own, never a
  resumed one.
- **What:** the four roadmap staged artifacts (`01-domain.md` …
  `04-roadmap.md`) carry no in-band format version, unlike the plan and
  run-grade detail classes. A stamp changes the artifact bytes, and
  `plan_tool/roadmap_versions.py` binds each accepted-head version to the
  sha256 digests of those exact bytes, so a declaration-only change would
  invalidate every enrolled roadmap. Full reasoning:
  [`docs/evidence/authored-artifact-structure-versioning.md`](docs/evidence/authored-artifact-structure-versioning.md)
  § "Roadmap staged artifacts — deferred"; read it before design work.
- **Scope contract:**
  - **Outcome:** each of the four roadmap staged artifacts declares its
    format version in-band as one bundle version (not four independently
    versioned stages), a reader rejects an unsupported version with a named,
    actionable result, and the interaction with the accepted-head version
    store's exact-byte digests is explicitly resolved rather than left
    implicit.
  - **In scope (once re-entered):** `plan_tool/roadmap_artifacts.py`
    (`_parse_frontmatter` and the four staged parsers/renderers),
    `plan_tool/roadmap_versions.py` (the digest interaction),
    `plan_tool/roadmap_source_identity.py` (only if question 2 below still
    finds a relationship to settle),
    `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`.
  - **Out of scope / Non-goals:** version 2 of any artifact, a migration
    engine, on-read upgrading, content revision/lineage/history, and
    versioning `BACKLOG.md` / `plan-seeds/` / jira exports; resuming paused
    #242; reopening closed #328.
  - **Allowed behavior changes:** none yet — this entry is design work before
    it is implementation work. Behavior changes are scoped when the design
    questions below are answered.
  - **Allowed reorganization:** none yet, for the same reason.
  - **Verification:** deferred to the design phase; must include a fixture
    proving an already-enrolled roadmap either stays valid under the new
    declaration or is re-enrolled through an explicit, described transition —
    never silently invalidated.
  - **Stop / defer:** do not begin implementation from this entry's Outcome
    alone; the design questions below are answered first, in a fresh bare plan.
- **Design questions to settle in that bare plan:**
  1. Whether a structure upgrade republishes the bundle as a new accepted-head
     version whose record marks it structure-only (the current, undesigned
     recommendation), or enrolled roadmaps are exempt, or re-enrollment with an
     accepted lineage break is correct.
  2. How an in-band structure version relates to any other version field in the
     roadmap subsystem. Re-checked 2026-11-14: no roadmap module carries a
     `format_version` field now (`roadmap_source_identity.py` defines only
     `SOURCE_IDENTITY_VERSION` for the publication journal), so the collision
     the deferral first cited does not hold; confirm that at design time.
  3. Whether all four staged artifacts always declare the same version. The
     current recommendation is yes, one bundle version with a mixed-version
     bundle refusing.
- **Approach:** `plan-tool` once re-entered, design first; not `direct`.
- **Origin:** 2026-09-08, carved out of the authored-artifact format-version
  design review; user-confirmed the roadmap class is out of scope for the plan
  and detail format-version work.

**#365 — Reconcile authored-artifact documentation and planning-manifest discoverability**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** document `plan_tool/detail_artifacts.py` as the owner of the live
  run-grade detail version contract in `docs/ARCHITECTURE.md`, and reconcile
  the `Authored plans` manifest with the current planning-plan set (including
  the missing `roadmap-source-baseline-recovery` row).
- **Effort:** small; a direct documentation and manifest edit.
- **Dependencies:** the authored-artifact plan and detail contract landing for
  the architecture entry; the manifest repair itself is otherwise independent.
- **Scope contract:**
  - **Outcome:** an architecture reader can discover the detail version owner,
    and the planning manifest matches its stated coverage.
  - **In scope:** `docs/ARCHITECTURE.md` and the authored-plans manifest in
    `BACKLOG.md`.
  - **Out of scope / Non-goals:** changing artifact-version behavior, making
    `CLAUDE.md` itself versioned, a broad documentation linter, and #362's
    roadmap design; deliberately not a drift guard over the `CLAUDE.md`
    reference-doc bullets, because a guard on reference-bullet prose is
    semantic-doc linting (`CLAUDE.md` § "Validating a semantic property you
    cannot observe").
  - **Verification:** compare the manifest to the current `status: planning`
    plans, and verify the architecture entry names the correct owning module
    and contract.
- **Approach:** `direct`.
- **Origin:** filed 2026-09-09 while restructuring the authored-artifact plan
  after the detail-grounded audit surfaced the architecture/manifest
  discoverability gaps. Guard half cut 2026-11-14.
- **Status:** ready.

**#383 — Per-stage supplementary sources for `roadmap`, with declared roles**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** a named roadmap stage lacks essential grounded facts that
  cannot safely fit in the approved one-file brief, with the stage, the facts,
  and the failed safe representation recorded; more material in a composed
  input is not evidence.
- **What:** every roadmap stage receives exactly one prose input, the whole
  brief (`plan_tool/roadmap.py:_render_stage_prompt` builds `${brief}` plus
  one `${<key>_artifact}` per upstream stage). When the brief is produced
  upstream by another lifecycle engine, its material is already separated by
  purpose — a constraint register, a decision log, a prioritized backlog — and
  flattening it into one document is what forces a composer to choose between
  withholding grounding stage 2 needs and pasting a list stage 4 will return
  one row per. Give the roadmap's recorded source an optional `supplements`
  map keyed by stage key, render it as `${supplements}`, and require each entry to declare a
  **role** — `grounding` (facts a stage must use) versus `judgment` (material
  the stage is measured against afterward and must not enumerate from).
- **Effort:** medium. The prompt seam is one `variables` dict; the four
  stage templates need the new placeholder. The volume is in the identity
  contract: `roadmap_source_identity.py`'s digest must cover the supplements
  and each supplement's role declaration, or a receipt's currentness claim
  becomes false. Where a supplement attaches to the stored brief of an
  accepted version is undecided (see Precondition).
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
- **Status:** held 2026-09-16
  ([comparison](docs/evidence/roadmap-aidlc-intake-comparison-20260916.md));
  parked, see Unpark when above.
- **Precondition:** `source.json`, `read_recorded_brief_source`, and
  `_write_brief_source` were removed 2026-11-05 by
  `roadmap-versioned-from-birth`; a stage run now refuses once an accepted head
  exists. The carrier this entry describes must be re-grounded against the
  immutable version store (the stored brief bytes of an accepted version)
  before any plan is authored, and the owner decides how a supplement attaches
  to that stored brief.
- **Acceptance points (beyond the role enforcement above):** the identity
  digest covers each supplement and its role declaration; a roadmap with only
  a hand-written brief keeps current behavior.
- **Origin:** 2026-09-09, Integration's AI-DLC Ideation route. Stage 2 requires one
  hosting row per facet and one disposition per quality attribute and guesses
  when the brief is silent; the facts exist in an upstream
  `constraint-register.md` that has no way to reach it except by being pasted
  into the brief.

**#385 — `roadmap --view status --json`: one machine-readable state projection**

- **Labels:** Route `plan` · Readiness `ready` · Tier `architect` · Principle `untriaged`
- **What:** no roadmap view emits JSON
  (`--view {summary,walk,ledger,index,seeds,html}` are all human renders). A caller that wants to know where a roadmap *is* — whether it has an
  accepted head and which version, which feedback rows are open or awaiting
  review, which draft seeds classify `current`, and the last run's
  outcome — has to parse human output or re-implement the classifiers. Add one
  read-only projection over facts the tool already computes: the accepted-head
  versions (`load_accepted_head`), `classify_draft_seeds`, the feedback
  collections, and the run log's terminal event. The field list is grounded on
  the versioned-from-birth store: no baseline-enrolment or baseline-record
  field exists, because a roadmap has no baseline.
- **Effort:** small to medium. Every input already has a function; the work is
  the schema, its `DATA_CONTRACT.md` registration, and the fail-closed
  behavior when a roadmap is partially written.
- **Risks / fallout:** a state projection invites callers to treat it as
  authority. It is a *view*: the accepted-head versions remain the
  record, exactly as the run log is a monitoring projection rather than the
  execution record. Version it from the first release or a consumer will pin
  its field names by accident.
- **Dependencies:** none. Complements the shipped stage-lifecycle stderr
  contract (#337) rather than extending it — that reports transitions during a
  run, this reports state between runs.
- **Origin:** 2026-09-09, Integration's control-plane work. Integration presents two
  engines through one contract; the other engine offers both an event log and
  `--status --json`, where `plan-tool` offers `plan-tool runs` and no state
  projection, so the presentation layer is asymmetric for reasons that are not
  about the engines' actual capabilities.

**#386 — Prefer stating a parity/consistency relationship over enumerating one side of it, in plan authoring and audit remedies**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** a second independent enumeration-drift spiral is observed
  in plan authoring or audit remedies (the first was #370's router-parity
  rounds, 2026-09-16).
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
- **Status:** parked; not started.

**#518 — An installed plan-tool skill's router does not name the phase rules a driving session must read, so it skips them (for example the audit stopping rule)**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `converge-on-correct-plan`
- **Absorbs #425 and #388 (merged 2026-11-14):** (a) the router's must-read
  list names `integrations/shared/DIRECTIVES.md` § "Which model to run a
  subcommand with", so a driving session states the backend and model before
  any model-backed command and passes them explicitly; the mapping stays in
  the directives and no model ids are copied into the routers. This does not
  cover a repository with no skill installed, which was #425's motivating case
  and is an install-readiness issue. (b) #388's router-table drift decision
  (generated template or drift lint over the three hand-maintained copies of
  the decision-tree and subcommands tables) stays open and is not part of this
  slice: it is decided only if the full split below is ever taken, because the
  split is what removes most of those copies.
- **What:** ship the smallest version of the fix. Each integration's router
  (`integrations/{claude,codex,cursor}/`) names, per phase (authoring,
  auditing, running and the post-run tail, roadmap), the
  `DIRECTIVES.md` sections the session must read in full before acting in that
  phase, and inlines a short checklist of the specific rules the measured
  incident broke. The router keeps loading and the rules keep living in the
  sibling `DIRECTIVES.md`; the router tells the session which sections it may
  not skip. Re-measure on the next consuming-repo run; split the skill into a
  core plus per-phase skills only if the broken rules recur.
- **Why:** measured 2026-10-28 in a consuming repo (discord-config), driving
  a milestone plan through both audit gates and a post-run tail with the
  Claude Code skill installed (`.claude/skills/plan-tool/`, whose
  `DIRECTIVES.md` is identical to `integrations/shared/DIRECTIVES.md`, then
  1,402 lines). The session read `DIRECTIVES.md` by
  section offsets and grep hits, never whole, and broke four rules it never
  loaded:
  - It stopped the Gate 1 audit after round 3, whose findings were material,
    and started `detail`. It treated § "Trajectory, stopping, and the three
    exits"'s three-snapshot minimum window as a stopping point. The user
    corrected it.
  - It moved a capability out of a plan's scope on its own judgment and told
    the user only afterwards (§ "Pause on a product question — ask, don't
    infer"; § "Before applying anything: audit the why, not the what", the
    override rule).
  - It never recorded owner answers as dated decision lines in the plan.
  - It never presented findings as the plan-gap map.

  Earlier in the same session it had implemented five steps of a plan by hand
  instead of through `run`, then marked them done. Neither `reconcile-code
  --all` nor a code-review pass ran until a side note pointed it out
  (§ "After `run` finishes a plan").

  Two structural reasons show up for skill routing:
  - **One description covers every phase.** The router's `description` /
    `when_to_use` names authoring, audit, run, reconcile, roadmap and Jira
    together, so any plan-tool intent matches the same skill and gets the
    same thin router.
  - **The rules arrive by optional reading.** `DIRECTIVES.md` runs from
    § "Invocation and discovery" to § "Escape hatch" with about 30 sections.
    A session in one phase has no cue to read the whole section it needs
    rather than the first match.
- **Outcome:** a driving session that invokes the plan-tool skill for a phase
  finds, in the router itself, that phase's must-read `DIRECTIVES.md` sections
  and a short checklist of the rules the incident broke: for
  `completeness-audit`, the three-snapshot minimum window is not a stopping
  point, a scope move is surfaced to the user first, owner answers are
  recorded as dated decision lines, and findings are presented as the
  plan-gap map; for `run`, the plan runs through `run` with `--commit`, and
  `reconcile-code --all` plus a code-review pass follow the last green step.
- **Scope contract:**
  - **In scope:**
    - **The three routers** under `integrations/{claude,codex,cursor}/`: a
      per-phase must-read section list and an inlined phase checklist, kept in
      parity across the three (#386: state the relationship, not one side's
      instances). The checklist items restate existing rules by pointer to
      their `DIRECTIVES.md` section; no rule is reworded or added.
    - **The model-selection pointer (from #425):** each router names §
      "Which model to run a subcommand with" in its must-read list.
    - The install, format and help or catalog tests that pin today's router
      text.
  - **Out of scope / Non-goals:**
    - Any change to plan-tool CLI subcommands or their behavior.
    - Deliberately not the core-plus-per-phase skill split, the splitting of
      `integrations/shared/DIRECTIVES.md` by phase, or the install-set change
      in `plan-tool install-skill`: the split is large, Codex and Cursor
      routing between several skills is unverified, and the smaller change has
      not yet been measured to fail. Taken only if the re-measurement shows
      the broken rules recurring; then file it as its own entry with the
      phase-boundary, core-content and shared-source decisions.
    - Deliberately not a router-table template or drift lint (#388's
      decision), for the reason under **Absorbs**.
    - A gate in the tool that refuses `detail` while the latest bare audit
      has open blocking findings. That is invocation-time enforcement, which
      #370 excluded; file it as its own entry if wanted.
    - Drift-detection machinery on guidance content
      (`backlog-arc-installed-skill.md` § "Decision gates").
    - Rewording or adding rules, except the model-selection pointer absorbed
      from #425, which operationalizes an existing rule.
    - Changing what the machine-local `~/.claude/directives/plan-tool.md`
      symlink and the project-`CLAUDE.md` pointer reach.
    - Seed-authoring guidance (#377) and capture rules (#378, including the
      former #379).
  - **Allowed behavior changes:** the installed router's text grows by the
    must-read lists and phase checklists.
  - **Allowed reorganization:** none.
  - **Verification:**
    - Install each integration into a temporary project, with and without
      `--copy`, and check that each router names every phase's must-read
      sections and carries the checklist (binary).
    - Check that each router names the model-selection section (binary).
    - Check that every section a router names exists as a heading in
      `DIRECTIVES.md`.
    - Run the existing install and format tests, updated for the new router
      text.
    - Re-measure on the next consuming-repo run that drives a plan through both
      audit gates and the post-run tail, and record whether the four rules
      were broken again.
  - **Stop / defer:** if the re-measurement shows the rules still skipped,
    stop and file the full split as its own entry; do not widen this one. If a
    rule fits no single phase, it goes in the checklist for the phase that
    needs it and the shared-rule list once, not in two phases.
- **Dependencies:** #370, shipped 2026-09-16, is the base this changes.
  #388 and #425 are folded into this entry (see "Absorbs" above), so nothing
  needs coordinating.
- **Approach:** `direct`. The change edits three router files and their
  tests; the `architect`-tier phase-boundary decisions belong to the deferred
  split.
- **Origin:** 2026-10-28, a driving session in discord-config. The user
  proposed splitting the skill, not the CLI, to improve skill routing; the
  scope was cut to the router-only slice 2026-11-14.
- **Status:** ready.

**#389 — A newly added backend is rejected by `plan-tool install-skill --integration` with "invalid choice" until someone edits its hard-coded list of three names** → promoted to IPPT-7 (2026-09-24)

**#519 — Decide the disposition of the unreachable granularity-split review-walk opt-in**

- **Labels:** Route `direct`
  · Readiness `decision-needed`
  · Tier `experienced`
  · Principle `none` — disposition of an unreachable shared dispatch route
- **Evidence:** `plan_tool/review_walk.py:split_escalation_target()` requires
  `granularity-split` in `extra_apply_sources` and medium severity. The former
  `is_granularity_split_finding()` name no longer exists. Production callers of
  `cli/review_actions.py:_build_review_action_fn()` do not opt into that source;
  the surviving data-contract walk opts into its own source only. Retirement of
  `completeness-apply` leaves the structural dispatch branch unreachable.
- **Outcome:** choose removal or an explicitly scoped surviving consumer for
  this opt-in, then deliver only that decision with focused regression coverage.
- **In scope:** the opt-in predicate, shared dispatcher branch, caller inventory,
  and tests for the chosen disposition.
- **Out of scope:** reconnecting conceptual auto-apply, changing generic review
  or reconcile authority, audit gates, or an inventory of other `apply_finding` callers (the discarded #369).
- **Allowed behavior changes:** only the separately judged split-route disposition.
- **Allowed reorganization:** none.
- **Verification:** enumerate all production opt-ins; test the selected route and
  preserve the generic walk's refusal to dispatch unopted structural findings.
- **Stop / defer:** surface any need to change shared review authority separately.
- **Origin:** completeness-apply-retirement step 6, 2026-11-04.

**#520 — Prune current lesson guidance that points to retired application machinery**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `write-for-the-human`
- **Evidence:** `.plan-tool/lessons/project.md` has current guidance anchored by
  `completeness_apply_parallel.py` / `WorktreePool` (branchless worktree consumer),
  `_CONCEPTUAL_APPLY_SOURCE_RANK` (saved replay routing), and
  `_SAVED_SERIAL_APPLY_SOURCE_RANK` (serial/parallel source membership).
  Those production owners no longer exist after completeness-apply-retirement.
- **Outcome:** review and prune or narrow these stale instructional bullets so
  lessons describe surviving machinery without losing useful dated provenance.
- **In scope:** the named lesson bullets and directly related retirement claims;
  verify each against current symbols and consumers before changing it.
- **Out of scope:** blanket deletion of historical command mentions, lesson-store
  redesign, shared review changes, or rewriting saved reports and run logs.
- **Allowed behavior changes:** lesson text only.
- **Allowed reorganization:** none.
- **Verification:** compare each edited instruction with current code; inspect the
  diff to preserve independent lessons, history, and surviving consumer guidance.
- **Stop / defer:** file unrelated stale lessons separately rather than expanding
  into a repository-wide lesson audit.
- **Origin:** completeness-apply-retirement step 6, 2026-11-04.

**#338 — Extend stage-lifecycle status output to `roadmap --refresh-seeds` and `--materialize`**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** an operator runs `roadmap --refresh-seeds` or
  `--materialize` on a large seed or plan set and reports lacking visibility
  into which item is processing.
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
- **Origin:** 2026-09-02 `/code-review` pass on
  `2-roadmap-stage-lifecycle-output.md`'s landed diff
  (`plan_tool/roadmap.py` + `plan_tool/cli/roadmap_cmd.py`); the diff's own
  scope was the `roadmap <slug>` stage-run path, so this sibling gap was
  deliberately not folded into it.
- **Status:** parked; not started. No operator complaint stands behind it; it is a code-review sibling gap.

**#336 — Preserve deferred shared semantic work as a manual follow-up handoff**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** a `defer` result from split-create is observed lost (not
  surfaced where the operator would act on it); even then, first try printing
  the defer verdict in create's summary and run log before building a handoff
  artifact.
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
- **Iterate:** no seed is authored; none is written until unparked.
- **Status:** parked; not started.

**#332 — Install the run-log sink for developer-doc research in `create`**

- **Labels:** Route `plan` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** the developer-doc research call (`propose_references`) runs with no
  run-log sink, so its usage, cost and failure evidence are lost and the call
  warns that nothing saved them. Install the run-log sink for it, so the
  existing `claude_call_*` and `parse_failure` events land in the create run
  record.
- **Scope contract:**
  - **Outcome:** a create run that reaches `propose_references` always has an
    active compatible run-log sink for the Claude invocation, and an
    unparseable response produces a queryable `parse_failure` record distinct
    from an intentional empty reference result.
  - **In scope:** the create caller-to-invoker logging seam; the existing
    `claude_call_*`, backend-termination, and `parse_failure` event carriers;
    and hermetic command-level tests for success, an unparseable response, and
    an injected/alternate invoker path.
  - **Out of scope / Non-goals:** unrestricted raw model-response retention;
    a new cross-command telemetry framework; changing the reference-selection
    policy; or making a developer-doc research failure fatal (the failure
    policy belongs to the linked bug); deliberately not a new redacted
    diagnostic-artifact file or run-log pointer to one, because the sink alone
    may close the observed gap. File the artifact as its own entry only if the
    sink proves insufficient.
  - **Allowed behavior changes:** the run log gains the `claude_call_*` and
    `parse_failure` events for the reference-research call.
  - **Allowed reorganization:** reuse the current run-log writer and shell
    sink lifecycle. Do not introduce a general telemetry abstraction.
  - **Verification:** command-level fake-backend tests prove the reference
    call has `claude_call_end` token/cost fields, the unparseable path records
    a `parse_failure` event with its phase and reason, the empty-list path has
    no parse-failure record, and a sink-installation regression emits no
    unsinked-call warning.
  - **Stop / defer:** if an alternate invoker cannot provide usage safely,
    record that capability as unavailable with the parse reason; do not
    synthesize missing fields or add backend-specific persistence. If the
    sink alone leaves a failure undiagnosable, stop and file the diagnostic
    artifact separately.
- **Dependencies:** related to the developer-doc research parse-failure bug in
  `BUG_BACKLOG.md`; neither item blocks the other.
- **Approach:** `plan-tool` — a narrow observability change across create and
  shell/run-log integration, with contract tests.
- **Quality:** `failure-evidence` — makes a non-happy-path model call
  inspectable without widening the create plan's product scope.
- **Origin:** observed 2026-09-01 alongside the developer-doc research parse
  failure: the only diagnostic was the progress-line summary, and the call
  warned that no run-log sink saved its raw response, usage, cost, or lower-
  level failure evidence. Diagnostic-artifact half cut 2026-11-14.
- **Status:** not started.

**#268 — Per-step contract asks in the step proposal (failure modes and criterion mapping)**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** #110 resolves; then re-check the gap against
  `DETAIL_FORMAT.md`'s seven-section run-grade contract before designing,
  since it may close with no action.
- **What:** a proposed step today is title + classification + file list +
  one-line intent — the proposal prompt never asks what the step guarantees,
  what can fail and each failure's disposition, or which acceptance criterion
  proves it. The first three audit rounds of both 2026-08-12/13 plans
  (`batch-authoring-observability`, `roadmap-seed-materialization`) were
  dominated by exactly this mass: missing failure/atomicity contracts,
  unowned mechanisms, dangling criteria, `change_type` mislabels.
- **Waits on #110.** The right carrier (prompt-only prose vs. new `Step`
  fields) can't be decided yet — #110's measurement may conclude "keep
  claim-vs-delivery advisory" rather than promote it, which changes how much
  of this gap #110 already closes on its own. Wait for #110 to resolve, then
  decide the carrier and write the full design.
- **Effort:** medium–large, design-first, once unblocked.
- **Dependencies:** #110.
- **Approach:** plan-tool (seed first), once unparked.

**#173 — Keep incremental completeness scans deferred**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** measured operational audit cost justifies a new, bounded
  design that selects and proves a full-discovery cadence.
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
- **Status:** parked since 2026-08-20 (user-confirmed). Fresh completeness audits
  remain the operating path.
- **Durable insight (from a superseded draft, cut 2026-11-14):** under
  `--audit-passes 1`, `confirmation_kind` is `null` in every saved report,
  because the in-process dry streak cannot accumulate within a single pass;
  #303 owns cross-invocation comparison.

**#175 — Jira-readiness deterministic checks: HEAD-anchor verification and footprint coherence in `jira --lint` / `validate`**

- **Labels:** Route `direct`
  · Readiness `decision-needed`
  · Tier `experienced`
  · Principle `untriaged`
- **What:** extend `jira --lint` / `validate` with two deterministic checks
  that judge a detailed plan against one question — *can each step be handed
  to an implementer as an atomic story?* — with no model call and no new verb:
  (1) **HEAD-anchor verification** — extract the grep-verifiable code claims
  detail files make about HEAD (backticked paths, symbols, config keys,
  version pins in Input / "verified at HEAD" sections) and verify them against
  the repo, reporting only broken anchors; (2) **frontmatter↔detail footprint
  coherence** — each step's `files:`/`creates:` lists match the detail's
  declared footprint, including detail-flagged "noted additions".
- **Why (evidence 2026-07-22, example-app `mobile-initial-release-password-gate`):**
  a full completeness-audit round costs 30+ min. A hand audit reached
  jira-ready confidence in ~10 min: read 9 detail files, batch-grep-verified
  ~35 HEAD anchors (all held), and found exactly one ticket-blocking gap
  (step 8's detail declared a test file absent from the step's `creates:` —
  check 2). Everything that mattered for story generation was deterministic;
  the expensive conceptual sweep contributed nothing at that stage.
- **Effort:** small to medium — extraction plus file/grep work (the detail
  format's backticked-citation convention is already near-machine-readable).
- **Risks / fallout:** anchor extraction can misread speculative prose as
  a HEAD claim — scope extraction to citation-bearing sections (Input,
  acceptance-criteria greps) and treat "dependency contract" /
  "verification limit" labels as exempt.
- **Dependencies:** complements **#173** (fingerprint-gated completeness
  — that caches the expensive lane, this adds cheap deterministic checks).
  It remains independent of the terminal developer-handoff projection in
  #293. Reconcile with the authored `jira-sweep-deterministic` plan and the
  `jira-sweep-verify-code-truth` seed before planning: both read Jira
  ticket state through `jira-cli` (the plan's `plan_tool/jira_cli.py` leaf,
  #142/#143), which looks like a different question (ticket status versus
  plan readiness) with no anchor or footprint check; confirm the overlap is
  nil, or fold this entry into whichever owns the shared surface.
- **Scope contract:**
  - **Outcome:** `jira --lint` / `validate` reports broken HEAD anchors and
    footprint mismatches on a detailed plan in seconds, with zero model
    calls, each finding labeled with the check that produced it.
  - **In scope:** the two checks and their report lines; anchor extraction
    over `DETAIL_FORMAT.md`-shaped detail files; tests with a fixture plan.
  - **Out of scope / Non-goals:** changing the full completeness audit's
    behavior or prompts; #173's caching substrate; auto-fixing findings; a new
    audit verb or lane; deliberately not a decided-scope filter that
    auto-rejects findings inside a plan's "decided" sections (a semantic
    filter that can suppress real findings, and its marker convention in
    `PLAN_FORMAT.md`); deliberately not a ticket-blocking triage policy over
    conceptual finding kinds (triage policy, not a binary observable).
  - **Allowed behavior changes:** new lint/validate findings from the two
    checks.
  - **Allowed reorganization:** none.
  - **Verification:** on a fixture plan with (a) one broken anchor and (b) one
    undeclared detail-noted file, the checks report exactly (a) and (b), with
    zero model calls.
  - **Stop / defer:** the reconciliation under **Dependencies** comes first;
    stop if it shows the checks already ship elsewhere. Story-quality linting
    beyond what `jira --lint` already does.
- **Approach:** `direct` once reconciled — the two deterministic checks need no
  new format convention.
- **Quality:** `audit-coverage` + `gate-signal` — a deterministic
  complement to the sampled conceptual audit, aimed at the one exit
  signal (`jira` export) that hands work to humans; `grounding` — anchor
  verification keeps detail claims tied to HEAD at story-generation time.
- **Status:** not started. Use the example-app-amplify password-gate plan at
  `docs/implementation-plans/2-mobile-initial-release-password-gate.md` as a
  representative case. Cut to checks 1–2 2026-11-14.

**#163 — Claude-judged fold detector for dropped guardrail sections**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** a run-log count of how often the preservation warning fires
  on a folded rather than a dropped section shows the fold tail is noisy;
  otherwise discard the entry.
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
- **Priority note:** gated on evidence, not order. #162 (shipped
  2026-08-19) grounds the audit deterministically and spends no extra Claude;
  this spends a call to refine a finding's phrasing. The deterministic
  preservation check is live, so the question is answerable: **count how
  often its warning fires on a folded section rather than a dropped one.** If
  that tail is not actually noisy, do not build this.

**#98 — Rate-limit handling under parallel workers: non-interactive policy under `--jobs N` (the de-dup half is discarded)**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** an operator is actually prompted N times for one rate-limit
  event under `--jobs N`; it also waits on the `BUG_BACKLOG.md`
  `--on-rate-limit` policy fix.
- **What:** The interactive rate-limit recovery (prompt + key-polling wait) is now
  thread-serialized by a shared `claude_errors.RATE_LIMIT_PROMPT_LOCK`, so parallel
  workers (`detail --jobs N`, which share one process-global
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
  - **De-dup the forked helpers → discarded (#136; the duplication is the injection seam, per #79).** The near-verbatim copies of
    `_can_prompt_on_rate_limit` / `_select_rate_limit_backend` /
    `_ask_rate_limit_action` across `shell.py` and `launcher.py` are the remaining
    seam-extraction work, which is not to be merged (see
    `docs/history/backlog-decisions.md`, #136). This entry keeps only the
    non-interactive-policy half above.
- **Effort:** small (the non-interactive signal touches the invoker call sites in
  `detail.py`). **Approach:** `direct`.
- **Dependencies:** the landed `RATE_LIMIT_PROMPT_LOCK` fix; interacts with the
  `BUG_BACKLOG.md` entry "`--on-rate-limit switch`/`ask` silently collapse to
  `stop`" (fix that policy plumbing first so the shared helper carries the correct
  4-way behavior).
- **Origin:** 2026-07-06 — high-effort workflow code-review of
  `read-only-audit-split`; the TTY-collision finding plus the shell/launcher
  duplication finding.

**#107 — Deferred: project-configurable story layer vocabulary**

- **Labels:** Route `plan`
  · Readiness `parked`
  · Tier `experienced`
  · Principle `none` — deferred; export vocabulary with no demonstrated blocker
- **Unpark when:** a non-web Jira export fails to produce a usable artifact
  under the fixed story-layer vocabulary (see Trigger below); a hypothetical
  repository is not a trigger.
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
- **Status:** parked pending a demonstrated non-web Jira-export blocker.

**#66 — Contract-trace / path-enumeration audit mode (deterministic complement to the conceptual sampler)**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `architect`
  · Principle `deterministic-non-determinism` — the T3 band: a deterministic complement to the conceptual sampler
- **What:** A second completeness-audit mode that, instead of asking Claude to
  read the plan's prose and stochastically reason about it, materializes the
  plan's **declared seams/contracts** — function signatures, dataclass
  field-discipline (which field is populated on which outcome), the enum of
  outcomes/verdicts, and the call-site list — into a checkable skeleton, then
  **walks the `(caller × outcome × edge-input)` grid** and reports cells that
  are uncovered, crash, or violate a declared contract. Runs *alongside* the
  conceptual sampler, not instead of it. What is validated and what is not:
  `experiments/contract-trace-audit/` (`spike.py`, `LESSONS.md`) validated only
  the downstream grid walk over a **hand-encoded** contract model on the
  `escalate-structural-findings-to-split` fixture. The unproven half is
  **extracting the contract model from plan prose**, which is where the value
  and the risk sit; if extraction needs a Claude call, the determinism win
  largely evaporates. The next step is a narrowly bounded extraction spike,
  not the build.
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
- **Effort:** a small extraction spike first; the build is large and is not
  planned until the spike passes. Open design questions: how to extract the
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
- **Scope contract:**
  - **Outcome:** a recorded verdict on whether the contract model can be
    extracted from plan prose deterministically.
  - **In scope:** an extraction spike under `experiments/contract-trace-audit/`
    run on the original `escalate-structural-findings-to-split` fixture plus
    one recent plan; the verdict recorded in `LESSONS.md`.
  - **Out of scope / Non-goals:** the audit-mode build, a new
    `completeness-audit` mode or flag, and a full executable mock;
    deliberately not planning the large build before the spike passes,
    because the unproven extraction half decides whether it should exist.
  - **Allowed behavior changes:** none (experiment code only).
  - **Allowed reorganization:** none.
  - **Verification:** the spike either reproduces the three known findings
    from extracted (not hand-encoded) contracts with no Claude call and no
    mock-artifact findings, or the entry closes.
  - **Stop / defer:** close the entry if extraction is not deterministic or
    produces mock-artifact findings; record the measurement in `LESSONS.md`
    and remove the entry.
- **Approach:** `direct` for the bounded extraction spike; a `plan-tool` plan
  for the audit mode only if the spike passes.
- **Quality:** `audit-coverage` — a deterministic, path-enumerating audit mode that
  catches the contract/control-flow gaps the stochastic conceptual sampler surfaces
  only intermittently (the motivating HIGH an 11-sample run missed).
- **Origin:** 2026-06-22 — user, after watching the conceptual sampler surface
  the escalate plan's control-flow findings stochastically across multiple audit
  runs (a HIGH that an earlier 11-sample run missed), asked whether tracing logic
  paths through a mock implementation would find correctness/completeness gaps
  more reliably than feeding the plan prose. Narrowed to the extraction spike
  2026-11-14.

**#312 — Ground `detail` authoring in the plan's fetched reference-doc content instead of a bare link list**

- **Labels:** Route `plan` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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

**#156 — Make the conceptual-audit sampler key on the `[out-of-scope-deferred]` tag (currently prompt/operator convention only)**

- **Labels:** Route `plan` · Readiness `ready` · Tier `architect` · Principle `untriaged`
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
  low-yield productivity predicate; `recommend_audit_passes` no longer exists,
  so relocate the pass recommender, `review.py:audit_plan_until_stable`, before editing) + tests.
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

**#105 — Stable per-step identity to close the directive-signature same-`(title, change_type)` collision**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** one mis-targeted structural remedy is observed from a
  same-`(title, change_type)` collision.
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
  degrade to recommend-only on a gone plan instead of raising. Fold the
  `FileNotFoundError` handling into whatever change next touches the bridge,
  independent of unparking this entry.
- **Quality:** `audit-coverage` — sharpens how precisely the walk reasons about
  which step a saved directive still targets. Sibling of #93 (shipped) and its
  remaining test-authoring cross-link (#87).
- **Effort:** medium. **Approach:** `plan-tool`. **Iterate:** none until unparked.
- **Origin:** 2026-07-08 — high-effort code review of the shipped
  `precise-directive-staleness` (#93) change; confirmed the `(title, change_type)`
  signature collides and the bridge re-validation does not fully defeat it,
  correcting that plan's "bridges re-validate → never a wrong flip" overclaim.

**#119 — Snapshot-restore-then-retry for a partial-mutation streaming failure (response B)**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** run logs show surfaced partial-mutation stops often enough
  that the hand-revert-and-re-run cost is real; the `--commit` mandate already
  keeps the common path clean.
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
- **Iterate:** none until unparked.
- **Status:** parked; backlog entry only.
- **Origin:** deferred response B of the transient-retry-partial-mutation-guard
  plan (shipped response A closed the `BUG_BACKLOG.md` RISK), 2026-07-11.

**#120 — Close the partial-mutation retry guard's baseline-instant fail-open**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** the shipped response-A guard
  (`plan_tool/git_state.py:make_partial_mutation_retry_guard`) detects partial
  mutations via a git changed-**paths** delta. A baseline read that fails
  because of a transient `index.lock` returns `None` and leaves the guard
  inert, the same as a non-git tree, so a real repo that was momentarily
  unreadable at baseline has no guard for that call (a narrow fail-open). Add
  one `git rev-parse --is-inside-work-tree` probe to split "non-git tree"
  (inert) from "real repo unreadable" (retry the baseline read on a lock with
  a short backoff, then fail closed), which closes the fail-open and avoids a
  false failure on a transient lock.
- **Why:** a surfaced failure is the safe direction, but an inert guard on a
  real repo can let a retry double-apply an unseen partial mutation. Surfaced
  by two adversarial code-review rounds on the shipped guard.
- **Effort:** small — the guard closure and `changed_paths_or_none` plus
  tests; no leaf change (the `RETRY`/`STOP` contract is unaffected).
- **Risks:** the read-retry must not stall the loop (bounded, short backoff).
- **Dependencies:** builds on shipped response A; independent of #119
  (response B).
- **Scope contract:**
  - **Outcome:** a baseline-instant git-read failure in a real work tree
    retries briefly and then fails closed, while a non-git tree stays inert.
  - **In scope:** the `rev-parse` probe, the bounded baseline-read retry, and
    focused tests for lock-then-success, lock-persisting, and non-git tree.
  - **Out of scope / Non-goals:** deliberately not content-level detection of
    a further edit to an already-dirty baseline file (same-path masking),
    because it only bites without `--commit`, which the standing mandate
    already avoids; deliberately not scoping the delta to declared files or
    ignoring a benign-artifact set (`__pycache__` false STOP), because that
    case is hypothetical and over-scoping could weaken the guard. File each
    separately if it is ever observed.
  - **Allowed behavior changes:** a retry on a locked baseline read, and a
    fail-closed stop where the guard was inert on a real repo.
  - **Allowed reorganization:** none.
  - **Verification:** a fake reader that fails once then succeeds yields an
    active guard; one that keeps failing in a real work tree yields a STOP;
    a non-git tree still returns `None`.
  - **Stop / defer:** if the probe cannot distinguish the cases without
    changing the leaf's contract, stop and record why.
- **Approach:** `direct` — one probe and a bounded retry in the guard.
- **Status:** not started — backlog entry only.
- **Origin:** two adversarial `/code-review` rounds on the shipped
  transient-retry-partial-mutation-guard response A, 2026-07-11. Cut to the
  baseline-instant fix 2026-11-14.

**#230 — Extend the shipped `--time-budget` stop to durable batch boundaries**

- **Labels:** Route `plan` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `--time-budget` already stops the convergence loops cleanly. Extend
  the same cooperative deadline posture to the two long-lived surfaces that do
  not route through `convergence.should_continue`: the non-reconcile `run`
  per-step batch and the outer
  `detail` step-to-step batch boundary. Each has a durable progress boundary
  (plan pointer or per-step commit), so check the deadline
  only between units and emit an accurate resume hint.
- **Outcome:** a time-budgeted invocation of each named surface exits cleanly at
  its next durable boundary, preserves completed work, reports
  `time_budget_exceeded`, and provides a resume command.
- **In scope:** the two batch boundaries, shared budget resolution, their
  reporter/resume-hint wiring, and focused tests.
- **Out of scope / Non-goals:** interrupting a running Claude call; changing the
  shipped convergence-loop behavior; reworking checkpointing or commit policy;
  argparse consolidation (owned by #80); and a broad reason-to-hint refactor.
- **Effort:** small–medium — two boundary integrations over an established
  budget contract. **Approach:** `plan-tool` because the two caller contracts
  and resume semantics must stay coherent.
- **Quality:** `survive-interruption` — extends an existing safe-stop contract
  only where progress is already durable.
- **Verification:** each surface stops after a completed durable unit rather
  than beginning another; zero/off preserves current behavior; a natural stop
  retains its more-specific reason; and rerunning resumes without repeating
  completed work.
- **Origin:** retired cooperative-time-budget follow-up, 2026-08-04.
- **Status:** not started.

**#135 — Concurrent `reconcile-code` invocations should fail with a clear message**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **Shipped 2026-08-16:** `reconcile-code <name> --all` sweeps every plan step
  in order (including `done` steps, skipping explicit `non-code` steps). The
  documented "no remaining drift" signal is the full sweep's printed per-step
  verdicts (`_cmd_run_reconcile`'s docstring; `CLAUDE.md`'s run-tail loop 1).
- **What:** concurrent `reconcile-code` on the same plan should fail with a
  clear message instead of a bare exit-2 collision.
- **Effort:** small.
- **Approach:** `direct`.
- **Scope contract:**
  - **Outcome:** a second `reconcile-code` invocation on a plan that another
    invocation is reconciling exits non-zero with a message naming the
    concurrent run.
  - **In scope:** the concurrent-invocation detection in the `reconcile-code`
    path and a focused test.
  - **Out of scope / Non-goals:** deliberately not a `--check` drift rollup,
    because the full sweep's printed verdicts are the documented signal;
    deliberately not a shared-sweep abstraction across
    `_cmd_detail_reconcile_all`, `_cmd_run_reconcile_all` and
    `_cmd_run_sweep`, because their selection and persistence policies differ
    and no evidence calls for common machinery; serializing concurrent runs.
  - **Allowed behavior changes:** a clear failure message for a concurrent
    invocation.
  - **Allowed reorganization:** none.
  - **Verification:** a second invocation against a plan held by a first fails
    with the clear message, and a single invocation is unchanged.
  - **Stop / defer:** if the collision comes from a shared lock owned elsewhere,
    reuse that lock's message and stop; do not build a new lock.
- **Origin:** 2026-07-16 — lazy-deferral run-tail loop 1; friction driving
  `reconcile-code` step-by-step across a completed plan. Narrowed to the
  concurrency message 2026-11-14.

**#142 — Jira ID-linking sweep: map local plan-story IDs to real Jira keys via summary bracket-token**

- **Labels:** Route `plan` · Readiness `ready` · Tier `architect` · Principle `untriaged`
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

**#143 — Code-truth verification of status divergences: feed #142's divergent stories through the existing step-coverage verifiers, report only**

- **Labels:** Route `plan`
  · Readiness `blocked-on #142`
  · Tier `experienced`
  · Principle `untriaged`
- **What:** a follow-up to #142 that takes its divergence list and runs each
  divergent story, **serially**, through the existing step-coverage verifiers
  (`verify-all` / `reconcile-code`), reading the story's acceptance criteria
  and files-in-scope against the actual working tree. It reports a verdict per
  story (Done / Partial / Absent) and writes nothing: no local `[status:]`
  marker and no Jira field changes.
- **Why:** #142 (and any Jira-status sweep) can say two records disagree but
  can't say which is right. Tested for real: a code-blind sync that trusted
  Jira's "Done" and overwrote local `todo` markers was wrong for 24 of 29
  divergent stories — including silently endorsing two production regressions
  (an eligibility flag hardcoded to `true` behind a "Temporarily disable"
  comment, and a gate commented out entirely, both with their test suites
  rewritten to assert the disabled behavior) as "done" work.
- **Design source:** `plan-seeds/jira-sweep-verify-code-truth.md` holds the
  original design, whose 10-parallel-agent architecture and special-case
  classifiers are **not** the plan: in-process fan-out carries the
  parallelism burden of proof (`CLAUDE.md` § "Architecture"), and the
  verifiers it would rebuild already exist. The seed is reshaped to this
  entry's scope before `create`. Sequenced in
  `docs/implementation-plans/backlog-arcs/backlog-arc-operator-workflow.md`'s
  Prioritized selection: execute `jira-sweep-deterministic` (#142) first, then
  evaluate this one.
- **Scope contract:**
  - **Outcome:** each divergent story from #142's list has a printed
    Done / Partial / Absent verdict derived from the existing verifiers'
    reading of the working tree, with no file or Jira write.
  - **In scope:** a serial driver over #142's divergence list that calls the
    existing step-coverage verifiers and prints the verdicts; focused tests
    with a fake verifier.
  - **Out of scope / Non-goals:** auto-writing local status or Jira status;
    deliberately not 10-parallel agents, because in-process fan-out needs
    explicit sign-off and the serial path has not been shown too slow;
    deliberately not new behavioral-regression or superseded-plan
    classifiers, because the existing verifiers already judge coverage; a
    sample of agreeing stories (file separately if wanted).
  - **Allowed behavior changes:** a new read-only report over #142's output.
  - **Allowed reorganization:** none.
  - **Verification:** on a fixture divergence list, each story gets a verdict
    from a fake verifier, the run is serial, and no status marker changes.
  - **Stop / defer:** if the existing verifiers cannot take a story's criteria
    as input without a new prompt, stop and file that gap before building.
- **Dependencies:** #142 (needs its divergence list as input).
- **Origin:** 2026-07-17 — directly follows the #142 dry run; the manual
  10-parallel-agent run (`example-app-amplify`) is the evidence the design is
  built from. Reshaped to a serial, report-only driver 2026-11-14.
- **Status:** blocked on #142 executing first (per the operator-workflow
  arc's ordering); the seed needs reshaping before `create`.

**#190 — Refuse `reconcile-plan` on steps an execution already implemented**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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

**#192 — Conceptual findings carry a machine-readable step id**

- **Labels:** Route `direct` · Readiness `ready` · Tier `architect` · Principle `untriaged`
- **What:** every conceptual finding (`plan-correctness` / `plan-completeness`)
  is saved with `step_id = None`; all eight findings in the reviewed sample
  carry that value. The step is named only in prose ("Step 9 (`slug`)"). Have the audit prompt attribute
  each finding to a step id and parse it into the existing
  `Recommendation.step_id` field, which already exists and is already populated
  by the deterministic checks.
- **Why:** `step_id` is the join key several wanted behaviors need and none can
  have today — deterministically filtering findings whose remedy lands on a
  `done` step (the enforcement half of the discarded #191), a `--step`-scoped
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
- **Dependencies:** none.
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
- **Origin:** 2026-07-29, jira-grade round-17 checkpoint; split from the former #191 so
  the cheap advisory half could ship without waiting on the schema work.
- **Status:** not started.

**#193 — Lesson provenance: code anchors, commit, and step outcome on every citation**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** `--lessons` capture becomes the default again, so the
  lesson store grows on ordinary runs.
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
  6. **#195** gate injection behind `--lessons` — independent of #193/#194.

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
  **injection-side** entry (**#195** gate injection behind `--lessons`)
  is untouched: every run still injects the full matching set from the 1,462
  records already on disk, so a stale or contradicting entry keeps reaching
  authoring whether or not anything new is captured. **If this cluster is
  picked up, sequence #195 (injection-side) before #193 and #194
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
    (#195 injection gate); contradiction detection (discarded #197); back-filling
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
- **Status:** parked; not started.

**#194 — Reconcile lessons against the code they generalized from**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** #193 unparks and ships provenance anchors; discard this
  entry if #195's reshape makes lesson injection opt-in.
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
    provenance capture (#193); injection gating and any later ranking (#195); back-filling
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
- **Status:** parked with #193; not started.

**#195 — Inject lessons into `detail` authoring only behind the `--lessons` opt-in**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `render_lessons_block(load_lessons(...))` runs on every `detail`
  authoring prompt (`plan_tool/detail.py`, the `${lessons_block}` render)
  unconditionally, over a 1.6 MB store matched by `when:` conditions. Gate that
  injection behind the same `--lessons` opt-in that gates lesson capture, so a
  run that did not opt in receives no lessons block. Measure whether injected
  lessons help at all before building any ranking.
- **Why:** every injected lesson is a chance to contradict the plan — the
  rendered `detail` prompt for one step carried a plan fence forbidding export
  gates and a lesson asserting one, ~90 lines apart. With injection
  unconditional, that contradiction risk is live on every `detail` call. Gating
  the injection removes the surface for runs that did not ask for it, which is
  why this outranks building a detector (the discarded #197).
- **Measurement before ranking:** use the authored
  `lessons-reuse-instrumentation` plan to measure whether injected lessons help
  at all. Relevance-ranked top-k selection (anchor overlap with
  `step.files`/`creates`, `change_type` match, recency, citation count, with a
  floor below which nothing is injected) is built only if that measurement
  shows lessons help and the wholesale set is the problem; stay deterministic
  first, and justify `sqlite-vec` against a measured miss rate, not by default
  (`docs/explanations/nondeterministic-plan-design.md`'s determinism ladder).
- **Risks / fallout:** gating injection changes what an existing `detail`
  invocation without `--lessons` receives; the change is the point, and the
  prompt-rendering tests that assume a lessons block need updating.
- **Dependencies:** independent. Benefits from #193's anchors if ranking is
  ever built.
- **Effort:** small.
- **Scope contract:**
  - **Outcome:** a `detail` authoring run without `--lessons` renders no
    lessons block; a run with `--lessons` renders it as today.
  - **In scope:** the lesson-injection render in `plan_tool/detail.py`
    feeding `${lessons_block}` and the `--lessons` gate, tests.
  - **Out of scope / Non-goals:** changing lesson *content* or capture (#193
    and the BUG_BACKLOG capture-timing entry); contradiction detection
    (discarded #197); deliberately not relevance-ranked top-k selection, a
    relevance floor, or a withheld-count log line, because it is unproven that
    lessons help at all and ranking is built only after the measurement;
    adopting an embedding or vector dependency without a measured miss rate.
  - **Allowed behavior changes:** `detail` without `--lessons` stops receiving
    the lessons block.
  - **Allowed reorganization:** none.
  - **Verification:** a prompt render without `--lessons` has an empty lessons
    block and one with `--lessons` has the matching set; existing capture
    behavior is unchanged.
  - **Stop / defer:** if the measurement shows lessons do not help, stop and
    record that; if it shows they help and the wholesale set is the problem,
    file ranking as its own entry.
- **Approach:** `direct` — a gate on one injection site.
- **Quality:** `audit-coverage` — fewer irrelevant lessons means fewer invented
  requirements downstream.
- **Origin:** 2026-07-30, jira-grade authoring-model probe. Narrowed from
  ranked retrieval to the injection gate 2026-11-14.
- **Status:** not started.

**#198 — Plan provenance in git: structured trailers on green and archive commits, and `list --archived` read from the git log**

- **Labels:** Route `plan` · Readiness `ready` · Tier `architect` · Principle `untriaged`
- **What:** make "which plans were actually implemented, and where did that land
  in git?" answerable by machine, using git as the only store. Two parts:
  **(a)** structured `Plan-Slug: <slug>` and `Plan-Step: <n>` trailers on
  per-step green commits, plus a `Plan-Archive-Reason:` trailer on archive
  commits carrying an explicit archive **reason** (`implemented` /
  `superseded` / `cut`), because implemented and superseded plans are
  indistinguishable today; **(b)** `list --archived`, which reads the git log
  for those trailers.
- **Why:** the only durable trail now is the green-commit *subject*
  (`plan(<slug>): step N green — <title>`, `cli/run_cmd.py:_green_commit_subject`),
  which is prose parsed by `--grep` and breaks on hand-advanced steps, hand
  commits, and `--commit`-less runs. No trailer mechanism exists on these
  commits today (the operator's no-attribution policy rules out an
  AI-attribution trailer as that mechanism), so this introduces new
  machinery rather than extending existing plumbing. An archived plan is
  dropped from the manifest (`.plan-tool/plans.json`, a bare list of
  repo-relative paths with no metadata field), so no index of archived plans
  exists and `list` has no `--archived`. The discarded #199 (delete archived
  plans) would have depended on a reliable git record; this entry stands alone.
- **Implementation recommendation:** `git log --grep='^Plan-Slug: foo'` and
  `git interpret-trailers` both work without parsing prose. `list --archived`
  walks the log for archive-commit trailers, so there is no second store that
  can drift from git (the archive-folder mistake, #200). Consider
  `Plan-Fingerprint:` for the plan revision the step ran against.
- **Risks / fallout:** trailers only exist going forward; historical plans have
  subject-prose only. Do not back-fill by rewriting history — accept a
  `provenance: legacy` tier and let queries report it honestly.
- **Dependencies:** none.
- **Effort:** small to medium — trailer emission is small; the reason field is
  the design work.
- **Scope contract:**
  - **Outcome:** every newly landed plan step and every newly archived plan is
    locatable in git by structured query, with its archive reason recorded, and
    `list --archived` names archived plans with their reason from the log.
  - **In scope:** `plan_tool/cli/run_cmd.py` green-commit path, the archive
    commit path, `list --archived` reading git log, `DATA_CONTRACT.md` (the
    trailer vocabulary), tests.
  - **Out of scope / Non-goals:** deleting plans from the filesystem (the
    discarded #199); rewriting historical commits; changing what `run`
    commits; deliberately not an archive ledger file
    (`.plan-tool/archive-ledger.jsonl`) or its rebuild path, a ticket-to-step
    join over the jira export, or capturing a `verify-all` verdict at archive
    time, because git trailers answer the question without a second store;
    build any of them only once a query actually needs it, and file it as its
    own entry.
  - **Allowed behavior changes:** new trailers on green and archive commits and
    the `list --archived` surface. Commit *subjects* stay byte-identical — they
    are load-bearing for existing greps.
  - **Allowed reorganization:** none.
  - **Verification:** a `--commit` run emits parseable `Plan-Slug` and
    `Plan-Step` trailers; an archive commit emits `Plan-Archive-Reason`;
    `list --archived` names every archived plan with its reason from the log;
    legacy plans report `legacy` rather than a wrong answer.
  - **Stop / defer:** if an archive path makes no commit to carry the trailer,
    record that route as unsupported rather than adding a second store.
- **Approach:** `plan-tool` — two surfaces with an open reason-value design
  call.
- **Quality:** `grounding` — replaces prose-parsed provenance with a queryable
  record.
- **Origin:** 2026-07-30, from the archive-redundancy finding: git already holds
  what the filesystem archive duplicates, but nothing makes git *queryable* for
  which plans shipped. Cut to trailers plus `list --archived` 2026-11-14.
- **Status:** not started.

**#202 — Acceptance-criterion test references: each criterion names its test, and the check verifies the test exists**

- **Labels:** Route `plan` · Readiness `ready` · Tier `architect` · Principle `untriaged`
- **What:** the run-grade detail format requires each `## Acceptance criteria`
  bullet to name the test function(s) that assert it, and a deterministic check
  verifies that every named test function exists in the repo. A criterion with
  no named test, or naming a test that does not exist, is surfaced.
- **Why — measured, not hypothetical.** Four of the eight executed
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
- **Why a binary check and not a name matcher.** Fuzzy matching between
  criterion prose and test names is a semantic proxy: operators learn to ignore
  it, and it would not have caught the vacuous or under-asserted cases above
  (only mutation does). The observable the tool can assert is binary: the
  criterion names a test, and that test function exists. Whether the test
  asserts the criterion stays with the human and the reviewer.
- **Scope note: there is no longer a `refactor` pre-change contract to cover.**
  A sibling entry once proposed verifying that a refactor step's tests pass
  against **pre-change** code. It was measured and **withdrawn 2026-07-30** —
  81–89% of real refactor steps cannot satisfy it for legitimate reasons (see
  `CLAUDE.md` § "Withdrawn: the per-`change_type` test-ordering contract").
  This entry stands on its own and must **not** be widened to revive it.
- **Risks / fallout:** the format requirement changes `DETAIL_FORMAT.md`, so
  the format version and its legacy-bundle handling are decided explicitly in
  the plan, not left implicit. One test can legitimately be named by several
  criteria, and one criterion can name several tests; report only criteria with
  a missing or non-existent reference, never "excess" tests.
- **Dependencies:** none.
- **Effort:** medium — the format-contract change, the extraction of named
  tests, and the existence check; no matching heuristic and no precision
  calibration.
- **Scope contract:**
  - **Outcome:** a finding per acceptance criterion that names no test, or
    names a test function that does not exist.
  - **In scope:** the `DETAIL_FORMAT.md` requirement (with its format-version
    handling), the detail authoring prompt line, the run-grade
    criterion/test-reference extraction, the existence check, its registry
    entry, and tests.
  - **Out of scope / Non-goals:** deliberately not a fuzzy name or prose
    matcher between criteria and tests (a semantic proxy that operators learn
    to ignore, and one that would not catch vacuous or under-asserted cases);
    judging whether a named test really asserts the criterion; mutation
    testing; coverage thresholds; reviving any refactor pre-change ordering
    check; flipping any exit code.
  - **Allowed behavior changes:** one new finding source, and the
    detail-format requirement that criteria name their tests.
  - **Allowed reorganization:** none.
  - **Verification:** a criterion naming no test is flagged; a criterion naming
    a non-existent test function is flagged; a step whose criteria all name
    existing tests is silent; the finding never flips an exit code.
  - **Stop / defer:** if the format requirement forces churn across existing
    bundles that the version handling cannot absorb, stop and report rather
    than adding a matcher.
- **Approach:** `plan-tool` — the format-version handling is the open design
  call.
- **Quality:** `audit-coverage` — closes the gap between what a step promises
  and what it proves.
- **Origin:** 2026-07-30, from a 15-mutation spot-check over a session's
  shipped guards (14 caught, 1 unasserted guarantee) plus four review findings
  of the same shape. Reshaped 2026-11-14 from a fuzzy claim-to-test matcher to
  the binary named-test check.
- **Status:** not started.

**#208 — `roadmap` arc position 05: framework lenses** *(anchor entry for the `roadmap-NN-*` seed group)*

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `grounding`
- **Unpark when:** a named framework-specific roadmap need arises with a
  checkable coverage contract (a set comparison, not a judgment).
- **What:** positions 01-04 of the `roadmap` arc ship (2026-07-31 to
  2026-08-05; contract in `ROADMAP_FORMAT.md`). Position 05,
  `roadmap-05-framework-lenses`, is the whole of this entry and stays
  unauthored: a lens registry, an `aws-well-architected` descriptor, a
  `--framework` flag, a lens-driven stage-2 prompt, and a coverage gate that
  fails a response leaving a pillar neither discharged nor explicitly
  deferred. Stages 1-4 ship on the generic default lens, so it is additive.
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
- **Evidence:** `docs/evidence/roadmap-run-measurements.md`; read
  `docs/evidence/roadmap-layering-measurement.md` § "How to read this result"
  before citing it.
- **Origin:** 2026-07-31, user request for architecture-framework alignment
  (AWS Well-Architected named); positions 01-04 discharged everything but the
  framework half.

**#216 — A quality benchmark for plan-tool's own output, floors first** *(anchor entry for the `quality-bench-NN-*` seed group)*

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** a concrete current-model A/B question needs the one disposable
  observation.
- **What:** one disposable observation of each metric's own rerun spread,
  run **only when a concrete "did change X help?" question exists** that the
  spread would let someone answer. A corpus replay that stores artifacts and
  reports deltas between labelled runs against that spread (note: a
  `plan-tool bench {run,report}` group already exists for backend × task-family
  comparison, and this replay is not built there) is a possible later route,
  not current scope. The arc deliberately ships **no model-scored metric in
  position 01**.
- **Trigger — no question named today.** Measurement is worth doing only when
  a decision consumes it. Nothing consumes it now: position 02 is unauthored
  and no pending A/B question is named, so the observation is **not scheduled**
  and the entry is off the board's "Next" lane. A named question promotes it.
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
  (`docs/explanations/nondeterministic-plan-design.md` Rule 6's fork) — floors and trends over
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
- **Re-triage (2026-08-28; reshaped 2026-11-14):** position 01's noise-floor
  question is retained and its three-step plan is withdrawn: that plan builds a
  corpus format, persisted record, runner, CLI, and documentation before one
  current-model exercise shows a durable replay surface is needed. The
  observation is one disposable two-item, serial stage-2 run with an explicit
  Codex backend that records only the three factual measurements. It creates no
  new command or reusable storage, and it runs only once the trigger above
  fires. A fresh bare plan is justified only if that observation cannot answer
  the question or shows a repeated durable replay need. It receives completed
  risk and confidence surfaces only as context for what later claims might
  concern; it does not score either field, turn either into a decision rule, or
  merge their contracts. Renderer consolidation (the discarded `#316`) stays
  out.
- **Prior scope reset (2026-08-27; historical):** the seven-step
  `quality-bench-01-corpus-and-noise-floor` plan received repeated
  completeness-stage `split=1` then `split=2` assessments (for example,
  telemetry decisions `3a1543ba94050e6a`, `ab34e1d31cb647f8`, and
  `5975b3732a4fb9dd`). This is detector case **(a)**: the signal fired but was
  not acted on. The user-directed conclusion is that position 01 is a
  three-step smallest-proof feasibility effort, not a reusable benchmark
  subsystem. That conclusion reduced the plan but did not make its runner and
  CLI necessary; the plan is now historical, not the selected scope.
- **Current effort:** a single low-cost observation, run only on the trigger
  above. Any future verb group, metric registry, artifact store, or
  data-contract row needs fresh evidence from that observation rather than
  inheriting this entry's old product shape.
- **Current scope contract (the observation):**
  - **Outcome:** the three factual rerun measurements for one two-item stage-2
    replay, recorded against the named A/B question that triggered the run.
  - **In scope:** one disposable serial run and a short evidence note.
  - **Out of scope / Non-goals:** deliberately not a command, runner, corpus
    format, artifact store, or `DATA_CONTRACT.md` row (a durable surface needs
    the observation's evidence first); deliberately not running without a named
    question (nothing would consume the result); any model-scored metric.
  - **Allowed behavior changes:** none.
  - **Allowed reorganization:** none.
  - **Verification:** the note states the A/B question, the backend, and the
    three measurements.
  - **Stop / defer:** with no named question, do nothing.
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
- **Future capability boundary** (not current scope, not on the board; a later
  evidence-backed seed pins its own):
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
- **Status:** parked until a concrete A/B question names a consumer for the
  measurement. No active position-01 seed or plan. The withdrawn plan and its
  audit reports preserve the rejected runner/CLI shape as history. Position 02
  remains unauthored until a future, reviewed floor record exists.

**#242 — A `roadmap` revision discards what it resolves: retain the closed feedback and the decision behind a drop**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** a second independently justified source-baseline recovery
  need arises, or an explicit bounded one-time Integration 2:3 remedy is
  requested; start with a fresh bare plan and consider shipping only
  `FeedbackState.closed` first, since the removal-to-decision reference has no
  reader need yet.
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

**#395 — Selector-era candidate lineage has no discard route: check whether any enrolled roadmap holds one**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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
- **Why now:** the exposure is legacy-only and matters only when a ledger-less or
  freshly migrated roadmap holds an unfinished selector-era candidate.
  Ledger-batch candidates release through the routes above. No evidence yet
  shows that any enrolled roadmap holds such a lineage, so the first step is to
  check rather than design.
- **Outcome:** a recorded answer to "does any enrolled roadmap hold a
  selector-era candidate lineage (an admission with `root_version_id` of
  `None`)?". If none does, the selector-era route is retired or a hand recovery
  for it is documented. If one does, that lineage is recovered by hand and the
  entry closes with the recovery recorded.
- **In scope:** inspecting the admission file of each enrolled roadmap the owner
  names; then either retiring the selector-era route or documenting the hand
  recovery (for example in `docs/how-to/roadmap.md`).
- **Out of scope / Non-goals:** deliberately not a new discard route, and
  deliberately not "stalled"-versus-slow semantics or an operator confirmation
  for them (the exposure is legacy-only, so a designed state machine is
  disproportionate); any change to `promote_review_seal` or the
  sealed-promotion boundary; discarding a lineage that has already produced a
  sealed, promotable review; the batch reject and discard routes; widening the
  narrower `unpromoted-candidate-lineage` predicate the batch route uses.
- **Allowed behavior changes:** retiring the selector-era route, only if the
  check finds no lineage; otherwise none.
- **Allowed reorganization:** none.
- **Verification:** the entry states which roadmaps were checked and what each
  admission held; a retirement is covered by a test that the retired route is
  refused with an actionable message.
- **Stop / defer:** if a selector-era lineage exists on a roadmap the owner
  cannot inspect, leave the entry open and record the unknown.
- **Approach:** direct — an inspection, then either a small retirement or a
  documented hand recovery.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** 2026-09-18, `roadmap-decision-settlement` bare-plan audit round 5,
  finding `enrolled-lineage-block-exit`; narrowed 2026-09-23 when
  `roadmap-versioned-feedback-revision-chain` shipped reject and discard for batch
  candidates; reshaped 2026-11-14 from a discard-route design to a check-then-retire
  decision.

**#525 — Validate copied plan-tool skills in the current project so stale instructions are visible**

- **Labels:** Route `direct`
  · Readiness `decision-needed` — select the existing validation surface and when it runs; #403 builds no doctor command, so this check ships on the existing skill-install surface without a broader readiness inventory
  · Tier `experienced`
  · Principle `deterministic-non-determinism`
- **What:** add a read-only validation of the current project's copied
  plan-tool skill against the matching bundled integration. Compare both
  `SKILL.md` and its shared `DIRECTIVES.md`; report whether each copy matches,
  differs, or cannot be compared, with the project path and a safe refresh
  command. A symlinked installation is outside this copied-content check.
- **Why:** copied installations do not track package updates automatically.
  `plan_tool/cli/skill_cmd.py` also deliberately installs the Codex integration
  as copies because Codex skips symlinked `SKILL.md` files. A current-project
  check makes stale copied instructions visible before they guide work.
- **Effort:** small — project installation discovery, byte comparison against
  packaged sources, an actionable report, and focused tests.
- **Risks / fallout:** legitimate local edits also differ from bundled bytes;
  describe a difference without judging instruction quality or overwriting it.
  Missing packaged sources must report inability to compare, not a match.
- **Dependencies:** no implementation dependency; coordinate ownership with
  #403, which owns the doctor-reference cleanup and assigns stale copied skills
  to this entry.
- **Scope contract:**
  - **Outcome:** an operator can determine whether a copied plan-tool skill in
    the current project matches the installed package's corresponding files.
  - **In scope:** project-local `.claude` and `.agents` plan-tool skill
    installations, matching integration selection, router/directives byte
    comparison, and actionable read-only validation output.
  - **Out of scope / Non-goals:** semantic quality judgments, comparison of
    unrelated skills, user-wide installation inventory, automatic refresh,
    forced overwrites, converting copies to symlinks, and a general doctor
    framework. Do not make freshness a gate or change ordinary command exit
    codes merely because copied bytes differ.
  - **Allowed behavior changes:** only the selected validation report and its
    documented invocation; preserve installations and local edits.
  - **Allowed reorganization:** none.
  - **Verification:** fixtures cover matching copies, stale router only,
    stale directives only, missing companion/source, both project skill roots,
    the Codex copy default, and symlink exclusion. Verify no files change.
  - **Stop / defer:** resolve the validation-surface choice before implementation;
    file broader readiness checks as separate entries (#403's revisit condition).
- **Origin:** explicit owner request, 2026-11-12, during project model
  configuration design.
- **Status:** not started.

**#403 — `plan-tool doctor`: fix the stale `docs/GATES.md` reference and file readiness checks individually**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** no `plan-tool doctor` command is built. Three bounded actions replace
  the former spike: (1) fix or remove the `plan-tool doctor` line in
  `docs/GATES.md` § "Correctness checks (shipped, follow-ups deferred)", which
  names a unified pre-everything gate the CLI does not have; (2) ship the
  copied-skill staleness check as #525 on the existing skill-install surface
  (`cli.skill_cmd`), not on a new command; (3) file each further readiness
  check as its own backlog entry when an operator observes the need.
- **Why:** the entry was triggered by one incident (a persistent local writer
  lock that needed a precise `.gitignore` rule), and its candidate inventory
  (version and resources, worktree discovery, ignore rules, skill state,
  backend executable, malformed roadmap files, Git executable) was a kitchen
  sink with no shared owner, remedy, or observed demand. One observed check
  does not justify a top-level command, status vocabulary, or JSON contract.
  Narrow primitives already exist: `cli.gitcommit.ignored_recommended_paths`
  for durable `.plan-tool` files and `cli.skill_cmd`'s packaged-source and
  destination classification.
- **Revisit condition:** reopen a `doctor` design only once three or more
  individually owned checks exist, each with a stable remedy, so the shared
  report shape is drawn from real checks. The general `.gitignore` audit stays
  #318.
- **Scope contract:**
  - **Outcome:** `docs/GATES.md` no longer names a doctor command that does not
    exist (or names it as deliberately deferred with the revisit condition),
    and the doctor-related readiness checks have owners: #525 for skill
    staleness, individual entries for anything else observed.
  - **In scope:** the `docs/GATES.md` line; the #525 cross-reference; filing
    individual check entries as observed.
  - **Out of scope / Non-goals:** deliberately not a `plan-tool doctor`
    command, status vocabulary, or JSON report now (one incident does not
    support a framework; reopen at three owned checks); deliberately not a
    spike or inventory of the candidate list; changing `.gitignore` rules
    across arbitrary repositories (#318); modifying skill installations;
    authenticating or invoking a model provider; a general security scanner.
  - **Allowed behavior changes:** none.
  - **Allowed reorganization:** none.
  - **Verification:** `docs/GATES.md` agrees with the CLI's actual subcommands
    (`plan-tool --help` lists no `doctor`, and the doc does not claim one).
  - **Stop / defer:** any readiness check without a clear owner or remedy stays
    unfiled until observed.
- **Risks / fallout:** an over-broad doctor can become a misleading release
  gate or duplicate checks that belong to the feature that owns them; the
  revisit condition keeps that from being designed early.
- **Dependencies:** #525 ships the skill-staleness check independently; related
  to #318's broad ignore-rule audit but does not depend on it. The
  installed-skill entries #377–#378 are not reopened.
- **Approach:** direct — a one-line doc fix and bookkeeping.
- **Origin:** 2026-09-21, a Integration roadmap run left a persistent local writer
  lock that needed a precise `.gitignore` rule, alongside questions about the
  active plan-tool installation and installed skill readiness; reshaped
  2026-11-14 from a doctor-contract spike.
- **Status:** not started.

**#404 — Decide the completeness audit's intent-fidelity boundary**

- **Labels:** Route `plan` · Readiness `decision-needed` · Tier `architect` · Principle `untriaged`
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

**#377 — Teach installed plan-tool skills to author and validate plan seeds**

- **Labels:** Route `plan`
  · Readiness `ready`
  · Tier `architect` — it changes the guidance available to every driving assistant before plan creation
  · Principle `untriaged`
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
  updating entries found already addressed (the former #379, now part of #378).
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
- **Origin:** 2026-09-16, user clarification that chat orchestration often
  creates the seed and the router/reference plan (formerly #370) should stay
  focused on the router.
- **Status:** not started.

**#378 — Installed skills route discoveries outside a plan's intent, proportionality, or scope into the host repo's tracker**

- **Labels:** Route `direct` — guidance text in one reference file plus citations; a missed site is caught by the binary citation check in Verification
  · Readiness `ready` — the router/reference split it depended on (formerly #370) shipped 2026-09-16
  · Tier `architect` — it changes the canonical directives every driving assistant follows
  · Principle `untriaged`
- **What:** one direct edit adds a single section to the installed shared
  reference (`integrations/shared/DIRECTIVES.md`) for a discovery the driving
  session will not act on because it falls outside the plan's stated intent,
  the proportionality bound, or the scope contract. The section states four
  things: the sink order, the ask-once fallback with an explicit "not filed"
  report, an existing-record search before filing, and the entry's own commit.
  Every directive site that says "defer", "present separately", or "file it"
  without saying how cites that section instead of restating it.
- **Absorbs #379 (merged 2026-11-14):** closing an already-addressed entry, as
  a subsection beside this entry's rule. Tier stays `architect`: it governs
  when a session may remove a record another author wrote. When a session
  observes that a tracker entry other than the plan's own source entry is
  already satisfied, partly satisfied, superseded, or based on a false
  premise, these closing defaults C1–C6 apply, separate from this entry's own
  defaults (confirm or revise before implementation): (C1) incidental only:
  entries the session's work touched or its searches returned, never a
  proactive staleness sweep; (C2) verify first against the entry's Outcome and
  Verification (a bug's Symptom) at HEAD, citing the satisfying commit or
  anchor, and annotate instead of closing if checking needs a new run,
  measurement or model call; (C3) addressed: close by the host convention (a
  more specific rule in the entry or its plan wins); partial: narrow to the
  verified remainder and cite what shipped; superseded or false premise: close
  with a dated reason; uncertain: add a dated evidence note; (C4) citation
  sweep before closing: search tracked docs for the id and the entry's title
  vocabulary (roll-up boards, arc and runbook docs, seeds, plans) and update
  or explicitly keep each hit; (C5) surface instead of changing when the entry
  is `decision-needed` or `parked`, or records a user decision not to reopen;
  (C6) commit separately (tracker-only) and list each entry changed with its
  disposition and evidence. Measured failures behind it: over-deletion
  (`5042c3ba` restored #337 after a closure applied the general
  remove-when-shipped convention) and a dangling citation (a step deleted #315
  and checked only `BACKLOG.md`, missing an arc-doc citation). Resemblance is
  not closure: four of five claimed duplicate helpers in #79 were wrong. If a
  host's closure convention cannot be discovered generically, default to a
  dated evidence note and surfacing. Escalate to a fuller plan if the user
  wants per-entry confirmation before any closure (which also changes this
  entry's authority line).
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
    consolidation opportunity; migrate a findings stub). A `plan-tool` defect
    found while driving another project goes to the file that owns its
    subsystem, when observed.
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
- **The section's four rules (reshaped 2026-11-14 from six defaults):**
  1. **Sink, in order.** The host repo's stated convention (its instruction
     file, or a contributing or tracking doc); an existing forward-work and
     defect tracker pair such as `BACKLOG.md` / `BUG_BACKLOG.md`, choosing by
     "would a user filing this as an issue be right?"; the plan's own
     `## Deferred` for later scope or an open decision that belongs to that
     plan. A `plan-tool` defect goes to `plan-tool`'s tracker, not the host's;
     with no writable `plan-tool` checkout, surface it with the evidence needed
     to file it.
  2. **Ask once, else "not filed".** With no sink identified, ask the user
     once. Unanswered in a headless run, the item is listed in the final report
     under an explicit *Not filed — no tracker identified* heading. Never
     create a tracker, or file into a similarly named artifact with another
     purpose, without the user.
  3. **Existing record first.** Search by identifier and by vocabulary (check
     0's two searches) and extend a matching entry with the new provenance
     rather than duplicating it.
  4. **Own commit.** Record once classified and before the next `plan-tool`
     invocation's pre-call commit, as its own tracker-only commit and never
     inside a plan-correction batch. A chat message, handoff note, or scratch
     file is not a record. The session reports each record by location.
  The section applies to a discovery outside the plan's fence (an
  `[out-of-scope-deferred]` finding, a finding declined under the
  proportionality rule, an out-of-scope sibling from check 0, a broader fix the
  smallest-change rule declines, a scope-guard stub's reverted records, an
  exit-3 item, a `plan-tool` defect found while driving another repo). An in-scope advisory tail is not covered; its
  saved report already retains it. Deferring a material, in-scope-looking
  finding that no explicit fence excludes remains a scope decision that the
  existing override rule surfaces first.
- **Effort:** small to medium — one new reference section, citation edits in
  the nine sections above plus the router pointers, and two hand-walk checks.
  No code.
- **Risks:** filing noise if the section reads as "record every finding" — the
  advisory-tail exclusion is load-bearing; drift if sites paraphrase the rule
  instead of citing it; misrouting in a repo with an unusual convention, which
  the ask-once fallback contains.
- **Dependencies:** none — the shared reference is the installed
  `DIRECTIVES.md` file, shipped 2026-09-16 as the skill-router-and-shared-reference
  plan (formerly tracked as #370); that plan's own Non-goals excluded
  directive content changes beyond relocating roadmap guidance. This item
  edits the same files as #377; sequence after #377 if it is also taken.
- **Outcome:** a session driving `plan-tool` through an installed skill
  reaches, from every site that defers, one rule that turns an out-of-scope
  discovery into a record in the host repo's own tracker or an explicit,
  reported "not filed".
- **In scope:** `integrations/shared/DIRECTIVES.md` (the new section, including
  the closing-an-addressed-entry subsection absorbed from #379, and a
  citation in each section above); the router pointers as the shipped
  router/reference plan (formerly #370) leaves them; install and format tests
  only where the edits require it.
- **Out of scope / Non-goals:** deliberately not a plan route (guidance text
  with an explicit Verification, reviewed through the normal pull request at
  `architect` tier, needs no plan decomposition); deliberately not the six
  numbered defaults the entry first proposed (a required minimum-content
  template and a separate authority default restate content the host's own
  entry format and the existing override rule already carry); a command that detects or closes addressed
  entries; closing items in an external issue tracker; this repo's closure
  convention in `docs/TRACKING.md`; the scope guard's stub output (#380); seed-time
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
    (a) a scratch repo with `BACKLOG.md` / `BUG_BACKLOG.md` and (b) a
    Integration-shaped repo with no tracker and a backlog-named ideation file.
  - A hand replay of the closing rule reaches the right outcome on the three
    measured incidents: #337 (the plan-specific retention rule beats general
    removal), #315 (the sweep finds the arc-doc citation), and `2b0273cc`'s
    already-fixed defect (verified, not filed).
  - Deliberately not checked: whether a session records anything, entry
    quality, the fence judgment, or whether a session notices an addressed
    entry or verifies it soundly.
- **Stop / defer:** if sink selection cannot be stated without a tool-side
  key, ship the ask-once and "not filed" fallback and file the key as its own
  entry.
- **Origin:** 2026-09-16, a user-directed review of the installed skills and
  this backlog for orchestration-layer duties when work surfaces outside a
  plan's intent, proportionality, or scope; reshaped 2026-11-14 to one direct
  section.
- **Status:** not started.

### B. Significant UX changes

**#262 — Bare-stage report header: one static line that detail is the next step**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** the bare-stage completeness report (the one that labels exact
  detail coverage) carries one static line in its header: *"Remaining
  detail-owned remedies are expected; with no HIGH/CRITICAL plan-correctness
  finding, `detail` is the next step."* The line is fixed text. It counts
  nothing, reads no audit history, and is not conditioned on how many bare
  audits ran.
- **Why:** a bare plan has no detail bundle for the audit to ground against, so
  repeated conceptual samples can keep discovering increasingly fine
  implementation contracts. The need is mostly covered already: the bare-stage
  bar does not block on `plan-completeness` medium findings, the
  severity-aware low-yield exit exists, the `bare_mechanism_findings` advisory
  exists, and `CLAUDE.md` already says a confirmed-dry re-audit plus a fresh
  unchanged snapshot is enough to proceed to `detail`. What is missing is the
  same sentence at the point where an operator reads a bare-stage report.
- **Cut 2026-11-14 (do not re-open without new evidence):** a history-counting
  policy (the qualifying bare-audit count, saved-history eligibility filtering,
  a JSON advisory payload) and its plan route. Its only evidence was one
  retired planning session (n=1, the #231 plan's eight bare-plan audits), and
  an uncalibrated counter over legacy and checkpoint sidecars is a
  maintenance cost the static line avoids.
- **Effort:** small — one header line in the report renderer, and a test that
  the line renders on a bare-stage report and not on a detail-stage report.
- **Risks / fallout:** a fixed line could teach users to skip a genuinely
  unsound design into detailed prose; the HIGH/CRITICAL condition in the line
  states the exception, and the existing correctness findings are unchanged.
  Copy must not imply a changed exit code, bar, or verdict.
- **Dependencies / related:** the settled bare-vs-detail convergence bar; this
  item consumes the shipped stage facts without adding a blocking rule.
  Narrowing the bare prompt (the discarded #241) and a separate
  implementation-time finding class (the discarded #139) are not a substitute.
- **Scope contract:**
  - **Outcome:** a bare-stage completeness report states, in one fixed line,
    that detail-owned remedies are expected and that `detail` is the next step
    absent a HIGH/CRITICAL plan-correctness finding; detail-stage reports are
    unchanged.
  - **In scope:** the bare-stage header in `plan_tool/completeness_report.py`,
    its fixture, and the CLI documentation line that describes the report.
  - **Out of scope / Non-goals:** deliberately not a history count, an
    eligibility predicate over saved audits, or a JSON advisory payload (the
    cut above); changing conceptual finding severity or source; suppressing,
    auto-applying, or reclassifying findings; modifying `--audit-passes`;
    changing the bare/detail blocking bars or exit codes; automatically
    invoking `detail`; adding a plan-mass or audit-count gate.
  - **Allowed behavior changes:** one informational line in the bare-stage
    report. Existing verdicts, findings, JSON fields, and exit codes stay
    unchanged.
  - **Allowed reorganization:** none.
  - **Verification:** a bare-stage report renders the line; a detail-stage
    report does not; return codes and blocking JSON fields are unchanged.
  - **Stop / defer:** if the line cannot be placed without touching a JSON
    contract, render it in the terminal summary only and record that.
- **Approach:** direct — a fixed header line and one test.
- **Quality:** `convergence` and `gate-signal` — sharpens the operator's next
  action without weakening the audit's correctness or coverage verdicts.
- **Origin:** 2026-08-11, operator decision during eight bare-plan audits of
  the now-retired #231 plan: the plan was materially ready for detail, but the
  audit offered only more findings and no stage-transition signal; reshaped
  2026-11-14 from a history-counting advisory to one static line.
- **Status:** not started.

**#167 — Make plain English the default writing style for every generated plan-detail file**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **Escalate to plan if:** the rubric change needs more than prompt text under
  `plan_tool/prompts/`.
- **What:** Change the `plan-tool detail` prompts so every generated per-step
  detail file is understandable in plain English on a first read. The change is
  a prompt-rubric delta: compare the rubric below with what
  `plan_tool/prompts/detail.md` already says (it already carries a plain-language
  top rule, a swap list, and an active-voice rule) and add only the missing
  items. Keep concrete file paths,
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
- **Design (reshaped 2026-11-14 from four steps to two):**
  1. Define the rubric delta for run-grade detail: lead with the outcome; **be
     to the point — say each thing once, no filler, no restated context**;
     expand or explain project abbreviations; separate required constraints
     from suggested implementation; and use a small concrete example instead of
     a dense abstract paragraph. Both directives (plain English and
     conciseness) target the descriptive prose only — they never reduce code
     anchors, paths, symbols, examples, or stated constraints. Add each item
     that `detail.md` does not already say to `detail.md`, and the reviewer
     wording to `detail-quality.md`. Preserve every full repo-relative path,
     symbol anchor, identifier, test reference, and required
     mechanical/compatibility sequence.
  2. Land it together with #497's shared plain-words swap list, so the swap list
     and the rubric are edited in one pass rather than twice.
- **Cut 2026-11-14 (do not re-open without new evidence):** mechanical
  readability checks (sentence length, undefined acronyms, buried outcomes) and
  an opt-in re-author path for existing bundles. The checks are a
  semantic-property proxy that fires on legitimate prose, which `CLAUDE.md`
  § "Validating a semantic property you cannot observe" and #497 refuse; a
  clarity finding comes from the model reviewer reading the rubric in
  `detail-quality.md`, not from a heuristic. New detail is the target; existing
  bundles are not rewritten.
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
  it been adopted. With the mechanical checks cut, no thresholds remain to
  source. Do not re-open without a concrete case where a self-stated rubric
  produced a materially worse result than a sourced one would have.
- **Effort:** small — `plan_tool/prompts/detail.md`,
  `plan_tool/prompts/detail-quality.md`, and the prompt-rendering tests; no
  parser or check code.
- **Risks / fallout:** simplistic readability rules can erase necessary precision.
  Treat paths, symbols, identifiers, code spans, test references, and stated
  mechanical/compatibility constraints as immutable facts and keep the rubric
  scoped to descriptive prose.
- **Dependencies:** lands together with #497 (shared swap list); complements
  #149 (compact structure). Jira-grade detail is retired, so this entry applies
  only to supported run-grade detail.
- **Scope contract:**
  - **Outcome:** newly authored plan detail is clear, direct plain English while
    retaining the actionable technical facts needed to implement and verify it.
  - **In scope:** `detail.md` and `detail-quality.md` rubric text (the delta
    against what they already say), and prompt-rendering tests.
  - **Out of scope / Non-goals:** deliberately not mechanical readability checks
    or thresholds (sentence length, undefined acronyms, buried outcomes) — a
    semantic-property proxy that fires on legitimate prose, refused by
    `CLAUDE.md` and #497; deliberately not an opt-in re-author path or any
    rewrite of existing bundles; changing plan-body prose; removing, weakening,
    or generalizing required evidence, file paths, symbols, tests, acceptance
    criteria, or mechanical constraints; changing implementation behavior;
    sourcing thresholds from an external writing standard (decided above).
  - **Allowed behavior changes:** new detail output may be more concise and less
    prescriptive; existing read compatibility remains.
  - **Allowed reorganization:** only the prompt text needed to use one rubric
    for supported run-grade detail, shared with #497's swap list.
  - **Verification:** a prompt-rendering test shows each rubric item appears in
    the rendered `detail.md` and `detail-quality.md` once, with the rubric
    stating that paths, symbols, examples, and constraints are never reduced.
    Review a sample run-grade detail for direct, outcome-first language without
    loss of anchors.
  - **Stop / defer:** if the delta against `detail.md` is empty, close this entry
    with that finding rather than adding text.
- **Approach:** `plan-tool`, direct. Prompt text only; no open architectural
  experiment.
- **Status:** not started. 2026-07-22 — two directives recorded: (1) the
  rubric explicitly includes **conciseness** (prose to the point, not
  verbose) alongside plain English, both aimed at descriptions only — code
  anchors and examples are never reduced; (2) the then-supported Jira-grade
  authoring lane applied this rubric at birth. That lane is retired;
  this entry now owns only existing run-grade surfaces. Extending the same
  rubric to **plan-body
  prose** (`create` output) is outside this entry's fence — promote it to
  its own entry when scheduling this work.

**#149 — Compact `detail` output: a compact required-H2 authoring schema (phase B is the only phase) — PLAN-AUTHORED (`detail-verbosity-compact-summary`)**

- **Labels:** Route `plan` · Readiness `ready` · Tier `architect` · Principle `untriaged`
- **What:** make `plan-tool detail` output less verbose with a **compact
  required detail schema** that changes what `detail` authors by default: merge
  Summary+Why into a single `Intent` and drop the Table of Contents. This is
  the only phase, because it is the part that reduces tokens and stale prose.
  **Deferred for run-grade re-baseline:** this plan's compact-schema authority
  names the retired Jira-grade lane. Do not preserve `plan_tool/jira_grade.py` as an
  alias source. Re-baseline the compact-schema phase on a run-grade-owned
  contract before execution; a complexity gate can then keep `low` steps
  always-compact while `medium`/`high` may expand only the section carrying
  the approach. The format version changes **explicitly through
  `DETAIL_FORMAT.md`** and its format-version marker, not as an implicit side
  effect of a prompt change.
  Legacy seven-section files stay valid on the **read** path via dual-token
  lookup — nothing is force-migrated; the write path emits compact only.
- **Optional, demoted — the `--summary` review surface (phase A).** A read-only
  `plan-tool detail <name> --summary` that prints one compact review card per
  step from existing detail files (spending no Claude, always exiting 0) is
  optional and not part of this entry's outcome. It renders from whatever
  sections a file has, so it does not depend on the compact schema and does not
  block it. The WIP plan still lists it as step 1 ("Phase A — ship first"), so
  the re-baseline this entry's Status requires also removes that step and
  wording from the plan; until then, do not run the plan as written. Take the
  cards only if the compact schema has shipped and an operator still wants them.
- **Why:** `_REQUIRED_H2_TOKENS` hard-requires seven sections, so even a
  one-line change authors ~70 lines and denser steps land at ~120–170; ToC is
  ceremony, Why duplicates Summary, and Implementation inflates into call-site
  inventories. Existing "intent over mechanics" guidance is inert because
  `detail-altitude` is advisory/non-apply-eligible and sibling tone-matching
  re-inflates new files. Length also compounds cost: `run` injects the full
  detail body into the implementer prompt (relates to #38's detail-length
  drift signal).
- **Approach:** `plan-tool` — the existing plan, re-baselined: phase B
  (compact authoring contract + complexity gate + sibling hygiene) and phase C
  (read-compat via dual-token lookup) are the scope; phase A is optional.
  Touches `plan_tool/detail.py`
  (`_REQUIRED_H2_TOKENS`/`_REQUIRED_H2_DISPLAY`/parse gate + read
  compatibility), `plan_tool/cli/authoring.py`, `plan_tool/prompts/detail.md` +
  `detail-quality.md`, `DETAIL_FORMAT.md`, `docs/how-to/pipeline/detail.md`, CLI-reference
  regen, and `tests/test_detail.py`.
- **Scope contract:**
  - **Outcome:** newly authored run-grade detail uses the compact required-H2
    set, at a stated format version in `DETAIL_FORMAT.md`; legacy seven-section
    files still read.
  - **In scope:** the compact schema and its explicit format-version change, the
    complexity gate, sibling-body hygiene, dual-token read compatibility, and
    their prompts, docs, and tests.
  - **Out of scope / Non-goals:** deliberately not the `--summary` cards as part
    of this outcome (optional and demoted above); the retired Jira-grade lane;
    an interactive detail wizard (the discarded #49); purity-prompt size (the
    discarded #133); auto-rewriting historical detail files.
  - **Allowed behavior changes:** `detail` authors the compact schema; the
    format version changes through `DETAIL_FORMAT.md`.
  - **Allowed reorganization:** the parse-gate token tables the dual-token read
    requires.
  - **Verification:** a freshly authored step has no Table of Contents and a
    single `Intent` section; a legacy seven-section file still parses; the
    format-version marker rejects an unsupported value as `DETAIL_FORMAT.md`
    states.
  - **Stop / defer:** if the re-baselined schema cannot name a run-grade-owned
    authority, stop and report rather than retaining the removed module.
- **Status:** a WIP plan `docs/implementation-plans/2-detail-verbosity-compact-summary.md`
  (status `planning`, 6 steps) is authored for this; its detail bundle is
  **incomplete** (steps 1–3 detailed, 4–6 pending) and it is
  registered in `.plan-tool/plans.json`. Re-baseline the WIP plan and its
  incomplete detail bundle on phase B before it runs (the former Jira-grade
  schema authority is removed, and the plan must not retain the removed module
  as a compatibility dependency); the plan's phase A step becomes optional. When
  the plan ships, its final step removes/marks this entry. The former terminal
  companion (#293, superseded) is not this entry's target surface.
- **Origin:** 2026-07-18 — filed to close the plan's dangling forward-reference
  to "BACKLOG #149" (the plan's step 6 and detail files cite it). Companion to
  #38 (detail length as a drift signal); reshaped 2026-11-14 to phase B only.

**#114 — Give `detail` and `completeness-audit` the same no-name plan-picker `run` already has, filtered to each command's applicable state**

- **Labels:** Route `plan` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** a human operator reports difficulty discovering which plan to name for `detail` or `completeness-audit`.
- **What:** Today only `run` accepts a missing plan name and falls back to an
  interactive picker (`run_cmd.py:_select_open_plan` over `_open_plan_entries`,
  which keeps `e.plan is not None and not e.plan.all_steps_done`). `detail`
  and `completeness-audit` make `name` a required positional
  (`authoring.py` `p_detail`, `completeness_cmd.py` `p_completeness`) and argparse-error when it's omitted — with no help
  discovering which plans are actually in the right state for that command.
  Generalize `run`'s picker so all three commands, given no name on a TTY, list the
  plans **applicable to that command** and let the user choose.
- **Per-command filter predicate (the applicable-state definition):**
  - `detail` → plans that **need detail**:
    `audit_detail_bundle_status(plan, path, repo_root).is_bare` (at least one step
    has no detail file). `.is_fully_bare` distinguishes freshly-created from
    partially-detailed.
  - `completeness-audit` → plans with a **complete detail
    bundle** (`not .is_bare`). A bare plan named explicitly remains accepted;
    the filter governs only what the picker offers, not audit capability.
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
  than copy-pasting into two commands. Model row output on `cmd_list`'s row builder
  (`inspect.py:140–179`) and `_select_open_plan`'s menu.
- **Effort:** medium — one shared picker helper + two parser changes (`name` →
  `nargs="?"`, `default=None`) + two call-site fallbacks + tests. No new plan-state
  primitive is needed; the tri-state composes from the helpers above.
- **Risks:** small. Making `name` optional must preserve the non-TTY / piped path as a
  hard error (rc=2) exactly like `run` — a picker must never block a scripted/CI
  invocation. Keep
  the MALFORMED handling (`e.plan is None`) `cmd_list` already does so unparseable
  entries don't crash the picker.
- **Dependencies:** none — every primitive already exists.
- **Approach (when unparked):** `plan-tool` — cross-cuts three command surfaces + a shared helper +
  tests, a natural fit for the create→detail→run pipeline.
- **Origin:** 2026-07-09 — requested to make the plan-consuming commands
  self-discoverable, extending `run`'s existing picker to `detail` and the
  completeness verbs.

**#69 — Close (or explicitly document) the standalone `reconcile-plan` unattended-apply gap** → promoted to IPPT-13 (2026-09-27)

### C. Investigations / decision-making





**#507 — A recorded `single` decision should stop the audit's mixed-step finding from recurring**

- **Labels:** Route `plan`
  · Readiness `decision-needed` (whether a recorded decision excuses the finding)
  · Tier `architect`
  · Principle `converge-on-correct-plan`
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
- **Origin:** 2026-10-19, Integration `construction-batch-driver` Gate 2 rounds 3 to 8.

**#495 — Decide the default number of conceptual-audit passes from measured per-pass yield**

- **Labels:** Route `direct`
  · Readiness `evidence-gated` (needs the audits above)
  · Tier `experienced`
  · Principle `none` — token cost of the conceptual audit; no grounding principle is served directly
- **What:** once enough audits carry `audit_pass_end` run-log events, compute
  how often audit passes 2 and 3 add a material finding that pass 1 did not,
  and decide whether the default `--audit-passes` (3 passes) can drop. The
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
- **Origin:** 2026-10-16 token-ledger analysis; logging shipped in Bitbucket pull
  requests 101 and 102 (not backlog ids).

**#381 — Measure whether lesson-equivalence confidence supports its drop threshold**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** instrumentation shows lessons are reused, or a wrong lesson drop (a false drop at the `0.6` floor) is observed.
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
  noise-floor observation (parked until a named A/B question exists) before creating a durable benchmark, calibrated
  probability, or shared confidence policy.
- **Outcome:** a short evidence table and a recommendation to keep, change,
  or stop using the numeric floor for lesson-drop decisions. No threshold or
  write behavior changes in this item.
- **Approach:** `direct` investigation; propose a scoped implementation only
  if the measured result warrants one.
- **Status:** parked 2026-11-14; no false drop observed, and lesson reuse is unconfirmed (`lessons-reuse-instrumentation` is idle).

**#380 — Decide what the scope guard emits instead of an `out-of-scope-findings` plan stub**

- **Labels:** Route `direct` (a decision record)
  · Readiness `decision-needed`
  · Tier `experienced` — it stays within existing contracts, but the records it decides on are written by `scope_guard.py` and emitted by both the reconcile and completeness loops, so the choice changes behavior across modules. A wrong choice shows up as a review finding against the backlog-routing rule, not as a failing test
  · Principle `untriaged`
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
    the retained `_iterate_reconcile_loop` helper is a candidate for source-level
    investigation, but no current reconcile CLI route enables its budget. Do
    not use the removed `--mode reconcile` route as a reproduction.
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
- **Origin:** 2026-09-16, found during #378's review of where out-of-scope
  findings land. Filed rather than folded into #378 because it changes tool
  output, not orchestration guidance.
- **Status:** not started.

**#111 — Rework the `orphaned-deliverable` identity model — the per-condition directory-token tension is irreducible under a single symbol set**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** the detector misfires (a false positive or false negative) on a real plan.
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
  bug — the shipped equilibrium is defensible. Distinct from the footprint
  over-work reduction (shipped) and #110 (`claim-vs-delivery` FP rate), though all
  three touch the same self-consistency detectors.
- **Effort:** small (the decision); the model that follows is a separate
  `plan-tool` item. **Approach (when unparked):** decision first (`direct` write-up), then
  `plan-tool` if a model change is chosen.
- **Dependencies:** none — #100 shipped the detector. No misfire on a real plan is cited; the five-round review's tradeoffs are accepted.
- **Origin:** 2026-07-09 — five-round high-effort workflow review of the
  `plan-self-consistency-gate` step commits; rounds 2–5 each fixed one direction
  of the tension and re-surfaced the other, converging only at "no CONFIRMED
  finding, accepted PLAUSIBLE tradeoffs" (the `stop-patching-file-a-backlog-entry`
  rule for a non-converging region).

**#110 — Measure `claim-vs-delivery` false-positive rate (incl. fuzzy near-miss misses) and decide its status**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `detect_claim_vs_delivery` (shipped in #100) is deliberately
  **advisory** on `smell_recs` — it never flips rc — until its false-positive
  rate is measured on real plans. This entry is the measurement and the
  decision it supports, nothing more. It pins a concrete data point: the fuzzy
  match `_claim_delivered` uses `SequenceMatcher.ratio()
  >= _NEAR_MISS_RATIO` (0.85) over whole tokens, so a claim clearly delivered by
  a related-but-differently-named symbol misses (`parse_plan` vs a declared
  `parser` scores ~0.75) and is reported as undelivered — advisory noise today.
- **Output of investigation:** run the detector across the repo's real plans
  (no Claude), bucket the findings into true/false positives, and record the
  rate. Apply `CLAUDE.md` § "Validating a semantic property you cannot observe"
  rule 5 (a high false-positive rate means kill, not tune):
  - **FP rate at or below about 1 in 5:** the detector stays advisory with the
    measured rate recorded; promotion to a blocking bucket is a separate
    follow-up (below), filed only on this result.
  - **FP rate above about 1 in 5:** keep it advisory or remove it. Do **not**
    tune `_NEAR_MISS_RATIO` or the token normalization to buy a lower rate.
- **Follow-ups, filed only if the measurement supports promotion (not part of
  this entry):** wiring the check into `create --iterate`'s own deterministic
  loop and the completeness-audit smell layer (`create --iterate` does not run
  it today, so a seam can surface rounds later in the audit), and the inverse
  check (a step whose headline intent maps to no acceptance criterion), which
  the current detector checks neither way. Each is its own entry.
- **Risks / fallout:** the detector's advisory status is a **settled
  decision, not an oversight** — `detect_claim_vs_delivery`'s docstring pins
  "stays advisory" on fuzzy-matching false positives (this entry's own
  `_NEAR_MISS_RATIO` data point above is exactly that risk). Any later
  promotion must not adopt the raw fuzzy `SequenceMatcher` matcher wholesale —
  measured precision or an exact-match-only subset first.
- **Scope contract** (cut back to the measurement 2026-11-14; the
  `create --iterate` wiring, the inverse check, and the severity/routing move
  are follow-ups, do not re-widen without updating this fence):
  - **Outcome:** a recorded true/false-positive count over the repo's real
    plans and a stated decision: stay advisory with the rate, or keep advisory
    or remove it because the rate is above about 1 in 5.
  - **In scope:** a no-Claude run of `plan_tool/review.py`'s
    `detect_claim_vs_delivery` over the repo's plans, the bucketed counts, and
    the decision note.
  - **Out of scope / Non-goals:** deliberately not tuning `_NEAR_MISS_RATIO`
    or token normalization (rule 5: a high false-positive rate means kill, not
    tune); deliberately not promoting the detector to `self_consistency_recs`
    or changing `create`'s convergence severity mapping; deliberately not the
    `create --iterate` wiring or the inverse (intent with no criterion) check
    — each is a follow-up filed only if the result supports promotion; any
    Claude-judged check on claim quality; the completeness-audit conceptual bar
    (`is_blocking_finding`); step schema changes (#268's carrier decision);
    exit-code conventions.
  - **Allowed behavior changes:** none.
  - **Allowed reorganization:** none.
  - **Verification:** the measurement's bucketed true/false-positive counts and
    the recorded decision.
  - **Stop / defer:** newly noticed criterion patterns needing judgment (not
    delivery tracing) go to the backlog, not into this check.
- **Effort:** small — a no-Claude measurement and a decision note.
  **Approach:** `direct`.
- **Dependencies:** none — #100 shipped the detector. #268 waits on this
  decision.
- **Origin:** 2026-07-09 — #100's `## Deferred` ("Promoting `claim-vs-delivery`
  to blocking … until its false-positive rate is measured") plus the high-effort
  workflow review's fuzzy near-miss finding on `review.py:3788`
  (`detect_claim_vs_delivery`); cut to the measurement 2026-11-14.

**#87 — Hash test files before the call so the test-authoring gate does not depend on `--commit` discipline**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What (the build, 2026-11-14):** hash each test file before the backend call
  and count a changed content hash after the call as authored, in place of the
  *post-call git-changed delta against a pre-call baseline of dirty paths*. A
  step's edit to an already-dirty shared test module changes its hash and
  counts, so the gate no longer depends on `--commit` to clear the tree between
  steps. The gate's observable stays binary (a test file's content changed
  during the call); test quality is not graded. A no-edit retry with no declared
  files stays on `run --step N --accept`; the hash check does not pass an
  unchanged file.
- **Why this is the build, not a question:** this is the most recurring gate
  problem in the history below (2026-07, 2026-10-06, 2026-10-08, 2026-10-15),
  and hand-added `enforce_test_authoring: false` exemptions are left sitting in
  plan frontmatter afterward. The `--commit` mandate in `CLAUDE.md` is a
  workaround that depends on operator discipline; a per-file hash removes that
  dependency.
- **Problem statement.** The test-authoring gate isolates a step's test coverage as the
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
  through 9 so a retry could advance. (2) *(Fixed 2026-10-22: the gate now unions the working-tree delta with backend-committed test paths, `launcher.py` `committed_changed_paths`; the per-file hash build keeps that union.)* The model committed its own work inside
  the call (a 49-file commit, step 10), so the working-tree delta was empty, the
  gate reported "no test file modified", and the suite gate never ran. Exemptions added by hand
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
    a no-edit retry whose tests already differ from the last green commit, for
    a step that declares no files, stays on `run --step N --accept` (decided
    2026-11-14: the hash check does not pass an unchanged file).
- **Cause (2) again, 2026-10-15 (`sibling-planned-input-paths`):** steps 1
  and 2 start clean under `run --all --commit`, author regression tests, and
  commit them inside the backend call (`373997be9`, `bf44003f3`). Both return
  with an empty working-tree test delta and fail the authorship gate. Inspection,
  mutation verification and independent full-suite runs establish authored
  coverage; `run --step N --accept --commit` runs the suite again and advances
  each step. No gate exemption is needed. This reproduces the committed-delta
  case independently of the dirty-baseline case; keep both in any remedy matrix.
- **Scope contract:**
  - **Outcome:** a step that edits a test file passes the authorship gate when
    that file was already dirty before the call, with no `--commit` needed
    between steps, and a step that changes no test file's content still fails
    it.
  - **In scope:** the pre-call per-file content-hash snapshot and the
    post-call comparison in `launcher.py`'s test-authoring gate (keeping the
    committed-path union), and tests.
  - **Out of scope / Non-goals:** deliberately not passing a no-edit retry whose
    tests merely differ from the last green commit (that stays on
    `run --step N --accept`); grading test quality; a prompt rule telling the
    model not to commit (not a guarantee); removing the `--commit` mandate from
    `CLAUDE.md` in the same change (a follow-up once the gate ships); the
    #455 failure-receipt work.
  - **Allowed behavior changes:** the gate stops blocking a step whose edit to
    an already-dirty test file the old path-delta masked.
  - **Allowed reorganization:** none.
  - **Verification:** a test with a dirty shared test file edited by the next
    step passes; a test where the step changes no test file fails; a test
    where the model commits its own test edit inside the call still passes;
    verify by mutation that reverting to the path delta turns the first test
    red.
  - **Stop / defer:** if hashing every test file is too slow on a large tree,
    hash only the step's declared and changed-candidate test files and record
    the choice.
- **Effort:** medium — a snapshot and comparison in the gate, plus the tests.
- **Approach:** `direct` — one gate in `launcher.py` with a settled design.
- **Dependencies:** the `--commit`-on-multi-step-`run` mandate in CLAUDE.md is the
  current workaround this supersedes.
- **Origin:** 2026-07-04 — surfaced running visualize-split-criteria without
  `--commit`; root cause corrected 2026-07-05 after the `--commit` known-limit
  rule landed upstream; turned from an investigation into the per-file hash
  build 2026-11-14.

**#71 — [Decision] Define the `detail --reconcile` refusal-token shape (enforce vs. record)**

- **Labels:** Route `direct`
  · Readiness `parked`
  · Tier `architect`
  · Principle `converge-on-correct-plan` — a refusal token the apply layer can check
- **Unpark when:** a `detail --reconcile` apply narrows scope or softens an acceptance criterion despite the prompt's prose refusal policy.
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
    finding, surface it, no action)? The prose policy works correctly today (no failure observed),
    so enforcement is the riskier, higher-cost path; recording is the cheaper
    floor.
  - **Parser seam:** where it threads through `review.py` (alongside `Redirect`
    / `parse_redirect_block`) and the `Recommendation` / `Annotation` model.
- **Output:** a short design note (chosen token shape + enforce-vs-record
  stance + parser seam) that converts the decision into a buildable
  `plan-tool` item.
- **Effort:** small (the decision + write-up); the build that follows is the
  separate MINOR.
- **Approach (when unparked):** decision first (`direct` write-up), then `plan-tool` to build
  the chosen shape.
- **Dependencies:** none.
- **Origin:** 2026-06-22 — draining the bug backlog surfaced the
  refusal-signal work as a forward-looking design decision, not a correctness
  bug.

**#141 — Document the 4h jira story-size floor against a `--max-hours` below it, and warn on `--max-hours < 4`**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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
- **Decision (2026-11-14): option (c), then close.** The overlap is advisory
  noise reachable only with a pathological config, and two high-effort review
  rounds already churned on this exact region: a first attempt clamped the
  *prompt* floor to `min(4, max_hours)` but left the *lint* floor fixed, which
  made the two diverge (worse). The work is one doc line in `JIRA_FORMAT.md`
  stating that a `--max-hours` below the 4h floor makes every story advisory-lint
  as below the floor, plus a one-line warning when `--max-hours < 4`. The
  current shipped state is a **fixed 4h floor everywhere** (lint + prompt), with
  the prompt prose deferring to a lower `--max-hours` target.
- **Scope contract:**
  - **Outcome:** `JIRA_FORMAT.md` documents the `--max-hours < 4` overlap and
    `jira` prints a one-line warning when `--max-hours` is below 4; the entry
    then closes.
  - **In scope:** the `JIRA_FORMAT.md` line, the `--max-hours < 4` warning in
    `plan_tool/cli/jira_cmd.py`, and a test for the warning.
  - **Out of scope / Non-goals:** deliberately not threading `max_hours` into
    `lint_story_size` / `partition_lint_findings` / `_emit_story_warnings`
    (option a: `jira --lint` has no `--max-hours` context, so the surfaces would
    still disagree between `export` and `--lint`); deliberately not forbidding
    or clamping `--max-hours` below the floor (option b: changes `--max-hours`
    semantics); changing the 4h constant or the lint's advisory status.
  - **Allowed behavior changes:** one stderr warning on `--max-hours < 4`; exit
    code unchanged.
  - **Allowed reorganization:** none.
  - **Verification:** `--max-hours 3` prints the warning and exits as before;
    `--max-hours 4` and the default print none.
  - **Stop / defer:** if the warning needs plumbing beyond `jira_cmd.py`, ship
    the doc line alone.
- **Effort:** small. **Approach:** `direct` — one doc line and one warning.
- **Quality/accuracy lens:** low — advisory-only noise reachable only by a
  ceiling-below-floor misconfiguration; the default (`--max-hours 8`) is unaffected.
- **Origin:** 2026-07-16 — surfaced by the round-2 code review of the story-size
  floor feature (the fixed-floor-vs-configurable-ceiling tension), deferred here
  rather than patched a third time per the convergence escape hatch; narrowed
  to option (c) 2026-11-14.

**#210 — Decide whether the per-step purity Claude pass earns its cost: it has never reported a finding, and 87.5% of its calls never return**

- **Labels:** Route `direct` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** an independently justified audit has invoked `--purity` and recorded an outcome (zero findings so far); decide keep, opt-in, or cut from those outcomes. Passive observation is settled and user-confirmed; no dedicated measurement.
- **What:** the `completeness-audit` phase-1 per-step MIXED-STEP purity pass
  (`purity_scan` phase) spends one Claude call per step per audit. Decide,
  on measurement, whether to keep it, invert its default to off, or cut it
  — the same measure-then-decide treatment that retired the
  per-`change_type` test-ordering contract (CLAUDE.md § "Withdrawn").
- **Absorbs #151 (merged 2026-11-14):**
  `completeness_phases._collect_purity_split_findings` calls
  `detail.collect_detail_quality_findings` (`prompts/detail-quality.md`, ~140
  KB), which asks for repo-wide grounding, altitude advisories and a
  mixed-step verdict, then keeps only medium `granularity-split`
  recommendations. A cache hit costs no model call; a real miss still sends
  the full prompt and discards most of the reply. Decide keep or cut first.
  Only if the pass is kept, in order: (1) no call when the purity cache can
  satisfy the audit, (2) reuse the purity subset from `detail`'s fully
  consumed authoring call, (3) a narrow purity-only mode built from step
  metadata and `## Implementation` / `## Tests`, with no repo-wide grounding.
  Do not weaken `detail`'s authoring call: its repo-wide grounding is
  intentional, and a declared-files cache key cannot stand in for it. Out of
  scope: parallel purity fan-out and payload-size work (#38). The work is
  scheduled only if this decision keeps the pass, and then as its own entry
  with a scope contract and acceptance test.
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
- **Status:** parked; passive observation only, settled 2026-08-20 (user-confirmed).

**#212 — `apply_finding` rewrites a step but can leave its `intent` stale: one instruction in `apply-finding.md`**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `Step.intent` has shipped (plan `2-intent-scope-fence.md`), and
  `plan_tool/launcher.py:apply_finding` rewrites a step's title, files, and
  acceptance criteria from an audit finding while leaving `intent` untouched.
  The result can be a one-line why that no longer describes the step but still
  renders into the `detail`, `run`, and conceptual-audit prompts as
  authoritative input — the "a stale intent is worse than an absent one" hazard
  that plan's Risks section names, arriving through a verb that plan does not
  cover. The remedy is **one instruction in `plan_tool/prompts/apply-finding.md`**
  telling the model to keep `intent` consistent with the step when it rewrites
  the step (revise the one-line why to match, or leave it when the rewrite does
  not change the step's purpose). `apply_finding` is a Claude-driven edit, so
  the consistency decision belongs in that prompt, not in a code path.
- **Decision (2026-11-14): do not clear `intent`.** The earlier remedy, a code
  rule that clears the field on a rewrite, conflicts with the shipped
  intent-required rule (`CLAUDE.md` § "The two intent reversals"): a missing
  intent is a `medium` self-consistency finding that blocks completeness
  convergence, so clearing a rewritten step's intent would create a blocking
  finding. Conceptual findings are also now applied by hand, so
  `apply_finding` rarely rewrites steps.
- **Why it is filed rather than folded in:** `2-intent-scope-fence.md` scopes
  propagation to the four **structural** verbs (`split`, `merge`, `scope-out`,
  `reground`). `apply_finding` is not one of them, and that plan's
  `## Audit guardrails` fences propagation past those four out **by
  construction**. Surfaced by its own round-1 conceptual audit, which correctly
  tagged it `[out-of-scope-deferred]` and cited the guardrail as its reason for
  not expanding the plan.
- **Dependencies:** none — `2-intent-scope-fence.md` shipped the field, so the
  one blocker this entry had is clear.
- **Effort:** small — one prompt instruction and a prompt-rendering test.
- **Scope contract:**
  - **Outcome:** the `apply-finding` prompt tells the model to keep a rewritten
    step's `intent` consistent with the step.
  - **In scope:** one instruction in `plan_tool/prompts/apply-finding.md` and
    its prompt-rendering test.
  - **Out of scope / Non-goals:** deliberately not clearing `intent` in
    `apply_finding` (it would create a blocking missing-intent finding, above);
    a code path that rewrites or re-derives intent; a separate Claude call to
    re-derive it;
    any intent-vs-work agreement check (permanently refused — see CLAUDE.md
    § "Validating a semantic property you cannot observe", "The two intent
    reversals"); the four structural verbs, which `2-intent-scope-fence.md`
    already owns.
  - **Allowed behavior changes:** `apply_finding` prompt text only.
  - **Allowed reorganization:** none.
  - **Verification:** the rendered `apply-finding` prompt contains the
    instruction; no code path changes, so a step with no intent is
    byte-identical to today.
  - **Stop / defer:** park this entry if `apply_finding` is found to rarely
    rewrite steps in practice; record that as the reason.
- **Approach:** `direct` — one prompt line and one test.
- **Quality:** `grounding` — keeps an authoritative input from going stale.
- **Origin:** 2026-08-01, round-1 conceptual audit of `2-intent-scope-fence.md`;
  remedy changed from clearing to a prompt instruction 2026-11-14.
- **Status:** not started; unblocked (that plan's step 1 landed the field).

**#228 — A deterministic enumeration/count drift check across a plan and its detail bundle**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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
  `ROADMAP_FORMAT.md`, `RUNBOOK.md`, `docs/how-to/use-cases.md`, and a docstring, and it
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

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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

**#391 — Optional handoff-register reconciliation in the installed `plan-tool` skill routers**

- **Labels:** Route `plan`
  · Readiness `parked`
  · Tier `architect` — defines an installed-skill contract at the boundary between external handoff context and plan-tool's authoritative artifacts
  · Principle `untriaged`
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
- **Dependencies:** gated on the Integration AI-DLC-to-plan-tool register
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
- **Unpark when:** Integration's first controlled register reconciliation shows a need the router could not meet by hand.
- **Origin:** 2026-09-17, Integration AI-DLC-to-plan-tool handoff work. The first
  register tracks cross-engine evidence without becoming Roadmap or seed input;
  the reusable capability is its optional, human-controlled reconciliation
  protocol rather than Integration-specific connector behavior.
- **Status:** parked 2026-11-14.

### D. Process / hygiene

**#497 — Keep one plain-words swap list for the detail, audit, and apply prompts**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `write-for-the-human`
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
- **Origin:** 2026-10-19 review of generated plan and roadmap prose.

**#431 — `_gate_correction`'s prefix matcher → one exhaustive `kind → remedy` table**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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
- **Why:** five kinds already needed a hand-curated override
  (`duplicate-inherited-decision`, `duplicate-feedback-id`,
  `duplicate-store-reference`, `duplicate-stack-concern`,
  `ordering-plan-id-duplicate`) after shipping
  with the wrong, rename-shaped remedy — direct evidence the prefix heuristic
  gets it wrong in practice, not just in theory. A future `VIOLATION_*` kind
  whose string happens to start with an already-claimed prefix but needs a
  different remedy will silently render the wrong retry instruction to a
  model, and the exhaustiveness test stays green because it only checks
  generic-vs-specific, never specific-vs-*correct*-specific.
- **Approach sketch (reshaped 2026-11-14):** replace the prefix tuples and
  `_DROP_EXTRA_ROWS_GATE_KINDS` with one exhaustive `kind → remedy` table in
  `roadmap_candidate.py` covering every `VIOLATION_*` constant in
  `roadmap_gates.py` (currently 81), and read the remedy from the table in
  `_gate_correction`. Add a test that every `VIOLATION_*` constant appears in
  the table, so a new kind fails the test until someone chooses its remedy.
  This makes the decision explicit per kind, where the author adds the kind,
  without touching the ~95 `Violation(...)` construction sites.
- **Deliberately not a `remedy_shape` field on `Violation`:** setting the remedy
  at each of ~95 construction sites is more churn than the property needs. The
  table gives the same per-kind explicitness and the same new-kind failure at a
  fraction of the change. Revisit only if the table drifts from the checks
  that raise the kinds.
- **Scope contract:**
  - **Outcome:** a new `VIOLATION_*` kind cannot land without an explicit
    remedy choice: a test fails until the kind has a row in the
    `kind → remedy` table.
  - **In scope:** the `kind → remedy` table in `roadmap_candidate.py`,
    `_gate_correction`'s dispatch from it, retiring the prefix tuples and
    `_DROP_EXTRA_ROWS_GATE_KINDS`, and the every-constant-is-in-the-table test.
  - **Out of scope / Non-goals:** deliberately not changing `Violation`'s shape
    or its ~95 construction sites in `roadmap_gates.py` (the table delivers the
    explicit per-kind decision without that churn); any change to a violation's
    `message` text, or to which remedy each existing kind gets today — this is
    a mechanism change, not a remedy re-audit (the current mapping is already
    verified correct; kinds in `_INTENTIONALLY_GENERIC_GATE_KINDS` map to the
    generic remedy explicitly in the table).
  - **Allowed behavior changes:** none; every existing kind renders the same
    correction text.
  - **Allowed reorganization:** the table replaces the prefix tuples in
    `_gate_correction`.
  - **Verification:** a test that every `VIOLATION_*` constant in
    `roadmap_gates.py` is a key of the table, and a test that each existing
    kind's rendered correction equals today's (captured before the change);
    verify by mutation that adding a constant without a table row turns the
    first test red.
  - **Stop / defer:** if a kind's remedy depends on the violation's fields
    rather than the kind alone (as the ordering-reference condition does), keep
    that field-keyed branch and table the kind to it explicitly.
- **Effort:** small — one table, one dispatch change, and two tests; no
  construction-site sweep.
- **Approach:** direct.
- **Origin:** 2026-09-27, roadmap-candidate gate-correction review pass 5,
  finding 3 (`plan_tool/roadmap_candidate.py:_gate_correction`) — raised after
  three prior passes (R1.5, P2.1, P3.1) each fixed one more instance of the
  same false-friend-prefix shape; reshaped 2026-11-14 from a construction-site
  `remedy_shape` field to an exhaustive table.
- **Status:** not started.

**#432 — `render_candidate_question_prompt` still reads its template with a bare, unguarded `read_text()`**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **Start here:** `plan_tool/roadmap_candidate_review.py` (`render_candidate_question_prompt`, the two `read_text` sites) and `tests/test_roadmap_candidate_review.py`.
- **Precedent:** `plan_tool/roadmap_candidate_run.py:1106` (`render_candidate_delta_prompt` reads its template through `read_roadmap_text` with a local `unreadable_template` closure); `read_roadmap_text` is already imported at line 21 of that module.
- **Settled decisions to respect:** raise `CandidateReviewError` (this module's convention), not `CandidateProposalError`; no new named per-module wrapper function (flagged and removed in pass 7, P7.1); leave the caller's `except OSError` handling alone.
- **Done when:** a missing or unreadable `roadmap-candidate-questions.md` raises `CandidateReviewError` naming the file at both read sites, the entry states the result status a missing template yields (`refused`, which the caller maps `CandidateReviewError` to, or `failed`, which it maps `OSError` to), and a test pins both; the focused tests are green.
- **Reviewer:** unassigned
- **What:** `roadmap_candidate_review.render_candidate_question_prompt` (two
  call sites, lines ~768 and ~797) reads `roadmap-candidate-questions.md` via
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

**#355 — "second-KeyboardInterrupt-safe" is a per-call-site convention in the roadmap candidate flows, not a property `RunLogWriter` enforces**

- **Labels:** Route `plan` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** a lost or corrupt run log is attributed to a double Ctrl-C.
- **What:** `RunLogWriter`'s `phase_end`, `run_end`, `parse_failure`, and
  `run_interrupted` methods do not guarantee that a second
  `KeyboardInterrupt` is best-effort only. The eight terminal-record calls
  inside the candidate proposal and review flows' `try`/`finally` blocks are
  individually guarded today, but each future caller must remember the
  convention with no API, lint, or type-level enforcement — and the
  convention's own reach is incomplete: `logger.phase_start(...)` is called
  *before* the `try:` block in all four candidate-flow entry points
  (`run_initial_candidate_proposal`, `generate_candidate_question`,
  `request_replacement`, `_edit_structural_candidate`), so a `KeyboardInterrupt` landing during that call
  (a real `os.open`/`os.write` plus a lock-guarded in-flight snapshot write)
  still escapes every guard uncaught.
- **Absorbs #360 (merged 2026-11-14):** `run_initial_candidate_proposal`
  records `run_interrupted` with `contextlib.suppress(KeyboardInterrupt)`
  inline, and `roadmap_candidate_review.py` records it inside
  `_interrupted_result`. If a best-effort write contract is settled on
  `RunLogWriter`, both call sites use it and the duplicate falls out; each
  caller keeps constructing its own result type. No standalone helper.
  Acceptance for this part: a second `KeyboardInterrupt` during
  `run_interrupted` still lets each caller return its interrupted result; if
  the chosen contract leaves the raw methods in place, the duplicate suppress
  in the two call sites is recorded here as accepted or removed.
- **Why parked:** one live gap is now known (the pre-`try` `phase_start`
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
- **Approach (when unparked):** `plan-tool` — this shared-class contract change needs its own
  scoped plan and bare/detail audit gates, rather than a direct edit.
- **Origin:** 2026-09-04, roadmap candidate-context review pass 5; confirmed
  as the appropriate deferred structural concern by pass 6 on 2026-09-07
  (`plan_tool/roadmap_candidate_run.py:844`, line numbers as of that pass);
  two further live instances deferred here by pass 7 on 2026-09-08
  (`plan_tool/roadmap_candidate_run.py:628`,
  `plan_tool/roadmap_candidate_review.py:728,885`, same caveat; a third
  site in the since-deleted `roadmap_revision_run.py`), per explicit user direction not
  to patch a fifth site inline.
- **Status:** parked 2026-11-14; the live gap (pre-`try` `phase_start`) affects a best-effort diagnostics write, not results.

**#349 — Consider migrating the roadmap stage loop's hand-rolled status channel onto `progress.py`'s shared reporter**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** roadmap operators report silent long stages (for example, a missing heartbeat).
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
- **Absorbs #342 (merged 2026-11-14):** whether `status_callback` (bounded
  stderr facts) and `RunLoggerLike` (structured JSONL events) should be one
  seam. They thread through near-identical signatures in `roadmap.py`, fire at
  close to the same transitions, and are wired inconsistently: `cmd_roadmap`
  passes `status_callback=note` and no `run_logger`, while
  `_cmd_roadmap_materialize` builds a real `run_logger` and never wires
  `status_callback`. Decide it as part of this migration question, not
  separately.
- **Why not fixed inline:** a real architectural migration — every
  `_emit_roadmap_status`/`_emit_stage_retry_status`/`_StageStopReporter`
  call site across the stage loop, both revision flows, and their tests
  would need to move onto `ProgressReporter`'s lifecycle and vocabulary,
  which may not even fit roadmap's per-stage-not-per-attempt reporting
  shape without its own extension — a decision and a design pass, not a
  proportional fix to make now. The `status_callback` vs. `RunLoggerLike` unification question (formerly
  #342) is part of this entry; see "Absorbs" above.
- **Effort:** large — a genuine cross-cutting migration, not a local
  refactor.
- **Dependencies:** none (the former #342 is folded in).
- **Approach (when unparked):** decision first.
- **Origin:** 2026-09-02, round-14 `/code-review` pass (full
  `77e1aeb7..HEAD` to-be-pushed range) on
  `2-roadmap-stage-lifecycle-output.md`'s landed diff.
- **Status:** parked 2026-11-14; no observed operator problem. This entry stays the single umbrella for the roadmap status-line cluster.

**#326 — Reconsider where the sampler checkpoint lives (bolted onto `SavedReview`/`save_review`)**

- **Labels:** Route `direct` · Readiness `ready` · Tier `architect` · Principle `untriaged`
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
  fighting the abstractions it's built on rather than fitting them. A full
  redesign (migrating to `checkpoint.py`'s primitive, or a purpose-built
  persisted shape) is a deliberate architectural decision, not something to
  hand-apply mid-review; only the path move below is in scope.
- **Effort:** small — the first slice moves one path constant and its
  writer/reader sites. **Value:** readers of the reports directory no longer
  need a `path != checkpoint_path` / `path.name != SAMPLER_CHECKPOINT_FILENAME`
  exclusion (today a fixed, non-timestamped filename lives alongside
  timestamped saved reviews, so each reader needs one), which removes the
  hazard waiting for the next reader.
- **Approach:** direct change. First slice: move the sampler checkpoint file
  out of the plan's `reports/` directory into its own path
  (`sampler_checkpoint_path` in `review_persistence.py`), then delete the
  per-reader exclusions. **Deliberately not** the migration to
  `checkpoint.py`'s content-hash primitive or a purpose-built persisted shape
  in this slice: migrate only if the remaining `save_review` special-casing
  (`_checkpoint_path`, `sampler_state`, `checkpoint_audit_revision`) causes a
  defect. Reshaped 2026-11-14 from a medium-to-large redesign.

**#323 — Share the ordering/plan reconciliation between `--view walk` and `--view html`**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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

**#324 — `jira --output` lacks the directory/trailing-separator check `roadmap --view html --output` has**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `roadmap --view html --output PATH`
  (`cli/roadmap_cmd.py:cmd_roadmap`, the html branch) rejects a destination
  that names a directory, carries a trailing separator on a path that
  doesn't exist yet, or raises `PermissionError` out of `Path.is_dir()` —
  with one specific message and exit code for each. `jira --output PATH`
  (`cli/jira_cmd.py:133`, `Path(args.output).resolve() if args.output else
  None`) performs none of this: the identical operator mistake
  (`jira <slug> --output some_dir/`) proceeds straight to opening a file at
  that path with no directory/trailing-slash check at all.
- **Why now — not fixed alongside `--view html`:** `jira_cmd.py` is
  pre-existing, unrelated code the `--view html` work never touched, and
  fixing it changes a second command's behavior.
- **Fix:** give `jira --output` the same directory / trailing-separator
  check `roadmap --view html --output` performs (one message and exit code
  per case). Extract the existing roadmap helper only if it lifts out
  trivially; otherwise a small `jira`-local check is enough.
- **Deliberately not:** a "shared CLI infrastructure" framing (a shared
  `--output` validator in `cli/console.py` or a new leaf, plus thinning the
  `--view html` branch of `_cmd_roadmap_view`). Two surfaces do not justify
  it; revisit when a third `--output` surface exists. Reshaped 2026-11-14.
- **Effort:** small. **Value:** `jira <slug> --output some_dir/` gets the same
  clear error as the roadmap command instead of failing at file open.

**#325 — Check a valid id of the wrong row kind in reference lists once, in the gates**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `roadmap_view.resolve_id_of_kind` warns at render time when an
  entity-typed reference (a `REFERENCE`-typed field or an `entity_ids` list)
  resolves to a row of the wrong kind. Other cross-artifact reference-id lists
  rendered by `roadmap_html.py` (`component.pattern_ids`,
  `component.constraint_ids`, `component.store_ids`, `plan.component_ids`, a
  row's `anchor_ids` / `consuming_plan_ids`, ordering's `depends_on` /
  `assumption_targets`) resolve through plain `_ref_list` / `resolve_id` with
  no kind check, so a *valid id of the wrong kind* in one of them renders as a
  confident link.
- **Premise (checked 2026-11-14):** cross-kind id *collisions* cannot reach a
  gated version: `check_duplicate_row_ids` (`duplicate-row-id`,
  `roadmap_gates.py`) requires row ids to be unique across every row kind in
  every artifact. What remains is a reference whose id exists but names the
  wrong kind of row.
- **Fix:** if that gap matters, check it once in the gates, where a violation
  is retried and remedied, rather than as render-time warnings at about 8 view
  sites. First step: confirm whether an existing reference-resolution gate
  already covers these lists and which of them it leaves open; add a gate
  check only for the open ones. Otherwise close this entry as not worth doing.
- **Scope contract:**
  - **Outcome:** a wrong-kind reference in the listed fields is a gate
    violation with a retryable remedy, or the entry is dropped.
  - **In scope:** `plan_tool/roadmap_gates.py` (one reference-kind check over
    the listed fields) and its tests.
  - **Out of scope / Non-goals:** deliberately not render-time warnings at the
    `roadmap_html.py` / `roadmap_view.py` call sites (the gate makes them
    unreachable for gated versions); deliberately not folding
    `_plans_block`'s ad hoc "does not name a plan" branch into
    `resolve_id_of_kind` here; no change to `resolve_id_of_kind`'s signature
    or `KIND_*` vocabulary; no multi-kind generalization.
  - **Allowed behavior changes:** a wrong-kind reference fails the gate.
  - **Verification:** a fixture per newly-checked field with a wrong-kind id,
    asserting the violation names the field and id.
  - **Stop / defer:** if anchors are genuinely polymorphic (several valid
    kinds per anchor), defer those fields with a new entry rather than
    guessing a single expected kind.
- **Effort:** small. **Value:** low — closes a narrow remaining gap at the
  point where it can be retried. Reshaped 2026-11-14 from a render-time
  sweep over about 8 view sites.

**#270 — `CliBackend.batch_output` is set by every backend but never read**

- **Labels:** Route `direct`
  · Readiness `decision-needed`
  · Tier `architect`
  · Principle `untriaged`
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

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `create.py:8735`'s `_render_testing_strategy()` appends a
  "Per-step test strategy" block to every plan's `## Testing` section (called
  from `_render_plan_body` at `create.py:8904`), one bullet per step. For
  code steps the bullet text is byte-identical regardless of `change_type` —
  `_TESTING_STRATEGY_BY_CHANGE_TYPE` at `create.py:417` maps both
  `refactor` and `feature` to the same sentence ("tests covering the
  behavior this step changes; green before completion."); only `non_code`
  differs. Nothing downstream reads the rendered block back: the run-time
  test-authoring gate (`launcher.py:990`'s `_test_directive()` and
  `launcher.py:1053`'s `_step_requires_test_authoring()`) derives its
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
    (flagged but explicitly deferred by the comment above `create.py:417`) —
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

**#278 — `materialize_plan_seed` and `materialize_and_diff_one_plan` duplicate their "acquire-or-reuse a writer guard" branch**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** the next change touches either function's writer-guard logic; fold the extraction into that change.
- **What:** Both functions in `plan_tool/roadmap.py` repeat an identical
  "acquire a fresh writer guard if none was supplied, else validate and
  reuse the caller's" branch before delegating to their own private twin
  implementation.
- **Why:** a bug fix to the reuse/validation logic must be applied in both
  places by hand, with nothing enforcing they stay in sync.
- **Approach:** `direct`, but not fully mechanical — extraction needs
  `_materialize_plan_seed` to gain a `writer_token` parameter to forward,
  which it does not currently have.
- **Status:** parked 2026-11-14; no observed drift between the two functions.
- **Origin:** 2026-08-14, `/code-review` pass on the local-revision-observability
  merge's follow-up direct fixes.

**#89 — Extend `--commit` to `reconcile-code` / `reconcile-plan` (orphaned saved reports)**

- **Labels:** Route `plan`
  · Readiness `ready` (sequence after the BUG_BACKLOG.md entry on `--commit` staging the whole tree; see Dependencies)
  · Tier `experienced`
  · Principle `untriaged` — commit hygiene; it may bear on `survive-interruption`, which the entry does not say
- **What:** `--commit` is accepted by four surfaces — `run` (per-step green
  commits), `detail`, `completeness-audit`, and `manifest sweep`/archive.
  `reconcile-plan` and `reconcile-code` mutate the repo (plan-side or
  code-side edits) and also write a saved audit report, but leave the working
  tree dirty. Extend `--commit` to those two verbs, each committing **its
  own** edits **and** the saved report: `save_review`
  (`review_persistence.py`) writes `<ts>-run-reconcile.json` /
  `<ts>-detail-reconcile.json` to `plan-details/<slug>/reports/`
  unconditionally (unless `--no-save`) with no git operation of its own, so
  the report is exactly as orphan-prone as the edits the audit makes.
- **Evidence it recurs:** two `reconcile-code` `run-reconcile.json` reports
  (`audit-pass-persistence`, step 3, 2026-08-31 23:12/23:18 UTC) sat orphaned
  — untracked, uncommitted — for a day. The operating habit at the time was to
  sweep saved reports into their own dedicated commit (`644be98a` "save
  reconcile-code reports", `881f8ba3`), but that habit lapsed once six
  subsequent code-fix commits (`08af949d` through `306c9bd9`) landed
  back-to-back with no report files staged at all — nothing in the tool
  forced or reminded either commit to happen.
- **Scope contract:**
  - **Outcome:** `reconcile-plan` and `reconcile-code` accept `--commit` and
    end on a clean tree, with the reconcile edits and the saved report in the
    commit.
  - **In scope:** `--commit` on those two verbs (the `detail`-style meaning:
    one authoring-edit commit, not `run`'s per-step green commits), the
    help text distinguishing the two meanings, and tests.
  - **Out of scope / Non-goals:** deliberately not `create`, `split`, `merge`,
    `scope-out`, or `annotate` (cut 2026-11-14): no gap has been observed on
    them, and each would need its own commit-unit decision; re-open one only
    when someone observes it orphaning files. No change to `run`'s per-step
    commits or to the clean-tree precondition.
  - **Allowed behavior changes:** the two verbs gain an opt-in flag; no
    default changes.
  - **Verification:** a reconcile run with `--commit` leaves no untracked
    report and no dirty edit; without the flag behavior is unchanged.
  - **Stop / defer:** if a verb cannot enumerate its footprint without new
    bookkeeping, ship the other and file the rest.
- **Design notes:** respect "commit only when the user asks": `--commit` is the
  explicit opt-in. Bounded-commits rule still applies — one concern per commit.
- **Effort:** small per verb (a `git add <its outputs> + commit` behind the
  flag), medium overall.
- **Approach:** `plan-tool` (a flag + commit-unit decision per verb) or `direct`
  one verb at a time.
- **Dependencies:** land the BUG_BACKLOG.md entry "`--commit` stages the whole working tree with
  `git add -A` ..." first (`commit_all` stages with a bare
  `git add -A`; extending `--commit` to more verbs would spread its
  over-staging hazard). Complements the `run --commit` mandate and [#87](#c-investigations--decision-making).
- **Origin:** 2026-07-05 — user, after `create` had to be hand-committed while
  building the auto-bridge-structural-remedies plan; narrowed 2026-11-14.

**#83 — End-to-end bare-plan action-surface regression harness**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** Add one integration fixture driving `completeness-audit` on bare
  and partially-detailed plans. Verify conceptual findings remain reported for
  session-directed edits and deterministic detail-level writers stay withheld.
  Check stderr, grouped output, saved markdown, sidecar replay, and next steps
  for consistent detail coverage and actionable surviving commands.
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
  deterministic iterate-loop action gates separately; this item adds
  the end-to-end leak check across all surfaces.

**#79 — Finish the lenient JSON-envelope slice; the measured do-not-merge list stays (most of the original duplicate-helper list turned out not to be duplication)**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `none` — consolidation; its claims need re-verifying before any merge
- **Absorbs #300 (merged 2026-11-14):** finish the `response_contract.py`
  migration for the two heading regexes of the same shape,
  `launcher.py:_VALIDATION_RE` and `review.py:_REDIRECT_HEADING_RE`, as one
  direct batch with the JSON slice. `_REDIRECT_HEADING_RE` bounds the
  structural sub-block parser: keep its blank-line anchoring (`(?:\A|\r?\n[
  \t]*\r?\n)`) exactly as it is.
- **What:** an AST pass that normalizes away docstrings, function names, and
  argument names found, on 2026-08-02 over `plan_tool/` (~91k lines), 6
  exact-duplicate function groups / 7 redundant copies, and showed that most of
  this entry's original list was not duplication. Every one of those groups
  has since been merged or removed: `tests/test_duplication.py` holds a zero
  baseline, with one allowlisted pair (the discarded #273). What remains is the
  lenient JSON-envelope slice below, and the do-not-merge list, which
  `tests/test_duplication.py` cites.
- **Remaining extract — lenient JSON-envelope slice (4 local sites):** object
  `find("{")…rfind("}")` at `create.py:4417`, `lessons.py:782` and
  `lessons.py:1479`, and array `find("[")…rfind("]")` at `jira.py:883`. These are
  statement blocks inside larger parse functions, not standalone functions, so
  the AST pass does not see them: verify each by hand before folding.
  `plan_tool/response_contract.py:JsonResponseContract` is the bracket-
  parameterized helper that already serves `foundational_logic.py`, `gates.py`
  and `annotate.py`; migrating these four onto it finishes the slice.
  `intent_proposal.py:174` scans for the matching bracket instead and is a
  different shape, so it stays out.
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
    `docs/reference/contracts/codex-cli.md` /
    `docs/reference/contracts/cursor-agent-cli.md` and
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
- **Effort:** small — four JSON-envelope call sites plus the two heading
  regexes absorbed from #300, one concern per commit.
- **Risks:** low **for the four JSON-envelope sites**, which are checked by
  hand; the two heading regexes are not: `_VALIDATION_RE` is MULTILINE-anchored
  and `_REDIRECT_HEADING_RE` is blank-line anchored, so check each one's exact
  anchoring and case behavior before swapping it onto a shared contract, and
  make no behavior change (leave a regex local if the contract cannot match it
  identically). The risk this entry guards against is the opposite one: merging a
  look-alike. Re-run the AST check before folding anything not listed above. Direct change → audit → fix → re-audit with
  affected tests each round (CLAUDE.md).
- **Approach:** direct. Migrate the four sites onto `JsonResponseContract`, one
  concern per commit; check per site that `JsonResponseContract` accepts the
  input each site accepts today, and leave a site local if it does not. The
  same rule applies to the two heading regexes.
- **Closure:** the migration batch is the only remaining work. The
  do-not-merge list is a settled record, not work: it moves into
  `docs/history/` (or next to `DO_NOT_MERGE` in `tests/test_duplication.py`,
  which already cites it), after which this entry closes. Until that move
  lands, the list above stays authoritative. Reshaped 2026-11-14.

**#80 — Consolidate the duplicated `iterate_parent` companion flags into `parser.py`**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `none` — consolidation of shared argparse parents
- **What:** the `--iterate` companion flags (`--time-budget` and the others,
  a ~60-line block ×3 in `run_cmd`/`completeness_cmd`/`authoring`) are rebuilt
  per command module instead of in the `parser.py` leaf. A flag added to one
  command is silently missing from the others, which is the drift risk this
  entry closes. Add one shared `add_iterate_args(parser)` builder (or
  `make_iterate_parent()`) to `parser.py` that registers the companions once;
  each `register()` calls it. **Folds in the time-budget cleanup follow-up.**
- **Deliberately not (cut 2026-11-14):** the `name` plan positional + its help
  string (14×) and `fail_on_findings_parent` (3×) — cosmetic duplication with
  no drift risk worth a sweep. `yes_parent` is already consolidated for its
  byte-identical sites (`make_yes_parent()`) and is not touched here.
- **Caveat:** keep the `--iterate`/`--no-iterate` **action itself**
  per-subparser — its default differs (ON for create, OFF for run) and
  argparse parents copy by reference (NOTE at `run_cmd.py:1536`).
  Consolidate only the *companion* iterate flags, not `--iterate`. Per-command
  help-text variants of `-y` (`gates_cmd.py`, `scope_out_cmd.py`,
  `worktree_cmd.py`, `roadmap_cmd.py`) stay as they are; they are outside this
  entry.
- **Effort:** small. ~120 lines removed, mechanical.
- **Risks:** low. `--help` text for the companions becomes consistent (a
  behavior change, but a desired one). Guard with the existing CLI-reference drift test
  (`tests/cli/test_cli_reference.py`) — regenerate `docs/cli/` after.
- **Approach:** direct. Explicitly TODO'd in-code; natural home already
  exists.

**#81 — Extract the byte-identical sub-blocks shared by the 4 convergence loops (NOT a unified driver)**

- **Labels:** Route `plan`
  · Readiness `parked`
  · Tier `experienced`
  · Principle `none` — extraction of sub-blocks shared by the convergence loops
- **Unpark when:** the next fix has to touch the same sub-block in all four convergence loops; extract that block then.
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
    lambda) → `dispatch_apply_finding_logged`. **Historical 2026-08-28:** the two
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
- **Approach (when unparked):** plan-tool. Multi-module refactor; paper-trail worthy.
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

**#56 — Add a linter (ruff) + pre-commit gate**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `none` — a repository lint gate, not a property of the tool's output
- **What:** `ruff` is in the dev dependency group (`ruff>=0.16.3`) and
  `pyproject.toml` carries `[tool.ruff]` with `select = ["F", "E9"]`; as of
  2026-11-14 `uv run ruff check plan_tool` reports 2 errors (the undefined
  names tracked in `BUG_BACKLOG.md`). What remains: wire a `pre-commit` hook
  into the existing tracked `scripts/hooks/` setup (alongside the `pre-push`
  suite guard) that lints staged Python; today `scripts/hooks/pre-commit` is a
  secret scanner only and runs no ruff.
- **Effort:** small — the hook wiring plus the 2 remaining errors. (A
  2026-06-16 probe under ruff's default `E,F` ruleset found 368 violations; the
  narrower shipped ruleset, `F` and `E9` only, replaced that rollout.)
- **Risks:** a hook that lints the whole repo blocks every commit while the 2
  errors stand; lint only staged Python, or clear the 2 errors first.
- **Dependencies:** none. The tracked-hooks scaffold
  (`scripts/hooks/install.sh`, `core.hooksPath`) already exists, so the
  pre-commit hook slots in beside `pre-push`.
- **Origin:** Requested 2026-06-16 while adding the CLI-reference
  pre-push hook; the dependency and `[tool.ruff]` config have since landed.
- **Approach:** `direct` — the rule set is already chosen (`F`, `E9`); what is
  left is the staged-file hook and the 2 remaining errors.

**#176 — Run-log writers for the remaining Claude-spending verbs (`jira`, `annotate`, `reconcile-plan-walk`)**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** these three spend Claude and open no run log at all — no cost
  record, no `in-flight.json`, nothing in `plan-tool runs list`. Verified
  empirically against every saved log in this repo: the only `run_start`
  commands ever recorded are `run`, `completeness`, `detail`, `create`,
  `completeness-apply`, `run-reconcile`, `detail-reconcile`, `split`,
  `suggest-gates`, and (as of `741fdf6`) `reconcile-plan` / `verify-all`.
  Statically, `cli/jira_cmd.py` and `cli/annotate_cmd.py` contain no
  `RunLogWriter` reference; the standalone `reconcile-plan-walk` likewise.
  (`merge` logs now: `command="merge"` in `cli/authoring.py`.) `annotate` is one call per file, so a batch run multiplies it.
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
  - **Outcome:** each of the three verbs writes one run log per invocation,
    with its Claude calls recorded under a named phase.
  - **In scope:** `plan_tool/cli/jira_cmd.py`, `plan_tool/cli/annotate_cmd.py`,
    `cmd_review_walk` in
    `plan_tool/cli/review_cmd.py`; their tests.
  - **Out of scope / Non-goals:** #177 (the slug pre-log ordering), the
    already-satisfied `run` phase attribution, adding new run-log *event kinds* or
    fields; changing `DATA_CONTRACT.md`; any orchestrator signature change
    (bind the sink at the command level, as `741fdf6` did).
  - **Allowed behavior changes:** a `.plan-tool/runs/<slug>/` log appears for
    these three verbs. Nothing else — no output, rc, or prompt changes.
  - **Allowed reorganization:** promoting `_run_logged_audit` / `_audit_sink`
    out of `review_cmd.py` into a shared CLI leaf **is** permitted here,
    since two of the three callers live in other modules and importing from
    `review_cmd` would create a new edge between command modules. Smallest
    move only: the two helpers, no adjacent refactor.
  - **Verification:** per verb, one test asserting `run_start`'s `command`,
    a single `run_end` with the real rc, and no leftover `in-flight.json`;
    plus a sink test on at least one (drive `shell._emit_call_end` and assert
    the phase override), mirroring `tests/test_review.py`'s.
  - **Stop / defer:** if a verb turns out to need a *nested* log, file that separately rather than
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

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** the BUG_BACKLOG fix that makes the unsinked-call warning name its real caller lands; then default to option (c), a RUNBOOK note, unless the unlogged cost matters.
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
  ran"); settle that before choosing among (a)–(c); that fix is the unpark condition.
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
- **Approach (when unparked):** `decision first`, then `direct` — the implementation is small
  under every option; picking the option is the work.
- **Quality:** `audit-coverage` — closes or documents a known hole in
  per-command cost accounting.
- **Origin:** 2026-07-28, same logging-gap audit as #176. Filed after an
  initial read wrongly called it a mechanical sink wrap; the ordering
  constraint is what makes it a decision.

**#180 — Structural renumbering: fix detail-file H1s and report surviving step references after split/merge/scope-out**

- **Labels:** Route `plan` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `plan-tool split` (and the same renumber path used by `merge` and
  `scope-out`) renames detail files and repairs `depends_on`, but leaves every
  human-readable step reference stale. After a split it does not update: the
  `# Step N — …` H1 **inside** each renamed detail file; prose cross-references
  in sibling detail files and the plan body (`step 7 owns …`, `steps 3–7
  shipped …`, `owned by step 9`); execution-order strings such as
  `1 → 2 → 3 → 5 → 6 → 7 → 4`; and Deferred/Input bullets that assign ownership
  by step number. This entry ships the first slice only: rewrite the
  detail-file H1 and report surviving step references (see the scope contract).
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
  reporting, not guessing.
- **Why it matters:** the renumber is *already* the tool's job — it repairs
  `depends_on` precisely because dangling ids are a correctness problem. Prose
  references are the same class of dangling pointer, just unenforced: nothing
  validates them, so they rot silently and mislead the implementer that a later
  step reads. It also undercuts the structural remedies the tool recommends: an
  operator told to `split` pays an invisible hand-fix tax, which is a reason not
  to take the advice.
- **First slice (this entry):** the renumber already computes an old→new id
  map. (a) Rewrite the `# Step N — …` H1 of each detail file it renames; the
  mapping is unambiguous. (b) After a renumber or carve, scan the surviving
  detail files and plan body for `[Ss]tep N` / `[Ss]teps A–B` references to
  moved or carved ids and print them ("7 references to carved step 10 survive
  — review these"), rewriting nothing. The report needs no ambiguity policy
  and turns the manual sweep into a checklist.
- **Deferred until the report shows it is still needed:** a prose rewriter for
  `[Ss]tep N` references and its ambiguity policy (a reference may mean either
  half of a split step). Revisit once the report shows how often operators
  still hand-rewrite the listed references.
- **Scope contract:**
  - **Outcome:** after a `split`/`merge`/`scope-out`, no renamed detail file's
    H1 names a stale step number, and every surviving `[Ss]tep N` prose
    reference to a moved or carved id is listed in the command's output.
  - **In scope:** the shared renumber path (`plan_tool/scope_out.py`'s
    `apply_narrow` / the split executor's migrate-and-renumber), the detail-file
    H1 rewrite, and a read-only report scanning detail files and the plan body.
  - **Out of scope / Non-goals:** deliberately not rewriting prose references
    (`[Ss]tep N`, execution-order strings, Deferred/Input ownership bullets) in
    this slice, because the ambiguity policy is undecided and the report may
    show rewriting is unnecessary; rewriting prose that names a step by
    *title* rather than number; touching archived plans; renaming test
    functions or code symbols that embed a step number; any change to
    `depends_on` repair, which already works.
  - **Allowed behavior changes:** the H1 of each renamed detail file changes,
    and the command's summary gains a list of surviving references; no sibling
    file or plan-body prose is edited.
  - **Allowed reorganization:** extracting the reference scan into a small
    helper shared by the three verbs.
  - **Verification:** a test that splits a fixture plan whose detail files carry
    H1s and cross-references, asserting every H1 matches its step id and every
    surviving reference to a moved id is reported while the files' prose is
    byte-unchanged; plus a carve case asserting references to the carved id
    are reported.
  - **Stop / defer:** if a reference cannot be classified without a Claude
    call, stop — this entry is deterministic text scanning, not a judgment
    surface.
- **Dependencies:** none.
- **Effort:** small-to-medium — the map exists; the work is the H1 rewrite and
  the scan.
- **Approach:** `plan-tool` — touches three verbs' shared renumber path and
  changes what a mutation writes, so it goes through a plan. Narrowed
  2026-11-14 to the H1 rewrite plus the read-only report.
- **Quality:** `audit-coverage` — stale cross-references are a recurring source
  of completeness findings that the tool itself creates.
- **Origin:** 2026-07-29, after two splits of `jira-grade-01-detail-instrument`
  each needed a manual reference sweep and the audit filed the leftovers.

**#183 — `scope-out`'s blocked-path advice should name the small fix, not jump to re-decomposition**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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

**#185 — `scope-out --into-seed <path>`: carve into an existing seed instead of always minting a standalone**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** a second hand-merge of a carved seed into an existing seed is needed (the first target seed has since been withdrawn).
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
- **Dependencies:** none.
- **Effort:** small/medium — the rendering exists; the work is the append
  path and its ordering guarantee.
- **Approach (when unparked):** direct — a bounded option on an existing deterministic writer.
- **Quality:** `advice-quality` — the tool told the operator the scope's owner
  and then ignored it.
- **Origin:** 2026-07-29, scope-out exercise (jira-grade-01 falsification
  carve folded into the stage-03 ledger seed by hand).

**#186 — Carved seeds inherit no fence: the seed must state what the parent kept, so the carve can't be silently re-absorbed**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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

**#189 — Retroactive forward-looking sweep of the reference docs**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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
  - **Dead module `plan_tool/iteration_lock.py`, cited by `TESTING.md:228`**
    (the `docs/*RESUME_FLOW.md` docs that also cited it no longer exist). The
    file does not exist; `plan_tool/repo_lock.py` is the likely successor.
    Determine whether it is, then fix the citation. Highest-value item here.
  - Other dead citations: `reformat.py` (`TESTING.md:235`) and
    `prompts/reconcile.md` (`TESTING.md:229`),
    `plan-seeds/escalate-structural-findings-to-split-redecomposed.md`
    (`RUNBOOK.md`).
  - Change-narration to rewrite as current-state, ~8 sites, mostly
    `RUNBOOK.md`: "keep the **old behavior**" (770), "the staleness that
    **used to** make reuse a gamble" (1366), "saved reconciles **used to**
    drift into" (1391), "you **no longer** edit `status:` by hand" (2205),
    "citations **no longer** flag" (2943), "**no longer** falls through"
    (3292). Re-run the method below to re-derive the full set.
    `reconcile-plan is no longer exposed as a --mode` (`RUNBOOK.md` 3958) is
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

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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
- **Dependencies:** independent. **Git is the archive for detail files** (the plan-level form, #199, is
  discarded). (An earlier
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
    plan-level archival (discarded #199); deleting existing `archive/` directories in any
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
**#201 — One-time scripted cleanup of the redundant detail-level `archive/` directories #200 retires**

- **Labels:** Route `direct`
  · Readiness `blocked-on #200`
  · Tier `experienced`
  · Principle `untriaged`
- **What:** remove, in this repo, the per-detail `archive/` directories under
  `docs/implementation-plans/` whose contents are fully recoverable from the
  version history. #200 stops *writing* them and deliberately leaves existing
  ones alone; this is the one-time sweep that clears what is already on disk.
  It is a scripted `git rm`, not a product feature: deliberately not a
  `validate` advisory and not an opt-in removal subcommand, because the
  cleanup runs once (cut 2026-11-14).
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
- **Procedure:** a throwaway script walks the detail-level `archive/`
  directories (nested ones included), verifies each file with `git cat-file`,
  and `git rm`s only the directories whose files all pass. Anything that
  fails is reported and left for a human. The script is not committed to the
  tool. After #200 lands, add one line to the release notes telling consuming
  repos they can remove their own redundant `archive/` directories the same
  way.
- **Do not couple it to plan archival.** This sweeps directories; plan archival
  is out of scope (#199 is discarded).
- **Ignore-file hygiene:** report `.DS_Store`-class noise; do not grow a general
  gitignore linter here.
- **Risks / fallout:** deleting a directory a doc still cites by path. The
  jira-grade handoff cites
  `docs/implementation-plans/archive/plan-details/jira-grade-detail-side-by-side-evaluation/reports/`
  as spin evidence, and citations like it must survive — so the sweep either
  skips plan-level `archive/` trees entirely (scoping to the per-detail
  `archive/` folders #200 retires) or runs a citation sweep for them.
  **Recommended: scope to the detail-level folders**, and leave plan-level
  archival alone (#199 is discarded).
- **Dependencies:** runs after **#200** — that entry stops the bleeding, this
  one cleans the wound. Landing this without #200 means the directories come
  back.
- **Effort:** small — one script run and one commit.
- **Scope contract:**
  - **Outcome:** every per-detail `archive/` directory in this repo whose
    contents are fully recoverable from git is removed in one commit; the
    release notes carry one line for consuming repos.
  - **In scope:** the scripted, `git cat-file`-verified `git rm` of the
    detail-level folders in this repo, and the release-notes line.
  - **Out of scope / Non-goals:** deliberately not a `plan-tool validate`
    advisory or an opt-in removal subcommand (a one-time cleanup does not earn
    product surface); plan-level `docs/implementation-plans/archive/` trees
    (#199 is discarded); deleting anything in another repo; a general
    gitignore linter; changing what writes archives (#200).
  - **Allowed behavior changes:** none to the tool.
  - **Allowed reorganization:** none.
  - **Verification:** after the run, no detail-level `archive/` directory
    remains whose files were all recoverable; any directory holding a file
    whose exact bytes are absent from git is reported and left in place; git
    history for the removed paths is intact.
  - **Stop / defer:** if a doc-citation to a detail-level archive path turns up,
    stop and keep that reference working rather than breaking it.
- **Approach:** `direct` — a one-time script and a commit.
- **Quality:** `audit-coverage` — removes superseded design from the surface
  greps and audits read.
- **Origin:** 2026-07-30, user request while retiring the archive convention.
- **Status:** not started.

**#294 — Model deployment units before treating a runtime/store pair as a roadmap contradiction**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** a concrete roadmap needs the tool to reject an incompatible runtime/store pair.
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
- **Priority:** unrated while parked; it is a deferred design, not a blocker for recording the hosting and store facts.
- **Approach:** plan-tool — a new persisted relation and cross-artifact gate
  require staged design and migration decisions.
- **Status:** parked 2026-11-14.

**#301 — Version saved conceptual-audit coverage records before their next additive field**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** the next additive `audit_coverage` field is proposed; version the record first.
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
- **Status:** parked (deferred 2026-08-20); no live bug.

**#302 — Pin `on_nonsuccess` notification with a table-driven test over every arm of the rate-limit loop**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced`. · Principle `untriaged`
- **Unpark when:** a deliberate recovery-loop hardening pass is scheduled, or a
  new recovery arm is added to the loop.
- **What:** `run_with_rate_limit_recovery` reaches `on_nonsuccess` through one
  local helper, `_notify_nonsuccess`, called from each exit arm. Add one
  table-driven test that asserts the callback count and both retry booleans for
  every arm.
- **Why:** a future recovery arm could otherwise omit its `_notify_nonsuccess`
  call or give it the wrong retry state, losing quota-drift telemetry. The test pins that
  property: a new arm that skips the callback fails it.
- **Effort:** small — one focused test over existing arms.
- **Risks / fallout:** low; the loop is not edited.
- **Dependencies:** the shipped #101 recovery-loop extraction. This is
  separate from #136's caller-side helper consolidation.
- **Scope contract:**
  - **Outcome:** each non-success attempt is asserted to invoke
    `on_nonsuccess` exactly once with the actual and predicted retry signals it
    has today.
  - **In scope:** `tests/test_rate_limit_loop.py` (or the existing focused test
    module for the loop).
  - **Out of scope / Non-goals:** deliberately not restructuring the loop into
    one shared completion path (cut 2026-11-14): that control-flow rewrite is
    the risky part and is unnecessary once the test pins the property;
    shell/launcher seam consolidation (#136), retry-policy changes, new
    recovery actions, and telemetry-format changes.
  - **Allowed behavior changes:** none.
  - **Allowed reorganization:** none.
  - **Verification:** the table covers every existing terminal and re-invoking
    arm, asserting callback count and both retry booleans; deleting the
    `_notify_nonsuccess` call from any one arm turns the test red, and the
    table's arms are checked against the loop's exits so a new arm without a
    row fails.
  - **Stop / defer:** if the table exposes an arm whose behavior is wrong,
    that becomes a separate decision rather than an incidental fix.
- **Approach:** `direct` — a test over shipped behavior, no design choice.
- **Quality:** audit-coverage — keeps terminal quota-drift observation
  complete as new recovery exits are added.
- **Origin:** 2026-08-20, `plan-quota-recovery` whole-feature review round 5,
  finding 4; narrowed 2026-11-14 from a loop restructure to the test.
- **Status:** parked since 2026-08-20; no live bug.

**#303 — Compare saved audit history only with provenance-backed admission**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
- **Unpark when:** a convergence decision needs cross-invocation audit comparison; none has asked since #247.
- **What:** add a separately scoped cross-invocation audit comparison only
  after saved evidence can prove the history is eligible for comparison.
- **Why parked:** #247 makes artifacts visible, but saved metadata alone
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
- **Status:** parked (deferred 2026-08-21); #247's delivered ledger is a prerequisite
  for visibility, not proof that comparison is safe.

**#259 — Render a `depends_on` edge's consumption note in the detail-authoring prompt, the bridging-edge grounding block and the Jira story body**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `detail.py:render_detail_prompt` renders a step's `depends_on` as a
  bare comma list (`step_depends_on`) in the prompt that asks Claude to write
  that step's implementation detail file.
- **Absorbs #257 and #258 (merged 2026-11-14):** render the same existing
  `depends_on_notes` entry in all three places as one direct change: (a)
  `create.py:_render_dependency_cohesion_block`, where a bridging edge that
  has a note reaches body synthesis indistinguishable from one with none
  (`_BridgingDependencyEdge` carries no note text); (b) `jira.py`'s story
  body, which prints `Depends on:` ids with no note; (c) this entry's detail
  prompt. The Jira part is the lowest priority and costs almost nothing in the
  batch.
- **Why:** whoever (or whatever) authors the detail file benefits from seeing
  what a dependency actually delivers, the same reasoning applies one stage earlier
  in the pipeline (body-synthesis grounding, absorbed from #257) and in the Jira
  export (absorbed from #258).
- **Effort:** small — thread each edge's `depends_on_notes` text into the
  run-grade dependency block, the bridging-edge grounding block and the Jira
  story body.
- **Dependencies:** builds on shipped `depends_on_notes`.
- **Scope contract:**
  - **Outcome:** the detail-authoring prompt's dependency block, the
    bridging-edge grounding block and the exported Jira story body each show an
    edge's note when one exists.
  - **In scope:** `plan_tool/detail.py:render_detail_prompt`,
    `plan_tool/create.py:_render_dependency_cohesion_block` (with note text on
    `_BridgingDependencyEdge`), the story rendering in `plan_tool/jira.py`,
    tests.
  - **Out of scope / Non-goals:** any check on note content; changing what
    `depends_on` ids are listed.
  - **Allowed behavior changes:** the rendered prompt's dependency block and
    the bridging-edge grounding block gain optional note text per edge; the
    exported Jira story body gains the same note, and stays valid under
    `JIRA_FORMAT.md` and `jira --lint`.
  - **Allowed reorganization:** none beyond carrying note text on
    `_BridgingDependencyEdge`.
  - **Verification:** a step whose antecedent has a note renders it in the
    detail prompt, the bridging-edge grounding block and the Jira story body;
    one without renders exactly as today in each.
  - **Stop / defer:** anything beyond rendering the note text as-is.
- **Approach:** `direct`.
- **Quality:** `audit-coverage`.
- **Origin:** 2026-08-08, found in BACKLOG #253's own round-3 bare-plan audit;
  self-flagged `[out-of-scope-deferred]` by that audit and split out rather
  than absorbed.
- **Status:** not started.

**#318 — Audit `.gitignore` correctness and consolidate ignore-rule management onto a single tracked location**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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
  model to match); this machine's `.git/info/exclude`, which carries ten
  `**/.claude/*` runtime-state patterns (`scheduled_tasks.lock`,
  `scheduled_tasks.json`, `routines/.state/`, `worktrees/`, `checkpoints/`,
  `mailbox/`, `agent-registry.json`, `agent-memory-local`,
  `assistant-daemon-state.json`, `first-run`); and this user's global
  `~/.config/git/ignore`, which carries `**/.claude/settings.local.json`.
  The tracked root `.gitignore` carries only `.claude/local/` (line 51), which
  covers none of them. None of those eleven patterns ship with the repo — `git ls-files .claude/`
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

**#406 — `docs/ARCHITECTURE.md` says the comparison branch avoids `plan_tool.roadmap`; the import graph does not**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `docs/ARCHITECTURE.md` § "Read-only snapshot comparison" states the
  comparison branch (`roadmap_compare_run.py`, `roadmap_compare.py`,
  `roadmap_diff.py`, `roadmap_compare_render.py`) "imports version and
  artifact-reader leaves, owns no lifecycle transition, and does not import
  or invoke roadmap writers." At HEAD, `roadmap_diff.py` imports
  `RoadmapStage` and `roadmap_compare_run.py` imports `STAGES`, both from
  `plan_tool.roadmap` — the stage-execution/backend-invoking module the
  claim says this branch avoids. `RoadmapStage`/`STAGES` are pure data; the
  coupling is an artifact of where they are defined. A second edge:
  `roadmap_compare_run.py` imports `load_stored_candidate_proposal` from
  `roadmap_candidate_run.py`, which imports `roadmap_revision_publish`,
  `roadmap_feedback_ledger`, `shell`, and `RunLogWriter`; the comparison route
  only reads through it, but the graph reaches writer modules.
- **Fix:** correct the `ARCHITECTURE.md` sentence so it describes the actual
  import graph: the branch reads through the stage table and the stored-
  candidate loader, both defined in modules that also reach writers, and owns
  no lifecycle transition itself.
- **Deliberately not (cut 2026-11-14):** moving `RoadmapStage`/`STAGES` or the
  stored-candidate loader into read-only leaves. The 2026-09-21 attempt at that
  extraction broke `roadmap_candidate.py`'s `GateCleanCandidate` Pydantic
  model: moving `RoadmapStage` out of `roadmap.py` changed import-order timing
  enough that `RoadmapGateOutcome`'s nested forward-ref
  (`violations: tuple[Violation, ...]`) stopped auto-resolving at class build,
  and the failure traced into Pydantic v2/Python 3.14 `annotationlib`
  internals. Re-open the extraction only if the read-only layering becomes an
  enforced contract, for example via an import-graph test; whoever does so must
  re-verify `GateCleanCandidate`/`RoadmapGateOutcome` explicitly, not only the
  touched files' own test suites.
- **Scope contract:**
  - **Outcome:** the `ARCHITECTURE.md` description of the comparison branch's
    imports is true at HEAD.
  - **In scope:** the one `docs/ARCHITECTURE.md` sentence (and any restatement
    of it found by grepping the comparison branch's layering vocabulary).
  - **Out of scope / Non-goals:** any module move or import change; an
    import-graph test (the trigger for re-opening the extraction).
  - **Allowed behavior changes:** none.
  - **Verification:** each import the sentence names or denies is checked
    against the module's imports at HEAD.
  - **Stop / defer:** if making the sentence true requires describing an
    import the owner would rather remove, stop and file that as its own entry.
- **Effort:** small — a documentation edit.
- **Dependencies:** none.
- **Approach:** `direct` — documentation only.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`); reshaped 2026-11-14.
- **Status:** not started; the doc claim remains inaccurate at HEAD.

**#409 — `build_roadmap_diff`'s `predecessor_bytes`/`candidate_artifacts_bytes` are positional, unlike its own keyed `*_artifacts` parameters**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** `build_roadmap_diff`'s signature next changes; make the bytes keyed by construction then.
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
- **Approach (when unparked):** `direct`, once verified against `roadmap_candidate.py`'s full
  suite, not just this feature's own tests.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** parked 2026-11-14; latent, not reachable today.

**#417 — A pure reorder of an ordering row's `depends_on`/`assumption_targets` produces a "changed" card with an empty field summary**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
- **Unpark when:** an operator is actually misled by the empty-summary card on a same-membership reorder.
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
- **Approach (when unparked):** `direct`, once a fix shape is chosen — needs a design
  decision (widen relation matching vs. special-case ordering), not just an
  implementation.
- **Origin:** 2026-09-21, `/code-review high` pass on the `roadmap-concept-comparison`
  plan's shipped implementation (`e77ebfa5..HEAD`).
- **Status:** parked 2026-11-14; narrow (same-membership reorder with no other field change), and before/after still shows the change.

### E. Cosmetic / churn

**#393 — `ROADMAP_FORMAT.md` calls a field "discharges" where the schema keyword is `constraint_ids`**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `ROADMAP_FORMAT.md`'s component section describes a component as
  "discharging" prioritized constraints in prose, but the actual
  frontmatter/schema keyword the gates read is `constraint_ids`
  (`check_component_constraint_references`,
  `check_prioritized_constraint_discharge`). The prose name and the schema
  name don't match, which reads as if `discharges` were a quotable field name
  when it isn't one. `ROADMAP_FORMAT.md:442` already pairs the prose with
  `(constraint_ids)` and the gate table (lines 1734-1735) names the field, so
  what remains is wording only (lines 21, 288, 421).
- **Effort:** small — doc wording only, no code or schema change.
- **Approach:** direct.
- **Origin:** 2026-09-17, noticed incidentally while reading
  `ROADMAP_FORMAT.md`'s component/constraint-discharge description during an
  AI-DLC comparison pass.
- **Status:** not started.

**#223 — `RUNBOOK.md`'s self-consistency walkthrough omits the blocking intent finding**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `RUNBOOK.md`'s "Completeness reports two concept-specific sources"
  passage names a medium `concept-coverage` finding as the blocking
  self-consistency example. `intent-presence` now blocks through the same
  bucket at `medium`, and the walkthrough never mentions it — so an operator
  reading the runbook after hitting the finding gets no remedy. The fix is one
  bullet naming the one-line `intent:` edit, with a session-directed edit remedy.
- **Effort:** small — prose only, no code, no tests.
- **Approach:** direct. **Origin:** 2026-08-02, `intent-required` step 8; the
  file was in neither that step's nor its sibling doc step's file list.
- **Status:** not started.

**#264 — `arm-clustering`'s consensus requirement could be satisfied across audit rounds, not only within one `--audit-passes` execution**

- **Labels:** Route `plan`
  · Readiness `parked` (parked 2026-11-14: a new detector for a different signal; `CLAUDE.md` already directs the operator to count the arm by hand when the detector is silent)
  · Tier `architect`
  · Principle `untriaged`
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
  (`plan_tool/convergence_diagnosis.py:1437,1352`) already read
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
- **Unpark when:** a real missed arm turns up that a cross-round consensus signal would have caught.
- **Status:** plan-authored: `docs/implementation-plans/2-arm-clustering-cross-round-consensus.md`
  (status `planning`, registered in `.plan-tool/plans.json`); implementation
  is not started and stays unstarted while parked.

**#265 — `split` (and similar detail-authoring commands) should default to `--no-detail` when the target plan is bare**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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

**#267 — `seed-state.json`'s load-modify-write cycle has no cross-process locking**

- **Labels:** Route `direct`
  · Readiness `parked` (parked 2026-11-14: the tool is serial by design and two concurrent operator processes on one roadmap have not been observed)
  · Tier `experienced`
  · Principle `untriaged`
- **What:** `plan_tool/roadmap_seed_state.py`'s `load_seed_state`/
  `write_seed_state` read the whole sidecar, let a caller mutate it, and write
  it back with no lock. Every entry point that touches an individual plan's
  entry — `--refresh-seeds`, `--apply`, `--materialize`, and `--accept-seed` —
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
- **Unpark when:** a lost `seed-state.json` write is observed from two concurrent processes.
- **Origin:** 2026-08-13, `roadmap-seed-materialization` completeness audit,
  finding `seed-state-concurrent-cli-race`.
- **Status:** parked.

**#291 — Seed materialization states the greenfield case explicitly instead of asking the model to match code that doesn't exist**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `prompts/roadmap-seed.md` instructs the backend to "inspect the
  **current repository**" and make the seed's implementation-facing language
  "match the code that exists now." The four stage prompts deliberately never
  read the repository, so this prompt is the roadmap arc's only repo-aware
  surface — and it has no posture for a repository with no code yet.
  `_render_seed_materialize_prompt` (`plan_tool/roadmap.py:3386`) interpolates
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

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** two doc gaps that together argue against a designed use. First,
  `docs/how-to/use-cases.md`'s "When not to use it" says "No repo to ground against …
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
  grows) and add a greenfield section to `docs/how-to/roadmap.md`
  stating the cadence.
- **Effort:** small — two doc edits, no code.
- **Risks:** none beyond ordinary doc drift.
- **Dependencies:** none — the cadence documents machinery that already
  ships.
- **Scope contract:**
  - **Outcome:** a reader planning a greenfield project finds an explicit
    statement that `roadmap` is the intended entry point and a stated
    execute → refresh → create loop.
  - **In scope:** `docs/how-to/use-cases.md` (§ "When not to use it" and § 11),
    `docs/how-to/roadmap.md`.
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

- **Labels:** Route `direct`
  · Readiness `parked` (parked 2026-11-14: the motivating incident is unverified and the exposure is mostly an editable-install developer-machine hazard)
  · Tier `experienced`
  · Principle `untriaged`
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
- **Unpark when:** a stale-process failure is reproduced in a fresh process, in another project, or from supported-route provenance.
- **Origin:** 2026-08-26, raised by the user after tracing the roadmap
  evidence-schema incident to a plausible long-running-process cause, with
  the observation that this is a structural exposure class — "almost all
  processes of the tool are long running" — not a one-off worth a narrow fix
  alone.

**#317 — Longer bounded transient backoff so a short network outage does not halt `run`**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** a real network outage (WiFi drop, laptop sleep/wake, VPN
  reconnect) is indistinguishable today from an ordinary blip.
  `rate_limit_loop.run_with_rate_limit_recovery`'s `TRANSIENT` arm
  (`ECONNRESET`, `network error`, `timeout`, `connection reset`, matched by
  `backend._CLAUDE_TRANSIENT_PATTERN`) gets only
  `DEFAULT_MAX_TRANSIENT_RETRIES=2` attempts at
  `DEFAULT_TRANSIENT_BASE_DELAY=2.0`s exponential backoff (`shell.py:157-158`)
  before `TERMINAL`, halting `run_step()`'s blocking claude-call gate
  (`docs/how-to/pipeline/run.md` step [6]) within ~6 seconds with no automatic
  resume. Raise the transient backoff to a bounded window of minutes, not
  seconds, with an interruptible wait, so a laptop sleep or WiFi drop recovers
  without operator action. No incident is cited yet; the concern is a P4
  robustness gap.
- **Parked (not in this entry):** a real, injectable connectivity probe and a
  pause-and-poll path that resubmits only once a fresh probe confirms
  connectivity is back, including admitting a `SILENCE_TIMEOUT`-killed
  long-running call (`backend_runner.py`'s 900s heartbeat kill,
  `_KILL_AFTER_SILENCE_S`, classified `ClaudeFailureKind.TIMEOUT`, deliberately
  terminal today per `claude_errors.py`). That design adds a probe/poll-wait
  seam pair, a widened retry-candidate computation in the stdlib-only
  `rate_limit_loop.py` leaf, a poll-eligibility rule keyed on
  `get_last_termination_reason()`, a new opt-out, and a third
  `backend_recovery_wait.reason` value: a lot of new state in the retry leaf.
  Re-open it only when a real outage halts a run that a longer backoff would
  not have saved. `plan-seeds/connectivity-pause-and-poll.md` describes the
  parked design and is not the seed for this slice.
- **Effort:** small — raise the transient delay/attempt constants (or give the
  transient arm a bounded total-wait cap), make the wait interruptible, and
  update tests and docs.
- **Risks / fallout:** a longer wait keeps a run blocked on a genuinely broken
  network for the whole window before `TERMINAL`; the window must be bounded.
  The wait must stay interruptible on a TTY, and the partial-mutation
  `retry_guard` (`git_state.make_partial_mutation_retry_guard`) must still gate
  every retry. The candidate flow's `shell_candidate_proposal_invoker` and
  `shell_candidate_review_invoker` pass `max_transient_retries=1` and
  `wait_on_rate_limit=False` and must not gain the longer window.
- **Dependencies:** none. Independent of #119/#120 (snapshot-restore-then-retry
  and retry-guard hardening), which harden *what happens when a retry is
  allowed*; this changes *how long the loop waits before giving up*.
- **Outcome:** a `TRANSIENT` backend failure retries over a bounded window of
  minutes with an interruptible wait before surfacing `TERMINAL`, instead of
  exhausting two ~2s retries.
- **In scope:** `plan_tool/rate_limit_loop.py` and `plan_tool/shell.py` (the
  transient delay/attempt defaults and the interruptible wait),
  `docs/how-to/pipeline/run.md`, `RUNBOOK.md`, and focused tests with a stubbed
  clock/sleep.
- **Out of scope / Non-goals:** deliberately not the connectivity probe, the
  pause-and-poll path, or `SILENCE_TIMEOUT` recovery (parked above, with the
  reason); making a `CONFIGURED_TIMEOUT` kill retry-eligible; any new
  `ClaudeFailureKind`, `AttemptCategory`, or `TerminationReason` member; a new
  CLI flag; any change to `backend_runner.py`'s kill ladder or thresholds;
  changing `RATE_LIMIT`/`PLAN_QUOTA` handling.
- **Allowed behavior changes:** a `TRANSIENT` failure waits longer before
  `TERMINAL`. No change to a `CONFIGURED_TIMEOUT` kill, a wedged call, the
  candidate invokers' no-recovery posture, or the partial-mutation guard's
  precedence.
- **Allowed reorganization:** none.
- **Verification:** a stubbed-clock test shows a transient failure retried over
  the new window and then surfacing `TERMINAL`; an interrupt ends the wait; the
  candidate invokers still stop after one retry; `retry_guard` still refuses a
  retry over a dirty tree; no test sleeps for real.
- **Stop / defer:** if the longer window needs the probe to be safe (for
  example because it masks a captive-portal failure), stop and file the
  parked design as its own entry; anything surfaced outside this fence goes to
  `BACKLOG.md` / `BUG_BACKLOG.md`.
- **Approach:** `direct` — a bounded change to existing retry constants and
  wait, no new seam.
- **Status:** not started; narrowed 2026-11-14 from the probe-and-poll design.
- **Origin:** 2026-08-26, investigation requested into making long-running
  `plan-tool` processes resistant to a lack of connectivity.

**#322 — Migrate remaining human-input and human-availability routes after the vertical proof**

- **Labels:** Route `plan`
  · Readiness `parked` (parked 2026-11-14: the inventory exists and no route is selected)
  · Tier `architect`
  · Principle `untriaged`
- **What:** evaluate and migrate the remaining prompt and human-availability
  routes through the landed record protocol or a deliberately revised
  successor. `docs/reference/contracts/human-io.md`, the focused review-walk proof, and the
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
- **Unpark when:** a named headless consumer (Loom or Integration) blocks on a direct `input()` call.
- **Status:** the current-code inventory is recorded in
  [`analysis/headless-process-route-inventory.md`](docs/implementation-plans/backlog-arcs/analysis/headless-process-route-inventory.md).
  Its standalone saved-review selection is complete as
  [`headless-review-walk-annotation-entry`](docs/implementation-plans/archive/2-headless-review-walk-annotation-entry.md).
  No follow-on route, shared policy, or lifecycle change is selected. Refresh
  the inventory against post-proof code before selecting another route.

**#329 — Validate the exact root-enrollment journal before pre-enrollment recovery**

- **Labels:** Route `direct`
  · Readiness `parked` (parked 2026-11-14: guards against forged or corrupt journals that normal writers never produce)
  · Tier `experienced`
  · Principle `untriaged`
- **What:** Before `plan_tool/roadmap.py:_publish_root_version` (via
  `build_root_enrollment_generation` and `publish_roadmap_generation`)
  recovers a pending root-enrollment journal, verify that its members are exactly the
  root version record, brief, fixed artifact inventory, and final accepted-head
  selector for one root version. Refuse any other journal without recovery or
  capture.
- **Why parked:** Normal lifecycle writers do not create a falsely labelled
  `root-enrollment` journal. The shipped #328 happy-path proof already refuses
  actual pending legacy journals before capture; this adds persistence-integrity
  hardening for corrupt or forged journal content.
- **Effort:** small — one narrow generation recognizer, the enrollment
  preflight, and focused recovery fixtures.
- **Risks / fallout:** An over-broad recognizer could prevent a legitimate
  interrupted root enrollment from recovering. Keep unversioned recovery and
  every other generation kind unchanged.
- **Dependencies:** #328 (closed) is the source of the published root-generation
  contract.
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
- **Unpark when:** a corrupt or falsely labelled pending root-enrollment journal is observed.
- **Arc assignment:** `backlog-arc-roadmap` (its persistence-integrity hardening
  note names this entry).
- **Origin:** 2026-09-01 post-run reconciliation report
  `20260901-151003-run-reconcile.json`, finding `step4-run-reconcile-cad5fa58`;
  user-confirmed as deferred hardening.
- **Status:** parked; #328 is closed and no corrupt journal has been observed.

**#353 — Durable artifact-contention handoff for terminal and headless operators**

- **Labels:** Route `plan` · Readiness `parked` · Tier `architect` · Principle `untriaged`
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
  destination untouched. `docs/reference/contracts/human-io.md` and #322 provide the existing
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
- **Unpark when:** the narrow normalized-artifact collision correction reaches external review convergence and the owner explicitly selects this item.
- **When unparked:** the seed comes first, from this scope contract; the
  bare-plan audit is load-bearing for the human-authority and stale-choice
  rules, and the detail-grounded audit is load-bearing for persistence and
  idempotence.
- **Arc assignment:**
  [`backlog-arc-headless-process.md`](docs/implementation-plans/backlog-arcs/backlog-arc-headless-process.md),
  with Integration recorded only as an intended headless consumer.
- **Origin:** 2026-09-04 user-confirmed scope carve during the external
  `seed-ingestion-routing` review, after recurring collision findings showed
  that durable human coordination is useful but exceeds the narrow correction.
- **Status:** not started; parked.

---

**#405 — Document focused feedback subsets for a failed broad roadmap revision**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** add a short "submit focused feedback subsets" guidance paragraph to
  `docs/how-to/roadmap.md` § 6. When a revision over many related feedback rows
  returns responses without material structural change, the operator keeps the
  full ledger, exposes one focused cross-artifact concern in the working
  artifacts, and reruns the normal revision lifecycle, repeating per concern.
- **Why:** Integration's first full-MVP revision attempted 23 related requests at once
  and produced responses without material structural changes. The recovery was
  to retain the 23-row ledger, expose only one focused cross-artifact concern
  in the working artifacts, and rerun the normal revision lifecycle. One case
  (n=1) supports the guidance, not a diagnostic.
- **Effort:** small — one documentation paragraph.
- **Risks:** the paragraph must not imply that semantic completeness is proven,
  or that grouping by artifact alone is sufficient; a concern can span stages.
- **Dependencies:** none.
- **Outcome:** an operator whose broad revision fails to change the roadmap
  finds, in the how-to, the focused-subset recovery and how to keep a concern
  that spans artifacts together.
- **In scope:** the `docs/how-to/roadmap.md` paragraph (and a pointer from any
  failure-recovery text there that names a broad revision).
- **Out of scope / Non-goals:** deliberately not a diagnostic or report that
  classifies a failure as a breadth failure and groups feedback rows into
  subsets (cut 2026-11-14): "is this a breadth failure" and coherent grouping
  are semantic judgments with a high false-positive risk on one observed case.
  Also out: modifying artifacts or feedback state; applying revisions; a group
  manifest; atomic publication; automatic approval; concurrent revision
  management; a general roadmap editor.
- **Allowed behavior changes:** none; documentation only.
- **Allowed reorganization:** none.
- **Verification:** the paragraph states only steps that the existing roadmap
  commands support, checked against `docs/reference/commands.md`'s roadmap
  flags.
- **Stop / defer:** re-open a diagnostic only if several observed failures show
  a groupable pattern a deterministic check could name; any request to edit
  feedback, execute a subset, approve a revision, or publish artifacts belongs
  to the existing roadmap lifecycle or a separate backlog item.
- **Approach:** `direct` — documentation only.
- **Quality:** `gate-signal` — makes an over-broad revision failure actionable
  without weakening existing publication authority.
- **Origin:** 2026-09-21, Integration full-MVP roadmap review; reshaped
  2026-11-14 from a read-only diagnostic to guidance.
- **Status:** not started.

**#428 — A ledger proposal's current-or-stale status is defined but never computed**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced` — a read-only derived label with no persisted state
  · Principle `untriaged`
- **What:** `roadmap-versioned-feedback-revision-chain` defines a stored
  ledger proposal as *current* only while its bound candidate revision is one
  member of the current processing pair (the accepted root or the active
  candidate), and *stale* once supersession, rejection, discard, or an
  accepted-head change leaves it outside that pair
  (`docs/implementation-plans/archive/2-roadmap-versioned-feedback-revision-chain.md`,
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
- **Arc assignment:** `backlog-arc-roadmap`.
- **Renumbered:** filed as #425 on this branch on 2026-09-23 and cited that way in its commit history; renumbered to #428 on merging `main`, which had already allocated #425.
- **Origin:** 2026-09-23, post-run review of
  `roadmap-versioned-feedback-revision-chain`.
- **Status:** not started.

**#430 — Investigate whether the same-receipt re-entry return in the batch proposal path can ever fire**

- **Labels:** Route `direct`
  · Readiness `evidence-gated`
  · Tier `experienced` — it needs a trace of the batch states, not a design decision
  · Principle `untriaged`
- **What:** `_run_batch_candidate_proposal` in
  `plan_tool/roadmap_candidate_run.py` (line 1587) returns the stored active
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
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** found 2026-09-23 in code review of
  `roadmap-structural-feedback-approval`; filed 2026-09-24 at the owner's
  direction. It sits outside that plan's range and breaks nothing.
- **Status:** not started.

**#433 — Print a periodic stderr heartbeat during ledger-batch candidate proposals**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** make `plan-tool roadmap <slug> --propose-candidate` print a periodic
  stderr heartbeat while a ledger-batch candidate proposal is running, built
  from the `claude_call_progress` events the run already emits: elapsed time
  and backend-silence time.
- **Why:** Integration candidate proposals commonly take one to four minutes. The
  command currently writes `claude_call_progress` events into
  `.plan-tool/runs/<slug>/...jsonl` every 20 seconds, but prints no incremental
  terminal status. An operator cannot tell whether the local process is still
  alive without manually locating and tailing the run log.
- **Effort:** small. The run-log events already exist; the command needs a
  bounded stderr line on each progress event, stable wording, and tests.
- **Risks / fallout:** the heartbeat must not claim that the backend is healthy
  merely because the local process emits a timer tick. It must say elapsed time
  and backend silence explicitly, preserve machine-readable command output, and
  avoid model/prompt content.
- **Dependencies:** evaluate `#349`'s `progress.py`/roadmap-status seam before
  adding another reporter. This item may reuse that reporter but must not
  expand `#337`'s completed stage-run contract by implication.
- **Outcome:** a terminal operator can see that a ledger-batch candidate
  proposal is locally alive, with elapsed time and backend-silence time, without
  inspecting JSONL files by hand; a quiet backend remains visibly "waiting"
  rather than being represented as confirmed backend progress.
- **In scope:** batch `--propose-candidate` only; one stderr line per existing
  `claude_call_progress` event carrying elapsed and silence time; stderr
  routing; focused CLI/reporter tests.
- **Out of scope / Non-goals:** deliberately not a lifecycle vocabulary (batch
  accepted, attempt started, response validation, retry/correction, stored,
  rejected, failed) and not a new reporter-seam design (cut 2026-11-14): the
  heartbeat answers the operator's actual question, "is it still alive", at
  small cost. Also out: streaming model output or prompts; job control,
  cancellation, dashboards, persistent live-job state, candidate review or
  promotion status, generic status expansion across all commands, and changing
  JSONL schema or candidate authority.
- **Allowed behavior changes:** additional human-readable stderr lines during
  batch candidate proposals. Candidate bytes, feedback state, retries, exit
  codes, and machine-readable output retain their existing semantics.
- **Allowed reorganization:** only the smallest extraction needed to reuse a
  current progress/status reporter if `#349` has produced one; do not refactor
  unrelated roadmap status paths.
- **Verification:** use an injected delayed candidate invoker to assert one
  heartbeat line per progress event; assert silence time is labelled as silence
  rather than success; verify no model content appears; and prove JSONL
  lifecycle records and command results remain unchanged.
- **Stop / defer:** if `#349` selects a shared reporter contract that changes
  the implementation shape, route this item through that contract rather than
  adding a second status channel. A request for lifecycle status, real backend
  liveness, or job control is separate work.
- **Approach:** `direct` — a small stderr hook over existing events.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** Integration ledger-batch candidate acceptance attempts on 2026-09-28;
  narrowed 2026-11-14 from a full lifecycle reporter.
- **Status:** not started.

**#437 — Let a candidate reconciliation response state its basis, and show when it does not**

- **Labels:** Route `plan`
  · Readiness `parked`
  · Tier `experienced` (a prompt and an additive persisted field within existing contracts)
  · Principle `untriaged`
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
- **Dependencies:** IPPT-18 and IPPT-19 have landed (archived plans
  `2-candidate-prose-correction` and `2-candidate-narrative-review-evidence`).
  IPPT-19's computed-evidence function is where the basis check would plug in.
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
- **Unpark when:** reviewers are observed to miss an unjustified "no change" candidate response.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** the IPPT-19 plan carve, 2026-10-02.
- **Status:** not started; parked 2026-11-14 (the Integration case does not need it).

**#438 — Widen the narrative check's removed-id source to a candidate's own `remove-row` operations**

- **Labels:** Route `plan`
  · Readiness `decision-needed` (own-removal case observed above; the false-positive measurement comes first)
  · Tier `architect` (widens a blocking policy source)
  · Principle `untriaged`
- **What:** IPPT-19's narrative check finds live prose that names a removed row,
  but only for removals recorded in the candidate artifact's own carried
  `removals` (or, for a feedback-free candidate, its immediate predecessor's).
  A row dropped by the candidate's own `remove-row` operation writes no removal
  record, so it escapes. This entry derives the removed ids for that observed
  case, so it shows the same evidence as a carried removal.
- **Why:** the code review of IPPT-19 (round 6, 2026-10-05) found the gap by
  static reading, and Integration Group 5 supplies observed evidence for the
  candidate's own-removal case (below).
- **Deliberately not (cut 2026-11-14):** the stacked-root case, a removal
  recorded at the accepted root of a stack of feedback-free batches that the
  tip's immediate predecessor no longer carries. It remains unobserved; re-open
  it only if a real stack shows it.
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
- **Effort:** small-to-medium. A second removed-id source (the candidate's own
  `remove-row` operations) in `check_removed_ids_in_live_prose` and
  `compute_candidate_narrative_evidence`, the contract section "Source of the
  removed ids", and tests.
- **Risks / fallout:** a widened source widens the blocking class, so the
  false-positive rate on real candidates must be measured before the source
  blocks anything. Deriving ids from `remove-row` operations (not a row-id
  difference) avoids counting a row replaced under a new id as removed.
- **Dependencies:** IPPT-19 lands first.
- **Outcome:** a candidate that removes a row through its own `remove-row`
  operation shows the same removed-id evidence as a carried removal.
- **In scope:** the removed-id source for the candidate's own `remove-row`
  operations, a false-positive measurement over real candidates, and the
  contract text.
- **Out of scope / Non-goals:** the stacked-root case (see above); deriving the
  set from a predecessor/candidate row-id difference; any model-judged review
  (#435); a new defect class; changing what blocks approval or the operator
  exits; storing evidence.
- **Allowed behavior changes:** more candidates are shown, and may be refused,
  for prose that names a removed id.
- **Allowed reorganization:** none.
- **Verification:** the false-positive rate on real stored candidates is
  measured and recorded here before the source blocks; a candidate with its own
  `remove-row` and prose naming the row is refused with both exits (the
  Integration candidate above is the first fixture); the existing
  carried-removal cases are unchanged.
- **Stop / defer:** if the measured false-positive rate on real candidates is
  not low, stop and record the rate here.
- **Approach:** `plan-tool`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** the IPPT-19 code review, round 6, 2026-10-05.

**#439 — Decide whether one candidate may replace a row and correct the paragraph that describes it**

- **Labels:** Route `plan`
  · Readiness `parked` (parked 2026-11-14: the stacked route works, and this reverses a settled, architect-reviewed contract to save one review round)
  · Tier `architect` (changes a settled candidate contract)
  · Principle `untriaged`
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
- **Unpark when:** the second-round cost of the stacked route recurs across more than one lineage.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** Integration Group 5 prose correction diagnosis, 2026-10-05; moved from
  `BUG_BACKLOG.md` after the stacked route was shown to work.

**#440 — Measure whether listing uncorrected paragraphs that name changed rows would help a candidate reviewer**

- **Labels:** Route `plan`
  · Readiness `evidence-gated` (gate: the measured false-positive rate)
  · Tier `experienced`
  · Principle `untriaged`
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
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** Integration Group 5 stacked-route trial, 2026-10-05.

**#449 — Remove the code the retired escalation, impact-analysis, and structural-rewrite routes left callerless**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** `roadmap-versioned-from-birth` step 9 caller trace, 2026-10-06.

**#450 — Remove retired roadmap routes from the docs outside the version-only docs sweep**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `roadmap-versioned-from-birth` step 12 swept the roadmap docs, but
  these live docs still name a removed route (`--from-stage`,
  `--confirm-brief-rebind`, `--enroll-version`, `--reopen-feedback`, escalation,
  impact analysis, or structural rewrite): `CAPABILITIES.md` (not yet in the
  guard's file list) and `docs/reference/contracts/codex-cli.md` (§ "Structural
  evaluator capability profile"). `docs/how-to/use-cases.md`,
  `docs/how-to/common-workflows.md`, `docs/reference/commands.md`, and
  `BUG_BACKLOG.md` are already in `_REMOVED_ROUTE_DOC_FILES` and pass.
- **Why:** each reads as current behavior and sends a reader to a refusal.
- **Effort:** small — doc edits plus extending the removed-route guard's file list.
- **Approach:** `direct`.
- **Outcome:** no live doc names a removed roadmap route outside dated history.
- **In scope:** the two files above; adding `CAPABILITIES.md` to
  `_REMOVED_ROUTE_DOC_FILES` in `tests/test_roadmap_format.py`.
- **Out of scope / Non-goals:** any replacement route for structural rewrite or
  revision restore.
- **Verification:** the extended `test_live_roadmap_docs_name_no_removed_route`
  passes.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** `roadmap-versioned-from-birth` step 12 sweep, 2026-10-06.

**#451 — Remove the stage-feedback revision path and result fields the stage-run rewrite left callerless**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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
    at `cli/roadmap_cmd.py:554-558`) always print nothing in production; only
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
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** `roadmap-versioned-from-birth` code review 1, 2026-10-06; producer-less
  stage-loop names added from code review 2, 2026-10-06.

**#453 — Stop `INDEX.md` from naming a stale accepted head after a failed refresh**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `refresh_roadmap_index` warns and returns when `collect_index_rows`
  raises `RoadmapVersionError` (one unreadable `version.json`,
  `candidate-evidence.json`, terminal resolution, or admission file), so the
  previous `INDEX.md` stays on disk after a promotion and still labels the old
  version `accepted head`.
- **Why:** a file generated for people can name the wrong head with only a
  transient stderr line as the signal.
- **Verified:** by reading `roadmap.py` (`refresh_roadmap_index`) and
  `roadmap_index.py` (`collect_index_rows`, `write_roadmap_index`). No program
  was run; a reproducing test is the first step of the fix.
- **Effort:** small — one degrade rule and its tests.
- **Approach:** `direct`; on a refresh failure, rewrite `INDEX.md` with a
  one-line could-not-refresh body naming the failure, so the file never names a
  superseded head as current.
- **Dependencies:** none; independent of the BUG_BACKLOG.md ROADMAP entry
  "A publication journal left by a crash blocks most roadmap writers until a
  stage run, and a non-root journal beside a head can only be removed by hand".
- **Outcome:** a refresh failure never leaves an `INDEX.md` that names a
  superseded accepted head without saying it is stale.
- **In scope:** `refresh_roadmap_index`, `roadmap_index.py`, and the tests and
  docs (`ROADMAP_FORMAT.md`, `docs/how-to/roadmap.md` § 3) that pin them.
- **Out of scope / Non-goals:** changing the head, journal, or version-store
  formats; per-version degrade in `collect_index_rows` (deliberately not taken:
  the could-not-refresh body is the smaller change); scoping the first-run
  resume directory by plans directory (deliberately not taken, cut 2026-11-14:
  it needs two plans directories sharing a slug in one repo, which no run has
  produced; revisit only if one is observed); a cross-plans-dir lock.
- **Allowed behavior changes:** a refresh failure rewrites `INDEX.md`.
- **Allowed reorganization:** none.
- **Verification:** a test with one unreadable historic record after a
  promotion showing `INDEX.md` does not name the old head as current; the full
  suite passes.
- **Stop / defer:** none beyond the fence above.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** `roadmap-versioned-from-birth` code review 4, 2026-10-06.

**#454 — Make a `run` step verify its own edits and sweep the tests that pin the old behavior before it finishes**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
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
- **Arc assignment:** `backlog-arc-run-gates`.
- **Origin:** `roadmap-versioned-from-birth` run, 2026-10-06.

**#455 — Give a failed `run` step's retry the complete failure list**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** the failure note a retry sees keeps a short pytest tail. In step 3
  attempt 2, 3 of the first 6 failures were not visible to the model, and the step
  needed manual repair. A stale tail also persists in `status_note` after the step
  later advances.
- **Absorbs #88 (merged 2026-11-14), parked:** a `run` step whose `claude`
  call succeeded but whose post-call test-authoring or drift gate failed
  re-spends the whole call on re-run. The remedy is to re-evaluate the
  post-call gates against the tree already on disk without a new call; the
  call's output is tree edits already on disk, so memoizing it is the wrong
  frame. Acceptance: a post-gate failure re-runs without a new model call when
  inputs are unchanged. Reuse `checkpoint.py` only if the re-evaluation needs
  saved state. Resume is otherwise already durable per `claude` call in
  `detail` and `completeness-audit`; no second stage ledger. This remains
  open and is parked with the bounded-repair attempt (see Parked below).
- **Why:** a retry that cannot see the failures it must fix cannot fix them, and a
  halt costs a human turn for failures the model could repair when shown the
  full list.
- **Verified:** not yet. `launcher.py`'s attempt and retry limits, how
  `status_note` is built, and whether the tail truncation is in the gate output or
  in the note were not read. Read them first.
- **Verified (2026-10-08, partial):** a retry's prompt carries no failure
  information at all. `plan_tool/prompts/run.md` has no `status_note` variable,
  and `plan_tool/renderer.py` never reads `status_note`. The note exists only in
  the plan file: the first 400 characters (`launcher.py:2228`, `:2278`) of the
  500-character tail that `_run_test_gate` returns (`launcher.py:965`). So (a)
  renders the previous gate's failed test ids into the retry prompt, not only a
  longer note. A run that advances the step clears the note
  (`launcher.py:2345`). A stale note survives only a hand-advanced step, which
  `run --accept` (shipped 2026-10-10) closes. Second instance: `roadmap-stack-propagation` step 1, observed
  2026-10-08. After `.tmp/roadmap-stack-propagation.run.log` failed on one test,
  the re-run (`run-step1-retry2.log`, 48 s) modified no declared file.
- **Effort:** small.
- **Approach:** `direct`: carry the failed test ids with one error line each
  (`pytest -rf` summary) into the retry prompt and clear the note when the step
  advances.
- **Parked (split from this entry, cut 2026-11-14):** an in-run bounded
  repair attempt. The run halts after one failed suite gate: it halted at steps
  3 through 9, and steps 4, 5, 7, 8, and 9 were small mechanical fixes (a
  comment, an import, a helper, snapshot helpers, fixtures) that each cost a
  manual round trip and a WIP commit. Whether to add the attempt is decided
  after this entry ships and its effect on retries is observed; it interacts
  with the attempt limits and with the no-re-spend rule absorbed from #88. It
  needs its own entry with an id when taken up; this paragraph is its
  placeholder.
- **Dependencies:** #87 (same gate family).
- **Outcome:** a retry sees every failed test id from the previous gate with a
  one-line error, and a stale note does not outlive the step's advance.
- **In scope:** failure-note construction, rendering the ids into the retry
  prompt, `status_note` lifecycle, and their tests.
- **Out of scope / Non-goals:** the in-run bounded repair attempt and the
  post-gate re-evaluation absorbed from #88 (deliberately not in this slice:
  both wait on this slice's observed effect; see Parked); raising the attempt
  limit by default; changing what the gate checks; unattended retry loops
  without a bound.
- **Allowed behavior changes:** failure notes get longer; a stale note is cleared.
- **Allowed reorganization:** none.
- **Verification:** a test with more failures than the old tail holds, showing all
  ids reach the retry prompt; a test showing the note is cleared on advance; the
  full suite passes.
- **Stop / defer:** the parked repair attempt and the #88 re-evaluation stay
  open after this slice ships; the entry's removal waits until they ship or are
  recorded as declined. Before building them, state how the test-authoring
  gate's pre-call baseline survives a tree the first attempt already dirtied
  (#87's known limit).
- **Arc assignment:** `backlog-arc-run-gates`.
- **Origin:** `roadmap-versioned-from-birth` run, 2026-10-06.

**#457 — Re-run only the failed tests once before a `run` step fails on the suite gate**

- **Labels:** Route `direct` · Readiness `parked` · Tier `experienced` · Principle `untriaged`
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
- **Stop / defer:** with one instance, stay parked; a retry can also mask a
  real order-dependent failure, so the retry stays at one and reports both results.
- **Unpark when:** a second non-reproducing gate failure occurs.
- **Arc assignment:** `backlog-arc-run-gates`.
- **Origin:** `roadmap-versioned-from-birth` run 6, 2026-10-06.

**#458 — Report the test names a step's detail lists that no test file contains (advisory only)**

- **Labels:** Route `direct`
  · Readiness `evidence-gated` (gate: the measured false-positive rate)
  · Tier `experienced`
  · Principle `untriaged`
- **What:** a step can write production code and no tests; the test-authoring
  gate knows only whether a test file was touched. Step 6's first pass edited
  production code and no test file, and 14 test cases named in the detail's
  `## Tests` section were absent.
- **Absorbs #427 (merged 2026-11-14):** the archived plan
  `roadmap-versioned-feedback-revision-chain` is this advisory's ready-made
  false-positive corpus. Its eleven step detail files cite 212 backticked
  `test_*` names; 95 are defined in `tests/` and 117 are not (re-run
  2026-11-14; cited/defined per step: 1: 15/9, 2: 8/0, 3: 12/0, 4: 16/2, 5:
  34/24, 6: 34/8, 7: 22/10, 8: 29/19, 9: 17/17, 10: 16/2, 11: 9/4). A missing
  name is a claim to check, not proof the behavior is untested, and a defined
  name does not prove the test asserts what the detail says. Spot-check only
  steps 2, 3, 4 and 10 (0–2 defined) for genuinely uncovered behavior. Do not
  rewrite the archived plan's detail files; nobody reconciles a closed plan.
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
- **Arc assignment:** `backlog-arc-run-gates`.
- **Origin:** `roadmap-versioned-from-birth` run, step 6, 2026-10-06.

**#459 — Decide what `reconcile-code --no-walk` promises, since an audit call still edited a test file**

- **Labels:** Route `direct`
  · Readiness `decision-needed`
  · Tier `experienced`
  · Principle `untriaged`
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
- **Arc assignment:** `backlog-arc-run-gates`.
- **Origin:** `roadmap-versioned-from-birth` reconcile-code sweep 2, 2026-10-06.

**#462 — Audit every plan derived from an accepted roadmap against its settled decisions and against each other, reported in one saved advisory report**

- **Labels:** Route `plan`
  · Readiness `parked` (owner decision 2026-10-15 kept the evidence gate)
  · Tier `architect` (it defines a new audit surface and what it may assert, where a wrong call is invisible because the report checks plans against themselves)
  · Principle `converge-on-correct-plan`
- **What:** The per-plan completeness audit judges one plan against code at HEAD and never reads the accepted roadmap, so a plan that contradicts a settled roadmap decision or stack row, or two plans that each choose their own technology for a store the roadmap says is shared, pass unseen; a roadmap-level cross-plan audit holds the accepted roadmap version as its reference, puts it and every derived plan (optionally every draft seed) in front of one auditor, and saves the conflicts it reports.
- **Effort:** medium; one new read-only audit surface (prompt, invoker seam, report persistence, CLI), plus derived-plan discovery from the roadmap's existing plan rows and seed state.
- **Risks / fallout:** the property is semantic and unobservable, so the surface can grow into a checker; the not-built list below is the fence. Plan-vs-roadmap stack conflicts overlap the per-plan audit, since the shipped `## Stack` section carries the stack into the plan body, so the cross-plan audit's own value rests on what no single-plan audit can see. A shared report read as a verdict trains operators to treat silence as clearance.
- **Dependencies:** the shipped `## Stack` section (the stack rendered into seeds and carried into plan bodies). Independent of #461 (shipped): a version without a `stack` collection is judged against its hosting and store rows and settled decisions.
- **Outcome:** One command run against an accepted roadmap writes a saved report that names the accepted version id it was judged against, lists every derived plan (and draft seed, when included) it read, and records each conflict the auditor reports between a plan and a settled roadmap decision or stack row, or between two plans.
- **In scope:** a read-only cross-plan audit command over one roadmap slug; resolving the accepted-head version; discovering derived plans from the roadmap's existing plan rows and seed state; an audit prompt carrying the accepted version's settled decisions, stores, hosting rows (and `stack` rows when present), and each derived plan's body and detail files; the saved report and its listing; the invoker seam and its `TESTING.md` neutralization row; `docs/cli/` regeneration; the how-to and `ROADMAP_FORMAT.md` cross-reference.
- **Out of scope / Non-goals:** each of these is deliberately not built, with its reason:
  - a gate, refusal, or blocking state on any finding — the property is semantic ("does this plan contradict that decision"), and a check firing on prose with no runnable remedy is the refused shape in `CLAUDE.md` § "Validating a semantic property you cannot observe"; deliver, don't verify;
  - an exit-code flip or a new `--fail-on-findings` path — the exit-code convention holds: a completed audit exits 0 with findings;
  - a deterministic technology-name comparison (matching `PostgreSQL` against `SQLite` strings) — it measures vocabulary, not the property, misses a plan that names no product or a synonym, and a high false-positive proxy is killed, not tuned;
  - a new roadmap artifact or a fifth roadmap stage file — decided 2026-10-08 under #461; the report is a saved audit report outside the roadmap's versioned store and never enters a roadmap version;
  - auto-applying findings — conceptual application commands are retired; whoever drives the plan reads the report and edits through that plan's own audit loop;
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
- **Unpark when:** a concrete case shows what this report catches or resolves that #492's shared contract record and coordinated session-directed edits cannot.
- **Evidence gate:** the gate is met when one accepted roadmap lineage shows a conflict that a per-plan completeness audit passes clean with `## Stack` carried into the plan body: two derived plans contradicting each other, or a plan contradicting a settled decision that the `## Stack` section does not carry into the plan body. Closing with "no action" is a valid outcome.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Seed:** none until the evidence gate is met.
- **Origin:** Integration owner request, 2026-10-08. Premise checked read-only on 2026-10-08 against Integration (`<integration-consumer-root>`) and found exactly one conflict:
  - **The one conflict (plan vs. roadmap):** the accepted version (`57e2912e…`, matching the working copy) declares `store-app-db` relational/pool with `product: PostgreSQL` (`roadmaps/integration-aidlc-mvp/03-components.md:20-23`) under settled `decision-shared-database` (`:134-141`); `2-connector-registry-seed.md:47` persists to "the shared SQLite database" while its own Architecture names only `store-app-db` with no product (`:78`). The plan was uncommitted, and its details folder held only `grounding.json`, so no per-plan audit had run.
  - **Draft seeds:** all six cite `store-app-db` by id; none names a database product, hosting product, or language, and none contradicts another or the roadmap.
  - **Plan vs. plan within the roadmap:** none possible; `connector-registry-seed` was the only plan derived from `integration-aidlc-mvp`.
  - **Outside this entry's reference:** `2-workspace-membership-selection.md` derives from the separate `project-workspace-membership-proof` roadmap, defers its store product (`:224`), and creates `pyproject.toml` with a `src/integration/` layout (`:22-23`) where the connector plan creates a flat `integration/` package (`:33-35`); that cross-roadmap collision is not a stack-decision conflict and is out of scope here.
  - The SQLite case is within the `## Stack` section's reach once the stack is carried into the plan body, so it does not yet show a conflict only a cross-plan audit can see; hence the gate stays and the entry is parked.
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
  is not itself a between-plan conflict this item can detect. #492 (closed) owned that
  composition investigation; new context delivery (#493) is discarded. Preserve this
  entry's evidence gate and no-new-quality/ordering/gating fence; do not mark it
  ready solely because another per-plan audit needed manual coordination.

- **Owner decision (2026-10-15):** retain the existing evidence gate
  (labelled `parked` since 2026-11-14); no seed or implementation proceeds. The cited
  Integration audits detect the recorded cross-plan conflicts. Coordinated fixes
  demonstrate a resolution problem, not an additional detection capability.
  Use #492's shared contract record and coordinated session-directed edits for
  that case. Revisit this item only with a concrete case showing what its
  additional report catches or resolves that those existing routes cannot;
  changing the current gate requires a separate explicit owner decision.

**#464 — Twelve test assertions pin a line break inside a prompt or doc sentence, so rewrapping that text with no word changed fails the suite**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `beginner`
  · Principle `none` (test hygiene, and no principle is served directly)
- **What:**
  - 12 assertions in 4 test files match a phrase containing a hard line break
    taken from hard-wrapped prose:
    - `tests/test_create.py:17205`
    - `tests/test_roadmap_candidate_run.py:1675`, `:1942`, `:1993`, `:1995`,
      `:2027`, and `:2086`
    - `tests/test_roadmap_format.py:550`, `:553`, and `:555`
    - `tests/cli/test_inspect_cmds.py:704` and `:706` (against `CLAUDE.md`)
  - This contradicts the rule the repository already states at
    `tests/test_roadmap.py:959` (`_flattened`): "a rewrap that changes no
    words must not redden a check".
  - Count method: a search over `tests/` for quoted literals containing
    `[a-z,;:\`)]\n[a-z\`(]` followed by ` in `. Structural line breaks were
    then excluded: heading-then-body, fenced blocks, paragraph boundaries, and
    multi-line record bodies. Those are `tests/test_concept_sync.py:177` and
    `:193`, `tests/test_jira.py:956` and `:974`, `tests/test_create.py:11867`,
    `:16045`, `:16061`, `:16079`, and `:16080`,
    `tests/test_roadmap_revision_patch.py:672-673`, and
    `tests/cli/test_roadmap_cmd.py:6908`. Those excluded assertions pin
    structure, not wrapping, and stay.
- **Why:** a no-word rewrap fails a test, and the fix that comes naturally is
  restoring the old wrap rather than correcting the test. Observed 2026-10-08:
  the step-2 hand fix of `roadmap-stack-propagation` was "restoring a pinned
  prompt line break" (`b77efc10`) for the `tests/test_create.py:17205`
  assertion.
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
    files (`tests/test_roadmap.py:959`, `tests/test_roadmap_feedback_format.py:89`,
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
- **Start here:** the 4 test files above.
- **Precedent:** `_flattened` at `tests/test_roadmap.py:959` and its uses, for
  example at `:1391`, `:1484`, `:1491`, and `:1502`.
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

**#468 — Give roadmap retries the rejected proposal so they can correct specific defects**

- **Labels:** Route `direct`
  · Readiness `parked` — efficiency follow-up
  · Tier `architect`
  · Principle `converge-on-correct-plan`
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
- **Unpark when:** roadmap retry failures recur after the ordering fixes.
- **Status:** parked; one consumer observation, and the retry would add about 68 KB of context.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** Integration owner requested these plan-tool updates on 2026-10-09.

**#472 — Learn a Claude model's context window before its first call**

- **Labels:** Route `direct`
  · Readiness `evidence-gated` (confirm the suffix against a real run first)
  · Tier `experienced`
  · Principle `deterministic-non-determinism`
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
- **Quality:** `gate-signal` — the advisory and the gate stop judging a 1M-window model against 200,000.
- **Status:** not started.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** deferred follow-up from the model-aware prompt-budget code review (2026-10-09).

**#477 — Fix the stale and bare `BUG_BACKLOG` citations in code**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `docs/TRACKING.md:771-772` says "`BUG_BACKLOG.md` entries are
  titled headings with no id", so code cites bugs by title or not at all. Of
  21 `BUG_BACKLOG` mentions under `plan_tool/`, seven are a bare
  "See BUG_BACKLOG." with no title (`create.py:12024`, `data_contract.py:643`,
  `review.py:1837`, `review.py:1862`, `detail.py:1542`, `detail.py:2041`,
  `cli/completeness_phases.py:2278`). Two title citations no longer resolve,
  and only git history says why: `tests/test_launcher.py:2853`
  cites "`run` advances a step whose `creates:`…", an entry removed when the
  bug was fixed (`4fc168027`); `completeness_report.py:1502` cites "The
  persisted report withholds ``suggested_action``", fixed in `72de18d29`,
  a title no backlog file has ever carried.
- **Outcome:** no bare or stale `BUG_BACKLOG` citation remains under
  `plan_tool/` or `tests/`.
- **In scope:** the two stale and seven bare citations: name the live entry's
  title, or delete the citation when the entry is gone or the comment stands
  alone.
- **Out of scope / Non-goals:** stable bug ids (`B-N`), extending
  `tests/test_backlog_ids.py` to `BUG_BACKLOG.md`, and the TRACKING.md rule
  change (deliberately not taken, cut 2026-11-14: nine citations cost minutes
  to fix; adopt ids only if bug citations from code keep rotting after this
  cleanup); checking that a cited title is still live; renumbering
  `BACKLOG.md`.
- **Verification:** a grep shows no bare "See BUG_BACKLOG." and neither stale
  title under `plan_tool/` or `tests/`.
- **Stop / defer:** if a citation names a title that exists in
  `BUG_BACKLOG.md`, keep it.
- **Status:** not started.
- **Origin:** tracking-process review, 2026-10-10.

**#478 — Prune delivered, closed and no-action backlog entries, then re-measure before splitting the catalog**

- **Labels:** Route `direct` · Readiness `ready` · Tier `experienced` · Principle `untriaged`
- **What:** `BACKLOG.md` is about 13,500 lines, `docs/TRACKING.md` is 1,107, and
  `BUG_BACKLOG.md` is 2,155. A reader or a session loads most of a file to find
  one entry or one rule, and duplicated guidance drifts (the TRACKING.md recipe
  skipped the bare-plan audit until 2026-10-10). A value review of one range of
  the catalog found about 18 entries that are delivered, closed, no-action, or
  self-admitted low value; splitting the file by area would carry them along.
- **Outcome:** the delivered, closed, no-action and self-admitted-low-value
  entries are removed under `docs/TRACKING.md`'s removal rules, and the
  catalog's size and lookup cost are re-measured afterwards. A split decision
  waits on that measurement.
- **In scope:** the pruning, and the re-measurement (line counts, and whether
  sessions still fail to find entries or rules: missed duplicates, misapplied
  recipes).
- **Out of scope / Non-goals:** splitting the catalog by area now (deliberately
  not taken, cut 2026-11-14: a split preserves the bloat; reconsider only if
  the re-measurement still shows a cost); moving guidance out of the catalog;
  the entry format and the labels (#476, #477).
- **Verification:** the id test and the readability guard pass after the
  pruning; every removed id's citations elsewhere resolve to a closed or
  stub record or are rewritten.
- **Stop / defer:** stop if the readability guard
  (`tests/test_backlog_readability.py`) or external Jira links depend on an
  entry slated for removal. If the re-measurement shows no remaining cost,
  close with "no action".
- **Status:** not started.
- **Origin:** tracking-process review, 2026-10-10.

**#484 — Mark each finding the `edit_drift` advisory attributes to the previous apply, and count them**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `converge-on-correct-plan`
- **What:** the `edit_drift` advisory (`convergence_diagnosis.py`,
  `classify_edit_drift`) says only that a strict majority of new findings match
  the prior-apply set. The report does not say which findings those are, so a
  finding against surface the previous round's fix added reads the same as a
  defect in what the plan always promised.
- **Evidence:** a Integration fix added a deployment-role construct to
  `cdk-infrastructure-and-environments`. The next round produced 8 new HIGH
  findings across that plan and `bitbucket-deployment-pipelines`, all on the
  new construct (Integration reports under
  `plan-details/<plan>/reports/20261010-*-completeness.md`).
- **Effort:** small to medium; `classify_edit_drift` already builds the
  window-local prior-apply set, so the work is exposing its matches per finding
  and rendering them.
- **Risks / fallout:** the match is a judgment; a wrong mark could teach
  operators to dismiss a real defect.
- **Dependencies:** none.
- **Outcome:** `EditDriftAdvisory` carries the matched findings, and the
  `edit_drift` rendering (`_edit_drift_lines`) marks each one and states the
  count of marked findings beside the total.
- **In scope:** `classify_edit_drift`, `EditDriftAdvisory`,
  `_edit_drift_lines`, and their tests.
- **Out of scope / Non-goals:** a separate attribution rule or a plan-snapshot
  diff-to-finding mapping (deliberately not taken, cut 2026-11-14: it overlaps
  the shipped `edit_drift` match); a new completeness-report field; marking
  when the advisory does not fire; suppressing, demoting, or excluding a marked
  finding from the blocking set; changing the stopping rule (#125) or any
  continuation or exit behavior (`edit_drift` stays recommend-only).
- **Allowed behavior changes:** the per-finding mark and count in the existing
  advisory output only.
- **Allowed reorganization:** none.
- **Verification:** a fixture where `classify_edit_drift` fires asserts the
  advisory lists exactly the matched findings and the rendering marks them and
  gives the count; an unmatched finding is not marked.
- **Stop / defer:** stop if a match cannot be tied to a finding without
  inferring from prose; surface that rather than guess.
- **Approach:** direct; extend the existing advisory.
- **Quality:** `convergence` — separates fix-induced growth from real
  non-convergence.
- **Status:** not started.
- **Origin:** Integration `integration-aidlc-mvp` nine-plan roadmap-to-plan run, 2026-10-10.

**#486 — Say in `detail`'s description and console output that it runs a completeness audit and saves a report**

- **Labels:** Route `direct` · Readiness `ready` · Tier `beginner` · Principle `write-for-the-human`
- **What:** `detail` runs a completeness audit after authoring and writes a
  report under `plan-details/<plan>/reports/`. `detail --help` states this
  only under `--no-completeness`. The run's console output already names the
  audit (`cli/authoring.py:2269`) and the saved report path
  (`cli/completeness_phases.py:4029`); the `detail` subparser has no
  description. Integration operators found the reports only by listing the reports folder during the
  2026-10-10 roadmap-to-plan run.
- **Effort:** small; the argparse description and the directive.
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
- **Status:** not started.
- **Origin:** Integration `integration-aidlc-mvp` nine-plan roadmap-to-plan run, 2026-10-10.

**#487 — Audit infrastructure-as-code plans only against resources the plan defines the creation of, and name the rest as exceptions**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `converge-on-correct-plan`
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
- **Effort:** small; the directive ships at
  `integrations/shared/DIRECTIVES.md` § "Infrastructure plans: claim scope only
  for resources the plan creates". Remaining: a Gate 2 prompt clause in
  `plan-audit.md`.
- **Risks / fallout:** an exception list can hide a real gap; the plan states
  each exception in its own prose with its reason, so the exception is visible
  in the plan the audit reads.
- **Dependencies:** none.
- **Outcome:** the detail-grounded audit prompt tells the auditor to judge
  isolation, scoping and least-privilege claims only against resources the plan
  creates, and to treat toolchain resources the plan names as exceptions (with
  their stated reason) as out of scope.
- **In scope:** the detail-grounded audit prompt clause (`plan-audit.md`); the
  directives text already ships.
- **Out of scope / Non-goals:** deciding which resources a given toolchain
  creates; relaxing checks on resources the plan does define; a new
  completeness-report field for declared exceptions and demoting findings
  against them to informational (deliberately not taken, cut 2026-11-14: the
  machinery outgrows a prompt clause; if recorded exceptions are wanted, route
  them through #490 dispositions).
- **Allowed behavior changes:** the audit prompt gains the clause; no change to
  finding severity or blocking rules.
- **Allowed reorganization:** none.
- **Verification:** the prompt-content test names the clause (resources the
  plan creates; exceptions stated in plan prose); the full suite passes. Effect
  on audit output is not measurable from one test; record it on the next
  infrastructure plan audited.
- **Stop / defer:** stop if a stated exception covers a resource the plan's
  own code creates.
- **Approach:** audit prompt clause; the directive already ships.
- **Quality:** `precision` — removes defects that no plan edit can close.
- **Integration-side use:** the same rule belongs in Integration's own audit and review
  guidance, since Integration will audit infrastructure plans for its users. The
  per-technology record of out-of-scope items is started in Integration at
  `docs/technology-shapes/` (CDK first); plan-tool consumption of such an
  index is a follow-up to this entry.

**#488 — Route a failed `run` step's stated reason to roadmap feedback**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `converge-on-correct-plan`
- **Escalate to plan if:** a frontmatter provenance field is needed.
- **What:** a `run` step that stops on an upstream gap now records why, in a
  `model_failure_receipt` whose sidecar holds the executor's final reply
  (`reason: no-edits-applied`, shipped 2026-10-13). Nothing carries that reason
  to the roadmap feedback ledger, where an upstream gap belongs.
- **Why:** the gap goes back to the roadmap only if someone notices the receipt
  and retypes it as `roadmap --submit-feedback`. AI-DLC's construction loop
  treats this as a first-class move: a failure jumps back to the stage that owns
  the gap as a logged event (`aidlc-workflows`
  `core/aidlc-common/protocols/stage-protocol-recovery.md`).
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
  feedback item that names the receipt it came from, by passing a run id and
  step to `--submit-feedback` with an operator-supplied roadmap and target.
- **In scope:** `roadmap --submit-feedback` accepting a run id and step as the
  item's source reference; the feedback item's source field; tests.
- **Out of scope / Non-goals:** listing receipts never routed anywhere
  (deliberately not taken now, cut 2026-11-14: defer until an operator asks);
  choosing the roadmap target automatically;
  deciding whether the executor was right to stop; retrying the step; routing to
  anything other than the roadmap ledger; changing candidate proposal or
  approval.
- **Allowed behavior changes:** a new submission form; a feedback item may
  carry a source reference.
- **Allowed reorganization:** none.
- **Verification:** a fixture run with a `no-edits-applied` receipt, submitted
  against a named roadmap target, produces an `open` item whose source names the
  run and step; the full suite passes.
- **Stop / defer:** if binding a receipt to a roadmap needs plan provenance in
  plan frontmatter, file that as its own entry and ship with an operator-supplied
  roadmap slug and target.
- **Arc assignment:** `backlog-arc-roadmap` (adjacent to `backlog-arc-run-gates`,
  which shipped the receipt it consumes).
- **Origin:** comparison with `aidlc-workflows`' feedback model, 2026-10-13.

**#489 — Record who decided a structural roadmap approval or a decision settlement, as stated by the caller**

- **Labels:** Route `direct`
  · Readiness `parked`
  · Tier `architect` (changes an approval contract)
  · Principle `deterministic-non-determinism`
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
- **Dependencies:** none to build. Land this before Integration's
  `roadmap_driver.py` begins relaying an owner's approval into `--decide-candidate`.
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
- **Unpark when:** Integration's `roadmap_driver.py` begins relaying an owner's approval into `--decide-candidate`.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** comparison with `aidlc-workflows`' feedback model, 2026-10-13;
  owner direction that Integration facilitates human decisions rather than hiding them.

**#490 — Let an operator record a decision on an audit finding, and show it to the next audit so it is not re-raised**

- **Labels:** Route `plan`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `converge-on-correct-plan`
- **Departure kind (absorbed from #485):** Readiness `decision-needed`, Tier
  `architect` (it changes an approval contract). The authority question is
  settled first; the other dispositions ship without it.
- **What:** a completeness or reconcile finding that the operator declines,
  accepts as a known risk, or reopens has that decision recorded only in a
  handoff doc. The next audit cannot see it and re-reports the finding, so
  settled decisions get re-argued round after round.
- **Absorbs #485 (merged 2026-11-14):** a deliberate departure from an
  accepted roadmap row is a disposition of kind `departure`, citing the
  roadmap row and a bound feedback item and held in this entry's store, not a
  second suppression mechanism. Without it, every audit re-reports the
  contradiction at the same severity until the roadmap changes. Settle the
  authority question here before departures are relied on: who may record one,
  and that a pending feedback id alone does not approve a roadmap change.
- **Why:** CLAUDE.md's "do not re-open" rules and the convergence exits depend on
  a session remembering prose. AI-DLC records a per-finding human disposition in
  its ledger (accepted risk on approve, an explicit rejection carrying the
  person's exact reason, an explicit reopen) and states "never infer either
  decision from generic revision feedback"
  (`aidlc-workflows` `core/aidlc-common/protocols/stage-protocol-reviewer.md`).
- **Evidence:** the `no-edits-applied` review (2026-10-13)
  re-stated its declined
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
  text is unchanged. A deliberate departure from an accepted roadmap row is
  recorded as a `departure` disposition and is shown the same way.
- **In scope:** a disposition record (`declined`, `accepted-risk`, `reopened`,
  and `departure` absorbed from #485, citing the roadmap row and a bound
  feedback item; each with a reason); the command that writes one; the completeness-audit
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
  text changes; a plan with a recorded departure is not re-reported as
  contradicting its roadmap row while the cited row text is unchanged; the full
  suite passes.
- **Stop / defer:** if stable finding identity does not hold across rounds for
  the finding classes in scope, file that and stop. If the departure authority
  question cannot be settled, ship the other dispositions and keep `departure`
  out.
- **Arc assignment:** `backlog-arc-convergence-evidence`.
- **Origin:** comparison with `aidlc-workflows`' feedback model, 2026-10-13.

- **Evidence update (2026-10-15):** Integration's shared proposal keeps explicit
  contributor/owner decisions and finding destinations to avoid repeated
  arguments. This supports supplying dispositions to later review, not inferring
  them from a generic approval or overriding a settled roadmap. This entry stays
  owned by `backlog-arc-convergence-evidence`; #492's route only consults it.

## Public onboarding and release candidates

These candidates retain clone plus editable `uv` installation. Existing arcs own
their lanes; `backlog-arc-public-release` coordinates the release sequence.

**#508 — Separate portable skill guidance from repository team policy**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `architect`
  · Principle `write-for-the-human`
- **Arc assignment:** `backlog-arc-installed-skill`.
- **Effort:** small–medium.
- **Outcome:** Installed guidance works in a consuming repository without assuming this
  project’s organization, Jira keys, reviewer roles, or publication policy.
- **In scope:** Shared directives and all three skill routers; preserve this
  repository’s applicable policy in repository-owned developer guidance.
- **Out of scope / Non-goals:** New workflow rules, tracker configuration, automatic
  publication, or absorbing #378's convention discovery and closing rule.
- **Allowed behavior changes:** Relocate local policy and generalize examples without
  weakening this repository’s approval requirements.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no
  unrelated restructuring.
- **Verification:** Review the installed guidance from an unrelated consuming repository
  and verify local policy remains reachable. Changes to CLAUDE.md require architect-tier
  review.
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

**#509 — Have the skill router detect the Git hosting provider from the remote and confirm it with the user**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `write-for-the-human`
- **Arc assignment:** `backlog-arc-installed-skill`.
- **Effort:** small.
- **Outcome:** The skill router tells a driving session to detect GitHub or
  Bitbucket from the selected remote's URL and confirm the provider and PR target
  with the user before using `gh` or `bkt`.
- **In scope:** Router guidance text only: read the remote (origin by default, or
  the one the user names), infer the provider from its host, confirm with the user
  when the host is custom or ambiguous, and check CLI help before backend
  lifecycle commands.
- **Out of scope / Non-goals:** A configuration reader, a repository
  configuration key, or code-side provider verification (deliberately not taken,
  cut 2026-11-14: the driving session already uses `gh`/`bkt` and can confirm
  with the user; a reader plus verification is a plan for work the session does
  anyway); a hosting plugin framework, automatic publishing, history rewriting,
  or coupling provider choice to Jira/team policy.
- **Allowed behavior changes:** Router guidance text only; preserve explicit
  publication authorization. No runtime change.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no
  unrelated restructuring.
- **Verification:** The router text names the detect-then-confirm steps for GitHub
  and Bitbucket SSH and HTTPS remotes, custom hosts and alternate remotes; the
  existing router guards pass.
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

**#510 — Make onboarding skill-first with one bounded first-task walkthrough**

- **Labels:** Route `direct`
  · Readiness `blocked-on #508`
  · Tier `experienced`
  · Principle `write-for-the-human`
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
  The recipe-consistency prerequisite is satisfied (skill-router repair).
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

**#511 — Explain skill installation, refresh and the next action**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `write-for-the-human`
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

**#512 — Explain backend, model, precedence and effort choice**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `experienced`
  · Principle `write-for-the-human`
- **Arc assignment:** `backlog-arc-installed-skill`.
- **Effort:** small–medium.
- **Outcome:** Users can choose a backend/model and understand recommendations,
  configuration precedence, reasoning effort and where to find current prices.
- **In scope:** One authoritative explanation, linked from onboarding and routers:
  driving assistant versus subprocess backend versus model; Sol for Codex stages and
  Opus creation/Sonnet subsequent Claude work; explicit flags versus inherited defaults;
  reasoning-effort/token consumption and API versus subscription billing; links to
  the providers' pricing pages for current prices.
- **Out of scope / Non-goals:** Automatic model routing, a pricing service, a benchmark
  framework, or claims of equal quality/task cost from equal token prices; dated
  price comparisons (deliberately not taken, cut 2026-11-14: they go stale and
  need re-verification on every release, so the doc links the pricing pages
  instead).
- **Allowed behavior changes:** Documentation only; reconcile stale Terra
  recommendations without changing runtime defaults. Explain why creation errors
  compound and distinguish measured evidence from owner-selected recommendations.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no
  unrelated restructuring.
- **Verification:** Check claims against backend resolution and current official
  provider documentation. Pricing pages linked: https://developers.openai.com/api/docs/models/gpt-6.1-sol and
  https://platform.claude.com/docs/en/models/sonnet-5-5/overview ; the explanation
  states no price figure.
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

**#514 — Set the public distribution, license and history boundary**

- **Labels:** Route `direct`
  · Readiness `ready`
  · Tier `architect`
  · Principle `write-for-the-human`
- **Arc assignment:** `backlog-arc-public-release` (release prerequisite).
- **Effort:** small–medium.
- **Settled decisions:** Apache-2.0 (owner choice, 2026-10-19); public GitHub
  repository with ongoing internal Bitbucket sync; clone plus editable uv
  installation. Owner decision, 2026-10-20: use
  `https://github.com/rupe120/plan-tool` (currently private, owner-reported),
  possibly transferring to the Protagona organization later. Start public history
  with one fresh sanitized root shared by Bitbucket and GitHub. Maintain the same
  ancestry on both hosts and reconcile changes locally in one designated clone.
  License file and package declaration are present. Owner decision, 2026-11-06:
  the user installation is `uv tool install git+https://github.com/rupe120/plan-tool`
  (verified to install, upgrade with `uv tool upgrade` and pin a tag); the clone
  plus editable install remains the contributor route. PyPI stays out of scope
  here and is #523. Publication, transfer and remote changes remain
  separate actions. Future sync uses the shared sanitized base; do not merge
  pre-snapshot branches into it.
- **Outcome:** A reviewed release decision names the license, accessible source URL,
  supported installation/update path and public Git-history boundary.
- **In scope:** Retain the Git install for users and clone plus uv editable install for contributors; retain Apache-2.0, choose the exact public HTTPS
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

- **Labels:** Route `direct`
  · Readiness `blocked-on #510`
  · Tier `experienced`
  · Principle `write-for-the-human`
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
  recipe-consistency prerequisite is satisfied (skill-router repair); missing
  credentials remain an explicit coverage gap.
- **Stop / defer:** file adjacent work separately; resolve missing owner decisions
  before dependent implementation.

---

**#523 — plan-tool is not on PyPI, so installing it needs a Git URL**

- **Labels:** Route `direct`
  · Readiness `parked`
  · Tier `architect`
  · Principle `write-for-the-human`
- **What:** users install with `uv tool install git+https://github.com/rupe120/plan-tool`. Publishing to PyPI would shorten that to `uv tool install plan-tool`, make the tool findable on PyPI, and give it versioned releases. The name `plan-tool` was unclaimed on PyPI on 2026-11-06.
- **Arc assignment:** `backlog-arc-public-release`.
- **Effort:** about a day. Measured 2026-11-06: the wheel already bundles `integrations/`, the prompts, LICENSE and NOTICE, and an installed wheel ran `--version`, `install-skill --copy` and the start screen outside the clone.
- **Unpark when:** outside users ask for a PyPI install, versioned releases become needed, or the `plan-tool` name is at risk. Deliberately not done at launch (owner decision, 2026-11-06): the Git install removes the clone step, and every PyPI version is a permanent public release while the tool is still changing quickly.
- **Risks / fallout:** published versions cannot be replaced; release steps become user-visible; a symlinked skill points into uv's tool environment, whose path includes the Python version.
- **Outcome:** `uv tool install plan-tool` installs a released version, and each release is published from a tagged commit.
- **In scope:** trim the source distribution (it was 23 MB and 8,344 files on 2026-11-06, mostly the captured reports) with a hatch sdist include list; give PyPI a description whose links resolve (the README has 64 relative links); add authors, project URLs, classifiers and keywords; a publish job added to the existing GitHub Actions workflow (`.github/workflows/ci.yml` already runs the suite), triggered by a version tag and using Trusted Publishing; install-guide and RELEASING.md updates.
- **Out of scope / Non-goals:** automatic updates, an internal package index, changing the Git install, and publishing anything before the owner approves the first release.
- **Allowed behavior changes:** packaging metadata, CI, and documentation; no CLI behavior.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no unrelated restructuring.
- **Verification:** `uv build` produces a small sdist and the wheel; the wheel installs in a fresh environment and runs `--version`, `install-skill --copy` and the start screen; a TestPyPI publish from the workflow succeeds before the real one.
- **Stop / defer:** file adjacent work separately; the first real publish needs the owner's explicit go-ahead.
- **Dependencies:** #514 (distribution decisions).
- **Origin:** 2026-11-06, an assessment of whether to publish at public launch.

**#524 — plan-tool drives only three CLIs as backends, so Gemini, Kiro, Copilot and OpenCode users cannot run it**

- **Labels:** Route `plan` (one plan per backend; the first also settles the capture template)
  · Readiness `parked` (parked 2026-11-14: each backend is permanent surface pinned to one CLI version, no user has asked, and the provisional route exists)
  · Tier `experienced`
  · Principle `write-for-the-human`
- **What:** the registered backends are `claude`, `codex` and `cursor`. Other common coding CLIs have a headless JSON mode and could be driven the same way. An unregistered name already works as a provisional backend (`[binary, prompt]`, the claude parser, generic failure patterns, extra flags from `.plan-tool/backends.json`), which is best-effort for plain-text CLIs in batch mode and gives no streaming progress or real error classification.
- **Unpark when:** a named user requests a specific CLI as a backend; unpark one CLI at a time (Kiro is the cheapest capture and settles the template, Gemini has the largest demand; capture needs the CLI installed and an authenticated account).
- **Arc assignment:** `backlog-arc-installed-skill`.
- **Effort:** about 1–2 days per CLI, mostly capturing real transcripts and failure copy; about a day for the capture template first. Measured 2026-11-06: a backend is a manifest (`integrations/<name>/backend.json`, about 40 lines), a stream-line parser registered in `_PARSER_REGISTRY` when its event schema differs (cursor's is about 120 lines in `plan_tool/backend.py`), a contract document with fixtures (cursor 150 lines, codex 434), tests, and a skill variant.
- **Candidates:**
  - **Kiro CLI.** Verified from the real binary's help (kiro-cli 2.37.0, 2026-11-06): `kiro-cli chat --output-format stream-json` writes the run's ACP events as JSON Lines, one self-describing event per line, and implies `--no-interactive`; `--trust-all-tools` auto-approves tools and `--model` selects a model. It has two engines (`--v2`, `--v3`) and `--trust-workspace` is V3 only, so capture both engines or pin one. It is the only candidate installed on the maintainer's machine, so it is the cheapest capture and the natural first backend for settling the capture template. Login status was not checked.
  - **Gemini CLI.** Headless `gemini -p --output-format stream-json`. A `gemini-*` model-family stub already exists (`plan_tool/model_specs.py`) and `docs/BACKENDS.md` says it selects a provisional backend until a packaged integration exists. Largest demand.
  - **OpenCode.** `opencode run --format json`. Its event structure is not documented, so pin a version. One backend reaches many providers.
  - **GitHub Copilot CLI.** `copilot -p --output-format json` (JSONL). Do it when someone asks.
- **Evidence status:** the Kiro flags are read from the installed binary's help, but no transcript has been captured yet. The Gemini, Copilot and OpenCode flags come from one secondary source (a DEV Community comparison of headless modes, 2026-11-06) and are unverified; capture each against the real binary and record the version, as `docs/reference/contracts/cursor-agent-cli.md` does. Amp, Goose and Aider were not researched; Aider is plain text, so the provisional route may already cover it.
- **Risks / fallout:** each backend is permanent surface and pins one CLI version's output (the cursor contract warns that drift is likely). Real rate-limit, quota and auth failure copy cannot be captured without hitting those limits, so start from the generic patterns and mark the new patterns provisional. Assistants read skills from different places (Codex needed `.agents` and copies, not symlinks), so check each. No evidence yet that plan-tool's prompts work as well on other models.
- **Outcome:** `plan-tool --backend <name> run` completes a step end to end for each added CLI, with streaming progress and failure classification taken from captured behavior, and `install-skill --integration <name>` installs a skill its assistant reads.
- **In scope:** for each chosen CLI: the manifest, the parser if needed, captured fixtures and a contract document, tests, a skill variant and its install location, the model-family mapping, and the `docs/BACKENDS.md` and README tables. First, a capture checklist and contract-document template drawn from the cursor and codex contracts.
- **Out of scope / Non-goals:** automatic model routing; a quality or cost comparison of the new backends (the backend-recommendations benchmark is separate); backends with no headless mode; the Kiro IDE launcher (`kiro`), a different tool from `kiro-cli`; changing the provisional synthesized route; Amp, Goose, Aider and any CLI not listed until someone asks.
- **Allowed behavior changes:** new registered backends and `--integration` choices only; the existing three keep their behavior.
- **Allowed reorganization:** only the smallest relocation needed for this outcome; no unrelated restructuring.
- **Verification:** per backend, parser tests over fixtures captured from the real binary; the manifest round-trip golden; classification tests for every pattern whose copy was captured, with the rest marked provisional; `install-skill --integration <name>` accepts it; one bounded `run` step completes on a scratch plan; mutation checks on the parser and each classification pattern.
- **Stop / defer:** file adjacent work separately; stop and report if a CLI has no headless mode or no capturable event stream rather than writing a parser from documentation alone.
- **Dependencies:** #389 (promoted to IPPT-7), the hard-coded `install-skill --integration` list (`choices=("claude", "codex", "cursor")` in `plan_tool/cli/skill_cmd.py`). Do it first or as the first backend's step, so later backends need no edit there.
- **Origin:** 2026-11-06, an estimate of what supporting other common CLIs would take.

**#527 — Decide whether to delete the four public `demo/*` branches that still show the needs-updating notice**

- **Labels:** Route `direct`
  · Readiness `decision-needed` (the owner decides delete versus keep)
  · Tier `architect`
  · Principle `write-for-the-human`
- **What:** `demo/1-seed`, `demo/2-plan`, `demo/3-detail` and `demo/4-jira` exist on both Bitbucket and GitHub (kept by owner decision, 2026-10-21) and every one points at the shared "mark preserved demo checkpoints as needing update" commit (2026-10-21). The maintained walkthroughs (`docs/demos/planning-demo.md`, `docs/how-to/roadmap-demo.md`) describe the seed, plan, detail and Jira stages, and carry the demo, so the branches may no longer earn their upkeep.
- **Arc assignment:** `backlog-arc-public-release`.
- **Effort:** small; a decision, then at most a reviewed ref deletion on two hosts.
- **Risks / fallout:** a remote ref deletion is hard to undo and visible to every user; it needs private recovery bundles of both hosts' prior refs, as the sanitized-root replacement (2026-10-21) used.
- **Outcome:** a recorded owner decision on whether to delete the four `demo/*` branches. If deleted, the branches are gone from both hosts, read back from both. If kept, a separate entry holds the content refresh.
- **In scope:** asking the owner; if the answer is delete, a reviewed deletion of the four branch names on Bitbucket and GitHub after private recovery bundles of the old tips are made and verified, with separate authorization for the remote update, then read-back from both hosts.
- **Out of scope / Non-goals:** curating or refreshing checkpoint content (deliberately not taken before the delete decision, cut 2026-11-14: refreshing four refs on two hosts is a careful operational job, and the walkthrough docs already carry the demo); `main`, tags, repository visibility, and organization transfer (the release workflow in `docs/RELEASING.md` owns them); a fresh TTRPG roadmap run or browser interaction; code, CLI, or skill changes; pushing or deleting any ref without the separate authorization above.
- **Allowed behavior changes:** remote `demo/*` refs may be deleted.
- **Allowed reorganization:** none.
- **Verification:** the owner's decision is recorded here; if deleted, `git ls-remote` on both hosts shows none of the four branch names and the private recovery bundles still verify.
- **Stop / defer:** stop if a recovery bundle is missing or fails verification; if the owner keeps the branches, file the refresh as its own entry rather than expanding this one.
- **Dependencies:** none; independent of #514 and #515.
- **Approach:** direct; ref updates are a reviewed operational action, not a code change.
- **Origin:** 2026-10-21 public-release preparation; the refresh was deferred when the checkpoints were marked as needing update.

**#528 — Nothing reviews whether the stage-4 plan list in `04-roadmap.md` is a deliberate decomposition**

- **Labels:** Route `direct` (an investigation that reports findings)
  · Readiness `parked` (parked 2026-11-14: no confirmed defect, and no decision waits on the report)
  · Tier `architect`
  · Principle `converge-on-correct-plan`
- **What:** stage 4 maps accepted roadmap rows to plans, and every downstream artifact (draft seeds, `create`, detail) takes its boundaries from that list. Seed distillation has an explicit one-plan-or-many judgment grounded in shared implementation, but no review has compared the stage-4 guidance (`plan_tool/prompts/roadmap-plans.md`, which already requires bounded plan rows, rejects fixed plan counts, and forbids repository inspection) with it or looked at retained stage-4 outputs. An oversized or fragmented plan row is therefore noticed only after seeds or `create` expose it. No confirmed defect exists; this is an assessment.
- **Unpark when:** downstream seeds or `create` split a stage-4 plan row in practice.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Effort:** small to medium; reading, comparison, and a written report.
- **Risks / fallout:** the property is semantic, so the assessment can grow into a checker; the fence below is the guard. Prompt-presence tests in `tests/test_roadmap.py` (`TestPlansPromptTemplate`) pin guidance wording, not model decomposition quality.
- **Outcome:** one written report holds a comparison matrix (principle, current stage-4 provision, seed-side provision, justified altitude difference, remaining gap), the named retained stage-4 artifacts examined with exact paths and versions (unavailable evidence marked), and findings separated into demonstrated defects, hypotheses, and advisory questions; or it concludes that no material gap exists and closes without an implementation proposal.
- **In scope:** `plan_tool/prompts/roadmap-plans.md`, `plan_tool/prompts/distill-seed.md` § "Decide: one plan, or many?", `plan_tool/prompts/roadmap-seed.md`, how `plan_tool/roadmap.py` composes the stage-4 instructions, `TestPlansPromptTemplate`, and a small explicitly named set of retained stage-4 outputs with their brief and upstream versions.
- **Out of scope / Non-goals:** prompt, schema, or CLI changes in this item; repository grounding inside stage 4 (the seed-side file/function criterion is not copied into stage 4); new fields, automatic semantic gates, quality scores, fixed size or plan-count thresholds; changing seed cardinality or repartitioning accepted rows; new concurrency; live generation, rehearsal, or publication; a vocabulary matcher for a judged property. Materialization keeps surfacing an overly broad mapping through roadmap review and never repartitions an accepted row.
- **Allowed behavior changes:** none.
- **Allowed reorganization:** none.
- **Verification:** the report names its evidence and its limits; when downstream seeds or `create` split a row, it compares the saved evidence with the accepted mapping to tell an original mapping gap from new code knowledge, a source change, or a materializer omission.
- **Stop / defer:** if representative evidence is unavailable, report that limit before proposing new generation work. If existing rules already cover an observed issue, name the remedy as clearer review practice, a prompt-delivery defect, or an evidenced behavior failure; do not add another restatement because an output can be bad. A remedy that changes structure needs its own entry and a user decision.
- **Dependencies:** none.
- **Approach:** direct; the work is reading and reporting, with any remedy filed separately.
- **Origin:** 2026-10-23 review request after the roadmap seed-materialization and plan-row selection work, which changed neither stage-4 decomposition nor its review.

**#529 — Nothing checks that relative links in the live documentation resolve, so broken links accumulate**

- **Labels:** Route `direct`
  · Readiness `decision-needed` (a guard test with exception groups, or a one-off triage of the live links)
  · Tier `experienced`
  · Principle `write-for-the-human`
- **What:** no test scans `*.md` links. A scan on 2026-11-13 over tracked Markdown found 608 relative link targets that do not exist; 42 sit outside archived plans, plan-detail bundles, and saved reports (13 each in two `tests/fixtures/reformat/` files, five in each of the three `integrations/*/SKILL.md` routers, one in `lessons/general.md`). The routers link `DIRECTIVES.md` as a sibling because `plan-tool install-skill` installs both files into one directory, so a scan of the source tree flags links that are correct once installed.
- **Effort:** small; a guard needs three exception groups (archived and frozen plan files, the installed-layout routers, link-shaped fixture text).
- **Risks / fallout:** archived and audited plan files are frozen, because an edit makes their saved audit reports stale; a guard that scans them fails forever. A guard also adds a maintenance edge to every doc move.
- **Outcome:** a documented decision between a guard test and a one-off triage, and the chosen one in place with the live-document links resolving.
- **In scope:** a test over tracked `*.md` that skips the three exception groups above, or a repair of the 42 live targets, plus a documented reason for each retained exception.
- **Out of scope / Non-goals:** editing archived plans, plan-detail files, or saved reports for link hygiene; checking heading anchors or external URLs; a readability check (the documentation style guide deliberately has none).
- **Allowed behavior changes:** none to the CLI; one new test, or doc link edits.
- **Allowed reorganization:** none.
- **Verification:** the test fails when a live link target is removed and passes with the exception groups; or a rerun of the scan reports zero unexplained live targets.
- **Stop / defer:** file any doc defect that a link repair would require reworking as a separate entry.
- **Dependencies:** none.
- **Approach:** direct.
- **Origin:** 2026-11-13 triage of the live documentation after the temporary handoff files were retired.

**#530 — Fix the developer-documentation stumbles that the fresh-reader walkthrough in #515 finds**

- **Labels:** Route `direct`
  · Readiness `blocked-on #515`
  · Tier `experienced`
  · Principle `write-for-the-human`
- **What:** the scan-first standard (`docs/reference/documentation-style.md`) and the task-first layers (`docs/README.md`, `CONTRIBUTING.md` § "New contributor path") shipped. The section-by-section readability audit of the remaining live developer documents (`CONTRIBUTING.md` drive-or-review workflow, `docs/ARCHITECTURE.md` subsystem paragraphs, `docs/ITERATION.md` and `docs/GATES.md` matrices, the `docs/TRACKING.md` lifecycle) judges an unobservable property section by section, so it is not run as a batch. The four reader journeys (install and begin, run or review a plan safely, change `plan-tool` itself, find ownership, tracking, and escalation routes) are checked by a fresh reader instead: #515 verifies the first journey in a fresh repository, and #510 covers the first-task walkthrough.
- **Effort:** small to medium; one fix batch per place a reader stumbled.
- **Risks / fallout:** test-pinned wording in `tests/test_roadmap_format.py` and sibling documentation guards; link churn on moved anchors; a reshape that drops a fact.
- **Outcome:** each place the fresh-reader walkthrough recorded as blocking a reader (normal path, an exception, an owner, or a next action not findable) is fixed or filed, with links, terminology, and authority boundaries in agreement.
- **In scope:** the live developer-facing documents a recorded stumble names; the fix for that stumble only.
- **Out of scope / Non-goals:** the remaining batch-by-batch readability audit (deliberately not taken, cut 2026-11-14: it grades an unobservable property; only observed stumbles are fixed); a separate walkthrough (the fresh-reader walk belongs to #515); the first-task walkthrough and skill-first onboarding (#510); a link-resolution check (#529); generated run-grade plan-detail prose; archived plans, saved reports, and immutable evidence; a word-count gate, a long-prose checker, or any tooling that judges readability (the style guide deliberately has none); a pull-request checklist item; new pipeline rules or product behavior.
- **Allowed behavior changes:** none to the CLI or generated output; documentation structure and wording only.
- **Allowed reorganization:** only the smallest relocation a fix needs, naming the ownership boundary it fixes; no document moves for tidiness.
- **Verification:** every command, path, anchor, state condition, and ordering rule named in a fixed section survives (checked by enumerating them before and after); `uv run pytest tests/test_roadmap_format.py -q` and the documentation guards pass.
- **Stop / defer:** a defect or product gap that a fix exposes becomes its own entry; a fix that would change a contract stops and is filed instead. If #515's walkthrough records no stumble, close with "no action".
- **Dependencies:** #515 (supplies the recorded stumbles).
- **Approach:** direct, one reviewable batch per recorded stumble group, each with the session-directed review loop.
- **Origin:** the 2026-09 readability audit of the live developer documentation, whose first batches shipped; filed 2026-11-13, narrowed 2026-11-14.

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
