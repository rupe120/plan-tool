# Step 2 — Require version-store paths for roadmap file names in draft seeds

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step tightens `plan_tool/roadmap_gates.py` so a draft seed can name a roadmap member file only by its version-store path, `.roadmap-versions/<version-id>/0N-*.md`. The References gate now requires each of the four member filenames in that form. A new public text-only function, which `validate_draft_seed_content` calls, flags any member filename in the body that lacks that segment. This includes fenced code and paths to a top-level copy. The key decision is that both checks judge only the form of the citation, so neither needs a repo root, an accepted head or a new argument. On green, legacy bare-name seeds classify `malformed`, `--apply` refuses them, `--accept-seed` refuses a hand-edited seed that still has a bare name, and `--refresh-seeds` regenerates them under step 1's contract.

## Table of Contents

- [Why](#why) — what bare names cost and why the gate is the backstop
- [Input](#input) — step 1's output and the existing gate surface this step edits
- [Files (creates vs edits)](#files-creates-vs-edits) — the six files and their edits
- [Implementation](#implementation) — the shared occurrence rule, both checks, callers, and what is not free to vary
- [Tests](#tests) — gate, manifest and roadmap cases, plus the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — docs for regex and fence handling
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

Step 1 makes the seed writer ask for version-store paths. A model can still ignore that ask, and a hand-edited or older seed can still carry bare `01-domain.md`-style names. With an accepted head, top-level `0N-*.md` files are inert and can be stale. A reader or audit that opens a bare name can read stale content. `validate_draft_seed_content` already runs at every route that admits a seed. A form check there closes those routes without a new gate site. Today's References check accepts a bare filename, so the stale-copy citation passes.

## Input

- **Step 1** makes `plan_tool/roadmap.py:_materialize_plan_seed` render version-store paths into the seed prompt. This step depends on it only so regenerated seeds pass the new gate. It reads nothing else from step 1.
- **`plan_tool/roadmap_gates.py:validate_draft_seed_content(text, *, plan)`** has two early returns, for an unmatched fence and for bad provenance. It then collects component-reference violations. After that it runs the References loop over `DOMAIN_FILENAME`, `CONSTRAINTS_FILENAME`, `COMPONENTS_FILENAME` and `PLANS_FILENAME` against `_draft_seed_sections(text)["references"]`. The loop uses the boundary regex `(?<![A-Za-z0-9_.-])name(?![A-Za-z0-9_.-])`. The Risks check comes last.
- **`_draft_seed_sections`** drops fenced code. The new body check must not use it.
- **`plan_tool/roadmap_versions.py`** owns `ROADMAP_VERSION_NAMESPACE_DIRNAME` (`.roadmap-versions`) and `SHA256_DIGEST_RE` (`[0-9a-f]{64}`, ASCII). `roadmap_gates.py` must not import it, so it repeats both as local constants. A test pins them equal.
- **`PlansFILENAME` caveat:** the fourth member filename is the constant named `PLANS_FILENAME` (`04-roadmap.md`).
- **Callers of `validate_draft_seed_content`** at HEAD:
  - `plan_tool/roadmap.py`, four sites (`--accept-seed`, the `--apply` recheck, `_reject_unmatched_operator_draft_fences`, materialize candidate validation).
  - `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds`.
  - `plan_tool/roadmap_view.py` only mentions it in a docstring.
- **Verification limit:** these checks prove form, not meaning. They do not show that a quoted passage matches the cited file.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_gates.py`:
    - add two local constants for the directory name and the digest pattern;
    - add one occurrence helper shared by both checks;
    - add one public text-only body-check function;
    - add a new violation kind constant;
    - change the References loop to require the path form;
    - call the new function from `validate_draft_seed_content`.
  - `plan_tool/roadmap.py`: no production edit is expected, because the four call sites keep working unchanged. Touch it only if a message or help text names the old "literal filename" rule. Confirm by grep.
  - `plan_tool/roadmap_seed_manifest.py`: no production edit is expected. Confirm that `classify_draft_seeds` joins the new messages into the `malformed` detail unchanged.
  - `tests/test_roadmap_gates.py`: add the gate cases and update bare-name fixtures.
  - `tests/test_roadmap_seed_manifest.py`: update `_seed_text` and add the legacy `malformed` case.
  - `tests/test_roadmap.py`: update canned seeds with bare names and add the route cases.

## Implementation

- **One occurrence rule, two consumers.**
  - Write one private helper that finds each member-filename occurrence in a text. It uses the References gate's existing boundary rule, so a name embedded in a longer filename (for example `x01-domain.md` or `01-domain.md.bak`) is not an occurrence.
  - For each occurrence, it reports the filename, its start offset, and whether the text directly before it ends with `.roadmap-versions/<64 lowercase hex>/`.
  - Both checks use this helper. One way: a single compiled alternation over the four filenames.
- **Match exactly the four member filenames.**
  - A name like `01-setup.md` or `05-notes.md` is not an occurrence and must not be flagged.
  - Use the four existing constants, not a `0N-*.md` pattern.
- **Well-formed means form only.**
  - Any lowercase 64-hex id passes. It does not have to be the accepted one, because a hand-edited seed cites the version its text came from.
  - Uppercase hex, 63 or 65 characters, or a missing id segment all fail.
  - The repo-relative prefix before `.roadmap-versions` is step 1's writer's job. The gates must not judge it. Do not read the filesystem or an accepted head.
- **(a) References gate.**
  - Keep `VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE` and its per-filename loop.
  - A filename now counts as present only when the References section has at least one well-formed occurrence of it.
  - Rewrite the message to name the required form `.roadmap-versions/<version-id>/<filename>` instead of "add the literal filename". Keep it self-contained: it names the plan id, the seed basename and the filename.
- **(b) Body check, own violation kind.**
  - Add a new constant, for example `VIOLATION_BARE_ROADMAP_FILE_CITATION`, and one public function, for example `find_bare_roadmap_file_citations(text)`. It returns `list[Violation]` and takes only text.
  - **Scan scope.** Run it over `_strip_frontmatter(text)` with fences kept, so it covers Architecture, Risks, fenced code and every other section. Do not route it through `_draft_seed_sections`.
  - **Rule.** Every occurrence without the well-formed segment directly before it is a violation. This covers a path to a top-level copy such as `docs/.../01-domain.md`, where the last path component is the member name.
  - **Presence check only.** It never judges citation versus mention.
  - **Messages.** Each names the offending occurrence and the path form to use. It has no plan id or row id, because step 3 calls it on a promoted copy that has no provenance block. Use `row_id=None` and `artifact` set the way the module's other row-less violations set it; check `Violation`'s fields at HEAD.
  - **Cardinality.** Emit one violation per offending occurrence. A seed with the same bare name three times reports three. A one-per-defect count would hide the later occurrences from the author.
- **Wiring in `validate_draft_seed_content`.**
  - Call the new function after the References loop, and map its violations onto the plan row the way neighboring violations do (`artifact=PLANS_FILENAME`, `row_id=plan.id`, message prefixed with the plan id and seed basename).
  - Keep the signature. Add no import to `roadmap_gates.py`.
  - The two early returns stay first, so an unmatched fence still returns alone.
- **Interaction to expect.** A seed with a bare name in its References section trips both the References gate (path form absent) and the body check (bare occurrence). Both messages are useful: one says what to add, the other says what to replace. Do not add logic to suppress either.
- **Rejected alternative: resolve each cited path against the accepted version.**
  - It needs a repo root and the loaded head, and it fails for a no-head roadmap.
  - It also rejects a hand-edited seed that cites the version its text came from, which the plan allows.
  - The fixed form check delivers the property: only version-store citations reach a plan.
- **Rejected alternative: a regex that matches any `0N-*.md`.** It would flag unrelated files. The plan names the four members.
- **Destructive operations and caller effects.**
  - `--refresh-seeds` and `--materialize` still overwrite the draft, hand edits included, and still keep the `seed-refresh-report.md` diff. `--apply` still copies only admitted seeds. Nothing in this step deletes or rewrites a seed.
  - The gates are unconditional. A roadmap with no accepted head never reaches them: every seed route loads the accepted plans artifact first and refuses with `NoPublishedRoadmapVersionError`, as today. The no-head test must show that refusal is unchanged and that no new head lookup or error appears.
  - Legacy bare-name seeds classify `malformed` in `--view` via `classify_draft_seeds`, `--apply` refuses them through its recheck, and `--accept-seed` refuses a seed that still has a bare name.
  - A seed whose names were replaced is accepted.
- **Sweep for siblings.**
  - Grep `plan_tool/` and `tests/` for the old message wording ("add the literal filename") and for bare `01-domain.md`-style names in canned seeds.
  - Grep the docs the class touches: `ROADMAP_FORMAT.md` and `docs/how-to/roadmap.md` describe the draft-seed References contract. They are outside this step's file list, so route any needed wording change to the docs step. Record the finding in `## Deferred`; do not edit them here.

## Tests

- `tests/test_roadmap_gates.py`, `tests/test_roadmap_seed_manifest.py` and `tests/test_roadmap.py` are the three files.

### Tests for this step

`tests/test_roadmap_gates.py`:

- `test_bare_member_name_in_architecture_is_rejected` — a bare filename in an `## Architecture` section yields the new violation kind.
- `test_bare_member_name_in_risks_is_rejected` — the same in `## Risks`.
- `test_bare_member_name_inside_a_fence_is_rejected_deliberately` — a bare name in fenced code still fails. Name states that the body check keeps fences on purpose, unlike `_draft_seed_sections`.
- `test_top_level_copy_path_is_rejected_by_its_last_component` — `docs/x/01-domain.md` fails because no version segment precedes the name.
- `test_non_accepted_version_id_is_accepted` — a path with any well-formed 64-hex id passes both checks; the gate never compares against an accepted id.
- `test_malformed_version_id_is_rejected` — uppercase hex, 63 hex characters, or a missing id segment fails.
- `test_references_message_names_the_required_path_form` — the missing-reference message contains `.roadmap-versions/<version-id>/` and the filename, and no longer says "literal filename".
- `test_required_paths_never_trip_the_body_check` — a seed that cites all four members by version-store path yields no body-check violations, including inside a fence.
- `test_non_member_numbered_filename_is_not_flagged` — `01-setup.md` produces no violation. The carve-out is deliberate, so it is asserted.
- `test_name_embedded_in_a_longer_filename_is_not_an_occurrence` — `x01-domain.md` and `01-domain.md.bak` are not flagged, matching the References boundary rule.
- `test_body_check_takes_only_text_and_needs_no_provenance` — call the public function on text with no provenance block; it returns violations without raising. This pins step 3's reuse.
- `test_one_violation_per_offending_occurrence` — three bare occurrences yield three violations.
- `test_gate_constants_equal_roadmap_versions_originals` — the local directory name and digest pattern equal `ROADMAP_VERSION_NAMESPACE_DIRNAME` and `SHA256_DIGEST_RE.pattern`.

`tests/test_roadmap_seed_manifest.py`:

- `test_classify_malformed_for_a_legacy_bare_name_seed` — a seed with bare names in References and digest matching state classifies `DRAFT_SEED_STATE_MALFORMED`, and the detail names the path form.
- Update `_seed_text` to cite version-store paths, so the existing `current` cases stay green. These reds are expected sibling updates.

`tests/test_roadmap.py`:

- `test_apply_refuses_a_legacy_bare_name_seed` — `--apply` refuses it and copies nothing.
- `test_refresh_seeds_regenerates_a_legacy_seed_under_the_new_contract` — `--refresh-seeds` replaces the bare-name draft with a conforming canned response, and the `seed-refresh-report.md` diff is still written.
- `test_accept_seed_refuses_a_hand_edited_seed_with_a_bare_name` — acceptance fails with the new message.
- `test_accept_seed_accepts_a_seed_whose_names_were_replaced` — the same seed with version-store paths is accepted.
- `test_roadmap_without_an_accepted_head_keeps_todays_behavior` — a no-head roadmap still refuses with `NoPublishedRoadmapVersionError` before any gate runs.
- Update the canned seed fixtures that use bare names.

**Green-before-done gate:** every test above must be green, plus the full existing suites for the three files, before this step is finished. Run `tests/test_duplication.py` too, because the new helper must not duplicate an existing function body. Expect red sibling tests during the fixture sweep. Read each one to decide whether it is a missed fixture or a genuine carve-out.

## Acceptance criteria

- A draft seed whose body names any of the four member files without `.roadmap-versions/<64 lowercase hex>/` directly before it returns at least one violation of the new kind.
- A seed whose every member-file name carries that segment returns no violation of the new kind or of `VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE`.
- `01-setup.md` and other non-member names produce no violation.
- The References message names the required path form.
- The new public function takes only text and works on text without provenance.
- `validate_draft_seed_content` keeps its signature, and `roadmap_gates.py` gains no import.
- `rg -n "roadmap_versions" plan_tool/roadmap_gates.py` returns nothing.
- `classify_draft_seeds` returns `malformed` for a legacy bare-name seed, and `current` for a conforming one.
- `--apply`, `--accept-seed` and `--refresh-seeds` behave as listed under Implementation.
- The test files above pass, including the constant-equality test.

## References

- [re — Regular expression operations (Python 3 docs)](https://docs.python.org/3/library/re.html) — pattern syntax and `finditer` semantics for the occurrence helper and its lookbehind boundary.
- [CommonMark Spec — Fenced code blocks](https://spec.commonmark.org/0.31.2/#fenced-code-blocks) — why fenced text must still be scanned by the body check.
- [pytest — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — compact form for the section, fence and top-level-path cases.

## Applicable guardrails

- **The plan's "## Scope guardrails" (no new check that a quoted passage matches its cited file):** the checks judge only whether a name has the path form. They must not compare quoted text with file content.
- **The plan's "## Scope guardrails" (legacy seed text is not rewritten, nothing deleted):** this step adds no code that edits or deletes a seed or a top-level `0N-*.md` file. Legacy seeds become `malformed` and are repaired by `--refresh-seeds`.
- **The plan's "## Audit guardrails" (stop if resolution needs a new link record, a layout change, or a plans directory outside the repository):** form checking needs none of these. If implementation seems to need one, stop and surface it.
- **The plan's "## Out of scope" (completeness audit and prompts, prose `create` writes during synthesis):** no change to audit code or prompts, and no new `create` behavior.

## Deferred

- Docs wording for the References contract in `ROADMAP_FORMAT.md` and `docs/how-to/roadmap.md` — outside this step's file list; routed to the plan's docs step.
- Step 3's promoted-copy check — it calls the new public function from this step; its wiring belongs to step 3.
- Comparing a cited version id with the accepted one — refused by design, since a hand-edited seed cites the version its text came from.
- Checking that a quoted passage matches its cited file — the semantic property the plan refuses.
