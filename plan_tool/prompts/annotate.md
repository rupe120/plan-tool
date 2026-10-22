# Annotate plan implementation status

You are judging how much of an existing plan or notes document is
**already implemented** in the current repository. You are given the
document verbatim, the plan's per-step specs (when it is a plan-tool
plan), and the current contents of the code files it cites. Classify
each section as `IMPLEMENTED`, `PARTIAL`, or `NOT-IMPLEMENTED`, backed by
concrete code references.

Be precise; do not invent. Cite **symbolic anchors** — function names,
class names, constants, section headings — over raw line numbers, which
drift on every commit (e.g. `plan_tool/annotate.py:classify_plan_implementation`,
not `annotate.py:412`). Write file paths in full from the repo root.

## Plan spec

The blocks below are each step's `detail:` spec — the **spec to satisfy,
not evidence of implementation**. A spec existing on disk never by itself
implies the step is done; judge it only against the code grounding below.
When the document is not a plan-tool plan this section is empty and you
judge by markdown heading instead.

${step_specs_block}

## Code grounding

The blocks below are the current on-disk contents of the files the
document cites — the repo state to judge against. A file marked
**truncated** shows only its first bytes, so any verdict you ground on it
must set `confidence_low` rather than assume a symbol past the cut is
absent. A cited file that does not appear here did not resolve on disk —
a strong `NOT-IMPLEMENTED` signal.

${grounded_files_block}

## Document to classify

${source_body}

## What to produce

${response_format_block}

Rules:

- `status` is exactly one of `IMPLEMENTED`, `PARTIAL`, or `NOT-IMPLEMENTED`
  — no other value is valid, and a single unrecognized `status` discards
  the entire response.
- `code_refs` must be concrete `path:symbol` / `path:line` strings for
  `IMPLEMENTED` and `PARTIAL`, and an **empty array** for
  `NOT-IMPLEMENTED`. Prefer symbol anchors over raw line numbers.
- For `PARTIAL`, `code_refs` names the already-implemented portion and
  `remaining` states the not-yet-implemented remainder — the only part a
  follow-up plan should scope. Set `remaining` to `""` for `IMPLEMENTED`
  and `NOT-IMPLEMENTED`.
- Set `confidence_low` to `true` when grounding is uncertain — too few
  files resolved, or a verdict rests on a file marked truncated.

### Plan-tool plan input (the primary case)

When the document is a valid plan-tool plan, its substantive spec is the
frontmatter `steps:` block, and its `## Steps` prose body is just a
placeholder ("See the `steps:` block in the frontmatter"). Treat **each
frontmatter `steps:` entry as its own classifiable section**: the entry's
`description:` (or legacy `title:`) supplies the section `heading`, and its
`detail:` content (loaded into the **Plan spec** section above, matched by
that step text) is the spec to
judge against. Emit one array element per step entry with
`"is_step": true`, plus elements for any other substantive prose sections
(`Overview`, `Architecture`, `Risks`, …) with `"is_step": false`. Do not
emit a contentless `NOT-IMPLEMENTED` for the `## Steps` placeholder.

### Heading-less input (the rough-notes case)

When the document has no parseable `steps:` block and no markdown
headings, treat the entire file as a single section: emit exactly **one**
array element whose `heading` is a short synthesized label and whose
`status` / `evidence` / `code_refs` judge the whole document at once.
