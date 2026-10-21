> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
kind: plan-convergence-evidence
version: 1
source_plan: concept-signoff-integrations
source_status: completed
assessment: not_reconciled
recommended_action: split_remediation
recommended_plan_count: 3
evidence_backend: codex
---

# Concept Signoff Integrations — Convergence Evidence and Split Recommendation

## Decision

Do not continue repairing `concept-signoff-integrations` as one plan and do not
archive it as reconciled. Preserve it as the implementation history, then create
three remediation plans:

1. `concept-remediation-1-publication-transactions` — one mutation and publication authority
   for plan text and concept records, followed by create and scope-out adoption.
2. `concept-remediation-2-authoring-boundary-hardening` — evidence grounding, mandatory
   structured detail responses, and recoverable detail replacement.
3. `concept-remediation-3-ownership-lifecycle-accounting` — explicit `wont_do` accounting,
   deferral-link conservation across structural remedies, seed restoration, and
   completeness/documentation parity.

The plans should be implemented in the order shown. Plan 2 may be authored and
audited in parallel with plan 1, but any detail-record persistence work in plan 2
must consume the publication API shipped by plan 1. Plan 3 should start only
after that API is stable because it exercises the authority across multiple
lifecycle operations.

This is a split by invariant and failure boundary, not by original step number.
The original plan placed three different kinds of correctness in one convergence
surface: transactional durability, model-output validation, and lifecycle
accounting. A correction to one repeatedly exposed an unstated contract in
another.

## Execution and reconciliation evidence

All model-backed execution and reconciliation used the Codex backend. All ten
steps reached `green`, and the repository test suite subsequently passed with
`5913 passed, 1 skipped`. Passing tests did not establish reconciliation because
the missing cases are primarily negative publication, recovery, and cross-command
lifecycle cases.

The saved per-step reconciliation reports contain:

| Step | Critical | High | Medium | Nit | Interpretation |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 0 | 0 | 0 | 0 | Explicit ownership schema is a stable shipped prerequisite. |
| 2 | 0 | 1 | 1 | Model evidence validation boundary is incomplete. |
| 3 | 1 | 3 | 1 | Create publication is not transactional and lacks durable resume semantics. |
| 4 | 0 | 3 | 1 | Detail authoring mixes response parsing, file replacement, and a missing core mutation API. |
| 5 | 0 | 1 | 1 | Coverage semantics incorrectly treat `wont_do` as self-accounting. |
| 6 | 0 | 0 | 2 | Split conservation implementation is present but negative/dry-run tests are incomplete. |
| 7 | 0 | 0 | 0 | Merge ownership conservation is reconciled. |
| 8 | 0 | 0 | 0 | Re-ground ownership preservation is reconciled. |
| 9 | 0 | 1 | 1 | Scope-out bypasses the shared synchronizer and lacks recovery/refusal coverage. |
| 10 | 0 | 0 | 1 | Documentation edit ownership conflicts with generated CLI-reference boundaries. |

Aggregate result: **1 critical, 9 high, 7 medium, and 1 nit**. The distribution
is more important than the count: steps 1, 7, and 8 are clean, while steps 3 and
4 concentrate publication and boundary failures and steps 5, 6, 9, and 10 expose
lifecycle-accounting tails. Re-running one monolithic repair loop would make the
clean steps part of the prompt and review surface without helping close those
clusters.

Primary reports:

- `reports/20260713-101216-run-reconcile.json` — create transaction, resume,
  unsigned publication, interactivity, and missing end-to-end cases.
- `reports/20260713-101522-run-reconcile.json` — structured detail response,
  replacement recovery, and missing prerequisite mutation APIs.
- `reports/20260713-101714-run-reconcile.json` — `wont_do` accounting semantics.
- `reports/20260713-102114-run-reconcile.json` — scope-out publication authority
  and rollback/refusal tests.
- `reports/20260713-102329-run-reconcile.json` — generated CLI documentation
  ownership.

## Evidence clusters

### Cluster A — publication authority and transaction boundaries

Finding IDs:

- `step3-run-reconcile-f405ee40` — critical: create archives collisions before
  concept synchronization can reject the new state.
- `step3-run-reconcile-7574ef9c` — high: sidecar-only resume and incremental
  review persistence are absent.
- `step3-run-reconcile-80b9cde2` — high: unsigned proposals bypass the canonical
  synchronizer.
- `step3-run-reconcile-9d3324a4` — high: publication-boundary integration cases
  are missing.
- `step4-run-reconcile-5830b0ac` — high redirect: detail needs public deferral
  replacement, review, and synchronization APIs that the core does not expose.
- `step9-run-reconcile-e9b34ca4` — high: scope-out directly saves the concept
  tree instead of using the synchronizer.
- `step9-run-reconcile-2b18c36e` — medium: refusal and rollback cases are absent.

These are one cluster because they all ask the same question: **who may publish
a decision-bearing change, and what is restored if publication fails?** Fixing
each caller locally would create more authorities. The shared contract must land
first, with callers reduced to preparation plus one commit operation.

### Cluster B — untrusted authoring and replacement boundaries

Finding IDs:

- `step2-run-reconcile-ce244a8e` — high: a literal rationale excerpt can ground
  an unrelated invented title.
- `step2-run-reconcile-84957c73` — medium: an unpaired surrogate escapes the
  fail-soft producer boundary.
- `step4-run-reconcile-8ae6c687` — high: detail authoring accepts envelope-free
  Markdown when no concept record exists.
- `step4-run-reconcile-04ac0dba` — high: the old detail is not restored when the
  replacement write fails.
- `step4-run-reconcile-28491d51` and `step4-run-reconcile-a6c41ba8` — missing
  concurrency, deduplication, bounded-regeneration, recovery, dry-run, and
  command-failure cases.

These belong together because the invariant is **untrusted output must become a
validated, recoverable artifact or no artifact change at all**. They do not need
the structural-remedy and completeness context carried by Cluster C.

### Cluster C — explicit accounting across lifecycle transformations

Finding IDs:

- `step5-run-reconcile-69028ee5` — high: approved `wont_do` is treated as
  covered without an explicit structured link.
- `step5-run-reconcile-6b8b7ab0` — medium: completeness parity and multi-concept
  cases are incomplete.
- `step6-run-reconcile-cb54717a` and
  `step6-run-reconcile-be1832fa` — split extra-ID and dry-run conservation cases
  are not pinned.
- The earlier completeness audit's `structural-deferral-links` finding — split
  and merge can invalidate step-linked structured deferrals while preserving
  only `concept_ids`.
- The earlier completeness audit's `forward-seed-ownership-restoration` finding
  — re-ground and scope-out render IDs into seeds, but create does not consume
  those IDs as authoritative restoration input.
- `step10-run-reconcile-d05fb53f` — documentation changes must originate in the
  parser/help source that generates the CLI index.

These are one cluster because the invariant is **every reviewed concept remains
explicitly accounted for after every supported lifecycle transformation**. The
clean merge and re-ground implementations should be treated as fixtures and
regression targets, not reimplemented.

## Recommended remediation plans

### Plan 1 seed — Concept Remediation 1: Publication Transactions

Historical seed: `../../../../plan-seeds/archive/concept-publication-transactions.replaced.md`.

**Problem.** Concept mutations are prepared in several commands, but callers can
write plan text, sidecars, archives, and manifests in different orders. Direct
`save_concepts()` calls bypass synchronization, while the current synchronizer
cannot represent unsigned preservation or detail-deferral replacement. Failure
can therefore leave an archived prior plan, mismatched prose, or lost resume
state.

**Outcome.** Ship one public publication contract that validates a prepared plan
and concept record, stages all affected artifacts, commits them in a declared
order, and restores the full pre-operation snapshot on any failure.

**Owned scope.**

- Define request/result types for signed decisions, unsigned-preserving updates,
  ownership changes, and structured-deferral replacement.
- Separate preparation from publication and make collision archival part of the
  same rollback journal as plan, sidecar, detail, and manifest changes.
- Make create persist scoped review progress as resumable sidecar-only state,
  determine interactivity from terminal/`--yes` state, and publish final signed
  and unsigned records through the shared authority.
- Make scope-out publish its prepared tree and rendered scope through the same
  authority.
- Add failure-injection tests at every publication boundary, including archive,
  plan write, synchronization, sidecar write, detail move, and manifest update.

**Excluded scope.** Evidence/title validation, detail response grammar,
`wont_do` coverage policy, structural ownership algorithms, and documentation
copy.

**Exit evidence.** No production caller directly saves a decision-bearing
concept tree; create collision failure is byte-for-byte non-mutating; unsigned
resume survives interruption; scope-out rollback restores plan, sidecar, and
details; focused and full suites pass; reconcile-code reports no publication
authority redirect.

### Plan 2 seed — Concept Remediation 2: Authoring Boundary Hardening

Historical seed: `../../../../plan-seeds/archive/concept-authoring-boundary-hardening.replaced.md`.

**Problem.** Model output can introduce a title not supported by evidence, can
escape fail-soft handling through invalid Unicode, and can bypass the structured
detail envelope. Detail replacement archives the known-good artifact before the
new artifact is durable and does not restore it on failure.

**Outcome.** Treat concept enrichment and detail generation as untrusted input:
accept only evidence-grounded structured output and replace an existing detail
only through a recoverable operation.

**Owned scope.**

- Require evidence support for the proposed concept claim/title, not merely a
  rationale substring; define conservative normalization and rejection rules.
- Enclose parsing, normalization, ID derivation, and merging in the fail-soft
  producer boundary, including malformed Unicode.
- Require the structured detail response for newly authored output regardless
  of whether a concept sidecar currently exists; retain legacy parsing only for
  explicitly identified pre-feature checkpoints if compatibility is required.
- Restore the previous detail after any replacement-write failure.
- Add concurrent sibling, multi-concept deduplication, bounded regeneration,
  persistence failure, command-failure, and dry-run tests.

**Excluded scope.** Shared concept publication implementation belongs to Plan 1;
this plan consumes that API for deferral persistence. Coverage and structural
accounting belong to Plan 3.

**Exit evidence.** Invented titles, malformed Unicode, malformed envelopes, and
replacement write failures are non-mutating; no new envelope-free detail can be
authored; recovery and concurrency tests pass; reconcile-code has no authoring
boundary finding.

### Plan 3 seed — Concept Remediation 3: Ownership Lifecycle Accounting

Historical seed: `../../../../plan-seeds/archive/concept-ownership-lifecycle-accounting.replaced.md`.

**Problem.** Exact `concept_ids` survive several transformations, but the system
does not consistently preserve the structured accounting link that explains why
a concept has no active owner. `wont_do` passes completeness without that link,
step-linked deferrals can become stale after split/merge, and ownership rendered
into a forward or re-baseline seed is not restored authoritatively by create.

**Outcome.** Define and test a conservation law for both active ownership and
structured non-delivery accounting across create, split, merge, re-ground, and
scope-out.

**Owned scope.**

- Define which structured record accounts for `defer` and `wont_do`; a decision
  value alone must not suppress completeness.
- Give deferral links stable identity or explicitly remap them when steps split,
  merge, disappear, or are regenerated.
- Make create consume machine-readable ownership/restoration metadata from
  re-baseline and forward seeds, with conflict detection against the signed
  concept record.
- Complete split extra-ID/dry-run tests and add end-to-end lifecycle conservation
  cases using the already-clean merge and re-ground behavior as fixtures.
- Update parser/help sources first, regenerate the CLI reference, and document
  explicit-link coverage and non-apply-eligible ownership-gap routing.

**Excluded scope.** Publication mechanics and rollback belong to Plan 1. Model
response validation and detail file replacement belong to Plan 2.

**Exit evidence.** For every reviewed concept, each lifecycle operation leaves
either at least one exact committed owner or one valid structured non-delivery
record; no link references a removed/wrong step; seed round trips restore exact
IDs without inference; generated documentation is drift-free; reconcile-code is
clean for the lifecycle matrix.

## Dependency and overlap rules

```text
concept-remediation-1-publication-transactions
          |
          +----------> concept-remediation-3-ownership-lifecycle-accounting
          |
          +----------> detail persistence tail of
                       concept-remediation-2-authoring-boundary-hardening

concept-remediation-2-authoring-boundary-hardening
          (evidence and parsing work can begin independently)
```

File overlap is not itself a reason to merge plans. `create.py` appears in Plans
1 and 3, and `detail.py` appears in Plans 1, 2, and 3, but each plan must touch a
different named contract:

- Plan 1 owns mutation/publication calls and rollback.
- Plan 2 owns untrusted-output parsing and artifact replacement.
- Plan 3 owns ownership/deferral transformations and their conservation tests.

If a proposed step crosses two of those contracts, split the step or make the
earlier contract an explicit prerequisite. Do not let a downstream plan invent a
local substitute for a missing prerequisite API; that condition is a redirect.

## Reusable split pattern for plan-tool

This case suggests a tool-facing pattern that can guide a user when a plan does
not converge.

### Signals that should trigger a split recommendation

1. A post-run reconcile contains a critical finding and high findings in at
   least two different invariant classes.
2. Two or more findings say callers bypass or locally recreate the same claimed
   authority.
3. A detail receives a redirect because its prerequisite does not expose the API
   the detail assumes.
4. Some steps reconcile cleanly while a small subset repeatedly concentrates
   findings; clean steps should be frozen instead of returned to the audit loop.
5. The full test suite passes while reconciliation still identifies missing
   negative or cross-command cases; this is evidence of an incomplete test
   matrix, not convergence.
6. Findings form clusters with different rollback boundaries or different
   sources of truth. Those clusters should not share a plan merely because they
   touch the same file.

### Suggested clustering inputs

For every finding, record:

- stable finding ID and source report;
- severity and whether it is a redirect;
- named invariant or source of truth;
- mutation boundary and artifacts that can change;
- owning public API, or `missing` when the redirect identifies one;
- production files and test matrix;
- prerequisite and downstream consumers;
- whether the finding recurred, changed class, or appeared after remediation.

Cluster primarily by `(invariant, mutation boundary, authority)`, then use file
overlap only as a scheduling constraint. A useful candidate plan has one primary
invariant, one declared authority, a bounded failure matrix, and an exit condition
that can be reconciled independently.

### User-facing recommendation shape

When the tool detects this pattern, it should present:

1. **Why the current plan is not converging** — finding trajectory and recurring
   invariant conflicts, not only the latest count.
2. **Frozen work** — steps already reconciled that the split will consume rather
   than recreate.
3. **Candidate plans** — name, invariant, owned scope, exclusions, dependencies,
   evidence IDs, and independent exit criteria.
4. **Overlap warning** — files shared between candidates and the distinct
   contracts each candidate may edit.
5. **Seed-ready blocks** — Problem, Outcome, Owned scope, Excluded scope, and Exit
   evidence, as supplied above.
6. **Confirmation request** — allow the user to merge, rename, or reorder the
   candidates before plan creation.

### Convergence rule after splitting

Audit each candidate independently. Treat it as ready only when:

- no critical or high conceptual-correctness finding remains;
- no redirect remains;
- the candidate's named failure matrix is represented by tests;
- the latest two audit passes produce the same low-yield result, or every pass is
  low-yield, under the repository's documented low-yield convergence rule;
- `reconcile-code` confirms the shipped contract rather than discovering a new
  local authority; and
- validation, focused tests, the full suite, and generated-artifact drift checks
  pass as applicable.

The low-yield rule controls when to stop sampling a nondeterministic audit. It
does not override a known critical/high finding or redirect. A stable bad result
is converged evidence that the plan needs restructuring, not evidence that the
plan is ready to run.
