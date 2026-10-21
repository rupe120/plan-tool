# Plan seed: alias-aware seed-extraction pre-fill for body sections

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/seed-extraction-alias-prefill.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

Source: BACKLOG #102 → promoted to IPPT-11 (2026-09-27). This seed carries
that entry's scope contract; the ticket holds the working brief.

## Outcome

`create`'s rung-2 seed-extraction (`extract_h2_sections`, populating
`seed_sections` in `create.py`'s body-section ladder,
`synthesized ≻ seed_sections ≻ _(TODO)_`) resolves a seed heading that is a
near-miss synonym of a canonical section name (e.g. `Approach` for
`Implementation`, `Testing` for `Tests`) to that canonical section, instead of
falling straight to `_(TODO)_` and waiting on the stochastic `--iterate` loop
to re-synthesize content the seed's author already wrote verbatim.

## In scope

- `plan_tool/scope_fence.py:extract_h2_sections` (and/or its caller): an
  explicit, small alias/synonym map keyed on heading identity.
- `plan_tool/create.py`'s rung-2 `seed_sections` call site
  (`extract_h2_sections(body_source, ...)`): consumes the widened match with
  no change to the ladder's precedence order.
- `tests/test_scope_fence.py` (`TestExtractH2Sections`): fixtures for each
  aliased near-miss heading resolving, and a negative case that must still
  fall through to `_(TODO)_`.
- `tests/test_create.py`: coverage that a plan built from a seed with an
  aliased heading renders the canonical section verbatim from the seed.

## Out of scope / Non-goals

- Fuzzy or similarity-based matching of any kind. Matching is heading
  identity against an explicit, small map — never prose similarity.
- Any change to the ladder's precedence (`synthesized ≻ seed_sections ≻
  _(TODO)_`) or to the stochastic `--iterate` loop itself. A canonical
  section the seed never wrote at all is a true gap and stays the loop's job.
- The write-time placeholder gate, `create.py:_find_placeholder_body_sections`.
- Backlog #41 (retired): threading seed text into the *stochastic*
  `apply_finding` re-synthesis. This seed is the deterministic-pre-fill
  direction instead; do not reopen #41's approach.

## Allowed behavior changes

None beyond the Outcome: a wider set of seed headings resolve verbatim into
their canonical section. Every other `create` behavior — synthesis, the
`_(TODO)_` gate, the `--iterate` loop — is unchanged.

## Allowed reorganization

None. The alias map is additive to the existing matcher; it does not move or
rename existing functions.

## Verification

- New fixtures in `TestExtractH2Sections` show each aliased near-miss heading
  resolving to its canonical section, and a non-aliased near-miss still
  falling through to `_(TODO)_`.
- `uv run pytest tests/test_scope_fence.py tests/test_create.py -q` is green.

## Stop / defer

Stop and surface to the user if the alias map's scope is unclear for a given
heading. Precision over recall: a false-positive alias that copies the wrong
seed block into a canonical slot verbatim ("confidently wrong") is worse than
a clean `_(TODO)_` the loop fills — prefer leaving a gap over a low-confidence
match, and defer rather than widen the map past what this Outcome requires.

## References

- `plan_tool/scope_fence.py` (`extract_h2_sections`, `extract_h2_section_occurrences`) —
  the matcher this seed widens.
- `plan_tool/create.py` (rung-2 `seed_sections`, the `body_source`-fed call site) —
  the caller that consumes the widened match.
- `tests/test_scope_fence.py` (`TestExtractH2Sections`) — the fixture class
  the new alias cases and the negative case belong in.

## Backlog reconciliation

`BACKLOG.md`'s `#102` entry is already a promotion stub pointing at IPPT-11.
No further backlog edit is required when this plan ships.
