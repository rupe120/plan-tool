You enrich an existing deterministic concept record from supplied evidence.

Use only the text inside EVIDENCE to propose concepts. PLAN CONTEXT may orient
you, but it is not evidence. Do not infer concepts from a title or general
knowledge. Copy a short, literal excerpt from EVIDENCE into each
`evidence_rationale` so support can be checked locally.

${response_format_block}

`children` is optional and contains objects of the same shape. Do not emit
more than ${max_breadth} concepts in any one collection or nest concepts more
than ${max_depth} levels deep. Do not emit IDs, review/sign-off decisions,
step ownership, deferrals, or persistence instructions. An empty supported
set is `{"concepts":[]}`.

PLAN CONTEXT (orientation only):
${plan_context}

EVIDENCE:
${evidence}
