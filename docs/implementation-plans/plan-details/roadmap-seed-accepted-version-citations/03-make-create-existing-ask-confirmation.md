# Step 3 — Refuse a tracked seed that fails the bare-name check, even under `-y`, and name its repair routes

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed` refuse a tracked seed that still names a roadmap member file without its version-store path, with or without `-y`. It runs step 2's text-only bare-name function on the exact bytes `create` is about to read, draft or promoted copy, before the existing state-based confirmation. The key decisions: the refusal does not yield to `-y` (owner decision, 2026-11-17: automated sessions always pass `-y`, so a continuing confirmation would let the bug through in hands-off runs), and the refusal names the repair routes for that seed's location. On green, a legacy seed never becomes a plan until it is regenerated or repaired.

## Table of Contents

- [Why](#why) — what the promoted copy skips today
- [Input](#input) — step 2's function and the existing confirmation flow
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files and their edits
- [Implementation](#implementation) — the bare-name check first, the refusal, per-location messages, constraints
- [Tests](#tests) — unit, route and integration cases, plus the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — docs for the tools this step uses
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

Step 2 makes a draft seed with a bare name `malformed`, so the draft path reaches today's confirmation, which `-y` answers. A promoted copy is judged only by the sidecar's `invalidated` status, so a legacy promoted copy with bare names passes silently into `create`. `create` then copies seed sections into the plan, and a reader or audit that opens a bare name can read a stale top-level `0N-*.md` beside the accepted head. A confirmation would not close it either: the directives tell every automated session to pass `-y`, so a prompt that `-y` answers lets a legacy seed through in exactly the hands-off runs this bug hurts most. This step closes the route with a refusal that `-y` does not override.

## Input

- **Step 2** adds a public text-only function in `plan_tool/roadmap_gates.py` (the plan suggests `find_bare_roadmap_file_citations(text)`, returning `list[Violation]`). Read the landed name from the module; the landed name wins. It needs no repo root or accepted head.
- **`_confirm_invalidated_roadmap_seed(location, *, yes, input_fn=input)`** already loads the accepted version, finds the plan row, and splits on `location.via_marker`. The draft arm calls `classify_draft_seeds`. The promoted arm reads only `load_seed_state(location.state_path)["seeds"]` for `status == "invalidated"`.
- **`cmd_create`** calls `locate_tracked_seed(source_path, repo_root=repo_root)`, then this function, and returns 2 on refusal. `PRE_SLUG_REFUSAL_REASONS` holds the closed set of `create-refused: reason=` tokens, documented in `DATA_CONTRACT.md` and drift-guarded by `tests/test_data_contract.py`; this step adds one, `roadmap-seed-bare-citation`, because `roadmap-seed-not-confirmed` would misdescribe a refusal `-y` cannot clear.
- **`TrackedSeedLocation`** (`plan_tool/roadmap_seed_state.py`) carries `plan_id`, `roadmap_slug`, `state_path`, `via_marker`. The seed state entry carries a `published` bool.
- **`source_artifacts`** is read by no module (the `source_artifacts` name in `plan_tool/roadmap_candidate_run.py` is an unrelated local variable); `plan_tool/create.py` never reads it. The frontmatter case below pins that `create` does not copy it, with no new code.
- **Verification limit:** these checks prove citation form, not that a quoted passage matches the cited file.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py`: in `_confirm_invalidated_roadmap_seed`, run the bare-name function on the bytes `create` will read, before the state checks; refuse with `roadmap-seed-bare-citation` and per-location routes; add the token to `PRE_SLUG_REFUSAL_REASONS`; update the function docstring.
  - `DATA_CONTRACT.md`: add `roadmap-seed-bare-citation` to the documented `create-refused` reason tokens.
  - `tests/cli/test_authoring_cmds.py`: add cases to `TestRoadmapSeedConfirmation` (reuse its `_write_tracked_draft` helper) and one integration case.

## Implementation

- **Check the bytes `create` will read, first.**
  - For every tracked seed (`location is not None`), after the accepted version and plan row are resolved and before the state checks, call step 2's function on the seed text `create` is about to consume: the draft's bytes on the draft arm, the promoted copy's bytes on the `location.via_marker` arm. Pass the text from `cmd_create`, which already holds it, as a new keyword argument (for example `seed_text`) rather than reading the file again.
  - The function strips frontmatter itself, as step 2 defines; pass the text as read. Do not run `validate_draft_seed_content` on a promoted copy; a promoted copy is not a draft.
- **A bare name refuses, whatever else is true.**
  - When the function returns violations, print the message with the location's routes and refuse with `_pre_slug_refusal("roadmap-seed-bare-citation")`, returning `False`. `yes` is not consulted, and no prompt is shown, on a TTY or not.
  - This precedes the stale and `malformed` arms, so a seed that is both invalidated and bare-named refuses here. Its `--refresh-seeds` route regenerates under the new contract and clears both conditions. A draft that is `malformed` only because of bare names also refuses here; a draft `malformed` for another reason keeps today's confirmation.
- **Name routes by location.** Build the message in one place, keyed on `location.via_marker`.
  - **Draft:** regenerate with `plan-tool roadmap <slug> --refresh-seeds`, or hand-replace each bare name with the source version's path and run `--accept-seed PLAN_ID`.
  - **Promoted copy:** `--refresh-seeds` rewrites it only when the seed state records `published: true`. Otherwise, or to keep hand edits, hand-replace the bare names in the promoted copy itself. `create` reads that file directly, so no `--accept-seed` is involved.
  - Read `published` from the `load_seed_state` entry. A missing entry counts as not published.
- **Unchanged:** a seed with no bare name goes through today's stale and `malformed` confirmation exactly as before, `-y` included.
- **Not free to vary:**
  - An untracked seed (`location is None`) returns `True` first, unchanged.
  - A roadmap with no accepted head keeps raising `NoPublishedRoadmapVersionError` into the existing refusal, before the bare-name check.
  - `create` never rewrites the seed. No destructive operation.
- **Rejected alternatives:** a confirmation that `-y` answers (lets the bug through in automated runs; rejected by the owner 2026-11-17), and running the full validator on the promoted copy (it judges draft structure a promoted copy need not keep, and would refuse intact promotions).

## Tests

All in `tests/cli/test_authoring_cmds.py`, unless noted.

- `test_draft_legacy_seed_refuses_and_names_draft_routes` — a tracked draft with a bare name refuses with `roadmap-seed-bare-citation`; the text names `--refresh-seeds` and `--accept-seed`.
- `test_promoted_legacy_copy_refuses_and_names_promoted_routes` — a promoted copy with a bare name refuses; the text names `--refresh-seeds` with the `published: true` condition and hand editing the copy, and does not name `--accept-seed`.
- `test_promoted_copy_with_no_bare_name_and_no_provenance_block_does_not_prompt` — a clean promoted copy returns `True` with no prompt.
- `test_dash_y_does_not_override_a_bare_name_refusal` — `yes=True` still returns `False` with `roadmap-seed-bare-citation`, and no prompt is shown.
- `test_bare_name_refusal_needs_no_tty` — a non-TTY run without `-y` refuses with `roadmap-seed-bare-citation`, not `roadmap-seed-not-confirmed`.
- `test_untracked_seed_is_unchanged` — `location=None` returns `True`.
- `test_invalidated_and_bare_named_seed_refuses_on_the_bare_name` — draft and promoted cases: the bare-name refusal wins over the stale confirmation, and `-y` does not continue.
- `test_clean_invalidated_seed_keeps_todays_confirmation` — a stale seed with no bare name still prompts, and `-y` still continues, as at HEAD.
- `test_no_accepted_head_keeps_todays_refusal` — no head refuses as before, and the bare-name check never runs.
- `test_published_flag_selects_the_refresh_wording` — the promoted message differs between `published: true` and not published.
- `test_create_does_not_copy_source_artifacts_frontmatter_into_the_plan` — a tracked seed with `source_artifacts: [04-roadmap.md]` yields a plan with no `source_artifacts` key and no bare member filename taken from it. This pins existing behavior.
- Integration (`@pytest.mark.integration`): `test_regenerated_seed_cites_only_existing_version_store_paths` — a stage-run roadmap with no top-level files plus a stale top-level `04-roadmap.md` beside an accepted head; a seed regenerated with a canned response carries into the plan body only version-store paths that name existing files holding the accepted bytes.

### Tests for this step

Every case above must be green before this step is finished. The invariant cases (`..._does_not_prompt`, `..._is_unchanged`, `..._keeps_todays_refusal`, `..._keeps_todays_confirmation`) are green at HEAD and guard the existing behavior while the edit is made; write them first. The rest need the new branch. Verify the carve-outs by breaking the code each names and watching the test go red.

## Acceptance criteria

- A tracked draft or promoted copy with a bare roadmap file name is refused with `roadmap-seed-bare-citation`, with or without `-y`; the message names that location's repair routes.
- A promoted copy with no bare name and no provenance block does not prompt.
- A seed with no bare name keeps today's confirmation, `-y` included.
- `DATA_CONTRACT.md` lists `roadmap-seed-bare-citation`, and `tests/test_data_contract.py` passes.
- An untracked seed and a no-head roadmap behave as before.
- `create` never writes to the seed file.
- `plan_tool/cli/authoring.py` does not import `plan_tool.cli.app` at module top.
- The full suite passes (`uv run pytest tests/ -q -n auto`).

## References

- [pathlib — Object-oriented filesystem paths (Python 3 docs)](https://docs.python.org/3/library/pathlib.html) — path handling for the promoted copy.
- [pytest documentation — How to use temporary directories and files in tests](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — `tmp_path` for the hermetic roadmap fixtures.
- [pytest documentation — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — parametrizing the location cases.

## Applicable guardrails

- **The plan's "## Scope guardrails":** legacy seed text is not rewritten in place. This step only reads the seed and refuses; the repair routes are operator actions.
- **The plan's "## Out of scope" (new `create` behavior for synthesis prose):** this step checks the seed's citations only. It adds nothing to prose the model writes during `create`.
- **The plan's "## Audit guardrails":** a need for a new link record or a plans directory outside the repository stops the step and goes to the user.

## Deferred

- Bare names in new prose that `create`'s model writes — recorded as a follow-up on the source `BUG_BACKLOG.md` entry.
- Rewriting a legacy seed in place — dropped in the plan's design, see the plan's "## Out of scope".
- Plans already created from bare-name seeds — not migrated; corrected by hand or by re-running `create`.
