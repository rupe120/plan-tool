# Proposal seed — docs/config only (must classify non-code)

Prose the backend turns into a plan via `create`. This seed is pure
documentation and configuration work with no source-code footprint. A correct
proposal must classify every step `change_type: non-code` and must NOT invent
a source-file footprint.

## Request

Our README is out of date and the project has no contributor guide. Rewrite
`README.md` so the install/run/test sections match the current `uv`-based
workflow, add a `CONTRIBUTING.md` describing the branch-and-PR flow, and add a
`.editorconfig` pinning indentation and final-newline rules so editors agree.
No code changes — this is documentation and editor configuration only.

## Expected labels (answer key)

The proposal scorer reads only this block. Label agreement is a set
comparison against `plan_tool/schema.py:ChangeType` — no LLM judge.

```json
{
  "expected_step_count_range": [1, 3],
  "expected_change_types": ["non-code"],
  "expected_dependency_shape": "any",
  "must_split": false,
  "expected_source_footprint": false,
  "notes": "Every emitted step must be change_type=non-code. The footprint must contain only docs/config paths (README.md, CONTRIBUTING.md, .editorconfig); any plan_tool/**.py or src/**.py footprint is a misclassification and a scoring failure."
}
```
