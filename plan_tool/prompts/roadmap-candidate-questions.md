# Immutable roadmap candidate question

Work only from the stored candidate facts below. They are the complete authority
for this request. Do not inspect repository files, filesystem paths, a live
ledger, a live brief, an accepted head, current gates, or any other source.

Return one unfenced JSON object and nothing else. Its root must contain exactly
these two fields:

```json
{"anchor": {"kind": "..."}, "question": "..."}
```

`question` is opaque reviewer-facing text. Do not add an identifier, answer,
delta, explanation, artifact text, promotion instruction, or extra field.
Write `question` in plain words a reviewer can answer without opening the
stored facts: say what each thing you name is the first time you name it, and
ask one thing.

`anchor` must identify one supplied immutable fact using exactly one form:

- `{"kind":"feedback","artifact_key":"...","feedback_id":"..."}` for the selected feedback.
- `{"kind":"diff-row","artifact_key":"...","row_type":"...","row_id":"..."}` for one persisted changed row.
- `{"kind":"full-member","artifact_key":"...","row_type":"...","row_id":"..."}` for one supplied full closure member.
- `{"kind":"inventory","artifact_key":"...","row_type":"...","row_id":"..."}` for one compact inventory identity.
- `{"kind":"reviewer-item","artifact_key":"ledger","row_type":"reviewer-item","row_id":"..."}` for one admitted reviewer-item snapshot.
- `{"kind":"derived-context","artifact_key":"derived-context","row_type":"row","row_id":"..."}` for one supplied derived-context row.

Every anchor is discovery-only. It does not grant replacement edit authority.
The replacement request, if any, has a separate closed candidate-delta
contract and only the issued capsule controls its authority.

Active candidate version identity:

${initial_candidate_version_id}

Initial candidate content identity:

${initial_content_identity}

Stored predecessor version identity:

${predecessor_version_id}

Accepted root version identity (batch candidates only):

${root_version_id}

Direct source version identity (batch candidates only):

${source_version_id}

Immutable batch receipt identity (batch candidates only):

${batch_receipt_identity}

Selected feedback:

${feedback}

Persisted predecessor diff:

${predecessor_diff}

Ordered closure-member receipts:

${closure_members}

Declared-relation evidence:

${declared_relations}

Compact identity inventory:

${inventory}

Stored capsule receipt:

${capsule_receipt}

Stored review requirement:

${review_requirement}

Admitted reviewer-item snapshots (batch candidates only):

${reviewer_items}

Persisted derived-context rows (batch candidates only):

${derived_context}

When present, the stored review requirement is immutable disclosure for this
one question only. It grants no edit, replacement, promotion, or approval
authority.
