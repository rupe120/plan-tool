> **Replaced**: this file has been superseded by `docs/implementation-plans/2-telemetry-decision-outcome-resolver.md`.
> Preserved here for history; do not edit.

# Plan seed: decision→outcome resolver + `plan-tool telemetry` analysis surface (BACKLOG #72, phase 3)

The **consumer** slice of #72 (decision/outcome telemetry) — the payoff phases 1–2
set up. Phase 1 gave `DecisionEvent` a *place* to carry the join keys; phase 2
made the producers *populate* them (fingerprints on six recorders + three new
decision families). Neither shipped a reader. Phase 3 is the **first and only
consumer**: a read-only resolver that ties a recorded *decision* to what later
*happened*, and a `plan-tool telemetry` command that aggregates across plans and
over time to surface **tuning recommendations** — advisory only, never
auto-tuning a threshold.

> **Source.** Distilled from **BACKLOG #72** ("Decision/outcome telemetry →
> understand heuristics across scenarios over time, recommend tuning"), the
> "Remaining (phase 3)" scope, and the schema spike
> **`.tmp/72-telemetry-linkage.spike.md`** §6–§8 (the outcome model + resolver
> design). The resulting plan **must update BACKLOG #72** when it ships (final
> docs/status step + acceptance criterion): mark phase 3 delivered, and either
> close #72 or leave only any residual as a small follow-up. This backlog
> reconciliation is a plan requirement, not an operator afterthought.

## Why phase 3 now

Phases 1–2 shipped the schema and the producers, but **nothing reads the keys**.
Real telemetry is now accumulating `decision_id` / `run_id` / `plan_fingerprint` /
`code_fingerprint` / `anchor` on new events, and three high-leverage families
(drift-gate, apply-verdict, escalate-split) fire — but the mission's payoff
(*set thresholds from the distribution over scenarios/time, not by anecdote*)
needs the correlate-and-recommend surface. The spike's smoke test (§7) — does
`code-reveals-split` fire on step N, then a split follow, then the next sidecar
show step N became two steps? — **cannot run until this reader exists.**

## What phase 3 delivers

Two pieces, both **read-only, no Claude, always exit 0, advisory** (mirroring the
`convergence` command exactly):

**A. A decision→outcome resolver (a cycle-free leaf).** Joins each decision to its
later outcome and derives a verdict. Two-tier outcome model (spike §6):
- **Synchronous / same-call outcomes are already inline** — some decisions record
  their own result (`create-step-outcome.action` = split-applied/split-error;
  `apply-verdict.context.verdict`; `escalate-split.context.outcome`). The resolver
  reads these directly; they need only their `decision_id`.
- **Async / derived outcomes** — the hard case #72 names ("an outcome can be many
  runs later"). The resolver joins **decision → run-log** on `run_id`
  (`IterationEnd.outcome` / `RunEnd.outcome`+`rc`) and **decision → later sidecar
  state** on a `plan_fingerprint` transition **plus** the
  `convergence_diagnosis.py` finding matcher, and *derives* one of
  `acted-on` / `no-op` / `reverted` / `still-open`.

**B. A `plan-tool telemetry` analysis-and-recommend command.** Reads **all** plans'
decisions (the log is per-repo, gitignored, local), aggregates **across plans and
over time** grouped by `kind`/`decision`, and flags **tuning opportunities** —
e.g. "signal X fired on Y% of steps, Z% were acted on / led to a spin/overflow →
consider adjusting threshold to …". Always advisory: it prints recommendations, it
**never** mutates a threshold or a plan.

## Resolved design decisions (ground the build on these — from the spike)

1. **Reuse `convergence_diagnosis.py`'s matcher — do not reinvent it.** That leaf
   already does cross-run outcome correlation over saved sidecars: the 3-tier join
   (`_normalized_focus`: **step focus → `anchor` slug → fuzzy title** at
   `TITLE_SIMILARITY_CUTOFF = 0.85`), `load_report_history`, and the
   `RunFinding`/`RunSnapshot` shapes. Phase 3 **extends** it to also consume (i) the
   telemetry decision stream (`telemetry.read_decisions`) and (ii) the run-log, and
   to **emit derived outcome verdicts** — it does not build a second matcher.
2. **The resolver is a cycle-free leaf, like `convergence_diagnosis`.** Its only
   first-party imports are the *read* APIs — `telemetry.read_decisions`,
   `review_persistence`/`convergence_diagnosis` (sidecar history), `run_log` (run
   read), `locator` — and **no `plan_tool.cli`**. The `plan-tool telemetry` command
   (`cli/telemetry_cmd.py`) is the thin wiring above it, modeled on
   `cli/convergence_cmd.py` (`cmd_*` + `register(subparsers)`).
3. **Read-only, no-Claude, always exit 0, advisory — the `convergence` contract.**
   `cmd_convergence` is the template: it spends no Claude, writes no run-log entry,
   mutates nothing on the default path, and returns 0 for every verdict (CI parses
   the lines; `--fail-on-findings` is the only opt-in rc flip, and even that is
   optional here). **Never auto-tune a threshold** — same never-mutate-unattended
   discipline as structural remedies. Recommendations are printed, decisions stay
   with the operator.
4. **No second heavyweight store (spike §5).** Outcomes ride the *existing*
   sidecars and run-log; #72 **reads and correlates**, it does not duplicate. The
   resolver's derived verdicts are computed on read, not persisted (or persisted
   only as a cheap cache if a step proves it necessary — default to compute-on-read).
5. **Aggregate across plans, tolerant of the ownerless tail.** The log mixes
   plan-scoped decisions with ownerless `prompt-budget` checks (81% of the spike's
   347 events) and `plan_slug=""` rows; aggregation must bucket by `kind`/`decision`
   and skip un-joinable rows gracefully, not choke on them. Weakly-anchored events
   (greenfield create, `run_id=""` authoring decisions) join only where their keys
   allow and are otherwise counted but not correlated.

## Seams to reuse / verify at HEAD during detail

- `plan_tool/telemetry.py` — `read_decisions(repo_root) -> list[DecisionEvent]`
  and the 11-field `DecisionEvent` (the 5 join keys). The resolver's input.
- `plan_tool/convergence_diagnosis.py` — `load_report_history`, `_normalized_focus`
  / `TITLE_SIMILARITY_CUTOFF`, `RunFinding`/`RunSnapshot`. The matcher to extend
  (it reads sidecars only today — phase 3 adds the telemetry + run-log inputs).
- `plan_tool/run_log.py` — `runs_root(repo_root)`, the per-`run_id` JSONL events
  (`IterationEnd.outcome`, `RunEnd.outcome`/`rc`); confirm/extend a read API for
  completed runs (today `read_in_flight` reads the live one — a completed-run
  reader may need adding).
- `plan_tool/cli/convergence_cmd.py` — `cmd_convergence` + `register` — the exact
  no-Claude / exit-0 / advisory command shape `plan-tool telemetry` copies.
- `plan_tool/review_persistence.py` — `compute_plan_fingerprint` and the saved
  sidecar shape the fingerprint-transition join keys on.
- `DATA_CONTRACT.md` + `tests/test_data_contract.py` (drift guard) — document any
  new derived/persisted shape (a resolver-output dataclass, or a cache sidecar if a
  step adds one).

## Scope of work (indicative — let `create` decompose)

1. **Resolver leaf** — read decisions + run-log + sidecar history; join a decision
   to its outcome (inline result → same event; async → `run_id` to run-log,
   `plan_fingerprint` transition + the reused matcher to the next sidecar); derive
   `acted-on` / `no-op` / `reverted` / `still-open`. Cycle-free, no `cli` import.
2. **Cross-plan / over-time aggregation** — group resolved decisions by
   `kind`/`decision`; compute per-signal distributions (fire rate, acted-on rate,
   spin/overflow/no-op correlation) tolerant of ownerless / un-joinable rows.
3. **Tuning-recommendation rendering** — turn the distributions into advisory
   flags ("signal X fires on Y%, Z% acted on → consider threshold …"); print-only.
4. **`plan-tool telemetry` command** (`cli/telemetry_cmd.py`) — thin wiring over
   1–3, modeled on `convergence_cmd`: `register`, resolve scope (a plan or all),
   no Claude, no run-log entry, exit 0. A `--json` machine-readable form is
   optional but useful for CI.
5. **DATA_CONTRACT.md + drift guard** — document the resolver-output shape (and any
   cache sidecar). Update **CAPABILITIES.md** (new surface → its MISSION principle)
   and **USE_CASES.md** (when to reach for it).
6. **Docs/status step** — update **BACKLOG #72**: mark phase 3 shipped; close the
   entry or leave only residual follow-ups. Reconcile against the phase-2 plan's
   Known-limitations list (below).
7. **Tests** — the spike §7 smoke test end-to-end (a `code-reveals-split` fire →
   split → next sidecar → `acted-on`); resolver join correctness per outcome
   verdict; aggregation over a mixed log (plan-scoped + ownerless); the exit-0 /
   no-Claude / no-mutation command contract; DATA_CONTRACT drift green.

## Companion producer-side hardening (separable — `create` may split to its own plan)

BACKLOG #72's phase-3 bullet also lists the **producer-side** hardening deferred
from phase 2. These are independent of the resolver and can ship as early steps
here **or** as a separate small plan — flag the choice at `create`, don't silently
drop them:
- **Backend-invocation-failure applies** get their own `apply-verdict` verdict
  token (today they emit no event; the crash is only in the run-log). Completes the
  apply-outcome distribution the resolver reads.
- **Parallel `completeness-apply --jobs N` telemetry** routed to the canonical
  `repo_root` + its keys threaded (today worker events land in a discarded worktree
  or reach the canonical log unkeyed).
- **`_MAX_LINE_BYTES` mitigation** on the `code_fingerprint`-carrying sites
  (drift-gate, code-reveals-split, create): a dropped-event counter so loss is
  visible, or a compact code-state **digest** in place of the full path→hash map.
- **Create-outcome per-step map dedup** — carry `code_fingerprint` once at
  assessment level, join by `plan_slug`+`ts`, not one copy per step.
- **Regression tests** for the four apply-loop threading sites and the
  Part-A/escalate best-effort wrap-sites (kwargs forwarded / a raising compute
  never perturbs the host command).

## Non-goals / out of scope

- **Auto-tuning any threshold** — the surface *recommends*; a human decides and
  edits. Never mutate a threshold, a plan, or a config from telemetry.
- **A second telemetry store** — outcomes ride the existing sidecars/run-log; no
  duplication (spike §5).
- **Backfilling / migrating historical events** — the resolver reads whatever keys
  events already carry; un-joinable legacy rows are counted, not repaired.
- **Changing `telemetry.py`'s leaf status** — it stays a stdlib-only recorder; the
  resolver is a *separate* leaf that reads its output.
- **A live/streaming dashboard** — this is an offline, on-demand read (like
  `convergence`), not a daemon.

## Risks

- **Outcome-linkage is genuinely hard (the async gap).** A decision's outcome can
  be many runs later; the join can mis-attribute. Mitigation: reuse the *tested*
  `convergence_diagnosis` matcher, keep verdicts advisory, and prove one real
  end-to-end link (the §7 smoke test) before trusting the aggregate.
- **Recommendation over-confidence.** Small-n distributions read as signal.
  Mitigation: surface counts + n alongside every recommendation; never present a
  tuning flag as a mandate; keep it advisory.
- **Leaf-cycle regression.** The resolver must not import `plan_tool.cli`, and the
  command must not pull business logic down into a leaf. Keep the
  `convergence_diagnosis` layering (leaf reads; cli wires).
- **Ownerless-tail skew.** 81% of real events are ownerless `prompt-budget` checks;
  naive aggregation drowns the signal. Mitigation: bucket by `kind`/`decision` and
  report per-family, not a global blend.
- **Reading a large local log.** The gitignored log grows unbounded; a full read
  could be slow. Mitigation: stream/iterate `read_decisions`; cap or window by time
  if a step shows it necessary (the run-log's cap/rotate precedent).

## Acceptance criteria (plan-level)

- A resolver joins a recorded decision to its outcome — inline result for
  self-recording families, and `run_id`→run-log + `plan_fingerprint`-transition +
  the reused `convergence_diagnosis` matcher for async — and derives one of
  `acted-on` / `no-op` / `reverted` / `still-open`; it imports no `plan_tool.cli`
  and reuses the existing matcher (no second matcher).
- `plan-tool telemetry` aggregates across plans and over time by `kind`/`decision`
  and prints advisory tuning recommendations with counts/n; it spends **no Claude**,
  writes **no run-log entry**, mutates nothing, and **exits 0** for every verdict
  (the `convergence` contract).
- The spike §7 smoke test passes end-to-end on a seeded scenario: a
  `code-reveals-split` fire at fingerprint P → a split → the next sidecar at P′ where
  step N became two steps → the resolver emits `acted-on`.
- Aggregation is tolerant of the ownerless/`plan_slug=""`/`run_id=""` tail (counted,
  not crashed on; correlated only where keys allow).
- `DATA_CONTRACT.md` documents any new derived/persisted shape with the drift guard
  green; **CAPABILITIES.md** and **USE_CASES.md** register the new surface.
- **BACKLOG #72 is updated** in the final step: phase 3 marked shipped, the entry
  closed or reduced to residual follow-ups, reconciled against the phase-2
  Known-limitations list; if the companion producer-side hardening is split to its
  own plan, that split is named in the backlog.
