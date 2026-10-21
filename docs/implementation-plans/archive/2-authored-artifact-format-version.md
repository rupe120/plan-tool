> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Authored Artifact Format Version
intent: A plan file and a run-grade detail file each declare their format version
  in-band, and each reader refuses an unsupported declared version with a named, actionable
  result instead of a generic parse error.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/authored-artifact-format-version.md
steps:
- id: 1
  title: Accept the fixed plan format_version field, reject an unsupported value before
    Plan.model_validate with `UnsupportedPlanFormatVersionError`, and distinguish
    it from annotate rough notes
  intent: An older plan-tool tells an operator that a plan is a newer format instead
    of reporting an unknown-field typo and directs them to a build that supports the
    declared version, while every current plan-reading command retains its established
    malformed-plan handling. `annotate` catches that named `ValidationError` subtype
    before its ordinary parse fallback, turns it into its named source failure, and
    does not silently reclassify it as ordinary notes.
  files:
  - plan_tool/parser.py
  - plan_tool/schema.py
  - plan_tool/annotate.py
  - plan_tool/cli/annotate_cmd.py
  - plan_tool/cli/inspect.py
  - plan_tool/cli/app.py
  - RUNBOOK.md
  - docs/cli/validate.md
  - tests/test_parser.py
  - tests/test_annotate.py
  - tests/cli/test_annotate_cmd.py
  - tests/cli/test_inspect_cmds.py
  - tests/cli/test_app.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/authored-artifact-format-version/01-accept-fixed-plan-format-version-field.md
  status: done
- id: 2
  title: Stamp the plan format version in both eligible plan serializers (write_plan
    and render_plan_text), keeping write_plan's whole-file overwrite, byte-preserved
    body, and compare-and-swap guard unchanged
  intent: Every fresh or current-version plan this build writes carries its format
    declaration, so a future reader has something to recognize. A serializer refuses
    an effective older version until its explicit raw upgrade runs; the two serializers
    and the plan-format reference ship that bootstrap and refusal contract together.
  files:
  - plan_tool/parser.py
  - PLAN_FORMAT.md
  - tests/test_parser.py
  - tests/test_concept_sync.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Ships the supported-version constant and the reader that accepts a declared
      version, so nothing is stamped before a shipped reader understands it.
  detail: docs/implementation-plans/plan-details/authored-artifact-format-version/02-stamp-plan-format-version-both-eligible.md
  status: done
- id: 3
  title: Add the fixed run-grade detail body marker and shared parser to detail_artifacts.py,
    then route every semantic run-grade detail read and apply boundary through its
    refusal
  intent: A detail file gets somewhere to declare its format version without gaining
    YAML frontmatter, and every command that interprets its run-grade body refuses
    a version it cannot honor before using that body or recording a partial apply
    result.
  files:
  - plan_tool/detail_artifacts.py
  - plan_tool/renderer.py
  - plan_tool/review.py
  - plan_tool/launcher.py
  - plan_tool/detail.py
  - plan_tool/scope_out.py
  - plan_tool/annotate.py
  - plan_tool/completeness_report.py
  - plan_tool/cli/reconcile.py
  - plan_tool/jira.py
  - plan_tool/gates.py
  - plan_tool/split_criteria.py
  - plan_tool/cli/gates_cmd.py
  - plan_tool/cli/split_criteria_cmd.py
  - plan_tool/cli/inspect.py
  - plan_tool/cli/app.py
  - plan_tool/cli/authoring.py
  - plan_tool/cli/completeness_apply_parallel.py
  - plan_tool/auto_reconcile.py
  - plan_tool/review_walk.py
  - tests/test_detail_artifacts.py
  - tests/test_renderer.py
  - tests/test_review.py
  - tests/test_launcher.py
  - tests/test_detail.py
  - tests/test_scope_out.py
  - tests/test_annotate.py
  - tests/test_completeness_report.py
  - tests/cli/test_reconcile_engine.py
  - tests/test_jira.py
  - tests/test_gates.py
  - tests/test_split_criteria.py
  - tests/test_auto_reconcile.py
  - tests/cli/test_inspect_cmds.py
  - tests/cli/test_review_actions.py
  - tests/cli/test_completeness_apply_parallel.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_app.py
  - tests/cli/test_authoring_cmds.py
  - tests/test_review_walk.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Owns the plan-format `validate` refusal and the older-build operator direction;
      this step extends only the already-established `validate` branch for details.
  detail: docs/implementation-plans/plan-details/authored-artifact-format-version/03-fixed-run-grade-detail-body-marker.md
  status: done
- id: 4
  title: Make detail.py the sole authority for the current run-grade detail marker,
    keeping the archive-then-overwrite of a prior detail file unchanged
  intent: Every run-grade detail file this build authors carries its format declaration,
    so the reader gate has something to read. After a model response, the detail writer
    replaces any proposed marker in the fixed post-H1 slot with its current marker;
    the main prompt and `detail.py:_REPROMPT_SUFFIX` reserve that slot but do not
    author a version, and the format reference describes the resulting marker and
    its unsupported-version refusal before `Summary`. The direct CLI recovery route
    supplies a distinct recovery-only signal; forced review regeneration and merge
    retain their normal prompt context.
  files:
  - plan_tool/detail.py
  - plan_tool/cli/authoring.py
  - plan_tool/sweep.py
  - plan_tool/create.py
  - DETAIL_FORMAT.md
  - docs/cli/detail.md
  - plan_tool/prompts/detail.md
  - tests/test_detail.py
  - tests/test_sweep.py
  - tests/test_create.py
  - tests/cli/test_authoring_cmds.py
  - tests/cli/test_review_actions.py
  complexity: low
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Owns the marker's spelling and its parser, so the writer stamps exactly what
      the reader accepts rather than restating the recipe.
  detail: docs/implementation-plans/plan-details/authored-artifact-format-version/04-make-detail-py-sole-authority-current.md
  status: done
- id: 5
  title: Register the two authored-artifact version constants through a version-only
    data-contract record and add their class-specific evolution, writer-eligibility,
    support-window, and retirement rules to DATA_CONTRACT.md
  intent: The authored-artifact layer has documented class-specific version evolution
    without pretending that either artifact has a persisted dataclass or JSON-object
    schema — strict plan fields break while an ignored optional detail section does
    not. A later constant change, class rule, support window, writer eligibility,
    or retirement rule cannot drift away from the doc silently.
  files:
  - plan_tool/data_contract.py
  - DATA_CONTRACT.md
  - tests/test_data_contract.py
  allowed_mentions:
  - tests/cli/test_data_contract_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 3
  depends_on_notes:
    1: Defines the plan class's supported-version constant the version-only record
      names.
    3: Defines the run-grade detail supported-version constant the version-only record
      names.
  detail: docs/implementation-plans/plan-details/authored-artifact-format-version/05-register-two-authored-artifact-version.md
  status: done
- id: 6
  title: Give each artifact class an explicit raw-artifact upgrade entry point, and
    a coverage test over plan absence or detail valid-carrier absence plus every supported
    version
  intent: The always-upgradable raw-state obligation is held by a failing test rather
    than prose. The writer authors current-format artifacts directly; the explicit
    upgrader carries an existing raw absent plan or valid-carrier detail to version
    1 and is exercised by the coverage test. A raw detail body without a valid carrier
    H1 has no carrier slot, so its upgrader refuses it rather than synthesizing an
    H1 or marker and its declared path is forced re-authoring.
  files:
  - plan_tool/parser.py
  - plan_tool/detail_artifacts.py
  - DATA_CONTRACT.md
  - tests/test_parser.py
  - tests/test_detail_artifacts.py
  - tests/test_duplication.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 4
  depends_on_notes:
    2: Ships the plan carrier and current writer, so the explicit absent-to-1 upgrader
      has a defined target shape.
    4: Ships the detail carrier and current writer, for the same reason.
  detail: docs/implementation-plans/plan-details/authored-artifact-format-version/06-give-each-artifact-class-explicit-raw.md
  status: done
- id: 7
  title: 'Delete BACKLOG.md #356, preserve the bounded authored-artifact follow-ups,
    and update CLAUDE.md''s format-doc bullets to name the version declaration'
  intent: 'The backlog stops advertising work that has shipped, and the per-session
    reference bullets describe the contracts as they now stand. The roadmap staged-artifact
    class was carved into BACKLOG #362 before this plan started and stays tracked
    there, not reopened here; #362 and the planning lanes are restated so no shipped-work
    or deleted-entry reference remains, while the three bounded follow-ups filed during
    this plan''s restructuring remain independent backlog records.'
  files:
  - BACKLOG.md
  - CLAUDE.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 4
  - 5
  - 6
  depends_on_notes:
    2: Ships the plan class end to end, so the entry's plan half is genuinely discharged.
    4: Ships the run-grade detail class end to end.
    5: Ships the registry and doc obligation the entry's scope contract names.
    6: Ships the upgrade obligation, without which the entry's always-upgradable requirement
      is undischarged.
  detail: docs/implementation-plans/plan-details/authored-artifact-format-version/07-delete-backlog-md-356-update-claude-md.md
  status: done
---
# Authored Artifact Format Version

## Overview

Every record `plan-tool` persists declares a schema version: review sidecars
(`review_persistence.SCHEMA_VERSION`), telemetry, grounding, the project
profile, the purity cache, checkpoints, the run log, roadmap evidence, and the
roadmap version store each carry one. Every artifact
`plan-tool` authors carries none. This effort closes that asymmetry for two
authored classes — the plan and the run-grade detail file — and stops there:
it ships version 1 and the refusal, and no second version of anything.

The four roadmap staged artifacts are a third authored class with the same
hole. They are carved out of this effort into `BACKLOG.md` #362, deferred (see
[Out of scope](#out-of-scope)). Stamping a version declaration into a staged
artifact changes its bytes, and the accepted-head roadmap-version store binds
each enrolled roadmap to exact digests of those bytes
(`roadmap_versions.py:_require_content_matches_record`); a declaration-only
change there would break every roadmap already enrolled. Settling that
interaction, and its relationship to the unrelated existing
`CanonicalSourceIdentity.format_version` field, is #362's problem, not this
effort's.

`DATA_CONTRACT.md` § "Version-evolution policy" already governs how a durable
version must behave — readers fail closed and never guess a version. This
effort records the two authored-artifact version constants under that policy
while `PLAN_FORMAT.md` and `DETAIL_FORMAT.md` retain ownership of their
respective schemas.

The deliberate operator-visible widenings beyond the seed's original
no-other-delta boundary are bounded to two outcomes: `validate` now exits 1
for a named plan or detail format refusal even without `--fail-on-findings`,
and an H2-first or indented-H1 detail-authoring response consumes an existing
retry rather than being accepted and written. Step 1 owns the command help,
generated CLI reference, and malformed-frontmatter runbook text for the
`validate` distinction; step 4 owns the authoring retry rule. Ordinary
schema-invalid input remains exit-0 unless the flag requests CI gating.

## Problem statement

`Plan` sets `extra="forbid"` (`schema.py:208`), and `PLAN_FORMAT.md`
validation rule 8 rejects any unknown frontmatter key. A plan written by a
newer `plan-tool` is therefore a hard parse rejection by an older one,
surfaced as an unknown-field typo, with nothing in the artifact saying the
format moved. The rejection is correct and the diagnosis is wrong, and no
amount of care in a future format change can fix that from the newer side —
the older reader has to be able to recognize a version it does not support.

The detail class has the same hole in a different shape: a detail file is
pure markdown with no frontmatter at all (`DETAIL_FORMAT.md` § Format), so it
has nowhere to put a version today.

## Architecture

The following plan-level contracts are settled here; their implementation
mechanics belong to `detail`.

**The carriers are fixed.** A plan's declaration is the top-level frontmatter
key `format_version`. A run-grade detail declaration is exactly
`<!-- plan-tool:detail-format-version: N -->`, the first non-blank line after
the document's first non-blank line, which must be an H1; `## Summary` is the
next H2. The H1 begins in column 0 and matches
the `locate_detail_format_carrier` helper in `detail_artifacts.py`; leading
blank lines before it do not alter the slot. A body with a non-blank preamble before an H1 has no
carrier, so marker-shaped text in it is ordinary prose. Only that fixed post-H1
line carries the declaration. Both the spelling and placement remain fixed for
the life of their format; a later version may change other structure but must
leave the carrier where an older reader looks.

**The gate runs before strict validation.** A version read that happens inside
`Plan.model_validate` is inert: a newer plan's other new keys raise
unknown-field errors first and the version is never reached. The plan gate
reads the declaration from the already-parsed `raw` mapping in
`parse_plan_text` and refuses an unsupported value before validation runs.
`Plan` also declares the supported `format_version` field with its current
default, so a supported declaration reaches strict validation without relaxing
`extra="forbid"`. The same ordering holds per class — recognize the version,
then apply the shape contract.

**An unsupported plan directs the operator to a supporting build.** The plan
class has no safe in-build recovery: an older binary cannot interpret or
upgrade a newer plan. Step 1 therefore owns a typed `main()` boundary for
`UnsupportedPlanFormatVersionError`; it preserves the named declared-and-
supported diagnosis, exits 1, and points to a `plan-tool` build that supports
the declared version. Its ordinary parse/schema fallback keeps its existing
`validate`/`list` suggestions. Step 3 owns only the detail-format `validate`
arm and its direct forced-regeneration recovery route.

**Absent means version 1, by an explicit default at each gate.** The
mechanism is the default applied in the two gates; they own it; and the
reader gates land before any writer stamps a declaration, so no artifact ever
carries a version that no shipped reader understands. This is what keeps every
existing artifact parsing unchanged. The plan parser assigns effective version
1 from a missing raw key even after a later build's `Plan` field default changes
to its new current version. A reader's effective-version default does not erase
the raw state: the explicit upgrade entry points receive an unparsed frontmatter
mapping or detail body, distinguish a missing carrier from a declared version 1,
and return the upgraded raw counterpart.

**The detail carrier is a body marker, not frontmatter.** Giving detail files
YAML frontmatter would break `DETAIL_FORMAT.md`'s pure-markdown contract and
every body parser keyed on `detail.py:_REQUIRED_H2_TOKENS`. The precedent for
a machine-read marker inside a markdown body is
`roadmap_seed_state.py:render_seed_state_marker` and its parser at
`roadmap_seed_state.py:33-36`. The fixed comment after the H1 preserves the
required-first-H1 rule; the detail prompt and format reference restate that
`Summary` follows the marker, while the existing section parser stays unchanged.

**The detail writer, not the model, owns the marker value.** After it receives
a drafted body, `detail.py` normalizes the one fixed post-H1 carrier slot: it
removes or replaces a model-proposed marker there and writes the build's current
marker exactly once. The prompt reserves that position in the response shape but
does not declare a version. Marker-shaped prose outside that slot stays untouched
as prose, so a model cannot cause a self-refusing detail file by proposing a
future value. `detail.py:_REPROMPT_SUFFIX` states the same H1-then-marker-then-
`Summary` sequence when it asks a failed response to retry.

An on-disk body without a valid carrier H1 has no marker slot, so the reader
resolves it as absent legacy version 1 and applies the same support-window check.
That does not make it acceptable authoring output.
Before the writer can stamp, `parse_detail_response` strips any response preamble
and requires its first heading to be an H1; an H2-first response consumes an
existing retry attempt and is never written.

**Each semantic detail reader shares the same gate.**
`detail_artifacts.py` owns the marker parser and the unsupported-version
error. Every consumer that interprets a run-grade body routes through it:
run prompt assembly, review and audit prompt construction, deep reconcile,
semantic detail regeneration, quality, merge, and sibling-reference reads,
scope-out, annotation grounding, completeness-report mass reads, `validate`'s
pointer-backed suppression scan, pre-mutation apply surfaces, the selected
run-reconcile preflight, drift-halt auto-reconcile, Jira export, gate suggestion,
and split criteria. `granularity.py` is a downstream evaluator: it receives
already-gated `detail_bodies` only from `split_criteria.py`. `detail.py`
passes its in-flight model responses and freshly drafted candidate bodies to
`parse_mixed_step_findings`, not an on-disk artifact; its separate semantic
on-disk reads still gate. Byte-only consumers such as fingerprints and persisted
path metadata keep hashing or naming files without interpreting their body and
do not gate. `bench.py` re-reads only the same-invocation detail body
that the current writer has just stamped, to score its H2s and acceptance bullets;
that post-write verification is not an independent artifact-input boundary and
stays ungated. Lesson distillation has the same single-invocation, post-write
shape and stays ungated too; neither reader consumes an externally supplied
run-grade artifact.

**A best-effort or apply handler cannot erase a format refusal.** A handler
above a semantic reader may keep its existing fallback for ordinary failures,
but it must re-raise `DetailFormatError`: `detail.py:_format_already_implemented_block`,
`detail.py:collect_step_grounding_findings`, `review.py`'s audit-budget
estimator around `render_plan_audit_prompt`,
`completeness_report.py:compute_plan_mass_best_effort`,
`plan_tool/launcher.py:_compute_findings_delta`,
`plan_tool/cli/authoring.py:_run_completeness_tail`, the guarded worker in
`cli/completeness_apply_parallel.py`, and each action handler in `review_walk.py`.
The tail keeps its ordinary audit warning, while the parallel dispatcher and
interactive walk retain ordinary per-item continuation only for non-format
failures. A format refusal reaches the parent command before any sibling result
is recorded. These are error boundaries above the reader gates, not named
carve-outs; swallowing one would silently degrade a prompt, report, or apply
transaction, which the fail-closed contract forbids.

**Refusal has an existing command outcome for each class.** The plan reader's
named unsupported-version error is `UnsupportedPlanFormatVersionError`, a
`ValidationError` subtype, so list, validate, sweep, detail, and the other
existing plan consumers retain their current malformed-plan outcome. `annotate`,
which also accepts non-plan rough notes, catches that subtype before its broad
plan-or-notes fallback and converts it to an `AnnotateError` carrying the
declared-and-supported message. A single source writes neither annotation nor
carryover seed; a batch records the named per-source failure and continues
independent inputs. Ordinary malformed or non-plan input still follows the
rough-notes path. A detail reader propagates its named error to its command boundary;
`run` stops before invoking the backend and returns its existing command-error
outcome, while audit, reconcile, annotation, scope-out, and every `detail`
path that semantically reuses an existing body stop before using the unsupported
body. This is a new refusal reason for run-grade detail, not a new advisory,
secondary gate, or fallback body.

`detail_artifacts.py` exposes that reason as a named `DetailFormatError` whose
message includes the declared and supported versions. Command-local wrappers
preserve that message; `run` retains its `LauncherError` command result and
Jira its `JiraError` result. `plan_tool/cli/app.py` catches every otherwise-propagated
`DetailFormatError` before its unexpected-error handler, prints the same named
diagnosis and recovery direction, and returns exit 1, matching malformed plan
input. `validate` catches the refusal before it prints `OK:`, prints one
`INVALID:` verdict with the diagnosis, and returns exit 1 rather than treating
the condition as advisory. Step 1 owns the named plan-format path; step 3
extends the established branch only for the detail-format path and the
pre-`OK:` ordering. Ordinary schema-invalid plans retain `validate`'s existing
`--fail-on-findings` exit policy. Thus audit, reconcile, scope-out, annotation, and
semantic `detail` paths show the operator the format refusal without a crash
traceback. Apply surfaces fail before taking their edit snapshot or changing a
file. The drift-halt auto-reconcile path must re-raise a detail-format-caused
`LauncherError` instead of converting it to its ordinary per-step skip.

**Forced plain detail regeneration is the refused-detail recovery route.** It
does not interpret any pre-existing detail in the bundle: `plan-tool detail
<slug> --step N --force --recover-refused --commit --no-completeness` enters
an explicit recovery-only prompt mode,
archives the target's bytes, suppresses every prompt block that reads a
pre-existing bundle body — sibling details, the already-implemented heuristic,
and per-step deterministic grounding — and writes a fresh current-format body
in their place. `plan_tool/cli/authoring.py:cmd_detail` alone accepts the
explicit `--recover-refused` signal and requires it to accompany `--step N`,
`--force`, and `--no-completeness` before it calls `generate_detail`; it alone
passes `recovery_only=True`. The signal is distinct from `force=True`, which
`merge_steps` and
`cli/review_actions.py` also pass while retaining their prior-body, sibling, and
grounding context. The recovery route is deliberately one target at a time, so
only the serial prompt assembly is in scope; `--jobs` neither enables recovery
nor changes its behavior. Semantic reuse outside this route remains fail-closed
— ordinary forced re-authoring, merge inputs, purity reuse, and any other
detail path that consumes prior bodies gate them first. `--no-completeness` is a
recovery prerequisite, not the recovery signal: the normal tail stays
fail-closed, while recovery reauthors each refused target without re-reading
its refused siblings. Once every target is current, the operator runs a fresh
completeness audit over the repaired bundle. This works when every file in a
newer bundle is refused, not only when the target is the sole refused file.

Every unsupported-version message names the artifact's declared value and the
build's complete supported-version set. This stays meaningful when the window
contains both current and current-minus-one rather than only version 1.

`suggest-gates` and `split-criteria` are also command-boundary refusals: an
unsupported run-grade body stops the selected command before it emits a
recommendation or criterion report, with its existing non-zero command-error
outcome. They do not treat the refusal as a missing detail or silently omit
the body. Jira already uses its `JiraError` route for an invalid run-grade
body; it receives the same named format diagnosis there.

**Refusal is fail-closed at the semantic plan-operation boundary.** An
unsupported or malformed detail carrier stops every operation that interprets
that plan's detail bundle; there is no per-step fallback, partial report, or
best-effort omission for that error. Forced plain regeneration is the explicit
non-reading recovery exception above. The existing per-step best-effort behavior
remains for a missing or unreadable file only. `list` keeps its inventory role
and presents an unsupported plan as one malformed row. Batch `annotate` keeps
processing independent source paths, but reports an unsupported plan source as
a named per-source failure and writes no annotation or carryover seed for it.
The completeness mass wrapper catches only missing/unreadable I/O; it propagates
`DetailFormatError` to its command instead of dropping a body from a mass result.
The authoring auto-completeness tail also propagates a format refusal instead of
downgrading it to a warning on successful *ordinary* authoring. The explicit
recovery command skips that tail so it can replace one refused target at a time.

**The plan declaration must survive both serializer elisions.**
`parser.py:write_plan` and `render_plan_text` serialize via
`model_dump(exclude_defaults=True, exclude_none=True)`, so an optional field
whose value equals its model default is never written — adding a field with a
default would silently produce plans that declare nothing. Both serializers
first require the plan's effective version to be current, then inject the
current declaration into their serialized mapping after the model dump,
including the concept-sync publish path. At version 1, absent and current both
have effective version 1 and can stamp; once a later current version ships,
both a declared current-minus-one plan and a raw absent legacy plan have
effective version 1 and refuse until their explicit raw upgrade runs. Version 1
exposes that upgrade only as a library entry point exercised by its coverage
tests. The first release that makes a previously supported live on-disk plan or
detail representation reach either a reader or writer refusal ships an
operator-invocable route for the affected class in the same change, before it
raises the current version. An arbitrary future or malformed declaration still
directs the operator to a supporting build; it does not create an in-build
upgrade obligation. The written declaration is a property of an eligible
writer, not a by-product of the model default.

**Version evolution is class-specific, and reading never upgrades.** A plan
frontmatter or step key is a break even when optional: `Plan` and `Step` forbid
unknown fields, so its writer bumps the plan format before it emits such a key.
An optional detail section that the established body readers ignore is additive
and does not bump the detail format; a carrier move or another reader-visible
detail change does. Readers support current and current-minus-one; writers emit
current only; version N retires by a dated, user-approved record before N+2
ships. This effort adds these authored-artifact rules to `DATA_CONTRACT.md`
alongside its existing transition and fail-closed rules. A transform carries
existing content forward but never invents missing content: a required missing
value becomes the established `_(TODO)_` placeholder and audit channel, or the
artifact is re-authored through `create --from-existing`. No model-authored
upgrade route exists.

At version 1 the supported set is `{1}` and the only pre-declaration state is
`absent`. For a live plan or live run-grade detail, `absent` is legacy version 1
for support-window purposes: it remains readable while version 1 is supported
and retires with it only after the dated retirement roster shows no absent
artifacts remain. A writer creates a fresh current-format artifact directly;
version-1 injection is valid only because a raw absent artifact is legacy
version 1. The version-policy record requires a future writer to refuse a
supported older declared version rather than relabel it as current. Version 1
deliberately has no operator upgrade command because it newly refuses no
previously supported live on-disk representation. The first later release that
makes either class reach a reader or writer refusal for one ships the affected
class's operator route alongside the bump, then uses the existing raw upgrade
before it writes the current artifact.

An archived detail bundle is a historical snapshot, not a live run-grade
artifact. `plan_tool/sweep.py:_archive_plan_details` and
`plan_tool/create.py:_copy_details_bundle_for_archive` deliberately prepend a
breadcrumb before the H1; that snapshot therefore has no run-grade carrier,
leaves the support window and upgrade obligation with its archived plan, and is
never re-authored or routed through a live detail reader. This is not a second
writer: `plan_tool/detail.py:_author_step_detail` remains the sole writer of a *current*
run-grade detail body.

That first legacy-refusal release also preflights the affected class's reader or
writer compatibility before any command mutates plan-adjacent state. It does
not rely on a late `write_plan`/`render_plan_text` refusal after a green step,
a lesson append, or a seed/archive mutation. Each affected command either
performs the shared preflight before its first mutation or follows an explicitly
documented transactional rollback route; its version-specific tests prove the
operator can upgrade and rerun without being left in partial state.

Each class exposes a pure, explicitly called absent-to-1 transform over its
raw input, exercised by the coverage test. The plan enumeration is
`{absent} ∪ supported`; the detail enumeration is
`{absent with a valid carrier} ∪ supported`. A carrier-less detail remains a
readable legacy shape only while version 1 is supported, but it lacks a carrier
the raw transform may use; its declared path to current is the explicit forced
re-authoring route above, not the upgrader. A later operator route belongs to,
and is required by, the first actual break that makes a previously supported
live on-disk representation reach either reader or writer refusal.

**The drift record names constants, not artifact schemas.** A narrow
version-only record in `data_contract.py` supplies the owner, code anchor,
documentation section, and version constant for each authored class. It does
not make `Plan` a dataclass, describe markdown as JSON, or take ownership of
either format schema. `DATA_CONTRACT.md` records this policy and its constants;
its Scope explicitly admits the authored-artifact version constants and
evolution policy while the two format documents remain the structure
references.

## Scope guardrails

The check asserts exactly one binary observable: **the artifact's declared
format-version value is one this build supports.** Nothing else. Every
semantic run-grade detail reader performs that same check before using a body.

The check does not validate the body schema. A body with no valid carrier H1 —
no column-0 H1, an indented H1, or a nonblank preamble before one — has no
carrier slot, so any marker-shaped text it contains is ordinary prose and the
existing absent-version behavior applies; `parse_detail_response` remains the
separate authoring-time H1 validator using that same recognizer. A malformed
declaration is only one that appears in the fixed carrier slot, and it refuses
rather than defaulting.

The upgrade obligation carries its own binary observable: **each plan absent
state and supported version, and each detail state with a valid carrier plus
every supported version, has a declared path to current**, enumerated by a
coverage test that fails when a supported state is added without one. A
carrier-less detail has no safe raw upgrade because the transform cannot invent
an H1; its separate declared path is forced re-authoring. At version 1 the
absent-to-1 path makes the upgradable-state obligation real rather than prose.

Not allowed, enumerated rather than implied:

- Checking whether an artifact's *content* conforms to the version it
  declares. The declaration is taken at its word; agreement between a declared
  version and the artifact's actual shape is not observable here and is not
  checked.
- Any quality judgment, prose-agreement check between two artifacts, or shape
  or length cap.
- A fallback that feeds an unsupported run-grade body to a command. Plan
  readers use their existing validation-error handling. A run-grade detail
  refusal stops the invoking command before it uses the body; `run` therefore
  returns its existing command-error outcome before backend invocation.
- Emitting a warning, finding, or advisory about a *supported* version.
- Upgrading, inferring, or repairing a version *at read time*. Reading never
  upgrades: a reader meeting an unsupported version refuses. Upgrading is a
  separate, explicitly invoked action, never a side effect of parsing.

## References

- `BACKLOG.md` #356 — the source entry whose scope contract this plan
  inherits for the plan and detail classes, and which this effort removes on
  shipping. Its roadmap half is tracked separately at `BACKLOG.md` #362.
- `DATA_CONTRACT.md` § "Version-evolution policy" — the fail-closed reader
  rule this effort extends to the authored-artifact layer, and § Scope, which
  currently excludes it.
- `PLAN_FORMAT.md` § "Validation rules" — rule 8, the unknown-field rejection
  that makes a newer plan undiagnosable to an older reader.
- `DETAIL_FORMAT.md` § Format — the pure-markdown, no-frontmatter contract the
  detail carrier must respect.
- `plan_tool/parser.py:parse_plan_text`, `plan_tool/parser.py:write_plan`,
  `plan_tool/schema.py:208`, `plan_tool/roadmap_seed_state.py:render_seed_state_marker`,
  `plan_tool/detail.py:_REQUIRED_H2_TOKENS`, `plan_tool/data_contract.py` —
  the seams verified at HEAD.
- `handoffs/2026-09-08-authored-artifact-structure-versioning.md` — the design
  session that produced this scope and the reasoning behind the roadmap
  deferral to `BACKLOG.md` #362.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- The four staged roadmap artifacts — the in-band declaration and any upgrade,
  both. Carved out 2026-09-08 into `BACKLOG.md` #362, deferred, because
  stamping a declaration changes bytes the accepted-head roadmap-version store
  binds by exact digest (`roadmap_versions.py:_require_content_matches_record`),
  and because `roadmap_source_identity.py`'s
  `CanonicalSourceIdentity.format_version` already exists in the same
  subsystem naming a different concept — the semantic-projection version used
  for baseline identity, not the staged artifact's on-disk structure. See
  `handoffs/2026-09-08-authored-artifact-structure-versioning.md` for the full
  reasoning and #362's re-entry trigger.
- Any version 2 of any artifact. This ships the version-1 declaration and the
  refusal; the first real format change is a separate effort under the
  version-evolution policy.
- A migration *engine*, a `plan-tool migrate` verb, or a concrete v1-to-v2
  conversion — there is no version 2 to convert to. This effort lands the
  upgrade entry point and the obligation binding every future version; the
  engine belongs to the version that first needs one.
- Rewriting or upgrading artifacts on read. A reader refuses an unsupported
  version; it never repairs one.
- Content revision, lineage, generation counters, or history. Retired #92
  holds that axis behind a re-open bar, `BACKLOG.md` #198 owns git-native plan
  provenance, and closed #328 already ships the roadmap content-version store.
- Declaring the detail *grade* in the artifact. A detail reader is handed its
  grade by its caller (`jira_grade.py:GRADE_DEFAULT`), which is a separate
  gap; this effort does not close it and must not widen the marker to carry
  it.
- Legacy jira-grade detail artifacts, whose creation is already disabled.
- Versioning `BACKLOG.md` / `BUG_BACKLOG.md`, `plan-seeds/`, roadmap draft
  seeds, or jira story exports.
- Changing any existing version constant, `audit_input_revision`'s `version`,
  or `PURITY_VERDICT_LOGIC_VERSION`; relaxing `extra="forbid"`; and giving
  detail files YAML frontmatter.
- A preservation check for arbitrary direct model edits. `apply_finding` may
  edit a plan or detail file in place and remove a declaration while preserving
  its carrier. The next `write_plan` incidentally restores a plan declaration,
  but a detail declaration persists as absent until that detail is deliberately
  re-authored; a dropped declaration and a destroyed or carrier-less detail
  body are accepted residuals rather than new reader checks. A malformed marker
  in an intact fixed slot remains the hard refusal, with no read-time repair.

## Risks

- A gate placed after strict validation is inert and reads as shipped. The
  plan class is the one that proves this, because `extra="forbid"` makes the
  failure mode concrete.
- A field added with a model default is elided by `write_plan` and produces
  plans that declare nothing, while every test that constructs a `Plan`
  in-process still passes.
- The first stamped plan is intentionally one-way: a pre-declaration binary
  rejects its new `format_version` key as an unknown field. That legacy result
  cannot be repaired by this release, is not a supported reader, and is stated
  in the format documentation and tests before the writer becomes default.
- The detail refusal is a new reason for `run` to stop before backend
  invocation. Wording it without the declared and supported values leaves an
  operator with the same undiagnosable state the effort exists to remove.
- Widening the detail marker into a general metadata block reopens the
  frontmatter question the pure-markdown contract settled.
- The upgrade obligation degrades into prose if nothing fails when a version is
  added without a path. The coverage test is the mechanism that holds it, so an
  absent or supported state it does not enumerate is the real failure mode.
- A direct model edit can remove a declaration while leaving a valid carrier.
  This effort adds no preservation gate: a later unrelated plan mutation
  re-stamps its declaration, while an undeclared detail persists until an
  intentional detail re-authoring. A dropped declaration or destroyed carrier
  remains accepted residual risk; a malformed marker in an intact slot is
  instead a hard refusal until explicit re-authoring, so the post-edit delta
  path must retain its named diagnosis.
- The first plan or detail rewrite changes bytes captured by saved-review and
  audit fingerprints. Existing reports become stale and require their normal
  fresh audit; this is accepted file-change staleness, not a migration gate.
- The first refusal of a previously supported live representation can otherwise
  land after a command has already marked a step green, appended a lesson, or
  changed a seed. That release must preflight compatibility before its first
  mutation and test that its operator route upgrades then reruns without
  partial state.

## Testing

Per class, prove three states: an artifact with no declaration reads as
version 1 and parses identically to today; an artifact declaring version 1
parses identically; an artifact declaring an unsupported value is refused with
a message naming its declared version and the build's supported-version set.
Pin each by mutation — break the gate and watch the assertion go red — rather
than by reading, per CLAUDE.md § Tests.

For a carrier that is present but malformed, prove the reader refuses rather
than treating it as absent: a non-integer plan value and a malformed marker in
the fixed post-H1 slot each fail closed. A marker-shaped line outside that slot
remains ordinary prose.

Prove the two traps directly, since both stay green under a naive suite: a
plan carrying an unknown key *and* an unsupported version is refused for the
version, not the key. Fresh and current-version plans round-tripped through
`write_plan` and `render_plan_text` (including concept-sync publication) each
come back carrying their declaration; an effective current-minus-one plan —
including raw absent once version 2 ships — refuses serialization until its raw
upgrade runs.

Prove the reader classes rather than only their parser: run prompt assembly,
review/audit, deep reconcile, detail quality and every regeneration path that
semantically reuses an existing body, scope-out, annotation, completeness
reporting, `validate`'s pointer-backed suppression scan, selected run-reconcile,
drift-halt auto-reconcile, Jira export, gate suggestion, split criteria,
pre-mutation apply surfaces, and detail merge/sibling reads all reject an
unsupported run-grade marker
before they consume its body. Prove that `run` does not invoke a backend on that
refusal, while `suggest-gates` and `split-criteria` return their command error
without partial output. A forced plain detail regeneration with
`--recover-refused --no-completeness` instead archives and replaces one refused
target without reading any pre-existing bundle detail; the operator reruns
completeness only after every refused sibling is repaired, while ordinary
forced re-authoring and merge retain their prior and sibling context. Prove a
refusal stops every other
plan-bundle operation but leaves missing and unreadable detail on its current
best-effort path; list renders a malformed plan row, and batch annotate records
the rejected source then continues its independent inputs. Byte-only fingerprint
and persisted path metadata remain ungated; `split_criteria.py` supplies only
already-gated detail bodies to `granularity.py`, while `detail.py`'s mixed-step
parser receives only in-flight model or freshly drafted bodies.

Prove the error boundaries as well as the reader: each of
`_format_already_implemented_block`, `collect_step_grounding_findings`, the
audit-budget estimator, `compute_plan_mass_best_effort`,
`_compute_findings_delta`, and `_run_completeness_tail` continues its existing
ordinary-failure fallback but re-raises `DetailFormatError`. Direct CLI recovery
suppresses sibling,
already-implemented, and deterministic-grounding prompt blocks; forced review
regeneration and merge remain negative controls that retain them.

Prove the error reaches the operator as well as the shared reader: every direct
CLI route for audit, reconcile, scope-out, annotation, and semantic `detail`
reuse prints the declared-and-supported `DetailFormatError` diagnostic with an
exit-1 command error and no crash traceback. Apply surfaces fail before edits.
`run` and Jira retain their existing named error results with the same diagnosis.

Prove the upgrade obligation by its mechanism, not by inspection: the coverage
test enumerates plan `absent` plus each supported version and detail
`absent-with-carrier` plus each supported version, and asserts a path to current
for each; adding an unpathed supported state turns it red. At version 1 the
explicit absent-to-1 raw transform is that path; fresh writer stamping remains
a separate current-artifact operation. The test feeds raw absent frontmatter or
a marker-free, H1-bearing detail body, so reader normalization cannot turn the
transition into an identity. A raw detail body with no valid carrier H1 — no
column-0 H1, an indented H1, or a nonblank preamble before one — instead takes
the named upgrade refusal and
remains unchanged; its declared path is forced re-authoring with
`--recover-refused --no-completeness`, which a recovery test proves writes a
current carrier without reading the body. Leading blank lines before an H1
remain valid and receive the marker after that H1.

Prove the archived-snapshot exemption rather than only its prose: both archive
writers prepend their breadcrumb before the H1, and a shared carrier-locator
assertion proves the resulting historical detail has no valid run-grade carrier.
This keeps a readability-only archive-header move from silently re-entering the
live support window.

Prove the fixed-carrier and bootstrap contracts directly: a plan's
`format_version` and the detail marker's name and post-H1 placement stay
recognized while marker-shaped prose elsewhere is ignored; an unsupported plan
takes the existing validation-error path while `annotate` catches its named
`UnsupportedPlanFormatVersionError` before rough-note fallback, reports it for
one source, and continues a batch's other sources. A strict fixture containing
the pre-declaration Plan field set rejects the first stamped plan's
`format_version` as the accepted one-way bootstrap result.

Stage-separated replay. The bare-plan audit owns the carrier decision for
detail — a plan-level contract that may not be deferred to `detail`. The
detail-grounded audit owns the gate-before-validation ordering and the
`write_plan` elision mechanism. A bare-stage finding that proposes checking
content against a declared version is out of scope by the guardrails, not a
gap to close.

## Acceptance criteria

- Each class declares its format version in-band at its fixed carrier: plan
  frontmatter `format_version`, or the detail comment as the first non-blank
  line after its H1, before `Summary`. Marker-shaped detail prose elsewhere is
  ignored; later versions never move or rename either carrier.
- Each plan reader and every semantic run-grade detail reader refuses an
  unsupported declared value with a message naming the declared version and the
  build's supported-version set.
- A named plan- or detail-format refusal from `validate` always prints one
  `INVALID:` verdict and exits 1; step 1 owns the plan-format arm and its test,
  while step 3 owns only the detail-format arm and the pre-`OK:` ordering.
  Other schema-invalid plans keep the existing `--fail-on-findings` policy.
- An artifact with no declaration parses to the same result as before this
  effort, for both classes.
- The plan gate refuses an unsupported version before `Plan.model_validate`
  runs, demonstrated on a plan that also carries an unknown key, and uses the
  existing validation-error handling while `annotate` catches
  `UnsupportedPlanFormatVersionError` before rough-note fallback and surfaces
  its refusal.
- A fresh or current-version plan written by `write_plan` carries its
  declaration; an effective older plan refuses serialization until its explicit
  raw upgrade runs.
- A fresh or current-version plan rendered by `render_plan_text`, including
  its concept-sync publish path, carries its declaration; an effective older
  plan refuses serialization until its explicit raw upgrade runs.
- Every run-grade detail file `detail.py` writes carries its declaration at the
  fixed post-H1 position before `Summary`. `detail.py` replaces any
  model-proposed marker in that slot with its own current marker exactly once;
  the main prompt and `detail.py:_REPROMPT_SUFFIX` reserve the position without
  declaring a version, and `DETAIL_FORMAT.md` describes the resulting position.
- An H2-first or indented-H1 model response is rejected inside the detail
  author's existing retry loop; the authoring-time H1 check and carrier locator
  use the same column-0 recognizer. A no-H1 on-disk body resolves as absent
  legacy version 1 and is accepted only while that version remains supported.
- An unsupported run-grade detail stops `run` before backend invocation and
  stops every plan-bundle operation that semantically reads it before use; it
  creates no advisory, fallback body, partial output, or secondary gate. A
  direct plain `detail --step N --force --recover-refused --commit
  --no-completeness` archives and replaces it without reading any existing
  bundle detail, which is the explicit recovery route even when every sibling
  declares an unsupported version; it re-audits only after every refused target
  is replaced. Ordinary forced re-authoring, forced review regeneration, and
  merge are not recovery mode and keep their ordinary context.
- Every unsupported run-grade detail refusal reaches its CLI operator as the
  declared-and-supported named format diagnosis through either its established
  command error or `plan_tool/cli/app.py`'s typed handler, never as an unexpected-error
  traceback; the typed handler returns exit 1.
- An auto-completeness tail propagates `DetailFormatError` to its parent command
  rather than downgrading it to a warning; only the documented forced recovery
  route skips that tail. Ordinary audit failures retain the existing best-effort
  warning.
- Completeness mass reads propagate a detail-format refusal rather than silently
  omitting a body, and every apply surface refuses before its first mutation;
  the parallel completeness dispatcher and all review-walk action handlers
  re-raise it before recording a per-item result or continuing to a sibling.
- Missing and unreadable detail retain their existing best-effort behavior;
  list renders an unsupported plan as malformed, and batch annotate reports a
  rejected source while continuing independent inputs.
- The first stamped plan's rejection by a pre-declaration binary is documented
  and tested by feeding that stamped plan to a strict fixture whose old `Plan`
  field set has no `format_version` field, as the accepted one-way bootstrap
  result.
- Each artifact class exposes an upgrade entry point mapping every supported raw
  state to the current raw state; the plan's absent state and the detail's
  H1-bearing absent state are exercised through it. Fresh writers do not invoke
  the entry point. A carrier-less detail follows the separately tested forced
  re-authoring route because its raw upgrader refuses rather than synthesizing
  an H1. Version 1 exposes these library APIs only; the first release making a
  previously supported live plan or detail reach a reader or writer refusal
  ships an operator-invocable route for the affected class in the same change.
- A coverage test enumerates every plan absent-or-supported state and every
  detail H1-bearing-absent-or-supported state and fails when one has no declared
  raw upgrade path; a separate recovery test covers a carrier-less detail, so no
  future version can ship with an unpathed live representation.
- Reading still never upgrades: a reader meeting an unsupported version
  refuses, and the upgrade path is reached only by explicit invocation.
- `DATA_CONTRACT.md` and its registry-driven test hold the class-specific
  break rule, writer eligibility, support window, and retirement rule: a new
  plan key bumps the plan version; an ignored optional detail section does not;
  future writers refuse a supported older declared artifact until its explicit
  upgrade runs; only a raw absent artifact receives the version-1 legacy default;
  the first release making a refusal of a previously supported live
  representation reachable preflights compatibility before its first mutation
  and ships its operator upgrade route.
- An archived detail bundle is a non-run-grade historical snapshot: its
  breadcrumb preamble intentionally removes the live carrier, and archive exit
  also removes its support-window and upgrade-path obligation. Tests prove both
  archive writers keep that breadcrumb before the H1.
- A present but malformed plan or detail declaration refuses rather than
  defaulting to version 1.
- A body with no valid carrier H1 has no marker slot and follows the absent
  legacy-version support check; marker-shaped text there is ordinary prose, not
  a declaration. Leading blank lines before a column-0 H1 preserve the carrier
  slot, while an indented H1 does not.
- `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and `DATA_CONTRACT.md` describe the
  declaration, refusal, bootstrap result, and policy boundary: step 2 owns the
  plan document's declaration/bootstrap/refusal text and step 4 owns the detail
  document's marker/refusal text. `CLAUDE.md` names the new format contract; and
  the version-only data-contract record makes `tests/test_data_contract.py` fail
  when either constant, the class-specific break rule, writer eligibility,
  support window, or retirement rule drifts.
- `DATA_CONTRACT.md`'s Scope explicitly covers the authored-artifact version
  constants and evolution policy while the two format documents retain schema
  ownership.
- `BACKLOG.md` #356 is removed when the work ships; #362 stands without a
  reference to its deleted parent, and the planning lanes no longer advertise
  this shipped plan as next work. The bounded follow-ups #363 (first
  legacy-refusal operator route), #364 (contract drift coverage), and #365
  (documentation and manifest discoverability) remain independent entries.

## Deferred

Out-of-scope discoveries are filed in `BACKLOG.md` or `BUG_BACKLOG.md` per
that file's decision rule, never applied as plan expansion. This restructuring
files three bounded follow-ups: `BACKLOG.md` #363 owns the first legacy-refusal
operator route, #364 owns completeness/registry drift coverage for the version
contract, and #365 owns documentation and manifest discoverability. Declaring
the detail grade in the artifact; a version declaration for draft seeds, plan
seeds, or jira exports; and a concrete v1-to-v2 conversion remain unfiled until
their own concrete break exists. The roadmap staged-artifact class is not a
loose candidate here — it is tracked as its own entry, `BACKLOG.md` #362, with
its own re-entry trigger.

If the detail carrier turns out to require a body-schema change rather than a
marker, stop and file that decision instead of widening this effort — a
detail-format change is a second Outcome.
