> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Telemetry Decision Outcome Resolver
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a completed-run event reader to run_log.py
  files:
  - plan_tool/run_log.py
  - tests/test_run_log.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/telemetry-decision-outcome-resolver/01-completed-run-event-reader-run-log-py.md
  status: done
- id: 2
  title: Add the telemetry_analysis leaf with inline (self-recording) outcome verdicts
  creates:
  - plan_tool/telemetry_analysis.py
  - tests/test_telemetry_analysis.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/telemetry-decision-outcome-resolver/02-telemetry-analysis-leaf-inline-self.md
  status: done
- id: 3
  title: Resolve async outcomes by joining the run-log and sidecar transitions, reusing
    the convergence_diagnosis matcher
  files:
  - plan_tool/telemetry_analysis.py
  - tests/test_telemetry_analysis.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/telemetry-decision-outcome-resolver/03-resolve-async-outcomes-joining-run-log.md
  status: done
- id: 4
  title: Aggregate decisions by kind and decision across plans and emit advisory tuning
    recommendations
  files:
  - plan_tool/telemetry_analysis.py
  - tests/test_telemetry_analysis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/telemetry-decision-outcome-resolver/04-aggregate-decisions-kind-decision.md
  status: done
- id: 5
  title: Add the plan-tool telemetry command wiring the analysis leaf, with optional
    --json
  files:
  - plan_tool/cli/parser.py
  - plan_tool/cli/app.py
  - CAPABILITIES.md
  - plan_tool/telemetry_analysis.py
  creates:
  - plan_tool/cli/telemetry_cmd.py
  - tests/cli/test_telemetry_cmd.py
  - docs/cli/telemetry.md
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/telemetry-decision-outcome-resolver/05-plan-tool-telemetry-command-wiring.md
  status: done
- id: 6
  title: 'Document the telemetry surface and close BACKLOG #72 phase 3'
  files:
  - USE_CASES.md
  - CLAUDE.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/telemetry-decision-outcome-resolver/06-document-telemetry-surface-close.md
  status: done
---
# Telemetry Decision Outcome Resolver

## Overview

Adds the **consumer** slice of BACKLOG #72's decision/outcome telemetry: a read-only decision→outcome resolver (a cycle-free leaf) that ties each recorded *decision* to what later *happened* and derives a verdict, plus a `plan-tool telemetry` command (`cli/telemetry_cmd.py`) that aggregates decisions across plans and over time — grouped by `kind`/`decision` — and prints advisory **tuning recommendations**. Phases 1–2 shipped the `DecisionEvent` schema and the producers that populate its join keys; this is the first and only reader. The whole surface mirrors the `convergence` command's contract: **read-only, no Claude, always exit 0, advisory** — it prints recommendations and **never** auto-tunes a threshold, mutates a plan, or edits a config.

## Problem statement

Phases 1–2 shipped the schema and the producers, but **nothing reads the keys**. Real telemetry is now accumulating `decision_id` / `run_id` / `plan_fingerprint` / `code_fingerprint` / `anchor` on new events, and three high-leverage families (drift-gate, apply-verdict, escalate-split) fire — but the mission's payoff (*set thresholds from the distribution over scenarios/time, not by anecdote*) needs the correlate-and-recommend surface. The spike's smoke test (§7) — does `code-reveals-split` fire on step N, then a split follow, then the next sidecar show step N became two steps? — **cannot run until this reader exists.**

## Architecture

Two pieces, both read-only, no Claude, always exit 0, advisory (mirroring the `convergence` command exactly).

**A. A decision→outcome resolver (a cycle-free leaf).** Joins each decision to its later outcome and derives a verdict via a two-tier outcome model (spike §6):
- **Synchronous / same-call outcomes are already inline** — some decisions record their own result (`create-step-outcome.action` = split-applied/split-error; `apply-verdict.context.verdict`; `escalate-split.context.outcome`). The resolver reads these directly; they need only their `decision_id`.
- **Async / derived outcomes** — the hard case #72 names ("an outcome can be many runs later"). The resolver joins **decision → run-log** on `run_id` (`IterationEnd.outcome` / `RunEnd.outcome`+`rc`) and **decision → later sidecar state** on a `plan_fingerprint` transition **plus** the `convergence_diagnosis.py` finding matcher, and *derives* one of `acted-on` / `no-op` / `reverted` / `still-open`.

**B. A `plan-tool telemetry` analysis-and-recommend command** (`cli/telemetry_cmd.py`). Reads **all** plans' decisions (per-repo, gitignored, local), aggregates **across plans and over time** grouped by `kind`/`decision`, and flags tuning opportunities (e.g. "signal X fired on Y% of steps, Z% were acted on / led to a spin/overflow → consider adjusting threshold to …"). It is the thin wiring above the resolver leaf, modeled on `cli/convergence_cmd.py` (`cmd_*` + `register(subparsers)`).

**Resolved design decisions (from the spike):**
1. **Reuse `convergence_diagnosis.py`'s matcher — do not reinvent it.** That leaf already does cross-run outcome correlation over saved sidecars: the 3-tier join (`_normalized_focus`: step focus → `anchor` slug → fuzzy title at `TITLE_SIMILARITY_CUTOFF = 0.85`), `load_report_history`, and the `RunFinding`/`RunSnapshot` shapes. Phase 3 **extends** it to also consume (i) the telemetry decision stream (`telemetry.read_decisions`) and (ii) the run-log, and to emit derived outcome verdicts — it does not build a second matcher.
2. **The resolver is a cycle-free leaf, like `convergence_diagnosis`.** Its only first-party imports are the *read* APIs — `telemetry.read_decisions`, `review_persistence`/`convergence_diagnosis` (sidecar history), `run_log` (run read), `locator` — and **no `plan_tool.cli`**.
3. **Read-only, no-Claude, always exit 0, advisory — the `convergence` contract.** `cmd_convergence` is the template: spends no Claude, writes no run-log entry, mutates nothing on the default path, returns 0 for every verdict (`--fail-on-findings` the only opt-in rc flip, and even that optional here). **Never auto-tune a threshold.**
4. **No second heavyweight store (spike §5).** Outcomes ride the *existing* sidecars and run-log; #72 **reads and correlates**, it does not duplicate. Derived verdicts are computed on read, not persisted (or persisted only as a cheap cache if a step proves it necessary — default to compute-on-read).
5. **Aggregate across plans, tolerant of the ownerless tail.** The log mixes plan-scoped decisions with ownerless `prompt-budget` checks (81% of the spike's 347 events) and `plan_slug=""` rows; aggregation buckets by `kind`/`decision` and skips un-joinable rows gracefully. Weakly-anchored events (greenfield create, `run_id=""` authoring decisions) join only where their keys allow and are otherwise counted but not correlated.

**Seams to reuse / verify at HEAD during detail:** `plan_tool/telemetry.py` (`read_decisions(repo_root) -> list[DecisionEvent]`, the 11-field `DecisionEvent`); `plan_tool/convergence_diagnosis.py` (`load_report_history`, `_normalized_focus` / `TITLE_SIMILARITY_CUTOFF`, `RunFinding`/`RunSnapshot`); `plan_tool/run_log.py` (`runs_root(repo_root)`, per-`run_id` JSONL — `IterationEnd.outcome`, `RunEnd.outcome`/`rc` — where a completed-run reader may need adding beside today's `read_in_flight`); `plan_tool/cli/convergence_cmd.py` (`cmd_convergence` + `register`); `plan_tool/review_persistence.py` (`compute_plan_fingerprint` and the saved sidecar shape).

## References

- [difflib — Helpers for computing deltas (Python 3.13)](https://docs.python.org/3/library/difflib.html) — Documents SequenceMatcher.ratio() and get_close_matches, the basis for the resolver's fuzzy title matcher at TITLE_SIMILARITY_CUTOFF = 0.85.
- [argparse — Parser for command-line options (Python 3.13)](https://docs.python.org/3/library/argparse.html) — Documents add_subparsers and sub-command wiring, needed to register the new `plan-tool telemetry` command mirroring cli/convergence_cmd.py's register(subparsers).
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — Reference for @dataclass and frozen=True, used to model DecisionEvent and any frozen resolver-output/verdict shapes.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — Documents json.loads for parsing the per-line records when streaming the gitignored telemetry decisions.jsonl and run-log JSONL.
- [JSON Lines format specification](https://jsonlines.org/) — Primary spec for the newline-delimited JSON (.jsonl) format that telemetry.read_decisions and the run-log reader stream and iterate over.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Auto-tuning any threshold** — the surface *recommends*; a human decides and edits. Never mutate a threshold, a plan, or a config from telemetry.
- **A second telemetry store** — outcomes ride the existing sidecars/run-log; no duplication (spike §5).
- **Backfilling / migrating historical events** — the resolver reads whatever keys events already carry; un-joinable legacy rows are counted, not repaired.
- **Changing `telemetry.py`'s leaf status** — it stays a stdlib-only recorder; the resolver is a *separate* leaf that reads its output.
- **A live/streaming dashboard** — this is an offline, on-demand read (like `convergence`), not a daemon.

## Risks

- **Outcome-linkage is genuinely hard (the async gap).** A decision's outcome can be many runs later; the join can mis-attribute. Mitigation: reuse the *tested* `convergence_diagnosis` matcher, keep verdicts advisory, and prove one real end-to-end link (the §7 smoke test) before trusting the aggregate.
- **Recommendation over-confidence.** Small-n distributions read as signal. Mitigation: surface counts + n alongside every recommendation; never present a tuning flag as a mandate; keep it advisory.
- **Leaf-cycle regression.** The resolver must not import `plan_tool.cli`, and the command must not pull business logic down into a leaf. Keep the `convergence_diagnosis` layering (leaf reads; cli wires).
- **Ownerless-tail skew.** 81% of real events are ownerless `prompt-budget` checks; naive aggregation drowns the signal. Mitigation: bucket by `kind`/`decision` and report per-family, not a global blend.
- **Reading a large local log.** The gitignored log grows unbounded; a full read could be slow. Mitigation: stream/iterate `read_decisions`; cap or window by time if a step shows it necessary (the run-log's cap/rotate precedent).

## Testing

Follow the project's unit-first convention (mirror `plan_tool/X.py` → `tests/test_X.py`; `@pytest.mark.integration` only for cross-module end-to-end wiring):
- The spike §7 smoke test end-to-end on a seeded scenario: a `code-reveals-split` fire at fingerprint P → a split → the next sidecar at P′ where step N became two steps → the resolver emits `acted-on`. This drives the resolver across telemetry + sidecar + run-log, so it belongs in the integration tier.
- Resolver join correctness per outcome verdict (`acted-on` / `no-op` / `reverted` / `still-open`), covering both the inline self-recording families and the async `run_id`→run-log + `plan_fingerprint`-transition path.
- Aggregation over a mixed log (plan-scoped + ownerless `prompt-budget` / `plan_slug=""` / `run_id=""` rows): counted, not crashed on; correlated only where keys allow.
- The `plan-tool telemetry` command contract: exit 0 for every verdict, no Claude, no run-log entry, no mutation.
- `DATA_CONTRACT.md` drift guard (`tests/test_data_contract.py`) green for any new derived/persisted resolver-output shape (and any cache sidecar).

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- A resolver joins a recorded decision to its outcome — inline result for self-recording families, and `run_id`→run-log + `plan_fingerprint`-transition + the reused `convergence_diagnosis` matcher for async — and derives one of `acted-on` / `no-op` / `reverted` / `still-open`; it imports no `plan_tool.cli` and reuses the existing matcher (no second matcher).
- `plan-tool telemetry` aggregates across plans and over time by `kind`/`decision` and prints advisory tuning recommendations with counts/n; it spends **no Claude**, writes **no run-log entry**, mutates nothing, and **exits 0** for every verdict (the `convergence` contract).
- The spike §7 smoke test passes end-to-end on a seeded scenario: a `code-reveals-split` fire at fingerprint P → a split → the next sidecar at P′ where step N became two steps → the resolver emits `acted-on`.
- Aggregation is tolerant of the ownerless/`plan_slug=""`/`run_id=""` tail (counted, not crashed on; correlated only where keys allow).
- `DATA_CONTRACT.md` documents any new derived/persisted shape with the drift guard green; **CAPABILITIES.md** and **USE_CASES.md** register the new surface.
- **BACKLOG #72 is updated** in the final step: phase 3 marked shipped, the entry closed or reduced to residual follow-ups, reconciled against the phase-2 Known-limitations list; if the companion producer-side hardening is split to its own plan, that split is named in the backlog. An optional `--json` machine-readable form is available for CI.

## Deferred

- **Companion producer-side hardening (separable — may split to its own plan).** BACKLOG #72's phase-3 bullet also lists producer-side hardening deferred from phase 2, independent of the resolver. It can ship as early steps here **or** as a separate small plan — the choice must be flagged at `create`, not silently dropped, and if split out it must be named in the BACKLOG #72 update. The items: **Backend-invocation-failure applies** get their own `apply-verdict` verdict token (today they emit no event; the crash is only in the run-log); **Parallel `completeness-apply --jobs N` telemetry** routed to the canonical `repo_root` with its keys threaded (today worker events land in a discarded worktree or reach the canonical log unkeyed); **`_MAX_LINE_BYTES` mitigation** on the `code_fingerprint`-carrying sites (drift-gate, code-reveals-split, create) — a dropped-event counter or a compact code-state digest replacing the full path→hash map; **Create-outcome per-step map dedup** — carry `code_fingerprint` once at assessment level, join by `plan_slug`+`ts`, not one copy per step; and **regression tests** for the four apply-loop threading sites and the Part-A/escalate best-effort wrap-sites.
- **Persisting derived verdicts as a cache sidecar** — default is compute-on-read; a cache is added only if a step proves it necessary (spike §4).
- **Time-windowing / capping the log read** — added only if a step shows a full `read_decisions` is too slow, following the run-log's cap/rotate precedent.
