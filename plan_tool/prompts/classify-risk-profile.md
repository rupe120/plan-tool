# Classify a seed's risk profile

Use only the supplied seed text. Do not inspect the repository, read files,
search for consumers, or rely on repository-local documents.

Propose `low` only when the seed itself establishes all of these conditions:

1. Deletion or removal dominates the work.
2. No consumer, caller, client, or dependent remains.
3. The work adds no new external, schema, API, contract, or runtime surface.

Otherwise propose `standard`. You may propose only `low` or `standard`; never
propose `high`.

Respond with ONLY this JSON object shape, with no prose, markdown fences, or
additional keys:

```json
{
  "tier": "low",
  "rationale": "one non-empty line that cites the seed evidence",
  "evidence": {
    "deletion_dominance": "exact non-empty seed excerpt",
    "no_consumer": "exact non-empty seed excerpt",
    "no_new_surface": "exact non-empty seed excerpt"
  }
}
```

Set `tier` to either `low` or `standard`. For `low`, every `evidence` value
must be an exact excerpt from the supplied seed and must establish its named
condition. For `standard`, every `evidence` value must be `null`.

## Seed

```
${seed_text}
```
