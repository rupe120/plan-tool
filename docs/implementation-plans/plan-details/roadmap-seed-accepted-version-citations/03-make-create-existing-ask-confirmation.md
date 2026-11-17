# Step 3 — Ask for confirmation on a tracked seed that fails the bare-name check, and name both repair routes

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed` stop and ask when a tracked seed still names a roadmap member file without its version-store path. A draft seed reaches the prompt through `classify_draft_seeds` once step 2 makes it `malformed`. A promoted `plan-seeds/` copy has no such route, so the step runs step 2's text-only bare-name function on the copy's own bytes. The key decision is that the prompt text and the non-TTY refusal both name the repair routes for that seed's location (draft or promoted). On green, a legacy seed is never carried into a plan silently: the operator regenerates it, repairs it, or confirms with `-y`.

## Table of Contents

- [Why](#why) — what the promoted copy skips today
- [Input](#input) — step 2's function and the existing confirmation flow
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files and their edits
- [Implementation](#implementation) — the promoted-copy check, per-location messages, constraints
- [Tests](#tests) — unit, route and integration cases, plus the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — docs for the tools this step uses
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

Step 2 makes a draft seed with a bare name `malformed`, so the draft path already prompts. A promoted copy is judged only by the sidecar's `invalidated` status, so a legacy promoted copy with bare names passes silently into `create`. `create` then copies seed sections into the plan, and a reader or audit that opens a bare name can read a stale top-level `0N-*.md` beside the accepted head. This step closes that route with a confirmation.

## Input

- **Step 2** adds a public text-only function in `plan_tool/roadmap_gates.py` (the plan suggests `find_bare_roadmap_file_citations(text)`, returning `list[Violation]`). Read the landed name from the module; the landed name wins. It needs no repo root or accepted head.
- **`_confirm_invalidated_roadmap_seed(location, *, yes, input_fn=input)`** already loads the accepted version, finds the plan row, and splits on `location.via_marker`. The draft arm calls `classify_draft_seeds`. The promoted arm reads only `load_seed_state(location.state_path)["seeds"]` for `status == "invalidated"`.
- **`cmd_create`** calls `locate_tracked_seed(source_path, repo_root=repo_root)`, then this function, and returns 2 on refusal. `PRE_SLUG_REFUSAL_REASONS` already holds `roadmap-seed-not-confirmed`; this step adds no reason.
- **`TrackedSeedLocation`** (`plan_tool/roadmap_seed_state.py`) carries `plan_id`, `roadmap_slug`, `state_path`, `via_marker`. The seed state entry carries a `published` bool.
- **`source_artifacts`** appears in `plan_tool/roadmap_candidate_run.py` only; `plan_tool/create.py` never reads it. The frontmatter case below pins that `create` does not copy it, with no new code.
- **Verification limit:** these checks prove citation form, not that a quoted passage matches the cited file.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py`: in `_confirm_invalidated_roadmap_seed`, run the bare-name function on the promoted copy's bytes, add the bare-name message arm with per-location routes, and update the function docstring.
  - `tests/cli/test_authoring_cmds.py`: add cases to `TestRoadmapSeedConfirmation` (reuse its `_write_tracked_draft` helper) and one integration case.

## Implementation

- **Promoted copy: check its own bytes.**
  - In the `location.via_marker` arm, read the promoted copy's text and call step 2's function. The location has no promoted path, so find the path through the same lookup `locate_tracked_seed` used (likely via `_TRACKED_SEED_MARKER_RE` and the source path passed in). Simplest: pass the source path from `cmd_create` as a new keyword argument (for example `seed_text`), since `cmd_create` already holds the seed's text. Prefer that over a second file read.
  - Judge the whole text, not `_read_seed_body` output, so a bare name in the provenance block counts. Do not run `validate_draft_seed_content`; a promoted copy is not a draft.
- **One bare-name state.**
  - Treat "bare names found" as its own non-current reason beside the draft state and the stale state. For a draft, step 2's `malformed` classification carries the cause in `classification.detail`.
  - A seed that is both `invalidated` and bare keeps the stale wording; the bare-name routes apply only when the seed is otherwise current or `malformed` for this cause.
- **Name routes by location.** Build the message in one place, keyed on `location.via_marker`.
  - **Draft:** regenerate with `plan-tool roadmap <slug> --refresh-seeds`, or hand-replace each bare name with the source version's path and run `--accept-seed PLAN_ID`.
  - **Promoted copy:** `--refresh-seeds` rewrites it only when the seed state records `published: true`. Otherwise, or to keep hand edits, hand-replace the bare names in the promoted copy itself. `create` reads that file directly, so no `--accept-seed` is involved.
  - Read `published` from the same `load_seed_state` entry already loaded in that arm. A missing entry counts as not published.
- **Prompt and refusal.**
  - `-y` prints the message and continues. A non-TTY run without `-y` prints the message with the routes and refuses with `roadmap-seed-not-confirmed`, as the existing refusal does. The existing non-TTY text points only at `--refresh-seeds`; make it use the per-location routes for this reason.
- **Not free to vary:**
  - An untracked seed (`location is None`) returns `True` first, unchanged.
  - A roadmap with no accepted head keeps raising `NoPublishedRoadmapVersionError` into the existing refusal, before the bare-name check.
  - `create` never rewrites the seed. No destructive operation.
- **Rejected alternative:** running the full validator on the promoted copy. It judges draft structure that a promoted copy need not keep, and would refuse intact promotions.

## Tests

All in `tests/cli/test_authoring_cmds.py`, unless noted.

- `test_draft_legacy_seed_prompts_and_names_draft_routes` — a tracked draft with a bare name prompts; the text names `--refresh-seeds` and `--accept-seed`.
- `test_promoted_legacy_copy_prompts_and_names_promoted_routes` — a promoted copy with a bare name prompts; the text names `--refresh-seeds` with the `published: true` condition and hand editing the copy, and does not name `--accept-seed`.
- `test_promoted_copy_with_no_bare_name_and_no_provenance_block_does_not_prompt` — a clean promoted copy returns `True` with no prompt.
- `test_dash_y_continues_on_a_bare_name_seed` — `yes=True` returns `True` and prints the message.
- `test_non_tty_without_dash_y_refuses_a_bare_name_seed` — returns `False` with `roadmap-seed-not-confirmed`, and the message names the location's routes.
- `test_untracked_seed_is_unchanged` — `location=None` returns `True`.
- `test_invalidated_and_bare_named_promoted_copy_shows_only_the_stale_message` — the stale message wins, matching the draft classifier's first-match order; the bare-name routes are not added.
- `test_no_accepted_head_keeps_todays_refusal` — no head refuses as before, and the bare-name check never runs.
- `test_published_flag_selects_the_refresh_wording` — the promoted message differs between `published: true` and not published.
- `test_create_does_not_copy_source_artifacts_frontmatter_into_the_plan` — a tracked seed with `source_artifacts: [04-roadmap.md]` yields a plan with no `source_artifacts` key and no bare member filename taken from it. This pins existing behavior.
- Integration (`@pytest.mark.integration`): `test_regenerated_seed_cites_only_existing_version_store_paths` — a stage-run roadmap with no top-level files plus a stale top-level `04-roadmap.md` beside an accepted head; a seed regenerated with a canned response carries into the plan body only version-store paths that name existing files holding the accepted bytes.

### Tests for this step

Every case above must be green before this step is finished. The invariant cases (`..._does_not_prompt`, `..._is_unchanged`, `..._keeps_todays_refusal`) are green at HEAD and guard the existing behavior while the edit is made; write them first. The rest need the new branch. Verify the carve-outs by breaking the code each names and watching the test go red.

## Acceptance criteria

- A tracked draft or promoted copy with a bare roadmap file name prompts; the message names that location's repair routes.
- A promoted copy with no bare name and no provenance block does not prompt.
- `-y` continues; a non-TTY run without `-y` refuses with `roadmap-seed-not-confirmed`.
- An untracked seed and a no-head roadmap behave as before.
- `create` never writes to the seed file.
- `plan_tool/cli/authoring.py` does not import `plan_tool.cli.app` at module top.
- The full suite passes (`uv run pytest tests/ -q -n auto`).

## References

- [pathlib — Object-oriented filesystem paths (Python 3 docs)](https://docs.python.org/3/library/pathlib.html) — path handling for the promoted copy.
- [pytest documentation — How to use temporary directories and files in tests](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — `tmp_path` for the hermetic roadmap fixtures.
- [pytest documentation — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — parametrizing the location cases.

## Applicable guardrails

- **The plan's "## Scope guardrails":** legacy seed text is not rewritten in place. This step only reads the seed and asks; the repair routes are operator actions.
- **The plan's "## Out of scope" (new `create` behavior for synthesis prose):** this step checks the seed's citations only. It adds nothing to prose the model writes during `create`.
- **The plan's "## Audit guardrails":** a need for a new link record or a plans directory outside the repository stops the step and goes to the user.

## Deferred

- Bare names in new prose that `create`'s model writes — recorded as a follow-up on the source `BUG_BACKLOG.md` entry.
- Rewriting a legacy seed in place — dropped in the plan's design, see the plan's "## Out of scope".
- Plans already created from bare-name seeds — not migrated; corrected by hand or by re-running `create`.
