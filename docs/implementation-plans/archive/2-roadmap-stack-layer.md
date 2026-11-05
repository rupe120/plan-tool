> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Roadmap Stack Layer
intent: A roadmap records its technology stack as a distinct concern layer — each
  stack concern either chosen or explicitly open — and that layer is called out to
  the reviewer at first publish and in every candidate review, so a stack choice or
  an open stack question reaching acceptance by a first run or a candidate is never
  unseen; hand enrollment is deliberately excluded.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-stack-layer.md
steps:
- id: 1
  title: Add the `stack` collection to `02-constraints.md` parsing and rendering in
    roadmap_artifacts.py, keeping a missing collection distinct from an empty one
    so versions without it re-render byte-identically
  intent: Gives each stack concern (deployment platform, store engine, language/runtime)
    one typed home with a choice or an explicit `open`, while every accepted version
    that predates the collection still parses as 'stack not recorded' and keeps its
    stored bytes and digests.
  files:
  - plan_tool/roadmap_artifacts.py
  - tests/test_roadmap_artifacts.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-stack-layer/01-stack-collection-02-constraints-md.md
  status: done
- id: 2
  title: 'Add stack gates: totality over the three concerns in the constraints gate
    set, binding any artifact that carries the collection; unknown-concern, duplicate-id,
    and row-state reports; and stack ids added to the decision-anchor union and to
    the identity rows that feedback, continuity, and the duplicate-id check read'
  intent: 'Makes any artifact carrying the collection refuse a missing concern while
    accepting `open`, so a candidate cannot introduce a partial or empty stack, and
    never refuses an artifact for lacking the collection, on any envelope path. A
    first run that omits the stack is accepted and shown as "stack not recorded".
    Stack rows are the authority for their concerns, and no gate compares a stack
    row with a hosting or store `product`. Stack rows are identity rows and decision
    anchors but not prose-inventory rows: they stay out of `_constraints_rows`, which
    also feeds the prose-inventory gate and `design_row_ids`. The components stage
    needs no gate of its own: it resolves anchors through the same union, so the stack
    term there is the whole components-side change.'
  files:
  - plan_tool/roadmap_gates.py
  - tests/test_roadmap_gates.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the parsed stack row type and the present-versus-absent collection distinction
      the gates key on
  detail: docs/implementation-plans/plan-details/roadmap-stack-layer/02-stack-gates-totality-over-three.md
  status: done
- id: 3
  title: 'Make stack rows feedback targets and revisable through candidates: register
    the collection in the stage-row policy, the candidate and revision row-type maps,
    the revision patch, and the candidate-delta selector prompt, with the concern
    field fixed, rows addable so a candidate can introduce the stack, and no row removable'
  intent: Lets an existing roadmap gain or revise its stack through the ordinary feedback
    and candidate lifecycle, never through regeneration, as the acceptance round-trip
    requires. This step owns the refusal to remove a stack row. A candidate is a set
    of row operations on its predecessor, no operation drops a collection key, and
    emptying the collection requires removing every row, which the stage-row policy
    (`allow_remove=False`) refuses.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_candidate.py
  - plan_tool/roadmap_candidate_run.py
  - plan_tool/roadmap_candidate_context.py
  - plan_tool/roadmap_revision.py
  - plan_tool/roadmap_revision_patch.py
  - plan_tool/prompts/roadmap-candidate-delta-selector.md
  - tests/test_roadmap_candidate.py
  - tests/test_roadmap_candidate_run.py
  - tests/test_roadmap_revision.py
  - tests/test_roadmap_revision_patch.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: the stack row type and collection key to register
    2: the gates a revised candidate must pass, including totality once the collection
      exists
  detail: docs/implementation-plans/plan-details/roadmap-stack-layer/03-make-stack-rows-feedback-targets.md
  status: done
- id: 4
  title: Teach the constraints stage prompt to author one stack row per concern, recording
    `open` when the brief leaves a concern undecided and never inventing a vendor,
    with a Integration-brief replay under the invoker seam
  intent: 'Makes a brief that says ''not decided'' leave a recorded `open` concern
    instead of no trace or an invented choice such as PostgreSQL, while the existing
    ban on inventing hosting vendors still holds. The replay shows only what a stubbed
    backend can: canned output with `open` clears the gates and renders, and the prompt
    carries the open-versus-invented-vendor instruction. Real-model behavior on the
    Integration brief is observed separately and gates nothing.'
  files:
  - plan_tool/prompts/roadmap-constraints.md
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: the stack row field names and the `open` spelling the prompt must restate
    2: the gates a replayed constraints response must clear
  detail: docs/implementation-plans/plan-details/roadmap-stack-layer/04-teach-constraints-stage-prompt-author.md
  status: done
- id: 5
  title: Show the full stack, with open and pending concerns listed separately, in
    the first stage run's completion output and in the generated INDEX.md, both fed
    by the new `plan_tool/roadmap_stack_summary.py` as the single producer of the
    stack summary (the INDEX.md atomic rewrite is kept and now includes the stack
    section)
  intent: Makes sure no stack choice or open stack question reaches acceptance unseen
    through a first run, which publishes without candidate review, and shows 'stack
    not recorded' for versions that lack the collection.
  files:
  - plan_tool/roadmap_index.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap_index.py
  - tests/cli/test_roadmap_cmd.py
  creates:
  - plan_tool/roadmap_stack_summary.py
  - tests/test_roadmap_stack_summary.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: the parsed stack rows and the absent-collection state to summarize
    2: stack ids as decision anchors, which is how a pending concern is identified
  detail: docs/implementation-plans/plan-details/roadmap-stack-layer/05-show-full-stack-open-pending-concerns.md
  status: done
- id: 6
  title: Show the current stack, and the stack rows a candidate adds, changes, or
    opens, at every candidate review print site next to the narrative evidence, listing
    each stack choice beside the hosting and store `product` values it was reviewed
    with, without touching approval refusal
  intent: Makes every candidate review show the reviewer the stack, the stack delta,
    and the recorded `product` values side by side, while guaranteeing that the callout
    never becomes a narrative-evidence defect class or an approval block. The summary
    displays and does not compare.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/roadmap_stack_summary.py
  - tests/cli/test_roadmap_cmd.py
  - tests/test_roadmap_stack_summary.py
  - tests/test_roadmap_candidate_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 5
  depends_on_notes:
    3: candidates that can add, change, or open stack rows
    5: the shared stack summary to extend with a predecessor-to-candidate delta
  detail: docs/implementation-plans/plan-details/roadmap-stack-layer/06-show-current-stack-stack-rows-candidate.md
  status: done
- id: 7
  title: 'Render the stack collection in materialized draft seeds next to #460''s
    hosting and store section (the draft and promoted-seed overwrites #460 owns stay
    as they are, now writing the stack-bearing text)'
  intent: 'Makes a plan derived from the roadmap see the chosen and open stack concerns,
    including language/runtime, as settled input. This step extends the `## Stack`
    renderer #460 shipped (`_render_stack_section` in `plan_tool/roadmap.py`).'
  files:
  - plan_tool/roadmap.py
  - plan_tool/prompts/roadmap-seed.md
  - tests/test_roadmap.py
  - tests/test_roadmap_seed_manifest.py
  complexity: low
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the parsed stack rows and the absent-collection state to render
  detail: docs/implementation-plans/plan-details/roadmap-stack-layer/07-render-stack-collection-materialized.md
  status: done
- id: 8
  title: 'Document the stack collection, its gates, its feedback operations, and its
    callouts in ROADMAP_FORMAT.md and ROADMAP_FEEDBACK_FORMAT.md, record the new summary
    module in docs/ARCHITECTURE.md, and mark BACKLOG.md #461 as plan-authored until
    full shipment'
  intent: 'Keeps the schema references and the backlog accurate to what ships. Any
    doc example of `02-constraints.md` must still parse and pass the gates, and #461
    is removed only once the whole plan has shipped.'
  files:
  - ROADMAP_FORMAT.md
  - ROADMAP_FEEDBACK_FORMAT.md
  - docs/ARCHITECTURE.md
  - BACKLOG.md
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  depends_on_notes:
    1: the landed field names and the absent-versus-empty rule
    2: the gate names and the version-compatibility rule
    3: the stack rows' feedback-target and candidate operation policy
    5: the first-run and INDEX.md callout shape
    6: the candidate-review callout and delta shape
  detail: docs/implementation-plans/plan-details/roadmap-stack-layer/08-document-stack-collection-its-gates-its.md
  status: done
---
# Roadmap Stack Layer

## Overview

A roadmap records its technology stack as a distinct concern layer: a `stack` collection in `02-constraints.md` with one row per required concern (deployment platform, store engine, language/runtime), each holding a choice or an explicit `open`. The stack is shown to the reviewer in the first stage run's completion output, in the generated `INDEX.md`, and in every candidate review. That way no stack choice and no open stack question reaches acceptance, by a first run or a candidate, without being seen. Hand enrollment of an older folder is deliberately excluded: it has no callout site, and an enrolled folder that already carries a stack is shown by the next `INDEX.md` write or candidate review. The callout is a standing summary and never blocks approval. An existing roadmap gains its stack through the ordinary feedback and candidate lifecycle, never by regeneration. Source: BACKLOG.md #461.

## Problem statement

Stack facts have no single home today. Hosting rows in `02-constraints.md` record vendor-neutral categories with an optional compute `product`. These rows are identity-only: they are never decision anchors or prose-inventory rows, and they have no undecided value. Store rows in `03-components.md` carry an optional `product`. Language and runtime are recorded nowhere. The constraints prompt (`plan_tool/prompts/roadmap-constraints.md`) forbids inventing a vendor or a pending hosting decision, so a brief that explicitly says "not decided" has nowhere to put that fact.

Observed 2026-10-08 in Integration (`integration-aidlc-mvp`): the brief says "No AWS account or specific service is fixed yet" and names only "a relational store". The accepted roadmap:

- records `managed-containers` without a product;
- gives no trace that the vendor is open;
- introduces PostgreSQL, which the brief does not name;
- carries zero pending decisions.

The plan derived from that roadmap chose Python. The roadmap entered versioning when an older folder was enrolled by hand (2026-09-21). Neither hand enrollment nor a first stage run (which publishes the root version once all four stages pass) goes through candidate review. Candidate review's narrative evidence reports only removed ids still named in prose. So stack choices and open stack questions reach acceptance without the reviewer ever seeing them.

## Architecture

**The `stack` collection.** `02-constraints.md` gains a `stack` collection with one row per required concern: deployment platform, store engine, and language/runtime. Each row carries either a choice or an explicit `open`. The ledger addresses design rows only, so a stack row is never a reviewer-feedback target; a decision can anchor to one, and pending-ness is derived from decisions anchored to a row and is never stored on it (see Open and pending). The collection sits alongside the existing constraints rows (`ConstraintsArtifact`, `HostingRow`, `stage_row_collections`, `_STAGE_ROW_OPERATION_POLICIES` in `plan_tool/roadmap_artifacts.py`). It is deliberately not a fifth roadmap artifact: stack choices are constraints, and the four-member version layout runs through every roadmap surface (decided 2026-10-08).

**One source of truth.** Stack rows are the authority for deployment platform, store engine, and language/runtime. Hosting `product` and store `product` fields stay as authored, and no gate compares them with a stack row (a stack-versus-`product` agreement gate is deliberately not built, decided 2026-10-08: agreement would make two places hold the same fact). The candidate-review stack summary shows each stack choice beside the hosting or store `product` values recorded in the same candidate, and does not judge whether they differ: no comparison rule is defined, because a vendor-name comparison would need a vocabulary this plan bans and would measure wording rather than the property. It never refuses a candidate. An existing roadmap such as Integration's, whose store row already carries a PostgreSQL `product`, gains its stack when a candidate introduces the collection.

**Open and pending.** A stack row is either `open`, when the brief leaves the concern undecided and the row carries no choice, or chosen, when it carries a choice. Pending-ness is a fact about decisions: a decision anchored to a stack row's id with status `pending`, in the constraints, components, or plans artifact, makes that row pending (the domain stage runs before any stack row exists, so its decisions cannot anchor to one). The two facts are independent, so a row may be both `open` and pending, and appears in both lists; the gate accepts a decision anchored to an `open` row. A candidate moves a row between `open` and chosen. The first-run output and `INDEX.md` list `open` concerns and pending rows as two separate lists; the candidate-review summary shows the added, changed, and opened rows instead.

**Totality and version compatibility.** A totality gate sits next to `check_hosting_totality` in the constraints gate tuple (`plan_tool/roadmap_gates.py`). It refuses an artifact that is missing a required concern, accepts a concern recorded as `open`, and reports an unknown concern, a duplicate id, a second row for a concern that already has one (a duplicate concern, so one row per required concern holds), and a row that is not exactly one of chosen or `open`; the stack gate, not the parser, owns that rule. Totality binds any artifact that carries the `stack` collection, so a present but partial or empty collection is refused, including one a candidate introduces. Absence never binds, on any envelope path (first run, resumed first run, below-stage re-gating, revision gates, candidate narrative evidence, the impact snapshot), so the gate needs no envelope field and no first-run signal. A first run whose constraints omit the collection is accepted, and the first-run output and `INDEX.md` show it as "stack not recorded", so the omission is seen rather than blocked; the constraints prompt (step 4) is what teaches the model to author the stack. Forcing authoring by refusing a first run is deliberately not built (decided 2026-10-08): the mechanism drew four consecutive audit findings about when absence binds, and a visible "not recorded" marker meets the Outcome without it. A version without the collection reads as "stack not recorded", never as an empty stack. A candidate in a lineage without the collection is not refused for that absence, so unrelated feedback on an existing roadmap keeps working until some candidate introduces a complete stack. Stack rows are identity rows and decision anchors but not prose-inventory rows. Their ids get an explicit stack term in the decision-anchor union both stages resolve against (`_envelope_rows`), which is the only components-side change, and in the identity rows that feedback targets, removal continuity, and the global duplicate-id check read (`_constraints_identity_rows`, `_envelope_identity_rows`). They stay out of `_constraints_rows`, which also feeds the prose-inventory gate and `design_row_ids`: a stack row carries its own `choice` or `open` marker, so it needs no prose naming, as with hosting rows. Stack rows can be added but not removed, as with hosting rows, so a candidate can never turn a recorded stack back into "stack not recorded".

**Constraints-stage authoring.** The constraints prompt records chosen and open concerns. When the brief leaves a concern open, the prompt records `open` instead of inventing a choice. Loosening the prompt for stack concerns must not let the model invent a vendor the brief leaves open.

**Callouts.** The stack is shown in two places:

- The first stage run's completion output and the generated `INDEX.md` (`plan_tool/roadmap_index.py:write_roadmap_index`) list the full stack, with open and pending concerns listed separately.
- Every candidate review (`plan_tool/roadmap_candidate_review.py`, `plan_tool/roadmap_candidate_narrative.py`) shows the current stack and what that candidate adds, changes, or opens.

Both callouts are produced by one new module, `plan_tool/roadmap_stack_summary.py`, the single producer of the stack summary, its `open` and pending lists, and the candidate delta. Hand enrollment of an older folder is not a callout site: an enrolled version without the collection shows "stack not recorded", and the stack first reaches review through the candidate that introduces it. The callout is a standing summary, not a narrative-evidence defect class, and it never blocks approval.

**Seed rendering.** Seed materialization (#460) renders the stack collection alongside hosting and store rows. #460's renderer has shipped (`_render_stack_section`, `roadmap-stack-propagation`), so step 7 extends it and no ordering condition remains between #460 and this plan. Step 7 adds a `### Technology stack` sub-part after `### Hosting` and `### Stores` inside the tool-owned `## Stack` section: one line per row in source order, `open` rows marked "open — not decided", and one explicit line each for a `None` stack ("stack not recorded for this roadmap version") and an empty one ("stack collection present and empty"). The seed-rendering test and the `roadmap-seed.md` wording use these names.

**Documentation.** `ROADMAP_FORMAT.md` (the `02-constraints.md` schema, § "Hosting facets and values", § "Narrative review evidence", root-version publication) and `ROADMAP_FEEDBACK_FORMAT.md` (feedback targets and the candidate lifecycle) describe the collection.

**Backlog reconciliation.** While execution is pending, BACKLOG.md #461 is marked plan-authored. When the work ships, the plan reconciles that entry: it is removed only after full shipment, and any separately deferred follow-up is kept.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — Covers frozen dataclasses, field defaults, and `replace()`, for when you add a stack-row type next to `HostingRow` in the constraints artifact model.
- [enum — Support for enumerations (Python 3.13)](https://docs.python.org/3.13/library/enum.html) — Covers `Enum` and `StrEnum`, for when you model the closed set of required stack concerns and the chosen/open/pending states.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Covers `safe_load` and how YAML maps to Python types, for when you parse and validate the new `stack` collection in `02-constraints.md` frontmatter.
- [YAML Ain't Markup Language (YAML) Version 1.2.2](https://yaml.org/spec/1.2.2/) — The YAML spec, for checking how values like `open` or `null` are read so that an explicit `open` is never confused with a missing value.
- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Covers `@pytest.mark.parametrize` and `pytest.param` ids, for the parametrized test over version-compatibility cases and the totality-gate cases.
- [How to monkeypatch/mock modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Covers the `monkeypatch` fixture, for stubbing the invoker seam in the Integration-brief replay so the test never starts a real backend.
- [CommonMark Spec](https://spec.commonmark.org/current/) — The CommonMark spec for headings, lists, and tables, for when the stack callout is rendered into the generated `INDEX.md` and the candidate-review markdown.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Out of scope / Non-goals:** a fifth roadmap artifact — deliberately not built, since the four-member version layout runs through every roadmap surface and stack choices are constraints (decided 2026-10-08); stack concerns beyond the three named; a closed vendor or product vocabulary; a narrative-evidence defect class or any approval block on stack content; judging whether a choice is good; Integration's HTML review aid, which follows this work separately in Integration; regenerating or rewriting existing accepted versions.

## Risks

- Existing accepted versions lack the collection; reading them as an empty stack, or refusing their candidates for the absence, would break every current roadmap lineage.
- Hosting `product`, store `product`, and stack rows can state the same fact twice; stack rows are authoritative, no gate compares them, and candidate review lists them side by side for the reviewer to read.
- The constraints prompt currently forbids pending hosting decisions; loosening it for stack concerns must not let the model invent a vendor the brief leaves open.
- Review callouts that grow into approval blocks would turn a summary into a gate on stack content.

## Testing

- Parse and gate tests for the `stack` collection: an artifact carrying the collection and missing a required concern is refused, a concern recorded as `open` is accepted, and an unknown concern or duplicate id is reported.
- A parametrized test over the version-compatibility cases: a version without the collection reads as "stack not recorded", and an unrelated candidate in that lineage is not refused for the absence.
- Callout tests that assert keys rather than words: first-run output and `INDEX.md` list open and pending concerns separately; a candidate review shows the stack and the added, changed, or opened rows; a review callout never changes whether approval is blocked.
- A feedback round-trip test: a stack row is targeted by feedback and revised through a candidate.
- A constraints artifact with no `stack` collection is accepted on every envelope path (first run, resumed first run, below-stage re-gating, revision gates, candidate narrative evidence, the impact snapshot), and the first-run output and `INDEX.md` show "stack not recorded" for a first run that omitted it. No envelope field or first-run signal exists.
- A candidate that introduces a partial stack, or an empty `stack` collection, is refused; a stack row cannot be removed through a candidate, which is what keeps a recorded stack from reverting to "stack not recorded"; a candidate that introduces a complete one is accepted.
- A stack row needs no prose naming and is not a design-row id; a decision anchored to a stack row id is accepted; a stack id colliding with another artifact's id is reported once; a second stack row for an already-present concern, under a different id, is reported as a duplicate concern; a stack row carrying both `choice` and `open`, or neither, is reported; a candidate cannot remove a stack row or the collection; a pending decision in `03-components.md` anchored to a stack row appears in the pending list.
- A decision anchored to an `open` stack row is accepted, and the row is listed in both the `open` and pending lists.
- A Integration-brief replay under the invoker seam, never a real backend: canned output recording the deployment platform as `open` clears the gates and renders, and the constraints prompt carries the open-versus-invented-vendor instruction (asserted by key). Real-model behavior on the Integration brief is a separate observation that gates nothing.
- A candidate-review test: the summary lists a stack choice beside the hosting and store `product` values recorded with it, and does not change whether approval is blocked.
- A draft-seed test: a materialized draft renders the stack collection, including `open` concerns, next to #460's hosting and store section.
- Existing hosting gate and candidate-review evidence tests stay green.

## Acceptance criteria

- **Verification:** under the invoker seam, canned Integration-brief output recording the deployment platform as `open` clears the gates, every required concern is chosen or `open`, and the prompt carries the instruction not to invent a vendor; first-run output and `INDEX.md` list open concerns separately; a candidate that opens, adds, or changes a stack row shows that delta in review; an accepted version without the collection reads and renders as "stack not recorded", and an unrelated candidate in that lineage is not refused for the absence; a stack row can be targeted by feedback and revised through a candidate; a candidate introducing a partial or empty stack is refused, and a constraints artifact without the collection is accepted on every envelope path, with a first run that omitted it shown as "stack not recorded"; a decision anchored to an `open` row is accepted and the row appears in both lists; the review summary shows each stack choice beside the recorded `product` values and never blocks; a materialized draft seed renders the stack once #460's step 1 has landed; existing hosting gates and candidate-review evidence stay green.

## Deferred

- **Stop / defer:** surface a stack concern the collection cannot express or a conflict with an accepted hosting or store choice without inventing one; route unrelated defects separately.
