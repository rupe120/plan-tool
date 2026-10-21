# Public-release cleanup decisions

Preserve these decisions when changing public setup, examples or package metadata.
The cleanup review closes by owner merge of PR #120. Current implementation
review and release actions belong to [the pickup record](2026-10-19-public-onboarding-and-release.md).

## Decisions to preserve

- Use Apache-2.0 in LICENSE, package metadata and contributor-facing guidance.
- Select reviewers per PR; keep architect-tier review for contracts and policy.
- Keep organization targets and contributor mappings in ignored local configuration.
  Tracked setup uses generic examples and portable paths.
- Use neutral example identities while preserving fixture correlations and behavior.
  Retain meaningful technical-product references.
- Keep the owner-authored policy PDF aligned with its Markdown source.
- Keep content preparation, distribution/update procedures and consumer onboarding
  as separate work under #513, #514 and #515.

## Check future changes

Check license bytes and package metadata, local-context reads, reviewer rules,
renamed references, policy source/PDF alignment and fixture identity correlations.
Run the affected checks and the full suite when fixture or runtime behavior changes.
Use the [selection record](../docs/evidence/public-release-content-snapshot.md)
for content decisions and the [verification receipt](../docs/evidence/public-release-content-snapshot-verification-20261020.md)
for measured candidate results. Publication remains an explicit owner decision.
