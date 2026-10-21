> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Re-author the withdrawn audit-trajectory step graph as a notes fixture

## Summary

This step adds `tests/fixtures/withdrawn_audit_trajectory_depends_on_notes.md`, a hand-authored plan file that copies the withdrawn `audit-trajectory-instrumentation` step graph and annotates **three** of its four bridging `depends_on` edges with pointer-style `depends_on_notes`, leaving one bridging edge visibly silent. Tests in `tests/test_create.py` parse the fixture, confirm `_bridging_dependency_edges` still yields 4→1, 4→2, 4→3, and 5→1, and check that each bridging edge either carries a note naming what it consumes or visibly lacks one — never an implied-but-unstated coupling. The archived plan under `docs/implementation-plans/archive/` stays untouched; the fixture is the separate proof artifact BACKLOG #253's scope contract names. No production code changes.

## Table of Contents

- [Summary](#summary) — what ships, where, and the green outcome
- [Why](#why) — the gap this step closes
- [Input](#input) — contracts and source material this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint per file
- [Implementation](#implementation) — fixture shape, note policy, and boundaries
- [Tests](#tests) — fixture contract cases
- [Verification (non-code step)](#verification-non-code-step) — reviewer checks beyond pytest
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs worth reading
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly not this step

## Why

BACKLOG #253's verification names re-authoring withdrawn #172's step graph so each bridging edge either states what it delivers or is visibly silent. Step 1 adds the schema field and step 3 teaches `create` to collect notes at authoring time, but nothing in the repo yet holds the motivational example as a durable, parseable artifact. The existing `test_withdrawn_172_plan_yields_its_measured_four_bridging_edges` in `tests/test_create.py` reads the real archived plan (no notes) to pin BACKLOG #252's topology; this step adds the companion fixture that shows what those same four edges look like once the consumption question is answered in frontmatter.

## Input

- **Step 1 outcome** — `plan_tool/schema.py:Step` carries `depends_on_notes: dict[int, str]` with a step-level validator rejecting keys not in that step's `depends_on`. Partial edge coverage parses; empty-string values may parse but are **not** the fixture's representation of silence — visible silence is an absent key.
- **Read-only source graph** — `docs/implementation-plans/archive/2-audit-trajectory-instrumentation.withdrawn.md` (strip the leading withdrawal blockquote before reading frontmatter, same as `test_withdrawn_172_plan_yields_its_measured_four_bridging_edges`). Copy each step's `id`, `files`, `creates`, and `depends_on` verbatim so `_bridging_dependency_edges` reproduces the same four edges; do not edit the archive file itself.
- **Bridging-edge definition** — `plan_tool/create.py:_bridging_dependency_edges` and `plan_tool/create.py:_BridgingDependencyEdge`: an edge whose dependent and antecedent share no declared production file (`plan_tool/create.py:_step_declared_code_files` excludes `tests/` paths). The four edges are 4→1, 4→2, 4→3, and 5→1; edges from test-only or docs-only steps (7→4, 7→6, 8→7) stay excluded.
- **Terminology** — "bridging edges" (BACKLOG #252 / `_BridgingDependencyEdge`) and the plan step title's "cross-cluster edges" name the same four edges in the Problem statement and Testing section.

## Files (creates vs edits)

- **New files:**
  - `tests/fixtures/withdrawn_audit_trajectory_depends_on_notes.md` — minimal valid plan: YAML frontmatter with the eight-step graph (topology copied from the archive), `depends_on_notes` on step 4 for three bridging edges (step 5's bridging edge left silent), and a one-line markdown body identifying it as BACKLOG #253's proof fixture (not an executable plan).

- **Existing files (edits only):**
  - `tests/test_create.py` — add a focused test class beside `TestBridgingDependencyEdges` (after `test_withdrawn_172_plan_yields_its_measured_four_bridging_edges`) with a module-level path constant to the new fixture; parse via `plan_tool/parser.py:parse_plan` or `parse_plan_text`; assert bridging topology and per-edge note presence policy.

## Implementation

### Design stance

- **Fixture, not archive rewrite** — the withdrawn plan's on-disk frontmatter is history. This step creates a separate file under `tests/fixtures/` that demonstrates the field on the graph that motivated the work.
- **Pointer notes, not scored claims** — each note names a symbol or deliverable to look up (BACKLOG #253's "consumes X from step N" style), mirroring step 3's authoring contract. Notes are not assertions that the coupling is real; they prove the question was asked.
- **Rejected alternative: generating the fixture through `create`** — would couple the proof artifact to proposal prompt quality and a Claude round-trip; the deliverable is a stable, reviewable markdown file checked into `tests/fixtures/`.

### Fixture content

- **Open on `---`** — no withdrawal blockquote; the file must parse through `parse_plan` without stripping.
- **Required frontmatter fields** — at minimum `title`, `status`, `priority`, and the full `steps:` block. Keep `files` / `creates` / `depends_on` aligned with the archive so `_bridging_dependency_edges(plan.steps)` returns `[(4, 1), (4, 2), (4, 3), (5, 1)]`.
- **May shorten** — `title`, `intent`, and step titles can be one-line summaries; long archive prose is not load-bearing for this fixture.
- **`depends_on_notes` placement** — only on steps that own the bridging edges (steps 4 and 5 in the archive graph). Annotate **three** of the four bridging edges with pointer-style notes; leave **one** bridging edge visibly silent (absent key) so the fixture demonstrates both first-class outcomes. Concrete split:

  | Edge | Policy | Likely note pointer (adapt wording; keep symbol names) |
  | --- | --- | --- |
  | 4→1 | annotated | consumes `record_hand_resolution` from step 1 |
  | 4→2 | annotated | consumes sidecar fingerprint diff gate from step 2 |
  | 4→3 | annotated | consumes sidecar finding-id diff from step 3 |
  | 5→1 | visibly silent | omit key `1` from step 5's `depends_on_notes` (or omit the field) |

- **YAML shape** — int keys under `depends_on_notes`, per step 1's contract (e.g. `depends_on_notes:\n  1: …`). Keys must round-trip as Python `int`, not strings.
- **Visible silence** — the silent bridging edge above plus all non-bridging edges omit their keys; do not invent notes on edges outside the three annotated bridging pairs.
- **Body** — one heading plus a sentence that this file is the BACKLOG #253 / depends-on-consumes-note step 5 proof fixture derived from withdrawn `audit-trajectory-instrumentation`, not a plan to run.

### Test module shape

- **Path constant** — one way: `WITHDRAWN_AUDIT_TRAJECTORY_NOTES_FIXTURE = Path(__file__).parent / "fixtures" / "withdrawn_audit_trajectory_depends_on_notes.md"`.
- **Helper** — small local helper returning the four bridging pairs from a parsed `Plan`, reusing `_bridging_dependency_edges` rather than duplicating file-overlap logic.
- **Do not replace** `test_withdrawn_172_plan_yields_its_measured_four_bridging_edges` — it pins the archive topology for #252; the new class pins the notes fixture for #253.

### Boundaries

- **No production edits** — do not change `plan_tool/create.py:_render_dependency_cohesion_block` to read notes (#257).
- **No content validation** — tests assert key presence and non-empty pointer text on annotated edges; they do not judge plausibility or truth.
- **No manifest registration** — the fixture lives under `tests/fixtures/` and is not a discoverable plan.

## Tests

The plan's `enforce_step_tests` gate keys on `change_type: feature` / `refactor`; this step is `non-code`, so that gate does not apply. The cases below are fixture contract tests in `tests/test_create.py`, not production behavior tests.

**New class** (one way: `TestWithdrawnAuditTrajectoryDependsOnNotesFixture`, beside `TestBridgingDependencyEdges`):

- `test_fixture_parses` — `parse_plan(WITHDRAWN_AUDIT_TRAJECTORY_NOTES_FIXTURE)` succeeds.
- `test_fixture_yields_same_four_bridging_edges_as_archive` — `_bridging_dependency_edges` on the fixture returns exactly (4,1), (4,2), (4,3), (5,1).
- `test_fixture_bridging_edges_each_have_note_or_visible_silence` — for each of the four bridging pairs, the dependent step either has a `depends_on_notes` entry for that antecedent id with non-empty text, or lacks that key entirely (empty `{}` on the step counts as visible silence for that edge).
- `test_fixture_annotates_three_bridging_edges_and_leaves_one_silent` — step 4's notes include keys 1, 2, and 3 with non-empty pointer text; step 5 omits key 1 (the silent bridging edge). Assert keys and non-emptiness on the annotated three — not exact prose.
- `test_fixture_note_keys_are_subset_of_depends_on` — every `depends_on_notes` key on every step is in that step's `depends_on` (sanity check that the hand-authored fixture respects step 1's validator).
- `test_fixture_is_not_the_archived_withdrawn_plan` — fixture path is under `tests/fixtures/`; `read_text` does not start with the archive's withdrawal blockquote.

Optional if cheap: `test_fixture_round_trips_notes_through_write_plan` — parse → `write_plan` → re-parse preserves the four note texts (can live here or defer to step 1's parser suite; prefer here only if it guards this specific fixture).

### Verification (non-code step)

1. `uv run pytest tests/test_create.py::TestWithdrawnAuditTrajectoryDependsOnNotesFixture -q` passes.
2. `docs/implementation-plans/archive/2-audit-trajectory-instrumentation.withdrawn.md` is unchanged (`git diff` clean on that path).
3. `rg 'depends_on_notes' tests/fixtures/withdrawn_audit_trajectory_depends_on_notes.md` shows entries only on steps 4 and 5.
4. Manual read: each of the four bridging edges either has a note naming what to look up, or the dependent step omits that antecedent's key — no edge relies on narrative alone.
5. Fixture opens with `---` and parses without blockquote stripping.

## Acceptance criteria

- `tests/fixtures/withdrawn_audit_trajectory_depends_on_notes.md` exists and parses through `plan_tool/parser.py:parse_plan`.
- `_bridging_dependency_edges` on the fixture returns exactly the four pairs (4,1), (4,2), (4,3), (5,1) — same topology as `test_withdrawn_172_plan_yields_its_measured_four_bridging_edges`.
- Each bridging edge has a non-empty `depends_on_notes` entry naming a concrete consumption pointer, or visibly lacks that key; the fixture specifically annotates three bridging edges and leaves one silent — no bridging edge is left in a state where a reader cannot tell whether a consumption claim was made.
- Every note key in the fixture is a member of its step's `depends_on` list.
- `docs/implementation-plans/archive/2-audit-trajectory-instrumentation.withdrawn.md` is not modified.
- New tests in `tests/test_create.py` pass; no files under `plan_tool/` change.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — int-key mapping in `safe_load`/`safe_dump` for frontmatter block mappings.
- [YAML 1.2.2 Specification](https://yaml.org/spec/1.2.2/) — bare integer mapping keys in plan frontmatter.
- [Pydantic v2 — Fields](https://docs.pydantic.dev/latest/concepts/fields/) — optional `dict[int, str]` field shape step 1 lands on `Step`.

## Applicable guardrails

- **Plan fence (structural key membership only)** — tests may check that a note key exists with non-empty text on annotated edges, or that a silent edge omits the key; they must not check wording quality, length, or truth, and must not require every edge to carry a note.
- **Plan "## Out of scope", retroactive notes** — do not edit the archived withdrawn plan or any other corpus plan; the fixture is the only new annotated artifact.
- **Plan "## Out of scope", gates and grading** — no gate, exit-code flip, or severity change keyed on note presence; the fixture is not consumed by any pipeline gate in this step.
- **Step intent** — scope is the four bridging edges on the motivational graph; do not require notes on non-bridging edges or on plans outside this fixture.

## Deferred

- **Threading notes into `_render_dependency_cohesion_block`** — BACKLOG #257; `_BridgingDependencyEdge` carries no note text today.
- **Automatic claim-vs-code checking** — permanently out of scope; notes are lookup pointers only.
- **Backfilling notes onto the archived plan or live corpus** — out of scope per the plan fence.
- **Parser round-trip tests for generic `depends_on_notes` shapes** — owned by step 1's `tests/test_parser.py`; this step only needs fixture-specific coverage unless a round-trip case is added as a cheap guard.
- **Using `create` / `_parse_steps_json` to produce the fixture** — rejected; hand-authored fixture is the deliverable.
