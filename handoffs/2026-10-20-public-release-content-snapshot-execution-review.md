# Public-release snapshot implementation review

Use merged [PR #123](https://bitbucket.org/protagona/plan-tool/pull-requests/123) to
review the accepted content-preparation decisions. The merged selected bytes
match the independently tested prose candidate. Current next
actions belong in [the pickup record](2026-10-19-public-onboarding-and-release.md).

## Review map

| Area | Property to check |
| --- | --- |
| Selection record and receipt | Exact selected files, report exclusions, useful conclusions and honest verification limits |
| Governing documents | The same provenance judgment in both authorities, using reports, decisions, code and tests; uncertainty does not justify structural rework |
| Policy source and PDF | Owner-approved content, matching text, current tool references and unchanged governance rules |
| Reference repairs | Correct live targets and complete explanations, with findings and closure labels preserved |
| Backlog and coordination | #513 content preparation is complete; #514 distribution and #515 consumer work retain their own owners |

Most added lines in the selection record enumerate report exclusions. Review the
selection rule and accounting before sampling that inventory. The changes add no
runtime code or test behavior.

## Finding dispositions

| Finding | Disposition |
| --- | --- |
| Omitted report references need explicit edit ownership | Fixed: the 13 consumers belong to step 2, with closure checked in independent verification |
| Live RUNBOOK, arc and planning-detail links point at moved files | Fixed: 28 navigation occurrences use existing canonical targets |
| Guidance and compressed ledgers do not carry enough decision context | Fixed: keep the explanation, evidence, disposition and closure needed to continue the work |
| Fresh test PATH omits Python/backend prerequisites | Resolved as environment setup: expose the snapshot Python and installed executable prerequisites; six focused repros and the full suite pass without source/test edits |
| Implementation acceptance | Owner-merged PR #123; future contract/policy changes retain architect-tier review |

## Verification and closure

The [2026-10-20 receipt](../docs/evidence/public-release-content-snapshot-verification-20261020.md)
identifies the exact candidate: ordinary frozen installation succeeds; 573 focused
tests and 14,697 full-suite tests pass, with 67 existing skips. PDF verification
covers all five A4 pages, extracted text, title metadata and URL annotations.
Selected bytes remain unchanged after checks.

The plan-canonical post-run sweep reports no code steps to reconcile. Independent
local reviews find no actionable regressions; local review closure is converged.
Publication remains a separate owner decision.
Documentation revisions require a new candidate identity and appropriate checks;
the receipt's measurements continue to describe only its named bytes.
