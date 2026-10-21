> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# HANDOFF — telemetry-decision-outcome-resolver (BACKLOG #72, phase 3)

Resume doc for the `telemetry-decision-outcome-resolver` plan. Written after the
detail-authoring pass for steps 1–5 landed; picks up at step 6.

Plan file: `docs/implementation-plans/2-telemetry-decision-outcome-resolver.md`
Seed (archived): `plan-seeds/archive/telemetry-resolver-surface.replaced.md`
Source backlog: **BACKLOG #72** (`BACKLOG.md` line ~863, "Remaining (phase 3)").

---

## 1. State at handoff

| Step | Title | change_type | detail authored? | committed |
|------|-------|-------------|------------------|-----------|
| 1 | Completed-run event reader in `run_log.py` | feature | ✅ | `3f3eec1` |
| 2 | `telemetry_analysis` leaf — inline (self-recording) verdicts | feature | ✅ | `c27b6ea` |
| 3 | Async outcomes — join run-log + sidecar transitions, reuse `convergence_diagnosis` matcher | feature | ✅ | `931ee52` |
| 4 | Aggregate by `kind`/`decision` across plans + advisory tuning recs | feature | ✅ | `a312ad0` |
| 5 | `plan-tool telemetry` command wiring (`cli/telemetry_cmd.py`, `--json`) | feature | ✅ | `09d1713` |
| 6 | **Docs + close BACKLOG #72 phase 3** | non-code | ❌ **TODO** | — |

`progress=0/6` in `plan-tool status` is expected — that counts *execution* (`run`)
progress, not detail-authoring. No step has been **run/built** yet; only detail
files exist.

Working tree is clean. Nothing is in flight.

### Detail-authoring already done — key contract decisions captured in the files

Read the per-step detail `.md` files (`01-…` through `05-…`) for the authored
contracts. The load-bearing decisions carried from the seed:

- **Resolver is a cycle-free leaf** (`plan_tool/telemetry_analysis.py`, new).
  First-party imports allowed: `telemetry.read_decisions`, `convergence_diagnosis`
  / `review_persistence` (sidecar history), `run_log` (run read), `locator`.
  **No `plan_tool.cli` import** — that's the leaf-cycle invariant (mirrors
  `convergence_diagnosis`).
- **Reuse the existing matcher — do not build a second one.** Step 3 extends
  `convergence_diagnosis`'s `_normalized_focus` 3-tier join (step focus → `anchor`
  slug → fuzzy title at `TITLE_SIMILARITY_CUTOFF = 0.85`), `load_report_history`,
  `RunFinding`/`RunSnapshot`.
- **Two-tier outcome model.** *Inline / same-call* outcomes are read straight off
  the decision event (`create-step-outcome.action`, `apply-verdict.context.verdict`,
  `escalate-split.context.outcome`) — step 2. *Async / derived* outcomes join
  decision→run-log on `run_id` and decision→later-sidecar on a `plan_fingerprint`
  transition + the reused matcher, deriving one of
  `acted-on` / `no-op` / `reverted` / `still-open` — step 3.
- **Command contract = the `convergence` contract exactly:** read-only, no Claude,
  writes no run-log entry, mutates nothing, **exits 0 for every verdict**
  (`--fail-on-findings` optional). `cli/telemetry_cmd.py` = `cmd_*` + `register()`,
  modeled on `cli/convergence_cmd.py`. `--json` is the CI-friendly machine form.
- **Never auto-tune.** The surface *prints* tuning recommendations with counts + n;
  a human decides. No threshold/plan/config is ever mutated from telemetry.
- **Ownerless-tail tolerance.** ~81% of real events are ownerless `prompt-budget`
  rows; `plan_slug=""` / `run_id=""` rows exist. Aggregation buckets by
  `kind`/`decision`, counts un-joinable rows, correlates only where keys allow —
  never crashes on them.

---

## 2. Workflow constraint (why this was authored step-by-step)

**This environment kills long-running background processes at ~5–6 min.** A batch
`plan-tool detail … --iterate` (all steps) and even a *single* high-complexity
step's convergence loop both exceed that; a hard kill mid-loop commits nothing.

**The working pattern that succeeds** — one step at a time, with a graceful
self-checkpoint under the kill window:

```bash
plan-tool detail telemetry-decision-outcome-resolver --step N --iterate --commit --time-budget 240 -y
```

- `--time-budget 240` makes `detail` checkpoint and exit 0 gracefully (~4 min,
  under the ~5–6 min kill) with a resume hint if it hasn't converged; re-run to
  resume the same step's loop until it converges and commits.
- `--commit` is **per-step** — each converged step lands its own commit, so a kill
  never loses a finished step.
- **Gotcha:** `detail --commit` commits the detail `.md` but sometimes leaves the
  trailing `reports/*.json|md` completeness sidecars **untracked**. Those *are*
  tracked artifacts in this repo (128 exist for other plans). If the tree isn't
  clean before the next `--commit` step, sweep them:
  `git add docs/implementation-plans/plan-details/telemetry-decision-outcome-resolver/reports/ && git commit`.
- **On a kill mid-step:** `git checkout -- <plan .md>` and `rm` the partial
  `NN-*.md` for the in-flight step, then re-run that step. (Committed steps are
  safe.)

Apply this same per-step + `--time-budget` discipline to `plan-tool run` below.

---

## 3. Detailed conceptual flow of the remaining tasks

Three phases remain: **(A)** finish authoring (step 6 detail), **(B)** execute the
plan, **(C)** the post-run reconciliation and code-review tail. Per CLAUDE.md, B
and C are mandatory — green steps are not the finish line.

### Phase A — author step 6 detail (docs / non-code)

Step 6 files: `USE_CASES.md`, `CLAUDE.md`, `BACKLOG.md`. It is the plan's
docs-and-reconciliation step. Author its detail file:

```bash
plan-tool detail telemetry-decision-outcome-resolver --step 6 --iterate --commit --time-budget 240 -y
```

Step 6 is low-complexity non-code and should converge in one window. Its detail
must lay out, and its eventual execution must deliver:

1. **`CAPABILITIES.md`** — register the new `plan-tool telemetry` surface mapped to
   its MISSION principle (deterministic verifiability / grounding — the data-driven
   heuristic-tuning foundation). Note: `CAPABILITIES.md` was placed in **step 5**'s
   file list, so confirm which step actually writes it and avoid a double-write;
   the catalog is drift-guarded by `plan-tool validate`
   (`plan_tool/capability_catalog.py`), so it must be accurate or CI fails.
2. **`USE_CASES.md`** — situation-first entry: *when* to reach for `plan-tool
   telemetry` (you want to tune a threshold from the distribution over
   scenarios/time rather than by single-session anecdote).
3. **`CLAUDE.md`** — a short architecture note for the resolver leaf +
   command, in the terse house style, slotted near the `convergence` /
   `telemetry.py` descriptions.
4. **`BACKLOG.md` #72 reconciliation** — *this is a hard plan requirement, not
   bookkeeping.* The update must:
   - Mark **phase 3 shipped** (resolver + `plan-tool telemetry` + derived verdicts).
   - **Close #72, or reduce it to a named residual.** The **companion
     producer-side hardening** items (see §4) were **deferred** by this plan (they
     live in the plan's `## Deferred` section, not as steps). The #72 update must
     **name that split explicitly** — either as a small follow-up backlog entry or
     as retained residual bullets on #72 — so the deferral is on record, not
     silently dropped.
   - Reconcile against the **phase-2 Known-limitations** list referenced in #72.

### Phase B — execute the plan (`plan-tool run`)

Once all six detail files exist, build the code. Conceptually the steps build the
consumer bottom-up, matching the dependency DAG (`1,2 → 3 → 4 → 5 → 6`):

1. **`run_log.py` completed-run reader** (step 1) — today `read_in_flight` reads
   the *live* run; step 1 adds a reader for **completed** runs' per-`run_id` JSONL
   (`IterationEnd.outcome`, `RunEnd.outcome`/`rc`). This is the async-join input the
   resolver needs. Foundation; no deps.
2. **`telemetry_analysis` leaf — inline verdicts** (step 2) — new leaf file. Reads
   `telemetry.read_decisions`, resolves the *self-recording* families whose outcome
   is already on the event. Establishes the leaf, its dataclasses (a frozen
   resolver-output/verdict shape — **must be documented in `DATA_CONTRACT.md`** and
   pass `tests/test_data_contract.py`), and the no-`cli` import boundary.
3. **Async resolver** (step 3, deps 1+2, **high complexity**) — the hard slice.
   Joins decision→run-log on `run_id` and decision→next-sidecar on a
   `plan_fingerprint` transition, driving the derivation through the *reused*
   `convergence_diagnosis` matcher, emitting
   `acted-on`/`no-op`/`reverted`/`still-open`. The **spike §7 smoke test** lives
   here (integration tier): `code-reveals-split` fires at fingerprint P → a split →
   the next sidecar at P′ shows step N became two steps → resolver emits
   `acted-on`.
4. **Aggregation** (step 4, dep 3) — group resolved decisions by `kind`/`decision`
   across all plans and over time; compute per-signal distributions (fire rate,
   acted-on rate, spin/overflow/no-op correlation); tolerate the ownerless tail.
   Turn distributions into **advisory tuning flags** ("signal X fires on Y%, Z%
   acted on → consider threshold …") with counts + n attached (over-confidence
   guard).
5. **`plan-tool telemetry` command** (step 5, dep 4) — thin `cli/telemetry_cmd.py`
   over the leaf: `register(subparsers)`, resolve scope (one plan or all), print
   recommendations, optional `--json`. No Claude, no run-log entry, exit 0.
6. **Docs + backlog** (step 6, dep 5) — Phase A's substance, delivered.

Run it per-step, honoring the same kill-window discipline and the `--commit`
mandate for multi-step runs (each green step commits; keeps the tree clean so the
**test-authoring gate** measures each step's coverage delta correctly):

```bash
# one step at a time; re-run to resume if a step's build gets killed mid-window
plan-tool run telemetry-decision-outcome-resolver --commit --time-budget 240
# (add --iterate only when reconciling; a plain forward run does not take it)
```

Watch the **test-authoring gate**: `enforce_step_tests: true` is set on this plan,
so each feature step must author a real test in its own commit or the gate blocks
advancement. `--commit` between steps is what keeps that gate honest.

### Phase C — post-run reconciliation + code review (mandatory; green ≠ done)

After the last step is green **and committed**, run two loops to convergence
(CLAUDE.md "After a `plan-tool run` finishes a plan…"):

1. **Plan-canonical code reconciliation** — the plan is canonical; land the edits
   the code still needs to *fully cover* it. No built-in `--iterate`; loop by hand:
   ```bash
   plan-tool reconcile-code telemetry-decision-outcome-resolver
   plan-tool reconcile-code telemetry-decision-outcome-resolver --dry-run   # until: no drift
   ```
2. **Code review** — a `/code-review` session pass (not a plan-tool surface); fix
   findings, re-review each round until it converges (no new findings).

`completeness-audit` / `completeness-apply` belong to plan authoring and are not
part of this post-implementation tail.

**Escape hatch (both loops + any step build):** if a finding/region keeps
re-surfacing or a fix needs structural rework you can't land here, **stop and file
a `BACKLOG.md` / `BUG_BACKLOG.md` entry** naming the issue rather than looping
indefinitely.

---

## 4. Companion producer-side hardening — the deferred split (decide in step 6)

BACKLOG #72's phase-3 bullet also lists **producer-side hardening** deferred from
phase 2. This plan **did not fold these in as steps** — they sit in the plan's
`## Deferred` section. Step 6's BACKLOG update must name this split. The items:

- **Backend-invocation-failure applies** → their own `apply-verdict` verdict token
  (today they emit no event; the crash is only in the run-log).
- **Parallel `completeness-apply --jobs N` telemetry** routed to the canonical
  `repo_root` with its keys threaded (today worker events land in a discarded
  worktree or reach the canonical log unkeyed).
- **`_MAX_LINE_BYTES` mitigation** on `code_fingerprint`-carrying sites (drift-gate,
  code-reveals-split, create): a dropped-event counter, or a compact code-state
  **digest** replacing the full path→hash map.
- **Create-outcome per-step map dedup** — carry `code_fingerprint` once at
  assessment level, join by `plan_slug`+`ts`, not one copy per step.
- **Regression tests** for the four apply-loop threading sites and the
  Part-A/escalate best-effort wrap-sites (kwargs forwarded / a raising compute
  never perturbs the host command).

**Recommendation:** ship these as a **separate small plan** (they're independent of
the resolver and would bloat this plan's scope), and record that split in the #72
update. If instead they're folded in, they become new steps here and the plan
grows — flag the choice explicitly, don't silently drop.

---

## 5. Acceptance criteria (plan-level — verify before calling #72 phase 3 done)

- Resolver joins a decision to its outcome (inline for self-recording families;
  `run_id`→run-log + `plan_fingerprint`-transition + reused matcher for async) and
  derives `acted-on`/`no-op`/`reverted`/`still-open`; **no `plan_tool.cli` import**;
  **no second matcher**.
- `plan-tool telemetry` aggregates across plans + over time by `kind`/`decision`,
  prints advisory recs with counts/n; **no Claude**, **no run-log entry**, mutates
  nothing, **exits 0** for every verdict.
- Spike **§7 smoke test** passes end-to-end (`code-reveals-split` → split → next
  sidecar → `acted-on`).
- Aggregation tolerant of the ownerless / `plan_slug=""` / `run_id=""` tail.
- `DATA_CONTRACT.md` documents any new derived/persisted shape, drift guard green;
  **CAPABILITIES.md** + **USE_CASES.md** register the surface.
- **BACKLOG #72 updated**: phase 3 marked shipped; closed or reduced to named
  residual; companion hardening split named; reconciled vs phase-2 known-limits.

---

## 6. One-glance resume

```bash
# 1. author the last detail file
plan-tool detail telemetry-decision-outcome-resolver --step 6 --iterate --commit --time-budget 240 -y
#    (sweep reports/ into a commit if the tree isn't clean afterward)

# 2. build the plan, one step at a time, committing each green step
plan-tool run telemetry-decision-outcome-resolver --commit --time-budget 240

# 3. convergence tail
plan-tool reconcile-code telemetry-decision-outcome-resolver           # loop until --dry-run shows no drift
# then a /code-review session pass, fix + re-review until it converges
```
