# Plan seed: roadmap draft seeds cite the accepted roadmap version, not bare filenames

This file is a `plan-tool create` input. Use it via:

```
plan-tool create roadmap-seed-accepted-version-citations --from-existing docs/implementation-plans/plan-seeds/roadmap-seed-accepted-version-citations.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

Source: `BUG_BACKLOG.md` → BUG → "Roadmap-derived plans cite bare `0N-*.md`
names, which resolve to stale top-level copies beside an accepted head, so
audits ground on a superseded roadmap and report false contradictions"
(Route: plan). It has no Jira ticket yet. This seed carries that entry's scope
contract.

## Outcome

A plan derived from a roadmap draft seed cites the accepted roadmap version it
was derived from, so a completeness audit or a reader opening a cited roadmap
artifact reads the accepted content and never an inert top-level `0N-*.md`
copy left beside the accepted head.

This covers every roadmap, not only older folders with leftovers. A stage run
publishes no top-level `0N-*.md` files (`ROADMAP_FORMAT.md` § "What writes
them"), so in a roadmap created that way a bare-name citation names no file
at all. That case follows from the design; the observed symptom is the
stale-copy case.

## In scope

- The draft-seed contract: `plan_tool/prompts/roadmap-seed.md` has the seed
  name the accepted version's member files by their version-store paths
  everywhere in the seed body, not only in `## References`, instead of bare
  `01-domain.md` … `04-roadmap.md` filenames. `create` copies the seed's
  body sections into the plan, so a bare name in Architecture or Risks
  reaches the audit as surely as one in References. The seed writer is given
  those paths; it does not derive them.
- The draft-seed gates in `plan_tool/roadmap_gates.py`:
  - The References gate (`VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE`)
    requires the version-store path. Today it accepts a bare filename, and
    its message tells the bounded retry to "add the literal filename", which
    steers the seed writer back to the old form. Its message names the path.
  - A bare `0N-*.md` name anywhere in the seed body, outside fenced code, is
    a violation. Bare means not the final component of a version-store path,
    so the paths the contract requires never trip it. This is a plain
    presence check: it rejects every bare
    occurrence and never has to judge whether one is a citation or a
    mention. Fenced code is excluded with the same scanner the References
    gate uses (`extract_h2_sections`, `strip_fenced_code=True`, in
    `plan_tool/scope_fence.py`).
- Legacy draft seeds with bare names: `create --from-existing` rewrites them
  under a fixed rule (Architecture, "Legacy seeds").
- `source_artifacts`, deliberately departing from the source entry's Fix,
  which renders that key in the new form too. The prompt never asks for the
  key, and `parse_draft_seed_provenance` ignores it (`roadmap_components` and
  `cross_cutting` are the only keys), so the seed body stays the one citation
  surface. The plan records whether `create` drops a stray `source_artifacts`
  key or leaves it inert.

## Out of scope / Non-goals

- Any change to the completeness audit or its prompts. A path citation
  needs no translation at read time: the audit model opens the file the
  citation names.
- Bare roadmap file names in new prose that `create`'s model writes while
  synthesizing the plan, as opposed to sections it copies from the seed.
  Nothing deterministic writes that prose, so closing it needs a `create`
  prompt rule or a post-synthesis check: new `create` behavior this seed
  does not allow. Decided 2026-10-29: deferred, recorded as a follow-up on
  the source `BUG_BACKLOG.md` entry.
- Plans already created from bare-name seeds. Deliberately not migrated:
  their citations are corrected by hand or by re-running `create` from the
  seed.
- Making promotion rewrite or refresh the top-level `0N-*.md` files. That
  restores the two-copy design `docs/implementation-plans/2-roadmap-versioned-from-birth.md`
  removed, and the top-level files stay inert by design.
- Deleting or warning about leftover top-level files. The stderr warning
  shipped 2026-10-10 on the roadmap verbs stays as it is.
- The sibling-plan problems filed beside this entry in `BUG_BACKLOG.md`
  (an unbuilt upstream plan, and a path a sibling plan creates). They concern
  how plans relate to each other, not how they cite the roadmap.
- Any new check that a quoted passage matches its cited file. The citation
  names the right file; verifying quotes is the semantic property
  CLAUDE.md § "Validating a semantic property you cannot observe" refuses.

## Allowed behavior changes

Only these:

- A newly written draft seed names roadmap files by version-store path
  throughout its body.
- The References gate requires those paths and its message names them, and
  a bare `0N-*.md` name anywhere in the seed body outside fenced code is a
  gate violation.
- `create --from-existing` rewrites every bare `0N-*.md` name outside fenced
  code in a qualifying legacy seed's body to the accepted version's paths.

No other `roadmap`, `create`, or audit behavior changes.

## Allowed reorganization

None.

## Architecture

- **Settled: the seed writer owns the fix.** Promotion changes only the
  accepted-head selector, and that stays so. The defect is the citation
  contract, so the contract changes, and no command is taught to find a
  "better" copy of a bare name at read time.
- **Settled: the citation form is the repo-relative version-store path** of
  the member file, e.g.
  `docs/implementation-plans/roadmaps/<slug>/.roadmap-versions/<version-id>/04-roadmap.md`
  when the plans directory is `docs/implementation-plans/` (`roadmap_dir`). Repo-relative, because
  plans and promoted seed copies live outside the roadmap folder, so a
  roadmap-relative path would resolve to no file from either place. Rejected:
  the version id plus the member name, which would need a resolver at read
  time. The audit model opens files by path and has no roadmap resolution.
- **Settled: one lookup, no second resolver.** The seed writer's paths and
  `create`'s legacy rewrite both come from `load_accepted_version` and
  `stored_artifact_path` in `plan_tool/roadmap_versions.py`. The rewrite also
  needs the roadmap slug, from `locate_tracked_seed`
  (`plan_tool/roadmap_seed_state.py`), and the bare-name-to-artifact-key
  mapping, read from `VERSION_ARTIFACT_INVENTORY`'s `member_name` entries
  (`stored_artifact_path` takes a key, and today only key-to-name exists).
- **Guarantee: "the audit never grounds on a top-level copy of a cited roadmap
  artifact."** Mechanism: every roadmap file name that a derived plan carries
  from its seed is a version-store path. Owner: the seed writer and the
  draft-seed gates for new seeds, `create` for qualifying legacy seeds.
  Order: the draft-seed contract and gate change first, then the legacy
  rewrite in `create`.
- **Legacy seeds.** The rewrite applies only when all of these hold:
  - `locate_tracked_seed` resolves the seed;
  - its seed-state status is `current`;
  - the roadmap has an accepted head.

  It rewrites every bare `0N-*.md` name in the seed body outside fenced
  code, found with the same fence-aware scanner as the gate, and nothing
  else.
  Seed state records no source version, but every applied revision marks all
  tracked seeds invalidated (`ROADMAP_FORMAT.md` § "Invalidation and explicit
  refresh"). So a `current` seed was written against the accepted head, and
  citing that head is citing the version it was derived from. An invalidated
  seed is not rewritten. Its body may quote an older version, and
  re-pointing it at the head would attach stale quotes to the accepted path.
  It keeps today's explicit-continue prompt, and `--materialize` or
  `--refresh-seeds` regenerates it under the new contract. An untracked
  seed, or a roadmap with no accepted head, keeps today's behavior.

## Testing

- A roadmap with an accepted head and a stale top-level `04-roadmap.md`: a
  draft seed written by the changed contract names repo-relative
  version-store paths throughout, and every roadmap file name the derived
  plan carries from it names an existing version-store file holding the
  accepted content. None names a top-level file.
- The References gate rejects a draft seed that cites a bare filename, and
  its message names the version-store path.
- The body gate rejects a seed with a bare `04-roadmap.md` in Architecture
  or Risks, and accepts the same name inside a fenced code block.
- A `current` legacy seed with bare names in References and in Architecture,
  in the same roadmap: the derived plan carries the accepted version's paths
  in both sections, and a bare name inside fenced code is left unchanged.
- An invalidated legacy seed is not rewritten and still gets the
  explicit-continue prompt.
- A roadmap created by a stage run, with no top-level files: a new-contract
  seed and a `current` legacy seed both yield plans whose carried roadmap
  file names point at existing version-store files.
- An untracked seed, and a roadmap with no accepted head, keep their current
  behavior.
- `uv run pytest tests/ -q -n auto` is green, including the doc-drift guards
  for `ROADMAP_FORMAT.md`.

## Acceptance criteria

- While an accepted head exists, no roadmap file name that a plan carries
  from a new-contract or `current` legacy draft seed names a top-level
  `0N-*.md`, in any section.
- A `current` seed written before the change still grounds against the
  accepted version, and an invalidated one is routed to regeneration rather
  than re-pointed.
- `ROADMAP_FORMAT.md` § "Draft seeds under the roadmap slug" states the new
  citation form, and the roadmap-seed prompt and both draft-seed gates agree
  with it.
- Backlog reconciliation: the final step removes the originating
  `BUG_BACKLOG.md` entry only after full shipment, and leaves or updates any
  deferred follow-up. Authoring this plan does not remove it.

## Stop / defer

Stop and surface to the user if resolving a citation needs a new link record
or a change to the immutable version layout, or if some accepted-head writer
does not invalidate tracked seeds (the legacy rule depends on it). File any
adjacent finding in `BUG_BACKLOG.md` or `BACKLOG.md`; do not absorb it here.

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

## References

- `BUG_BACKLOG.md` — the source entry named above.
- `ROADMAP_FORMAT.md` — the accepted-head lifecycle and the draft-seed contract.
- `docs/implementation-plans/2-roadmap-versioned-from-birth.md` — why top-level
  files beside an accepted head are inert.
- `plan_tool/prompts/roadmap-seed.md`, `plan_tool/roadmap_versions.py`,
  `plan_tool/roadmap_gates.py`, `plan_tool/roadmap_seed_state.py`.
