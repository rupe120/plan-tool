# Plan seed: reseed advisor — a directed forward-seed proposal as the actuator for the `FORK_STRUCTURAL` arm

> **BLOCKED — do not run as-is (2026-08-08, BACKLOG #251).** This seed's
> trigger and evidence source (`spinning` verdict, `FORK_STRUCTURAL`,
> `convergence_diagnosis`'s region-trending layer — `RegionTrend`,
> `recurring_regions`, `build_region_trends`) no longer exist: #251 retired
> them for being starved (0.13% of findings) with one lifetime firing, a
> false alarm. Every design section below (`## First principles`, `## Design`,
> `## Risks and mitigations`, `## Acceptance criteria`) assumes that verdict
> and must be re-premised on a non-fork trigger (operator judgment, a chat
> surface, or MIXED-STEP) before this seed is runnable. See BACKLOG #168.

This file is a `plan-tool create` input. Once re-premised, use it via:

```
plan-tool create reseed-advisor --from-existing plan-seeds/reseed-advisor.md --iterate
```

> **Source and lifecycle.** Implements BACKLOG **#168** and inherits its full
> scope contract. The final docs/status step must reconcile `BACKLOG.md`:
> mark #168 plan-authored while execution is pending and remove it only after
> the command ships; deferred follow-ups named there (taxonomy extensions,
> auto-chaining into `create`, the telemetry scoring loop) stay in the
> backlog, not in this plan.

---

## Overview

Every structural-remedy arm has an actuator except the most expensive one:
re-split has `--apply-split`, scope-out has `scope_out_step`, merge/re-ground
have their bridges — but `FORK_STRUCTURAL` ends at "hand-author `<seed.md>`
from the plan's current state." This plan adds `plan-tool reseed <name>`: a
command that turns a **spinning** verdict plus the plan's saved audit history
into a reviewed-quality forward-seed proposal — deterministic evidence
assembly, one directed Claude call that names each recurring region's *fold*
and proposes the minimal *seam set*, gated response validation, and draft
`create --from-existing` seed file(s). Recommend-only by default; writing
seeds sits behind the standard apply gate; it never runs `create` itself.

## First principles (these drive the prompt and the gates)

A spinning finding is by definition **invariant under the plan's available
moves** — three audit/apply rounds of prose edits did not move it, so it is a
property of the decomposition, not of the prose. Two derived definitions
anchor the design:

- **A fold is the stable invariant** every recurrence of a region shares.
  Naming it is the analysis; everything else is bookkeeping.
- **A seam is a line across which the two sides converge under different
  regimes.** The partition test is **local closability**: cut the plan so
  each partition's residual findings are closable by edits inside that
  partition. A finding closable only by touching two partitions marks either
  a bad cut or a fence conflict.

## Design

### Deterministic evidence assembly (no Claude)

Per *deterministically driven non-determinism*, everything mechanical happens
before tokens are spent:

- Load report history and region trends through `convergence_diagnosis`'s
  existing layers. Require the three-snapshot trajectory window and a
  spinning/`FORK_STRUCTURAL` verdict; on anything less, print the cheaper
  applicable remedy and exit 0 without a Claude call.
- Build a **finding↔anchor bipartite graph** from the persisted reports:
  recurring regions on one side; the steps, body sections, and fence clauses
  they cite on the other. Connected components are *candidate* partitions;
  findings bridging components are *candidate* fence conflicts. Pure graph
  work over data the sidecars already hold.
- Resolve provenance: the original seed via the archive's `.replaced` chain,
  the source backlog entry and its scope contract (seeds name their source),
  and the current plan + detail bundle.

### The directed Claude request

The assembled evidence plus a **forced classification taxonomy** — "find the
seams" is too open; the taxonomy is the direction. For each recurring region
the response must:

1. **Name the invariant** behind the recurrence.
2. **Classify the fold** as exactly one of:
   - **fence conflict** — the scope contract forbids machinery the acceptance
     criteria require;
   - **missing substrate** — the plan asserts a property no step purchases;
   - **self-inconsistent gate** — acceptance contradicts the plan's own risk
     mitigations;
   - **fused concerns** — one step mixes work that audits under different
     regimes.
3. **Propose the minimal seam set** passing the local-closability test.
4. **Emit one forward-seed per partition**, inheriting the source scope
   contract verbatim, carrying backlog reconciliation forward, and expressing
   every fence conflict as an explicit `DECISION:` block for the operator —
   never a silently widened fence.

### Response gates (loopable under `--iterate`)

Deterministic checks mirroring `create`'s re-parse discipline; a failing
reply re-prompts with the violation named:

- every recurring region maps to exactly one disposition — dissolve /
  defer-to-seed / surface-as-decision;
- the union of proposed seed scopes ⊆ the original contract plus explicitly
  flagged `DECISION:` amendments;
- each proposed seed names its backlog source;
- no non-advisory finding is unaccounted for.

### Persistence, gating, and layering

- The proposal lands as a saved sidecar report (alongside the plan's other
  saved reports) plus draft seed files in a proposals location; `--apply` +
  TTY confirm (`-y` as the deliberate bypass) moves the drafts into
  `plan-seeds/`. The next-steps output prints the
  `plan-tool create --from-existing` line; the command never invokes `create`
  and never archives or mutates the source plan.
- `convergence`'s `FORK_STRUCTURAL` output gains one next-steps line pointing
  at `plan-tool reseed <name>`.
- New cycle-free leaf `plan_tool/reseed.py` importing only
  `convergence_diagnosis`, `review_persistence`, `review`, and `locator`; a
  prompt file; thin CLI wiring. `invoker=` seam with a real-CLI default;
  tests neutralize it per TESTING.md and cover the assembly with fixture
  report histories (no Claude).
- One `record_decision` telemetry event per proposal (proposed / applied /
  declined), so `telemetry_analysis` can later score whether accepted
  proposals converged. Recording stays best-effort.
- Exit-code convention: 0 on any completed proposal or short-circuit;
  non-zero only on failure-to-complete.

## Suggested decomposition

- **Assembly leaf step:** history/trend loading, the trigger gate, the
  bipartite graph, provenance resolution — deterministic, snapshot-tested on
  fixture report histories.
- **Prompt + gates step:** the prompt file encoding the taxonomy and seam
  test, response parsing, the four deterministic gates, and the `--iterate`
  re-prompt loop, tested against conforming and violating stub replies.
- **CLI + persistence step:** `plan-tool reseed` wiring, sidecar proposal
  persistence, the `--apply` gate, the `convergence` next-steps line, and
  `docs/cli/` regeneration.
- **Telemetry + docs step:** the decision event, `RUNBOOK.md` /
  `CAPABILITIES.md` coverage, and `BACKLOG.md` #168 reconciliation.

## Out of scope

- Running `create`, archiving the source plan, or mutating it in any way.
- Changing `convergence_diagnosis` verdict logic or any completeness-audit
  surface.
- Auto-amending any scope fence — fence conflicts are surfaced as decisions,
  never applied.
- Speculative taxonomy extensions; the four folds ship as-is (see Risks).
- The telemetry *scoring* loop (analysis-side outcome resolution for reseed
  events beyond the recorded event itself).

## Risks and mitigations

- **Closed-world taxonomy:** a novel contradiction shape gets nearest-bucket
  classified. Acceptable: the proposal is operator-reviewed before any seed
  lands, and the report must quote the invariant so a misclassification is
  visible. Extensions are backlog follow-ups.
- **Proposal quality unmeasurable at first:** the recorded decision event is
  the hook; the scoring loop is deferred, not skipped.
- **Trigger misfire:** the command consumes the diagnostic's verdict as-is;
  fork-classification quality is #148's concern, and a stale window is
  #166's — neither is re-solved here.

## Acceptance criteria

- On a spinning/`FORK_STRUCTURAL` plan, `plan-tool reseed <name>` produces a
  saved proposal report and draft seed file(s) in which every recurring
  region carries a named invariant, exactly one fold classification, and one
  disposition; every fence conflict appears as a `DECISION:` block; every
  draft seed names its backlog source and inherits the contract.
- On a non-spinning plan it prints the cheaper applicable remedy, spends no
  Claude, and exits 0.
- The four response gates demonstrably reject violating replies and the
  iterate loop re-prompts with the violation named.
- `--apply` writes seeds into `plan-seeds/` only under confirm/`-y`; the
  default path writes only the proposal artifacts; `create` is never invoked.
- The assembly is fully covered by fixture-driven tests with no real backend
  spawn; the prompt/gate path is covered via stub invokers.
- A telemetry decision event is recorded per proposal outcome.
- `BACKLOG.md` #168 is reconciled by the final step.

## Deferred

- Taxonomy extensions beyond the four folds.
- Auto-chaining an accepted proposal into `create --from-existing`.
- Telemetry outcome scoring for reseed proposals (did accepted re-seeds
  converge?).

## References

- `BACKLOG.md` #168 — forward-seed proposal scope and required lifecycle
  reconciliation.
- `BACKLOG.md` #251 — retired region-trending machinery that keeps this seed
  blocked pending a replacement signal.
- `plan_tool/convergence.py` — convergence outcomes that distinguish the
  reseed route from cheaper remedies.
