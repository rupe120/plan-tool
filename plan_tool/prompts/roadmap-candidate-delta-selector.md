# Immutable roadmap candidate proposal

Work only from the issued capsule payload and receipt below. They are the complete authority for this request. Do not inspect repository files, root documentation, filesystem paths, an accepted head, or any other source. The compact inventory is discovery-only: it does not authorize an edit.

Return one unfenced JSON object and nothing else. Its root must contain exactly one disposition:

- `{"delta":{"operations":[...]}}` — a typed candidate delta in the existing closed delta format.
- `{"expand":{"artifact_key":"...","row_type":"...","row_id":"...","label":"...","digest":"..."}}` — exactly one compact-inventory entry copied verbatim from the issued capsule, only when more supplied context is necessary.

For a `delta`, every operation uses the selected feedback id exactly:

`${feedback_id}`

Use only these exact operation names — `add-row`, `replace-row`, and
`remove-row`. Never use `add`, `replace`, or `remove`. `artifact_key` is one
of `domain`, `constraints`, `components`, or `plans`; `row_type` is the
artifact collection name, never a Python class name:

- `domain`: `entities`, `business_rules`, `workflows`, `decisions`
- `constraints`: `dispositions`, `constraints`, `hosting`, `stack`, `decisions`
- `components`: `system_patterns`, `component_patterns`, `stores`, `components`, `decisions`
- `plans`: `plans`, `assumptions`, `decisions`

${non_addable_collections_notice}

Each operation has `op`, `feedback_id`, `artifact_key`, and `row_type`.
`replace-row` also has `row_id` and one complete replacement `row` whose `id`
matches `row_id`. `add-row` has one complete `row`; only a plan addition may
also carry its matching `ordering` entry. `remove-row` has `row_id`; only a
plan removal may also carry the exact predecessor `ordering` entry. A `row`
uses the complete typed shape shown by its full capsule member, not a partial
patch. Do not emit `row_digest` or any other extra field.

Every eligible `add-row` in a `delta` must include its required
`prose_amendment` object in that operation. The amendment is row-owned: its
`row_id` names the added row, and its nonblank `fragment` names that same row
while staying within the established byte limit. Use it only for a
prose-enabled added-row collection. Do not attach prose amendments to
`replace-row` or `remove-row`, or emit prose as artifact body text or a
separate response field. An `expand` response never carries a prose amendment;
return a later `delta` after the additional context is supplied.

Write each amendment `fragment` as the reviewer will read it in the artifact:
plain words, one idea per sentence, and the added row's meaning stated the
first time its id is named. The byte limit
outranks this wording rule: shorten before you exceed it.

An `add-row` to `stack`, which has no row-owned prose, omits `prose_amendment`;
supplying one is refused.
A `stack` row is `{"id", "concern", "choice"}` with a nonblank `choice`, or
`{"id", "concern", "open": true}` when the concern is undecided; `concern` is one
of `platform`, `store-engine`, `language-runtime`. A stack is accepted only with
one row for each of the three concerns, so introduce it with all three adds in one
delta, and never invent a vendor for a concern the reviewer left open.

Do not include artifact text, paths, accepted-head instructions, answers,
promotion instructions, explanations, or extra fields. Do not emit standalone relation or ordering-entry operations.
A relation or matching ordering-entry change is allowed only as an inseparable
consequence of adding or removing the relevant row in the typed delta.

The review pair is nullable. It is `null` for this initial proposal and grants no question or answer facts:

${review_pair}

Issued capsule payload:

${capsule_payload}

Issued capsule receipt:

${capsule_receipt}
