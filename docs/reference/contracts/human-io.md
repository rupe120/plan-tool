# Human-input filesystem record protocol

`plan_tool/human_io.py:make_human_input_provider`,
`HumanInputRequest`, and `HumanInputResolution` are the source of truth for
the filesystem-record protocol. `plan_tool/review_walk.py:walk_recommendations`
and the caller-specific `plan_tool/cli/review_cmd.py:cmd_review` and
`cmd_review_walk` handlers enforce the restricted remote review behavior
documented below. If this reference disagrees with the landed code, the code
wins.

## Scope

This protocol supports the two remote reads in the review walk only:

- `review-walk.annotation`
- `review-walk.feedback`

The only caller-side non-TTY exceptions are the inline `cmd_review` entry and
the standalone `cmd_review_walk` entry described in [Restricted remote
review](#restricted-remote-review). It does not define behavior for other
direct-input or human-availability routes.

## Configure a provider

Leave `PLAN_TOOL_HUMAN_IO` unset to preserve the review walk's terminal
callback behavior. Set both variables to use the filesystem provider:

```text
PLAN_TOOL_HUMAN_IO=remote
PLAN_TOOL_HUMAN_IO_DIR=/path/to/existing/shared-directory
```

`PLAN_TOOL_HUMAN_IO_DIR` must name an existing, readable, writable, and
searchable directory. An explicit mode other than `remote`, or an invalid
directory, raises an error; neither condition silently selects terminal input.
Remote mode has no default answer and never falls back to terminal input.

## Restricted remote review

`plan_tool/cli/review_cmd.py:register` provides the only two command handlers
that can start this restricted remote non-TTY annotation walk:

- `cmd_review` serves the inline `reconcile-plan` command and its `reconcile`
  and `review` aliases. It may walk either an eligible saved plan-wide review
  selected for reuse or the saved result of an ordinary fresh review. The fresh
  route excludes `--refresh`, and either route requires a promptable finding;
  `--no-walk`, `--no-save`, and `--dry-run` suppress this inline walk.
- `cmd_review_walk` serves the standalone `reconcile-plan-walk` command and
  its `reconcile-walk` and `review-walk` aliases. It first selects an eligible
  final saved review for the named plan: an eligible matching `--id`, or the
  newest eligible final saved review when `--id` is absent. It does not inherit
  the inline route's fresh-review, reuse, or walk-suppression rules.

Both entries require the configured filesystem provider described in
[Configure a provider](#configure-a-provider), including both remote
environment variables, and non-TTY stdin. Setting only
`PLAN_TOOL_HUMAN_IO=remote`, non-TTY stdin alone, or `--yes` alone does not
start a restricted walk. Ordinary non-TTY input still reports saved findings
without walking them unless the applicable caller-specific conditions also
hold.

Each restricted `review-walk.annotation` request advertises this closed prompt:

```text
  (s)kip / (q)uit >
```

`s` and `skip` use the existing saved-review annotation path to persist
`Annotation(status="skip", note="")` for the finding. `q` and `quit` end the
walk without creating an annotation. A blank response or any other response
also ends the walk after that annotation request without an annotation, action,
or feedback request. The provider's request and resolution records are protocol
traffic; this skip annotation is the restricted route's only review-state
update. It does not dispatch a review action, collect feedback, or mutate a
plan or code.

On eligible saved-review reuse, a skipped finding remains visible in the report
but is not promptable again. Other terminal annotations receive the same
report-only treatment; a `failed` annotation remains promptable under the
normal selection rule.

Remote mode with TTY stdin retains the full annotation and feedback menu for
both callers. These caller-specific exceptions do not grant remote access to
other `walk_recommendations` callers, including the data-contract,
reconciliation, and completeness routes. They also do not change the
`_render_refresh` route, remote feedback handoff, or provider lifecycle policy.

## Records

Each prompt has one generated `request_id`. Its records are siblings in the
configured directory:

```text
<request_id>.request.json
<request_id>.resolution.json
```

The provider publishes this request record. `request_id` is the generated
identity for this read, `prompt_id` is its stable prompt purpose, and `prompt`
is the text displayed to the operator. This example is the full remote TTY
annotation prompt; the restricted remote non-TTY prompt is documented above:

```json
{
  "prompt": "  (a)pply [default] / (s)kip / (f)eedback / (r)un / (aa) apply-all / (q)uit / (?) help > ",
  "prompt_id": "review-walk.annotation",
  "request_id": "57d9bb95e9034ce3a6292857d1e95a57"
}
```

The operator publishes the matching resolution record:

```json
{
  "request_id": "57d9bb95e9034ce3a6292857d1e95a57",
  "text": "a"
}
```

Use the emitted request identity exactly. Every actual read receives a fresh
request identity, so an operator must answer the request record that appears
rather than choosing an identifier.

## Operator lifecycle

1. The provider publishes the complete request record at its final path.
2. Read that final request record and prepare a resolution with the same
   `request_id` and the response text.
3. Write the complete resolution to a sibling temporary path, then publish it
   to the final resolution path without replacing an existing file.
4. The provider waits while only the temporary resolution exists. It reads
   only the final resolution path, then returns its matching text to the
   review walk.

Both final records require complete-before-visible, no-clobber publication.
Use an exclusive create or an equivalent operation when publishing the final
resolution; do not rename over an existing final record.

## Errors and safety rules

The provider refuses to overwrite an existing final request or resolution
record. Malformed final resolution JSON (including a non-object), a missing or
non-text `request_id` or `text`, and a resolution whose `request_id` differs
from the request all raise an error instead of becoming an answer. Those
failures leave the existing final records in place and do not overwrite either
record.

The provider waits for a final resolution record without a timeout. Temporary
resolution files are not answers, and no default, terminal fallback,
authorization, conflict rule, advisory delivery, or alternate transport is
defined by this proof.
