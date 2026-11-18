# Step 2 — Verify installed seed guidance against file-backed intake

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend `tests/cli/test_skill_cmd.py` to follow both authoring entry points from each installed router to the shared seed guidance. Exercise default and explicit `--copy` installs for Claude, Codex, and Cursor, and run the installed examples through file-backed intake without a model call. Repeat the link check outside pytest with the CLI from an isolated wheel installation. The checks pass when all six cases in each run expose the same authoring contract and the examples demonstrate direct readiness and preparation as documented.

## Table of Contents

- [Summary](#summary) — What the source and wheel checks prove.
- [Table of Contents](#table-of-contents) — Where to find each check.
- [Why](#why) — What the existing installed-link test leaves open.
- [Input](#input) — The guidance, examples, and intake results this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The test module this step extends.
- [Implementation](#implementation) — How to verify the installed path and both example routes.
- [Tests](#tests) — Focused pytest cases and the separate wheel run.
- [Acceptance criteria](#acceptance-criteria) — What must be observable before step 3 closes the backlog entry.
- [References](#references) — The contracts and code behind the checks.
- [Applicable guardrails](#applicable-guardrails) — The limits on verification and changes.
- [Deferred](#deferred) — Release bookkeeping owned by step 3.

## Why

`tests/cli/test_skill_cmd.py:test_installed_router_links_resolve_against_the_installed_directives()` already installs each integration in both modes and confirms that the phase table’s links point to headings in the installed sibling. Its generic assertion can still pass if the Authoring row loses its seed link. It also leaves the examples untested against intake and provides no evidence that a standalone wheel carries the guidance a consuming repo needs.

## Input

- Step 1 supplies the Authoring row and big-document shortcut, the shared authoring contract, and the two worked seed examples. Read the examples through the installed link and use the sample request, backlog entry, and local evidence named by the walkthrough.
- `plan_tool/create.py:validate_from_existing_seed()` accepts seed text and returns `FileBackedSourceIntake`. Use `references_ready`, `direct_ready`, and `needs_preparation` to check preflight and body shape. Review evidence quality, the placement of binding limits, and the approval sequence separately.

## Files (creates vs edits)

- **New files** — None.
- **Existing files (edits only)**
  - `tests/cli/test_skill_cmd.py` — Extend the existing installation matrix and add focused checks for the examples read from the installed guidance.

## Implementation

- **Follow the required link from the installed router.** Extend `tests/cli/test_skill_cmd.py:test_installed_router_links_resolve_against_the_installed_directives()` and reuse `tests/cli/conftest.py:tmp_repo` with `CliRepo.argv()`. Use `tests/skill_router_phase.py:phase_section()`, `LINK_RE`, and `anchors()` for the existing phase checks. Require `DIRECTIVES.md#authoring-hygiene` in both the Authoring row and the big-document shortcut. Look up the sibling relative to the installed router’s directory before resolving symlinks. A checkout-only link test, or an anchor check on a sibling opened independently of the router link, can pass while the authoring path is missing.
- **Check both files in each fresh install.** Match `plan_tool/cli/skill_cmd.py:cmd_install_skill()`: Claude and Cursor use `.claude` and symlink both files by default. Codex uses `.agents` and copies both files by default. Explicit `--copy` copies both files for all three. Keep temporary installs, fixture writes, unlinks, and cleanup inside test-owned paths. If checking that a missing link trips the assertion, change an in-memory string or a test-owned copy.
- **Check the examples as written.** Extract the seed text from the linked section and pass it unchanged to `plan_tool/create.py:validate_from_existing_seed()`. Check that the request example is direct-ready and that the backlog example passes preflight and needs preparation. In a test-owned copy of the direct example, replace the Testing prose with a fenced-only command and check that the classifier selects preparation. A focused check of the shared examples suffices once the six installs prove they expose the same guidance.
- **Trace each example to its evidence.** Use the landed examples to choose small consuming-repo fixtures. Open the paths named in each `References` section, confirm any cited symbols or tests exist, and check that the cited material supports the claim. Review the measurable `Outcome`, full scope contract, verification and acceptance evidence, and the backlog example’s source identity and shipment bookkeeping. Trace each binding limit to its named guardrail and check that each `None` matches the example’s actual limits. Check that the preparation guidance and example cover source-backed exclusions, risks, testing, acceptance criteria, and any actual deferrals. Verify that the walkthrough puts user approval and a commit of the approved seed before the file-backed `create` call.
- **Prove wheel provenance in a separate run.** Build a wheel with the existing build tooling and install that artifact into a fresh environment outside the checkout. Invoke that environment’s `plan-tool` executable from fresh consuming repositories with checkout imports excluded. Confirm that the imported package and the integrations directory selected by `plan_tool/backend.py:_packaged_integrations_dir()` are inside the wheel installation. Check symlink targets against those packaged files and compare copied bytes with their packaged counterparts. Follow both links in all six cases and compare the authoring sections across modes and integrations using only the installed pair. The wheel run needs neither an editable install nor the checkout’s `SEED_FORMAT.md`.

## Tests

### Verification (non-code step)

`plan_tool/launcher.py:_step_requires_test_authoring()` exempts `non-code` steps from the run gate. This step adds focused verification in the existing suite.

1. `tests/cli/test_skill_cmd.py:test_installed_router_links_resolve_against_the_installed_directives` — All six fresh installs have the expected file types, retain their phase links, and expose the required authoring link in both router entries.
2. `tests/cli/test_skill_cmd.py:test_installed_seed_examples_match_intake_and_source_evidence` — The two shipped examples pass preflight with their expected readiness results, cite usable fixture evidence, and carry their binding limits under the correct guardrails.
3. Installed walkthrough review — Confirm that source and code checks precede user approval, then the approved seed is committed before `create --from-existing`.
4. Isolated wheel acceptance — Outside pytest, repeat the six-case link check through the installed executable, confirm wheel provenance, and report the result for step 3.

## Acceptance criteria

- The focused pytest checks pass for Claude, Codex, and Cursor in both modes. The Authoring row and big-document shortcut in each case reach the same section in the installed sibling.
- The installed request example returns `references_ready` and `direct_ready`. The backlog example and a fenced-only Testing variant of the request example pass preflight and return `needs_preparation`. These checks run without a model call.
- Each example’s References lead to usable evidence, its limits appear in the relevant guardrails, and its testing and acceptance evidence covers the stated outcome. The walkthrough puts approval and commit before creation.
- The separate wheel run passes all six cases outside the checkout, demonstrates where each installed file comes from, and reaches the same contract without opening the checkout’s `SEED_FORMAT.md`. Existing installs are untouched.

## References

- [Seed format — Review the scope contract and canonical heading conventions](../../../../SEED_FORMAT.md#conventions)
- [Seed ingestion contract — Check preflight, body readiness, and preparation evidence](../../../../docs/reference/contracts/seed-ingestion.md)
- [File-backed intake — Find `validate_from_existing_seed()` and `FileBackedSourceIntake`](../../../../plan_tool/create.py)
- [Installed authoring guidance — Find the walkthrough and examples under Authoring hygiene](../../../../integrations/shared/DIRECTIVES.md#authoring-hygiene)
- [Skill installer — Find `cmd_install_skill()` and its mode and destination rules](../../../../plan_tool/cli/skill_cmd.py)
- [Wheel configuration — Find the console entry point and `tool.hatch.build.targets.wheel.force-include`](../../../../pyproject.toml)
- [Installed Seed Authoring — Check ownership, verification, and release criteria](../../2-installed-seed-authoring.md)
- [Backlog — Find entry #377 for the source scope and verification requirements](../../../../BACKLOG.md)

## Applicable guardrails

- **The plan’s `## Scope guardrails`, verification boundary.** Keep the tracked diff in the declared test module. Exercise the existing installer and file-backed intake as production entry points.
- **The plan’s `## Audit guardrails`, review boundary.** Review the installed authoring path and its agreement with intake. The plan assigns onboarding sign-off and tracker policy elsewhere.
- **The plan’s `## Expected placement`, guidance ownership.** Read the contract from the installed sibling. Use the source format as the authoring reference during repository review and the installed pair as the sole guidance for wheel acceptance.
- **The plan’s `## Out of scope`, preparation and adjacent work.** Preserve the preparation example’s eligible source shape. Keep the checks focused on installed guidance and the existing intake contract, within the product and tracker boundaries named in the plan.

## Deferred

- `BACKLOG.md` #377 release bookkeeping — Step 3 owns closure after shipment and passing source and wheel verification.
