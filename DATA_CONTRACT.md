# Application Data Contract — persisted / serialized schemas

> **Source of truth:** this doc is reference reading for humans and coding agents —
> the tool does **not** load it at runtime. The enforced registry lives in
> `plan_tool/data_contract.py`; runtime behavior still lives in
> `plan_tool/review_persistence.py:save_review`,
> `plan_tool/review_persistence.py:load_review`,
> `plan_tool/telemetry.py:record_decision`,
> `plan_tool/telemetry.py:read_decisions`, and
> `plan_tool/locator.py:load_manifest_plan_paths`. If this doc and the code
> disagree, **the code wins — fix the doc.** A drift guard
> (`tests/test_data_contract.py`) fails when a registered persisted shape,
> sidecar key, durable config key, schema constant, or authored-artifact
> format-version constant drifts from this doc.

**Scope.** This documents the layer plan-tool *persists and reads back at runtime*
— review/report sidecars, their recommendations and walk annotations, the
fingerprints, and the plan manifest — plus the authored-artifact
format-version constants and their evolution policy below. It does **not**
re-document the *authored-artifact* content schemas — `PLAN_FORMAT.md`,
`DETAIL_FORMAT.md`, and `JIRA_FORMAT.md` retain ownership of field and section
shape — nor internal in-memory types with no persistence.

## Version-evolution policy

A new durable schema, identity, or protocol version carries a transition for
projects that already hold the previous version. Before the new writer becomes
the default, the owning plan and format reference define one of these paths:

- compatible reading followed by a safe rewrite;
- a bounded, recoverable migration with explicit eligibility and rollback or
  repair behavior; or
- a user-approved retirement after every known consumer and live record has
  migrated or been deliberately archived.

The chosen path states the observable legacy reader/CLI result and has fixtures
for both successful transition and unsupported or unsafe legacy data. Readers
fail closed; they never guess a version, silently bless current state, or turn
an unsupported record into a newer one. Issuing a newer version alone is not an
upgrade path. A retirement that makes old records unreadable is valid only when
the project-level migration/archival decision and that fail-closed outcome are
explicit. Roadmap evidence version 1 meets that condition through the dated,
approved roster and zero-blocker record in
[`docs/history/roadmap-evidence-v1-retirement.md`](docs/history/roadmap-evidence-v1-retirement.md);
its reader boundary rejects version-1 evidence rather than inferring an
upgrade.

## Authored-artifact format versions

A plan file and a run-grade detail file each declare their format version
in-band, and each reader refuses an unsupported declared version rather than
guessing or silently accepting it. The registry entries below
(`plan_tool/data_contract.py:artifact_format_version_contracts`) name only the
version constant, its supported-versions companion, and this policy — they
carry no dataclass fields or JSON keys, and never describe either artifact's
actual content shape. `PLAN_FORMAT.md` and `DETAIL_FORMAT.md` remain the
schema references for that shape.

### Plan format version (`plan_tool/schema.py`)

- **Constants:** `PLAN_FORMAT_VERSION` (currently **`1`**) and
  `SUPPORTED_PLAN_FORMAT_VERSIONS`.
- **Carrier:** the top-level frontmatter key `format_version`; a missing key
  resolves to legacy version 1. See `PLAN_FORMAT.md` for its placement in the
  frontmatter shape.
- **Break rule:** any new frontmatter key is a break, even an optional one —
  `Plan` and `Step` both declare `extra="forbid"`, so a writer must bump
  `PLAN_FORMAT_VERSION` before it ever emits such a key, except for the named
  version-1 step alias exception below.
- **Version-1 step alias exception:** owner-confirmed 2026-10-22 (#517),
  `steps[].description` is preferred output while legacy `steps[].title`
  remains accepted. Both plan serializers emit `description` on ordinary
  rewrites, retaining format version 1 without an explicit upgrade. Existing
  plans remain readable and writable. Older installations that do not recognize
  step `description` reject newly emitted keys through strict validation,
  even with declared version 1; accepting version 1 does not guarantee support
  for this spelling. This exception permits no arbitrary unknown fields or
  unrelated schema changes. [PLAN_FORMAT.md](PLAN_FORMAT.md#field-semantics)
  owns the alias and dual-key input rules.
- **Writer eligibility:** `write_plan`/`render_plan_text` stamp the current
  declaration only when the plan's effective version is already current, and
  refuse to serialize an effective-older plan — including a raw absent
  legacy plan, once a later version ships — until its explicit raw upgrade
  runs. At version 1 that upgrader exists only as a library entry point
  exercised by its coverage tests, since version 1 refuses no previously
  supported live representation.
- **Support window:** a reader accepts the current version and
  current-minus-one; absent counts as legacy version 1 for a live plan.
- **Retirement:** a version retires only by a dated, user-approved record,
  once every remaining live absent-or-older plan has an explicit upgrade or
  archival path, before version N+2 ships.
- **First-refusal obligation:** the first release that makes a previously
  supported live on-disk plan reach a reader or writer refusal ships an
  operator-invocable upgrade route for the plan class, and a shared
  compatibility preflight before every affected mutating command's first
  state change, in that same release. The step alias exception preserves this
  release's support for existing plans; older installations rejecting new output
  do not constitute this release refusing an existing plan.
- **Upgrade obligation:** `plan_tool.parser.upgrade_plan_frontmatter_to_current`
  takes a raw frontmatter mapping — not a parsed `Plan`, whose
  `format_version` field already defaults to current — and returns one
  declaring the current version. Every raw state (absent, plus each version
  in `SUPPORTED_PLAN_FORMAT_VERSIONS`) has a declared path to current,
  enforced by a coverage test in `tests/test_parser.py`: adding a version to
  the supported set with no matching branch fails that test. Reading never
  upgrades — the path is reached only by explicit invocation. At version 1
  the entry point is a library API only; the first release that makes a
  previously supported live plan reach a reader or writer refusal ships an
  operator-invocable route for the plan class in that same change. Retiring a
  version removes it from the supported set, and from this obligation, with
  it.

### Detail format version (`plan_tool/detail_artifacts.py`)

- **Constants:** `DETAIL_FORMAT_VERSION` (currently **`1`**) and
  `SUPPORTED_DETAIL_FORMAT_VERSIONS`.
- **Carrier:** the fixed post-H1 body marker
  `<!-- plan-tool:detail-format-version: N -->`, the first non-blank line
  after the document's first non-blank line (which must be an H1). A detail
  file has no YAML frontmatter, so this marker is the carrier rather than a
  schema field; see `DETAIL_FORMAT.md` for the surrounding body shape.
- **Break rule:** an optional section the established run-grade body readers
  already ignore is additive and does not bump `DETAIL_FORMAT_VERSION`; a
  carrier move or any other reader-visible structural change does.
- **Writer eligibility:** the detail writer carries no comparable refusal —
  `plan_tool/detail.py` always authors a fresh current-format body rather
  than rewriting an existing older one in place.
- **Support window:** a reader accepts the current version and
  current-minus-one. Absent counts as legacy version 1 for a live run-grade
  detail. A body with a valid carrier H1 but no marker is raw-upgradable to
  current. A carrier-less body (no valid carrier H1) remains readable only
  while legacy version 1 stays supported, and its declared path to current is
  forced re-authoring — the raw upgrader cannot invent a missing H1. An
  archived detail bundle is a historical snapshot outside this window: its
  archive breadcrumb intentionally precedes the H1, so it carries no live
  carrier, no live reader obligation, and no upgrade obligation.
- **Retirement:** a version retires only by a dated, user-approved record,
  once every remaining live absent-or-older detail has an explicit upgrade or
  forced-re-authoring path, before version N+2 ships.
- **First-refusal obligation:** the first release that makes a previously
  supported live on-disk detail reach a reader or writer refusal ships an
  operator-invocable upgrade route for the detail class, and a shared
  compatibility preflight before every affected mutating command's first
  state change, in that same release.
- **Upgrade obligation:** `plan_tool.detail_artifacts.upgrade_detail_body_to_current`
  takes a raw body — not a value already resolved by
  `require_supported_detail_format_version` — and returns one whose fixed
  post-H1 slot declares the current version. Every raw state with a valid
  carrier H1 (absent, plus each version in `SUPPORTED_DETAIL_FORMAT_VERSIONS`)
  has a declared path to current, enforced by a coverage test in
  `tests/test_detail_artifacts.py`: adding a version to the supported set
  with no matching branch fails that test. A carrier-less body (no valid
  carrier H1) has no raw path — the upgrader refuses rather than inventing
  one — and its declared path to current is forced re-authoring instead.
  Reading never upgrades — the path is reached only by explicit invocation.
  At version 1 the entry point is a library API only; the first release that
  makes a previously supported live detail reach a reader or writer refusal
  ships an operator-invocable route for the detail class in that same
  change. Retiring a version removes it from the supported set, and from
  this obligation, with it.

## Authored plan concept ownership (`steps[].concept_ids`)

`steps[].concept_ids` is persisted ownership metadata in a plan's YAML
frontmatter. It is an ordered list of stable, lowercase 64-character SHA-256
concept IDs from the signed-off concept record. The field defaults to `[]`; the
empty default is omitted when frontmatter is rewritten, while non-empty lists
round-trip in authored order.

Each entry must be a non-empty string in the stable concept-ID format, and an ID
may not be repeated within one step. Different steps may own the same concept.
Plan parsing validates only this local shape and uniqueness: the field does not
by itself prove that a referenced concept record or concept exists. Membership
checks belong to workflows that have the signed-off concept record available.

## Saved review sidecar (`<ts>[-<kind>].json`)

Every review/audit/reconcile run persists one JSON sidecar under the plan's
reports directory — `<plan-dir>/plan-details/<slug>/reports/` (see
`plan_reports_dir`). Written by `save_review`, read by `load_review`.

- **Filename:** `YYYYMMDD-HHMMSS[-<kind>].json` — UTC second-precision, lexically
  sortable (newest-last). The `kind` suffix is omitted for the default
  `"review"`; non-default kinds embed verbatim, e.g. `<ts>-completeness.json`,
  `<ts>-detail-reconcile.json`, `<ts>-run-reconcile.json`.
- **`version`** — schema version integer. Ordinary reviews use **`1`**;
  completeness sidecars with an `audit_shape_advisory` use **`2`**; the
  role-aware format carrying `is_pre_apply_checkpoint` uses **`3`**; and a
  completeness sidecar carrying `qualified_result` uses **`4`**.
  `load_review` requires an exact supported version and treats a malformed
  optional advisory as unavailable without rejecting otherwise valid saved
  findings. Versions `1` and `2` are the legacy final-report formats and stay
  readable; a reader that predates a version rejects it rather than reading a
  payload whose keys it cannot interpret, which is what stops an older reader
  from taking a version-4 checkpoint or result-bearing audit for a final
  report it cannot interpret. Versions `1`–`3` remain readable legacy
  evidence but do not qualify a current completeness replay.

`load_review` rejects a sidecar whose required persisted field has the wrong
type or whose severity is outside the `Recommendation` values below. Producer
`source` names remain open string identifiers; absent or malformed optional
audit metadata instead projects as unknown.

Completeness audits can also persist data-contract documentation drift findings
as ordinary `Recommendation` records with `source="data-contract"`. Applyable
`DATA_CONTRACT.md` drift findings additionally have a sibling
`<ts>-completeness-data-contract.json` payload artifact containing the
structured candidate edit and registry/doc fingerprints captured by the audit.
`plan-tool data-contract-apply <name>` walks those saved findings
interactively, replays only fresh structured contract-document payloads, and
annotates the audit through the same saved-review workflow used by other walks.
It does not re-run drift detection or infer edits from prose findings. Stale
fingerprints require a new `plan-tool completeness-audit <name>` before apply;
data-contract findings about stale plan/detail `## Input` references are normal
repair findings and are not `DATA_CONTRACT.md` payload edits. This does not add
fields to the saved-review schema; the code-owned registry remains
authoritative.

Both `review.py:check_plan_input_contract_references` and
`review.py:check_step_input_contract_references` use
`review.py:_eligible_planned_paths` to select creation promises. The selector
preserves the audited plan's own step `creates` and adds explicitly declared
creates from usable sibling plans registered in the same repository. For a
roadmap-derived plan, siblings must resolve to the same accepted roadmap
identity. Missing, unreadable, malformed, outside-repository, or ineligible
sibling records contribute nothing; unavailable or uncertain audited-plan
identity or registration leaves only its own creates. Selection belongs to
`_eligible_planned_paths`, not to separate rules in the two consumers.

These promises excuse an absent path only: undeclared and edit-only missing
paths still produce findings. `data_contract.py:check_input_contract_references`
and `data_contract.py:_code_anchor_resolves` continue ordinary symbol validation
for existing files, even when an eligible plan declares the file for creation.
Accepting an absent path establishes neither delivery nor future symbol
existence nor agreement between sibling contracts. Stale Input references
remain ordinary repair findings, without structured documentation payloads or
new persisted fields.

Completeness audits also persist the `medium` mixed-refactor-plus-feature
(MIXED-STEP) `granularity-split` finding (`source="granularity-split"`, with
`step_id` set to the mixed step) into `recommendations`, alongside the
correctness/completeness/data-contract findings. This is the one advisory smell
that reaches the sidecar: `completeness-apply` replays it through the
`escalate_to_split` bridge (the split bridge). The `info` deterministic split recs, the
`granularity-merge` recs, and the repo-structural smells stay advisory-only
(report render, not persisted), and this finding never flips the exit code.

### `SavedReview` (`review_persistence.py`)

The in-memory record; its JSON payload is the persisted contract. JSON key
`version` maps to the field `schema_version`; the value is checked against the
supported set — `SCHEMA_VERSION` plus the additive variants listed above.

| Field | Persisted | Meaning |
|---|---|---|
| `plan_slug` | yes | plan slug the review belongs to |
| `plan_path` | yes | repo-relative posix path to the plan (absolute if outside the repo) |
| `created_at` | yes | ISO-8601 UTC, e.g. `2026-06-21T13:30:51Z` |
| `report_md` | yes | the human-readable report markdown (frozen) |
| `recommendations` | yes | list of `Recommendation` (see below) |
| `annotations` | yes | map of `rec_id` → `Annotation` (the walk's per-finding decisions) |
| `schema_version` | yes (as JSON `version`) | schema version int |
| `kind` | yes | `"review"` \| `"detail-reconcile"` \| `"run-reconcile"` \| `"completeness"` — the producer |
| `step_id` | yes | step id for the reconcile kinds; `None` for completeness/review |
| `plan_fingerprint` | yes | plan+detail-bundle digest (see Fingerprints); `""` = unset/legacy |
| `code_fingerprint` | yes | opaque path→hash map of watched code |
| `code_fingerprint_present` | yes | `True` iff `code_fingerprint` was computed (distinguishes computed-empty from never-computed) |
| `detail_bundle_fingerprint` | yes | per-step detail-file path→hash snapshot at audit time |
| `detail_bundle_fingerprint_present` | yes | `True` iff `detail_bundle_fingerprint` was computed |
| `step_ids` | yes | sorted ids of every step (parked included) parsed from the plan at save time (BACKLOG #166); self-computed by `save_review` from `plan_path`, not caller-supplied like the fingerprints above, so every `kind` carries it |
| `step_ids_present` | yes | `True` iff `step_ids` was computed (a plan-parse failure at save time records `False`, never breaking the save) |
| `outcome_evidence_valid` | yes | `True` only for a parser-valid `run-reconcile` findings result (severity-labelled findings or explicit `_(none)_`); `False` is invalid output and `None` is legacy/unknown, neither of which may clear calibration evidence |
| `audit_shape_advisory` | yes, optional (versions 2 and 3) | immutable non-routing `AuditShapeAdvisory` saved only by run-grade completeness audits; absent from version-1 sidecars and displayed only when its dedicated exact audit-input fingerprint still matches the plan and resolved detail inputs |
| `audit_coverage` | yes, optional (completeness sidecars only) | canonical conceptual-audit coverage provenance; valid values follow the public `coverage` contract below without `evidence_status`; a terminal plan quota stop remains unconfirmed recovery evidence and never writes an ordinary final findings sidecar, so it is not reusable; absent or malformed legacy values are unknown, never a clean verdict |
| `is_pre_apply_checkpoint` | yes, optional (producer output: version-4 completeness sidecars only; annotation rewrites can preserve an unknown marker on another kind or version) | the saved-review role: `True` = a confirmed pre-apply audit checkpoint (crash-recovery evidence, not a converged result), `False` = an ordinary final artifact, `None` = unknown metadata no reader may trust as final |
| `sampler_state` | yes, optional (stable sampler checkpoint only) | sampler recovery mapping, separate from audit evidence; its `lifecycle` is `"in-progress"` for a resumable boundary or `"terminal-residue"` for non-resumable diagnostic residue |
| `plan_mass` | yes, optional | #238 plan-mass snapshot (see below); `None` for a sidecar saved before this field existed, a jira-grade audit, or a pre-apply checkpoint (`completeness_phases.py` computes it only for the final-report path) |
| `audit_stage` | yes, optional (completeness sidecars only) | the bare/detail bar under which the completeness audit ran (`"bare"` or `"detail"`); absent or malformed legacy values load as `None` and are excluded from compatible-pass windows |
| qualified audit result | yes (version-4 completeness sidecars, as JSON `qualified_result`) | immutable final audit decision object with `headline`, `stage`, `coverage`, `revision_status`, and nullable nested `audit_revision`; final sidecars require the object and recovery checkpoints store JSON `null` |
| `checkpoint_audit_revision` | yes, optional (version-4 confirmed completeness checkpoints only) | immutable captured plan/detail revision for recovery evidence; separate from the nested final-result revision because a checkpoint has `qualified_result: null` and is never reusable or applicable |
| `path` | **no** (in-memory) | populated by `load_review` with the file path; `None` right after save |

**Checkpoint-role policy.** The three role states above are normalized on load;
a bad marker never raises, so the sidecar stays inspectable.

- **Confirmed checkpoint** (`True`) — `version` is `4`, `kind` is
  `"completeness"`, `is_pre_apply_checkpoint` is the JSON literal `true`, and
  `qualified_result` is JSON `null`. Its optional
  `checkpoint_audit_revision` retains the audited plan/detail provenance but
  cannot make the checkpoint reusable or applicable. This is the only
  checkpoint-producer output.
- **Ordinary final** (`False`) — an unmarked version-1/2 sidecar (the legacy
  absence, preserved in place with no migration or bulk rewrite), or a raw
  version-3 completeness sidecar carrying literal `false`, or a version-4
  completeness sidecar carrying literal `false` and a valid
  `qualified_result`. The raw version-3 form remains readable compatibility
  evidence; final result writers emit version 4.
- **Unknown** (`None`) — a non-boolean marker (string, number, `null`,
  collection — values are never coerced), a marker on a non-completeness
  sidecar, a marker in a version-1/2 sidecar (a role/version mismatch), or a
  version-3/4 sidecar with no marker. Readers fail closed on this state rather
  than treating it as final.

**Sampler checkpoints.** `sampler_checkpoint_path()` stores the one stable
`in-progress-sampler-checkpoint.json` artifact beneath the plan's reports
directory, outside the timestamped `-completeness` report and sidecar stems.
Each write replaces that path atomically and durably. A sampler checkpoint is
version `4`, kind `"completeness"`, has `is_pre_apply_checkpoint: true`, a
JSON `null` `qualified_result`, and a valid `sampler_state` mapping. Its
`"in-progress"` lifecycle is resumable; its `"terminal-residue"` lifecycle is
non-resumable diagnostic evidence. A missing, malformed, or role-contradictory
sampler state normalizes to the unknown non-final role and cannot become final
evidence. A pre-apply checkpoint has no `sampler_state`.

A checkpoint's `low_impact_demotion_classes` (the calibration cohort used to
demote low-impact medium findings) is carried through resume, not gated on:
it stays frozen at its pre-crash build rather than being rebuilt from live
calibration history, so a resumed run reproduces the result an uninterrupted
run would have produced. It is therefore excluded from the identity fields a
resume must match (`plan_tool.review._SAMPLER_IDENTITY_FIELDS`).

Its fixed, non-timestamped filename sorts lexically ahead of every dated
saved review, so `resolve_saved_review`'s id-less "newest saved review"
resolution excludes it explicitly — it is transient recovery state, not a
saved review. It remains reachable by its explicit id for a recovery reader
that asks for it.

`update_annotation` preserves the role and its version: a confirmed checkpoint
is rewritten as a version-4 `true` with its null result, and an unknown role is rewritten as the
non-boolean `"unknown"` marker — a durable unknown representation, since any
non-boolean value re-reads as unknown in every version — so an annotation walk
can never turn an untrusted sidecar into an ordinary final one.

### Qualified audit result (`qualified_result`)

The object records what the audit concluded at audit time. It is immutable
evidence: later readers calculate `view_revision_status` separately and never
rewrite the stored result. `headline` is exactly
`no-qualified-current-evidence`, `awaiting-human-action`, `advisory-only`, or
`clean`. `stage` is `bare`, `detail`, or `not-sampled`; `coverage` is
`confirmed`, `unconfirmed`, `unknown-legacy`, or `not-sampled`; and
`revision_status` is `current`, `stale`, `unknown-legacy`, or `not-sampled`.

`audit_revision` is `null` exactly when all three qualifiers are
`not-sampled`; otherwise it records the grade-selected audited plan digest,
detail-bundle digest, detail list, and `detail_grade`. A later plan/detail
mismatch projects `view_revision_status: "stale"`; a capture failure projects
`"unknown"`; a result without an audit revision projects `"not-sampled"`.
Project code, prompts, lessons, configuration, and audit history remain live
explanation context and are not revision-freshness inputs. Missing or malformed
result data stays inspectable but is unavailable for a completeness walk.

### Saved gate verdict (`gate-status`, version 1)

`plan-tool gate-status <name> --json [--grade run|jira]` reads saved final
completeness results without running an audit, calling a backend, or writing
state. It emits JSON with or without `--json`; `--grade` defaults to `run`.
A completed read exits 0 regardless of its verdict. Resolution failures remain
command errors.

| Top-level field | Value |
| --- | --- |
| `version` | integer `1` |
| `plan`, `plan_path` | plan slug and repository-relative POSIX path (absolute for an external plan) |
| `detail_grade` | selected `run` or `jira` grade |
| `current_stage` | current grade-selected `bare` or `detail` stage; `null` when derivation fails |
| `stages` | object with exactly `bare` and `detail` keys |

Each stage is `null` when no eligible result exists. Selection uses the existing
newest-first sidecar listing and final-role eligibility predicate. It skips
unloadable sidecars, checkpoints, unknown roles, missing qualified results,
`not-sampled` results, and results from another grade. The newest eligible
result per stage wins even when stale; readers never fall back to an older
current result to obtain convergence.

This is a view of saved final evidence, not of the latest invocation. Jira-grade
audits deliberately write no final findings sidecar; ordinary Jira audit history
therefore leaves both stage values `null` under `--grade jira`. Grade selection
still prevents any foreign-grade sidecar from substituting for the requested
grade. A terminal `plan-quota` stop also withholds its final sidecar. Neither a
markdown-only report nor a recovery checkpoint replaces an older eligible final
result: the command returns that older evidence, or `null` if none exists. It
cannot distinguish “never audited” from “audited without a final sidecar”.

| Stage field | Value |
| --- | --- |
| `report`, `created_at` | sidecar filename stem and saved ISO-8601 UTC timestamp |
| `headline`, `coverage`, `revision_status` | unchanged fields from `qualified_result` |
| `view_revision_status` | existing read-time projection: `current`, `stale`, or `unknown` |
| `confirmation_kind` | saved audit-coverage confirmation kind, or `null` when unavailable |
| `plan_digest`, `detail_bundle_digest` | digests from the result's immutable `audit_revision` |
| `converged` | boolean: `SavedCompletenessResultView.is_current_final_qualified` and headline `clean` or `advisory-only` |

`awaiting-human-action` never means converged. Confirmation kind alone does not
determine convergence. To read the current gate, select `stages[current_stage]`
and read its `converged` field; a null stage or result means no verdict is
available. Plan or grade-selected detail edits invalidate freshness without
changing saved evidence. This document restates the existing qualified
result policy; it introduces no audit, continuation, or exit-code gate.

### `AuditShapeAdvisory` (`audit_shapes.py`)

An additive, optional saved completeness-audit payload. It never enters the
`Recommendation` list, source filters, annotations, or apply dispatcher.
`shape_id` is currently `"arm-clustering"`; the payload stores its
`source_plan_fingerprint`, ordered `arm_step_ids`, material/arm finding counts,
and minimal ordered evidence (`anchor` and audit `source`, not finding prose).
Presentation recomputes the dedicated exact audit-input fingerprint through
`AuditInputSnapshot`, not `compute_plan_fingerprint()`. Missing, malformed, or
mismatched payloads are simply unavailable for presentation while the saved
review remains usable.

| Field | Meaning |
|---|---|
| `shape_id` | registry-owned advisory emitter ID |
| `source_plan_fingerprint` | exact captured plan, resolved run-grade detail-input, and (when set) `Plan.source_seed` bytes digest |
| `arm_step_ids` | ordered committed step IDs forming the qualifying arm |
| `material_finding_ids` | stable IDs for every material audit finding in the final union |
| `arm_finding_ids` | stable IDs for material findings attributed to the arm |
| `material_finding_evidence` | ordered minimal `{finding_id, anchor, source}` records; no finding prose or execution target |
| `material_finding_count` | count matching `material_finding_ids` |
| `arm_finding_count` | count matching `arm_finding_ids` |
| `committed_step_count` | committed-step denominator captured for the arm decision |

### `PlanMass` (`completeness_report.py`, BACKLOG #238)

Opaque JSON dict stored under `SavedReview.plan_mass` (`plan_mass_to_json`),
read back by `first_saved_plan_mass` to compute the report's step-count /
detail-bundle-byte deltas against a plan's first audit. **Reporting only** —
no field here feeds a threshold, gate, warning, or exit code anywhere in the
tool (BACKLOG #238's scope fence). Every ratio is `None` (JSON `null`, never
`0`) when the plan has fewer than two committed steps.

This fence is why `convergence_diagnosis.py`'s BACKLOG #166 re-decomposition
advisory reads the top-level `step_ids` field above instead of nesting a
second step-identity signal inside `plan_mass` — `plan_mass` may never feed a
warning, so a dedicated, unfenced field carries it.

| Field | Meaning |
|---|---|
| `step_count` | committed-step count |
| `detail_bundle_bytes` | total UTF-8 byte size of every committed step's on-disk detail file (0 for a step with none) |
| `keystone_fan_out` | `max(\|depends_on\|) / (step_count - 1)` over code committed steps (`change_type` anything but `non-code` — `None`/unclassified counts as code); `null` if the plan has no code steps |
| `satellite_ratio` | share of committed steps whose only code (non-`non-code`) dependent is the keystone step; `null` under the same no-code-steps condition |
| `inert_step_ratio` | share of **code** committed steps whose detail body matches an "nothing user-visible changes"-style phrase (free-prose heuristic, tuned against a single session — expect false negatives); excludes `non-code` steps from both the numerator and the denominator, and deliberately excludes "changes no production code" from the phrase list — that is `detail.py`'s literal non-code-step boilerplate, not a padding signal; `null` if the plan has no code steps |
| `audit_induced_growth` | share of committed steps whose title was ever recorded as structural-split-created (see `DecisionEvent` kind `step-provenance` below); a step added by hand-editing the plan file is unobservable and never counted |
| `soft_edges` | list of `SoftEdge` (below) — declared `depends_on` edges whose detail prose marks them ordering-only/test-only (free-prose heuristic, same caveat) |

#### `SoftEdge` (`completeness_report.py`)

One flagged `depends_on` edge, nested inside `PlanMass.soft_edges`.

| Field | Meaning |
|---|---|
| `step_id` | the step declaring the edge |
| `depends_on_id` | the step it depends on |
| `note` | the matched detail-body sentence, verbatim |

### `Recommendation` (`review.py`)

One actionable finding. Round-trips through review sidecars and the purity
cache via `asdict` / normalized `recommendation_from_persisted_mapping`. `id` is
content-addressed (stable across re-runs of an *unchanged* finding).

| Field | Meaning |
|---|---|
| `id` | stable content-addressed identifier (also the `annotations` key) |
| `source` | open producer string (`plan-completeness`, `plan-correctness`, `file-check`, `heuristic`, `deps`, `claude`, `granularity-split`, …) |
| `severity` | `critical` \| `high` \| `medium` \| `low` (legacy) \| `nit` \| `info` |
| `step_id` | owning step id, or `None` (always `None` for `plan-completeness` / `plan-correctness`) |
| `title` | one-line title (clipped from the finding's first line) |
| `body` | full human-readable finding text |
| `suggested_action` | follow-up command/check, or `None` |
| `impact` | triage tag `low` \| `medium` \| `high`, or `None` |
| `complexity` | triage tag `low` \| `medium` \| `high`, or `None` |
| `redirect` | a `Redirect` (refuse-and-redirect signal), or `None`; persisted values must be `null` or an object with string `reason` and `suggested_next` fields |
| `purity_verdict_provenance` | `fresh` | `exact-cache` | `below-floor-reuse` for `granularity-split` purity verdicts, or `None`; legacy history is grouped as `unknown` by calibration |
| `file_path` | repo-relative path a deterministic apply can act on, or `None` |
| `anchor` | Claude-minted `[anchor-slug]` concept key, or `None` (encouraged stable across re-audits, not guaranteed) |
| `target_signature` | SHA-256 digest of the directive's target steps' `(id → title + change_type)` identity for the precise stale-directive guard, or `None` (unknown: legacy/non-directive/never-stamped) |
| `confidence` | `supported` for a directly verified predicate or `limited` for a fresh finding without that proof. An absent or `null` legacy persisted value loads as unknown (`None`) and an annotation rewrite writes JSON `null`; invalid sidecar values fail with `ReviewLoadError` before a reader consumes them. |
| `restated_property` | plan-altitude restatement of a bare-step Correctness finding raised under `plan-audit.md`'s "Property coverage versus delivery mechanisms" rule (the `### Restated` sub-block), or `None` for every other finding. `severity` is the auditor's one judgment, reasoned from this same restated framing (not a later revision); this field itself never changes axis or disposition. **The axis half is code-enforced** — `_parse_plan_audit_findings_with_evidence` nulls it inline for any non-`plan-correctness` finding at parse time, and `normalize_restated_property_axis` re-enforces the same rule on every persisted load (a hand-edited or other-producer-authored sidecar isn't bound by the parser). **The bare-step half relies on prompt compliance only** — `_parse_plan_audit_findings_with_evidence` takes no per-step detail-bundle-status parameter, so nothing stops the model from emitting `### Restated` on a Correctness finding for a step that already has a detail file. |

#### `Redirect` (`review.py`, nested on `Recommendation.redirect`)

| Field | Meaning |
|---|---|
| `reason` | why the finding's root cause is redirected (e.g. code→plan) |
| `suggested_next` | the redirected next action |

### `Annotation` (`review_persistence.py`)

The walk's per-finding decision, keyed in `annotations` by `rec_id`. Only the
interactive walk populates these; a fresh `save_review` writes `{}`.

| Field | Meaning |
|---|---|
| `status` | `"applied"` \| `"skip"` \| `"failed"` \| `"open"` (legacy `"done"` is rewritten to `"applied"` on load). `"failed"` is **non-terminal** — the apply attempt errored out (no edit landed); the re-walk re-prompts it without `--rewalk` instead of treating it as resolved, and carry-forward reads it as open |
| `note` | free-text operator note |
| `halt_reason` | why a non-apply happened; `""` for a deliberate decline, `"drift"` for a pre-apply safety halt |

## Fingerprints

Reproducible content identities captured at save time so a later run can tell
whether the world drifted. Grounding, saved-review, and detail-bundle artifacts
retain `{repo-relative-posix-path: sha256-hex}` maps where per-path comparison is
required. Decision telemetry stores only the canonical code-state digest below.

- **`plan_fingerprint`** (`compute_plan_fingerprint`, `review_persistence.py`) —
  one SHA-256 over the plan file **plus its detail bundle** (combined). `""` is
  the unset/legacy sentinel.
- **`code_fingerprint`** (`compute_code_fingerprint`, `fingerprint.py`) — the
  plan's in-scope **code** surface (`step.files`/`creates` minus the plan + detail
  files). `code_fingerprint_present` is the computed/never-computed marker
  (freshness gates on the marker, never on dict-truthiness).
- **`detail_bundle_fingerprint`** (`compute_detail_bundle_fingerprint`,
  `fingerprint.py`) — each step's **on-disk detail file** hashed individually
  (bare steps contribute no key — absence is the bare-state signal). The granular
  per-step counterpart to the combined `plan_fingerprint`; lets an apply
  re-validate *which* detail file drifted since an audit (BACKLOG #61).
  `detail_bundle_fingerprint_present` is its computed/never marker.

## Plan manifest (`<repo-root>/.plan-tool/plans.json`)

Per-project plan registry (the package ships none). Shape:

```json
{ "plans": ["docs/implementation-plans/2-foo.md", "..."] }
```

A `plans` array of repo-relative path strings naming posix `.md` paths.
`locator.py` scopes resolution to the cwd's git tree (no cross-project
leakage); override with `--plans-dir` / `PLAN_TOOL_PLANS_DIR`.

## Concept sidecar (`<plan-dir>/plan-details/<slug>/concepts.json`)

`plan_tool/concept_tree.py` owns this tracked decision record. A missing file
means no concept tree exists. A present malformed file raises an invalid-record
failure; a valid record whose `plan_fingerprint` differs from the expected
current plan fingerprint raises a distinct stale-record failure. The stored
`plan_slug` must also match the slug implied by the sidecar path. Saves validate
the complete record and atomically replace one `concepts.json` file.

Two record kinds share this file, discriminated by `record_kind` (default
`full-tree`). The legacy `full-tree` record is a hierarchical cache of plan text
and is fingerprint-gated on load as above. The flat `decision-record` kind holds
operator/tool `defer`/`wont_do` decisions confirmed *after* further plan edits;
it carries `plan_fingerprint` for provenance only and is **not** fingerprint-
validated on load, so it never raises the stale-record failure. Each flat node
has no hierarchy (empty `parent_path`), a non-empty coarse `bucket` tag, and a
`decision` of `defer` or `wont_do`.

### `ConceptTree` (`concept_tree.py`)

Top-level record stored in `concepts.json`; its integrity version is
`CONCEPTS_SCHEMA_VERSION`.

| Field | Meaning |
|---|---|
| `plan_slug` | slug derived from the plan filename and sidecar location |
| `plan_fingerprint` | exact plan/detail-bundle fingerprint against which the concepts were derived; mismatch is rejected as stale |
| `concepts` | ordered list of nested `ConceptNode` records |
| `schema_version` | exact sidecar version integer (currently **`1` = `CONCEPTS_SCHEMA_VERSION`**); unsupported versions are invalid |
| `record_kind` | record shape discriminator, exactly `full-tree` (default; fingerprint-gated) or `decision-record` (flat, not fingerprint-validated on load); other values are invalid |

### `ConceptNode` (`concept_tree.py`)

| Field | Meaning |
|---|---|
| `id` | SHA-256 stable identifier derived only from the NFKC/whitespace-normalized `title` and ordered `parent_path` using an unambiguous NUL-delimited UTF-8 encoding |
| `title` | non-empty concept title |
| `parent_path` | ordered ancestor-title path; every declared ancestor must exist in the same tree |
| `order` | mutable non-negative display/source order |
| `source` | mutable source linkage string |
| `decision` | mutable decision content |
| `rationale` | mutable decision rationale |
| `review_state` | exactly `unreviewed`, `approved`, or `rejected` |
| `source_metadata` | mutable string-to-string source metadata |
| `bucket` | coarse section-level tag (default `""`); required non-empty on a `decision-record` node, left empty on legacy `full-tree` nodes |

Identity excludes `order`, `review_state`, `decision`, `rationale`, `source`,
and `source_metadata`. Loading recomputes every `id` and rejects tampering,
duplicates, invalid parent paths, unknown review states, wrong JSON types,
unknown or missing fields, duplicate JSON keys, and schema-version mismatch.

## Grounding sidecar (`<plan-dir>/plan-details/<slug>/grounding.json`)

Tracked freshness sidecar written by `plan_tool/grounding.py:write_grounding`
and read by `plan_tool/grounding.py:read_grounding`. It records the plan/code
state a plan was last reconciled against, so refresh and re-grounding checks can
detect code freshness drift without depending on saved review reports.

### `Grounding` (`grounding.py`)

| Field | Meaning |
|---|---|
| `plan_slug` | slug derived from the plan filename and sidecar location |
| `grounded_at` | ISO-8601 UTC timestamp for the grounding write |
| `plan_fingerprint` | combined plan/detail-bundle digest captured at grounding time |
| `code_fingerprint` | opaque repo-relative path→hash map of watched code |
| `step_authoring_fingerprints` | `{"<step id>": digest}` (BACKLOG #165). A digest of a step's `title`/`files`/`creates`/`change_type`/`depends_on` plus the plan's `## Out of scope`/`## Deferred` text, taken when that step's detail file was last written. A step that's never been detailed has no entry. Additive field, no `schema_version` bump — an old sidecar just reads back as `{}`, since this whole file is a disposable cache, not a durable record. |
| `schema_version` | sidecar version int (currently **`1` = `GROUNDING_SCHEMA_VERSION`**); mismatches read as ungrounded |

**Writing `step_authoring_fingerprints`:** `write_grounding` only touches this
map when a caller explicitly passes it; otherwise it reads whatever's already
on disk and keeps it as-is. `create`/`detail`'s stamp helper
(`cli/authoring.py:_stamp_grounding`) uses this to update only the steps it
just wrote, never the whole map — a blanket rewrite on every stamp would
quietly erase the very staleness a plan edit had introduced for an untouched
sibling step, since the "current" plan is all a rewrite would have to compare
against.

## Project profile (`.plan-tool/project.json`)

Tracked, project-owned metadata written once by `plan-tool init` and available
to the scope-bearing `create`, `detail`, and `completeness-audit` prompts. It
never inherits from user-level configuration. V1 does not infer, evaluate, or
mutate its content; it renders the confirmed values as scope context, not
repository evidence or a plan-necessity verdict. `init` publishes a synced
temporary file through an exclusive link, so a crash cannot leave a partial
final profile. An existing profile is revised by a deliberate file edit and
commit; `init` refuses to replace it. Readers treat any missing, malformed,
schema-mismatched, or extra-field V1 object as unset. That strict shape is a
fail-closed V1 contract: an additive field requires a schema-version change.

### `ProjectProfile` (`project_profile.py`)

| Field | Meaning |
|---|---|
| `schema_version` | profile format version int (currently **`1` = `PROJECT_PROFILE_SCHEMA_VERSION`**) |
| `intent` | one non-empty, operator-confirmed project-level guiding intent; whitespace collapses to one logical prompt line |
| `non_goals` | optional ordered list of non-empty, operator-confirmed exclusions; each value becomes one logical prompt line |
| `decisions` | optional ordered list of non-empty, operator-confirmed settled statements; each becomes one logical prompt line, and V1 assigns no category, identifier, plan key, or application mapping |

## Purity findings cache (`<repo-root>/.plan-tool/purity-cache/<slug>.json`)

Gitignored, best-effort per-plan cache of the MIXED-STEP purity verdict, keyed
by step id, read and written by `plan_tool/purity_cache.py`. The two purity call
sites consult it so an unchanged step skips the expensive Claude MIXED-STEP call.
The file is a single whole-file JSON map with keys `version`
(`PURITY_CACHE_SCHEMA_VERSION`), `plan_slug`, and `entries` (a `{ "<step-id>":
{…} }` object — JSON keys are strings, so the step id is a string key on disk and
an `int` in memory). An entry's *presence* means the step was **successfully**
purity-checked: empty `findings` reads as "checked, pure," never as "never
checked" or "the call failed." Each entry stores the combined cache key plus its
individual components (`detail_hash`, `all_files_fingerprint`, `change_type`,
`depends_on`, `purity_verdict_logic_version`) separately, so step 4 can grade the
components one at a time rather than only observing that the combined key moved.
The store prunes entries for step ids no longer in the plan on a plan-aware load,
and its writers are serialized by the repo mutation lock (a best-effort, atomic
whole-file `os.replace` write); a lost entry degrades to a re-check, never a
stale verdict. A missing or malformed file loads as an empty cache.

### `PurityCacheEntry` (`purity_cache.py`)

| Field | Meaning |
|---|---|
| `step_id` | the step this entry is about (the `entries` map key, as an `int`) |
| `cache_key` | combined purity cache key from step 1; opaque here, the hit test |
| `detail_hash` | detail-file hash component (step 1); `null` if the detail file was absent |
| `all_files_fingerprint` | `all_files` content-fingerprint component; compared in isolation by step 4 to tell a source-file change from a trivial detail edit |
| `change_type` | the step's `change_type` at check time (component + step 4's #144 frontmatter-OR source) |
| `depends_on` | the step's `depends_on` at check time (component + step 4's #144 frontmatter-OR source) |
| `purity_verdict_logic_version` | `PURITY_VERDICT_LOGIC_VERSION` component at check time; a maintainer bump mismatches every prior entry |
| `detail_relpath` | the step's detail-file relpath at check time; step 4's renumber guard requires it to equal the current relpath so a renumber grades the miss genuine |
| `findings` | the cached purity verdict as a `Recommendation` list; `[]` = checked and pure. Its `confidence` accepts `supported`, `limited`, `null`, or an absent legacy key; absent and `null` load as unknown (`None`) and save as JSON `null`. Invalid confidence makes the whole cache an empty miss so the caller re-checks. |
| `impl_tests_text` | concatenated `## Implementation` + `## Tests` detail-body text at check time (step 4's #144 diff source) |
| `checked_at` | ISO-8601 UTC timestamp for the check |
| `risk_context_rendered` | `true` iff the write-through call that produced this verdict rendered a declared risk-profile advisory into the purity prompt; the read-through audit path treats such an entry as unusable (both the strict hit check and the below-floor graded-reuse path) rather than silently serving a risk-influenced verdict. `false` for every entry written before this field existed |
| schema | file version int (currently **`1` = `PURITY_CACHE_SCHEMA_VERSION`**); mismatches load as an empty cache |

## Project configuration (`.plan-tool/config.json` / `~/.plan-tool/config.json`)

Durable configuration read by `plan_tool/project_config.py`. Branch-awareness
and smell-check readers use `.plan-tool/config.json` with an optional
`~/.plan-tool/config.json` fallback and treat malformed levels as unset. The
closed `roadmap_feedback.stage_limits` contract reads only the project file,
can lower but never raise its hard ceilings, snapshots valid values once per
roadmap run, and fails command preflight before a backend call when its present
block is malformed. It has no user-level fallback and does not change canonical
artifact comments; the one-material-operation-per-active-feedback rule remains
fixed outside configuration.

| Key | Meaning |
|---|---|
| `branch_awareness` | block controlling branch-awareness behavior |
| `enabled` | boolean nested under `branch_awareness`; enables branch-aware guards |
| `branch_prefixes` | list of valid branch ref prefixes nested under `branch_awareness` |
| `smell_checks` | block for repo-structural advisory smell checks |
| `validation_machinery_paths` | list of tool-owned audit machinery paths nested under `smell_checks` |
| `roadmap_feedback` | project-only block for closed stage-feedback behavior |
| `stage_limits` | strict numeric caps nested under `roadmap_feedback` |
| `max_active_feedback_items` | positive cap at or below the hard 32 active-item ceiling |
| `max_response_bytes` | positive cap at or below the hard 32 KiB reply ceiling |
| `max_prose_amendment_bytes` | positive cap at or below the hard 4 KiB row-prose ceiling |

## Intentional exclusions

No registered serialized fields or JSON keys are intentionally undocumented.
`SavedReview.path` is documented as in-memory only, not as a serialized
exclusion.

## CLI JSON payloads

These payloads are serialized for machine consumers but are not persisted by the
tool. Keep them stable enough for CI/report parsers, but they are not read back
at runtime the way saved-review sidecars are.

### `completeness-audit --json`

Top-level shape:

| Field | Meaning |
|---|---|
| `plan` | requested plan name/slug |
| `checks` | deterministic and conceptual finding groups |
| `coverage` | conceptual-audit pass budget and confidence signal |
| `qualified_result` | additive final decision object with `headline`, `stage`, `coverage`, immutable audit-time `revision_status`, and nullable nested `audit_revision`; it is `null` only when a caller renders recovery-only rather than a final result |
| `detail_grade` | which detail bundle grounded the audit (`"jira"`). Present **only** under a non-default `--grade`, so a run-grade payload is unchanged |
| `detail_bundle_fingerprint` | the artifact→digest map the audit read, as grounding provenance. Emitted under the same non-default-grade condition as `detail_grade` (`{}` when no artifact was on disk) |
| `audit_shape_advisory` | present only for a current run-grade saved advisory; its additive object contains `shape_id`, source fingerprint, resolved arm step ids/titles, counts, and axis-grouped anchor slugs (never finding prose or opaque finding ids) |
| `has_blocking_findings` | `True` when blocking findings are present under the stage bar (conceptual recs use `is_blocking_finding` at the hoisted `stage`; deterministic arms unchanged); process rc remains 0 unless `--fail-on-findings` is set |
| `stage` | `"bare"` or `"detail"` — the hoisted audit stage that selected the conceptual bar |
| `audit_incomplete` | `True` when the conceptual-audit sample did not qualify (no conforming pass or malformed/failed passes), reached its `budget_limited` pass cap, or ended early with `early_stop_reason: "plan-quota"` -- pass-conformance and confirmation are different axes; a still-discovering run ordinarily has every pass parse cleanly, so conformance alone can't stand in for confirmation |
| `conceptual_bar_blocking_ids` | stable finding ids where the stage bar blocks on conceptual findings; `null` when `audit_incomplete` is true (never `[]` as “measured none”) |
| `stop_reason` | present when the iterate loop set a stop reason (e.g. `converged`, `terminal_hand_apply`) |
| `halt_reason` | present only when an iterate loop halted early |
| `early_exit_code` | present only when an iterate halt controls the process rc |

Every recommendation-derived object in `checks` carries `confidence` as the
raw `supported`, `limited`, or legacy-normalized `unknown` value. The human
rendering's `confidence: <value>` label is not part of this JSON field.

`qualified_result.audit_revision` identifies the plan, grade-selected detail
bundle, and the optional inputs the audit sampled: (v2, BACKLOG #162) the
plan's `source_seed` file as `source_seed_digest`, and (v3) the confirmed
project context as `project_context_digest`. Either digest is `null` when its
input was absent. A later sidecar reader may calculate an unpersisted
`view_revision_status` of `current`, `stale`, `unknown`, or `not-sampled` from
those artifacts; a seed or project-context edit after the report was saved
counts as staleness the same way a plan or detail edit already does.
The revision records only the digest of the rendered confirmed profile; it
does not persist its contents or claim that broader live project context is
captured or reproducible.

A saved report is a durable artifact, not a cache — pre-v2 reports were
already committed when `source_seed_digest` was added — so older revisions
read missing optional digests as `null` rather than getting rejected.
Rejecting them would cascade through `normalize_qualified_result` and throw
away the report's whole verdict (`headline`/`stage`/`coverage`/
`revision_status`), not just its freshness signal.

`coverage` mirrors the markdown report's coverage-confidence block:

For `"unknown-legacy"`, every verdict field below is `null`; this records
missing evidence rather than a clean conceptual-audit result.

| Field | Meaning |
|---|---|
| `evidence_status` | `"observed"` for a saved/fresh normalized producer result, or `"unknown-legacy"` when a reused legacy sidecar omitted or malformed its optional coverage provenance |
| `budget_limited` | `True` when the conceptual audit reached its pass cap without a clean dry tail, so coverage is unconfirmed |
| `early_stop_reason` | present as `"plan-quota"` when conceptual sampling ended after the typed terminal provider outcome; this distinct unconfirmed state preserves the actual attempted count and configured cap without claiming a pass-cap stop, cannot qualify as reusable evidence or a clean qualified result, and leaves no ordinary final findings sidecar (non-JSON runs still retain the Markdown report) |
| `passes_used` | number of conceptual-audit passes consumed, or `null` when no conceptual audit ran |
| `cap` | pass cap in force for that audit, or `null` |
| `recommendation_kind` | compatibility-only; always `null` |
| `recommended_passes` | compatibility-only; always `null` |
| `recommendation_advice` | compatibility-only; always `null` |
| `confirmation_kind` | `"confirmed-dry"` \| `"confirmed-low-yield"` (BACKLOG #125), or `null` when coverage is unconfirmed |
| `conforming_pass_count` | number of outer conceptual-audit passes that returned exit 0 with both required findings headings present |
| `failed_or_malformed_pass_count` | number of outer passes where the invoker failed, headings stayed missing after retry, or the pass errored |

## Run log events (`<repo-root>/.plan-tool/runs/<slug>/<run_id>.jsonl`)

Append-only JSONL written by `plan_tool/run_log.py:RunLogWriter` and read back by
`read_run_events` / `read_run_outcome` and the `plan-tool runs` subcommand. Every
line carries `ts`, `run_id`, and the `event` discriminator; the emit helpers merge
caller `**extra` keys into the payload, so a line is a *superset* of its event
dataclass's fields.

`claude_call_start.prompt_sha256` is an optional SHA-256 hex digest of the
exact UTF-8 prompt, with no prompt text stored. New events default to null
when no prompt is available; older events lack the key. This additive field
does not change the schema version or backend-specific token accounting.

**The event catalog is the `Event` union in `run_log.py`, not this doc.** Only the
events registered in `plan_tool/data_contract.py` are drift-guarded here — the
rest are documented by their dataclasses. A per-line size cap
(`_MAX_LINE_BYTES`, 4096) keeps one `O_APPEND` write atomic, so any event
embedding caller prose bounds it before serializing.

**`run_end`'s `termination_reason` is tracked, not threaded through.**
`RunLogWriter.run_end(...)` accepts an optional `termination_reason` kwarg
that, when omitted (every one of its 23 existing call sites), falls back to
the writer's own tracked value — whatever `BackendTermination` or
`RunInterrupted` most recently set on that writer via their `reason` /
`"operator_interrupt"`. No call site needs to thread the reason through by
hand, and a run that never reaches either event (`jira`, `annotate`, and
`create.py`'s slug-generation call, none of which open a `RunLogWriter` at
all) keeps emitting `run_end` with no `termination_reason` key at all, rather
than an explicit `null`.

`RunLogWriter.reset_termination_reason()` clears the tracked value back to
untracked. A command that processes several rows under one writer (seed
`--materialize` / `--refresh-seeds`, see below) calls this once a batch of
more than one row finishes, so `run_end` doesn't report one row's backend
outcome as if it summarized the whole batch — it either omits the field or
reports what the very next `BackendTermination`/`RunInterrupted` sets.

**`run_end.result` names what `create` and `detail` wrote.** `RunLogWriter.run_end(...)`
accepts an optional `result` mapping that is emitted as `run_end.result`; every
other command omits the key. Paths are repo-relative POSIX strings, or absolute
when the file lies outside the repo (for example under `--output-dir`). A run that writes nothing
(a `create` that splits or refuses; a `detail` that writes no file) still
records the keys, empty or `null`, so "nothing written" is distinct from
"field missing". A `create` that fails or is interrupted after leaving a plan on
disk records that plan, and on any `error` or `interrupted` outcome the lists are a
lower bound: archives moved before the failure may be missing, so a consumer that
needs completeness checks the filesystem. `manifest_updated` on that path means the
plan is registered, not that this run added the entry. A `detail` whose authoring call raised records `null` for
its file fields, whether it failed before writing anything or after some steps:
the record cannot tell those apart, and "unknown" is not reported as "none". A `create` refusal that happens before the slug resolves opens
no run log and is outside this contract.

| Command | Keys |
|---|---|
| `create` | `plan_path` (string or `null`), `manifest_updated` (bool or `null`; true when this run added the entry), `archived_paths` (every archive destination: replaced plans, the normalized artifact, the archived source, the archived provenance seed), `archived_paths_truncated` (bool) |
| `detail` | `detail_files_written` (list or `null`), `detail_files_written_count` (the true count or `null`), `detail_files_truncated` (bool or `null`) |

Both path lists are bounded (about 2 KB of UTF-8) so one event stays under the
run log's line cap; when a list truncates, the flag says so, and `detail` also
keeps the true count.

**`run_end.usage` totals the run's backend calls.** When a run recorded at least
one `claude_call_end` event, `run_end` carries `usage`: `calls` (the count) and one
total each for `tokens_input`, `tokens_output`, `cache_creation_tokens`,
`cache_read_tokens`, and `cost_usd`. A total is the sum over the calls that
reported the field, and `null` when none did. A field only some calls reported
(a retried or failed call has no usage; Codex reports no `cost_usd` and no
cache-creation tokens; Cursor reports no `cost_usd`) is listed in
`partial_fields`, which marks its sum as a lower bound; a field absent from
`partial_fields` is complete. `calls` and the sums cover the run's recorded
`claude_call_end` events, so a call made while no run-log sink was installed is
in neither. `cost_usd` is an API-equivalent estimate, not a charge, and
`cost_usd_basis` says so. A run with no backend call (`jira`, `annotate`, ...)
omits `usage`. Wall time stays `run_end.duration_ms`. Totals do not reconcile
`tokens_input` across backends: Codex counts cached tokens in it and Claude does
not (`input_includes_cached`), and one run uses one backend.

`run_end` never raises on size. If an event with a `result` would exceed the
run log's line cap (a long multibyte `error` plus a full path list), the `result`
is dropped and the event carries `result_dropped: true`; every other field is
kept.

### Roadmap seed-action context and lifecycle

`plan-tool roadmap <slug> --materialize [PLAN_ID]` and `--refresh-seeds` use
the existing `RunLogWriter` lifecycle — `start()`, `phase_start()`,
`phase_end()`, and `run_end()` — to write one command-level JSONL record and
one active `in-flight.json` snapshot. This is writer context and extra fields
on existing events, **not** a new `Event` discriminator, run-log schema
version, or `seed-state.json` schema.

The writer keeps `command: "roadmap"` immutable. The following context travels
on every record and snapshot, including `run_start` and `run_end`; it keeps
command identity separate from `roadmap_action`.

| field | description |
|---|---|
| `roadmap_action` | `"materialize"` or `"refresh-seeds"`; names the seed action under the immutable roadmap command |
| `roadmap_slug` | roadmap slug supplied to the action |
| `requested_plan_id` | explicitly requested `--materialize PLAN_ID`; literal `null` for unqualified materialization and refresh |
| `active_plan_id` | row currently being prepared or materialized; literal `null` when no row is active |
| `seed_attempt` | 1-based candidate-seed correction attempt for the active row; literal `null` when no candidate is active |
| `backend_attempt` | 1-based child-process attempt inside the current candidate; literal `null` before a child starts or when no row is active |
| `backend_child_started` | `true` after a child starts for the current candidate; `false` is the no-child marker and the inactive value |

Every attempted row has a `seed-materialize:<plan-id>` phase. Both actions
follow `PlansArtifact.plans` source order, never `PlansArtifact.ordering`:
an explicitly selected materialization has its one requested row, an
unqualified `--materialize` processes all eligible rows in that order, and
`--refresh-seeds` attempts every row independently in that order. A row's
`phase_end` retains its `active_plan_id`; the immediately following
inter-phase snapshot and all terminal records set `active_plan_id`,
`seed_attempt`, and `backend_attempt` to literal `null`.

The `seed_attempt` / `backend_attempt` pair is authoritative. `seed_attempt`
counts candidate-seed corrections; `backend_attempt` counts child processes
within one candidate. The legacy `attempt` field remains the candidate ordinal
on materializer events and the child ordinal on child-lifecycle events.
`backend_recovery_wait.attempt` stays tied to the child that just failed, while
its `next_attempt` names the next child ordinal. This describes only the safe
lifecycle observer around materialization; it does not prescribe the
materializer's retry implementation.

The closed terminal `run_end.outcome` vocabulary for these actions is:

| outcome | meaning |
|---|---|
| `completed` | all attempted rows finish without an exhausted row |
| `no-op` | materialization finds no eligible row to attempt |
| `partial` | a batch has both completed work and one or more exhausted rows |
| `exhausted` | attempted backend work exhausts without a completed row |
| `preflight-refused` | command or row preparation refuses before backend work can proceed |
| `interrupted` | the lifecycle handles `KeyboardInterrupt` and terminates with the interrupt boundary |
| `error` | an unexpected post-start failure terminates the command; it remains distinct from exhausted backend work |

These lifecycle outcomes are not the command-result values in
`RoadmapSeedRefreshResult` or the `SEED_REFRESH_OUTCOME_*` constants. The CLI
keeps its existing result rendering and exit-code meanings; readers use the
terminal outcome together with `rc` to interpret the durable record.

Seed-action logs are redacted by contract. They may retain lifecycle timing,
retry counters, safe failure kind, numeric return code, and aggregate counts.
They must not retain prompts, seed bodies, replies, reply heads, validation
prose, `failure_detail`, provider transcripts, or tool-input summaries.
`_render_seed_refresh_report()` remains a human-facing report outside this log
contract.

### `AttemptFailed` (`run_log.py`)

Emitted once per failed attempt, for **every** failure kind, including the
attempt that spends the retry budget.

Without it, an attempt that fails and then **recovers** leaves no trace at all:
the stage writes its artifact, `failure_kind` reaches `RoadmapResult` only on
the exhausted path, and `gate_violations` speaks for one kind of four. Measured
2026-08-04 on `cfp-review`'s spelling run — stage 1 spent an attempt with `rc:
0`, 22,746 stdout bytes and no `gate_violations`, which narrowed the cause to
`FAILURE_PARSE` or `FAILURE_AUTHORED_REVIEW_ROWS` and no further. Recovery is
the *common* case, so this is the event that makes retry pressure readable.
It discharged the retry-budget question (closed 2026-08-05, no action —
`docs/history/backlog-decisions.md`).

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"attempt_failed"` |
| `phase` | the phase whose attempt failed (e.g. `"stage-1-domain"`) |
| `attempt` | 1-based attempt number within that phase |
| `failure_kind` | one of `roadmap.py`'s four: `"invoke"`, `"parse"`, `"authored-review-rows"`, `"gates"` |

Producer: `plan_tool/roadmap.py:_run_stage`. Deliberately carries **no** reply
bytes, rc, or duration — `claude_call_end` already records `rc`,
`duration_ms` and `stdout_bytes` for the same `(phase, attempt)`, so this event
adds only the fact those cannot supply. The gates kind emits **both** this and
`gate_violations`; that redundancy is the point, since a consumer counting
spent attempts by kind then reads one event type rather than unioning two.

### `ModelFailureReceipt` (`run_log.py`)

Emitted after a producer finishes its best-effort rejected-response sidecar
write. It gives every migrated producer one redacted terminal evidence envelope
without changing run-log snapshot refresh or cleanup.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"model_failure_receipt"` |
| `phase` | producer-owned phase for the rejected response |
| `attempt` | 1-based attempt number within that phase |
| `reason` | open producer-owned failure or terminal-outcome string; this event introduces no shared reason vocabulary |
| `response_bytes` | UTF-8 byte count of the rejected response, or `null` when there is no response |
| `response_sha256` | SHA-256 digest of the rejected response bytes, or `null` when there is no response |
| `sidecar_disposition` | one of `"written"`, `"no-response"`, `"not-retained"`, or `"write-failed"` from `ModelResponseSidecarResult` |
| `sidecar_path` | repository-relative sidecar path only when `sidecar_disposition` is `"written"`; otherwise omitted from the event |

The receipt never contains raw response or prompt text, validation prose,
provider transcripts, tool-input summaries, or sidecar-write error prose.
`no-response` takes precedence when no response bytes exist, so both identity
fields are `null` and no sidecar path is recorded. A failed or intentionally
skipped sidecar write still preserves the response byte count and digest when
the producer received response bytes.

**`plan-tool run` emits this receipt for a mutating step that fails on one of
the five paths below** — not for a step that ends by exception (a raised
invoker error, an interrupt) or when no run logger is attached — with
`phase: "claude_call"`, `attempt: 1`, and the sidecar under
`.plan-tool/parse-failures/_run/<plan-slug>/` (the run log's own slug). Its
`reason` values are
`invoke` (non-zero exit or `is_error`), `no-edits-applied` (exit 0, every
declared file unchanged), `test-authoring-gate`, `test-gate`, and `gate`.
A step that declares no files is exempt from `no-edits-applied`.

The sidecar holds the model's final reply unfiltered (the whole stream when
no final text was captured), which can contain credential-shaped text. It is
local operator evidence; a caller that surfaces it must filter it first.

### `GateViolations` (`run_log.py`)

Emitted once per attempt whose gates rejected the artifact, including the attempt
that spends the retry budget. Without it `phase_end`'s `ok`/`exhausted` outcome
makes a stage that passed on its last attempt indistinguishable from a clean
first-try pass — measured 2026-08-01, when the first real `roadmap` run spent
3 of 3 attempts on the constraints stage and nothing recorded which of that
stage's six rules it was missing.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"gate_violations"` |
| `phase` | the phase whose attempt failed (e.g. `"stage-2-constraints"`) |
| `attempt` | 1-based attempt number within that phase |
| `violation_count` | **exact** total violations that consumed the attempt, whether or not each message was retained |
| `violations` | the violation messages, **whole** — messages are dropped rather than cut, so a retained message is always the one the gate made. Bounded by `_MAX_VIOLATION_BYTES_IN_PAYLOAD`; the first message is retained whatever its size and is elided visibly (`…<elided N chars>`) if it alone exceeds the per-string cap |
| `violations_omitted` | how many messages did not fit — `violation_count - len(violations)` |

Producer: `plan_tool/roadmap.py:_run_stage`. The other **three** roadmap failure
kinds produce **no** violations, because in each the gates never ran: `invoke`
and `parse` never yielded an artifact to gate, and `authored-review-rows`
refuses an artifact that *did* parse, before the gate call. So none of the three
emits an event of this kind; they are readable from `AttemptFailed` above,
which every kind emits.

### `BackendSpawn` (`run_log.py`)

Emitted immediately before a backend child process runs. Marks the start of
the window `BackendTermination` closes.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"backend_spawn"` |
| `phase` | the phase spawning the child (e.g. `"claude_invoke"`, `"claude_call"`) |
| `attempt` | 1-based attempt number within that phase |
| `backend` | the active backend's name (e.g. `"claude"`) |
| `transport` | which of argv/stdin carries the prompt — a safe descriptor only, never the `PromptTransport` object |
| `child_pid` | the spawned child's PID |
| `effective_timeout_ms` | the earlier of the configured timeout and the silence threshold |
| `prompt_bytes` | prompt size in bytes |
| `stream_log` | file name of the call's raw stream log in the sibling `<run_id>.streams/` directory; `null` when no log was written (suppressed content output, open failure) |

Producer: `plan_tool/backend_runner.py:run_streaming_once`, the sole emitter
for both the streaming and batch lanes — `plan_tool/shell.py:claude_invoke`
routes both through it, so every optional field is populated for either lane.

### `BackendTermination` (`run_log.py`)

Emitted once a backend child process ends, however it ended. Closes the window
`BackendSpawn` opens.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"backend_termination"` |
| `phase` | the phase whose child ended |
| `attempt` | 1-based attempt number within that phase |
| `backend` | the active backend's name |
| `reason` | open string, producer-owned — follows `AttemptFailed.failure_kind`'s convention rather than importing a closed vocabulary. Both lanes share `backend_runner.TerminationReason`'s full seven-value vocabulary: `"completed"`, `"configured_timeout"`, `"silence_timeout"`, `"operator_interrupt"`, `"spawn_failure"`, `"backend_nonzero"`, `"unknown"` |
| `duration_ms` | wall-clock duration of the child's run, reused from the caller's own timing rather than measured again |
| `signal_or_timeout` | which kill mechanism fired, when one did |
| `silent_ms` | how long the child had been silent at termination |

Producer: `plan_tool/backend_runner.py:run_streaming_once`, the sole emitter
for both lanes, classifying with the full seven-value `TerminationReason`
vocabulary. Setting `reason` also updates the emitting writer's tracked
termination reason — see `run_end`'s `termination_reason` below.

### `RunInterrupted` (`run_log.py`)

Emitted when an operator interrupt (Ctrl-C) lands during a window this plan
gives its own handling: a rate-limit/transient recovery wait (`source`
`"recovery_wait"`), or anywhere in the shared runner's window from a
successful `subprocess.Popen()` spawn call (`source` `"spawn"`) through its
`proc.wait()` returning (`source` `"proc_wait"`).

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"run_interrupted"` |
| `phase` | the phase that was interrupted |
| `attempt` | the attempt that was in flight (the just-failed attempt whose retry the interrupted wait was waiting to make, not the upcoming one) |
| `source` | open string, producer-owned — same convention as `reason` above. Backed by `backend_runner.InterruptSource`'s three-value vocabulary: `"recovery_wait"` (an interrupt caught during the rate-limit/transient recovery wait), `"spawn"` (an interrupt caught around the shared runner's `subprocess.Popen()` call), or `"proc_wait"` (an interrupt caught anywhere between a successful `Popen()` and the shared runner's `proc.wait()` returning) |
| `signal` | fixed label, always `"SIGINT"` — every interrupt this plan produces is Python's `KeyboardInterrupt`, the main-thread SIGINT translation. Reserved for a future non-SIGINT source, not classification work |

Producer: three sources, all writing `backend_runner.InterruptSource` members
rather than a repeated string literal. `source="recovery_wait"` comes from the
two wrapper factories in `plan_tool/claude_errors.py`
(`make_backend_recovery_wait_seam` / `make_backend_recovery_sleep_seam`) that
`shell.py:claude_invoke` and `launcher.py:shell_invoker` thread through
`rate_limit_loop.run_with_rate_limit_recovery`'s `wait` / `sleep` seams.
`source="spawn"` and `source="proc_wait"` both come from
`plan_tool/backend_runner.py:run_streaming_once`, via its shared
`_finalize_interrupted_call` helper: `"spawn"` for an exception around its
`subprocess.Popen()` call, `"proc_wait"` for one anywhere from a successful
spawn through its `proc.wait()` call returning.
Every row of this kind *is* an operator interrupt by construction, so there is
no separate `reason` field. Emitting this event also sets the writer's tracked
termination reason to `"operator_interrupt"`, which always wins over an
earlier `BackendTermination` on the same writer — nothing in this plan runs
after the interrupt propagates, which is what makes plain last-write-wins
already correct.

### `BackendRecoveryWait` (`run_log.py`)

Emitted before the shared rate-limit/transient recovery loop
(`rate_limit_loop.run_with_rate_limit_recovery`) sleeps between attempts —
the quiet window between one attempt's `BackendTermination` /
`claude_call_end` and the next attempt's `BackendSpawn`, which otherwise
carries no event at all and is indistinguishable from a genuine hang from the
JSONL alone.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"backend_recovery_wait"` |
| `phase` | the phase whose retry loop is waiting |
| `attempt` | the just-failed attempt whose retry this wait precedes |
| `reason` | `"rate_limit"` or `"transient"` — the loop's two distinct sleep seams (`wait(target)` on the RATE_LIMIT path, a separate `sleep(delay)` callable the TRANSIENT path calls directly) |
| `delay_ms` | the wait's duration: target-minus-current-clock for a rate-limit wait, the backoff delay directly for a transient sleep |
| `next_attempt` | the upcoming retry's ordinal number, matching the `attempt` field every other call event already carries — not a timestamp |
| `backend` | the active backend's name |

Producer: the same two `claude_errors.py` wrapper factories as
`RunInterrupted` above. Emitted only when a `RunLogWriter` is bound at wait
time (read fresh via a zero-argument accessor, not resolved once at
seam-construction time) — with no writer bound, the wrapping is a silent
no-op and callers behave exactly as before this event existed.
`rate_limit_loop.py` itself never emits this event or any other: it is a
stdlib-only leaf with no first-party imports, so the seam-wrapping caller
(`shell.py`, `launcher.py`) emits, never the leaf.

### `RoadmapPreflightFailed` (`run_log.py`)

Emitted when a stage run stops before invoking a stage. The explanatory prose
remains on `run_end` and stderr; this short category lets run-log consumers
group failures without parsing human-facing error text.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"roadmap_preflight_failed"` |
| `check` | producer-owned failed preflight category: `accepted_head`, `pre_head_state`, `brief_source`, `brief_read`, `publication_recovery`, `resume_brief_digest`, or `carried_decisions` |

### `RoadmapStageWritten` (`run_log.py`)

Emitted once per stage the run holds for resume, after the stage's text parses
and passes its gates. The stage is held under the run directory's
`roadmap-stage-resume/`, not published: the version store receives all four
stages together when the run completes. The event records aggregate effects
only: a digest and the always-zero inline draft-seed count, not artifact
contents.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"roadmap_stage_written"` |
| `phase` | phase that wrote the artifact, such as `stage-2-constraints` |
| `stage` | numeric roadmap stage |
| `artifact_path` | repository-relative when possible path of the held stage file under `roadmap-stage-resume/` |
| `artifact_digest` | SHA-256 digest of the held stage text |
| `replaced` | always `false`; a held stage never replaces a published artifact |
| `draft_seed_count` | always `0`; stages never write draft-seed bodies inline |

### `RoadmapSeedApplyResult` (`run_log.py`)

Emitted once by every `roadmap --apply` invocation, including recommend-only
and refuse-by-default outcomes. The containing run uses `command: "roadmap"`
and `flags.mode: "apply"`; this event gives the aggregate promotion effects.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"roadmap_seed_apply_result"` |
| `outcome` | `"applied"`, `"recommended"`, or `"refused"` |
| `target_count` | draft-to-destination targets considered; seeds already recorded as published are skipped and not counted |
| `promotion_count` | target bodies promoted into `plan-seeds/` |
| `collision_count` | destination collisions that prevented promotion |
| `missing_draft_count` | draft seeds classified `missing` |
| `malformed_draft_count` | draft seeds classified `malformed` |
| `stale_draft_count` | draft seeds classified `stale` |
| `path_escaping_draft_count` | draft seeds classified `path-escaping` |
| `duplicate_draft_count` | draft seeds classified `duplicate` |
| `digest_mismatched_draft_count` | draft seeds classified `digest-mismatched` |

## Roadmap evidence lifecycle records

### Candidate approval records

The feedback lifecycle persists immutable candidate versions and their
evidence, immutable `CandidateReviewSeal` records, and an
`AcceptedRoadmapHead` selector. `CandidateProposalEvidence` records the
candidate and predecessor identities, review lineage, raw-brief and artifact
digests, content identity, predecessor diff, gate evidence, capsule and
receipt, plus batch-only `root_version_id`, `source_version_id`,
`batch_receipt`, `normalized_operations`, and `operation_classification` when
the selector-free ledger route produced them. These are stored facts, not live
ledger input and not publication authority.

Newly written initial and edited candidates persist both fields. Batch evidence
without the operation/route pair remains readable for its existing lifecycle but
cannot enter the structural decision: that is evidence stored before the route
existed and every answered-review replacement, which is refused at storage when
its own computed classification is structural and persists neither field. In
a stack, a hop with no stored route contributes nothing to whether the stack is
structural.

A structural approval persists a `CandidateReviewSeal` with
`decision: "structural-approval"`, `initial_candidate_version_id`,
`approved_candidate_version_id`, `approved_content_identity`, and
`final_capsule_identity`; batch seals additionally bind the root, source, and
batch-receipt identities. The seal binds exactly one reviewed candidate, the
top of the stack it covers. Only the approve invocation that carries a
`--confirm-stack-digest` equal to the digest recomputed at confirm time creates
it. No stack or digest field is persisted: the unpromoted stack is derived at
use from the stored candidate records above the recorded root, and the digest
is recomputed from their stored facts, so it is neither a stored receipt nor a
seal binding. Edit stores a replacement candidate for a fresh decision, while
rejection releases the active candidate and the unpromoted hops beneath it
without deleting immutable records.

`AcceptedRoadmapHead` persists only its schema version, roadmap slug, and
accepted `version_id`. `promote_review_seal` is the publication boundary: it
accepts a stored seal only after its accepted-root, active-candidate, stored
candidate, decision, and gate bindings remain current, then journals the head
change and the active-pointer release, plus the seed-state member when
any hop above the recorded root stores a structural route; promotion re-derives
that stack, requires the `structural-approval` seal for it, and recovery applies
the same rule. Candidate
creation, review, replacement, rejection, failed validation, interruption, and
staleness do not write that selector or canonical artifact bytes. The selector
and seal retain identities and digests; immutable candidate versions contain
artifact bytes, and candidate evidence can contain reviewer requests, typed row
content, and the context payload issued to the model. Candidate evidence and
seals retain no raw model reply; a rejected reply is kept only in the
parse-failure sidecar under `.plan-tool/parse-failures/`.

The six registered roadmap-evidence lifecycle records below persist only event
identity, safe identifiers, digests, counts, and closed outcomes. They retain
no source prose, baseline contents, reviewer requests, prompts, replies, or
backend text. No current command emits these six events; their payloads stay
registered in `plan_tool/run_log.py` so run logs written earlier remain
interpretable. These tables document the durable redacted event payloads only.

### `RoadmapStructuralRevisionPreflight` (`run_log.py`)

Emitted once when the structural-revision runner reaches its redacted
preflight boundary. It retains only safe identifiers, SHA-256 identities, and
closed status facts. It never stores a receipt body, analysis body, feedback
text, roadmap prose, prompt, backend reply, evaluator configuration, path, or
exception detail.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"roadmap_structural_revision_preflight"` |
| `receipt_final` | SHA-256 identity of the admitted immutable receipt, or `null` |
| `analysis_final` | SHA-256 identity of the admitted immutable impact analysis, or `null` |
| `artifact_key` | receipt-safe selected artifact key, or `null` |
| `feedback_id` | receipt-safe selected feedback identifier, or `null` |
| `target_row_id` | receipt-safe selected target row identifier, or `null` |
| `binding_digest` | SHA-256 identity of the complete accepted binding, or `null` |
| `render_canonical` | resolved canonical-rendering result, or `null` before it runs |
| `verdict` | one of `"mode-rejected"`, `"evaluator-rejected"`, `"enrolled-roadmap-rejected"`, `"evidence-rejected"`, `"changed-brief"`, `"legacy-brief"`, `"feedback-rejected"`, `"render-canonical-rejected"`, `"accepted"`, or `"interrupted"` |

The preflight facts follow one closed matrix. `mode-rejected`,
`evaluator-rejected`, `enrolled-roadmap-rejected`, and `interrupted` retain no
evidence, selection, binding,
or canonicality facts. `evidence-rejected`, `changed-brief`, and `legacy-brief`
retain exactly the complete `receipt_final`/`analysis_final` pair.
`feedback-rejected` additionally retains
the selected `artifact_key` and `feedback_id`. `render-canonical-rejected`
additionally retains `target_row_id` and sets `render_canonical` to `false`.
`accepted` requires every field through `binding_digest` and sets
`render_canonical` to `true`. A partial final pair, unsafe identifier, binding
before complete canonical evidence, or later-stage fact on an earlier rejection
is invalid.

`changed-brief` and `legacy-brief` refuse a valid request after evaluator
admission and guarded recovery when the decoded current brief differs from its
accepted baseline or that baseline is absent. `mode-rejected` covers malformed final names and mixed or incomplete command
forms without retaining their raw values. `evaluator-rejected` covers an
unavailable, malformed, or version-mismatched fixed evaluator, unavailable
host-isolation provider, or failed workspace-read denial without retaining its
version, path, configuration, or error string. `enrolled-roadmap-rejected`
covers the immutable-authority fence before structural evidence is admitted.
Rejected and interrupted
preflight events do not have a structural attempt event; an accepted preflight
will have exactly one attempt with `attempt: 1`.

### `RoadmapStructuralRevisionAttempt` (`run_log.py`)

Emitted once after an accepted structural preflight. It records the terminal
phase matrix for one physical rewrite request. It has no extension bag and
never stores feedback text, roadmap prose, prompt, backend reply, artifact
content, path, or exception detail.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"roadmap_structural_revision_attempt"` |
| `attempt` | always integer `1` |
| `binding_digest` | required SHA-256 identity of the complete accepted binding |
| `invalidated_seed_count` | nonnegative invalidated seed count after publication, otherwise `null` |
| `operation_verdict` | `"not-reached"`, `"accepted"`, or `"rejected"` |
| `merge_verdict` | `"not-reached"`, `"accepted"`, or `"rejected"` |
| `proof_verdict` | `"not-reached"`, `"structural-rejected"`, `"gate-rejected"`, or `"accepted"` |
| `final_snapshot_verdict` | `"not-reached"`, `"current"`, or `"stale"` |
| `publication_outcome` | `"not-reached"`, `"published"`, `"failed"`, or `"unknown-after-interrupt"` |
| `outcome` | `"invoke-failed"`, `"empty-reply"`, `"envelope-rejected"`, `"merge-rejected"`, `"proof-rejected"`, `"final-snapshot-stale"`, `"changed-brief"`, `"legacy-brief"`, `"publication-failed"`, `"published"`, or `"interrupted"` |

Only `published` carries a nonnegative `invalidated_seed_count`; every other
outcome carries `null`. The outcome matrix is closed:

| `outcome` | `operation_verdict` | `merge_verdict` | `proof_verdict` | `final_snapshot_verdict` | `publication_outcome` |
|---|---|---|---|---|---|
| invoke-failed / empty-reply | `not-reached` | `not-reached` | `not-reached` | `not-reached` | `not-reached` |
| envelope-rejected | `rejected` | `not-reached` | `not-reached` | `not-reached` | `not-reached` |
| merge-rejected | `accepted` | `rejected` | `not-reached` | `not-reached` | `not-reached` |
| proof-rejected | `accepted` | `accepted` | `structural-rejected` or `gate-rejected` | `not-reached` | `not-reached` |
| final-snapshot-stale | `accepted` | `accepted` | `accepted` | `stale` | `not-reached` |
| changed-brief / legacy-brief | `accepted` | `accepted` | `accepted` | `stale` | `not-reached` |
| publication-failed | `accepted` | `accepted` | `accepted` | `current` | `failed` |
| published | `accepted` | `accepted` | `accepted` | `current` | `published` |

`interrupted` permits only an incomplete prefix of the successful path and
always retains `null` for `invalidated_seed_count`. `unknown-after-interrupt`
is valid only after `final_snapshot_verdict: "current"`, when replacement may
have started. Every other phase tuple is invalid.

### `RoadmapEscalationPreflight` (`run_log.py`)

Emitted before immutable escalation evidence can be published. It records only
resolved receipt-safe identifiers and closed lifecycle facts; raw selector and
reason inputs, reviewer content, source bytes, and exception text never enter
the event.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"roadmap_escalation_preflight"` |
| `artifact_key` | resolved receipt-safe artifact key, or `null` before selector admission |
| `feedback_id` | resolved receipt-safe feedback id, or `null` before selector admission |
| `reason` | one closed reason, or `null` before reason admission: `"prose"`, `"row-structure"`, `"collection-structure"`, `"relationship-semantics"`, `"decision-semantics"`, or `"cross-artifact-impact"` |
| `target_kind` | resolved `"artifact"` or `"row"` target kind, or `null` before accepted selection |
| `target_id` | resolved receipt-safe target id, or `null` before accepted selection |
| `artifact_digest` | SHA-256 of readable selected source bytes, or `null` before source decoding succeeds |
| `verdict` | `"mode-rejected"`, `"malformed-selector"`, `"unknown-artifact"`, `"identifier-rejected"`, `"reason-rejected"`, `"artifact-unreadable"`, `"artifact-unparsable"`, `"artifact-not-current"`, `"missing-feedback"`, `"duplicate-feedback"`, `"not-open"`, `"already-responded"`, `"missing-or-ambiguous-target"`, `"target-not-live-in-selected-artifact"`, `"accepted"`, or lifecycle-only `"interrupted"` |

Fields are monotonic. Selector failures and the all-null `interrupted`
preflight record no resolved facts. A valid reason follows an admitted selector;
source digest follows strict UTF-8 decoding; target fields appear only for an
accepted selected-artifact result. Any other preflight verdict leaves later
facts `null`.

### `RoadmapEscalationResult` (`run_log.py`)

Emitted once after a receipt preflight event when receipt lifecycle telemetry is
available. It is the terminal receipt fact, not a place for a storage error or
reviewer prose. A telemetry failure is intentionally not emitted because the
sink cannot establish that the record persisted.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"roadmap_escalation_result"` |
| `outcome` | `"preflight-rejected"`, `"storage-rejected"`, `"created"`, `"committed-existing"`, `"reused"`, `"collision"`, `"invalid-existing-receipt"`, `"write-failed"`, `"commit-failed"`, or `"interrupted"` |
| `receipt_id` | durable receipt semantic identity only for `"created"`, `"committed-existing"`, or validated `"reused"`; otherwise `null` |
| `handoff` | `"requires-scope-review"` only with a durable receipt identity; otherwise `null` |

For a root-valid creation with an available sink, the ordering is one preflight,
one result, then `run_end` with the same outcome and process status. The status
map is `0` for `created`, `committed-existing`, and `reused`, `2` for
`preflight-rejected`, `1` for `storage-rejected`, `collision`,
`invalid-existing-receipt`, `write-failed`, `commit-failed`, and
`telemetry-unavailable`, and `130` for `interrupted`. Startup or preflight
append failure blocks publication and returns the unpersisted
`telemetry-unavailable` result. An interruption before startup returns promises
no receipt lifecycle; an interruption inside an event append makes no exact
pair claim or compensating append.

### `RoadmapImpactPreflight` (`run_log.py`)

Emitted before immutable impact-analysis evidence can be published. It records
only a safe requested receipt final, validated receipt facts, aggregate counts,
redacted mapping diagnostics, and digest facts. It never records raw command
arguments, paths, artifact or brief content, an artifact-digest vector,
reviewer prose, prompts, backend data, or relation identifiers.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"roadmap_impact_preflight"` |
| `receipt_final` | SHA-256 final requested for analysis, or `null` before parsing establishes one |
| `artifact_key` | validated receipt-safe selected artifact key, or `null` before receipt admission |
| `feedback_id` | validated receipt-safe selected feedback id, or `null` before receipt admission |
| `reason` | validated receipt reason: `"prose"`, `"row-structure"`, `"collection-structure"`, `"relationship-semantics"`, `"decision-semantics"`, or `"cross-artifact-impact"`; otherwise `null` |
| `target_kind` | validated receipt target kind, `"artifact"` or `"row"`; otherwise `null` |
| `target_id` | validated receipt-safe target id, or `null` before receipt admission |
| `receipt_source_digest` | SHA-256 digest bound to the validated receipt's selected source, or `null` before receipt admission |
| `source_record_digest` | SHA-256 digest of exact raw recorded-source bytes, or `null` before snapshot admission |
| `brief_digest` | SHA-256 digest of decoded recorded-brief text, or `null` before snapshot admission |
| `snapshot_artifact_count` | nonnegative count of captured snapshot artifacts, or `null` before snapshot admission |
| `closure_node_count` | nonnegative count of selected closure nodes, or `null` before closure resolution |
| `closure_relation_count` | nonnegative count of selected closure relations, or `null` before closure resolution |
| `closure_mapping_failures` | ordered sequence of redacted `(source_index, owner_match_count, endpoint_match_count)` triples for reached unmappable relations, or `null` before closure resolution; it contains no relation identifiers |
| `verdict` | one closed admission verdict: `"mode-rejected"`, `"final-rejected"`, `"receipt-missing"`, `"receipt-unreadable"`, `"receipt-invalid"`, `"receipt-rejected"`, `"changed-brief"`, `"legacy-brief"`, `"snapshot-rejected"`, `"closure-rejected"`, `"accepted"`, or `"interrupted"` |

Facts are prefix-ordered. `mode-rejected`, `final-rejected`,
`receipt-missing`, `receipt-unreadable`, `receipt-invalid`, and an early
`interrupted` event carry no receipt, snapshot, or closure facts; they can carry
only a parser-established safe `receipt_final`. `receipt-rejected`,
`changed-brief`, and `legacy-brief` can add the complete validated receipt
group, but `changed-brief` and `legacy-brief` leave every snapshot and closure
fact `null`. `snapshot-rejected` can additionally add the two snapshot digests
and artifact count. `closure-rejected` can additionally
add both closure counts and the redacted mapping diagnostics. `accepted`
requires the complete resolved set. An
interruption after admission preserves only the complete prefix reached before
it; no verdict can disclose a later-phase fact. Any populated receipt,
snapshot, or closure group requires every member of that group and all earlier
groups.

### `RoadmapImpactResult` (`run_log.py`)

Emitted only after its own append succeeds. It records terminal impact-analysis
lifecycle facts separately from the immutable route and publication facts; it
never records evidence content or mutable publication authority.

| field | description |
|---|---|
| `ts` | ISO-8601 UTC timestamp |
| `run_id` | the run that emitted the event |
| `event` | discriminator, always `"roadmap_impact_result"` |
| `outcome` | `"completed"`, `"preflight-rejected"`, `"changed-brief"`, `"legacy-brief"`, `"invalid"`, `"storage-rejected"`, `"collision"`, `"write-failed"`, or `"interrupted"` |
| `analysis_id` | SHA-256 immutable analysis identity only for `"completed"`; otherwise `null` |
| `route_class` | `"same-artifact"`, `"cross-artifact"`, or `"requires-scope-review"` only for `"completed"`; otherwise `null` |
| `publication_outcome` | `"created"` or `"reused"` only for `"completed"`; otherwise `null` |
| `next_workflow` | `"roadmap-same-artifact-structural-revision"` for `"same-artifact"`, `"roadmap-cross-artifact-revision-transaction"` for `"cross-artifact"`, and `null` for `"requires-scope-review"` and every failure outcome |

`completed` always includes exactly one analysis identity, route class, and
publication outcome. A durable scope-review analysis remains completed and
records its identity and publication outcome while its workflow stays `null`.
Every noncompleted outcome, including `changed-brief` and `legacy-brief`,
leaves all four analysis facts `null`.
`telemetry-unavailable` remains a return-only process outcome: a failed append
cannot prove that an event was durable, so it never appears in this event.

After `RunLogWriter.start` succeeds, the guarded impact runner resolves and
appends one preflight before publication. A nonaccepted `mode-rejected` or
`final-rejected` preflight is followed by `preflight-rejected`; `changed-brief`
and `legacy-brief` are followed by their matching terminal outcome; every other
nonaccepted preflight is followed by `invalid`. An accepted preflight runs a
final snapshot recheck before publication; it can then return `changed-brief`,
`legacy-brief`, or `invalid`. Otherwise publication returns one of `completed`,
`storage-rejected`, `collision`, or `write-failed`. A successfully appended
terminal interruption can use `interrupted`.

A telemetry failure or interruption during the preflight or terminal-result
append returns a redacted process result, performs normal generic cleanup, and
adds no compensating event. Failure before publication blocks publication. If
the terminal result event is already durable, a later generic `run_end` cleanup
failure returns that durable result without another cleanup append. Otherwise,
failure or interruption after immutable publication leaves the final untouched:
telemetry observes durability but never grants authority over it, and a later
exact retry can report `reused`.

## Decision telemetry log (`<repo-root>/.plan-tool/telemetry/decisions.jsonl`)

Append-only JSONL, one `DecisionEvent` per line — a passive record of heuristic
decisions plus a bounded explicit decomposition-decision record. Gitignored and
local. The append primitive is best-effort: observational callers ignore a
write failure, while `plan-tool decide` checks its acknowledgement and reports
failure rather than claiming a durable explicit decision. `plan-tool telemetry`
resolves outcomes from this log plus existing run/report evidence without
mutating it.

`plan-tool telemetry` also computes an advisory finding-drift calibration at
read time from the existing saved review/report sidecars, including later
`run-reconcile` outcomes. It is not a `DecisionEvent` variant and creates no
calibration sidecar or cache. `telemetry_analysis.analyze_telemetry` combines
that read-only result with decision telemetry; `classify_calibration_recommendation`,
`analysis_to_dict`, and `render_analysis` expose its stable class key and
operator output. The calibration does not mutate plans, configuration, or live
convergence gates; a future impact-only demote may consume the advisory evidence
under its own scope.

Each append holds a cross-process advisory lock on the sibling
`decisions.jsonl.lock` file (`flock` on POSIX, byte-range locking on Windows),
retries short writes, and rolls a partial row back before releasing the lock.
The lock file is local, gitignored, and contains no telemetry data.

### `DecisionEvent` (`telemetry.py`)

| field | description |
|---|---|
| `schema_version` | event-shape version int (currently **`3` = `TELEMETRY_SCHEMA_VERSION`**); the reader tolerates schema-v1/v2 lines |
| `ts` | ISO-8601 UTC timestamp |
| `kind` | decision family — `"granularity"` \| `"audit-coverage"` \| `"convergence"` \| `"plan-criteria-breakdown"` \| `"prompt-budget"` \| `"backend-pattern-miss"` \| `"drift-gate"` \| `"apply-verdict"` \| `"escalate-split"` \| `"step-provenance"` \| `"decomposition-decision"` (extensible) |
| `decision` | the specific call within the kind (e.g. `"assessed"` / `"passes"` / `"diagnosed"`) |
| `plan_slug` | plan slug the decision was about (`""` if unresolved) |
| `context` | open per-`kind` bag of the inputs that drove it (counts, sizes, pass budget, verdict, …) — the raw material a later aggregation tunes against |
| `decision_id` | stable content hash minted in `record_decision` — `sha256` over `(schema_version, kind, decision, plan_slug, plan_fingerprint, step_id, ts)`, truncated to 16 hex chars; the outcome-resolver join handle. **Not globally unique** (see note below) |
| `run_id` | the run that observed the decision, read from a telemetry-owned `ContextVar` set at the run boundary; `""` when no run is active |
| `plan_fingerprint` | caller-supplied plan digest (see `compute_plan_fingerprint`); `""` when absent. A base-event join key — distinct from any `context.plan_fingerprint` a wrapper also writes |
| `code_fingerprint` | equality-only code-state identity: a full 64-character lowercase SHA-256 digest; `""` when unavailable |
| `anchor` | caller-supplied decision target; `decomposition-decision` uses `"plan"` or `"step:<id>"`, while finding-oriented producers may use an `[anchor-slug]`; `""` when absent |

`decision_id` is a stable handle to a *class* of content-identical decisions, not
a per-row key: `context` is deliberately out of the hash, so genuinely-distinct
same-family decisions that share a second-precision `ts` (e.g. two
`record_granularity` calls with different `split`/`merge`) collide by design.
Since `ts`/`plan_slug`/`plan_fingerprint` are already hash inputs, colliding rows
share them, so only `context` distinguishes them — a resolver treats `decision_id`
as non-unique and falls back to `context` (or log position) when it must pick a
single row. No line-ordinal tiebreaker is added: that would force
`record_decision` to read the append-only log and break its stdlib-only,
best-effort leaf shape.

`step_id` normalization: telemetry stores step ids as `str` (in `context` and,
for `record_decision`, folded into the `decision_id` hash), whereas sidecars and
`Recommendation`s carry them as `int`. The phase-3 outcome resolver casts across
that boundary.

#### Backend pattern misses

`kind="backend-pattern-miss"` and `decision="plan-quota-candidate"` record a
Cursor error that did not classify as a terminal plan quota but has multiple
monthly-plan-quota landmarks while failing the confirmed exact banner pattern.
Its local-only `context` records `backend`, `classified_as`, `markers`, `phase`,
and a whitespace-normalized, secret-redacted `excerpt` around the first
landmark. The record is observational: it never changes recovery behavior. A
future pattern update uses observed excerpts to extend the matcher without
widening it from hypothetical wording alone.

Telemetry derives `code_fingerprint` without reading code again. Its SHA-256
input is UTF-8 compact JSON (`ensure_ascii=False`, separators `,` and `:`) of
`["plan-tool-code-fingerprint-v1", pairs]`, where `pairs` is a list of
`[path, hash]` pairs sorted by path. Paths and hashes are opaque strings. A
computed empty map hashes through this framing to a stable non-empty digest;
`""` means unavailable. The reader preserves stored digest strings, normalizes
non-empty schema-v2 maps with this rule, and maps schema-v1 missing fields and
schema-v2 `{}` to `""` because legacy rows did not carry a presence marker.

#### Explicit decomposition decisions

`plan-tool decide <name> --outcome OUTCOME --anchor ANCHOR --rationale TEXT`
is the sole producer of `kind="decomposition-decision"` and
`decision="recorded"`. It records an explicit operator/session conclusion; it
does not infer one from findings, history, source diffs, or conversation text.
`anchor` is exactly `"plan"` or `"step:<id>"` for an existing plan step, and
`outcome` is one of `"single"`, `"split"`, `"scope-out"`, `"reframe"`,
`"withdraw"`, or `"defer"`. The open `context` bag has exactly these producer
keys:

| key | description |
|---|---|
| `outcome` | the closed-vocabulary explicit decomposition conclusion |
| `rationale` | the non-empty operator/session rationale, trimmed before write |

The command validates the plan and anchor before attempting the append. A
failed append returns a non-success command result and prints no durable-record
success message. It never mutates the plan, creates a telemetry analysis, or
causes a split, scope-out, re-seed, or withdrawal action.

#### Create granularity decisions

Create-time granularity telemetry uses `kind="granularity"` with two decision
values:

- `decision="create-review"` records one assessment of the candidate step list
  during the change-type review pass.
- `decision="create-step-outcome"` records each reviewed step answer and each
  split attempt outcome.

`plan_slug` stays on the top-level `DecisionEvent`. Every review pass mints a
fresh, opaque, non-empty `assessment_id`: the `create-review` parent and all of
its interactive `create-step-outcome` children store that same value in
`context`. The parent row is attempted first, and outcomes are emitted only
after the complete newline-terminated parent row is successfully appended. A
failed or partially written parent append is acknowledged as unsuccessful,
rolled back, and suppresses every child for that pass; telemetry failure never
changes the review itself.

`create-review` context keys:

| key | description |
|---|---|
| `stage` | always `"create"` |
| `assessment_id` | fresh per-pass association that identifies this one observed `create-review` occurrence and joins its outcomes |
| `steps` | number of candidate steps in the reviewed list |
| `candidate_fingerprint` | stable digest of the candidate step list, used with `plan_slug` to collapse repeated observations of the same candidate list |
| `file_footprint` | count of distinct declared paths across each step's full footprint (`files` plus `creates`) |
| `split` | number of `granularity-split` recommendations |
| `split_steps` | number of distinct candidate steps that carried at least one split recommendation |
| `merge` | number of `granularity-merge` recommendations |
| `split_step_ids` | deduplicated split-bearing step ids, stored as strings in candidate order |
| `predicate_counts` | counts grouped by deterministic create-stage predicate key: `mixed-verbs`, `two-clauses`, and `multi-area`; `mixed-step` is reserved for prose/detail-stage helper recovery and is not emitted by the create-review deterministic count |
| `can_split` | whether a split invoker was wired and split was mechanically available |
| `mode` | review mode: `interactive`, `yes`, `non_tty`, or `checkpoint` |

`mode="checkpoint"` marks a resume observation. Aggregation should exclude it
from "fresh signal fired" counts and should dedupe equivalent candidate-list
observations by `plan_slug` plus `candidate_fingerprint`.

The two create identities have different ownership and meaning.
`assessment_id` joins exactly one observed review occurrence to its outcomes;
`candidate_fingerprint` groups repeated observations of equivalent candidate
lists. `DecisionEvent.decision_id` is not a substitute: it remains a non-unique
class identity whose hash omits `context`. Likewise, `plan_slug` plus `ts` can
collide, and `run_id` is normally empty during authoring. The review event alone
owns the compact top-level `code_fingerprint`; associated outcome rows keep its
empty sentinel and carry the smaller `assessment_id` instead.

`create-step-outcome` context keys:

| key | description |
|---|---|
| `assessment_id` | association copied from the successfully appended `create-review` parent for this pass |
| `step_id` | candidate step id, stored as a string |
| `had_split_hint` | whether a split hint was surfaced for the step in the review UI |
| `proposed_change_type` | proposed `ChangeType` value, or `null` when unclassified |
| `resolved_change_type` | final `ChangeType` value after the answer, or `null` |
| `action` | one of `accept`, `override`, `unclassified-accepted`, `unclassified-classified`, `split-requested`, `split-applied`, `split-unusable`, `split-invalid`, or `split-error` |
| `before_steps` | step count before a successful split attempt; omitted when absent |
| `after_steps` | step count after a successful split attempt; omitted when absent |
| `error_class` | exception class for deterministic split rejection or proposal-time failure; omitted when absent |

`accept` means the resolved change type equals the proposed change type.
`override` is only for a step with a proposed value that the operator changed to
a different concrete value. First-time classification of an unproposed step is
`unclassified-classified`, and accepting an unproposed step as still unknown is
`unclassified-accepted`. Split-only fields are omitted when absent; absence is
not a zero value.

Legacy create rows remain readable when `context.assessment_id` is absent, and
legacy outcomes retain their action-based inline resolution. They cannot be
linked unambiguously to one historical assessment occurrence, so readers do not
fabricate or backfill an association.

Reconcile-lane granularity telemetry adds one more decision value under
`kind="granularity"`:

- `decision="code-reveals-split"` records one reconcile-lane fire of the
  low-confidence code-reveals-a-split detector (`review.py`), so its fire — and
  eventual acted-on / false-positive — rate is measurable from telemetry rather
  than a manual study (BACKLOG #117).

`code-reveals-split` context keys:

| key | description |
|---|---|
| `stage` | always `"reconcile"` |
| `steps` | number of steps in the plan |
| `fired` | number of steps the detector flagged this pass |
| `step_ids` | the flagged step ids, stored as strings (stable across passes, so a later outcome pass can check whether the step was actually split) |

#### Plan split-criteria breakdown

`kind="plan-criteria-breakdown"` records one per-plan split-criteria evaluation,
with `decision="evaluated"`. Each event is tagged with a plan fingerprint so
decomposition drift is detectable: for a fixed `plan_slug`, a changed
`plan_fingerprint` paired with a changed criteria result-set is drift.

Context keys:

| key | description |
|---|---|
| `plan_fingerprint` | caller-supplied plan digest (see `compute_plan_fingerprint`); always present |
| `criteria` | per-criterion rows, each `id` (str), `fired` (bool), `severity` (str or `null`), `step_ids` (list of str) |
| `criteria_count` | number of criteria evaluated (`len(criteria)`) |
| `fired_count` | number of criteria that fired |

As of phase 1 `plan_fingerprint` is **dual-homed**: this wrapper forwards it to the
base `DecisionEvent.plan_fingerprint` field (base-event table above) *and* keeps the
`context` copy documented here, so the in-repo drift consumer (`split_criteria.py`)
keeps reading it from `context` — it is a short digest, so the duplicate is cheap.
`code_fingerprint` is **base-homed only** (`DecisionEvent.code_fingerprint`, `""`
when unavailable): it is not copied into `context`. Full maps remain in grounding
and saved-review artifacts, while telemetry retains only their compact identity.
Phase 2 drops the `plan_fingerprint` `context` copy too and migrates the consumer
to the base field.

#### Prompt-budget advisory

`kind="prompt-budget"` records one pre-send prompt-budget check verdict, with
`decision="estimated"`. Each event captures where the check ran (`phase`), the
prompt's measured size, and the advisory level, so the `warn`/`high` thresholds
can be retuned from the recorded distribution rather than single-session
anecdote.

Context keys:

| key | description |
|---|---|
| `phase` | assembly point the check ran at (e.g. `"detail"`, `"create-steps"`, `"run-step"`, `"shell-backstop"`); always present |
| `total_bytes` | measured byte count of the assembled prompt; always present |
| `advisory` | advisory level string — `"ok"` \| `"warn"` \| `"high"` (the `PromptBudget.level`); always present |
| `estimated_tokens` | caller-projected token estimate; omitted when absent |
| `context_window` | model context window used for the headroom check; omitted when absent |
| `headroom_ratio` | estimated fraction of the context window the prompt consumes; omitted when absent |
| `blocks` | per-block breakdown as an ordered list of `[name, bytes]` pairs; omitted when absent or empty |

`context_window` is the window the check used, from one of four sources: a window the Claude CLI
reported exactly, the smallest window of a mixed Claude result (a lower bound that can be a helper
model's), Codex's usable share (`context_window` × `effective_context_window_percent`), or the
200,000 fallback when none was known. The record deliberately does not say which (the summary
printed to the operator marks only the fallback, with `(default)`), so a distribution of
`context_window` mixes the four.

The three tuning primitives (`estimated_tokens` / `context_window` /
`headroom_ratio`) and `blocks` are omitted when their argument is `None` —
absence means "not recorded", not zero.

#### Reconcile drift-gate

`kind="drift-gate"` records one verdict of the reconcile/`--refresh` drift-gate
(`refresh.py:refresh_plan`), with `decision="gated"`. Each refresh emits exactly
one event so a later aggregation can see how often the gate clears clean vs
reconciles, how many files drift, and how many findings a drift produces.

Context keys:

| key | description |
|---|---|
| `verdict` | one of `"no-baseline"` \| `"no-drift"` \| `"drifted"`; always present |
| `drifted_files` | count of drifted files the reconcile was scoped to (`0` on `no-drift`) |
| `findings` | count of findings the reconcile surfaced (`0` on `no-drift`) |

The `code_fingerprint` digest is carried on **every** verdict (it is derived from
the already-computed code axis the gate diffs on). `plan_fingerprint` is carried on
`no-baseline`/`drifted` only and is `""` on the hot `no-drift` path — that path is
a byte-identical no-op, so the extra plan-file read `compute_plan_fingerprint`
does is skipped. `no-baseline` covers both a genuine first stamp and a corrupt or
unreadable sidecar (`read_grounding` returns `None` for both); the literal stays
accurate — no readable baseline existed either way.

#### Apply verdict

`kind="apply-verdict"` records the selected per-finding apply verdict with
`decision="recorded"`. Authoritative serial callers record at the
`launcher.py:apply_finding` boundary by default. Interactive review defers a
successful verdict until the operator keeps a non-empty edit, but records an
observed `INVOCATION-FAILED` before returning through its failure path.
`completeness-apply --jobs N`
suppresses every isolated worker write and makes canonical
`completeness_apply_parallel.py:replay_results` the sole durable owner.

Context keys:

| key | description |
|---|---|
| `verdict` | the apply token — `"APPLIED"` \| `"NOT-APPLICABLE"` \| `"BLOCKED"` \| `"BLOCKED-STRUCTURAL"` \| `"UNKNOWN"` \| `"INVOCATION-FAILED"`; always present |
| `step_id` | the resolved step id (also folded into the `decision_id` hash); omitted when no step resolved |

The finding's `anchor` rides the **base event** (a first-class join key), not
`context` — it is coerced to `""` when falsy, so an anchorless finding
(`Recommendation.anchor is None`) stores `""`, never the string `"None"`.
`plan_fingerprint` is the caller-hoisted base-event digest (computed once before
the apply loop, not re-read per finding); **no `code_fingerprint` map** is carried
at this per-finding site (dozens of lines each carrying a large map would be
wasteful volume).

Parallel replay uses only canonical join keys: canonical repository and plan
slug, the launcher's resolved step id, the finding anchor (or `""`), the active
command run id, and the fingerprint of the plan state the selected apply
evaluated. Non-conflicting workers share the one pre-dispatch fingerprint. A
conflict discards the stale worker outcome and recomputes the fingerprint before
the fresh canonical rerun; only that rerun can be recorded.

Canonical replay makes at most one best-effort append attempt for an accepted,
recordable result. A swallowed recorder failure can therefore leave zero rows;
delivery is not exactly-once. Pre-skipped findings, setup and pre-invocation
parse failures, `APPLIED` with an empty landed diff, and edits rejected and
restored by the parse gate emit no event. Annotation persistence and telemetry
remain independent best-effort actions.

`UNKNOWN` means an accepted exit-`0` response emitted no recognized verdict token
(a response-contract violation). `INVOCATION-FAILED` means a primary or auto-fix
follow-up invocation returned non-zero or raised before providing a usable
response. A zero-exit response stays on the ordinary parsed-verdict path even
when its backend stats self-report `is_error`; telemetry follows the response
the host accepted. `dry_run` performs no invocation and records nothing. Failure
rows use the same plan slug, step id, anchor, plan fingerprint, and ambient
`run_id`; detailed exit and exception data remains in the run-log.
Deferred workers transport this failure token and the resolved step even when
the invocation raises. The launcher first restores every tracked file and marks
the transported outcome with restoration safety; incomplete restoration
propagates as a batch abort and is never selected for replay.

#### Escalate-to-split outcome

`kind="escalate-split"` records one disposition of the escalate-to-split bridge
(`launcher.py:escalate_to_split`) — emitted exactly once per completed call,
carrying that call's final `EscalateResult.outcome` — with `decision="resolved"`.
One event fires per call, so a later aggregation sees how often the split bridge
actually mutates a plan versus recommends versus can't act, per plan and per step.

Context keys:

| key | description |
|---|---|
| `outcome` | the `EscalateResult.outcome` — `"applied"` \| `"recommended"` \| `"unsafe"` \| `"proposal-unusable"` \| `"step-missing"`; always present |
| `allow_split` | whether the caller permitted the mutation; always present |
| `step_id` | the target step id (also folded into the `decision_id` hash); always present |
| `blocking` | the downstream ids blocking the split, as strings; omitted unless the outcome is `"unsafe"` |

`plan_fingerprint` is the caller-hoisted base-event digest, snapshotted **before**
an `applied` path's `write_plan` so the event captures the plan the bridge
observed and acted on, not the post-split file; the caller-side compute is guarded
so a fingerprint failure degrades to `""` rather than perturbing the bridge. **No
`code_fingerprint` map** is carried — escalate is a plan structure/safety
decision, not a code-footprint one.

#### Step-provenance (#238)

`kind="step-provenance"` records the titles of the step(s) one structural-split
mutation just created, with `decision="created"` — emitted best-effort by both
tool-mediated step-creation paths (`detail.py:split_step`, used by
`plan-tool split`; and
`launcher.py:escalate_to_split`'s `applied` outcome). Read back by
`telemetry.read_step_provenance_titles` and, through it, by
`completeness_report.compute_plan_mass`'s `audit_induced_growth` ratio.

Context keys:

| key | description |
|---|---|
| `new_step_titles` | list of the freshly-inserted steps' titles (never the surviving original's); always present and non-empty — the recorder no-ops rather than writing an empty list |
| `mechanism` | `"split"` \| `"escalate-split"` — which actuator created them |

Keyed on **title**, not step id: a split renumbers every downstream step
(`create._apply_step_split`'s contiguous-`1..N` invariant), so an id recorded at
one split can point at a different step after a later one — titles survive
renumbering, and `split_step` already requires them unique within one split. A
step added by hand-editing the plan file is not observable through this path and
is never counted; a step created by a split and later retitled by hand goes
stale the same way every provenance signal in this tool does under a hand edit.


### Roadmap seed publication layout

The version-1 seed-state entry optionally carries `publication_layout`, a closed
`root` / `nested` string. Absence reads as `root` for existing publications;
new promotions record `nested`. Normalization and state rewrites preserve this
field. See ROADMAP_FORMAT.md for destination and ownership semantics.
