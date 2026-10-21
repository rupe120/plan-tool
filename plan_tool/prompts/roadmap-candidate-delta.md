# Immutable roadmap candidate proposal

Work only from the issued batch payload and receipt below. They are the complete
authority for this request. Do not inspect repository files, root documentation,
filesystem paths, an accepted head, or any other source.

Return one unfenced JSON object and nothing else. Its root must contain exactly
these fields:

```json
{"operations":[...],"responses":[...],"derived_feedback":[...]}
```

`operations` is the existing typed candidate-delta array. Use only `add-row`, `replace-row`,
`remove-row`, and `correct-prose`. Each operation's `feedback_id` must name one
issued reviewer item from `reviewer_items`; do not name an item outside that
batch. The compact inventory is discovery-only and does not authorize an edit.
Never use `add`, `replace`, or `remove`.

${non_addable_collections_notice}

Use these complete closed operation envelopes. They are writable operations,
not `existing_rows` discovery records. `ordering` is `null` for every row
type except `plans`. A `plans` `add-row` or `remove-row` requires an `ordering` object naming
that plan (`plan_id`, with optional `depends_on` and `assumption_targets`); a removal repeats the
plan's existing ordering entry exactly.

An `add-row` must be grounded in a reviewed row: it cites a reached existing row or a
grounded added row, or a reached existing row you replace in the same response cites it.
Added rows that only cite each other are refused. A value-only entity therefore needs a
`replace-row` that makes a reached existing row reference it.

Every eligible `add-row` must include its required `prose_amendment` object in
that operation. The amendment is row-owned: its `row_id` names the added row,
and its nonblank `fragment` names that same row while staying within the
established byte limit. Use it only for a prose-enabled added-row collection.
Do not attach prose amendments to `replace-row` or `remove-row`, or emit prose
as artifact body text or a separate response field.

Write each amendment `fragment` and each `correct-prose` `replacement` as the
reviewer will read it in the artifact: plain words, one idea per sentence, the
added row's meaning stated the first time its id is named, and every condition
of the original kept. The byte limit
outranks this wording rule: shorten before you exceed it.

An `add-row` to `stack`, which has no row-owned prose, omits `prose_amendment`;
supplying one is refused.
A `stack` row is `{"id", "concern", "choice"}` with a nonblank `choice`, or
`{"id", "concern", "open": true}` when the concern is undecided; `concern` is one
of `platform`, `store-engine`, `language-runtime`. A stack is accepted only with
one row for each of the three concerns, so introduce it with all three adds in one
delta, and never invent a vendor for a concern the reviewer left open.

${operation_shapes}

`correct-prose` replaces the text of one shared-narrative span the payload issued
(a `source_spans` entry on a full member, or an entry in the payload's top-level
`shared_source_spans` table, which a member names in `shared_source_span_ids`) and
changes no typed row. A table entry belongs to the artifact in its `artifact_key`:
copy that `artifact_key` and the entry's `span_id` into the operation. Use it only to fix a stale or
wrong narrative block that an issued span covers. Its closed envelope is:

```json
{"op":"correct-prose","feedback_id":"<issued reviewer item id>","artifact_key":"<artifact key>","span_id":"<issued span_id>","replacement":"<corrected block text>"}
```

All five keys are required and no others are allowed. `span_id` is copied exactly
from an issued span entry, and `replacement` is the full corrected text
of that one block: nonblank and at most 4096 bytes. A `span_id` the payload did not
issue grants no authority, and neither does a reference to a removed row. Never
correct other body text, select text by marker, or emit an empty replacement to
delete. The correction text travels only inside this operation, never as a
separate response field. One feedback item may carry a correction beside its other
operations, but a candidate that adds, replaces, or removes a row in the span's
`owning_row_ids` is refused. Two corrections of the same span are refused.

For an entity `add-row`, keep `row_type` as `entities` and do not emit
`collection` or `row_id`. For a `decisions` row, `source` is discovery-only
and is not writable; do not emit it in `row`.

Use the artifact collection name, never a Python class name. Do not emit `row_digest`.
Use this source-checked syntax guide for `row_type`; `PatternRow` can mean
`system_patterns` or `component_patterns`, and `existing_rows` identifies the
actual collection for each issued row. This guide does not grant edit authority:

${collection_hints}

`responses` has exactly one object for every issued `reviewer_items` entry and
no others. Each object is `{"item_id":"...","response":"..."}`. Copy each
`item_id` exactly and provide a nonempty response. Do not include target,
request, fingerprint, state, candidate revision id, or lifecycle fields.

`derived_feedback` is the complete fresh ordinary roadmap-derived set for this
successor. Each object is `{"context_id":"...","content":"..."}`. It may be
empty. Do not copy, match, explain, or carry forward entries from the supplied
derived context; it is evidence only. Do not emit duplicate context ids.

Do not include artifact feedback, removals, proposed responses, reviewer state,
artifact text, paths, accepted-head instructions, explanations, or extra fields.
A relation or matching ordering-entry change is allowed only as an inseparable
consequence of adding or removing the relevant typed row.
Do not emit standalone relation or ordering-entry operations.

The review pair is nullable. For a structural edit it carries the supplied correction as
context only; it grants no question or answer authority, reviewer items, operations,
relation edits, or artifact content:

${review_pair}

Issued batch payload:

${capsule_payload}

Issued batch receipt:

${capsule_receipt}
