# General onboarding documentation

The README routes first-time users through installation, reviewed planning,
execution prerequisites and the operational guides. Detailed command, backend,
recovery, logging and gate procedures live in their existing guides. Existing
README heading anchors remain available for incoming links.

## Scope and sources

The user requests correction of the onboarding review's five findings:
execution prerequisites, the frontmatter example, deprecated apply guidance,
contributor setup/work selection, and README duplication. Runtime behavior and
assistant policy remain unchanged.

Identifier searches cover `intent`, `format_version`, `require_merged_plan`,
`completeness-apply`, `--jobs`, and README links. Vocabulary searches cover
execution, default branch, planning artifacts, interactive application,
installation, picking work, and recovery. Relevant sites are README's first-plan
handoff, plan example, operational sections and install options; CONTRIBUTING's
short version and setup; common workflows' execution handoff; and the run guide's
entry prerequisites. The correction applies at these sites. Deeper independent
reference prose remains outside this onboarding edit.

Sources are `plan_tool/cli/run_cmd.py:_preflight_merged_plan_guard`,
`plan_tool/plan_merge_guard.py`, `plan_tool/review.py:check_intent_presence`,
`plan_tool/parser.py:parse_plan_text`, the completeness CLI options, and the
existing task/reference guides. The merge-check description distinguishes
missing artifacts, drift warnings, absent origin and unverifiable remote state.

## Verification and review

- Full suite: `uv run pytest tests/ -q -n auto` — **15,154 passed, 66 skipped**.
- The README frontmatter example parses through `parse_plan_text` and produces
  no `check_intent_presence` findings.
- Local link and fragment checks pass for all four edited onboarding documents.
  All original README heading anchors outside fenced examples remain available.
- `git diff --check` passes.
- Session review round 1 catches a nonexistent lessons reference and a stale
  contributor pull-request anchor; both links receive corrections. A second
  correctness/completeness pass checks the execution state cases, example,
  deprecated commands, setup prerequisites and preserved routes, with no new
  findings. These are session reviews, not independent backend reviews.

No implementation or model-backed plan-tool command is necessary for this
bounded documentation correction. The installation instructions are checked
against tracked sources; no fresh external installation is exercised.
