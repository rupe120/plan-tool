> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Completeness Stage Bar Reporting
intent: Make completeness-audit results accurately explain what happened and what
  to do next. Every human-readable report, JSON result, failure signal, and Jira-grade
  handoff uses one qualified result contract, distinguishing no qualified evidence,
  a human-action stop, an advisory-only result, and a clean result from coverage and
  revision qualifiers—without changing the settled blocking or automatic-apply policy.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Define the qualified audit-result contract
  intent: Gives every completeness consumer one ordered result model, exhaustive finalization-state
    mapping, and immutable audited-plan/detail revision before new wording or output
    fields are added.
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/completeness_report.py
  - plan_tool/fingerprint.py
  - plan_tool/review.py
  - plan_tool/review_persistence.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_completeness_report.py
  - tests/test_review.py
  - tests/test_review_persistence.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/completeness-stage-bar-reporting/01-define-qualified-audit-result-contract.md
  status: done
- id: 2
  title: Show the qualified audit result everywhere
  intent: Lets operators and machine consumers see one result, its evidence qualification,
    and the exact persisted plan/detail revision being viewed.
  files:
  - DATA_CONTRACT.md
  - plan_tool/cli/data_contract_cmd.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/review_cmd.py
  - plan_tool/completeness_report.py
  - plan_tool/review_persistence.py
  - tests/cli/test_data_contract_cmd.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_review_cmds.py
  - tests/test_data_contract.py
  - tests/test_completeness_report.py
  - tests/test_review_persistence.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the shared finalization decision that the new status contract qualifies
      and renders.
  detail: docs/implementation-plans/plan-details/completeness-stage-bar-reporting/02-show-qualified-audit-result-everywhere.md
  status: done
- id: 3
  title: Give create and detail the right audit follow-up
  intent: Makes create and every detail grade plainly say when there is no current
    qualified audit result and suggest a safe next action.
  files:
  - plan_tool/cli/authoring.py
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_authoring_cmds.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Supplies the qualified audit outcome that authoring uses to choose safe stage-specific
      follow-up commands.
  detail: docs/implementation-plans/plan-details/completeness-stage-bar-reporting/03-give-create-detail-right-audit-follow-up.md
  status: done
- id: 4
  title: Document result interpretation and plan-gap handoff
  intent: Makes result precedence, bare-plan deferral, revision qualification, Jira-grade
    handoff, and assistant-led plan-gap presentation understandable without reading
    code.
  files:
  - CLAUDE.md
  - docs/AUDIT_FLOW.md
  - integrations/shared/DIRECTIVES.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: Defines the status vocabulary and report behavior the flow document describes.
    3: Settles the post-create, post-detail, and Jira-grade handoff language.
  detail: docs/implementation-plans/plan-details/completeness-stage-bar-reporting/04-document-result-interpretation-plan-gap.md
  status: done
---
# Completeness Stage Bar Reporting

## Overview

`stage-differentiated-blocking` shipped the core two-bar policy. Its Gate 1
reporting arm was intentionally deferred so the bar could stabilize first.
The logic now needs one result contract that tells the operator whether there is
no qualified evidence, work is awaiting a human, work is deliberately advisory,
or work is clean, while separately explaining coverage and revision context.

## Problem statement

The same short output currently has to carry several distinct facts. An operator
can mistake a non-blocking bare completeness finding for a clean plan, mistake a
coverage-limited, malformed, legacy-unknown, or stale reused audit for an
approved revision, or receive a next command after create/detail even when no
current audit result exists. Machine consumers also cannot rely on a documented
result shape. This is a communication/traceability gap, not evidence that the
blocking policy is wrong.

## Architecture

Define one shared result model before rendering it. It retains the underlying
facts—stop reason, finding disposition, audit stage, coverage confidence, and
audited-revision identity—but selects one headline in this order: no qualified
current evidence, awaiting human action, advisory-only, then clean. Coverage and
revision facts remain visible qualifiers; they never disappear into a
clean-sounding headline. A stale saved audit means its reuse is declined and the
operator is routed to a fresh audit. Once a fresh audit captures current inputs,
the old saved audit is not carried forward as a stale qualifier.

That order is global, not a default: no-qualified-current-evidence overrides
every stop, halt, finding class, and presentation branch. Stop/halt mappings are
evaluated only after a sample is final and qualified; only then can a human-action
or advisory outcome outrank clean. This prevents a failed or coverage-unconfirmed
audit that later halts from acquiring a contradictory human-action headline.

The new routing is deterministic. The shared contract selects headlines, exit
guidance, apply/re-audit commands, and authoring follow-up from persisted audit
facts: completion, explicit stop/halt, normalized finding disposition, stage,
coverage, and revision freshness. It must not add an application-flow branch
based on a model's narrative category, cluster, role, or suggested wording. The
settled blocking policy still consumes its existing normalized finding inputs;
this work only makes that policy's result explainable. Model findings may supply
evidence and human-facing explanation, but they do not become a second routing
authority.

Step 1 owns one exhaustive mapping from existing audit-only and iterate outcomes
to those headlines. No qualified current evidence leads when the audit was
absent, skipped, failed, coverage-unconfirmed, legacy-unknown, or no longer
matches the state captured for its sample. An audit-only run has no iterate stop
reason: with qualified evidence, blocking findings mean awaiting human action,
non-blocking findings mean advisory-only, and no findings mean clean. In an
iterate run, `terminal_hand_apply`, `manual_fix_blocking_findings`, and every
early/halted exit mean awaiting human action; `all_auto_apply_findings_deferred`
is a routing state, not a headline: it is advisory-only only when every
remaining deferred finding is explicitly advisory and no human action remains.
Structural diagnostics, manually fixable findings, and triage-deferred material
findings instead mean awaiting human action, even if no automatic apply remains.
`converged` or `no_blocking_findings` means clean only when the established
finalization predicate permits it *and* no result-bearing finding remains.
When qualified evidence has only advisory findings—including a bare medium
completeness finding after an iterate loop's `converged` or
`no_blocking_findings` stop—the headline is advisory-only, never clean. The
mapping takes named aggregate facts (blocking, manual, deferred-by-class,
remaining-advisory, coverage, revision, and stop) rather than relying on a
reporter to infer a conclusion from missing stop data. The pre-apply checkpoint
remains recovery evidence, not a user-facing final result. The mapping is a
shared table or helper, not prose re-derived independently by a reporter.

Create one grade-aware audited plan/detail capture before the conceptual audit
begins, and use that same capture both to build the model's plan/detail prompt
payload and to populate the persisted audit revision. It records the plan bytes,
the selected detail for every step, each selected path and resolution, its
present/missing/unreadable state, content digest where present, and the derived
bare/detail stage. The run-grade `AuditInputSnapshot` flow is extended to this
shared contract; Jira grade uses the same contract for its Jira-selected
artifacts instead of taking a separate live read. Project code and all other
context remain live outside this capture. No fresh, reused, iterate, or Jira
path may re-read or re-digest plan/detail input after capture and then call it
the audited revision. Preserve the captured values through the pre-apply
checkpoint, final report, reuse checks, and authoring handoff instead of
recomputing them after iteration changes the plan or details. A missing selected
detail is an explicit captured bare-plan state; a failed capture yields no
qualified current evidence.

The audit continues to read the live project as context. Code, prompts, lessons,
configuration, and prior audit history help the model explain why a plan issue
matters; they are not asserted to be frozen or reproducible inputs, and their
later change does not by itself make a saved plan audit stale. The audit revision
therefore identifies the plan and selected detail bundle that the result is
about, not every source the model may consult. Before reuse, replay, or an
authoring follow-up presents a result as current, compare those plan/detail
artifacts to the captured revision. A mismatch leads to a fresh-audit
suggestion. This adds accurate presentation and persistence only: existing
blocking bars, apply eligibility, loop stops, and exit behavior stay unchanged.

Persisted Markdown, JSON, and sidecars are immutable audit-time records. Their
revision qualification says whether the sampled revision was current when that
audit finalized; it never changes after a later edit. Any command that reads a
saved report computes a separate live freshness projection against disk at view
time. That projection—not the historical record—governs whether the reader may
call the result current, reuse it, replay/apply its findings, or offer a current
next step. A later mismatch therefore presents the record as historical/stale
without rewriting its sampled fingerprints or pretending that the original audit
never happened.

`coverage-unconfirmed` is the public qualifier for a fresh audit whose pass cap
was reached while still discovering, or whose sample had no conforming pass or
failed/malformed passes. `coverage-unknown-legacy` is a distinct qualifier for
a reused legacy sidecar that has no valid coverage provenance. Both lead to no
qualified current evidence, but reports and JSON preserve the distinction rather
than inventing fresh-sample coverage facts for a legacy save. An audit revision
covers the sampled plan bytes and exactly the detail bundle selected by the
grade. It uses a plan-only sampled fingerprint rather than the compatible
`compute_plan_fingerprint()` digest, which hashes every root detail and does not
represent Jira selection. Project code and other model context remain live
explanation context, not revision-qualification inputs. Any plan or
grade-selected-detail mismatch is stale.

Render the shared model at stderr, persisted Markdown, JSON,
`--fail-on-findings` guidance, and authoring handoffs rather than re-deriving
prose at each site. JSON receives an additive, documented result object with a
headline plus stage, coverage, and revision qualification; existing keys keep
their established meaning, and absent/legacy values never mean clean. The
bare-plan handoff names its deferred completeness set and intended detail-stage
re-evaluation; a detail-grounded result uses its own bar name.

The additive JSON object is named `qualified_result`. It is present in every
new final CLI JSON payload and final persisted sidecar, while legacy sidecars
remain readable without pretending that the object existed. Its required fields are
`headline` (`no-qualified-current-evidence`, `awaiting-human-action`,
`advisory-only`, or `clean`), `stage` (`bare`, `detail`, or `not-sampled`),
`coverage` (`confirmed`, `unconfirmed`, `unknown-legacy`, or `not-sampled`),
and `revision_status` (`current`, `stale`, `unknown-legacy`, or
`not-sampled`). A result with no completed audited-revision capture—an absent,
skipped, or pre-capture failed audit—uses `not-sampled` for all three
qualifiers and `audit_revision: null`. A completed fresh sample whose passes
fail, are malformed, or exhaust coverage retains its captured bare/detail
stage and uses `unconfirmed`; legacy sidecars remain result-less or project
only `unknown-legacy` compatibility facts. Its nullable
`audit_revision` object carries a sampled `plan_fingerprint` plus an ordered
grade-selected detail-bundle revision. Every bundle entry identifies its step,
selected path and resolution, present/missing/unreadable state, and a content
digest when present, so absence cannot disappear from the identity. Those values
come from the one capture that supplied the model's plan/detail payload; the
object is present for a known fresh or stale sample and `null` for an absent,
unsampled, or legacy-unknown sample. Existing code fingerprints may remain
historical report metadata, but they do not qualify the result as current.
`stage` and `revision_status` are immutable
audit-time qualification. A
later saved-report reader emits a separate live `view_revision_status` projection
using the same enum, without rewriting `qualified_result`. Existing post-loop
top-level `stage`, `coverage`, `stop_reason`, and finding keys keep their current meanings;
the new object is the only joined audit-time interpretation.
A pre-apply recovery checkpoint retains its explicit checkpoint role but writes
`qualified_result: null`; report readers, reuse selection, and next-step output
must never present it as a final result or choose it as current evidence.

Every non-empty current finding in the deterministic correctness, body/detail
coverage, files/lessons, data-contract, self-consistency, purity-coverage,
conceptual plan-audit, or smell output bucket is result-bearing. `path_style`
and dependency diagnostics are result-bearing whenever they surface a current
issue. Audit-shape advice, plan-mass data, coverage metadata, and report
footnotes are diagnostic context only, never findings. This one deterministic
membership set decides whether a qualified result is clean or advisory-only;
no renderer maintains its own list.

The final/current qualification rule applies to every completeness-sidecar
consumer, not only the main report: default selection, explicit `--id` lookup,
reuse, `completeness-apply`, `data-contract-apply`, the generic saved-review
walk, next-step rendering, and any new consumer. A checkpoint, stale, legacy,
coverage-unconfirmed, or malformed completeness sidecar cannot supply current
evidence or findings to any of those paths. `convergence` remains a historical
trend diagnostic across saved reports, not a consumer that presents one report
as the current audit result. A consumer may inspect a checkpoint only as
recovery evidence and must direct the operator to a fresh final audit before
replaying or applying findings.

Step 3 owns an explicit authoring outcome matrix. When `create` wrote and
registered a plan, it has no current completeness result because it has not
sampled the plan, so it suggests a fresh bare-plan `completeness-audit` command
rather than presenting a prior sidecar as current. A successful `create` split
proposal wrote no plan or detail bundle, so it must retain the carve/create
follow-up and offer no audit command. A run-grade detail/split/merge result may
use the tail's result only when it is a final qualified result: confirmed
coverage, a current sampled revision, and a headline other than
`no-qualified-current-evidence`. A completed tail with a pass-cap,
failed/malformed sample, stale revision, checkpoint role, or any other
unqualified state instead says that there is no current result and gives the
grade-compatible fresh audit command. A tail disabled by `--no-completeness`,
skipped because no detail was written, or failed follows that same no-current
result branch. Jira-grade detail deliberately skips the run-grade tail; it names
the Jira-grade audit command and never repurposes a run-grade sidecar. In every
branch, a sidecar from before authoring changed the plan or selected detail bundle
is historical evidence, not a current result.

When an assistant presents in-scope plan-level gaps for a scope decision, the
documentation defines a neutral map: plan intent, related raw findings,
relevant step intent, what happened, and a suggested next step. That map is
assistant guidance, not a CLI-generated LLM feature, a new gate, or a decision
about how the user must dispose of a gap.

## References

- [sys — System-specific parameters and functions](https://docs.python.org/3.13/library/sys.html) — Covers stderr and process exit behavior needed to preserve the CLI’s output-stream and finalization contract.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Documents CLI option parsing and error exits relevant to keeping --fail-on-findings guidance consistent with existing status behavior.
- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Defines the standard-library serialization APIs for adding stable stop-reason, stage, and revision-qualification fields.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Covers SHA-256 digest APIs relevant to presenting the audited plan revision fingerprint without changing its identity scheme.
- [How to capture stdout/stderr output](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Explains pytest capture fixtures for pinning the stderr and JSON/report output contracts at their CLI consumers.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://datatracker.ietf.org/doc/html/rfc8259) — Specifies interoperable JSON structure and values for the persisted and --json audit-result contract.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing the bare-plan or detail-grounded blocking bars, severity thresholds,
  domain classification, or pass-count policy.
- Changing which findings automatic iteration applies or placing conceptual
  findings into an apply-eligible convergence state.
- #261 policy-channel ownership, #231 bad-fix provenance, and #262 generic
  detail-readiness guidance.
- New audit scoring, new exit-code semantics beyond accurately reflecting the
  existing finalization contract, or broad report-layout restyling.
- A model-generated CLI plan-gap map, automatic gap grouping, or a tool-selected
  apply/defer/carve decision.

## Risks

- A more explicit status line can accidentally become a new gate; preserve
  existing exit/finalization semantics and test them.
- Repeating derived state across reporters can create contradictory messages;
  define precedence once and reuse it.
- A stale-audit label must identify the audited plan and selected details without
  claiming the plan is invalid, discarding useful findings, or treating live
  project context as a frozen audit input.
- The documented plan-gap map can sound like a tool verdict; keep it neutral and
  make the user, rather than the map, decide a gap's disposition.

## Testing

Exercise representative bare clean, bare advisory-only medium completeness,
detail-grounded clean, human-action stop, absent/skipped/pre-capture-failed
audit evidence, coverage-unconfirmed evidence from a completed fresh sample
(pass cap or failed/malformed passes), legacy-unknown coverage, stale reused
evidence, and a fresh audit after stale reuse. Pin the no-sample result's
`not-sampled` stage, coverage, revision status, and null audit revision.
Assert one headline/qualifier precedence at stderr, persisted Markdown, JSON,
`--fail-on-findings`, and Jira-grade next-step surfaces where applicable. Pin
the additive JSON/data-contract shape and sampled plan/selected-detail-bundle
freshness, and
that the same finding sets retain their previous blocking and apply decisions;
only the explanation changes. Exercise every existing finalization state:
`terminal_hand_apply`, `manual_fix_blocking_findings`,
`all_auto_apply_findings_deferred`, `converged`, `no_blocking_findings`, and
each early/halted exit. Pin the sampled plan/selected-detail revision and audit
stage in both the pre-apply checkpoint and final sidecar; prove a later plan or
selected-detail change presents the saved result as non-current without
rewriting its captured revision, while a later fresh audit presents its own
revision. Project code, prompts, lessons, configuration, and history remain
live context for explaining findings: prove changes to them do not claim to
invalidate or reproduce the saved plan/detail result.
Prove a bare sample that later gains detail retains a bare
`qualified_result.stage` while the post-loop top-level stage reports the current
bundle. Exercise audited-revision capture failure and missing/unreadable
grade-selected plan/detail input for each grade, proving those failures yield no
qualified current evidence without changing the live-context policy or leaving
a new durable plan artifact. Prove every fresh, reused, iterate, and Jira-grade
path uses one grade-aware capture for both its model plan/detail payload and its
persisted audit revision, with no later plan/detail re-read able to replace that
identity. Exercise audit-only runs with blocking findings, only
advisory deferrals, structural/manual/material deferrals, and no findings, as
well as every iterate outcome.
Exercise `converged` and `no_blocking_findings` with a remaining bare medium
completeness finding, proving the headline remains advisory-only; clean requires
no result-bearing finding. Exercise authoring tails that complete with
unconfirmed coverage, malformed/failed samples, stale revisions, and checkpoint
roles, proving none can become a current authoring handoff.
Exercise create; run-grade detail/split/merge with a completed, disabled,
skipped, or failed tail; and Jira-grade detail, proving each no-current branch
names the grade-compatible fresh audit and rejects older sidecars as current.
Exercise `create` separately for a written plan and a successful split proposal:
only the written-plan branch may name an audit command. Pin fresh-unconfirmed
and legacy-unknown coverage as distinct report/JSON qualifiers that both prevent
a qualified current result. Pin final-sidecar `qualified_result` fields and
pre-apply checkpoint `qualified_result: null`, including readers that must not
reuse or present a checkpoint as final.
Exercise no-qualified-current-evidence with every stop/halt value, proving it
always wins headline precedence. Populate each named current finding bucket and
each diagnostic-only output, proving the shared membership set selects
advisory-only versus clean consistently. Exercise default and explicit-id
selection for every completeness-sidecar consumer, including
`data-contract-apply` and the generic saved-review walk; a pre-apply checkpoint
may be inspected but cannot be replayed, applied, reused, presented as current,
or selected as the newest final audit. Persist a current audit, then change the plan or selected detail
after the sidecar and static Markdown/JSON have been written. Prove the saved
record keeps its original sampled fingerprints and audit-time
`revision_status`, while every later reader emits a stale
`view_revision_status`, rejects reuse/replay/current next steps, and directs to
a fresh audit.
Pin the `qualified_result` JSON/sidecar schema, its new schema-version
transition for both final and checkpoint completeness sidecars, every enum,
nullable revision rule, and legacy-read behavior while proving existing
top-level keys remain unchanged. Version 1–3 sidecars remain readable as legacy
evidence; version-4 `qualified_result` sidecars are rejected by an older reader
rather than silently dropping the object, and annotation rewrites preserve both
their version and result. Perturb model wording, finding order, and presentation grouping while
holding normalized audit facts constant; the selected headline, route, and exit
guidance must remain unchanged.
Check the documented plan-gap map includes plan
intent, relevant step intent, what happened, and a suggestion without assigning
the user's disposition.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- An operator can tell whether there is no qualified evidence, a result is
  awaiting action, advisory-only, or clean, and can separately see coverage and
  revision qualifiers without reading implementation code.
- A bare-plan medium completeness finding is visibly deferred for
  detail-grounded re-evaluation, not silently treated as absence of work.
- No stage label, stop reason, JSON field, exit guidance, or Jira-grade handoff
  claims a clean verdict for absent, coverage-unconfirmed, legacy-unknown, or
  stale reused audit evidence. An absent, skipped, or pre-capture failed audit
  has `not-sampled` stage, coverage, and revision qualification with a null
  audit revision; a fresh audit is qualified against its own captured inputs.
- Every existing finalization state has exactly one shared headline mapping; no
  reporter makes its own choice between awaiting action, advisory-only, and
  clean, including audit-only runs that have no iterate stop reason and deferred
  findings with different required-action classes; a clean headline has no
  result-bearing finding left. No-qualified-current-evidence wins over every
  stop or halt.
- A final report and sidecar identify the exact plan and grade-selected-detail
  revision plus audit stage the sample read. One grade-aware capture supplies
  both those persisted values and the model's plan/detail payload, including
  every selected detail's path and present/missing/unreadable state. The project remains live context
  for explaining why findings matter; the result does not claim that code,
  prompts, lessons, configuration, or history were frozen. If the plan or
  selected details changed afterward, the immutable record preserves the
  sampled revision and audit-time qualification while a later reader presents a
  separate non-current plan/detail freshness view.
- JSON exposes the documented additive result contract while preserving existing
  consumers' keys and meanings, including its object name, fields, enums, and
  absent/legacy rules. `qualified_result` sidecars use one new schema version
  for final and pre-apply checkpoint forms; version 1–3 sidecars remain
  legacy-readable, and annotation rewrite preserves a version-4 result rather
  than dropping it. A pre-apply checkpoint is explicitly non-final and has no
  qualified result.
- Every completeness-sidecar consumer rejects a checkpoint, stale, legacy,
  coverage-unconfirmed, or malformed sidecar as final or current evidence,
  including default and explicit-id `data-contract-apply` and generic
  saved-review-walk selection. Only a fresh final audit may supply replayable
  findings; convergence remains a historical trend diagnostic.
- Create and every detail-authoring branch either carries a current qualified
  final result or plainly says none exists, offers the correct fresh audit for
  its grade, and never treats an older sidecar as current after authoring changed
  its inputs; a create split proposal names no audit because it produced no
  plan. A completed but unqualified, stale, or checkpoint tail is not current.
- The added reporting flow is selected from deterministic audit facts; changing
  model wording, clusters, roles, or narrative categories cannot alter whether
  the tool applies, defers, re-audits, or reports a result.
- Assistant guidance for an in-scope plan-gap scope decision restates plan and
  relevant-step intent, summarizes what happened, and suggests a next step
  without categorizing the gap or deciding its disposition.
- Existing blocking and automatic-apply decisions are unchanged by this work.

## Deferred

Policy changes belong to #261 only if a new overlapping finding channel is
introduced; #261 is currently closed. Bad-fix provenance (#231) remains
deferred. Generic readiness recommendations remain #262. Any proposal to
change audit thresholds, pass caps, or exit behavior is separate work.
