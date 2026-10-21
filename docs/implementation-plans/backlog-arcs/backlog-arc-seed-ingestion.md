# Seed-ingestion and create-routing backlog arc

## File intent

This arc records the delivered file-backed seed-ingestion route. Its detailed
operator contract lives in
[the seed-ingestion contract](../../reference/contracts/seed-ingestion.md).

## Delivered route

#327 is complete through
[the seed-ingestion plan](../archive/2-seed-ingestion-routing.md). File-backed
create now:

1. selects `seed_body` when present, otherwise `from_description`, without
   allowing a description to hide an empty provenance source;
2. refuses unmatched fences and unusable References before a run record,
   checkpoint, model call, plan, or manifest entry;
3. selects exactly one post-preflight outcome: `direct`, `normalized`,
   `split`, or `refused`;
4. keeps direct raw source authority, including the required raw-source split
   assessment, and gives non-direct source one visible preparation decision;
5. keeps `SplitProposal` inside `create` as a successful no-plan, no-manifest
   result with an operator-visible carving action; and
6. assigns checkpoint retention, branch rollback for no-plan results, and
   clean CLI-only archival to the selected route.

The route does not treat canonical shape as universal validation. References is
the only source-evidence preflight; a free-form source that otherwise needs
help enters preparation. A malformed direct assessment or preparation result
fails closed as `refused`, never by publishing the supplied source or adding a
new route name.

## Handoff

#102 remains separate work. It may propose semantic heading aliases, but does
not reopen #327's canonical-title normalization, source authority, preflight,
split, or lifecycle decisions. Select and implement that work as its own effort
if alias matching remains needed.

#353 is also separate work. It owns a future durable human/headless decision
when a normalized-artifact destination reappears after bounded recovery. It
does not reopen this arc's ingestion or routing decisions, and it remains
parked until the narrow collision correction reaches external review
convergence and the user explicitly selects it.

## Out of scope

This completed arc does not add a general semantic seed audit, a broader
universal heading preflight, a separate split command, hidden single-plan
continuation, or changes to downstream authoring contracts outside the
selected source and preparation route. It also does not add generic locking,
writer identity detection, pending-payload storage, contention receipts, or a
Integration transport; #353 owns the bounded plan-tool follow-on.
