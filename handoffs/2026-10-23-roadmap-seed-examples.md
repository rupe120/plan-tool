# Roadmap seed examples

`docs/how-to/common-workflows.md` separates roadmap stage publication from
explicit seed materialization. The examples review the mapping, materialize
all recoverable drafts or a selected plan ID, inspect state and reported paths,
and review seed scope/references/Stack/prerequisites before create.

Direct draft consumption and optional promotion are alternatives. New promoted
seeds default to `docs/implementation-plans/plan-seeds/`; recorded legacy
publication and draft paths remain supported. The guide names the actual
reported path, preserves plan ordering/scope fences and continues through
both ordinary plan audit gates. No runtime behavior or default changes.

## Sites and evidence

Invariant: copied examples consume an explicitly materialized, reviewed seed
at its reported location; stage completion alone supplies no seed file.
Identifier search (`plan-seeds/`, `seeds/`, `materializ`) and vocabulary search
(`draft seed`, `ordered create`) locate the roadmap overview and the ordinary
pipeline handoff. Both sites receive the correction. The unchanged lifecycle
prose and other workflow sections remain outside this task.

Sources: `plan_tool/seed_paths.py` for nested/default versus legacy publication;
`docs/how-to/roadmap.md` section 7 for materialization, digest acceptance and
optional promotion; the generated roadmap command reference for flags.

- `uv run pytest tests/test_seed_paths.py tests/cli/test_cli_reference.py -q`: **15 passed**.
- The added seed-preparation link and heading anchor resolve.
- `git diff --check` passes.
- Initial reviews of `46daebb53..cc24341fc` use actual Claude Code Skill
  invocations (confirmed in session logs). One persisted first-round report
  describes its internal inline recipe as no Skill invocation; the outer
  session log explicitly contains `Skill(code-review)`. Round 2 records the
  invocation directly. Both verify the tracked source/path correction.
- A bounded follow-up changes inspection to `--view seeds`, separates the
  materialization heading, clarifies preserving hand edits before regeneration
  and explicitly points at the printed promotion create handoff.
- Two independent final actual Claude Code reviews of
  `46daebb53..fe525f41d986483cc0b9ea53fb96dc0edb2dace8` converge at **low-yield**:
  zero factual/correctness defects, only low-severity presentation feedback.
  Retained advisories: the seed subsection also contains general read-back
  prose; the conditional preservation warning appears before the first-run
  command. Neither changes the executable route or path contract. No further
  iteration is needed for the tracked defect.
- Final focused checks repeat with **15 passed**. The original backlog entry
  is removed with this correction. Separate README materialization drift and
  the destination-specific promotion summary are filed in BUG_BACKLOG; neither
  is claimed fixed here.

Review 1 session: `d21d9904-d78c-49eb-a4be-4e0877272516`.

Review 2 session: `e4a33535-6995-4092-b1bf-6df0e2b99b18`.

Review 3 session: `e392ae9a-3855-48bc-94b9-000b4a06c8e6`.

Review 4 session: `b9ad6952-4891-41f3-a990-94b926a48e36`.
