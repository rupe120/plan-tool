# Step 4 — Document the version-store citation contract and retire the source backlog entry

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step edits four non-code surfaces so they describe the citation contract steps 1–3 ship. `ROADMAP_FORMAT.md` states the repo-relative version-store citation form and the bare-name rule. It also records that legacy bare-name seeds classify `malformed` and that seed frontmatter never reaches the plan. `docs/how-to/roadmap.md` and `docs/explanations/roadmap-plan-handoff.md` stop treating a bare `0N-*.md` read as the expected path. `BUG_BACKLOG.md` loses the shipped entry and keeps the deferred synthesis-prose follow-up. The key decision is to read every identifier off the landed code, so the docs match HEAD. On green, no live doc tells a seed writer to use a bare filename, the doc-drift guards pass, and the full suite passes.

## Table of Contents

- [Why](#why) — what the docs say today versus the shipped contract
- [Input](#input) — what steps 1–3 land and the doc sites to edit
- [Files (creates vs edits)](#files-creates-vs-edits) — the four files and their edits
- [Implementation](#implementation) — per-file content, the vocabulary sweep, and the backlog edit
- [Tests](#tests) — verification for this non-code step
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — docs behind the facts cited
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

After steps 1–3, a new draft seed cites each roadmap file as `.roadmap-versions/<version-id>/0N-*.md`. The gate rejects a bare member name anywhere in the body, and `create --from-existing` refuses a legacy seed, even under `-y`. The docs still say a draft cites "the four accepted artifacts by filename". They still describe a reader opening a bare `04-roadmap.md` as the expected path. They do not say what happens to legacy seeds. Readers and audits act on the docs, so a stale sentence argues for the bare form. The `BUG_BACKLOG.md` entry also still says the fix is pending.

## Input

- **Steps 1–3 own the code.** Step 1 passes the four member paths into the seed prompt in `plan_tool/roadmap.py:_materialize_plan_seed`. Step 2 adds the References form check and a public text-only bare-name function in `plan_tool/roadmap_gates.py`, called by `validate_draft_seed_content`. Step 3 adds the bare-name refusal, which `-y` does not override, in `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed`.
- **Read names off the landed modules.** At HEAD the step 2 function is not yet in `plan_tool/roadmap_gates.py`. Read its landed name, its violation code constant, and the messages it emits from the module. If they differ from the plan's suggestion, the landed name wins.
- **Doc sites at HEAD** (found by vocabulary, not by identifier):
  - `ROADMAP_FORMAT.md` § "Draft seeds under the roadmap slug": no citation form is stated.
  - `ROADMAP_FORMAT.md` § "Draft-seed manifest states": says the body carries a `## References` section "citing the four accepted artifacts by filename".
  - `docs/how-to/roadmap.md` § 1, "An enrolled folder with leftovers": says "A reader that opens a bare `04-roadmap.md` would ground on the superseded copy".
  - `docs/how-to/roadmap.md` § 7 "Direct fallback": says a seed "cites the four artifacts resolved through the accepted head".
  - `docs/explanations/roadmap-plan-handoff.md` § "References": lists the accepted-store paths, and its `create`, `detail` and `completeness-audit` rows describe References.
  - `BUG_BACKLOG.md`: the entry "Roadmap-derived plans cite bare `0N-*.md` names…" carries the Deferred follow-up bullet.
- **Verification limit:** the checks prove the docs name real symbols and carry no bare-name instruction. They do not prove a real model follows the citation ask.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md`: add the citation contract to § "Draft seeds under the roadmap slug"; add the legacy-seed rule to § "Draft-seed manifest states"; fix the "by filename" clause.
  - `docs/how-to/roadmap.md`: reword the § 1 leftover-files sentence; check § 7 wording.
  - `docs/explanations/roadmap-plan-handoff.md`: describe what References carries in the new form.
  - `BUG_BACKLOG.md`: remove the shipped entry; keep the deferred follow-up as its own entry.

## Implementation

- **`ROADMAP_FORMAT.md` § "Draft seeds under the roadmap slug".** Add a short "Citing roadmap files" block. As bullets, it states:
  - **Form:** a seed names each member file by `.roadmap-versions/<version-id>/0N-*.md`, written relative to the roadmap's repository.
  - **Re-rooting:** the path stays relative to the roadmap's repository even when `create` later re-roots the plan.
  - **Body-wide rule:** a bare member filename (the four constants in `plan_tool/roadmap_artifacts.py`) is a violation anywhere in the body, fenced code included. A path to a top-level copy is also a violation.
  - **Version id:** any stored version id passes, because the gate judges form only.
  - **Older version after promotion:** a seed that cites an older version after a later promotion is intended, not a defect. Cite the gate function and its violation code by their landed names.
  - Do not state that the gate checks a quoted passage against its file. Say it is deliberately not checked, per the plan's "## Out of scope".
- **`ROADMAP_FORMAT.md` § "Draft-seed manifest states".**
  - Replace "by filename" with the version-store form.
  - Add a paragraph: a legacy seed that names a bare member file classifies `malformed`.
  - Name the two repair routes: `--refresh-seeds` regenerates it under the new prompt, or a hand edit plus `--accept-seed PLAN_ID` records it. A hand edit first classifies `digest-mismatched`, as the existing Risks paragraph says.
  - State that a seed's frontmatter never reaches the plan. No module reads a seed's `source_artifacts` key (the name in `plan_tool/roadmap_candidate_run.py` is an unrelated local variable), and `plan_tool/create.py` never reads it. Cite the step 3 "frontmatter" test by its landed name.
  - Name the promoted-copy route in one line: `create --from-existing` refuses a seed with a bare name, with or without `-y` (step 3, reason `roadmap-seed-bare-citation`); repair the promoted copy by hand, or `--refresh-seeds` when the seed is published.
- **`docs/how-to/roadmap.md` § 1.** Keep the facts (leftover files are inert, the stderr warning shipped 2026-10-10). Replace the sentence that frames reading a bare `04-roadmap.md` as the expected path. Say instead that new seeds cite the accepted version's path, so no reader needs the top-level copy, and that the warning still names leftovers. Do not state that deleting leftovers is required.
- **`docs/how-to/roadmap.md` § 7 and "Direct fallback".** Keep "resolved through the accepted head". Add that a hand-written seed uses the same version-store path form, so it passes the gate. Do not tell a writer to use a literal filename.
- **`docs/explanations/roadmap-plan-handoff.md`.** In the References bullet that lists accepted-store paths, say References carries repo-relative version-store paths for each cited member file. Keep the existing `{01-domain,04-roadmap}.md` brace form, since it is already version-store-rooted. Check the `create` row: it says References carry "exact source pointers", which stays true.
- **Vocabulary sweep (not only identifiers).** Run `rg -n -i "literal filename|by filename|bare|0N-\*|0[1-4]-[a-z]+\.md"` over the four files and `SEED_FORMAT.md`, `docs/how-to/pipeline/create-from-existing.md`, and `CAPABILITIES.md`. Decide per hit: update, or keep with a stated reason. Keep unrelated hits ("bare-plan gate", "bare word `security`"). A hit in a file outside the four is out of this step's scope: edit it only if it tells a seed writer to use a bare name, otherwise file it in `BUG_BACKLOG.md`.
- **Do not change `plan_tool/prompts/roadmap-seed.md` or any code.** Step 1 owns the prompt.
- **`BUG_BACKLOG.md`.**
  - Remove the whole "Roadmap-derived plans cite bare `0N-*.md` names…" entry. This is the first action only once steps 1–3 are green; the plan's final docs step is where it ships.
  - Add a new entry for the deferred follow-up: bare roadmap file names in prose `create`'s model writes during synthesis. Give it Files (the `create` prompts under `plan_tool/prompts/`), Symptom, Fix options (a `create` prompt rule or a post-synthesis check), `Route`, `Readiness`, `Tier`, and `Origin` (the removed entry, decided 2026-10-29).
  - Keep the entry forward-looking, with no narration of this plan's work.
  - Check the neighbor entries filed beside it (unbuilt upstream, sibling-created path) stay unchanged.
  - Sweep `BACKLOG.md` and `docs/history/` for pointers to the removed entry title.
- **Doc-drift guards.** `tests/test_roadmap_format.py` checks the artifact examples parse and round-trip, the closed vocabulary literals are real, and the draft-seed provenance examples parse. Do not edit a fenced example unless it parses. Do not add a new fenced `yaml` block with a `roadmap_components` key without confirming `test_draft_seed_provenance_examples_parse` accepts it. Prefer inline code for the citation example.

## Tests

### Verification (non-code step)

This step is `change_type: non-code`, so the test-authoring gate does not apply (it keys on `feature` and `refactor`). The substitute checks are:

1. Run `uv run pytest tests/ -q -n auto`. It must pass, including `tests/test_roadmap_format.py`, `tests/test_data_contract.py` and `tests/cli/test_cli_reference.py`.
2. For every symbol the new doc text names, run `rg -n "<symbol>" plan_tool/`. Each must return a definition at HEAD.
3. Run `rg -n -i "literal filename" ROADMAP_FORMAT.md docs/ SEED_FORMAT.md plan_tool/prompts/roadmap-seed.md`. It must return nothing that tells a writer to use a bare name.
4. Run `rg -n "04-roadmap\.md" docs/how-to/roadmap.md docs/explanations/roadmap-plan-handoff.md`. Review each hit: none tells a reader to open a bare name as the expected path.
5. Run `rg -n "Roadmap-derived plans cite bare" BUG_BACKLOG.md BACKLOG.md docs/`. It must return nothing, and the new follow-up entry must exist.
6. Check every changed heading's anchor with `rg -n "#draft-seed" docs/ README.md`, because no heading is renamed.
7. Run `git diff --stat`. It must list only the four declared files.

## Acceptance criteria

- This step does not run the manual real-model `--materialize` check. The orchestrating session runs it in the post-run tail, records the outcome in the code pull request, and stops and surfaces a fallback to bare names (plan § Testing).
- `ROADMAP_FORMAT.md` § "Draft seeds under the roadmap slug" states the version-store citation form, the repository-relative rule under `create` re-rooting, the body-wide bare-name rule including fenced code, acceptance of any stored version id, and that citing an older version after a later promotion is intended.
- `ROADMAP_FORMAT.md` § "Draft-seed manifest states" says a legacy bare-name seed classifies `malformed`, names both repair routes, says a bare name in a roadmap row value fails materialize until the row is revised through reviewer feedback (a new accepted version), and says seed frontmatter never reaches the plan.
- No sentence in `docs/how-to/roadmap.md` describes opening a bare `04-roadmap.md` as the expected path.
- `docs/explanations/roadmap-plan-handoff.md` says References carries the version-store paths.
- `BUG_BACKLOG.md` has no "Roadmap-derived plans cite bare `0N-*.md` names…" entry and has one new entry for the synthesis-prose follow-up.
- Every symbol the new text cites is found by `rg` in `plan_tool/`.
- `uv run pytest tests/ -q -n auto` passes.
- `git diff --stat` shows only the four declared files.

## References

- [pathlib — Object-oriented filesystem paths (Python 3 docs)](https://docs.python.org/3/library/pathlib.html) — read `PurePath.relative_to` to describe the repository-relative form accurately.
- [CommonMark Spec — Fenced code blocks](https://spec.commonmark.org/0.31.2/#fenced-code-blocks) — read it to word the "fenced code included" rule.

## Applicable guardrails

- **The plan's "## Scope guardrails", no completeness-audit change.** The docs must not claim the audit resolves a citation or checks a quote. State the form check as the only deterministic check.
- **The plan's "## Scope guardrails", legacy text is not rewritten.** The docs describe regeneration or hand repair. They must not describe an in-place rewrite, a deleted leftover file, or a promotion that refreshes top-level files.
- **The plan's "## Scope guardrails", no new `create` synthesis behavior.** The new backlog entry records the gap and must not propose it as shipped.
- **The plan's "## Audit guardrails", sibling-plan problems stay out.** Leave the neighbor entries in `BUG_BACKLOG.md` unchanged. Surface to the user instead of editing if a doc fix would need a link record or a plans directory outside the repository.

## Deferred

- Bare roadmap names in prose `create`'s model writes during synthesis — kept as its own `BUG_BACKLOG.md` entry; closing it needs new `create` behavior the plan's "## Out of scope" refuses.
- Rewriting legacy seed text in place — refused by the plan's "## Out of scope"; regeneration and hand repair are the documented routes.
- Plans already created from bare-name seeds — not migrated; corrected by hand or by re-running `create` from the seed.
- Doc hits outside the four declared files that do not tell a writer to use a bare name — filed in `BUG_BACKLOG.md` if material, not edited here.
