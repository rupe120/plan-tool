# Public snapshot verification receipt (2026-10-20)

This receipt records the frozen reference-closure candidate. It is a local
release-review artifact **outside** the tested candidate, not an extra selected
file. Public publication and architect-tier implementation approval remain
separate. BACKLOG #513 stays open until required review and shipment conditions hold.

## Frozen candidate identity

| Field | Value |
| --- | --- |
| Preparation source | `51c645eeebd89e0de1c1c0d1cb5c86813347ea69` |
| Independent parentless root | `f0171133caab913c1ff0b31d735f4c91493fe028` |
| Selected paths | 2,587 |
| Path inventory SHA-256 | `a4d0447c7e8cb3c276c4282b3138aa87488fab36995e4ab27a7ba61280aa4b4b` |
| Selected content SHA-256 | `af638eef8157d8c27f58141c5807245631bbd05c3b231c30d9a4d8c99b03988a` |
| Policy PDF SHA-256 | `225bc6e791d6676a69ce23f754fe793d09e2ec4245dc2aa13d685162084ff872` |

Reconstruct the path set from the original 8,200-path selection baseline: omit
all 5,616 exact report paths listed in the
[selection record](public-release-content-snapshot.md), retain both approved
policy artifacts, and add the selection record plus the two explicitly selected
2026-10-20 reference-repair/execution review records. Read each blob and mode from
the preparation source. Hash sorted UTF-8 paths terminated by NUL for the path
inventory. For content, hash UTF-8 `json.dumps(records, separators=(',', ':'),
ensure_ascii=True)`, with sorted `[path, Git mode, SHA-256(blob bytes)]` records.

Export blobs into an empty directory, preserve executable modes and the
`AGENTS.md` symlink, then initialize Git with an empty template and synthetic
verification author. Stage only the explicit selected list using `git add
--force --pathspec-from-file=- --pathspec-file-nul`; ignored-name selected files
must not disappear. Do not clone/import the internal object store.

## Isolation, installation and checks

- Every selected blob and mode matches the preparation source. One root commit,
  no remotes, no object alternates or shared Git storage; `git fsck --full
  --no-reflogs` passes. Only selected content and its independent root enter the verification store.
- The fresh HOME and explicit environment allowlist exclude inherited repository,
  credential, backend, agent-socket, project-context and Python-path settings.
  Global/system Git configuration is disabled. The snapshot's own `.venv/bin`
  is on PATH, followed by an isolated tools directory exposing genuine installed
  `codex`, `claude`, `cursor` and `agent` executable links, then system tools.
  The existing conftest guard against real backend execution remains active;
  backend-switch tests use their existing mocked invokers. No source virtualenv,
  ignored source configuration or credential is copied.
- Homebrew uv 0.12.19 and CPython 3.14.0: `uv sync --frozen --python
  /opt/homebrew/bin/python3.14` succeeds with an initially empty cache and ordinary
  dependency downloads. Eighteen locked distributions and this snapshot's project
  install successfully. `plan_tool.__file__` resolves inside
  this snapshot. Platform support beyond this environment remains untested.
- Focused existing fingerprint/persistence/locator/manifest/data/response suites:
  **573 passed**, 3.34 seconds.
- Complete existing suite, `python -m pytest tests/ -q -n auto -rs`:
  **14,697 passed, 67 skipped**, 60.31 seconds. Existing skips: one scope-diff
  proxy expects a `main` ref absent from the one-branch snapshot; one real-bundle
  smoke test cannot resolve its plan title; 65 retired feedback-route cases.
  No test, assertion, skip marker or fixture changes to obtain these results.
- Repaired live owners (RUNBOOK, four coordination arcs, two planning details,
  handoff index): all inline local-link file targets exist in selected content.
  Contextual review separately preserves historical links, illustrative fixtures
  and installed sibling layout; it does not claim exhaustive reference-style or
  every-anchor verification. The repaired audit anchor exists in its canonical guide.
- Selected PDF hash matches the verified five-page source-aligned rebuild.
  `git diff --exit-code HEAD` confirms selected tracked bytes remain unchanged
  after installation and tests.

Test prerequisites: include the environment's Python and installed backend
executables on PATH. A missing `python` can fail benchmark shell gates with 127;
a missing backend executable can send mocked switch tests into their error paths.
Keep the real-backend execution guard active and diagnose setup failures before
changing application code or tests.

## Review and remaining boundary

The bounded follow-up repairs all 28 live navigation occurrences in its regenerated
candidate set, keeps useful explanations and evidence self-contained, preserves
all ten compressed ledgers' findings/dispositions/closure labels, and synchronizes
only the canonical provenance paragraph in the tracked directive copy.
Read-only reviews find no actionable regression. The earlier plan-canonical
post-run sweep has no code steps to reconcile; no runtime code changes occur.

These checks establish this exact frozen candidate's installation, tests and
bounded reference repairs. They do not certify every historical claim, recover
external stores, exercise real model/Jira/provider credentials, grant rights for
unreviewed content categories, approve public publication, or supply architect
review. #514 retains distribution/update and sync work; #515 retains the separate
fresh-consumer workflow. Owner-confirmed policy rights remain settled.

Later local receipt/backlog/handoff/review-status edits are outside these tested
bytes. Publish only an explicitly identified approved candidate; exporting later
working-branch bytes requires renewed verification. Do not mistake the internal
Bitbucket branch's ancestry for this independent root.
