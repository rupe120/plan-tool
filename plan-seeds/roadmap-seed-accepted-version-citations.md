# Plan seed: roadmap draft seeds cite the accepted roadmap version, not bare filenames

This file is a `plan-tool create` input. Use it via:

```
plan-tool create roadmap-seed-accepted-version-citations --from-existing plan-seeds/roadmap-seed-accepted-version-citations.md
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

## In scope

- The draft-seed contract: the `## References` rule in
  `plan_tool/prompts/roadmap-seed.md` names the accepted version's artifacts
  instead of bare `01-domain.md` … `04-roadmap.md` filenames. The model also
  writes a `source_artifacts` frontmatter key into some draft seeds; the
  provenance schema does not name it (`roadmap_components` and
  `cross_cutting` are the only keys), so the schema ignores it. `create`
  decides whether it is dropped or made to follow the same citation form.
- The path from a draft seed into a plan: `create --from-existing` carries
  the citation unchanged, and the audit's inputs resolve it to the accepted
  version's member file.
- Draft seeds already written with bare names, which must keep grounding to
  the accepted version rather than fail.

## Out of scope / Non-goals

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

Only these: a newly written draft seed names accepted-version artifacts in
`References`, and `create` and the audit resolve those
names. No other `roadmap`, `create`, or audit behavior changes.

## Allowed reorganization

None.

## Architecture

- **Settled: the seed writer owns the fix.** Promotion changes only the
  accepted-head selector, and that stays so. The defect is the citation
  contract, so the contract changes, and no command is taught to find a
  "better" copy of a bare name.
- **Settled: one resolution rule.** A citation form is chosen once, either a
  version-store path or the version id plus the member name. Everything that
  reads a citation resolves it through the existing accepted-version lookup
  (`load_accepted_version` in `plan_tool/roadmap_versions.py`), and no second
  resolver is written.
- **Decision for `create` to settle, with the choice recorded in the plan:**
  which of those two citation forms is stored. Prefer the one that survives a
  later promotion of a newer head unchanged, because a plan cites the version
  it was derived from.
- **Guarantee: "the audit never grounds on a top-level copy of a cited roadmap
  artifact."** Mechanism: the cited name resolves to a version-store file
  before the audit reads it. Owner: the citation-resolution step. Order: the
  draft-seed contract changes first, then `create` carries it, then the audit
  resolves it, then the legacy-seed fallback.
- **Legacy seeds:** a bare `0N-*.md` citation in an existing draft seed
  resolves through the accepted head when one exists. With no head, the
  existing behavior is unchanged.

## Testing

- A roadmap with an accepted head and a stale top-level `04-roadmap.md`: a
  draft seed written by the changed contract cites the accepted version, and
  the audit input for the derived plan contains the accepted content, not the
  stale text.
- A legacy draft seed with bare names, in the same roadmap, resolves to the
  accepted version.
- A roadmap with no accepted head keeps its current behavior.
- `uv run pytest tests/ -q -n auto` is green, including the doc-drift guards
  for `ROADMAP_FORMAT.md`.

## Acceptance criteria

- No path from draft seed to plan to audit input reads a top-level `0N-*.md`
  while an accepted head exists.
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

- A citation form that embeds the version id goes stale when a newer head is
  promoted. That is intended: the plan cites the version it was derived from.
  The plan must say so, so an audit does not report it as a defect.
- Changing a prompt contract can leave the prompt and `ROADMAP_FORMAT.md`
  disagreeing. Sweep all three by vocabulary, not only by
  identifier.

## References

- `BUG_BACKLOG.md` — the source entry named above.
- `ROADMAP_FORMAT.md` — the accepted-head lifecycle and the draft-seed contract.
- `docs/implementation-plans/2-roadmap-versioned-from-birth.md` — why top-level
  files beside an accepted head are inert.
- `plan_tool/prompts/roadmap-seed.md`, `plan_tool/roadmap_versions.py`.
