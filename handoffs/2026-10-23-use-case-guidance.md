# Use-case guidance correction

The catalog in `docs/how-to/use-cases.md` routes users through reviewed seeds,
both plan audit gates, and separately requested execution or local export.
Its CI example explicitly uses `--fail-on-findings`; informal manual review
does not replace either audit gate. Small changes use the supported staged
route; deprecated direct commands appear only as compatibility guidance.
New seed examples use `docs/implementation-plans/plan-seeds/`, while recorded
legacy destinations remain valid. External drafts explicitly reach both gates.

The roadmap entry provides artifact review questions and links to the deeper
walkthrough instead of repeating lifecycle mechanics. It requires explicit
materialization after stage 4, grounded in `plan_tool/roadmap.py` and the
walkthrough's seed-preparation section. Materialization does not approve a seed.

## Scope and sites

Invariant: a use-case entry points to the supported route and does not imply
that generation, a zero exit code, or informal review proves audit convergence.
Identifier searches cover `direct-jira`, `direct-run`, `plan-seeds/`,
`verify-all`, and the retired section-9 anchor. Vocabulary searches cover
manual verification, skipping audits, seed promotion and draft generation.
The relevant sites are the fit table, shared review introduction, sections
1/2/4/9/11, the not-to-use list and the entry-point table. All are corrected
within this catalog; detailed lifecycle procedures remain with their owners.
No repository link targets the renamed section-9 heading.

## Verification

- Every local Markdown link target and heading anchor in the catalog resolves.
- `git diff --check` passes.
- `uv run pytest tests/cli/test_cli_reference.py -q`: **10 passed**.
- No runtime changes or live plan/backend invocations are part of this task.
- Initial reviews at `38cee4947` both invoke the actual built-in Claude Code
  `code-review` Skill with `claude-sonnet-5-5 --effort high`. Round 2 finds no
  confirmed defect. Round 1 identifies residual legacy-grade future wording
  and the linked common-workflows CI mismatch; both receive bounded fixes.
  Its claim that section 5 never states the pre-execution boundary is partly
  refuted by the existing “unexecuted plan” request; the correction also makes
  the boundary explicit in explanatory prose and names the applicable re-audit.
- Optional suggestions to restore roadmap lifecycle detail are declined: the
  linked walkthrough and format own those procedures, and the orientation page
  makes no conflicting claim. An undefined direct-change route gains its exact
  directives link. No runtime behavior or test-authoring work is implied.
- Two independent final actual Claude Code reviews at
  `46987e67e63bc1a939d3427f2d27bf8b586e65e3` (range `8a92bb504..46987e67e`)
  find no introduced defect in the changed guidance. Both retain optional
  wording suggestions without requiring further edits: low-yield convergence
  for this bounded documentation change.
- Both reviews confirm pre-existing roadmap seed examples in the untouched
  common-workflows roadmap subsection still use old paths and imply automatic
  materialization. They are deferred to BUG_BACKLOG, “Common-workflows roadmap
  examples point new users at seeds that do not exist.” No source behavior is
  changed or claimed fixed by that deferral.
- Final command-reference recheck: **10 passed**; links/anchors and whitespace
  checks pass again after the correction batch.

Initial round 1 session: `bc379312-afed-43aa-bd9f-07d840f65a50`.

Initial round 2 session: `8f750bc4-309f-4244-bb39-36555e53fb10`.

Final round 3 session: `33918a2a-ae91-451e-ac9e-632712e85f4a`.

Final round 4 session: `dc4c8019-0569-44b7-8f79-046680176630`.
