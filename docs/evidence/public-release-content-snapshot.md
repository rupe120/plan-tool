# Public release content selection

Use this record to choose release content, preserve the evidence behind current
decisions, and verify a publication candidate. [The release backlog](../../BACKLOG.md)
owns remaining distribution and onboarding work; [the pickup record](../../handoffs/2026-10-19-public-onboarding-and-release.md)
owns the next action. The [verification receipt](public-release-content-snapshot-verification-20261020.md)
identifies measured candidate bytes and results.

## Content selection

Retain implementation, tests, package metadata, guides, generic examples, plans,
lessons and review records that support the project. Retain captured report files
byte-for-byte: they are the evidence the audit workflow is tuned against. A report
may contain local home-directory paths; leave them in place, because rewriting a
report changes its hash and qualification metadata, and do not rewrite either to
make a sanitized capture appear equivalent.

The 2026-10-21 sanitized candidate omitted 5,616 reports. They were restored
byte-identical from `archive/pre-sanitization-main-20261021` on 2026-11-05 after a
scan found nothing in them that the retained reports lack: the only local context
in either set is `/Users/<name>` paths, with no emails, tracker sites, cloud account
identifiers, or vocabulary absent from the current tree. The scan is a pattern and
vocabulary check, not proof that 81 MB of audit text holds nothing sensitive.

| Content | Treatment and owner |
| --- | --- |
| Package and ordinary project documents | Retain; keep Apache-2.0 declarations and current examples consistent |
| Organization/client examples and fixture identities | Use generic values while preserving behavior, correlations and test meaning |
| Technical references | Retain TypeSafe, System One, Jev and relevant research-product references |
| Organization targets and contributor mappings | Keep actual values in ignored local configuration; track generic examples |
| Captured reports and sidecars | Retain byte-for-byte; leave local paths unscrubbed so hashes stay valid |
| Plans, seeds, lessons and review ledgers | Retain useful design intent, evidence, dispositions, unresolved work and settled decisions |
| Policy Markdown and PDF | Include both under Apache-2.0; the owner confirms authorship |
| Integration sizing example | Retain sanitized payload identity separately from measurement-input identity |

### File-set accounting

The 2026-10-20 selection baseline contains 8,200 paths. The frozen candidate
retained 2,584 of them, including both policy artifacts, and omitted its 5,616
report paths (since restored; see [Content selection](#content-selection)). The
owner-approved selection adds these 17 explicit records for a 2,601-path candidate:

- `docs/evidence/public-release-audit-next-steps-comparison-20261021.md`
- `docs/evidence/public-release-content-snapshot-verification-20261020.md`
- `docs/evidence/public-release-content-snapshot.md`
- `docs/evidence/public-release-distribution-verification-20261021.json`
- `docs/evidence/public-release-merged-branch-triage-20261021.json`
- `docs/evidence/public-release-outside-commit-triage-20261021.md`
- `docs/evidence/public-release-prose-verification-20261020.json`
- `docs/evidence/public-release-ref-disposition-20261021.md`
- `docs/how-to/install-and-update.md`
- `experiments/RETRO-token-optimization.md`
- `experiments/harness-instruction-loading/DESIGN.md`
- `experiments/harness-instruction-loading/RECHECK.md`
- `experiments/harness-instruction-loading/RESULTS.md`
- `experiments/harness-instruction-loading/scored-results.json`
- `experiments/token-ledger/REPORT.md`
- `handoffs/2026-10-20-public-release-content-snapshot-execution-review.md`
- `handoffs/2026-10-20-public-release-reference-repair-review.md`

The experiment additions retain the protocol, results, scored measurements,
recheck and retro that support their conclusions. Cleanup records retain the
branch dispositions and behavior comparisons. Harness executables, transient
inputs and local sync scripts are outside this selection.

Each dated receipt describes only its named source and candidate. Store new
verification results outside the frozen candidate; include them in a later
selection only through an explicit decision, rather than changing the frozen set.

Retain executable modes and `AGENTS.md` → `CLAUDE.md`. Review every later file
addition explicitly; new captured reports are retained like the restored ones.
Removing a plan from
the manifest alone does not remove it from directory discovery or the candidate.
Keep registered plan paths and selected files consistent.

The baseline path inventory digest is
`4331d7353c14f0bf2b674f66f6421ee28b37a6c5a31cb86f66eb2c8d4d93a040`,
computed over Git's NUL-terminated path output. The receipt defines the sorted
candidate path/content digests; those hashes describe different sets.

<a id="commit-citation-treatment-step-3"></a>

## Maintainer guidance

Write explanations that let a maintainer understand the current decision and
follow the next action from the repository. Keep a dated example only when it
justifies a settled choice, explains a failure to avoid, supports a measurement,
or describes a compatibility contract that still applies.

When a finding recurs, compare reports or conclusion summaries, decisions,
current code and tests. Use relevant revisions when available. If the evidence
cannot establish whether a prior fix caused the recurrence, state that uncertainty
before proposing structural rework. Both governing documents use this rule.

Review ledgers keep each finding's evidence, disposition and closure. Preserve
`fixed`, `refuted`, `declined`, `tracked` and `pending` outcomes, and distinguish
convergence from owner-stopped work or closure by owner decision. Remove session
narrative when it no longer helps a maintainer continue the work.

A source identifier is useful only when it supports a concrete claim. Explain
the behavior or result directly instead of asking the reader to infer it from
an identifier. Preserve content digests, artifact identities and their byte-level
meaning. Use current documentation targets for live navigation.

<a id="preserve-conclusions-and-repair-dependencies"></a>
<a id="step-2-preparation-and-reference-review"></a>

## Evidence and references

Keep the conclusion in its existing owner wherever practical. A report summary
explains a result; it is not a reusable audit report and does not confer current
qualification. Test and audit results apply to their named inputs.

<a id="applied-dispositions-and-retained-conclusions"></a>

### Decisions supported by retained evidence

| Concern | Decision and reason | Maintained owner |
| --- | --- | --- |
| Audit checkpoint recovery | Preserve a successfully written resumable prefix; determine recovery from the artifact present after publication. Keep terminal residue and successful-resume provenance explicit | [Audit-pass persistence](../explanations/audit-pass-persistence.md) |
| Authored artifact versions | Version plan/detail formats explicitly and preserve refusal, byte-preservation and recovery contracts. A scoped backend result does not become a clean result merely because it contains no findings | [Structure-versioning record](authored-artifact-structure-versioning.md) |
| Coverage replay | Keep the hermetic capture-runner proposal withdrawn: its proof system costs more than the bounded measurement it serves. A new need requires independent evidence | [Backlog decisions](../history/backlog-decisions.md) |
| Jira-grade instrument and measurement | Separate building the instrument from measuring it; require correct audit grounding, independent baselines and a noise-aware comparison | [Planning guidance](../explanations/nondeterministic-plan-design.md) |
| Convergence evaluator | Preserve the owner-selected withdrawal rather than expanding an interlocked proof mechanism in response to more findings | [Developer-docs decisions](../../handoffs/2026-09-14-developer-docs-and-tracking.md) |
| Brief drift | Keep lifecycle ownership and source-baseline acceptance with the stage runner; non-stage routes retain their separate boundary | [Roadmap delivery decisions](../../handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md) |
| Candidate collection guidance | Use actual collection names and verified source hints while preserving persisted capsule and receipt identity | [Candidate guidance](../../handoffs/2026-09-25-roadmap-candidate-vocabulary-retry.md) |
| Snapshot design audit | The 2026-10-20 bare audit has zero conceptual findings at 0/6 details; the final detail audit has zero at 6/6 with confirmed-dry coverage. The false PDF diagnostic leaves the overall result `awaiting-human-action`; do not call it a clean tool verdict | [Design review](../../handoffs/2026-10-20-public-release-content-snapshot-plan-review.md) |

### Reference verification

Check live links against selected files and anchors. Keep illustrative fixture
paths and installed-skill sibling layouts distinct from navigation users must
follow. For experiment instructions, name the repository, corpus, revisions and
store needed to run a new measurement; keep a new result separate from a dated
study. Do not change a frozen experiment's conclusions to make it reproducible
under different inputs.

Report-dependent reader content belongs in these 13 document owners:

- `docs/evidence/authored-artifact-structure-versioning.md`
- `docs/explanations/audit-pass-persistence.md`
- `docs/explanations/nondeterministic-plan-design.md`
- `docs/history/backlog-decisions.md`
- `docs/implementation-plans/archive/2-jira-grade-01-detail-instrument.md`
- `handoffs/2026-09-14-developer-docs-and-tracking.md`
- `handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md`
- `handoffs/2026-09-25-roadmap-candidate-vocabulary-retry.md`
- `handoffs/2026-10-19-public-onboarding-and-release.md`
- `handoffs/2026-10-20-public-release-content-snapshot-plan-review.md`
- `plan-seeds/archive/jira-grade-01-detail-instrument.distilled.replaced.md`
- `plan-seeds/archive/jira-grade-01-detail-instrument.replaced.md`
- `BACKLOG.md`

The 2026-10-20 reference review checks 28 live navigation occurrences and all ten
compressed ledgers. Search matches include historical records, examples and
content identities; a match count is not a defect count. New required dependencies
need an explicit repair or disposition before candidate verification.

<a id="policy-retention-and-verification-step-4"></a>

## Policy source and PDF

Use `docs/reference/ai-assisted-development-policy.md` as the source and regenerate
`AI_SDLC_POLICY.pdf` whenever its text changes. Both artifacts are owner-authored
and selected under Apache-2.0. Keep governance responsibilities and approval
rules intact when correcting factual tool references.

The current guidance describes `convergence <name>` as advisory plan-loop trends.
Before execution, `reconcile-plan --refresh` uses code as canonical; after execution,
`reconcile-code --all` uses the plan as canonical.

For a rebuild, use policy-title metadata, A4 pages and 18 mm margins. Avoid
heading/row breaks, duplicate visible titles, browser headers and checkout links.
Inspect extracted text and every rendered page. PDF extraction can reorder table
cells and add list numerals, so a text tally does not replace visual inspection.
Use a temporary browser profile and a rendering environment with the required
permissions; no new package dependency is needed.

The verified five-page PDF is 209,909 bytes, with SHA-256
`225bc6e791d6676a69ce23f754fe793d09e2ec4245dc2aa13d685162084ff872`.
The 2026-10-20 rebuild uses Pandoc 3.9.0.1, Chrome 155.0.8059.85 and Poppler
26.08.0. Recheck metadata, text, URL annotations and every page after another rebuild.

## Content identity

The sanitized integration payload is 211,999 bytes, SHA-256
`89120e6b6bb05829600b2dc7f15fa6b0983d7e94a5a52916aca8e3b607764af6`.
Its measurement-input digest is
`d0a742fa4c70f6403a7066eacfedbb621744a530c20093634169cec3824ceb5e`,
with 211,712 measured bytes. Keep these identities separate; a sanitized example
cannot substantiate a measurement of different bytes. The provenance and sizing
files own the detailed limits.

Report identity and qualification stay with the existing fingerprint and
persistence contracts. Capture a new revision for new inputs; do not edit saved
revision metadata or reinterpret report summaries as qualified evidence.

## Build and verify a candidate

1. Freeze a committed preparation source and its explicit selected paths. Preserve
   executable modes and symlinks; omit ignored settings.
2. Export selected bytes into an empty repository with an independent object store.
   Stage the explicit path list with `git add --force --pathspec-from-file=-
   --pathspec-file-nul` so selected ignored-name paths remain included.
3. Check selected bytes/modes, a single parentless commit, no remotes or alternates,
   and `git fsck --full --no-reflogs`. Record path and content digests.
4. Install normally with the tracked lockfile in a fresh environment. Expose that
   environment's Python and required installed executable prerequisites on PATH;
   keep credentials, ignored project settings and source virtualenvs out.
5. Run focused contracts and the full suite. Check live references, structured-file
   parsing, manifest/discovery, payload/PDF identity and bounded procedures using
   selected content. Keep skipped, failed and untested cases explicit.
6. Write a receipt identifying the tested bytes and results. Later edits require a
   new candidate identity and appropriate verification; do not extend an older
   measurement to a different selection.

The [2026-10-20 receipt](public-release-content-snapshot-verification-20261020.md)
records normal locked installation, 573 focused tests and 14,697 full-suite tests
passing, with 67 documented skips. It is evidence about that exact candidate.

<a id="local-pickup-conclusion-step-6-2026-10-20"></a>

## Review and release

Content preparation is accepted through merged PR #123. Preserve architect-tier
review for future governing-rule changes. Publication remains a separate owner
decision.
#514 owns release/update and sync procedures; #515 owns the fresh-consumer
workflow. Keep those responsibilities distinct from content preparation.

The prose review uses present and future descriptions of current behavior,
settled decisions and next actions. Retain dated evidence where it justifies a
current choice or explains a failure to avoid. Remove session chronology and
references that ask a reader to reconstruct the project's former state.

## Captured-report exclusions

*(none)* — every captured report is retained. The 5,616-path list that the
2026-10-21 candidate omitted was retired on 2026-11-05, when those reports were
restored byte-identical (see [Content selection](#content-selection)).
