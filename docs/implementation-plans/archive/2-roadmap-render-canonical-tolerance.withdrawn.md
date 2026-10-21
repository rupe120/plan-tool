> **Withdrawn 2026-08-19** — Superseded before detail authoring: parser-round-trip tolerance cannot detect semantic source drift; roadmap canonical source identity owns the replacement contract.
> Preserved here for history; do not edit.

---
title: Roadmap Render Canonical Tolerance
intent: 'An artifact whose on-disk text differs from `render(parse(text))` only in
  ways that don''t change its parsed meaning — formatting drift today, and concretely
  BACKLOG #242''s planned closed-row render sort once it ships — is accepted by every
  revision-family consumer as the freshly-rendered canonical text, instead of being
  refused outright with no recovery path.'
status: planning
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-render-canonical-tolerance.md
steps:
- id: 1
  title: Add a shared safe-canonical-text helper and keep receipt snapshots byte-strict
  intent: Give every revision family one exact rule for replacing cosmetic drift while
    preserving raw-byte evidence binding.
  files:
  - plan_tool/roadmap_artifacts.py
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap_escalation_selection.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Store semantically equal impact snapshots as canonical text and digests
  intent: Let structural revision evidence proceed from harmlessly reformatted artifacts
    with stable canonical bindings.
  files:
  - plan_tool/roadmap_impact_snapshot.py
  - tests/test_roadmap_impact_snapshot.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the exact semantic-equality substitution rule used during capture.
- id: 3
  title: Use canonical structural patch text while preserving malformed-scalar rejection
    and canonical replacement
  intent: Ensure structural patching works from safe canonical substitutions without
    weakening its byte-splice protections.
  files:
  - plan_tool/roadmap_structural_revision_patch.py
  - tests/test_roadmap_structural_revision_patch.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Supplies canonical snapshot text to the structural preflight chain.
- id: 4
  title: Use canonical text in structural proofs while preserving one-artifact publication
  intent: Prevent the proof boundary from rejecting safe substitutions while keeping
    published candidates renderer-produced.
  files:
  - plan_tool/roadmap_structural_revision_proof.py
  - tests/test_roadmap_structural_revision_proof.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Provides canonical patch candidates and preserves the malformed-scalar guard.
- id: 5
  title: Accept semantically equal structural preflights while preserving seed invalidation
    and artifact replacement
  intent: Keep the structural runner from reinstating a stricter byte-only refusal
    after safe normalization.
  files:
  - plan_tool/roadmap_structural_revision_run.py
  - tests/test_roadmap_structural_revision_run.py
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  depends_on_notes:
    4: Completes canonical proof handling before the runner admits the widened route.
- id: 6
  title: Accept semantically equal local revisions while preserving seed invalidation
    and canonical artifact replacement
  intent: Let bounded local feedback revisions recover from cosmetic hand edits without
    tolerating semantic changes.
  files:
  - plan_tool/roadmap_revision.py
  - tests/test_roadmap_revision.py
  - tests/test_roadmap_revision_run.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the shared exact semantic-equality substitution rule.
- id: 7
  title: Document parsed-equality tolerance and remove the resolved bug backlog entry
  intent: Make the roadmap format contract describe the shipped fallback and stop
    advertising the fixed limitation.
  files:
  - ROADMAP_FORMAT.md
  - BUG_BACKLOG.md
  - tests/test_roadmap_format.py
  complexity: low
  change_type: non-code
  depends_on:
  - 5
  - 6
  depends_on_notes:
    5: Delivers the complete structural-revision behavior the contract describes.
    6: Delivers the local-revision behavior the contract describes.
---
# Roadmap Render Canonical Tolerance

## Overview

One check shape, five call sites, one fix shape. Every site currently does
`if render(parse(on_disk_text)) != on_disk_text: refuse`. Each becomes: on a
byte mismatch, additionally check `parse(on_disk_text) ==
parse(render(parse(on_disk_text)))` — parsed/semantic equality. A match means
nothing semantic was lost; substitute `render(parse(on_disk_text))` as the
trusted working text and proceed. A mismatch keeps the existing refusal,
unchanged.

## Problem statement

`ROADMAP_FORMAT.md:731-736` already documents this as a known, currently-live
limitation, verbatim: "The loaded artifact must be render-canonical. The
contract parses it with the selected stage parser, renders that value with
the matching selected stage renderer, and requires byte-for-byte equality
with the loaded text. It does not strip comments or normalize whitespace...
a hand-edited version is not [canonical]." No RUNBOOK.md guidance or code
path tells an operator how to recover once this fires, and the only existing
test (`tests/test_roadmap_impact_snapshot.py:206`,
`test_capture_rejects_parseable_but_noncanonical_artifact_text`) covers only
trivially-garbage input, not a realistic valid-but-reformatted hand edit — so
a legitimate hand edit hitting this has no coverage anywhere.

BACKLOG #242's planned closed-row render sort is the concrete, likely-common
trigger this seed exists to get ahead of: a reviewer setting a mid-list
row's `state` to `closed` — a move that plan explicitly sanctions — leaves
the artifact byte-non-canonical until an ordinary revision run next
re-renders it. Every consumer below rejects the file outright in the
meantime, rather than self-correcting, even for a request answering an
unrelated row entirely.

## Architecture

**Five enforcement points, three independent consumer families — not one
chain to patch in one place:**

- **The impact-snapshot family** (chained): `roadmap_impact_snapshot.py:176-198`
  (`_capture_artifact`) is the first, effective blocker — it populates
  `RoadmapImpactSnapshot` from raw on-disk bytes and refuses immediately on a
  canonicality mismatch. `load_structural_revision_preflight`
  (`roadmap_structural_revision.py:138`) reads that snapshot into
  `preflight.selected_artifact_text`, which
  `roadmap_structural_revision_patch.py:154-175` (`_require_preflight`)
  re-checks as defense-in-depth against staleness between capture and use.
  `roadmap_structural_revision_patch.py:462-473` (`_parse_canonical_candidate`)
  is a third check on the *patched* candidate, in practice unreachable for
  this scenario since `_require_preflight` already blocks first — the fix
  belongs at `_capture_artifact`, with the later two kept as the same
  defense-in-depth they are today (they should simply never fire once the
  source they compare against is already canonical).
- **The structural-revision proof family** (independent):
  `roadmap_structural_revision_proof.py:232-242` (`_require_canonical_text`)
  is a separate consumer of on-disk text with its own identical check —
  needs the same tolerance applied at its own read boundary.
- **The local/incremental-revision family** (independent):
  `roadmap_revision.py:183-195` (`preflight_feedback_revision`) is a wholly
  separate route (`roadmap_revision.py` / `roadmap_revision_patch.py` /
  `roadmap_revision_publish.py` / `roadmap_revision_run.py`), architecturally
  distinct from "structural revision" despite the similar name and originating
  from a third, separate archived plan (`roadmap-incremental-revision`,
  whose creation commit literally introduces render-canonicality as
  foundational). A fix scoped to only the structural-revision family leaves
  this route silently unprotected — it hits the identical failure mode
  independently.

**Why parsed equality is safe, checked against the actual code, not assumed.**
`tests/test_roadmap_structural_revision_patch.py:234`
(`test_merge_rejects_canonical_target_scalar_that_crosses_a_physical_yaml_line`)
proves the malformed-scalar-span protection
(`_locate_row_field_scalar` in `roadmap_structural_revision_patch.py`) fires
on *whatever text is currently being byte-spliced* — including the
renderer's own natural output for a sufficiently long value (its own fixture,
`_naturally_folded_render`, demonstrates this) — and runs *before* replacement
is applied. Substituting a freshly re-rendered source for raw bytes changes
none of this check's inputs in a way that weakens it: a genuinely
long/wrapping value still wraps, and still gets caught, in the re-rendered
text exactly as it would in the original. There is already a precedent for
parsed-level comparison in this exact module — `roadmap_structural_revision_patch.py`
already compares `predecessor != preflight.selected_artifact` as parsed
objects (`RoadmapArtifact` variants are frozen dataclasses, so structural
equality is free) — this seed's fix is the same comparison discipline
applied one layer earlier, at the raw-text boundary.

**Update the contract statement, not just the code.** `ROADMAP_FORMAT.md:731-736`
currently states the canonicality requirement as unconditional byte equality;
it must be corrected to describe the parsed-equality fallback once it ships,
or the doc becomes the next thing this effort makes stale.

**Duplication note.** The same "on byte mismatch, try parsed-equality
substitution" shape lands at three independent sites. `tests/test_duplication.py`
is this repo's guard against exact-duplicate function bodies (≥4 lines,
normalized) — if the three sites end up with enough shared shape to trip it,
extract one small shared helper; if their surrounding context differs enough
that a shared helper would distort any of the three, an `ALLOWED_DUPLICATE_GROUPS`
entry with a stated reason is the correct answer per that guard's own
documented policy. This is `create`/`detail`'s call once the actual code is
in front of them, not this seed's.

## References

- [YAML 1.2.2 Specification — Processes and Models](https://yaml.org/spec/1.2.2/#chapter-3-processes-and-models) — Defines YAML representation, serialization, presentation details, and why comments and formatting do not affect parsed meaning.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Documents safe_load, safe_dump, compose, node types, and source marks used by the roadmap parser and renderer.
- [Python 3.13 dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Specifies generated structural equality and frozen dataclass behavior underlying parsed artifact comparisons.
- [pytest — Parametrizing Tests](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Explains parameterized test cases suitable for exercising equivalent and mismatched artifacts across every consumer boundary.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- BACKLOG #242's own work (the closed-row sort itself) — a separate,
  already-in-progress plan; this seed only gets ahead of a gap that plan's
  design would otherwise trigger.
- Any operator recovery tooling or guidance beyond the `ROADMAP_FORMAT.md`
  contract correction — e.g. a `plan-tool roadmap --canonicalize` command.
  File that separately if a real operator need is observed after this ships.
- Reopening any of the three originating plans' own settled feature scope.
  This is confined to the shared render-canonical *check* each one calls,
  never their patch/publish/proof semantics beyond it.
- Any other kind of non-canonical drift beyond what parsed equality already
  tolerates (e.g. a genuinely different value that just happens to render
  similarly) — stays refused, unconditionally.

## Risks

- **Parsed-equality is only as safe as `parse()`'s own completeness.** If any
  future roadmap artifact field is lossy or non-deterministic through a
  parse/render round-trip in a way that isn't true today, this tolerance
  would silently paper over it. Nothing today is known to have that property,
  and this is why `## Not allowed` refuses loosening beyond exact parsed
  equality.
- **This touches code from three already-completed, otherwise-protected
  plans.** Ground each site's current behavior directly against its own
  tests before changing it, and re-run each of the four sites' existing test
  files in full, not just new tests, so no unrelated behavior in those
  modules regresses.
- **Precedence assumption.** The impact-snapshot family's three checks are
  assumed sequential (`_capture_artifact` first, effectively blocking before
  the other two are ever reached in this scenario) based on the call chain
  traced during this seed's research, not from a dedicated integration test —
  confirm this ordering holds before relying on fixing only the first site to
  silence the other two in practice; fix all three regardless, since each is
  independently reachable in principle.

## Testing

Hermetic, fixture-driven — the arc's existing pattern. What would prove the
Outcome: an artifact whose on-disk text differs from its canonical render
only by whitespace/comment formatting is accepted (substituted) by each of
the three consumer families, asserted by mutation (CLAUDE.md § Tests) —
break the substitution and watch each consumer's test go red; a
concretely-reordered artifact (a `closed` feedback row placed mid-list by a
direct fixture edit, not requiring BACKLOG #242 to have shipped) is likewise
accepted once fed through a renderer that already sorts, proving the fix
generalizes to #242's future trigger without depending on it; the
malformed-scalar-span rejection test
(`test_merge_rejects_canonical_target_scalar_that_crosses_a_physical_yaml_line`)
still passes unchanged; a genuinely semantically-different source text (not
just reformatted) is still refused at every one of the five sites, each
asserted directly; and `ROADMAP_FORMAT.md`'s render-canonical statement
matches the shipped behavior, held by its own format test the way this
family of docs already is elsewhere.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A hand-edited artifact that changes nothing semantically (reformatted
  whitespace, a stripped/altered comment) is accepted by `_capture_artifact`,
  `_require_preflight`, `_require_canonical_text`, and
  `preflight_feedback_revision` — all four read/capture boundaries — instead
  of raising a canonicality error.
- A source text with a genuinely different parsed meaning is still refused at
  every one of the five sites, with the same error shape as today.
- The malformed-scalar-span rejection
  (`test_merge_rejects_canonical_target_scalar_that_crosses_a_physical_yaml_line`)
  is unaffected.
- `ROADMAP_FORMAT.md:731-736`'s render-canonical statement accurately
  describes the parsed-equality fallback.
- Each of the three consumer families' existing test suites pass unchanged
  beyond the new coverage this effort adds.

## Deferred

- Any operator-facing recovery/repair tooling.
- Any second kind of tolerance beyond exact parsed equality.
- Reopening any of the three originating plans' feature scope beyond the
  shared canonicality-check leaf.
