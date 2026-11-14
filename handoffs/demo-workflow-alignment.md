# Demo workflow alignment

The dark-mode authored sample uses preferred step `description`; legacy
`title` remains accepted by the tool. Its excerpts remain intentionally
incomplete, with no new claim of captured output or live audit convergence.
The planning walkthrough already carries both audit/review boundaries,
current seed placement and local-only export, so it needs no workflow edit.

The TTRPG runbook places scaffold authoring after accepted roadmap publication,
asks readers to inspect plan IDs/outcomes/ownership/dependencies, and names
materialization/review before optional promotion. The promotion request shows
the complete target set and does not silently extend a selected demo batch to
missing or unreviewed sibling seeds. Direct reviewed draft use remains an
alternative. Later create reuses the selected row ID with a reported
repo-relative seed path. The prior phase-3 anchor remains valid through an
explicit anchor because the dated verification record links to it.

## Scope and sites

Invariant: demos teach the shipped workflow and preserve review/authorization
boundaries without implying a new rehearsal or remote publication. Identifier
searches cover step title/description, materialize/apply/create operands and
phase headings; vocabulary searches cover seed generation, scaffold timing,
promotion selection and legacy seed destinations. The four demo pages are
reviewed; only the sample and roadmap runbook need changes. Existing lifecycle
procedures remain owned by the shared directives and format/guide documents.

The plan-list review prompt reflects current stage-4 responsibilities; it is
not a stage-4 algorithm change or a semantic decomposition gate. Historical
preparation checkmarks and measurements remain dated provenance.

## Verification

- `uv run pytest tests/test_seed_paths.py tests/cli/test_cli_reference.py -q`: **15 passed**.
- All demo-local link targets and heading anchors resolve; prior phase-3
  incoming anchor from the verification record remains available.
- `git diff --check` passes.
- Existing `tests/test_roadmap_format.py` (including the demo documentation
  guard): **53 passed**. No full-suite repeat for this prose-only correction.
- Two independent completed reviews target
  `f7176a27a..ed29b1e97bba36e611453605a61ebf713a0d6b7c`, using actual built-in
  Claude Code `code-review` Skill calls with `claude-sonnet-5-5 --effort high`.
  Both session logs contain the actual Skill invocation; the second persisted
  report describes its inline recipe rather than that outer call.
- Outcome: **low-yield convergence**. No correctness/contract failure is
  confirmed against source. Retained low-severity observations: historical
  scaffold wording still names its stage-3 source (dated provenance, not timing
  instructions); later audit/detail placeholders retain the generic plan-id
  spelling; the generic reviewed-seed path covers either source. The promotion
  instruction already stops on missing/unreviewed siblings and offers direct
  draft use; a fuller all-or-nothing explanation belongs to the linked owner.
- Old heading text in completed plan details remains historical provenance;
  the explicit anchor preserves the live evidence-record link. Inline
  placeholders are explained substitution notation, not new CLI operands.
- A new parser test for deliberately incomplete reading excerpts is declined:
  it would turn authored samples into runnable fixtures outside this scope.
  The existing format/documentation guard passes instead.

## Preparation limits

No live plan-tool authoring, model rehearsal, feature implementation, tracker
publication or remote checkpoint update occurs in this task. Dark-mode remote
checkpoint refresh and a fresh TTRPG rehearsal remain pending as the demo index
and existing verification record state.

Review 1 session: `1f7a2c46-d325-4d2c-86b5-c2070e9a660c`.

Review 2 session: `16345ded-8227-4679-8e4c-bba6c593dbdd`.
