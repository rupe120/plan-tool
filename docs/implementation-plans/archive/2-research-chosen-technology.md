> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Research Chosen Technology
intent: '`create`''s web research is grounded in the technologies the plan actually
  uses, and `create` refuses to proceed when it cannot ground one and no operator
  description exists.'
status: completed
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/research-chosen-technology.md
steps:
- id: 1
  title: Preserve operator descriptions and research-disclosure decisions on hosting
    and store rows
  intent: Give operators a recorded local fallback and require explicit consent before
    a product name may leave the repository for research.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_revision.py
  - plan_tool/prompts/roadmap-constraints.md
  - plan_tool/prompts/roadmap-components.md
  - ROADMAP_FORMAT.md
  - tests/test_roadmap.py
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap_revision.py
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/research-chosen-technology/01-preserve-optional-operator-descriptions.md
  status: done
- id: 2
  title: Select a tracked roadmap source and request source evidence for every recorded
    product row
  intent: Make create research exactly the products recorded by the source roadmap,
    preserving a row's local origin, fallback description, disclosure decision, and
    repeated product names.
  files:
  - plan_tool/create.py
  - plan_tool/cli/authoring.py
  - tests/test_create.py
  - tests/cli/test_direct_cmd.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides parsed and revision-safe operator descriptions beside each product.
  detail: docs/implementation-plans/plan-details/research-chosen-technology/02-select-tracked-roadmap-source-request.md
  status: done
- id: 3
  title: Refuse an ungrounded roadmap product before publication and retain its retry
    checkpoint
  intent: Stop create from presenting plausible guesses as researched guidance when
    a chosen technology cannot be grounded, without discarding the already-proposed
    plan.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Provides the selected roadmap snapshot and per-row source verdicts the refusal
      evaluates and reports.
  detail: docs/implementation-plans/plan-details/research-chosen-technology/03-refuse-ungrounded-roadmap-product.md
  status: done
- id: 4
  title: 'Mark BACKLOG #244 resolved only after the description, research, and refusal
    changes ship'
  intent: Keep the roadmap backlog accurate without closing the work before its behavior
    and tests are complete.
  files:
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: Ships the operator-description artifact contract.
    2: Ships roadmap-grounded research inputs.
    3: Ships the tested hard refusal.
  detail: docs/implementation-plans/plan-details/research-chosen-technology/04-mark-backlog-244-resolved-only-after.md
  status: done
---
# Research Chosen Technology

## Overview

Four changes to `create`'s existing research phase:

- **Select the real inputs.** A `--from-existing` source that resolves through
  the roadmap seed-state sidecar binds `create` to that roadmap's current
  `hosting:` and `stores:` rows. Other create origins retain the existing
  title/seed-prose research path unchanged.
- **Ask for evidence per recorded row.** Research receives only a stable token
  and named product literal for targets explicitly marked `external`; field
  origin, optional description, and every local/unmarked product stay local for
  diagnostics and refusal. It returns a source verdict for that target rather
  than one untagged batch.
- **Fail closed on disclosure.** `research_disclosure: external` is the only
  per-row permission for an outbound product query. Missing or `local` values
  take a local description-backed route; a local row without a nonblank
  description refuses before research.
- **Refuse, naming what failed** — the technology and the field that named
  it — unless that row carries an operator `description`. Step 1 supplies that
  field and the disclosure decision on the hosting/store schema and preserves
  both through revisions.

## Problem statement

`plan_tool/create.py:_build_research_context` builds the research description
from the plan **title plus step titles**, and `_prepare_create_plan` calls it
whenever no source text is available. No technology choice reaches it.

**Measured, 2026-08-07.** `world-foundation`'s `References` cited `sqlite3`
and PEP 249 as "useful when defining the single world-scoped
repository/session boundary that mediates all reads and writes" — while all
six of its code steps keep every store an in-process stand-in and none
imports `sqlite3`. The research phase had nothing to ground on, so it
produced plausible documentation for a persistence layer the plan does not
build. The detail-grounded audit caught it as `persistence-references`
(MEDIUM); a reader would not have, because `References` is trusted precisely
*because* it looks researched.

**The contrast is the same machinery with better inputs, one run apart.** The
`roadmap-hosting-and-stores` seed named AWS explicitly, and that run's
research returned the Lambda execution-environment lifecycle (which became
the factual basis for a gate rather than an assertion), the AWS
Well-Architected SaaS Lens tenancy models, a multi-tenant storage-partitioning
whitepaper, Azure's independent tenancy taxonomy as a neutrality check, and
12-Factor's stateless-process statement. Nothing about the phase changed —
only what it was told to research.

**Why vendor services are the worst case.** They are fast-moving, frequently
renamed, and full of near-homonyms — Aurora Serverless v1 versus v2, DSQL,
Lambda SnapStart — where a model's confident wrong answer is indistinguishable
from a right one, and where the wrongness surfaces at implementation time
rather than review time.

## Architecture

**The refusal is the feature; the research quality is not checkable and is
not checked.** The gate keys on one binary fact per named technology: the
research step returned at least one source, or a non-empty operator
`description` is present. Nothing asserts the sources are good, current,
relevant, or actually about the technology named. That boundary is the whole
reason this can ship as a gate at all — see CLAUDE.md § "Validating a semantic
property you cannot observe", whose rule is to assert a binary fact about
state, deliver the rest, and enumerate what may not be checked.

**A hard stop, decided 2026-08-07 — do not soften to a warning.** Research
returning nothing usable blocks, names the technology and the field that named
it, and tells the operator what to add. Warn-and-continue was weighed and
rejected: it re-opens the exact silent-invention path this closes, and an
advisory on a channel operators already skim is not a fence. The refusal must
behave identically on non-interactive stdin — a Claude session auto-driving
gets the same error, never a prompt it cannot answer.

**A technology with no public documentation is the case the description
exists for, not an edge case to engineer around.** Something brand-new,
internal, or proprietary legitimately has none; that is precisely when writing
down what it is and how to use it properly is worth the operator's time. The
plan's job is to make supplying it cheap and to not discard work already done
in the same run — not to widen the gate.

**Outbound disclosure is an explicit row decision.** A hosting or store row
may set `research_disclosure: external` only when its product literal may leave
the repository for web research. `local` and an omitted disclosure fail closed:
they never render that literal into a research prompt and instead require a
nonblank local description. This is not a quality assessment of a description;
it is a boundary on which data may leave. A selected local row with no
description errors before any research call, naming the field and asking for a
description or explicit external disclosure.

**Scope of the new product-research path.** Only technologies named in a
**recorded field** receive a per-target source verdict and gate. A technology
mentioned only in prose is out of that path — prose mining is unbounded and
would turn every incidental noun into a blocking question. The existing generic
References search still reads seed prose on every legacy route, including a
tracked roadmap with no named product; it creates no product target or verdict
and never triggers this refusal.

### Source selection and research records

The roadmap branch is selected only when the `--from-existing` path resolves
through `locate_tracked_seed` against the initially resolved repository root.
`cmd_create` resolves that `TrackedSeedLocation` once, passes the exact
location to stale-seed confirmation, and then carries it through any
seed-driven `find_umbrella_root` relocation into `create`. No later helper
locates the marker or sidecar again, so a changed locator cannot make
confirmation approve one roadmap while research reads another. Relocation
changes where the new plan publishes, not which accepted roadmap the seed
belongs to.
`create` derives one immutable input snapshot from that sidecar's roadmap root:
the parsed `02-constraints.md` hosting rows followed by the parsed
`03-components.md` store rows. A `product` is named only when
its trimmed value is non-empty; `null`, empty, and whitespace-only values are
absent and produce no target. Each named product produces one target with a
stable token, its trimmed product string, exact local origin, optional
`description`, and disclosure decision. The origin contains the artifact path,
collection, and source-order position as well as the row id, so duplicate row
ids remain separate and diagnosable.
The two artifacts must be readable and parseable before research starts; a
bad tracked-roadmap input fails before publication with its path and does not
silently fall back to seed prose.

An inline `--from`, the interactive path, and an untracked `--from-existing`
path do not select this branch. Their research prompt, checkpoints, rendered
References, and publication behavior remain unchanged. A roadmap branch with
no named products makes that unchanged generic References call, but creates no
target record and runs no refusal. The selection therefore never mines prose
to create a product target or infers a roadmap from a filename.

Only external targets enter the external request, which carries each target
token and product literal. It never includes an operator description, origin,
row metadata, roadmap path, sidecar path, raw artifact, or local/unmarked
product; those values remain local for cache identity, diagnostics, and the
refusal. A selected local/unmarked target with a nonblank description produces
its local no-source result without invoking research. The reference protocol
returns one record for every requested external target. Each record contains either one or more
decoded `Reference` values or an explicit empty source list. Every member of a
non-empty list must satisfy the existing Reference title, URL, and description
shape; an invalid member is a research-protocol failure, not an empty verdict.
Missing, duplicate, or foreign target records, and an unparseable response,
are also research-protocol failures before publication; they are not evidence
that a product has no public source. Repeated product strings and duplicate row
ids remain separate target records: a source for one source-order position
never clears another row's verdict or fallback.
The existing References renderer receives the flattened returned references
without changing their body location or judging their quality.

### Zero-source References disclosure

When every selected result is source-free—an external target returned an
explicit empty list or a local target produced its local result—and step 3
admits every target through its own nonblank description, `References` renders
this fixed disclosure instead of a seed block or `_(TODO)_`: “No external references
were returned for the selected roadmap products; publication proceeds under
their recorded operator descriptions.” It is a truthful state marker, not a
Reference entry and not evidence that a description is authoritative. A
selected result with at least one decoded Reference retains the ordinary
flattened References list; untracked and no-product routes retain their current
seed/placeholder behavior.

### Description and revision contract

`HostingRow` and `StoreRow` each carry an optional `description`. Absent or
whitespace-only descriptions mean no fallback; any non-empty value is accepted
without a format, length, freshness, authority, or quality judgment. Parsers,
renderers, and the closed stage-revision payload models preserve the field. An
`edit-row` payload that omits `description` retains the existing value; an
explicit `description: null` clears it. In particular, a revision that edits
another property of a hosting or store row does not delete its description by
omission.

`research_disclosure` is optional on the same rows and is either `external` or
`local`; omission behaves as `local`. It carries no product-quality judgment.
An `external` value is explicit permission to send only that row's trimmed
product literal to the research invoker. A local or unmarked row needs a
nonblank description before creation can proceed. Parsing, rendering, and
full-row stage revision preserve the setting; omission in an edit retains it,
while explicit `null` clears it back to the local default.

### Refusal, checkpoint, and iteration contract

Before the first publication, every selected target passes when its own record
has at least one decoded source or its own row has a non-empty description.
Otherwise `create` exits non-zero, names the product and exact field origin,
and tells the operator to add a description or repair the source. The check
runs after the initial plan proposal but before collision archival, plan or
manifest writes, seed consumption, or a References write. It never prompts, so
a non-interactive caller receives the same refusal. An existing branch-collision
rollback may run after that `CreateError`: it clears only the temporary branch
binding and restores the invocation branch, leaving its empty candidate branch
for manual removal. That outer cleanup is not publication, must not archive or
consume a seed, and must leave the reusable proposal and research checkpoints
intact.

The zero-source disclosure is selected before publication only after the gate
passes. It therefore cannot make an ungrounded product publish, and it prevents
a fully description-backed selected result from reusing stale seed References
or failing the required-body placeholder check.

The source snapshot (target tokens, product values, origins, and descriptions)
is part of the reference-research checkpoint key. An operator who adds a
description and retries invalidates the affected research result while keeping
the initial step proposal and all pre-publication work reusable; the failed
attempt has neither archived nor consumed its seed. A changed source snapshot
cannot reuse a verdict for a different row.

For a roadmap-selected create, post-publication `--iterate` keeps the
pre-publication References block, including a zero-source disclosure, and skips
its later reference re-proposal. It may continue to re-propose steps, but it
does not obtain a second, nondeterministic no-source verdict after a plan has
published and therefore never patches, clears, or replaces the accepted
References block. A fresh create attempt again evaluates the source snapshot
before any replacement publication.

## References

- [Claude Code CLI referencehttps: — Documents non-interactive execution, structured output, tool permissions, and exit behavior for the research subprocess.
- [Claude Code Tools referencehttps: — Defines WebSearch behavior and permissions needed to understand how the research invocation obtains sources.
- [PyYAML Documentationhttps: — Covers safe YAML loading and scalar handling for the new optional roadmap-row description field.
- [dataclasses — Data Classeshttps: — Documents field defaults and frozen dataclass behavior used by hosting and store row models.
- [json — JSON encoder and decoderhttps: — Documents JSON decoding and failure handling for structured per-technology research results.
- [io — Core tools for working with streamshttps: — Defines terminal detection semantics needed to keep refusal behavior identical on non-interactive stdin.
- [How to monkeypatch/mock modules and environmentshttps: — Shows how to stub the research invoker, stdin state, and environment for hermetic refusal-path tests.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- The existing hosting/store blocks, vocabularies, and gates — this consumes
  them and must not redesign them. A defect found in them is filed as new work,
  not fixed here.
- Threading research into `detail`, `run`, or `jira`.
- Researching entity fields, patterns, or constraints — technology only.
- Any `--framework` lens work (#208 position 05). A lens supplies vocabulary;
  this supplies documentation, and the two must not be merged.
- Offline or air-gapped operation.

## Risks

- **A new way for `create` to fail, late in a long run.** The refusal lands
  after step proposal, so it must not discard that work — an operator who adds
  a description should not pay for a full re-proposal. If the plan cannot make
  that cheap, say so rather than shipping a re-run loop.
- **Detection quality is the likeliest defect.** A search that misses docs
  which exist produces a refusal the operator cannot honestly satisfy. See
  Stop/defer.

## Stop/defer

If an operator can show public documentation for a refused product, the
missing-source verdict is a detection or protocol defect. Fix the target
mapping, prompt, parsing, or checkpoint invalidation that caused it, then
re-run the existing refusal tests; do not treat an operator description as a
workaround or loosen the binary gate. Questions of whether the returned source
is relevant, current, authoritative, or sufficient remain out of scope and
are not turned into a scoring system in this work.

## Testing

Hermetic, with a stubbed research invoker — never the real network. What
would prove the Outcome: a tracked source selects the two roadmap artifacts
and renders a target for every named hosting/store row; whitespace-only product
values create no target; and repeated product names or row ids remain distinct
by a source-order token. Only the corresponding row's source or description
clears its verdict. A missing, duplicate, foreign, or malformed target response
fails as a protocol error rather than silently becoming an empty result. The
same is true when a non-empty target list contains an invalid Reference member.

Assert the disclosure boundary independently. A row marked `external` sends
only its product literal and opaque token; its description, origin, and every
local/unmarked product remain absent from the prompt. A `local` or unmarked row
with a nonblank description produces no outbound query and can proceed through
the local fallback. The same row without that description fails before the
invoker runs, asking for a description or explicit external disclosure. A
local-only selected roadmap makes no generic research request.

For a valid per-row response, a named technology whose record returns sources
proceeds; the same one returning nothing and carrying no description refuses,
naming both the technology and its field; and the same row with a description
present proceeds. Verify that a useless-but-present description passes, because
quality is deliberately not checked. Assert that parse/render and a revision
of a different field both retain descriptions. Assert that inline, interactive,
and untracked source paths retain today's behavior. Assert that a no-product
roadmap makes the existing generic References call but creates no target and
cannot refuse for prose-only technology names. Assert that a promoted seed whose
marker is relative to its original root still selects its roadmap when seed
paths relocate plan publication to a sibling repository. Also assert that a
changed marker or sidecar locator after initial selection cannot change the
confirmed roadmap, and that the product-mode prompt contains its token and
product but no description, origin, row metadata, or roadmap/sidecar path.

Assert the zero-source case separately: when every selected target is
source-free—an explicit empty external response or local result—and every row
has a nonblank description, the plan publishes with the exact disclosure rather
than seed References or `_(TODO)_`; a mixed source/description result publishes
decoded References plus one disclosure line naming any description-backed
products still selected, never a fabricated Reference row for them. Under
`--iterate`, the disclosure remains byte-identical and no later writer
replaces it.

For recovery, assert that a refusal occurs before any archive, plan, manifest,
seed-consumption, or References mutation; its initial step checkpoint survives;
and adding a description makes a retry recheck the changed target without
re-proposing unchanged steps. Under `--iterate`, assert that a roadmap branch
preserves the References block and makes no late reference call. The refusal
fires identically on non-interactive stdin.

Assert by mutation (CLAUDE.md § Tests). Assert the carve-out explicitly: a
description whose content is obviously useless still passes, because quality
is deliberately not checked — that test is what stops a later reader from
"improving" the gate into a judgment.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A tracked `--from-existing` source resolves one readable roadmap snapshot;
  each trimmed-nonblank `hosting:` or `stores:` product has a local description,
  field origin, disclosure decision, and stable token that includes its
  collection and source-order position. Only a row marked `external` sends its
  token and product literal to the external research request. Whitespace-only
  products create no target.
- A promoted tracked seed keeps its accepted absolute sidecar identity through
  seed-driven repository-root relocation, and stale-seed confirmation consumes
  that same identity without a second lookup; the relocated create still reads
  the original roadmap rather than silently taking the generic research path.
- The response binds exactly one source verdict to every external target, while
  a described local/unmarked target receives its deterministic local no-source
  result. Repeated product strings or duplicate row ids cannot share a verdict,
  and a malformed or incomplete external response fails before publication.
  Every member of a non-empty source list must decode as a Reference; invalid
  members are protocol failures, not empty-source verdicts.
- A `local` or unmarked selected product never triggers an external or generic
  research request. It proceeds only with a nonblank local description;
  otherwise creation fails before the research invoker runs, naming the row and
  requesting a description or `research_disclosure: external`.
- An empty source verdict for a named target, with no `description`, refuses;
  the message names the technology, its field origin, and what to add.
- The same target with a non-empty `description` proceeds, while a useless but
  present description also passes.
- When every selected verdict is explicitly empty but descriptions admit every
  target, References contains the fixed no-source disclosure—not a seed block,
  placeholder, or synthetic citation. Any decoded source instead uses the
  ordinary flattened References list.
- The refusal is identical on non-interactive stdin — no prompt, no skip.
- Non-roadmap create origins retain existing behavior. A roadmap with no named
  product makes the existing generic References call but creates no product
  target or refusal; malformed selected artifacts fail explicitly rather than
  degrading to plan prose.
- Failed pre-publication research retains the initial proposal checkpoint and
  leaves collision archives, plan/manifest writes, seed consumption, and
  References untouched; a description-only retry rechecks research without
  re-proposing unchanged steps.
- When a branch-collision gate is active, refusal may restore the original
  branch and clear its temporary binding, but still leaves every plan,
  manifest, source-archive, and checkpoint guarantee above intact.
- A roadmap-selected `--iterate` leaves its accepted References block untouched
  (including a no-source disclosure) and does not make a late re-research call.
- `ROADMAP_FORMAT.md` documents the `description` field on both row kinds, and
  `research_disclosure` on both row kinds; stage revision preserves both during
  unrelated row edits.
- `BACKLOG.md` #244 is updated when the work ships.

## Deferred

- Research for `detail`, `run`, and `jira`.
- Any re-research or staleness policy for a cached result.
- Researching non-technology rows.
