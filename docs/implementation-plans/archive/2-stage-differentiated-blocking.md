> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Stage Differentiated Blocking
intent: '`completeness-audit` applies **different blocking bars by audit stage** and
  those bars **steer the iterate loop mid-run** (not only finalize/JSON/CI). A **bare-plan**
  gate is clean after **one** completed clean audit pass (medium+ correctness clear
  and no high-or-critical completeness). A **detail-grounded** gate (gate 2) demotes
  medium docs/unit-test findings for the stop while keeping medium code-logic blocking.
  Finalize and `--json` carry stage + bar-blocking; reporting polish is Deferred.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add deterministic classify_finding_domain in review.py
  intent: Deliver a deterministic no-Claude domain classifier over conceptual finding
    prose with closed vocabulary; matched-signal precedence code-logic > unit-test
    > docs; unknown is the no-match default only. Pin both BACKLOG 91 shapes as conceptual
    Recommendation fixtures (docs pin is prose-shaped medium, not the files-coherence
    diagnostic).
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/stage-differentiated-blocking/01-deterministic-classify-finding-domain.md
  status: done
- id: 2
  title: Add stage-aware is_blocking_finding with classify_domain callback
  intent: 'Add is_blocking_finding(rec, *, stage=..., classify_domain=...) in plan_tool/convergence.py:
    bare uses source-axis+severity (no domain call; medium completeness does not block);
    detail uses domain on conceptual mediums (missing callback → unknown); non-conceptual
    severity-only; keep is_blocking/is_blocking_impact unchanged; synthetic #248 count
    fixture for is_blocking tallies; assert bare bar stays blocking across all four
    sample rounds (not over-permissive); separate conceptual fixtures for is_blocking_finding.'
  files:
  - plan_tool/convergence.py
  - tests/test_convergence.py
  creates:
  - tests/fixtures/convergence/bare-bar-four-round-sample.json
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/stage-differentiated-blocking/02-stage-aware-blocking-finding-classify.md
  status: done
- id: 3
  title: Hoist one stage derivation before the iterate or audit-only branch
  intent: 'Behavior-preserving refactor only: derive DetailBundleStatus / stage once
    before the iterate versus audit-only branch using the Architecture table — total
    == 0 → bare first (step-less plans are bare even when is_bare is False), then
    is_fully_bare / otherwise detail — and thread it to emit_bare_plan_banner, the
    loop, finalize, and write_pre_apply_audit_checkpoint (including grade). Do not
    delegate stage to is_bare alone. No new bar behavior.'
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/stage-differentiated-blocking/03-hoist-one-stage-derivation-before.md
  status: done
- id: 4
  title: Surface pass-conformance and compute conceptual bar-blocking set
  intent: On live audit entry points and accepted reuse, surface pass-conformance
    and compute conceptual bar-blocking over the union via is_blocking_finding (detail
    stage must pass classify_domain=classify_finding_domain); bar set = stable finding
    ids where the bar is true; extend _AUDIT_COVERAGE_KEYS, normalize_audit_coverage,
    project_audit_coverage, and _coverage_input_from_reusable_audit / _coverage_for_sidecar
    together with the new keys (closed vocab in DATA_CONTRACT.md — exact-key normalize
    must accept them); auto-reuse without conformance declines to a fresh audit; explicit
    --reuse-audit/--reuse-audit-id without conformance → audit_incomplete; accepted
    reuse with conformance may count as the qualifying sample.
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/review.py
  - plan_tool/review_persistence.py
  - DATA_CONTRACT.md
  - tests/cli/test_completeness_cmd.py
  - tests/test_convergence.py
  - tests/test_review.py
  - tests/test_data_contract.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/stage-differentiated-blocking/04-surface-pass-conformance-compute.md
  status: done
- id: 5
  title: Steer the iterate loop mid-run with the stage bar
  intent: 'Mid-run: after every should_continue result (including no_blocking_findings
    and all_auto_apply_findings_deferred) and at not-open_apply (including iteration-0
    when open_apply is empty and the loop would record converged while conceptual
    bar blockers remain), remap conceptual bar blocks to terminal_hand_apply with
    remedy by class on existing surfaces (walkable correctness → completeness-apply
    / diagnostic_remedies when sidecar exists; bare high/critical plan-completeness
    bar ids → hand-edit; bare medium completeness outside the bar → withhold informational
    copy; detail completeness bar ids → hand-edit / _sc_manual_fix_note); never claim
    clean mid-run. Preserve deterministic has_blocking_findings.'
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 4
  detail: docs/implementation-plans/plan-details/stage-differentiated-blocking/05-steer-iterate-loop-mid-run-stage-bar.md
  status: done
- id: 6
  title: Carry stage bar into finalize, --json, --fail-on-findings, and CLI help
  intent: 'Finalize owns clean (pass-conformance qualifying sample ∧ conceptual bar
    ∧ non-conceptual arms ∧ loop-kind eligibility from outcome.stop_reason — halt
    and loop paths, pre- and post-remap). Machine-visible clean signal: --json exposes
    audit_incomplete=false, has_blocking_findings=false (bar-aware), and outcome.stop_reason
    eligible — no separate clean key required. confirmation_kind does not gate clean;
    budget_limited alone does not deny. Carry stage + conceptual_bar_blocking_ids
    (stable ids) + audit_incomplete into --json; has_blocking_findings in JSON/finalize
    is bar-aware _completeness_has_blocking_findings with classify_domain=classify_finding_domain
    at detail. Align _render_coverage_confidence_markdown and emit_coverage_unconfirmed
    with qualifying-sample. CLI help. Minimal reporting only.'
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - DATA_CONTRACT.md
  - docs/cli/completeness-audit.md
  - docs/cli/README.md
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_cli_reference.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/stage-differentiated-blocking/06-carry-stage-bar-finalize-json-fail-on.md
  status: done
- id: 7
  title: Update the gate docs and close BACKLOG 91 and 248
  intent: Make the two-bar + mid-run rule discoverable beside the severity-aware stopping
    rule and is_blocking_impact policy boundary; partially close BACKLOG 91 and 248;
    point reporting polish at the Deferred / follow-up entry.
  files:
  - integrations/shared/DIRECTIVES.md
  - CLAUDE.md
  - docs/AUDIT_FLOW.md
  - RUNBOOK.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 5
  - 6
  detail: docs/implementation-plans/plan-details/stage-differentiated-blocking/07-update-gate-docs-close-backlog-91-248.md
  status: done
---
# Stage Differentiated Blocking

## Overview

Make `completeness-audit`'s stop decision stage-aware, and make that decision **steer the iterate loop mid-run** as well as finalize / `--json` / `--fail-on-findings`. A **bare-plan** gate is clean after **one completed clean audit pass**: conceptual `plan-correctness` clear at medium+ and no high-or-critical completeness, **and** today's non-conceptual blocking arms clear — **finalize** owns that clean claim. A **detail-grounded** gate (**gate 2**) blocks on medium **code-logic** findings (both conceptual sources) and treats medium **docs/unit-test** findings as advisory for the stop. Discriminator: `is_blocking_finding(rec, *, stage=…, classify_domain=…)`. Coexists with `is_blocking` and `is_blocking_impact`. Stage once per invocation before the iterate / audit-only branch.

**Settled 2026-08-09 (do not re-open):** bare clean = **one** completed clean pass; the bar **must** steer loop mid-run. **Settled 2026-08-10:** this plan ships the **core** (bars + mid-run + finalize/JSON); reporting polish (full stop-reason vocabulary, set-aside handoff, intros, tails, jira next-steps) is **Deferred** — do not expand Gate 1 to cover it.

## Problem statement

Severity-only `is_blocking` is the wrong completeness-loop question (#248 sample). #248 and #91 rewrite the completeness stop on independent axes — land them together. The #248 entry supplies **per-round counts only**; the fixture is **synthetic** for `is_blocking` tallies **and** must assert the **bare** `is_blocking_finding` policy would **not** have exited early across those four rounds (over-permissive check from #248 Verification). Exercise domain/`is_blocking_finding` detail behavior on separately authored conceptual fixtures (not claimed as #248 prose provenance).

## Architecture

### Predicates

| Predicate | Role |
| --- | --- |
| `is_blocking(severity)` | Pure severity helper — **keeps this name**. |
| `is_blocking_finding(rec, *, stage=…, classify_domain=…)` | Stage-aware discriminator for loop + finalize. **Bare (`stage="bare"`):** no `classify_domain` call — block by **source axis + severity** (medium+ `plan-correctness` blocks; `plan-completeness` blocks only at high/critical; nit/info never). Not “severity for every conceptual finding.” **Detail:** domain call on conceptual mediums (missing callback → `unknown`); non-conceptual → severity-only, no domain call. |
| `is_blocking_impact(rec, …)` | Unchanged — reconcile + conceptual `material_new` only. |

Closed **stage** vocabulary: `bare` | `detail` (JSON / finalize must match).

### Stage selection (once, before iterate / audit-only branch)

| Bundle / grade input | Bar |
| --- | --- |
| `total == 0` (including step-less plans where HEAD `is_bare`/`is_fully_bare` are False) | `bare`. Check **`total == 0` first** — do not derive stage from `is_bare` alone. |
| `is_fully_bare` (including all-`done` never-detailed) | `bare`. `done` counts toward bareness. Withholding still keys on `is_bare` (False when step-less — empty set-aside). |
| Otherwise at requested `--grade` | `detail`. Selection is grounding, not an ordered "never lowers" claim. |
| **Jira-grade** (`--no-iterate` only) | Bar follows jira-grade artifact presence; run-grade-only → `bare`. |

### The two bars (settled)

| Stage | Blocking bar |
| --- | --- |
| `bare` | Conceptual: zero medium+ `plan-correctness` and zero high-or-critical completeness. Non-conceptual: today's arms unchanged. Clean (finalize): conceptual ∧ non-conceptual ∧ qualifying sample ∧ loop kind eligible. |
| `detail` | Conceptual (both sources): high/critical always; nit/info never; medium blocks iff `code-logic` or `unknown`; docs/unit-test mediums advisory. Same non-conceptual rule. |

**Persisted severity:** prompt `LOW` → stored `medium` (accepted cost; clean-eligible correctness in practice is `nit`/`info` only).

**Qualifying clean audit sample:** bar reads the **union**. For a **live** audit in this invocation: qualifies when the pass-conformance aggregate shows ≥1 conforming outer pass **and** zero failed/malformed outer passes (`conforming_pass_count` / `failed_or_malformed_pass_count`). Inner heading-retry inside `check_plan_audit` does **not** create a second outer pass — a successful inner retry makes that **one** outer pass conforming (the failed first attempt is not a separate outer failed pass). Any failed/malformed **outer** pass → `audit_incomplete`.

**Sole conceptual-audit evidence gate for finalize `clean`:** those pass-conformance aggregates. Legacy `confirmation_kind` (`confirmed-dry` / `confirmed-low-yield` / …) stays a productivity / dry-streak **reporting** field only — it does **not** add a separate clean requirement and must not be consulted to deny or grant clean. Not `confirmed-dry`.

**Accepted reuse as qualifying sample:** when explicit `--reuse-audit` / `--reuse-audit-id` is accepted **and** the persisted payload’s pass-conformance aggregates meet the same qualifying-sample criteria as a live audit (`conforming_pass_count` / `failed_or_malformed_pass_count`), that save **counts as** the one qualifying sample (no live pass required). Bar clearance is evaluated **separately** for finalize `clean` — a conforming reused sidecar with remaining conceptual bar blockers still qualifies the sample and is still not-clean. Without conformance evidence → `audit_incomplete` (already settled).

**No mandatory two-pass streak; no bare dry-round floor of 2.**

**`budget_limited`:** reported; does **not** by itself deny clean when pass-conformance qualifies. Clean still requires a qualifying sample (errored-empty unions are not clean). Mid-run `emit_coverage_unconfirmed` follows the same rule as `_render_coverage_confidence_markdown`: suppress the “not fully validated” warning when `conforming_pass_count` qualifies even if `budget_limited` is true.

**Pass-conformance signal (settled):** step 4 adds an explicit run-level aggregate on the audit return (and persisted coverage for reuse) — e.g. `conforming_pass_count` / `failed_or_malformed_pass_count` (exact key names in `DATA_CONTRACT.md`). Extend `_AUDIT_COVERAGE_KEYS`, `normalize_audit_coverage`, `project_audit_coverage`, and `_coverage_input_from_reusable_audit` / `_coverage_for_sidecar` **together** — HEAD `normalize_audit_coverage` rejects any dict whose key set is not exactly `_AUDIT_COVERAGE_KEYS`, so writer-only changes still drop/deny conformance. **Do not** reuse `advisory_valid` / `advisory_invalid` (grade-gated / skip-false). Per attempted pass: invoker success **and** both required headings → conforming; invoker failure or missing headings → failed/malformed; skipped-without-attempt counts as neither. Qualifying sample uses that aggregate only.

### Domain classifier

Closed: `code-logic` | `docs` | `unit-test` | `unknown`. Matched precedence: **code-logic > unit-test > docs**. `unknown` = no-match default only. Conceptual sources; deterministic; not persisted. #91 pins = conceptual Recommendation fixtures (not live files-coherence).

### Mid-run steering (settled)

0. Hoist stage (step 3). Step 4 computes pass-conformance + conceptual bar-blocking for **all three** conceptual sources: live `audit_plan_until_stable`, live `_sample_conceptual_audit`, **and** accepted reuse (`reused_audit_recs`) — conformance gate in `_resolve_audit_reuse`/`_accept_reuse` only; **post-hoist** `is_blocking_finding(..., stage=<hoisted>, classify_domain=classify_finding_domain when stage is detail)` over the saved union before the iterate loop body and before finalize/`--json`. The **conceptual bar-blocking set** is the stable finding `id`s where that predicate is true (not full records); JSON key `conceptual_bar_blocking_ids` (name in `DATA_CONTRACT.md`). `_halt()` preserves bar/incomplete fields once computed.
1. Conceptual ids stay out of `current_finding_ids`.
2. Do **not** force conceptual into `has_blocking_findings` (preserves advisory `no_blocking_findings`).
3. After **every** `should_continue` return **and** at `not open_apply` (including **iteration 0**, where HEAD records `_loop_stop_reason=converged` when deterministic `open_apply` is empty while conceptual findings remain only in `_audit_recs`): leaf continue while deterministic auto-apply remains; leaf `converged` / **`no_blocking_findings`** / **`all_auto_apply_findings_deferred`** / idle while the bar still sees conceptual blockers → remap to **`terminal_hand_apply`** (with remedy by class), never mid-run `clean`. This is load-bearing: rule 2 keeps conceptual out of `has_blocking_findings`, so iteration-0 `converged`, deferred-all-auto-apply, and post-apply `no_blocking_findings` are the common exits when only conceptual blockers remain — the bar re-decision must catch all three, not only the post-`should_continue` path.
4. Conceptual-only blockers → terminal stop kind **`terminal_hand_apply`** (name = not-converged conceptual stop, **not** “always hand-edit”); remedy by class on **existing** mid-run surfaces for both `should_continue` exits and the `not open_apply` branch: walkable `plan-correctness` → `completeness-apply` / `diagnostic_remedies` when a sidecar exists; **blocking** bare `plan-completeness` (high/critical ids in `conceptual_bar_blocking_ids`) → hand-edit / `_sc_manual_fix_note` (Testing: high-or-critical + withhold → hand-edit); bare **medium** completeness outside the bar set → bare-withhold informational copy only; detail-grounded completeness bar ids → hand-edit / `_sc_manual_fix_note`. Do **not** print withhold-style “informational until detail” for bar-blocking high/critical completeness. No busy-loop.
5. **Observable:** stop-kind + remedy + no mid-run clean — not extra apply rounds.
6. Finalize owns clean; `_completeness_has_blocking_findings` conceptual arm calls the same `is_blocking_finding` wiring (including `classify_domain=classify_finding_domain` at detail).

**Core stop kinds this plan owns:** `terminal_hand_apply`, `audit_incomplete`, `clean` (finalize only). Treat loop reason `blocked` as an **alias** of existing producer `manual_fix_blocking_findings` for clean-eligibility only (no new `_loop_stop_reason="blocked"` writer). Full machine→display vocabulary is Deferred.

**Clean eligibility:** finalize `clean` only when conceptual ∧ non-conceptual ∧ qualifying sample hold **and** the loop-kind input is eligible. That input is **`outcome.stop_reason`** after the iterate (or audit-only) path returns — covering halt (`halted: *` from `_halt()`, which never writes `_loop_stop_reason`) **and** normal loop exits (`stop_reason=_loop_stop_reason`, pre- and post-bar-remap). Do **not** consult only the internal `_loop_stop_reason` variable. Map machine reasons as follows (reported kinds may still be Deferred):

| `outcome.stop_reason` (halt + loop; pre- or post-remap) | Finalize clean eligible? |
| --- | --- |
| `converged` / `no_blocking_findings` after bar remap cleared (or never blocked) → treated as idle/`deferred_advisory` path | yes, if other arms clear |
| `all_auto_apply_findings_deferred` when bar clear | yes, if other arms clear |
| `terminal_hand_apply` (incl. remapped from `converged`/`no_blocking_findings`/`all_auto_apply_findings_deferred` while bar blocks) | **no** |
| `manual_fix_blocking_findings` (incl. eligibility alias `blocked`) | **no** |
| `max_iterations` / `no_progress` / `marginal` / `deadline_exceeded` / `time_budget_exceeded` (= budget exhaustion) | **no** |
| `halted: *` | **no** |
| `audit_incomplete` | **no** |
| `--no-iterate` / no loop (`audit_only`) | yes, if other arms clear |

**`has_blocking_findings` dual use (settled):** keep the **names** but split roles — (1) `ConvergenceState.has_blocking_findings` stays **deterministic-only** (mid-run rule 2); (2) finalize / `--json` / `--fail-on-findings` use `_completeness_has_blocking_findings`, whose conceptual arm is **stage-bar** `is_blocking_finding` (with `classify_domain=classify_finding_domain` when `stage="detail"`). Do **not** write the stage bar into `ConvergenceState.has_blocking_findings`. JSON keeps legacy key `has_blocking_findings` for the finalize predicate (bar-aware) and exposes `stage` + `conceptual_bar_blocking_ids` (stable ids where the bar is true) so CI is not ambiguous.

### Stop inputs

- High-or-critical completeness blocks both bars.
- Code-logic-medium completeness blocks detail only; docs/unit-test medium demotion on both conceptual sources at detail.
- Hand-edit when withhold (`is_bare`) applies.
- Conceptual sources = `{plan-correctness, plan-completeness}`.

### Finalize / JSON (minimal, in scope)

- Carry `stage`, `conceptual_bar_blocking_ids` (stable ids of conceptual findings where `is_blocking_finding` is true under the selected stage), and `audit_incomplete` into finalize / `--json` / `--fail-on-findings` (rc 1 on incomplete fresh sample). Name the field in `DATA_CONTRACT.md`.
- When `audit_incomplete`, **do not** present an empty conceptual blocking set as a measured “none” — mark blockers unavailable / not measured.
- Finalize `clean` evidence = pass-conformance aggregates only; do not require `confirmation_kind`; `budget_limited` alone does not deny.
- Detail-stage finalize / JSON / `--fail-on-findings` must call `is_blocking_finding(..., stage="detail", classify_domain=classify_finding_domain)` everywhere the conceptual bar is evaluated (same as step 4 mid-run set).
- Loop-kind eligibility reads `outcome.stop_reason` (halt + loop), not `_loop_stop_reason` alone.
- CLI help: not a flat medium+ completeness gate.
- **Reuse:** explicit `--reuse-audit` **and** `--reuse-audit-id` without conformance → `audit_incomplete` (same rule); auto-reuse without conformance → decline and fresh audit. Step 4 must thread new conformance keys through `_AUDIT_COVERAGE_KEYS` / `normalize_audit_coverage` / `project_audit_coverage` / `_coverage_input_from_reusable_audit` / `_coverage_for_sidecar` together.
- **Coverage callout:** `_render_coverage_confidence_markdown` **and** mid-run `emit_coverage_unconfirmed` must follow the qualifying-sample rule — do not tell operators clean is “not fully validated” solely because `budget_limited` is true when the sample qualifies.
- **`audit_incomplete` operator route (all producers):** re-run with a live sample (`--no-reuse-audit` when a weak sidecar was the cause); do **not** raise `--audit-passes` as the primary remedy for errored/malformed passes. Failed invoker / malformed headings / reuse-without-conformance all print this route.

### Reporting polish (Deferred — not this plan)

Full stop-reason vocabulary, clean-bare set-aside handoff listing, withheld-completeness intro rewrites, gate-2 tail bar naming, jira-grade clean next-steps, revision-qualification prose on every surface. Tracked as Deferred + BACKLOG follow-up after this ships.

### Backlog / docs

Step 7: document two-bar + mid-run rule; partially close #91/#248; re-file four-loop consistency and reconcile `is_blocking_impact`; point to Deferred reporting follow-up.

## Input

- `plan_tool/convergence.py` — `is_blocking`, `is_blocking_impact`, `should_continue`, `has_blocking_findings`.
- Audit stream + pass-conformance (both entry points).
- `DetailBundleStatus.total` / `is_fully_bare` / `is_bare`.
- Completeness wiring — pre-branch stage, mid-run re-decide, finalize.

## References

- [typing](https://docs.python.org/3/library/typing.html), [PEP 3102](https://peps.python.org/pep-3102/), [pytest parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html).

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Reporting polish listed under Deferred.
- Edit-drift; bare withhold (#241); multi-pass streak; dry-round floor of 2; arm-clustering; audit prompt; severity reassignment; spinning/FORK_*; #158/#168; #255.
- Stage bar in reconcile / create / detail loops.
- Persisted `Recommendation.domain`; expanding into `is_blocking_impact`.
- Classifier live-rate accuracy as a build gate.
- Changing unconditional `_completeness_has_blocking_findings` arms (`files_coh_issues` → `BUG_BACKLOG.md`).

## Risks

- Axis mislabel vs severity — #248 fixture cannot withdraw the bar.
- Docs demotion reachability when findings cite `.py` anchors — fixture demotion required; live rate Deferred.
- `--fail-on-findings` loosens on demoted mediums; tightens on `audit_incomplete` (rc 1).
- Deferral bet: medium completeness set aside at bare may multiply after `detail` — accepted; measurement Deferred.
- Busy-loop if mid-run mis-wired; forcing conceptual into `has_blocking_findings` kills advisory exit.
- Folded LOW→medium blocks bare with no advisory band — accepted.
- Shipping without reporting polish means operators may not see set-aside lists until the follow-up — accepted for this carve.

## Testing

- Bare: medium+ correctness → not clean mid-run; high-or-critical + withhold → hand-edit; walkable correctness → apply when sidecar exists; nit/info + deferred medium completeness + pass-conformance qualifying sample + finalize clear → clean eligible; any failed pass → `audit_incomplete`; `budget_limited` alone / `confirmation_kind` alone do not deny when sample qualifies.
- Detail: docs/unit-test medium advisory; code-logic blocks; unknown blocks; demote a docs-domain conceptual medium fixture; bar evaluators pass `classify_domain=classify_finding_domain`.
- Mid-run: conceptual-only → `terminal_hand_apply` with class-mapped remedy surfaces, including iteration-0 `not open_apply` that would otherwise record `converged` and later `all_auto_apply_findings_deferred` while the bar still blocks; bare high/critical completeness bar ids → hand-edit (not withhold informational); deterministic work first; `has_blocking_findings` deterministic; never prints `clean`.
- Hoist: `total == 0 → bare` before `is_bare`; behavior-preserving otherwise; conformance + `conceptual_bar_blocking_ids` on both entry points and accepted reuse; coverage-key normalize accepts new keys; reused sample qualifies on pass-conformance alone (bar separate).
- Finalize/JSON/`--fail-on-findings` / `--no-iterate` match core bar; JSON exposes `conceptual_bar_blocking_ids`; clean eligibility uses `outcome.stop_reason`; auto-reuse without conformance → fresh audit.
- Fixture: `is_blocking` tallies; bare `is_blocking_finding` stays blocking across all four #248 sample rounds; separate fixtures for detail/domain cases.
- Pass-conformance keys distinct from `advisory_valid`; jira-grade one-pass can still qualify.
- `audit_incomplete` JSON does not claim empty measured blockers; `--reuse-audit-id` matches explicit reuse rule; incomplete remedy printed for invoker/malformed/reuse producers.
- `emit_coverage_unconfirmed` suppresses unconfirmed warning when sample qualifies despite `budget_limited`.

**Per-step:** steps 1–6 tests green; step 7 doc verification.

## Acceptance criteria

- `is_blocking_finding` beside unchanged `is_blocking` / `is_blocking_impact`; bare = source-axis+severity (no domain); detail = domain on conceptual mediums.
- Domain classifier + #91 conceptual fixtures; detail demotes a docs medium.
- Stage once before branch; values `bare` | `detail`.
- One qualifying clean sample via pass-conformance aggregates; no mandatory streak; errored passes → `audit_incomplete`; `budget_limited` alone ≠ deny; `confirmation_kind` does not gate clean.
- Mid-run stop-kind + remedy by class on existing surfaces; `terminal_hand_apply` ≠ always hand-edit; no conceptual force into `has_blocking_findings`; finalize owns clean via `outcome.stop_reason`.
- Pass-conformance aggregate with named coverage keys (not `advisory_valid`); `_AUDIT_COVERAGE_KEYS` / normalize / project updated together; reuse rules cover `--reuse-audit` and `--reuse-audit-id`; auto-reuse declines without conformance.
- Detail bar sites pass `classify_domain=classify_finding_domain` into `is_blocking_finding`.
- Finalize/JSON/`--fail-on-findings`: stage + `conceptual_bar_blocking_ids` + incomplete; clean signal = `audit_incomplete=false` ∧ bar-aware `has_blocking_findings=false` ∧ eligible `outcome.stop_reason`; incomplete omits measured-empty blockers; incomplete prints re-run route; coverage callouts (markdown + `emit_coverage_unconfirmed`) match qualifying-sample; CLI help updated.
- #248 fixture pins bare bar not over-permissive across four rounds; docs + partial backlog closure; reporting polish Deferred.

**Superseded 2026-08-14 (BACKLOG #91):** `is_blocking_impact` gained an
optional `classify_domain` param (`material_new` only, still stage-agnostic
and still separate from the stage bar); bare stage now also demotes on
`classify_domain` → `docs` for `plan-correctness`; detail's demotion narrowed
to `docs` only (`unit-test` now blocks, same as `code-logic`). See BACKLOG
#91's status for current behavior.

## Deferred

- Reporting polish: full stop-reason vocabulary, set-aside handoff, intros, gate-2 tails, jira next-steps, revision-qualification prose (BACKLOG #260 after this ships).
- Discriminating axis-vs-severity calibration; domain-classifier live-rate corpus.
- Stage bars for reconcile / create / detail.
- Persisted domain field; decision telemetry expansion.
