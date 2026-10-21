> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Seed Ingestion Routing
intent: So a usable seed is authored from as supplied — and a seed that needs help
  takes one named, visible preparation route — instead of model output silently replacing
  the operator's source and spending calls that were never necessary.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/intentional-seed-ingestion-routing.md
steps:
- id: 1
  title: Classify every file-backed source at the create intake seam with unique normalized
    direct-ready headings, References preflight, and strict-steps properties
  intent: Give --from-existing and its matching library call one deterministic answer
    to whether the raw source can remain authoritative, which incomplete property
    selects preparation, which ambiguous required evidence refuses before cost, and
    whether its step graph can be lifted without a proposal.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/seed-ingestion-routing/01-classify-every-file-backed-source.md
  status: done
- id: 2
  title: Replace the file-backed 16 KiB shortcut with a source-authoritative direct
    route that performs one raw-only split check and bypasses generic post-write convergence
  intent: Stop model rewriting and generic post-write edits for a usable source while
    retaining one deliberate pre-write single-versus-split decision and preserving
    raw source authority through publication, while failing closed when that decision
    cannot safely classify the source.
  files:
  - plan_tool/create.py
  - plan_tool/distill_thresholds.py
  - plan_tool/split_criteria.py
  - tests/test_create.py
  - tests/test_distill.py
  - tests/test_split_criteria.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: supplies the deterministic verdict and route names this branch dispatches on
  detail: docs/implementation-plans/plan-details/seed-ingestion-routing/02-replace-file-backed-16-kib-shortcut.md
  status: done
- id: 3
  title: Give file-backed preparation one exhaustive result contract — normalized,
    split, or refused — before any plan or manifest write
  intent: Make every source that needed model help end in exactly one stated outcome
    instead of quietly reverting to raw text, with repair remaining an internal bounded
    attempt rather than an ambiguous published route.
  files:
  - plan_tool/create.py
  - plan_tool/prompts/distill-seed.md
  - tests/test_create.py
  - tests/test_distill.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: supplies the closed route vocabulary these terminal results are drawn from
    2: installs the route dispatch this branch hangs the non-direct arm off
  detail: docs/implementation-plans/plan-details/seed-ingestion-routing/03-give-file-backed-preparation-one.md
  status: done
- id: 4
  title: Refuse unsupported normalized evidence before every authoring call in both
    iterative and non-iterative create modes
  intent: Stop a source that cannot support Out of scope, Risks, Testing, Acceptance
    criteria, or Deferred from spending step or References calls or reaching a late
    placeholder gate.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: mints the refusal/repair result and the point in the flow where it is returned
  detail: docs/implementation-plans/plan-details/seed-ingestion-routing/04-refuse-unsupported-normalized-evidence.md
  status: done
- id: 5
  title: Publish route, exit, and --no-distill compatibility semantics for TTY, --yes,
    and non-TTY callers
  intent: Let an operator and a headless caller see which ingestion route create took
    and whether it produced a plan, a discoverable split, or a refused input; prevent
    --no-distill from bypassing file-backed routing while retaining inline compatibility.
  files:
  - plan_tool/create.py
  - plan_tool/cli/authoring.py
  - docs/cli/create.md
  - tests/test_distill.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 3
  - 4
  depends_on_notes:
    3: supplies the complete result set that output and run records must be able to
      name
    4: adds the refusal producer whose outcome this step must also report
  detail: docs/implementation-plans/plan-details/seed-ingestion-routing/05-publish-route-exit-no-distill.md
  status: done
- id: 6
  title: Set versioned per-route checkpoints and artifact handling for direct, normalized,
    split, and refused outcomes
  intent: Make each route's effect on the seed file, the normalized artifact, and
    the saved checkpoints explicit, including stale-contract invalidation and every
    no-plan outcome, rather than a side effect of which producer happened to run;
    select one lifecycle table before helpers or archive calls are changed.
  files:
  - plan_tool/create.py
  - plan_tool/cli/authoring.py
  - tests/test_distill.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  - 5
  depends_on_notes:
    2: the direct route produces no distilled text, so the artifact writer and its
      archive step get no input on that route
    3: names the normalized and refusal results this step keys archival on
    5: publishes the explicit selected-route handoff lifecycle work consumes
  detail: docs/implementation-plans/plan-details/seed-ingestion-routing/06-set-versioned-per-route-checkpoints.md
  status: done
- id: 7
  title: Update the ingestion, resume, CLI, seed-format, arc, and backlog surfaces
    to describe the shipped route contract
  intent: Leave every maintained operator-facing route description aligned with the
    shipped contract, and close out the originating backlog entry and its arc.
  files:
  - docs/how-to/pipeline/create-from-existing.md
  - docs/reference/contracts/seed-ingestion.md
  - docs/how-to/recovery/create.md
  - docs/how-to/recovery/README.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md
  - SEED_FORMAT.md
  - README.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  - 5
  - 6
  depends_on_notes:
    2: settles what the direct route actually skips, which SEED_FORMAT's canonical-H2
      claim currently overstates
    3: settles the result names the docs must use
    5: settles the output and run-log wording the flow doc reproduces
    6: settles the archive and checkpoint tables in the flow and resume docs
  detail: docs/implementation-plans/plan-details/seed-ingestion-routing/07-update-ingestion-resume-cli-seed-format.md
  status: done
---
# Seed Ingestion Routing

## Overview

`create --from-existing` and `create_plan` calls with a file-backed source
first pass unmatched-fence input safety and require exactly one non-placeholder
`## References` section. An unmatched fence or missing, placeholder, or duplicate
References heading is a pre-log refusal: it exits 2 before a run record,
checkpoint, model call, or write. Every source that passes those preflights
ends in exactly one visible in-`create` outcome:
`direct`, `normalized`, `split`, or `refused`.
A direct-ready source receives one deliberate, non-rewriting pre-write split
assessment: `single` produces `direct` and a multi-plan result produces
`split`. A source that is not direct-ready enters preparation and produces
`normalized`, `split`, or `refused`. Repair is a bounded internal attempt that
either yields one of those results or ends as `refused`.

Malformed, schema-invalid, or otherwise non-decision direct assessments are
post-preflight refused results with the reason direct_split_assessment_invalid.
They never publish the raw source, fall through to preparation, or create a
fifth visible route.

## Problem statement

The current distill pass mixes source canonicalization, split assessment, and
downstream source replacement. It can replace supplied prose even when the
source already supplies the body and References that plan authoring needs, and
its size-based shortcut does not express why a model call is necessary. It also
lets `--no-distill` and the library default bypass the route entirely. The
existing safe split proposal must remain inside `create`, but the selected
route and artifact authority must be visible to operators, headless callers,
run records, checkpoints, and archival handling. The direct-ready split check
is a deliberate new cost that preserves automatic split protection without
normalizing or replacing source text; it is not the current canonical-small
shortcut, which skips split assessment entirely.

## Architecture

The new routing governs only `--from-existing` and library calls carrying
`from_existing_path`; inline `--from` prose and library calls with no file-backed
path retain their present `distill`-flag behavior. The file-backed gate retains
the existing non-placeholder References refusal and accepts a direct source
only when every canonical body H2 appears exactly once, is non-empty, and
holds no recognized placeholder after shared H2 normalization. Letter case and
an optional closing ATX sequence do not change a canonical title; semantic
heading aliases remain BACKLOG #102. It reuses the recognized placeholder
syntax from existing References validation, not a new content-quality
heuristic. A duplicate canonical body H2 selects preparation; a duplicate
References H2 is ambiguous required evidence and uses the pre-log refusal. A
strict canonical `## Steps` block is a separate property: it skips step
decomposition when present, but its absence does not force body normalization
or make a source non-direct-ready.

Every file-backed entry selects one raw source value before References
preflight: `seed_body` when it is not `None`, otherwise `from_description`. An
empty provenance body remains selected and refuses on its own merits; neither
`cmd_create` nor `_prepare_create_plan` may substitute a non-empty description
with a truthiness fallback. The CLI passes that same selected value into its
pre-log check, and the library carries it through classification and all route
decisions.

Each direct-ready candidate receives the deliberate new pre-write
single-versus-split assessment against the raw source. A `single` assessment
publishes `direct`; a `SplitProposal` stays a no-plan, no-manifest success with
an operator-visible next action. That assessment may classify scope but never
supplies replacement authoring text. A published `direct` result ends after
its initial write and does not enter `_converge_create_plan`: it makes no
Reference or step re-proposal and dispatches no `apply_finding` prose edit.
Its raw body and References therefore remain authoritative through publication.
Source authority is enforced at every create writer: direct protects its entire
raw body and References, while normalized protects its five exact
source-materialized evidence-only fields. The scope-decision renderer, concept
synchronization, and convergence apply path preserve those protected ranges; an
attempt to alter one is rejected before a successful create result. The
boundary lasts for this create invocation only: a later operator-directed audit
can change the published plan through its own explicit workflow. `--iterate`
retains its existing convergence behavior for normalized and inline routes, but
normalized convergence may alter only fields outside its protected evidence.

An invalid or non-decision direct assessment fails closed as refused with the
direct_split_assessment_invalid reason. It does not retry through preparation
or publish an unprotected direct plan. This is a terminal result in the
existing visible outcome set, not a new route name.

Preparation returns one closed result before a plan or manifest write. A
normalization candidate must contain all eight canonical keys, with non-empty
derived `Overview`, `Problem statement`, and `Architecture` values; their
absence is an invalid preparation response. It preserves supplied optional
context and maps evidence without fabricating commitments. A candidate may
carry a `null` evidence span only long enough for the evidence gate to refuse
it: an accepted `normalized` result has all eight non-empty canonical body
sections. Unsupported `Out of scope`, `Risks`, `Testing`, `Acceptance criteria`,
or `Deferred` content returns `refused` before every subsequent authoring call
in both iteration modes. For each evidence-only section, the preparation
response must supply one or more valid inclusive raw-source line spans. The
parser materializes that section from those exact source lines and ignores any
model-authored prose for it; a missing or invalid span is unsupported evidence.
The resulting complete materialized map bypasses later body synthesis, so that
validated evidence cannot be replaced downstream. A malformed fresh response
gets one repair call. A malformed cached preparation response is discarded and
takes that same one repair call; its invalid repair returns `refused`. A direct
assessment has no repair. Raw passthrough is not an outcome.

`direct` and `normalized` publish one plan. `split` is a successful, no-plan,
no-manifest outcome and preserves the source for operator action. `refused` is
a terminal post-preflight no-write input failure: it records the selected route
in the active run log and exits 2 in TTY, `--yes`, and non-TTY modes. An
unmatched input fence and a missing, placeholder, or duplicate References
section are the file-backed preflight refusals with no selected route or run
record. `--no-distill` remains an inline compatibility control but cannot
bypass file-backed classification or preparation.

## Terminal route lifecycle

Step 6 will implement this selected CLI lifecycle rather than deriving it from
which helper happens to return:

| Result | Plan and manifest | Source and normalized artifact | Routing checkpoints | Run record and exit |
|---|---|---|---|---|
| Input-syntax or References-preflight refusal | neither is written | the source remains in place; no normalized artifact exists | none are read or written | no selected route or run record; exit 2 |
| direct | one plan and manifest entry publish | archive the raw source only after the plan publishes; never write a normalized artifact | discard stale preparation and direct-assessment checkpoints after success | record direct; exit 0 |
| normalized, clean finalization | one plan and manifest entry publish | archive the raw source and the emitted normalized artifact only after clean finalization | key preparation reuse by raw input, prompt, and result contract; discard it after success | record normalized; exit 0 |
| normalized, iteration incomplete | the initially published plan and manifest remain registered | retain the raw source; do not emit or archive a normalized artifact | retain preparation and convergence checkpoints for the existing plan | record iteration_incomplete; exit 0; resume in place with completeness-audit on the slug |
| split | neither is written | retain the raw source and any rendered split worksheet; no normalized artifact exists; roll back any collision-created branch binding | retain the versioned split result for retry | record split; exit 0 |
| post-preflight refused, including invalid direct assessment | neither is written | retain the raw source; write no normalized artifact and remove any transient one | discard the direct-assessment or preparation result | record refused with its reason; exit 2 |

`create_plan(..., from_existing_path=...)` uses the same source selection,
route vocabulary, preparation, and checkpoint policy, but is non-destructive:
it never moves the supplied source or writes a normalized sibling. It returns
the selected route and any clean-normalized artifact payload needed by a caller.
Only `cmd_create` owns durable source/artifact writes and calls
`archive_existing_source`, after a clean route-specific finalization. An
iteration-incomplete library result likewise retains its caller-owned source;
the in-place completeness-audit command remains the recovery path for the
published plan.

## References

- [CommonMark Spec 0.31.2 — ATX Headings and Fenced Code Blockshttps: — Normative Markdown grammar for line-anchored headings and fenced spans, needed to decide canonical body sections and detect a placeholder/absent References heading deterministically.
- [PyYAML Documentationhttps: — Reference for safe_load/dump behavior and error types when parsing and re-emitting the YAML frontmatter that carries plan and step properties at the intake seam.
- [Python argparse — Parser for command-line options, arguments and subcommandshttps: — Canonical reference for wiring the create --from-existing / --yes surface and the parser-level exit behavior the route outcomes must respect.
- [Python enum — Support for enumerationshttps: — Reference for modeling the closed, observable route vocabulary (`direct`, `normalized`, `split`, `refused`) as an exhaustive typed set rather than free strings.
- [Python os module — os.replace and file descriptor operationshttps: — Documents the atomic-rename and fsync primitives required so checkpoint reuse and raw/normalized archive writes never leave a partially published artifact.
- [Claude Code CLI referencehttps: — Authoritative flag, output-format, and non-interactive invocation contract for the model subprocess calls the direct-ready gate is meant to skip.
- [pytest — How to use temporary directories and files in testshttps: — Reference for the hermetic tmp_path/monkeypatch fixtures used to pin TTY vs headless reporting, run-log outcomes, and no-plan/no-manifest split assertions.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A general semantic seed audit or a new universal canonical-heading
  preflight beyond References.
- Removing `SplitProposal`, moving split assessment into a separate command,
  or silently continuing a split as one plan.
- Changing step, References-research, or body-synthesis contracts beyond the
  selected source and preparation routing they consume.
- Rewriting historical seeds or artifacts, or implementing #102's broader
  heading-alias proposal. This route normalizes canonical title case and a
  closing ATX sequence only.

## Risks

- An over-permissive direct-ready gate can publish from an unusable source;
  an over-narrow gate preserves unnecessary model cost and hidden rewriting.
- Checkpoints, archived raw/normalized artifacts, CLI exit behavior, and run
  records form one compatibility surface across terminal and headless modes.
- A preparation result must not fabricate scope, risks, tests, acceptance
  criteria, or deferrals merely to complete a canonical shape.
- A stale preparation checkpoint can otherwise replay an old result contract
  under a new parser, and a post-write refresh can otherwise undo source
  authority after the initial direct write.

## Testing

- Cover the file-backed/direct-library gate, exactly-one canonical body and
  References headings, placeholder-only bodies, and the independent strict-Steps
  property; prove duplicate body headings select preparation while missing,
  placeholder, or duplicate References headings exit 2 before a run record,
  checkpoint, model call, or write. Prove an empty `seed_body` paired with a
  valid description fails against the same selected source in the CLI and
  library. Prove inline callers retain their existing routing.
- Cover a direct-ready source that receives exactly one deliberate raw-only
  split assessment. Its `single` outcome performs no normalization,
  References-research, body-synthesis, or `_converge_create_plan` call,
  including no re-proposal or `apply_finding` edit, and retains raw body and
  References through publication.
- Cover direct source authority through scope-decision rendering and final
  concept synchronization, and normalized materialized-evidence authority
  through scope synchronization and an enabled convergence apply. Both routes
  must reject protected-field changes while permitting their named unprotected
  work.
- Cover `normalized`, `split`, and `refused` preparation results. A normalization
  candidate requires non-empty derived body fields, and an accepted normalized
  result supplies every canonical body section; each unsupported evidence-only
  section, including Out of scope, refuses before any later authoring call under
  both `--iterate` and `--no-iterate`; split writes no plan or manifest entry.
- Cover raw-source evidence spans for every evidence-only normalized field:
  prove malformed, out-of-range, or missing spans refuse; prove model-provided
  field prose is ignored in favor of the exact cited source lines; and prove
  no later body synthesis replaces the materialized evidence.
- Cover absent optional Outcome, Input, and recognized guardrail context as
  cost-free and absent from the final required-body gate; supplied optional
  context survives normalization verbatim.
- Pin TTY, `--yes`, and non-TTY output, exit, and run-log outcomes: direct and
  normalized succeed, split succeeds with a next action, and refused exits 2.
  A post-preflight preparation refusal records its selected route; unmatched
  fence and References preflight refusals are the explicit no-record
  exceptions. Pin `--no-distill` file-backed parity and inline compatibility.
- Pin that split and refused both roll back a collision-created branch binding,
  while a normalized iteration-incomplete result retains the raw source and
  route checkpoints, emits no normalized archive artifact, and directs the
  operator to the in-place completeness-audit resume command.
- Pin direct checkpoint clearing, normalized checkpoint versioning by prompt and
  result contract, invalid-cache preparation repair, split checkpoint reuse,
  refused-checkpoint discard, CLI-only raw and normalized archive behavior, and
  the file-backed threshold/split-criteria wording after byte size stops
  selecting that route.
- Pin an invalid, malformed, or non-decision raw-only direct split assessment
  to the refused result and its reason, with no plan, manifest, preparation
  call, normalized artifact, or safety-bypassing raw publication. Exercise the
  terminal lifecycle table for every route, including the no-record References
  preflight and source/archive timing after successful direct and normalized
  publication.
- Verify that the ingestion, resume, CLI, README, seed-format, arc, and backlog
  docs describe the shipped contract and close #327, including
  `RESUME_FLOW.md`'s repair-retry description.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- The route applies to every file-backed `--from-existing` and matching
  library invocation; `--no-distill` cannot bypass it, and inline input keeps
  its current behavior.
- A direct-ready file-backed source has exactly one of each normalized,
  non-empty, non-placeholder canonical body H2 and exactly one normalized
  References heading. A duplicate body heading selects preparation; missing,
  placeholder, or duplicate References refuses before the run log. After one
  deliberate raw-only split assessment yields `single`, direct publishes without
  normalization, References research, body synthesis, or generic post-write
  convergence; its raw body and References remain authoritative through
  publication. Strict Steps independently
  decides only whether step decomposition runs.
- File-backed CLI and library intake use `seed_body` whenever it is present,
  including an empty string, and otherwise `from_description`. References
  preflight and every file-backed route decision consume that one selected
  value; a valid description cannot mask an empty provenance body.
- Every non-direct-ready source reaches exactly one externally visible
  `normalized`, `split`, or `refused` result before publication; repair is
  bounded and never exposes raw passthrough as a result. A malformed cached
  preparation response is discarded and receives the same one repair call as a
  malformed fresh response; a direct assessment never repairs.
- Split stays an automatic, discoverable successful no-plan/no-manifest outcome,
  including for a source otherwise eligible for the direct route.
- References remains the only universal source fallback and refuses before
  cost when absent or placeholder.
- An unmatched source fence is a separate input-syntax preflight refusal. It
  likewise exits before a selected route or run record and does not change the
  References evidence requirement or add a fifth route.
- Preparation preserves optional supplied context and refuses unsupported
  evidence-only content, including Out of scope, before every later authoring
  call in both iteration modes.
- Every normalized evidence-only field is materialized from validated raw-source
  line spans, not accepted because the model supplied a non-null string; later
  body synthesis cannot replace that validated material.
- An accepted normalized result has all eight non-empty canonical body
  sections: the three derived fields validate before rebinding, and the five
  evidence-only fields validate before publication. It therefore never falls
  through to generic body synthesis.
- Direct raw body and References, and normalized materialized evidence-only
  fields, remain unchanged through every create-owned scope, concept, and
  convergence writer. A later user-directed audit is outside that create-time
  authority boundary.
- Route outcome, archive/checkpoint behavior, and command behavior are explicit
  and covered for TTY, `--yes`, and non-TTY operation. Direct and normalized
  publish; split succeeds with a next action; refused exits 2 without a write.
  A post-preflight refused route has a run record, while the missing,
  placeholder, or duplicate References and unmatched-fence preflights remain
  no-record exceptions.
- The public library applies the same route and checkpoint semantics but never
  archives or writes a source artifact; only `cmd_create` archives a clean direct
  or normalized CLI source chain after finalization.
- Checkpoints version the preparation prompt/result contract; direct clears
  preparation reuse, split preserves its result for retry, and refused results
  leave no reusable preparation checkpoint.
- Split and refused roll back a collision-created branch binding because neither
  leaves a plan. A normalized iteration-incomplete result keeps its registered
  plan, raw source, and route checkpoints without emitting a normalized archive
  artifact; the operator resumes the existing plan with
  `plan-tool completeness-audit <slug> --iterate`.
- An invalid or non-decision direct split assessment is refused with the
  direct_split_assessment_invalid reason. It writes no plan or manifest,
  enters no preparation route, retains its raw source, and records the same
  refused exit and lifecycle as every other post-preflight refusal.
- The completion sweep updates the listed ingestion/resume/operator documents
  and resolves BACKLOG #327 and this arc without reopening #102.

## Deferred

- Conservative aliases for near-miss canonical headings remain BACKLOG #102;
  this route only normalizes canonical title case and a closing ATX sequence.
- A general seed-quality or semantic-audit policy remains outside this route.
