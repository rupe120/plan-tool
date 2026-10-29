# Plan-tool bug backlog

Tracks known correctness issues that are still unresolved. Completed items are
removed; Git history is the record. Forward-looking work belongs in
[`BACKLOG.md`](BACKLOG.md).

## Triage

- Add new items at the bottom of their severity section.
- A promoted item keeps its `###` heading and carries only
  `- **Promoted:** IPPT-123 (YYYY-MM-DD)`; the Jira ticket holds the working brief.
  See [`docs/TRACKING.md`](docs/TRACKING.md#promotion-stubs).
- Drain `BUG`, then `RISK`, then `MINOR`. The `ROADMAP` section is
  owner-tracked and is not part of the team's drain or its Jira promotion.
- Put a new roadmap-owned item under `## ROADMAP` with a `Severity` line.
  An item that touches roadmap code and shared code goes in its severity
  section instead. See
  [`docs/TRACKING.md`](docs/TRACKING.md#roadmap-boundary).
- Every live item needs Files, Symptom, Fix, and Approach; the
  [documentation style guide](docs/reference/documentation-style.md#backlog-entries-and-tickets)
  says how to word them. A promoted item is
  only its heading and its `Promoted` line, and an item under `ROADMAP` also
  carries a `Severity` line. The route, readiness,
  and tier labels in
  [`docs/TRACKING.md`](docs/TRACKING.md#labels-every-entry-carries) apply here
  too; they're being added as entries are touched. Use `plan-tool` for
  changes with open design choices or multi-module persistence contracts.
- Confirm the claimed bug against the test module covering its target code
  before changing it — a passing test that pins the current behavior
  outranks a plausible static diagnosis.
- **Resolving a bug:** add or update regression coverage that fails under the
  prior behavior; run focused tests, then the full suite; review the complete
  diff for sibling call sites, documentation, and error outcomes a class-wide
  fix implies; then remove only the fulfilled entry (or its promotion stub)
  and any obsolete
  references.
- **Retiring a risk or contingent change:** do so only when the accepted scope
  has no current behavioral defect, or an observed input is required before a
  safe remedy can be selected. Do not describe a retirement as fixed. Record
  why it is disproportionate now and its exact re-open condition in
  `docs/history/backlog-decisions.md`; regression coverage remains required
  for any claimed behavior change.

Durable re-open conditions for retired items are recorded in
[`docs/history/backlog-decisions.md`](docs/history/backlog-decisions.md).

## BUG

### A same-batch add-row whose relation targets itself is wrongly refused as unauthorized

- **Files:** `plan_tool/roadmap_candidate.py:_same_batch_added_endpoint_identity`,
  `_validate_relation_authority`. Not part of the `roadmap-candidate-row-prose-amendments`
  branch — this is already-shipped code from the merged
  `roadmap-candidate-same-batch-relations` plan; a stale local `main` in this
  clone (41 commits behind `origin/main`) caused a `/code-review` pass to
  scope its diff against it and surface this, so it's recorded here rather
  than fixed on that unrelated branch.
- **Symptom:** confirmed by execution against the real
  `materialize_candidate`/`parse_candidate_delta` pipeline. A batch add-row
  creating a row whose own declared relation targets itself (e.g. an entity
  with a `REFERENCE` field pointing at its own id — a tree/parent-pointer
  shape) is refused with `reason='unauthorized-addition'`. In
  `_same_batch_added_endpoint_identity`, the exclusion
  `(operation.artifact_key, operation.row.id) != (relation.owner_artifact_key,
  relation.owner_id)` is written to stop a relation's owning operation from
  authorizing itself, but for a true self-reference the owner op is also the
  only operation that could ever supply the endpoint, so the exclusion
  removes the sole valid match and `exact_additions` comes back empty.
- **Fix:** none applied (out of scope for the branch that surfaced it). The
  exclusion needs to distinguish "this operation is the owner, and a
  *different* operation should supply the endpoint" from "this operation is
  the owner and legitimately also creates its own self-referencing endpoint"
  — likely by allowing the match when `relation.owner_id == relation.endpoint_id`
  rather than unconditionally excluding same-operation matches.
- **Related, same area, not separately filed:** the same review pass also
  flagged (a) the same-batch exception being checked identically for added
  *and* removed relation atoms in `_validate_relation_authority` (structurally
  unreachable today given gate-maintained invariants, but written
  endpoint-generic rather than addition-generic), and (b)
  `_RELATION_ENDPOINT_IDENTITIES` failing open for any future `RelationKind`
  with no entry (its own comment already records `CONSTRAINT_ANCHOR` once
  slipping through this way) with no exhaustiveness test tying the table to
  `RelationKind`'s members. Both are real but lower-severity; worth a look
  alongside the fix above rather than filing three separate entries.
- **Approach:** direct, once picked up on the branch/plan that actually owns
  this code — small, localized exclusion-condition fix plus a regression test
  for the self-reference case.
- **Origin:** 2026-09-28, `/code-review high` on
  `run/roadmap-candidate-row-prose-amendments`, diff scoped against a stale
  local `main` in error.

### `_code_anchor_resolves` still reports two real, existing files as missing: bare-filename citations and negated-existence citations

- **Files:** `plan_tool/data_contract.py:_code_anchor_resolves`,
  `_resolve_anchor_path`.
- **Symptom:** Two of the four originally-reported data-contract false
  positives remain (the other two, and all three files-coherence false
  positives, are fixed — see below). (1) A bare filename citation
  (`test_qbo_realm_release.py`) whose real file lives in an unstated
  directory (`tests/integration/test_qbo_realm_release.py`) still reports
  "does not exist". The monorepo-subdirectory / multi-segment tail-match case
  *is* fixed (`_resolve_anchor_path`), but bare-filename fallback was
  deliberately dropped: a bare name is a non-distinctive global search, so it
  could otherwise silently resolve a genuinely broken citation (e.g.
  `config.py`) against an unrelated real file elsewhere in the repo, masking
  the exact defect the check exists to catch. (2) A sentence that cites a
  path specifically to assert its absence ("there is no shared
  `tests/integration/conftest.py` yet") is still flagged as if it were a
  dependency. A negation-detection heuristic was implemented, found buggy by
  review (its lookback window bled across an adjacent, unrelated citation),
  and removed rather than patched: it is the same prose-vocabulary-inference
  shape this repo's own CLAUDE.md documents as a withdrawn anti-pattern (§
  "Withdrawn: the per-`change_type` test-ordering contract") — guessing
  author intent from nearby words, for one sub-case out of seven.
- **Fix:** none identified that doesn't reintroduce one of the two problems
  above. A safe bare-filename fix needs a way to bound the search to files
  the citing plan/step is actually related to; no such project-scoping
  concept exists in the data model today. A safe negation fix needs the
  finding to carry enough machine-checkable structure that suppression isn't
  inferred from prose at all — e.g. an explicit decided-absence marker the
  detail format recognizes — rather than sentence-level negation detection.
- **Approach:** `plan-tool` — needs a design decision (see Fix); no longer a
  bounded existing-function edit.
- **Origin:** 2026-09-01, authoring `login-with-quickbooks` in a sibling repo.
  Of that round's 7 false positives, `check_files_coherence`'s near-miss
  heuristic (3 of 7, an absolute-basename-character-gap fix replacing a
  length-sensitive ratio) and `_code_anchor_resolves`'s monorepo-subdirectory
  resolution (1 of 7) are fixed with regression coverage
  (`tests/test_review.py::TestNearestDeclaredMatch`,
  `tests/test_data_contract.py`); these remaining two are not.

### Model-backed commands do not share one complete terminal failure receipt

- **Files:** `plan_tool/run_log.py`, `plan_tool/create.py`,
  `plan_tool/detail.py`, `plan_tool/roadmap.py`, `plan_tool/roadmap_candidate_run.py`,
  `plan_tool/roadmap_candidate_review.py`, and their focused run-log and command tests.
- **Symptom:** a failed model-backed command does not consistently retain the
  facts an operator needs to diagnose it: phase, attempt, terminal outcome and
  reason, response byte count and digest, whether a raw response receipt was
  captured, and where that receipt lives. Existing paths use incompatible
  combinations of `phase_end`, `parse_failure`, result prose, and raw sidecar
  files. The narrow candidate repair will retain its own rejection evidence,
  but `create`, `detail`, roadmap stages, and
  candidate review will still require command-specific interpretation instead
  of one dependable terminal record.
- **Fix:** define one narrow, redacted terminal-failure receipt contract in
  the shared run-log layer, then migrate each producer deliberately. It must
  preserve the existing no-raw-JSONL rule, make a missing or failed sidecar
  capture explicit, and keep an optional diagnostic-write failure from
  changing the command's real outcome. Reconcile BACKLOG #217 and #332 rather
  than creating parallel raw-response storage.
- **Roadmap slice shipped 2026-09-21:** fresh stage authoring (`_run_stage`),
  bounded stage feedback (`_run_bounded_stage_feedback`), and local
  `--revise-feedback` emit the shared receipt for rejected replies. Each
  receipt records the producer-owned phase, attempt, reason, response byte
  count and digest, and sidecar disposition with its safe path only when
  written. Recovered attempts remain observable, and sidecar I/O failure does
  not change the command outcome.
- **Later migration slices:** migrate `create`, `detail`, candidate flows, and
  seed materialization deliberately. This remains the live work and prevents
  the completed roadmap class from claiming a cross-command migration.
- **Not this effort:** exception classification, CLI return-code policy,
  terminal status vocabulary, template-read normalization, and interrupt
  lifecycle behavior. Interrupt lifecycle behavior remains in BACKLOG #339.
- **Approach:** `plan-tool` — this is a cross-command persistence and
  observability contract, not a safe opportunistic refactor. Start only after
  Seed Ingestion Routing's current create work has completed its route,
  checkpoint, and documentation steps; keep that plan's file-backed route
  records intact.
- **Seed:** `plan-seeds/roadmap-model-failure-receipts.md` defines the first
  roadmap producer slice. Later producer migrations remain here rather than
  expanding that seed.
- **Origin:** observed 2026-09-03 while a candidate proposal completed its
  backend call but ended as `response-rejected`; its run log retained the
  outcome but not the parser reason or response evidence. The narrow candidate
  repair lands separately to avoid entangling the active create vertical.
  Seen again 2026-09-17 on Integration's `integration-aidlc-mvp` roadmap: two
  `--revise-feedback components:fb-1` runs ended `operation-rejected`, and
  `plan_tool/roadmap_revision_run.py` caught the `RevisionContractError`
  without logging its message; a 2026-09-17 `--from-stage 1` run ended `stage-invalid`
  in 13 ms with no reason recorded.
- **Status:** roadmap slice shipped 2026-09-21; later producer migrations remain deferred.

### `plan-tool sweep` fails with an error while printing its report when the repository path goes through a symlink

- **Promoted:** IPPT-1 (2026-09-24)

### `create` and `reprocess` point users at a `plan-tool completeness` command that doesn't exist

- **Promoted:** IPPT-2 (2026-09-24)

### A stored candidate with an unreviewed add-row fails to reload once `prose_amendment` became a required wire key, with no schema-version signal

- **Files:** `plan_tool/roadmap_candidate.py:ADD_ROW_REQUIRED_KEYS` (`prose_amendment`
  added, unconditionally required, by `roadmap-candidate-row-prose-amendments`
  step 2/4); `plan_tool/roadmap_candidate_run.py:_SCHEMA_VERSION`,
  `CandidateProposalEvidence._requires_normalized_operations`,
  `load_stored_candidate_proposal`.
- **Symptom:** `_requires_normalized_operations` (a `mode="before"` field
  validator) reparses `normalized_operations` through the same strict
  `parse_candidate_delta` used for a fresh model-proposed delta, every time
  stored candidate evidence is loaded (`load_stored_candidate_proposal` →
  `parse_candidate_evidence` → pydantic deserialization). Verified
  empirically: feeding a pre-this-change add-row wire shape (no
  `prose_amendment` key — the shape every stored candidate has if created
  before this upgrade) through that validator raises `ValueError("candidate
  batch operations are malformed")`, which `load_stored_candidate_proposal`
  catches and re-raises as `CandidateProposalError("candidate evidence is
  unreadable")`. `_SCHEMA_VERSION` stayed at `1` — every other addition to
  `CandidateProposalEvidence`'s own top-level fields (`feedback`,
  `review_requirement`, `root_version_id`, `source_version_id`,
  `batch_receipt`, `normalized_operations`, `operation_classification`) was
  made an `Optional` field defaulting to `None`, the established additive,
  non-breaking pattern for this record; `prose_amendment` breaks that pattern
  by being required inside the *nested* operation wire shape the same
  validator re-derives on every load, with no corresponding version bump. An
  operator with an unpromoted candidate stack open across the upgrade (a
  normal occurrence — a candidate persists until reviewed and decided) gets
  a generic "unreadable" error the next time that candidate is loaded,
  rendered, or decided, instead of a diagnosable, typed refusal.
- **Fix:** none applied. `DATA_CONTRACT.md`'s "Version-evolution policy" is
  explicit that issuing a newer schema version alone is not an upgrade path,
  and that a retirement making old records unreadable is valid only with an
  explicit project-level migration/archival decision and a stated fail-closed
  outcome (its own cited precedent: `docs/history/roadmap-evidence-v1-retirement.md`).
  Bumping `_SCHEMA_VERSION` to `2` would convert the current confusing deep-
  parse failure into the clean, already-built-for "candidate proposal
  evidence schema version is unsupported" refusal — but that alone still
  silently strands whatever candidate stack exists at upgrade time, which the
  policy requires being an explicit, documented decision rather than a side
  effect of an unrelated feature step. The alternative — making
  `prose_amendment` optional on the *reload* path only, defaulting absent to
  `None` for pre-upgrade evidence while keeping it required for a freshly
  parsed model delta — needs its own version-keyed branch in the same strict
  parser this reload path deliberately shares with fresh-delta parsing (by
  design, to catch tampering/corruption via an exact round-trip), which is
  not obviously smaller than the version-bump path.
- **Deliberately not:** silently bumping `_SCHEMA_VERSION` without the
  `DATA_CONTRACT.md`-required migration/retirement writeup — that would
  itself violate this repo's own persisted-schema governance rule.
- **Approach:** `plan-tool` — an open design choice (retire-with-doc vs.
  backward-compatible reload) against a multi-module persistence contract
  (`roadmap_candidate.py` wire shape + `roadmap_candidate_run.py` schema
  version + `DATA_CONTRACT.md` policy).
- **Origin:** 2026-09-28, `/code-review high` on the
  `roadmap-candidate-row-prose-amendments` run branch (commit `1af9d8c5`).

### Roadmap-derived plans cite bare `0N-*.md` names, which resolve to stale top-level copies beside an accepted head, so audits ground on a superseded roadmap and report false contradictions

- **Files:** `plan_tool/prompts/roadmap-seed.md` (the `## References` rule:
  "cites `01-domain.md`, `02-constraints.md`, `03-components.md`, and
  `04-roadmap.md` by their literal filenames"), the draft-seed
  `source_artifacts` frontmatter it produces,
  `plan_tool/roadmap_version_promotion.py` (module docstring: "Promote one
  exact sealed roadmap candidate by changing only its selector"), and the
  completeness audit prompts, which carry no roadmap resolution.
- **Symptom:** promotion writes only `.roadmap-versions/accepted-head.json`
  and does not refresh the top-level `0N-*.md` files. That is by design
  (`docs/implementation-plans/2-roadmap-versioned-from-birth.md`,
  Architecture: top-level files beside an accepted head "are inert leftovers
  that no command reads or flags"). No command reads them, but seed authors
  and audit models do. The seed prompt makes every draft seed cite bare
  filenames, `create --from-existing` carries those into the plan, and the
  audit model opens the only file on disk with that name, the inert
  top-level copy. On Integration's `integration-aidlc-mvp` (2026-10-10) the top-level
  `04-roadmap.md` still holds the old `decision-minimal-workflow-shape`
  ("Seed exactly one workflow with two steps spanning two different runtime
  connectors…"), five plans, and no `workflow-run` owner. The accepted head
  `.roadmap-versions/c7743c56…a4987/04-roadmap.md` chooses "one fixed
  three-step workflow" and nine delivery plans, and contains no "two steps
  spanning". Bare audits then reported false HIGH correctness findings
  grounded on the stale copy (reports under Integration
  `docs/implementation-plans/plan-details/<plan>/reports/`):
  - `workflow-catalog-core` `20261010-003835-completeness.md`:
    `[workflow-shape-provenance]` ("The cited `04-roadmap.md` decision
    requires two steps") and `[run-owner-association]` ("its current field
    set has no owner").
  - `isolated-engine-worker` `20261010-005401`:
    `[configured-three-connector-sequence]`. Its citation names the
    accepted-version path but quotes the stale top-level text, so a
    misattributed quote passes the audit unchecked.
  - `chat-output-streaming` `20261010-010407`: `[workflow-shape]`.
  - `cdk-infrastructure-and-environments` `20261010-012103`:
    `[accepted-roadmap-source]`.

  The same citation also breaks a roadmap with no leftovers. A stage run
  publishes only the version store and the accepted head
  (`ROADMAP_FORMAT.md` § "What writes them"), so in a roadmap created that way a bare
  `04-roadmap.md` names no file at all. That case follows from the design and
  has not been observed in a run; the stale-copy case above is the observed
  one.
- **Cause (verified in code):** promotion is meant to change only the
  selector, so the defect is not a missed refresh. It is the citation
  contract. The seed prompt binds plans to bare names that resolve on disk
  to the files the versioned-from-birth plan declared inert. No path (seed
  writer, `create`, or the audit inputs) translates a roadmap citation to
  the accepted version.
- **Fix:** roadmap seed citations name the accepted version: the seed
  writer renders `References` and `source_artifacts` as version-store paths
  (or the version id plus the member name), and `create` keeps them. This
  changes the draft-seed contract, so it goes through the plan pipeline.
  Shipped 2026-10-10 as a separate direct change: a stderr warning naming
  leftover top-level `0N-*.md` files beside an accepted head, on
  `roadmap --view`, `--materialize`, `--refresh-seeds`, `--accept-seed`, and
  `--apply`. Deliberately not warned: `create --from-existing <seed>`, the
  route that opens the cited name; the citation fix removes the bare name
  there.
- **Deliberately not:** making promotion rewrite the top-level files, which
  restores the two-copy design the versioned-from-birth plan removed.
- **Workaround:** delete the top-level `0N-*.md` files (the documented hand
  conversion, which the warning from 2026-10-10 prompts) and re-audit.
- **Route:** plan · **Readiness:** ready · **Tier:** experienced.
- **Origin:** Integration `integration-aidlc-mvp` bare audits, 2026-10-10.

### Ten model-backed calls still write no start or end record to the run log, so run-log token totals undercount

- **Files:** `plan_tool/create.py` (`suggest_slug`), `plan_tool/review.py`
  (`check_criteria_fulfillment`, `review_plan_full`,
  `extract_and_append_review_lessons`), `plan_tool/jira.py`
  (`render_jira_export`), `plan_tool/annotate.py`
  (`classify_plan_implementation`), `plan_tool/lessons.py`
  (`find_lesson_equivalences`), `plan_tool/concept_tree.py`
  (`emit_concept_tree`), `plan_tool/launcher.py` (`_run_deep_for_step`,
  `run_all_done_steps`).
- **Symptom:** `shell._emit_call_end` drops `claude_call_end` when no sink is
  installed. None of these functions receives a `RunLogWriter`, so none can
  bind one. Their tokens are invisible to run-log analysis.
- **Fix:** thread a `run_logger` parameter (or one shared opener) through each
  function's public signature and CLI callers, bind a sink, emit a start with
  `prompt_sha256`. The list is pinned as `DEFERRED_SITES` in
  `tests/test_run_log_call_coverage.py`; wiring a site moves it to
  `LOGGED_SITES`.
- **Deliberately not done:** an ambient-writer fallback inside `_emit_call_end`
  — with no bind there is no ambient writer either.
- **Approach:** direct.
- **Origin:** 2026-10-16, token ledger analysis. Wired the same day:
  `apply_finding` (streaming invoker emitted no end),
  `assess_direct_source_split_from_claude`, `_propose_risk_profile_from_seed`;
  `plan_audit` now emits a start; `prompt_sha256` added to every start.

### `create` writes a single "record unbuilt upstreams and stop" step for a seed whose upstream plans are planned but unbuilt, and the bare audit rates that plan CRITICAL

- **Files:** the `create` plan-generation prompts under `plan_tool/prompts/`,
  which have no rule for a sibling plan that exists but is unbuilt ("unbuilt"
  appears only in `plan-audit.md`), and `plan-audit.md`'s delivery-route
  criterion.
- **Symptom:** for three Integration seeds whose upstream plans exist but are not
  built, `create` emitted a one-step plan that records the missing upstreams
  and stops (Integration commit `da657b8`:
  `docs/implementation-plans/2-repository-browse-and-reference.md`,
  `2-static-spa-delivery.md`, and `2-bitbucket-deployment-pipelines.md`).
  Step 1 of the pipelines plan reads "Record unbuilt CDK, SPA, and
  repository-browse dependencies and unresolved API hosting, then stop…".
  The bare audit then rated each plan CRITICAL for having no delivery route:
  `[repository-browse-delivery]` (`20261010-010632`),
  `[static-spa-owner-journey]` (`20261010-012242`), and
  `[pipeline-delivery-route]` (`20261010-012626`, "only records
  prerequisites and stops; it supplies no later delivery route"). One stage
  generates a shape the next gate always refuses, and neither says which
  side is wrong.
- **Fix:** settle one contract and apply it on both sides. Either `create`
  plans against an upstream plan's declared interfaces (its Architecture and
  Acceptance criteria) and states the dependency as an ordering
  prerequisite, or the audit accepts a stop-and-record plan as a valid
  interim shape and routes it to a re-`create` once the upstreams ship. The
  first matches roadmap ordering, which already sequences dependent plans.
- **Deliberately not:** suppressing the CRITICAL finding without changing
  what `create` produces.
- **Approach:** plan-tool; it decides how a plan may depend on an unbuilt
  sibling plan.
- **Route:** plan · **Readiness:** ready · **Tier:** architect.
- **Origin:** Integration `integration-aidlc-mvp` batch plan creation and bare audits,
  2026-10-10.

### The audit reports a path a sibling plan in the same roadmap creates as missing

- **Files:** the audit's missing-file grounding. Locate the emitting check
  first; `plan_tool/grounding.py` and
  `plan_tool/data_contract.py:_code_anchor_resolves` are the candidates.
- **Symptom:** `integrations/shared/DIRECTIVES.md` tells the triaging session
  that a finding citing a path another plan in the same roadmap creates is a
  known false positive (T): verify it once and leave the plan alone. The audit
  still raises it, and in a multi-plan roadmap batch it recurs every round.
  Integration's batch driver has no `proceed` at Gate 2, so a material T finding there
  can only end in `continue` or `stop`.
- **Fix:** have the audit exclude paths a sibling roadmap plan declares in
  `creates:` from missing-file findings, wherever the finding is emitted.
  A two-plan roadmap fixture where plan 2 cites a file plan 1 creates audits
  without that finding.
- **Deliberately not:** suppressing any other T class, or paths created by
  plans outside the roadmap. If sibling footprints are not reliable at audit
  time, record that and stop. Related: the unbuilt-sibling entry above, which
  concerns how a plan may depend on a sibling at all.
- **Approach:** plan-tool; the audit needs the roadmap membership and the
  siblings' footprints at audit time.
- **Route:** plan · **Readiness:** ready · **Tier:** architect.
- **Origin:** Integration `construction-batch-driver` open item "T findings at
  Gate 2", 2026-10-19. Filed first as BACKLOG #503 in the same pull request,
  then moved here; #503 is not reused.

### `create --from-existing` records `source_seed` as the seed path it then archives, so the plan points at a file that no longer exists and Gate 1 rates it HIGH

- **Files:** `plan_tool/create.py:_resolve_source_seed` (`:1672`) and the
  seed archive on the superseded-by-new-plan path (`ARCHIVE_DIRNAME`,
  `REPLACED_SUFFIX`, `:488-498`).
- **Symptom:** `_resolve_source_seed` records the `--from-existing` path
  while the file exists, and `create` then moves that file to
  `plan-seeds/archive/<slug>.replaced.md`. Integration commit `da657b8` wrote
  `source_seed: plan-seeds/bitbucket-deployment-pipelines.md` into
  `2-bitbucket-deployment-pipelines.md`, and the same commit holds only
  `plan-seeds/archive/bitbucket-deployment-pipelines.replaced.md`. The
  durable seed is the roadmap draft at
  `roadmaps/integration-aidlc-mvp/plan-seed-drafts/bitbucket-deployment-pipelines.md`.
  The round-five Gate 1 audit (`bitbucket-deployment-pipelines`
  `20261010-042824`/`-042825`) reported `[authoritative-roadmap-snapshot]`
  HIGH on the dangling path, and Integration commit `03b4e23` repointed it by hand.
- **Fix:** record the path that survives `create`. For a roadmap-published
  seed that is its `plan-seed-drafts/` source; otherwise the archived copy.
  The audit resolves `source_seed` through the same rule, so a plan created
  before the fix still grounds.
- **Approach:** direct.
  **Escalate to plan if:** the roadmap-published seed's draft path is not
  recoverable from the `plan-seeds/` copy without a new link record.
- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Origin:** Integration `integration-aidlc-mvp` nine-plan roadmap-to-plan run, 2026-10-10.

### Two tests fail under full-suite load: a 5-second subprocess wait times out and one test crashes its xdist worker

- **Files:** `tests/` — `test_reader_guard_blocks_a_writer_for_the_same_roadmap`
  (waits 5 seconds for a spawned subprocess) and
  `test_direct_run_broader_relocation_end_to_end` (kills its `-n 4` worker).
- **Symptom:** in a full `-n 4` run on a loaded machine (about 550 seconds) the
  first fails on its 5-second wait and the second crashes its worker ("node
  down"). Both pass alone. The second crashes the same way on the commit before
  the stream-log work (`a5a14a387`), so the load, not that change, is the cause.
- **Fix:** none applied. Widen or poll the spawn wait in the first; find what the
  second does that kills a worker (memory or a nested subprocess) and bound it.
- **Approach:** direct.
- **Origin:** 2026-10-13, full-suite runs during the stream-log review rounds.

### `_code_anchor_resolves` reports an existing method, private method or nested function as not resolving in HEAD

- **Files:** `plan_tool/data_contract.py:_code_anchor_resolves` and
  `_module_level_symbol_exists`.
- **Symptom:** a detail citation `path:Class.method` (or `path:Class._private`,
  or a function nested in another) is reported as `code anchor … does not
  resolve in HEAD` unless the owner is a registered data contract. The check
  accepts only a one-part symbol that exists at module level, so any two-part
  symbol falls through to the failure branch even when the class and method
  exist. In one detail bundle (Integration `construction-batch-driver`, Gate 2 round
  1), 19 such citations were flagged as blocking structural findings, and each
  named a method that exists at the cited path (for example
  `RoadmapDriver.start`, `_Reader.text`).
- **Fix:** resolve a two-part symbol by finding the top-level class, then a
  `def` or `async def` inside it. Keep reporting a symbol that is genuinely
  absent. This extends the resolver fix already tracked for bare-filename and
  negated-existence citations in the entry above.
- **Deliberately not:** resolving names that are keys in a runtime dict or
  built by registration; those keep failing, and an author cites them in
  prose.
- **Approach:** direct; a bounded change in one function with a test per shape.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `experienced`.
- **Origin:** 2026-10-19, Integration `construction-batch-driver` Gate 2 audit. The
  workaround was to cite the path and the symbol in separate spans.

### Onboarding and installed skill instructions conflict with canonical audit and iteration rules

- **Files:** `docs/how-to/common-workflows.md`, `README.md`, all three
  `integrations/*/SKILL.md` routers; authority:
  `integrations/shared/DIRECTIVES.md` and `docs/how-to/pipeline/audit.md`.
- **Symptom:** common workflows tells readers to detail before auditing and
  treats absent details as audit defects; routers also describe detail iteration
  as on by default despite their own one-shot instruction. The first-task path
  can therefore skip the bare gate or select the wrong detail behavior.
- **Fix:** enumerate identifier and vocabulary restatements, then align the
  introductory flows and routers with the two audit gates and actual iteration
  defaults. Keep one authority for rules; add no prose-lint gate.
- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Arc assignment:** `backlog-arc-installed-skill`; coordinate onboarding #510.
- **Verification:** review all three routers and linked first-plan paths against
  current parser behavior and canonical guidance; check affected links/examples.
- **Scope:** documentation correctness only; no runtime/default changes or
  unrelated documentation rewrite.

### `plan-tool create --from-existing` crashes with "concept scope contains duplicate IDs" on a seed that has some but not all of the standard section headings

- **Files:** `plan_tool/create.py` (`_review_create_concepts` at line 7833, which
  builds the scope list at line 7871; the concept tree is built at about line
  9648 from `parse_body_sections(concept_source, ignore_fenced_code=True)`),
  `plan_tool/concept_review.py:_validate_request` (line 61, the duplicate-ID
  check), `plan_tool/concept_tree.py:concept_id` (line 77, the ID is a hash of
  the section title).
- **Symptom:** confirmed by running the command twice. On plan-tool 0.1.0,
  `plan-tool create milestone-3-diff-plan --from-existing
  plan-seeds/milestone-3-diff-plan.md --output-dir docs/implementation-plans -y
  < /dev/null` finishes "Distilling seed" and "Proposing initial steps", prints
  "test command omitted: no preflight-qualified command and no interactive
  operator input.", then stops with `plan-tool: unexpected error:
  InvalidConceptScopeError: concept scope contains duplicate IDs`. Nothing is
  written or registered. A re-run resumes from the cached checkpoints and fails
  the same way. The seed has these level-2 headings, each once: Outcome, In
  scope, Out of scope, Architecture, Risks, Testing, Acceptance criteria,
  Deferred, References. It has no Overview and no Problem statement, so
  `SEED_FORMAT.md` says it is not "direct-ready" and create distills it
  first. Running `plan_tool.parser.parse_body_sections` on the seed file alone
  returns 9 unique names, and the distilled output saved in
  `.plan-tool/checkpoints/<slug>/create-distill-seed.json` has 8 unique section
  names. Wrapping `review_concept_scope` to print what it receives showed 13
  concepts: overview, problem statement, architecture, out of scope, risks,
  testing, acceptance criteria, deferred, then out of scope, risks, testing,
  acceptance criteria, deferred a second time. Two nodes with the same title
  get the same ID, so the check at `concept_review.py:61` rejects the list.
  Crash logs are in `.plan-tool/crashes/<slug>/` (for example
  `20261018T032229Z.txt`).
- **Fix:** none applied. Not yet found: why `concept_source` (`seed_body` at
  that call) holds the five canonical sections twice. The likely cause is that
  the distilled body is joined with the original seed's own canonical sections
  when the seed has some of the standard headings but not all of them. This is
  an inference from the evidence above; the joining code has not been read.
  Fix it where the duplicates are introduced, and also make
  `_review_create_concepts` report the repeated section name instead of the
  hash-based "duplicate IDs" crash, since no user can act on that message.
- **Workaround:** add non-empty `## Overview` and `## Problem statement`
  sections so the seed is direct-ready and skips the distill step. Not tried
  yet.
- **Approach:** direct, starting with a regression test that builds a seed with
  some but not all of the standard headings and calls create with `-y`.
  **Escalate to plan if:** the duplication comes from the distilled body being
  merged with the raw seed by design, and the right merge rule is a product
  decision.
- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Origin:** the discord-cfg repository (`rupe120/discord-config`), writing a
  seed for its milestone 3 plan, 2026-10-17. Not checked against the existing
  tests for `create`, so a test that pins the current joining behavior may
  exist.

### Feature-container unknown fields are mislabeled as plan-level fields

- **Files:** `plan_tool/parser.py:_explain_extra_field` and mirrored tests.
- **Symptom:** a rejected extra field in a feature registry object, such as `features: [{id: cap, title: X, description: d}]`, is labeled “unknown plan-level field” and lists Plan fields rather than the Feature fields. Validation correctly rejects the input; the container label and allowed-field list are misleading.
- **Evidence:** step-description diagnostic review 1 probes this input and the existing `features.0.depends_on` case. The helper classifies every non-step location as plan-level at the pre-repair base as well; this is not introduced by the alias diagnostic change.
- **Outcome / in scope:** identify actual feature containers and list their supported fields while preserving plan/step diagnostics and placement hints.
- **Out of scope:** accepting new fields, changing feature or step schemas, altering error payloads or exit codes, or normalizing unrelated application errors.
- **Verification:** real feature-extra-field errors name the feature container and only its valid keys; plan/step extra and missing-field cases retain their correct behavior.
- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Origin:** concise step-description diagnostic review, 2026-10-22; pre-existing formatter follow-up.

### Create body-patch helpers can normalize existing plan body newlines

- **Files:** `plan_tool/create.py:_patch_plan_body_section`, `_insert_references_section`.
- **Evidence / symptom:** newline-preservation review 2 identifies `read_text`/`write_text` pairs that normalize an existing CRLF/CR body. These helpers are unchanged by the concept-sync/scope-out repair. No end-to-end create reproduction is claimed; investigate whether a reachable finalization path supplies non-LF text before selecting a fix.
- **Outcome / in scope:** establish a real reachable case and, if confirmed, preserve unowned body bytes through these existing patch helpers.
- **Out of scope:** concept-sync and scope-out, section ownership, seed synthesis, alias semantics, broad I/O consolidation or markdown redesign.
- **Verification:** reproduce through the create path; assert raw unowned bytes while intended body edits still apply, including fence and concurrency behavior already supported by each helper.
- **Stop / defer:** close without implementation if the reachable path cannot supply non-LF input; do not add a framework based only on a helper-level possibility.
- **Route:** direct · **Readiness:** needs investigation · **Tier:** experienced.
- **Origin:** newline-preservation Claude Code review 2, raw finding 2; static evidence only.

### Multiline concept decisions can create document headings outside their owned section

- **Files:** `plan_tool/concept_sync.py:render_scope_decisions` interpolates concept titles/rationales as unescaped Markdown.
- **Symptom / evidence:** a valid deferred concept with rationale `why\n# Injected heading\nmore rationale` publishes successfully, but the section reader sees only `- Delayed — why` inside Deferred; the rest becomes an H1 section. A 2026-10-22 probe through `synchronize_concepts` confirms the heading and truncated owned body. The rendering code predates the H1-boundary repair and is unchanged by it.
- **Outcome / in scope:** render valid concept text as decision content without letting it introduce document-level boundaries; cover title and rationale consistently.
- **Out of scope:** changing concept ownership/decisions, tightening stored schemas, parser boundary rules, publication protocols or broader Markdown sanitization.
- **Verification:** actual sync with multiline titles/rationales, heading-looking and fenced-looking lines; assert intended decision content remains within its owned section, unowned bytes survive and repeat sync does not accumulate unintended sections.
- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Origin:** H1-boundary Claude Code review 1, candidate 6; independently reproduced through the actual synchronizer.

## RISK

### `extract_h2_sections`'s `ignore_fenced_code`/`strip_fenced_code` default to off even though every current production caller opts in

- **Files:** `plan_tool/scope_fence.py:extract_h2_sections`.
- **Symptom:** every one of the 13 current production call sites (verified
  by grep) now passes `ignore_fenced_code=True` or `strip_fenced_code=True`
  explicitly; none relies on the default. A future consumer of a seed/plan
  `## References`/`## Overview`/etc. section that calls
  `extract_h2_sections(text)` with neither keyword silently reintroduces the
  fenced-pseudo-heading bug class the `seed-source-references-fallback`
  sweep paid to fix at every existing site.
- **Fix:** the parser-fence prerequisite has shipped: parser-driven readers
  and writes now use fence-safe parsing, and unmatched openings refuse before
  parser-driven writes. The `extract_h2_sections` defaults remain off.
  Consider flipping them only after a separate compatibility review audits
  callers and tests that deliberately exercise the plain, non-fence-aware
  path.
- **Approach:** direct, but deferred until that compatibility review makes a
  standalone default-change decision.
- **Origin:** 2026-09-02, `/code-review high HEAD~2..HEAD` on the
  `seed-source-references-fallback` sweep.

### `install-skill`'s Phase 1 destination classification is not re-verified before Phase 2 writes (TOCTOU)

- **Files:** `plan_tool/cli/skill_cmd.py:cmd_install_skill`, `_classify_dest`.
- **Symptom:** Phase 1 classifies every destination once (`missing` /
  `already` / `mode-switch` / `collision`); Phase 2 acts on that snapshot
  without re-checking. Two concurrent `install-skill` invocations (or a
  manual `touch`/other process) targeting the same destination between the
  two phases: both see a path as `missing`; one succeeds, the other then
  either crashes (`os.symlink` raises `FileExistsError`) or silently
  overwrites the first process's write (`shutil.copyfile`). The Phase 1
  guarantee ("a collision blocks the whole set before any write") only
  covers collisions that exist *before* Phase 1 runs, not ones created in
  the window between classification and write.
- **Fix:** none applied. A safe fix needs either a lock file scoped to
  `dest_dir` or an atomic create-exclusive write path (`O_EXCL`), and either
  adds real complexity for a race that requires two concurrent
  `install-skill` runs against the identical destination — implausible for
  this CLI's normal single-operator use. Accepted as a low-priority risk
  rather than fixed now; re-open if a concurrent-install use case (e.g. a
  provisioning script running `install-skill` from multiple processes)
  actually surfaces it.
- **Approach:** direct, if ever revisited.
- **Origin:** 2026-09-17, `/code-review high` on the
  `skill-router-and-shared-reference` plan (install-skill's two-phase
  install set, added by that plan's step 2).

### A candidate add-row's prose amendment enforces only the fixed hard byte ceiling, not a project's configured lower limit

- **Files:** `plan_tool/roadmap_candidate.py:_parse_add_row_prose_amendment`
  (imports `HARD_MAX_PROSE_AMENDMENT_BYTES` from `project_config.py`
  directly); compare `plan_tool/roadmap_revision.py:_bind_add_prose` /
  `_validate_prose_bytes`, which check the project-configurable
  `StageFeedbackLimits.max_prose_amendment_bytes` (itself bounded below the
  same hard ceiling via `STAGE_MAX_PROSE_AMENDMENT_BYTES`).
- **Symptom:** the stage-revision path (human-reviewed row prose edits) and
  the candidate-delta path (model-proposed row-owned prose on add-row, added
  by `roadmap-candidate-row-prose-amendments`) both bound the identical kind
  of fragment, but only the former respects a project's configured stricter
  limit. A project that lowers `max_prose_amendment_bytes` below the 4KB hard
  ceiling gets that cap silently ignored on an LLM-authored add-row fragment.
  Separately, `_parse_add_row_prose_amendment` hand-rolls the same nonblank
  check `roadmap_revision.py:_require_nonblank` already provides, as an
  independent implementation with a different exception type
  (`CandidateDeltaError` vs `RevisionContractError`).
- **Fix:** none applied. `parse_candidate_delta` and everything under it is a
  pure, stateless parser (`response_text: str -> CandidateDelta`) with no
  `limits`/project-config concept anywhere in `roadmap_candidate.py`, unlike
  `roadmap_revision.py`'s threaded `StageRevisionContext`. Threading one
  through means a signature change across all 7 `parse_candidate_delta` call
  sites, including the pydantic `mode="before"` field validator
  (`CandidateProposalEvidence._requires_normalized_operations` in
  `roadmap_candidate_run.py`) that reparses stored evidence on every load —
  that call site has no natural place to source a live project-config object
  from. Reusing `_require_nonblank` directly isn't a small fix either: it's
  private to `roadmap_revision.py` and raises the wrong exception type for
  this caller's contract. Whether the candidate-delta path should even share
  the stage-revision path's configurability (the two are architecturally
  different — model-proposed batch delta vs. human-reviewed single edit) is
  an open design question, not obviously smaller than the schema-version gap
  documented above ("A stored candidate with an unreviewed add-row fails to
  reload...").
- **Approach:** `plan-tool` — open design choice (share `limits`
  configurability across the two prose-amendment paths, or keep them
  deliberately separate) against a parser used identically by two different
  call contexts.
- **Origin:** 2026-09-28, `/code-review high` on
  `run/roadmap-candidate-row-prose-amendments` (commit range through
  `efb78f0a`).

### `create --from-existing` reads several seed sections without first removing the seed's YAML frontmatter, so a `## <Section>` comment line there replaces the real section

- **Files:** `plan_tool/create.py` (`_preserve_source_optional_sections`,
  `_extract_supplied_guardrails`, the `_canonical_seed_covers_all` input in the
  file-backed route, the `seed_sections` read from `body_source`,
  `_restore_materialized_evidence_sections`) and `plan_tool/reprocess.py` (the
  archive's `extract_h2_sections` read).
- **Symptom:** a column-0 `##` YAML comment is legal in frontmatter and parses
  as a section when the reader does not strip the frontmatter first
  (`scope_fence._strip_frontmatter`'s docstring describes the failure). The
  duplicate rule keeps the first non-empty body, so that comment shadows the
  real section. Reproduced 2026-10-08 at `bfc8b261`: for a seed whose
  frontmatter holds a `## Scope guardrails` comment,
  `_extract_supplied_guardrails` returns `{'Scope guardrails': '---'}` while
  `_intent_from_seed_outcome` returns the real Outcome for the same text.
- **Sites, enumerated 2026-10-08** (every call of `extract_h2_sections`,
  `extract_h2_section_occurrences`, `_fenced_code_spans`, and `h2_section_spans`
  in `plan_tool/` by identifier; `_H2_HEADING_RE`, `_STRICT_STEPS_H2_RE`, and
  `^##` regex readers by vocabulary): 6 readers of a seed or seed-like source do
  not strip; 12 do (`create.py` at `_strip_frontmatter` call sites,
  `roadmap_gates.py` twice, `roadmap.py:_replace_stack_section`,
  `annotate_render.py` twice, `reprocess.py` for its fence check, and
  `canonical.py`, which uses the strict splitter).
- **Fix:** read the sections of the frontmatter-stripped text at the 6 sites,
  as `_intent_from_seed_outcome` already does. Strip only the text handed to the
  section reader, never the `source_text` that distillation's evidence spans
  index by line.
- **Do not merge:** the lenient `scope_fence._strip_frontmatter` and the strict
  `parser._split_frontmatter` stay separate (the lenient one's docstring says
  why). `read_canonical_provenance` and the draft-seed state readers read the
  frontmatter on purpose. `_patch_plan_body_section` locates the body by the
  exact `\n---\n` literal. The plan and detail readers that already split first
  are not in the class.
- **Verification:** one test parametrized over the 6 readers, with a seed whose
  frontmatter holds `## Scope guardrails`, `## Outcome`, and a body-section
  comment, showing the real section wins (following `TestIntentPredicateConsumers`);
  revert each strip and watch its case go red; the full suite passes.
- **Out of scope:** merging the two frontmatter splitters or adding a shared
  "read seed sections" helper (consolidation needs its own evidence), changing
  the first-occurrence duplicate rule, and changing what `create` does with a
  section once read.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `beginner`.
- **Approach:** direct, small: the same wrap at 6 sites plus one parametrized test.
- **Origin:** 2026-10-08, `/code-review high` on the `roadmap-stack-propagation`
  change, which noted `_extract_supplied_guardrails` reading the raw seed while
  its sibling strips. The enumeration and reproduction were done the same day.

### Run-log call pairing has open gaps around `plan_audit` and the sink-installing proposal sites

- **Files:** `plan_tool/review.py:_error_tracking_invoker`, `plan_tool/launcher.py:_invoke_and_log_end`,
  `_invoker_stats`, `plan_tool/gates.py:suggest_gates`, `plan_tool/intent_proposal.py`,
  `plan_tool/create.py:_propose_risk_profile_from_seed`.
- **Symptom:** (1) a `plan_audit` missing-heading re-prompt writes two starts and two ends under one
  `(phase, attempt=pass)` key, so a ledger cannot tell the calls apart. (2) `plan_audit`, `suggest_gates`,
  `propose_intents`, and the risk-profile classifier write a start before the call; an invoker that raises
  before reaching the shell leaves it without an end; `assess_direct_source_split_from_claude` has the inverse risk, an end sink
  with its start coming only from a reporter that may carry no run log. (3) `_invoker_stats` only isolates the bare `shell_invoker`, not a wrapper of it, so a wrapped
  invoker under `--jobs N` still reads the shared `_last_stats`.
- **Fix:** a per-call attempt for the audit; an end on the raise path at each start site; thread-local stats for wrappers.
- **Approach:** direct. The three start/sink blocks in `gates.py`, `intent_proposal.py` and `create.py`
  are also near-identical and could share one scoped helper; that consolidation needs AST-verified
  identity before anyone merges them.

## MINOR

### `_append_added_row_prose` copies its artifacts mapping even though both call sites hand it an already-fresh, about-to-be-reassigned dict

- **Files:** `plan_tool/roadmap_candidate.py:_append_added_row_prose`
  (`amended = dict(artifacts)`); its two callers,
  `plan_tool/roadmap_candidate.py:materialize_candidate` and
  `plan_tool/roadmap_candidate_run.py`'s
  `_require_reproducible_batch_operations` replay path — both build a fresh
  `dict(predecessor_artifacts)`, mutate it in an `_apply_operation` loop, then
  pass it straight in and immediately reassign the return value onto the same
  variable, so nothing holds the pre-call reference afterward.
- **Symptom:** not a correctness bug — confirmed no aliasing exists at either
  call site, so the copy is pure waste, not a safety net. On the data volumes
  here (a handful of stage-artifact keys, a handful of operations per
  candidate) the cost is immaterial; recorded so it stops surfacing as a
  seemingly-new finding across `/code-review` rounds.
- **Fix:** have `_append_added_row_prose` mutate its `artifacts` argument in
  place and return it, matching how the adjacent `_apply_operation` loop
  already mutates the same dict directly — which also means widening its
  parameter type from `Mapping[str, RoadmapArtifact]` to a mutable mapping
  type, a real (if small) signature/contract change, not just a body edit.
- **Deliberately not:** folding the prose-append pass into the
  `_apply_operation` loop itself — that would need duplicating the fold at
  both call sites rather than fixing the shared helper once.
- **Approach:** direct, low priority — wasted work only, no behavioral
  change.
- **Origin:** 2026-09-28, `/code-review high`, flagged in two consecutive
  rounds on `run/roadmap-candidate-row-prose-amendments`.

### `review_plan_full`'s fence guard re-runs the full audit-input snapshot capture, duplicating `cmd_review`'s own capture moments earlier

- **Files:** `plan_tool/review.py` (`review_plan_full`'s call to
  `AuditInputSnapshot.capture(plan_path, repo_root)`, made purely to reach
  the unmatched-fence check); `plan_tool/cli/review_cmd.py` (`cmd_review`'s
  own, separate full capture just before it).
- **Symptom:** not a correctness bug — both captures agree, since nothing
  mutates the plan between them — but every `plan-tool review` /
  `reconcile-plan` invocation on an N-step plan performs the full O(N)
  snapshot capture (one file read per step's detail artifact, plus the seed
  archive fallback's directory scan) twice in a row, purely to raise on a
  fence check that a lightweight standalone helper (like the sibling
  `_reject_unmatched_*_fence` functions already in this file) could answer
  without the snapshot's other side reads.
- **Fix:** either thread `cmd_review`'s already-captured snapshot into
  `review_plan_full` instead of re-capturing, or replace the fence check's
  use of the full capture with a narrow, snapshot-free `_fenced_code_spans`
  check like `review.py`'s own `_reject_unmatched_plan_fence`.
- **Approach:** direct, low priority — wasted work only, no behavioral
  change.
- **Origin:** 2026-09-02, `/code-review high` round 2 on the
  fence-guard-class fix (`be28de96`); confirmed but predates that fix (the
  guard call site itself is unchanged by it).

### Candidate consolidation: ~12 independent copies of the same "reject unmatched opening code fence" check (unverified — needs identity check before any merge)

- **Files:** `plan_tool/launcher.py`, `detail.py`, `review.py`, `renderer.py`,
  `scope_out.py`, `reprocess.py`, `create.py`, `annotate_render.py`,
  `jira.py`, `review_persistence.py`, `roadmap.py` (each with a private
  `_reject_unmatched_*_fence`-shaped function), plus three inline
  reimplementations in `cli/run_cmd.py` (x2) and `cli/authoring.py` and
  `cli/scope_review_cmd.py`.
- **Symptom:** a `/code-review` pass flagged that every one of these reads
  plan/source text, strips frontmatter (via either `scope_fence._strip_frontmatter`
  or `parser._split_frontmatter` — the two disagree on trailing whitespace,
  see the fixed `reprocess.py` case in `be28de96`), checks
  `_fenced_code_spans(...).unmatched_opening`, and raises a module-local
  error type with near-identical wording. This is a **resemblance
  observation, not verified evidence** — no AST-normalized comparison has
  been run, per this repo's CLAUDE.md consolidation-entry rule ("a
  consolidation entry must carry machine-verified evidence, never a
  resemblance"). A sibling duplication exists one level down too: the
  "exclude a regex match that falls inside a fenced span" filter idiom
  (`start <= match.start() < end for start, end in spans`) is independently
  hand-written at least five times (`parser.py:_is_outside_spans`,
  `detail.py:_h2_matches_outside_fences`, inline in `create.py`'s
  `_patch_plan_body_section`, inline in `jira.py`'s
  `_run_grade_detail_missing_sections`, inline in `reprocess.py`'s
  `_substitute_todo_sections` — the last one's own comment admits it's
  deliberately "mirroring" rather than sharing the logic). Any consolidation
  pass on the outer check should fold this inner one in too rather than
  treat them separately, since they're the same primitive at two call
  depths.
- **Confirmed, not just hypothesized:** round 4 of the same review
  reproduced the "naive merge onto the lenient variant would reopen that
  exact bug" risk directly — `launcher.py:run_step` (the highest-traffic
  guard site: `_reject_unmatched_plan_fence` via the lenient
  `scope_fence._strip_frontmatter`, immediately followed by
  `parse_plan(plan_path)` via the strict `parser._split_frontmatter` on the
  same `plan_path`, moments later in the same call) has the identical
  sequential-disagreement shape `reprocess.py` had — a closing `---` line
  with trailing whitespace passes the guard, then fails the strict reparse
  with a generic `ParseError` instead of the guard's own clear "unmatched
  opening code fence" message. `create.py`, `detail.py`, `scope_out.py`, and
  `cli/run_cmd.py` share the identical shape (each guards then reparses the
  same `plan_path` shortly after). Left unfixed for now rather than patched
  five more times, narrow-style: the outcome is a confusing error message,
  not silent corruption or a silent bypass (the file is still correctly
  rejected, just with the wrong diagnostic) — lower severity than every
  other finding this session fixed directly, and fixing it site-by-site
  would only add five more near-duplicates to the very set this entry is
  about consolidating. Fold the fix into whichever design closes this
  entry (a single correctly-strict shared implementation resolves both the
  duplication and this disagreement at once) rather than patching it ad hoc.
- **Fix:** not yet designed. Before proposing a merge: (1) run the same kind
  of AST-normalized identity check BACKLOG #79 required (normalizing
  docstrings, function/parameter names) to get an actual count of
  byte-for-byte-equivalent bodies, covering both the outer "reject unmatched
  fence" check and the inner "exclude matches inside fenced spans" filter;
  (2) for each pair the check groups, verify neither is doing something a
  shared helper would silently drop — in particular, a shared implementation
  must use the *strict* (`parser._split_frontmatter`-equivalent) frontmatter
  boundary, per the confirmed `launcher.py`/`create.py`/`detail.py`/
  `scope_out.py`/`cli/run_cmd.py` disagreement above, not the lenient one;
  (3) note any site that is deliberately scoped to a subset of modes/callers
  (e.g. `launcher.py`'s guard fires only for `mode in MUTATING_MODES`) as a
  do-not-merge look-alike, not an oversight to fix by merging.
- **Approach:** direct, once the identity check above is done and produces a
  real mergeable set — do not merge on resemblance alone.
- **Origin:** 2026-09-02/03, `/code-review high` rounds 2, 4, and 5 on the
  fence-guard-class fix (`be28de96` onward). Round 5 independently
  reconfirmed the same `launcher.py`/`detail.py`/`scope_out.py` disagreement
  shape with concrete line numbers, and put the inner "exclude fenced
  spans" duplication count at 6 sites (adding `scope_fence.py` itself and a
  structurally-equivalent copy in `parser.py` to the five already listed
  above) — consistent with, not a new finding beyond, what's recorded here.

### `renderer.py` hardcodes `mode == "run"` instead of referencing `launcher.MUTATING_MODES`

- **Files:** `plan_tool/renderer.py:render_prompt` (the unmatched-fence
  guard's mode check); `plan_tool/launcher.py:MUTATING_MODES`.
- **Symptom:** not currently a live bug — `MUTATING_MODES` contains only
  `"run"` today, so the two checks agree. But `renderer.py`'s guard
  hardcodes the string literal instead of referencing the frozenset the
  rest of the codebase treats as the single source of truth for which
  modes mutate (`launcher.py`'s own test-authoring gate, done-marking, and
  advancement all key off it). If a second mutating mode is ever added to
  `MUTATING_MODES`, `renderer.py`'s check silently fails to pick it up.
- **Fix:** have `renderer.py` import and check `mode in MUTATING_MODES`
  instead of `mode == "run"`. Blocked on a real cycle, not just tidiness:
  `launcher.py` already imports `DetailGradeError`/`render_prompt` from
  `renderer.py`, so `renderer.py` importing `MUTATING_MODES` back from
  `launcher.py` would be circular. Needs `MUTATING_MODES` moved to a leaf
  both modules can import (or an equivalent restructure) before this can
  land safely.
- **Approach:** direct, but gated on the import-cycle fix above — not a
  drop-in one-liner despite looking like one.
- **Origin:** 2026-09-02, `/code-review high` round 4 on the fence-guard-class
  fix.

### `ruff check` reports an undefined name, `Plan`, in `tests/cli/test_completeness_cmd.py`, so the code check fails on that file even though its tests pass

- **Promoted:** IPPT-5 (2026-09-24)

### `install-skill`'s Phase 1/Phase 2 recompute a resolved path and read source bytes redundantly

- **Files:** `plan_tool/cli/skill_cmd.py:cmd_install_skill`, `_classify_dest`.
- **Symptom:** `source.resolve()` is computed once in `_classify_dest`
  during Phase 1 and again in Phase 2 for a symlink write; on a
  collision/mode-switch `--copy` write, `_same_bytes` reads the source's
  bytes during Phase 1 classification and `atomic_write_bytes` reads them
  again to write. No correctness issue — both files are small and read
  once per invocation — pure avoidable redundancy.
- **Fix:** thread Phase 1's already-resolved path and already-read bytes
  forward into Phase 2 instead of recomputing, most naturally by having
  `_classify_dest` return the resolved source path (and, for the `--copy`
  case, the bytes it already read) alongside the status.
- **Approach:** direct.
- **Origin:** 2026-09-17, `/code-review high` (round 4) on the
  `skill-router-and-shared-reference` plan.

### `_classify_dest`'s "collision" status discards the "is a directory" fact it already computed

- **Promoted:** IPPT-12 (2026-09-27)

### `docs/TRACKING.md` and `docs/explanations/lessons-learned.md` still describe a `--strict-intent` safety check that was deleted in May 2026, so they tell readers a safeguard exists that does not

- **Promoted:** IPPT-6 (2026-09-24)

### No fixed `producer_slug` prefix can structurally rule out a sidecar-directory collision with a `register`-adopted plan

- **Files:** `plan_tool/model_response_sidecar.py:store_model_response_sidecar`
  (the shared `.plan-tool/parse-failures/<producer_slug>/` directory
  convention); `plan_tool/roadmap.py:record_model_failure_receipt` (the
  `producer_slug=f"_roadmap/{slug}"` namespace root);
  `plan_tool/launcher.py:_record_step_failure_receipt` (the `_run/{slug}`
  namespace root, the same leading-underscore scheme, added 2026-10-13);
  `plan_tool/detail.py:
  _log_parse_failure` (`producer_slug=_plan_slug(plan_path)`);
  `plan_tool/roadmap_candidate_run.py` (`receipt_dir` built from
  `logger.slug` directly); `plan_tool/cli/manifest.py:cmd_register`;
  `plan_tool/locator.py:slug_from_filename`.
- **Symptom:** `detail.py`/`roadmap_candidate_run.py` write parse-failure
  sidecars flat at `.plan-tool/parse-failures/<plan-slug>/`, sharing that
  parent directory with `roadmap.py`'s `_roadmap/<roadmap-slug>/` receipts.
  `SLUG_RE` (`^[a-z0-9][a-z0-9-]*[a-z0-9]$`, `create.py:221`) is enforced
  only inside `create`'s own slug-minting path; `cmd_register` (the
  documented way to adopt an on-disk plan file `create` didn't mint) only
  requires `parse_plan()` to succeed, never validates the resulting slug.
  `slug_from_filename()` (`locator.py:669`) derives a plan's slug from its
  bare filename stem with no character restriction once the optional
  `<digit>-` prefix is stripped, so `cp some-plan.md _roadmap.md &&
  plan-tool register _roadmap.md` registers a plan whose slug is literally
  `_roadmap`, colliding with the namespace root chosen specifically to rule
  this out (round 2 of a `code-review-loop` pass on
  `handoffs/2026-09-22-roadmap-model-failure-receipts-code-review.md`
  chose `_roadmap` believing no valid slug could start with `_`, which is
  true for every `create`-minted slug but not for a `register`-adopted
  one). No fixed literal namespace-root string can close this: `register`'s
  slug space is bounded only by "valid filename, minus an optional numeric
  prefix," so any prefix chosen from that same space can always be defeated
  by a suitably-named registered file — this is the same shape as a
  positional/pattern-exclusion boundary rather than a structural one.
- **Fix:** either (a) validate a `register`-adopted plan's derived slug
  against `SLUG_RE` at registration time (closes the gap for every producer
  that assumes a plan slug is `SLUG_RE`-shaped, not just this one, but is a
  behavior change to `register` itself with its own compatibility
  questions for already-registered plans), or (b) stop sharing
  `.plan-tool/parse-failures/` between plan-slug-keyed producers and
  roadmap-family receipts — e.g. nest roadmap's model-failure sidecars
  under `.plan-tool/runs/<slug>/`, a directory already exclusively owned by
  run-log infrastructure and never written to by `detail.py`/`create.py`/
  `roadmap_candidate_run.py`'s parse-failure convention. Both require
  touching call sites or contracts outside the `roadmap-model-failure-
  receipts` plan's scope (detail.py's `.plan-tool/parse-failures/<plan-
  slug>/` path convention is explicitly pinned by that plan's own step 1).
- **Approach:** `plan-tool` — open design choice (which of (a)/(b), and
  whether the residual risk is worth either given it requires a
  deliberately-crafted `register`-adopted filename).
- **Origin:** 2026-09-22, `/code-review high` round 3 of the
  `code-review-loop` pass on `handoffs/2026-09-22-roadmap-model-failure-
  receipts-code-review.md`, after rounds 1 and 2 each narrowed but did not
  close the same collision.

### `CLAUDE.md`, `TESTING.md`, and backlog entry #190 cite a reconcile prompt, `prompts/reconcile.md`, that has never existed in this repository, so readers cannot find the rules they describe

- **Files:** `CLAUDE.md:226`; `TESTING.md:245` (the "Impact-weighted apply
  triage" row); `BACKLOG.md:3407` and `:3455` (entry #190).
- **Symptom:** each cites `prompts/reconcile.md`. No file has that name, and git
  history shows none at that path. What the citations describe lives elsewhere.
  The refusal of scope-narrowing and criterion-softening edits that `CLAUDE.md`
  and #190 name is in `plan_tool/prompts/detail-reconcile.md` (lines 107-112;
  the `status`/`status_note` flip is at line 78). `TESTING.md`'s row says the
  prompt asks for "Impact/Complexity Decision-block fields", but the triage tags
  are an inline `(impact=..., complexity=...)` parenthetical asked for by
  `plan-audit.md` (line 344) and `run-reconcile.md` (line 116). The same row
  also cites a test class, `TestDecisionImpactComplexity`, that does not exist
  (`TestApplyTriage` is at `tests/test_review.py:13513`). Backlog entry #189
  already lists `TESTING.md`'s citation among its dead citations.
- **Fix:** point each citation at the file that holds the text, checking each
  against that file before editing: `detail-reconcile.md` for the refusal list,
  `plan-audit.md` and `run-reconcile.md` for the triage tag. In the `TESTING.md`
  row, also replace "Decision-block fields" with the inline tag and the missing
  test class with one that exists. `CLAUDE.md` is architect-reviewed (its own
  header), so that edit goes through pull-request review. If #189 lands first,
  drop the `TESTING.md` part here.
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `experienced` — the
  `TESTING.md` fix changes what the row says about how triage behaves, not only
  a path.
- **Approach:** `direct` — four sites; no test pins these strings.
- **Origin:** 2026-09-24, found while writing the IPPT-6 ticket, whose fence
  cites `detail-reconcile.md` because `CLAUDE.md`'s file does not exist.

### Six code comments say the reconcile prompts ask for a `## Decision` block and put the triage tags in it, but no prompt does either

- **Promoted:** IPPT-8 (2026-09-25)

### A same-batch relation with a multi-typed target can misattribute its refusal reason when two added rows collide on one id

- **Severity:** MINOR
- **Files:** `plan_tool/roadmap_candidate.py:_same_batch_added_endpoint_identity`.
- **Symptom:** `_RELATION_ENDPOINT_IDENTITIES[RelationKind.CONSTRAINT_ANCHOR]` now lists three acceptable
  `(artifact, row type)` pairs (`EntityRow`, `BusinessRuleRow`, `WorkflowRow`, all in `domain`). If a same-batch
  delta adds two different eligible row types sharing the same row id (e.g. an `EntityRow` and a `WorkflowRow`
  both named `"x"`), `identities` now has more than one entry where the pre-fix single-pair design could only ever
  produce one, so `exact_additions` can match both and `len(exact_additions) != 1` refuses the relation with
  `"relation-authority"`/`"unauthorized-addition"` instead of the more accurate `"duplicate-row-id"` that
  `check_duplicate_row_ids` would report — that gate runs after `_validate_relation_authority` in
  `materialize_candidate`'s existing ordering, unchanged by this fix. The malformed delta is refused either way; only
  the reported reason is wrong.
- **Fix:** not attempted here — the accurate fix means either reordering `check_duplicate_row_ids` ahead of relation
  authority (an ordering decision affecting every other refusal in between) or duplicating id-collision detection
  locally, and the current fail-safe (wrong label, correct refusal) doesn't warrant either yet.
- **Approach:** `plan-tool` — needs a decision on gate ordering, not a local patch.
- **Origin:** 2026-09-28, `/code-review high` round 2 on the `roadmap-candidate-same-batch-relations` post-run
  review, surfaced by the `CONSTRAINT_ANCHOR` multi-type fix itself.

### The unsinked-call warning names the rate-limit retry loop instead of the call that ran

- **Severity:** MINOR
- **Files:** `plan_tool/shell.py:_caller_outside_shell` (and its caller
  `_warn_unsinked_call`); `plan_tool/rate_limit_loop.py` (the frame it names);
  `tests/test_shell.py` (the existing `_caller_outside_shell` test).
- **Symptom:** the warning promises to name "the actual call site"
  (`_caller_outside_shell`'s docstring), but it returns the nearest frame
  outside `shell.py`. A call routed through the rate-limit retry loop reports
  that frame, `rate_limit_loop.py:145`, and `phase` is the generic
  `claude_invoke`; neither identifies which call was unsinked. Observed on two
  `plan-tool create` runs with an explicit slug (2026-10-01 and 2026-10-02): both
  printed `claude call at rate_limit_loop.py:145 (phase='claude_invoke')` right
  after the distill step, and the warning cannot say whether that call is the
  distill pass, the slug proposal, or another. The gap BACKLOG #177 tracks
  therefore cannot be located from the warning's own output.
- **Fix:** skip `rate_limit_loop.py` frames (and any other retry/transport
  frame that sits between `shell.py` and the caller) when walking the stack, so
  the warning names the first frame owned by the code that asked for the call.
  Add a test that a call routed through the loop names its caller, beside the
  existing `test_shell.py` check.
- **Approach:** `direct`; readiness `ready`; tier `beginner` — one module plus
  its test, the acceptance check is the new test, and the existing
  `_caller_outside_shell` test is the precedent.
- **Origin:** 2026-10-02, tracing the warning in the `candidate-narrative-review-evidence`
  `create` log.

### A completeness report prints every conceptual-correctness finding twice, once in its own section and again in the embedded grouped report

- **Files:** `plan_tool/completeness_report.py:build_report_md` (the
  `## Conceptual correctness — fix these first` section at `:1914` and the
  `## Full grouped report` embed at `:2065`), and
  `plan_tool/cli/completeness_phases.py:_render_grouped_report` (`:1601`),
  whose `### Correctness (run these first)` block renders the same set.
- **Symptom:** in Integration's
  `plan-details/chat-output-streaming/reports/20261010-140834-completeness.md`,
  lines 40 and 76 are the same `[message-delivery-state-finality]` finding,
  word for word. A reader counts two findings where there is one, and a
  session triaging the report can apply the same edit twice.
- **Fix:** render each finding once. The grouped report embedded by
  `build_report_md` omits its correctness block and points to the top-level
  section; the standalone grouped report keeps it.
- **Approach:** direct.
- **Route:** direct · **Readiness:** ready · **Tier:** beginner.
- **Origin:** Integration `integration-aidlc-mvp` nine-plan roadmap-to-plan run, 2026-10-10.

### A partially edited protected References block is restored as a second full copy

- **Files:** `plan_tool/create.py` — `_restore_materialized_evidence_sections` (the `References` branch) and `_references_present`; the render-time check in the plan-body renderer uses the same predicate. Existing tests start at `tests/test_create.py:23762`.
- **Symptom:** when a later writer edits one line of a protected `## References` block, `_references_present` no longer finds the seed block as contiguous verbatim lines, so the restore appends the whole seed block after the existing section. With a three-bullet seed and the third bullet edited, the plan carries all three seed bullets twice: the two unedited ones identically, the third in edited and original form. Nothing is dropped.
- **Fix:** none applied. The block-integrity rule (a protected block is never dropped or split) stays. Decide whether the restore appends only the seed lines missing from the existing section, or leaves the edited block alone when its bullets are a superset or edit of the seed's; pin the chosen behavior with a test on the edited-line input. Review rounds 2 and 4 of PR #107 pulled toward line-level append and round 3 toward block integrity, so settle the invariant before patching.
- **Approach:** direct, after the invariant is stated.
- **Route:** direct · **Readiness:** decision-needed · **Tier:** experienced.
- **Origin:** PR #107 branch-wide `/code-review`, 2026-10-16; accepted then as a known limit, filed 2026-10-19 after reproducing the whole-block duplication. Closed with BACKLOG #496.

### Roadmap promotion summary names the nested destination even for legacy publications

- **Files:** `plan_tool/cli/roadmap_cmd.py:_render_apply_outcome`; `tests/cli/test_roadmap_cmd.py`.
- **Symptom:** the success summary always says promotion goes to `docs/implementation-plans/plan-seeds/`, while detailed rows and create handoffs use each real destination. A legacy recorded publication can retain root `plan-seeds/`, making the summary misleading.
- **Fix:** render a destination-neutral summary or derive it from actual promotion results; preserve detailed paths and all publication semantics. Cover legacy and nested outcomes.
- **Approach:** direct; **Readiness:** ready; **Tier:** working.
- **Scope contract:** rendered promotion summary and focused tests only; no seed moves, storage/provenance changes or path-policy redesign. Verify existing rendering tests before applying a fix.
- **Evidence:** `_render_apply_outcome` contains the unconditional nested-path string; `plan_tool/seed_paths.py:published_seeds_dir` retains legacy roots. Static confirmation only; this task changes no runtime code.

## ROADMAP

Owner-tracked. The `roadmap` verb is experimental work the
project owner develops on their own schedule. The lead does not promote these
entries to Jira, and the team's drain order (BUG, then RISK, then MINOR) does
not include them.

- **What belongs here:** an entry that
  [`docs/TRACKING.md`](docs/TRACKING.md#roadmap-boundary) calls roadmap-owned.
  The definition and its case table live there, so it has one authority.
- **Deliberately not moved:** an entry that touches roadmap code *and* shared
  code stays in its severity section, because a defect in shared code is team
  work. Request the owner's review explicitly for its roadmap part.
- **Severity:** each entry here carries its own **Severity** line, because the
  section no longer states it.

### Incomplete immutable lifecycle journals can permanently block a resumed proposal, review, or promotion

- **Severity:** BUG
- **Files:** `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication`,
  `plan_tool/roadmap_version_promotion.py`, `plan_tool/roadmap_candidate_run.py`,
  `plan_tool/roadmap_candidate_review.py`,
  `plan_tool/roadmap_decision_settlement_enrolled.py`, and their focused
  lifecycle/recovery tests.
- **Symptom:** a review-seal promotion interrupted before its selector changes,
  and candidate proposal, candidate review record, or answer-bound replacement
  publications interrupted after an accepted head exists, leave a
  `PendingGeneration` that the enrolled recovery path cannot safely recognize.
  The enrolled decision-settlement writer's own `"decision-settlement"`
  `PendingGeneration` kind is another instance of the same shape: interrupted
  before its selector swap, it is refused as `journal-unrecoverable` and left
  in place, with no in-tool repair, exactly like the promotion and candidate
  shapes above. Candidate writers do not invoke recovery before retrying. The
  resulting journal blocks every later lifecycle write for that slug. An
  enrolled roadmap carrying one of these journal shapes has no in-tool path
  back to a retryable lifecycle state; this is an availability failure, not
  merely a declined recovery.
- **Fix:** define and validate each exact writer-produced promotion and
  candidate generation shape, including the promotion's seal and candidate
  bindings, then let the relevant lifecycle entry recover only a wholly old,
  wholly new, or recorded mixed state. Leave an unknown, forged, or unrecorded
  member state untouched and refused.
- **Approach:** `plan-tool` — this is a multi-module persistence contract with
  several immutable record shapes. It must not become a general journal
  ownership framework, repair command, or legacy-writer migration.
- **Origin:** 2026-09-01 code-review findings 2 and 4 for
  `roadmap-immutable-candidate-versions`; the same review found the narrow
  root and feedback-reopen recovery defects that were fixed in the current
  review batch.
- **Status:** deferred pending final sign-off on #328. Arc assignment remains
  intentionally unassigned because another branch is updating backlog-arc
  documentation structure; assign it only after that sign-off.

### An enrolled roadmap's candidate promotion never re-checks a settled decision against its predecessor

- **Severity:** BUG
- **Files:** `plan_tool/roadmap_impact_snapshot.py:_evaluate_full_roadmap_gates`,
  `plan_tool/roadmap_gates.py:check_settled_decisions`, and their focused
  gate/impact-snapshot tests.
- **Symptom:** `_evaluate_full_roadmap_gates` — the shared evaluator
  `check_complete_roadmap_gates` runs, which backs `promote_review_seal`'s
  `_recheck_stored_candidate` on every enrolled candidate promotion —
  unconditionally builds each stage's `ArtifactEnvelope` with
  `predecessor=None`. `check_settled_decisions` returns immediately whenever
  `predecessor is None`, so it is a permanent no-op on this path: nothing
  stops an ordinary candidate proposal and promotion from changing a
  Roadmap-derived `settled` decision's `id`, `status`, `chosen_option`, or
  `anchor` back once it is live on an enrolled roadmap. The parallel
  inherited-decision check (`check_inherited_decisions`) is unaffected — it
  keys off `envelope.carried_decisions`, a separate argument the caller does
  populate, not `predecessor` — so this gap is specific to Roadmap-derived
  settled decisions on the enrolled lineage. It is already live, not
  dormant: the domain stage prompt already instructs the model to author a
  decision directly as `settled` during ordinary authoring ("Use `settled`
  otherwise"), `roadmap_candidate.py` already accepts a `status` change in
  an ordinary candidate delta with no gating, and an un-enrolled revision
  can already newly settle a decision — every one of those settled rows is
  equally unprotected once the roadmap is enrolled. No operator-confirmed
  route to `settled` has existed until now, but the gap in
  `check_settled_decisions` itself predates and does not depend on one.
- **Fix:** give the enrolled candidate-validity check a real predecessor —
  built from the currently accepted version's own artifacts — for the stage
  gate set that runs `check_settled_decisions`, without changing the
  no-fallback, no-substitution contract `check_complete_roadmap_gates`'s
  docstring already commits to. Verify no other predecessor-keyed gate
  changes behavior for an ordinary (non-settlement) candidate promotion once
  a real predecessor is threaded through.
- **Approach:** `plan-tool` — this changes the shared full-roadmap gate
  evaluator every candidate promotion runs through; needs its own audited
  plan rather than a bundled fix inside an unrelated feature.
- **Origin:** 2026-09-18, found by the bare-plan completeness audit round 3
  for `roadmap-decision-settlement` (BUG_BACKLOG "Approved roadmap
  decisions cannot transition from `pending` to `settled`") while designing
  that plan's enrolled-lineage settlement route; round 5 corrected the
  initial "dormant until this plan ships" framing — the gap is already
  live against existing settled-decision producers (ordinary stage
  authoring, ordinary revision, and an ordinary candidate delta), not one
  this plan's route is first to reach. That plan documents this as a
  known, pre-existing limit rather than absorbing the fix.

### Reverting a settled decision to `pending` by hand fails source admission, same as the forward hand-edit

- **Severity:** BUG
- **Files:** `RUNBOOK.md`, `plan_tool/roadmap_gates.py` (the
  `check_settled_decisions` violation message), and any test covering
  operator-facing un-settle guidance.
- **Symptom:** `RUNBOOK.md` tells a reviewer who wants to un-settle a
  decision to "Confirm it in place, or set its status to `pending`", and
  `check_settled_decisions`'s own violation message says "the reviewer has
  to set decision … to status 'pending' … first" — both describing a
  direct hand-edit of the artifact's `status` field. Exactly like the
  forward direction (`docs/how-to/roadmap.md` §5's "edit `status` to
  `settled`", closed by `roadmap-decision-settlement`), that edit changes a
  field `canonical_projection` includes, so the stage no longer matches its
  recorded `.roadmap-baselines` entry and re-entry refuses it
  ("source changed outside reviewer feedback"). Both documented
  instructions lead to a stage every route already refuses.
- **Fix:** correct both messages to describe the actual working recovery
  (revert the edit, matching pre-edit bytes, so the stage matches its
  baseline again, then use whatever confirmed route applies) or add a
  narrow, confirmed un-settle route — the reverse of
  `roadmap-decision-settlement`'s new action — and point both messages at
  it once it exists.
- **Approach:** direct for the documentation correction; `plan-tool` if a
  confirmed un-settle route is built, since it is a new narrow lifecycle
  action with its own refusal surface, not a doc fix.
- **Origin:** 2026-09-18, `roadmap-decision-settlement` bare-plan audit
  round 6, finding `unsettle-hand-edit-instructions`. That plan defers
  building an un-settle route (BACKLOG-worthy on its own, not filed here
  since no one has asked for it yet) and does not correct these two
  messages, since neither describes the forward settlement action it adds.

### Enrolled decision settlement folds a corrupt sibling artifact member into an ordinary write-failed refusal

- **Severity:** BUG
- **Files:** `plan_tool/roadmap_decision_settlement_enrolled.py`,
  `plan_tool/roadmap_decision_settlement_run.py`, `plan_tool/roadmap_versions.py`
  (`load_accepted_head`, `_read_member_bytes`).
- **Symptom:** both settlement runners deliberately let
  `DecisionSettlementSourceCorruptError` (an unparsable *selected* accepted
  version member) propagate to the top-level unexpected-error handler
  instead of becoming an ordinary refusal, but `RoadmapVersionError` itself
  stays in the ordinary catch-all — correctly, for its one pinned use (a
  malformed accepted-head *selector* file must stay `write-failed`, per
  `test_invalid_accepted_head_is_write_failed_before_recovery`). The same
  exception type is also what `roadmap_versions.py:_read_member_bytes`
  raises when a *sibling* stored artifact member (any of the three not
  being settled) fails its digest verification or isn't valid UTF-8 —
  genuine store corruption, exactly the class the propagate-don't-swallow
  treatment exists for. Both cases share one exception type with nothing
  structural distinguishing them short of parsing the message string, so
  the corrupted-sibling-member case is currently indistinguishable from the
  malformed-selector case and silently becomes a generic `write-failed`
  too.
- **Fix:** give `load_accepted_head`'s own raise sites (dangling selector
  symlink, malformed/non-canonical selector JSON, slug mismatch) a distinct
  `RoadmapVersionError` subclass, purely additive so every existing bare
  `except RoadmapVersionError` elsewhere in the codebase is unaffected; have
  both settlement runners' propagate-carve-out catch the base
  `RoadmapVersionError` while excluding (or specifically catching-and-
  refusing) only the new selector-specific subclass.
- **Approach:** `plan-tool` — the new subclass lives in `roadmap_versions.py`,
  a foundational module several other features depend on; even though the
  change is additive, it needs its own audited plan rather than a bundled
  fix inside an unrelated feature's code-review pass.
- **Origin:** 2026-09-18, `roadmap-decision-settlement` post-run
  `/code-review` round 4 (re-confirmed round 7). No live trigger without
  actual on-disk corruption of a stored version member; deferred rather
  than fixed in the same pass given the shared-module blast radius.

### Decision settlement's post-receipt-commit recheck can crash without reporting the already-committed receipt id

- **Severity:** BUG
- **Files:** `plan_tool/roadmap_decision_settlement_run.py`,
  `plan_tool/roadmap_decision_settlement_enrolled.py`.
- **Symptom:** after the settlement receipt is durably committed, both
  runners rebuild the candidate a second time (`decision_settlement_candidate_is_current`)
  to check the source is still current. That rebuild calls the same
  `build_decision_settlement_candidate` the initial preflight does, so it
  can raise the same `DecisionSettlementContentIntegrityError` the initial
  call can — deliberately not caught anywhere (see the "settlement folds a
  corrupt sibling artifact member" entry above for why this class of
  exception must propagate rather than become an ordinary refusal). The
  enrolled runner's own post-receipt `_admission_blocks_settlement` call
  can similarly raise `CandidateProposalError`. Both are correctly excluded
  from the write-failed carve-out — that part is deliberate and correct —
  but propagating loses the `receipt_id` that the result would otherwise
  carry: the top-level unexpected-error handler prints the exception's
  message, never the receipt id already sitting in local scope.
- **Fix:** thread the already-committed `receipt_id` into whatever
  propagates from this point, e.g. wrapping the internal-consistency
  exception with the receipt id attached, or having the top-level handler
  accept an optional structured payload — needs a design decision on the
  right mechanism, not a narrow patch.
- **Approach:** `plan-tool` — touches the shared internal-consistency
  exception contract and the CLI's top-level error handler, not scoped to
  one file.
- **Origin:** 2026-09-18, `roadmap-decision-settlement` post-run
  `/code-review` round 7. Requires a narrow race (an out-of-band artifact
  edit between the initial candidate build and the post-receipt recheck)
  compounded with a genuine settlement-logic bug to trigger; the receipt
  itself is never lost (still durably committed, discoverable via git
  history or the evidence namespace) — only the CLI's crash output doesn't
  surface it.

### `run_roadmap`'s primary success path can discard a fully-completed `RoadmapResult` if the writer guard's own teardown then fails

- **Severity:** BUG
- **Files:** `plan_tool/roadmap.py:run_roadmap`, `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard`
  (`_release_writer_lock`/`os.close`), `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`.
- **Symptom:** `run_roadmap`'s `return _run_roadmap(...)` sits inside
  `with _roadmap_writer_owner(plans_dir, slug) as writer_token:`. If every
  stage completes and `_run_roadmap` returns a successful `RoadmapResult`,
  the `with` block's normal exit still has to run `roadmap_writer_guard`'s
  teardown; when the guarded body raised nothing (`body_error is None`),
  that teardown re-raises a bare `OSError` verbatim on a lock-release or
  `os.close` failure. Python discards the pending return and propagates
  that `OSError` instead. It isn't `RoadmapWriterGuardError`/
  `RoadmapRevisionPublishError`, so `run_roadmap`'s own except clause
  doesn't catch it; it reaches `cmd_roadmap`'s
  `except (OSError, RoadmapEnvironmentalError)` handler, which — finding no
  `roadmap_stage_started` attribute — resolves via its `default=True` to
  `"error"`/rc=1, even though every stage finished and the artifacts are
  already on disk.
- **Fix:** not a narrow patch. The lost `RoadmapResult` can't be recovered
  once `__exit__` has already discarded it, so the fix is a disposition
  decision, not a bug fix: `ROADMAP_FORMAT.md`'s terminal-disposition matrix
  currently has no row for "all stage work completed, then an unrelated
  teardown step failed" — its "Expected failure after start" row
  (`error`/rc=1) is written for "the run did not finish," which is false
  here. Resolving this needs either a documented new row (and the matching
  `run_roadmap`/`cmd_roadmap` mechanism to reach it, e.g. capturing the
  result before the `with` exits and tagging a teardown-only failure the
  way `_preflight_prompt_error` tags a not-yet-started one) or an explicit
  decision that `error`/rc=1 is an acceptable, intentionally conservative
  disposition for this edge case — either way, the matrix and the code need
  to agree on paper, not just by accident.
- **Approach:** `plan-tool` — touches a documented cross-file contract
  (`ROADMAP_FORMAT.md`) plus `run_roadmap`/`cmd_roadmap`, not scoped to one
  file.
- **Origin:** 2026-09-21, `/code-review high` round 2 of the
  `2026-09-21-unpushed-main-code-review` ledger. Predates this ledger's
  entire reviewed range (present in `origin/main` already); surfaced by
  analogy to a sibling bug the same round found and fixed in
  `_cmd_roadmap_materialize`'s own writer-guard teardown handling. Requires
  a transient lock-release/`close` failure landing on an otherwise fully
  successful run to trigger — narrow, but real.

### A mid-batch writer-token race changes telemetry/outcome classification in `_materialize_seed_rows`, untested either way

- **Severity:** RISK
- **Files:** `plan_tool/roadmap.py:_materialize_seed_rows` (the three
  except branches around its `materialize_and_diff_one_plan(...)` call),
  `_refresh_roadmap_seeds` (its caller).
- **Symptom:** before the `RoadmapWriterGuardError` normalization sweep,
  a writer token that raced stale *between* a batch's own preflight and
  a later row's independent, redundant guard check inside
  `materialize_and_diff_one_plan` propagated as a raw
  `RoadmapWriterGuardError`, caught by `_materialize_seed_rows`'s
  `except BaseException:` branch — recording a
  `run_logger.attempt_failed(..., failure_kind="materialize-error")`
  event and leaving `phase_outcome` at its default `"error"`. Now that
  the inner guard call converts it to `RoadmapError` before it
  propagates, the same race instead hits the `except (RoadmapError,
  RoadmapArtifactError):` branch — no `attempt_failed` event, and
  `phase_outcome` becomes `"preflight-refused"`/`"row-refused"` (the
  classification meant for an ordinary, expected per-row refusal, not
  an infrastructure race). The batch still correctly fails and
  re-raises either way; only the telemetry label and outcome string
  differ. Confirmed by direct execution (`/code-review` gap-sweep); no
  existing or new test exercises this nested/mid-batch race path on
  either side of the change.
- **Fix:** needs a considered choice, not a quick patch — e.g. inspect
  `exc.__cause__` in the `(RoadmapError, RoadmapArtifactError)` branch
  and route a `RoadmapWriterGuardError` cause through the same
  `attempt_failed`/`"error"` treatment as `BaseException`, or accept
  the reclassification as more accurate (a stale token really is a kind
  of refusal) and document it. Add a test pinning whichever
  classification is chosen before closing this.
- **Approach:** direct, but needs a design decision on the "refused"
  vs. "errored" boundary for this specific exception at this nesting
  level.
- **Origin:** 2026-09-02 `/code-review` gap-sweep on the
  `RoadmapWriterGuardError` normalization diff.

### The suite fails at random under `-n auto` when `GateCleanCandidate` is validated before its forward references resolve

- **Severity:** RISK
- **Files:** `plan_tool/roadmap_candidate.py` (`GateCleanCandidate`, first
  validated during candidate materialization) and
  `tests/test_roadmap_version_promotion.py`.
- **Symptom:** a parallel full-suite run sometimes fails three or four tests
  in `tests/test_roadmap_version_promotion.py` with
  `pydantic.errors.PydanticUserError: `GateCleanCandidate` is not fully
  defined; you should define `CandidateImpactAtom` (or `Callable`), then call
  `GateCleanCandidate.model_rebuild()``. The module passes 18/18 on its own,
  and the next full run passes. The failure depends on which tests share a
  worker and the order modules get imported in. Observed 2026-09-12 (four
  tests) and 2026-09-14 (three tests). The pre-push hook runs this suite, so
  the flake can block a push at random.
- **What's known:**
  - The module uses `from __future__ import annotations`, so Pydantic
    resolves annotations lazily.
  - `GateCleanCandidate` annotates `impact_atoms` with `CandidateImpactAtom`,
    a type alias defined further down the module.
  - `Callable` isn't imported in the module, so that name comes from a type
    defined elsewhere.
  - The module never calls `model_rebuild()`.
  - Whether a production import order can hit the same error is unverified.
- **Fix:** reproduce the failing import order in a fresh interpreter first.
  Then make `GateCleanCandidate` resolve regardless of import order, and pin
  that with a test that runs the failing order in a fresh interpreter.
- **Approach:** direct once the failing order is reproduced; an
  investigation until then.
- **Origin:** 2026-09-14, full-suite validation of the docs restructure. It
  was first noted on 2026-09-12 as "known suite instability" in the roadmap
  brief-source review handoff, but never filed.

### `validate_draft_seed_content` parses a draft seed's frontmatter boundary twice

- **Severity:** MINOR
- **Files:** `plan_tool/roadmap_gates.py:validate_draft_seed_content`,
  `_draft_seed_references`; `plan_tool/roadmap_artifacts.py:
  parse_draft_seed_provenance`.
- **Symptom:** not a correctness bug — both boundary finders agree on
  well-formed frontmatter — but every draft-seed validation call parses the
  frontmatter/body split twice: once inside
  `parse_draft_seed_provenance` (via `_parse_frontmatter`, which computes
  and discards the body), and again inside `_draft_seed_references` (via
  `scope_fence._strip_frontmatter`) for the same `text`.
- **Fix:** thread the body `parse_draft_seed_provenance` already computed
  through to `_draft_seed_references` instead of re-parsing — needs
  `parse_draft_seed_provenance`'s return shape (or a sibling helper) to
  expose the body, which is a small public-API change to a leaf module
  (`roadmap_artifacts.py`) with its own callers to check.
- **Approach:** direct, low priority — wasted work only, no behavioral
  change.
- **Origin:** 2026-09-02, `/code-review high HEAD~2..HEAD` on the
  `seed-source-references-fallback` sweep.

### `_lift_artifact_text`'s frontmatter search can be misled by a "---" inside an illustrative fenced example in a stage reply's preamble

- **Severity:** MINOR
- **Files:** `plan_tool/roadmap.py:_lift_artifact_text`, `_strip_reply_lines`.
- **Symptom:** flagged three review rounds running (rounds 2, 3, and 4) as
  the same residual gap. `_strip_reply_lines`'s `has_outer_opener` check
  (fixed in rounds 1 and 4 to require a genuinely *unclosed* fence in the
  preamble, not just any line starting with "```") only protects the
  outer-opener decision. `_lift_artifact_text`'s separate "find the first
  literal `---` line" search has no fence-awareness of its own: a preamble
  containing a self-contained illustrative fenced example whose own content
  happens to include a "---"-delimited block, followed later by the real
  artifact's own frontmatter, makes that search lock onto the illustrative
  example's "---" instead. A fence-exclusion fix was attempted and reverted
  in round 4 (see `05a9ff96` era work) because it broke the *common*, tested
  case instead: a genuine whole-reply wrapper (`` ```markdown\n---\n...\n``` ``)
  is itself one *complete* (not unmatched) fenced span once the reply is
  fully wrapped, so "exclude any '---' inside a fenced span" also excludes
  the real frontmatter fence in that far more common shape.
- **Fix:** not yet designed. The real distinguishing property is "the fence
  wraps everything, including the frontmatter" (strip it) vs. "the fence is
  self-contained, unrelated content that happens to precede the frontmatter"
  (don't let it hide the real `---`) — a correct fix needs to tell these
  apart, which a simple "is this position inside any fenced span" check
  cannot. In practice this is a rare, multi-part adversarial shape (preamble
  + a self-closed illustrative example + that example coincidentally
  containing its own "---"), and even when it fires, the stage's own
  `stage.parse()` gate is likely to reject the resulting malformed
  frontmatter and trigger the existing retry loop rather than silently
  publish it — this is why it has been deferred three rounds rather than
  chased into a bigger redesign.
- **Approach:** direct, once a design exists that distinguishes the two
  cases above; needs a design decision first, not just an implementation.
- **Origin:** 2026-09-02/03, `/code-review high` rounds 2, 3, and 4 on the
  fence-guard-class fix.

### The feedback ledger accepts a whitespace-only reviewer request

- **Severity:** MINOR
- **Files:** `plan_tool/roadmap_feedback_ledger.py:ReviewerFeedbackItem._requires_request`;
  `plan_tool/roadmap_feedback_ledger_run.py:submit_reviewer_feedback`,
  `edit_reviewer_feedback`.
- **Symptom:** `_requires_request` rejects only the empty string, so
  `--submit-feedback ... --feedback-request '   '`, or an edit to whitespace,
  creates an open, eligible item whose blank request reaches the candidate
  context as the reviewer's words. Migration already treats
  `not request.strip()` as "no request text" (a blank legacy row imports as a
  closed marker item), and the reopen/edit guard for migrated items uses the
  same predicate, so a reviewer-written item is the one path that still
  accepts it. Not introduced by the `roadmap-versioned-feedback-revision-chain`
  fixes; found while reviewing them.
- **Fix:** reject `not value.strip()` in `_requires_request`, and decide two
  things first: whether a ledger already on disk with a whitespace-only request
  should still load (the schema check also runs at parse time), and how the
  refusal reaches the CLI as one named line rather than a raw validation dump
  (the ledger runner names the row for migration only).
- **Approach:** `direct` — small, one validator plus its tests. Readiness
  `decision-needed` on the load-compatibility question above; Tier `beginner`.
- **Origin:** 2026-09-23, `/code-review high` pass 4 of
  `handoffs/2026-09-23-roadmap-versioned-feedback-revision-chain-code-review.md`.

### `ruff` reports five undefined names in roadmap code and tests (`PendingGeneration`, `Any` twice, `Callable`), so the code check fails though nothing breaks at run time

- **Severity:** MINOR
- **Files:** `plan_tool/roadmap.py:1066,1071` (`PendingGeneration`, in
  `_with_initial_feedback_ledger`'s annotations); `tests/cli/test_roadmap_cmd.py:3784`
  (`Any`, twice); `tests/test_roadmap.py:8521` (`Callable`).
- **Symptom:** `uv run ruff check plan_tool tests` reports each as `F821` (a name
  that is used but never defined or imported). Nothing fails at run time: all
  three modules have `from __future__ import annotations`, so the annotations
  are never evaluated. Only the `ruff` check is red.
- **Fix:** add `PendingGeneration` to the existing
  `from plan_tool.roadmap_source_identity import (...)` at `roadmap.py:181`
  (the class is defined at `roadmap_source_identity.py:110`, and that module
  imports only `roadmap_json`, so there is no import cycle); add
  `from typing import Any` to `tests/cli/test_roadmap_cmd.py`; add `Callable` to
  the `from typing import Any, Optional, Sequence` at `tests/test_roadmap.py:24`.
- **Out of scope:** the other nine `ruff` findings (seven `F811`, two `F841`),
  and the sixth undefined name, in `tests/cli/test_completeness_cmd.py`
  (IPPT-5).
- **Route:** `direct` · **Readiness:** `ready` · **Tier:** `beginner` — the same
  small edit (add an import) at three named files.
- **Where to start:** `roadmap.py:181` and the import lines of the two test
  files.
- **Precedent:** an existing pattern: the import at `roadmap.py:181` already
  pulls sibling names from the same module.
- **Settled decisions:** none.
- **Done when:** `uv run ruff check plan_tool tests` reports no `F821` in these
  three files (the whole-tree count falls by five, from 15 to 10) and the full
  suite is green.
- **Reviewer:** unassigned.
- **Approach:** `direct` — three one-line imports.
- **Origin:** 2026-09-24, found while writing IPPT-5.

### Approving or reviewing a stack of candidates crashes with a raw parser traceback, instead of refusing cleanly, when an earlier candidate's stored files no longer parse

- **Severity:** RISK
- **Files:** `plan_tool/roadmap_candidate_run.py:_require_reproducible_batch_diff` (the
  `except (AttributeError, TypeError, UnicodeDecodeError, ValueError)` around `stage.parse`);
  `plan_tool/roadmap_artifacts.py:RoadmapArtifactError`; and the callers of `candidate_stack_route`:
  `plan_tool/roadmap_candidate_review.py:_stack_is_structural` and `build_candidate_stack_view`,
  `plan_tool/cli/roadmap_cmd.py` (the proposal output and the decision precheck), and
  `plan_tool/roadmap_revision_publish.py:_selected_promotion_is_structural`.
- **Symptom:** before an approval or promotion, `plan-tool` works out whether any candidate in the stack of
  unpromoted candidates (each one is a "hop") stores a structural change. That step, `candidate_stack_route`, loads
  and checks every candidate in the stack, and re-reads each one's stored roadmap files inside a `try` that catches
  `ValueError` but not `RoadmapArtifactError`, which derives from `Exception`. If a stored candidate's files still
  match their recorded digest but today's parser rejects them, that error passes through instead of becoming
  `CandidateProposalError`, the error every caller expects for "this stack cannot be read". A user sees the following.
  `--decide-candidate ... approve` and the `--propose-candidate` output end in a Python traceback instead of the
  message "candidate stack route is underivable" (the stack's route cannot be worked out) and exit status 2.
  `--review-candidate` and `--answer-question` pass the raw error on. `_selected_promotion_is_structural`, the check
  that recovery uses to tell whether an interrupted promotion should have invalidated seed state, passes it on
  instead of returning `None` (unknown), so recovery raises the raw parser error instead of declining. No write
  happens on any of these paths, so the guarantee still holds that a structural change reaches the accepted head
  only through a confirmed approval; only the shape of the refusal is wrong. Not reproduced: it needs a parser
  tightened after the candidate was stored. The same function already turns a parse failure in the candidate's
  source into `CandidateProposalError`; the mismatch predates `roadmap-stack-aware-approval`, which exposes it to
  every candidate in a stack.
- **Fix:** add `RoadmapArtifactError` to that catch tuple (the batch path; the identical tuple on the selector-era
  path is never part of a stack and can stay), and pin it with one test that makes a lower candidate fail to parse
  and asserts the "underivable" refusal at `_stack_is_structural` and the unknown (`None`) result at
  `_selected_promotion_is_structural`.
- **Approach:** `direct` — one tuple entry and one test. Readiness `ready`; Tier `beginner`.
- **Origin:** 2026-09-24, `/code-review high` pass 2 of
  `handoffs/2026-09-24-roadmap-stack-aware-approval-code-review.md` (finding P2.1, low, PLAUSIBLE), deferred by the
  owner.

### Confirmed structural approval contradicts the separate review-seal promotion command

- **Severity:** BUG
- **Files:** `plan_tool/cli/roadmap_cmd.py` (approval and promotion command
  rendering/dispatch), `plan_tool/roadmap_candidate_review.py` (confirmed
  structural approval), `plan_tool/roadmap_version_promotion.py` (review-seal
  promotion), CLI reference/help text, lifecycle documentation, and focused
  CLI/promotion tests.
- **Symptom:** the CLI advertises a two-step lifecycle: confirming
  `--decide-candidate ... --candidate-decision approve --confirm-stack-digest`
  creates a review seal, then `--promote-review-seal <seal>` advances the
  accepted head. In fact, confirmed structural approval already promotes the
  candidate and releases the active-candidate pointer. Its output says
  `promoted version`, and `tests/cli/test_roadmap_cmd.py` asserts that the
  accepted head has advanced immediately after confirmation. A user following
  the documented next command then receives exit 2 with `structural approval
  does not bind the active candidate`, even though the seal and promotion both
  succeeded. Integration Group 2 reproduced this on 2026-09-29: candidate
  `fb1e45b4aa6c786fb8dd8b0e1f5f699b3029e37b2a24285c449bbbed37423c15`, seal
  `216329677fda58b3dd25fa6660fc8726ffd97954bc720c1bbca92f7589223853`, and
  accepted head all identify the same promoted revision.
- **Fix:** preserve the current confirmed-approval behavior as the authoritative
  lifecycle: the digest confirmation seals and promotes atomically. Make
  `--promote-review-seal` recognize a seal whose approved candidate is already
  the accepted head and return exit 0 with an explicit `already promoted`
  result, without rewriting any lifecycle record. Retain the existing refusal
  when the seal is neither currently promotable nor already the accepted head.
  Update CLI help, reference documentation, and rendered approval output so
  they describe the terminal confirmation accurately; do not ask users to run
  a redundant promotion command after confirmation.
- **Verification:** cover a confirmed structural approval that atomically
  advances accepted head and clears the active candidate; then invoke
  `--promote-review-seal` with its seal and assert exit 0, an `already
  promoted` result, and byte-identical accepted-head and admission records.
  Preserve refusal for a seal whose candidate is not the accepted head and no
  longer active. Assert CLI help and lifecycle documentation no longer promise
  a second required promotion step.
- **Approach:** `direct` — reconcile an already-tested atomic lifecycle with
  its stale CLI surface; do not change candidate authority or approval
  semantics.
- **Origin:** Integration Group 2 manual-session-recovery approval on 2026-09-29.

### The single candidate correction still names only the first of several defects that the closed diagnostics do not cover

- **Severity:** RISK
- **Files:** `plan_tool/roadmap_candidate.py:_operation_diagnostics` (the pre-pass that collects every
  operation's defects), `_parse_operation`, and `_parse_optional_ordering`.
- **Symptom:** the pre-pass added by `roadmap-candidate-envelope-diagnostics` reports every missing or unknown
  field, every invalid `row_type`, and every row-body field defect across all operations in one correction. It does
  not check three things that `_parse_operation` checks one operation at a time: a malformed `ordering` entry, a
  `replace-row` whose `row.id` differs from its `row_id`, and a non-string `feedback_id`, `artifact_key`, or
  `row_id`. A reply where operation A carries one of these and operation B carries another therefore gets a
  correction naming only A's defect. The root is a fourth case: `parse_candidate_delta` raises a root key defect
  (a missing `derived_feedback` beside `responses`, or an unknown root key) before the operation pre-pass runs, so a
  reply with a root defect and an operation defect reports only the root one. The retry fixes A, fails on B, and the two-attempt bound is spent. None of the
  three appeared in the stored Integration replies, and none falls in the plan's `missing-field` / `unknown-field` /
  `invalid-row-type` vocabulary, so the plan left them out on purpose. Not reproduced against a live model.
- **Fix:** have the pre-pass also run `_parse_optional_ordering` and the `row_id` / `row.id` comparison and collect
  their messages, keeping the same closed wording (no model text echoed), and collect the root diagnostics without
  raising so the operation pre-pass still runs when `operations` is a list. Pin it with one test that puts two of the
  three defects on different operations and one with a root defect beside an operation defect, each asserting both
  appear in the one correction.
- **Deliberately not:** widening the retry budget, or repairing any of these at parse time.
- **Approach:** `direct` — one pre-pass extension and one test. Readiness `ready`.
- **Origin:** 2026-09-27, `/code-review high` pass 1 of
  `handoffs/2026-09-26-roadmap-candidate-envelope-diagnostics-code-review.md` (findings P1.3 and P2.2, low, PLAUSIBLE),
  deferred.

### `--promote-review-seal` idempotency covers only structural-approval seals, not answered-replacement ones

- **Severity:** BUG
- **Files:** `plan_tool/roadmap_version_promotion.py` (`promote_review_seal`,
  `_load_complete_sealed_candidate`, `_load_reviewed_batch_candidate`, the non-batch
  answered branch), and focused promotion tests.
- **Symptom:** a companion fix made `--promote-review-seal` idempotent for an
  already-promoted `structural-approval` seal (the already-promoted shortcut,
  gated on `seal.decision == "structural-approval"`). The same repeated-promotion
  failure exists for the ordinary `answered-replacement` route
  (`--review-candidate` / `--answer-question` then `--promote-review-seal`):
  `build_active_candidate_pointer_release_generation` runs after any successful
  promotion regardless of `seal.decision`, releasing the active-candidate
  pointer the same way for both. A second `--promote-review-seal` on an
  already-promoted answered-replacement seal falls through the shortcut
  (wrong decision value) into `_load_reviewed_batch_candidate` or the non-batch
  branch, which then sees the released pointer and raises
  `RoadmapVersionPromotionError` — the exact class of failure the structural
  fix exists to prevent, left open for the sibling seal type. No current flow
  auto-invokes promotion for the answered route the way structural approval's
  confirm step does, so this needs a deliberate retry (a script, a network-
  interrupted CLI call) to trigger, not the redundant-documented-next-step
  reflex the structural bug had — traced, not reproduced against a live model.
- **Fix:** extend the already-promoted shortcut to answered-replacement seals.
  Unlike the structural case, the promoted `StoredRoadmapVersion` alone is not
  enough to authorize it: the answered route's slow path
  (`_load_replacement_binding`, `_require_replacement_binding`,
  `_require_final_capsule_binding`, plus the question-inventory/answer
  validation chain) is substantially larger than the structural route's single
  equality block, so a proportionate fix needs its own design pass — not a
  copy of the structural shortcut's shape onto a materially different
  validation surface.
- **Verification:** cover a first successful answered-replacement promotion
  followed by a repeat `--promote-review-seal` on the same seal, asserting
  exit 0 / `already-promoted` and no write; keep the existing refusal for a
  seal that is neither the active replacement nor already promoted.
- **Approach:** `plan-tool` or `direct`, owner's call once scoped — larger than
  the structural fix it parallels.
- **Origin:** `/code-review high` on `run/roadmap-candidate-row-prose-amendments`,
  2026-09-29, traced (not empirically reproduced) and confirmed by reading
  `promote_review_seal`'s release step alongside `_load_reviewed_batch_candidate`
  and the non-batch answered branch.

### The candidate relation-authority check accepts an existing row of the wrong type as a relation endpoint

- **Severity:** BUG (low — the downstream gate still refuses the result)
- **Files:** `plan_tool/roadmap_candidate.py:_validate_relation_authority`
  (`endpoint_identities = predecessor_rows.get(relation.endpoint_id, ())`) and
  `_RELATION_ENDPOINT_IDENTITIES`; candidate relation-authority tests.
- **Symptom:** an endpoint added in the same batch is checked against the typed
  endpoint table, but an endpoint that already exists is matched by id alone,
  whatever its row type. A relation that cites an existing row of the wrong type
  (for example an entity id in an ordering entry's `assumption_targets`) passes
  relation authority and is refused afterwards by its gate with that gate's
  message, not the authority wording that names the expected row type.
- **Evidence:** read from the code during `/code-review high` on
  `fix/roadmap-assumption-target-authority`, 2026-10-09; not reproduced end to
  end. The unresolved-reference refusal names the expected type only when no
  row at all carries the id.
- **Fix:** type the predecessor-side match against `_RELATION_ENDPOINT_IDENTITIES`
  for typed kinds, and reuse
  `_unresolved_relation_detail` for the refusal. Decide first whether an existing
  wrong-typed row should be refused at authority or left to its gate: authority
  refusals stop before any gate runs, so a batch that the gates would repair
  through a companion row edit would become unreachable.
- **Verification:** through the real materializer, a typed relation citing an
  existing wrong-typed row is refused with the expected-type wording while the
  same relation citing a correctly typed row is admitted, for each typed kind;
  `DECISION_ANCHOR` follows the owner-stage-scoped rule in the decision-anchor
  entry below (it is not typed by `_RELATION_ENDPOINT_IDENTITIES`, and it does
  not resolve against any row of any artifact); the existing predecessor-side
  authority tests stay green or are rewritten with their reason stated.
- **Route:** direct · **Readiness:** needs a decision (refuse at authority or at
  the gate) · **Tier:** experienced.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** split from the unresolved-reference refusal entry when it shipped,
  2026-10-09; no fix applied.

### The candidate prompt never states the `draft_seed_path` rule, and a bad value is refused with a misleading UTF-8 message

- **Severity:** BUG
- **Files:** `plan_tool/prompts/roadmap-candidate-delta.md` (and the
  operation-shape examples in `plan_tool/roadmap_candidate_run.py`);
  `plan_tool/roadmap_candidate.py:_assemble_candidate_artifacts`
  (the `except` that returns `render-mismatch`); `plan_tool/roadmap_artifacts.py`
  (the `draft_seed_path` validator, which says `must begin with
  'plan-seed-drafts/' or 'seeds/'`).
- **Symptom:** an added or replaced plan row must carry a string
  `draft_seed_path` beginning `plan-seed-drafts/` or `seeds/`. The candidate
  prompt states neither the field's requirement nor the prefix. A `null` value
  is refused at parse as `candidate field 'draft_seed_path' must be a string`
  without naming the plan; a string with another prefix (`plan-seeds/plan-a.md`,
  this repo's own seed directory, or `x`, or `""`) passes parse and authority,
  then fails render with `render-mismatch: candidate stage rendering cannot bind
  complete UTF-8 evidence`. That wording names no plan and no field, and the
  cause is not an encoding problem. The retry prompt does not carry the
  rejected reply, so the model regenerates without any pointer to the field.
- **Evidence:** Integration run `2026-10-09T16-03-29+00-00-6f1ebc`, attempt 2 sets
  `draft_seed_path: null` on four of its ten added plans. Attempt 1 supplies six
  valid `plan-seed-drafts/…` paths, so the model follows the convention when it
  guesses right. Probe: the real materializer with `plan-seeds/plan-a.md`
  returns the UTF-8 refusal while the parser's own error names the prefix rule.
- **Fix:** state the field rule in the candidate prompt and in the add-row plan
  example. Check each added or replaced plan's `draft_seed_path` before render
  and refuse with closed wording that names the validated plan id and the two
  allowed prefixes; name the plan on the `null` parse error too. Echo no model
  text.
- **Verification:** through the real materializer and the batch retry, each of
  `null`, `""`, `plan-seeds/…`, and `x` yields a correction naming the plan id
  and both prefixes; the second invoker prompt contains the rule; a
  `plan-seed-drafts/…` path and a `seeds/…` path stay accepted.
- **Approach:** direct — one prompt paragraph, one pre-render check, tests.
- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Priority:** blocks the next Integration proposal: the stored attempt-2 response
  carries four plans with a `null` seed path.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** roadmap process review, 2026-10-09; reproduced with a probe.

### Candidate retry corrections often name neither the row nor the id the model must change

- **Severity:** RISK
- **Files:** `plan_tool/roadmap_candidate.py:_gate_correction`,
  `_validate_relation_authority`, `_prepare_operations`,
  `_validate_operation_authority`, `_enum_value`;
  `plan_tool/roadmap_gates.py` (`check_component_coverage`,
  `check_entity_coverage`, and the `undefined-*` gates);
  `plan_tool/roadmap_candidate_run.py`.
- **Symptom:** the retry prompt is a fresh render plus one correction line; it
  does not contain the rejected reply. The correction is therefore all the model
  has, and these refusals leave it too little to locate the defect in the one
  retry the run allows:
  - `uncovered-entity` and `uncovered-component` print `(row identity
    unavailable)`; three uncovered entities give three identical lines, and
    `uncovered-component` is filed under `03-components.md` although the fix is
    a plan's `component_ids` in `04-roadmap.md`. The uncovered id is a defined,
    validated row id and is safe to echo.
  - The `undefined-*` kinds and `unresolved-constraint-anchor` /
    `unresolved-decision-anchor` omit the referenced id, so two bad references
    on one row print identically.
  - Citing a row that appears only in the capsule inventory is refused as
    `every affected predecessor relation endpoint requires full membership`,
    naming no owner, relation, or endpoint; the prompt says an inventory row
    does not authorize an edit but never says it cannot be cited.
  - Operation refusals (`cannot target one row twice`, `existing rows require
    exact full-content capsule membership`, `a plan addition requires its
    matching ordering entry`, `responses must cover all and only admitted
    reviewer items`) name no row or item.
  - `_enum_value` refusals (`candidate field type is not allowed` and the
    plan-disposition, decision-status, and constraint-disposition siblings)
    list no allowed values, and the prompt lists none.
  - `field-reference-target`, `constraint-on-not-load-bearing-attribute`,
    `shared-in-process-store`, `hosting-topology-coherence`, and
    `invalid-plan-id-slug` fall to the generic `repair this gate's named row`
    branch; every `unknown-*` kind prints `reference a defined, permitted
    roadmap row or value` without the vocabulary.
  - Authority and parse refusals return on the first defect, while gate
    corrections list every violation. A reply with one authority defect and
    several gate defects learns only the first, then spends its retry on it.
  - `_validate_relation_authority` iterates `added_rows` and `removed_rows`
    sets, so the defect reported first varies with `PYTHONHASHSEED` once
    refusals name a row.
  - A model-supplied `op` or `row_type` value is echoed unbounded into the
    correction; an empty `response`/`content` or `context_id` parses and is then
    refused as a bare `invalid-delta`.
  - The example entity in the add-row prompt has `fields: []`, which
    `check_entity_fields` refuses (`entity-without-fields`).
- **Evidence:** read from the code and confirmed with probes through the real
  materializer and gate functions, 2026-10-09; 20,000 random envelopes through
  the gates and 4,000 random batch deltas through the materializer raised
  nothing, so the gap is wording and ordering, not crashes. The Integration batch adds
  about four entities and rules, ten constraints, three stack rows, components,
  and four plans in one response, so several of these defects arrive together.
- **Fix:** carry validated ids through closed wording, as
  `_ordering_reference_condition` already does: put the uncovered or
  unresolved id in `referenced_id`, add a per-kind condition for each kind in
  the generic branch, append the closed enum values, and name the row or item in
  each operation refusal when `is_receipt_safe_id` accepts it (otherwise `(identity
  unavailable)`). Iterate in operation order, and collect all authority defects
  into one closed correction. Echo `op`/`row_type` only when it is a member of
  the closed alias set. Give the prompt's entity example one text field.
  This entry subsumes the "first of several defects" entry for the authority
  and gate layers; that entry keeps the parse layer.
- **Deliberately not:** adding the rejected reply to the retry prompt, widening
  the retry budget, or copying raw `Violation.message` text or row prose. The
  `test_gate_correction_excludes_free_form_row_identity_and_message` boundary
  stays.
- **Verification:** for each bullet above, one test through the materializer or
  batch retry that asserts the second invoker prompt names the id, plus the
  existing free-form-exclusion test unchanged; a hash-seed sweep asserts the
  same defect is reported first.
- **Approach:** direct, in batches by file (gates, authority, parse).
- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** roadmap process review, 2026-10-09.

### A new component that needs component-local storage has no legal candidate move

- **Severity:** RISK
- **Files:** `plan_tool/roadmap_candidate.py:_RELATIONLESS_ADD_ROW_TYPES`;
  `plan_tool/roadmap_gates.py:check_store_definitions`.
- **Symptom:** `check_store_definitions` requires every component to name a
  store, refuses a shared in-process store, and tells the model to "define a
  separate in-process store". `stores` is non-addable (parse refuses it as
  `stores cannot be added`), so a new component that needs component-local
  storage can cite only an existing durable store.
- **Evidence:** probe: a store add is refused at parse, and a shared in-process
  store is refused by the gate; the two corrections contradict each other.
- **Fix:** decided 2026-10-09 (owner-approved default): keep stores non-addable,
  and change the `shared-in-process-store` gate correction to say only an
  existing durable store can be cited. `ROADMAP_FORMAT.md` § "Candidate row
  anchors" already states the limit.
- **Approach:** decision, then direct.
- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** roadmap process review, 2026-10-09.

### A settled decision with no link to the feedback can be rewritten by any candidate operation

- **Severity:** BUG
- **Files:** `plan_tool/roadmap_candidate_context.py` (the `settled-decision`
  inclusion), `_full_member_authority` and `_validate_operation_authority` in
  `plan_tool/roadmap_candidate.py`.
- **Symptom:** every settled decision is a full capsule member with reason
  `settled-decision`, and full membership is enough authority to replace a row.
  A reviewer item about one entity can therefore change `chosen_option`, or set
  `status` from `settled` back to `pending`, on a settled decision anchored to
  an unrelated, unreached row. A removal is refused only by the incidence check.
  `BUG_BACKLOG` "An enrolled roadmap's candidate promotion never re-checks a
  settled decision" covers the missing promotion-time gate; neither entry names
  this authority path.
- **Evidence:** real materializer on batch and selector capsules with the
  predecessor's existing violations filtered out: replacing an unrelated settled
  decision and flipping it to `pending` both return `ACCEPTED`.
- **Fix:** give `settled-decision`-only members read-only authority, so editing
  one requires `feedback-closure` or `inventory-expansion`. Fix it with the
  promotion-time entry or state why the two stay apart.
- **Verification:** replacing or reverting a settled decision with no other
  inclusion reason is refused on both routes; a settled decision that
  feedback-closure reaches stays editable.
- **Approach:** direct.
- **Route:** direct · **Readiness:** ready · **Tier:** architect.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** roadmap process review, 2026-10-09; reproduced with a probe.

### Inherited decisions cannot anchor to stack rows, and decision-anchor resolution is defined three ways

- **Severity:** BUG
- **Files:** `plan_tool/roadmap_gates.py:check_inherited_decisions` (local set
  from `design_row_ids`) and `check_decision_records` (`_envelope_rows`,
  stripped anchor); `plan_tool/roadmap_candidate.py` (the untyped
  `DECISION_ANCHOR` fallback in `_validate_relation_authority`);
  `ROADMAP_FORMAT.md` (carried-decisions example, § "Ids, anchors, and
  feedback", decision-record gate table).
- **Symptom:**
  - A Roadmap-derived decision may anchor to a stack row; an inherited one
    cannot (`inherited-decision-nonlocal-anchor`), so a brief-carried settled
    stack decision never passes the stage gate. The format doc's own carried
    example anchors to `hosting-compute`, which the same doc says is not an
    anchor.
  - Candidate authority resolves a decision anchor against any row of any
    artifact (its comment says this "matches its real resolution semantics").
    The gate resolves against the owner artifact and its upstream artifacts,
    excluding hosting and store ids. A decision anchored to a component,
    constraint, or plan from a domain decision passes authority and fails the
    gate as `unresolved-decision-anchor`.
  - Only `check_decision_records` strips whitespace from an anchor; the
    extractor, candidate authority, the inherited check, and the view citation
    map use the raw string. A padded anchor passes the stage gate and is refused
    by candidate authority.
  - `ROADMAP_FORMAT.md` says anchors resolve to "a row in its own artifact, plus
    `01-domain.md`'s rows for a constraints decision"; the code and stage
    prompts resolve to the union of upstream artifacts.
- **Evidence:** probes through the gate functions and the real materializer,
  2026-10-09: derived `stack-platform` anchor `[]`, inherited `stack-platform`
  `inherited-decision-nonlocal-anchor`, domain decision anchored to
  `component-order` accepted by authority and refused by the gate.
- **Fix:** one rule, stated once in `ROADMAP_FORMAT.md`: the union of upstream
  artifacts plus the artifact under check, including stack rows, excluding
  hosting and store ids, compared after the same whitespace handling everywhere
  (or padded anchors rejected at parse). Make `check_inherited_decisions` and
  candidate authority use it; change the carried-decisions example's anchor to a
  disposition or stack id.
- **Verification:** an inherited decision anchored to a stack row passes; a
  hosting anchor is refused with the same kind on both decision forms; a
  candidate decision anchored to a wrong-stage row is refused at authority with
  closed wording naming the owner and anchor.
- **Approach:** direct after the rule is written down.
- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** roadmap process review, 2026-10-09.

### A plan that other plans depend on cannot be removed or restructured by a candidate

- **Severity:** RISK
- **Files:** `plan_tool/roadmap_candidate.py:_validate_operation_authority`,
  `_prepare_operations`; `plan_tool/prompts/roadmap-candidate-delta.md`
  (ordering paragraph).
- **Symptom:** a `replace-row` carries no `ordering`, and removing then
  re-adding the same row is refused as targeting one row twice. Removing
  `plan-order` while `plan-b` depends on it is refused (`removing a row must
  remove every incident declared relation`); replacing `plan-b` cannot drop its
  `depends_on`. A batch therefore cannot merge or split plans, or make an
  existing plan depend on a newly added one, short of removing every dependent
  plan as well.
- **Evidence:** probes through the real materializer, 2026-10-09. The prompt
  says an ordering change is allowed "only as an inseparable consequence of
  adding or removing the relevant typed row", so the limit is partly
  deliberate; no test or document states the consequence.
- **Fix:** decide whether a `plans` `replace-row` may carry an `ordering`
  under the same relation authority as other relation edits. If not, document
  the limit in `ROADMAP_FORMAT.md` and have the removal refusal name the
  dependents.
- **Approach:** decision, then direct.
- **Route:** direct · **Readiness:** decision-needed · **Tier:** architect.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** roadmap process review, 2026-10-09.

### Roadmap docs and prompts disagree with the gates, and stored-batch replay skips relation authority

- **Severity:** MINOR
- **Files:** `ROADMAP_FORMAT.md` (§ constraints schema, § "Ids, anchors, and
  feedback", gate table), `plan_tool/prompts/roadmap-constraints.md`,
  `plan_tool/roadmap_view.py` (citation-map docstring),
  `plan_tool/roadmap_candidate_run.py:_require_reproducible_batch_operations`,
  `_DELTA_ROW_TYPES`.
- **Symptom:**
  - Hosting, store, and stack ids are documented and prompted as "not feedback
    targets", but the embedded stage-feedback route targets them on purpose
    (`_feedback_target_rows`, pinned by
    `test_hosting_ids_stay_out_of_local_design_resolution_but_are_feedback_targets`).
    Only the ledger route excludes them. The docs describe one route as the
    only one.
  - `ROADMAP_FORMAT.md` describes constraint `anchor_ids` as "Ids in
    `01-domain.md`"; the gate, the endpoint table, and the gate table accept
    entity, business rule, and workflow ids only.
  - The citation-map docstring says "exactly eleven" fields and omits
    `ComponentRow.store_ids`; the table maps twelve.
  - Stored batch replay re-runs preparation, authority, application, and
    assembly but not `_validate_relation_authority`, so the anchor and endpoint
    rules apply only at first materialization. Promotion re-runs the gates, not
    authority. A tampered local store whose operations and bytes agree would
    replay clean.
  - `ConstraintRow.attribute` references a disposition by name and is not
    extracted as a relation. It is safe today because an attribute change is
    classified structural and `check_attribute_totality` checks the value.
  - `_DELTA_ROW_TYPES` copies `_ROW_TYPE_BY_CLASS_NAME` with no test tying the
    two together.
- **Fix:** document the two feedback routes and correct the constraints prompt
  sentence; name the three anchor row types; correct the docstring; call
  `_validate_relation_authority` with the stored capsule in replay; add one test
  asserting the two row-type tables are equal.
- **Approach:** direct, docs first.
- **Route:** direct · **Readiness:** ready · **Tier:** beginner.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** roadmap process review, 2026-10-09.

### A stored batch candidate capsule is accepted when its payload's embedded ceiling disagrees with its recorded ceiling

- **Severity:** MINOR
- **Files:** `plan_tool/roadmap_candidate_context.py:_capsule_is_intact` and the
  batch branch of `plan_tool/roadmap_candidate_run.py:_capsule_and_receipt_are_exact`,
  with a test beside `tests/test_roadmap_candidate_context.py`'s supported-ceiling tests.
- **Symptom:** a stored selector capsule is protected because it is re-rendered
  and compared; a stored batch capsule is never re-rendered, so validation checks
  only that `capsule.ceiling_bytes` is a supported value, that
  `receipt.ceiling_bytes` equals it, and that the digests match. It does not check
  that the payload's own embedded `"ceiling_bytes"` equals the recorded value, nor
  that `len(payload)` is within it. A hand-edited or migrated record whose
  capsule says 64 KiB over a 300 KB payload, or whose payload says 384 KiB while
  the capsule says 192 KiB, validates. It needs write access to stored evidence
  and the digests are unsigned, so this is a consistency gap, not an external
  attack. It predates the 2026-10-09 ceiling change, which adds a third allowed
  value and so makes an accidental mismatch easier.
- **Fix:** in `_capsule_is_intact`, also require `receipt.payload_bytes <=
  capsule.ceiling_bytes` and the payload's embedded `ceiling_bytes` to equal
  `capsule.ceiling_bytes`; pin both with a batch test.
- **Deliberately not:** re-rendering stored batch capsules (the route is built
  not to recompute them).
- **Approach:** direct, low priority.
- **Route:** direct · **Readiness:** ready · **Tier:** experienced.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** 2026-10-09, `/code-review high` pass 1 on `fix/roadmap-context-ceiling`
  (`handoffs/2026-10-09-roadmap-context-ceiling-code-review.md`, finding 4).

### `--apply` links promoted seed copies into `plan-seeds/` before it records `published`

- **Severity:** RISK
- **Files:** `plan_tool/roadmap.py` (`apply_roadmap_seeds` →
  `_register_roadmap_seed_promotions`).
- **Symptom:** not reproduced. `--apply` links the copies into `plan-seeds/`,
  then records `published: true`. A failure between the two leaves a file the
  tool wrote, carrying its state marker, while the state says unpublished.
  Refresh and accept leave it untouched (the recorded flag is the only
  publication proof), and `--apply` refuses it as a collision, so the operator
  deletes it by hand.
- **Fix:** decide first: accept the in-file state marker as proof of
  authorship (it names the roadmap and plan id; no parser for it exists
  today), or record `published` before linking and clear it when linking
  fails.
- **Deliberately not:** restoring "an existing destination counts as
  published" for refresh or accept, which overwrote hand-written files
  (fixed in PR #80).
- **Route:** direct · **Readiness:** decision-needed (marker-as-proof or
  record-first) · **Tier:** experienced.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** `/code-review high` of PR #80, 2026-10-10.

### `--accept-seed` clears an `invalidated` seed's invalidation when the draft was hand-edited

- **Severity:** RISK
- **Files:** `plan_tool/roadmap.py` (`_accept_roadmap_seed` writes
  `"status": "current"`), `plan_tool/roadmap_seed_manifest.py`
  (`classify_draft_seeds` checks the digest before the status).
- **Symptom:** after a feedback revision marks a seed `invalidated`, a hand
  edit of its draft classifies `digest-mismatched`, not `stale`, so accept's
  guard passes and the entry is rewritten `current`. `create --from-existing`
  then stops asking for stale-use confirmation although the roadmap changed
  after the draft was generated. The unedited invalidated draft is refused
  (pinned by `test_accept_refuses_each_non_digest_mismatched_classification`).
  Not reproduced.
- **Fix:** decide first whether a hand edit made after invalidation counts as
  the operator's re-review (then say so in the accept output), or accept
  preserves `invalidated` / refuses until a refresh. The registration path
  `_register_roadmap_seed_promotions` keeps the prior status.
- **Route:** direct · **Readiness:** decision-needed · **Tier:** experienced.
- **Arc assignment:** `backlog-arc-roadmap`.
- **Origin:** `/code-review high` of `fix/accept-seed-write-order`, 2026-10-10.
