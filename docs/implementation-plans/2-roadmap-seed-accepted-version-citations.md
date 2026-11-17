---
format_version: 1
title: Roadmap Seed Accepted Version Citations
intent: A plan derived from a roadmap draft seed cites the accepted roadmap version
  it was derived from, so a completeness audit or a reader opening a cited roadmap
  artifact reads the accepted content and never an inert top-level `0N-*.md` copy
  left beside the accepted head.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/roadmap-seed-accepted-version-citations.md
steps:
- id: 1
  intent: Newly written draft seeds name the accepted version's stored files, so anything
    copied from them points at accepted content.
  files:
  - plan_tool/roadmap.py
  - plan_tool/prompts/roadmap-seed.md
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-seed-accepted-version-citations/01-make-seed-writer-cite-each-roadmap-file.md
  status: current
  description: 'Make the seed writer cite each roadmap file by its repo-relative version-store
    path. In `plan_tool/roadmap.py`, `_materialize_plan_seed` already reads `loaded`
    through `load_accepted_roadmap_artifacts`, and each `_LoadedArtifact.path` is
    already the accepted version''s stored member file. Turn those four paths into
    repo-root-relative strings and pass them to `_render_seed_materialize_prompt`
    as new template variables, so the paths come from the same read as the artifact
    text. If the plans directory is outside `repo_root`, no repo-relative path exists,
    so stop with a `RoadmapError` that names the problem; do not fall back to a bare
    name. Rewrite `plan_tool/prompts/roadmap-seed.md` so it asks for those exact paths
    everywhere a roadmap file is named in the seed body (References, Architecture,
    Risks, fenced text included), not only in `## References`, including a member filename
    that appears in accepted artifact text the writer carries over: the prompt tells
    the writer to replace each such name with its version-store path. A response that
    still fails the gates after the bounded retry is the existing materialize failure.
    Drop the ''cite by
    their literal filenames'' wording. The `### 01-domain.md` … `### 04-roadmap.md`
    input headings may keep the bare member names because they label prompt inputs,
    not seed text. The prompt still never asks for a `source_artifacts` key. Tests
    in `tests/test_roadmap.py`: the rendered prompt contains each version-store path
    and leaves no unresolved `${`; every placeholder the template uses is a key the
    caller supplies; a canned conforming response with version-store paths passes
    today''s gates and is written. Destructive operations: none change. The materialize
    write path still replaces the draft atomically, exactly as today.'
- id: 2
  intent: Only seeds whose every roadmap file name is a version-store path pass, so
    a bare or top-level citation can no longer reach a plan through the roadmap routes.
  files:
  - plan_tool/roadmap_gates.py
  - plan_tool/roadmap.py
  - plan_tool/roadmap_seed_manifest.py
  - tests/test_roadmap_gates.py
  - tests/test_roadmap_seed_manifest.py
  - tests/test_roadmap.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: The writer already emits version-store paths, so tightening the gates does
      not break materialization.
  detail: docs/implementation-plans/plan-details/roadmap-seed-accepted-version-citations/02-tighten-draft-seed-gates-plan-tool.md
  description: 'Tighten the draft-seed gates in `plan_tool/roadmap_gates.py:validate_draft_seed_content`.
    The check matches exactly the four member filenames (`01-domain.md`, `02-constraints.md`,
    `03-components.md`, `04-roadmap.md`, the constants the References gate already
    uses); another file whose name starts `0N-` is deliberately not flagged. Both
    checks judge the citation''s form only, so they need no repo root: an occurrence
    of a member filename passes exactly when `.roadmap-versions/<version-id>/` directly
    precedes it, for any well-formed version id: a lowercase 64-hex SHA-256 digest,
    the form `roadmap_versions.SHA256_DIGEST_RE` accepts, under the `.roadmap-versions`
    directory (`ROADMAP_VERSION_NAMESPACE_DIRNAME`). The gate repeats both facts as
    local constants, and a test pins them equal to the `roadmap_versions` originals.
    The id does not have to be the accepted one, because a hand-edited seed cites
    the version its text came from. The repo-relative prefix in front of that segment
    is step 1''s writer''s responsibility, not the gates''. (a) The References gate
    (`VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE`) requires each member filename
    in that form; its message names the required path form instead of ''add the literal
    filename''. (b) Add a body check with its own violation kind: any member-filename
    occurrence anywhere in the seed body, fenced code included, without that segment
    directly before it is a violation. That covers a path to a top-level copy. It
    is a plain presence check that never judges citation versus mention. It lives
    in one public function in `roadmap_gates.py` that takes only text: it scans the
    frontmatter-stripped text (`_strip_frontmatter`) with fenced code kept, unlike
    `_draft_seed_sections`, which excises fences, and finds member filenames with
    an occurrence rule shared with the References gate: no `[A-Za-z0-9_.-]`
    directly before the name, and after it neither `[A-Za-z0-9_-]` nor a `.` followed by
    a letter or digit. A name embedded in a longer filename is therefore not an occurrence,
    while a sentence-final period does not hide one (the References gate''s current
    lookahead treats any following `.` as part of a longer name, and is replaced by this rule). `validate_draft_seed_content` calls it,
    and step 3 calls it directly on a promoted copy, which has no provenance block
    for the full validator to read. Each message names the offending occurrence and
    the path form to use. `validate_draft_seed_content` keeps its signature, so every
    existing caller (the four `roadmap.py` sites: `--accept-seed`, the `--apply` post-classification
    recheck, `_reject_unmatched_operator_draft_fences`, materialize candidate validation;
    and `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds`) gets the new checks
    without a new argument, and `roadmap_gates.py` gains no import. Legacy bare-name
    seeds then classify `malformed` in `--view`, `--apply` refuses them, `--accept-seed`
    refuses a hand-edited seed that still has a bare name and accepts one whose names
    were replaced, and `--refresh-seeds` regenerates them under step 1''s contract.
    Destructive operations: `--refresh-seeds`/`--materialize` still overwrite the
    draft, hand edits included, and keep the `seed-refresh-report.md` diff. `--apply`
    still copies only admitted seeds. Nothing new deletes or rewrites a seed. Tests:
    `tests/test_roadmap_gates.py` covers rejection in Architecture, in Risks, inside
    a fence, and as the last component of a top-level-copy path; acceptance of a non-accepted
    version id; the References message naming the path; a case pinning that the required
    paths never trip the body check; and a case pinning that a non-member `0N-` filename
    such as `01-setup.md` is not flagged; and a case where an accepted row value names
    a member file, so the tool-written `## Stack` section fails materialize closed with
    a message naming the section and the roadmap-revision route. `tests/test_roadmap_seed_manifest.py` and
    `tests/test_roadmap.py` cover the legacy `malformed` classification, `--apply`
    refusal, `--refresh-seeds` repair, the two `--accept-seed` cases, and a roadmap
    with no accepted head still refusing before any gate runs, as today. Update the existing canned seed
    fixtures that use bare names; those reds are expected sibling updates.'
- id: 3
  intent: 'A seed written before the change never becomes a plan, even in an unattended
    `-y` run, until the operator regenerates or repairs it.'
  files:
  - plan_tool/cli/authoring.py
  - tests/cli/test_authoring_cmds.py
  - DATA_CONTRACT.md
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Provides the text-only bare-name function that create's refusal calls.
  detail: docs/implementation-plans/plan-details/roadmap-seed-accepted-version-citations/03-make-create-existing-ask-confirmation.md
  description: 'Make `create --from-existing` refuse a tracked seed that fails the
    bare-name check, with or without `-y`, and name its repair routes (owner decision,
    2026-11-17: automated sessions always pass `-y`, so a confirmation `-y` answers
    would let the bug through in hands-off runs). In `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed`,
    for every tracked seed, run step 2''s text-only bare-name function on the exact
    bytes `create` will read (the draft, or the promoted `plan-seeds/` copy for `location.via_marker`)
    before the existing stale and `malformed` confirmation; the full validator is not
    run on a promoted copy. On a bare name, refuse with a new pre-slug reason token,
    `roadmap-seed-bare-citation`, added to `PRE_SLUG_REFUSAL_REASONS` and to `DATA_CONTRACT.md`;
    `yes` is not consulted. A seed that is both invalidated and bare-named refuses
    on the bare name; its `--refresh-seeds` route clears both. The message names the
    routes for the seed''s location. For a draft: regenerate with `plan-tool roadmap
    <slug> --refresh-seeds`, or hand-replace each bare name with the source version''s
    path and run `--accept-seed PLAN_ID`. For a promoted copy: `--refresh-seeds` rewrites
    it only when the seed''s state records `published: true`; otherwise, or to keep
    hand edits, hand-replace the bare names in the promoted copy itself, which `create`
    reads directly, so no `--accept-seed` is involved. A seed with no bare name keeps
    today''s confirmation, `-y` included. An untracked seed, and a roadmap with no
    accepted head, keep today''s behavior. Destructive operations: none; `create` reads
    the seed and never rewrites it. Tests in `tests/cli/test_authoring_cmds.py`: the
    draft legacy seed and the promoted legacy copy each refuse with the new token and
    name their location''s routes; `-y` does not override the refusal; a non-TTY run
    refuses with the new token; an invalidated, bare-named seed refuses on the bare
    name; a clean invalidated seed keeps today''s confirmation; a promoted copy with
    no bare name and no provenance block does not prompt; untracked and no-head cases
    are unchanged; a tracked seed whose frontmatter carries `source_artifacts: [04-roadmap.md]`
    yields a plan with no `source_artifacts` key and no bare member filename copied
    from it. One integration case covers a stage-run roadmap with no top-level files
    plus a stale top-level `04-roadmap.md` beside an accepted head: a seed regenerated
    with a canned response carries into the plan body only version-store paths that
    name existing files holding the accepted bytes.'
- id: 4
  intent: Keeps the format contract, how-to, handoff explanation and backlog consistent
    with the shipped citation form, so readers and audits act on the current design.
  files:
  - ROADMAP_FORMAT.md
  - docs/how-to/roadmap.md
  - docs/explanations/roadmap-plan-handoff.md
  - BUG_BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    2: The shipped gate names and messages are what the format doc describes.
    3: The create refusal is what the manifest-states section and the backlog removal
      depend on.
  detail: docs/implementation-plans/plan-details/roadmap-seed-accepted-version-citations/04-bring-docs-backlog-line-new-citation.md
  description: 'Bring the docs and the backlog in line with the new citation contract.
    `ROADMAP_FORMAT.md` § ''Draft seeds under the roadmap slug'' states the repo-relative
    version-store citation form, that a cited path is relative to the roadmap''s repository
    even when `create` later re-roots the plan, the body-wide bare-name rule over
    the four member filenames (fenced code included), that any stored version id is
    accepted, and that a cited path naming an older version after a later promotion
    is intended, not a defect. § ''Draft-seed manifest states'' records that legacy
    bare-name seeds classify `malformed`, with the two repair routes, that a bare name
    in a roadmap row value fails materialize until the row is revised through reviewer
    feedback, and that a seed''s
    frontmatter never reaches the plan (Architecture, `source_artifacts`). `docs/how-to/roadmap.md`
    § 1''s leftover-files paragraph stops describing a reader opening a bare `04-roadmap.md`
    as the expected path. `docs/explanations/roadmap-plan-handoff.md` describes what
    References carries in the new form. Sweep these surfaces by vocabulary (''literal
    filename'', ''bare'', `0N-*.md`), not only by identifier, and keep the doc-drift
    guards in `tests/test_roadmap_format.py` green. Once the work has fully shipped,
    remove the source `BUG_BACKLOG.md` entry (''Roadmap-derived plans cite bare `0N-*.md`
    names…''). Keep, or re-file as its own entry, the deferred follow-up about bare
    names in prose `create`''s model writes during synthesis. Verification for this
    non-code step: the full suite passes with `uv run pytest tests/ -q -n auto`, every
    symbol cited in the docs exists (checked with `rg`), and no doc still tells a
    seed writer to use a literal bare filename. This step does not perform the manual
    real-model `--materialize` check; it hands it off to the post-run tail (Testing).'
---
# Roadmap Seed Accepted Version Citations

## Overview

Draft seeds that the `roadmap` verb writes will cite each roadmap file by its repo-relative version-store path, such as `docs/implementation-plans/roadmaps/<slug>/.roadmap-versions/<version-id>/04-roadmap.md`, instead of a bare `01-domain.md` … `04-roadmap.md` filename. `create` copies a seed's body sections into the plan. With this change, a completeness audit or a reader who opens a cited roadmap file reads the accepted content, never an inert top-level `0N-*.md` copy. The draft-seed gates in `plan_tool/roadmap_gates.py` enforce the new form. Legacy seeds that still use bare names are cleared through existing routes (regenerate, or hand-edit and `--accept-seed`) and are never rewritten by the tool. No completeness-audit or prompt change is part of this work.

## Problem statement

Plans derived from roadmaps cite bare `0N-*.md` names. Beside an accepted head, those names resolve to stale top-level copies, so audits ground on a superseded roadmap and report false contradictions (`BUG_BACKLOG.md`, Route: plan, no Jira ticket yet). This is the observed symptom.

The defect is in the citation contract, not in any one reader. `plan_tool/prompts/roadmap-seed.md` asks for bare filenames. The References gate (`VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE`) accepts a bare filename, and its retry message tells the seed writer to "add the literal filename", which steers it back to the old form. `create` copies seed body sections into the plan, so a bare name in Architecture or Risks reaches the audit just as surely as one in References.

The problem affects every roadmap, not only older folders with leftovers. A stage run publishes no top-level `0N-*.md` files (`ROADMAP_FORMAT.md` § "What writes them"), so in a roadmap created that way a bare-name citation names no file at all.

## Architecture

**Settled: the seed writer owns the fix.** Promotion changes only the accepted-head selector, and that stays so. The citation contract changes. No command is taught to find a "better" copy of a bare name at read time.

**Settled: the citation form is the repo-relative version-store path** of the member file: `stored_artifact_path(...)` made relative to the repository root, e.g. `docs/implementation-plans/roadmaps/<slug>/.roadmap-versions/<version-id>/04-roadmap.md` when the plans directory is `docs/implementation-plans/`. The path is repo-relative because plans and promoted seed copies live outside the roadmap folder, so a roadmap-relative path would resolve to no file from either place. Rejected: the version id plus the member name. That form would need a resolver at read time, and the audit model opens files by path and has no roadmap resolution.

**Settled: one lookup, no second resolver.** The seed writer's paths come from `load_accepted_version` and `stored_artifact_path` in `plan_tool/roadmap_versions.py`, at the moment the seed is written, so each path names the version its text was generated from. The seed writer is given those paths; it does not derive them.

**Draft-seed contract.** `plan_tool/prompts/roadmap-seed.md` has the seed name the accepted version's member files by their version-store paths everywhere in the seed body, not only in `## References`.

**Draft-seed gates (`plan_tool/roadmap_gates.py`).**
- Both gates match exactly the four member filenames, `01-domain.md` through `04-roadmap.md`. Another file whose name starts `0N-` is deliberately not flagged.
- Both gates are unconditional: they run wherever `validate_draft_seed_content` runs today. Every seed route, and `create`'s confirmation, already refuses with `NoPublishedRoadmapVersionError` before any gate when no accepted head exists, so "a roadmap with no accepted head keeps today's behavior" means that refusal stays as it is; no gate is switched off by head state.
- The tool-written `## Stack` section is checked like the rest of the body. `_render_stack_section` copies accepted row values verbatim and names no member file in its own template text, so a bare name there can only come from a roadmap row value. Such a seed fails materialize closed, with a message naming the section and the route: revise that row through reviewer feedback (`docs/how-to/roadmap.md` § 6), which publishes a new accepted version, then regenerate; accepted versions are immutable, so `--refresh-seeds` alone fails the same way every time. Deliberately not done: rewriting row text in the renderer (a new rewrite path), or exempting the section (a bare name would then reach the plan).
- Both gates judge the citation's form, not its root: a member filename passes exactly when `.roadmap-versions/<version-id>/` directly precedes it. They take no repo root and keep their current signature at every caller. The repo-relative prefix is the seed writer's responsibility: the writer has `repo_root` and refuses a plans directory outside it. A cited path is relative to the roadmap's repository, and `create` carries seed text verbatim, so the path keeps that meaning even when `create` re-roots the plan under an umbrella root. Deliberately not checked by the gates: whether a hand-edited prefix resolves. A non-resolving path names no top-level copy, so the Guarantee holds, and the plan's existing cited-path check reports it as missing.
- The References gate (`VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE`) requires the version-store form, and its message names that form.
- A new body check makes a bare member filename anywhere in the seed body a violation, fenced code included. It is one text-only function that scans the frontmatter-stripped text with fences kept and uses one occurrence rule shared with the References gate (no `[A-Za-z0-9_.-]` before the name; after it, neither `[A-Za-z0-9_-]` nor `.` plus a letter or digit), so a longer filename is not an occurrence and a sentence-final period does not hide one; the full validator and `create`'s check on a promoted copy both call it. `create` copies fenced text into the plan verbatim, so a fence is no safer than prose. Bare means any occurrence whose path does not contain `.roadmap-versions/<version-id>/`. A path to a top-level copy therefore counts as bare, and the required paths never trip the check. This is a plain presence check: it rejects every bare occurrence and never judges whether an occurrence is a citation or a mention.
- Both gates accept a version-store path naming any stored version, not only the accepted one. The hand-edit route cites the version a seed's text was written from, which can be older than the accepted head.

**`source_artifacts`.** This deliberately departs from the source entry's Fix, which renders that key in the new form too. The prompt never asks for the key, and `parse_draft_seed_provenance` ignores it (`roadmap_components` and `cross_cutting` are its only keys), so the seed body stays the one citation surface. A stray `source_artifacts` key, bare name included, cannot reach a plan, and the guarantee depends on that: plan frontmatter is serialized only by `write_plan` from the `Plan` schema, which forbids extra fields, and the sections `create` copies come from frontmatter-stripped seed text (`_strip_frontmatter`). Step 3 pins it with a test. Bare names the model might write from frontmatter into new prose are the deferred synthesis case, not this one.

**Guarantee: "the audit never grounds on a top-level copy of a cited roadmap artifact."** Mechanism: every roadmap file name in a seed that passes the draft-seed gates is a version-store path, and `create` copies seed text into the plan. Owners: the seed writer and the draft-seed gates. Order: the draft-seed contract and gates change first, then `create`'s refusal of a tracked seed that fails the check.

**Legacy seeds.** A seed written before the change fails the bare-name check. The tool never rewrites it in place. Two existing routes clear it:
- **Regenerate** with `--refresh-seeds` or `--materialize`. This writes the seed under the new contract against the accepted version and replaces any hand edit in it; `seed-refresh-report.md` keeps a diff from the last generation.
- **Hand-edit and accept**, for a seed whose hand edits should survive. The operator replaces each bare name with the path of the version the seed's text was written from (older versions stay in the version store), then runs `--accept-seed PLAN_ID`. `--accept-seed` already runs `validate_draft_seed_content` before recording the edit, so a seed that still has a bare name is refused. When the source version is unknown, regenerate instead.

Until one of these routes runs, `--view` shows the seed as `malformed` (or `digest-mismatched` once hand-edited), and `--apply` refuses it. `create --from-existing` refuses a tracked seed that fails the bare-name check, with or without `-y`, and names the routes for its location; it refuses with the new pre-slug reason `roadmap-seed-bare-citation`. This departs from the invalidated-seed precedent (`invalidated_seed_continuation` in `plan_tool/roadmap_seed_state.py`), where `-y` continues: decided 2026-11-17 by the owner, because automated sessions always pass `-y`, so a confirmation would let a legacy seed through in exactly the hands-off runs the bug affects. The `malformed` classification follows the precedent `ROADMAP_FORMAT.md` § "Draft-seed manifest states" set for the `Risks` requirement; no new repair route is added. An untracked seed, or a roadmap with no accepted head, keeps today's behavior.

**Allowed behavior changes are only these:** newly written draft seeds use version-store paths throughout; the References gate requires those paths and names them in its message; a bare member filename (`01-domain.md` … `04-roadmap.md`) anywhere in the body is a gate violation; legacy seeds classify `malformed` and are refused by `--apply` until a route clears them; `create` refuses a tracked seed that fails the check, even under `-y`, with the new reason token `roadmap-seed-bare-citation`. No other `roadmap`, `create`, or audit behavior changes. No reorganization is allowed.

**Stop / defer.** Stop and surface to the user if resolving a citation needs a new link record or a change to the immutable version layout, or if the plans directory sits outside the repository, where no repo-relative path exists. File any adjacent finding in `BUG_BACKLOG.md` or `BACKLOG.md`; do not absorb it here.

## Scope guardrails

- No change to the completeness audit or its prompts, and no new check that a
  quoted passage matches its cited file.
- Legacy seed text is not rewritten in place; promotion does not rewrite the
  top-level `0N-*.md` files, and leftover top-level files are not deleted.
- No new `create` behavior for prose the model writes during synthesis.

## Audit guardrails

- Sibling-plan problems filed in `BUG_BACKLOG.md` and plans already created
  from bare-name seeds are out of scope.
- Stop and surface to the user if resolving a citation needs a new link record,
  a change to the immutable version layout, or a plans directory outside the
  repository; file adjacent findings in `BUG_BACKLOG.md` or `BACKLOG.md`.

## Expected placement

None.

## References

- [pathlib — Object-oriented filesystem paths (Python 3 docs)](https://docs.python.org/3/library/pathlib.html) — Covers PurePath.relative_to, as_posix and is_relative_to, which you need to turn stored_artifact_path into a repo-relative POSIX citation and to handle a plans directory outside the repository.
- [re — Regular expression operations (Python 3 docs)](https://docs.python.org/3/library/re.html) — Reference for the pattern syntax and the search/finditer semantics behind the bare `0N-*.md` body check, which must not match `.roadmap-versions/<version-id>/` paths.
- [CommonMark Spec — Fenced code blocks](https://spec.commonmark.org/0.31.2/#fenced-code-blocks) — The normative fence rules (backtick and tilde fences, length matching, unclosed fences) that explain why fenced seed text still has to be scanned for bare names.
- [CommonMark Spec — ATX headings](https://spec.commonmark.org/0.31.2/#atx-headings) — Defines how line-anchored `## References` and other section headings are recognized, which the gates rely on when they locate seed body sections.
- [pytest documentation — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Covers `@pytest.mark.parametrize` for the body-gate cases (Architecture, Risks, fenced code, top-level path) and the accept cases for version-store paths.
- [pytest documentation — How to use temporary directories and files in tests](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Reference for the `tmp_path` fixture used to build hermetic roadmap fixtures with an accepted head, a stale top-level `04-roadmap.md`, and a version store.

- `BUG_BACKLOG.md` — the source entry named above.
- `ROADMAP_FORMAT.md` — the accepted-head lifecycle and the draft-seed contract.
- `docs/implementation-plans/archive/2-roadmap-versioned-from-birth.md` — why top-level
  files beside an accepted head are inert.
- `plan_tool/prompts/roadmap-seed.md`, `plan_tool/roadmap_versions.py`,
  `plan_tool/roadmap_gates.py`, `plan_tool/roadmap_seed_state.py`.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Any change to the completeness audit or its prompts. A path citation
  needs no translation at read time: the audit model opens the file the
  citation names.
- Bare roadmap file names in new prose that `create`'s model writes while
  synthesizing the plan, as opposed to sections it copies from the seed.
  Nothing deterministic writes that prose, so closing it needs a `create`
  prompt rule or a post-synthesis check: new `create` behavior this seed
  does not allow. Decided 2026-10-29: deferred, recorded as a follow-up on
  the source `BUG_BACKLOG.md` entry.
- Rewriting a legacy seed's text in place. Tried in this seed's design and
  dropped 2026-10-29: seed state records no source version, and neither
  decision settlement nor a non-structural promotion marks seeds
  invalidated, so a `current` seed can quote an older version and a rewrite
  would attach those quotes to the accepted path. Regeneration has no such
  premise.
- Plans already created from bare-name seeds. Deliberately not migrated:
  their citations are corrected by hand or by re-running `create` from the
  seed.
- Making promotion rewrite or refresh the top-level `0N-*.md` files. That
  restores the two-copy design `docs/implementation-plans/archive/2-roadmap-versioned-from-birth.md`
  removed, and the top-level files stay inert by design.
- Deleting or warning about leftover top-level files. The stderr warning
  shipped 2026-10-10 on the roadmap verbs stays as it is.
- The sibling-plan problems filed beside this entry in `BUG_BACKLOG.md`
  (an unbuilt upstream plan, and a path a sibling plan creates). They concern
  how plans relate to each other, not how they cite the roadmap.
- Any new check that a quoted passage matches its cited file. The citation
  names the right file; verifying quotes is the semantic property
  CLAUDE.md § "Validating a semantic property you cannot observe" refuses.

## Risks

- A version-store path goes stale when a newer head is promoted. That is
  intended: the plan cites the version it was derived from. The plan must say
  so, so an audit does not report it as a defect.
- Changing a prompt contract can leave its descriptions disagreeing. Sweep
  every one by vocabulary, not only by identifier:
  - `plan_tool/prompts/roadmap-seed.md`;
  - both draft-seed gates' messages in `plan_tool/roadmap_gates.py`;
  - `ROADMAP_FORMAT.md` § "Draft seeds under the roadmap slug";
  - `docs/how-to/roadmap.md` § 1's leftover-files paragraph, which describes
    a reader opening a bare `04-roadmap.md`;
  - `docs/explanations/roadmap-plan-handoff.md`, which describes what
    `References` carries from seed to plan.

## Testing

- A roadmap with an accepted head and a stale top-level `04-roadmap.md`: a
  draft seed written by the changed contract names repo-relative
  version-store paths throughout, and every roadmap file name the derived
  plan carries from it names an existing version-store file holding the
  accepted content. None names a top-level file.
- The References gate rejects a draft seed that cites a bare filename, and
  its message names the version-store path.
- The body gate rejects a seed with a bare `04-roadmap.md` in Architecture,
  in Risks, inside a fenced code block, and as the last component of a path
  to a top-level copy. It accepts a version-store path, including one naming
  an older stored version, and does not flag a non-member `0N-` filename.
- A legacy seed with bare names classifies `malformed`, `--apply` refuses it,
  and after `--refresh-seeds` it passes and cites version-store paths.
- A hand-edited legacy seed whose bare names are replaced with
  version-store paths is accepted by `--accept-seed` and keeps its other
  edits; one that still has a bare name is refused.
- `create --from-existing` on a tracked legacy seed refuses with
  `roadmap-seed-bare-citation` and names its location's routes, with and
  without `-y`; a tracked seed with no bare name keeps today's confirmation.
- A roadmap created by a stage run, with no top-level files: a regenerated
  seed yields a plan whose carried roadmap file names point at existing
  version-store files.
- An untracked seed, and a roadmap with no accepted head, keep their current
  behavior.
- `uv run pytest tests/ -q -n auto` is green, including the doc-drift guards
  for `ROADMAP_FORMAT.md`.
- Manual real-model check, outside the suite (tests are hermetic and never
  spawn a backend). Owner: the orchestrating session, in the post-run tail
  beside `reconcile-code` and code review, not a `run` step, since a step's
  executor must not spawn a backend itself. After steps 1 and 2 land and
  before the code merges, one
  `plan-tool roadmap <slug> --materialize` against a real backend, on a
  throwaway roadmap with an accepted head, writes a seed that passes the
  gates and names every member file by its version-store path. The canned
  responses above prove the gates and the prompt wiring; only this run shows
  the real seed writer complies. If it falls back to bare names after the
  bounded retry, stop and surface it: the remedy is a scoped follow-up (a
  deterministic rewrite of bare member names to the paths the writer was
  given), never a looser gate.

## Acceptance criteria

- While an accepted head exists, no roadmap file name that a plan carries
  from a draft seed passing the gates names a top-level `01-domain.md` …
  `04-roadmap.md`, in any section, fenced code included.
- A seed written before the change is never carried into a plan silently:
  it is regenerated or repaired (hand-edited, and accepted for a draft), and
  `create` refuses it until then, with or without `-y`.
- `ROADMAP_FORMAT.md` § "Draft seeds under the roadmap slug" states the new
  citation form, and the roadmap-seed prompt and both draft-seed gates agree
  with it.
- One real-model `--materialize` run, recorded with its outcome in the code
  pull request, produced a gate-clean seed citing only version-store paths
  before the code merged.
- Backlog reconciliation: the final step removes the originating
  `BUG_BACKLOG.md` entry only after full shipment, and leaves or updates any
  deferred follow-up. Authoring this plan does not remove it.

## Deferred

- Bare roadmap file names in new prose that `create`'s model writes during
  synthesis. Deferred 2026-10-29 because closing it needs new `create`
  behavior (a prompt rule or a post-synthesis check) that this plan does not
  allow; it stays a follow-up on the source `BUG_BACKLOG.md` entry, kept or
  re-filed by step 4 when that entry is removed.
