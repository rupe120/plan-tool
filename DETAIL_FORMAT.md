# DETAIL_FORMAT.md

> **Source of truth:** this doc is reference reading for humans and coding
> agents — the tool does **not** load it at runtime. The enforced contract
> lives in code: `_REQUIRED_H2_TOKENS` and
> `parse_detail_response` (`plan_tool/detail.py`, prompt
> `plan_tool/prompts/detail.md`). The format-version marker (below) is written by
> `stamp_detail_format_version_marker` (`plan_tool/detail.py`) and read back
> by `require_supported_detail_format_version`
> (`plan_tool/detail_artifacts.py`, re-exported from `plan_tool/detail.py`).
> If this doc and the code disagree, the code wins — fix the doc.

The on-disk schema for a step's **detail file** — the per-step markdown that
`plan-tool detail` authors and that `run` renders into the implementation
prompt. The plan file (`PLAN_FORMAT.md`) is the machine-readable source of
truth; a detail file is the human- and agent-facing deep-dive for one step.

## What writes detail

`plan-tool detail <plan>` (orchestrator `plan_tool/detail.py`, CLI
`plan_tool/cli/authoring.py`). One Claude call per step, retried up to twice
(`_MAX_INVOKE_ATTEMPTS`) when the response fails the parse gate. The plan's
`steps[].detail` frontmatter field is updated to point at the written file.
Run-grade detail is the sole supported input, selected by `steps[].detail`.
After a response parses, the writer
stamps the current format-version marker (below) into the body, replacing
anything the model proposed there, before the file is written to disk.

## Format

A detail file is **pure markdown — no YAML frontmatter.** The schema is a
fixed set of H2 sections in the body, beneath a single H1 title. (Contrast the
plan file, whose contract lives in frontmatter.) The body carries exactly one
machine-read line — the [format version marker](#format-version-marker) — and
nothing else in the body is machine metadata.

### Path convention

```
<plan_dir>/plan-details/<plan_slug>/<NN>-<step_slug>.md
```

- `plan_dir` — the directory holding the plan `.md`.
- `plan_slug` — the plan filename stem with a leading `<digit>-` priority
  prefix stripped (mirrors `PlanEntry.slug`).
- `NN` — the zero-padded step id (`01`, `02`, …) so lexical sort matches step
  order.
- `step_slug` — kebab-case from the step title: `[A-Za-z0-9]+` tokens,
  lowercased, single-character tokens and stopwords dropped, capped at 40
  chars on a `-` boundary. Falls back to `step` when empty.

Computed by `derive_detail_path()` (`plan_tool/detail_artifacts.py`).

## Section schema

```markdown
# <Step title>                  ← required H1; must be the first non-blank line

<!-- plan-tool:detail-format-version: 1 -->
                                 ← required. Written by `plan-tool detail`, not
                                   the model. First non-blank line after the H1.

## Summary                      ← required. 3–5 sentences for a reviewer skimming.
## Table of Contents            ← required. Bulleted list of every H2 below, in
                                  document order: `- [<Section>](#anchor) — blurb`.
## Why                          ← required. Justification for the step.
## Files                        ← required. Creates vs. edits; the footprint.
## Implementation               ← required. Intent over mechanics: what must hold +
                                  a recommended approach, grounded in real anchors;
                                  exact code left to the implementer. Keep the
                                  heading even for docs-only/verification steps.
## Tests                        ← required. The tests covering the behavior this
                                  step changes, and the green-before-done gate.
                                  One directive for feature and refactor alike;
                                  no ordering is requested or checked.
## Acceptance criteria          ← required. Checkable behaviors, as bullets.

## Input                        ← optional. Existing contract consumed by this
                                  step; omit when no contract input exists.
                                  Use for upstream artifacts, persisted
                                  contracts, sidecars, fields, and HEAD code
                                  anchors whose shape affects correctness.
## References                   ← optional. Authoritative docs; omit when none.
## Deferred                     ← optional. Out-of-scope work; omit when none.
```

### Field semantics

**Required H2s (seven).** `Summary`, `Table of Contents`, `Why`, `Files`,
`Implementation`, `Tests`, `Acceptance criteria`. Canonical token list:
`_REQUIRED_H2_TOKENS` in `plan_tool/detail.py`.

- **Matching is lenient.** Headings match case-insensitively on the **first
  word** only, and trailing words are allowed — `## Why we did this` satisfies
  `## Why`, `## Files (creates vs edits)` satisfies `## Files`. Section order
  is **not** enforced.
- **`Summary`** belongs immediately after the [format version marker](#format-version-marker) (which itself sits immediately after the H1).
- **`Table of Contents`** lists every H2 actually emitted, in order.
- **`Acceptance criteria`** bullets are parsed (`-`/`*`, single-line only) by
  `parse_acceptance_bullets()` and consumed by the deep verifier / reconcile
  to judge the step; keep each criterion runnable on its own line.

**Optional H2s.** `Input`, `References`, and `Deferred` are listed in the
prompt template or docs but deliberately **not** required. `Input` appears only
when the step consumes an existing data structure, persisted schema, API
surface, saved audit, output format, or dependency-step output whose shape
affects correctness. Use it to name what contract the step reads, which fields
or code locations it depends on, and what limits apply to verifying it. When
the input comes from another step, cite that owning step id and outcome instead
of restating the sibling step's implementation details. Explicit persisted
contract references that use a registered owner and field, such as
`SavedReview.recommendations`, must be paired with a HEAD code-location anchor
such as `plan_tool/review_persistence.py:SavedReview`; the data-contract audit
checks both pieces against HEAD. Ordinary commands, file paths, and backticked
prose are not contract references unless they use that registered owner/field
shape. `References` is omittable when web search surfaces no authoritative
docs, and `Deferred` when nothing is out of scope. Any other H2 is allowed and
is preserved verbatim.

### Format version marker

Every run-grade detail file `plan-tool detail` writes carries exactly this
line, the first non-blank line after the H1:

```
<!-- plan-tool:detail-format-version: N -->
```

- **Slot.** Leading blank lines before the H1 are ignored; the H1 must then
  be the document's first non-blank line, unindented, matching `# ` at column
  0 (`locate_detail_format_carrier` in `plan_tool/detail_artifacts.py`). The
  marker is the first non-blank line strictly after that H1. `## Summary` is
  the next H2, immediately after the marker.
- **Writer-owned.** `stamp_detail_format_version_marker`
  (`plan_tool/detail.py`) runs once, at write time, on every response
  `parse_detail_response` accepted: it drops any consecutive marker-shaped
  lines starting in the slot — well-formed or malformed, any payload — and
  replaces them with the current build's marker. The authoring prompt
  (`plan_tool/prompts/detail.md`) and its retry suffix (`_REPROMPT_SUFFIX`)
  both reserve the slot and name the marker's prefix but never show a
  version number, so a model can never author a value the writer doesn't
  choose. A marker-shaped line anywhere *else* in the body — inside a
  section, inside a fenced code block, or separated from the slot by a blank
  line — is ordinary prose and is left untouched.
- **Absent means legacy version 1.** A body with no valid carrier H1 (no
  column-0 H1, an indented H1, or non-blank preamble before one), or a
  carrier H1 with nothing marker-shaped in the slot, resolves to version 1 —
  every detail file this build authored before this marker existed.
- **Malformed refuses, it does not default.** A slot line that matches the
  marker's grammar but carries a non-ASCII-decimal-integer or unsupported
  payload is a declared value, not an absence, and refuses rather than
  reading as 1.
- **Readers refuse before reading the body.** Every semantic run-grade
  detail reader calls `require_supported_detail_format_version(text,
  path=...)` right after `read_text()`, before any truncation. An
  unsupported or malformed declaration raises `DetailFormatError` naming the
  declared value and `SUPPORTED_DETAIL_FORMAT_VERSIONS`; the invoking command
  stops before using the body (`run` surfaces its existing command-error
  outcome; a plan reader uses its existing validation-error handling).
  Reading never upgrades a declaration — upgrading is a separate, explicitly
  invoked action, never a side effect of parsing.
- **Recovering a refused file.** `plan-tool detail <slug> --step N --force
  --recover-refused --no-completeness` (optionally `--commit`) is the
  targeted repair route: it archives the one named refused-or-carrier-less
  target and replaces it with a stamped current body, without reading any
  other detail file in the bundle (sibling, already-implemented, or
  deterministic-grounding — each of those would itself call the reader gate
  and re-trip on any other refused sibling) and without running the
  post-write convergence loop or the whole-bundle completeness tail. Repeat
  per refused target, then run a fresh `plan-tool completeness-audit` once
  every target in the bundle is repaired.

### Authoring altitude and concept threads

The `Implementation` section should stay at the detail-file altitude: concrete
enough to preserve intent, constraints, contracts, real anchors, gotchas, and
accepted tradeoffs, but not so mechanical that incidental executor choices read
as mandatory design. This is a judgment rule for authors and reviewers, not a
parser rule, blocking lint rule, auto-rewrite behavior, new required H2, or new
YAML field.

| Keep at detail altitude | Cut or demote when merely mechanical |
| --- | --- |
| Invariants and observable behavior the implementation must preserve. | Exact pseudo-code or line-by-line algorithms that only illustrate one possible implementation. |
| Required signatures, names, status codes, token kinds, event boundaries, or ordering when those exact values are already fixed. | Full config, IAM, or payload blobs copied from a source plan when placeholders would carry the contract. |
| Cross-step contracts, file/symbol anchors, and call-site boundaries that later steps rely on. | Magic constants, API literals, speculative helper names, or local variable names that are examples rather than constraints. |
| Failure modes, rejected alternatives with reasons, and accepted tradeoffs. | Exhaustive test rosters better summarized as representative cases or acceptance checks. |
| Checkable acceptance outcomes and real anchors needed to verify them. | Brittle shell transcripts, temporary commands, or ticket bookkeeping that belongs in an executor note. |

Demoting mechanical detail does not mean deleting useful context. Keep it as an
`e.g.` example, a placeholder like `<project-id>`, an executor note, or a ticket
note when it helps the implementer understand the shape of the work without
making that exact mechanism the required design.

Do not use conceptual altitude as a reason to remove specificity that is the
constraint. Preserve the exact value, name, order, status code, token kind,
event boundary, file path, symbol anchor, invariant, contract, accepted
tradeoff, or rejected alternative when the implementer must satisfy that exact
thing.

When a recurring idea appears across plan prose, multiple step details,
acceptance criteria, audit findings, or convergence reporting, choose one
distinctive phrase for that concept thread and keep that phrase stable.
Surrounding prose can vary; the phrase gives reviewers and audit output a
stable identity to search for and report against.

Concept phrases identify evidence; they do not own capability routing. Feature
IDs and `step.features` remain the ownership mechanism for plan capabilities
and feature-thread checks, including `validate_feature_refs` and
`detect_self_referential_features` in `plan_tool/review.py`. Stable concept
phrases complement the plan-audit finding identity already expressed as
`[anchor-slug]` in `plan_tool/prompts/plan-audit.md` and carried forward by
`_format_carried_findings_block`; they do not create a new enforcement surface.

## Validation rules

Applied by `parse_detail_response()` (`plan_tool/detail.py`) to each Claude
response before it is written:

1. **First character must be `#`, and it must be a real, unindented H1 with
   a valid marker slot.** Leading preamble ("Sure, here's the file:") before
   the first column-0 `#` is stripped, not rejected. A response with no
   column-0 `#` heading, or whose first heading has no valid carrier slot
   (`locate_detail_format_carrier` returns `None` — e.g. the first heading is
   actually an H2), is rejected (`None`).
2. **Fences tolerated, conditionally.** Whether the document "opens with a
   fence" is decided by the same fenced-code scanner used everywhere else
   in this contract (`_fenced_code_spans`), not by pattern-matching the
   first line in isolation — a single-line inline code span containing a
   backtick (e.g. `` ```rm -rf /``` deletes files.``) is *not* a real
   opener (CommonMark forbids a backtick in a backtick fence's info
   string), and treating it as one let a real trailing example's closer
   get stripped as if it belonged to that fake wrap (round-14 review).
   - **Document does not open with a fence** (the common case). A
     trailing closer-shaped line is stripped only when the scanner
     reports it as a genuinely partner-less opener with nothing fenced
     before it (the original leniency for a lone trailing closer with no
     partner) — checked by comparing the scanner's reported unmatched
     position to the trailing line's own start, not by "does *any*
     unmatched fence exist in the document." A trailing line that is part
     of an already-complete fenced span (real content, e.g. `## Tests`
     showing command output) is protected. Critically, a trailing line
     that merely *looks* like a closer but sits inside a fence the model
     opened earlier and never validly closed is **also** protected, not
     stripped — the whole region from that real, dangling opener to EOF
     is genuine (if malformed) content, and truncating the last line of
     it would silently discard real content the same way marker search
     used to before rule 3.1's fix (round-14 review, the sibling hazard
     class to the one rule 3.1 already closed).
   - **Document does open with a fence.** The leading fence line is
     stripped unconditionally (and `lines[0]` itself must independently
     match the fence-open pattern, not merely position 0 of the joined
     text — a blank `lines[0]` falls through to the no-leading-fence
     case rather than crashing, round-15 review). A trailing
     closer is stripped only when it is a valid CommonMark closer for
     that specific opener — same character **and** run length at least as
     long (`_fence_run_closes`, shared with `_fenced_code_spans`'s own
     closer check) — so a different-character or shorter-run trailing
     fence is protected as provably separate, legitimate content, common
     when the leading fence is itself never closed. **And** only when the
     scanner pairs the leading span through EOF or reports the trailing
     candidate itself as the unmatched scanner artifact created by
     same-length nesting. An unrelated later unmatched opener does not
     authorize stripping the trailing line. A leading fence that closes
     validly *earlier* means any later fence-shaped trailing line is
     unrelated content, even if it
     coincidentally shares the leading opener's character and length
     (round-15 review, the third instance of rule 2's own hazard class:
     round 14 closed it for the no-leading-fence case and for a
     misdetected leading fence; this closes it for a validly-but-early-closed
     leading fence).
3. **A response that is neither a plain, unwrapped title nor
   sentinel-delimited (below) is unparseable → hard reject** (`None`).
   Earlier revisions guessed at which fenced block in an ambiguous response
   was the real one; every such heuristic was defeated by a new adversarial
   input across several rounds (2026-09-08 authored-artifact-format-version
   handoff, review passes 5–13). Rule 3.1 replaces guessing with an
   explicit, non-positional boundary instead.
   - **3.1. Wrapper sentinel.** When the model can't avoid adding
     commentary or a fence around the file, it may bracket the file exactly
     between two lines, each used exactly once and alone on its own line —
     `<!-- plan-tool:detail-response-start -->` immediately before the `#`
     title (commentary is tolerated inside the brackets too, before the
     title) and `<!-- plan-tool:detail-response-end -->` immediately after
     the file's last line, before the deferrals envelope (§ below), never
     inside it — the envelope is always the true final content of the
     response either way. `parse_detail_response` checks for the sentinel
     **before** the plain unwrapped path, unconditionally, whenever exactly
     one of each marker is present outside fenced code: the wrapped
     content's own `#` title is often already unfenced and would otherwise
     be found directly by the plain path, silently ignoring the end marker
     and anything after it that the sentinel exists to exclude. Extraction
     is a substring slice between the two markers, not an inference about
     which candidate is real, so a preamble before the start marker is
     excluded unconditionally regardless of its own shape — but *locating*
     the markers does exclude fenced occurrences (so an illustrative fenced
     example of the syntax elsewhere in the body can't be mistaken for a
     real boundary). Zero, or more than one, of either marker outside
     fenced code is ambiguous and rejected (`None`) rather than resolved
     by guessing which occurrence is real. The deferrals-envelope search
     (§ below) has the identical fence and ambiguity handling.
     **Marker search always treats every fenced span as excluded,
     including a trailing unmatched-to-EOF one** (unlike rule 2's own
     trailing-fence-stripping leniency, which is a different mechanism for
     a different purpose). A round-9–12 design instead trusted a trailing
     unmatched span as real text specifically so a marker sitting after a
     same-length nested example fence's mis-scanned wrap could still be
     found — round 13 found that same trust let an illustrative,
     genuinely-never-closed fence elsewhere in a response (containing a
     coincidental marker-shaped line) win the same way, silently
     truncating real content instead of being rejected. The two cases are
     indistinguishable from the text alone without a nesting-aware
     scanner, which this codebase does not have (round 12 verified the
     one candidate for reuse, the then-located `jira_grade.fenced_spans`, does not handle
     nesting correctly either). Given that, marker search always fails
     closed: a sentinel-wrapped response containing a same-length nested
     example fence now correctly rejects (triggers a retry) rather than
     risking the corruption class round 13 found. This is a deliberate,
     user-confirmed trade-off (2026-09-11), not an oversight — see the
     2026-09-08 authored-artifact-format-version handoff's review pass 13
     triage.
4. **Missing required sections:**
   - **Two or more missing → hard reject** (`None`); `detail` retries, then
     errors. Too much to fabricate in a stub.
   - **Exactly one missing → auto-stubbed.** A heading is synthesized with the
     body marker `_(stub: model omitted this section — fill in manually)_` so
     the on-disk file still carries all seven H2s for downstream readers. The
     marker is grep-friendly — audit how often it fires.
5. **Stamped at write time.** Once a response clears rules 1–4, the accepted
   body is passed to `stamp_detail_format_version_marker` immediately before
   the write — see [Format version marker](#format-version-marker).

A rejected parse consumes one of the two invoke attempts. The retry appends
`_REPROMPT_SUFFIX`, which restates the exact constraints above, with one
exception: when the body parses and only the trailing deferrals envelope is
missing or is a complete envelope comment holding invalid JSON, the retry is
an envelope-only `## Repair` prompt (the original prompt, the rejected reply, and a request for the
envelope alone). The accepted body plus the repair reply are joined and
validated as one response, and the joined text is the checkpoint payload. A
repair reply that is not exactly one envelope, or that fails validation, uses
the second attempt and fails the step like any other rejected parse. A
cut-off envelope (no closing `-->`), or a marker-like line inside the body,
takes the full-regeneration retry instead.

## Parsing helpers (for consumers)

- `parse_detail_file_sections(text) -> {token: body}` — splits a file into its
  sections keyed by the lowercased first heading word (`sections.get("tests")`).
  Each body runs from the line after its heading to the next H1/H2/EOF.
- `parse_acceptance_bullets(body) -> list[str]` — the `## Acceptance criteria`
  bullets, leading marker stripped. Empty list signals "fall back to the
  standard reconcile verdict."
- `require_supported_detail_format_version(text, *, path=None) -> None`
  (`plan_tool/detail_artifacts.py`) — raises `DetailFormatError` when `text`
  declares an unsupported or malformed format version, else returns `None`.
  Validates only; consumers call it on the full text right after their own
  `read_text()`, before any truncation.

## Example (abridged)

```markdown
# Wire branch-awareness config leaf

<!-- plan-tool:detail-format-version: 1 -->

## Summary
Adds a `branch_awareness_enabled` flag to project config so `run` can opt into
the attach-branch guard. Three call sites read it; default is off.

## Table of Contents
- [Why](#why) — the motivation
- [Files](#files) — footprint
- [Implementation](#implementation) — the change
- [Tests](#tests) — coverage
- [Acceptance criteria](#acceptance-criteria) — checks

## Why
The guard must stay opt-in so existing repos are unaffected …

## Files
- edits: `plan_tool/project_config.py`
- creates: `tests/test_project_config.py`

## Implementation
Add the leaf with a `False` default …

## Tests
Feature step — implement the leaf, then add `test_project_config.py` covering
default-off and explicit-on; all green before finishing.

## Acceptance criteria
- `load_config()` returns `branch_awareness_enabled=False` when the key is absent
- setting the key to `true` round-trips through write/read
```

## See also

- `SEED_FORMAT.md` — authoring directives for the seed the plan (and its
  detail bundle) was created from.
- `PLAN_FORMAT.md` — the plan file (`steps[].detail` points at these files).
- `JIRA_FORMAT.md` — the exported jira-story files (also under `plan-details/`).
- `docs/how-to/pipeline/detail.md` — the authoring/convergence *workflow* (this doc is the
  *format*).
