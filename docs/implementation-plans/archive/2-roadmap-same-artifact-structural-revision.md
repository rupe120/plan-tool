> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Same Artifact Structural Revision
intent: '`plan-tool roadmap` will turn one current structural-escalation receipt and
  its selected open feedback row into a reviewable rewrite of exactly one canonical
  roadmap artifact. The rewrite changes only explicitly allowed fields of existing
  rows and the contents of already-delimited prose regions. It preserves every row
  identity, relation, decision, collection order, unselected feedback row, and every
  other canonical artifact, then publishes only the selected artifact and its proposed
  feedback response after a candidate proof and final snapshot check.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Share the full-roadmap gate check with candidate proofs
  intent: Make current-state capture and candidate proof use exactly one full-roadmap
    gate rule.
  files:
  - plan_tool/roadmap_impact_snapshot.py
  - tests/test_roadmap_impact_snapshot.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-same-artifact-structural-revision/01-share-full-roadmap-gate-check-candidate.md
  status: done
- id: 2
  title: Bind current receipt and impact evidence without treating the route as write
    authority
  intent: Ensure rewrite work starts only from one exact current receipt-analysis
    pair, its complete immutable evidence and full-snapshot binding, one open row-targeted
    feedback item with a nonblank reviewer request, and the selected artifact slice.
  files:
  - plan_tool/roadmap_evidence_store.py
  - tests/test_roadmap_evidence_store.py
  creates:
  - plan_tool/roadmap_structural_revision.py
  - tests/test_roadmap_structural_revision.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-same-artifact-structural-revision/02-bind-current-receipt-impact-evidence.md
  status: done
- id: 3
  title: Define finite row-field and existing prose-region rewrite operations
  intent: Constrain backend output to uniquely targeted existing-row scalar spans
    and pre-marked prose interiors that cannot express new identities, relations,
    decisions, rows, or files.
  creates:
  - plan_tool/roadmap_structural_operations.py
  - tests/test_roadmap_structural_operations.py
  allowed_mentions:
  - plan_tool/roadmap_structural_revision.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Supplies the selected artifact, feedback identity, and bounded row context
      against which every operation is validated.
  detail: docs/implementation-plans/plan-details/roadmap-same-artifact-structural-revision/03-define-finite-row-field-existing-prose.md
  status: done
- id: 4
  title: Merge allowed rewrites and update only the selected feedback response
  intent: Build one candidate by splicing only permitted source spans, including the
    selected response-key insertion, while preserving all other bytes and reviewer-owned
    feedback.
  creates:
  - plan_tool/roadmap_structural_revision_patch.py
  - tests/test_roadmap_structural_revision_patch.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: Supplies the canonical predecessor and the one feedback row allowed to change.
    3: Supplies the validated row-field, prose-region, and response operations.
  detail: docs/implementation-plans/plan-details/roadmap-same-artifact-structural-revision/04-merge-allowed-rewrites-update-only.md
  status: done
- id: 5
  title: Prove row, relation, decision, order, feedback, and full-snapshot gate invariants
  intent: Prove every declared structural and complete gate-input invariant before
    publication while leaving semantic effect assessment to the selected feedback
    review.
  creates:
  - plan_tool/roadmap_structural_revision_proof.py
  - tests/test_roadmap_structural_revision_proof.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  - 4
  depends_on_notes:
    1: Supplies the same full-roadmap gate traversal used by current impact snapshots.
    2: Supplies the captured full-roadmap evidence and selected predecessor.
    4: Supplies the completed candidate to compare and substitute into every stage
      context.
  detail: docs/implementation-plans/plan-details/roadmap-same-artifact-structural-revision/05-prove-row-relation-decision-order.md
  status: done
- id: 6
  title: Bind publication to the proof and complete final snapshot, preserve lock-byte
    initialization and seed invalidation, and narrow atomic replacement to the matched
    artifact
  intent: Prevent an unproved candidate or one stale in any proof input from reaching
    the final guarded replacement boundary.
  files:
  - plan_tool/fileio.py
  - plan_tool/roadmap_revision_publish.py
  - tests/test_fileio.py
  - tests/test_roadmap_revision_publish.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 5
  depends_on_notes:
    2: Supplies the source and evidence digest binding that must still match immediately
      before replacement.
    5: Supplies the successful candidate proof required before publication.
  detail: docs/implementation-plans/plan-details/roadmap-same-artifact-structural-revision/06-bind-publication-proof-complete-final.md
  status: done
- id: 7
  title: Add closed redacted rewrite preflight and terminal events while preserving
    atomic run-log replacement and guarded temporary and in-flight cleanup
  intent: Make every rewrite preflight and terminal outcome diagnosable without persisting
    feedback text, roadmap prose, prompts, or backend replies.
  files:
  - plan_tool/run_log.py
  - plan_tool/data_contract.py
  - tests/test_run_log.py
  - DATA_CONTRACT.md
  - tests/test_data_contract.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: Supplies the closed evidence identities and preflight verdicts recorded by
      the lifecycle.
    3: Supplies the operation and rejection vocabulary summarized by attempt events.
  detail: docs/implementation-plans/plan-details/roadmap-same-artifact-structural-revision/07-closed-redacted-rewrite-preflight.md
  status: done
- id: 8
  title: Run one bounded exact-envelope rewrite with preserved seed invalidation and
    snapshot-checked single-artifact replacement
  intent: Carry one exact-evidence, row-targeted request through one bounded backend
    call only when its reviewer request is nonblank, then to a proved and complete-snapshot-checked
    publication.
  files:
  - TESTING.md
  - docs/CODEX_CLI_CONTRACT.md
  - plan_tool/backend.py
  - plan_tool/backend_runner.py
  - plan_tool/shell.py
  - tests/test_backend.py
  - tests/test_backend_config.py
  - tests/test_backend_runner.py
  - tests/test_shell.py
  creates:
  - plan_tool/roadmap_structural_revision_run.py
  - plan_tool/prompts/roadmap-structural-feedback-revision.md
  - tests/test_roadmap_structural_revision_run.py
  allowed_mentions:
  - plan_tool/roadmap_structural_revision.py
  complexity: high
  change_type: feature
  depends_on:
  - 4
  - 5
  - 6
  - 7
  depends_on_notes:
    4: Supplies deterministic candidate construction and the selected-feedback-only
      transition.
    5: Supplies the preservation and full-roadmap proof.
    6: Supplies the proof-bound final publication boundary and snapshot refusal.
    7: Supplies the redacted preflight, attempt, and terminal event contract.
  detail: docs/implementation-plans/plan-details/roadmap-same-artifact-structural-revision/08-run-one-bounded-exact-envelope-rewrite.md
  status: done
- id: 9
  title: Wire an explicit exact-pair structural rewrite command with no local or broad
    fallback
  intent: Require operators to name the immutable receipt-analysis pair for one row-targeted
    rewrite and its one-artifact write set without inferred evidence or mode widening.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/cli/__init__.py
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/package_surface_help.golden.txt
  - docs/cli/roadmap.md
  complexity: high
  change_type: feature
  depends_on:
  - 8
  depends_on_notes:
    8: Supplies the typed runner result, backend seam, write-set facts, and exit-code
      outcomes.
  detail: docs/implementation-plans/plan-details/roadmap-same-artifact-structural-revision/09-wire-explicit-exact-pair-structural.md
  status: done
- id: 10
  title: Document local, exact-pair rewrite-only, evidence, generic, transaction,
    and broad roadmap paths
  intent: Help operators choose the correct roadmap path and understand the rewrite's
    exact source spans, review boundary, and exclusions.
  files:
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_format.py
  - README.md
  - CLAUDE.md
  - CAPABILITIES.md
  - docs/ARCHITECTURE.md
  - docs/ROADMAP_WALKTHROUGH.md
  - RUNBOOK.md
  - integrations/claude/SKILL.md
  complexity: high
  change_type: non-code
  depends_on:
  - 3
  - 5
  - 7
  - 9
  depends_on_notes:
    3: Supplies the landed field allowlists, operation schema, and prose-region grammar.
    5: Supplies the final preservation and downstream-proof contract.
    7: Supplies the landed lifecycle and redaction vocabulary.
    9: Supplies the final command form, conflict rules, output, and result behavior.
  detail: docs/implementation-plans/plan-details/roadmap-same-artifact-structural-revision/10-document-local-exact-pair-rewrite-only.md
  status: done
---
# Roadmap Same Artifact Structural Revision

## Overview

This is the safe one-artifact structural path for a request whose answer is a
rewrite, not a new or rewired design element. It remains an exclusive command:
it never starts broad stage re-entry and never promotes itself into a
cross-artifact writer.

## Problem statement

The existing local revision path is intentionally limited to one allowlisted
presentation-field change. A whole-artifact or coordinated existing-row rewrite
needs bounded prose and structured replacements, but a generic structural
operation language would also need to decide whether a candidate creates
downstream obligations. Current static impact routing cannot make that decision
for a candidate that preserves identity: `roadmap_impact_snapshot._require_current_gates`,
`resolve_impact_closure`, and `check_entity_component_coverage` correctly make
a gate-valid Domain artifact appear cross-artifact even when a candidate only
rewrites existing content.

## Architecture

One current receipt record and one current impact-analysis record are required
preflight evidence. The requested receipt's immutable final name must equal the
analysis's embedded `receipt.final_name`; the runner captures the raw digest of
each named immutable final; and both records must revalidate against the same
current source and selected open feedback row. The feedback target must be
`row`, with exactly one live target row and a nonblank `request`; artifact-targeted
or blank-request feedback refuses. Invalid, stale, mismatched, unavailable, or
`requires-scope-review` evidence refuses before seed invalidation or backend contact.
A `same-artifact` or
`cross-artifact` static route may proceed only to candidate construction; route
class is evidence, not candidate-write authority.

The structural runner uses one fixed, independently verified V1 evaluator, not
the active effective backend. On macOS it launches `codex exec --json -C
ISOLATED_EMPTY_DIR -s read-only --skip-git-repo-check --ephemeral
--ignore-user-config --ignore-rules PROMPT` as a child of a generated
`/usr/bin/sandbox-exec` Seatbelt profile. The outer profile denies both file
data and metadata reads below the resolved repository and plans roots, while
the fresh non-repository `ISOLATED_EMPTY_DIR` supplies the evaluator's working
root. Thus the no-read property does not rest on `-C` or Codex's internal
read-only mode. `--ignore-user-config` and `--ignore-rules` prevent user
configuration and user or project execpolicy rules from altering the evaluator;
authentication remains the CLI's own concern. The profile is usable only when
the local `codex --version` exactly matches the captured structural-runtime
contract and a sanitized capability probe verifies the JSON terminal envelope,
read-only write denial, and denial of a workspace-only read. V1 supports only
that verified macOS host-isolation provider: on another platform, a missing
provider, a profile-generation failure, or a failed read-denial probe, it
refuses before evidence load or seed invalidation. Active backend selection,
fallback selection, and all project `extra_batch_argv` and
`extra_streaming_argv` are irrelevant to this command: they cannot select or
alter the fixed evaluator. The runner must not derive its profile through
`build_effective_backend` or `codex sandbox` configuration.

The sole accepted V1 reply is a duplicate-member-free strict JSON object with
exactly `version`, `operations`, and `feedback_response` keys. `version` is the
native JSON integer `1`, never a string or another value; every other version
or type refuses. `operations` is a nonempty array of strict discriminated
objects: a `row-field` object has exactly `kind`, `collection`, `row_id`,
`field`, and string `value`; a `prose-region` object has exactly `kind`,
`region_id`, and string `value`. A row-field value contains no CR or LF and is
is nonblank with no surrounding whitespace, and is admitted only when the current renderer's YAML options produce exactly one
physical scalar line for that field. The accepted operation retains the
renderer-derived scalar fragment, and the merger splices that fragment rather
than the raw JSON value; the merged candidate must parse and render back to the
exact candidate bytes. A prose-region value cannot introduce,
remove, or alter any delimiter line. A row operation may replace only one
allowlisted text field on the selected feedback target row: `entities.name`,
`business_rules.statement`, `workflows.name`, `constraints.statement`,
`system_patterns.name` or `.statement`, `component_patterns.name` or
`.statement`, `components.name`, `plans.title` or `.sizing_rationale`, or
`assumptions.statement`. No operation may change `decisions`, including
`decisions.rationale`, or any `dispositions` field; rationale-only work uses
the existing local-revision path. A target field and a prose region may each
occur only once in an envelope,
the envelope contains at most one prose operation, and `feedback_response` is
exactly one nonblank JSON string for the selected feedback row.

A prose operation may replace one interior bounded by the pre-existing markers
`<!-- plan-tool:rewrite-region id="<id>">` and
`<!-- /plan-tool:rewrite-region -->`, where `<id>` matches
`[a-z][a-z0-9-]{0,63}`. Each delimiter occupies an otherwise whitespace-only
body line; regions cannot nest; and a marker id must occur once. The interior
starts after the opening delimiter line and ends before the closing delimiter
line. A region is full-body, and refuses, unless the body prefix before the
opening delimiter or the suffix after the closing delimiter contains at least
one non-whitespace byte. V1 creates no marker, migrates no artifact, and
changes no stage generator: a markerless artifact simply refuses a prose
operation. The merger changes only uniquely located, single-line YAML scalar
spans in the renderer's canonical block-style row mapping for the selected row,
the selected feedback's `state: open` scalar, one zero-width insertion point
immediately after that state line, and the interior of one eligible region.
`feedback_response` contains no CR or LF and is admitted only when rendering
`{"proposed_response": feedback_response}` with the current renderer's YAML
options produces exactly one physical `proposed_response: <scalar>` line. The
merger replaces the state scalar with `awaiting-review` and inserts that one
generated line at the permitted insertion point; every other response encoding
refuses. The locator keys each row span by its collection, existing id, and
field; it refuses block scalars, flow collections, aliases, tags, and any
source form that yields zero or multiple spans. The candidate marker inventory,
including ids, delimiter bytes, and nesting validity, must equal the
predecessor's. It also rejects an unknown or
duplicate target, identity or relation change, new or removed row,
collection-order change, decision mutation, unselected-feedback mutation,
absent/ambiguous/full-body region, or any operation outside the selected
artifact. It preserves marker delimiters and every source byte outside those
permitted spans; it never re-renders the whole artifact.

Before publication, a candidate-versus-predecessor proof establishes that the
selected artifact's row-id inventory, relation inventory, decisions, collection
orders, and all non-selected feedback are unchanged, then substitutes the
candidate into the captured full-roadmap gate context. The binding for that
proof includes the exact receipt-final and analysis-final names and raw digests,
plus `RoadmapImpactSnapshot._binding`: the recorded-source digest, recorded
brief digest, ordered stage keys, and raw digest of every staged artifact. That
proof establishes only these declared structural and gate invariants; it does
not claim to decide whether changed statement or prose meaning creates a
semantic downstream obligation. The selected feedback response remains in
`awaiting-review` for that human assessment.

The runner holds one participating-writer token continuously while it reloads
the exact evidence finals, recaptures the complete current snapshot, compares
every proof-binding member, and atomically replaces the selected artifact with
the proved candidate's exact UTF-8 bytes through a binary replacement path,
with no intervening unlock. A changed unselected artifact, selected
artifact, recorded source, brief, receipt final, analysis final, or current-gate
failure therefore refuses before replacement. This coordinates only `plan-tool`
writers that honor the guard; it cannot prevent or recover an external manual
edit that races after the comparison. Existing conservative seed invalidation
and atomic single-artifact publication remain in force; a failed attempt leaves
canonical bytes unchanged and may leave only the existing stale derived-state
result.

The only command form is `plan-tool roadmap <slug> --rewrite-structural
RECEIPT_FINAL --rewrite-analysis ANALYSIS_FINAL`. Each final name is required
exactly once, is compared as the explicit immutable evidence identity, and
accepts no companion roadmap mode. A missing, repeated, mismatched, or
unavailable pair refuses before evidence selection, seed invalidation, or
backend contact. The command never infers either final from a selector, a
current record, a directory scan, timestamp, or static route.

Before evidence load or writer-guard acquisition, the runner validates the
exclusive command shape and each supplied final as a 64-character lowercase-hex
identity, then validates the fixed evaluator's captured runtime contract.
Malformed, mixed, or incomplete command forms emit `mode-rejected`; a missing,
malformed, or version-mismatched evaluator, unavailable host-isolation provider,
or failed workspace-read denial emits `evaluator-rejected`. Both are fact-free,
retain no raw supplied value, and have no attempt event. Each
remaining invocation emits one redacted
`roadmap_structural_revision_preflight` event with only receipt/analysis final
names, selected artifact/feedback/target ids, an optional complete-binding
digest, render-canonical fact, and one closed verdict: `accepted`,
`mode-rejected`, `evaluator-rejected`, `evidence-rejected`,
`feedback-rejected`, `render-canonical-rejected`, or `interrupted`. A rejected
or interrupted preflight ends
there. An accepted preflight emits exactly one terminal
`roadmap_structural_revision_attempt` event with attempt `1`, binding digest,
seed-invalidation count, operation (`not-reached`/`accepted`/`rejected`), merge
(`not-reached`/`accepted`/`rejected`), proof
(`not-reached`/`structural-rejected`/`gate-rejected`/`accepted`), final snapshot
(`not-reached`/`current`/`stale`), and publication
(`not-reached`/`published`/`failed`/`unknown-after-interrupt`) facts, and one
closed outcome: `seed-invalidation-failed`,
`invoke-failed`, `empty-reply`, `envelope-rejected`, `merge-rejected`,
`proof-rejected`, `final-snapshot-stale`, `publication-failed`, `published`,
or `interrupted`. Phase facts are monotonic: a phase is `not-reached` after an
earlier rejection or interruption, and each later reached phase requires the
preceding one to be `accepted` or `current` as applicable. These events,
standard run boundaries, and the CLI summary contain no feedback text, roadmap
prose, prompt, or backend reply.

Each accepted reply contains exactly one response for the selected open
feedback row. Publication may move only that row to `awaiting-review` with a
proposed response. No semantic-review conclusion is inferred from a successful
structural proof.

## References

- [Pydantic Configuration](https://docs.pydantic.dev/latest/api/config/) — Covers strict, immutable models and forbidden extra fields for the closed rewrite envelope.
- [Pydantic Discriminated Unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions) — Explains tagged unions for validating the finite set of permitted rewrite operations.
- [Python json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html#json.load) — Documents object_pairs_hook and strict parsing controls needed to reject duplicate envelope members.
- [RFC 8259 — The JavaScript Object Notation Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html#section-4) — Defines JSON object-member semantics and the interoperability requirement for unique member names.
- [Python os.replace](https://docs.python.org/3.13/library/os.html#os.replace) — Documents replacement semantics used to publish one artifact atomically without partial canonical writes.
- [Python fcntl.flock](https://docs.python.org/3.13/library/fcntl.html#fcntl.flock) — Documents shared and exclusive file locking for the participating-writer guard around final rechecks and publication.
- [Python hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html#hashlib.file_digest) — Covers deterministic file digests for detecting source or evidence changes before publication.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Row creation, removal, reordering, ID changes, relation rewiring, decision
  changes (including `decisions.rationale`), prose-region creation, marker
  migration, stage-generator marker emission, or a generic typed patch language.
- A candidate-aware impact subsystem capable of classifying additions or other
  changed semantic downstream obligations; record that later work in BACKLOG
  #289 when a real request demonstrates it.
- Writing another canonical artifact, journaled multi-file recovery, broad
  `--from-stage` authoring, automatic escalation, or a generic document editor.
- Changes to canonical roadmap schemas, seed materialization semantics, or
  unrelated revision modes merely to unify implementation; local revision
  remains the path for decision-rationale edits.
- Linux, Windows, or another macOS evaluator-isolation provider. V1 refuses on
  every host without the verified macOS Seatbelt boundary rather than weakening
  the no-workspace-read invariant; a later provider needs its own capability
  evidence and plan.

## Risks

- **Static-route overreach:** treating a route as a candidate proof would
  reject safe rewrites or admit a widening change. Exact evidence binding plus
  structural/gate proof, not static route class, determine publication.
- **Manual-write race:** a participating-writer guard coordinates only writers
  that honor it. The final guarded comparison refuses an observed mismatch but
  cannot preserve an external edit that races after comparison and before
  replacement.
- **Evaluator workspace reachability:** `-C` and a read-only tool policy do
  not alone prevent absolute-path reads. The outer host boundary denies all
  reads below canonical repository and plans roots and V1 refuses when that
  boundary cannot be verified.
- **Hidden structural change:** a field replacement could change identity,
  relations, ordering, or a protected feedback fact. The closed allowlists,
  source-span merger, and candidate/predecessor proof reject it before
  publication; semantic effects remain reviewer-owned rather than gate claims.
- **Markerless prose:** current artifacts have no rewrite markers, so V1 prose
  operations refuse until a separately authorized workflow provides markers.

## Testing

Backend-free unit and CLI tests cover the sole exact-pair command form: missing,
repeated, mismatched, unavailable, selector-substituted, inferred, and
companion-mode evidence all refuse before backend contact. They cover exact
receipt-analysis identity binding, both static route classes, invalid no-route
evidence, and row-targeted-feedback refusal for artifact targets or blank
reviewer requests. They cover
the strict V1 envelope's exact keys, native integer version, every closed
operation shape, nested duplicate member, and response type/value rejection.
They cover every listed row-field allowlist member, the explicit
`decisions.rationale` local-revision carve-out, duplicate row/region targets,
more than one prose operation, one response, canonical scalar-span rejection,
and preservation of every unpermitted byte through final raw-byte publication
on every supported platform. Selected-feedback fixtures prove
that an open, response-absent row replaces only its `state` scalar and receives
one canonical single-line inserted `proposed_response` mapping; multiline,
noncanonical, or pre-existing-response cases refuse; row-field values reject
blank or surrounding-whitespace text and follow the same renderer-derived
one-line and candidate-canonicality rule. Region fixtures cover the
exact standalone-line marker grammar, duplicate or nested markers, the
non-whitespace outside-content full-body boundary, absent regions, and
markerless V1 refusal, and replacement values that alter marker inventory.
Tests also cover structural-proof failures, current
full-gate failures, and changes to every final proof input during guarded
backend work: selected and unselected artifacts, recorded source, brief,
receipt final, and analysis final. They cover continuous guard scope through
comparison and replacement, selected-feedback-only transitions, seed-state
outcomes, atomic failure paths, preflight interruption, and every closed
monotonic redacted preflight/terminal phase combination. Structural-transport
tests pin the isolated Codex read-only argv, configuration/rules isolation, and
workspace, prove its captured runtime capability contract, macOS Seatbelt
workspace-read denial, and fact-free version-or-isolation mismatch refusal, and
prove that active backend selection, fallback selection, and configured extra
backend argv cannot alter the fixed evaluator; malformed final names reach the
redacted preflight refusal before seed invalidation or backend contact. Platform fixtures prove the final binary
replacement retains LF candidate bytes without text newline translation.
Fixtures prove a rewrite can preserve identity and relations while
changing a permitted span; they never claim to classify the semantic adequacy
or downstream effect of changed prose.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.
- step 8 (feature) — tests covering the behavior this step changes; green before completion.
- step 9 (feature) — tests covering the behavior this step changes; green before completion.
- step 10 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A current receipt record and current analysis record with the same exact
  immutable receipt identity can produce a row-targeted one-artifact candidate
  only when its selected reviewer request is nonblank and after the proof confirms declared identity, relation, ordering,
  decision, feedback, parse, complete proof-input, and current-gate invariants.
- The command replaces only listed canonical row-field spans, one selected
  feedback `state` scalar plus its canonical response insertion point, and an
  eligible pre-existing region interior. It accepts only the strict V1 envelope
  and explicit exact-pair command, and rejects decision-rationale edits,
  duplicate targets, artifact-targeted feedback, more than one prose operation,
  markerless prose operations, blank or surrounding-whitespace row-field values,
  unsupported scalar encodings, marker-inventory
  changes, and every other
  unsupported operation before seed invalidation, backend contact where
  determinable, or publication.
- Every byte outside permitted spans, including marker delimiters and line
  endings, remains unchanged through final raw-byte replacement; the structural
  path never re-renders a whole artifact.
- A mismatch or gate failure in any complete proof input observed while the
  participating-writer guard remains held through replacement refuses without
  replacement. This includes an unselected artifact, recorded source, brief,
  receipt final, or analysis final; it does not claim protection for an external
  manual edit that races after comparison.
- Successful publication changes exactly the selected canonical artifact and
  selected feedback response, leaves semantic assessment to `awaiting-review`,
  and preserves the existing conservative seed-state contract. Failure leaves
  canonical content unchanged.
- Every invocation records the closed redacted preflight/terminal outcome
  matrix and no lifecycle surface contains reviewer text, roadmap prose,
  prompts, or backend replies.
- A structural invocation uses the captured, version-pinned Codex read-only
  evaluator inside the verified macOS Seatbelt no-workspace-read boundary, with
  a fresh isolated working root and user config and execpolicy rules disabled.
  Active backend selection, fallback, and configured argv cannot alter it;
  malformed final identities and an unavailable, changed, or unisolated
  evaluator refuse before seed invalidation or backend contact.
- Documentation distinguishes presentation revision, rewrite-only structural
  revision, evidence-only escalation/impact analysis, generic structural work,
  cross-artifact transactions, and broad stage re-entry.

## Deferred

BACKLOG #289 owns generic creation, removal, ordering, relation-changing
operations, and candidate-aware semantic-impact proof. A separate evidenced
request owns marker creation or migration if prose rewriting must become
available for current artifacts. A cross-artifact transaction remains dormant
until the generic contract and a real declared multi-artifact request exist.

## Implementation and reconciliation status (2026-08-17)

All ten implementation steps completed green under `run --all --commit`; step
10 is explicit non-code documentation. Four complete plan-canonical
reconciliation sweeps followed. They closed exact-final-read, lifecycle,
publication-boundary, redaction, in-flight snapshot, literal-dollar, and
coverage-matrix gaps. The fourth sweep is preserved in
`20260817-225221-run-reconcile.json` through
`20260817-230809-run-reconcile.json`; it covers steps 1–9, because step 10 is
non-code.

That fourth sweep finds six clean steps plus four bounded follow-ups: focused
test coverage at steps 2 and 6; one fail-safe delimiter-admission inconsistency
at step 3, where the later merger already rejects the malformed inline marker;
and the known step-8 evaluator capability contract. The installed runtime
cannot initialize inside the verified Seatbelt boundary, so the route remains
correctly fail-closed before evidence or seed mutation. That is external
capability evidence, not a reason to weaken isolation or widen this arc.

## Post-run convergence disposition

The post-run tail stops whole-sweep discovery here. The direct audit-policy
update requires a handoff triage rather than a model-label-based stopping
decision: prove an outstanding plan-canonical code property against code and
its existing tests, apply a class-wide correction with focused coverage when it
is false, and use focused test work when behavior is already correct.

No further `reconcile-code --all` run is required merely to elaborate the
remaining coverage or capability tail. A later full sweep needs a verified
class-wide implementation correction, a newly reproduced safety/authority
failure, or material code drift. The next ordinary verification surface is code
review; it preserves the rewrite-only boundary and never uses
`reconcile-plan` after this execution.
