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

This covers every roadmap, not only older folders with leftovers. A roadmap
created by a stage run has no top-level `0N-*.md` files, because the run
publishes only the version store and the accepted head (`ROADMAP_FORMAT.md`
§ "What writes them"). There, a bare-name citation names no file at all. That case
follows from the design; the observed symptom is the stale-copy case.

## In scope

- The draft-seed contract: the `## References` rule in
  `plan_tool/prompts/roadmap-seed.md` cites the accepted version's member
  files by their version-store paths instead of bare `01-domain.md` …
  `04-roadmap.md` filenames. The seed writer is given those paths; it does
  not derive them.
- Draft seeds already written with bare names: `create --from-existing`
  rewrites their bare `0N-*.md` citations to the accepted version's paths
  when it carries the seed into a plan, so they keep grounding on accepted
  content rather than fail.
- `source_artifacts`, deliberately departing from the source entry's Fix,
  which renders that key in the new form too. The prompt never asks for the
  key, and `parse_draft_seed_provenance` ignores it (`roadmap_components` and
  `cross_cutting` are the only keys), so `References` stays the one citation
  surface. The plan records whether `create` drops a stray `source_artifacts`
  key or leaves it inert.

## Out of scope / Non-goals

- Any change to the completeness audit or its prompts. A path citation
  needs no translation at read time: the audit model opens the file the
  citation names.
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

Only these: a newly written draft seed cites version-store paths in
`References`, and `create --from-existing` rewrites a legacy seed's bare
`0N-*.md` citations to the accepted version's paths when an accepted head
exists. No other `roadmap`, `create`, or audit behavior changes.

## Allowed reorganization

None.

## Architecture

- **Settled: the seed writer owns the fix.** Promotion changes only the
  accepted-head selector, and that stays so. The defect is the citation
  contract, so the contract changes, and no command is taught to find a
  "better" copy of a bare name at read time.
- **Settled: the citation form is the version-store path** of the member
  file, e.g. `.roadmap-versions/<version-id>/04-roadmap.md` under the roadmap
  slug. Rejected: the version id plus the member name. The audit model opens
  files by path and has no roadmap resolution, so that form would need a
  resolver at read time; a path needs none. The plan fixes whether the path
  is repo-relative or relative to the roadmap folder and records the choice.
- **Settled: one lookup, no second resolver.** Both the seed writer's paths
  and `create`'s legacy rewrite come from `load_accepted_version` and
  `stored_artifact_path` in `plan_tool/roadmap_versions.py`.
- **Guarantee: "the audit never grounds on a top-level copy of a cited roadmap
  artifact."** Mechanism: every roadmap citation in a derived plan is a
  version-store path. Owner: the seed writer for new seeds, `create` for
  legacy seeds. Order: the draft-seed contract changes first, then the legacy
  rewrite in `create`.
- **Legacy seeds:** a legacy seed does not record the version it came from,
  so `create` cites the version accepted when it runs. With no accepted head,
  the existing behavior is unchanged.

## Testing

- A roadmap with an accepted head and a stale top-level `04-roadmap.md`: a
  draft seed written by the changed contract cites version-store paths, and
  every roadmap citation in the plan `create` derives from it names a
  version-store file holding the accepted content. None names a top-level
  file.
- A legacy draft seed with bare names, in the same roadmap: the derived
  plan's citations are the accepted version's paths.
- A roadmap created by a stage run, with no top-level files: a draft seed
  written by the changed contract, and a legacy bare-name seed, both yield
  plan citations that name existing version-store files.
- A roadmap with no accepted head keeps its current behavior.
- `uv run pytest tests/ -q -n auto` is green, including the doc-drift guards
  for `ROADMAP_FORMAT.md`.

## Acceptance criteria

- While an accepted head exists, no roadmap citation in a plan derived from
  a draft seed names a top-level `0N-*.md`.
- A seed written before the change still grounds against the accepted version.
- `ROADMAP_FORMAT.md` § "Draft seeds under the roadmap slug" states the new
  citation form, and the roadmap-seed prompt agrees with it.
- Backlog reconciliation: the final step removes the originating
  `BUG_BACKLOG.md` entry only after full shipment, and leaves or updates any
  deferred follow-up. Authoring this plan does not remove it.

## Stop / defer

Stop and surface to the user if resolving a citation needs a new link record
or a change to the immutable version layout. File any adjacent finding in
`BUG_BACKLOG.md` or `BACKLOG.md`; do not absorb it here.

## Risks

- A version-store path goes stale when a newer head is promoted. That is
  intended: the plan cites the version it was derived from. The plan must say
  so, so an audit does not report it as a defect.
- Changing a prompt contract can leave its descriptions disagreeing. Sweep
  all three by vocabulary, not only by identifier:
  `plan_tool/prompts/roadmap-seed.md`, `ROADMAP_FORMAT.md` § "Draft seeds
  under the roadmap slug", and `docs/how-to/roadmap.md` § 1's leftover-files
  paragraph, which describes a reader opening a bare `04-roadmap.md`.

## References

- `BUG_BACKLOG.md` — the source entry named above.
- `ROADMAP_FORMAT.md` — the accepted-head lifecycle and the draft-seed contract.
- `docs/implementation-plans/2-roadmap-versioned-from-birth.md` — why top-level
  files beside an accepted head are inert.
- `plan_tool/prompts/roadmap-seed.md`, `plan_tool/roadmap_versions.py`.
