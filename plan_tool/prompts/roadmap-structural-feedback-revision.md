You will propose one strict V1 structural-revision envelope. Do not inspect files,
run tools, or write files. Use only the selected context below.

Selected artifact: `${artifact_key}`
Selected feedback id: `${feedback_id}`
Selected reviewer request:
${feedback_request}

Selected row:
- collection: `${target_collection}`
- id: `${target_row_id}`
- allowed scalar fields and current values:
${selected_scalars}

Selected scope context:
${target_scope_context}

Pre-existing rewrite regions, if any:
${rewrite_regions}

${update_judgment}

Reply with exactly one unfenced JSON object and no other text. The object must
contain exactly `version`, `operations`, and `feedback_response`. Set `version`
to `1`. `operations` is a non-empty array. Each operation is either a
`row-field` object with exactly `kind`, `collection`, `row_id`, `field`, and
`value`, or one `prose-region` object with exactly `kind`, `region_id`, and
`value`. Use only the selected row and listed scalar fields. At most one
`prose-region` operation is allowed and it must name a listed pre-existing
region. Include one single-line `feedback_response`. Do not add rows, remove
rows, reorder anything, alter decisions or relations, or target another
artifact.
