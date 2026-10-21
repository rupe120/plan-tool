# Bounded roadmap stage feedback revision

Return exactly one unfenced JSON object. Do not include prose, Markdown fences,
an artifact, an authoring prompt, or any key outside the schema below.

${shared_revision_guidance}

Apply only the authorities in the issued context. Supply exactly one
`respond-feedback` operation for every active feedback id in its listed order.
Each feedback id may authorize at most ${max_material_operations_per_feedback}
material operation. Split the feedback into smaller requests when the allowed
operation or response budget cannot express it.

Effective limits:

- Active feedback items: ${max_active_feedback_items}
- Response bytes: ${max_response_bytes}
- Row prose amendment bytes: ${max_prose_amendment_bytes}

## Issued context

```json
${context_json}
```

## Closed response schema

```json
${operation_schema}
```
