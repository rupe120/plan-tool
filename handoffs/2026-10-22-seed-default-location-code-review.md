# New-seed default placement

Base: `330441789` on branch `fix/seed-default-location`, independent of PR #136.
Intent: new seeds default to `docs/implementation-plans/plan-seeds/`; existing
seed files stay at their current paths. Both directories receive an explanatory
README. No seed migration or configurable-directory feature ships.

## Scope and invariant

`seed_paths.py` is a stdlib-only placement leaf. Scope-out (single/region),
reground, roadmap promotion and annotate share the nested default. Explicit
annotate output/seed destinations remain authoritative and its report default
stays beside the source. `create --from-existing` keeps explicit path semantics.

Existing roadmap publications retain root placement, even if their file is
archived or absent. New promotions persist optional `publication_layout: nested`;
missing layout means legacy root. Normalization validates the closed root/nested
vocabulary, and accept/materialize state rewrites preserve it. Refresh comparison
and skipped apply targets follow the recorded destination, not folder existence.
Unpublished files never gain publication ownership from their presence.

Pre-edit identifier search covers literal plan-seeds joins in all writers and
roadmap refresh/accept/preview paths. Vocabulary search covers placement,
promotion, published copies, seed authoring, CLI help and annotate output rules.
Sites: both scope-out path builders, reground builder, ordered roadmap targets,
publication registration, accept/materialize/refresh destinations, CLI preview,
annotate derivation and batch collision preflight. Documentation sites include
seed format, roadmap/data contracts, consuming directives, routers, user guides,
generated CLI references and repository authoring policy. Scratch enumeration:
`.tmp/seed-default-location.sites.md`.

Backlog #184 retains project-level configuration as separate future work; this
user-directed change supersedes its former root-default assumption. CLAUDE.md
changes only the seed authoring path and retains old-seed editing coverage;
normal PR review must use the required architect tier for that protected file.
PR #136 independently owns iteration guidance; do not absorb that work here.

## Validation

- Affected writers/lifecycle suite: 1,367 passed, 65 skipped before the final
  malformed-layout case; integration fixtures then update explicit expectations.
- Full completed source/fixture suite: 14,711 passed, 67 skipped in 60.70s.
- Mutation: reverting the nested constant fails the new-default invariant;
  forcing legacy publications into the nested folder fails all legacy-placement
  cases. Both mutations are restored before final full-suite validation.
- Existing legacy materialization/archive tests remain; a parametrized root/
  nested test verifies the recorded destination changes and the other same-named
  file stays byte-identical. Layout roundtrip/invalidation and malformed-field
  tests pin persistence and fail-closed parsing.
- Existing annotate override tests pass. The live root-seed preflight excludes
  README.md rather than treating explanatory prose as an implementation seed;
  existing seeds are not rewritten to satisfy a wider validation sweep.
- Help snapshot and CLI reference are regenerated from intentional parser/help
  changes. `git diff --check` is clean. No existing seed file is renamed/deleted.

## Review status

Actual Claude Code `/code-review` at high effort follows the committed snapshot.
