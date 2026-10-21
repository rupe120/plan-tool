---
format_version: 1
title: Roadmap Stack Propagation
intent: A seed materialized from an accepted roadmap carries the hosting and store
  choices its plan depends on as settled constraints, `create` and `detail` carry
  them forward intact, and the plan audit treats them as commitments to trace.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-stack-propagation.md
steps:
- id: 1
  title: Render the accepted hosting and store stack into each draft seed in materialize_plan_seed
    (the draft and promoted-seed overwrites and the sidecar rewrite stay as they are,
    now writing the stack-bearing text, so a promoted seed rewritten after this change
    carries the section)
  intent: Draft seeds stop dropping the stack. The tool inserts a `## Stack` section,
    always emitted and naming its accepted version id, with every hosting row (id,
    facet, value, product) and the store rows (id, category, sharing, product) named
    by the plan row's components; a cross-cutting row includes its listed components
    and a row with no components renders the hosting rows alone. A model-authored
    `## Stack` section is replaced. A row with no product says explicitly that the
    accepted roadmap leaves the product open. This step owns its tests, namely open-product
    wording, a changed accepted row changing the rendered stack on rematerialization,
    the no-components and cross-cutting cases, replacement of a lookalike `## Stack`,
    and the rendered section passing `validate_draft_seed_content` and `classify_draft_seeds`
    without reading as drifted.
  files:
  - plan_tool/roadmap.py
  - plan_tool/prompts/roadmap-seed.md
  - tests/test_roadmap.py
  - tests/test_roadmap_seed_manifest.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-stack-propagation/01-render-accepted-hosting-store-stack.md
  status: done
- id: 2
  title: Add `Stack` to the existing guardrail-section mechanism so create preserves
    the seed's `## Stack` verbatim in the plan body and the scope fence threads it
    into detail prompts
  intent: 'A plan built from a stack-bearing seed keeps the roadmap''s store and hosting
    choices, for example PostgreSQL rather than its own SQLite. `Stack` joins `GUARDRAIL_BODY_SECTIONS`
    in `scope_fence.py` and the optional plan-body section shapes in `create.py`,
    the same path `Scope guardrails`, `Audit guardrails`, and `Expected placement`
    already use: the seed''s body is captured before distillation, overrides model
    output in the rendered plan, and reaches detail through the fence. The distill
    and synthesize prompts list it as a preserved section. `_load_roadmap_research_targets`
    keeps supplying product research only. A seed with no `## Stack`, such as a draft
    or promoted seed written before this change, carries nothing, so its plan has
    no stack commitment. This step owns its tests: verbatim preservation through create,
    presence in the detail fence, and the absent-section case. `Stack` sits last in
    `GUARDRAIL_BODY_SECTIONS`, after `Expected placement`, and the fence order, the
    `create.py` render order, and the two prompt lists follow it, with one test that
    pins the order. Every site that enumerates the guardrail headings is swept, and
    tests that pin the three-heading set are updated.'
  files:
  - plan_tool/scope_fence.py
  - plan_tool/create.py
  - plan_tool/prompts/synthesize-body.md
  - plan_tool/prompts/distill-seed.md
  - tests/test_scope_fence.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the seed's deterministic stack section, which create preserves as settled input
  detail: docs/implementation-plans/plan-details/roadmap-stack-propagation/02-stack-existing-guardrail-section.md
  status: done
- id: 3
  title: Have the plan audit treat a plan's `## Stack` as an authoritative preserved
    section and a settled technology choice as a commitment to trace
  intent: 'The per-plan completeness audit already treats `Scope guardrails`, `Audit
    guardrails`, and `Expected placement` as authoritative preserved sections, and
    traces commitments through every step and detail file. `plan-audit.md` receives
    two edits. The authoritative-section sentence in its scope-contract rule gains
    `## Stack` and is reworded so it covers a settled technology constraint, not only
    a scope, audit, or placement decision, so a stack contradiction is never read
    as out of scope. The commitment-kinds list gains a settled store or hosting product,
    so a step or detail that contradicts the carried stack is reported as a finding.
    The audit stays advisory and gains no gate, exit-code change, or technology-name
    comparison in code. A Integration-style replay, a plan whose `## Stack` says PostgreSQL
    and whose step says SQLite, is run through `completeness-audit` once and recorded
    in this plan''s handoff as an observation that gates nothing. This step owns its
    tests: the prompt carries both edits (asserted by key).'
  files:
  - plan_tool/prompts/plan-audit.md
  - tests/test_review.py
  complexity: low
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: the preserved `## Stack` section the audit prompt refers to
  detail: docs/implementation-plans/plan-details/roadmap-stack-propagation/03-have-plan-audit-treat-plan-stack.md
  status: done
- id: 4
  title: 'Document the draft seed''s `## Stack` section and its preserved carry through
    create, detail, and the audit, and reconcile BACKLOG.md #460'
  intent: 'The format docs describe the rendered stack section, including the explicit
    open-product wording, the per-row field sets, and the version id. PLAN_FORMAT.md
    lists `Stack` with the other preserved sections. #460 is removed only when the
    work has fully shipped, and the #461 and #462 dependency notes stay accurate.'
  files:
  - ROADMAP_FORMAT.md
  - docs/how-to/roadmap.md
  - PLAN_FORMAT.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: the landed stack section shape and wording to document
    2: the preserved-section carry to document
    3: the audit behavior to document
  detail: docs/implementation-plans/plan-details/roadmap-stack-propagation/04-document-draft-seed-stack-section-its.md
  status: done
---
# Roadmap Stack Propagation

## Overview

A draft seed materialized from an accepted roadmap will carry the hosting and store choices its plan depends on as settled constraints. `materialize_plan_seed` renders that stack deterministically from the accepted version under a fixed `## Stack` heading. `create` preserves the section verbatim in the plan body and `detail` receives it through the scope fence, both through the guardrail-section path that already exists. The per-plan completeness audit treats it as an authoritative section and traces a settled technology choice like any other commitment, so a step that contradicts the stack is reported as an audit finding. Nothing in `create` or `detail` judges the plan's prose.

## Problem statement

The accepted roadmap already defines the stack: the constraints gates require one hosting row per facet (`compute`, `model`, `topology`), and every component names its store rows, each with a category and an optional `product`. The stack is lost at seed materialization. `plan_tool/prompts/roadmap-seed.md` asks the seed to bind its domain rows, constraints, and assumptions, but not its hosting or store rows, and it leaves storage schemas to `create` and `detail`. So a draft seed names `store-app-db` by id without saying what it is, and `create`, grounding against a repository with no database, picks its own.

Observed 2026-10-08 in Integration (`integration-aidlc-mvp`): `03-components.md` declares `store-app-db` as `relational`, `pool`, `PostgreSQL` under the settled `decision-shared-database`. All six draft seeds cite `store-app-db` by id, and none names PostgreSQL. The plan `2-connector-registry-seed.md`, derived from one of them, persists to "the shared SQLite database". No draft seed carries `hosting-compute: managed-containers` either.

Source: BACKLOG.md #460. The entry is marked plan-authored while execution is pending. The plan reconciles that backlog entry when the work ships: it is removed only after full shipment, and any separately deferred follow-up is kept.

## Architecture

**Deterministic stack rendering at materialization.** `plan_tool/roadmap.py:materialize_plan_seed` inserts a section under the fixed heading `## Stack` into the draft after the model's reply, built from the accepted version (`plan_tool/roadmap_artifacts.py` — `HostingRow`, store rows, and their `product` fields). The tool owns that heading: a model-authored `## Stack` section is replaced by the rendered one, so the rendered rows are the only stack in the seed and no lookalike or contradicting model passage competes with them. The section is always emitted and names the accepted version id it was rendered from. Hosting rows (id, facet, value, product) are always included. Store rows (id, category, sharing, product) are those named by the plan row's component ids, including a cross-cutting row's listed components, and a plan row with no components renders the hosting rows alone. The components gates already guarantee that every named store resolves. A row with no `product` renders the explicit open wording, so an open vendor can be told apart from an unstated one. The checkable fact is that the seed's `## Stack` equals the accepted rows. #461 extends this renderer with stack collection and review callouts.

**Survival through draft-seed validation and identity.** The rendered section sits inside model-authored draft text. It must pass `plan_tool/roadmap_gates.py:validate_draft_seed_content` and `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds` so that a rematerialized draft does not read as drifted. A changed accepted store or hosting row changes the rendered stack when the draft is rematerialized. A draft that is not rematerialized after the accepted version changes keeps its older stack; detecting that is left to the existing draft digest and rematerialization, an accepted limit, and the version id in the section lets the reader see which accepted version the stack came from.

**Carrying the stack through `create` and `detail`.** `Stack` is added to the existing guardrail-section mechanism: `GUARDRAIL_BODY_SECTIONS` in `plan_tool/scope_fence.py`, the optional plan-body section shapes and capture and render sites in `plan_tool/create.py`, and the section lists in `plan_tool/prompts/synthesize-body.md` and `plan_tool/prompts/distill-seed.md`. `create` captures the seed's `## Stack` before distillation can replace the seed, renders it verbatim over any model output, and the scope fence threads it into detail prompts. A reused mechanism is deliberate: a second copy path would duplicate the capture, the override, and the fence. `plan_tool/create.py:_load_roadmap_research_targets` keeps supplying product research and is not a second stack source.

**The audit is the contradiction check.** The per-plan completeness audit already inventories commitments and traces each through every step and detail file, and already treats the guardrail sections as authoritative. `plan_tool/prompts/plan-audit.md` adds `## Stack` to that list and a settled store or hosting product to its commitment kinds, so a step or detail file that persists to SQLite beside a carried PostgreSQL row is a finding in the saved report. Conflict surfacing inside `create` and `detail` is deliberately not built (decided 2026-10-08): recognizing that a model's own design contradicts a stack is a semantic judgment the tool cannot observe, the only checkable fact is that the seed's `## Stack` equals the accepted rows, and the audit is where the codebase already puts model-judged checks. A deterministic comparison of technology names is likewise not built: it would measure vocabulary rather than the property. The audit stays advisory.

**Source of the carried stack.** The seed's rendered stack section is the single source `create` reads. A seed without that section carries nothing, so its plan has no stack commitment; there is no fallback to the accepted version.

**Stop / defer.** A stack choice the accepted roadmap cannot express is surfaced without inventing a technology. Unrelated defects are routed separately.

## Input

The accepted roadmap already defines the stack: the constraints gates require one hosting row per facet (`compute`, `model`, `topology`), and every component names its store rows, each with a category and an optional `product`. The loss happens at seed materialization. `roadmap-seed.md` asks the seed to bind its domain rows, constraints, and assumptions — not its hosting or store rows — and leaves storage schemas to `create` and `detail`, so a draft seed names `store-app-db` by id without its content, and `create`, grounding against a repository with no database, chooses its own.

## References

- [dataclasses — Data Classes (Python 3 standard library)](https://docs.python.org/3/library/dataclasses.html) — Covers frozen dataclasses, field defaults and equality semantics, which you need when rendering HostingRow and store rows, including an optional product, into a deterministic stack section.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Explains safe_load/safe_dump and how YAML values map to Python types, for reading accepted-version frontmatter and emitting stack rows whose missing product must stay explicit rather than null.
- [YAML Ain't Markup Language Specification 1.2.2](https://yaml.org/spec/1.2.2/) — The primary YAML spec for null, empty-scalar and quoting rules, so an absent product is told apart from an unfixed one when the stack is rendered or parsed.
- [CommonMark Spec — Fenced code blocks and ATX headings](https://spec.commonmark.org/current/) — Defines line-anchored headings and fenced blocks, so a rendered stack section in model-authored draft text is marked structurally and passes draft-seed validation and identity classification.
- [pytest: How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Shows parametrized tests for the verification matrix: rows with and without product, changed accepted rows on rematerialization, and advisory conflicts that never block.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Reference for the content hashing behind draft-seed identity, to check that a changed accepted store or hosting row changes the rendered stack's fingerprint while an unchanged one does not.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Out of scope / Non-goals:** requiring hosting input in the brief, emitting a hosting question, owner-provenance tracking on hosting rows, and an "inapplicable hosting" answer — deliberately not built: the hosting gates already guarantee a defined stack, and clarifying a vendor or runtime (e.g. whether Integration targets AWS) is roadmap content settled through the existing feedback lifecycle (decided 2026-10-08). Also out: conflict surfacing, notes, or technology-name comparison inside `create` and `detail` (deliberately not built, decided 2026-10-08; the plan audit is the contradiction check); carrying `## Stack` into the Jira handoff, whose section list is a whitelist that omits it; a cross-plan audit of derived plans against the roadmap (BACKLOG.md #462); new hosting facets, values, or a provider field; a dedicated stack or foundation plan workflow; review-aid rendering; cloud provisioning or infrastructure configuration; correcting existing Integration plans or drafts.

## Risks

- Drafts and promoted seeds written before this change lack the stack section until rematerialized, and a promoted seed rewritten after it carries the section; plans already derived from the earlier text, such as Integration's `2-connector-registry-seed.md`, keep their current text.
- A draft that is not rematerialized after the accepted version changes keeps its older stack, and `create` carries it as settled; the version id in the `## Stack` section makes the source visible, and detecting staleness is left to the existing digest and rematerialization.
- The audit is model-judged and advisory: it may miss a contradiction or flag a false one, and a finding needs a reader to act. The replay in step 3 is the only evidence of its reach and gates nothing.
- Adding a fourth guardrail heading touches every site that enumerates the three, and tests that pin the three-heading order go red until updated; the sweep is part of step 2, not follow-up work.
- A rendered section inside model-authored draft text must survive draft-seed validation and identity classification, or every rematerialized draft would read as drifted.

## Testing

- **Verification:** replay the Integration case — the `connector-registry-seed` draft's `## Stack` names PostgreSQL for `store-app-db` and the managed-containers hosting, `create` preserves that section verbatim in the plan body, and the `detail` fence carries it. Whether a real model still reaches for SQLite is observed separately and gates nothing. The audit prompt carries `## Stack` as an authoritative section and a settled technology choice as a commitment kind (asserted by key), and a Integration-style plan replayed through `completeness-audit` is recorded in this plan's handoff as an observation. A row without `product` renders it explicitly as not fixed. A changed accepted store or hosting row changes the rendered stack on rematerialization. A plan row with no components renders the hosting rows alone. A seed with no `## Stack` carries nothing. Existing draft-seed validation, hosting gates, and the guardrail-section tests, updated for the added heading, stay green.

## Acceptance criteria

- **Verification:** replay the Integration case — the `connector-registry-seed` draft's `## Stack` names PostgreSQL for `store-app-db` and the managed-containers hosting, `create` preserves that section verbatim in the plan body, and the `detail` fence carries it. Whether a real model still reaches for SQLite is observed separately and gates nothing. The audit prompt carries `## Stack` as an authoritative section and a settled technology choice as a commitment kind (asserted by key), and a Integration-style plan replayed through `completeness-audit` is recorded in this plan's handoff as an observation. A row without `product` renders it explicitly as not fixed. A changed accepted store or hosting row changes the rendered stack on rematerialization. A plan row with no components renders the hosting rows alone. A seed with no `## Stack` carries nothing. Existing draft-seed validation, hosting gates, and the guardrail-section tests, updated for the added heading, stay green.

- **Case ownership:** open-product wording, rematerialization with a changed row, the no-components and cross-cutting cases, replacement of a lookalike `## Stack`, and draft-seed validation and identity are tested in step 1; verbatim preservation through create, presence in the detail fence, the absent-section case, and the sweep of every guardrail-heading site in step 2; the audit prompt's two additions and the recorded replay in step 3; step 4 documents and reconciles.

## Deferred

- **Roadmap stack collection and its publish and candidate-review callouts (BACKLOG.md #461):** this is a separate backlog entry that builds on the renderer this plan delivers. It stays deferred until this plan ships.
- **Cross-plan audit of derived plans against the accepted roadmap (BACKLOG.md #462):** a separate backlog entry that depends on the `## Stack` section this plan delivers.
