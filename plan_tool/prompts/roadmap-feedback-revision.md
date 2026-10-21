You are revising one selected roadmap feedback request. Return only one unfenced
JSON object with no surrounding text.

Selected artifact: `${artifact_key}` at `${artifact_path}`
Selected feedback: `${feedback_id}`
Feedback state: `${feedback_state}`
Feedback request:
${feedback_request}

Selected target row: `${target_row_id}` (`${target_row_type}`)
Allowed presentation fields and current values:
${allowed_fields}

Immutable relation summary:
${relation_summary}

${update_judgment}

Return this closed shape exactly:

{
  "operations": [
    {
      "op": "replace-row-presentation",
      "row_id": "${target_row_id}",
      "field": "one allowed field name",
      "value": "a non-empty replacement"
    },
    {
      "op": "respond-feedback",
      "feedback_id": "${feedback_id}",
      "proposed_response": "a non-empty proposed response"
    }
  ]
}

The presentation replacement is optional. When present it must be first. The
final operation must always respond to the selected feedback. Do not add,
remove, reorder, or otherwise modify rows or relations.
