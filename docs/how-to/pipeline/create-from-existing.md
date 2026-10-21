# `create --from-existing` workflow

This document maps the file-backed flow for
`plan-tool create <slug> --from-existing <path>`. The detailed route and
lifecycle table belongs to
[`CREATE_SEED_INGESTION_CONTRACT.md`](../../reference/contracts/seed-ingestion.md).
For checkpoint recovery, see
[`CREATE_RESUME_FLOW.md`](../recovery/create.md) and the shared
[`RESUME_FLOW.md`](../recovery/README.md).

## TL;DR

- File-backed intake is source-led, not size-led. It selects `seed_body` when
  present, even when empty, and otherwise selects `from_description`.
- An unmatched fence and the usable-References check are separate no-run-record
  preflights. They write no checkpoint, call no model, publish no plan, and do
  not select a route.
- A direct-ready source is assessed for a split against its raw content. It
  then selects `direct`, `split`, or `refused`.
- A source that is not direct-ready takes one preparation decision and selects
  `normalized`, `split`, or `refused`. It never silently falls through to raw
  publication.
- `SplitProposal` is a successful no-plan result: `cmd_create` displays a
  carving action and can save a worksheet while leaving the raw source in
  place.

## File-backed decision flow

```
plan-tool create <slug> --from-existing <path>
                     |
                     v
  select seed_body when present, else from_description
                     |
                     v
  unmatched-fence protection + usable ## References preflight
                     |                 |
                     |                 +-- refuse: no run record, no route, exit 2
                     v
        is the selected source direct-ready?
              |                         |
             yes                       no
              |                         |
              v                         v
raw-source split assessment       one preparation decision
              |                         |
       +------+-------+          +------+----------+-------+
       |              |          |                 |       |
       v              v          v                 v       v
    direct         split      normalized         split   refused
       |              |          |                 |       |
       v              v          v                 v       v
  publish plan    no plan    publish plan      no plan   no plan
```

`direct`, `normalized`, `split`, and `refused` are the selected terminal
outcomes. A split or refusal after preflight rolls back any branch binding
created for a collision before reporting its no-plan outcome. See the contract
for publication, checkpoint, and archival disposition for each outcome.

## Direct publication

Direct readiness requires complete canonical body headings after shared H2
normalization: letter case and an optional closing ATX sequence do not change a
canonical title, but semantic aliases remain outside the route. It is not a byte
threshold. The direct route keeps the supplied body and `## References` content
authoritative, performs its required split assessment on that raw source, and
bypasses generic post-write convergence after publication.

Strict canonical `## Steps` is an independent reader decision. When it is
present, `create` lifts the graph deterministically; otherwise the normal step
authoring path remains responsible for the graph. Neither case lets a later
authoring stage replace a direct source body or its References.

## Intent, risk, and ordinary authoring

The first usable paragraph of `## Outcome` in the selected raw source supplies
the plan `intent` before routing. A missing-intent proposal and risk-profile
advice remain separate authoring decisions: neither rewrites a source body or
turns a file-backed source into another route. The normal step, reference, and
body authoring work continues only within the authority boundary selected by
the route.

## Preparation and normalized publication

A missing, duplicate, empty, or placeholder canonical body heading does not
make a file-backed source invalid. It selects the visible preparation decision.
That decision can normalize source-supported content for one plan, identify a
multi-plan split, or refuse. A malformed or unsupported result does not
publish raw text, retry through a different route, or expose a new route name.

On a normalized publication, source-materialized evidence-only fields remain
protected through scope rendering, concept synchronization, and applicable
convergence work. The selected source’s local References also reach step
proposal and remain in the published plan alongside applicable research links
and disclosures. Local paths, anchors, source ids, and notes are context; they
do not satisfy selected-product research requirements. See the
[seed ingestion contract](../../reference/contracts/seed-ingestion.md) for
source selection, route authority, and archival rules. Direct raw body and References receive the same protection
on the direct route. These invocation-local protections do not prevent a later
operator-directed audit from revising the published plan.

## Split proposal

`plan_tool/create.py:SplitProposal` carries the multi-plan result, and
`plan_tool/cli/authoring.py:_emit_split_proposal` presents it as an
operator-visible success. The CLI prints each proposed carve and, under
`--yes` or non-TTY input, saves `<slug>-split-proposal.md`. It writes no plan
or manifest entry, leaves the raw source available, and exits `0`; create each
carved plan later with its own `--from-existing` invocation.

## Publication and archival

`create_plan(..., from_existing_path=...)` is a public library entry point. It
uses the selected source and the same route/checkpoint rules, but leaves its
caller-owned source unchanged. `cmd_create` owns the destructive action:

- Clean direct publication archives the raw source chain and writes no
  normalized artifact.
- Clean normalized publication materializes and archives the normalized
  artifact and archives the raw source chain.
- Split and post-preflight refusal retain the raw source. Split retains its
  versioned route result; refusal removes its terminal route result.
- A normalized iteration-incomplete publication retains the raw source and
  checkpoints, emits no normalized archive artifact, and continues with
  `plan-tool completeness-audit <slug> --iterate` against the registered
  plan—not a second create invocation.

Legacy provenance frontmatter continues to identify an original source and a
matching plan-details bundle. On clean CLI publication, its source-chain
archive and any applicable bundle rename follow the normal replacement rules;
public `create_plan` callers retain those caller-owned files. Collision and
target-recovery behavior stays in
[`CREATE_RESUME_FLOW.md`](../recovery/create.md): a target that already exists
is retained for recovery, while no-plan split and refusal results roll back a
collision-created branch binding.

## Inline compatibility

`--from-existing` is the file-backed route described here. Inline `--from`
does not run the References preflight and retains its separate compatibility
behavior. In particular, `--no-distill` is not a file-backed raw-source
bypass.

## Source map

| Concern | Owner |
| --- | --- |
| Selected source, preflight, route result, and finalization | `plan_tool/create.py` (`select_file_backed_source`, `validate_from_existing_seed`, `FileBackedSourceRoute`, `_prepare_create_plan`, `_finalize_create_plan`) |
| Split data and presentation | `plan_tool/create.py:SplitProposal`; `plan_tool/cli/authoring.py:_emit_split_proposal` |
| CLI preflight, route result, and clean archival | `plan_tool/cli/authoring.py:cmd_create` |
| Route behavior | `tests/test_create.py`, `tests/test_distill.py`, `tests/cli/test_authoring_cmds.py` |
