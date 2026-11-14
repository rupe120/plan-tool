# Roadmap seed `## Risks` presence rule — review ledger

| Field | Value |
| --- | --- |
| Change | A draft seed without a non-empty `## Risks` section classifies `malformed` (`missing-draft-seed-risks`). Owner decision 2026-10-10: roadmap seeds must carry `## Risks` |
| Branch | `fix/roadmap-seed-risks-required` |
| Reviewer | `/code-review high main` in-session (forked), report-only |

## Settled decisions

- Presence only. A fenced example or a `_(TODO)_`/`TODO` placeholder (the existing `scope_fence` vocabulary) does not count; what a risk says is never judged, and `TBD`/`None.` pass.
- A plan row whose artifacts state no risk writes one explicit line saying so (prompt and correction message name it); the prompt still forbids inventing a risk.
- Consequence accepted by the owner: existing drafts without `Risks`, Integration's included, are `malformed` until `--refresh-seeds` or a hand edit plus `--accept-seed`.
- `Testing` and `Acceptance criteria` stay ungated; stated in `ROADMAP_FORMAT.md`.

## Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | Prompt forbids inventing a risk but the gate demands content: a row with no stated risk had no compliant reply | **Fixed.** Prompt and correction name the one-line statement; `create` accepts it because any seed line is citable |
| 2 | Deleted entry dropped the undecided `Testing` / `Acceptance criteria` follow-up | **Fixed.** Stated as deliberately not gated in `ROADMAP_FORMAT.md` |
| 3 | Consumers of the rule not pinned | **Fixed.** Classifier and `--apply` tests (`malformed` on a matching digest); gate disabled turns them red |
| 4 | Doc: a hand edit goes through `digest-mismatched` and needs `--accept-seed` | **Fixed** |
| 5 | A placeholder-only body satisfies the gate | **Fixed in part.** Reuses `_is_placeholder_section`; a bare `-` still passes (vocabulary matching beyond the existing placeholder set is the semantic check this gate refuses) |
| 6 | Sections extracted twice | **Fixed.** One `_draft_seed_sections` dict |
| 7 | Prompt leaks "roadmap gate"; unwrapped line | **Fixed** |
| 8 | A handoff still lists the decision as open | **Fixed** |
