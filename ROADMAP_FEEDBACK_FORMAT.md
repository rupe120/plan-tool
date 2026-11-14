# Roadmap feedback ledger format

> **Source of truth:** `plan_tool/roadmap_feedback_ledger.py` parses, validates, and renders this file. Code wins on disagreement.

The ledger at `docs/implementation-plans/roadmaps/<slug>/feedback-ledger.yaml` is mutable reviewer input. It is not canonical roadmap content, an accepted-head selector, or immutable feedback history. Immutable roadmap artifacts do not carry mutable reviewer feedback; `AcceptedRoadmapHead` remains the sole selector of canonical artifact content.

## Lifecycle and ownership

Every ledger is `ledger-native` (`ledger_state: ledger-native`): the first stage run creates it that way, and it is ready for reviewer mutations from the start.

Reviewers use `--submit-feedback`, `--retarget-feedback`, `--edit-feedback`, `--defer-feedback`, `--close-feedback`, and `--reopen-ledger-feedback`. Each item has an `item_id`, target, request, lifecycle state, submitted source version, and target fingerprint. Valid item states are `open`, `awaiting-review`, `deferred`, and `closed`; a closed item has no live proposal. A live `proposal` carries the proposed `response` and the `candidate_version_id` of the stored candidate that produced it. `legacy_source` is a retained schema field: it is `null` on every item the tool creates. A target binds either an entire artifact (`kind: artifact`, no `row_id`) or one exact row (`kind: row`, with `row_id`). The source version and fingerprint make changed targets stale; retarget or edit deliberately, never automatically.

## Worked ledger

This canonical YAML is a complete parseable example. Commands write real digests; hand edits must retain canonical rendering.

<!-- ledger-example:start -->
```yaml
schema_version: 1
roadmap_slug: my-project
ledger_state: ledger-native
reviewer_feedback_groups:
- predecessor_version_id: '0000000000000000000000000000000000000000000000000000000000000000'
  items:
  - item_id: rename-order
    target:
      artifact_key: domain
      kind: row
      row_id: workflow-review
    request: Clarify the review workflow order.
    state: open
    submitted_against_version_id: '0000000000000000000000000000000000000000000000000000000000000000'
    target_fingerprint: '0000000000000000000000000000000000000000000000000000000000000000'
    proposal: null
    legacy_source: null
derived_context: []
```
<!-- ledger-example:end -->

## Ledger-to-candidate workflow

1. Start from the accepted version the first stage run published.
2. Submit or edit reviewer-owned ledger items; only current `open` items are eligible. Reviewers never choose a structural feedback type or route.
3. Run `plan-tool roadmap <slug> --propose-candidate`. Validated typed operations classify the stored batch as bounded or structural; request wording grants neither classification nor write authority. The command snapshots eligible items and current roadmap-derived context into one exact root/source batch and stores an inert candidate. It does not rewrite an accepted artifact. While a candidate is active, the new batch takes that candidate as its source, structural or not, so `--propose-candidate` stacks under an active structural candidate and never refuses because of the active candidate's route. The unpromoted candidates above the recorded accepted root form the stack.

   A valid proposal that adds an eligible prose-bearing design row also carries a nonblank, row-named prose fragment for that row. The candidate keeps each fragment with its added row and presents it for structural review; it remains inert with the rest of the candidate until approval and promotion. [Roadmap format](ROADMAP_FORMAT.md) defines the immutable operation schema, validation, and authority boundary.
   A candidate can add, replace, or revise a stack row, but cannot retype its `concern` or remove it. A candidate that introduces the `stack` collection on a lineage that lacks it carries every required concern in that one candidate, because totality binds once the collection is present. Candidate review prints a stack callout with the rows the candidate added, changed, and opened; the callout is display only. [Roadmap format](ROADMAP_FORMAT.md) § "Stack rows" defines the schema and gate.
4. A bounded candidate follows its stored review requirement. A stack is structural when any candidate above its recorded root stores a STRUCTURAL route; the stack is derived at use from stored candidate records, and a candidate with no stored route contributes nothing. A structural stack is disclosed and receives one exact decision on its top candidate, which can itself be presentation-only, with `--decide-candidate CANDIDATE_VERSION_ID --candidate-decision approve|edit|reject`. Every decision covers the whole stack of unpromoted hops above the accepted root, not only the top candidate:
   - Approve takes two invocations. The first, without `--confirm-stack-digest`, prints every unpromoted hop, the cumulative diff from the accepted root to the top candidate, the top candidate's disclosure, and a stack digest. It writes nothing and exits with status `2` (`approve confirmation-required`), so automation never reads it as an approval. The second repeats the command with `--confirm-stack-digest DIGEST`, the digest exactly as printed. The library recomputes the digest under the writer guard, and a differing digest refuses with no write. The confirmed approval creates a `structural-approval` review seal bound to the top candidate identity and its stored content identity; that invocation is the seal's one construction site. The confirm is a flag value, not a terminal prompt, so scripts, containers, and terminals use the same two invocations; `-y` is refused beside a candidate decision and is not confirmation.
   - Edit stores a replacement candidate that requires a fresh decision, and its output prints the replacement's stack. The edit is accepted when the replacement's stack carries a structural hop, even if the replacement's own route is presentation-only.
   - Reject promotes nothing and drops every unpromoted hop above the accepted root: rejection releases only the active candidate, names the dropped hops in its output, and preserves immutable candidate and decision history, so the dropped hops stay stored.

   Edit and reject print the stack first and take no confirm; only approve has a confirm step. The `--propose-candidate` output prints the same stack when the stack it stores carries a structural hop. The digest is stateless: it is recomputed at confirm time and never stored, and it covers the stack's stored facts (the accepted root, hop identities and order, stored routes, batch receipts, selected feedback, typed operations, each hop's diff, and the cumulative diff), not the printed wording.

   The reviewed nonstructural route (`--review-candidate` and `--answer-question`, and an answered seal promoted with `--promote-review-seal`) refuses a stack that carries a structural hop and names `--decide-candidate`; a `structural-approval` seal reaches publication during its confirmed approval as item 5 describes.
5. A matching digest creates a `structural-approval` seal, then publishes its top candidate as a second, separately-durable write. The confirmation invokes `promote_review_seal`, which rechecks the accepted root, active candidate, stored candidate, seal, and gates before its journaled publication advances `AcceptedRoadmapHead` to the top candidate, which carries every hop beneath it, releases the active pointer, and applies the seed-state effect when any hop above the recorded root stores a STRUCTURAL route. A later `--promote-review-seal` for that same structural seal returns `already promoted` without writing; it remains a promotion command for answered seals and for a structural seal left by an interrupted confirmation. Promotion re-derives the stack and refuses a structural stack whose seal is not `structural-approval`; recovery of an interrupted promotion asks the same question of the same identifiers. The next `--propose-candidate` starts from that promoted accepted version, never from a pending candidate or mutable ledger state.

Candidate, review, and promotion records bind recorded root, direct source, batch items, context, and evidence; they cannot substitute later ledger state. A later unrelated ledger edit does not invalidate recorded evidence. A changed processing pair or admitted item that no longer matches its snapshot refuses candidate storage without consuming the reviewer edit or changing a candidate pointer. Promotion never rediscovers live ledger eligibility.

Not built: workflow authoring, automatic approval, feedback grouping, multi-user approval, or a general transaction system; each needs its own decision and plan.

Invalid output, failed gates, interruption, rejection, edit, and stale bindings are non-publication outcomes: they do not advance `AcceptedRoadmapHead`, rewrite canonical roadmap artifacts, or rewrite seeds. The lifecycle updates selected ledger items only where its stored records require it; unselected feedback remains unchanged.

## Settlement confirmation

Decision settlement remains a separate selector-based operation. If settlement would stale an active candidate, it returns `confirmation-required` and prints the exact confirmation-evidence receipt final. In a separate invocation, bind and apply the response:

```bash
plan-tool roadmap <slug> --respond-decision-settlement RECEIPT_FINAL --decision-settlement-yes
plan-tool roadmap <slug> --respond-decision-settlement RECEIPT_FINAL --decision-settlement-no
```

This is deliberately non-interactive: there is no prompt or `-y` shortcut, so scripts, containers, and terminals use the same receipt-bound response.

For ordinary operation, see [the roadmap walkthrough](docs/how-to/roadmap.md). `ROADMAP_FORMAT.md` owns immutable artifact schema and structural routes.
