# Leftover top-level 0N-*.md warning — review ledger

| Field | Value |
| --- | --- |
| Change | BUG_BACKLOG "Roadmap-derived plans cite bare `0N-*.md` names" part 2: a stderr warning names inert top-level `0N-*.md` files beside an accepted head |
| Branch | `fix/stale-0n-roadmap-citations` |
| Reviewer | `/code-review high main` in-session (forked), report-only |

## Settled decisions

- Warning only; never an exit-code or rendered-output change. Existence check only, never a read.
- Silent without an accepted head (the no-published-version refusal already names the files).
- Part 1 (draft seeds cite the accepted version) stays in BUG_BACKLOG, route plan.

## Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | Warning missing on the routes that hand a seed to `create` | **Fixed in part.** Added to `--accept-seed` and `--apply`. **Declined** for `create --from-existing <seed>`: a different module, and part 1 removes the bare name there. Recorded in the entry |
| 2 | `.roadmap-versions` hard-coded | **Fixed.** `version_namespace_path` |
| 3 | The existence scan written twice | **Fixed.** One `leftover_top_level_artifacts`; the tuple is private again |
| 4 | Materialize test claims an ordering it does not pin | **Fixed.** Renamed to the route it covers; accept/apply routes pinned by a parametrized test |
| 5 | Singular/plural grammar | **Fixed**, asserted by exact phrase |
| 6 | Undated history in the backlog entry | **Fixed.** Dated 2026-10-10 |

Process note: the foreground full-suite run beside a background review hit one load-sensitive failure in `tests/cli/test_direct_cmd.py::test_direct_jira_relocated_root_preexisting_dirt_aborts_before_detail`; it passes alone and in the clean runs. Not changed.
