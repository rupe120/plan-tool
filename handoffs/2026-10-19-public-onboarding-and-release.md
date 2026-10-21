# Public onboarding and release pickup

Continue with review of the local 2,608-path sanitized release before any remote
publication. The demo refresh is deferred by owner decision on 2026-10-21 and
does not block cleanup or release preparation. Content preparation is accepted
through merged [PR #123](https://bitbucket.org/protagona/plan-tool/pull-requests/123),
and #513 is complete. Keep subsequent release work separate from the completed
content-preparation plan.

## Session pickup

- Working clone: `/Users/joshrusso/temp/plan-tool/plan-tool-clones/plan-tool-2`.
- Accepted baseline: main `506b61dca`, including merged PR #128's cleanup records
  and PR #127's retro. Current preparation branch: `docs/public-release-final-selection`.
- Owner-approved content selection: 2,601 paths, extending the prior 2,590 with
  11 experiment/evidence records. The [selection record](../docs/evidence/public-release-content-snapshot.md#file-set-accounting)
  enumerates all 17 additions to the original non-report baseline. Verified source:
  `d0eb93c263e18dee192bac1b450a861d514a6f31`; independent root:
  `06774684566f7ff93482f075836724e467217ce8`. The
  [final-selection receipt](../docs/evidence/public-release-final-selection-verification-20261021.json)
  owns its inventory, hashes and checks. This receipt and later pickup edits are
  outside the frozen candidate; do not claim they are part of its tested bytes.
  Preserve `.tmp/public-release-final-selection.bundle` as the local root artifact.
- The current local release base selects 2,608 paths from source `256f466380`:
  the 2,601-path verified set plus the final-selection receipt, four primary
  documentation-folder READMEs, the demo refresh handoff and the documentation
  placement review handoff. Independent root `949e6dd5e8c093e7c073e004d468eb022a15484c`
  has one parentless commit and exact selected modes/blobs; its inventory and
  digests are in `.tmp/public-release-demo-base.verification.json`. The older
  final-selection receipt is a frozen baseline, not a claim about these bytes.
- Remote cleanup is complete for the approved branches. Preserve the four demo
  stages on each host for separate updates. The [triage record](../docs/evidence/public-release-outside-commit-triage-20261021.md)
  and [correctness comparison](../docs/evidence/public-release-audit-next-steps-comparison-20261021.md)
  retain the evidence; no implementation replay is needed for retired branches.
- Private recovery bundle: `.tmp/public-release-pre-snapshot-refs-20261021.bundle`.
  Copy it to durable private storage before destructive operations; `.tmp/` is transient.
- Use this clone's `.venv/bin/plan-tool`; the global CLI targets the main
  integration clone `/Users/joshrusso/bitbucket/protagona/plan-tool`.
  That clone owns dual-host sync. This clone pushes only Bitbucket.
- Preserve ignored `.local/reconcile-remotes.py` and `REPO_SYNC.local.md`.
  Keep publication, tag decisions and history replacement separately authorized.

## Current decisions

| Concern | Direction |
| --- | --- |
| License | Apache-2.0; keep package metadata, LICENSE and documentation aligned |
| Policy | Include the owner-authored Markdown and PDF; keep their content aligned |
| Public source | `https://github.com/rupe120/plan-tool`; a later Protagona organization transfer is possible |
| Publication | Prepare one verified sanitized root for both hosts; retain shared ancestry and synchronize through one designated clone |
| Installation | Clone plus `uv tool install --editable .`; explain clone retention and dependency/skill refresh |
| Onboarding | Recommend the assistant skill as the primary route, with direct CLI guidance available |
| Review | Select reviewers per PR; retain architect-tier review for contracts and policy |
| Examples | Use generic organization/client identities while preserving technical behavior and meaningful third-party references |

Git hosting does not select a Jira provider or an approval policy. #509 must name
its configuration reader and runtime behavior. Keep backend choice, model choice,
authentication and cost guidance distinct.

## Preparation result

- Package and repository declarations use Apache-2.0.
- Organization targets and contributor mappings use ignored local configuration;
  tracked examples use generic values and portable paths.
- Fixture identities are synthetic, with event correlations and test behavior
  preserved. Approved TypeSafe, System One, Jev and research-product references stay.
- The selection record defines exact report exclusions and preserves the decisions
  and useful conclusions that support current guidance.
- Live navigation points to current guides and contracts. Review ledgers preserve
  finding explanations, dispositions and their distinct closure outcomes.
- The policy PDF matches its Markdown source and includes the current convergence
  and reconciliation guidance. PDF checks cover all five A4 pages, title metadata,
  text completeness and link annotations.

Use the [selection record](../docs/evidence/public-release-content-snapshot.md)
for the file boundary and the
[prose verification receipt](../docs/evidence/public-release-prose-verification-20261020.json)
for exact tested bytes and results. The 2026-10-20 candidate passes normal locked
installation, 573 focused tests and 14,697 full-suite tests, with 67 documented
existing skips. These measurements apply to the candidate named in the receipt;
verify a new candidate whenever selected files change. The receipt names source
`b73141d99fc5c4983c33d534ce5d6ac3dce673d4` and independent root
`80dba090cc2f2251dcd6d5ea0558225199ddf85a`; it does not certify the subsequent
distribution-guidance edits.

The [demo refresh handoff](2026-10-21-demo-refresh.md) retains the exact local
release and demo refs and test results. Demo updating and its live model run are
deferred until the demo is needed; preserve the existing remote demo branches.

## Next actions

1. Review the current local bundle and exact refs in the demo refresh handoff.
   `main` is a local Release 0.2.0 commit above the sanitized root, `v0.2.0`
   is an annotated local tag, and the four demo stages form one direct chain.
   Locked installation, full suite (14,698 passed, 66 skipped), Jira lint,
   bundle verification and `git fsck` pass. The three Jira lint warnings are
   advisory estimates below the 4h soft floor. The earlier 2,601-path receipt
   remains available for its own tested snapshot.
2. Inspect a fresh remote ref inventory and the private recovery bundle before
   any main or tag replacement. Keep all four demo branch names on both hosts;
   any ancestry accommodation needed for the sanitized history is separate from
   refreshing their demonstration content. A live demo run is not a release gate.
3. Continue #508–#512 and #377, then exercise #515 in a fresh consuming repository.
   #510 owns the walkthrough; #511 owns skill installation and refresh guidance.

Owner authorship of the policy Markdown/PDF and Apache-2.0 inclusion are settled.
No completed plan step needs restarting. Public visibility, remote replacement
and transfers require approval for the concrete operations and destinations.

## Distribution guidance verification

The #514 documentation checkpoint has two reviewed passes covering installation,
update environments, copied-skill scope, shared ancestry and partial-push recovery.
The first pass adds the missing PATH recovery instruction; the second finds no
remaining material documentation issue. Verification on 2026-10-20 covers:

- Isolated `uv tool` editable installation and reinstallation, executable version
  and installed-tool listing, without changing the machine's installed CLI.
- Codex user-skill installation and forced refresh in a temporary home; both
  installed files match the bundled router and canonical directives.
- Relative document targets and whitespace checks; 87 focused tests pass.
- Full suite: 14,697 pass and 67 skip in 57.78 seconds.

The 2026-10-21 frozen candidate additionally passes locked installation, 573
focused tests and 14,697 full-suite tests (67 skips, 66.59 seconds). Exact modes,
blobs, one parentless root, independent storage, live targets and the PDF digest
are verified. Both hosts permit authenticated read-only ref enumeration. Write
permissions, ref disposition, release tags and fresh-consumer onboarding retain
their separate requirements; #514 remains open.

## Follow-ups and maintenance

- The binary-PDF prompt transport failure and the false PDF Files-coherence
  diagnostic are tool follow-ups, separate from the content cleanup.
- The onboarding/workflow-consistency bug and #511 own alignment between installed
  skills and canonical driving instructions.
- #516 owns the non-feature repository-cleanup example; its local tracking work
  remains on the original planning branch until separately reviewed.
- Preserve the unrelated untracked
  `handoffs/2026-10-16-token-ledger-logging-gaps-reverted-attempt.md`.

When this release route closes, move durable decisions into their canonical
owners and retire this pickup record under [the retention rules](README.md#retention).
