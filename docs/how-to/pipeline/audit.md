# `audit` workflow

Run `completeness-audit` on the bare plan after `create` and again after
`detail`, before execution or export. This document explains both audit gates,
their results and recovery. Use `reconcile-plan` before execution when changed
code requires the plan to be re-grounded; post-execution reconciliation uses
`reconcile-code`. Source-of-truth references are inline.

> `completeness-audit` is also the **in-place continuation path** after a `create` /
> `detail` crash or abort. Its resume behavior — deterministic findings
> re-derived from the on-disk plan, a pass-level sampler checkpoint during fresh
> conceptual sampling, and the separate **pre-apply checkpoint** an `--iterate`
> run saves as apply-phase recovery evidence — is in
> [`AUDIT_RESUME_FLOW.md`](../recovery/audit.md) (shared engine:
> [`RESUME_FLOW.md`](../recovery/README.md)).

## TL;DR

- **`completeness-audit`** — conceptual audit of the plan's design. A free
  deterministic layer flags authoring gaps (missing/placeholder body sections,
  steps without detail files, detail-vs-files drift, lessons coverage), then a
  **multi-pass claude audit** (`prompts/plan-audit.md`, run until passes surface
  nothing new, unioned by stable anchor id — `--audit-passes` (default a static
  3; deprecated alias `--audit-samples`) / `--audit-dry-rounds`) judges whether
  the plan's own concepts are **correct** (sound, internally consistent, and
  free of material ambiguity) and **complete** (no orphaned concepts,
  uncovered risks, or dangling acceptance criteria). Ambiguity is reported in
  the persisted `plan-correctness` group: it covers an in-scope contract where
  reasonable readers could produce materially different behavior — **grounded in the
  per-step detail bundle**, with Read/Grep access to the repo at HEAD, so a
  gap a detail file already specifies is not re-flagged. Run first: it gets
  the plan's own house in order before `reconcile` compares it to the code.
- **`reconcile`** — plan-vs-code fit audit. **One claude call** plus deterministic
  primitives. Answers "does the plan still match the code it would edit?", saves a
  walkable artifact, and walks each finding through `apply_finding`.
- **Direction of truth:** both verbs edit the **plan and detail files** only —
  neither touches code. `reconcile` edits the plan to match the code; `completeness-audit`
  edits the plan to make it internally correct, complete, and unambiguous (the audit reads
  code to ground its findings but never writes it).
- **Scope fence:** `completeness-audit` must remain inside the seed/backlog
  **authoring scope contract** (Outcome, In scope, Out of scope / Non-goals,
  Allowed behavior changes, Allowed reorganization). That contract lives in
  the seed/backlog entry; the plan **body**'s only schema-recognized carriers
  are `## Out of scope` and `## Deferred`, plus the optional `## Scope
  guardrails` / `## Audit guardrails` / `## Expected placement` / `## Stack`
  sections a seed's fence lands in verbatim when the seed uses those headings (the rest
  are authoring guidance the audit honors, not required body H2s). When a
  plan was created `--from-existing` and its seed instead states the fence
  under the canonical scope-contract headings, `Plan.source_seed` (BACKLOG
  #162) lets the audit prompt re-read those fields straight from the seed
  file as informational context — the plan body still wins on conflict. A
  plan with no resolvable `source_seed`, or a seed using none of the
  canonical headings, gets no such block; do not treat its absence as
  evidence the plan has no fence. A valid adjacent concern is not a
  completeness gap — tag it `[out-of-scope-deferred]` and route it to
  `BACKLOG.md` / `BUG_BACKLOG.md` rather than strengthening the plan into
  sibling work. Findings tagged `[out-of-scope-deferred]` must not be treated
  as productive for dry-streak / low-yield convergence and must not justify
  count-series guidance. Prefer `--audit-passes 1` for scope-contract-bound
  audits (CLI default remains `3`). Label stops using emitted coverage facts:
  `confirmation_kind=confirmed-dry` / `confirmed-low-yield`,
  `budget_limited=true`, or `early_stop_reason="plan-quota"`.

**Proportionality is part of the scope fence.** Do not enlarge a plan to absorb
a more general abstraction, adjacent workflow, or future capability merely
because it would be useful. A finding is in scope only when the plan's stated
outcome, acceptance property, authority boundary, safety invariant, or ordering
rule cannot hold without it; otherwise defer it as above.

## High-level flow

```
        plan-tool completeness-audit <name>  (run first)
                       |
                       v
        cmd_completeness (plan_tool/cli/completeness_cmd.py)
          1. deterministic primitives, in order:
               correctness  (file existence, deps, path-style)
               completeness (body sections, detail coverage,
                             detail body, files coherence, lessons)
          2. conceptual audit -- multi-pass claude calls (plan-audit.md,
             grounded in the detail bundle; union by stable anchor id
             until a pass adds nothing new). Each completed nonterminal pass
             replaces the stable IN-PROGRESS SAMPLER CHECKPOINT:
               plan-correctness  (unsound / contradictory / materially ambiguous concepts)
               plan-completeness (orphaned concepts, uncovered risks,
                                  dangling criteria, missing edge cases)
             A later fresh sampler resumes at the next un-run pass only when
             this checkpoint's complete identity matches. Otherwise it starts
             a new union at pass 1; an interruption inside a pass retries that
             pass. See AUDIT_RESUME_FLOW.md for the decision flow.
                       |
                       v
          3. after the conceptual sampler reaches a terminal result, under
             --iterate ONLY and before the first apply:
               write_pre_apply_audit_checkpoint -> the PRE-APPLY CHECKPOINT
               (same reports dir, same <ts>-completeness.md/.json names,
                schema-version-4 payload with `qualified_result: null` and
                `is_pre_apply_checkpoint: true`)
               so a crash inside apply_finding cannot discard the audit
                       |
                       v
          4. under --iterate: only findings whose
                           remedy is a plan/detail prose edit are applied
                           via apply_finding (deterministic well-formedness +
                           body/detail-body gaps; conceptual correctness and
                           completeness require session-directed judgment), each fingerprint at most once, re-checking
                           deterministic gaps each round until they converge
                           / no net progress / budget out. Structural
                           diagnostics (unresolved paths, dep-graph gaps,
                           missing detail files, lessons gaps) and advisory
                           plan-completeness/info findings are reported, not
                           applied — dispatching them would only return
                           NOT-APPLICABLE.
                       |
                       v
          5. every run (under --iterate, after the loop):
               print grouped report (correctness first) + save the FINAL report
               (plan-details/<slug>/reports/<ts>-completeness.md; the role
                marker is `false`, so it is the ordinary final artifact)


        plan-tool reconcile-plan <name>              (one claude call; run second)
                       |
                       v
        cmd_review (plan_tool/cli/review_cmd.py) -> review_plan_full (review.py)
          deterministic primitives + one claude call
            (prompts/review.md, every step vs current code)
                       |
                       v
          print report -> save_review
            (plan-details/<slug>/reports/)
                       |
                       v
          walk_recommendations -> apply_finding
            (plan/detail edits only; never code)
                       |
                       v
          extract + append lessons
            (only with --lessons)
```

## `completeness-audit` — conceptual audit (deterministic + multi-pass claude audit)

`cmd_completeness` parses the plan, runs deterministic primitives from
`review.py`, then runs the multi-pass conceptual audit. Correctness findings
(deterministic and conceptual alike) render **before** completeness findings so
structural blockers surface ahead of coverage gaps.

**1. Deterministic layer (free):**

- **Correctness:** `check_file_existence`, `validate_deps`,
  `detect_path_style_mismatch`.
- **Completeness:** `check_body_completeness` (required H2s present and not
  `_(TODO)_`), `check_detail_coverage` (steps missing a `step.detail`),
  `check_detail_body_completeness` (the seven required H2s in each detail file),
  `check_files_coherence` (detail's cited paths vs the step's recognized paths),
  `check_lessons_coverage`.
- **Self-consistency:** the sources in `review.py`'s
  `SELF_CONSISTENCY_SOURCES`, partitioned off the advisory smell bucket onto a
  blocking-capable one and rendered under the report's `### Self-consistency`
  heading. `check_intent_presence` is one of them: a plan or step carrying no
  usable `intent` produces at most two findings per plan — one for the
  plan-level field, one roll-up naming every step id that lacks one. The
  severity and the field contract belong to
  [`PLAN_FORMAT.md`](../../../PLAN_FORMAT.md#smell-checks-advisory).

  **Blocking means blocking *convergence*, nothing else.** A completed audit
  still exits 0 without `--fail-on-findings`, per the exit-code convention.

  **None of these is auto-applied.** They are deliberately outside
  `APPLY_ELIGIBLE_SOURCES`, so `apply_finding` never dispatches one and the
  report's next-steps block names no apply verb for them — `apply_finding` is a
  prose editor and cannot write a frontmatter field. A missing intent's remedy
  is the one-line frontmatter edit `triage_reason` prints; the *drafting* help
  lives at authoring time, in `plan-tool create`'s wizard (see
  [`CREATE_FROM_EXISTING_FLOW.md`](create-from-existing.md#intent-risk-and-ordinary-authoring)).

**Optional purity battery:** `--purity` adds a Claude-backed MIXED-STEP check
after the free deterministic checks and before the conceptual audit. Each
eligible scan has its own per-call timeout. The battery has a separate total
allowance and stops admitting scans when it expires; each remaining readable
eligible step becomes a blocking coverage gap rather than looking like a clean
or advisory result. See [Completeness-audit timeout controls](#completeness-audit-timeout-controls)
for settings, defaults, and precedence.

### Completeness-audit timeout controls

The timeout controls are environment settings, not CLI flags.

| Setting | Default | Scope |
| --- | --- | --- |
| `PLAN_TOOL_PURITY_CLAUDE_TIMEOUT` | 900 seconds | Each eligible purity scan. |
| `PLAN_TOOL_CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT` | 1,800 seconds | Each conceptual-audit backend call. |
| `PLAN_TOOL_PURITY_SCAN_BUDGET` | 1,800 seconds | The whole optional purity battery. |

For a per-call phase, a non-empty phase setting wins, then
`PLAN_TOOL_CLAUDE_TIMEOUT`, then the phase default. A zero, negative, or
malformed phase setting disables that phase's timeout and masks the legacy
global value; an absent or empty phase setting permits fallback. The legacy
global setting remains the timeout for unscoped callers.

The total purity-battery setting never falls back to the legacy global value.
Its zero, negative, or malformed values disable only the total cap. The
per-call purity timeout still applies to every admitted call. This total cap
is separate from `--time-budget`, which cooperatively limits `--iterate` at
round boundaries and does not kill in-flight backend calls.

**2. Conceptual layer (multi-pass claude audit):** `audit_plan_until_stable`
runs `check_plan_audit` until a pass surfaces no new finding (or
`--audit-passes` is hit — default a static 3, since each pass is a full
independent audit over the whole plan + code at HEAD, so extra passes re-roll
the LLM's non-determinism rather than cover more of the plan), unioning by
stable anchor id. Each pass renders
`prompts/plan-audit.md` with the plan body **plus the per-step detail bundle**
(and Read/Grep access to the repo at HEAD), and parses two finding lists:

- **`plan-correctness`** — unsound design, internal contradictions, technically
  wrong concepts, conceptual ordering hazards, or material ambiguity. An
  ambiguity is in scope when reasonable readers could implement or verify
  materially different behavior and neither the detail bundle nor code resolves
  the choice. Routed into the correctness group, it can carry critical/high
  severity.
- **`plan-completeness`** — orphaned concepts, unsatisfied problem statement,
  uncovered risks, dangling acceptance criteria, missing edge-case concepts.
  Routed into the advisory completeness group.

### Bare-plan policy: properties before mechanisms

At bare stage, the audit tests named plan properties rather than unselected
delivery mechanisms. An uncovered route for a named safety, ordering,
ownership, compatibility, bypass, or acceptance property remains an actionable
`plan-correctness` gap; its remedy names the missing property and route. A
typed carrier, serializer, dependency order, fixture shape, telemetry value,
parser arrangement, or comparable internal choice belongs to `detail` when the
plan has not selected it.

The finding must quote the exact plan sentence and anchor it is treating as
the property, not a paraphrase — a sentence declaring a mechanism *unchanged*
or something *out of scope* is a scope statement, not a promise that the
mechanism covers every upstream failure, and citing one as the property is a
grounding error rather than a real gap.

The exception is narrow: the bare audit may require a mechanism when the plan
text explicitly makes that mechanism the observable contract for a named
property. Do not infer that contract from a plausible implementation choice.
This bare-stage policy does not lower the detail-grounded bar: once detail
selects a delivery mechanism, the detail-grounded audit may judge that selected
contract.

Run-grade convergence output and completeness stderr may render a deterministic
bare-mechanism recommendation, composed with `edit_drift` when the same current
finding matches the prior-apply comparison. The signal helps an operator
reconsider a likely detail-owned request; it is neither causal proof nor an
automatic deferral. It changes no finding gate, continuation, failure, or exit
behavior.

**Terminal plan-quota coverage.** After a typed terminal `PLAN_QUOTA` result,
`audit_plan_until_stable` stops later conceptual passes. It records the actual
attempted `passes_used`, configured `cap`, and
`early_stop_reason: "plan-quota"`; coverage is unconfirmed,
`budget_limited` is false, and no confirmation kind is emitted. This is not a
pass-cap budget stop, cannot qualify as reusable evidence, and cannot produce
a clean qualified result. For non-JSON output,
`_persist_and_present_report` still writes an operator-readable Markdown
report, but withholds the ordinary final reusable findings sidecar; the missing
sidecar does not mean the report was lost and does not describe every failed
audit. Resolve the provider condition and run a fresh audit invocation before
using the gate.

**Budget-limited coverage.** When the loop hits `--audit-passes` without a clean
dry tail, it is *budget-limited* (coverage unconfirmed). The audit reports only
the pass cap, pass count, and confirmation state; it does not infer a next action
from the count series. The legacy `coverage.recommendation_kind`,
`coverage.recommended_passes`, and `coverage.recommendation_advice` keys remain
present as `null` for schema compatibility.

**Arm-clustering advisory.** A qualifying run-grade conceptual audit may save one
non-routing `AuditShapeAdvisory` beside its findings. It records the exact
plan/detail audit-input fingerprint, the contiguous arm's step ids, counts, and
anchor slugs grouped by audit axis. Grouped audit output, persisted reports,
concise iterate output and JSON render the same keep-or-
carve prompt only when that dedicated fingerprint still matches current disk. A
human may continue with the arm; that explicitly overrides the non-blocking
signal. The advisory never enters source filters, annotations, workers, or the
apply queue.

**Severity-aware low-yield convergence (BACKLOG #125).** A pass is only
*productive* (resets the dry streak) if it clears `new_threshold` **and** at
least one new finding is material under the calibrated
`convergence.is_blocking_impact` predicate. A material finding does not bypass `new_threshold`; it
only narrows what counts toward it — a below-threshold pass stays
non-productive even if what little it found was material (unchanged
pre-#125 behavior). A threshold-clearing pass whose new findings are *all*
advisory is the new carve-out: non-productive no matter how many of them
there are, so a tail like `…→1→1` of singleton advisory findings no longer
burns passes to the cap. That carve-out alone additionally requires **two**
consecutive non-productive passes before it can stop the loop, even when
`--audit-dry-rounds` is 1 — a single advisory-only pass is suggestive, not
confirmed (the operator's "two repeated low-yield passes" proposal); the
pre-existing below-threshold dry mechanism keeps honoring `dry_rounds` as
configured, with no floor.

The clean-stop verdict distinguishes **`confirmed-dry`** (a literal zero-new
streak) from **`confirmed-low-yield`** (the streak kept discovering findings,
but every one was advisory) via `coverage.confirmation_kind` in the JSON
payload and a "Converged (low-yield)" callout in the markdown report. Both
read `None`/absent on a budget-limited stop, **and** on the `--audit-passes 1`
single-pass fallback when that one pass was productive — `budget_limited` is
unconditionally False in single-pass mode (it always was, pre-#125), so
`confirmation_kind` is gated on the loop actually having gone non-productive
to completion, not merely on `not budget_limited`, so a productive single
pass is never mislabeled `confirmed-dry`. A low-yield stop is still clean
convergence (not budget-limited), but is flagged distinctly so it never reads
as an exhaustively clean audit.

## Post-run reconcile-tail stopping

`reconcile-code --all` is a post-execution implementation check, not another
completeness-audit loop. It uses the plan as canonical, but its model report is
still evidence to verify rather than an authority that classifies a workflow
trap. After three **completed full sweeps**, stop launching another whole sweep
just to enumerate more findings. Record the remaining findings in the handoff
with the plan property at stake, the code and existing test checked, and one
bounded disposition.

Only a verified false plan property — scope/authority, safety, ordering,
acceptance, or an implementation contradiction — calls for a class-wide code
fix and focused regression test. A coverage-only gap gets focused test work;
an unavailable runtime/configuration/capability contract remains fail-closed
and is deferred with its needed evidence. A further full sweep requires a
verified class-wide implementation correction, a newly reproduced
safety/authority failure, or material code drift that invalidates the prior
sweep. Model source, impact, severity, wording, and file labels never select
that exit by themselves. The policy is advisory/session-directed and leaves blocking
predicates, exit codes, and generated finding labels unchanged.

**Calibrated impact-aware convergence.** The selected convergence paths use
`convergence.is_blocking_impact(rec)` with an operation-scoped, historical
calibration lookup. Only evidence-qualified low-impact, medium-severity
recommendation classes can be demoted. High-impact recommendations and
`high`/`critical` severities always block; this is not an impact-only policy.
`audit_plan_until_stable` uses the predicate to decide whether new findings are
material, so completeness callers using that audit loop inherit this narrow
materiality rule. The internal `_iterate_reconcile_loop` helper uses it for its
open-blocking-finding state, but current reconcile CLI routes do not expose
an iteration loop.

`check_plan_audit`'s own within-round materiality check (feeding
`audit_plan_until_stable`'s dry-streak accounting) additionally passes
`classify_domain=classify_finding_domain`: a medium-severity conceptual
finding classified `"docs"` is never material, matching the stage bar's docs
exemption above. Kept stage-agnostic (`check_plan_audit` has no bare/detail
concept). `_iterate_reconcile_loop`'s refreshes deliberately omit
`classify_domain` — they evaluate plan-vs-code drift findings, not conceptual
audit findings, and doc-vs-code drift is what that loop exists to catch.

This rule does **not** make completeness continuation impact-aware: its
deterministic and reporting gates keep their existing policy. Nor does it
change prompts, schemas, recommendations, or convergence diagnosis. The
separate triage partition still decides which findings to apply or defer;
deferring a finding alone does not guarantee another reconcile iteration.

Each conceptual finding carries a trailing `(impact=<level>, complexity=<level>)`
triage tag (parsed into `rec.impact` / `rec.complexity`), so the apply loop's
impact-weighted gate can defer low-impact/high-complexity gaps instead of
auto-applying every finding. Findings without the tag fall open to "apply".

Between the gap prose and that tag, each finding also carries a `→ fix: <one-line
conceptual remediation>` marker (parsed into `rec.suggested_action`). The fix is
stated at the conceptual level — the intent of the change, reading as a natural
continuation of the gap rather than a mechanical code edit. The walk renders it
under a **will apply** label so the operator sees what `(a)pply` will do, and
`apply_finding` injects it into the apply prompt's `## Targeted fix` section so
Claude realizes exactly that intent rather than re-deriving one. Findings without
the marker degrade gracefully (no fix shown; apply reads the gap). `check_plan_audit`
logs how many findings omitted the marker (`N missing → fix:`), parity with the
missing-`[anchor-slug]` count.

**Report artifact.** Every `completeness-audit` run writes a markdown report to
`<plan-dir>/plan-details/<slug>/reports/<ts>-completeness.md`. It records each
finding's *disposition* — applied (with verdict), deferred (with the reason:
structural-diagnostic / info / low-payoff), or advisory conceptual-completeness
— and a per-category rationale explaining **why** a finding wasn't auto-applied.
Under `--iterate` the terminal shows only a concise summary plus the report
path (the long per-item detail lives in the file, reusable later); audit-only
runs still print the grouped report to stdout for interactive reading and also
persist the file. For a standalone read of loop health over saved report
history (three-state verdict plus newest-run advisories), run
`plan-tool convergence <name>` — the completeness report itself does not embed
that diagnosis.

When a current arm-clustering advisory is present, the grouped audit report and
saved report render its committed arm steps, stored counts, and axis-grouped
anchor slugs as an evidence-bearing keep-or-carve decision aid. `--iterate`
keeps the same current signal in its compact summary. Stale optional advice is hidden without changing audit findings.

The conceptual audit runs once up front; only deterministic checks repeat
between repair rounds. Each repair fingerprint dispatches at most once. The
loop stops when deterministic findings converge, the open count stalls
(`--max-stall-rounds`), or the budget is spent; conceptual stage blockers
remain for judged correction.

The iterate loop repairs deterministic well-formedness findings only. Both
conceptual axes remain saved evidence for human or orchestrating-session
judgment. Read the report, verify and judge related findings, edit the plan or
detail text, commit bounded corrections, and re-audit the changed snapshot.

**Bare-plan correction boundary.** A plan is bare when at least one step has
no detail file on disk. Correct material plan-body contracts, ordering, risks,
and acceptance criteria before authoring detail. Keep implementation mechanics
and fixture-level coverage detail-owned. Bare-stage completeness medium findings
remain advisory; audit the complete detail bundle again before execution.
`next_step_gaps` keeps reported close-or-advisory lists consistent with the
stage-aware blocking verdict; see
[One blocking set drives every next step](#one-blocking-set-drives-every-next-step).

### One blocking set drives every next step

After a `completeness-audit`, every message that says what to close and whether
to move on agrees with the finalize gate's own blocking verdict
(`BlockingVerdict` in `plan_tool/completeness_report.py`, built by
`blocking_verdict_from_gate`).

| Verdict state | Command list | Stage transition (`detail`, `run`, `jira`) |
| --- | --- | --- |
| `set`, non-empty | Names the blocking gaps and ends with the re-audit to run after the session-directed edit | Not offered |
| `set`, empty | Offers the next stage; advisory gaps stay listed | Offered |
| `incomplete` | Keeps the blocking ids the stage bar computes, even for a budget-limited audit (named as gaps to close, except under `stale-revision`, where they are advisory), and ends with the re-audit the cause prescribes (table below) | Not offered |
| `absent` | Ends with the re-audit, which establishes the verdict | Not offered |

An advisory gap is listed but holds back no stage.

An `incomplete` verdict carries one `untrusted_cause`
(`_verdict_untrusted_cause` in `plan_tool/cli/completeness_cmd.py`), and the
cause decides the action `_reaudit_command` names:

| Cause | Applies when | Next command says |
| --- | --- | --- |
| `transient` | The audit stopped on a cut-short stop (`max_iterations`, `deadline_exceeded`, `no_progress`, a budget stop), or halted on drift (a re-audit takes a fresh drift baseline) | The plain re-audit, which continues the run |
| `persistent` | Coverage is unqualified, a hand-apply stop or deferrals await a person, or the loop halted on text that fails to parse, a reverted edit, or an unmatched fence (a re-audit reproduces it) | Triage the saved report, correct it in a session-directed edit, and commit before re-auditing the changed snapshot |
| `stale-revision` | No current evidence for this text: the plan changed since the saved evidence, the revision is legacy or unsampled, or the coverage is legacy | Run a fresh audit ("no current audit evidence for this text"); the saved gaps may describe other text, so they are listed as advisory, not text to close and not counted |

When one result fits several causes, the first match wins in the order
`stale-revision`, then `persistent` (an incomplete or unqualified current
result), then — only when no blocking set is present — `transient`, then
`persistent` (hand-apply stop or awaiting deferrals). A non-empty blocking set
is trusted whatever the stop.

The `incomplete` ids come from the stage bar alone. The finalize gate's
`--json` `has_blocking_findings`, `--fail-on-findings`, and exit codes are
unchanged by them.

The readers are `next_stage_command`, `suggested_next_steps`,
`suggested_next_step_commands`, and `console_summary` in
`plan_tool/completeness_report.py`, plus `_render_grouped_report` in
`plan_tool/cli/completeness_phases.py`. The `detail` / `split` / merge parents
in `plan_tool/cli/authoring.py` (`_CompletenessTailOutcome`) drop `run` for the
same reason.

Unchanged: the stage bar stays in `is_blocking_finding`, the stage stays
`derive_audit_stage`'s, and `--json`, `--fail-on-findings`, and exit codes are
as before. The loop-stop `open_findings=` banner is not a next-step reader.

#### Authoring follow-up after a tail audit

`detail`, `split`, and `merge` print one follow-up row after their tail audit.
When the tail result does not prove the bundle on disk current, the row is chosen
by comparing the result's recorded audit revision with the files now on disk
(one capture, shared by both checks), not by the verdict's cause alone:

| Evidence | Row says |
| --- | --- |
| The recorded run-grade revision no longer matches the files | `stale-revision`: "no current audit evidence for this text — run a fresh audit". Whatever the original cause, and its deterministic blockers are not counted (they were computed on the old text) |
| The revision matches, or nothing can be compared (no result, a capture that failed) | The verdict's own cause and count: `transient`, `persistent`, or a `set` verdict's gaps and failing checks |
| An empty set that could not be proven current, or an `absent` verdict | The fixed "no current qualified audit result exists; run a fresh audit" row |

A missing result, retired-grade evidence, or a failed capture is not evidence that the
files moved, so none is called stale. A failed capture is `unknown` in
`project_saved_completeness_result` (what `status` and `list` show); the
authoring tail agrees with it.

### Stage bar and mid-run steering

Operator narrative for bare vs detail bars lives in
[`integrations/shared/DIRECTIVES.md`](../../../integrations/shared/DIRECTIVES.md)
(§ Stage-differentiated conceptual bar).

### Reading the final qualified result

Read a final completeness result in this order: **qualification**, then its
headline, then its suggested next step. Do not infer that order from a finding
count, exit code, stage name, or report filename. The finalizer selects exactly
one headline in this precedence order:

1. `no-qualified-current-evidence` wins whenever current final evidence is
   unavailable. Run a fresh audit before reusing, applying, or presenting saved
   findings as a plan-gap decision surface.
2. `awaiting-human-action` names qualified findings or a terminal state that
   needs human judgment.
3. `advisory-only` preserves qualified, non-blocking result-bearing findings.
4. `clean` requires the existing clean-finalization conditions and no
   result-bearing finding.

The result records separate facts; neither substitutes for the others:

- **Audit stage** is the `bare` or `detail` bar sampled when the conceptual
  audit ran. It is not detail-bundle coverage.
- **Audit coverage** says whether the conceptual-audit sample qualified. A
  completed fresh audit may therefore retain its `bare` or `detail` stage while
  reporting `unconfirmed` coverage.
- **Audit-time plan/detail revision** is the immutable
  `qualified_result.revision_status` plus `qualified_result.audit_revision`.
  The revision identifies the plan and the declared run-grade detail bundle
  when the audit completed.

An absent, skipped, or pre-capture-failed audit explicitly records
`not-sampled` for stage, coverage, and revision status, with a null audit
revision. A bare-stage audit can still provide qualified evidence for plan-level
work. Incomplete coverage, stale or unknown revision evidence, or a missing,
incomplete, or nonmatching audited plan/detail revision cannot become current
qualified evidence. A bare plan does not make missing detail-level work an
automatic apply target; the bare-plan apply fence above keeps that distinction
explicit.

The conceptual audit intentionally reads live project context — code, prompts,
lessons, configuration, and prior audits — so it can explain why an issue
matters in this project. That context is explanation context, not an asserted
frozen input set. Only the audited plan and run-grade detail revision say
what the saved result is about. A later change to either makes the result
noncurrent; a later change to live context alone neither claims to invalidate
the saved result nor reproduces it.

1. **[BLOCK] Stage hoisting** — `cmd_completeness` calls
   `derive_audit_stage(bundle_status)` once before the iterate vs audit-only
   branch (`total == 0 → bare` even when `DetailBundleStatus.is_bare` is false).
2. **[BLOCK] Pass-conformance** — `conforming_pass_count` /
   `failed_or_malformed_pass_count`; `audit_incomplete` when the sample does not
   qualify (including reuse without conformance), the audit was
   `budget_limited` (a well-formed sample still discovering at the pass cap),
   or it ended with `early_stop_reason="plan-quota"` — each independently
   leaves coverage unconfirmed (per `_conceptual_bar_from_audit_recs`).
3. **[BLOCK] Conceptual bar set** — `compute_conceptual_bar_blocking_ids` +
   `is_blocking_finding` (`classify_domain=classify_finding_domain` at both
   stages: medium demotes only on `"docs"`; bare-stage `plan-completeness`
   medium is a separate unconditional non-block).
4. **[BLOCK] Mid-run steering** — `_run_iterate_convergence_loop` remaps
   `converged` / `no_blocking_findings` / `all_auto_apply_findings_deferred`
   when conceptual bar blockers remain → `terminal_hand_apply`.
5. **[BLOCK] Finalize / JSON** — `_completeness_has_blocking_findings`
   bar-aware arm; JSON keys `stage`, `conceptual_bar_blocking_ids`,
   `audit_incomplete`, bar-aware `has_blocking_findings`.

### Saved audit evidence ledger — visible artifacts, not a decision

`plan-tool convergence <name>` renders its convergence diagnosis first, then a
separate **saved audit evidence ledger**. The ledger is a read-only inventory of
saved completeness Markdown and JSON artifacts. It reports what is on disk and
the saved metadata it can read; it does not compare rows, match findings,
establish freshness, or decide whether the audit loop is converging.

The empty result and every row have a local next action:

| Ledger result | Meaning | Rendered next action |
|---|---|---|
| `no-saved-audits` | No saved completeness-audit artifacts are present. | `Run a completeness audit to save structured evidence.` |
| `orphan-sidecar` | A readable `kind="completeness"` JSON sidecar has no matching Markdown report. | `Inspect the saved artifact or run a fresh completeness audit.` |
| `malformed-sidecar` | A JSON sidecar is unreadable or its saved kind is not `completeness`, with or without a matching Markdown report. | `Inspect the saved artifact or run a fresh completeness audit.` |
| `checkpoint` | A complete saved pair is a confirmed pre-apply checkpoint, so it is not an ordinary final. | `Inspect the saved artifact or run a fresh completeness audit.` |
| `in-progress-checkpoint` | The stable sampler sidecar records completed nonterminal conceptual passes. It is resumable only through the exact-match sampler gate, never as final evidence. | `Inspect the saved artifact or run a fresh completeness audit.` |
| `terminal-sampler-residue` | The sampler published its non-resumable terminal lifecycle before cleanup; a cleanup failure left this diagnostic-only residue. | `Inspect the saved artifact or run a fresh completeness audit.` |
| `unknown-role` | A complete saved pair has an untrusted persisted role. | `Inspect the saved artifact or run a fresh completeness audit.` |
| `saved-final` | A complete `kind="completeness"` pair has the ordinary-final role. Its metadata and qualified result remain saved facts, not current evidence. | See the saved-final actions below. |

For a `saved-final` row whose saved qualified-result headline is
`no-qualified-current-evidence`, the renderer says `Run a fresh completeness
audit.` because its saved result says no qualified current evidence exists. For
any other known saved headline, it says `Inspect the saved report and its saved
result.` If the saved qualified result is unknown, it says `Inspect the saved
artifact; run a fresh audit when a qualified result is needed.` Unknown metadata
stays unknown: the ledger does not infer a present plan, detail bundle, code
state, or audit result from it.

Treat each action as local to the named artifact. More than one ledger row does
not call for a re-audit by itself and does not establish a comparable series,
trajectory, confirmation, or current result.

Ledger actions stay command-agnostic: they describe what the saved row warrants
without inferring that a plan-specific command is applicable.

### Pre-apply checkpoint vs. final report — the persisted role

An `--iterate` audit keeps three distinct artifact kinds. While fresh
conceptual sampling continues, `audit_plan_until_stable` writes its stable
`in-progress-sampler-checkpoint.json` sidecar. After sampling reaches a
terminal result, `write_pre_apply_audit_checkpoint`
(`plan_tool/cli/completeness_phases.py`) writes the separate timestamped
apply-phase checkpoint before the first `apply_finding`; the persistence tail
then writes the timestamped ordinary final. Artifact purpose and the loaded
payload decide their meaning, never directory position or timestamp.

| Artifact | Written by | Read as |
|---|---|---|
| In-progress sampler checkpoint | `plan_tool/review.py:audit_plan_until_stable` through `save_sampler_checkpoint`, at a completed continuing pass | A stable JSON-only recovery boundary. Only the sampler's exact identity gate may resume its accumulated union at the next pass. |
| Terminal sampler residue | The sampler publishes `sampler_state.lifecycle="terminal-residue"` before it attempts cleanup of an existing sampler checkpoint. | Non-resumable, non-final diagnostic evidence when cleanup leaves the stable sidecar behind. |
| Pre-apply checkpoint | `write_pre_apply_audit_checkpoint`, before the first `apply_finding`; this artifact keeps the ordinary timestamped Markdown and JSON names. | Apply-phase crash-recovery evidence, never a completed audit. |
| Ordinary final | The normal report persistence tail after the audit and any iterate loop. | The only completeness artifact eligible for ordinary final readers. |

**The three role states** live on `SavedReview.is_pre_apply_checkpoint` and are
normalized on load; [`DATA_CONTRACT.md`](../../../DATA_CONTRACT.md) § `SavedReview`
owns the full policy. `True` marks a confirmed non-final checkpoint, `False`
an ordinary final, and `None` untrusted metadata. `sampler_state` further
distinguishes the sampler's `in-progress` and `terminal-residue` lifecycles
from the separate pre-apply checkpoint. New sampler and pre-apply checkpoints
are schema version **4**, `kind="completeness"`, `qualified_result: null`, and
role `true`; new finals carry role `false` and a final `qualified_result`.
Unmarked version-1/2 and role-aware version-3 records remain legacy-readable.

The sampler is considered only after ordinary-final reuse has declined and the
command reaches fresh conceptual sampling. It neither reorders
`resolve_reusable_audit` selection nor turns a checkpoint into a reusable
final. [`AUDIT_RESUME_FLOW.md`](../recovery/audit.md) owns the detailed
resume, decline, terminal-transition, and cleanup sequence.

Every new final and checkpoint completeness sidecar carrying
`qualified_result` writes schema version **4**. Version-1–3 sidecars remain
legacy-readable. A pre-v4 reader rejects v4 rather than silently dropping
`qualified_result` and misreading the result or checkpoint role.

`qualified_result.revision_status` and
`qualified_result.audit_revision` remain audit-time facts; reading a saved
record later does not recalculate or replace them. The read-time
`view_revision_status` compares only the saved audit revision's plan and
declared run-grade detail bundle with disk. It is a current-artifact view, not a
second audit and not a verdict on live context. An annotation rewrite preserves
the v4 payload and result fields. Neither it nor a later view may downgrade the
sidecar, rewrite the saved result, or make a checkpoint, legacy payload,
incomplete revision, or noncurrent sidecar appear current.

**Malformed metadata fails closed, and stays on disk.** A non-boolean marker, a
marker on a non-completeness sidecar, a marker in a version-1/2 sidecar (a
role/version mismatch), or a version-3/4 sidecar with no marker all read as
unknown. Such a sidecar remains loadable and inspectable through `load_review`;
it is simply ineligible for reuse and convergence history. Nothing is deleted,
migrated, or silently reclassified — including the historical unmarked pairs
already tracked in this repo.

**Same-second publication allocates distinct stems.** A timestamped pre-apply
checkpoint and the final report that follows it can land in one wall-clock
second, and the timestamp stem is the only thing keeping them apart.
`_reserve_report_timestamp` reserves the Markdown report, findings sidecar,
and optional data-contract payload *together* at one whole-second stem,
advancing whole seconds until all three are free; that reserved timestamp is
what `created_at` records. The sampler instead owns its fixed stable filename.

**The reader boundary.** Four readers decide eligibility from the loaded
payload:

The ledger is not a fifth eligibility reader. `load_audit_evidence_ledger`
lists completeness artifacts without selecting convergence history, and
`render_audit_evidence_ledger` presents that inventory after
`render_diagnosis`. `no-history` in the diagnosis therefore means that
`load_report_history` found no eligible ordinary-final sidecar whose kind is in
`HISTORY_KINDS`; it does **not** mean the reports directory contains no file.
The ledger can consequently display report-only, orphan-sidecar,
malformed-sidecar, a pre-apply checkpoint, either sampler state, or
unknown-role evidence beside a `no-history` diagnosis.

- **Reuse** — `resolve_reusable_audit` selects the newest sidecar satisfying
  `is_reusable_audit_sidecar`: both `kind="completeness"` **and** the ordinary-
  final role. A filename that ends `-completeness.json` over a payload of
  another kind is rejected on the payload, and a pre-apply checkpoint,
  in-progress sampler checkpoint, terminal sampler residue, or unknown role is
  skipped outright rather than returned as a stale verdict, so non-final
  findings never supply the next audit.
- **Convergence history** — `load_report_history` keeps a sidecar only when its
  `kind` is in `HISTORY_KINDS` *and* `_is_final_report_role` holds, so a
  `RunSnapshot` is created from eligible ordinary finals only. Pre-apply
  checkpoints and either sampler lifecycle never enter history. The exclusion
  happens once, for every caller.
- **`reconcile-plan` prompt reuse** — `_prompt_reuse_saved_review` applies the
  same rule to its own kind through `_review_reuse_ineligibility`: an
  ordinary-final `kind="review"` payload only. Unpinned, it scans newest-first
  past unreadable, checkpoint, unknown-role, and non-review saves; a pinned
  `--reuse-id` that is ineligible declines with its reason instead of falling
  back.
- **`reconcile-plan-walk` direct walk** — `cmd_review_walk` owns a separate,
  kind-agnostic policy: only a loaded sidecar whose
  `SavedReview.is_pre_apply_checkpoint is False` can enter its per-finding
  walk. By default it scans the selected plan's listed sidecars newest-first,
  skipping malformed, confirmed-checkpoint (including either sampler
  lifecycle), unknown-role, and foreign-target candidates until it finds an
  ordinary final. It does not restrict the saved kind, perform reuse freshness
  checks, or start a replacement audit: it replays the selected saved findings
  only. If no final is eligible, it reports no eligible saved review, exits `2`,
  and starts no walk or annotation mutation.

  An explicit `--id` is stricter: it may match exactly one basename or stem
  already listed under the selected plan's reports directory, and that
  candidate's resolved path must remain inside that directory. The reports
  root itself must be the canonical non-symlink location beside the selected
  plan, so it cannot redirect the listing to another plan. Path-bearing input,
  no match, an ambiguous match, a foreign-target symlink, an unreadable
  sidecar, a checkpoint, and an unknown role each receive their own refusal
  and exit `2`; an exact selection never falls back to an older artifact.

Direct-walk filtering does not change the generic
`plan_tool/review_persistence.py:resolve_saved_review()` locator or pre-apply
checkpoint recovery. A sampler checkpoint never reaches
`plan_tool/cli/data_contract_cmd.py:cmd_data_contract_apply()`, which requires
ordinary final qualified evidence.

**Who inherits this, and who does not.** `plan_tool/telemetry_analysis.py`,
`plan_tool/split_criteria.py`, and `plan-tool convergence` consume
`load_report_history` and therefore inherit final-only history without carrying
role rules of their own. The sampler's non-final boundary applies everywhere it
could otherwise be mistaken for audit evidence; it is not an application,
direct-walk, reuse, or history input.

### Authoring tails use only final, current evidence

`_persist_and_present_report()` passes a final qualified result to
`_run_completeness_tail()` only after it persists and presents the ordinary
final report; checkpoints never enter that handoff. A create, detail, split, or
merge tail retains result-aware guidance only when that final result has
confirmed coverage, an audit-time current plan/detail revision, and an exact
current match for the same plan and declared run-grade detail bundle. The eligible
headlines are `awaiting-human-action`, `advisory-only`, and `clean`.

When the result is absent, is a checkpoint, says
`no-qualified-current-evidence`, lacks confirmed/current/matching plan-detail
evidence, or carries retired detail-grade evidence, authoring leads with a fresh run-grade
`completeness-audit` instead. This transport selects existing guidance; it does
not rebuild the audit policy or promote a saved finding into current evidence.

> The code-aware fulfillment check (`check_criteria_fulfillment`) belongs to
> `verify`. `completeness-audit` reads code to ground design findings, not to
> judge whether shipped code delivers the criteria.

## `reconcile` — plan-vs-code fit (one claude call)

`cmd_review` → `review_plan_full`:

1. **Reuse check:** offers to reuse a previously saved reconcile's findings
   instead of spending a fresh claude call — but **only when that save is
   fingerprint-fresh**: the saved sidecar's captured **plan fingerprint AND code
   fingerprint** must both still match current disk. Any plan edit or in-scope
   code change (including a deleted / newly-landed in-scope file) declines and
   re-audits. The **deterministic primitives are never gated** — file-existence,
   deps, path-style, and the looks-already-done heuristic run on every
   invocation, reuse or not (the cheap-correctness-always-runs invariant the
   completeness reuse path documents). Three flags drive the decision:
   `--reuse` reuses when fresh (no prompt), `--no-reuse` always re-audits,
   `--reuse-id STEM` pins a specific saved sidecar; **unset prompts on a TTY and
   auto-decides under `--yes` / non-TTY**. See the
   [Reusing a saved reconcile](../../../RUNBOOK.md#reusing-a-saved-reconcile---reuse)
   runbook subsection for the operator recipe (the flag surface lives in the
   runbook). Two verdict paths apply the same plan-AND-code gate: `reconcile-plan`
   (kind `review`) recomputes the freshness verdict **inline** in
   `review_cmd.py`'s `_prompt_reuse_saved_review` (there is no
   `resolve_reusable_review`), while `reconcile-code` and `detail --reconcile`
   route through the shared `resolve_reusable_reconcile` helper.
2. **Audit:** combines deterministic primitives (file existence, deps, path-style,
   the looks-already-done heuristic) with a **single claude semantic review call**
   (`prompts/review.md`) covering every step's body and frontmatter against the
   current code.
3. **Report + save:** prints the report and persists it as a walkable artifact
   under `plan-details/<slug>/reports/` (`save_review`) so the findings
   can be stepped through later without re-invoking claude.
4. **Walk:** `walk_recommendations` steps through each recommendation, dispatching
   applies through `apply_finding` — which edits the **plan/detail files only**.
   On by default on a TTY (or `--yes`); skipped in non-interactive contexts, which
   just get the report. The `intent-presence` finding never reaches this walk —
   the smell fan-out that mints it runs in `completeness-audit` and in
   `plan-tool validate`, not in `reconcile`.
5. **Lessons:** with `--lessons` (off by default), distills + appends lessons
   from the review (best-effort).

`plan-tool reconcile-plan-walk <name>` replays a saved ordinary-final review
later (`cmd_review_walk`) — same per-finding apply/skip loop, no new claude
call. Its persisted-role reader boundary above describes its kind-agnostic
default and exact `--id` selection rules.

## When to reach past `reconcile`

`reconcile` is the preferred plan-vs-codebase reconciliation entry point — one claude
call audits every step. `plan-tool detail <name> --reconcile --step N` is a
per-step drill-down for when `reconcile` flags concrete drift in a specific step's
detail body; see [Per-subcommand reconcile](../../GATES.md#per-subcommand-reconcile)
for the code-is-truth vs plan-is-truth split.

## Source map

| Concern                          | File                                                            |
|----------------------------------|-----------------------------------------------------------------|
| Conceptual audit (det. + claude) | `plan_tool/cli/completeness_cmd.py` (`cmd_completeness`)         |
| Qualified-result finalization | `plan_tool/cli/completeness_cmd.py` (`finalize_completeness_run`) |
| Result JSON, report, and final handoff | `plan_tool/cli/completeness_phases.py` (`_render_completeness_json`, `_persist_and_present_report`) |
| Result report assembly | `plan_tool/completeness_report.py` (`build_report_md`) |
| Saved result, coverage normalization, and read-time revision view | `plan_tool/review_persistence.py` (`normalize_audit_coverage`, `audit_coverage_qualifies_sample`, `SavedReview.qualified_result`, `project_saved_completeness_result`) |
| Authoring result handoff | `plan_tool/cli/authoring.py` (`_run_completeness_tail`) |
| Deterministic primitives         | `plan_tool/review.py` (`check_file_existence`, `validate_deps`, `detect_path_style_mismatch`, `check_body_completeness`, `check_detail_coverage`, `check_detail_body_completeness`, `check_files_coherence`, `check_lessons_coverage`) |
| Conceptual audit prompt, quota stop, and check | `plan_tool/prompts/plan-audit.md`, `plan_tool/review.py` (`audit_plan_until_stable`, `check_plan_audit`, `render_plan_audit_prompt`) |
| Bare-plan policy prompt + classifier | `plan_tool/review.py` (`render_plan_audit_prompt`, `classify_likely_bare_mechanism`) |
| Bare-mechanism / `edit_drift` advisory | `plan_tool/convergence_diagnosis.py` (`classify_bare_mechanism_advisory`, `compose_mechanism_edit_drift_advisory_lines`, `render_diagnosis`) |
| Completeness stderr advisory | `plan_tool/cli/completeness_cmd.py` (`_convergence_loop_advisory_lines`, `_emit_convergence_loop_advisories`) |
| Completeness timeout controls | `plan_tool/cli/completeness_phases.py` (`_collect_purity_split_findings`, `_sample_conceptual_audit`); `plan_tool/shell.py` (`scoped_claude_timeout`, `_effective_subprocess_timeout`) |
| Arm advisory capture + freshness | `plan_tool/audit_shapes.py` (`AuditShapeAdvisory`, `evaluate_arm_clustering`), `plan_tool/review_persistence.py` (`AuditInputSnapshot`, `audit_input_fingerprint_matches_disk`) |
| Checkpoint role (persisted contract) | `plan_tool/review_persistence.py` (`SavedReview.is_pre_apply_checkpoint`, `SavedReview.is_in_progress_sampler_checkpoint`, `_normalize_checkpoint_role`, `save_review`'s `is_pre_apply_checkpoint=`); policy in [`../DATA_CONTRACT.md`](../../../DATA_CONTRACT.md) § `SavedReview` |
| Sampler persistence, resume, and terminal transition | `plan_tool/review.py` (`audit_plan_until_stable`, `_restore_sampler_checkpoint_state`, `write_completed_sampler_boundary`); `plan_tool/review_persistence.py` (`sampler_checkpoint_path`, `load_sampler_checkpoint`, `save_sampler_checkpoint`) |
| Pre-apply checkpoint writer | `plan_tool/cli/completeness_phases.py` (`write_pre_apply_audit_checkpoint` — the apply-phase checkpoint writer) |
| Same-second stem allocation | `plan_tool/completeness_report.py` (`_reserve_report_timestamp`, `_report_artifact_paths`, `write_completeness_report`) |
| Role-aware reuse reader | `plan_tool/completeness_report.py` (`is_reusable_audit_sidecar`, `resolve_reusable_audit`) |
| Role-aware history reader | `plan_tool/convergence_diagnosis.py` (`_is_final_report_role`, `load_report_history`, `HISTORY_KINDS`) |
| Saved audit evidence ledger | `plan_tool/convergence_diagnosis.py` (`load_audit_evidence_ledger`, `render_audit_evidence_ledger`) |
| Role-aware direct-walk reader | `plan_tool/cli/review_cmd.py` (`cmd_review_walk` — listed, contained ordinary-final selection; kind-agnostic replay) |
| Standalone convergence diagnosis + ledger render | `plan_tool/cli/convergence_cmd.py` (`cmd_convergence`); `plan_tool/convergence_diagnosis.py` (`diagnose_convergence`, `render_diagnosis`) |
| Intent-presence detector          | `plan_tool/review.py` (`check_intent_presence`, `is_usable_intent`, `INTENT_PRESENCE_SOURCE`, its `triage_reason` branch) |
| Self-consistency partition + next steps | `plan_tool/review.py` (`SELF_CONSISTENCY_SOURCES`), `plan_tool/cli/completeness_phases.py` (the `### Self-consistency` render and its next-steps line) |
| Deterministic battery + report      | `plan_tool/cli/completeness_phases.py` (`deterministic_detector_registry`, `_render_grouped_report`, `_render_completeness_json`) |
| Advisory presentation             | `plan_tool/completeness_report.py` (`prepare_audit_shape_advisory_display`, shared markdown/console/JSON renderers) |
| Report assembly                   | `plan_tool/completeness_report.py` (`build_report_md`) |
| Bare-plan conceptual apply fence  | `plan_tool/completeness_report.py` (`next_step_gaps`, `_blocked_next_step`, `DETAIL_LEVEL_FINDING_SOURCES`); `plan_tool/review.py` (`audit_detail_bundle_status`, `DetailBundleStatus`) |
| Run-grade detail-bundle fingerprint | `plan_tool/fingerprint.py` (`compute_detail_bundle_fingerprint`) |
| Audit stage derivation            | `plan_tool/cli/completeness_phases.py` (`derive_audit_stage`) |
| Stage conceptual bar              | `plan_tool/convergence.py` (`is_blocking_finding`, `STAGE_BARE`, `STAGE_DETAIL`); `plan_tool/review.py` (`classify_finding_domain`) |
| Conceptual bar blocking set       | `plan_tool/cli/completeness_phases.py` (`compute_conceptual_bar_blocking_ids`); `plan_tool/completeness_report.py` (`BlockingVerdict`, `blocking_verdict_from_gate`); `plan_tool/cli/completeness_cmd.py` (`_completeness_has_blocking_findings`) |
| Mid-run bar steering              | `plan_tool/cli/completeness_phases.py` (`_run_iterate_convergence_loop` → `terminal_hand_apply`) |
| Impact-aware continuation         | `plan_tool/convergence.py` (`is_blocking_impact` — reconcile + `material_new` only, **not** the completeness stage bar); audit materiality in `plan_tool/review.py` (`audit_plan_until_stable`, inherited by completeness callers); internal reconcile refresh helper in `plan_tool/cli/reconcile.py` (`_iterate_reconcile_loop`; no CLI iteration route) |
| Plan-vs-code audit               | `plan_tool/cli/review_cmd.py` (`cmd_review`), `plan_tool/review.py` (`review_plan_full`) |
| Review prompt template           | `plan_tool/prompts/review.md`                                   |
| Findings parse / verdict         | `plan_tool/review.py` (`_claude_recommendations`), `plan_tool/launcher.py` (`summarize_findings`, `format_findings_verdict`) |
| Save / load artifacts            | `plan_tool/review_persistence.py` (`save_review`, `load_review`)|
| Walk + apply                     | `plan_tool/review_walk.py` (`walk_recommendations`), `plan_tool/launcher.py` (`apply_finding`) |
| Reconcile-sidecar reuse verdict  | `plan_tool/cli/reconcile.py` (`resolve_reusable_reconcile`, `ReusableReconcile`) for `reconcile-code` / `detail --reconcile`; `reconcile-plan` (kind `review`) recomputes the verdict inline in `plan_tool/cli/review_cmd.py` (`_prompt_reuse_saved_review`, no `resolve_reusable_review`) |
| Plan / code fingerprints         | `plan_tool/review_persistence.py` (`compute_plan_fingerprint`), `plan_tool/fingerprint.py` (`compute_code_fingerprint` — the `fingerprint.py` leaf, **not** `completeness_report.py`) |
| Reuse gate + code-drift warning (CLI) | `plan_tool/cli/reconcile.py` (`_prompt_reuse_saved`, `_warn_reuse_code_drift`), `plan_tool/cli/review_cmd.py` (`_prompt_reuse_saved_review`) |
| Replay saved review              | `plan_tool/cli/review_cmd.py` (`cmd_review_walk`)               |
| Lessons capture                  | `plan_tool/prompts/extract-lessons-review.md`                   |
