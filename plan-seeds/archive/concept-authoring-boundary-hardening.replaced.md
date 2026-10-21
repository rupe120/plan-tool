> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-authoring-boundary-hardening.md`.
> Preserved here for history; do not edit.

# Plan seed: Concept Authoring Boundary Hardening

This file is a `plan-tool create` input. Use the Codex backend. It may be authored
and audited while `concept-publication-transactions` is underway, but its detail
deferral persistence must consume that plan's public publication contract rather
than introduce another local save path.

Evidence source:
`docs/implementation-plans/plan-details/concept-signoff-integrations/convergence-evidence-and-split-recommendation.md`.

## Overview

Harden the two model-authored boundaries in the concept workflow. Concept
enrichment must accept only claims grounded in supplied evidence and must fail
softly for every invalid model output, including malformed Unicode that fails
during normalization or ID derivation. Detail generation must require the
structured response envelope for all newly authored output and must replace an
existing detail through a recoverable operation that never loses the prior body.

This plan owns validation, parsing, bounded regeneration, and detail artifact
replacement. It does not own multi-artifact concept publication, coverage policy,
or structural ownership transformations.

## Problem statement

The completed integration accepts output that satisfies the shape of a contract
without satisfying its meaning:

- `_parse_emitted_concepts()` checks that `evidence_rationale` is a literal
  excerpt, but it does not require the proposed title/claim to be supported by
  that evidence. A title such as “Quantum mechanics” can be accepted when both
  evidence and rationale contain only “cats.”
- JSON can contain an unpaired surrogate. The parser accepts it, then later ID
  derivation raises `UnicodeEncodeError` outside the producer's fail-soft
  boundary.
- `_author_step_detail()` falls back to legacy Markdown parsing when no concept
  tree is loaded, even though newly authored responses are required to use the
  structured envelope.
- Detail replacement archives the current file before writing the new body. If
  the write fails, the active path disappears and the prior body is not restored.
- The intended serial/concurrent regeneration contract lacks tests for sibling
  preservation, deduplication, bounded retries, persistence failure, dry-run,
  and command failure.

The shared invariant is: **untrusted model output either becomes a validated,
recoverably published artifact or causes no artifact change.**

## Reconciliation evidence to close

- `step2-run-reconcile-ce244a8e` — invented title accepted through an unrelated
  literal rationale excerpt.
- `step2-run-reconcile-84957c73` — malformed Unicode escapes fail-soft handling.
- `step4-run-reconcile-8ae6c687` — envelope-free Markdown fallback for newly
  authored detail.
- `step4-run-reconcile-04ac0dba` — missing restoration after replacement failure.
- `step4-run-reconcile-28491d51` — missing concurrency, deduplication,
  bounded-regeneration, persistence, and recovery cases.
- `step4-run-reconcile-a6c41ba8` — missing command-failure and dry-run concept
  state cases.

The missing publication API identified by `step4-run-reconcile-5830b0ac` belongs
to `concept-publication-transactions`; this plan must consume it and must not
close the redirect with a second local schema or direct save.

## Architectural contract

### Evidence-backed concept claims

Define “grounded” conservatively and deterministically. The model response must
carry evidence sufficient to support the proposed concept claim/title, not just
an arbitrary excerpt. Prefer a response field that quotes a bounded evidence
span plus a claim/title whose normalized meaningful tokens are demonstrably
present in or tied to that span. If purely lexical validation cannot establish
support, reject the candidate rather than invoking a second model judge or
accepting fluent rationale.

The prompt and parser must agree on the rule. Bound title, rationale/span,
hierarchy depth, breadth, and total output size. Reject duplicate keys, unknown
fields, invalid suggested states, empty/whitespace claims, control characters,
and invalid Unicode. Preserve deterministic concepts when every enriched
candidate is rejected.

### Total fail-soft producer boundary

The fail-soft boundary begins before invocation and ends after normalization,
ID/source-key derivation, candidate construction, and merge into a deep copy.
Any exception caused by backend output returns the documented no-enrichment
result and leaves the input tree unchanged. Do not broadly suppress programmer or
filesystem errors outside the untrusted-output path; keep the exception boundary
narrow enough that genuine defects remain visible.

### Structured detail protocol

Every newly invoked detail response uses the structured response parser whether
or not a concept sidecar currently exists. The envelope must distinguish the
detail body from structured deferral candidates and make prose/candidate parity
validatable. A missing sidecar means there may be no known concept IDs; it does
not turn off the response grammar.

If compatibility requires legacy checkpoints, recognize them through explicit
checkpoint version/provenance, not by silently trying the permissive parser after
structured parsing fails. Fresh malformed output follows the existing bounded
reprompt policy and then fails without replacing an artifact.

### Recoverable detail replacement

Render and validate the new body before moving the old file. Replace with an
operation whose journal records the old path/archive destination and restores
the old active body when any new write or post-write validation fails. Do not
describe a best-effort archive as recovery. If restoration fails, surface a
distinct error and preserve the recoverable archive path in the diagnostic.

The detail file replacement is local to this plan. Persistence of deferral
record changes must call the publication API from
`concept-publication-transactions`.

### Bounded regeneration

When post-authoring review changes a candidate to include, deduplicate affected
steps and regenerate each step a bounded number of times. A worker may return
body/candidates but cannot mutate shared concept state. The serial parent merges
candidates and publishes through the shared authority after all required bodies
validate. Repeated contradictory output stops with an actionable unresolved
candidate report and retains the last known-good artifacts.

## Proposed implementation sequence

### 1. Tighten the evidence response contract and prompt

Files likely involved:

- `plan_tool/prompts/concept-emit.md`
- `plan_tool/concept_tree.py`
- `tests/test_concept_emit.py`

Define the evidence-span/claim relationship, validate all fields and limits, and
reject unrelated titles even when a rationale substring is literal. Add cases
for punctuation/case normalization, repeated terms, nested candidates, duplicate
keys, unknown fields, unsupported state, over-limit output, and mixed valid and
invalid candidates. Choose and document whether one invalid node rejects the
whole response or only that candidate; ensure hierarchy cannot retain a child of
a rejected parent accidentally.

### 2. Make enrichment fail-soft through construction and merge

Files likely involved:

- `plan_tool/concept_tree.py`
- `tests/test_concept_emit.py`
- `TESTING.md`

Bring normalization, encoding, ID/source-key derivation, deep-copy mutation, and
merge inside the backend-output exception boundary. Test unpaired surrogates in
titles, evidence spans, rationale, and parent paths. Assert the original tree is
byte-for-byte unchanged and that injected backend failures remain isolated.

### 3. Require structured detail responses for fresh authoring

Files likely involved:

- `plan_tool/prompts/detail.md`
- `plan_tool/detail.py`
- checkpoint metadata if explicit legacy recognition is required
- `tests/test_detail.py`

Remove the no-concept-tree permissive fallback for fresh responses. Keep serial,
parallel, resumed, and reprompted paths on the same grammar. Validate parity
between deferred/out-of-scope prose and structured candidates, including the
empty-candidate case. If legacy checkpoint support remains, pin its version gate
and ensure malformed fresh output cannot enter that branch.

### 4. Make detail replacement recoverable

Files likely involved:

- `plan_tool/detail.py`
- `tests/test_detail.py`

Replace `_archive_existing_detail()`'s best-effort overwrite sequence with a
recoverable active-file replacement. Inject failures at archive creation, move,
new write, post-write validation, and restoration. Assert active and archived
paths and exact bytes. Preserve the existing canonical active filename used by
plan pointers and downstream tools.

### 5. Pin serial/concurrent regeneration and CLI behavior

Files likely involved:

- `plan_tool/detail.py`
- `plan_tool/cli/authoring.py`
- `tests/test_detail.py`
- `tests/cli/test_authoring_cmds.py`

Add tests for concurrent sibling candidate preservation, multi-concept
deduplication, bounded regeneration, shared-record publication failure, dry-run,
command failure, and repeated contradiction. Verify workers never persist the
concept record and a failed sibling cannot cause successful siblings to publish
inconsistent shared state.

## Out of scope

- Create collision transactions, sidecar-only resume, manifest recovery, and
  scope-out publication.
- Defining or implementing the canonical concept publisher; consume the public
  contract from `concept-publication-transactions`.
- `wont_do` completeness semantics and structural deferral-link remapping.
- Using a second model call to judge whether the first model's claim is grounded.
- Rewriting old detail files solely to add envelopes.
- General-purpose filesystem transactions outside detail artifact replacement.

## Risks and controls

- **Grounding heuristic too strict:** prefer false-negative enrichment because
  deterministic seeds remain; document normalization and test real evidence
  phrases.
- **Grounding heuristic too permissive:** require a claim-to-span relationship,
  not merely any shared stop word or literal rationale.
- **Compatibility fallback reopens the hole:** gate legacy parsing on explicit
  persisted provenance and never on absence of a sidecar.
- **Broad exception swallowing hides bugs:** catch only errors attributable to
  invocation/output processing and test that unrelated programmer errors surface.
- **Regeneration loop:** cap attempts, deduplicate by step, and preserve known-good
  artifacts on exhaustion.
- **Parallel state races:** workers return immutable outcomes; only the serial
  parent merges and publishes.

## Testing matrix

- Grounded and ungrounded titles with the same rationale excerpt.
- Stop-word-only overlap, punctuation/case variants, nested hierarchy, duplicate
  siblings, bounds, unknown/duplicate fields, and invalid states.
- Unpaired surrogates and other encoding failures in every model-controlled
  string position; original-tree immutability.
- Fresh detail with and without a concept record, resumed fresh-format checkpoint,
  explicitly recognized legacy checkpoint, malformed envelope, prose/candidate
  mismatch, and bounded reprompt exhaustion.
- Replacement failure before/after archive, during write, during validation, and
  during restoration.
- Serial and parallel candidate collection, sibling preservation, deduplication,
  bounded include regeneration, contradictory regenerated prose, publisher
  failure, dry-run, and CLI command failure.

## Acceptance criteria

- A concept title/claim unsupported by its cited evidence span is rejected even
  when its rationale contains a literal evidence excerpt.
- Every invalid model-controlled Unicode value is fail-soft and leaves the input
  tree unchanged.
- Fresh detail authoring always requires the structured response envelope,
  independent of sidecar presence and job count.
- Legacy parsing, if retained, is reachable only through explicit persisted
  provenance and cannot accept malformed fresh output.
- A failed detail replacement leaves the prior body active byte-for-byte, or
  reports a distinct restoration failure and the recoverable archive location.
- Include-triggered regeneration is deduplicated and bounded; workers never write
  shared concept state.
- Deferral persistence uses the publication contract from
  `concept-publication-transactions` rather than a local schema/save path.
- Focused tests, the full suite, prompt/data-contract drift checks, and
  `reconcile-code` pass with no authoring-boundary finding.

## Deferred

- Publication transaction mechanics are owned by
  `concept-publication-transactions`.
- Coverage and lifecycle conservation are owned by
  `concept-ownership-lifecycle-accounting`.

