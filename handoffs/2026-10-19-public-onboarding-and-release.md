# Public onboarding and release pickup

The sanitized history is published on Bitbucket and GitHub. Internal work uses
Bitbucket. Version 1.0.0 and the skill-focused README are merged into Bitbucket
main; the internal CLI is current. Finish mirror synchronization and release
tagging before treating the 1.0.0 release as fully distributed. Demo refresh is
deferred and does not block that work.

## Current pickup

| Item | Verified state on 2026-10-21 |
| --- | --- |
| Internal source | `git@bitbucket.org:protagona/plan-tool.git` |
| Bitbucket main | `d90b84ef2f7f0eb4e7222f2cc7cecfea9f7f0aa5` — PR #131 merged |
| Version | 1.0.0 in package metadata and lockfile; changelog entry present; PR #130 merged |
| GitHub mirror main | `03cbb6882696edd5114b3d739517a56919400025` — sanitized v0.2.0 release; behind Bitbucket |
| Release tags | `v0.2.0` exists on both hosts; `v1.0.0` is not present in the checked refs |
| CLI/sync clone | `/Users/joshrusso/bitbucket/protagona/plan-tool`, clean on Bitbucket main `d90b84ef2`; global `plan-tool --version` reports 1.0.0 |
| Working clone | `/Users/joshrusso/temp/plan-tool/plan-tool-clones/plan-tool-2`; current handoff branch `docs/release-handoff-current`, based on merged Bitbucket main |
| Bitbucket protection | Restored according to the owner; independent branch-restriction reads return 403 for missing token scopes |
| Demo branches | All four names on both hosts point to the shared needs-updating notice; content refresh remains deferred |

The [publication record](2026-10-21-sanitized-publication.md) owns the exact
sanitized release refs, successful readback, recovery paths and clone cutover.
Its v0.2.0 measurements describe that frozen release, not later main commits.
The [demo handoff](2026-10-21-demo-refresh.md) owns the deferred update work.

## Completed release and onboarding work

- PR #129 merges the final content-selection records, primary-folder READMEs,
  durable how-to guidance and the dedicated `docs/demos/` entry point.
- The owner-approved sanitized publication replaces both hosts' main and tag
  histories. Its root is `9c10d74ca970e97c98a4ce6895ebdc0836b668d9`; the initial
  v0.2.0 release commit is `03cbb6882696edd5114b3d739517a56919400025`. The old
  v0.1.0 tag is retired, and recovery bundles are preserved privately.
- PR #130 merges the 1.0.0 version, matching lockfile entry and release notes.
  Its version-bump commit is `e6e9a8e84218`; 57 release tests and the mandatory
  full pre-push suite pass. Dependency pins stay unchanged.
- PR #131 merges skill-focused onboarding. The README leads with assistant
  setup and conversational planning/execution requests, names both audit gates,
  and places direct CLI guidance below. Internal installation uses Bitbucket.
  Changed link targets and compatibility anchors pass; 42 installer/reference
  tests and the mandatory full pre-push suite pass.
- Owner authorship of the policy Markdown/PDF and Apache-2.0 inclusion are
  settled. The policy PDF digest and exact selected-content checks remain in
  the [merged-selection receipt](../docs/evidence/public-release-merged-selection-verification-20261021.json).

## Next actions

1. Use the designated CLI/sync clone to compare both hosts and fast-forward the
   GitHub mirror to reviewed Bitbucket main. Re-read current refs before acting;
   the recorded mirror state is a pickup measurement. Keep one shared root and
   preserve the clone's dual push URLs and ignored sync configuration.
2. Prepare the `v1.0.0` tag from the merged release history and obtain explicit
   authorization before pushing that tag. The earlier history-replacement
   approval covers v0.2.0 publication, not this new tag. Keep the existing
   v0.2.0 release tag. Public visibility and any organization transfer are
   separate actions.
3. Continue onboarding follow-ups #508–#512 and #377, then exercise #515 in a
   fresh consuming repository. #510 owns the walkthrough; #511 owns skill
   installation/refresh guidance. Recheck their tracking state before taking
   work; this handoff does not certify those items complete.

The Slack announcement draft uses the internal Bitbucket URL. No Slack message
is sent. Demo regeneration, a live demo model run, and both demo audit gates
remain outside the current release route.

## Recovery and local conventions

- Private recovery directory:
  `/Users/joshrusso/.local/share/plan-tool/release-backups/2026-10-21-pr129`.
  It contains verified host and local-ref bundles, the published candidate,
  exact operation plan, successful results and previous installed skill copies.
- `archive/pre-sanitization-main-20261021` branches and other former-history
  local refs are private recovery material. Do not push or merge them into the
  sanitized history. For additional clones, preserve local work and refs before
  realigning main with the remote.
- Preserve ignored `.local/reconcile-remotes.py` and `REPO_SYNC.local.md`.
  The designated clone owns dual-host synchronization; this working clone's
  origin pushes only to Bitbucket.
- The earlier publication-confirmation branch holds local pickup records that
  are not merged into main. This handoff branch carries their useful records
  forward; do not merge former source-history branches to recover documentation.
- Preserve the unrelated untracked
  `handoffs/2026-10-16-token-ledger-logging-gaps-reverted-attempt.md`.
- The binary-PDF prompt transport issue, false PDF Files-coherence diagnostic,
  onboarding/workflow-consistency issue and #516 cleanup-use-case example are
  follow-ups. Verify their backlog/tracker state before implementation.

When this release route closes, move durable decisions to their canonical
owners and retire pickup records under [the retention rules](README.md#retention).
